#!/usr/bin/env python3
"""Prepare a CORD-first OCR transfer surface for future public reruns.

The current repository cache only includes the public CORD repository metadata,
not a fully pinned dataset snapshot. This helper makes that boundary explicit by
writing benchmark-specific preparation artifacts, and can build a wrapper-ready
manifest if a user later supplies a real CORD dataset root with annotations.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_CACHE_ROOT = EXPERIMENTS_DIR / "external_data" / "resource_cache" / "cord_dataset" / "archive" / "cord-master"
PREPARATION_MANIFEST_PATH = EXPERIMENTS_DIR / "cord_transfer_preparation_manifest.csv"
WRAPPED_MANIFEST_PATH = EXPERIMENTS_DIR / "cord_prompt_wrapped_manifest.csv"
EXECUTION_MANIFEST_PATH = EXPERIMENTS_DIR / "cord_transfer_execution_manifest.csv"
RUN_LOG_PATH = EXPERIMENTS_DIR / "cord_transfer_run_log.csv"
PROTOCOL_PATH = EXPERIMENTS_DIR / "cord_transfer_protocol.json"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _repo_relative(path: Path) -> str:
    try:
        return path.relative_to(EXPERIMENTS_DIR.parent.parent).as_posix()
    except ValueError:
        return path.as_posix()


def _looks_like_annotation(path: Path) -> bool:
    if path.suffix.lower() != ".json":
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and "valid_line" in payload and "meta" in payload


def _load_annotation(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _index_images(dataset_root: Path) -> dict[str, Path]:
    image_map: dict[str, Path] = {}
    for path in dataset_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            image_map.setdefault(path.stem, path)
    return image_map


def _resolve_image_path(image_map: dict[str, Path], image_id: str, annotation_path: Path) -> Path | None:
    sibling_image_dir = annotation_path.parent.parent / "image"
    if sibling_image_dir.exists():
        sibling_candidates = [annotation_path.stem]
        if image_id.isdigit():
            sibling_candidates.append(f"receipt_{int(image_id):05d}")
        sibling_candidates.append(Path(image_id).stem)
        for candidate in sibling_candidates:
            for suffix in IMAGE_EXTENSIONS:
                candidate_path = sibling_image_dir / f"{candidate}{suffix}"
                if candidate_path.exists():
                    return candidate_path

    candidates = [Path(image_id).stem, annotation_path.stem]
    if image_id.isdigit():
        candidates.append(f"receipt_{int(image_id):05d}")
    for candidate in candidates:
        image_path = image_map.get(candidate)
        if image_path is not None:
            return image_path
    return None


def build_wrapped_manifest(dataset_root: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    annotation_paths = [path for path in dataset_root.rglob("*.json") if _looks_like_annotation(path)]
    image_map = _index_images(dataset_root)
    rows: list[dict[str, str]] = []
    split_counts: dict[str, int] = {}

    for path in sorted(annotation_paths):
        payload = _load_annotation(path)
        meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
        valid_lines = payload.get("valid_line", []) if isinstance(payload.get("valid_line"), list) else []
        split = str(meta.get("split", "unknown"))
        split_counts[split] = split_counts.get(split, 0) + 1
        image_id = str(meta.get("image_id", path.stem))
        image_path = _resolve_image_path(image_map, image_id, path)
        word_count = 0
        key_word_count = 0
        category_set: set[str] = set()
        for line in valid_lines:
            if not isinstance(line, dict):
                continue
            category = str(line.get("category", "")).strip()
            if category:
                category_set.add(category)
            words = line.get("words", [])
            if isinstance(words, list):
                word_count += len(words)
                key_word_count += sum(1 for word in words if isinstance(word, dict) and word.get("is_key"))

        rows.append(
            {
                "benchmark": "CORD",
                "split": split,
                "document_id": image_id,
                "annotation_path": _repo_relative(path),
                "image_path": _repo_relative(image_path) if image_path else "",
                "line_count": str(len(valid_lines)),
                "word_count": str(word_count),
                "key_word_count": str(key_word_count),
                "entity_categories": " | ".join(sorted(category_set)),
                "wrapper_instruction": "Protect receipt fields that carry identifying or sensitive financial content while preserving task-relevant totals, item structure, and semantic layout cues.",
                "evaluation_slice": "receipt OCR matched transfer",
            }
        )
    return rows, split_counts


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_protocol(dataset_root: Path) -> None:
    protocol = {
        "benchmark": "CORD",
        "benchmark_family": "ocr-heavy receipt transfer",
        "status": "prepared_not_executed",
        "core_metrics": [
            "ocr_span_f1",
            "multimodal_per",
            "ac",
            "latency_ms",
        ],
        "expected_input": {
            "format": "CORD annotation JSON plus receipt image files or an equivalent pinned Hugging Face export",
            "required_fields": ["meta", "valid_line"],
            "recommended_cache_root": _repo_relative(dataset_root),
        },
        "wrapper_prompt_template": {
            "system_instruction": "You are evaluating OCR-heavy privacy mediation on receipt documents.",
            "user_prompt": "Protect identifying or sensitive receipt fields while preserving task-faithful structure and semantic totals. Return a sanitized OCR text view plus a concise receipt summary.",
        },
        "matched_comparators": [
            "Raw OCR text prompt",
            "OCR + regex masking",
            "OCR + generic de-identification",
            "Proposed multimodal mediation",
        ],
        "notes": [
            "The current public repository cache only contains the CORD README and a sample image unless a fuller dataset root is supplied.",
            "Promoting CORD to executed evidence still requires a pinned OCR engine/version manifest and a real annotation/image snapshot.",
        ],
    }
    PROTOCOL_PATH.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")


def build_surface(dataset_root: Path) -> tuple[Path, Path, Path, Path, Path]:
    write_protocol(dataset_root)
    wrapped_rows, split_counts = build_wrapped_manifest(dataset_root)
    image_count = sum(1 for path in dataset_root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    annotation_count = len([path for path in dataset_root.rglob("*.json") if _looks_like_annotation(path)])
    sample_only = annotation_count == 0

    preparation_rows = [
        {
            "benchmark": "CORD",
            "dataset_root": _repo_relative(dataset_root),
            "root_exists": "yes" if dataset_root.exists() else "no",
            "annotation_file_count": str(annotation_count),
            "image_file_count": str(image_count),
            "wrapper_manifest_rows": str(len(wrapped_rows)),
            "split_breakdown": " | ".join(f"{key}:{value}" for key, value in sorted(split_counts.items())),
            "current_surface": "sample_only_repo_archive" if sample_only else "wrapper_ready_dataset_surface",
            "notes": "Only README/sample assets are cached locally for CORD." if sample_only else "Wrapper-ready CORD manifest built from supplied annotations.",
        }
    ]
    write_csv(PREPARATION_MANIFEST_PATH, preparation_rows, list(preparation_rows[0].keys()))

    wrapped_fieldnames = [
        "benchmark",
        "split",
        "document_id",
        "annotation_path",
        "image_path",
        "line_count",
        "word_count",
        "key_word_count",
        "entity_categories",
        "wrapper_instruction",
        "evaluation_slice",
    ]
    write_csv(WRAPPED_MANIFEST_PATH, wrapped_rows, wrapped_fieldnames)

    execution_rows = [
        {
            "benchmark": "CORD",
            "method": "Raw OCR text prompt",
            "family": "No protection",
            "execution_status": "waiting_for_dataset_and_ocr" if sample_only else "waiting_for_ocr_runtime",
            "input_scope": "Pinned CORD snapshot required",
            "notes": "Needs a wrapper-ready export and exact OCR/runtime logging before execution.",
        },
        {
            "benchmark": "CORD",
            "method": "OCR + regex masking",
            "family": "Pattern baseline",
            "execution_status": "waiting_for_dataset_and_ocr" if sample_only else "waiting_for_ocr_runtime",
            "input_scope": "Pinned CORD snapshot required",
            "notes": "Needs OCR text extraction plus a filled OCR engine/version manifest.",
        },
        {
            "benchmark": "CORD",
            "method": "OCR + generic de-identification",
            "family": "Generic de-identification",
            "execution_status": "waiting_for_dataset_and_ocr" if sample_only else "waiting_for_ocr_runtime",
            "input_scope": "Pinned CORD snapshot required",
            "notes": "Needs OCR text extraction plus a bundled comparator implementation under the released wrapper.",
        },
        {
            "benchmark": "CORD",
            "method": "Proposed multimodal mediation",
            "family": "Policy-aware mediation",
            "execution_status": "waiting_for_dataset_and_ocr" if sample_only else "prepared_not_executed",
            "input_scope": "Pinned CORD snapshot required",
            "notes": "Wrapper surface is benchmark-specific here, but promotion to executed evidence still requires OCR/version and run-log fields.",
        },
    ]
    write_csv(EXECUTION_MANIFEST_PATH, execution_rows, list(execution_rows[0].keys()))

    run_log_rows = [
        {
            "benchmark": "CORD",
            "execution_status": "sample_only_repo_archive" if sample_only else "prepared_not_executed",
            "input_scope": "public repository metadata only" if sample_only else "wrapper-ready dataset surface",
            "document_count": str(len(wrapped_rows)),
            "split_breakdown": " | ".join(f"{key}:{value}" for key, value in sorted(split_counts.items())),
            "wrapper_manifest": WRAPPED_MANIFEST_PATH.name,
            "execution_manifest": EXECUTION_MANIFEST_PATH.name,
            "protocol": PROTOCOL_PATH.name,
            "runtime_template": "ocr_engine_runtime_manifest_template.csv",
            "command_template": "python src/experiments/build_cord_transfer_surface.py --dataset-root <pinned_cord_dataset_root>",
            "notes": "Current cache exposes only README/sample metadata for CORD; a fuller dataset snapshot must be pinned before OCR-heavy execution can start." if sample_only else "CORD wrapper surface prepared; next step is a filled OCR runtime manifest and executed rerun.",
        }
    ]
    write_csv(RUN_LOG_PATH, run_log_rows, list(run_log_rows[0].keys()))

    return (
        PREPARATION_MANIFEST_PATH,
        WRAPPED_MANIFEST_PATH,
        EXECUTION_MANIFEST_PATH,
        RUN_LOG_PATH,
        PROTOCOL_PATH,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a CORD-first OCR transfer surface.")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_CACHE_ROOT, help="Pinned local CORD dataset root or repo cache root")
    args = parser.parse_args()

    outputs = build_surface(args.dataset_root)
    for output in outputs:
        print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())