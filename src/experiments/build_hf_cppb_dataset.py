#!/usr/bin/env python3
"""Build a Hugging Face-ready CPPB dataset bundle and optionally upload it."""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from textwrap import dedent

from datasets import Dataset, DatasetDict
from huggingface_hub import HfApi


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = EXPERIMENTS_DIR / "hf_cppb_dataset"
PROMPT_MANIFEST_PATH = EXPERIMENTS_DIR / "cppb_prompt_manifest.csv"
SPLIT_MANIFEST_PATH = EXPERIMENTS_DIR / "cppb_split_manifest.csv"
SPLIT_SUMMARY_PATH = EXPERIMENTS_DIR / "cppb_split_summary.csv"
ACCOUNTING_SUMMARY_PATH = EXPERIMENTS_DIR / "cppb_accounting_summary.csv"
SOURCE_LICENSE_PATH = EXPERIMENTS_DIR / "cppb_source_licensing_manifest.csv"
RELEASE_CARD_PATH = EXPERIMENTS_DIR / "cppb_release_card.md"
SPLIT_CARD_PATH = EXPERIMENTS_DIR / "cppb_split_release_card.md"
ARXIV_URL = "https://arxiv.org/abs/2604.05793"
PAPER_TITLE = "BodhiPromptShield: Pre-Inference Prompt Mediation for Suppressing Privacy Propagation in LLM/VLM Agents"

DATA_FIELDS = [
    "prompt_id",
    "template_id",
    "variant_id",
    "prompt_family",
    "prompt_source",
    "downstream_task_type",
    "primary_privacy_category",
    "subset",
    "modality",
    "template_stub",
    "prompt_stub",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _copy_if_exists(src: Path, dest: Path) -> None:
    if src.exists():
        shutil.copy2(src, dest)


def _normalize_row(row: dict[str, str], split: str) -> dict[str, str]:
    normalized = {field: row[field] for field in DATA_FIELDS}
    normalized["split"] = split
    normalized["release_scope"] = "prompt-stub-manifest"
    normalized["raw_prompt_released"] = "no"
    normalized["ocr_source_asset_released"] = "no"
    normalized["paper_title"] = PAPER_TITLE
    normalized["paper_url"] = ARXIV_URL
    return normalized


def build_rows() -> tuple[list[dict[str, str]], dict[str, list[dict[str, str]]]]:
    prompt_rows = _read_csv(PROMPT_MANIFEST_PATH)
    split_rows = _read_csv(SPLIT_MANIFEST_PATH)
    prompt_map = {row["prompt_id"]: row for row in prompt_rows}
    split_to_rows: dict[str, list[dict[str, str]]] = {"train": [], "dev": [], "test": []}
    all_rows: list[dict[str, str]] = []

    for split_row in split_rows:
        prompt_id = split_row["prompt_id"]
        prompt_row = prompt_map[prompt_id]
        normalized = _normalize_row(prompt_row, split_row["split"])
        split_to_rows[split_row["split"]].append(normalized)
        all_rows.append(normalized)

    return all_rows, split_to_rows


def build_metadata(all_rows: list[dict[str, str]]) -> dict[str, object]:
    family_counts = Counter(row["prompt_family"] for row in all_rows)
    category_counts = Counter(row["primary_privacy_category"] for row in all_rows)
    subset_counts = Counter(row["subset"] for row in all_rows)
    modality_counts = Counter(row["modality"] for row in all_rows)
    split_counts = Counter(row["split"] for row in all_rows)
    template_count = len({row["template_id"] for row in all_rows})

    return {
        "dataset_name": "CPPB",
        "pretty_name": "Controlled Prompt-Privacy Benchmark",
        "paper_title": PAPER_TITLE,
        "paper_url": ARXIV_URL,
        "release_scope": "prompt-stub-manifest",
        "raw_prompt_release": False,
        "ocr_source_asset_release": False,
        "total_rows": len(all_rows),
        "template_count": template_count,
        "split_counts": dict(split_counts),
        "subset_counts": dict(subset_counts),
        "prompt_family_counts": dict(family_counts),
        "primary_privacy_category_counts": dict(category_counts),
        "modality_counts": dict(modality_counts),
        "row_schema": DATA_FIELDS + [
            "split",
            "release_scope",
            "raw_prompt_released",
            "ocr_source_asset_released",
            "paper_title",
            "paper_url",
        ],
    }


def build_readme(metadata: dict[str, object]) -> str:
    split_counts = metadata["split_counts"]
    return dedent(
        f"""\
        ---
        language:
        - en
        pretty_name: Controlled Prompt-Privacy Benchmark
        size_categories:
        - n<1K
        task_categories:
        - text-generation
        - text-classification
        task_ids:
        - named-entity-recognition
        - document-question-answering
        - text2text-generation
        tags:
        - privacy
        - prompt-security
        - de-identification
        - redaction
        - llm-agents
        - evaluation
        license: other
        configs:
        - config_name: default
          data_files:
          - split: train
            path: data/train.csv
          - split: validation
            path: data/dev.csv
          - split: test
            path: data/test.csv
        ---

        # CPPB

        ## Summary

        CPPB is the public release surface for the Controlled Prompt-Privacy Benchmark introduced in [{PAPER_TITLE}]({ARXIV_URL}).

        This Hugging Face package intentionally releases the benchmark-authored prompt manifest and template-stratified train/dev/test split, not raw third-party prompts, source images, or end-to-end OCR assets. Each row is a controlled prompt stub with benchmark metadata that supports reproducible accounting, split-auditability, and benchmark discoverability.

        ## What Is Released

        - 256 benchmark-authored prompt-manifest rows derived from 32 templates x 8 variants.
        - Deterministic template-disjoint `train` / `dev` / `test` split: {split_counts['train']} / {split_counts['dev']} / {split_counts['test']} rows.
        - Prompt-family, privacy-category, subset, modality, and provenance fields needed to reconstruct the released benchmark card.
        - Companion release notes and licensing/provenance manifests in the repository bundle.

        ## What Is Not Released

        - Raw user prompts or third-party prompt payloads.
        - Original OCR source assets, screenshots, or scanned documents.
        - Licensed clinical notes or private operational logs.
        - Exact multimodal regeneration assets beyond the released manifest surface.

        ## Dataset Structure

        Main columns:

        - `prompt_id`: unique prompt instance identifier.
        - `template_id`: template identifier shared across the eight fixed variants.
        - `variant_id`: one of `V1`-`V8`.
        - `prompt_family`: one of Direct requests, Document-oriented, Retrieval-style, Tool-oriented agent.
        - `prompt_source`: benchmark-authored source family.
        - `downstream_task_type`: Prompt QA, Document QA, Retrieval QA, or Agent execution.
        - `primary_privacy_category`: dominant protected-content category.
        - `subset`: Essential-privacy or Incidental-privacy.
        - `modality`: Text-only or OCR-mediated text-plus-image.
        - `template_stub`: compact template-level description.
        - `prompt_stub`: compact prompt-instance description.
        - `split`: released split membership.

        ## Intended Use

        - Benchmark accounting and public discoverability for the CPPB release surface.
        - Template-disjoint train/dev/test selection for future detector or routing research.
        - Evaluation protocol alignment with the BodhiPromptShield paper.

        ## Limitations

        This package is a controlled benchmark manifest, not a full raw-prompt corpus. It should be interpreted as a benchmark-authored release card surface that preserves provenance, split semantics, and release boundaries. If you need end-to-end multimodal regeneration assets or licensed external benchmark inputs, use the repository protocols instead of this Hugging Face package.

        ## Citation

        ```bibtex
        @article{{ma2026bodhipromptshield,
          title={{BodhiPromptShield: Pre-Inference Prompt Mediation for Suppressing Privacy Propagation in LLM/VLM Agents}},
          author={{Ma, Bo and Wu, Jinsong and Yan, Weiqi}},
          journal={{arXiv preprint arXiv:2604.05793}},
          year={{2026}},
          url={{https://arxiv.org/abs/2604.05793}}
        }}
        ```

        ## Repository

        - GitHub: https://github.com/mabo1215/BodhiPromptShield
        - Paper: {ARXIV_URL}
        - Release source files: `src/experiments/cppb_*`
        """
    ).strip() + "\n"


def write_bundle(output_dir: Path) -> dict[str, object]:
    all_rows, split_to_rows = build_rows()
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    metadata_dir = output_dir / "metadata"
    data_dir.mkdir(exist_ok=True)
    metadata_dir.mkdir(exist_ok=True)

    fieldnames = DATA_FIELDS + [
        "split",
        "release_scope",
        "raw_prompt_released",
        "ocr_source_asset_released",
        "paper_title",
        "paper_url",
    ]

    _write_csv(data_dir / "all.csv", all_rows, fieldnames)
    _write_csv(data_dir / "train.csv", split_to_rows["train"], fieldnames)
    _write_csv(data_dir / "dev.csv", split_to_rows["dev"], fieldnames)
    _write_csv(data_dir / "test.csv", split_to_rows["test"], fieldnames)

    metadata = build_metadata(all_rows)
    _write_json(metadata_dir / "dataset_info.json", metadata)
    _copy_if_exists(SPLIT_SUMMARY_PATH, metadata_dir / SPLIT_SUMMARY_PATH.name)
    _copy_if_exists(ACCOUNTING_SUMMARY_PATH, metadata_dir / ACCOUNTING_SUMMARY_PATH.name)
    _copy_if_exists(SOURCE_LICENSE_PATH, metadata_dir / SOURCE_LICENSE_PATH.name)
    _copy_if_exists(RELEASE_CARD_PATH, metadata_dir / RELEASE_CARD_PATH.name)
    _copy_if_exists(SPLIT_CARD_PATH, metadata_dir / SPLIT_CARD_PATH.name)
    (output_dir / "README.md").write_text(build_readme(metadata), encoding="utf-8")

    return metadata


def upload_bundle(output_dir: Path, repo_id: str, private: bool) -> None:
    api = HfApi()
    api.create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(output_dir),
        commit_message="Add CPPB dataset release bundle",
    )


def push_with_datasets(output_dir: Path, repo_id: str, private: bool) -> None:
    dataset_dict = DatasetDict(
        {
            "train": Dataset.from_csv(str(output_dir / "data" / "train.csv")),
            "validation": Dataset.from_csv(str(output_dir / "data" / "dev.csv")),
            "test": Dataset.from_csv(str(output_dir / "data" / "test.csv")),
        }
    )
    dataset_dict.push_to_hub(repo_id, private=private)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Destination directory for the Hugging Face-ready bundle.",
    )
    parser.add_argument(
        "--repo-id",
        default="",
        help="Optional Hugging Face dataset repo id, for example username/CPPB.",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload the generated bundle to the Hugging Face dataset repo with huggingface_hub.",
    )
    parser.add_argument(
        "--push-with-datasets",
        action="store_true",
        help="Push split tables as a DatasetDict after the bundle is generated.",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create or push to a private dataset repo instead of a public one.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the existing output directory before regenerating the bundle.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()

    if args.clean and output_dir.exists():
        shutil.rmtree(output_dir)

    metadata = write_bundle(output_dir)
    print(f"CPPB Hugging Face bundle written to {output_dir}")
    print(f"Total rows: {metadata['total_rows']}")
    print(f"Split counts: {metadata['split_counts']}")

    if args.upload or args.push_with_datasets:
        if not args.repo_id:
            raise SystemExit("--repo-id is required when using --upload or --push-with-datasets")

    if args.upload:
        upload_bundle(output_dir, args.repo_id, args.private)
        print(f"Uploaded bundle files to dataset repo {args.repo_id}")

    if args.push_with_datasets:
        push_with_datasets(output_dir, args.repo_id, args.private)
        print(f"Pushed DatasetDict splits to dataset repo {args.repo_id}")


if __name__ == "__main__":
    main()