#!/usr/bin/env python3
"""Check that a run on another host can stand in for the recorded runs.

The later experiments ran on a different host and server version than the recorded runs.
Neither temperature 0 nor a seed makes decoding portable, so the comparison is measured:
recorded prompts are put to the new host, and its answers are compared with the recorded
answers.

A model digest is necessary and not sufficient. An imported model also needs its chat
template, and whether a bare ``FROM`` supplies one depends on the server version: a server
that reads the template embedded in the GGUF serves the recorded digest correctly, while an
older one falls back to the bare prompt, and the replies look like replies while being text
continuations. ``qwen3_8b_workstation.Modelfile`` is what an older server needs. A first
workstation run made that mistake, and this comparison is what caught it.

The bars below were fixed before the runs they judge. A run that misses any of them cannot
stand in for the recorded runs, and the script exits non-zero so that a queue stops there.

Reads records only; no model is called. Output, next to the records, one file per model and
host: ``host_anchor_<model>_<host>.csv``.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent

MIN_ANSWERED_PERCENT = 98.0
MIN_SAME_ANSWER_PERCENT = 80.0
MAX_RATE_GAP_POINTS = 5.0


def _rows(name: str) -> list[dict[str, str]]:
    with (EXPERIMENTS_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _line(instrument: str, total: int, both: list[tuple[str, str]], same: int) -> list[object]:
    """Compare (rerun, recorded) positives over the items answered on both."""
    answered = 100.0 * len(both) / total
    same_percent = 100.0 * same / len(both) if both else 0.0
    rerun_rate = 100.0 * sum(int(a) for a, _ in both) / len(both) if both else 0.0
    recorded_rate = 100.0 * sum(int(b) for _, b in both) / len(both) if both else 0.0
    passed = (answered >= MIN_ANSWERED_PERCENT and same_percent >= MIN_SAME_ANSWER_PERCENT
              and abs(rerun_rate - recorded_rate) <= MAX_RATE_GAP_POINTS)
    return [instrument, total, len(both), f"{same_percent:.1f}", f"{rerun_rate:.1f}", f"{recorded_rate:.1f}",
            "pass" if passed else "fail"]


def _recovery_anchor(attacker: str, tag: str) -> list[object]:
    rerun = _rows(f"privacylens_attribute_recovery_rows_{attacker}_{tag}.csv")
    recorded = {(r["condition"], r["case"], r["fact_index"]): r
                for r in _rows(f"privacylens_attribute_recovery_rows_{attacker}_corrected.csv")}
    pairs = [(r, recorded[(r["condition"], r["case"], r["fact_index"])]) for r in rerun]
    both = [(a, b) for a, b in pairs if a["chosen_option"] and b["chosen_option"]]
    same = sum(a["chosen_option"] == b["chosen_option"] for a, b in both)
    return _line(f"attribute recovery, typed placeholder (learned), {attacker}", len(pairs),
                 [(a["correct"], b["correct"]) for a, b in both], same)


def _judge_line(instrument: str, rerun: dict[str, dict[str, str]], recorded: dict[str, str]) -> list[object]:
    both = [(rerun[i]["judge_inferable"], recorded[i]) for i in rerun if i in recorded
            and rerun[i]["judge_inferable"] != "" and recorded[i] != ""]
    same = sum(a == b for a, b in both)
    return _line(instrument, len(recorded), both, same)


def _judge_anchor(model: str, tag: str) -> list[object]:
    rerun = {r["item_id"]: r for r in _rows(f"semantic_inferability_capacity_rows_{model}_vgpu3090_{tag}.csv")}
    recorded = {r["item_id"]: r["judge_inferable"]
                for r in _rows(f"semantic_inferability_capacity_rows_{model}_vgpu3090.csv")}
    return _judge_line(f"inferability judge, reported prompt, {model}", rerun, recorded)


def _reported_judge_anchor(tag: str) -> list[object]:
    """The reported judge's own records are keyed by method, document, and fact."""
    rerun = {r["item_id"]: r for r in _rows(f"semantic_inferability_capacity_rows_gemma2_27b_vgpu3090_{tag}.csv")}
    by_fact = {(r["method_key"], r["doc_id"], r["fact_index"]): r["judge_inferable"]
               for r in _rows("semantic_inferability_rows_vgpu3090.csv")}
    recorded = {}
    for row in _rows("semantic_inferability_human_key_vgpu3090.csv"):
        if row["item_id"] in rerun:
            recorded[row["item_id"]] = by_fact[(row["method_key"], row["doc_id"], row["fact_index"])]
    return _judge_line("inferability judge, reported prompt, gemma2_27b", rerun, recorded)


def _live_anchor(tag: str, model: str, detector: str) -> list[list[object]]:
    """Live-stack trajectories rerun with a recorded detector, compared per case and condition."""
    recorded = {}
    for path in sorted(EXPERIMENTS_DIR.glob(f"live_stack_placement_rows_{model}_{detector}_v1_shard*of4.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                recorded[(row["case"], row["condition"])] = row
    rerun = _rows(f"live_stack_placement_rows_{model}_{detector}_{tag}.csv")
    pairs = [(r, recorded[(r["case"], r["condition"])]) for r in rerun]
    table = []
    for name, value in (("task utility", lambda r: str(int(float(r["utility"] or 0)))),
                        ("any non-authorized value exposed", lambda r: str(int(float(r["nonauth_v"] or 0) > 0)))):
        both = [(value(a), value(b)) for a, b in pairs]
        table.append(_line(f"live stack, {name}, {detector}", len(pairs), both, sum(a == b for a, b in both)))
    return table


def _injection_anchor(tag: str, recorded_tag: str) -> list[list[object]]:
    """AgentDojo injection pairs rerun on this host, compared per (suite, task, injection task)."""
    table = []
    pairs = []
    for suite in ("banking", "slack"):
        rerun = _rows(f"agentdojo_restoration_rows_{suite}_qwen3_32b-q4km-hf_{tag}.csv")
        recorded = {(r["task"], r["injection_task"]): r
                    for r in _rows(f"agentdojo_restoration_rows_{suite}_qwen3_32b-q4km-hf_{recorded_tag}.csv")}
        pairs += [(r, recorded[(r["task"], r["injection_task"])]) for r in rerun]
    for name, field in (("attack success", "security"), ("task utility", "utility")):
        both = [(a[field], b[field]) for a, b in pairs]
        table.append(_line(f"injection, {name}, regex_only", len(pairs), both, sum(a == b for a, b in both)))
    return table


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--attacker", default="qwen3_8b-q4km-hf", help="model as written in the record file names")
    parser.add_argument("--attack-tag", default="anchor_4c")
    parser.add_argument("--judge-tag", default="4c")
    parser.add_argument("--reported-judge", action="store_true", help="compare the 27B reported judge only")
    parser.add_argument("--live-tag", help="compare live-stack rows written under this output tag")
    parser.add_argument("--live-model", default="qwen3_32b-q4km-hf")
    parser.add_argument("--live-detector", default="learned_lr")
    parser.add_argument("--injection-tag", help="compare AgentDojo injection rows written under this output tag")
    parser.add_argument("--recorded-injection-tag", default="inj_all_fixed")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.injection_tag:
        table = _injection_anchor(args.injection_tag, args.recorded_injection_tag)
    elif args.live_tag:
        table = _live_anchor(args.live_tag, args.live_model, args.live_detector)
    elif args.reported_judge:
        table = [_reported_judge_anchor(args.judge_tag)]
    else:
        table = [_recovery_anchor(args.attacker, args.attack_tag), _judge_anchor(args.attacker, args.judge_tag)]
    with (EXPERIMENTS_DIR / args.output).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["instrument", "items", "items_answered_on_both", "same_answer_percent",
                         "rerun_positive_percent", "recorded_positive_percent", "verdict"])
        writer.writerows(table)
    for row in table:
        print("  " + "  ".join(map(str, row)), flush=True)
    return 0 if all(row[-1] == "pass" for row in table) else 1


if __name__ == "__main__":
    raise SystemExit(main())
