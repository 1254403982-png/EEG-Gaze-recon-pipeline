# 架构设计说明

本文描述当前运行版本的模块边界、数据生命周期和关键设计决策。接口字段见
[API.md](API.md)，Policy 数学规则见 [POLICY.md](POLICY.md)，落盘格式见
[DATA_SCHEMA.md](DATA_SCHEMA.md)。

## 1. 总体数据流

```text
BrainCo SDK -> RawEEGChunk -> 原始 NPZ
                         \-> 全 32 导预处理/质量 -> decoder -> EEGFeatures --+
                                                                          |
Tobii G3 -> gaze2d + scene -> 动态屏幕映射 -> EyeFeatureExtractor --------+-> Synchronizer
                                                                          |        |
浏览器 -> UIContext / interaction ---------------------------------------+        +-> Policy
                                                                                       |
                                                 可执行决策锁存 -> 被试确认 -> LLM -> 对话
```

`acquisition` 和 `gaze` 负责设备；`eeg` 负责信号处理；`synchronization` 只组合最新
状态；`policy` 只消费版本化数据契约；`server` 适配 HTTP；`storage` 负责追加式记录。
硬件 SDK、Policy 和实验 DOM 之间没有反向依赖。

## 2. Condition 与实验生命周期

一次页面实验只运行一个 C1/C2/C3 Condition，并创建一个 Condition-scoped run。
同一被试的三种 Condition 通过三次独立 session 完成，实验中途不切换 Condition。

```text
session start
-> T01 前 10 s rest_calibration
-> reading -> quiz -> trial_survey
-> T02 前 10 s rest_calibration -> ... -> T06 -> quiz -> trial_survey
-> condition_survey -> collect -> session end
```

每次 Condition 有 6 个 trial，低/中/高难度各 2 个。题目首次呈现时立即写入
`runs/_subject_question_history.json`，相同被试编号的后续 session 会排除已用题目。
Policy 只允许在 `reading` 阶段触发；状态机本身是门控的一部分。

问卷状态机只包含两种固定 schema：

- `trial-survey-v1`：每个 trial 的两道理解题提交后呈现，依次记录心理努力、困惑程度、
  当前理解（均为 1–7）以及帮助需求（0/1/2）。提交后才能进入下一次静息；T06 提交后
  进入 Condition 问卷。
- `condition-survey-v3`：6 个 trial 完成后呈现，依次记录需求匹配、解释清晰度和个性化；
  三项均为 1–7 同意度并允许“不适用”。提交后结束本次 session。

C1/C2/C3 共用完全相同的说明、题目、顺序和量表。问卷界面不暴露 Condition 编号、传感器
或 Policy 机制，Condition 问卷之后没有额外问卷阶段。

## 3. 时间边界

服务端 `Timestamp` 同时包含：

- `host_monotonic_ns`：同一服务进程内比较先后、新鲜度、窗口和模态偏差。
- `utc`：人类可读的审计时间，不能用于精确间隔计算。
- `device_seconds`：设备提供时原样保留，目前不用于在线融合。

EEG 的逐样本 `host_timestamps_ns` 根据数据块主机接收时刻和采样率向前反推；gaze
样本使用其到达采集电脑时的主机时刻。浏览器交互另带 `Date.now()` 与
`performance.now()`，服务端收到后再附加自己的单调时钟。在线 EEG-gaze 偏差因此是
“最新接收数据之间的主机时间差”，不是硬件 TTL 同步，也没有自动消除设备传输延迟。

## 4. EEG 通路

BrainCo SDK 的发现、连接、启停和缓冲区兼容封装在
`acquisition/brainco_sdk.py`；其他模块不直接导入 SDK。

每个 acquisition chunk 在通道映射、滤波和特征计算前交给 `RunRawEEGRecorder`。
记录器按固定时长分块；session、trial、Condition、phase、采样布局或数据类型变化时
立即切块，并使用临时文件、原子替换和 SHA-256 manifest 降低异常退出损失。

全部 32 导先经过统一预处理和质量判定，形成 `ProcessedEEGWindow`。每个
`EEGDecoder` 再自行按通道名选择输入。默认 `posterior_alpha` 只选择后部 7 导，
但不会裁剪原始数据或全通道质量信息。当前标准输出是相对 Alpha proxy，不是已经验证的
临床认知负荷测量。

## 5. gaze、场景与屏幕映射

核心层只依赖 `GazeProvider`。`UnavailableGazeProvider` 明确返回 unavailable，
`ReplayGazeProvider` 用于离线接口验证，`TobiiG3Provider` 负责 gaze/scene RTSP、
官方佩戴校准、重连和低延迟消费。

Tobii 默认使用 RTSP-over-TCP interleaved transport，降低 UDP 丢包或乱序后损坏 H.264
单元进入 PyAV/FFmpeg 的概率。RTCP 状态队列由 provider 主动排空。该设置是对当前
Windows 原生视频解码崩溃的风险缓解；scene decoder 尚未隔离到子进程，正式收数前仍需
完成覆盖完整 Condition 时长的稳定性验证。

Tobii `gaze2d` 是场景相机归一化坐标。实验页上报 viewport、阅读 AOI、可见 DOM
边界以及左上 OMNI、右上 AI、右下发送、左下下一题四个自然界面锚点。服务端从场景帧
检测屏幕四边形并计算单应矩阵；每个 gaze 样本只使用其到达时有效的矩阵映射，历史轨迹
不会被新矩阵重算。

映射短暂丢失仅在有限 hold 窗口内沿用；过期、几何无效或布局缺失时保留场景坐标，
屏幕坐标和 Eye 指标置空，不虚构 DOM 注视位置。Monitor 显示完整实验页镜像，并只叠加
最近约 3 秒的屏幕轨迹。

## 6. Eye 特征与个人基线

`EyeFeatureExtractor` 从映射后的 3 秒轨迹生成固定契约：AOI dwell、I-DT fixation、
平均 fixation 时长，以及离开阅读 AOI 后再次进入的回视次数和回视停留时间。

- 阅读 AOI dwell 秒数；
- 阅读 AOI 内 I-DT fixation 数量；
- fixation 平均持续秒数。

旧的 entropy、saccade、pupil 等字段可用于诊断，但不进入当前 Policy。C2/C3 在首题
最初 10 秒有效阅读窗口上建立本次 session 的个人 Eye 中位数基线；白屏静息没有映射
锚点，因此不用于 Eye baseline。该选择属于当前实现约束，正式研究前应评估首题材料
难度对基线的污染。

## 7. Policy、降级与消息锁存

C1 不消费任何生理数据；C2 只消费 Eye；C3 消费 Eye 与通过质量门控的 EEG。C3 的
EEG warning/stale/unavailable 时可显式退化为 Eye-only，输出
`degraded_mode=eye_only_low_eeg_quality`；Eye 缺失时绝不退化为 EEG-only。

Policy 还检查 phase、数据年龄、gaze 有效率、屏幕映射、AI 面板注视、多模态时间偏差、
持续证据、冷却时间和每 trial 询问上限。每个输出记录 `sources_available`、
`sources_used`、`component_scores`、`reason_codes`、`suppressed` 和降级状态。

一个可执行 offer 生成后由应用层锁存，直到实验页 `POST /api/policy` 确认领取。这样高频
到达的普通状态不会在前端下一次轮询前覆盖触发，也避免同一 episode 同时出现两个询问。

## 8. 两条 LLM 交互通路

人工通路在 C1/C2/C3 都存在：被试先选解释档位，再粘贴材料片段并发送。选择按钮本身
不会调用 LLM。

Policy 通路先使用近期轨迹、gaze overlay 场景帧和完整材料推断可能的关注区域，然后只
显示一个带“需要帮助 / 不需要”选择的确认气泡。拒绝只落盘；接受后才调用 LLM 生成相应
档位解释。Policy、确认和回答通过同一 `policyId` 连接。答题、已有确认气泡、AI 正在回复
或被试注视右侧 AI 面板时，不叠加新询问。

## 9. Condition-scoped 存储

`ExperimentRunManager` 只为正式被试 session 创建：

```text
runs/<subject>_condition_<n>_<stamp>/
  metadata.json
  experiment.json
  events.jsonl
  interactions.jsonl
  eeg/
  gaze/
  policy/
```

高频 EEG/gaze 特征与稀疏交互分文件保存。原始 EEG、原始 gaze、滚动特征、Policy 和
浏览器汇总彼此不互相替代。`experiment.json` 原子覆盖保存最终汇总；JSONL/NPZ 采用
追加或分块方式，因此 Trial/Condition 问卷汇总保存失败不会破坏已经完成的信号块。

每条 Trial 问卷记录归入对应 `trials[].trialSurvey`；Condition 问卷记录归入
`meta.conditionSurveys[]`。两者都保存 schema 版本与快照、开始/提交时间、逐题响应延迟、
题序和答案。Condition 的“不适用”保存为 `answers` 中的 `null`，并同步写入
`notApplicable[]`，不能按量表中点处理。

## 10. 可审计性与当前复现缺口

事件记录包含 session/trial/Condition/phase 和服务端时间；对话额外记录
`source=manual|policy|f10`、角色、完整内容、解释档位和 `policyId`。Policy 日志在状态
变化时立即写，相同状态最多每秒写一次。

当前 run 尚未自动快照完整配置、Policy 参数、题库版本、代码版本、设备/固件、LLM
temperature 与完整提示词；场景 JPEG 也没有随 run 持久化。它们是正式可复现实验前需要
补齐的元数据，不应在论文中声称已经完整记录。
