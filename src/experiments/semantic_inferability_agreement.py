"""Score the human-annotated subset against the judge (Cohen's kappa).

``semantic_inferability_judge`` emits a blind annotation sheet and a separate
key file. An annotator fills the sheet's verdict column without seeing the
judge's answer; this script joins the two and reports raw agreement, Cohen's
kappa, and the confusion matrix, plus the same statistics against the lexical
Fact Retention criterion so the two measures can be compared on the same
items.

Kappa is the number that decides whether the judged inferability rate can be
reported as a measurement rather than as a model artifact.

With ``--round2`` the script scores the second annotator's export. That round
was run as a review pass: every item opened carrying the first annotator's
label, and the second annotator confirmed it or changed it. Both records are
kept whole and separate -- round one is never rewritten -- but the two are not
independent ratings, because the second reader started from the first one's
answer. Agreement between them is therefore reported as a primed rate and an
upper bound, never as an independent reliability estimate; the count of items
the second reader changed is reported alongside it, since that is the part the
priming cannot manufacture. The judge and the lexical criterion are scored
against the second reader's own labels.
"""
from __future__ import annotations

import argparse
import csv
import random
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


def _bootstrap_ci(flags: list[int], iterations: int = 10000, seed: int = 17) -> tuple[float, float]:
    """Percentile bootstrap CI for the rate of 1s, on the same seed as the run."""
    rng = random.Random(seed)
    n = len(flags)
    if n == 0:
        return 0.0, 0.0
    rates = []
    for _ in range(iterations):
        draw = sum(flags[rng.randrange(n)] for _ in range(n))
        rates.append(100.0 * draw / n)
    rates.sort()
    return rates[int(0.025 * iterations)], rates[min(int(0.975 * iterations), iterations - 1)]


def _rate(flags: list[int]) -> str:
    lo, hi = _bootstrap_ci(flags)
    return f"{100.0 * sum(flags) / len(flags):.1f} [{lo:.1f}, {hi:.1f}]"


def run_round2(round2: Path, key: Path, out: Path, by_method: Path) -> None:
    """Score the second annotator's review pass against round one and the proxies."""
    with round2.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with key.open(encoding="utf-8", newline="") as handle:
        key_rows = {r["item_id"]: r for r in csv.DictReader(handle)}

    items = []
    for row in rows:
        item = row["item_id"]
        a1 = _parse_human(row.get("annotator1", ""))
        a2 = _parse_human(row.get("annotator2", ""))
        seen = (row.get("reviewed", "YES") or "YES").strip().upper() != "NO"
        if item in key_rows and a1 is not None and a2 is not None and seen:
            items.append((item, a1, a2))

    if not items:
        print(f"[agreement] {round2.name} has no reviewed round-2 items yet; the "
              f"second annotator has not confirmed or changed anything.")
        return

    primed, primed_obs, primed_matrix = _kappa([(a1, a2) for _, a1, a2 in items])
    judge = _kappa([(a2, int(key_rows[i]["judge_inferable"])) for i, _, a2 in items])
    lex = _kappa([(a2, int(key_rows[i]["lexical_retained"])) for i, _, a2 in items])
    changed = sum(1 for _, a1, a2 in items if a1 != a2)

    print(f"[agreement] {len(items)} reviewed round-2 items of {len(rows)}")
    print(f"  annotator 2 changed {changed} of {len(items)} items "
          f"({100.0 * changed / len(items):.1f}%)")
    print(f"  annotator 1 vs annotator 2: kappa {primed:.3f} ({_interpret(primed)}), "
          f"raw agreement {primed_obs:.1%}")
    print(f"    NOTE: annotator 2 worked from annotator 1's labels, so this is a "
          f"primed agreement rate and an upper bound. It is NOT an independent "
          f"inter-rater reliability estimate and must not be reported as one.")
    print(f"  judge   vs annotator 2: kappa {judge[0]:.3f} ({_interpret(judge[0])}), "
          f"raw agreement {judge[1]:.1%}")
    print(f"  lexical vs annotator 2: kappa {lex[0]:.3f} ({_interpret(lex[0])}), "
          f"raw agreement {lex[1]:.1%}")
    print(f"  confusion [annotator1][annotator2]: {primed_matrix}")

    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["comparison", "n", "cohens_kappa", "interpretation", "raw_agreement",
                         "cell_no_no", "cell_no_yes", "cell_yes_no", "cell_yes_yes", "note"])
        writer.writerow(["annotator1_vs_annotator2_primed", len(items), f"{primed:.3f}",
                         _interpret(primed), f"{primed_obs:.3f}",
                         primed_matrix[0][0], primed_matrix[0][1],
                         primed_matrix[1][0], primed_matrix[1][1],
                         "annotator 2 reviewed annotator 1's labels rather than rating "
                         "independently; upper bound, not an inter-rater reliability estimate"])
        for label, (kappa, obs, matrix) in (("judge_vs_annotator2", judge),
                                            ("lexical_vs_annotator2", lex)):
            writer.writerow([label, len(items), f"{kappa:.3f}", _interpret(kappa),
                             f"{obs:.3f}", matrix[0][0], matrix[0][1],
                             matrix[1][0], matrix[1][1], ""])
        writer.writerow(["annotator2_changed_from_annotator1", len(items), "", "",
                         f"{changed / len(items):.3f}", "", "", "", "", ""])
    print(f"[agreement] wrote {out.name}")

    # Per-method rates in the same shape the inferability figure reads, so the
    # figure can be redrawn on the second reader's labels.
    methods: dict[str, list[tuple[int, str]]] = {}
    for item, _, a2 in items:
        methods.setdefault(key_rows[item]["method_key"], []).append((a2, item))
    with by_method.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["method_key", "items", "human_inferable",
                         "judge_inferable", "lexical_retained"])
        for method, pairs in methods.items():
            human = [v for v, _ in pairs]
            ids = [i for _, i in pairs]
            writer.writerow([method, len(pairs), _rate(human),
                             _rate([int(key_rows[i]["judge_inferable"]) for i in ids]),
                             _rate([int(key_rows[i]["lexical_retained"]) for i in ids])])
    print(f"[agreement] wrote {by_method.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="vgpu3090")
    parser.add_argument("--round2", help="the second annotator's exported CSV")
    args = parser.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""
    key = EXPERIMENTS_DIR / f"semantic_inferability_human_key{suffix}.csv"
    if args.round2:
        run_round2(Path(args.round2), key,
                   EXPERIMENTS_DIR / f"semantic_inferability_agreement_round2{suffix}.csv",
                   EXPERIMENTS_DIR / f"semantic_inferability_human_by_method_round2{suffix}.csv")
        return
    run(
        EXPERIMENTS_DIR / f"semantic_inferability_human_sheet{suffix}.csv",
        key,
        EXPERIMENTS_DIR / f"semantic_inferability_agreement{suffix}.csv",
    )


if __name__ == "__main__":
    main()
