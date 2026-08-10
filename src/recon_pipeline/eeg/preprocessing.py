"""Channel-agnostic filtering, PSD calculation, and signal-quality checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
from scipy.signal import butter, filtfilt, iirnotch, sosfiltfilt, welch

from .contracts import ProcessedEEGWindow


def integrate_band(
    frequencies_hz: np.ndarray,
    psd: np.ndarray,
    low_hz: float,
    high_hz: float,
) -> np.ndarray:
    mask = (frequencies_hz >= low_hz) & (frequencies_hz <= high_hz)
    if np.count_nonzero(mask) < 2:
        return np.zeros(psd.shape[:-1], dtype=float)
    if hasattr(np, "trapezoid"):
        return np.trapezoid(psd[..., mask], frequencies_hz[mask], axis=-1)
    return np.trapz(psd[..., mask], frequencies_hz[mask], axis=-1)


@dataclass(frozen=True)
class EEGQualityConfig:
    line_frequency_hz: float = 50.0
    line_bandwidth_hz: float = 2.0
    line_power_threshold: float = 10.0
    high_frequency_low_hz: float = 20.0
    high_frequency_high_hz: float = 40.0
    high_frequency_power_threshold: float = 30.0
    extreme_amplitude_threshold: float = 100.0
    extreme_seconds_threshold: float = 2.0
    max_bad_channel_ratio: float = 0.45


class EEGPreprocessor:
    """Preprocess all acquired channels without deciding which channels encode a metric."""

    def __init__(
        self,
        *,
        sampling_rate_hz: float = 250.0,
        bandpass_low_hz: float = 1.0,
        bandpass_high_hz: float = 45.0,
        quality: Optional[EEGQualityConfig] = None,
    ) -> None:
        self.sampling_rate_hz = float(sampling_rate_hz)
        self.bandpass_low_hz = float(bandpass_low_hz)
        self.bandpass_high_hz = float(bandpass_high_hz)
        self.quality = quality or EEGQualityConfig()
        if not 0 < self.bandpass_low_hz < self.bandpass_high_hz:
            raise ValueError("EEG bandpass frequencies must be ordered and positive.")
        if self.bandpass_high_hz >= self.sampling_rate_hz / 2.0:
            raise ValueError("EEG bandpass high frequency must be below Nyquist.")

    def process(
        self,
        samples: np.ndarray,
        channel_names: Sequence[str],
    ) -> ProcessedEEGWindow:
        matrix = np.asarray(samples, dtype=np.float32)
        names = tuple(str(name).strip().upper() for name in channel_names)
        if matrix.ndim != 2 or matrix.shape[0] != len(names):
            raise ValueError("EEG window must have shape (named_channels, samples).")
        if not np.all(np.isfinite(matrix)):
            raise ValueError("EEG samples contain NaN or infinite values.")

        centered = matrix - np.median(matrix, axis=1, keepdims=True)
        sos = butter(
            4,
            [self.bandpass_low_hz, self.bandpass_high_hz],
            btype="bandpass",
            fs=self.sampling_rate_hz,
            output="sos",
        )
        filtered = sosfiltfilt(sos, centered, axis=1)
        notch_b, notch_a = iirnotch(
            self.quality.line_frequency_hz,
            30.0,
            fs=self.sampling_rate_hz,
        )
        filtered = filtfilt(notch_b, notch_a, filtered, axis=1)
        frequencies, psd = welch(
            filtered,
            fs=self.sampling_rate_hz,
            nperseg=min(filtered.shape[1], int(self.sampling_rate_hz * 2)),
            axis=1,
        )

        half_width = self.quality.line_bandwidth_hz / 2.0
        line_power = integrate_band(
            frequencies,
            psd,
            self.quality.line_frequency_hz - half_width,
            self.quality.line_frequency_hz + half_width,
        )
        high_frequency_power = integrate_band(
            frequencies,
            psd,
            self.quality.high_frequency_low_hz,
            self.quality.high_frequency_high_hz,
        )
        extreme_count = np.sum(
            np.abs(filtered) >= self.quality.extreme_amplitude_threshold,
            axis=1,
        )
        extreme_limit = self.quality.extreme_seconds_threshold * self.sampling_rate_hz
        line_bad = line_power > self.quality.line_power_threshold
        high_frequency_bad = (
            high_frequency_power > self.quality.high_frequency_power_threshold
        )
        extreme_bad = extreme_count > extreme_limit
        bad_mask = line_bad | high_frequency_bad | extreme_bad
        return ProcessedEEGWindow(
            sampling_rate_hz=self.sampling_rate_hz,
            channel_names=names,
            filtered_samples=filtered,
            frequencies_hz=frequencies,
            power_spectral_density=psd,
            bad_channel_mask=np.asarray(bad_mask, dtype=bool),
            quality_metrics={
                "bad_channel_ratio": float(np.mean(bad_mask)),
                "bad_channel_reasons": _channel_reasons(
                    names,
                    line_bad=line_bad,
                    high_frequency_bad=high_frequency_bad,
                    extreme_bad=extreme_bad,
                ),
                "line_power": _channel_values(names, line_power),
                "high_frequency_power": _channel_values(names, high_frequency_power),
                "extreme_sample_count": _channel_values(names, extreme_count),
                "thresholds": {
                    "line_power": self.quality.line_power_threshold,
                    "high_frequency_power": self.quality.high_frequency_power_threshold,
                    "extreme_amplitude": self.quality.extreme_amplitude_threshold,
                    "extreme_sample_count": float(extreme_limit),
                    "max_bad_channel_ratio": self.quality.max_bad_channel_ratio,
                },
            },
        )


def _channel_values(names: Sequence[str], values: np.ndarray) -> dict[str, float]:
    return {name: float(value) for name, value in zip(names, values)}


def _channel_reasons(
    names: Sequence[str],
    *,
    line_bad: np.ndarray,
    high_frequency_bad: np.ndarray,
    extreme_bad: np.ndarray,
) -> dict[str, list[str]]:
    reasons: dict[str, list[str]] = {}
    for index, name in enumerate(names):
        channel_reasons = []
        if bool(line_bad[index]):
            channel_reasons.append("line_noise")
        if bool(high_frequency_bad[index]):
            channel_reasons.append("high_frequency")
        if bool(extreme_bad[index]):
            channel_reasons.append("extreme_amplitude")
        if channel_reasons:
            reasons[name] = channel_reasons
    return reasons
