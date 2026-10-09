"""Plot what each measure says a mediation method leaves inferable.

Three measures of the same quantity disagree, and the disagreement is the
point. The lexical Fact Retention Rate counts whether a fact's content words
survive. An LLM judge, shown only the released surface, is asked whether a
reader would still learn the fact. A person, blind both to which method
produced an item and to the judge's verdict, answers that same question on a
stratified subset of the same judgments.

The two automated measures report a roughly flat line: whatever the method,
most facts look retained. The human labels descend monotonically from the
unprotected control to the most aggressive redactor. Against those labels the
judge scores a kappa at chance and the lexical measure only a little better,
so neither proxy can carry the claim. Both kappas are read from the agreement
table rather than written here, so the legend cannot drift from the data. The figure exists to show why the paper reports the
human numbers and treats the proxies as failed instruments.

Reads the per-method table written by the annotation analysis; recomputes
nothing. The labels are annotator 1's on the full 240-item subset (40 per
method): the first 102 items pooled with the same reader's extension round.
"""
import argparse
import csv
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
EXPERIMENTS_DIR = os.path.join(SRC_DIR, "experiments")

# Validated categorical slots 1-3 (light mode), all-pairs safe at three hues.
HUMAN = "#2a78d6"
JUDGE = "#eb6834"
LEXICAL = "#1baf7a"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#d9d8d4"
SURFACE = "#fcfcfb"

LABELS = {
    "no_protection": "No protection",
    "regex_only": "Regex-only",
    "presidio": "Presidio",
    "casper_style": "Casper-style",
    "learned_lr": "Ours (learned)",
    "heuristic_mediator": "Ours (heuristic)",
}


def _point(cell):
    return float(re.match(r"\s*([-\d.]+)", cell).group(1))


def _bounds(cell):
    nums = [float(x) for x in re.findall(r"[-\d.]+", cell)]
    return (nums[0], nums[1], nums[2]) if len(nums) >= 3 else (nums[0], nums[0], nums[0])


def inputs(tag):
    """The per-method table and agreement table the figure reads, for one tag."""
    suffix = f"_{tag}" if tag else ""
    return (os.path.join(EXPERIMENTS_DIR,
                         f"semantic_inferability_human_by_method_extend40{suffix}_pooled_annotator1.csv"),
            os.path.join(EXPERIMENTS_DIR, f"semantic_inferability_agreement_extend40{suffix}.csv"))


def _kappas(path, judge_row="judge_vs_pooled_annotator1",
            lexical_row="lexical_vs_pooled_annotator1"):
    """Read the two kappas from the agreement table beside the per-method one."""
    out = {}
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            out[row["comparison"]] = float(row["cohens_kappa"])
    return out[judge_row], out[lexical_row]


def plot(path, out_path, judge_k, lex_k):
    with open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda r: -_point(r["human_inferable"]))
    y = np.arange(len(rows), dtype=float)

    fig, ax = plt.subplots(figsize=(5.5, 0.44 * len(rows) + 1.15))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    for i, row in enumerate(rows):
        # The human value is the measurement, so it carries the interval and
        # the heavier mark; the proxies sit behind it as small hollow markers.
        h, lo, hi = _bounds(row["human_inferable"])
        ax.plot([lo, hi], [i, i], color=HUMAN, linewidth=1.1, alpha=0.45, zorder=2)
        ax.plot(_point(row["judge_inferable"]), i, marker="s", markersize=5.4,
                markerfacecolor="none", markeredgecolor=JUDGE, markeredgewidth=1.4, zorder=3)
        ax.plot(_point(row["lexical_retained"]), i, marker="^", markersize=5.6,
                markerfacecolor="none", markeredgecolor=LEXICAL, markeredgewidth=1.4, zorder=3)
        ax.plot(h, i, marker="o", markersize=7, color=HUMAN, zorder=4,
                markeredgecolor=SURFACE, markeredgewidth=1.1)
        ax.annotate(f"{h:.0f}", (h, i), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=6.8, color=HUMAN, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels([LABELS.get(r["method_key"], r["method_key"]) for r in rows], fontsize=7.8)
    ax.set_ylim(-0.8, len(rows) - 0.25)
    ax.invert_yaxis()
    ax.set_xlabel("Sensitive facts still inferable (%)", fontsize=8, color=TEXT_PRIMARY)
    ax.set_xlim(0, 108)
    ax.tick_params(axis="x", labelsize=7, colors=TEXT_SECONDARY, length=0)
    ax.tick_params(axis="y", colors=TEXT_PRIMARY, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.spines["bottom"].set_linewidth(0.6)

    handles = [
        plt.Line2D([], [], marker="o", linestyle="none", markersize=7, color=HUMAN,
                   markeredgecolor=SURFACE, label="Human (blind), 95% CI"),
        plt.Line2D([], [], marker="s", linestyle="none", markersize=5.4, markerfacecolor="none",
                   markeredgecolor=JUDGE, markeredgewidth=1.4,
                   label=f"LLM judge, $\\kappa$={judge_k:.2f}"),
        plt.Line2D([], [], marker="^", linestyle="none", markersize=5.6, markerfacecolor="none",
                   markeredgecolor=LEXICAL, markeredgewidth=1.4,
                   label=f"Lexical, $\\kappa$={lex_k:.2f}"),
    ]
    ax.legend(handles=handles, frameon=False, fontsize=6.9, loc="lower center",
              bbox_to_anchor=(0.5, 1.0), ncol=3, handlelength=1.0,
              labelcolor=TEXT_SECONDARY, columnspacing=1.0)

    fig.tight_layout()
    fig.savefig(out_path, dpi=400, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="vgpu3090")
    parser.add_argument("--out", default=os.path.join(
        SRC_DIR, os.pardir, "paper", "figs", "fact_retention_vs_inferability.pdf"))
    args = parser.parse_args()
    by_method, agreement = inputs(args.tag)
    judge_k, lex_k = _kappas(agreement)
    plot(by_method, os.path.abspath(args.out), judge_k, lex_k)


if __name__ == "__main__":
    main()
