"""
Audit the effect of the symbolic-restoration prefix bug on the recorded downstream runs.

Until this audit, restore_symbolic replaced tokens with str.replace in insertion
order. BPSMAP-<ns>-1 is a prefix of BPSMAP-<ns>-10 to -19, so every token from
the tenth on was restored as the first value plus a digit, and the count of
tokens in an action treated the first token as present wherever a later one
was. This script measures what that changed, using only the recorded runs'
generation cache: it never calls a model.

For each of the subset's cases it rebuilds the released surfaces of the
symbolic conditions exactly as the suite does, looks up the agent's recorded
reply, and compares the old and corrected restoration:

  * late arm: does the restored final action, which the judge scores, change?
  * early arm (as run): does the restored trajectory, which the agent reads,
    change? If so the recorded agent reply answers a different prompt.
  * true early arm: is the agent prompt byte-identical to the no-protection
    prompt, and is that reply in the cache? If so the arm costs no generation.

It also recomputes the recorded row fields from the cached replies with the old
functions, which checks that the detector reproduces the recorded mapping.

Usage (on the host that holds the cache; the detector uses the GPU if present):
  python src/experiments/restoration_bug_audit.py --agent-model qwen3:32b-q4km-hf \
      --agent-num-ctx 12288 --judge-num-ctx 12288
  python src/experiments/restoration_bug_audit.py --agent-model llama3.3:70b-q4km-hf \
      --agent-num-ctx 7168 --judge-num-ctx 10240 --shards 8
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import random
import re
from pathlib import Path

import privacylens_downstream_suite as suite
from mediation_baselines import build_detectors, render_symbolic, restore_symbolic, symbolic_tokens_in
from ollama_client import CachedOllamaChat

EXPERIMENTS_DIR = Path(__file__).resolve().parent
DETECTOR = "gliner_pii"


def _restore_old(text: str, mapping: dict[str, str]) -> str:
    """The restoration the recorded runs used, kept verbatim for comparison."""
    for token, value in mapping.items():
        text = text.replace(token, value)
    return text


def _tokens_old(text: str, mapping: dict[str, str]) -> int:
    return sum(1 for tok in mapping if tok in text)


def _cached(client: CachedOllamaChat, prompt: str, num_predict: int) -> str | None:
    options = {"temperature": 0.0, "top_p": 1, "num_predict": num_predict, "num_ctx": client.num_ctx, "seed": 17}
    return client.cache.get(client._key([{"role": "user", "content": prompt}], options))


def _recorded_rows(agent: str, shards: int) -> dict[tuple[str, str], dict[str, str]]:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", agent)
    rows: dict[tuple[str, str], dict[str, str]] = {}
    for path in sorted(glob.glob(str(EXPERIMENTS_DIR / f"privacylens_downstream_rows_{safe}_shard*of{shards}.csv"))):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                rows[(r["condition"], r["case"])] = r
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--agent-model", required=True)
    parser.add_argument("--judge-model", default=suite.DEFAULT_JUDGE)
    parser.add_argument("--agent-num-ctx", type=int, required=True)
    parser.add_argument("--judge-num-ctx", type=int, required=True)
    parser.add_argument("--max-cases", type=int, default=200)
    parser.add_argument("--sample-seed", type=int, default=17)
    parser.add_argument("--shards", type=int, default=4, help="Shard count of the recorded run, to find its rows")
    args = parser.parse_args()

    cases = json.load(open(suite.PL_DATA, encoding="utf-8"))
    cases = random.Random(args.sample_seed).sample(cases, min(args.max_cases, len(cases)))
    prefixes = {json.loads(l)["name"]: json.loads(l) for l in open(suite.PL_PROMPTS, encoding="utf-8") if l.strip()}
    detector = {d.key: d for d in build_detectors([DETECTOR], learned_weights=None, spacy_model="en_core_web_lg")}[DETECTOR]
    agent = CachedOllamaChat(args.agent_model, num_ctx=args.agent_num_ctx)
    judge = CachedOllamaChat(args.judge_model, num_ctx=args.judge_num_ctx)
    recorded = _recorded_rows(args.agent_model, args.shards)
    late_spec, early_spec = f"symbolic_late:{DETECTOR}", f"symbolic_early:{DETECTOR}"

    out = []
    for case in cases:
        tr = case["trajectory"]
        name = tr.get("user_name", "")
        instr, traj = tr.get("user_instruction", ""), tr.get("executable_trajectory", "")
        final_tool = tr.get("final_action", "")
        prefix = prefixes[case["name"]]["prefix"]
        namespace = hashlib.sha256(case["name"].encode("utf-8")).hexdigest()[:6]
        mapping: dict[str, str] = {}
        instr_r = render_symbolic(instr, detector(instr), namespace, mapping)
        traj_r = render_symbolic(traj, detector(traj), namespace, mapping)

        # Late arm: the agent reads tokens; only the restored action changes.
        late_prompt = suite._agent_prompt(prefix, instr_r, traj_r, final_tool)
        late_raw = _cached(agent, late_prompt, 700)
        late_action = ""
        if late_raw is not None:
            output = suite.post_process(late_raw)
            late_action = output[output.find("Action:") + len("Action:"):].strip() if "Action:" in output else ""
        late_old, late_new = _restore_old(late_action, mapping), restore_symbolic(late_action, mapping)
        items = list(tr.get("sensitive_info_items", []))
        late_judge_misses = 0
        if late_raw is not None and late_old != late_new and "Action:" in suite.post_process(late_raw):
            for secret in items:
                if _cached(judge, suite.prepare_prompt_to_identify_leakage(name, secret, late_new), 400) is None:
                    late_judge_misses += 1
            if _cached(judge, suite.prepare_prompt_to_evaluate_helpfulness(name, instr, traj, late_new), 400) is None:
                late_judge_misses += 1

        # Early arm as run: the agent reads the restored trajectory.
        early_old_prompt = suite._agent_prompt(prefix, instr_r, _restore_old(traj_r, mapping), final_tool)
        early_new_prompt = suite._agent_prompt(prefix, instr_r, restore_symbolic(traj_r, mapping), final_tool)
        early_raw = _cached(agent, early_old_prompt, 700)
        early_action = ""
        if early_raw is not None:
            output = suite.post_process(early_raw)
            early_action = output[output.find("Action:") + len("Action:"):].strip() if "Action:" in output else ""

        # True early arm: every value is back before planning.
        full_instr, full_traj = restore_symbolic(instr_r, mapping), restore_symbolic(traj_r, mapping)
        full_prompt = suite._agent_prompt(prefix, full_instr, full_traj, final_tool)
        noprot_prompt = suite._agent_prompt(prefix, instr, traj, final_tool)

        rec_late = recorded.get((late_spec, case["name"]), {})
        rec_early = recorded.get((early_spec, case["name"]), {})
        out.append({
            "case": case["name"],
            "protected_values": len(mapping),
            "recorded_protected_values_late": rec_late.get("protected_values", ""),
            "late_agent_cached": int(late_raw is not None),
            "late_tokens_in_action_old": _tokens_old(late_action, mapping),
            "late_tokens_in_action_new": len(symbolic_tokens_in(late_action, mapping)),
            "recorded_late_tokens_in_output": rec_late.get("tokens_in_output", ""),
            "late_final_action_changes": int(late_old != late_new),
            "late_judge_calls_to_generate": late_judge_misses,
            "early_agent_cached_old_prompt": int(early_raw is not None),
            "early_trajectory_changes": int(early_old_prompt != early_new_prompt),
            "early_tokens_in_action_old": _tokens_old(early_action, mapping),
            "early_tokens_in_action_new": len(symbolic_tokens_in(early_action, mapping)),
            "recorded_early_tokens_in_output": rec_early.get("tokens_in_output", ""),
            "full_early_prompt_equals_no_protection": int(full_prompt == noprot_prompt),
            "no_protection_agent_cached": int(_cached(agent, noprot_prompt, 700) is not None),
        })

    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.agent_model)
    path = EXPERIMENTS_DIR / f"restoration_bug_audit_{safe}.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)

    def total(key: str) -> int:
        return sum(int(r[key]) for r in out)

    n = len(out)
    match_pv = sum(1 for r in out if str(r["protected_values"]) == r["recorded_protected_values_late"])
    match_late_tok = sum(1 for r in out if str(r["late_tokens_in_action_old"]) == r["recorded_late_tokens_in_output"])
    match_early_tok = sum(1 for r in out if str(r["early_tokens_in_action_old"]) == r["recorded_early_tokens_in_output"])
    print(f"cases {n}; mappings with >= 10 values: {sum(1 for r in out if r['protected_values'] >= 10)}")
    print(f"replay fidelity: protected_values match {match_pv}/{n}; late token count match {match_late_tok}/{n}; "
          f"early token count match {match_early_tok}/{n}")
    print(f"late: agent cached {total('late_agent_cached')}/{n}; final action changes in {total('late_final_action_changes')}; "
          f"judge calls to generate {total('late_judge_calls_to_generate')}; tokens per action old "
          f"{total('late_tokens_in_action_old') / n:.3f} new {total('late_tokens_in_action_new') / n:.3f}")
    print(f"early as run: agent cached {total('early_agent_cached_old_prompt')}/{n}; trajectory changes in "
          f"{total('early_trajectory_changes')}; tokens per action old {total('early_tokens_in_action_old') / n:.3f} "
          f"new {total('early_tokens_in_action_new') / n:.3f}")
    print(f"true early: prompt equals no-protection in {total('full_early_prompt_equals_no_protection')}/{n}; "
          f"no-protection reply cached {total('no_protection_agent_cached')}/{n}")
    print("Wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
