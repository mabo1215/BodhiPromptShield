#!/usr/bin/env python3
"""Rescore the lexical fact-retention flag of the inferability records with whole-word matching.

The lexical criterion first matched a fact's content words as substrings, so
``care`` counted as present inside ``healthcare``; it now matches whole words.
The judge verdicts and human labels do not depend on it, so only the flag is
recomputed: the released surfaces are rebuilt exactly as the judge suite built
them, and the rescoring refuses to write anything unless every rebuilt surface
has the recorded length and reproduces every recorded flag under the old
substring rule. The old flag is kept beside the new one.

Updated in place: the judge rows and the four human-key files, which carry the
flag for the annotated items. Run the agreement scripts afterwards to refresh
the kappas and per-method rates.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from propagation_suite import _load_documents, fact_retained
from semantic_inferability_judge import _released_surfaces


EXPERIMENTS_DIR = Path(__file__).resolve().parent
TAG = "vgpu3090"
ROWS = EXPERIMENTS_DIR / f"semantic_inferability_rows_{TAG}.csv"
KEYS = [EXPERIMENTS_DIR / f"semantic_inferability_human_key{s}_{TAG}.csv" for s in ("", "_topup", "_topup2", "_extend40")]
OLD = "lexical_retained_substring"


def _read(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _with_old(fields: list[str]) -> list[str]:
    if OLD in fields:
        return fields
    i = fields.index("lexical_retained") + 1
    return fields[:i] + [OLD] + fields[i:]


def main() -> int:
    fields, rows = _read(ROWS)
    if OLD in fields:
        print(f"{ROWS.name} is already rescored; nothing to do")
        return 0
    doc_ids = {r["doc_id"] for r in rows}
    methods = list(dict.fromkeys(r["method_key"] for r in rows))
    docs = [d for d in _load_documents("privacylens", None) if d["doc_id"] in doc_ids]
    surfaces = _released_surfaces(docs, methods, "en_core_web_lg")

    mismatches = 0
    new: dict[tuple[str, str, str], int] = {}
    for r in rows:
        released = surfaces[(r["method_key"], r["doc_id"])]
        old = int(fact_retained(released, r["fact"], whole_words=False))
        if len(released) != int(r["released_chars"]) or old != int(r["lexical_retained"]):
            mismatches += 1
            continue
        new[(r["method_key"], r["doc_id"], r["fact_index"])] = int(fact_retained(released, r["fact"]))
    if mismatches:
        print(f"[refuse] {mismatches} of {len(rows)} rows do not reproduce from the rebuilt surfaces; nothing written")
        return 1
    print(f"[check] all {len(rows)} rows reproduce their recorded surface length and substring flag")

    for r in rows:
        r[OLD] = r["lexical_retained"]
        r["lexical_retained"] = str(new[(r["method_key"], r["doc_id"], r["fact_index"])])
    _write(ROWS, _with_old(fields), rows)
    changed = sum(1 for r in rows if r[OLD] != r["lexical_retained"])
    print(f"[rows] {ROWS.name}: {changed} of {len(rows)} flags changed")

    for path in KEYS:
        kfields, krows = _read(path)
        for r in krows:
            r[OLD] = r["lexical_retained"]
            r["lexical_retained"] = str(new[(r["method_key"], r["doc_id"], r["fact_index"])])
        _write(path, _with_old(kfields), krows)
        print(f"[key] {path.name}: {sum(1 for r in krows if r[OLD] != r['lexical_retained'])} of {len(krows)} changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
