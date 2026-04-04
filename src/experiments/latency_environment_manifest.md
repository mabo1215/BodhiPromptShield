# Latency Environment Manifest

## Included

- `latency_overhead.csv` reports single-request middleware-overhead measurements for the controlled CPPB setting.
- `latency_host_manifest.csv` records the actual local workstation, OS, Python runtime, scheduling mode, and prompt-scope bucket for that bundled latency snapshot.
- Pipelines covered: raw prompting, regex-only redaction, NER-only masking, policy-aware balanced mediation, aggressive contextual mediation.
- The intended interpretation is comparative prototype overhead within one release snapshot.

## Evidence Boundary

- The release supports relative latency comparisons across mediation pipelines under a matched local setting.
- It should not be interpreted as a portable service-level benchmark.

## Missing For Full Regeneration

- Service-scale concurrency traces.
- Memory usage or throughput telemetry tied to each latency row.
- Network or service orchestration metadata for deployment-scale inference.
- A broader host matrix if the table is later promoted from one local snapshot to a portable infrastructure comparison.

## Promotion Contract

- `latency_host_manifest_template.csv` remains the reusable schema for future reruns on alternate hosts.
- `latency_host_manifest.csv` is the current filled instance for the bundled release snapshot.