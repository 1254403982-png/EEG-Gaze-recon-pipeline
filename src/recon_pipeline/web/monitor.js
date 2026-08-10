const $ = (id) => document.getElementById(id);
const history = [];
let latestPayload = {};
let latestMapping = {};
let lastMirrorSignature = "";

function text(id, value, fallback = "—") {
  $(id).textContent = value === null || value === undefined || value === "" ? fallback : value;
}

function number(value, digits = 1, suffix = "") {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(digits)}${suffix}` : "—";
}

function age(timestamp) {
  const utc = timestamp?.utc;
  if (!utc) return "尚未收到数据";
  const ms = Math.max(0, Date.now() - Date.parse(utc));
  return ms < 1000 ? "刚刚更新" : `${(ms / 1000).toFixed(1)} 秒前`;
}

function setChip(id, quality) {
  const el = $(id);
  el.textContent = quality || "unavailable";
  el.className = `chip ${quality || ""}`;
}

function drawChart() {
  const canvas = $("loadChart");
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width || !height) return;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = "#dce3e8";
  ctx.lineWidth = 1;
  [0, .25, .5, .75, 1].forEach((part) => {
    const y = 12 + (height - 24) * part;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
  });
  if (history.length < 2) return;
  ctx.strokeStyle = "#205f9d";
  ctx.lineWidth = 4;
  ctx.beginPath();
  history.forEach((point, index) => {
    const x = index * width / Math.max(1, history.length - 1);
    const y = 12 + (100 - point) / 100 * (height - 24);
    if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function renderState(payload) {
  latestPayload = { ...payload, screen_mapping: latestMapping };
  const state = payload.state || {};
  const eeg = state.eeg || {};
  const gaze = state.gaze || {};
  const eye = state.eye || {};
  const policy = payload.policy || {};
  text("session", state.session_id);
  text("trial", `trial: ${state.trial_id || "—"}`);
  text("condition", `C${state.condition || 1}`);
  text("sources", state.condition === 1 ? "无自适应数据源" : state.condition === 2 ? "Eye only" : "EEG + Eye");
  text("eegStatus", eeg.status); text("gazeStatus", gaze.status);
  text("eegAge", age(eeg.timestamp)); text("gazeAge", age(gaze.timestamp));
  setChip("eegQuality", eeg.quality); setChip("gazeQuality", gaze.quality);

  text("load", number(eeg.cognitive_load, 0));
  text("frontalTheta", number(eeg.frontal_theta_power, 3));
  text("alphaPower", number(eeg.posterior_alpha_power ?? eeg.alpha_power, 3));
  text("alphaPeak", number(eeg.alpha_peak_hz, 2, " Hz"));
  text("workloadIndex", number(eeg.workload_index, 3));
  const eegMetadata = eeg.metadata || {};
  const primaryDecoder = eegMetadata.decoder_outputs?.[eegMetadata.primary_decoder] || {};
  const qualityControl = eegMetadata.quality_control || {};
  const acquiredChannels = eegMetadata.channels || [];
  text("eegChannels", acquiredChannels.length ? `${eegMetadata.channel_count || acquiredChannels.length} 通道` : null);
  text("decoderChannels", primaryDecoder.channels_used?.length ? primaryDecoder.channels_used.join(", ") : null);
  text("badChannels", eeg.bad_channels?.length ? eeg.bad_channels.join(", ") : "无");
  text("decoderBadChannels", primaryDecoder.bad_channels?.length ? primaryDecoder.bad_channels.join(", ") : "无");
  const reasonNames = { line_noise: "工频", high_frequency: "高频", extreme_amplitude: "大振幅" };
  const badReasonText = Object.entries(qualityControl.bad_channel_reasons || {})
    .map(([channel, reasons]) => `${channel}: ${(reasons || []).map(reason => reasonNames[reason] || reason).join("/")}`)
    .join("；");
  text("badChannelReasons", badReasonText || "无");
  const load = Number(eeg.cognitive_load);
  $("gaugeArc").style.strokeDashoffset = String(
    Number.isFinite(load) ? 330 * (1 - Math.min(100, Math.max(0, load)) / 100) : 330,
  );
  if (Number.isFinite(load)) {
    history.push(load);
    if (history.length > 120) history.shift();
  }
  drawChart();

  text("aoi", gaze.primary_aoi);
  text("aoiDwell", number(eye.aoi_dwell_time, 2, " s"));
  text("fixationCount", eye.fixation_count);
  text("meanFixation", number(eye.mean_fixation_duration, 3, " s"));
  text("revisitCount", eye.aoi_revisit_count);
  text("revisitTime", number(eye.aoi_revisit_time, 2, " s"));
  text("eyeScore", number(policy.component_scores?.eye_difficulty_score, 2));
  text("validSamples", number(gaze.valid_sample_ratio == null ? null : gaze.valid_sample_ratio * 100, 0, "%"));
  text("cameraCoords", coordinate(gaze.x_normalized, gaze.y_normalized));

  text("policyId", `#${policy.policy_id ?? "—"}`); text("policyLevel", policy.explanation_level);
  $("policyLevel").className = `policy-level ${policy.explanation_level || "none"}`;
  text("policyAction", policy.action); text("policyMode", `UI mode · ${policy.ui_mode || "normal"}`);
  $("sourceEEG").classList.toggle("used", policy.sources_used?.includes("eeg"));
  $("sourceGaze").classList.toggle("used", policy.sources_used?.includes("eye"));
  $("reasons").innerHTML = (policy.reason_codes || [])
    .map((reason) => `<span>${escapeHtml(reason)}</span>`).join("");
  text("confidence", number((policy.confidence || 0) * 100, 0, "%"));
  text("degraded", policy.degraded_mode || "No"); text("suppressed", policy.suppressed ? "Yes" : "No");
  $("rawJson").textContent = JSON.stringify(latestPayload, null, 2);
}

function renderMapping(mapping) {
  latestMapping = mapping || {};
  text("mapStatus", mapping.valid ? "Mapped" : "Calibrating");
  text("mapAge", mapping.homography_age_ms == null ? mapping.status : `${Math.round(mapping.homography_age_ms)} ms`);
  setChip("mappingQuality", mapping.status || "waiting");
  text("homographyAge", number(mapping.homography_age_ms, 0, " ms"));
  text("screenCoords", coordinate(mapping.screen_x_normalized, mapping.screen_y_normalized));
  text("focusCoords", coordinate(mapping.focus_x_normalized, mapping.focus_y_normalized));
  text("trajectoryCount", mapping.trajectory?.length || 0);
  text("markerCount", `${(mapping.detected_marker_ids || []).length} / 4`);
  syncExperimentMirror(mapping.layout);
  drawScreenTrajectory(mapping);
  $("rawJson").textContent = JSON.stringify({ ...latestPayload, screen_mapping: mapping }, null, 2);
}

function syncExperimentMirror(layout) {
  const viewport = layout?.viewport;
  const width = Number(viewport?.width);
  const height = Number(viewport?.height);
  const available = width > 0 && height > 0;
  $("mappingEmpty").classList.toggle("hidden", available);
  if (!available) return;

  const stage = $("experimentStage");
  const stageWidth = stage.clientWidth;
  const stageHeight = stage.clientHeight;
  const scale = Math.min(stageWidth / width, stageHeight / height);
  const surfaceWidth = width * scale;
  const surfaceHeight = height * scale;
  const surface = $("mirrorSurface");
  surface.style.width = `${surfaceWidth}px`;
  surface.style.height = `${surfaceHeight}px`;
  surface.style.left = `${(stageWidth - surfaceWidth) / 2}px`;
  surface.style.top = `${(stageHeight - surfaceHeight) / 2}px`;
  const frame = $("experimentMirror");
  frame.style.width = `${width}px`;
  frame.style.height = `${height}px`;
  frame.style.transform = `scale(${scale})`;
  const mirror = layout.mirror || {};
  const signature = JSON.stringify({
    slideId: layout.slide_id,
    readingScroll: layout.reading_scroll,
    readingTitle: mirror.reading_title,
    readingHtml: mirror.reading_html,
    chatHtml: mirror.chat_html,
    chatScrollTop: mirror.chat_scroll_top,
    chatInput: mirror.chat_input,
    selectedLevel: mirror.selected_level,
    aiBusy: mirror.ai_busy,
  });
  if (signature === lastMirrorSignature) return;
  lastMirrorSignature = signature;
  frame.contentWindow?.postMessage({
    type: "recon-monitor-mirror",
    slideId: layout.slide_id,
    readingScroll: layout.reading_scroll,
    mirror: layout.mirror,
  }, window.location.origin);
}

function drawScreenTrajectory(mapping) {
  const canvas = $("screenTrajectory");
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width || !height) return;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  ctx.clearRect(0, 0, width, height);
  const trajectory = mapping.trajectory || [];
  if (trajectory.length > 1) {
    ctx.strokeStyle = "#c54138";
    ctx.lineWidth = 4;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    trajectory.forEach((point, index) => {
      const x = point.x_normalized * width;
      const y = point.y_normalized * height;
      if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }
  const x = Number(mapping.display_x_normalized ?? mapping.screen_x_normalized);
  const y = Number(mapping.display_y_normalized ?? mapping.screen_y_normalized);
  if (mapping.valid && Number.isFinite(x) && Number.isFinite(y)) {
    $("screenGazePoint").classList.remove("hidden");
    $("screenGazePoint").style.left = `${x * 100}%`;
    $("screenGazePoint").style.top = `${y * 100}%`;
  } else {
    $("screenGazePoint").classList.add("hidden");
  }
}

function coordinate(x, y) {
  return Number.isFinite(Number(x)) && Number.isFinite(Number(y))
    ? `${Number(x).toFixed(3)}, ${Number(y).toFixed(3)}` : "—";
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}

async function pollState() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderState(await response.json());
    $("connection").className = "status live";
    $("connection").innerHTML = "<i></i>实时连接";
  } catch (_) {
    $("connection").className = "status error";
    $("connection").innerHTML = "<i></i>连接断开";
  }
}

async function pollMapping() {
  try {
    const response = await fetch("/api/screen/mapping", { cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    renderMapping(payload.mapping || {});
  } catch (_) {}
}

async function pollCalibration() {
  try {
    const response = await fetch("/api/tobii/calibration", { cache: "no-store" });
    if (!response.ok) return;
    const calibration = (await response.json()).calibration || {};
    const status = calibration.status || "unavailable";
    setChip("tobiiCalibrationStatus", status);
    const button = $("tobiiCalibrate");
    button.disabled = !calibration.connected || ["requested", "running"].includes(status);
    button.title = calibration.detail || "Wear the glasses and look at the Tobii calibration target";
  } catch (_) {
    $("tobiiCalibrate").disabled = true;
  }
}

async function startTobiiCalibration() {
  if (!window.confirm("请确认被试已正确佩戴眼镜，并正在注视 Tobii 官方校准目标中心。")) return;
  const button = $("tobiiCalibrate");
  button.disabled = true;
  setChip("tobiiCalibrationStatus", "requested");
  try {
    const response = await fetch("/api/tobii/calibration", {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.error || `HTTP ${response.status}`);
    setChip("tobiiCalibrationStatus", payload.calibration?.status || "requested");
  } catch (error) {
    setChip("tobiiCalibrationStatus", "failed");
    button.title = error.message;
  }
}

function activateView(viewName) {
  document.querySelectorAll("[data-view-tab]").forEach((item) => {
    item.classList.toggle("active", item.dataset.viewTab === viewName);
  });
  document.querySelectorAll("[data-monitor-view]").forEach((view) => {
    const active = view.dataset.monitorView === viewName;
    view.classList.toggle("active", active);
    view.hidden = !active;
  });
  drawChart();
  syncExperimentMirror(latestMapping.layout);
  drawScreenTrajectory(latestMapping);
}

document.querySelectorAll("[data-view-tab]").forEach((button) => {
  button.addEventListener("click", () => activateView(button.dataset.viewTab));
});

$("experimentMirror").addEventListener("load", () => syncExperimentMirror(latestMapping.layout));
$("tobiiCalibrate").addEventListener("click", startTobiiCalibration);
$("copyJson").addEventListener("click", async () => {
  await navigator.clipboard.writeText(
    JSON.stringify({ ...latestPayload, screen_mapping: latestMapping }, null, 2),
  );
  $("copyJson").textContent = "已复制";
  setTimeout(() => { $("copyJson").textContent = "复制 JSON"; }, 1200);
});
window.addEventListener("resize", () => {
  drawChart();
  syncExperimentMirror(latestMapping.layout);
  drawScreenTrajectory(latestMapping);
});

pollState();
pollMapping();
pollCalibration();
const requestedView = new URLSearchParams(window.location.search).get("view");
if (["gaze", "eeg", "policy"].includes(requestedView)) activateView(requestedView);
async function schedule(task, delayMs) {
  await task();
  window.setTimeout(() => schedule(task, delayMs), delayMs);
}

window.setTimeout(() => schedule(pollState, 250), 250);
window.setTimeout(() => schedule(pollMapping, 60), 60);
window.setTimeout(() => schedule(pollCalibration, 500), 500);
