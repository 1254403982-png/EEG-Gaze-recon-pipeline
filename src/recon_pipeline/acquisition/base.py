"""Small hardware-neutral acquisition boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

import numpy as np

from ..clock import Timestamp


@dataclass
class RawEEGChunk:
    samples: np.ndarray
    channel_names: Sequence[str]
    sampling_rate_hz: float
    timestamp: Timestamp
    sample_timestamps: Optional[np.ndarray] = None
    source: str = "eeg"

    def __post_init__(self) -> None:
        matrix = np.asarray(self.samples)
        if matrix.ndim != 2:
            raise ValueError("EEG samples must be a 2D channels-by-samples array.")
        if matrix.shape[0] != len(self.channel_names):
            raise ValueError("Channel-name count does not match EEG rows.")
        if self.sampling_rate_hz <= 0:
            raise ValueError("sampling_rate_hz must be positive.")


class EEGSource(Protocol):
    @property
    def is_running(self) -> bool: ...

    def start(self) -> None: ...

    def read(self) -> Optional[RawEEGChunk]: ...

    def stop(self) -> None: ...
