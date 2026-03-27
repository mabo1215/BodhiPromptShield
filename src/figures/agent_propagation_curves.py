"""
Generate a main-text propagation figure for the multi-step agent experiment.

The plot visualizes stage-wise propagation exposure (SPE) from Table XI.
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


def _load_rows():
    path = os.path.join(EXPERIMENTS_DIR, "agent_pipeline_metrics.csv")
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def plot_agent_propagation_curves(out_path: str):
    rows = _load_rows()
    stage_keys = ["retrieval", "memory", "tool"]
    stage_labels = ["Retrieval", "Memory", "Tool"]
    x = np.arange(len(stage_labels))

    method_styles = {
        "No protection": {"color": "#7F7F7F", "marker": "o"},
        "Regex-only": {"color": "#E45756", "marker": "s"},
        "Generic de-identification": {"color": "#4C78A8", "marker": "^"},
        "Proposed (boundary restoration)": {"color": "#54A24B", "marker": "D"},
    }

    fig, ax = plt.subplots(figsize=(3.45, 2.6))
    for row in rows:
        method = row["method"]
        values = [float(row[key]) for key in stage_keys]
        style = method_styles.get(method, {"color": "#333333", "marker": "o"})
        label = method.replace("Generic de-identification", "Generic de-id")
        label = label.replace("Proposed (boundary restoration)", "Proposed")
        ax.plot(
            x,
            values,
            linewidth=2.0,
            markersize=5.5,
            marker=style["marker"],
            color=style["color"],
            label=label,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(stage_labels, fontsize=8)
    ax.set_ylim(0, 105)
    ax.set_ylabel("SPE (%)", fontsize=9)
    ax.set_title("Propagation Across Agent Boundaries", fontsize=10)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=6.7, frameon=False, loc="upper right")

    plt.tight_layout()
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate the main-text propagation figure.")
    parser.add_argument("--out-dir", default=None, help="Output directory (default: repo_root/paper/fig)")
    args = parser.parse_args()

    out_dir = args.out_dir
    if out_dir is None:
        repo_root = os.path.dirname(os.path.dirname(SRC_DIR))
        out_dir = os.path.join(repo_root, "paper", "fig")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "agent_propagation_curves.png")
    plot_agent_propagation_curves(out_path)
    print("Saved", out_path)


if __name__ == "__main__":
    main()
