"""Small registry for constructing decoders from configuration."""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from ..contracts import EEGDecoder
from .cognitive_workload import CognitiveWorkloadDecoder
from .posterior_alpha import PosteriorAlphaDecoder

DecoderFactory = Callable[[str, Sequence[str], Mapping[str, Any]], EEGDecoder]
_FACTORIES: Dict[str, DecoderFactory] = {}


def register_decoder(decoder_type: str, factory: DecoderFactory, *, replace: bool = False) -> None:
    key = decoder_type.strip().lower()
    if not key:
        raise ValueError("decoder_type must not be empty.")
    if key in _FACTORIES and not replace:
        raise ValueError("EEG decoder type is already registered: %s" % key)
    _FACTORIES[key] = factory


def build_decoder(
    decoder_type: str,
    decoder_id: str,
    channels: Sequence[str],
    options: Optional[Mapping[str, Any]] = None,
) -> EEGDecoder:
    key = decoder_type.strip().lower()
    try:
        factory = _FACTORIES[key]
    except KeyError as exc:
        raise ValueError("Unknown EEG decoder type: %s" % decoder_type) from exc
    return factory(decoder_id, channels, dict(options or {}))


def _posterior_alpha_factory(
    decoder_id: str,
    channels: Sequence[str],
    options: Mapping[str, Any],
) -> EEGDecoder:
    return PosteriorAlphaDecoder(
        decoder_id=decoder_id,
        channels=channels,
        **dict(options),
    )


register_decoder("posterior_alpha", _posterior_alpha_factory)


def _cognitive_workload_factory(
    decoder_id: str, channels: Sequence[str], options: Mapping[str, Any]
) -> EEGDecoder:
    return CognitiveWorkloadDecoder(
        decoder_id=decoder_id,
        channels=channels,
        **dict(options),
    )


register_decoder("cognitive_workload", _cognitive_workload_factory)
