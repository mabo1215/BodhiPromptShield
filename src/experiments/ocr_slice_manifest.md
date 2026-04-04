# OCR Slice Manifest

## Included

- OCR-mediated slice membership is explicit: V4 and V8 across all 32 templates.
- Current slice coverage: 64 prompts total, split 32 essential and 32 incidental.
- The current supporting slice reports OCR Span F1, multimodal PER, and AC for matched multimodal comparators.

## Evidence Boundary

- The released multimodal supporting table is reconstructed from bundled OCR-slice summary records plus deterministic slice membership.
- The release therefore supports slice accounting and reported summary values, but not a fully independent rerun from source images.

## Missing For Full Regeneration

- Exact OCR backend name and version.
- Document-rendering assets or image-level source package.
- Rendering/preprocessing configuration for noisy OCR cases.
- Runtime metadata for OCR latency portability.

## Transfer Boundary

- Public text-only wrappers on TAB and clinical wrappers on i2b2 now have explicit protocol and execution-manifest artifacts.
- `multimodal_provenance_card.md` now consolidates what is known about OCR-facing slice construction and what still remains missing for a full public rerun.
- The CPPB multimodal slice itself still lacks an equivalent executable public wrapper with exact OCR/version provenance, even though the separate external OCR transfer route now has executed CORD, FUNSD, and SROIE public slices with filled OCR runtime manifests.