#!/usr/bin/env python3
"""Build TAB prompt-wrapper manifests and matched-baseline protocol files.

This script always writes a protocol description for TAB external transfer. If
TAB JSON files are supplied, it also emits a prompt-wrapped manifest under the
current CPPB-aligned evaluation protocol.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
PROTOCOL_PATH = EXPERIMENTS_DIR / "tab_matched_baseline_protocol.json"
DEFAULT_MANIFEST_PATH = EXPERIMENTS_DIR / "tab_prompt_wrapped_manifest.csv"

MATCHED_BASELINES = [
    {
        "name": "Raw prompt",
        "family": "No protection",
        "restoration_aware": False,
        "notes": "Forward the wrapped prompt without sanitization.",
    },
    {
        "name": "Regex-only",
        "family": "Pattern baseline",
        "restoration_aware": False,
        "notes": "Mask deterministic identifiers with regex recognizers only.",
    },
    {
        "name": "NER-only masking",
        "family": "Entity baseline",
        "restoration_aware": False,
        "notes": "Mask PERSON/ORG/LOCATION style mentions without policy routing.",
    },
    {
        "name": "Presidio (regex-only baseline)",
        "family": "Industrial de-identification",
        "restoration_aware": False,
        "notes": "Run Presidio recognizers restricted to pattern-heavy entities.",
    },
    {
        "name": "Presidio (with NER fallback)",
        "family": "Industrial de-identification",
        "restoration_aware": False,
        "notes": "Run Presidio with NER fallback under the same wrapped prompt.",
    },
    {
        "name": "Prompted LLM zero-shot de-identification",
        "family": "Semantic baseline",
        "restoration_aware": False,
        "notes": "Use one fixed de-identification prompt template and decoding configuration.",
    },
    {
        "name": "BodhiPromptShield (proposed)",
        "family": "Policy-aware mediation",
        "restoration_aware": True,
        "notes": "Run the same mediation policy profile used in CPPB utility-constrained evaluation.",
    },
]


def _write_protocol() -> None:
    protocol = {
        "benchmark": "TAB",
        "benchmark_family": "text anonymization external transfer",
        "core_metrics": ["span_precision", "span_recall", "span_f1", "per", "ac", "tsr"],
        "evaluation_slice": "text-only matched transfer",
        "expected_input": {
            "format": "TAB JSON files such as echr_train.json / echr_dev.json / echr_test.json from the public repository root",
            "required_document_fields": ["doc_id", "dataset_type", "text", "annotations", "task"],
        },
        "wrapper_prompt_template": {
            "system_instruction": "You are evaluating prompt privacy mediation on a public anonymization benchmark.",
            "user_prompt": "Protect all identifiers that should remain masked while preserving the document's task-relevant meaning. Return a sanitized version and a short summary that stays faithful to the original case.",
        },
        "matched_baselines": MATCHED_BASELINES,
        "category_mapping_notes": [
            "DIRECT and QUASI identifier types map to the main exposure slice.",
            "Confidential attributes remain part of the contextual sensitivity analysis rather than a standalone release-time label.",
            "Document-level summaries should be evaluated under the same AC/TSR interpretation used in CPPB text-only slices.",
        ],
    }
    with open(PROTOCOL_PATH, "w", encoding="utf-8") as handle:
        json.dump(protocol, handle, indent=2)
        handle.write("\n")


def _load_documents(path: Path) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("documents", "docs", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError(f"Unsupported TAB JSON payload in {path}")


def _extract_mentions(document: dict[str, Any]) -> list[dict[str, Any]]:
    annotations = document.get("annotations", [])
    if isinstance(annotations, dict):
        values: list[dict[str, Any]] = []
        for value in annotations.values():
            if isinstance(value, dict):
                mention_rows = value.get("entity_mentions", [])
                if isinstance(mention_rows, list):
                    values.extend(item for item in mention_rows if isinstance(item, dict))
            elif isinstance(value, list):
                values.extend(item for item in value if isinstance(item, dict))
        return values
    if isinstance(annotations, list):
        return [item for item in annotations if isinstance(item, dict)]
    return []


def _iter_input_paths(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        candidate = Path(item)
        if candidate.is_dir():
            paths.extend(sorted(candidate.glob("*.json")))
            continue
        expanded = [Path(path) for path in glob.glob(item)]
        if expanded:
            paths.extend(sorted(path for path in expanded if path.suffix.lower() == ".json"))
            continue
        paths.append(candidate)

    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(path)
    return unique_paths


def build_manifest(input_paths: list[Path], output_path: Path) -> Path:
    rows: list[dict[str, str]] = []
    for path in input_paths:
        for document in _load_documents(path):
            mentions = _extract_mentions(document)
            unique_mentions = {
                (
                    int(mention.get("start_offset", -1)),
                    int(mention.get("end_offset", -1)),
                    str(mention.get("identifier_type", "")).upper(),
                    str(mention.get("entity_type", "UNKNOWN")),
                    str(mention.get("span_text", "")),
                    str(mention.get("confidential_status", "")),
                )
                for mention in mentions
                if isinstance(mention.get("start_offset"), int) and isinstance(mention.get("end_offset"), int)
            }
            direct_mentions = sum(1 for mention in unique_mentions if mention[2] == "DIRECT")
            quasi_mentions = sum(1 for mention in unique_mentions if mention[2] == "QUASI")
            confidential = sum(
                1
                for mention in unique_mentions
                if mention[5] and mention[5].upper() not in {"NOT_CONFIDENTIAL", "NONE", "FALSE"}
            )
            entity_types = sorted({mention[3] for mention in unique_mentions if mention[3]})
            annotations = document.get("annotations", {})
            annotator_count = len(annotations) if isinstance(annotations, dict) else 1
            rows.append(
                {
                    "benchmark": "TAB",
                    "split": str(document.get("dataset_type", "unknown")),
                    "document_id": str(document.get("doc_id", "unknown")),
                    "task_target": str(document.get("task", "unspecified target")),
                    "document_chars": str(len(str(document.get("text", "")))),
                    "annotator_count": str(annotator_count),
                    "annotated_mentions": str(len(mentions)),
                    "maskable_mentions": str(direct_mentions + quasi_mentions),
                    "direct_mentions": str(direct_mentions),
                    "quasi_mentions": str(quasi_mentions),
                    "confidential_mentions": str(confidential),
                    "entity_types": " | ".join(entity_types),
                    "wrapper_instruction": "Protect identifiers while preserving case semantics; return a sanitized text plus a short faithful summary.",
                    "evaluation_slice": "text-only matched transfer",
                }
            )

    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "benchmark",
                "split",
                "document_id",
                "task_target",
                "document_chars",
                "annotator_count",
                "annotated_mentions",
                "maskable_mentions",
                "direct_mentions",
                "quasi_mentions",
                "confidential_mentions",
                "entity_types",
                "wrapper_instruction",
                "evaluation_slice",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build TAB external-transfer wrapper artifacts.")
    parser.add_argument("inputs", nargs="*", help="TAB JSON files to wrap")
    parser.add_argument("--output", default=str(DEFAULT_MANIFEST_PATH), help="Output CSV for wrapped manifest")
    args = parser.parse_args()

    _write_protocol()
    print(f"TAB matched-baseline protocol written to {PROTOCOL_PATH}")

    if not args.inputs:
        print("No TAB JSON supplied; wrote protocol only.")
        return 0

    output_path = build_manifest(_iter_input_paths(args.inputs), Path(args.output))
    print(f"TAB prompt-wrapped manifest written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())