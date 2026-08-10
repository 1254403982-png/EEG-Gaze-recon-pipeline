"""Explicit null provider used until real gaze hardware is integrated."""

from __future__ import annotations

from typing import Optional

from ..clock import Timestamp
from ..models import GazeFeatures, SignalStatus


class UnavailableGazeProvider:
    """Return unavailable, never fabricated zeros or random measurements."""

    def __init__(self, reason: str = "gaze_device_not_configured") -> None:
        self.reason = reason
        self.session_id: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self.session_id is not None

    def start(self, session_id: str) -> None:
        self.session_id = session_id

    def read(self) -> GazeFeatures:
        if not self.is_running:
            raise RuntimeError("Gaze provider is not started.")
        return GazeFeatures(
            timestamp=Timestamp.now(),
            status=SignalStatus.UNAVAILABLE,
            quality="unavailable",
            source="unavailable",
            metadata={"reason": self.reason},
        )

    def stop(self) -> None:
        self.session_id = None
