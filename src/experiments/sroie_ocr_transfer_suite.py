#!/usr/bin/env python3
"""Run an executable OCR-heavy SROIE transfer slice on a pinned public snapshot."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np
from datasets import load_dataset
from rapidocr_onnxruntime import RapidOCR

from acquire_sroie_snapshot import DEFAULT_MANIFEST_PATH as SNAPSHOT_MANIFEST_PATH
from acquire_sroie_snapshot import DEFAULT_REVISION
from acquire_sroie_snapshot import acquire_snapshot
from build_cord_transfer_surface import _repo_relative
from build_cord_transfer_surface import write_csv
from ocr_transfer_common import build_presidio_analyzer
from ocr_transfer_common import build_spacy_model
from ocr_transfer_common import build_transcript
from ocr_transfer_common import char_coverage
from ocr_transfer_common import mean
from ocr_transfer_common import predict_presidio_token_indices
from ocr_transfer_common import predict_spacy_token_indices
from ocr_transfer_common import span_counts
from ocr_transfer_common import token_indices_to_spans
from ocr_transfer_common import token_is_numeric_like
from ocr_transfer_common import token_needs_regex_mask


EXPERIMENTS_DIR = Path(__file__).resolve().parent
SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "sroie_transfer_results.csv"
DETAIL_OUTPUT_PATH = EXPERIMENTS_DIR / "sroie_transfer_document_metrics.csv"
EXECUTION_MANIFEST_PATH = EXPERIMENTS_DIR / "sroie_transfer_execution_manifest.csv"
RUN_LOG_PATH = EXPERIMENTS_DIR / "sroie_transfer_run_log.csv"
PREPARATION_MANIFEST_PATH = EXPERIMENTS_DIR / "sroie_transfer_preparation_manifest.csv"
PROTOCOL_PATH = EXPERIMENTS_DIR / "sroie_transfer_protocol.json"
WRAPPED_MANIFEST_PATH = EXPERIMENTS_DIR / "sroie_prompt_wrapped_manifest.csv"
RUNTIME_MANIFEST_PATH = EXPERIMENTS_DIR / "sroie_ocr_runtime_manifest.csv"

METHOD_SPECS = [
    {
        "name": "Raw OCR text prompt",
        "family": "No protection",
        "notes": "No sanitization is applied after OCR extraction.",
    },
    {
        "name": "OCR + regex masking",
        "family": "Pattern baseline",
        "notes": "Mask numeric identifiers and receipt-style patterns with OCR-text regexes only.",
    },
    {
        "name": "OCR + generic de-identification",
        "family": "Generic de-identification",
        "notes": "Mask regex hits plus upper receipt header lines without policy routing.",
    },
    {
        "name": "OCR + Presidio receipt de-identification",
        "family": "Named OCR de-identification",
        "notes": "Use a real Presidio recognizer stack plus receipt-specific line expansion on OCR text.",
    },
    {
        "name": "OCR + spaCy receipt de-identification",
        "family": "Named OCR de-identification",
        "notes": "Use a spaCy NER stack plus receipt-specific line expansion on OCR text.",
    },
    {
        "name": "Proposed multimodal mediation",
        "family": "Policy-aware mediation",
        "notes": "Mask sensitive receipt header and contact fields while preserving total-value utility.",
    },
]

SENSITIVE_FIELDS = ("company", "address", "date")
TOTAL_FIELD = "total"
SENSITIVE_LINE_KEYWORDS = {
    "address",
    "date",
    "gst",
    "invoice",
    "receipt",
    "ref",
    "reference",
    "tax",
    "tel",
    "time",
}
TOTAL_LINE_KEYWORDS = {"amount", "cash", "change", "gst", "subtotal", "tax", "total"}
STOPWORDS = {"and", "bhd", "co", "jln", "no", "sdn", "the"}


def _snapshot_metadata() -> dict[str, Any]:
    if SNAPSHOT_MANIFEST_PATH.exists():
        return json.loads(SNAPSHOT_MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def _data_files(snapshot_root: Path) -> dict[str, list[str]]:
    data_files: dict[str, list[str]] = {}
    for split in ("train", "test"):
        matched = sorted(snapshot_root.glob(f"data/{split}-*.parquet"))
        if matched:
            data_files[split] = [str(path) for path in matched]
    return data_files


def _parse_target_sequence(target_sequence: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for field in (*SENSITIVE_FIELDS, TOTAL_FIELD):
        match = re.search(rf"<s_{field}>(.*?)</s_{field}>", target_sequence)
        fields[field] = match.group(1).strip() if match else ""
    return fields


def _normalized_image(example: dict[str, Any]) -> np.ndarray:
    image = np.array(example["pixel_values"], dtype=np.float32)
    if image.ndim == 3 and image.shape[0] in (1, 3, 4):
        image = np.transpose(image, (1, 2, 0))
    image = np.clip((image + 1.0) * 127.5, 0, 255).astype("uint8")
    return image


def _normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _sensitive_gold_spans(tokens: list[dict[str, Any]], fields: dict[str, str]) -> list[tuple[int, int]]:
    sensitive_tokens: list[str] = []
    for field in SENSITIVE_FIELDS:
        for piece in re.findall(r"[A-Za-z0-9]+", fields.get(field, "")):
            normalized = _normalize_token(piece)
            if not normalized or normalized in STOPWORDS:
                continue
            sensitive_tokens.append(normalized)

    matched_indices: set[int] = set()
    for token_index, token in enumerate(tokens):
        candidate = _normalize_token(token["text"])
        if not candidate:
            continue
        if any(candidate == gold for gold in sensitive_tokens):
            matched_indices.add(token_index)
            continue
        if len(candidate) >= 4:
            if any(SequenceMatcher(None, candidate, gold).ratio() >= 0.82 for gold in sensitive_tokens if len(gold) >= 4):
                matched_indices.add(token_index)
    return token_indices_to_spans(matched_indices, tokens)


def _mask_header_tokens(lines: list[dict[str, Any]], tokens: list[dict[str, Any]], allow_total_tail: bool) -> set[int]:
    predicted: set[int] = set()
    for line in lines:
        line_tokens = [tokens[idx] for idx in line["token_indices"]]
        line_text = " ".join(token["text"].lower() for token in line_tokens)
        has_total_keyword = any(keyword in line_text for keyword in TOTAL_LINE_KEYWORDS)
        if line["top"] > 300 and not any(keyword in line_text for keyword in SENSITIVE_LINE_KEYWORDS):
            continue
        for offset, token in enumerate(line_tokens):
            text = token["text"]
            if len(text) <= 1:
                continue
            if allow_total_tail and has_total_keyword and token_is_numeric_like(text):
                continue
            if any(character.isalpha() for character in text) or token_needs_regex_mask(text):
                predicted.add(line["token_indices"][offset])
    return predicted


def _predict_presidio_indices(transcript: str, tokens: list[dict[str, Any]], lines: list[dict[str, Any]], analyzer: Any) -> set[int]:
    predicted = predict_presidio_token_indices(transcript, tokens, analyzer)
    line_detected = {line["line_index"] for line in lines if any(index in predicted for index in line["token_indices"])}
    if line_detected:
        predicted |= _mask_header_tokens([line for line in lines if line["line_index"] in line_detected], tokens, allow_total_tail=True)
    predicted |= _mask_header_tokens(lines, tokens, allow_total_tail=True)
    return predicted


def _predict_spacy_indices(transcript: str, tokens: list[dict[str, Any]], lines: list[dict[str, Any]], model: Any) -> set[int]:
    predicted = predict_spacy_token_indices(transcript, tokens, model)
    line_detected = {line["line_index"] for line in lines if any(index in predicted for index in line["token_indices"])}
    if line_detected:
        predicted |= _mask_header_tokens([line for line in lines if line["line_index"] in line_detected], tokens, allow_total_tail=True)
    predicted |= _mask_header_tokens(lines, tokens, allow_total_tail=True)
    return predicted


def _predict_spans(
    method: str,
    transcript: str,
    tokens: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    presidio_analyzer: Any,
    spacy_model: Any,
) -> list[tuple[int, int]]:
    if method == "Raw OCR text prompt":
        return []

    predicted_token_indices: set[int] = set()
    for token_index, token in enumerate(tokens):
        if token_needs_regex_mask(token["text"]):
            predicted_token_indices.add(token_index)

    if method == "OCR + regex masking":
        return token_indices_to_spans(predicted_token_indices, tokens)

    if method == "OCR + Presidio receipt de-identification":
        predicted_token_indices |= _predict_presidio_indices(transcript, tokens, lines, presidio_analyzer)
        return token_indices_to_spans(predicted_token_indices, tokens)

    if method == "OCR + spaCy receipt de-identification":
        predicted_token_indices |= _predict_spacy_indices(transcript, tokens, lines, spacy_model)
        return token_indices_to_spans(predicted_token_indices, tokens)

    if method == "OCR + generic de-identification":
        predicted_token_indices |= _mask_header_tokens(lines, tokens, allow_total_tail=True)
        return token_indices_to_spans(predicted_token_indices, tokens)

    predicted_token_indices |= _mask_header_tokens(lines, tokens, allow_total_tail=True)
    return token_indices_to_spans(predicted_token_indices, tokens)


def _write_protocol(snapshot_root: Path, split: str, document_count: int, snapshot: dict[str, Any]) -> None:
    protocol = {
        "benchmark": "SROIE",
        "benchmark_family": "ocr-heavy receipt transfer",
        "status": "executed_public_slice",
        "core_metrics": [
            "ocr_span_precision",
            "ocr_span_recall",
            "ocr_span_f1",
            "multimodal_per",
            "text_retention",
            "latency_ms",
        ],
        "snapshot": {
            "revision": snapshot.get("snapshot_revision", DEFAULT_REVISION),
            "snapshot_root": _repo_relative(snapshot_root),
            "source_url": snapshot.get("snapshot_url", ""),
        },
        "evaluation_slice": {
            "split": split,
            "document_count": document_count,
            "wrapper_manifest": WRAPPED_MANIFEST_PATH.name,
        },
        "matched_comparators": [
            {
                "name": spec["name"],
                "family": spec["family"],
                "notes": spec["notes"],
            }
            for spec in METHOD_SPECS
        ],
        "sensitivity_mapping": {
            "protected_fields": list(SENSITIVE_FIELDS),
            "utility_field": TOTAL_FIELD,
            "mapping_notes": [
                "SROIE company, address, and date fields are treated as the protected public receipt-privacy slice, while total is retained as utility-carrying content.",
                "Gold spans are approximated on the OCR transcript by matching receipt-field tokens from the structured target sequence to OCR tokens.",
                "The same declared RapidOCR runtime and named comparator roster are reused so SROIE forms a third public OCR rerun under one wrapper discipline.",
            ],
        },
    }
    PROTOCOL_PATH.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")


def run_suite(snapshot_root: Path, split: str, max_documents: int | None) -> tuple[Path, Path, Path, Path, Path, Path]:
    snapshot = _snapshot_metadata()
    dataset = load_dataset("parquet", data_files=_data_files(snapshot_root))
    if split not in dataset:
        raise ValueError(f"No SROIE split named '{split}' in the pinned snapshot.")
    records = list(dataset[split])
    if max_documents is not None:
        records = records[:max_documents]
    if not records:
        raise ValueError("No SROIE records matched the requested split.")

    engine = RapidOCR()
    presidio_analyzer = build_presidio_analyzer()
    spacy_model = build_spacy_model()
    detail_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, str]] = []
    wrapped_rows: list[dict[str, str]] = []
    aggregate: dict[str, dict[str, Any]] = {
        spec["name"]: {
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "gold_sensitive_chars": 0,
            "residual_sensitive_chars": 0,
            "non_sensitive_chars": 0,
            "preserved_non_sensitive_chars": 0,
            "mentions": 0,
            "latency_ms": [],
        }
        for spec in METHOD_SPECS
    }

    for row_index, example in enumerate(records):
        image_id = f"sroie_{split}_{row_index:04d}"
        fields = _parse_target_sequence(example["target_sequence"])
        image = _normalized_image(example)
        wrapped_rows.append(
            {
                "benchmark": "SROIE",
                "split": split,
                "document_id": image_id,
                "source_record_id": image_id,
                "image_size": f"{image.shape[1]}x{image.shape[0]}",
                "word_count": str(len(re.findall(r'[A-Za-z0-9]+', example["target_sequence"]))),
                "entity_categories": "company | address | date | total",
                "wrapper_instruction": "Protect identifying receipt header fields while preserving total-value utility and overall receipt structure for downstream reasoning.",
                "evaluation_slice": "receipt OCR matched transfer",
            }
        )

        started = time.perf_counter()
        ocr_result, _ = engine(image)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        transcript, tokens, lines = build_transcript(ocr_result or [])
        gold_spans = _sensitive_gold_spans(tokens, fields)
        gold_chars = char_coverage(gold_spans)
        total_chars = set(range(len(transcript)))
        non_sensitive_chars = total_chars - gold_chars

        for spec in METHOD_SPECS:
            method = spec["name"]
            predicted_spans = _predict_spans(method, transcript, tokens, lines, presidio_analyzer, spacy_model)
            predicted_chars = char_coverage(predicted_spans)
            tp, fp, fn = span_counts(predicted_spans, gold_spans)
            residual_sensitive_chars = len(gold_chars - predicted_chars)
            preserved_non_sensitive_chars = len(non_sensitive_chars - predicted_chars)
            aggregate_row = aggregate[method]
            aggregate_row["tp"] += tp
            aggregate_row["fp"] += fp
            aggregate_row["fn"] += fn
            aggregate_row["gold_sensitive_chars"] += len(gold_chars)
            aggregate_row["residual_sensitive_chars"] += residual_sensitive_chars
            aggregate_row["non_sensitive_chars"] += len(non_sensitive_chars)
            aggregate_row["preserved_non_sensitive_chars"] += preserved_non_sensitive_chars
            aggregate_row["mentions"] += len(gold_spans)
            aggregate_row["latency_ms"].append(elapsed_ms)

            detail_rows.append(
                {
                    "method": method,
                    "document_id": image_id,
                    "split": split,
                    "gold_mentions": str(len(gold_spans)),
                    "predicted_spans": str(len(predicted_spans)),
                    "span_tp": str(tp),
                    "span_fp": str(fp),
                    "span_fn": str(fn),
                    "per_percent": f"{(100.0 * residual_sensitive_chars / len(gold_chars)) if gold_chars else 0.0:.1f}",
                    "text_retention": f"{(preserved_non_sensitive_chars / len(non_sensitive_chars)) if non_sensitive_chars else 1.0:.3f}",
                    "ocr_token_count": str(len(tokens)),
                    "latency_ms": f"{elapsed_ms:.1f}",
                }
            )

    write_csv(
        WRAPPED_MANIFEST_PATH,
        wrapped_rows,
        [
            "benchmark",
            "split",
            "document_id",
            "source_record_id",
            "image_size",
            "word_count",
            "entity_categories",
            "wrapper_instruction",
            "evaluation_slice",
        ],
    )

    for spec in METHOD_SPECS:
        method = spec["name"]
        row = aggregate[method]
        precision = row["tp"] / (row["tp"] + row["fp"]) if (row["tp"] + row["fp"]) else 0.0
        recall = row["tp"] / (row["tp"] + row["fn"]) if (row["tp"] + row["fn"]) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per_percent = 100.0 * row["residual_sensitive_chars"] / row["gold_sensitive_chars"] if row["gold_sensitive_chars"] else 0.0
        text_retention = row["preserved_non_sensitive_chars"] / row["non_sensitive_chars"] if row["non_sensitive_chars"] else 1.0
        summary_rows.append(
            {
                "method": method,
                "document_count": str(len(records)),
                "mention_count": str(row["mentions"]),
                "ocr_span_precision": f"{precision:.2f}",
                "ocr_span_recall": f"{recall:.2f}",
                "ocr_span_f1": f"{f1:.2f}",
                "multimodal_per": f"{per_percent:.1f}",
                "text_retention": f"{text_retention:.2f}",
                "mean_latency_ms": f"{mean(row['latency_ms']):.1f}",
                "notes": spec["notes"],
            }
        )

    write_csv(SUMMARY_OUTPUT_PATH, summary_rows, list(summary_rows[0].keys()))
    write_csv(DETAIL_OUTPUT_PATH, detail_rows, list(detail_rows[0].keys()))

    runtime_rows = [
        {
            "benchmark_id": "sroie_public_receipts",
            "ocr_engine": "rapidocr-onnxruntime",
            "engine_version": importlib.metadata.version("rapidocr-onnxruntime"),
            "language_pack": "default bundled multilingual detector/recognizer",
            "preprocessing_stack": "Denormalized processed SROIE tensors from [-1, 1] into uint8 images, then applied RapidOCR default preprocessing",
            "render_source": "Pinned Hugging Face SROIE processed parquet snapshot",
            "image_asset_bundle": snapshot.get("snapshot_root", ""),
            "host_class": "local workstation",
            "hardware_summary": f"{platform.system()} {platform.release()} | {platform.processor()}",
            "os_runtime": platform.platform(),
            "python_runtime": sys.version.split()[0],
            "invocation_command": f"python src/experiments/sroie_ocr_transfer_suite.py --snapshot-root {_repo_relative(snapshot_root)} --split {split}",
            "notes": f"Executed OCR-heavy public SROIE slice on snapshot revision {snapshot.get('snapshot_revision', DEFAULT_REVISION)}.",
        }
    ]
    write_csv(RUNTIME_MANIFEST_PATH, runtime_rows, list(runtime_rows[0].keys()))

    execution_rows = [
        {
            "benchmark": "SROIE",
            "method": spec["name"],
            "family": spec["family"],
            "execution_status": "executed",
            "input_scope": f"Pinned SROIE {split} split on public snapshot {snapshot.get('snapshot_revision', DEFAULT_REVISION)}",
            "notes": spec["notes"],
        }
        for spec in METHOD_SPECS
    ]
    write_csv(EXECUTION_MANIFEST_PATH, execution_rows, list(execution_rows[0].keys()))

    run_log_rows = [
        {
            "benchmark": "SROIE",
            "execution_status": "executed_public_slice",
            "input_scope": f"Pinned public SROIE snapshot ({split} split)",
            "document_count": str(len(records)),
            "mention_count": str(sum(row["mentions"] for row in aggregate.values()) // len(METHOD_SPECS)),
            "split_breakdown": " | ".join(f"{key}:{value}" for key, value in sorted(snapshot.get("split_breakdown", {}).items())),
            "snapshot_manifest": SNAPSHOT_MANIFEST_PATH.name,
            "wrapper_manifest": WRAPPED_MANIFEST_PATH.name,
            "summary_output": SUMMARY_OUTPUT_PATH.name,
            "detail_output": DETAIL_OUTPUT_PATH.name,
            "execution_manifest": EXECUTION_MANIFEST_PATH.name,
            "runtime_manifest": RUNTIME_MANIFEST_PATH.name,
            "protocol": PROTOCOL_PATH.name,
            "command_template": f"python src/experiments/sroie_ocr_transfer_suite.py --snapshot-root {_repo_relative(snapshot_root)} --split {split}",
            "notes": "Executed OCR-heavy SROIE rerun on a fixed public processed snapshot with the same declared OCR runtime used for CORD and FUNSD.",
        }
    ]
    write_csv(RUN_LOG_PATH, run_log_rows, list(run_log_rows[0].keys()))

    tracked_files = snapshot.get("tracked_files", [])
    preparation_rows = [
        {
            "benchmark": "SROIE",
            "snapshot_root": _repo_relative(snapshot_root),
            "root_exists": "yes" if snapshot_root.exists() else "no",
            "parquet_file_count": str(sum(1 for item in tracked_files if str(item.get("path", "")).endswith(".parquet"))),
            "wrapper_manifest_rows": str(len(wrapped_rows)),
            "split_breakdown": " | ".join(f"{key}:{value}" for key, value in sorted(snapshot.get("split_breakdown", {}).items())),
            "snapshot_revision": snapshot.get("snapshot_revision", DEFAULT_REVISION),
            "current_surface": "executed_public_snapshot",
            "notes": "Pinned public SROIE snapshot acquired, wrapper manifest built, OCR runtime recorded, and executed receipt rerun completed.",
        }
    ]
    write_csv(PREPARATION_MANIFEST_PATH, preparation_rows, list(preparation_rows[0].keys()))
    _write_protocol(snapshot_root, split, len(records), snapshot)

    return (
        SUMMARY_OUTPUT_PATH,
        DETAIL_OUTPUT_PATH,
        EXECUTION_MANIFEST_PATH,
        RUN_LOG_PATH,
        RUNTIME_MANIFEST_PATH,
        PREPARATION_MANIFEST_PATH,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an executable OCR-heavy SROIE transfer slice.")
    parser.add_argument("--snapshot-root", type=Path, help="Pinned local SROIE snapshot root")
    parser.add_argument("--split", default="test", help="SROIE split to execute")
    parser.add_argument("--max-documents", type=int, help="Optional cap on documents for a smaller executed slice")
    parser.add_argument(
        "--acquire-snapshot",
        action="store_true",
        help="Acquire the default pinned SROIE snapshot first if --snapshot-root is not supplied.",
    )
    args = parser.parse_args()

    snapshot_root = args.snapshot_root
    if snapshot_root is None:
        if not args.acquire_snapshot:
            raise SystemExit("Provide --snapshot-root or pass --acquire-snapshot to fetch the pinned public SROIE snapshot.")
        snapshot_root = acquire_snapshot(DEFAULT_REVISION, "rajistics/sroie_processed", force_download=False)

    outputs = run_suite(snapshot_root, args.split, args.max_documents)
    print(f"SROIE transfer summary written to {outputs[0]}")
    print(f"SROIE transfer detail metrics written to {outputs[1]}")
    print(f"SROIE transfer execution manifest written to {outputs[2]}")
    print(f"SROIE transfer run log written to {outputs[3]}")
    print(f"SROIE OCR runtime manifest written to {outputs[4]}")
    print(f"SROIE preparation manifest written to {outputs[5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())