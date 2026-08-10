"""Fixed AOI eye metrics derived from mapped Tobii gaze samples."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from ..models import EyeFeatures


@dataclass(frozen=True)
class _Point:
    time_seconds: float
    x: float
    y: float


class EyeFeatureExtractor:
    """Calculate dwell and I-DT fixation metrics in the reading AOI."""

    def __init__(
        self,
        *,
        fixation_dispersion: float = 0.035,
        fixation_min_duration_ms: float = 100.0,
        maximum_sample_gap_ms: float = 100.0,
    ) -> None:
        self.fixation_dispersion = float(fixation_dispersion)
        self.fixation_min_duration_seconds = float(fixation_min_duration_ms) / 1000.0
        self.maximum_sample_gap_seconds = float(maximum_sample_gap_ms) / 1000.0
        if self.fixation_dispersion <= 0:
            raise ValueError("fixation_dispersion must be positive.")
        if self.fixation_min_duration_seconds <= 0:
            raise ValueError("fixation_min_duration_ms must be positive.")
        if self.maximum_sample_gap_seconds <= 0:
            raise ValueError("maximum_sample_gap_ms must be positive.")

    def snapshot(self, screen_mapping: Mapping[str, Any]) -> EyeFeatures:
        if not screen_mapping.get("valid"):
            return EyeFeatures()
        aoi = _clean_aoi(screen_mapping.get("reading_aoi"))
        points = _trajectory_points(screen_mapping.get("trajectory"))
        if aoi is None or not points:
            return EyeFeatures()

        dwell_seconds = _aoi_dwell_seconds(
            points,
            aoi,
            maximum_gap_seconds=self.maximum_sample_gap_seconds,
        )
        fixation_durations = _idt_fixation_durations(
            points,
            aoi,
            dispersion=self.fixation_dispersion,
            minimum_duration_seconds=self.fixation_min_duration_seconds,
            maximum_gap_seconds=self.maximum_sample_gap_seconds,
        )
        revisit_count, revisit_time = _aoi_revisit_metrics(
            points,
            aoi,
            minimum_visit_seconds=self.fixation_min_duration_seconds,
            maximum_gap_seconds=self.maximum_sample_gap_seconds,
        )
        return EyeFeatures(
            aoi_dwell_time=float(dwell_seconds),
            fixation_count=len(fixation_durations),
            mean_fixation_duration=(
                float(np.mean(fixation_durations)) if fixation_durations else 0.0
            ),
            aoi_revisit_count=revisit_count,
            aoi_revisit_time=float(revisit_time),
        )


def _trajectory_points(value: object) -> List[_Point]:
    if not isinstance(value, Sequence):
        return []
    points: List[_Point] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        try:
            x = float(item["x_normalized"])
            y = float(item["y_normalized"])
            age_ms = float(item["age_ms"])
        except (KeyError, TypeError, ValueError):
            continue
        if not np.isfinite([x, y, age_ms]).all() or not (0 <= x <= 1 and 0 <= y <= 1):
            continue
        points.append(_Point(time_seconds=-max(0.0, age_ms) / 1000.0, x=x, y=y))
    return sorted(points, key=lambda point: point.time_seconds)


def _clean_aoi(value: object) -> Optional[Tuple[float, float, float, float]]:
    if not isinstance(value, Mapping):
        return None
    try:
        bounds = tuple(float(value[key]) for key in ("x_min", "y_min", "x_max", "y_max"))
    except (KeyError, TypeError, ValueError):
        return None
    x_min, y_min, x_max, y_max = bounds
    if not (0 <= x_min < x_max <= 1 and 0 <= y_min < y_max <= 1):
        return None
    return x_min, y_min, x_max, y_max


def _inside(point: _Point, aoi: Tuple[float, float, float, float]) -> bool:
    x_min, y_min, x_max, y_max = aoi
    return x_min <= point.x <= x_max and y_min <= point.y <= y_max


def _aoi_dwell_seconds(
    points: Sequence[_Point],
    aoi: Tuple[float, float, float, float],
    *,
    maximum_gap_seconds: float,
) -> float:
    dwell = 0.0
    for before, after in zip(points, points[1:]):
        delta = after.time_seconds - before.time_seconds
        if 0 < delta <= maximum_gap_seconds and _inside(before, aoi) and _inside(after, aoi):
            dwell += delta
    return max(0.0, dwell)


def _aoi_revisit_metrics(
    points: Sequence[_Point],
    aoi: Tuple[float, float, float, float],
    *,
    minimum_visit_seconds: float,
    maximum_gap_seconds: float,
) -> Tuple[int, float]:
    """Count returns to the reading AOI and their accumulated dwell time.

    A visit is a contiguous in-AOI run separated by at least one out-of-AOI
    sample (or a sample gap). Very short runs are ignored to avoid treating a
    single noisy sample as a genuine return. The first usable visit is the
    initial reading pass; subsequent usable visits are revisits.
    """

    segments: List[List[_Point]] = []
    current: List[_Point] = []
    for point in points:
        inside = _inside(point, aoi)
        separated = (
            current
            and point.time_seconds - current[-1].time_seconds > maximum_gap_seconds
        )
        if separated or not inside:
            if current:
                segments.append(current)
            current = []
        if inside:
            current.append(point)
    if current:
        segments.append(current)

    visit_dwell: List[float] = []
    for segment in segments:
        dwell = 0.0
        for before, after in zip(segment, segment[1:]):
            delta = after.time_seconds - before.time_seconds
            if 0 < delta <= maximum_gap_seconds:
                dwell += delta
        if dwell >= minimum_visit_seconds:
            visit_dwell.append(dwell)
    if len(visit_dwell) <= 1:
        return 0, 0.0
    return len(visit_dwell) - 1, float(sum(visit_dwell[1:]))


def _idt_fixation_durations(
    points: Sequence[_Point],
    aoi: Tuple[float, float, float, float],
    *,
    dispersion: float,
    minimum_duration_seconds: float,
    maximum_gap_seconds: float,
) -> List[float]:
    sequences: List[List[_Point]] = []
    current: List[_Point] = []
    for point in points:
        separated = current and point.time_seconds - current[-1].time_seconds > maximum_gap_seconds
        if separated or not _inside(point, aoi):
            if current:
                sequences.append(current)
            current = []
        if _inside(point, aoi):
            current.append(point)
    if current:
        sequences.append(current)

    durations: List[float] = []
    for sequence in sequences:
        start = 0
        while start < len(sequence):
            end = start
            while (
                end + 1 < len(sequence)
                and sequence[end].time_seconds - sequence[start].time_seconds
                < minimum_duration_seconds
            ):
                end += 1
            if sequence[end].time_seconds - sequence[start].time_seconds < minimum_duration_seconds:
                break
            if _dispersion(sequence[start : end + 1]) > dispersion:
                start += 1
                continue
            while end + 1 < len(sequence) and _dispersion(sequence[start : end + 2]) <= dispersion:
                end += 1
            durations.append(sequence[end].time_seconds - sequence[start].time_seconds)
            start = end + 1
    return durations


def _dispersion(points: Sequence[_Point]) -> float:
    xs = [point.x for point in points]
    ys = [point.y for point in points]
    return max(max(xs) - min(xs), max(ys) - min(ys))
