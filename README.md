# Recon EEG + Gaze 自适应阅读辅助实验平台

Recon 是一个面向受控阅读实验的实时平台。它同步接入 BrainCo 32 通道 EEG、
Tobii Pro Glasses 3 眼动和实验界面事件，用可审计的 Policy 决定是否向被试提出
AI 帮助询问，并把原始信号、派生特征、策略、交互与答题结果保存在同一次
Condition 的 run 中。

```text
BrainCo 32 导 EEG -> 原始分块 + 全通道预处理 -> Theta/Alpha workload proxy --+
                                                                  |
Tobii gaze2d + 场景视频 -> 屏幕映射 -> 3 秒 Eye 特征 + 个人基线 ------+-> Policy
                                                                  |      |
实验阶段、题目与对话事件 -----------------------------------------+      +-> 先询问被试
                                                                         |
                                                      被试选择需要帮助 --+-> LLM
```

当前实现已经包含完整实验页面、实时 Monitor、题库、两条 AI 通路、Condition 级
数据存储和真机适配。它仍是研究原型，不是临床脑电系统，也不能把眼动或频谱
指标直接解释成被试的真实想法。

## 当前能力

- BrainCo 32 通道采集、原始数据分块保存、1–45 Hz 预处理、PSD 和逐导质量检查。
- 全部 32 导参与预处理；C3 默认使用 `FZ/F3/F4/FC1/FC2` 的额区 Theta 与
  `P3/P4/P7/P8/PZ/O1/O2` 的后部 Alpha 计算被试内 workload proxy。
- Tobii `gaze2d`、场景视频和官方佩戴校准接入。
- 使用实验界面四个自然锚点进行动态单应映射，并保存每个 gaze 样本到达时的
  场景坐标、屏幕坐标和映射状态。
- Policy 固定消费阅读 AOI dwell、fixation 数量和平均 fixation 时长；C3 还可消费
  EEG proxy，并记录输入、门控、降级、冷却和触发原因。
- 人工通路与 Policy 通路并存。自动触发只先显示“需要帮助 / 不需要”，被试确认
  “需要帮助”后才调用 LLM。
- 完整实验生命周期：单次进入只运行一个 Condition；每个 Condition 6 个 trial，
  低/中/高难度各 2 题，每题前 10 秒纯白静息；每个 trial 的两道理解题后提交 4 题即时
  问卷，6 个 trial 全部完成后提交 3 题 Condition 问卷。
- 48 篇材料题库；相同被试编号跨三次 Condition 不重复出题。
- 服务端统一记录 EEG、gaze、Policy、实验阶段、完整对话、被试选择和问卷。

## 实验条件

| Condition | 人工粘贴提问 | 自动 Policy | Policy 数据源 |
|---|---:|---:|---|
| C1 | 是 | 否 | 不使用 EEG/Eye |
| C2 | 是 | 是 | Eye-only |
| C3 | 是 | 是 | Eye + EEG；EEG 低质量时显式退化为 Eye-only |

Eye 缺失或屏幕映射无效时，C2/C3 都不会退化为 EEG-only。Policy 只在
`reading` 阶段运行；静息、答题、问卷和 AI 对话区注视期间不会发起新询问。

## 实验问卷

实验平台只呈现两类问卷，三个 Condition 的措辞、题序和量表完全相同：

- 每个 Trial 后的 `trial-survey-v1` 共 4 题：心理努力、困惑程度、当前理解均为七分制，
  帮助需求为 `0 没有 / 1 有但较低 / 2 有且较高`。
- 每个 Condition 后的 `condition-survey-v3` 共 3 题：需求匹配、解释清晰度和个性化，
  均使用 `1 完全不同意` 至 `7 完全同意`，并允许选择“不适用”。

Condition 问卷提交后本次 session 结束，不再呈现其他问卷。完整措辞、字段与编码见
[问卷方案](docs/QUESTIONNAIRES.md)。

## 快速启动

当前真机组合推荐 64 位 Python 3.10。第一次部署以及 Tobii 的 PyAV/aiortsp
兼容安装必须按 [使用说明](docs/USAGE.md) 执行，不要复制另一台电脑的虚拟环境。

```powershell
cd 'D:\Users\EDY\Desktop\EEG+Gaze\recon_pipline'
Set-ExecutionPolicy -Scope Process Bypass
.\.venv-win\Scripts\Activate.ps1
$env:DASHSCOPE_API_KEY = '你的 API Key'
.\run_tobii.ps1 -BrainCo
```

启动后使用：

```text
http://127.0.0.1:8810/experiment   被试实验页面
http://127.0.0.1:8810/monitor      EEG、眼动映射与 Policy 监控
http://127.0.0.1:8810/api/health   设备与服务健康状态
```

不连接硬件时可运行：

```powershell
python -m recon_pipeline.cli --config configs/development.json
```

## 数据目录

正式记录从实验进入首个静息校准阶段后开始。一次实验只建立一个 Condition 目录：

```text
runs/<被试编号>_condition_<1|2|3>_<时间>/
  metadata.json
  experiment.json
  events.jsonl
  interactions.jsonl
  eeg/{metadata.json,manifest.jsonl,features.jsonl,chunks/*.npz}
  gaze/{raw_samples.jsonl,features.jsonl}
  policy/decisions.jsonl
```

`host_monotonic_ns` 用于同一服务进程内的时间比较，UTC 用于审计，设备时间原样
保留。当前同步依据是数据到达采集电脑的时间，不等于硬件 TTL 同步。逐文件语义、
连接键和离线分析注意事项见 [数据结构](docs/DATA_SCHEMA.md)。

## 文档

- [使用说明](docs/USAGE.md)：新电脑安装、真机启动、实验操作和故障检查。
- [架构说明](docs/ARCHITECTURE.md)：采集、映射、同步、Policy、UI 与存储边界。
- [Policy 说明](docs/POLICY.md)：C2/C3 输入、个人基线、阈值、门控和输出。
- [API 说明](docs/API.md)：页面和 HTTP 接口契约。
- [数据结构](docs/DATA_SCHEMA.md)：run 文件、字段、时钟、连接键和派生指标。
- [原始 EEG](docs/RAW_EEG.md)：NPZ/manifest 格式与恢复方法。
- [CHI 研究方案](docs/CHI_STUDY_PLAN.md)：研究问题、实验、测量和统计分析计划。
- [修改记录](docs/MODIFICATION_LOG.md)：实现变更与验证历史。

## 测试

```powershell
python -m pytest -q
```

## 科研边界

- `cognitive_load` 当前是被试内滚动历史归一化的额区 Theta/后部 Alpha workload
  proxy，不是经过量表标定的真实负荷百分比；`attention` 不再由负荷反向派生。
- gaze 只能作为可能的关注与困难证据；相同轨迹也可能表示复核、兴趣或正常阅读。
- C3 低质量 EEG 会退化为 Eye-only。论文分析必须报告降级比例，不能把所有 C3
  trial 都表述为完整多模态融合。
- 正式实验前必须冻结题库、配置、Policy、模型和提示词，并完成时间延迟、屏幕映射、
  EEG 构念以及 Policy 检出性能验证。
