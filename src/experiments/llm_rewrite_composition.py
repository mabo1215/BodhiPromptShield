#!/usr/bin/env python3
"""What the language-model attacker's rewrites actually are, with explicit definitions.

Reads only the per-span rows of ``llm_rewrite_evasion_suite.py`` for the 32B
attacker. Nothing is rerun and no model is called.

Every (original, rewrite) pair falls in exactly one category, tested in order:

``unchanged``
    The rewrite is byte-identical to the original.
``punctuation_or_spacing_only``
    The sequence of alphanumeric characters is identical, case-sensitively.
``case_change_only``
    The alphanumeric sequence is identical only after case folding. Together
    with the previous category this is what the suite's own normalization
    (``_normalize``: casefold, alphanumerics only) calls the same value spelled
    with different punctuation.
``unicode_form_only``
    The alphanumeric sequence is identical only after NFKC folding as well
    (fullwidth digits and similar).
``original_kept_with_additions``
    The original's folded alphanumeric sequence appears, in order, inside the
    rewrite's, which also has extra letters or digits ("M (Male)", "457 (the
    original value is 457)", "a1s9t7r4i3d2a").
``letters_or_digits_changed``
    Everything else: substitutions, spell-outs, reformatting, reversals,
    truncations, and replies that lost the value.

Universes reported: the distinct (original, rewrite) pairs over all detectors
and rounds (the 2,839 of the supplement), every row, the distinct pairs of the
detector-blind first round, and the rewrites behind the value-preserving
evasions at round 3 per detector.

Digit spell-out, over rewrites of spans whose original contains a digit, is
reported under three explicit definitions: (a) the rewrite contains a digit word
zero to nine (or "oh") that the original does not; (b) the same with any English
number word; (c) definition (b) and the rewrite has fewer digit characters than
the original.

The supplement's "change only punctuation or spacing (38%)" is not reproduced
by any of the categories above, and no record says how it was computed. Two
looser measures that happen to land near 38% are written out on the first
universe, labelled ``candidate_38_percent_*``. They are post-hoc matches, not
evidence of how the figure was obtained, and neither means what the sentence
says: the first lets letters change whenever the digits survive
("19th October 1981" -> "19. October, 1981"), and the second compares the rewrite
with its own decoding rather than with the original.

Output, next to the records:
``llm_rewrite_evasion_composition_qwen3_32b-q4km-hf.csv``
"""
from __future__ import annotations

import collections
import csv
import re
import unicodedata
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
ATTACKER = "qwen3_32b-q4km-hf"
ROWS_PATH = EXPERIMENTS_DIR / f"llm_rewrite_evasion_spans_{ATTACKER}.csv"
OUT_PATH = EXPERIMENTS_DIR / f"llm_rewrite_evasion_composition_{ATTACKER}.csv"

CATEGORIES = ["unchanged", "punctuation_or_spacing_only", "case_change_only", "unicode_form_only",
              "original_kept_with_additions", "letters_or_digits_changed"]

DIGIT_WORD = re.compile(r"\b(zero|one|two|three|four|five|six|seven|eight|nine|oh)\b", re.I)
NUMBER_WORD = re.compile(r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
                         r"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|"
                         r"sixty|seventy|eighty|ninety|hundred|thousand|million|oh|nought)\b", re.I)


def _alnum(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum())


def _folded(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def _nfkc_folded(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKC", value).casefold() if ch.isalnum())


def _is_subsequence(needle: str, haystack: str) -> bool:
    it = iter(haystack)
    return all(ch in it for ch in needle)


def categorize(original: str, rewrite: str) -> str:
    if rewrite == original:
        return "unchanged"
    if _alnum(rewrite) == _alnum(original):
        return "punctuation_or_spacing_only"
    if _folded(rewrite) == _folded(original):
        return "case_change_only"
    if _nfkc_folded(rewrite) == _nfkc_folded(original):
        return "unicode_form_only"
    if _is_subsequence(_nfkc_folded(original), _nfkc_folded(rewrite)):
        return "original_kept_with_additions"
    return "letters_or_digits_changed"


def _digits(value: str) -> int:
    return sum(ch.isdigit() for ch in value)


def composition_rows(universe: str, pairs: list[tuple[str, str]]) -> list[dict]:
    counts = collections.Counter(categorize(o, w) for o, w in pairs)
    n = len(pairs)
    rows = [{"universe": universe, "measure": cat, "numerator": counts[cat], "denominator": n,
             "percent": f"{100.0 * counts[cat] / n:.1f}" if n else ""} for cat in CATEGORIES]
    same_value = counts["punctuation_or_spacing_only"] + counts["case_change_only"]
    for name, value in (("suite_rule_changed_but_same_alphanumerics", same_value),
                        ("suite_rule_same_alphanumerics_including_unchanged", same_value + counts["unchanged"]),
                        ("nfkc_changed_but_same_alphanumerics", same_value + counts["unicode_form_only"])):
        rows.append({"universe": universe, "measure": name, "numerator": value, "denominator": n,
                     "percent": f"{100.0 * value / n:.1f}" if n else ""})
    return rows


def spellout_rows(universe: str, pairs: list[tuple[str, str]]) -> list[dict]:
    with_digit = [(o, w) for o, w in pairs if any(ch.isdigit() for ch in o)]
    n = len(with_digit)
    a = sum(1 for o, w in with_digit if DIGIT_WORD.search(w) and not DIGIT_WORD.search(o))
    b_pairs = [(o, w) for o, w in with_digit if NUMBER_WORD.search(w) and not NUMBER_WORD.search(o)]
    c = sum(1 for o, w in b_pairs if _digits(w) < _digits(o))
    return [{"universe": universe, "measure": name, "numerator": value, "denominator": n,
             "percent": f"{100.0 * value / n:.1f}" if n else ""}
            for name, value in (("digit_spellout_a_digit_word", a),
                                ("digit_spellout_b_any_number_word", len(b_pairs)),
                                ("digit_spellout_c_number_word_and_fewer_digits", c))]


def main() -> int:
    with ROWS_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    pair = lambda r: (r["original"], r["rewrite"])
    distinct = sorted({pair(r) for r in rows if r["rewrite"]})
    out: list[dict] = []
    universes = [
        ("distinct_pairs_all_detectors_all_rounds", distinct),
        ("all_rows", [pair(r) for r in rows if r["rewrite"]]),
        ("distinct_pairs_round_1", sorted({pair(r) for r in rows if r["rewrite"] and r["round"] == "1"})),
        ("distinct_pairs_any_row_value_preserved",
         sorted({pair(r) for r in rows if r["rewrite"] and r["preserved"] == "1"})),
    ]
    for universe, pairs in universes:
        out += composition_rows(universe, pairs)
        out += spellout_rows(universe, pairs)
    decoded_of = {pair(r): r["decoded"] for r in rows}

    def digits_or_letters_kept(original: str, rewrite: str) -> bool:
        digits = [ch for ch in original if ch.isdigit()]
        if digits:
            return digits == [ch for ch in rewrite if ch.isdigit()]
        return [ch for ch in original.casefold() if ch.isalpha()] == [
            ch for ch in rewrite.casefold() if ch.isalpha()]

    candidates = (
        ("candidate_38_percent_changed_digits_kept_else_letters_kept",
         sum(1 for o, w in distinct if w != o and digits_or_letters_kept(o, w))),
        ("candidate_38_percent_changed_rewrite_equals_own_decoding",
         sum(1 for o, w in distinct if w != o and _folded(w) == _folded(decoded_of[(o, w)]))),
    )
    for name, value in candidates:
        out.append({"universe": "distinct_pairs_all_detectors_all_rounds", "measure": name,
                    "numerator": value, "denominator": len(distinct),
                    "percent": f"{100.0 * value / len(distinct):.1f}"})
    # What actually got past each detector: the rows counted by the
    # value-preserving ASR after three rounds.
    for detector in sorted({r["detector"] for r in rows}):
        evading = [pair(r) for r in rows if r["detector"] == detector and r["round"] == "3"
                   and r["caught_clean"] == "1" and r["caught_attacked"] == "0" and r["preserved"] == "1"]
        out += composition_rows(f"value_preserving_evasions_round_3_{detector}", evading)
        out += spellout_rows(f"value_preserving_evasions_round_3_{detector}", evading)
    with OUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["universe", "measure", "numerator", "denominator", "percent"])
        writer.writeheader()
        writer.writerows(out)
    for row in out:
        print(f"  {row['universe']:<58} {row['measure']:<52} "
              f"{row['numerator']:>5}/{row['denominator']:<5} {row['percent']:>5}")
    print(f"wrote {OUT_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
