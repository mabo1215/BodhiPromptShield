"""
Generate a compact visual summary of prompt privacy mediation operating points.

Panel A: method-level operating points from Tables III and V.
Panel B: policy-profile operating points from Table VIII.
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


def _load_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _exposure_reduction(per_value):
    return 100.0 - float(per_value)


def plot_operating_points(out_path: str):
    methods = _load_csv(os.path.join(EXPERIMENTS_DIR, "prompt_method_comparison.csv"))
    policies = _load_csv(os.path.join(EXPERIMENTS_DIR, "policy_sensitivity.csv"))

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3))

    ax = axes[0]
    for row in methods:
        x = _exposure_reduction(row["per"])
        y = float(row["tsr"])
        label = row["method"]
        color = "tab:red" if "utility-constrained" in label else "tab:blue"
        marker = "o" if "Proposed" in label else "s"
        size = 52 if "utility-constrained" in label else 42
        ax.scatter(x, y, s=size, c=color, marker=marker, edgecolors="black", linewidths=0.4, zorder=3)
        short_label = (
            label.replace("Proposed ", "")
            .replace("Generic de-identification", "Generic de-id")
            .replace("Enterprise staged redaction", "Enterprise staged")
        )
        ax.annotate(short_label, (x, y), xytext=(4, 4), textcoords="offset points", fontsize=7)
    ax.set_title("Method-Level Operating Points", fontsize=10)
    ax.set_xlabel("Direct Exposure Reduction (%)", fontsize=9)
    ax.set_ylabel("Task Success Rate", fontsize=9)
    ax.set_xlim(-2, 102)
    ax.set_ylim(0.68, 1.02)
    ax.grid(True, alpha=0.25, zorder=0)

    ax = axes[1]
    order = {"Lenient": "tab:green", "Balanced": "tab:red", "Strict": "tab:orange"}
    for row in policies:
        x = _exposure_reduction(row["per"])
        y = float(row["tsr"])
        label = row["profile"]
        ax.scatter(x, y, s=52, c=order[label], edgecolors="black", linewidths=0.4, zorder=3)
        ax.annotate(label, (x, y), xytext=(4, 4), textcoords="offset points", fontsize=7)
    xs = [_exposure_reduction(row["per"]) for row in policies]
    ys = [float(row["tsr"]) for row in policies]
    ax.plot(xs, ys, color="0.45", linewidth=1.0, linestyle="--", zorder=2)
    ax.set_title("Policy-Profile Trade-Off", fontsize=10)
    ax.set_xlabel("Direct Exposure Reduction (%)", fontsize=9)
    ax.set_ylabel("Task Success Rate", fontsize=9)
    ax.set_xlim(86, 94)
    ax.set_ylim(0.86, 0.98)
    ax.grid(True, alpha=0.25, zorder=0)

    fig.suptitle("Prompt Privacy Mediation Operating Regimes in CPPB", fontsize=11, y=1.02)
    plt.tight_layout()
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate prompt privacy operating-point summary figure.")
    parser.add_argument("--out-dir", default=None, help="Output directory (default: repo_root/paper/fig)")
    args = parser.parse_args()

    out_dir = args.out_dir
    if out_dir is None:
        repo_root = os.path.dirname(os.path.dirname(SRC_DIR))
        out_dir = os.path.join(repo_root, "paper", "fig")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "prompt_privacy_operating_points.png")
    plot_operating_points(out_path)
    print("Saved", out_path)


if __name__ == "__main__":
    main()
