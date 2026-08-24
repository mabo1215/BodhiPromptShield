#!/usr/bin/env python3
"""Audit evidence boundaries requested by the latest editorial review.

The repository contains several historical CPPB score logs.  This script does
not treat those logs as a fresh live model rerun.  It validates the structural
template split, records the legacy dev/test comparison with its provenance,
recomputes the released baseline gap, and reports missing runtime provenance.

Outputs:
  - review_revision_audit.csv
  - review_revision_audit_runtime_manifest.csv
"""
from __future__ import annotations

import csv
import platform
import sys
from pathlib import Path
from typing import Iterable


EXPERIMENTS_DIR = Path(__file__).resolve().parent
AUDIT_PATH = EXPERIMENTS_DIR / "review_revision_audit.csv"
RUNTIME_PATH = EXPERIMENTS_DIR / "review_revision_audit_runtime_manifest.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_key_value(path: Path) -> dict[str, str]:
    rows = _read_csv(path)
    return {row.get("field", ""): row.get("value", "") for row in rows}


def _write_csv(path: Path, rows: Iterable[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _row(
    audit_id: str,
    category: str,
    metric: str,
    value: str,
    units: str,
    source: str,
    provenance: str,
    interpretation: str,
) -> dict[str, str]:
    return {
        "audit_id": audit_id,
        "category": category,
        "metric": metric,
        "value": value,
        "units": units,
        "source": source,
        "provenance": provenance,
        "interpretation": interpretation,
    }


def _audit_cppb_split(rows: list[dict[str, str]], output: list[dict[str, str]]) -> None:
    by_split: dict[str, set[str]] = {}
    prompts: set[str] = set()
    duplicate_prompts = 0
    for row in rows:
        split = row["split"]
        by_split.setdefault(split, set()).add(row["template_id"])
        prompt_id = row["prompt_id"]
        if prompt_id in prompts:
            duplicate_prompts += 1
        prompts.add(prompt_id)

    split_names = sorted(by_split)
    overlaps: set[str] = set()
    for index, left in enumerate(split_names):
        for right in split_names[index + 1 :]:
            overlaps.update(by_split[left] & by_split[right])

    output.append(_row(
        "cppb-split",
        "CPPB split integrity",
        "total_prompts",
        str(len(rows)),
        "prompts",
        "cppb_split_manifest.csv",
        "structural_manifest_audit",
        "Template-stratified release surface; this is not a model rerun.",
    ))
    output.append(_row(
        "cppb-split",
        "CPPB split integrity",
        "template_overlap_across_splits",
        str(len(overlaps)),
        "templates",
        "cppb_split_manifest.csv",
        "structural_manifest_audit",
        "Zero is required for a template-disjoint split.",
    ))
    output.append(_row(
        "cppb-split",
        "CPPB split integrity",
        "duplicate_prompt_ids",
        str(duplicate_prompts),
        "rows",
        "cppb_split_manifest.csv",
        "structural_manifest_audit",
        "Zero is required for a unique prompt manifest.",
    ))
    for split in split_names:
        output.append(_row(
            "cppb-split",
            "CPPB split integrity",
            f"{split}_templates",
            str(len(by_split[split])),
            "templates",
            "cppb_split_manifest.csv",
            "structural_manifest_audit",
            "All variants of each template are kept in one split.",
        ))


def _audit_legacy_scores(output: list[dict[str, str]]) -> None:
    path = EXPERIMENTS_DIR / "cppb_split_method_summary.csv"
    rows = _read_csv(path)
    selected = [
        row
        for row in rows
        if row.get("setting") == "Proposed (utility-constrained)"
        and row.get("split") in {"dev", "test"}
    ]
    for row in selected:
        for metric in ("per_mean", "ac_mean", "tsr_mean"):
            output.append(_row(
                "cppb-score-provenance",
                "CPPB score provenance",
                f"{row['split']}_{metric}",
                row[metric],
                "reported score",
                path.name,
                "legacy_bundled_score_log",
                "Recorded for transparency; not evidence of a fresh end-to-end live rerun.",
            ))
    if len(selected) == 2:
        for metric in ("per_mean", "ac_mean", "tsr_mean"):
            dev = float(next(row[metric] for row in selected if row["split"] == "dev"))
            test = float(next(row[metric] for row in selected if row["split"] == "test"))
            output.append(_row(
                "cppb-score-provenance",
                "CPPB score provenance",
                f"test_minus_dev_{metric}",
                f"{test - dev:.4f}",
                "score difference",
                path.name,
                "legacy_bundled_score_log",
                "A near-zero gap does not establish generalization when the underlying log is not a live rerun.",
            ))


def _audit_privacylens(output: list[dict[str, str]]) -> None:
    result_path = EXPERIMENTS_DIR / "measured_privacylens_propagation_results.csv"
    runtime_path = EXPERIMENTS_DIR / "measured_privacylens_propagation_runtime_manifest.csv"
    results = _read_csv(result_path)
    runtime = _read_key_value(runtime_path)
    learned = next(row for row in results if row["method"] == "Proposed (learned detector)")
    output.append(_row(
        "privacylens-semantic",
        "PrivacyLens measured propagation",
        "surface_form_per",
        learned["per_percent"],
        "percent",
        result_path.name,
        "exact_character_coverage",
        "Literal surface-form exposure only.",
    ))
    output.append(_row(
        "privacylens-semantic",
        "PrivacyLens semantic residue",
        "semantic_residue",
        runtime.get("semantic_residue_percent", ""),
        "percent",
        runtime_path.name,
        "gold_fact_residue_audit",
        "Sensitive facts can remain semantically conveyed after surface masking.",
    ))


def _audit_context_attack(output: list[dict[str, str]]) -> None:
    result_path = EXPERIMENTS_DIR / "context_inference_attack_results.csv"
    rows = _read_csv(result_path)
    overall = next(row for row in rows if row["attack_surface"] == "Prompt-history attribute inference")
    output.append(_row(
        "context-inference",
        "Context inference attack",
        "sanitized_accuracy",
        overall["sanitized_attack_accuracy_percent"],
        "percent",
        result_path.name,
        "bundled_local_attack_record",
        "Attack probe, not a bound on semantic recovery.",
    ))


def _audit_baseline_gap(output: list[dict[str, str]]) -> None:
    path = EXPERIMENTS_DIR / "prompt_method_comparison.csv"
    rows = {row["method"]: row for row in _read_csv(path)}
    enterprise = rows["Enterprise staged redaction"]
    proposed = rows["Proposed (utility-constrained)"]
    for metric in ("per", "ac", "tsr"):
        gap = float(proposed[metric]) - float(enterprise[metric])
        units = "percentage points" if metric == "per" else "score points"
        output.append(_row(
            "enterprise-gap",
            "Enterprise baseline gap",
            f"proposed_minus_enterprise_{metric}",
            f"{gap:.2f}",
            units,
            path.name,
            "bundled_matched_comparison",
            "The proposed setting is not a direct-exposure winner; utility gains are small and require independent validation.",
        ))


def _audit_metadata(output: list[dict[str, str]]) -> None:
    crossmodel_path = EXPERIMENTS_DIR / "crossmodel_runtime_log.csv"
    crossmodel = _read_csv(crossmodel_path)
    alias_only = sum(1 for row in crossmodel if row.get("public_backend_identifier", "").startswith("LLM-"))
    output.append(_row(
        "metadata",
        "Runtime provenance",
        "crossmodel_alias_only_rows",
        str(alias_only),
        "rows",
        crossmodel_path.name,
        "metadata_completeness_audit",
        "Exact vendor/model/version identifiers are absent from this portability slice.",
    ))

    context_path = EXPERIMENTS_DIR / "context_inference_attack_runtime_manifest.csv"
    context_header = _read_csv(context_path)
    has_digest = bool(context_header and "model_digest" in context_header[0])
    output.append(_row(
        "metadata",
        "Runtime provenance",
        "context_attack_model_digest_present",
        str(has_digest).lower(),
        "boolean",
        context_path.name,
        "metadata_completeness_audit",
        "A model tag without a digest is insufficient for exact attack rerun identification.",
    ))

    for name in ("cord_ocr_runtime_manifest.csv", "funsd_ocr_runtime_manifest.csv", "sroie_ocr_runtime_manifest.csv"):
        rows = _read_csv(EXPERIMENTS_DIR / name)
        fields = set(rows[0]) if rows else set()
        complete = all(field in fields and rows[0].get(field, "") for field in ("ocr_engine", "engine_version", "python_runtime")) if rows else False
        output.append(_row(
            "metadata",
            "OCR runtime provenance",
            f"{name}_core_fields_present",
            str(complete).lower(),
            "boolean",
            name,
            "metadata_completeness_audit",
            "Core OCR engine/version/runtime fields are present; this does not establish full VLM-loop reproducibility.",
        ))


def main() -> int:
    audit_rows: list[dict[str, str]] = []
    _audit_cppb_split(_read_csv(EXPERIMENTS_DIR / "cppb_split_manifest.csv"), audit_rows)
    _audit_legacy_scores(audit_rows)
    _audit_privacylens(audit_rows)
    _audit_context_attack(audit_rows)
    _audit_baseline_gap(audit_rows)
    _audit_metadata(audit_rows)
    fields = ["audit_id", "category", "metric", "value", "units", "source", "provenance", "interpretation"]
    _write_csv(AUDIT_PATH, audit_rows, fields)

    runtime_rows = [
        {"field": "script", "value": Path(__file__).name},
        {"field": "python", "value": sys.version.split()[0]},
        {"field": "platform", "value": platform.platform()},
        {"field": "input_scope", "value": "Bundled CPPB, PrivacyLens, baseline, attack, and OCR manifests"},
        {"field": "provenance_policy", "value": "Legacy/generated score logs are flagged and are not promoted to live rerun evidence"},
    ]
    _write_csv(RUNTIME_PATH, runtime_rows, ["field", "value"])
    print(f"Wrote {AUDIT_PATH}")
    print(f"Wrote {RUNTIME_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
