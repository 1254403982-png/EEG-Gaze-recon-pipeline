"""Auditable Eye/EEG policy rules with source isolation and stabilization."""

from __future__ import annotations

import threading
import time
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from ..clock import Timestamp
from ..config import PolicyConfig
from ..models import EyeFeatures, GazeFeatures, MultimodalState, PolicyDecision, SignalStatus

_SEVERITY = {"none": 0, "brief": 1, "example": 2, "detailed": 3}


class MultimodalPolicyEngine:
    """Generate a platform action without silently crossing condition boundaries."""

    def __init__(self, config: PolicyConfig) -> None:
        self.config = config
        self._lock = threading.Lock()
        self._next_policy_id = 1
        self._candidate_level = "none"
        self._candidate_count = 0
        self._candidate_since = 0.0
        self._last_emitted_level = "none"
        self._last_emitted_at = 0.0
        self._eye_baseline_samples: List[Tuple[int, EyeFeatures]] = []
        self._eye_baseline: Optional[EyeFeatures] = None
        self._last_baseline_gaze_ns: Optional[int] = None
        self._active_trial_key: Optional[Tuple[str, Optional[str], int]] = None
        self._trial_offer_count = 0

    def reset(self) -> None:
        with self._lock:
            self._candidate_level = "none"
            self._candidate_count = 0
            self._candidate_since = 0.0
            self._last_emitted_level = "none"
            self._last_emitted_at = 0.0
            self._eye_baseline_samples = []
            self._eye_baseline = None
            self._last_baseline_gaze_ns = None
            self._active_trial_key = None
            self._trial_offer_count = 0

    def release_offer(self, trial_id: Optional[str] = None) -> None:
        """Allow a new evidence episode after the participant answered an offer.

        Acknowledging that the browser received an offer must not immediately
        re-open the same prompt.  The response itself closes the current
        episode; the normal cooldown and stabilization gates still apply.
        """

        with self._lock:
            if self._active_trial_key is None:
                return
            if trial_id is not None and self._active_trial_key[1] != trial_id:
                return
            self._last_emitted_level = "none"
            self._candidate_level = "none"
            self._candidate_count = 0
            self._candidate_since = 0.0

    def evaluate(self, state: MultimodalState) -> PolicyDecision:
        with self._lock:
            decision = self._evaluate_unlocked(state)
            decision.policy_id = self._next_policy_id
            self._next_policy_id += 1
            return decision

    def _evaluate_unlocked(self, state: MultimodalState) -> PolicyDecision:
        self._enter_trial(state)
        eeg_valid = (
            state.eeg.status == SignalStatus.AVAILABLE
            and state.eeg.quality == "pass"
            and state.eeg.cognitive_load is not None
        )
        gaze_valid = state.gaze.status == SignalStatus.AVAILABLE and state.gaze.quality == "pass"
        available = []
        if eeg_valid:
            available.append("eeg")
        if gaze_valid and _eye_complete(state.gaze.eye):
            available.append("eye")

        if state.ui.phase.strip().lower() != "reading":
            self._candidate_level = "none"
            self._candidate_count = 0
            self._candidate_since = 0.0
            return self._decision(
                state,
                level="none",
                action="no_adaptation",
                ui_mode="normal",
                reasons=["ui_phase_policy_disabled"],
                available=available,
                used=[],
                suppressed=True,
            )

        if bool(state.ui.metadata.get("policy_suppressed")):
            self._candidate_level = "none"
            self._candidate_count = 0
            self._candidate_since = 0.0
            return self._decision(
                state,
                level="none",
                action="no_adaptation",
                ui_mode="normal",
                reasons=[
                    "ui_policy_suppressed",
                    str(state.ui.metadata.get("policy_suppression_reason") or "unspecified"),
                ],
                available=available,
                used=[],
                suppressed=True,
            )

        if state.condition == 1:
            return self._decision(
                state,
                level="none",
                action="no_adaptation",
                ui_mode="normal",
                reasons=["condition_c1_policy_disabled"],
                available=available,
                used=[],
            )

        if not gaze_valid or not _eye_complete(state.gaze.eye):
            return self._insufficient(state, available, "required_eye_unavailable")
        gaze_gate = _gaze_gate_reason(state.gaze, self.config, state)
        if gaze_gate is not None:
            return self._insufficient(state, available, gaze_gate)

        # Collect the personal Eye baseline during the initial orientation
        # window.  The window still suppresses offers, but it must not postpone
        # baseline collection until after the window or every Trial would lose
        # another eye_baseline_seconds before it can ever trigger.
        if self._eye_baseline is None:
            self._collect_eye_baseline(state.gaze)

        # The first part of each material is an orientation/baseline window.
        # Do not let an unstable initial gaze or EEG window create a prompt;
        # the browser keeps seconds_in_trial updated while the participant reads.
        elapsed = state.ui.seconds_in_trial
        # The first policy poll can arrive before the browser has posted its
        # first UI-context heartbeat. Treat an unknown elapsed time as the
        # beginning of the Trial instead of allowing an early offer.
        if elapsed is None or elapsed < self.config.minimum_trial_seconds:
            self._candidate_level = "none"
            self._candidate_count = 0
            self._candidate_since = 0.0
            component_scores = {
                "seconds_in_trial": float(elapsed or 0.0),
                "minimum_trial_seconds": float(self.config.minimum_trial_seconds),
                "eye_baseline_samples": float(len(self._eye_baseline_samples)),
            }
            if self._eye_baseline is not None:
                component_scores["eye_baseline_ready"] = 1.0
            return self._decision(
                state,
                level="none",
                action="hold",
                ui_mode="normal",
                reasons=["trial_reading_baseline_window"],
                available=available,
                used=[],
                confidence=0.0,
                degraded="trial_baseline_collecting",
                component_scores=component_scores,
                suppressed=True,
            )

        if self._eye_baseline is None:
            return self._baseline_hold(state, available)

        eye_score, eye_level, eye_components, eye_reasons = _eye_difficulty(
            state.gaze.eye,
            self._eye_baseline,
            self.config,
            condition=state.condition,
        )
        score = eye_score
        level = eye_level
        used = ["eye"]
        reasons = eye_reasons
        degraded: Optional[str] = None
        confidence = 0.75
        component_scores = eye_components

        if state.condition == 3:
            if not eeg_valid:
                if not self.config.allow_degraded_c3:
                    return self._insufficient(state, available, "required_eeg_unavailable")
                degraded = "eye_only_low_eeg_quality"
                confidence = 0.65
                reasons = [*reasons, "eeg_quality_low_eye_only"]
                component_scores = {
                    **component_scores,
                    "eye_level": float(_SEVERITY[eye_level]),
                    "eeg_quality_confidence": 0.0,
                    "final_difficulty_score": float(_SEVERITY[eye_level]),
                }
                score = float(_SEVERITY[eye_level])
            else:
                skew_ms = abs(
                    state.eeg.timestamp.host_monotonic_ns
                    - state.gaze.timestamp.host_monotonic_ns
                ) / 1_000_000.0
                if skew_ms > self.config.max_multimodal_skew_ms:
                    return self._insufficient(
                        state, available, "multimodal_receive_time_skew_too_large"
                    )
                eeg_level, eeg_reasons = _eeg_level(state, self.config)
                eye_level_value = _SEVERITY[eye_level]
                weight_total = self.config.eeg_weight + self.config.gaze_weight
                final_score = (
                    self.config.gaze_weight * eye_level_value
                    + self.config.eeg_weight * eeg_level
                ) / weight_total
                level, fusion_reason = _c3_level(
                    eye_level_value,
                    eeg_level,
                    version=self.config.c3_policy_version,
                )
                score = final_score
                used = ["eye", "eeg"]
                reasons = [*eye_reasons, *eeg_reasons, fusion_reason]
                confidence = 0.85
                component_scores = {
                    **component_scores,
                    "eye_level": float(eye_level_value),
                    "eeg_level": float(eeg_level),
                    "eeg_quality_confidence": 1.0,
                    "final_difficulty_score": final_score,
                }

        target_aoi = state.gaze.primary_aoi
        offer_limit = _offer_limit(self.config, state.condition)
        if (
            level != "none"
            and offer_limit > 0
            and self._trial_offer_count >= offer_limit
        ):
            return self._decision(
                state,
                level="none",
                action="hold",
                ui_mode="normal",
                reasons=[*reasons, "trial_offer_budget_reached"],
                available=available,
                used=used,
                confidence=confidence,
                degraded=degraded,
                target_aoi=target_aoi,
                difficulty_score=score,
                component_scores={
                    **component_scores,
                    "trial_offer_count": float(self._trial_offer_count),
                    "trial_offer_limit": float(offer_limit),
                },
                suppressed=True,
            )
        return self._stabilize(
            state,
            level=level,
            score=score,
            reasons=_unique(reasons),
            available=available,
            used=used,
            confidence=confidence,
            degraded=degraded,
            target_aoi=target_aoi,
            component_scores=component_scores,
        )

    def _enter_trial(self, state: MultimodalState) -> None:
        trial_key = (state.session_id, state.trial_id, state.condition)
        if trial_key == self._active_trial_key:
            return
        self._active_trial_key = trial_key
        self._trial_offer_count = 0
        self._candidate_level = "none"
        self._candidate_count = 0
        self._candidate_since = 0.0
        self._last_emitted_level = "none"
        self._last_emitted_at = 0.0

    def _collect_eye_baseline(self, gaze: GazeFeatures) -> None:
        timestamp_ns = gaze.timestamp.host_monotonic_ns
        if timestamp_ns == self._last_baseline_gaze_ns:
            return
        self._last_baseline_gaze_ns = timestamp_ns
        self._eye_baseline_samples.append((timestamp_ns, gaze.eye))
        self._eye_baseline_samples = self._eye_baseline_samples[-1000:]
        samples = self._eye_baseline_samples
        span_seconds = (
            (samples[-1][0] - samples[0][0]) / 1_000_000_000.0 if len(samples) >= 2 else 0.0
        )
        if (
            len(samples) < self.config.eye_baseline_min_samples
            or span_seconds < self.config.eye_baseline_seconds
        ):
            return
        dwell = _positive_median(sample.aoi_dwell_time for _, sample in samples)
        count = _positive_median(sample.fixation_count for _, sample in samples)
        duration = _positive_median(sample.mean_fixation_duration for _, sample in samples)
        revisit_count = _nonnegative_median(sample.aoi_revisit_count for _, sample in samples)
        revisit_time = _nonnegative_median(sample.aoi_revisit_time for _, sample in samples)
        if dwell is None or count is None or duration is None:
            return
        self._eye_baseline = EyeFeatures(
            aoi_dwell_time=dwell,
            fixation_count=max(1, round(count)),
            mean_fixation_duration=duration,
            aoi_revisit_count=(
                max(0, round(revisit_count)) if revisit_count is not None else None
            ),
            aoi_revisit_time=(
                max(0.0, revisit_time) if revisit_time is not None else None
            ),
        )

    def _baseline_hold(self, state: MultimodalState, available: List[str]) -> PolicyDecision:
        samples = self._eye_baseline_samples
        progress = (
            (samples[-1][0] - samples[0][0]) / 1_000_000_000.0 if len(samples) >= 2 else 0.0
        )
        return self._decision(
            state,
            level="none",
            action="hold",
            ui_mode="normal",
            reasons=["eye_personal_baseline_collecting"],
            available=available,
            used=[],
            confidence=0.0,
            degraded="baseline_collecting",
            component_scores={
                "eye_baseline_progress_seconds": progress,
                "eye_baseline_samples": float(len(samples)),
            },
            suppressed=True,
        )

    def _stabilize(
        self,
        state: MultimodalState,
        *,
        level: str,
        score: float,
        reasons: List[str],
        available: List[str],
        used: List[str],
        confidence: float,
        degraded: Optional[str],
        target_aoi: Optional[str],
        component_scores: Optional[Dict[str, float]] = None,
    ) -> PolicyDecision:
        now = time.monotonic()
        if level == self._candidate_level:
            self._candidate_count += 1
        else:
            self._candidate_level, self._candidate_count = level, 1
            self._candidate_since = now

        evidence_seconds = max(0.0, now - self._candidate_since)
        if level != "none" and (
            self._candidate_count < self.config.required_confirmations
            or evidence_seconds < self.config.minimum_evidence_seconds
        ):
            return self._decision(
                state,
                level="none",
                action="hold",
                ui_mode="normal",
                reasons=[*reasons, "awaiting_sustained_evidence"],
                available=available,
                used=used,
                confidence=confidence,
                degraded=degraded,
                target_aoi=target_aoi,
                difficulty_score=score,
                component_scores=component_scores,
                evidence_duration_seconds=evidence_seconds,
                suppressed=True,
            )

        is_escalation = _SEVERITY[level] > _SEVERITY[self._last_emitted_level]
        cooldown_seconds = _cooldown_seconds(self.config, state.condition)
        cooling_down = now - self._last_emitted_at < cooldown_seconds
        if is_escalation and cooling_down:
            return self._decision(
                state,
                level=self._last_emitted_level,
                action="hold",
                ui_mode=_ui_mode(self._last_emitted_level),
                reasons=[*reasons, "policy_cooldown"],
                available=available,
                used=used,
                confidence=confidence,
                degraded=degraded,
                target_aoi=target_aoi,
                difficulty_score=score,
                component_scores=component_scores,
                evidence_duration_seconds=evidence_seconds,
                suppressed=True,
            )

        if level != "none" and level == self._last_emitted_level:
            return self._decision(
                state,
                level=level,
                action="hold",
                ui_mode=_ui_mode(level),
                reasons=[*reasons, "already_emitted_for_current_episode"],
                available=available,
                used=used,
                confidence=confidence,
                degraded=degraded,
                target_aoi=target_aoi,
                difficulty_score=score,
                component_scores=component_scores,
                evidence_duration_seconds=evidence_seconds,
                suppressed=True,
            )

        if level != self._last_emitted_level:
            self._last_emitted_level = level
        if level != "none":
            self._last_emitted_at = now
            self._trial_offer_count += 1
            component_scores = {
                **(component_scores or {}),
                "trial_offer_count": float(self._trial_offer_count),
                "trial_offer_limit": float(_offer_limit(self.config, state.condition)),
            }
        reasons.append("difficulty_score_%.1f" % score)
        return self._decision(
            state,
            level=level,
            action=_action(level),
            ui_mode=_ui_mode(level),
            reasons=reasons,
            available=available,
            used=used,
            confidence=confidence,
            degraded=degraded,
            target_aoi=target_aoi,
            difficulty_score=score,
            component_scores=component_scores,
            evidence_duration_seconds=evidence_seconds,
        )

    def _insufficient(
        self, state: MultimodalState, available: List[str], reason: str
    ) -> PolicyDecision:
        self._candidate_level = "none"
        self._candidate_count = 0
        self._candidate_since = 0.0
        return self._decision(
            state,
            level="none",
            action="hold",
            ui_mode="normal",
            reasons=[reason],
            available=available,
            used=[],
            confidence=0.0,
            degraded="insufficient_input",
            suppressed=True,
        )

    @staticmethod
    def _decision(
        state: MultimodalState,
        *,
        level: str,
        action: str,
        ui_mode: str,
        reasons: List[str],
        available: List[str],
        used: List[str],
        confidence: float = 0.0,
        degraded: Optional[str] = None,
        target_aoi: Optional[str] = None,
        difficulty_score: Optional[float] = None,
        component_scores: Optional[Dict[str, float]] = None,
        evidence_duration_seconds: float = 0.0,
        suppressed: bool = False,
    ) -> PolicyDecision:
        return PolicyDecision(
            policy_id=0,
            session_id=state.session_id,
            trial_id=state.trial_id,
            condition=state.condition,
            timestamp=Timestamp.now(),
            action=action,
            explanation_level=level,
            ui_mode=ui_mode,
            reason_codes=_unique(reasons),
            sources_available=available,
            sources_used=used,
            target_aoi=target_aoi,
            difficulty_score=difficulty_score,
            component_scores=dict(component_scores or {}),
            evidence_duration_seconds=evidence_duration_seconds,
            confidence=confidence,
            degraded_mode=degraded,
            suppressed=suppressed,
        )


def _eye_complete(eye: EyeFeatures) -> bool:
    return (
        eye.aoi_dwell_time is not None
        and eye.fixation_count is not None
        and eye.mean_fixation_duration is not None
    )


def _eye_thresholds(
    config: PolicyConfig, condition: int
) -> Tuple[float, float, float, float, float]:
    if condition == 2 and config.c2_eye_mild_threshold is not None:
        return (
            float(config.c2_eye_abnormal_ratio),
            float(config.c2_eye_single_feature_ratio),
            float(config.c2_eye_mild_threshold),
            float(config.c2_eye_moderate_threshold),
            float(config.c2_eye_strong_threshold),
        )
    return (
        config.eye_abnormal_ratio,
        config.eye_single_feature_ratio,
        config.eye_mild_threshold,
        config.eye_moderate_threshold,
        config.eye_strong_threshold,
    )


def _offer_limit(config: PolicyConfig, condition: int) -> int:
    if condition == 2 and config.c2_max_automatic_offers_per_trial is not None:
        return int(config.c2_max_automatic_offers_per_trial)
    return int(config.max_automatic_offers_per_trial)


def _cooldown_seconds(config: PolicyConfig, condition: int) -> float:
    if condition == 2 and config.c2_cooldown_seconds is not None:
        return float(config.c2_cooldown_seconds)
    return float(config.cooldown_seconds)


def _eye_difficulty(
    eye: EyeFeatures,
    baseline: EyeFeatures,
    config: PolicyConfig,
    *,
    condition: int = 3,
) -> Tuple[float, str, Dict[str, float], List[str]]:
    abnormal_ratio, single_ratio, mild, moderate, strong = _eye_thresholds(
        config, condition
    )
    assert _eye_complete(eye) and _eye_complete(baseline)
    dwell_ratio = float(eye.aoi_dwell_time) / float(baseline.aoi_dwell_time)
    fixation_ratio = float(eye.fixation_count) / float(baseline.fixation_count)
    duration_ratio = float(eye.mean_fixation_duration) / float(
        baseline.mean_fixation_duration
    )
    core_ratios = {
        "aoi_dwell_ratio": dwell_ratio,
        "fixation_count_ratio": fixation_ratio,
        "mean_fixation_duration_ratio": duration_ratio,
    }
    ratios = dict(core_ratios)
    weighted_components = [
        (config.eye_dwell_weight, dwell_ratio),
        (config.eye_fixation_weight, fixation_ratio),
        (config.eye_duration_weight, duration_ratio),
    ]
    # Revisit metrics are optional for backwards-compatible HTTP/replay
    # payloads. When present, add smoothed ratios so a zero baseline does not
    # create an infinite score.
    revisit_available = (
        eye.aoi_revisit_count is not None
        and baseline.aoi_revisit_count is not None
        and eye.aoi_revisit_time is not None
        and baseline.aoi_revisit_time is not None
    )
    if revisit_available:
        revisit_count_ratio = (float(eye.aoi_revisit_count) + 1.0) / (
            float(baseline.aoi_revisit_count) + 1.0
        )
        revisit_time_ratio = (float(eye.aoi_revisit_time) + 0.25) / (
            float(baseline.aoi_revisit_time) + 0.25
        )
        ratios.update(
            {
                "aoi_revisit_count_ratio": revisit_count_ratio,
                "aoi_revisit_time_ratio": revisit_time_ratio,
            }
        )
        weighted_components.extend(
            [
                (config.eye_revisit_count_weight, revisit_count_ratio),
                (config.eye_revisit_time_weight, revisit_time_ratio),
            ]
        )
    total_weight = sum(weight for weight, _ in weighted_components)
    score = sum(weight * value for weight, value in weighted_components) / total_weight
    abnormal = [name for name, value in ratios.items() if value >= abnormal_ratio]
    core_abnormal = [
        name for name, value in core_ratios.items() if value >= abnormal_ratio
    ]
    single_feature_trigger = max(core_ratios.values()) >= single_ratio
    revisit_abnormal = [
        name
        for name in ratios
        if name.startswith("aoi_revisit_") and ratios[name] >= abnormal_ratio
    ]
    repeated_evidence = len(core_abnormal) >= 2 or (
        bool(core_abnormal) and bool(revisit_abnormal)
    )
    if score >= strong:
        level = "detailed"
    elif score >= moderate and (repeated_evidence or single_feature_trigger):
        level = "example"
    # A single mildly abnormal fixation/dwell ratio is too noisy for an
    # automatic "brief" prompt. Require either two core indicators or a
    # core indicator corroborated by revisit evidence.
    elif score >= mild and repeated_evidence:
        level = "brief"
    else:
        level = "none"
    reasons = ["eye_ratio_%s" % name for name in abnormal]
    if single_feature_trigger and score < mild:
        reasons.append("eye_single_feature_spike")
    reasons.append("eye_%s" % (level if level != "none" else "near_personal_baseline"))
    components = {
        **ratios,
        "eye_difficulty_score": float(score),
        "baseline_aoi_dwell_time": float(baseline.aoi_dwell_time),
        "baseline_fixation_count": float(baseline.fixation_count),
        "baseline_mean_fixation_duration": float(baseline.mean_fixation_duration),
        "eye_abnormal_ratio_threshold": float(abnormal_ratio),
        "eye_single_feature_ratio_threshold": float(single_ratio),
        "eye_mild_threshold": float(mild),
        "eye_moderate_threshold": float(moderate),
        "eye_strong_threshold": float(strong),
    }
    if revisit_available:
        components.update(
            {
                "baseline_aoi_revisit_count": float(baseline.aoi_revisit_count),
                "baseline_aoi_revisit_time": float(baseline.aoi_revisit_time),
            }
        )
    return (
        float(score),
        level,
        components,
        reasons,
    )


def _eeg_level(state: MultimodalState, config: PolicyConfig) -> Tuple[int, List[str]]:
    load = float(np.clip(state.eeg.cognitive_load, 0.0, 100.0))
    if load >= config.eeg_high_threshold:
        return 3, ["eeg_high_workload"]
    if load >= config.eeg_medium_threshold:
        return 1, ["eeg_elevated_workload"]
    return 0, ["eeg_low_workload"]


def _c3_level(eye_level: int, eeg_level: int, version: str = "v1") -> Tuple[str, str]:
    if version == "v2":
        # Asymmetric fusion is intentional. Eye behaviour proposes observable
        # difficulty; EEG disambiguates normal re-reading from cognitive load.
        # A high EEG state can also expose covert overload before gaze changes,
        # while a merely elevated EEG state is not sufficient on its own.
        if eye_level > 0 and eeg_level == 0:
            return "none", "c3_v2_eye_difficulty_not_confirmed_by_eeg"
        if eye_level == 0 and eeg_level >= 3:
            return "example", "c3_v2_covert_high_workload_eeg_only"
        if eye_level == 0:
            return "none", "c3_v2_no_actionable_cognitive_state"
        if eeg_level >= 3:
            return "detailed", "c3_v2_eye_and_high_workload_agree"
        return "example", "c3_v2_eye_and_eeg_difficulty_agree"
    if eye_level == 0 and eeg_level == 0:
        return "none", "c3_eye_and_eeg_normal"
    if eye_level > 0 and eeg_level == 0:
        return "brief", "c3_eye_only_abnormal_intervention_reduced"
    if eye_level == 0 and eeg_level > 0:
        return "brief", "c3_eeg_only_abnormal_intervention_reduced"
    if eeg_level >= 3:
        return "detailed", "c3_eye_and_high_workload_agree"
    return "example", "c3_eye_and_eeg_difficulty_agree"


def _positive_median(values: Iterable[object]) -> Optional[float]:
    positive = []
    for value in values:
        if value is None:
            continue
        number = float(value)
        if np.isfinite(number) and number > 0:
            positive.append(number)
    return float(np.median(positive)) if positive else None


def _nonnegative_median(values: Iterable[object]) -> Optional[float]:
    nonnegative = []
    for value in values:
        if value is None:
            continue
        number = float(value)
        if np.isfinite(number) and number >= 0:
            nonnegative.append(number)
    return float(np.median(nonnegative)) if nonnegative else None


def _gaze_gate_reason(
    gaze: GazeFeatures, config: PolicyConfig, state: Optional[MultimodalState] = None
) -> Optional[str]:
    if (
        gaze.valid_sample_ratio is not None
        and gaze.valid_sample_ratio < config.gaze_min_valid_ratio
    ):
        return "gaze_valid_ratio_below_threshold"
    mapping = gaze.metadata.get("screen_mapping")
    if isinstance(mapping, dict):
        # A layout from the preceding Trial can remain visible briefly while
        # the browser is rendering the new material.  Do not interpret its
        # dwell target as the current question's focus.
        mapping_trial = mapping.get("trial_id")
        mapping_slide = mapping.get("slide_id")
        current_trial = state.trial_id if state is not None else None
        current_slide = state.ui.slide_id if state is not None else None
        if current_trial and mapping_trial and str(mapping_trial) != str(current_trial):
            return "screen_mapping_trial_mismatch"
        if current_slide and mapping_slide and str(mapping_slide) != str(current_slide):
            return "screen_mapping_slide_mismatch"
        if config.require_screen_mapping and not mapping.get("valid"):
            return "screen_mapping_invalid"
        if config.require_screen_mapping and "dwell_target" in mapping:
            target = mapping.get("dwell_target")
            # A missing target can occur during a short mapping refresh. Do not
            # discard an otherwise valid Eye episode; only reject a confirmed
            # target in the AI panel, which is the unsafe case.
            if isinstance(target, dict) and target.get("policy_region") == "ai_panel":
                return "gaze_not_on_reading_content"
        for target_name in ("dwell_target", "target"):
            target = mapping.get(target_name)
            if isinstance(target, dict) and target.get("policy_region") == "ai_panel":
                return "gaze_on_ai_panel"
    elif config.require_screen_mapping:
        return "screen_mapping_missing"
    return None


def _action(level: str) -> str:
    return {
        "none": "continue",
        "brief": "offer_brief_explanation",
        "example": "offer_example",
        "detailed": "offer_detailed_explanation",
    }[level]


def _ui_mode(level: str) -> str:
    return "normal" if level == "none" else "assistance"


def _unique(values: List[str]) -> List[str]:
    return list(dict.fromkeys(values))
