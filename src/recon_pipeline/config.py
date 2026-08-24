"""Typed configuration loading with explicit validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8810


@dataclass(frozen=True)
class SynchronizationConfig:
    max_eeg_age_ms: int = 2500
    max_gaze_age_ms: int = 1500


@dataclass(frozen=True)
class PolicyConfig:
    # v1 preserves the frozen/original C3 fusion rule. v2 requires concordant
    # Eye+EEG evidence and is enabled only by an explicit alternate config.
    c3_policy_version: str = "v1"
    cooldown_seconds: float = 45.0
    required_confirmations: int = 3
    minimum_evidence_seconds: float = 0.45
    # Do not offer help while the participant is still orienting to the page.
    minimum_trial_seconds: float = 15.0
    # 0 means unlimited automatic offers; a positive value enables a per-trial cap.
    max_automatic_offers_per_trial: int = 0
    allow_degraded_c3: bool = False
    require_screen_mapping: bool = False
    gaze_min_valid_ratio: float = 0.70
    max_multimodal_skew_ms: float = 500.0
    require_joint_c3_evidence: bool = True
    brief_threshold: float = 50.0
    example_threshold: float = 65.0
    detailed_threshold: float = 78.0
    eeg_weight: float = 0.65
    gaze_weight: float = 0.35
    gaze_pupil_weight: float = 0.30
    gaze_entropy_weight: float = 0.25
    gaze_fixation_weight: float = 0.30
    gaze_blink_weight: float = 0.15
    fixation_reference_ms: float = 1500.0
    eye_baseline_seconds: float = 10.0
    eye_baseline_min_samples: int = 5
    eye_dwell_weight: float = 0.40
    eye_fixation_weight: float = 0.30
    eye_duration_weight: float = 0.30
    eye_revisit_count_weight: float = 0.15
    eye_revisit_time_weight: float = 0.15
    eye_abnormal_ratio: float = 1.35
    eye_single_feature_ratio: float = 1.55
    eye_mild_threshold: float = 1.30
    eye_moderate_threshold: float = 1.35
    eye_strong_threshold: float = 1.85
    # Optional C2-only overrides.  None preserves the shared Eye setting for
    # backwards-compatible configs and unit tests.
    c2_eye_abnormal_ratio: float | None = None
    c2_eye_single_feature_ratio: float | None = None
    c2_eye_mild_threshold: float | None = None
    c2_eye_moderate_threshold: float | None = None
    c2_eye_strong_threshold: float | None = None
    c2_cooldown_seconds: float | None = None
    c2_max_automatic_offers_per_trial: int | None = None
    eeg_medium_threshold: float = 40.0
    eeg_high_threshold: float = 70.0
    attention_low_threshold: float = 40.0


@dataclass(frozen=True)
class BrainCoConfig:
    address: str = ""
    port: int = 0
    auto_discover: bool = True
    scan_timeout_seconds: float = 6.0
    ready_timeout_seconds: float = 10.0
    start_retries: int = 2
    gain: int = 6
    signal_source: str = "NORMAL"
    enable_imu: bool = False
    device_id: str = "eeg-cap"


@dataclass(frozen=True)
class EEGDecoderConfig:
    decoder_id: str
    decoder_type: str
    channels: Tuple[str, ...]
    options: Dict[str, Any]


@dataclass(frozen=True)
class EEGProcessingConfig:
    sampling_rate_hz: float = 250.0
    window_seconds: float = 4.0
    max_buffer_seconds: float = 90.0
    bandpass_low_hz: float = 1.0
    bandpass_high_hz: float = 45.0
    primary_decoder: str = "posterior_alpha"
    decoders: Tuple[EEGDecoderConfig, ...] = ()
    quality: Dict[str, Any] = field(default_factory=dict)
    brainco: BrainCoConfig = field(default_factory=BrainCoConfig)


@dataclass(frozen=True)
class StorageConfig:
    run_dir: Path = Path("runs")
    event_log: Path = Path("runs/events.jsonl")
    policy_log: Path = Path("runs/policies.jsonl")
    experiment_data_dir: Path = Path("runs/experiment_data")
    raw_eeg_dir: Path = Path("runs/raw_eeg")
    raw_eeg_chunk_seconds: float = 10.0
    raw_gaze_log: Path = Path("runs/raw_gaze.jsonl")


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = True
    endpoint: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    api_key_env: str = "DASHSCOPE_API_KEY"
    default_model: str = "qwen-vl-max"
    timeout_seconds: int = 60


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    synchronization: SynchronizationConfig
    policy: PolicyConfig
    eeg: EEGProcessingConfig
    storage: StorageConfig
    llm: LLMConfig


def _section(payload: Dict[str, Any], name: str) -> Dict[str, Any]:
    value = payload.get(name, {})
    if not isinstance(value, dict):
        raise ValueError("Configuration section '%s' must be an object." % name)
    return value


def load_config(path: Path) -> AppConfig:
    source = path.expanduser().resolve()
    payload = _load_config_payload(source)
    if not isinstance(payload, dict):
        raise ValueError("Configuration root must be a JSON object.")

    server = ServerConfig(**_section(payload, "server"))
    synchronization = SynchronizationConfig(**_section(payload, "synchronization"))
    policy = PolicyConfig(**_section(payload, "policy"))
    eeg = _load_eeg_config(_section(payload, "eeg"))
    storage_values = _section(payload, "storage")
    storage = StorageConfig(
        run_dir=Path(storage_values.get("run_dir", "runs")),
        event_log=Path(storage_values.get("event_log", "runs/events.jsonl")),
        policy_log=Path(storage_values.get("policy_log", "runs/policies.jsonl")),
        experiment_data_dir=Path(storage_values.get("experiment_data_dir", "runs/experiment_data")),
        raw_eeg_dir=Path(storage_values.get("raw_eeg_dir", "runs/raw_eeg")),
        raw_eeg_chunk_seconds=float(storage_values.get("raw_eeg_chunk_seconds", 10.0)),
        raw_gaze_log=Path(storage_values.get("raw_gaze_log", "runs/raw_gaze.jsonl")),
    )
    llm = LLMConfig(**_section(payload, "llm"))
    if not 1 <= server.port <= 65535:
        raise ValueError("server.port must be between 1 and 65535.")
    if policy.required_confirmations < 1:
        raise ValueError("policy.required_confirmations must be at least 1.")
    if policy.c3_policy_version not in {"v1", "v2"}:
        raise ValueError("policy.c3_policy_version must be 'v1' or 'v2'.")
    if policy.minimum_evidence_seconds < 0:
        raise ValueError("policy.minimum_evidence_seconds must be non-negative.")
    if policy.minimum_trial_seconds < 0:
        raise ValueError("policy.minimum_trial_seconds must be non-negative.")
    if policy.max_automatic_offers_per_trial < 0:
        raise ValueError("policy.max_automatic_offers_per_trial must be non-negative.")
    if not (
        0 <= policy.brief_threshold < policy.example_threshold < policy.detailed_threshold <= 100
    ):
        raise ValueError("policy thresholds must be ordered between 0 and 100.")
    if (
        policy.eeg_weight < 0
        or policy.gaze_weight < 0
        or policy.eeg_weight + policy.gaze_weight <= 0
    ):
        raise ValueError("policy EEG/gaze weights must be non-negative with a positive sum.")
    gaze_weights = (
        policy.gaze_pupil_weight,
        policy.gaze_entropy_weight,
        policy.gaze_fixation_weight,
        policy.gaze_blink_weight,
    )
    if any(weight < 0 for weight in gaze_weights) or sum(gaze_weights) <= 0:
        raise ValueError("policy gaze feature weights must have a positive sum.")
    if policy.fixation_reference_ms <= 0:
        raise ValueError("policy.fixation_reference_ms must be positive.")
    if not 0 <= policy.gaze_min_valid_ratio <= 1:
        raise ValueError("policy.gaze_min_valid_ratio must be between 0 and 1.")
    if policy.max_multimodal_skew_ms <= 0:
        raise ValueError("policy.max_multimodal_skew_ms must be positive.")
    if policy.eye_baseline_seconds < 0 or policy.eye_baseline_min_samples < 1:
        raise ValueError("policy eye baseline duration/sample count is invalid.")
    eye_weights = (
        policy.eye_dwell_weight,
        policy.eye_fixation_weight,
        policy.eye_duration_weight,
        policy.eye_revisit_count_weight,
        policy.eye_revisit_time_weight,
    )
    if any(weight < 0 for weight in eye_weights) or sum(eye_weights) <= 0:
        raise ValueError("policy eye feature weights must have a positive sum.")
    if not (
        1 <= policy.eye_mild_threshold
        < policy.eye_moderate_threshold
        < policy.eye_strong_threshold
    ):
        raise ValueError("policy eye ratio thresholds must be ordered above baseline.")
    if policy.eye_abnormal_ratio < 1:
        raise ValueError("policy.eye_abnormal_ratio must be at least 1.")
    if policy.eye_single_feature_ratio < policy.eye_abnormal_ratio:
        raise ValueError(
            "policy.eye_single_feature_ratio must not be below eye_abnormal_ratio."
        )
    c2_abnormal = policy.c2_eye_abnormal_ratio
    c2_single = policy.c2_eye_single_feature_ratio
    c2_mild = policy.c2_eye_mild_threshold
    c2_moderate = policy.c2_eye_moderate_threshold
    c2_strong = policy.c2_eye_strong_threshold
    c2_eye_values = (c2_abnormal, c2_single, c2_mild, c2_moderate, c2_strong)
    if any(value is not None for value in c2_eye_values):
        if not all(value is not None for value in c2_eye_values):
            raise ValueError("all C2 Eye threshold overrides must be supplied together.")
        assert c2_abnormal is not None and c2_single is not None
        assert c2_mild is not None and c2_moderate is not None and c2_strong is not None
        if not (1 <= c2_mild < c2_moderate < c2_strong):
            raise ValueError("C2 Eye ratio thresholds must be ordered above baseline.")
        if c2_abnormal < 1 or c2_single < c2_abnormal:
            raise ValueError("C2 Eye abnormal/single-feature thresholds are invalid.")
    if policy.c2_cooldown_seconds is not None and policy.c2_cooldown_seconds < 0:
        raise ValueError("policy.c2_cooldown_seconds must be non-negative.")
    if (
        policy.c2_max_automatic_offers_per_trial is not None
        and policy.c2_max_automatic_offers_per_trial < 0
    ):
        raise ValueError("policy.c2_max_automatic_offers_per_trial must be non-negative.")
    if not (
        0 <= policy.eeg_medium_threshold
        < policy.eeg_high_threshold
        <= 100
        and 0 <= policy.attention_low_threshold <= 100
    ):
        raise ValueError("policy EEG/attention thresholds must be ordered between 0 and 100.")
    if eeg.sampling_rate_hz <= 0 or eeg.window_seconds <= 0 or eeg.max_buffer_seconds <= 0:
        raise ValueError("EEG sampling rate and buffer durations must be positive.")
    decoder_ids = [decoder.decoder_id for decoder in eeg.decoders]
    if len(set(decoder_ids)) != len(decoder_ids):
        raise ValueError("EEG decoder IDs must be unique.")
    if eeg.primary_decoder not in decoder_ids:
        raise ValueError("eeg.primary_decoder must identify one configured decoder.")
    if storage.raw_eeg_chunk_seconds <= 0:
        raise ValueError("storage.raw_eeg_chunk_seconds must be positive.")
    return AppConfig(server, synchronization, policy, eeg, storage, llm)


def _load_config_payload(source: Path, chain: Tuple[Path, ...] = ()) -> Dict[str, Any]:
    """Load a config with optional, relative JSON inheritance.

    Alternate research policies can override only the fields under study while
    the frozen acquisition/LLM configuration remains inherited and auditable.
    """

    if source in chain:
        raise ValueError("Configuration inheritance cycle detected: %s" % source)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Configuration root must be a JSON object.")
    parent_name = payload.pop("extends", None)
    if parent_name is None:
        return payload
    if not isinstance(parent_name, str) or not parent_name.strip():
        raise ValueError("Configuration 'extends' must be a non-empty relative path.")
    parent_path = (source.parent / parent_name).resolve()
    parent = _load_config_payload(parent_path, (*chain, source))
    return _deep_merge(parent, payload)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_eeg_config(values: Dict[str, Any]) -> EEGProcessingConfig:
    decoder_values = values.get("decoders")
    if decoder_values is None:
        decoder_values = [
            {
                "id": "posterior_alpha",
                "type": "posterior_alpha",
                "channels": ["P3", "P4", "P7", "P8", "PZ", "O1", "O2"],
                "options": {},
            }
        ]
    if not isinstance(decoder_values, list) or not decoder_values:
        raise ValueError("eeg.decoders must be a non-empty array.")
    decoders = []
    for index, item in enumerate(decoder_values):
        if not isinstance(item, dict):
            raise ValueError("eeg.decoders[%s] must be an object." % index)
        channels = item.get("channels", [])
        options = item.get("options", {})
        if not isinstance(channels, list) or not channels:
            raise ValueError("eeg.decoders[%s].channels must be a non-empty array." % index)
        if not isinstance(options, dict):
            raise ValueError("eeg.decoders[%s].options must be an object." % index)
        decoder_id = str(item.get("id", "")).strip()
        decoder_type = str(item.get("type", "")).strip()
        if not decoder_id or not decoder_type:
            raise ValueError("Every EEG decoder requires non-empty id and type.")
        decoders.append(
            EEGDecoderConfig(
                decoder_id=decoder_id,
                decoder_type=decoder_type,
                channels=tuple(str(channel).strip().upper() for channel in channels),
                options=dict(options),
            )
        )
    quality = values.get("quality", {})
    brainco_values = values.get("brainco", {})
    if not isinstance(quality, dict) or not isinstance(brainco_values, dict):
        raise ValueError("eeg.quality and eeg.brainco must be objects.")
    return EEGProcessingConfig(
        sampling_rate_hz=float(values.get("sampling_rate_hz", 250.0)),
        window_seconds=float(values.get("window_seconds", 4.0)),
        max_buffer_seconds=float(values.get("max_buffer_seconds", 90.0)),
        bandpass_low_hz=float(values.get("bandpass_low_hz", 1.0)),
        bandpass_high_hz=float(values.get("bandpass_high_hz", 45.0)),
        primary_decoder=str(values.get("primary_decoder", "posterior_alpha")),
        decoders=tuple(decoders),
        quality=dict(quality),
        brainco=BrainCoConfig(**brainco_values),
    )
