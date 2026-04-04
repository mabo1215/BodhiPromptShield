#!/usr/bin/env python3
"""Prepare normalized i2b2 exports for the clinical transfer wrapper pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tarfile
from typing import Any
import xml.etree.ElementTree as ET


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = EXPERIMENTS_DIR / "i2b2_normalized_export.jsonl"
DEFAULT_TEMPLATE_PATH = EXPERIMENTS_DIR / "i2b2_normalized_export_template.jsonl"

SPLIT_HINTS = {"train", "training", "test", "dev", "valid", "validation"}


def _infer_split(path: Path, override: str | None) -> str:
    if override:
        return override
    for candidate in [path.parent.name, path.parent.parent.name, path.stem]:
        lowered = candidate.lower()
        if lowered in SPLIT_HINTS:
            return "dev" if lowered in {"dev", "valid", "validation"} else lowered
    return "unknown"


def _fallback_text(xml_path: Path) -> str:
    txt_path = xml_path.with_suffix(".txt")
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8")
    return ""


def _decode_text(payload: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def _infer_split_from_name(name: str) -> str | None:
    lowered = name.lower()
    if "test" in lowered:
        return "test"
    if "train" in lowered:
        return "train"
    if any(token in lowered for token in ("dev", "valid", "validation")):
        return "dev"
    return None


def _normalize_xml_payload(
    *,
    xml_text: str,
    note_name: str,
    split_override: str | None,
    split_hint: str | None,
    fallback_text: str = "",
) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    text = root.findtext(".//TEXT") or fallback_text
    tags_parent = root.find(".//TAGS")
    phi_spans: list[dict[str, Any]] = []
    if tags_parent is not None:
        for child in list(tags_parent):
            start_raw = child.attrib.get("start")
            end_raw = child.attrib.get("end")
            if start_raw is None or end_raw is None:
                continue
            start = int(start_raw)
            end = int(end_raw)
            span_text = child.attrib.get("text") or text[start:end]
            phi_type = child.attrib.get("TYPE") or child.tag
            phi_spans.append(
                {
                    "start": start,
                    "end": end,
                    "text": span_text,
                    "phi_type": phi_type,
                    "phi_subtype": child.tag,
                }
            )
    note_id = root.attrib.get("id") or Path(note_name).stem
    return {
        "note_id": note_id,
        "split": split_override or split_hint or _infer_split_from_name(note_name) or "unknown",
        "text": text,
        "phi_spans": sorted(phi_spans, key=lambda item: (item["start"], item["end"], item["phi_type"])),
    }


def _normalize_xml_file(path: Path, split_override: str | None) -> dict[str, Any]:
    return _normalize_xml_payload(
        xml_text=path.read_text(encoding="utf-8"),
        note_name=path.name,
        split_override=split_override,
        split_hint=_infer_split(path, split_override),
        fallback_text=_fallback_text(path),
    )


def _load_archive_records(path: Path, split_override: str | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    split_hint = _infer_split_from_name(path.name)
    with tarfile.open(path, "r:*") as archive:
        text_members: dict[str, str] = {}
        xml_members: list[tarfile.TarInfo] = []
        for member in archive.getmembers():
            if not member.isfile():
                continue
            member_name = Path(member.name)
            suffix = member_name.suffix.lower()
            if suffix == ".xml":
                xml_members.append(member)
                continue
            if suffix == ".txt":
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                text_members[str(member_name.with_suffix(""))] = _decode_text(extracted.read())

        for member in sorted(xml_members, key=lambda item: item.name):
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            member_name = Path(member.name)
            records.append(
                _normalize_xml_payload(
                    xml_text=_decode_text(extracted.read()),
                    note_name=member_name.name,
                    split_override=split_override,
                    split_hint=split_hint,
                    fallback_text=text_members.get(str(member_name.with_suffix("")), ""),
                )
            )
    return records


def _normalize_json_record(record: dict[str, Any], source_path: Path, split_override: str | None, index: int) -> dict[str, Any]:
    note_id = str(record.get("note_id") or record.get("id") or f"{source_path.stem}-{index:04d}")
    split = str(record.get("split") or _infer_split(source_path, split_override))
    text = str(record.get("text") or record.get("note_text") or "")
    raw_spans = record.get("phi_spans") or record.get("tags") or record.get("phi") or []
    phi_spans: list[dict[str, Any]] = []
    if isinstance(raw_spans, list):
        for span in raw_spans:
            if not isinstance(span, dict):
                continue
            start = span.get("start")
            end = span.get("end")
            if start is None or end is None:
                continue
            phi_type = str(span.get("phi_type") or span.get("TYPE") or span.get("tag") or "UNKNOWN")
            phi_subtype = str(span.get("phi_subtype") or span.get("subtype") or phi_type)
            span_text = str(span.get("text") or text[int(start):int(end)])
            phi_spans.append(
                {
                    "start": int(start),
                    "end": int(end),
                    "text": span_text,
                    "phi_type": phi_type,
                    "phi_subtype": phi_subtype,
                }
            )
    return {
        "note_id": note_id,
        "split": split,
        "text": text,
        "phi_spans": sorted(phi_spans, key=lambda item: (item["start"], item["end"], item["phi_type"])),
    }


def _load_json_records(path: Path, split_override: str | None) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        if path.suffix.lower() == ".jsonl":
            payload = [json.loads(line) for line in handle if line.strip()]
        else:
            payload = json.load(handle)
    if isinstance(payload, dict):
        for key in ("records", "notes", "data"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
        else:
            payload = [payload]
    if not isinstance(payload, list):
        raise ValueError(f"Unsupported JSON payload in {path}")
    return [
        _normalize_json_record(record, path, split_override, index)
        for index, record in enumerate(payload)
        if isinstance(record, dict)
    ]


def _iter_source_paths(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        archive_files = sorted(input_path.rglob("*.tar.gz")) + sorted(input_path.rglob("*.tgz"))
        if archive_files:
            return archive_files
        xml_files = sorted(input_path.rglob("*.xml"))
        if xml_files:
            return xml_files
        json_files = sorted(input_path.rglob("*.jsonl")) + sorted(input_path.rglob("*.json"))
        if json_files:
            return json_files
    return [input_path]


def build_template(output_path: Path) -> Path:
    example_record = {
        "note_id": "i2b2-example-0001",
        "split": "train",
        "text": "Patient John Smith was admitted on 2014-03-21 to Boston General Hospital.",
        "phi_spans": [
            {"start": 8, "end": 18, "text": "John Smith", "phi_type": "PATIENT", "phi_subtype": "NAME"},
            {"start": 35, "end": 45, "text": "2014-03-21", "phi_type": "DATE", "phi_subtype": "DATE"},
            {"start": 49, "end": 72, "text": "Boston General Hospital", "phi_type": "HOSPITAL", "phi_subtype": "LOCATION"},
        ],
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(example_record, ensure_ascii=False) + "\n")
    return output_path


def build_normalized_export(input_path: Path, output_path: Path, split_override: str | None) -> Path:
    records: list[dict[str, Any]] = []
    for source_path in _iter_source_paths(input_path):
        source_name = source_path.name.lower()
        if source_name.endswith((".tar.gz", ".tgz")):
            records.extend(_load_archive_records(source_path, split_override))
        elif source_path.suffix.lower() == ".xml":
            records.append(_normalize_xml_file(source_path, split_override))
        elif source_path.suffix.lower() in {".json", ".jsonl"}:
            records.extend(_load_json_records(source_path, split_override))
        else:
            raise ValueError(f"Unsupported source file: {source_path}")

    with open(output_path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare normalized i2b2 exports for wrapper evaluation.")
    parser.add_argument("input", nargs="?", help="i2b2 XML/TXT directory or JSON/JSONL export to normalize")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Output JSONL path")
    parser.add_argument("--split", help="Optional split override applied to all notes")
    parser.add_argument("--template-only", action="store_true", help="Write a template normalized export and exit")
    args = parser.parse_args()

    if args.template_only:
        output_path = build_template(Path(args.output) if args.output else DEFAULT_TEMPLATE_PATH)
        print(f"i2b2 normalized export template written to {output_path}")
        return 0

    if not args.input:
        raise ValueError("An input path or --template-only is required")

    output_path = build_normalized_export(Path(args.input), Path(args.output), args.split)
    print(f"Normalized i2b2 export written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())