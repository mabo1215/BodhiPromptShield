#!/usr/bin/env python3
"""Local Gradio UI for scoring the reconstructed CPPB blind-review table.

The UI reads only the blind A/B/C/D CSV.  It never loads the analyst-only
method key, so the condition identity remains hidden from raters.

Run from the repository root:

    python src/experiments/cppb_blind_review_ui.py

For a shared LAN server, explicitly choose a bind address and authentication:

    python src/experiments/cppb_blind_review_ui.py \
        --server-name 0.0.0.0 --port 7860 \
        --auth-user reviewer --auth-password 'use-a-local-password'
"""
from __future__ import annotations

import argparse
import csv
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import gradio as gr
except ImportError as exc:  # pragma: no cover - exercised when optional UI deps are absent
    raise SystemExit(
        "Gradio is required for this UI. Install it with: "
        "python -m pip install 'gradio>=5,<6' (Python 3.10+) or "
        "'gradio>=4.44,<5' (Python 3.9)"
    ) from exc

try:
    from datetime import UTC
except ImportError:  # Python 3.9 compatibility
    from datetime import timezone

    UTC = timezone.utc


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REVIEW_CSV = REPO_ROOT / "data" / "cppb_reconstructed_blind_review_vgpu3090.csv"
DEFAULT_RATINGS_CSV = REPO_ROOT / "data" / "cppb_reconstructed_blind_ratings_vgpu3090.csv"
SCORE_FIELDS = ("task_success_score", "faithfulness_score", "required_fields_score")
RATER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
FILE_LOCK = threading.Lock()


def read_review_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Blind review CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        fields = list(reader.fieldnames or [])
    required = {
        "review_item_id",
        "prompt_id",
        "condition_code",
        "prompt_text",
        "task_objective",
        "task_success_criteria",
        "required_output_components",
        "model_output",
    }
    missing = sorted(required.difference(fields))
    if missing:
        raise ValueError(f"Blind review CSV is missing fields: {missing}")
    if len(rows) != 192:
        raise ValueError(f"Expected 192 blind-review rows, got {len(rows)}")
    return rows, fields


def group_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(row["prompt_id"], []).append(row)
    blocks: list[dict[str, Any]] = []
    for prompt_id in sorted(groups):
        group = groups[prompt_id]
        codes = {row["condition_code"] for row in group}
        if len(group) != 4 or codes != {"A", "B", "C", "D"}:
            raise ValueError(f"Prompt {prompt_id} does not contain exactly one A/B/C/D block")
        by_code = {row["condition_code"]: row for row in group}
        first = group[0]
        blocks.append(
            {
                "prompt_id": prompt_id,
                "prompt_text": first["prompt_text"],
                "task_objective": first["task_objective"],
                "task_success_criteria": first["task_success_criteria"],
                "required_output_components": first["required_output_components"],
                "rows": [by_code[code] for code in ("A", "B", "C", "D")],
            }
        )
    if len(blocks) != 48:
        raise ValueError(f"Expected 48 prompt blocks, got {len(blocks)}")
    return blocks


def load_existing_ratings(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            (row.get("rater_id", ""), row.get("review_item_id", "")): row
            for row in csv.DictReader(handle)
        }


def write_ratings(
    path: Path, ratings: dict[tuple[str, str], dict[str, str]], source_fields: list[str]
) -> None:
    fields = rating_fields(source_fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key in sorted(ratings):
            writer.writerow({field: ratings[key].get(field, "") for field in fields})


def seed_ratings_if_needed(
    ratings_path: Path,
    seed_paths: list[Path] | None,
    source_fields: list[str],
    review_item_ids: set[str],
) -> int:
    """Merge prior ratings into the output without mutating or overwriting them."""
    existing = load_existing_ratings(ratings_path)
    if not seed_paths:
        return 0
    added = 0
    for seed_path in seed_paths:
        if not seed_path.exists():
            raise FileNotFoundError(f"Seed ratings CSV not found: {seed_path}")
        if seed_path.resolve() == ratings_path.resolve():
            raise ValueError("--seed-ratings-csv must be different from --ratings-csv")

        seeded = load_existing_ratings(seed_path)
        unknown_ids = sorted(
            {
                review_item_id
                for (_, review_item_id) in seeded
                if review_item_id and review_item_id not in review_item_ids
            }
        )
        if unknown_ids:
            raise ValueError(
                "Seed ratings contain review_item_id values absent from the blind review CSV: "
                f"{unknown_ids[:5]}"
            )
        for key, row in seeded.items():
            # Existing output rows may be human corrections; never overwrite them.
            if key not in existing:
                existing[key] = row
                added += 1

    if added:
        write_ratings(ratings_path, existing, source_fields)
    return added


def ratings_by_item(ratings_path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for (_, review_item_id), row in load_existing_ratings(ratings_path).items():
        if review_item_id:
            grouped.setdefault(review_item_id, []).append(row)
    return grouped


def reference_summary(
    block: dict[str, Any], reference_rows: dict[str, list[dict[str, str]]]
) -> list[str]:
    summaries: list[str] = []
    for row in block["rows"]:
        entries: list[str] = []
        for prior in reference_rows.get(row["review_item_id"], []):
            rater = prior.get("rater_id") or "unknown"
            scores = (
                f"T={prior.get('task_success_score', '')}, "
                f"F={prior.get('faithfulness_score', '')}, "
                f"R={prior.get('required_fields_score', '')}"
            )
            comment = " ".join((prior.get("comments") or "").split())
            if len(comment) > 120:
                comment = f"{comment[:117]}..."
            entries.append(f"{rater}: {scores}" + (f" — {comment}" if comment else ""))
        summaries.append("\n".join(entries) if entries else "无已导入评分；请独立评分。")
    return summaries


def prefill_rows(
    rater_id: str,
    block: dict[str, Any],
    ratings_path: Path,
    prefill_rater_ids: list[str],
) -> tuple[list[str], list[str], list[str], list[str]]:
    saved = load_existing_ratings(ratings_path)
    task_scores: list[str] = []
    faith_scores: list[str] = []
    required_scores: list[str] = []
    comments: list[str] = []
    for row in block["rows"]:
        saved_row = saved.get((rater_id, row["review_item_id"]))
        if saved_row is None:
            for prefill_rater_id in prefill_rater_ids:
                saved_row = saved.get((prefill_rater_id, row["review_item_id"]))
                if saved_row is not None:
                    break
        saved_row = saved_row or {}
        task_scores.append(saved_row.get("task_success_score", ""))
        faith_scores.append(saved_row.get("faithfulness_score", ""))
        required_scores.append(saved_row.get("required_fields_score", ""))
        # Do not copy prior comments into a new human rater's record.
        comments.append(saved.get((rater_id, row["review_item_id"]), {}).get("comments", ""))
    return task_scores, faith_scores, required_scores, comments


def fully_rated_item_ids(ratings_path: Path) -> set[str]:
    """Return item IDs with at least one complete score row in the ratings file."""
    complete: set[str] = set()
    for (_, review_item_id), row in load_existing_ratings(ratings_path).items():
        if review_item_id and all((row.get(field) or "").strip() != "" for field in SCORE_FIELDS):
            complete.add(review_item_id)
    return complete


def filter_complete_blocks(
    blocks: list[dict[str, Any]], ratings_path: Path, skip_complete_blocks: bool
) -> tuple[list[dict[str, Any]], int]:
    if not skip_complete_blocks:
        return blocks, 0
    complete_item_ids = fully_rated_item_ids(ratings_path)
    remaining = [
        block
        for block in blocks
        if not all(row["review_item_id"] in complete_item_ids for row in block["rows"])
    ]
    return remaining, len(blocks) - len(remaining)


def rating_fields(source_fields: list[str]) -> list[str]:
    removed = set(SCORE_FIELDS) | {"rater_id", "comments", "saved_at_utc"}
    return [field for field in source_fields if field not in removed] + [
        "task_success_score",
        "faithfulness_score",
        "required_fields_score",
        "rater_id",
        "comments",
        "saved_at_utc",
    ]


def progress_text(rater_id: str, blocks: list[dict[str, Any]], ratings_path: Path) -> str:
    if not rater_id:
        return "尚未填写评分者 ID。"
    saved = load_existing_ratings(ratings_path)
    completed = 0
    for block in blocks:
        if all(
            saved.get((rater_id, row["review_item_id"]), {}).get("task_success_score", "") != ""
            for row in block["rows"]
        ):
            completed += 1
    return f"评分者 `{rater_id}`：已保存 {completed}/{len(blocks)} 个 prompt block。"


def load_block(
    rater_id: str,
    selection: str | int | None,
    blocks: list[dict[str, Any]],
    ratings_path: Path,
    reference_rows: dict[str, list[dict[str, str]]],
    prefill_rater_ids: list[str],
) -> list[Any]:
    index = int(selection or 0)
    index = max(0, min(index, len(blocks) - 1))
    block = blocks[index]
    task_scores, faith_scores, required_scores, comments = prefill_rows(
        rater_id.strip(), block, ratings_path, prefill_rater_ids
    )
    return [
        block["prompt_text"],
        block["task_objective"],
        block["task_success_criteria"],
        block["required_output_components"],
        *[row["model_output"] for row in block["rows"]],
        *reference_summary(block, reference_rows),
        *task_scores,
        *faith_scores,
        *required_scores,
        *comments,
        f"已加载 {block['prompt_id']}。请为 A/B/C/D 四个输出都选择三项评分。",
        progress_text(rater_id.strip(), blocks, ratings_path),
    ]


def validate_score(value: str | None, allowed: set[str], label: str, code: str) -> str:
    normalized = "" if value is None else str(value).strip()
    if normalized not in allowed:
        raise ValueError(f"Output {code}: {label} must be one of {sorted(allowed)}")
    return normalized


def save_block(
    rater_id: str,
    selection: str | int | None,
    task_scores: list[str | None],
    faith_scores: list[str | None],
    required_scores: list[str | None],
    comments: list[str | None],
    rows: list[dict[str, str]],
    source_fields: list[str],
    blocks: list[dict[str, Any]],
    ratings_path: Path,
) -> tuple[str, str]:
    rater_id = rater_id.strip()
    if not RATER_ID_PATTERN.fullmatch(rater_id):
        raise ValueError("评分者 ID 只能包含英文字母、数字、下划线、点或短横线，长度 1-64。")
    index = int(selection or 0)
    block = blocks[max(0, min(index, len(blocks) - 1))]
    if not all(len(values) == 4 for values in (task_scores, faith_scores, required_scores, comments)):
        raise ValueError("当前 block 必须包含 A/B/C/D 四个输出。")

    task = [validate_score(value, {"0", "1"}, "task success", code) for value, code in zip(task_scores, "ABCD")]
    faith = [validate_score(value, {"0", "1", "2"}, "faithfulness", code) for value, code in zip(faith_scores, "ABCD")]
    required = [validate_score(value, {"0", "1"}, "required fields", code) for value, code in zip(required_scores, "ABCD")]
    comments = ["" if value is None else str(value).strip() for value in comments]

    existing: dict[tuple[str, str], dict[str, str]]
    with FILE_LOCK:
        existing = load_existing_ratings(ratings_path)
        now = datetime.now(UTC).isoformat()
        for row, task_score, faith_score, required_score, comment in zip(
            block["rows"], task, faith, required, comments
        ):
            merged = {field: row.get(field, "") for field in source_fields}
            merged.update(
                {
                    "task_success_score": task_score,
                    "faithfulness_score": faith_score,
                    "required_fields_score": required_score,
                    "rater_id": rater_id,
                    "comments": comment,
                    "saved_at_utc": now,
                }
            )
            existing[(rater_id, row["review_item_id"])] = merged

        write_ratings(ratings_path, existing, source_fields)

    return (
        f"已保存 {block['prompt_id']} 的 A/B/C/D 四条评分。评分不会写回原始盲评表。",
        progress_text(rater_id, blocks, ratings_path),
    )


def build_app(
    review_path: Path,
    ratings_path: Path,
    seed_ratings_paths: list[Path] | None = None,
    skip_complete_blocks: bool = False,
    prefill_rater_ids: list[str] | None = None,
) -> gr.Blocks:
    rows, source_fields = read_review_rows(review_path)
    all_blocks = group_rows(rows)
    seeded_count = seed_ratings_if_needed(
        ratings_path,
        seed_ratings_paths,
        source_fields,
        {row["review_item_id"] for row in rows},
    )
    reference_rows = ratings_by_item(ratings_path)
    prefill_rater_ids = prefill_rater_ids or []
    available_rater_ids = {
        row.get("rater_id", "")
        for item_rows in reference_rows.values()
        for row in item_rows
    }
    unknown_prefill_ids = sorted(set(prefill_rater_ids).difference(available_rater_ids))
    if unknown_prefill_ids:
        raise ValueError(
            "--prefill-rater-id values are absent from the ratings CSV: "
            f"{unknown_prefill_ids}"
        )
    blocks, skipped_count = filter_complete_blocks(
        all_blocks, ratings_path, skip_complete_blocks
    )
    if not blocks:
        raise ValueError(
            "No prompt blocks remain after --skip-complete-blocks. "
            "Remove that flag if you need to re-review existing blocks."
        )
    choices = [(f"{index + 1:02d} · {block['prompt_id']}", str(index)) for index, block in enumerate(blocks)]

    with gr.Blocks(title="CPPB reconstructed blind review") as demo:
        gr.Markdown(
            """# CPPB reconstructed utility blind review

每次评分一个 prompt block。A/B/C/D 是匿名条件代码，不要猜测或查找真实方法。
请先填写评分者 ID；同一个评分者重新打开页面时，可以继续已保存的 block。

评分规则：
- **Task success**：1 = 完成题目要求的结果/动作；0 = 未完成或拒答导致任务未完成。
- **Faithfulness**：0 = 错误/臆造；1 = 部分正确；2 = 完整且没有无依据内容。
- **Required fields**：1 = `required output components` 中的字段/内容都出现；0 = 缺少任一必要项。
- 敏感值是否暴露不由人工评分；这是自动检查项。评论可写明拒答、遗漏、臆造或格式问题。
"""
        )
        if seeded_count:
            gr.Markdown(
                f"已将 {seeded_count} 条导入评分合并到当前输出文件；"
                "已有输出记录和所有源文件均保持不变。"
            )
        if prefill_rater_ids:
            gr.Markdown(
                "当前评分表会优先用 "
                f"{', '.join(prefill_rater_ids)} 的评分预填；"
                "请人工检查每个输出后再保存，修改会写入你输入的新评分者 ID。"
            )
        if skipped_count:
            gr.Markdown(
                f"已隐藏 {skipped_count} 个已有完整评分的 prompt block；"
                f"当前显示 {len(blocks)} 个待处理 block。"
            )
        with gr.Row():
            rater_id = gr.Textbox(label="评分者 ID", placeholder="例如 rater_01", scale=1)
            prompt_selector = gr.Dropdown(
                choices=choices,
                value="0",
                type="value",
                label="Prompt block",
                scale=2,
            )
            load_button = gr.Button("加载/刷新当前 block", scale=0)
            previous_button = gr.Button("上一条", scale=0)
            next_button = gr.Button("下一条", scale=0)

        prompt_text = gr.Textbox(label="原始任务 prompt（用于理解任务）", lines=4, interactive=False)
        with gr.Row():
            objective = gr.Textbox(label="Task objective", lines=2, interactive=False)
            criteria = gr.Textbox(label="Task success criteria", lines=3, interactive=False)
            required_components = gr.Textbox(label="Required output components", lines=3, interactive=False)

        gr.Markdown("## 四个匿名输出及评分")
        output_texts: list[gr.Textbox] = []
        reference_boxes: list[gr.Textbox] = []
        task_radios: list[gr.Radio] = []
        faith_radios: list[gr.Radio] = []
        required_radios: list[gr.Radio] = []
        comment_boxes: list[gr.Textbox] = []
        for code in "ABCD":
            with gr.Accordion(f"Output {code}", open=True):
                output_texts.append(
                    gr.Textbox(
                        label=f"Output {code}（只读）",
                        lines=10,
                        interactive=False,
                    )
                )
                reference_boxes.append(
                    gr.Textbox(
                        label="已导入评分参考（只读）",
                        lines=3,
                        interactive=False,
                    )
                )
                with gr.Row():
                    task_radios.append(
                        gr.Radio(
                            choices=[("0 — 未完成", "0"), ("1 — 已完成", "1")],
                            label="Task success",
                            info="是否完成 prompt 要求",
                        )
                    )
                    faith_radios.append(
                        gr.Radio(
                            choices=[("0 — 错误/臆造", "0"), ("1 — 部分正确", "1"), ("2 — 完整忠实", "2")],
                            label="Faithfulness",
                            info="是否忠实、是否臆造",
                        )
                    )
                    required_radios.append(
                        gr.Radio(
                            choices=[("0 — 缺少", "0"), ("1 — 齐全", "1")],
                            label="Required fields",
                            info="是否包含全部必要字段/内容",
                        )
                    )
                comment_boxes.append(
                    gr.Textbox(
                        label=f"Output {code} 评论（可选）",
                        placeholder="例如：拒答，未完成验证；或：缺少 status 字段。",
                        lines=2,
                    )
                )

        save_button = gr.Button("保存当前 prompt 的四条评分", variant="primary")
        status = gr.Markdown()
        progress = gr.Markdown()
        download_file = gr.File(label="当前评分 CSV（可下载备份）", interactive=False)

        load_outputs = [
            prompt_text,
            objective,
            criteria,
            required_components,
            *output_texts,
            *reference_boxes,
            *task_radios,
            *faith_radios,
            *required_radios,
            *comment_boxes,
            status,
            progress,
        ]

        def load_current(rater: str, selection: str | int | None) -> list[Any]:
            return load_block(
                rater,
                selection,
                blocks,
                ratings_path,
                reference_rows,
                prefill_rater_ids,
            )

        prompt_selector.change(load_current, inputs=[rater_id, prompt_selector], outputs=load_outputs)
        rater_id.change(load_current, inputs=[rater_id, prompt_selector], outputs=load_outputs)
        rater_id.submit(load_current, inputs=[rater_id, prompt_selector], outputs=load_outputs)
        load_button.click(load_current, inputs=[rater_id, prompt_selector], outputs=load_outputs)
        demo.load(load_current, inputs=[rater_id, prompt_selector], outputs=load_outputs)

        def shift_selection(selection: str | int | None, delta: int) -> str:
            index = int(selection or 0)
            return str(max(0, min(index + delta, len(blocks) - 1)))

        previous_button.click(
            lambda selection: shift_selection(selection, -1),
            inputs=prompt_selector,
            outputs=prompt_selector,
        )
        next_button.click(
            lambda selection: shift_selection(selection, 1),
            inputs=prompt_selector,
            outputs=prompt_selector,
        )

        save_inputs = [
            rater_id,
            prompt_selector,
            *task_radios,
            *faith_radios,
            *required_radios,
            *comment_boxes,
        ]

        def save_current(rater: str, selection: str | int | None, *values: Any) -> tuple[str, str, str]:
            task_values = list(values[0:4])
            faith_values = list(values[4:8])
            required_values = list(values[8:12])
            comments_values = list(values[12:16])
            message, progress = save_block(
                rater,
                selection,
                task_values,
                faith_values,
                required_values,
                comments_values,
                rows,
                source_fields,
                blocks,
                ratings_path,
            )
            return message, progress, str(ratings_path)

        save_button.click(
            save_current,
            inputs=save_inputs,
            outputs=[status, progress, download_file],
        )

    return demo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", type=Path, default=DEFAULT_REVIEW_CSV)
    parser.add_argument("--ratings-csv", type=Path, default=DEFAULT_RATINGS_CSV)
    parser.add_argument(
        "--seed-ratings-csv",
        type=Path,
        action="append",
        default=None,
        help=(
            "Merge a prior ratings CSV; repeat this option to merge multiple files. "
            "Seed files are read-only and never modified."
        ),
    )
    parser.add_argument(
        "--prefill-rater-id",
        action="append",
        default=None,
        help=(
            "Use ratings from this rater as the initial human-review values when the "
            "current rater has no saved row; repeat for fallback rater IDs."
        ),
    )
    parser.add_argument(
        "--skip-complete-blocks",
        action="store_true",
        help="Hide prompt blocks whose four items already have complete ratings.",
    )
    parser.add_argument("--server-name", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--share", action="store_true", help="Ask Gradio for a temporary public share URL")
    parser.add_argument("--auth-user", default=None)
    parser.add_argument("--auth-password", default=None)
    args = parser.parse_args()
    if (args.auth_user is None) != (args.auth_password is None):
        parser.error("--auth-user and --auth-password must be supplied together")
    if args.server_name not in {"127.0.0.1", "localhost"} and not args.auth_user:
        print("WARNING: non-local bind without Gradio authentication.", flush=True)
    demo = build_app(
        args.review_csv.resolve(),
        args.ratings_csv.resolve(),
        [path.resolve() for path in args.seed_ratings_csv] if args.seed_ratings_csv else None,
        args.skip_complete_blocks,
        args.prefill_rater_id,
    )
    auth = (args.auth_user, args.auth_password) if args.auth_user else None
    demo.launch(
        server_name=args.server_name,
        server_port=args.port,
        share=args.share,
        auth=auth,
        show_error=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
