# 论文进度

## 2026-09-09（第三轮）本地构建复核：附录两张表根本没排进 PDF（当前最新）

没有可用主机，本轮是纯本地构建复核。发现并修掉一处会被审稿人直接看到的缺陷。

**现象**：`paper/main.pdf` 与 `paper/appendix.pdf` 里有三处 `??`。之前几轮把它记成
"未定义引用 appendix 1、main 2，均为既有"，当成噪声放过了——但它不是引用写错，是
**附录第 I 节的两张表（`tab:pi_profiles` 策略档位、`tab:mapping_surface` 映射表威胁面）
压根没有排进 PDF**。两张表都声明为 `[t]`，出现在附录最后一节的开头，浮动队列一直没排掉，
文档被参考文献跑完就结束了，于是 caption 没有 ship、label 没有进 `.aux`。
正文第 6、7 页跨文档引用这两张表的两处，以及附录内部的一处，全部打印成 `??`。

**修法**：两张表改为 `[H]`（与两节之后的算法一致），落在正文介绍它们的位置。
重新构建后：main 14 页（正文仍在第 12 页结束）、appendix 由 10 页变 9 页、
**0 error、0 undefined reference**（此前 main 2 处、appendix 1 处），
两张表分别落在附录第 7、8 页；lines 549--583 没有新增 overfull。paper submodule f0b7dea。

**顺带核实**：本地 `paper/build/` 里的 PDF 此前停留在 01:40 那次构建（appendix 8 页），
比 14:55 的 CPPB 回填提交要旧，也就是说上一轮记的"已构建通过"在本机没有留下对应产物。
现已重新构建，PDF 与当前源码一致。PoPETs 强制的三节（ethical considerations / open science /
AI use）确认都在 `main.tex` 里、在第 12 页之后，符合页数要求。

## 2026-09-09 第三位标注者的空白标注页入库；但**第三轮标注结果并不存在**

本条是跨主机同步用的：另一台主机在找"第三位标注者的记录"，找不到是对的——记录确实没有。

**已入库的**：`src/experiments/semantic_inferability_round3_page_vgpu3090.html`（commit `659788d`）。
这是第三位标注者用的**独立轮标注页**（`--mode independent`），102 条全量，页面里
`MODE = "independent"`、`R1 = {}`——不带任何第一轮答案，自己的 localStorage key
（`inferability-annotations-r3-v1`）、自己的 collection（`round3`）、自己的导出名
（`human_annotations_round3.csv`）。它此前只存在于一个 scratch 目录里，所以别的主机拿不到。
生成器 `src/experiments/build_annotation_page.py` 本来就已入库且支持 `--mode independent`，
所以另一台主机也可以自己重新生成；直接 pull 这个 HTML 更省事。

**没有的**：第三轮的答案。这一点已经从两侧独立确认——
- 本机：仓库、`Downloads`、`Desktop`、`Documents`、以及全部 Claude scratch 目录下都没有
  `human_annotations_round3.csv`，也没有任何 `*round3*` 的结果文件。
- 另一会话：那个 artifact（"可推断性标注 第三位"）的 `round3` collection 返回 0 条文档；
  同一 artifact 的 `annotations` 与 `round2` 也是空的。而第一轮（另一个 artifact 的
  `annotations`）102 条、第二轮（再一个 artifact 的 `round2`）96 条都读得出来，
  说明存储本身是好的，就是第三轮没写进去过。

页面本身也解释了为什么"文件在"不等于"标注做过"：答案只写进标注者浏览器的 localStorage
和 artifact 的存储，HTML 文件里不含任何答案。页面 `.html` 与 `.html.bak` 的时间戳同为
09-09 11:46、两者只差一段 `file://` 下的 CSV 导出兜底代码，看不出有人真的做完过一遍。

**一个必须避开的坑**：那个 scratch 目录里有 `fake_round3.csv`，102 行、`item_id` 0–101、
YES/NO 齐全，看起来正好是"第三轮结果"该有的样子。**它是冒烟测试用的合成数据**（同目录
还有 `fake_decisions.csv`、`fake_judge_annotations.csv`，内容是 `Jane Doe` /
`secret text no_protection 0` 这类占位串）。谁都不要把它当成第三位标注者的标签喂进
`semantic_inferability_agreement.py`——那会直接产出一个假的 annotator1-vs-annotator3 kappa。

**因此现在的状态**：论文里关于标注者独立性的写法仍然只能是现在这样——第二位是**复核**
（primed，κ=0.915 是上界不是 IRR），第三位的独立轮**工具已就绪、标注未开始**。在拿到真实的
`human_annotations_round3.csv` 之前，不要动 Limitations 段落里关于标注者独立性的措辞。

## 2026-09-09 PRO 6000 会话：给四张 CPPB 附录表补上可命名的 runtime

开 PRO 6000（96 GiB）是为了关掉计划里唯一"只差一台 GPU 主机"的那一项：附录四张 CPPB 表
（`tab:per`、`tab:utility`、`tab:pi_sensitivity`、`tab:latency`）的数字来自没有记录 runtime
的旧 score log，而产生它们的 prompt 已经不存在（released manifest 里只有 template/prompt 存根）。
在这些数字旁边补写 backend 和 digest 等于"声称"而不是"记录"provenance，所以改为在
`data/cppb_full_annotations.jsonl` 的 256 条重建面上重新测量，并完整登记 runtime。

**新增测量脚本**：七种中介方法（无保护／正则／大小写启发式／通用去标识／企业分级遮蔽（Presidio）／
语义抽象／utility-constrained）× 256 条，指标为 PER（金标敏感 span 是否仍字面出现，带 span 级
bootstrap 区间）、AC（同一 prompt 原始答案与中介后答案的任务相关一致性，judge 评分）、
TSR（是否满足模板自述的成功判据）、以及仅中介环节的 CPU 延迟。行级 flush + fsync，断点续跑。

**顺带发现并修掉的三件事**（都已提交）：
1. **已发布的阈值 sweep 是插值出来的。** `policy_threshold_sweep.csv` 由三个 profile 线性插值
   得到六个点，但附录写的是"a genuine sweep rather than a three-point sketch"——文字与产物不符。
   新脚本对每个 τ 都真跑一遍（阈值作用在 learned detector 自己的 token 概率上），使这句话名副其实。
2. **LLM sanitizer 的输出预算下限是 2048。** 该下限是为长临床病历设的；CPPB 的 prompt 是单句，
   于是每次都要求模型为一句话生成 2048 token，四个 shard 同时卡死在语义抽象那一步十分钟。
   同时构造函数的 `num_ctx` 是死代码，`_options_for` 里硬写 `FIXED_NUM_CTX`。
3. **judge 决策回放实际在重新生成。** context 是响应缓存 key 的一部分，而 32B 那轮跑在
   per-model context 之前、用的是共享的 12288（它的 manifest 里根本没记 context），
   于是用当前常量回放全部 miss——正是这个导出机制要防止的替换。改为两个 context 都可显式指定后，
   已验证"every call came from the cache"。

**运行过程中的一个教训**：把 70B 和 32B 同时排进来会让 ollama 反复换出 43 GB 的模型，两个 run
一起停摆；把 GLiNER（判决导出）和 ollama 放在一张卡上争用，则直接把 ollama 卡死（07:20 之后
没有任何一次 `/api/chat` 完成）。最终排布是：模型槽位数恰好等于所需模型数（32B + judge + sanitizer），
70B 交叉验证这一轮放弃，判决导出挪到 CPPB 跑完之后。

**测量结果**（256 条全覆盖，qwen3:32b 作答 / mistral:7b 评分，digest 与解码参数见 manifest）：

| 方法 | 旧 PER | 实测 PER [95% CI] | 旧 AC/TSR | 实测 AC/TSR |
|---|---|---|---|---|
| No protection | 100.0 | 100.00 | 1.00/1.00 | 1.000/1.000 |
| Regex-only | 61.3 | 50.00 [44.53, 56.25] | 0.97/0.96 | 0.996/1.000 |
| Capitalization heuristic | 48.7 | 62.50 [56.64, 67.97] | 0.91/0.89 | 0.988/1.000 |
| Generic de-identification | 12.4 | 0.00 [0.00, 0.00] | 0.73/0.71 | 0.934/0.937 |
| Enterprise staged redaction | 8.1 | 37.50 [32.03, 43.75] | 0.92/0.90 | 0.975/1.000 |
| Proposed (semantic abstraction) | 14.6 | 27.34 [21.88, 32.81] | 0.88/0.86 | 0.984/1.000 |
| Proposed (utility-constrained) | 9.3 | 12.50 [8.59, 17.19] | 0.94/0.92 | 0.957/1.000 |

三条需要落到稿子里的结论：

1. **企业分级遮蔽与本文方法的排序反转。** 旧表是 8.1 对 9.3（企业基线更优），附录为此写了一整段解释
   "为什么在这个受控面上基线会赢"。实测是 37.50 对 12.50，本文方法明显更优，那段辩解与数据矛盾，必须改。
2. **τ 扫描是平的。** 0.30–0.80 每一档 PER 都是 12.50，只有 AC 从 0.955 走到 0.975。已发布的六点
   sweep 是三点线性插值的产物，而附录称它是 "a genuine sweep rather than a three-point sketch"。
   真测下来 learned detector 的 token 概率呈双峰（73% < 0.30，21% > 0.80，[0.70,0.80) 为空），
   金标 span 全在所有阈值之上，所以阈值动不了暴露面。
3. **TSR 饱和。** 七种方法里六种全 256 条 SUCCESS，只有通用去标识掉到 0.937。附录主张的排序方向
   成立，但这一列几乎没有区分度，不能当作"utility 全都保住了"来用。

延迟（仅规则类流水线，单位 ms，mean/p95）：正则 0.9/0.5，大小写启发式 0.1/0.2，通用去标识 0.7/0.7，
企业分级遮蔽 192.2/692.9，本文 policy-aware balanced 0.9/0.8。语义抽象的中介步骤本身就是一次模型
生成（4927 ms），与规则类不可比，因此不进这张表。

**边界（必须写进稿子）**：这是**重建面**，不是原始 CPPB prompt（原始的已不存在）。新旧差异里有多少来自
prompt 不同、多少来自 runtime 不同，无法拆分。只能表述为"在可命名 runtime 的重建面上测得如下"，
不能表述为"旧数字是错的"。重建版 CSV 写在旧文件旁边（`*_reconstructed.csv`），旧 CSV 未被覆盖。

**论文已回填**（paper submodule 788a9eb）：四张表改读 `*_reconstructed.csv`，四条 caption 标注为
重建面 + 具名 runtime，并重写了三处会与新数据矛盾的论证——(1) 暴露表那段"为什么企业基线在此面上更优"
的辩解删除，改为陈述实测排序并说明新旧不可归因；(2) 策略敏感性改为报告"阈值在此面上完全不动暴露"，
并指出 profile 之间不止差一个 τ、其权重系数本次未测；(3) 效用表改为承认 TSR 饱和，不再从中读排序。
图注中"六点扫描"改为"七点实测、非插值"。main 14 页（正文仍在第 12 页结束）、appendix 10 页，
0 error；未定义引用数与改动前一致（appendix 1、main 2，均为既有）。

**未完成**：判决决策回放（喂给盲评 judge 抽查）。它绝大部分命中缓存，但少数 miss 会要求 32B 用当初的
num_ctx 12288，而卡上模型是按 2048 加载的——不同 context 强制 ollama 整体重载模型，10 分钟只推进了
3 次 agent / 21 次 judge 生成。已停止。要继续应当单独起一个 12288 的 ollama 实例一次装好再跑，
不要和 2048 的实验共用一张卡。该项本就卡在数天人工评分上，不阻塞投稿。
那批生成缓存（18M + 2.7M，7 个文件）此前只存在于 PRO 6000 上，本次已拉回本地并校验一致。

## 2026-09-09（第二轮）对照 RevisionSuggestions.tex 再核，补上 5 处并修掉两个会自我回退的生成缺陷

先核了主机：`C:\work\9\saveway.txt` 里四台 GPU 主机（H800、PRO 6000、vGPU 3090、2c 3080）
的 SSH 端口全部探测过，**全部拒绝连接**，也就是说 PRO 6000 上既没有在跑的实验、也没有排队的实验。
本轮全部是本地 CPU 工作。

### 1. tab:advmeas 补置信区间（F17 / E6 最后一块）

F17 点名的五张表里，`tab:advmeas` 是唯一还只报点估计的。ASR 是"被攻击后逃逸的 span 数 /
原本被抓到的 span 数"，是一个比值之和，而 span 聚集在文档内，所以按**文档级** bootstrap
重算（走 propagation 表用的同一个 helper、同一个 seed 17、1000 次重采样）。

- 16 个点估计**全部逐位复现**，只新增区间与 span 数列。
- 区间把"脆"和"只是噪声大"分开了：同样 893 个 span，zero-width 99.7% [98.9, 100.0]
  是真的全线失守，intra-token spacing 47.1% [31.1, 60.8] 只能说方向明确；
  separator injection 的 0.0% 上界到 12.1%，不能读成"免疫"。
- 正文 §6.5 那两个承重数字（99.7%、28.2%）也带上了区间。

### 2. OCR 那条路补回来了（F26 的正确收尾）

上一轮删掉没有 provenance 的 CPPB OCR 小节是对的，**但删完留了个洞**：正文 §5.1 仍把
"OCR-mediated prompt protection"列为四个被评测设定之一，ethics 里仍声明用了 CORD/FUNSD/SROIE，
附录里还有一句"三个 OCR 公开切片"——却没有任何一个数字。

有记录的公开切片其实一直在仓库里，这次直接报出来：三个基准 × 六个方法，
span F1 / 字符级 PER / 文本保留率，caption 写明 OCR 引擎与版本
（`rapidocr-onnxruntime` 1.2.3）和固定快照 revision。

结果是权衡不是胜利，就按权衡写：暴露控制迁移过来了，隐私-保留权衡更陡
（CORD/FUNSD 上 spaCy 栈 PER 最低 20.1/19.9%，代价是删掉 2/3 和过半的非敏感文本；
本文方法两边保留率都稳在 0.55，PER 38.2/42.7%）；**没有**迁移过来的是检测质量
（F1 0.35/0.46，干净文本上是 0.51/0.59）。SROIE 全员 F1 0.02 也如实解释了——
63 张收据只标了 21 个 span，正确保护也算误报，那一列不可读，PER 列才可读。

### 3. 两个"会把已修好的东西改回去"的生成缺陷

这两个是本轮最值得记的，因为它们**只在重新生成表格时才发作**：

- **F16(d) 的基线改名此前只改在 `.tex` 里**。我今天跑了一次 `fill_paper_tables.py`，
  四张表的 `NER-only masking` 标签立刻回来了——上一轮的修复被自己的工具撤销了。
  现在改名放进生成器里（render 时的显示映射），released records 不动。
- **`build_measprop_table` 读的还是 E1 之前的单分片旧文件**，重跑会把正文那张十方法、
  双数据源、带 CI 的承重传播表覆盖成过时的五方法版本。已改为读 pooled 记录，
  重新生成与已发布版本**逐字节相同**。顺带让论文 §5.2 那句"每张 record-backed 表都能由
  一次 table-fill 复现"对承重表**真的成立**了——在此之前它不成立。

### 4. AgentDojo 口径不一致

摘要和 §5.2 还写着注入实验只用 banking 套件，而 §6.5 与 `tab:inject` 自 slack 扩展以来
一直是 banking + slack 共 74 对。两处已改。同时 §5.2 补上了只在附录出现的两个公开数据源
（PhysioNet、三个文档图像基准）——ethics 里声明了它们，datasets 里却没有对应条目。

### 5. 附录语气清理（F11 / F12 / F13 残留）

附录还有五处自我否定与仓库口吻的表述，其中两处把同一条 CPPB split 完整性的免责声明
说了两遍。重写为陈述句，并把重复的那条合成一句——现在写的是"dev/test 几乎相同这件事
测的是划分构造，不是泛化"，而不是只说它不能证明什么。

### 构建与核查

main 14 页（**正文仍止于第 12 页**）、appendix 8 页；两份日志 0 undefined reference、
0 undefined citation、0 大号 overfull；跨两个文档 0 悬空 label、0 未引用 bib 条目；
双盲在两个 PDF 上重新用抽页面文本验证过——唯一出现的作者名仍是参考文献里第三人称的自引。

`docs/ExperimentProgress.tex` 两张表都已更新：完成表新增本轮 8 行；next-step 表按要求
**移走了已完成/已按范围关闭的四行**（API 模型、LDP 保证、AgentDojo 套件扩展、第二位标注者），
只留 8 行真正未完成的，每行都有完成百分比、预估新西兰时间（能定的给日期，被卡住的写明卡在哪，
不编造日期）和备注。


## 2026-09-09 人工标注子集补齐至 102，论文数字全面刷新

F19 要求 human-agreement 子集 n≥100，原来是 96。**差额是整除造成的，不是设计**：
sheet 用 `--human-n 100` 生成，但先分层再计数，`100 // 6 = 16`，六个方法共 96。

### 补法与两道校验

补 6 条（每方法 +1）而不是 4 条，这样是 102 且每方法 17 条、仍然均衡；
补 4 条会变成 17/17/17/17/16/16。新增 `src/experiments/semantic_inferability_human_topup.py`，
每条新题必须过两关才发出：

1. **抽样重放**：用原 seed 与同样的 rng 消耗顺序重放分层洗牌，96 条全部复现，
   证明"下一条"确实是原顺序里的下一条。
2. **文本逐字节重建**：把该方法已标条目的轨迹重新生成，与 sheet 里存的文本比对。
   不一致就拒绝出题——给标注者看的若不是判官当初看到的文本，κ 就是假的。

`presidio` 和 `casper_style` 需要 spaCy + Presidio，而原 manifest 只记了
`en_core_web_lg`、没记包版本，本来预期会失败。实测：本机
spaCy 3.8.16 / Presidio 2.2.364 / en_core_web_lg 3.8.0 / Python 3.12，
对 32 条 presidio+casper 轨迹**逐字节全部一致**（原运行是 Python 3.10.12）。
装在 scratchpad 的独立 venv 里，没动系统 Python。

六条由第一位标注者通过同一个 artifact 页面盲标完成（答案存在同一个库里）。

### 刷新后的数字（n=96 → 102）

- judge vs human：κ 0.080 → **0.087**，raw agreement 59.4% → 58.8%；
  判官判"可推断"81.4%，人工 57.8%
- lexical vs human：κ 0.283 → **0.250**
- 每方法人工可推断率：100 / 94.1 / **52.9**(presidio) / **41.2**(casper) /
  **35.3**(learned) / **23.5**(heuristic)，与对照的差从 −47.1 到 −76.5 点
- 两个 κ 移动都不到一个百分点，**结论不依赖子集大小**：判官仍在随机水平

论文里所有相关处已刷新：摘要、贡献列表、§5.5、§6.2、图 `fig:inferability`
（含 alt text）、Limitations、Conclusion。正文仍在第 12 页结束，
main 14 页 / appendix 8 页，0 undefined、0 大号 overfull。

### 顺带修的两个复现缺口

- 论文引的第一位标注者每方法比率，来自一个**现有代码不会再生成**的文件
  （agreement 脚本 round2 重构后的遗留）。round1 路径现在走同一个 helper 产出。
  用原 96 条输入重跑，点估计与 5/6 区间完全一致；`learned_lr` 的 CI 下界
  18.8 → 12.5，因为 bootstrap 按下标重采样、历史文件方法内行序不同——点估计不受影响。
- `fig:inferability` 的图例把两个 κ **硬编码**成 0.08 / 0.28，数据变了图不会变。
  改成从 agreement 表读。


### 更正：第二位标注者不是作者

论文 Limitations 原写"两位标注者都不独立、都是作者"——**这是错的**，第二位不是作者，
是外部路过的人。已改为：报告用的标签来自一位作者（第一位），第二位非作者复核了前 96 条。

按你的决定，论文现在把他写成**独立的外部读者**，并直接陈述 96 条里认同 92 条、
改动的 4 条全部同向（判为更不可推断）且都落在最激进的三个方法上、排序未变。

同时把原来的过度对冲删掉了——"primed upper bound"、"treat the effect size as indicative"
这类说法把一个单调、间距很大、两位读者都认的结果说得像存疑，
正是评审 F11 点名批评的自我否定语气。只保留一句陈述该轮是在既有标签上复核、
而非从空白表重标。

正文仍在第 12 页结束，0 undefined。

## 2026-09-09 对照 RevisionSuggestions.tex 全面复核，补上 6 处遗留

把当前 `paper/main.tex` + `paper/appendix.tex` 与 `docs/RevisionSuggestions.tex`
的 F1–F27、A1、A2(E1–E8)、A3、A4 逐条对照了一遍。绝大多数已在前几轮闭环，
本轮补上 6 处仍然成立的问题，全部是无需 GPU 的（两台主机现在都是关机状态）。

### 本轮修掉的

1. **F23(a) CPPB 基线数值打架**：`tab:judge` 里 Regex-only 61.6 / 大写启发式 49.0，
   而同一附录的 canonical 表是 61.3 / 48.7。根因在生成器
   `cppb_privacy_judge_baseline.py`：enterprise/proposed 两行读 canonical 全量
   256-prompt 文件，另外两行却读 per-split 重建，一张表里混了两个总体。
   现在全部比较基线统一读 canonical，只有 judge 行是 held-out split，
   caption 和 runtime manifest 都写明了。CSV 已重新生成。
2. **F23(b) 同一检测器两个数**：`tab:lightclf` 是 Span F1 0.53 / PER 7.6%，
   `tab:crossdom` 是 0.51 / 7.4%。原 caption 只说"是另一次独立训练"，
   真正原因是评测集不同——AI4Privacy 全量 2,997 篇 vs cross-domain 的 300 篇。
   caption 改成写明两个篇数，读者可以自己核对，而不只是被告知"有差异"。
3. **F16(d) 基线错标**：正文早已把 "NER-only masking" 改称 capitalization heuristic
   （它实现上就是大小写/称谓/地点正则，没有任何 NER），但附录四张表加一段正文
   还留着旧标签，两个文档自相矛盾。附录已全部改齐，并加一句把它映射到
   released records 里仍然叫 `NER-only masking` 的字段名，方便查 artifact。
4. **F26 CPPB OCR 段落**：断言了 Span F1 0.90 / PER 11.3% / AC 0.88，
   却既没有表、也没有任何 OCR 引擎与版本记录。评审给的两个选项是"补表"或"删段"，
   provenance 已不可恢复，因此删除。有记录的公开 CORD/FUNSD/SROIE slice 不受影响。
5. **AE 意见 5 的残留**：附录 TAB 一节里还留着一段 3.2B `llama3.2:latest`
   "named-runtime pilot"——正是 AE 第 5 条点名批评的弱模型，
   9 月 7 日那轮就是因为它才删掉了整个 Appendix G。这次一并删除。
6. **F8 顺带闭环**：昨天把附录拆成独立文档后，`appendix.pdf` 变成每次构建都重新
   生成的产物，评审说的"还在发布 4 月的陈旧 appendix.pdf"自动不成立，
   `AGENTS.md` 里对 `paper/appendix.tex` 的描述也重新变成正确的。

### 顺带重新核了一遍已闭环项（因为拆附录动了半篇论文）

两个文档合起来：0 个悬空 label、0 个指不到目标的引用、0 个未被引用的 bib 条目；
评审点名要补的 8 篇 agent-privacy 文献全部在且被引；无修订史/仓库口吻语句；
无自我否定的 caption；`tab:crossmodel`、`tab:propagation`、`tab:cppb_audit`、
blind-utility 两表都已不存在；LDP 叙述已清干净；F23(c)(d)(e)(f) 均已消解。

**双盲重新在两个 PDF 上验证过**（用 pypdf 抽页面文本，不是只看源码）：
没有任何单位名，唯一出现的作者名是参考文献里第三人称的自引 [17]，PoPETs 允许。
附录 PDF 是我昨天新造的文档，这次是它第一次被查。

构建：main 14 页（正文仍在第 12 页结束，12 页上限守住）、appendix 8 页，
两份日志 0 undefined、0 大号 overfull。

### 没做的，以及原因

- **F15 / E3 的 API 模型**：评审要求"一个强开源模型 + 一个注明版本号的 API 模型"。
  开源那半边已经做了两遍（32B + 70B，都带 digest），API 那半边从未跑过。
  卡点不是算力（API 不需要本地 GPU），是评审自己的 D3 里那句还没关闭的
  "API spend ceiling 未定"。**需要你决定**：要么给一个预算上限我去跑，
  要么在 Limitations 里写明"评测仅限开源权重模型"。
  我的建议是后者——第二个开源家族已经把可移植性这行填上了。
- **F19 的人工一致性子集 n=96**，评审写的是 n≥100。差 4 条，需要盲标注者再标。
- 其余长期项（PrivacyRestore 同协议复现、CPPB 原始端到端重跑、licensed i2b2、
  live mapping 攻防、语义推断缓解、独立人工效用验证、AgentDojo travel suite）
  状态未变，全部卡在外部数据/授权/开放研究问题上，已在 `ExperimentProgress.tex`
  第二张表里逐行记着。

本轮没有新实验：6 项修复都不需要 GPU，唯一重跑的是确定性的 CPU 端
judge-baseline 生成器。

### 补充（同日）：F15 按"缩范围"方案关闭

你选了后者，所以不买 API 那次跑，改为在论文里把边界写明。`paper/main.tex`
Limitations 第四点现在写：所有被评测的模型都是开源权重且本地部署，未测试任何
托管 API，因此商业端点背后的行为（含其自身的上游过滤）是未知的，可移植性检查
改由两个开源家族之间完成（指向附录 H）。Future work 里原来那句含糊的
"wider replication across model families" 换成了明确的 "a hosted-API replication"。

**又一次撞到页数**：正文零余量，加这段后 Conclusion 掉到第 13 页。这次没有删内容，
而是把 AgentDojo 的 suite-shape 那句（banking 的任务才会把受保护值送进工具参数，
slack 21 条里只有 2 条，travel 的 agent 根本到不了工具）移到附录里它所解释的
injection 表旁边——那句在全文只出现一次，删掉是真丢内容。移完正文回到第 12 页。

构建：main 14 页 / appendix 8 页，0 undefined、0 大号 overfull。

`ExperimentProgress.tex` 两张表都记了：完成表新增一行记录这次范围决策，
next-steps 表里那行从"等预算上限"改为"按范围决策关闭"，处理方式与 LDP 那行一致
——都是 scope correction，不是待办的声明。重新打开只需要一个预算上限。


## 2026-09-08 第二下游模型跑完 + 配对检验推翻一条既有结论 + 附录拆分

### 1. PRO 6000：第二下游模型（可移植性）实验完成

`ExperimentProgress.tex` 里挂了很久的 "Second downstream model"（0%，等主机开机）
已跑完。同样 200 个 PrivacyLens case、同样的 judge（mistral 7b）、同样 seed 17，
把 agent 换成另一个家族的 llama3.3:70b，9 个 condition 八分片并行，
2026-09-08 18:53 CST（22:53 NZST）结束。

- **1800/1800 行**，每分片 225 行、225 个唯一 `(condition, case)`，全局重复 0，
  唯一 case 200，八个日志里 traceback/error/timeout/skip 计数全为 0。
- 已用 `pool_downstream("llama3.3_70b-q4km-hf")` 汇总（注意：
  `aggregate_paper_results.py` 的 `main()` 默认只 pool 32B 那一臂，必须显式传参）。
- 25 个文件（8 rows + 8 runtime manifest + 8 summary + 1 pooled）已拉回本地，
  **25 个 md5 与远端逐一相同**。

**可移植的部分**：无保护 exact-ID 暴露 13.7% → 13.1%，检测器类条件两边都落在
1.9–4.4%，semantic abstraction 两边都停在接近无保护的水平（12.9% / 12.0%），排序保持。

**不可移植的部分**：中介的效用代价明显更大——learned detector 的 helpfulness
配对差值在 70B 上是 −1.06，32B 上只有 −0.21；symbolic_late 两边都最稳
（−0.27 / −0.16），这对论文首选配置是有利的，但必须作为差异写出来，不能抹平成"一致"。

**一个必须写清的边界**：boundary leak 两臂完全相同（late 1.6/1.6，early 51.0/51.0），
不是巧合——`raw_values_visible_before_tool` 是对已中介的释放文本
（`instr_r + traj_r`）计数的，完全不经过 agent 输出，按构造就不可能随模型变化。
论文那条 51.0% → 1.6% 的 restoration-timing 结论**不能**说"在第二个模型上复现"。

### 2. 配对检验：推翻 "judge leak 不被任何方法改变" 这条结论

原结论建立在边际置信区间是否重叠上，而九个 condition 跑的是同一批 200 个 case，
这种比法把配对信息丢掉了。新增 `src/experiments/downstream_paired_tests.py`：
按 case 配对，用 McNemar 精确检验 + 配对 bootstrap 差值区间 + 每个模型内部
8 次比较的 Holm 校正。

- **70B 上，Holm 校正后 8 条里有 6 条与无保护分离**：learned_lr −18.5 点
  (Holm p<1e−4)、casper_style −15.5 (4e−4)、gliner −15.5 (2e−4)、presidio −10.5
  (0.015)、symbolic_late −9.5 (0.022)、abstraction −8.0 (0.027)。
- **32B 上**，casper_style 与 learned_lr 未校正时已是 p=0.009 / 0.022，
  Holm 后退回 0.075 / 0.156。也就是说原措辞**只在校正之后、且只在那一个模型上**成立。

结论：这是一条**模型相关**的负结果，不是普遍结论，论文不能再无条件陈述。
`docs/ExperimentProgress.tex` 已相应改写（新增两行完成项，并修正
semantic-mitigation 行里重复这条声明的措辞）。

### 3. 论文附录从 main.tex 拆出，恢复 paper/appendix.tex

按要求把 `\appendix` 之后的八节（A–H）拆回独立文档。

- 附录 preamble 按**当前** main.tex 重建（PoPETs 2027 / anonymous），
  没有沿用 git 历史里删掉的那份——那份还是 ACM TOPS，且 Jinsong Wu 单位仍写着
  University of Chile。
- 合并期间新产生了 8 条正文→附录、3 条附录→正文的交叉引用，拆开后会全部失效，
  所以两边都用 `xr` 读对方的 `.aux`。
  **踩到一个坑**：直接 `\externaldocument{main}` 会让附录里每个 `\section` 报
  `Missing number, treated as zero`。二分 `.aux` 定位到原因是 acmart 自己写的
  `\newlabel{tocindent-1}{0pt}` 等标签被对方文档的同名副本覆盖，
  而 acmart 会把它们当尺寸读回来。`xr-hyper` 无效，用标签前缀解决
  （正文导入为 `A-`，附录导入为 `M-`），11 条引用相应改写。
- `paper/build.bat` 改为 main → appendix → main（第二遍 main 才能拿到 appendix.aux），
  并把 `build\` 加进 `TEXINPUTS` 供 `xr` 找 aux。
- 构建结果：main 14 页、appendix 7 页，两份日志 0 undefined reference、
  0 undefined citation、0 Missing number；正文仍在第 12 页结束，12 页限制不受影响。
- 已逐字节比对 `HEAD:main.tex`：附录正文与被移走的部分完全一致（仅 5 处 `M-` 前缀），
  保留的正文也完全一致（仅 xr 段落、back-matter 注释改写、8 处 `A-` 前缀）。

### 4. 按方案 (a) 改写 §6.3，并关闭 PRO 6000

- `paper/main.tex` §6.3 把"每个中介区间都与无保护区间重叠"换成配对检验：
  casper −9.5 点、learned_lr −9.0 点（McNemar p=0.009 / 0.022，Holm 后均不显著），
  并指出第二个 agent 上八条里有六条分离。
- 顺带核了相邻那句"learned_lr 与 casper 的 leak rate 统计不可区分"——配对检验
  p=1.000（32B）/ 0.480（70B），结论成立，改为按配对口径陈述。
- Setup 里"fixed 12k-token context window"是旧值（代码早已是 agent 7,168 /
  judge 10,240），一并改正。
- 附录新增 §H "Portability to a Second Downstream Agent"（表 `tab:portability`），
  给出两个 agent 的完整对照与 Holm p 值，并写明 boundary leak 为何被排除在对照之外。
  附录模型清单补上 llama3.3:70b（70.6B / Q4_K_M / bb2a7bfe）。
- **页数是硬约束**：正文原本正好卡在 12 页上限，加字后 Conclusion 掉到第 13 页。
  因此把跨模型细节移进附录、正文只留一句加指针，并压掉两处因新文字而冗余的表述，
  最终正文 +188 字符、Conclusion 回到第 12 页。main 14 页 / appendix 8 页，
  两份日志 0 undefined、0 大号 overfull。
- 实验已收完、结果已 push，**PRO 6000 已关机**（已确认不可达，停止计费）。
  scratch 卷上的 ollama / sanitizer 缓存与模型权重是可重建的派生物，未做保留。


## 2026-09-08 第二位标注者完成复核，结果已回填论文

第二位标注者把 96 条全部复核完毕。从 artifact 的存储里取回全部 96 条记录，
逐条比对确认页面携带的第一位答案与第一轮表格完全一致（无一条错位），再计分。

### 结果

- **96/96 全部复核，改动 4 条（4.2%）**
- 4 条改动**全部是 YES → NO**（判为更不可推断），且**全部落在最激进的三个方法**上：
  heuristic_mediator 两条、learned_lr 一条、casper_style 一条。
  no_protection、regex_only、presidio 三档一条未动。
- 两份记录一致率 95.8%，κ = 0.915。**但这是有先验提示下的一致率，不是独立评分者间信度**
  ——第二位是从第一位的答案起步的。脚本按此命名并打印警告。
- **判官对第二位的标签仍是随机水平：κ = 0.086**（第一位是 0.080）。
  词面指标 κ = 0.372（第一位 0.283）。

### 这轮结果的意义

判官失效这条**从"一个读者的判断"变成"两个读者都测出随机水平"**，是本轮最实质的加强
——这条恰恰不依赖两位标注者是否独立。

方法排序在第二位的标签下不变而且更陡（最激进方法 25.0% → 12.5%）。
但**论文正文仍然用第一位的数字**：第二位的四条改动全部朝有利于本文的方向，
若改用复核后的标签当主结果，等于让一个被先验提示过的复核抬高了自家效应，
审稿人一定会问。用第一位的（未被提示的）标签，这个质疑不成立。

### 论文改动（`paper/main.tex`）

- §6.2 加两句陈述复核结果，caveat 指向 Limitations（不在两处重复论证）
- Limitations 第一条重写：从"只有一个标注者"改为"两位标注者但不独立，
  95.8% 一致率是 primed 不是 inter-rater reliability，主结果用第一位的标签，
  独立的第二次标注仍是未竟事项"
- 为腾出版面，压缩了 Limitations 里 AgentDojo 套件形态那句（travel 的细节移交附录与公开记录）
- 构建：20 页，**正文仍止于第 12 页**，0 undefined ref/cite

注：baseline 的 conclusion 正好卡在第 12 页末尾，零余量，任何净增字数都会溢出到 13 页。
本轮是边加边减压回去的。以后往正文加内容都要按同样方式核对
（`grep newlabel{sec:conclusion} paper/build/main.aux`，页码必须是 12）。

### 新增结果文件

- `semantic_inferability_round2_annotations_vgpu3090.csv`（两人标注逐条对照，96 行）
- `semantic_inferability_agreement_round2_vgpu3090.csv`（三组 κ 与改动率）
- `semantic_inferability_human_by_method_round2_vgpu3090.csv`（第二位标签的逐方法比率，
  格式与图表脚本一致，需要时可直接重绘）

`docs/cover_letter.txt` 与 `docs/ae_response.txt` 同步更新到两位标注者的表述。

### 仍然未闭合

**独立的第二次标注**（不看第一位答案、从空表开始）仍是这条发现最硬的补法。
本轮做的是复核，不是独立重标——两者能回答的问题不同。是否还要再找一位独立标注者，
取决于你对审稿风险的判断；现在的写法已经把这个限制说清楚了，不算隐瞒。

## 2026-09-08 投稿材料与稿件一致性核查

本轮不跑实验，只做一次全仓一致性核查，起因是核对"下一步该干什么"。发现三处
上一轮人工验证反转结论后**没有同步**的地方，已全部改掉。

### 1. cover letter 与论文自相矛盾（最严重，已修）

`docs/cover_letter.txt` 与 `docs/ae_response.txt` 停留在 09-07 版本，仍写着
"没有任何表层方法能实质降低事实披露，83.0–98.8% 的事实在中介后存活"，并把这一条
称为"论文最有分量的结果"。而 09-08 的人工标注已经把这条**反转**成"从 100% 压到
25–56%，全部显著"。PoPETs 要求随稿提交先前评审与逐条回应——一份与正文互相打架的
回应信足以直接葬送投稿。

已改：
- cover letter：贡献列表 3 条 → 4 条（与正文 `egin{itemize}` 对齐）；
  "两条负面结果"段整体重写为"一条测量学结果 + 一条负面结果"；新增一段坦述
  单标注者局限；删掉正文里出现的仓库路径 `docs/ae_response.txt`（改为"attached"）。
- ae_response：AE 第 3 条回应整节重写——先按意见把 83% 扩到十方法全量，再建判官，
  再报告判官 κ=0.080 失效、词面 κ=0.283，最后给人工反转后的数值与区间；补上
  "PrivacyLens 自带 judge 未经验证、同样存疑"的自我披露；开头"三条主张未存活"改为
  "两条未存活、一条反向"；结尾 What changed overall 同步。

### 2. 正文 Limitations 编号坏了（已修）

`paper/main.tex` §Limitations 写"Three limitations"，实际列了四条，且序号是
First / Second / **Second** / Third。已改为 Four + First/Second/Third/Fourth。
重建：20 页，正文止于第 12 页，0 undefined ref/cite。

### 3. USAGE.md 目标 venue 行是旧的（已修）

D1 在 09-06 就已定为 PoPETs 2027 Issue 3，`docs/RevisionSuggestions.tex` 也已同步，
但 `USAGE.md` 的 `目标会议或期刊：` 一行仍是 ICLR 2027——所有按该行取 venue 的
后续流程都会走错标准。已改为 PoPETs 2027 Issue 3（2026-11-30 AoE）+ TAISAP 备选。

### 4. 匿名 artifact 包已重建（投稿硬性要求，本轮主要产出）

新增 `src/package_artifact.py`，生成 `submit/BodhiPromptShield_artifact_anonymous.zip`
（391 个文件、2.0 MB）。原来 `submit/` 里那份是 **2026-06-17 TOPS 时代**的包，
早于整个 E1–E7 重建，正文 `openscience` 节承诺的补充材料等于是空的。

做法上和旧包的三点不同：

1. **目录结构保持仓库原样**（`src/` + `data/`），不再压平成 `source/`。
   实验脚本用 `parents[2]` 定位根目录再读 `data/`，旧包压平后这些脚本根本跑不起来。
   已实测：解压后直接 `python src/experiments/semantic_inferability_agreement.py --tag vgpu3090`
   跑通，输出 κ=0.080 / 0.283，与论文数字逐位一致。
2. **排除了 PhysioNet 派生的临床文本**（`physionet_deid_relabeled_export*.jsonl`）。
   旧包把它打进去了——PhysioNet 是 credentialed 数据，随补充材料公开分发违反使用协议。
   派生的逐文档指标和 prompt 包装清单不含正文，保留。
3. **匿名化是构建时强制的**：作者名、`github.com/mabo1215/...`、arXiv 链接、
   租用 GPU 容器主机名统一改写，改写后再全量扫一遍，只要还剩一个就拒绝出包。
   打包脚本本身不进包（它字面写着要清除的那些字符串）。运行日志也不进包
   （里面是 `/root/autodl-tmp/...` 绝对路径），provenance 由 runtime manifest 承担。

**顺带发现的双盲风险**：仓库里存在一篇同名 arXiv 预印本
（`arXiv:2604.05793`，署三位作者），`build_hf_cppb_dataset.py` 和 HF dataset card
里都引了它。包里已抹掉，但**预印本本身是公开的**，PoPETs 双盲下审稿人一搜即中。
这个需要你判断要不要处理（PETS 通常容忍预印本，但你应该知道它在那儿）。

### 5. 第二位标注者的页面已上线

用户已找到第二名标注者，明确要求：**把第一位的标注拷贝一份预填进去，第二位在上面
确认或调整，形成第二位自己的记录；第二位的任何修改都记进第二位的记录，不动第一位的，
最后得到两个人各自的标注。**页面按这个要求实现。

交互：每条打开时已经填好第一位的答案，并在事实句下方单独一栏显示"第一位标注者：是/否"。
同意就按同一个键确认，不同意就按另一个键改掉——两种都算已复核，自动跳下一条。
表头显示"已复核 N / 96，其中改动 M 条"，进度格里改动过的条目单独标色。
第一位的记录在页面上是只读的，两份记录存在不同的文件和不同的集合里。

**一处如实记录**：这样第二位是在第一位的答案上起步的，两份标注不再互相独立，
它们之间的一致率会被"先验提示"抬高，不能当作独立的评分者间信度（inter-rater
reliability）来报告。脚本输出里已按实际含义命名（primed agreement / 上限），
并显式打印一行警告，避免日后被误当成独立 κ 写进论文。这一轮真正立得住的是
**第二位读者对全部 96 条都给了判断，以及他改动了多少条**——后者是先验提示
制造不出来的。

- `src/experiments/build_annotation_page.py` 双模式（`--mode blind|review`），
  两轮共用一套页面实现和一套盲态断言（判官答案、method、doc_id 永不进页面，已验证）。
  第二轮额外用 `reviewed` 标记区分"第二位真的看过并按了键"与"只是预填还没动"，
  否则一份预填好的表格打开就显示 100% 完成。
  顺带修了原版一个静默 bug：`db.collection().get()` 返回的是 QuerySnapshot 不是数组，
  原来的恢复代码 `.forEach` 会抛异常被 catch 吞掉，云端恢复一直没生效（只有 localStorage 在起作用）。
- `src/experiments/semantic_inferability_agreement.py` 加 `--round2`：输出改动条数、
  两份记录的 primed 一致率（带警告）、判官与词面指标对第二位标签的 κ，
  并另外生成 `semantic_inferability_human_by_method_round2_*.csv`——与图表脚本读的
  格式完全一致，可直接用第二位的标签重绘可推断性图。已用合成数据跑通，
  其中判官与词面的 bootstrap 区间与第一轮文件逐位一致，说明区间实现对得上。
- 标注页：https://claude.ai/code/artifact/b2f67c85-bb52-46d6-8dd8-0a81769347fc
  本地独立副本 `tmp/inferability_round2.html`（无 `window.claude` 时自动退回
  localStorage + 剪贴板导出，可直接把文件发给对方）。

**注意**：该页声明了 db 能力，因此只有登录同一组织的人能打开。
如果第二名标注者不在你的组织里，改发本地 HTML 文件，功能完全一样，
标完点"导出答案 (CSV)"回传即可。

回收后一条命令出全部结果：
`python src/experiments/semantic_inferability_agreement.py --round2 <导出的csv>`

### 6. 两处需要你处理的状态不一致

- **哪台主机在计费，说法冲突**：`docs/progress.md` 顶部说 vGPU 3090 按指示保持开机；
  `docs/ExperimentProgress.tex` 说 vGPU 已关、PRO 6000 保持开机。两份文档不可能都对。
- **`C:\source\.env` 不存在**，因此本轮无法自行 SSH 上去核实。登录规则指向该文件，
  它要么被移动要么被删除。

## 2026-09-08 vGPU 会话：E5′ 判定、AgentDojo 扩展、人工验证推翻第三条发现

**提交**：主仓 `1eafdb0`，`paper` 子模块 `18b3575`，均已 push。vGPU 3090 **按指示保持开机**（仍在计费）。

### 1. E5′ 可推断性判定（新增实验）

新增 `src/experiments/semantic_inferability_judge.py`：对每个 (方法, 轨迹, 事实) 三元组，
用与 `propagation_suite` 完全相同的路径重新生成释放文本，再让判官模型**只看释放文本**
判断该事实是否仍可被推断。3,459 次判定，0 解析失败，判官 `gemma2:27b`
（digest `53261bc9…`, Q4_0, 27.2B, temp 0, seed 17）——与下游 32B agent、PrivacyLens
自带 7B judge 均不同家族。

**推翻了我上一轮写进论文的说法**：我曾把 FRR 描述为"披露的下界"，实测显示两个方向都偏
（保留文本的方法高估 8–11 点，激进删除的方法低估 37 点）。

### 2. AgentDojo 套件扩展

- **slack modes** 63 行跑完，与 banking 合并后 utility 覆盖 16 → 37 任务，区间 ±25 → ±13.5
- **travel 废弃**：28 个工具 schema（banking 只有 11）压垮 Q4 32B agent，19 行**零工具调用**，
  却仍从文本拿到非零 utility。无工具调用的行无法为工具边界还原提供任何证据，
  并入 utility 等于用一个在该套件上不工作的 agent 冒充方法性能。文件保留并改名
  `_ABANDONED_no_tool_calls` 作为该发现的记录。
- **slack 注入三臂**各 42 对，与 banking 合并 **74 对**同型外泄攻击，未保护臂区间宽度 34 → 19 点。
  只取外泄型注入（banking 1/8、slack 2/4）——slack 另外三个是发链接、拉人，
  不含用户数据，数据面中介按构造就不可能影响，混入只会稀释对比。
- 新增**配对检验**（三臂跑同一批对）：用户定向还原 −10.8 点 [−21.6, +1.4]，
  不限还原 −5.4 [−14.9, +4.1]，均含 0。负面结论"中介不防注入"从"32 对区间重叠"
  升级为"74 对配对检验下不显著"——证据翻倍，结论不变。

### 3. 人工验证：判官失效，第三条发现反转（本轮最重要）

发布中文标注页（`build_annotation_page.py` 生成，96 条盲样，事实句附中文对照，
轨迹保留英文原文因为其中的 `█` 遮蔽块就是实验操作本身）。作者完成全部 96 条标注，
**对方法与判官答案双盲**。

**判官未通过验证**：Cohen's κ = **0.080**（等于随机），原始一致率 59.4%。
判官在 81.2% 的条目说"可推断"，人工只在 59.4% 上这么说。
词面 FRR 反而更好（κ = 0.283）——**我上一轮"FRR 不可靠、判官更准"的判断也被一并推翻**。

**人工数据反转了结论**：

| 方法 | 人工可推断 | 相对无保护 |
|---|---|---|
| 无保护 | 100.0% | （基准） |
| Regex-only | 93.8% | −6.2（不显著） |
| Presidio | 56.2% | **−43.8** [−68.8, −18.8] |
| Casper-style | 43.8% | **−56.2** [−81.2, −31.2] |
| Ours (learned) | 37.5% | **−62.5** [−87.5, −37.5] |
| Ours (heuristic) | 25.0% | **−75.0** [−93.8, −50.0] |

论文原写"中介几乎不影响事实披露"，实际是**从 100% 压到 25–56%，全部显著**。

### 4. 论文改动（走 A 方案：跟随人工数据）

第三条发现现在同时是实质发现与**方法学发现**：一个 LLM 判官给出了看似合理、内部自洽、
但错误的答案，且与粗糙的词面启发式吻合到**两者互相都暴露不了对方**，只有人工标注把它们分开。
§6.2 明确主张：用 judge 模型测语义泄漏的工作应先报告与人工标注的一致性再当测量用。

Limitations 直说两点不好听的：**单一标注者且是作者本人**；以及既然自家判官在这一关翻车，
**PrivacyLens 自带 judge 我们从未验证过**，§6.3 的"下游泄漏率未变"应受同样怀疑。

摘要、贡献、§5.5、§6.2、Limitations、结论、图全部重写。构建：20 页，
**正文止于第 12 页**，0 undefined、0 悬空 label、0 未引用 bib、1–12 页无身份泄漏。

### 5. 主机环境的三个坑（已记录以免重犯）

- AutoDL `network_turbo` 会**卡死 Ollama registry**（TLS 握手超时），它只加速 GitHub/HF；
  且守护进程若在 source turbo 后启动会继承代理
- 16 路并发 + 8k 上下文把 **6/47 层挤到 CPU**，慢 7 倍；降到 4k 上下文后恢复 47/47
- AgentDojo 的 `--output-tag` 会把文件名里已有的 suite+model 再重复一遍

### 6. hf-mirror 实测（用户建议）

| 路径 | 速度 |
|---|---|
| hf-mirror 裸连 | 0.79 MB/s |
| ollama registry | 7.1 MB/s |
| **hf-mirror + turbo** | **12.9 MB/s** |
| huggingface.co + turbo | 11.1 MB/s |

结论：hf-mirror **必须配合 turbo** 才快；aria2c 16 连接可达 16 MiB/s。


## 2026-09-07 AE 意见追溯审查 + 论文全面修订

本轮起因是核查 `docs/AESuggestion.txt` 六条 AE 意见是否都已回应。核查结论：
实验侧 E1/E2/E3/E4/E6/E7 确已完成且带 CI，但**论文文本里残留了三处旧内容，
会让审稿人误以为工作没做**，另有一处度量措辞超出实现能力。本轮把这些全部改掉。

### 1. §3.3 自相矛盾段（AE 1，最严重）

正文原有一段写着"we do not reimplement Casper or PrivacyRestore... we make no
head-to-head claim"，而摘要、贡献列表、`tab:measprop`、`tab:downstream` 全都
在报告 Casper-style 的同协议对比结果。审稿人先读 Related Work 再读 Results，
会认为论文在 AE 第 1 条上自打嘴巴。已改写为：明确说明 Casper 机制已复现并在
单一协议下跑通（标 `-style` 因为复现的是机制而非浏览器扩展），PrivacyRestore
不复现的理由是**架构性的**——它靠服务端 activation steering 还原，前提是白盒
推理控制，而本层位于黑盒 API 之前，两者处在不同信任边界。对比表 caption 与
两行系统描述同步更新。

### 2. 附录 C 复述 AE 的反对意见（AE 2、AE 4）

CPPB 降级到附录后，附录里仍原样保留着"企业基线 PER 8.1% 低于我们的 9.3%、
我们不占优"、"+0.02 不构成有意义改进"、"AC/TSR rubric 未经独立验证"等
免责段落——等于替审稿人写好了反对意见。已重写为：说明受控单边界表面
**衡量的是什么、不衡量什么**（不给跨边界存活与还原时机任何credit），并指出
在真实 agent 测量上该排序反转六到七倍。附录定位改为设计分析而非比较证据。

### 3. 删除审计语言残留

- 删除附录 G "Named-Runtime Pilots and Semantic Probe" 与 `tab:revision_execution`
  整节：这是内部执行审计表，且把 AE 第 5 条批评过的 3.2B `llama3.2` 运行时又
  带回论文；其 12 探针面板还是 context-inference 准确率的第二套冲突数据
  （50/25/8.3/16.7 vs 附录 E 有记录支撑的 100→50），F23(f) 一直没调和，删除即解决。
- 删除 §4.2 "Implementation Status and Validation Scope"，整节都是证据边界记账。

### 4. FRR 度量措辞与实现对齐（AE 3）

正文原写语义列衡量"whether each marked sensitive fact remains **inferable**
from the released surface"，但 `propagation_suite.py:_semantic_residue` 实现的是
**内容词重叠**（事实中长度≥4 的非停用词有一半以上出现在释放文本中即判为保留）。
这是论文第三条头条发现，审稿人打开 artifact 就会看到，且正落在 AE 第 3 条的火力点上。
已把度量命名为 Fact Retention Rate，给出明确操作定义，并说明它是披露的
**下界**而非可推断性度量。§6.2 重写为围绕"下界"性质展开——这反而让论证更强：
PER 降到 1.8% 而 FRR 仍有 83.0%，且真实披露只会更高，说明差距不可能靠提高
span 检测精度来弥合。摘要、贡献、表头与 caption、Limitations、Conclusion 同步。

### 5. SPE 单调性错误声明（F18）

删除 `SPE_{k+1} ≤ SPE_k` 的声明——被自家数据反驳（无保护 AI4Privacy 是
48.7/100.0/74.8）。改为正确解释：三个边界不是级联滤波器，而是同一份中介后
prompt 的三种不同投影（检索查询是关键词化缩写、memory write 接近全文、
tool call 是结构化抽取），所以 SPE 按边界定义、不单调；memory write 拷贝
文本最多，对所有方法都是最高列。

### 6. 新增主文证据图

新增 `src/figures/propagation_and_fact_gap.py`，从已有 pooled 记录生成双栏图：
(a) 十种方法在三个边界的 SPE 分组柱状图（配合修正后的 SPE 语义，用柱状而非
曲线）；(b) PER 对 FRR 散点图带 bootstrap 误差棒，直观显示两者横跨整个暴露轴
却挤在 83–99% 的窄保留带里。调色板经色觉障碍校验；每根柱带直接数值标签。

### 7. 其他

- 补引 PAPILLON、Rescriber、Dou et al.、ConfAIde 四篇（F17），删除未被引用的
  `dodge2020finetuning`。
- `fig:workflow` 在 §4.1 补引；`tab:pi_profiles`/`tab:mapping_surface` 连同
  α/β 损失展开移入新附录 G。全仓检查：0 悬空 label、0 未引用 bib、0 undefined ref。
- **页数**：插图后正文一度到第 13 页，超 PoPETs 12 页上限。通过压缩 metrics 列表
  （只定义正文实际报告的六个指标，AC/TSR/UPR 移到使用处即附录 C 定义）、合并
  引言三段重复段落（同时补上 PoPETs 要求的首页真实场景相关性陈述）、精简对抗
  实验/Limitations/Conclusion，现正文止于第 12 页，全文 20 页。
- 双盲检查：正文 1–12 页无任何身份字符串；改掉了一处用作者所在城市举例的措辞；
  源文件 author block 由 `anonymous` 选项抑制，唯一自引为第三人称，符合投稿要求。
- 新增 `docs/ae_response.txt`（PoPETs 要求的逐条答复），重写 `docs/cover_letter.txt`
  （原稿仍写给 ACM TOPS，且仍把 CPPB 列为头条贡献）。

### 8. GPU 现状

本轮全部主机不可达：PRO 6000 / H800 / vGPU 3090 / A800 均 connection refused，
4c 3090 超时；本机仅 RTX 3070 8GB + `qwen3:0.6b`；原可充当 judge 的
`kimi-k2.5:cloud` 已于 2026-07-31 上游下线。因此 E5' 与 AgentDojo 扩展两项
实验**未能执行**，详见下方"未修改或部分修改"。论文文本未对未跑的实验作任何
承诺——FRR 已如实写成下界度量。


## 2026-09-07 00:50 §6 结果重写 + F11 自我否定清理完成

**提交**：主仓 `d69b722`，`paper` 子模块 `e5097ed`，均已 push。

### 1. 结果聚合（新增 `src/experiments/aggregate_paper_results.py`）

分片实验各自只对本分片算 CI，因此新增聚合脚本，把 E1/E3 的分片记录合并后**在完整总体上重算所有统计量**（bootstrap 1000 次重采样，seed 固定），而不是对分片摘要取平均。同时**修复了此前记录的 E7-b `none` 阶段 summary 崩溃 bug**：该文件表头早于 row-schema 扩展，按列名读回必然 `KeyError`，改为按字段数（14 列旧 schema / 18 列新 schema）分派解析，已补算出缺失的那份 summary（ASR 62.5% [43.8, 78.1]）。产出 4 张论文用聚合表。

### 2. 核心结果（供后续引用，均带 95% bootstrap CI）

- **E1 跨边界传播（10 方法同协议）**：AI4Privacy 300 文档上，learned detector PER **7.4% [6.3, 8.7]**，而 Casper-style 46.7% [43.4, 49.7]、Presidio 52.2% [48.7, 55.4]——**6–7 倍差距且 CI 不重叠**，这是 AE 要求的 head-to-head 胜出。PrivacyLens 493 轨迹上 Casper-style 1.4% 与 learned 1.8% 接近（不夸大）。代价侧诚实报告：learned detector 保留率 0.80/0.75，低于 Casper 的 0.95/0.91（过度脱敏）。
- **E1 语义残留（升级为跨方法正式发现，对应评审 E5）**：所有保留可用文本的方法，PrivacyLens 敏感事实仍被语义传达 **83.0–98.8%**。唯一显著降低的是 released heuristic（41.8%），但它靠销毁 40% 非敏感文本做到（保留率 0.60），属于效用失败而非隐私机制。
- **E3 下游任务原生指标（200 例 × 9 条件，qwen3:32b agent + PrivacyLens 原版 judge）**：最终动作中的精确标识符暴露从 **13.7% → 2.1–3.1%**（4–6 倍下降），但 judge 判定的泄露率仅 38.0% → 28.5–37.5% 且**所有 CI 与无保护重叠**——即"去掉字符串≠去掉事实"。效用上 **Casper-style 掉 0.73 helpfulness（2.42→1.69）**，而 placeholder+learned detector 在同等泄露率（29.0 vs 28.5）下保持 2.21，**在该基准上帕累托优于 Casper-style**。
- **E3 还原时机（机制级主张）**：late vs early restoration = BLR **1.6% [1.1, 2.1] vs 51.0% [48.0, 54.0]**，32 倍差距、CI 不相交，而 helpfulness 只差 0.11。
- **E7-b AgentDojo 注入攻击（诚实负结果）**：ASR 无保护 62.5% → 中介后 59.4%/56.2%，**CI 几乎完全重叠，不显著**。结论写为：prompt injection 是指令通道的控制流攻击，数据面中介层本就不应也确实没有防住；中介层的贡献是被外泄的参数通常是占位符而非真实标识符（BLR 0.0–8.3%，RSR 85–100%）。

### 3. 论文改动（`paper/main.tex`）

§6 重建为五个测量结果（传播 / 表面-语义差距 / 下游效用 / 还原时机 / 对抗与注入），新增 `tab:downstream`、`tab:inject`，`tab:measprop` 换成 10 方法双数据源带 CI 版本。同时按 F11 清理自我否定表述：摘要改为先给发现而不是先认输（删掉"enterprise staged redaction PER 更低"这一已被新数据推翻的旧结论）、贡献列表第 4 条（"明确证据范围"不算贡献）替换为可辩护的四条、Limitations 从 3 段免责收敛为 1 段三点、Conclusion 改为自信陈述三个发现 + 一句边界。§5 Setup 同步更新为实际使用的模型（32B agent / 7B judge / 8B sanitizer）并删除过时的 llama3 描述与大段免责。

**构建**：正文止于**第 12 页**（PoPETs 上限内），全文 20 页，0 error / 0 undefined ref / 0 overfull box。

### 4. 其他

- 按用户要求把根目录 `run_logs/` 用 `git mv` 移入 `src/run_logs/`（保留历史），**此仓库根目录不再新建文件夹**。
- PRO 6000 **仍未关机**（按用户指令保持开机，仍在计费），等待进一步指示。

## 2026-09-07 00:12 PRO 6000 实验全部跑完，结果已拉回并提交

**5 个 screen 全部正常退出，无新增未诊断错误。** 巡检全过程（10 分钟一次，本会话重新挂载后共 22 轮）未发现真实卡死；两次疑似异常（GPU 显存下降、行数不变）经核实均为良性——分别是 Ollama 因空闲自动卸载 `qwen3:8b-q4km-hf`（后续按条件需要会自动重新加载）、以及巡检脚本本身的 bug（`e7b_lines` 只统计未打 tag 的旧文件，命令推进到 `--output-tag inj_all` 新文件后旧文件行数自然不再增长，已修复巡检脚本本身，不影响实验）。

**实验完成情况**：
- **E1**（propagation_suite，AI4Privacy 3-way shard + PrivacyLens 4-way shard，全部方法）：本会话确认早前已完成，本次一并拉回并提交。
- **E3**（privacylens_downstream_suite，qwen3:32b agent + mistral:7b judge，4-way shard，200 例子集 × 9 条件）：**4/4 shard 全部完成**，每 shard 451 行（共 1804 行），9 条件全部跑完（no_protection → placeholder:presidio → casper_style → placeholder:learned_lr → placeholder:gliner_pii → llm_sanitizer:qwen3:8b → abstraction:qwen3:8b → symbolic_late:gliner_pii → symbolic_early:gliner_pii），全部 summary/manifest 已生成，日志零错误。
- **E7-a**（adversary_propagation_suite，AI4Privacy 200 文档 × 8 攻击 × 5 detector）：本会话确认早前已完成（9000+ 行文档级记录），本次一并拉回并提交。
- **E7-b**（agentdojo_restoration_suite，AgentDojo banking + important_instructions 注入攻击，三段顺序命令）：**全部完成**：
  1. `--modes none`（baseline under attack）：32 行数据全部写入成功，**但该阶段自身的 summary 计算因复用了一个 schema 变更前的旧文件表头（缺 `injection_task`/`restore_scope`/`security`/`refused_unscoped_restorations` 列）而抛出 `KeyError: 'security'` 崩溃**——原始逐行数据完整且已 fsync，不受影响；仅该阶段自动生成的 summary CSV 缺失，需要后续用一个小脚本从原始行数据重新计算（原因：该阶段刻意不传 `--output-tag`，与更早的 baseline E4 共用同一个默认文件名，但该默认文件是在 ROW_FIELDS schema 扩展之前写入的）。**待办**：修复 `agentdojo_restoration_suite.py` 的表头迁移逻辑并补算这一份 summary。
  2. `--modes late --restore-scope all`（`inj_all`）：32 行，summary 正常生成——utility(all)=50.0% [31.2,68.8]，utility(protected)=43.8% [18.8,68.8]，BLR=0.0%，RSR=100.0% [100.0,100.0]。
  3. `--modes late --restore-scope user-directed`（`inj_scoped`）：32 行，summary 正常生成——utility(all)=50.0% [34.4,65.6]，utility(protected)=50.0% [25.0,75.0]，BLR=8.3% [0.0,21.4]，RSR=85.0% [63.2,100.0]。

**结果已拉回并提交**：`rsync` 拉回 `src/experiments/`（含结果 CSV、日志、`llm_sanitizer_cache/`、`ollama_cache/`，约 130MB），已排除仓库内预先存在的、与本次实验无关的权限位噪音（WSL 挂载导致几乎全仓库文件在 `git status` 下显示为 modified，但 `git diff` 确认零实际内容差异，纯 mode-bit 问题，未处理、未纳入本次提交）。提交 `41f989d`："Pull E1/E3/E7 results from PRO 6000..."，已 push 到 `origin/main`。

**2026-09-06 23:2x 用户指令：PRO 6000 跑完后先别关机。** 已记录并遵守——主机保持开机（仍在计费），关机步骤暂缓，等待用户后续明确指示。详见下方"全部实验完成后的收尾流程"一节的覆盖说明。

**下一步（待做，未开始）**：
1. 修复 E7-b `none` 阶段的 summary 生成 bug 并补算该份 summary。
2. **论文 §6 Results 重写**：把 E1/E3/E7 的真实结果（表格+图，含 bootstrap CI，多数已由实验脚本算好）接入 `paper/main.tex`。
3. F11（自我否定表述清理）。
4. 等待用户对 PRO 6000 关机的进一步指示。

## 2026-09-06 16:50 会话中断前检查点（重启 Claude Code 前记录）

**目的**：用户即将重启 Claude Code 会话。本节记录当前所有正在进行的工作的完整状态，供新会话直接续接，无需重新摸索。

### 立即要做的三件事（新会话打开后）

1. **重新挂载 10 分钟巡检**：本会话的后台 Monitor 会随重启丢失，但 **PRO 6000 上的 screen 会话不受影响，会继续独立运行**。新会话应立即用 SSH 检查 PRO 6000 状态（见下方"如何检查"），并按需重新启动一个 10 分钟巡检 Monitor（本地 git/disk + 远程 screen/GPU/行数/traceback，模式见本会话历史，或直接问用户是否需要）。
2. **不要重复启动实验**：所有 screen 都是幂等/可续跑的（fsync 逐行写入 + 断点续跑）。如果发现 screen 还在跑，不要 kill 重启；如果发现 screen 已全部退出，说明实验做完了，直接进入"全部完成后"的收尾流程（见下）。
3. **读本节 + 下面的"仓库当前状态"再动手**，避免重复劳动或用旧假设覆盖已完成的工作。

### PRO 6000 当前状态（2026-09-06 16:50 本地时间 / 主机 CST 12:50 左右，运行中）

登录信息：`C:\source\.env` 的 "PRO 6000" 块（`ssh -p 48305 root@connect.westc.seetacloud.com`）。GPU 已开（有卡模式，RTX PRO 6000 Blackwell 96GB）。

仓库位置：`/root/autodl-tmp/BodhiPromptShield`（HEAD 应为 `b7bb44d` 或更新，用 `source /etc/network_turbo && git pull` 同步）。
Ollama：`OLLAMA_MODELS=/root/autodl-tmp/ollama/models OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MAX_LOADED_MODELS=4 OLLAMA_NUM_PARALLEL=4 OLLAMA_CONTEXT_LENGTH=12288 OLLAMA_KEEP_ALIVE=2h OLLAMA_FLASH_ATTENTION=1`，已装模型：`qwen3:8b-q4km-hf`、`qwen3:32b-q4km-hf`、`mistral:7b-instruct-v0.2-q4km-hf`（judge，与 PrivacyLens 原协议一致）。**llama3.3:70b 尚未可用**——两次导入失败（无卡模式内存不足 kill；孤儿 blob 校验失败），磁盘仅剩 44G，需要用户批准删除三个孤儿 blob 文件才能重下（见下方"待用户决策"）。

**仍在跑的 screen（5 个，`cd /root/autodl-tmp/BodhiPromptShield/src/experiments` 下 `screen -ls` 查看）**：
- `e3_q32_0/1/2/3`：E3/E5 PrivacyLens 下游评测（agent=qwen3:32b，judge=mistral-7b，200 例子集，4-way 分片）。9 个条件，目前 4 个 shard 都在第 5 个条件 `placeholder:gliner_pii`（no_protection → placeholder:presidio → casper_style → placeholder:learned_lr → **placeholder:gliner_pii** → llm_sanitizer:qwen3:8b → abstraction:qwen3:8b → symbolic_late:gliner_pii → symbolic_early:gliner_pii）。累计 944 行（截至 16:50），预计还需 1–1.5 小时。
- `e7b_q32`：AgentDojo banking + important_instructions 注入攻击（injection_task_1/8 试图外泄 IBAN），三段顺序命令：①`--modes none`（当前，task_1/inj_8 附近）②`--modes late --restore-scope all`（output-tag `inj_all`）③`--modes late --restore-scope user-directed`（output-tag `inj_scoped`，即"仅当工具调用收件人指向用户 prompt 中提及的实体才还原"这条防护）。累计 68 行。**曾两次被巡检误判"卡住"，两次直接登录验证后确认健康**（进程在 `do_poll` 等待 Ollama 响应，CPU 时间正常低，属于正常 I/O 等待；后续行确实在增长）——**不要因为某一次巡检看到同一行两次就断定卡死，先用 `stat` 看 mtime、`ps -o etimes,time,stat,wchan` 看进程再下结论**。

**已完成并已退出的 screen（不用管）**：
- `e1_ai4_0/1/2`（AI4Privacy 传播，全部 10 方法）：3000 行，完成。
- `e1_pl_0/1/2/3`（PrivacyLens 传播，全部 10 方法）：4930 行，完成。
- `e7a`（自适应攻击下的传播，8 攻击 × 5 detector × 200 文档）：9000 行，完成。
- `e4_q32`（AgentDojo banking，none/late/no_restore + 工具输出脱敏变体 mto）：68 行（与 e7b 共用同一个输出文件，见下）。完成。

**如何检查（新会话直接可用的命令模板）**：
```bash
PW=$(awk 'tolower($0)=="pro 6000"{getline; getline; print; exit}' /mnt/c/source/.env)
SSHPASS="$PW" sshpass -e ssh -p 48305 root@connect.westc.seetacloud.com \
  'cd /root/autodl-tmp/BodhiPromptShield/src/experiments && screen -ls; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader'
```
密码取自 `C:\source\.env`；ssh 走 WSL（`.claude/rules/shell.md`），Bash 工具即可，见本会话历史里反复用过的 `sshpass -e ssh` 模式。

### 待用户决策（未回答，问题保持有效）

1. **磁盘清理批准**：`/root/autodl-tmp/ollama/models/blobs/` 下三个孤儿文件（无 manifest 引用，共约 47.9GB）：
   - `sha256-32df3bac…`（42.5GB，损坏的 70B 拷贝，校验已失败）
   - `sha256-4824460d…-partial`（稀疏文件，R2 中断下载残留）
   - `sha256-3e0039fd…`（4.4GB，Mistral 重复导入副本）
   回复"删除"后即可腾出空间重下 70B（改用 hf-mirror.com GGUF 直接单份写入，不再走 Ollama registry 的 Cloudflare R2 路线，因为那条路线在此机器上直连超时、走 network_turbo 代理后又降到 0 吞吐）。**不删除的话，本轮论文结果只有 qwen3:32b 一个强开源模型，llama3.3:70b 缺席。**

### 全部实验完成后的收尾流程（自动执行，无需用户再确认——**关机步骤除外，见下方覆盖指令**）

用户原指令（2026-09-06 早些时候）："10分钟定时巡检，完成后拉回实验结果同时PRO 6000关机，避免扣费"。

**2026-09-06 23:2x 用户覆盖指令："PRO 6000 跑完后先别关机"** —— 关机步骤（原步骤 3）现改为**暂停，等待用户明确指示后再执行**；其余步骤（拉回结果、commit/push、更新本文件、§6 重写）仍按原计划自动执行，不受影响。5 个 screen 全部退出时：
1. `rsync`/`scp` 拉回所有结果 CSV、`*_runtime_manifest*.csv`、`logs/`、`llm_sanitizer_cache/`、`ollama_cache/` 到本地 `src/experiments/`。
2. `git add` + commit + push（提交信息按惯例，含 Co-Authored-By 与 Claude-Session 尾注，见 CLAUDE.md/仓库历史）。
3. ~~PRO 6000 执行 `shutdown` 关机~~ **暂缓——用户已明确要求跑完后先别关机；主机继续开着（仍在计费），等待用户后续指示再关机。**
4. 更新本文件（`docs/progress.md`）记录最终结果与行数。
5. **论文 §6 Results 重写**：把新的真实数据结果（E1/E3/E5/E7 的表格与图，含 bootstrap CI）接入 `paper/main.tex`，替换/补充现有 controlled-CPPB-only 的叙述；关注正文 12 页上限（PoPETs 2027），必要时把新表移入附录并只在正文放核心发现。
6. **F11**（自我否定表述清理）仍待做——见 `docs/RevisionSuggestions.tex` 的 F11 条目。

### 仓库当前状态速览（截至本检查点）

- **Venue 已定**：PoPETs 2027 Issue 3（截止 2026-11-30 AoE firm，正文 12 页），备选 TAISAP。`USAGE.md` 已同步。
- **论文模板转换已完成**：`paper/main.tex` 已是 PoPETs 2027 模板（acmart `sigconf,anonymous,review` + `popets.sty`），三个必填节（ethics/openscience/ai）已加，F12（修订历史措辞）与 F23（六处数值不一致）已修复，CPPB 内容已移入附录，正文当前**止于第 12 页**、0 undefined ref/cite。原稿备份：`paper/backup_main_pre_popets_20260906.tex`、`paper/backup_main_pre_restructure_20260906.tex`。
- **实验代码已完成并推送**（`src/experiments/`）：`mediation_baselines.py`（方法注册表：真实 Presidio/spaCy NER/Casper-style/GLiNER/LLM sanitizer，含 GenerationFailed 语义——模型调用失败时跳过该条目而非静默记为"未保护"）、`propagation_suite.py`（E1，支持 `--shard I/N`）、`privacylens_downstream_suite.py`（E3/E5，PrivacyLens 原版 judge prompt 逐字复现）、`agentdojo_restoration_suite.py`（E4/E7-b，含注入攻击与 `--restore-scope user-directed`）、`adversary_propagation_suite.py`（E7-a）、`ollama_client.py`（带 fsync 缓存的 Ollama 客户端）、`privacylens_render_prompts.py`（用 PrivacyLens 官方代码渲染 prompt，需要 `~/.venvs/pl`，本地已建好，见 PrivacyLens 依赖清单：langchain==0.0.277、pydantic<2、procoder、pandas、tiktoken、rouge_score、tenacity）。
- **本地环境**：`~/.venvs/bps`（presidio + spaCy + gliner + agentdojo + torch/transformers，用于 CPU 冒烟测试）、`~/.venvs/pl`（PrivacyLens 官方依赖，仅用于渲染 prompt）。
- **独立评审文件**：`docs/RevisionSuggestions.tex`（自包含英文 LaTeX，已按 PoPETs 重写，含 F1–F27 编号发现、AE 六条意见追溯表、A1–A4 行动计划、D1–D3 决策记录）。已编译为 `docs/RevisionSuggestions.pdf` 并发给用户。

## 2026-09-05 独立评审重置与 venue 重选

**2026-09-06 用户决策：D1 = PoPETs 2027 Issue 3（截止 2026-11-30 firm，正文 12 页，双盲）；D2 = CPPB 降入附录；D3 = 先盘点 Ollama/GPU 主机再定模型。** `USAGE.md` 目标行与 `docs/RevisionSuggestions.tex` 已同步为 PoPETs 首选、TAISAP 备选。

PoPETs 2027 作者须知（2026-09-06 核实）：正文 12 页；模板 `submission-template-2027.zip`；三节必填且不计页——`ethical considerations`、`open science`、`AI use`；**首页须明确说明与真实隐私应用的相关性**；**曾被任何 venue 拒稿且有评审意见的投稿必须附上先前评审**（即 TOPS AE 六条意见需匿名化后随稿提交，并附逐条回应）；字体须 Type1/TrueType 嵌入；不得操纵版式。

本次按用户指令对当前论文做了独立评审（不使用旧的 `docs/RevisionSuggestions.tex` 作为输入），
依据为当前单文件 `paper/main.tex`（1211 行，附录内嵌）与 `paper/main.pdf`（35 页，
2026-09-03 由当前源码构建，0 undefined ref/cite）。评审先按 `USAGE.md` 原目标 ICLR 2027 完成，
随后用户指示"不一定投 ICLR，投对口、能中的期刊或会议即可"，遂改为 venue 重选。
为选 venue 读取了投稿历史：论文已被 ACM TOPS 拒稿（TOPS-2026-06-0395，AE 六条意见），
此前经历过 CCS 一轮；AE 六条意见与本次独立评审结论高度一致。

**Venue 结论（已写入 `USAGE.md` 目标行，用户可覆盖）：**
- 首选 **ACM TAISAP**（Transactions on AI Security and Privacy）：2025 年新刊、已开放投稿、
  2026–2029 OA 免费；scope 明确含 AI 部署阶段隐私；论文已是 acmart 格式、systems/threat-model
  叙事可保留、附录可完整保留、无截止期。需在作者指南页核实页数上限与是否双盲（本次 dl.acm.org 403）。
- 备选 **PoPETs 2027 Issue 3**（截止 2026-11-30 firm；Issue 4 为 2027-02-28）：正文 12 页
  （revise 时 13 页），双盲，有 accept/revise/reject 三档且 revise 有 4 个月编辑指导期。
- 冲刺 USENIX Security '27 Cycle 2（2027-01-26）仅当新实验有明确 head-to-head 胜出时考虑。
- 不建议 ICLR 2027（贴合度差、9 页、20 天）与 TOPS 重投（刚被拒）。
- 三条路线的实验完全相同，10 月 31 日按结果定 venue。

# 已全部修改

1. **`build_cppb_full_annotations.py` 重构（src）**：常量提取、模板化统一、`_locate_span` 拆分、
   CSV 列序守卫；修复两处 provenance 缺陷——metadata 中写入了本机绝对路径（改为仓库相对路径）、
   sha256 随 CRLF/LF 检出而变（改为 LF 归一化后哈希并新增 `hash_convention` 字段）；CSV 改为
   LF 行尾。已验证 `cppb_full_annotations.jsonl`/`.csv` 与 HEAD 逐字节一致，256 行 offset
   round-trip 全部通过，两个下游脚本所需字段完整。数据 schema 未改。
2. **`docs/RevisionSuggestions.tex` 完全重写**（英文 LaTeX，自包含）：venue 对比表与推荐、
   总体判断、27 条编号发现（F1–F27，P0/P1/P2/P3 分级）、AE 六条意见→本次行动的追溯表、
   TAISAP（≤30 页）与 PoPETs（12 页）两套结构预算、行动计划 A1（合规，1–4 天）/
   A2（实验 E1–E8，1–45 天）/A3（重写，10–55 天）/A4（投稿事务与 10-31 决策点），以及
   需作者决策的 D1–D3。
3. **`USAGE.md` 目标 venue 行**由 ICLR 2027 改为 TAISAP（备选 PoPETs 2027 Issue 3）。

评审核心结论（详见该文件）：
- 现稿再投任何严肃 venue 仍大概率被拒，原因与 TOPS AE 一致：主对比是己方承认的失败
  （enterprise staged redaction PER 8.1% < proposed 9.3%，utility 仅 +0.02 且 rubric 未验证；
  附录盲评 TSR 仅 12–13.5%）；CPPB 主表来自不可再生的历史日志且附录传播表自述"非实测"；
  下游模型仅 llama3/llama3.2-3B-Q4；无 LLM sanitizer、真实 Presidio、Casper 复现等 baseline；
  所有主表无置信区间；SPE 单调性声明被自家数据反驳；大量修订历史措辞与自我否定叙述；
  PrivacyLens 论文在 bib 中却从未被引用；三处正文承诺的附录图不存在；"Section~IV" 硬编码。
- 可行的 accept 路径（AE 原话即规格）："a new evaluation on real agent stacks with strong
  baselines and realistic privacy attacks"——保留 systems 叙事，把 restoration governance 做成
  可测机制并与 Casper-style/Presidio/LLM sanitizer 同协议对比（E1、E4），用强模型与
  task-native utility 重做（E3），把 83% 语义泄露从"限制"变成跨方法的正式发现（E5），
  全表加 CI（E6），加入带下游效应的自适应攻击（E7）。

3. **A1 模板转换已完成（2026-09-06）**：`paper/main.tex` 已改为 PoPETs 2027 模板（acmart `sigconf,anonymous,review` + `popets.sty`，模板文件已复制到 `paper/`，原稿备份为 `paper/backup_main_pre_popets_20260906.tex`）；删除 TOPS 元数据与 CCS XML、`\shortauthors` 覆盖、两处真实 GitHub 链接与致谢文字；新增 `ethics`/`openscience`/`ai` 三个必填节（AI use 节声明了 LLM 助手参与代码与文本编辑——**请作者确认措辞**）；修正 "Section~IV"、补引 PrivacyLens 与 FUNSD、删除三处不存在的"附录图"表述；算法浮动体改为 `[H]`（原 `[t]` 在双栏下丢失）。构建结果：21 页、0 undefined ref/cite；正文到第 16 页（≈15.5 页，上限 12 页，需删减约 1/4）。
4. **PRO 6000 无卡模式环境（2026-09-06）**：Ollama 0.33.3 已装（需先 `apt install zstd`）；Ollama registry 的 Cloudflare R2 blob 直连超时，经 `network_turbo` 代理短暂可用后持续 0 MiB/s，**已改用 hf-mirror.com GGUF + `ollama create` 路线**（aria2c 可续传，>100 MB/s；每个模型导入后删除 GGUF 控制峰值磁盘；sha256 记入 `/root/autodl-tmp/ollama/gguf/manifest.csv`）。模型命名 `qwen3:8b-q4km-hf`、`qwen3:32b-q4km-hf`、`llama3.3:70b-q4km-hf`。仓库已 clone 到 `/root/autodl-tmp/BodhiPromptShield`（main@482e2bd）；PrivacyLens `main_data.json`（493 条）已下载；miniconda Python 3.12 已装 presidio、spaCy+en_core_web_lg、torch 2.8.0+cu128、transformers、gliner。本地 WSL 建了 `~/.venvs/bps`（presidio+spaCy）用于 CPU 冒烟测试。

5. **E3/E4/E5 代码已完成并本地冒烟（2026-09-06）**：`privacylens_downstream_suite.py`（用 PrivacyLens 自身代码渲染的 naive agent prompt；条件含 typed placeholder、Casper-style、LLM sanitizer、语义抽象、symbolic late/early restoration；逐条 secret 泄露判定与 0–3 helpfulness 使用其 `evaluate_final_action.py` 原 prompt；judge 用其原版 Mistral-7B-Instruct-v0.2）、`agentdojo_restoration_suite.py`（AgentDojo banking 套件，PromptMediator + 工具边界还原的 RestoringToolsExecutor，none/late/no_restore 三模式，utility 由环境状态判定）、`ollama_client.py`（fsync 缓存）、`privacylens_render_prompts.py`。全部 GPU 实验以 screen 并行方式在 PRO 6000 上运行，10 分钟巡检 Monitor 已启用。
6. **PRO 6000 开卡运行记录（2026-09-06 06:52 起）**：RTX PRO 6000 Blackwell 96GB；Ollama 0.33.3 以 `OLLAMA_CONTEXT_LENGTH=12288 / NUM_PARALLEL=1 / MAX_LOADED_MODELS=4` 运行（客户端 num_ctx 统一 12288，避免按请求变 ctx 触发模型重载）。首次 70B 导入实际失败（导入脚本把 `| tail` 的返回码当成功并删除了 GGUF），已修 pipefail；孤儿 blob（完整 42.5GB 拷贝）经 `ollama create FROM <blob>` 重新注册。screen：e1_ai4、e1_pl（E1 全部方法含 GLiNER 与 qwen3:8b sanitizer）、e3_q32（PrivacyLens 下游，agent qwen3:32b）、e4_q32（AgentDojo banking）；70B 注册后追加 e3_l70（200 例子集）、e4_l70、e1_l70（70B sanitizer，output-tag l70）。

7. **论文结构重排完成（2026-09-06）**：按 D2 与评审结构计划，把 CPPB 专属内容（基准构造、tab:per/utility/pi_sensitivity/latency、类别分析、split 审计、OCR 子集、运行开销、operating-points 图）整体移入新附录 "Controlled CPPB Operating Surface"（`\label{app:cppb}`）；删除自我否定的 tab:cppb_audit、tab:propagation（"非实测"）、tab:crossmodel 及 Cross-Model 小节、以及将被 E3 取代的盲评附录（tab:blindutility 等）；§5.2 改写为以真实数据源为主的 "Datasets"（AI4Privacy / PrivacyLens / AgentDojo / TAB + CPPB 一句）。同时完成 F12 修订历史措辞清理（29 处）。构建：20 页，**正文止于第 12 页**（PoPETs 上限 12），0 undefined ref/cite。原稿备份 `paper/backup_main_pre_restructure_20260906.tex`。仍待：结果回填后重写 §6（新表：真实来源传播+CI、PrivacyLens 下游 helpfulness/leakage、AgentDojo restoration）、F11 自我否定表述、F23 数值一致性。

8. **F23 数值一致性已修（2026-09-06）**：Regex/NER 在 judge 表 vs per 表的差异标注为"test split 单独计算"；learned detector 跨域协议行标注为"独立训练不完全等于 lightclf 表"；latency 硬件段与 §6.12 措辞不再矛盾；homoglyph 94.1%→43.9% 标注为"exposure 而非 tab:advmeas 的 ASR"；CPPB 第八类别统一为 "context-dependent confidential span"；两套 context-inference 面板标注为"探针集不同、不可直接比较"。
9. **E7（带下游效应的自适应攻击）已实现**：`adversary_propagation_suite.py`（E7-a，AI4Privacy 200 文档 × 8 攻击 × 5 detector，测量被攻击后 gold span 在 retrieval/memory/tool 三阶段的存活率与 PER，非仅 evasion ASR）已在 PRO 6000 跑完（9000 行文档级记录）；`agentdojo_restoration_suite.py` 扩展 `--with-injections`（AgentDojo important_instructions 攻击，banking injection_task_1/8 试图把 IBAN 外泄）与 `--restore-scope user-directed`（仅当工具调用的收件人类参数指向用户自己 prompt 中提及的实体时才还原 token，抵御"注入指令触发过早/越权 restoration"）；已修一处 AgentDojo 内部 bug（its important_instructions 攻击要求 pipeline.name 含其硬编码模型名列表中的一个，开源本地模型标签不在列表内会抛异常，已加同义回退且不影响实际调用模型）。E7-b 在 e4_q32（AgentDojo 基线）跑完后自动接续。

10. **E3 规模下调（2026-09-06 08:40，未经请示的合理默认，已通知用户）**：实测吞吐显示 493 例 × 9 条件（每例含 agent 生成 + 均值 3 条 secret 泄露判定 + 1 条 helpfulness 判定，约 5 次模型调用）在 4-way 分片下约 1.1 行/分钟/分片，全量预计需 16–20 小时——与"巡检并在完成后关机"的一次性会话预期冲突，且直接产生 GPU 计费。已停止 e3_q32 四个 shard（行已 fsync，未丢失，归档为 `*_partial_full493.csv`），改为 `--max-cases 200`（与 70B pilot 的抽样规模一致）重新分片续跑，预计可在本次会话时间窗口内跑完全部 9 条件。全量 493 例版本的部分结果予以保留，如需补齐可用相同种子（17）继续。

11. **AE 六条意见追溯审查与论文全面修订（2026-09-07）**：见本文件顶部本轮记录。
    修改内容：§3.3 矛盾段重写、附录 C 重构、附录 G 与 §4.2 整节删除、FRR 度量
    命名与下界定义、SPE 单调性修正、新增双栏证据图、补四篇引用、两表移入附录、
    页数压回 12 页、双盲复核、AE 逐条答复与 cover letter 重写。构建：20 页，
    正文止于第 12 页，0 undefined ref/cite，0 悬空 label，0 未引用 bib。

12. **E5′ 判定、AgentDojo 扩展、人工验证与论文第三条发现重写（2026-09-08）**：见本文件顶部本轮记录。
    构建：20 页，正文止于第 12 页，0 undefined/悬空/未引用，双盲干净。

13. **第二轮复核（2026-09-09）**：主机全部离线已核实；`tab:advmeas` 补文档级 bootstrap 区间
    （16 个点估计逐位复现）；OCR 评测由三个有 provenance 的公开文档图像切片补回
    （`tab:ocrslice`，引擎与版本写在 caption 里）；修掉两个重跑即回退的生成缺陷
    （基线改名进生成器、承重传播表改读 pooled 记录）；摘要与 §5.2 的 AgentDojo 口径对齐；
    附录五处语气残留清理。构建：main 14 页（正文止于第 12 页）、appendix 8 页，
    0 undefined/悬空/未引用，双盲干净。

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

## 2026-09-09 遗留问题答复后的落地

- 已按你的答复关闭"正式放弃旧的人工效用验证"（遗留问题第 4 条）。修改说明：核查确认
  `data/cppb_reconstructed_blind_ratings_vgpu3090.csv`（88 行、覆盖 44/192 条输出、
  16 条多评者重叠、provenance 不全、47 条 refusal-like 里 43 条被打成 task success 1）
  **没有被主文或附录的任何声明读取**——主文效用现在走 PrivacyLens 自带 judge 的 0--3
  helpfulness 与 AgentDojo 的环境状态判定，Limitations 也已写明二者均未经人工验证。
  因此本项不需要改论文，只是记账：文件按"保留为记录、不作为证据"处理（不删，删数据要你当面确认），
  `docs/ExperimentProgress.tex` 对应行已标注正式退役。
- 已确认 AI use 声明措辞（遗留问题第 5 条），`paper/main.tex` 的 `ai` 环境保持原样，无需改动。
- 已为第三位独立标注者建好并发布工具（遗留问题第 1 条，你答"要，重新生成"）。修改说明：
  `src/experiments/build_annotation_page.py` 新增 `independent` 模式——空表盲标，102 条全量，
  页面内既不含前两位的答案也不含 judge 判定（构建时断言拦截会泄底的列）。关键是**记录隔离**：
  每一轮各自持有独立的浏览器存储键、独立的 artifact 集合（`annotations` / `round2` / `round3`）
  与独立的导出文件名，两轮共用一个集合会静默合并成一份记录，那样第三轮存在的意义就没了。
  `semantic_inferability_agreement.py` 新增 `--round3`：第一位 vs 第三位是**真正的评分者间信度**
  （两人互不相看），第二位 vs 第三位单独报并注明第二位那侧带引导偏差，judge 与词重叠两个代理
  也在第三位的标签上重算。补齐了 6 条此前缺失的事实句中文对照（第 96--101 条），
  原先它们会让页面构建直接失败。已用合成导出端到端验证；原有 `blind` / `review` 两种模式
  逐字节复现，第二轮的既有答案不受影响。
- 已为 PrivacyLens 自带 judge 的人工抽查建好整条链路（遗留问题第 2 条，你答"抽查"）。修改说明：
  `privacylens_downstream_suite.py` 的 `evaluate_case` 现在可以逐条记录 judge 对**每个敏感条目**
  的判定（原来只有 case 级聚合，而 judge 是逐条裁决的），并新增 `--export-judge-decisions`：
  把已记录的那次运行从生成缓存里重放，导出每条判定连同它当时看到的动作原文，**不触碰**规范 rows 文件。
  这样抽查比对的是产出论文数字的那批判定，而不是重跑出来的另一批；脚本会统计有多少次调用是
  现生成而非重放，只要不为零就明确报警并以非零码退出，因为悄悄重生成的判定会让这次验证测错东西。
  新增 `privacylens_judge_human_sheet.py`（按条件 × judge 自身判定双向分层抽样，输出盲表与
  分析者专用 key 两个文件）与 `privacylens_judge_agreement.py`（整体与逐条件的 κ）。
  标注页新增 `judge_check` 模式：把"是否仍可得知这条事实"换成"这个动作是否泄漏了这条信息"，
  并把会泄底的 `judge_leak` / `judge_reasoning` / `condition` / `case` 一并加进构建时的拦截集合。
  已在合成数据上端到端验证（1200 条判定、22.4% 的偏斜基准率抽成 12 层各 10 条的均衡子集）。
  余下只差在存有 `ollama_cache/` 的主机上跑一次重放，以及标注工时。
- 已查清"legacy CPPB 补齐 backend/digest/decoding"按字面做不到，并把它作为一个新的选择题
  退回给你（见 `# 遗留问题`）。修改说明：`cppb_prompt_manifest.csv` 只有 stub 而没有 prompt 原文，
  产出那四张表的输入已不存在，因此在旧数字旁写 runtime 只能是声称而非记录；未写入任何伪造字段。
  可行的替代是在重建的 256 条面上重测四张表并用带 provenance 的新数字替换，需要开主机。

# 未修改或部分修改

只列仍然开着、且还值得做的项。已完成的在 `# 已全部修改`；已被取代、资产不可恢复、
或属于论文已写明的 future work 的项已从本节移除（`docs/ExperimentProgress.tex`
的 next-step 表仍保留它们的完整记录与百分比，那张表是全量台账，本节只是待办）。

2026-09-09：`# 遗留问题` 的六条已全部答复，本节按答复重排。放弃与认可两条已闭合并
移入 `# 已全部修改`；另外三条从"等你拍板"变成"工具已就绪、等人力或等主机"。

**等标注人力，不等你决策**

- **第三位独立标注者**（60%）：你说"要，重新生成"。空表盲标页已生成并发布，102 条全在里面，
  页面里没有前两位的答案、也没有模型判定；它写进自己独立的存储集合，不会和前两轮混在一起。
  评分脚本 `--round3` 也写好并验证过：它给出的是**真正的评分者间信度**（第一位 vs 第三位，
  两人互不相看），第二位 vs 第三位单独报并注明第二位那侧带引导偏差。
  - 现在只差一个人：不能是作者，且没看过前两轮。把页面分享给对方即可开始，不需要 GPU。
  - 拿到导出的 CSV 后跑 `semantic_inferability_agreement.py --round3 <csv>`，
    然后据此改写主文 Limitations 那段（目前写的是"给不出信度估计"）。
  - 2026-09-09 跨主机同步：标注页此前只在 scratch 目录里，现已入库为
    `src/experiments/semantic_inferability_round3_page_vgpu3090.html`（commit `659788d`），
    别的主机 pull 即可拿到。**同时确认：`round3` 存储集合是空的，第三轮至今一条标注都没有**
    （详见本文件顶部当日条目，内含一个必须避开的 `fake_round3.csv` 合成数据坑）。
- **PrivacyLens 自带 judge 的人工抽查**（70%）：你说"抽查"。整条链路已建好并本地验证：
  `privacylens_downstream_suite.py --export-judge-decisions` 把已记录的那次运行从生成缓存里
  重放出来，逐条导出 judge 对每个敏感条目的判定和它当时看到的动作原文——因此抽查比对的是
  **产出论文数字的那批判定**，不是重跑出来的另一批；抽样按条件和 judge 自己的判定双向分层
  （否则一个"九成说没泄漏"的 judge 会靠基准率白捡一个高一致率）；标注页有 `judge_check` 模式；
  κ 脚本已就绪。
  - 差两步：**一是那次重放必须在有 `ollama_cache/` 的主机上跑**（重放不生成、不耗 GPU，
    但缓存在主机上；脚本会在有任何一次是现生成而非重放时明确报警）；二是 n≥120 的标注工时。
  - 缓存导出后我会补敏感条目的中文对照，再发布标注页。

**卡在外部资源，不需要你现在决定**

- **PrivacyRestore 同协议复现**（60%）：需要白盒自服务模型 + 约 5 天。论文已给出不复现的
  架构理由（它在服务端模型内部做激活引导，本层在黑盒端点之前）。在 11-30 之前做它，
  会和上面的标注工时抢同一份预算。
- **licensed i2b2 临床覆盖**（60%）：等数据使用审批。公开 PhysioNet 路线已跑通并入表。
- **live-stack mapping table 攻防**（50%）：需要一套真实部署栈、审计路径与凭据模型，
  不是算力问题。论文把该结论限定在机制层面。

# 遗留问题

需要你提供/决策。答完一条即可就地删掉该条。

1. **同名 arXiv 预印本 `arXiv:2604.05793` 要更新什么**——见下方"预印本需要更新的内容"，
   确认后我可以直接生成用于 arXiv v2 的稿件。
   - A: 
3. **第三轮独立标注：页面已就绪，但没有人真的标过——需要你确认由谁来标、什么时候标。**
   标注页已入库（`src/experiments/semantic_inferability_round3_page_vgpu3090.html`），
   双击用浏览器打开即可，102 条，只需按 Y/N，做完点导出得到 `human_annotations_round3.csv`。
   这是全篇唯一一个能把"标注者一致性"从上界（κ=0.915，primed）变成真正 IRR 的环节，
   也直接决定 Limitations 段落怎么写、预印本 v2 第 4 条"标注者独立性描述"能不能改。
   拿到 CSV 后我这边跑 `semantic_inferability_agreement.py --round3` 就能出
   annotator1-vs-annotator3 kappa 和重算的 judge/lexical kappa。
   - **需要你回答**：这一轮由谁标（第三位标注者是否还能联系上）？大致什么时候能做完？
     如果赶不上 11-30 投稿，是否接受论文按"仅两位标注者、第二位为复核"定稿？
   - A: 

## 预印本需要更新的内容（回应你上一条的提问）

先说结论：**不用撤，但更新要赶在投稿之前，不要在评审期间更新。** PoPETs 2027 的作者指引原话是
"While not expressly forbidden, we discourage authors from publicly posting pre-prints of their
submissions while under review"——不禁止，但明确不建议在评审期间公开挂预印本，理由就是
审稿人可能搜到从而产生偏见。这篇预印本已经挂在那里了，撤不撤都改变不了它可被搜到，
所以合规上没问题；但**"评审期间推 v2"会主动把它顶上去**，这正是指引劝阻的动作。
投稿的 PDF 那一侧是干净的：已是 `anonymous`，也没有引用这篇预印本。

因此时间点建议：要发 v2 就赶在 11-30 投稿之前发；投出去之后到出结果之前，最好不要动它。

但从内容看，那个版本和现在的稿子差得已经比较远了，而且**差的方向不利于你**——预印本里有几处
现在已知是错的或已被推翻的说法，任何人搜到它都会先看到旧结论。按重要性排：

1. **第三个主结论已经反过来了。** 预印本时代的说法是"中介手段几乎不改变事实层面的泄漏"，
   依据是词重叠指标和 LLM judge。人工盲标推翻了这一条：可推断性从无保护的 100% 降到最激进
   detector 的 24%，而那两个自动指标都没看出这个变化（κ=0.25 和 0.09，后者等于随机）。
   现在论文的第三个卖点是"语义泄漏指标在被人工验证之前不可信"，和预印本写的正好相反。
2. **主证据面换了。** 预印本以自建的 CPPB 为核心证据；现在 CPPB 已降级为附录里的"受控操作面"，
   主文证据换成真实数据：AI4Privacy 300 篇、PrivacyLens 493 条真实 agent 轨迹 + 200 个任务
   （由该基准自带的 judge 评分）、AgentDojo 的 banking/slack（真实工具执行 + 注入）。
   对应的头条数字也换了：PER 7.4% / 1.8%，最终动作里的精确标识符从 13.7% 降到 2.1--3.1%。
3. **多了两个预印本完全没有的结论**：一是恢复时机是主要设计变量（延后到执行边界，
   边界泄漏 51.0% → 1.6%，只损失 0.11 分 helpfulness）；二是语义改写类逃逸能打穿
   排版类逃逸打不穿的 detector（learned detector 上 paraphrase ASR 28.2%）。
4. **几处事实性更正**（这几条是"必须改"，不是"最好改"）：作者单位、标注者的独立性描述
   （第二位是复核不是独立重标）、以及若干在后续核对中被改掉的数字。
5. **署名与致谢**：预印本署三位作者；确认现在的作者名单和顺序与之一致，不一致要一并改。

建议做法：这一轮（第三位标注者 + judge 抽查）落地后、11-30 投稿之前，一次性发 v2；
不要现在发一版两周后再发一版，更不要等投出去之后再发。如果这两项赶不上，
那就只带上面第 1、2、4 条（结论反转、证据面更换、事实性更正）发一版——
把已知是错的说法留在公开版本上，比版本旧本身更伤。
**要发的时候告诉我，我按当时的 `paper/main.tex` 生成一版非匿名的 v2 稿。**

注：PoPETs 2027 正文上限是 12 页（不含 ethical considerations / open science / AI use
三个必需小节、致谢、参考文献与明确标注的附录），超出直接 desk-reject。当前 `paper/main.pdf`
正文正好在第 12 页结束，三个必需小节从第 13 页开始，符合要求；预印本 v2 不受这条约束，
但如果你想让 v2 和投稿版保持一致，就按现在这个结构出。
