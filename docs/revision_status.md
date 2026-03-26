# 修订状态

最后更新：2026-03-27  
对应审稿建议：`docs/revision_suggestions.tex`（当前为 Stage 24）

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
- 修改说明：主文已经统一围绕 LLM/VLM prompt privacy mediation 展开，不再保留旧的 classifier-era 混合叙事；标题、摘要、问题定义、框架、实验、结论目前属于同一条主线。
- 涉及文件：
  - `paper/main.tex`

### 2. Section V-D baseline opening 更专业

- 修改状态：已全部修改
- 修改说明：基线开头已使用更正式的 “representative operational baselines” 风格，符合 Stage 24 中对该项“已修好”的判断。
- 涉及文件：
  - `paper/main.tex`

### 3. Sections VI-B、VI-G、VI-H、VI-I 的解释段补强

- 修改状态：已全部修改
- 修改说明：相关结果小节已经从“报表式描述”补成“解释 category gradient、OCR bottleneck、cross-model stability、propagation depth 的部署导向分析”。
- 涉及文件：
  - `paper/main.tex`

### 4. Section VI-L 结尾措辞强化

- 修改状态：已全部修改
- 修改说明：当前结尾已采用 “practical deployment defense” 的更强措辞，不再是较弱的早期说法。
- 涉及文件：
  - `paper/main.tex`

### 5. Table II 范围句与位置流转修正

- 修改状态：已全部修改
- 修改说明：
  - `Table II` 说明句已正确写成 `Tables III--XIII`；
  - 说明句不再停留在 Section IV 尾部，而是和 `Table II` 一起出现在 Section V 语境中；
  - 当前 PDF 中，说明句与 `Table II` 一起出现在第 5 页。
- 涉及文件：
  - `paper/main.tex`

### 6. Appendix / Table XIV 过渡句清理

- 修改状态：已全部修改
- 修改说明：`Table XIV` 前的过渡句已去重并整理顺畅，不再重复。
- 涉及文件：
  - `paper/appendix.tex`

### 7. Appendix B 历史说明精简

- 修改状态：已全部修改
- 修改说明：Appendix B 目前是简短、正式且不干扰主文叙事的版本，符合 Stage 24 对该项“已修好”的判断。
- 涉及文件：
  - `paper/appendix.tex`

### 8. 附录算法标题与 procedure 风格自然化

- 修改状态：已全部修改
- 修改说明：
  - Appendix A 中 Algorithm 1--3 的标题本身已保持自然期刊风格；
  - 本轮通过调整 `algpseudocode` 的 `\textproc` 显示方式，使 `ExtractSpans`、`SanitizePrompt`、`RestoreEntities` 在 PDF 中不再呈现原先那种全大写小型大写体观感；
  - 当前第 11 页 PDF 已显示为更自然的 procedure 名称风格。
- 涉及文件：
  - `paper/main.tex`

### 9. 附录当前版本复核

- 修改状态：已全部修改
- 修改说明：已复核 Appendix A 伪代码、Table XIV、Appendix B 与主文一致性；当前附录内容与主文框架对齐，因此本轮不需要对 `appendix.tex` 再做实质性文字改写。
- 涉及文件：
  - `paper/appendix.tex`

---

## 二、未修改或部分修改的条目

### 1. 第 4 页版面密度

- 修改状态：部分修改
- 已修改部分：
  - 已将 `Table II` 的说明句移出第 4 页页尾；
  - 已压缩 Section IV 后半段若干长句；
  - 已把 Section IV-G 和 Section IV-H 的开头进一步改短；
  - 已将几个很短的独立公式改成行内写法，减少垂直占用。
- 尚未修改部分：
  - 第 4 页整体仍然略显拥挤；
  - 还没有通过更大幅的版面重排来彻底拉开第 4 页和第 5 页的视觉间距。
- 未全部修改原因：
  - 当前建议把这一项定义为 final polish，不是结构性问题；
  - 这轮优先采用低风险压缩，避免因进一步挪动浮动体而影响主文整体流转。
- 涉及文件：
  - `paper/main.tex`

### 2. Table I 仍与 Fig.1 / 公式区域挤在同一页

- 修改状态：未修改
- 已修改部分：
  - 已通过压缩 IV-G、IV-H 的开头来尝试减轻该页密度；
  - 但 `Table I` 目前仍然停留在第 4 页。
- 尚未修改部分：
  - 没有把 `Table I` 主动后移到下一页页顶；
  - 没有额外调整 Figure 1 或相关浮动体参数。
- 未修改原因：
  - Stage 24 明确把这项列为可选优化；
  - 当前不建议在最后阶段为了一页的观感去大幅扰动浮动体布局。
- 涉及文件：
  - `paper/main.tex`

### 3. 最终 typography / equation / algorithm 人工通读

- 修改状态：部分修改
- 已修改部分：
  - 已检查 `\tilde{x}`、`\Pi`、PER、UPR 附近的关键排版；
  - 已检查第 4 页和第 11 页；
  - 已重新编译并确认当前没有未解析的引用或交叉引用警告。
- 尚未修改部分：
  - 还没有做一轮逐页、逐段、以投稿视觉效果为目标的人工细读；
  - 还没有逐项处理所有 IEEE 模板造成的 `underfull/overfull` 提示。
- 未全部修改原因：
  - 这是最后一轮人工视觉 polish，更适合在最终提交前通读整份 PDF 时完成；
  - 当前版本已经没有实质性引用错误，剩余主要是模板级排版提示。
- 涉及文件：
  - `paper/main.tex`
  - `paper/appendix.tex`

### 4. 参考文献进一步增强

- 修改状态：未修改
- 已修改部分：
  - 无新增参考文献条目。
- 尚未修改部分：
  - 没有向 `references.bib` 新增 trustworthy deployment、document/OCR privacy、enterprise agent privacy / RAG risk 等方向的额外强引用。
- 未修改原因：
  - 最新建议明确指出该项只是 optional literature polish；
  - 当前 bibliography 已被认为可以投稿，本轮优先处理低风险版面和风格项。
- 涉及文件：
  - `paper/references.bib`

---

## 三、本轮实际改动文件

- `paper/main.tex`
- `docs/revision_status.md`

说明：

- `paper/appendix.tex` 本轮已复核，但没有新增文字改动；
- 附录算法风格的改善是通过 `paper/main.tex` 中对 `algpseudocode` 显示方式的调整实现的。

---

## 四、验证结果

- 已在 `paper/` 目录运行 `bibtex main` 与多次 `pdflatex -interaction=nonstopmode main.tex`。
- 当前结果确认：
  - `Table II` 说明句与表格一起出现在第 5 页；
  - `Table II` 编号保持正确；
  - `Tables III--XIII` 引用链保持正确；
  - 第 11 页中 `ExtractSpans`、`SanitizePrompt`、`RestoreEntities` 的显示风格已更自然；
  - `Table XIV` 和 `APPENDIX B` 正常；
  - 最终 `main.log` 中没有未解析的引用或交叉引用警告。
- 当前仍存在少量 IEEE 模板常见的 `underfull/overfull` 排版提示，但不属于结构性问题。

---

## 五、当前结论

按照 `docs/revision_suggestions.tex` 的当前 Stage 24 版本，这篇论文已经非常接近最终投稿状态。

本轮之后：

- 必改项已经完成；
- 新增的附录算法风格优化已经完成；
- 剩余未做内容主要是可选的版面美化和参考文献增强，而不是必须修的问题。
