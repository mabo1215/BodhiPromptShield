# Artifact Metadata Notes

## CPPB Benchmark Card Extension

- Benchmark unit: one prompt instance created from a deterministic pair of template family and privacy category, then expanded into eight fixed variants.
- Current scale: 32 templates x 8 variants = 256 prompts.
- Template families: Direct requests, Document-oriented, Retrieval-style, Tool-oriented agent.
- Privacy categories: Person names, Contact details, Postal addresses, National/account identifiers, Financial references, Medical content, Organization/project terms, Context-dependent confidential spans.
- Split semantics: V1-V4 are Essential-privacy variants and V5-V8 are Incidental-privacy variants; V4 and V8 are the OCR-mediated text-plus-image slice.
- Prompt/source provenance in the public snapshot is benchmark-authored and template-derived. The released files describe prompt stubs and accounting metadata rather than raw third-party user data.
- `cppb_release_card.md` consolidates release scope, provenance, annotation examples, wrapper specification, and known omissions into one benchmark-card-style companion note.

## Annotation And Label Semantics

- `primary_privacy_category` is assigned by benchmark construction and names the dominant protected content carried by each prompt template.
- `subset` marks whether the sensitive content is task-critical or incidental to downstream task completion.
- `modality` distinguishes text-only prompts from OCR-mediated text-plus-image prompts.
- Template- and prompt-level assignments are documented in `cppb_template_inventory.csv` and `cppb_prompt_manifest.csv`.

## Multimodal Slice Note

- The OCR-mediated slice contains 64 prompts: variant V4 and V8 across all 32 templates.
- The public snapshot exposes multimodal slice membership through the prompt manifest and accounting summary.
- `multimodal_analysis.csv` reconstructs the current supporting table from bundled slice accounting plus recorded OCR-mediated summary values.
- The current repository still does not ship raw OCR engine/version manifests or document-rendering assets for a full end-to-end multimodal rerun.

## Cross-Model Portability Note

- `crossmodel_portability_results.csv` reconstructs the current appendix portability slice from a bundled alias-level supporting record.
- `crossmodel_runtime_log.csv` records the public alias-level runtime surface for that slice while keeping vendor identities anonymized.
- Exact backend names, versions, and vendor-specific decoding fields are still not bundled in the current snapshot.
- `crossmodel_portability_manifest.md` makes the current portability evidence boundary explicit while preserving anonymous reporting.

## Public TAB Transfer Note

- `tab_transfer_results.csv` and `tab_transfer_document_metrics.csv` provide the first executable public-benchmark transfer slice in the current repository snapshot.
- This TAB slice is intentionally text-only and reports span precision/recall/F1, PER, and non-sensitive text retention rather than CPPB-style AC/TSR.
- The current runner evaluates only baselines that can be executed from the bundled public snapshot without closed-model access or heavyweight external dependencies.

## Latency Measurement Note

- `latency_overhead.csv` should be read as a prototype middleware-overhead summary for the controlled CPPB setting.
- The timing rows are intended for single-request serial processing comparisons across the listed mediation pipelines.
- `latency_environment_manifest.md` records the current interpretation boundary for those timing rows.
- The current repository does not yet bundle host identifiers or service-scale concurrency traces, so the latency table is not a portable infrastructure benchmark.