# BodhiPromptShield

面向 LLM/VLM agent 的推理前提示词隐私传播抑制框架，仓库包含论文源码、CPPB 基准发布面，以及可复现实验工件。

[![arXiv](https://img.shields.io/badge/arXiv-2604.05793-b31b1b.svg)](https://arxiv.org/abs/2604.05793)
[![Hugging Face Dataset](https://img.shields.io/badge/Hugging%20Face-Dataset-ffcc4d.svg)](https://huggingface.co/datasets/mabo1215/CPPB)
[![Hugging Face Paper](https://img.shields.io/badge/Hugging%20Face-Paper%20Page-f6b73c.svg)](https://huggingface.co/papers/2604.05793)
[![Artifacts](https://img.shields.io/badge/Artifacts-Released-2ea44f.svg)](https://github.com/mabo1215/BodhiPromptShield)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB.svg)](https://www.python.org/)
[![Benchmark](https://img.shields.io/badge/Benchmark-CPPB-0a7ea4.svg)](https://huggingface.co/datasets/mabo1215/CPPB)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Reproducibility](https://img.shields.io/badge/Reproducibility-Scripts%20%2B%20Manifests-2da44e.svg)](https://github.com/mabo1215/BodhiPromptShield)

English: [README.md](README.md) | 中文: [README.zh-CN.md](README.zh-CN.md)

BodhiPromptShield 是论文 "BodhiPromptShield: Pre-Inference Prompt Mediation for Suppressing Privacy Propagation in LLM/VLM Agents" 的代码与工件仓库，包含论文源文件、复现实验脚本、benchmark manifest 和图表生成代码。

## Quick Start

安装依赖：

```bash
pip install -r src/requirements.txt
```

运行轻量复现检查：

```bash
python src/run_all.py
```

构建 CPPB manifest 和 Hugging Face 数据集打包结果：

```bash
python src/experiments/build_cppb_manifest.py
python src/experiments/build_cppb_source_manifest.py
python src/experiments/build_hf_cppb_dataset.py --clean
```

## Dataset / Paper Citation

| Dataset | Paper | Citation |
| --- | --- | --- |
| CPPB 基准公开发布面已上传到 Hugging Face。\n\n链接：https://huggingface.co/datasets/mabo1215/CPPB | 论文已公开在 arXiv，并关联到 Hugging Face 论文页。\n\narXiv：https://arxiv.org/abs/2604.05793\nPaper page：https://huggingface.co/papers/2604.05793 | 引用仓库、数据集或论文时，可使用下方 Citation 段落中的 BibTeX。 |

## 状态

- 论文状态：已公开 arXiv 预印本。
- 数据集状态：CPPB 已公开发布到 Hugging Face。
- 仓库状态：代码、manifest、图表和 release-card 材料已包含在仓库中。
- 可复现性状态：仓库提供图表生成、benchmark manifest 和公开工件打包脚本。
- Benchmark 状态：CPPB 是当前仓库和论文使用的公开 benchmark 发布面。
- License 状态：仓库代码和文档采用 Apache License 2.0。
- License scope：第三方数据集、外部资产和其他上游材料仍然遵循各自原始许可或访问条款。

## 仓库结构

- `src/`: 实验代码、图表生成、benchmark manifest 和发布工具。
- `docs/`: 修订说明与进度跟踪。

## Usage

生成图表：

```bash
python src/figures/run_all_figures.py --out-dir paper/figs
```

生成 CPPB benchmark manifest：

```bash
python src/experiments/build_cppb_manifest.py
python src/experiments/build_cppb_source_manifest.py
```

生成 Hugging Face 可发布的 CPPB 数据集包：

```bash
python src/experiments/build_hf_cppb_dataset.py --clean
```

上传 CPPB 数据集到 Hugging Face：

```bash
python src/experiments/build_hf_cppb_dataset.py --clean --repo-id <your-hf-org-or-username>/CPPB --upload
```

更完整的脚本与工件说明见 `src/README.md`。

## CPPB Dataset

CPPB 数据集入口：

- https://huggingface.co/datasets/mabo1215/CPPB

仓库中与其对应的构建脚本包括：

- `src/experiments/build_cppb_manifest.py`
- `src/experiments/build_cppb_source_manifest.py`
- `src/experiments/build_cppb_split_release.py`
- `src/experiments/build_hf_cppb_dataset.py`

## Citation

如果你使用了本仓库、CPPB 数据集或论文，请引用：

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

本仓库采用 Apache License 2.0，完整文本见 [LICENSE](LICENSE)。

仓库引用的第三方数据集、外部资产和 benchmark 源材料可能适用不同的许可或访问条款，本仓库不会对其重新授权。

关于第三方材料的简短说明，见 [NOTICE](NOTICE)。

## 说明


- 本仓库公开的是当前可发布范围内的代码、manifest 和 benchmark card 工件。
- 部分外部数据源和精确再生成资产仍然不在当前公开范围内，具体边界见论文和 release-card 说明。