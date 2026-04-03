#!/usr/bin/env python3
"""Run lightweight matched baselines on the public TAB ECHR JSON release.

This suite turns the existing TAB wrapper manifest into executable result files.
It intentionally evaluates only baselines that can be run from the current
public repository snapshot without external closed-model access or heavyweight
dependencies. The output is therefore an honest first transfer slice rather
than a full reproduction of the planned industrial/LLM baseline roster.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = EXPERIMENTS_DIR / "external_data" / "tab"
SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "tab_transfer_results.csv"
DETAIL_OUTPUT_PATH = EXPERIMENTS_DIR / "tab_transfer_document_metrics.csv"

ROLE_WORDS = {
    "agent",
    "applicant",
    "attorney",
    "barrister",
    "counsel",
    "delegate",
    "director",
    "doctor",
    "dr",
    "governor",
    "judge",
    "lawyer",
    "magistrate",
    "minister",
    "mrs",
    "mr",
    "ms",
    "officer",
    "president",
    "prosecutor",
    "professor",
    "secretary",
    "solicitor",
}

STOPWORD_STARTS = {
    "Article",
    "Articles",
    "Court",
    "Convention",
    "Government",
    "I",
    "II",
    "III",
    "IV",
    "In",
    "On",
    "The",
    "This",
}

REGEX_PATTERNS = [
    re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
    re.compile(r"\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b"),
    re.compile(r"\b(?:no\.?|nos\.?|application|case)\s*\d{1,6}/\d{2,4}\b", re.IGNORECASE),
    re.compile(r"\b\d{2,6}/\d{2,6}\b"),
    re.compile(r"\b[A-Z]{1,4}-\d{2,6}\b"),
    re.compile(r"\b[A-Z]{2,}[0-9]{2,}[A-Z0-9-]*\b"),
    re.compile(r"\b\+?\d[\d()\- ]{6,}\d\b"),
    re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
]

TITLE_PATTERN = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Judge|President|Prosecutor|Professor|Minister|Officer|Governor|Delegate|Counsel|Barrister|Magistrate)\.?\s+"
    r"[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){0,3}"
)
CAPITALIZED_SEQUENCE_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){1,3}"
)
ORG_PATTERN = re.compile(
    r"\b(?:Ministry|Government|Court|Commission|Committee|Office|Bar|Embassy|Cabinet|Police)"
    r"(?:\s+of)?(?:\s+[A-Z][A-Za-z'\-.]+){0,4}"
)
LOCATION_CONTEXT_PATTERN = re.compile(
    r"\b(?:in|at|from|near|to)\s+[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){0,3}"
)


def _load_documents(input_dir: Path) -> list[dict[str, object]]:
    documents: list[dict[str, object]] = []
    for path in sorted(input_dir.glob("*.json")):
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            documents.extend(item for item in payload if isinstance(item, dict))
    return documents


def _ground_truth_spans(document: dict[str, object]) -> list[tuple[int, int]]:
    annotations = document.get("annotations", {})
    mentions: list[tuple[int, int]] = []
    unique: set[tuple[int, int, str]] = set()
    if isinstance(annotations, dict):
        iterables = annotations.values()
    elif isinstance(annotations, list):
        iterables = annotations
    else:
        iterables = []
    for item in iterables:
        if isinstance(item, dict):
            entity_mentions = item.get("entity_mentions", [])
            if isinstance(entity_mentions, list):
                for mention in entity_mentions:
                    if not isinstance(mention, dict):
                        continue
                    start = mention.get("start_offset")
                    end = mention.get("end_offset")
                    entity_type = str(mention.get("entity_type", ""))
                    if not isinstance(start, int) or not isinstance(end, int) or end <= start:
                        continue
                    key = (start, end, entity_type)
                    if key in unique:
                        continue
                    unique.add(key)
                    mentions.append((start, end))
        elif isinstance(item, list):
            for mention in item:
                if not isinstance(mention, dict):
                    continue
                start = mention.get("start_offset")
                end = mention.get("end_offset")
                entity_type = str(mention.get("entity_type", ""))
                if not isinstance(start, int) or not isinstance(end, int) or end <= start:
                    continue
                key = (start, end, entity_type)
                if key in unique:
                    continue
                unique.add(key)
                mentions.append((start, end))
    return sorted(mentions)


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


def _ner_like_spans(text: str, applicant_name: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    spans.extend((match.start(), match.end()) for match in TITLE_PATTERN.finditer(text))
    spans.extend((match.start(), match.end()) for match in ORG_PATTERN.finditer(text))
    for match in CAPITALIZED_SEQUENCE_PATTERN.finditer(text):
        phrase = match.group(0)
        if phrase.split()[0] in STOPWORD_STARTS:
            continue
        spans.append((match.start(), match.end()))
    if applicant_name:
        spans.extend(_find_literal_spans(text, applicant_name))
        surname = applicant_name.split()[-1]
        if len(surname) >= 4:
            spans.extend(_find_literal_spans(text, surname))
    return spans


def _policy_aware_spans(text: str, applicant_name: str) -> list[tuple[int, int]]:
    spans = []
    spans.extend(_regex_spans(text))
    spans.extend(_ner_like_spans(text, applicant_name))
    spans.extend((match.start(), match.end()) for match in LOCATION_CONTEXT_PATTERN.finditer(text))
    for token in ROLE_WORDS:
        pattern = re.compile(rf"\b{re.escape(token.title())}\b")
        for match in pattern.finditer(text):
            end = match.end()
            trailer = text[end : min(len(text), end + 60)]
            next_match = re.match(r"\s+[A-Z][A-Za-z'\-.]+(?:\s+[A-Z][A-Za-z'\-.]+){0,2}", trailer)
            if next_match:
                spans.append((match.start(), end + next_match.end()))
    return spans


def _predict_spans(method: str, text: str, applicant_name: str) -> list[tuple[int, int]]:
    if method == "Raw prompt":
        return []
    if method == "Regex-only":
        return _merge_spans(_regex_spans(text))
    if method == "NER-only masking":
        return _merge_spans(_ner_like_spans(text, applicant_name))
    if method == "BodhiPromptShield (released heuristic mediator)":
        return _merge_spans(_policy_aware_spans(text, applicant_name))
    raise ValueError(f"Unsupported method: {method}")


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


def evaluate_tab_transfer(input_dir: Path) -> tuple[Path, Path]:
    methods = [
        ("Raw prompt", "No protection baseline on the wrapped TAB documents."),
        ("Regex-only", "Pattern-only masking for dates, codes, phones, and other structured identifiers."),
        ("NER-only masking", "Capitalization and title-driven entity masking without policy routing."),
        (
            "BodhiPromptShield (released heuristic mediator)",
            "Released lightweight policy-aware mediator using regex, applicant-name, title, organization, and location heuristics.",
        ),
    ]

    documents = _load_documents(input_dir)
    if not documents:
        raise ValueError(f"No TAB JSON files found under {input_dir}")

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
        for document in documents:
            text = str(document.get("text", ""))
            meta = document.get("meta", {})
            applicant_name = str(meta.get("applicant", "")) if isinstance(meta, dict) else ""
            gold_spans = _ground_truth_spans(document)
            predicted_spans = _predict_spans(method_name, text, applicant_name)
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
                    "document_id": str(document.get("doc_id", "unknown")),
                    "split": str(document.get("dataset_type", "unknown")),
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
                "document_count": str(len(documents)),
                "mention_count": str(total_mentions),
                "span_precision": f"{precision:.2f}",
                "span_recall": f"{recall:.2f}",
                "span_f1": f"{f1:.2f}",
                "per_percent": f"{per_percent:.1f}",
                "text_retention": f"{text_retention:.2f}",
                "notes": notes,
            }
        )

    with open(SUMMARY_OUTPUT_PATH, "w", encoding="utf-8", newline="") as handle:
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

    with open(DETAIL_OUTPUT_PATH, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "method",
                "document_id",
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

    return SUMMARY_OUTPUT_PATH, DETAIL_OUTPUT_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight TAB matched baselines.")
    parser.add_argument(
        "--input-dir",
        default=str(DEFAULT_INPUT_DIR),
        help="Directory containing the public TAB ECHR JSON files.",
    )
    args = parser.parse_args()

    summary_path, detail_path = evaluate_tab_transfer(Path(args.input_dir))
    print(f"TAB transfer summary written to {summary_path}")
    print(f"TAB per-document metrics written to {detail_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())