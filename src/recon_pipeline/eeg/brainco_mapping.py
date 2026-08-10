"""Explicit BrainCo 32-channel to posterior 7-channel mapping."""

from __future__ import annotations

from typing import ClassVar, Sequence

import numpy as np

OUTPUT_CHANNELS = ("CP5", "CP6", "PO3", "PO4", "O1", "Oz", "O2")


class BrainCoNeuraDockMapper:
    """Create the posterior layout expected by the current Alpha algorithm.

    PO3, PO4, and Oz are spatial surrogates, not measured electrodes. The
    mapping is surfaced as metadata so research exports cannot hide that fact.
    """

    mapping: ClassVar[dict] = {
        "CP5": "CP5",
        "CP6": "CP6",
        "PO3": "0.5*(P3+O1)",
        "PO4": "0.5*(P4+O2)",
        "O1": "O1",
        "Oz": "(PZ+O1+O2)/3",
        "O2": "O2",
    }

    def transform(self, samples: np.ndarray, channel_names: Sequence[str]) -> np.ndarray:
        matrix = np.asarray(samples, dtype=np.float32)
        if matrix.ndim != 2:
            raise ValueError("BrainCo EEG must be a 2D channels-by-samples array.")
        names = tuple(str(name).strip().upper() for name in channel_names)
        if matrix.shape[0] != len(names) and matrix.shape[1] == len(names):
            matrix = matrix.T
        if matrix.shape[0] != len(names):
            raise ValueError("BrainCo channel names do not match the EEG matrix.")
        index = {name: position for position, name in enumerate(names)}
        required = {"CP5", "CP6", "P3", "P4", "PZ", "O1", "O2"}
        missing = sorted(required.difference(index))
        if missing:
            raise ValueError("Missing required BrainCo channels: %s" % ", ".join(missing))

        cp5, cp6 = matrix[index["CP5"]], matrix[index["CP6"]]
        p3, p4, pz = matrix[index["P3"]], matrix[index["P4"]], matrix[index["PZ"]]
        o1, o2 = matrix[index["O1"]], matrix[index["O2"]]
        return np.vstack(
            [cp5, cp6, (p3 + o1) / 2.0, (p4 + o2) / 2.0, o1, (pz + o1 + o2) / 3.0, o2]
        ).astype(np.float32)
