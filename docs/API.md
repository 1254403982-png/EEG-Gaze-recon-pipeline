# 实验平台接口说明

所有写接口接受 JSON，所有响应均为 JSON。

页面由同一服务提供：

```text
GET /             导航
GET /experiment   实验平台
GET /monitor      实时监控
```

## 实验会话与状态

### `POST /api/session/start`

```json
{"session_id": "S001", "condition": 1}
```

为正式被试创建 `runs/<subject>_condition_<n>_<stamp>/` 并重置同步器和 Policy。使用
`development` 或 `not_started` 不创建正式 run。中断后可以带原目录时间戳恢复：

```json
{"session_id": "S001", "condition": 1, "resume_stamp": "20260805_143012_123456"}
```

当对应目录存在且时间戳格式有效时复用该目录，否则创建新目录。响应会包含本次 run 的
`run_stamp`，浏览器将其写入 `experimentData.meta.runStamp`。

### `POST /api/session/end`

```json
{}
```

先写入 `session_ended`、flush 当前记录器，再关闭本次 run。实验页在 Condition 问卷与
`/api/collect` 保存成功后调用。

### `GET /api/condition`

返回当前实验条件以及严格允许的采集来源：

```json
{
  "condition": 2,
  "policy_enabled": true,
  "sources": {"eeg": false, "gaze": true}
}
```

### `POST /api/condition`

```json
{"condition": 3}
```

### `POST /api/ui/context`

```json
{
  "trial_id": "T05",
  "phase": "reading",
  "slide_id": "7",
  "seconds_in_trial": 23.4,
  "metadata": {
    "reading_progress": 0.35,
    "reading_scroll_top": 420
  }
}
```

## 实时输入

### `POST /api/eeg/features`

供独立脑电处理进程使用。直接通过 `--brainco` 启动时由内部后台任务提交。
该接口接收的是处理后特征，不包含原始波形。原始 EEG 仅在使用内部
`--brainco` worker 时自动写入当前 Condition run 的 `eeg/chunks/`。

```json
{
  "status": "available",
  "quality": "pass",
  "cognitive_load": 72,
  "attention": 28,
  "alpha_power": 12.7,
  "alpha_peak_hz": 10.2,
  "alpha_suppression": 0.31,
  "bad_channels": []
}
```

### `POST /api/gaze`

真实眼动适配器最终需要输出此结构。`eye` 是 Policy 唯一消费的眼动特征契约；其余
gaze 字段只用于质量、映射和诊断：

```json
{
  "status": "available",
  "quality": "pass",
  "x_normalized": 0.42,
  "y_normalized": 0.61,
  "primary_aoi": "reading_content",
  "eye": {
    "aoi_dwell_time": 1.84,
    "fixation_count": 5,
    "mean_fixation_duration": 0.31,
    "aoi_revisit_count": 1,
    "aoi_revisit_time": 0.42
  },
  "fixation_duration_ms": 820,
  "fixation_rate": 1.8,
  "saccade_rate": 2.4,
  "pupil_dilation": 0.16,
  "gaze_entropy": 0.51,
  "blink_rate": 0.22,
  "valid_sample_ratio": 0.94
}
```

`aoi_dwell_time`、`mean_fixation_duration` 和 `aoi_revisit_time` 的单位是秒。
`aoi_revisit_count` 是回到阅读 AOI 并形成有效 fixation 的次数，不包含第一次进入。
屏幕映射无效、阅读 AOI 不存在或数据不足时，五个 Eye 数值必须使用 `null`，不得使用伪造的 `0`。旧的
fixation/entropy/saccade/pupil 字段可以继续提交，但不会进入当前 Policy。

## 输出

### `GET /api/policy`

```json
{
  "schema_version": "1.0",
  "policy_id": 184,
  "session_id": "S001",
  "trial_id": "T05",
  "condition": 3,
  "action": "offer_example",
  "explanation_level": "example",
  "ui_mode": "assistance",
  "reason_codes": ["c3_eye_and_eeg_difficulty_agree"],
  "sources_available": ["eye", "eeg"],
  "sources_used": ["eye", "eeg"],
  "target_aoi": "reading_content",
  "confidence": 0.85,
  "degraded_mode": null,
  "suppressed": false
}
```

实验平台必须按 `policy_id` 去重，并核对 `session_id`、`trial_id` 和 `condition`。
可执行的自动询问会由服务端锁存，后续非触发状态不会在实验页读取前覆盖它。

### `POST /api/policy`

实验页收到并开始呈现锁存的自动询问后进行确认：

```json
{"policy_id": 184}
```

响应中的 `acknowledged=true` 表示该消息已从待领取槽清除。它只确认前端已收到，不代表
被试选择了“需要帮助”；被试选择仍通过 `POST /api/interaction` 单独记录。

### `GET /api/state`

返回最新同步状态及最新策略，主要供监控和调试使用。`state.eye` 是
`state.gaze.eye` 的稳定顶层镜像：

```json
{
  "state": {
    "eye": {
      "aoi_dwell_time": 1.84,
      "fixation_count": 5,
      "mean_fixation_duration": 0.31,
      "aoi_revisit_count": 1,
      "aoi_revisit_time": 0.42
    }
  }
}
```

Policy 的个人基线、实时 ratio、Eye/EEG level 和最终融合分位于最新决策的
`component_scores` 中。baseline 尚未完成时，决策为 `hold`，并包含
`eye_personal_baseline_collecting`。每个 Trial 的 `seconds_in_trial` 小于
`policy.minimum_trial_seconds`（开发配置为 15 秒）时，决策会包含
`trial_reading_baseline_window`；屏幕映射如果没有阅读元素的稳定 `dwell_target`，
也不会生成自动询问。

对于 C2，`GET /api/policy` 还会返回 `screen_mapping`、`seconds_in_trial` 和 `ui_phase`，
用于区分“屏幕映射/眼动流未就绪”和“Eye ratio 尚未达到门槛”。C2 不会使用 EEG 代替缺失的
Eye 指标；只有 `available/pass` 的 gaze、有效屏幕映射以及 dwell、fixation、duration
三个核心 Eye 指标齐全时才会进入 C2 阈值计算。

### `POST /api/policy/evaluate`

不注入新信号，只要求服务端立即用最新状态重新评估一次 Policy。该接口用于测试与调试；
正式页面依靠信号/UI 更新和 `GET /api/policy`，不需要持续调用它。

### `GET /api/health`

返回 HTTP 服务、脑电和眼动的独立连接及质量状态。

### `GET /api/attention`

为迁移后的原实验界面提供兼容的 EEG 负荷响应。

### `POST /api/collect`

把浏览器汇总原子保存为当前 Condition run 的 `experiment.json`。没有正式 active run 时
返回错误；该接口不会替代此前已经追加的 JSONL/NPZ。

问卷数据随同浏览器汇总保存：

- `experimentData.trials[].trialSurvey`：每个 Trial 一份 `trial-survey-v1`，包含心理努力、
  困惑、主观理解和帮助需求 4 题。
- `experimentData.meta.conditionSurveys[]`：每个 Condition 一份 `condition-survey-v3`，
  只包含需求匹配、清晰度和个性化 3 题。

两类记录都保存 `questionnaireVersion`、开始/提交时间、逐题作答延迟、题目顺序、答案和
schema 快照。Condition 中明确选择“不适用”的题目在 `answers` 中为 `null`，并同时写入
`notApplicable[]`。

Condition 第一次确认时，浏览器先冻结唯一问卷记录并写入本地存储，再调用本接口完成上传。
若上传或 session finalize 失败，“重新提交”会复用相同答案与首次 `submittedAt`，只重试
上传和结束流程；不会再次采集作答、修改原记录或向 `conditionSurveys[]` 追加重复项。

### `POST /api/interaction`

```json
{
  "action": "policy_response",
  "policyId": 184,
  "response": "needed",
  "client_timestamp": {
    "wall_clock_iso": "2026-08-02T12:34:56.789Z",
    "performance_ms": 18234.5
  }
}
```

服务端补充 session/trial/Condition/phase、`host_monotonic_ns` 和当时的同步摘要，写入
`interactions.jsonl`。对话、Policy 确认、问卷和实验阶段操作均通过此接口审计。
问卷使用 `trial_questionnaire_started`、`trial_questionnaire_submitted`、
`condition_questionnaire_started` 和 `condition_questionnaire_submitted` 等 action。
首次确认后的网络或结束流程失败再次提交时，另写
`condition_questionnaire_finalize_retried`；该事件表示复用已冻结记录重试上传和 session
finalize，不表示被试重新作答，也不应计为第二份 Condition 问卷。

### `GET /api/questions/used?subject_id=S001`

返回该被试在本机已呈现的题目 ID，用于跨三次 Condition 排除重复题目。

### `POST /api/questions/reserve`

```json
{"subject_id":"S001","condition":2,"question_ids":["1","17","33"]}
```

题目首次呈现时原子更新 `runs/_subject_question_history.json`。该历史文件不属于某个单独
run，也不含答题结果。

### `POST /v1/chat/completions`

将实验界面的 OpenAI 兼容请求转发到配置的大语言模型。凭据只从
`DASHSCOPE_API_KEY`（或请求的 `Authorization` 标头）读取。调用方可提供
`X-Request-ID`，服务端会在代理 request/response 交互事件中原样记录；当前实验页尚未
自动生成该标头，因此正式复现实验前应补齐，不能依赖空 ID 连接并发请求。

## 时间同步与场景帧

`GET /api/state` 的 `state.synchronization` 使用采集电脑的
`host_monotonic` 时钟对齐 EEG 数据块和最新 gaze 样本：

```json
{
  "clock": "host_monotonic",
  "method": "sample_or_chunk_receive_time",
  "comparable": true,
  "eeg_minus_gaze_ms": 18.4,
  "absolute_skew_ms": 18.4
}
```

只有两种信号都可用时 `comparable` 才为 `true`。正偏差表示最新 EEG 数据块的
主机接收时刻晚于最新 gaze 样本。该字段适合实时融合和 policy 审计，但不等同于
硬件触发的实验室级同步。

`GET /api/gaze/frame` 返回 Tobii 场景相机最新 JPEG、尺寸、时间戳、帧年龄，以及
最近滚动时间窗中的眼动轨迹：

```json
{
  "gaze": {"x_normalized": 0.42, "y_normalized": 0.61},
  "trajectory_window_ms": 3000,
  "trajectory": [
    {"x_normalized": 0.40, "y_normalized": 0.59, "age_ms": 840},
    {"x_normalized": 0.42, "y_normalized": 0.61, "age_ms": 15}
  ]
}
```

`trajectory` 按采样时间从旧到新排列；`age_ms` 是相对场景帧接收时刻的样本年龄。
图像以 `data:image/jpeg;base64,...` 返回，可直接作为 OpenAI-compatible
多模态请求的 `image_url.url`。未收到场景帧或最新帧已超过 3 秒时返回 HTTP 503；
响应中的 `age_ms` 可用于区分尚无帧和旧帧过期。

## Screen mapping

### `GET /api/tobii/calibration`

返回 Tobii 官方佩戴校准的 `unavailable/idle/requested/running/succeeded/failed` 状态。

### `POST /api/tobii/calibration`

```json
{}
```

异步请求 `glasses.calibrate.run()`，HTTP 202 只表示请求已接受；应继续读取 GET 接口，
只有 `succeeded` 才表示眼镜接受校准。

`GET /api/screen/marker?id=10` 返回兼容用的 ArUco PNG。允许的 ID 为
`10/11/12/13`。当前实验页不绘制额外标记，而是依次使用左上 OMNI 品牌图标、右上
AI 阅读助手图标、右下“发送”和左下“下一题”作为自然界面锚点。服务端同时保留
ArUco 和旧版四色标记检测能力。

`POST /api/screen/layout` 由实验页调用，提交 viewport、标记归一化中心、可见 DOM
文字块边界、阅读区滚动位置，以及 Monitor 只读镜像所需的当前材料和对话状态。
该接口只有启动真实 Tobii provider 时可用。

`GET /api/screen/mapping` 返回动态映射状态：

```json
{
  "ok": true,
  "mapping": {
    "valid": true,
    "status": "valid",
    "screen_x_normalized": 0.42,
    "screen_y_normalized": 0.61,
    "focus_x_normalized": 0.41,
    "focus_y_normalized": 0.60,
    "homography_age_ms": 18,
    "detected_marker_ids": [10, 11, 12, 13],
    "target": {"id": "slide-3-content-2", "tag": "p", "text": "..."},
    "reading_aoi": {
      "x_min": 0.01,
      "y_min": 0.06,
      "x_max": 0.65,
      "y_max": 0.90
    },
    "trajectory": [],
    "layout": {
      "viewport": {},
      "elements": [],
      "reading_aoi": {
        "x_min": 0.01,
        "y_min": 0.06,
        "x_max": 0.65,
        "y_max": 0.90
      }
    }
  }
}
```

`status=tracking_hold` 表示当前帧短暂漏检，但仍在 250 ms 容忍时间内；
`markers_missing`、`marker_geometry_invalid`、`mapping_stale`、`layout_missing` 和
`detector_unavailable` 均不得作为有效屏幕注视点使用。`trajectory` 中每个点都使用
该 gaze 样本到达时有效的单应矩阵映射，适合观察头部移动期间的 3 秒历史轨迹。
