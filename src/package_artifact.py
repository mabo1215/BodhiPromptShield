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
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "BodhiPromptShield_artifact"

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
EXCLUDED_NAMES = {
    "AGENTS.md": "Coding-assistant rule file; not part of the research record.",
    "package_artifact.py": (
        "The packaging script itself. It names the identifiers it scrubs, so "
        "shipping it would reintroduce exactly what it removes; the policy it "
        "applies is rendered into this README instead."
    ),
}

# Path globs (package-relative, posix) dropped with cause.
EXCLUDED_GLOBS = {
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
)


def _excluded(rel: Path) -> str | None:
    """Return the reason this path is excluded, or None to include it."""
    for part in rel.parts[:-1]:
        if part in EXCLUDED_DIRS:
            return EXCLUDED_DIRS[part]
    if rel.name in EXCLUDED_NAMES:
        return EXCLUDED_NAMES[rel.name]
    posix = rel.as_posix()
    for glob, reason in EXCLUDED_GLOBS.items():
        if fnmatch.fnmatch(posix, glob):
            return reason
    if rel.suffix.lower() not in KEEP_EXTENSIONS:
        return "extension not shipped"
    return None


def _redact(text: str) -> tuple[str, int]:
    total = 0
    for pattern, replacement in REDACTIONS:
        text, n = pattern.subn(replacement, text)
        total += n
    return text, total


def stage(root: Path, dest: Path) -> tuple[list[Path], int, dict[str, int]]:
    """Copy the shippable tree into ``dest``, redacting as it goes."""
    staged: list[Path] = []
    redactions = 0
    skipped: dict[str, int] = {}

    for tree in SOURCE_TREES:
        base = root / tree
        if not base.exists():
            raise SystemExit(f"missing source tree: {base}")
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            reason = _excluded(rel)
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
                cleaned, n = _redact(original)
                redactions += n
                with target.open("w", encoding="utf-8", errors="surrogateescape",
                                 newline="") as handle:
                    handle.write(cleaned)
            else:
                shutil.copy2(path, target)
            staged.append(rel)

    return staged, redactions, skipped


def verify(dest: Path) -> None:
    """Fail the build if any forbidden identifier survived staging."""
    hits: list[str] = []
    for path in sorted(dest.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        for pattern in FORBIDDEN:
            match = pattern.search(text)
            if match:
                rel = path.relative_to(dest).as_posix()
                hits.append(f"{rel}: {pattern.pattern} -> {match.group(0)!r}")
    if hits:
        raise SystemExit("anonymity check failed:\n  " + "\n  ".join(hits[:40]))


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


def write_readme(dest: Path, staged: list[Path], skipped: dict[str, int]) -> Path:
    exclusions = "\n".join(
        f"- **{count} file(s)** — {reason}"
        for reason, count in sorted(skipped.items(), key=lambda kv: -kv[1])
        if reason != "extension not shipped"
    )
    text = f"""# Artifact for "BodhiPromptShield: Pre-Inference Prompt Mediation for Surface-Form Privacy Propagation in LLM Agent Pipelines"

Anonymous supplementary material. {len(staged)} files.

## Layout

    src/algorithms/     Mediation mechanism and the supporting algorithms.
    src/experiments/    Every experiment, baseline, benchmark-construction and
                        analysis script, together with the result records
                        (*_results.csv, *_rows_*.csv, *_summary_*.csv) and the
                        run manifests (*_runtime_manifest_*.csv) that record
                        model digests, quantization, decoding settings, seeds,
                        context length, library versions, and hardware.
    src/figures/        The figure scripts that produce the manuscript figures.
    data/               The paper's own template-derived benchmark (CPPB) and
                        its annotation records.
    MANIFEST.csv        Every shipped file with size and SHA-256.

The tree keeps its repository-relative shape on purpose: the scripts resolve
the project root two levels above `src/experiments` and read `data/` from
there, so they run from an unzipped copy without path edits.

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

## Anonymization

Author names, the code repository URL, the preprint identifier, and the rented
GPU container hostname were rewritten before packaging. Hardware descriptions,
model digests, decoding settings, and seeds are untouched, so the provenance a
reviewer needs to check a number is intact. The build refuses to produce a zip
if any of those identifiers survives the pass.
"""
    out = dest / "README.md"
    out.write_text(text, encoding="utf-8")
    return out


def build(root: Path, out_zip: Path) -> None:
    if out_zip.exists():
        raise SystemExit(
            f"{out_zip} already exists; move or delete it first rather than "
            f"overwriting a package that may already have been submitted.")

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / PACKAGE_NAME
        dest.mkdir(parents=True)

        staged, redactions, skipped = stage(root, dest)
        verify(dest)

        write_manifest(dest, staged)
        write_readme(dest, staged, skipped)

        out_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for path in sorted(dest.rglob("*")):
                if path.is_file():
                    zf.write(path, Path(PACKAGE_NAME) / path.relative_to(dest))

    size = out_zip.stat().st_size
    print(f"[package] {len(staged)} files, {redactions} identity rewrites")
    for reason, count in sorted(skipped.items(), key=lambda kv: -kv[1]):
        print(f"[package] skipped {count:>4}  {reason[:88]}")
    print(f"[package] wrote {out_zip} ({size / 1e6:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(REPO_ROOT / "submit" /
                                             f"{PACKAGE_NAME}_anonymous.zip"))
    args = parser.parse_args()
    build(REPO_ROOT, Path(args.out))


if __name__ == "__main__":
    main()
