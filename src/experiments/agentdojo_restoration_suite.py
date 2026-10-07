#!/usr/bin/env python3
"""Restoration timing on real tool-executing agent tasks (AgentDojo).

AgentDojo (Debenedetti et al., 2024) runs an LLM agent against sandboxed tool
environments with objective, environment-state utility checks.  Several
banking tasks require the agent to pass an exact identifier from the user's
prompt (an IBAN, an address) to a tool.  This suite mediates the user prompt
before the agent sees it and measures, per task and mode:

* ``none``        the raw prompt (no mediation);
* ``late``        detected spans become opaque tokens; the tool executor
                  restores the real values in the tool arguments at the tool
                  boundary (authorized late restoration);
* ``no_restore``  tokens are never restored (utility cost of protection
                  without a restoration path).

With ``--with-injections`` the same pipelines face AgentDojo's
``important_instructions`` prompt-injection attack on the selected injection
tasks (banking tasks 1 and 8 try to exfiltrate IBANs to an attacker account).
This is the threat model's restoration-trigger adversary: an injected
instruction that routes a *token* into an exfiltration tool call, which an
unscoped late-restoration executor would dutifully restore.  ``--restore-scope
user-directed`` restores a token only in tool calls whose recipient-like
arguments name an entity the user's own prompt refers to, and the reported
``security`` column is AgentDojo's attack-success judgement.

Reported per task: AgentDojo utility, whether raw protected values were ever
visible to the model before the tool boundary (boundary leakage), whether the
tool received the restored value when a token was emitted (restoration
success), unrestored tokens, and the number of tool calls.  With
``--mediate-tool-outputs`` the same token map is also applied to tool outputs,
so values echoed back by tools (e.g. transaction lists) do not re-enter the
model context in raw form.

The agent model is served by Ollama's OpenAI-compatible endpoint with native
tool calling; results are appended per task with fsync and skipped on restart.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import sys
from collections.abc import Sequence
from pathlib import Path

import openai
from agentdojo.agent_pipeline import AgentPipeline, InitQuery, OpenAILLM, SystemMessage, ToolsExecutionLoop, ToolsExecutor
from agentdojo.agent_pipeline.agent_pipeline import load_system_message
from agentdojo.models import MODEL_NAMES
from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.types import ChatMessage, text_content_block_from_string

from ai4privacy_matched_baseline_suite import _merge_spans
import ai4privacy_lightweight_classifier_baseline as clf
from mediation_baselines import (Detector, bootstrap_ratio_ci, build_detectors, render_symbolic, restore_symbolic,
                                 symbolic_tokens_in)


EXPERIMENTS_DIR = Path(__file__).resolve().parent
AI4_PATH = EXPERIMENTS_DIR / "ai4privacy_pii300k_english_export.jsonl"
BENCHMARK_VERSION = "v1"
ROW_FIELDS = ["suite", "task", "injection_task", "mode", "restore_scope", "detector", "agent_model", "utility", "security",
              "protected_values", "raw_visible_before_tool", "tokens_emitted_in_tool_args", "restored_in_tool_args",
              "unrestored_tokens", "refused_unscoped_restorations", "raw_in_tool_outputs", "tool_calls", "error"]
RECIPIENT_KEYS = {"recipient", "to", "recipients", "email", "channel", "user", "cc", "bcc"}


def _text_of(message: ChatMessage) -> str:
    content = message.get("content")
    if not content:
        return ""
    return "\n".join(str(block.get("content", "")) for block in content if isinstance(block, dict))


class PromptMediator(BasePipelineElement):
    """Replaces detected spans in the user message with opaque per-task tokens."""

    def __init__(self, detector: Detector, state: dict) -> None:
        self.detector = detector
        self.state = state

    def query(self, query: str, runtime: FunctionsRuntime, env: Env = EmptyEnv(), messages: Sequence[ChatMessage] = [],
              extra_args: dict = {}) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        mapping: dict[str, str] = self.state.setdefault("mapping", {})
        namespace = self.state["namespace"]
        released = render_symbolic(query, self.detector(query), namespace, mapping)
        messages = list(messages)
        if messages and messages[-1]["role"] == "user":
            messages[-1] = {**messages[-1], "content": [text_content_block_from_string(released)]}
        return released, runtime, env, messages, extra_args


class RestoringToolsExecutor(ToolsExecutor):
    """Restores tokens in tool arguments at the tool boundary; optionally re-tokenizes tool outputs."""

    def __init__(self, state: dict, restore: bool, mediate_outputs: bool, scope: str = "all") -> None:
        super().__init__()
        self.state = state
        self.restore = restore
        self.mediate_outputs = mediate_outputs
        self.scope = scope

    def _authorized(self, call, mapping: dict[str, str]) -> bool:
        """Under user-directed scope, restore only when every recipient-like argument names an entity from the user's prompt."""
        if self.scope != "user-directed":
            return True
        prompt = self.state.get("user_prompt", "")
        for key, value in call.args.items():
            if key.lower() in RECIPIENT_KEYS and isinstance(value, str):
                target = restore_symbolic(value, mapping)
                if target not in prompt and not any(v in target for v in mapping.values() if v in prompt):
                    return False
        return True

    def query(self, query: str, runtime: FunctionsRuntime, env: Env = EmptyEnv(), messages: Sequence[ChatMessage] = [],
              extra_args: dict = {}) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        mapping: dict[str, str] = self.state.get("mapping", {})
        if messages and messages[-1]["role"] == "assistant" and messages[-1].get("tool_calls"):
            for call in messages[-1]["tool_calls"]:
                self.state["tool_calls"] = self.state.get("tool_calls", 0) + 1
                for key, value in list(call.args.items()):
                    if not isinstance(value, str):
                        continue
                    emitted = symbolic_tokens_in(value, mapping)
                    if emitted:
                        self.state["tokens_emitted"] = self.state.get("tokens_emitted", 0) + len(emitted)
                        if self.restore and self._authorized(call, mapping):
                            call.args[key] = restore_symbolic(value, mapping)
                            self.state["restored"] = self.state.get("restored", 0) + len(emitted)
                        elif self.restore:
                            self.state["refused"] = self.state.get("refused", 0) + len(emitted)
                        else:
                            self.state["unrestored"] = self.state.get("unrestored", 0) + len(emitted)
        n_before = len(messages)
        query, runtime, env, messages, extra_args = super().query(query, runtime, env, messages, extra_args)
        messages = list(messages)
        for i in range(n_before, len(messages)):
            text = _text_of(messages[i])
            raw_hits = sum(1 for v in mapping.values() if v in text)
            self.state["raw_in_tool_outputs"] = self.state.get("raw_in_tool_outputs", 0) + raw_hits
            if self.mediate_outputs and raw_hits:
                for tok, val in mapping.items():
                    text = text.replace(val, tok)
                messages[i] = {**messages[i], "content": [text_content_block_from_string(text)]}
        return query, runtime, env, messages, extra_args


class Recorder(BasePipelineElement):
    def __init__(self, state: dict) -> None:
        self.state = state

    def query(self, query, runtime, env=EmptyEnv(), messages=[], extra_args={}):
        self.state["messages"] = list(messages)
        return query, runtime, env, messages, extra_args


def build_pipeline(llm: OpenAILLM, detector: Detector | None, mode: str, state: dict, mediate_outputs: bool,
                   scope: str = "all") -> AgentPipeline:
    elements: list[BasePipelineElement] = [SystemMessage(load_system_message(None)), InitQuery()]
    if mode != "none" and detector is not None:
        elements.append(PromptMediator(detector, state))
    executor = (RestoringToolsExecutor(state, restore=(mode == "late"), mediate_outputs=mediate_outputs, scope=scope)
                if mode != "none" else ToolsExecutor())
    elements += [llm, ToolsExecutionLoop([executor, llm]), Recorder(state)]
    pipeline = AgentPipeline(elements)
    pipeline.name = f"{llm.model}-{mode}-{scope}"
    return pipeline


def _attack_addressable_name(pipeline_name: str, with_injections: bool) -> str:
    """AgentDojo's important_instructions attack needs a recognized model-name substring
    in pipeline.name to phrase its injected message; append a generic fallback for
    open-weight local tags it does not recognize (does not change which model runs)."""
    if not with_injections or any(key in pipeline_name for key in MODEL_NAMES):
        return pipeline_name
    return f"{pipeline_name} meta-llama/Llama-3-70b-chat-hf"


def _train_learned_detector() -> dict:
    records = clf._load_records(AI4_PATH)
    train = [r for r in records if str(r.get("split")) == "ai4privacy-train"][: clf.TRAIN_DOC_LIMIT]
    weights, _ = clf._train_logreg(clf._build_examples(train))
    return weights


def _with_tag(path: Path, tag: str | None) -> Path:
    return path if not tag else path.with_name(f"{path.stem}_{tag}{path.suffix}")


def run(args: argparse.Namespace) -> None:
    client = openai.OpenAI(base_url=f"{args.base_url}/v1", api_key="ollama")
    llm = OpenAILLM(client, args.agent_model, temperature=0.0)
    learned = _train_learned_detector() if args.detector == "learned_lr" else None
    detector = build_detectors([args.detector], learned_weights=learned, spacy_model=args.spacy_model)[0]
    suite = get_suite(BENCHMARK_VERSION, args.suite)
    task_ids = [t.strip() for t in args.tasks.split(",")] if args.tasks else list(suite.user_tasks.keys())
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    injection_ids: list[str | None] = [None]
    attack = None
    if args.with_injections:
        from agentdojo.attacks.attack_registry import load_attack

        injection_ids = [i.strip() for i in args.injection_tasks.split(",")] if args.injection_tasks else list(suite.injection_tasks.keys())

    safe_agent = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.agent_model)
    rows_path = _with_tag(EXPERIMENTS_DIR / f"agentdojo_restoration_rows_{args.suite}_{safe_agent}.csv", args.output_tag)
    summary_path = _with_tag(EXPERIMENTS_DIR / f"agentdojo_restoration_summary_{args.suite}_{safe_agent}.csv", args.output_tag)
    manifest_path = _with_tag(EXPERIMENTS_DIR / f"agentdojo_restoration_runtime_manifest_{args.suite}_{safe_agent}.csv", args.output_tag)
    done: set[tuple[str, str, str, str]] = set()
    if rows_path.exists():
        with rows_path.open("r", encoding="utf-8", newline="") as f:
            done = {(r["task"], r.get("injection_task", ""), r["mode"], r.get("restore_scope", "all")) for r in csv.DictReader(f)}
    new_file = not rows_path.exists()
    handle = rows_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
    if new_file:
        writer.writeheader(); handle.flush()

    for mode in modes:
        for task_id in task_ids:
            for inj_id in injection_ids:
                if (task_id, inj_id or "", mode, args.restore_scope) in done:
                    continue
                task = suite.get_user_task_by_id(task_id)
                state: dict = {"namespace": hashlib.sha256(f"{args.suite}/{task_id}".encode()).hexdigest()[:6], "user_prompt": task.PROMPT}
                pipeline = build_pipeline(llm, detector, mode, state, args.mediate_tool_outputs, args.restore_scope)
                pipeline.name = _attack_addressable_name(pipeline.name, args.with_injections)
                error = ""
                try:
                    if inj_id is None:
                        utility, security = suite.run_task_with_pipeline(pipeline, task, injection_task=None, injections={})
                    else:
                        if attack is None or getattr(attack, "_pipeline_name", None) != pipeline.name:
                            attack = load_attack("important_instructions", suite, pipeline)
                            attack._pipeline_name = pipeline.name
                        inj_task = suite.get_injection_task_by_id(inj_id)
                        injections = attack.attack(task, inj_task)
                        utility, security = suite.run_task_with_pipeline(pipeline, task, injection_task=inj_task, injections=injections)
                except Exception as exc:  # noqa: BLE001 - one failing task must not abort the sweep
                    utility, security, error = False, False, f"{type(exc).__name__}: {str(exc)[:160]}"
                mapping = state.get("mapping", {})
                if mode == "none":  # count what would have been protected; everything is visible raw
                    mapping = {f"raw-{i}": task.PROMPT[s:e] for i, (s, e) in enumerate(detector(task.PROMPT))}
                visible = "\n".join(_text_of(m) for m in state.get("messages", []) if m["role"] in ("user", "assistant", "tool"))
                raw_visible = sum(1 for v in mapping.values() if v in visible) if mode != "none" else len(mapping)
                row = {"suite": args.suite, "task": task_id, "injection_task": inj_id or "", "mode": mode, "restore_scope": args.restore_scope,
                       "detector": args.detector, "agent_model": args.agent_model, "utility": int(bool(utility)), "security": int(bool(security)),
                       "protected_values": len(mapping), "raw_visible_before_tool": raw_visible,
                       "tokens_emitted_in_tool_args": state.get("tokens_emitted", 0), "restored_in_tool_args": state.get("restored", 0),
                       "unrestored_tokens": state.get("unrestored", 0), "refused_unscoped_restorations": state.get("refused", 0),
                       "raw_in_tool_outputs": state.get("raw_in_tool_outputs", 0), "tool_calls": state.get("tool_calls", 0), "error": error}
                writer.writerow(row); handle.flush(); os.fsync(handle.fileno())
                print(f"  {mode:10s} {task_id:13s} inj={inj_id or '-':16s} utility={row['utility']} security={row['security']} protected={row['protected_values']} "
                      f"raw_visible={raw_visible} restored={row['restored_in_tool_args']} refused={row['refused_unscoped_restorations']} calls={row['tool_calls']} {error}")
    handle.close()

    with rows_path.open("r", encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["agent_model"] == args.agent_model and r["mode"] in modes]
    summary = []
    for mode in modes:
        rs = [r for r in rows if r["mode"] == mode]
        if not rs:
            continue
        pv = [r for r in rs if int(r["protected_values"]) > 0]
        def ci(sub, num, den, scale, digits):
            pairs = [(float(r[num]), float(r[den]) if den else 1.0) for r in sub]
            p, lo, hi = bootstrap_ratio_ci(pairs, n_boot=args.bootstrap, scale=scale)
            return f"{p:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"
        summary.append({"mode": mode, "tasks": str(len(rs)), "tasks_with_protected_values": str(len(pv)),
                        "attack_success_percent": ci(rs, "security", None, 100.0, 1) if args.with_injections else "n/a",
                        "utility_percent_all": ci(rs, "utility", None, 100.0, 1),
                        "utility_percent_protected": ci(pv, "utility", None, 100.0, 1) if pv else "n/a",
                        "boundary_leak_percent": ci(pv, "raw_visible_before_tool", "protected_values", 100.0, 1) if pv else "n/a",
                        "restoration_success_percent": ci(pv, "restored_in_tool_args", "tokens_emitted_in_tool_args", 100.0, 1) if pv else "n/a",
                        "raw_in_tool_outputs_mean": ci(rs, "raw_in_tool_outputs", None, 1.0, 2)})
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys())); w.writeheader(); w.writerows(summary)
    for s in summary:
        print(f"  {s['mode']:10s} utility(all)={s['utility_percent_all']:>20s} utility(protected)={s['utility_percent_protected']:>20s} BLR={s['boundary_leak_percent']:>20s} RSR={s['restoration_success_percent']}")
    manifest = [{"field": "benchmark", "value": f"AgentDojo {BENCHMARK_VERSION} suite {args.suite}, " + ("important_instructions injections on " + ";".join(i or "" for i in injection_ids) if args.with_injections else "no injections")},
                {"field": "restore_scope", "value": args.restore_scope},
                {"field": "tasks", "value": ";".join(task_ids)}, {"field": "modes", "value": ";".join(modes)},
                {"field": "detector", "value": args.detector}, {"field": "mediate_tool_outputs", "value": str(args.mediate_tool_outputs)},
                {"field": "agent_model", "value": args.agent_model}, {"field": "llm_backend", "value": "Ollama OpenAI-compatible /v1, native tool calling, temperature 0"},
                {"field": "bootstrap", "value": f"{args.bootstrap} task-level resamples, 95% percentile CI"},
                {"field": "python", "value": platform.python_version()}, {"field": "platform", "value": platform.platform()}]
    from importlib.metadata import version
    manifest.append({"field": "agentdojo", "value": version("agentdojo")})
    for k, v in detector.versions.items():
        manifest.append({"field": f"{detector.key}.{k}", "value": str(v)})
    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["field", "value"]); w.writeheader(); w.writerows(manifest)
    print(f"Rows: {rows_path}\nSummary: {summary_path}\nManifest: {manifest_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--agent-model", required=True)
    parser.add_argument("--suite", default="banking")
    parser.add_argument("--tasks", help="Comma-separated user task ids (default: all)")
    parser.add_argument("--modes", default="none,late,no_restore")
    parser.add_argument("--detector", default="regex_only", help="Registry key: regex_only, presidio, learned_lr, gliner_pii, spacy_ner")
    parser.add_argument("--mediate-tool-outputs", action="store_true")
    parser.add_argument("--with-injections", action="store_true", help="Run AgentDojo important_instructions injections (restoration-trigger adversary)")
    parser.add_argument("--injection-tasks", help="Comma-separated injection task ids (default: all in the suite)")
    parser.add_argument("--restore-scope", default="all", choices=["all", "user-directed"])
    parser.add_argument("--spacy-model", default="en_core_web_lg")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--output-tag")
    run(parser.parse_args())
    return 0


if __name__ == "__main__":
    sys.exit(main())
