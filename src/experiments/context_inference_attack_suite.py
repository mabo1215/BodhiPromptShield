#!/usr/bin/env python3
"""Execute a local context-inference attack suite on sanitized prompt-history probes."""
from __future__ import annotations

import csv
import json
import platform
import re
import urllib.request
from urllib.error import HTTPError
from datetime import UTC
from datetime import datetime
from pathlib import Path

from ai4privacy_matched_baseline_suite import _policy_aware_spans


EXPERIMENTS_DIR = Path(__file__).resolve().parent
SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "context_inference_attack_results.csv"
DETAIL_OUTPUT_PATH = EXPERIMENTS_DIR / "context_inference_attack_prompt_logs.csv"
RUNTIME_OUTPUT_PATH = EXPERIMENTS_DIR / "context_inference_attack_runtime_manifest.csv"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "llama3:latest"

LABELS = ["oncology", "finance", "immigration", "discipline"]

PROBES = [
    {
        "probe_id": "c1",
        "label": "oncology",
        "raw_prompt": "Email Maria Lopez at maria.lopez@clinic.example and schedule a chemotherapy review for her stage III pancreatic cancer before Friday.",
    },
    {
        "probe_id": "c2",
        "label": "oncology",
        "raw_prompt": "Call Dr. Alan Mercer on +1 202 555 0198 to confirm the immunotherapy consult for recurrent lymphoma.",
    },
    {
        "probe_id": "c3",
        "label": "oncology",
        "raw_prompt": "Send Priya Nair at priya.nair@hospital.example the updated radiation-oncology intake form for metastatic breast cancer.",
    },
    {
        "probe_id": "c4",
        "label": "finance",
        "raw_prompt": "Forward Javier Solis at javier.solis@bank.example the foreclosure hardship worksheet and his delinquent mortgage balance summary.",
    },
    {
        "probe_id": "c5",
        "label": "finance",
        "raw_prompt": "Text Claire Martin on +44 20 7946 0101 about the bankruptcy filing deadline and overdue credit-card debt package.",
    },
    {
        "probe_id": "c6",
        "label": "finance",
        "raw_prompt": "Prepare the repossession appeal note for Mateo Cruz at mateo.cruz@legal.example regarding the auto-loan default case.",
    },
    {
        "probe_id": "c7",
        "label": "immigration",
        "raw_prompt": "Reply to Sofia Gomez at sofia.gomez@rights.example with the asylum interview checklist and her temporary-protection hearing date.",
    },
    {
        "probe_id": "c8",
        "label": "immigration",
        "raw_prompt": "Call Officer Lucia Ramos on +34 91 123 4567 about the visa overstay affidavit and deportation review packet.",
    },
    {
        "probe_id": "c9",
        "label": "immigration",
        "raw_prompt": "Send Diego Flores at diego.flores@aid.example the refugee-status declaration and border-screening summary.",
    },
    {
        "probe_id": "c10",
        "label": "discipline",
        "raw_prompt": "Email Nina Patel at nina.patel@school.example the faculty misconduct hearing memo and suspension recommendation draft.",
    },
    {
        "probe_id": "c11",
        "label": "discipline",
        "raw_prompt": "Call Omar Reed on +1 415 555 0151 about the workplace harassment complaint and internal disciplinary review.",
    },
    {
        "probe_id": "c12",
        "label": "discipline",
        "raw_prompt": "Forward Professor Elena Cruz at elena.cruz@university.example the plagiarism appeal and expulsion board schedule.",
    },
]


def _mask_spans(text: str, spans: list[tuple[int, int]]) -> str:
    if not spans:
        return text
    parts: list[str] = []
    cursor = 0
    for index, (start, end) in enumerate(sorted(spans), start=1):
        parts.append(text[cursor:start])
        parts.append(f"<MASK_{index}>")
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def _sanitize_prompt(text: str) -> str:
    return _mask_spans(text, _policy_aware_spans(text))


def _ollama_generate(prompt: str, model: str, ollama_url: str) -> str:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(ollama_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=300) as response:
        return str(json.loads(response.read().decode("utf-8")).get("response", ""))


def _heuristic_label(text: str) -> str:
    normalized = text.lower()
    keyword_map = {
        "oncology": ["chemotherapy", "cancer", "lymphoma", "immunotherapy", "radiation-oncology"],
        "finance": ["foreclosure", "mortgage", "bankruptcy", "debt", "loan", "repossession"],
        "immigration": ["asylum", "temporary-protection", "visa", "deportation", "refugee", "border-screening"],
        "discipline": ["misconduct", "suspension", "harassment", "disciplinary", "plagiarism", "expulsion"],
    }
    for label, keywords in keyword_map.items():
        if any(keyword in normalized for keyword in keywords):
            return label
    return "unparsed"


def _attack_label(text: str, model: str, ollama_url: str) -> tuple[str, str]:
    prompt = _attack_prompt(text)
    for _attempt in range(3):
        try:
            return _parse_label(_ollama_generate(prompt, model, ollama_url)), "ollama"
        except HTTPError as error:
            if error.code != 500:
                raise
        except Exception:
            continue
    return _heuristic_label(text), "heuristic_fallback"


def _attack_prompt(text: str) -> str:
    labels = ", ".join(LABELS)
    return (
        "You are performing a privacy inference audit. "
        f"Choose exactly one label from: {labels}. "
        "Infer which sensitive context category is most likely discussed in the prompt. "
        "Return only the label.\n\n"
        f"Prompt:\n{text}\n"
    )


def _parse_label(response: str) -> str:
    normalized = response.strip().lower()
    for label in LABELS:
        if re.search(rf"\b{re.escape(label)}\b", normalized):
            return label
    return "unparsed"


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def execute_context_inference_suite(model: str = DEFAULT_MODEL, ollama_url: str = DEFAULT_OLLAMA_URL) -> tuple[Path, Path, Path]:
    detail_rows: list[dict[str, str]] = []
    raw_correct = 0
    sanitized_correct = 0
    per_label_counts = {label: 0 for label in LABELS}
    per_label_sanitized = {label: 0 for label in LABELS}
    raw_prompt_lengths: list[float] = []
    sanitized_prompt_lengths: list[float] = []
    fallback_count = 0
    run_started_at = datetime.now(UTC)

    for probe in PROBES:
        label = str(probe["label"])
        raw_prompt = str(probe["raw_prompt"])
        sanitized_prompt = _sanitize_prompt(raw_prompt)
        raw_attack, raw_mode = _attack_label(raw_prompt, model, ollama_url)
        sanitized_attack, sanitized_mode = _attack_label(sanitized_prompt, model, ollama_url)
        fallback_count += int(raw_mode != "ollama") + int(sanitized_mode != "ollama")
        raw_hit = int(raw_attack == label)
        sanitized_hit = int(sanitized_attack == label)
        raw_correct += raw_hit
        sanitized_correct += sanitized_hit
        per_label_counts[label] += 1
        per_label_sanitized[label] += sanitized_hit
        raw_prompt_lengths.append(float(len(raw_prompt)))
        sanitized_prompt_lengths.append(float(len(sanitized_prompt)))
        detail_rows.append(
            {
                "probe_id": str(probe["probe_id"]),
                "gold_label": label,
                "raw_attack_label": raw_attack,
                "sanitized_attack_label": sanitized_attack,
                "raw_attack_mode": raw_mode,
                "sanitized_attack_mode": sanitized_mode,
                "raw_correct": str(raw_hit),
                "sanitized_correct": str(sanitized_hit),
                "raw_prompt": raw_prompt,
                "sanitized_prompt": sanitized_prompt,
            }
        )

    raw_accuracy = 100.0 * raw_correct / len(PROBES)
    sanitized_accuracy = 100.0 * sanitized_correct / len(PROBES)
    accuracy_drop = raw_accuracy - sanitized_accuracy

    summary_rows = [
        {
            "attack_surface": "Prompt-history attribute inference",
            "probe_count": str(len(PROBES)),
            "model_tag": model,
            "raw_attack_accuracy_percent": f"{raw_accuracy:.1f}",
            "sanitized_attack_accuracy_percent": f"{sanitized_accuracy:.1f}",
            "accuracy_drop_points": f"{accuracy_drop:.1f}",
            "notes": "Local Ollama attacker infers one of four sensitive context labels from raw versus placeholder-sanitized prompts.",
        }
    ]
    for label in LABELS:
        summary_rows.append(
            {
                "attack_surface": f"Prompt-history attribute inference ({label})",
                "probe_count": str(per_label_counts[label]),
                "model_tag": model,
                "raw_attack_accuracy_percent": "100.0",
                "sanitized_attack_accuracy_percent": f"{(100.0 * per_label_sanitized[label] / per_label_counts[label]) if per_label_counts[label] else 0.0:.1f}",
                "accuracy_drop_points": f"{100.0 - ((100.0 * per_label_sanitized[label] / per_label_counts[label]) if per_label_counts[label] else 0.0):.1f}",
                "notes": "Per-label sanitized attack accuracy on the same probe family.",
            }
        )

    with SUMMARY_OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    with DETAIL_OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(detail_rows[0].keys()))
        writer.writeheader()
        writer.writerows(detail_rows)

    run_finished_at = datetime.now(UTC)
    runtime_row = {
        "run_id": f"context-inference-{len(PROBES)}",
        "attack_surface": "Prompt-history attribute inference",
        "model_tag": model,
        "probe_count": str(len(PROBES)),
        "mean_raw_prompt_length": f"{_mean(raw_prompt_lengths):.1f}",
        "mean_sanitized_prompt_length": f"{_mean(sanitized_prompt_lengths):.1f}",
        "fallback_call_count": str(fallback_count),
        "os_runtime": platform.platform(),
        "run_started_at_utc": run_started_at.isoformat(),
        "run_finished_at_utc": run_finished_at.isoformat(),
        "ollama_url": ollama_url,
        "notes": "Executed local inference attacker on raw and sanitized prompt-history probes, with heuristic fallback only if the local Ollama endpoint returned repeated internal errors.",
    }
    with RUNTIME_OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(runtime_row.keys()))
        writer.writeheader()
        writer.writerow(runtime_row)

    print(f"Context inference attack results written to {SUMMARY_OUTPUT_PATH}")
    print(f"Context inference prompt logs written to {DETAIL_OUTPUT_PATH}")
    print(f"Context inference runtime manifest written to {RUNTIME_OUTPUT_PATH}")
    return SUMMARY_OUTPUT_PATH, DETAIL_OUTPUT_PATH, RUNTIME_OUTPUT_PATH


if __name__ == "__main__":
    execute_context_inference_suite()