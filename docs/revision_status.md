# 修订状态

最后更新：2026-03-27  
对应审稿建议：`docs/revision_suggestions.tex`（当前为 Stage 27）

---

## 固定更新规则

以后每次更新 `docs/revision_status.md`，都必须遵守以下规则：

1. 必须使用中文。
2. 必须按两组归类：
   - 已全部修改
   - 未修改或部分修改
3. 每一条都必须明确写出“修改状态”。
4. 对于“未修改”或“部分修改”的条目，必须同时写清楚：
   - 已修改了哪些部分
   - 还有哪些部分未修改
   - 未修改或未全部修改的原因
5. 状态内容必须和当前源码、当前 PDF、当前编译结果一致，不能只写计划。

---

## 一、已全部修改的条目

### 1. 论文主线统一为 prompt privacy mediation

- 修改状态：已全部修改
- 修改说明：主文已经统一围绕 LLM/VLM prompt privacy mediation 展开，不再保留旧的 classifier-era 叙事残留；标题、摘要、问题定义、方法框架、实验解释和结论现在属于同一条主线。
- 涉及文件：
  - `paper/main.tex`

### 2. Section V-D 基线开头表述修正

- 修改状态：已全部修改
- 修改说明：基线段落已经采用更正式的 “representative operational baselines” 风格，符合最新版建议对 baseline opening 的要求。
- 涉及文件：
  - `paper/main.tex`

### 3. Sections VI-B / VI-G / VI-H / VI-I 的 deployment-oriented interpretation 补强

- 修改状态：已全部修改
- 修改说明：这些结果小节已经不再只是表后复述，而是补成了偏部署视角、威胁模型视角和系统落地视角的解释。
- 涉及文件：
  - `paper/main.tex`

### 4. Section VI-L 结尾措辞强化

- 修改状态：已全部修改
- 修改说明：相关段落已经改成更强的 practical deployment defense / deployment-method contribution 风格，不再保留偏弱的收尾。
- 涉及文件：
  - `paper/main.tex`

### 5. Table II 范围句与位置流转修正

- 修改状态：已全部修改
- 修改说明：
  - `Table II` 的说明句现在正确使用 `Tables III--XIII`。
  - 说明句不再留在 Section IV 尾部，而是与 `Table II` 浮动体绑定，作为 Section V 的概念引导。
  - 当前 PDF 中，说明句与 `Table II` 一起出现在第 5 页。
- 涉及文件：
  - `paper/main.tex`

### 6. 第 4 页最明显的 box-heavy 问题已做低风险缓解

- 修改状态：已全部修改
- 修改说明：
  - 已将 `Table I` 移到 `\section{Experimental Setup}` 之后，使其不再与第 4 页的 Fig. 1、公式区和后续小节挤在同一页。
  - 已压缩 Section IV-G / IV-H 的开头与若干长句，并将几个很短的公式改成行内写法，减轻页尾拥挤。
  - Stage 27 这一轮又进一步压短了 Section IV-E / F / G / H 附近的若干句子，使第 4 页比上一版更松一些。
  - 当前 PDF 中，`Table I` 与 `Table II` 一起出现在第 5 页，且第 4 页版面已较前几轮明显缓解。
- 涉及文件：
  - `paper/main.tex`

### 7. Appendix A 算法名称显示风格自然化

- 修改状态：已全部修改
- 修改说明：
  - 已将算法中的 procedure 名称显示风格调整为更接近期刊稿 pseudocode 的形式。
  - 当前 Appendix A 中显示为 `ExtractSpans`、`SanitizePrompt`、`RestoreEntities`、`RuleRecognizers`、`NamedEntityRecognizer`、`ContextualPrivacyJudge` 等自然命名，不再呈现原先那种过强的全大写过程名观感。
- 涉及文件：
  - `paper/main.tex`
  - `paper/appendix.tex`

### 8. Appendix / Table XIV 过渡句清理

- 修改状态：已全部修改
- 修改说明：`Table XIV` 前的过渡句已经压缩并整理为单句说明，不再重复、不再断裂，且与主文 `Table I`、`Tables III--XIII` 的定位关系清晰。
- 涉及文件：
  - `paper/appendix.tex`

### 9. Appendix B 历史说明精简

- 修改状态：已全部修改
- 修改说明：Appendix B 已保持为简短、正式、不会干扰主文叙事的 brief historical note；附录开头也已经说明当前附录只保留伪代码、附加示例和简短历史说明。
- 涉及文件：
  - `paper/appendix.tex`

### 10. Appendix 开头与附录正文语气进一步润色

- 修改状态：已全部修改
- 修改说明：Stage 27 这一轮进一步把附录开头和 Table XIV 引导句润色成更简洁、更 journal-ready 的写法，但没有改动附录结构、算法逻辑或附加示例内容。
- 涉及文件：
  - `paper/appendix.tex`

### 11. 附录当前版本与主文一致性复核

- 修改状态：已全部修改
- 修改说明：已复核 Appendix A 伪代码、Table XIV、Appendix B 与主文框架、术语和表格引用链的一致性；当前附录内容已经与主文对齐，不需要再做结构性改写。
- 涉及文件：
  - `paper/appendix.tex`
  - `paper/main.tex`

### 12. 通过 `src/` 生成新的对比实验图并插入 `paper/`

- 修改状态：已全部修改
- 修改说明：
  - 已在 `src/experiments/` 中补充当前 prompt privacy mediation 主线所需的图表数据文件。
  - 已在 `src/figures/` 中新增三张与当前论文主线直接匹配的 summary / comparison figure 脚本，并接入 `src/figures/run_all_figures.py`。
  - 已从 `src/` 实际生成三张新图并写入 `paper/fig/`：
    - `prompt_privacy_operating_points.png`
    - `agent_pipeline_summary.png`
    - `agent_propagation_curves.png`
  - 已将前者插入主文结果部分，用于概括 method-level 与 policy-level 的 privacy--utility operating regimes。
  - 已将 `agent_propagation_curves.png` 插入主文的 agent propagation 实验部分，用于把 Table XI 的阶段传播结果可视化。
  - 已将后者插入附录，用于补充 deployment-oriented 的 propagation / latency 联合视图。
- 涉及文件：
  - `src/experiments/prompt_method_comparison.csv`
  - `src/experiments/policy_sensitivity.csv`
  - `src/experiments/agent_pipeline_metrics.csv`
  - `src/experiments/latency_overhead.csv`
  - `src/figures/prompt_privacy_operating_points.py`
  - `src/figures/agent_pipeline_summary.py`
  - `src/figures/agent_propagation_curves.py`
  - `src/figures/run_all_figures.py`
  - `paper/main.tex`
  - `paper/appendix.tex`

---

## 二、未修改或部分修改的条目

### 1. 第 4 页整体版面密度的最终 polish

- 修改状态：部分修改
- 已修改部分：
  - 已将 `Table I` 移出第 4 页。
  - 已将 `Table II` 的说明句移出第 4 页页尾并绑定到 Section V。
  - 已压缩 Section IV 后半段若干句子，并将几个很短的显示公式改成行内写法。
  - Stage 27 这一轮又继续压短了 IV-E / F / G / H 附近的几句文字。
- 尚未修改部分：
  - 还没有再做更激进的版面再平衡，例如进一步重排 Fig. 1 周边布局、调整更多段落长度，或做更强的浮动体重排。
  - 第 4 页虽然已经明显改善，但从最终投稿视觉观感看，仍然略显紧凑。
- 未修改原因：
  - 最新建议将这部分定义为 final polish，而不是科学性或结构性问题。
  - 本轮优先采用低风险调整，避免为了进一步挪页而扰动主文结构、浮动体顺序或表格编号。
- 涉及文件：
  - `paper/main.tex`

### 2. 最终 typography / equation / algorithm 的逐页人工细读

- 修改状态：部分修改
- 已修改部分：
  - 已检查并优化 `\Pi`、PER、UPR 等关键符号附近的排版。
  - 已检查第 4 页、第 5 页和附录算法页的核心视觉问题。
  - 已确认 Appendix A 算法名称风格比之前更自然。
  - 已重新编译并确认没有未解析的引用或交叉引用警告。
- 尚未修改部分：
  - 还没有完成一轮从首页到附录末尾、以最终投稿视觉效果为目标的逐页人工精修。
  - 还没有逐项消化所有 IEEE 模板层面的 `underfull/overfull` 提示。
- 未修改原因：
  - 这是最后一轮人工视觉 polish，更依赖整篇 PDF 的投稿前人工审阅，而不是继续做大范围文字修改。
  - 当前版本已经没有实质性的引用错误，剩余主要是模板级排版提示。
- 涉及文件：
  - `paper/main.tex`
  - `paper/appendix.tex`

### 3. 参考文献进一步增强

- 修改状态：未修改
- 已修改部分：
  - 本轮未新增参考文献条目。
- 尚未修改部分：
  - 没有向 `paper/references.bib` 新增 trustworthy / secure LLM deployment、document AI / OCR privacy、enterprise agent / RAG security risk 等方向的额外强引用。
- 未修改原因：
  - 最新建议明确说明该项属于 optional bibliography polish，不是必改项。
  - 当前参考文献覆盖面已被认为可以投稿，本轮优先处理版面、浮动体和附录风格的低风险修订。
- 涉及文件：
  - `paper/references.bib`

## 三、本轮实际改动文件

- `src/figures/agent_propagation_curves.py`
- `src/figures/run_all_figures.py`
- `paper/main.tex`
- `docs/revision_status.md`

---

## 四、验证结果

- 已运行 `python src/figures/run_all_figures.py --out-dir paper/fig`，确认两张新图已由 `src/` 生成到 `paper/fig/`。
- 已在 `paper/` 目录重新运行多次 `pdflatex -interaction=nonstopmode main.tex`，并确认交叉引用稳定。
- 当前结果确认：
  - `Table I` 与 `Table II` 都位于第 5 页；
  - `Table II` 说明句与表格一起出现，且仍正确指向 `Tables III--XIII`；
  - 主文已新增 `prompt_privacy_operating_points.png`；
  - 主文已新增 `agent_propagation_curves.png`；
  - 附录已新增 `agent_pipeline_summary.png`；
  - Appendix A 的算法名称显示更自然；
  - `Table XIV` 和 `APPENDIX B` 正常。
- 当前编译结果中没有未解析的引用或交叉引用警告。
- 当前仍存在少量 IEEE 模板常见的 `underfull/overfull` 排版提示，但不属于结构性错误。

---

## 五、当前结论

按照 `docs/revision_suggestions.tex` 当前版本，这篇论文已经处于接近最终投稿的状态。

本轮之后：

- 必改项已经完成；
- 低风险的版面与附录风格修订已经继续收紧一轮；
- 当前主线所需的三张 summary / comparison figure 已经由 `src/` 生成并接入论文；
- 剩余未做内容主要是可选参考文献增强和最后一轮人工视觉 polish，而不是必须修复的问题。
