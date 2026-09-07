"""Score the human-annotated subset against the judge (Cohen's kappa).

``semantic_inferability_judge`` emits a blind annotation sheet and a separate
key file. An annotator fills the sheet's verdict column without seeing the
judge's answer; this script joins the two and reports raw agreement, Cohen's
kappa, and the confusion matrix, plus the same statistics against the lexical
Fact Retention criterion so the two measures can be compared on the same
items.

Kappa is the number that decides whether the judged inferability rate can be
reported as a measurement rather than as a model artifact.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

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


def _kappa(pairs: list[tuple[int, int]]) -> tuple[float, float, list[list[int]]]:
    """Cohen's kappa for two binary raters, with raw agreement and the table."""
    matrix = [[0, 0], [0, 0]]
    for a, b in pairs:
        matrix[a][b] += 1
    n = len(pairs)
    if n == 0:
        return 0.0, 0.0, matrix
    observed = (matrix[0][0] + matrix[1][1]) / n
    row0 = (matrix[0][0] + matrix[0][1]) / n
    row1 = (matrix[1][0] + matrix[1][1]) / n
    col0 = (matrix[0][0] + matrix[1][0]) / n
    col1 = (matrix[0][1] + matrix[1][1]) / n
    expected = row0 * col0 + row1 * col1
    kappa = (observed - expected) / (1 - expected) if expected < 1 else 1.0
    return kappa, observed, matrix


def _interpret(kappa: float) -> str:
    for threshold, label in ((0.81, "almost perfect"), (0.61, "substantial"),
                             (0.41, "moderate"), (0.21, "fair"), (0.0, "slight")):
        if kappa >= threshold:
            return label
    return "poor (worse than chance)"


def run(sheet: Path, key: Path, out: Path) -> None:
    with sheet.open(encoding="utf-8", newline="") as handle:
        human = {r["item_id"]: _parse_human(r["human_inferable_YES_or_NO"])
                 for r in csv.DictReader(handle)}
    with key.open(encoding="utf-8", newline="") as handle:
        key_rows = {r["item_id"]: r for r in csv.DictReader(handle)}

    annotated = [i for i, v in human.items() if v is not None and i in key_rows]
    if not annotated:
        print(f"[agreement] {sheet.name} has no completed annotations yet; "
              f"fill the human_inferable_YES_or_NO column and re-run.")
        return

    judge_pairs = [(human[i], int(key_rows[i]["judge_inferable"])) for i in annotated]
    lex_pairs = [(human[i], int(key_rows[i]["lexical_retained"])) for i in annotated]

    jk, jo, jm = _kappa(judge_pairs)
    lk, lo, lm = _kappa(lex_pairs)

    print(f"[agreement] {len(annotated)} annotated items of {len(human)}")
    print(f"  judge   vs human: kappa {jk:.3f} ({_interpret(jk)}), raw agreement {jo:.1%}")
    print(f"  lexical vs human: kappa {lk:.3f} ({_interpret(lk)}), raw agreement {lo:.1%}")
    print(f"  judge confusion [human][judge]: {jm}")

    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["comparison", "n", "cohens_kappa", "interpretation", "raw_agreement",
                         "human_no_pred_no", "human_no_pred_yes", "human_yes_pred_no", "human_yes_pred_yes"])
        for label, kappa, obs, matrix in (("judge_vs_human", jk, jo, jm),
                                          ("lexical_vs_human", lk, lo, lm)):
            writer.writerow([label, len(annotated), f"{kappa:.3f}", _interpret(kappa), f"{obs:.3f}",
                             matrix[0][0], matrix[0][1], matrix[1][0], matrix[1][1]])
    print(f"[agreement] wrote {out.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="vgpu3090")
    args = parser.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""
    run(
        EXPERIMENTS_DIR / f"semantic_inferability_human_sheet{suffix}.csv",
        EXPERIMENTS_DIR / f"semantic_inferability_human_key{suffix}.csv",
        EXPERIMENTS_DIR / f"semantic_inferability_agreement{suffix}.csv",
    )


if __name__ == "__main__":
    main()
