# Recon 实验问卷方案

## 1. 问卷范围

实验平台只呈现两类问卷：

1. 每个 Trial 完成后呈现一份即时问卷，共 4 题。
2. 每个 Condition 的 6 个 Trial 全部完成后呈现一份 Condition 问卷，共 3 题。

三个 Condition 使用完全相同的题目、顺序、说明和量表。问卷界面不显示 C1/C2/C3、
Eye、EEG、Policy 或具体触发机制。系统不再呈现主动筛选回忆题、分支题或三个 Condition
完成后的最终总问卷。

## 2. 通用实施原则

- Trial 问卷在两道理解题提交后、下一 Trial 的 10 秒静息前呈现；T06 的 Trial 问卷提交后
  再呈现 Condition 问卷。
- 所有题目必须作答后才能提交；Condition 问卷中的“不适用”是有效作答，不等同于漏答。
- “不适用”保存为 `null`，并在独立的 `notApplicable` 数组中保存题目 ID，不按量表中点计分。
- 每份问卷保存版本、题目顺序、开始和提交时间、逐题作答延迟及完整 schema 快照。
- 问卷不能通过点击遮罩或按 `Esc` 关闭；保存失败时保留当前答案并允许重试。

## 3. Trial 即时问卷

### 3.1 呈现说明

> 请只根据刚才完成的这篇材料作答。请选择最符合你实际体验的选项。

四题在同一页面呈现，不分页。当前 schema 版本为 `trial-survey-v1`。

### 3.2 Trial-Q1：心理努力

> 为了理解刚才的材料，你投入了多少心理努力？

七分制：`1 非常少`、`4 中等`、`7 非常多`。

字段：`trial_mental_effort`

### 3.3 Trial-Q2：困惑程度

> 阅读过程中，你有多大程度感到卡住，或不确定自己是否理解正确？

七分制：`1 完全没有`、`4 中等`、`7 非常强烈`。

字段：`trial_confusion`

### 3.4 Trial-Q3：当前理解

> 现在你认为自己对刚才材料的理解程度如何？

七分制：`1 完全不理解`、`4 理解一部分`、`7 完全理解`。

字段：`trial_understanding`

### 3.5 Trial-Q4：帮助需求

> 阅读过程中，你是否出现过希望获得额外解释或帮助的时刻？

分类选项：

| 值 | 标签 |
|---:|---|
| `0` | 没有 |
| `1` | 有，但需求较低 |
| `2` | 有，而且需求较高 |

字段：`trial_help_need`

### 3.6 Trial 层分析映射

| 构念 | 字段 | 主要外部参照 |
|---|---|---|
| 心理努力 | `trial_mental_effort` | EEG workload proxy |
| 困惑 | `trial_confusion` | Eye + EEG Policy、被试响应 |
| 主观理解 | `trial_understanding` | 理解题正确率 |
| 帮助需求 | `trial_help_need` | Policy 触发、接受和拒绝日志 |

`trial_help_need` 可以用于描述 Policy 的潜在命中、漏检或误触发，但不能单独作为困难状态的
客观真值。应同时结合客观理解题、人工提问、Policy 日志和信号质量进行分析。

## 4. Condition 结束问卷

### 4.1 呈现说明

> 系统在不同任务中可能采用不同的辅助方式。有些辅助由你主动发起，有些可能由系统询问，也可能没有出现相关互动。请只根据刚刚完成的整轮任务作答。若没有相关体验，请选择“不适用”。

三题在同一页面呈现。统一使用七分制：`1 完全不同意`、`4 中立`、`7 完全同意`，
并允许选择“不适用”。当前 schema 版本为 `condition-survey-v3`。

### 4.2 Condition-Q1：需求匹配

> 本轮 AI 辅助回应了我真正需要理解的内容。

字段：`assistance_need_fit`

### 4.3 Condition-Q2：清晰度

> 本轮 AI 提供的解释清楚易懂。

字段：`assistance_clarity`

### 4.4 Condition-Q3：个性化

> 本轮 AI 辅助符合我当时具体的阅读情况，而不是提供泛泛的解释。

字段：`assistance_personalization`

## 5. 题量

| 问卷 | 次数 | 每次数量 | 三个 Condition 的总数量 |
|---|---:|---:|---:|
| Trial 即时问卷 | 每个 Trial 一次 | 4 | `3 × 6 × 4 = 72` |
| Condition 问卷 | 每个 Condition 一次 | 3 | `3 × 3 = 9` |
| 总计 | - | - | 81 |

## 6. 数据编码

- 七分量表保存整数 `1..7`。
- Trial 帮助需求保存整数 `0..2`。
- Condition 问卷的“不适用”在 `answers` 中保存为 `null`，同时把字段 ID 写入
  `notApplicable[]`。
- 所有合成分数均在分析阶段生成；原始记录保留每道题的单项答案。

## 参考

Danry, V., Hernandez, J., Wilson, A., Maes, P., & Amores, J. (2026). *From Gaze to
Guidance: Interpreting and Adapting to Users' Cognitive Needs with Multimodal Gaze-Aware
AI Assistants*. arXiv:2604.08062. https://arxiv.org/abs/2604.08062
