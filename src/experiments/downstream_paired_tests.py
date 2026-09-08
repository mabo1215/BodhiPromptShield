"""Paired tests for the PrivacyLens downstream conditions against no_protection.

The pooled summary reports each condition's marginal rate with its own bootstrap
interval.  Reading two marginal intervals for overlap is a conservative and
underpowered test here, because every condition is evaluated on the *same* 200
cases: the pairing is thrown away.  This script keeps it.  For each mediated
condition it compares the per-case outcome with the same case's outcome under
no_protection, and reports

  * McNemar's exact two-sided test on the judge's binary leak verdict, which
    conditions on the discordant pairs only,
  * a paired bootstrap interval for the difference in rate, resampling cases
    (not rows) so that both arms of a pair move together, and
  * Holm-Bonferroni adjustment across the conditions compared within one agent
    model, since each arm tests eight of them against a shared control.

Helpfulness and exact-identifier exposure get the same paired bootstrap so that
a privacy change and its utility cost are read off the same resamples.

Usage:
    python downstream_paired_tests.py [agent_model ...]
"""

from __future__ import annotations

import random
import sys
from math import comb
from pathlib import Path

from aggregate_paper_results import _read_shards, _write

EXPERIMENTS_DIR = Path(__file__).resolve().parent
N_BOOT = 1000
SEED = 17
CONTROL = "no_protection"
DEFAULT_MODELS = ["qwen3_32b-q4km-hf", "llama3.3_70b-q4km-hf"]


def mcnemar_exact_p(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the two discordant-pair counts.

    Under the null the discordant pairs split by a fair coin, so the tail
    probability is binomial with p=0.5 on b+c trials.  Doubling the smaller
    tail is the standard two-sided form; it is capped because the doubled
    tail can exceed 1 when b and c are nearly equal.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2.0**n)
    return min(1.0, 2.0 * tail)


def holm(pvalues: list[float]) -> list[float]:
    """Holm-Bonferroni step-down adjustment, preserving input order."""
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted = [0.0] * len(pvalues)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (len(pvalues) - rank) * pvalues[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted


def paired_bootstrap_diff(pairs: list[tuple[float, float, float, float]],
                          n_boot: int = N_BOOT, scale: float = 1.0) -> tuple[float, float, float]:
    """Bootstrap the difference of two ratio estimators over paired cases.

    Each entry is (treated_num, treated_den, control_num, control_den) for one
    case.  Cases are resampled as units so a case contributes to both arms or
    to neither, which is what makes the interval a paired one.
    """
    def ratio_diff(sample: list[tuple[float, float, float, float]]) -> float:
        tn = sum(p[0] for p in sample)
        td = sum(p[1] for p in sample)
        cn = sum(p[2] for p in sample)
        cd = sum(p[3] for p in sample)
        treated = tn / td if td else 0.0
        control = cn / cd if cd else 0.0
        return (treated - control) * scale

    point = ratio_diff(pairs)
    rng = random.Random(SEED)
    n = len(pairs)
    draws = []
    for _ in range(n_boot):
        draws.append(ratio_diff([pairs[rng.randrange(n)] for _ in range(n)]))
    draws.sort()
    lo = draws[int(0.025 * n_boot)]
    hi = draws[int(0.975 * n_boot) - 1]
    return point, lo, hi


def _fmt(point: float, lo: float, hi: float, digits: int) -> str:
    return f"{point:+.{digits}f} [{lo:+.{digits}f}, {hi:+.{digits}f}]"


def paired_tests(agent_model: str) -> Path:
    """Compare every mediated condition with no_protection on matched cases."""
    rows = _read_shards(f"privacylens_downstream_rows_{agent_model}_shard*of*.csv")
    if not rows:
        raise SystemExit(f"no downstream shards found for {agent_model}")

    by_condition: dict[str, dict[str, dict]] = {}
    order: list[str] = []
    for row in rows:
        cond = row["condition"]
        if cond not in by_condition:
            by_condition[cond] = {}
            order.append(cond)
        by_condition[cond][row["case"]] = row
    if CONTROL not in by_condition:
        raise SystemExit(f"{agent_model}: no {CONTROL} rows to compare against")

    control = by_condition[CONTROL]
    out: list[dict] = []
    raw_p: list[float] = []

    for cond in order:
        if cond == CONTROL:
            continue
        treated = by_condition[cond]
        cases = sorted(set(treated) & set(control))
        if not cases:
            continue

        # Judge's binary leak verdict: b and c are the pairs that disagree.
        b = sum(1 for k in cases if int(treated[k]["leak_any"]) == 0 and int(control[k]["leak_any"]) == 1)
        c = sum(1 for k in cases if int(treated[k]["leak_any"]) == 1 and int(control[k]["leak_any"]) == 0)
        p = mcnemar_exact_p(b, c)
        raw_p.append(p)

        leak = paired_bootstrap_diff(
            [(float(treated[k]["leak_any"]), 1.0, float(control[k]["leak_any"]), 1.0) for k in cases],
            scale=100.0)
        ids = paired_bootstrap_diff(
            [(float(treated[k]["ids_in_final_action"]), float(treated[k]["ids_total"]),
              float(control[k]["ids_in_final_action"]), float(control[k]["ids_total"])) for k in cases],
            scale=100.0)
        helpful = paired_bootstrap_diff(
            [(float(treated[k]["helpfulness"]), 1.0, float(control[k]["helpfulness"]), 1.0) for k in cases])

        out.append({
            "condition": cond,
            "paired_cases": str(len(cases)),
            "leak_rate_diff_points": _fmt(*leak, 1),
            "mcnemar_discordant_b_c": f"{b}/{c}",
            "mcnemar_p": f"{p:.4f}",
            "mcnemar_p_holm": "",
            "exact_id_exposure_diff_points": _fmt(*ids, 1),
            "helpfulness_diff": _fmt(*helpful, 2),
        })

    for row, adj in zip(out, holm(raw_p)):
        row["mcnemar_p_holm"] = f"{adj:.4f}"

    path = EXPERIMENTS_DIR / f"downstream_paired_tests_{agent_model}.csv"
    _write(path, out)
    return path


def main(argv: list[str]) -> int:
    for model in (argv[1:] or DEFAULT_MODELS):
        print(f"\n=== {model} (control: {CONTROL}) ===")
        paired_tests(model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
