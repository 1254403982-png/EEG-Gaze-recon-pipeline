"""Full-channel EEG preprocessing and pluggable online decoders."""

from .brainco_mapping import BrainCoNeuraDockMapper
from .contracts import EEGDecoder, EEGDecoderResult, ProcessedEEGWindow
from .decoders import CognitiveWorkloadDecoder, PosteriorAlphaDecoder, build_decoder, register_decoder
from .factory import build_eeg_processor
from .online import OnlineEEGProcessor
from .preprocessing import EEGPreprocessor, EEGQualityConfig

__all__ = [
    "BrainCoNeuraDockMapper",
    "CognitiveWorkloadDecoder",
    "EEGDecoder",
    "EEGDecoderResult",
    "EEGPreprocessor",
    "EEGQualityConfig",
    "OnlineEEGProcessor",
    "PosteriorAlphaDecoder",
    "ProcessedEEGWindow",
    "build_decoder",
    "build_eeg_processor",
    "register_decoder",
]
