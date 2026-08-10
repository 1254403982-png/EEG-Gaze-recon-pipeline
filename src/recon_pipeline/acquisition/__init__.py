"""Acquisition contracts and hardware adapters."""

from .base import EEGSource, RawEEGChunk
from .brainco import BRAINCO_32_CHANNELS, BrainCoSource, LegacyBrainCoSource
from .brainco_sdk import BrainCoSDKAcquirer

__all__ = [
    "BRAINCO_32_CHANNELS",
    "BrainCoSDKAcquirer",
    "BrainCoSource",
    "EEGSource",
    "LegacyBrainCoSource",
    "RawEEGChunk",
]
