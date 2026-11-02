"""
Audit the attribute-recovery answer parser against the recorded replies.

The attack scores a reply by the first in-range option number it contains
(privacylens_attribute_recovery_attack._parse_choice). A reply that mentions a
second such number could in principle be misread. This script measures, per
attacker, how many replies mention more than one in-range number, how many of
the parsed replies do not open with their answer, and how far the value-absent
recovery rate of each condition moves if those replies are treated as unparsed
(dropped) or as failures. It reads the released per-question records only.

Usage:
  python src/experiments/attribute_recovery_parse_audit.py
"""
from __future__ import annotations

import csv
import os
import re

EXPERIMENTS_DIR = os.path.dirname(os.path.abspath(__file__))
ATTACKERS = ("qwen3_8b-q4km-hf", "qwen3_32b-q4km-hf", "llama3.3_70b-q4km-hf")
OUT = os.path.join(EXPERIMENTS_DIR, "privacylens_attribute_recovery_parse_audit.csv")

_THINK = re.compile(r"<think>.*?</think>", flags=re.S | re.I)
_NUMBER = re.compile(r"\b([1-9][0-9]?)\b")
# A reply "opens with its answer" when its first word-like token is the option
# number, optionally after "Option"/"Answer"/"Candidate" and punctuation.
_LEADING = re.compile(r"^\W*(?:(?:option|answer|candidate)\s*:?\s*)?\(?([1-9][0-9]?)\b", re.I)


def _in_range(text: str, n: int) -> list[int]:
    return [int(t) for t in _NUMBER.findall(text) if 1 <= int(t) <= n]


def _rate(rows: list[dict[str, str]]) -> float | None:
    return 100.0 * sum(int(r["correct"]) for r in rows) / len(rows) if rows else None


def main() -> int:
    out_rows = []
    for tag in ATTACKERS:
        path = os.path.join(EXPERIMENTS_DIR, f"privacylens_attribute_recovery_rows_{tag}_corrected.csv")
        with open(path, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        multi = 0
        not_leading = set()
        for i, r in enumerate(rows):
            text = _THINK.sub(" ", r["raw"]).strip()
            if len(set(_in_range(text, int(r["n_options"])))) > 1:
                multi += 1
            lead = _LEADING.match(text)
            if r["chosen_option"] and not (lead and int(lead.group(1)) == int(r["chosen_option"])):
                not_leading.add(i)
        multi_not_leading = sum(
            1 for i in not_leading
            if len(set(_in_range(_THINK.sub(" ", rows[i]["raw"]), int(rows[i]["n_options"])))) > 1
        )
        for cond in sorted({r["condition"] for r in rows}):
            absent = [(i, r) for i, r in enumerate(rows)
                      if r["condition"] == cond and r["chosen_option"] and r["survives_release"] == "0"]
            kept = [r for i, r in absent if i not in not_leading]
            as_failure = [dict(r, correct="0") if i in not_leading else r for i, r in absent]
            current, dropped, failed = _rate([r for _, r in absent]), _rate(kept), _rate(as_failure)
            out_rows.append({
                "attacker": tag,
                "replies": len(rows),
                "replies_multiple_in_range_numbers": multi,
                "parsed_replies_not_opening_with_answer": len(not_leading),
                "of_which_multiple_in_range_numbers": multi_not_leading,
                "condition": cond,
                "value_absent_questions": len(absent),
                "value_absent_not_opening_with_answer": len(absent) - len(kept),
                "recovery_when_absent_percent": f"{current:.2f}" if current is not None else "",
                "if_dropped_percent": f"{dropped:.2f}" if dropped is not None else "",
                "if_failure_percent": f"{failed:.2f}" if failed is not None else "",
            })
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        writer.writeheader()
        writer.writerows(out_rows)
    for r in out_rows:
        print(f"{r['attacker']:<22} {r['condition']:<24} multi={r['replies_multiple_in_range_numbers']:>4} "
              f"not_leading={r['parsed_replies_not_opening_with_answer']:>2} "
              f"absent {r['recovery_when_absent_percent']:>6} -> drop {r['if_dropped_percent']:>6} / fail {r['if_failure_percent']:>6}")
    print("Wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
