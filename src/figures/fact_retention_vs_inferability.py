"""Plot what each measure says a mediation method leaves inferable.

Three measures of the same quantity disagree, and the disagreement is the
point. The lexical Fact Retention Rate counts whether a fact's content words
survive. An LLM judge, shown only the released surface, is asked whether a
reader would still learn the fact. A person, not told which method produced
an item and not shown the judge's verdict, answers that same question on a
stratified subset of the same judgments.

The two automated measures report a roughly flat line: whatever the method,
most facts look retained. The human labels fall from the
unprotected control under four of the five mediation methods. Against those labels the
judge scores a kappa at chance and the lexical measure only a little better,
so neither proxy can carry the claim. Both kappas are read from the agreement
table rather than written here, so the legend cannot drift from the data. The figure exists to show why the paper reports the
human numbers and treats the proxies as failed instruments.

Reads the per-method table written by the annotation analysis; recomputes
nothing. The labels are annotator 1's on the full 240-item subset (40 per
method): the first 102 items pooled with the same reader's extension round.
The human intervals are that table's document-clustered bootstrap intervals.

The figure is drawn at the one-column width it is printed at and saved
without cropping, so every font size is its printed size (none under 7 pt).
Point labels carry one decimal, since a 40-item rate moves in steps of 2.5.
Fonts are embedded as TrueType (Type 42) and the PDF carries no creation date.
"""
import argparse
import csv
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

# Printed one-column width in the manuscript's layout (acmart sigconf).
COLUMN_WIDTH_IN = (506.295 - 24.0) / 2 / 72.27
MIN_PT = 7.0

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
    "learned_lr": "Learned detector",
    "heuristic_mediator": "Heuristic detector",
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

    fig, ax = plt.subplots(figsize=(COLUMN_WIDTH_IN, 0.3 * len(rows) + 0.95), layout="constrained")
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    for i, row in enumerate(rows):
        # The human value is the measurement, so it carries the interval and
        # the heavier mark; the proxies sit behind it as small hollow markers.
        h, lo, hi = _bounds(row["human_inferable"])
        ax.plot([lo, hi], [i, i], color=HUMAN, linewidth=1.1, alpha=0.45, zorder=2)
        ax.plot(_point(row["judge_inferable"]), i, marker="s", markersize=4.6,
                markerfacecolor="none", markeredgecolor=JUDGE, markeredgewidth=1.2, zorder=3)
        ax.plot(_point(row["lexical_retained"]), i, marker="^", markersize=4.8,
                markerfacecolor="none", markeredgecolor=LEXICAL, markeredgewidth=1.2, zorder=3)
        ax.plot(h, i, marker="o", markersize=5.6, color=HUMAN, zorder=4,
                markeredgecolor=SURFACE, markeredgewidth=1.0)
        # One decimal: rates over 40 items are multiples of 2.5, and a rounded
        # integer label would print 32.5 as 32 (round-half-even).
        ax.annotate(f"{h:.1f}", (h, i), textcoords="offset points", xytext=(0, 5.5),
                    ha="center", fontsize=MIN_PT, color=TEXT_PRIMARY)

    ax.set_yticks(y)
    ax.set_yticklabels([LABELS.get(r["method_key"], r["method_key"]) for r in rows], fontsize=MIN_PT)
    ax.set_ylim(-0.75, len(rows) - 0.4)
    ax.invert_yaxis()
    ax.set_xlabel("Sensitive facts still inferable (%)", fontsize=7.5, color=TEXT_PRIMARY)
    ax.set_xlim(0, 105)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="x", labelsize=MIN_PT, colors=TEXT_SECONDARY, length=0)
    ax.tick_params(axis="y", colors=TEXT_PRIMARY, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.spines["bottom"].set_linewidth(0.6)

    handles = [
        plt.Line2D([], [], marker="o", linestyle="none", markersize=5.6, color=HUMAN,
                   markeredgecolor=SURFACE, label="Human, 95% CI"),
        plt.Line2D([], [], marker="s", linestyle="none", markersize=4.6, markerfacecolor="none",
                   markeredgecolor=JUDGE, markeredgewidth=1.2,
                   label=f"LLM judge, $\\kappa$={judge_k:.2f}"),
        plt.Line2D([], [], marker="^", linestyle="none", markersize=4.8, markerfacecolor="none",
                   markeredgecolor=LEXICAL, markeredgewidth=1.2,
                   label=f"Lexical, $\\kappa$={lex_k:.2f}"),
    ]
    fig.legend(handles=handles, frameon=False, fontsize=MIN_PT, loc="outside upper center",
               ncol=3, handlelength=0.8, handletextpad=0.3, labelcolor=TEXT_SECONDARY,
               columnspacing=0.7)

    fig.get_layout_engine().set(w_pad=0.02, h_pad=0.02)
    fig.savefig(out_path, dpi=400, facecolor=SURFACE, metadata={"CreationDate": None})
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
