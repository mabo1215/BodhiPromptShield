#!/usr/bin/env python3
"""Propagation under an adaptive surface-form adversary (SPE/PER under attack).

The measured adaptive adversary reports how often a perturbation makes a
previously caught span evade the detector.  This suite closes the loop the
threat model actually cares about: an evaded span is only harmful if it then
propagates.  For every attack family and every detector in the registry, the
gold spans of the AI4Privacy test slice are mutated in place, the mutated
document is mediated by the detector and pushed through the documented
deterministic reference agent, and residual exposure (PER) and stage-wise
surface survival (SPE) of the *mutated* gold spans are measured with
document-level bootstrap confidence intervals.

Attack families and mutation functions are imported from the adaptive
adversary script so the two results share one definition.
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys
from pathlib import Path

from ai4privacy_matched_baseline_suite import _char_coverage, _load_records, _merge_spans
import ai4privacy_lightweight_classifier_baseline as clf
from measured_adaptive_adversary import ATTACKS, _build_mutation
from measured_agent_propagation import MARKER, _memory_write, _retrieval_query, _sanitize, _tool_call
from mediation_baselines import Detector, GenerationFailed, bootstrap_ratio_ci, build_detectors
from propagation_suite import AI4_PATH, AI4_SPLIT, _survival


EXPERIMENTS_DIR = Path(__file__).resolve().parent
MAX_DOCS = 200  # the adaptive-adversary slice
DEFAULT_METHODS = ["heuristic_mediator", "learned_lr", "presidio", "spacy_ner", "gliner_pii"]
ROW_FIELDS = ["attack", "method_key", "doc_id", "ret_s", "ret_t", "mem_s", "mem_t", "tool_s", "tool_t", "res_chars", "sens_chars"]
RESULT_FIELDS = ["attack", "method", "method_key", "documents", "retrieval_spe", "retrieval_spe_lo", "retrieval_spe_hi",
                 "memory_spe", "memory_spe_lo", "memory_spe_hi", "tool_spe", "tool_spe_lo", "tool_spe_hi",
                 "per_percent", "per_lo", "per_hi"]


def _with_tag(path: Path, tag: str | None) -> Path:
    return path if not tag else path.with_name(f"{path.stem}_{tag}{path.suffix}")


def _train_learned_detector() -> dict:
    records = clf._load_records(AI4_PATH)
    train = [r for r in records if str(r.get("split")) == "ai4privacy-train"][: clf.TRAIN_DOC_LIMIT]
    weights, _ = clf._train_logreg(clf._build_examples(train))
    return weights


def _measure(text: str, gold: list[tuple[int, int]], detector: Detector) -> dict[str, int]:
    gold_texts = [text[a:b] for a, b in gold]
    released = _sanitize(text, detector(text))
    ret_s, ret_t = _survival(_retrieval_query(released), gold_texts)
    mem_s, mem_t = _survival(_memory_write(released), gold_texts)
    tool_s, tool_t = _survival(_tool_call(released), gold_texts)
    gold_chars = _char_coverage(gold)
    res = sum(1 for i in gold_chars if i < len(released) and released[i] != MARKER)
    return {"ret_s": ret_s, "ret_t": ret_t, "mem_s": mem_s, "mem_t": mem_t, "tool_s": tool_s, "tool_t": tool_t,
            "res_chars": res, "sens_chars": len(gold_chars)}


def run(method_keys: list[str], *, max_docs: int, spacy_model: str, n_boot: int, output_tag: str | None) -> None:
    records = [r for r in _load_records(AI4_PATH) if str(r.get("split")) == AI4_SPLIT][:max_docs]
    docs = []
    for i, r in enumerate(records):
        gold = _merge_spans([(int(s["start"]), int(s["end"])) for s in r.get("phi_spans", []) if isinstance(s, dict)])
        docs.append((str(r.get("note_id", i)), str(r.get("text", "")), gold))
    learned = _train_learned_detector() if "learned_lr" in method_keys else None
    detectors = build_detectors(method_keys, learned_weights=learned, spacy_model=spacy_model)

    rows_path = _with_tag(EXPERIMENTS_DIR / "adversary_propagation_documents.csv", output_tag)
    results_path = _with_tag(EXPERIMENTS_DIR / "adversary_propagation_results.csv", output_tag)
    manifest_path = _with_tag(EXPERIMENTS_DIR / "adversary_propagation_runtime_manifest.csv", output_tag)
    done: dict[tuple[str, str, str], dict[str, int]] = {}
    if rows_path.exists():
        with rows_path.open("r", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                done[(r["attack"], r["method_key"], r["doc_id"])] = {k: int(r[k]) for k in ROW_FIELDS[3:]}
    new_file = not rows_path.exists()
    handle = rows_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
    if new_file:
        writer.writeheader(); handle.flush()

    results = []
    families = [("clean", None, None)] + [(name, mut, applies) for name, mut, applies in ATTACKS]
    for attack, mutate, applies in families:
        for det in detectors:
            per_doc = []
            for doc_id, text, gold in docs:
                key = (attack, det.key, doc_id)
                if key in done:
                    per_doc.append(done[key]); continue
                if mutate is None:
                    m_text, m_gold = text, gold
                else:
                    m_text, m_gold = _build_mutation(text, gold, mutate, applies)
                try:
                    counts = _measure(m_text, m_gold, det)
                except GenerationFailed as exc:
                    print(f"  skip {attack} {det.key} {doc_id}: {exc}"); continue
                writer.writerow({"attack": attack, "method_key": det.key, "doc_id": doc_id, **counts})
                handle.flush(); os.fsync(handle.fileno())
                done[key] = counts; per_doc.append(counts)
            pairs = lambda s, t: [(float(c[s]), float(c[t])) for c in per_doc]  # noqa: E731
            row = {"attack": attack, "method": det.label, "method_key": det.key, "documents": str(len(per_doc))}
            for prefix, s, t_ in (("retrieval_spe", "ret_s", "ret_t"), ("memory_spe", "mem_s", "mem_t"), ("tool_spe", "tool_s", "tool_t")):
                p, lo, hi = bootstrap_ratio_ci(pairs(s, t_), n_boot=n_boot, scale=100.0)
                row.update({prefix: f"{p:.1f}", f"{prefix}_lo": f"{lo:.1f}", f"{prefix}_hi": f"{hi:.1f}"})
            p, lo, hi = bootstrap_ratio_ci(pairs("res_chars", "sens_chars"), n_boot=n_boot, scale=100.0)
            row.update({"per_percent": f"{p:.1f}", "per_lo": f"{lo:.1f}", "per_hi": f"{hi:.1f}"})
            results.append(row)
            print(f"  {attack:28s} {det.label:40s} PER={row['per_percent']:>5} [{row['per_lo']},{row['per_hi']}] mem={row['memory_spe']:>5} tool={row['tool_spe']:>5}")
    handle.close()
    with results_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_FIELDS); w.writeheader(); w.writerows(results)
    manifest = [{"field": "benchmark", "value": f"AI4Privacy PII-Masking-300K English test slice, {len(docs)} documents"},
                {"field": "attacks", "value": "; ".join(a for a, _, _ in families)},
                {"field": "pipeline", "value": "Deterministic reference agent (retrieval=first half, memory=verbatim, tool=structured fields)"},
                {"field": "measurement", "value": "PER and SPE of the mutated gold spans after mediation of the mutated document"},
                {"field": "bootstrap", "value": f"{n_boot} document-level resamples, 95% percentile CI"},
                {"field": "python", "value": platform.python_version()}, {"field": "platform", "value": platform.platform()}]
    for det in detectors:
        for k, v in det.versions.items():
            manifest.append({"field": f"{det.key}.{k}", "value": str(v)})
    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["field", "value"]); w.writeheader(); w.writerows(manifest)
    print(f"Results: {results_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--methods", default=",".join(DEFAULT_METHODS))
    parser.add_argument("--max-docs", type=int, default=MAX_DOCS)
    parser.add_argument("--spacy-model", default="en_core_web_lg")
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--output-tag")
    args = parser.parse_args()
    run([k.strip() for k in args.methods.split(",") if k.strip()], max_docs=args.max_docs, spacy_model=args.spacy_model,
        n_boot=args.bootstrap, output_tag=args.output_tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
