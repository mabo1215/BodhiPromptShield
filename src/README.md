# PromptShield 论文配套代码

当前仓库中的 `src/` 只应被理解为当前 prompt privacy mediation 论文的可复现辅助代码，而不是整篇论文所有实验的完整训练流水线。为避免过度声称，下面按“当前仍直接服务于论文”的内容说明。

## 目录说明

- `experiments/`
  - `prompt_method_comparison.csv`：主文方法级对比结果，用于 Table III（PER）、Table V（AC/TSR）以及主文 operating-points 图。
  - `policy_sensitivity.csv`：主文 policy sensitivity 结果，用于 Table VIII 和 operating-points 图。
  - `agent_pipeline_metrics.csv`：主文 multi-step propagation 结果，用于 Table XI、主文 propagation 曲线和附录 deployment 图。
  - `latency_overhead.csv`：主文 latency 结果，用于 Table XII 和附录 deployment 图。
  - `fill_paper_tables.py`：把上述 CSV 回填到 `paper/main.tex` 中对应的代码支撑表格。
- `figures/`
  - `prompt_privacy_operating_points.py`：生成主文 `prompt_privacy_operating_points.png`。
  - `agent_propagation_curves.py`：生成主文 `agent_propagation_curves.png`。
  - `agent_pipeline_summary.py`：生成附录 `agent_pipeline_summary.png`。
  - `run_all_figures.py`：统一生成当前论文图以及仓库中保留的旧图文件。
- `algorithms/`
  - 当前只保留轻量示例/烟雾测试代码，不应被表述为主文所有实验结果的直接来源。

## 当前可由代码直接支撑的论文内容

- 主文 Table III `tab:per`
- 主文 Table V `tab:utility`
- 主文 Table VIII `tab:pi_sensitivity`
- 主文 Table XI `tab:propagation`
- 主文 Table XII `tab:latency`
- 主文 `prompt_privacy_operating_points.png`
- 主文 `agent_propagation_curves.png`
- 附录 `agent_pipeline_summary.png`

其余表格目前仍属于：

- 概念性或示意性内容，例如 Table I、Table II、Table XIV；
- 或当前仓库中尚未补齐完整生成脚本的手工整理结果。

## 推荐命令

- 生成论文图：
  - `python src/figures/run_all_figures.py --out-dir paper/fig`
- 用 CSV 回填主文中已代码支撑的表格：
  - `python src/experiments/fill_paper_tables.py --paper paper/main.tex`
- 运行仓库内轻量代码检查：
  - `python src/run_all.py`

## 依赖

见 `src/requirements.txt`。当前图形脚本依赖 `numpy`、`matplotlib`，其余脚本仅使用 Python 标准库或轻量数值库。
