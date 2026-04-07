#!/usr/bin/env python3
"""Download and pin a reproducible public SROIE snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from datasets import load_dataset
from huggingface_hub import snapshot_download


EXPERIMENTS_DIR = Path(__file__).resolve().parent
RESOURCE_ROOT = EXPERIMENTS_DIR / "external_data" / "resource_cache" / "sroie_dataset"
SNAPSHOT_ROOT = RESOURCE_ROOT / "hf_snapshot"
DEFAULT_REVISION = "b9bc49bf5eb8b06528c810d02a4f7c766474fbad"
DEFAULT_DATASET_ID = "rajistics/sroie_processed"
DEFAULT_MANIFEST_PATH = EXPERIMENTS_DIR / "sroie_snapshot_manifest.json"


def _repo_relative(path: Path) -> str:
    try:
        return path.relative_to(EXPERIMENTS_DIR.parent.parent).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _snapshot_ready(snapshot_dir: Path) -> bool:
    return any(snapshot_dir.glob("data/*.parquet"))


def _local_data_files(snapshot_dir: Path) -> dict[str, list[str]]:
    data_files: dict[str, list[str]] = {}
    for split in ("train", "test"):
        matched = sorted(snapshot_dir.glob(f"data/{split}-*.parquet"))
        if matched:
            data_files[split] = [str(path) for path in matched]
    return data_files


def acquire_snapshot(revision: str, dataset_id: str, force_download: bool) -> Path:
    snapshot_dir = SNAPSHOT_ROOT / revision
    if snapshot_dir.exists() and force_download:
        shutil.rmtree(snapshot_dir)

    if not _snapshot_ready(snapshot_dir):
        snapshot_download(
            repo_id=dataset_id,
            repo_type="dataset",
            revision=revision,
            local_dir=snapshot_dir,
            allow_patterns=["dataset_infos.json", "data/*.parquet"],
            force_download=force_download,
        )
        download_status = "downloaded"
    else:
        download_status = "reused_local_snapshot"

    data_files = _local_data_files(snapshot_dir)
    dataset = load_dataset("parquet", data_files=data_files)
    first_split = next(iter(dataset.keys()))
    tracked_files = [path for path in snapshot_dir.rglob("*") if path.is_file()]

    manifest: dict[str, Any] = {
        "benchmark": "SROIE",
        "dataset_id": dataset_id,
        "snapshot_revision": revision,
        "snapshot_url": f"https://huggingface.co/datasets/{dataset_id}/tree/{revision}",
        "license": "See upstream pinned dataset card",
        "snapshot_root": _repo_relative(snapshot_dir),
        "download_status": download_status,
        "split_breakdown": {split: len(records) for split, records in dataset.items()},
        "feature_fields": list(dataset[first_split].features.keys()),
        "tracked_files": [
            {
                "path": _repo_relative(path),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in sorted(tracked_files)
        ],
        "notes": "Pinned public SROIE processed parquet snapshot downloaded from Hugging Face and stored locally for reproducible OCR reruns.",
    }
    DEFAULT_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return snapshot_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and pin a public SROIE snapshot.")
    parser.add_argument("--revision", default=DEFAULT_REVISION, help="Pinned Hugging Face revision SHA")
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID, help="Hugging Face dataset identifier")
    parser.add_argument("--force-download", action="store_true", help="Redownload the snapshot even if cached")
    args = parser.parse_args()

    snapshot_dir = acquire_snapshot(args.revision, args.dataset_id, args.force_download)
    print(f"SROIE snapshot manifest written to {DEFAULT_MANIFEST_PATH}")
    print(f"SROIE snapshot ready at {snapshot_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())