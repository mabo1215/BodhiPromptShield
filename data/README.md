# CPPB reconstructed annotation surface

`cppb_full_annotations.jsonl` and `cppb_full_annotations.csv` are generated
from the released `src/experiments/cppb_prompt_manifest.csv` and
`cppb_split_manifest.csv` by:

```text
python src/experiments/build_cppb_full_annotations.py
```

Important provenance boundary: the public CPPB release contains stubs, not the
historical raw prompt payloads. These files are therefore a deterministic
reconstruction from the public metadata. They provide complete prompt text and
machine-checkable Python Unicode code-point half-open character offsets (not
UTF-8 byte or token offsets) for a new
reconstructed protocol; they do not recover or claim to reproduce the original
private/raw CPPB prompts.

Text-only rows are prompt-ready for a separately frozen reconstructed runtime.
The 64 OCR-mediated rows contain OCR-text proxies but remain blocked for an
image-backed rerun until the original render package, images, OCR engine/version,
and preprocessing configuration are available.

## Reconstructed text-only utility pilot

The vGPU 3090 run uses the 48 text-only prompts in the released `test` split
and four matched conditions per prompt, producing 192 named `llama3.2:latest`
outputs:

- `cppb_reconstructed_utility_outputs_vgpu3090.csv` and `.jsonl`: full prompts,
  condition labels, outputs, latency, and response metadata;
- `cppb_reconstructed_blind_review_vgpu3090.csv`: A/B/C/D randomized review
  table with blank `task_success_score`, `faithfulness_score`, and
  `required_fields_score` columns;
- `cppb_reconstructed_blind_review_instructions.md`: rater rubric;
- `cppb_reconstructed_blind_method_key_vgpu3090.csv`: analyst-only condition
  mapping; do not distribute before ratings are complete;
- `cppb_reconstructed_utility_runtime_manifest_vgpu3090.csv` and
  `cppb_reconstructed_utility_run_log_vgpu3090.csv`: model digest, decoding,
  hardware, and run provenance.

This is a reconstructed utility pilot, not the original CPPB live rerun.
The completed blind-rating artifacts are external model-based utility pilots;
they are not human validation and do not score exact raw-value exposure.

The completed ratings and deterministic summaries are:

- `cppb_reconstructed_blind_ratings_vgpu3090_completed_openai_luna.csv` and
  `...completed_claude_sonnet5.csv`: the original 88 rows plus 148 pending
  blind ratings from each external rater;
- `cppb_blind_utility_summary.csv`: score distributions and descriptive
  response-family counts for both raters;
- `cppb_blind_utility_by_template.csv`: per-template breakdown for the seven
  template IDs represented in the pending reconstructed slice;
- `cppb_blind_utility_agreement.csv`: exact agreement and mean absolute
  difference between the two external raters.

The summaries are regenerated with:

```text
python src/experiments/analyze_blind_utility_review.py
```

The local scoring interface is started with:

```text
python src/experiments/cppb_blind_review_ui.py
```

Open the displayed local URL, enter a rater ID, select a prompt block, score
all four anonymous outputs, add optional comments, and click **保存当前
prompt 的四条评分**. Ratings are written to
`cppb_reconstructed_blind_ratings_vgpu3090.csv`; this file contains only the
blind condition codes and rater scores, not the analyst method key.
