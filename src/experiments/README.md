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
- `external_resource_acquisition_card.md`
  - Consolidated note for official public/resource-gated access paths, acquisition modes, and the boundary between acquisition metadata and executed evidence
- `external_resource_acquisition_manifest.json`
  - Machine-readable registry of official external dataset, baseline, OCR-engine, and model-documentation access paths
- `ocr_transfer_protocol.json`
  - Protocol scaffold for OCR-heavy public transfer under the same wrapper discipline used for TAB and i2b2
- `ocr_transfer_resource_manifest.csv`
  - Acquisition-aware cache/status manifest for CORD, FUNSD, SROIE, and DocILE OCR-heavy transfer targets
- `cppb_release_card.md`
  - Consolidated benchmark-card note for release scope, provenance, annotation examples, and wrapper semantics
- `ocr_slice_manifest.md`
  - Explicit evidence boundary for the OCR-mediated slice and its remaining regeneration gaps
- `multimodal_provenance_card.md`
  - Consolidated multimodal slice provenance note covering construction, rendering boundary, and missing OCR/source-asset metadata
- `crossmodel_portability_manifest.md`
  - Explicit evidence boundary for the anonymous cross-model portability slice
- `external_wrapper_release_card.md`
  - Consolidated wrapper/data-card note for TAB and i2b2 public-transfer protocols, rosters, outputs, and licensing boundaries
- `latency_environment_manifest.md`
  - Explicit evidence boundary for prototype latency measurements
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
- `crossmodel_portability_results.csv`
  - Appendix table `tab:crossmodel`
- `crossmodel_runtime_log.csv`
  - Alias-level runtime log for the appendix cross-model portability slice
- `crossmodel_named_rerun_manifest_template.csv`
  - Template for promoting the appendix cross-model slice from alias-level reporting to a named rerun with full provenance
- `hardcase_analysis.csv`
  - Appendix table `tab:hardcase`
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
- `tab_transfer_results.csv`
  - Appendix table `tab:tabtransfer`
- `tab_transfer_document_metrics.csv`
  - Per-document TAB transfer metrics emitted by the lightweight matched-baseline runner
- `tab_transfer_execution_manifest.csv`
  - Execution-status record for the current TAB comparator roster
- `tab_transfer_run_log.csv`
  - Raw rerun record for the current TAB wrapper roster, input scope, and generated outputs
- `i2b2_matched_baseline_protocol.json`
  - Protocol scaffold for i2b2 prompt-wrapper external transfer
- `i2b2_normalized_export_template.jsonl`
  - Template normalized export schema for user-supplied i2b2 notes
- `i2b2_transfer_execution_manifest.csv`
  - Execution-status record for the current i2b2 comparator roster
- `i2b2_transfer_run_log.csv`
  - Raw rerun record for the current i2b2 wrapper roster and waiting/executed clinical state

## 回填主文表格

执行：

```bash
python src/experiments/build_cppb_manifest.py
python src/experiments/categorywise_analysis.py
python src/experiments/multimodal_analysis.py
python src/experiments/crossmodel_analysis.py
python src/experiments/hardcase_analysis.py
python src/experiments/multiseed_evaluation.py
python src/experiments/leavetemplateout_evaluation.py
python src/experiments/external_baseline_suite.py
python src/experiments/tab_external_transfer.py src/experiments/external_data/tab
python src/experiments/tab_matched_baseline_suite.py
python src/experiments/prepare_i2b2_normalized_export.py --template-only --output src/experiments/i2b2_normalized_export_template.jsonl
python src/experiments/i2b2_external_transfer.py
python src/experiments/i2b2_matched_baseline_suite.py
python src/experiments/acquire_external_resources.py
python src/experiments/ocr_external_transfer.py
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
- `tab:crossmodel`
- `tab:hardcase`
- `tab:restore`
- `tab:ablation`
- `tab:multiseed`
- `tab:lto`
- `tab:baseline`
- `tab:tabtransfer`

它不会改动以下内容：

- 概念性或示意性表格，如 `tab:example`、`tab:tradeoff`
- 纯说明性 appendix 内容，如 `tab:app-concept-example`、`tab:app-regimes`、`tab:app-examples`

## 诚实性说明

如果某个表格当前没有对应 CSV 或实验脚本，就不应在论文中被表述为“已由仓库代码自动再现”。这类表格应被视为：

- 手工整理的受控实验结果，或
- 说明性/概念性内容。

同时，release-card / manifest 类文件主要用于界定证据边界与可复现性范围；它们不是新的 benchmark 结果，不应被误读为额外实验得分。

对于 public OCR/document benchmarks、baseline repositories、request-gated clinical corpora，以及 closed-model documentation 的官方访问入口，优先通过 `acquire_external_resources.py` 生成当前 acquisition manifest，再通过 `ocr_external_transfer.py` 把 OCR-heavy 目标整理成 protocol/availability scaffold；只有在 wrapper 对齐、runtime logging 和结果文件落盘后，这些资源才应被提升为论文中的 executed evidence。
