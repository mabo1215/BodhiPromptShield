# CPPB Release Card

## Scope

- Release unit: one deterministic prompt instance built from a template family, a primary privacy category, and one of eight fixed variants.
- Current scale: 256 prompts from 32 templates x 8 variants.
- Intended use: controlled evaluation of prompt-level privacy mediation under matched downstream settings.
- Non-goal: redistribution of raw third-party user prompts, multimodal source assets, or a fully externalized community benchmark package.

## Provenance

- Prompt sources are benchmark-authored families rather than harvested user records.
- Prompt-family coverage: Direct requests, Document-oriented, Retrieval-style, Tool-oriented agent.
- Privacy-category coverage: Person names, Contact details, Postal addresses, National/account identifiers, Financial references, Medical content, Organization/project terms, Context-dependent confidential spans.
- Modality coverage: text-only plus OCR-mediated text-plus-image prompts.

## Split Semantics

- V1-V4: Essential-privacy variants where sensitive content is task-critical.
- V5-V8: Incidental-privacy variants where sensitive content is not strictly required for downstream success.
- V4 and V8: OCR-mediated text-plus-image slice.

## Label Semantics

- `primary_privacy_category`: benchmark-construction label naming the dominant protected content.
- `subset`: construction-time split label, not a model prediction.
- `modality`: text-only or OCR-mediated text-plus-image.
- Template and prompt assignments are auditable through the released inventory, manifest, and accounting records.

## Annotation Examples

- Stable lexical identifiers: names, e-mail addresses, account numbers, and postal addresses.
- Context-dependent spans: confidential project references, organization-specific internal terms, or task-conditioned sensitive content.
- OCR-mediated cases: scanned invoices, report snippets, and image-assisted variants in which privacy-bearing content enters through OCR.

## Wrapper Specification

- External transfer should preserve the same mediation protocol: matched baseline comparisons, the same utility definitions, and explicit separation between text-only, multimodal, and clinically specialized slices.
- TAB wrappers operate over public ECHR JSON documents.
- i2b2 wrappers operate only over user-provided normalized exports and do not redistribute licensed clinical notes.
- Public-benchmark wrapper execution status is tracked through explicit execution-manifest CSVs so that protocol-defined but unexecuted comparator families are not misread as completed reruns.

## Known Omissions

- No raw OCR assets or end-to-end OCR regeneration package.
- No named cross-model runtime logs in the current public snapshot.
- No hardware/concurrency manifest for portable latency benchmarking.
- No bundled licensed i2b2 clinical result tables or OCR-heavy public transfer score tables yet.
- No bundled prompted-LLM or domain-specific external runtime for the public-benchmark wrapper protocols.