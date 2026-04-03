# PromptShield 论文配套代码

当前仓库中的 `src/` 只是可复现代码，未完成整篇论文所有实验的完整训练流水线。

## 目录说明

- `experiments/`
  - `build_cppb_manifest.py`：生成 CPPB 的 template inventory、prompt-level manifest，以及主文 benchmark accounting 表所需的汇总 CSV。
  - `cppb_accounting_summary.csv`：主文 `tab:cppb_card` 的精确 benchmark accounting，并参与附录 `cppb_benchmark_composition.png` 的汇总说明。
  - `cppb_template_inventory.csv`：CPPB template 级清单。
  - `cppb_prompt_manifest.csv`：CPPB prompt 级 manifest。
  - `cppb_distribution_breakdown.csv`：CPPB 在 subset / family / category / source / modality 维度上的精确计数与占比，并支撑附录 `cppb_benchmark_composition.png`。
  - `artifact_metadata_notes.md`：补充 CPPB data-card、split 语义、multimodal slice、cross-model portability 与 latency assumptions 的仓库说明。
  - `prompt_method_comparison.csv`：主文方法级对比结果，用于 Table III（PER）、Table V（AC/TSR）以及主文 operating-points 图。
  - `policy_sensitivity.csv`：主文 policy sensitivity 结果，用于 Table VIII 和 operating-points 图。
  - `agent_pipeline_metrics.csv`：主文 multi-step propagation 结果，用于 Table XI、主文 propagation 曲线和附录 deployment 图。
  - `latency_overhead.csv`：主文 latency 结果，用于 Table XII 和附录 deployment 图。
  - `restoration_boundary_analysis.csv`：附录 restoration boundary supporting table 与 supporting figure 的记录文件。
  - `sanitization_mode_ablation.csv`：附录 sanitization-mode ablation supporting table 与 supporting figure 的记录文件。
  - `multiseed_evaluation.py`：生成 method / policy operating-point 的多随机种子稳定性记录、汇总 CSV 和 prompt-level logs。
  - `multiseed_method_summary.csv`：附录 repeated-run stability 表，并为主文 operating-points 图提供误差线。
  - `multiseed_policy_summary.csv`：policy profile repeated-run stability 汇总，并为主文 operating-points 图提供误差线。
  - `leavetemplateout_evaluation.py`：生成 CPPB leave-template-out 泛化结果与汇总表。
  - `leavetemplateout_summary.csv`：附录 held-out-template generalization 表。
  - `external_baseline_comparison.csv`：附录 Presidio-class external baseline comparison 表。
  - `presidio_baseline_notes.txt`：附录外部基线配置说明。
  - `fill_paper_tables.py`：把上述 CSV 回填到 `paper/main.tex` 与 `paper/appendix.tex` 中对应的代码支撑表格。
- `figures/`
  - `prompt_privacy_operating_points.py`：生成主文 `prompt_privacy_operating_points.png`。
  - `agent_propagation_curves.py`：生成主文 `agent_propagation_curves.png`。
  - `agent_pipeline_summary.py`：生成附录 `agent_pipeline_summary.png`。
  - `cppb_benchmark_composition.py`：生成附录 `cppb_benchmark_composition.png`。
  - `restoration_ablation_tradeoffs.py`：生成附录 `restoration_ablation_tradeoffs.png`。
  - `run_all_figures.py`：统一生成当前论文图以及仓库中保留的旧图文件。
- `algorithms/`
  - 当前只保留轻量示例/烟雾测试代码，不应被表述为主文所有实验结果的直接来源。

## 当前可由代码直接支撑的论文内容

- 主文 Table III `tab:per`
- 主文 Table V `tab:utility`
- 主文 Table VIII `tab:pi_sensitivity`
- 主文 Table XI `tab:propagation`
- 主文 Table XII `tab:latency`
- 主文 `tab:cppb_card`
- 主文 `prompt_privacy_operating_points.png`
- 主文 `agent_propagation_curves.png`
- 附录 `agent_pipeline_summary.png`
- 附录 `cppb_benchmark_composition.png`
- 附录 `tab:restore`
- 附录 `tab:ablation`
- 附录 `tab:multiseed`
- 附录 `tab:lto`
- 附录 `tab:baseline`
- 附录 `restoration_ablation_tradeoffs.png`

其余表格目前仍属于：

- 概念性或示意性内容，例如 Table I、Table II、Table XIV；
- 或当前仓库中尚未补齐完整生成脚本的手工整理结果。

## 推荐命令

- 生成论文图：
  - `python src/figures/run_all_figures.py --out-dir paper/figs`
- 生成 CPPB benchmark accounting 工件：
  - `python src/experiments/build_cppb_manifest.py`
- 生成 multi-seed 稳定性工件：
  - `python src/experiments/multiseed_evaluation.py`
- 生成 leave-template-out 泛化工件：
  - `python src/experiments/leavetemplateout_evaluation.py`
- 生成 external baseline comparison 工件：
  - `python src/experiments/external_baseline_suite.py`
- 用 CSV 回填主文中已代码支撑的表格：
  - `python src/experiments/fill_paper_tables.py --paper paper/main.tex`
- 用 CSV 回填附录中已代码支撑的表格：
  - `python src/experiments/fill_paper_tables.py --paper paper/appendix.tex`
- 运行仓库内轻量代码检查：
  - `python src/run_all.py`

## 依赖

见 `src/requirements.txt`。当前图形脚本依赖 `numpy`、`matplotlib`，其余脚本仅使用 Python 标准库或轻量数值库。
