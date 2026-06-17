# Cross-Model Portability Manifest

## Included

- The appendix reports a three-backend portability slice under a fixed mediation policy.
- Each backend is now disclosed at the family level so the portability claim can be interpreted:
  - `LLM-A`: open-weight instruction-tuned LLM, 7-8B parameter class, local self-hosted runtime, open weights.
  - `LLM-B`: closed hosted general-purpose LLM, large undisclosed size class, vendor-hosted API, closed weights.
  - `LLM-C`: OCR-capable hosted multimodal LLM, mid-to-large undisclosed size class, vendor-hosted multimodal API, closed weights.
- Reported outputs are bounded to PER, AC, and TSR comparisons under matched interface-layer conditions.
- The intended interpretation is policy robustness to backend family and hosting mode, not benchmarking named vendors.

## Evidence Boundary

- The current release supports the family-level portability claim reported in the manuscript.
- It does not support backend-specific reproduction or vendor-to-vendor ranking, because exact vendor/model/version identifiers are still withheld.

## Missing For Full Regeneration

- Exact model names and versions.
- Decoding settings and prompt formatting logs.
- Runtime environment identifiers.
- Hardware and service configuration metadata.

## Promotion Contract

- `crossmodel_named_rerun_manifest_template.csv` defines the minimum disclosure fields required before this slice can be promoted from alias-level portability to a named rerun.
- Until those fields are filled from actual logs, the release should be interpreted as portability evidence only, not named backend benchmarking.