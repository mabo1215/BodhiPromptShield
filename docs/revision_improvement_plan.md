# BodhiPromptShield 返修改进计划

本文档根据 `docs/revision_suggestions.tex` 中 ACM CCS 2026 B Paper #541 的两份评审意见整理。总体判断是：当前稿件不是简单补几句话即可解决的问题，而是需要把“威胁模型、实际实现、可测指标、实验主张、论文叙事”重新对齐。返修目标应从“证明一个强安全系统”调整为“给出一个边界清晰、证据充分、面向 agent 管线传播控制的系统原型与评估协议”。

## 1. 总体诊断

两位 reviewer 的共同关切集中在五条主线：

1. 威胁模型没有被充分 operationalize。三类 adversary 被命名，但实验没有逐一对应，尤其是 secure mapping table adversary 和 adaptive prompt adversary。
2. SPE 的含义不够清楚。当前写法容易把 Stage-wise Propagation Exposure 同时当作部署卫生指标和安全恢复阻力指标，但 reviewer 认为它本质上更接近 surface-form propagation metric。
3. 形式化过重而实现证据偏弱。`R_prop`、policy loss、权重等符号承担了过多叙事重量，但实际系统主要是规则、NER、启发式 routing 和 exposure measurement。
4. 技术增量需要重新定位。typed placeholders、semantic abstraction、delayed restoration 与 Presidio 或企业 redaction stack 的距离不够清楚，secure symbolic mapping 又缺少更具体的安全面说明。
5. 评估规模与外部有效性不足。CPPB 是作者自建 controlled benchmark，TAB transfer、multimodal OCR、cross-model validation、hard cases 等 supporting slices 目前还不足以支撑强泛化声明。

因此，修改应优先收紧 claim，而不是继续扩大不够成熟的强 claim。核心叙事应变为：

> BodhiPromptShield is a deployment-oriented pre-inference mediation layer that reduces explicit surface-form propagation across agent boundaries under controlled conditions. It does not provide formal recovery resistance, end-to-end privacy guarantees, or complete adversarial robustness.

## 2. 修改优先级

### P0：必须处理，否则弱拒理由仍然成立

- 将三类 adversary 映射到具体实验或明确标注为未完全评估。
- 明确 SPE 只衡量 explicit surface-form propagation，不上界 paraphrase、normalization、CoT elicitation、context inference 或 mapping-table compromise 下的恢复概率。
- 精简或降级 `R_prop` 等未直接估计的形式化内容，避免让读者期待一个没有实际测量的安全风险量。
- 重新定义 secure symbolic mapping 的 threat surface，包括 token format、table visibility、partial table read、cross-session isolation、restoration boundary 和 audit assumption。
- 把 CPPB 明确写成 paper-specific controlled benchmark，而不是成熟社区 benchmark。

### P1：强烈建议处理，用来提升论文成熟度

- 增加或前移 TAB transfer，并诚实解释 privacy-utility trade-off 和 precision drop。
- 增加一个轻量 LLM/privacy judge 或 classifier baseline 的讨论，若不能执行完整实验，至少给出 protocol 和 pilot。
- 分离 deployed agent pipeline threats 与 mediation system threats。
- 补充 naive countermeasure 分析：tenant isolation、access control、scoped retrieval/memory/logs 为什么仍不能完全解决 within-agent propagation。
- 调整 Introduction，增加一个 pedagogical figure 或 running example，让读者第一次阅读即可理解 setting、threat、mechanism、evaluation。

### P2：版面、表达与证据展示优化

- 放大过小图表，确保图中文字接近 caption font size。
- 所有术语首次出现时显式定义，包括 CPPB、PER、SPE、AC、TSR、UPR、policy profile、restoration boundary。
- 将 benchmark 构造细节移到 appendix/data card，列出 32 templates 的来源、selection、sensitive span injection、quality check。
- cross-model validation 不应匿名到无法判断 portability claim，至少披露 model family、size class、hosting mode 或开源/闭源属性。
- multimodal/VLM claim 要降级为 OCR-mediated multimodal prompt mediation，除非真实接入 VLM loop。

## 3. 章节级改写计划

### Abstract

- 删除或弱化任何可能被读成 formal security guarantee 的措辞。
- 保留最硬的 controlled evidence：pre-inference mediation reduces explicit propagation across retrieval, memory, and tool boundaries while preserving utility under CPPB。
- 增加一句 scope guard：results are controlled surface-form propagation measurements, not recovery-resistance or formal privacy guarantees。

### Section 1: Introduction

改写目标：让 setting、痛点、最小反例和贡献边界在第一页成立。

需要新增或强化：

- 一个端到端 running example，例如 reimbursement assistant：invoice OCR -> retrieval -> memory -> expense tool。
- naive countermeasures 段落：tenant isolation 和 access control 能减少跨用户泄漏，但不能阻止同一授权 agent 内部把 raw sensitive spans 复制到 retrieval query、memory、tool logs。
- 贡献重新表述为 propagation-control framing、middleware design、controlled benchmark protocol 和 bounded evidence，而不是 broad LLM/VLM privacy solution。
- 明确 CPPB 是 controlled evaluation construct。

### Section 2: Problem Definition and Threat Model

改写目标：把 threat model 从“命名 adversary”改成“capability + observable + evaluated claim”。

建议新增表格：

| Threat class | Capability | Protected surface | Current experiment | Claim status |
| --- | --- | --- | --- | --- |
| Honest-but-curious downstream observer | Sees retrieval queries, memory writes, tool args, logs | Raw sensitive spans | PER/SPE across agent stages | Directly evaluated |
| Adaptive prompt adversary | Uses homoglyphs, paraphrase, mixed language, unsafe restoration trigger | Span detector and restoration policy | Surface-form evasion probes | Partially evaluated |
| Mapping-table adversary | Reads tokens, partial logs, or partial table rows | Symbolic mapping table and restoration credentials | Design analysis plus restoration-boundary test | Not fully evaluated |
| Context inference adversary | Infers attributes from remaining context | Non-surface private attributes | Small inference probe or future protocol | Limited or future |

同时处理 `R_prop`：

- 若保留，降级为 conceptual deployment risk view。
- 不再把 SPE 称为 `R_prop` 的强 proxy。
- 写清楚：SPE is a measurable lower-level operational metric for explicit released spans at stage boundaries。

### Section 3: Related Work

改写目标：更直接面对“这和 de-identification middleware 有什么不同”。

需要加强对比：

- Presidio / enterprise redaction：document or ingress-level de-identification。
- BodhiPromptShield：stage-aware mediation, restoration timing, policy routing across retrieval/memory/tool boundaries。
- 诚实承认 typed placeholders 和 mapping 思路并非全新，论文增量在 agent-boundary propagation framing 和 evaluation protocol。
- 增加 lightweight LLM judge、privacy classifier、policy-violation classifier 作为 relevant baseline family 或未来 baseline。

### Section 4: Proposed Framework

改写目标：从过度形式化转成实现可核查的系统描述。

需要修改：

- 将 policy objective 的数学符号压缩到必要程度。
- 对 routing table 说明每个输入信号从哪里来，如何校准，哪些是 hand-written rules。
- secure symbolic mapping 增加具体设计说明：
  - token format：opaque per-session token，例如 `BPS_MAP_<session_nonce>_<counter>`，不编码实体类型或原文。
  - table separation：mapping table 不进入 prompt、retrieval index、agent memory 或 general logs。
  - isolation：per-session namespace，token cannot be linked across tasks without table access。
  - partial read risk：若 attacker 读到某 session 的 table rows，可恢复该 session 中对应 spans；不能声称 uncompromised confidentiality。
  - restoration：only authorized tool boundary can dereference tokens。
  - audit：append-only restoration log with no raw value unless strictly required。
- VLM 相关措辞改为 OCR-mediated multimodal unless actual VLM reasoning loop is evaluated。

### Section 5: Experimental Setup

改写目标：让 controlled benchmark、metrics 和 baselines 的身份清楚。

需要修改：

- CPPB 首次出现时说明：paper-specific controlled benchmark, released with manifest, not an established community benchmark。
- PER、SPE、AC、TSR 等指标逐一定义，标注哪些是 privacy exposure metrics，哪些是 utility metrics。
- SPE 定义旁边加入 limitation：does not measure semantic recovery, paraphrase leakage, or attribute inference。
- Baselines 增加分层：
  - naive masking / regex；
  - Presidio-class de-identification；
  - enterprise staged redaction；
  - optional or protocol-level LLM/privacy judge baseline。
- TAB transfer 提前到 setup 中说明，避免像“最后补充的外部结果”。

### Section 6: Results and Discussion

改写目标：把结果按 reviewer 关心的问题重新排序。

建议顺序：

1. Main controlled propagation result: retrieval/memory/tool SPE。
2. Direct exposure and utility trade-off: PER + AC/TSR。
3. Stronger baseline comparison: Presidio-class and enterprise staged redaction。
4. External transfer: TAB precision drop and residual exposure trade-off。
5. Threat-aligned robustness: adaptive evasion, restoration boundary, context inference。
6. Supporting slices: ablation, policy sensitivity, multimodal OCR, cross-model, runtime。
7. Failure cases and deployment interpretation。

对 TAB precision drop 的解释需要具体回答 reviewer 541A 的问题：

- 分析 precision drop 是 span detector、routing policy、还是 CPPB distribution bias 导致。
- 至少给出 error taxonomy：legal entity boundary mismatch、quasi-identifier over-detection、category mapping mismatch、policy abstraction causing non-standard anonymization label。
- 不要只说 deliberate trade-off，要展示哪部分 trade-off 是设计导致，哪部分是模型/数据 mismatch。

### Section 7: Limitations

改写目标：把 reviewer 指出的边界主动写清。

必须包含：

- SPE 不衡量 recovery resistance。
- adaptive robustness 是 partial。
- secure mapping relies on deployment hygiene and key management。
- CPPB 是 controlled benchmark，外部泛化仍有限。
- multimodal track 当前主要是 OCR-mediated，不等于完整 VLM-loop privacy validation。
- cross-model slice 需要披露 model family 或完整版本日志才可支撑更强 portability claim。

## 4. 实验补强计划

### E1. Threat-to-experiment mapping

最小可行版本：

- 在主文新增 threat map table。
- 在 appendix 增加每类 adversary 的 exact capability、input mutation、success metric。
- 对不能完整评估的 adversary 标注 future validation，不强行 claim。

推荐指标：

- downstream observer：PER, SPE。
- adaptive prompt adversary：attack success rate, residual exposure under mutation, recovery after normalization。
- restoration adversary：unauthorized restoration rate, token leakage count, restoration event audit completeness。
- mapping-table adversary：design-level analysis plus partial-table read scenario。
- context inference adversary：attribute inference accuracy from sanitized prompt。

### E2. SPE interpretation audit

需要在实验表格和正文中统一措辞：

- 用 `explicit surface-form propagation` 描述 SPE。
- 避免使用 `security guarantee`、`bound recovery`、`resistant to inference` 等强措辞。
- 若讨论 recovery，需要独立实验，不从 SPE 推导。

### E3. External benchmark and baseline

优先级：

1. TAB text anonymization transfer：主文前移，报告 precision/recall/F1、residual exposure、non-sensitive retention。
2. AI4Privacy 或 PII masking corpus：用作 detection transfer 或 lightweight judge baseline。
3. AgentDojo 或 PrivacyLens：若时间不足，作为 protocol-level future validation，不要硬塞不完整结果。
4. OCR public slices：CORD、FUNSD、SROIE 可作为 appendix supporting evidence，但 title/claim 要对应 OCR-mediated scope。

需要产出的 error analysis：

- TAB 上 BodhiPromptShield vs Presidio+NER 的 precision/recall 差异。
- routing policy 是否造成 over-sanitization。
- detector 是否在 legal text domain 出现 category shift。
- CPPB templates 是否让方法在 within-benchmark 下显得过强。

### E4. Secure symbolic mapping evaluation

最小可行版本：

- 给出 design model 和 threat table。
- 执行 restoration-boundary test：authorized boundary restores, unauthorized retrieval/memory/log boundary does not。
- 执行 token unlinkability sanity check：不同 session 的同一 raw value 生成不同 opaque token。

不要声称：

- mapping table compromise 后仍安全。
- tokens 提供 cryptographic unlinkability，除非实现和证明足够完整。
- audit log 可以阻止泄漏，只能检测和追责。

### E5. Cross-model disclosure

如果无法公开具体模型名：

- 至少公开 family class，例如 open-weight instruction model、closed hosted model、multimodal-capable hosted model。
- 披露 size band、temperature、prompt template、API/local runtime、date or snapshot。
- 将 claim 改为 alias-level portability sanity check。

## 5. 作者回复准备

### 对 Reviewer 541A 的核心回复

1. 三类 adversary 如何映射实验？
   - 回答：新增 threat-to-evaluation table。honest-but-curious observer 由 PER/SPE 直接评估；adaptive prompt adversary 由 surface-form evasion probes 部分评估；mapping-table adversary 由 secure mapping threat surface 和 restoration-boundary tests 说明，完整 table-compromise evaluation 作为未覆盖范围。

2. TAB precision drop 来自哪里？
   - 回答：补充 TAB error taxonomy，区分 detector domain shift、legal entity boundary mismatch 和 policy routing 的 intentional privacy-utility trade-off。

3. 低 SPE 如何面对 paraphrase、normalization、CoT elicitation？
   - 回答：SPE 不上界这些 recovery attacks，只衡量 explicit surface-form propagation；相关攻击需要单独 adversarial/inference experiments。

4. cross-model validation 是否可披露 model family？
   - 回答：补充 model family、size/runtime class 或将其降级为 alias-level portability check。

### 对 Reviewer 541B 的核心回复

1. 形式化与实现不一致。
   - 回答：精简形式化，降级 `R_prop` 为 conceptual framing，主文以 implemented pipeline、PER/SPE/utility metrics 为中心。

2. span identification 没有和更简单替代方法比较。
   - 回答：补充 Presidio-class、enterprise staged redaction，并增加 lightweight privacy judge/classifier baseline 或 protocol。

3. ordinary enterprise isolation 后还剩什么 threat？
   - 回答：新增 deployment motivation：tenant isolation 控制跨租户边界，但 within-agent propagation 仍会把同一用户授权数据复制到 retrieval/memory/tool/log surfaces。

4. CPPB 和 metrics 表达像通用标准。
   - 回答：全文改称 controlled benchmark and paper-specific metrics，并在 appendix/data card 公开模板、注入、质量检查。

5. 论文更像 early prototype。
   - 回答：收紧 claim 为 controlled systems prototype with bounded evidence，不主张成熟完整安全方案。

## 6. 文稿执行清单

- [x] Abstract 加入 controlled/surface-form/scope guard。（main.tex 摘要末句已显式声明 "controlled systems results about explicit surface-form propagation, not formal privacy guarantees, recovery-resistance bounds, or broad public-benchmark transfer claims"。）
- [x] Introduction 增加 running example 和 enterprise isolation 之后的 residual threat。（reimbursement assistant running example + tenant isolation/access control 之后的 within-agent residual threat 段落已落地。）
- [x] Threat Model 增加 threat-to-experiment table。（四类 adversary 的 capability/protected surface/experiment/claim-status 表已存在。）
- [x] 删除、压缩或降级未测量的 `R_prop`、loss weight 叙事。（R_prop 已降级为 conceptual deployment-risk view，SPE 不再被称为其强 proxy。）
- [x] SPE 全文统一解释为 explicit surface-form propagation。（main.tex 多处统一为 explicit surface-form propagation metric，非 recovery-resistance。）
- [x] Secure Mapping 增加 token、table、partial read、session isolation、restoration boundary、audit 描述。（threat-surface 表 + 本轮新增 executed sanity check `tab:mapadv`。）
- [x] Related Work / Setup 增加 Presidio、enterprise redaction、LLM judge/classifier baseline 的差异讨论。（本轮新增 formal lightweight learned classifier 小节与 `tab:lightclf`；prompted judge 仍为 pilot。）
- [x] Experimental Setup 明确 CPPB 是 paper-specific controlled benchmark。（"CPPB remains a paper-specific controlled benchmark rather than a mature community benchmark" 已落地。）
- [~] Results 中前移 TAB transfer 并增加 precision drop error taxonomy。（precision-drop three-factor error taxonomy 已补；前移到 Experimental Setup 仍待版面允许时处理。）
- [x] Multimodal/VLM claim 降级为 OCR-mediated，除非补充真实 VLM loop。（标题/正文已收紧为 OCR-mediated multimodal inputs。）
- [x] Cross-model slice 披露 model family 或降级 claim。（本轮已补 family/size-class/hosting-mode 披露，claim 降级为 family-level portability check。）
- [~] Appendix 增加 CPPB template/data card、adversary protocol、baseline protocol。（data-card/release-card、adversary protocol、baseline protocol 已在 appendix；尚缺 appendix 内逐模板 inventory 摘要。）
- [x] 全文检查图表字号和术语首次定义。（本轮清理 appendix overfull/float，主文无大号告警；术语首用定义已就位。）

## 7. 建议的返修策略

如果时间有限，应优先做“收紧主张 + 对齐证据”的修改，而不是盲目扩展实验。两位 reviewer 的拒稿理由都不是单纯因为少一个实验，而是因为当前论文让读者期待了更强的安全论证、更广的 benchmark 泛化和更成熟的系统实现。

最稳妥的策略是：

1. 承认贡献是 deployment-oriented propagation mediation，而不是 formal privacy mechanism。
2. 把 SPE 放回它真正能支持的位置：显式表面传播暴露指标。
3. 把 secure mapping 从“新安全组件”改写成“有明确假设的 restoration governance mechanism”。
4. 用 TAB 和 hard cases 主动展示外部泛化与失败边界。
5. 在 response 中逐条说明哪些已直接评估，哪些只是 partial，哪些明确留作 future work。

这样可以降低 reviewer 对 overclaiming 的反感，同时保留论文最有价值的部分：agent boundary graph 下的 pre-inference privacy propagation framing。
