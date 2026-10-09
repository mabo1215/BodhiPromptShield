"""Draw the manuscript's figures into paper/figs/.

The manuscript shows three generated figures. This draws those three, in the
formats the manuscript includes:

    propagation_and_fact_gap.pdf        cross-boundary exposure (fig:propagation)
    fact_retention_vs_inferability.pdf  surface form vs facts (fig:inferability)
    prompt_privacy_operating_points.pdf policy operating points (fig:operating_points)

The fourth figure in the paper, the workflow diagram, is drawn by hand and has
no script.

An earlier version of this runner drew nine figures from an earlier version of
the paper and none of the first two above, so the command advertised as
producing the manuscript figures did not produce them. Those nine are still
here, behind --legacy, because they belong to the record of what was run even
though nothing in the current manuscript shows them.

Usage: python run_all_figures.py [--out-dir paper/figs] [--legacy]
"""
import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

EXPERIMENTS_DIR = os.path.join(SRC_DIR, "experiments")


def _manuscript_figures(out_dir, tag):
    from figures.propagation_and_fact_gap import plot as plot_propagation
    plot_propagation(os.path.join(out_dir, "propagation_and_fact_gap.pdf"), "a")

    from figures.fact_retention_vs_inferability import plot as plot_inferability, _kappas, inputs
    by_method, agreement = inputs(tag)
    judge_k, lex_k = _kappas(agreement)
    plot_inferability(by_method, os.path.join(out_dir, "fact_retention_vs_inferability.pdf"),
                      judge_k, lex_k)

    # This one writes the PDF the manuscript includes beside the PNG it is asked
    # for, so the .png path is the one to pass.
    from figures.prompt_privacy_operating_points import plot_operating_points
    plot_operating_points(os.path.join(out_dir, "prompt_privacy_operating_points.png"))
    print("wrote", os.path.join(out_dir, "prompt_privacy_operating_points.pdf"))


def _legacy_figures(out_dir):
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
        out_path=os.path.join(out_dir, "Spatial_distribution_of_internal_categories.png"))

    from figures.agent_pipeline_summary import plot_agent_pipeline_summary
    plot_agent_pipeline_summary(out_path=os.path.join(out_dir, "agent_pipeline_summary.png"))

    from figures.agent_propagation_curves import plot_agent_propagation_curves
    plot_agent_propagation_curves(out_path=os.path.join(out_dir, "agent_propagation_curves.png"))

    from figures.cppb_benchmark_composition import plot_cppb_benchmark_composition
    plot_cppb_benchmark_composition(out_path=os.path.join(out_dir, "cppb_benchmark_composition.png"))

    from figures.restoration_ablation_tradeoffs import plot_restoration_ablation_tradeoffs
    plot_restoration_ablation_tradeoffs(
        out_path=os.path.join(out_dir, "restoration_ablation_tradeoffs.png"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", default=None,
                   help="Output directory (default: repo_root/paper/figs)")
    p.add_argument("--tag", default="vgpu3090",
                   help="Record tag for the inferability figure's inputs")
    p.add_argument("--legacy", action="store_true",
                   help="Also draw the figures from earlier versions of the paper")
    args = p.parse_args()
    out_dir = args.out_dir
    if out_dir is None:
        repo = os.path.dirname(os.path.dirname(SCRIPT_DIR))
        out_dir = os.path.join(repo, "paper", "figs")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    print("Output directory:", out_dir)

    _manuscript_figures(out_dir, args.tag)
    if args.legacy:
        _legacy_figures(out_dir)
    print("All figures generated.")


if __name__ == "__main__":
    main()
