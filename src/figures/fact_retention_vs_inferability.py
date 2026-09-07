"""Plot the gap between lexical fact retention and judged inferability.

The propagation table reports the Fact Retention Rate, a lexical criterion:
a sensitive fact counts as retained when at least half of its content words
survive the released surface. FRR is therefore a lower bound on disclosure --
it credits a method for deleting a fact's vocabulary even when the surrounding
text still gives the fact away.

This figure shows how loose that bound is. For each mediation method it draws
the lexical rate and the rate a judge model assigns when shown only the
released surface, connected by a line whose length is the bound's slack. The
control row (no protection) calibrates the judge's ceiling: it cannot reach
100% because some PrivacyLens facts are not fully spelled out even in the raw
trajectory.

Reads the summary written by ``semantic_inferability_judge``; recomputes
nothing.
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

# Validated categorical slots 1 and 2 (light mode); all-pairs safe at two hues.
LEXICAL_COLOR = "#eb6834"
JUDGED_COLOR = "#2a78d6"
CONNECTOR = "#b8b7b2"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#d9d8d4"
SURFACE = "#fcfcfb"

LABELS = {
    "no_protection": "No protection",
    "regex_only": "Regex-only",
    "capitalization_heuristic": "Capitalization heur.",
    "spacy_ner": "spaCy NER",
    "presidio": "Presidio",
    "casper_style": "Casper-style",
    "heuristic_mediator": "Ours (heuristic)",
    "learned_lr": "Ours (learned)",
    "gliner_pii": "Ours (transformer)",
}


def _point(cell: str) -> float:
    return float(re.match(r"\s*([-\d.]+)", cell).group(1))


def _bounds(cell: str) -> tuple[float, float, float]:
    nums = [float(x) for x in re.findall(r"[-\d.]+", cell)]
    return (nums[0], nums[1], nums[2]) if len(nums) >= 3 else (nums[0], nums[0], nums[0])


def _label(key: str) -> str:
    if key.startswith("llm_sanitizer"):
        return "LLM sanitizer"
    return LABELS.get(key, key)


def plot(summary_path: str, out_path: str) -> None:
    with open(summary_path, encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("facts")]
    if not rows:
        raise SystemExit(f"no rows in {summary_path}")

    # Largest slack at the top: the figure is about how loose the bound gets.
    rows.sort(key=lambda r: _point(r["judged_inferable"]) - _point(r["lexical_frr"]))
    y = np.arange(len(rows), dtype=float)

    fig, ax = plt.subplots(figsize=(5.4, 0.42 * len(rows) + 1.25))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    for i, row in enumerate(rows):
        lex, judged = _point(row["lexical_frr"]), _point(row["judged_inferable"])
        ax.plot([lex, judged], [i, i], color=CONNECTOR, linewidth=1.6, zorder=2,
                solid_capstyle="round")
        for value, cell, color in ((lex, row["lexical_frr"], LEXICAL_COLOR),
                                   (judged, row["judged_inferable"], JUDGED_COLOR)):
            _, lo, hi = _bounds(cell)
            ax.plot([lo, hi], [i, i], color=color, linewidth=0.9, alpha=0.5, zorder=3)
            ax.plot(value, i, marker="o", markersize=6, color=color, zorder=4,
                    markeredgecolor=SURFACE, markeredgewidth=1.0)
        # Annotate the slack on the connector, which is the figure's subject.
        gap = judged - lex
        if abs(gap) >= 1.0:
            ax.annotate(f"{gap:+.0f}", ((lex + judged) / 2, i), textcoords="offset points",
                        xytext=(0, 7), ha="center", fontsize=6.5, color=TEXT_SECONDARY)

    ax.set_yticks(y)
    ax.set_yticklabels([_label(r["method_key"]) for r in rows], fontsize=7.5)
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.invert_yaxis()
    ax.set_xlabel("Sensitive facts surviving mediation (%)", fontsize=8, color=TEXT_PRIMARY)
    ax.set_xlim(0, 105)
    ax.tick_params(axis="x", labelsize=7, colors=TEXT_SECONDARY, length=0)
    ax.tick_params(axis="y", colors=TEXT_PRIMARY, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.spines["bottom"].set_linewidth(0.6)

    handles = [
        plt.Line2D([], [], marker="o", linestyle="none", markersize=6, color=LEXICAL_COLOR,
                   markeredgecolor=SURFACE, label="Lexical FRR (lower bound)"),
        plt.Line2D([], [], marker="o", linestyle="none", markersize=6, color=JUDGED_COLOR,
                   markeredgecolor=SURFACE, label="Judged inferable"),
    ]
    ax.legend(handles=handles, frameon=False, fontsize=7, loc="lower center",
              bbox_to_anchor=(0.5, 1.0), ncol=2, handlelength=1.0,
              labelcolor=TEXT_SECONDARY, columnspacing=1.4)

    fig.tight_layout()
    fig.savefig(out_path, dpi=400, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="vgpu3090")
    parser.add_argument("--out", default=os.path.join(
        SRC_DIR, os.pardir, "paper", "figs", "fact_retention_vs_inferability.pdf"))
    args = parser.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""
    plot(os.path.join(EXPERIMENTS_DIR, f"semantic_inferability_summary{suffix}.csv"),
         os.path.abspath(args.out))


if __name__ == "__main__":
    main()
