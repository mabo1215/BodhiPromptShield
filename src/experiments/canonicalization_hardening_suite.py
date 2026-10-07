#!/usr/bin/env python3
"""Canonicalization hardening against the adaptive surface-form adversary.

The manuscript observes that none of the evaluated detectors normalizes its
input before matching and calls canonicalizing before the rule and NER passes
"the cheapest hardening the results point to".  This suite measures what that
hardening actually buys.  A byte-level canonicalizer is placed in front of
every detector in the registry, and both adversary measurements are repeated
for the plain and the canonicalized variant of each detector:

* attack success rate (ASR) per attack family, defined exactly as in the
  measured adaptive adversary: the fraction of previously-caught applicable
  gold spans that the attack pushes to evade;
* post-propagation exposure (PER) and stage-wise surface survival (SPE) of the
  mutated gold spans through the deterministic reference agent, defined
  exactly as in the adversary propagation suite, plus the clean row.

Canonicalizer (applied per original character, in this order)
--------------------------------------------------------------
1. drop Unicode format characters (general category Cf: zero-width space,
   joiner and non-joiner, word joiner, byte-order mark, soft hyphen, ...);
2. NFKC-normalize the character on its own (fullwidth forms to ASCII,
   ideographic space to space; an expansion maps every produced character to
   the same original index);
3. fold Latin-lookalike Cyrillic and Greek letters to Latin with the explicit
   table below.

The canonicalizer deliberately changes no token structure: case, ordinary
spaces, punctuation and digits are left alone.  Attacks that alter token
structure (intra-token spacing, separator injection, case inversion,
leetspeak, digit spell-out) are therefore expected to survive it; the point of
the measurement is to separate what byte-level normalization closes from what
it does not.  Detected spans are mapped back from canonical to original
offsets, so the released text is the original document with the detected
characters masked, including any zero-width characters hidden inside a
detected span.

Records
-------
Per-document rows are appended one at a time with flush+fsync and are resumable
by (attack, method_key, variant, doc_id); ``method_key`` is the base detector
key and ``variant`` is ``plain`` or ``canonical``.  The summary tables are
rebuilt from every row of the current slice on each invocation, so detectors
may be run in separate invocations (the transformer detector is run last on
its own).  Within an invocation each base detector memoizes its output per
input text, so a canonical variant whose canonical surface coincides with an
already-detected surface costs no extra detector call.
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys
import time
import unicodedata
from functools import cache
from pathlib import Path

from adversary_propagation_suite import RESULT_FIELDS as PROPAGATION_FIELDS, _measure, _train_learned_detector
from ai4privacy_matched_baseline_suite import _load_records, _merge_spans
from measured_adaptive_adversary import ATTACKS, HOMOGLYPH, N_BOOT, _build_mutation, _covered
from measured_agent_propagation import MARKER, _sanitize
from mediation_baselines import PAPER_LABELS, Detector, TypedSpan, bootstrap_ratio_ci, build_detectors
from propagation_suite import AI4_PATH, AI4_SPLIT


EXPERIMENTS_DIR = Path(__file__).resolve().parent
ASR_ROWS_PATH = EXPERIMENTS_DIR / "canonicalization_hardening_asr_documents.csv"
ASR_RESULTS_PATH = EXPERIMENTS_DIR / "canonicalization_hardening_asr_results.csv"
PROPAGATION_ROWS_PATH = EXPERIMENTS_DIR / "canonicalization_hardening_documents.csv"
PROPAGATION_RESULTS_PATH = EXPERIMENTS_DIR / "canonicalization_hardening_propagation_results.csv"
MANIFEST_PATH = EXPERIMENTS_DIR / "canonicalization_hardening_runtime_manifest.csv"

MAX_DOCS = 200  # the adaptive-adversary slice
DEFAULT_METHODS = ["heuristic_mediator", "learned_lr", "presidio", "spacy_ner", "gliner_pii"]
VARIANTS = ("plain", "canonical")
CANONICAL_SUFFIX = " + canonicalization"
CANONICALIZER_RULES = [
    "drop Unicode format characters (general category Cf: U+200B-U+200D, U+2060, U+FEFF, U+00AD, ...)",
    "NFKC-normalize each remaining character on its own (fullwidth forms to ASCII, ideographic space to space; "
    "an expansion maps every produced character to the same original index)",
    "fold Latin-lookalike Cyrillic and Greek letters to Latin with an explicit table; case, ordinary spaces, "
    "punctuation and digits are left unchanged",
]
ASR_ROW_FIELDS = ["attack", "method_key", "variant", "doc_id", "applicable", "caught_clean", "caught_attacked"]
ASR_RESULT_FIELDS = ["detector_key", "detector", "variant", "attack_family", "documents", "applicable_spans",
                     "clean_recall", "attacked_recall", "attack_success_rate", "attack_success_lo", "attack_success_hi"]
PROPAGATION_ROW_FIELDS = ["attack", "method_key", "variant", "doc_id", "ret_s", "ret_t", "mem_s", "mem_t",
                          "tool_s", "tool_t", "res_chars", "sens_chars"]
PROPAGATION_RESULT_FIELDS = PROPAGATION_FIELDS[:3] + ["variant"] + PROPAGATION_FIELDS[3:]

# Cyrillic and Greek letters whose reference glyph coincides with a Latin letter,
# named rather than spelled so that the source stays ASCII.
_CONFUSABLE_NAMES = [
    ("CYRILLIC SMALL LETTER A", "a"), ("CYRILLIC SMALL LETTER IE", "e"), ("CYRILLIC SMALL LETTER O", "o"),
    ("CYRILLIC SMALL LETTER ER", "p"), ("CYRILLIC SMALL LETTER ES", "c"), ("CYRILLIC SMALL LETTER U", "y"),
    ("CYRILLIC SMALL LETTER HA", "x"), ("CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I", "i"),
    ("CYRILLIC SMALL LETTER JE", "j"), ("CYRILLIC SMALL LETTER DZE", "s"), ("CYRILLIC SMALL LETTER KOMI DE", "d"),
    ("CYRILLIC SMALL LETTER SHHA", "h"), ("CYRILLIC SMALL LETTER STRAIGHT U", "y"),
    ("CYRILLIC SMALL LETTER IZHITSA", "v"), ("CYRILLIC SMALL LETTER ABKHASIAN CHE", "e"),
    ("CYRILLIC SMALL LETTER QA", "q"), ("CYRILLIC SMALL LETTER WE", "w"),
    ("CYRILLIC CAPITAL LETTER A", "A"), ("CYRILLIC CAPITAL LETTER VE", "B"), ("CYRILLIC CAPITAL LETTER IE", "E"),
    ("CYRILLIC CAPITAL LETTER KA", "K"), ("CYRILLIC CAPITAL LETTER EM", "M"), ("CYRILLIC CAPITAL LETTER EN", "H"),
    ("CYRILLIC CAPITAL LETTER O", "O"), ("CYRILLIC CAPITAL LETTER ER", "P"), ("CYRILLIC CAPITAL LETTER ES", "C"),
    ("CYRILLIC CAPITAL LETTER TE", "T"), ("CYRILLIC CAPITAL LETTER HA", "X"), ("CYRILLIC CAPITAL LETTER U", "Y"),
    ("CYRILLIC CAPITAL LETTER BYELORUSSIAN-UKRAINIAN I", "I"), ("CYRILLIC CAPITAL LETTER JE", "J"),
    ("CYRILLIC CAPITAL LETTER DZE", "S"),
    ("GREEK CAPITAL LETTER ALPHA", "A"), ("GREEK CAPITAL LETTER BETA", "B"), ("GREEK CAPITAL LETTER EPSILON", "E"),
    ("GREEK CAPITAL LETTER ZETA", "Z"), ("GREEK CAPITAL LETTER ETA", "H"), ("GREEK CAPITAL LETTER IOTA", "I"),
    ("GREEK CAPITAL LETTER KAPPA", "K"), ("GREEK CAPITAL LETTER MU", "M"), ("GREEK CAPITAL LETTER NU", "N"),
    ("GREEK CAPITAL LETTER OMICRON", "O"), ("GREEK CAPITAL LETTER RHO", "P"), ("GREEK CAPITAL LETTER TAU", "T"),
    ("GREEK CAPITAL LETTER UPSILON", "Y"), ("GREEK CAPITAL LETTER CHI", "X"),
    ("GREEK SMALL LETTER OMICRON", "o"), ("GREEK SMALL LETTER NU", "v"),
]
CONFUSABLES: dict[str, str] = {unicodedata.lookup(name): latin for name, latin in _CONFUSABLE_NAMES}


# ---------------------------------------------------------------------------
# Canonicalizer and detector wrapper.
# ---------------------------------------------------------------------------


def canonicalize(text: str) -> tuple[str, list[int]]:
    """Canonical text plus an offset map: ``offset_map[i]`` is the original index of canonical character ``i``."""
    chars: list[str] = []
    offset_map: list[int] = []
    for index, char in enumerate(text):
        if unicodedata.category(char) == "Cf":
            continue
        for produced in unicodedata.normalize("NFKC", char):
            chars.append(CONFUSABLES.get(produced, produced))
            offset_map.append(index)
    return "".join(chars), offset_map


def to_original(span: tuple[int, int], offset_map: list[int]) -> tuple[int, int]:
    """Map a canonical ``[a, b)`` span to the original ``[offset_map[a], offset_map[b - 1] + 1)``."""
    a, b = span
    b = min(b, len(offset_map))
    if b <= a:
        return 0, 0
    return offset_map[a], offset_map[b - 1] + 1


def canonical_detector(det: Detector) -> Detector:
    """Run ``det`` on the canonical text and map its spans back to original offsets.

    The returned detector's untyped call merges the mapped spans through
    ``_merge_spans`` as every registry detector does.
    """

    def typed(text: str) -> list[TypedSpan]:
        canonical, offset_map = canonicalize(text)
        spans: list[TypedSpan] = []
        for start, end, label in det.typed(canonical):
            a, b = to_original((start, end), offset_map)
            if b > a:
                spans.append((a, b, label))
        return sorted(spans)

    return Detector(f"{det.key}+canon", f"{det.label}{CANONICAL_SUFFIX}", typed, dict(det.versions))


def _memoized(det: Detector) -> Detector:
    """Sort and cache ``typed`` per input text.

    Sorting matters: the registry merge assumes its first span is the earliest,
    and Presidio returns its results unsorted, which otherwise drops every span
    that starts before the first-listed one.  Caching matters for cost: the clean
    document and several attack surfaces recur across the grid.
    """
    return Detector(det.key, det.label, cache(lambda text: sorted(det.typed(text))), det.versions)


# ---------------------------------------------------------------------------
# Self-test on the eight mutation functions.
# ---------------------------------------------------------------------------

BYTE_LEVEL_ATTACKS = {"Homoglyph substitution", "Zero-width insertion", "Mixed-language fullwidth"}
SELF_TEST_SPANS = ["John Smith", "jane.doe@example.com", "+1 415 555 0100", "Account 123456789", "12 Rue de la Paix"]


def self_test() -> int:
    """Check the canonicalizer and the wrapper against every attack family; return the number of checks."""
    checks = 0
    for key, latin in CONFUSABLES.items():
        assert len(key) == 1 and ord(key) > 127 and latin.isascii() and latin.isalpha(), (key, latin)
        assert unicodedata.normalize("NFKC", key) == key, key  # NFKC must not pre-empt the fold
        checks += 1
    assert all(ch in CONFUSABLES for ch in HOMOGLYPH.values()), "adversary homoglyphs outside the fold table"
    checks += 1

    def find_john(text: str) -> list[TypedSpan]:
        start = text.find("John Smith")
        return [] if start < 0 else [(start, start + len("John Smith"), "PERSON")]

    wrapped = canonical_detector(Detector("toy", "Toy", find_john))
    assert wrapped.key == "toy+canon" and wrapped.label == "Toy" + CANONICAL_SUFFIX
    for name, mutate, applies in ATTACKS:
        for span in SELF_TEST_SPANS:
            if not applies(span):
                continue
            mutated = mutate(span)
            expected = span if name in BYTE_LEVEL_ATTACKS else mutated
            canonical, offset_map = canonicalize(mutated)
            assert canonical == expected, (name, span, canonical)
            assert to_original((0, len(canonical)), offset_map) == (0, len(mutated)), (name, span)
            # Spans map back onto the mutated document, not just onto the isolated span.
            doc = f"Contact {span} today."
            m_doc, m_spans = _build_mutation(doc, [(8, 8 + len(span))], mutate, applies)
            c_doc, c_map = canonicalize(m_doc)
            start = c_doc.index(expected)
            assert to_original((start, start + len(expected)), c_map) == m_spans[0], (name, span, m_spans)
            checks += 3
            if span == "John Smith":
                detected = wrapped(m_doc)
                if name in BYTE_LEVEL_ATTACKS:
                    assert detected == [m_spans[0]], (name, detected, m_spans)
                    released = _sanitize(m_doc, detected)
                    assert released == f"Contact {MARKER * len(mutated)} today.", (name, released)
                else:
                    assert detected == [], (name, detected)  # token structure is not the canonicalizer's job
                checks += 1
    # Compound attack, NFKC expansion, idempotence.
    compound = mutate_compound("John Smith")
    canonical, offset_map = canonicalize(compound)
    assert canonical == "John Smith" and to_original((0, 10), offset_map) == (0, len(compound))
    assert canonicalize("\ufb01le")[0] == "file" and canonicalize("\ufb01le")[1] == [0, 0, 1, 2]
    again, identity = canonicalize(canonical)
    assert again == canonical and identity == list(range(len(canonical)))
    checks += 3
    print(f"self-test passed ({checks} checks, {len(CONFUSABLES)} confusables)")
    return checks


def mutate_compound(span: str) -> str:
    """Homoglyph, then zero-width insertion, then fullwidth: the three byte-level attacks stacked."""
    mutations = {name: mutate for name, mutate, _ in ATTACKS}
    return mutations["Mixed-language fullwidth"](mutations["Zero-width insertion"](mutations["Homoglyph substitution"](span)))


# ---------------------------------------------------------------------------
# Resumable per-document records.
# ---------------------------------------------------------------------------

Doc = tuple[str, str, list[tuple[int, int]]]
RowKey = tuple[str, str, str, str]


def _load_docs(max_docs: int) -> list[Doc]:
    records = [r for r in _load_records(AI4_PATH) if str(r.get("split")) == AI4_SPLIT][:max_docs]
    docs: list[Doc] = []
    for i, r in enumerate(records):
        gold = [(int(s["start"]), int(s["end"])) for s in r.get("phi_spans", []) if isinstance(s, dict)]
        docs.append((str(r.get("note_id", i)), str(r.get("text", "")), gold))
    return docs


def _load_rows(path: Path, fields: list[str]) -> dict[RowKey, dict[str, int]]:
    done: dict[RowKey, dict[str, int]] = {}
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as handle:
            for r in csv.DictReader(handle):
                done[(r["attack"], r["method_key"], r["variant"], r["doc_id"])] = {k: int(r[k]) for k in fields[4:]}
    return done


class _RowFile:
    """Append-only CSV with one fsync per row."""

    def __init__(self, path: Path, fields: list[str]) -> None:
        new_file = not path.exists()
        self.handle = path.open("a", encoding="utf-8", newline="")
        self.writer = csv.DictWriter(self.handle, fieldnames=fields)
        if new_file:
            self.writer.writeheader()
            self.handle.flush()

    def append(self, row: dict[str, object]) -> None:
        self.writer.writerow(row)
        self.handle.flush()
        os.fsync(self.handle.fileno())

    def close(self) -> None:
        self.handle.close()


def _group(done: dict[RowKey, dict[str, int]], doc_index: dict[str, int]) -> dict[tuple[str, str, str], list[dict[str, int]]]:
    """Rows of the current slice grouped by (attack, method_key, variant), in slice order."""
    groups: dict[tuple[str, str, str], list[tuple[int, dict[str, int]]]] = {}
    for (attack, key, variant, doc_id), counts in done.items():
        if doc_id in doc_index:
            groups.setdefault((attack, key, variant), []).append((doc_index[doc_id], counts))
    return {g: [c for _, c in sorted(rows, key=lambda r: r[0])] for g, rows in groups.items()}


def _ordered_keys(groups: dict[tuple[str, str, str], list[dict[str, int]]]) -> list[str]:
    present = {key for _, key, _ in groups}
    return [k for k in DEFAULT_METHODS if k in present] + sorted(present - set(DEFAULT_METHODS))


def _label(key: str, variant: str) -> str:
    base = PAPER_LABELS.get(key, key)
    return base if variant == "plain" else base + CANONICAL_SUFFIX


# ---------------------------------------------------------------------------
# Measurement 1: attack success rate, as in measured_adaptive_adversary.
# ---------------------------------------------------------------------------

DetectorPair = tuple[str, Detector, Detector]  # (base key, plain, canonical)


def run_asr(docs: list[Doc], pairs: list[DetectorPair], done: dict[RowKey, dict[str, int]], rows: _RowFile) -> dict[str, float]:
    wall: dict[str, float] = {}
    for key, plain, canonical in pairs:
        started = time.perf_counter()
        for attack, mutate, applies in ATTACKS:
            for variant, det in zip(VARIANTS, (plain, canonical)):
                for doc_id, text, gold in docs:
                    row_key = (attack, key, variant, doc_id)
                    if row_key in done:
                        continue
                    app_idx = [i for i, (a, b) in enumerate(gold) if applies(text[a:b])]
                    if not app_idx:
                        continue
                    det_clean = det(text)
                    caught_clean = sum(1 for i in app_idx if _covered(gold[i], det_clean))
                    mut_text, new_spans = _build_mutation(text, gold, mutate, applies)
                    det_mut = det(mut_text)
                    caught_attacked = sum(1 for i in app_idx if _covered(new_spans[i], det_mut))
                    counts = {"applicable": len(app_idx), "caught_clean": caught_clean, "caught_attacked": caught_attacked}
                    rows.append({"attack": attack, "method_key": key, "variant": variant, "doc_id": doc_id, **counts})
                    done[row_key] = counts
            print(f"  asr {key:20s} {attack:28s} done ({time.perf_counter() - started:7.1f} s)", flush=True)
        wall[key] = time.perf_counter() - started
    return wall


def _summarize_asr(done: dict[RowKey, dict[str, int]], doc_index: dict[str, int], n_boot: int) -> list[dict[str, str]]:
    groups = _group(done, doc_index)
    results: list[dict[str, str]] = []
    for key in _ordered_keys(groups):
        for variant in VARIANTS:
            for attack, _, _ in ATTACKS:
                counts = groups.get((attack, key, variant))
                if not counts:
                    continue
                applicable = sum(c["applicable"] for c in counts)
                caught_clean = sum(c["caught_clean"] for c in counts)
                caught_attacked = sum(c["caught_attacked"] for c in counts)
                asr = max(0.0, (caught_clean - caught_attacked) / caught_clean) if caught_clean else 0.0
                doc_pairs = [(float(c["caught_clean"] - c["caught_attacked"]), float(c["caught_clean"])) for c in counts]
                _, lo, hi = bootstrap_ratio_ci(doc_pairs, n_boot=n_boot, scale=100.0)
                results.append({
                    "detector_key": key, "detector": _label(key, variant), "variant": variant, "attack_family": attack,
                    "documents": str(len(counts)), "applicable_spans": str(applicable),
                    "clean_recall": f"{caught_clean / applicable if applicable else 0.0:.2f}",
                    "attacked_recall": f"{caught_attacked / applicable if applicable else 0.0:.2f}",
                    "attack_success_rate": f"{100.0 * asr:.1f}",
                    "attack_success_lo": f"{max(0.0, lo):.1f}", "attack_success_hi": f"{max(0.0, hi):.1f}",
                })
    return results


# ---------------------------------------------------------------------------
# Measurement 2: propagation, as in adversary_propagation_suite.
# ---------------------------------------------------------------------------


def run_propagation(docs: list[Doc], pairs: list[DetectorPair], done: dict[RowKey, dict[str, int]], rows: _RowFile) -> dict[str, float]:
    families = [("clean", None, None)] + list(ATTACKS)
    wall: dict[str, float] = {}
    for key, plain, canonical in pairs:
        started = time.perf_counter()
        for attack, mutate, applies in families:
            for variant, det in zip(VARIANTS, (plain, canonical)):
                for doc_id, text, raw_gold in docs:
                    row_key = (attack, key, variant, doc_id)
                    if row_key in done:
                        continue
                    gold = _merge_spans(raw_gold)
                    if mutate is None:
                        m_text, m_gold = text, gold
                    else:
                        m_text, m_gold = _build_mutation(text, gold, mutate, applies)
                    counts = _measure(m_text, m_gold, det)
                    rows.append({"attack": attack, "method_key": key, "variant": variant, "doc_id": doc_id, **counts})
                    done[row_key] = counts
            print(f"  prop {key:20s} {attack:28s} done ({time.perf_counter() - started:7.1f} s)", flush=True)
        wall[key] = time.perf_counter() - started
    return wall


def _summarize_propagation(done: dict[RowKey, dict[str, int]], doc_index: dict[str, int], n_boot: int) -> list[dict[str, str]]:
    groups = _group(done, doc_index)
    results: list[dict[str, str]] = []
    stages = (("retrieval_spe", "ret_s", "ret_t"), ("memory_spe", "mem_s", "mem_t"), ("tool_spe", "tool_s", "tool_t"),
              ("per", "res_chars", "sens_chars"))
    for attack in ["clean"] + [a for a, _, _ in ATTACKS]:
        for key in _ordered_keys(groups):
            for variant in VARIANTS:
                counts = groups.get((attack, key, variant))
                if not counts:
                    continue
                row = {"attack": attack, "method": _label(key, variant), "method_key": key, "variant": variant,
                       "documents": str(len(counts))}
                for prefix, s, t in stages:
                    p, lo, hi = bootstrap_ratio_ci([(float(c[s]), float(c[t])) for c in counts], n_boot=n_boot, scale=100.0)
                    name = "per_percent" if prefix == "per" else prefix
                    row.update({name: f"{p:.1f}", f"{prefix}_lo": f"{lo:.1f}", f"{prefix}_hi": f"{hi:.1f}"})
                results.append(row)
    return results


# ---------------------------------------------------------------------------
# Driver.
# ---------------------------------------------------------------------------


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _update_manifest(updates: dict[str, str], drop: list[str]) -> None:
    """Merge into the existing manifest so separate invocations accumulate one record."""
    fields: dict[str, str] = {}
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open("r", encoding="utf-8", newline="") as handle:
            fields = {r["field"]: r["value"] for r in csv.DictReader(handle)}
    for field in drop:
        fields.pop(field, None)
    fields.update(updates)
    _write_csv(MANIFEST_PATH, ["field", "value"], [{"field": k, "value": v} for k, v in fields.items()])


def _build_pairs(method_keys: list[str]) -> tuple[list[DetectorPair], dict[str, str]]:
    learned = _train_learned_detector() if "learned_lr" in method_keys else None
    pairs: list[DetectorPair] = []
    excluded: dict[str, str] = {}
    for key in method_keys:
        try:
            base = _memoized(build_detectors([key], learned_weights=learned)[0])
        except Exception as exc:  # noqa: BLE001 - an unavailable detector is recorded, not fatal
            excluded[key] = f"{type(exc).__name__}: {exc}".splitlines()[0]
            print(f"  excluded {key}: {excluded[key]}", flush=True)
            continue
        pairs.append((key, base, canonical_detector(base)))
    return pairs, excluded


def run(method_keys: list[str], *, max_docs: int, n_boot: int, do_asr: bool, do_propagation: bool) -> None:
    docs = _load_docs(max_docs)
    if not docs:
        raise ValueError("No AI4Privacy records selected.")
    doc_index = {doc_id: i for i, (doc_id, _, _) in enumerate(docs)}
    pairs, excluded = _build_pairs(method_keys)

    manifest = {
        "benchmark": "AI4Privacy PII-Masking-300K (English) test slice, real text + gold spans",
        "slice": f"first {len(docs)} documents of split {AI4_SPLIT}",
        "attacks": "; ".join(a for a, _, _ in ATTACKS),
        "variants": "plain (detector as released); canonical (same detector behind the canonicalizer, spans mapped back)",
        **{f"canonicalizer_rule_{i}": rule for i, rule in enumerate(CANONICALIZER_RULES, 1)},
        "confusable_table_size": str(len(CONFUSABLES)),
        "asr_definition": "Fraction of previously-caught applicable spans pushed to evade by the attack",
        "pipeline": "Deterministic reference agent (retrieval=first half, memory=verbatim, tool=structured fields)",
        "measurement": "PER and SPE of the mutated gold spans after mediation of the mutated document",
        "bootstrap": f"{n_boot} document-level percentile resamples, 95% CI, seed 17",
        "span_ordering": "typed spans sorted by start before the registry merge, in both variants",
        "memoization": "each base detector caches typed() per input text within an invocation",
        "llm_in_loop": "None; measurement is exact against the real detectors",
        "python": platform.python_version(), "platform": platform.platform(),
    }
    drop: list[str] = []
    for key, base, _ in pairs:
        manifest[f"detector.{key}"] = base.label
        manifest.update({f"{key}.{k}": str(v) for k, v in base.versions.items()})
        drop.append(f"excluded.{key}")
    manifest.update({f"excluded.{key}": reason for key, reason in excluded.items()})

    if do_asr:
        done = _load_rows(ASR_ROWS_PATH, ASR_ROW_FIELDS)
        rows = _RowFile(ASR_ROWS_PATH, ASR_ROW_FIELDS)
        wall = run_asr(docs, pairs, done, rows)
        rows.close()
        results = _summarize_asr(done, doc_index, n_boot)
        _write_csv(ASR_RESULTS_PATH, ASR_RESULT_FIELDS, results)
        manifest.update({f"wall_seconds.asr.{key}": f"{seconds:.1f}" for key, seconds in wall.items()})
        print(f"ASR results: {ASR_RESULTS_PATH}")
        for row in results:
            print(f"  {row['detector']:60s} {row['attack_family']:28s} clean={row['clean_recall']} "
                  f"atk={row['attacked_recall']} ASR={row['attack_success_rate']:>5}% [{row['attack_success_lo']},{row['attack_success_hi']}]")
    if do_propagation:
        done = _load_rows(PROPAGATION_ROWS_PATH, PROPAGATION_ROW_FIELDS)
        rows = _RowFile(PROPAGATION_ROWS_PATH, PROPAGATION_ROW_FIELDS)
        wall = run_propagation(docs, pairs, done, rows)
        rows.close()
        results = _summarize_propagation(done, doc_index, n_boot)
        _write_csv(PROPAGATION_RESULTS_PATH, PROPAGATION_RESULT_FIELDS, results)
        manifest.update({f"wall_seconds.propagation.{key}": f"{seconds:.1f}" for key, seconds in wall.items()})
        print(f"Propagation results: {PROPAGATION_RESULTS_PATH}")
        for row in results:
            print(f"  {row['attack']:28s} {row['method']:60s} PER={row['per_percent']:>5} [{row['per_lo']},{row['per_hi']}] "
                  f"ret={row['retrieval_spe']:>5} mem={row['memory_spe']:>5} tool={row['tool_spe']:>5}")
    _update_manifest(manifest, drop)
    print(f"Manifest: {MANIFEST_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--methods", default=",".join(DEFAULT_METHODS))
    parser.add_argument("--max-docs", type=int, default=MAX_DOCS)
    parser.add_argument("--bootstrap", type=int, default=N_BOOT)
    parser.add_argument("--self-test", action="store_true", help="check the canonicalizer against the eight mutations and exit")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--only-asr", action="store_true")
    scope.add_argument("--only-propagation", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    run([k.strip() for k in args.methods.split(",") if k.strip()], max_docs=args.max_docs, n_boot=args.bootstrap,
        do_asr=not args.only_propagation, do_propagation=not args.only_asr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
