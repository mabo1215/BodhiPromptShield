"""Stage the LaTeX source set that a Springer Nature journal submission needs.

The manuscript is kept as ``paper/main.tex`` plus ``paper/appendix.tex`` with
figures under ``paper/figs/`` and the class and style files under
``paper/template/``. Springer Nature's Editorial Manager builds the PDF itself
from the uploaded source, and the template states the constraints that layout
violates: the manuscript must be a single ``.tex`` file (no ``\\input``), and
the source files must not sit in subfolders. This script turns the working
layout into a flat, self-contained source set:

1. ``\\input{appendix}`` is replaced by the appendix text, so there is one
   ``.tex`` file.
2. Figure paths lose their ``figs/`` prefix and the referenced figures are
   copied next to the ``.tex`` file; unreferenced figures are left out.
3. The class file, the bibliography style, the ``.bib`` database, and the
   ``.bbl`` from the last local build are copied alongside, so the source
   compiles whether or not the submission system runs BibTeX.
4. The compiled PDF from the last local build is copied as the reference PDF
   that the journal asks for next to the source.

The build fails if the flattened file still includes another file, references a
figure that does not exist, or if the local PDF is older than the sources it
was built from, so the staged PDF and the staged source cannot silently drift
apart.

Usage:
  python src/package_journal_submission.py
  python src/package_journal_submission.py --out submit/applied_intelligence
"""
from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER = REPO_ROOT / "paper"
DEFAULT_OUT = REPO_ROOT / "submit" / "applied_intelligence"

MANUSCRIPT_NAME = "manuscript"
CLASS_FILES = ("sn-jnl.cls", "sn-basic.bst")

INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
GRAPHICS_RE = re.compile(r"(\\includegraphics(?:\[[^\]]*\])?\{)([^}]+)(\})")


def _inline_inputs(text: str) -> str:
    """Replace every \\input{name} with the content of paper/name.tex."""

    def _sub(match: re.Match[str]) -> str:
        name = match.group(1)
        path = PAPER / (name if name.endswith(".tex") else name + ".tex")
        if not path.exists():
            raise SystemExit(f"\\input target not found: {path}")
        body = path.read_text(encoding="utf-8")
        return f"%% ---- begin inlined {path.name} ----\n{body.rstrip()}\n%% ---- end inlined {path.name} ----"

    return INPUT_RE.sub(_sub, text)


def _flatten_graphics(text: str) -> tuple[str, list[Path]]:
    """Strip directory prefixes from figure paths and collect the figure files."""
    figures: list[Path] = []

    def _sub(match: re.Match[str]) -> str:
        rel = match.group(2)
        src = PAPER / rel
        if not src.exists():
            raise SystemExit(f"Figure not found: {src}")
        figures.append(src)
        return match.group(1) + src.name + match.group(3)

    flat = GRAPHICS_RE.sub(_sub, text)
    names = [f.name for f in figures]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise SystemExit(f"Figures would collide once flattened: {sorted(duplicates)}")
    return flat, figures


def _check_pdf_is_current(pdf: Path, sources: list[Path]) -> None:
    newest = max(p.stat().st_mtime for p in sources)
    if pdf.stat().st_mtime < newest:
        stale = [p.name for p in sources if p.stat().st_mtime > pdf.stat().st_mtime]
        raise SystemExit(
            f"{pdf} is older than {', '.join(stale)}; rebuild the paper (paper/build.bat) first."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (recreated)")
    args = parser.parse_args()
    out: Path = args.out.resolve()

    main_tex = PAPER / "main.tex"
    bbl = PAPER / "build" / "main.bbl"
    pdf = PAPER / "build" / "main.pdf"
    for required in (main_tex, bbl, pdf, PAPER / "ref.bib", *(PAPER / "template" / c for c in CLASS_FILES)):
        if not required.exists():
            raise SystemExit(f"Missing {required}; build the paper first.")

    text = _inline_inputs(main_tex.read_text(encoding="utf-8"))
    if INPUT_RE.search(text):
        raise SystemExit("The flattened manuscript still includes another file.")
    text, figures = _flatten_graphics(text)

    _check_pdf_is_current(pdf, [main_tex, PAPER / "appendix.tex", PAPER / "ref.bib", *figures])

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    (out / f"{MANUSCRIPT_NAME}.tex").write_text(text, encoding="utf-8", newline="\n")
    shutil.copy2(bbl, out / f"{MANUSCRIPT_NAME}.bbl")
    shutil.copy2(PAPER / "ref.bib", out / "ref.bib")
    for name in CLASS_FILES:
        shutil.copy2(PAPER / "template" / name, out / name)
    for fig in figures:
        shutil.copy2(fig, out / fig.name)
    shutil.copy2(pdf, out / f"{MANUSCRIPT_NAME}.pdf")

    staged = sorted(p for p in out.iterdir() if p.is_file())
    if any(p.is_dir() for p in out.iterdir()):
        raise SystemExit("The staged source set must not contain subfolders.")

    archive = out.parent / f"{out.name}_latex_source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in staged:
            if p.suffix != ".pdf":
                zf.write(p, p.name)

    print(f"Staged {len(staged)} files in {out}:")
    for p in staged:
        print(f"  {p.name} ({p.stat().st_size:,} bytes)")
    print(f"LaTeX source archive (no PDF): {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
