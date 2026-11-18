"""Build the anonymized artifact package that accompanies the submission.

The manuscript's open-science statement promises the middleware, the benchmark
construction and split scripts, every experiment, table, and figure script, the
run manifests, and the result records behind every reported number. This script
produces exactly that, as a single zip, with three properties the submission
depends on:

1. **The layout is runnable.** Scripts under ``src/experiments`` resolve the
   repository root as ``parents[2]`` and read ``data/`` from it, so the package
   keeps the real ``src/`` and ``data/`` tree rather than flattening it. A
   reviewer can unzip and run without rewriting paths.
2. **It carries no author identity.** Names, the repository URL, and the
   preprint URL are rewritten during staging, and the build fails if any
   survives the pass.
3. **It redistributes nothing it may not.** Third-party corpora are referenced
   by their acquisition scripts, not shipped; PhysioNet-derived clinical text is
   excluded outright.

Every exclusion below carries its reason, and those reasons are rendered into
the package README, so what the README claims and what the zip contains cannot
drift apart.

With ``--named`` the same tree is packaged for public archiving (for example on
Zenodo) instead of anonymous review: author names, the repository URL, and the
preprint identifier are kept, and only build-host details -- private network
addresses, the rented GPU container hostname, and local checkout paths -- are
rewritten. The named package also carries the human labels that validate the
benchmark's leakage judge, which live under ``data/`` beside the excluded
benchmark of the earlier version, and the repository's LICENSE and NOTICE.
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "prompt_mediation_artifact"

# Trees copied into the package, in package-relative form.
SOURCE_TREES = ("src", "data")

# Only these extensions travel. Anything else in the tree is a build product,
# an editor artifact, or a binary we have no reason to ship.
TEXT_EXTENSIONS = {".py", ".csv", ".json", ".jsonl", ".md", ".txt", ".cfg",
                   ".toml", ".yaml", ".yml", ".bib"}
KEEP_EXTENSIONS = TEXT_EXTENSIONS | {".gitkeep"}

# Raw stdout capture. It quotes absolute paths on the machines the runs
# executed on, and the provenance a reader actually needs is in the run
# manifests, so it is dropped rather than scrubbed.
_RAW_LOG_REASON = (
    "Raw stdout capture from the experiment runs. It quotes absolute paths on "
    "the machines that executed them; the provenance a reader needs -- model "
    "digests, quantization, decoding settings, seeds, context length, library "
    "versions, hardware -- is in the *_runtime_manifest_*.csv files, which are "
    "included."
)

# Directory names dropped anywhere in the tree, with the reason shown in the
# package README.
EXCLUDED_DIRS = {
    "__pycache__": "Python bytecode.",
    ".pytest_cache": "Test-runner cache.",
    ".ipynb_checkpoints": "Notebook editor state.",
    "external_data": (
        "Third-party corpora downloaded during setup (PrivacyLens task data, "
        "TAB ECHR splits). They are public and are fetched by the acquisition "
        "scripts in src/experiments; redistributing them here would add ~75 MB "
        "and duplicate their upstream terms."
    ),
    "run_logs": _RAW_LOG_REASON,
    "logs": _RAW_LOG_REASON,
}

# Individual files dropped by name, anywhere in the tree.
_ANNOTATION_UI_REASON = (
    "Annotator-facing tooling (a labeling page builder, a blind-review UI, and a "
    "translation aid shown to annotators). The labels it collected are included; "
    "the tooling is not needed to reproduce any number."
)
EXCLUDED_NAMES = {
    "build_annotation_page.py": _ANNOTATION_UI_REASON,
    "cppb_blind_review_ui.py": _ANNOTATION_UI_REASON,
    "fact_translations_zh.json": _ANNOTATION_UI_REASON,
    "privacylens_secret_translations_zh.json": _ANNOTATION_UI_REASON,
    "AGENTS.md": "Coding-assistant rule file; not part of the research record.",
    "package_artifact.py": (
        "The packaging script itself. It names the identifiers it scrubs, so "
        "shipping it would reintroduce exactly what it removes; the policy it "
        "applies is rendered into this README instead."
    ),
}

# Path globs (package-relative, posix, matched case-insensitively) dropped with cause.
_CPPB_REASON = (
    "The constructed prompt benchmark of an earlier version of the work. The "
    "manuscript no longer reports any result on it, and its dataset card links "
    "to a public release, so it is left out of this package."
)
EXCLUDED_GLOBS = {
    "data/*": _CPPB_REASON,
    "*cppb*": _CPPB_REASON,
    "src/experiments/physionet_deid_relabeled_export*.jsonl": (
        "PhysioNet-derived clinical note text. PhysioNet data is obtained under "
        "a credentialed use agreement and is not ours to redistribute. The "
        "derived per-document metrics and the prompt-wrapped manifest, which "
        "carry no note text, are included."
    ),
    "src/experiments/ai4privacy_pii300k_english_export*.jsonl": (
        "A 34 MB export of a public third-party corpus. The acquisition script "
        "in src/experiments regenerates it; the derived per-document metrics "
        "are included."
    ),
}

# Files under data/ that the named package keeps: the human labels behind the
# validation of the benchmark's own leakage judge. The anonymous package drops
# all of data/ with the earlier benchmark.
NAMED_DATA_KEEP = ("data/privacylens_judge_human_annotations.csv",
                   "data/privacylens_judge_human_annotations2.csv")

# Repository-root files the named package carries.
NAMED_ROOT_FILES = ("LICENSE", "NOTICE")

# Any single file larger than this is a redistribution we did not intend.
MAX_FILE_BYTES = 12 * 1024 * 1024

# Identity rewrites applied to every shipped text file. Order matters: the
# longer forms are rewritten before the substrings they contain.
REDACTIONS = (
    (re.compile(r"Ma,\s*Bo\s+and\s+Wu,\s*Jinsong\s+and\s+Yan,\s*Weiqi"),
     "Anonymous Authors"),
    (re.compile(r"ma2026bodhipromptshield"), "anon2026bodhipromptshield"),
    (re.compile(r"https?://github\.com/mabo1215/[A-Za-z0-9_.-]+"),
     "[repository URL withheld for anonymous review]"),
    (re.compile(r"https?://arxiv\.org/abs/[0-9]{4}\.[0-9]{4,5}(v[0-9]+)?"),
     "[preprint URL withheld for anonymous review]"),
    (re.compile(r"arXiv\s+preprint\s+arXiv:[0-9]{4}\.[0-9]{4,5}(v[0-9]+)?"),
     "preprint [identifier withheld for anonymous review]"),
    (re.compile(r"arXiv:[0-9]{4}\.[0-9]{4,5}(v[0-9]+)?"),
     "[preprint identifier withheld for anonymous review]"),
    # A rented-container hostname is an account-scoped identifier. The hardware
    # description that actually matters for provenance is a separate field.
    (re.compile(r"autodl-container-[a-z0-9]+-[a-z0-9]+"), "anonymized-gpu-host"),
    # The system name is linked to the public preprint, so it is replaced with a
    # neutral one; the manuscript does not use it either.
    (re.compile(r"[A-Za-z]:/source/BodhiPromptShield"), "<repository root>"),
    (re.compile(r"BodhiPromptShield"), "PromptMediation"),
    (re.compile(r"bodhipromptshield"), "promptmediation"),
    # Private-network host addresses of the machines the runs used.
    (re.compile(r"\b10\.126\.\d{1,3}\.\d{1,3}\b"), "<private-host>"),
)

# The named package keeps authorship and only rewrites build-host details.
NAMED_REDACTIONS = (
    (re.compile(r"autodl-container-[a-z0-9]+-[a-z0-9]+"), "rented-gpu-host"),
    (re.compile(r"[A-Za-z]:/source/BodhiPromptShield"), "<repository root>"),
    (re.compile(r"\b10\.126\.\d{1,3}\.\d{1,3}\b"), "<private-host>"),
)

# What must not survive into the named package: personal e-mail addresses,
# build-host identifiers, and local account paths.
NAMED_FORBIDDEN = (
    re.compile(r"\bamabo\w*@", re.I),
    re.compile(r"\bmabo1215@", re.I),
    re.compile(r"autodl-container-", re.I),
    re.compile(r"[A-Za-z]:\\+[Ss]ource\\+", re.I),
    re.compile(r"/root/autodl"),
    re.compile(r"[A-Za-z]:\\+Users\\+", re.I),
    re.compile(r"AppData\\+", re.I),
    re.compile(r"\b10\.126\.\d"),
    re.compile(r"[A-Za-z]:/source/", re.I),
)

# The build fails if any of these survive staging. Kept deliberately wider than
# the rewrite list above, so a new leak in a new file is caught rather than
# silently shipped.
FORBIDDEN = (
    re.compile(r"mabo1215", re.I),
    re.compile(r"\bamabo\w*@", re.I),
    re.compile(r"arxiv\.org/abs/", re.I),
    re.compile(r"\bWu,\s*Jinsong\b", re.I),
    re.compile(r"\bYan,\s*Weiqi\b", re.I),
    re.compile(r"\bMa,\s*Bo\b", re.I),
    re.compile(r"Auckland University of Technology", re.I),
    re.compile(r"Guilin University", re.I),
    re.compile(r"autodl-container-", re.I),
    re.compile(r"[A-Za-z]:\\+[Ss]ource\\+", re.I),
    re.compile(r"/root/autodl"),
    # A Windows profile path carries an account name or number, which is an
    # identifier even when it is a number. The earlier list only caught
    # C:\source and shipped C:\Users\<account>\AppData in a data README.
    re.compile(r"[A-Za-z]:\\+Users\\+", re.I),
    re.compile(r"AppData\\+", re.I),
    re.compile(r"bodhi", re.I),
    re.compile(r"2604\.05793"),
    re.compile(r"\b10\.126\.\d"),
    re.compile(r"[A-Za-z]:/source/", re.I),
    # No generic /home/<user>/ rule: the PrivacyLens benchmark's synthetic
    # content contains /home/john/ and /home/jane/, and a check that fires on
    # benchmark data is a check the next person disables. The real account name
    # is already covered by the mabo1215 pattern above.
)


def _excluded(rel: Path, named: bool = False) -> str | None:
    """Return the reason this path is excluded, or None to include it."""
    posix = rel.as_posix()
    if named and any(fnmatch.fnmatch(posix, keep) for keep in NAMED_DATA_KEEP):
        return None
    for part in rel.parts[:-1]:
        if part in EXCLUDED_DIRS:
            return EXCLUDED_DIRS[part]
    if rel.name in EXCLUDED_NAMES:
        return EXCLUDED_NAMES[rel.name]
    posix = rel.as_posix().lower()
    for glob, reason in EXCLUDED_GLOBS.items():
        if fnmatch.fnmatch(posix, glob):
            return reason
    if rel.suffix.lower() not in KEEP_EXTENSIONS:
        return "extension not shipped"
    return None


def _redact(text: str, named: bool = False) -> tuple[str, int]:
    total = 0
    for pattern, replacement in (NAMED_REDACTIONS if named else REDACTIONS):
        text, n = pattern.subn(replacement, text)
        total += n
    return text, total


def stage(root: Path, dest: Path, named: bool = False) -> tuple[list[Path], int, dict[str, int]]:
    """Copy the shippable tree into ``dest``, redacting as it goes."""
    staged: list[Path] = []
    redactions = 0
    skipped: dict[str, int] = {}

    for tree in SOURCE_TREES:
        base = root / tree
        if not base.exists():
            raise SystemExit(f"missing source tree: {base}")
        # Tracked files only: caches and scratch outputs that were never
        # committed are not part of the record and must not travel.
        tracked = subprocess.run(["git", "ls-files", "-z", tree], cwd=root, capture_output=True, check=True).stdout
        for name in sorted(n for n in tracked.decode("utf-8").split("\0") if n):
            path = root / name
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            reason = _excluded(rel, named)
            if reason is not None:
                skipped[reason] = skipped.get(reason, 0) + 1
                continue
            if path.stat().st_size > MAX_FILE_BYTES:
                skipped[f"larger than {MAX_FILE_BYTES // (1024 * 1024)} MB"] = (
                    skipped.get(f"larger than {MAX_FILE_BYTES // (1024 * 1024)} MB", 0) + 1)
                continue

            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel.suffix.lower() in TEXT_EXTENSIONS:
                # newline="" preserves each file's own line endings; the
                # redaction is a substring rewrite and must not reformat.
                with path.open(encoding="utf-8", errors="surrogateescape",
                               newline="") as handle:
                    original = handle.read()
                cleaned, n = _redact(original, named)
                redactions += n
                with target.open("w", encoding="utf-8", errors="surrogateescape",
                                 newline="") as handle:
                    handle.write(cleaned)
            else:
                shutil.copy2(path, target)
            staged.append(rel)

    if named:
        for name in NAMED_ROOT_FILES:
            shutil.copy2(root / name, dest / name)
            staged.append(Path(name))

    return staged, redactions, skipped


def verify(dest: Path, named: bool = False) -> None:
    """Fail the build if any forbidden identifier survived staging."""
    hits: list[str] = []
    forbidden = NAMED_FORBIDDEN if named else FORBIDDEN
    for path in sorted(dest.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        for pattern in forbidden:
            match = pattern.search(text)
            if match:
                rel = path.relative_to(dest).as_posix()
                hits.append(f"{rel}: {pattern.pattern} -> {match.group(0)!r}")
    if hits:
        raise SystemExit("identifier check failed:\n  " + "\n  ".join(hits[:40]))


# A shipped Markdown file may knowingly name a label the manuscript has
# retired -- for instance when it lists what a script can write rather than
# what the paper contains. It declares those on one line so the claim is
# deliberate and visible in review, rather than the check being loosened for
# everyone:
#
#     <!-- retired-labels: tab:catwise, tab:lto -->
_RETIRED_DECLARATION = re.compile(r"<!--\s*retired-labels:([^>]*)-->", re.I)
_LABEL_REFERENCE = re.compile(r"\b((?:tab|fig):[A-Za-z0-9_:-]+)")


def _manuscript_labels(root: Path) -> set[str] | None:
    """Every label the manuscript defines, or None if it is not checked out."""
    sources = [root / "paper" / "main.tex", root / "paper" / "appendix.tex"]
    if not all(path.exists() for path in sources):
        return None
    labels: set[str] = set()
    for path in sources:
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        labels.update(re.findall(r"\\label\{((?:tab|fig):[^}]+)\}", text))
    return labels


def verify_documentation(root: Path, dest: Path) -> None:
    """Fail the build if shipped prose names a table or figure the paper lacks.

    Documentation rots quietly. Three separate files in this package once
    described tables from an earlier version of the manuscript, and every one
    of them was found by a person reading rather than by a check. A reviewer
    who follows a README to a table that does not exist learns something about
    the artifact that is not true of the science, so this refuses to ship it.

    Only Markdown is checked. Scripts legitimately carry code for labels the
    manuscript no longer uses -- a builder whose label is absent simply does
    nothing -- and failing on that would mean deleting working code to satisfy
    a check.
    """
    labels = _manuscript_labels(root)
    if labels is None:
        print("[package] manuscript not checked out; skipping documentation check")
        return

    hits: list[str] = []
    for path in sorted(dest.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        declared = set()
        for block in _RETIRED_DECLARATION.findall(text):
            declared.update(part.strip() for part in block.replace(",", " ").split())
        unknown = {ref for ref in _LABEL_REFERENCE.findall(text)} - labels - declared
        for ref in sorted(unknown):
            hits.append(f"{path.relative_to(dest).as_posix()}: {ref}")
    if hits:
        raise SystemExit(
            "documentation check failed -- shipped prose names manuscript "
            "objects that do not exist:\n  " + "\n  ".join(hits[:40]) +
            "\n\nFix the file, or declare the ones it names on purpose with a "
            "<!-- retired-labels: ... --> line.")
    print(f"[package] documentation check: every label named in shipped prose "
          f"exists in the manuscript ({len(labels)} labels)")


def write_manifest(dest: Path, staged: list[Path]) -> Path:
    """List every shipped file with its size and SHA-256."""
    out = dest / "MANIFEST.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["path", "bytes", "sha256"])
        for rel in staged:
            blob = (dest / rel).read_bytes()
            writer.writerow([rel.as_posix(), len(blob), hashlib.sha256(blob).hexdigest()])
    return out


def write_readme(dest: Path, staged: list[Path], skipped: dict[str, int], named: bool = False) -> Path:
    exclusions = "\n".join(
        f"- **{count} file(s)** — {reason}"
        for reason, count in sorted(skipped.items(), key=lambda kv: -kv[1])
        if reason != "extension not shipped"
    )
    if named:
        header = (
            "Code and per-unit records for the paper by Bo Ma, Weiqi Yan, and Jinsong Wu.\n"
            "An archived snapshot of https://github.com/mabo1215/BodhiPromptShield, "
            f"{len(staged)} files. The code is released under the Apache License 2.0 "
            "(LICENSE, NOTICE); external datasets remain under their own terms.\n"
        )
        labels_note = """
## Human labels

    src/experiments/semantic_inferability_*      Inferability labels: the
                        sheets each annotator answered, the agreement and
                        per-method summaries, and the keys that map items to
                        methods.
    data/privacylens_judge_human_annotations{,2}.csv
                        Two annotators' labels on 120 decisions of the
                        benchmark's own leakage judge.

Nothing was recorded about the annotators beyond their labels.
"""
        privacy_note = """## Build-host details

Private network addresses of the evaluation hosts, the rented GPU container
hostname, and local checkout paths were rewritten before packaging. Hardware
descriptions, model digests, decoding settings, and seeds are untouched. The
build refuses to produce a zip if a personal e-mail address or any of those
host details survives the pass.
"""
    else:
        header = f"Anonymous supplementary material. {len(staged)} files.\n"
        labels_note = ""
        privacy_note = """## Anonymization

Author names, the system name used in an earlier version, the code repository
URL, the preprint identifier, private host addresses, and the rented GPU
container hostname were rewritten before packaging. Hardware descriptions,
model digests, decoding settings, and seeds are untouched, so the provenance a
reviewer needs to check a number is intact. The build refuses to produce a zip
if any of those identifiers survives the pass.
"""
    text = f"""# Artifact for "What Prompt Mediation Stops in LLM Agent Pipelines, and How to Measure It"

{header}
## Layout

    src/experiments/    The mediation layer itself -- detectors and sanitization
                        modes in mediation_baselines.py, the agent-pipeline
                        element in agentdojo_restoration_suite.py -- and every
                        experiment, baseline, benchmark-construction and
                        analysis script, together with the result records
                        (*_results.csv, *_rows_*.csv, *_summary_*.csv) and the
                        run manifests (*_runtime_manifest_*.csv) that record
                        model digests, quantization, decoding settings, seeds,
                        context length, library versions, and hardware.
    src/figures/        The figure scripts that produce the manuscript figures.
    src/algorithms/     Not the mediation layer: 123 lines of unrelated code from
                        an earlier project, kept only because run_all.py imports
                        them as a smoke test.
    MANIFEST.csv        Every shipped file with size and SHA-256.

The tree keeps its repository-relative shape on purpose: the scripts resolve
the project root two levels above `src/experiments`, so they run from an
unzipped copy without path edits.
{labels_note}
## Reproducing

    python -m pip install -r src/requirements.txt
    python src/experiments/acquire_external_resources.py   # public corpora
    python src/run_all.py                                  # controlled surface
    python src/figures/run_all_figures.py                  # manuscript figures

Model-serving experiments expect an OpenAI-compatible local endpoint at
`http://127.0.0.1:11434` and the open-weight models named in the run manifests.

## What is not included, and why

{exclusions}

Third-party corpora are referenced rather than shipped; the acquisition scripts
in `src/experiments` document the exact source and version of each. External
datasets remain under their own licenses and access terms.

{privacy_note}"""
    out = dest / "README.md"
    out.write_text(text, encoding="utf-8")
    return out


def build(root: Path, out_zip: Path, named: bool = False) -> None:
    if out_zip.exists():
        raise SystemExit(
            f"{out_zip} already exists; move or delete it first rather than "
            f"overwriting a package that may already have been submitted.")

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / PACKAGE_NAME
        dest.mkdir(parents=True)

        staged, redactions, skipped = stage(root, dest, named)
        verify(dest, named)
        verify_documentation(root, dest)

        write_manifest(dest, staged)
        write_readme(dest, staged, skipped, named)

        out_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for path in sorted(dest.rglob("*")):
                if path.is_file():
                    zf.write(path, Path(PACKAGE_NAME) / path.relative_to(dest))

    size = out_zip.stat().st_size
    print(f"[package] {len(staged)} files, {redactions} rewrites ({'named' if named else 'anonymous'} package)")
    for reason, count in sorted(skipped.items(), key=lambda kv: -kv[1]):
        print(f"[package] skipped {count:>4}  {reason[:88]}")
    print(f"[package] wrote {out_zip} ({size / 1e6:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--named", action="store_true",
                        help="keep authorship for public archiving; rewrite build-host details only")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    default = (REPO_ROOT / "submit" / "zenodo" / f"{PACKAGE_NAME}.zip" if args.named
               else REPO_ROOT / "submit" / f"{PACKAGE_NAME}_anonymous.zip")
    build(REPO_ROOT, Path(args.out) if args.out else default, args.named)


if __name__ == "__main__":
    main()
