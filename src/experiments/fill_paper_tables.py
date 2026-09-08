"""
Fill code-backed empirical tables in paper/main.tex from CSV files under src/experiments.

This script only updates tables that are directly backed by repository CSVs:
  - tab:cppb_card        <- cppb_accounting_summary.csv
  - tab:per              <- prompt_method_comparison.csv
  - tab:utility          <- prompt_method_comparison.csv
  - tab:pi_sensitivity   <- policy_sensitivity.csv
  - tab:propagation      <- agent_pipeline_metrics.csv
  - tab:latency          <- latency_overhead.csv
    - tab:catwise          <- categorywise_analysis.csv
    - tab:multimodal       <- multimodal_analysis.csv
    - tab:crossmodel       <- crossmodel_portability_results.csv
    - tab:lightclf         <- lightweight_classifier_comparison.csv
    - tab:judge            <- cppb_privacy_judge_comparison.csv
    - tab:measprop         <- propagation_suite_{ai4privacy,privacylens}_results_pooled.csv
    - tab:advmeas          <- measured_adaptive_adversary_results.csv
    - tab:mapadv           <- secure_mapping_adversary_results.csv
    - tab:hardcase         <- hardcase_analysis.csv
  - tab:restore          <- restoration_boundary_analysis.csv
  - tab:ablation         <- sanitization_mode_ablation.csv
    - tab:multiseed        <- multiseed_method_summary.csv
    - tab:lto              <- leavetemplateout_summary.csv
    - tab:baseline         <- external_baseline_comparison.csv
  - tab:tabtransfer      <- tab_transfer_results.csv
  - tab:ocrslice         <- {cord,funsd,sroie}_transfer_results.csv
  - tab:blindutility     <- data/cppb_blind_utility_summary.csv
  - tab:blindutilitytemplate <- data/cppb_blind_utility_by_template.csv

It intentionally does NOT touch illustrative or manually curated tables such as:
  - tab:example
  - tab:tradeoff

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


def _read_data_csv(name: str) -> list[dict[str, str]]:
    path = os.path.join(REPO_ROOT, "data", name)
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


# The released records label the capitalization/title/location regular-expression
# baseline "NER-only masking", which overstates it: it runs no named-entity
# recognizer. The manuscript reports it under its actual mechanism, so the rename
# is applied at render time rather than by rewriting released result records.
BASELINE_DISPLAY_NAMES = {
    "NER-only masking": "Capitalization heuristic",
}


def _display_method(name: str) -> str:
    return BASELINE_DISPLAY_NAMES.get(name.strip(), name)


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
    body = "\n".join(
        f"{_display_method(r['method'])} & {_fmt_float(r['per'])} \\\\" for r in rows
    )
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
        f"{_display_method(r['method'])} & {float(r['ac']):.2f} & {float(r['tsr']):.2f} \\\\"
        for r in rows
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
        f"{_display_method(r['pipeline'])} & {int(float(r['mean_ms']))} & {int(float(r['p95_ms']))} \\\\"
        for r in rows
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


def build_catwise_table() -> str:
    rows = sorted(_read_csv("categorywise_analysis.csv"), key=lambda row: int(row["order"]))
    body = "\n".join(
        f"{_tex_escape(row['category_label'])} & {float(row['span_f1']):.2f} & {_fmt_float(row['per_percent'])} \\\\" for row in rows
    )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xcc}\n"
        "\\toprule\n"
        "Category & Span F1 & PER (\\%) \\\\\n"
        "\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n"
        "\\end{tabularx}"
    )


def build_multimodal_table() -> str:
    rows = sorted(_read_csv("multimodal_analysis.csv"), key=lambda row: int(row["order"]))
    body_lines = []
    for row in rows:
        ocr_span_f1 = row["ocr_span_f1"]
        ocr_value = "--" if ocr_span_f1 == "--" else f"{float(ocr_span_f1):.2f}"
        body_lines.append(
            f"{_tex_escape(row['method'])} & {ocr_value} & {_fmt_float(row['multimodal_per'])} & {float(row['ac']):.2f} \\\\" 
        )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xccc}\n"
        "\\toprule\n"
        "Method & OCR Span F1 & Multimodal PER (\\%) & AC \\\\\n"
        "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        "\\end{tabularx}"
    )


def build_crossmodel_table() -> str:
    rows = sorted(_read_csv("crossmodel_portability_results.csv"), key=lambda row: int(row["order"]))
    header = (
        "Backend & Family / size / hosting & PER (\\%) & AC & TSR " + r"\\" + "\n"
    )
    body = "\n".join(
        f"{_tex_escape(row['backend_alias'])} & "
        f"{_tex_escape(row['model_family'])}, {_tex_escape(row['size_class'])}, {_tex_escape(row['hosting_mode'])} & "
        f"{_fmt_float(row['per_percent'])} & {float(row['ac']):.2f} & {float(row['tsr']):.2f} \\\\"
        for row in rows
    )
    return (
        "\\begin{tabularx}{\\linewidth}{lXccc}\n"
        + "\\toprule\n"
        + header
        + "\\midrule\n"
        f"{body}\n"
        + "\\bottomrule\n"
        + "\\end{tabularx}"
    )


def _lightclf_short_name(method: str) -> str:
    mapping = {
        "Regex-only": "Regex-only",
        "Presidio-class (NER fallback heuristic)": "Presidio-class (+NER)",
        "Hybrid rule+context de-identification": "Hybrid rule+context de-id",
        "Lightweight learned classifier (logistic regression)": "Lightweight learned classifier",
        "BodhiPromptShield (released heuristic mediator)": "BodhiPromptShield (heuristic)",
    }
    return mapping.get(method, method)


def build_lightclf_table() -> str:
    rows = _read_csv("lightweight_classifier_comparison.csv")
    header = "Method & Prec. & Rec. & Span F1 & PER (\\%) & Retention " + r"\\" + "\n"
    body = "\n".join(
        f"{_tex_escape(_lightclf_short_name(row['method']))} & "
        f"{float(row['span_precision']):.2f} & {float(row['span_recall']):.2f} & "
        f"{float(row['span_f1']):.2f} & {_fmt_float(row['per_percent'])} & "
        f"{float(row['text_retention']):.2f} \\\\"
        for row in rows
    )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xccccc}\n"
        + "\\toprule\n"
        + header
        + "\\midrule\n"
        f"{body}\n"
        + "\\bottomrule\n"
        + "\\end{tabularx}"
    )


MEASPROP_ORDER = [
    ("no_protection", "No protection"),
    ("regex_only", "Regex-only"),
    ("capitalization_heuristic", "Capitalization heuristic"),
    ("spacy_ner", "spaCy NER masking"),
    ("presidio", "Microsoft Presidio"),
    ("casper_style", "Casper-style (rules + NER, dummy values)"),
    ("llm_sanitizer", "LLM sanitizer (8B)"),
    ("heuristic_mediator", "Proposed (released heuristic detector)"),
    ("gliner_pii", "Proposed (transformer PII detector)"),
    ("learned_lr", "Proposed (learned detector)"),
]


def _ci_point(cell: str) -> str:
    """Point estimate of a "point [lo, hi]" cell."""
    return cell.split("[")[0].strip()


def _ci_full(cell: str) -> str:
    """A "point [lo, hi]" cell, dropping a degenerate interval that adds no information."""
    point, _, rest = cell.partition("[")
    point = point.strip()
    if not rest:
        return point
    lo, _, hi = rest.rstrip("]").partition(",")
    if lo.strip() == hi.strip() == point:
        return point
    return f"{point} [{rest.strip()}"


def _measprop_source(csv_name: str) -> dict[str, dict[str, str]]:
    by_key: dict[str, dict[str, str]] = {}
    for row in _read_csv(csv_name):
        key = row["method_key"].split(":")[0]
        by_key[key] = row
    return by_key


def build_measprop_table() -> str:
    """Pooled cross-boundary propagation on both real sources, with CIs.

    Reads the pooled records written by aggregate_paper_results.py, so the
    intervals cover the full document population rather than a single shard.
    """
    ai4 = _measprop_source("propagation_suite_ai4privacy_results_pooled.csv")
    pl = _measprop_source("propagation_suite_privacylens_results_pooled.csv")

    best = {
        "ai4": min(float(_ci_point(r["per_percent"])) for r in ai4.values()),
        "pl": min(float(_ci_point(r["per_percent"])) for r in pl.values()),
    }

    def _per(row: dict[str, str], tag: str) -> str:
        cell = _ci_full(row["per_percent"])
        if abs(float(_ci_point(row["per_percent"])) - best[tag]) < 1e-9:
            return "\\textbf{" + cell + "}"
        return cell

    body_lines = []
    for key, label in MEASPROP_ORDER:
        a, p = ai4[key], pl[key]
        body_lines.append(
            " & ".join(
                [
                    _tex_escape(label),
                    _ci_point(a["memory_spe"]),
                    _per(a, "ai4"),
                    f"{float(_ci_point(a['text_retention'])):.2f}",
                    _ci_point(p["memory_spe"]),
                    _per(p, "pl"),
                    f"{float(_ci_point(p['text_retention'])):.2f}",
                    _ci_point(p["semantic_residue"]),
                ]
            )
            + " \\\\"
        )

    n_ai4 = next(iter(ai4.values()))["documents"]
    n_pl = next(iter(pl.values()))["documents"]
    return (
        "\\begin{tabular}{lccccccc}\n"
        + "\\toprule\n"
        + "& \\multicolumn{3}{c}{\\emph{AI4Privacy text, reference agent "
        + f"({n_ai4} docs)}}}} & \\multicolumn{{4}}{{c}}{{\\emph{{PrivacyLens agent trajectories ({n_pl} tasks)}}}} \\\\\n"
        + "\\cmidrule(lr){2-4}\\cmidrule(lr){5-8}\n"
        + "Method & Mem.\\ SPE & PER & Ret. & Mem.\\ SPE & PER & Ret. & FRR \\\\\n"
        + "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        + "\\end{tabular}"
    )


def build_advmeas_table() -> str:
    rows = _read_csv("measured_adaptive_adversary_results.csv")
    by_attack: dict[str, dict[str, dict[str, str]]] = {}
    order: list[str] = []
    for row in rows:
        atk = row["attack_family"]
        if atk not in by_attack:
            by_attack[atk] = {}
            order.append(atk)
        key = "heur" if row["detector"].startswith("Released") else "learn"
        by_attack[atk][key] = row
    def _cell(row: dict[str, str] | None) -> str:
        if row is None:
            return "---"
        return (
            f"{_fmt_float(row['attack_success_rate'])} "
            f"[{_fmt_float(row['attack_success_lo'])}, {_fmt_float(row['attack_success_hi'])}]"
        )
    header = "Attack family & Spans & Heuristic ASR (\\%) & Learned ASR (\\%) " + r"\\" + "\n"
    body = "\n".join(
        f"{_tex_escape(atk)} & "
        f"{by_attack[atk].get('learn', by_attack[atk].get('heur'))['applicable_spans']} & "
        f"{_cell(by_attack[atk].get('heur'))} & {_cell(by_attack[atk].get('learn'))} \\\\"
        for atk in order
    )
    return (
        "\\begin{tabularx}{\\textwidth}{>{\\raggedright\\arraybackslash}Xrcc}\n"
        + "\\toprule\n"
        + header
        + "\\midrule\n"
        f"{body}\n"
        + "\\bottomrule\n"
        + "\\end{tabularx}"
    )


def build_judge_table() -> str:
    rows = _read_csv("cppb_privacy_judge_comparison.csv")
    header = "Method & PER (\\%) & AC & TSR " + r"\\" + "\n"
    body = "\n".join(
        f"{_tex_escape(_display_method(row['method']))} & {_fmt_float(row['per_percent'])} & "
        f"{float(row['ac']):.2f} & {float(row['tsr']):.2f} \\\\"
        for row in rows
    )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xccc}\n"
        + "\\toprule\n"
        + header
        + "\\midrule\n"
        f"{body}\n"
        + "\\bottomrule\n"
        + "\\end{tabularx}"
    )


def build_mapcompromise_table() -> str:
    rows = _read_csv("secure_mapping_compromise_results.csv")
    header = "Adversary capability & Target (\\%) & Cross-session (\\%) & Blast radius " + r"\\" + "\n"
    body = "\n".join(
        f"{_tex_escape(row['tier'])} & {_fmt_float(row['target_recovery_percent'])} & "
        f"{_fmt_float(row['cross_session_recovery_percent'])} & {_tex_escape(row['blast_radius'])} \\\\"
        for row in rows
    )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xcc>{\\raggedright\\arraybackslash}p{1.45cm}}\n"
        + "\\toprule\n"
        + header
        + "\\midrule\n"
        f"{body}\n"
        + "\\bottomrule\n"
        + "\\end{tabularx}"
    )


def build_crossdom_table() -> str:
    rows = _read_csv("cross_domain_detector_results.csv")
    header = "Train $\\rightarrow$ Test & Setting & Rec. & F1 & PER (\\%) " + r"\\" + "\n"
    body = "\n".join(
        f"{_tex_escape(row['train_domain'])} $\\rightarrow$ {_tex_escape(row['test_domain'])} & "
        f"{_tex_escape(row['setting'])} & {float(row['recall']):.2f} & {float(row['span_f1']):.2f} & "
        f"{_fmt_float(row['per_percent'])} \\\\"
        for row in rows
    )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}X>{\\raggedright\\arraybackslash}p{1.5cm}ccc}\n"
        + "\\toprule\n"
        + header
        + "\\midrule\n"
        f"{body}\n"
        + "\\bottomrule\n"
        + "\\end{tabularx}"
    )


def build_mapadv_table() -> str:
    rows = _read_csv("secure_mapping_adversary_results.csv")
    body = "\n".join(
        f"{_tex_escape(row['scenario'])} & {_tex_escape(row['interpretation'])} \\\\"
        for row in rows
    )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}p{2.05cm}>{\\raggedright\\arraybackslash}X}\n"
        + "\\toprule\n"
        + "Adversary scenario & Measured outcome \\\\\n"
        + "\\midrule\n"
        f"{body}\n"
        + "\\bottomrule\n"
        + "\\end{tabularx}"
    )


def build_hardcase_table() -> str:
    rows = sorted(_read_csv("hardcase_analysis.csv"), key=lambda row: int(row["order"]))
    header = "Subset & Span F1 & PER (\\%) & AC " + r"\\" + "\n"
    body = "\n".join(
        f"{_tex_escape(row['subset'])} & {float(row['span_f1']):.2f} & {_fmt_float(row['per_percent'])} & {float(row['ac']):.2f} \\\\" for row in rows
    )
    return (
        "\\begin{tabular}{lccc}\n"
        + "\\toprule\n"
        + header
        + "\\midrule\n"
        f"{body}\n"
        + "\\bottomrule\n"
        + "\\end{tabular}"
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
    display_names = {
        "Enterprise staged redaction": "Enterprise redaction",
        "Generic de-identification": "Generic de-id",
        "Proposed (semantic abstraction)": "Proposed (semantic)",
        "Proposed (utility-constrained)": "Proposed (balanced)",
    }
    body_lines = []
    for row in rows:
        body_lines.append(
            " & ".join(
                [
                    display_names.get(row["setting"], row["setting"]),
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
    display_names = {
        "Presidio (regex-only baseline)": "Presidio (regex)",
        "Presidio (with NER fallback)": "Presidio (+NER)",
        "BodhiPromptShield (proposed)": "BodhiPromptShield",
    }
    body_lines = []
    for row in rows:
        body_lines.append(
            " & ".join(
                [
                    _tex_escape(display_names.get(row["method"], row["method"])),
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


OCR_SLICES = (("CORD", "cord"), ("FUNSD", "funsd"), ("SROIE", "sroie"))

OCR_METHOD_LABELS = {
    "Raw OCR text prompt": "No protection",
    "OCR + regex masking": "Regex-only",
    "OCR + generic de-identification": "Generic de-identification",
    "OCR + Presidio receipt de-identification": "Presidio",
    "OCR + Presidio form de-identification": "Presidio",
    "OCR + spaCy receipt de-identification": "spaCy NER",
    "OCR + spaCy form de-identification": "spaCy NER",
    "Proposed multimodal mediation": "Proposed mediation",
}

OCR_METHOD_ORDER = [
    "No protection",
    "Regex-only",
    "Generic de-identification",
    "Presidio",
    "spaCy NER",
    "Proposed mediation",
]


def build_ocrslice_table() -> str:
    """Public OCR-mediated transfer slices, one column group per benchmark."""
    per_slice: dict[str, dict[str, dict[str, str]]] = {}
    for label, prefix in OCR_SLICES:
        by_method: dict[str, dict[str, str]] = {}
        for row in _read_csv(f"{prefix}_transfer_results.csv"):
            by_method[OCR_METHOD_LABELS[row["method"]]] = row
        per_slice[label] = by_method

    body_lines = []
    for method in OCR_METHOD_ORDER:
        cells = [_tex_escape(method)]
        for label, _ in OCR_SLICES:
            row = per_slice[label][method]
            cells += [
                f"{float(row['ocr_span_f1']):.2f}",
                _fmt_float(row["multimodal_per"]),
                f"{float(row['text_retention']):.2f}",
            ]
        body_lines.append(" & ".join(cells) + " \\\\")

    group = " & ".join(
        f"\\multicolumn{{3}}{{c}}{{{label} ({per_slice[label]['No protection']['document_count']} docs, "
        f"{per_slice[label]['No protection']['mention_count']} spans)}}"
        for label, _ in OCR_SLICES
    )
    sub = " & ".join(["F1 & PER & Ret."] * len(OCR_SLICES))
    return (
        "\\begin{tabularx}{\\textwidth}{>{\\raggedright\\arraybackslash}X"
        + "ccc" * len(OCR_SLICES)
        + "}\n"
        + "\\toprule\n"
        + f"& {group} \\\\\n"
        + "\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\\cmidrule(lr){8-10}\n"
        + f"Method & {sub} \\\\\n"
        + "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        + "\\end{tabularx}"
    )


def build_tab_transfer_table() -> str:
    rows = _read_csv("tab_transfer_results.csv")
    display_names = {
        "Presidio-class (regex-focused heuristic)": "Presidio-class (regex)",
        "Presidio-class (NER fallback heuristic)": "Presidio-class (+NER)",
        "Hybrid rule+context de-identification": "Hybrid de-id",
        "BodhiPromptShield (released heuristic mediator)": "BodhiPromptShield",
    }
    header = "Method & Precision & Recall & Span F1 & PER (\\%) & Text retention " + r"\\" + "\n"
    body_lines = []
    for row in rows:
        body_lines.append(
            " & ".join(
                [
                    _tex_escape(display_names.get(row["method"], row["method"])),
                    f"{float(row['span_precision']):.2f}",
                    f"{float(row['span_recall']):.2f}",
                    f"{float(row['span_f1']):.2f}",
                    _fmt_float(row["per_percent"]),
                    f"{float(row['text_retention']):.2f}",
                ]
            )
            + " \\\\"
        )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xccccc}\n"
        + "\\toprule\n"
        + header
        + "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        + "\\end{tabularx}"
    )


def build_blind_utility_table() -> str:
    rows = _read_data_csv("cppb_blind_utility_summary.csv")
    display_names = {
        "openai_luna": "OpenAI Luna",
        "claude_sonnet5": "Claude Sonnet 5",
    }
    body_lines = []
    for row in rows:
        response = (
            f"{row['safe_refusal_count']}/{row['generic_template_or_code_count']}/"
            f"{row['fully_useful_count']}/{row['partial_or_incomplete_count']}"
        )
        faith = f"{row['faithfulness_0']}/{row['faithfulness_1']}/{row['faithfulness_2']}"
        body_lines.append(
            " & ".join(
                [
                    _tex_escape(display_names.get(row["rater"], row["rater"])),
                    row["n"],
                    row["task_success_rate_pct"],
                    faith,
                    row["required_fields_rate_pct"],
                    row["fully_useful_count"],
                    response,
                ]
            )
            + " \\\\"
        )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}XrcccrX}\n"
        "\\toprule\n"
        "Rater & $n$ & TSR (\\%) & \\makecell{Faith.\\\\0/1/2} & Fields (\\%) & Useful & \\makecell{Refusal/Gen./\\\\Useful/Other} \\\\\n"
        "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        + "\\end{tabularx}"
    )


def build_blind_utility_template_table() -> str:
    rows = _read_data_csv("cppb_blind_utility_by_template.csv")
    by_template: dict[str, dict[str, str]] = {}
    for row in rows:
        by_template.setdefault(row["template_id"], {})[row["rater"]] = row
    body_lines = []
    for template_id in sorted(by_template):
        luna = by_template[template_id]["openai_luna"]
        claude = by_template[template_id]["claude_sonnet5"]
        body_lines.append(
            " & ".join(
                [
                    _tex_escape(template_id),
                    luna["n"],
                    luna["task_success_rate_pct"],
                    claude["task_success_rate_pct"],
                    luna["faithfulness_2_rate_pct"],
                    claude["faithfulness_2_rate_pct"],
                    luna["required_fields_rate_pct"],
                    claude["required_fields_rate_pct"],
                ]
            )
            + " \\\\"
        )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xrrrrrrr}\n"
        "\\toprule\n"
        "\\makecell[l]{Template\\\\ID} & $n$ & \\makecell{Luna\\\\TSR} & \\makecell{Claude\\\\TSR} & \\makecell{Luna\\\\F2} & \\makecell{Claude\\\\F2} & \\makecell{Luna\\\\fields} & \\makecell{Claude\\\\fields} \\\\\n"
        "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        + "\\end{tabularx}"
    )


TABLE_BUILDERS: dict[str, Callable[[], str]] = {
    "tab:cppb_card": build_cppb_accounting_table,
    "tab:per": build_per_table,
    "tab:utility": build_utility_table,
    "tab:pi_sensitivity": build_pi_table,
    "tab:propagation": build_propagation_table,
    "tab:latency": build_latency_table,
    "tab:catwise": build_catwise_table,
    "tab:multimodal": build_multimodal_table,
    "tab:crossmodel": build_crossmodel_table,
    "tab:lightclf": build_lightclf_table,
    "tab:judge": build_judge_table,
    "tab:measprop": build_measprop_table,
    "tab:advmeas": build_advmeas_table,
    "tab:mapcompromise": build_mapcompromise_table,
    "tab:crossdom": build_crossdom_table,
    "tab:mapadv": build_mapadv_table,
    "tab:hardcase": build_hardcase_table,
    "tab:restore": build_restore_table,
    "tab:ablation": build_ablation_table,
    "tab:multiseed": build_multiseed_table,
    "tab:lto": build_lto_table,
    "tab:baseline": build_baseline_table,
    "tab:tabtransfer": build_tab_transfer_table,
    "tab:ocrslice": build_ocrslice_table,
    "tab:blindutility": build_blind_utility_table,
    "tab:blindutilitytemplate": build_blind_utility_template_table,
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
