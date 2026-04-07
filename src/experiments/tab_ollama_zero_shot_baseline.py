#!/usr/bin/env python3
"""Run a local Ollama-backed zero-shot de-identification pilot on TAB.

This script executes a public, checkable pilot slice for the TAB benchmark
using a locally hosted open-weight model through the Ollama HTTP API. It does
not overwrite the released full TAB heuristic roster; instead it writes a
separate set of pilot artifacts that make the runtime conditions explicit.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import platform
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from tab_matched_baseline_suite import _char_coverage
from tab_matched_baseline_suite import _ground_truth_spans
from tab_matched_baseline_suite import _load_documents
from tab_matched_baseline_suite import _merge_spans
from tab_matched_baseline_suite import _span_counts


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = EXPERIMENTS_DIR / "external_data" / "tab"
PROMPT_TEMPLATE_PATH = EXPERIMENTS_DIR / "tab_zero_shot_prompt_template.txt"
SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "tab_ollama_zero_shot_results.csv"
DETAIL_OUTPUT_PATH = EXPERIMENTS_DIR / "tab_ollama_zero_shot_document_metrics.csv"
RUNTIME_MANIFEST_PATH = EXPERIMENTS_DIR / "tab_ollama_zero_shot_runtime_manifest.csv"
RUN_LOG_PATH = EXPERIMENTS_DIR / "tab_ollama_zero_shot_run_log.csv"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


def _build_prompt(document_text: str) -> str:
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.replace("{{DOCUMENT_TEXT}}", document_text)


def _changed_spans(original_text: str, sanitized_text: str) -> list[tuple[int, int]]:
    matcher = difflib.SequenceMatcher(a=original_text, b=sanitized_text, autojunk=False)
    spans: list[tuple[int, int]] = []
    for tag, start_a, end_a, _start_b, _end_b in matcher.get_opcodes():
        if tag == "equal":
            continue
        if end_a > start_a:
            spans.append((start_a, end_a))
    return _merge_spans(spans)


def _ollama_generate(prompt: str, model: str, ollama_url: str) -> dict[str, Any]:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        ollama_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read().decode("utf-8"))


def _ollama_model_metadata(model: str, ollama_url: str) -> dict[str, str]:
    tags_url = ollama_url.rsplit("/api/", 1)[0] + "/api/tags"
    with urllib.request.urlopen(tags_url, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    for row in payload.get("models", []):
        if str(row.get("name")) == model or str(row.get("model")) == model:
            details = row.get("details", {}) if isinstance(row.get("details"), dict) else {}
            return {
                "model_name": str(row.get("name", model)),
                "model_digest": str(row.get("digest", "")),
                "model_family": str(details.get("family", "")),
                "model_parameter_size": str(details.get("parameter_size", "")),
                "model_quantization": str(details.get("quantization_level", "")),
                "model_format": str(details.get("format", "")),
                "model_modified_at": str(row.get("modified_at", "")),
            }
    return {
        "model_name": model,
        "model_digest": "",
        "model_family": "",
        "model_parameter_size": "",
        "model_quantization": "",
        "model_format": "",
        "model_modified_at": "",
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _with_output_tag(path: Path, output_tag: str | None) -> Path:
    if not output_tag:
        return path
    safe_tag = output_tag.replace(" ", "_")
    return path.with_name(f"{path.stem}_{safe_tag}{path.suffix}")


def run_zero_shot_pilot(
    input_dir: Path,
    split: str,
    max_documents: int,
    model: str,
    ollama_url: str,
    output_tag: str | None = None,
) -> tuple[Path, Path, Path, Path]:
    summary_output_path = _with_output_tag(SUMMARY_OUTPUT_PATH, output_tag)
    detail_output_path = _with_output_tag(DETAIL_OUTPUT_PATH, output_tag)
    runtime_manifest_path = _with_output_tag(RUNTIME_MANIFEST_PATH, output_tag)
    run_log_path = _with_output_tag(RUN_LOG_PATH, output_tag)
    documents = [
        document
        for document in _load_documents(input_dir)
        if str(document.get("dataset_type", "")).lower() == split.lower()
    ]
    documents = documents[:max_documents]
    if not documents:
        raise ValueError("No TAB documents matched the requested split and max-document settings.")

    detail_rows: list[dict[str, str]] = []
    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_sensitive_chars = 0
    total_residual_sensitive_chars = 0
    total_non_sensitive_chars = 0
    total_preserved_non_sensitive_chars = 0
    total_mentions = 0
    prompt_eval_counts: list[int] = []
    eval_counts: list[int] = []
    latency_ms: list[float] = []
    run_started_at = datetime.now(UTC)
    model_metadata = _ollama_model_metadata(model, ollama_url)

    for index, document in enumerate(documents, start=1):
        text = str(document.get("text", ""))
        prompt = _build_prompt(text)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        started = time.perf_counter()
        response = _ollama_generate(prompt, model, ollama_url)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        sanitized_text = str(response.get("response", "")).strip() or text
        predicted_spans = _changed_spans(text, sanitized_text)
        gold_spans = _ground_truth_spans(document)
        true_positive, false_positive, false_negative = _span_counts(predicted_spans, gold_spans)
        gold_chars = _char_coverage(gold_spans)
        pred_chars = _char_coverage(predicted_spans)
        total_chars = set(range(len(text)))
        non_sensitive_chars = total_chars - gold_chars
        residual_sensitive_chars = len(gold_chars - pred_chars)
        preserved_non_sensitive_chars = len(non_sensitive_chars - pred_chars)

        total_tp += true_positive
        total_fp += false_positive
        total_fn += false_negative
        total_sensitive_chars += len(gold_chars)
        total_residual_sensitive_chars += residual_sensitive_chars
        total_non_sensitive_chars += len(non_sensitive_chars)
        total_preserved_non_sensitive_chars += preserved_non_sensitive_chars
        total_mentions += len(gold_spans)
        prompt_eval_counts.append(int(response.get("prompt_eval_count", 0) or 0))
        eval_counts.append(int(response.get("eval_count", 0) or 0))
        latency_ms.append(elapsed_ms)
        if index == 1 or index == len(documents) or index % 5 == 0:
            print(
                f"Processed {index}/{len(documents)} TAB {split} documents for {model}",
                flush=True,
            )

        detail_rows.append(
            {
                "document_id": str(document.get("doc_id", "unknown")),
                "split": str(document.get("dataset_type", "unknown")),
                "prompt_hash": prompt_hash[:16],
                "gold_mentions": str(len(gold_spans)),
                "predicted_spans": str(len(predicted_spans)),
                "span_tp": str(true_positive),
                "span_fp": str(false_positive),
                "span_fn": str(false_negative),
                "per_percent": f"{(100.0 * residual_sensitive_chars / len(gold_chars)) if gold_chars else 0.0:.1f}",
                "text_retention": f"{(preserved_non_sensitive_chars / len(non_sensitive_chars)) if non_sensitive_chars else 1.0:.3f}",
                "prompt_eval_count": str(prompt_eval_counts[-1]),
                "eval_count": str(eval_counts[-1]),
                "latency_ms": f"{elapsed_ms:.1f}",
            }
        )

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    per_percent = 100.0 * total_residual_sensitive_chars / total_sensitive_chars if total_sensitive_chars else 0.0
    text_retention = total_preserved_non_sensitive_chars / total_non_sensitive_chars if total_non_sensitive_chars else 1.0

    with summary_output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "benchmark",
                "method",
                "split",
                "document_count",
                "mention_count",
                "span_precision",
                "span_recall",
                "span_f1",
                "per_percent",
                "text_retention",
                "mean_prompt_eval_count",
                "mean_eval_count",
                "mean_latency_ms",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "benchmark": "TAB",
                "method": "Prompted LLM zero-shot de-identification",
                "split": split,
                "document_count": str(len(documents)),
                "mention_count": str(total_mentions),
                "span_precision": f"{precision:.2f}",
                "span_recall": f"{recall:.2f}",
                "span_f1": f"{f1:.2f}",
                "per_percent": f"{per_percent:.1f}",
                "text_retention": f"{text_retention:.2f}",
                "mean_prompt_eval_count": f"{_mean([float(value) for value in prompt_eval_counts]):.1f}",
                "mean_eval_count": f"{_mean([float(value) for value in eval_counts]):.1f}",
                "mean_latency_ms": f"{_mean(latency_ms):.1f}",
                "notes": "Executed local open-weight zero-shot pilot on a TAB subset with the fixed prompt surface.",
            }
        )

    with detail_output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(detail_rows[0].keys()))
        writer.writeheader()
        writer.writerows(detail_rows)

    run_finished_at = datetime.now(UTC)

    with runtime_manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "run_id",
                "benchmark",
                "method",
                "scope",
                "model_tag",
                "model_digest",
                "model_family",
                "model_parameter_size",
                "model_quantization",
                "model_format",
                "model_modified_at",
                "prompt_template",
                "document_count",
                "split",
                "mean_prompt_eval_count",
                "mean_eval_count",
                "mean_latency_ms",
                "hardware_summary",
                "os_runtime",
                "python_runtime",
                "run_started_at_utc",
                "run_finished_at_utc",
                "memory_usage_note",
                "ollama_url",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "run_id": f"tab-ollama-zeroshot-{split}-{len(documents):03d}",
                "benchmark": "TAB",
                "method": "Prompted LLM zero-shot de-identification",
                "scope": f"public TAB {split} subset pilot",
                "model_tag": model,
                "model_digest": model_metadata["model_digest"],
                "model_family": model_metadata["model_family"],
                "model_parameter_size": model_metadata["model_parameter_size"],
                "model_quantization": model_metadata["model_quantization"],
                "model_format": model_metadata["model_format"],
                "model_modified_at": model_metadata["model_modified_at"],
                "prompt_template": PROMPT_TEMPLATE_PATH.name,
                "document_count": str(len(documents)),
                "split": split,
                "mean_prompt_eval_count": f"{_mean([float(value) for value in prompt_eval_counts]):.1f}",
                "mean_eval_count": f"{_mean([float(value) for value in eval_counts]):.1f}",
                "mean_latency_ms": f"{_mean(latency_ms):.1f}",
                "hardware_summary": f"{platform.system()} {platform.release()} | {platform.processor()}",
                "os_runtime": platform.platform(),
                "python_runtime": sys.version.split()[0],
                "run_started_at_utc": run_started_at.isoformat(),
                "run_finished_at_utc": run_finished_at.isoformat(),
                "memory_usage_note": "Not exposed by the Ollama generate API in this pilot; keep as unresolved metadata.",
                "ollama_url": ollama_url,
                "notes": "This runtime manifest records a local open-weight pilot slice rather than a full released TAB rerun.",
            }
        )

    split_counts = {split: len(documents)}
    with run_log_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "benchmark",
                "method",
                "family",
                "execution_status",
                "input_scope",
                "document_count",
                "mention_count",
                "split_breakdown",
                "model_tag",
                "model_digest",
                "prompt_template",
                "summary_output",
                "detail_output",
                "runtime_manifest",
                "command_template",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "benchmark": "TAB",
                "method": "Prompted LLM zero-shot de-identification",
                "family": "Semantic baseline",
                "execution_status": "executed_pilot",
                "input_scope": f"public ECHR JSON release ({split} subset)",
                "document_count": str(len(documents)),
                "mention_count": str(total_mentions),
                "split_breakdown": " | ".join(f"{key}:{value}" for key, value in split_counts.items()),
                "model_tag": model,
                "model_digest": model_metadata["model_digest"],
                "prompt_template": PROMPT_TEMPLATE_PATH.name,
                "summary_output": summary_output_path.name,
                "detail_output": detail_output_path.name,
                "runtime_manifest": runtime_manifest_path.name,
                "command_template": f"python src/experiments/tab_ollama_zero_shot_baseline.py --split {split} --max-documents {max_documents} --model {model}",
                "notes": "Executed local Ollama-backed pilot slice under the fixed TAB zero-shot prompt surface.",
            }
        )

    return summary_output_path, detail_output_path, runtime_manifest_path, run_log_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local Ollama-backed TAB zero-shot pilot.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Directory containing TAB JSON files.")
    parser.add_argument("--split", default="dev", choices=["train", "dev", "test"], help="TAB split to execute.")
    parser.add_argument("--max-documents", type=int, default=16, help="Maximum number of TAB documents to execute.")
    parser.add_argument("--model", default="llama3:latest", help="Ollama model tag to execute.")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama generate API endpoint.")
    parser.add_argument("--output-tag", help="Optional suffix used to avoid overwriting the canonical pilot artifacts.")
    args = parser.parse_args()

    try:
        summary, detail, runtime_manifest, run_log = run_zero_shot_pilot(
            input_dir=args.input_dir,
            split=args.split,
            max_documents=args.max_documents,
            model=args.model,
            ollama_url=args.ollama_url,
            output_tag=args.output_tag,
        )
    except urllib.error.URLError as error:
        raise SystemExit(f"Unable to reach the Ollama API at {args.ollama_url}: {error}") from error

    print(f"TAB Ollama zero-shot summary written to {summary}")
    print(f"TAB Ollama zero-shot detail metrics written to {detail}")
    print(f"TAB Ollama zero-shot runtime manifest written to {runtime_manifest}")
    print(f"TAB Ollama zero-shot run log written to {run_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())