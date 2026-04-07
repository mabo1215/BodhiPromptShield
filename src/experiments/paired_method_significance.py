#!/usr/bin/env python3
"""Summarize paired bootstrap comparisons across released multi-seed CPPB method logs.

This helper quantifies whether direct-exposure differences between selected
method pairs remain directionally stable under the released five-seed prompt-log
 surface. It reports bootstrap confidence intervals over paired prompt-seed
 differences in direct exposure score and writes a compact CSV summary for the
 manuscript.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
INPUT_PATH = EXPERIMENTS_DIR / "multiseed_method_prompt_logs.csv"
OUTPUT_PATH = EXPERIMENTS_DIR / "paired_method_significance.csv"
BOOTSTRAP_SAMPLES = 5000
BOOTSTRAP_SEED = 20260404

COMPARISONS = [
    (
        "Enterprise staged redaction",
        "Proposed (utility-constrained)",
        "Direct-PER trade-off between the strongest typed-placeholder baseline and the full utility-constrained setting.",
    ),
    (
        "Generic de-identification",
        "Enterprise staged redaction",
        "Direct-PER gain from moving beyond one-token generic redaction to a typed enterprise baseline.",
    ),
    (
        "Proposed (semantic abstraction)",
        "Proposed (utility-constrained)",
        "Direct-PER effect of adding utility-constrained policy routing on top of semantic abstraction.",
    ),
]


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _paired_series(rows: list[dict[str, str]], setting: str) -> dict[tuple[str, str], float]:
    paired: dict[tuple[str, str], float] = {}
    for row in rows:
        if row["setting"] != setting:
            continue
        key = (row["prompt_id"], row["seed"])
        paired[key] = float(row["direct_exposure_score"])
    return paired


def _bootstrap_summary(differences: list[float]) -> tuple[float, float, float, float]:
    rng = random.Random(BOOTSTRAP_SEED)
    boot_means: list[float] = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sample = [differences[rng.randrange(len(differences))] for _ in range(len(differences))]
        boot_means.append(sum(sample) / len(sample))
    boot_means.sort()
    mean_diff = sum(differences) / len(differences)
    ci_low = boot_means[int(0.025 * len(boot_means))]
    ci_high = boot_means[int(0.975 * len(boot_means))]
    prob_nonnegative = sum(1 for value in boot_means if value >= 0.0) / len(boot_means)
    return mean_diff, ci_low, ci_high, prob_nonnegative


def main() -> None:
    rows = _read_rows(INPUT_PATH)
    output_rows: list[dict[str, str]] = []
    for reference, comparator, interpretation in COMPARISONS:
        reference_series = _paired_series(rows, reference)
        comparator_series = _paired_series(rows, comparator)
        shared_keys = sorted(set(reference_series) & set(comparator_series))
        if not shared_keys:
            continue
        differences = [comparator_series[key] - reference_series[key] for key in shared_keys]
        mean_diff, ci_low, ci_high, prob_nonnegative = _bootstrap_summary(differences)
        output_rows.append(
            {
                "reference_method": reference,
                "comparator_method": comparator,
                "metric": "direct_exposure_score",
                "paired_units": str(len(shared_keys)),
                "mean_difference_pct_points": f"{100.0 * mean_diff:.3f}",
                "ci95_low_pct_points": f"{100.0 * ci_low:.3f}",
                "ci95_high_pct_points": f"{100.0 * ci_high:.3f}",
                "bootstrap_prob_difference_nonnegative": f"{prob_nonnegative:.4f}",
                "interpretation": interpretation,
            }
        )

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "reference_method",
                "comparator_method",
                "metric",
                "paired_units",
                "mean_difference_pct_points",
                "ci95_low_pct_points",
                "ci95_high_pct_points",
                "bootstrap_prob_difference_nonnegative",
                "interpretation",
            ],
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Wrote paired bootstrap summary to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()