# 论文进度

最后更新：2026-03-28  
当前目标：继续按 `docs/revision_suggestions.tex` 收紧 `paper/`，但避免正文出现明显的“revision/修改过程”痕迹；本轮重点是把 CPPB 的 exact accounting 真正补进仓库工件和主文，而不是只在正文里解释为什么没有数字。

---

## 本轮已完成

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

- `src/experiments/fill_paper_tables.py` 已扩展：
  - 新增 `tab:cppb_card <- cppb_accounting_summary.csv`
  - 现在 CPPB accounting table 也可以像 PER / utility / policy / propagation / latency 一样由脚本回填到主文

- `src/README.md` 与 `src/experiments/README.md` 已同步：
  - 记录了新加的 CPPB manifest / accounting 工件
  - 增加了生成命令
  - 明确 `tab:cppb_card` 已属于代码支撑表格

## 本轮没有做的事

- 本轮没有新增新的下游模型实验结果，也没有重跑新的外部 baseline。
- 本轮新增的是 benchmark accounting 工件与主文表格，而不是新的 PER / TSR / propagation 数值切片。
- 原因是这次用户指出的核心问题首先是：
  - 正文里不能再写 `this revision`
  - CPPB 需要 exact counts
  - 这些问题优先级高于继续扩展新的对比实验

## 当前仍未彻底解决的点

1. stronger external practical baseline 仍然不够：
   - `Enterprise staged redaction` 已经在文中和代码背书里
   - 但 external Presidio-class pipeline、prompted LLM zero-shot de-identification 仍未做 matched benchmark

2. 部分 controlled manuscript results 仍未实现 end-to-end public regeneration：
   - `tab:restore`
   - `tab:ablation`
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

- `paper/main.tex`
- `paper/appendix.tex`
- `src/experiments/build_cppb_manifest.py`
- `src/experiments/cppb_template_inventory.csv`
- `src/experiments/cppb_prompt_manifest.csv`
- `src/experiments/cppb_distribution_breakdown.csv`
- `src/experiments/cppb_accounting_summary.csv`
- `src/experiments/fill_paper_tables.py`
- `src/experiments/README.md`
- `src/README.md`
- `docs/progress.md`

## 本轮执行与验证

- 已运行 `python src/experiments/build_cppb_manifest.py`
- 已运行 `python src/experiments/fill_paper_tables.py --paper paper/main.tex`
- 已运行 `bash paper/build.sh`

- 当前结果：
  - `paper/main.pdf` 成功生成
  - `paper/appendix.pdf` 成功生成
  - 新增的 `tab:cppb_card` 已成功进入主文
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
  - 仍为部分完成
  - `tab:catwise` 与 `tab:hardcase` 已在之前移至 appendix
  - 但主文里仍有若干 controlled manuscript result

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
