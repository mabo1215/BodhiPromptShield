#!/usr/bin/env python3
"""Download and pin a reproducible public CORD snapshot.

The repository previously cached only the public GitHub metadata repository for
CORD. This helper downloads the public Hugging Face mirror at a fixed revision,
stores the archive locally, extracts it, and writes a machine-readable manifest
that records the exact source URL, revision, archive hash, and discovered
dataset root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from build_cord_transfer_surface import _looks_like_annotation


EXPERIMENTS_DIR = Path(__file__).resolve().parent
RESOURCE_ROOT = EXPERIMENTS_DIR / "external_data" / "resource_cache" / "cord_dataset"
SNAPSHOT_ROOT = RESOURCE_ROOT / "hf_snapshot"
DEFAULT_REVISION = "4f51527df44a7f7f915bee494f1129915118d0e1"
DEFAULT_DATASET_ID = "katanaml/cord"
DEFAULT_MANIFEST_PATH = EXPERIMENTS_DIR / "cord_snapshot_manifest.json"


def _repo_relative(path: Path) -> str:
    try:
        return path.relative_to(EXPERIMENTS_DIR.parent.parent).as_posix()
    except ValueError:
        return path.as_posix()


def _dataset_url(dataset_id: str, revision: str) -> str:
    return f"https://huggingface.co/datasets/{dataset_id}/resolve/{revision}/dataset.zip"


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _download(url: str, output_path: Path, force_download: bool) -> dict[str, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not force_download:
        return {
            "download_status": "reused_cached_archive",
            "source_url": url,
            "content_length": str(output_path.stat().st_size),
            "etag": "cached_only",
        }

    with urllib.request.urlopen(url, timeout=600) as response:
        headers = {key.lower(): value for key, value in response.info().items()}
        with output_path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    return {
        "download_status": "downloaded",
        "source_url": url,
        "content_length": headers.get("content-length", str(output_path.stat().st_size)),
        "etag": headers.get("etag", ""),
    }


def _extract_archive(archive_path: Path, extract_root: Path, force_extract: bool) -> Path:
    if extract_root.exists() and force_extract:
        shutil.rmtree(extract_root)
    if not extract_root.exists():
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extract_root)
    return extract_root


def _discover_dataset_root(extract_root: Path) -> Path:
    child_dirs = [path for path in extract_root.iterdir() if path.is_dir()] if extract_root.exists() else []
    if len(child_dirs) == 1:
        child = child_dirs[0]
        child_has_annotations = any(_looks_like_annotation(path) for path in child.rglob("*.json"))
        child_has_images = any(
            path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
            for path in child.rglob("*")
        )
        if child_has_annotations and child_has_images:
            return child

    annotation_paths = [path for path in extract_root.rglob("*.json") if _looks_like_annotation(path)]
    image_paths = [
        path
        for path in extract_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]
    if not annotation_paths or not image_paths:
        return extract_root

    candidate_roots = []
    for annotation_path in annotation_paths[:20]:
        for parent in [annotation_path.parent, *annotation_path.parents]:
            if parent == extract_root.parent:
                break
            has_images = any(image_path.is_relative_to(parent) for image_path in image_paths)
            if has_images:
                candidate_roots.append(parent)
    if not candidate_roots:
        return extract_root

    def _score(path: Path) -> tuple[int, int]:
        direct_names = {child.name.lower() for child in path.iterdir() if child.is_dir()}
        split_score = len(direct_names & {"train", "test", "dev", "valid"})
        io_score = len(direct_names & {"json", "image"})
        return split_score, io_score

    candidate_roots = sorted(candidate_roots, key=lambda path: (_score(path), len(path.parts)), reverse=True)
    return candidate_roots[0]


def _split_breakdown(dataset_root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in dataset_root.rglob("*.json"):
        if not _looks_like_annotation(path):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
        split = str(meta.get("split", "unknown"))
        counts[split] = counts.get(split, 0) + 1
    return counts


def acquire_snapshot(revision: str, dataset_id: str, force_download: bool, force_extract: bool) -> Path:
    url = _dataset_url(dataset_id, revision)
    snapshot_dir = SNAPSHOT_ROOT / revision
    archive_path = snapshot_dir / "dataset.zip"
    extract_root = snapshot_dir / "extracted"
    download_info = _download(url, archive_path, force_download)
    _extract_archive(archive_path, extract_root, force_extract)
    dataset_root = _discover_dataset_root(extract_root)

    annotation_count = len([path for path in dataset_root.rglob("*.json") if _looks_like_annotation(path)])
    image_count = len(
        [
            path
            for path in dataset_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
        ]
    )
    manifest: dict[str, Any] = {
        "benchmark": "CORD",
        "dataset_id": dataset_id,
        "snapshot_revision": revision,
        "snapshot_url": url,
        "license": "CC-BY-4.0",
        "archive_path": _repo_relative(archive_path),
        "archive_size_bytes": archive_path.stat().st_size,
        "archive_sha256": _sha256(archive_path),
        "extract_root": _repo_relative(extract_root),
        "dataset_root": _repo_relative(dataset_root),
        "annotation_file_count": annotation_count,
        "image_file_count": image_count,
        "split_breakdown": _split_breakdown(dataset_root),
        "download_status": download_info["download_status"],
        "download_etag": download_info["etag"],
        "download_content_length": download_info["content_length"],
        "notes": "Pinned public CORD snapshot downloaded from the Hugging Face mirror and stored locally for reproducible OCR reruns.",
    }
    DEFAULT_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return dataset_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and pin a public CORD snapshot.")
    parser.add_argument("--revision", default=DEFAULT_REVISION, help="Pinned Hugging Face revision SHA")
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID, help="Hugging Face dataset identifier")
    parser.add_argument("--force-download", action="store_true", help="Redownload the dataset archive even if cached")
    parser.add_argument("--force-extract", action="store_true", help="Re-extract the archive even if it is already unpacked")
    args = parser.parse_args()

    dataset_root = acquire_snapshot(args.revision, args.dataset_id, args.force_download, args.force_extract)
    print(f"CORD snapshot manifest written to {DEFAULT_MANIFEST_PATH}")
    print(f"CORD dataset root ready at {dataset_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())