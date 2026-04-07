#!/usr/bin/env python3
"""Build a source-level provenance manifest for the released CPPB snapshot."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
TEMPLATE_INVENTORY_PATH = EXPERIMENTS_DIR / "cppb_template_inventory.csv"
PROMPT_MANIFEST_PATH = EXPERIMENTS_DIR / "cppb_prompt_manifest.csv"
OUTPUT_PATH = EXPERIMENTS_DIR / "cppb_source_licensing_manifest.csv"


SOURCE_NOTES = {
    "Dialogue templates": {
        "provenance_summary": "Repository-authored direct-request dialogue prompts for controlled Prompt QA evaluation.",
        "licensing_status": "Repository-authored release material; no third-party user records redistributed.",
        "raw_asset_release": "Prompt text stubs and accounting records only",
    },
    "Document scenarios": {
        "provenance_summary": "Repository-authored document-oriented prompt scenarios for controlled Document QA evaluation.",
        "licensing_status": "Repository-authored release material; no external document images or raw third-party records redistributed.",
        "raw_asset_release": "Prompt text stubs and accounting records only",
    },
    "Public task sources": {
        "provenance_summary": "Repository-authored retrieval-style prompts abstracted from public-task-style workflows rather than copied benchmark instances.",
        "licensing_status": "Repository-authored release material referencing public task styles but not redistributing external benchmark payloads.",
        "raw_asset_release": "Prompt text stubs and accounting records only",
    },
    "Agent workflow traces": {
        "provenance_summary": "Repository-authored tool-oriented agent traces for controlled agent-execution evaluation.",
        "licensing_status": "Repository-authored release material; no real operational logs or user traces redistributed.",
        "raw_asset_release": "Prompt text stubs and accounting records only",
    },
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_rows() -> list[dict[str, str]]:
    template_rows = _read_csv(TEMPLATE_INVENTORY_PATH)
    prompt_rows = _read_csv(PROMPT_MANIFEST_PATH)

    template_counts: dict[str, int] = defaultdict(int)
    prompt_counts: dict[str, int] = defaultdict(int)
    ocr_prompt_counts: dict[str, int] = defaultdict(int)
    downstream_types: dict[str, set[str]] = defaultdict(set)
    families: dict[str, set[str]] = defaultdict(set)

    for row in template_rows:
        source = row["prompt_source"]
        template_counts[source] += 1
        downstream_types[source].add(row["downstream_task_type"])
        families[source].add(row["prompt_family"])

    for row in prompt_rows:
        source = row["prompt_source"]
        prompt_counts[source] += 1
        if row["modality"] == "OCR-mediated text-plus-image":
            ocr_prompt_counts[source] += 1

    rows: list[dict[str, str]] = []
    for source in sorted(template_counts):
        source_note = SOURCE_NOTES[source]
        rows.append(
            {
                "prompt_source": source,
                "prompt_families": " | ".join(sorted(families[source])),
                "downstream_task_types": " | ".join(sorted(downstream_types[source])),
                "template_count": str(template_counts[source]),
                "prompt_count": str(prompt_counts[source]),
                "ocr_prompt_count": str(ocr_prompt_counts[source]),
                "provenance_summary": source_note["provenance_summary"],
                "licensing_status": source_note["licensing_status"],
                "raw_asset_release": source_note["raw_asset_release"],
                "notes": "Construction-time prompt sources are benchmark-authored and align with the released CPPB card rather than redistributed external raw assets.",
            }
        )
    return rows


def write_rows(rows: list[dict[str, str]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    rows = build_rows()
    write_rows(rows)
    print(f"CPPB source manifest written to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())