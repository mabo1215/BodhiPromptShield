#!/usr/bin/env python3
"""Run an executable OCR-heavy CORD transfer slice on a pinned public snapshot."""
from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import platform
import re
import sys
import time
from pathlib import Path
from typing import Any

from rapidocr_onnxruntime import RapidOCR

from acquire_cord_snapshot import DEFAULT_MANIFEST_PATH as SNAPSHOT_MANIFEST_PATH
from acquire_cord_snapshot import DEFAULT_REVISION
from acquire_cord_snapshot import acquire_snapshot
from build_cord_transfer_surface import _looks_like_annotation
from build_cord_transfer_surface import _repo_relative
from build_cord_transfer_surface import _resolve_image_path
from build_cord_transfer_surface import build_wrapped_manifest
from build_cord_transfer_surface import write_csv
from ocr_transfer_common import bbox_from_points
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
SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "cord_transfer_results.csv"
DETAIL_OUTPUT_PATH = EXPERIMENTS_DIR / "cord_transfer_document_metrics.csv"
EXECUTION_MANIFEST_PATH = EXPERIMENTS_DIR / "cord_transfer_execution_manifest.csv"
RUN_LOG_PATH = EXPERIMENTS_DIR / "cord_transfer_run_log.csv"
PREPARATION_MANIFEST_PATH = EXPERIMENTS_DIR / "cord_transfer_preparation_manifest.csv"
PROTOCOL_PATH = EXPERIMENTS_DIR / "cord_transfer_protocol.json"
WRAPPED_MANIFEST_PATH = EXPERIMENTS_DIR / "cord_prompt_wrapped_manifest.csv"
RUNTIME_MANIFEST_PATH = EXPERIMENTS_DIR / "cord_ocr_runtime_manifest.csv"

METHOD_SPECS = [
    {
        "name": "Raw OCR text prompt",
        "family": "No protection",
        "notes": "No sanitization is applied after OCR extraction.",
    },
    {
        "name": "OCR + regex masking",
        "family": "Pattern baseline",
        "notes": "Mask numeric identifiers and payment-style patterns with OCR-text regexes only.",
    },
    {
        "name": "OCR + generic de-identification",
        "family": "Generic de-identification",
        "notes": "Mask regex hits plus generic receipt header and contact-like text spans without policy routing.",
    },
    {
        "name": "OCR + Presidio receipt de-identification",
        "family": "Named OCR de-identification",
        "notes": "Use a real Presidio recognizer stack plus receipt-specific recognizers and line expansion on OCR text.",
    },
    {
        "name": "OCR + spaCy receipt de-identification",
        "family": "Named OCR de-identification",
        "notes": "Use a spaCy NER stack plus receipt-specific line expansion on OCR text.",
    },
    {
        "name": "Proposed multimodal mediation",
        "family": "Policy-aware mediation",
        "notes": "Mask receipt-item and payment-sensitive spans with layout-aware heuristics while preserving summary totals.",
    },
]

SENSITIVE_EXACT_CATEGORIES = {
    "menu.nm",
    "menu.sub_nm",
    "menu.etc",
    "menu.sub_etc",
    "void_menu.nm",
    "total.creditcardprice",
    "total.emoneyprice",
}
MENU_CATEGORY_PREFIXES = ("menu.nm", "menu.sub_nm", "void_menu.nm")

SENSITIVE_LINE_KEYWORDS = {
    "address",
    "alamat",
    "bank",
    "card",
    "cashier",
    "credit",
    "customer",
    "debit",
    "guest",
    "invoice",
    "member",
    "payment",
    "phone",
    "ref",
    "reference",
    "table",
    "tel",
    "transaction",
}
TOTAL_LINE_KEYWORDS = {"subtotal", "total", "tax", "service", "change", "cash"}


def _is_sensitive_category(category: str) -> bool:
    return category in SENSITIVE_EXACT_CATEGORIES or category.startswith(MENU_CATEGORY_PREFIXES)


def _annotation_paths(dataset_root: Path, split: str) -> list[Path]:
    matched: list[Path] = []
    for path in sorted(dataset_root.rglob("*.json")):
        if not _looks_like_annotation(path):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
        if str(meta.get("split", "unknown")).lower() == split.lower():
            matched.append(path)
    return matched


def _index_images(dataset_root: Path) -> dict[str, Path]:
    image_map: dict[str, Path] = {}
    for path in dataset_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            image_map.setdefault(path.stem, path)
    return image_map


def _gold_sensitive_boxes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sensitive_words: list[dict[str, Any]] = []
    for line in payload.get("valid_line", []):
        if not isinstance(line, dict):
            continue
        category = str(line.get("category", ""))
        if not _is_sensitive_category(category):
            continue
        for word in line.get("words", []):
            if not isinstance(word, dict) or "quad" not in word:
                continue
            sensitive_words.append(
                {
                    "text": str(word.get("text", "")).strip(),
                    "bbox": bbox_from_points(word["quad"]),
                    "category": category,
                }
            )
    return sensitive_words


def _mask_line_item_tokens(tokens: list[dict[str, Any]], preserve_tail_numeric: bool) -> set[int]:
    indices: set[int] = set()
    last_numeric_idx = -1
    for idx, token in enumerate(tokens):
        if token_is_numeric_like(token["text"]):
            last_numeric_idx = idx
    for idx, token in enumerate(tokens):
        text = token["text"]
        if preserve_tail_numeric and idx >= last_numeric_idx >= 0 and token_is_numeric_like(text):
            continue
        if len(text) <= 1:
            continue
        if text.lower() in TOTAL_LINE_KEYWORDS:
            continue
        if re.search(r"[A-Za-z]", text):
            indices.add(idx)
    return indices


def _predict_presidio_receipt_indices(
    transcript: str,
    tokens: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    analyzer: Any,
) -> set[int]:
    predicted_token_indices = predict_presidio_token_indices(transcript, tokens, analyzer)
    for line in lines:
        line_tokens = [tokens[idx] for idx in line["token_indices"]]
        lower_tokens = [token["text"].lower() for token in line_tokens]
        line_text = " ".join(lower_tokens)
        has_total_keyword = any(keyword in line_text for keyword in TOTAL_LINE_KEYWORDS)
        has_sensitive_keyword = any(keyword in line_text for keyword in SENSITIVE_LINE_KEYWORDS)
        line_detected = any(token_idx in predicted_token_indices for token_idx in line["token_indices"])
        looks_like_menu_line = any(token_is_numeric_like(token["text"]) for token in line_tokens[-2:]) and any(
            any(character.isalpha() for character in token["text"]) for token in line_tokens[:-1]
        )

        if not (line_detected or has_sensitive_keyword):
            continue

        if looks_like_menu_line and not has_total_keyword:
            for offset in _mask_line_item_tokens(line_tokens, preserve_tail_numeric=True):
                predicted_token_indices.add(line["token_indices"][offset])
            continue

        for offset, token in enumerate(line_tokens):
            text = token["text"]
            if len(text) <= 1:
                continue
            if has_total_keyword and token_is_numeric_like(text):
                continue
            if has_sensitive_keyword or line_detected:
                if any(character.isalpha() for character in text) or token_needs_regex_mask(text):
                    predicted_token_indices.add(line["token_indices"][offset])
    return predicted_token_indices


def _predict_spacy_receipt_indices(
    transcript: str,
    tokens: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    model: Any,
) -> set[int]:
    predicted_token_indices = predict_spacy_token_indices(transcript, tokens, model)
    for line in lines:
        line_tokens = [tokens[idx] for idx in line["token_indices"]]
        lower_tokens = [token["text"].lower() for token in line_tokens]
        line_text = " ".join(lower_tokens)
        has_total_keyword = any(keyword in line_text for keyword in TOTAL_LINE_KEYWORDS)
        has_sensitive_keyword = any(keyword in line_text for keyword in SENSITIVE_LINE_KEYWORDS)
        line_detected = any(token_idx in predicted_token_indices for token_idx in line["token_indices"])
        looks_like_menu_line = any(token_is_numeric_like(token["text"]) for token in line_tokens[-2:]) and any(
            any(character.isalpha() for character in token["text"]) for token in line_tokens[:-1]
        )

        if not (line_detected or has_sensitive_keyword):
            continue

        if looks_like_menu_line and not has_total_keyword:
            for offset in _mask_line_item_tokens(line_tokens, preserve_tail_numeric=True):
                predicted_token_indices.add(line["token_indices"][offset])
            continue

        for offset, token in enumerate(line_tokens):
            text = token["text"]
            if len(text) <= 1:
                continue
            if has_total_keyword and token_is_numeric_like(text):
                continue
            if has_sensitive_keyword or line_detected:
                if any(character.isalpha() for character in text) or token_needs_regex_mask(text):
                    predicted_token_indices.add(line["token_indices"][offset])
    return predicted_token_indices


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

    for token_idx, token in enumerate(tokens):
        if token_needs_regex_mask(token["text"]):
            predicted_token_indices.add(token_idx)

    if method == "OCR + regex masking":
        return token_indices_to_spans(predicted_token_indices, tokens)

    if method == "OCR + Presidio receipt de-identification":
        predicted_token_indices |= _predict_presidio_receipt_indices(transcript, tokens, lines, presidio_analyzer)
        return token_indices_to_spans(predicted_token_indices, tokens)

    if method == "OCR + spaCy receipt de-identification":
        predicted_token_indices |= _predict_spacy_receipt_indices(transcript, tokens, lines, spacy_model)
        return token_indices_to_spans(predicted_token_indices, tokens)

    for line in lines:
        line_tokens = [tokens[idx] for idx in line["token_indices"]]
        lower_tokens = [token["text"].lower() for token in line_tokens]
        line_text = " ".join(lower_tokens)
        has_sensitive_keyword = any(keyword in line_text for keyword in SENSITIVE_LINE_KEYWORDS)
        has_total_keyword = any(keyword in line_text for keyword in TOTAL_LINE_KEYWORDS)
        looks_like_menu_line = any(token_is_numeric_like(token["text"]) for token in line_tokens[-2:]) and any(
            re.search(r"[A-Za-z]", token["text"]) for token in line_tokens[:-1]
        )

        if method == "OCR + generic de-identification":
            if has_sensitive_keyword or (line["top"] < 300 and len(line_tokens) >= 2):
                for offset, token in enumerate(line_tokens):
                    if len(token["text"]) > 2 and (re.search(r"[A-Za-z]", token["text"]) or token_needs_regex_mask(token["text"])):
                        predicted_token_indices.add(line["token_indices"][offset])
            continue

        if has_sensitive_keyword:
            for offset, token in enumerate(line_tokens):
                if has_total_keyword and token_is_numeric_like(token["text"]):
                    continue
                if len(token["text"]) > 1:
                    predicted_token_indices.add(line["token_indices"][offset])
            continue

        if looks_like_menu_line and not has_total_keyword:
            for offset in _mask_line_item_tokens(line_tokens, preserve_tail_numeric=True):
                predicted_token_indices.add(line["token_indices"][offset])

        if line["top"] < 260 and not has_total_keyword:
            for offset, token in enumerate(line_tokens):
                if len(token["text"]) > 2 and re.search(r"[A-Za-z]", token["text"]):
                    predicted_token_indices.add(line["token_indices"][offset])

    return token_indices_to_spans(predicted_token_indices, tokens)


def _snapshot_metadata() -> dict[str, Any]:
    if SNAPSHOT_MANIFEST_PATH.exists():
        return json.loads(SNAPSHOT_MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def _write_protocol(dataset_root: Path, split: str, document_count: int, snapshot: dict[str, Any]) -> None:
    protocol = {
        "benchmark": "CORD",
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
            "dataset_root": _repo_relative(dataset_root),
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
            "sensitive_categories": sorted(SENSITIVE_EXACT_CATEGORIES),
            "mapping_notes": [
                "Receipt item-name fields and card/e-money payment fields are treated as the protected receipt-privacy slice.",
                "Aggregate subtotal and total lines remain utility-carrying content and are not designated as protected gold spans here.",
                "Gold spans are matched to OCR detections via box overlap so the evaluation remains grounded in the OCR transcript rather than in raw annotation text offsets.",
            ],
        },
    }
    PROTOCOL_PATH.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")


def run_suite(dataset_root: Path, split: str, max_documents: int | None) -> tuple[Path, Path, Path, Path, Path, Path]:
    snapshot = _snapshot_metadata()
    annotation_paths = _annotation_paths(dataset_root, split)
    if max_documents is not None:
        annotation_paths = annotation_paths[:max_documents]
    if not annotation_paths:
        raise ValueError("No CORD annotations matched the requested split.")

    image_map = _index_images(dataset_root)
    engine = RapidOCR()
    presidio_analyzer = build_presidio_analyzer()
    spacy_model = build_spacy_model()
    runtime_rows = []
    detail_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, str]] = []
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

    wrapped_rows, split_counts = build_wrapped_manifest(dataset_root)
    write_csv(
        WRAPPED_MANIFEST_PATH,
        [row for row in wrapped_rows if row["split"].lower() == split.lower()][: len(annotation_paths)],
        [
            "benchmark",
            "split",
            "document_id",
            "annotation_path",
            "image_path",
            "line_count",
            "word_count",
            "key_word_count",
            "entity_categories",
            "wrapper_instruction",
            "evaluation_slice",
        ],
    )

    for annotation_path in annotation_paths:
        payload = json.loads(annotation_path.read_text(encoding="utf-8"))
        meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
        image_id = str(meta.get("image_id", annotation_path.stem))
        image_path = _resolve_image_path(image_map, image_id, annotation_path)
        if image_path is None:
            raise FileNotFoundError(f"Missing image for CORD annotation: {annotation_path}")

        started = time.perf_counter()
        ocr_result, _ = engine(str(image_path))
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        transcript, tokens, lines = build_transcript(ocr_result or [])
        gold_spans = match_gold_spans(tokens, _gold_sensitive_boxes(payload))
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
                    "split": str(meta.get("split", "unknown")),
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
                "document_count": str(len(annotation_paths)),
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

    runtime_rows.append(
        {
            "benchmark_id": "cord_public_receipts",
            "ocr_engine": "rapidocr-onnxruntime",
            "engine_version": importlib.metadata.version("rapidocr-onnxruntime"),
            "language_pack": "default bundled multilingual detector/recognizer",
            "preprocessing_stack": "RapidOCR default preprocessing; no extra repo-side image transforms",
            "render_source": "Pinned Hugging Face CORD snapshot",
            "image_asset_bundle": snapshot.get("archive_path", ""),
            "host_class": "local workstation",
            "hardware_summary": f"{platform.system()} {platform.release()} | {platform.processor()}",
            "os_runtime": platform.platform(),
            "python_runtime": sys.version.split()[0],
            "invocation_command": f"python src/experiments/cord_ocr_transfer_suite.py --dataset-root {_repo_relative(dataset_root)} --split {split}",
            "notes": f"Executed OCR-heavy public CORD slice on snapshot revision {snapshot.get('snapshot_revision', DEFAULT_REVISION)}.",
        }
    )
    write_csv(RUNTIME_MANIFEST_PATH, runtime_rows, list(runtime_rows[0].keys()))

    execution_rows = [
        {
            "benchmark": "CORD",
            "method": spec["name"],
            "family": spec["family"],
            "execution_status": "executed",
            "input_scope": f"Pinned CORD {split} split on public snapshot {snapshot.get('snapshot_revision', DEFAULT_REVISION)}",
            "notes": spec["notes"],
        }
        for spec in METHOD_SPECS
    ]
    write_csv(EXECUTION_MANIFEST_PATH, execution_rows, list(execution_rows[0].keys()))

    run_log_rows = [
        {
            "benchmark": "CORD",
            "execution_status": "executed_public_slice",
            "input_scope": f"Pinned public CORD snapshot ({split} split)",
            "document_count": str(len(annotation_paths)),
            "mention_count": str(sum(row["mentions"] for row in aggregate.values()) // len(METHOD_SPECS)),
            "split_breakdown": " | ".join(f"{key}:{value}" for key, value in sorted(split_counts.items()) if key.lower() == split.lower()),
            "snapshot_manifest": SNAPSHOT_MANIFEST_PATH.name,
            "wrapper_manifest": WRAPPED_MANIFEST_PATH.name,
            "summary_output": SUMMARY_OUTPUT_PATH.name,
            "detail_output": DETAIL_OUTPUT_PATH.name,
            "execution_manifest": EXECUTION_MANIFEST_PATH.name,
            "runtime_manifest": RUNTIME_MANIFEST_PATH.name,
            "protocol": PROTOCOL_PATH.name,
            "command_template": f"python src/experiments/cord_ocr_transfer_suite.py --dataset-root {_repo_relative(dataset_root)} --split {split}",
            "notes": "Executed OCR-heavy CORD rerun on a fixed public snapshot with a declared OCR runtime manifest.",
        }
    ]
    write_csv(RUN_LOG_PATH, run_log_rows, list(run_log_rows[0].keys()))

    preparation_rows = [
        {
            "benchmark": "CORD",
            "dataset_root": _repo_relative(dataset_root),
            "root_exists": "yes" if dataset_root.exists() else "no",
            "annotation_file_count": str(len([path for path in dataset_root.rglob('*.json') if _looks_like_annotation(path)])),
            "image_file_count": str(len([path for path in dataset_root.rglob('*') if path.is_file() and path.suffix.lower() in {'.png', '.jpg', '.jpeg'}])),
            "wrapper_manifest_rows": str(len([row for row in wrapped_rows if row['split'].lower() == split.lower()][: len(annotation_paths)])),
            "split_breakdown": " | ".join(f"{key}:{value}" for key, value in sorted(split_counts.items())),
            "snapshot_revision": snapshot.get("snapshot_revision", DEFAULT_REVISION),
            "current_surface": "executed_public_snapshot",
            "notes": "Pinned public CORD snapshot acquired, wrapper manifest built, OCR runtime recorded, and executed receipt rerun completed.",
        }
    ]
    write_csv(PREPARATION_MANIFEST_PATH, preparation_rows, list(preparation_rows[0].keys()))
    _write_protocol(dataset_root, split, len(annotation_paths), snapshot)

    return (
        SUMMARY_OUTPUT_PATH,
        DETAIL_OUTPUT_PATH,
        EXECUTION_MANIFEST_PATH,
        RUN_LOG_PATH,
        RUNTIME_MANIFEST_PATH,
        PREPARATION_MANIFEST_PATH,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an executable OCR-heavy CORD transfer slice.")
    parser.add_argument("--dataset-root", type=Path, help="Pinned extracted CORD dataset root")
    parser.add_argument("--split", default="valid", help="CORD split to execute")
    parser.add_argument("--max-documents", type=int, help="Optional cap on documents for a smaller executed slice")
    parser.add_argument(
        "--acquire-snapshot",
        action="store_true",
        help="Acquire the default pinned CORD snapshot first if --dataset-root is not supplied.",
    )
    args = parser.parse_args()

    dataset_root = args.dataset_root
    if dataset_root is None:
        if not args.acquire_snapshot:
            raise SystemExit("Provide --dataset-root or pass --acquire-snapshot to fetch the pinned public CORD snapshot.")
        dataset_root = acquire_snapshot(DEFAULT_REVISION, "katanaml/cord", force_download=False, force_extract=False)

    outputs = run_suite(dataset_root, args.split, args.max_documents)
    print(f"CORD transfer summary written to {outputs[0]}")
    print(f"CORD transfer detail metrics written to {outputs[1]}")
    print(f"CORD transfer execution manifest written to {outputs[2]}")
    print(f"CORD transfer run log written to {outputs[3]}")
    print(f"CORD OCR runtime manifest written to {outputs[4]}")
    print(f"CORD preparation manifest written to {outputs[5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())