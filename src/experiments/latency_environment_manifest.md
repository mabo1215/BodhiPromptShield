# Latency Environment Manifest

## Included

- `latency_overhead.csv` reports single-request middleware-overhead measurements for the controlled CPPB setting.
- Pipelines covered: raw prompting, regex-only redaction, NER-only masking, policy-aware balanced mediation, aggressive contextual mediation.
- The intended interpretation is comparative prototype overhead within one release snapshot.

## Evidence Boundary

- The release supports relative latency comparisons across mediation pipelines under a matched local setting.
- It should not be interpreted as a portable service-level benchmark.

## Missing For Full Regeneration

- Host identifiers and hardware specification.
- Concurrency configuration and request scheduling traces.
- Prompt-length distribution tied to each latency row.
- Network or service orchestration metadata for deployment-scale inference.

## Promotion Contract

- `latency_host_manifest_template.csv` defines the minimum host, runtime, scheduling, and prompt-scope fields required before this slice can be promoted from comparative prototype overhead to a portable infrastructure claim.