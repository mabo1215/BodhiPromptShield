#!/usr/bin/env python3
"""Minimal Ollama chat client with a durable, append-only generation cache.

Every completed generation is written to a JSONL cache keyed by the SHA-256 of
(model, messages, options), flushed and fsync'd immediately, so an interrupted
experiment resumes without repeating any finished model call and a rerun with
the same inputs is free.  Failures are retried with backoff and then reported
as ``None`` so callers can record them rather than crash a long run.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_CACHE_DIR = EXPERIMENTS_DIR / "ollama_cache"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
# Context sizes are measured rather than guessed. Over the 200-case
# PrivacyLens subset the longest agent prompt is 5,116 tokens (plus 700
# generated) and the longest judge prompt is 8,051 (plus 400); the judge, not
# the agent, is the binding constraint. Sizing each model to what it needs
# frees KV cache on the 80-layer agent, and KV cache is what limits how many
# cases can be evaluated concurrently on one card.
DEFAULT_NUM_CTX = 12288
AGENT_NUM_CTX = 7168   # 5,816 needed, 23% headroom
JUDGE_NUM_CTX = 10240  # 8,451 needed, 21% headroom
FIXED_NUM_CTX = DEFAULT_NUM_CTX  # retained for callers that predate per-model sizing


class CachedOllamaChat:
    def __init__(self, model: str, base_url: str = DEFAULT_BASE_URL, cache_dir: Path = DEFAULT_CACHE_DIR,
                 think: bool = False, retries: int = 3, timeout: int = 900,
                 num_ctx: int = DEFAULT_NUM_CTX, cache_only: bool = False) -> None:
        self.model = model
        # A replay that must not generate: a miss returns None (reported as a
        # failure) instead of loading the model, which on a shared card could
        # evict another tenant or spill to CPU.
        self.cache_only = cache_only
        # One value per client instance: Ollama sizes a model's KV cache from
        # the context of the request that loads it, and a later request with a
        # different context forces a reload of the whole model.
        self.num_ctx = num_ctx
        self.base_url = base_url.rstrip("/")
        self.think = think
        self.retries = retries
        self.timeout = timeout
        cache_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", model)
        self.cache_path = cache_dir / f"chat__{safe}.jsonl"
        self.cache: dict[str, str] = {}
        if self.cache_path.exists():
            with self.cache_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        row = json.loads(line)
                        self.cache[row["key"]] = row["response"]
        self.generated = 0
        self.failures = 0

    def _key(self, messages: list[dict[str, str]], options: dict[str, Any]) -> str:
        blob = json.dumps({"model": self.model, "messages": messages, "options": options, "think": self.think},
                          sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.0, num_predict: int = 512,
             num_ctx: int | None = None, seed: int = 17) -> str | None:
        # Fixed per instance, never per call: a differing value would force
        # Ollama to reload the model between requests.
        options = {"temperature": temperature, "top_p": 1, "num_predict": num_predict,
                   "num_ctx": num_ctx or self.num_ctx, "seed": seed}
        key = self._key(messages, options)
        if key in self.cache:
            return self.cache[key]
        if self.cache_only:
            self.failures += 1
            return None
        payload = json.dumps({"model": self.model, "messages": messages, "stream": False, "think": self.think,
                              "options": options, "keep_alive": "30m"}).encode("utf-8")
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                request = urllib.request.Request(f"{self.base_url}/api/chat", data=payload,
                                                 headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                text = str(body.get("message", {}).get("content", ""))
                self.generated += 1
                self.cache[key] = text
                with self.cache_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"key": key, "model": self.model, "response": text}, ensure_ascii=False) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                return text
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = exc
                time.sleep(2 ** attempt)
        self.failures += 1
        print(f"[ollama_client] {self.model}: generation failed after {self.retries} attempts: {last}")
        return None

    def metadata(self) -> dict[str, str]:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError):
            return {"model_name": self.model, "model_digest": ""}
        for row in payload.get("models", []):
            if str(row.get("name")) == self.model:
                details = row.get("details", {}) or {}
                return {"model_name": self.model, "model_digest": str(row.get("digest", "")),
                        "model_family": str(details.get("family", "")),
                        "model_parameter_size": str(details.get("parameter_size", "")),
                        "model_quantization": str(details.get("quantization_level", ""))}
        return {"model_name": self.model, "model_digest": ""}
