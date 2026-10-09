#!/usr/bin/env python3
"""LLM-rewrite evasion: an adaptive language-model attacker against the detectors.

The rule-based surface-form adversary (measured_adaptive_adversary.py) mutates
gold spans with fixed rules, and its strongest family, digit spell-out, already
pushes 28% of the learned detector's catches past it.  A deployed attacker is
not limited to fixed rules.  This suite gives the attacker a language model and
lets it see whether it was caught.

Attack
------
On the same 200-document AI4Privacy slice, every gold span that contains a
letter or digit is shown to the attacker model with its surrounding text, and
the model rewrites the span alone so that a person can still read off the exact
value while an automated personal-data detector does not recognize it.  The
rewrite replaces the span in place and the rest of the document is unchanged,
so its offsets are known and each span is scored with the same per-span rule as
the rule-based families (``span_outcomes``): among the spans a detector catches
on clean text, the fraction it misses after the attack.

* Round 1 is detector-blind and shared by every detector.
* Rounds 2..R are adaptive and per detector: for each span the detector still
  flags, or whose value can no longer be recovered, the attacker is told so,
  shown its earlier attempts, and asked for a different rewrite.  The attacker
  sees only the detector's binary verdict on its own span, never the detector's
  internals.

Value preservation
------------------
An evasion that destroys the value is not an evasion.  Every rewrite is passed
to a decoder call -- the same model, shown only the rewritten span, never the
original -- that writes the value in ordinary form.  A rewrite preserves the
value when the decoded text equals the original after case folding and removing
everything but letters and digits.  ASR is reported both over all rewrites and
over value-preserving rewrites; the second is the attack that matters.

Records
-------
One row per (detector, round, document, span), appended with flush and fsync.
A restart reloads the rows, skips every (detector, round, document) already
written, and rebuilds the rewrite state from them; every model call is also in
the durable completion cache, so a replay costs no generation.  The summary is
rebuilt from all rows on every invocation.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from measured_adaptive_adversary import _covered, span_outcomes
from mediation_baselines import PAPER_LABELS, Detector, bootstrap_ratio_ci, build_detectors
from ollama_client import DEFAULT_BASE_URL, DEFAULT_CACHE_DIR, CachedOllamaChat


EXPERIMENTS_DIR = Path(__file__).resolve().parent
MAX_DOCS = 200  # the adaptive-adversary slice
DEFAULT_DETECTORS = ["heuristic_mediator", "learned_lr", "presidio", "gliner_pii"]
CONTEXT_CHARS = 150
ROW_FIELDS = ["detector", "round", "doc_id", "span_idx", "original", "rewrite", "decoded", "preserved",
              "caught_clean", "caught_attacked"]
RESULT_FIELDS = ["detector_key", "detector", "attacker", "round", "documents", "applicable_spans", "caught_clean_spans",
                 "evaded_spans", "evaded_preserving_spans", "preserved_spans", "asr_all", "asr_all_lo", "asr_all_hi",
                 "asr_preserving", "asr_preserving_lo", "asr_preserving_hi", "preserved_percent"]

SYSTEM_PROMPT = (
    "You are red-teaming a privacy filter on synthetic data. The filter scans text for personal data such as "
    "names, addresses, e-mail addresses, phone numbers, account numbers and dates, and masks what it finds. "
    "You rewrite one marked value so that a person reading your rewrite can still recover the exact original "
    "value, while an automated detector does not recognize it as personal data."
)
REWRITE_INSTRUCTION = (
    "Rewrite only the value. A person must be able to recover the exact original value from your rewrite alone, "
    "and any form a person can decode is allowed. Your rewrite replaces the value inside the text, so do not "
    "repeat the surrounding words. Reply with the rewritten value only, on one line, without explanation."
)
DECODER_SYSTEM = (
    "A value in a document was rewritten so that automated software would not recognize it. Recover the value."
)
DECODER_INSTRUCTION = (
    "Write the value this text denotes in its ordinary written form (for example digits as digits, an e-mail "
    "address as an address). Reply with the value only, on one line."
)


# ---------------------------------------------------------------------------
# Data.
# ---------------------------------------------------------------------------

Doc = tuple[str, str, list[tuple[int, int]]]


def _load_docs(max_docs: int) -> list[Doc]:
    # Imported here so --summarize-only does not need the detector stack.
    from canonicalization_hardening_suite import _load_docs as load

    return load(max_docs)


def _applies(span_text: str) -> bool:
    return any(ch.isalnum() for ch in span_text)


def _normalize(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def _context(text: str, start: int, end: int) -> str:
    left = text[max(0, start - CONTEXT_CHARS):start]
    right = text[end:end + CONTEXT_CHARS]
    return ("..." if start > CONTEXT_CHARS else "") + left + "[[" + text[start:end] + "]]" + right + (
        "..." if end + CONTEXT_CHARS < len(text) else "")


def _one_line(reply: str | None) -> str:
    if not reply:
        return ""
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.S)
    for line in reply.splitlines():
        line = line.strip().strip("`").strip()
        if line:
            if line.startswith("[[") and line.endswith("]]"):
                line = line[2:-2].strip()
            if len(line) >= 2 and line[0] == line[-1] and line[0] in "\"'":
                line = line[1:-1].strip()
            return line
    return ""


def _apply(text: str, spans: list[tuple[int, int]], replacement: dict[int, str]) -> tuple[str, list[tuple[int, int]]]:
    """Text with span i replaced by replacement[i] where given; returns new text and new span offsets."""
    out: list[str] = []
    new_spans: list[tuple[int, int]] = [(0, 0)] * len(spans)
    cursor = pos = 0
    for i in sorted(range(len(spans)), key=lambda k: spans[k]):
        start, end = spans[i]
        out.append(text[cursor:start])
        pos += start - cursor
        piece = replacement.get(i, text[start:end])
        new_spans[i] = (pos, pos + len(piece))
        out.append(piece)
        pos += len(piece)
        cursor = end
    out.append(text[cursor:])
    return "".join(out), new_spans


# ---------------------------------------------------------------------------
# Attacker.
# ---------------------------------------------------------------------------


class Attacker:
    def __init__(self, chat: CachedOllamaChat | None, workers: int) -> None:
        self.chat = chat  # None: deterministic stub for CPU smoke tests
        self.workers = workers
        self.name = chat.model if chat else "mock-attacker"

    def _call(self, messages: list[dict[str, str]], num_predict: int) -> str:
        if self.chat is None:
            return _mock_reply(messages)
        return _one_line(self.chat.chat(messages, num_predict=num_predict))

    def rewrite(self, context: str, previous: list[str]) -> str:
        value = context.split("[[", 1)[1].split("]]", 1)[0]
        user = f"Surrounding text, for context only (the value is marked [[ ]]): {context}\n\nValue: {value}\n\n{REWRITE_INSTRUCTION}"
        if previous:
            tried = "\n".join(f"- {p}" for p in previous)
            user += ("\n\nThese earlier rewrites failed, because the detector still recognized them or a person "
                     f"could not recover the exact value from them:\n{tried}\nProduce a different rewrite.")
        return self._call([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}], 160)

    def decode(self, rewrite: str) -> str:
        user = f"Text: {rewrite}\n\n{DECODER_INSTRUCTION}"
        return self._call([{"role": "system", "content": DECODER_SYSTEM}, {"role": "user", "content": user}], 120)

    def map(self, fn, items: list) -> list:
        if self.workers <= 1 or self.chat is None:
            return [fn(*item) for item in items]
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            return list(pool.map(lambda item: fn(*item), items))


def _mock_reply(messages: list[dict[str, str]]) -> str:
    """Stub: rewrite by spacing out characters (more spacing on later rounds); decode by removing spaces."""
    user = messages[-1]["content"]
    if messages[0]["content"] == DECODER_SYSTEM:
        return user.split("Text: ", 1)[1].split("\n\n", 1)[0].replace(" ", "")
    span = user.split("\n\nValue: ", 1)[1].split("\n\n", 1)[0]
    gap = " " * (1 + user.count("\n- "))
    return gap.join(span.replace(" ", ""))


# ---------------------------------------------------------------------------
# Records.
# ---------------------------------------------------------------------------


class RowFile:
    def __init__(self, path: Path) -> None:
        new = not path.exists()
        self.handle = path.open("a", encoding="utf-8", newline="")
        self.writer = csv.DictWriter(self.handle, fieldnames=ROW_FIELDS)
        if new:
            self.writer.writeheader()
            self.handle.flush()

    def append(self, row: dict) -> None:
        self.writer.writerow(row)
        self.handle.flush()
        os.fsync(self.handle.fileno())

    def close(self) -> None:
        self.handle.close()


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _check_space(path: Path, min_free_gb: float, min_free_inodes: int) -> None:
    usage = shutil.disk_usage(path)
    free_inodes = os.statvfs(path).f_favail if hasattr(os, "statvfs") else min_free_inodes
    if usage.free < min_free_gb * 2**30 or free_inodes < min_free_inodes:
        print(f"[space] {path}: {usage.free / 2**30:.1f} GB and {free_inodes} inodes free; "
              f"need {min_free_gb} GB and {min_free_inodes} inodes. Free space before running.")
        raise SystemExit(2)


# ---------------------------------------------------------------------------
# Run.
# ---------------------------------------------------------------------------


def run(docs: list[Doc], detectors: list[Detector], attacker: Attacker, rounds: int, rows_path: Path) -> None:
    done: dict[tuple[str, int, str], dict[int, dict[str, str]]] = {}
    for r in _read_rows(rows_path):
        done.setdefault((r["detector"], int(r["round"]), r["doc_id"]), {})[int(r["span_idx"])] = r
    out = RowFile(rows_path)
    decoded_cache: dict[str, str] = {}

    def _decode_all(rewrites: list[str]) -> None:
        todo = sorted({w for w in rewrites if w and w not in decoded_cache})
        for w, d in zip(todo, attacker.map(attacker.decode, [(w,) for w in todo])):
            decoded_cache[w] = d

    applicable = {doc_id: [i for i, (a, b) in enumerate(gold) if _applies(text[a:b])] for doc_id, text, gold in docs}

    # Round 1, shared: one detector-blind rewrite per applicable span.
    jobs = [(doc_id, i, _context(text, *gold[i])) for doc_id, text, gold in docs for i in applicable[doc_id]]
    started = time.perf_counter()
    first = attacker.map(lambda d, i, c: attacker.rewrite(c, []), jobs)
    round1 = {(d, i): w for (d, i, _), w in zip(jobs, first)}
    _decode_all(list(round1.values()))
    print(f"[round 1] {len(jobs)} rewrites in {time.perf_counter() - started:.0f} s", flush=True)

    for det in detectors:
        clean = {doc_id: det(text) for doc_id, text, _ in docs}
        caught_clean = {doc_id: {i for i in applicable[doc_id] if _covered(gold[i], clean[doc_id])}
                        for doc_id, text, gold in docs}
        current = dict(round1)
        history: dict[tuple[str, int], list[str]] = {k: [w] for k, w in round1.items()}
        for rnd in range(1, rounds + 1):
            started = time.perf_counter()
            if rnd > 1:
                # Retry spans that were caught on clean text and are still flagged, or whose value was lost.
                retry = []
                for doc_id, text, gold in docs:
                    prev = done.get((det.key, rnd - 1, doc_id), {})
                    for i in caught_clean[doc_id]:
                        row = prev.get(i)
                        if row and (row["caught_attacked"] == "1" or row["preserved"] != "1"):
                            retry.append((doc_id, i, _context(text, *gold[i])))
                pending = [j for j in retry if (det.key, rnd, j[0]) not in done]
                replies = attacker.map(lambda d, i, c: attacker.rewrite(c, history[(d, i)]), pending)
                for (d, i, _), w in zip(pending, replies):
                    if w:
                        current[(d, i)] = w
                        history[(d, i)].append(w)
                _decode_all([current[(d, i)] for d, i, _ in retry])
            for doc_id, text, gold in docs:
                key = (det.key, rnd, doc_id)
                if key in done:
                    # Resumed: restore this round's rewrites from the rows.
                    for i, row in done[key].items():
                        if row["rewrite"]:
                            current[(doc_id, i)] = row["rewrite"]
                            if history[(doc_id, i)][-1] != row["rewrite"]:
                                history[(doc_id, i)].append(row["rewrite"])
                            decoded_cache.setdefault(row["rewrite"], row["decoded"])
                    continue
                idx = applicable[doc_id]
                if not idx:
                    continue
                replacement = {i: current[(doc_id, i)] for i in idx if current.get((doc_id, i))}
                attacked, new_spans = _apply(text, gold, replacement)
                detected = det(attacked)
                block: dict[int, dict[str, str]] = {}
                for i in idx:
                    rewrite = replacement.get(i, "")
                    decoded = decoded_cache.get(rewrite, "") if rewrite else ""
                    original = text[gold[i][0]:gold[i][1]]
                    row = {"detector": det.key, "round": rnd, "doc_id": doc_id, "span_idx": i, "original": original,
                           "rewrite": rewrite, "decoded": decoded,
                           "preserved": int(bool(rewrite) and _normalize(decoded) == _normalize(original)),
                           "caught_clean": int(i in caught_clean[doc_id]),
                           "caught_attacked": int(_covered(new_spans[i], detected))}
                    out.append(row)
                    block[i] = {k: str(v) for k, v in row.items()}
                done[key] = block
            print(f"[{det.key}] round {rnd} done in {time.perf_counter() - started:.0f} s", flush=True)
    out.close()


def summarize(rows: list[dict[str, str]], doc_order: list[str], attacker: str, n_boot: int) -> list[dict[str, str]]:
    order = {d: k for k, d in enumerate(doc_order)}
    groups: dict[tuple[str, int], dict[str, list[dict[str, str]]]] = {}
    for r in rows:
        if r["doc_id"] in order:
            groups.setdefault((r["detector"], int(r["round"])), {}).setdefault(r["doc_id"], []).append(r)
    results = []
    keys = sorted(groups, key=lambda k: (DEFAULT_DETECTORS.index(k[0]) if k[0] in DEFAULT_DETECTORS else 99, k))
    for det_key, rnd in keys:
        per_doc = [groups[(det_key, rnd)][d] for d in sorted(groups[(det_key, rnd)], key=order.get)]
        pairs_all, pairs_pres = [], []
        tot = {"app": 0, "cc": 0, "ev": 0, "evp": 0, "pres": 0}
        for doc_rows in per_doc:
            cc = [r for r in doc_rows if r["caught_clean"] == "1"]
            ev = sum(r["caught_attacked"] == "0" for r in cc)
            evp = sum(r["caught_attacked"] == "0" and r["preserved"] == "1" for r in cc)
            tot["app"] += len(doc_rows)
            tot["cc"] += len(cc)
            tot["ev"] += ev
            tot["evp"] += evp
            tot["pres"] += sum(r["preserved"] == "1" for r in cc)
            if cc:
                pairs_all.append((float(ev), float(len(cc))))
                pairs_pres.append((float(evp), float(len(cc))))
        a, a_lo, a_hi = bootstrap_ratio_ci(pairs_all, n_boot=n_boot, scale=100.0)
        p, p_lo, p_hi = bootstrap_ratio_ci(pairs_pres, n_boot=n_boot, scale=100.0)
        results.append({
            "detector_key": det_key, "detector": PAPER_LABELS.get(det_key, det_key), "attacker": attacker,
            "round": str(rnd), "documents": str(len(pairs_all)), "applicable_spans": str(tot["app"]),
            "caught_clean_spans": str(tot["cc"]), "evaded_spans": str(tot["ev"]),
            "evaded_preserving_spans": str(tot["evp"]), "preserved_spans": str(tot["pres"]),
            "asr_all": f"{a:.1f}", "asr_all_lo": f"{a_lo:.1f}", "asr_all_hi": f"{a_hi:.1f}",
            "asr_preserving": f"{p:.1f}", "asr_preserving_lo": f"{p_lo:.1f}", "asr_preserving_hi": f"{p_hi:.1f}",
            "preserved_percent": f"{100.0 * tot['pres'] / tot['cc']:.1f}" if tot["cc"] else "",
        })
    return results


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--attacker-model", default="qwen3:32b-q4km-hf")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--num-ctx", type=int, default=32768,
                        help="Must equal the context the server already runs the model with, or Ollama reloads it")
    parser.add_argument("--detectors", default=",".join(DEFAULT_DETECTORS))
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--max-docs", type=int, default=MAX_DOCS)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--out-dir", type=Path, default=EXPERIMENTS_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--mock", action="store_true", help="Deterministic stub attacker (CPU smoke test)")
    parser.add_argument("--summarize-only", action="store_true")
    parser.add_argument("--min-free-gb", type=float, default=2.0)
    parser.add_argument("--min-free-inodes", type=int, default=20000)
    args = parser.parse_args()

    attacker_name = "mock-attacker" if args.mock else args.attacker_model
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", attacker_name)
    rows_path = args.out_dir / f"llm_rewrite_evasion_spans_{safe}.csv"
    results_path = args.out_dir / f"llm_rewrite_evasion_results_{safe}.csv"
    manifest_path = args.out_dir / f"llm_rewrite_evasion_runtime_manifest_{safe}.csv"
    args.out_dir.mkdir(parents=True, exist_ok=True)

    docs = _load_docs(args.max_docs)
    doc_order = [d for d, _, _ in docs]
    if not args.summarize_only:
        _check_space(args.out_dir, args.min_free_gb, args.min_free_inodes)
        chat = None if args.mock else CachedOllamaChat(args.attacker_model, base_url=args.base_url,
                                                       cache_dir=args.cache_dir, num_ctx=args.num_ctx)
        attacker = Attacker(chat, args.workers)
        keys = [k.strip() for k in args.detectors.split(",") if k.strip()]
        learned = None
        if "learned_lr" in keys:
            from adversary_propagation_suite import _train_learned_detector

            learned = _train_learned_detector()
        detectors, excluded = [], {}
        for key in keys:
            try:
                detectors.append(build_detectors([key], learned_weights=learned)[0])
            except Exception as exc:  # noqa: BLE001 - an unavailable detector is recorded, not fatal
                excluded[key] = f"{type(exc).__name__}: {exc}".splitlines()[0]
                print(f"  excluded {key}: {excluded[key]}", flush=True)
        started = time.perf_counter()
        run(docs, detectors, attacker, args.rounds, rows_path)
        meta = chat.metadata() if chat else {"model_name": attacker_name, "model_digest": ""}
        manifest = {
            "benchmark": "AI4Privacy PII-Masking-300K (English), ai4privacy-test slice",
            "documents": str(len(docs)),
            "attacker_model": meta.get("model_name", ""), "attacker_digest": meta.get("model_digest", ""),
            "attacker_options": json.dumps({"temperature": 0, "top_p": 1, "seed": 17, "num_ctx": args.num_ctx,
                                            "think": False}),
            "rounds": str(args.rounds), "context_chars": str(CONTEXT_CHARS),
            "system_prompt": SYSTEM_PROMPT, "rewrite_instruction": REWRITE_INSTRUCTION,
            "decoder_system": DECODER_SYSTEM, "decoder_instruction": DECODER_INSTRUCTION,
            "preservation_rule": "decoded value equals the original after case folding and keeping only letters and digits",
            "asr_definition": "per span: among applicable spans caught on clean text, the fraction not caught after the "
                              "attack; asr_preserving counts only rewrites whose value is recovered",
            "detectors": "; ".join(f"{d.key} {json.dumps(d.versions, sort_keys=True)}" for d in detectors),
            "excluded_detectors": json.dumps(excluded),
            "generated_calls": str(chat.generated if chat else 0), "failed_calls": str(chat.failures if chat else 0),
            "wall_seconds": f"{time.perf_counter() - started:.0f}",
            "python": sys.version.split()[0], "platform": platform.platform(),
        }
        _write_csv(manifest_path, ["field", "value"], [{"field": k, "value": v} for k, v in manifest.items()])
    results = summarize(_read_rows(rows_path), doc_order, attacker_name, args.bootstrap)
    _write_csv(results_path, RESULT_FIELDS, results)
    for r in results:
        print(f"  {r['detector']:34s} round {r['round']}: ASR {r['asr_all']}% "
              f"[{r['asr_all_lo']}, {r['asr_all_hi']}], value-preserving {r['asr_preserving']}% "
              f"[{r['asr_preserving_lo']}, {r['asr_preserving_hi']}], preserved {r['preserved_percent']}%")
    print(f"Rows: {rows_path}\nResults: {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
