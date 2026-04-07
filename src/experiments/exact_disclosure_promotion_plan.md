# Exact Disclosure Promotion Plan

## Purpose

This note defines how the current anonymous-review release can be promoted to an exact-regeneration release without conflating three different states: anonymous review evidence, confidential internal exact logs, and camera-ready public exact disclosure.

## Tier 1: Anonymous Review Release

- Keep alias-level cross-model reporting in the manuscript.
- Keep CPPB multimodal evidence as a summary slice with an explicit provenance boundary.
- Keep zero-shot local pilots labeled as pilot-executed rather than benchmark-closed.

## Tier 2: Confidential Internal Exact Bundle

- Fill `crossmodel_named_rerun_manifest_template.csv` from the actual backend logs.
- Fill `cppb_multimodal_exact_regeneration_manifest_template.csv` from the original OCR/render pipeline records.
- Archive the exact prompt wrapper, runtime manifests, host/runtime records, and result hashes in one internal disclosure bundle.
- Record file hashes for every exact-log input so that the later camera-ready disclosure can prove continuity with the anonymous-review slice.

This tier does not need to be public during review. Its purpose is to prevent information loss while the paper is still anonymized.

## Tier 3: Camera-Ready Public Exact Disclosure

- Replace alias-level LLM-A/B/C reporting with filled vendor/model/version/runtime records where anonymity is no longer required.
- Publish the filled CPPB multimodal exact-regeneration manifest if the original OCR/runtime records are releasable.
- Promote the strongest local semantic pilots from `pilot-executed` to `executed release evidence` only when the larger-scope runtime logs are also bundled.

## Immediate Repo-Level Next Steps

- The current repository can already ship the templates and promotion contract for those exact disclosures.
- The missing step is filling them from real internal logs, not redefining the schema again.
- For TIFS-facing revision text, the manuscript should describe this as a disclosure-tier boundary rather than as an unspecified reproducibility gap.

## Related Files

- `crossmodel_named_rerun_manifest_template.csv`
- `cppb_multimodal_exact_regeneration_manifest_template.csv`
- `latency_host_manifest.csv`
- `tab_ollama_zero_shot_runtime_manifest.csv`
- `i2b2_ollama_zero_shot_runtime_manifest.csv`
- `multimodal_provenance_card.md`
- `crossmodel_portability_manifest.md`