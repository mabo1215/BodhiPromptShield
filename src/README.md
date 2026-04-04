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
  - `cppb_source_licensing_manifest.csv`：CPPB 四类 prompt source 的 source-level provenance / licensing / OCR-count 结构化清单。
  - `external_resource_acquisition_card.md`：集中说明外部数据集、baseline repo、synthetic clinical route、OCR 引擎、open-weight runtime 和 closed-model 文档的官方获取路径与 access mode。
  - `external_baseline_runtime_manifest_template.csv`：TAB / i2b2 protocol-only semantic 和 named external baseline 的 runtime/disclosure 模板，现包含 Ollama + Llama3-8B-Instruct 的 public local zero-shot logging surface。
  - `tab_ollama_zero_shot_baseline.py`：执行本地 Ollama-backed TAB zero-shot pilot，并输出独立的 summary/detail/runtime/run-log 工件而不覆盖已发布的 full TAB heuristic slice。
  - `tab_ollama_zero_shot_results.csv` / `tab_ollama_zero_shot_document_metrics.csv` / `tab_ollama_zero_shot_runtime_manifest.csv` / `tab_ollama_zero_shot_run_log.csv`：本地 open-weight zero-shot baseline 的已执行 pilot 工件，当前对应 TAB `dev:32` 子集上的可检查 rerun。
  - `ollama_zero_shot_stability.py`：对 TAB / synthetic i2b2 的本地 Ollama zero-shot pilots 做多次重复运行、保存每次 snapshot，并生成 mean/std/CI stability 汇总。
  - `tab_ollama_zero_shot_stability_runs.csv` / `tab_ollama_zero_shot_stability_summary.csv`：TAB `dev:32` zero-shot pilot 的三次观测稳定性工件。
  - `ocr_engine_runtime_manifest_template.csv`：OCR-heavy transfer rerun所需的通用 OCR/version/host/preprocessing 模板。
  - `latency_host_manifest_template.csv`：latency slice 升级为 portable claim 前所需 host/runtime/scheduling 模板。
  - `latency_host_manifest.csv`：当前 `latency_overhead.csv` 对应的已填写 host/runtime/scheduling 记录，明确该 prototype latency slice 的实际本地执行环境。
  - `ocr_transfer_protocol.json`：OCR-heavy public transfer 的 tracking protocol，明确哪些 benchmark 已是 executed public slice、哪些仍处于 acquisition-tracked 状态。
  - `ocr_transfer_resource_manifest.csv`：CORD / FUNSD / SROIE / DocILE 的 acquisition-aware cache/status manifest，当前已区分 executed 与 scaffold-only benchmark。
  - `cppb_release_card.md`：集中说明 CPPB release scope、source provenance、annotation examples、external wrapper semantics 与已知缺口。
  - `ocr_slice_manifest.md`：说明 OCR-mediated slice 当前已知范围与仍缺失的 exact OCR / asset metadata。
  - `multimodal_provenance_card.md`：集中说明 multimodal slice 的构造来源、rendering boundary 与 OCR-facing provenance 缺口。
  - `crossmodel_portability_manifest.md`：说明匿名 cross-model portability slice 的证据边界与仍缺失的 backend provenance。
  - `latency_environment_manifest.md`：说明 latency 表的 prototype interpretation boundary 与仍缺失的 hardware/concurrency metadata。
  - `external_wrapper_release_card.md`：集中说明 TAB / i2b2 external wrapper 的 protocol invariants、comparator roster、落盘文件与 licensing boundary。
  - `acquire_external_resources.py`：生成 external dataset / baseline / provenance resource 的 machine-readable acquisition manifest，并可选缓存公开 GitHub 资源；当前也记录 i2b2-Synthea、CORD mirror/license 和 Ollama runtime surface。
  - `build_cppb_source_manifest.py`：从已发布的 template inventory 与 prompt manifest 生成 source-level CPPB provenance manifest。
  - `ocr_external_transfer.py`：基于 acquisition manifest 生成 OCR-heavy public transfer 的 protocol scaffold 与 benchmark availability manifest。
  - `tab_zero_shot_prompt_template.txt` / `i2b2_zero_shot_prompt_template.txt`：冻结 zero-shot semantic baselines 的固定 prompt surface，并被当前 TAB / synthetic i2b2 本地 Ollama pilots 直接复用。
  - `build_i2b2_synthea_synthetic_export.py`：把公开 i2b2-Synthea sample tables 转成 schema-compatible synthetic note export，用于无 licensed notes 时的 public rehearsal。
  - `i2b2_synthea_synthetic_export.jsonl`：基于公开 Synthea sample 构建的 synthetic i2b2-compatible note export。
  - `i2b2_synthea_prompt_wrapped_manifest.csv`：synthetic i2b2 export 在统一 wrapper 下的 prompt manifest。
  - `i2b2_ollama_zero_shot_baseline.py`：执行本地 Ollama-backed synthetic i2b2 zero-shot pilot，并输出独立的 summary/detail/runtime/run-log 工件。
  - `i2b2_ollama_zero_shot_results.csv` / `i2b2_ollama_zero_shot_document_metrics.csv` / `i2b2_ollama_zero_shot_runtime_manifest.csv` / `i2b2_ollama_zero_shot_run_log.csv`：synthetic i2b2-Synthea open-weight zero-shot baseline 的已执行 pilot 工件，当前对应 `synthea-dev:32` 子集。
  - `i2b2_ollama_zero_shot_stability_runs.csv` / `i2b2_ollama_zero_shot_stability_summary.csv`：synthetic i2b2 `synthea-dev:32` zero-shot pilot 的三次观测稳定性工件。
  - `acquire_cord_snapshot.py`：从 Hugging Face mirror 按固定 revision 下载并解包 CORD public snapshot，同时落盘 `cord_snapshot_manifest.json`。
  - `acquire_funsd_snapshot.py`：从 Hugging Face 按固定 revision 下载并固定 FUNSD public parquet snapshot，同时落盘 `funsd_snapshot_manifest.json`。
  - `acquire_sroie_snapshot.py`：从 Hugging Face 按固定 revision 下载并固定 SROIE public processed parquet snapshot，同时落盘 `sroie_snapshot_manifest.json`。
  - `build_cord_transfer_surface.py`：为 CORD 生成 benchmark-specific OCR rerun surface；若未提供完整数据快照，则诚实落盘 preparation-only 状态；当前也为 pinned snapshot 生成 wrapper manifest。
  - `cord_ocr_transfer_suite.py`：在 pinned public CORD snapshot 上执行 OCR-heavy matched rerun，并输出 result/detail/runtime/run-log 工件；当前 comparator roster 已扩到 Presidio 与 spaCy 两个 named OCR de-id family。
  - `funsd_ocr_transfer_suite.py`：在 pinned public FUNSD snapshot 上执行 OCR-heavy matched rerun，并输出 result/detail/runtime/run-log 工件；当前 comparator roster 也已补齐 Presidio 与 spaCy 两个 named OCR de-id family。
  - `sroie_ocr_transfer_suite.py`：在 pinned public SROIE processed snapshot 上执行第三个 OCR-heavy matched rerun，并输出 result/detail/runtime/run-log 工件。
  - `cord_snapshot_manifest.json`：记录 CORD public snapshot 的 fixed revision、下载 URL、archive SHA-256、解包路径与 split counts。
  - `funsd_snapshot_manifest.json`：记录 FUNSD public snapshot 的 fixed revision、本地 parquet snapshot root、split counts 与逐文件哈希。
  - `sroie_snapshot_manifest.json`：记录 SROIE public processed snapshot 的 fixed revision、本地 parquet snapshot root、split counts 与逐文件哈希。
  - `cord_ocr_runtime_manifest.csv`：已填写的 CORD OCR engine/version/runtime manifest，当前对应 `rapidocr-onnxruntime==1.2.3` 的本地执行面。
  - `funsd_ocr_runtime_manifest.csv`：已填写的 FUNSD OCR engine/version/runtime manifest，当前也对应 `rapidocr-onnxruntime==1.2.3` 的同一 declared OCR stack。
  - `sroie_ocr_runtime_manifest.csv`：已填写的 SROIE OCR engine/version/runtime manifest，当前同样对应 `rapidocr-onnxruntime==1.2.3` 的 declared OCR stack。
  - `cord_transfer_results.csv` / `cord_transfer_document_metrics.csv` / `cord_transfer_execution_manifest.csv` / `cord_transfer_run_log.csv` / `cord_transfer_protocol.json`：CORD `valid:100` OCR-heavy executed public slice 的结果、明细、执行状态、运行记录与协议工件；当前 summary 已同时包含 Presidio 与 spaCy 两个 named comparator。
  - `cord_transfer_preparation_manifest.csv`：记录 pinned CORD snapshot 的当前执行面，当前状态为 `executed_public_snapshot`。
  - `cord_prompt_wrapped_manifest.csv`：基于 pinned CORD snapshot 生成的 wrapper-ready manifest，当前对应 `valid:100` executed slice。
  - `funsd_transfer_results.csv` / `funsd_transfer_document_metrics.csv` / `funsd_transfer_execution_manifest.csv` / `funsd_transfer_run_log.csv` / `funsd_transfer_protocol.json`：FUNSD `test:50` OCR-heavy executed public slice 的结果、明细、执行状态、运行记录与协议工件；当前 summary 已同时包含 Presidio 与 spaCy 两个 named comparator。
  - `funsd_transfer_preparation_manifest.csv`：记录 pinned FUNSD snapshot 的当前执行面，当前状态为 `executed_public_snapshot`。
  - `funsd_prompt_wrapped_manifest.csv`：基于 pinned FUNSD snapshot 生成的 wrapper-ready manifest，当前对应 `test:50` executed slice。
  - `sroie_transfer_results.csv` / `sroie_transfer_document_metrics.csv` / `sroie_transfer_execution_manifest.csv` / `sroie_transfer_run_log.csv` / `sroie_transfer_protocol.json`：SROIE `test:63` OCR-heavy executed public slice 的结果、明细、执行状态、运行记录与协议工件。
  - `sroie_transfer_preparation_manifest.csv`：记录 pinned SROIE processed snapshot 的当前执行面，当前状态为 `executed_public_snapshot`。
  - `sroie_prompt_wrapped_manifest.csv`：基于 pinned SROIE processed snapshot 生成的 wrapper-ready manifest，当前对应 `test:63` executed slice。
  - `prompt_method_comparison.csv`：主文方法级对比结果，用于 Table III（PER）、Table V（AC/TSR）以及主文 operating-points 图。
  - `policy_sensitivity.csv`：主文 policy sensitivity 结果，用于 Table VIII 和 operating-points 图。
  - `agent_pipeline_metrics.csv`：主文 multi-step propagation 结果，用于 Table XI、主文 propagation 曲线和附录 deployment 图。
  - `latency_overhead.csv`：主文 latency 结果，用于 Table XII 和附录 deployment 图。
  - `categorywise_analysis.csv`：附录 `tab:catwise` 的 category-wise supporting artifact。
  - `multimodal_analysis.csv`：附录 `tab:multimodal` 的 OCR-mediated supporting artifact。
  - `crossmodel_analysis.py`：生成附录 `tab:crossmodel` 的 alias-level portability supporting artifact 与 runtime log。
  - `crossmodel_portability_results.csv`：附录 `tab:crossmodel` 的 portability supporting artifact。
  - `crossmodel_runtime_log.csv`：cross-model portability slice 的 alias-level runtime log。
  - `crossmodel_named_rerun_manifest_template.csv`：把 alias-level portability slice 升级为 named rerun 时所需的最小 provenance 字段模板。
  - `hardcase_analysis.py`：生成附录 `tab:hardcase` 的 deterministic hard-case supporting artifact。
  - `hardcase_analysis.csv`：附录 `tab:hardcase` 的 hard-case supporting artifact。
  - `restoration_boundary_analysis.csv`：附录 restoration boundary supporting table 与 supporting figure 的记录文件。
  - `sanitization_mode_ablation.csv`：附录 sanitization-mode ablation supporting table 与 supporting figure 的记录文件。
  - `multiseed_evaluation.py`：生成 method / policy operating-point 的多随机种子稳定性记录、汇总 CSV 和 prompt-level logs。
  - `multiseed_method_summary.csv`：附录 repeated-run stability 表，并为主文 operating-points 图提供误差线。
  - `multiseed_policy_summary.csv`：policy profile repeated-run stability 汇总，并为主文 operating-points 图提供误差线。
  - `leavetemplateout_evaluation.py`：生成 CPPB leave-template-out 泛化结果与汇总表。
  - `leavetemplateout_summary.csv`：附录 held-out-template generalization 表。
  - `external_baseline_comparison.csv`：附录 Presidio-class external baseline comparison 表。
  - `presidio_baseline_notes.txt`：附录外部基线配置说明。
  - `tab_matched_baseline_protocol.json`：TAB text anonymization external transfer 的 matched baseline protocol scaffold。
  - `tab_prompt_wrapped_manifest.csv`：基于公开 TAB ECHR JSON 生成的首个 prompt-wrapper manifest。
  - `tab_matched_baseline_suite.py`：运行扩展后的 TAB matched baselines，并生成结果 CSV 与 execution manifest。
  - `tab_transfer_results.csv`：附录 `tab:tabtransfer` 的扩展 comparator public-transfer 结果表。
  - `tab_transfer_document_metrics.csv`：TAB 文档级 matched-baseline 指标明细。
  - `tab_transfer_execution_manifest.csv`：TAB comparator roster 的 execution-status 记录。
  - `tab_transfer_run_log.csv`：TAB wrapper 当前一次 released rerun 的原始运行记录。
  - `i2b2_matched_baseline_protocol.json`：i2b2 clinical de-identification external transfer 的 matched baseline protocol scaffold。
  - `prepare_i2b2_normalized_export.py`：把用户自有的 i2b2 XML/TXT 或 JSON/JSONL 导出规范化为 clinical transfer 所需 schema 的工具。
  - `i2b2_matched_baseline_suite.py`：在用户提供 licensed normalized export 时运行 i2b2 matched baselines；无数据时只写 execution manifest。
  - `i2b2_transfer_execution_manifest.csv`：i2b2 comparator roster 的 execution-status 记录。
  - `i2b2_transfer_run_log.csv`：i2b2 wrapper 当前 waiting/executed 状态的原始运行记录。
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
- 附录 `tab:catwise`
- 附录 `tab:multimodal`
- 附录 `tab:crossmodel`
- 附录 `tab:hardcase`
- 附录 `tab:multiseed`
- 附录 `tab:lto`
- 附录 `tab:baseline`
- 附录 `tab:tabtransfer`
- 附录 `restoration_ablation_tradeoffs.png`

此外，release-card 与 manifest 类说明文件现在也可直接支撑论文中的 reproducibility / scope 边界表述，但它们不构成新的实验结果表。

其余表格目前仍属于：

- 概念性或示意性内容，例如 Table I、Table II；
- 或当前仓库中尚未补齐完整生成脚本的手工整理结果。

## 推荐命令

- 生成论文图：
  - `python src/figures/run_all_figures.py --out-dir paper/figs`
- 生成 CPPB benchmark accounting 工件：
  - `python src/experiments/build_cppb_manifest.py`
- 生成 CPPB source-level provenance 工件：
  - `python src/experiments/build_cppb_source_manifest.py`
- 生成 category-wise supporting artifact：
  - `python src/experiments/categorywise_analysis.py`
- 生成 multimodal supporting artifact：
  - `python src/experiments/multimodal_analysis.py`
- 生成 cross-model portability supporting artifact：
  - `python src/experiments/crossmodel_analysis.py`
- 生成 hard-case supporting artifact：
  - `python src/experiments/hardcase_analysis.py`
- 生成 multi-seed 稳定性工件：
  - `python src/experiments/multiseed_evaluation.py`
- 生成 leave-template-out 泛化工件：
  - `python src/experiments/leavetemplateout_evaluation.py`
- 生成 external baseline comparison 工件：
  - `python src/experiments/external_baseline_suite.py`
- 生成 TAB / i2b2 external transfer protocol scaffold：
  - `python src/experiments/tab_external_transfer.py src/experiments/external_data/tab`
  - `python src/experiments/tab_matched_baseline_suite.py`
  - `python src/experiments/prepare_i2b2_normalized_export.py --template-only --output src/experiments/i2b2_normalized_export_template.jsonl`
  - `python src/experiments/i2b2_external_transfer.py`
  - `python src/experiments/i2b2_matched_baseline_suite.py <normalized_i2b2_export.jsonl>`
- 生成 external dataset / baseline acquisition manifest：
  - `python src/experiments/acquire_external_resources.py`
- 生成 OCR-heavy transfer scaffold：
  - `python src/experiments/ocr_external_transfer.py`
- 固定并执行 CORD OCR-heavy public slice：
  - `python src/experiments/acquire_cord_snapshot.py`
  - `python src/experiments/cord_ocr_transfer_suite.py --dataset-root src/experiments/external_data/resource_cache/cord_dataset/hf_snapshot/4f51527df44a7f7f915bee494f1129915118d0e1/extracted/CORD --split valid`
- 用 CSV 回填主文中已代码支撑的表格：
  - `python src/experiments/fill_paper_tables.py --paper paper/main.tex`
- 用 CSV 回填附录中已代码支撑的表格：
  - `python src/experiments/fill_paper_tables.py --paper paper/appendix.tex`
- 运行仓库内轻量代码检查：
  - `python src/run_all.py`

## 依赖

见 `src/requirements.txt`。当前图形脚本依赖 `numpy`、`matplotlib`；OCR-heavy CORD rerun 另外使用 `rapidocr-onnxruntime`。
