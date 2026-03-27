# 论文进度

最后更新：2026-03-27  
当前目标：把仓库整理成与 `paper/` 当前 prompt privacy mediation 论文一致的 submission-grade package

---

## Completed

- 已把主文主线统一到 prompt privacy mediation，并保留了“controlled evidence / deployment-oriented contribution”的总体定位。
- 已把三张当前主线直接相关的图接入论文：
  - 主文 `prompt_privacy_operating_points.png`
  - 主文 `agent_propagation_curves.png`
  - 附录 `agent_pipeline_summary.png`
- 已把 `paper/main.tex` 中一处过于工程化的正文表述改成更适合 IEEE Transactions 风格的自然学术表述，不再在结果分析句中直接堆叠字面 redaction token。
- 已新增附录中的 reproducibility scope 说明，明确区分：
  - 概念性/示意性内容
  - 当前仓库已由代码直接支撑的表格/图
  - 仍属于受控手工整理、但尚未自动再生的结果
- 已重写 `src/experiments/fill_paper_tables.py`，使其只更新当前仓库里确实有 CSV 支撑的表格：
  - `tab:per`
  - `tab:utility`
  - `tab:pi_sensitivity`
  - `tab:propagation`
  - `tab:latency`
- 已重写 `src/README.md` 和 `src/experiments/README.md`，清除会误导读者理解为“旧 classifier-era 代码仍是当前论文主实验来源”的描述。
- 已修复 `paper/build.sh`，使其在当前 Windows + WSL/bash 环境下能够自动定位 MiKTeX 的 `pdflatex` / `bibtex` 并完成完整构建链。
- 已将 `paper/references.bib` 收缩为当前稿件真实引用的 cited-only 版本，移除了明显的旧项目遗留、占位条目和重复条目。
- 已收紧引言 contribution list，使其更明确地区分问题重 framing、方法设计和 controlled evidence，而不是把所有点写成同等强度的 novelty claim。
- 已将主文与附录拆分为两个独立 PDF：
  - `paper/main.pdf`：仅主文
  - `paper/appendix.pdf`：仅附录
  - `paper/appendix.tex` 现为 standalone 单文件附录源码，不再拆分 `appendix_body.tex`
- 已将论文标题抽取到 `paper/paper_metadata.tex`，使主文与附录共享同一标题源；附录首页不再显示作者姓名，只显示 `Appendix` 与论文标题。
- 已进一步调整附录首页标题为仅显示通栏顶置的 `Appendix`，不再附带论文标题。
- 已将附录 Table XIV 的 caption 改为可自动换行的盒子写法，避免长标题在单栏嵌入布局下横向撑开。
- 已移除附录中的 `APPENDIX A / APPENDIX B` 自动编号结构，当前附录只保留一个顶置 `Appendix` 标题；原 `Appendix B` 已并入同一附录并改为末尾历史说明段落。
- 已将附录中的补充示例表和 deployment summary 图改回单栏嵌入式 `table / figure` 布局，使其随正文内容流显示，而不是作为双栏通栏浮动体单独占版。

## In Progress

- 继续做“论文叙述强度”和“当前仓库证据边界”的对齐。
- 继续审查哪些 empirical tables 仍是手工整理结果、尚未由 `src/` 自动再生，并决定是补脚本还是在正文/附录中进一步弱化声称。
- 继续处理少量 typography / layout 杂讯，尤其是 underfull/overfull 提示较集中的段落与附录表示例表格。

## Next

- 进一步核对主文各表与 `src/experiments/` 的映射，标出“已代码验证 / 部分验证 / 未自动再生”的范围。
- 继续做最后一轮主文/附录版面收紧，优先处理最明显的 underfull/overfull 热点。
- 检查是否还能在当前仓库条件下，为尚未自动再生的 empirical tables 增补最小可行的数据映射或附录说明。

## Top 10 Publication Blockers

1. `src/` 文档和脚本曾明显残留旧论文逻辑，容易造成“代码与当前论文不匹配”的严重可信度问题。
2. `docs/progress.md` 之前并不满足当前任务要求，无法准确区分已完成、进行中、下一步、claim validation 和 unresolved blockers。
3. `src/experiments/fill_paper_tables.py` 原先指向旧的 ablation/baseline 结构，若继续使用会污染当前论文的可复现性叙述。
4. 主文并非所有 empirical tables 都能由当前 `src/` 自动再生，必须继续严控声称强度。
5. 第 4 页仍偏拥挤，属于版面 polish 而非科学性问题，但会影响第一印象。
6. 一些实验结果目前是“受控结果表述 + 局部 CSV 支撑”，还不是端到端完整实验管线。
7. 附录已经更诚实，但 reproducibility note 仍需和最终提交版保持同步。
8. 仍需继续清理少量版面级 underfull/overfull 提示，避免最终投稿前留下明显 typography 杂讯。
9. 仍需确认是否能在当前仓库中为 cross-model / multimodal / hard-case 等表补到最小自动化映射。
10. 还需要最终一轮面向投稿视觉效果的通读，而不是只依赖编译无错。

## Exact Files Changed

- `paper/main.tex`
- `paper/appendix.tex`
- `paper/paper_metadata.tex`
- `paper/build.sh`
- `paper/references.bib`
- `src/README.md`
- `src/experiments/README.md`
- `src/experiments/fill_paper_tables.py`
- `docs/progress.md`

## Experiments Actually Run

- 本轮未新增数值实验。
- 已运行 `python src/experiments/fill_paper_tables.py --paper paper/main.tex`，验证代码支撑表格可以回填到主文。
- 已运行 `python src/figures/run_all_figures.py --out-dir paper/fig`，重新生成当前论文使用的图以及仓库中保留的旧图文件。
- 已多次运行 `bash paper/build.sh`，确认完整构建链在当前环境下可稳定执行。

## Figures/Tables Actually Regenerated

- 本轮重新生成了以下当前论文直接使用的图：
  - `prompt_privacy_operating_points.png`
  - `agent_propagation_curves.png`
  - `agent_pipeline_summary.png`
- 本轮将 `src/experiments/fill_paper_tables.py` 改为可以回填以下代码支撑表格：
  - Table III `tab:per`
  - Table V `tab:utility`
  - Table VIII `tab:pi_sensitivity`
  - Table XI `tab:propagation`
  - Table XII `tab:latency`

## Major Claim Validation Status

- Claim: prompt privacy mediation can reduce exposure while retaining more utility than naive redaction baselines  
  - 状态：部分验证
  - 依据：Table III、Table V、Figure `prompt_privacy_operating_points.png` 由当前 CSV 直接支撑。
  - 缺口：仍然缺少完整端到端实验流水线脚本。

- Claim: policy-aware routing $\Pi$ creates an interpretable privacy--utility operating frontier  
  - 状态：部分验证
  - 依据：Table VIII 与 operating-points figure 有 CSV/脚本支撑。
  - 缺口：当前仓库没有更细粒度的 per-category policy-learning 实验。

- Claim: pre-inference mediation suppresses propagation across retrieval, memory, and tool boundaries  
  - 状态：部分验证
  - 依据：Table XI、主文 propagation figure、附录 deployment figure 都由当前 CSV/脚本支撑。
  - 缺口：仍是 controlled pipeline evidence，不是 production-scale long-horizon evidence。

- Claim: the framework is extensible to multimodal prompts  
  - 状态：部分验证
  - 依据：主文有 multimodal table，方法与附录叙述一致。
  - 缺口：当前仓库没有完整 OCR/multimodal 自动再生脚本。

- Claim: the framework is model-agnostic  
  - 状态：部分验证
  - 依据：主文有 cross-model table，正文已把结论控制在 controlled CPPB 条件下。
  - 缺口：当前仓库未提供 cross-model 自动再生脚本。

- Claim: the work is a deployment-method contribution rather than a formal privacy guarantee  
  - 状态：已验证
  - 依据：主文摘要、引言、limitations、conclusion 和附录都已经统一到这一定位，没有再把它写成 cryptographic / DP guarantee paper。

## Unresolved Blockers

- 多个 empirical tables 仍未由当前仓库自动再生，只能被诚实表述为 controlled manuscript results。
- 版面与 typography 的最终人工 polish 还没做完。
- cross-model、multimodal、hard-case 等表目前仍缺少最小自动再生映射。

## Build Status

- 已通过 `bash paper/build.sh` 完成完整构建链验证，并成功生成 `main.pdf` 与 `appendix.pdf` 两个文件。
- 当前 `paper/main.log` 与 `paper/appendix.log` 中都没有未解析引用或交叉引用警告。
- 当前仍存在少量 IEEE 模板常见的 underfull/overfull 提示，但不属于断链错误。
