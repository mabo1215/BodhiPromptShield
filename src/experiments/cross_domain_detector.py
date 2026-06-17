#!/usr/bin/env python3
"""Cross-domain validity of the lightweight learned detector (review item W4).

The learned detector is otherwise reported only in-domain (AI4Privacy). This
script measures cross-domain transfer by training the same deterministic
logistic span detector on one domain and evaluating it on another, on real text
with gold spans:

* generic multi-domain PII  : AI4Privacy English (train/test).
* clinical                  : public PhysioNet-relabeled clinical notes.

For each (train-domain -> test-domain) pair it reports measured span
precision/recall/F1 and residual exposure (PER). The in-domain vs. cross-domain
gap quantifies how far a single-domain learned detector generalizes.
"""
from __future__ import annotations

import csv
from pathlib import Path

from ai4privacy_matched_baseline_suite import _char_coverage
from ai4privacy_matched_baseline_suite import _span_counts

import ai4privacy_lightweight_classifier_baseline as clf


EXPERIMENTS_DIR = Path(__file__).resolve().parent
AI4_PATH = EXPERIMENTS_DIR / "ai4privacy_pii300k_english_export.jsonl"
CLINICAL_PATH = EXPERIMENTS_DIR / "physionet_deid_relabeled_export.jsonl"
RESULTS_PATH = EXPERIMENTS_DIR / "cross_domain_detector_results.csv"
RUNTIME_PATH = EXPERIMENTS_DIR / "cross_domain_detector_runtime_manifest.csv"

TRAIN_DOCS = 3000
TEST_DOCS = 300


def _load(path: Path, split: str, limit: int) -> list[dict]:
    rows = [r for r in clf._load_records(path) if str(r.get("split")) == split]
    return rows[:limit]


def _gold(record: dict) -> list[tuple[int, int]]:
    return [
        (int(s["start"]), int(s["end"]))
        for s in record.get("phi_spans", [])
        if isinstance(s, dict)
    ]


def _train(records: list[dict]) -> dict:
    weights, _ = clf._train_logreg(clf._build_examples(records))
    return weights


def _evaluate(weights: dict, records: list[dict]) -> dict[str, float]:
    tp = fp = fn = 0
    sens = res = 0
    for record in records:
        text = str(record.get("text", ""))
        gold = _gold(record)
        pred = clf._predict_spans(weights, text)
        a, b, c = _span_counts(pred, gold)
        tp += a; fp += b; fn += c
        gold_chars = _char_coverage(gold)
        pred_chars = _char_coverage(pred)
        sens += len(gold_chars)
        res += len(gold_chars - pred_chars)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    per = 100.0 * res / sens if sens else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "per": per}


def run() -> None:
    ai_train = _load(AI4_PATH, "ai4privacy-train", TRAIN_DOCS)
    ai_test = _load(AI4_PATH, "ai4privacy-test", TEST_DOCS)
    cl_train = _load(CLINICAL_PATH, "physionet-train", TRAIN_DOCS)
    cl_test = _load(CLINICAL_PATH, "physionet-test", TEST_DOCS)

    w_generic = _train(ai_train)
    w_clinical = _train(cl_train)

    pairs = [
        ("Generic (AI4Privacy)", "Generic (AI4Privacy)", w_generic, ai_test, "in-domain"),
        ("Generic (AI4Privacy)", "Clinical (PhysioNet)", w_generic, cl_test, "cross-domain"),
        ("Clinical (PhysioNet)", "Clinical (PhysioNet)", w_clinical, cl_test, "in-domain"),
        ("Clinical (PhysioNet)", "Generic (AI4Privacy)", w_clinical, ai_test, "cross-domain"),
    ]

    rows = []
    for train_dom, test_dom, weights, test_records, kind in pairs:
        m = _evaluate(weights, test_records)
        rows.append(
            {
                "train_domain": train_dom,
                "test_domain": test_dom,
                "setting": kind,
                "documents": str(len(test_records)),
                "precision": f"{m['precision']:.2f}",
                "recall": f"{m['recall']:.2f}",
                "span_f1": f"{m['f1']:.2f}",
                "per_percent": f"{m['per']:.1f}",
            }
        )

    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["train_domain", "test_domain", "setting", "documents", "precision", "recall", "span_f1", "per_percent"],
        )
        writer.writeheader()
        writer.writerows(rows)

    runtime_rows = [
        {"field": "model", "value": "Lightweight learned logistic span detector (shared with AI4Privacy baseline)"},
        {"field": "generic_domain", "value": "AI4Privacy PII-Masking-300K (English)"},
        {"field": "clinical_domain", "value": "Public PhysioNet-relabeled clinical notes"},
        {"field": "train_docs_cap", "value": str(TRAIN_DOCS)},
        {"field": "test_docs", "value": str(TEST_DOCS)},
        {"field": "measurement", "value": "Span overlap P/R/F1 and char-coverage PER on real text"},
        {"field": "randomness", "value": "Deterministic seeded SGD; reproducible"},
    ]
    with RUNTIME_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "value"])
        writer.writeheader()
        writer.writerows(runtime_rows)

    print(f"Cross-domain detector results written to {RESULTS_PATH}")
    for r in rows:
        print(f"  {r['train_domain']:22s} -> {r['test_domain']:22s} [{r['setting']:11s}] "
              f"R={r['recall']} F1={r['span_f1']} PER={r['per_percent']}%")


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
