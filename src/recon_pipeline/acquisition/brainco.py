"""BrainCo 32-channel source backed by the integrated SDK adapter."""

from __future__ import annotations

from typing import Any, Optional, Sequence

import numpy as np

from ..clock import Timestamp
from .base import RawEEGChunk
from .brainco_sdk import BrainCoSDKAcquirer

BRAINCO_32_CHANNELS = (
    "FP1", "FP2", "F3", "F4", "F7", "F8", "FZ", "C3",
    "C4", "CZ", "P3", "P4", "P7", "P8", "PZ", "O1",
    "O2", "T7", "T8", "FC1", "FC2", "FC5", "FC6", "CP1",
    "CP2", "CP5", "CP6", "FT9", "FT10", "TP9", "TP10", "IO",
)


class BrainCoSource:
    """Expose integrated BrainCo acquisition through the recon ``EEGSource`` API."""

    def __init__(
        self,
        *,
        sampling_rate_hz: float = 250.0,
        channel_names: Sequence[str] = BRAINCO_32_CHANNELS,
        acquirer_kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        self.sampling_rate_hz = float(sampling_rate_hz)
        self.channel_names = tuple(str(name).strip().upper() for name in channel_names)
        self.acquirer_kwargs = dict(acquirer_kwargs or {})
        self._acquirer: Optional[BrainCoSDKAcquirer] = None

    @property
    def is_running(self) -> bool:
        return self._acquirer is not None and self._acquirer.is_running

    def start(self) -> None:
        if self.is_running:
            return
        acquirer = BrainCoSDKAcquirer(
            sampling_rate_hz=self.sampling_rate_hz,
            channel_count=len(self.channel_names),
            **self.acquirer_kwargs,
        )
        acquirer.start()
        self._acquirer = acquirer

    def read(self) -> Optional[RawEEGChunk]:
        if self._acquirer is None:
            raise RuntimeError("BrainCo source is not started.")
        samples, device_timestamps = self._acquirer.read_new_samples()
        matrix = np.asarray(samples, dtype=np.float32)
        if matrix.size == 0:
            return None
        timestamps = np.asarray(device_timestamps, dtype=np.float64)
        device_seconds = float(timestamps[-1]) if timestamps.size else None
        return RawEEGChunk(
            samples=matrix,
            channel_names=self.channel_names,
            sampling_rate_hz=self.sampling_rate_hz,
            timestamp=Timestamp.now(device_seconds=device_seconds),
            sample_timestamps=timestamps if timestamps.size else None,
            source="brainco",
        )

    def stop(self) -> None:
        acquirer, self._acquirer = self._acquirer, None
        if acquirer is not None:
            acquirer.stop()


# Kept only so existing imports do not break. No external oi-mi path is used.
LegacyBrainCoSource = BrainCoSource
