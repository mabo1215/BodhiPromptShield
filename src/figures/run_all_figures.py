"""
Run all figure scripts and write outputs to paper/figs/.
Usage: python run_all_figures.py [--out-dir paper/figs]
"""
import argparse
import os
import sys

# Ensure project root on path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default=None, help="Output directory for figures (default: repo_root/paper/figs)")
    args = p.parse_args()
    out_dir = args.out_dir
    if out_dir is None:
        repo = os.path.dirname(os.path.dirname(SCRIPT_DIR))
        out_dir = os.path.join(repo, "paper", "figs")
    os.makedirs(out_dir, exist_ok=True)
    print("Output directory:", out_dir)

    from figures.doc2vec_distribution import (
        plot_chi2_theoretical,
        plot_ring_2d_projection,
        plot_edge_distribution,
    )
    plot_chi2_theoretical(k=213, out_path=os.path.join(out_dir, "chi2_theoretical_Doc2Vec.png"))
    plot_ring_2d_projection(out_path=os.path.join(out_dir, "Doc2Vec_ring_2d_projection.png"))
    plot_edge_distribution(out_path=os.path.join(out_dir, "Doc2Vec_edge_distribution.png"))

    from figures.category_margin import generate_margin_figure
    generate_margin_figure(out_path=os.path.join(out_dir, "Category_boundary.png"))

    from figures.spatial_internal_categories import plot_internal_categories_ring
    plot_internal_categories_ring(
        out_path=os.path.join(out_dir, "Spatial_distribution_of_internal_categories.png")
    )

    from figures.prompt_privacy_operating_points import plot_operating_points
    plot_operating_points(out_path=os.path.join(out_dir, "prompt_privacy_operating_points.png"))
    print("Saved", os.path.join(out_dir, "prompt_privacy_operating_points.png"))

    from figures.agent_pipeline_summary import plot_agent_pipeline_summary
    plot_agent_pipeline_summary(out_path=os.path.join(out_dir, "agent_pipeline_summary.png"))
    print("Saved", os.path.join(out_dir, "agent_pipeline_summary.png"))

    from figures.agent_propagation_curves import plot_agent_propagation_curves
    plot_agent_propagation_curves(out_path=os.path.join(out_dir, "agent_propagation_curves.png"))
    print("Saved", os.path.join(out_dir, "agent_propagation_curves.png"))

    from figures.cppb_benchmark_composition import plot_cppb_benchmark_composition
    plot_cppb_benchmark_composition(out_path=os.path.join(out_dir, "cppb_benchmark_composition.png"))
    print("Saved", os.path.join(out_dir, "cppb_benchmark_composition.png"))

    from figures.restoration_ablation_tradeoffs import plot_restoration_ablation_tradeoffs
    plot_restoration_ablation_tradeoffs(out_path=os.path.join(out_dir, "restoration_ablation_tradeoffs.png"))
    print("Saved", os.path.join(out_dir, "restoration_ablation_tradeoffs.png"))

    print("All figures generated.")


if __name__ == "__main__":
    main()
