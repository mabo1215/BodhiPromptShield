"""
Draw the architecture overview of prompt-privacy mediation as a vector figure.

The drawing follows the manuscript's system description rather than a generic
middleware picture:

* User input (text) enters
  a trusted mediation layer: span detection, then sanitization under a policy
  profile pi (typed placeholder, semantic abstraction, or symbolic token),
  which emits the sanitized prompt x~.
* The secure mapping table K is written by the sanitizer and kept beside the
  layer, inside the trusted domain and off the agent path.
* The downstream text LLM agent receives only x~. The surfaces it writes
  (retrieval query, memory write, application log, tool arguments) are drawn
  as parallel renderings of x~, not as a chain of successive filters.
* Exact values are restored only at an authorized tool-execution boundary,
  from K, after the agent has planned (deferred restoration). K has one
  outgoing edge, to that boundary.
* A dotted edge marks where early restoration would return values to the
  agent before planning; it is drawn for contrast only.

All geometry is in inches on a canvas of the printed size, so font sizes in
points are the sizes that appear on the page. No data is read.

Usage: python mediation_architecture.py [--out paper/figs/mediation_architecture.pdf]
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Rectangle

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DEFAULT_OUT = os.path.join(REPO_DIR, "paper", "figs", "mediation_architecture.pdf")

# Canvas in inches; the figure is included at the full text width, which scales it
# by about 0.8, so the font sizes below are chosen to print at about 7 pt.
WIDTH_IN = 6.7
HEIGHT_IN = 2.0

# Font sizes in points on the canvas.
FS_TEXT = 8.8
FS_SMALL = 8.6
FS_HEAD = 9.0

# Muted, colorblind-safe palette (blue / orange contrast for trust domains;
# blue and vermillion for the two restoration edges, also told apart by dash).
TEXT = "#1b1b1b"
TEXT_MUTED = "#555452"
EDGE = "#4a4a48"
BOX_FILL = "#ffffff"

TRUSTED_FILL = "#e4eef8"
TRUSTED_EDGE = "#8db0d6"
TRUSTED_TEXT = "#1f4f7f"

OBSERVED_FILL = "#f8ede0"
OBSERVED_EDGE = "#d8b086"
OBSERVED_TEXT = "#7a4a17"

FLOW = "#2f2f2d"
KEY = "#1f5f9f"
EARLY = "#c8551b"

LW_BOX = 0.8
LW_FLOW = 0.9


def _rounded(ax, x, y, w, h, fc=BOX_FILL, ec=EDGE, lw=LW_BOX, ls="-", pad=0.035, z=2):
    patch = FancyBboxPatch(
        (x + pad, y + pad), w - 2 * pad, h - 2 * pad,
        boxstyle=f"round,pad={pad}", fc=fc, ec=ec, lw=lw, ls=ls, zorder=z,
    )
    ax.add_patch(patch)
    return patch


def _text(ax, x, y, s, size=FS_TEXT, color=TEXT, weight="normal", ha="center",
          va="center", style="normal", rotation=0, z=5):
    return ax.text(x, y, s, fontsize=size, color=color, fontweight=weight, ha=ha,
                   va=va, fontstyle=style, rotation=rotation, zorder=z)


def _arrow(ax, p0, p1, color=FLOW, lw=LW_FLOW, ls="-", head=6.0, z=4):
    """Straight arrow from p0 to p1; ``head`` is the head length in points.

    A dashed or dotted shaft is drawn as a separate line so that the head
    itself is always filled and solid-edged.
    """
    style = f"-|>,head_length={head / 10:.2f},head_width={head / 20:.2f}"
    if ls == "-":
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=10,
                                     color=color, lw=lw, shrinkA=0, shrinkB=0, zorder=z))
        return
    (x0, y0), (x1, y1) = p0, p1
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    head_in = head / 72.0
    neck = (x1 - ux * head_in, y1 - uy * head_in)
    ax.plot([x0, neck[0]], [y0, neck[1]], color=color, lw=lw, linestyle=ls,
            solid_capstyle="butt", dash_capstyle="butt", zorder=z)
    ax.add_patch(FancyArrowPatch((neck[0] - ux * 0.002, neck[1] - uy * 0.002), p1,
                                 arrowstyle=style, mutation_scale=10, color=color,
                                 lw=lw, shrinkA=0, shrinkB=0, zorder=z))


def _cylinder(ax, x, y, w, h, fc=BOX_FILL, ec=EDGE, lw=LW_BOX, cap=0.09, z=2):
    """A database cylinder: body rectangle with an elliptical top and bottom."""
    ax.add_patch(Ellipse((x + w / 2, y + cap / 2), w, cap, fc=fc, ec=ec, lw=lw, zorder=z))
    # The body is drawn after the bottom ellipse so it hides that ellipse's
    # upper arc, leaving only the visible front rim.
    ax.add_patch(Rectangle((x, y + cap / 2), w, h - cap, fc=fc, ec="none", zorder=z))
    ax.plot([x, x], [y + cap / 2, y + h - cap / 2], color=ec, lw=lw, zorder=z,
            solid_capstyle="butt")
    ax.plot([x + w, x + w], [y + cap / 2, y + h - cap / 2], color=ec, lw=lw, zorder=z,
            solid_capstyle="butt")
    ax.add_patch(Ellipse((x + w / 2, y + h - cap / 2), w, cap, fc=fc, ec=ec, lw=lw,
                         zorder=z + 0.1))


def build_figure():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "mathtext.fontset": "dejavusans",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })
    fig = plt.figure(figsize=(WIDTH_IN, HEIGHT_IN))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, WIDTH_IN)
    ax.set_ylim(0, HEIGHT_IN)
    ax.set_axis_off()

    # ------------------------------------------------------------------
    # Trust domains: trusted band (bottom), observable band (top right).
    # ------------------------------------------------------------------
    trusted = (1.02, 0.02, WIDTH_IN - 1.04, 0.88)
    observed = (2.18, 0.97, WIDTH_IN - 2.20, 1.01)
    _rounded(ax, *trusted, fc=TRUSTED_FILL, ec=TRUSTED_EDGE, lw=0.7, pad=0.04, z=0)
    _rounded(ax, *observed, fc=OBSERVED_FILL, ec=OBSERVED_EDGE, lw=0.7, pad=0.04, z=0)
    _text(ax, WIDTH_IN - 0.13, trusted[1] + trusted[3] / 2, "Trusted",
          size=FS_HEAD, weight="bold", color=TRUSTED_TEXT, rotation=90)
    _text(ax, WIDTH_IN - 0.13, observed[1] + observed[3] / 2, "Observable",
          size=FS_HEAD, weight="bold", color=OBSERVED_TEXT, rotation=90)

    # ------------------------------------------------------------------
    # User input (outside both domains).
    # ------------------------------------------------------------------
    ux, uy, uw, uh = 0.02, 0.10, 0.90, 0.72
    _rounded(ax, ux, uy, uw, uh, ec=EDGE)
    _text(ax, ux + uw / 2, uy + uh - 0.10, r"User input $x$", weight="bold", size=FS_HEAD)
    _rounded(ax, ux + 0.06, 0.16, uw - 0.12, 0.48, ec=TEXT_MUTED, lw=0.6, pad=0.025)
    _text(ax, ux + uw / 2, 0.40, "prompt text", size=FS_SMALL)

    # ------------------------------------------------------------------
    # Mediation layer: span detection -> sanitization under pi.
    # ------------------------------------------------------------------
    mx0, mx1, my0, my1 = 1.10, 3.42, 0.07, 0.84
    _rounded(ax, mx0, my0, mx1 - mx0, my1 - my0, fc="none", ec=TRUSTED_TEXT, lw=0.7,
             ls=(0, (3, 2)), pad=0.03, z=1)
    _text(ax, mx0 + 0.08, my1 - 0.10, "Mediation layer", weight="bold", size=FS_HEAD,
          color=TRUSTED_TEXT, ha="left")

    dx, dy, dw, dh = 1.18, 0.11, 0.74, 0.575
    _rounded(ax, dx, dy, dw, dh)
    _text(ax, dx + dw / 2, 0.55, "Span", weight="bold")
    _text(ax, dx + dw / 2, 0.43, "detection", weight="bold")
    _text(ax, dx + dw / 2, 0.26, r"$E(x)$", color=TEXT_MUTED)

    sx, sy, sw, sh = 2.06, 0.11, 1.28, 0.575
    _rounded(ax, sx, sy, sw, sh)
    _text(ax, sx + sw / 2, 0.57, r"Sanitization $T_\pi$", weight="bold")
    for i, mode in enumerate(("typed placeholder", "semantic abstraction", "symbolic token")):
        _text(ax, sx + sw / 2, 0.45 - 0.115 * i, mode, size=FS_SMALL, color=TEXT_MUTED)

    # Input edge.
    _arrow(ax, (ux + uw, 0.40), (dx, 0.40))
    _arrow(ax, (dx + dw, 0.40), (sx, 0.40))

    # ------------------------------------------------------------------
    # Mapping table K (trusted, off the agent path).
    # ------------------------------------------------------------------
    kx, ky, kw, kh = 3.62, 0.13, 0.80, 0.56
    _cylinder(ax, kx, ky, kw, kh)
    _text(ax, kx + kw / 2, 0.475, "Mapping", weight="bold")
    _text(ax, kx + kw / 2, 0.355, r"table $K$", weight="bold")
    _text(ax, kx + kw / 2, 0.225, "off-path", size=FS_SMALL, color=TEXT_MUTED)
    _arrow(ax, (sx + sw, 0.32), (kx, 0.32), color=KEY, ls=(0, (3, 1.6)))

    # ------------------------------------------------------------------
    # Authorized tool-execution boundary (trusted).
    # ------------------------------------------------------------------
    bx, by, bw, bh = 4.66, 0.11, 1.74, 0.60
    _rounded(ax, bx, by, bw, bh, ec=KEY, lw=1.1)
    _text(ax, bx + bw / 2, 0.598, "Authorized tool boundary", weight="bold", size=FS_TEXT - 0.6)
    _text(ax, bx + bw / 2, 0.476, r"restores exact values from $K$", size=FS_SMALL)
    _text(ax, bx + bw / 2, 0.356, "only after planning (deferred)", size=FS_SMALL)
    _text(ax, bx + bw / 2, 0.236, "then executes the tool call", size=FS_SMALL)
    _arrow(ax, (kx + kw, 0.32), (bx, 0.32), color=KEY, ls=(0, (3, 1.6)))

    # ------------------------------------------------------------------
    # Downstream LLM agent (observable) and its parallel boundary surfaces.
    # ------------------------------------------------------------------
    ax0, ay0, aw, ah = 2.30, 1.08, 1.00, 0.76
    _rounded(ax, ax0, ay0, aw, ah)
    _text(ax, ax0 + aw / 2, 1.685, "LLM agent", weight="bold", size=FS_HEAD)
    _text(ax, ax0 + aw / 2, 1.535, "text-only model", size=FS_SMALL)
    _text(ax, ax0 + aw / 2, 1.385, r"plans over $\tilde{x}$", size=FS_SMALL)
    _text(ax, ax0 + aw / 2, 1.235, "(model provider)", size=FS_SMALL, color=TEXT_MUTED)

    # Sanitized prompt edge: the only content that crosses into the agent.
    xt = 2.80
    _arrow(ax, (xt, sy + sh), (xt, ay0))
    _text(ax, xt + 0.06, 0.748, r"$\tilde{x}$ only", size=FS_TEXT, ha="left")

    surf_x, surf_w, surf_h = 3.80, 1.14, 0.165
    rows = [
        ("retrieval query", "retrieval index", 1.705),
        ("memory write", "memory store", 1.50),
        ("application log", "log store", 1.295),
        ("tool arguments", "other tools", 1.09),
    ]
    _text(ax, surf_x + surf_w / 2, 1.875, r"parallel renderings of $\tilde{x}$",
          size=FS_SMALL, style="italic", color=OBSERVED_TEXT)
    fan_origin = (ax0 + aw, 1.46)
    for surface, sink, yc in rows:
        _rounded(ax, surf_x, yc - surf_h / 2, surf_w, surf_h, pad=0.02, lw=0.7)
        _text(ax, surf_x + surf_w / 2, yc, surface, size=FS_SMALL)
        _arrow(ax, fan_origin, (surf_x, yc), lw=0.75, head=5.0)
        _arrow(ax, (surf_x + surf_w, yc), (surf_x + surf_w + 0.18, yc), lw=0.75, head=5.0)
        _text(ax, surf_x + surf_w + 0.22, yc, sink, size=FS_SMALL, ha="left",
              color=TEXT_MUTED)

    # Tool arguments cross back into the trusted domain, still tokenized.
    tx = 4.80
    _arrow(ax, (tx, rows[-1][2] - surf_h / 2), (tx, by + bh))
    _text(ax, tx + 0.06, 0.83, "planned call, tokens only", size=FS_SMALL, ha="left")

    # Early restoration, for contrast: values return before planning.
    _arrow(ax, (kx + 0.30, ky + kh), (ax0 + aw - 0.08, ay0), color=EARLY, lw=0.9,
           ls=(0, (1.2, 1.4)))

    # ------------------------------------------------------------------
    # Legend (top left, outside both domains).
    # ------------------------------------------------------------------
    lx, ly, step = 0.06, 1.86, 0.165
    ax.add_patch(Rectangle((lx, ly - 0.05), 0.24, 0.10, fc=TRUSTED_FILL, ec=TRUSTED_EDGE,
                           lw=0.6))
    _text(ax, lx + 0.32, ly, "trusted domain", size=FS_SMALL, ha="left")
    ly -= step
    ax.add_patch(Rectangle((lx, ly - 0.05), 0.24, 0.10, fc=OBSERVED_FILL,
                           ec=OBSERVED_EDGE, lw=0.6))
    _text(ax, lx + 0.32, ly, "partially trusted, observable", size=FS_SMALL, ha="left")
    ly -= step
    _arrow(ax, (lx, ly), (lx + 0.24, ly), head=5.0)
    _text(ax, lx + 0.32, ly, "sanitized content", size=FS_SMALL, ha="left")
    ly -= step
    _arrow(ax, (lx, ly), (lx + 0.24, ly), color=KEY, ls=(0, (3, 1.6)), head=5.0)
    _text(ax, lx + 0.32, ly, r"mapping state $K$", size=FS_SMALL, ha="left")
    ly -= step
    _arrow(ax, (lx, ly), (lx + 0.24, ly), color=EARLY, ls=(0, (1.2, 1.4)), head=5.0)
    _text(ax, lx + 0.32, ly, "early restoration (contrast)", size=FS_SMALL, ha="left")

    return fig


def save(fig, out_path):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    metadata = {"CreationDate": None} if out_path.lower().endswith(".pdf") else None
    fig.savefig(out_path, metadata=metadata, facecolor="white")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    fig = build_figure()
    save(fig, args.out)
    plt.close(fig)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
