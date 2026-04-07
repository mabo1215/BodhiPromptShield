#!/usr/bin/env python3
"""Build a normalized export from the public AI4Privacy PII-Masking-300K dataset.

This script filters the dataset to English examples, assigns a deterministic
train/dev/test split based on the released record id, and converts span labels
into the normalized export schema used by the repository's transfer runners.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from datasets import load_dataset


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = "ai4privacy/pii-masking-300k"
DEFAULT_OUTPUT = EXPERIMENTS_DIR / "ai4privacy_pii300k_english_export.jsonl"
DEFAULT_LANGUAGE = "English"

LABEL_MAP = {
    "BOD": "DATE",
    "CITY": "LOCATION",
    "COUNTRY": "LOCATION",
    "DATE": "DATE",
    "DRIVERLICENSE": "ID",
    "EMAIL": "EMAIL",
    "GEOCOORD": "LOCATION",
    "GIVENNAME1": "PERSON",
    "GIVENNAME2": "PERSON",
    "IDCARD": "ID",
    "IP": "IP",
    "LASTNAME1": "PERSON",
    "LASTNAME2": "PERSON",
    "LASTNAME3": "PERSON",
    "PASSPORT": "ID",
    "POSTCODE": "LOCATION",
    "SECADDRESS": "LOCATION",
    "SOCIALNUMBER": "ID",
    "STATE": "LOCATION",
    "STREET": "LOCATION",
    "TEL": "PHONE",
    "TIME": "TIME",
    "TITLE": "TITLE",
    "USERNAME": "USERNAME",
    "BUILDING": "LOCATION",
    "SEX": "ATTRIBUTE",
    "PASS": "PASSWORD",
    "CARDISSUER": "FINANCIAL",
}


def _assign_split(record_id: str) -> str:
    digest = hashlib.sha256(record_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 10
    if bucket == 0:
        return "ai4privacy-test"
    if bucket == 1:
        return "ai4privacy-dev"
    return "ai4privacy-train"


def _normalize_record(record: dict[str, Any], index: int) -> dict[str, Any]:
    text = str(record.get("source_text", ""))
    record_id = str(record.get("id", f"row-{index:06d}"))
    raw_spans = record.get("privacy_mask", [])
    phi_spans: list[dict[str, Any]] = []
    if isinstance(raw_spans, list):
        for span in raw_spans:
            if not isinstance(span, dict):
                continue
            start = span.get("start")
            end = span.get("end")
            label = str(span.get("label") or "UNKNOWN")
            if not isinstance(start, int) or not isinstance(end, int) or end <= start:
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
    return {
        "note_id": f"ai4privacy-{record_id}",
        "split": _assign_split(record_id),
        "text": text,
        "phi_spans": sorted(phi_spans, key=lambda item: (item["start"], item["end"], item["phi_type"])),
    }


def build_export(dataset_name: str, output_path: Path, language: str, split_filter: str | None, max_records: int | None) -> Path:
    dataset = load_dataset(dataset_name, split="train")
    written = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for index, record in enumerate(dataset):
            if str(record.get("language", "")) != language:
                continue
            normalized = _normalize_record(record, index)
            if split_filter and normalized["split"] != split_filter:
                continue
            handle.write(json.dumps(normalized, ensure_ascii=False) + "\n")
            written += 1
            if max_records is not None and written >= max_records:
                break
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a normalized export from the public AI4Privacy PII-Masking-300K dataset.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="Hugging Face dataset name to load")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSONL path")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="Language filter for the export")
    parser.add_argument("--split", help="Optional split filter, e.g. ai4privacy-test")
    parser.add_argument("--max-records", type=int, help="Optional maximum number of records to export")
    args = parser.parse_args()

    output_path = build_export(args.dataset, Path(args.output), args.language, args.split, args.max_records)
    print(f"AI4Privacy normalized export written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())