#!/usr/bin/env python3
"""Build a normalized export from the public PhysioNet-relabeled i2b2-style dataset.

The Hugging Face dataset provides publicly accessible note text plus span labels in
an i2b2-style de-identification schema. This script converts it into the same
normalized export schema used by the existing clinical transfer runners.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from datasets import load_dataset


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = "theekshana/NER_medical_reports_tokenized_deid_roberta_i2b2"
DEFAULT_OUTPUT = EXPERIMENTS_DIR / "physionet_deid_relabeled_export.jsonl"

LABEL_MAP = {
    "PATIENT": "PATIENT",
    "AGE": "AGE",
    "PHONE": "PHONE",
    "LOC": "LOCATION",
    "LOCATION": "LOCATION",
    "DATE": "DATE",
    "ID": "ID",
    "CITY": "CITY",
    "STATE": "STATE",
    "COUNTRY": "COUNTRY",
    "ORGANIZATION": "ORGANIZATION",
    "HOSPITAL": "HOSPITAL",
    "PROFESSION": "PROFESSION",
}


def _normalize_record(record: dict[str, Any], split: str, index: int) -> dict[str, Any]:
    text = str(record.get("text", ""))
    raw_spans = record.get("ner_tags", [])
    phi_spans: list[dict[str, Any]] = []
    if isinstance(raw_spans, list):
        for span in raw_spans:
            if not isinstance(span, dict):
                continue
            start = span.get("start")
            end = span.get("end")
            label = str(span.get("label") or "UNKNOWN")
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            phi_type = LABEL_MAP.get(label, label)
            phi_spans.append(
                {
                    "start": start,
                    "end": end,
                    "text": text[start:end],
                    "phi_type": phi_type,
                    "phi_subtype": label,
                }
            )
    note_id = f"physionet-relabeled-{split}-{index:04d}"
    return {
        "note_id": note_id,
        "split": f"physionet-{split}",
        "text": text,
        "phi_spans": sorted(phi_spans, key=lambda item: (item["start"], item["end"], item["phi_type"])),
    }


def build_export(dataset_name: str, output_path: Path, split_filter: str | None, max_notes: int | None) -> Path:
    dataset = load_dataset(dataset_name)
    with open(output_path, "w", encoding="utf-8") as handle:
        for split, split_ds in dataset.items():
            if split_filter and split != split_filter:
                continue
            for index, record in enumerate(split_ds):
                if max_notes is not None and index >= max_notes:
                    break
                normalized = _normalize_record(record, split, index)
                handle.write(json.dumps(normalized, ensure_ascii=False) + "\n")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a normalized export from the public PhysioNet-relabeled i2b2-style dataset.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="Hugging Face dataset name to load")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSONL path")
    parser.add_argument("--split", help="Optional split filter, e.g. train or test")
    parser.add_argument("--max-notes", type=int, help="Optional maximum number of notes to export from each selected split")
    args = parser.parse_args()

    output_path = build_export(args.dataset, Path(args.output), args.split, args.max_notes)
    print(f"Public PhysioNet-relabeled export written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())