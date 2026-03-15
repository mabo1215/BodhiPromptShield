# IBPPSVM 论文修改计划（相对已发表论文 MTAPBoMa 的差异化）

## 一、已发表论文 MTAPBoMa 需避开的核心内容

**文献**：*A Privacy-preserving Word Embedding Text Classification Model Based On Privacy Boundary Constructed By Deep Belief Network*（Multimedia Tools and Applications，MTAPBoMa.pdf）

### 1.1 核心方法与术语（文中需避免与之雷同或混淆）

| 项目 | MTAPBoMa 已发表内容 | 本稿应采取的立场 |
|------|---------------------|------------------|
| **边界来源** | 使用 **Deep Belief Network (DBN)** 计算 Independence Degree (ID)，得到 **Privacy Boundary (PB)**；PB 用于采样与生成隐私噪声 | **不采用 DBN，不引入 PB 概念**；边界由可推导的分布结构与算法给出 |
| **独立性/频繁序列** | **PPDIFSEA**（Privacy-preserving Distribution and Independent Frequent Subsequence Extraction Algorithm），与 DBN 结合用于求 ID 与验证隐私 | 明确区分：本稿为 **GDIFSEA**（高斯分布+独立支撑/频繁闭子串），**无 DBN、无 PB**，不称 PPDIFSEA |
| **分类与隐私框架** | **WECPPSVM**（Word Embedding Combination Privacy-preserving SVM）；四步：DBN 独立性计算→PB→Word embedding→SVM 训练→加噪声并用 PPDIFSEA 验证 | 本稿为 **IBPPSVM** + **ppSVM/ppSGD**，隐私通过 **差分隐私（ε-DP/Laplace）** 与 **高维分布理论** 实现，**无 DBN 步骤** |
| **噪声与隐私** | 从 **PB** 采样生成隐私噪声，隐私预算 (Privacy Budget) 控制保护级别 | 本稿采用 **差分隐私**（Laplace 噪声、敏感度 Δf、ε），不采用“从 PB 采样”的表述 |

### 1.2 已发表论文的主要贡献（本稿不重复强调为“首创”）

- 将 DBN 插入独立性计算，预测输入分布并得到 Privacy Boundary。
- 在 PB 范围内采样，生成隐私噪声，在保证分类精度的前提下减少隐私泄露。
- 结合 SVM 降低词嵌入文本分类模型的隐私泄露风险。
- 使用 PPDIFSEA 验证隐私噪声是否合适。

本稿修改时：**不在摘要/贡献中声称“首次用 DBN 构造隐私边界”或“首次提出 PPDIFSEA/WECPPSVM”**；若引用 MTAPBoMa，仅作对比与区分。

---

## 二、本稿主方向创新点（修改后应突出的主线）

### 2.1 主创新方向概括

**“Improving Boundary”** 在本稿中的含义应明确为：

- **边界不由 DBN 学习得到**，而由 **可推导的文档/词向量高维概率分布**（环结构、椭球壳、半径与方差关系）与 **内部分类中心 (internal classification center)** 确定；
- 隐私保护依赖 **差分隐私（ε-DP / Rényi-DP）** 与 **SGD 下的隐私噪声**（如式 (2) 中 \(N_{Privacy Noise}\)），**不依赖 DBN 或 PB**；
- 在 **不完整标注、极不均衡、仅正样本** 等实际场景下，通过 **GDIFSEA + 关键词过滤 + 遗传算法包优化 + 两阶段分类器** 提升边界识别与分类效果。

即：**分布驱动的边界 + 差分隐私 + 小标注/不均衡下的算法组合**，与“DBN+PB+PPDIFSEA”形成清晰区分。

### 2.2 建议列出的五条贡献（与 MTAPBoMa 无重叠）

1. **高维分布理论**：从文档向量定义与中心极限定理推导词嵌入/文档向量在高维空间的概率分布（环/椭球壳结构，半径与方差关系），并用 COVID-19 等数据验证；见 Appendix 降维与分布小节。
2. **GDIFSEA**：基于 N-GRAM 相关图与**独立支撑/频繁闭子串**的 Gaussian Distributed Independent Frequently Subsequence Extraction Algorithm，用于优化 MWU 与词典构建，**不依赖 DBN，不产生 PB**。
3. **不完整标注下的包优化与两阶段分类**：基于融合矩阵的遗传算法包优化、经验公式 \(K=(1-\mathrm{prob})/\log(1-p)\)、两组件分类器（先包内预分类再再分类），提升不完整标注下的性能。
4. **极不均衡与仅正样本**：结合**内部分类中心**的边界判断与**关键词提取**串联过滤，应对 95%+ 负样本、仅正样本标注的 MCC 场景。
5. **小标注下的模型综合**：以少量人工标注为反馈，更新监督与无监督模型，实现持续改进（与 DBN 驱动的 PB 采样无直接对应关系）。

### 2.3 术语与表述规范（避免与 MTAPBoMa 混淆）

- **边界**：统一用 “boundary of internal classification center” / “classification margin” / “high-dimensional ring (ellipsoid) structure”；**不要** 使用 “Privacy Boundary (PB)” 或 “boundary constructed by DBN”。
- **算法名**：仅使用 **GDIFSEA**；不出现 PPDIFSEA、WECPPSVM；可保留 ppSVM、ppSGD、IBPPSVM。
- **隐私**：统一用 “differential privacy”、“ε-differential privacy”、“Laplace noise”、“sensitivity”、“\(N_{Privacy Noise}\)”；**不要** 写 “noise sampled from privacy boundary” 或 “DBN-based privacy boundary”。

---

## 三、具体修改任务清单

### 3.1 摘要与标题

- [ ] **标题**：保持或微调为突出 “Improving Boundary” 的**分布+内部分类中心**含义，避免与 “Privacy Boundary Constructed By DBN” 相近。
- [ ] **摘要**：重写时明确 (1) 高维分布理论 (2) GDIFSEA (3) 差分隐私（非 DBN/PB）(4) 不完整标注/极不均衡下的包优化与两阶段分类 (5) 小标注模型综合；**删除或改写** 任何“基于 DBN 的边界”“PB”“PPDIFSEA”的表述。

### 3.2 Introduction

- [ ] **贡献列表**：与上文 2.2 五条贡献对齐；明确写 “we do **not** use Deep Belief Network or Privacy Boundary”。
- [ ] **动机**：强调医疗/COVID-19 场景下**不完整标注、极不均衡、仅正样本**带来的边界识别难点，以及**可解释的分布结构**在边界上的作用。

### 3.3 Related Work

- [ ] **新增小节或段落**：“Comparison with DBN-based privacy boundary methods” 或 在 “Privacy preservation for SVM / word embedding” 中增加：
  - 引用 MTAPBoMa（若已发表），简述其采用 DBN 构造 PB、PPDIFSEA、WECPPSVM；
  - 明确本稿差异：**无 DBN、无 PB**；边界来自**高维分布理论 + 内部分类中心**；隐私来自**差分隐私**；序列与词典方法为 **GDIFSEA**。
- [ ] 确保 Related Work 中 **Word embedding、VSM、SVM、差分隐私** 的综述不依赖 DBN/PB 作为本稿创新点。

### 3.4 方法部分（Preparation / Model）

- [ ] **差分隐私**：保留并强化 Definition (ε-DP)、Laplace 噪声、敏感度；**不** 出现 “privacy boundary”“sampling from boundary”“DBN” 的表述。
- [ ] **GDIFSEA**：在首次出现处增加 1–2 句与 “DBN-based independence / PPDIFSEA” 的对比，强调本方法为**纯序列/图与独立支撑**，不依赖神经网络边界。
- [ ] **内部分类中心与边界**：统一使用 “internal classification center”“margin”“ring structure”；配图/图注中若有 “boundary”，改为 “classification boundary” 或 “margin”，避免 “Privacy Boundary”。

### 3.5 实验与讨论

- [ ] **实验设计**：若与 MTAPBoMa 使用相同或相近数据集，在实验小节中简要说明**设置差异**（如：本稿用 ppSVM/ppSGD+差分隐私+GDIFSEA，无 DBN/PB），避免审稿人误认为重复。
- [ ] **消融/对比**：可增加 “without differential noise”“without GDIFSEA”“without two-stage classifier” 等，突出本稿独有组件；**不要** 做 “without DBN” 的消融（因本稿本身无 DBN）。

### 3.6 参考文献与术语一致性

- [ ] 若已接受/发表，将 MTAPBoMa 加入 `references.bib`，并在 Related Work 与对比段落中引用。
- [ ] 全文搜索 “DBN”“Privacy Boundary”“PB”“PPDIFSEA”“WECPPSVM”，确保仅在对 MTAPBoMa 的对比或历史工作中出现，本稿方法描述中**一律不使用**。

---

## 四、修改优先级建议

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P0 | 摘要与贡献重写；术语规范（无 DBN/PB/PPDIFSEA） | 直接避免与已发表论文重合 |
| P1 | Related Work 增加与 MTAPBoMa 的对比段落；GDIFSEA 与 DBN 方法区分 | 明确创新差异 |
| P2 | Introduction 动机与贡献与 2.2 对齐；方法部分边界/隐私表述统一 | 主线清晰 |
| P3 | 实验对比与消融；参考文献加入 MTAPBoMa | 增强说服力 |

---

## 五、小结

- **避开**：DBN、Privacy Boundary (PB)、PPDIFSEA、WECPPSVM、从 PB 采样噪声。
- **主方向**：**高维分布理论下的边界（环/椭球壳）+ 内部分类中心 + 差分隐私 + GDIFSEA + 不完整标注/极不均衡下的包优化与两阶段分类 + 小标注模型综合**。
- **输出**：按本计划在 `paper/main.tex` 及相关小节逐项修改，完成后可再通读摘要与贡献，确保与 MTAPBoMa 无重叠、主创新点一目了然。
