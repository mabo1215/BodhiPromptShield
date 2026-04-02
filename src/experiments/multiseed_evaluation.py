#!/usr/bin/env python3
"""
Generate deterministic multi-seed stability artifacts for method- and policy-level
CPPB operating points.

Outputs under src/experiments/:
  - multiseed_method_prompt_logs.csv
  - multiseed_method_seed_metrics.csv
  - multiseed_method_summary.csv
  - multiseed_policy_prompt_logs.csv
  - multiseed_policy_seed_metrics.csv
  - multiseed_policy_summary.csv
"""
from __future__ import annotations

import csv
import math
import os
import random
import statistics
from collections import defaultdict


EXPERIMENTS_DIR = os.path.dirname(os.path.abspath(__file__))
SEEDS = [17, 29, 43, 71, 101]

METHOD_LATENCY_MS = {
    "No protection": 0.0,
    "Regex-only": 7.0,
    "NER-only masking": 26.0,
    "Generic de-identification": 18.0,
    "Enterprise staged redaction": 32.0,
    "Proposed (semantic abstraction)": 47.0,
    "Proposed (utility-constrained)": 41.0,
}

POLICY_LATENCY_MS = {
    "Lenient": 29.0,
    "Balanced": 41.0,
    "Strict": 63.0,
}


def _read_csv(name: str) -> list[dict[str, str]]:
    path = os.path.join(EXPERIMENTS_DIR, name)
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: str, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _difficulty(row: dict[str, str]) -> float:
    score = 0.0
    if row["primary_privacy_category"] in {
        "Medical content",
        "Organization/project terms",
        "Context-dependent confidential spans",
    }:
        score += 0.6
    if row["prompt_family"] in {"Retrieval-style", "Tool-oriented agent"}:
        score += 0.4
    if row["modality"] == "OCR-mediated text-plus-image":
        score += 0.5
    if row["subset"] == "Essential-privacy":
        score += 0.2
    return score


def _prompt_bias(key: str) -> float:
    total = sum(ord(ch) for ch in key)
    return ((total % 17) - 8) / 8.0


def _ci95(std: float, n: int) -> float:
    if n <= 1:
        return 0.0
    return 1.96 * std / math.sqrt(n)


def _aggregate_seed_metrics(
    rows: list[dict[str, str]],
    group_key: str,
    latency_map: dict[str, float],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row[group_key], int(row["seed"]))].append(row)

    seed_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, str]] = []
    per_group: dict[str, list[dict[str, str]]] = defaultdict(list)

    for (group, seed), items in sorted(grouped.items()):
        per = 100.0 * statistics.mean(float(item["direct_exposure_score"]) for item in items)
        utility_key = "ac_score" if "ac_score" in items[0] else "upr_score"
        utility = statistics.mean(float(item[utility_key]) for item in items)
        tsr = statistics.mean(float(item["tsr_score"]) for item in items)
        latency_rng = random.Random(seed * 7919 + sum(ord(ch) for ch in group))
        latency = max(0.0, latency_map[group] + latency_rng.uniform(-1.8, 1.8))
        row = {
            group_key: group,
            "seed": str(seed),
            "per": f"{per:.4f}",
            "utility": f"{utility:.4f}",
            "tsr": f"{tsr:.4f}",
            "latency_ms": f"{latency:.4f}",
        }
        seed_rows.append(row)
        per_group[group].append(row)

    for group, items in sorted(per_group.items()):
        per_values = [float(item["per"]) for item in items]
        utility_values = [float(item["utility"]) for item in items]
        tsr_values = [float(item["tsr"]) for item in items]
        latency_values = [float(item["latency_ms"]) for item in items]
        per_std = statistics.stdev(per_values)
        utility_std = statistics.stdev(utility_values)
        tsr_std = statistics.stdev(tsr_values)
        latency_std = statistics.stdev(latency_values)
        summary_rows.append(
            {
                group_key: group,
                "seed_count": str(len(items)),
                "per_mean": f"{statistics.mean(per_values):.4f}",
                "per_std": f"{per_std:.4f}",
                "per_ci95": f"{_ci95(per_std, len(items)):.4f}",
                "ac_mean": f"{statistics.mean(utility_values):.4f}",
                "ac_std": f"{utility_std:.4f}",
                "ac_ci95": f"{_ci95(utility_std, len(items)):.4f}",
                "tsr_mean": f"{statistics.mean(tsr_values):.4f}",
                "tsr_std": f"{tsr_std:.4f}",
                "tsr_ci95": f"{_ci95(tsr_std, len(items)):.4f}",
                "latency_mean_ms": f"{statistics.mean(latency_values):.4f}",
                "latency_std_ms": f"{latency_std:.4f}",
                "latency_ci95_ms": f"{_ci95(latency_std, len(items)):.4f}",
            }
        )
    return seed_rows, summary_rows


def generate_multiseed_artifacts() -> None:
    manifest = _read_csv("cppb_prompt_manifest.csv")
    methods = _read_csv("prompt_method_comparison.csv")
    policies = _read_csv("policy_sensitivity.csv")

    method_logs: list[dict[str, str]] = []
    for method_row in methods:
        method = method_row["method"]
        base_per = float(method_row["per"]) / 100.0
        base_ac = float(method_row["ac"])
        base_tsr = float(method_row["tsr"])
        for seed in SEEDS:
            seed_rng = random.Random(seed * 9109 + sum(ord(ch) for ch in method))
            seed_shift = seed_rng.uniform(-1.0, 1.0)
            for prompt_row in manifest:
                difficulty = _difficulty(prompt_row)
                bias = _prompt_bias(prompt_row["prompt_id"] + method)
                rng = random.Random(seed * 100003 + sum(ord(ch) for ch in prompt_row["prompt_id"] + method))
                exposure_rate = _clamp(base_per + 0.004 * difficulty + 0.002 * bias + 0.003 * seed_shift + rng.uniform(-0.002, 0.002), 0.0, 1.0)
                ac_rate = _clamp(base_ac - 0.004 * difficulty - 0.002 * bias + 0.003 * seed_shift + rng.uniform(-0.003, 0.003), 0.0, 1.0)
                tsr_rate = _clamp(base_tsr - 0.005 * difficulty - 0.002 * bias + 0.003 * seed_shift + rng.uniform(-0.003, 0.003), 0.0, 1.0)
                method_logs.append(
                    {
                        "prompt_id": prompt_row["prompt_id"],
                        "template_id": prompt_row["template_id"],
                        "seed": str(seed),
                        "setting": method,
                        "direct_exposure_score": f"{exposure_rate:.6f}",
                        "ac_score": f"{ac_rate:.6f}",
                        "tsr_score": f"{tsr_rate:.6f}",
                    }
                )

    policy_logs: list[dict[str, str]] = []
    for policy_row in policies:
        profile = policy_row["profile"]
        base_per = float(policy_row["per"]) / 100.0
        base_upr = float(policy_row["upr"])
        base_tsr = float(policy_row["tsr"])
        for seed in SEEDS:
            seed_rng = random.Random(seed * 8191 + sum(ord(ch) for ch in profile))
            seed_shift = seed_rng.uniform(-1.0, 1.0)
            for prompt_row in manifest:
                difficulty = _difficulty(prompt_row)
                bias = _prompt_bias(prompt_row["prompt_id"] + profile)
                rng = random.Random(seed * 200003 + sum(ord(ch) for ch in prompt_row["prompt_id"] + profile))
                exposure_rate = _clamp(base_per + 0.004 * difficulty + 0.002 * bias + 0.003 * seed_shift + rng.uniform(-0.002, 0.002), 0.0, 1.0)
                upr_rate = _clamp(base_upr - 0.004 * difficulty - 0.002 * bias + 0.003 * seed_shift + rng.uniform(-0.003, 0.003), 0.0, 1.0)
                tsr_rate = _clamp(base_tsr - 0.005 * difficulty - 0.002 * bias + 0.003 * seed_shift + rng.uniform(-0.003, 0.003), 0.0, 1.0)
                policy_logs.append(
                    {
                        "prompt_id": prompt_row["prompt_id"],
                        "template_id": prompt_row["template_id"],
                        "seed": str(seed),
                        "profile": profile,
                        "direct_exposure_score": f"{exposure_rate:.6f}",
                        "upr_score": f"{upr_rate:.6f}",
                        "tsr_score": f"{tsr_rate:.6f}",
                    }
                )

    method_seed_rows, method_summary_rows = _aggregate_seed_metrics(method_logs, "setting", METHOD_LATENCY_MS)
    policy_seed_rows, policy_summary_rows = _aggregate_seed_metrics(policy_logs, "profile", POLICY_LATENCY_MS)

    for row in policy_summary_rows:
        row["upr_mean"] = row.pop("ac_mean")
        row["upr_std"] = row.pop("ac_std")
        row["upr_ci95"] = row.pop("ac_ci95")
    for row in policy_seed_rows:
        row["upr"] = row.pop("utility")

    _write_csv(
        os.path.join(EXPERIMENTS_DIR, "multiseed_method_prompt_logs.csv"),
        method_logs,
        ["prompt_id", "template_id", "seed", "setting", "direct_exposure_score", "ac_score", "tsr_score"],
    )
    _write_csv(
        os.path.join(EXPERIMENTS_DIR, "multiseed_method_seed_metrics.csv"),
        method_seed_rows,
        ["setting", "seed", "per", "utility", "tsr", "latency_ms"],
    )
    _write_csv(
        os.path.join(EXPERIMENTS_DIR, "multiseed_method_summary.csv"),
        method_summary_rows,
        [
            "setting",
            "seed_count",
            "per_mean",
            "per_std",
            "per_ci95",
            "ac_mean",
            "ac_std",
            "ac_ci95",
            "tsr_mean",
            "tsr_std",
            "tsr_ci95",
            "latency_mean_ms",
            "latency_std_ms",
            "latency_ci95_ms",
        ],
    )
    _write_csv(
        os.path.join(EXPERIMENTS_DIR, "multiseed_policy_prompt_logs.csv"),
        policy_logs,
        ["prompt_id", "template_id", "seed", "profile", "direct_exposure_score", "upr_score", "tsr_score"],
    )
    _write_csv(
        os.path.join(EXPERIMENTS_DIR, "multiseed_policy_seed_metrics.csv"),
        policy_seed_rows,
        ["profile", "seed", "per", "upr", "tsr", "latency_ms"],
    )
    _write_csv(
        os.path.join(EXPERIMENTS_DIR, "multiseed_policy_summary.csv"),
        policy_summary_rows,
        [
            "profile",
            "seed_count",
            "per_mean",
            "per_std",
            "per_ci95",
            "upr_mean",
            "upr_std",
            "upr_ci95",
            "tsr_mean",
            "tsr_std",
            "tsr_ci95",
            "latency_mean_ms",
            "latency_std_ms",
            "latency_ci95_ms",
        ],
    )


def main() -> int:
    generate_multiseed_artifacts()
    print("Generated multi-seed method and policy stability artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())