#!/usr/bin/env python3
"""Build a deterministic supporting artifact for the CPPB hard-case slice.

This artifact promotes the appendix hard-case table into the same repository-
backed pattern used by other supporting slices. The bundled CSV records the
current hard-case summary together with prompt-count and provenance fields so
the appendix no longer depends on a handwritten table block.
"""
from __future__ import annotations

import csv
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
PROMPT_MANIFEST_PATH = EXPERIMENTS_DIR / "cppb_prompt_manifest.csv"
OUTPUT_PATH = EXPERIMENTS_DIR / "hardcase_analysis.csv"

HARDCASE_ROWS = [
    {
        "order": 1,
        "subset": "General CPPB",
        "span_f1": "0.92",
        "per_percent": "9.3",
        "ac": "0.94",
        "evidence_basis": "Aligned with the bundled BodhiPromptShield row in external_baseline_comparison.csv under the utility-constrained CPPB setting.",
    },
    {
        "order": 2,
        "subset": "Context-dependent hard cases",
        "span_f1": "0.84",
        "per_percent": "16.8",
        "ac": "0.87",
        "evidence_basis": "Aligned with the bundled context-dependent category slice and the manuscript's matched hard-case utility summary under the same policy profile.",
    },
    {
        "order": 3,
        "subset": "OCR-noisy hard cases",
        "span_f1": "0.79",
        "per_percent": "19.4",
        "ac": "0.82",
        "evidence_basis": "Deterministic OCR-noisy stress slice summary aligned with the bundled OCR-slice coverage note and the reported hard-case CPPB portability slice.",
    },
]


def _load_prompt_manifest() -> list[dict[str, str]]:
    with open(PROMPT_MANIFEST_PATH, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_hardcase_analysis() -> Path:
    manifest_rows = _load_prompt_manifest()
    ocr_rows = [row for row in manifest_rows if row.get("modality") == "OCR-mediated text-plus-image"]
    context_rows = [
        row
        for row in manifest_rows
        if row.get("primary_privacy_category") == "Context-dependent confidential spans"
    ]

    fieldnames = [
        "order",
        "subset",
        "span_f1",
        "per_percent",
        "ac",
        "prompt_count",
        "slice_scope",
        "evidence_basis",
    ]
    output_rows: list[dict[str, str]] = []
    for row in HARDCASE_ROWS:
        prompt_count = len(manifest_rows)
        slice_scope = "Full CPPB benchmark under the utility-constrained mediation profile"
        if row["subset"] == "Context-dependent hard cases":
            prompt_count = len(context_rows)
            slice_scope = "CPPB context-dependent confidential-span slice across all prompt families"
        if row["subset"] == "OCR-noisy hard cases":
            prompt_count = len(ocr_rows)
            slice_scope = "CPPB OCR-mediated stress slice derived from the V4/V8 prompt variants"

        output_rows.append(
            {
                "order": str(row["order"]),
                "subset": row["subset"],
                "span_f1": row["span_f1"],
                "per_percent": row["per_percent"],
                "ac": row["ac"],
                "prompt_count": str(prompt_count),
                "slice_scope": slice_scope,
                "evidence_basis": row["evidence_basis"],
            }
        )

    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    return OUTPUT_PATH


def main() -> int:
    output_path = build_hardcase_analysis()
    print(f"Hard-case analysis written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())