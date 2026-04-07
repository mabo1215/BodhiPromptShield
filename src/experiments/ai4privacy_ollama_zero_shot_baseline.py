#!/usr/bin/env python3
"""Run a local Ollama-backed zero-shot de-identification pilot on AI4Privacy records."""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import platform
import sys
import time
import urllib.request
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from build_ai4privacy_pii300k_export import DEFAULT_OUTPUT as DEFAULT_EXPORT_PATH


EXPERIMENTS_DIR = Path(__file__).resolve().parent
PROMPT_TEMPLATE_PATH = EXPERIMENTS_DIR / "ai4privacy_zero_shot_prompt_template.txt"
SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "ai4privacy_ollama_zero_shot_results.csv"
DETAIL_OUTPUT_PATH = EXPERIMENTS_DIR / "ai4privacy_ollama_zero_shot_document_metrics.csv"
RUNTIME_MANIFEST_PATH = EXPERIMENTS_DIR / "ai4privacy_ollama_zero_shot_runtime_manifest.csv"
RUN_LOG_PATH = EXPERIMENTS_DIR / "ai4privacy_ollama_zero_shot_run_log.csv"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_BENCHMARK_NAME = "AI4Privacy PII-Masking-300K (English)"
DEFAULT_SCOPE = "public multi-domain pii pilot"
DEFAULT_INPUT_SCOPE = "public AI4Privacy normalized text export"
DEFAULT_NOTES = "Executed local open-weight zero-shot pilot on a held-out public AI4Privacy English slice."
DEFAULT_RUNTIME_NOTES = "Executed on the public AI4Privacy PII-Masking-300K English export under a generic de-identification prompt."
DEFAULT_RUN_LOG_NOTES = "Executed local Ollama-backed pilot on a held-out AI4Privacy English slice."


def _load_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _build_prompt(text: str) -> str:
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.replace("{{NOTE_TEXT}}", text)


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    merged: list[list[int]] = [[spans[0][0], spans[0][1]]]
    for start, end in sorted(spans):
        current = merged[-1]
        if start <= current[1]:
            current[1] = max(current[1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _changed_spans(original_text: str, sanitized_text: str) -> list[tuple[int, int]]:
    matcher = difflib.SequenceMatcher(a=original_text, b=sanitized_text, autojunk=False)
    spans: list[tuple[int, int]] = []
    for tag, start_a, end_a, _start_b, _end_b in matcher.get_opcodes():
        if tag != "equal" and end_a > start_a:
            spans.append((start_a, end_a))
    return _merge_spans(spans)


def _char_coverage(spans: list[tuple[int, int]]) -> set[int]:
    covered: set[int] = set()
    for start, end in spans:
        covered.update(range(start, end))
    return covered


def _span_counts(predicted: list[tuple[int, int]], gold: list[tuple[int, int]]) -> tuple[int, int, int]:
    matched_gold: set[int] = set()
    true_positive = 0
    for pred in predicted:
        best_idx = -1
        best_overlap = 0
        for idx, gold_span in enumerate(gold):
            if idx in matched_gold:
                continue
            overlap = max(0, min(pred[1], gold_span[1]) - max(pred[0], gold_span[0]))
            if overlap > best_overlap:
                best_idx = idx
                best_overlap = overlap
        if best_idx != -1 and best_overlap > 0:
            matched_gold.add(best_idx)
            true_positive += 1
    return true_positive, max(0, len(predicted) - true_positive), max(0, len(gold) - true_positive)


def _ollama_generate(prompt: str, model: str, ollama_url: str) -> dict[str, Any]:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(ollama_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
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
    return {"model_name": model, "model_digest": "", "model_family": "", "model_parameter_size": "", "model_quantization": "", "model_format": "", "model_modified_at": ""}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _with_output_tag(path: Path, output_tag: str | None) -> Path:
    if not output_tag:
        return path
    return path.with_name(f"{path.stem}_{output_tag}{path.suffix}")


def run_zero_shot_pilot(
    input_path: Path,
    model: str,
    ollama_url: str,
    max_records: int | None,
    output_tag: str | None = None,
    benchmark_name: str = DEFAULT_BENCHMARK_NAME,
    scope: str = DEFAULT_SCOPE,
    input_scope: str = DEFAULT_INPUT_SCOPE,
    summary_notes: str = DEFAULT_NOTES,
    runtime_notes: str = DEFAULT_RUNTIME_NOTES,
    run_log_notes: str = DEFAULT_RUN_LOG_NOTES,
) -> tuple[Path, Path, Path, Path]:
    summary_output_path = _with_output_tag(SUMMARY_OUTPUT_PATH, output_tag)
    detail_output_path = _with_output_tag(DETAIL_OUTPUT_PATH, output_tag)
    runtime_manifest_path = _with_output_tag(RUNTIME_MANIFEST_PATH, output_tag)
    run_log_path = _with_output_tag(RUN_LOG_PATH, output_tag)
    records = _load_records(input_path)
    if max_records is not None:
        records = records[:max_records]
    if not records:
        raise ValueError("No AI4Privacy records were found.")

    detail_rows: list[dict[str, str]] = []
    prompt_eval_counts: list[int] = []
    eval_counts: list[int] = []
    latency_ms: list[float] = []
    total_tp = total_fp = total_fn = 0
    total_sensitive_chars = total_residual_sensitive_chars = 0
    total_non_sensitive_chars = total_preserved_non_sensitive_chars = 0
    total_mentions = 0
    run_started_at = datetime.now(UTC)
    model_metadata = _ollama_model_metadata(model, ollama_url)

    for record in records:
        text = str(record.get("text", ""))
        prompt = _build_prompt(text)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        started = time.perf_counter()
        response = _ollama_generate(prompt, model, ollama_url)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        sanitized_text = str(response.get("response", "")).strip() or text
        predicted_spans = _changed_spans(text, sanitized_text)
        gold_spans = [(int(span["start"]), int(span["end"])) for span in record.get("phi_spans", [])]
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

        detail_rows.append(
            {
                "note_id": str(record.get("note_id", "unknown")),
                "split": str(record.get("split", "unknown")),
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
    split = str(records[0].get("split", "unknown"))

    with summary_output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["benchmark", "method", "split", "note_count", "mention_count", "span_precision", "span_recall", "span_f1", "per_percent", "text_retention", "mean_prompt_eval_count", "mean_eval_count", "mean_latency_ms", "notes"])
        writer.writeheader()
        writer.writerow({
            "benchmark": benchmark_name,
            "method": "Prompted LLM zero-shot de-identification",
            "split": split,
            "note_count": str(len(records)),
            "mention_count": str(total_mentions),
            "span_precision": f"{precision:.2f}",
            "span_recall": f"{recall:.2f}",
            "span_f1": f"{f1:.2f}",
            "per_percent": f"{per_percent:.1f}",
            "text_retention": f"{text_retention:.2f}",
            "mean_prompt_eval_count": f"{_mean([float(v) for v in prompt_eval_counts]):.1f}",
            "mean_eval_count": f"{_mean([float(v) for v in eval_counts]):.1f}",
            "mean_latency_ms": f"{_mean(latency_ms):.1f}",
            "notes": summary_notes,
        })

    with detail_output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(detail_rows[0].keys()))
        writer.writeheader()
        writer.writerows(detail_rows)

    run_finished_at = datetime.now(UTC)
    with runtime_manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["run_id", "benchmark", "method", "scope", "model_tag", "model_digest", "model_family", "model_parameter_size", "model_quantization", "model_format", "model_modified_at", "prompt_template", "note_count", "split", "mean_prompt_eval_count", "mean_eval_count", "mean_latency_ms", "hardware_summary", "os_runtime", "python_runtime", "run_started_at_utc", "run_finished_at_utc", "memory_usage_note", "ollama_url", "notes"])
        writer.writeheader()
        writer.writerow({
            "run_id": f"ai4privacy-ollama-zeroshot-{len(records)}",
            "benchmark": benchmark_name,
            "method": "Prompted LLM zero-shot de-identification",
            "scope": scope,
            "model_tag": model_metadata["model_name"],
            "model_digest": model_metadata["model_digest"],
            "model_family": model_metadata["model_family"],
            "model_parameter_size": model_metadata["model_parameter_size"],
            "model_quantization": model_metadata["model_quantization"],
            "model_format": model_metadata["model_format"],
            "model_modified_at": model_metadata["model_modified_at"],
            "prompt_template": PROMPT_TEMPLATE_PATH.name,
            "note_count": str(len(records)),
            "split": split,
            "mean_prompt_eval_count": f"{_mean([float(v) for v in prompt_eval_counts]):.1f}",
            "mean_eval_count": f"{_mean([float(v) for v in eval_counts]):.1f}",
            "mean_latency_ms": f"{_mean(latency_ms):.1f}",
            "hardware_summary": "Local workstation; same prototype host class used for public Ollama pilots.",
            "os_runtime": platform.platform(),
            "python_runtime": sys.version.replace("\n", " "),
            "run_started_at_utc": run_started_at.isoformat(),
            "run_finished_at_utc": run_finished_at.isoformat(),
            "memory_usage_note": "Memory telemetry not captured in the public local Ollama pilot.",
            "ollama_url": ollama_url,
            "notes": runtime_notes,
        })

    with run_log_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["benchmark", "method", "execution_status", "input_scope", "note_count", "split", "summary_output", "detail_output", "runtime_manifest", "command_template", "notes"])
        writer.writeheader()
        writer.writerow({
            "benchmark": benchmark_name,
            "method": "Prompted LLM zero-shot de-identification",
            "execution_status": "executed",
            "input_scope": input_scope,
            "note_count": str(len(records)),
            "split": split,
            "summary_output": summary_output_path.name,
            "detail_output": detail_output_path.name,
            "runtime_manifest": runtime_manifest_path.name,
            "command_template": f"python src/experiments/ai4privacy_ollama_zero_shot_baseline.py --input {input_path} --model {model}",
            "notes": run_log_notes,
        })

    return summary_output_path, detail_output_path, runtime_manifest_path, run_log_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local Ollama-backed zero-shot de-identification pilot on AI4Privacy records.")
    parser.add_argument("--input", type=Path, default=DEFAULT_EXPORT_PATH, help="Normalized AI4Privacy JSONL export")
    parser.add_argument("--model", default="llama3:latest", help="Ollama model tag")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama generate API endpoint")
    parser.add_argument("--max-records", type=int, help="Maximum records to evaluate")
    parser.add_argument("--output-tag", help="Optional suffix for output files")
    parser.add_argument("--benchmark-name", default=DEFAULT_BENCHMARK_NAME, help="Benchmark label recorded in outputs")
    parser.add_argument("--scope", default=DEFAULT_SCOPE, help="Runtime scope label recorded in outputs")
    parser.add_argument("--input-scope", default=DEFAULT_INPUT_SCOPE, help="Input scope label recorded in outputs")
    parser.add_argument("--summary-notes", default=DEFAULT_NOTES, help="Summary notes recorded in outputs")
    parser.add_argument("--runtime-notes", default=DEFAULT_RUNTIME_NOTES, help="Runtime notes recorded in outputs")
    parser.add_argument("--run-log-notes", default=DEFAULT_RUN_LOG_NOTES, help="Run-log notes recorded in outputs")
    args = parser.parse_args()

    outputs = run_zero_shot_pilot(
        args.input,
        args.model,
        args.ollama_url,
        args.max_records,
        output_tag=args.output_tag,
        benchmark_name=args.benchmark_name,
        scope=args.scope,
        input_scope=args.input_scope,
        summary_notes=args.summary_notes,
        runtime_notes=args.runtime_notes,
        run_log_notes=args.run_log_notes,
    )
    print("AI4Privacy zero-shot outputs written to:")
    for path in outputs:
        print(f" - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())#!/usr/bin/env python3
"""Run a local Ollama-backed zero-shot de-identification pilot on AI4Privacy records."""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import platform
import sys
import time
import urllib.request
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from build_ai4privacy_pii300k_export import DEFAULT_OUTPUT as DEFAULT_EXPORT_PATH


EXPERIMENTS_DIR = Path(__file__).resolve().parent
PROMPT_TEMPLATE_PATH = EXPERIMENTS_DIR / "ai4privacy_zero_shot_prompt_template.txt"
SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "ai4privacy_ollama_zero_shot_results.csv"
DETAIL_OUTPUT_PATH = EXPERIMENTS_DIR / "ai4privacy_ollama_zero_shot_document_metrics.csv"
RUNTIME_MANIFEST_PATH = EXPERIMENTS_DIR / "ai4privacy_ollama_zero_shot_runtime_manifest.csv"
RUN_LOG_PATH = EXPERIMENTS_DIR / "ai4privacy_ollama_zero_shot_run_log.csv"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_BENCHMARK_NAME = "AI4Privacy PII-Masking-300K (English)"
DEFAULT_SCOPE = "public multi-domain pii pilot"
DEFAULT_INPUT_SCOPE = "public AI4Privacy normalized text export"
DEFAULT_NOTES = "Executed local open-weight zero-shot pilot on a held-out public AI4Privacy English slice."
DEFAULT_RUNTIME_NOTES = "Executed on the public AI4Privacy PII-Masking-300K English export under a generic de-identification prompt."
DEFAULT_RUN_LOG_NOTES = "Executed local Ollama-backed pilot on a held-out AI4Privacy English slice."


def _load_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _build_prompt(text: str) -> str:
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.replace("{{NOTE_TEXT}}", text)


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    merged: list[list[int]] = [[spans[0][0], spans[0][1]]]
    for start, end in sorted(spans):
        current = merged[-1]
        if start <= current[1]:
            current[1] = max(current[1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _changed_spans(original_text: str, sanitized_text: str) -> list[tuple[int, int]]:
    matcher = difflib.SequenceMatcher(a=original_text, b=sanitized_text, autojunk=False)
    spans: list[tuple[int, int]] = []
    for tag, start_a, end_a, _start_b, _end_b in matcher.get_opcodes():
        if tag != "equal" and end_a > start_a:
            spans.append((start_a, end_a))
    return _merge_spans(spans)


def _char_coverage(spans: list[tuple[int, int]]) -> set[int]:
    covered: set[int] = set()
    for start, end in spans:
        covered.update(range(start, end))
    return covered


def _span_counts(predicted: list[tuple[int, int]], gold: list[tuple[int, int]]) -> tuple[int, int, int]:
    matched_gold: set[int] = set()
    true_positive = 0
    for pred in predicted:
        best_idx = -1
        best_overlap = 0
        for idx, gold_span in enumerate(gold):
            if idx in matched_gold:
                continue
            overlap = max(0, min(pred[1], gold_span[1]) - max(pred[0], gold_span[0]))
            if overlap > best_overlap:
                best_idx = idx
                best_overlap = overlap
        if best_idx != -1 and best_overlap > 0:
            matched_gold.add(best_idx)
            true_positive += 1
    return true_positive, max(0, len(predicted) - true_positive), max(0, len(gold) - true_positive)


def _ollama_generate(prompt: str, model: str, ollama_url: str) -> dict[str, Any]:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(ollama_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
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
    return {"model_name": model, "model_digest": "", "model_family": "", "model_parameter_size": "", "model_quantization": "", "model_format": "", "model_modified_at": ""}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _with_output_tag(path: Path, output_tag: str | None) -> Path:
    if not output_tag:
        return path
    return path.with_name(f"{path.stem}_{output_tag}{path.suffix}")


def run_zero_shot_pilot(
    input_path: Path,
    model: str,
    ollama_url: str,
    max_records: int | None,
    output_tag: str | None = None,
    benchmark_name: str = DEFAULT_BENCHMARK_NAME,
    scope: str = DEFAULT_SCOPE,
    input_scope: str = DEFAULT_INPUT_SCOPE,
    summary_notes: str = DEFAULT_NOTES,
    runtime_notes: str = DEFAULT_RUNTIME_NOTES,
    run_log_notes: str = DEFAULT_RUN_LOG_NOTES,
) -> tuple[Path, Path, Path, Path]:
    summary_output_path = _with_output_tag(SUMMARY_OUTPUT_PATH, output_tag)
    detail_output_path = _with_output_tag(DETAIL_OUTPUT_PATH, output_tag)
    runtime_manifest_path = _with_output_tag(RUNTIME_MANIFEST_PATH, output_tag)
    run_log_path = _with_output_tag(RUN_LOG_PATH, output_tag)
    records = _load_records(input_path)
    if max_records is not None:
        records = records[:max_records]
    if not records:
        raise ValueError("No AI4Privacy records were found.")

    detail_rows: list[dict[str, str]] = []
    prompt_eval_counts: list[int] = []
    eval_counts: list[int] = []
    latency_ms: list[float] = []
    total_tp = total_fp = total_fn = 0
    total_sensitive_chars = total_residual_sensitive_chars = 0
    total_non_sensitive_chars = total_preserved_non_sensitive_chars = 0
    total_mentions = 0
    run_started_at = datetime.now(UTC)
    model_metadata = _ollama_model_metadata(model, ollama_url)

    for record in records:
        text = str(record.get("text", ""))
        prompt = _build_prompt(text)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        started = time.perf_counter()
        response = _ollama_generate(prompt, model, ollama_url)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        sanitized_text = str(response.get("response", "")).strip() or text
        predicted_spans = _changed_spans(text, sanitized_text)
        gold_spans = [(int(span["start"]), int(span["end"])) for span in record.get("phi_spans", [])]
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

        detail_rows.append(
            {
                "note_id": str(record.get("note_id", "unknown")),
                "split": str(record.get("split", "unknown")),
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
    split = str(records[0].get("split", "unknown"))

    with summary_output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["benchmark", "method", "split", "note_count", "mention_count", "span_precision", "span_recall", "span_f1", "per_percent", "text_retention", "mean_prompt_eval_count", "mean_eval_count", "mean_latency_ms", "notes"])
        writer.writeheader()
        writer.writerow({
            "benchmark": benchmark_name,
            "method": "Prompted LLM zero-shot de-identification",
            "split": split,
            "note_count": str(len(records)),
            "mention_count": str(total_mentions),
            "span_precision": f"{precision:.2f}",
            "span_recall": f"{recall:.2f}",
            "span_f1": f"{f1:.2f}",
            "per_percent": f"{per_percent:.1f}",
            "text_retention": f"{text_retention:.2f}",
            "mean_prompt_eval_count": f"{_mean([float(v) for v in prompt_eval_counts]):.1f}",
            "mean_eval_count": f"{_mean([float(v) for v in eval_counts]):.1f}",
            "mean_latency_ms": f"{_mean(latency_ms):.1f}",
            "notes": summary_notes,
        })

    with detail_output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(detail_rows[0].keys()))
        writer.writeheader()
        writer.writerows(detail_rows)

    run_finished_at = datetime.now(UTC)
    with runtime_manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["run_id", "benchmark", "method", "scope", "model_tag", "model_digest", "model_family", "model_parameter_size", "model_quantization", "model_format", "model_modified_at", "prompt_template", "note_count", "split", "mean_prompt_eval_count", "mean_eval_count", "mean_latency_ms", "hardware_summary", "os_runtime", "python_runtime", "run_started_at_utc", "run_finished_at_utc", "memory_usage_note", "ollama_url", "notes"])
        writer.writeheader()
        writer.writerow({
            "run_id": f"ai4privacy-ollama-zeroshot-{len(records)}",
            "benchmark": benchmark_name,
            "method": "Prompted LLM zero-shot de-identification",
            "scope": scope,
            "model_tag": model_metadata["model_name"],
            "model_digest": model_metadata["model_digest"],
            "model_family": model_metadata["model_family"],
            "model_parameter_size": model_metadata["model_parameter_size"],
            "model_quantization": model_metadata["model_quantization"],
            "model_format": model_metadata["model_format"],
            "model_modified_at": model_metadata["model_modified_at"],
            "prompt_template": PROMPT_TEMPLATE_PATH.name,
            "note_count": str(len(records)),
            "split": split,
            "mean_prompt_eval_count": f"{_mean([float(v) for v in prompt_eval_counts]):.1f}",
            "mean_eval_count": f"{_mean([float(v) for v in eval_counts]):.1f}",
            "mean_latency_ms": f"{_mean(latency_ms):.1f}",
            "hardware_summary": "Local workstation; same prototype host class used for public Ollama pilots.",
            "os_runtime": platform.platform(),
            "python_runtime": sys.version.replace("\n", " "),
            "run_started_at_utc": run_started_at.isoformat(),
            "run_finished_at_utc": run_finished_at.isoformat(),
            "memory_usage_note": "Memory telemetry not captured in the public local Ollama pilot.",
            "ollama_url": ollama_url,
            "notes": runtime_notes,
        })

    with run_log_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["benchmark", "method", "execution_status", "input_scope", "note_count", "split", "summary_output", "detail_output", "runtime_manifest", "command_template", "notes"])
        writer.writeheader()
        writer.writerow({
            "benchmark": benchmark_name,
            "method": "Prompted LLM zero-shot de-identification",
            "execution_status": "executed",
            "input_scope": input_scope,
            "note_count": str(len(records)),
            "split": split,
            "summary_output": summary_output_path.name,
            "detail_output": detail_output_path.name,
            "runtime_manifest": runtime_manifest_path.name,
            "command_template": f"python src/experiments/ai4privacy_ollama_zero_shot_baseline.py --input {input_path} --model {model}",
            "notes": run_log_notes,
        })

    return summary_output_path, detail_output_path, runtime_manifest_path, run_log_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local Ollama-backed zero-shot de-identification pilot on AI4Privacy records.")
    parser.add_argument("--input", type=Path, default=DEFAULT_EXPORT_PATH, help="Normalized AI4Privacy JSONL export")
    parser.add_argument("--model", default="llama3:latest", help="Ollama model tag")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama generate API endpoint")
    parser.add_argument("--max-records", type=int, help="Maximum records to evaluate")
    parser.add_argument("--output-tag", help="Optional suffix for output files")
    parser.add_argument("--benchmark-name", default=DEFAULT_BENCHMARK_NAME, help="Benchmark label recorded in outputs")
    parser.add_argument("--scope", default=DEFAULT_SCOPE, help="Runtime scope label recorded in outputs")
    parser.add_argument("--input-scope", default=DEFAULT_INPUT_SCOPE, help="Input scope label recorded in outputs")
    parser.add_argument("--summary-notes", default=DEFAULT_NOTES, help="Summary notes recorded in outputs")
    parser.add_argument("--runtime-notes", default=DEFAULT_RUNTIME_NOTES, help="Runtime notes recorded in outputs")
    parser.add_argument("--run-log-notes", default=DEFAULT_RUN_LOG_NOTES, help="Run-log notes recorded in outputs")
    args = parser.parse_args()

    outputs = run_zero_shot_pilot(
        args.input,
        args.model,
        args.ollama_url,
        args.max_records,
        output_tag=args.output_tag,
        benchmark_name=args.benchmark_name,
        scope=args.scope,
        input_scope=args.input_scope,
        summary_notes=args.summary_notes,
        runtime_notes=args.runtime_notes,
        run_log_notes=args.run_log_notes,
    )
    print("AI4Privacy zero-shot outputs written to:")
    for path in outputs:
        print(f" - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())