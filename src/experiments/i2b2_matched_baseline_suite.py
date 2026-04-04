#!/usr/bin/env python3
"""Run matched heuristic baselines on normalized i2b2 exports when available.

The current public repository cannot ship licensed i2b2 notes, but it can ship
the exact runner, result schema, and execution manifest used once a licensed
normalized export is supplied by the user.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "i2b2_transfer_results.csv"
DETAIL_OUTPUT_PATH = EXPERIMENTS_DIR / "i2b2_transfer_document_metrics.csv"
EXECUTION_MANIFEST_PATH = EXPERIMENTS_DIR / "i2b2_transfer_execution_manifest.csv"
RUN_LOG_PATH = EXPERIMENTS_DIR / "i2b2_transfer_run_log.csv"
DEFAULT_BENCHMARK_NAME = "2014 i2b2/UTHealth"


def _with_output_tag(path: Path, output_tag: str | None) -> Path:
    if not output_tag:
        return path
    return path.with_name(f"{path.stem}_{output_tag}{path.suffix}")

METHOD_SPECS = [
    {
        "name": "Raw prompt",
        "family": "No protection",
        "status": "executable_with_licensed_data",
        "notes": "No sanitization is applied before evaluation.",
    },
    {
        "name": "Regex-only",
        "family": "Pattern baseline",
        "status": "executable_with_licensed_data",
        "notes": "Structured PHI patterns only.",
    },
    {
        "name": "NER-only masking",
        "family": "Entity baseline",
        "status": "executable_with_licensed_data",
        "notes": "Capitalization and title heuristics without clinical routing.",
    },
    {
        "name": "Presidio-class (regex-focused heuristic)",
        "family": "Industrial de-identification",
        "status": "executable_with_licensed_data",
        "notes": "Released approximation of a Presidio-class structured recognizer stack under the clinical wrapper.",
    },
    {
        "name": "Presidio-class (NER fallback heuristic)",
        "family": "Industrial de-identification",
        "status": "executable_with_licensed_data",
        "notes": "Released approximation of a Presidio-class structured-plus-NER stack under the clinical wrapper.",
    },
    {
        "name": "Clinical hybrid heuristic de-identification",
        "family": "Hybrid heuristic de-identification",
        "status": "executable_with_licensed_data",
        "notes": "Released hybrid heuristic using structured, named-entity, clinical-context, and location cues under the clinical wrapper.",
    },
    {
        "name": "Clinical hybrid de-identification pipeline",
        "family": "Clinical domain baseline",
        "status": "pending_external_runtime",
        "notes": "Intended for a domain-specific pipeline not bundled in the public repository snapshot.",
    },
    {
        "name": "Prompted LLM zero-shot de-identification",
        "family": "Semantic baseline",
        "status": "pending_external_runtime",
        "notes": "Protocol defined, but no closed-model runtime is bundled in the current release.",
    },
    {
        "name": "BodhiPromptShield (released heuristic mediator)",
        "family": "Policy-aware mediation",
        "status": "executable_with_licensed_data",
        "notes": "Released lightweight policy-aware mediator using bundled heuristics only.",
    },
]

ROLE_WORDS = {
    "attending",
    "clinic",
    "department",
    "doctor",
    "dr",
    "hospital",
    "mr",
    "mrs",
    "ms",
    "patient",
    "physician",
    "provider",
    "room",
    "ward",
}

REGEX_PATTERNS = [
    re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
    re.compile(r"\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b"),
    re.compile(r"\b\+?\d[\d()\- ]{6,}\d\b"),
    re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:MRN|ID|Acct|Account|Visit|Case)[:#\s-]*[A-Z0-9-]{4,}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,5}\s+[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){0,3}\s+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b"),
]

TITLE_PATTERN = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Doctor|Patient|Provider|Physician)\.?\s+"
    r"[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){0,3}"
)
CAPITALIZED_SEQUENCE_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){1,3}"
)
ORG_PATTERN = re.compile(
    r"\b(?:Hospital|Clinic|Medical Center|Health System|Department|Practice|Laboratory|Pharmacy)"
    r"(?:\s+of)?(?:\s+[A-Z][A-Za-z'\-.]+){0,4}"
)
LOCATION_CONTEXT_PATTERN = re.compile(
    r"\b(?:in|at|from|near|to|lives in|resides in)\s+[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){0,3}",
    re.IGNORECASE,
)
CLINICAL_CONTEXT_PATTERN = re.compile(
    r"\b(?:patient|provider|physician|doctor|attending|room|ward|clinic|hospital)"
    r"(?:\s+[A-Z][A-Za-z'\-.]+){0,4}",
    re.IGNORECASE,
)


def _write_execution_manifest(input_supplied: bool, benchmark_name: str, execution_manifest_path: Path, summary_output_path: Path) -> Path:
    with open(execution_manifest_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["method", "family", "execution_status", "result_scope", "notes"],
        )
        writer.writeheader()
        for spec in METHOD_SPECS:
            status = spec["status"]
            if status == "executable_with_licensed_data":
                status = "executed" if input_supplied else "waiting_for_licensed_data"
            writer.writerow(
                {
                    "method": spec["name"],
                    "family": spec["family"],
                    "execution_status": status,
                    "result_scope": summary_output_path.name if input_supplied and status == "executed" else "protocol-only",
                    "notes": spec["notes"],
                }
            )
    return execution_manifest_path


def _load_records(path: Path) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        if path.suffix.lower() == ".jsonl":
            return [json.loads(line) for line in handle if line.strip()]
        payload = json.load(handle)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("records", "notes", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError(f"Unsupported normalized i2b2 payload in {path}")


def _find_literal_spans(text: str, phrase: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    if not phrase:
        return spans
    start = 0
    while True:
        idx = text.find(phrase, start)
        if idx == -1:
            break
        spans.append((idx, idx + len(phrase)))
        start = idx + len(phrase)
    return spans


def _regex_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in REGEX_PATTERNS:
        spans.extend((match.start(), match.end()) for match in pattern.finditer(text))
    return spans


def _ner_like_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    spans.extend((match.start(), match.end()) for match in TITLE_PATTERN.finditer(text))
    spans.extend((match.start(), match.end()) for match in ORG_PATTERN.finditer(text))
    for match in CAPITALIZED_SEQUENCE_PATTERN.finditer(text):
        phrase = match.group(0)
        if phrase.split()[0].lower() in {"the", "a", "an", "and"}:
            continue
        spans.append((match.start(), match.end()))
    return spans


def _presidio_regex_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    spans.extend(_regex_spans(text))
    spans.extend((match.start(), match.end()) for match in TITLE_PATTERN.finditer(text))
    return spans


def _presidio_ner_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    spans.extend(_presidio_regex_spans(text))
    spans.extend((match.start(), match.end()) for match in ORG_PATTERN.finditer(text))
    spans.extend(_ner_like_spans(text))
    return spans


def _clinical_hybrid_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    spans.extend(_presidio_regex_spans(text))
    spans.extend((match.start(), match.end()) for match in ORG_PATTERN.finditer(text))
    spans.extend((match.start(), match.end()) for match in LOCATION_CONTEXT_PATTERN.finditer(text))
    spans.extend((match.start(), match.end()) for match in CLINICAL_CONTEXT_PATTERN.finditer(text))
    return spans


def _policy_aware_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    spans.extend(_regex_spans(text))
    spans.extend(_ner_like_spans(text))
    spans.extend((match.start(), match.end()) for match in LOCATION_CONTEXT_PATTERN.finditer(text))
    spans.extend((match.start(), match.end()) for match in CLINICAL_CONTEXT_PATTERN.finditer(text))
    for token in ROLE_WORDS:
        pattern = re.compile(rf"\b{re.escape(token.title())}\b")
        for match in pattern.finditer(text):
            end = match.end()
            trailer = text[end : min(len(text), end + 60)]
            next_match = re.match(r"\s+[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){0,2}", trailer)
            if next_match:
                spans.append((match.start(), end + next_match.end()))
    return spans


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    merged: list[list[int]] = [[spans[0][0], spans[0][1]]]
    for start, end in sorted(spans):
        current = merged[-1]
        if start <= current[1]:
            current[1] = max(current[1], end)
            continue
        merged.append([start, end])
    return [(start, end) for start, end in merged]


def _predict_spans(method: str, text: str) -> list[tuple[int, int]]:
    if method == "Raw prompt":
        return []
    if method == "Regex-only":
        return _merge_spans(_regex_spans(text))
    if method == "NER-only masking":
        return _merge_spans(_ner_like_spans(text))
    if method == "Presidio-class (regex-focused heuristic)":
        return _merge_spans(_presidio_regex_spans(text))
    if method == "Presidio-class (NER fallback heuristic)":
        return _merge_spans(_presidio_ner_spans(text))
    if method == "Clinical hybrid heuristic de-identification":
        return _merge_spans(_clinical_hybrid_spans(text))
    if method == "BodhiPromptShield (released heuristic mediator)":
        return _merge_spans(_policy_aware_spans(text))
    raise ValueError(f"Unsupported method: {method}")


def _write_run_log(
    records: list[dict[str, Any]],
    input_supplied: bool,
    input_path: Path | None,
    *,
    benchmark_name: str,
    run_log_path: Path,
    execution_manifest_path: Path,
    wrapper_manifest_name: str,
    summary_output_path: Path,
    detail_output_path: Path,
) -> None:
    split_counts: dict[str, int] = {}
    mention_count = 0
    for record in records:
        split = str(record.get("split", "unknown"))
        split_counts[split] = split_counts.get(split, 0) + 1
        raw_spans = record.get("phi_spans", [])
        if isinstance(raw_spans, list):
            mention_count += sum(1 for span in raw_spans if isinstance(span, dict))

    with open(run_log_path, "w", encoding="utf-8", newline="") as handle:
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
                "protocol_file",
                "wrapper_manifest",
                "summary_output",
                "detail_output",
                "execution_manifest",
                "command_template",
                "notes",
            ],
        )
        writer.writeheader()
        for spec in METHOD_SPECS:
            status = spec["status"]
            if status == "executable_with_licensed_data":
                status = "executed" if input_supplied else "waiting_for_licensed_data"
            writer.writerow(
                {
                    "benchmark": benchmark_name,
                    "method": spec["name"],
                    "family": spec["family"],
                    "execution_status": status,
                    "input_scope": str(input_path) if input_path else "licensed normalized export required",
                    "document_count": str(len(records)),
                    "mention_count": str(mention_count),
                    "split_breakdown": " | ".join(f"{key}:{value}" for key, value in sorted(split_counts.items())),
                    "protocol_file": "i2b2_matched_baseline_protocol.json",
                    "wrapper_manifest": wrapper_manifest_name if input_supplied else "",
                    "summary_output": summary_output_path.name if input_supplied and status == "executed" else "",
                    "detail_output": detail_output_path.name if input_supplied and status == "executed" else "",
                    "execution_manifest": execution_manifest_path.name,
                    "command_template": "python src/experiments/i2b2_matched_baseline_suite.py <normalized_i2b2_export.jsonl>",
                    "notes": spec["notes"],
                }
            )


def _overlap(span_a: tuple[int, int], span_b: tuple[int, int]) -> int:
    return max(0, min(span_a[1], span_b[1]) - max(span_a[0], span_b[0]))


def _span_counts(predicted: list[tuple[int, int]], gold: list[tuple[int, int]]) -> tuple[int, int, int]:
    matched_gold: set[int] = set()
    true_positive = 0
    for pred in predicted:
        best_idx = -1
        best_overlap = 0
        for idx, gold_span in enumerate(gold):
            if idx in matched_gold:
                continue
            overlap = _overlap(pred, gold_span)
            if overlap > best_overlap:
                best_idx = idx
                best_overlap = overlap
        if best_idx != -1 and best_overlap > 0:
            matched_gold.add(best_idx)
            true_positive += 1
    false_positive = max(0, len(predicted) - true_positive)
    false_negative = max(0, len(gold) - true_positive)
    return true_positive, false_positive, false_negative


def _char_coverage(spans: list[tuple[int, int]]) -> set[int]:
    covered: set[int] = set()
    for start, end in spans:
        covered.update(range(start, end))
    return covered


def evaluate_i2b2_transfer(
    input_path: Path,
    *,
    benchmark_name: str,
    output_tag: str | None,
    wrapper_manifest_name: str,
) -> tuple[Path, Path, Path, Path]:
    summary_output_path = _with_output_tag(SUMMARY_OUTPUT_PATH, output_tag)
    detail_output_path = _with_output_tag(DETAIL_OUTPUT_PATH, output_tag)
    execution_manifest_path = _with_output_tag(EXECUTION_MANIFEST_PATH, output_tag)
    run_log_path = _with_output_tag(RUN_LOG_PATH, output_tag)
    methods = [
        ("Raw prompt", "No protection baseline on the wrapped clinical notes."),
        ("Regex-only", "Pattern-only masking for dates, IDs, phones, emails, and address-like spans."),
        ("NER-only masking", "Capitalization and title-driven masking without clinical routing."),
        (
            "Presidio-class (regex-focused heuristic)",
            "Released approximation of a Presidio-class structured recognizer stack under the clinical wrapper.",
        ),
        (
            "Presidio-class (NER fallback heuristic)",
            "Released approximation of a Presidio-class structured-plus-NER stack under the clinical wrapper.",
        ),
        (
            "Clinical hybrid heuristic de-identification",
            "Released hybrid heuristic using structured, named-entity, clinical-context, and location cues under the clinical wrapper.",
        ),
        (
            "BodhiPromptShield (released heuristic mediator)",
            "Released lightweight policy-aware mediator using regex, clinical context, title, organization, and location heuristics.",
        ),
    ]

    records = _load_records(input_path)
    if not records:
        raise ValueError(f"No normalized i2b2 notes found in {input_path}")

    summary_rows: list[dict[str, str]] = []
    detail_rows: list[dict[str, str]] = []
    for method_name, notes in methods:
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_sensitive_chars = 0
        total_residual_sensitive_chars = 0
        total_non_sensitive_chars = 0
        total_preserved_non_sensitive_chars = 0
        total_mentions = 0
        for record in records:
            text = str(record.get("text", ""))
            raw_spans = record.get("phi_spans", [])
            if not isinstance(raw_spans, list):
                raw_spans = []
            gold_spans = [
                (int(span["start"]), int(span["end"]))
                for span in raw_spans
                if isinstance(span, dict) and isinstance(span.get("start"), int) and isinstance(span.get("end"), int)
            ]
            predicted_spans = _predict_spans(method_name, text)
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

            detail_rows.append(
                {
                    "method": method_name,
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
                "method": method_name,
                "document_count": str(len(records)),
                "mention_count": str(total_mentions),
                "span_precision": f"{precision:.2f}",
                "span_recall": f"{recall:.2f}",
                "span_f1": f"{f1:.2f}",
                "per_percent": f"{per_percent:.1f}",
                "text_retention": f"{text_retention:.2f}",
                "notes": notes,
            }
        )

    with open(summary_output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "method",
                "document_count",
                "mention_count",
                "span_precision",
                "span_recall",
                "span_f1",
                "per_percent",
                "text_retention",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    with open(detail_output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "method",
                "note_id",
                "split",
                "gold_mentions",
                "predicted_spans",
                "span_tp",
                "span_fp",
                "span_fn",
                "per_percent",
                "text_retention",
            ],
        )
        writer.writeheader()
        writer.writerows(detail_rows)

    _write_execution_manifest(
        input_supplied=True,
        benchmark_name=benchmark_name,
        execution_manifest_path=execution_manifest_path,
        summary_output_path=summary_output_path,
    )
    _write_run_log(
        records,
        input_supplied=True,
        input_path=input_path,
        benchmark_name=benchmark_name,
        run_log_path=run_log_path,
        execution_manifest_path=execution_manifest_path,
        wrapper_manifest_name=wrapper_manifest_name,
        summary_output_path=summary_output_path,
        detail_output_path=detail_output_path,
    )
    return summary_output_path, detail_output_path, execution_manifest_path, run_log_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run heuristic i2b2 matched baselines when a licensed normalized export is available.")
    parser.add_argument("input", nargs="?", help="Normalized i2b2 JSONL or JSON export")
    parser.add_argument("--benchmark-name", default=DEFAULT_BENCHMARK_NAME, help="Benchmark label recorded in outputs")
    parser.add_argument("--output-tag", help="Optional suffix added to output files")
    parser.add_argument("--wrapper-manifest", default="i2b2_prompt_wrapped_manifest.csv", help="Wrapper manifest filename recorded in the run log")
    args = parser.parse_args()

    summary_output_path = _with_output_tag(SUMMARY_OUTPUT_PATH, args.output_tag)
    detail_output_path = _with_output_tag(DETAIL_OUTPUT_PATH, args.output_tag)
    execution_manifest_path = _with_output_tag(EXECUTION_MANIFEST_PATH, args.output_tag)
    run_log_path = _with_output_tag(RUN_LOG_PATH, args.output_tag)

    if not args.input:
        manifest_path = _write_execution_manifest(
            input_supplied=False,
            benchmark_name=args.benchmark_name,
            execution_manifest_path=execution_manifest_path,
            summary_output_path=summary_output_path,
        )
        _write_run_log(
            [],
            input_supplied=False,
            input_path=None,
            benchmark_name=args.benchmark_name,
            run_log_path=run_log_path,
            execution_manifest_path=execution_manifest_path,
            wrapper_manifest_name=args.wrapper_manifest,
            summary_output_path=summary_output_path,
            detail_output_path=detail_output_path,
        )
        print(f"i2b2 execution manifest written to {manifest_path}")
        print(f"i2b2 run log written to {run_log_path}")
        print("No normalized i2b2 export supplied; results remain pending licensed data.")
        return 0

    summary_path, detail_path, manifest_path, run_log_path = evaluate_i2b2_transfer(
        Path(args.input),
        benchmark_name=args.benchmark_name,
        output_tag=args.output_tag,
        wrapper_manifest_name=args.wrapper_manifest,
    )
    print(f"i2b2 transfer summary written to {summary_path}")
    print(f"i2b2 per-document metrics written to {detail_path}")
    print(f"i2b2 execution manifest written to {manifest_path}")
    print(f"i2b2 run log written to {run_log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())