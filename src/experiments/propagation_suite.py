#!/usr/bin/env python3
"""Measured stage-wise propagation on real sources with the full baseline roster.

This suite generalizes the two measured-propagation scripts (AI4Privacy through
the documented deterministic reference agent; PrivacyLens real agent-task
trajectories) to the complete method registry in ``mediation_baselines`` --
real Presidio, real spaCy NER, a Casper-style sanitizer, a transformer PII
detector, and LLM sanitizers -- and adds document-level bootstrap confidence
intervals for every exposure metric.

Outputs (suffix ``_<tag>`` when ``--output-tag`` is given):

* ``propagation_suite_<source>_results.csv``   -- one row per method with the
  same columns as the original measured tables plus ``*_lo``/``*_hi`` CI columns;
* ``propagation_suite_<source>_documents.csv`` -- one row per (method, document),
  written incrementally with fsync and skipped on restart when already present;
* ``propagation_suite_<source>_runtime_manifest.csv`` -- library and model
  versions, digests, hardware, and the measurement conventions.

Stage artifacts and gold definitions are unchanged from the original scripts
so that the new rows are directly comparable to the published ones.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import sys
from pathlib import Path

from ai4privacy_matched_baseline_suite import _char_coverage, _load_records, _merge_spans
import ai4privacy_lightweight_classifier_baseline as clf
from measured_agent_propagation import MARKER, _memory_write, _retrieval_query, _sanitize, _tool_call
from measured_privacylens_propagation import _gold_spans as _pl_gold_spans
from mediation_baselines import METHOD_ORDER, Detector, bootstrap_ratio_ci, build_detectors


EXPERIMENTS_DIR = Path(__file__).resolve().parent
AI4_PATH = EXPERIMENTS_DIR / "ai4privacy_pii300k_english_export.jsonl"
PL_PATH = EXPERIMENTS_DIR / "external_data" / "privacylens" / "main_data.json"
AI4_SPLIT = "ai4privacy-test"
AI4_MAX_DOCS = 300

STOP = set("the a an and or of to in on for with is are was were be by at as that this from your you i we it".split())

RESULT_FIELDS = [
    "method", "method_key", "documents", "mentions",
    "retrieval_spe", "retrieval_spe_lo", "retrieval_spe_hi",
    "memory_spe", "memory_spe_lo", "memory_spe_hi",
    "tool_spe", "tool_spe_lo", "tool_spe_hi",
    "per_percent", "per_lo", "per_hi",
    "text_retention", "retention_lo", "retention_hi",
    "semantic_residue", "semantic_lo", "semantic_hi",
]
DOC_FIELDS = [
    "method_key", "doc_id", "ret_s", "ret_t", "mem_s", "mem_t", "tool_s", "tool_t",
    "res_chars", "sens_chars", "kept_nonsens", "nonsens_chars", "sem_s", "sem_t",
]


def _with_tag(path: Path, tag: str | None) -> Path:
    return path if not tag else path.with_name(f"{path.stem}_{tag}{path.suffix}")


def _train_learned_detector() -> dict:
    records = clf._load_records(AI4_PATH)
    train = [r for r in records if str(r.get("split")) == "ai4privacy-train"][: clf.TRAIN_DOC_LIMIT]
    weights, _ = clf._train_logreg(clf._build_examples(train))
    return weights


def _load_documents(source: str, max_docs: int | None) -> list[dict]:
    """Normalize both sources to {doc_id, artifacts: {stage: text}, gold(stage_text)->spans, items}."""
    docs: list[dict] = []
    if source == "ai4privacy":
        records = [r for r in _load_records(AI4_PATH) if str(r.get("split")) == AI4_SPLIT][: max_docs or AI4_MAX_DOCS]
        for i, record in enumerate(records):
            text = str(record.get("text", ""))
            gold = _merge_spans([(int(s["start"]), int(s["end"])) for s in record.get("phi_spans", []) if isinstance(s, dict)])
            docs.append({"doc_id": str(record.get("note_id", i)), "text": text, "gold": gold, "items": []})
    elif source == "privacylens":
        data = json.load(open(PL_PATH, encoding="utf-8"))[: max_docs or None]
        for i, ex in enumerate(data):
            tr = ex["trajectory"]
            docs.append({
                "doc_id": str(ex.get("name", i)),
                "name": tr.get("user_name", ""), "email": tr.get("user_email", ""),
                "instr": tr.get("user_instruction", ""), "traj": tr.get("executable_trajectory", ""),
                "action": str(tr.get("final_action", "")), "items": list(tr.get("sensitive_info_items", [])),
            })
    else:
        raise ValueError(source)
    if not docs:
        raise ValueError(f"No documents loaded for {source}")
    return docs


def _survival(stage_text: str, gold_texts: list[str]) -> tuple[int, int]:
    return sum(1 for g in gold_texts if g and g in stage_text), len(gold_texts)


def _semantic_residue(released: str, items: list[str]) -> tuple[int, int]:
    """Items whose content words mostly survive in the released text (PrivacyLens)."""
    released = released.lower()
    survived = total = 0
    for item in items:
        words = [w for w in re.findall(r"[a-zA-Z]{4,}", item.lower()) if w not in STOP]
        if not words:
            continue
        total += 1
        if sum(1 for w in words if w in released) >= max(1, len(words) // 2):
            survived += 1
    return survived, total


def _measure_ai4privacy(doc: dict, detector: Detector) -> dict[str, int]:
    text, gold = doc["text"], doc["gold"]
    gold_texts = [text[a:b] for a, b in gold]
    released = _sanitize(text, detector(text))
    ret_s, ret_t = _survival(_retrieval_query(released), gold_texts)
    mem_s, mem_t = _survival(_memory_write(released), gold_texts)
    tool_s, tool_t = _survival(_tool_call(released), gold_texts)
    gold_chars = _char_coverage(gold)
    res = sum(1 for i in gold_chars if i < len(released) and released[i] != MARKER)
    non = set(range(len(text))) - gold_chars
    kept = sum(1 for i in non if i < len(released) and released[i] == text[i])
    return {"ret_s": ret_s, "ret_t": ret_t, "mem_s": mem_s, "mem_t": mem_t, "tool_s": tool_s, "tool_t": tool_t,
            "res_chars": res, "sens_chars": len(gold_chars), "kept_nonsens": kept, "nonsens_chars": len(non), "sem_s": 0, "sem_t": 0}


def _measure_privacylens(doc: dict, detector: Detector) -> dict[str, int]:
    name, email = doc["name"], doc["email"]
    counts = {}
    for stage, text in (("ret", doc["instr"]), ("mem", doc["traj"]), ("tool", doc["action"])):
        gold = _pl_gold_spans(text, name, email)
        if not gold:
            counts[f"{stage}_s"], counts[f"{stage}_t"] = 0, 0
            continue
        released = _sanitize(text, detector(text))
        gold_chars = _char_coverage(gold)
        counts[f"{stage}_s"] = sum(1 for i in gold_chars if i < len(released) and released[i] != MARKER)
        counts[f"{stage}_t"] = len(gold_chars)
    combined = doc["instr"] + "\n" + doc["traj"] + "\n" + doc["action"]
    gold = _pl_gold_spans(combined, name, email)
    released = _sanitize(combined, detector(combined))
    gold_chars = _char_coverage(gold)
    counts["res_chars"] = sum(1 for i in gold_chars if i < len(released) and released[i] != MARKER)
    counts["sens_chars"] = len(gold_chars)
    non = set(range(len(combined))) - gold_chars
    counts["nonsens_chars"] = len(non)
    counts["kept_nonsens"] = sum(1 for i in non if i < len(released) and released[i] == combined[i])
    counts["sem_s"], counts["sem_t"] = _semantic_residue(_sanitize(doc["traj"], detector(doc["traj"])), doc["items"])
    return counts


def _read_done(path: Path) -> dict[tuple[str, str], dict[str, int]]:
    done: dict[tuple[str, str], dict[str, int]] = {}
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                done[(row["method_key"], row["doc_id"])] = {k: int(row[k]) for k in DOC_FIELDS[2:]}
    return done


def _ci_fields(prefix: str, pairs: list[tuple[float, float]], n_boot: int, scale: float, digits: int) -> dict[str, str]:
    point, lo, hi = bootstrap_ratio_ci(pairs, n_boot=n_boot, scale=scale)
    fmt = f"{{:.{digits}f}}"
    return {prefix: fmt.format(point), f"{prefix}_lo": fmt.format(lo), f"{prefix}_hi": fmt.format(hi)}


def run(source: str, method_keys: list[str], *, max_docs: int | None, spacy_model: str, ollama_url: str,
        n_boot: int, output_tag: str | None) -> Path:
    docs = _load_documents(source, max_docs)
    learned = _train_learned_detector() if "learned_lr" in method_keys else None
    detectors = build_detectors(method_keys, learned_weights=learned, spacy_model=spacy_model, ollama_url=ollama_url)
    measure = _measure_ai4privacy if source == "ai4privacy" else _measure_privacylens

    results_path = _with_tag(EXPERIMENTS_DIR / f"propagation_suite_{source}_results.csv", output_tag)
    docs_path = _with_tag(EXPERIMENTS_DIR / f"propagation_suite_{source}_documents.csv", output_tag)
    manifest_path = _with_tag(EXPERIMENTS_DIR / f"propagation_suite_{source}_runtime_manifest.csv", output_tag)

    done = _read_done(docs_path)
    new_file = not docs_path.exists()
    handle = docs_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=DOC_FIELDS)
    if new_file:
        writer.writeheader()
        handle.flush()

    rows: list[dict[str, str]] = []
    for det in detectors:
        per_doc: list[dict[str, int]] = []
        for doc in docs:
            key = (det.key, doc["doc_id"])
            if key in done:
                per_doc.append(done[key])
                continue
            counts = measure(doc, det)
            writer.writerow({"method_key": det.key, "doc_id": doc["doc_id"], **counts})
            handle.flush()
            os.fsync(handle.fileno())
            done[key] = counts
            per_doc.append(counts)
        pairs = lambda s, t: [(float(c[s]), float(c[t])) for c in per_doc]  # noqa: E731
        row: dict[str, str] = {"method": det.label, "method_key": det.key, "documents": str(len(docs)),
                               "mentions": str(sum(len(d.get("gold", [])) for d in docs))}
        row.update(_ci_fields("retrieval_spe", pairs("ret_s", "ret_t"), n_boot, 100.0, 1))
        row.update(_ci_fields("memory_spe", pairs("mem_s", "mem_t"), n_boot, 100.0, 1))
        row.update(_ci_fields("tool_spe", pairs("tool_s", "tool_t"), n_boot, 100.0, 1))
        per = _ci_fields("per_percent", pairs("res_chars", "sens_chars"), n_boot, 100.0, 1)
        row.update({"per_percent": per["per_percent"], "per_lo": per["per_percent_lo"], "per_hi": per["per_percent_hi"]})
        ret = _ci_fields("text_retention", pairs("kept_nonsens", "nonsens_chars"), n_boot, 1.0, 2)
        row.update({"text_retention": ret["text_retention"], "retention_lo": ret["text_retention_lo"], "retention_hi": ret["text_retention_hi"]})
        sem = _ci_fields("semantic_residue", pairs("sem_s", "sem_t"), n_boot, 100.0, 1)
        row.update({"semantic_residue": sem["semantic_residue"], "semantic_lo": sem["semantic_residue_lo"], "semantic_hi": sem["semantic_residue_hi"]})
        rows.append(row)
        print(f"  {det.label:44s} ret={row['retrieval_spe']:>5} mem={row['memory_spe']:>5} tool={row['tool_spe']:>5} "
              f"PER={row['per_percent']:>5} [{row['per_lo']},{row['per_hi']}] keep={row['text_retention']} sem={row['semantic_residue']}")
    handle.close()

    with results_path.open("w", encoding="utf-8", newline="") as out:
        w = csv.DictWriter(out, fieldnames=RESULT_FIELDS)
        w.writeheader()
        w.writerows(rows)

    manifest = [
        {"field": "source", "value": source},
        {"field": "documents", "value": str(len(docs))},
        {"field": "methods", "value": ";".join(method_keys)},
        {"field": "bootstrap_resamples", "value": str(n_boot)},
        {"field": "ci", "value": "document-level percentile bootstrap, 95%, seed 17"},
        {"field": "stages", "value": "AI4Privacy: retrieval=first half, memory=verbatim, tool=structured fields; PrivacyLens: retrieval=user_instruction, memory=executable_trajectory, tool=final_action"},
        {"field": "measurement", "value": "exact gold surface survival (SPE), char-coverage PER/retention, content-word semantic residue (PrivacyLens)"},
        {"field": "python", "value": platform.python_version()},
        {"field": "platform", "value": platform.platform()},
    ]
    for det in detectors:
        for k, v in det.versions.items():
            manifest.append({"field": f"{det.key}.{k}", "value": str(v)})
    with manifest_path.open("w", encoding="utf-8", newline="") as out:
        w = csv.DictWriter(out, fieldnames=["field", "value"])
        w.writeheader()
        w.writerows(manifest)
    print(f"Results: {results_path}\nDocuments: {docs_path}\nManifest: {manifest_path}")
    return results_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source", choices=["ai4privacy", "privacylens"], required=True)
    parser.add_argument("--methods", default="all", help="Comma-separated registry keys, 'all', or llm_sanitizer:<model> entries")
    parser.add_argument("--max-docs", type=int)
    parser.add_argument("--spacy-model", default="en_core_web_lg")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434/api/generate")
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--output-tag")
    args = parser.parse_args()
    keys = METHOD_ORDER if args.methods == "all" else [k.strip() for k in args.methods.split(",") if k.strip()]
    run(args.source, keys, max_docs=args.max_docs, spacy_model=args.spacy_model, ollama_url=args.ollama_url,
        n_boot=args.bootstrap, output_tag=args.output_tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
