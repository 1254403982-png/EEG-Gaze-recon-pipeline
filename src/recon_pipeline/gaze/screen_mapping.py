"""Dynamic mapping from Tobii scene-camera gaze to experiment viewport coordinates."""

from __future__ import annotations

import threading
import time
from collections import deque
from itertools import product
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

MARKER_IDS = (10, 11, 12, 13)
_HOLD_SECONDS = 1.0
_SOURCE_SWITCH_SECONDS = 0.75
_TRAJECTORY_SECONDS = 3.0
_DISPLAY_FILTER_SECONDS = 0.10
_MAX_CORNER_STEP_RATIO = 0.08
_REACQUIRE_FRAMES = 5
_TARGET_WINDOW_MS = 2500.0
_TARGET_MIN_WINDOW_MS = 1200.0
_TARGET_MIN_DWELL_RATIO = 0.60


def marker_png(marker_id: int, size: int = 128) -> bytes:
    """Generate one 4x4 ArUco marker used by the experiment viewport."""

    if marker_id not in MARKER_IDS:
        raise ValueError("Unsupported screen marker ID.")
    import cv2

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, int(size))
    ok, encoded = cv2.imencode(".png", marker)
    if not ok:
        raise RuntimeError("Unable to encode screen marker.")
    return encoded.tobytes()


class ScreenMapper:
    """Track browser fiducials and map rolling gaze samples through a homography."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._layout: Optional[Dict[str, Any]] = None
        self._homography: Optional[np.ndarray] = None
        self._frame_size: Optional[Tuple[int, int]] = None
        self._last_homography_at = 0.0
        self._smoothed_centers: Optional[np.ndarray] = None
        self._pending_centers: Optional[np.ndarray] = None
        self._pending_center_frames = 0
        self._screen_samples: deque[Tuple[float, float, float]] = deque()
        self._display_point: Optional[Tuple[float, float]] = None
        self._display_updated_at = 0.0
        self._anchor_source: Optional[str] = None
        self._anchor_source_last_seen_at = 0.0
        self._last_detection_source: Optional[str] = None
        self._detector: Any = None
        self._latest: Dict[str, Any] = self._invalid("layout_missing")

    def update_layout(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        viewport = payload.get("viewport")
        markers = payload.get("markers")
        elements = payload.get("elements", [])
        if not isinstance(viewport, Mapping) or not isinstance(markers, Sequence):
            raise ValueError("viewport and markers are required.")
        width = float(viewport.get("width", 0))
        height = float(viewport.get("height", 0))
        if width <= 0 or height <= 0:
            raise ValueError("viewport dimensions must be positive.")

        marker_points: Dict[int, Tuple[float, float]] = {}
        for marker in markers:
            if not isinstance(marker, Mapping):
                continue
            marker_id = int(marker.get("id", -1))
            if marker_id not in MARKER_IDS:
                continue
            x = float(marker.get("x_normalized", -1))
            y = float(marker.get("y_normalized", -1))
            if 0 <= x <= 1 and 0 <= y <= 1:
                marker_points[marker_id] = (x, y)
        if set(marker_points) != set(MARKER_IDS):
            raise ValueError("All four screen markers are required.")
        if not _valid_marker_geometry(marker_points, width=1, height=1):
            raise ValueError("Screen marker geometry is degenerate.")

        clean_elements = []
        if isinstance(elements, Sequence):
            for element in elements[:250]:
                clean = _clean_element(element)
                if clean is not None:
                    clean_elements.append(clean)
        layout = {
            "viewport": {"width": width, "height": height},
            "markers": marker_points,
            "elements": clean_elements,
            "reading_aoi": _reading_aoi(clean_elements),
            "reading_scroll": _clean_reading_scroll(payload.get("reading_scroll")),
            "mirror": _clean_mirror(payload.get("mirror")),
            "page": str(payload.get("page", "experiment"))[:80],
            "trial_id": _optional_text(payload.get("trial_id"), 80),
            "slide_id": _optional_text(payload.get("slide_id"), 80),
            "updated_at_ms": int(time.time() * 1000),
        }
        with self._lock:
            self._layout = layout
        return {"ok": True, "marker_ids": list(MARKER_IDS), "elements": len(clean_elements)}

    def process_frame(
        self,
        image: Any,
        trajectory: Sequence[Tuple[float, float, float]],
        *,
        now_monotonic: Optional[float] = None,
    ) -> Dict[str, Any]:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        width, height = image.size
        with self._lock:
            layout = self._layout
        if layout is None:
            latest = self._invalid("layout_missing")
            self._set_latest(latest)
            return latest

        try:
            detected = self._detect(image)
        except (ImportError, AttributeError) as exc:
            latest = self._invalid("detector_unavailable", error=str(exc))
            self._set_latest(latest)
            return latest

        detected_ids = sorted(detected)
        with self._lock:
            detection_source = self._last_detection_source
        complete_geometry = all(marker_id in detected for marker_id in MARKER_IDS)
        geometry_valid = complete_geometry and _valid_marker_geometry(
            detected, width=width, height=height
        )
        if geometry_valid:
            source = np.asarray([detected[marker_id] for marker_id in MARKER_IDS], dtype=np.float32)
            with self._lock:
                previous_centers = (
                    self._smoothed_centers.copy()
                    if self._smoothed_centers is not None
                    else None
                )
                pending_centers = (
                    self._pending_centers.copy()
                    if self._pending_centers is not None
                    else None
                )
                pending_frames = self._pending_center_frames
            frame_diagonal = float(np.hypot(width, height))
            abrupt_change = (
                previous_centers is not None
                and float(np.max(np.linalg.norm(source - previous_centers, axis=1)))
                > frame_diagonal * _MAX_CORNER_STEP_RATIO
            )
            if abrupt_change:
                same_pending = (
                    pending_centers is not None
                    and float(np.max(np.linalg.norm(source - pending_centers, axis=1)))
                    <= frame_diagonal * (_MAX_CORNER_STEP_RATIO / 2.0)
                )
                pending_frames = pending_frames + 1 if same_pending else 1
                with self._lock:
                    self._pending_centers = source
                    self._pending_center_frames = pending_frames
                if pending_frames < _REACQUIRE_FRAMES:
                    geometry_valid = False
            else:
                with self._lock:
                    self._pending_centers = None
                    self._pending_center_frames = 0
        if geometry_valid:
            smoothed = (
                source
                if previous_centers is None
                else 0.72 * source + 0.28 * previous_centers
            )
            try:
                candidate_homography = _homography(
                    smoothed,
                    np.asarray([layout["markers"][marker_id] for marker_id in MARKER_IDS]),
                )
            except ValueError:
                geometry_valid = False
        if geometry_valid:
            with self._lock:
                self._smoothed_centers = smoothed
                self._pending_centers = None
                self._pending_center_frames = 0
                self._homography = candidate_homography
                self._frame_size = (width, height)
                self._last_homography_at = now
                homography = self._homography.copy()
            status = "valid"
        else:
            with self._lock:
                homography = None if self._homography is None else self._homography.copy()
                homography_age = now - self._last_homography_at
                frame_size = self._frame_size
            if (
                homography is None
                or frame_size != (width, height)
                or homography_age > _HOLD_SECONDS
            ):
                missing_status = (
                    "marker_geometry_invalid" if complete_geometry else "markers_missing"
                )
                latest = self._invalid(missing_status, detected_marker_ids=detected_ids)
                self._set_latest(latest)
                return latest
            status = "tracking_hold"

        screen_points = self._screen_trajectory(now)
        if not screen_points and trajectory:
            # Bootstrap with only the newest scene sample. Older samples must not be
            # reprojected through a homography measured after they were captured.
            gaze_x, gaze_y, gaze_age_ms = trajectory[-1]
            mapped = _map_points(homography, [(gaze_x, gaze_y)], width, height)
            if mapped:
                self._record_screen_point(
                    now - max(0.0, gaze_age_ms) / 1000.0,
                    mapped[0][0],
                    mapped[0][1],
                )
                screen_points = self._screen_trajectory(now)
        latest_point = screen_points[-1] if screen_points else None
        focus_point = _trajectory_focus(screen_points)
        target = _target_for(focus_point, layout["elements"])
        dwell_target = _dwell_target_for(screen_points, layout["elements"])
        with self._lock:
            age_ms = max(0.0, (now - self._last_homography_at) * 1000.0)
            source_centers = (
                self._smoothed_centers.copy() if self._smoothed_centers is not None else None
            )
        latest = {
            "valid": True,
            "status": status,
            "coordinate_system": "experiment_viewport_normalized",
            "screen_x_normalized": latest_point[0] if latest_point else None,
            "screen_y_normalized": latest_point[1] if latest_point else None,
            "focus_x_normalized": focus_point[0] if focus_point else None,
            "focus_y_normalized": focus_point[1] if focus_point else None,
            "display_x_normalized": self._display_point[0] if self._display_point else None,
            "display_y_normalized": self._display_point[1] if self._display_point else None,
            "trajectory": [
                {"x_normalized": x, "y_normalized": y, "age_ms": age_ms}
                for x, y, age_ms in screen_points
            ],
            "target": target,
            "dwell_target": dwell_target,
            "reading_aoi": layout["reading_aoi"],
            "detected_marker_ids": detected_ids,
            "required_marker_ids": list(MARKER_IDS),
            "anchor_source": detection_source,
            "homography_age_ms": age_ms,
            "viewport": layout["viewport"],
            "trial_id": layout["trial_id"],
            "slide_id": layout["slide_id"],
            "fiducial_quad_scene": (
                [
                    {"x_normalized": float(x / width), "y_normalized": float(y / height)}
                    for x, y in source_centers
                ]
                if source_centers is not None
                else []
            ),
            "homography": homography.tolist(),
        }
        self._set_latest(latest)
        return latest

    def map_point(
        self, x: Optional[float], y: Optional[float], *, now_monotonic: Optional[float] = None
    ) -> Dict[str, Any]:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        if x is None or y is None:
            return {"valid": False, "status": "invalid_gaze"}
        with self._lock:
            homography = None if self._homography is None else self._homography.copy()
            frame_size = self._frame_size
            age_ms = max(0.0, (now - self._last_homography_at) * 1000.0)
        if homography is None or frame_size is None or age_ms > _HOLD_SECONDS * 1000.0:
            return {"valid": False, "status": "mapping_stale", "homography_age_ms": age_ms}
        mapped = _map_points(homography, [(x, y)], *frame_size)
        if not mapped:
            return {"valid": False, "status": "outside_viewport", "homography_age_ms": age_ms}
        self._record_screen_point(now, mapped[0][0], mapped[0][1])
        screen_points = self._screen_trajectory(now)
        focus_point = _trajectory_focus(screen_points)
        with self._lock:
            layout = self._layout
            if self._latest.get("valid"):
                self._latest = {
                    **self._latest,
                    "screen_x_normalized": mapped[0][0],
                    "screen_y_normalized": mapped[0][1],
                    "focus_x_normalized": focus_point[0] if focus_point else None,
                    "focus_y_normalized": focus_point[1] if focus_point else None,
                    "display_x_normalized": (
                        self._display_point[0] if self._display_point else None
                    ),
                    "display_y_normalized": (
                        self._display_point[1] if self._display_point else None
                    ),
                    "trajectory": [
                        {"x_normalized": px, "y_normalized": py, "age_ms": point_age_ms}
                        for px, py, point_age_ms in screen_points
                    ],
                    "target": (
                        _target_for(focus_point, layout["elements"])
                        if layout is not None
                        else None
                    ),
                    "dwell_target": (
                        _dwell_target_for(screen_points, layout["elements"])
                        if layout is not None
                        else None
                    ),
                    "reading_aoi": layout["reading_aoi"] if layout is not None else None,
                    "homography_age_ms": age_ms,
                }
        return {
            "valid": True,
            "status": "valid" if age_ms <= 120 else "tracking_hold",
            "x_normalized": mapped[0][0],
            "y_normalized": mapped[0][1],
            "homography_age_ms": age_ms,
        }

    def _record_screen_point(self, received_at: float, x: float, y: float) -> None:
        with self._lock:
            self._screen_samples.append((received_at, x, y))
            cutoff = received_at - _TRAJECTORY_SECONDS
            while self._screen_samples and self._screen_samples[0][0] < cutoff:
                self._screen_samples.popleft()
            recent = [
                (point_x, point_y)
                for captured_at, point_x, point_y in self._screen_samples
                if captured_at >= received_at - _DISPLAY_FILTER_SECONDS
            ]
            robust = np.median(np.asarray(recent, dtype=float), axis=0)
            candidate = (float(robust[0]), float(robust[1]))
            if (
                self._display_point is None
                or received_at - self._display_updated_at > _HOLD_SECONDS
            ):
                self._display_point = candidate
            else:
                distance = float(np.hypot(
                    candidate[0] - self._display_point[0],
                    candidate[1] - self._display_point[1],
                ))
                # Small motion is mostly tracker noise; large sustained motion is a
                # real saccade and should remain responsive after the median gate.
                alpha = 0.28 if distance < 0.05 else (0.55 if distance < 0.18 else 0.78)
                self._display_point = (
                    self._display_point[0] + alpha * (candidate[0] - self._display_point[0]),
                    self._display_point[1] + alpha * (candidate[1] - self._display_point[1]),
                )
            self._display_updated_at = received_at

    def _screen_trajectory(self, now: float) -> list[Tuple[float, float, float]]:
        with self._lock:
            cutoff = now - _TRAJECTORY_SECONDS
            while self._screen_samples and self._screen_samples[0][0] < cutoff:
                self._screen_samples.popleft()
            samples = list(self._screen_samples)
        return [(x, y, max(0.0, (now - captured_at) * 1000.0)) for captured_at, x, y in samples]

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            value = dict(self._latest)
            last_at = self._last_homography_at
        if last_at:
            value["homography_age_ms"] = max(0.0, (time.monotonic() - last_at) * 1000.0)
            if value.get("valid") and value["homography_age_ms"] > _HOLD_SECONDS * 1000.0:
                value["valid"] = False
                value["status"] = "mapping_stale"
        return value

    def dashboard_snapshot(self) -> Dict[str, Any]:
        value = self.snapshot()
        with self._lock:
            layout = self._layout
        value["layout"] = (
            {
                "viewport": layout["viewport"],
                "elements": list(layout["elements"]),
                "reading_aoi": layout["reading_aoi"],
                "reading_scroll": layout["reading_scroll"],
                "mirror": layout["mirror"],
                "page": layout["page"],
                "trial_id": layout["trial_id"],
                "slide_id": layout["slide_id"],
                "updated_at_ms": layout["updated_at_ms"],
            }
            if layout is not None
            else None
        )
        return value

    def _detect(self, image: Any) -> Dict[int, Tuple[float, float]]:
        import cv2

        if self._detector is None:
            dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            parameters = cv2.aruco.DetectorParameters()
            parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
            self._detector = cv2.aruco.ArucoDetector(dictionary, parameters)
        rgb = np.asarray(image.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        corners, ids, _rejected = self._detector.detectMarkers(gray)
        aruco_detected = (
            {
                int(marker_id): tuple(np.asarray(marker_corners).reshape(4, 2).mean(axis=0))
                for marker_corners, marker_id in zip(corners, ids.flatten())
                if int(marker_id) in MARKER_IDS
            }
            if ids is not None
            else {}
        )
        color_detected = _detect_color_fiducials(rgb)
        interface_detected = _detect_interface_anchors(rgb)
        with self._lock:
            layout_markers = (
                dict(self._layout["markers"]) if self._layout is not None else {}
            )
        boundary_detected = (
            {}
            if set(interface_detected) == set(MARKER_IDS)
            else _detect_screen_boundary_anchors(rgb, layout_markers)
        )
        candidates = {
            "aruco": aruco_detected,
            "interface": interface_detected,
            "color": color_detected,
            "screen_boundary": boundary_detected,
        }
        complete = {
            source: points
            for source, points in candidates.items()
            if set(points) == set(MARKER_IDS)
            and _valid_marker_geometry(points, width=rgb.shape[1], height=rgb.shape[0])
        }
        with self._lock:
            active_source = self._anchor_source
            active_last_seen_at = self._anchor_source_last_seen_at
            previous_centers = (
                self._smoothed_centers.copy()
                if self._smoothed_centers is not None
                else None
            )

        now = time.monotonic()
        if active_source in complete:
            selected_source = active_source
        elif active_source is not None and now - active_last_seen_at <= _SOURCE_SWITCH_SECONDS:
            # A few blurred/exposure-shifted frames must not switch the coordinate
            # system to a different detector. process_frame will hold the last H.
            with self._lock:
                self._last_detection_source = active_source
            return candidates.get(active_source, {})
        elif complete and previous_centers is not None:
            selected_source = min(
                complete,
                key=lambda source: _center_displacement(
                    complete[source], previous_centers
                ),
            )
        elif complete:
            selected_source = next(
                source
                for source in ("aruco", "interface", "color", "screen_boundary")
                if source in complete
            )
        else:
            # Partial detections are diagnostic only. Never construct a homography
            # from corners produced by different detectors.
            selected_source = None

        selected = complete.get(selected_source, {})
        if not selected:
            selected = max(candidates.values(), key=len, default={})
        with self._lock:
            if selected_source is not None:
                self._anchor_source = selected_source
                self._anchor_source_last_seen_at = now
            self._last_detection_source = selected_source or active_source
        return selected

    def _set_latest(self, value: Dict[str, Any]) -> None:
        with self._lock:
            self._latest = value

    @staticmethod
    def _invalid(status: str, **extra: Any) -> Dict[str, Any]:
        return {
            "valid": False,
            "status": status,
            "coordinate_system": "experiment_viewport_normalized",
            "screen_x_normalized": None,
            "screen_y_normalized": None,
            "focus_x_normalized": None,
            "focus_y_normalized": None,
            "display_x_normalized": None,
            "display_y_normalized": None,
            "trajectory": [],
            "target": None,
            "dwell_target": None,
            "reading_aoi": None,
            "detected_marker_ids": extra.pop("detected_marker_ids", []),
            "required_marker_ids": list(MARKER_IDS),
            "anchor_source": None,
            **extra,
        }


def _homography(source: np.ndarray, destination: np.ndarray) -> np.ndarray:
    import cv2

    matrix = cv2.getPerspectiveTransform(source.astype(np.float32), destination.astype(np.float32))
    if not np.isfinite(matrix).all() or abs(float(np.linalg.det(matrix))) < 1e-12:
        raise ValueError("Degenerate screen homography.")
    return matrix


def _center_displacement(
    detected: Mapping[int, Tuple[float, float]], previous: np.ndarray
) -> float:
    current = np.asarray([detected[marker_id] for marker_id in MARKER_IDS], dtype=float)
    return float(np.mean(np.linalg.norm(current - previous, axis=1)))


def _map_points(
    homography: np.ndarray, points: Sequence[Tuple[float, float]], width: int, height: int
) -> list[Tuple[float, float]]:
    if not points:
        return []
    transformed = _transform_points(homography, points, width, height)
    return [
        (float(x), float(y))
        for x, y in transformed
        if np.isfinite(x) and np.isfinite(y) and -0.02 <= x <= 1.02 and -0.02 <= y <= 1.02
    ]


def _transform_points(
    homography: np.ndarray, points: Sequence[Tuple[float, float]], width: int, height: int
) -> np.ndarray:
    import cv2

    pixels = np.asarray([[[x * width, y * height] for x, y in points]], dtype=np.float32)
    return cv2.perspectiveTransform(pixels, homography)[0]


def _trajectory_focus(
    points: Sequence[Tuple[float, float, float]], window_ms: float = 1500.0
) -> Optional[Tuple[float, float]]:
    recent = [(x, y) for x, y, age_ms in points if age_ms <= window_ms]
    if not recent:
        return None
    values = np.asarray(recent)
    return float(np.median(values[:, 0])), float(np.median(values[:, 1]))


def _target_for(
    point: Optional[Tuple[float, float]], elements: Sequence[Mapping[str, Any]]
) -> Optional[Dict[str, Any]]:
    if point is None:
        return None
    x, y = point
    matches = [
        element
        for element in elements
        if element["x_min"] <= x <= element["x_max"]
        and element["y_min"] <= y <= element["y_max"]
    ]
    if not matches:
        return None
    target = min(
        matches,
        key=lambda item: (item["x_max"] - item["x_min"]) * (item["y_max"] - item["y_min"]),
    )
    return {
        "id": target["id"],
        "tag": target["tag"],
        "text": target["text"],
        "context_text": target.get("context_text", ""),
        "policy_region": target.get("policy_region"),
    }


def _dwell_target_for(
    points: Sequence[Tuple[float, float, float]],
    elements: Sequence[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    recent = [point for point in points if point[2] <= _TARGET_WINDOW_MS]
    if not recent:
        return None
    observed_window_ms = max(point[2] for point in recent) - min(point[2] for point in recent)
    if observed_window_ms < _TARGET_MIN_WINDOW_MS:
        return None
    counts: Dict[str, int] = {}
    targets: Dict[str, Dict[str, Any]] = {}
    for x, y, _age_ms in recent:
        target = _target_for((x, y), elements)
        if target is None:
            continue
        target_id = str(target["id"])
        counts[target_id] = counts.get(target_id, 0) + 1
        targets[target_id] = target
    if not counts:
        return None
    # Prefer a readable leaf when one is covered by the same gaze window. If
    # the gaze is between lines, retain the broad reading target as a useful
    # fallback because scene-camera calibration is approximate.
    specific_ids = {
        target_id
        for target_id, target in targets.items()
        if not _is_broad_reading_target(target)
    }
    if specific_ids:
        counts = {
            target_id: count
            for target_id, count in counts.items()
            if target_id in specific_ids
        }
        if not counts:
            return None
    target_id, count = max(counts.items(), key=lambda item: item[1])
    dwell_ratio = count / len(recent)
    if dwell_ratio < _TARGET_MIN_DWELL_RATIO:
        return None
    return {
        **targets[target_id],
        "dwell_ratio": dwell_ratio,
        "trajectory_samples": len(recent),
        "observed_window_ms": observed_window_ms,
    }


def _is_broad_reading_target(target: Mapping[str, Any]) -> bool:
    tag = str(target.get("tag", "")).strip().lower()
    element_id = str(target.get("id", "")).strip().lower()
    return tag in {"readingcontent", "readingtitle", "h1", "h2", "h3"} or element_id in {
        "readingcontent",
        "readingtitle",
    }


def _clean_element(value: object) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    try:
        x_min = float(value["x_min"])
        y_min = float(value["y_min"])
        x_max = float(value["x_max"])
        y_max = float(value["y_max"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0 <= x_min < x_max <= 1 and 0 <= y_min < y_max <= 1):
        return None
    return {
        "id": str(value.get("id", "content"))[:100],
        "tag": str(value.get("tag", "content"))[:40],
        "text": str(value.get("text", "")).strip()[:240],
        "context_text": str(value.get("context_text", "")).strip()[:500],
        "policy_region": str(value.get("policy_region", ""))[:40],
        "x_min": x_min,
        "y_min": y_min,
        "x_max": x_max,
        "y_max": y_max,
    }


def _reading_aoi(elements: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    reading = [element for element in elements if element.get("policy_region") == "reading"]
    if not reading:
        return None
    preferred = next(
        (element for element in reading if str(element.get("tag")) == "readingContent"),
        None,
    )
    if preferred is not None:
        return {
            key: preferred[key]
            for key in ("id", "tag", "x_min", "y_min", "x_max", "y_max")
        }
    return {
        "id": "reading-aoi",
        "tag": "reading",
        "x_min": min(float(element["x_min"]) for element in reading),
        "y_min": min(float(element["y_min"]) for element in reading),
        "x_max": max(float(element["x_max"]) for element in reading),
        "y_max": max(float(element["y_max"]) for element in reading),
    }


def _optional_text(value: object, limit: int) -> Optional[str]:
    return None if value is None else str(value)[:limit]


def _clean_reading_scroll(value: object) -> Dict[str, float]:
    if not isinstance(value, Mapping):
        return {"top": 0.0, "height": 0.0, "client_height": 0.0}
    cleaned: Dict[str, float] = {}
    for key in ("top", "height", "client_height"):
        try:
            cleaned[key] = max(0.0, float(value.get(key, 0.0)))
        except (TypeError, ValueError):
            cleaned[key] = 0.0
    return cleaned


def _clean_mirror(value: object) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "reading_title": str(value.get("reading_title", ""))[:500],
        "reading_html": str(value.get("reading_html", ""))[:200_000],
        "chat_html": str(value.get("chat_html", ""))[:200_000],
        "chat_scroll_top": max(0.0, _safe_float(value.get("chat_scroll_top"))),
        "chat_input": str(value.get("chat_input", ""))[:10_000],
        "selected_level": _optional_text(value.get("selected_level"), 50),
        "ai_busy": bool(value.get("ai_busy", False)),
    }


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _detect_color_fiducials(rgb: np.ndarray) -> Dict[int, Tuple[float, float]]:
    import cv2

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    ranges = {
        10: ((82, 70, 75), (105, 255, 255)),
        11: ((130, 60, 80), (172, 255, 255)),
        12: ((20, 65, 90), (42, 255, 255)),
        13: ((42, 65, 65), (80, 255, 255)),
    }
    frame_height, frame_width = rgb.shape[:2]
    max_area = max(2500.0, frame_width * frame_height * 0.003)
    candidates_by_id: Dict[int, list[Tuple[int, float, float]]] = {}
    for marker_id, (lower, upper) in ranges.items():
        mask = cv2.inRange(
            hsv,
            np.asarray(lower, dtype=np.uint8),
            np.asarray(upper, dtype=np.uint8),
        )
        count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
        candidates: list[Tuple[int, float, float]] = []
        for index in range(1, count):
            _left, _top, width, height, area = stats[index]
            aspect = width / max(1, height)
            if 8 <= area <= max_area and 0.45 <= aspect <= 2.2:
                candidates.append(
                    (int(area), float(centroids[index][0]), float(centroids[index][1]))
                )
        if candidates:
            candidates_by_id[marker_id] = sorted(candidates, reverse=True)[:10]

    if set(candidates_by_id) != set(MARKER_IDS):
        return {
            marker_id: (candidates[0][1], candidates[0][2])
            for marker_id, candidates in candidates_by_id.items()
        }

    best: Optional[Tuple[float, Dict[int, Tuple[float, float]]]] = None
    candidate_groups = [candidates_by_id[marker_id] for marker_id in MARKER_IDS]
    for combination in product(*candidate_groups):
        areas = [candidate[0] for candidate in combination]
        if max(areas) > min(areas) * 8:
            continue
        detected = {
            marker_id: (candidate[1], candidate[2])
            for marker_id, candidate in zip(MARKER_IDS, combination)
        }
        if not _valid_marker_geometry(detected, width=frame_width, height=frame_height):
            continue
        score = _marker_quad_area(detected) + sum(areas)
        if best is None or score > best[0]:
            best = (score, detected)
    if best is not None:
        return best[1]
    return {
        marker_id: (candidates[0][1], candidates[0][2])
        for marker_id, candidates in candidates_by_id.items()
    }


def _detect_interface_anchors(rgb: np.ndarray) -> Dict[int, Tuple[float, float]]:
    """Find the four natural experiment controls used as screen anchors.

    Marker 10 is the orange OMNI logo. Markers 11, 12 and 13 are the blue AI,
    Send and Next controls. Their joint screen geometry disambiguates blue page
    content without adding calibration-only marks to the participant display.
    """

    import cv2

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    orange = cv2.inRange(
        hsv,
        np.asarray((0, 70, 28), dtype=np.uint8),
        np.asarray((28, 255, 255), dtype=np.uint8),
    )
    blue = cv2.inRange(
        hsv,
        np.asarray((88, 50, 28), dtype=np.uint8),
        np.asarray((132, 255, 255), dtype=np.uint8),
    )
    # The OMNI SVG contains separated orange strokes. At scene-camera scale they
    # are only a few pixels wide, so join nearby strokes before component search.
    orange_candidates = _interface_components(orange, rgb.shape, kernel_size=(21, 11))
    blue_candidates = _interface_components(blue, rgb.shape, kernel_size=(3, 3))
    if not orange_candidates or len(blue_candidates) < 3:
        return {}

    frame_height, frame_width = rgb.shape[:2]

    def normalized(candidate: Tuple[int, float, float, int, int]) -> Tuple[float, float]:
        return candidate[1] / frame_width, candidate[2] / frame_height

    top_left = sorted(
        orange_candidates,
        key=lambda candidate: sum(normalized(candidate)),
    )[:8]
    top_right = sorted(
        blue_candidates,
        key=lambda candidate: normalized(candidate)[0] - normalized(candidate)[1],
        reverse=True,
    )[:12]
    bottom_right = sorted(
        blue_candidates,
        key=lambda candidate: sum(normalized(candidate)),
        reverse=True,
    )[:12]
    bottom_left = sorted(
        blue_candidates,
        key=lambda candidate: normalized(candidate)[1] - normalized(candidate)[0],
        reverse=True,
    )[:12]

    best: Optional[Tuple[float, Dict[int, Tuple[float, float]]]] = None
    for logo, assistant, send, next_button in product(
        top_left, top_right, bottom_right, bottom_left
    ):
        if len({assistant[1:3], send[1:3], next_button[1:3]}) != 3:
            continue
        assistant_aspect = assistant[3] / max(1, assistant[4])
        send_aspect = send[3] / max(1, send[4])
        next_aspect = next_button[3] / max(1, next_button[4])
        if not (0.55 <= assistant_aspect <= 1.8):
            continue
        if not (0.75 <= send_aspect <= 5.5 and 0.75 <= next_aspect <= 5.5):
            continue
        anchors = (logo, assistant, send, next_button)
        interface_detected = {
            marker_id: (candidate[1], candidate[2])
            for marker_id, candidate in zip(MARKER_IDS, anchors)
        }
        if not _valid_marker_geometry(
            interface_detected, width=frame_width, height=frame_height
        ):
            continue
        component_area = sum(candidate[0] for candidate in anchors)
        score = _marker_quad_area(interface_detected) + component_area * 0.35
        if best is None or score > best[0]:
            best = (score, interface_detected)
    return best[1] if best is not None else {}


def _detect_screen_boundary_anchors(
    rgb: np.ndarray,
    layout_markers: Mapping[int, Tuple[float, float]],
) -> Dict[int, Tuple[float, float]]:
    """Project browser anchors through the visible monitor boundary.

    This is a fallback for dark scene-camera frames where one natural control
    briefly loses its color. It uses the physical display edges already present
    in the scene, so no participant-visible calibration marks are required.
    """

    if set(layout_markers) != set(MARKER_IDS):
        return {}
    import cv2

    height, width = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 30, 90)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180.0,
        threshold=max(55, round(width * 0.055)),
        minLineLength=max(120, round(width * 0.14)),
        maxLineGap=max(24, round(width * 0.03)),
    )
    if lines is None:
        return {}

    horizontal = []
    vertical = []
    for raw_line in lines[:, 0]:
        x1, y1, x2, y2 = (float(value) for value in raw_line)
        dx, dy = x2 - x1, y2 - y1
        length = float(np.hypot(dx, dy))
        angle = abs(float(np.degrees(np.arctan2(dy, dx))))
        angle = min(angle, 180.0 - angle)
        value = (length, (x1 + x2) / 2.0, (y1 + y2) / 2.0, (x1, y1, x2, y2))
        if angle <= 12.0:
            horizontal.append(value)
        elif angle >= 60.0:
            vertical.append(value)

    long_horizontal = [line for line in horizontal if line[0] >= width * 0.22]
    long_vertical = [line for line in vertical if line[0] >= height * 0.32]
    top_options = [line for line in long_horizontal if line[2] <= height * 0.35]
    bottom_options = [
        line for line in long_horizontal if height * 0.40 <= line[2] <= height * 0.90
    ]
    left_options = [line for line in long_vertical if line[1] <= width * 0.45]
    right_options = [line for line in long_vertical if line[1] >= width * 0.55]
    if not (top_options and bottom_options and left_options and right_options):
        return {}

    top = min(top_options, key=lambda line: line[2])[3]
    bottom = max(bottom_options, key=lambda line: line[2])[3]
    left = min(left_options, key=lambda line: line[1])[3]
    right = max(right_options, key=lambda line: line[1])[3]
    corners = [
        _line_intersection(top, left),
        _line_intersection(top, right),
        _line_intersection(bottom, right),
        _line_intersection(bottom, left),
    ]
    if any(point is None for point in corners):
        return {}
    screen_corners = np.asarray(corners, dtype=np.float32)
    screen_geometry = {
        marker_id: tuple(screen_corners[index])
        for index, marker_id in enumerate(MARKER_IDS)
    }
    if not _valid_marker_geometry(screen_geometry, width=width, height=height):
        return {}
    if any(
        x < -width * 0.1
        or x > width * 1.1
        or y < -height * 0.1
        or y > height * 1.1
        for x, y in screen_corners
    ):
        return {}

    unit_to_scene = cv2.getPerspectiveTransform(
        np.asarray(((0, 0), (1, 0), (1, 1), (0, 1)), dtype=np.float32),
        screen_corners,
    )
    layout_points = np.asarray(
        [
            [
                [layout_markers[marker_id][0], layout_markers[marker_id][1]]
                for marker_id in MARKER_IDS
            ]
        ],
        dtype=np.float32,
    )
    projected = cv2.perspectiveTransform(layout_points, unit_to_scene)[0]
    return {
        marker_id: (float(point[0]), float(point[1]))
        for marker_id, point in zip(MARKER_IDS, projected)
    }


def _line_intersection(
    first: Tuple[float, float, float, float],
    second: Tuple[float, float, float, float],
) -> Optional[Tuple[float, float]]:
    first_line = np.cross(
        np.asarray((first[0], first[1], 1.0)),
        np.asarray((first[2], first[3], 1.0)),
    )
    second_line = np.cross(
        np.asarray((second[0], second[1], 1.0)),
        np.asarray((second[2], second[3], 1.0)),
    )
    point = np.cross(first_line, second_line)
    if abs(float(point[2])) < 1e-6:
        return None
    return float(point[0] / point[2]), float(point[1] / point[2])


def _interface_components(
    mask: np.ndarray,
    frame_shape: Sequence[int],
    *,
    kernel_size: Tuple[int, int],
) -> list[Tuple[int, float, float, int, int]]:
    import cv2

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
    merged = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(merged, 8)
    frame_height, frame_width = frame_shape[:2]
    max_area = max(3000.0, frame_width * frame_height * 0.025)
    candidates: list[Tuple[int, float, float, int, int]] = []
    for index in range(1, count):
        _left, _top, width, height, area = stats[index]
        aspect = width / max(1, height)
        if 6 <= area <= max_area and 0.2 <= aspect <= 6.0:
            candidates.append(
                (
                    int(area),
                    float(centroids[index][0]),
                    float(centroids[index][1]),
                    int(width),
                    int(height),
                )
            )
    return candidates


def _valid_marker_geometry(
    detected: Mapping[int, Tuple[float, float]], *, width: int, height: int
) -> bool:
    """Reject same-color page content that cannot form the expected screen quadrilateral."""

    top_left, top_right, bottom_right, bottom_left = (
        detected[marker_id] for marker_id in MARKER_IDS
    )
    if not (
        top_left[0] < top_right[0]
        and bottom_left[0] < bottom_right[0]
        and top_left[1] < bottom_left[1]
        and top_right[1] < bottom_right[1]
    ):
        return False
    polygon = np.asarray([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)
    x_values = polygon[:, 0]
    y_values = polygon[:, 1]
    if np.ptp(x_values) < width * 0.25 or np.ptp(y_values) < height * 0.25:
        return False
    area = _marker_quad_area(detected)
    bounding_area = float(np.ptp(x_values) * np.ptp(y_values))
    if area < width * height * 0.08 or area < bounding_area * 0.55:
        return False
    edges = np.linalg.norm(np.roll(polygon, -1, axis=0) - polygon, axis=1)
    horizontal_ratio = float(min(edges[0], edges[2]) / max(edges[0], edges[2]))
    vertical_ratio = float(min(edges[1], edges[3]) / max(edges[1], edges[3]))
    side_slant = max(
        abs(float(bottom_right[0] - top_right[0])),
        abs(float(bottom_left[0] - top_left[0])),
    )
    if side_slant > float(max(edges[0], edges[2])) * 0.20:
        return False
    return horizontal_ratio >= 0.42 and vertical_ratio >= 0.68


def _marker_quad_area(detected: Mapping[int, Tuple[float, float]]) -> float:
    polygon = np.asarray([detected[marker_id] for marker_id in MARKER_IDS], dtype=np.float32)
    shifted = np.roll(polygon, -1, axis=0)
    return 0.5 * abs(float(np.sum(polygon[:, 0] * shifted[:, 1] - polygon[:, 1] * shifted[:, 0])))
