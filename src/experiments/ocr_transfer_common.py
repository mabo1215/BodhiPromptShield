#!/usr/bin/env python3
"""Shared OCR-transfer helpers for public document reruns."""
from __future__ import annotations

from functools import lru_cache
import re
from typing import Any


PRICE_PATTERN = re.compile(r"^(?:rp)?\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?$")
ID_PATTERN = re.compile(r"^(?:#|no\.?|id|ref)\s*[A-Z0-9-]{3,}$", re.IGNORECASE)
DATE_PATTERN = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$")
TIME_PATTERN = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
LONG_DIGIT_PATTERN = re.compile(r"^\d{6,}$")
MIXED_ID_PATTERN = re.compile(r"^(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9#/-]{5,}$")

PRESIDIO_ALLOWED_ENTITIES = (
    "CREDIT_CARD",
    "DATE_TIME",
    "EMAIL_ADDRESS",
    "IBAN_CODE",
    "IP_ADDRESS",
    "LOCATION",
    "NRP",
    "PERSON",
    "PHONE_NUMBER",
    "URL",
    "US_BANK_NUMBER",
    "US_DRIVER_LICENSE",
    "FORM_ID",
    "RECEIPT_ID",
)

SPACY_ALLOWED_LABELS = (
    "CARDINAL",
    "DATE",
    "FAC",
    "GPE",
    "LOC",
    "MONEY",
    "NORP",
    "ORG",
    "PERSON",
)


def bbox_from_points(points: Any) -> tuple[float, float, float, float]:
    if isinstance(points, dict):
        xs = [float(points[key]) for key in ("x1", "x2", "x3", "x4")]
        ys = [float(points[key]) for key in ("y1", "y2", "y3", "y4")]
    else:
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def bbox_iou(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    left = max(box_a[0], box_b[0])
    top = max(box_a[1], box_b[1])
    right = min(box_a[2], box_b[2])
    bottom = min(box_a[3], box_b[3])
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    denominator = area_a + area_b - intersection
    return intersection / denominator if denominator else 0.0


def group_ocr_lines(result: list[list[Any]]) -> list[list[dict[str, Any]]]:
    tokens: list[dict[str, Any]] = []
    for item in result or []:
        if not isinstance(item, list) or len(item) < 2:
            continue
        bbox = bbox_from_points(item[0])
        tokens.append(
            {
                "bbox": bbox,
                "text": str(item[1]).strip(),
                "score": float(item[2]) if len(item) > 2 else 0.0,
                "center_y": (bbox[1] + bbox[3]) / 2.0,
                "left": bbox[0],
                "top": bbox[1],
            }
        )
    tokens = [token for token in tokens if token["text"]]
    tokens.sort(key=lambda token: (token["center_y"], token["left"]))

    lines: list[list[dict[str, Any]]] = []
    line_threshold = 18.0
    for token in tokens:
        if not lines:
            lines.append([token])
            continue
        current_line = lines[-1]
        mean_y = sum(entry["center_y"] for entry in current_line) / len(current_line)
        if abs(token["center_y"] - mean_y) <= line_threshold:
            current_line.append(token)
        else:
            lines.append([token])

    for line in lines:
        line.sort(key=lambda token: token["left"])
    return lines


def build_transcript(ocr_result: list[list[Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    lines = group_ocr_lines(ocr_result)
    parts: list[str] = []
    tokens: list[dict[str, Any]] = []
    line_records: list[dict[str, Any]] = []
    cursor = 0

    for line_index, line in enumerate(lines):
        line_start = cursor
        line_token_indices: list[int] = []
        for token in line:
            if parts and not parts[-1].endswith("\n"):
                parts.append(" ")
                cursor += 1
            start = cursor
            parts.append(token["text"])
            cursor += len(token["text"])
            end = cursor
            token_record = {
                **token,
                "char_start": start,
                "char_end": end,
                "line_index": line_index,
            }
            line_token_indices.append(len(tokens))
            tokens.append(token_record)
        if line_index < len(lines) - 1:
            parts.append("\n")
            cursor += 1
        line_text = " ".join(tokens[index]["text"] for index in line_token_indices)
        line_records.append(
            {
                "line_index": line_index,
                "token_indices": line_token_indices,
                "text": line_text,
                "top": min(tokens[index]["top"] for index in line_token_indices) if line_token_indices else 0.0,
                "bottom": max(tokens[index]["bbox"][3] for index in line_token_indices) if line_token_indices else 0.0,
                "char_start": line_start,
                "char_end": cursor,
            }
        )
    return "".join(parts), tokens, line_records


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    merged: list[list[int]] = [[spans[0][0], spans[0][1]]]
    for start, end in sorted(spans):
        current = merged[-1]
        if start <= current[1]:
            current[1] = max(current[1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def char_coverage(spans: list[tuple[int, int]]) -> set[int]:
    covered: set[int] = set()
    for start, end in spans:
        covered.update(range(start, end))
    return covered


def span_counts(predicted: list[tuple[int, int]], gold: list[tuple[int, int]]) -> tuple[int, int, int]:
    matched_gold: set[int] = set()
    true_positive = 0
    for pred in predicted:
        best_idx = -1
        best_overlap = 0
        for idx, gold_span in enumerate(gold):
            if idx in matched_gold:
                continue
            overlap = max(0, min(pred[1], gold_span[1]) - max(pred[0], gold_span[0]))
            if overlap > best_overlap:
                best_idx = idx
                best_overlap = overlap
        if best_idx != -1 and best_overlap > 0:
            matched_gold.add(best_idx)
            true_positive += 1
    return true_positive, max(0, len(predicted) - true_positive), max(0, len(gold) - true_positive)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def token_is_numeric_like(token_text: str) -> bool:
    stripped = token_text.replace(",", "").replace(".", "").replace(":", "")
    return stripped.isdigit()


def token_needs_regex_mask(token_text: str) -> bool:
    candidate = token_text.strip()
    return any(
        pattern.match(candidate)
        for pattern in (PRICE_PATTERN, ID_PATTERN, DATE_PATTERN, TIME_PATTERN, LONG_DIGIT_PATTERN, MIXED_ID_PATTERN)
    )


def token_indices_to_spans(token_indices: set[int], tokens: list[dict[str, Any]]) -> list[tuple[int, int]]:
    return merge_spans([(tokens[idx]["char_start"], tokens[idx]["char_end"]) for idx in sorted(token_indices)])


def match_gold_spans(
    tokens: list[dict[str, Any]],
    sensitive_words: list[dict[str, Any]],
    iou_threshold: float = 0.1,
) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for token in tokens:
        best_iou = 0.0
        for word in sensitive_words:
            overlap = bbox_iou(token["bbox"], word["bbox"])
            if overlap > best_iou:
                best_iou = overlap
        if best_iou >= iou_threshold:
            spans.append((token["char_start"], token["char_end"]))
    return merge_spans(spans)


@lru_cache(maxsize=1)
def build_presidio_analyzer() -> Any:
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer import Pattern
    from presidio_analyzer import PatternRecognizer

    analyzer = AnalyzerEngine(supported_languages=["en"])
    registry = analyzer.registry
    recognizer_specs = [
        (
            "RECEIPT_ID",
            [
                Pattern("receipt_reference", r"(?:invoice|receipt|ref|trx|transaction|member|table)\s*[:#-]?\s*[A-Z0-9-]{3,}", 0.72),
                Pattern("compact_receipt_id", r"[A-Z]{1,4}-?\d{3,}[A-Z0-9-]*", 0.62),
            ],
        ),
        (
            "FORM_ID",
            [
                Pattern("form_id_label", r"(?:claim|policy|member|account|customer|patient|invoice|reference|fax|phone|id)\s*[:#-]?\s*[A-Z0-9][A-Z0-9/-]{3,}", 0.68),
                Pattern("long_account_like", r"(?:\d[ -]?){8,18}", 0.55),
            ],
        ),
    ]
    for supported_entity, patterns in recognizer_specs:
        registry.add_recognizer(PatternRecognizer(supported_entity=supported_entity, patterns=patterns))
    return analyzer


def predict_presidio_token_indices(
    transcript: str,
    tokens: list[dict[str, Any]],
    analyzer: Any | None = None,
) -> set[int]:
    if not transcript.strip():
        return set()
    active_analyzer = analyzer or build_presidio_analyzer()
    detections = active_analyzer.analyze(
        text=transcript,
        language="en",
        entities=list(PRESIDIO_ALLOWED_ENTITIES),
    )
    token_indices: set[int] = set()
    for token_index, token in enumerate(tokens):
        for detection in detections:
            overlap = max(0, min(token["char_end"], detection.end) - max(token["char_start"], detection.start))
            if overlap > 0:
                token_indices.add(token_index)
                break
    return token_indices


@lru_cache(maxsize=1)
def build_spacy_model() -> Any:
    import spacy

    for model_name in ("en_core_web_lg", "en_core_web_md", "en_core_web_sm"):
        try:
            return spacy.load(model_name)
        except OSError:
            continue
    raise RuntimeError("A spaCy English model is required for the OCR comparator. Install en_core_web_lg, en_core_web_md, or en_core_web_sm.")


def predict_spacy_token_indices(
    transcript: str,
    tokens: list[dict[str, Any]],
    model: Any | None = None,
    allowed_labels: tuple[str, ...] = SPACY_ALLOWED_LABELS,
) -> set[int]:
    if not transcript.strip():
        return set()
    nlp = model or build_spacy_model()
    doc = nlp(transcript)
    token_indices: set[int] = set()
    for entity in doc.ents:
        if entity.label_ not in allowed_labels:
            continue
        for token_index, token in enumerate(tokens):
            overlap = max(0, min(token["char_end"], entity.end_char) - max(token["char_start"], entity.start_char))
            if overlap > 0:
                token_indices.add(token_index)
    return token_indices