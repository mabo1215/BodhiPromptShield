#!/usr/bin/env python3
"""Bounds on raw-value exfiltration among successful AgentDojo injections.

The injection rows record, per task/injection pair and arm, AgentDojo's attack
success judgement (``security``) and counts about the layer's protected values
(the values detected in the user prompt): how many there were, how many were
visible in raw form anywhere in the text the agent read (tool outputs
included), how many tokens reached tool arguments, and how many of those the
boundary restored or refused.  The rows do not keep the tool-call arguments, so
the content of the attacker-directed call cannot be read back.  What the counts
do decide is whether a raw protected value *could* have been in any tool-call
payload of a run:

* ``no_protected_value``: the run had no protected value at all, so whatever
  the attack stole was not a value the layer protects;
* ``raw_impossible``: protected values existed, none was ever visible raw to
  the agent, and the boundary restored none into any tool argument, so no
  payload of the run can contain a raw protected value; it can carry tokens
  or data the layer does not protect;
* ``raw_possible``: a raw protected value was visible to the agent or was
  restored into some tool argument, so the payload may contain it; the rows
  cannot say whether it did.

Per arm, over successful attacks, ``raw_possible`` is therefore an upper bound
on raw-value exfiltration and ``no_protected_value + raw_impossible`` a lower
bound on exfiltration of placeholders or unprotected data only.  Turning the
bound into an exact rate needs the per-call arguments of the attacker-directed
tool calls, which these runs did not write.

The pairs are exactly those pooled in the injection summary (exfiltration-
shaped injections on banking and slack).  Reads records only; nothing is rerun.

Usage:
    python agentdojo_payload_bounds.py
"""
from __future__ import annotations

import csv
from pathlib import Path

from aggregate_paper_results import _read_agentdojo_mixed

EXPERIMENTS_DIR = Path(__file__).resolve().parent
AGENT = "qwen3_32b-q4km-hf"
SUITES = ("banking", "slack")
OUT_PATH = EXPERIMENTS_DIR / f"agentdojo_injection_payload_bounds_{AGENT}.csv"
FIELDS = ["arm", "suite", "pairs", "successful_attacks", "no_protected_value", "raw_impossible", "raw_possible",
          "raw_possible_visible", "raw_possible_restored_only", "successful_with_tokens_in_tool_args",
          "successful_with_refused_restoration", "raw_exfiltration_upper_bound_percent",
          "placeholder_or_unprotected_lower_bound_percent"]


def _arm_rows() -> dict[str, list[dict]]:
    """The pooled injection pairs per arm, located exactly as pool_agentdojo_injections locates them."""
    arms: dict[str, list[dict]] = {"unprotected": [], "unrestricted": [], "user_directed": []}
    for suite in SUITES:
        def read(path: Path, baseline: bool = False) -> list[dict]:
            if not path.exists():
                return []
            rows = [r for r in _read_agentdojo_mixed(path) if r.get("injection_task")]
            return [r for r in rows if r["mode"] == "none"] if baseline else rows

        inj_none = EXPERIMENTS_DIR / f"agentdojo_restoration_rows_{suite}_{AGENT}_inj_none.csv"
        arms["unprotected"] += read(inj_none) if inj_none.exists() else \
            read(EXPERIMENTS_DIR / f"agentdojo_restoration_rows_{suite}_{AGENT}.csv", baseline=True)
        arms["unrestricted"] += read(EXPERIMENTS_DIR / f"agentdojo_restoration_rows_{suite}_{AGENT}_inj_all.csv")
        arms["user_directed"] += read(EXPERIMENTS_DIR / f"agentdojo_restoration_rows_{suite}_{AGENT}_inj_scoped.csv")
    return arms


def _summarize(arm: str, suite: str, rows: list[dict]) -> dict[str, str]:
    won = [r for r in rows if int(r["security"])]
    none = [r for r in won if int(r["protected_values"]) == 0]
    rest = [r for r in won if int(r["protected_values"]) > 0]
    visible = [r for r in rest if int(r["raw_visible_before_tool"]) > 0]
    restored_only = [r for r in rest if int(r["raw_visible_before_tool"]) == 0 and int(r["restored_in_tool_args"]) > 0]
    impossible = [r for r in rest if int(r["raw_visible_before_tool"]) == 0 and int(r["restored_in_tool_args"]) == 0]
    possible = len(visible) + len(restored_only)
    n = len(won)
    return {
        "arm": arm, "suite": suite, "pairs": str(len(rows)), "successful_attacks": str(n),
        "no_protected_value": str(len(none)), "raw_impossible": str(len(impossible)), "raw_possible": str(possible),
        "raw_possible_visible": str(len(visible)), "raw_possible_restored_only": str(len(restored_only)),
        "successful_with_tokens_in_tool_args": str(sum(1 for r in won if int(r["tokens_emitted_in_tool_args"]) > 0)),
        "successful_with_refused_restoration": str(sum(1 for r in won if int(r["refused_unscoped_restorations"]) > 0)),
        "raw_exfiltration_upper_bound_percent": f"{100.0 * possible / n:.1f}" if n else "n/a",
        "placeholder_or_unprotected_lower_bound_percent": f"{100.0 * (len(none) + len(impossible)) / n:.1f}" if n else "n/a",
    }


def main() -> int:
    out: list[dict[str, str]] = []
    for arm, rows in _arm_rows().items():
        for suite in SUITES:
            out.append(_summarize(arm, suite, [r for r in rows if r["suite"] == suite]))
        out.append(_summarize(arm, "pooled", rows))
    with OUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(out)
    print(f"wrote {OUT_PATH.name}")
    for row in out:
        print("  " + " ".join(f"{k}={row[k]}" for k in FIELDS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
