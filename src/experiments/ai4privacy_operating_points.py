#!/usr/bin/env python3
"""Compare detectors on AI4Privacy at matched text retention, not at one setting each.

PER rewards over-redaction: a detector that masks more text scores lower. The
exposure table reports each detector at its default threshold, and those defaults
keep different amounts of non-sensitive text (learned 0.80, transformer 0.94,
Presidio 0.97), so the table alone cannot say whether one detector beats another
or merely sits further along the same trade-off. This sweeps the decision
threshold of the three detectors that expose a score, over the same 300 held-out
documents and with the same per-document counts as the exposure table.

Each detector runs once at a low score floor and is filtered per threshold. The
counts at each default threshold must equal the recorded exposure-table documents,
and the script refuses to write the summary otherwise.

Outputs, next to this script:

* ``ai4privacy_operating_points_documents.csv``: one row per (detector, threshold,
  document), appended and flushed per document so that a run can resume;
* ``ai4privacy_operating_points_summary.csv``: PER, retention, and span precision
  with document-level bootstrap intervals per detector and threshold;
* ``ai4privacy_operating_points_matched.csv``: at each retention level, the lowest
  PER each detector reaches while keeping at least that much text, and the paired
  difference from the learned detector over the same documents.

Every threshold is reported, none is selected for later use, and the matched rows are
read off the same held-out documents, so they describe the trade-off rather than
tune a detector.

Run with the project's virtual environment, which holds the detector stack:

    python src/experiments/ai4privacy_operating_points.py
"""
from __future__ import annotations

import argparse
import collections
import csv
import math
import os
import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENTS_DIR))

import ai4privacy_lightweight_classifier_baseline as clf  # noqa: E402
from ai4privacy_matched_baseline_suite import _merge_spans  # noqa: E402
from downstream_paired_tests import paired_bootstrap_diff  # noqa: E402
from mediation_baselines import (  # noqa: E402
    GLINER_LABELS,
    GLINER_MODEL_ID,
    GLINER_THRESHOLD,
    PRESIDIO_SCORE_THRESHOLD,
    _chunks,
    GLINER_CHUNK_CHARS,
    bootstrap_ratio_ci,
)
from propagation_suite import _load_documents, _measure_ai4privacy, _train_learned_detector  # noqa: E402

DOCUMENTS = EXPERIMENTS_DIR / "ai4privacy_operating_points_documents.csv"
SUMMARY = EXPERIMENTS_DIR / "ai4privacy_operating_points_summary.csv"
MATCHED = EXPERIMENTS_DIR / "ai4privacy_operating_points_matched.csv"
FIELDS = ["method_key", "threshold", "doc_id", "res_chars", "sens_chars", "kept_nonsens",
          "nonsens_chars", "span_tp", "span_pred"]
ANCHOR_FIELDS = ("res_chars", "sens_chars", "kept_nonsens", "nonsens_chars", "span_tp", "span_pred")
DEFAULTS = {"learned_lr": clf.DECISION_THRESHOLD, "presidio": PRESIDIO_SCORE_THRESHOLD, "gliner_pii": GLINER_THRESHOLD}
GRID = {
    "learned_lr": (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98, 0.99, 0.995),
    "presidio": (0.05, 0.2, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0),
    "gliner_pii": (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98),
}
RETENTION_LEVELS = (0.80, 0.90, 0.94, 0.96)


def _learned_scored(weights: dict[str, float]):
    """Token spans with the probability the tagger's decision rule compares."""
    def score(text: str) -> list[tuple[int, int, float]]:
        out = []
        tokens = clf._tokenize(text)
        for idx, (start, end, token) in enumerate(tokens):
            prev_token = tokens[idx - 1][2] if idx > 0 else None
            value = sum(weights.get(name, 0.0) for name in clf._token_features(token, prev_token))
            out.append((start, end, 1.0 / (1.0 + math.exp(-value))))
        return out
    return score


def _presidio_scored(spacy_model: str):
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    provider = NlpEngineProvider(
        nlp_configuration={"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": spacy_model}]})
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])

    def score(text: str) -> list[tuple[int, int, float]]:
        return [(r.start, r.end, float(r.score)) for r in analyzer.analyze(text=text, language="en", score_threshold=0.0)]
    return score


def _gliner_scored():
    from gliner import GLiNER

    model = GLiNER.from_pretrained(GLINER_MODEL_ID)

    def score(text: str) -> list[tuple[int, int, float]]:
        out = []
        for offset, chunk in _chunks(text, GLINER_CHUNK_CHARS):
            for ent in model.predict_entities(chunk, GLINER_LABELS, threshold=min(GRID["gliner_pii"])):
                out.append((offset + int(ent["start"]), offset + int(ent["end"]), float(ent["score"])))
        return out
    return score


def _anchor() -> dict[tuple[str, str], dict[str, str]]:
    records: dict[tuple[str, str], dict[str, str]] = {}
    for shard in EXPERIMENTS_DIR.glob("propagation_suite_ai4privacy_documents_v2_shard*of3.csv"):
        with shard.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                records[(row["method_key"], row["doc_id"])] = row
    return records


def _sweep(methods: list[str], docs: list[dict], spacy_model: str) -> None:
    done: set[tuple[str, str, str]] = set()
    if DOCUMENTS.exists():
        with DOCUMENTS.open(encoding="utf-8", newline="") as handle:
            done = {(r["method_key"], r["threshold"], r["doc_id"]) for r in csv.DictReader(handle)}
    write_header = not DOCUMENTS.exists() or DOCUMENTS.stat().st_size == 0
    with DOCUMENTS.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
            handle.flush()
        for method in methods:
            grid = GRID[method]
            remaining = [d for d in docs if any((method, str(t), d["doc_id"]) not in done for t in grid)]
            print(f"[{method}] {len(docs) - len(remaining)} documents done, {len(remaining)} to run", flush=True)
            if not remaining:
                continue
            if method == "learned_lr":
                scorer = _learned_scored(_train_learned_detector())
            elif method == "presidio":
                scorer = _presidio_scored(spacy_model)
            else:
                scorer = _gliner_scored()
            for n, doc in enumerate(remaining, 1):
                scored = scorer(doc["text"])
                for tau in grid:
                    if (method, str(tau), doc["doc_id"]) in done:
                        continue
                    spans = _merge_spans([(a, b) for a, b, s in scored if s >= tau])
                    counts = _measure_ai4privacy(doc, lambda _text, spans=spans: spans)
                    writer.writerow({"method_key": method, "threshold": tau, "doc_id": doc["doc_id"],
                                     **{k: counts[k] for k in ANCHOR_FIELDS}})
                handle.flush()
                os.fsync(handle.fileno())
                if n % 25 == 0:
                    print(f"  {method}: {n}/{len(remaining)}", flush=True)


def _summaries(methods: list[str], n_boot: int) -> int:
    with DOCUMENTS.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[tuple[str, float], list[dict[str, str]]] = collections.defaultdict(list)
    for row in rows:
        grouped[(row["method_key"], float(row["threshold"]))].append(row)

    anchor = _anchor()
    mismatches = 0
    for method in methods:
        default = DEFAULTS[method]
        for row in grouped.get((method, float(default)), []):
            recorded = anchor.get((method, row["doc_id"]))
            if recorded is None or any(int(recorded[k]) != int(row[k]) for k in ANCHOR_FIELDS):
                mismatches += 1
        print(f"[anchor] {method} at {default}: {len(grouped.get((method, float(default)), []))} documents, "
              f"cumulative mismatches {mismatches}", flush=True)
    if mismatches:
        print("[anchor] counts differ from the exposure-table records; summary not written", flush=True)
        return 1

    table: list[dict[str, object]] = []
    with SUMMARY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["method_key", "threshold", "is_default", "documents", "per_percent", "retention",
                         "span_precision", "per_point", "retention_point"])
        for (method, tau), sub in sorted(grouped.items()):
            per, plo, phi = bootstrap_ratio_ci([(float(r["res_chars"]), float(r["sens_chars"])) for r in sub],
                                               n_boot=n_boot, scale=100.0)
            ret, rlo, rhi = bootstrap_ratio_ci([(float(r["kept_nonsens"]), float(r["nonsens_chars"])) for r in sub],
                                               n_boot=n_boot, scale=1.0)
            pre, qlo, qhi = bootstrap_ratio_ci([(float(r["span_tp"]), float(r["span_pred"])) for r in sub],
                                               n_boot=n_boot, scale=1.0)
            writer.writerow([method, tau, int(tau == float(DEFAULTS[method])), len(sub),
                             f"{per:.1f} [{plo:.1f}, {phi:.1f}]", f"{ret:.3f} [{rlo:.3f}, {rhi:.3f}]",
                             f"{pre:.2f} [{qlo:.2f}, {qhi:.2f}]", f"{per:.2f}", f"{ret:.4f}"])
            table.append({"method": method, "tau": tau, "per": per, "ret": ret, "cell": f"{per:.1f} [{plo:.1f}, {phi:.1f}]"})

    by_doc = {key: {r["doc_id"]: r for r in sub} for key, sub in grouped.items()}
    with MATCHED.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["retention_at_least", "method_key", "threshold", "retention", "per_percent",
                         "learned_minus_this_points"])
        for level in RETENTION_LEVELS:
            chosen: dict[str, dict[str, object]] = {}
            for method in methods:
                options = [r for r in table if r["method"] == method and float(r["ret"]) >= level]
                if options:
                    chosen[method] = min(options, key=lambda r: float(r["per"]))
            learned = chosen.get("learned_lr")
            for method in methods:
                best = chosen.get(method)
                if best is None:
                    writer.writerow([level, method, "", "", "not reached on this grid", ""])
                    continue
                difference = ""
                if learned is not None and method != "learned_lr":
                    ours = by_doc[("learned_lr", float(learned["tau"]))]
                    theirs = by_doc[(method, float(best["tau"]))]
                    pairs = [(float(ours[d]["res_chars"]), float(ours[d]["sens_chars"]),
                              float(theirs[d]["res_chars"]), float(theirs[d]["sens_chars"])) for d in ours]
                    point, lo, hi = paired_bootstrap_diff(pairs, n_boot=n_boot, scale=100.0)
                    difference = f"{point:+.1f} [{lo:+.1f}, {hi:+.1f}]"
                writer.writerow([level, method, best["tau"], f"{float(best['ret']):.3f}", best["cell"], difference])
    print(f"[sweep] wrote {SUMMARY.name} and {MATCHED.name}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--methods", default="learned_lr,presidio,gliner_pii")
    parser.add_argument("--spacy-model", default="en_core_web_lg")
    parser.add_argument("--bootstrap", type=int, default=1000)
    args = parser.parse_args()
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    docs = _load_documents("ai4privacy", None)
    print(f"[sweep] {len(docs)} documents", flush=True)
    _sweep(methods, docs, args.spacy_model)
    return _summaries(methods, args.bootstrap)


if __name__ == "__main__":
    raise SystemExit(main())
