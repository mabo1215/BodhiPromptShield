#!/usr/bin/env python3
"""Paired document-level bootstrap tests of PER differences behind tab:measprop.

For each real source (AI4Privacy reference-agent documents and PrivacyLens
agent trajectories) every pair of methods in the propagation table is compared
on residual exact-identifier exposure (PER).  PER is the pooled ratio of
residual to sensitive gold characters, sum(res_chars) / sum(sens_chars), the
same aggregation the pooled records use; units that carry no gold span
contribute zero to both sums.

The test resamples documents (AI4Privacy) or tasks (PrivacyLens) with
replacement, 10,000 times with seed 17, and applies one draw to every method
at once, so each difference is paired on the same units.  The two-sided
bootstrap p-value is 2 * min(P(d* <= 0), P(d* >= 0)) with the add-one
correction, (count + 1) / (B + 1), capped at 1.  Holm's step-down correction is
applied across all pairs within each source.

Reads the per-document propagation shards exactly as aggregate_paper_results.py
pools them; nothing is rerun.  Writes one row per (source, pair) plus a
manifest that also records the per-source count of units without gold spans
and, for disclosure, each method's per-unit (macro) PER over the units that
carry gold next to the pooled PER the paper reports.

Usage:
    python propagation_paired_per_tests.py
"""
from __future__ import annotations

import csv
import itertools
import platform
from pathlib import Path

import numpy as np

from aggregate_paper_results import _read_shards

EXPERIMENTS_DIR = Path(__file__).resolve().parent
RESULTS_PATH = EXPERIMENTS_DIR / "propagation_paired_per_tests.csv"
MANIFEST_PATH = EXPERIMENTS_DIR / "propagation_paired_per_tests_manifest.csv"
SOURCES = ("ai4privacy", "privacylens")
N_BOOT = 10_000
SEED = 17
ALPHA = 0.05
# The rows of tab:measprop, by method key; the LLM sanitizer key carries its model tag.
METHODS = ("no_protection", "regex_only", "capitalization_heuristic", "spacy_ner", "presidio", "casper_style",
           "llm_sanitizer", "heuristic_mediator", "gliner_pii", "learned_lr")
FIELDS = ["source", "method_a", "method_b", "units", "per_a", "per_b", "diff_points", "diff_lo", "diff_hi",
          "p_bootstrap", "p_holm", "holm_reject_at_0.05", "resamples", "seed"]


def _matrices(source: str) -> tuple[list[str], list[str], np.ndarray, np.ndarray]:
    """Unit ids, method keys, and (units x methods) residual and sensitive character counts."""
    rows = _read_shards(f"propagation_suite_{source}_documents_shard*.csv")
    by_key: dict[str, dict[str, tuple[float, float]]] = {}
    for r in rows:
        key = r["method_key"].split(":")[0]
        if key in METHODS:
            by_key.setdefault(key, {})[r["doc_id"]] = (float(r["res_chars"]), float(r["sens_chars"]))
    keys = [k for k in METHODS if k in by_key]
    units = sorted(by_key[keys[0]])
    for k in keys:
        if sorted(by_key[k]) != units:
            raise ValueError(f"{source}: method {k} covers a different unit set")
    res = np.array([[by_key[k][u][0] for k in keys] for u in units])
    sens = np.array([[by_key[k][u][1] for k in keys] for u in units])
    return units, keys, res, sens


def _holm(pvalues: list[float]) -> list[float]:
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    m = len(pvalues)
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def run() -> None:
    out: list[dict[str, str]] = []
    manifest: dict[str, str] = {
        "per_aggregation": "pooled ratio sum(res_chars) / sum(sens_chars) over units, as in the pooled records",
        "resampling_unit": "document (AI4Privacy) / task (PrivacyLens), one draw shared by all methods (paired)",
        "resamples": str(N_BOOT), "seed": f"{SEED} (numpy default_rng)",
        "p_value": "two-sided bootstrap, 2 * min((#{d*<=0}+1)/(B+1), (#{d*>=0}+1)/(B+1)), capped at 1",
        "multiplicity": "Holm step-down across all method pairs within each source",
        "python": platform.python_version(), "numpy": np.__version__,
    }
    rng = np.random.default_rng(SEED)
    for source in SOURCES:
        units, keys, res, sens = _matrices(source)
        n = len(units)
        no_gold = int((sens[:, 0] == 0).sum())
        manifest[f"{source}.units"] = str(n)
        manifest[f"{source}.units_without_gold"] = str(no_gold)
        manifest[f"{source}.units_with_gold"] = str(n - no_gold)
        point = 100.0 * res.sum(axis=0) / sens.sum(axis=0)
        # Disclosure only: the per-unit (macro) average over units that carry gold.
        has_gold = sens[:, 0] > 0
        macro = 100.0 * (res[has_gold] / sens[has_gold]).mean(axis=0)
        for k, pooled, avg in zip(keys, point, macro):
            manifest[f"{source}.per_pooled.{k}"] = f"{pooled:.1f}"
            manifest[f"{source}.per_macro_over_gold_units.{k}"] = f"{avg:.1f}"
        # Multiplicity of every unit in every resample, then all methods' PERs per resample.
        counts = np.zeros((N_BOOT, n))
        draws = rng.integers(0, n, size=(N_BOOT, n))
        for b in range(N_BOOT):
            counts[b] = np.bincount(draws[b], minlength=n)
        boot = 100.0 * (counts @ res) / (counts @ sens)
        pairs = list(itertools.combinations(range(len(keys)), 2))
        stats = []
        for i, j in pairs:
            d = boot[:, i] - boot[:, j]
            lo, hi = np.percentile(d, [2.5, 97.5])
            p = min(1.0, 2.0 * min(((d <= 0).sum() + 1) / (N_BOOT + 1), ((d >= 0).sum() + 1) / (N_BOOT + 1)))
            stats.append((i, j, point[i] - point[j], lo, hi, p))
        adjusted = _holm([s[5] for s in stats])
        for (i, j, diff, lo, hi, p), p_holm in zip(stats, adjusted):
            out.append({
                "source": source, "method_a": keys[i], "method_b": keys[j], "units": str(n),
                "per_a": f"{point[i]:.1f}", "per_b": f"{point[j]:.1f}", "diff_points": f"{diff:.1f}",
                "diff_lo": f"{lo:.1f}", "diff_hi": f"{hi:.1f}", "p_bootstrap": f"{p:.4f}", "p_holm": f"{p_holm:.4f}",
                "holm_reject_at_0.05": str(p_holm < ALPHA), "resamples": str(N_BOOT), "seed": str(SEED),
            })
        manifest[f"{source}.pairs"] = str(len(pairs))
    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(out)
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "value"])
        writer.writeheader()
        writer.writerows({"field": k, "value": v} for k, v in manifest.items())
    print(f"Paired PER tests: {RESULTS_PATH}")
    for row in out:
        if "learned_lr" in (row["method_a"], row["method_b"]):
            print(f"  {row['source']:12s} {row['method_a']:25s} {row['method_b']:25s} d={row['diff_points']:>6} "
                  f"[{row['diff_lo']}, {row['diff_hi']}] p={row['p_bootstrap']} holm={row['p_holm']}")
    print(f"Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    run()
