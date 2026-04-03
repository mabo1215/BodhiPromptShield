# Multimodal Provenance Card

## Slice Construction

- The OCR-mediated CPPB slice is deterministic: variants V4 and V8 across all 32 templates.
- Slice size is 64 prompts total, split 32 essential and 32 incidental.
- Slice membership is auditable through `cppb_prompt_manifest.csv` and the benchmark accounting summaries.

## What Is Bundled

- Prompt-level modality membership.
- Supporting summary metrics in `multimodal_analysis.csv`.
- OCR-facing boundary note in `ocr_slice_manifest.md`.

## Rendering Boundary

- The released snapshot supports multimodal slice accounting and the reported summary metrics.
- It does not yet ship the original rendered image package, document-level OCR traces, or the exact OCR engine/version manifest needed for an end-to-end public rerun.
- `ocr_engine_runtime_manifest_template.csv` now defines the exact OCR/runtime disclosure fields that must be filled before the OCR-heavy public slices can be promoted beyond scaffold status.

## Relation To External Transfer

- TAB and i2b2 wrappers now have explicit protocol, execution-manifest, and run-log artifacts.
- OCR-heavy transfer on SROIE/CORD/FUNSD should only be promoted to the same release level after equivalent OCR/version, source-asset, and run-log provenance is bundled.