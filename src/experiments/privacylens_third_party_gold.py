#!/usr/bin/env python3
"""Measure exposure on PrivacyLens against the people the secrets are about.

The PrivacyLens identifier gold is e-mail and digit-run regex matches plus the
user's own name and e-mail. Gold defined by regexes favours rule-based detectors,
and it leaves out third-party names, who are the subjects of the benchmark's
secrets. This adds a second gold set, third-party person names, and reports PER
under both, for every detector of the exposure table, on the same 493 cases and
with the same per-stage detection as that table.

A mention of a third-party name is any of:

* a title followed by a capitalized name (``Dr. Stanton``); the title is not gold;
* a capitalized word in a public first-name list, excluding the listed words that
  are ordinary vocabulary or places in this benchmark (``NOT_PERSON``), together
  with a capitalized word directly after it, which is taken as a surname;
* a surname established by either rule, wherever else it occurs in the same case.

Tokens of the user's own name are excluded, since the first gold set covers them.
The rule uses no detector and no statistical model, so it does not favour any row
of the table; it is a rule, not an annotation, so its precision is measured by
reading a seeded sample of its mentions (``--write-sample``).

Before anything is reported, the identifier-gold counts of every detector on every
case must equal the exposure table's per-document records, which is what makes the
second column comparable with the first. The script refuses to summarize otherwise.

Outputs, next to the records:

* ``privacylens_third_party_gold_documents.csv``: one row per (method, case),
  appended and flushed per case so that a run can resume;
* ``privacylens_third_party_gold_summary.csv``: PER under each gold set, with
  case-level bootstrap intervals;
* ``privacylens_third_party_gold_mentions_sample.csv``: the sample to read.

The first names are the NLTK names corpus, version 1.3, Copyright (C) 1991 Mark
Kantrowitz, additions by Bill Ross, redistributed with its README in ``names_corpus``.

Run with the project's virtual environment, which holds the detector stack.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENTS_DIR))

from ai4privacy_matched_baseline_suite import _char_coverage, _merge_spans  # noqa: E402
from mediation_baselines import bootstrap_ratio_ci, build_detectors  # noqa: E402
from measured_agent_propagation import MARKER, _sanitize  # noqa: E402
from measured_privacylens_propagation import _gold_spans  # noqa: E402
from propagation_suite import PL_PATH, _load_documents, _train_learned_detector  # noqa: E402

DOCUMENTS = EXPERIMENTS_DIR / "privacylens_third_party_gold_documents.csv"
SUMMARY = EXPERIMENTS_DIR / "privacylens_third_party_gold_summary.csv"
SAMPLE = EXPERIMENTS_DIR / "privacylens_third_party_gold_mentions_sample.csv"
NAMES_DIR = EXPERIMENTS_DIR / "names_corpus"
PARITY_METHOD = "parity_tagger"
METHODS = ("no_protection", "regex_only", "capitalization_heuristic", "spacy_ner", "presidio", "casper_style",
           "heuristic_mediator", "gliner_pii", "learned_lr", "llm_sanitizer:qwen3:8b-q4km-hf", PARITY_METHOD)
FIELDS = ["method_key", "doc_id", "id_res", "id_sens", "name_res", "name_sens", "both_res", "both_sens", "mentions",
          "kept_nonsens", "nonsens_chars"]

# Words in the name list that this benchmark uses as ordinary vocabulary, dates, places,
# organizations or pet and product names. Fixed by reading every list word that occurs.
NOT_PERSON = frozenset("""
Tuesday Don Hope Case Lincoln Park Harmony Haven April Happy Love Art See Charity Trip Lane Sunny Star
Harvard Will Son Valentine Quill May Shadow Job Nanny June Melody Way Saw Faith Chester Aurora Worth
August Urban Washington Sapphire Mercy Chase Kingston Chance Foster Rocky King Ave Rose Andromeda Luna
Orion Merlin Grove Glad Buddy Crystal West Major Jefferson Madison Dean Mayor Con France Marry Francisco
Sterling Locke Willow Hall Bishop Diego Grace Austin Westbrook Montgomery Hamilton Luther Lawrence Reed
Carter Davis Ray Trinity Summer Winter Autumn Spring Dawn Bay Holly Ivy Page Rich Wade
""".split())
_NOT_SURNAME = frozenset("""
Action Observation Input Final Answer Thought Note Notes Subject Date From Inbox Project Team Meeting Report
Support Group Manager Director Please Thanks Thank Best Regards Dear Hello The This That And But For With
Family Home Office School University College Hospital Clinic Company Inc Street Road Avenue
""".split())
_TITLE = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)")
_CAPITALIZED = re.compile(r"\b[A-Z][a-z]{2,}\b")
_FOLLOWING = re.compile(r"\s([A-Z][a-z]+)\b")


def _first_names() -> frozenset[str]:
    names: set[str] = set()
    for filename in ("female.txt", "male.txt"):
        with (NAMES_DIR / filename).open(encoding="latin-1") as handle:
            names.update(line.strip() for line in handle if line.strip())
    return frozenset(names - NOT_PERSON)


def third_party_spans(text: str, user_name: str, first_names: frozenset[str]) -> list[tuple[int, int]]:
    own = set(user_name.split())
    spans: list[tuple[int, int]] = []
    surnames: set[str] = set()
    for match in _TITLE.finditer(text):
        words = match.group(1).split()
        if own & set(words):
            continue
        spans.append(match.span(1))
        surnames.add(words[-1])
    for match in _CAPITALIZED.finditer(text):
        word = match.group(0)
        if word in own or word not in first_names:
            continue
        start, end = match.span()
        following = _FOLLOWING.match(text, end)
        if following and following.group(1) not in _NOT_SURNAME and following.group(1) not in own:
            end = following.end()
            surnames.add(following.group(1))
        spans.append((start, end))
    if surnames:
        pattern = re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(surnames))) + r")\b")
        spans.extend(m.span() for m in pattern.finditer(text))
    return _merge_spans(spans)


def _survived(gold: list[tuple[int, int]], released: str) -> tuple[int, int]:
    chars = _char_coverage(gold)
    return sum(1 for i in chars if i < len(released) and released[i] != MARKER), len(chars)


def _measure(doc: dict, detector, first_names: frozenset[str]) -> dict[str, int]:
    """The exposure table's combined text and per-stage detection, with two gold sets."""
    parts = (doc["instr"], doc["traj"], doc["action"])
    spans: list[tuple[int, int]] = []
    offset = 0
    for text in parts:
        spans.extend((offset + s, offset + e) for s, e in detector(text))
        offset += len(text) + 1
    combined = "\n".join(parts)
    released = _sanitize(combined, _merge_spans(spans))
    gold_ids = _gold_spans(combined, doc["name"], doc["email"])
    gold_names = third_party_spans(combined, doc["name"], first_names)
    id_res, id_sens = _survived(gold_ids, released)
    name_res, name_sens = _survived(gold_names, released)
    both_res, both_sens = _survived(_merge_spans(gold_ids + gold_names), released)
    # Retention is against the identifier gold, as in the exposure table.
    non = set(range(len(combined))) - _char_coverage(gold_ids)
    kept = sum(1 for i in non if i < len(released) and released[i] == combined[i])
    return {"id_res": id_res, "id_sens": id_sens, "name_res": name_res, "name_sens": name_sens,
            "both_res": both_res, "both_sens": both_sens, "mentions": len(gold_names),
            "kept_nonsens": kept, "nonsens_chars": len(non)}


def _parity_detector(seed: int):
    """The transformer tagger trained on AI4Privacy, applied here out of domain."""
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    import ai4privacy_parity_tagger as parity

    folder = parity.CHECKPOINTS / f"{parity.MODEL_ID}_seed{seed}"
    if not (folder / f"epoch{parity.EPOCHS}.done").exists():
        raise SystemExit(f"[gold] no finished parity tagger for seed {seed}")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(parity.MODEL_ID)
    model = AutoModelForTokenClassification.from_pretrained(folder / "latest").to(device).eval()
    scorer = parity._scorer(tokenizer, model, device)

    def detect(text: str) -> list[tuple[int, int]]:
        return _merge_spans([(a, b) for a, b, p in scorer(text) if p >= parity.DEFAULT_THRESHOLD])
    return detect


def _anchor() -> dict[tuple[str, str], tuple[int, int, int, int]]:
    recorded: dict[tuple[str, str], tuple[int, int, int, int]] = {}
    for shard in EXPERIMENTS_DIR.glob("propagation_suite_privacylens_documents_v2_shard*of4.csv"):
        with shard.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                recorded[(row["method_key"], row["doc_id"])] = (int(row["res_chars"]), int(row["sens_chars"]),
                                                                int(row["kept_nonsens"]), int(row["nonsens_chars"]))
    return recorded


def _write_sample(docs: list[dict], first_names: frozenset[str], size: int, seed: int) -> None:
    mentions: list[tuple[str, str, str]] = []
    for doc in docs:
        combined = "\n".join((doc["instr"], doc["traj"], doc["action"]))
        for start, end in third_party_spans(combined, doc["name"], first_names):
            context = combined[max(0, start - 40):start] + "[[" + combined[start:end] + "]]" + combined[end:end + 40]
            mentions.append((doc["doc_id"], combined[start:end], context.replace("\n", " ")))
    sample = random.Random(seed).sample(mentions, min(size, len(mentions)))
    with SAMPLE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["doc_id", "mention", "context", "is_person_name"])
        writer.writerows([*row, ""] for row in sample)
    print(f"[gold] {len(mentions)} mentions in {len(docs)} cases; wrote a sample of {len(sample)}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--methods", default=",".join(METHODS))
    parser.add_argument("--spacy-model", default="en_core_web_lg")
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--write-sample", type=int, help="write a sample of mentions to read, then stop")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--parity-seed", type=int, default=17, help="which trained parity tagger to apply")
    args = parser.parse_args()

    first_names = _first_names()
    docs = _load_documents("privacylens", None)
    if len(docs) != len(json.load(open(PL_PATH, encoding="utf-8"))):
        raise SystemExit("[gold] case count mismatch")
    if args.write_sample:
        _write_sample(docs, first_names, args.write_sample, args.seed)
        return 0

    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    done: set[tuple[str, str]] = set()
    if DOCUMENTS.exists():
        with DOCUMENTS.open(encoding="utf-8", newline="") as handle:
            done = {(r["method_key"], r["doc_id"]) for r in csv.DictReader(handle)}
    write_header = not DOCUMENTS.exists() or DOCUMENTS.stat().st_size == 0
    with DOCUMENTS.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
            handle.flush()
        for method in methods:
            remaining = [d for d in docs if (method, d["doc_id"]) not in done]
            print(f"[{method}] {len(docs) - len(remaining)} cases done, {len(remaining)} to run", flush=True)
            if not remaining:
                continue
            if method == PARITY_METHOD:
                detector = _parity_detector(args.parity_seed)
            else:
                learned = _train_learned_detector() if method == "learned_lr" else None
                detector = build_detectors([method], learned_weights=learned, spacy_model=args.spacy_model)[0]
            for n, doc in enumerate(remaining, 1):
                counts = _measure(doc, detector, first_names)
                writer.writerow({"method_key": method, "doc_id": doc["doc_id"], **counts})
                handle.flush()
                os.fsync(handle.fileno())
                if n % 100 == 0:
                    print(f"  {method}: {n}/{len(remaining)}", flush=True)

    with DOCUMENTS.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    anchor = _anchor()
    # The parity tagger is new here, so it has no recorded row to agree with.
    mismatches = sum(1 for r in rows if r["method_key"] != PARITY_METHOD
                     and anchor.get((r["method_key"], r["doc_id"])) != (int(r["id_res"]), int(r["id_sens"]),
                                                                        int(r["kept_nonsens"]), int(r["nonsens_chars"])))
    print(f"[anchor] {len(rows)} rows against the exposure-table records: {mismatches} mismatches", flush=True)
    if mismatches:
        print("[anchor] identifier-gold counts differ from the records; summary not written", flush=True)
        return 1

    with SUMMARY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["method_key", "cases", "cases_with_name_gold", "name_gold_mentions", "per_identifier_percent",
                         "per_third_party_name_percent", "per_both_percent", "retention"])
        for method in methods:
            sub = [r for r in rows if r["method_key"] == method]

            if not sub:
                continue

            def cell(num: str, den: str, scale: float = 100.0, digits: int = 1) -> str:
                point, lo, hi = bootstrap_ratio_ci([(float(r[num]), float(r[den])) for r in sub],
                                                   n_boot=args.bootstrap, scale=scale)
                return f"{point:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"
            writer.writerow([method, len(sub), sum(1 for r in sub if int(r["name_sens"])),
                             sum(int(r["mentions"]) for r in sub), cell("id_res", "id_sens"),
                             cell("name_res", "name_sens"), cell("both_res", "both_sens"),
                             cell("kept_nonsens", "nonsens_chars", 1.0, 2)])
    print(f"[gold] wrote {SUMMARY.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
