#!/usr/bin/env python3
"""Build i2b2 prompt-wrapper manifests and matched-baseline protocol files.

This script always writes a protocol description for i2b2-style external
transfer. If a normalized note export is supplied, it also emits a
prompt-wrapped manifest under the current CPPB-aligned evaluation protocol.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
PROTOCOL_PATH = EXPERIMENTS_DIR / "i2b2_matched_baseline_protocol.json"
DEFAULT_MANIFEST_PATH = EXPERIMENTS_DIR / "i2b2_prompt_wrapped_manifest.csv"

MATCHED_BASELINES = [
    {
        "name": "Raw prompt",
        "family": "No protection",
        "notes": "Forward the wrapped clinical note without sanitization.",
    },
    {
        "name": "Regex-only",
        "family": "Pattern baseline",
        "notes": "Mask dates, IDs, phones, and e-mail-like spans with rule-based recognizers.",
    },
    {
        "name": "NER-only masking",
        "family": "Entity baseline",
        "notes": "Mask person and organization entities without clinical PHI specialization.",
    },
    {
        "name": "Presidio-class (regex-focused heuristic)",
        "family": "Industrial de-identification",
        "notes": "Run the released structured-recognizer approximation for a Presidio-class comparator under the wrapped clinical note protocol.",
    },
    {
        "name": "Presidio-class (NER fallback heuristic)",
        "family": "Industrial de-identification",
        "notes": "Run the released structured-plus-NER approximation for a Presidio-class comparator under the wrapped clinical note protocol.",
    },
    {
        "name": "Clinical hybrid de-identification pipeline",
        "family": "Clinical domain baseline",
        "notes": "Allow one domain-specific hybrid comparator under the same prompt wrapper and evaluation slices.",
    },
    {
        "name": "Prompted LLM zero-shot de-identification",
        "family": "Semantic baseline",
        "notes": "Use one fixed clinical de-identification prompt template and decoding configuration.",
    },
    {
        "name": "BodhiPromptShield (proposed)",
        "family": "Policy-aware mediation",
        "notes": "Run the same utility-constrained mediation profile with clinically aligned task prompts.",
    },
]


def _write_protocol() -> None:
    protocol = {
        "benchmark": "2014 i2b2/UTHealth",
        "benchmark_family": "clinical de-identification external transfer",
        "core_metrics": [
            "entity_span_precision",
            "entity_span_recall",
            "entity_span_f1",
            "per",
            "category_wise_per",
            "ac",
            "tsr",
        ],
        "evaluation_slice": "clinical text matched transfer",
        "expected_input": {
            "format": "Normalized JSONL or JSON array with one note per item",
            "required_fields": ["note_id", "split", "text", "phi_spans"],
            "phi_span_fields": ["start", "end", "text", "phi_type", "phi_subtype"],
        },
        "wrapper_prompt_template": {
            "system_instruction": "You are evaluating privacy mediation on longitudinal clinical narratives.",
            "user_prompt": "Protect all PHI spans while preserving clinically relevant meaning. Return a sanitized note and a short task-faithful clinical summary.",
        },
        "matched_baselines": MATCHED_BASELINES,
        "category_mapping_notes": [
            "HIPAA and i2b2 PHI labels are preserved as the primary external de-identification target.",
            "Downstream utility should be evaluated on note summarization or clinical QA slices that do not require raw PHI restoration.",
            "The repository does not redistribute i2b2 raw notes; wrappers operate on user-provided normalized exports only.",
            "Use prepare_i2b2_normalized_export.py to convert raw XML/TXT releases into the required normalized export schema.",
        ],
    }
    with open(PROTOCOL_PATH, "w", encoding="utf-8") as handle:
        json.dump(protocol, handle, indent=2)
        handle.write("\n")


def _load_records(path: Path) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        if path.suffix.lower() == ".jsonl":
            return [json.loads(line) for line in handle if line.strip()]
        payload = json.load(handle)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("records", "notes", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError(f"Unsupported normalized i2b2 payload in {path}")


def _iter_input_paths(input_value: str) -> list[Path]:
    path = Path(input_value)
    if path.is_dir():
        paths = sorted(path.glob("*.jsonl")) + sorted(path.glob("*.json"))
        if paths:
            return paths
    expanded = [Path(item) for item in glob.glob(input_value)]
    if expanded:
        return sorted(expanded)
    return [path]


def build_manifest(input_paths: list[Path], output_path: Path) -> Path:
    rows: list[dict[str, str]] = []
    for input_path in input_paths:
        for record in _load_records(input_path):
            spans = record.get("phi_spans", [])
            if not isinstance(spans, list):
                spans = []
            phi_types = sorted({str(span.get("phi_type", "UNKNOWN")) for span in spans if isinstance(span, dict)})
            rows.append(
                {
                    "benchmark": "2014 i2b2/UTHealth",
                    "split": str(record.get("split", "unknown")),
                    "note_id": str(record.get("note_id", "unknown")),
                    "note_chars": str(len(str(record.get("text", "")))),
                    "phi_span_count": str(len(spans)),
                    "phi_types": " | ".join(phi_types),
                    "wrapper_instruction": "Protect PHI spans while preserving clinical meaning; return a sanitized note plus a concise clinical summary.",
                    "evaluation_slice": "clinical text matched transfer",
                }
            )

    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "benchmark",
                "split",
                "note_id",
                "note_chars",
                "phi_span_count",
                "phi_types",
                "wrapper_instruction",
                "evaluation_slice",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build i2b2 external-transfer wrapper artifacts.")
    parser.add_argument("input", nargs="?", help="Normalized JSONL or JSON export for i2b2 notes")
    parser.add_argument("--output", default=str(DEFAULT_MANIFEST_PATH), help="Output CSV for wrapped manifest")
    args = parser.parse_args()

    _write_protocol()
    print(f"i2b2 matched-baseline protocol written to {PROTOCOL_PATH}")

    if not args.input:
        print("No normalized i2b2 export supplied; wrote protocol only.")
        return 0

    output_path = build_manifest(_iter_input_paths(args.input), Path(args.output))
    print(f"i2b2 prompt-wrapped manifest written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())