"""Within-session cognitive-workload proxy using frontal theta and posterior alpha."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..contracts import EEGDecoderResult, ProcessedEEGWindow
from ..preprocessing import integrate_band

DEFAULT_FRONTAL_CHANNELS = ("FZ", "F3", "F4", "FC1", "FC2")
DEFAULT_POSTERIOR_CHANNELS = ("P3", "P4", "P7", "P8", "PZ", "O1", "O2")


class CognitiveWorkloadDecoder:
    """Estimate relative workload from frontal theta / posterior alpha (TLI).

    The 0--100 output is a within-session percentile proxy, not a calibrated
    psychological scale. Raw component powers and the log TLI are retained for
    audit and later participant-specific calibration.
    """

    def __init__(
        self,
        *,
        decoder_id: str = "cognitive_workload",
        channels: Sequence[str] = (*DEFAULT_FRONTAL_CHANNELS, *DEFAULT_POSTERIOR_CHANNELS),
        frontal_channels: Sequence[str] = DEFAULT_FRONTAL_CHANNELS,
        posterior_channels: Sequence[str] = DEFAULT_POSTERIOR_CHANNELS,
        theta_low_hz: float = 4.0,
        theta_high_hz: float = 7.0,
        alpha_low_hz: float = 8.0,
        alpha_high_hz: float = 13.0,
        relative_power_low_hz: float = 4.0,
        relative_power_high_hz: float = 30.0,
        min_good_frontal_channels: int = 2,
        min_good_posterior_channels: int = 3,
        max_bad_channel_ratio: float = 0.45,
        baseline_history_size: int = 600,
    ) -> None:
        self._decoder_id = str(decoder_id)
        configured = tuple(str(name).strip().upper() for name in channels)
        self.frontal_channels = tuple(str(name).strip().upper() for name in frontal_channels)
        self.posterior_channels = tuple(str(name).strip().upper() for name in posterior_channels)
        required = (*self.frontal_channels, *self.posterior_channels)
        self.channels = tuple(name for name in required if name in configured) or required
        self.theta_low_hz = float(theta_low_hz)
        self.theta_high_hz = float(theta_high_hz)
        self.alpha_low_hz = float(alpha_low_hz)
        self.alpha_high_hz = float(alpha_high_hz)
        self.relative_power_low_hz = float(relative_power_low_hz)
        self.relative_power_high_hz = float(relative_power_high_hz)
        self.min_good_frontal_channels = int(min_good_frontal_channels)
        self.min_good_posterior_channels = int(min_good_posterior_channels)
        self.max_bad_channel_ratio = float(max_bad_channel_ratio)
        self.baseline_history_size = int(baseline_history_size)
        self._tli_history: List[float] = []
        self._alpha_history: List[float] = []

    @property
    def decoder_id(self) -> str:
        return self._decoder_id

    def reset(self) -> None:
        self._tli_history.clear()
        self._alpha_history.clear()

    def decode(self, window: ProcessedEEGWindow) -> EEGDecoderResult:
        available = {name: index for index, name in enumerate(window.channel_names)}
        frontal, frontal_missing, frontal_bad = self._good_indices(
            self.frontal_channels, available, window
        )
        posterior, posterior_missing, posterior_bad = self._good_indices(
            self.posterior_channels, available, window
        )
        missing = (*frontal_missing, *posterior_missing)
        bad = (*frontal_bad, *posterior_bad)
        unavailable_ratio = (len(missing) + len(bad)) / len(self.channels)
        quality_pass = (
            len(frontal) >= self.min_good_frontal_channels
            and len(posterior) >= self.min_good_posterior_channels
            and unavailable_ratio <= self.max_bad_channel_ratio
        )

        metrics: Dict[str, Optional[float]] = {
            "cognitive_load": None,
            "attention": None,
            "frontal_theta_power": None,
            "posterior_alpha_power": None,
            "workload_index": None,
            "alpha_power": None,
            "alpha_peak_hz": None,
            "alpha_suppression": None,
        }
        if frontal and posterior:
            total = integrate_band(
                window.frequencies_hz,
                window.power_spectral_density,
                self.relative_power_low_hz,
                self.relative_power_high_hz,
            )
            theta = integrate_band(
                window.frequencies_hz, window.power_spectral_density,
                self.theta_low_hz, self.theta_high_hz,
            )
            alpha = integrate_band(
                window.frequencies_hz, window.power_spectral_density,
                self.alpha_low_hz, self.alpha_high_hz,
            )
            eps = 1e-12
            frontal_theta = float(np.median(theta[frontal] / (total[frontal] + eps)))
            posterior_alpha = float(np.median(alpha[posterior] / (total[posterior] + eps)))
            log_tli = float(np.log(frontal_theta + eps) - np.log(posterior_alpha + eps))
            if quality_pass:
                self._tli_history.append(log_tli)
                self._tli_history = self._tli_history[-self.baseline_history_size :]
                self._alpha_history.append(float(np.log(posterior_alpha + eps)))
                self._alpha_history = self._alpha_history[-self.baseline_history_size :]
            if len(self._tli_history) >= 3:
                history = np.asarray(self._tli_history, dtype=float)
                rank = float(np.mean(history <= log_tli))
                load = float(np.clip(100.0 * rank, 0.0, 100.0))
                baseline_log_alpha = float(np.median(self._alpha_history))
            else:
                load = 50.0
                baseline_log_alpha = float(np.log(posterior_alpha + eps))
            posterior_psd = np.mean(window.power_spectral_density[posterior], axis=0)
            alpha_mask = ((window.frequencies_hz >= self.alpha_low_hz)
                          & (window.frequencies_hz <= self.alpha_high_hz))
            alpha_peak = float(window.frequencies_hz[alpha_mask][np.argmax(posterior_psd[alpha_mask])])
            metrics.update({
                "cognitive_load": load,
                "frontal_theta_power": frontal_theta,
                "posterior_alpha_power": posterior_alpha,
                "workload_index": log_tli,
                "alpha_power": posterior_alpha,
                "alpha_peak_hz": alpha_peak,
                "alpha_suppression": baseline_log_alpha - float(np.log(posterior_alpha + eps)),
            })

        used = tuple(window.channel_names[index] for index in (*frontal, *posterior))
        return EEGDecoderResult(
            decoder_id=self.decoder_id,
            quality="pass" if quality_pass else "warning",
            metrics=metrics,
            channels_requested=self.channels,
            channels_used=used,
            missing_channels=missing,
            bad_channels=bad,
            metadata={
                "theta_band_hz": [self.theta_low_hz, self.theta_high_hz],
                "alpha_band_hz": [self.alpha_low_hz, self.alpha_high_hz],
                "frontal_channels": list(self.frontal_channels),
                "posterior_channels": list(self.posterior_channels),
                "history_count": len(self._tli_history),
                "interpretation": "within-session frontal-theta/posterior-alpha workload proxy",
            },
        )

    @staticmethod
    def _good_indices(
        requested: Sequence[str], available: Dict[str, int], window: ProcessedEEGWindow
    ) -> Tuple[List[int], Tuple[str, ...], Tuple[str, ...]]:
        present = [available[name] for name in requested if name in available]
        missing = tuple(name for name in requested if name not in available)
        bad = tuple(window.channel_names[index] for index in present if window.bad_channel_mask[index])
        good = [index for index in present if not window.bad_channel_mask[index]]
        return good, missing, bad
