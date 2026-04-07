#!/usr/bin/env python3
"""Run an executable OCR-heavy FUNSD transfer slice on a pinned public snapshot."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from datasets import load_dataset
from rapidocr_onnxruntime import RapidOCR

from acquire_funsd_snapshot import DEFAULT_MANIFEST_PATH as SNAPSHOT_MANIFEST_PATH
from acquire_funsd_snapshot import DEFAULT_REVISION
from acquire_funsd_snapshot import acquire_snapshot
from build_cord_transfer_surface import _repo_relative
from build_cord_transfer_surface import write_csv
from ocr_transfer_common import build_presidio_analyzer
from ocr_transfer_common import build_spacy_model
from ocr_transfer_common import build_transcript
from ocr_transfer_common import char_coverage
from ocr_transfer_common import match_gold_spans
from ocr_transfer_common import mean
from ocr_transfer_common import predict_presidio_token_indices
from ocr_transfer_common import predict_spacy_token_indices
from ocr_transfer_common import span_counts
from ocr_transfer_common import token_indices_to_spans
from ocr_transfer_common import token_is_numeric_like
from ocr_transfer_common import token_needs_regex_mask


EXPERIMENTS_DIR = Path(__file__).resolve().parent
SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "funsd_transfer_results.csv"
DETAIL_OUTPUT_PATH = EXPERIMENTS_DIR / "funsd_transfer_document_metrics.csv"
EXECUTION_MANIFEST_PATH = EXPERIMENTS_DIR / "funsd_transfer_execution_manifest.csv"
RUN_LOG_PATH = EXPERIMENTS_DIR / "funsd_transfer_run_log.csv"
PREPARATION_MANIFEST_PATH = EXPERIMENTS_DIR / "funsd_transfer_preparation_manifest.csv"
PROTOCOL_PATH = EXPERIMENTS_DIR / "funsd_transfer_protocol.json"
WRAPPED_MANIFEST_PATH = EXPERIMENTS_DIR / "funsd_prompt_wrapped_manifest.csv"
RUNTIME_MANIFEST_PATH = EXPERIMENTS_DIR / "funsd_ocr_runtime_manifest.csv"

METHOD_SPECS = [
    {
        "name": "Raw OCR text prompt",
        "family": "No protection",
        "notes": "No sanitization is applied after OCR extraction.",
    },
    {
        "name": "OCR + regex masking",
        "family": "Pattern baseline",
        "notes": "Mask numeric identifiers and field-style patterns with OCR-text regexes only.",
    },
    {
        "name": "OCR + generic de-identification",
        "family": "Generic de-identification",
        "notes": "Mask regex hits plus form-like answer text around common field labels without layout routing.",
    },
    {
        "name": "OCR + Presidio form de-identification",
        "family": "Named OCR de-identification",
        "notes": "Use a real Presidio recognizer stack plus form-specific recognizers and value-span expansion on OCR text.",
    },
    {
        "name": "OCR + spaCy form de-identification",
        "family": "Named OCR de-identification",
        "notes": "Use a spaCy NER stack plus form-value expansion on OCR text.",
    },
    {
        "name": "Proposed multimodal mediation",
        "family": "Policy-aware mediation",
        "notes": "Mask likely answer/value regions with OCR-line and layout-aware heuristics while preserving form labels.",
    },
]

FORM_FIELD_KEYWORDS = {
    "account",
    "address",
    "amount",
    "claim",
    "customer",
    "date",
    "dob",
    "email",
    "fax",
    "from",
    "id",
    "invoice",
    "member",
    "name",
    "patient",
    "phone",
    "policy",
    "reference",
    "ssn",
    "tax",
    "to",
}
NER_POSITIVE_MARKERS = ("ANSWER",)


def _snapshot_metadata() -> dict[str, Any]:
    if SNAPSHOT_MANIFEST_PATH.exists():
        return json.loads(SNAPSHOT_MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def _data_files(snapshot_root: Path) -> dict[str, list[str]]:
    data_files: dict[str, list[str]] = {}
    for split in ("train", "test"):
        matched = sorted(snapshot_root.glob(f"funsd/{split}-*.parquet"))
        if matched:
            data_files[split] = [str(path) for path in matched]
    return data_files


def _label_names(dataset: Any, split: str) -> list[str]:
    return list(dataset[split].features["ner_tags"].feature.names)


def _word_box_to_pixels(box: list[int], width: int, height: int) -> tuple[float, float, float, float]:
    return (
        box[0] * width / 1000.0,
        box[1] * height / 1000.0,
        box[2] * width / 1000.0,
        box[3] * height / 1000.0,
    )


def _gold_sensitive_boxes(example: dict[str, Any], label_names: list[str], width: int, height: int) -> list[dict[str, Any]]:
    sensitive_words: list[dict[str, Any]] = []
    for token_text, bbox, tag_id in zip(example["tokens"], example["bboxes"], example["ner_tags"], strict=False):
        label = label_names[int(tag_id)]
        if not any(marker in label for marker in NER_POSITIVE_MARKERS):
            continue
        sensitive_words.append(
            {
                "text": str(token_text).strip(),
                "bbox": _word_box_to_pixels(list(bbox), width, height),
                "category": label,
            }
        )
    return sensitive_words


def _line_has_field_keyword(line_tokens: list[dict[str, Any]]) -> bool:
    line_text = " ".join(token["text"].lower() for token in line_tokens)
    return any(keyword in line_text for keyword in FORM_FIELD_KEYWORDS)


def _value_start_offset(line_tokens: list[dict[str, Any]]) -> int:
    for index, token in enumerate(line_tokens):
        if token["text"].endswith(":"):
            return min(index + 1, len(line_tokens) - 1)
    for index, token in enumerate(line_tokens[:-1]):
        if token["text"].lower().rstrip(":") in FORM_FIELD_KEYWORDS:
            return index + 1
    return 1 if len(line_tokens) > 1 else 0


def _mask_value_region(line: dict[str, Any], tokens: list[dict[str, Any]], preserve_label: bool) -> set[int]:
    line_tokens = [tokens[idx] for idx in line["token_indices"]]
    start_offset = _value_start_offset(line_tokens) if preserve_label else 0
    masked: set[int] = set()
    for offset, token in enumerate(line_tokens):
        if offset < start_offset:
            continue
        text = token["text"]
        if len(text) <= 1:
            continue
        if any(character.isalpha() for character in text) or token_needs_regex_mask(text) or token_is_numeric_like(text):
            masked.add(line["token_indices"][offset])
    return masked


def _predict_presidio_form_indices(
    transcript: str,
    tokens: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    analyzer: Any,
) -> set[int]:
    predicted = predict_presidio_token_indices(transcript, tokens, analyzer)
    for line in lines:
        line_tokens = [tokens[idx] for idx in line["token_indices"]]
        line_detected = any(index in predicted for index in line["token_indices"])
        if line_detected or _line_has_field_keyword(line_tokens):
            predicted |= _mask_value_region(line, tokens, preserve_label=True)
    return predicted


def _predict_spacy_form_indices(
    transcript: str,
    tokens: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    model: Any,
) -> set[int]:
    predicted = predict_spacy_token_indices(transcript, tokens, model)
    for line in lines:
        line_tokens = [tokens[idx] for idx in line["token_indices"]]
        line_detected = any(index in predicted for index in line["token_indices"])
        if line_detected or _line_has_field_keyword(line_tokens):
            predicted |= _mask_value_region(line, tokens, preserve_label=True)
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

    if method == "OCR + Presidio form de-identification":
        predicted_token_indices |= _predict_presidio_form_indices(transcript, tokens, lines, presidio_analyzer)
        return token_indices_to_spans(predicted_token_indices, tokens)

    if method == "OCR + spaCy form de-identification":
        predicted_token_indices |= _predict_spacy_form_indices(transcript, tokens, lines, spacy_model)
        return token_indices_to_spans(predicted_token_indices, tokens)

    for line in lines:
        line_tokens = [tokens[idx] for idx in line["token_indices"]]
        has_keyword = _line_has_field_keyword(line_tokens)
        has_colon = any(token["text"].endswith(":") for token in line_tokens)

        if method == "OCR + generic de-identification":
            if has_keyword or has_colon:
                predicted_token_indices |= _mask_value_region(line, tokens, preserve_label=True)
            continue

        if has_keyword or has_colon:
            predicted_token_indices |= _mask_value_region(line, tokens, preserve_label=True)
            continue

        line_left = min(token["bbox"][0] for token in line_tokens) if line_tokens else 0.0
        line_right = max(token["bbox"][2] for token in line_tokens) if line_tokens else 0.0
        pivot = line_left + 0.55 * (line_right - line_left)
        for offset, token in enumerate(line_tokens):
            if token["bbox"][0] < pivot:
                continue
            text = token["text"]
            if len(text) > 1 and (any(character.isalpha() for character in text) or token_needs_regex_mask(text) or token_is_numeric_like(text)):
                predicted_token_indices.add(line["token_indices"][offset])

    return token_indices_to_spans(predicted_token_indices, tokens)


def _write_protocol(snapshot_root: Path, split: str, document_count: int, snapshot: dict[str, Any]) -> None:
    protocol = {
        "benchmark": "FUNSD",
        "benchmark_family": "ocr-heavy form transfer",
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
            "protected_tag_family": ["B-ANSWER", "I-ANSWER"],
            "mapping_notes": [
                "FUNSD answer-field spans are treated as the protected privacy-bearing slice, while question/header tokens remain utility-carrying context.",
                "Gold spans are matched to OCR detections via box overlap so evaluation stays grounded in the OCR transcript rather than in source token offsets.",
                "The same declared RapidOCR runtime is reused here to form a second public OCR rerun under one documented OCR stack.",
            ],
        },
    }
    PROTOCOL_PATH.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")


def run_suite(snapshot_root: Path, split: str, max_documents: int | None) -> tuple[Path, Path, Path, Path, Path, Path]:
    snapshot = _snapshot_metadata()
    dataset = load_dataset("parquet", data_files=_data_files(snapshot_root))
    if split not in dataset:
        raise ValueError(f"No FUNSD split named '{split}' in the pinned snapshot.")
    records = list(dataset[split])
    if max_documents is not None:
        records = records[:max_documents]
    if not records:
        raise ValueError("No FUNSD records matched the requested split.")

    label_names = _label_names(dataset, split)
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

    for example in records:
        image = example["image"]
        image_id = str(example.get("id", len(wrapped_rows)))
        width, height = image.size
        wrapped_rows.append(
            {
                "benchmark": "FUNSD",
                "split": split,
                "document_id": image_id,
                "source_record_id": image_id,
                "image_size": f"{width}x{height}",
                "word_count": str(len(example["tokens"])),
                "entity_categories": "ANSWER | HEADER | QUESTION",
                "wrapper_instruction": "Protect privacy-bearing answer values while preserving question/header text and OCR-form structure for downstream reasoning.",
                "evaluation_slice": "form OCR matched transfer",
            }
        )

        started = time.perf_counter()
        ocr_result, _ = engine(np.array(image))
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        transcript, tokens, lines = build_transcript(ocr_result or [])
        gold_spans = match_gold_spans(tokens, _gold_sensitive_boxes(example, label_names, width, height))
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
            "benchmark_id": "funsd_public_forms",
            "ocr_engine": "rapidocr-onnxruntime",
            "engine_version": importlib.metadata.version("rapidocr-onnxruntime"),
            "language_pack": "default bundled multilingual detector/recognizer",
            "preprocessing_stack": "RapidOCR default preprocessing; no extra repo-side image transforms",
            "render_source": "Pinned Hugging Face FUNSD parquet snapshot",
            "image_asset_bundle": snapshot.get("snapshot_root", ""),
            "host_class": "local workstation",
            "hardware_summary": f"{platform.system()} {platform.release()} | {platform.processor()}",
            "os_runtime": platform.platform(),
            "python_runtime": sys.version.split()[0],
            "invocation_command": f"python src/experiments/funsd_ocr_transfer_suite.py --snapshot-root {_repo_relative(snapshot_root)} --split {split}",
            "notes": f"Executed OCR-heavy public FUNSD slice on snapshot revision {snapshot.get('snapshot_revision', DEFAULT_REVISION)}.",
        }
    ]
    write_csv(RUNTIME_MANIFEST_PATH, runtime_rows, list(runtime_rows[0].keys()))

    execution_rows = [
        {
            "benchmark": "FUNSD",
            "method": spec["name"],
            "family": spec["family"],
            "execution_status": "executed",
            "input_scope": f"Pinned FUNSD {split} split on public snapshot {snapshot.get('snapshot_revision', DEFAULT_REVISION)}",
            "notes": spec["notes"],
        }
        for spec in METHOD_SPECS
    ]
    write_csv(EXECUTION_MANIFEST_PATH, execution_rows, list(execution_rows[0].keys()))

    run_log_rows = [
        {
            "benchmark": "FUNSD",
            "execution_status": "executed_public_slice",
            "input_scope": f"Pinned public FUNSD snapshot ({split} split)",
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
            "command_template": f"python src/experiments/funsd_ocr_transfer_suite.py --snapshot-root {_repo_relative(snapshot_root)} --split {split}",
            "notes": "Executed OCR-heavy FUNSD rerun on a fixed public snapshot with the same declared OCR runtime used for CORD.",
        }
    ]
    write_csv(RUN_LOG_PATH, run_log_rows, list(run_log_rows[0].keys()))

    tracked_files = snapshot.get("tracked_files", [])
    preparation_rows = [
        {
            "benchmark": "FUNSD",
            "snapshot_root": _repo_relative(snapshot_root),
            "root_exists": "yes" if snapshot_root.exists() else "no",
            "parquet_file_count": str(sum(1 for item in tracked_files if str(item.get("path", "")).endswith(".parquet"))),
            "wrapper_manifest_rows": str(len(wrapped_rows)),
            "split_breakdown": " | ".join(f"{key}:{value}" for key, value in sorted(snapshot.get("split_breakdown", {}).items())),
            "snapshot_revision": snapshot.get("snapshot_revision", DEFAULT_REVISION),
            "current_surface": "executed_public_snapshot",
            "notes": "Pinned public FUNSD snapshot acquired, wrapper manifest built, OCR runtime recorded, and executed form rerun completed.",
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
    parser = argparse.ArgumentParser(description="Run an executable OCR-heavy FUNSD transfer slice.")
    parser.add_argument("--snapshot-root", type=Path, help="Pinned local FUNSD snapshot root")
    parser.add_argument("--split", default="test", help="FUNSD split to execute")
    parser.add_argument("--max-documents", type=int, help="Optional cap on documents for a smaller executed slice")
    parser.add_argument(
        "--acquire-snapshot",
        action="store_true",
        help="Acquire the default pinned FUNSD snapshot first if --snapshot-root is not supplied.",
    )
    args = parser.parse_args()

    snapshot_root = args.snapshot_root
    if snapshot_root is None:
        if not args.acquire_snapshot:
            raise SystemExit("Provide --snapshot-root or pass --acquire-snapshot to fetch the pinned public FUNSD snapshot.")
        snapshot_root = acquire_snapshot(DEFAULT_REVISION, "nielsr/funsd-layoutlmv3", force_download=False)

    outputs = run_suite(snapshot_root, args.split, args.max_documents)
    print(f"FUNSD transfer summary written to {outputs[0]}")
    print(f"FUNSD transfer detail metrics written to {outputs[1]}")
    print(f"FUNSD transfer execution manifest written to {outputs[2]}")
    print(f"FUNSD transfer run log written to {outputs[3]}")
    print(f"FUNSD OCR runtime manifest written to {outputs[4]}")
    print(f"FUNSD preparation manifest written to {outputs[5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())