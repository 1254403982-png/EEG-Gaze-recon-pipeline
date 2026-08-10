"""Versioned data contracts for every boundary in the realtime pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .clock import Timestamp

SCHEMA_VERSION = "1.0"


class SignalStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    WARNING = "warning"


@dataclass
class EyeFeatures:
    """AOI eye metrics exposed to the adaptive policy.

    ``aoi_revisit_time`` is measured in seconds and counts only time spent in
    AOI visits after the first visit in the current gaze window.
    """

    aoi_dwell_time: Optional[float] = None
    fixation_count: Optional[int] = None
    mean_fixation_duration: Optional[float] = None
    aoi_revisit_count: Optional[int] = None
    aoi_revisit_time: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EEGFeatures:
    timestamp: Timestamp
    status: SignalStatus
    quality: str
    cognitive_load: Optional[float] = None
    attention: Optional[float] = None
    alpha_power: Optional[float] = None
    alpha_peak_hz: Optional[float] = None
    alpha_suppression: Optional[float] = None
    frontal_theta_power: Optional[float] = None
    posterior_alpha_power: Optional[float] = None
    workload_index: Optional[float] = None
    bad_channels: List[str] = field(default_factory=list)
    source: str = "brainco"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.to_dict()
        payload["status"] = self.status.value
        return payload


@dataclass
class GazeFeatures:
    timestamp: Timestamp
    status: SignalStatus
    quality: str
    x_normalized: Optional[float] = None
    y_normalized: Optional[float] = None
    primary_aoi: Optional[str] = None
    fixation_duration_ms: Optional[float] = None
    fixation_rate: Optional[float] = None
    saccade_rate: Optional[float] = None
    pupil_dilation: Optional[float] = None
    gaze_entropy: Optional[float] = None
    blink_rate: Optional[float] = None
    valid_sample_ratio: Optional[float] = None
    source: str = "gaze"
    metadata: Dict[str, Any] = field(default_factory=dict)
    eye: EyeFeatures = field(default_factory=EyeFeatures)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.to_dict()
        payload["status"] = self.status.value
        return payload


@dataclass
class UIContext:
    phase: str = "idle"
    slide_id: Optional[str] = None
    seconds_in_trial: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MultimodalState:
    session_id: str
    trial_id: Optional[str]
    condition: int
    timestamp: Timestamp
    eeg: EEGFeatures
    gaze: GazeFeatures
    ui: UIContext = field(default_factory=UIContext)

    def to_dict(self) -> dict:
        comparable = self.eeg.status in {
            SignalStatus.AVAILABLE,
            SignalStatus.WARNING,
        } and self.gaze.status in {SignalStatus.AVAILABLE, SignalStatus.WARNING}
        delta_ms = None
        if comparable:
            delta_ms = (
                (self.eeg.timestamp.host_monotonic_ns - self.gaze.timestamp.host_monotonic_ns)
                / 1_000_000.0
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "session_id": self.session_id,
            "trial_id": self.trial_id,
            "condition": self.condition,
            "timestamp": self.timestamp.to_dict(),
            "eeg": self.eeg.to_dict(),
            "gaze": self.gaze.to_dict(),
            "eye": self.gaze.eye.to_dict(),
            "ui": asdict(self.ui),
            "synchronization": {
                "clock": "host_monotonic",
                "method": "sample_or_chunk_receive_time",
                "comparable": comparable,
                "eeg_minus_gaze_ms": delta_ms,
                "absolute_skew_ms": abs(delta_ms) if delta_ms is not None else None,
            },
        }


@dataclass
class PolicyDecision:
    policy_id: int
    session_id: str
    trial_id: Optional[str]
    condition: int
    timestamp: Timestamp
    action: str
    explanation_level: str
    ui_mode: str
    reason_codes: List[str]
    sources_available: List[str]
    sources_used: List[str]
    target_aoi: Optional[str] = None
    difficulty_score: Optional[float] = None
    component_scores: Dict[str, float] = field(default_factory=dict)
    evidence_duration_seconds: float = 0.0
    confidence: float = 0.0
    degraded_mode: Optional[str] = None
    suppressed: bool = False

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["schema_version"] = SCHEMA_VERSION
        payload["timestamp"] = self.timestamp.to_dict()
        return payload
