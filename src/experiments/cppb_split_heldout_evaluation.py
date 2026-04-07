#!/usr/bin/env python3
"""Aggregate split-specific CPPB held-out summaries from bundled prompt-level logs."""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
SPLIT_MANIFEST_PATH = EXPERIMENTS_DIR / "cppb_split_manifest.csv"
METHOD_LOGS_PATH = EXPERIMENTS_DIR / "multiseed_method_prompt_logs.csv"
POLICY_LOGS_PATH = EXPERIMENTS_DIR / "multiseed_policy_prompt_logs.csv"
METHOD_SEED_OUTPUT_PATH = EXPERIMENTS_DIR / "cppb_split_method_seed_metrics.csv"
METHOD_SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "cppb_split_method_summary.csv"
POLICY_SEED_OUTPUT_PATH = EXPERIMENTS_DIR / "cppb_split_policy_seed_metrics.csv"
POLICY_SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "cppb_split_policy_summary.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean_value = _mean(values)
    return math.sqrt(sum((value - mean_value) ** 2 for value in values) / (len(values) - 1))


def _ci95(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return 1.96 * _std(values) / math.sqrt(len(values))


def _split_maps(split_rows: list[dict[str, str]]) -> tuple[dict[str, str], dict[str, set[str]]]:
    prompt_to_split = {row["prompt_id"]: row["split"] for row in split_rows}
    split_to_templates: dict[str, set[str]] = defaultdict(set)
    for row in split_rows:
        split_to_templates[row["split"]].add(row["template_id"])
    return prompt_to_split, split_to_templates


def _aggregate_metric_logs(
    rows: list[dict[str, str]],
    group_field: str,
    utility_field: str,
    utility_label: str,
    prompt_to_split: dict[str, str],
    split_to_templates: dict[str, set[str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        split = prompt_to_split.get(row["prompt_id"])
        if split is None:
            continue
        grouped[(split, row[group_field], row["seed"])].append(row)

    seed_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, str]] = []
    summary_grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    for (split, group_name, seed), items in sorted(grouped.items()):
        per_percent = 100.0 * _mean([float(item["direct_exposure_score"]) for item in items])
        utility_value = _mean([float(item[utility_field]) for item in items])
        tsr_value = _mean([float(item["tsr_score"]) for item in items])
        seed_row = {
            "split": split,
            group_field: group_name,
            "seed": seed,
            "prompt_count": str(len(items)),
            "template_count": str(len(split_to_templates[split])),
            "per_percent": f"{per_percent:.4f}",
            utility_label: f"{utility_value:.4f}",
            "tsr": f"{tsr_value:.4f}",
        }
        seed_rows.append(seed_row)
        summary_grouped[(split, group_name)].append(seed_row)

    for (split, group_name), items in sorted(summary_grouped.items()):
        per_values = [float(item["per_percent"]) for item in items]
        utility_values = [float(item[utility_label]) for item in items]
        tsr_values = [float(item["tsr"]) for item in items]
        summary_rows.append(
            {
                "split": split,
                group_field: group_name,
                "seed_count": str(len(items)),
                "prompt_count": items[0]["prompt_count"],
                "template_count": items[0]["template_count"],
                "per_mean": f"{_mean(per_values):.4f}",
                "per_std": f"{_std(per_values):.4f}",
                "per_ci95": f"{_ci95(per_values):.4f}",
                f"{utility_label}_mean": f"{_mean(utility_values):.4f}",
                f"{utility_label}_std": f"{_std(utility_values):.4f}",
                f"{utility_label}_ci95": f"{_ci95(utility_values):.4f}",
                "tsr_mean": f"{_mean(tsr_values):.4f}",
                "tsr_std": f"{_std(tsr_values):.4f}",
                "tsr_ci95": f"{_ci95(tsr_values):.4f}",
                "notes": "Split-specific CPPB held-out reconstruction from bundled prompt-level multi-seed logs.",
            }
        )

    return seed_rows, summary_rows


def main() -> int:
    split_rows = _read_csv(SPLIT_MANIFEST_PATH)
    method_rows = _read_csv(METHOD_LOGS_PATH)
    policy_rows = _read_csv(POLICY_LOGS_PATH)
    prompt_to_split, split_to_templates = _split_maps(split_rows)

    method_seed_rows, method_summary_rows = _aggregate_metric_logs(
        method_rows,
        "setting",
        "ac_score",
        "ac",
        prompt_to_split,
        split_to_templates,
    )
    policy_seed_rows, policy_summary_rows = _aggregate_metric_logs(
        policy_rows,
        "profile",
        "upr_score",
        "upr",
        prompt_to_split,
        split_to_templates,
    )

    _write_csv(
        METHOD_SEED_OUTPUT_PATH,
        method_seed_rows,
        ["split", "setting", "seed", "prompt_count", "template_count", "per_percent", "ac", "tsr"],
    )
    _write_csv(
        METHOD_SUMMARY_OUTPUT_PATH,
        method_summary_rows,
        [
            "split",
            "setting",
            "seed_count",
            "prompt_count",
            "template_count",
            "per_mean",
            "per_std",
            "per_ci95",
            "ac_mean",
            "ac_std",
            "ac_ci95",
            "tsr_mean",
            "tsr_std",
            "tsr_ci95",
            "notes",
        ],
    )
    _write_csv(
        POLICY_SEED_OUTPUT_PATH,
        policy_seed_rows,
        ["split", "profile", "seed", "prompt_count", "template_count", "per_percent", "upr", "tsr"],
    )
    _write_csv(
        POLICY_SUMMARY_OUTPUT_PATH,
        policy_summary_rows,
        [
            "split",
            "profile",
            "seed_count",
            "prompt_count",
            "template_count",
            "per_mean",
            "per_std",
            "per_ci95",
            "upr_mean",
            "upr_std",
            "upr_ci95",
            "tsr_mean",
            "tsr_std",
            "tsr_ci95",
            "notes",
        ],
    )
    print(f"CPPB split method seed metrics written to {METHOD_SEED_OUTPUT_PATH}")
    print(f"CPPB split method summary written to {METHOD_SUMMARY_OUTPUT_PATH}")
    print(f"CPPB split policy seed metrics written to {POLICY_SEED_OUTPUT_PATH}")
    print(f"CPPB split policy summary written to {POLICY_SUMMARY_OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())