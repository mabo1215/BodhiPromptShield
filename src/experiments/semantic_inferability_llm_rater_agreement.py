#!/usr/bin/env python3
"""Score a model rater's blind inferability labels against the human reference.

The 102-item human subset (``semantic_inferability_human_sheet*``) is the
paper's reference for factual inferability. This script scores an additional
rater that answered the same sheet from a blank copy -- the released text and
the fact only, in a shuffled order, with no access to the key, the judge's
verdict, the method, or any earlier annotator's answer -- and reports Cohen's
kappa and raw agreement against the first annotator, the independent blank-sheet
reader (round 3), the primed review pass (round 2), the recorded judge model,
and the lexical criterion, together with the per-method inferable rate the
rater's labels imply.

It exists so that a rater which is itself a language model can be reported as
exactly that: one more judge whose agreement with people is measured before
its rate is read, never as an extension of the human-annotated subset. The
annotations file is the record; this script only regenerates the statistics.

Usage:
    python semantic_inferability_llm_rater_agreement.py \
        --annotations semantic_inferability_llm_rater_annotations_claude_20261007.csv \
        --out-tag claude_20261007
"""
from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

from semantic_inferability_agreement import _interpret, _kappa, _parse_human

EXPERIMENTS_DIR = Path(__file__).resolve().parent
METHOD_ORDER = ["no_protection", "regex_only", "presidio", "casper_style", "heuristic_mediator", "learned_lr"]


def _read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _labels(path: Path, column: str) -> dict[str, int]:
    out: dict[str, int] = {}
    if not path.exists():
        return out
    for row in _read(path):
        value = _parse_human(row.get(column, ""))
        if value is not None and row["item_id"] not in out:
            out[row["item_id"]] = value
    return out


def _rate_ci(values: list[int], n_boot: int, rng: random.Random) -> tuple[float, float, float]:
    point = 100.0 * sum(values) / len(values)
    boots = sorted(100.0 * sum(rng.choice(values) for _ in values) / len(values) for _ in range(n_boot))
    return point, boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot) - 1]


def run(annotations: Path, tag: str, out_tag: str, n_boot: int) -> None:
    suffix = f"_{tag}" if tag else ""
    rater = _labels(annotations, "human_inferable_YES_or_NO")
    if not rater:
        raise SystemExit(f"{annotations.name} carries no YES/NO labels")

    first: dict[str, int] = {}
    key: dict[str, dict[str, str]] = {}
    for stem in ("", "_topup", "_topup2"):
        first.update({k: v for k, v in _labels(EXPERIMENTS_DIR / f"semantic_inferability_human_sheet{stem}{suffix}.csv",
                                               "human_inferable_YES_or_NO").items() if k not in first})
        key_path = EXPERIMENTS_DIR / f"semantic_inferability_human_key{stem}{suffix}.csv"
        if key_path.exists():
            for row in _read(key_path):
                key.setdefault(row["item_id"], row)
    round2 = _labels(EXPERIMENTS_DIR / f"semantic_inferability_round2_annotations{suffix}.csv", "annotator2")
    round3 = _labels(EXPERIMENTS_DIR / f"semantic_inferability_round3_annotations{suffix}.csv", "human_inferable_YES_or_NO")
    judge = {k: int(r["judge_inferable"]) for k, r in key.items() if r["judge_inferable"] != ""}
    lexical = {k: int(r["lexical_retained"]) for k, r in key.items() if r["lexical_retained"] != ""}

    comparisons = [("rater_vs_annotator1", first), ("rater_vs_annotator2_primed", round2),
                   ("rater_vs_annotator3_blank_sheet", round3), ("rater_vs_judge", judge), ("rater_vs_lexical", lexical)]
    rows = []
    for name, other in comparisons:
        pairs = [(other[k], rater[k]) for k in rater if k in other]
        if not pairs:
            continue
        kappa, raw, matrix = _kappa(pairs)
        rows.append({"comparison": name, "n": str(len(pairs)), "cohens_kappa": f"{kappa:.3f}",
                     "interpretation": _interpret(kappa), "raw_agreement": f"{raw:.3f}",
                     "other_no_rater_no": str(matrix[0][0]), "other_no_rater_yes": str(matrix[0][1]),
                     "other_yes_rater_no": str(matrix[1][0]), "other_yes_rater_yes": str(matrix[1][1])})
    pairs = [(first[k], round3[k]) for k in round3 if k in first]
    if pairs:
        kappa, raw, matrix = _kappa(pairs)
        rows.append({"comparison": "annotator1_vs_annotator3_reference", "n": str(len(pairs)),
                     "cohens_kappa": f"{kappa:.3f}", "interpretation": _interpret(kappa),
                     "raw_agreement": f"{raw:.3f}", "other_no_rater_no": str(matrix[0][0]),
                     "other_no_rater_yes": str(matrix[0][1]), "other_yes_rater_no": str(matrix[1][0]),
                     "other_yes_rater_yes": str(matrix[1][1])})
    out = EXPERIMENTS_DIR / f"semantic_inferability_llm_rater_agreement_{out_tag}.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    by_method: dict[str, list[str]] = defaultdict(list)
    for item_id, row in key.items():
        if item_id in rater:
            by_method[row["method_key"]].append(item_id)
    rng = random.Random(17)
    method_rows = []
    for method in METHOD_ORDER + sorted(set(by_method) - set(METHOD_ORDER)):
        items = by_method.get(method, [])
        if not items:
            continue
        point, lo, hi = _rate_ci([rater[k] for k in items], n_boot, rng)
        method_rows.append({"method_key": method, "items": str(len(items)),
                            "rater_inferable": f"{point:.1f} [{lo:.1f}, {hi:.1f}]",
                            "annotator1_inferable": f"{100.0 * sum(first[k] for k in items) / len(items):.1f}",
                            "annotator3_inferable": f"{100.0 * sum(round3[k] for k in items) / len(items):.1f}",
                            "judge_inferable": f"{100.0 * sum(judge[k] for k in items) / len(items):.1f}"})
    by_out = EXPERIMENTS_DIR / f"semantic_inferability_llm_rater_by_method_{out_tag}.csv"
    with by_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(method_rows[0].keys()))
        writer.writeheader()
        writer.writerows(method_rows)

    for row in rows:
        print(f"  {row['comparison']:36s} n={row['n']:>3} kappa={row['cohens_kappa']} ({row['interpretation']}) raw={row['raw_agreement']}")
    for row in method_rows:
        print(f"  {row['method_key']:18s} rater={row['rater_inferable']:22s} A1={row['annotator1_inferable']:>5} "
              f"A3={row['annotator3_inferable']:>5} judge={row['judge_inferable']:>5}")
    print(f"Written: {out.name}, {by_out.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--annotations", required=True, help="CSV with item_id and human_inferable_YES_or_NO")
    parser.add_argument("--tag", default="vgpu3090", help="tag of the sheet/key/round files to score against")
    parser.add_argument("--out-tag", required=True, help="suffix for the written agreement records")
    parser.add_argument("--bootstrap", type=int, default=1000)
    args = parser.parse_args()
    run(Path(args.annotations), args.tag, args.out_tag, args.bootstrap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
