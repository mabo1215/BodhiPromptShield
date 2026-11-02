"""Does the attribute-recovery result depend on how strong the attacker is?

The paper's own judge sweep is why this exists: capacity moved judge agreement
with human labels from 0.087 to 0.491, nearly fivefold, so a recovery number
from a single attacker invites exactly that objection.

The comparison is unusually clean here. Question construction is seeded, so
every attacker is posed the identical questions -- the same blanked values in
the same candidate slots -- and the runs can therefore be paired on the
question rather than merely compared under a shared protocol. This checks that
set-equality rather than assuming it, and refuses to pair runs that disagree.

Two outputs: the capacity table the appendix renders, and the paired
differences between attackers on the questions whose value the detector
removed, which is the column the finding rests on.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENTS_DIR))

from downstream_paired_tests import paired_bootstrap_diff  # noqa: E402

# Ordered weakest to strongest, which is the order a reader should see.
ATTACKERS = (
    ("qwen3_8b-q4km-hf", "Qwen3 8B"),
    ("qwen3_32b-q4km-hf", "Qwen3 32B"),
    ("llama3.3_70b-q4km-hf", "Llama 3.3 70B"),
)
CONDITIONS = ("no_protection", "placeholder:presidio", "casper_style", "placeholder:learned_lr")


def _rows(tag: str) -> list[dict[str, str]] | None:
    path = EXPERIMENTS_DIR / f"privacylens_attribute_recovery_rows_{tag}_corrected.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _design(rows: list[dict[str, str]]) -> dict[tuple[str, str], tuple[str, str]]:
    """How each question was posed: which value was blanked and where it sat."""
    return {(r["case"], r["fact_index"]): (r["answer"], r["correct_option"]) for r in rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--out", default=str(
        EXPERIMENTS_DIR / "privacylens_attribute_recovery_capacity.csv"))
    args = parser.parse_args()

    loaded: list[tuple[str, str, list[dict[str, str]]]] = []
    for tag, label in ATTACKERS:
        rows = _rows(tag)
        if rows is None:
            print(f"[capacity] {label}: no record yet, skipping")
            continue
        loaded.append((tag, label, rows))
    if len(loaded) < 2:
        print("[capacity] need at least two attackers to compare")
        return 1

    # Pairing is legitimate only if the questions were posed the same way. A run
    # still in progress has answered fewer of them, which is fine -- the pairing
    # below intersects. What is not fine is the same question carrying a
    # different blanked value or a different answer slot, because then the two
    # attackers were not asked the same thing.
    reference = _design(loaded[0][2])
    for _tag, label, rows in loaded[1:]:
        design = _design(rows)
        shared = reference.keys() & design.keys()
        clashes = [k for k in shared if reference[k] != design[k]]
        if clashes:
            raise SystemExit(
                f"[capacity] {label} poses {len(clashes)} of {len(shared)} shared questions "
                f"differently; these runs cannot be paired. Re-run it with the same --seed and "
                f"--options.")
        if len(design) < len(reference):
            print(f"[capacity] {label}: {len(design)} of {len(reference)} questions so far "
                  f"(run in progress); pairing on what it has answered")
    print(f"[capacity] {len(loaded)} attackers, question design identical where they overlap")

    with Path(args.out).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["comparison", "condition", "questions_paired",
                         "difference_percentage_points", "excludes_zero"])
        for i in range(len(loaded) - 1):
            _t_a, label_a, rows_a = loaded[i]
            _t_b, label_b, rows_b = loaded[i + 1]
            index_a = {(r["condition"], r["case"], r["fact_index"]): r for r in rows_a}
            index_b = {(r["condition"], r["case"], r["fact_index"]): r for r in rows_b}
            for cond in CONDITIONS:
                per_case: dict[str, list[float]] = {}
                for key, row_a in index_a.items():
                    if key[0] != cond or not row_a["chosen_option"]:
                        continue
                    row_b = index_b.get(key)
                    if row_b is None or not row_b["chosen_option"]:
                        continue
                    # Restrict to questions whose value the release removed: on
                    # those the answer cannot be read, only inferred.
                    if row_a["survives_release"] != "0" or row_b["survives_release"] != "0":
                        continue
                    acc = per_case.setdefault(key[1], [0.0, 0.0, 0.0, 0.0])
                    acc[0] += float(row_b["correct"]); acc[1] += 1.0
                    acc[2] += float(row_a["correct"]); acc[3] += 1.0
                pairs = [tuple(v) for v in per_case.values()]
                if not pairs:
                    continue
                point, lo, hi = paired_bootstrap_diff(pairs, n_boot=args.bootstrap, scale=100.0)
                excludes = "yes" if (lo > 0 and hi > 0) or (lo < 0 and hi < 0) else "no"
                questions = int(sum(p[1] for p in pairs))
                name = f"{label_b} - {label_a}"
                print(f"  {name:<28} {cond:<24} {point:+6.1f} [{lo:+.1f}, {hi:+.1f}]  "
                      f"n={questions}  excludes zero: {excludes}")
                writer.writerow([name, cond, questions,
                                 f"{point:+.1f} [{lo:+.1f}, {hi:+.1f}]", excludes])
    print(f"[capacity] wrote {Path(args.out).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
