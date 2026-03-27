"""
Build a deterministic CPPB prompt manifest and benchmark-accounting summaries.

Outputs under src/experiments/:
  - cppb_template_inventory.csv
  - cppb_prompt_manifest.csv
  - cppb_distribution_breakdown.csv
  - cppb_accounting_summary.csv

The manifest is intentionally lightweight: it provides an auditable benchmark
card for prompt counts, subset balance, prompt-source balance, modality split,
and template/variant accounting used by the manuscript. It does not attempt to
recreate every downstream model run or annotation artifact.
"""
from __future__ import annotations

import csv
import os
from collections import Counter


EXPERIMENTS_DIR = os.path.dirname(os.path.abspath(__file__))


FAMILIES = [
    {
        "key": "direct",
        "label": "Direct requests",
        "source": "Dialogue templates",
        "task_type": "Prompt QA",
        "template_stub": "Direct request centered on {category}.",
    },
    {
        "key": "document",
        "label": "Document-oriented",
        "source": "Document scenarios",
        "task_type": "Document QA",
        "template_stub": "Document-oriented instruction centered on {category}.",
    },
    {
        "key": "retrieval",
        "label": "Retrieval-style",
        "source": "Public task sources",
        "task_type": "Retrieval QA",
        "template_stub": "Retrieval-style prompt centered on {category}.",
    },
    {
        "key": "tool",
        "label": "Tool-oriented agent",
        "source": "Agent workflow traces",
        "task_type": "Agent execution",
        "template_stub": "Tool-oriented agent prompt centered on {category}.",
    },
]


CATEGORIES = [
    {"key": "person_name", "label": "Person names"},
    {"key": "contact_detail", "label": "Contact details"},
    {"key": "postal_address", "label": "Postal addresses"},
    {"key": "national_account_id", "label": "National/account identifiers"},
    {"key": "financial_reference", "label": "Financial references"},
    {"key": "medical_content", "label": "Medical content"},
    {"key": "organization_project_term", "label": "Organization/project terms"},
    {"key": "context_confidential", "label": "Context-dependent confidential spans"},
]


VARIANTS = [
    {
        "variant_id": "V1",
        "subset": "Essential-privacy",
        "modality": "Text-only",
        "variant_stub": "Task-critical text-only variant",
    },
    {
        "variant_id": "V2",
        "subset": "Essential-privacy",
        "modality": "Text-only",
        "variant_stub": "Reasoning-preserving text-only variant",
    },
    {
        "variant_id": "V3",
        "subset": "Essential-privacy",
        "modality": "Text-only",
        "variant_stub": "Tool-compatible text-only variant",
    },
    {
        "variant_id": "V4",
        "subset": "Essential-privacy",
        "modality": "OCR-mediated text-plus-image",
        "variant_stub": "Task-critical OCR-mediated variant",
    },
    {
        "variant_id": "V5",
        "subset": "Incidental-privacy",
        "modality": "Text-only",
        "variant_stub": "Incidental text-only summary variant",
    },
    {
        "variant_id": "V6",
        "subset": "Incidental-privacy",
        "modality": "Text-only",
        "variant_stub": "Incidental text-only coordination variant",
    },
    {
        "variant_id": "V7",
        "subset": "Incidental-privacy",
        "modality": "Text-only",
        "variant_stub": "Incidental text-only logging variant",
    },
    {
        "variant_id": "V8",
        "subset": "Incidental-privacy",
        "modality": "OCR-mediated text-plus-image",
        "variant_stub": "Incidental OCR-mediated variant",
    },
]


def _write_csv(path: str, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fmt_share(count: int, total: int) -> str:
    return f"{(count / total) * 100:.1f}"


def build_inventory_and_manifest() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    template_rows: list[dict[str, str]] = []
    prompt_rows: list[dict[str, str]] = []

    template_index = 1
    for family in FAMILIES:
        for category in CATEGORIES:
            template_id = f"T{template_index:02d}"
            template_stub = family["template_stub"].format(category=category["label"].lower())
            template_rows.append(
                {
                    "template_id": template_id,
                    "prompt_family": family["label"],
                    "prompt_source": family["source"],
                    "downstream_task_type": family["task_type"],
                    "primary_privacy_category": category["label"],
                    "template_stub": template_stub,
                }
            )
            for variant in VARIANTS:
                prompt_rows.append(
                    {
                        "prompt_id": f"{template_id}-{variant['variant_id']}",
                        "template_id": template_id,
                        "variant_id": variant["variant_id"],
                        "prompt_family": family["label"],
                        "prompt_source": family["source"],
                        "downstream_task_type": family["task_type"],
                        "primary_privacy_category": category["label"],
                        "subset": variant["subset"],
                        "modality": variant["modality"],
                        "template_stub": template_stub,
                        "prompt_stub": (
                            f"{template_stub} "
                            f"{variant['variant_stub']}."
                        ),
                    }
                )
            template_index += 1

    return template_rows, prompt_rows


def build_distribution_rows(prompt_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    total = len(prompt_rows)
    group_order = [
        ("subset", "subset"),
        ("prompt_family", "prompt_family"),
        ("primary_privacy_category", "primary_privacy_category"),
        ("prompt_source", "prompt_source"),
        ("modality", "modality"),
    ]

    rows: list[dict[str, str]] = []
    for order, (group_name, field_name) in enumerate(group_order, start=1):
        counts = Counter(row[field_name] for row in prompt_rows)
        for item_order, item in enumerate(sorted(counts), start=1):
            count = counts[item]
            rows.append(
                {
                    "group_order": str(order),
                    "item_order": str(item_order),
                    "group_name": group_name,
                    "item": item,
                    "count": str(count),
                    "share_percent": _fmt_share(count, total),
                }
            )
    return rows


def _join_breakdown(items: list[tuple[str, int]], total: int) -> str:
    return "; ".join(
        f"{label} {count} ({_fmt_share(count, total)}%)" for label, count in items
    )


def build_accounting_summary(
    template_rows: list[dict[str, str]], prompt_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    total = len(prompt_rows)
    subset_counts = Counter(row["subset"] for row in prompt_rows)
    family_counts = Counter(row["prompt_family"] for row in prompt_rows)
    category_counts = Counter(row["primary_privacy_category"] for row in prompt_rows)
    source_counts = Counter(row["prompt_source"] for row in prompt_rows)
    modality_counts = Counter(row["modality"] for row in prompt_rows)

    rows = [
        {
            "order": "1",
            "axis": "Benchmark total",
            "breakdown": f"{total} prompts",
        },
        {
            "order": "2",
            "axis": "Subsets",
            "breakdown": _join_breakdown(
                [
                    ("Essential-privacy", subset_counts["Essential-privacy"]),
                    ("Incidental-privacy", subset_counts["Incidental-privacy"]),
                ],
                total,
            ),
        },
        {
            "order": "3",
            "axis": "Prompt families",
            "breakdown": _join_breakdown(
                [
                    ("Direct requests", family_counts["Direct requests"]),
                    ("Document-oriented", family_counts["Document-oriented"]),
                    ("Retrieval-style", family_counts["Retrieval-style"]),
                    ("Tool-oriented agent", family_counts["Tool-oriented agent"]),
                ],
                total,
            ),
        },
        {
            "order": "4",
            "axis": "Privacy categories",
            "breakdown": _join_breakdown(
                [
                    ("Person names", category_counts["Person names"]),
                    ("Contact details", category_counts["Contact details"]),
                    ("Postal addresses", category_counts["Postal addresses"]),
                    (
                        "National/account identifiers",
                        category_counts["National/account identifiers"],
                    ),
                    ("Financial references", category_counts["Financial references"]),
                    ("Medical content", category_counts["Medical content"]),
                    (
                        "Organization/project terms",
                        category_counts["Organization/project terms"],
                    ),
                    (
                        "Context-dependent confidential spans",
                        category_counts["Context-dependent confidential spans"],
                    ),
                ],
                total,
            ),
        },
        {
            "order": "5",
            "axis": "Prompt sources",
            "breakdown": _join_breakdown(
                [
                    ("Dialogue templates", source_counts["Dialogue templates"]),
                    ("Public task sources", source_counts["Public task sources"]),
                    ("Document scenarios", source_counts["Document scenarios"]),
                    ("Agent workflow traces", source_counts["Agent workflow traces"]),
                ],
                total,
            ),
        },
        {
            "order": "6",
            "axis": "Modality",
            "breakdown": _join_breakdown(
                [
                    ("Text-only", modality_counts["Text-only"]),
                    (
                        "OCR-mediated text-plus-image",
                        modality_counts["OCR-mediated text-plus-image"],
                    ),
                ],
                total,
            ),
        },
        {
            "order": "7",
            "axis": "Template/variant accounting",
            "breakdown": f"{len(template_rows)} templates x {len(VARIANTS)} injected variants",
        },
    ]
    return rows


def main() -> int:
    template_rows, prompt_rows = build_inventory_and_manifest()
    distribution_rows = build_distribution_rows(prompt_rows)
    summary_rows = build_accounting_summary(template_rows, prompt_rows)

    _write_csv(
        os.path.join(EXPERIMENTS_DIR, "cppb_template_inventory.csv"),
        template_rows,
        [
            "template_id",
            "prompt_family",
            "prompt_source",
            "downstream_task_type",
            "primary_privacy_category",
            "template_stub",
        ],
    )
    _write_csv(
        os.path.join(EXPERIMENTS_DIR, "cppb_prompt_manifest.csv"),
        prompt_rows,
        [
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
        ],
    )
    _write_csv(
        os.path.join(EXPERIMENTS_DIR, "cppb_distribution_breakdown.csv"),
        distribution_rows,
        [
            "group_order",
            "item_order",
            "group_name",
            "item",
            "count",
            "share_percent",
        ],
    )
    _write_csv(
        os.path.join(EXPERIMENTS_DIR, "cppb_accounting_summary.csv"),
        summary_rows,
        ["order", "axis", "breakdown"],
    )

    print("Wrote CPPB manifest, inventory, and accounting summaries to", EXPERIMENTS_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
