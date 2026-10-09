"""
Fill code-backed empirical tables in paper/main.tex and paper/appendix.tex from CSV files under src/experiments.

This script only updates tables that are directly backed by repository CSVs:
  - tab:propagation      <- agent_pipeline_metrics.csv
  - tab:latency          <- latency_overhead_reconstructed.csv
    - tab:catwise          <- categorywise_analysis.csv
    - tab:multimodal       <- multimodal_analysis.csv
    - tab:crossmodel       <- crossmodel_portability_results.csv
    - tab:judge            <- cppb_privacy_judge_comparison.csv
    - tab:measprop         <- propagation_suite_{ai4privacy,privacylens}_results_pooled.csv
    - tab:advmeas          <- measured_adaptive_adversary_span_results.csv (per-span ASR)
    - tab:attrrecovery     <- privacylens_attribute_recovery_summary_*.csv
    - tab:attrcap          <- privacylens_attribute_recovery_summary_*.csv (all attackers)
    - tab:mapadv           <- secure_mapping_adversary_results.csv
    - tab:hardcase         <- hardcase_analysis.csv
  - tab:restore          <- restoration_boundary_analysis.csv
  - tab:ablation         <- sanitization_mode_ablation.csv
    - tab:baseline         <- external_baseline_comparison.csv
  - tab:tabtransfer      <- tab_transfer_results.csv
  - tab:ocrslice         <- {cord,funsd,sroie}_transfer_results.csv
  - tab:blindutility     <- data/cppb_blind_utility_summary.csv
  - tab:blindutilitytemplate <- data/cppb_blind_utility_by_template.csv
  - tab:downstream       <- privacylens_downstream_summary_qwen3_32b-q4km-hf_pooled.csv
                            (RCE shown only where the per-case shards record a mapping)
  - tab:inject           <- agentdojo_injection_summary_pooled_qwen3_32b-q4km-hf_fixed.csv
  - tab:portability      <- privacylens_downstream_summary_{qwen3_32b,llama3.3_70b}-q4km-hf_pooled.csv
                            + downstream_paired_tests_llama3.3_70b-q4km-hf.csv
  - tab:pljudge          <- privacylens_judge_agreement.csv
  - tab:contextattack    <- privacylens_context_attack_summary_qwen3_32b-q4km-hf.csv
  - tab:propints         <- propagation_suite_{ai4privacy,privacylens}_results_pooled.csv
  - tab:judgecap         <- semantic_inferability_{agreement,agreement_round3,capacity_agreement_*}_vgpu3090.csv
                            + semantic_inferability_llm_rater_agreement_claude_20261007.csv
  - tab:canon            <- canonicalization_hardening_asr_span_results.csv (per-span ASR)

The CPPB card and result tables (PER, utility, policy sensitivity, multi-seed
and leave-template-out) and the lightweight-classifier comparison were removed
from the manuscript, so their builders are gone. A registered label that is absent
from the target file is skipped with a printed note rather than treated as an
error.

It intentionally does NOT touch illustrative or manually curated tables such as:
  - tab:example
  - tab:tradeoff

Usage:
  python src/experiments/fill_paper_tables.py
  python src/experiments/fill_paper_tables.py --paper paper/main.tex --dry-run
  python src/experiments/fill_paper_tables.py --paper paper/appendix.tex
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


# The latency record's pipeline names, as the manuscript names them: the
# generic pipeline is the heuristic detector's spans behind one generic token,
# the staged pipeline is the Presidio recognizer with typed placeholders, and
# the balanced pipeline is the learned detector at the balanced threshold.
LATENCY_DISPLAY_NAMES = {
    "Raw prompting (no middleware)": "No protection",
    "Regex-only redaction": "Regex-only",
    "Capitalization heuristic": "Capitalization heuristic",
    "Generic de-identification": "Heuristic detector, generic token",
    "Enterprise staged redaction": "Presidio",
    "Proposed (policy-aware balanced)": "Proposed (learned detector)",
}


def build_latency_table() -> str:
    rows = _read_csv("latency_overhead_reconstructed.csv")
    body = "\n".join(
        f"{LATENCY_DISPLAY_NAMES.get(r['pipeline'], r['pipeline'])} & {float(r['mean_ms']):.1f} & {float(r['p95_ms']):.1f} \\\\"
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


MEASPROP_ORDER = [
    ("no_protection", "No protection"),
    ("regex_only", "Regex-only"),
    ("capitalization_heuristic", "Capitalization heuristic"),
    ("spacy_ner", "spaCy NER masking"),
    ("presidio", "Presidio"),
    # The exposure suites mask every method with one marker, so this row is the
    # Casper-style detector alone; dummy values appear only downstream.
    ("casper_style", "Casper-style detector (rules + NER)"),
    ("llm_sanitizer", "LLM sanitizer (8B)"),
    ("heuristic_mediator", "Proposed (heuristic detector)"),
    ("gliner_pii", "Proposed (transformer detector)"),
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
    rows = _read_csv("measured_adaptive_adversary_span_results.csv")
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


# The condition keys the attack writes are the mediation specs it was run with.
# The manuscript names the conditions the way the rest of its tables do.
_RECOVERY_CONDITION_LABELS = {
    "no_protection": "No protection",
    "placeholder:presidio": "Typed placeholder (Presidio)",
    "placeholder:learned_lr": "Typed placeholder (learned)",
    "casper_style": "Casper-style (dummy values)",
}


def build_attrrecovery_table() -> str:
    """Value recovery beside literal survival, so the gap between them is visible.

    Recovery is what an adversary can put back; survival is what the release
    still literally contained. Reporting one without the other invites reading
    inference into a number that is just text that was never removed.
    """
    rows = _read_csv("privacylens_attribute_recovery_summary_qwen3_32b-q4km-hf.csv")
    chance = rows[0]["chance_percent"] if rows else "25.0"
    header = ("Condition & \\makecell{Recov-\\\\ered (\\%)} & \\makecell{Value\\\\present (\\%)} & "
              "\\makecell{Recovered\\\\when absent (\\%)} " + r"\\" + "\n")
    # The value-present column is the one the text reads first: the condition
    # that leaves the value verbatim least often is set in bold.
    least = min(float(_ci_point(r["value_survives_release_percent"])) for r in rows)

    def _present(row: dict[str, str]) -> str:
        cell = _tex_escape(row["value_survives_release_percent"])
        return "\\textbf{" + cell + "}" if abs(float(_ci_point(cell)) - least) < 1e-9 else cell

    body = "\n".join(
        f"{_tex_escape(_RECOVERY_CONDITION_LABELS.get(row['condition'], row['condition']))} & "
        f"{_tex_escape(row['recovery_percent'])} & "
        f"{_present(row)} & "
        f"{_tex_escape(row['recovery_when_value_absent_percent'])} \\\\"
        for row in rows
    )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xccc}\n"
        + "\\toprule\n"
        + header
        + "\\midrule\n"
        f"{body}\n"
        + "\\midrule\n"
        + f"Chance & {_fmt_float(chance)} & --- & {_fmt_float(chance)} \\\\\n"
        + "\\bottomrule\n"
        + "\\end{tabularx}"
    )


# The attacker-capacity sweep, in the order a reader should see it. Each entry
# is (record tag, label); a model whose record is not present is skipped rather
# than shown as a gap, so the table renders whatever has finished.
_ATTACKER_CAPACITY = (
    ("qwen3_8b-q4km-hf", "Qwen3 8B"),
    ("qwen3_32b-q4km-hf", "Qwen3 32B (reported)"),
    ("llama3.3_70b-q4km-hf", "Llama 3.3 70B"),
)


def build_attrcap_table() -> str:
    """Recovery against attacker capacity, on the conditions that carry the claim.

    The paper's own judge-capacity result is why this exists: capacity moved
    judge agreement nearly fivefold, so a single-attacker attack number invites
    the same objection. The column shown is recovery on the questions whose
    value the detector removed, because that is the one the finding rests on.
    """
    wanted = ("no_protection", "placeholder:presidio", "casper_style", "placeholder:learned_lr")
    short = {"no_protection": "None", "placeholder:presidio": "Presidio",
             "casper_style": "Casper", "placeholder:learned_lr": "Learned"}
    grid = []
    for tag, label in _ATTACKER_CAPACITY:
        try:
            rows = _read_csv(f"privacylens_attribute_recovery_summary_{tag}.csv")
        except FileNotFoundError:
            continue
        by_cond = {r["condition"]: r for r in rows}
        cells = []
        for cond in wanted:
            row = by_cond.get(cond)
            cells.append(_tex_escape(row["recovery_when_value_absent_percent"]) if row else "---")
        grid.append((label, cells))
    if not grid:
        raise FileNotFoundError("no attacker-capacity summaries found")
    # The lowest cell is set in bold: it is the one capacity moved, and the
    # text reads the rest of the grid against it.
    least = min(float(_ci_point(c)) for _, cells in grid for c in cells if c != "---")
    body_rows = [
        f"{_tex_escape(label)} & "
        + " & ".join(
            "\\textbf{" + c + "}" if c != "---" and abs(float(_ci_point(c)) - least) < 1e-9 else c
            for c in cells
        )
        + " \\\\"
        for label, cells in grid
    ]
    header = ("Attacker & " + " & ".join(short[c] for c in wanted) + " " + r"\\" + "\n")
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xcccc}\n"
        + "\\toprule\n"
        + "& \\multicolumn{4}{c}{Recovered when value absent (\\%)} \\\\\n"
        + "\\cmidrule(lr){2-5}\n"
        + header
        + "\\midrule\n"
        + "\n".join(body_rows) + "\n"
        + "\\midrule\n"
        + "Chance & 25.0 & 25.0 & 25.0 & 25.0 \\\\\n"
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
    "OCR + spaCy receipt de-identification": "spaCy NER masking",
    "OCR + spaCy form de-identification": "spaCy NER masking",
    "Proposed multimodal mediation": "Proposed mediation",
}

OCR_METHOD_ORDER = [
    "No protection",
    "Regex-only",
    "Generic de-identification",
    "Presidio",
    "spaCy NER masking",
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


# ---------------------------------------------------------------------------
# PrivacyLens downstream protocol, its portability and judge checks, the
# forced-choice context attack, and AgentDojo prompt injection.
# ---------------------------------------------------------------------------

# The agent each downstream record was produced with, by the role the paper
# gives it: the reported agent and the second family it is checked against.
_DOWNSTREAM_AGENT = "qwen3_32b-q4km-hf"
_DOWNSTREAM_SECOND_AGENT = "llama3.3_70b-q4km-hf"

# The downstream conditions in the order the manuscript reads them. Keys are
# the mediation specs the suite was run with; a key ending in ":" names a
# helper-model condition and is matched by prefix, so the two 8B conditions
# still render if the helper tag changes.
_DOWNSTREAM_ORDER = (
    ("no_protection", "No protection"),
    ("placeholder:presidio", "Typed placeholder (Presidio)"),
    ("casper_style", "Casper-style"),
    # The same release with Casper's dummy->original map applied to the action.
    ("casper_restored", "Casper-style, restored"),
    ("placeholder:learned_lr", "Typed placeholder (learned)"),
    ("placeholder:gliner_pii", "Typed placeholder (transformer)"),
    ("llm_sanitizer:", "LLM sanitizer (8B)"),
    ("abstraction:", "Semantic abstraction (8B)"),
    ("symbolic_late:gliner_pii", "Symbolic mapping, late restoration"),
    # The true early arm; the trajectory-only arm it replaces is retired.
    ("symbolic_fullearly:gliner_pii", "Symbolic mapping, early restoration"),
)


def _downstream_summary(agent: str) -> dict[str, dict[str, str]]:
    return {r["condition"]: r for r in _read_csv(f"privacylens_downstream_summary_{agent}_pooled.csv")}


def _downstream_row(by_cond: dict[str, dict[str, str]], key: str) -> dict[str, str]:
    if key in by_cond:
        return by_cond[key]
    if key.endswith(":"):
        matches = [c for c in by_cond if c.startswith(key)]
        if len(matches) == 1:
            return by_cond[matches[0]]
    raise KeyError(f"downstream condition not found: {key}")


def _downstream_protected_values(agent: str) -> dict[str, int]:
    """Per condition, how many values the mediation mapping held across all cases.

    This is the denominator of the released-context exposure rate. It is zero
    wherever no mapping exists, and the pooled summary prints 0.0 there, which
    is not a measurement; the table shows a dash instead. The count lives in
    the per-case rows, read exactly as the pooling script reads them
    (superseding records and retired conditions applied).
    """
    from aggregate_paper_results import read_downstream_rows

    rows = read_downstream_rows(agent)
    if not rows:
        raise FileNotFoundError(f"no downstream shards found for {agent}")
    totals: dict[str, int] = {}
    for row in rows:
        totals[row["condition"]] = totals.get(row["condition"], 0) + int(float(row["protected_values"] or 0))
    return totals


def build_downstream_table() -> str:
    """Task-native privacy and utility on the reported agent, with CIs.

    Cells are the pooled record's own "point [lo, hi]" strings. The RCE
    column is defined only where a mapping exists; the lowest defined rate
    is set in bold, since that column is the restoration-timing result.
    """
    by_cond = _downstream_summary(_DOWNSTREAM_AGENT)
    denominators = _downstream_protected_values(_DOWNSTREAM_AGENT)
    rows = [(label, _downstream_row(by_cond, key)) for key, label in _DOWNSTREAM_ORDER]
    defined = [r for _, r in rows if denominators.get(r["condition"], 0) > 0]
    best = min(float(_ci_point(r["boundary_leak_percent"])) for r in defined) if defined else None

    body_lines = []
    for label, row in rows:
        if row in defined:
            rce = row["boundary_leak_percent"]
            if abs(float(_ci_point(rce)) - best) < 1e-9:
                rce = "\\textbf{" + rce + "}"
        else:
            rce = "---"
        body_lines.append(
            " & ".join(
                [
                    _tex_escape(label),
                    row["leak_rate_percent"],
                    row["secret_leak_percent"],
                    row["helpfulness_mean"],
                    row["exact_id_exposure_percent"],
                    rce,
                ]
            )
            + " \\\\"
        )
    return (
        "\\begin{tabular}{lccccc}\n"
        + "\\toprule\n"
        + "Condition & Leak (\\%) & Secret (\\%) & Help.\\ (0--3) & ID exp.\\ (\\%) & RCE (\\%) \\\\\n"
        + "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        + "\\end{tabular}"
    )


def _holm_p(cell: str) -> str:
    p = float(cell)
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def build_portability_table() -> str:
    """The downstream conditions under both agents, point estimates only.

    The paired column is the Holm-corrected McNemar test on the second agent,
    read from its paired-test record; the unprotected reference row has no
    test against itself.
    """
    first = _downstream_summary(_DOWNSTREAM_AGENT)
    second = _downstream_summary(_DOWNSTREAM_SECOND_AGENT)
    paired = {r["condition"]: r for r in _read_csv(f"downstream_paired_tests_{_DOWNSTREAM_SECOND_AGENT}.csv")}

    body_lines = []
    for key, label in _DOWNSTREAM_ORDER:
        a, b = _downstream_row(first, key), _downstream_row(second, key)
        test = paired.get(b["condition"])
        body_lines.append(
            " & ".join(
                [
                    _tex_escape(label),
                    _ci_point(a["exact_id_exposure_percent"]),
                    _ci_point(b["exact_id_exposure_percent"]),
                    _ci_point(a["leak_rate_percent"]),
                    _ci_point(b["leak_rate_percent"]),
                    _ci_point(a["helpfulness_mean"]),
                    _ci_point(b["helpfulness_mean"]),
                    _holm_p(test["mcnemar_p_holm"]) if test else "\\textemdash",
                ]
            )
            + " \\\\"
        )
    return (
        "\\begin{tabular}{@{}lccccccc@{}}\n"
        + "\\toprule\n"
        + "& \\multicolumn{2}{c}{ID exp.\\ (\\%)} & \\multicolumn{2}{c}{Leak (\\%)} & \\multicolumn{2}{c}{Help.} & \\\\\n"
        + "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\n"
        + "Condition & 32B & 70B & 32B & 70B & 32B & 70B & Holm $p$ \\\\\n"
        + "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        + "\\end{tabular}"
    )


# The agreement record keeps one row per comparison; the readers' row is the
# ceiling the judge is read against and is set apart below a rule.
_PLJUDGE_ROWS = (
    ("judge_vs_human_overall", "Judge vs.\\ annotator 4"),
    ("judge_vs_annotator2", "Judge vs.\\ annotator 5"),
)
_PLJUDGE_CEILING = ("annotator1_vs_annotator2", "Annotator 4 vs.\\ annotator 5")


def build_pljudge_table() -> str:
    by_comparison = {r["comparison"]: r for r in _read_csv("privacylens_judge_agreement.csv")}

    def _cells(key: str, label: str, bold: bool) -> str:
        row = by_comparison[key]
        cells = [label, f"{float(row['cohens_kappa']):.3f}", f"{float(row['raw_agreement']) * 100:.1f}\\%"]
        if bold:
            cells = ["\\textbf{" + c + "}" for c in cells]
        return " & ".join(cells) + " \\\\"

    body = "\n".join(_cells(key, label, False) for key, label in _PLJUDGE_ROWS)
    ceiling = _cells(*_PLJUDGE_CEILING, True)
    return (
        "\\begin{tabular}{lcc}\n"
        + "\\toprule\n"
        + "Comparison & Cohen's $\\kappa$ & Raw agreement \\\\\n"
        + "\\midrule\n"
        + body + "\n"
        + "\\midrule\n"
        + ceiling + "\n"
        + "\\bottomrule\n"
        + "\\end{tabular}"
    )


def _thousands(value: str) -> str:
    return f"{int(float(value)):,}".replace(",", "{,}")


# The forced-choice attack conditions in the order the manuscript reads them.
_CONTEXT_ATTACK_ORDER = ("no_protection", "placeholder:presidio", "placeholder:learned_lr", "casper_style")


def build_contextattack_table() -> str:
    """Forced-choice case identification on the released surface.

    The lowest accuracy is set in bold: on this axis the condition that most
    misleads the attacker is the one the text singles out.
    """
    by_cond = {r["condition"]: r for r in _read_csv(f"privacylens_context_attack_summary_{_DOWNSTREAM_AGENT}.csv")}
    rows = [by_cond[c] for c in _CONTEXT_ATTACK_ORDER]
    best = min(float(_ci_point(r["attack_accuracy_percent"])) for r in rows)
    chance = rows[0]["chance_percent"]

    body_lines = []
    for row in rows:
        accuracy = row["attack_accuracy_percent"]
        if abs(float(_ci_point(accuracy)) - best) < 1e-9:
            accuracy = "\\textbf{" + accuracy + "}"
        body_lines.append(
            f"{_tex_escape(_RECOVERY_CONDITION_LABELS.get(row['condition'], row['condition']))} & "
            f"{accuracy} & {_thousands(row['questions'])} \\\\"
        )
    return (
        "\\begin{tabular}{lcc}\n"
        + "\\toprule\n"
        + "Condition & Attack accuracy (\\%) & Questions \\\\\n"
        + "\\midrule\n"
        + "\n".join(body_lines) + "\n"
        + "\\midrule\n"
        + f"Chance & {_fmt_float(chance)} & --- \\\\\n"
        + "\\bottomrule\n"
        + "\\end{tabular}"
    )


# The AgentDojo arms in the order the manuscript reads them, by the restoration
# policy each ran under.
_INJECT_ARMS = (
    ("unprotected", "No protection"),
    ("unrestricted", "Unrestricted restoration"),
    ("user_directed", "User-directed restoration"),
)


def _signed_ci(cell: str) -> str:
    """A signed "point [lo, hi]" cell with each number in math mode, so its sign typesets as one."""
    point, _, rest = cell.partition("[")
    lo, _, hi = rest.rstrip("]").partition(",")
    return f"${point.strip()}$ [${lo.strip()}$, ${hi.strip()}$]"


def build_inject_table() -> str:
    # The rerun with the repaired harness (temperature and seed sent, restoration on an
    # executed copy, attacker-call payloads classified) supersedes the earlier pass.
    by_arm = {r["arm"]: r for r in _read_csv(f"agentdojo_injection_summary_pooled_{_DOWNSTREAM_AGENT}_fixed.csv")}
    body_lines = []
    for arm, label in _INJECT_ARMS:
        row = by_arm[arm]
        delta = row["paired_asr_delta_vs_unprotected"].strip()
        body_lines.append(
            " & ".join(
                [
                    _tex_escape(label),
                    row["attack_success_percent"],
                    row["utility_percent"],
                    _signed_ci(delta) if delta else "---",
                    f"{row['raw_value_exfil_pairs']}/{row['pairs']}",
                ]
            )
            + " \\\\"
        )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xcccc}\n"
        + "\\toprule\n"
        + "Condition & ASR (\\%) & Util.\\ (\\%) & Paired $\\Delta$ ASR (pts) & Raw \\\\\n"
        + "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        + "\\end{tabularx}"
    )


# ---------------------------------------------------------------------------
# Propagation with intervals on every column, judge capacity against the human
# reference, and input canonicalization against surface-form evasion.
# ---------------------------------------------------------------------------

def build_propints_table() -> str:
    """Every propagation column with its interval, on both real sources.

    Degenerate intervals are kept here, unlike tab:measprop, because the point
    of this table is that every column carries one.  Rows carry the same method
    names as tab:measprop (they fit the full width at this size).
    """
    ai4 = _measprop_source("propagation_suite_ai4privacy_results_pooled.csv")
    pl = _measprop_source("propagation_suite_privacylens_results_pooled.csv")
    body_lines = []
    for key, label in MEASPROP_ORDER:
        a, p = ai4[key], pl[key]
        body_lines.append(
            " & ".join(
                [
                    _tex_escape(label),
                    a["retrieval_spe"],
                    a["memory_spe"],
                    a["tool_spe"],
                    a["per_percent"],
                    a["text_retention"],
                    p["memory_spe"],
                    p["per_percent"],
                    p["text_retention"],
                    p["semantic_residue"],
                ]
            )
            + " \\\\"
        )
    n_ai4 = next(iter(ai4.values()))["documents"]
    n_pl = next(iter(pl.values()))["documents"]
    return (
        "\\begin{tabular}{@{}lccccccccc@{}}\n"
        + "\\toprule\n"
        + f"& \\multicolumn{{5}}{{c}}{{\\emph{{AI4Privacy text, reference agent ({n_ai4} docs)}}}} "
        + f"& \\multicolumn{{4}}{{c}}{{\\emph{{PrivacyLens agent trajectories ({n_pl} tasks)}}}} \\\\\n"
        + "\\cmidrule(lr){2-6}\\cmidrule(lr){7-10}\n"
        + "& \\multicolumn{3}{c}{SPE} & & & SPE & & & \\\\\n"
        + "\\cmidrule(lr){2-4}\\cmidrule(lr){7-7}\n"
        + "Method & Retrieval & Memory & Tool & PER & Ret. & Memory & PER & Ret. & FRR \\\\\n"
        + "\\midrule\n"
        + "\n".join(body_lines)
        + "\n\\bottomrule\n"
        + "\\end{tabular}"
    )


def _manifest(name: str) -> dict[str, str]:
    return {r["field"]: r["value"] for r in _read_csv(name)}


def _pct(numerator: int, denominator: int) -> str:
    return f"{100.0 * numerator / denominator:.1f}"


# The judges re-run on the identical prompt and released text, by record tag.
_JUDGE_CAPACITY = ("qwen3_8b-q4km-hf", "qwen3_32b-q4km-hf", "llama3.3_70b-q4km-hf")


def build_judgecap_table() -> str:
    """Inferability-judge agreement with the two independent readers, by capacity.

    Each judge row is kappa against annotator 1 and against annotator 3 (the
    blank-sheet reader) on the 102-item subset, and how often the judge calls a
    fact inferable. The reported 27B judge comes from the first agreement
    record and the round-3 record; the re-run judges from their capacity
    records; the frontier rater from its validation record, whose yes-rate is
    read off its contingency cells. The highest judge kappa in each column and
    the readers' own agreement, the ceiling, are set in bold.
    """
    def _model(tag: str) -> str:
        return tag.removesuffix("-q4km-hf")

    rows: list[tuple[str, str, float, float, str]] = []

    def _add(label: str, params: str, k1: str, k3: str, yes: str) -> None:
        rows.append((label, params, float(k1), float(k3), yes))

    reported = _manifest("semantic_inferability_runtime_manifest_vgpu3090.csv")
    first = {r["comparison"]: r for r in _read_csv("semantic_inferability_agreement_vgpu3090.csv")}
    round3 = {r["comparison"]: r for r in _read_csv("semantic_inferability_agreement_round3_vgpu3090.csv")}
    j1 = first["judge_vs_human"]
    reported_yes = int(j1["human_no_pred_yes"]) + int(j1["human_yes_pred_yes"])
    capacity: dict[str, tuple] = {}
    for tag in _JUDGE_CAPACITY:
        by_ref = {r["reference"]: r for r in _read_csv(f"semantic_inferability_capacity_agreement_{tag}_vgpu3090.csv")}
        size = _manifest(f"semantic_inferability_capacity_manifest_{tag}_vgpu3090.csv")["judge_parameter_size"]
        a1, a3 = by_ref["annotator1"], by_ref["annotator3"]
        capacity[tag] = (size, a1["cohens_kappa"], a3["cohens_kappa"], f"{float(a1['judge_yes_rate']) * 100:.1f}")

    # Ordered by parameter count, with the reported judge in its place.
    _add(f"\\texttt{{{_model(_JUDGE_CAPACITY[0]).replace('_', ':')}}}", *capacity[_JUDGE_CAPACITY[0]])
    _add(f"\\texttt{{{reported['judge_model']}}} (reported)", reported["judge_parameter_size"],
         j1["cohens_kappa"], round3["judge_vs_annotator3"]["cohens_kappa"], _pct(reported_yes, int(j1["n"])))
    for tag in _JUDGE_CAPACITY[1:]:
        _add(f"\\texttt{{{_model(tag).replace('_', ':')}}}", *capacity[tag])

    rater = {r["comparison"]: r for r in _read_csv("semantic_inferability_llm_rater_agreement_claude_20261007.csv")}
    r1 = rater["rater_vs_annotator1"]
    rater_yes = int(r1["other_no_rater_yes"]) + int(r1["other_yes_rater_yes"])
    _add("Frontier model, agent harness", "---", r1["cohens_kappa"],
         rater["rater_vs_annotator3_blank_sheet"]["cohens_kappa"], _pct(rater_yes, int(r1["n"])))

    best1 = max(r[2] for r in rows)
    best3 = max(r[3] for r in rows)

    def _k(value: float, best: float) -> str:
        cell = f"{value:.3f}"
        return "\\textbf{" + cell + "}" if abs(value - best) < 1e-9 else cell

    body = "\n".join(
        f"{label} & {params} & {_k(k1, best1)} & {_k(k3, best3)} & {yes}\\% \\\\"
        for label, params, k1, k3, yes in rows
    )
    readers = round3["annotator1_vs_annotator3_independent"]
    n = int(readers["n"])
    a1_yes = _pct(int(readers["cell_yes_no"]) + int(readers["cell_yes_yes"]), n)
    a3_yes = _pct(int(readers["cell_no_yes"]) + int(readers["cell_yes_yes"]), n)
    return (
        "\\begin{tabularx}{\\columnwidth}{lcccc}\n"
        + "\\toprule\n"
        + "Judge & Params & $\\kappa$ vs.\\ Ann.~1 & $\\kappa$ vs.\\ Ann.~3 & Calls inferable \\\\\n"
        + "\\midrule\n"
        + body + "\n"
        + "\\midrule\n"
        + f"Annotator 1 vs.\\ annotator 3 & --- & \\multicolumn{{2}}{{c}}{{\\textbf{{{float(readers['cohens_kappa']):.3f}}}}} "
        + f"& {a1_yes} / {a3_yes}\\% \\\\\n"
        + "\\bottomrule\n"
        + "\\end{tabularx}"
    )


# Detectors as the canonicalization table reads them, left to right: the three
# configurations of the proposed layer, then the two external baselines.
_CANON_DETECTORS = (
    ("heuristic_mediator", "Heuristic"),
    ("gliner_pii", "Transformer"),
    ("learned_lr", "Learned"),
    ("presidio", "Presidio"),
    ("spacy_ner", "spaCy NER"),
)
# The byte-level families the canonicalizer addresses, then the five that
# change token structure and so are untouched by it by construction.
_CANON_BYTE_LEVEL = ("Homoglyph substitution", "Zero-width insertion", "Mixed-language fullwidth")
_CANON_TOKEN_LEVEL = (
    "Intra-token spacing",
    "Case inversion",
    "Leetspeak",
    "Separator injection (ids)",
    "Paraphrase (digit spell-out)",
)


def build_canon_table() -> str:
    """Attack success with and without the canonicalizer, plain -> canonical.

    A detector whose record is absent is left out rather than shown as a gap,
    so the table renders whatever has finished.
    """
    cells: dict[tuple[str, str, str], str] = {}
    for row in _read_csv("canonicalization_hardening_asr_span_results.csv"):
        cells[(row["detector_key"], row["variant"], row["attack_family"])] = row["attack_success_rate"]
    detectors = [(k, label) for k, label in _CANON_DETECTORS if (k, "plain", _CANON_BYTE_LEVEL[0]) in cells]
    if not detectors:
        raise FileNotFoundError("no canonicalization results found")

    def _line(family: str) -> str:
        pairs = [
            f"{_fmt_float(cells[(k, 'plain', family)])} $\\rightarrow$ {_fmt_float(cells[(k, 'canonical', family)])}"
            for k, _ in detectors
        ]
        return f"{_tex_escape(family)} & " + " & ".join(pairs) + " \\\\"

    return (
        "\\begin{tabularx}{\\textwidth}{>{\\raggedright\\arraybackslash}X" + "c" * len(detectors) + "}\n"
        + "\\toprule\n"
        + "Attack family & " + " & ".join(label for _, label in detectors) + " \\\\\n"
        + "\\midrule\n"
        + "\n".join(_line(f) for f in _CANON_BYTE_LEVEL) + "\n"
        + "\\midrule\n"
        + "\n".join(_line(f) for f in _CANON_TOKEN_LEVEL) + "\n"
        + "\\bottomrule\n"
        + "\\end{tabularx}"
    )


def build_attrcompact_table() -> str:
    """Main-text digest of the attribute-recovery result.

    Value presence comes from the reported 32B run (it is a property of the
    release, so every attacker shares it); the last three columns are recovery
    on the questions whose value was removed, for each attacker capacity.
    """
    wanted = ("no_protection", "placeholder:presidio", "casper_style", "placeholder:learned_lr")
    labels = {"no_protection": "No protection", "placeholder:presidio": "Presidio placeholder",
              "casper_style": "Casper-style", "placeholder:learned_lr": "Learned placeholder"}
    reported = {r["condition"]: r for r in _read_csv("privacylens_attribute_recovery_summary_qwen3_32b-q4km-hf.csv")}
    by_attacker = [{r["condition"]: r for r in _read_csv(f"privacylens_attribute_recovery_summary_{tag}.csv")}
                   for tag, _ in _ATTACKER_CAPACITY]
    body = "\n".join(
        f"{labels[c]} & {_ci_point(reported[c]['value_survives_release_percent'])} & "
        + " & ".join(_ci_point(a[c]["recovery_when_value_absent_percent"]) for a in by_attacker)
        + " \\\\"
        for c in wanted
    )
    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xcccc}\n"
        + "\\toprule\n"
        + "& & \\multicolumn{3}{c}{Recovered when absent (\\%)} \\\\\n"
        + "\\cmidrule(lr){3-5}\n"
        + "Condition & Present (\\%) & 8B & 32B & 70B \\\\\n"
        + "\\midrule\n"
        + body + "\n"
        + "\\bottomrule\n"
        + "\\end{tabularx}"
    )


# Main-text labels for the evasion digest; the byte-level rows carry the dagger
# the caption uses for "closed by canonicalization".
_EVASION_LABELS = {
    "Homoglyph substitution": "Homoglyph$^\\dagger$",
    "Zero-width insertion": "Zero-width insertion$^\\dagger$",
    "Mixed-language fullwidth": "Fullwidth (mixed language)$^\\dagger$",
    "Paraphrase (digit spell-out)": "Digit spell-out",
}
_EVASION_DETECTORS = (("heuristic_mediator", "Heur."), ("gliner_pii", "Transf."),
                      ("learned_lr", "Learned"), ("presidio", "Presidio"))


def build_evasion_table() -> str:
    """Main-text digest of surface-form evasion: plain ASR for four detectors."""
    cells = {(r["detector_key"], r["attack_family"]): r["attack_success_rate"]
             for r in _read_csv("canonicalization_hardening_asr_span_results.csv") if r["variant"] == "plain"}

    def _line(family: str) -> str:
        label = _EVASION_LABELS.get(family, _tex_escape(family))
        return label + " & " + " & ".join(_fmt_float(cells[(k, family)]) for k, _ in _EVASION_DETECTORS) + " \\\\"

    return (
        "\\begin{tabularx}{\\columnwidth}{>{\\raggedright\\arraybackslash}Xcccc}\n"
        + "\\toprule\n"
        + "Attack family & " + " & ".join(label for _, label in _EVASION_DETECTORS) + " \\\\\n"
        + "\\midrule\n"
        + "\n".join(_line(f) for f in _CANON_BYTE_LEVEL) + "\n"
        + "\\midrule\n"
        + "\n".join(_line(f) for f in _CANON_TOKEN_LEVEL) + "\n"
        + "\\bottomrule\n"
        + "\\end{tabularx}"
    )


# The live-stack placement experiment: one pooled summary per detector arm.
_LIVE_STACK_MODEL = "qwen3_32b-q4km-hf"
_LIVE_STACK_ARMS = (("learned_lr", "Learned detector"), ("presidio", "Presidio"))
_LIVE_STACK_PLACEMENTS = (
    ("no_mediation", "No mediation"),
    ("ingress_only", "Ingress only"),
    ("egress_only", "Egress only (at write)"),
    ("per_edge", "Every read edge"),
    ("ingress_only_plus_restore", "Ingress only, restored"),
    ("per_edge_plus_restore", "Every read edge, restored"),
)
_LIVE_STACK_COLUMNS = (
    ("utility_percent", False),
    ("model_context.in.value_percent", False),
    ("model_context.mid.value_percent", False),
    ("nonauthorized_exposure_percent", True),
)


def _live_stack_summary(detector: str) -> dict[tuple[str, str], dict[str, str]]:
    rows = _read_csv(f"live_stack_placement_summary_{_LIVE_STACK_MODEL}_{detector}_v1_pooled.csv")
    return {(r["condition"], r["metric"]): r for r in rows}


def build_livestack_table() -> str:
    """Placement in a live agent stack, both detector arms side by side.

    Utility, the share of ingress and of reference mid-trajectory values the
    model endpoint saw, and the share of all gold values reaching any
    non-authorized boundary (index, memory, tool arguments as written, log,
    final answer). Only the last column carries its interval, for width.
    """
    arms = [(_live_stack_summary(k), label) for k, label in _LIVE_STACK_ARMS]

    def _cell(summary: dict, cond: str, metric: str, with_ci: bool) -> str:
        r = summary.get((cond, metric))
        if not r or r["point"] == "":
            return "---"
        point = f"{float(r['point']):.1f}"
        return f"{point} [{float(r['lo']):.1f}, {float(r['hi']):.1f}]" if with_ci else point

    body = "\n".join(
        label + " & " + " & ".join(_cell(s, cond, m, ci) for s, _ in arms for m, ci in _LIVE_STACK_COLUMNS) + " \\\\"
        for cond, label in _LIVE_STACK_PLACEMENTS
    )
    sub = "Util. & Ctx in & Ctx mid & Non-auth."
    return (
        "\\begin{tabular}{l" + "cccc" * len(arms) + "}\n"
        + "\\toprule\n"
        + "& " + " & ".join(f"\\multicolumn{{4}}{{c}}{{\\emph{{{label}}}}}" for _, label in arms) + " \\\\\n"
        + "".join(f"\\cmidrule(lr){{{2 + 4 * i}-{5 + 4 * i}}}" for i in range(len(arms))) + "\n"
        + "Placement & " + " & ".join(sub for _ in arms) + " \\\\\n"
        + "\\midrule\n"
        + body + "\n"
        + "\\bottomrule\n"
        + "\\end{tabular}"
    )


TABLE_BUILDERS: dict[str, Callable[[], str]] = {
    "tab:propagation": build_propagation_table,
    "tab:latency": build_latency_table,
    "tab:catwise": build_catwise_table,
    "tab:multimodal": build_multimodal_table,
    "tab:crossmodel": build_crossmodel_table,
    "tab:judge": build_judge_table,
    "tab:measprop": build_measprop_table,
    "tab:advmeas": build_advmeas_table,
    "tab:mapcompromise": build_mapcompromise_table,
    "tab:crossdom": build_crossdom_table,
    "tab:attrrecovery": build_attrrecovery_table,
    "tab:attrcap": build_attrcap_table,
    "tab:mapadv": build_mapadv_table,
    "tab:hardcase": build_hardcase_table,
    "tab:restore": build_restore_table,
    "tab:ablation": build_ablation_table,
    "tab:baseline": build_baseline_table,
    "tab:tabtransfer": build_tab_transfer_table,
    "tab:ocrslice": build_ocrslice_table,
    "tab:blindutility": build_blind_utility_table,
    "tab:blindutilitytemplate": build_blind_utility_template_table,
    "tab:downstream": build_downstream_table,
    "tab:inject": build_inject_table,
    "tab:portability": build_portability_table,
    "tab:pljudge": build_pljudge_table,
    "tab:contextattack": build_contextattack_table,
    "tab:propints": build_propints_table,
    "tab:judgecap": build_judgecap_table,
    "tab:canon": build_canon_table,
    "tab:attrcompact": build_attrcompact_table,
    "tab:evasion": build_evasion_table,
    "tab:livestack": build_livestack_table,
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
            print(f"Skipping {label}: label not present in {args.paper}")
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
