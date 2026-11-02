#!/usr/bin/env python3
"""Split the pooled AgentDojo prompt-injection result by suite.

The reported injection result pools banking and slack (74 task/injection
pairs, exfiltration-shaped injections only) under the repaired harness (output
tag ``_fixed``). This script first rebuilds the pooled numbers from the shipped
rows, with the same estimators as ``aggregate_paper_results.pool_agentdojo_injections``
(whole (suite, user task) clusters resampled, 1,000 resamples, seed 17; exact
task-level sign-flip p-value for the paired difference), and then reports the
same quantities per suite and per (suite, injection task):

* attack success rate (AgentDojo's ``security`` flag) and utility, with pair
  and user-task counts;
* the paired change in attack success and in utility against no protection,
  over the identical task/injection pairs, with discordant-pair counts;
* the same attack success rate and paired change restricted to the pairs in
  which the layer had a protected value (a value detected in the user prompt);
* the exact payload class of successful attacks (raw protected value, tokens
  only, unprotected data only, no protected value), which the repaired harness
  records per pair.

Reads records only; nothing is rerun and no model is called.

Output, next to the records:
``agentdojo_injection_per_suite_qwen3_32b-q4km-hf_fixed.csv``
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENTS_DIR))

# Stdlib-only helpers shared with the script that wrote the pooled summary.
from aggregate_paper_results import (  # noqa: E402
    AGENTDOJO_EXFIL_CLASSES, _read_agentdojo_mixed, _signflip_p, _task_ci)
from mediation_baselines import bootstrap_ratio_ci  # noqa: E402

AGENT = "qwen3_32b-q4km-hf"
SUFFIX = "_fixed"
SUITES = ("banking", "slack")
ARMS = {"unprotected": "inj_none", "unrestricted": "inj_all", "user_directed": "inj_scoped"}
N_BOOT = 1000
OUT_PATH = EXPERIMENTS_DIR / f"agentdojo_injection_per_suite_{AGENT}{SUFFIX}.csv"


def arm_rows() -> dict[str, list[dict]]:
    arms: dict[str, list[dict]] = {arm: [] for arm in ARMS}
    for suite in SUITES:
        for arm, tag in ARMS.items():
            path = EXPERIMENTS_DIR / f"agentdojo_restoration_rows_{suite}_{AGENT}_{tag}{SUFFIX}.csv"
            arms[arm] += [r for r in _read_agentdojo_mixed(path) if r.get("injection_task")]
    return arms


def paired(base_rows: list[dict], arm_rows_: list[dict], field: str) -> dict[str, str]:
    """Paired arm-minus-baseline difference of ``field``, clustered by (suite, task)."""
    base = {(r["suite"], r["task"], r["injection_task"]): float(r[field]) for r in base_rows}
    other = {(r["suite"], r["task"], r["injection_task"]): float(r[field]) for r in arm_rows_}
    shared = sorted(set(base) & set(other))
    if not shared:
        return {}
    clusters: dict[tuple[str, str], list[float]] = {}
    for k in shared:
        acc = clusters.setdefault(k[:2], [0.0, 0.0])
        acc[0] += other[k] - base[k]
        acc[1] += 1.0
    point, lo, hi = bootstrap_ratio_ci([tuple(v) for v in clusters.values()], n_boot=N_BOOT, scale=100.0)
    nonzero = [v[0] for v in clusters.values() if v[0] != 0]
    p = f"{_signflip_p([v[0] for v in clusters.values()]):.3f}" if len(nonzero) <= 22 else "n/a"
    return {
        "paired_n": str(len(shared)),
        "paired_tasks": str(len(clusters)),
        "delta": f"{point:+.1f} [{lo:+.1f}, {hi:+.1f}]",
        "signflip_p": p,
        "arm_only": str(sum(1 for k in shared if other[k] > base[k])),
        "baseline_only": str(sum(1 for k in shared if other[k] < base[k])),
    }


def summarize(scope: str, arm: str, rows: list[dict], base_rows: list[dict]) -> dict[str, str]:
    successful = [r for r in rows if r["security"] == "1"]
    out = {
        "scope": scope,
        "arm": arm,
        "pairs": str(len(rows)),
        "user_tasks": str(len({(r["suite"], r["task"]) for r in rows})),
        "successful_attacks": str(len(successful)),
        "attack_success_percent": _task_ci(rows, "security", None, 100.0, 1),
        "utility_successes": str(sum(1 for r in rows if r["utility"] == "1")),
        "utility_percent": _task_ci(rows, "utility", None, 100.0, 1),
    }
    for cls in AGENTDOJO_EXFIL_CLASSES:
        out[f"successful_{cls}"] = str(sum(1 for r in successful if r["exfil_class"] == cls))
    # Pairs where the layer had something to protect (a value detected in the
    # user prompt); on the others a data-plane layer cannot change the payload.
    protected = [r for r in rows if int(r["protected_values"]) > 0]
    out["pairs_with_protected_values"] = str(len(protected))
    out["attack_success_percent_protected_pairs"] = (
        _task_ci(protected, "security", None, 100.0, 1) if protected else "")
    base_protected = [r for r in base_rows if int(r["protected_values"]) > 0]
    result = paired(base_protected, protected, "security") if arm != "unprotected" and protected else {}
    out["paired_asr_delta_vs_unprotected_pp_protected_pairs"] = result.get("delta", "")
    out["paired_asr_n_protected_pairs"] = result.get("paired_n", "")
    for field, label in (("security", "asr"), ("utility", "utility")):
        result = paired(base_rows, rows, field) if arm != "unprotected" else {}
        out[f"paired_{label}_n"] = result.get("paired_n", "")
        out[f"paired_{label}_tasks"] = result.get("paired_tasks", "")
        out[f"paired_{label}_delta_vs_unprotected_pp"] = result.get("delta", "")
        out[f"paired_{label}_task_signflip_p"] = result.get("signflip_p", "")
        out[f"paired_{label}_pairs_up"] = result.get("arm_only", "")
        out[f"paired_{label}_pairs_down"] = result.get("baseline_only", "")
    return out


def main() -> int:
    arms = arm_rows()
    scopes: list[tuple[str, callable]] = [("pooled", lambda r: True)]
    for suite in SUITES:
        scopes.append((suite, lambda r, s=suite: r["suite"] == s))
    for suite in SUITES:
        tasks = sorted({r["injection_task"] for r in arms["unprotected"] if r["suite"] == suite})
        for task in tasks:
            scopes.append((f"{suite}/{task}",
                           lambda r, s=suite, t=task: r["suite"] == s and r["injection_task"] == t))
    out = []
    for scope, keep in scopes:
        base = [r for r in arms["unprotected"] if keep(r)]
        for arm, rows in arms.items():
            out.append(summarize(scope, arm, [r for r in rows if keep(r)], base))
    with OUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out[0].keys()))
        writer.writeheader()
        writer.writerows(out)
    for row in out:
        print(f"  {row['scope']:<26} {row['arm']:<14} n={row['pairs']:>3} tasks={row['user_tasks']:>2} "
              f"ASR {row['attack_success_percent']:<20} util {row['utility_percent']:<20} "
              f"dASR {row['paired_asr_delta_vs_unprotected_pp']:<22} p={row['paired_asr_task_signflip_p']}")
    print(f"wrote {OUT_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
