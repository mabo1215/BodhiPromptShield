# 当前论文实验数据说明

本目录当前保存的是与 prompt privacy mediation 论文直接对齐的实验结果 CSV，以及一个用于把这些结果回填进 `paper/main.tex` 的脚本。

## CSV 与论文表格的映射

- `prompt_method_comparison.csv`
  - Table III `tab:per`
  - Table V `tab:utility`
  - Figure `prompt_privacy_operating_points.png`
- `policy_sensitivity.csv`
  - Table VIII `tab:pi_sensitivity`
  - Figure `prompt_privacy_operating_points.png`
- `agent_pipeline_metrics.csv`
  - Table XI `tab:propagation`
  - Figure `agent_propagation_curves.png`
  - Figure `agent_pipeline_summary.png`
- `latency_overhead.csv`
  - Table XII `tab:latency`
  - Figure `agent_pipeline_summary.png`

## 回填主文表格

执行：

```bash
python src/experiments/fill_paper_tables.py --paper paper/main.tex
```

该脚本只会更新当前仓库中有明确 CSV 支撑的表格：

- `tab:per`
- `tab:utility`
- `tab:pi_sensitivity`
- `tab:propagation`
- `tab:latency`

它不会改动以下内容：

- 概念性或示意性表格，如 `tab:example`、`tab:tradeoff`
- 当前仓库尚未补齐自动生成脚本的表格，如 `tab:catwise`、`tab:restore`、`tab:ablation`、`tab:multimodal`、`tab:crossmodel`、`tab:hardcase`

## 诚实性说明

如果某个表格当前没有对应 CSV 或实验脚本，就不应在论文中被表述为“已由仓库代码自动再现”。这类表格应被视为：

- 手工整理的受控实验结果，或
- 说明性/概念性内容。
