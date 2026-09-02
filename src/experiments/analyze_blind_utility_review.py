"""Summarize the reconstructed CPPB blind utility review.

The source files contain 88 pre-existing ratings plus 148 pending ratings for
each external blind rater.  This script keeps only the explicit external
ratings (openai_luna or claude_sonnet5), computes score distributions, and
emits an auditable per-template breakdown.

The response-family labels are deliberately descriptive heuristics, not new
quality scores:
  safe_refusal: refusal/boundary language without a useful completed action;
  useful_completion: all three rubric conditions are satisfied;
  generic_template_or_code: non-completing generic scaffolding, examples, or
      code/template responses;
  partial_or_incomplete: everything else not meeting the above conditions.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List


RATERS = ("openai_luna", "claude_sonnet5")
REFUSAL_RE = re.compile(
    r"\b(?:can't|cannot|can’t|unable|not able|refuse|decline|won't|will not|not permitted)\b",
    re.IGNORECASE,
)
GENERIC_RE = re.compile(
    r"```|\b(?:pseudocode|code scaffold|generic|template|example|outline|general guidance)\b|\b(?:import|def)\s+",
    re.IGNORECASE,
)


def read_rows(path: Path, rater: str) -> List[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    return [row for row in rows if row.get("rater_id", "") == rater]


def as_int(row: dict[str, str], key: str) -> int:
    return int(row[key])


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


def pct(value: int, total: int, digits: int = 1) -> str:
    return f"{100.0 * value / total:.{digits}f}" if total else "0.0"


def base_stats(rows: Iterable[dict[str, str]]) -> dict[str, object]:
    rows = list(rows)
    n = len(rows)
    task = Counter(as_int(row, "task_success_score") for row in rows)
    faithful = Counter(as_int(row, "faithfulness_score") for row in rows)
    required = Counter(as_int(row, "required_fields_score") for row in rows)
    families = Counter(response_family(row) for row in rows)
    fully_useful = sum(
        1
        for row in rows
        if as_int(row, "task_success_score") == 1
        and as_int(row, "faithfulness_score") == 2
        and as_int(row, "required_fields_score") == 1
    )
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
        "fully_useful_count": fully_useful,
        "safe_refusal_count": families["safe_refusal"],
        "generic_template_or_code_count": families["generic_template_or_code"],
        "partial_or_incomplete_count": families["partial_or_incomplete"],
    }


def write_csv(path: Path, rows: List[dict[str, object]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--luna",
        default="data/cppb_reconstructed_blind_ratings_vgpu3090_completed_openai_luna.csv",
    )
    parser.add_argument(
        "--claude",
        default="data/cppb_reconstructed_blind_ratings_vgpu3090_completed_claude_sonnet5.csv",
    )
    parser.add_argument("--output-dir", default="data")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    inputs = {
        "openai_luna": root / args.luna,
        "claude_sonnet5": root / args.claude,
    }
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    all_rows: Dict[str, List[dict[str, str]]] = {
        rater: read_rows(path, rater) for rater, path in inputs.items()
    }
    if any(len(rows) != 148 for rows in all_rows.values()):
        raise ValueError({rater: len(rows) for rater, rows in all_rows.items()})

    summary_fields = ["rater", *base_stats([]).keys()]
    summary_rows = [
        {"rater": rater, **base_stats(rows)} for rater, rows in all_rows.items()
    ]
    write_csv(output_dir / "cppb_blind_utility_summary.csv", summary_rows, summary_fields)

    template_fields = [
        "rater",
        "template_id",
        *base_stats([]).keys(),
    ]
    by_template_rows: List[dict[str, object]] = []
    for rater, rows in all_rows.items():
        grouped: dict[str, List[dict[str, str]]] = defaultdict(list)
        for row in rows:
            template_id = row["prompt_id"].split("-", 1)[0]
            grouped[template_id].append(row)
        for template_id in sorted(grouped):
            by_template_rows.append(
                {"rater": rater, "template_id": template_id, **base_stats(grouped[template_id])}
            )
    write_csv(
        output_dir / "cppb_blind_utility_by_template.csv",
        by_template_rows,
        template_fields,
    )

    luna_by_id = {row["review_item_id"]: row for row in all_rows["openai_luna"]}
    claude_by_id = {row["review_item_id"]: row for row in all_rows["claude_sonnet5"]}
    shared = sorted(set(luna_by_id) & set(claude_by_id))
    agreement_rows = []
    agreement_fields = ["metric", "n", "exact_agreement", "exact_agreement_pct", "mean_abs_difference"]
    for key in ("task_success_score", "faithfulness_score", "required_fields_score"):
        diffs = [abs(as_int(luna_by_id[item], key) - as_int(claude_by_id[item], key)) for item in shared]
        exact = sum(diff == 0 for diff in diffs)
        agreement_rows.append(
            {
                "metric": key,
                "n": len(shared),
                "exact_agreement": exact,
                "exact_agreement_pct": pct(exact, len(shared)),
                "mean_abs_difference": f"{sum(diffs) / len(diffs):.3f}" if diffs else "0.000",
            }
        )
    write_csv(output_dir / "cppb_blind_utility_agreement.csv", agreement_rows, agreement_fields)

    print("Wrote blind utility summaries for", ", ".join(f"{r}={len(v)}" for r, v in all_rows.items()))
    print("Templates:", len({row["template_id"] for row in by_template_rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
