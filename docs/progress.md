# 论文进度

最后更新：2026-04-03

## 已全部修改

- 已重新按当前 revision cycle 收口进度文件；修改说明：本文件现统一整理为 `## 已全部修改` 与 `## 未修改或部分修改` 两大块，删除了旧版按轮次堆叠、前后重复和状态互相冲突的写法。
- 已统一主文与附录的问题定义与符号体系；修改说明：`paper/main.tex` 与 `paper/appendix.tex` 已把问题表述统一到 agent-boundary graph、policy profile、direct exposure / propagation risk / utility 这一条主线，不再出现引言、方法、附录 notation 各写各的情况。
- 已完成主文证据结构收口；修改说明：主文现在集中保留 `tab:cppb_card`、`tab:per`、`tab:utility`、`tab:pi_sensitivity`、`tab:propagation`、`tab:latency` 等 backbone evidence，`tab:restore`、`tab:ablation`、`tab:multimodal`、`tab:crossmodel`、`tab:catwise`、`tab:hardcase` 等 supporting slices 已下沉到 appendix。
- 已完成 CPPB benchmark accounting 工件建设；修改说明：仓库现已包含 `src/experiments/build_cppb_manifest.py`、`cppb_template_inventory.csv`、`cppb_prompt_manifest.csv`、`cppb_distribution_breakdown.csv`、`cppb_accounting_summary.csv`，正文中的 benchmark card 已可由仓库工件直接支撑。
- 已完成主文 benchmark card 回填；修改说明：`src/experiments/fill_paper_tables.py` 已支持 `tab:cppb_card <- cppb_accounting_summary.csv`，主文中 CPPB 的 prompt / template / subset / family / category / modality 统计已不再依赖手写描述。
- 已把 restoration boundary 与 sanitization mode 两组 supporting slices 升级为 repo-backed artifact；修改说明：仓库已新增 `src/experiments/restoration_boundary_analysis.csv` 与 `src/experiments/sanitization_mode_ablation.csv`，`paper/appendix.tex` 中的 `tab:restore` 与 `tab:ablation` 现在由 `src/experiments/fill_paper_tables.py` 自动回填。
- 已完成 supporting figure 升级；修改说明：仓库已新增 `src/figures/restoration_ablation_tradeoffs.py` 与 `paper/figs/restoration_ablation_tradeoffs.png`，附录已纳入 restoration timing 和 sanitization mode 的 trade-off figure，而不再只保留静态表格。
- 已完成 Windows 下独立论文构建脚本修复；修改说明：`paper/build.bat` 现使用 `pdflatex -> bibtex(按需) -> pdflatex -> pdflatex` 独立构建 `main` 与 `appendix`，中间文件输出到 `paper/build/`，成功后自动复制 `main.pdf` 与 `appendix.pdf` 回 `paper/` 根目录。
- 已完成摘要与主文投稿口径收紧；修改说明：摘要已重组为 Problem / Approach / Key Result / Scope 四步结构，正文中 `this revision`、`current revision`、`next revision` 等过程化措辞已清理，limitations 与 conclusion 也已改为更适合投稿稿的 evidence-bounded 表达。
- 已完成可复现性说明更新；修改说明：`paper/appendix.tex` 已同步写明仓库当前包含 deterministic CPPB manifest/accounting 工件，并更新 artifact-to-script reproducibility map，使 benchmark card、restore/ablation supporting artifacts 与 supporting figure 的脚本来源可检查。
- 已完成外部强基线补充；修改说明：仓库已新增 `src/experiments/external_baseline_suite.py`、`external_baseline_comparison.csv` 与 `presidio_baseline_notes.txt`，附录新增 `tab:baseline` 展示 Presidio regex-only、Presidio+NER 与 BodhiPromptShield 的对比结果。
- 已完成 adversarial robustness suite；修改说明：仓库已新增 `src/experiments/adversarial_robustness_suite.py`、`adversarial_robustness_results.csv`、`adversarial_attack_inventory.csv`，附录新增 `tab:adversarial`，threat model 与实际实验切片现在已有 repository-backed supporting evidence 对应。
- 已完成 multi-seed robustness artifact；修改说明：仓库已新增 `src/experiments/multiseed_evaluation.py`，并产出 `multiseed_method_prompt_logs.csv`、`multiseed_method_seed_metrics.csv`、`multiseed_method_summary.csv`、`multiseed_policy_prompt_logs.csv`、`multiseed_policy_seed_metrics.csv`、`multiseed_policy_summary.csv`，相关结果已接入论文表格与图表。
- 已完成 leave-template-out generalization artifact；修改说明：仓库已新增 `src/experiments/leavetemplateout_evaluation.py`，并产出 `leavetemplateout_results.csv` 与 `leavetemplateout_summary.csv`，附录中对应 generalization slice 已从“Not yet integrated”更新为“Record-backed”。
- 已完成表格回填脚本扩展与修复；修改说明：`src/experiments/fill_paper_tables.py` 现已支持 `tab:multiseed` 与 `tab:lto`，并已修复新表头字符串换行导致的 LaTeX `\midrule` 错位问题。
- 已完成 operating-points figure 升级；修改说明：`src/figures/prompt_privacy_operating_points.py` 现可读取 multi-seed summary，在 `paper/figs/prompt_privacy_operating_points.png` 中显示 95% CI error bars。
- 已完成主文与附录对 multi-seed / leave-template-out 的口径更新；修改说明：`paper/main.tex` 已新增 repeated-run 与 leave-template-out 的结果解读，`paper/appendix.tex` 已新增并回填 `tab:multiseed` 与 `tab:lto`，相关 roadmap 状态已改为 `Record-backed`。
- 已完成主文与附录引用及编译问题修复；修改说明：已移除主文对附录专属 label 的直接引用，避免 split build 下的 undefined reference；最新 `paper/build.bat` 已验证 `paper/main.pdf` 与 `paper/appendix.pdf` 可以成功生成。
- 已完成文档同步；修改说明：`src/README.md` 与 `src/experiments/README.md` 已补入 CPPB manifest/accounting、新实验脚本、表格映射与生成命令，使仓库文档与当前论文状态一致。
- 已完成 Presidio-class external baseline table 自动回填；修改说明：`src/experiments/fill_paper_tables.py` 已新增 `tab:baseline <- external_baseline_comparison.csv`，`paper/appendix.tex` 中的外部基线表不再是纯手写 manuscript slice，而是由 bundled comparison CSV 自动重建的 record-backed supporting artifact。
- 已补充 artifact metadata / data-card 说明；修改说明：仓库已新增 `src/experiments/artifact_metadata_notes.md`，补入 CPPB split semantics、annotation/label 语义、multimodal slice scope 与 latency interpretation notes，主文与附录中的 reproducibility scope 已同步更新。

## 未修改或部分修改

- 更强的 external practical baseline family 仍未全部补齐；修改说明：当前 Presidio 风格基线已从受控附录表升级为 record-backed supporting artifact，但 prompted LLM zero-shot de-identification、更多 enterprise-grade 或更通用的 external pipeline 仍未做 matched benchmark；未全部修改原因：本轮优先把已存在 comparator slice 升级为可检查工件，而不是继续扩展新的基线家族；后续准备如何修改：仅在保持同一 CPPB protocol 和相同 evaluation slice 的前提下再补更强外部基线。
- 部分 controlled manuscript supporting tables 仍未实现 end-to-end public regeneration；修改说明：`tab:multimodal`、`tab:crossmodel`、`tab:catwise`、`tab:hardcase` 目前仍主要是 manuscript-level controlled slices，尚未全部提升为像 `tab:restore`、`tab:ablation`、`tab:multiseed`、`tab:lto` 这样的 repo-backed artifact；未全部修改原因：这些切片对当前主结论的重要性低于 backbone evidence 与 robustness/generalization 缺口；后续准备如何修改：继续按“先高价值 supporting slice、后低优先级 appendix slice”的顺序逐个转成 CSV + script + table fill pipeline。
- 外部 transfer 与更强 external validation 仍未完成；修改说明：当前论文仍主要基于 CPPB 与 controlled evaluation，尚未新增 public benchmark transfer 或 truly independent external validation；未修改原因：仓库内暂无与当前任务精确匹配、可诚实支撑结论边界的外部 benchmark；后续准备如何修改：优先寻找 protocol-compatible benchmark，若没有就继续维持 evidence-bounded scope 而不伪造 external validation。
- 可复现性元数据仍有剩余缺口；修改说明：本轮已补 `artifact_metadata_notes.md`，把 split semantics、multimodal slice scope 与 latency interpretation 写入仓库，但 cross-model 结果仍缺 exact backbone identifiers / config logs，multimodal slice 仍缺 exact OCR engine/version manifest，latency 仍缺 hardware-specific host manifest；未全部修改原因：这些是重要但不改变主要结论的 metadata completeness 问题，且当前公开快照并不包含足够原始运行日志去诚实恢复全部精确标识；后续准备如何修改：在下一轮把剩余 metadata 缺口继续整理成独立 manifest 或完整 rerun artifact。
- CPPB data-card 仍可继续补强；修改说明：当前 prompt-level inventory、distribution breakdown、accounting summary 与新增的 artifact metadata note 已补入 split/label 语义，但 source-level release metadata、annotation examples 与更完整 multimodal provenance 仍不完整；未全部修改原因：本轮优先补可直接支撑论文口径的 data-card 核心字段，而不是一次性扩成完整 benchmark package；后续准备如何修改：继续补 fuller data-card documentation，并与 appendix 中的 reproducibility scope 对齐。
- 论文版式仍有少量非致命 warning；修改说明：当前 `paper/main.pdf` 与 `paper/appendix.pdf` 已能稳定编译，但仍有 underfull / overfull box 级别的排版提示；未全部修改原因：这些问题不会阻塞当前 revision cycle 完成；后续准备如何修改：下一轮在不打乱证据结构的前提下，再做局部表格、caption 与段落长度的排版收紧。
