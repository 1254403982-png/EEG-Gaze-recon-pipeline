# 原始脑电数据存储说明

本文说明当前 Condition-scoped run 中 BrainCo 原始 EEG 的格式。完整 run 的其他文件
见 [DATA_SCHEMA.md](DATA_SCHEMA.md)。

## 启用与开始时机

原始 EEG 记录与内部 BrainCo acquisition worker 绑定：

```powershell
python -m recon_pipeline.cli --config configs/development.json --brainco
```

同时连接 Tobii 时使用：

```powershell
.\run_tobii.ps1 -BrainCo
```

服务启动后的 `development` 状态不会创建正式文件。被试点击开始、
`POST /api/session/start` 建立正式 session，并进入 T01 前 `rest_calibration` 后才落盘。

当前主流程配置为：

```json
{
  "storage": {
    "run_dir": "runs",
    "raw_eeg_chunk_seconds": 10.0,
    "recording_starts_at": "calibration"
  }
}
```

## 目录结构

EEG 位于本次 Condition 目录的 `eeg/` 中，不再单独写入 `runs/raw_eeg`：

```text
runs/S001_condition_3_20260724_160000_123456/
  metadata.json
  experiment.json
  eeg/
    metadata.json
    manifest.jsonl
    features.jsonl
    chunks/
      chunk_000000.npz
      chunk_000001.npz
```

`eeg/metadata.json` 保存初始通道布局、采样率、数据类型、来源、分块时长，以及主机
逐样本时间的重建方法。

`eeg/manifest.jsonl` 每行对应一个已完成块，记录：

- session、trial、Condition 和 UI phase；
- 通道名、采样率、样本数、数据类型和来源；
- 首末 SDK chunk 的主机时间与设备时间；
- 原 acquisition chunk 数量、相对文件路径和 SHA-256；
- 文件实际写入时间。

一个 NPZ 不会跨越 session、trial、Condition、phase、通道布局、采样率、来源或
数据类型边界。上下文变化会提前写出未满 10 秒的块。

## NPZ 字段

每个 `.npz` 可独立读取，不依赖 Python pickle：

| 字段 | 含义 |
|---|---|
| `schema_version` | 当前原始 EEG schema 版本 |
| `samples` | SDK 返回的采集级数据，形状为 `channels × samples` |
| `device_timestamps` | 每个样本的设备时间；设备未提供时为 `NaN` |
| `host_timestamps_ns` | 按采样率从 SDK chunk 主机接收时刻向前反推的逐样本单调时间 |
| `channel_names` | 原始通道名称 |
| `sampling_rate_hz` | 采样率 |
| `session_id` / `trial_id` | 当前被试 session 与 trial |
| `condition` / `phase` | 当前实验条件与界面阶段 |
| `source` | 数据来源 |
| `source_chunk_offsets` | 各 SDK chunk 在本 NPZ 中的起始样本位置 |
| `source_chunk_host_monotonic_ns` | 各 SDK chunk 到达主机的单调时钟 |
| `source_chunk_host_utc` | 各 SDK chunk 到达主机的 UTC |
| `source_chunk_device_seconds` | SDK chunk 携带的设备时间 |

这里的“原始”表示 BrainCo SDK 返回后、Recon 通道映射和滤波之前的数据。Recon 目前
不会把 SDK 数值自动换算或标记为伏特/微伏。

`host_timestamps_ns` 是基于固定采样率的主机到达时间重建，不是硬件为每个样本提供的
时间戳。它适合与同一进程中的 gaze/交互事件做秒级对齐，但不等于外部 TTL 同步。

## 读取示例

```python
from pathlib import Path

import numpy as np

run = Path("runs/S001_condition_3_20260724_160000_123456")
sample_parts = []
host_time_parts = []
device_time_parts = []

for path in sorted((run / "eeg" / "chunks").glob("chunk_*.npz")):
    with np.load(path, allow_pickle=False) as chunk:
        sample_parts.append(chunk["samples"])
        host_time_parts.append(chunk["host_timestamps_ns"])
        device_time_parts.append(chunk["device_timestamps"])

samples = np.concatenate(sample_parts, axis=1)
host_timestamps_ns = np.concatenate(host_time_parts)
device_timestamps = np.concatenate(device_time_parts)
print(samples.shape, host_timestamps_ns.shape, device_timestamps.shape)
```

离线分析前先逐行读取 `eeg/manifest.jsonl`，验证文件存在、SHA-256 一致，并使用其中的
trial/phase 边界。不要只靠文件名、块序号或近似时长推断实验阶段。

## 原始波形与特征的区别

- `eeg/chunks/*.npz`：滤波前的 32 通道采集值，适合重新预处理和离线分析。
- `eeg/features.jsonl`：实时 4 秒滚动窗口的质量与 decoder 输出，为降采样后的派生数据。
- `experiment.json.trials[].loadSamples`：浏览器约每 1.5 秒保存的界面层 load 采样，
  不能替代前两者。

正式分析需要说明使用哪一层数据、窗口长度、重叠方式、坏导规则和缺失处理，且不能把
高频重叠窗口当作相互独立的被试样本。
