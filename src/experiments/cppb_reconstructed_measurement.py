#!/usr/bin/env python3
"""Re-measure the four CPPB appendix tables under a fully named runtime.

The exposure, utility, policy-sensitivity, and latency tables in the appendix
were carried over from score logs whose generating runtime was never recorded,
and whose input prompts no longer exist: the released manifest holds template
and prompt stubs rather than prompt texts.  Writing a backend, digest, or
decoding setting beside those numbers would assert a runtime rather than
record one.  This script instead re-measures all four tables on the
reconstructed 256-prompt surface, under a runtime it manifests in full, so the
reported numbers are provenanced rather than inherited.

Roster (detector plus renderer), one row per appendix table line:

* ``no_protection``                -- raw prompt, released unchanged;
* ``regex_only``                   -- structured-identifier regexes, typed placeholders;
* ``capitalization_heuristic``     -- capitalization/title/location regexes, typed placeholders;
* ``generic_deid``                 -- policy-aware detector, one generic ``[REDACTED]`` token;
* ``enterprise_staged``            -- Presidio, category-aware typed placeholders;
* ``proposed_abstraction``         -- LLM rewrite to category-level referents;
* ``proposed_utility_constrained`` -- learned span detector at tau, typed placeholders.

Metrics:

* **PER** -- residual direct exposure: gold sensitive spans still literally
  present in the released prompt, as a percentage of all gold spans, with
  document-level bootstrap confidence intervals.
* **AC** -- answer consistency: judge-scored task-relevant agreement between
  the downstream answer on the raw prompt and on the mediated prompt.
* **TSR** -- task success: judge-scored satisfaction of the template's own
  stated success criteria by the mediated answer.
* **latency** -- mediation wall-clock per prompt, mean and P95.  This is a CPU
  measurement of the middleware alone and excludes model generation.

The policy sweep re-measures every tau as an actual operating point.  The
released sweep artifact interpolates linearly between three profiles, so its
intermediate points are drawn rather than measured; every tau here is run.

Every generation goes through the shared response cache, and every scored row
is appended and flushed as it completes, so an interrupted run resumes without
regenerating or rescoring completed work.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import ai4privacy_lightweight_classifier_baseline as clf
from ai4privacy_matched_baseline_suite import _merge_spans, _policy_aware_spans
from mediation_baselines import (
    Detector,
    LLMSanitizer,
    bootstrap_ratio_ci,
    build_detectors,
    render_placeholders,
)
from ollama_client import CachedOllamaChat

EXPERIMENTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENTS_DIR.parents[1]
ANNOTATIONS_PATH = REPO_ROOT / "data" / "cppb_full_annotations.jsonl"
ABSTRACTION_TEMPLATE = EXPERIMENTS_DIR / "privacylens_abstraction_prompt_template.txt"

DEFAULT_AGENT = "qwen3:32b-q4km-hf"
DEFAULT_JUDGE = "mistral:7b-instruct-v0.2-q4km-hf"
DEFAULT_SANITIZER = "qwen3:8b-q4km-hf"
DEFAULT_TAU = 0.55
SWEEP_TAUS = [0.30, 0.40, 0.50, 0.55, 0.60, 0.70, 0.80]

# The reconstructed prompts and their answers are short; these ceilings are
# sized to the surface rather than left at a library default, because Ollama
# builds a model's KV cache from the context of the request that loads it.
AGENT_NUM_CTX = 2048
JUDGE_NUM_CTX = 2048
AGENT_NUM_PREDICT = 320
JUDGE_NUM_PREDICT = 8
SEED = 17

ROW_FIELDS = [
    "method", "tau", "prompt_id", "template_id", "variant_id", "split",
    "privacy_category", "gold_spans", "surviving_spans", "mediation_ms",
    "ac", "tsr", "ac_verdict", "tsr_verdict", "agent_model", "judge_model",
]

GENERIC_TOKEN = "[REDACTED]"


# ---------------------------------------------------------------------------
# Surface
# ---------------------------------------------------------------------------


def _load_prompts(max_prompts: int | None, shard: str | None) -> list[dict[str, Any]]:
    with ANNOTATIONS_PATH.open("r", encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    records.sort(key=lambda r: str(r.get("prompt_id")))
    if max_prompts:
        records = records[:max_prompts]
    if shard:
        i, n = (int(x) for x in shard.split("/"))
        records = records[i::n]
    return records


def _gold_texts(record: dict[str, Any]) -> list[str]:
    spans = record.get("sensitive_spans") or []
    out = []
    for span in spans:
        text = str(span.get("text", "")).strip()
        if text:
            out.append(text)
    return out


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def render_generic(text: str, spans: list[tuple[int, int]]) -> str:
    """Generic de-identification: every protected span collapses to one token.

    This is the baseline that removes type information along with the value,
    which is why it costs utility that typed placeholders keep.
    """
    out: list[str] = []
    cursor = 0
    for start, end in _merge_spans(spans):
        if start < cursor:
            continue
        out.append(text[cursor:start])
        out.append(GENERIC_TOKEN)
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def _learned_spans_at(weights: dict[str, float], text: str, tau: float) -> list[tuple[int, int]]:
    """The learned detector's spans at an explicit decision threshold.

    ``clf._predict_spans`` fixes the threshold at its module constant.  The
    policy table varies it, so the token loop is repeated here with tau as a
    parameter rather than mutating the module's constant, which would silently
    change every other caller in the same process.
    """
    tokens = clf._tokenize(text)
    spans: list[tuple[int, int]] = []
    for idx, (start, end, token) in enumerate(tokens):
        prev_token = tokens[idx - 1][2] if idx > 0 else None
        score = sum(weights.get(name, 0.0) for name in clf._token_features(token, prev_token))
        if 1.0 / (1.0 + math.exp(-score)) >= tau:
            spans.append((start, end))
    return _merge_spans(spans)


class Mediator:
    """A named mediation method: detect, then release."""

    def __init__(self, key: str, label: str, fn: Callable[[str], str], versions: dict[str, str] | None = None) -> None:
        self.key = key
        self.label = label
        self.fn = fn
        self.versions = versions or {}

    def __call__(self, text: str) -> str:
        return self.fn(text)


def build_mediators(
    keys: list[str],
    *,
    tau: float,
    weights: dict[str, float],
    detectors: dict[str, Detector],
    sanitizer: LLMSanitizer | None,
) -> list[Mediator]:
    built: list[Mediator] = []
    for key in keys:
        if key == "no_protection":
            built.append(Mediator(key, "No protection", lambda t: t))
        elif key == "regex_only":
            det = detectors["regex_only"]
            built.append(Mediator(key, "Regex-only", lambda t, d=det: render_placeholders(t, d.typed(t))))
        elif key == "capitalization_heuristic":
            det = detectors["capitalization_heuristic"]
            built.append(Mediator(key, "Capitalization heuristic",
                                  lambda t, d=det: render_placeholders(t, d.typed(t))))
        elif key == "generic_deid":
            built.append(Mediator(key, "Generic de-identification",
                                  lambda t: render_generic(t, _policy_aware_spans(t))))
        elif key == "enterprise_staged":
            det = detectors["presidio"]
            built.append(Mediator(key, "Enterprise staged redaction",
                                  lambda t, d=det: render_placeholders(t, d.typed(t)), det.versions))
        elif key == "proposed_abstraction":
            if sanitizer is None:
                raise ValueError("proposed_abstraction requires a sanitizer model")
            built.append(Mediator(key, "Proposed (semantic abstraction)",
                                  lambda t, s=sanitizer: s.sanitize(t), sanitizer.metadata()))
        elif key == "proposed_utility_constrained":
            built.append(Mediator(key, "Proposed (utility-constrained)",
                                  lambda t: render_generic_typed(t, weights, tau),
                                  {"decision_threshold": f"{tau:.2f}"}))
        else:
            raise ValueError(f"Unknown mediator key: {key}")
    return built


def render_generic_typed(text: str, weights: dict[str, float], tau: float) -> str:
    """Learned-detector release at tau, as typed placeholders.

    The learned detector returns untyped spans, so every span is released under
    one placeholder kind.  That keeps role information ("something was removed
    here, and these two removals are different") without asserting a category
    the detector did not produce.
    """
    spans = _learned_spans_at(weights, text, tau)
    return render_placeholders(text, [(s, e, "LEARNED") for s, e in spans])


# ---------------------------------------------------------------------------
# Downstream answering and judging
# ---------------------------------------------------------------------------


def _answer(agent: CachedOllamaChat, record: dict[str, Any], prompt_text: str) -> str | None:
    messages = [
        {"role": "system",
         "content": "You are a task assistant. Answer the user's request directly and briefly. "
                    "Some values may appear as placeholder tokens; treat them as opaque referents "
                    "and keep using them by name rather than inventing concrete values."},
        {"role": "user",
         "content": f"{prompt_text}\n\nRequired output components: "
                    f"{record.get('required_output_components', '')}"},
    ]
    return agent.chat(messages, temperature=0.0, num_predict=AGENT_NUM_PREDICT, seed=SEED)


_AC_CHOICES = {"AGREE": 1.0, "PARTIAL": 0.5, "DISAGREE": 0.0}


def _judge_ac(judge: CachedOllamaChat, record: dict[str, Any], raw_answer: str, med_answer: str) -> tuple[float | None, str]:
    """Task-relevant agreement between the raw-prompt and mediated-prompt answers."""
    messages = [
        {"role": "system", "content": "You grade agreement between two answers. Reply with exactly one word."},
        {"role": "user", "content":
            f"Task: {record.get('task_objective', '')}\n"
            f"Required components: {record.get('required_output_components', '')}\n\n"
            f"ANSWER A:\n{raw_answer}\n\nANSWER B:\n{med_answer}\n\n"
            "Do A and B agree on the task-relevant content? A placeholder token standing in for a "
            "concrete value still counts as agreement when the role it fills is the same. "
            "Reply with exactly one of: AGREE, PARTIAL, DISAGREE."},
    ]
    reply = judge.chat(messages, temperature=0.0, num_predict=JUDGE_NUM_PREDICT, seed=SEED)
    return _parse_choice(reply, _AC_CHOICES)


_TSR_CHOICES = {"SUCCESS": 1.0, "FAIL": 0.0}


def _judge_tsr(judge: CachedOllamaChat, record: dict[str, Any], answer: str) -> tuple[float | None, str]:
    """Whether the mediated answer satisfies the template's own success criteria."""
    messages = [
        {"role": "system", "content": "You grade task success. Reply with exactly one word."},
        {"role": "user", "content":
            f"Task: {record.get('task_objective', '')}\n"
            f"Success criteria: {record.get('task_success_criteria', '')}\n\n"
            f"ANSWER:\n{answer}\n\n"
            "Does the answer satisfy the success criteria? A placeholder token standing in for a "
            "protected value satisfies the category-level referent requirement. "
            "Reply with exactly one of: SUCCESS, FAIL."},
    ]
    reply = judge.chat(messages, temperature=0.0, num_predict=JUDGE_NUM_PREDICT, seed=SEED)
    return _parse_choice(reply, _TSR_CHOICES)


def _parse_choice(reply: str | None, choices: dict[str, float]) -> tuple[float | None, str]:
    if reply is None:
        return None, ""
    upper = reply.upper()
    for name, value in choices.items():
        if re.search(rf"\b{name}\b", upper):
            return value, name
    return None, reply.strip()[:40]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _survival(released: str, gold: list[str]) -> int:
    """Gold spans still literally present in the released text.

    This is a lower bound on disclosure, not a measure of inferability: a fact
    the release paraphrases rather than repeats is not counted here.
    """
    lowered = released.lower()
    return sum(1 for text in gold if text.lower() in lowered)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(pct / 100.0 * (len(ordered) - 1)))))
    return ordered[idx]


def _read_done(path: Path) -> set[tuple[str, str, str]]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {(r["method"], r["tau"], r["prompt_id"]) for r in csv.DictReader(handle)}


def _with_tag(path: Path, tag: str | None) -> Path:
    return path if not tag else path.with_name(f"{path.stem}_{tag}{path.suffix}")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    records = _load_prompts(args.max_prompts, args.shard)
    if not records:
        print("no prompts selected", file=sys.stderr)
        return 1

    safe_agent = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.agent_model)
    tag = args.output_tag
    if args.shard:
        i, n = args.shard.split("/")
        tag = f"{tag + '_' if tag else ''}shard{i}of{n}"

    rows_path = _with_tag(EXPERIMENTS_DIR / f"cppb_reconstructed_rows_{safe_agent}.csv", tag)
    summary_path = _with_tag(EXPERIMENTS_DIR / f"cppb_reconstructed_summary_{safe_agent}.csv", tag)
    sweep_path = _with_tag(EXPERIMENTS_DIR / f"cppb_reconstructed_policy_sweep_{safe_agent}.csv", tag)
    latency_path = _with_tag(EXPERIMENTS_DIR / f"cppb_reconstructed_latency_{safe_agent}.csv", tag)
    manifest_path = _with_tag(EXPERIMENTS_DIR / f"cppb_reconstructed_runtime_manifest_{safe_agent}.csv", tag)

    base = args.base_url.rstrip("/")
    agent = CachedOllamaChat(args.agent_model, base_url=base, num_ctx=AGENT_NUM_CTX)
    judge = CachedOllamaChat(args.judge_model, base_url=base, num_ctx=JUDGE_NUM_CTX)

    roster = [k.strip() for k in args.methods.split(",") if k.strip()]
    needs_sanitizer = "proposed_abstraction" in roster
    sanitizer = None
    if needs_sanitizer:
        template = ABSTRACTION_TEMPLATE if ABSTRACTION_TEMPLATE.exists() else None
        kwargs = {"template_path": template} if template else {}
        sanitizer = LLMSanitizer(args.sanitizer_model, ollama_url=f"{base}/api/generate", **kwargs)

    detector_keys = []
    if "regex_only" in roster:
        detector_keys.append("regex_only")
    if "capitalization_heuristic" in roster:
        detector_keys.append("capitalization_heuristic")
    if "enterprise_staged" in roster:
        detector_keys.append("presidio")
    detectors = {d.key: d for d in build_detectors(detector_keys, spacy_model=args.spacy_model,
                                                   ollama_url=f"{base}/api/generate")} if detector_keys else {}

    weights: dict[str, float] = {}
    if "proposed_utility_constrained" in roster or args.sweep:
        print("[setup] training the learned span detector ...", flush=True)
        import propagation_suite

        weights = propagation_suite._train_learned_detector()

    mediators = build_mediators(roster, tau=args.tau, weights=weights,
                                detectors=detectors, sanitizer=sanitizer)
    sweep_jobs: list[tuple[str, float]] = []
    if args.sweep:
        sweep_jobs = [("policy_sweep", t) for t in SWEEP_TAUS]

    done = _read_done(rows_path)
    new_file = not rows_path.exists()
    handle = rows_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
    if new_file:
        writer.writeheader()
        handle.flush()
        os.fsync(handle.fileno())

    # The raw answer is the reference for answer consistency, so it is produced
    # once per prompt and reused by every mediated condition.
    raw_answers: dict[str, str] = {}
    print(f"[run] {len(records)} prompts x {len(mediators)} methods"
          f"{f' + {len(sweep_jobs)} sweep points' if sweep_jobs else ''}", flush=True)

    jobs: list[tuple[str, str, float, Callable[[str], str], dict[str, str]]] = []
    for med in mediators:
        jobs.append((med.key, med.label, args.tau if med.key == "proposed_utility_constrained" else float("nan"),
                     med, med.versions))
    for _, tau in sweep_jobs:
        jobs.append(("policy_sweep", f"Policy sweep tau={tau:.2f}", tau,
                     Mediator("policy_sweep", f"tau={tau:.2f}",
                              lambda t, tt=tau: render_generic_typed(t, weights, tt)),
                     {"decision_threshold": f"{tau:.2f}"}))

    failures = 0
    for record in records:
        pid = str(record.get("prompt_id"))
        gold = _gold_texts(record)
        raw_text = str(record.get("prompt_text", ""))
        for key, _label, tau, med, _versions in jobs:
            tau_key = "" if tau != tau else f"{tau:.2f}"  # NaN check
            if (key, tau_key, pid) in done:
                continue
            start = time.perf_counter()
            try:
                released = med(raw_text)
            except Exception as exc:  # a mediator that cannot run must not lose the run
                print(f"  mediation failed {key} {pid}: {exc}", flush=True)
                failures += 1
                continue
            mediation_ms = (time.perf_counter() - start) * 1000.0

            if pid not in raw_answers:
                reply = _answer(agent, record, raw_text)
                if reply is None:
                    print(f"  agent failed on raw {pid}", flush=True)
                    failures += 1
                    continue
                raw_answers[pid] = reply
            raw_answer = raw_answers[pid]

            med_answer = raw_answer if released == raw_text else _answer(agent, record, released)
            if med_answer is None:
                print(f"  agent failed {key} {pid}", flush=True)
                failures += 1
                continue

            if released == raw_text:
                ac, ac_verdict = 1.0, "IDENTICAL"
            else:
                ac, ac_verdict = _judge_ac(judge, record, raw_answer, med_answer)
            tsr, tsr_verdict = _judge_tsr(judge, record, med_answer)
            if ac is None or tsr is None:
                print(f"  judge unparsed {key} {pid}: ac={ac_verdict!r} tsr={tsr_verdict!r}", flush=True)
                failures += 1
                continue

            writer.writerow({
                "method": key, "tau": tau_key, "prompt_id": pid,
                "template_id": record.get("template_id", ""), "variant_id": record.get("variant_id", ""),
                "split": record.get("split", ""), "privacy_category": record.get("privacy_category", ""),
                "gold_spans": len(gold), "surviving_spans": _survival(released, gold),
                "mediation_ms": f"{mediation_ms:.3f}", "ac": f"{ac:.3f}", "tsr": f"{tsr:.3f}",
                "ac_verdict": ac_verdict, "tsr_verdict": tsr_verdict,
                "agent_model": agent.model, "judge_model": judge.model,
            })
            handle.flush()
            os.fsync(handle.fileno())
        print(f"[{pid}] done", flush=True)

    handle.close()
    _summarize(rows_path, summary_path, sweep_path, latency_path, args.bootstrap)
    _write_manifest(manifest_path, args, records, agent, judge, sanitizer, detectors, roster)
    print(f"[done] rows={rows_path.name} failures={failures} "
          f"agent_generated={agent.generated} judge_generated={judge.generated}", flush=True)
    return 0


def _summarize(rows_path: Path, summary_path: Path, sweep_path: Path, latency_path: Path, n_boot: int) -> None:
    with rows_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return

    def _emit(group_rows: list[dict[str, str]]) -> dict[str, str]:
        pairs = [(float(r["surviving_spans"]), float(r["gold_spans"])) for r in group_rows]
        per, lo, hi = bootstrap_ratio_ci(pairs, n_boot=n_boot, scale=100.0)
        acs = [float(r["ac"]) for r in group_rows]
        tsrs = [float(r["tsr"]) for r in group_rows]
        return {
            "prompts": str(len(group_rows)),
            "per": f"{per:.2f}", "per_ci_low": f"{lo:.2f}", "per_ci_high": f"{hi:.2f}",
            "ac": f"{statistics.fmean(acs):.3f}", "tsr": f"{statistics.fmean(tsrs):.3f}",
        }

    methods = [r for r in rows if r["method"] != "policy_sweep"]
    by_method: dict[str, list[dict[str, str]]] = {}
    for row in methods:
        by_method.setdefault(row["method"], []).append(row)
    with summary_path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=["method", "prompts", "per", "per_ci_low", "per_ci_high", "ac", "tsr"])
        writer.writeheader()
        for key, group in by_method.items():
            writer.writerow({"method": key, **_emit(group)})
        out.flush()
        os.fsync(out.fileno())

    sweep = [r for r in rows if r["method"] == "policy_sweep"]
    if sweep:
        by_tau: dict[str, list[dict[str, str]]] = {}
        for row in sweep:
            by_tau.setdefault(row["tau"], []).append(row)
        with sweep_path.open("w", encoding="utf-8", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=["tau", "prompts", "per", "per_ci_low", "per_ci_high", "ac", "tsr"])
            writer.writeheader()
            for tau in sorted(by_tau, key=float):
                writer.writerow({"tau": tau, **_emit(by_tau[tau])})
            out.flush()
            os.fsync(out.fileno())

    with latency_path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=["method", "prompts", "mean_ms", "p95_ms"])
        writer.writeheader()
        for key, group in by_method.items():
            values = [float(r["mediation_ms"]) for r in group]
            writer.writerow({"method": key, "prompts": str(len(values)),
                             "mean_ms": f"{statistics.fmean(values):.1f}",
                             "p95_ms": f"{_percentile(values, 95):.1f}"})
        out.flush()
        os.fsync(out.fileno())


def _write_manifest(path: Path, args: argparse.Namespace, records: list[dict], agent: CachedOllamaChat,
                    judge: CachedOllamaChat, sanitizer: LLMSanitizer | None,
                    detectors: dict[str, Detector], roster: list[str]) -> None:
    fields: list[tuple[str, str]] = [
        ("surface", "CPPB reconstructed prompt surface (data/cppb_full_annotations.jsonl); "
                    "reconstructed from the public stub manifest, not historical raw-prompt recovery"),
        ("prompts", str(len(records))),
        ("methods", ";".join(roster)),
        ("policy_sweep", ";".join(f"{t:.2f}" for t in SWEEP_TAUS) if args.sweep else "not run"),
        ("tau_utility_constrained", f"{args.tau:.2f}"),
        ("per_definition", "gold sensitive spans literally present in the released prompt / all gold spans; "
                           "a lower bound on disclosure, not a measure of inferability"),
        ("ac_definition", "judge-scored task-relevant agreement between the raw-prompt and mediated-prompt "
                          "answers (AGREE=1, PARTIAL=0.5, DISAGREE=0)"),
        ("tsr_definition", "judge-scored satisfaction of the template's stated success criteria (SUCCESS=1, FAIL=0)"),
        ("latency_definition", "mediation wall-clock per prompt, CPU only, excluding model generation"),
        ("decoding", f"temperature 0, top_p 1, seed {SEED}; agent num_predict {AGENT_NUM_PREDICT}, "
                     f"judge num_predict {JUDGE_NUM_PREDICT}"),
        ("context", f"agent num_ctx {AGENT_NUM_CTX}, judge num_ctx {JUDGE_NUM_CTX}"),
        ("bootstrap", f"{args.bootstrap} span-level resamples, 95% percentile CI"),
        ("python", platform.python_version()),
        ("platform", platform.platform()),
        ("host", platform.node()),
        ("run_started_utc", datetime.now(timezone.utc).isoformat()),
    ]
    for prefix, meta in (("agent", agent.metadata()), ("judge", judge.metadata())):
        for key, value in meta.items():
            fields.append((f"{prefix}.{key}", str(value)))
    if sanitizer is not None:
        for key, value in sanitizer.metadata().items():
            fields.append((f"abstraction.{key}", str(value)))
    for det in detectors.values():
        for key, value in det.versions.items():
            fields.append((f"{det.key}.{key}", str(value)))
    try:
        from importlib.metadata import version

        fields.append(("scikit_learn", version("scikit-learn")))
    except Exception:
        pass

    with path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["field", "value"])
        writer.writerows(fields)
        out.flush()
        os.fsync(out.fileno())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--agent-model", default=DEFAULT_AGENT)
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE)
    parser.add_argument("--sanitizer-model", default=DEFAULT_SANITIZER)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--spacy-model", default="en_core_web_lg")
    parser.add_argument("--methods", default="no_protection,regex_only,capitalization_heuristic,"
                                             "generic_deid,enterprise_staged,proposed_abstraction,"
                                             "proposed_utility_constrained")
    parser.add_argument("--tau", type=float, default=DEFAULT_TAU)
    parser.add_argument("--sweep", action="store_true", help="Also measure every policy threshold as a real operating point")
    parser.add_argument("--max-prompts", type=int)
    parser.add_argument("--shard", help="I/N: run only every N-th prompt (outputs get a shard tag)")
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--output-tag")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
