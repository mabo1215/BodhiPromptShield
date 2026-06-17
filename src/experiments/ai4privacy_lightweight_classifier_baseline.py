#!/usr/bin/env python3
"""Lightweight learned privacy-span classifier baseline on public AI4Privacy.

Reviewer 541B asks how the rule + NER + contextual-heuristic span detector
compares with simpler learned alternatives such as small privacy judges or
lightweight classifiers of the kind used for policy-violation or
offensive-content detection. The existing repository answers this only with a
prompted open-weight zero-shot pilot. This script adds a *formal*, deterministic,
self-contained lightweight classifier baseline so the comparison is not only a
pilot.

The baseline is a token-level logistic-regression privacy-span detector trained
on the public ``ai4privacy-train`` split and evaluated on the held-out
``ai4privacy-test`` split, scored with exactly the same span-overlap,
PER (residual-exposure), and text-retention metrics used by the matched
baseline suite. It uses only cheap lexical/shape/context features (digits,
capitalization, punctuation shape, e-mail/number patterns, and neighbouring
context cues), so it stands in for a deployable lightweight classifier rather
than a large model. The optimizer is plain class-weighted SGD with a fixed seed,
fixed epoch count, and zero initialization, so the artifact is reproducible from
repository files with no external model dependency.
"""
from __future__ import annotations

import argparse
import csv
import math
import re
from pathlib import Path

from ai4privacy_matched_baseline_suite import _char_coverage
from ai4privacy_matched_baseline_suite import _load_records
from ai4privacy_matched_baseline_suite import _merge_spans
from ai4privacy_matched_baseline_suite import _span_counts


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = EXPERIMENTS_DIR / "ai4privacy_pii300k_english_export.jsonl"
RESULTS_PATH = EXPERIMENTS_DIR / "ai4privacy_lightweight_classifier_results.csv"
COMPARISON_PATH = EXPERIMENTS_DIR / "lightweight_classifier_comparison.csv"
RUNTIME_PATH = EXPERIMENTS_DIR / "ai4privacy_lightweight_classifier_runtime_manifest.csv"
MATCHED_SUMMARY_PATH = EXPERIMENTS_DIR / "ai4privacy_transfer_results.csv"

TOKEN_PATTERN = re.compile(r"\S+")
CONTEXT_CUES = {
    "at", "in", "from", "near", "to", "mr", "mrs", "ms", "dr",
    "username", "user", "account", "passport", "license", "id",
    "password", "postcode", "zip", "ssn", "email", "phone", "call",
    "contact", "address", "name", "named", "dob", "born",
}

# Training / optimization hyper-parameters. Fixed for reproducibility.
TRAIN_DOC_LIMIT = 3000
EPOCHS = 25
LEARNING_RATE = 0.25
L2 = 1e-5
DECISION_THRESHOLD = 0.5


def _tokenize(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group(0)) for m in TOKEN_PATTERN.finditer(text)]


def _token_features(token: str, prev_token: str | None) -> list[str]:
    """Return the names of the active (binary) features for one token."""
    feats: list[str] = ["bias"]
    core = token.strip(".,;:!?()[]{}\"'")
    if any(ch.isdigit() for ch in token):
        feats.append("has_digit")
    if core.isdigit():
        feats.append("all_digit")
    if len(core) >= 2 and sum(ch.isdigit() for ch in core) >= len(core) / 2:
        feats.append("digit_heavy")
    if core[:1].isupper():
        feats.append("is_capitalized")
    if core.isupper() and len(core) > 1:
        feats.append("all_caps")
    if "@" in token:
        feats.append("has_at")
    if "." in token:
        feats.append("has_dot")
    if ":" in token:
        feats.append("has_colon")
    if "/" in token:
        feats.append("has_slash")
    if "-" in token:
        feats.append("has_hyphen")
    if "_" in token:
        feats.append("has_underscore")
    if len(core) >= 12:
        feats.append("very_long")
    elif len(core) >= 8:
        feats.append("long")
    if re.search(r"[A-Za-z]", token) and re.search(r"\d", token):
        feats.append("alnum_mix")
    if prev_token is not None and prev_token.strip(".,;:!?()[]{}\"'").lower() in CONTEXT_CUES:
        feats.append("ctx_cue_prev")
    if prev_token is not None and prev_token.endswith(":"):
        feats.append("prev_colon")
    return feats


def _is_sensitive_token(start: int, end: int, gold_chars: set[int]) -> bool:
    """A token is sensitive if at least half its characters are gold."""
    if end <= start:
        return False
    covered = sum(1 for pos in range(start, end) if pos in gold_chars)
    return covered >= (end - start) / 2.0


def _build_examples(records: list[dict]) -> list[tuple[list[str], int]]:
    examples: list[tuple[list[str], int]] = []
    for record in records:
        text = str(record.get("text", ""))
        gold_spans = [
            (int(span["start"]), int(span["end"]))
            for span in record.get("phi_spans", [])
            if isinstance(span, dict)
        ]
        gold_chars = _char_coverage(gold_spans)
        tokens = _tokenize(text)
        for idx, (start, end, token) in enumerate(tokens):
            prev_token = tokens[idx - 1][2] if idx > 0 else None
            label = 1 if _is_sensitive_token(start, end, gold_chars) else 0
            examples.append((_token_features(token, prev_token), label))
    return examples


def _train_logreg(examples: list[tuple[list[str], int]]) -> tuple[dict[str, float], float]:
    positives = sum(label for _, label in examples)
    negatives = len(examples) - positives
    pos_weight = (negatives / positives) if positives else 1.0

    weights: dict[str, float] = {}
    # Deterministic shuffle (fixed permutation) for stable SGD ordering.
    order = list(range(len(examples)))
    seed = 1234567
    for epoch in range(EPOCHS):
        # Linear congruential reshuffle keeps the run dependency-free and seeded.
        for i in range(len(order) - 1, 0, -1):
            seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
            j = seed % (i + 1)
            order[i], order[j] = order[j], order[i]
        for k in order:
            feats, label = examples[k]
            score = sum(weights.get(name, 0.0) for name in feats)
            pred = 1.0 / (1.0 + math.exp(-score))
            weight = pos_weight if label == 1 else 1.0
            grad = weight * (pred - label)
            for name in feats:
                current = weights.get(name, 0.0)
                weights[name] = current - LEARNING_RATE * (grad + L2 * current)
    return weights, pos_weight


def _predict_spans(weights: dict[str, float], text: str) -> list[tuple[int, int]]:
    tokens = _tokenize(text)
    spans: list[tuple[int, int]] = []
    for idx, (start, end, token) in enumerate(tokens):
        prev_token = tokens[idx - 1][2] if idx > 0 else None
        feats = _token_features(token, prev_token)
        score = sum(weights.get(name, 0.0) for name in feats)
        prob = 1.0 / (1.0 + math.exp(-score))
        if prob >= DECISION_THRESHOLD:
            spans.append((start, end))
    return _merge_spans(spans)


def _evaluate(weights: dict[str, float], records: list[dict]) -> dict[str, float]:
    total_tp = total_fp = total_fn = 0
    total_sensitive = total_residual = 0
    total_non_sensitive = total_preserved = 0
    total_mentions = 0
    for record in records:
        text = str(record.get("text", ""))
        gold_spans = [
            (int(span["start"]), int(span["end"]))
            for span in record.get("phi_spans", [])
            if isinstance(span, dict)
        ]
        total_mentions += len(gold_spans)
        predicted = _predict_spans(weights, text)
        tp, fp, fn = _span_counts(predicted, gold_spans)
        gold_chars = _char_coverage(gold_spans)
        pred_chars = _char_coverage(predicted)
        non_sensitive = set(range(len(text))) - gold_chars
        total_tp += tp
        total_fp += fp
        total_fn += fn
        total_sensitive += len(gold_chars)
        total_residual += len(gold_chars - pred_chars)
        total_non_sensitive += len(non_sensitive)
        total_preserved += len(non_sensitive - pred_chars)

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    per = 100.0 * total_residual / total_sensitive if total_sensitive else 0.0
    retention = total_preserved / total_non_sensitive if total_non_sensitive else 1.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "per_percent": per,
        "text_retention": retention,
        "mentions": float(total_mentions),
    }


def _read_matched_rows() -> dict[str, dict[str, str]]:
    if not MATCHED_SUMMARY_PATH.exists():
        return {}
    with MATCHED_SUMMARY_PATH.open("r", encoding="utf-8") as handle:
        return {row["method"]: row for row in csv.DictReader(handle)}


def run(input_path: Path, train_split: str, test_split: str) -> None:
    records = _load_records(input_path)
    train_records = [r for r in records if str(r.get("split")) == train_split][:TRAIN_DOC_LIMIT]
    test_records = [r for r in records if str(r.get("split")) == test_split]
    if not train_records or not test_records:
        raise ValueError("Train or test split is empty; check split labels.")

    examples = _build_examples(train_records)
    weights, pos_weight = _train_logreg(examples)
    metrics = _evaluate(weights, test_records)

    method_name = "Lightweight learned classifier (logistic regression)"
    result_row = {
        "method": method_name,
        "document_count": str(len(test_records)),
        "mention_count": str(int(metrics["mentions"])),
        "span_precision": f"{metrics['precision']:.2f}",
        "span_recall": f"{metrics['recall']:.2f}",
        "span_f1": f"{metrics['f1']:.2f}",
        "per_percent": f"{metrics['per_percent']:.1f}",
        "text_retention": f"{metrics['text_retention']:.2f}",
        "notes": (
            "Token-level class-weighted logistic regression trained on "
            f"{len(train_records)} public {train_split} documents using lexical/"
            "shape/context features; evaluated on the held-out test split."
        ),
    }
    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result_row.keys()))
        writer.writeheader()
        writer.writerow(result_row)

    # Build a compact comparison against key matched baselines + proposed.
    matched = _read_matched_rows()
    comparison_methods = [
        ("Regex-only", "Pattern baseline"),
        ("Presidio-class (NER fallback heuristic)", "Industrial de-identification"),
        ("Hybrid rule+context de-identification", "Hybrid heuristic de-identification"),
        (method_name, "Lightweight learned baseline"),
        ("BodhiPromptShield (released heuristic mediator)", "Policy-aware mediation"),
    ]
    comparison_rows: list[dict[str, str]] = []
    for name, family in comparison_methods:
        if name == method_name:
            src = result_row
        elif name in matched:
            src = matched[name]
        else:
            continue
        comparison_rows.append(
            {
                "method": name,
                "family": family,
                "span_precision": src["span_precision"],
                "span_recall": src["span_recall"],
                "span_f1": src["span_f1"],
                "per_percent": src["per_percent"],
                "text_retention": src["text_retention"],
            }
        )
    with COMPARISON_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "method",
                "family",
                "span_precision",
                "span_recall",
                "span_f1",
                "per_percent",
                "text_retention",
            ],
        )
        writer.writeheader()
        writer.writerows(comparison_rows)

    runtime_rows = [
        {"field": "benchmark", "value": "AI4Privacy PII-Masking-300K (English)"},
        {"field": "train_split", "value": f"{train_split} (first {len(train_records)} docs)"},
        {"field": "test_split", "value": f"{test_split} ({len(test_records)} docs)"},
        {"field": "model", "value": "Token-level logistic regression (sparse binary features)"},
        {"field": "feature_count", "value": str(len(weights))},
        {"field": "epochs", "value": str(EPOCHS)},
        {"field": "learning_rate", "value": str(LEARNING_RATE)},
        {"field": "l2", "value": str(L2)},
        {"field": "positive_class_weight", "value": f"{pos_weight:.2f}"},
        {"field": "decision_threshold", "value": str(DECISION_THRESHOLD)},
        {"field": "randomness", "value": "Deterministic seeded LCG shuffle; zero init"},
        {"field": "dependencies", "value": "Pure Python standard library only"},
    ]
    with RUNTIME_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "value"])
        writer.writeheader()
        writer.writerows(runtime_rows)

    print(f"Lightweight classifier results written to {RESULTS_PATH}")
    print(f"Lightweight classifier comparison written to {COMPARISON_PATH}")
    print(f"Lightweight classifier runtime manifest written to {RUNTIME_PATH}")
    print(
        "Test metrics: "
        f"P={metrics['precision']:.2f} R={metrics['recall']:.2f} "
        f"F1={metrics['f1']:.2f} PER={metrics['per_percent']:.1f}% "
        f"retention={metrics['text_retention']:.2f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT_PATH))
    parser.add_argument("--train-split", default="ai4privacy-train")
    parser.add_argument("--test-split", default="ai4privacy-test")
    args = parser.parse_args()
    run(Path(args.input), args.train_split, args.test_split)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
