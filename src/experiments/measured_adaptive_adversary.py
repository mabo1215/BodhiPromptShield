#!/usr/bin/env python3
"""Measured adaptive surface-form adversary against the real mediation mechanism.

Reviewer concern #2: the named adaptive prompt adversary is not exercised with a
measured success rate against the actual mechanism. This script gives the
adversary concrete capabilities and measures, on *real* prompt text (AI4Privacy
English test slice with gold PII spans), how often each attack causes a sensitive
span that the deployed detector would otherwise catch to *evade* detection (and
thus propagate). Both the released heuristic detector and the stronger learned
detector are attacked, so the result reports the residual evasion surface of the
actual mechanism rather than a toy probe.

Adversary capabilities (applied to the sensitive span surface in real text)
---------------------------------------------------------------------------
* Homoglyph substitution  : Latin -> Cyrillic/Greek confusables.
* Zero-width insertion     : U+200B inserted between characters.
* Intra-token spacing      : single spaces inserted between characters.
* Case inversion           : per-character case flip.
* Leetspeak                : a->4 e->3 i->1 o->0 s->5 (letters only).
* Separator injection      : spaces inserted inside digit runs (structured ids).

Metrics (measured, per attack family x detector)
------------------------------------------------
* clean_recall    : fraction of applicable spans the detector catches unmutated.
* attacked_recall : fraction of mutated applicable spans still caught.
* attack_success_rate (ASR) : fraction of *previously-caught* spans the attack
  pushes to evade = max(0, (caught_clean - caught_attacked) / caught_clean).
"""
from __future__ import annotations

import csv
from pathlib import Path

from ai4privacy_matched_baseline_suite import _load_records
from ai4privacy_matched_baseline_suite import _policy_aware_spans

import ai4privacy_lightweight_classifier_baseline as clf


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = EXPERIMENTS_DIR / "ai4privacy_pii300k_english_export.jsonl"
RESULTS_PATH = EXPERIMENTS_DIR / "measured_adaptive_adversary_results.csv"
RUNTIME_PATH = EXPERIMENTS_DIR / "measured_adaptive_adversary_runtime_manifest.csv"

SPLIT = "ai4privacy-test"
MAX_DOCS = 200

HOMOGLYPH = {
    "a": "а", "e": "е", "i": "і", "o": "о", "p": "р",
    "c": "с", "x": "х", "y": "у", "A": "А", "E": "Е",
    "O": "О", "P": "Р", "C": "С", "X": "Х",
}
LEET = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "A": "4", "E": "3", "O": "0", "S": "5"}


def _has_alpha(s: str) -> bool:
    return any(ch.isalpha() for ch in s)


def _has_digit_run(s: str) -> bool:
    run = 0
    for ch in s:
        run = run + 1 if ch.isdigit() else 0
        if run >= 3:
            return True
    return False


def _has_alnum(s: str) -> bool:
    return any(ch.isalnum() for ch in s)


DIGIT_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}


def _mut_homoglyph(s: str) -> str:
    return "".join(HOMOGLYPH.get(ch, ch) for ch in s)


def _mut_zerowidth(s: str) -> str:
    return "​".join(s)


def _mut_spacing(s: str) -> str:
    return " ".join(s)


def _mut_case(s: str) -> str:
    return "".join(ch.lower() if ch.isupper() else ch.upper() for ch in s)


def _mut_leet(s: str) -> str:
    return "".join(LEET.get(ch, ch) for ch in s)


def _mut_separator(s: str) -> str:
    return " ".join(s)  # break digit runs with spaces


def _mut_fullwidth(s: str) -> str:
    out = []
    for ch in s:
        code = ord(ch)
        if 0x21 <= code <= 0x7E:
            out.append(chr(code + 0xFEE0))  # ASCII -> fullwidth
        elif ch == " ":
            out.append("　")  # ideographic space
        else:
            out.append(ch)
    return "".join(out)


def _mut_spell_digits(s: str) -> str:
    return "".join(DIGIT_WORDS[ch] + " " if ch in DIGIT_WORDS else ch for ch in s)


ATTACKS = [
    ("Homoglyph substitution", _mut_homoglyph, _has_alpha),
    ("Zero-width insertion", _mut_zerowidth, _has_alpha),
    ("Intra-token spacing", _mut_spacing, _has_alpha),
    ("Case inversion", _mut_case, _has_alpha),
    ("Leetspeak", _mut_leet, _has_alpha),
    ("Separator injection (ids)", _mut_separator, _has_digit_run),
    ("Mixed-language fullwidth", _mut_fullwidth, _has_alnum),
    ("Paraphrase (digit spell-out)", _mut_spell_digits, _has_digit_run),
]


def _covered(span: tuple[int, int], detected: list[tuple[int, int]]) -> bool:
    a, b = span
    for x, y in detected:
        if min(b, y) - max(a, x) > 0:
            return True
    return False


def _build_mutation(text: str, spans: list[tuple[int, int]], mutate, applies) -> tuple[str, list[tuple[int, int]]]:
    """Rebuild text with applicable spans mutated; return new text + new span ranges."""
    out = []
    new_spans: list[tuple[int, int]] = []
    cursor = 0
    pos = 0
    for start, end in sorted(spans):
        out.append(text[cursor:start]); pos += start - cursor
        original = text[start:end]
        if applies(original):
            mutated = mutate(original)
        else:
            mutated = original
        new_spans.append((pos, pos + len(mutated)))
        out.append(mutated); pos += len(mutated)
        cursor = end
    out.append(text[cursor:])
    return "".join(out), new_spans


def evaluate(input_path: Path) -> None:
    records = [r for r in _load_records(input_path) if str(r.get("split")) == SPLIT][:MAX_DOCS]
    if not records:
        raise ValueError("No AI4Privacy records selected.")

    # Train the learned detector once.
    all_records = clf._load_records(input_path)
    train_records = [r for r in all_records if str(r.get("split")) == "ai4privacy-train"][: clf.TRAIN_DOC_LIMIT]
    learned_weights, _ = clf._train_logreg(clf._build_examples(train_records))

    detectors = {
        "Released heuristic detector": lambda t: _policy_aware_spans(t),
        "Learned detector": lambda t: clf._predict_spans(learned_weights, t),
    }

    rows = []
    for det_name, detector in detectors.items():
        for attack_name, mutate, applies in ATTACKS:
            caught_clean = caught_attacked = applicable = 0
            for record in records:
                text = str(record.get("text", ""))
                gold = [
                    (int(s["start"]), int(s["end"]))
                    for s in record.get("phi_spans", [])
                    if isinstance(s, dict)
                ]
                app_idx = [i for i, (a, b) in enumerate(gold) if applies(text[a:b])]
                if not app_idx:
                    continue
                # Clean detection.
                det_clean = detector(text)
                for i in app_idx:
                    if _covered(gold[i], det_clean):
                        caught_clean += 1
                # Attacked detection.
                mut_text, new_spans = _build_mutation(text, gold, mutate, applies)
                det_mut = detector(mut_text)
                for i in app_idx:
                    applicable += 1
                    if _covered(new_spans[i], det_mut):
                        caught_attacked += 1
            clean_recall = caught_clean / applicable if applicable else 0.0
            attacked_recall = caught_attacked / applicable if applicable else 0.0
            asr = max(0.0, (caught_clean - caught_attacked) / caught_clean) if caught_clean else 0.0
            rows.append(
                {
                    "detector": det_name,
                    "attack_family": attack_name,
                    "applicable_spans": str(applicable),
                    "clean_recall": f"{clean_recall:.2f}",
                    "attacked_recall": f"{attacked_recall:.2f}",
                    "attack_success_rate": f"{100.0 * asr:.1f}",
                }
            )

    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "detector",
                "attack_family",
                "applicable_spans",
                "clean_recall",
                "attacked_recall",
                "attack_success_rate",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    runtime_rows = [
        {"field": "benchmark", "value": "AI4Privacy PII-Masking-300K (English) test slice, real text + gold spans"},
        {"field": "split", "value": SPLIT},
        {"field": "documents", "value": str(len(records))},
        {"field": "detectors", "value": "Released heuristic policy-aware detector; learned logistic detector"},
        {"field": "attacks", "value": "; ".join(a[0] for a in ATTACKS)},
        {"field": "asr_definition", "value": "Fraction of previously-caught applicable spans pushed to evade by the attack"},
        {"field": "llm_in_loop", "value": "None; measurement is exact against the real detector"},
        {"field": "dependencies", "value": "Pure Python standard library + repository detection helpers"},
    ]
    with RUNTIME_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "value"])
        writer.writeheader()
        writer.writerows(runtime_rows)

    print(f"Measured adaptive-adversary results written to {RESULTS_PATH}")
    for row in rows:
        print(
            f"  {row['detector']:28s} {row['attack_family']:26s} "
            f"clean={row['clean_recall']} atk={row['attacked_recall']} ASR={row['attack_success_rate']}%"
        )


def main() -> int:
    evaluate(DEFAULT_INPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
