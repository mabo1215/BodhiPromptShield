"""
Generate a repository-backed benchmark-composition figure for CPPB.

The figure summarizes:
  - total prompt/template accounting,
  - subset and modality balance,
  - prompt family / prompt source balance,
  - privacy-category coverage.
"""
import argparse
import csv
import os
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
EXPERIMENTS_DIR = os.path.join(SRC_DIR, "experiments")


def _load_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _group_rows(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["group_name"], []).append(row)
    return grouped


def _summary_lookup(rows):
    return {row["axis"]: row["breakdown"] for row in rows}


def _wrap_labels(labels, width):
    return [textwrap.fill(label, width=width) for label in labels]


def _draw_segmented_bar(ax, y, values, colors, labels, total):
    left = 0
    for value, color, label in zip(values, colors, labels):
        ax.barh([y], [value], left=left, color=color, height=0.42)
        x = left + value / 2
        ax.text(
            x,
            y,
            f"{label}\n{value} ({(value / total) * 100:.1f}%)",
            ha="center",
            va="center",
            fontsize=8,
            color="white" if value / total >= 0.22 else "#222222",
            fontweight="bold" if value / total >= 0.22 else None,
        )
        left += value


def plot_cppb_benchmark_composition(out_path: str):
    breakdown_rows = _load_csv(os.path.join(EXPERIMENTS_DIR, "cppb_distribution_breakdown.csv"))
    summary_rows = _load_csv(os.path.join(EXPERIMENTS_DIR, "cppb_accounting_summary.csv"))

    grouped = _group_rows(breakdown_rows)
    summary = _summary_lookup(summary_rows)

    total_prompts = 256
    summary_lines = [
        ("Benchmark total", summary["Benchmark total"]),
        ("Template/variant", summary["Template/variant accounting"]),
        ("Subsets", summary["Subsets"]),
        ("Modality", summary["Modality"]),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(10.0, 6.3))
    fig.patch.set_facecolor("white")

    ax = axes[0, 0]
    ax.axis("off")
    ax.set_title("Accounting Snapshot", fontsize=11, loc="left")
    y = 0.94
    for title, value in summary_lines:
        ax.text(0.0, y, title, fontsize=9, fontweight="bold", color="#1F2A44", va="top")
        ax.text(0.0, y - 0.09, textwrap.fill(value, width=44), fontsize=9, color="#333333", va="top")
        y -= 0.22
    ax.text(
        0.0,
        0.05,
        "CPPB is designed as a balanced controlled benchmark specification rather\n"
        "than as a single prompt family or single privacy-category slice.",
        fontsize=9,
        color="#4F5B66",
        va="bottom",
    )

    ax = axes[0, 1]
    ax.set_title("Subset and Modality Balance", fontsize=11, loc="left")
    subset_rows = sorted(grouped["subset"], key=lambda row: int(row["item_order"]))
    modality_rows = sorted(grouped["modality"], key=lambda row: int(row["item_order"]))
    _draw_segmented_bar(
        ax,
        1,
        [int(row["count"]) for row in subset_rows],
        ["#4C78A8", "#F58518"],
        [row["item"].replace("-privacy", "") for row in subset_rows],
        total_prompts,
    )
    _draw_segmented_bar(
        ax,
        0,
        [int(row["count"]) for row in modality_rows],
        ["#E45756", "#54A24B"],
        ["OCR-mediated", "Text-only"],
        total_prompts,
    )
    ax.set_xlim(0, total_prompts)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Modality", "Subset"], fontsize=9)
    ax.set_xlabel("Prompt count", fontsize=9)
    ax.grid(True, axis="x", alpha=0.22)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)

    ax = axes[1, 0]
    ax.set_title("Prompt Families and Sources", fontsize=11, loc="left")
    family_rows = sorted(grouped["prompt_family"], key=lambda row: int(row["item_order"]))
    source_rows = sorted(grouped["prompt_source"], key=lambda row: int(row["item_order"]))
    combined_labels = [f"Family: {row['item']}" for row in family_rows] + [
        f"Source: {row['item']}" for row in source_rows
    ]
    combined_values = [int(row["count"]) for row in family_rows] + [int(row["count"]) for row in source_rows]
    colors = ["#72B7B2"] * len(family_rows) + ["#B279A2"] * len(source_rows)
    y_positions = list(range(len(combined_labels)))
    ax.barh(y_positions, combined_values, color=colors)
    ax.set_yticks(y_positions)
    ax.set_yticklabels(_wrap_labels(combined_labels, width=22), fontsize=8)
    ax.set_xlim(0, 72)
    ax.set_xlabel("Prompt count", fontsize=9)
    ax.grid(True, axis="x", alpha=0.22)
    ax.invert_yaxis()
    for y_pos, value in zip(y_positions, combined_values):
        ax.text(value + 1.5, y_pos, str(value), va="center", fontsize=8, color="#333333")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    ax = axes[1, 1]
    ax.set_title("Privacy-Category Coverage", fontsize=11, loc="left")
    category_rows = sorted(grouped["primary_privacy_category"], key=lambda row: int(row["item_order"]))
    category_labels = _wrap_labels([row["item"] for row in category_rows], width=18)
    category_values = [int(row["count"]) for row in category_rows]
    ax.bar(range(len(category_labels)), category_values, color="#9D755D")
    ax.set_xticks(range(len(category_labels)))
    ax.set_xticklabels(category_labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Prompt count", fontsize=9)
    ax.set_ylim(0, 36)
    ax.grid(True, axis="y", alpha=0.22)
    for idx, value in enumerate(category_values):
        ax.text(idx, value + 0.6, str(value), ha="center", va="bottom", fontsize=8, color="#333333")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.suptitle("CPPB Benchmark Composition and Balance", fontsize=12, y=0.995)
    plt.tight_layout()
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate CPPB benchmark composition figure.")
    parser.add_argument("--out-dir", default=None, help="Output directory (default: repo_root/paper/fig)")
    args = parser.parse_args()

    out_dir = args.out_dir
    if out_dir is None:
        repo_root = os.path.dirname(os.path.dirname(SRC_DIR))
        out_dir = os.path.join(repo_root, "paper", "fig")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "cppb_benchmark_composition.png")
    plot_cppb_benchmark_composition(out_path)
    print("Saved", out_path)


if __name__ == "__main__":
    main()
