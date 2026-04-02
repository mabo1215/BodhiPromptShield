"""
Spatial distribution of internal categories (2D projection).
Paper: "Spatial distribution of internal categories (2D projection)" — single category also in ring.
"""
import argparse
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_internal_categories_ring(out_path: str = None, n_per_class: int = 150, k: int = 50):
    """One category: document vectors in a smaller ring (2D projection)."""
    r_sq = np.random.chisquare(k, n_per_class)
    r = np.sqrt(r_sq)
    z = np.random.randn(n_per_class, k)
    z = z / np.linalg.norm(z, axis=1, keepdims=True)
    x2d = (z * r[:, np.newaxis])[:, :2]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.scatter(x2d[:, 0], x2d[:, 1], alpha=0.6, s=20, c="steelblue", edgecolors="none")
    ax.set_xlabel("Dimension 1")
    ax.set_ylabel("Dimension 2")
    ax.set_title("Spatial distribution of internal categories (2D projection)")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    if out_path:
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        print("Saved", out_path)
    plt.close()


def main():
    p = argparse.ArgumentParser(description="Internal categories spatial distribution figure")
    p.add_argument("--out-dir", default=None, help="Output directory (default: paper/figs)")
    args = p.parse_args()
    out_dir = args.out_dir
    if out_dir is None:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        out_dir = os.path.join(base, "paper", "figs")
    os.makedirs(out_dir, exist_ok=True)
    plot_internal_categories_ring(
        out_path=os.path.join(out_dir, "Spatial_distribution_of_internal_categories.png")
    )


if __name__ == "__main__":
    main()
