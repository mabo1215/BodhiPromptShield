#!/usr/bin/env python3
"""Draw the blind subset for validating PrivacyLens' own judge model.

The downstream leak rates in the paper are counts of decisions made by the
judge model PrivacyLens released with the benchmark, applied through that
benchmark's verbatim prompts.  Nothing in this work has ever checked those
decisions against a person.  That gap matters more here than it usually would:
the same check, run on our own judge for factual inferability, found it at
chance against a human reader.  A judge that has not been checked is not
evidence that it is right.

This script draws the subset for that check from
``privacylens_downstream_suite --export-judge-decisions``, which replays the
recorded run out of the generation cache, so the decisions sampled here are
the ones behind the published numbers rather than a fresh run that might
differ.

Two files come out, and the split between them is the point:

* the **sheet** carries only the action the judge saw and the one sensitive
  item in question.  It has no verdict column, no condition label, and no case
  name -- a reader who knew an item came from the unprotected arm could infer
  the answer without reading anything.
* the **key** carries the judge's verdict and the provenance, and is for the
  analyst scoring agreement.  It must not be given to the annotator.

Sampling is stratified over conditions and over the judge's own verdict, so
the subset cannot agree with the judge merely by inheriting a lopsided base
rate: a judge that answers "no leak" nine times in ten would otherwise look
accurate on a sample that is nine-tenths "no leak" items.  Within a stratum
the draw is seeded and therefore reproducible.
"""
from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent

SHEET_FIELDS = ["item_id", "released_text_shown_to_judge", "fact", "human_leak_YES_or_NO"]
KEY_FIELDS = ["item_id", "condition", "case", "secret_index", "user_name",
              "judge_model", "judge_leak", "judge_reasoning"]


def _strata(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    buckets: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        buckets[(row["condition"], row["judge_leak"])].append(row)
    return buckets


def _allocate(buckets: dict[tuple[str, str], list[dict[str, str]]], total: int) -> dict[tuple[str, str], int]:
    """Spread the sample as evenly as the strata allow, largest-remainder.

    An even split is what keeps the check honest, but a stratum cannot give
    more rows than it holds; whatever a small stratum cannot supply is handed
    back to the ones that can, so the subset still reaches its target size.
    """
    quota = {k: 0 for k in buckets}
    remaining = total
    open_strata = set(buckets)
    while remaining > 0 and open_strata:
        share, extra = divmod(remaining, len(open_strata))
        if share == 0:
            # Fewer rows left than strata: hand them out one at a time, in a
            # fixed order, to whichever strata still have room.
            for key in sorted(open_strata)[:extra or remaining]:
                quota[key] += 1
                remaining -= 1
            break
        progressed = False
        for key in sorted(open_strata):
            room = len(buckets[key]) - quota[key]
            take = min(share, room)
            quota[key] += take
            remaining -= take
            if take:
                progressed = True
            if quota[key] >= len(buckets[key]):
                open_strata.discard(key)
        if not progressed:
            break
    return quota


def draw(decisions: Path, sheet: Path, key: Path, n: int, seed: int) -> None:
    with decisions.open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if (r.get("final_action") or "").strip()]
    if not rows:
        raise SystemExit(f"{decisions.name} holds no decisions with an action to judge")

    buckets = _strata(rows)
    quota = _allocate(buckets, min(n, len(rows)))
    rng = random.Random(seed)

    drawn: list[dict[str, str]] = []
    for stratum in sorted(buckets):
        pool = sorted(buckets[stratum], key=lambda r: (r["case"], int(r["secret_index"])))
        drawn.extend(rng.sample(pool, quota[stratum]))
    # Present in an order that carries no signal: consecutive items from one
    # condition would let a reader infer the arm, and with it the answer.
    rng.shuffle(drawn)

    with sheet.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_FIELDS)
        writer.writeheader()
        for i, row in enumerate(drawn, 1):
            writer.writerow({"item_id": str(i), "released_text_shown_to_judge": row["final_action"],
                             "fact": row["secret"], "human_leak_YES_or_NO": ""})
    with key.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=KEY_FIELDS)
        writer.writeheader()
        for i, row in enumerate(drawn, 1):
            writer.writerow({"item_id": str(i), **{f: row[f] for f in KEY_FIELDS[1:]}})

    leaked = sum(1 for r in drawn if r["judge_leak"] == "1")
    print(f"[judge-sheet] drew {len(drawn)} of {len(rows)} decisions across {len(buckets)} strata")
    print(f"  judge says leaked: {leaked} ({100.0 * leaked / len(drawn):.1f}%); "
          f"population rate {100.0 * sum(1 for r in rows if r['judge_leak'] == '1') / len(rows):.1f}%")
    print(f"[judge-sheet] wrote {sheet.name} (blind) and {key.name} (analyst only -- do not hand to the annotator)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--decisions", required=True,
                        help="privacylens_judge_decisions_<agent>.csv from --export-judge-decisions")
    parser.add_argument("--tag", default="")
    parser.add_argument("-n", type=int, default=120,
                        help="subset size; the review asked for at least 100")
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""
    draw(Path(args.decisions),
         EXPERIMENTS_DIR / f"privacylens_judge_human_sheet{suffix}.csv",
         EXPERIMENTS_DIR / f"privacylens_judge_human_key{suffix}.csv",
         args.n, args.seed)


if __name__ == "__main__":
    main()
