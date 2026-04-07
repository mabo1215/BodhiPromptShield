#!/usr/bin/env python3
"""Build a note-style synthetic export from the public i2b2-Synthea sample zip.

The public i2b2-Synthea cache ships table-oriented synthetic patient data rather
than note-style PHI annotations. This helper constructs a small, transparent,
normalization-compatible note export so the local zero-shot clinical path can be
executed without licensed notes.
"""
from __future__ import annotations

import argparse
import csv
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_ZIP_PATH = (
    EXPERIMENTS_DIR
    / "external_data"
    / "resource_cache"
    / "i2b2_synthea_toolkit"
    / "archive"
    / "i2b2-synthea-main"
    / "syntheamass_63K_sample.zip"
)
DEFAULT_OUTPUT_PATH = EXPERIMENTS_DIR / "i2b2_synthea_synthetic_export.jsonl"


def _read_delimited_rows(zip_file: zipfile.ZipFile, member_name: str) -> list[dict[str, str]]:
    with zip_file.open(member_name) as handle:
        decoded = (line.decode("utf-8", errors="replace").rstrip("\r\n") for line in handle)
        rows = [line.split("\t") for line in decoded if line.strip()]
    header = rows[0]
    return [dict(zip(header, row)) for row in rows[1:] if row]


def _normalize_birth_date(value: str) -> str:
    return value.split(" ")[0] if value and value != "1900-01-01 00:00:00" else "unknown"


def _normalize_sex(value: str) -> str:
    return {"M": "male", "F": "female"}.get(value, value.lower() if value else "unknown")


def _observation_text(observation: dict[str, str]) -> str | None:
    concept = observation.get("CONCEPT_CD", "")
    tval = observation.get("TVAL_CHAR", "")
    if concept.startswith("DEM|"):
        return None
    if not tval or tval == "@":
        return None
    concept_label = concept.split(":", 1)[-1].replace("_", " ").replace("|", " ").strip()
    return f"{concept_label}: {tval}"


def build_synthetic_export(zip_path: Path, output_path: Path, max_notes: int, split: str) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        patient_rows = _read_delimited_rows(archive, "patient_dimension.csv")
        observation_rows = _read_delimited_rows(archive, "observation_fact.csv")

    observations_by_patient: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observation_rows:
        patient_num = row.get("PATIENT_NUM", "")
        if patient_num:
            observations_by_patient[patient_num].append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for patient in patient_rows:
            patient_num = patient.get("PATIENT_NUM", "")
            if not patient_num:
                continue
            birth_date = _normalize_birth_date(patient.get("BIRTH_DATE", ""))
            sex = _normalize_sex(patient.get("SEX_CD", ""))
            race = (patient.get("RACE_CD", "") or "unknown").strip().lower()
            marital = (patient.get("MARITAL_STATUS_CD", "") or "unknown").strip()
            observation_texts = []
            for observation in observations_by_patient.get(patient_num, []):
                rendered = _observation_text(observation)
                if rendered and rendered not in observation_texts:
                    observation_texts.append(rendered)
                if len(observation_texts) >= 4:
                    break
            if not observation_texts:
                continue

            note_text = (
                f"Synthetic patient {patient_num} was born on {birth_date}. "
                f"This {sex} patient is recorded as race {race} and marital status {marital}. "
                f"Recent structured clinical observations include {'; '.join(observation_texts)}."
            )

            phi_spans = []
            patient_phrase = f"patient {patient_num}"
            patient_start = note_text.index(patient_phrase) + len("patient ")
            phi_spans.append(
                {
                    "start": patient_start,
                    "end": patient_start + len(patient_num),
                    "text": patient_num,
                    "phi_type": "PATIENT_ID",
                    "phi_subtype": "ID",
                }
            )
            if birth_date != "unknown":
                birth_start = note_text.index(birth_date)
                phi_spans.append(
                    {
                        "start": birth_start,
                        "end": birth_start + len(birth_date),
                        "text": birth_date,
                        "phi_type": "DATE",
                        "phi_subtype": "BIRTH_DATE",
                    }
                )

            record = {
                "note_id": f"synthea-{int(patient_num):05d}",
                "split": split,
                "text": note_text,
                "phi_spans": phi_spans,
                "source_route": "i2b2_synthea_public_sample",
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
            if written >= max_notes:
                break

    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a synthetic note-style export from the i2b2-Synthea sample zip.")
    parser.add_argument("--zip-path", type=Path, default=DEFAULT_ZIP_PATH, help="Path to syntheamass_63K_sample.zip")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output JSONL path")
    parser.add_argument("--max-notes", type=int, default=32, help="Maximum number of synthetic notes to emit")
    parser.add_argument("--split", default="synthea-dev", help="Split label written into the normalized export")
    args = parser.parse_args()

    output_path = build_synthetic_export(args.zip_path, args.output, args.max_notes, args.split)
    print(f"Synthetic i2b2-style export written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())