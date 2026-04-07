#!/usr/bin/env python3
"""Run repeat local Ollama zero-shot pilots and summarize stability.

This script reuses the released TAB and synthetic i2b2-Synthea zero-shot pilot
executors, snapshots each repeat's artifacts, and writes aggregate stability
summaries that can be cited as bounded repeat-run evidence.
"""
from __future__ import annotations

import argparse
import csv
import math
import shutil
import statistics
from pathlib import Path

from i2b2_ollama_zero_shot_baseline import DETAIL_OUTPUT_PATH as I2B2_DETAIL_OUTPUT_PATH
from i2b2_ollama_zero_shot_baseline import RUN_LOG_PATH as I2B2_RUN_LOG_PATH
from i2b2_ollama_zero_shot_baseline import RUNTIME_MANIFEST_PATH as I2B2_RUNTIME_MANIFEST_PATH
from i2b2_ollama_zero_shot_baseline import SUMMARY_OUTPUT_PATH as I2B2_SUMMARY_OUTPUT_PATH
from i2b2_ollama_zero_shot_baseline import _with_output_tag as i2b2_with_output_tag
from i2b2_ollama_zero_shot_baseline import run_zero_shot_pilot as run_i2b2_zero_shot_pilot
from tab_ollama_zero_shot_baseline import DETAIL_OUTPUT_PATH as TAB_DETAIL_OUTPUT_PATH
from tab_ollama_zero_shot_baseline import RUN_LOG_PATH as TAB_RUN_LOG_PATH
from tab_ollama_zero_shot_baseline import RUNTIME_MANIFEST_PATH as TAB_RUNTIME_MANIFEST_PATH
from tab_ollama_zero_shot_baseline import SUMMARY_OUTPUT_PATH as TAB_SUMMARY_OUTPUT_PATH
from tab_ollama_zero_shot_baseline import run_zero_shot_pilot as run_tab_zero_shot_pilot


EXPERIMENTS_DIR = Path(__file__).resolve().parent

METRIC_FIELDS = [
    "span_precision",
    "span_recall",
    "span_f1",
    "per_percent",
    "text_retention",
    "mean_prompt_eval_count",
    "mean_eval_count",
    "mean_latency_ms",
]


def _read_single_row_csv(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one data row in {path}, found {len(rows)}")
    return rows[0]


def _copy_snapshot(path: Path, snapshot_dir: Path, repeat_index: int) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{path.stem}_run{repeat_index:02d}{path.suffix}"
    shutil.copy2(path, snapshot_path)
    return snapshot_path


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def _ci95(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return 1.96 * _std(values) / math.sqrt(len(values))


def run_tab_stability(
    input_dir: Path,
    split: str,
    max_documents: int,
    model: str,
    ollama_url: str,
    repeats: int,
    include_current: bool,
) -> tuple[Path, Path]:
    runs_output = EXPERIMENTS_DIR / "tab_ollama_zero_shot_stability_runs.csv"
    summary_output = EXPERIMENTS_DIR / "tab_ollama_zero_shot_stability_summary.csv"
    snapshot_dir = EXPERIMENTS_DIR / "tab_ollama_zero_shot_stability_runs"
    run_rows: list[dict[str, str]] = []

    if include_current and TAB_SUMMARY_OUTPUT_PATH.exists():
        summary_row = _read_single_row_csv(TAB_SUMMARY_OUTPUT_PATH)
        summary_snapshot = _copy_snapshot(TAB_SUMMARY_OUTPUT_PATH, snapshot_dir, 0)
        detail_snapshot = _copy_snapshot(TAB_DETAIL_OUTPUT_PATH, snapshot_dir, 0)
        runtime_snapshot = _copy_snapshot(TAB_RUNTIME_MANIFEST_PATH, snapshot_dir, 0)
        run_log_snapshot = _copy_snapshot(TAB_RUN_LOG_PATH, snapshot_dir, 0)
        run_rows.append(
            {
                "benchmark": summary_row["benchmark"],
                "split": summary_row["split"],
                "repeat_index": "0",
                "unit_label": "document_count",
                "unit_count": summary_row["document_count"],
                "mention_count": summary_row["mention_count"],
                **{field: summary_row[field] for field in METRIC_FIELDS},
                "summary_snapshot": summary_snapshot.name,
                "detail_snapshot": detail_snapshot.name,
                "runtime_manifest_snapshot": runtime_snapshot.name,
                "run_log_snapshot": run_log_snapshot.name,
            }
        )

    for repeat_index in range(1, repeats + 1):
        run_tab_zero_shot_pilot(input_dir, split, max_documents, model, ollama_url)
        summary_row = _read_single_row_csv(TAB_SUMMARY_OUTPUT_PATH)
        summary_snapshot = _copy_snapshot(TAB_SUMMARY_OUTPUT_PATH, snapshot_dir, repeat_index)
        detail_snapshot = _copy_snapshot(TAB_DETAIL_OUTPUT_PATH, snapshot_dir, repeat_index)
        runtime_snapshot = _copy_snapshot(TAB_RUNTIME_MANIFEST_PATH, snapshot_dir, repeat_index)
        run_log_snapshot = _copy_snapshot(TAB_RUN_LOG_PATH, snapshot_dir, repeat_index)
        run_rows.append(
            {
                "benchmark": summary_row["benchmark"],
                "split": summary_row["split"],
                "repeat_index": str(repeat_index),
                "unit_label": "document_count",
                "unit_count": summary_row["document_count"],
                "mention_count": summary_row["mention_count"],
                **{field: summary_row[field] for field in METRIC_FIELDS},
                "summary_snapshot": summary_snapshot.name,
                "detail_snapshot": detail_snapshot.name,
                "runtime_manifest_snapshot": runtime_snapshot.name,
                "run_log_snapshot": run_log_snapshot.name,
            }
        )

    metric_values = {field: [float(row[field]) for row in run_rows] for field in METRIC_FIELDS}
    summary_row = {
        "benchmark": run_rows[0]["benchmark"],
        "split": run_rows[0]["split"],
        "repeat_count": str(len(run_rows)),
        "unit_label": "document_count",
        "unit_count": run_rows[0]["unit_count"],
        "mention_count": run_rows[0]["mention_count"],
    }
    for field in METRIC_FIELDS:
        summary_row[f"{field}_mean"] = f"{_mean(metric_values[field]):.4f}"
        summary_row[f"{field}_std"] = f"{_std(metric_values[field]):.4f}"
        summary_row[f"{field}_ci95"] = f"{_ci95(metric_values[field]):.4f}"
    summary_row["notes"] = (
        "Repeat-run local Ollama stability summary for the fixed TAB zero-shot prompt surface."
    )

    with runs_output.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(run_rows[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(run_rows)

    with summary_output.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(summary_row.keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(summary_row)

    return runs_output, summary_output


def run_i2b2_stability(
    input_path: Path,
    model: str,
    ollama_url: str,
    max_notes: int | None,
    repeats: int,
    include_current: bool,
    output_tag: str | None,
    benchmark_name: str,
    scope: str,
    input_scope: str,
    summary_notes: str,
    runtime_notes: str,
    run_log_notes: str,
) -> tuple[Path, Path]:
    runs_output = i2b2_with_output_tag(EXPERIMENTS_DIR / "i2b2_ollama_zero_shot_stability_runs.csv", output_tag)
    summary_output = i2b2_with_output_tag(EXPERIMENTS_DIR / "i2b2_ollama_zero_shot_stability_summary.csv", output_tag)
    snapshot_dir_name = "i2b2_ollama_zero_shot_stability_runs"
    if output_tag:
        snapshot_dir_name += f"_{output_tag.replace(' ', '_')}"
    snapshot_dir = EXPERIMENTS_DIR / snapshot_dir_name
    run_rows: list[dict[str, str]] = []
    summary_source_path = i2b2_with_output_tag(I2B2_SUMMARY_OUTPUT_PATH, output_tag)
    detail_source_path = i2b2_with_output_tag(I2B2_DETAIL_OUTPUT_PATH, output_tag)
    runtime_source_path = i2b2_with_output_tag(I2B2_RUNTIME_MANIFEST_PATH, output_tag)
    run_log_source_path = i2b2_with_output_tag(I2B2_RUN_LOG_PATH, output_tag)

    if include_current and summary_source_path.exists():
        summary_row = _read_single_row_csv(summary_source_path)
        summary_snapshot = _copy_snapshot(summary_source_path, snapshot_dir, 0)
        detail_snapshot = _copy_snapshot(detail_source_path, snapshot_dir, 0)
        runtime_snapshot = _copy_snapshot(runtime_source_path, snapshot_dir, 0)
        run_log_snapshot = _copy_snapshot(run_log_source_path, snapshot_dir, 0)
        run_rows.append(
            {
                "benchmark": summary_row["benchmark"],
                "split": summary_row["split"],
                "repeat_index": "0",
                "unit_label": "note_count",
                "unit_count": summary_row["note_count"],
                "mention_count": summary_row["mention_count"],
                **{field: summary_row[field] for field in METRIC_FIELDS},
                "summary_snapshot": summary_snapshot.name,
                "detail_snapshot": detail_snapshot.name,
                "runtime_manifest_snapshot": runtime_snapshot.name,
                "run_log_snapshot": run_log_snapshot.name,
            }
        )

    for repeat_index in range(1, repeats + 1):
        run_i2b2_zero_shot_pilot(
            input_path,
            model,
            ollama_url,
            max_notes,
            output_tag=output_tag,
            benchmark_name=benchmark_name,
            scope=scope,
            input_scope=input_scope,
            summary_notes=summary_notes,
            runtime_notes=runtime_notes,
            run_log_notes=run_log_notes,
        )
        summary_row = _read_single_row_csv(summary_source_path)
        summary_snapshot = _copy_snapshot(summary_source_path, snapshot_dir, repeat_index)
        detail_snapshot = _copy_snapshot(detail_source_path, snapshot_dir, repeat_index)
        runtime_snapshot = _copy_snapshot(runtime_source_path, snapshot_dir, repeat_index)
        run_log_snapshot = _copy_snapshot(run_log_source_path, snapshot_dir, repeat_index)
        run_rows.append(
            {
                "benchmark": summary_row["benchmark"],
                "split": summary_row["split"],
                "repeat_index": str(repeat_index),
                "unit_label": "note_count",
                "unit_count": summary_row["note_count"],
                "mention_count": summary_row["mention_count"],
                **{field: summary_row[field] for field in METRIC_FIELDS},
                "summary_snapshot": summary_snapshot.name,
                "detail_snapshot": detail_snapshot.name,
                "runtime_manifest_snapshot": runtime_snapshot.name,
                "run_log_snapshot": run_log_snapshot.name,
            }
        )

    metric_values = {field: [float(row[field]) for row in run_rows] for field in METRIC_FIELDS}
    summary_row = {
        "benchmark": run_rows[0]["benchmark"],
        "split": run_rows[0]["split"],
        "repeat_count": str(len(run_rows)),
        "unit_label": "note_count",
        "unit_count": run_rows[0]["unit_count"],
        "mention_count": run_rows[0]["mention_count"],
    }
    for field in METRIC_FIELDS:
        summary_row[f"{field}_mean"] = f"{_mean(metric_values[field]):.4f}"
        summary_row[f"{field}_std"] = f"{_std(metric_values[field]):.4f}"
        summary_row[f"{field}_ci95"] = f"{_ci95(metric_values[field]):.4f}"
    summary_row["notes"] = f"Repeat-run local Ollama stability summary for the fixed {benchmark_name} zero-shot prompt surface."

    with runs_output.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(run_rows[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(run_rows)

    with summary_output.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(summary_row.keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(summary_row)

    return runs_output, summary_output


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeat local Ollama zero-shot pilots and summarize stability.")
    parser.add_argument("--benchmark", choices=["tab", "synthetic-i2b2"], required=True)
    parser.add_argument("--repeats", type=int, default=3, help="Number of repeated runs to execute")
    parser.add_argument("--model", default="llama3:latest", help="Ollama model tag")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434/api/generate", help="Ollama generate API endpoint")
    parser.add_argument("--input-dir", type=Path, default=EXPERIMENTS_DIR / "external_data" / "tab", help="TAB input directory")
    parser.add_argument("--split", default="dev", choices=["train", "dev", "test"], help="TAB split")
    parser.add_argument("--max-documents", type=int, default=32, help="Maximum TAB documents")
    parser.add_argument("--input", type=Path, default=EXPERIMENTS_DIR / "i2b2_synthea_synthetic_export.jsonl", help="Synthetic i2b2 export JSONL")
    parser.add_argument("--max-notes", type=int, help="Maximum synthetic notes")
    parser.add_argument("--include-current", action="store_true", help="Reuse the current canonical pilot artifacts as the first observation")
    parser.add_argument("--output-tag", help="Optional suffix used for tagged i2b2-like benchmark outputs")
    parser.add_argument("--benchmark-name", default="Synthetic i2b2-Synthea", help="Benchmark label recorded in i2b2-like outputs")
    parser.add_argument("--scope", default="public synthetic clinical pilot", help="Runtime scope label recorded in i2b2-like outputs")
    parser.add_argument("--input-scope", default="public synthetic clinical note export", help="Input scope label recorded in i2b2-like outputs")
    parser.add_argument("--summary-notes", default="Executed local open-weight zero-shot pilot on a synthetic i2b2-compatible export built from the public Synthea sample.", help="Summary notes passed to the i2b2-like zero-shot runner")
    parser.add_argument("--runtime-notes", default="Executed on a synthetic note export built from the public i2b2-Synthea sample tables rather than licensed clinical notes.", help="Runtime notes passed to the i2b2-like zero-shot runner")
    parser.add_argument("--run-log-notes", default="Executed local Ollama-backed pilot on a synthetic i2b2-compatible export.", help="Run-log notes passed to the i2b2-like zero-shot runner")
    args = parser.parse_args()

    if args.benchmark == "tab":
        runs_output, summary_output = run_tab_stability(
            input_dir=args.input_dir,
            split=args.split,
            max_documents=args.max_documents,
            model=args.model,
            ollama_url=args.ollama_url,
            repeats=args.repeats,
            include_current=args.include_current,
        )
    else:
        runs_output, summary_output = run_i2b2_stability(
            input_path=args.input,
            model=args.model,
            ollama_url=args.ollama_url,
            max_notes=args.max_notes,
            repeats=args.repeats,
            include_current=args.include_current,
            output_tag=args.output_tag,
            benchmark_name=args.benchmark_name,
            scope=args.scope,
            input_scope=args.input_scope,
            summary_notes=args.summary_notes,
            runtime_notes=args.runtime_notes,
            run_log_notes=args.run_log_notes,
        )

    print(f"Zero-shot stability run records written to {runs_output}")
    print(f"Zero-shot stability summary written to {summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())