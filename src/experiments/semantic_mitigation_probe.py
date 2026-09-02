#!/usr/bin/env python3
"""Probe simple semantic-context mitigation candidates without overwriting canonicals.

This is a preparation/execution script for E3.  It uses the same four-way
context labels as ``context_inference_attack_suite.py`` and writes tagged
outputs only.  The context-abstraction and access-control variants are
explicit heuristic baselines, not a claim of semantic privacy protection.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai4privacy_matched_baseline_suite import _policy_aware_spans


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = "llama3:latest"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
LABELS = ["oncology", "finance", "immigration", "discipline"]
OUTPUT_PREFIX = "semantic_mitigation_probe"

PROBES = [
    ("c1", "oncology", "Email Maria Lopez at maria.lopez@clinic.example and schedule a chemotherapy review for her stage III pancreatic cancer before Friday."),
    ("c2", "oncology", "Call Dr. Alan Mercer on +1 202 555 0198 to confirm the immunotherapy consult for recurrent lymphoma."),
    ("c3", "oncology", "Send Priya Nair at priya.nair@hospital.example the updated radiation-oncology intake form for metastatic breast cancer."),
    ("c4", "finance", "Forward Javier Solis at javier.solis@bank.example the foreclosure hardship worksheet and his delinquent mortgage balance summary."),
    ("c5", "finance", "Text Claire Martin on +44 20 7946 0101 about the bankruptcy filing deadline and overdue credit-card debt package."),
    ("c6", "finance", "Prepare the repossession appeal note for Mateo Cruz at mateo.cruz@legal.example regarding the auto-loan default case."),
    ("c7", "immigration", "Reply to Sofia Gomez at sofia.gomez@rights.example with the asylum interview checklist and her temporary-protection hearing date."),
    ("c8", "immigration", "Call Officer Lucia Ramos on +34 91 123 4567 about the visa overstay affidavit and deportation review packet."),
    ("c9", "immigration", "Send Diego Flores at diego.flores@aid.example the refugee-status declaration and border-screening summary."),
    ("c10", "discipline", "Email Nina Patel at nina.patel@school.example the faculty misconduct hearing memo and suspension recommendation draft."),
    ("c11", "discipline", "Call Omar Reed on +1 415 555 0151 about the workplace harassment complaint and internal disciplinary review."),
    ("c12", "discipline", "Forward Professor Elena Cruz at elena.cruz@university.example the plagiarism appeal and expulsion board schedule."),
]

CONTEXT_TERMS = [
    "chemotherapy", "cancer", "lymphoma", "immunotherapy", "radiation-oncology", "pancreatic",
    "breast cancer", "foreclosure", "mortgage", "bankruptcy", "debt", "loan", "repossession",
    "asylum", "temporary-protection", "visa", "deportation", "refugee", "border-screening",
    "misconduct", "suspension", "harassment", "disciplinary", "plagiarism", "expulsion",
]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mask_spans(text: str, spans: list[tuple[int, int]]) -> str:
    parts: list[str] = []
    cursor = 0
    for index, (start, end) in enumerate(sorted(spans), start=1):
        parts.append(text[cursor:start])
        parts.append(f"<MASK_{index}>")
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def _placeholder(text: str) -> str:
    return _mask_spans(text, _policy_aware_spans(text))


def _context_abstraction(text: str) -> str:
    result = _placeholder(text)
    for term in sorted(CONTEXT_TERMS, key=len, reverse=True):
        result = re.sub(re.escape(term), "<PRIVATE_CONTEXT>", result, flags=re.IGNORECASE)
    return result


def _access_control_variant(text: str) -> str:
    result = _context_abstraction(text)
    return re.sub(r"(?:<PRIVATE_CONTEXT>\s*)+", "<ACCESS_CONTROLLED_CONTEXT> ", result)


def _attack_prompt(text: str) -> str:
    return (
        "You are performing a privacy inference audit. Choose exactly one label from: "
        f"{', '.join(LABELS)}. Infer the sensitive context category. Return only the label.\n\n"
        f"Prompt:\n{text}\n"
    )


def _parse_label(response: str) -> str:
    normalized = response.strip().lower()
    for label in LABELS:
        if re.search(rf"\b{re.escape(label)}\b", normalized):
            return label
    return "unparsed"


def _generate(prompt: str, model: str, url: str) -> tuple[str, str, float]:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0, "top_p": 1.0, "seed": 20260903, "num_predict": 16},
        }
    ).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response", "")), "ollama", (time.perf_counter() - started) * 1000.0


def _nvidia_smi() -> str:
    try:
        return subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,memory.used", "--format=csv,noheader"],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=30,
        ).strip()
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        return f"unavailable: {error}"


def run(model: str, ollama_url: str, output_tag: str, max_probes: int | None, dry_run: bool) -> tuple[Path, Path]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", output_tag):
        raise ValueError("output tag must contain only letters, digits, '.', '_' or '-'")
    selected = PROBES[:max_probes] if max_probes is not None else PROBES
    variants = {
        "raw": lambda text: text,
        "placeholder": _placeholder,
        "context_abstraction": _context_abstraction,
        "access_control": _access_control_variant,
    }
    detail_rows: list[dict[str, Any]] = []
    for probe_id, gold_label, raw_text in selected:
        for variant, transform in variants.items():
            sanitized = transform(raw_text)
            if dry_run:
                label, mode, latency_ms = "not_run", "dry_run", 0.0
            else:
                response, mode, latency_ms = _generate(_attack_prompt(sanitized), model, ollama_url)
                label = _parse_label(response)
            detail_rows.append(
                {
                    "probe_id": probe_id,
                    "gold_label": gold_label,
                    "variant": variant,
                    "prompt_hash": _sha256(sanitized),
                    "prompt_text": sanitized,
                    "attack_label": label,
                    "attack_correct": "" if dry_run else str(int(label == gold_label)),
                    "attack_mode": mode,
                    "latency_ms": f"{latency_ms:.1f}",
                }
            )

    detail_path = EXPERIMENTS_DIR / f"{OUTPUT_PREFIX}_prompt_logs_{output_tag}.csv"
    result_path = EXPERIMENTS_DIR / f"{OUTPUT_PREFIX}_results_{output_tag}.csv"
    runtime_path = EXPERIMENTS_DIR / f"{OUTPUT_PREFIX}_runtime_manifest_{output_tag}.csv"
    with detail_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(detail_rows[0].keys()))
        writer.writeheader()
        writer.writerows(detail_rows)

    result_rows: list[dict[str, str]] = []
    for variant in variants:
        rows = [row for row in detail_rows if row["variant"] == variant and row["attack_correct"] != ""]
        correct = sum(int(row["attack_correct"]) for row in rows)
        result_rows.append(
            {
                "variant": variant,
                "probe_count": str(len(selected)),
                "accuracy_percent": f"{100.0 * correct / len(rows):.1f}" if rows else "",
                "execution_status": "dry_run_not_scored" if dry_run else "executed",
                "notes": "Heuristic context abstraction/access-control candidates; not a semantic privacy guarantee.",
            }
        )
    with result_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result_rows[0].keys()))
        writer.writeheader()
        writer.writerows(result_rows)

    runtime_rows = [
        ("model", model),
        ("ollama_url", ollama_url),
        ("seed", "20260903"),
        ("temperature", "0.0"),
        ("top_p", "1.0"),
        ("probe_count", str(len(selected))),
        ("dry_run", str(dry_run).lower()),
        ("python_version", platform.python_version()),
        ("nvidia_smi", _nvidia_smi()),
        ("run_started_utc", datetime.now(timezone.utc).isoformat()),
        ("claim_boundary", "Preparation/heuristic mitigation probe; no semantic protection claim without frozen executed evidence."),
    ]
    with runtime_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["field", "value"])
        writer.writerows(runtime_rows)
    print(f"Wrote {detail_path}")
    print(f"Wrote {result_path}")
    print(f"Wrote {runtime_path}")
    return detail_path, result_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--output-tag", default="revision20260903")
    parser.add_argument("--max-probes", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.max_probes is not None and not 1 <= args.max_probes <= len(PROBES):
        raise SystemExit(f"--max-probes must be between 1 and {len(PROBES)}")
    run(args.model, args.ollama_url, args.output_tag, args.max_probes, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
