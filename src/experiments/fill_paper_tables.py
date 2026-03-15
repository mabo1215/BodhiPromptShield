"""
Run experiments (ablation and/or baselines), then update paper/main.tex table bodies
with the generated results. This enables "run code -> fill paper" in one step.

Usage (from repo root):
  python -m experiments.fill_paper_tables
  python -m experiments.fill_paper_tables --reaedp C:/source/REAEDP/data
  python -m experiments.fill_paper_tables --paper paper/main.tex --ablation-csv out/ablation_table.csv

Options:
  --reaedp DIR     Run ablation with prior_ablation_table --reaedp DIR and use output for tab:ablation.
  --paper PATH     Path to main.tex (default: paper/main.tex from repo root).
  --run-ablation   Run prior_ablation_table (with --reaedp if given) and write ablation CSV to --out-dir.
  --ablation-csv   Use this CSV for tab:ablation instead of running (ignored if --run-ablation).
  --run-baselines  Run run_baselines.py if present and use its output for tab:baselines.
  --baseline-csv   Use this CSV for tab:baselines (optional).
  --out-dir DIR    Directory for ablation_table.csv / baseline_table.csv (default: same dir as script).
  --dry-run        Only run experiments and print would-be table content; do not modify main.tex.
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _escape_tex(s: str) -> str:
    """Escape & and preserve backslash for LaTeX cell content."""
    if not isinstance(s, str):
        s = str(s)
    return s.replace("&", "\\&").replace("%", "\\%")


def _config_latex(config: str) -> str:
    """Format Config column for ablation table: (A) -> DBN/PB with cite."""
    s = (config or "").strip()
    if "(A)" in s and ("DBN" in s or "PB" in s):
        return "(A) DBN/PB~\\cite{ma2021privacy}"
    if s == "(E) Full (ours)" or s == "(E)":
        return "(E) Full (ours)"
    if s == "(B)":
        return "(B) No boundary"
    if s == "(C)":
        return "(C) Internal center only"
    if s == "(D)":
        return "(D) Ring + center"
    return _escape_tex(s)


def run_ablation(reaedp_dir: str, out_dir: str) -> str | None:
    """Run prior_ablation_table and return path to ablation_table.csv."""
    csv_path = os.path.join(out_dir, "ablation_table.csv")
    cmd = [sys.executable, "-m", "experiments.prior_ablation_table", "--out", csv_path]
    if reaedp_dir and os.path.isdir(reaedp_dir):
        cmd.extend(["--reaedp", reaedp_dir])
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(REPO_ROOT, "src")
    try:
        subprocess.run(cmd, cwd=REPO_ROOT, check=True, capture_output=True, text=True, env=env)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return csv_path if os.path.isfile(csv_path) else None


def build_ablation_tabular(csv_path: str) -> str:
    """Build full \\begin{tabular}...\\end{tabular} body from ablation CSV."""
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            config = _config_latex(r.get("Config", ""))
            train = r.get("Train_acc", "--")
            val = r.get("Val_acc", "--")
            notes = _escape_tex(r.get("Notes", ""))
            rows.append(f"{config} & {train} & {val} & {notes} \\\\")
    header = "Config & Train acc. & Val acc. & Notes \\\\\n\\hline\n"
    body = "\n\\hline\n".join(rows) + "\n\\hline\n"
    return (
        "\\begin{tabular}{|l|c|c|l|}\n"
        "\\hline\n"
        + header
        + "\\hline\n"
        + body
        + "\\end{tabular}"
    )


def patch_main_tex(paper_path: str, label: str, new_tabular: str, dry_run: bool) -> bool:
    """Replace the tabular block for the given table label in main.tex."""
    path = os.path.join(REPO_ROOT, paper_path) if not os.path.isabs(paper_path) else paper_path
    if not os.path.isfile(path):
        print("Paper not found:", path, file=sys.stderr)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Find table: after \label{...} find the next \begin{tabular}...\end{tabular}
    label_needle = "\\label{" + label + "}"
    idx = content.find(label_needle)
    if idx == -1:
        print(f"Table {label} not found in {path}", file=sys.stderr)
        return False
    tab_begin = content.find("\\begin{tabular}", idx)
    if tab_begin == -1:
        print(f"Table {label}: no \\begin{{tabular}} after label.", file=sys.stderr)
        return False
    end_marker = "\\end{tabular}"
    tab_end = content.find(end_marker, tab_begin)
    if tab_end == -1:
        print(f"Table {label}: no \\end{{tabular}}.", file=sys.stderr)
        return False
    tab_end += len(end_marker)
    new_content = content[:tab_begin] + new_tabular + content[tab_end:]
    if dry_run:
        print("[dry-run] Would replace", label, "tabular with:\n", new_tabular[:300], "...")
        return True
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Updated", label, "in", path)
    return True


def main():
    ap = argparse.ArgumentParser(description="Run experiments and fill paper tables")
    ap.add_argument("--reaedp", default="", help="Path to REAEDP/data for ablation placeholder run")
    ap.add_argument("--paper", default="paper/main.tex", help="Path to main.tex")
    ap.add_argument("--run-ablation", action="store_true", help="Run prior_ablation_table and use output")
    ap.add_argument("--ablation-csv", default="", help="Use this CSV for tab:ablation (skip running)")
    ap.add_argument("--run-baselines", action="store_true", help="Run run_baselines.py if present")
    ap.add_argument("--baseline-csv", default="", help="Use this CSV for tab:baselines")
    ap.add_argument("--out-dir", default="", help="Output dir for CSVs (default: experiments dir)")
    ap.add_argument("--dry-run", action="store_true", help="Do not modify main.tex")
    args = ap.parse_args()

    out_dir = args.out_dir or os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out_dir, exist_ok=True)

    # Ablation: run or use provided CSV (run if --run-ablation or --reaedp given and no --ablation-csv)
    ablation_csv = args.ablation_csv
    if (args.run_ablation or args.reaedp) and not args.ablation_csv:
        csv_path = run_ablation(args.reaedp, out_dir)
        if csv_path:
            ablation_csv = csv_path
    if ablation_csv and os.path.isfile(ablation_csv):
        tabular = build_ablation_tabular(ablation_csv)
        patch_main_tex(args.paper, "tab:ablation", tabular, args.dry_run)
    elif args.run_ablation or args.ablation_csv:
        print("No ablation CSV produced or found; skipping tab:ablation.", file=sys.stderr)

    # Baselines: optional run + CSV -> tab:baselines (stub: only if baseline CSV exists)
    if args.baseline_csv and os.path.isfile(args.baseline_csv):
        # Build tab:baselines from CSV (columns: Method, Accuracy, Epsilon, Notes)
        try:
            with open(args.baseline_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = []
                for r in reader:
                    m = _escape_tex(r.get("Method", ""))
                    acc = _escape_tex(r.get("Accuracy", "--"))
                    eps = _escape_tex(r.get("Epsilon", "N/A"))
                    notes = _escape_tex(r.get("Notes", ""))
                    rows.append(f"{m} & {acc} & {eps} & {notes} \\\\")
                body = "\n\\hline\n".join(rows) + "\n\\hline\n"
                tabular = (
                    "\\begin{tabular}{|l|c|c|l|}\n"
                    "\\hline\n"
                    "Method & Accuracy (mean $\\pm$ std) & $\\varepsilon$ / privacy & Notes \\\\\n"
                    "\\hline\n"
                    + body
                    + "\\end{tabular}"
                )
                patch_main_tex(args.paper, "tab:baselines", tabular, args.dry_run)
        except Exception as e:
            print("Baseline table update failed:", e, file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
