# BodhiPromptShield

Pre-inference prompt mediation for suppressing privacy propagation in LLM/VLM agents, with the paper source, CPPB benchmark release surface, and reproducible experiment artifacts.

[![arXiv](https://img.shields.io/badge/arXiv-2604.05793-b31b1b.svg)](https://arxiv.org/abs/2604.05793)
[![Hugging Face Dataset](https://img.shields.io/badge/Hugging%20Face-Dataset-ffcc4d.svg)](https://huggingface.co/datasets/mabo1215/CPPB)
[![Hugging Face Paper](https://img.shields.io/badge/Hugging%20Face-Paper%20Page-f6b73c.svg)](https://huggingface.co/papers/2604.05793)
[![Artifacts](https://img.shields.io/badge/Artifacts-Released-2ea44f.svg)](https://github.com/mabo1215/BodhiPromptShield)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB.svg)](https://www.python.org/)
[![Benchmark](https://img.shields.io/badge/Benchmark-CPPB-0a7ea4.svg)](https://huggingface.co/datasets/mabo1215/CPPB)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Reproducibility](https://img.shields.io/badge/Reproducibility-Scripts%20%2B%20Manifests-2da44e.svg)](https://github.com/mabo1215/BodhiPromptShield)

English: [README.md](README.md) | 中文: [README.zh-CN.md](README.zh-CN.md)

BodhiPromptShield is the code and artifact repository for the paper "BodhiPromptShield: Pre-Inference Prompt Mediation for Suppressing Privacy Propagation in LLM/VLM Agents". The repository contains the paper source, reproducible experiment scripts, benchmark manifests, and figure-generation code used to support the released results.

## Quick Start

Install dependencies:

```bash
pip install -r src/requirements.txt
```

Run the lightweight reproducibility check:

```bash
python src/run_all.py
```

Build the CPPB manifest and Hugging Face-ready bundle:

```bash
python src/experiments/build_cppb_manifest.py
python src/experiments/build_cppb_source_manifest.py
python src/experiments/build_hf_cppb_dataset.py --clean
```

## Dataset / Paper / Citation

| Dataset | Paper | Citation |
| --- | --- | --- |
| CPPB benchmark release surface on Hugging Face.\n\nLink: https://huggingface.co/datasets/mabo1215/CPPB | Public arXiv preprint and Hugging Face paper page.\n\nArXiv: https://arxiv.org/abs/2604.05793\nPaper page: https://huggingface.co/papers/2604.05793 | Use the BibTeX entry in the Citation section below when citing the repository, dataset, or paper. |

## Status

- Paper status: public arXiv preprint.
- Dataset status: CPPB is publicly available on Hugging Face.
- Repository status: code, manifests, figures, and release-card materials are included in this repo.
- Reproducibility status: the repository provides runnable scripts for figure generation, benchmark manifests, and released artifact packaging.
- Benchmark status: CPPB is the released benchmark surface used by this repository and paper.
- License status: repository code and documentation are released under Apache License 2.0.
- License scope: third-party datasets, external assets, and other upstream materials remain subject to their own original terms.

## Repository Layout

- `src/`: experiment code, figure generation, benchmark manifests, and release utilities.
- `docs/`: revision notes and progress tracking.

## Usage

Generate paper figures:

```bash
python src/figures/run_all_figures.py --out-dir paper/figs
```

Build the CPPB benchmark manifests:

```bash
python src/experiments/build_cppb_manifest.py
python src/experiments/build_cppb_source_manifest.py
```

Build the Hugging Face-ready CPPB bundle:

```bash
python src/experiments/build_hf_cppb_dataset.py --clean
```

Upload a CPPB dataset bundle to Hugging Face:

```bash
python src/experiments/build_hf_cppb_dataset.py --clean --repo-id <your-hf-org-or-username>/CPPB --upload
```

For a more detailed inventory of reproducible scripts and generated artifacts, see `src/README.md`.

## CPPB Dataset

The Controlled Prompt-Privacy Benchmark (CPPB) released with this project is available on Hugging Face:

- https://huggingface.co/datasets/mabo1215/CPPB

The repository also includes the scripts used to assemble the released benchmark surface and Hugging Face package:

- `src/experiments/build_cppb_manifest.py`
- `src/experiments/build_cppb_source_manifest.py`
- `src/experiments/build_cppb_split_release.py`
- `src/experiments/build_hf_cppb_dataset.py`

## Citation

If you use this repository, the CPPB dataset, or the paper, cite:

```bibtex
@article{ma2026bodhipromptshield,
  title={BodhiPromptShield: Pre-Inference Prompt Mediation for Suppressing Privacy Propagation in LLM/VLM Agents},
  author={Ma, Bo and Wu, Jinsong and Yan, Weiqi},
  journal={arXiv preprint arXiv:2604.05793},
  year={2026},
  url={https://arxiv.org/abs/2604.05793}
}
```

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for the full text.

Third-party datasets, external assets, and benchmark source materials referenced by this repository may use different licenses or access terms and are not relicensed by this repository.

For a short notice covering third-party materials, see [NOTICE](NOTICE).

## Notes

- This repository releases code, manifests, and benchmark cards for the current public artifact surface.
- Some external data sources and exact regeneration assets remain intentionally out of scope for the public release, as described in the paper and release-card materials.