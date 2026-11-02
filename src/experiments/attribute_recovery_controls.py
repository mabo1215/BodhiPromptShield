#!/usr/bin/env python3
"""Read attribute recovery against what the question gives away with no release.

The attack's recovery rate mixes two things: inference from the released text, and
what the stem and the four candidates reveal on their own. The second can be large,
because candidates are typed only by shape: a blank in "____ is going through a
divorce" among one person name and three company names answers itself. Two controls
answer the identical questions with nothing about the case in the release:

* ``no_document``: the document is withheld outright;
* ``masked_document``: every word of the document is replaced by the same marker, so
  only its layout and length remain.

This compares each recorded condition with the controls on the same questions,
paired over cases. It refuses to compare unless every control row carries the same
answer, correct option, and value kind as the recorded row for that question, which
is what makes the pairing valid. No model is called.

Inputs: ``*_rows_<attacker>_controls.csv`` from the attack script and the corrected
per-question rows from the presence audit. Output, next to the records:

* ``privacylens_attribute_recovery_controls.csv``: per attacker, condition, and value
  kind, recovery with a case-level interval, and its paired difference from each
  control over all questions and over the questions whose value is absent;
* ``privacylens_attribute_recovery_controls_by_question.csv``: one row per attacker
  and question, for the controls.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENTS_DIR))

from downstream_paired_tests import paired_bootstrap_diff  # noqa: E402
from mediation_baselines import bootstrap_ratio_ci  # noqa: E402

OUT = EXPERIMENTS_DIR / "privacylens_attribute_recovery_controls.csv"
BY_QUESTION = EXPERIMENTS_DIR / "privacylens_attribute_recovery_controls_by_question.csv"
CONTROLS = ("no_document", "masked_document")
RELEASES = ("no_protection", "placeholder:presidio", "casper_style", "placeholder:learned_lr")
KINDS = ("all", "identifier", "number", "entity")
KEY_FIELDS = ("answer", "correct_option", "span_kind")


def _rows(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {(r["condition"], r["case"], r["fact_index"]): r for r in csv.DictReader(handle)}


def _check_same_questions(control: dict, recorded: dict) -> int:
    """Every control row must be the recorded question, or the pairing means nothing."""
    by_question = {(c, i): r for (cond, c, i), r in recorded.items() if cond == RELEASES[0]}
    bad = 0
    for (_cond, case, index), row in control.items():
        other = by_question.get((case, index))
        if other is None or any(row[f] != other[f] for f in KEY_FIELDS):
            bad += 1
    return bad


def _answered(row: dict[str, str]) -> float:
    """An unparsed reply counts as wrong, the strict reading used in the main text."""
    return float(row["correct"]) if row.get("chosen_option") else 0.0


def _paired(a_rows: list[dict], b_lookup: dict, n_boot: int) -> str:
    per_case: dict[str, list[float]] = {}
    for row in a_rows:
        other = b_lookup.get((row["case"], row["fact_index"]))
        if other is None:
            continue
        acc = per_case.setdefault(row["case"], [0.0, 0.0, 0.0, 0.0])
        acc[0] += _answered(row)
        acc[1] += 1.0
        acc[2] += _answered(other)
        acc[3] += 1.0
    pairs = [tuple(v) for v in per_case.values()]
    if not pairs:
        return ""
    point, lo, hi = paired_bootstrap_diff(pairs, n_boot=n_boot, scale=100.0)
    return f"{point:+.1f} [{lo:+.1f}, {hi:+.1f}]"


def analyse(attacker: str, n_boot: int) -> list[list[object]]:
    control_path = EXPERIMENTS_DIR / f"privacylens_attribute_recovery_rows_{attacker}_controls.csv"
    recorded_path = EXPERIMENTS_DIR / f"privacylens_attribute_recovery_rows_{attacker}_corrected.csv"
    if not control_path.exists():
        print(f"[controls] {attacker}: no control rows yet", flush=True)
        return []
    control = _rows(control_path)
    recorded = _rows(recorded_path)
    bad = _check_same_questions(control, recorded)
    if bad:
        raise SystemExit(f"[controls] {attacker}: {bad} control rows do not match a recorded question")

    lookups = {name: {(c, i): r for (cond, c, i), r in control.items() if cond == name} for name in CONTROLS}
    table: list[list[object]] = []
    for condition in (*CONTROLS, *RELEASES):
        source = control if condition in CONTROLS else recorded
        rows = [r for (cond, _c, _i), r in source.items() if cond == condition]
        if not rows:
            continue
        for kind in KINDS:
            sub = [r for r in rows if kind == "all" or r["span_kind"] == kind]
            if not sub:
                continue
            by_case: dict[str, tuple[float, float]] = {}
            for row in sub:
                num, den = by_case.get(row["case"], (0.0, 0.0))
                by_case[row["case"]] = (num + _answered(row), den + 1.0)
            point, lo, hi = bootstrap_ratio_ci(list(by_case.values()), n_boot=n_boot, scale=100.0)
            absent = [r for r in sub if r["survives_release"] == "0"]
            cells = [attacker, condition, kind, len(sub), f"{point:.1f} [{lo:.1f}, {hi:.1f}]", len(absent)]
            for name in CONTROLS:
                if condition == name or not lookups[name]:
                    cells += ["", ""]
                    continue
                cells += [_paired(sub, lookups[name], n_boot),
                          _paired(absent, lookups[name], n_boot) if condition not in CONTROLS else ""]
            table.append(cells)
            print("  " + "  ".join(str(c) for c in cells[1:]), flush=True)
    return table


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--attackers", default="qwen3_8b-q4km-hf,qwen3_32b-q4km-hf,llama3.3_70b-q4km-hf")
    parser.add_argument("--bootstrap", type=int, default=1000)
    args = parser.parse_args()

    rows: list[list[object]] = []
    per_question: list[list[object]] = []
    for attacker in [a.strip() for a in args.attackers.split(",") if a.strip()]:
        rows += analyse(attacker, args.bootstrap)
        path = EXPERIMENTS_DIR / f"privacylens_attribute_recovery_rows_{attacker}_controls.csv"
        if path.exists():
            for (condition, case, index), row in _rows(path).items():
                per_question.append([attacker, condition, case, index, row["span_kind"], row["answer"],
                                     row["correct_option"], row["chosen_option"], row["correct"]])
    if not rows:
        print("[controls] nothing to write")
        return 1
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["attacker", "condition", "value_kind", "questions", "recovery_percent",
                         "questions_value_absent",
                         "minus_no_document_points", "minus_no_document_points_value_absent",
                         "minus_masked_document_points", "minus_masked_document_points_value_absent"])
        writer.writerows(rows)
    with BY_QUESTION.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["attacker", "condition", "case", "fact_index", "value_kind", "answer", "correct_option",
                         "chosen_option", "correct"])
        writer.writerows(per_question)
    print(f"[controls] wrote {OUT.name} and {BY_QUESTION.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
