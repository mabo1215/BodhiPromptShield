#!/usr/bin/env python3
"""Recompute whether a blanked value is really still readable in each release.

The attribute-recovery attack first recorded ``survives_release`` with a plain
substring test on the released text. That over-counts in three ways:

* a short number answer matches inside a replacement token ("15" in
  ``<PROTECTED_15>``, "1" in ``<PERSON_1>``);
* it matches inside the planted Casper-style stand-ins ("12" and "2001" in
  ``12 March 2001``);
* it matches inside longer words and numbers ("1" in "2001", "John" in "Johnson").

It also under-counts, since a release that keeps "Dave" and masks "Thompson" counts
as having removed "Dave Thompson". This script regenerates every release with the
same code path the attack used (no attacker and no language model are involved: the
detectors are rules, spaCy, Presidio, and the logistic-regression tagger), checks the
regenerated text against the recorded flag on every question, and writes the corrected
flags. The original rows are never modified and the attacker replies are reused
unchanged, so recovery itself does not move: only which questions count as "absent".

Outputs, all next to this script:

* ``privacylens_attribute_recovery_presence_by_question.csv``: one row per
  (condition, case, fact), written incrementally so that a run can resume;
* ``privacylens_attribute_recovery_rows_<attacker>_corrected.csv``: the recorded rows
  with ``survives_release`` set by the corrected rule and the recorded flag kept as
  ``survives_release_substring``. Every analysis downstream reads these;
* ``privacylens_attribute_recovery_{summary,paired}_<attacker>_corrected.csv``: the
  attack's own scoring applied to the corrected rows;
* ``privacylens_attribute_recovery_presence_summary.csv``,
  ``privacylens_attribute_recovery_presence_by_kind.csv``: recovery, value present, and
  recovery when absent under each presence rule, so the choice of rule can be checked;
* ``privacylens_attribute_recovery_presence_capacity.csv``: paired differences between
  adjacent attackers on absent questions under each rule;
* ``privacylens_attribute_recovery_presence_validation.csv``: agreement between the
  regenerated substring rule and the recorded flag.

Run with the project's virtual environment, which holds the detector stack:

    python src/experiments/attribute_recovery_presence_audit.py
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENTS_DIR))

from downstream_paired_tests import paired_bootstrap_diff  # noqa: E402
from mediation_baselines import bootstrap_ratio_ci, build_detectors  # noqa: E402
from privacylens_attribute_recovery_attack import (  # noqa: E402
    _build_questions,
    _paired,
    _score,
    strip_layer_text,
    value_present,
    word_in,
)
from privacylens_downstream_suite import Condition, PL_DATA, _train_learned_detector  # noqa: E402

ATTACKERS = (
    ("qwen3_8b-q4km-hf", "8B"),
    ("qwen3_32b-q4km-hf", "32B"),
    ("llama3.3_70b-q4km-hf", "70B"),
)
CONDITIONS = ("no_protection", "placeholder:presidio", "casper_style", "placeholder:learned_lr")
OPTIONS = 4
SEED = 17

FIELDS = ["condition", "case", "fact_index", "span_kind", "answer", "substring_rule",
          "outside_markers", "whole_word", "any_token_whole_word"]


def presence(answer: str, released: str, condition: str) -> dict[str, int]:
    """Whether ``answer`` is readable in the release, under each rule."""
    clean = strip_layer_text(released, condition)
    return {
        "substring_rule": int(answer in released),
        "outside_markers": int(answer in clean),
        "whole_word": int(word_in(answer, clean)),
        "any_token_whole_word": int(value_present(answer, released, condition)),
    }


def regenerate(out: Path, spacy_model: str) -> list[dict[str, str]]:
    done: set[tuple[str, str, str]] = set()
    if out.exists():
        with out.open(encoding="utf-8", newline="") as handle:
            done = {(r["condition"], r["case"], r["fact_index"]) for r in csv.DictReader(handle)}

    cases = json.load(open(PL_DATA, encoding="utf-8"))
    questions, dropped = _build_questions(cases, OPTIONS, SEED)
    print(f"[presence] {len(questions)} questions, {dropped} facts dropped", flush=True)
    expected = len(questions) * len(CONDITIONS)
    if len(done) < expected:
        print("[presence] training the learned detector", flush=True)
        learned = _train_learned_detector()
        detectors = {d.key: d for d in build_detectors(
            ["presidio", "casper_style", "learned_lr"], learned_weights=learned, spacy_model=spacy_model)}
        by_name = {c["name"]: c for c in cases}
        by_case: dict[str, list[dict]] = collections.defaultdict(list)
        for question in questions:
            by_case[question["case"]].append(question)
        write_header = not out.exists() or out.stat().st_size == 0
        with out.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            if write_header:
                writer.writeheader()
                handle.flush()
            for spec in CONDITIONS:
                cond = Condition(spec, detectors, "http://127.0.0.1:11434", spacy_model)
                for n, (case_name, items) in enumerate(by_case.items(), 1):
                    pending = [q for q in items if (spec, case_name, str(q["fact_index"])) not in done]
                    if not pending:
                        continue
                    tr = by_name[case_name]["trajectory"]
                    instr, traj, _map, _mode = cond.apply(
                        case_name, tr.get("user_instruction", ""), tr.get("executable_trajectory", ""))
                    released = f"{instr}\n\n{traj}"
                    for question in pending:
                        writer.writerow({
                            "condition": spec, "case": case_name, "fact_index": question["fact_index"],
                            "span_kind": question["span_kind"], "answer": question["answer"],
                            **presence(question["answer"], released, spec)})
                    handle.flush()
                    os.fsync(handle.fileno())
                    if n % 50 == 0:
                        print(f"  {spec}: {n}/{len(by_case)} cases", flush=True)
    with out.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _rows(tag: str) -> list[dict[str, str]]:
    path = EXPERIMENTS_DIR / f"privacylens_attribute_recovery_rows_{tag}.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _ratio(rows: list[dict[str, str]], value, n_boot: int) -> tuple[str, int]:
    by_case: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        by_case[row["case"]].append(value(row))
    pairs = [(sum(v), float(len(v))) for v in by_case.values()]
    if not pairs:
        return "", 0
    point, lo, hi = bootstrap_ratio_ci(pairs, n_boot=n_boot, scale=100.0)
    return f"{point:.1f} [{lo:.1f}, {hi:.1f}]", int(sum(d for _, d in pairs))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--spacy-model", default="en_core_web_lg")
    parser.add_argument("--bootstrap", type=int, default=1000)
    args = parser.parse_args()

    flags_path = EXPERIMENTS_DIR / "privacylens_attribute_recovery_presence_by_question.csv"
    flags = regenerate(flags_path, args.spacy_model)
    keyed = {(r["condition"], r["case"], r["fact_index"]): r for r in flags}

    # Validation: the regenerated substring rule must equal the recorded flag.
    with (EXPERIMENTS_DIR / "privacylens_attribute_recovery_presence_validation.csv").open(
            "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["attacker", "condition", "questions", "regenerated_matches_recorded_flag", "disagreements"])
        for tag, _label in ATTACKERS:
            rows = _rows(tag)
            for cond in CONDITIONS:
                sub = [r for r in rows if r["condition"] == cond]
                same = sum(keyed[(r["condition"], r["case"], r["fact_index"])]["substring_rule"]
                           == r["survives_release"] for r in sub)
                writer.writerow([tag, cond, len(sub), same, len(sub) - same])
                print(f"[validate] {tag} {cond}: {same}/{len(sub)} match", flush=True)

    # Corrected rows and the attack's own scoring applied to them.
    for tag, _label in ATTACKERS:
        rows = _rows(tag)
        corrected = EXPERIMENTS_DIR / f"privacylens_attribute_recovery_rows_{tag}_corrected.csv"
        with corrected.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]) + ["survives_release_substring"])
            writer.writeheader()
            for row in rows:
                flag = keyed[(row["condition"], row["case"], row["fact_index"])]["any_token_whole_word"]
                writer.writerow({**row, "survives_release": flag, "survives_release_substring": row["survives_release"]})
        print(f"[presence] rescoring {tag}", flush=True)
        _score(corrected, EXPERIMENTS_DIR / f"privacylens_attribute_recovery_summary_{tag}_corrected.csv",
               OPTIONS, args.bootstrap)
        _paired(corrected, EXPERIMENTS_DIR / f"privacylens_attribute_recovery_paired_{tag}_corrected.csv",
                args.bootstrap)

    rule_names = ("substring_rule", "outside_markers", "whole_word", "any_token_whole_word")
    for name, kinds in (("summary", ("all",)), ("by_kind", ("all", "identifier", "number", "entity"))):
        with (EXPERIMENTS_DIR / f"privacylens_attribute_recovery_presence_{name}.csv").open(
                "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            header = ["attacker", "condition", "span_kind", "questions_answered", "recovery_percent"]
            for rule in rule_names:
                header += [f"present_{rule}", f"questions_absent_{rule}", f"recovery_when_absent_{rule}"]
            writer.writerow(header)
            for tag, _label in ATTACKERS:
                rows = [r for r in _rows(tag) if r["chosen_option"]]
                for cond in CONDITIONS:
                    for kind in kinds:
                        sub = [r for r in rows if r["condition"] == cond and (kind == "all" or r["span_kind"] == kind)]
                        recovery, answered = _ratio(sub, lambda r: float(r["correct"]), args.bootstrap)
                        line: list[object] = [tag, cond, kind, answered, recovery]
                        for rule in rule_names:
                            flag = lambda r, rule=rule: int(keyed[(r["condition"], r["case"], r["fact_index"])][rule])
                            present, _ = _ratio(sub, lambda r: float(flag(r)), args.bootstrap)
                            absent = [r for r in sub if not flag(r)]
                            rec_absent, n_absent = _ratio(absent, lambda r: float(r["correct"]), args.bootstrap)
                            line += [present, n_absent, rec_absent]
                        writer.writerow(line)

    # Paired differences between adjacent attackers on absent questions. The
    # value-absent set is a property of the release, so it is the same for every attacker.
    with (EXPERIMENTS_DIR / "privacylens_attribute_recovery_presence_capacity.csv").open(
            "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["comparison", "condition", "rule", "questions_paired", "cases",
                         "difference_percentage_points", "excludes_zero"])
        loaded = [(tag, label, {(r["condition"], r["case"], r["fact_index"]): r
                                for r in _rows(tag) if r["chosen_option"]}) for tag, label in ATTACKERS]
        for (_ta, la, ra), (_tb, lb, rb) in zip(loaded, loaded[1:]):
            for cond in CONDITIONS:
                for rule in ("substring_rule", "whole_word", "any_token_whole_word"):
                    per_case: dict[str, list[float]] = {}
                    for key, row in rb.items():
                        if key[0] != cond or key not in ra or int(keyed[key][rule]):
                            continue
                        acc = per_case.setdefault(key[1], [0.0, 0.0, 0.0, 0.0])
                        acc[0] += float(row["correct"])
                        acc[1] += 1.0
                        acc[2] += float(ra[key]["correct"])
                        acc[3] += 1.0
                    pairs = [tuple(v) for v in per_case.values()]
                    point, lo, hi = paired_bootstrap_diff(pairs, n_boot=args.bootstrap, scale=100.0)
                    excludes = "yes" if (lo > 0 and hi > 0) or (lo < 0 and hi < 0) else "no"
                    writer.writerow([f"{lb} - {la}", cond, rule, int(sum(p[1] for p in pairs)), len(pairs),
                                     f"{point:+.1f} [{lo:+.1f}, {hi:+.1f}]", excludes])
    print("[presence] wrote summary, by_kind, capacity, and validation records", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
