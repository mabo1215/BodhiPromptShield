#!/usr/bin/env python3
"""Score PrivacyLens' own judge model against human labels (Cohen's kappa).

``privacylens_judge_human_sheet`` draws a blind, verdict-stratified subset of
the judge's per-item leakage decisions and holds its verdicts in a separate
key.  An annotator fills the sheet without seeing that key; this script joins
the two and reports raw agreement, Cohen's kappa, and the confusion matrix,
overall and per mediation condition.

The number this produces decides how the paper's downstream leak rates may be
described.  A judge that agrees with a person can be reported as measuring
leakage.  One that does not is reporting its own behaviour, and the rates it
produced have to be written that way -- which is exactly what happened to our
own inferability judge when it was put through this same check.

Because the subset is drawn stratified over the judge's verdict rather than at
its natural base rate, raw agreement here is not the accuracy the judge would
show on the full run: a balanced subset is deliberately harder than a lopsided
one.  Kappa is the number to read, and the per-condition rows say where any
disagreement concentrates.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from semantic_inferability_agreement import _interpret, _kappa

EXPERIMENTS_DIR = Path(__file__).resolve().parent

YES = {"yes", "y", "1", "true"}
NO = {"no", "n", "0", "false"}


def _parse_human(value: str) -> int | None:
    token = (value or "").strip().lower()
    if token in YES:
        return 1
    if token in NO:
        return 0
    return None


def _answer_column(row: dict[str, str]) -> str:
    for name in ("human_leak_YES_or_NO", "human_inferable_YES_or_NO", "human"):
        if name in row:
            return name
    raise SystemExit(f"no human answer column in {sorted(row)}")


def run(annotations: Path, key: Path, out: Path) -> None:
    with annotations.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    column = _answer_column(rows[0])
    human = {r["item_id"]: _parse_human(r[column]) for r in rows}
    with key.open(encoding="utf-8", newline="") as handle:
        key_rows = {r["item_id"]: r for r in csv.DictReader(handle)}

    annotated = [i for i, v in human.items() if v is not None and i in key_rows]
    if not annotated:
        print(f"[judge-agreement] {annotations.name} has no completed answers yet.")
        return

    pairs = [(human[i], int(key_rows[i]["judge_leak"])) for i in annotated]
    kappa, observed, matrix = _kappa(pairs)

    by_condition: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for i in annotated:
        by_condition[key_rows[i]["condition"]].append((human[i], int(key_rows[i]["judge_leak"])))

    print(f"[judge-agreement] {len(annotated)} annotated items of {len(human)}")
    print(f"  judge vs human: kappa {kappa:.3f} ({_interpret(kappa)}), raw agreement {observed:.1%}")
    print(f"  confusion [human][judge]: {matrix}")
    print(f"  human says leaked in {sum(h for h, _ in pairs)}, judge in {sum(j for _, j in pairs)}")
    print("  NOTE: the subset is stratified over the judge's verdict, so raw agreement here is not "
          "the judge's accuracy on the full run. Read kappa.")

    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["comparison", "n", "cohens_kappa", "interpretation", "raw_agreement",
                         "human_no_judge_no", "human_no_judge_yes", "human_yes_judge_no",
                         "human_yes_judge_yes", "note"])
        writer.writerow(["judge_vs_human_overall", len(annotated), f"{kappa:.3f}", _interpret(kappa),
                         f"{observed:.3f}", matrix[0][0], matrix[0][1], matrix[1][0], matrix[1][1],
                         "subset stratified over condition and over the judge's own verdict, so raw "
                         "agreement is not the judge's accuracy at its natural base rate"])
        for condition in sorted(by_condition):
            sub = by_condition[condition]
            k, o, m = _kappa(sub)
            writer.writerow([f"judge_vs_human_{condition}", len(sub), f"{k:.3f}", _interpret(k),
                             f"{o:.3f}", m[0][0], m[0][1], m[1][0], m[1][1], ""])
    print(f"[judge-agreement] wrote {out.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--annotations", required=True, help="the annotator's exported CSV")
    parser.add_argument("--tag", default="")
    args = parser.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""
    run(Path(args.annotations),
        EXPERIMENTS_DIR / f"privacylens_judge_human_key{suffix}.csv",
        EXPERIMENTS_DIR / f"privacylens_judge_agreement{suffix}.csv")


if __name__ == "__main__":
    main()
