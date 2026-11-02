#!/usr/bin/env python3
"""The release-free controls on the value subsets the supplement discusses.

``attribute_recovery_controls.py`` compares each release with the controls overall and by
value kind. The per-kind levels hide what the shortlist alone gives away, so this script
reads the same rows on finer subsets: the user's own name, digit runs, names told from
other names, entities that are not names, and answers whose format is or is not unique
among the four options.

Reads records only; no model is called. It refuses to run if a rebuilt question differs
from a record. Output, next to the records:
``privacylens_attribute_recovery_control_subsets.csv``.
"""
from __future__ import annotations

import argparse
import csv
import json

from attribute_recovery_breakdown import PL_DATA, SEED, first_name_lexicon, format_signature
from attribute_recovery_controls import CONTROLS, EXPERIMENTS_DIR, RELEASES, _answered, _paired, _rows
from mediation_baselines import bootstrap_ratio_ci
from privacylens_attribute_recovery_attack import _build_questions

OUT = EXPERIMENTS_DIR / "privacylens_attribute_recovery_control_subsets.csv"


def _subset_of(row: dict, question: dict, user_name: str, lexicon: set[str]) -> list[str]:
    """Every subset a question belongs to."""
    answer = row["answer"]
    others = [o for i, o in enumerate(question["options"], 1) if i != question["correct_option"]]
    signature = format_signature(answer)
    names = ["format_unique" if all(format_signature(o) != signature for o in others) else "format_shared"]
    first = answer.split()[0] if answer.split() else ""
    if row["span_kind"] == "identifier":
        if answer == user_name:
            names.append("identifier_user_name")
        elif "@" not in answer:
            names.append("identifier_digit_run")
    elif row["span_kind"] == "entity":
        if first in lexicon:
            names.append("entity_first_name")
            if any(o.split() and o.split()[0] in lexicon for o in others):
                names.append("entity_name_among_names")
        else:
            names.append("entity_other")
    return names


def _rate(rows: list[dict], n_boot: int) -> str:
    by_case: dict[str, tuple[float, float]] = {}
    for row in rows:
        num, den = by_case.get(row["case"], (0.0, 0.0))
        by_case[row["case"]] = (num + _answered(row), den + 1.0)
    point, lo, hi = bootstrap_ratio_ci(list(by_case.values()), n_boot=n_boot, scale=100.0)
    return f"{point:.1f} [{lo:.1f}, {hi:.1f}]"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--attackers", default="qwen3_8b-q4km-hf,qwen3_32b-q4km-hf")
    parser.add_argument("--bootstrap", type=int, default=1000)
    args = parser.parse_args()

    cases = json.load(PL_DATA.open(encoding="utf-8"))
    lexicon = first_name_lexicon(cases)
    user_names = {c["name"]: c["trajectory"].get("user_name", "") for c in cases}
    questions, _ = _build_questions(cases, 4, SEED)
    by_key = {(q["case"], str(q["fact_index"])): q for q in questions}

    table: list[list[object]] = []
    for attacker in [a.strip() for a in args.attackers.split(",") if a.strip()]:
        control = _rows(EXPERIMENTS_DIR / f"privacylens_attribute_recovery_rows_{attacker}_controls.csv")
        recorded = _rows(EXPERIMENTS_DIR / f"privacylens_attribute_recovery_rows_{attacker}_corrected.csv")
        rows_by_condition: dict[str, list[dict]] = {}
        for source in (control, recorded):
            for (condition, _case, _index), row in source.items():
                rows_by_condition.setdefault(condition, []).append(row)
        no_document = {(r["case"], r["fact_index"]): r for r in rows_by_condition[CONTROLS[0]]}
        unprotected = {(r["case"], r["fact_index"]): r for r in rows_by_condition["no_protection"]}
        for condition in (*CONTROLS, *RELEASES):
            grouped: dict[str, list[dict]] = {}
            for row in rows_by_condition.get(condition, []):
                question = by_key[(row["case"], row["fact_index"])]
                if (question["answer"], str(question["correct_option"]), question["span_kind"]) != (
                        row["answer"], row["correct_option"], row["span_kind"]):
                    raise SystemExit(f"rebuilt question differs from the record at {row['case']}/{row['fact_index']}")
                for name in _subset_of(row, question, user_names[row["case"]], lexicon):
                    grouped.setdefault(name, []).append(row)
                if (condition in RELEASES and row["survives_release"] == "0"
                        and unprotected[(row["case"], row["fact_index"])]["survives_release"] == "1"):
                    grouped.setdefault("shown_unprotected_then_removed", []).append(row)
            for name in sorted(grouped):
                sub = grouped[name]
                absent = [r for r in sub if r["survives_release"] == "0"]
                is_control = condition in CONTROLS
                table.append([attacker, name, condition, len(sub), _rate(sub, args.bootstrap), len(absent),
                              _rate(absent, args.bootstrap) if absent else "",
                              "" if condition == CONTROLS[0] else _paired(sub, no_document, args.bootstrap),
                              "" if is_control or not absent else _paired(absent, no_document, args.bootstrap)])
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["attacker", "subset", "condition", "questions", "recovery_percent", "questions_value_absent",
                         "recovery_when_value_absent_percent", "minus_no_document_points",
                         "minus_no_document_points_value_absent"])
        writer.writerows(table)
    print(f"[subsets] wrote {OUT.name}: {len(table)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
