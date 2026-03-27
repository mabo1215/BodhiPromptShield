# 论文进度

最后更新：2026-03-28  
当前目标：根据 `docs/revision_suggestions.tex` 继续把 `paper/` 收紧到更接近 top-tier submission 的版本，并把“已经补上的证据”和“当前仓库仍然缺失的证据”明确分开。

---

## 本轮已完成

- 已继续强化主文的中心叙事，把 propagation suppression 明确写成论文最强的系统性结果：
  - 摘要现在直接给出 stage-wise propagation 数值结果：
    - Proposed boundary-aware mediation：`10.7% -> 7.1%`
    - Regex-only：`62.7% -> 59.8%`
  - 引言进一步明确论文的新意是 `pre-inference mediation under propagation risk`，而不是泛泛的 prompt sanitization。
  - 结论继续以 propagation suppression 作为最强验证结论，并把后续里程碑写得更具体。

- 已把更强、且更贴近部署的 baseline 正式写进实验设计与结果解释：
  - 新增并明确命名 `Enterprise staged redaction` baseline。
  - 该 baseline 对应现有代码背书结果中的 typed-placeholder-only profile，但正文现在明确解释它代表：
    - regex/pattern matching
    - NER
    - category-aware typed replacement
    - 无 semantic abstraction
    - 无 controlled boundary restoration
  - 主文现在不再只和轻量级 comparator 对比，而是明确说明该 baseline 更接近现实企业式 redaction middleware。

- 已同步更新代码背书产物，使 baseline 命名和论文叙述一致：
  - `src/experiments/prompt_method_comparison.csv`
    - `Proposed (typed placeholder)` 已改为 `Enterprise staged redaction`
  - `src/figures/prompt_privacy_operating_points.py`
    - 更新图中该 baseline 的标注缩写
  - 已重新运行：
    - `python src/experiments/fill_paper_tables.py --paper paper/main.tex`
    - `python src/figures/run_all_figures.py --out-dir paper/fig`

- 已把“迁移出主文的概念表”真正补回附录，而不是只在正文里口头前引：
  - 附录新增 illustrative prompt mediation example table
  - 附录新增 conceptual operating regimes table
  - 主文继续只保留简短前引，从而提高正文 empirical density

- 已在附录新增 artifact-to-script reproducibility map：
  - 形式为：
    - Artifact
    - Script / CSV
    - Status
    - Notes
  - 覆盖主文主要表图与附录可再生产物
  - 明确区分：
    - `Fully regenerated`
    - `CSV-backed`
    - `Controlled manuscript`
    - `Illustrative`
  - 并补入了 reproducible subset 的命令摘要

- 已进一步把“仓库当前证据边界”写清楚，而不是模糊带过：
  - 主文和附录都明确说明：
    - 当前仓库没有 CPPB prompt-accounting manifest
    - 因而这轮不会凭空补 exact subset/source/template counts
    - 这是当前 artifact gap，而不是隐藏细节

## 已部分回应、但仍未彻底解决

- `revision_suggestions.tex` 中关于 “Add exact CPPB counts and distributions”：
  - 本轮只能做到：
    - 在主文/附录中明确记录缺口
    - 说明为什么当前 revision 不补 unsupported numbers
  - 仍未做到：
    - total prompt count
    - subset counts
    - source composition counts
    - template / variant counts
  - 原因：
    - 当前仓库没有可核验的 CPPB prompt-accounting manifest

- 关于 “Add at least one stronger deployment-relevant baseline as an actual experiment”：
  - 本轮已完成最小可行版本：
    - `Enterprise staged redaction` 已作为实际 benchmark comparator 出现在代码背书表格中
  - 仍未做到：
    - 外部 Presidio-class pipeline 的 matched benchmark
    - prompted LLM zero-shot de-identification 的 matched benchmark

- 关于 “Add one small repeated-run or robustness analysis”：
  - 本轮未新增 repeated-run / multi-seed robustness artifact
  - 当前图仍应解释为 operating-profile visualization，而不是 variance-certified robustness evidence

## 当前仍然存在的主要 blocker

1. CPPB 的 exact prompt accounting 仍然缺失仓库内可核验 manifest。
2. 外部更强 baseline 仍缺 matched scripts / calibration / result logs。
3. 若要进一步冲 top-tier，仍需要：
   - 外部 Presidio-class 或 prompted-LLM baseline
   - 更完整的 CPPB 数据卡与 split/accounting manifest
   - 至少一个 repeated-run / robustness artifact
4. 附录新增 artifact map 后，虽然已成功编译，但仍有少量 appendix overfull 提示，属于版面收紧而非断链错误。

## 本轮实际改动文件

- `paper/main.tex`
- `paper/appendix.tex`
- `src/experiments/prompt_method_comparison.csv`
- `src/figures/prompt_privacy_operating_points.py`
- `docs/progress.md`

## 本轮实际执行与验证

- 已运行 `python src/experiments/fill_paper_tables.py --paper paper/main.tex`
- 已运行 `python src/figures/run_all_figures.py --out-dir paper/fig`
- 已运行 `bash paper/build.sh`
- 当前结果：
  - `paper/main.pdf` 成功生成
  - `paper/appendix.pdf` 成功生成
  - 主文未出现新的未解析引用
  - 附录有少量新增 overfull/underfull 提示，但没有构建失败或引用断链

## 对 revision_suggestions.tex 的当前对应状态

- Move conceptual tables out of the main paper  
  - 已完成

- Harden the CPPB benchmark description with explicit sample accounting  
  - 部分完成
  - 已补诚实边界说明；精确计数仍缺 manifest

- Add a benchmark reproducibility map with script-level linkage  
  - 已完成

- Add at least one stronger deployment-relevant baseline as an actual experiment  
  - 部分完成
  - 已加入 `Enterprise staged redaction`
  - 外部强 baseline 仍未完成

- Make propagation suppression the undisputed central contribution  
  - 已完成本轮主叙事强化

## 下一步建议

1. 如果手头有 CPPB 的 prompt-accounting manifest，优先把 exact counts 补进实验设计或附录 benchmark accounting table。
2. 若还能做一轮实验，优先补一个外部 deployment-style baseline：
   - Presidio-style pipeline
   - 或 prompted LLM zero-shot de-identification
3. 若时间允许，再补一个最小 repeated-run artifact，用于 operating-point figure 或 propagation slice 的稳健性说明。
