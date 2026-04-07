#!/usr/bin/env python3
"""Run generic matched baselines on the public AI4Privacy English transfer slice."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "ai4privacy_transfer_results.csv"
DETAIL_OUTPUT_PATH = EXPERIMENTS_DIR / "ai4privacy_transfer_document_metrics.csv"
EXECUTION_MANIFEST_PATH = EXPERIMENTS_DIR / "ai4privacy_transfer_execution_manifest.csv"
RUN_LOG_PATH = EXPERIMENTS_DIR / "ai4privacy_transfer_run_log.csv"
DEFAULT_BENCHMARK_NAME = "AI4Privacy PII-Masking-300K (English)"
DEFAULT_INPUT_PATH = EXPERIMENTS_DIR / "ai4privacy_pii300k_english_export.jsonl"


METHOD_SPECS = [
    {"name": "Raw prompt", "family": "No protection", "status": "executed", "notes": "No sanitization is applied before evaluation."},
    {"name": "Regex-only", "family": "Pattern baseline", "status": "executed", "notes": "Structured identifier patterns only."},
    {"name": "NER-only masking", "family": "Entity baseline", "status": "executed", "notes": "Capitalization, title, and location-shape heuristics only."},
    {"name": "Presidio-class (regex-focused heuristic)", "family": "Industrial de-identification", "status": "executed", "notes": "Released approximation of a structured recognizer stack on a public multi-domain PII benchmark."},
    {"name": "Presidio-class (NER fallback heuristic)", "family": "Industrial de-identification", "status": "executed", "notes": "Released approximation of a structured-plus-NER stack on a public multi-domain PII benchmark."},
    {"name": "Hybrid rule+context de-identification", "family": "Hybrid heuristic de-identification", "status": "executed", "notes": "Released hybrid heuristic using structured, entity, and context cues on a public multi-domain PII benchmark."},
    {"name": "BodhiPromptShield (released heuristic mediator)", "family": "Policy-aware mediation", "status": "executed", "notes": "Released lightweight policy-aware mediator under the public multi-domain wrapper."},
]


EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d[\d()\- ]{6,}\d)\b")
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
TIME_PATTERN = re.compile(r"\b\d{1,2}:\d{2}(?:\s?[AaPp][Mm])?\b|\b(?:quarter|half)\s+past\s+\d{1,2}\b")
DATE_PATTERN = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")
SOCIAL_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PASSPORT_PATTERN = re.compile(r"\b[A-Z]{1,3}\d{5,10}\b")
POSTCODE_PATTERN = re.compile(r"\b\d{4,6}(?:-\d{3,4})?\b")
USERNAME_PATTERN = re.compile(r"\b[a-z][a-z0-9._-]{5,}\b")
ADDRESS_PATTERN = re.compile(r"\b\d{1,5}\s+[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){0,3}\s+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Court|Ct)\b")
TITLE_PATTERN = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Professor|Officer|Director|Agent)\.?\s+[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){0,2}")
CAPITALIZED_SEQUENCE_PATTERN = re.compile(r"\b[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){1,2}")
LOCATION_CONTEXT_PATTERN = re.compile(r"\b(?:in|at|from|near|to)\s+[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){0,2}", re.IGNORECASE)
ACCOUNT_CONTEXT_PATTERN = re.compile(r"\b(?:username|user|account|passport|license|id|password|postcode|zip|ssn|social security)[:#\s-]*[A-Za-z0-9._\-]{2,}\b", re.IGNORECASE)


def _with_output_tag(path: Path, output_tag: str | None) -> Path:
    if not output_tag:
        return path
    return path.with_name(f"{path.stem}_{output_tag}{path.suffix}")


def _load_records(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


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


def _regex_spans(text: str) -> list[tuple[int, int]]:
    patterns = [
        EMAIL_PATTERN,
        PHONE_PATTERN,
        IP_PATTERN,
        TIME_PATTERN,
        DATE_PATTERN,
        SOCIAL_PATTERN,
        PASSPORT_PATTERN,
        POSTCODE_PATTERN,
        ADDRESS_PATTERN,
        ACCOUNT_CONTEXT_PATTERN,
    ]
    spans: list[tuple[int, int]] = []
    for pattern in patterns:
        spans.extend((match.start(), match.end()) for match in pattern.finditer(text))
    return spans


def _ner_like_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    spans.extend((match.start(), match.end()) for match in TITLE_PATTERN.finditer(text))
    for match in CAPITALIZED_SEQUENCE_PATTERN.finditer(text):
        phrase = match.group(0)
        if phrase.split()[0] in {"The", "This", "That", "Subject", "Group", "Good"}:
            continue
        spans.append((match.start(), match.end()))
    spans.extend((match.start(), match.end()) for match in LOCATION_CONTEXT_PATTERN.finditer(text))
    return spans


def _presidio_regex_spans(text: str) -> list[tuple[int, int]]:
    return _merge_spans(_regex_spans(text) + [(match.start(), match.end()) for match in TITLE_PATTERN.finditer(text)] + [(match.start(), match.end()) for match in USERNAME_PATTERN.finditer(text)])


def _presidio_ner_spans(text: str) -> list[tuple[int, int]]:
    return _merge_spans(_presidio_regex_spans(text) + _ner_like_spans(text))


def _hybrid_spans(text: str) -> list[tuple[int, int]]:
    return _merge_spans(_presidio_ner_spans(text) + [(match.start(), match.end()) for match in ACCOUNT_CONTEXT_PATTERN.finditer(text)])


def _policy_aware_spans(text: str) -> list[tuple[int, int]]:
    return _merge_spans(_hybrid_spans(text) + [(match.start(), match.end()) for match in LOCATION_CONTEXT_PATTERN.finditer(text)])


def _predict_spans(method: str, text: str) -> list[tuple[int, int]]:
    if method == "Raw prompt":
        return []
    if method == "Regex-only":
        return _merge_spans(_regex_spans(text))
    if method == "NER-only masking":
        return _merge_spans(_ner_like_spans(text))
    if method == "Presidio-class (regex-focused heuristic)":
        return _presidio_regex_spans(text)
    if method == "Presidio-class (NER fallback heuristic)":
        return _presidio_ner_spans(text)
    if method == "Hybrid rule+context de-identification":
        return _hybrid_spans(text)
    if method == "BodhiPromptShield (released heuristic mediator)":
        return _policy_aware_spans(text)
    raise ValueError(f"Unsupported method: {method}")


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


def evaluate_transfer(input_path: Path, benchmark_name: str, output_tag: str | None, split_filter: str | None, max_records: int | None) -> tuple[Path, Path, Path, Path]:
    summary_output_path = _with_output_tag(SUMMARY_OUTPUT_PATH, output_tag)
    detail_output_path = _with_output_tag(DETAIL_OUTPUT_PATH, output_tag)
    execution_manifest_path = _with_output_tag(EXECUTION_MANIFEST_PATH, output_tag)
    run_log_path = _with_output_tag(RUN_LOG_PATH, output_tag)

    records = _load_records(input_path)
    if split_filter:
        records = [record for record in records if str(record.get("split", "")) == split_filter]
    if max_records is not None:
        records = records[:max_records]
    if not records:
        raise ValueError("No AI4Privacy records selected for evaluation.")

    summary_rows: list[dict[str, str]] = []
    detail_rows: list[dict[str, str]] = []
    split_counts: dict[str, int] = {}
    total_mentions = 0

    for record in records:
        split = str(record.get("split", "unknown"))
        split_counts[split] = split_counts.get(split, 0) + 1
        spans = record.get("phi_spans", [])
        if isinstance(spans, list):
            total_mentions += sum(1 for span in spans if isinstance(span, dict))

    for spec in METHOD_SPECS:
        method = spec["name"]
        total_tp = total_fp = total_fn = 0
        total_sensitive_chars = total_residual_sensitive_chars = 0
        total_non_sensitive_chars = total_preserved_non_sensitive_chars = 0
        for record in records:
            text = str(record.get("text", ""))
            gold_spans = [(int(span["start"]), int(span["end"])) for span in record.get("phi_spans", []) if isinstance(span, dict)]
            predicted_spans = _predict_spans(method, text)
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
            detail_rows.append(
                {
                    "method": method,
                    "note_id": str(record.get("note_id", "unknown")),
                    "split": str(record.get("split", "unknown")),
                    "gold_mentions": str(len(gold_spans)),
                    "predicted_spans": str(len(predicted_spans)),
                    "span_tp": str(true_positive),
                    "span_fp": str(false_positive),
                    "span_fn": str(false_negative),
                    "per_percent": f"{(100.0 * residual_sensitive_chars / len(gold_chars)) if gold_chars else 0.0:.1f}",
                    "text_retention": f"{(preserved_non_sensitive_chars / len(non_sensitive_chars)) if non_sensitive_chars else 1.0:.3f}",
                }
            )

        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per_percent = 100.0 * total_residual_sensitive_chars / total_sensitive_chars if total_sensitive_chars else 0.0
        text_retention = total_preserved_non_sensitive_chars / total_non_sensitive_chars if total_non_sensitive_chars else 1.0
        summary_rows.append(
            {
                "method": method,
                "document_count": str(len(records)),
                "mention_count": str(total_mentions),
                "span_precision": f"{precision:.2f}",
                "span_recall": f"{recall:.2f}",
                "span_f1": f"{f1:.2f}",
                "per_percent": f"{per_percent:.1f}",
                "text_retention": f"{text_retention:.2f}",
                "notes": spec["notes"],
            }
        )

    with summary_output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    with detail_output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(detail_rows[0].keys()))
        writer.writeheader()
        writer.writerows(detail_rows)

    with execution_manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["benchmark", "method", "family", "execution_status", "result_scope", "notes"])
        writer.writeheader()
        for spec in METHOD_SPECS:
            writer.writerow(
                {
                    "benchmark": benchmark_name,
                    "method": spec["name"],
                    "family": spec["family"],
                    "execution_status": spec["status"],
                    "result_scope": summary_output_path.name,
                    "notes": spec["notes"],
                }
            )

    with run_log_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["benchmark", "input_scope", "document_count", "mention_count", "split_breakdown", "summary_output", "detail_output", "execution_manifest", "notes"])
        writer.writeheader()
        writer.writerow(
            {
                "benchmark": benchmark_name,
                "input_scope": input_path.name,
                "document_count": str(len(records)),
                "mention_count": str(total_mentions),
                "split_breakdown": json.dumps(split_counts, sort_keys=True),
                "summary_output": summary_output_path.name,
                "detail_output": detail_output_path.name,
                "execution_manifest": execution_manifest_path.name,
                "notes": "Executed generic matched baselines on the public AI4Privacy English transfer slice.",
            }
        )

    return summary_output_path, detail_output_path, execution_manifest_path, run_log_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run generic matched baselines on the public AI4Privacy English transfer slice.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH, help="Normalized AI4Privacy JSONL export")
    parser.add_argument("--benchmark-name", default=DEFAULT_BENCHMARK_NAME, help="Benchmark label recorded in outputs")
    parser.add_argument("--output-tag", help="Optional suffix for output files")
    parser.add_argument("--split", help="Optional split filter, e.g. ai4privacy-test")
    parser.add_argument("--max-records", type=int, help="Optional maximum number of records to evaluate")
    args = parser.parse_args()

    outputs = evaluate_transfer(args.input, args.benchmark_name, args.output_tag, args.split, args.max_records)
    print("AI4Privacy transfer outputs written to:")
    for path in outputs:
        print(f" - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())