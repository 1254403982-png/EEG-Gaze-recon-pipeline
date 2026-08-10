"""Realtime Tobii Pro Glasses 3 gaze provider.

The SDK is imported lazily so replay-only and EEG-only installations do not
need the Tobii runtime.  RTSP acquisition runs in its own asyncio thread and
the synchronous provider boundary exposes rolling, quality-gated features.
"""

from __future__ import annotations

import asyncio
import io
import logging
import math
import threading
import time
from collections import deque
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit

from ..clock import Timestamp
from ..models import GazeFeatures, SignalStatus
from .eye_features import EyeFeatureExtractor
from .screen_mapping import ScreenMapper

LOGGER = logging.getLogger(__name__)
_STREAM_STALE_SECONDS = 5.0
_STREAM_WAIT_SECONDS = 0.05
_MAPPING_INTERVAL_SECONDS = 0.04
_JPEG_INTERVAL_SECONDS = 0.12


@dataclass(frozen=True)
class AOIRegion:
    """A normalized rectangle in the Tobii scene-camera coordinate system."""

    name: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def contains(self, x: float, y: float) -> bool:
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max


@dataclass(frozen=True)
class SceneFrame:
    jpeg: bytes
    timestamp: Timestamp
    width: int
    height: int
    gaze_x: Optional[float] = None
    gaze_y: Optional[float] = None
    gaze_trajectory: Tuple[Tuple[float, float, float], ...] = ()
    trajectory_window_ms: float = 0.0
    screen_mapping: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _GazeSample:
    received_monotonic: float
    device_seconds: Optional[float]
    x: Optional[float]
    y: Optional[float]

    @property
    def valid(self) -> bool:
        return self.x is not None and self.y is not None


class TobiiGazeFeatureExtractor:
    """Convert G3 ``gaze2d`` samples into a rolling feature snapshot."""

    def __init__(
        self,
        *,
        window_seconds: float = 3.0,
        min_valid_ratio: float = 0.60,
        min_valid_samples: int = 5,
        fixation_dispersion: float = 0.035,
        fixation_min_duration_ms: float = 100.0,
        saccade_velocity_threshold: float = 0.80,
        aoi_regions: Sequence[AOIRegion] = (),
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive.")
        if not 0.0 <= min_valid_ratio <= 1.0:
            raise ValueError("min_valid_ratio must be between 0 and 1.")
        if min_valid_samples < 1:
            raise ValueError("min_valid_samples must be at least 1.")
        self.window_seconds = float(window_seconds)
        self.min_valid_ratio = float(min_valid_ratio)
        self.min_valid_samples = int(min_valid_samples)
        self.fixation_dispersion = float(fixation_dispersion)
        self.fixation_min_duration_ms = float(fixation_min_duration_ms)
        self.saccade_velocity_threshold = float(saccade_velocity_threshold)
        self.aoi_regions = tuple(aoi_regions)
        self._samples: Deque[_GazeSample] = deque()
        self._total_samples = 0

    @property
    def total_samples(self) -> int:
        return self._total_samples

    def clear(self) -> None:
        self._samples.clear()
        self._total_samples = 0

    def latest_valid_point(self) -> Tuple[Optional[float], Optional[float]]:
        for sample in reversed(self._samples):
            if sample.valid:
                return sample.x, sample.y
        return None, None

    def recent_valid_points(
        self, *, now_monotonic: Optional[float] = None
    ) -> Tuple[Tuple[float, float, float], ...]:
        """Return valid points in the rolling window as ``(x, y, age_ms)``."""

        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        self._prune(now)
        return tuple(
            (float(sample.x), float(sample.y), max(0.0, (now - sample.received_monotonic) * 1000.0))
            for sample in self._samples
            if sample.valid
        )

    def add(
        self,
        payload: object,
        device_seconds: object = None,
        *,
        received_monotonic: Optional[float] = None,
    ) -> None:
        received = time.monotonic() if received_monotonic is None else float(received_monotonic)
        x, y = _extract_gaze2d(payload)
        self._samples.append(
            _GazeSample(
                received_monotonic=received,
                device_seconds=_finite_float(device_seconds),
                x=x,
                y=y,
            )
        )
        self._total_samples += 1
        self._prune(received)

    def snapshot(
        self,
        *,
        now_monotonic: Optional[float] = None,
        source: str = "tobii_g3",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> GazeFeatures:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        self._prune(now)
        samples = list(self._samples)
        valid = [sample for sample in samples if sample.valid]
        valid_ratio = len(valid) / len(samples) if samples else 0.0
        latest = valid[-1] if valid else (samples[-1] if samples else None)
        sample_age_ms = (
            max(0.0, (now - latest.received_monotonic) * 1000.0)
            if latest is not None
            else None
        )
        quality_pass = (
            len(valid) >= self.min_valid_samples
            and valid_ratio >= self.min_valid_ratio
            and sample_age_ms is not None
            and sample_age_ms <= 1000.0
        )

        fixation_duration_ms = _current_fixation_duration_ms(
            valid, dispersion=self.fixation_dispersion
        )
        duration_seconds = _sample_span_seconds(valid)
        fixation_rate = _fixation_rate_per_minute(
            valid,
            dispersion=self.fixation_dispersion,
            min_duration_ms=self.fixation_min_duration_ms,
            duration_seconds=duration_seconds,
        )
        saccade_rate = _saccade_rate_per_second(
            valid,
            velocity_threshold=self.saccade_velocity_threshold,
            duration_seconds=duration_seconds,
        )
        entropy = _normalized_spatial_entropy(valid)
        x = latest.x if latest is not None and latest.valid else None
        y = latest.y if latest is not None and latest.valid else None

        details: Dict[str, Any] = dict(metadata or {})
        details.update(
            {
                "coordinate_system": "tobii_scene_camera_normalized",
                "clock_domain": "host_monotonic_at_sample_receive",
                "device_time_basis": "tobii_rtsp_timestamp",
                "scene_region": _scene_region(x, y) if x is not None and y is not None else None,
                "window_seconds": self.window_seconds,
                "window_samples": len(samples),
                "valid_samples": len(valid),
                "total_samples": self._total_samples,
                "sample_age_ms": sample_age_ms,
                "fixation_rate_unit": "per_minute",
                "saccade_rate_unit": "per_second",
            }
        )
        return GazeFeatures(
            timestamp=(
                Timestamp.from_monotonic_ns(
                    int(latest.received_monotonic * 1_000_000_000), latest.device_seconds
                )
                if latest is not None
                else Timestamp.now()
            ),
            status=SignalStatus.AVAILABLE if quality_pass else SignalStatus.WARNING,
            quality="pass" if quality_pass else "insufficient_valid_samples",
            x_normalized=x,
            y_normalized=y,
            primary_aoi=self._aoi_for(x, y),
            fixation_duration_ms=fixation_duration_ms,
            fixation_rate=fixation_rate,
            saccade_rate=saccade_rate,
            gaze_entropy=entropy,
            valid_sample_ratio=valid_ratio,
            source=source,
            metadata=details,
        )

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._samples and self._samples[0].received_monotonic < cutoff:
            self._samples.popleft()

    def _aoi_for(self, x: Optional[float], y: Optional[float]) -> Optional[str]:
        if x is None or y is None:
            return None
        for region in self.aoi_regions:
            if region.contains(x, y):
                return region.name
        # A scene-camera region is not a screen/DOM AOI.  Keep primary_aoi
        # empty unless the caller supplied an experimentally calibrated map.
        return None


class TobiiG3Provider:
    """Synchronous pipeline provider backed by a G3 RTSP gaze stream."""

    def __init__(
        self,
        hostname: Optional[str] = None,
        *,
        using_zeroconf: bool = True,
        discovery_timeout_seconds: float = 8.0,
        connect_timeout_seconds: float = 20.0,
        read_timeout_seconds: float = 1.0,
        rtsp_transport: str = "tcp",
        scene_camera: bool = True,
        extractor: Optional[TobiiGazeFeatureExtractor] = None,
        eye_extractor: Optional[EyeFeatureExtractor] = None,
        screen_mapper: Optional[ScreenMapper] = None,
    ) -> None:
        self.hostname = hostname.strip() if hostname and hostname.strip() else None
        self.using_zeroconf = bool(using_zeroconf)
        self.discovery_timeout_seconds = float(discovery_timeout_seconds)
        self.connect_timeout_seconds = float(connect_timeout_seconds)
        self.read_timeout_seconds = float(read_timeout_seconds)
        normalized_transport = rtsp_transport.strip().lower()
        if normalized_transport not in {"tcp", "udp"}:
            raise ValueError("rtsp_transport must be 'tcp' or 'udp'.")
        self.rtsp_transport = normalized_transport
        self.scene_camera_enabled = bool(scene_camera)
        self.extractor = extractor or TobiiGazeFeatureExtractor()
        self.eye_extractor = eye_extractor or EyeFeatureExtractor(
            fixation_dispersion=self.extractor.fixation_dispersion,
            fixation_min_duration_ms=self.extractor.fixation_min_duration_ms,
        )
        self.screen_mapper = screen_mapper or ScreenMapper()
        self.session_id: Optional[str] = None
        self.device_name: Optional[str] = None
        self.last_error: Optional[BaseException] = None
        self._connected = False
        self._started = False
        self._last_emitted_total = 0
        self._ready = threading.Event()
        self._stop_requested = threading.Event()
        self._condition = threading.Condition()
        self._frame_lock = threading.Lock()
        self._latest_scene_frame: Optional[SceneFrame] = None
        self._last_frame_encoded_monotonic = 0.0
        self._last_mapping_processed_monotonic = 0.0
        self._calibration_requested = threading.Event()
        self._calibration_lock = threading.Lock()
        self._calibration: Dict[str, Any] = {
            "status": "idle",
            "success": None,
            "detail": None,
        }
        self._pending_raw_samples: Deque[Dict[str, Any]] = deque()
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def start(self, session_id: str) -> None:
        if self.is_running:
            return
        if not session_id.strip():
            raise ValueError("session_id must not be empty.")
        self.session_id = session_id
        self.device_name = None
        self.last_error = None
        self._connected = False
        self._started = True
        self._last_emitted_total = 0
        self.extractor.clear()
        with self._condition:
            self._pending_raw_samples.clear()
        with self._frame_lock:
            self._latest_scene_frame = None
            self._last_frame_encoded_monotonic = 0.0
            self._last_mapping_processed_monotonic = 0.0
        self._ready.clear()
        self._stop_requested.clear()
        self._calibration_requested.clear()
        self._set_calibration("idle")
        self._thread = threading.Thread(
            target=self._thread_main,
            daemon=True,
            name="tobii-g3-rtsp",
        )
        self._thread.start()
        if not self._ready.wait(timeout=self.connect_timeout_seconds):
            self.stop()
            raise TimeoutError(
                "Timed out connecting to Tobii G3 after %.1f seconds."
                % self.connect_timeout_seconds
            )
        if self.last_error is not None:
            error = self.last_error
            self.stop()
            raise RuntimeError("Unable to start Tobii G3 gaze stream: %s" % error) from error
        LOGGER.info(
            "Tobii G3 gaze stream connected: %s",
            self.device_name or self.hostname or "auto-discovered device",
        )

    def read(self) -> GazeFeatures:
        if not self._started:
            raise RuntimeError("Tobii G3 provider is not started.")
        deadline = time.monotonic() + self.read_timeout_seconds
        with self._condition:
            while (
                self.extractor.total_samples <= self._last_emitted_total
                and self.last_error is None
                and not self._stop_requested.is_set()
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=remaining)
            if self.last_error is not None:
                return GazeFeatures(
                    timestamp=Timestamp.now(),
                    status=SignalStatus.UNAVAILABLE,
                    quality="stream_error",
                    source="tobii_g3",
                    metadata={
                        "reason": str(self.last_error),
                        "hostname": self.hostname,
                        "device_name": self.device_name,
                    },
                )
            features = self.extractor.snapshot(
                metadata={
                    "hostname": self.hostname,
                    "device_name": self.device_name,
                    "connected": self._connected,
                    "session_id": self.session_id,
                }
            )
            screen_mapping = self.screen_mapper.snapshot()
            features.metadata["screen_mapping"] = screen_mapping
            features.eye = self.eye_extractor.snapshot(screen_mapping)
            mapped_samples = _mapped_gaze_samples(screen_mapping.get("trajectory"))
            if screen_mapping.get("valid") and mapped_samples:
                features.fixation_duration_ms = _current_fixation_duration_ms(
                    mapped_samples, dispersion=self.extractor.fixation_dispersion
                )
                features.gaze_entropy = _normalized_spatial_entropy(mapped_samples)
                mapped_span = _sample_span_seconds(mapped_samples)
                features.fixation_rate = _fixation_rate_per_minute(
                    mapped_samples,
                    dispersion=self.extractor.fixation_dispersion,
                    min_duration_ms=self.extractor.fixation_min_duration_ms,
                    duration_seconds=mapped_span,
                )
                features.saccade_rate = _saccade_rate_per_second(
                    mapped_samples,
                    velocity_threshold=self.extractor.saccade_velocity_threshold,
                    duration_seconds=mapped_span,
                )
                features.metadata["gaze_metric_coordinate_system"] = (
                    "experiment_viewport_normalized"
                )
            else:
                features.metadata["gaze_metric_coordinate_system"] = (
                    "tobii_scene_camera_normalized"
                )
            target = screen_mapping.get("dwell_target")
            if screen_mapping.get("valid") and isinstance(target, Mapping):
                features.primary_aoi = str(target.get("text") or target.get("id") or "") or None
            self._last_emitted_total = self.extractor.total_samples
            return features

    def stop(self) -> None:
        self._stop_requested.set()
        with self._condition:
            self._condition.notify_all()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5.0)
        self._thread = None
        self._connected = False
        self._started = False

    def latest_scene_frame(self) -> Optional[SceneFrame]:
        with self._frame_lock:
            return self._latest_scene_frame

    def latest_screen_mapping(self) -> Dict[str, Any]:
        return self.screen_mapper.dashboard_snapshot()

    def calibration_status(self) -> Dict[str, Any]:
        with self._calibration_lock:
            value = dict(self._calibration)
        value["connected"] = self.is_connected
        value["device_name"] = self.device_name
        return value

    def request_calibration(self) -> Dict[str, Any]:
        if not self.is_running or not self.is_connected:
            raise RuntimeError("Tobii Glasses 3 is not connected.")
        with self._calibration_lock:
            if self._calibration["status"] in {"requested", "running"}:
                return dict(self._calibration)
            self._calibration = {
                "status": "requested",
                "success": None,
                "detail": None,
            }
        self._calibration_requested.set()
        return self.calibration_status()

    def update_screen_layout(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        return self.screen_mapper.update_layout(payload)

    def drain_raw_samples(self) -> List[Dict[str, Any]]:
        """Remove and return raw gaze samples waiting for durable storage."""

        with self._condition:
            samples = list(self._pending_raw_samples)
            self._pending_raw_samples.clear()
            return samples

    def _record_gaze_payload(
        self,
        payload: object,
        device_seconds: object,
        *,
        received_monotonic: Optional[float] = None,
    ) -> None:
        received = time.monotonic() if received_monotonic is None else float(received_monotonic)
        x, y = _extract_gaze2d(payload)
        screen = self.screen_mapper.map_point(x, y, now_monotonic=received)
        timestamp = Timestamp.from_monotonic_ns(
            int(received * 1_000_000_000), _finite_float(device_seconds)
        )
        with self._condition:
            self.extractor.add(
                payload,
                device_seconds,
                received_monotonic=received,
            )
            self._pending_raw_samples.append(
                {
                    "timestamp": timestamp.to_dict(),
                    "x_normalized": x,
                    "y_normalized": y,
                    "valid": x is not None and y is not None,
                    "screen_mapping": screen,
                }
            )
            self._condition.notify_all()

    def _thread_main(self) -> None:
        while not self._stop_requested.is_set():
            try:
                self.last_error = None
                asyncio.run(self._stream_gaze())
                if not self._stop_requested.is_set():
                    raise RuntimeError("Tobii G3 stream ended unexpectedly.")
            except BaseException as exc:
                if self._stop_requested.is_set():
                    break
                had_connected = self._ready.is_set()
                self.last_error = exc
                self._connected = False
                with self._frame_lock:
                    self._latest_scene_frame = None
                self._ready.set()
                with self._condition:
                    self._condition.notify_all()
                if not had_connected:
                    LOGGER.exception("Unable to start Tobii G3 stream: %s", exc)
                    break
                LOGGER.warning("Tobii G3 stream interrupted; reconnecting: %s", exc)
                if self._stop_requested.wait(1.0):
                    break
        self._connected = False
        self._ready.set()
        with self._condition:
            self._condition.notify_all()

    def _set_calibration(
        self, status: str, *, success: Optional[bool] = None, detail: Optional[str] = None
    ) -> None:
        with self._calibration_lock:
            self._calibration = {
                "status": status,
                "success": success,
                "detail": detail,
            }

    async def _stream_gaze(self) -> None:
        try:
            from g3pylib import connect_to_glasses
        except ImportError as exc:
            raise RuntimeError(
                "g3pylib is not installed. Install the project with the 'tobii' extra."
            ) from exc

        if self.hostname is not None:
            connector = connect_to_glasses.with_hostname(
                self.hostname,
                using_zeroconf=self.using_zeroconf,
                using_ip=True,
            )
        else:
            connector = connect_to_glasses.with_zeroconf(
                using_ip=True,
                timeout=self.discovery_timeout_seconds * 1000.0,
            )
        connector = _connector_with_rtsp_transport(
            connect_to_glasses,
            connector,
            self.rtsp_transport,
        )
        LOGGER.info("Tobii RTSP transport: %s", self.rtsp_transport.upper())
        if not self.scene_camera_enabled:
            LOGGER.warning(
                "Tobii scene camera disabled; gaze-only diagnostic mode has no screen mapping"
            )

        async with connector as glasses:
            try:
                self.device_name = str(await glasses.rudimentary.get_name())
            except Exception:
                self.device_name = self.hostname or "Tobii Pro Glasses 3"
            async with AsyncExitStack() as stack:
                streams = await stack.enter_async_context(
                    glasses.stream_rtsp(
                        scene_camera=self.scene_camera_enabled,
                        gaze=True,
                    )
                )
                gaze_stream = await stack.enter_async_context(streams.gaze.decode())
                scene_stream = None
                if self.scene_camera_enabled:
                    scene_stream = await stack.enter_async_context(
                        streams.scene_camera.decode()
                    )
                self._connected = True
                self.last_error = None
                self._ready.set()
                last_gaze_at = time.monotonic()
                last_scene_at = last_gaze_at
                gaze_task = asyncio.create_task(gaze_stream.get())
                scene_task = (
                    asyncio.create_task(scene_stream.get())
                    if scene_stream is not None
                    else None
                )
                calibration_task: Optional[asyncio.Task] = None
                try:
                    while not self._stop_requested.is_set():
                        if self._calibration_requested.is_set() and calibration_task is None:
                            self._calibration_requested.clear()
                            self._set_calibration("running")
                            calibration_task = asyncio.create_task(glasses.calibrate.run())

                        stream_tasks = {gaze_task}
                        if scene_task is not None:
                            stream_tasks.add(scene_task)
                        done, _pending = await asyncio.wait(
                            stream_tasks,
                            timeout=_STREAM_WAIT_SECONDS,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        _drain_async_queue(streams.gaze.rtcp_queue)
                        if self.scene_camera_enabled:
                            _drain_async_queue(streams.scene_camera.rtcp_queue)
                        if gaze_task in done:
                            gaze_items = [gaze_task.result()]
                            while True:
                                try:
                                    gaze_items.append(gaze_stream.get_nowait())
                                except asyncio.QueueEmpty:
                                    break
                            gaze_task = asyncio.create_task(gaze_stream.get())
                            last_gaze_at = time.monotonic()
                            for payload, device_seconds in gaze_items:
                                self._record_gaze_payload(payload, device_seconds)

                        if scene_task is not None and scene_task in done:
                            assert scene_stream is not None
                            scene_item = scene_task.result()
                            while True:
                                try:
                                    scene_item = scene_stream.get_nowait()
                                except asyncio.QueueEmpty:
                                    break
                            scene_task = asyncio.create_task(scene_stream.get())
                            last_scene_at = time.monotonic()
                            self._store_scene_frame(*scene_item)

                        if calibration_task is not None and calibration_task.done():
                            try:
                                success = bool(calibration_task.result())
                            except Exception as exc:
                                self._set_calibration("failed", success=False, detail=str(exc))
                            else:
                                self._set_calibration(
                                    "succeeded" if success else "failed",
                                    success=success,
                                    detail=None if success else "Device rejected calibration.",
                                )
                            calibration_task = None

                        now = time.monotonic()
                        stale_streams = []
                        if now - last_gaze_at > _STREAM_STALE_SECONDS:
                            stale_streams.append("gaze")
                        if (
                            self.scene_camera_enabled
                            and now - last_scene_at > _STREAM_STALE_SECONDS
                        ):
                            stale_streams.append("scene")
                        if stale_streams:
                            raise TimeoutError(
                                "No %s RTP received for %.1f seconds."
                                % ("/".join(stale_streams), _STREAM_STALE_SECONDS)
                            )
                finally:
                    tasks = [gaze_task]
                    if scene_task is not None:
                        tasks.append(scene_task)
                    if calibration_task is not None:
                        tasks.append(calibration_task)
                        self._set_calibration(
                            "failed", success=False, detail="Calibration interrupted."
                        )
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

    def _store_scene_frame(self, frame: Any, device_seconds: object) -> None:
        now = time.monotonic()
        with self._frame_lock:
            mapping_due = (
                now - self._last_mapping_processed_monotonic >= _MAPPING_INTERVAL_SECONDS
            )
            jpeg_due = now - self._last_frame_encoded_monotonic >= _JPEG_INTERVAL_SECONDS
            if not mapping_due and not jpeg_due:
                return
            if mapping_due:
                self._last_mapping_processed_monotonic = now
            if jpeg_due:
                self._last_frame_encoded_monotonic = now
        try:
            from PIL import ImageDraw

            image = frame.to_image()
            image.thumbnail((1280, 720))
            with self._condition:
                trajectory = self.extractor.recent_valid_points(now_monotonic=now)
                if trajectory:
                    gaze_x, gaze_y = trajectory[-1][0], trajectory[-1][1]
                else:
                    gaze_x, gaze_y = None, None
            mapping = (
                self.screen_mapper.process_frame(image, trajectory, now_monotonic=now)
                if mapping_due
                else self.screen_mapper.snapshot()
            )
            if not jpeg_due:
                return
            quad = mapping.get("fiducial_quad_scene") or []
            if len(quad) == 4:
                draw = ImageDraw.Draw(image)
                points = [
                    (
                        round(point["x_normalized"] * image.width),
                        round(point["y_normalized"] * image.height),
                    )
                    for point in quad
                ]
                draw.line([*points, points[0]], fill=(0, 210, 190), width=4)
            if len(trajectory) >= 2:
                draw = ImageDraw.Draw(image)
                pixels = [
                    (round(x * image.width), round(y * image.height))
                    for x, y, _age_ms in trajectory
                ]
                draw.line(pixels, fill=(225, 45, 50), width=4, joint="curve")
                for point_x, point_y in pixels[:: max(1, len(pixels) // 24)]:
                    draw.ellipse(
                        (point_x - 3, point_y - 3, point_x + 3, point_y + 3),
                        fill=(255, 220, 40),
                    )
            if gaze_x is not None and gaze_y is not None:
                center_x = round(gaze_x * image.width)
                center_y = round(gaze_y * image.height)
                radius = max(12, round(min(image.width, image.height) * 0.025))
                draw = ImageDraw.Draw(image)
                draw.ellipse(
                    (
                        center_x - radius,
                        center_y - radius,
                        center_x + radius,
                        center_y + radius,
                    ),
                    outline=(255, 255, 255),
                    width=8,
                )
                draw.ellipse(
                    (
                        center_x - radius,
                        center_y - radius,
                        center_x + radius,
                        center_y + radius,
                    ),
                    outline=(220, 24, 36),
                    width=4,
                )
                draw.line(
                    (center_x - radius, center_y, center_x + radius, center_y),
                    fill=(220, 24, 36),
                    width=3,
                )
                draw.line(
                    (center_x, center_y - radius, center_x, center_y + radius),
                    fill=(220, 24, 36),
                    width=3,
                )
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=82, optimize=True)
            captured = SceneFrame(
                jpeg=output.getvalue(),
                timestamp=Timestamp.from_monotonic_ns(
                    int(now * 1_000_000_000), _finite_float(device_seconds)
                ),
                width=int(image.width),
                height=int(image.height),
                gaze_x=gaze_x,
                gaze_y=gaze_y,
                gaze_trajectory=trajectory,
                trajectory_window_ms=self.extractor.window_seconds * 1000.0,
                screen_mapping=mapping,
            )
        except Exception as exc:
            LOGGER.warning("Unable to encode Tobii scene frame: %s", exc)
            return
        with self._frame_lock:
            self._latest_scene_frame = captured


def _drain_async_queue(queue: object) -> int:
    """Discard already-accounted-for RTCP packets before g3pylib's queue fills."""
    get_nowait = getattr(queue, "get_nowait", None)
    if not callable(get_nowait):
        return 0
    drained = 0
    while True:
        try:
            get_nowait()
        except asyncio.QueueEmpty:
            return drained
        drained += 1


def _rtsp_url_for_transport(url: Optional[str], transport: str) -> Optional[str]:
    if url is None:
        return None
    parsed = urlsplit(url)
    if parsed.scheme not in {"rtsp", "rtspt"}:
        raise ValueError("Unexpected Tobii RTSP URL scheme: %s" % parsed.scheme)
    scheme = "rtspt" if transport == "tcp" else "rtsp"
    return urlunsplit(parsed._replace(scheme=scheme))


def _connector_with_rtsp_transport(
    connector_type: Any,
    connector: Any,
    transport: str,
) -> Any:
    """Preserve g3pylib discovery while selecting UDP or interleaved TCP RTP."""

    async def urls() -> tuple[str, Optional[str], Optional[str]]:
        websocket_url, rtsp_url, http_url = await connector.url_generator
        return (
            websocket_url,
            _rtsp_url_for_transport(rtsp_url, transport),
            http_url,
        )

    return connector_type(urls())


def _extract_gaze2d(payload: object) -> Tuple[Optional[float], Optional[float]]:
    if not isinstance(payload, Mapping):
        return None, None
    value = payload.get("gaze2d")
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None, None
    x, y = _finite_float(value[0]), _finite_float(value[1])
    if x is None or y is None or not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return None, None
    return x, y


def _finite_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _sample_span_seconds(samples: Sequence[_GazeSample]) -> float:
    if len(samples) < 2:
        return 0.0
    return max(0.0, samples[-1].received_monotonic - samples[0].received_monotonic)


def _current_fixation_duration_ms(
    samples: Sequence[_GazeSample], *, dispersion: float
) -> Optional[float]:
    if not samples:
        return None
    cluster: List[_GazeSample] = [samples[-1]]
    for sample in reversed(samples[:-1]):
        candidate = [sample, *cluster]
        xs = [float(item.x) for item in candidate if item.x is not None]
        ys = [float(item.y) for item in candidate if item.y is not None]
        if max(xs) - min(xs) > dispersion or max(ys) - min(ys) > dispersion:
            break
        cluster.insert(0, sample)
    return max(
        0.0,
        (cluster[-1].received_monotonic - cluster[0].received_monotonic) * 1000.0,
    )


def _fixation_rate_per_minute(
    samples: Sequence[_GazeSample],
    *,
    dispersion: float,
    min_duration_ms: float,
    duration_seconds: float,
) -> Optional[float]:
    if len(samples) < 2 or duration_seconds <= 0:
        return None
    fixation_count = 0
    segment: List[_GazeSample] = [samples[0]]
    for sample in samples[1:]:
        candidate = [*segment, sample]
        xs = [float(item.x) for item in candidate if item.x is not None]
        ys = [float(item.y) for item in candidate if item.y is not None]
        if max(xs) - min(xs) <= dispersion and max(ys) - min(ys) <= dispersion:
            segment.append(sample)
            continue
        if _sample_span_seconds(segment) * 1000.0 >= min_duration_ms:
            fixation_count += 1
        segment = [sample]
    if _sample_span_seconds(segment) * 1000.0 >= min_duration_ms:
        fixation_count += 1
    return fixation_count * 60.0 / duration_seconds


def _saccade_rate_per_second(
    samples: Sequence[_GazeSample],
    *,
    velocity_threshold: float,
    duration_seconds: float,
) -> Optional[float]:
    if len(samples) < 2 or duration_seconds <= 0:
        return None
    count = 0
    in_saccade = False
    for before, after in zip(samples, samples[1:]):
        delta_t = after.received_monotonic - before.received_monotonic
        if (
            delta_t <= 0
            or before.x is None
            or before.y is None
            or after.x is None
            or after.y is None
        ):
            continue
        velocity = math.hypot(after.x - before.x, after.y - before.y) / delta_t
        active = velocity >= velocity_threshold
        if active and not in_saccade:
            count += 1
        in_saccade = active
    return count / duration_seconds


def _normalized_spatial_entropy(samples: Iterable[_GazeSample], bins: int = 4) -> Optional[float]:
    counts = [0] * (bins * bins)
    total = 0
    for sample in samples:
        if sample.x is None or sample.y is None:
            continue
        x_bin = min(bins - 1, int(sample.x * bins))
        y_bin = min(bins - 1, int(sample.y * bins))
        counts[y_bin * bins + x_bin] += 1
        total += 1
    if total == 0:
        return None
    entropy = -sum(
        (count / total) * math.log(count / total) for count in counts if count
    )
    return entropy / math.log(bins * bins)


def _mapped_gaze_samples(value: object) -> List[_GazeSample]:
    if not isinstance(value, Sequence):
        return []
    now = time.monotonic()
    samples: List[_GazeSample] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        x = _finite_float(item.get("x_normalized"))
        y = _finite_float(item.get("y_normalized"))
        age_ms = _finite_float(item.get("age_ms"))
        if x is None or y is None:
            continue
        samples.append(
            _GazeSample(
                received_monotonic=now - max(0.0, age_ms or 0.0) / 1000.0,
                device_seconds=None,
                x=x,
                y=y,
            )
        )
    samples.sort(key=lambda sample: sample.received_monotonic)
    return samples


def _scene_region(x: float, y: float) -> str:
    horizontal = "left" if x < 1.0 / 3.0 else "right" if x > 2.0 / 3.0 else "center"
    vertical = "top" if y < 1.0 / 3.0 else "bottom" if y > 2.0 / 3.0 else "middle"
    if horizontal == "center" and vertical == "middle":
        return "scene_center"
    return "scene_%s_%s" % (vertical, horizontal)
