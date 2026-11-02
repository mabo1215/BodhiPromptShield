#!/usr/bin/env python3
"""Give a transformer tagger the same training data as the learned detector.

The AI4Privacy exposure comparison is not like-for-like in one respect the
operating-point sweep cannot remove: the logistic-regression tagger trained on
3,000 documents of this source, and the zero-shot detectors did not. At matched
retention it still leads them by 13-14 points. This asks how much of that lead is
the training data rather than the model family, by fine-tuning a small transformer
token classifier on the identical 3,000 documents and scoring it on the identical
300 held-out documents with the identical per-document counts.

Design choices, fixed in advance and not tuned on the held-out documents:

* the task is the tagger's task: one binary decision per word token, on the same
  word tokenization, with the same "at least half its characters are gold" label;
* subword probabilities become a word score by taking the maximum, so a word is
  either masked whole or kept whole, as it is for the logistic-regression tagger;
* architecture, learning rate, batch size and epoch count are the fixed values
  below; the development split is not used, and no threshold is selected;
* several seeds are trained, so that the reported gap can be read against
  training-run variation. The first seed is the reported one.

Outputs, next to this script, one set per seed:

* ``ai4privacy_parity_tagger_documents_seed<seed>.csv``: one row per (threshold,
  document), appended and flushed per document so that a run can resume;
* ``ai4privacy_parity_tagger_summary.csv``: PER, retention, and span precision with
  document-level bootstrap intervals per seed and threshold;
* ``ai4privacy_parity_tagger_matched.csv``: at each retention level, the lowest PER
  each seed reaches while keeping at least that much text, and the paired difference
  from the logistic-regression tagger over the same documents;
* ``ai4privacy_parity_tagger_transfer.csv``: both taggers, trained on AI4Privacy, on the
  held-out clinical notes, since a lead measured in domain says nothing about transfer;
* ``ai4privacy_parity_tagger_manifest.csv``.

Weights are checkpointed per epoch outside the recorded artifacts, so an interrupted
training run restarts from its last completed epoch.

Run with a GPU build of PyTorch:

    python src/experiments/ai4privacy_parity_tagger.py --seeds 17,18,19
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import platform
import random
import sys
import time
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENTS_DIR))

import ai4privacy_lightweight_classifier_baseline as clf  # noqa: E402
from ai4privacy_matched_baseline_suite import _merge_spans  # noqa: E402
from ai4privacy_operating_points import ANCHOR_FIELDS, DOCUMENTS as LR_DOCUMENTS, RETENTION_LEVELS  # noqa: E402
from downstream_paired_tests import paired_bootstrap_diff  # noqa: E402
from mediation_baselines import bootstrap_ratio_ci  # noqa: E402
from propagation_suite import AI4_PATH, _load_documents, _measure_ai4privacy  # noqa: E402

SUMMARY = EXPERIMENTS_DIR / "ai4privacy_parity_tagger_summary.csv"
MATCHED = EXPERIMENTS_DIR / "ai4privacy_parity_tagger_matched.csv"
TRANSFER = EXPERIMENTS_DIR / "ai4privacy_parity_tagger_transfer.csv"
MANIFEST = EXPERIMENTS_DIR / "ai4privacy_parity_tagger_manifest.csv"
CLINICAL_PATH = EXPERIMENTS_DIR / "physionet_deid_relabeled_export.jsonl"
CLINICAL_DOCS = 300  # the export holds fewer; the cross-domain experiment uses the same limit
CHECKPOINTS = EXPERIMENTS_DIR / "parity_tagger_checkpoints"

MODEL_ID = "distilbert-base-cased"
EPOCHS = 4
LEARNING_RATE = 3e-5
BATCH_SIZE = 16
MAX_LENGTH = 256
STRIDE = 64
DEFAULT_THRESHOLD = 0.5
GRID = (0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.998, 0.999)
FIELDS = ["seed", "threshold", "doc_id", *ANCHOR_FIELDS]


def _documents_path(seed: int) -> Path:
    return EXPERIMENTS_DIR / f"ai4privacy_parity_tagger_documents_seed{seed}.csv"


def _train_records() -> list[dict]:
    """The same documents, in the same order, as the logistic-regression tagger."""
    records = clf._load_records(AI4_PATH)
    return [r for r in records if str(r.get("split")) == "ai4privacy-train"][: clf.TRAIN_DOC_LIMIT]


def _encode_windows(tokenizer, text: str) -> list[dict]:
    encoded = tokenizer(text, truncation=True, max_length=MAX_LENGTH, stride=STRIDE,
                        return_overflowing_tokens=True, return_offsets_mapping=True)
    return [{"input_ids": encoded["input_ids"][i], "attention_mask": encoded["attention_mask"][i],
             "offsets": encoded["offset_mapping"][i]} for i in range(len(encoded["input_ids"]))]


def _word_labels(text: str, gold_spans: list[tuple[int, int]]) -> list[tuple[int, int, int]]:
    gold_chars = clf._char_coverage(gold_spans)
    return [(start, end, int(clf._is_sensitive_token(start, end, gold_chars)))
            for start, end, _token in clf._tokenize(text)]


def _training_windows(records: list[dict], tokenizer) -> list[dict]:
    """Each subword inherits the label of the word it falls in; others are ignored."""
    windows: list[dict] = []
    for record in records:
        text = str(record.get("text", ""))
        gold = [(int(s["start"]), int(s["end"])) for s in record.get("phi_spans", []) if isinstance(s, dict)]
        words = _word_labels(text, gold)
        for window in _encode_windows(tokenizer, text):
            labels: list[int] = []
            cursor = 0
            for start, end in window["offsets"]:
                if end <= start:
                    labels.append(-100)
                    continue
                while cursor < len(words) and words[cursor][1] <= start:
                    cursor += 1
                inside = cursor < len(words) and words[cursor][0] < end
                labels.append(words[cursor][2] if inside else -100)
            windows.append({"input_ids": window["input_ids"], "attention_mask": window["attention_mask"],
                            "labels": labels})
    return windows


def _collate(batch: list[dict], pad_id: int, torch):
    width = max(len(item["input_ids"]) for item in batch)

    def pad(key: str, fill: int):
        return torch.tensor([item[key] + [fill] * (width - len(item[key])) for item in batch])
    return pad("input_ids", pad_id), pad("attention_mask", 0), pad("labels", -100)


def _train(seed: int, epochs: int, device: str, smoke: bool):
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    random.seed(seed)
    torch.manual_seed(seed)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    records = _train_records()[: 32 if smoke else None]
    windows = _training_windows(records, tokenizer)
    print(f"[seed {seed}] {len(records)} training documents, {len(windows)} windows", flush=True)

    folder = CHECKPOINTS / f"{MODEL_ID.replace('/', '_')}_seed{seed}"
    folder.mkdir(parents=True, exist_ok=True)
    start_epoch = 0
    for epoch in range(epochs, 0, -1):
        if (folder / f"epoch{epoch}.done").exists():
            start_epoch = epoch
            break
    source = str(folder / "latest") if start_epoch else MODEL_ID
    model = AutoModelForTokenClassification.from_pretrained(source, num_labels=2).to(device)
    if start_epoch >= epochs:
        print(f"[seed {seed}] training already complete", flush=True)
        return tokenizer, model.eval()

    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    order = list(range(len(windows)))
    for epoch in range(1, epochs + 1):
        # The shuffle is drawn for every epoch, so a resumed run sees the same order.
        random.shuffle(order)
        if epoch <= start_epoch:
            continue
        model.train()
        total, batches, began = 0.0, 0, time.time()
        for i in range(0, len(order), BATCH_SIZE):
            ids, mask, labels = _collate([windows[j] for j in order[i:i + BATCH_SIZE]],
                                         tokenizer.pad_token_id, torch)
            out = model(input_ids=ids.to(device), attention_mask=mask.to(device), labels=labels.to(device))
            optimizer.zero_grad()
            out.loss.backward()
            optimizer.step()
            total += out.loss.item()
            batches += 1
        print(f"[seed {seed}] epoch {epoch}/{epochs}: loss {total / max(batches, 1):.4f} "
              f"in {time.time() - began:.0f}s", flush=True)
        model.save_pretrained(folder / "latest")
        (folder / f"epoch{epoch}.done").touch()
    return tokenizer, model.eval()


def _scorer(tokenizer, model, device: str):
    """(word start, word end, score) on the tagger's own word tokenization."""
    import torch

    def score(text: str) -> list[tuple[int, int, float]]:
        words = clf._tokenize(text)
        best = [0.0] * len(words)
        for window in _encode_windows(tokenizer, text):
            with torch.no_grad():
                logits = model(input_ids=torch.tensor([window["input_ids"]]).to(device),
                               attention_mask=torch.tensor([window["attention_mask"]]).to(device)).logits[0]
            probabilities = torch.softmax(logits, dim=-1)[:, 1].tolist()
            cursor = 0
            for (start, end), probability in zip(window["offsets"], probabilities):
                if end <= start:
                    continue
                while cursor < len(words) and words[cursor][1] <= start:
                    cursor += 1
                if cursor < len(words) and words[cursor][0] < end:
                    best[cursor] = max(best[cursor], probability)
        return [(w[0], w[1], s) for w, s in zip(words, best)]
    return score


def _evaluate(seed: int, docs: list[dict], tokenizer, model, device: str) -> None:
    path = _documents_path(seed)
    done: set[tuple[str, str]] = set()
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            done = {(r["threshold"], r["doc_id"]) for r in csv.DictReader(handle)}
    write_header = not path.exists() or path.stat().st_size == 0
    scorer = _scorer(tokenizer, model, device)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
            handle.flush()
        for doc in docs:
            if all((str(t), doc["doc_id"]) in done for t in GRID):
                continue
            scored = scorer(doc["text"])
            for tau in GRID:
                if (str(tau), doc["doc_id"]) in done:
                    continue
                spans = _merge_spans([(a, b) for a, b, s in scored if s >= tau])
                counts = _measure_ai4privacy(doc, lambda _text, spans=spans: spans)
                writer.writerow({"seed": seed, "threshold": tau, "doc_id": doc["doc_id"],
                                 **{k: counts[k] for k in ANCHOR_FIELDS}})
            handle.flush()
            os.fsync(handle.fileno())


def _ratio(sub: list[dict], num: str, den: str, n_boot: int, scale: float) -> tuple[float, float, float]:
    return bootstrap_ratio_ci([(float(r[num]), float(r[den])) for r in sub], n_boot=n_boot, scale=scale)


def _learned_table(n_boot: int) -> dict[float, dict]:
    with LR_DOCUMENTS.open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["method_key"] == "learned_lr"]
    grouped: dict[float, list[dict]] = {}
    for row in rows:
        grouped.setdefault(float(row["threshold"]), []).append(row)
    table = {}
    for tau, sub in grouped.items():
        per, plo, phi = _ratio(sub, "res_chars", "sens_chars", n_boot, 100.0)
        ret = _ratio(sub, "kept_nonsens", "nonsens_chars", n_boot, 1.0)[0]
        table[tau] = {"tau": tau, "per": per, "ret": ret, "cell": f"{per:.1f} [{plo:.1f}, {phi:.1f}]",
                      "docs": {r["doc_id"]: r for r in sub}}
    return table


def _write_tables(seeds: list[int], n_boot: int) -> None:
    learned = _learned_table(n_boot)
    per_seed: dict[int, dict[float, dict]] = {}
    with SUMMARY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["seed", "threshold", "is_default", "documents", "per_percent", "retention",
                         "span_precision", "per_point", "retention_point"])
        for seed in seeds:
            with _documents_path(seed).open(encoding="utf-8", newline="") as source:
                rows = list(csv.DictReader(source))
            grouped: dict[float, list[dict]] = {}
            for row in rows:
                grouped.setdefault(float(row["threshold"]), []).append(row)
            per_seed[seed] = {}
            for tau, sub in sorted(grouped.items()):
                per, plo, phi = _ratio(sub, "res_chars", "sens_chars", n_boot, 100.0)
                ret, rlo, rhi = _ratio(sub, "kept_nonsens", "nonsens_chars", n_boot, 1.0)
                pre, qlo, qhi = _ratio(sub, "span_tp", "span_pred", n_boot, 1.0)
                writer.writerow([seed, tau, int(tau == DEFAULT_THRESHOLD), len(sub),
                                 f"{per:.1f} [{plo:.1f}, {phi:.1f}]", f"{ret:.3f} [{rlo:.3f}, {rhi:.3f}]",
                                 f"{pre:.2f} [{qlo:.2f}, {qhi:.2f}]", f"{per:.2f}", f"{ret:.4f}"])
                per_seed[seed][tau] = {"tau": tau, "per": per, "ret": ret,
                                       "cell": f"{per:.1f} [{plo:.1f}, {phi:.1f}]",
                                       "docs": {r["doc_id"]: r for r in sub}}

    with MATCHED.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["retention_at_least", "seed", "threshold", "retention", "per_percent",
                         "learned_threshold", "learned_retention", "learned_per_percent",
                         "learned_minus_this_points"])
        for level in RETENTION_LEVELS:
            options = [e for e in learned.values() if e["ret"] >= level]
            ours = min(options, key=lambda e: e["per"]) if options else None
            for seed in seeds:
                options = [e for e in per_seed[seed].values() if e["ret"] >= level]
                theirs = min(options, key=lambda e: e["per"]) if options else None
                if not ours or not theirs:
                    writer.writerow([level, seed, "", "", "not reached on this grid", "", "", "", ""])
                    continue
                pairs = [(float(ours["docs"][d]["res_chars"]), float(ours["docs"][d]["sens_chars"]),
                          float(theirs["docs"][d]["res_chars"]), float(theirs["docs"][d]["sens_chars"]))
                         for d in ours["docs"]]
                point, lo, hi = paired_bootstrap_diff(pairs, n_boot=n_boot, scale=100.0)
                writer.writerow([level, seed, theirs["tau"], f"{theirs['ret']:.3f}", theirs["cell"],
                                 ours["tau"], f"{ours['ret']:.3f}", ours["cell"],
                                 f"{point:+.1f} [{lo:+.1f}, {hi:+.1f}]"])
    print(f"[parity] wrote {SUMMARY.name} and {MATCHED.name}", flush=True)


def _transfer(seeds: list[int], device: str, n_boot: int) -> None:
    """Exposure, retention, and span precision on clinical notes, at each tagger's default."""
    records = [r for r in clf._load_records(CLINICAL_PATH) if str(r.get("split")) == "physionet-test"][:CLINICAL_DOCS]

    def counts(detect) -> list[dict[str, float]]:
        out = []
        for record in records:
            text = str(record.get("text", ""))
            gold = _merge_spans([(int(s["start"]), int(s["end"])) for s in record.get("phi_spans", [])
                                 if isinstance(s, dict)])
            predicted = detect(text)
            gold_chars = clf._char_coverage(gold)
            predicted_chars = clf._char_coverage(predicted)
            true_pos, false_pos, _false_neg = clf._span_counts(predicted, gold)
            out.append({"res": len(gold_chars - predicted_chars), "sens": len(gold_chars),
                        "kept": len(text) - len(gold_chars) - len(predicted_chars - gold_chars),
                        "non": len(text) - len(gold_chars), "tp": true_pos, "pred": true_pos + false_pos})
        return out

    def row(label: str, rows: list[dict[str, float]]) -> list[object]:
        def cell(num: str, den: str, scale: float, digits: int) -> str:
            point, lo, hi = bootstrap_ratio_ci([(r[num], r[den]) for r in rows], n_boot=n_boot, scale=scale)
            return f"{point:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"
        return [label, len(rows), cell("res", "sens", 100.0, 1), cell("kept", "non", 1.0, 3), cell("tp", "pred", 1.0, 2)]

    from propagation_suite import _train_learned_detector
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    weights = _train_learned_detector()
    table = [row("logistic-regression tagger", counts(lambda text: _merge_spans(clf._predict_spans(weights, text))))]
    for seed in seeds:
        folder = CHECKPOINTS / f"{MODEL_ID.replace('/', '_')}_seed{seed}"
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        model = AutoModelForTokenClassification.from_pretrained(folder / "latest").to(device).eval()
        scorer = _scorer(tokenizer, model, device)
        table.append(row(f"parity tagger seed {seed}", counts(
            lambda text, scorer=scorer: _merge_spans([(a, b) for a, b, p in scorer(text) if p >= DEFAULT_THRESHOLD]))))
    with TRANSFER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tagger_trained_on_ai4privacy", "clinical_documents", "per_percent", "retention", "span_precision"])
        writer.writerows(table)
    for line in table:
        print("  " + "  ".join(map(str, line)), flush=True)


def _write_manifest(seeds: list[int], device: str, gpu_name: str) -> None:
    import torch
    import transformers

    with MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["field", "value"])
        for field, value in [
            ("model", MODEL_ID), ("task", "binary per-word sensitive/not, maximum subword probability"),
            ("training_documents", str(clf.TRAIN_DOC_LIMIT)), ("evaluation_documents", "300"),
            ("epochs", str(EPOCHS)), ("learning_rate", str(LEARNING_RATE)), ("batch_size", str(BATCH_SIZE)),
            ("max_length", str(MAX_LENGTH)), ("stride", str(STRIDE)),
            ("seeds", ";".join(map(str, seeds))), ("device", device), ("gpu", gpu_name),
            ("torch", torch.__version__), ("transformers", transformers.__version__),
            ("python", platform.python_version()), ("platform", platform.platform()),
            ("host", platform.node()), ("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S%z")),
        ]:
            writer.writerow([field, value])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seeds", default="17,18,19")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--transfer-only", action="store_true", help="apply the finished taggers to clinical notes")
    parser.add_argument("--smoke", action="store_true",
                        help="32 training documents, 5 evaluation documents; nothing recorded is written")
    args = parser.parse_args()

    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    gpu_name = torch.cuda.get_device_name(0) if device == "cuda" else ""
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    if args.transfer_only:
        _transfer(seeds, device, args.bootstrap)
        return 0
    docs = _load_documents("ai4privacy", None)
    if args.smoke:
        tokenizer, model = _train(seeds[0], 1, device, True)
        scored = _scorer(tokenizer, model, device)(docs[0]["text"])
        counts = _measure_ai4privacy(docs[0], lambda _t, s=_merge_spans([(a, b) for a, b, p in scored if p >= 0.5]): s)
        word_count = len(clf._tokenize(docs[0]["text"]))
        print(f"[smoke] words {word_count}, scored {len(scored)}, finite {all(math.isfinite(p) for *_, p in scored)}, "
              f"counts {counts['res_chars']}/{counts['sens_chars']} kept {counts['kept_nonsens']}/{counts['nonsens_chars']}",
              flush=True)
        return 0
    for seed in seeds:
        tokenizer, model = _train(seed, args.epochs, device, False)
        _evaluate(seed, docs, tokenizer, model, device)
        del model
        if device == "cuda":
            torch.cuda.empty_cache()
    _write_tables(seeds, args.bootstrap)
    _transfer(seeds, device, args.bootstrap)
    _write_manifest(seeds, device, gpu_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
