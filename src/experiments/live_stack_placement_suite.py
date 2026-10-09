#!/usr/bin/env python3
"""Where mediation is applied, measured in a live agent stack.

The propagation results elsewhere in this artifact come from a deterministic
reference agent whose boundary artifacts are projections of the mediated
prompt, and every compared method mediates at the same point.  This suite
varies the *placement* of mediation with the detector and the mediation
operator held fixed, in a stack where the agent model itself writes every
boundary artifact.

Stack (one session per case and condition):

* **Agent**: a tool-calling agent served through an OpenAI-compatible
  ``/v1/chat/completions`` endpoint (Ollama or vLLM), native tool calls,
  temperature 0, fixed seed; every completion is cached durably, so an
  interrupted trajectory replays its finished calls on restart.
* **Tools**: the AgentDojo v1 ``banking``, ``slack`` and ``workspace``
  suites, executed for real against their sandboxed environments.  Their
  tool outputs carry personal data (IBANs, e-mail addresses, contact names,
  customer records), so sensitive values enter the trajectory mid-way and
  not only at the prompt, and AgentDojo's own environment-state utility
  checks score task success.  Suites with more tools than ``--max-tools``
  (workspace, travel) expose only the tool families the task needs, because
  a 4-bit 32B agent stops calling tools at all when handed 28 schemas.
* **Retrieval index**: ``search_knowledge_base(query)``, an Okapi BM25 index
  over the user's environment rendered as documents (e-mails, events,
  files, messages, transactions, web pages), queried with queries the agent
  writes.  It is a non-authorized boundary: tokens are never restored into it.
* **Persistent memory**: ``memory_write(note)`` / ``memory_read()``, an
  append-only store persisted to disk that the agent writes and reads back
  across steps.
* **Application log**: every model message, tool call and tool result is
  appended to a JSONL log, as an observability layer would record it.

Sensitive values enter at **ingress** (the user-context line of the system
prompt, the task prompt, and in the ``profile`` variant a short header with
the account holder's identifiers) and **mid-trajectory** (tool outputs and
retrieved documents).  Gold values come from rules over the environment that
share no code with any detector (``live_stack_components.build_lexicon``).
The fixed per-case reference set splits into ingress values and the values
the task's own ground-truth trajectory exposes; the values each run actually
received are recorded as a second, trajectory-dependent denominator.

Placement conditions (detector and symbolic operator fixed; ``--detector``):

* ``no_mediation``
* ``ingress_only``            mediate the system user-context line and the prompt
* ``egress_only``             mediate only what is written: retrieval queries,
                              memory notes, tool arguments, log lines
* ``per_edge``                ingress plus every tool output and retrieved
                              document before the agent reads it
* ``ingress_only_plus_restore`` ingress, with tokens restored into tool
                              arguments at the authorized boundary (the
                              configuration the manuscript deploys)
* ``per_edge_plus_restore``   per-edge, with the same restoration
* ``per_edge_plus_egress``    (optional) per-edge plus write-time mediation

Restoration happens only inside the executor of the user's own services
(AgentDojo tools), after logging, under a recipient check, and into the final
answer delivered to the user; the agent's history, the log, the memory and
the index never see restored values.

Per case and condition the suite records, from what the agent generated:
gold-value survival (per value and per character) in the model context, the
retrieval queries, the memory writes, the tool arguments as written and as
executed, the log, and the final answer before and after restoration;
AgentDojo utility; and, under restoration, restoration success and raw
values reaching non-authorized boundaries.  Summaries use cluster bootstrap
intervals (clusters are AgentDojo tasks, which the prompt variants share),
1,000 resamples, seed 17, and paired contrasts between placements.

Rows are appended with flush and fsync and skipped on restart by
(case, condition); free bytes and inodes are checked before a run starts.
``--mock-llm`` replaces the model by a deterministic stub that replays the
task's ground-truth plan and copies whatever tokens it sees, so the whole
pipeline can be exercised on CPU; ``--dry-run`` is mock mode on two tasks per
suite.  ``--plan`` prints the run size and exits.
"""
from __future__ import annotations

import argparse
import ast
import copy
import csv
import glob
import hashlib
import json
import os
import platform
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentdojo.agent_pipeline.agent_pipeline import load_system_message
from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suite

from ai4privacy_matched_baseline_suite import _merge_spans
import ai4privacy_lightweight_classifier_baseline as clf
from live_stack_components import (
    BM25Index, CompletionCache, GoldValue, append_jsonl, build_lexicon, char_coverage, char_total,
    cluster_ratio_ci, env_documents, gold_spans, paired_cluster_diff_ci, storage_preflight, values_in,
)
from mediation_baselines import Detector, build_detectors, render_symbolic, restore_symbolic, symbolic_tokens_in


EXPERIMENTS_DIR = Path(__file__).resolve().parent
AI4_PATH = EXPERIMENTS_DIR / "ai4privacy_pii300k_english_export.jsonl"
DEFAULT_CACHE_DIR = EXPERIMENTS_DIR / "ollama_cache"
DEFAULT_SUITES = "banking,slack,workspace"
DEFAULT_CONDITIONS = ("no_mediation,ingress_only,egress_only,per_edge,ingress_only_plus_restore,per_edge_plus_restore")


@dataclass(frozen=True)
class Placement:
    ingress: bool = False   # system user-context line and user prompt
    reads: bool = False     # every tool output and retrieved document, before the agent reads it
    egress: bool = False    # retrieval queries, memory notes, tool arguments, log lines, at write time
    restore: bool = False   # tokens restored into authorized tool arguments and the delivered answer


PLACEMENTS = {
    "no_mediation": Placement(),
    "ingress_only": Placement(ingress=True),
    "egress_only": Placement(egress=True),
    "per_edge": Placement(ingress=True, reads=True),
    "ingress_only_plus_restore": Placement(ingress=True, restore=True),
    "per_edge_plus_restore": Placement(ingress=True, reads=True, restore=True),
    "per_edge_plus_egress": Placement(ingress=True, reads=True, egress=True),
}

DEFAULT_CONTRASTS = [
    ("ingress_only", "no_mediation"), ("egress_only", "no_mediation"), ("per_edge", "no_mediation"),
    ("per_edge", "ingress_only"), ("per_edge", "egress_only"),
    ("per_edge_plus_restore", "ingress_only_plus_restore"), ("per_edge_plus_restore", "per_edge"),
    ("per_edge_plus_restore", "no_mediation"), ("per_edge_plus_egress", "per_edge"),
]

# Boundary artifacts, in the order they are reported.
ARTIFACTS = ["model_context", "retrieval", "memory", "tool_args", "tool_exec", "log", "final", "delivered"]
ARTIFACT_LABELS = {
    "model_context": "text the model endpoint received (system, user, tool results)",
    "retrieval": "queries the retrieval index received",
    "memory": "notes the memory store received",
    "tool_args": "tool arguments as the agent wrote them (after egress mediation, before restoration)",
    "tool_exec": "tool arguments as executed by the user's services (after restoration)",
    "log": "application log lines as stored",
    "final": "final answer as the agent generated it",
    "delivered": "final answer as delivered to the user (restored under *_plus_restore)",
}
NON_AUTHORIZED = ["retrieval", "memory", "tool_args", "log", "final"]
# origin: ingress values; reference mid-trajectory values (ground-truth trajectory and the
# index's answer to the raw prompt); mid-trajectory values this run actually received.
ORIGINS = ["in", "mid", "xmid"]

RECIPIENT_KEYS = {"recipient", "recipients", "to", "cc", "bcc", "email", "user_email", "channel", "user",
                  "participants", "emails", "iban"}

STACK_TOOLS = [
    {"type": "function", "function": {
        "name": "search_knowledge_base",
        "description": "Search the user's personal knowledge base (e-mails, calendar events, files, messages, "
                       "transactions, web pages) and return the most relevant documents.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Free-text search query."},
            "top_k": {"type": "integer", "description": "Number of documents to return (1-5).", "default": 3}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "memory_write",
        "description": "Save a note to your long-term memory so that you can use it in later steps.",
        "parameters": {"type": "object", "properties": {
            "note": {"type": "string", "description": "The note to save."}}, "required": ["note"]}}},
    {"type": "function", "function": {
        "name": "memory_read",
        "description": "Return every note saved in your long-term memory during this session.",
        "parameters": {"type": "object", "properties": {}}}},
]
STACK_TOOL_NAMES = {t["function"]["name"] for t in STACK_TOOLS}

STACK_INSTRUCTIONS = """
You also work with three components of the assistant platform:
  - search_knowledge_base(query) searches an index of the user's e-mails, calendar, files, messages and transactions. Use it first to gather context for the request.
  - memory_write(note) saves a note to your long-term memory. Whenever a tool returns information you will need later, save a short note.
  - memory_read() returns your saved notes. Read them before you give your final answer.
When the task is complete, reply to the user without calling any tool."""

# The account holder of the AgentDojo environments (the travel suite's user
# record); the profile variant prepends these identifiers to the prompt.
PROFILE = {"name": "Emma Johnson", "email": "emma.johnson@bluesparrowtech.com", "phone": "327-420-4923",
           "address": "123 Main Street, Anytown, USA"}
IDENTITY_SENTENCE = re.compile(r"The user's name is [^\n]*?\.(?=\s|$)")

ROW_FIELDS = (
    ["case", "cluster", "suite", "task", "variant", "condition", "detector", "agent_model", "run_id",
     "utility", "finished", "steps", "llm_calls", "env_calls", "kb_queries", "memory_writes", "memory_reads",
     "tool_errors", "tools_exposed", "tokens_emitted", "restored", "refused", "unrestored_exec",
     "nonauth_v", "nonauth_den", "det_in_hit", "det_in_tot", "det_mid_hit", "det_mid_tot", "max_prompt_tokens"]
    + [f"{o}_{u}_den" for o in ORIGINS for u in ("v", "c")]
    + [f"{a}_{o}_{u}" for a in ARTIFACTS for o in ORIGINS for u in ("v", "c")]
    + ["elapsed_s", "error"]
)


# ---------------------------------------------------------------------------
# Mediation operator (fixed across placements).
# ---------------------------------------------------------------------------


def letter_namespace(case_id: str) -> str:
    """Six letters from the case hash; letters only so a mapped digit run can never hit a token."""
    digest = hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:6]
    return "".join(chr(ord("a") + int(ch, 16)) for ch in digest)


class Mediator:
    """Fixed detector plus secure symbolic mapping with one per-session token table.

    Two span normalizations are part of the operator and apply identically
    under every placement.  Leading and trailing punctuation is trimmed from
    each detected span (``trim``): the learned detector returns whole
    whitespace tokens, so without trimming ``'bill.txt'`` would be mapped with
    its quotes and restored into a tool argument that names no file.  And
    spans overlapping a token already issued in this session are cut around
    it, so re-mediating released text never wraps a token in a new token (the
    learned detector flags token-shaped strings).
    """

    def __init__(self, detector: Detector, namespace: str, trim: bool = True) -> None:
        self.detector = detector
        self.namespace = namespace
        self.trim = trim
        self.mapping: dict[str, str] = {}
        self.token_re = re.compile(rf"BPSMAP-{namespace}-\d+")

    def _trimmed(self, text: str, start: int, end: int) -> tuple[int, int]:
        if not self.trim:
            return start, end
        while start < end and not text[start].isalnum():
            start += 1
        while end > start and not text[end - 1].isalnum():
            end -= 1
        return start, end

    def spans(self, text: str) -> list[tuple[int, int]]:
        protected = [(m.start(), m.end()) for m in self.token_re.finditer(text)]
        out: list[tuple[int, int]] = []
        for start, end in (self._trimmed(text, s, e) for s, e in self.detector(text)):
            pieces = [(start, end)]
            for ps, pe in protected:
                nxt = []
                for s, e in pieces:
                    if pe <= s or ps >= e:
                        nxt.append((s, e))
                        continue
                    if s < ps:
                        nxt.append((s, ps))
                    if pe < e:
                        nxt.append((pe, e))
                pieces = nxt
            out.extend((s, e) for s, e in pieces if any(ch.isalnum() for ch in text[s:e]))
        return _merge_spans(out)

    def mediate(self, text: str) -> tuple[str, list[tuple[int, int]]]:
        if not text:
            return text, []
        spans = self.spans(text)
        return render_symbolic(text, spans, self.namespace, self.mapping), spans

    def mediate_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.mediate(value)[0]
        if isinstance(value, list):
            return [self.mediate_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self.mediate_value(v) for k, v in value.items()}
        return value

    def restore_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return restore_symbolic(value, self.mapping)
        if isinstance(value, list):
            return [self.restore_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self.restore_value(v) for k, v in value.items()}
        return value

    def tokens_in(self, value: Any) -> list[str]:
        return symbolic_tokens_in(json.dumps(value, ensure_ascii=False, default=str), self.mapping)


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    return []


def _covered(spans: list[tuple[int, int]]) -> set[int]:
    return {i for s, e in spans for i in range(s, e)}


# ---------------------------------------------------------------------------
# Cases.
# ---------------------------------------------------------------------------


@dataclass
class Case:
    case_id: str
    cluster: str
    suite_name: str
    task_id: str
    variant: str
    prompt: str
    identity: str
    system_instructions: str
    suite: Any
    task: Any
    tools: list
    tool_schemas: list
    lexicon: list[GoldValue]
    r_in: set[GoldValue]
    r_mid: set[GoldValue]
    gt_calls: list
    gt_output: str
    kb_documents: list[str] = field(default_factory=list)


def _family(function) -> str:
    module = function.run.__module__.rsplit(".", 1)[-1]
    if module == "travel_booking_client":
        for key in ("hotel", "restaurant", "car", "flight", "user_information"):
            if key in function.name:
                return f"travel:{key}"
    return module


def _system_parts(no_think: bool) -> tuple[str, str]:
    """AgentDojo's default system message split into operator instructions and the user-context sentence."""
    base = load_system_message(None)
    match = IDENTITY_SENTENCE.search(base)
    identity = match.group(0) if match else ""
    instructions = (base.replace(identity, "").rstrip() + "\n" + STACK_INSTRUCTIONS).strip()
    if no_think:
        instructions += "\n/no_think"
    return instructions, identity


def _profile_header(suite_name: str, env_dump: dict) -> tuple[str, list[GoldValue]]:
    extra = ""
    gold = [GoldValue(PROFILE["name"], "name"), GoldValue("Emma", "given"), GoldValue(PROFILE["email"], "email"),
            GoldValue(PROFILE["phone"], "phone"), GoldValue(PROFILE["address"], "address")]
    iban = (env_dump.get("bank_account") or {}).get("iban")
    if iban:
        extra = f"; my IBAN is {iban}"
        gold.append(GoldValue(iban, "iban"))
    passport = (env_dump.get("user") or {}).get("passport_number")
    if passport:
        extra += f"; passport {passport}"
        gold.append(GoldValue(passport, "number"))
    header = (f"(About me, in case you need it: {PROFILE['name']}, e-mail {PROFILE['email']}, phone {PROFILE['phone']}, "
              f"home address {PROFILE['address']}{extra}.)\n\n")
    return header, gold


def build_cases(args: argparse.Namespace) -> list[Case]:
    instructions, identity = _system_parts(args.no_think)
    wanted = {t.strip() for t in args.tasks.split(",")} if args.tasks else None
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    cases: list[Case] = []
    for suite_name in [s.strip() for s in args.suites.split(",") if s.strip()]:
        suite = get_suite(args.benchmark_version, suite_name)
        task_ids = sorted(suite.user_tasks, key=lambda t: int(t.rsplit("_", 1)[-1]))
        if wanted:
            task_ids = [t for t in task_ids if f"{suite_name}/{t}" in wanted]
        if args.max_tasks_per_suite:
            task_ids = task_ids[: args.max_tasks_per_suite]
        for task_id in task_ids:
            task = suite.get_user_task_by_id(task_id)
            env = task.init_environment(suite.load_and_inject_default_environment({}))
            env_dump = env.model_dump(mode="json")
            gt_calls = task.ground_truth(env.model_copy(deep=True))
            gt_output = str(getattr(task, "GROUND_TRUTH_OUTPUT", "") or "")
            # Tool scoping: suites with many schemas expose only the families the task touches.
            tools = list(suite.tools)
            if len(tools) > args.max_tools:
                needed = {_family(f) for f in tools if f.name in {c.function for c in gt_calls}}
                tools = [f for f in tools if _family(f) in needed]
            schemas = [{"type": "function", "function": {"name": f.name, "description": f.description,
                                                         "parameters": f.parameters.model_json_schema()}}
                       for f in tools] + STACK_TOOLS
            header, header_gold = _profile_header(suite_name, env_dump)
            lexicon = build_lexicon(env_dump, extra=header_gold, given_names=not args.no_given_names)
            documents = env_documents(suite_name, env_dump)
            index = BM25Index(documents)
            # Reference mid-trajectory exposure: outputs of the ground-truth plan on a fresh copy,
            # plus what the index returns for the raw task prompt.
            gt_env = env.model_copy(deep=True)
            runtime = FunctionsRuntime(suite.tools)
            gt_texts = []
            for call in gt_calls:
                result, error = runtime.run_function(gt_env, call.function, dict(call.args))
                gt_texts.append(tool_result_to_str(result) if error is None else "")
            gt_texts.append(index.render(task.PROMPT, args.kb_top_k))
            ref_mid_text = "\n".join(gt_texts)
            for variant in variants:
                if variant not in ("task", "profile"):
                    raise ValueError(f"unknown variant {variant}")
                prompt = (header if variant == "profile" else "") + task.PROMPT
                r_in = values_in(identity + "\n" + prompt, lexicon)
                r_mid = values_in(ref_mid_text, lexicon) - r_in
                cases.append(Case(
                    case_id=f"{suite_name}/{task_id}/{variant}", cluster=f"{suite_name}/{task_id}", suite_name=suite_name,
                    task_id=task_id, variant=variant, prompt=prompt, identity=identity, system_instructions=instructions,
                    suite=suite, task=task, tools=tools, tool_schemas=schemas, lexicon=lexicon, r_in=r_in, r_mid=r_mid,
                    gt_calls=gt_calls, gt_output=gt_output, kb_documents=documents))
    if args.max_cases:
        cases = cases[: args.max_cases]
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        cases = cases[i::n]
    return cases


# ---------------------------------------------------------------------------
# Agents.
# ---------------------------------------------------------------------------


THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think(text: str) -> str:
    text = THINK_BLOCK.sub("", text or "")
    if "<think>" in text:  # an unterminated block: the whole remainder is reasoning
        text = text[: text.find("<think>")]
    return text.strip()


def _parse_arguments(raw: Any) -> tuple[dict, str]:
    if isinstance(raw, dict):
        return raw, ""
    if not raw:
        return {}, ""
    try:
        parsed = json.loads(raw)
        return (parsed if isinstance(parsed, dict) else {"value": parsed}), ""
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", str(raw), re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0)), ""
            except json.JSONDecodeError:
                pass
    return {}, f"unparseable tool arguments: {str(raw)[:120]}"


class OpenAICompatAgent:
    """Chat-completions client with native tool calling and a durable completion cache."""

    def __init__(self, model: str, base_url: str, api_key: str, cache: CompletionCache, temperature: float,
                 seed: int, max_tokens: int, timeout: int, retries: int = 3) -> None:
        self.model, self.base_url, self.api_key, self.cache = model, base_url.rstrip("/"), api_key, cache
        self.temperature, self.seed, self.max_tokens, self.timeout, self.retries = temperature, seed, max_tokens, timeout, retries
        self.generated = 0
        self.replayed = 0

    def bind(self, case: Case, session: "Session") -> None:  # the live agent needs no case knowledge
        return None

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        payload = {"model": self.model, "messages": messages, "tools": tools, "tool_choice": "auto",
                   "temperature": self.temperature, "seed": self.seed, "max_tokens": self.max_tokens, "stream": False}
        key = CompletionCache.key(payload)
        cached = self.cache.get(key)
        if cached is not None:
            self.replayed += 1
            return cached
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                request = urllib.request.Request(f"{self.base_url}/v1/chat/completions", data=body, method="POST",
                                                 headers={"Content-Type": "application/json",
                                                          "Authorization": f"Bearer {self.api_key}"})
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                choice = data["choices"][0]
                message = choice.get("message") or {}
                calls = []
                for i, tc in enumerate(message.get("tool_calls") or []):
                    fn = tc.get("function") or {}
                    calls.append({"id": tc.get("id") or f"call_{len(messages)}_{i}", "name": fn.get("name", ""),
                                  "arguments": fn.get("arguments", "")})
                normalized = {"content": message.get("content") or "", "tool_calls": calls,
                              "finish_reason": choice.get("finish_reason"), "usage": data.get("usage", {})}
                self.cache.put(key, normalized)
                self.generated += 1
                return normalized
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as exc:
                last = exc
                time.sleep(2 ** attempt)
        raise RuntimeError(f"model call failed after {self.retries} attempts: {last}")

    def metadata(self) -> dict[str, str]:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            for row in payload.get("models", []):
                if str(row.get("name")) == self.model:
                    details = row.get("details", {}) or {}
                    return {"model_digest": str(row.get("digest", "")), "model_family": str(details.get("family", "")),
                            "model_parameter_size": str(details.get("parameter_size", "")),
                            "model_quantization": str(details.get("quantization_level", ""))}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            pass
        return {"model_digest": ""}


class MockAgent:
    """Deterministic stand-in for the model, for CPU smoke tests of the whole pipeline.

    It searches the index with the first words of the prompt it sees, notes
    the task, replays the task's ground-truth tool plan one call per turn
    while noting each previous result, reads its memory, and answers with
    the ground-truth answer plus a snippet of the last tool output.  Like a
    copying agent, it never writes a raw value it has not seen: where its
    context holds a token for a ground-truth argument value instead of the
    value, it writes the token.  Its numbers test plumbing, not behaviour.
    """

    model = "mock-llm"

    def __init__(self) -> None:
        self.generated = 0
        self.replayed = 0

    def bind(self, case: Case, session: "Session") -> None:
        self.case, self.session = case, session
        self.turn = 0

    def _visible(self, messages: list[dict]) -> str:
        parts = [str(m.get("content") or "") for m in messages]
        parts += [json.dumps(tc, ensure_ascii=False) for m in messages for tc in m.get("tool_calls") or []]
        return "\n".join(parts)

    def _adapt(self, value: Any, visible: str) -> Any:
        if isinstance(value, list):
            return [self._adapt(v, visible) for v in value]
        if not isinstance(value, str) or not value or value in visible:
            return value
        for token, raw in sorted(self.session.mediator.mapping.items(), key=lambda kv: -len(kv[1])):
            if raw and raw in value and token in visible and raw not in visible:
                value = value.replace(raw, token)
        # A gold value the stub has neither seen raw nor as a token is one a
        # real agent could not write; hide it rather than leak ground truth.
        for gold in self.case.lexicon:
            if gold.text in value and gold.text not in visible:
                value = value.replace(gold.text, "<unknown>")
        return value

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        self.generated += 1
        visible = self._visible(messages)
        user = next(m["content"] for m in messages if m["role"] == "user")
        last_tool = next((m["content"] for m in reversed(messages) if m["role"] == "tool"), "")
        gt = self.case.gt_calls
        turn, self.turn = self.turn, self.turn + 1
        calls: list[dict] = []
        if turn == 0:
            calls.append(("search_knowledge_base", {"query": " ".join(user.split()[:8])}))
        elif turn == 1:
            calls.append(("memory_write", {"note": "Task: " + user[:160]}))
        elif 2 <= turn < 2 + len(gt):
            if turn > 2:
                calls.append(("memory_write", {"note": "Result: " + last_tool[:120]}))
            call = gt[turn - 2]
            calls.append((call.function, {k: self._adapt(v, visible) for k, v in call.args.items()}))
        elif turn == 2 + len(gt):
            calls.append(("memory_read", {}))
        else:
            answer = self._adapt(self.case.gt_output, visible) if self.case.gt_output else "Done."
            return {"content": f"{answer} Last result: {last_tool[:120]}", "tool_calls": [], "finish_reason": "stop"}
        return {"content": "", "finish_reason": "tool_calls",
                "tool_calls": [{"id": f"mock_{turn}_{i}", "name": n, "arguments": json.dumps(a, ensure_ascii=False, default=str)}
                               for i, (n, a) in enumerate(calls)]}

    def metadata(self) -> dict[str, str]:
        return {"model_digest": "mock"}


# ---------------------------------------------------------------------------
# One session: a case under one placement.
# ---------------------------------------------------------------------------


class Session:
    def __init__(self, case: Case, condition: str, placement: Placement, detector: Detector, args: argparse.Namespace,
                 run_id: str, log_path: Path, memory_path: Path) -> None:
        self.case, self.condition, self.placement, self.args, self.run_id = case, condition, placement, args, run_id
        self.mediator = Mediator(detector, letter_namespace(case.case_id), trim=not args.no_trim_spans)
        self.index = BM25Index(case.kb_documents)
        self.log_path, self.memory_path = log_path, memory_path
        self.texts: dict[str, list[str]] = {a: [] for a in ARTIFACTS}
        self.notes: list[str] = []
        self.raw_received: list[str] = []      # raw env-tool outputs and retrieved documents, before mediation
        self.provenance: list[str] = []        # raw texts a recipient may legitimately come from
        self.counts = {k: 0 for k in ("env_calls", "kb_queries", "memory_writes", "memory_reads", "tool_errors",
                                      "tokens_emitted", "restored", "refused", "unrestored_exec")}
        self.det = {"in_hit": 0, "in_tot": 0, "mid_hit": 0, "mid_tot": 0}
        self.seq = 0

    # -- edges -------------------------------------------------------------

    def _detect_coverage(self, raw: str, spans: list[tuple[int, int]], origin: str, candidates: set[GoldValue]) -> None:
        gold = _covered(gold_spans(raw, candidates))
        if gold:
            self.det[f"{origin}_hit"] += len(gold & _covered(spans))
            self.det[f"{origin}_tot"] += len(gold)

    def ingress(self, raw: str) -> str:
        if not self.placement.ingress:
            return raw
        released, spans = self.mediator.mediate(raw)
        self._detect_coverage(raw, spans, "in", self.case.r_in)
        return released

    def read(self, raw: str, from_environment: bool) -> str:
        if not self.placement.reads:
            return raw
        released, spans = self.mediator.mediate(raw)
        if from_environment:
            self._detect_coverage(raw, spans, "mid", set(self.case.lexicon) - self.case.r_in)
        return released

    def write(self, value: Any) -> Any:
        return self.mediator.mediate_value(value) if self.placement.egress else copy.deepcopy(value)

    def log(self, kind: str, text: str) -> None:
        stored = self.mediator.mediate(text)[0] if self.placement.egress else text
        self.texts["log"].append(stored)
        self.seq += 1
        append_jsonl(self.log_path, {"run_id": self.run_id, "case": self.case.case_id, "condition": self.condition,
                                     "seq": self.seq, "kind": kind, "text": stored})

    def context(self, text: str) -> None:
        self.texts["model_context"].append(text)

    # -- restoration -------------------------------------------------------

    def _authorized(self, args: dict) -> bool:
        policy = self.args.recipient_check
        if policy == "none":
            return True
        corpus = self.case.identity + "\n" + self.case.prompt
        if policy == "provenance":
            corpus += "\n" + "\n".join(self.provenance)
        for key, value in args.items():
            if key.lower() not in RECIPIENT_KEYS:
                continue
            for text in _strings(value):
                target = restore_symbolic(text, self.mediator.mapping)
                if target and target not in corpus:
                    return False
        return True

    # -- tool execution ----------------------------------------------------

    def execute(self, name: str, args: dict, call_id: str, runtime: FunctionsRuntime, env: Any, trace: list) -> str:
        written = self.write(args)
        from_environment = False
        if name == "search_knowledge_base":
            query = str(written.get("query", ""))
            try:
                k = max(1, min(5, int(written.get("top_k", self.args.kb_top_k))))
            except (TypeError, ValueError):
                k = self.args.kb_top_k
            self.texts["retrieval"].append(query)
            self.counts["kb_queries"] += 1
            raw = self.index.render(query, k)
            self.raw_received.append(raw)
            self.provenance.append(raw)
            from_environment = True
        elif name == "memory_write":
            note = str(written.get("note", ""))
            self.notes.append(note)
            self.texts["memory"].append(note)
            self.counts["memory_writes"] += 1
            append_jsonl(self.memory_path, {"run_id": self.run_id, "case": self.case.case_id, "condition": self.condition,
                                            "index": len(self.notes), "note": note})
            raw = f"Saved note {len(self.notes)}."
        elif name == "memory_read":
            self.counts["memory_reads"] += 1
            raw = "\n".join(f"{i}. {n}" for i, n in enumerate(self.notes, 1)) or "No notes saved yet."
        elif name in runtime.functions:
            self.counts["env_calls"] += 1
            self.texts["tool_args"].append(json.dumps({"function": name, "args": written}, ensure_ascii=False, default=str))
            executed = written
            tokens = self.mediator.tokens_in(written)
            self.counts["tokens_emitted"] += len(tokens)
            if self.placement.restore and tokens:
                if self._authorized(written):
                    executed = self.mediator.restore_value(written)
                    self.counts["restored"] += len(tokens)
                else:
                    self.counts["refused"] += len(tokens)
            self.counts["unrestored_exec"] += len(self.mediator.tokens_in(executed))
            executed = {k: (ast.literal_eval(v) if isinstance(v, str) and _is_list_literal(v) else v) for k, v in executed.items()}
            self.texts["tool_exec"].append(json.dumps({"function": name, "args": executed}, ensure_ascii=False, default=str))
            trace.append(FunctionCall(function=name, args=executed, id=call_id))
            result, error = runtime.run_function(env, name, executed)
            if error is not None:
                self.counts["tool_errors"] += 1
                raw = f"Error: {error}"
            else:
                raw = tool_result_to_str(result)
            self.raw_received.append(raw)
            self.provenance.append(raw)
            from_environment = True
        else:
            self.counts["tool_errors"] += 1
            raw = f"Error: the tool `{name}` is not available."
        if name in STACK_TOOL_NAMES:
            trace.append(FunctionCall(function=name, args=written, id=call_id))
        delivered = self.read(raw, from_environment)
        self.context(delivered)
        self.log("tool_call", json.dumps({"function": name, "args": written}, ensure_ascii=False, default=str))
        self.log("tool_result", delivered)
        return delivered


def _is_list_literal(text: str) -> bool:
    try:
        return isinstance(ast.literal_eval(text), list)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return False


# ---------------------------------------------------------------------------
# Running and measuring one trajectory.
# ---------------------------------------------------------------------------


def _agentdojo_utility(task: Any, output: str, pre_env: Any, post_env: Any, trace: list) -> tuple[bool, str]:
    try:
        verdict = task.utility_from_traces(output, pre_env, post_env, trace)
        if verdict is None:
            verdict = task.utility(output, pre_env, post_env)
        return bool(verdict), ""
    except Exception as exc:  # noqa: BLE001 - a utility check that crashes scores as failure, recorded
        return False, f"utility check raised {type(exc).__name__}: {str(exc)[:120]}"


def run_trajectory(case: Case, condition: str, agent: Any, detector: Detector, args: argparse.Namespace,
                   paths: dict[str, Path]) -> tuple[dict, dict]:
    started = time.time()
    placement = PLACEMENTS[condition]
    run_id = uuid.uuid4().hex[:12]
    session = Session(case, condition, placement, detector, args, run_id, paths["log"], paths["memory"])
    agent.bind(case, session)
    env = case.task.init_environment(case.suite.load_and_inject_default_environment({}))
    pre_env = env.model_copy(deep=True)
    runtime = FunctionsRuntime(case.tools)

    identity = session.ingress(case.identity)
    system = case.system_instructions + (f"\nUser context: {identity}" if identity else "")
    user = session.ingress(case.prompt)
    messages: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for kind, text in (("system", system), ("user", user)):
        session.context(text)
        session.log(kind, text)

    trace: list = []
    final, finished, steps, llm_calls, error, max_prompt = "", False, 0, 0, "", 0
    # A model-endpoint failure raises RuntimeError out of this loop; the caller
    # records nothing for the pair, so a rerun repeats it from the cache.
    for steps in range(1, args.max_steps + 1):
        reply = agent.complete(messages, case.tool_schemas)
        llm_calls += 1
        try:  # the endpoint's own count; near the server context it signals silent front truncation
            max_prompt = max(max_prompt, int((reply.get("usage") or {}).get("prompt_tokens") or 0))
        except (TypeError, ValueError):
            pass
        content = _strip_think(reply.get("content", ""))
        calls = []
        for tc in reply.get("tool_calls") or []:
            parsed, perr = _parse_arguments(tc.get("arguments"))
            if perr:
                error = (error + "; " if error else "") + perr
            calls.append({"id": tc["id"], "name": tc.get("name", ""), "args": parsed})
        message: dict = {"role": "assistant", "content": content}
        if calls:
            message["tool_calls"] = [{"id": c["id"], "type": "function",
                                      "function": {"name": c["name"], "arguments": json.dumps(c["args"], ensure_ascii=False, default=str)}}
                                     for c in calls]
        messages.append(message)
        session.log("assistant", content + ("\n" + json.dumps([{"function": c["name"], "args": c["args"]} for c in calls],
                                                               ensure_ascii=False, default=str) if calls else ""))
        if not calls:
            final, finished = content, True
            break
        final = content
        for c in calls:
            output = session.execute(c["name"], c["args"], c["id"], runtime, env, trace)
            messages.append({"role": "tool", "tool_call_id": c["id"], "name": c["name"], "content": output})
    delivered = restore_symbolic(final, session.mediator.mapping) if placement.restore else final
    session.texts["final"].append(final)
    session.texts["delivered"].append(delivered)
    utility, uerr = _agentdojo_utility(case.task, delivered, pre_env, env, trace)
    if uerr:
        error = (error + "; " if error else "") + uerr

    # -- measurement -------------------------------------------------------
    received = "\n".join(session.raw_received)
    x_mid = values_in(received, case.lexicon) - case.r_in
    origin_sets = {"in": case.r_in, "mid": case.r_mid, "xmid": x_mid}
    all_gold = case.r_in | case.r_mid | x_mid
    row: dict[str, Any] = {
        "case": case.case_id, "cluster": case.cluster, "suite": case.suite_name, "task": case.task_id,
        "variant": case.variant, "condition": condition, "detector": detector.key, "agent_model": agent.model,
        "run_id": run_id, "utility": int(utility), "finished": int(finished), "steps": steps, "llm_calls": llm_calls,
        "tools_exposed": len(case.tool_schemas), **session.counts,
        "det_in_hit": session.det["in_hit"], "det_in_tot": session.det["in_tot"],
        "det_mid_hit": session.det["mid_hit"], "det_mid_tot": session.det["mid_tot"], "max_prompt_tokens": max_prompt,
    }
    for origin, values in origin_sets.items():
        row[f"{origin}_v_den"] = len(values)
        row[f"{origin}_c_den"] = char_total(values)
    joined = {a: "\n".join(session.texts[a]) for a in ARTIFACTS}
    found_by_artifact = {}
    for artifact in ARTIFACTS:
        found = values_in(joined[artifact], all_gold)
        found_by_artifact[artifact] = found
        for origin, values in origin_sets.items():
            row[f"{artifact}_{origin}_v"] = len(found & values)
            row[f"{artifact}_{origin}_c"] = sum(char_coverage(v, joined[artifact])[0] for v in values)
    nonauth = set().union(*(found_by_artifact[a] for a in NON_AUTHORIZED))
    row["nonauth_v"], row["nonauth_den"] = len(nonauth), len(all_gold)
    row["elapsed_s"] = round(time.time() - started, 2)
    row["error"] = error

    record = {
        "run_id": run_id, "case": case.case_id, "condition": condition, "agent_model": agent.model, "detector": detector.key,
        "gold": {o: sorted(f"{v.kind}:{v.text}" for v in vals) for o, vals in origin_sets.items()},
        "found": {a: sorted(v.text for v in found_by_artifact[a]) for a in ARTIFACTS},
        "retrieval_queries": session.texts["retrieval"], "memory_writes": session.texts["memory"],
        "tool_args": session.texts["tool_args"], "tool_exec": session.texts["tool_exec"],
        "final_answer": final, "delivered_answer": delivered, "mapping_size": len(session.mediator.mapping),
        "log_lines": len(session.texts["log"]),
        "model_context": joined["model_context"] if args.store_context else None,
    }
    return row, record


# ---------------------------------------------------------------------------
# Summaries.
# ---------------------------------------------------------------------------


def _metric_specs() -> list[tuple[str, str, str | None, float]]:
    specs = [("utility_percent", "utility", None, 100.0), ("finished_percent", "finished", None, 100.0),
             ("restoration_success_percent", "restored", "tokens_emitted", 100.0),
             ("unrestored_tokens_per_case", "unrestored_exec", None, 1.0),
             ("nonauthorized_exposure_percent", "nonauth_v", "nonauth_den", 100.0),
             ("detector_char_recall_ingress_percent", "det_in_hit", "det_in_tot", 100.0),
             ("detector_char_recall_mid_percent", "det_mid_hit", "det_mid_tot", 100.0),
             ("llm_calls_per_case", "llm_calls", None, 1.0), ("kb_queries_per_case", "kb_queries", None, 1.0),
             ("memory_writes_per_case", "memory_writes", None, 1.0), ("env_calls_per_case", "env_calls", None, 1.0)]
    for artifact in ARTIFACTS:
        for origin in ORIGINS:
            specs.append((f"{artifact}.{origin}.value_percent", f"{artifact}_{origin}_v", f"{origin}_v_den", 100.0))
            specs.append((f"{artifact}.{origin}.char_percent", f"{artifact}_{origin}_c", f"{origin}_c_den", 100.0))
    return specs


def _units(rows: list[dict], num: str, den: str | None) -> list[tuple[str, float, float]]:
    return [(r["cluster"], float(r[num]), float(r[den]) if den else 1.0) for r in rows]


def summarize(rows: list[dict], conditions: list[str], contrasts: list[tuple[str, str]], n_boot: int,
              seed: int) -> tuple[list[dict], list[dict]]:
    by_cond = {c: [r for r in rows if r["condition"] == c] for c in conditions}
    summary: list[dict] = []
    for cond in conditions:
        rs = by_cond[cond]
        if not rs:
            continue
        for name, num, den, scale in _metric_specs():
            ci = cluster_ratio_ci(_units(rs, num, den), n_boot=n_boot, seed=seed, scale=scale)
            summary.append({"condition": cond, "metric": name, "cases": len(rs), "clusters": len({r["cluster"] for r in rs}),
                            "point": "" if ci is None else f"{ci[0]:.2f}", "lo": "" if ci is None else f"{ci[1]:.2f}",
                            "hi": "" if ci is None else f"{ci[2]:.2f}"})
    paired: list[dict] = []
    for a, b in contrasts:
        ra = {r["case"]: r for r in by_cond.get(a, [])}
        rb = {r["case"]: r for r in by_cond.get(b, [])}
        shared = sorted(set(ra) & set(rb))
        if not shared:
            continue
        for name, num, den, scale in _metric_specs():
            units = [(ra[c]["cluster"], float(ra[c][num]), float(ra[c][den]) if den else 1.0,
                      float(rb[c][num]), float(rb[c][den]) if den else 1.0) for c in shared]
            ci = paired_cluster_diff_ci(units, n_boot=n_boot, seed=seed, scale=scale)
            paired.append({"contrast": f"{a} - {b}", "metric": name, "pairs": len(shared),
                           "clusters": len({ra[c]["cluster"] for c in shared}),
                           "diff": "" if ci is None else f"{ci[0]:+.2f}", "lo": "" if ci is None else f"{ci[1]:+.2f}",
                           "hi": "" if ci is None else f"{ci[2]:+.2f}"})
    return summary, paired


def detector_contrasts(rows: list[dict], conditions: list[str], a: str, b: str, n_boot: int,
                       seed: int) -> list[dict]:
    """Per placement, detector ``a`` minus detector ``b`` on the same cases (cluster bootstrap)."""
    out: list[dict] = []
    for cond in conditions:
        ra = {r["case"]: r for r in rows if r["condition"] == cond and r["detector"] == a}
        rb = {r["case"]: r for r in rows if r["condition"] == cond and r["detector"] == b}
        shared = sorted(set(ra) & set(rb))
        if not shared:
            continue
        for name, num, den, scale in _metric_specs():
            units = [(ra[c]["cluster"], float(ra[c][num]), float(ra[c][den]) if den else 1.0,
                      float(rb[c][num]), float(rb[c][den]) if den else 1.0) for c in shared]
            ci = paired_cluster_diff_ci(units, n_boot=n_boot, seed=seed, scale=scale)
            out.append({"condition": cond, "contrast": f"{a} - {b}", "metric": name, "pairs": len(shared),
                        "clusters": len({ra[c]["cluster"] for c in shared}),
                        "diff": "" if ci is None else f"{ci[0]:+.2f}", "lo": "" if ci is None else f"{ci[1]:+.2f}",
                        "hi": "" if ci is None else f"{ci[2]:+.2f}"})
    return out


def _print_headline(summary: list[dict], conditions: list[str]) -> None:
    get = {(s["condition"], s["metric"]): s for s in summary}

    def cell(cond: str, metric: str) -> str:
        s = get.get((cond, metric))
        return "  n/a " if not s or s["point"] == "" else f"{float(s['point']):6.1f}"

    cols = [("util", "utility_percent")] + [(f"{a[:7]}:{o}", f"{a}.{o}.value_percent")
                                            for a in ("model_context", "retrieval", "memory", "tool_exec", "log", "final")
                                            for o in ("in", "mid")]
    print("\nValue survival (%) by boundary and origin (in = ingress values, mid = reference mid-trajectory values)")
    print(f"{'condition':28s}" + "".join(f"{c:>15s}" for c, _ in cols))
    for cond in conditions:
        if any(k[0] == cond for k in get):
            print(f"{cond:28s}" + "".join(f"{cell(cond, m):>15s}" for _, m in cols))


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------


def _train_learned_detector(cache_path: Path) -> dict:
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    records = clf._load_records(AI4_PATH)
    train = [r for r in records if str(r.get("split")) == "ai4privacy-train"][: clf.TRAIN_DOC_LIMIT]
    weights, _ = clf._train_logreg(clf._build_examples(train))
    tmp = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")  # shards may train at the same moment
    tmp.write_text(json.dumps(weights), encoding="utf-8")
    os.replace(tmp, cache_path)
    return weights


def _with_tag(path: Path, tag: str | None) -> Path:
    return path if not tag else path.with_name(f"{path.stem}_{tag}{path.suffix}")


def _read_rows(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for p in paths:
        if p.exists():
            with p.open("r", encoding="utf-8", newline="") as handle:
                rows.extend(csv.DictReader(handle))
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def _plan(cases: list[Case], conditions: list[str], pending: int, sec_per_call: float) -> dict[str, float]:
    turns = [len(c.gt_calls) + 4 for c in cases]  # ground-truth calls + index, notes, memory read, answer
    per_case = sum(turns) / len(turns) if turns else 0.0
    calls = pending * per_case
    return {"cases": len(cases), "clusters": len({c.cluster for c in cases}), "conditions": len(conditions),
            "trajectories_pending": pending, "mean_turns_per_trajectory_est": round(per_case, 1),
            "model_calls_est": round(calls), "model_calls_upper_bound": pending * 15,
            "gpu_hours_est_serial": round(calls * sec_per_call / 3600, 1),
            "disk_mb_est": round(pending * 0.15 + calls * 0.002, 1)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--agent-model", default="qwen3:32b")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434", help="Server root; /v1/chat/completions is appended")
    parser.add_argument("--api-key", default="ollama")
    parser.add_argument("--benchmark-version", default="v1")
    parser.add_argument("--suites", default=DEFAULT_SUITES)
    parser.add_argument("--variants", default="task,profile", help="task: published prompt; profile: prompt with the account holder's identifiers prepended")
    parser.add_argument("--tasks", help="Comma-separated suite/user_task_N ids (default: all tasks of the suites)")
    parser.add_argument("--max-tasks-per-suite", type=int)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--conditions", default=DEFAULT_CONDITIONS)
    parser.add_argument("--contrasts", help="Comma-separated A-B pairs, e.g. per_edge-ingress_only (default: the built-in set)")
    parser.add_argument("--detector", default="learned_lr", help="Registry key: learned_lr, presidio, gliner_pii, regex_only, spacy_ner, ...")
    parser.add_argument("--spacy-model", default="en_core_web_lg")
    parser.add_argument("--recipient-check", default="provenance", choices=["provenance", "prompt", "none"],
                        help="provenance: a recipient must occur in the raw prompt or in raw data the user's services returned; "
                             "prompt: in the raw prompt only; none: no check")
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--max-tools", type=int, default=14, help="Suites with more tools expose only the tool families the task touches")
    parser.add_argument("--kb-top-k", type=int, default=3)
    parser.add_argument("--think", dest="no_think", action="store_false", help="Allow Qwen3 thinking (default appends /no_think)")
    parser.add_argument("--no-given-names", action="store_true", help="Exclude single given names from the gold lexicon")
    parser.add_argument("--no-trim-spans", action="store_true",
                        help="Keep the detector's raw span boundaries (default trims leading/trailing punctuation)")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--context-length", type=int, default=32768,
                        help="The server's context window (OLLAMA_CONTEXT_LENGTH); only used to flag trajectories near it")
    parser.add_argument("--server-config", default="",
                        help="Server settings the endpoint cannot report itself (e.g. KV cache type, parallel slots); "
                             "recorded verbatim in the manifest")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--mock-llm", action="store_true", help="Replace the model with a deterministic stub (CPU smoke test)")
    parser.add_argument("--dry-run", action="store_true", help="Mock model on two tasks per suite")
    parser.add_argument("--plan", action="store_true", help="Print the run size and exit")
    parser.add_argument("--sec-per-call", type=float, default=5.0, help="Serial seconds per model call used by --plan")
    parser.add_argument("--out-dir", type=Path, default=EXPERIMENTS_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output-tag")
    parser.add_argument("--shard", help="I/N: run every N-th case starting at I (outputs get a shard tag)")
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--bootstrap-seed", type=int, default=17)
    parser.add_argument("--min-free-gb", type=float, default=2.0)
    parser.add_argument("--min-free-inodes", type=int, default=20000)
    parser.add_argument("--no-store-context", dest="store_context", action="store_false",
                        help="Do not keep the full model context in the per-run artifact records")
    parser.add_argument("--summarize-only", action="store_true", help="Rebuild summaries from existing rows without running")
    parser.add_argument("--rows-glob", help="With --summarize-only: pool every rows file matching this glob (e.g. all shards)")
    parser.add_argument("--versus-detector",
                        help="With --summarize-only: also write per-placement contrasts of --detector minus this "
                             "detector on shared cases (the glob must match both detectors' rows)")
    args = parser.parse_args()

    if args.dry_run:
        args.mock_llm = True
        args.max_tasks_per_suite = args.max_tasks_per_suite or 2
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    unknown = [c for c in conditions if c not in PLACEMENTS]
    if unknown:
        parser.error(f"unknown condition(s): {unknown}; known: {sorted(PLACEMENTS)}")
    contrasts = ([tuple(p.split("-", 1)) for p in args.contrasts.split(",")] if args.contrasts else DEFAULT_CONTRASTS)
    contrasts = [(a, b) for a, b in contrasts if a in conditions and b in conditions]

    model_name = "mock-llm" if args.mock_llm else args.agent_model
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", model_name)
    # Outputs are per model and detector; the completion cache is per model only, so a second
    # detector arm replays every request whose mediated text coincides (all of no_mediation).
    stem = f"{safe}_{re.sub(r'[^A-Za-z0-9_.-]+', '_', args.detector)}"
    tag = args.output_tag
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        tag = f"{tag + '_' if tag else ''}shard{i}of{n}"
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "rows": _with_tag(out / f"live_stack_placement_rows_{stem}.csv", tag),
        "summary": _with_tag(out / f"live_stack_placement_summary_{stem}.csv", tag),
        "paired": _with_tag(out / f"live_stack_placement_paired_{stem}.csv", tag),
        "manifest": _with_tag(out / f"live_stack_placement_runtime_manifest_{stem}.csv", tag),
        "artifacts": _with_tag(out / f"live_stack_placement_artifacts_{stem}.jsonl", tag),
        "log": _with_tag(out / f"live_stack_placement_app_log_{stem}.jsonl", tag),
        "memory": _with_tag(out / f"live_stack_placement_memory_{stem}.jsonl", tag),
    }

    if args.summarize_only:
        files = [Path(p) for p in sorted(glob.glob(args.rows_glob))] if args.rows_glob else [paths["rows"]]
        rows = [r for r in _read_rows(files) if r["condition"] in conditions and r["detector"] == args.detector]
        other = sorted({r["detector"] for r in _read_rows(files)} - {args.detector})
        if other:
            print(f"[note] ignored rows of other detector(s) {other}; pass --detector to summarize those")
        summary, paired = summarize(rows, conditions, contrasts, args.bootstrap, args.bootstrap_seed)
        _write_csv(paths["summary"], summary)
        _write_csv(paths["paired"], paired)
        _print_headline(summary, conditions)
        print(f"Pooled {len(rows)} rows from {len(files)} file(s)\nSummary: {paths['summary']}\nPaired: {paths['paired']}")
        if args.versus_detector:
            versus = detector_contrasts(_read_rows(files), conditions, args.detector, args.versus_detector,
                                        args.bootstrap, args.bootstrap_seed)
            vs_path = _with_tag(out / f"live_stack_placement_detector_contrast_{stem}_vs_"
                                      f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', args.versus_detector)}.csv", tag)
            _write_csv(vs_path, versus)
            print(f"Detector contrast ({len(versus)} rows): {vs_path}" if versus
                  else f"[warn] no shared cases between {args.detector} and {args.versus_detector} in the glob")
        return 0

    print("[setup] building cases (environments, gold lexicons, reference trajectories, indexes)")
    cases = build_cases(args)
    done: set[tuple[str, str]] = set()
    if paths["rows"].exists():
        with paths["rows"].open("r", encoding="utf-8", newline="") as probe:
            header = next(csv.reader(probe), [])
        if header != ROW_FIELDS:
            print(f"[error] {paths['rows'].name} has a different schema ({len(header)} columns, this build writes "
                  f"{len(ROW_FIELDS)}); appending would misalign rows. Use a new --output-tag.")
            return 1
        existing = _read_rows([paths["rows"]])
        foreign = sorted({r["detector"] for r in existing} - {args.detector})
        if foreign:
            print(f"[error] {paths['rows'].name} holds rows of detector(s) {foreign}; resuming would mark this "
                  f"detector's cases done. Use a new --output-tag.")
            return 1
        done = {(r["case"], r["condition"]) for r in existing}
    pending = [(c, cond) for cond in conditions for c in cases if (c.case_id, cond) not in done]
    plan = _plan(cases, conditions, len(pending), args.sec_per_call)
    print("[plan] " + ", ".join(f"{k}={v}" for k, v in plan.items()))
    with_in = sum(1 for c in cases if c.r_in)
    with_mid = sum(1 for c in cases if c.r_mid)
    print(f"[gold] cases with ingress gold: {with_in}/{len(cases)}; with reference mid-trajectory gold: {with_mid}/{len(cases)}; "
          f"mean |R_in|={sum(len(c.r_in) for c in cases) / max(1, len(cases)):.1f}, "
          f"mean |R_mid|={sum(len(c.r_mid) for c in cases) / max(1, len(cases)):.1f}")
    if args.plan:
        return 0

    ok, message = storage_preflight(out, int(plan["disk_mb_est"] * 1e6), int(args.min_free_gb * 1e9), args.min_free_inodes)
    print("[storage] " + message)
    if not ok:
        return 2
    if not args.mock_llm and out.resolve() != args.cache_dir.resolve():
        ok, message = storage_preflight(args.cache_dir, int(plan["model_calls_est"] * 2000), int(0.2e9), 100)
        print("[storage] cache " + message)
        if not ok:
            return 2

    learned = _train_learned_detector(out / "live_stack_learned_lr_weights.json") if args.detector == "learned_lr" else None
    detector = build_detectors([args.detector], learned_weights=learned, spacy_model=args.spacy_model)[0]
    if args.mock_llm:
        agent: Any = MockAgent()
    else:
        cache = CompletionCache(args.cache_dir / f"livestack__{safe}.jsonl")
        agent = OpenAICompatAgent(args.agent_model, args.base_url, args.api_key, cache, args.temperature, args.seed,
                                  args.max_tokens, args.timeout)

    new_file = not paths["rows"].exists()
    handle = paths["rows"].open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
    if new_file:
        writer.writeheader()
        handle.flush()
        os.fsync(handle.fileno())
    failures = 0
    try:
        for n, (case, cond) in enumerate(pending, 1):
            try:
                row, record = run_trajectory(case, cond, agent, detector, args, paths)
            except RuntimeError as exc:  # the endpoint is down: keep what is done, stop cleanly
                failures += 1
                print(f"  [fail] {cond} {case.case_id}: {exc}")
                if failures >= 3:
                    print("  [stop] three consecutive model failures; completed rows are kept, rerun resumes")
                    break
                continue
            failures = 0
            append_jsonl(paths["artifacts"], record)     # durable before the row that marks the case done
            writer.writerow(row)
            handle.flush()
            os.fsync(handle.fileno())
            print(f"  [{n}/{len(pending)}] {cond:26s} {case.case_id:32s} util={row['utility']} steps={row['steps']:>2} "
                  f"kb={row['kb_queries']} mem={row['memory_writes']} env={row['env_calls']} "
                  f"ctx(in/mid)={row['model_context_in_v']}/{row['in_v_den']},{row['model_context_mid_v']}/{row['mid_v_den']} "
                  f"log={row['log_in_v']},{row['log_mid_v']} restored={row['restored']} refused={row['refused']}"
                  + (f" ERR={row['error'][:60]}" if row["error"] else ""))
    finally:
        handle.close()

    rows = [r for r in _read_rows([paths["rows"]])
            if r["condition"] in conditions and r["agent_model"] == model_name and r["detector"] == detector.key]
    near_limit = [r for r in rows if int(r.get("max_prompt_tokens") or 0) >= 0.95 * args.context_length]
    if near_limit:
        print(f"[warn] {len(near_limit)} trajectories reached >=95% of the {args.context_length}-token context; the server "
              f"may have truncated their prompts from the front (system prompt first). Raise OLLAMA_CONTEXT_LENGTH and rerun "
              f"those pairs under a new --output-tag.")
    summary, paired = summarize(rows, conditions, contrasts, args.bootstrap, args.bootstrap_seed)
    _write_csv(paths["summary"], summary)
    _write_csv(paths["paired"], paired)
    _print_headline(summary, conditions)

    from importlib.metadata import version
    manifest = [
        ("benchmark", f"AgentDojo {args.benchmark_version} suites {args.suites}, no injections, variants {args.variants}"),
        ("agentdojo", version("agentdojo")), ("cases", str(len(cases))), ("clusters", str(len({c.cluster for c in cases}))),
        ("conditions", ";".join(conditions)),
        ("placements", "; ".join(f"{c}={PLACEMENTS[c]}" for c in conditions)),
        ("detector", detector.key),
        ("mediation_operator", "secure symbolic mapping, one token table per case session, letter namespace; "
                               + ("raw detector span boundaries" if args.no_trim_spans else "span edges trimmed of punctuation")),
        ("recipient_check", args.recipient_check), ("max_steps", str(args.max_steps)),
        ("tool_scoping", f"suites with more than {args.max_tools} tools expose the tool families the ground truth touches"),
        ("retrieval_index", f"Okapi BM25 k1=1.5 b=0.75 over environment documents, top_k {args.kb_top_k}, never mediated at ingestion"),
        ("memory", "append-only per-session note store persisted to JSONL"),
        ("log", "JSONL: system, user, assistant, tool_call, tool_result lines"),
        ("gold", "rule-derived lexicon from the environment (structured identifiers, personal fields, derived names)"
                 + ("" if not args.no_given_names else ", given names excluded")),
        ("agent_model", model_name), ("endpoint", "mock" if args.mock_llm else f"{args.base_url}/v1/chat/completions"),
        ("server_context_length_declared", str(args.context_length)),
        ("server_config_declared", args.server_config or "not declared"),
        ("max_prompt_tokens_observed", str(max((int(r.get("max_prompt_tokens") or 0) for r in rows), default=0))),
        ("decoding", f"temperature {args.temperature}, seed {args.seed}, max_tokens {args.max_tokens}, "
                     + ("/no_think appended" if args.no_think else "thinking allowed")),
        ("bootstrap", f"{args.bootstrap} cluster (task) resamples, seed {args.bootstrap_seed}, 95% percentile; paired by case"),
        ("generated_calls_this_invocation", str(agent.generated)), ("replayed_calls_this_invocation", str(agent.replayed)),
        ("python", platform.python_version()), ("platform", platform.platform()),
    ]
    manifest += [(f"agent.{k}", v) for k, v in agent.metadata().items()]
    manifest += [(f"{detector.key}.{k}", str(v)) for k, v in detector.versions.items()]
    _write_csv(paths["manifest"], [{"field": k, "value": v} for k, v in manifest])
    for key in ("rows", "summary", "paired", "manifest", "artifacts", "log", "memory"):
        print(f"{key}: {paths[key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
