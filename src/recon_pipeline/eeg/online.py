"""Orchestrate full-channel buffering, preprocessing, and independent decoders."""

from __future__ import annotations

from typing import Dict, Optional, Sequence

import numpy as np

from ..clock import Timestamp
from ..models import EEGFeatures, SignalStatus
from .contracts import EEGDecoder
from .decoders import PosteriorAlphaDecoder
from .preprocessing import EEGPreprocessor


class OnlineEEGProcessor:
    """Process a named N-channel stream and publish one primary decoder result."""

    def __init__(
        self,
        sampling_rate_hz: float = 250.0,
        window_seconds: float = 4.0,
        max_buffer_seconds: float = 90.0,
        *,
        preprocessor: Optional[EEGPreprocessor] = None,
        decoders: Optional[Sequence[EEGDecoder]] = None,
        primary_decoder: str = "posterior_alpha",
    ) -> None:
        self.fs = float(sampling_rate_hz)
        self.window_samples = round(window_seconds * self.fs)
        self.max_buffer_samples = round(max_buffer_seconds * self.fs)
        self.preprocessor = preprocessor or EEGPreprocessor(sampling_rate_hz=self.fs)
        self.decoders = tuple(decoders or (PosteriorAlphaDecoder(),))
        self.primary_decoder = str(primary_decoder)
        decoder_ids = [decoder.decoder_id for decoder in self.decoders]
        if len(set(decoder_ids)) != len(decoder_ids):
            raise ValueError("EEG decoder IDs must be unique.")
        if self.primary_decoder not in decoder_ids:
            raise ValueError("Primary EEG decoder is not configured: %s" % primary_decoder)
        self._buffer: Optional[np.ndarray] = None
        self._channel_names: Optional[tuple[str, ...]] = None

    @property
    def channel_names(self) -> tuple[str, ...]:
        return self._channel_names or ()

    def reset(self) -> None:
        self._buffer = None
        self._channel_names = None
        for decoder in self.decoders:
            decoder.reset()

    def append(
        self,
        samples: np.ndarray,
        channel_names: Sequence[str],
        *,
        sampling_rate_hz: Optional[float] = None,
        device_seconds: Optional[float] = None,
        host_monotonic_ns: Optional[int] = None,
    ) -> Optional[EEGFeatures]:
        matrix = np.asarray(samples, dtype=np.float32)
        names = tuple(str(name).strip().upper() for name in channel_names)
        if matrix.ndim != 2 or matrix.shape[0] != len(names):
            raise ValueError("EEG samples must have shape (named_channels, samples).")
        if sampling_rate_hz is not None and not np.isclose(sampling_rate_hz, self.fs):
            raise ValueError(
                "EEG sample rate %.3f does not match processor %.3f."
                % (sampling_rate_hz, self.fs)
            )
        if self._channel_names is None:
            self._channel_names = names
            self._buffer = np.empty((len(names), 0), dtype=np.float32)
        elif names != self._channel_names:
            raise ValueError("EEG channel layout changed during an active processing session.")
        if not np.all(np.isfinite(matrix)):
            raise ValueError("EEG samples contain NaN or infinite values.")
        assert self._buffer is not None
        self._buffer = np.concatenate([self._buffer, matrix], axis=1)
        self._buffer = self._buffer[:, -self.max_buffer_samples :]
        if self._buffer.shape[1] < self.window_samples:
            return None
        return self._analyze(
            self._buffer[:, -self.window_samples :],
            device_seconds=device_seconds,
            host_monotonic_ns=host_monotonic_ns,
        )

    def _analyze(
        self,
        window_samples: np.ndarray,
        *,
        device_seconds: Optional[float],
        host_monotonic_ns: Optional[int],
    ) -> EEGFeatures:
        assert self._channel_names is not None
        window = self.preprocessor.process(window_samples, self._channel_names)
        results = {decoder.decoder_id: decoder.decode(window) for decoder in self.decoders}
        primary = results[self.primary_decoder]
        metrics = primary.metrics
        return EEGFeatures(
            timestamp=(
                Timestamp.from_monotonic_ns(host_monotonic_ns, device_seconds)
                if host_monotonic_ns is not None
                else Timestamp.now(device_seconds=device_seconds)
            ),
            status=(
                SignalStatus.AVAILABLE
                if primary.quality == "pass"
                else SignalStatus.WARNING
            ),
            quality=primary.quality,
            cognitive_load=_metric(metrics, "cognitive_load"),
            attention=_metric(metrics, "attention"),
            alpha_power=_metric(metrics, "alpha_power"),
            alpha_peak_hz=_metric(metrics, "alpha_peak_hz"),
            alpha_suppression=_metric(metrics, "alpha_suppression"),
            frontal_theta_power=_metric(metrics, "frontal_theta_power"),
            posterior_alpha_power=_metric(metrics, "posterior_alpha_power"),
            workload_index=_metric(metrics, "workload_index"),
            bad_channels=list(window.bad_channels),
            metadata={
                "channel_count": len(window.channel_names),
                "channels": list(window.channel_names),
                "clock_domain": "host_monotonic_at_chunk_receive",
                "device_time_basis": "sample_index_divided_by_sampling_rate",
                "window_seconds": self.window_samples / self.fs,
                "primary_decoder": self.primary_decoder,
                "decoder_outputs": {
                    decoder_id: result.to_dict() for decoder_id, result in results.items()
                },
                "quality_control": dict(window.quality_metrics),
            },
        )


def _metric(metrics: Dict[str, Optional[float]], name: str) -> Optional[float]:
    value = metrics.get(name)
    return None if value is None else float(value)
