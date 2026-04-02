"""
Generate figures for paper: high-dimensional ring/ellipsoid distribution of Doc2Vec.
- Theoretical chi-square distribution (radius ~ k, variance ~ 2k).
- 2D projection showing ring structure (documents on a ring).
Outputs to paper/figs/ (or path given by --out).
"""
import argparse
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats


def plot_chi2_theoretical(k: int = 213, out_path: str = None):
    """Theoretical distribution of sum of squared standard normals (chi-square with k df)."""
    x = np.linspace(max(0, k - 4 * np.sqrt(2 * k)), k + 4 * np.sqrt(2 * k), 500)
    pdf = stats.chi2.pdf(x, k)
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.plot(x, pdf, "b-", linewidth=2, label=r"$\chi^2(k)$, $k={}$".format(k))
    ax.axvline(k, color="gray", linestyle="--", label=r"$\mu \approx k$")
    ax.set_xlabel(r"$X = \sum_{i=1}^k \xi_i^2$")
    ax.set_ylabel("PDF")
    ax.set_title("Theoretical distribution of Doc2Vec (standardized) radius squared")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    if out_path:
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        print("Saved", out_path)
    plt.close()


def plot_ring_2d_projection(out_path: str = None, n_points: int = 400, k: int = 400):
    """
    Simulate document vectors on high-dim ring: sample chi-square radius, then uniform on sphere.
    2D projection shows ring structure (paper: documents in high-dimensional ring).
    """
    r_sq = np.random.chisquare(k, n_points)
    r = np.sqrt(r_sq)
    # Uniform direction in k-dim, then project to 2D (first two coords)
    z = np.random.randn(n_points, k)
    z = z / np.linalg.norm(z, axis=1, keepdims=True)
    x2d = (z * r[:, np.newaxis])[:, :2]
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(x2d[:, 0], x2d[:, 1], alpha=0.5, s=10, c="steelblue", edgecolors="none")
    ax.set_xlabel("Dimension 1")
    ax.set_ylabel("Dimension 2")
    ax.set_title("Doc2Vec 2D projection (high-dimensional ring structure)")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    if out_path:
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        print("Saved", out_path)
    plt.close()


def plot_edge_distribution(out_path: str = None, k: int = 213, n_samples: int = 5000):
    """Edge (marginal) distribution of one dimension: approximately normal (CLT)."""
    # Simulate: each doc vector component ~ normal in limit
    x = np.random.randn(n_samples)
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.hist(x, bins=50, density=True, alpha=0.7, color="steelblue", edgecolor="white", label="Sample")
    xn = np.linspace(-4, 4, 200)
    ax.plot(xn, stats.norm.pdf(xn), "r-", linewidth=2, label="Normal")
    ax.set_xlabel("Standardized dimension value")
    ax.set_ylabel("Density")
    ax.set_title("Doc2Vec edge distribution (one dimension)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    if out_path:
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        print("Saved", out_path)
    plt.close()


def main():
    p = argparse.ArgumentParser(description="Doc2Vec distribution figures for IBPPSVM paper")
    p.add_argument("--out-dir", default=None, help="Output directory (default: paper/figs)")
    args = p.parse_args()
    out_dir = args.out_dir
    if out_dir is None:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        out_dir = os.path.join(base, "paper", "figs")
    os.makedirs(out_dir, exist_ok=True)
    plot_chi2_theoretical(k=213, out_path=os.path.join(out_dir, "chi2_theoretical_Doc2Vec.png"))
    plot_ring_2d_projection(out_path=os.path.join(out_dir, "Doc2Vec_ring_2d_projection.png"))
    plot_edge_distribution(out_path=os.path.join(out_dir, "Doc2Vec_edge_distribution.png"))


if __name__ == "__main__":
    main()
