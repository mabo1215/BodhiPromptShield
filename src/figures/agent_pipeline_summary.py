"""
Generate a supplementary deployment-summary figure for prompt privacy mediation.

Panel A: stage-wise propagation exposure from Table XI.
Panel B: latency overhead from Table XII.
"""
import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
EXPERIMENTS_DIR = os.path.join(SRC_DIR, "experiments")


def _load_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def plot_agent_pipeline_summary(out_path: str):
    propagation = _load_csv(os.path.join(EXPERIMENTS_DIR, "agent_pipeline_metrics.csv"))
    latency = _load_csv(os.path.join(EXPERIMENTS_DIR, "latency_overhead.csv"))

    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.5))

    ax = axes[0]
    stage_names = ["retrieval", "memory", "tool"]
    stage_labels = ["Retrieval", "Memory", "Tool"]
    x = np.arange(len(propagation))
    width = 0.22
    colors = ["#4C78A8", "#72B7B2", "#F58518"]
    for idx, (stage_key, stage_label, color) in enumerate(zip(stage_names, stage_labels, colors)):
        values = [float(row[stage_key]) for row in propagation]
        ax.bar(x + (idx - 1) * width, values, width=width, color=color, label=stage_label)
    ax.set_xticks(x)
    ax.set_xticklabels(
        ["No protection", "Regex-only", "Generic de-id", "Proposed"],
        rotation=18,
        ha="right",
        fontsize=8,
    )
    ax.set_ylim(0, 108)
    ax.set_ylabel("SPE (%)", fontsize=9)
    ax.set_title("Stage-Wise Propagation Exposure", fontsize=10)
    ax.legend(fontsize=7, frameon=False)
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1]
    labels = [
        "Raw",
        "Regex",
        "NER",
        "Balanced",
        "Aggressive",
    ]
    mean_vals = [float(row["mean_ms"]) for row in latency]
    p95_vals = [float(row["p95_ms"]) for row in latency]
    x = np.arange(len(labels))
    width = 0.34
    ax.bar(x - width / 2, mean_vals, width=width, color="#54A24B", label="Mean")
    ax.bar(x + width / 2, p95_vals, width=width, color="#E45756", label="P95")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=18, ha="right", fontsize=8)
    ax.set_ylabel("Latency (ms)", fontsize=9)
    ax.set_title("Runtime Overhead", fontsize=10)
    ax.legend(fontsize=7, frameon=False)
    ax.grid(True, axis="y", alpha=0.25)

    fig.suptitle("Deployment Summary for Prompt Privacy Mediation", fontsize=11, y=1.02)
    plt.tight_layout()
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate deployment summary figure for prompt privacy mediation.")
    parser.add_argument("--out-dir", default=None, help="Output directory (default: repo_root/paper/figs)")
    args = parser.parse_args()

    out_dir = args.out_dir
    if out_dir is None:
        repo_root = os.path.dirname(os.path.dirname(SRC_DIR))
        out_dir = os.path.join(repo_root, "paper", "figs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "agent_pipeline_summary.png")
    plot_agent_pipeline_summary(out_path)
    print("Saved", out_path)


if __name__ == "__main__":
    main()
