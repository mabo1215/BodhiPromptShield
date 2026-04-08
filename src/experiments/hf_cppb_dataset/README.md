---
language:
- en
pretty_name: Controlled Prompt-Privacy Benchmark
size_categories:
- n<1K
task_categories:
- text-generation
- text-classification
task_ids:
- named-entity-recognition
- document-question-answering
- text2text-generation
tags:
- privacy
- prompt-security
- de-identification
- redaction
- llm-agents
- evaluation
license: other
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train.csv
  - split: validation
    path: data/dev.csv
  - split: test
    path: data/test.csv
---

# CPPB

## Summary

CPPB is the public release surface for the Controlled Prompt-Privacy Benchmark introduced in [BodhiPromptShield: Pre-Inference Prompt Mediation for Suppressing Privacy Propagation in LLM/VLM Agents](https://arxiv.org/abs/2604.05793).

This Hugging Face package intentionally releases the benchmark-authored prompt manifest and template-stratified train/dev/test split, not raw third-party prompts, source images, or end-to-end OCR assets. Each row is a controlled prompt stub with benchmark metadata that supports reproducible accounting, split-auditability, and benchmark discoverability.

## What Is Released

- 256 benchmark-authored prompt-manifest rows derived from 32 templates x 8 variants.
- Deterministic template-disjoint `train` / `dev` / `test` split: 128 / 64 / 64 rows.
- Prompt-family, privacy-category, subset, modality, and provenance fields needed to reconstruct the released benchmark card.
- Companion release notes and licensing/provenance manifests in the repository bundle.

## What Is Not Released

- Raw user prompts or third-party prompt payloads.
- Original OCR source assets, screenshots, or scanned documents.
- Licensed clinical notes or private operational logs.
- Exact multimodal regeneration assets beyond the released manifest surface.

## Dataset Structure

Main columns:

- `prompt_id`: unique prompt instance identifier.
- `template_id`: template identifier shared across the eight fixed variants.
- `variant_id`: one of `V1`-`V8`.
- `prompt_family`: one of Direct requests, Document-oriented, Retrieval-style, Tool-oriented agent.
- `prompt_source`: benchmark-authored source family.
- `downstream_task_type`: Prompt QA, Document QA, Retrieval QA, or Agent execution.
- `primary_privacy_category`: dominant protected-content category.
- `subset`: Essential-privacy or Incidental-privacy.
- `modality`: Text-only or OCR-mediated text-plus-image.
- `template_stub`: compact template-level description.
- `prompt_stub`: compact prompt-instance description.
- `split`: released split membership.

## Intended Use

- Benchmark accounting and public discoverability for the CPPB release surface.
- Template-disjoint train/dev/test selection for future detector or routing research.
- Evaluation protocol alignment with the BodhiPromptShield paper.

## Limitations

This package is a controlled benchmark manifest, not a full raw-prompt corpus. It should be interpreted as a benchmark-authored release card surface that preserves provenance, split semantics, and release boundaries. If you need end-to-end multimodal regeneration assets or licensed external benchmark inputs, use the repository protocols instead of this Hugging Face package.

## Citation

```bibtex
@article{ma2026bodhipromptshield,
  title={BodhiPromptShield: Pre-Inference Prompt Mediation for Suppressing Privacy Propagation in LLM/VLM Agents},
  author={Ma, Bo and Wu, Jinsong and Yan, Weiqi},
  journal={arXiv preprint arXiv:2604.05793},
  year={2026},
  url={https://arxiv.org/abs/2604.05793}
}
```

## Repository

- GitHub: https://github.com/mabo1215/BodhiPromptShield
- Paper: https://arxiv.org/abs/2604.05793
- Release source files: `src/experiments/cppb_*`
