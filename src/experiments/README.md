# 当前论文实验数据说明

本目录当前保存的是与 prompt privacy mediation 论文直接对齐的实验结果 CSV，以及一个用于把这些结果回填进 `paper/main.tex` 的脚本。

## CSV 与论文表格的映射

- `cppb_accounting_summary.csv`
  - Table `tab:cppb_card`
  - Figure `cppb_benchmark_composition.png`
- `cppb_template_inventory.csv`
  - CPPB template inventory for benchmark accounting
- `cppb_prompt_manifest.csv`
  - Prompt-level CPPB manifest for benchmark accounting
- `cppb_distribution_breakdown.csv`
  - Exact count / percentage breakdown by subset, family, category, source, and modality
  - Figure `cppb_benchmark_composition.png`
- `artifact_metadata_notes.md`
  - Supplementary CPPB data-card and reproducibility notes for split semantics, multimodal slice membership, cross-model scope, and latency assumptions
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
- `categorywise_analysis.csv`
  - Appendix table `tab:catwise`
- `multimodal_analysis.csv`
  - Appendix table `tab:multimodal`
- `restoration_boundary_analysis.csv`
  - Appendix table `tab:restore`
  - Figure `restoration_ablation_tradeoffs.png`
- `sanitization_mode_ablation.csv`
  - Appendix table `tab:ablation`
  - Figure `restoration_ablation_tradeoffs.png`
- `multiseed_method_summary.csv`
  - Appendix table `tab:multiseed`
  - Figure `prompt_privacy_operating_points.png` error bars (method panel)
- `multiseed_policy_summary.csv`
  - Figure `prompt_privacy_operating_points.png` error bars (policy panel)
- `multiseed_method_prompt_logs.csv`
  - Prompt-level repeated-run records for method operating points
- `multiseed_policy_prompt_logs.csv`
  - Prompt-level repeated-run records for policy operating points
- `leavetemplateout_summary.csv`
  - Appendix table `tab:lto`
- `leavetemplateout_results.csv`
  - Held-out-template fold records for CPPB generalization
- `external_baseline_comparison.csv`
  - Appendix table `tab:baseline`
- `presidio_baseline_notes.txt`
  - Configuration note for the bundled Presidio-class comparator slice
- `tab_matched_baseline_protocol.json`
  - Protocol scaffold for TAB prompt-wrapper external transfer
- `tab_prompt_wrapped_manifest.csv`
  - Real TAB prompt-wrapper manifest generated from the public ECHR JSON files
- `i2b2_matched_baseline_protocol.json`
  - Protocol scaffold for i2b2 prompt-wrapper external transfer
- `i2b2_normalized_export_template.jsonl`
  - Template normalized export schema for user-supplied i2b2 notes

## 回填主文表格

执行：

```bash
python src/experiments/build_cppb_manifest.py
python src/experiments/categorywise_analysis.py
python src/experiments/multimodal_analysis.py
python src/experiments/multiseed_evaluation.py
python src/experiments/leavetemplateout_evaluation.py
python src/experiments/external_baseline_suite.py
python src/experiments/tab_external_transfer.py src/experiments/external_data/tab
python src/experiments/prepare_i2b2_normalized_export.py --template-only --output src/experiments/i2b2_normalized_export_template.jsonl
python src/experiments/i2b2_external_transfer.py
python src/experiments/fill_paper_tables.py --paper paper/main.tex
python src/experiments/fill_paper_tables.py --paper paper/appendix.tex
```

该脚本只会更新当前仓库中有明确 CSV 支撑的表格：

- `tab:cppb_card`
- `tab:per`
- `tab:utility`
- `tab:pi_sensitivity`
- `tab:propagation`
- `tab:latency`
- `tab:catwise`
- `tab:multimodal`
- `tab:restore`
- `tab:ablation`
- `tab:multiseed`
- `tab:lto`
- `tab:baseline`

它不会改动以下内容：

- 概念性或示意性表格，如 `tab:example`、`tab:tradeoff`
- 当前仓库尚未补齐自动生成脚本的表格，如 `tab:crossmodel`、`tab:hardcase`

## 诚实性说明

如果某个表格当前没有对应 CSV 或实验脚本，就不应在论文中被表述为“已由仓库代码自动再现”。这类表格应被视为：

- 手工整理的受控实验结果，或
- 说明性/概念性内容。
