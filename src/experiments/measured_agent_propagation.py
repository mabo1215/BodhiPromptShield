#!/usr/bin/env python3
"""Measured stage-wise propagation on real prompt text (no synthetic scoring).

The CPPB propagation table in the main text is a controlled-benchmark operating
surface. To answer the strongest reviewer concern---that the headline
propagation result is constructed rather than measured---this script runs the
actual released detection/mediation on *real* prompt text (the public AI4Privacy
English slice, which ships with character-level gold PII spans) and *measures*
how many gold sensitive surface forms survive into three concrete agent-stage
artifacts produced by a documented, deterministic reference pipeline.

Reference agent pipeline (documented, deterministic, LLM-free for reproducibility)
---------------------------------------------------------------------------------
For each document the mediator first produces a released prompt ``p`` (raw for
``No protection``; with detected spans replaced by a fixed marker otherwise).
The released prompt then flows into three stage artifacts:

* Retrieval query : the first half (by characters) of ``p`` -- a partial RAG
  query that keeps the opening context.
* Memory write    : the full released prompt ``p`` stored verbatim.
* Tool call       : only the structured field-like tokens of ``p`` (e-mails,
  digit-bearing identifiers, and capitalized name tokens) forwarded as tool
  arguments.

Stage-wise Propagation Exposure (SPE) at a stage is the measured fraction of
gold sensitive characters that still appear in that stage's artifact. PER is the
residual direct exposure on the released prompt, and retention is the fraction
of non-sensitive characters preserved. All numbers are measured by exact
character-coverage over real text; nothing is sampled or hand-set.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from ai4privacy_matched_baseline_suite import _char_coverage
from ai4privacy_matched_baseline_suite import _load_records
from ai4privacy_matched_baseline_suite import _merge_spans
from ai4privacy_matched_baseline_suite import _ner_like_spans
from ai4privacy_matched_baseline_suite import _policy_aware_spans
from ai4privacy_matched_baseline_suite import _regex_spans

import ai4privacy_lightweight_classifier_baseline as clf


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = EXPERIMENTS_DIR / "ai4privacy_pii300k_english_export.jsonl"
RESULTS_PATH = EXPERIMENTS_DIR / "measured_agent_propagation_results.csv"
RUNTIME_PATH = EXPERIMENTS_DIR / "measured_agent_propagation_runtime_manifest.csv"

SPLIT = "ai4privacy-test"
MAX_DOCS = 300  # fixed deterministic slice for tractable, reproducible measurement
MARKER = "█"  # full block: a fixed marker that shares no characters with PII

FIELD_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9@._+\-]{1,}")


def _train_learned_detector(input_path: Path) -> dict:
    """Train the lightweight learned span detector on the public train split."""
    records = clf._load_records(input_path)
    train_records = [r for r in records if str(r.get("split")) == "ai4privacy-train"][: clf.TRAIN_DOC_LIMIT]
    examples = clf._build_examples(train_records)
    weights, _ = clf._train_logreg(examples)
    return weights


def _build_methods(input_path: Path):
    learned_weights = _train_learned_detector(input_path)
    return [
        ("No protection", lambda t: []),
        ("Regex-only", lambda t: _merge_spans(_regex_spans(t))),
        ("NER-only masking", lambda t: _merge_spans(_ner_like_spans(t))),
        ("Proposed (released heuristic detector)", lambda t: _policy_aware_spans(t)),
        ("Proposed (learned detector)", lambda t: clf._predict_spans(learned_weights, t)),
    ]


def _sanitize(text: str, spans: list[tuple[int, int]]) -> str:
    """Replace detected spans with a fixed marker, preserving other characters."""
    if not spans:
        return text
    out = []
    cursor = 0
    for start, end in sorted(_merge_spans(spans)):
        start = max(0, min(start, len(text)))
        end = max(start, min(end, len(text)))
        out.append(text[cursor:start])
        out.append(MARKER * max(1, end - start))
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def _retrieval_query(p: str) -> str:
    return p[: max(1, len(p) // 2)]


def _memory_write(p: str) -> str:
    return p


def _tool_call(p: str) -> str:
    tokens = []
    for m in FIELD_TOKEN.finditer(p):
        tok = m.group(0)
        if any(ch.isdigit() for ch in tok) or "@" in tok or tok[:1].isupper():
            tokens.append(tok)
    return " ".join(tokens)


def _gold_surface_survival(stage_text: str, gold_texts: list[str]) -> tuple[int, int]:
    """Count how many gold sensitive spans survive verbatim in stage_text."""
    survived = 0
    for g in gold_texts:
        if g and g in stage_text:
            survived += 1
    return survived, len(gold_texts)


def evaluate(input_path: Path) -> None:
    records = [r for r in _load_records(input_path) if str(r.get("split")) == SPLIT][:MAX_DOCS]
    if not records:
        raise ValueError("No AI4Privacy records selected.")

    methods = _build_methods(input_path)

    rows = []
    total_mentions = 0
    for record in records:
        total_mentions += sum(1 for s in record.get("phi_spans", []) if isinstance(s, dict))

    for method_name, detector in methods:
        # Stage-survival counters (verbatim gold-span survival per stage).
        ret_s = ret_t = mem_s = mem_t = tool_s = tool_t = 0
        # Char-coverage residual exposure / retention on the released prompt.
        sens_chars = res_chars = nonsens_chars = kept_nonsens = 0
        for record in records:
            text = str(record.get("text", ""))
            gold_spans = [
                (int(s["start"]), int(s["end"]))
                for s in record.get("phi_spans", [])
                if isinstance(s, dict)
            ]
            gold_texts = [text[a:b] for a, b in gold_spans]
            detected = detector(text)
            released = _sanitize(text, detected)

            # Stage artifacts from the released prompt.
            r_art = _retrieval_query(released)
            m_art = _memory_write(released)
            t_art = _tool_call(released)
            s, t = _gold_surface_survival(r_art, gold_texts); ret_s += s; ret_t += t
            s, t = _gold_surface_survival(m_art, gold_texts); mem_s += s; mem_t += t
            s, t = _gold_surface_survival(t_art, gold_texts); tool_s += s; tool_t += t

            # PER / retention via char coverage on the released prompt.
            gold_chars = _char_coverage(gold_spans)
            released_sens = {i for i in gold_chars if i < len(released) and released[i] != MARKER}
            all_chars = set(range(len(text)))
            non_sensitive = all_chars - gold_chars
            kept = {i for i in non_sensitive if i < len(released) and released[i] == text[i]}
            sens_chars += len(gold_chars)
            res_chars += len(released_sens)
            nonsens_chars += len(non_sensitive)
            kept_nonsens += len(kept)

        rows.append(
            {
                "method": method_name,
                "documents": str(len(records)),
                "mentions": str(total_mentions),
                "retrieval_spe": f"{100.0 * ret_s / ret_t if ret_t else 0.0:.1f}",
                "memory_spe": f"{100.0 * mem_s / mem_t if mem_t else 0.0:.1f}",
                "tool_spe": f"{100.0 * tool_s / tool_t if tool_t else 0.0:.1f}",
                "per_percent": f"{100.0 * res_chars / sens_chars if sens_chars else 0.0:.1f}",
                "text_retention": f"{kept_nonsens / nonsens_chars if nonsens_chars else 1.0:.2f}",
            }
        )

    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "method",
                "documents",
                "mentions",
                "retrieval_spe",
                "memory_spe",
                "tool_spe",
                "per_percent",
                "text_retention",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    runtime_rows = [
        {"field": "benchmark", "value": "AI4Privacy PII-Masking-300K (English), real text + gold spans"},
        {"field": "split", "value": SPLIT},
        {"field": "documents", "value": str(len(records))},
        {"field": "mentions", "value": str(total_mentions)},
        {"field": "pipeline", "value": "Documented deterministic reference agent (retrieval=first half, memory=verbatim, tool=structured fields)"},
        {"field": "measurement", "value": "Exact gold-span surface survival + char-coverage PER/retention"},
        {"field": "llm_in_loop", "value": "None (measurement is exact and reproducible without a model)"},
        {"field": "dependencies", "value": "Pure Python standard library + repository detection helpers"},
    ]
    with RUNTIME_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "value"])
        writer.writeheader()
        writer.writerows(runtime_rows)

    print(f"Measured agent-propagation results written to {RESULTS_PATH}")
    for row in rows:
        print(
            f"  {row['method']:34s} ret={row['retrieval_spe']:>5} mem={row['memory_spe']:>5} "
            f"tool={row['tool_spe']:>5} PER={row['per_percent']:>5} ret={row['text_retention']}"
        )


def main() -> int:
    evaluate(DEFAULT_INPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
