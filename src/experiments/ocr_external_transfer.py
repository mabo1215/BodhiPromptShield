#!/usr/bin/env python3
"""Write OCR-heavy external-transfer tracking artifacts.

The current public snapshot mixes executed OCR-heavy public slices with tracked
future extensions. This helper records both the execution surface and the
remaining acquisition state under one protocol summary.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENTS_DIR.parent.parent
DEFAULT_ACQUISITION_MANIFEST = EXPERIMENTS_DIR / "external_resource_acquisition_manifest.json"
DEFAULT_PROTOCOL_PATH = EXPERIMENTS_DIR / "ocr_transfer_protocol.json"
DEFAULT_RESOURCE_MANIFEST_PATH = EXPERIMENTS_DIR / "ocr_transfer_resource_manifest.csv"
DEFAULT_DOWNLOAD_ROOT = EXPERIMENTS_DIR / "external_data" / "resource_cache"


BENCHMARKS: list[dict[str, Any]] = [
    {
        "benchmark_id": "cord_public_receipts",
        "resource_id": "cord_dataset",
        "dataset_name": "CORD",
        "task_focus": "OCR-heavy receipt parsing and entity extraction",
        "benchmark_kind": "public_receipt_benchmark",
        "priority": "primary",
        "execution_surface": "executed_public_snapshot",
        "missing_requirements": [],
        "next_step": "Keep the pinned CORD snapshot and executed comparator roster fixed, then use the same wrapper for broader OCR family comparisons.",
    },
    {
        "benchmark_id": "funsd_public_forms",
        "resource_id": "funsd_dataset",
        "dataset_name": "FUNSD",
        "task_focus": "Noisy form understanding after OCR-mediated text recovery",
        "benchmark_kind": "public_form_benchmark",
        "execution_surface": "executed_public_snapshot",
        "missing_requirements": [],
        "next_step": "Keep the pinned FUNSD snapshot and executed comparator roster fixed, then use the same wrapper for broader named OCR/de-id comparisons.",
    },
    {
        "benchmark_id": "sroie_public_receipts",
        "resource_id": "sroie_dataset",
        "dataset_name": "SROIE",
        "task_focus": "Receipt OCR and information extraction under noisy layout conditions",
        "benchmark_kind": "public_receipt_benchmark",
        "execution_surface": "executed_public_snapshot",
        "missing_requirements": [],
        "next_step": "Keep the pinned SROIE processed snapshot fixed, and improve the approximate OCR-token field alignment before claiming broader receipt generalization.",
    },
    {
        "benchmark_id": "docile_request_gated_documents",
        "resource_id": "docile_benchmark",
        "dataset_name": "DocILE",
        "task_focus": "Invoice and reimbursement document workflows with request-gated data access",
        "benchmark_kind": "request_gated_business_documents",
        "missing_requirements": [
            "Approved dataset access for the primary benchmark files",
            "Wrapper-ready export aligned to the matched mediation protocol",
            "Exact OCR engine and version manifest",
            "Result CSV and rerun log under the released comparator roster",
        ],
        "next_step": "Cache the public helper repository for schema/provenance support, then wait for approved benchmark access before execution.",
    },
]


def _load_acquisition_entries(manifest_path: Path) -> dict[str, dict[str, Any]]:
    if not manifest_path.exists():
        return {}
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in entries}


def _repo_relative(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _cache_state(resource_id: str, download_root: Path) -> tuple[str, str, bool]:
    resource_dir = download_root / resource_id
    archive_dir = resource_dir / "archive"
    helper_dir = resource_dir / "helper_archive"
    snapshot_dir = resource_dir / "hf_snapshot"
    if archive_dir.exists() and any(archive_dir.iterdir()):
        return "archive_cached", _repo_relative(archive_dir), False
    if helper_dir.exists() and any(helper_dir.iterdir()):
        return "helper_repo_cached", _repo_relative(helper_dir), True
    if snapshot_dir.exists() and any(snapshot_dir.rglob("*")):
        return "snapshot_cached", _repo_relative(snapshot_dir), False
    if resource_dir.exists():
        access_note = resource_dir / "ACCESS_NOTE.txt"
        if access_note.exists():
            return "access_note_only", _repo_relative(access_note), False
    return "not_cached", "", False


def build_rows(acquisition_entries: dict[str, dict[str, Any]], download_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for benchmark in BENCHMARKS:
        entry = acquisition_entries.get(benchmark["resource_id"], {})
        cache_state, artifact_path, helper_cached = _cache_state(benchmark["resource_id"], download_root)
        rows.append(
            {
                "benchmark_id": benchmark["benchmark_id"],
                "resource_id": benchmark["resource_id"],
                "dataset_name": benchmark["dataset_name"],
                "benchmark_kind": benchmark["benchmark_kind"],
                "task_focus": benchmark["task_focus"],
                "access_mode": str(entry.get("access_mode", "unknown")),
                "official_url": str(entry.get("official_url", "")),
                "download_status": str(entry.get("download_status", "recorded_only")),
                "current_release_status": str(entry.get("current_release_status", "resource entry recorded")),
                "local_cache_status": cache_state,
                "local_artifact_path": artifact_path,
                "helper_repo_cached": "yes" if helper_cached else "no",
                "execution_surface": str(benchmark.get("execution_surface", "scaffold_only")),
                "missing_requirements": " | ".join(benchmark["missing_requirements"]),
                "next_step": benchmark["next_step"],
            }
        )
    return rows


def build_protocol(rows: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "protocol_name": "ocr_heavy_external_transfer_tracking",
        "version": "1.0",
        "scope": "Public OCR-heavy document and receipt benchmarks tracked as executed or acquisition-aware transfer surfaces.",
        "status": "mixed_executed_and_tracked",
        "wrapper_invariants": [
            "Use the same mediation semantics and comparator-family distinctions as the released TAB and i2b2 wrappers.",
            "Keep exact OCR engine, version, and preprocessing configuration logged for every executed slice.",
            "Treat public acquisition manifests and helper repositories as provenance support rather than benchmark results for request-gated or still-tracked benchmarks.",
        ],
        "required_outputs_for_execution": [
            "Benchmark-specific wrapper manifest aligned to the matched mediation protocol",
            "Execution manifest with executed versus waiting-state comparator status",
            "Result CSV and per-document metrics when the benchmark is executable",
            "Run log that records OCR engine, input scope, and generated outputs",
        ],
        "benchmarks": [
            {
                "benchmark_id": row["benchmark_id"],
                "dataset_name": row["dataset_name"],
                "benchmark_kind": row["benchmark_kind"],
                "task_focus": row["task_focus"],
                "priority": next(
                    benchmark["priority"]
                    for benchmark in BENCHMARKS
                    if benchmark["benchmark_id"] == row["benchmark_id"] and "priority" in benchmark
                )
                if any(
                    benchmark["benchmark_id"] == row["benchmark_id"] and "priority" in benchmark
                    for benchmark in BENCHMARKS
                )
                else "tracked",
                "access_mode": row["access_mode"],
                "local_cache_status": row["local_cache_status"],
                "local_artifact_path": row["local_artifact_path"],
                "execution_surface": row["execution_surface"],
                "missing_requirements": row["missing_requirements"].split(" | "),
                "next_step": row["next_step"],
            }
            for row in rows
        ],
    }


def write_resource_manifest(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    acquisition_entries = _load_acquisition_entries(DEFAULT_ACQUISITION_MANIFEST)
    rows = build_rows(acquisition_entries, DEFAULT_DOWNLOAD_ROOT)
    protocol = build_protocol(rows)

    DEFAULT_PROTOCOL_PATH.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    write_resource_manifest(rows, DEFAULT_RESOURCE_MANIFEST_PATH)

    print(f"OCR transfer protocol written to {DEFAULT_PROTOCOL_PATH}")
    print(f"OCR transfer resource manifest written to {DEFAULT_RESOURCE_MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())