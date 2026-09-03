#!/usr/bin/env python3
"""Audit and summarize human ratings for the reconstructed CPPB utility pilot.

This is intentionally separate from the external model-rater analyzer.  It
does not alter the raw ratings file and reports coverage, per-rater score
distributions, pairwise agreement on overlapping items, and a calibration flag
for refusal-like outputs that were marked as task-successful.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


SCORE_FIELDS = (
    "task_success_score",
    "faithfulness_score",
    "required_fields_score",
)
REFUSAL_RE = re.compile(
    r"\b(?:can't|cannot|unable|refuse|decline|won't|will not|not able|"
    r"no connection|not obtainable|not executable)\b",
    re.IGNORECASE,
)
GENERIC_RE = re.compile(
    r"```|\b(?:pseudocode|code scaffold|generic|template|example|outline|"
    r"general guidance)\b|\b(?:import|def)\s+",
    re.IGNORECASE,
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def as_int(row: dict[str, str], key: str) -> int:
    value = int(row[key])
    allowed = {
        "task_success_score": {0, 1},
        "faithfulness_score": {0, 1, 2},
        "required_fields_score": {0, 1},
    }[key]
    if value not in allowed:
        raise ValueError(f"{key} out of range: {value}")
    return value


def pct(value: int, total: int) -> str:
    return f"{100.0 * value / total:.1f}" if total else "0.0"


def response_family(row: dict[str, str]) -> str:
    text = f"{row.get('comments', '')}\n{row.get('model_output', '')}"
    if (
        as_int(row, "task_success_score") == 1
        and as_int(row, "faithfulness_score") == 2
        and as_int(row, "required_fields_score") == 1
    ):
        return "useful_completion"
    if REFUSAL_RE.search(text):
        return "safe_refusal"
    if GENERIC_RE.search(text):
        return "generic_template_or_code"
    return "partial_or_incomplete"


def score_stats(rows: Iterable[dict[str, str]]) -> dict[str, object]:
    rows = list(rows)
    n = len(rows)
    task = Counter(as_int(row, "task_success_score") for row in rows)
    faithful = Counter(as_int(row, "faithfulness_score") for row in rows)
    required = Counter(as_int(row, "required_fields_score") for row in rows)
    families = Counter(response_family(row) for row in rows)
    refusal_like = [
        row
        for row in rows
        if REFUSAL_RE.search(f"{row.get('comments', '')}\n{row.get('model_output', '')}")
    ]
    return {
        "n": n,
        "task_success_0": task[0],
        "task_success_1": task[1],
        "task_success_rate_pct": pct(task[1], n),
        "faithfulness_0": faithful[0],
        "faithfulness_1": faithful[1],
        "faithfulness_2": faithful[2],
        "faithfulness_2_rate_pct": pct(faithful[2], n),
        "required_fields_0": required[0],
        "required_fields_1": required[1],
        "required_fields_rate_pct": pct(required[1], n),
        "fully_useful_count": sum(
            1
            for row in rows
            if response_family(row) == "useful_completion"
        ),
        "safe_refusal_count": families["safe_refusal"],
        "generic_template_or_code_count": families["generic_template_or_code"],
        "partial_or_incomplete_count": families["partial_or_incomplete"],
        "refusal_like_count": len(refusal_like),
        "refusal_like_task_success_1": sum(
            as_int(row, "task_success_score") == 1 for row in refusal_like
        ),
    }


def pairwise_agreement(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["review_item_id"]].append(row)

    output: list[dict[str, object]] = []
    for key in SCORE_FIELDS:
        pairs = 0
        exact = 0
        absolute_difference = 0
        items_with_overlap = 0
        for item_rows in grouped.values():
            if len(item_rows) < 2:
                continue
            items_with_overlap += 1
            for index, left in enumerate(item_rows):
                for right in item_rows[index + 1 :]:
                    pairs += 1
                    difference = abs(as_int(left, key) - as_int(right, key))
                    exact += difference == 0
                    absolute_difference += difference
        output.append(
            {
                "metric": key,
                "overlap_items": items_with_overlap,
                "pair_comparisons": pairs,
                "exact_agreement_pct": pct(exact, pairs),
                "mean_abs_difference": (
                    f"{absolute_difference / pairs:.3f}" if pairs else "0.000"
                ),
            }
        )
    return output


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ratings-csv",
        default="data/cppb_reconstructed_blind_ratings_vgpu3090.csv",
    )
    parser.add_argument(
        "--review-csv",
        default="data/cppb_reconstructed_blind_review_vgpu3090.csv",
    )
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--prefix", default="cppb_human_utility")
    parser.add_argument(
        "--human-rater-id",
        action="append",
        default=None,
        help=(
            "Analyze only these human rater IDs; repeat for multiple human raters. "
            "Use this when the CSV also contains AI ratings."
        ),
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    ratings_path = root / args.ratings_csv
    review_path = root / args.review_csv
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    ratings = read_csv(ratings_path)
    raw_rating_count = len(ratings)
    if args.human_rater_id:
        human_rater_ids = set(args.human_rater_id)
        ratings = [row for row in ratings if row.get("rater_id", "") in human_rater_ids]
        if not ratings:
            raise ValueError(
                "No ratings remain after --human-rater-id filtering: "
                f"{sorted(human_rater_ids)}"
            )
    source = read_csv(review_path)
    required = {"review_item_id", "prompt_id", "condition_code", *SCORE_FIELDS}
    missing = sorted(required.difference(ratings[0] if ratings else {}))
    if missing:
        raise ValueError(f"Ratings CSV is missing fields: {missing}")

    source_ids = {row["review_item_id"] for row in source}
    rated_ids = {row["review_item_id"] for row in ratings}
    rated_prompts = {row["prompt_id"] for row in ratings}
    source_prompts = {row["prompt_id"] for row in source}
    grouped_source: dict[str, set[str]] = defaultdict(set)
    grouped_ratings: dict[str, set[str]] = defaultdict(set)
    for row in source:
        grouped_source[row["prompt_id"]].add(row["review_item_id"])
    for row in ratings:
        grouped_ratings[row["prompt_id"]].add(row["review_item_id"])
    complete_prompts = {
        prompt
        for prompt, ids in grouped_source.items()
        if ids.issubset(rated_ids) and len(ids) == 4
    }
    overlap_items = sum(
        count > 1
        for count in Counter(row["review_item_id"] for row in ratings).values()
    )

    summary_fields = ["rater", *score_stats([]).keys()]
    summary_rows = [{"rater": "all", **score_stats(ratings)}]
    for rater in sorted({row.get("rater_id", "") for row in ratings}):
        summary_rows.append(
            {"rater": rater, **score_stats([row for row in ratings if row.get("rater_id") == rater])}
        )
    write_csv(output_dir / f"{args.prefix}_summary.csv", summary_rows, summary_fields)

    agreement_rows = pairwise_agreement(ratings)
    write_csv(
        output_dir / f"{args.prefix}_agreement.csv",
        agreement_rows,
        list(agreement_rows[0].keys()),
    )

    coverage = {
        "source_rows": len(source),
        "source_unique_review_items": len(source_ids),
        "source_unique_prompt_blocks": len(source_prompts),
        "rated_rows": len(ratings),
        "rated_unique_review_items": len(rated_ids),
        "review_item_coverage_pct": pct(len(rated_ids), len(source_ids)),
        "rated_prompt_blocks": len(rated_prompts),
        "complete_prompt_blocks": len(complete_prompts),
        "prompt_block_coverage_pct": pct(len(complete_prompts), len(source_prompts)),
        "multi_rater_items": overlap_items,
        "rater_count": len({row.get("rater_id", "") for row in ratings}),
        "unrated_source_items": len(source_ids - rated_ids),
    }
    write_csv(
        output_dir / f"{args.prefix}_coverage.csv",
        [coverage],
        list(coverage.keys()),
    )

    report_path = output_dir / f"{args.prefix}_audit.txt"
    all_stats = summary_rows[0]
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(f"Ratings file: {ratings_path.relative_to(root)}\n")
        handle.write(f"Review file: {review_path.relative_to(root)}\n")
        if args.human_rater_id:
            handle.write(
                f"Human rater filter: {', '.join(sorted(set(args.human_rater_id)))}\n"
            )
            handle.write(f"Raw ratings rows before filter: {raw_rating_count}\n")
        handle.write(f"Rated rows: {coverage['rated_rows']}\n")
        handle.write(
            f"Unique rated items: {coverage['rated_unique_review_items']} / "
            f"{coverage['source_unique_review_items']} "
            f"({coverage['review_item_coverage_pct']}%)\n"
        )
        handle.write(f"Complete prompt blocks: {coverage['complete_prompt_blocks']}\n")
        handle.write(f"Multi-rater items: {coverage['multi_rater_items']}\n")
        handle.write(
            f"Refusal-like rows: {all_stats['refusal_like_count']}; "
            f"task_success=1 among them: {all_stats['refusal_like_task_success_1']}\n"
        )
        handle.write("Pairwise overlap diagnostics (not a reliability coefficient):\n")
        for row in agreement_rows:
            handle.write(
                f"- {row['metric']}: {row['pair_comparisons']} pairs, "
                f"exact agreement {row['exact_agreement_pct']}%, "
                f"MAD {row['mean_abs_difference']}\n"
            )

    print(f"Wrote human utility audit for {len(ratings)} rows to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
