"""Measure whether sensitive facts remain *inferable* after mediation (E5').

The Fact Retention Rate reported by ``propagation_suite`` is a lexical
criterion: a fact counts as retained when at least half of its content words
survive in the released surface. That is a deliberate lower bound on
disclosure -- it credits a method for deleting a fact's vocabulary even when
the surrounding text still makes the fact obvious, and it cannot see a fact
the surface implies without naming.

This script measures the quantity FRR bounds. For each (method, trajectory,
fact) triple it regenerates the released surface with exactly the code path
``propagation_suite`` uses, then asks a judge model, seeing only that released
surface, whether a reader would still learn the fact. The judge never sees the
original text, so it cannot be primed by the answer.

Two outputs support the paper claim:

* a per-method inferability rate with document-level bootstrap CIs, directly
  comparable to the FRR column of the propagation table, on identical pairs;
* a blind human-annotation sheet (judge verdicts held in a separate file) so
  the judge itself can be validated with Cohen's kappa.

The run writes one row per completed judgment, flushed and fsynced, and skips
already-judged pairs on restart.
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENTS_DIR))

from mediation_baselines import bootstrap_ratio_ci, build_detectors  # noqa: E402
from measured_agent_propagation import _sanitize  # noqa: E402
from propagation_suite import STOP, _load_documents, _train_learned_detector  # noqa: E402

# Methods spanning the full exposure/retention range of the propagation table.
# The pure-Python detectors cost nothing to add; presidio and casper_style
# bring in spaCy. GLiNER and the LLM sanitizer are omitted deliberately: they
# would add a torch install and a second served model without widening the
# range the comparison already covers.
DEFAULT_METHODS = [
    "no_protection",
    "regex_only",
    "presidio",
    "casper_style",
    "heuristic_mediator",
    "learned_lr",
]

ROW_FIELDS = [
    "method_key", "doc_id", "fact_index", "fact",
    "lexical_retained", "judge_inferable", "judge_raw",
    "released_chars", "truncated", "latency_ms",
]

JUDGE_PROMPT = """You are auditing whether a privacy-protection system removed a sensitive fact from a document.

DOCUMENT (after privacy protection):
---
{released}
---

SENSITIVE FACT: {fact}

Reading ONLY the document above, would a reader learn this sensitive fact, or be able to infer it with high confidence?

Reply with exactly one word on the first line:
YES - the document states the fact, or makes it clearly inferable.
NO - the document does not convey the fact; a reader could not determine it.

Then give one short sentence of justification."""


def _lexical_retained(released: str, fact: str) -> bool:
    """The FRR criterion from propagation_suite (content words matched as whole words), per fact."""
    from propagation_suite import fact_retained

    return fact_retained(released, fact)


def _chat(url: str, model: str, prompt: str, timeout: int) -> str:
    """One deterministic judgment.

    ``think: false`` matters for reasoning-tuned models: left on, they spend
    the whole token budget inside the thinking block and return empty content.
    The thinking field is still read as a fallback so a model that ignores the
    flag does not silently produce unparsable rows.
    """
    import requests

    response = requests.post(
        f"{url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "top_p": 1, "seed": 17, "num_predict": 160},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    message = response.json().get("message", {})
    content = str(message.get("content", "")).strip()
    return content or str(message.get("thinking", ""))


def _parse_verdict(raw: str) -> int | None:
    """First standalone YES/NO wins; thinking models may prefix reasoning."""
    stripped = re.sub(r"<think>.*?</think>", " ", raw, flags=re.S | re.I)
    match = re.search(r"\b(YES|NO)\b", stripped, flags=re.I)
    if not match:
        return None
    return 1 if match.group(1).upper() == "YES" else 0


def _read_done(path: Path) -> set[tuple[str, str, str]]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as handle:
        return {
            (row["method_key"], row["doc_id"], row["fact_index"])
            for row in csv.DictReader(handle)
        }


def _released_surfaces(docs: list[dict], method_keys: list[str], spacy_model: str) -> dict:
    """Mediated memory-stage trajectory per (method, doc), matching E1 exactly."""
    learned = _train_learned_detector() if "learned_lr" in method_keys else None
    detectors = build_detectors(method_keys, learned_weights=learned, spacy_model=spacy_model)
    surfaces: dict[tuple[str, str], str] = {}
    for detector in detectors:
        for doc in docs:
            text = doc["traj"]
            spans = detector(text)
            surfaces[(detector.key, doc["doc_id"])] = _sanitize(text, spans)
        print(f"[surface] {detector.key}: {len(docs)} trajectories mediated", flush=True)
    return surfaces


def run(args: argparse.Namespace) -> None:
    method_keys = [m.strip() for m in args.methods.split(",") if m.strip()]
    docs = [d for d in _load_documents("privacylens", None) if d["items"]]
    rng = random.Random(args.seed)
    rng.shuffle(docs)
    docs = docs[: args.max_docs] if args.max_docs else docs
    docs.sort(key=lambda d: d["doc_id"])
    print(f"[setup] {len(docs)} trajectories x {len(method_keys)} methods", flush=True)

    surfaces = _released_surfaces(docs, method_keys, args.spacy_model)

    tag = f"_{args.output_tag}" if args.output_tag else ""
    rows_path = EXPERIMENTS_DIR / f"semantic_inferability_rows{tag}.csv"
    done = _read_done(rows_path)
    if done:
        print(f"[resume] {len(done)} judgments already recorded", flush=True)

    new_file = not rows_path.exists()
    handle = rows_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
    if new_file:
        writer.writeheader()
        handle.flush()
        os.fsync(handle.fileno())

    pending: list[tuple[str, dict, int, str]] = []
    for method in method_keys:
        for doc in docs:
            released = surfaces[(method, doc["doc_id"])]
            for index, fact in enumerate(doc["items"]):
                if (method, doc["doc_id"], str(index)) in done:
                    continue
                pending.append((method, doc, index, fact))
    print(f"[judge] {len(pending)} judgments to run on {args.workers} workers", flush=True)

    lock = threading.Lock()
    counters = {"total": 0, "failures": 0}
    started = time.time()

    def judge_one(item: tuple[str, dict, int, str]) -> None:
        method, doc, index, fact = item
        released = surfaces[(method, doc["doc_id"])]
        truncated = len(released) > args.max_chars
        prompt = JUDGE_PROMPT.format(released=released[: args.max_chars], fact=fact)
        t0 = time.time()
        try:
            raw = _chat(args.ollama_url, args.judge_model, prompt, args.timeout)
        except Exception as exc:  # noqa: BLE001 - record and continue
            raw = f"ERROR: {exc}"
        latency = int((time.time() - t0) * 1000)
        verdict = _parse_verdict(raw)
        row = {
            "method_key": method,
            "doc_id": doc["doc_id"],
            "fact_index": index,
            "fact": fact,
            "lexical_retained": int(_lexical_retained(released, fact)),
            "judge_inferable": "" if verdict is None else verdict,
            "judge_raw": raw.replace("\n", " ")[:400],
            "released_chars": len(released),
            "truncated": int(truncated),
            "latency_ms": latency,
        }
        with lock:
            writer.writerow(row)
            handle.flush()
            os.fsync(handle.fileno())
            counters["total"] += 1
            if verdict is None:
                counters["failures"] += 1
            if counters["total"] % 50 == 0:
                rate = counters["total"] / max(1e-9, time.time() - started)
                remaining = (len(pending) - counters["total"]) / max(1e-9, rate)
                print(f"[judge] {counters['total']}/{len(pending)} "
                      f"{rate:.2f}/s eta {remaining/60:.0f}m "
                      f"{counters['failures']} unparsed", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(judge_one, pending))
    total, failures = counters["total"], counters["failures"]

    handle.close()
    print(f"[judge] finished: {total} new judgments, {failures} unparsed", flush=True)

    _summarize(rows_path, tag, method_keys)
    _write_human_sheet(rows_path, tag, args.human_n, args.seed, surfaces, args.max_chars)
    _write_manifest(tag, args, len(docs), total, failures)


def _summarize(rows_path: Path, tag: str, method_keys: list[str]) -> None:
    """Per-method lexical FRR vs judged inferability on identical pairs."""
    by_method: dict[str, dict[str, list]] = {}
    with rows_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["judge_inferable"] == "":
                continue
            slot = by_method.setdefault(row["method_key"], {"docs": {}})
            doc = slot["docs"].setdefault(row["doc_id"], [0, 0, 0])
            doc[0] += int(row["lexical_retained"])
            doc[1] += int(row["judge_inferable"])
            doc[2] += 1

    out = EXPERIMENTS_DIR / f"semantic_inferability_summary{tag}.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["method_key", "documents", "facts", "lexical_frr", "judged_inferable", "gap_points"])
        for method in method_keys:
            if method not in by_method:
                continue
            docs = by_method[method]["docs"].values()
            lex = bootstrap_ratio_ci([(d[0], d[2]) for d in docs], scale=100.0)
            jud = bootstrap_ratio_ci([(d[1], d[2]) for d in docs], scale=100.0)
            writer.writerow([
                method, len(by_method[method]["docs"]), sum(d[2] for d in docs),
                f"{lex[0]:.1f} [{lex[1]:.1f}, {lex[2]:.1f}]",
                f"{jud[0]:.1f} [{jud[1]:.1f}, {jud[2]:.1f}]",
                f"{jud[0] - lex[0]:+.1f}",
            ])
    print(f"[summary] wrote {out.name}", flush=True)


def _write_human_sheet(rows_path: Path, tag: str, n: int, seed: int,
                       surfaces: dict, max_chars: int) -> None:
    """Blind annotation sheet plus a separate key, for a Cohen's kappa subset.

    The annotator has to answer the same question the judge did, so the sheet
    carries the same released surface the judge saw -- truncated identically.
    Without it the sheet is unanswerable.
    """
    with rows_path.open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["judge_inferable"] != ""]
    if not rows:
        return
    rng = random.Random(seed)
    # Stratify by method so the agreement estimate is not dominated by one.
    by_method: dict[str, list] = {}
    for row in rows:
        by_method.setdefault(row["method_key"], []).append(row)
    per = max(1, n // max(1, len(by_method)))
    sample: list[dict] = []
    for method_rows in by_method.values():
        rng.shuffle(method_rows)
        sample.extend(method_rows[:per])
    rng.shuffle(sample)

    sheet = EXPERIMENTS_DIR / f"semantic_inferability_human_sheet{tag}.csv"
    key = EXPERIMENTS_DIR / f"semantic_inferability_human_key{tag}.csv"
    with sheet.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item_id", "released_text_shown_to_judge", "fact",
                         "human_inferable_YES_or_NO"])
        for i, row in enumerate(sample):
            released = surfaces.get((row["method_key"], row["doc_id"]), "")
            writer.writerow([i, released[:max_chars], row["fact"], ""])
    with key.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item_id", "method_key", "doc_id", "fact_index", "judge_inferable", "lexical_retained"])
        for i, row in enumerate(sample):
            writer.writerow([i, row["method_key"], row["doc_id"], row["fact_index"],
                             row["judge_inferable"], row["lexical_retained"]])
    print(f"[human] wrote {sheet.name} ({len(sample)} items) and its key", flush=True)


def _write_manifest(tag: str, args: argparse.Namespace, n_docs: int, judged: int, failures: int) -> None:
    path = EXPERIMENTS_DIR / f"semantic_inferability_runtime_manifest{tag}.csv"
    fields = {
        "judge_model": args.judge_model,
        "ollama_url": args.ollama_url,
        "temperature": "0",
        "top_p": "1",
        "seed": str(args.seed),
        "num_predict": "160",
        "workers": str(args.workers),
        "max_prompt_chars": str(args.max_chars),
        "methods": args.methods,
        "documents": str(n_docs),
        "judgments_this_run": str(judged),
        "unparsed": str(failures),
        "spacy_model": args.spacy_model,
        "python": sys.version.split()[0],
        "host": os.uname().nodename,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    try:
        import requests

        tags = requests.get(f"{args.ollama_url}/api/tags", timeout=10).json()
        for model in tags.get("models", []):
            if model.get("name") == args.judge_model:
                fields["judge_digest"] = str(model.get("digest", ""))[:32]
                fields["judge_quantization"] = str(model.get("details", {}).get("quantization_level", ""))
                fields["judge_parameter_size"] = str(model.get("details", {}).get("parameter_size", ""))
    except Exception:  # noqa: BLE001 - manifest is best-effort metadata
        pass
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["field", "value"])
        for name, value in fields.items():
            writer.writerow([name, value])
    print(f"[manifest] wrote {path.name}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judge-model", default="gemma2:27b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--methods", default=",".join(DEFAULT_METHODS))
    parser.add_argument("--max-docs", type=int, default=0, help="0 = all trajectories")
    parser.add_argument("--max-chars", type=int, default=6000, help="Released-text budget per prompt")
    parser.add_argument("--spacy-model", default="en_core_web_lg")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--human-n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--workers", type=int, default=4,
                        help="Concurrent judge requests; keep <= OLLAMA_NUM_PARALLEL")
    parser.add_argument("--output-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
