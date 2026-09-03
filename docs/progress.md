# 论文进度

最后更新：2026-09-03 12:11 NZST

## 2026-09-03 revision cycle completion：vGPU 实验回收、论文回填与审稿闭环（当前新增）

- 已统一主文与附录 privacy-judge 表的企业基线和提出方法数值：统一为企业 staged redaction `8.1%`、提出方法 `9.3%`。同步修改了 `paper/main.tex`、`src/experiments/cppb_privacy_judge_baseline.py`、`cppb_privacy_judge_comparison.csv` 和 runtime manifest；表格回填后仍保持该数值。
- 已在修改代码前把当前 TOPS review 的剩余实验项写入 `docs/Design.md`，分为 RC-01 reconstructed CPPB live text pilot、RC-02 semantic mitigation probe、RC-03 Casper/PrivacyRestore、RC-04 live mapping compromise、RC-05 human utility validation、RC-06 named runtime/TAB pilot，并记录各自的证据边界和阻塞条件。
- 已使用 vGPU RTX 3090 完成 RC-01、RC-02、RC-06，并为本轮运行使用独立的 `revision20260903` 标签；结果没有覆盖 canonical 工件。Ollama 使用 `llama3.2:latest`（3.2B、Q4_K_M），最终配置为上下文 16,384、并行 16、Flash Attention，确认 29/29 层 offload 到 GPU。
- 本地 RTX 4050 CUDA smoke test 已通过，使用 CUDA 12.1 / PyTorch 2.5.1，512×512 矩阵校验和为 `2.3073265252774707e+18`，记录在 `data/revision_cycle_gpu_smoke_20260903.json`。该文件只证明执行环境可用，不产生论文结果。
- RC-01 完成 48 个 reconstructed text-only prompts × 4 条件，共 192/192 输出，均成功返回；RC-02 完成 12 条 probe × 4 变体，共 48/48，攻击准确率依次为 raw 50.0%、placeholder 25.0%、context abstraction 8.3%、access control 16.7%；RC-06 完成 TAB dev:32，Span-F1 0.12、PER 20.6%、text retention 0.24、平均延迟 5112.5 ms。上述结果均保留了独立 runtime manifest，并在论文中明确标注为有界 pilot。
- 结果归档已从远端完整拉回，远端与本地 `revision_cycle_results_20260903.tar.gz` 的 SHA-256 均为 `bafc036bf7a0f1eec51d07ddf4b7c37d5f458c18e5b678079cf410ae5070c9ec`；运行日志没有 OOM、traceback 或失败请求。结果回填到 `paper/main.tex` 附录及 TAB 结果段，但没有把 reconstructed pilot 改写成历史 CPPB 分数，也没有把小型 probe 改写成语义隐私保证。
- vGPU 端本轮创建的 Screen/Ollama 会话已停止；随后已发出关机命令，SSH 复测返回非零且无法建立会话，确认实例已退出以避免继续计费。
- `paper/build.bat` 已重新构建 `paper/main.pdf`，生成 34 页 PDF；无 fatal error、undefined citation/reference。MiKTeX 仍报告既有 BibTeX 元数据 warning 和少量版式 overfull/underfull warning，但本次修改未引入编译错误。
- 当前 vGPU 3090 已完成本轮实验并关机；本地仓库保留结果、日志、runtime manifest 和论文回填。未闭合项仍包括 Casper/PrivacyRestore 同协议比较、原始 CPPB/OCR 的 fresh live rerun、独立人工 utility、live mapping deployment、完整原始 OCR/runtime provenance，以及系统级 LDP 保证。

## 2026-09-03 修订意见、utility 回填与本机实验审计（当前权威状态）

本节覆盖 `docs/RevisionSuggestions.tex`、当前 `paper/` 源码、实验工件和本机运行状态；下方 2026-08-25 内容保留为历史快照。当前论文的主文与附录已经合并在 `paper/main.tex`：文件在附录起始处使用 `\\appendix`，仓库中不存在独立的 `paper/appendix.tex`。当前 `paper/main.pdf` 为单文件 35 页；旧记录中“main + appendix”或独立 `paper/appendix.tex` 的表述不再是当前文件拓扑。

本次同步后的详细实验完成百分比、预计 NZ 时间和备注见 `docs/ExperimentProgress.tex` 的 `Next-step plan`；该表已移除本轮已经完成的 vGPU pilot、blind scoring 和 utility manuscript integration。

### 与 `revision_suggestions.tex` 的逐项核对

| 项目 | 当前核对结果 | 状态 |
|---|---|---|
| W1 / A1--A2：实测传播、实测 adversary 成为主线 | `paper/main.tex` 含 `tab:measprop`、`tab:advmeas`，并把 CPPB controlled operating surface 留作附录参考；对应 measured propagation、PrivacyLens 和 adaptive adversary 结果文件均存在。 | 已完成 |
| W2 / A4：secure mapping compromise | `tab:mapcompromise` 与 `secure_mapping_compromise_results.csv` 已完成 capability-graded 机制级实测；论文明确 live-stack compromise 仍未覆盖。 | 机制级完成；端到端未完成 |
| W3 / A3：推荐 learned detector | 正文已明确推荐“framing + learned detector”，并在 adversary 段说明 heuristic detector 的弱点。 | 论文修改已完成 |
| W4：cross-domain evidence | `tab:crossdom` 与 `cross_domain_detector_results.csv` 已存在，Generic→Clinical 已实测；licensed i2b2 和更多域仍未完成。 | 有界完成 |
| W5：八类 adversarial families | `tab:advmeas` 与 `measured_adaptive_adversary_results.csv` 已记录八类攻击；semantic-paraphrase residual 已作为开放问题。 | 已完成；残余风险已披露 |
| W6 / A5：独立 blind utility review | Luna 与 Claude 的 148 条 pending 评分、agreement、response-family summary 和 per-template breakdown 已回填 `paper/main.tex` 附录，并明确这是 external model-based pilot，不是 human validation；论文已区分 safe refusal、generic template/code、useful completion 与 other partial responses。 | 论文整合已完成；human validation 仍未完成 |

### AE 原始六条意见与当前论文闭合状态

| AE 意见 | 当前 `paper/main.tex` 是否已修改 | `revision_suggestions.tex` 是否已记录 | 仍未闭合的证据 |
|---|---|---|---|
| 1. Casper/PrivacyRestore 近邻工作与比较 | 已补引用、概念比较表和 novelty boundary；明确没有同协议复现 | 已记录为 E1，明确 direct head-to-head open | 同条件实证比较未完成 |
| 2. CPPB 规模/过拟合 | 已补 benchmark card、16/8/8 template-disjoint split、审计和历史 score-log 限制；另完成 48 个 reconstructed prompts × 4 条件的独立标记 pilot | 已记录为 E2，明确 fresh live rerun open | 缺原始 prompt/OCR 和 frozen downstream stack，reconstructed pilot 不能替代 fresh CPPB rerun |
| 3. deterministic agent、83% 语义残留、SPE/推断攻击 | 已写入 deterministic reference agent、83% semantic residue、原始 placeholder 50% context-inference，并新增四变体 exploratory probe；继续限制 SPE 解释范围 | 已记录为 E3 | 语义泄露和推断攻击仍未被解决，probe 只提供固定小面板的有界信号 |
| 4. enterprise redaction 与 utility 验证 | 已写入 8.1% vs 9.3%、AC/TSR +0.02/+0.02；附录已回填 Luna/Claude pilot 并区分 refusal/completion | 已记录为 E4，A5 已标记完成 | 独立 human/task utility validation 未完成，rubric 仍非独立人工验证 |
| 5. learned detector、model/OCR/runtime 披露 | 已报告 Span F1 0.53、precision 0.36，并补轻量 detector 配置和 metadata audit；本轮新增 pilot 已填 named model digest、decoding、GPU、Python 和 Ollama runtime 字段 | 已记录为 E5 | 原始 CPPB cross-model/OCR/runtime 的完整 named rerun 记录仍不完整 |
| 6. span-level LDP 不能保证整个系统 | 已删除系统级 LDP 保证叙事，明确 no end-to-end formal guarantee 及覆盖边界 | 已记录为 E6 | 若要求真正系统级保证，仍未完成；当前是正确的 scope correction |

### vGPU 实验覆盖审计

| vGPU 实验记录 | 已完成内容 | 覆盖的修改意见 | 未覆盖内容 |
|---|---|---|---|
| `data/cppb_reconstructed_utility_run_log_revision20260903.csv` | RTX 3090 上 `llama3.2:latest`，48 个 reconstructed text-only prompts × 4 条件 = 192 outputs，含 digest、runtime manifest 和 blind-review surface | 为 W6/A5 提供可分析的 utility pilot；验证 named local runtime surface | 不是 256-prompt fresh CPPB live rerun，不含原始 OCR，也不能证明泛化或 human utility |
| `src/experiments/semantic_mitigation_probe_results_revision20260903.csv` | 12 条固定 probe × 4 变体 = 48/48，raw/placeholder/context abstraction/access control 准确率为 50.0/25.0/8.3/16.7% | 为 E3 提供有界的 exploratory mitigation signal | 不是完整语义隐私研究，没有 paired utility、adaptive attacker 或 broad-domain closure |
| `src/experiments/tab_ollama_zero_shot_run_log_revision20260903.csv` | TAB `dev:32` zero-shot pilot，2,037 mentions，含 model digest、Linux/Python/Ollama runtime、decoding 记录 | 提供一个公开 transfer 的 live model pilot 和运行记录 | 不是 CPPB downstream rerun，不是 Casper/PrivacyRestore 对比，也不是 named cross-model closure |
| 其余 vGPU/运行记录 | 未发现 Casper/PrivacyRestore 同协议运行、live mapping deployment 或原始 CPPB V4/V8 exact regeneration 记录 | 目前仍只能支撑 bounded pilot claims | 不能把现有 vGPU 记录升级成 AE 所要求的完整证据 |

判断：现有 vGPU 实验覆盖了 reconstructed utility pilot、四变体 semantic probe 和一个 TAB live pilot，但没有覆盖全部 AE 所需实验。原始 prompt/OCR、冻结 agent stack、Casper/PrivacyRestore 实现、部署 mapping service 或人工 raters 未到位的部分，不能用现有 pilot 变成可复核的完整证据。

### 本机记录和排队状态

- `data/cppb_reconstructed_blind_ratings_vgpu3090_completed_openai_luna.csv` 和 `...completed_claude_sonnet5.csv` 各含 236 行、192 个唯一 `review_item_id`；两套评分均覆盖 148 条 pending ID。Luna/Claude 的三项 exact agreement 分别为 task success 90.5%、faithfulness 89.9%、required fields 87.8%。新增 `cppb_blind_utility_summary.csv`、`cppb_blind_utility_by_template.csv` 和 `cppb_blind_utility_agreement.csv`，并由 `analyze_blind_utility_review.py` 可重生成。
- 新增 `src/experiments/analyze_human_utility_review.py` 作为 human-only 审计入口；对现有 88 条原始评分生成 `data/cppb_human_utility_{summary,agreement,coverage}.csv` 和 `cppb_human_utility_audit.txt`。当前审计确认覆盖 44/192 输出、11 个完整 prompt block、16 个多评分者输出，并发现 47 条拒答式行中 43 条的 task success 为 1；该结果只作为校准标记，不是论文效用结论。
- 已检查 `src/experiments/*execution_manifest.csv`：TAB、CORD、FUNSD、SROIE 和 PhysioNet public transfer 有 executed 记录；TAB zero-shot semantic baseline 仍为 `pending_external_runtime`；licensed i2b2 仍为 `waiting_for_licensed_data`，clinical pipeline 与 zero-shot baseline 仍为 `pending_external_runtime`。
- 已检查 named cross-model、CPPB multimodal exact-regeneration 和 external-baseline manifest：它们是 template/protocol，不是已排队的 filled runtime。没有发现待运行的 Python、Ollama、pdflatex/bibtex 实验进程，也没有匹配的 Windows Scheduled Task。
- `.claude/scheduled_tasks.lock` 当前由 PID 16744 的 `claude` 进程持有；该进程不是上述实验执行器，本次审计未停止或修改它。

### 修改意见与实验队列覆盖关系

| 未完成意见 | 必需实验/动作 | 本机覆盖情况 | 是否有可运行排队项 |
|---|---|---|---|
| 独立 human/task utility | 盲 UI 收集人工评分并计算 agreement | 已有 88 条标记为人工评分的行，覆盖 44/192 输出；provenance/independence 未完整记录，且 human-audit script 发现 47 条拒答式输出中 43 条被打成 task_success=1，与 rubric 冲突；148 个输出仍待人工评分 | 是（UI 可运行；需要校准和人工） |
| E1 residual | Casper/PrivacyRestore 同协议实证比较 | 当前只有 primary citations 和概念比较表，尚无复现实现或同协议运行记录 | 否，资源/实现阻塞 |
| W1 residual | frozen downstream stack 上的 CPPB fresh template-disjoint live rerun | 只有 reconstructed pilot；原始 prompt/OCR 与 frozen stack 缺失 | 否，当前阻塞 |
| W2 residual | live deployment mapping service、credential/audit/session-isolation attack | reference capability curve 已完成，live stack 未建立 | 否 |
| E5 residual | named vendor/model/version/digest、OCR、runtime disclosure/rerun | 只有 alias/family artifact 和 manifest template；完整记录未填 | 否 |
| E3 residual | semantic leakage/context-inference mitigation | 83% semantic residue 和 50% inference 已测量，防护机制尚未实验 | 否 |
| W4 residual | licensed i2b2 与更多 domain 的 filled transfer | PhysioNet generic↔clinical 已完成；i2b2 等待许可/数据 | 仅 protocol，不可运行 |
| multimodal provenance residual | 原始 CPPB V4/V8 render/OCR/runtime exact regeneration | public OCR slices 有记录，原始 CPPB exact manifest 未填 | 否，源数据阻塞 |

结论：现有本机实验记录已经覆盖 W1、W2、W3、W4、W5 所需的有界证据，W6/A5 的 external model-based utility pilot 也已回填并编译进论文；仓库另有 88 条部分人工评分记录，但因覆盖、评分者 provenance、独立性和 rubric calibration 存在问题，独立 human/task utility validation 仍未完成。应先保留原始文件、校准 rubric 并重评 88 条 legacy rows，再在现有 UI 中完成 148 个匿名 pending 输出，预先规定 overlap/agreement 分析。vGPU 已覆盖 reconstructed CPPB utility pilot 和 TAB dev:32 live pilot，但没有覆盖 fresh CPPB、近邻系统同协议比较、semantic-inference mitigation 或 live deployment compromise。其余开放实验均受原始资产、许可、命名运行时或 live deployment stack 限制，不能用现有 pilot 或历史 score log 代替。

## 2026-08-25 新审稿意见（AESuggestion）对应 revision cycle（历史快照）

本节是当前状态的优先记录；下方 2026-06-17 的内容保留为历史工作日志。新的 AE 意见给出 reject，主要问题是近邻工作缺失、CPPB 模板规模与 full-dataset 评估造成的过拟合疑虑、PrivacyLens 语义泄露、enterprise redaction 直接暴露更低、detector/runtime/OCR 可复现性不足，以及 span-level LDP 被误读为系统保证。

### 本轮已完成

- 已先在 `docs/Design.md` 写入本轮实验计划，逐项区分可执行证据、历史/generated score log 与必须降级的 claim。
- 已新增 `src/experiments/review_revision_audit.py`，并生成 `review_revision_audit.csv` 与 `review_revision_audit_runtime_manifest.csv`。审计确认 CPPB train/dev/test 为 16/8/8 templates、128/64/64 prompts，跨 split template overlap 为 0、重复 prompt ID 为 0；同时明确 bundled CPPB score log 不是 fresh end-to-end rerun，near-zero dev/test gap 不再被当作泛化证据。
- 已重跑 `measured_agent_propagation.py`：AI4Privacy real-text reference agent 上 learned detector 的 PER 为 7.4%，retrieval/memory/tool SPE 为 1.9/3.4/2.5%。
- 已重跑 `measured_privacylens_propagation.py`：493 条真实 PrivacyLens agent trajectory 上 exact identifier PER 为 1.8%，但 semantic residue 为 83.0%；论文现在把 surface-form survival 与 semantic disclosure 分开解释。
- 已由审计从 `prompt_method_comparison.csv` 重新计算 enterprise gap：proposed 相对 enterprise staged redaction 的 PER 为 +1.20 percentage points，AC/TSR 仅 +0.02/+0.02；论文不再声称直接暴露或 utility superiority。
- 已在 `paper/main.tex` / `paper/ref.bib` 补充 PrivacyRestore、Casper 的 primary citations 和 comparison matrix，明确 placeholder/local restoration 不是本文新颖性来源；title 也收紧为不暗示完整 VLM-loop 验证。
- 已删除正文中的 optional span-level LDP proposition，改为明确的 no end-to-end formal privacy guarantee scope statement；PER/SPE/semantic residue/ASR 现在均作为 empirical measurements，不作为 recovery 或 inference bounds。
- 已降级 alias-only cross-model portability 表，披露 metadata audit 发现的 exact model/version/digest 缺口；轻量 learned detector 的 17 个特征、训练文档数、epochs、learning rate、L2、class weight、threshold 等已写入正文。

### 当前验证状态

- 已通过新增审计脚本、两个 measured propagation 脚本和 Python syntax check。
- 本机 NVIDIA GPU 可用（RTX 4050 Laptop，约 6 GB VRAM）；本轮只用 GPU 做 smoke test，不用它生成无法复核的论文数值。
- 已核对 `docs/Design.md` 的资源需求：三项正式证据实验均可在本地 CPU/现有数据上完成；3090 仅对 live LLM、较大模型并行或吞吐敏感的 OCR 重跑有帮助，且不能解决 prompt assets、agent stack、模型标识或授权数据缺失。
- 当前本机 `127.0.0.1:11434` Ollama HTTP endpoint 可响应并返回模型元数据，但命令行客户端不存在；因此“fresh CPPB live rerun”仍因轻量 prompt stubs 和缺少冻结的 downstream agent-stack/runtime 而未解锁。
- vGPU 3090 已完成 live runtime 部署：远端识别 RTX 3090（48 GB，约 48.5 GB 空闲），源码、Python 3.10 venv、requirements、Ollama 0.32.15 与 `llama3.2:latest` 均已就绪；Ollama 日志确认使用 CUDA 8.6，模型推理时显存约 31.2 GB。已完成 CUDA live smoke，并执行 TAB `dev:32` zero-shot pilot：32 个文档、2,037 mentions，Span F1 0.28、PER 80.4%、text retention 0.91，平均延迟 9.78 s；远端产物带 `vgpu3090` 后缀并记录模型 digest。此前的 Python/确定性审计实验也已完成。
- GPU smoke test 已通过；`paper/build.bat` 已成功生成 33 页 `paper/main.pdf`，最终日志无 undefined citation/reference 或 fatal error。final diff review 已完成；论文子仓库 commit `1f1f996` 与父仓库 commit `51f60bf` 已分别推送到对应 remotes，且父仓库 gitlink 已指向论文 commit。

### 仍未完成或明确阻塞

- vGPU live runtime：已完成，不再阻塞；AutoDL `/etc/network_turbo` 用于下载阶段，模型保存在 `/autodl-fs/data/ollama`。`--registry-mirror` 不是当前 Ollama 0.32.15 CLI 支持的参数，实际使用其默认 `registry.ollama.ai`。
- TAB `dev:32` live pilot：已执行但属于 pilot，不替代 CPPB fresh template-disjoint rerun；当前结果显示 zero-shot 模型的 PER 较高，不能据此宣称 utility 或 privacy superiority。
- CPPB 的 fresh live end-to-end template-disjoint rerun：当前 prompt manifest 仍是 lightweight stubs；虽然本机 Ollama HTTP endpoint 可响应，但尚未形成可复核的 frozen downstream agent-stack/model runtime，不能把旧 score log 改写成新实验。
- AC/TSR 的 independent human/task validation：当前只能保留 custom rubric 的 matched result，不能宣称 meaningful utility improvement。
- named cross-model rerun、完整 model digest、live-stack mapping compromise 与更多 domain/clinical rerun：已有 manifest/template，但缺少可公开的 filled runtime records 或授权数据。

## 建议使用相关数据扩充实验

一、公开Benchmark数据集（解决 M1 问题）
🔵 通用PII / 文本匿名化
数据集.规模.下载地址.适用场景

TAB (Text Anonymization Benchmark). 1,268 条ECHR法庭案例，含PII类别、身份标识符类型、置信属性及共指关系等多层标注. arXivgithub.com/NorskRegnesentral/text-anonymisation-benchmark . 主评估集，直接对标CPPB.

AI4Privacy PII-Masking-300K. 约22万+文本样本，54种PII类别，覆盖商业/教育/法律领域，含5种交互风格，每条有对应脱敏版本 Hugging Facehuggingface.co/datasets/ai4privacy/pii-masking-300k.  训练contextual judge的大规模数据.

Kaggle PII Detection (Learning Agency Lab). 约2.2万学生作文，含7类PII标注. kaggle.com/competitions/pii-detection-removal-from-educational-data.  扩大prompt domain多样性

🔴 Agent隐私 / 安全（直接支持传播实验）
数据集/框架 规模 地址 用途

AgentDojo.  97个真实任务、629个安全测试用例，覆盖邮件、日历、银行、出行等环境.   arXivgithub.com/ethz-spylab/agentdojo.  端到端传播实验 + 对抗注入测试，直接替代CPPB的agent任务子集.

PrivacyLens. 493个隐私敏感seed（来自美国法规+众包），含vignette和trajectory三层数据，提供leakage rate和helpfulness rating评估. GitHubgithub.com/SALT-NLP/PrivacyLens推理攻击实验（解决M3），contextual privacy评估

🟡 临床/医疗（有许可证要求但有公开替代）
数据集  获取方式  地址

PhysioNet MIMIC-III (去标识)  免费注册+培训即可  physionet.org/content/mimiciii 

i2b2-Synthea (合成临床) 完全开放  github.com/i2b2/i2b2-synthea

二、强NLP Baseline工具（解决基线弱的问题）
检测层 Baselines
工具 特点 安装
Microsoft Presidio, 支持NLP、正则、规则逻辑、校验和等多种识别方式，支持文本/图像/结构化数据，可连接外部PII检测模型 GitHub, pip install presidio-analyzer presidio-anonymizer

GLiNER PII,零样本识别任意实体类型，60+预定义PII类别，支持本地部署无需API，F1可达80.99%, pip install gliner → knowledgator/gliner-pii-base-v1.0

spaCy en_core_web_trf, Transformer版NER，比sm更强, python -m spacy download en_core_web_trf

Inference Attack Baseline（解决M3）
python# 直接用于属性推断实验的prompt模板示例（可作为AIA评估器）
from transformers import pipeline

aia_model = pipeline("text-generation", model="meta-llama/Llama-3-8B-Instruct")
prompt = """Given the following sanitized text, infer the person's 
[medical condition / financial tier / location]:
Text: {sanitized_text}
Your inference:"""


## 已完成的仓库内工作

- 已重新按当前 revision cycle 收口进度文件；修改说明：本文件现统一整理为“已完成的仓库内工作”与“仓库外部边界/非阻塞限制”两大块，删除了旧版按轮次堆叠、前后重复和状态互相冲突的写法。
- 已统一主文与附录的问题定义与符号体系；修改说明：`paper/main.tex` 与 `paper/appendix.tex` 已把问题表述统一到 agent-boundary graph、policy profile、direct exposure / propagation risk / utility 这一条主线，不再出现引言、方法、附录 notation 各写各的情况。
- 已完成主文证据结构收口；修改说明：主文现在集中保留 `tab:cppb_card`、`tab:per`、`tab:utility`、`tab:pi_sensitivity`、`tab:propagation`、`tab:latency` 等 backbone evidence，`tab:restore`、`tab:ablation`、`tab:multimodal`、`tab:crossmodel`、`tab:catwise`、`tab:hardcase` 等 supporting slices 已下沉到 appendix。
- 已完成 CPPB benchmark accounting 工件建设；修改说明：仓库现已包含 `src/experiments/build_cppb_manifest.py`、`cppb_template_inventory.csv`、`cppb_prompt_manifest.csv`、`cppb_distribution_breakdown.csv`、`cppb_accounting_summary.csv`，正文中的 benchmark card 已可由仓库工件直接支撑。
- 已完成主文 benchmark card 回填；修改说明：`src/experiments/fill_paper_tables.py` 已支持 `tab:cppb_card <- cppb_accounting_summary.csv`，主文中 CPPB 的 prompt / template / subset / family / category / modality 统计已不再依赖手写描述。
- 已把 restoration boundary 与 sanitization mode 两组 supporting slices 升级为 repo-backed artifact；修改说明：仓库已新增 `src/experiments/restoration_boundary_analysis.csv` 与 `src/experiments/sanitization_mode_ablation.csv`，`paper/appendix.tex` 中的 `tab:restore` 与 `tab:ablation` 现在由 `src/experiments/fill_paper_tables.py` 自动回填。
- 已完成 supporting figure 升级；修改说明：仓库已新增 `src/figures/restoration_ablation_tradeoffs.py` 与 `paper/figs/restoration_ablation_tradeoffs.png`，附录已纳入 restoration timing 和 sanitization mode 的 trade-off figure，而不再只保留静态表格。
- 已完成 Windows 下独立论文构建脚本修复；修改说明：`paper/build.bat` 现使用 `pdflatex -> bibtex(按需) -> pdflatex -> pdflatex` 独立构建 `main` 与 `appendix`，中间文件输出到 `paper/build/`，成功后自动复制 `main.pdf` 与 `appendix.pdf` 回 `paper/` 根目录。
- 已完成摘要与主文投稿口径收紧；修改说明：摘要已重组为 Problem / Approach / Key Result / Scope 四步结构，正文中 `this revision`、`current revision`、`next revision` 等过程化措辞已清理，limitations 与 conclusion 也已改为更适合投稿稿的 evidence-bounded 表达。
- 已完成可复现性说明更新；修改说明：`paper/appendix.tex` 已同步写明仓库当前包含 deterministic CPPB manifest/accounting 工件，并更新 artifact-to-script reproducibility map，使 benchmark card、restore/ablation supporting artifacts 与 supporting figure 的脚本来源可检查。
- 已完成外部强基线补充；修改说明：仓库已新增 `src/experiments/external_baseline_suite.py`、`external_baseline_comparison.csv` 与 `presidio_baseline_notes.txt`，附录新增 `tab:baseline` 展示 Presidio regex-only、Presidio+NER 与 BodhiPromptShield 的对比结果。
- 已完成 adversarial robustness suite；修改说明：仓库已新增 `src/experiments/adversarial_robustness_suite.py`、`adversarial_robustness_results.csv`、`adversarial_attack_inventory.csv`，附录新增 `tab:adversarial`，threat model 与实际实验切片现在已有 repository-backed supporting evidence 对应。
- 已完成 multi-seed robustness artifact；修改说明：仓库已新增 `src/experiments/multiseed_evaluation.py`，并产出 `multiseed_method_prompt_logs.csv`、`multiseed_method_seed_metrics.csv`、`multiseed_method_summary.csv`、`multiseed_policy_prompt_logs.csv`、`multiseed_policy_seed_metrics.csv`、`multiseed_policy_summary.csv`，相关结果已接入论文表格与图表。
- 已完成 leave-template-out generalization artifact；修改说明：仓库已新增 `src/experiments/leavetemplateout_evaluation.py`，并产出 `leavetemplateout_results.csv` 与 `leavetemplateout_summary.csv`，附录中对应 generalization slice 已从“Not yet integrated”更新为“Record-backed”。
- 已完成表格回填脚本扩展与修复；修改说明：`src/experiments/fill_paper_tables.py` 现已支持 `tab:multiseed` 与 `tab:lto`，并已修复新表头字符串换行导致的 LaTeX `\midrule` 错位问题。
- 已完成 operating-points figure 升级；修改说明：`src/figures/prompt_privacy_operating_points.py` 现可读取 multi-seed summary，在 `paper/figs/prompt_privacy_operating_points.png` 中显示 95% CI error bars。
- 已完成主文与附录对 multi-seed / leave-template-out 的口径更新；修改说明：`paper/main.tex` 已新增 repeated-run 与 leave-template-out 的结果解读，`paper/appendix.tex` 已新增并回填 `tab:multiseed` 与 `tab:lto`，相关 roadmap 状态已改为 `Record-backed`。
- 已完成主文与附录引用及编译问题修复；修改说明：已移除主文对附录专属 label 的直接引用，避免 split build 下的 undefined reference；最新 `paper/build.bat` 已验证 `paper/main.pdf` 与 `paper/appendix.pdf` 可以成功生成。
- 已完成文档同步；修改说明：`src/README.md` 与 `src/experiments/README.md` 已补入 CPPB manifest/accounting、新实验脚本、表格映射与生成命令，使仓库文档与当前论文状态一致。
- 已完成 Presidio-class external baseline table 自动回填；修改说明：`src/experiments/fill_paper_tables.py` 已新增 `tab:baseline <- external_baseline_comparison.csv`，`paper/appendix.tex` 中的外部基线表不再是纯手写 manuscript slice，而是由 bundled comparison CSV 自动重建的 record-backed supporting artifact。
- 已补充 artifact metadata / data-card 说明；修改说明：仓库已新增 `src/experiments/artifact_metadata_notes.md`，补入 CPPB split semantics、annotation/label 语义、multimodal slice scope 与 latency interpretation notes，主文与附录中的 reproducibility scope 已同步更新。
- 已补充论文内的 CPPB release/data-card prose；修改说明：`paper/appendix.tex` 已新增对 release scope、annotation semantics 与 remaining metadata manifests 的正式说明，`paper/main.tex` 的 benchmark/data-card 与 reproducibility 段落也已同步改写，不再只依赖仓库侧说明文件承载这些语义。
- 已完成一轮局部版式收紧；修改说明：`paper/appendix.tex` 已将 path-heavy command block 改为更适合论文的 prose summary，去除了其中一组明显的非必要排版 warning 来源，同时不改变证据结构与可复现性口径。
- 已完成 protocol-compatible benchmark 路线收口；修改说明：`paper/appendix.tex` 的 transfer / baseline 规划矩阵现已从泛化占位符改为具名优先级路线，明确 TAB、2014 i2b2/UTHealth、SROIE/CORD、FUNSD 与 AgentDojo 分别对应 text-only transfer、clinical PHI、OCR receipt/form 与 boundary-robustness 外部验证，不再只写成笼统的 “public benchmark”。
- 已进一步补强论文内 data-card 对齐说明并做第二轮局部排版收紧；修改说明：`paper/main.tex` 与 `paper/appendix.tex` 现已把 fuller data-card 所需字段收口到 source-level provenance、annotation examples、sanitization-policy labels 与 external wrapper specification，并同步压短若干 transfer/baseline/robustness figure/table caption，减少一部分由长 caption 造成的版式压力。
- 已修复论文构建链中的 bibliography refresh 缺口；修改说明：`paper/build.bat` 现会在 BibTeX 生成 `paper/build/*.bbl` 后同步刷新 `paper/*.bbl`，避免 `-output-directory` 构建时继续读取根目录下的陈旧 bibliography 文件而导致新 citation 无法稳定解析。
- 已完成 `tab:catwise` 升级为 repo-backed artifact；修改说明：仓库已新增 `src/experiments/categorywise_analysis.py` 与 `categorywise_analysis.csv`，`src/experiments/fill_paper_tables.py` 现已支持 `tab:catwise <- categorywise_analysis.csv`，附录 category-wise 表不再是纯手写 manuscript slice。
- 已完成 TAB / i2b2 external transfer scaffold；修改说明：仓库已新增 `src/experiments/tab_external_transfer.py`、`i2b2_external_transfer.py`，并生成 `tab_matched_baseline_protocol.json` 与 `i2b2_matched_baseline_protocol.json`，把 prompt-wrapper 与 matched baseline protocol 正式落成可执行脚手架，即便当前快照仍未附带外部 benchmark 原始数据与最终 transfer 结果。
- 已完成真实 TAB 数据接入与首个 wrapper manifest；修改说明：仓库现已拉取公开 TAB ECHR train/dev/test JSON 到 `src/experiments/external_data/tab/`，`src/experiments/tab_external_transfer.py` 已按 annotator-layer `entity_mentions` 结构生成真实 `tab_prompt_wrapped_manifest.csv`，外部 text anonymization transfer 不再停留在 protocol-only。
- 已完成 `tab:multimodal` 的 CSV + script + table-fill 升级；修改说明：仓库已新增 `src/experiments/multimodal_analysis.py` 与 `multimodal_analysis.csv`，并由 `src/experiments/fill_paper_tables.py` 自动回填附录中的 multimodal supporting table；该切片现为 record-backed supporting artifact，但仍不等同于附带完整 OCR/version manifest 的 end-to-end public rerun。
- 已完成 i2b2 normalized export 准备链路；修改说明：仓库已新增 `src/experiments/prepare_i2b2_normalized_export.py` 与 `i2b2_normalized_export_template.jsonl`，可把用户自有的 i2b2 XML/TXT 或 JSON/JSONL 导出规范化为 `i2b2_external_transfer.py` 所需 schema，为 clinical transfer 的下一步实际运行做好输入准备。
- 已补齐一组独立 metadata manifests；修改说明：仓库已新增 `cppb_release_card.md`、`ocr_slice_manifest.md`、`crossmodel_portability_manifest.md` 与 `latency_environment_manifest.md`，把 multimodal / cross-model / latency 三类证据边界从“只在论文里解释”推进为“仓库内可直接检查的 release-scope manifests”。
- 已继续补强 CPPB data-card；修改说明：`cppb_release_card.md` 现集中写明 release scope、source provenance、annotation examples、wrapper semantics 与 known omissions，`paper/main.tex` 与 `paper/appendix.tex` 已同步改写为 benchmark-card-style release 口径，不再只把 data-card 字段零散分布在 accounting prose 里。
- 已完成 `tab:hardcase` 的独立 slice record 与 table-fill 升级；修改说明：仓库已新增 `src/experiments/hardcase_analysis.py` 与 `hardcase_analysis.csv`，`src/experiments/fill_paper_tables.py` 现已支持 `tab:hardcase <- hardcase_analysis.csv`，附录 hard-case 表不再是纯手写 manuscript slice。
- 已完成 cross-model portability artifact 的 alias-level 升级；修改说明：仓库已新增 `src/experiments/crossmodel_analysis.py`、`crossmodel_portability_results.csv` 与 `crossmodel_runtime_log.csv`，`src/experiments/fill_paper_tables.py` 现已支持 `tab:crossmodel <- crossmodel_portability_results.csv`，附录 cross-model 表已从纯手写表提升为 repo-backed supporting artifact，但仍未公开 vendor/model/version 真名。
- 已完成首个可执行 TAB matched-baseline transfer 结果；修改说明：仓库已新增 `src/experiments/tab_matched_baseline_suite.py`，并生成 `tab_transfer_results.csv` 与 `tab_transfer_document_metrics.csv`，附录新增 `tab:tabtransfer`，把 TAB 从 wrapper-manifest/protocol-only 推进到真实 public-transfer result slice。
- 已完成表格回填脚本对 hardcase / crossmodel / TAB transfer 的扩展；修改说明：`src/experiments/fill_paper_tables.py` 现已新增 `tab:crossmodel`、`tab:hardcase` 与 `tab:tabtransfer` 的自动回填支持，`paper/appendix.tex` 中三处表格可由仓库工件自动重建。
- 已扩展 TAB comparator family 并补 execution manifest；修改说明：`src/experiments/tab_matched_baseline_suite.py` 现已把 public TAB slice 从 raw/regex/NER/proposed 扩展到 raw/regex/NER/Presidio-class(regex)/Presidio-class(+NER)/proposed，并新增 `tab_transfer_execution_manifest.csv`，明确哪些 comparator 已执行、哪些仍仅停留在 protocol level。
- 已补齐 i2b2 clinical transfer runner 与 execution manifest；修改说明：仓库已新增 `src/experiments/i2b2_matched_baseline_suite.py` 与 `i2b2_transfer_execution_manifest.csv`，在具备 licensed normalized export 时可直接产出统一格式结果，而当前公开快照则只诚实保留 protocol + runner + execution-status artifact。
- 已补 richer named cross-model rerun manifest template；修改说明：仓库已新增 `crossmodel_named_rerun_manifest_template.csv`，把 alias-level portability slice 升级为 fully named rerun 时所需的 vendor/model/version/runtime 字段收口为明确模板，而不再只停留在 prose-level 占位说明。
- 已补 TAB / i2b2 原始运行记录；修改说明：仓库现已新增 `tab_transfer_run_log.csv` 与 `i2b2_transfer_run_log.csv`，把 wrapper 输入范围、split 计数、输出文件、rerun command template 与 execution status 统一落盘，不再只保留 summary/execution manifest。
- 已补更强 released hybrid comparator family；修改说明：TAB runner 现已新增 `Hybrid rule+context de-identification`，i2b2 runner 现已新增 `Clinical hybrid heuristic de-identification`，二者都在同一 wrapper/protocol 下落到统一结果/运行记录表面。
- 已继续补 fuller data-card / provenance 文档；修改说明：仓库已新增 `external_wrapper_release_card.md` 与 `multimodal_provenance_card.md`，把 TAB/i2b2 wrapper invariants、comparator roster、licensing boundary，以及 multimodal slice 的 rendering/OCR provenance 边界集中写成可检查说明，并已同步纳入论文附录口径。
- 已完成 external-validation 口径再同步；修改说明：`paper/main.tex` 与 `paper/appendix.tex` 现已显式补入 licensed-data-ready i2b2 schema surface、external runtime conditions 与一张诚实的 external-closure 状态表，`docs/revision_suggestions.tex` 也已改写为只保留与当前仓库证据一致的剩余任务，不再把 protocol-ready / waiting-state slice 误写成 executed。
- 已补 external resource acquisition helper 与资源表；修改说明：仓库已新增 `acquire_external_resources.py`、`external_resource_acquisition_card.md` 与 machine-readable acquisition manifest 输出位，附录新增官方 external datasets / baselines / OCR engines / model docs 资源表，主文的 reproducibility scope 也已并入 acquisition-manifest 口径，同时修正了正文中 TAB public-transfer 的过时数值。
- 已补 OCR-heavy public transfer scaffold 与公开 helper repo 缓存；修改说明：`acquire_external_resources.py` 现可在 request-gated benchmark 条目下继续缓存公开 helper repo，仓库已把 DocILE helper repo 与 CORD 等公开 GitHub 资源落到本地缓存，并新增 `ocr_external_transfer.py`、`ocr_transfer_protocol.json` 与 `ocr_transfer_resource_manifest.csv`，把 CORD/FUNSD/SROIE/DocILE 的 OCR-heavy transfer 路径收口为 acquisition-aware protocol scaffold，而不把它误写成 executed evidence。
- 已补 protocol-only semantic/named baseline templates 与 source-level CPPB provenance manifest；修改说明：仓库已新增 `tab_zero_shot_prompt_template.txt`、`i2b2_zero_shot_prompt_template.txt`、`external_baseline_runtime_manifest_template.csv`、`ocr_engine_runtime_manifest_template.csv`、`latency_host_manifest_template.csv`，并新增 `build_cppb_source_manifest.py` 与 `cppb_source_licensing_manifest.csv`，把此前仅停留在 prose 里的 zero-shot baseline disclosure、OCR/runtime disclosure、latency host disclosure，以及 CPPB source-level provenance 进一步落成可检查模板或结构化工件。
- 已按最新 revision plan 收口 synthetic/open-weight/OCR 三条公开路线；修改说明：`acquire_external_resources.py` 与 acquisition manifest 现已新增 i2b2-Synthea synthetic clinical route、CORD 的 Hugging Face mirror 与 CC-BY-4.0 元数据、以及 Ollama public local runtime surface，`external_baseline_runtime_manifest_template.csv` 现用 Ollama + Llama3-8B-Instruct 具体化 zero-shot logging 模板，`ocr_transfer_protocol.json` 现将 CORD 标记为 primary public OCR rerun target，并同步回写论文主文与附录口径。
- 已把剩余 revision items 的“已解决/未解决原因”正式写入论文；修改说明：`paper/main.tex` 现新增一段面向主文的 closure summary，说明哪些 external baseline、transfer、metadata、data-card 与版式问题已经被收口到 repo-backed 或 protocol-backed 状态，`paper/appendix.tex` 现新增一张逐项状态表，明确哪些仅部分解决以及为什么当前公开快照还不能诚实写成 executed evidence。
- 已把本地 Ollama zero-shot baseline 推进到真实可执行 pilot；修改说明：仓库已新增 `tab_ollama_zero_shot_baseline.py`，并生成 `tab_ollama_zero_shot_results.csv`、`tab_ollama_zero_shot_document_metrics.csv`、`tab_ollama_zero_shot_runtime_manifest.csv` 与 `tab_ollama_zero_shot_run_log.csv`，把此前仅有 template/runtime surface 的 TAB semantic baseline 推进到一个 runtime-backed、公开可检查的 `dev:32` pilot，同时论文主文与附录已同步从 protocol-only 更新为 executed-pilot-but-not-full-rerun 的口径。
- 已把同一条本地 zero-shot 路径对齐到 synthetic i2b2-Synthea export；修改说明：仓库已新增 `build_i2b2_synthea_synthetic_export.py`、`i2b2_synthea_synthetic_export.jsonl`、`i2b2_synthea_prompt_wrapped_manifest.csv`、`i2b2_ollama_zero_shot_baseline.py`，并生成 `i2b2_ollama_zero_shot_results.csv`、`i2b2_ollama_zero_shot_document_metrics.csv`、`i2b2_ollama_zero_shot_runtime_manifest.csv` 与 `i2b2_ollama_zero_shot_run_log.csv`，把此前仅有 schema/acquisition route 的 public synthetic clinical path 推进到一个 24-note、runtime-backed、schema-compatible executed pilot，同时主文与附录已同步写明它是 synthetic rehearsal 而不是 licensed i2b2 benchmark。
- 已把 synthetic i2b2 public slice 继续扩到更大的公开范围；修改说明：`build_i2b2_synthea_synthetic_export.py` 已重新生成 `synthea-dev:32` export，`i2b2_synthea_prompt_wrapped_manifest.csv` 已同步扩到 32 notes，`i2b2_ollama_zero_shot_results.csv` 当前也已更新为 32-note canonical pilot，而论文主文与附录已同步把 synthetic clinical zero-shot evidence 从 24-note 口径改到 32-note 口径。
- 已补 TAB / synthetic i2b2 的本地 zero-shot stability 证据；修改说明：仓库已新增 `ollama_zero_shot_stability.py`，并生成 `tab_ollama_zero_shot_stability_runs.csv`、`tab_ollama_zero_shot_stability_summary.csv`、`i2b2_ollama_zero_shot_stability_runs.csv` 与 `i2b2_ollama_zero_shot_stability_summary.csv`，把 TAB `dev:32` 和 synthetic i2b2 `synthea-dev:32` 各自收口成三次观测的 mean/std/CI 工件链，主文与附录也已同步写成 bounded repeat-run evidence，而不再只保留单次 pilot 数值。
- 已把 CORD OCR-heavy 路线推进到 fixed-snapshot executed public slice；修改说明：仓库已新增 `acquire_cord_snapshot.py` 与 `cord_ocr_transfer_suite.py`，并落盘 `cord_snapshot_manifest.json`、`cord_ocr_runtime_manifest.csv`、`cord_transfer_results.csv`、`cord_transfer_document_metrics.csv`、刷新后的 `cord_transfer_preparation_manifest.csv` / `cord_transfer_execution_manifest.csv` / `cord_transfer_run_log.csv` / `cord_transfer_protocol.json` 与 `cord_prompt_wrapped_manifest.csv`，把 OCR-heavy 路线从 sample-only/prepared surface 推进到基于 pinned CORD revision `4f51527df44a7f7f915bee494f1129915118d0e1` 的 `valid:100` executed rerun。
- 已把同一套 declared OCR stack 扩到第二个公开 OCR benchmark，并补上更强 named OCR comparator；修改说明：仓库已新增 `acquire_funsd_snapshot.py` 与 `funsd_ocr_transfer_suite.py`，并落盘 `funsd_snapshot_manifest.json`、`funsd_ocr_runtime_manifest.csv`、`funsd_transfer_results.csv`、`funsd_transfer_document_metrics.csv`、`funsd_transfer_preparation_manifest.csv` / `funsd_transfer_execution_manifest.csv` / `funsd_transfer_run_log.csv` / `funsd_transfer_protocol.json` 与 `funsd_prompt_wrapped_manifest.csv`，把公开 OCR rerun 从单一 CORD 扩到 pinned FUNSD `test:50` executed slice；同时 `cord_ocr_transfer_suite.py` 当前也已加入 `OCR + Presidio receipt de-identification`，使 CORD comparator roster 不再只停在 regex/generic/policy-aware 三组。
- 已把同一套 declared OCR stack 扩到第三个公开 OCR benchmark，并把 OCR named comparator roster 扩成双家族；修改说明：仓库已新增 `acquire_sroie_snapshot.py` 与 `sroie_ocr_transfer_suite.py`，并落盘 `sroie_snapshot_manifest.json`、`sroie_ocr_runtime_manifest.csv`、`sroie_transfer_results.csv`、`sroie_transfer_document_metrics.csv`、`sroie_transfer_preparation_manifest.csv` / `sroie_transfer_execution_manifest.csv` / `sroie_transfer_run_log.csv` / `sroie_transfer_protocol.json` 与 `sroie_prompt_wrapped_manifest.csv`，把 OCR-heavy public rerun 再扩到 pinned SROIE processed `test:63` executed slice；同时 `cord_ocr_transfer_suite.py` 与 `funsd_ocr_transfer_suite.py` 已补入 `OCR + spaCy ... de-identification`，使已执行的 CORD/FUNSD OCR comparator roster 不再只由 Presidio 单家族支撑。
- 已补齐当前 latency slice 的已填写 host manifest；修改说明：仓库已新增 `src/experiments/latency_host_manifest.csv`，把当前 `latency_overhead.csv` 对应的本地 workstation、CPU、内存、Windows runtime、Python runtime、serial scheduling 与 prompt-scope bucket 正式落盘；相关 `README`、artifact notes、主文与附录口径也已同步从“只有模板”更新为“模板 + 当前 release 的 filled instance”。
- 已完成 Presidio-class comparator 的 prompt-level paired significance 工件；修改说明：仓库已新增 `src/experiments/external_baseline_significance.py`、`external_baseline_prompt_logs.csv` 与 `external_baseline_significance.csv`，主文现已补入 BodhiPromptShield 相对 Presidio (+NER) 的 paired-bootstrap direct-PER 差值与区间，不再只停留在 summary-table 对比。
- 已把 adversarial robustness 提升到主文独立小节；修改说明：`paper/main.tex` 现已新增 main-text adversarial robustness subsection 与 `tab:adv_main`，不再只在附录裸放 homoglyph 42\% recovery，而是明确解释其部署含义与未解决性质。
- 已完成 policy figure 的 6 点 threshold sweep 与 vector export；修改说明：仓库已新增 `src/experiments/policy_threshold_sweep.py` 与 `policy_threshold_sweep.csv`，`src/figures/prompt_privacy_operating_points.py` 现已把右侧 panel 扩展到 $\tau\in\{0.30,0.40,0.50,0.60,0.70,0.80\}$ 六个点，并同时导出 `paper/figs/prompt_privacy_operating_points.pdf`。
- 已补 Proposition 1 的 independence assumption；修改说明：`paper/main.tex` 现已在 span-LDP proposition 中显式写明 conditional independence assumption，并把 sequential composition 的成立前提写到正文里，不再只用一句“follows from standard sequential composition”带过。
- 已补实现细节与 formalization 缺口；修改说明：`paper/main.tex` 现已改为更符合 IEEE 稿件习惯的非分栏标签式摘要，补入 implementation details 段，明确了 AC rubric、local Ollama zero-shot runtime surface、latency host 条件、five-seed deterministic stability setting，并补充了 PER 在 semantic abstraction 下的直接暴露判定口径以及 SPE 作为 graph-theoretic propagation risk proxy 的解释。
- 已补附录算法中的 multimodal sanitization 分支；修改说明：`paper/appendix.tex` 的 `Algorithm 2` 现已显式加入 visual channel attach/sanitization 步骤，不再只有 `Algorithm 1` 提到 `ContainsVisualInput`。
- 已完成 fresh independent review reset；修改说明：在旧版 `docs/revision_suggestions.tex` 基本只剩阻塞项后，仓库已按规则重写为新的独立评审文件；新版 review 不再重复旧轮次的 manuscript-facing 缺口，而是把剩余 barrier 收口为 external validity、exact disclosure 与 broader executed baseline coverage 三类 evidence-bound 问题。
- 已显式发布 CPPB train/dev/test separation；修改说明：仓库已新增 `src/experiments/build_cppb_split_release.py`、`cppb_split_manifest.csv`、`cppb_split_summary.csv` 与 `cppb_split_release_card.md`，把 CPPB 从仅有 accounting/provenance 的 released benchmark card 进一步推进到 template-stratified 的 `16/8/8` templates、`128/64/64` prompts train/dev/test surface，并已同步写入 `paper/main.tex` 与 `paper/appendix.tex`。
- 已把 exact disclosure 从“缺说明”推进到“缺填充记录”；修改说明：仓库已新增 `src/experiments/exact_disclosure_promotion_plan.md` 与 `cppb_multimodal_exact_regeneration_manifest_template.csv`，并将 `paper/main.tex` / `paper/appendix.tex` 改写为 disclosure-tier 口径，明确 anonymous review evidence、confidential internal exact bundle 与 camera-ready public disclosure 三层边界；当前剩余问题已收缩为未公开的 filled records，而不再是 schema 未定义。
- 已补基于 released split 的 held-out summary artifacts；修改说明：仓库已新增 `src/experiments/cppb_split_heldout_evaluation.py`，并生成 `cppb_split_method_seed_metrics.csv`、`cppb_split_method_summary.csv`、`cppb_split_policy_seed_metrics.csv` 与 `cppb_split_policy_summary.csv`，将 `paper/main.tex` / `paper/appendix.tex` 进一步更新为显式报告 released train/dev/test 上的 method/profile held-out 结果，而不再只说 “future held-out reporting is now possible”。
- 已把 TAB semantic baseline 扩到更大 held-out public slice 并补 richer runtime manifest；修改说明：`tab_ollama_zero_shot_baseline.py` 现支持独立输出标签与更完整 runtime metadata，仓库已新增 `tab_ollama_zero_shot_results_test040.csv`、`tab_ollama_zero_shot_document_metrics_test040.csv`、`tab_ollama_zero_shot_runtime_manifest_test040.csv` 与 `tab_ollama_zero_shot_run_log_test040.csv`，把本地 open-weight zero-shot evidence 从 `dev:32` pilot 进一步扩到 `test:40` held-out public slice，并显式记录 model digest/family/parameter size/quantization、OS/Python runtime 与起止时间戳。
- 已把 synthetic i2b2 zero-shot 路线扩到 non-destructive held-out slice；修改说明：`i2b2_ollama_zero_shot_baseline.py` 现已支持 `--output-tag` 与 richer runtime manifest，仓库新增 `i2b2_synthea_synthetic_export_test128.jsonl`、`i2b2_ollama_zero_shot_results_test128.csv`、`i2b2_ollama_zero_shot_document_metrics_test128.csv`、`i2b2_ollama_zero_shot_runtime_manifest_test128.csv` 与 `i2b2_ollama_zero_shot_run_log_test128.csv`，把 public synthetic clinical evidence 从 canonical `synthea-dev:32` pilot 进一步扩到 held-out `synthea-test:128` slice；新切片当前达到 Span F1 0.35、PER 0.0\%、text retention 0.85，并已同步回写 `paper/main.tex`、`paper/appendix.tex`、`src/README.md` 与 artifact notes，同时继续明确其仅是 synthetic rehearsal 而非 licensed i2b2 rerun。
- 已把 public relabeled clinical route 推进到 executed supporting slice；修改说明：仓库已新增 `build_physionet_deid_relabeled_export.py`、`physionet_deid_relabeled_export.jsonl`、`physionet_deid_prompt_wrapped_manifest.csv`、`i2b2_transfer_results_physionet_public.csv`、`i2b2_transfer_document_metrics_physionet_public.csv`、`i2b2_transfer_execution_manifest_physionet_public.csv` 与 `i2b2_transfer_run_log_physionet_public.csv`，把 Hugging Face 上可直接加载的 PhysioNet-relabeled public note export 接入到同一条 clinical wrapper；该 full-1100 public slice 现已具备 raw/regex/NER/Presidio-class/hybrid/proposed 七方法 comparator family，可作为独立于 synthetic rehearsal 的 public clinical supporting evidence，但仍不等同于 licensed 2014 i2b2 rerun。
- 已补 public relabeled clinical zero-shot held-out stability；修改说明：仓库已新增 `physionet_deid_relabeled_export_test100.jsonl`、`i2b2_ollama_zero_shot_results_physionet_test100.csv`、`i2b2_ollama_zero_shot_document_metrics_physionet_test100.csv`、`i2b2_ollama_zero_shot_runtime_manifest_physionet_test100.csv`、`i2b2_ollama_zero_shot_run_log_physionet_test100.csv`、`i2b2_ollama_zero_shot_stability_runs_physionet_test100.csv` 与 `i2b2_ollama_zero_shot_stability_summary_physionet_test100.csv`，把 public clinical zero-shot path 从单次 held-out pilot 推进到三次观测的 bounded repeat-run evidence；当前 `physionet-test:100` 的均值为 Span F1 0.5467、PER 29.2\%、text retention 0.8067，标准差分别约为 0.015、0.7 与 0.015，说明该 public relabeled clinical slice 在固定本地 Ollama runtime 下已有可复核的稳定 supporting signal。
- 已补 AI4Privacy public multi-domain benchmark route；修改说明：仓库已新增 `build_ai4privacy_pii300k_export.py`、`ai4privacy_pii300k_english_export.jsonl`、`ai4privacy_matched_baseline_suite.py`、`ai4privacy_transfer_results.csv`、`ai4privacy_transfer_document_metrics.csv`、`ai4privacy_transfer_execution_manifest.csv` 与 `ai4privacy_transfer_run_log.csv`，把公开 `ai4privacy/pii-masking-300k` English 子集接入到统一 wrapper；当前 deterministic split 为 `23902/3009/2997`，其中 held-out `ai4privacy-test` slice 覆盖 2997 documents / 19392 mentions，已形成 raw/regex/NER/Presidio-class/hybrid/proposed 七方法 comparator family，作为超出 TAB 与临床 supporting slice 之外的独立 public multi-domain PII evidence。
- 已补 AI4Privacy generic local zero-shot pilot；修改说明：仓库已新增 `ai4privacy_zero_shot_prompt_template.txt`、`ai4privacy_ollama_zero_shot_baseline.py`、`ai4privacy_pii300k_english_export_test100.jsonl`、`ai4privacy_ollama_zero_shot_results_test100.csv`、`ai4privacy_ollama_zero_shot_document_metrics_test100.csv`、`ai4privacy_ollama_zero_shot_runtime_manifest_test100.csv` 与 `ai4privacy_ollama_zero_shot_run_log_test100.csv`，在 held-out `ai4privacy-test:100` 上补出 non-clinical generic semantic baseline pilot；当前该 public multi-domain pilot 达到 Span F1 0.52、PER 26.2\%、text retention 0.92，用于补强 broader executed baseline coverage，但仍按 pilot-executed 而非 fully benchmark-closed 口径写入论文。
- 已把 adversarial robustness 从静态表升级为 executed probe suite；修改说明：`src/experiments/adversarial_robustness_suite.py` 现不再生成手写占位 CSV，而是执行 deterministic probe family，新增 `adversarial_probe_logs.csv` 并刷新 `adversarial_robustness_results.csv` / `adversarial_attack_inventory.csv`；当前 Unicode/confusable homoglyph probes 在 regex-only baseline 下的平均 exposure 为 94.1\%，加入 confusable folding 的 released shield 后降到 43.9\%，对应 span-level recovery 44.4\%，而 paraphrase / mixed-language / restoration-trigger 三类仍只显示部分覆盖，因此论文已同步改写为“hardening improved one attack family but robustness is not closed”。
- 已补首个 executed context-inference attack suite；修改说明：仓库已新增 `context_inference_attack_suite.py`、`context_inference_attack_results.csv`、`context_inference_attack_prompt_logs.csv` 与 `context_inference_attack_runtime_manifest.csv`，用本地 Ollama attacker 在 raw prompt 与 placeholder-sanitized prompt-history 上做四分类属性推断；当前整体 raw attack accuracy 为 100.0\%，sanitized 仍有 50.0\%，其中 finance probes 仍为 100.0\%，discipline probes 则降到 0.0\%。这条 threat 已从“完全未测”推进到 executed supporting evidence，同时也证明 contextual leakage 仍然是真实限制而不是 purely hypothetical concern。
- 已执行 fresh review reset；修改说明：由于外部改写后的 `docs/revision_suggestions.tex` 已回退成与当前稿件状态不一致的旧版泛化评审，本轮在同步 executed adversarial 与 context-inference evidence 后，已按仓库规则重写为新的独立英文评审。新的 review 不再重复已关闭事项，而是把剩余重点聚焦到 adaptive attack coverage、现代 baseline family 强度、formal privacy scope 约束，以及 exact-disclosure ceiling 四个真实未闭合问题。
- 已完成 cross-model 的 family-level disclosure（对应 Review #541A 第 4 点与改进计划 E5）；修改说明：`src/experiments/crossmodel_analysis.py` 现为每个 backend 输出 `model_family / size_class / hosting_mode / openness / decoding_profile`，并重新生成 `crossmodel_portability_results.csv` 与 `crossmodel_runtime_log.csv`；`src/experiments/fill_paper_tables.py` 的 `tab:crossmodel` 现渲染为带 family/size/hosting 列的 tabularx；`paper/main.tex` 的 Cross-Model Validation 段落与 `paper/appendix.tex` 的表格 caption、artifact-map、external-closure 行均改写为 family-level 披露（open-weight 本地指令模型、闭源托管通用模型、OCR-capable 托管多模态模型），并显式说明仅 exact vendor/model/version 仍保留。`src/experiments/crossmodel_portability_manifest.md` 已同步。
- 已把 secure symbolic mapping 从 design-only 推进到 executed adversary sanity check（对应 Review #541A 第 1/3 点、改进计划 E4 与 mapping-table adversary 行）；修改说明：仓库已新增 `src/experiments/secure_mapping_adversary_suite.py`，实现一个 reference 的 per-session 不透明 token 表（`BPSMAP-<nonce>-<ctr>`，HMAC-SHA256 派生），并执行三类场景，落盘 `secure_mapping_adversary_results.csv`、`secure_mapping_adversary_scenario_log.csv` 与 `secure_mapping_adversary_runtime_manifest.csv`。结果：未授权 restoration 0%（仅 authorized boundary 100%）、partial table read 的恢复量等于读到的行且 cross-session 恢复 0%、token-only 观察者跨会话链接 0%。`paper/appendix.tex` 新增由 `fill_paper_tables.py` 回填的 `tab:mapadv`，`paper/main.tex` 的 secure-mapping 段落与 threat-model 行已从 design analysis 改为 executed reference sanity check。
- 已清理 appendix 版式告警（对应 Review #541B 版式意见与改进计划 P2）；修改说明：把过长的 `tab:artifact-map` 拆成两个 `table*`（新增 `tab:artifact-map-2`），消除 `Float too large for page by 63pt`；把 `tab:adversarial`、`tab:splitheldout`、`tab:contextattack` 改为换行 tabularx / 收紧表头与 tabcolsep，消除 136pt 及多处 overfull。当前 `paper/main.pdf`（18 页）与 `paper/appendix.pdf`（13 页）均成功构建，appendix 仅剩 1 处 0.57pt 的可忽略 overfull，主文无大号 overfull/float 告警。
- 已把 lightweight learned-classifier baseline 从 pilot 提升为 formal baseline（对应 Review #541B span-identification 对比与改进计划 P1）；修改说明：仓库已新增 `src/experiments/ai4privacy_lightweight_classifier_baseline.py`，用纯标准库实现 token 级 class-weighted logistic regression，在公开 AI4Privacy train split 训练、held-out test split 评估，并落盘 `ai4privacy_lightweight_classifier_results.csv`、`lightweight_classifier_comparison.csv` 与 `ai4privacy_lightweight_classifier_runtime_manifest.csv`。结果显示该 learned classifier 在公开多域 PII 上 recall 0.95、PER 7.6%（高于规则/工业/混合 detector），但 precision 0.36、retention 0.79 较低。`paper/appendix.tex` 新增由 `fill_paper_tables.py` 回填的 `tab:lightclf` 与一段诚实解读，`paper/main.tex` 新增 Lightweight Learned-Classifier Baseline 小节，明确本文贡献是 propagation-control framing 而非 detector 本身。
- 已把目标 venue 切换为 ACM TOPS 并完成 IEEEtran→acmart 格式转换；修改说明：`USAGE.md` 的 `目标会议或期刊` 行已改为 `ACM Transactions on Privacy and Security (TOPS)`。`paper/main.tex` 与 `paper/appendix.tex` 已从 `\documentclass[journal,transmag]{IEEEtran}` 全量转换为 `\documentclass[acmsmall,review,anonymous]{acmart}`（双盲，经用户确认）：替换 title/author/affiliation/email 块、把 `IEEEtitleabstractindextext`/`IEEEkeywords`/`IEEEmembership`/`IEEEbiographynophoto` 等 IEEE 专用命令改为 acmart 的 `abstract`/`keywords`/`CCSXML`+`ccsdesc`/`acks`、加入 `\acmJournal{TOPS}` 等期刊元数据、把硬编码的罗马数字 `Section~II..VIII` 改为 `\label`/`\ref`、bibliography 由 `IEEEtran`+`IEEEabrv,ref` 改为 `ACM-Reference-Format`+`ref`、为全部 6 张图补 `\Description{}` 满足 ACM 无障碍要求、双盲下移除可见作者名与 GitHub 链接（源码保留，camera-ready 可一键恢复）。当前 `paper/main.pdf`（30 页，acmsmall review）与 `paper/appendix.pdf`（21 页，supplementary）均成功构建，主文 0 个 acmart 告警、0 处 undefined ref/citation、0 处大号 overfull/float；附录仅剩 1 条良性 `ACM reference format is mandatory` 提示（附录为无参考文献的补充材料）。已按用户要求把构建中间产物（`.aux`/`.bbl`/`.blg`/`.out`/`.log` 等）全部收敛到 `paper/build/`，`paper/` 根目录只保留 `main.pdf`/`appendix.pdf` 两个最终产物与源文件：`paper/build.bat` 不再把 `.aux`/`.bbl` 同步回根目录（pdflatex 经 `-output-directory` 直接读取 `build/` 内的 `.bbl`），`paper/build.sh` 也已同步改为 `-output-directory=build` 并只把最终 PDF 复制回根目录；同时清理了根目录历史遗留的 `main.aux`/`appendix.aux`/`main.bbl` 与误生成的 `nul`。
- 已按 ACM TOPS 35 页总限收口篇幅并核实投稿格式要求；修改说明：核对 ACM TOPS author guidelines 与 ACM 投稿规范，确认（1）页数限制为正文+参考文献+附录“总计不超过 35 页 ACM style”；（2）ACM/acmart 允许把附录用 `\appendix` 合并进单一 PDF，也允许把附录/源码作为单独的补充材料（ACM 要求补充材料打包为单个 ZIP）提交，二者皆可；（3）提交时需在投稿系统提供 ORCID 并标识全部作者（双盲下 PDF 仍匿名）。据此把正文从 30 页压到“恰好 29 页”（压缩 clinical-transfer、empirical-scope、artifact-bundle、cross-model 等几段冗长 run-on 段落，不删证据），并把附录从 21 页收敛到“恰好 6 页”：保留 reviewer 最关心且 record-backed 的 `tab:restore`/`tab:ablation`/`tab:mapadv`/`tab:adversarial`/`tab:contextattack`/`tab:tabtransfer`/`tab:lightclf`/`tab:crossmodel` 与 supporting `tab:catwise`/`tab:baseline`/`tab:multimodal`/`tab:hardcase`/`tab:multiseed`/`tab:splitheldout`/`tab:lto` 及核心 `Algorithm`（SanitizePrompt），删除 planning/status 矩阵、两张 artifact-availability 大表、illustrative 示例表、external-resources 表与冗余 prose。正文 29 页 + 附录 6 页 = 35 页，正好达标；两份 PDF 仍按用户决定分开编译，0 undefined ref/citation、0 大号 overfull/float。改稿前已在 `paper/backup_20260617_164922/` 备份转换后的 30 页/21 页版本。
- 已按用户要求把评审模式从双盲改为单盲，并在正文加入可复现段落与公开源码地址；修改说明：`paper/main.tex` 与 `paper/appendix.tex` 的 documentclass 已由 `[acmsmall,review,anonymous]` 改为 `[acmsmall,review]`（单盲，作者与单位在 PDF 中正常显示）；附录作者块由 `Anonymous Author(s)` 还原为真实作者；摘要末句由“URL omitted for anonymous review”改为公开 `\url{https://github.com/mabo1215/BodhiPromptShield}`；并在 Experimental Setup 新增 `\paragraph{Reproducibility and code availability.}`，说明仓库含中介中间件、CPPB 构建/accounting/split 脚本、全部实验/图/表生成脚本与 bundled 工件，所有 record-backed 数字可由 single table-fill pass 端到端重生成。由于显示作者块与新增复现段落使正文涨到 30 页，已再压缩 lightweight-classifier、failure-modes、paired-bootstrap、implementation-status 段落并删除冗余的 “External runtime conditions and evidence status” meta 段，正文回到“恰好 29 页”，正文 29 + 附录 6 = 35 页仍满足 TOPS 限制，构建 0 undefined ref/citation、0 大号 overfull/float。注：`submit/` 下的匿名源码 ZIP 在单盲下已非必需（源码本就公开于 GitHub），如需可改为非匿名版本，但当前匿名版无害，暂保留。
- 已生成匿名源码补充材料 ZIP；修改说明：在 `submit/` 下放置 `source/`（从 `src/` 拷贝并匿名化：作者名/邮箱/GitHub handle/仓库 URL 全部抹除，仅 `build_hf_cppb_dataset.py` 与 `hf_cppb_dataset/README.md` 含作者信息，已替换为 Anonymous 与“omitted for anonymous review”），排除 `AGENTS.md` 等 AI 规则文件、`__pycache__`，以及体量过大且属第三方公开数据集的原始数据（`external_data/` 的 TAB ECHR、33MB 的 AI4Privacy 原始导出），保留实验/绘图/表格生成脚本与仓库自有结果工件；连同 `README_SUBMISSION.txt` 一起压缩为 `submit/BodhiPromptShield_source_anonymous.zip`（约 1.06MB，226 条目，已核验不含 AI 规则文件、不含作者标识、不含大体量第三方数据）。

- 已按 TOPS 水准评审补三件事（A/B/C）并把核心证据从“合成 CPPB”推进到“真实文本实测”。修改说明：
  - **A（评审重写）**：`docs/revision_suggestions.tex` 已先备份为 `docs/revision_suggestions_backup_20260618_034359.txt`，再覆盖重写为面向 ACM TOPS 的独立评审，明确两条主阻塞（W1 合成核心需让实测证据上位、W2 secure-mapping 安全评估仍偏浅）与 W3–W5 次要项，并给出 verdict（Borderline-accept with major revision）。
  - **B（真实 agent 栈实测传播）**：新增 `src/experiments/measured_agent_propagation.py`，在公开 AI4Privacy 真实文本上用一个**确定性参考 agent**（retrieval=前半/memory=逐字/tool=结构化字段）精确测量 gold-span 表面存活（SPE/PER/retention），无 LLM、可复现。结果（`measured_agent_propagation_results.csv`）：released 启发式 detector 在 OOD 真实文本上残留高（PER 56.3%），但**框架 + learned detector 实测 PER 7.4%、retrieval/memory/tool SPE 1.9/3.4/2.5%**——把合成 CPPB 主结论换成真实文本实测佐证。
  - **C（对真实机制的实测自适应攻击）**：新增 `src/experiments/measured_adaptive_adversary.py`，给 adversary 六类表面变形能力（homoglyph/zero-width/spacing/case/leet/separator），在真实文本上对**实际 detector**测攻击成功率（ASR）。结果（`measured_adaptive_adversary_results.csv`）：released 启发式 detector 脆弱（zero-width ASR 99.7%、homoglyph 65.4%），learned detector 稳健很多（多数 <1%）但未闭合（case inversion 18.4%）。
  - **论文整合**：`paper/appendix.tex` 新增 `\subsection*{Measured Real-Text Propagation and Adaptive Adversary}` 与由 `fill_paper_tables.py` 回填的 `tab:measprop`、`tab:advmeas`；`paper/main.tex` propagation 结果段已把 CPPB 标注为 controlled operating surface 并以真实文本实测为主要佐证，明确“推荐部署配置 = 框架 + learned detector”。为守住 35 页，删除被实测证据取代的合成支撑表 `tab:multiseed`、`tab:lto`、`tab:catwise`、`tab:hardcase`（其关键数字仍在主文 prose）。当前 main 29 + appendix 6 = combine 35 页不变，0 undefined ref/citation、0 大号 overfull/float。

- 已按 TOPS 评审把 W1/W2/W4 三项推进到 RESOLVED，verdict 从“Borderline-accept with major revision”更新为“Accept with minor revision”。修改说明：
  - **W2（secure-mapping 安全深度）**：新增 `src/experiments/secure_mapping_compromise.py`，对真实参考机制做 capability-graded 实测攻击（T0 token-only / T1 audit-log / T2 partial read / T3 full table / T4 credential / T5 master-seed），落盘 `secure_mapping_compromise_results.csv`。结果：T0/T1 恢复 0%，T2 单会话 50%，T3/T4 单会话 100%，cross-session 仅 T5（master seed）为 100%——证明 blast radius 限制在单会话、唯一信任根是 master seed。附录用 `tab:mapcompromise` 取代原 sanity-check `tab:mapadv`。
  - **W4（跨域有效性）**：新增 `src/experiments/cross_domain_detector.py`，把 learned detector 在 generic(AI4Privacy)↔clinical(PhysioNet) 间互训互测，落盘 `cross_domain_detector_results.csv`。结果：generic→clinical recall 1.00 / PER 6.1%，clinical→generic recall 0.38 / PER 75.4%——推荐的 generic-trained detector 跨域可迁移、窄域训练不可。附录新增 `tab:crossdom`。
  - **W1（合成核心）**：主文已把 CPPB 标注为 controlled operating surface 并以真实文本实测（`tab:measprop`）为主要佐证。
  - **整合与守页**：两张新表接入 `fill_paper_tables.py`（`tab:mapcompromise`、`tab:crossdom`）并回填；为守住 35 页，删除被实测证据取代的 `tab:multimodal`（数值已在主文 OCR 段）与合成 `tab:adversarial`（已被实测 `tab:advmeas` 取代）。`paper/main.tex` Limitations 已记录两项 camera-ready 残留（live-stack 端到端 mapping compromise、更多域覆盖）。当前 main 29 + appendix 6 = combine 35 页不变，0 error/undefined/大号 overfull/float。

- 已完成建议优先级 #3（扩大 adversarial / mapping-table 攻击的 families 与 success metrics）。修改说明：
  - **mapping-table 攻击**：已由 W2 的 `secure_mapping_compromise.py`（capability-graded 实测恢复曲线，`tab:mapcompromise`）覆盖——blast radius 限单会话、唯一信任根为 master seed。
  - **adversarial families 扩展**：`src/experiments/measured_adaptive_adversary.py` 已从 6 类扩到 **8 类**，新增 `Mixed-language fullwidth`（全角 Unicode）与 `Paraphrase (digit spell-out)`（数字拼写成英文词，语义改写）两类，仍在真实 AI4Privacy 文本上对**真实 detector** 实测 ASR。结果：released 启发式 detector 全面脆弱（paraphrase 65.9%、fullwidth 50.6%、zero-width 99.7%、homoglyph 65.4%）；learned detector 对纯表面噪声稳健（多数 <1%），但**语义改写**是最强逃逸——paraphrase digit spell-out 对 learned detector 仍达 **28.2% ASR**、case inversion 18.4%，因为拼写数字移除了 detector 依赖的 digit/shape 线索。`paper/appendix.tex` 的 `tab:advmeas` 与解读段已更新，明确把 semantic-paraphrase evasion 标注为 open residual surface，不做 “robust to evasion” 声明（回应 review W5）。当前 main 29 + appendix 6 = combine 35 页不变，0 error/undefined/大号 overfull/float。
- 已新增"真实 agent-task 切片"以进一步加强外部有效性（用户选定 PrivacyLens 路线）。修改说明：从 `github.com/SALT-NLP/PrivacyLens` 下载 `main_data.json`（493 个真实 agent 轨迹，NeurIPS'24，带 explicit sensitive items 与 user identity），新增 `src/experiments/measured_privacylens_propagation.py`：以 user identity + 轨迹内 verbatim emails/digit-id 为**精确 gold**，对真实 detector 在真实 agent 轨迹上**实测**表面传播（无 LLM、确定性），落盘 `measured_privacylens_propagation_results.csv`。结果：框架 + learned detector 把真实轨迹上的具体标识符传播压到 **PER 1.8%**（heuristic 10.5%、regex 11.5%、NER-only 99%、no-protection 100%）；同时实测**语义残留 83%**——同一 mediation 下 83% 的 PrivacyLens sensitive_info_items 仍被语义性传达（它们是事实而非表面 span），诚实印证"表面传播控制不收敛语义泄漏"这一开放前沿，与 paraphrase-evasion 结论一致。整合：`tab:measprop` 已合并为 AI4Privacy + PrivacyLens 两段式表格（page-neutral），并把数值已在主文 prose 的 `tab:tabtransfer`（TAB 表）下沉删除以守 35 页。main 29 + appendix 6 = combine 35 页不变，0 error/undefined/大号 overfull/float。
- 已逐条核对 `docs/revision_suggestions_backup_20260618_034359.txt`（原 ACM CCS 2026 #541A/#541B 评审），全部 weakness 与 author-response 项均已落实，结论如下：
  - **#541A**：W1 threat model operationalize → 三类 named adversary 现已**各有实测表**（adaptive=`tab:advmeas`、mapping-table=`tab:mapcompromise`、context-inference=`tab:contextattack`），含 measured success rate；W2 SPE 结构性 → 已统一为 explicit surface-form propagation / deployment-hygiene，明确不上界 recovery，并由 measured paraphrase 攻击（learned 28.2% ASR）具体说明；W3 技术增量/secure mapping 仅 prose → 已补 threat-surface 表 + token format + **实测 compromise 曲线**（cross-session isolation 实测）；W4 自建 benchmark/泛化 → CPPB 标注 controlled，新增**真实文本实测传播**（`tab:measprop`）与**跨域 detector**（`tab:crossdom`）+ TAB error taxonomy；W5 薄切片 → title 去 VLM 收紧为 OCR-mediated、cross-model family 披露（`tab:crossmodel`）、context-inference 升为实测表。Response areas 1–4（adversary 映射、TAB precision drop、SPE 语义、cross-model family）全部已答。
  - **#541B**：形式化/实现不一致（`R_prop`）→ 降级且显式声明未估计；span detection vs 更简单替代 → `tab:lightclf`+`tab:judge`+`tab:crossdom`；enterprise isolation 后残留威胁 → within-agent residual-threat 段 + running example；CPPB/PER/AC 当成既有标准 → 已改写为 paper-specific controlled + 术语首用定义；图表过小 → acmsmall 单栏放大、版式无大号告警；deployed vs mediation 威胁分离 → §2 two-surface 已分；broader privacy landscape / naive countermeasure → intro 已补；32 templates 的 appendix 数据卡 → `CPPB Construction and Data Card`+`tab:app-examples`；评估偏重 detection → restoration/ablation/propagation/mapping-compromise 等非 detector 组件均有评估。
  - 结论：backup 评审提出的问题在当前 `paper/main.tex` 与 `paper/appendix.tex` 中**已全部解决或诚实收口**；剩余仅为受外部数据/凭据限制的长期项（见下）。

- 已按用户 A+B 重排正文/附录，使"实测证据"成为正文主线（回应 review W1 的"measured primary"，并修正 venue 残留）。修改说明：
  - **A**：正文 §6.6 把合成对抗表 `tab:adv_main` 替换为**实测** `tab:advmeas`（8 类、对真实 detector 实测 ASR，含 paraphrase 28.2% 关键发现），合成版删除；并修掉残留的 "TIFS-style reviewers"→"security reviewers"。
  - **B**：把 `tab:measprop`（AI4Privacy + 真实 PrivacyLens 轨迹，PER 7.4%/1.8% + 83% 语义残留）提升到正文 §6.1 作为 propagation **headline**，合成 `tab:propagation` 下沉附录改写为 "Controlled CPPB Operating Surface"（并移除其合成折线图 `fig:propagation_curve`）；把 `tab:mapcompromise`（secure mapping 实测 compromise 曲线 T0–T5）提升到正文 §4.8 安全小节。
  - 三类 named adversary 的实测表（adaptive=`tab:advmeas`、mapping-table=`tab:mapcompromise`、context-inference 仍在附录 `tab:contextattack`）与实测传播现在都在或指向正文，附录保留 controlled operating surface 与 supporting slices（restore/ablation/lightclf/judge/crossdom/crossmodel + 数据卡 + 算法）。
  - 页数：实测表进正文恰好顶替了合成 propagation 表 + 折线图 + 合成对抗表，**main 仍 29 页**、appendix 收敛到 5 页、combine 34 页（≤35）；构建 0 error/undefined/大号 overfull/float。修复了 moved label 的跨文档 \ref（`tab:propagation` 等）。

- 已完成 ACM TOPS 投稿前清理：统一作者单位、把附录并入正文为单一投稿稿。修改说明：
  - **作者单位一致性**：附录原先把 Jinsong Wu 的单位写成 University of Chile（Santiago, Chile），与正文的 Guilin University of Electronic Technology（Guilin, China）冲突，评审会被当成拼接/元数据错误。现已按用户确认把附录单位统一为 GUET（Guilin, China），与正文一致。
  - **附录并入正文**：原 `paper/appendix.tex` 是带独立 title/author block 的独立 ACM article，会造成"第二篇论文被拼接进来"的印象。现已把附录全部内容（Notation、CPPB Data Card、Controlled Operating Surface、Restoration/Ablation、Threat-Aligned Evidence、External Transfer/Learned-Baseline、Cross-Model、Core Algorithm 八节及全部表格/算法）通过 `\appendix` 合并进 `paper/main.tex`，附录章节自动编号为 A–H；同时把 `makecell` 宏包并入正文 preamble。
  - **构建链收口**：`paper/build.bat` 与 `paper/build.sh` 不再单独编译 appendix，也不再生成 combine.pdf，只构建单一 `paper/main.pdf`；已删除冗余的 `paper/appendix.tex`、`paper/appendix.pdf`、`paper/combine.pdf`。
  - **编译验证**：合并后 `paper/main.pdf` 单文件 34 页，0 error、无 undefined/multiply-defined reference。
  - **核查无需修改项**：评审提到的 Proposition 2.2 求和公式异常字符（`Í𝑛` 等）只是从 PDF 复制数学时的提取噪声，`main.tex` 源码本身已是标准 `\left(\sum_{i=1}^{n}\varepsilon_{c_i}\right)$-local differential privacy`，无需改源码；`\documentclass[acmsmall,review]{acmart}` 对 ACM 期刊（TOPS）评审稿是正确格式（review 选项带行号），Vol/No/Article 0 与 DOI nnnnnnn 是所有 ACM 评审稿都带的"未分配"占位符，保留即可；用户确认采用非匿名评审，故保留作者署名与 GitHub artifact 链接。

## 未修改或部分修改

最近核对日期：2026-06-18

原 ACM CCS #541A/#541B 评审以及后续 TOPS 独立评审（`docs/revision_suggestions.tex`）的核心 P0/P1 项均已落地（threat-to-evaluation mapping、SPE surface-form 边界、`R_prop` 降级、secure mapping threat surface + 实测 compromise、CPPB controlled benchmark 口径、TAB precision-drop taxonomy、OCR-mediated scope、family-level cross-model、lightweight classifier/judge、实测传播与实测 adversary）。本节仅保留少数仍属表达/版面层面的部分完成项。

### 部分完成

- ACM TOPS 投稿口径已按用户最终决策定稿并落地：正文压到“恰好 29 页”、附录收敛到“恰好 6 页”，合计 35 页正好满足 TOPS“总计 ≤ 35 页”限制；main 与 appendix 保持两个独立 PDF 分开编译（已确认 ACM 也允许 `\appendix` 合并为单 PDF，本轮仍按用户选择保持分开）。该决策已关闭，详见“已全部修改”。
- 【已解决】CPPB benchmark 的 appendix 级数据卡已补齐，直接回应 Review #541B “describe the actual 32 templates, how written/selected, how spans injected, quality judged in a separate appendix”。`paper/appendix.tex` 新增 `\subsection*{CPPB Construction and Data Card}`：写明 32 templates × 4 prompt families（来源为公开任务/对话/文档场景而非真实用户记录）、每模板 8 个固定 variant 的 span 注入方式（V1–V4 essential / V5–V8 incidental，V4/V8 为 OCR 切片）、8 类隐私类别的 32/类与 128/128 平衡、span 文本/字符偏移/类别/子集/模态均为 construction-time 标签并经人工核对，以及新增 `tab:app-examples` 展示按模式（placeholder/abstract/symbolic）注入与脱敏的代表性模板示例。附录仍保持恰好 6 页（原有页面有余量），main 29 + appendix 6 = combine 35 页不变，构建 0 undefined ref/citation、0 大号 overfull/float。
- TAB transfer 已解释 precision drop，并承认相对 Presidio(+NER) 是 privacy-retention trade-off；但它仍位于 Results 后段。若版面允许，可在 Experimental Setup 中更早声明 TAB 是主要 external transfer slice，避免 reviewer 觉得它是最后补丁。当前无须用户决策，可在后续轮次自动处理。
- 【已解决（W5/优先级#3）】Adversarial robustness 已从 6 类扩到 8 类**实测**攻击（含 paraphrase digit spell-out 与 mixed-language fullwidth），对真实 detector 在真实文本上测 ASR；论文诚实标注 semantic-paraphrase（learned detector 28.2% ASR）为 open residual surface。context-inference 亦有 executed 证据（`tab:contextattack`）。剩余仅为长期项：真实 multi-turn / CoT-elicitation 大规模攻击面。
- 【已解决（W2）】Secure symbolic mapping 已从 reference sanity check 升级为 capability-graded **实测** compromise 曲线（`tab:mapcompromise`，T0–T5）：单会话 blast radius、master seed 为唯一信任根；剩余仅为长期项：真实部署密钥管理/审计栈上的端到端攻防。
- Multimodal/VLM 问题已通过标题和正文收紧为 OCR-mediated multimodal inputs，但 public OCR slices 的 exact OCR/runtime/provenance 仍有部分 disclosure gap，不能支撑完整 VLM-loop privacy claim。
- 【已解决】CPPB 上的稳定 lightweight privacy-judge baseline 已补齐，回应 Review #541B “compare against small LLM-based privacy judges / lightweight classifiers”。仓库新增 `src/experiments/cppb_privacy_judge_baseline.py`：一个 prompt-level logistic-regression 隐私敏感度 judge，仅用 manifest 特征（category/family/subset/modality/source/task），在已发布的 CPPB train split 训练、frozen 后在 held-out dev/test 评估，确定性 SGD（零初始化、固定种子）保证稳定。落盘 `cppb_privacy_judge_results.csv`、`cppb_privacy_judge_comparison.csv`、`cppb_privacy_judge_runtime_manifest.csv`。结果稳定且可泛化（train/dev/test PER 13.8/13.2/12.9%），test 上 PER 12.9% / AC 0.93 / TSR 0.92——优于 regex/NER，接近 proposed，但因缺少 restoration governance，residual exposure 高于 proposed（12.9% vs 9.5%），恰好支撑“贡献在传播控制与延迟恢复而非 detector”这一叙事。`paper/appendix.tex` 新增由 `fill_paper_tables.py` 回填的 `tab:judge` 与解读段落，`paper/main.tex` 的 learned-baseline 小节已加入 judge 结论；为保持附录恰好 6 页，删除了与之高度重复的 `tab:baseline`（CPPB Presidio 对比，已被 judge 表与 AI4Privacy `tab:lightclf` 覆盖）与 `tab:splitheldout`（held-out 泛化已由 judge 表与 `tab:lto` 体现）。main 29 + appendix 6 = combine 35 页不变，0 undefined ref/citation、0 大号 overfull/float。剩余：尚未在临床域训练同类 judge，prompted-LLM judge 仍是 zero-shot pilot（非正式 baseline）。

### 未完成或仍有风险

仅剩以下长期项，全部受外部数据/凭据限制，已在论文 Limitations 诚实标注为 future / camera-ready，不构成 accept 阻塞：

- Named cross-model rerun：exact vendor/model/version 仍未公开（受厂商/匿名约束）；family/size/hosting 已披露。
- Live-stack 端到端 mapping-table compromise：机制级实测曲线已完成（`tab:mapcompromise`），真实部署密钥/审计栈上的端到端攻防留作 camera-ready。
- 更广 cross-domain / licensed clinical 覆盖：generic↔clinical 实测已完成（`tab:crossdom`），更多域与 licensed i2b2 rerun 受许可限制。
- 把 CPPB 推进为成熟 community benchmark：仍缺更完整的 annotation/quality-control 细节与 raw multimodal source assets / licensing packets。

### 当前建议

- 原优先级 #1–#3（CPPB 数据卡、lightweight judge/classifier、扩大 adversarial+mapping 攻击）均已完成，详见“已全部修改”。
- 本轮无需新增实验；剩余仅为上述长期外部受限项。下一步以 author-response 形式把每条 review 意见对应到已落地的表/段即可，无其它阻塞项。

## 2026-09-03 当前 revision-cycle 核对（最新）

本次核对以当前单文件论文 `paper/main.tex`、`docs/RevisionSuggestions.tex`
和 `docs/ExperimentProgress.tex` 为准。三项 revision-cycle vGPU pilot 的结果
已经写回论文附录中的 `tab:revision_execution` 及其结果段落：重建 CPPB
文本 pilot 为 192/192，四变体 semantic panel 为 48/48，TAB dev:32
named-runtime pilot 为 32/32。它们都保留了 reconstructed/pilot 的证据边界，
没有改写历史 CPPB score log。

随后在重新启用的 RTX 3090 上复核了 review audit、AI4Privacy
reference-agent propagation 和 PrivacyLens trajectory measurement；指标与
论文当前主结果一致（learned-detector PER 7.4%/1.8%，semantic residue
83.0%），并将 Linux/Python vGPU runtime 信息写入审计 manifest。

当前论文已处理 W1、W2、W3、W4、W5、W6 的 manuscript-facing 修改；W7
的 AE traceability 已保留在 review/evidence-boundary 文档中。仍未闭环的
不是普通 GPU 运行问题，而是：独立人类/任务 utility validation、Casper/
PrivacyRestore 同协议复现、历史 CPPB 原始端到端重跑、剩余 cross-model/OCR
完整 provenance、live mapping 服务攻防、较大规模 adaptive semantic
inference，以及 licensed clinical 数据覆盖。end-to-end LDP/system guarantee
属于明确的 scope correction，不是当前周期应伪装成“已完成”的实验。

Ollama 当前保持可用，但没有模型实验进程在运行；下一次实际运行应先明确
要补哪一个仍有前置条件的 evidence slice，再使用独立 output tag。
