# CPPB Split Release Card

## Split Rule

- The released split is template-stratified: all eight variants of one template stay in the same split.
- The deterministic assignment rule is `template_stratified_family_category_rotation`.
- Each split retains all four prompt families and all eight privacy categories.

## Released Counts

- Train: 16 templates / 128 prompts
- Dev: 8 templates / 64 prompts
- Test: 8 templates / 64 prompts

## Intended Use

- Train: future detector/router fitting or prompt-policy learning on a template-disjoint slice.
- Dev: threshold/profile selection and ablation tuning without touching the final held-out slice.
- Test: final report-only evaluation under the released template-disjoint protocol.

## Leakage Boundary

- No template crosses splits.
- Because all variants of a template remain co-located, the split prevents variant-level leakage between train/dev/test.
- The current paper still reports the legacy matched full-release CPPB aggregates for continuity, but the released split surface is now available for stricter future selection/evaluation separation.
