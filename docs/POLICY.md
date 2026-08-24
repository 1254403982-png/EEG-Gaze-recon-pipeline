# Policy 层说明

## C3 Policy 版本

原始规则固定为 `c3_policy_version=v1`，默认配置 `configs/development.json` 继续使用该
版本。新的研究候选规则位于 `configs/development_c3_v2.json`，通过配置继承只覆盖 Policy
参数，不改变 EEG、Tobii、LLM 或存储设置：

```powershell
.\run_tobii.ps1 -C3PolicyV2 -BrainCo
```

也可显式传入 `-Config configs/development_c3_v2.json`。不要用默认启动命令采集新版 C3；
默认 `development.json` 是为复现原始 v1 保留的冻结配置。

C3 v2 检验 EEG 相对于 gaze 的增量价值，而不是简单要求两个模态投票：

- gaze 异常、EEG 正常：可能是正常复核、兴趣或阅读策略，不自动干预；
- gaze 正常、EEG 仅轻度升高：证据不足，不自动干预；
- gaze 正常、EEG 持续高负荷：标记为 gaze 不可见的隐性认知过载，提供 example；
- gaze 异常、EEG 同时升高：提供 example；EEG 高负荷时提供 detailed；
- EEG 低质量：不降级为 Eye-only，不声称发生了多模态推断。

候选配置把每个 Trial 的自动提示限制为 2 次，将初始无干预窗口和冷却期提高到 30 秒，
并要求 3 次确认和 0.45 秒持续证据。这些是待验证的预注册候选参数，不能由单个被试 002
直接证明。学习效果应通过 C2/C3 的正确率、延迟保持、迁移题和主观负担验证；减少不必要
干预则报告每 Trial 提示数、拒绝率，以及 gaze-only 异常被 EEG 否决的比例。

在 C3 中，AI 正在生成内容时 Policy 被服务端显式抑制；答案显示后根据文本长度进入
45–90 秒阅读安静期，拒绝一次提示后进入 30 秒安静期。安静期不仅隐藏前端弹窗，还会通过
UI context 清除生成前已经锁存的旧提示，避免答案刚显示就立即出现下一次帮助询问。

## C2 focus and trigger calibration (2026-08-06)

- The first policy evaluation is held when `seconds_in_trial` is missing, so the server cannot offer help before the configured 20-second reading-start protection window.
- Screen mapping prefers readable leaf content (`p`, `li`, table cells and formulas) when available. If calibration places the gaze between lines, the broader reading container or a paragraph heading may remain as a fallback target.
- C2/C3 eye thresholds remain unchanged; the system does not require pixel-level gaze precision. The target label is allowed to be a readable paragraph or heading when that is all the camera can support.

Policy 将当前 Eye、EEG、实验条件和界面阶段转换为四级决策。它不直接调用 LLM；
前端只有收到可执行决策后才询问被试，被试选择“需要帮助”后才生成解释。

固定等级只有：`none`、`brief`、`example`、`detailed`。当前规则是可审计的先导实验
规则，不是医学判断或已经验证的认知状态分类器。正式实验前应固定版本并预注册参数。

## 1. 实时输入与门控

入口为 `MultimodalPolicyEngine.evaluate(MultimodalState)`：

| 来源 | Policy 使用字段 |
|---|---|
| 实验上下文 | `session_id`、`trial_id`、`condition`、`ui.phase` |
| Eye | `aoi_dwell_time`、`fixation_count`、`mean_fixation_duration`、`aoi_revisit_count`、`aoi_revisit_time` |
| Eye 质量 | gaze `status/quality`、`valid_sample_ratio`、屏幕映射、主机接收时间 |
| EEG | `cognitive_load`、`attention`、`quality`、主机接收时间 |

以下情况不触发：

- `ui.phase` 不是 `reading`；静息、答题、问卷和反馈阶段均禁用。
- Eye 数据缺少三个核心指标，或 gaze 不是 `available/pass`。回视字段是可选兼容字段，缺少时不加入回视权重。
- gaze 有效样本比例低于 `gaze_min_valid_ratio`。

开发启动脚本会把 `gaze_min_valid_ratio` 同时传给 Tobii 采集器和 Policy。这样 C2 不会先被
采集器旧的 0.60 门槛拦截；但仍要求有效样本、屏幕映射和三个 Eye 核心指标都存在。
- 屏幕映射无效。
- 屏幕布局中的 `trial_id` 或 `slide_id` 与当前 UI 上下文不一致；新题正在渲染时暂缓询问，
  避免把上一题的停留区域当成当前题的关注区域。
- 最近约 1.5 秒的屏幕轨迹中心位于右侧 `ai_panel`。
- C3 两种高质量信号的主机接收时间差超过 `max_multimodal_skew_ms`。
- 每个 Trial 进入材料后的前 `minimum_trial_seconds=20` 秒；这段时间用于让被试进入
  阅读状态并完成首段基线，服务端返回 `trial_reading_baseline_window`。
- 屏幕映射已启用但最近轨迹没有在阅读元素上形成稳定 `dwell_target`；只在阅读区域
  附近形成持续停留时才允许产生候选，避免用材料后段的概念去打断前段阅读。

## 2. 固定 Eye Feature

Tobii provider 从真实 `gaze2d` 样本得到最近 3 秒的屏幕映射轨迹。阅读材料容器是
Policy AOI；AI 对话区不属于阅读 AOI。

```json
{
  "eye": {
    "aoi_dwell_time": 1.84,
    "fixation_count": 5,
    "mean_fixation_duration": 0.31,
    "aoi_revisit_count": 1,
    "aoi_revisit_time": 0.42
  }
}
```

- `aoi_dwell_time`：窗口内有效注视落在阅读 AOI 的累计秒数。超过 100 ms 的缺样间隔
  不计为连续 dwell。
- `fixation_count`：阅读 AOI 中的 I-DT fixation 数量。
- `mean_fixation_duration`：上述 fixation 的平均持续时间，单位秒。
- `aoi_revisit_count`：在离开阅读 AOI 后再次进入并形成有效 fixation 的次数；第一次进入不计入回视。
- `aoi_revisit_time`：回视段在阅读 AOI 内的累计有效停留时间，单位秒；只统计第一次进入之后的段落。

I-DT 使用映射后的归一化屏幕坐标，默认离散阈值 `0.035`，最短持续时间 `100 ms`。
旧的 entropy、saccade、pupil 等诊断字段可以保留在 gaze 日志中，但不进入 Policy。

## 3. Personal baseline

每个 Condition/session 建立一个 Eye baseline。由于纯白静息页没有屏幕映射锚点，
Eye baseline 使用本轮第一道题开始后最初 5 秒的有效映射阅读窗口，而不是白屏静息数据。

系统收集至少 5 个互不重复的 3 秒 Eye snapshot；三个核心时长/计数指标取正值中位数，
回视次数和回视时间允许为 0，并取非负值中位数：

```text
baseline_aoi_dwell_time
baseline_fixation_count
baseline_mean_fixation_duration
baseline_aoi_revisit_count
baseline_aoi_revisit_time
```

baseline 建立期间输出 `hold` 和 `eye_personal_baseline_collecting`，不会询问被试。
这段收集与第一道题的前 20 秒阅读保护窗重叠，因此保护窗结束后不再额外等待一轮基线；
后续 Trial 继续使用本 Condition 的基线，但每个 Trial 仍保留 20 秒保护窗。
即使 10 秒基线已经完成，首题仍要等到材料开始后的 20 秒才允许自动询问。后续 Trial
沿用本 Condition 的 Eye baseline，但每个 Trial 都重新执行这 20 秒的阅读起始保护窗。

## 4. C2：Eye-only

实时归一化：

```text
dwell_ratio    = current_aoi_dwell_time / baseline_aoi_dwell_time
fixation_ratio = current_fixation_count / baseline_fixation_count
duration_ratio = current_mean_fixation_duration / baseline_mean_fixation_duration

# 仅当当前窗口和个人 baseline 都提供回视字段时启用；+1/+0.25 防止低计数时比例爆炸
revisit_count_ratio = (current_aoi_revisit_count + 1) / (baseline_aoi_revisit_count + 1)
revisit_time_ratio = (current_aoi_revisit_time + 0.25) / (baseline_aoi_revisit_time + 0.25)

eye_difficulty_score =
    (0.40 * dwell_ratio
   + 0.30 * fixation_ratio
   + 0.30 * duration_ratio
   + 0.15 * revisit_count_ratio
   + 0.15 * revisit_time_ratio)
    / (0.40 + 0.30 + 0.30 + 0.15 + 0.15)
```

当前开发配置把单项异常比例设为 `eye_abnormal_ratio=1.25`，任一核心指标达到
`eye_single_feature_ratio=1.70` 才可单独形成举例候选；Eye 总分门槛为
`1.35/1.55/2.00`。简单解释仍需两个核心指标异常，或核心指标与回视证据共同支持；

C2 使用独立覆盖参数，避免为了修复 C2 漏检而同时改变 C3 融合规则：异常比例为
`1.20`，brief/example/detailed 为 `1.15/1.55/2.00`，单核心指标阈值为
`1.70`。C2 每个 Trial 最多自动询问 2 次，两次可执行 episode 至少间隔 30 秒。
被试点击“需要/不需要”后会释放新的证据 episode，因此同一题可以在新的疑问证据下再次询问。
问题做的温和放宽。回视指标只在两侧均有有效
baseline 时加入，不会因为旧日志缺字段而改变判定。C2/C3 的组合指标仍使用同一套
Eye level，但只有持续证据通过后才会显示询问。

| Level | 条件 | 输出 |
|---|---|---|
| 0 | 未达到核心异常条件 | `none` |
| 1 | score `>=1.35` 且至少一个核心 ratio `>=1.20` | `brief` |
| 2 | score `>=1.50` 且有重复核心证据、核心+回视证据或单个核心 ratio `>=1.75` | `example` |
| 3 | score `>=1.75`，并通过持续证据门控 | `detailed` |

回视指标不能凭借单独一次升高触发 Level 1；C2 不读取任何 EEG 字段。

## 5. C3：Eye + EEG

Eye level 使用 C2 结果并转换为 `0–3`。高质量 EEG 转换为：

EEG 主解码器使用额区 `FZ/F3/F4/FC1/FC2` 的 4–7 Hz 相对 Theta 功率，以及后部
`P3/P4/P7/P8/PZ/O1/O2` 的 8–13 Hz 相对 Alpha 功率。两者均相对于 4–30 Hz 功率，
并计算 `workload_index = log(frontal_theta) - log(posterior_alpha)`；随后按被试内
滚动历史百分位映射为 `cognitive_load`。这个 0–100 数值是相对 workload proxy，
不是心理量表百分比。

| EEG level | 条件 |
|---|---|
| 0 | `cognitive_load <50` |
| 1 | `50 <= cognitive_load <80` |
| 3 | `cognitive_load >=80` |

当前不从 workload 反向生成 attention；`attention` 兼容字段为 null，也不参与C3门控或分级。

高质量 EEG 的审计融合分数为：

```text
final_difficulty_score = 0.40 * eye_level + 0.60 * eeg_level
```

最终等级采用附件规定的保守 case rule：

| Eye | EEG | 输出 |
|---|---|---|
| 正常 | 正常 | Level 0 |
| 异常 | 正常 | 最多 Level 1 |
| 正常 | 异常 | 最多 Level 1 |
| 异常 | 中/高负荷 | Level 2 |
| 异常 | 高 workload | Level 3 |

EEG 为 warning、stale、unavailable 或缺少 workload 时，`quality_confidence=0`，C3
自动退化为 Eye-only；`degraded_mode=eye_only_low_eeg_quality`。低质量 EEG 不会触发或
提高等级。Eye 缺失时不允许退化为 EEG-only。

## 6. 稳定化与输出

开发配置下，非 `none` 候选连续出现 2 次并持续 0.20 秒。Level 3 因此仍需要多个异常窗口。
一次触发后同一证据 episode 不重复发送；开发配置下同一等级新 episode 至少间隔 8 秒。当前配置不设置每个
trial 的询问次数上限（`max_automatic_offers_per_trial=0` 表示 unlimited），前端也不再按解释等级去重，
因此 C2 在同一题内可以在新的证据 episode 中再次主动询问。进入下一个 trial 时 episode 状态重置，但个人 Eye baseline
继续沿用。

可执行决策会在服务端锁存，直到实验页通过 `POST /api/policy` 确认领取，因此不会被
随后到达的高频 gaze 状态覆盖。实验页每 400 ms 读取一次 Policy；普通健康状态和布局
仍按较低频率更新。

`PolicyDecision` 中可审计字段包括：

- `difficulty_score`：C2 为 baseline ratio 加权分；C3 为 `0–3` 融合分。
- `component_scores`：三个 ratio、baseline、Eye level、EEG level、质量置信和融合分。
- `reason_codes`：baseline、门控、C2/C3 case、等待、冷却和降级原因。
- `sources_available/sources_used`：Policy 使用 `eye` 与 `eeg` 名称。
- `target_aoi`、`confidence`、`degraded_mode`、`suppressed`。

前端只在 `explanation_level != none`、`action != hold` 且 `suppressed=false` 时显示询问。
AI 正在回答、已有待选择询问或被试注视 AI 面板时不会叠加新询问。

## 7. Eye 信息进入 LLM 的时机

1. Policy 未触发时，Eye/EEG 只进入规则引擎与日志。
2. 可执行 trigger 产生后，视觉 LLM 使用最近轨迹场景帧、映射轨迹和完整材料复核关注区域，
   同时把该帧及轨迹缓存为内存中的 `frameSnapshot`。
3. 前端先询问被试“是否对该内容感到疑惑”。
4. 选择“不需要”只记录拒绝；选择“需要帮助”才调用 LLM，并复用触发时的
   `frameSnapshot`，不会重新抓取视线已移到 AI 对话区后的新帧。
5. Policy、被试选择和 LLM 回复通过相同 `policyId` 关联。

快照只随当前待确认 Policy 对象在内存中传递。持久化到 `trial.policySuggestions` 时只保留
关注区域推断和帧时间等元数据，不保存 `frameSnapshot` 的 base64 图像，避免
`experiment.json` 体积膨胀。

## 8. 调参位置

常规调参位于 `configs/development.json`：

```json
{
  "required_confirmations": 2,
  "minimum_evidence_seconds": 0.20,
  "minimum_trial_seconds": 20.0,
  "cooldown_seconds": 8,
  "max_automatic_offers_per_trial": 0,
  "gaze_min_valid_ratio": 0.50,
  "eye_baseline_seconds": 5.0,
  "eye_baseline_min_samples": 5,
  "eye_dwell_weight": 0.40,
  "eye_fixation_weight": 0.30,
  "eye_duration_weight": 0.30,
  "eye_revisit_count_weight": 0.15,
  "eye_revisit_time_weight": 0.15,
  "eye_abnormal_ratio": 1.25,
  "eye_single_feature_ratio": 1.70,
  "eye_mild_threshold": 1.35,
  "eye_moderate_threshold": 1.55,
  "eye_strong_threshold": 2.00,
  "c2_eye_abnormal_ratio": 1.20,
  "c2_eye_single_feature_ratio": 1.70,
  "c2_eye_mild_threshold": 1.15,
  "c2_eye_moderate_threshold": 1.55,
  "c2_eye_strong_threshold": 2.00,
  "c2_cooldown_seconds": 30.0,
  "c2_max_automatic_offers_per_trial": 2,
  "eeg_medium_threshold": 50,
  "eeg_high_threshold": 80,
  "eeg_weight": 0.60,
  "gaze_weight": 0.40,
  "allow_degraded_c3": true
}
```

修改配置后必须重启服务。正式实验前应使用先导数据评估误触发率、漏触发率和帮助接受率。

## 9. 参考

- [pymovements I-DT event detection](https://pymovements.readthedocs.io/en/stable/user-guide/event-detection.html)
- [Fixation duration and pupil size as objective measures of memory load](https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2014.01063/full)
- [Neurophysiological Measures of Mental Workload: A Systematic Review](https://pmc.ncbi.nlm.nih.gov/articles/PMC12061935/)
