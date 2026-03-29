# 论文进度

最后更新：2026-03-29  
当前目标：继续按 `docs/revision_suggestions.tex` 自动收紧 `paper/`；本轮优先统一 problem formulation，把正文主线稳定到 “pre-inference agent-boundary mediation as propagation-control”，再把最值钱的 supporting experiment/table/figure 往 repo-backed artifact 推进一步。

---

## 本轮已完成

- 已将 `paper/build.bat` 改为可独立运行的 Windows 构建脚本，不再依赖 `latexmk`/`perl`，而是直接执行 `pdflatex -> bibtex(按需) -> pdflatex -> pdflatex`，将中间文件与 PDF 输出到 `paper/build/`，并把最终 `main.pdf`、`appendix.pdf` 自动复制回 `paper/`。

- 已把 problem formulation 从 Introduction、Section II、Section IV 到 appendix notation 统一成同一条主线，而不再是“引言讲 propagation、问题定义像一般去标识化、方法再单独讲 policy”的分裂结构：
  - `paper/main.tex` 现在把问题定义明确写成 agent-boundary graph 上的 propagation-control problem
  - 问题对象统一为 `T_{\pi}`、`\Pi_{\pi}`、`\rho`、`K`
  - 设计目标不再只是 document-boundary 的 `privacy + utility`，而是统一成 `direct exposure + propagation risk + utility`
  - policy profile 现在明确是 `lenient / balanced / strict` 三种实例化，而不是只把 `\Pi` 写成抽象选择器
  - `paper/appendix.tex` 的 notation 与算法伪代码也已同步到相同符号体系

- 已把一个高价值 supporting slice 从“附录手填结果”推进到“仓库可回填、可作图、可编译验证”的 repo-backed artifact：
  - 新增 `src/experiments/restoration_boundary_analysis.csv`
  - 新增 `src/experiments/sanitization_mode_ablation.csv`
  - `src/experiments/fill_paper_tables.py` 现在不仅能回填 `paper/main.tex`，也能回填 `paper/appendix.tex`
  - `paper/appendix.tex` 中的 `tab:restore`、`tab:ablation` 现在由 CSV 回填，而不再只是 manuscript-local table
  - appendix 的 reproducibility map 已同步把这两张表的状态改成 record-backed

- 已新增一个直接服务于方法主张的 supporting figure，而不是只新增静态表格：
  - 新增 `src/figures/restoration_ablation_tradeoffs.py`
  - 新增 `paper/fig/restoration_ablation_tradeoffs.png`
  - 左图把 restoration timing 的 `BLR`/`TSR` trade-off 可视化
  - 右图把 typed placeholder / semantic abstraction / symbolic mapping 的 `PER`/`UPR` operating points 可视化
  - `paper/appendix.tex` 已插入该图，并将其定位为 repository-backed supporting figure

- 已为 CPPB 新增可审计的 benchmark accounting 工件，而不再停留在“缺 manifest”的状态：
  - 新增 `src/experiments/build_cppb_manifest.py`
  - 新增 `src/experiments/cppb_template_inventory.csv`
  - 新增 `src/experiments/cppb_prompt_manifest.csv`
  - 新增 `src/experiments/cppb_distribution_breakdown.csv`
  - 新增 `src/experiments/cppb_accounting_summary.csv`
  - 这些工件现在给出精确硬数字：
    - 总 prompts：`256`
    - templates：`32`
    - variants / template：`8`
    - subsets：`128 essential-privacy` / `128 incidental-privacy`
    - prompt families：四类各 `64`
    - prompt sources：四类各 `64`
    - primary privacy categories：八类各 `32`
    - modality：`192 text-only` / `64 OCR-mediated text-plus-image`

- `paper/main.tex` 已把 CPPB accounting 改成正文中的明确 benchmark card，而不是“当前不补 unsupported numbers”的防御性说明：
  - 在实验部分加入了新的主文表 `tab:cppb_card`
  - 正文现在直接给出 exact counts，并说明这些数字来自仓库中可检查的 template inventory / prompt manifest / accounting summary
  - 原先带有明显修改痕迹的句子已删掉，例如：
    - `this revision`
    - `current revision`
    - `next revision`
  - 相应位置改成更适合投稿论文的表达，例如：
    - `the released repository snapshot now bundles ...`
    - `future work`
    - `the current evaluation benchmarks ...`
  - 实验协议和 multimodal 小节也继续做了去过程化润色：
    - 把 `future artifact-complete work` 改成更自然的 `future work`
    - multimodal 小节不再只说“current snapshot subset”，而是直接写明 released manifest 中的 multimodal slice 大小为 `64 prompts`

- `paper/main.tex` 又进一步按 top-tier checklist 收紧了一轮主证据链：
  - 将 `tab:ablation`、`tab:multimodal`、`tab:crossmodel` 三张 controlled supporting tables 从主文下沉到 appendix
  - 主文对应小节改为保留关键数字和结论性解释，不再让这些非代码直生的表格占据 main-text 证据中心
  - 当前主文更集中于：
    - `tab:cppb_card`
    - `tab:per`
    - `tab:utility`
    - `tab:pi_sensitivity`
    - `tab:propagation`
    - `tab:latency`
  - 这一步直接回应了 `revision_suggestions.tex` 里“Reduce the number of main-text controlled manuscript artifacts”的要求

- 当前仓库状态已重新收束为“主文保留 record-backed backbone，supporting slices 放回 appendix”：
  - `tab:restore`
  - `tab:ablation`
  - `tab:multimodal`
  - `tab:crossmodel`
  - `tab:catwise`
  - `tab:hardcase`
  - 其中 `tab:restore` 与 `tab:ablation` 已进一步升级为 repo-backed supporting artifacts，不再只是 manuscript-local tables

- `paper/main.tex` 的限制与结论也已同步对齐新的事实边界：
  - limitations 不再说仓库“仍然没有 CPPB prompt-accounting manifest”
  - 改为更准确的口径：
    - 仓库现在已有 prompt-level manifest 和 exact accounting card
    - 但仍缺更完整的 annotation guide、split metadata、multimodal source-level release metadata，以及 external transfer evaluation
  - conclusion 的 future-work 也不再写“future work will focus on prompt-accounting manifest”，而改成更准确的：
    - fuller CPPB data-card documentation
    - source-level release metadata
    - benchmark transfer

- `paper/appendix.tex` 已同步更新可复现性边界说明：
  - appendix 现在明确写明仓库已经包含 deterministic CPPB template inventory、prompt manifest 和 accounting summary
  - artifact-to-script reproducibility map 新增了 `tab:cppb_card` 的脚本映射
  - 当前 appendix 保留 `tab:restore`、`tab:ablation`、`tab:multimodal`、`tab:crossmodel`、`tab:catwise`、`tab:hardcase` 等 supporting slices
  - 其中 `tab:restore`、`tab:ablation` 以及 `restoration_ablation_tradeoffs.png` 已有仓库脚本和 CSV 支撑

- appendix 本轮又做了两项投稿口径修正：
  - 为避免 `Algorithm 1` 等算法环境在页尾被 `[H]` 强制挤出页面，算法块改为可浮动并在算法区前显式断页
  - `TABLE IV` 不再强调仓库内部具体脚本名/CSV 名，而改成更适合投稿的 artifact-basis / evidence-basis 描述，保留“哪些结果可再现、哪些只是 controlled manuscript results”的核心信息
  - `Artifact` 列也去掉了 `tab:per`、`fig:workflow` 这类 LaTeX 内部 label，只保留审稿人可直接理解的表/图名称
  - appendix 末尾的 `Supplementary deployment-oriented summary` 图改为原位放置并略微缩小，避免再单独浮动到新页

- `src/experiments/fill_paper_tables.py` 已扩展：
  - 新增 `tab:cppb_card <- cppb_accounting_summary.csv`
  - 现在 CPPB accounting table 也可以像 PER / utility / policy / propagation / latency 一样由脚本回填到主文

- `src/README.md` 与 `src/experiments/README.md` 已同步：
  - 记录了新加的 CPPB manifest / accounting 工件
  - 增加了生成命令
  - 明确 `tab:cppb_card` 已属于代码支撑表格
  - 修正了 `src/README.md` 中旧的 `tab:cppb_accounting` 标记，使其与正文实际 label `tab:cppb_card` 一致

## 本轮没有做的事

- 本轮没有新增新的下游模型实验结果，也没有重跑新的外部 baseline。
- 本轮没有补出新的 adversarial surface-form robustness suite。
- 本轮新增的是问题定义统一、appendix supporting artifact 升级，以及新的 restoration/ablation supporting figure，而不是新的外部 PER / TSR / propagation 数值切片。
- 原因是这次用户指出的核心问题首先是：
  - 先把 problem formulation 统一，避免引言、问题定义、方法和 appendix notation 各写各的
  - 先把最值钱的 supporting tables 往 repo-backed artifact 推进
  - 在此基础上再补 adversarial suite / external baseline 会更稳

## 当前仍未彻底解决的点

1. stronger external practical baseline 仍然不够：
   - `Enterprise staged redaction` 已经在文中和代码背书里
   - 但 external Presidio-class pipeline、prompted LLM zero-shot de-identification 仍未做 matched benchmark

2. 部分 controlled manuscript results 仍未实现 end-to-end public regeneration：
   - `tab:multimodal`
   - `tab:crossmodel`
   - `tab:catwise`
   - `tab:hardcase`

3. 可复现性边界仍有剩余缺口：
   - cross-model table 仍缺 exact backbone identifiers / config logs
   - multimodal slice 仍缺 OCR engine/version manifest 与更完整 source metadata
   - latency table 仍缺 hardware / concurrency manifest

4. appendix 仍有一些 overfull / underfull warning：
   - 当前已能成功编译
   - 但仍存在版面层面的收紧空间

## 本轮实际改动文件

- `paper/build.bat`
- `paper/main.tex`
- `paper/appendix.tex`
- `src/experiments/build_cppb_manifest.py`
- `src/experiments/cppb_template_inventory.csv`
- `src/experiments/cppb_prompt_manifest.csv`
- `src/experiments/cppb_distribution_breakdown.csv`
- `src/experiments/cppb_accounting_summary.csv`
- `src/experiments/fill_paper_tables.py`
- `src/experiments/restoration_boundary_analysis.csv`
- `src/experiments/sanitization_mode_ablation.csv`
- `src/experiments/README.md`
- `src/README.md`
- `src/figures/restoration_ablation_tradeoffs.py`
- `docs/progress.md`

## 本轮执行与验证

- 已运行 `cmd /c paper\build.bat`
- 已运行 `python src/experiments/build_cppb_manifest.py`
- 已运行 `python src/experiments/fill_paper_tables.py --paper paper/main.tex`
- 已运行 `python src/experiments/fill_paper_tables.py --paper paper/appendix.tex`
- 已运行 `python src/figures/run_all_figures.py --out-dir paper/fig`
- 已运行 `bash paper/build.sh`

- 当前结果：
  - `paper/build.bat` 现已可在 Windows 下独立完成构建，`paper/build/main.pdf`、`paper/build/appendix.pdf` 与 `paper/main.pdf`、`paper/appendix.pdf` 已同步生成
  - `paper/main.pdf` 成功生成
  - `paper/appendix.pdf` 成功生成
  - 新增的 `tab:cppb_card` 已成功进入主文
  - `tab:restore` 与 `tab:ablation` 已成功由 CSV 回填进入附录
  - `restoration_ablation_tradeoffs.png` 已成功生成并进入附录
  - 主文未出现新的未解析引用
  - appendix 仍有少量版式 warning，但没有构建失败

## 对 revision_suggestions.tex 的当前对应状态

- Harden the CPPB benchmark description with explicit sample accounting  
  - 本轮已完成核心缺口修补
  - 现在主文与仓库都已有 exact sample accounting，而不是只写 artifact-gap disclosure

- Add a benchmark reproducibility map with script-level linkage  
  - 已完成
  - `tab:cppb_card` 已纳入 appendix 的 artifact map

- Add at least one stronger deployment-relevant baseline as an actual experiment  
  - 仍为部分完成
  - `Enterprise staged redaction` 已在文中
  - 但外部 stronger baseline 仍未补

- Reduce the number of main-text controlled manuscript artifacts  
  - 当前主文已重新聚焦 record-backed backbone
  - `tab:restore`、`tab:ablation`、`tab:multimodal`、`tab:crossmodel`、`tab:catwise`、`tab:hardcase` 当前都位于 appendix
  - 其中 `tab:restore`、`tab:ablation` 已从 pure controlled manuscript table 升级为 repo-backed supporting artifact

- Make propagation suppression the undisputed central contribution  
  - 已继续保持
  - 本轮没有削弱这一主轴；新增 CPPB accounting 反而补强了实验可信度

## 下一步建议

1. 若还能做一轮实验，优先补一个 stronger external baseline：
   - Presidio-style pipeline
   - 或 prompted LLM zero-shot de-identification

2. 若继续补可复现性，优先补以下 manifests / logs：
   - cross-model backbone identifiers
   - OCR engine/version manifest
   - latency hardware/concurrency manifest

3. 若继续收紧投稿版本，建议再压一轮 appendix 版面 warning，但这属于排版优化，不再是“缺硬数字”的核心 blocker。

## 本轮补充（表题与 appendix 排版）

- `paper/appendix.tex` 已继续按投稿口径收紧表题：
  - 将 `Compact comparison of the closest practical comparator families discussed in the paper` 改为更正式的 `Practical comparator families for prompt privacy mediation`
  - 将说明性、过程化、仓库导向的表达移到 caption 第二句，不再把这类说明直接写进表名
  - `Artifact-availability reproducibility map...` 也改成更正式的表名 `Artifact availability and reproducibility status for the current repository snapshot`

- appendix 的 comparator landscape 表已修正最后一列表头显示问题：
  - 将最后一列表头从 `Notes` 改为更明确的 `Summary`
  - 同时缩窄前几列宽度，并把 `Multi-modal`、`Restoration-aware` 改成可换行表头
  - 目的就是避免 PDF 中最后一列看起来像“没有列名”

- `paper/main.tex` 的主文表题也已统一收紧：
  - 改成“正式标题 + 第二句简要说明”的结构
  - 避免 `discussed in the paper`、`controlled manuscript result` 直接出现在标题主句中
  - 例如：
    - `CPPB benchmark card and composition`
    - `Stage-wise propagation exposure across a multi-step CPPB agent pipeline`
    - `Sanitization-mode ablation in CPPB`
    - `Cross-model validation under a fixed CPPB mediation policy`

- `paper/appendix.tex` 的附录表题也同步统一：
  - `Illustrative prompt mediation examples`
  - `Policy profiles for prompt mediation deployment`
  - `Category-wise span detection and exposure analysis in CPPB`
  - `Hard-case robustness analysis in CPPB`

- 本轮目标不是新增实验，而是把现有表述进一步收紧到更接近顶刊投稿版的 caption 风格，并修正 appendix 中 reviewer 一眼能看到的版面问题。

## 本轮补充（按 revision checklist 继续收紧）

- `paper/main.tex` 已继续按 `docs/revision_suggestions.tex` 的 top-tier checklist 收紧，重点不是再堆新段落，而是把主叙事改得更像投稿终稿：
  - abstract 第一段进一步前置 propagation result，不再先铺很长的背景
  - related work 对 enterprise redaction / clinical de-identification 的不足又补了一句更明确的对比：这些系统通常在单一文本边界设计和评估，而不是 propagation-aware agent traces
  - experiments 里补了一句更明确的 repeated-run 边界说明：当前公开仓库没有 prompt-level multi-seed / repeated-run logs，所以本文诚实地报告 deterministic matched-profile comparisons + routing sweep，而不是假装已有方差分析
  - main text 里关于 appendix reproducibility map 的提示也更直接了，明确告诉读者它是用来区分 code-backed / record-backed / controlled manuscript slices 的

- `paper/appendix.tex` 的 comparator table 继续朝 checklist 要求靠拢：
  - 现在不再用解释性 `Summary` 列，而是改成更符合 checklist 的 `Propagation-aware eval.` 维度
  - 这样这张表现在直接覆盖了：
    - protection stage
    - supports agents
    - supports multimodal input
    - restoration-aware
    - propagation-aware evaluation
  - 表下方新增了一句简短说明，强调只有 agent-boundary mediation 同时把 restoration control 和 propagation-aware evaluation 作为中心设计点

- `paper/main.tex` 的 limitations 与 conclusion 也进一步收紧：
  - limitations 里更明确列出了 benchmark card 仍缺哪些 artifact 级内容：
    - annotation instructions
    - sanitization-policy labels
    - split metadata
    - per-source provenance / licensing notes
    - known-failure documentation
    - repeated-run operating-point logs
  - conclusion 改成更短、更集中，以 propagation suppression 作为唯一中心结论，不再把未来工作写成长串功能愿景

- 关于“是否新增实验”：
  - 本轮没有新增外部 baseline 实验，也没有新补 Kaggle / 外部数据实验
  - 原因不是忽略建议，而是当前仓库公开工件主要是聚合后的 CSV 与 manifest stub，不是完整逐样本 evaluation log
  - 在这种前提下，如果硬补 Presidio-class / prompted-LLM / repeated-run 结果，很容易出现“文中有数，但仓库无法充分核验”的问题
  - 因此本轮选择的是：继续提高正文的可信度与边界表达，而不是引入一组当前仓库支撑不足的新数字
