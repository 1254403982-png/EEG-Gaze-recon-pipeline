"""Contracts between channel-agnostic EEG preprocessing and pluggable decoders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class ProcessedEEGWindow:
    """A named, full-channel window shared by every decoder."""

    sampling_rate_hz: float
    channel_names: Tuple[str, ...]
    filtered_samples: np.ndarray
    frequencies_hz: np.ndarray
    power_spectral_density: np.ndarray
    bad_channel_mask: np.ndarray
    quality_metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def bad_channels(self) -> Tuple[str, ...]:
        return tuple(
            name for name, bad in zip(self.channel_names, self.bad_channel_mask) if bool(bad)
        )

    def channel_indices(self, names: Sequence[str]) -> Tuple[int, ...]:
        index = {name: position for position, name in enumerate(self.channel_names)}
        return tuple(index[name] for name in names if name in index)


@dataclass(frozen=True)
class EEGDecoderResult:
    """Generic decoder result; metric names are owned by the decoder."""

    decoder_id: str
    quality: str
    metrics: Dict[str, Optional[float]]
    channels_requested: Tuple[str, ...]
    channels_used: Tuple[str, ...]
    missing_channels: Tuple[str, ...] = ()
    bad_channels: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decoder_id": self.decoder_id,
            "quality": self.quality,
            "metrics": dict(self.metrics),
            "channels_requested": list(self.channels_requested),
            "channels_used": list(self.channels_used),
            "missing_channels": list(self.missing_channels),
            "bad_channels": list(self.bad_channels),
            "metadata": dict(self.metadata),
        }


class EEGDecoder(Protocol):
    """Minimal interface required for adding a new online EEG indicator."""

    @property
    def decoder_id(self) -> str: ...

    def reset(self) -> None: ...

    def decode(self, window: ProcessedEEGWindow) -> EEGDecoderResult: ...
