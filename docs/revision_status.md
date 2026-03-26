# 修订状态

最后更新：2026-03-27  
对应审稿建议：`docs/revision_suggestions.tex`（当前为 Stage 23）

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
- 修改说明：主文已经统一围绕 LLM/VLM prompt privacy mediation 展开，不再保留旧的 classifier-era 叙事残留；标题、摘要、问题定义、框架、结果和结论现在是同一条主线。
- 涉及文件：
  - `paper/main.tex`

### 2. Section V-D 基线表述修正

- 修改状态：已全部修改
- 修改说明：基线段落已使用更正式的 “representative operational baselines” 风格，符合最新建议中“baseline paragraph is now corrected”的判断。
- 涉及文件：
  - `paper/main.tex`

### 3. 结果部分的 deployment-oriented interpretation 补强

- 修改状态：已全部修改
- 修改说明：结果章节中针对关键表格的解释段已经补成偏部署视角的分析，不再只是逐表复述。
- 涉及文件：
  - `paper/main.tex`

### 4. Section VI-L 结尾措辞强化

- 修改状态：已全部修改
- 修改说明：相关段落已经使用更强的 “practical deployment defense” 方向表述，不再保留较弱收尾。
- 涉及文件：
  - `paper/main.tex`

### 5. Table II 范围句与位置流转修正

- 修改状态：已全部修改
- 修改说明：
  - `Table II` 的说明句现在正确使用 `Tables III--XIII`。
  - 说明句不再留在 Section IV 尾部，而是和 `Table II` 绑定在一起，作为 Section V 的概念引导。
  - 当前 PDF 中，说明句与 `Table II` 一起出现在第 5 页。
- 涉及文件：
  - `paper/main.tex`

### 6. Appendix / Table XIV 过渡句清理

- 修改状态：已全部修改
- 修改说明：`Table XIV` 前的过渡句已经去重并整理通顺，不再出现重复或断裂表述。
- 涉及文件：
  - `paper/appendix.tex`

### 7. Appendix B 历史说明精简

- 修改状态：已全部修改
- 修改说明：Appendix B 已经是简短、正式且不干扰主文叙事的版本，符合当前审稿建议中的 “clean and acceptable”。
- 涉及文件：
  - `paper/appendix.tex`

### 8. 附录当前版本复核

- 修改状态：已全部修改
- 修改说明：已复核 Appendix A 伪代码、Table XIV、Appendix B 与主文的一致性；当前附录内容已经和主文框架对齐，因此本轮不需要再做实质性文字改写。
- 涉及文件：
  - `paper/appendix.tex`

---

## 二、未修改或部分修改的条目

### 1. 第 4 页版面密度

- 修改状态：部分修改
- 已修改部分：
  - 已将 `Table II` 的说明句移出第 4 页页尾。
  - 已压缩 Section IV 后半段若干长句。
  - 已将几个很短的独立公式改成行内写法，以减少页面断行和垂直占用。
- 尚未修改部分：
  - 还没有进一步通过更激进的版面调整来彻底拉开第 4 页和第 5 页的视觉间距。
  - 还没有移动 `Table I`，也没有对 Figure 1 周边布局做结构性改动。
- 未全部修改原因：
  - 当前建议把这一项定义为 layout-only 的微调项，不是科学性问题。
  - 这轮优先采用低风险修改，避免为了进一步挪版面而扰动主文结构、浮动体顺序或表格编号。
- 涉及文件：
  - `paper/main.tex`

### 2. Table I / Table II 连续出现过于 box-heavy

- 修改状态：未修改
- 已修改部分：
  - 仅优化了 `Table II` 的引导语位置，使其与表格一起出现。
- 尚未修改部分：
  - 没有把 `Table II` 移到附录。
  - 仍然保留 `Table I` 和 `Table II` 在主文连续出现的结构。
- 未修改原因：
  - 最新建议明确说明这是可选项，当前主文放置方式仍然是 acceptable。
  - 如果把 `Table II` 挪到附录，会影响主文概念铺垫与表格流转，需要同步调整主文引用与阅读节奏，因此本轮未做。
- 涉及文件：
  - `paper/main.tex`
  - `paper/appendix.tex`

### 3. 最终 typography / equation / algorithm 人工通读

- 修改状态：部分修改
- 已修改部分：
  - 已检查 `\tilde{x}`、`\Pi`、PER、UPR 等关键符号附近的排版。
  - 已做一次面向第 4 页和第 11 页的定向检查。
  - 已重新编译并确认没有未解析的引用或交叉引用警告。
- 尚未修改部分：
  - 还没有做一轮逐页、逐段、以最终投稿视觉效果为目标的人工细读。
  - 还没有逐项处理所有 IEEE 模板造成的 `underfull/overfull` 提示。
- 未全部修改原因：
  - 这是典型的最后一轮人工视觉 polish，更多依赖整篇 PDF 的投稿前人工审阅，而不是继续做大范围文字改动。
  - 当前版本已经没有实质性引用错误，剩余主要是模板级排版提示。
- 涉及文件：
  - `paper/main.tex`
  - `paper/appendix.tex`

### 4. 参考文献进一步增强

- 修改状态：未修改
- 已修改部分：
  - 无新增参考文献条目。
- 尚未修改部分：
  - 没有向 `references.bib` 新增 trustworthy deployment、document/OCR privacy 等方向的额外强引用。
- 未修改原因：
  - 最新建议明确指出该项只是 optional literature polish。
  - 当前 bibliography 已被认为“acceptable”，本轮优先处理低风险版面与结构细节。
- 涉及文件：
  - `paper/references.bib`

---

## 三、本轮实际改动文件

- `paper/main.tex`
- `docs/revision_status.md`

说明：

- `paper/appendix.tex` 本轮已复核，但没有新增文字改动，因为当前状态已满足最新建议。

---

## 四、验证结果

- 已在 `paper/` 目录运行 `bibtex main` 与多次 `pdflatex -interaction=nonstopmode main.tex`。
- 当前结果确认：
  - `Table II` 说明句与表格一起出现在第 5 页；
  - `Table II` 编号保持正确；
  - `Tables III--XIII` 引用链保持正确；
  - `Table XIV` 和 `APPENDIX B` 正常；
  - 最终 `main.log` 中没有未解析的引用或交叉引用警告。
- 当前仍存在少量 IEEE 模板常见的 `underfull/overfull` 排版提示，但不属于引用错误或结构性问题。

---

## 五、当前结论

按照 `docs/revision_suggestions.tex` 的当前版本，这篇论文已经接近最终投稿状态。

本轮之后：

- 必改项已经完成；
- 低风险微调项已经完成一部分；
- 剩余未做内容主要是可选优化，而不是必须修的问题。
