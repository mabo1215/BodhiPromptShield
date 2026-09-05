#!/usr/bin/env python3
"""Shared registry of mediation and detection methods for propagation experiments.

Every method maps a text to the list of half-open character spans ``(start, end)``
that the method would protect.  Methods are grouped by family:

* ``no_protection``            -- raw text released unchanged;
* ``regex_only``               -- structured identifier patterns only;
* ``capitalization_heuristic`` -- the capitalization/title/location regular
  expressions previously labelled "NER-only masking" (it is not a recognizer);
* ``spacy_ner``                -- a real statistical NER (spaCy) over PII-bearing
  entity labels;
* ``presidio``                 -- Microsoft Presidio, installed and version-pinned;
* ``casper_style``             -- Casper-like sanitization: structured rules plus
  NER, with typed dummy-value substitution and a local restoration map;
* ``heuristic_mediator``       -- the released rule-based BodhiPromptShield detector;
* ``learned_lr``               -- the lightweight logistic-regression span detector;
* ``gliner_pii``               -- a transformer PII detector (GLiNER-PII);
* ``llm_sanitizer:<model>``    -- an instruction-following LLM asked to rewrite
  the text without PII (served by Ollama); the protected spans are recovered
  by diffing the rewrite against the original, and every generation is cached
  so that reruns are free and interruptions lose nothing.

Heavy dependencies (spaCy, Presidio, GLiNER, an Ollama server) are imported or
contacted lazily, so any subset of methods can run in an environment that has
only that subset installed.  ``bootstrap_ratio_ci`` provides document-level
bootstrap confidence intervals for ratio-of-sums metrics such as PER and SPE.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ai4privacy_matched_baseline_suite import _merge_spans
from ai4privacy_matched_baseline_suite import _ner_like_spans
from ai4privacy_matched_baseline_suite import _policy_aware_spans
from ai4privacy_matched_baseline_suite import _regex_spans


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_CACHE_DIR = EXPERIMENTS_DIR / "llm_sanitizer_cache"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
LLM_PROMPT_TEMPLATE_PATH = EXPERIMENTS_DIR / "ai4privacy_zero_shot_prompt_template.txt"

# spaCy entity labels treated as privacy-bearing (Presidio's default mapping plus
# organizations and dates, which the CPPB categories also protect).
SPACY_PII_LABELS = {"PERSON", "ORG", "GPE", "LOC", "FAC", "NORP", "DATE", "TIME"}
PRESIDIO_SCORE_THRESHOLD = 0.35
GLINER_MODEL_ID = "urchade/gliner_multi_pii-v1"
GLINER_LABELS = [
    "person", "organization", "address", "phone number", "email", "date of birth",
    "passport number", "credit card number", "social security number", "bank account number",
    "driver licence number", "username", "medical condition", "date", "identifier",
]
GLINER_THRESHOLD = 0.5
GLINER_CHUNK_CHARS = 1200

# Typed dummy values for Casper-style substitution (Chong et al., 2024 replace
# detected PII with plausible stand-ins and keep a local map for restoration).
DUMMY_VALUES = {
    "PERSON": "Alex Morgan",
    "ORG": "Northwind Ltd",
    "GPE": "Springfield",
    "LOC": "Riverside",
    "FAC": "Central Plaza",
    "NORP": "the community",
    "DATE": "12 March 2001",
    "TIME": "10:30",
    "EMAIL": "user@example.com",
    "PHONE": "555-0100",
    "STRUCTURED": "ID-000000",
}

METHOD_ORDER = [
    "no_protection",
    "regex_only",
    "capitalization_heuristic",
    "spacy_ner",
    "presidio",
    "casper_style",
    "heuristic_mediator",
    "learned_lr",
    "gliner_pii",
]

PAPER_LABELS = {
    "no_protection": "No protection",
    "regex_only": "Regex-only",
    "capitalization_heuristic": "Capitalization heuristic (formerly NER-only)",
    "spacy_ner": "spaCy NER masking",
    "presidio": "Microsoft Presidio",
    "casper_style": "Casper-style (rules + NER, dummy values)",
    "heuristic_mediator": "Proposed (released heuristic detector)",
    "learned_lr": "Proposed (learned detector)",
    "gliner_pii": "Proposed (transformer PII detector)",
}

Span = tuple[int, int]
TypedSpan = tuple[int, int, str]


@dataclass
class Detector:
    """A named span detector; ``typed`` additionally returns entity labels."""

    key: str
    label: str
    typed: Callable[[str], list[TypedSpan]]
    versions: dict[str, str] = field(default_factory=dict)

    def __call__(self, text: str) -> list[Span]:
        return _merge_spans([(s, e) for s, e, _ in self.typed(text)])


def _untyped(fn: Callable[[str], list[Span]], label: str = "SPAN") -> Callable[[str], list[TypedSpan]]:
    return lambda text: [(s, e, label) for s, e in _merge_spans(fn(text))]


def _regex_typed(text: str) -> list[TypedSpan]:
    from ai4privacy_matched_baseline_suite import EMAIL_PATTERN, PHONE_PATTERN

    typed: list[TypedSpan] = []
    emails = [(m.start(), m.end()) for m in EMAIL_PATTERN.finditer(text)]
    phones = [(m.start(), m.end()) for m in PHONE_PATTERN.finditer(text)]
    typed.extend((s, e, "EMAIL") for s, e in emails)
    typed.extend((s, e, "PHONE") for s, e in phones)
    covered = set()
    for s, e in emails + phones:
        covered.update(range(s, e))
    for s, e in _merge_spans(_regex_spans(text)):
        if not any(i in covered for i in range(s, e)):
            typed.append((s, e, "STRUCTURED"))
    return sorted(typed)


# ---------------------------------------------------------------------------
# Real NER and industrial baselines (lazy imports).
# ---------------------------------------------------------------------------

_SPACY_CACHE: dict[str, Any] = {}


def _load_spacy(model_name: str):
    if model_name not in _SPACY_CACHE:
        import spacy

        _SPACY_CACHE[model_name] = spacy.load(model_name, disable=["lemmatizer", "textcat"])
    return _SPACY_CACHE[model_name]


def _spacy_typed_factory(model_name: str) -> Callable[[str], list[TypedSpan]]:
    nlp = _load_spacy(model_name)

    def detect(text: str) -> list[TypedSpan]:
        return [
            (ent.start_char, ent.end_char, ent.label_)
            for ent in nlp(text).ents
            if ent.label_ in SPACY_PII_LABELS
        ]

    return detect


def _presidio_typed_factory(model_name: str) -> tuple[Callable[[str], list[TypedSpan]], dict[str, str]]:
    from importlib.metadata import version

    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    provider = NlpEngineProvider(
        nlp_configuration={"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": model_name}]}
    )
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])

    def detect(text: str) -> list[TypedSpan]:
        results = analyzer.analyze(text=text, language="en", score_threshold=PRESIDIO_SCORE_THRESHOLD)
        return [(r.start, r.end, r.entity_type) for r in results]

    versions = {"presidio_analyzer": version("presidio-analyzer"), "spacy": version("spacy"), "spacy_model": model_name}
    return detect, versions


def _casper_typed_factory(model_name: str) -> Callable[[str], list[TypedSpan]]:
    spacy_detect = _spacy_typed_factory(model_name)

    def detect(text: str) -> list[TypedSpan]:
        return sorted(_regex_typed(text) + spacy_detect(text))

    return detect


def substitute_dummy(text: str, typed_spans: list[TypedSpan]) -> tuple[str, dict[str, str]]:
    """Casper-style release: replace spans with typed dummy values, keep a local map."""
    out: list[str] = []
    cursor = 0
    restoration: dict[str, str] = {}
    for start, end, label in sorted(_dedupe_typed(typed_spans)):
        if start < cursor:
            continue
        dummy = DUMMY_VALUES.get(label, DUMMY_VALUES["STRUCTURED"])
        out.append(text[cursor:start])
        out.append(dummy)
        restoration.setdefault(dummy, text[start:end])
        cursor = end
    out.append(text[cursor:])
    return "".join(out), restoration


def _dedupe_typed(typed_spans: list[TypedSpan]) -> list[TypedSpan]:
    merged: list[TypedSpan] = []
    for start, end, label in sorted(typed_spans):
        if merged and start < merged[-1][1]:
            prev = merged[-1]
            merged[-1] = (prev[0], max(prev[1], end), prev[2])
        else:
            merged.append((start, end, label))
    return merged


# ---------------------------------------------------------------------------
# Transformer PII detector (GLiNER), chunked for long inputs.
# ---------------------------------------------------------------------------


def _gliner_typed_factory(model_id: str = GLINER_MODEL_ID) -> tuple[Callable[[str], list[TypedSpan]], dict[str, str]]:
    from importlib.metadata import version

    from gliner import GLiNER

    model = GLiNER.from_pretrained(model_id)

    def detect(text: str) -> list[TypedSpan]:
        typed: list[TypedSpan] = []
        for offset, chunk in _chunks(text, GLINER_CHUNK_CHARS):
            for ent in model.predict_entities(chunk, GLINER_LABELS, threshold=GLINER_THRESHOLD):
                typed.append((offset + int(ent["start"]), offset + int(ent["end"]), str(ent["label"]).upper()))
        return sorted(typed)

    return detect, {"gliner": version("gliner"), "gliner_model": model_id}


def _chunks(text: str, size: int) -> list[tuple[int, str]]:
    """Split on paragraph/sentence boundaries into chunks of at most ``size`` chars."""
    pieces: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if cut > start + size // 2:
                end = cut + 1
        pieces.append((start, text[start:end]))
        start = end
    return pieces


# ---------------------------------------------------------------------------
# LLM sanitizer via Ollama with a durable generation cache.
# ---------------------------------------------------------------------------


class LLMSanitizer:
    """Rewrite text without PII using an Ollama-served model; spans come from the diff.

    Generations are cached in an append-only JSONL keyed by the SHA-256 of
    (model, prompt template, text); each record is flushed and fsync'd so an
    interrupted run resumes without repeating any completed generation.
    """

    def __init__(self, model: str, ollama_url: str = DEFAULT_OLLAMA_URL, cache_dir: Path = DEFAULT_CACHE_DIR,
                 num_predict: int = 2048, num_ctx: int = 8192, retries: int = 3) -> None:
        self.model = model
        self.ollama_url = ollama_url
        self.template = LLM_PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
        self.template_hash = hashlib.sha256(self.template.encode("utf-8")).hexdigest()[:12]
        self.options = {"temperature": 0, "top_p": 1, "num_predict": num_predict, "num_ctx": num_ctx, "seed": 17}
        self.retries = retries
        cache_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", model)
        self.cache_path = cache_dir / f"{safe}__{self.template_hash}.jsonl"
        self.cache: dict[str, str] = {}
        if self.cache_path.exists():
            with self.cache_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        row = json.loads(line)
                        self.cache[row["key"]] = row["sanitized"]
        self.failures = 0
        self.generated = 0

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model}\n{self.template_hash}\n{text}".encode("utf-8")).hexdigest()

    def sanitize(self, text: str) -> str:
        key = self._key(text)
        if key in self.cache:
            return self.cache[key]
        prompt = self.template.replace("{{NOTE_TEXT}}", text)
        sanitized = self._generate(prompt)
        if sanitized is None:
            self.failures += 1
            return text
        self.generated += 1
        self.cache[key] = sanitized
        with self.cache_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"key": key, "model": self.model, "sanitized": sanitized}, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return sanitized

    def _generate(self, prompt: str) -> str | None:
        payload = json.dumps(
            {"model": self.model, "prompt": prompt, "stream": False, "think": False, "options": self.options,
             "keep_alive": "30m"}
        ).encode("utf-8")
        for attempt in range(self.retries):
            try:
                request = urllib.request.Request(self.ollama_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(request, timeout=900) as response:
                    body = json.loads(response.read().decode("utf-8"))
                return _strip_wrapping(str(body.get("response", "")))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                time.sleep(2 ** attempt)
                last = exc
        print(f"[llm_sanitizer] generation failed for {self.model}: {last}")
        return None

    def typed(self, text: str) -> list[TypedSpan]:
        sanitized = self.sanitize(text)
        return [(s, e, "LLM") for s, e in changed_spans(text, sanitized)]

    def metadata(self) -> dict[str, str]:
        tags_url = self.ollama_url.rsplit("/api/", 1)[0] + "/api/tags"
        try:
            with urllib.request.urlopen(tags_url, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError):
            return {"model_name": self.model, "model_digest": ""}
        for row in payload.get("models", []):
            if str(row.get("name")) == self.model:
                details = row.get("details", {}) or {}
                return {
                    "model_name": self.model,
                    "model_digest": str(row.get("digest", "")),
                    "model_family": str(details.get("family", "")),
                    "model_parameter_size": str(details.get("parameter_size", "")),
                    "model_quantization": str(details.get("quantization_level", "")),
                }
        return {"model_name": self.model, "model_digest": ""}


def _strip_wrapping(text: str) -> str:
    """Drop chat wrappers such as think blocks or a leading 'Sanitized text:' line."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^\s*(?:sanitized|redacted|output)\s*(?:text)?\s*:\s*", "", text, flags=re.IGNORECASE)
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def changed_spans(original: str, rewritten: str) -> list[Span]:
    """Character spans of the original that the rewrite did not keep verbatim."""
    matcher = difflib.SequenceMatcher(a=original, b=rewritten, autojunk=False)
    spans = [(a0, a1) for tag, a0, a1, _, _ in matcher.get_opcodes() if tag != "equal" and a1 > a0]
    return _merge_spans(spans)


# ---------------------------------------------------------------------------
# Registry.
# ---------------------------------------------------------------------------


def build_detectors(
    keys: list[str],
    *,
    learned_weights: dict | None = None,
    spacy_model: str = "en_core_web_lg",
    ollama_url: str = DEFAULT_OLLAMA_URL,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> list[Detector]:
    """Instantiate detectors for the requested keys (``llm_sanitizer:<model>`` allowed)."""
    detectors: list[Detector] = []
    for key in keys:
        if key == "no_protection":
            detectors.append(Detector(key, PAPER_LABELS[key], lambda t: []))
        elif key == "regex_only":
            detectors.append(Detector(key, PAPER_LABELS[key], _regex_typed))
        elif key == "capitalization_heuristic":
            detectors.append(Detector(key, PAPER_LABELS[key], _untyped(_ner_like_spans, "CAPITALIZED")))
        elif key == "spacy_ner":
            from importlib.metadata import version

            detectors.append(Detector(key, PAPER_LABELS[key], _spacy_typed_factory(spacy_model),
                                      {"spacy": version("spacy"), "spacy_model": spacy_model}))
        elif key == "presidio":
            fn, versions = _presidio_typed_factory(spacy_model)
            detectors.append(Detector(key, PAPER_LABELS[key], fn, versions))
        elif key == "casper_style":
            detectors.append(Detector(key, PAPER_LABELS[key], _casper_typed_factory(spacy_model), {"spacy_model": spacy_model}))
        elif key == "heuristic_mediator":
            detectors.append(Detector(key, PAPER_LABELS[key], _untyped(_policy_aware_spans, "HEURISTIC")))
        elif key == "learned_lr":
            if learned_weights is None:
                raise ValueError("learned_lr requires learned_weights")
            import ai4privacy_lightweight_classifier_baseline as clf

            weights = learned_weights
            detectors.append(Detector(key, PAPER_LABELS[key], _untyped(lambda t: clf._predict_spans(weights, t), "LEARNED")))
        elif key == "gliner_pii":
            fn, versions = _gliner_typed_factory()
            detectors.append(Detector(key, PAPER_LABELS[key], fn, versions))
        elif key.startswith("llm_sanitizer:"):
            model = key.split(":", 1)[1]
            sanitizer = LLMSanitizer(model, ollama_url=ollama_url, cache_dir=cache_dir)
            detectors.append(Detector(key, f"LLM sanitizer ({model})", sanitizer.typed, sanitizer.metadata()))
        else:
            raise ValueError(f"Unknown method key: {key}")
    return detectors


# ---------------------------------------------------------------------------
# Document-level bootstrap for ratio-of-sums metrics.
# ---------------------------------------------------------------------------


def bootstrap_ratio_ci(pairs: list[tuple[float, float]], n_boot: int = 1000, seed: int = 17, scale: float = 1.0) -> tuple[float, float, float]:
    """Point estimate and percentile 95% CI of sum(num)/sum(den) under document resampling."""
    if not pairs:
        return 0.0, 0.0, 0.0
    num = sum(p[0] for p in pairs)
    den = sum(p[1] for p in pairs)
    point = scale * num / den if den else 0.0
    rng = random.Random(seed)
    n = len(pairs)
    samples: list[float] = []
    for _ in range(n_boot):
        s_num = s_den = 0.0
        for _ in range(n):
            a, b = pairs[rng.randrange(n)]
            s_num += a
            s_den += b
        samples.append(scale * s_num / s_den if s_den else 0.0)
    samples.sort()
    lo = samples[int(0.025 * (n_boot - 1))]
    hi = samples[int(0.975 * (n_boot - 1))]
    return point, lo, hi
