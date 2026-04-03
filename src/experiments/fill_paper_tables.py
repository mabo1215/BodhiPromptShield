"""
Fill code-backed empirical tables in paper/main.tex from CSV files under src/experiments.

This script only updates tables that are directly backed by repository CSVs:
  - tab:cppb_card        <- cppb_accounting_summary.csv
  - tab:per              <- prompt_method_comparison.csv
  - tab:utility          <- prompt_method_comparison.csv
  - tab:pi_sensitivity   <- policy_sensitivity.csv
  - tab:propagation      <- agent_pipeline_metrics.csv
  - tab:latency          <- latency_overhead.csv
  - tab:restore          <- restoration_boundary_analysis.csv
  - tab:ablation         <- sanitization_mode_ablation.csv
    - tab:multiseed        <- multiseed_method_summary.csv
    - tab:lto              <- leavetemplateout_summary.csv
    - tab:baseline         <- external_baseline_comparison.csv

It intentionally does NOT touch illustrative or manually curated tables such as:
  - tab:example
  - tab:tradeoff
  - tab:catwise
  - tab:multimodal
  - tab:crossmodel
  - tab:hardcase

Usage:
  python src/experiments/fill_paper_tables.py
  python src/experiments/fill_paper_tables.py --paper paper/main.tex --dry-run
"""
from __future__ import annotations

import argparse
import csv
import os
import re
from typing import Callable


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXPERIMENTS_DIR = os.path.dirname(os.path.abspath(__file__))


def _read_csv(name: str) -> list[dict[str, str]]:
    path = os.path.join(EXPERIMENTS_DIR, name)
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _paper_path(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(REPO_ROOT, path)


def _replace_table_block(content: str, label: str, replacement: str) -> str:
    label_idx = content.find(f"\\label{{{label}}}")
    if label_idx == -1:
        raise ValueError(f"Label not found: {label}")

    begin_match = re.search(r"\\begin\{tabularx?\}", content[label_idx:])
    if not begin_match:
        raise ValueError(f"No tabular/tabularx found after {label}")
    begin_idx = label_idx + begin_match.start()
    begin_env = begin_match.group(0)
    end_env = "\\end{tabularx}" if begin_env == "\\begin{tabularx}" else "\\end{tabular}"
    end_idx = content.find(end_env, begin_idx)
    if end_idx == -1:
        raise ValueError(f"No matching {end_env} found for {label}")
    end_idx += len(end_env)
    return content[:begin_idx] + replacement + content[end_idx:]


def _fmt_float(value: str, digits: int = 1) -> str:
    return f"{float(value):.{digits}f}"


def _tex_escape(text: str) -> str:
    return (
        text.replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def build_cppb_accounting_table() -> str:
    rows = sorted(_read_csv("cppb_accounting_summary.csv"), key=lambda r: int(r["order"]))
    body = "\n".join(
        f"{_tex_escape(r['axis'])} & {_tex_escape(r['breakdown'])} \\\\" for r in rows
    )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}p{1.65cm}X}\n"
        "\\toprule\n"
        "Axis & Exact accounting \\\\\n"
        "\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n"
        "\\end{tabularx}"
    )


def build_per_table() -> str:
    rows = _read_csv("prompt_method_comparison.csv")
    body = "\n".join(f"{r['method']} & {_fmt_float(r['per'])} \\\\" for r in rows)
    return (
        "\\begin{tabular}{lc}\n"
        "\\toprule\n"
        "Method & PER (\\%) \\\\\n"
        "\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n"
        "\\end{tabular}"
    )


def build_utility_table() -> str:
    rows = _read_csv("prompt_method_comparison.csv")
    body = "\n".join(
        f"{r['method']} & {float(r['ac']):.2f} & {float(r['tsr']):.2f} \\\\" for r in rows
    )
    return (
        "\\begin{tabular}{lcc}\n"
        "\\toprule\n"
        "Method & AC & TSR \\\\\n"
        "\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n"
        "\\end{tabular}"
    )


def build_pi_table() -> str:
    tau_map = {"Lenient": "0.70", "Balanced": "0.55", "Strict": "0.40"}
    rows = _read_csv("policy_sensitivity.csv")
    body_lines = []
    for r in rows:
        profile = r["profile"]
        tau = tau_map.get(profile, "--")
        profile_label = f"{profile} ($\\tau={tau}$)"
        body_lines.append(
            f"{profile_label} & {_fmt_float(r['per'])} & {float(r['upr']):.2f} & {float(r['tsr']):.2f} \\\\"
        )
    return (
        "\\begin{tabular}{lccc}\n"
        "\\toprule\n"
        "Policy profile & PER (\\%) & UPR & TSR \\\\\n"
        "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        "\\end{tabular}"
    )


def build_propagation_table() -> str:
    rows = _read_csv("agent_pipeline_metrics.csv")
    body = "\n".join(
        f"{r['method']} & {_fmt_float(r['retrieval'])} & {_fmt_float(r['memory'])} & {_fmt_float(r['tool'])} \\\\"
        for r in rows
    )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xccc}\n"
        "\\toprule\n"
        "Setting & Retrieval SPE (\\%) & Memory SPE (\\%) & Tool SPE (\\%) \\\\\n"
        "\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n"
        "\\end{tabularx}"
    )


def build_latency_table() -> str:
    rows = _read_csv("latency_overhead.csv")
    body = "\n".join(
        f"{r['pipeline']} & {int(float(r['mean_ms']))} & {int(float(r['p95_ms']))} \\\\" for r in rows
    )
    return (
        "\\begin{tabular}{lcc}\n"
        "\\toprule\n"
        "Pipeline & Mean Latency (ms) & P95 (ms) \\\\\n"
        "\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n"
        "\\end{tabular}"
    )


def build_restore_table() -> str:
    rows = _read_csv("restoration_boundary_analysis.csv")
    body_lines = []
    for r in rows:
        rsr = "--" if not r["rsr"] else f"{float(r['rsr']):.2f}"
        body_lines.append(
            f"{r['setting']} & {float(r['tsr']):.2f} & {rsr} & {_fmt_float(r['blr'])} \\\\"
        )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xccc}\n"
        "\\toprule\n"
        "Setting & TSR & RSR & BLR (\\%) \\\\\n"
        "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        "\\end{tabularx}"
    )


def build_ablation_table() -> str:
    rows = _read_csv("sanitization_mode_ablation.csv")
    body = "\n".join(
        f"{r['mode']} & {_fmt_float(r['per'])} & {float(r['upr']):.2f} \\\\" for r in rows
    )
    return (
        "\\begin{tabular}{lcc}\n"
        "\\toprule\n"
        "Sanitization Mode & PER (\\%) & UPR \\\\\n"
        "\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n"
        "\\end{tabular}"
    )


def _fmt_pm(mean_key: str, std_key: str, row: dict[str, str], digits: int = 2) -> str:
    return f"{float(row[mean_key]):.{digits}f} $\\pm$ {float(row[std_key]):.{digits}f}"


def build_multiseed_table() -> str:
    rows = _read_csv("multiseed_method_summary.csv")
    body_lines = []
    for row in rows:
        body_lines.append(
            " & ".join(
                [
                    row["setting"],
                    _fmt_pm("per_mean", "per_std", row, digits=1),
                    _fmt_pm("ac_mean", "ac_std", row),
                    _fmt_pm("tsr_mean", "tsr_std", row),
                    f"{float(row['latency_mean_ms']):.1f} $\\pm$ {float(row['latency_std_ms']):.1f}",
                ]
            )
            + " \\\\"
        )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xcccc}\n"
        "\\toprule\n"
        "Setting & PER (\\%) & AC & TSR & Mean Latency (ms) \\\\\n"
        "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        "\\end{tabularx}"
    )


def build_lto_table() -> str:
    rows = _read_csv("leavetemplateout_summary.csv")
    display_rows = [row for row in rows if row["group"] in {"Direct requests", "Document-oriented", "Retrieval-style", "Tool-oriented agent", "Overall"}]
    body_lines = []
    for row in display_rows:
        body_lines.append(
            " & ".join(
                [
                    row["group"],
                    row["held_out_prompts"],
                    f"{float(row['span_f1_mean']):.2f}",
                    _fmt_pm("per_mean", "per_std", row, digits=1),
                    f"{float(row['ac_mean']):.2f}",
                    f"{float(row['tsr_mean']):.2f}",
                ]
            )
            + " \\\\"
        )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xccccc}\n"
        "\\toprule\n"
        "Held-out split & Prompts & Span F1 & PER (\\%) & AC & TSR \\\\\n"
        "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        "\\end{tabularx}"
    )


def build_baseline_table() -> str:
    rows = _read_csv("external_baseline_comparison.csv")
    body_lines = []
    for row in rows:
        body_lines.append(
            " & ".join(
                [
                    _tex_escape(row["method"]),
                    f"{float(row['span_f1']):.2f}",
                    _fmt_float(row["per_percent"]),
                    f"{float(row['ac']):.2f}",
                    f"{float(row['tsr']):.2f}",
                ]
            )
            + " \\\\"
        )
    return (
        "\\begin{tabular}{lcccc}\n"
        "\\toprule\n"
        "Method & Span F1 & PER (\\%) & AC & TSR \\\\\n"
        "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        "\\end{tabular}"
    )


TABLE_BUILDERS: dict[str, Callable[[], str]] = {
    "tab:cppb_card": build_cppb_accounting_table,
    "tab:per": build_per_table,
    "tab:utility": build_utility_table,
    "tab:pi_sensitivity": build_pi_table,
    "tab:propagation": build_propagation_table,
    "tab:latency": build_latency_table,
    "tab:restore": build_restore_table,
    "tab:ablation": build_ablation_table,
    "tab:multiseed": build_multiseed_table,
    "tab:lto": build_lto_table,
    "tab:baseline": build_baseline_table,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill code-backed paper tables from experiment CSVs.")
    parser.add_argument("--paper", default="paper/main.tex", help="Path to paper/main.tex")
    parser.add_argument("--dry-run", action="store_true", help="Print updated labels without writing file")
    args = parser.parse_args()

    paper_path = _paper_path(args.paper)
    with open(paper_path, "r", encoding="utf-8") as f:
        content = f.read()

    updated_labels = []
    for label, builder in TABLE_BUILDERS.items():
        if f"\\label{{{label}}}" not in content:
            continue
        content = _replace_table_block(content, label, builder())
        updated_labels.append(label)

    if not updated_labels:
        raise ValueError(f"No known code-backed labels found in {paper_path}")

    if args.dry_run:
        print("Would update:", ", ".join(updated_labels))
        return 0

    with open(paper_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated code-backed tables in", paper_path, "->", ", ".join(updated_labels))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
