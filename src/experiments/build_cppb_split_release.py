#!/usr/bin/env python3
"""Build a deterministic CPPB train/dev/test release split."""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
TEMPLATE_INVENTORY_PATH = EXPERIMENTS_DIR / "cppb_template_inventory.csv"
PROMPT_MANIFEST_PATH = EXPERIMENTS_DIR / "cppb_prompt_manifest.csv"
SPLIT_MANIFEST_PATH = EXPERIMENTS_DIR / "cppb_split_manifest.csv"
SPLIT_SUMMARY_PATH = EXPERIMENTS_DIR / "cppb_split_summary.csv"
SPLIT_CARD_PATH = EXPERIMENTS_DIR / "cppb_split_release_card.md"

FAMILY_ORDER = [
    "Direct requests",
    "Document-oriented",
    "Retrieval-style",
    "Tool-oriented agent",
]

CATEGORY_ORDER = [
    "Person names",
    "Contact details",
    "Postal addresses",
    "National/account identifiers",
    "Financial references",
    "Medical content",
    "Organization/project terms",
    "Context-dependent confidential spans",
]

PATTERNS = [
    ("train", "train", "dev", "test"),
    ("train", "dev", "test", "train"),
    ("dev", "test", "train", "train"),
    ("test", "train", "train", "dev"),
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _share(count: int, total: int) -> str:
    return f"{(100.0 * count / total):.1f}"


def build_split_map(template_rows: list[dict[str, str]]) -> dict[str, str]:
    split_map: dict[str, str] = {}
    for row in template_rows:
        family_index = FAMILY_ORDER.index(row["prompt_family"])
        category_index = CATEGORY_ORDER.index(row["primary_privacy_category"])
        split_map[row["template_id"]] = PATTERNS[category_index % 4][family_index]
    return split_map


def build_manifest_rows(prompt_rows: list[dict[str, str]], split_map: dict[str, str]) -> list[dict[str, str]]:
    return [
        {
            "split": split_map[row["template_id"]],
            "template_id": row["template_id"],
            "prompt_id": row["prompt_id"],
            "variant_id": row["variant_id"],
            "prompt_family": row["prompt_family"],
            "prompt_source": row["prompt_source"],
            "downstream_task_type": row["downstream_task_type"],
            "primary_privacy_category": row["primary_privacy_category"],
            "subset": row["subset"],
            "modality": row["modality"],
            "split_rule": "template_stratified_family_category_rotation",
        }
        for row in prompt_rows
    ]


def build_summary_rows(template_rows: list[dict[str, str]], manifest_rows: list[dict[str, str]], split_map: dict[str, str]) -> list[dict[str, str]]:
    total_prompts = len(manifest_rows)
    summary_rows: list[dict[str, str]] = []
    for order, split in enumerate(["train", "dev", "test"], start=1):
        split_templates = [row for row in template_rows if split_map[row["template_id"]] == split]
        split_prompts = [row for row in manifest_rows if row["split"] == split]
        family_counts = Counter(row["prompt_family"] for row in split_templates)
        category_counts = Counter(row["primary_privacy_category"] for row in split_templates)
        subset_counts = Counter(row["subset"] for row in split_prompts)
        modality_counts = Counter(row["modality"] for row in split_prompts)
        summary_rows.extend(
            [
                {"split_order": str(order), "split": split, "axis": "Template count", "breakdown": str(len(split_templates))},
                {"split_order": str(order), "split": split, "axis": "Prompt count", "breakdown": f"{len(split_prompts)} ({_share(len(split_prompts), total_prompts)}%)"},
                {"split_order": str(order), "split": split, "axis": "Prompt families", "breakdown": "; ".join(f"{name} {family_counts[name]}" for name in FAMILY_ORDER)},
                {"split_order": str(order), "split": split, "axis": "Privacy categories", "breakdown": "; ".join(f"{name} {category_counts[name]}" for name in CATEGORY_ORDER)},
                {"split_order": str(order), "split": split, "axis": "Subsets", "breakdown": "; ".join(f"{name} {subset_counts[name]}" for name in ["Essential-privacy", "Incidental-privacy"])},
                {"split_order": str(order), "split": split, "axis": "Modality", "breakdown": "; ".join(f"{name} {modality_counts[name]}" for name in ["Text-only", "OCR-mediated text-plus-image"])},
            ]
        )
    return summary_rows


def build_release_card(template_rows: list[dict[str, str]], manifest_rows: list[dict[str, str]], split_map: dict[str, str]) -> str:
    template_counts = Counter(split_map.values())
    prompt_counts = Counter(row["split"] for row in manifest_rows)
    return "\n".join(
        [
            "# CPPB Split Release Card",
            "",
            "## Split Rule",
            "",
            "- The released split is template-stratified: all eight variants of one template stay in the same split.",
            "- The deterministic assignment rule is `template_stratified_family_category_rotation`.",
            "- Each split retains all four prompt families and all eight privacy categories.",
            "",
            "## Released Counts",
            "",
            f"- Train: {template_counts['train']} templates / {prompt_counts['train']} prompts",
            f"- Dev: {template_counts['dev']} templates / {prompt_counts['dev']} prompts",
            f"- Test: {template_counts['test']} templates / {prompt_counts['test']} prompts",
            "",
            "## Intended Use",
            "",
            "- Train: future detector/router fitting or prompt-policy learning on a template-disjoint slice.",
            "- Dev: threshold/profile selection and ablation tuning without touching the final held-out slice.",
            "- Test: final report-only evaluation under the released template-disjoint protocol.",
            "",
            "## Leakage Boundary",
            "",
            "- No template crosses splits.",
            "- Because all variants of a template remain co-located, the split prevents variant-level leakage between train/dev/test.",
            "- The current paper still reports the legacy matched full-release CPPB aggregates for continuity, but the released split surface is now available for stricter future selection/evaluation separation.",
            "",
        ]
    )


def main() -> None:
    template_rows = _read_csv(TEMPLATE_INVENTORY_PATH)
    prompt_rows = _read_csv(PROMPT_MANIFEST_PATH)
    split_map = build_split_map(template_rows)
    manifest_rows = build_manifest_rows(prompt_rows, split_map)
    summary_rows = build_summary_rows(template_rows, manifest_rows, split_map)
    _write_csv(
        SPLIT_MANIFEST_PATH,
        manifest_rows,
        [
            "split",
            "template_id",
            "prompt_id",
            "variant_id",
            "prompt_family",
            "prompt_source",
            "downstream_task_type",
            "primary_privacy_category",
            "subset",
            "modality",
            "split_rule",
        ],
    )
    _write_csv(SPLIT_SUMMARY_PATH, summary_rows, ["split_order", "split", "axis", "breakdown"])
    SPLIT_CARD_PATH.write_text(build_release_card(template_rows, manifest_rows, split_map), encoding="utf-8")
    print(f"CPPB split manifest written to {SPLIT_MANIFEST_PATH}")
    print(f"CPPB split summary written to {SPLIT_SUMMARY_PATH}")
    print(f"CPPB split release card written to {SPLIT_CARD_PATH}")


if __name__ == "__main__":
    main()