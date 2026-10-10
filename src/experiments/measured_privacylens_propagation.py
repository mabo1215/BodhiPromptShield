#!/usr/bin/env python3
"""Measured propagation on real agent-task trajectories (PrivacyLens).

This upgrades the measured-propagation evidence from a reference agent over PII
text (AI4Privacy) to a *real agent-task* benchmark: PrivacyLens (NeurIPS 2024
D&B) ships 493 real agent trajectories (actions + observations) with explicit
sensitive items and user-identity fields. We run the actual released detectors
and mediation on these real trajectories and measure how many concrete
sensitive surface forms survive into the agent's stage artifacts.

Gold (exact, non-circular): the user identity (name, e-mail) plus all e-mail
addresses and digit-run identifiers that appear verbatim in the trajectory.
These are unambiguous concrete surface forms; we do NOT use a recognizer to
define gold. Stage artifacts are the user instruction (retrieval query), the
executable trajectory (working memory), and the final action (outgoing tool
call). Everything is measured by exact character coverage; no LLM is used.

Honest scope: PrivacyLens's marked sensitive items are largely *semantic facts*
(e.g., "X is accused of embezzling funds"), not verbatim PII spans. Surface-form
mediation suppresses the concrete identifiers but does not remove these semantic
facts, so we additionally report a semantic-residue rate to make explicit that
surface-form mediation does not contain semantic agent-task leakage -- the same
open frontier identified by the paraphrase-evasion result.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from ai4privacy_matched_baseline_suite import _char_coverage
from ai4privacy_matched_baseline_suite import _merge_spans
from ai4privacy_matched_baseline_suite import _ner_like_spans
from ai4privacy_matched_baseline_suite import _policy_aware_spans
from ai4privacy_matched_baseline_suite import _regex_spans

import ai4privacy_lightweight_classifier_baseline as clf
from measured_agent_propagation import _sanitize, MARKER


EXPERIMENTS_DIR = Path(__file__).resolve().parent
AI4_PATH = EXPERIMENTS_DIR / "ai4privacy_pii300k_english_export.jsonl"
PL_PATH = EXPERIMENTS_DIR / "external_data" / "privacylens" / "main_data.json"
RESULTS_PATH = EXPERIMENTS_DIR / "measured_privacylens_propagation_results.csv"
RUNTIME_PATH = EXPERIMENTS_DIR / "measured_privacylens_propagation_runtime_manifest.csv"

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
DIGIT_ID = re.compile(r"\b\d[\d\- ]{4,}\d\b")
STOP = set("the a an and or of to in on for with is are was were be by at as that this from your you i we it".split())


def _train_learned_detector() -> dict:
    records = clf._load_records(AI4_PATH)
    train = [r for r in records if str(r.get("split")) == "ai4privacy-train"][: clf.TRAIN_DOC_LIMIT]
    weights, _ = clf._train_logreg(clf._build_examples(train))
    return weights


def _gold_spans(text: str, user_name: str, user_email: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pat in (EMAIL, DIGIT_ID):
        spans.extend((m.start(), m.end()) for m in pat.finditer(text))
    for needle in (user_name, user_email):
        if needle and len(needle) >= 3:
            start = text.find(needle)
            while start != -1:
                spans.append((start, start + len(needle)))
                start = text.find(needle, start + len(needle))
    return _merge_spans(spans)


def _stage_spe(stage_text: str, name: str, email: str, detector) -> tuple[int, int]:
    gold = _gold_spans(stage_text, name, email)
    if not gold:
        return 0, 0
    released = _sanitize(stage_text, detector(stage_text))
    gold_chars = _char_coverage(gold)
    survived = sum(1 for i in gold_chars if i < len(released) and released[i] != MARKER)
    return survived, len(gold_chars)


def _semantic_residue(trajectory: str, items: list[str], detector) -> tuple[int, int]:
    """Fraction of sensitive items whose content words survive the strongest mediation."""
    released = _sanitize(trajectory, detector(trajectory)).lower()
    survived = 0
    total = 0
    for item in items:
        words = [w for w in re.findall(r"[a-zA-Z]{4,}", item.lower()) if w not in STOP]
        if not words:
            continue
        total += 1
        present = sum(1 for w in words if w in set(re.findall(r"[a-z]+", released)))  # whole words
        if present >= max(1, len(words) // 2):
            survived += 1
    return survived, total


def run() -> None:
    import json

    data = json.load(open(PL_PATH, encoding="utf-8"))
    learned = _train_learned_detector()

    methods = [
        ("No protection", lambda t: []),
        ("Regex-only", lambda t: _merge_spans(_regex_spans(t))),
        ("NER-only masking", lambda t: _merge_spans(_ner_like_spans(t))),
        ("Proposed (released heuristic detector)", lambda t: _policy_aware_spans(t)),
        ("Proposed (learned detector)", lambda t: clf._predict_spans(learned, t)),
    ]

    rows = []
    for method_name, detector in methods:
        ret_s = ret_t = mem_s = mem_t = tool_s = tool_t = 0
        per_s = per_t = ret_keep = ret_non = 0
        for ex in data:
            tr = ex["trajectory"]
            name, email = tr.get("user_name", ""), tr.get("user_email", "")
            instr = tr.get("user_instruction", "")
            traj = tr.get("executable_trajectory", "")
            action = str(tr.get("final_action", ""))
            for art, (sa, ta) in (
                (instr, ("ret_s", "ret_t")),
                (traj, ("mem_s", "mem_t")),
                (action, ("tool_s", "tool_t")),
            ):
                s, t = _stage_spe(art, name, email, detector)
                if ta == "ret_t": ret_s += s; ret_t += t
                elif ta == "mem_t": mem_s += s; mem_t += t
                else: tool_s += s; tool_t += t
            combined = instr + "\n" + traj + "\n" + action
            gold = _gold_spans(combined, name, email)
            released = _sanitize(combined, detector(combined))
            gold_chars = _char_coverage(gold)
            per_s += sum(1 for i in gold_chars if i < len(released) and released[i] != MARKER)
            per_t += len(gold_chars)
            non = set(range(len(combined))) - gold_chars
            ret_non += len(non)
            ret_keep += sum(1 for i in non if i < len(released) and released[i] == combined[i])
        rows.append(
            {
                "method": method_name,
                "documents": str(len(data)),
                "retrieval_spe": f"{100.0 * ret_s / ret_t if ret_t else 0.0:.1f}",
                "memory_spe": f"{100.0 * mem_s / mem_t if mem_t else 0.0:.1f}",
                "tool_spe": f"{100.0 * tool_s / tool_t if tool_t else 0.0:.1f}",
                "per_percent": f"{100.0 * per_s / per_t if per_t else 0.0:.1f}",
                "text_retention": f"{ret_keep / ret_non if ret_non else 1.0:.2f}",
            }
        )

    # Semantic residue under the strongest (learned) detector.
    sem_s = sem_t = 0
    for ex in data:
        tr = ex["trajectory"]
        s, t = _semantic_residue(tr.get("executable_trajectory", ""), tr.get("sensitive_info_items", []),
                                 lambda x: clf._predict_spans(learned, x))
        sem_s += s; sem_t += t
    semantic_residue = 100.0 * sem_s / sem_t if sem_t else 0.0

    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["method", "documents", "retrieval_spe", "memory_spe", "tool_spe", "per_percent", "text_retention"],
        )
        writer.writeheader()
        writer.writerows(rows)

    runtime_rows = [
        {"field": "benchmark", "value": "PrivacyLens (NeurIPS 2024 D&B), 493 real agent trajectories"},
        {"field": "source", "value": "github.com/SALT-NLP/PrivacyLens data/main_data.json"},
        {"field": "gold", "value": "user identity (name/email) + verbatim e-mails and digit-run identifiers in the trajectory"},
        {"field": "stages", "value": "retrieval=user_instruction; memory=executable_trajectory; tool=final_action"},
        {"field": "semantic_residue_percent", "value": f"{semantic_residue:.1f}"},
        {"field": "semantic_note", "value": "Percent of sensitive_info_items whose fact content survives the learned-detector mediation (surface mediation does not contain semantic leakage)"},
        {"field": "llm_in_loop", "value": "None; exact character-coverage measurement"},
    ]
    with RUNTIME_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "value"])
        writer.writeheader()
        writer.writerows(runtime_rows)

    print(f"Measured PrivacyLens propagation written to {RESULTS_PATH}")
    for r in rows:
        print(f"  {r['method']:38s} ret={r['retrieval_spe']:>5} mem={r['memory_spe']:>5} tool={r['tool_spe']:>5} PER={r['per_percent']:>5} keep={r['text_retention']}")
    print(f"  Semantic residue (learned detector): {semantic_residue:.1f}% of sensitive items still conveyed")


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
