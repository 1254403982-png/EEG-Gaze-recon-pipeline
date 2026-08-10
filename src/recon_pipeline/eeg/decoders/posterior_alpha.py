"""Posterior Alpha decoder implemented independently of acquisition and preprocessing."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

from ..contracts import EEGDecoderResult, ProcessedEEGWindow
from ..preprocessing import integrate_band

DEFAULT_POSTERIOR_CHANNELS = ("P3", "P4", "P7", "P8", "PZ", "O1", "O2")


class PosteriorAlphaDecoder:
    def __init__(
        self,
        *,
        decoder_id: str = "posterior_alpha",
        channels: Sequence[str] = DEFAULT_POSTERIOR_CHANNELS,
        alpha_low_hz: float = 8.0,
        alpha_high_hz: float = 13.0,
        min_good_channels: int = 3,
        max_bad_channel_ratio: float = 0.45,
        baseline_history_size: int = 600,
    ) -> None:
        self._decoder_id = str(decoder_id)
        self.channels = tuple(str(name).strip().upper() for name in channels)
        self.alpha_low_hz = float(alpha_low_hz)
        self.alpha_high_hz = float(alpha_high_hz)
        self.min_good_channels = int(min_good_channels)
        self.max_bad_channel_ratio = float(max_bad_channel_ratio)
        self.baseline_history_size = int(baseline_history_size)
        self._alpha_history: List[float] = []
        if not self.channels:
            raise ValueError("PosteriorAlphaDecoder requires at least one channel.")
        if self.min_good_channels < 1:
            raise ValueError("min_good_channels must be positive.")

    @property
    def decoder_id(self) -> str:
        return self._decoder_id

    def reset(self) -> None:
        self._alpha_history.clear()

    def decode(self, window: ProcessedEEGWindow) -> EEGDecoderResult:
        available = {name: index for index, name in enumerate(window.channel_names)}
        requested_indices = [available[name] for name in self.channels if name in available]
        missing = tuple(name for name in self.channels if name not in available)
        bad = tuple(
            window.channel_names[index]
            for index in requested_indices
            if bool(window.bad_channel_mask[index])
        )
        good_indices = [
            index for index in requested_indices if not bool(window.bad_channel_mask[index])
        ]
        used = tuple(window.channel_names[index] for index in good_indices)
        unavailable_count = len(bad) + len(missing)
        bad_ratio = unavailable_count / len(self.channels)
        quality_pass = (
            len(good_indices) >= self.min_good_channels
            and bad_ratio <= self.max_bad_channel_ratio
        )

        metrics: Dict[str, Optional[float]] = {
            "cognitive_load": None,
            "attention": None,
            "alpha_power": None,
            "alpha_peak_hz": None,
            "alpha_suppression": None,
        }
        if good_indices:
            alpha_by_channel = integrate_band(
                window.frequencies_hz,
                window.power_spectral_density,
                self.alpha_low_hz,
                self.alpha_high_hz,
            )
            alpha_power = float(np.mean(alpha_by_channel[good_indices]))
            posterior_psd = np.mean(window.power_spectral_density[good_indices], axis=0)
            alpha_mask = (
                (window.frequencies_hz >= self.alpha_low_hz)
                & (window.frequencies_hz <= self.alpha_high_hz)
            )
            alpha_peak = float(
                window.frequencies_hz[alpha_mask][np.argmax(posterior_psd[alpha_mask])]
            )
            log_alpha = float(np.log10(alpha_power + 1e-12))
            if quality_pass:
                self._alpha_history.append(log_alpha)
                self._alpha_history = self._alpha_history[-self.baseline_history_size :]
            if len(self._alpha_history) >= 3:
                history = np.asarray(self._alpha_history, dtype=float)
                baseline = float(np.median(history))
                rank = float(np.mean(history <= log_alpha))
                load = float(np.clip(100.0 * (1.0 - rank), 0.0, 100.0))
                suppression = baseline - log_alpha
            else:
                load, suppression = 50.0, 0.0
            metrics.update(
                {
                    "cognitive_load": load,
                    "attention": 100.0 - load,
                    "alpha_power": alpha_power,
                    "alpha_peak_hz": alpha_peak,
                    "alpha_suppression": float(suppression),
                }
            )

        return EEGDecoderResult(
            decoder_id=self.decoder_id,
            quality="pass" if quality_pass else "warning",
            metrics=metrics,
            channels_requested=self.channels,
            channels_used=used,
            missing_channels=missing,
            bad_channels=bad,
            metadata={
                "alpha_band_hz": [self.alpha_low_hz, self.alpha_high_hz],
                "history_count": len(self._alpha_history),
                "min_good_channels": self.min_good_channels,
                "bad_channel_ratio": bad_ratio,
                "interpretation": "within-session rolling posterior Alpha baseline",
            },
        )
