# CHI 投稿研究与分析方案

更新时间：2026-08-04。本文面向当前 Recon EEG + Eye Tracking + Adaptive Assistance
系统，区分“现在能记录什么”“正式研究还需验证什么”和“论文可以主张什么”。它不是已经
完成的预注册；先导结果出来后仍需冻结假设、排除标准、样本量和统计模型。

## 1. 投稿现实与论文定位

[CHI 2027 Papers](https://chi2027.acm.org/authors/papers/) 当前官方截止时间是
**2026-09-10 AoE**，没有摘要截止。官方鼓励 5,000–8,000 词；超过 12,000 词且无充分
理由会 desk reject。投稿使用单栏匿名稿，正文必须独立成立，人体实验须符合作者所在机构
的伦理审查要求。

CHI 的核心不是“设备多”，而是对 HCI 的原创、显著、有效且可复核的贡献。官方
[成功投稿指南](https://chi2027.acm.org/guide-to-a-successful-submission/) 特别强调：
定量和技术工作应可验证、可复现、可重复，研究问题、设计选择、算法和统计分析都要说明
“为什么”。

本项目最有潜力的定位是：

> 在自然屏幕阅读中，EEG 是否在 gaze 之上提供了可行动的增量信息；一个不直接替用户
> 做决定、而是先询问确认的实时 AI assistance policy，何时能改善理解和求助体验，何时
> 又会造成打断或错误推断？

不建议把论文定位成“首次把 gaze 视频交给 LLM”。2026 年预印本
[From Gaze to Guidance](https://arxiv.org/abs/2604.08062) 已直接使用第一视角视频和
gaze overlay 让多模态 LLM 推测困难位置。更可区分的贡献是：**在线实时干预、EEG 的增量
价值、透明可审计的 Policy，以及 ask-before-help 对用户自主性的影响**。

## 2. 建议贡献

论文应集中在 2–3 项互相支撑的贡献，而不是罗列功能：

1. **系统贡献**：一个把第一视角 gaze grounding、个人化 Eye baseline、EEG proxy、
   实验阶段门控和被试确认组合起来的实时 mixed-initiative 阅读助手。
2. **实证贡献**：比较人工求助、gaze-policy、EEG+gaze-policy，量化理解、保持、求助成本、
   错误打扰和用户控制感。
3. **方法贡献**：展示如何用事件级 ground truth、信号质量和降级审计评估“何时提供 AI
   帮助”，并报告 gaze-only 与 fusion 的 participant-independent 增量表现。

如果 EEG fusion 没有稳定超过 gaze-only，这仍可形成有价值的负结果：在什么质量与任务
边界下，增加 32 导 EEG 的佩戴成本并没有带来足够的 HCI 收益。

## 3. 研究问题与可检验假设

### RQ1：困难时刻能否被有效识别？

- gaze-only、EEG-only 和 EEG+gaze 对被试标注困难 episode 的事件级检出能力如何？
- fusion 相比 gaze-only 的增量是否在新被试和新材料上仍存在？
- 映射质量、坏导、头动和传输延迟如何影响误提示与漏报？

只有在先导数据支持后才预注册方向性 H1：fusion 的 participant-level PR-AUC 和事件级
recall 高于 gaze-only，同时 false prompts/min 不增加。

### RQ2：自动帮助是否改善理解？

- C2/C3 相比 C1 是否提高题级理解正确率或一周后的保持？
- 提升来自正确时机、更多帮助，还是不同解释粒度？
- 自动询问是否减少被试复制粘贴、提问轮次和求助启动成本？

主假设应围绕一个主要结局，例如题级即时理解正确率；延迟保持建议作为关键次要结局。

### RQ3：主动干预如何影响体验与自主性？

- 被试何时接受、拒绝或忽略帮助？
- 询问确认是否让推断错误更可容忍，还是仍会造成打断和被监控感？
- 用户对 gaze、EEG、场景视频和第三方 LLM 数据传输的接受边界是什么？

该问题适合量表加半结构访谈，不应只靠接受率替代。

## 4. 正式收数前的阻断项

以下问题会直接损害内部效度，应先解决再冻结研究：

### 4.1 题目选项位置偏差

当前 96 道理解题的 `answerIndex` 分布为：位置 0/1/2/3 分别为 **38/49/8/1**；高难度
32 道小题的正确答案全部在位置 0。被试可能学习位置规律，Condition 和顺序比较会被污染。

正式版本必须在呈现时随机化选项，并保存稳定 option ID、显示顺序和正确 option ID；
不能只改 `answerIndex` 而不保留呈现映射。

### 4.2 材料没有在 Condition 间平衡

系统当前保证每次低/中/高各 2 篇且同一被试不重复，但材料是随机抽取，不保证同一 item
在不同被试中均衡进入 C1/C2/C3。应预生成 balanced incomplete block / Latin-square
assignment，使每篇材料在各 Condition、session 位置和顺序中的曝光近似相等。

### 4.3 Eye baseline 受首题污染

个人 Eye baseline 来自随机 T01 的最初 10 秒有效阅读，而 T01 可以是任意难度；该基线
随后影响本 Condition 全部 6 个 trial。正式实验建议增加统一、不计分的中性阅读校准材料，
用相同字号和布局建立 baseline，使 T01 与其他 trial 可比较。

### 4.4 EEG 构念尚未验证

当前 `cognitive_load` 是 4 秒后部 Alpha 在被试滚动历史中的相对 proxy；
`attention = 100 - cognitive_load`，不是独立注意力指标。由此，当前 Policy 的高 load 与
低 attention 实际是同一条件：当 load `>=70` 时 attention 必然 `<=30`，当前 decoder 下
EEG level 2 分支实际不可达而会直接进入 level 3，不能作为“两种 EEG 证据一致”。

论文中在构念验证前应使用 `posterior-alpha proxy`，不能直接称为准确识别认知负荷。
40/70 阈值、0.60 EEG 权重和坏导阈值必须来自冻结的先导证据，而不是主实验后调到显著。

### 4.5 三条件混合了 timing、dose 与 content

C1/C2/C3 同时改变自动询问时机、询问数量和解释等级。即使 C3 表现更好，也不能直接
归因于 EEG。应采用本文件第 7 节的 matched-dose 时机控制，或把检测与干预拆成两个研究。

### 4.6 问卷与复现元数据不足

当前问卷已经收敛为两种固定 schema：每个 Trial 后的 `trial-survey-v1` 记录心理努力、
困惑程度、当前理解和帮助需求；每个 Condition 后的 `condition-survey-v3` 只记录需求匹配、
清晰度和个性化。三个条件使用完全相同的中性说明、题目、顺序与量表，并保存问卷版本和
题目快照。正式研究仍需在先导中做认知访谈、冻结中文措辞并预注册单项分析，不应把这些
自编项目冒充已验证量表。

run 仍尚未快照代码/配置/题库/prompt/model 参数，且没有保存 Policy 视觉定位所用场景帧。
正式研究前需补齐，详见 [DATA_SCHEMA.md](DATA_SCHEMA.md)。

另外，当前 `calibration.eyeTrackerConnected` 被错误赋为 EEG 连接状态，不能把该字段用于
眼动可用性排除；应以服务端 gaze 日志与 health 状态为准，修复后再收正式数据。

## 5. 阶段 A：技术与构念先导

建议先招募 12–18 名参与者；该数字用于发现问题和估计方差，不替代正式功效分析。

### 5.1 屏幕映射验证

让被试依次注视 9 或 16 个已知目标，每个 1.5–2 秒，并在中心、左右/前后头动和自然阅读
姿势下重复。报告：

- 屏幕归一化或像素误差的 median、IQR、P90/P95；
- AOI hit rate、mapping availability、丢失时长和重捕获时间；
- 静止与头动条件的误差差异；
- gaze 到 Monitor/实验页显示的端到端延迟。

### 5.2 时间与系统延迟验证

分别测量并报告分布，而不是只给均值：

```text
设备/场景事件 -> 主机接收
主机接收 -> Eye/EEG 特征可用
候选证据 -> Policy offer
offer -> 前端确认气泡
确认 -> LLM 首字/完整回答
```

至少报告 median、P90/P95、最大值、掉包/重连次数和 `absolute_skew_ms`。当前主机到达时间
方案足以支持秒级事件分析，但不应写成毫秒级硬件同步。条件允许时用共同硬件事件或
光电/TTL 参考测量传输偏差。

### 5.3 EEG proxy 构念验证

使用经过预试的低/高难度阅读或标准 workload task，配合 trial 级 mental-effort 自报，
验证 posterior-alpha proxy 的方向、被试内效应、重测可靠性和坏导敏感性。报告全部 32 导
质量、后部 7 导可用数、窗口 pass 比例和 C3 Eye-only 降级比例。

### 5.4 困难 ground truth

被试接受/拒绝只标注已经触发的位置，无法发现漏报；人工提问也只覆盖主动求助的困难。
建议组合：

- 少量随机时刻 difficulty probe，用于采样未触发区间；
- trial 后展示材料、时间线和近期 gaze 轨迹，让被试回看并标出困惑起止与对应段落；
- 人工提问、答题错误和接受/拒绝作为辅助标签，不把任一单独当金标准；
- 两名独立标注者复核段落/episode 边界，报告一致性。

回放标注应在 trial 后进行，避免实验中频繁移动鼠标改变头部和眼动。先导完成后冻结
window、baseline、阈值、权重、冷却时间和最大 offer 数。

## 6. 阶段 B：离线 Policy 验证

所有参与者同时采集 EEG 与 gaze，用完全相同的时间区间比较：

1. gaze-only；
2. EEG-only（研究比较，不作为当前在线 UI 的降级路径）；
3. EEG+gaze fusion；
4. 简单基线，如始终预测无困难或只用阅读时长。

训练/调参必须以 participant 为组做 LOSO 或 nested group cross-validation；同一被试、同一
材料或重叠窗口不能同时进入训练和测试。若继续使用无训练的规则 Policy，也应在 pilot 上
冻结阈值，然后只在独立 confirmatory 数据上评估。

### 6.1 检测指标

- PR-AUC 为主要分类指标；同时报告 ROC-AUC、balanced accuracy、sensitivity、specificity。
- Brier score、可靠性图或 expected calibration error。
- 事件级 precision/recall/F1、false prompts/min、false prompts/trial、missed episodes。
- 从困难 onset 到提示的延迟；提示早于、落在或晚于困难 episode 的比例。
- 屏幕段落 localization top-1/top-k、AOI hit rate 和轨迹到标注区域距离。
- gaze/EEG 特征消融、坏导阈值敏感性和低质量降级分析。

窗口级结果只用于模型诊断。论文应把 participant-level 或 event-level bootstrap 95% CI
作为推断依据，避免重叠窗口造成伪重复。

## 7. 阶段 C：交互主实验

### 7.1 当前三条件的最低可行设计

保留现有被试内设计：

| Condition | 在线行为 | 主要比较 |
|---|---|---|
| C1 | 人工选择档位、粘贴提问 | reactive/manual baseline |
| C2 | 人工通路 + gaze offer | C2-C1：主动 Eye Policy 的端到端差异 |
| C3 | 人工通路 + EEG/gaze offer | C3-C2：增加 EEG 后的端到端差异 |

所有 Condition 都应佩戴并静默采集两种设备，只改变 Policy 可用数据，避免 EEG 帽/眼镜的
佩戴负担成为条件混淆。三次 session 顺序用 6 种 Williams/Latin-square 序列平衡；每种
序列人数相等。条件间安排充分休息，记录 session 间隔。

该三条件可以比较完整系统配置，但不能单独证明“提示时机正确”或“EEG 导致提升”。

### 7.2 更强的 CHI 设计：matched-dose 时机控制

最推荐增加一个与 adaptive 条件 **提示次数、解释等级和内容剂量匹配**，但时机来自随机或
前一名被试的 yoked control。这样才能把“正确时机”与“多给帮助”分开。CHI 2026 的
[Sensing What Surveys Miss](https://doi.org/10.1145/3772318.3791191) 使用了 aligned、
time-misaligned 和 random timing 比较；[Eye-Mind Reader](https://doi.org/10.1080/07370024.2020.1716762)
也使用 matched-dose yoked control，并发现效果可能只在延迟测验出现。

若四个长 Condition 造成疲劳，可以采用：

- Study B 离线比较 gaze 与 fusion，Study C 只用胜出 Policy 比较 manual/aligned/yoked；或
- 在 Policy 候选时刻 micro-randomize 为“展示 / 暂不展示”，但需单独设计因果分析；或
- 固定解释粒度，只研究 timing；再把解释粒度作为另一个独立实验因素。

每 trial “最多 2 次”只能是上限，不应强制每题凑 1–2 次。否则 trigger rate 成为设计常量，
无法证明 Policy 真正发现困难。

### 7.3 材料与流程

- 当前每 Condition 6 个 trial、每难度 2 个可保留，但正式 assignment 必须跨 Condition
  平衡 item，而不只是被试内去重。
- 用独立样本预试材料的难度、长度、先验知识需求和两道理解题的 item difficulty/
  discrimination；主实验不再修改题目。
- 加不计分练习 trial，让被试熟悉复制粘贴、Policy 确认和设备。
- 记录领域先验知识；理解题侧重全文机制、迁移与边界，而不是原句识别。
- 建议在 24 小时或一周后做无 AI 的延迟保持/迁移测验。

## 8. 测量

### 8.1 主要结局

建议只预注册一个主要结局：每道理解题是否正确。当前每 trial 两题，分析应展开为题级，
而不是使用“两题至少对一题”的 `quiz.isCorrect`。

### 8.2 次要结局

| 类别 | 指标 |
|---|---|
| 学习 | `correctCount/2`、延迟保持、迁移题、答案信心 |
| 效率 | 纯阅读时间、逐题答题时间、总完成时间、用户输入字数/轮次 |
| 求助 | 人工提问率、offer 数、接受/拒绝/无响应、确认反应时 |
| Policy | precision/recall、漏报、误提示、触发延迟、目标段落准确性 |
| Trial 自报 | 心理努力、困惑程度、当前理解、帮助需求 |
| Condition 自报 | 需求匹配、解释清晰度、个性化 |
| 系统 | mapping 可用率、EEG pass/坏导、降级率、时钟偏差、LLM 延迟/错误 |

`trial-survey-v1` 在每个 Trial 的两道理解题提交后立即呈现四题：心理努力、困惑程度和当前
理解使用七分制，帮助需求使用 `0 没有 / 1 有但需求较低 / 2 有且需求较高`。其中帮助需求
可作为 Policy 命中、漏检和误触发分析的一项主观参照，但不能单独作为困难状态的客观真值。

`condition-survey-v3` 在每轮 6 个 Trial 完成后呈现三题：需求匹配、解释清晰度和个性化。
三项均使用 `1 完全不同意` 至 `7 完全同意`，并允许“不适用”；“不适用”必须作为独立类别
报告，不能编码为量表中点。当前问卷不支持把心理努力宣称为完整 workload 量表，论文应按
单项自报如实命名，并结合理解题、交互日志与传感特征分析。

### 8.3 LLM 回答质量

由不知道 Condition 的两名评审者独立编码：

- 与材料一致性/事实正确性；
- 是否回答被试关注的问题；
- 是否重复材料已有信息；
- 是否符合 brief/example/detailed 约束；
- 幻觉、遗漏或不必要扩展。

报告 Cohen's kappa、weighted kappa 或 ICC，并解决分歧。LLM-as-judge 可作为探索性补充，
不能替代人工盲评。

## 9. 统计分析计划

以 trial/item 为观测单位，以 participant 和 material 为随机效应。不要先按每人取均值后
只做三组 t-test，也不要把高频生理窗口当独立样本。

| 结局 | 建议模型 |
|---|---|
| 题级是否正确 | logistic GLMM |
| 阅读/答题/LLM 延迟 | log-normal LMM、Gamma GLMM；有删失时考虑生存模型 |
| 1–5/1–7 Likert | cumulative-link ordinal mixed model |
| offer/人工提问/错误次数 | negative-binomial mixed model |
| offer 接受 | logistic mixed model（仅有 offer 的选择性样本，需明确） |

题级主模型示意：

```text
correct ~ condition * material_difficulty
        + session_order + trial_position + prior_knowledge
        + (1 + condition | participant)
        + (1 | material) + (1 | question)
```

如果模型因样本量不能支持完整随机斜率，应预注册简化顺序并透明报告，而不是看到结果后
任意选择。主要 planned contrasts 可设为 `C2-C1` 和 `C3-C2`；若加入 yoked control，
`aligned-yoked` 应成为验证时机的主要对比。次要对比用 Holm 校正，始终报告效应量、
95% CI、原始分布和模型诊断，不只报告 p 值。

C3 按随机/指派 Condition 做 intention-to-treat 主分析；另预注册只包含足够 EEG 覆盖的
per-protocol 敏感性分析，并报告每个 run 的 `degraded_mode` 比例。不能把低质降级窗口
删除后仍称为无偏的 C3 主结果。

## 10. 样本量

相关近邻研究样本包括 N=32、36 和 70，但这些数字不能直接证明本设计的功效。先用阶段 A
估计 participant/item 方差、ICC、正确率基线和最小有意义差异，再对预注册 GLMM 做
simulation-based power analysis。

实务上可以先按 **至少 48 名完成者** 规划：三条件 6 种顺序各 8 人；考虑 EEG/眼动失效、
退出和延迟测验流失，预招约 54–60 人。最终 N 必须由功效模拟、预算和停止规则共同决定，
不要把 48 写成没有依据的固定答案。

## 11. 排除、缺失与质量

正式前预注册：

- 被试层：未完成、未同意、设备完全失败、未遵守任务的定义；
- run/trial 层：最低 gaze mapping 覆盖、EEG pass 覆盖、LLM 可用性和异常短/长时长；
- 信号层：坏导、插值、artifact、窗口重叠和降级的处理；
- 数据缺失：不把 0 当缺失，不因结果方向选择性删除；
- 设备/网络故障：重连、冻结场景帧、API 超时和重复 offer 的识别规则；
- 离群值：阈值依据、变换和稳健性分析。

被拒绝的 offer 不是自动假阳性；无 offer 也不是自动真阴性。分类指标必须依赖独立困难
标注。主分析、敏感性分析和探索性分析要在表格中分开。

## 12. 质性研究

每个 Condition 后做简短体验问题，全部 Condition 后进行 15–25 分钟半结构访谈：

- 哪些提示来得正好、过早、过晚或完全错误？
- 为什么接受/拒绝；是否改变主动求助？
- 先询问确认是否保留了控制感？
- 是否担心眼动、脑电、场景视频和 AI 推断？
- 设备重量、校准、头动限制是否改变自然阅读？

明确采用 reflexive thematic analysis 或 codebook thematic analysis，报告研究者立场、
编码流程、分歧处理和主题证据。不要只挑少量支持系统的引语。

## 13. 伦理、隐私与开放科学

正式收数前完成所在机构要求的伦理审批和书面知情同意。必须明确：

- 32 导 EEG、gaze、场景相机、完整对话和答题记录的内容；
- 场景帧和材料会发送给阿里云百炼/第三方 LLM；
- 可能拍到屏幕外环境或可识别信息；
- 去标识、加密、访问人员、保存期限、撤回和销毁流程；
- 被试可拒绝 AI 帮助且不受惩罚。

补充材料建议匿名发布：预注册、系统图、冻结配置、Policy 伪代码、材料 assignment、问卷、
访谈提纲、清洗/分析脚本、合成示例数据和去标识派生数据。无法公开原始 EEG/场景视频时，
说明伦理原因并公开可复核的派生表与数据字典。

遵守 [CHI 匿名规则](https://chi2027.acm.org/chi-anonymization-policy/)：论文、附件、匿名
仓库、文件 metadata、图片人脸和伦理表述都不能泄露作者或机构身份。

## 14. 收数前冻结清单

- [ ] 伦理审批、同意书和第三方 LLM 数据传输说明完成。
- [ ] 修复选项位置偏差，完成材料/题目独立预试和平衡 assignment。
- [ ] 使用统一中性阅读材料建立 Eye baseline。
- [ ] 完成映射、头动、时间延迟、EEG proxy 和 Policy ground-truth pilot。
- [ ] 冻结代码、配置、Policy、题库、模型、temperature 和完整 prompt。
- [ ] run 自动保存上述版本/hash、设备信息、选项顺序和逐题时间。
- [ ] 预注册 RQ、主要结局、planned contrasts、排除/缺失和 GLMM。
- [ ] 用 pilot 参数完成功效模拟并确定招募/停止规则。
- [ ] 准备盲评 LLM 输出、延迟保持测验和半结构访谈流程。
- [ ] 在 2–3 个完整模拟 run 上验证所有文件可连接并由另一人复现分析。

## 15. 建议论文结构

1. Introduction：问题、用户代价、研究空白和贡献。
2. Related Work：proactive/mixed-initiative AI、gaze-aware assistance、neuroadaptive HCI。
3. System：时钟、映射、特征、Policy、确认机制、失败与降级。
4. Formative/Validation Study：ground truth、技术误差和模型消融。
5. Main Study：条件、材料、参与者、流程、测量、功效与伦理。
6. Results：主要结果、Policy 性能、体验、质量和质性主题。
7. Discussion：EEG 增量是否值得、agency/timing 设计启示、隐私与局限。
8. Reproducibility Statement：公开与不公开的 artifact 及原因。

若伦理审批和主要数据尚未基本完成，距离 CHI 2027 Full Paper 截止时间过短，不建议用
未经验证的小样本匆忙形成强结论。可以先完成高质量 pilot，考虑 CHI 2027 Poster/交互展示
获取反馈，再以完整、预注册的研究瞄准后续 Full Paper。

## 16. 近邻工作起点

- [Sensing What Surveys Miss, CHI 2026](https://doi.org/10.1145/3772318.3791191)：
  生理/行为状态驱动的主动 LLM 支持与 aligned/misaligned/random timing。
- [Eye-Mind Reader](https://doi.org/10.1080/07370024.2020.1716762)：
  gaze 自适应与 matched-dose yoked control、即时与延迟学习结果。
- [AttentiveLearn, CHI 2026](https://doi.org/10.1145/3772318.3790667)：
  眼动驱动的长期个性化学习研究。
- [From Gaze to Guidance, 2026 preprint](https://arxiv.org/abs/2604.08062)：
  第一视角 gaze overlay 与多模态 LLM assistance。
- [Detecting Reading-Induced Confusion, 2025 preprint](https://arxiv.org/abs/2508.14442)：
  EEG+眼动的阅读困惑离线检测。
- [Need Help?, CHI 2025](https://arxiv.org/abs/2410.04596)：主动 LLM assistance 与
  mixed-initiative 用户控制。
