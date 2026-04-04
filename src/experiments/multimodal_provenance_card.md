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
- `ocr_engine_runtime_manifest_template.csv` remains the reusable OCR/runtime disclosure schema for reruns beyond the bundled external slices.

## Relation To External Transfer

- TAB and i2b2 wrappers now have explicit protocol, execution-manifest, and run-log artifacts.
- OCR-heavy transfer on CORD, FUNSD, and SROIE has now been promoted to that same release level with pinned snapshots, filled OCR runtime manifests, execution manifests, and run logs.
- What remains missing is the original OCR/render provenance for the separate CPPB multimodal supporting slice, not the public external OCR transfer route.