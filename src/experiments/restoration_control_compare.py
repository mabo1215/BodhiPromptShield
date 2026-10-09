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
    helpfulness, identifier counts), replayed record against regenerated record;
  * the restoration-timing contrast: the late arm paired against each of the
    two early records, so the claim can be read off either;
  * judge calls per agent: the judge cache is shared by both agents, so each
    regenerated case's judge prompts are rebuilt from that agent's regenerated
    reply (the true early arm's prompt is the unprotected prompt byte for byte,
    so the unprotected condition rebuilds the same judge prompts) with the
    regenerated run's own decoding options, and the calls are counted per agent.

Usage:
  python src/experiments/restoration_control_compare.py --regen-cache <dir> [--recorded-cache <dir>]

--recorded-cache defaults to the local generation cache; point it at a copy of
the recording host's cache when the local one is older than the replay.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from pathlib import Path

from aggregate_paper_results import _ci, _write, read_downstream_rows
from downstream_paired_tests import paired_bootstrap_diff
from ollama_client import CachedOllamaChat

EXPERIMENTS_DIR = Path(__file__).resolve().parent
RECORDED_CACHE = EXPERIMENTS_DIR / "ollama_cache"
AGENTS = (("qwen3:32b-q4km-hf", "qwen3_32b-q4km-hf"), ("llama3.3:70b-q4km-hf", "llama3.3_70b-q4km-hf"))
JUDGE = "mistral:7b-instruct-v0.2-q4km-hf"
OUTCOMES = ("has_action", "leak_any", "leak_count", "helpfulness", "ids_in_output", "ids_in_final_action")
CONDITION = "symbolic_fullearly:gliner_pii"
LATE = "symbolic_late:gliner_pii"


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


class _KeyRecorder(CachedOllamaChat):
    """A cache-only client that records the cache key of every call it is asked to make."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, cache_only=True, **kwargs)
        self.keys: set[str] = set()

    def chat(self, messages, *, temperature=0.0, num_predict=512, num_ctx=None, seed=17):
        options = {"temperature": temperature, "top_p": 1, "num_predict": num_predict,
                   "num_ctx": num_ctx or self.num_ctx, "seed": seed}
        self.keys.add(self._key(messages, options))
        return super().chat(messages, temperature=temperature, num_predict=num_predict, num_ctx=num_ctx, seed=seed)


def _regen_contexts(safe: str) -> tuple[int, int]:
    """Agent and judge num_ctx of the regenerated run, from its first shard's manifest."""
    path = sorted(glob.glob(str(EXPERIMENTS_DIR / f"privacylens_downstream_runtime_manifest_{safe}_fullearly_regen_shard0of*.csv")))[0]
    with open(path, encoding="utf-8", newline="") as handle:
        decoding = next(r["value"] for r in csv.DictReader(handle) if r["field"] == "decoding")
    agent_ctx, judge_ctx = (int(x) for x in re.findall(r"num_ctx (\d+)", decoding))
    return agent_ctx, judge_ctx


def _judge_keys_for_agent(regen_cache: Path, model: str, safe: str, cases: list[str]) -> tuple[set[str], int]:
    """Judge-call cache keys that the regenerated replies of one agent produce, and the cases rebuilt."""
    from privacylens_downstream_suite import PL_DATA, PL_PROMPTS, Condition, evaluate_case

    agent_ctx, judge_ctx = _regen_contexts(safe)
    data = {c["name"]: c for c in json.load(open(PL_DATA, encoding="utf-8"))}
    prefixes = {json.loads(l)["name"]: json.loads(l) for l in open(PL_PROMPTS, encoding="utf-8") if l.strip()}
    agent = CachedOllamaChat(model, cache_dir=regen_cache, num_ctx=agent_ctx, cache_only=True)
    judge = _KeyRecorder(JUDGE, cache_dir=regen_cache, num_ctx=judge_ctx)
    unprotected = Condition("no_protection", {}, "http://127.0.0.1:11434", "en_core_web_lg")
    rebuilt = 0
    for name in cases:
        try:
            evaluate_case(data[name], prefixes[name], unprotected, agent, judge)
            rebuilt += 1
        except Exception as exc:  # noqa: BLE001 - a case missing from the cache is counted, not fatal
            print(f"  {model} {name}: not rebuilt ({type(exc).__name__})")
    return judge.keys, rebuilt


def _timing(late: dict[str, dict[str, str]], early: dict[str, dict[str, str]]) -> dict[str, str]:
    """Late minus early, paired on case, as restoration_timing_paired_tests reports it."""
    cases = sorted(set(late) & set(early))

    def pairs(field: str, denominator: str | None) -> list[tuple[float, float, float, float]]:
        return [(float(late[k][field]), float(late[k][denominator]) if denominator else 1.0,
                 float(early[k][field]), float(early[k][denominator]) if denominator else 1.0) for k in cases]

    def fmt(diff: tuple[float, float, float], digits: int) -> str:
        return f"{diff[0]:+.{digits}f} [{diff[1]:+.{digits}f}, {diff[2]:+.{digits}f}]"

    return {
        "pre_restoration_id_diff_points": fmt(paired_bootstrap_diff(pairs("ids_in_output", "ids_total"), scale=100.0), 1),
        "leak_rate_diff_points": fmt(paired_bootstrap_diff(pairs("leak_any", None), scale=100.0), 1),
        "helpfulness_diff": fmt(paired_bootstrap_diff(pairs("helpfulness", None)), 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--regen-cache", type=Path, required=True)
    parser.add_argument("--recorded-cache", type=Path, default=RECORDED_CACHE)
    args = parser.parse_args()

    out = []
    judge_recorded, judge_regen = _cache(args.recorded_cache, JUDGE), _cache(args.regen_cache, JUDGE)
    for model, safe in AGENTS:
        recorded, regen = _cache(args.recorded_cache, model), _cache(args.regen_cache, model)
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
        late = {r["case"]: r for r in read_downstream_rows(safe) if r["condition"] == LATE}
        for label, source in (("replayed", replay), ("regenerated", regenerated)):
            for key, value in _timing(late, source).items():
                row[f"late_vs_{label}_early_{key}"] = value
        keys, rebuilt = _judge_keys_for_agent(args.regen_cache, model, safe, sorted(regenerated))
        regen_keys = [k for k in keys if k in judge_regen]
        row["cases_with_judge_prompts_rebuilt"] = str(rebuilt)
        row["judge_calls_regenerated_this_agent"] = str(len(regen_keys))
        row["judge_calls_with_recorded_key_this_agent"] = str(sum(1 for k in regen_keys if k in judge_recorded))
        row["judge_replies_byte_identical_this_agent"] = str(
            sum(1 for k in regen_keys if judge_recorded.get(k) == judge_regen[k]))
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
