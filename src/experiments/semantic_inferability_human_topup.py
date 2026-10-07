"""Extend the blind inferability annotation subset by one item per method.

The original sheet was requested with ``--human-n 100`` but stratifies before it
counts: ``100 // 6`` methods is 16 items each, so it wrote 96 and the review's
``n >= 100`` was missed by integer division rather than by design.  This script
adds the next item per method from the same shuffled order, so the subset grows
to 17 per method while staying balanced and disjoint from what was already
rated.

Two things have to hold before a new item can be trusted, and both are checked
rather than assumed:

  * the sampler replay must reproduce the existing key exactly, otherwise "the
    next item" is not the next item; and
  * a regenerated released surface must match the text stored in the original
    sheet byte for byte, otherwise the annotator is shown something different
    from what the judge saw and the agreement statistic is meaningless.

A method is only emitted once its own surfaces reproduce byte for byte.  That
gate matters most for ``presidio`` and ``casper_style``, whose detectors need
spaCy and Presidio at versions the original run did not record: if the local
stack differs, the check fails and the items are withheld rather than silently
shown to an annotator as something the judge never saw.

Methods that already have a top-up item are skipped, so the script can be run
again after installing more of the stack without duplicating work.

Usage:
    python semantic_inferability_human_topup.py --tag vgpu3090
    python semantic_inferability_human_topup.py --methods presidio,casper_style --out topup2
    python semantic_inferability_human_topup.py --extend-to 40 --out extend40

``--extend-to N`` grows every requested method to N items from the same
shuffled order, continuing after the items already rated (the base key and any
top-up), so the extension is balanced, disjoint from the rated subset, and
behind the same two verifications.
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import Counter
import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENTS_DIR))

from measured_agent_propagation import _sanitize  # noqa: E402
from mediation_baselines import build_detectors  # noqa: E402
from propagation_suite import _load_documents, _train_learned_detector  # noqa: E402

ALL_METHODS = ["no_protection", "regex_only", "presidio", "casper_style",
               "heuristic_mediator", "learned_lr"]
SEED = 17
MAX_DOCS = 200
MAX_CHARS = 6000
EXISTING_PER_METHOD = 16


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _documents() -> list[dict]:
    """Reproduce the judge run's document set and order exactly."""
    docs = [d for d in _load_documents("privacylens", None) if d["items"]]
    rng = random.Random(SEED)
    rng.shuffle(docs)
    docs = docs[:MAX_DOCS] if MAX_DOCS else docs
    docs.sort(key=lambda d: d["doc_id"])
    return docs


def _replay_sampler(rows: list[dict]) -> dict[str, list[dict]]:
    """Replay the original stratified shuffle, preserving rng consumption order."""
    by_method: dict[str, list[dict]] = {}
    for row in rows:
        if row["judge_inferable"] != "":
            by_method.setdefault(row["method_key"], []).append(row)
    rng = random.Random(SEED)
    for method_rows in by_method.values():
        rng.shuffle(method_rows)
    return by_method


def run(tag: str, methods: list[str], out_suffix: str, extend_to: int | None = None) -> int:
    suffix = f"_{tag}" if tag else ""
    rows = _read(EXPERIMENTS_DIR / f"semantic_inferability_rows{suffix}.csv")
    key = _read(EXPERIMENTS_DIR / f"semantic_inferability_human_key{suffix}.csv")
    sheet = _read(EXPERIMENTS_DIR / f"semantic_inferability_human_sheet{suffix}.csv")
    by_method = _replay_sampler(rows)

    # --- verification 1: the replay must reproduce the key that was actually rated.
    # Rated items are the base key plus every top-up key, deduplicated: the base
    # key later absorbed the first top-ups, so its size is not a constant. Per
    # method, the rated items must be exactly a prefix of the replayed order.
    rated_items = {(r["method_key"], r["doc_id"], r["fact_index"]) for r in key}
    for path in sorted(EXPERIMENTS_DIR.glob(f"semantic_inferability_human_key_topup*{suffix}.csv")):
        rated_items |= {(r["method_key"], r["doc_id"], r["fact_index"]) for r in _read(path)}
    rated_count = {m: sum(1 for item in rated_items if item[0] == m) for m in ALL_METHODS}
    replayed = {
        (m, r["doc_id"], r["fact_index"])
        for m, mrows in by_method.items()
        for r in mrows[:rated_count.get(m, 0)]
    }
    if replayed != rated_items:
        print(f"FAIL: sampler replay does not reproduce the rated items "
              f"({len(replayed & rated_items)}/{len(rated_items)} match).")
        return 1
    print(f"[verify 1] sampler replay reproduces all {len(rated_items)} rated items as per-method prefixes")

    # --- verification 2: a regenerated surface must equal the text the annotator saw.
    # Methods already topped up in an earlier pass are not re-emitted.
    already: set[str] = set()
    for path in sorted(EXPERIMENTS_DIR.glob(f"semantic_inferability_human_key_topup*{suffix}.csv")):
        already |= {r["method_key"] for r in _read(path)}
    rated = rated_count
    todo = [m for m in methods if m not in already] if extend_to is None else list(methods)
    if already and extend_to is None:
        print(f"[skip] already topped up: {', '.join(sorted(already))}")
    if not todo:
        print("nothing left to add for the requested methods.")
        return 0

    docs = _documents()
    learned = _train_learned_detector() if "learned_lr" in todo else None
    detectors = {d.key: d for d in build_detectors(todo, learned_weights=learned)}
    surfaces: dict[tuple[str, str], str] = {}
    for name, detector in detectors.items():
        for doc in docs:
            surfaces[(name, doc["doc_id"])] = _sanitize(doc["traj"], detector(doc["traj"]))

    sheet_by_id = {r["item_id"]: r for r in sheet}
    checked = mismatched = 0
    for row in key:
        if row["method_key"] not in detectors:
            continue
        stored = sheet_by_id[row["item_id"]]["released_text_shown_to_judge"]
        regenerated = surfaces[(row["method_key"], row["doc_id"])][:MAX_CHARS]
        checked += 1
        if stored != regenerated:
            mismatched += 1
            print(f"  MISMATCH item {row['item_id']} ({row['method_key']}, {row['doc_id']})")
    if mismatched:
        print(f"FAIL: {mismatched}/{checked} regenerated surfaces differ from the original sheet. "
              f"The local detector stack does not reproduce the run the judge scored, so these "
              f"items are withheld: an annotator would be shown text the judge never saw.")
        return 1
    print(f"[verify 2] all {checked} regenerated surfaces match the original sheet byte for byte")

    # --- emit the next item per reproducible method.
    additions = []
    for method in todo:
        pool = by_method.get(method, [])
        if extend_to is not None:
            # Continue the method's own shuffled order after every item already rated.
            batch = pool[rated[method]:extend_to]
            if len(batch) < extend_to - rated[method]:
                print(f"  {method}: pool holds only {len(pool)} items")
            additions.extend(batch)
            continue
        if len(pool) <= EXISTING_PER_METHOD:
            print(f"  {method}: pool exhausted, no further item available")
            continue
        additions.append(pool[EXISTING_PER_METHOD])
    if not additions:
        print("FAIL: nothing to add.")
        return 1
    if extend_to is not None:
        # The pool is read method by method; shuffling before ids are assigned
        # keeps neither position nor id from telling an annotator the method.
        random.Random(SEED + extend_to).shuffle(additions)

    used = {int(r["item_id"]) for r in key}
    for path in sorted(EXPERIMENTS_DIR.glob(f"semantic_inferability_human_key_topup*{suffix}.csv")):
        used |= {int(r["item_id"]) for r in _read(path)}
    start = max(used) + 1
    out_sheet = EXPERIMENTS_DIR / f"semantic_inferability_human_sheet_{out_suffix}{suffix}.csv"
    out_key = EXPERIMENTS_DIR / f"semantic_inferability_human_key_{out_suffix}{suffix}.csv"
    with out_sheet.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item_id", "released_text_shown_to_judge", "fact",
                         "human_inferable_YES_or_NO"])
        for offset, row in enumerate(additions):
            released = surfaces[(row["method_key"], row["doc_id"])][:MAX_CHARS]
            writer.writerow([start + offset, released, row["fact"], ""])
    with out_key.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item_id", "method_key", "doc_id", "fact_index",
                         "judge_inferable", "lexical_retained"])
        for offset, row in enumerate(additions):
            writer.writerow([start + offset, row["method_key"], row["doc_id"],
                             row["fact_index"], row["judge_inferable"], row["lexical_retained"]])

    print(f"\nwrote {out_sheet.name} ({len(additions)} items, ids {start}-{start + len(additions) - 1})")
    print(f"wrote {out_key.name} (verdicts withheld from the sheet)")
    # Count every prior top-up, not just the base key, or a later run misreports the total.
    print(f"subset would grow {len(used)} -> {len(used) + len(additions)}; "
          f"items per method: {dict(sorted(Counter(r['method_key'] for r in additions).items()))}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="vgpu3090")
    parser.add_argument("--methods", default=",".join(ALL_METHODS),
                        help="Comma-separated detector keys to consider")
    parser.add_argument("--out", default="topup", help="Output filename suffix")
    parser.add_argument("--extend-to", type=int, help="Grow every requested method to this many items")
    args = parser.parse_args()
    return run(args.tag, [m.strip() for m in args.methods.split(",") if m.strip()], args.out, args.extend_to)


if __name__ == "__main__":
    raise SystemExit(main())
