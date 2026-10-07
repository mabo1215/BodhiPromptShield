#!/usr/bin/env python3
"""Paired comparison of late against true early symbolic restoration on the same cases.

``downstream_paired_tests.py`` compares every mediated condition with the
unprotected control. The restoration-timing claim is a different pair: the two
symbolic-mapping arms share detector, mapping and cases and differ only in when
values are restored, so the comparison that carries the claim is late against
early, paired on the case. This script computes that pair from the released
per-case rows and nothing else, so that every restoration-timing number in the
manuscript can be regenerated with one command:

  * the paired difference in the pre-restoration exact-identifier rate (gold
    identifiers in the action as the agent wrote it, before any boundary
    restoration), as a ratio of sums over resampled cases;
  * McNemar's exact test on whether an action carried any such identifier;
  * the paired differences in judge-scored leak rate and helpfulness, and in
    the post-restoration identifier rate, on the same resamples.

The bootstrap resamples cases as units with the repository's fixed seed, so the
intervals here are the ones the other paired tables use; nothing is typed in.

Usage:
    python restoration_timing_paired_tests.py [agent_model ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

from aggregate_paper_results import _write, read_downstream_rows
from downstream_paired_tests import DEFAULT_MODELS, mcnemar_exact_p, paired_bootstrap_diff

EXPERIMENTS_DIR = Path(__file__).resolve().parent
LATE_PREFIX = "symbolic_late"
# The true early arm: every value is restored before planning, so the agent
# reads no token at all. (The earlier symbolic_early arm restored the
# trajectory only, and its rows are retired; see aggregate_paper_results.)
EARLY_PREFIX = "symbolic_fullearly"


def _fmt(point: float, lo: float, hi: float, digits: int) -> str:
    return f"{point:+.{digits}f} [{lo:+.{digits}f}, {hi:+.{digits}f}]"


def _arm(rows: list[dict], prefix: str) -> tuple[str, dict[str, dict]]:
    conditions = sorted({r["condition"] for r in rows if r["condition"].split(":")[0] == prefix})
    if len(conditions) != 1:
        raise SystemExit(f"expected exactly one {prefix} condition, found {conditions}")
    return conditions[0], {r["case"]: r for r in rows if r["condition"] == conditions[0]}


def paired_tests(agent_model: str) -> Path:
    rows = read_downstream_rows(agent_model)
    if not rows:
        raise SystemExit(f"no downstream shards found for {agent_model}")
    late_name, late = _arm(rows, LATE_PREFIX)
    early_name, early = _arm(rows, EARLY_PREFIX)
    cases = sorted(set(late) & set(early))
    if not cases:
        raise SystemExit(f"{agent_model}: no shared cases between {late_name} and {early_name}")

    def pairs(field: str, denominator: str | None) -> list[tuple[float, float, float, float]]:
        return [(float(late[k][field]), float(late[k][denominator]) if denominator else 1.0,
                 float(early[k][field]), float(early[k][denominator]) if denominator else 1.0) for k in cases]

    pre = paired_bootstrap_diff(pairs("ids_in_output", "ids_total"), scale=100.0)
    post = paired_bootstrap_diff(pairs("ids_in_final_action", "ids_total"), scale=100.0)
    leak = paired_bootstrap_diff(pairs("leak_any", None), scale=100.0)
    helpful = paired_bootstrap_diff(pairs("helpfulness", None))

    def any_pre(row: dict) -> int:
        return int(int(row["ids_in_output"]) > 0)

    b = sum(1 for k in cases if any_pre(late[k]) == 0 and any_pre(early[k]) == 1)
    c = sum(1 for k in cases if any_pre(late[k]) == 1 and any_pre(early[k]) == 0)
    late_any = 100.0 * sum(any_pre(late[k]) for k in cases) / len(cases)
    early_any = 100.0 * sum(any_pre(early[k]) for k in cases) / len(cases)
    late_tokens = sum(int(late[k]["tokens_in_output"]) for k in cases) / len(cases)
    early_tokens = sum(int(early[k]["tokens_in_output"]) for k in cases) / len(cases)

    out = [{
        "agent_model": agent_model,
        "late_condition": late_name,
        "early_condition": early_name,
        "paired_cases": str(len(cases)),
        "pre_restoration_id_exposure_diff_points": _fmt(*pre, 1),
        "actions_with_pre_restoration_id_late_vs_early_percent": f"{late_any:.1f} vs {early_any:.1f}",
        "mcnemar_discordant_late_only_early_only": f"{c}/{b}",
        "mcnemar_p": f"{mcnemar_exact_p(b, c):.4f}",
        "post_restoration_id_exposure_diff_points": _fmt(*post, 1),
        "leak_rate_diff_points": _fmt(*leak, 1),
        "helpfulness_diff_late_minus_early": _fmt(*helpful, 2),
        "unrestored_tokens_per_action_late_vs_early": f"{late_tokens:.2f} vs {early_tokens:.2f}",
    }]
    path = EXPERIMENTS_DIR / f"restoration_timing_paired_tests_{agent_model}.csv"
    _write(path, out)
    for key, value in out[0].items():
        print(f"  {key:52s} {value}")
    return path


def main(argv: list[str]) -> int:
    for model in (argv[1:] or DEFAULT_MODELS):
        print(f"\n=== {model}: {LATE_PREFIX} vs {EARLY_PREFIX}, paired on case ===")
        paired_tests(model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
