"""Built-in EEG decoders and registry helpers."""

from .cognitive_workload import CognitiveWorkloadDecoder
from .posterior_alpha import PosteriorAlphaDecoder
from .registry import build_decoder, register_decoder

__all__ = ["CognitiveWorkloadDecoder", "PosteriorAlphaDecoder", "build_decoder", "register_decoder"]
