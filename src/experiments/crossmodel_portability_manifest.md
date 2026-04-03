# Cross-Model Portability Manifest

## Included

- The appendix reports an anonymous three-backend portability slice under a fixed mediation policy.
- Reported outputs are bounded to PER, AC, and TSR comparisons under matched interface-layer conditions.
- The intended interpretation is policy robustness to backend variation, not benchmarking named vendors.

## Evidence Boundary

- The current release supports the anonymous portability claim reported in the manuscript.
- It does not support backend-specific reproduction or vendor-to-vendor ranking.

## Missing For Full Regeneration

- Exact model names and versions.
- Decoding settings and prompt formatting logs.
- Runtime environment identifiers.
- Hardware and service configuration metadata.

## Promotion Contract

- `crossmodel_named_rerun_manifest_template.csv` defines the minimum disclosure fields required before this slice can be promoted from alias-level portability to a named rerun.
- Until those fields are filled from actual logs, the release should be interpreted as portability evidence only, not named backend benchmarking.