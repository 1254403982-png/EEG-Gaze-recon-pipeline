"""Deterministic JSONL gaze replay for integration tests and UI development."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from ..clock import Timestamp
from ..models import EyeFeatures, GazeFeatures, SignalStatus


class ReplayGazeProvider:
    def __init__(self, source: Path, *, loop: bool = False) -> None:
        self.source = source.expanduser().resolve()
        self.loop = loop
        self._records: List[dict] = []
        self._index = 0
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, session_id: str) -> None:
        del session_id
        records: List[dict] = []
        with self.source.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("Gaze replay line %s must be a JSON object." % line_number)
                records.append(value)
        if not records:
            raise ValueError("Gaze replay file contains no records.")
        self._records, self._index, self._running = records, 0, True

    def read(self) -> Optional[GazeFeatures]:
        if not self._running:
            raise RuntimeError("Gaze replay is not started.")
        if self._index >= len(self._records):
            if not self.loop:
                return None
            self._index = 0
        item = self._records[self._index]
        self._index += 1
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else item
        timestamp = item.get("timestamp") if isinstance(item.get("timestamp"), dict) else {}
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        return GazeFeatures(
            timestamp=Timestamp.now(
                device_seconds=_optional_float(
                    payload.get("device_timestamp", timestamp.get("device_seconds"))
                )
            ),
            status=SignalStatus(str(payload.get("status", "available"))),
            quality=str(payload.get("quality", "pass")),
            x_normalized=_optional_float(payload.get("x_normalized")),
            y_normalized=_optional_float(payload.get("y_normalized")),
            primary_aoi=_optional_str(payload.get("primary_aoi")),
            fixation_duration_ms=_optional_float(payload.get("fixation_duration_ms")),
            fixation_rate=_optional_float(payload.get("fixation_rate")),
            saccade_rate=_optional_float(payload.get("saccade_rate")),
            pupil_dilation=_optional_float(payload.get("pupil_dilation")),
            gaze_entropy=_optional_float(payload.get("gaze_entropy")),
            blink_rate=_optional_float(payload.get("blink_rate")),
            valid_sample_ratio=_optional_float(payload.get("valid_sample_ratio")),
            source="replay",
            metadata={**metadata, "replay_index": self._index - 1},
            eye=EyeFeatures(
                aoi_dwell_time=_optional_float(_eye_value(payload, "aoi_dwell_time")),
                fixation_count=_optional_int(_eye_value(payload, "fixation_count")),
                mean_fixation_duration=_optional_float(
                    _eye_value(payload, "mean_fixation_duration")
                ),
                aoi_revisit_count=_optional_int(_eye_value(payload, "aoi_revisit_count")),
                aoi_revisit_time=_optional_float(_eye_value(payload, "aoi_revisit_time")),
            ),
        )

    def stop(self) -> None:
        self._running = False
        self._records = []
        self._index = 0


def _optional_float(value: object) -> Optional[float]:
    return None if value is None else float(value)


def _optional_str(value: object) -> Optional[str]:
    return None if value is None else str(value)


def _optional_int(value: object) -> Optional[int]:
    return None if value is None else int(value)


def _eye_value(item: dict, name: str) -> object:
    eye = item.get("eye")
    return eye.get(name) if isinstance(eye, dict) else item.get(name)
