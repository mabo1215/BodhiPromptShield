"""
Generate figure: classification margin (internal classification center).
2D sketch: two classes with margin H_+ and H_-, support vectors, and decision boundary.
Corresponds to paper Fig "Category boundary" / "Classification margin of Covid-19 and Medical Transcription with ppSVM".
"""
import argparse
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def generate_margin_figure(out_path: str = None):
    """
    Sketch: two classes (rings/blobs), max-margin hyperplane, margin.
    Internal classification center: each class has a center; decision by distance/margin.
    """
    np.random.seed(42)
    # Class +1: center (1, 1), class -1: center (-1, -1)
    n = 80
    c1 = np.random.randn(n, 2) * 0.5 + np.array([1, 1])
    c2 = np.random.randn(n, 2) * 0.5 + np.array([-1, -1])
    # Decision boundary: x + y = 0 (midway); margins x + y = ± 1
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.scatter(c1[:, 0], c1[:, 1], c="C0", s=25, alpha=0.7, label="Class +1", edgecolors="none")
    ax.scatter(c2[:, 0], c2[:, 1], c="C1", s=25, alpha=0.7, label="Class -1", edgecolors="none")
    xl = np.linspace(-2.5, 2.5, 2)
    ax.plot(xl, -xl, "k-", linewidth=2, label="Decision boundary $H_0$")
    ax.plot(xl, -xl + 1 / np.sqrt(2), "k--", alpha=0.8, label="$H_+$")
    ax.plot(xl, -xl - 1 / np.sqrt(2), "k--", alpha=0.8, label="$H_-$")
    ax.set_xlabel("Dimension 1")
    ax.set_ylabel("Dimension 2")
    ax.set_title("Classification margin (internal classification center, ppSVM)")
    ax.legend(loc="lower left", fontsize=8)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(-2.5, 2.5)
    plt.tight_layout()
    if out_path:
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        print("Saved", out_path)
    plt.close()


def main():
    p = argparse.ArgumentParser(description="Category margin figure for IBPPSVM paper")
    p.add_argument("--out-dir", default=None, help="Output directory (default: paper/figs)")
    args = p.parse_args()
    out_dir = args.out_dir
    if out_dir is None:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        out_dir = os.path.join(base, "paper", "figs")
    os.makedirs(out_dir, exist_ok=True)
    generate_margin_figure(out_path=os.path.join(out_dir, "Category_boundary.png"))


if __name__ == "__main__":
    main()
