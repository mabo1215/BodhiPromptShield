#!/usr/bin/env python3
"""Adversarial-feedback LLM anonymizer, after Staab et al. (2025).

The one-shot LLM sanitizer asks a model once to rewrite a text without its
sensitive content. Staab et al. ("Large Language Models are Advanced
Anonymizers", ICLR 2025) show that an anonymizer guided by an adversary is much
stronger: an adversary model reads the current text and states what it can
infer about the people in it, with the evidence; the anonymizer rewrites the
text to remove exactly those cues, changing as little as possible; and the loop
repeats on the rewrite. This module implements that loop for the PrivacyLens
releases, as a comparator for the mediation layer.

Per text, for up to ``rounds`` rounds:

1. the adversary lists every personal or sensitive item a reader can learn or
   confidently infer about any person in the text, one per line with its
   evidence, or replies NONE;
2. if it replied NONE the loop stops; otherwise the anonymizer rewrites the
   text so that none of the listed items can be inferred, generalizing or
   removing only the parts that reveal them.

The anonymizer and the adversary are the same model, which runs on raw text and
so sits inside the trusted computing base, like the one-shot sanitizer. Every
call goes through the durable completion cache, so an interrupted run replays
without regenerating, and the per-text history (each round's inferences and
rewrite) is recorded for the released records.
"""
from __future__ import annotations

import re
from pathlib import Path

from ollama_client import DEFAULT_BASE_URL, DEFAULT_CACHE_DIR, CachedOllamaChat


ADVERSARY_SYSTEM = (
    "You are an expert investigator. Given a text, determine what personal or sensitive information a reader "
    "can learn or confidently infer about any person mentioned in it: identity (names, contact details, "
    "account or ID numbers, addresses), health, finances, relationships, family, location, occupation, beliefs, "
    "legal matters, and any other private fact."
)
ADVERSARY_INSTRUCTION = (
    "List each item a reader can learn or infer on its own line, in the form: <information> | <evidence quoted "
    "from the text>. List only what the text supports. If nothing personal or sensitive can be inferred, reply "
    "NONE."
)
ANONYMIZER_SYSTEM = (
    "You are an expert anonymizer. You edit a text so that the personal or sensitive information an adversary "
    "inferred from it can no longer be inferred, while keeping the text useful for the task it serves. You "
    "change as little as possible."
)
ANONYMIZER_INSTRUCTION = (
    "Rewrite the text so that none of the inferred items above can be learned or inferred from it. Generalize or "
    "remove only the parts that reveal them, and keep everything else unchanged, including formatting, structure "
    "and tool-call syntax. Reply with the rewritten text only."
)
NONE_RE = re.compile(r"^\s*none\.?\s*$", re.I)


class AnonymizationFailed(RuntimeError):
    pass


def _strip(reply: str) -> str:
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.S).strip()
    if reply.startswith("```") and reply.endswith("```"):
        reply = reply.strip("`").split("\n", 1)[-1].rstrip("`").strip()
    return reply


class IterativeAnonymizer:
    def __init__(self, model: str, base_url: str = DEFAULT_BASE_URL, cache_dir: Path = DEFAULT_CACHE_DIR,
                 rounds: int = 3, num_ctx: int = 16384) -> None:
        self.model = model
        self.rounds = rounds
        self.chat = CachedOllamaChat(model, base_url=base_url, cache_dir=cache_dir, num_ctx=num_ctx)
        self.history: dict[str, list[dict[str, str]]] = {}

    def _call(self, system: str, user: str, num_predict: int) -> str:
        reply = self.chat.chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                               num_predict=num_predict)
        if reply is None:
            raise AnonymizationFailed(f"{self.model}: generation failed")
        return _strip(reply)

    def anonymize(self, text: str) -> str:
        """The text after up to ``rounds`` adversary/anonymizer rounds; the history is kept per input text."""
        if not text.strip():
            return text
        current = text
        history: list[dict[str, str]] = []
        # Output budget scales with the input so a long trajectory is never truncated mid-rewrite.
        budget = max(512, int(len(text) / 4 * 1.5))
        for _ in range(self.rounds):
            inferred = self._call(ADVERSARY_SYSTEM, f"Text:\n{current}\n\n{ADVERSARY_INSTRUCTION}", 1024)
            if not inferred or NONE_RE.match(inferred):
                history.append({"inferred": "NONE", "rewrite": ""})
                break
            rewrite = self._call(
                ANONYMIZER_SYSTEM,
                f"Text:\n{current}\n\nAn adversary inferred the following from this text:\n{inferred}\n\n"
                f"{ANONYMIZER_INSTRUCTION}", budget)
            if not rewrite:
                raise AnonymizationFailed(f"{self.model}: empty rewrite")
            history.append({"inferred": inferred, "rewrite": rewrite})
            current = rewrite
        self.history[text] = history
        return current

    def metadata(self) -> dict[str, str]:
        meta = self.chat.metadata()
        meta.update({"rounds": str(self.rounds), "num_ctx": str(self.chat.num_ctx)})
        return meta
