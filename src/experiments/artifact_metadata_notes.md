# Artifact Metadata Notes

## CPPB Benchmark Card Extension

- Benchmark unit: one prompt instance created from a deterministic pair of template family and privacy category, then expanded into eight fixed variants.
- Current scale: 32 templates x 8 variants = 256 prompts.
- Template families: Direct requests, Document-oriented, Retrieval-style, Tool-oriented agent.
- Privacy categories: Person names, Contact details, Postal addresses, National/account identifiers, Financial references, Medical content, Organization/project terms, Context-dependent confidential spans.
- Split semantics: V1-V4 are Essential-privacy variants and V5-V8 are Incidental-privacy variants; V4 and V8 are the OCR-mediated text-plus-image slice.
- Prompt/source provenance in the public snapshot is benchmark-authored and template-derived. The released files describe prompt stubs and accounting metadata rather than raw third-party user data.

## Annotation And Label Semantics

- `primary_privacy_category` is assigned by benchmark construction and names the dominant protected content carried by each prompt template.
- `subset` marks whether the sensitive content is task-critical or incidental to downstream task completion.
- `modality` distinguishes text-only prompts from OCR-mediated text-plus-image prompts.
- Template- and prompt-level assignments are documented in `cppb_template_inventory.csv` and `cppb_prompt_manifest.csv`.

## Multimodal Slice Note

- The OCR-mediated slice contains 64 prompts: variant V4 and V8 across all 32 templates.
- The public snapshot exposes multimodal slice membership through the prompt manifest and accounting summary.
- The current repository does not yet ship raw OCR engine/version manifests or document-rendering assets for the controlled multimodal appendix table.

## Cross-Model Portability Note

- The appendix cross-model table is currently a controlled portability slice rather than a named public rerun artifact.
- Exact backend names, versions, and decoding settings are not bundled in the current snapshot.
- The next portability release should attach backend identifiers, decoding settings, and runtime metadata to the reported table.

## Latency Measurement Note

- `latency_overhead.csv` should be read as a prototype middleware-overhead summary for the controlled CPPB setting.
- The timing rows are intended for single-request serial processing comparisons across the listed mediation pipelines.
- The current repository does not yet bundle host identifiers or service-scale concurrency traces, so the latency table is not a portable infrastructure benchmark.