67# 使用说明

## 实验用时记录

实验页在完成首次 10 秒静息校准后开始记录本次 Condition 的总用时。`experiment.json` 中的 `meta.experimentStartTime` 和 `meta.experimentEndTime` 是 epoch 毫秒，`startISO` 和 `endISO` 是便于核对的 ISO 时间，`totalDurationSec` 是两者相差的秒数。每个 Trial 另有自己的 `startTime`、`endTime` 和 `durationSec`。

页面显示使用 `M:SS`；超过 1 小时使用 `H:MM:SS`。断点恢复会兼容旧记录中的 ISO 字符串、epoch 秒和无效的 `0` 值，并从校准或首个 Trial 的时间回退恢复。服务端只保存事件日志的 run 如果没有生成 `experiment.json`，只能根据 `events.jsonl`/`interactions.jsonl` 核对已记录的时间，不能补出浏览器未提交的完整 Condition 结束时间。

本文档说明如何启动 Recon 脑电处理流水线、连接 BrainCo 32 通道脑电帽和 Tobii Pro Glasses 3，以及如何配置解码器和判断实验条件。逐文件字段和离线连接见
[DATA_SCHEMA.md](DATA_SCHEMA.md)；正式研究与统计设计见
[CHI_STUDY_PLAN.md](CHI_STUDY_PLAN.md)。

## 1. 数据通路

```text
BrainCo 32 通道原始 EEG
        |
        +--> 原始数据分块保存
        |
        +--> 全通道滤波、PSD 与质量评估
                    |
                    +--> posterior_alpha 解码器（默认选后部通道）
                    +--> 后续新增解码器（各自选择通道与输出指标）
                                      |
Tobii gaze2d --> 屏幕映射 --> 3 个 Eye 指标 --> 个人基线 --+
                                                              +--> 策略 --> 实验平台/界面
EEG 指标 -----------------------------------------------------+
```

采集和预处理层始终保留设备提供的完整通道。具体使用哪些通道、计算哪些指标，由每个解码器独立决定。

## 2. 安装

以下流程已经在 Windows、Python 3.10、BrainCo SDK 0.5.0 和 Tobii Pro
Glasses 3 上完成真机验证。新电脑建议严格按顺序执行。

项目代码支持 Python 3.10–3.13，但当前 Tobii `g3pylib` 依赖组合推荐固定使用
64 位 Python 3.10。每台电脑都应在仓库根目录重新创建 `.venv-win`，不要复制或
复用其他电脑以及 Linux/macOS 创建的 `.venv`。

### 2.1 创建 Windows 环境

打开 PowerShell，进入包含 `pyproject.toml` 的仓库根目录：

```powershell
cd 'D:\Users\EDY\Desktop\EEG+Gaze\recon_pipline'
py -3.10 -m venv .venv-win
Set-ExecutionPolicy -Scope Process Bypass
.\.venv-win\Scripts\Activate.ps1
python --version
```

`python --version` 应显示 `Python 3.10.x`。如果 `py -3.10` 不存在，先安装
64 位 Python 3.10，并在安装器中启用 Python Launcher。

仓库迁移后如果已经存在不可用的 `.venv-win`，删除并重建：

```powershell
deactivate 2>$null
Remove-Item .venv-win -Recurse -Force
py -3.10 -m venv .venv-win
.\.venv-win\Scripts\Activate.ps1
```

### 2.2 配置 pip 并安装 Recon + BrainCo

如果可以正常访问官方 PyPI：

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev,brainco]"
```

如果 `pypi.org` 出现 `SSLEOFError`，在当前 PowerShell 窗口临时使用阿里云镜像：

```powershell
Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY -ErrorAction SilentlyContinue
$env:PIP_INDEX_URL = 'http://mirrors.aliyun.com/pypi/simple/'
$env:PIP_TRUSTED_HOST = 'mirrors.aliyun.com'
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev,brainco]"
```

验证 BrainCo 环境：

```powershell
python -c "import bc_ecap_sdk, zeroconf, numpy, scipy; print('BrainCo environment OK')"
python scripts\diagnose_brainco.py --timeout 8
```

看到 `BrainCo acquisition started` 或诊断脚本显示设备地址、TCP 可达和数据回调，
说明 BrainCo 采集链路正常。

### 2.3 安装 Tobii 兼容依赖

不要直接安装 `.[tobii]`。官方 g3pylib 0.3.1-alpha 声明的 `av~=10.0.0`
在 Python 3.10/Windows 上没有可用 wheel，pip 会退回源码编译并在 Cython/PyAV
阶段失败。当前真机验证通过的组合是：

- `g3pylib`：官方 Tobii 仓库提交 `5868e2d327a077cb6bbe276182188b81fc90f224`
- `aiortsp`：官方依赖仓库 master（验证提交 `16b0e084e2520759ed32ff1dd911d82db84b8f34`）
- `av==12.3.0`
- `websockets~=10.3`、`aiohttp~=3.8.1`、`zeroconf~=0.47.1`

按以下顺序安装，`--no-deps` 用于阻止 g3pylib 把 PyAV 降回无法构建的版本：

```powershell
python -m pip install "av==12.3.0" --only-binary=:all:
python -m pip install "Pillow>=9" "websockets~=10.3" "aiohttp~=3.8.1" "zeroconf~=0.47.1"
python -m pip install --force-reinstall --no-deps `
  "aiortsp @ git+https://github.com/m4reko/aiortsp@master"
python -m pip install --no-deps `
  "g3pylib @ git+https://github.com/tobii/glasses3-pylib.git@5868e2d327a077cb6bbe276182188b81fc90f224"
```

必须使用 aiortsp 的 GitHub master。PyPI 的 `aiortsp 1.4.0` 缺少
`MediaStreamConfiguration`，会导致 g3pylib 导入失败。

验证完整环境：

```powershell
python -c "import av; from aiortsp.rtsp.session import MediaStreamConfiguration; from g3pylib import connect_to_glasses; print('Tobii environment OK, PyAV', av.__version__)"
python -m pytest -q
```

验证输出应包含 `Tobii environment OK, PyAV 12.3.0`，并且项目测试应全部通过。
由于主动使用 PyAV 12.3.0 兼容方案，`pip check` 可能继续报告
g3pylib 的 `av~=10.0.0` 元数据冲突。导入和短时真机 RTSP 成功只说明所用 API
能够运行，不能证明长时间 H.264 解码稳定；正式收数前必须完成至少一轮覆盖完整
Condition 时长的稳定性测试。Recon 默认使用 RTSP-over-TCP，减少 UDP 丢包或乱序后
不完整视频单元进入 PyAV/FFmpeg 的概率。

### 2.4 安装故障速查

| 报错 | 原因 | 处理 |
|---|---|---|
| `No Windows Python environment found` | 启动脚本未找到解释器 | 确认 `.venv-win\Scripts\python.exe` 存在，或传入 `-Python` |
| `av\logging.pyx` / `CompileError` | pip 正在源码编译旧 PyAV | 安装 `av==12.3.0 --only-binary=:all:`，不要安装 `av~=10` |
| `No module named websockets` | g3pylib 使用 `--no-deps` 安装后缺依赖 | 执行 2.3 中 websockets/aiohttp/zeroconf 安装命令 |
| `cannot import MediaStreamConfiguration` | 安装了 PyPI aiortsp 1.4.0 | 用 GitHub master 强制覆盖 aiortsp |
| `Could not connect to github.com:443` | GitHub 下载中断 | 恢复访问后重试两条 GitHub 安装命令；已构建 wheel 通常会被 pip 缓存 |
| `Ignoring invalid distribution -recon-eeg-pipeline` | 仓库包含 macOS `._*` 元数据 | 删除 `src\._recon_eeg_pipeline.egg-info` 后重装项目 |
| 无 Python traceback，程序直接回到 PowerShell | Python 原生扩展发生进程级崩溃 | 查看本节“原生崩溃排查”，不要把它当成正常断流 |

清理无效 macOS 元数据的安全命令：

```powershell
Remove-Item -LiteralPath "src\._recon_eeg_pipeline.egg-info" -Force -ErrorAction SilentlyContinue
python -m pip uninstall recon-eeg-pipeline -y
python -m pip install -e ".[dev,brainco]"
```

### 2.5 真机依赖说明

BrainCo 现需要 `bc-ecap-sdk>=0.5,<0.6`。SDK 0.5.0 的 Windows wheel 已发布到
PyPI 官方源；部分镜像同步延迟时会只显示到 0.4.5。Recon 默认只启用实验所需 EEG，
按 `start_data_stream -> set_eeg_config -> start_eeg_stream` 启流，避免把未使用的 IMU 帧
混入同一传输。只有将 `configs/development.json` 的 `eeg.brainco.enable_imu` 显式设为
`true` 时才使用 SDK 0.5+ 的统一 `ECapClient.start_stream(...)` 同时启动 EEG 与 IMU。

Windows 上 SDK 0.5.0 的原生 `mdns_start_scan()` 可能阻塞且无法被 asyncio 取消；
Recon 因此优先使用 `zeroconf` 解析 `_brainco-eeg._tcp.local.`，再使用 SDK 扫描作后备。
可用 `python scripts/diagnose_brainco.py --timeout 10` 检查 SDK 原生发现；如该命令卡住，
不代表 Zeroconf 回退不可用。

Tobii 官方 `g3pylib` 未发布到 PyPI，项目从迁移后的官方 GitHub 仓库安装，
并锁定提交 `5868e2d327a077cb6bbe276182188b81fc90f224`以保证可复现。
因为该 SDK 官方只支持 Python 3.10，旧的 Python 3.9 `.venv-win` 必须重建；
不要在 3.9 环境中继续强制安装。

### 2.6 环境变量

LLM 代理功能需要百炼 API Key；不使用 LLM 时可不配置：

```powershell
$env:DASHSCOPE_API_KEY = '你的 API Key'
```

凭据不应写入文档、代码或 Git 提交。

## 3. 启动方式

推荐在 `recon_pipline` 目录执行：

```powershell
cd 'D:\Users\EDY\Desktop\EEG+Gaze\recon_pipline'
```

复制到其他电脑后，将上面的路径替换为新电脑上包含 `pyproject.toml` 和
`run_tobii.ps1` 的实际目录。

`run_tobii.ps1` 会自动优先使用仓库根目录的
`.venv-win\Scripts\python.exe`，不再依赖某台电脑的固定 Miniconda 路径。

不连接硬件，只启动平台：

```powershell
python -m recon_pipeline.cli --config configs/development.json
```

只连接 BrainCo：

```powershell
python -m recon_pipeline.cli --config configs/development.json --brainco
```

只连接 Tobii：

```powershell
.\run_tobii.ps1
```

同时连接 BrainCo 与 Tobii：

```powershell
.\run_tobii.ps1 -BrainCo
```

默认使用 Tobii RTSP-over-TCP。启动日志应出现 `Tobii RTSP transport: TCP` 和
`receiving interleaved RTP`。仅在设备明确拒绝 TCP、并完成短时诊断后才临时回退 UDP：

```powershell
.\run_tobii.ps1 -BrainCo -TobiiRtspTransport udp
```

需要使用其他 Python 环境时，可显式指定：

```powershell
.\run_tobii.ps1 -BrainCo -Python 'C:\path\to\python.exe'
```

如果 PowerShell 报“禁止运行脚本”，这是执行策略问题，不是路径问题。
可先仅对当前进程放行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

> Windows PowerShell 5.1 会将无 BOM 的 UTF-8 `.ps1` 按本地代码页解析。
> 为避免中文字节导致脚本语法误判，启动脚本的运行时错误消息使用 ASCII，
> 中文说明统一维护在本文档中。

Tobii 自动发现不稳定时，可以显式指定设备 hostname 或 IP：

```powershell
.\run_tobii.ps1 -BrainCo -TobiiHostname 169.254.217.102
```

BrainCo 的 SDK 适配代码已集成到本项目，不再需要传入 `../oi-armi/oi-mi` 路径。

### 3.1 中断后继续实验

实验页会把当前 Condition 的浏览器状态保存到 localStorage 键
cogload_experiment_data，正常实验中约每 2 秒保存一次，切换页面或关闭页面前也会尝试
保存。保存内容包括当前 phase、Trial、已完成的理解题/Trial 问卷、对话记录、Policy 记录和
服务端 run 时间戳；服务端正式文件仍以 runs/<subject>_condition_<n>_<stamp>/ 为准。

重新打开实验页后输入相同被试编号并选择相同 Condition，页面会显示“发现未完成的实验记录”。
选择“继续实验”会复用原 run 目录，已完成的 Trial 不会重做；如果中断发生在正在阅读、答题
或问卷中，该 Trial 会从头重做，以免留下半个 Trial。选择“开始新的实验”会明确丢弃本地断点并
建立新的 run。浏览器本地存储被清空、换了浏览器或换了电脑时，无法仅凭页面恢复断点。

如需脚本侧恢复同一正式 run，POST /api/session/start 可带已有目录时间戳的 resume_stamp；
服务端响应中的 run_stamp 应保存回实验数据。只有时间戳格式正确且对应目录仍存在时才会复用，
否则会新建目录。

## 4. 页面与状态接口

启动后访问：

| 地址 | 用途 |
|---|---|
| `http://127.0.0.1:8810/` | 导航页 |
| `http://127.0.0.1:8810/experiment` | 实验平台 |
| `http://127.0.0.1:8810/monitor` | 脑电、眼动、策略实时监控 |
| `http://127.0.0.1:8810/api/health` | 设备连接和服务健康状态 |
| `http://127.0.0.1:8810/api/state` | 当前融合状态和实验条件 |
| `http://127.0.0.1:8810/api/policy` | 最新策略结果 |

在 PowerShell 中快速检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8810/api/health
Invoke-RestMethod http://127.0.0.1:8810/api/state
Invoke-RestMethod http://127.0.0.1:8810/api/policy
```

`/api/state` 返回值里的 `state.condition` 是后端实际采用的实验条件；不要只根据前端按钮或页面显示判断。PowerShell 可直接运行：

```powershell
(Invoke-RestMethod http://127.0.0.1:8810/api/state).state.condition
```

## 5. 实验条件含义

| 实验条件 | 策略可使用的数据 |
|---|---|
| C1 / `1` | 不使用 EEG 或 Eye，Policy 始终不触发 |
| C2 / `2` | 使用三个核心 Eye 指标，并在有数据时加入回视次数/时间；Eye 缺失时保持 `hold` |
| C3 / `3` | Eye + EEG；EEG 低质量时显式降级为 Eye-only，Eye 缺失时保持 `hold` |

实验平台有两条相互独立的 AI 对话通路：

- 人工通路：C1、C2、C3 均可先选择“简单解释 / 举例子 / 详细解释”，再把选中的材料粘贴到输入框并点击发送。解释按钮只选择档位，不会直接调用 LLM；只有答题、静息或正在等待 AI 回复时暂时禁用。
- Policy 通路：Eye/EEG 指标触发后，AI 先询问被试是否对当前材料感到疑惑。“需要帮助 / 不需要”按钮显示在被试一侧的气泡中；选择后，AI 询问气泡和被试回答都会保留。只有选择“需要帮助”才调用 LLM，选择“不需要”只记录拒绝。

自动询问出现后，被试保持头部和身体姿势，直接点击气泡中的“需要帮助”或“不需要”按钮
进行确认。页面任意位置的鼠标左键、右键不再代表选择，输入框、正文选择和右键菜单保持
正常行为。选择“需要帮助”后等待 AI 回复；AI 回复出现后再自然阅读，需要继续阅读材料时
将视线移回左侧正文即可。正文仍可用 `PageUp/PageDown` 翻动。

当前配置不限制每个 trial 的自动询问次数（`max_automatic_offers_per_trial=0` 表示无限制）。
被试选择“需要帮助”或“不需要”后，当前证据 episode 会结束；同一题后续出现新的持续困难证据时，
可以再次询问，不同档位仍需重新满足 Policy 证据。没有持续困难证据的 trial 不会为了凑次数而
提问。材料开始后的前 20 秒是阅读起始保护窗，Policy 不会弹窗；可执行触发会由服务端保留
到页面领取，Policy 轮询间隔为 400 ms。

进入答题弹窗后，人工输入、难度按钮、发送按钮、F10 和自动 Policy 触发均被禁用；Policy 后端也会对 `quiz`、`rest`、`calibration`、问卷和反馈阶段输出 `no_adaptation`。下一篇材料进入 `reading` 阶段后才重新启用 AI。

人工消息在用户气泡中显示为“解释档位：粘贴内容”。三档约束如下：

| 档位 | 输出约束 |
|---|---|
| 简单解释 | 被试主动粘贴时先回答理解缺口；Policy 主动询问时先回答定位区域；均使用 2–4 句、90–180 个中文字符补足一个关键术语、机制或因果联系，不举例、不类比 |
| 举例子 | 一句指出缺失联系，再给一个材料中没有出现过的具体、形象例子，最后说明对应关系 |
| 详细解释 | 使用编号从前提开始逐层拆解概念、条件、因果和推导，每一步只解决一个小问题，不举例、不复述全文 |

三档都会把当前页面完整材料和被试粘贴内容送给 LLM。提示词要求模型先区分材料已有
信息与尚未讲清的信息，只对后者进行增量解释。等待模型返回时，对话区显示旋转进度环
并暂时禁止重复发送。

模型返回后，前端会检查简单解释的长度、完整句数量以及是否含有举例或类比。输出不满足
上述契约时，系统会携带上一版回答自动请求模型重写，并复验重写结果，最多自动重写两次；
若仍不理想则保留最完整的回答，不阻断人工或 Policy 对话。

`F10` 用于人工模拟一次 Policy trigger，同样只显示确认气泡，不会绕过被试确认直接调用 LLM。

### 5.1 选择 Condition 与运行顺序

每次实验只运行一个 Condition。主试在被试开始前点击实验首页右上角的研究者设置按钮
（或按 `Ctrl+Shift+S`），在“本次实验 Condition”中选择 C1、C2 或 C3并保存。
选择会保存在本机浏览器中，但每次正式开始前仍应由主试核对。

同一被试需要分别进入 3 次实验，每次 6 个 trial。Condition 顺序由主试在实验外部按
研究设计确定，例如本次选择 C2，完成并结束后重新进入页面，再选择下一 Condition。
实验中途不要调用 `/api/condition` 切换条件。

每个 Condition 的固定流程为：

```text
选择 Condition -> 输入同一被试编号 -> T01 前静息 10 秒
-> T01 -> 答题 -> Trial 即时问卷 -> T02 前静息 10 秒 -> ...
-> T06 -> 答题 -> Trial 即时问卷 -> Condition 问卷 -> 保存并结束 session
```

C2/C3 在首题进入 `reading` 后，用最初 10 秒有效屏幕映射数据建立本次 Condition 的
个人 Eye 基线；每个 Trial 材料开始后的前 20 秒均为阅读起始保护窗，期间 Policy 输出
`hold`，不会询问被试。屏幕映射还必须在阅读元素附近形成持续停留，才允许将该区域作为
触发候选，避免刚开始看前文时弹出后文问题。个人基线完成后供本次
6 个 trial 共用，下一次 Condition/session 会重新建立。每题前的 10 秒纯白静息阶段
用于实验分段和 EEG 静息记录，不是 Eye 个人基线，也不参与 Eye ratio 计算。

每次从低、中、高难度各随机抽 2 题。题目首次呈现时，题号会同时写入浏览器记录和
`runs/_subject_question_history.json`；后续用相同被试编号开始实验时会排除所有已呈现
题目。因此三次 Condition 不会重复。被试编号大小写不影响匹配；不要为同一被试临时
更换编号，也不要在实验过程中删除题目历史文件。

高难度题库（ID 33–48）不采用定义原句复述作为主要考查方式。材料包含边界条件、变量
关系、机制失效或模型局限。正文纯文本控制在约 750–950 字符，与“正当防卫的界限与
特殊防卫”的信息量接近。两道题都要求理解全文主线、概念关系、适用边界或证据链，不设置
数值计算题，也不只抽取单个段落中的术语。正确选项可由当前材料推出，不要求被试依赖材料
之外的专业记忆。

材料载入后会按左侧实际可视高度检查是否超过一屏。只有发生溢出时才依次收紧段落间距和
行距，不缩小字号；适配成功后隐藏正文滚动条。若极端窗口尺寸下仍无法完整容纳，系统保留
滚动作为兜底而不会裁切文字。正式实验应保持预定屏幕分辨率和浏览器缩放比例。

每个 Trial 的两道理解题提交后都会呈现 4 题即时问卷，依次记录心理努力、困惑程度、
当前理解和阅读期间的帮助需求。前三题使用 1–7 分，帮助需求使用 `0/1/2` 分类；4 项全部
选择后才能进入下一次静息或 Condition 问卷。

T06 的即时问卷完成后呈现 Condition 问卷。C1/C2/C3 使用完全相同的标题、题目、顺序和
量表，被试界面不显示 Condition 编号、EEG、gaze、Policy 或主动触发方式。Condition 问卷
只包含需求匹配、清晰度和个性化 3 题，均使用 1–7 同意度并允许选择“不适用”。系统不再
呈现主动筛选回忆题、分支题或三个 Condition 完成后的最终总问卷。

问卷不能通过点击遮罩或按 `Esc` 关闭。提交期间显示“正在保存”，只有问卷和实验数据保存
成功才进入后续阶段，保存失败时问卷保持打开并允许重新提交。Trial 问卷版本为
`trial-survey-v1`，Condition 问卷版本为 `condition-survey-v3`；开始/提交时间、总耗时、
逐题作答时间、题目顺序和题目快照会随 `experiment.json` 保存。

## 6. 配置 32 通道处理和解码器

配置文件为 `configs/development.json`。核心结构：

```json
{
  "eeg": {
    "sampling_rate_hz": 250.0,
    "window_seconds": 4.0,
    "max_buffer_seconds": 90.0,
    "bandpass_low_hz": 1.0,
    "bandpass_high_hz": 45.0,
    "primary_decoder": "posterior_alpha",
    "decoders": [
      {
        "id": "posterior_alpha",
        "type": "posterior_alpha",
        "channels": ["P3", "P4", "P7", "P8", "PZ", "O1", "O2"],
        "options": {}
      }
    ]
  }
}
```

- 预处理和质量评估覆盖 BrainCo 返回的全部 32 通道。
- `channels` 只控制该解码器使用哪些通道，不会裁剪采集数据。
- `primary_decoder` 的标准结果会映射到现有 `EEGFeatures` 字段，保持策略和界面兼容。
- 所有解码器的完整输出位于 EEG 事件的 `metadata.decoder_outputs`。
- 新解码器在 `src/recon_pipeline/eeg/decoders/` 中实现并注册，无需修改采集层。
- 若新解码器被设为 `primary_decoder`，它应提供现有策略所需的标准指标名；只作为附加解码器时可以使用任意新的指标名。

默认后部 Alpha 解码器使用设备真实存在的 `P3/P4/P7/P8/PZ/O1/O2`，不再用相邻通道合成 NeuroDock 的 PO3、PO4、Oz。

## 7. BrainCo 连接配置

`eeg.brainco` 中可配置：

```json
{
  "address": "",
  "port": 0,
  "auto_discover": true,
  "device_id": "eeg-cap",
  "scan_timeout_seconds": 6.0,
  "ready_timeout_seconds": 10.0,
  "start_retries": 2,
  "gain": 6,
  "signal_source": "NORMAL"
}
```

默认通过 mDNS 自动发现。已知设备地址时可填写 `address` 和 `port`，用于跳过发现过程。若 TCP 已连接但持续收不到 EEG，请优先核对设备电量、SDK/固件兼容性、`device_id` 和采样配置。

注意：`llm/20260706211132/.../oi-mi/acquisition/brainco_acquirer.py` 是独立 `oi-mi` 副本，只有运行该副本的入口时才会由其 `acquisition/factory.py` 调用。当前 Recon 服务使用 `src/recon_pipeline/acquisition/brainco_sdk.py`，两处均已适配 `bc_ecap_sdk` 0.5 的统一启流接口。

## 8. 数据保存

服务启动但仍处于 `development` 时不会创建正式实验数据。被试点击开始并进入 T01 前
静息阶段后，当前单 Condition 的所有数据写入同一个目录：

```text
runs/<被试编号>_condition_<1|2|3>_<实验时间>/
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

`eeg/chunks` 保存滤波和解码前的原始 32 通道数据。每个样本包含按采样率反推的
`host_timestamps_ns`，每个设备 chunk 仍保留接收时刻和设备时间，格式与恢复方法见
[RAW_EEG.md](RAW_EEG.md)。

`gaze/raw_samples.jsonl` 保存每个 Tobii `gaze2d` 样本、主机接收时间、设备时间、
场景归一化坐标和当时的屏幕映射结果。`gaze/features.jsonl` 的 `eye` 字段保存阅读
AOI 停留秒数、fixation 数量和平均 fixation 秒数；`eeg/features.jsonl` 与
`gaze/features.jsonl` 都是滚动窗口聚合指标，不能替代原始信号。

`policy/decisions.jsonl` 在决策状态变化时立即写入；C1 的 `no_adaptation` 也会记录，
完全相同的状态最多每秒写
一次，并不保存每次内部 evaluate 调用。`component_scores` 包含个人 baseline、
三个实时 ratio、Eye level、EEG level 和 C3 融合分；`sources_used` 使用 `eye`/`eeg`
区分实际参与决策的来源，低质量 EEG 降级时另有 `degraded_mode`。

`interactions.jsonl` 记录 trial/静息/答题/人工提问/Policy 确认/LLM 请求、Trial 问卷和
Condition 问卷等操作，
统一使用服务端 `host_monotonic_ns`，并附带当时 EEG-gaze 主机接收时间差。
`experiment.json` 保存 6 个 trial、聊天、答题、每个 trial 的即时问卷和 Condition 问卷汇总。

对话内容保存两份：`experiment.json` 的 `trials[].chatMessages[]` 按 trial 汇总；
`interactions.jsonl` 的 `action=conversation_message` 按发生时间逐条保存。后者字段包括
`role`、完整 `content`、`messageType`、`explanationLevel`、`policyId` 和 `source`：

| `source` | 含义 |
|---|---|
| `manual` | 被试选择解释档位、粘贴并主动发送 |
| `policy` | C2/C3 Policy 自动提出帮助询问后形成的对话 |
| `f10` | 主试按 F10 人工模拟 Policy trigger |

Policy 的询问、被试“需要帮助/不需要”回答和随后 AI 回复使用相同 `policyId` 关联；
人工通路的 AI 回复明确写入 `triggerSource=manual`，不会与自动通路混在一起。

实时 Policy 视觉定位使用最近 3 秒有效眼动样本：场景帧中的红色折线和黄色采样点表示时间窗轨迹，末端红色准星表示最新位置。视觉模型同时接收轨迹、场景图和当前材料，优先依据轨迹聚集/停留区域推测被试在看哪里，不再只依赖单帧单点。时间窗由 `TobiiGazeFeatureExtractor(window_seconds=3.0)` 控制。

视觉定位发生时，前端会把当时的场景帧和轨迹缓存为 `frameSnapshot`。被试随后选择“需要帮助”
时，解释 LLM 复用这份触发时快照，不会重新抓取被试视线已经移到右侧对话区后的新帧。
`frameSnapshot` 只在当前待确认对象中以内存传递；写入 `trial.policySuggestions` 时会剥离图像，
避免把 base64 场景图塞入 `experiment.json`。

### Tobii 佩戴校准

实验页面中的 10 秒“静息校准”用于实验分段和记录静息数据，**不会校准 Tobii 眼镜的
眼模型，也不是 Policy 的 Eye 个人基线**。Eye 个人基线来自首题最初 10 秒有效阅读。
Tobii Pro Glasses 3 的佩戴校准使用官方 Glasses 3 WebSocket API：
`glasses.calibrate.run()`。当前服务将该官方调用暴露为：

- `GET /api/tobii/calibration`：读取 `idle/requested/running/succeeded/failed` 状态。
- `POST /api/tobii/calibration`：异步启动一次官方校准。
- Monitor 眼动映射页的 `Tobii 校准` 按钮：调用同一接口。

校准前让被试正确佩戴眼镜并注视 Tobii 官方校准卡/校准目标中心，确认
`gaze_connected=true` 后再点击按钮；状态变为 `succeeded` 才表示设备接受校准。
如果使用 Tobii Controller/官方连接应用校准，应先停止 Recon 的 Tobii 采集进程，避免两个
校准客户端同时操作设备；完成后再启动 Recon。校准失败时先检查眼镜位置、瞳孔是否被镜框
或头发遮挡、校准卡是否完整进入场景相机视野以及光照反射。

### 动态屏幕映射

主实验页不再绘制额外的彩色标定块，而是使用四个原有界面元素作为 ID `10/11/12/13`
的自然锚点：左上角 OMNI 品牌图标、右上角 AI 阅读助手图标、右下角“发送”和左下角
“下一题”。服务端联合检测左上橙色品牌、三个蓝色控件和它们形成的屏幕四边形，避免
正文中的蓝色公式或对话内容被单独误识别。ArUco 与四色检测仍作为旧版兼容能力保留，
`/api/screen/marker` 接口也没有删除，但当前实验页不会显示它们。

实验页每 1.5 秒或布局变化时，将 viewport、四个标记中心和当前可见文字块边界发送到
`POST /api/screen/layout`。Tobii provider 约每 40 ms 尝试检测一次标记，并为当前场景帧
计算动态单应矩阵。自然锚点必须形成符合左上、右上、右下、左下顺序的屏幕四边形。
自然控件颜色短暂丢失时，系统使用画面中的显示器物理边界和浏览器上报的控件位置作为
后备映射，不需要重新显示彩色块。只有自然锚点或屏幕边界检测成功，或者距离最近一次成功检测
不超过 250 ms，才输出有效屏幕坐标。每个 gaze 样本使用它到达时的单应矩阵进行映射，
并保存最近 3 秒的屏幕轨迹；不会用当前矩阵重算历史点，因此头部移动不会拖动旧轨迹。
映射输出位于 gaze 的 `metadata.screen_mapping`，完整布局和实时轨迹可在
`GET /api/screen/mapping` 和 Monitor 页面查看。

真机检查时让实验页保持在主实验界面，然后确认 Monitor 中：

1. `Screen Map` 为 `Mapped`。
2. 标记 `10/11/12/13` 全部变绿。
3. `homography_age_ms` 通常低于 250 ms。
4. 头部移动时屏幕轨迹仍落在相同的实验文字区域附近。

真机使用时建议将实验页最大化或全屏，并让场景相机完整看到这四个界面元素。自然界面
锚点对被试干扰更小，但其检测余量低于专用 ArUco 标记；若 Monitor 中四个 ID 不能持续
变绿，应先调整相机角度、屏幕亮度和拍摄距离。

映射失败时系统保留场景坐标，但不会虚构屏幕坐标。`gaze/raw_samples.jsonl` 的
`screen_mapping` 字段同时保存每个原始样本当时的映射结果和质量。

Tobii provider 分别监视 gaze 与 scene RTP；任一轨道连续 5 秒没有新数据时会清空旧场景帧、
关闭旧会话并自动重连。`GET /api/gaze/frame` 对超过 3 秒的旧帧返回 HTTP 503，Monitor
因此不会把冻结画面继续显示成实时视频。实验期间只运行一个 `recon_pipeline.cli --tobii`
实例；多个实例会争抢同一设备的 UDP/RTSP 流，并可能同时复用 8810 端口。

当前默认把 gaze 与 scene RTP 作为 RTSP-over-TCP 的 interleaved 数据接收，避免 UDP
丢包或乱序形成损坏 H.264 单元。RTCP 队列会被周期性清空；旧日志中的
`RTCP queue full ... thrown away` 表示状态包被丢弃，g3pylib 已在该分支捕获
`QueueFull`，它本身不会关闭 RTP 或退出 Python。

低延迟通路会并发消费 gaze 与 scene RTSP 队列，保留每个 gaze 样本但只处理最新待处理场景帧；
屏幕映射约 25 Hz，场景 JPEG 约 8 Hz，gaze 聚合 worker 上限约 100 Hz。Monitor 的映射请求
约每 60 ms 发起一次且不会重叠，只有材料、滚动或对话实际变化时才更新只读 iframe；每个
gaze 样本会直接更新映射快照，不再等待下一张场景视频帧。

Monitor 使用三个大字号页签：`眼动映射`、`脑电指标` 和 `Policy`。Policy 页固定展示
`AOI Dwell`、`Fix Count`、`Mean Fixation`、`回视次数`、`回视时间`、Eye validity 和 Eye score。眼动映射页不再重绘
零散的 DOM 文字框，而是以完整的只读实验页面作为底图，仅叠加最近 3 秒的屏幕眼动轨迹
和当前位置。当前材料、AI/被试对话气泡、Policy 确认按钮、加载状态、解释档位、输入区、
文档滚动位置和对话滚动位置均由实验页同步。Monitor 镜像不会启动试次、修改实验状态或
调用 LLM。页签也可用 `/ui/monitor.html?view=gaze|eeg|policy` 直接打开。

### EEG 通道质量判定

系统在每个 4 秒、32 通道窗口上先逐通道减去中位数，再做 1–45 Hz 四阶 Butterworth
带通和 50 Hz 陷波，随后计算 Welch 功率谱。任意一项成立即将该通道标记为“当前窗口异常”：

1. 49–51 Hz 功率大于 `10`，记为“工频”。
2. 20–40 Hz 功率大于 `30`，记为“高频”。
3. 滤波后绝对幅值达到 `100` 的样本超过 500 个，即按 250 Hz 采样率累计超过 2 秒，记为“大振幅”。

这里的幅值 `100` 是 BrainCo SDK 输出数值尺度上的阈值。Recon 适配器目前只调整缓冲区
形状，没有额外换算成微伏，因此在未用设备文档或标定信号确认 SDK 单位前，不应把它直接
表述为 `100 µV`。

Monitor 的“当前窗口异常”显示全部 32 导的诊断结果，并显示每个坏导触发了哪一种判据；
“解码排除”只显示当前 EEG 指标实际使用的后部通道中被排除的通道。当前 posterior-alpha
解码使用 `P3/P4/P7/P8/PZ/O1/O2`，至少需要 3 个可用通道，且坏导比例上限为 `0.45`：
这 7 个通道中最多允许 3 个
不可用；否则 EEG 质量为 `warning`，C3 Policy 会降级为 Eye-only，而不是把低质量 EEG
强行用于融合。

根据真机 run `2_condition_3_20260803_171720_918510` 的旧阈值结果离线复算：667 个窗口
原为 631 个 `pass`、36 个 `warning`；把高频阈值从 20 调到 30、后部坏导比例从 0.40
调到 0.45 后，预计为 650 个 `pass`（97.5%）和 17 个 `warning`。保留的 17 个 warning
正好是连续的全 32 导大范围伪迹，没有被放宽设置掩盖。`TP9` 全程有明显工频问题，
这种模式优先检查参考/地电极、TP9 接触、头发阻隔、电极阻抗、
帽体和线缆松动，以及咬牙、颈部用力和大幅转头。不要仅为了减少红色通道而整体放宽
阈值；应先根据 Monitor 的“工频/高频/大振幅”原因修复采集质量，再用多名被试的静息与
阅读数据重新标定阈值。

### 原生崩溃排查

2026-08-03 17:24:49 的自动退出不是应用主动断开。Windows Application Event 1000/1001
记录了 `python.exe` 在 `msvcrt.dll` 内发生 `0xc0000005` 访问冲突；同一模块、偏移和异常
签名此前也出现过。此类原生崩溃发生在 Python 解释器之外，普通 `try/except` 无法捕获，
所以终端不会出现 Python traceback，只会直接回到提示符。

本次日志同时包含两类独立现象：BrainCo 原生解析器报告 CRC 失败，以及 Tobii RTCP 队列
已满。CRC 缓冲区中可见交错帧头，因此 Recon 已默认禁用未使用的 IMU；RTCP 满队列只会
丢弃状态包，现也会主动清空。重复崩溃历史中至少有一次没有加载 BrainCo SDK，因此不能
把 CRC 失败当作整个 Python 进程崩溃的唯一根因。共同的高风险链路是 Tobii scene camera
的 `g3pylib -> PyAV -> FFmpeg` 长时 H.264 解码，且当前 PyAV 12.3 与 g3pylib 声明的
PyAV 10 存在版本偏差。默认 RTSP-over-TCP 是针对损坏 UDP 视频单元的风险缓解，不等于
已经证明根因彻底消失。

`run_tobii.ps1` 已启用 Python faulthandler，并在子进程非零退出时打印退出码。若再次无
traceback 退出，立即保留末尾日志，并运行：

```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=(Get-Date).AddMinutes(-10); Id=1000,1001} |
  Where-Object Message -Match 'python.exe' |
  Select-Object TimeCreated, Id, Message
```

如果 TCP 模式仍复现 `0xc0000005`，不要继续正式收数；下一步应把 scene video 解码隔离到
可独立重启的子进程。可先做 60–90 分钟 gaze-only 对照：

```powershell
.\run_tobii.ps1 -TobiiGazeOnly
```

该模式保留原始 `gaze2d`，但没有场景画面、屏幕映射和 Eye AOI 指标，不能用于 C2/C3
正式收数。若完整模式重复崩溃而 gaze-only 稳定，scene/PyAV 链路的嫌疑会显著提高；向
Tobii/PyAV 提交 WER dump、依赖版本和复现时长。自动重启整个实验服务会破坏 trial
连续性，因此不能把它当作正式实验修复。

## 9. 常见检查

1. `/api/health` 中 `eeg_connected`、`gaze_connected` 是否为 `true`。
2. `/api/state` 中 EEG/gaze 的 `status`、`quality` 和数据时间是否持续更新；C2/C3 还要确认 `state.eye` 的三个核心字段不为 `null`，并在有新格式数据时检查回视字段。
3. EEG 已连接但指标为空时，检查是否已经积累完整窗口（默认 4 秒）以及质量门控是否通过。
4. Tobii `gaze2d` 是眼镜场景相机坐标，不是电脑屏幕坐标；未做标定时不能直接解释为网页 DOM 坐标。
5. 真实实验前应使用本地数据重新校准坏导比例、线噪声和高频污染阈值。
6. 首题前 10 秒看到 `eye_personal_baseline_collecting` 是正常状态；持续超过 10 秒时检查屏幕映射、阅读 AOI 和有效样本比例。
