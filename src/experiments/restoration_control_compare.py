"""
Compare the replayed true early arm with the same arm regenerated from an empty cache.

The true early arm (symbolic_fullearly) restores every value before planning,
so its agent prompt is the no-protection prompt byte for byte and the arm was
first reported from the recorded generation cache without calling a model.
The control regenerates every call of that arm on the same host, model digests
and decoding settings, into a separate cache. This script measures how far the
two agree, at two levels:

  * calls: every regenerated call is looked up by its cache key, which is the
    hash of (model, messages, options), in the recorded cache; the share whose
    reply is byte-identical is the run-to-run reproducibility of the stack;
  * cases: the per-case outcomes the paper reports (action, leak, leak count,
    helpfulness, identifier counts), replayed record against regenerated record.

Usage:
  python src/experiments/restoration_control_compare.py --regen-cache <dir>
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from pathlib import Path

from aggregate_paper_results import _ci, _write

EXPERIMENTS_DIR = Path(__file__).resolve().parent
RECORDED_CACHE = EXPERIMENTS_DIR / "ollama_cache"
AGENTS = (("qwen3:32b-q4km-hf", "qwen3_32b-q4km-hf"), ("llama3.3:70b-q4km-hf", "llama3.3_70b-q4km-hf"))
JUDGE = "mistral:7b-instruct-v0.2-q4km-hf"
OUTCOMES = ("has_action", "leak_any", "leak_count", "helpfulness", "ids_in_output", "ids_in_final_action")
CONDITION = "symbolic_fullearly:gliner_pii"


def _cache(directory: Path, model: str) -> dict[str, str]:
    path = directory / f"chat__{re.sub(r'[^A-Za-z0-9_.-]+', '_', model)}.jsonl"
    out: dict[str, str] = {}
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    out[row["key"]] = row["response"]
    return out


def _rows(paths: list[str]) -> dict[str, dict[str, str]]:
    csv.field_size_limit(1 << 30)
    rows: dict[str, dict[str, str]] = {}
    for path in paths:
        with open(path, encoding="utf-8", newline="") as handle:
            for r in csv.DictReader(handle):
                if r["condition"] == CONDITION:
                    rows[r["case"]] = r
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--regen-cache", type=Path, required=True)
    args = parser.parse_args()

    out = []
    judge_recorded, judge_regen = _cache(RECORDED_CACHE, JUDGE), _cache(args.regen_cache, JUDGE)
    for model, safe in AGENTS:
        recorded, regen = _cache(RECORDED_CACHE, model), _cache(args.regen_cache, model)
        replay = _rows([str(EXPERIMENTS_DIR / f"privacylens_downstream_rows_{safe}_fullearly.csv")])
        regenerated = _rows(sorted(glob.glob(str(EXPERIMENTS_DIR / f"privacylens_downstream_rows_{safe}_fullearly_regen_shard*of*.csv"))))
        if not regen or not regenerated:
            print(f"{model}: no regenerated record yet")
            continue
        shared = sorted(set(replay) & set(regenerated))
        agent_same = sum(1 for k in regen if recorded.get(k) == regen[k])
        agent_found = sum(1 for k in regen if k in recorded)
        row = {
            "agent_model": model,
            "cases_compared": str(len(shared)),
            "agent_calls_regenerated": str(len(regen)),
            "agent_calls_with_recorded_key": str(agent_found),
            "agent_replies_byte_identical": str(agent_same),
        }
        for field in OUTCOMES:
            row[f"cases_equal_{field}"] = str(sum(1 for k in shared if replay[k][field] == regenerated[k][field]))
        for label, source in (("replayed", replay), ("regenerated", regenerated)):
            sub = [source[k] for k in shared]
            row[f"{label}_leak_rate_percent"] = _ci(sub, "leak_any", None, 100.0, 1)
            row[f"{label}_helpfulness_mean"] = _ci(sub, "helpfulness", None, 1.0, 2)
            row[f"{label}_exact_id_exposure_percent"] = _ci(sub, "ids_in_final_action", "ids_total", 100.0, 1)
        out.append(row)

    judge_found = sum(1 for k in judge_regen if k in judge_recorded)
    judge_same = sum(1 for k in judge_regen if judge_recorded.get(k) == judge_regen[k])
    for row in out:
        row["judge_calls_regenerated_both_agents"] = str(len(judge_regen))
        row["judge_calls_with_recorded_key"] = str(judge_found)
        row["judge_replies_byte_identical"] = str(judge_same)
    if not out:
        return 1
    path = EXPERIMENTS_DIR / "restoration_control_compare.csv"
    _write(path, out)
    for row in out:
        print(json.dumps(row, indent=1))
    print("Wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
