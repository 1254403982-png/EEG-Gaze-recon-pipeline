# 开工修改说明

## 2026-08-06: Gaze target fallback clarified

- Kept C2/C3 policy thresholds unchanged. Pixel-level gaze precision is not required; readable leaf targets are preferred, with heading or broad-container fallback when camera calibration is approximate.

## 2026-08-06: One-page final questionnaire layout

- Reworked the printable questionnaire into a single A4 final form completed only after all three rounds.
- Removed the per-round overall-experience section and merged checkbox items into compact comparison tables.
- Removed condition names and retained only neutral first/second/third-round and active-method A/B labels.

## 2026-08-06: Printable final questionnaire

- Added `docs/FINAL_QUESTIONNAIRE_PRINT.html`, an A4 print form with a per-round questionnaire template and a final three-round comparison questionnaire.
- Added branch wording for proactive-help timing and missed-help moments, plus “不适用” handling when a round such as C1 has no relevant AI interruption experience.
- Added neutral “主动方式 A/B” comparison items and instructions for recording the randomized A/B mapping without exposing condition names to participants.
- Added the matching usage guide in `docs/FINAL_QUESTIONNAIRE_PRINT.md`.

## 2026-08-06: Start-page JavaScript parse fix

- Replaced the multimodal gaze-focus prompt template literal with an array-based string builder. An unescaped backtick had caused `Unexpected identifier 'sustained_dom_target'` during page parsing, preventing the researcher-settings and experiment-start click handlers from being registered.
- Verified the page in a headless Edge session: no runtime exceptions; the settings panel opens, and the start button enables after a subject ID is entered and consent is checked.

## 2026-08-06: C2 early-offer and focus precision update

- A missing first UI heartbeat now counts as zero seconds in the Trial, so the server holds Policy during the full 20-second reading-start protection window.
- Automatic screen targets now prefer readable leaf elements and avoid using the full reading container or large headings as the focus label.
- C2 brief help requires corroborated core evidence; example and detailed thresholds are now `1.35` and `1.85`, with unlimited per-Trial offers still enabled (`max_automatic_offers_per_trial=0`).

## 2026-08-06：C2 初始保护、映射一致性与重复询问

- C2/C3 每个 Trial 的阅读起始保护窗调整为 20 秒；保护窗内服务端和实验页都禁止主动询问。
- Policy 增加当前 `trial_id`/`slide_id` 与屏幕布局的匹配检查。新题布局尚未同步完成时返回 hold，避免沿用上一题末段造成“刚开始就询问最后板块”。
- C2 的回视次数/回视时间继续参与总分，但不能凭单独回视异常触发简单解释；核心注视指标的分级调整为 `1.35/1.50/1.75`，并将单核心指标候选提高到 `1.75`。
- Policy offer 在被试点击“需要帮助/不需要”后释放当前证据 episode，同一题可以在后续新的持续证据下再次询问；每题仍不设自动询问次数上限。

## 2026-08-05：实验总用时计时修复

- 修复实验页把 `startExperimentTimer(null)` 的 `null` 转换为 `0` 的问题。旧逻辑从 Unix epoch 开始计时，会在页面显示类似 `29765497:32` 的巨大用时。
- 计时器现在统一接受正的 epoch 毫秒、epoch 秒或 ISO 时间戳，并在开始时立即刷新显示；超过 1 小时显示为 `H:MM:SS`，否则显示为 `M:SS`。
- 断点恢复和旧本地检查点会按 `meta.experimentStartTime`、`startISO`、校准结束/开始时间、首个 Trial 开始时间依次恢复；无法恢复时才从当前时刻开始，不会再从 1970 年开始。
- `meta.totalDurationSec`、`experimentEndTime` 和 `endISO` 使用同一套归一化后的开始时间计算。Trial 的 `durationSec` 和服务端事件时间不变。

本文档持续记录 Recon Pipeline 的结构性修改、验证结果和仍需完成的工作。每次开始新的实质修改时，在顶部追加一节。

## 2026-08-05：C2 焦点定位与主动询问次数调整

- C2 的 Eye 分级改为简单解释 `1.30`、举例子 `1.40`、详细解释 `1.80`；单一指标需达到 `1.65`，
  避免轻微波动过早弹出简单解释，同时允许持续多指标异常更快升级。
- C2 自动询问不再按解释档位去重，`max_automatic_offers_per_trial=0` 真正表示本题不限次数；
  同一证据 episode 仍通过服务端 8 秒冷却和持续证据门控去抑制重复闪现。
- Policy 焦点优先使用浏览器已映射的 `dwell_target` 或轨迹中心对应 DOM 段落，只有没有可靠映射时
  才调用 LLM 推断，避免模型根据材料顺序误选最后一、两段。

## 2026-08-05：Eye Policy 基线与触发诊断放宽

- Eye 个人基线改为在本 Condition 第一题的前 15 秒保护窗内同步收集；保护窗仍禁止自动询问，
  但不再额外等待完整的基线时长，后续 Trial 复用本轮基线。
- 开发配置将 Eye 基线窗口从 10 秒缩短为 5 秒，有效样本比例从 0.60 放宽为 0.50，
  单项/综合异常门槛调整为 `1.50`、`1.20/1.45/1.95`，持续证据窗口调整为 0.20 秒。
- 若记录仍显示 `screen_mapping_invalid`、`markers_missing` 或 Eye 核心指标为空，策略仍会保持，
  这是为了避免在 Tobii 断流或未映射时误触发；监控端应先处理映射/设备状态。
- Tobii 采集器的有效样本门槛改为复用 `policy.gaze_min_valid_ratio`，避免采集器默认 0.60
  在 C2 到达 Policy 之前提前拦截。

## 2026-08-05：Policy 弹窗去重与阅读起始保护窗

- 同一 Trial 的同一解释档位（简单解释/举例子/详细解释）只记录并呈现一次；被试选择需要
  或不需要后，该档位不再重复弹窗，状态保存在该 Trial 的 `policyPromptedLevels` 和
  `policyAnsweredLevels`。
- Policy 新增 `minimum_trial_seconds=15`。实验页每秒同步 `seconds_in_trial` 和阅读滚动进度，
  服务端在前 15 秒返回 `trial_reading_baseline_window`；屏幕映射没有阅读元素稳定停留时也
  不生成候选，减少刚开始阅读时对后段内容的误提示。

## 2026-08-05：放宽 Eye Policy 触发

- 保留每个 Trial 前 15 秒保护窗，但将开发配置的 Eye 门槛调整为
  mild/moderate/strong=`1.25/1.55/2.10`、异常 ratio=`1.25`、单指标触发=`1.70`。
- 持续证据从 3 次/0.45 秒调整为 2 次/0.30 秒，升级冷却从 45 秒调整为 30 秒。
- 屏幕映射短暂没有 dwell target 时不再阻断整个 Eye episode；只有确认注视 AI 面板时才
  抑制，避免因为映射刷新而完全没有自动询问。

## 2026-08-05：断点续做与高难题选项重写

- 实验页新增 Condition 级 checkpoint：约每 2 秒保存本地状态，并在页面离开前保存；重新输入
  相同被试和 Condition 可选择继续，已完成 Trial 保留，未完成 Trial 从头重做。
- 服务端 session start 支持 `resume_stamp`，恢复时复用原 Condition run 目录并返回 `run_stamp`，
  避免浏览器断点与 EEG/gaze 文件分叉。
- 重写高难度题 45–48 的综合理解选项，增加机制、条件和证据链之间的干扰项；不增加材料正文。
  正确选项位置和长度已重新分散，避免仅凭选项长度作答。

## 2026-08-04：对话接龙、简单解释分流与 Policy 触发收紧

- 人工复制提问和 Policy 回答现在都锚定在对应的用户气泡之后，AI 回复不会插入到上一条问题上方。
- 简单解释区分主动粘贴和 Policy 主动询问：均以 2–4 句、90–180 个中文字符补足关键理解链，输出不合格时最多自动重写两次，但不再因长度不足直接显示调用失败。
- `max_automatic_offers_per_trial=0` 表示每个 Trial 不设自动询问次数上限；同一证据 episode 仍只询问一次，避免重复气泡。
- 提高 C2/C3 的 Eye ratio 与 EEG workload 门槛，降低过于容易的自动触发；Policy 规则和阈值见 `docs/POLICY.md`。
- Eye 特征增加 `aoi_revisit_count` 与 `aoi_revisit_time`；仅在当前窗口和个人 baseline 均有字段时参与加权，避免旧数据被误判。
- 手动提问未选择解释粒度时会显示红色提示并阻止发送；AI 消息统一按事件发生顺序从上到下插入，Trial 重置时清空初始欢迎气泡。
- 修复 Policy 拒绝后人工提问跑到“不需要”气泡上方的问题：Policy 气泡、用户选择、手动消息和 AI 回复统一经过时间序列插入器，loading 指示器始终固定在消息尾部。

## 2026-08-04：问卷精简为 Trial 四题与 Condition 三题

- 新增 `trial-survey-v1`：每个 Trial 的理解题提交后立即呈现心理努力、困惑程度、当前
  理解和帮助需求 4 题，T01–T06 各记录一份，再进入下一次静息或 Condition 问卷。
- 将 Condition 问卷升级为 `condition-survey-v3`，C1/C2/C3 均只保留需求匹配、清晰度和
  个性化 3 道 1–7 同意度题；三题均允许选择“不适用”。
- 按最终实验方案彻底移除主动筛选回忆题、相关分支题、旧 14 项 Condition 题组和三个
  Condition 完成后的最终总问卷；历史 run 仍按各自保存的 schema 版本解释。
- 两类问卷均记录版本、起止时间、逐题延迟、题目顺序和 schema 快照，并增加 Trial 问卷
  开始/提交交互事件。同步更新使用说明、API、数据字典、架构和 CHI 研究说明。
- Condition 第一次确认后立即冻结答案和首次提交时间；保存或 session finalize 失败时，
  “重新提交”只上传同一条 pending record，并记录
  `condition_questionnaire_finalize_retried`，不会生成第二份问卷。
- 简单解释契约由旧 2–3 句/120 字调整为“1 句承接 + 3–5 句补足关键理解链”、180–260 个
  中文字符；系统复验每次输出并最多自动重写两次，仍不合格则明确提示被试重新发送，
  不再通过破坏性删句或截断伪造合格回答。
- Policy 视觉定位时缓存触发时场景帧及轨迹；被试确认需要帮助后，解释 LLM 复用该快照，
  不再抓取视线已移到对话区后的新帧。`frameSnapshot` 仅在内存传递，写入
  `trial.policySuggestions` 时剥离 base64 图像以控制 `experiment.json` 体积。

## 2026-08-03：原生退出取证与采集稳定性缓解

- 从 Windows Application Event 1000/1001 确认 17:24 的“自动断开”实际是
  `python.exe` 在 `msvcrt.dll` 中发生 `0xc0000005` 访问冲突，不是应用正常停止；相同
  崩溃签名此前已出现，且至少一次没有加载 BrainCo SDK。
- 区分三个现象：BrainCo CRC 失败、Tobii RTCP 队列满和 Python 原生崩溃。RTCP 满队列
  只丢状态包，现由 provider 周期清空；BrainCo 默认改为 EEG-only，避免未使用 IMU 帧
  继续混入传输，但不将其宣称为重复崩溃的唯一根因。
- Tobii 默认由 UDP 改为 RTSP-over-TCP interleaved transport，减少丢包/乱序形成损坏
  H.264 单元后进入 `g3pylib -> PyAV -> FFmpeg` 的概率；保留
  `-TobiiRtspTransport udp` 诊断回退。
- 增加 `-TobiiGazeOnly` 长时 A/B 诊断模式：保留 gaze2d 但关闭 scene/PyAV 解码；由于
  没有屏幕映射和 Eye AOI 指标，该模式明确禁止用于 C2/C3 正式收数。
- `run_tobii.ps1` 启用 faulthandler 并显示非零进程退出码；文档不再把
  g3pylib `av~=10` 与实际 `av==12.3` 的冲突描述为无运行风险。
- 放宽基于真机 run 复算的 EEG 高频阈值与后部坏导比例：高频功率阈值 20→30，后部
  `max_bad_channel_ratio` 0.40→0.45。预计 pass 由 631/667 增至 650/667，同时保留
  17 个全 32 导大伪迹 warning；工频和大振幅阈值不变。

## 2026-08-03：Condition 中性同版问卷 v2

- 将三个 Condition 结束后的差异化三题问卷替换为完全同标题、同措辞、同顺序的 14 项
  `condition-survey-v2`；被试问卷不再出现 C1/C2/C3、EEG、gaze、Policy 或主动触发说明。
- 新问卷覆盖心理努力、主观难度、感知理解、帮助价值、需求匹配、时机、清晰度、打断、
  操作负担、控制感、拒绝便利、信任和再使用意愿。AI 相关题支持显式“不适用”，不将其
  当作中间分。
- 增加问卷版本、开始/提交时间、总耗时、逐题作答时间、题目顺序和完整 schema 快照；
  新增 `condition_questionnaire_started` 事件，并保留提交失败重试与不可意外关闭行为。
- 更新问卷布局以适配普通窗口和实验大屏，增加完成进度；补充静态回归测试和数据字典。

## 2026-08-02：项目文档校准与 CHI 研究方案

- 重写项目 README 与架构说明，移除 Python 3.9、未实现实验页/屏幕映射、旧 entropy
  Policy、`runs/raw_eeg` 和 EEG-only 降级等过时描述，改为当前单 Condition 六试次流程。
- 将原始 EEG 文档迁移到实际的 Condition run `eeg/` 结构，补充逐样本
  `host_timestamps_ns`、分块边界和原始/特征/浏览器采样的区别；同步修正 API 与 USAGE
  中的落盘路径、Policy 日志节流和 gaze 文件名。
- 新增 `DATA_SCHEMA.md`，定义逐文件语义、时间边界、连接键、推荐派生表、完整性检查和
  当前尚未落盘的复现元数据。
- 新增 `CHI_STUDY_PLAN.md`，整理 CHI 2027 官方要求、研究定位、技术/构念 pilot、离线
  Policy 验证、交互主实验、matched-dose timing control、混合效应分析、伦理和冻结清单。
- 文档明确标记正式收数阻断项：正确选项位置严重失衡、材料未跨 Condition 平衡、首题
  Eye baseline 污染、posterior-alpha/attention 非独立、三条件混合 timing/dose/content，
  以及问卷和版本元数据不足。

## 2026-08-02：高难材料单页增补与最终问卷锁定

- 将高难材料纯文本由 600–900 字符增补至 750–950 字符，主要为原先留白较多的材料增加
  贯穿全文的综合情境或分析链路，使信息量更接近左侧阅读区一屏。
- 新增基于实际 `scrollHeight/clientHeight` 的单页适配：溢出时只收紧间距与行距，不缩小
  字号；适配后隐藏滚动条，仍放不下时保留滚动兜底，避免裁切内容。
- 最终 Condition 问卷不再响应遮罩点击或 `Esc`；提交改为先等待交互记录和实验数据保存，
  成功后才关闭并进入结束页，失败时保留问卷及选择并提供重新提交。

## 2026-08-02：高难题改为全文理解且取消计算

- 以中难度“正当防卫的界限与特殊防卫”约 801 个纯文本字符、三段主结构和一张表的呈现
  密度为参照，阶段性将高难材料控制在 600–900 字符；后续根据单页留白反馈增补至
  750–950 字符。
- 再次重写高难题库全部 32 道题：第一题明确从全文主线出发，第二题整合概念关系、适用
  边界或证据链；取消后验概率、相对论时间、贝尔曼回报、热力学阈值和窗口数值计算。
- 题库测试新增材料纯文本长度上下限，并禁止题干出现数字、计算、求数值或“最接近”类
  表述，防止以后退回局部细节题或计算题。

## 2026-08-02：高难度材料与理解题升级

- 重写高难题库 ID 33–48 的关键材料段落和全部 32 道理解题，将直接定义复述升级为跨段
  整合、条件判断、机制失效和反例辨析；阶段性加入的计算题已在后续修改中取消。
- 新增的推理内容覆盖基准率、洛伦兹因子、反应商、折叠动力学、数据泄漏、贝尔曼计算、
  记忆干扰、黏性损失、抗原呈递、交易成本、采样混叠、热力学阈值、黏弹时间尺度、
  表观因果检验、TCP窗口计算与最佳反应分析。
- 修正机翼升力的“等时路径”过度简化和 TCP Reno 快速恢复后的窗口描述；增加高难材料
  长度、两题四选项及答案索引的题库回归检查。

## 2026-08-02：理解题题干字号放大

- 将每篇材料阅读结束后弹出的两道理解题题干从 17 px 放大到 20 px，选项和其他实验区域
  字号保持不变。

## 2026-08-02：实验页全窗口字号下调

- 将实际实验主页面在基础窗口与 1800×1000 以上大屏分支中的正文、标题、公式、表格、
  对话气泡、Policy 确认、解释档位和输入区字号都统一下调 2 px，避免退出全屏后恢复旧字号。
- 保持面板、按钮、自然锚点和整体布局尺寸不变，避免仅调整字体时改变眼动映射几何位置。

## 2026-08-01：确认交互回退与 EEG 坏导诊断

- 取消待确认 Policy 气泡对页面全局鼠标左右键的接管，恢复为必须点击气泡中的
  “需要帮助 / 不需要”按钮，避免左键选中文字、聚焦输入框或右键菜单被误判为回答。
- 明确 C1/C2/C3 都保留人工复制粘贴提问通路；Condition 只决定自动 Policy 使用哪些
  生理信号，不会关闭被试主动选择解释档位并发送的能力。
- EEG 预处理为每个异常通道增加 `line_noise`、`high_frequency` 和
  `extreme_amplitude` 原因；Monitor 分开显示全部 32 导的当前窗口异常与真正被 EEG
  指标解码排除的后部通道。
- 核对真机 run `1_condition_3_20260801_170413_844378`：2581 个 EEG 窗口中 547 个为
  `warning`，TP9/T7/O1/O2 高频异常且存在全局多导恶化，暂不通过放宽阈值掩盖接触、
  参考/地、电缆或运动伪迹问题。

## 2026-08-01：C3 自动询问重复气泡修复

- 核对真机 run `1_condition_3_20260801_170413_844378`，确认 T03/T04 分别在不足
  1 秒内记录了两个不同 `policyId` 的 `policy_prompt_shown`。
- 原因为视觉 LLM 正在推断关注区域时，`pendingPolicySuggestion` 尚未建立，400 ms Policy
  轮询再次进入并发的 `triggerPolicyExplanation()`。
- 前端增加单飞轮询 `policyPollInFlight`、视觉定位准备锁 `policyPromptPreparing` 和
  `lastPresentedPolicyId` 去重；一次询问从获取决策到气泡创建期间不再接受第二次轮询。
- 服务端 Policy 消息改为气泡成功创建后才按 `policy_id` 确认领取，避免定位等待期间提前
  清空锁存消息。屏幕上同一时刻最多保留一个待回答的自动询问。

## 2026-07-31：真机先导后的 Policy 灵敏度与自动询问投递修复

- 分析 `1_condition_2_20260731_211741_036668`：T02 困难窗口 Eye score 最高 `1.266`，
  平均 fixation duration 达个人 baseline 的约 `2.04–2.14` 倍，但仅持续约 `0.6 s`，
  因旧 `1.5 s` 证据门槛未产生自动询问。
- 将 C2/C3 Eye 门槛调整为 mild/moderate/strong=`1.05/1.35/1.80`，异常 ratio=`1.10`，
  并允许任一 Eye ratio 达到 `1.50` 时产生 brief 候选。
- 持续证据改为至少 3 次且 `0.45 s`；自动询问间隔改为 45 秒，每个 trial 最多 2 次，
  换题时重置询问计数但不重建本次 Condition 的个人 baseline。
- 修复高频 gaze 评估覆盖一次性 trigger 的问题：服务端锁存可执行决策，实验页领取后按
  `policy_id` 确认；Policy 前端轮询独立提高到 400 ms。
- （已在 2026-08-01 后续修改中回退）曾短暂使用左键接受、右键拒绝的全局鼠标通路；
  现已恢复为点击 Policy 气泡内的明确按钮。

## 2026-07-31：固定 Eye 特征、个人基线与 C2/C3 Policy 重构

- 将 Policy 的眼动输入固定为三个字段：`aoi_dwell_time`、`fixation_count` 和
  `mean_fixation_duration`；旧 entropy、saccade、pupil 等字段只保留为诊断信息。
- 新增 `EyeFeatureExtractor`，从每个样本到达时的动态屏幕映射轨迹计算阅读 AOI dwell
  与 I-DT fixation；映射或阅读 AOI 无效时明确输出 `null`。
- 每个 Condition/session 使用首题最初 10 秒有效阅读数据建立个人 Eye 中位数基线。
  纯白静息不参与 Eye baseline，session 切换时基线清空。
- C2 改为三个个人 baseline ratio 的 `0.4/0.3/0.3` 加权难度分，并按
  `1.2/1.5/2.0` 分为 brief/example/detailed。
- C3 使用 Eye level 与 EEG level 的显式 case rule；脑负荷阈值为 `40/70`，低 attention
  阈值为 `40`。EEG 低质量只可退化为 Eye-only，Eye 缺失时禁止 EEG-only。
- `MultimodalState`、HTTP gaze 输入、回放 provider、`/api/state` 和 Monitor 同步增加
  稳定的 `eye` 结构；Policy 审计记录包含 baseline、ratio、level、融合分和降级原因。
- 维持 C1、BrainCo 采集、32 通道预处理、LLM 被试确认层和原始数据格式；旧 gaze
  诊断字段与事件外壳继续兼容。
- 新增基于既有真机轨迹节选的 Eye 特征回归夹具，并覆盖 C1、C2 baseline/C3 五类规则、
  AI 面板抑制、持续证据、HTTP 和 replay 数据契约。
- 离线重放既有 Condition 记录确认可建立个人 baseline 并产生分级候选；本次代码修改后
  尚未重新连接真实 Tobii/BrainCo，被试正式实验前仍需在 Monitor 核对映射和三个 Eye 指标。

## 2026-07-28：BrainCo SDK 0.5 启流与 Windows 发现修复

- 恢复正确依赖 `bc-ecap-sdk>=0.5,<0.6`，安装 PyPI 官方 Windows/Python 3.10 wheel 0.5.0。
- SDK 0.5+ 优先使用官方统一 `ECapClient.start_stream(parser, fs, gain, signal)`；旧分步 API 保留为兼容回退。
- 同步修正 `llm/20260706211132/.../oi-mi/acquisition/brainco_acquirer.py` 及根目录 `oi-armi` 副本。该文件只由对应 `oi-mi/acquisition/factory.py` 注册；Recon 主程序实际调用迁移后的 `BrainCoSDKAcquirer`。
- 新增统一启流单元测试，BrainCo SDK 适配器 5 项测试通过。
- Windows 上原生 `mdns_start_scan()` 可能无法取消地阻塞；发现顺序改为有界的直接 Zeroconf 优先。
- 真机诊断确认 `192.168.3.9:53129` TCP 可达，但设备未回复配置/启流命令且无首包；需关闭其他 BrainCo 客户端、重启脑电帽后复测，并核对固件与 SDK 0.5.0 兼容性。
- 新增有界诊断脚本 `scripts/diagnose_brainco.py`：直接 Zeroconf 发现、TCP 检查，并通过独立控制会话请求设备信息和电量，以区分程序启流问题与设备内部 MCU/固件无响应。

## 2026-07-28：中文路径 editable `.pth` 修复

- 定位 Python 3.10 `init_import_site` 崩溃为 UTF-8 editable `.pth` 被按 GBK 读取。
- 真机环境将 Recon 改为非 editable 本地 wheel 安装，避免 site-packages 依赖中文源码路径。
- 三个 `run_tobii.ps1` 入口统一设置 `PYTHONUTF8=1`。
- 在 `eeg_pipeline_副本` 目录增加快捷入口，修复该目录下 `.\run_tobii.ps1 -BrainCo` 找不到的问题。
- 由于镜像无 PyAV 10 Windows wheel 且源码与新 Cython 不兼容，本地 g3pylib wheel 改用官方 PyAV 14.2.0 Windows wheel；仍需真机验证 RTSP gaze 解码。
- `zeroconf` 固定为 0.47.4，使 BrainCo 和 g3pylib 的声明约束同时成立。

## 2026-07-28：pip TLS/Build Isolation 安装兼容

- 将构建系统的 setuptools 最低版本从 68 调整为 Python 3.10 默认环境可满足的 65；项目未使用 setuptools 68 专有能力。
- 增加 `SSLEOFError` 排错流程，通过 `PIP_INDEX_URL`/`PIP_TRUSTED_HOST` 使镜像配置传递给构建子进程。
- 建议对本地可编辑安装使用 `--no-build-isolation`，避免重复下载已存在的构建工具。
- 增加 GitHub `git fetch` 被重置时的 codeload ZIP 备用安装流程，Tobii 与 BrainCo 仍安装在同一虚拟环境。

## 2026-07-28：Tobii 官方 Git 依赖与 Python 3.10 统一

- 确认 `g3pylib` 未发布在 PyPI，原 `g3pylib>=0.3.1a0,<0.4` 无法解析。
- 改为 Tobii 迁移后的官方 `tobii/glasses3-pylib` Git 仓库，并锁定提交 `5868e2d327a077cb6bbe276182188b81fc90f224`。
- 根据官方支持范围，将 Recon 最低 Python 版本从 3.9 调整为 3.10。
- BrainCo 与 Tobii 继续共用同一 `.venv-win`，推荐用 Python 3.10 重建该环境。

## 2026-07-28：BrainCo SDK 公开源版本约束修复

- 修复不可满足的 `bc-ecap-sdk>=0.5,<0.6` 依赖声明。
- 锁定公开 Python 软件源已发布的 `bc-ecap-sdk==0.4.5`。
- Recon 集成使用 `0.4.x` 代际的 `set_cfg`、EEG 枚举、TCP 客户端和流控制接口。
- 安装与导入可在无硬件环境验证；真机发现、启停、固件兼容和样本接收仍需实验现场复核。

## 2026-07-28：Tobii/BrainCo Windows 启动入口修复

- 移除 `run_tobii.ps1` 中旧电脑的固定 Miniconda Python 路径。
- 默认探测仓库根目录 `.venv-win`，并允许通过 `-Python` 覆盖。
- 在 `EEG+Gaze` 根目录增加转发脚本，使 `.\run_tobii.ps1 -BrainCo` 可从用户常用终端目录直接运行。
- 补充工作目录、显式 Python 和 PowerShell 执行策略的排错说明。

## 2026-07-28：Windows 开发环境文档维护

- 将安装命令从旧电脑的固定盘符和 Miniconda 路径改为项目内 `.venv-win`。
- 明确 Python 3.9–3.13 版本范围，并补充 pytest/ruff 验证命令。
- 区分核心开发依赖与 BrainCo/Tobii 真机可选依赖。
- 补充 Windows 执行策略、防火墙、设备网段和 `DASHSCOPE_API_KEY` 配置说明。
- 本次只维护文档与本地环境，不改变代码、配置格式或 API。

## 2026-07-27：项目文档统一中文

- 将 README、架构说明、实验平台接口说明、原始脑电存储说明和第三方软件声明的标题及说明文字统一为中文。
- 保留 API 路径、JSON 字段、类名、命令参数等代码契约原文，避免与实现不一致。
- MIT 许可证法律文本保留英文原文，并增加中文引导说明。

## 2026-07-27：32 通道处理框架与 BrainCo 采集整合

### 修改目标

- BrainCo 的全部 32 通道进入统一预处理，不再在采集后立即压缩成 NeuroDock 7 通道。
- 将“使用哪些通道”和“计算什么指标”下沉到解码器，使采集、预处理和解码解耦。
- 允许并行注册多个解码器，为后续增加 EEG 指标保留稳定扩展点。
- 将 `../oi-armi/oi-mi` 中实际需要的 BrainCo SDK 采集能力迁入本项目，取消运行时目录依赖。
- 保持现有 `EEGFeatures`、策略、HTTP 接口和实验界面的兼容性。

### 主要结构变化

```text
acquisition/brainco_sdk.py       BrainCo SDK 连接、发现、启停和缓冲区归一化
acquisition/brainco.py           Recon EEGSource 适配器和 32 通道定义
eeg/contracts.py                 全通道处理窗口和通用解码结果契约
eeg/preprocessing.py             与通道数量无关的滤波、PSD 和质量评估
eeg/decoders/                    可插拔解码器及注册表
eeg/factory.py                   从配置构造预处理器和解码器
eeg/online.py                    全通道滑窗与多解码器调度
```

数据方向现在是：

```text
32 通道采集 --> 原始数据保存 --> 32 通道预处理 --> 解码器自行选通道 --> 标准状态/API
```

### 解码兼容策略

- `posterior_alpha` 是当前主解码器。
- 默认选择 `P3/P4/P7/P8/PZ/O1/O2`，这些都是 BrainCo 32 通道布局中的真实通道。
- 主解码器继续产生 `cognitive_load`、`attention`、`alpha_power`、`alpha_peak_hz` 和 `alpha_suppression` 等现有标准字段。
- 所有解码器的通用输出同时保存在 `metadata.decoder_outputs`，新增指标不要求修改采集协议。
- 旧 `BrainCoNeuraDockMapper` 仅为导入兼容保留，不再处于默认运行通路。

### `oi-mi` 整合范围

迁入了当前 Recon 实际需要的能力：

- mDNS/显式地址连接；
- BrainCo SDK 生命周期管理；
- 缓冲区配置；
- EEG 流启动、重试与无 ACK 容错；
- SDK 缓冲区形状归一化与连续时间戳；
- 回调、日志与安全停止。

没有迁入旧项目的 UI、旧模型、旧解码器或无关服务端代码。来源项目采用 MIT License，归属说明见根目录 `THIRD_PARTY_NOTICES.md`。

### 配置变化

`configs/development.json` 新增顶层 `eeg`：

- 采样率、窗口、缓冲长度和滤波范围；
- 全通道质量阈值；
- 主解码器和解码器列表；
- BrainCo 地址、设备 ID、超时、重试、增益和信号源。

命令行不再需要 `--legacy-oi-mi`。该参数暂时以隐藏的兼容参数保留，但不会影响运行。

### 验证记录

- 32 通道合成 EEG 可以完成预处理并输出标准特征。
- 解码器选取通道不会改变预处理窗口中的完整通道数。
- 可增加第二个自定义解码器并输出额外指标，现有策略契约不变。
- 运行中通道布局发生变化会被明确拒绝，避免错误拼接数据。
- session 切换时会清空滑窗和解码器基线，避免开发阶段或上一被试的数据进入当前被试基线。
- BrainCo SDK 缓冲区转置、嵌套 `msgId` 解析和无外部路径适配已有单元测试覆盖。
- 使用模拟 SDK 完成了内置采集适配器的连接、配置、取样和停止生命周期测试。
- 32 通道、4 秒窗口的本机合成数据处理基准约为平均 2.44 ms、P95 2.76 ms。
- 当前回归结果：34 项测试在 EEG 开发环境和 Tobii/BrainCo 运行环境中均通过。

### 后续验证与风险

- 已核对当前环境中 BrainCo SDK 的采样率、增益、信号源、客户端和消息解析接口；
  本次自动发现未找到在线设备，仍需在脑电帽处于同网段且可达时复核完整启停和样本接收。
- 现有质量阈值来自早期开发配置；正式实验前必须结合真实 32 通道数据重新标定。
- 实验页当前只画出主解码器选择的 7 个后部通道，并不是完整 32 通道头皮图；后续如需查看空间分布，应由 `channel_names` 动态渲染完整布局。
- Tobii 场景相机坐标若要映射到网页 AOI，仍需要场景到屏幕平面的标定步骤。

## 维护约定

后续修改按以下格式在本文件顶部追加：

```text
日期 + 修改主题
- 目标
- 涉及模块/配置/API
- 兼容性变化
- 测试与真实设备验证结果
- 未解决问题
```
## 2026-08-13: C2 Eye thresholds recalibrated from participants 004 and 005

- Compared all usable C2 Eye difficulty windows for participant 004 (mean 0.815,
  99th percentile 1.077, maximum 1.203) and participant 005 (mean 0.881,
  90th percentile 1.443, 95th percentile 1.617, maximum 3.357).
- Raised the abnormal, brief, example, detailed, and single-core-feature ratios
  to `1.25/1.35/1.55/2.00/1.70`. This reduces repeated offers for participant
  profiles like 005 without lowering the global threshold into the dense normal
  range. Participant 004 remains a baseline-sensitivity case; a fixed global
  threshold cannot recover that run without greatly over-triggering 005.
## 2026-08-15: C2-specific Eye sensitivity and offer guardrails

- Recalibrated C2 from participants 004, 005, and the partial 006 run. Their
  usable C2 Eye-score means were 0.815, 0.881, and 0.402 respectively. At a
  1.15 threshold, 004 and 006 each contained sustained candidate episodes,
  while 005 remained a high-episode profile.
- Added C2-only Eye overrides: abnormal `1.20`, brief `1.15`, example `1.55`,
  detailed `2.00`, and single-core-feature `1.70`. C3 retains the shared
  `1.25/1.35/1.55/2.00/1.70` thresholds.
- Limited C2 to 2 automatic offers per Trial with a 30-second cooldown so the
  lower brief threshold does not reproduce participant 005's excessive dose.
- The partial 006 C2 run produced one server-side brief offer but no browser
  `policy_prompt_shown`; the offer was therefore never presented to the user.
