# External Wrapper Release Card

## Scope

- This note covers the public wrapper protocols used for TAB and i2b2 external transfer.
- The invariant is a matched mediation protocol: the same wrapper semantics, the same released comparator roster definitions, and the same distinction between executed results and protocol-only families.

## Benchmarks

- TAB uses the bundled public ECHR JSON release under a text-only anonymization slice.
- i2b2 uses user-supplied normalized exports only; the repository does not redistribute licensed clinical notes.

## Executed Comparator Families

- Raw prompt.
- Regex-only masking.
- NER-only masking.
- Presidio-class structured heuristic.
- Presidio-class structured-plus-NER heuristic.
- Released hybrid heuristic de-identification.
- Released BodhiPromptShield heuristic mediator.

## Protocol-Only Comparator Families

- Prompted LLM zero-shot de-identification.
- Domain-specific or named industrial clinical de-identification pipelines.

## Generated Artifacts

- Protocol JSON: benchmark-specific wrapper and roster specification.
- Wrapped manifest CSV: input inventory aligned to the wrapper protocol.
- Result CSV: method-level summary metrics when execution is possible.
- Document metrics CSV: per-document or per-note detailed metrics when execution is possible.
- Execution manifest CSV: method roster with executed vs. protocol-only status.
- Run log CSV: input scope, split counts, command template, and output files for the released rerun surface.

## Licensing Boundary

- TAB artifacts are bundled because the source benchmark is public.
- i2b2 result files can only be generated locally by a licensed user from normalized exports.
- OCR-heavy public transfer is not yet bundled under the same wrapper because OCR/version and source-asset provenance are still incomplete.