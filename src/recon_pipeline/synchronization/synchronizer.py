"""Thread-safe latest-state synchronizer with freshness checks."""

from __future__ import annotations

import threading
import time
from dataclasses import replace
from typing import Optional

from ..clock import Timestamp
from ..models import (
    EEGFeatures,
    GazeFeatures,
    MultimodalState,
    SignalStatus,
    UIContext,
)


class MultimodalSynchronizer:
    def __init__(self, *, max_eeg_age_ms: int = 2500, max_gaze_age_ms: int = 1500) -> None:
        self.max_eeg_age_ms = int(max_eeg_age_ms)
        self.max_gaze_age_ms = int(max_gaze_age_ms)
        self._lock = threading.Lock()
        self._session_id = "not_started"
        self._trial_id: Optional[str] = None
        self._condition = 1
        self._eeg: Optional[EEGFeatures] = None
        self._gaze: Optional[GazeFeatures] = None
        self._ui = UIContext()

    def start_session(self, session_id: str, *, condition: int = 1) -> None:
        if not session_id.strip():
            raise ValueError("session_id must not be empty.")
        _validate_condition(condition)
        with self._lock:
            self._session_id = session_id
            self._trial_id = None
            self._condition = condition
            self._eeg = None
            self._gaze = None
            self._ui = UIContext()

    def set_trial(self, trial_id: Optional[str], ui: Optional[UIContext] = None) -> None:
        with self._lock:
            self._trial_id = trial_id
            if ui is not None:
                self._ui = ui

    def set_condition(self, condition: int) -> None:
        _validate_condition(condition)
        with self._lock:
            self._condition = condition

    def update_eeg(self, features: EEGFeatures) -> None:
        with self._lock:
            self._eeg = features

    def update_gaze(self, features: GazeFeatures) -> None:
        with self._lock:
            self._gaze = features

    def update_ui(self, context: UIContext) -> None:
        with self._lock:
            self._ui = context

    def snapshot(self, now_monotonic_ns: Optional[int] = None) -> MultimodalState:
        now_ns = time.monotonic_ns() if now_monotonic_ns is None else now_monotonic_ns
        with self._lock:
            eeg = self._eeg or _unavailable_eeg()
            gaze = self._gaze or _unavailable_gaze()
            session_id = self._session_id
            trial_id = self._trial_id
            condition = self._condition
            ui = replace(self._ui)
        if (
            eeg.status in {SignalStatus.AVAILABLE, SignalStatus.WARNING}
            and eeg.timestamp.age_ms(now_ns) > self.max_eeg_age_ms
        ):
            eeg = replace(eeg, status=SignalStatus.STALE, quality="stale")
        if (
            gaze.status in {SignalStatus.AVAILABLE, SignalStatus.WARNING}
            and gaze.timestamp.age_ms(now_ns) > self.max_gaze_age_ms
        ):
            gaze = replace(gaze, status=SignalStatus.STALE, quality="stale")
        return MultimodalState(
            session_id=session_id,
            trial_id=trial_id,
            condition=condition,
            timestamp=Timestamp.now(),
            eeg=eeg,
            gaze=gaze,
            ui=ui,
        )


def _validate_condition(condition: int) -> None:
    if condition not in {1, 2, 3}:
        raise ValueError("condition must be 1, 2, or 3.")


def _unavailable_eeg() -> EEGFeatures:
    return EEGFeatures(
        timestamp=Timestamp.now(),
        status=SignalStatus.UNAVAILABLE,
        quality="unavailable",
        metadata={"reason": "no_eeg_received"},
    )


def _unavailable_gaze() -> GazeFeatures:
    return GazeFeatures(
        timestamp=Timestamp.now(),
        status=SignalStatus.UNAVAILABLE,
        quality="unavailable",
        metadata={"reason": "no_gaze_received"},
    )
