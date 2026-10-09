"""
Generate the main-text evidence figure for measured agent-boundary propagation.

Panel A: per-surface exposure (SPE at the retrieval, memory, and tool
boundaries) for every mediation method on the AI4Privacy reference-agent run.
The three surfaces are different projections of the same mediated prompt, not
successive filters, so they are drawn as grouped bars rather than as a decay
curve.

Panel B pairs residual exact-identifier exposure (PER) with the lexical Fact
Retention Rate on PrivacyLens trajectories. It is retained behind ``--panels
ab`` for reference but is not the paper figure: fact retention is lexical, and
the measured comparison against judged inferability lives in
``fact_retention_vs_inferability``. The default single-panel output is what
the manuscript includes.

Reads the pooled result records written by the propagation suite; no number in
this figure is recomputed here.

The figure is drawn at the width it is printed at (the full text width) and
saved without cropping, so every font size below is its printed size; none is
under 7 pt. The caption carries the title. Fonts are embedded as TrueType
(Type 42) and the PDF carries no creation date, so a rebuild is byte-stable.
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

# Printed widths in the manuscript's layout (acmart sigconf).
TEXT_WIDTH_IN = 506.295 / 72.27
MIN_PT = 7.0

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
EXPERIMENTS_DIR = os.path.join(SRC_DIR, "experiments")

AI4PRIVACY_POOLED = "propagation_suite_ai4privacy_results_pooled.csv"
PRIVACYLENS_POOLED = "propagation_suite_privacylens_results_pooled.csv"

# Validated categorical slots 1-3 (light mode). Slot 3 (aqua) sits below 3:1
# contrast on the light surface, so every bar carries a visible value label.
SERIES = {"retrieval": "#2a78d6", "memory": "#eb6834", "tool": "#1baf7a"}
PROPOSED_COLOR = "#2a78d6"
BASELINE_COLOR = "#eb6834"

TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#d9d8d4"
SURFACE = "#fcfcfb"

# Short labels; the full method names live in the results table.
SHORT = {
    "no_protection": "None",
    "regex_only": "Regex",
    "capitalization_heuristic": "Capitaliz.",
    "spacy_ner": "spaCy NER",
    "presidio": "Presidio",
    # The exposure suite masks every method with one marker, so this is the
    # Casper-style detector alone, without its dummy values.
    "casper_style": "Casper-style det.",
    "heuristic_mediator": "Prop. (heuristic)",
    "learned_lr": "Prop. (learned)",
    "gliner_pii": "Prop. (transformer)",
}
# Panel (b) is dense in the low-exposure corner, so it uses compact labels;
# the caption maps them back to the full names used in panel (a).
SHORT_B = {
    "no_protection": "None",
    "regex_only": "Regex",
    "capitalization_heuristic": "Capital.",
    "spacy_ner": "spaCy",
    "presidio": "Presidio",
    "casper_style": "Casper det.",
    "heuristic_mediator": "Prop.-H",
    "learned_lr": "Prop.-L",
    "gliner_pii": "Prop.-T",
}
PROPOSED_KEYS = {"heuristic_mediator", "learned_lr", "gliner_pii"}
ORDER = [
    "no_protection",
    "regex_only",
    "capitalization_heuristic",
    "spacy_ner",
    "presidio",
    "casper_style",
    "heuristic_mediator",
    "gliner_pii",
    "learned_lr",
]


def _short(key: str) -> str:
    if key.startswith("llm_sanitizer"):
        return "LLM sanitizer"
    return SHORT.get(key, key)


def _short_b(key: str) -> str:
    if key.startswith("llm_sanitizer"):
        return "LLM san."
    return SHORT_B.get(key, key)


def _load(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _point(cell: str) -> float:
    """Take the point estimate out of a 'value [lo, hi]' cell."""
    return float(re.match(r"\s*([-\d.]+)", cell).group(1))


def _interval(cell: str):
    nums = re.findall(r"[-\d.]+", cell)
    if len(nums) >= 3:
        return float(nums[0]), float(nums[1]), float(nums[2])
    value = float(nums[0])
    return value, value, value


def _rows_in_order(path):
    by_key = {row["method_key"]: row for row in _load(path)}
    keys = [k for k in ORDER if k in by_key]
    keys += [k for k in by_key if k.startswith("llm_sanitizer")]
    return [(k, by_key[k]) for k in keys]


def _panel_a(ax, rows):
    labels = [_short(k) for k, _ in rows]
    x = np.arange(len(rows), dtype=float)
    width = 0.28

    for offset, (field, color, name) in enumerate(
        [
            ("retrieval_spe", SERIES["retrieval"], "Retrieval"),
            ("memory_spe", SERIES["memory"], "Memory"),
            ("tool_spe", SERIES["tool"], "Tool"),
        ]
    ):
        values = [_point(row[field]) for _, row in rows]
        # A 2px surface gap between adjacent bars: shrink each bar slightly.
        positions = x + (offset - 1) * width
        bars = ax.bar(
            positions,
            values,
            width * 0.88,
            color=color,
            label=name,
            linewidth=0.6,
            edgecolor=SURFACE,
            zorder=3,
        )
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 1.6,
                f"{value:.0f}",
                ha="center",
                va="bottom",
                fontsize=MIN_PT,
                color=TEXT_SECONDARY,
                zorder=4,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", rotation_mode="anchor", fontsize=MIN_PT)
    ax.set_ylabel("Surviving gold spans (SPE, %)", fontsize=7.5, color=TEXT_PRIMARY)
    ax.set_ylim(0, 115)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="y", labelsize=MIN_PT, colors=TEXT_SECONDARY, length=0)
    ax.tick_params(axis="x", colors=TEXT_PRIMARY, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.spines["bottom"].set_linewidth(0.6)
    ax.legend(
        frameon=False,
        fontsize=7.5,
        ncol=3,
        loc="upper right",
        bbox_to_anchor=(1.0, 1.08),
        handlelength=1.1,
        columnspacing=1.0,
        labelcolor=TEXT_SECONDARY,
    )


def _panel_b(ax, rows):
    for key, row in rows:
        per, per_lo, per_hi = _interval(row["per_percent"])
        frr, frr_lo, frr_hi = _interval(row["semantic_residue"])
        proposed = key in PROPOSED_KEYS
        color = PROPOSED_COLOR if proposed else BASELINE_COLOR
        ax.errorbar(
            per,
            frr,
            xerr=[[per - per_lo], [per_hi - per]],
            yerr=[[frr - frr_lo], [frr_hi - frr]],
            fmt="none",
            ecolor=color,
            elinewidth=0.7,
            alpha=0.55,
            zorder=2,
        )
        ax.plot(
            per,
            frr,
            marker="o" if proposed else "s",
            markersize=4.6,
            color=color,
            markeredgecolor=SURFACE,
            markeredgewidth=0.9,
            linestyle="none",
            zorder=3,
        )

    # Selective direct labels: every point is labelled, but placement is tuned
    # so no two collide in the crowded low-PER corner.
    # (dx, dy, ha) tuned against the plotted coordinates so no two labels touch.
    offsets = {
        "no_protection": (-7, 4, "right"),
        "regex_only": (6, 2, "left"),
        "capitalization_heuristic": (-7, -9, "right"),
        "spacy_ner": (0, 7, "center"),
        "presidio": (0, -11, "center"),
        "casper_style": (-7, 0, "right"),
        "heuristic_mediator": (8, -2, "left"),
        "learned_lr": (8, -3, "left"),
        "gliner_pii": (6, 3, "left"),
    }
    for key, row in rows:
        per = _point(row["per_percent"])
        frr = _point(row["semantic_residue"])
        dx, dy, ha = offsets.get(key, (-6, -11, "center"))
        ax.annotate(
            _short_b(key),
            (per, frr),
            textcoords="offset points",
            xytext=(dx, dy),
            fontsize=MIN_PT,
            ha=ha,
            color=TEXT_SECONDARY,
        )

    ax.set_xlabel("Residual exact-identifier exposure (PER, %)", fontsize=7, color=TEXT_PRIMARY)
    ax.set_ylabel("Fact Retention Rate (FRR, %)", fontsize=7, color=TEXT_PRIMARY)
    ax.set_xlim(-13, 112)
    ax.set_ylim(30, 108)
    ax.tick_params(labelsize=MIN_PT, colors=TEXT_SECONDARY, length=0)
    ax.grid(color=GRID, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
        ax.spines[side].set_linewidth(0.6)

    handles = [
        plt.Line2D([], [], marker="o", linestyle="none", markersize=4.6,
                   color=PROPOSED_COLOR, markeredgecolor=SURFACE, label="This work"),
        plt.Line2D([], [], marker="s", linestyle="none", markersize=4.6,
                   color=BASELINE_COLOR, markeredgecolor=SURFACE, label="Baselines"),
    ]
    ax.legend(handles=handles, frameon=False, fontsize=MIN_PT, loc="center left",
              bbox_to_anchor=(0.42, 0.34), handlelength=1.0,
              labelcolor=TEXT_SECONDARY)


def plot(out_path: str, panels: str = "a"):
    ai4 = _rows_in_order(os.path.join(EXPERIMENTS_DIR, AI4PRIVACY_POOLED))
    plens = _rows_in_order(os.path.join(EXPERIMENTS_DIR, PRIVACYLENS_POOLED))

    # Drawn at the printed width and saved uncropped, so sizes are printed sizes.
    if panels == "a":
        fig, ax = plt.subplots(1, 1, figsize=(TEXT_WIDTH_IN, 2.35), layout="constrained")
        fig.patch.set_facecolor(SURFACE)
        ax.set_facecolor(SURFACE)
        _panel_a(ax, ai4)
    else:
        fig, axes = plt.subplots(1, 2, figsize=(TEXT_WIDTH_IN, 2.6), layout="constrained")
        fig.patch.set_facecolor(SURFACE)
        for ax in axes:
            ax.set_facecolor(SURFACE)
        _panel_a(axes[0], ai4)
        _panel_b(axes[1], plens)
    fig.get_layout_engine().set(w_pad=0.02, h_pad=0.02)
    fig.savefig(out_path, dpi=400, facecolor=SURFACE, metadata={"CreationDate": None})
    plt.close(fig)
    print(f"wrote {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panels", default="a", choices=["a", "ab"],
                        help="'a' is the manuscript figure; 'ab' adds the lexical scatter")
    parser.add_argument(
        "--out",
        default=os.path.join(SRC_DIR, os.pardir, "paper", "figs", "propagation_and_fact_gap.pdf"),
    )
    args = parser.parse_args()
    plot(os.path.abspath(args.out), args.panels)


if __name__ == "__main__":
    main()
