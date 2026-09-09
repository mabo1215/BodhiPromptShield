"""Ask judges of different capacity the question the human annotators answered.

The paper reports that an LLM judge asked whether a fact is still inferable
disagrees with blind human annotation at chance. The obvious reading of that
result is that the judge was too small, so this script tests it: the same 102
items, the same prompt, the same decoding, judged by models spanning an order
of magnitude in parameter count. If the disagreement survives the largest
judge available, the finding is about the task rather than about one model.

The items are read from the annotation sheet rather than regenerated, so every
judge sees the byte-identical released text the annotators saw. Regenerating
the surfaces would put a detector stack between the finding and the evidence,
and a detector version bump would silently change what is being judged.

Each judgment is written as it completes and a restart skips finished rows, so
a run that loses its host resumes rather than repeating.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import sys
import threading
import time
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent

# Verbatim from semantic_inferability_judge.py: a capacity comparison is only
# a capacity comparison if the prompt is held fixed.
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

ROW_FIELDS = ["item_id", "method_key", "judge_inferable", "judge_raw", "released_chars", "latency_ms"]

YES = {"yes", "y", "1", "true"}
NO = {"no", "n", "0", "false"}


def _parse_human(value: str) -> int | None:
    token = (value or "").strip().lower()
    return 1 if token in YES else 0 if token in NO else None


def _parse_verdict(raw: str) -> int | None:
    """First standalone YES/NO wins; thinking models may prefix reasoning."""
    stripped = re.sub(r"<think>.*?</think>", " ", raw, flags=re.S | re.I)
    match = re.search(r"\b(YES|NO)\b", stripped, flags=re.I)
    if not match:
        return None
    return 1 if match.group(1).upper() == "YES" else 0


def _kappa(pairs: list[tuple[int, int]]) -> tuple[float, float, list[list[int]]]:
    matrix = [[0, 0], [0, 0]]
    for a, b in pairs:
        matrix[a][b] += 1
    n = len(pairs)
    if n == 0:
        return 0.0, 0.0, matrix
    observed = (matrix[0][0] + matrix[1][1]) / n
    row0, row1 = (matrix[0][0] + matrix[0][1]) / n, (matrix[1][0] + matrix[1][1]) / n
    col0, col1 = (matrix[0][0] + matrix[1][0]) / n, (matrix[0][1] + matrix[1][1]) / n
    expected = row0 * col0 + row1 * col1
    kappa = (observed - expected) / (1 - expected) if expected < 1 else 1.0
    return kappa, observed, matrix


def _interpret(kappa: float) -> str:
    if kappa < 0.0:
        return "worse than chance"
    if kappa < 0.2:
        return "slight"
    if kappa < 0.4:
        return "fair"
    if kappa < 0.6:
        return "moderate"
    if kappa < 0.8:
        return "substantial"
    return "almost perfect"


def _chat(url: str, model: str, prompt: str, timeout: int, num_predict: int, num_ctx: int) -> str:
    import requests

    response = requests.post(
        f"{url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "top_p": 1, "seed": 17, "num_predict": num_predict,
                        "num_ctx": num_ctx},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    message = response.json().get("message", {})
    content = str(message.get("content", "")).strip()
    return content or str(message.get("thinking", ""))


def _model_card(url: str, model: str) -> dict[str, str]:
    """Digest and quantization, so the row set names the weights that produced it."""
    import requests

    try:
        info = requests.post(f"{url}/api/show", json={"model": model}, timeout=60).json()
        details = info.get("details", {}) or {}
        # /api/show does not always carry the digest; /api/tags always does, and
        # a manifest without one names no weights at all.
        digest = str(info.get("digest", ""))
        if not digest:
            for tag in requests.get(f"{url}/api/tags", timeout=60).json().get("models", []):
                if tag.get("name") == model:
                    digest = str(tag.get("digest", ""))
                    break
        return {
            "judge_digest": digest[:64],
            "judge_family": str(details.get("family", "")),
            "judge_parameter_size": str(details.get("parameter_size", "")),
            "judge_quantization": str(details.get("quantization_level", "")),
        }
    except Exception:  # noqa: BLE001 - a missing card must not stop the run
        return {"judge_digest": "", "judge_family": "", "judge_parameter_size": "", "judge_quantization": ""}


def _read_done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["item_id"] for row in csv.DictReader(handle) if row.get("item_id")}


def _load_items(sheet: Path, key: Path) -> list[dict[str, str]]:
    with sheet.open(encoding="utf-8", newline="") as handle:
        sheet_rows = {r["item_id"]: r for r in csv.DictReader(handle)}
    with key.open(encoding="utf-8", newline="") as handle:
        key_rows = {r["item_id"]: r for r in csv.DictReader(handle)}
    items = []
    for item_id in sorted(sheet_rows, key=int):
        row = sheet_rows[item_id]
        items.append({
            "item_id": item_id,
            "method_key": key_rows[item_id]["method_key"],
            "released": row["released_text_shown_to_judge"],
            "fact": row["fact"],
        })
    return items


def _score(rows_path: Path, sheet: Path, round3: Path | None, key: Path,
           out: Path, model: str) -> None:
    """Report the new judge against both human records and the recorded judge."""
    with rows_path.open(encoding="utf-8", newline="") as handle:
        new_judge = {r["item_id"]: r["judge_inferable"] for r in csv.DictReader(handle)}
    with sheet.open(encoding="utf-8", newline="") as handle:
        a1 = {r["item_id"]: _parse_human(r["human_inferable_YES_or_NO"]) for r in csv.DictReader(handle)}
    with key.open(encoding="utf-8", newline="") as handle:
        recorded = {r["item_id"]: int(r["judge_inferable"]) for r in csv.DictReader(handle)}
    a3: dict[str, int | None] = {}
    if round3 and round3.exists():
        with round3.open(encoding="utf-8", newline="") as handle:
            a3 = {r["item_id"]: _parse_human(r["human_inferable_YES_or_NO"]) for r in csv.DictReader(handle)}

    scored = [i for i, v in new_judge.items() if v not in ("", None) and a1.get(i) is not None]
    unparsed = sum(1 for v in new_judge.values() if v in ("", None))
    if not scored:
        print("[capacity] nothing scoreable yet")
        return

    comparisons: list[tuple[str, list[tuple[int, int]]]] = [
        ("annotator1", [(a1[i], int(new_judge[i])) for i in scored]),
    ]
    if a3:
        pairs3 = [(a3[i], int(new_judge[i])) for i in scored if a3.get(i) is not None]
        if pairs3:
            comparisons.append(("annotator3", pairs3))
    comparisons.append(("recorded_judge_gemma2_27b",
                        [(recorded[i], int(new_judge[i])) for i in scored if i in recorded]))

    print(f"[capacity] {model}: {len(scored)} scored, {unparsed} unparsed")
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["judge_model", "reference", "n", "cohens_kappa", "interpretation",
                         "raw_agreement", "judge_yes_rate", "reference_yes_rate",
                         "cell_no_no", "cell_no_yes", "cell_yes_no", "cell_yes_yes"])
        for label, pairs in comparisons:
            kappa, observed, matrix = _kappa(pairs)
            judge_yes = sum(b for _, b in pairs) / len(pairs)
            ref_yes = sum(a for a, _ in pairs) / len(pairs)
            print(f"  vs {label}: kappa {kappa:.3f} ({_interpret(kappa)}), "
                  f"raw {observed:.3f}, n={len(pairs)}")
            writer.writerow([model, label, len(pairs), f"{kappa:.3f}", _interpret(kappa),
                             f"{observed:.3f}", f"{judge_yes:.3f}", f"{ref_yes:.3f}",
                             matrix[0][0], matrix[0][1], matrix[1][0], matrix[1][1]])
    print(f"[capacity] wrote {out.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--judge-model", required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--tag", default="vgpu3090", help="suffix of the sheet/key/round-3 records")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=600)
    # Left unset, Ollama sizes the KV cache from the model's maximum context: on a
    # 70B that reserved 160 GB across four slots and pushed half the layers onto
    # the CPU, which cost roughly fifty seconds a judgment. The prompts here run
    # about 1,500 tokens, so a small context keeps every layer on the card.
    parser.add_argument("--num-ctx", type=int, default=4096)
    parser.add_argument("--num-predict", type=int, default=160)
    parser.add_argument("--limit", type=int, default=0, help="smoke test: judge only the first N items")
    parser.add_argument("--score-only", action="store_true")
    args = parser.parse_args()

    suffix = f"_{args.tag}" if args.tag else ""
    sheet = EXPERIMENTS_DIR / f"semantic_inferability_human_sheet{suffix}.csv"
    key = EXPERIMENTS_DIR / f"semantic_inferability_human_key{suffix}.csv"
    round3 = EXPERIMENTS_DIR / f"semantic_inferability_round3_annotations{suffix}.csv"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.judge_model)
    rows_path = EXPERIMENTS_DIR / f"semantic_inferability_capacity_rows_{safe}{suffix}.csv"
    manifest = EXPERIMENTS_DIR / f"semantic_inferability_capacity_manifest_{safe}{suffix}.csv"
    agreement = EXPERIMENTS_DIR / f"semantic_inferability_capacity_agreement_{safe}{suffix}.csv"

    items = _load_items(sheet, key)
    if args.limit:
        items = items[: args.limit]
    if args.score_only:
        _score(rows_path, sheet, round3, key, agreement, args.judge_model)
        return 0

    done = _read_done(rows_path)
    pending = [it for it in items if it["item_id"] not in done]
    print(f"[capacity] {args.judge_model}: {len(pending)} of {len(items)} items to judge "
          f"({len(done)} already done)", flush=True)

    handle = rows_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
    if not done:
        writer.writeheader()
        handle.flush()
    lock = threading.Lock()
    counters = {"done": 0, "unparsed": 0}
    started = time.time()

    def judge_one(item: dict[str, str]) -> None:
        prompt = JUDGE_PROMPT.format(released=item["released"], fact=item["fact"])
        t0 = time.time()
        try:
            raw = _chat(args.ollama_url, args.judge_model, prompt, args.timeout, args.num_predict,
                        args.num_ctx)
        except Exception as exc:  # noqa: BLE001 - record and continue
            raw = f"ERROR: {exc}"
        verdict = _parse_verdict(raw)
        row = {
            "item_id": item["item_id"],
            "method_key": item["method_key"],
            "judge_inferable": "" if verdict is None else verdict,
            "judge_raw": raw.replace("\n", " ")[:400],
            "released_chars": len(item["released"]),
            "latency_ms": int((time.time() - t0) * 1000),
        }
        with lock:
            writer.writerow(row)
            handle.flush()
            os.fsync(handle.fileno())
            counters["done"] += 1
            if verdict is None:
                counters["unparsed"] += 1
            if counters["done"] % 10 == 0:
                rate = counters["done"] / max(time.time() - started, 1e-6)
                print(f"  {counters['done']}/{len(pending)} at {rate:.2f}/s", flush=True)

    threads: list[threading.Thread] = []
    queue = list(pending)
    qlock = threading.Lock()

    def worker() -> None:
        while True:
            with qlock:
                if not queue:
                    return
                item = queue.pop()
            judge_one(item)

    for _ in range(max(1, args.workers)):
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    handle.close()

    card = _model_card(args.ollama_url, args.judge_model)
    with manifest.open("w", encoding="utf-8", newline="") as mh:
        writer2 = csv.writer(mh)
        writer2.writerow(["field", "value"])
        for field, value in [
            ("judge_model", args.judge_model),
            *card.items(),
            ("prompt", "verbatim from semantic_inferability_judge.py JUDGE_PROMPT"),
            ("surfaces", f"read from {sheet.name}; not regenerated"),
            ("decoding", f"temperature 0, top_p 1, seed 17, num_predict {args.num_predict}, "
                         f"num_ctx {args.num_ctx}, think false"),
            ("items", str(len(items))),
            ("judged_this_run", str(counters["done"])),
            ("unparsed_this_run", str(counters["unparsed"])),
            ("workers", str(args.workers)),
            ("python", platform.python_version()),
            ("platform", platform.platform()),
            ("host", platform.node()),
            ("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S%z")),
        ]:
            writer2.writerow([field, value])
    print(f"[capacity] wrote {rows_path.name} and {manifest.name}")

    _score(rows_path, sheet, round3, key, agreement, args.judge_model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
