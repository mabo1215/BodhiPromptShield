# Revision Status（修改进度）

根据 `docs/revision_suggestions.tex` 的审稿意见整理。每个修改点一段话概括，并标注修改进度与修改说明。

---

## 一、需要修改的要点概括

1. **与 prior work 的冗余/自重叠风险（Major 1）**  
   审稿人要求明确说明：prior 贡献、本文保留/删除/新增内容、为何不是简单改写。需在 Introduction 增加子节 “Differences from Prior DBN/PB-based Work”，并给出对比表（Aspect, Prior Work, This Work, Why the difference matters），覆盖隐私机制、边界构造、DBN 作用、序列/词典方法、理论主张、数据集、实验、复用 vs 新增材料。

2. **新颖性未充分隔离（Major 2）**  
   审稿人指出：环/椭球假设为何合理、在何种假设下成立、对假设违背的敏感性、性能提升多少可归因于新边界，均未充分回答。要求增加消融实验，对比 (A) DBN/PB 边界、(B) 无边界、(C) 仅内部分类中心、(D) 环+内中心、(E) 环+内中心+GDIFSEA。

3. **数学表述不够严谨（Major 3）**  
   审稿人指出：差分隐私表述不精确、记号不一致、部分公式缺乏推导、margin 几何与 Hessian/隐私噪声关系不清晰、环/椭球与分类器联系松散。要求将理论部分改写为三层（表示层、几何层、学习层），并给出形式化命题：在假设 $\mathcal{A}_1,\ldots,\mathcal{A}_k$ 下，标准化文档向量以高概率落在 $r_1 \leq \|z\|_2 \leq r_2$ 的壳内，并说明该命题如何影响分类器设计。

4. **隐私保证与算法实现关系不清（Major 4）**  
   审稿人要求明确：发布机制、敏感度定义、邻接关系、组合会计。需增加子节 “Formal Privacy Mechanism and Adjacency Definition”，明确数据集邻接、$\Delta f$、$\mathcal{M}(D)=f(D)+\eta$、$f$ 在实现中是什么、噪声注入位置、隐私适用于训练/推理/发布、多次发布是否需组合。

5. **实验证据不够 decisive（Major 5）**  
   审稿人要求：强基线（如 TF-IDF+线性 SVM、CNN/RNN、Transformer、prior DBN/PB 若可得）、多次运行均值和标准差、显著性检验、运行时间与内存、隐私–效用曲线。为降低抄袭/重叠风险，可改用其他数据做实验；数据可挖掘 `C:\source\REAEDP\data`（如 CDC BRFSS、经济指标等公开 CSV）或标准 NLP 文本数据。

6. **写作质量（Major 6）**  
   审稿人要求：全篇技术语言改写、去除口语化与模糊表述、每个符号定义一次且一致使用、避免在多处重复同一动机。

7. **自重叠风险缓解（伦理要求）**  
   审稿人建议：在 Introduction 与 Related Work 中突出引用 prior DBN/PB 论文、增加 “relationship to prior work” 子节、继承的背景文字全部重写而非轻度编辑、不复用 prior 图表除非明确引用并说明、明确说明与 prior 在数据集/实验/章节上的重叠。并给出建议的披露句。

8. **按节修订清单（Introduction / Related Work / Method / Theory / Experiments / Conclusion）**  
   审稿人给出了各节的逐条清单（缩短动机、贡献一句一可验证主张、Related Work 分块与对比表、Method 假设与算法分离与伪代码、Theory 命题与假设、Experiments 基线/消融/统计/可复现、Conclusion 收敛表述与局限）。

---

## 二、已完成的修改

| 修改点 | 修改进度 | 修改说明 |
|--------|----------|----------|
| **Major 1：与 prior 的对比与披露** | 已完成 | 在 Introduction 中新增子节 “Differences from Prior DBN/PB-based Work”，包含审稿要求的披露句（三点差异 + 重写与新增实验说明），并增加 Table~\ref{tab:prior-vs-this}，列 Aspect / Prior work / This work / Why the difference matters，覆盖隐私机制、边界构造、DBN 作用、序列/词典方法、理论主张、数据集、实验、复用 vs 新增。 |
| **Major 4：正式隐私机制与邻接定义** | 已完成 | 在 Preparation 部分（差分隐私之后）新增子节 “Formal Privacy Mechanism and Adjacency Definition”，给出：数据集邻接 $D \sim D'$、敏感度 $\Delta f = \max_{D \sim D'} \|f(D)-f(D')\|_1$、发布机制 $\mathcal{M}(D)=f(D)+\eta$ 与 Laplace 尺度 $\Delta f/\varepsilon$；并说明 $f$ 在实现中为 ppSVM/ppSGD 的（聚合）输出、噪声加在发布输出上、隐私适用于发布结果、多次发布需组合。 |
| **自重叠缓解（披露与引用）** | 已完成 | 在 “Differences from Prior DBN/PB-based Work” 中已包含建议的披露句；prior 论文~\cite{ma2021privacy} 在 Introduction 与表中明确引用；对比表明确 “Reused vs new” 一行。 |
| **贡献列表精简** | 已完成 | Introduction 中五项贡献已改为每项一句、可验证式表述（分布理论、GDIFSEA、不完整标注、不均衡与正样本、模型综合）。 |
| **实验/数据与 REAEDP** | 部分完成 | 在 “Training result from incomplete annotation data” 的 Setup 后增加 “Data availability and additional datasets” 段：说明为减少与 prior 重叠，主文使用 COVID-19 与 Medical Transcription，并注明可使用额外公开数据（含 REAEDP/data：CDC BRFSS、经济指标、flight-delay 等）做消融与敏感性分析；表格中 “Datasets” 行已指向 “Section V” 及额外数据。 |
| **Major 2：新颖性隔离与消融** | 结构已完成 | 在实验部分新增 “Ablation study” 子节及 Table~\ref{tab:ablation}，明确五组配置 (A) DBN/PB、(B) 无边界、(C) 仅内中心、(D) 环+内中心、(E) 环+内中心+GDIFSEA；(A) 注明 “From prior paper if comparable”；(B)--(D) 为 placeholder，待补数值。 |
| **Major 3：理论三层结构与形式化命题** | 已完成 | 在 “Probability Distribution of Covid19 Dataset...” 中：增加三层结构（表示层/几何层/学习层）；给出 Assumption 1--3 与 **Proposition (Shell concentration)**，$r_1 \leq \|\mathbf{z}\|_2 \leq r_2$ 的显式 $r_1,r_2$；并说明学习层如何利用该几何（内部分类中心 + margin + 隐私加在输出）。 |
| **Major 5：强基线与统计报告** | 结构已完成 | 新增 “Baselines and statistical reporting” 子节及 Table~\ref{tab:baselines}（placeholder）：列出 TF-IDF+线性 SVM、RNN/CNN、Transformer、prior DBN/PB、IBPPSVM；说明将补充 mean±std、显著性、运行时间/内存、隐私–效用曲线；数据可选用 REAEDP 或标准 NLP 语料。 |
| **Related Work 分块与对比表** | 已完成 | 新增子节 “Privacy-preserving NLP and DP for text models”、“SVM and privacy-preserving classification”，以及 **Table (tab:related-comparison)**：Assumptions / Privacy mechanism / Cost 对比 Prior DBN/PB 与 This work。 |
| **Method：假设与算法分离** | 已完成 | 在 Preparation 部分 “Formal Privacy Mechanism” 之前新增 **“Assumptions”** 子节，列出 (A1)--(A4)（文档向量、shell 浓度、不完整标注、隐私要求），并指向 Proposition 与下文算法。伪代码已有（GDIFSEA、ppSVM），未再拆统一 pipeline。 |
| **Conclusion：收敛表述与局限** | 已完成 | 重写 Conclusion：首段收敛为 IBPPSVM 与分布驱动边界、形式化命题、实验概括及与 prior 关系；**Limitations** 段写明 shell 假设可能不成立、消融/基线进行中、统计与隐私–效用仅部分报告、可复现性；**Future work** 段列出 (i) 完整消融 (ii) 强基线与额外数据 (iii) 敏感性分析 (iv) 领域知识库。 |

---

## 三、未完成或部分完成的修改

| 修改点 | 修改进度 | 修改说明 |
|--------|----------|----------|
| **Major 2：消融数值** | 未完成 | 表~\ref{tab:ablation} 中 (B)(C)(D) 及 (A) 的 prior 数值尚未填入；需实际跑 (B)--(E) 或引用 prior 论文可比结果。见下方“需您决策”。 |
| **Major 5：基线数值与统计** | 未完成 | 表~\ref{tab:baselines} 为 placeholder；需跑 TF-IDF+SVM、RNN/Transformer 等并报告 mean±std、显著性、时间/内存、隐私–效用。见下方“需您决策”。 |
| **Major 6：全篇写作与符号** | 未完成 | 尚未全篇技术语言改写及“每符号一定义、一致使用”的系统检查；计划按 section-by-section 清单逐节润色并统一符号表。 |

---

## 四、需您决策的事项（已按您的选择更新）

1. **消融 (A) DBN/PB** → **已选：选项 C，并已完成**  
   表中 (A) 行已从 prior 论文 [ma2021privacy] 的 Table 1（MIMIC, $\nu=0.01$ → Val 0.8495）与 Fig.9（COVID-19 train 0.90）填入。脚本 \texttt{src/experiments/prior\_ablation\_table.py} 可复现该来源并输出 LaTeX 片段；可选 \texttt{--reaedp} 用 REAEDP 数据跑占位基线。

2. **基线实验** → **已选：用 REAEDP/data 做一部分实验**  
   基线实验将使用 **REAEDP/data**（如 CDC BRFSS、经济指标、flight-delay 等）做一部分实验（例如表格特征 + 分类），与 COVID-19/Medical Transcription 或标准文本数据配合。论文中 “Baselines and statistical reporting” 已更新为采用 REAEDP 数据。

3. **消融 (B)(C)(D) 的实现顺序** → **已选：先 E、D，再 C、B**  
   实现顺序：先做 **(E) 环+内中心+GDIFSEA** 与 **(D) 环+内中心**，再做 **(C) 仅内中心**、**(B) 无边界**。论文 Ablation 小节已注明该顺序。  

---

## 五、数据与实验（REAEDP 与其它）

- **REAEDP 数据路径**：`C:\source\REAEDP\data`。当前包含：CDC BRFSS 2024、经济指标、flight-delay、house-prices、home-credit、world-air-quality、tabular-feature-engineering 等 CSV；多为表格数据，可直接用于与 prior 不同的实验场景（如表格型 DP 或特征分析）。  
- **文本实验**：主文仍以 COVID-19 与 Medical Transcription 为主；为隔离新颖性并避免抄袭，新实验可增加：  
  - 标准 NLP 文本分类数据集（如 20 Newsgroups、AG News、DBpedia 等），和/或  
  - 从 REAEDP 或其它公开来源构造的文本/表格混合设置（如用 BRFSS 等做特征或分组变量）。  
- **建议**：在 “Data availability and additional datasets” 中已写明使用 REAEDP 等额外数据；实际跑消融与基线时，在 `revision_status.md` 中更新 “Major 2”“Major 5” 的修改进度与结果摘要。

---
*最后更新：已完成 Major 3（理论三层+命题）、Related Work 分块与对比表、Method Assumptions、Conclusion（Limitations+Future）、Ablation 与 Baselines 小节结构及占位表；Major 2/5 的数值与 Major 6 全篇改写仍待完成；“需您决策”见第四节。*
