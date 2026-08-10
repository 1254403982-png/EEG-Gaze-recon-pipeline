"""Build the full-channel processing graph from typed configuration."""

from __future__ import annotations

from ..config import EEGProcessingConfig
from .decoders import build_decoder
from .online import OnlineEEGProcessor
from .preprocessing import EEGPreprocessor, EEGQualityConfig


def build_eeg_processor(config: EEGProcessingConfig) -> OnlineEEGProcessor:
    quality = EEGQualityConfig(**config.quality)
    preprocessor = EEGPreprocessor(
        sampling_rate_hz=config.sampling_rate_hz,
        bandpass_low_hz=config.bandpass_low_hz,
        bandpass_high_hz=config.bandpass_high_hz,
        quality=quality,
    )
    decoders = [
        build_decoder(
            item.decoder_type,
            item.decoder_id,
            item.channels,
            item.options,
        )
        for item in config.decoders
    ]
    return OnlineEEGProcessor(
        sampling_rate_hz=config.sampling_rate_hz,
        window_seconds=config.window_seconds,
        max_buffer_seconds=config.max_buffer_seconds,
        preprocessor=preprocessor,
        decoders=decoders,
        primary_decoder=config.primary_decoder,
    )
