"""Stage the files an Elsevier (Array) submission needs.

The manuscript is kept as ``paper/main.tex``, with figures under ``paper/figs/``
and the class and style files under ``paper/template/``. The appendix is
submitted as a separate Supplementary Material PDF built from
``paper/supplementary.tex`` (which wraps ``paper/appendix.tex``). The two
documents reference each other through the ``xr`` package, which reads the
other document's ``.aux`` file at build time. The journal's system builds the
manuscript PDF from the uploaded LaTeX source and has no ``.aux`` for the
supplement, so this script turns the working layout into a flat,
self-contained source set:

1. Every main-text reference into the supplement (``\\ref{S-...}``) is replaced
   by the literal number recorded in ``paper/build/supplementary.aux``, and the
   ``xr`` preamble is removed, so the manuscript no longer depends on another
   document.
2. Figure paths lose their ``figs/`` prefix and the referenced figures are
   copied next to the ``.tex`` file; unreferenced figures are left out.
3. The class file, the bibliography style, the ``.bib`` database, and the
   ``.bbl`` from the last local build are copied alongside, so the source
   compiles whether or not the submission system runs BibTeX.
4. The compiled manuscript PDF, the Supplementary Material PDF, and the
   highlights file are copied as the separate uploads the journal asks for.
5. Every table of the manuscript is written, in order and one per page, to a
   standalone ``tables.tex`` with the manuscript's own preamble, and each table
   also to its own file under ``tables/``, for a journal that asks for editable
   tables. They are written after the LaTeX source archive, so the archive
   holds only the manuscript build. Compile ``tables.tex`` with the
   manuscript's ``.aux`` copied in as ``tables.aux``, or its section references
   print as ??.

The build fails if the manuscript includes another file, references a figure
that does not exist, references a supplement label the supplement does not
define, or if either local PDF is older than the sources it was built from, so
the staged PDFs and the staged source cannot silently drift apart. It also
fails while any source still carries an author placeholder (red text or an
"[Authors to confirm" note), so an unfinished manuscript cannot be staged.

Usage:
  python src/package_journal_submission.py
  python src/package_journal_submission.py --out submit/array
"""
from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER = REPO_ROOT / "paper"
BUILD = PAPER / "build"
DEFAULT_OUT = REPO_ROOT / "submit" / "array"

MANUSCRIPT_NAME = "manuscript"
SUPPLEMENT_NAME = "supplementary_material"
CLASS_FILES = ("elsarticle.cls", "elsarticle-num.bst")
HIGHLIGHTS = PAPER / "highlights.txt"

SUPP_PREFIX = "S-"
TABLE_RE = re.compile(r"\\begin\{(table\*?)\}.*?\\end\{\1\}", re.S)
TABLE_LABEL_RE = re.compile(r"\\label\{tab:([^}]+)\}")
# Author placeholders that must be resolved before a manuscript is staged.
PLACEHOLDER_RE = re.compile(r"\\textcolor\{red\}|\[Authors to confirm", re.IGNORECASE)
INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
GRAPHICS_RE = re.compile(r"(\\includegraphics(?:\[[^\]]*\])?\{)([^}]+)(\})")
SUPP_REF_RE = re.compile(r"\\ref\{" + re.escape(SUPP_PREFIX) + r"([^}]+)\}")
NEWLABEL_RE = re.compile(r"^\\newlabel\{([^}]+)\}\{\{([^}]*)\}")
# The preamble block that loads xr: its comment lines and the two commands.
XR_BLOCK_RE = re.compile(
    r"(?:%%[^\n]*\n)*?\\usepackage\{xr\}\n\\externaldocument(?:\[[^\]]*\])*\{supplementary\}\n"
)


def _supplement_labels(aux: Path) -> dict[str, str]:
    """Map each label the supplement defines to the number it printed."""
    labels: dict[str, str] = {}
    for line in aux.read_text(encoding="utf-8", errors="replace").splitlines():
        match = NEWLABEL_RE.match(line)
        if match:
            labels[match.group(1)] = match.group(2)
    return labels


def _resolve_supplement_refs(text: str, labels: dict[str, str]) -> str:
    """Replace \\ref{S-label} with the supplement's literal number."""
    missing: set[str] = set()

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in labels:
            missing.add(key)
            return match.group(0)
        return labels[key]

    resolved = SUPP_REF_RE.sub(_sub, text)
    if missing:
        raise SystemExit(f"Supplement labels not defined in supplementary.aux: {sorted(missing)}")
    block = XR_BLOCK_RE.search(resolved)
    if block is None:
        raise SystemExit("Could not find the xr preamble block in main.tex.")
    note = (
        "%% References to the Supplementary Material are written as literal numbers\n"
        "%% (Supplementary Section S1, Table S1, ...); it is uploaded as a separate file.\n"
    )
    resolved = resolved[: block.start()] + note + resolved[block.end():]
    if "\\externaldocument" in resolved or "\\usepackage{xr}" in resolved:
        raise SystemExit("The flattened manuscript still loads xr.")
    return resolved


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


def _write_tables(text: str, out: Path) -> list[Path]:
    """Write every table of the staged manuscript to a standalone tables.tex."""
    preamble = text[: text.index("\\begin{document}")]
    tables = [m.group(0) for m in TABLE_RE.finditer(text)]
    if not tables:
        raise SystemExit("The manuscript has no table environments.")
    note = (
        "%% Every table of the manuscript, in order and one per page, typeset with the\n"
        "%% manuscript's own preamble. Section references resolve when the manuscript's\n"
        "%% .aux is copied in as tables.aux.\n"
    )
    document = note + preamble + "\\begin{document}\n" + "\n\\clearpage\n".join(tables) + "\n\\end{document}\n"
    (out / "tables.tex").write_text(document, encoding="utf-8", newline="\n")
    folder = out / "tables"
    folder.mkdir()
    written = [out / "tables.tex"]
    for number, table in enumerate(tables, 1):
        label = TABLE_LABEL_RE.search(table)
        name = f"table{number}_{label.group(1) if label else number}.tex"
        (folder / name).write_text(table + "\n", encoding="utf-8", newline="\n")
        written.append(folder / name)
    (folder / "tables.tex").write_text(document, encoding="utf-8", newline="\n")
    for name in CLASS_FILES:
        shutil.copy2(PAPER / "template" / name, folder / name)
    return written


def _check_no_placeholders(sources: list[Path]) -> None:
    """Refuse to stage while any source still carries an author placeholder."""
    hits = []
    for src in sources:
        for number, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("%"):
                continue
            if PLACEHOLDER_RE.search(line):
                hits.append(f"{src.name}:{number}")
    if hits:
        raise SystemExit(f"Author placeholders remain in {', '.join(hits)}; resolve them first.")


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
    supp_sources = [PAPER / "supplementary.tex", PAPER / "appendix.tex"]
    bbl = BUILD / "main.bbl"
    pdf = BUILD / "main.pdf"
    supp_aux = BUILD / "supplementary.aux"
    supp_pdf = BUILD / "supplementary.pdf"
    for required in (
        main_tex, *supp_sources, bbl, pdf, supp_aux, supp_pdf, HIGHLIGHTS, PAPER / "ref.bib",
        *(PAPER / "template" / c for c in CLASS_FILES),
    ):
        if not required.exists():
            raise SystemExit(f"Missing {required}; build the paper first.")

    _check_no_placeholders([main_tex, *supp_sources])
    text = main_tex.read_text(encoding="utf-8")
    if INPUT_RE.search(text):
        raise SystemExit("main.tex includes another file; the manuscript must be a single .tex file.")
    text = _resolve_supplement_refs(text, _supplement_labels(supp_aux))
    text, figures = _flatten_graphics(text)

    # The manuscript prints supplement numbers, so it must be newer than the supplement too.
    _check_pdf_is_current(pdf, [main_tex, *supp_sources, PAPER / "ref.bib", *figures])
    _check_pdf_is_current(supp_pdf, [*supp_sources, main_tex, PAPER / "ref.bib"])

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
    shutil.copy2(supp_pdf, out / f"{SUPPLEMENT_NAME}.pdf")
    shutil.copy2(HIGHLIGHTS, out / HIGHLIGHTS.name)

    staged = sorted(p for p in out.iterdir() if p.is_file())
    if any(p.is_dir() for p in out.iterdir()):
        raise SystemExit("The staged source set must not contain subfolders.")

    # The LaTeX source archive holds only what the manuscript build needs.
    source_suffixes = {".tex", ".bbl", ".bib", ".cls", ".bst", ".pdf", ".png", ".jpg", ".eps"}
    archive = out.parent / f"{out.name}_latex_source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in staged:
            if p.suffix in source_suffixes and p.name not in {f"{MANUSCRIPT_NAME}.pdf", f"{SUPPLEMENT_NAME}.pdf"}:
                zf.write(p, p.name)

    tables = _write_tables(text, out)

    print(f"Staged {len(staged)} files in {out}:")
    for p in staged:
        print(f"  {p.name} ({p.stat().st_size:,} bytes)")
    print(f"LaTeX source archive (no compiled PDFs): {archive}")
    print(f"Standalone tables ({len(tables) - 1} tables, compile with the manuscript .aux as tables.aux): {tables[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
