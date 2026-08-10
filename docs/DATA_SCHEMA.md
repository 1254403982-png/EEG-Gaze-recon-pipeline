# 实验数据结构与离线连接说明

本文定义当前正式 run 中各文件的用途、时间语义和连接键。它是数据分析入口；原始 EEG
的数组字段见 [RAW_EEG.md](RAW_EEG.md)，实时接口见 [API.md](API.md)。

## 1. 记录边界

服务启动时的 `development` / `not_started` 状态不写正式数据。被试在实验页开始一次
单 Condition session 后创建：

```text
runs/<subject>_condition_<1|2|3>_<YYYYMMDD_HHMMSS_microseconds>/
  metadata.json
  experiment.json
  events.jsonl
  interactions.jsonl
  eeg/
    metadata.json
    manifest.jsonl
    features.jsonl
    chunks/chunk_*.npz
  gaze/
    raw_samples.jsonl
    features.jsonl
  policy/
    decisions.jsonl
```

T01 前 10 秒静息开始时已经进入正式 session。之后每个 trial 前的静息、阅读、答题、
Trial 即时问卷、Condition 问卷和结束事件都归入同一目录。

## 2. 公共标识与连接键

| 键 | 范围 | 用途 |
|---|---|---|
| `subject_id` | 被试 | 位于 run `metadata.json`；文件夹名只用于浏览，不作为唯一数据源 |
| `session_id` | 一次页面实验 | 当前等于被试输入编号；需与 Condition 和 run 时间共同使用 |
| `condition` | 1/2/3 | 本次实验条件 |
| `trial_id` | `T01`–`T06` | 信号、Policy 和交互的主要 trial 连接键 |
| `slideId` / question ID | 题目 | 连接题库材料；`experiment.json` 中保存 |
| `policy_id` / `policyId` | 一次 Policy 决策 | 连接 trigger、确认气泡、接受/拒绝、视觉定位和回答 |
| `request_id` | 一次 LLM 代理请求 | 调用方提供 `X-Request-ID` 时连接代理请求/响应；不替代 `policyId` |
| `host_monotonic_ns` | 同一服务进程 | 精确比较服务端事件与采集到达时间 |

`trial_id` 与浏览器对象中的 `trialIndex` 不同：前者是 `T01`–`T06`，后者当前为从 0
开始的数组索引。离线表应优先保留二者，并用 run/Condition/trial 三元组避免跨 session
碰撞。

## 3. 时间戳语义

服务端 `timestamp`：

```json
{
  "host_monotonic_ns": 1234567890123,
  "utc": "2026-08-02T12:34:56.789Z",
  "device_seconds": 18.42
}
```

- `host_monotonic_ns`：同一 Python 服务进程内的主要分析时钟；适合计算间隔和对齐。
- `utc`：跨文件人工审计；系统时钟调整会影响它，不用于精确间隔。
- `device_seconds`：设备提供时保留；当前在线系统不做设备时钟 offset/drift 拟合。
- `client_timestamp.wall_clock_iso`：浏览器墙钟。
- `client_timestamp.performance_ms`：当前页面生命周期中的浏览器单调时间。

EEG `host_timestamps_ns` 是根据 acquisition chunk 到达主机的时刻和采样率向前反推的
逐样本时间；gaze 的服务端时间表示样本到达采集电脑的时刻。两者可以支持当前秒级实验
的主机到达时间对齐，但不能表述为硬件级同步。服务重启后不能直接比较不同进程的
`host_monotonic_ns`，跨 run 对齐应使用各自相对时间和 UTC 审计。

## 4. 文件数据字典

### `metadata.json`

run 的最小身份信息：schema、被试编号、Condition、实验时间、开始记录 phase 和时钟
声明。当前没有自动保存完整配置、代码版本、题库 hash、设备/固件或 LLM 参数。

### `experiment.json`

浏览器在 Condition 问卷提交时保存的汇总文档：

- `experimentData.meta`：被试、背景、Condition、题目顺序、题目 ID、起止时间。
- `experimentData.calibration`：T01 前静息的开始/结束、界面 load 采样和连接标志。
- `experimentData.trials[]`：材料、难度、时间、答题、Trial 即时问卷、对话和界面层 EEG 采样。
- `experimentData.meta.conditionSurveys[]`：本次任务结束后的中性同版问卷。
- `experimentData.summary`：正确数、对话数和采样数等显示层汇总。

浏览器断点使用 localStorage["cogload_experiment_data"]，当前 checkpoint schema 为 2。
`experimentData.progress` 保存 `status`（`idle`、`active` 或 `completed`）、`phase`、
`currentTrial`、`updatedAt` 和版本号；`meta.runStamp` 连接浏览器断点与服务端 run 目录。
断点每约 2 秒更新，并在 `pagehide`/`beforeunload` 时再写一次。恢复时保留已经完成的 Trial
和全部对话、信号摘要及问卷；正在进行但未完成的 Trial 会从头重做，避免把半份答题或问卷
当成有效观测。Condition 问卷阶段恢复后直接回到问卷，不会重复生成已提交记录。

Trial 即时问卷当前版本为 `trial-survey-v1`。每个 trial 的两道理解题提交后记录
`trials[].trialSurvey`，包含以下四项：

```text
trial_mental_effort: 1..7
trial_confusion: 1..7
trial_understanding: 1..7
trial_help_need: 0..2
```

Condition 问卷当前版本为 `condition-survey-v3`。C1/C2/C3 呈现完全相同的三项题目，
界面不暴露条件编号或传感/Policy 机制。三项均为 1–7 同意度，并允许显式“不适用”：

```text
assistance_need_fit / assistance_clarity / assistance_personalization
```

系统不再收集主动筛选回忆题、条件分支题或三个 Condition 完成后的最终总问卷。

每条 `trials[].trialSurvey` 和 `conditionSurveys[]` 记录都包含：

| 字段 | 语义 |
|---|---|
| `questionnaireVersion` | 固定问卷版本；分别为 `trial-survey-v1` 或 `condition-survey-v3` |
| `condition` | 后台真实 C1/C2/C3；不在被试问卷中显示 |
| `trialIndex` / `trialId` | Trial 问卷所属题次；Condition 问卷不使用 |
| `startedAt` / `submittedAt` | 浏览器 epoch 毫秒 |
| `durationMs` | 打开问卷到最后点击提交的时长 |
| `answers` | 按稳定题目 ID 索引；Condition 的“不适用”保存为 `null` |
| `notApplicable[]` | Condition 中明确选择“不适用”的题目 ID；Trial 问卷为空数组 |
| `responseLatenciesMs` | 从问卷打开到该题最后一次选择的相对毫秒数 |
| `itemOrder[]` | 实际呈现顺序 |
| `schemaSnapshot` | 本次题目、端点、方向与反向计分标志快照 |

Condition 问卷第一次点击“确认提交”时，浏览器立即生成唯一的 survey record、追加到
`meta.conditionSurveys[]`、写入本地存储并禁用全部选项。此后即使 `/api/interaction`、
`/api/collect` 或 session finalize 失败，答案、首次 `submittedAt` 和逐题延迟也保持冻结。
“重新提交”只复用这条 pending record 重试上传和 session finalize，不重新读取界面、不追加
第二条问卷记录，也不改写首次提交时间。该重试通过
`condition_questionnaire_finalize_retried` 审计。

每个 trial 的核心字段：

| 字段 | 语义 |
|---|---|
| `startTime` / `endTime` | 浏览器 epoch 毫秒 |
| `durationSec` | 材料出现到第二道理解题提交；混合了阅读和答题时间 |
| `quiz.quizOpenTime` | 被试点击“下一题”、打开理解题的浏览器时间 |
| `quiz.responseTimeSec` | 两道理解题合计答题时间 |
| `quiz.results[]` | 每题文本、选择位置、正确位置和 `isCorrect` |
| `quiz.correctCount` | 两题答对数量 |
| `quiz.isCorrect` | 当前定义为两题至少答对一题，不能解释为整篇完全理解 |
| `trialSurvey` | 本 trial 的 `trial-survey-v1` 四题回答、时长和 schema 快照 |
| `chatMessages[]` | 本 trial 的用户/AI 消息、来源、档位和 Policy 关联 |
| `loadSamples[]` | 浏览器约每 1.5 秒取得的 EEG proxy，不是原始 EEG |

纯阅读时间可暂时派生为：

```text
reading_time_ms = quiz.quizOpenTime - trial.startTime
```

正式主分析应使用 `quiz.results[].isCorrect` 的题级二元结果，或明确报告
`correctCount / 2`；不要直接把 `trial.quiz.isCorrect` 当作理解正确率。

### `events.jsonl`

稀疏服务端事件，如 session start/end、UI context 等。每条包含 schema、session、trial、
Condition、服务端 timestamp 和 payload。未知事件类型也写入本文件。

### `interactions.jsonl`

实验操作与对话审计。每条包含 `action`、session/trial/Condition/phase、服务端 timestamp、
当时的 EEG-gaze 同步摘要以及浏览器 payload。当前主要 action：

```text
calibration_started / calibration_completed
rest_calibration_started / rest_calibration_completed
trial_started / quiz_opened / trial_completed
trial_questionnaire_started / trial_questionnaire_submitted
manual_explanation_level_selected
policy_focus_inferred / policy_prompt_shown / policy_response
conversation_message
llm_question_submitted / llm_gaze_context_attached
llm_answer_rendered / llm_answer_failed
llm_proxy_request_received / llm_proxy_response_received
f10_policy_trigger
condition_questionnaire_started / condition_questionnaire_submitted
condition_questionnaire_finalize_retried / condition_completed
```

`conversation_message.payload` 保存完整 `role/content`、`messageType`、
`explanationLevel`、`policyId` 和 `source`：

| `source` | 含义 |
|---|---|
| `manual` | 被试主动选择档位、粘贴并发送 |
| `policy` | C2/C3 自动询问被确认后产生 |
| `f10` | 主试用 F10 模拟 Policy trigger |

拒绝自动帮助也会记录 `policy_response`，但拒绝本身不能自动视为 Policy 假阳性；被试可能
暂时不想被打断。未触发时也没有天然的困难标签，因此 Policy recall 需要额外 ground truth。

### `eeg/chunks/*.npz` 与 `eeg/manifest.jsonl`

采集、映射和滤波前的 32 通道数据与分块清单。详见 [RAW_EEG.md](RAW_EEG.md)。

### `eeg/features.jsonl`

实时 4 秒滚动 EEG 窗口的 `status/quality/cognitive_load/attention/alpha_*`、全部坏导、
decoder 输出和服务端时间。事件记录器对相同类型最多约 5 Hz 落盘。重叠窗口不是独立
观测；统计模型不能把数万个窗口当作数万个被试。

### `gaze/raw_samples.jsonl`

每个 Tobii `gaze2d` 样本的设备时间、主机接收时间、场景归一化坐标，以及样本到达时的
屏幕映射快照。映射失败时屏幕值为空而不是 0。该文件不保存场景 JPEG。

Policy 视觉定位会临时缓存触发时场景帧及最近轨迹为内存中的 `frameSnapshot`。被试确认需要
帮助后，解释 LLM 复用该快照，不重新抓取视线移到对话区后的帧。`frameSnapshot` 不写入
`trials[].policySuggestions`；持久化记录只含关注区域推断、帧时间、轨迹样本数和 Policy
关联信息，不含 base64 图像。

### `gaze/features.jsonl`

最近约 3 秒滚动轨迹得到的 gaze 质量、有效率、屏幕位置与 Eye 三指标。事件记录器对相同
类型最多约 5 Hz 落盘。它是派生特征，不能替代 `raw_samples.jsonl`。

### `policy/decisions.jsonl`

C1/C2/C3 的决策记录；C1 通常为 `no_adaptation`。状态变化立即写；完全相同的状态最多
每秒写一次，而不是保存每次内部 evaluate 调用。核心字段：

- `explanation_level/action/suppressed`；
- `difficulty_score/component_scores`；
- `sources_available/sources_used`；
- `reason_codes/degraded_mode/confidence`；
- `target_aoi/evidence_duration_seconds/policy_id`。

## 5. 推荐离线合并顺序

1. 读取 run `metadata.json`，创建 `run_id`，确认 Condition 与开始时钟。
2. 用 `interactions.jsonl` 的 `trial_started`、`quiz_opened`、`trial_completed` 重建阶段；
   同时保留各信号文件已有的 `trial_id/phase` 作一致性检查。
3. 从 `experiment.json` 展开 trial 与题级答案；连接题库 ID、难度和顺序。
4. 按 `host_monotonic_ns` 在每个 trial/phase 内汇总 EEG/gaze 质量和特征。
5. 用 `policy_id` 连接 decisions、prompt、focus inference、接受/拒绝和回答。
6. 分开计算 Policy 视觉推断、确认等待和回答生成延迟，不把整段延迟都归因于传感触发。
7. 所有主统计以 participant、item 或 trial 为层级；高频窗口只用于 trial/episode 聚合或
   明确建模的时间序列分析。

## 6. 建议派生表

### `trial_outcomes`

一行一 trial：participant、run、Condition、order、trial、item、difficulty、阅读时间、
答题时间、`correctCount`、人工提问数、自动 offer/接受数、主观评分和有效信号覆盖率。

### `question_outcomes`

一行一理解题：participant、Condition、item、question index、显示选项位置、正确位置、
是否正确。正式实验应在随机化选项后同时记录稳定 option ID 与显示顺序。

### `policy_episodes`

一行一候选/触发 episode：Policy 特征和门控、offer 时间、目标区域、解释档位、是否展示、
接受/拒绝、各阶段延迟、LLM 成功与 ground-truth 困难标签。

### `signal_quality`

一行一 trial/phase：gaze 有效率、screen mapping 可用率/误差、EEG pass 比例、坏导比例、
C3 完整融合与 Eye-only 降级比例、模态时间偏差以及掉线时长。

## 7. 完整性检查

正式纳入分析前至少检查：

- run 目录名、`metadata.json` 与所有记录的 Condition 一致；
- 6 个 `trial_started` 和 6 个 `trial_completed` 成对；
- 每 trial 有 2 个 `quiz.results`，答案位置合法；
- 每 trial 有且只有一份完整的 `trial-survey-v1`，本 run 有且只有一份完整的
  `condition-survey-v3`；
- EEG manifest 的 SHA-256 与文件一致，NPZ 的 context 不跨 trial/phase；
- C2/C3 的 gaze 映射覆盖率、C3 EEG pass/降级率达到预注册标准；
- Policy prompt、response 和 conversation 的 `policyId` 能闭合；
- LLM 失败、session 提前结束和问卷保存重试被显式标记，不静默删除。

## 8. 当前需在正式收数前补齐的复现元数据

当前实现尚未自动记录以下内容：

- 代码 commit/build ID、完整 `development.json` 及其 hash；
- Policy 有效参数快照和题库/选项顺序版本；
- BrainCo/Tobii 序列号脱敏标识、固件和 SDK 版本；
- 精确 LLM 模型版本、temperature、完整 system/user prompt、token usage，以及浏览器为
  每次调用生成的非空稳定 request ID；
- Policy 视觉推断所用场景帧或可验证的去标识 artifact/hash；
- 每道理解题的独立作答时刻。

在这些字段补齐前，当前数据足以做技术调试和描述性先导分析，但不应声称第三方可以完整
重放每次 Policy 与 LLM 决策。

## 9. 隐私

`interactions.jsonl` 和 `experiment.json` 含完整被试提问与 AI 回答；Tobii 场景图在运行时
可能包含屏幕、环境或人物，并会在 Policy 视觉定位时发送给第三方 LLM API。API Key 不会
写入 run，但这不等于数据匿名。正式研究必须在知情同意、伦理审批和数据管理计划中明确
采集内容、第三方传输、保存期限、访问权限、去标识方式和撤回规则。
