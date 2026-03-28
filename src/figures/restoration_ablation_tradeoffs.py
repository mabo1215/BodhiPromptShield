"""
Generate a supporting figure for restoration timing and sanitization-mode trade-offs.

Panel A: restoration-boundary BLR/TSR trade-off.
Panel B: sanitization-mode exposure-reduction/UPR trade-off.
"""
import argparse
import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
EXPERIMENTS_DIR = os.path.join(SRC_DIR, "experiments")


def _load_csv(name: str) -> list[dict[str, str]]:
    path = os.path.join(EXPERIMENTS_DIR, name)
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _exposure_reduction(per_value: str) -> float:
    return 100.0 - float(per_value)


def plot_restoration_ablation_tradeoffs(out_path: str) -> None:
    restoration = _load_csv("restoration_boundary_analysis.csv")
    ablation = _load_csv("sanitization_mode_ablation.csv")

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3))

    ax = axes[0]
    rest_colors = {
        "No restoration": "#9D755D",
        "Late boundary restoration (proposed)": "#54A24B",
        "Early restoration (before memory/tool planning)": "#E45756",
    }
    for row in restoration:
        x = float(row["blr"])
        y = float(row["tsr"])
        label = row["setting"]
        short_label = (
            label.replace("Late boundary restoration (proposed)", "Late restoration")
            .replace("Early restoration (before memory/tool planning)", "Early restoration")
        )
        ax.scatter(
            x,
            y,
            s=58,
            c=rest_colors.get(label, "#4C78A8"),
            edgecolors="black",
            linewidths=0.4,
            zorder=3,
        )
        ax.annotate(short_label, (x, y), xytext=(4, 4), textcoords="offset points", fontsize=7)
    ax.set_title("Restoration Boundary Trade-Off", fontsize=10)
    ax.set_xlabel("Boundary Leakage Rate (%)", fontsize=9)
    ax.set_ylabel("Task Success Rate", fontsize=9)
    ax.set_xlim(-0.5, 10.8)
    ax.set_ylim(0.82, 0.96)
    ax.grid(True, alpha=0.25, zorder=0)

    ax = axes[1]
    mode_colors = {
        "Typed placeholder": "#4C78A8",
        "Semantic abstraction": "#F58518",
        "Secure symbolic mapping": "#54A24B",
    }
    for row in ablation:
        x = _exposure_reduction(row["per"])
        y = float(row["upr"])
        label = row["mode"]
        short_label = label.replace("Secure symbolic mapping", "Symbolic mapping")
        ax.scatter(
            x,
            y,
            s=58,
            c=mode_colors.get(label, "#4C78A8"),
            edgecolors="black",
            linewidths=0.4,
            zorder=3,
        )
        ax.annotate(short_label, (x, y), xytext=(4, 4), textcoords="offset points", fontsize=7)
    ax.set_title("Sanitization-Mode Operating Points", fontsize=10)
    ax.set_xlabel("Direct Exposure Reduction (%)", fontsize=9)
    ax.set_ylabel("UPR", fontsize=9)
    ax.set_xlim(84, 93)
    ax.set_ylim(0.90, 1.00)
    ax.grid(True, alpha=0.25, zorder=0)

    fig.suptitle("Mechanism-Specific Supporting Trade-Offs in CPPB", fontsize=11, y=1.02)
    plt.tight_layout()
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate supporting restoration/ablation trade-off figure.")
    parser.add_argument("--out-dir", default=None, help="Output directory (default: repo_root/paper/fig)")
    args = parser.parse_args()

    out_dir = args.out_dir
    if out_dir is None:
        repo_root = os.path.dirname(os.path.dirname(SRC_DIR))
        out_dir = os.path.join(repo_root, "paper", "fig")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "restoration_ablation_tradeoffs.png")
    plot_restoration_ablation_tradeoffs(out_path)
    print("Saved", out_path)


if __name__ == "__main__":
    main()
