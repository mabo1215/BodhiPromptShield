#!/usr/bin/env python3
"""Run the reconstructed CPPB text-only utility pilot through Ollama.

This is a new, explicitly reconstructed protocol.  It does not overwrite
legacy CPPB artifacts and must not be reported as the historical CPPB rerun.

The pilot selects the 48 text-only prompts in the released ``test`` split and
generates four matched conditions with one named model:

* raw prompt;
* enterprise-style ``[REDACTED]``;
* typed placeholder;
* proposed balanced boundary-aware abstraction.

The generated blind-review file contains only randomized A/B/C/D condition
codes.  The method key is written separately for the analyst and must not be
distributed to raters.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import random
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from datetime import UTC
except ImportError:  # Python 3.10 compatibility
    from datetime import timezone

    UTC = timezone.utc


EXPERIMENTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENTS_DIR.parents[1]
DATA_DIR = REPO_ROOT / "data"
ANNOTATIONS_PATH = DATA_DIR / "cppb_full_annotations.jsonl"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "llama3.2:latest"
DEFAULT_TAG = "vgpu3090"
DEFAULT_SEED = 20260825
CONDITIONS = ["raw", "enterprise_redaction", "typed_placeholder", "proposed_balanced"]
CONDITION_CODES = ["A", "B", "C", "D"]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _with_tag(path: Path, tag: str) -> Path:
    return path.with_name(f"{path.stem}_{tag}{path.suffix}")


def _replacement(row: dict[str, Any], condition: str) -> str:
    if condition == "raw":
        return str(row["sensitive_spans"][0]["text"])
    if condition == "enterprise_redaction":
        return "[REDACTED]"
    code = str(row["span_category_code"])
    if condition == "typed_placeholder":
        return f"<{code}_1>"
    if condition == "proposed_balanced":
        if row["subset"] == "Essential-privacy":
            category = str(row["privacy_category"]).replace("_", " ")
            return f"a protected {category} available at the authorized execution boundary"
        return f"<{code}_1>"
    raise ValueError(f"Unknown condition: {condition}")


def _condition_prompt(row: dict[str, Any], condition: str) -> tuple[str, bool]:
    start = int(row["span_start"])
    end = int(row["span_end"])
    source = str(row["prompt_text"])
    replacement = _replacement(row, condition)
    prompt = source[:start] + replacement + source[end:]
    raw_value = str(row["sensitive_spans"][0]["text"])
    hidden = condition != "raw" and raw_value not in prompt
    if condition != "raw" and not hidden:
        raise AssertionError(f"Sensitive value survived {condition} for {row['prompt_id']}")
    return prompt, hidden


def _ollama_json(url: str, payload: dict[str, Any], timeout: int = 900) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _model_metadata(model: str, ollama_url: str) -> dict[str, str]:
    tags_url = ollama_url.rsplit("/api/", 1)[0] + "/api/tags"
    request = urllib.request.Request(tags_url, method="GET")
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    for item in payload.get("models", []):
        if str(item.get("name")) == model or str(item.get("model")) == model:
            details = item.get("details", {}) if isinstance(item.get("details"), dict) else {}
            return {
                "model_name": str(item.get("name", model)),
                "model_digest": str(item.get("digest", "")),
                "model_family": str(details.get("family", "")),
                "model_parameter_size": str(details.get("parameter_size", "")),
                "model_quantization": str(details.get("quantization_level", "")),
                "model_format": str(details.get("format", "")),
                "model_modified_at": str(item.get("modified_at", "")),
            }
    raise RuntimeError(f"Model is not installed in Ollama: {model}")


def _hardware_summary() -> str:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,memory.used,utilization.gpu",
                "--format=csv,noheader",
            ],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=30,
        ).strip()
        return output
    except (FileNotFoundError, subprocess.SubprocessError):
        return "nvidia-smi unavailable"


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_blind_instructions(path: Path) -> None:
    path.write_text(
        """# CPPB reconstructed utility pilot: blind scoring instructions

This file accompanies the blind A/B/C/D review CSV. Do not seek or use the
separate method-key CSV while scoring. Each row is one model output for one
reconstructed CPPB test prompt under a randomized condition code.

Score only the output quality, not privacy detection quality:

- `task_success_score`: `1` if the requested action/result is completed, else `0`.
- `faithfulness_score`: `0` wrong/unsupported, `1` partially faithful, `2` complete and faithful.
- `required_fields_score`: `1` if the required output components listed in the row are present, else `0`.
- `comments`: short reason for a zero or partial score.

Do not manually score exact raw-value exposure. That is checked automatically
from the annotated prompt span. Do not infer the method from wording or output
style. Keep the condition code and method identity blinded until all ratings are
complete.

The protocol is a reconstructed text-only utility pilot, not recovery of the
historical CPPB raw benchmark. OCR rows are not included in this file.
""",
        encoding="utf-8",
    )


def run(
    model: str,
    ollama_url: str,
    output_tag: str,
    seed: int,
    max_prompts: int | None,
) -> None:
    rows = [
        row
        for row in _read_jsonl(ANNOTATIONS_PATH)
        if row.get("split") == "test" and row.get("modality") == "Text-only"
    ]
    if max_prompts is not None:
        rows = rows[:max_prompts]
    if len(rows) != 48:
        raise ValueError(f"Expected 48 text-only reconstructed test prompts, got {len(rows)}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    model_info = _model_metadata(model, ollama_url)
    run_started = datetime.now(UTC)
    rng = random.Random(seed)
    prompt_assignments: dict[str, dict[str, str]] = {}
    for row in rows:
        shuffled = list(CONDITION_CODES)
        rng.shuffle(shuffled)
        prompt_assignments[row["prompt_id"]] = dict(zip(CONDITIONS, shuffled))

    detail_rows: list[dict[str, Any]] = []
    blind_rows: list[dict[str, Any]] = []
    method_key_rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    total = len(rows) * len(CONDITIONS)
    done = 0

    for row in rows:
        for condition in CONDITIONS:
            condition_code = prompt_assignments[row["prompt_id"]][condition]
            prompt, hidden = _condition_prompt(row, condition)
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "30m",
                "options": {
                    "temperature": 0.0,
                    "top_p": 1.0,
                    "num_predict": 256,
                    "seed": seed,
                },
            }
            request_started = time.perf_counter()
            response = _ollama_json(ollama_url, payload)
            latency_ms = (time.perf_counter() - request_started) * 1000.0
            output = str(response.get("response", "")).strip()
            if not output:
                raise RuntimeError(f"Empty Ollama response for {row['prompt_id']} {condition}")
            review_item_id = f"R{len(detail_rows) + 1:04d}"
            detail_rows.append(
                {
                    "review_item_id": review_item_id,
                    "prompt_id": row["prompt_id"],
                    "condition": condition,
                    "condition_code": condition_code,
                    "prompt_hash": _sha256_text(prompt),
                    "prompt_text": prompt,
                    "sensitive_value_hidden": str(hidden).lower(),
                    "model_output": output,
                    "response_done": str(response.get("done", "")),
                    "prompt_eval_count": str(response.get("prompt_eval_count", 0) or 0),
                    "eval_count": str(response.get("eval_count", 0) or 0),
                    "latency_ms": f"{latency_ms:.1f}",
                }
            )
            blind_rows.append(
                {
                    "review_item_id": review_item_id,
                    "prompt_id": row["prompt_id"],
                    "condition_code": condition_code,
                    "prompt_text": row["prompt_text"],
                    "task_objective": row["task_objective"],
                    "task_success_criteria": row["task_success_criteria"],
                    "required_output_components": row["required_output_components"],
                    "model_output": output,
                    "task_success_score": "",
                    "faithfulness_score": "",
                    "required_fields_score": "",
                    "rater_id": "",
                    "comments": "",
                }
            )
            method_key_rows.append(
                {
                    "review_item_id": review_item_id,
                    "prompt_id": row["prompt_id"],
                    "condition_code": condition_code,
                    "condition": condition,
                }
            )
            done += 1
            if done == 1 or done == total or done % 8 == 0:
                elapsed = time.perf_counter() - started
                print(f"Generated {done}/{total} outputs ({elapsed:.1f}s)", flush=True)

    run_finished = datetime.now(UTC)
    tag = output_tag
    detail_path = _with_tag(DATA_DIR / "cppb_reconstructed_utility_outputs.csv", tag)
    jsonl_path = _with_tag(DATA_DIR / "cppb_reconstructed_utility_outputs.jsonl", tag)
    blind_path = _with_tag(DATA_DIR / "cppb_reconstructed_blind_review.csv", tag)
    key_path = _with_tag(DATA_DIR / "cppb_reconstructed_blind_method_key.csv", tag)
    runtime_path = _with_tag(DATA_DIR / "cppb_reconstructed_utility_runtime_manifest.csv", tag)
    run_log_path = _with_tag(DATA_DIR / "cppb_reconstructed_utility_run_log.csv", tag)
    instructions_path = DATA_DIR / "cppb_reconstructed_blind_review_instructions.md"

    detail_fields = list(detail_rows[0].keys())
    _write_csv(detail_path, detail_rows, detail_fields)
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in detail_rows:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    _write_csv(
        blind_path,
        blind_rows,
        [
            "review_item_id",
            "prompt_id",
            "condition_code",
            "prompt_text",
            "task_objective",
            "task_success_criteria",
            "required_output_components",
            "model_output",
            "task_success_score",
            "faithfulness_score",
            "required_fields_score",
            "rater_id",
            "comments",
        ],
    )
    _write_csv(key_path, method_key_rows, list(method_key_rows[0].keys()))
    _write_blind_instructions(instructions_path)

    runtime_rows = [
        {"field": "run_id", "value": f"cppb-reconstructed-utility-{tag}"},
        {"field": "benchmark", "value": "CPPB reconstructed annotation surface"},
        {"field": "scope", "value": "test split, 48 text-only prompts, 4 matched conditions"},
        {"field": "historical_raw_prompt_recovery", "value": "false"},
        {"field": "model_tag", "value": model_info["model_name"]},
        {"field": "model_digest", "value": model_info["model_digest"]},
        {"field": "model_family", "value": model_info["model_family"]},
        {"field": "model_parameter_size", "value": model_info["model_parameter_size"]},
        {"field": "model_quantization", "value": model_info["model_quantization"]},
        {"field": "model_format", "value": model_info["model_format"]},
        {"field": "ollama_url", "value": ollama_url},
        {"field": "temperature", "value": "0.0"},
        {"field": "top_p", "value": "1.0"},
        {"field": "num_predict", "value": "256"},
        {"field": "seed", "value": str(seed)},
        {"field": "prompt_count", "value": str(len(rows))},
        {"field": "condition_count", "value": str(len(CONDITIONS))},
        {"field": "output_count", "value": str(len(detail_rows))},
        {"field": "annotation_sha256", "value": _sha256_text(ANNOTATIONS_PATH.read_text(encoding="utf-8"))},
        {"field": "hardware_summary", "value": _hardware_summary()},
        {"field": "os_runtime", "value": platform.platform()},
        {"field": "python_runtime", "value": sys.version.replace("\n", " ")},
        {"field": "run_started_at_utc", "value": run_started.isoformat()},
        {"field": "run_finished_at_utc", "value": run_finished.isoformat()},
        {"field": "detail_output", "value": detail_path.name},
        {"field": "blind_review_output", "value": blind_path.name},
        {"field": "method_key_output", "value": key_path.name},
        {"field": "notes", "value": "New reconstructed protocol; do not merge into historical CPPB score artifacts."},
    ]
    _write_csv(runtime_path, runtime_rows, ["field", "value"])
    _write_csv(
        run_log_path,
        [
            {
                "benchmark": "CPPB reconstructed annotation surface",
                "protocol": "Four matched prompt conditions through one named Ollama model",
                "execution_status": "executed",
                "split": "test",
                "prompt_count": str(len(rows)),
                "condition_count": str(len(CONDITIONS)),
                "output_count": str(len(detail_rows)),
                "model_tag": model_info["model_name"],
                "model_digest": model_info["model_digest"],
                "detail_output": detail_path.name,
                "blind_review_output": blind_path.name,
                "runtime_manifest": runtime_path.name,
                "method_key_output": key_path.name,
                "notes": "Distribute blind review output and instructions only; retain method key for analysis.",
            }
        ],
        [
            "benchmark",
            "protocol",
            "execution_status",
            "split",
            "prompt_count",
            "condition_count",
            "output_count",
            "model_tag",
            "model_digest",
            "detail_output",
            "blind_review_output",
            "runtime_manifest",
            "method_key_output",
            "notes",
        ],
    )
    print(f"Wrote detail outputs to {detail_path}")
    print(f"Wrote blind review table to {blind_path}")
    print(f"Wrote method key to {key_path}")
    print(f"Wrote runtime manifest to {runtime_path}")
    print(f"Wrote run log to {run_log_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--output-tag", default=DEFAULT_TAG)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-prompts", type=int, default=None)
    args = parser.parse_args()
    run(args.model, args.ollama_url, args.output_tag, args.seed, args.max_prompts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
