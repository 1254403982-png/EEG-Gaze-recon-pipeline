"""Small standard-library HTTP API around the application service."""

from __future__ import annotations

import base64
import json
import mimetypes
import socket
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

from ..application import ExperimentApplication
from ..clock import Timestamp
from ..gaze.screen_mapping import marker_png
from ..gaze.tobii import SceneFrame
from ..models import EEGFeatures, EyeFeatures, GazeFeatures, SignalStatus, UIContext
from ..storage import ExperimentRunManager, JsonDocumentStore
from .llm_proxy import LLMProxy


class _ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class ExperimentHTTPServer:
    def __init__(
        self,
        application: ExperimentApplication,
        *,
        host: str = "127.0.0.1",
        port: int = 8810,
        static_root: Optional[Path] = None,
        document_store: Optional[JsonDocumentStore] = None,
        llm_proxy: Optional[LLMProxy] = None,
        scene_frame_supplier: Optional[Callable[[], Optional[SceneFrame]]] = None,
        screen_mapping_supplier: Optional[Callable[[], Dict[str, Any]]] = None,
        screen_layout_updater: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        tobii_calibration_supplier: Optional[Callable[[], Dict[str, Any]]] = None,
        tobii_calibration_starter: Optional[Callable[[], Dict[str, Any]]] = None,
        question_registry: Optional[ExperimentRunManager] = None,
    ) -> None:
        self.application = application
        self.static_root = (
            static_root.expanduser().resolve()
            if static_root is not None
            else (Path(__file__).resolve().parents[1] / "web").resolve()
        )
        self.document_store = document_store
        self.llm_proxy = llm_proxy
        self.scene_frame_supplier = scene_frame_supplier
        self.screen_mapping_supplier = screen_mapping_supplier
        self.screen_layout_updater = screen_layout_updater
        self.tobii_calibration_supplier = tobii_calibration_supplier
        self.tobii_calibration_starter = tobii_calibration_starter
        self.question_registry = question_registry
        self._server = _ExclusiveThreadingHTTPServer((host, port), self._handler())
        self._thread: Optional[threading.Thread] = None

    @property
    def address(self) -> tuple:
        return self._server.server_address

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _handler(self) -> type:
        app = self.application
        static_root = self.static_root
        document_store = self.document_store
        llm_proxy = self.llm_proxy
        scene_frame_supplier = self.scene_frame_supplier
        screen_mapping_supplier = self.screen_mapping_supplier
        screen_layout_updater = self.screen_layout_updater
        tobii_calibration_supplier = self.tobii_calibration_supplier
        tobii_calibration_starter = self.tobii_calibration_starter
        question_registry = self.question_registry

        class Handler(BaseHTTPRequestHandler):
            def do_OPTIONS(self) -> None:
                self.send_response(HTTPStatus.NO_CONTENT)
                self._cors_headers()
                self.end_headers()

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                route = parsed.path
                if route == "/":
                    self._serve_static("index.html")
                elif route in {"/experiment", "/experiment/"}:
                    self._redirect("/ui/experiment.html")
                elif route in {"/monitor", "/monitor/"}:
                    self._redirect("/ui/monitor.html")
                elif route.startswith("/ui/"):
                    self._serve_static(unquote(route[len("/ui/") :]))
                elif route == "/api/health":
                    self._send(HTTPStatus.OK, _health_payload(app))
                elif route == "/api/state":
                    self._send(HTTPStatus.OK, app.snapshot())
                elif route == "/api/policy":
                    self._send(HTTPStatus.OK, _compat_policy_payload(app))
                elif route == "/api/condition":
                    state = app.synchronizer.snapshot()
                    self._send(
                        HTTPStatus.OK,
                        {
                            "condition": state.condition,
                            "policy_enabled": state.condition >= 2,
                            "sources": {
                                "eeg": state.condition == 3,
                                "gaze": state.condition in {2, 3},
                            },
                        },
                    )
                elif route == "/api/questions/used":
                    if question_registry is None:
                        self._send(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            {"ok": False, "error": "question_registry_not_configured"},
                        )
                    else:
                        subject_id = parse_qs(parsed.query).get("subject_id", [""])[0]
                        self._send(
                            HTTPStatus.OK,
                            {
                                "ok": True,
                                "subject_id": subject_id,
                                "question_ids": question_registry.used_question_ids(subject_id),
                            },
                        )
                elif route == "/api/attention":
                    self._send(HTTPStatus.OK, _attention_payload(app))
                elif route == "/api/gaze/frame":
                    frame = scene_frame_supplier() if scene_frame_supplier is not None else None
                    frame_age_ms = frame.timestamp.age_ms() if frame is not None else None
                    if frame is None or frame_age_ms is None or frame_age_ms > 3000.0:
                        self._send(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            {
                                "ok": False,
                                "error": "scene_frame_unavailable",
                                "age_ms": frame_age_ms,
                            },
                        )
                    else:
                        self._send(
                            HTTPStatus.OK,
                            {
                                "ok": True,
                                "media_type": "image/jpeg",
                                "data_url": "data:image/jpeg;base64,"
                                + base64.b64encode(frame.jpeg).decode("ascii"),
                                "width": frame.width,
                                "height": frame.height,
                                "gaze": {
                                    "x_normalized": frame.gaze_x,
                                    "y_normalized": frame.gaze_y,
                                },
                                "trajectory": [
                                    {
                                        "x_normalized": x,
                                        "y_normalized": y,
                                        "age_ms": age_ms,
                                    }
                                    for x, y, age_ms in frame.gaze_trajectory
                                ],
                                "trajectory_window_ms": frame.trajectory_window_ms,
                                "screen_mapping": frame.screen_mapping,
                                "timestamp": frame.timestamp.to_dict(),
                                "age_ms": frame_age_ms,
                            },
                        )
                elif route == "/api/screen/mapping":
                    mapping = (
                        screen_mapping_supplier()
                        if screen_mapping_supplier is not None
                        else {"valid": False, "status": "tobii_not_configured"}
                    )
                    self._send(HTTPStatus.OK, {"ok": True, "mapping": mapping})
                elif route == "/api/tobii/calibration":
                    calibration = (
                        tobii_calibration_supplier()
                        if tobii_calibration_supplier is not None
                        else {"status": "unavailable", "connected": False}
                    )
                    self._send(HTTPStatus.OK, {"ok": True, "calibration": calibration})
                elif route == "/api/screen/marker":
                    try:
                        marker_id = int(parse_qs(parsed.query).get("id", [""])[0])
                        raw = marker_png(marker_id)
                    except (ImportError, RuntimeError, TypeError, ValueError) as exc:
                        self._send(
                            HTTPStatus.BAD_REQUEST,
                            {"ok": False, "error": "marker_unavailable", "detail": str(exc)},
                        )
                    else:
                        self._send_content(HTTPStatus.OK.value, raw, "image/png")
                else:
                    self._send(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

            def do_POST(self) -> None:
                route = urlparse(self.path).path
                try:
                    payload = self._read_json()
                    if route == "/v1/chat/completions":
                        if llm_proxy is None:
                            self._send(
                                HTTPStatus.SERVICE_UNAVAILABLE,
                                {"error": {"message": "LLM proxy is not configured."}},
                            )
                            return
                        request_id = str(self.headers.get("X-Request-ID", ""))[:100]
                        app.record_interaction(
                            "llm_proxy_request_received",
                            {
                                "request_id": request_id,
                                "model": str(payload.get("model", ""))[:100],
                                "message_count": len(payload.get("messages", [])),
                                "includes_scene_frame": _contains_image(payload),
                            },
                        )
                        status, body = llm_proxy.complete(
                            payload, self.headers.get("Authorization")
                        )
                        app.record_interaction(
                            "llm_proxy_response_received",
                            {
                                "request_id": request_id,
                                "http_status": status,
                                "response_bytes": len(body),
                            },
                        )
                        self._send_bytes(status, body)
                        return
                    if route == "/api/collect":
                        if document_store is None:
                            self._send(
                                HTTPStatus.SERVICE_UNAVAILABLE,
                                {"ok": False, "error": "document_store_not_configured"},
                            )
                            return
                        destination = document_store.save(payload)
                        self._send(
                            HTTPStatus.OK,
                            {"ok": True, "savedTo": str(destination)},
                        )
                        return
                    if route == "/api/questions/reserve":
                        if question_registry is None:
                            self._send(
                                HTTPStatus.SERVICE_UNAVAILABLE,
                                {"ok": False, "error": "question_registry_not_configured"},
                            )
                            return
                        reserved = question_registry.reserve_questions(
                            str(payload.get("subject_id", "")),
                            payload.get("question_ids", []),
                            int(payload.get("condition", 1)),
                        )
                        self._send(HTTPStatus.OK, {"ok": True, "question_ids": reserved})
                        return
                    if route == "/api/screen/layout":
                        if screen_layout_updater is None:
                            self._send(
                                HTTPStatus.SERVICE_UNAVAILABLE,
                                {"ok": False, "error": "screen_mapper_not_configured"},
                            )
                            return
                        result = screen_layout_updater(payload)
                        self._send(HTTPStatus.OK, result)
                        return
                    if route == "/api/tobii/calibration":
                        if tobii_calibration_starter is None:
                            self._send(
                                HTTPStatus.SERVICE_UNAVAILABLE,
                                {"ok": False, "error": "tobii_not_configured"},
                            )
                            return
                        result = tobii_calibration_starter()
                        self._send(HTTPStatus.ACCEPTED, {"ok": True, "calibration": result})
                        return
                    if route == "/api/interaction":
                        action = str(payload.pop("action", ""))
                        result = app.record_interaction(action, payload)
                        self._send(HTTPStatus.OK, {"ok": True, "interaction": result})
                        return
                    if route == "/api/policy":
                        policy_id = payload.get("policy_id")
                        result = app.acknowledge_policy(
                            int(policy_id) if policy_id is not None else None,
                            response=(
                                str(payload.get("response"))
                                if payload.get("response") is not None
                                else None
                            ),
                        )
                        self._send(HTTPStatus.OK, result)
                        return
                    if route == "/api/session/start":
                        result = app.start_session(
                            str(payload["session_id"]),
                            int(payload.get("condition", 1)),
                            resume_stamp=(
                                str(payload["resume_stamp"])
                                if payload.get("resume_stamp") is not None
                                else None
                            ),
                        )
                    elif route == "/api/session/end":
                        result = app.end_session()
                    elif route == "/api/condition":
                        result = app.set_condition(int(payload["condition"])).to_dict()
                    elif route == "/api/eeg/features":
                        result = app.update_eeg(_parse_eeg(payload)).to_dict()
                    elif route == "/api/gaze":
                        result = app.update_gaze(_parse_gaze(payload)).to_dict()
                    elif route == "/api/ui/context":
                        context = UIContext(
                            phase=str(payload.get("phase", "idle")),
                            slide_id=_optional_str(payload.get("slide_id")),
                            seconds_in_trial=_optional_float(payload.get("seconds_in_trial")),
                            metadata=_dict(payload.get("metadata")),
                        )
                        result = app.update_ui(
                            context, trial_id=_optional_str(payload.get("trial_id"))
                        ).to_dict()
                    elif route == "/api/policy/evaluate":
                        result = app.evaluate_policy().to_dict()
                    else:
                        self._send(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
                        return
                except (KeyError, RuntimeError, TypeError, ValueError) as exc:
                    self._send(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": "invalid_request", "detail": str(exc)},
                    )
                    return
                self._send(HTTPStatus.OK, result)

            def _serve_static(self, relative_path: str) -> None:
                candidate = (static_root / relative_path).resolve()
                if candidate != static_root and static_root not in candidate.parents:
                    self._send(HTTPStatus.FORBIDDEN, {"ok": False, "error": "forbidden"})
                    return
                if not candidate.is_file():
                    self._send(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
                    return
                raw = candidate.read_bytes()
                content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
                if content_type.startswith("text/") or content_type in {
                    "application/javascript",
                    "application/json",
                }:
                    content_type += "; charset=utf-8"
                self.send_response(HTTPStatus.OK.value)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(raw)

            def _redirect(self, location: str) -> None:
                self.send_response(HTTPStatus.FOUND.value)
                self.send_header("Location", location)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _read_json(self) -> Dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(max(0, length))
                value = json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(value, dict):
                    raise ValueError("Request body must be a JSON object.")
                return value

            def _send(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
                raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
                self._send_bytes(status.value, raw)

            def _send_bytes(self, status: int, raw: bytes) -> None:
                self._send_content(status, raw, "application/json; charset=utf-8")

            def _send_content(self, status: int, raw: bytes, content_type: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(raw)))
                self._cors_headers()
                self.end_headers()
                self.wfile.write(raw)

            def _cors_headers(self) -> None:
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header(
                    "Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID"
                )
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

            def log_message(self, format: str, *args: object) -> None:
                return

        return Handler


def _health_payload(app: ExperimentApplication) -> Dict[str, Any]:
    state = app.synchronizer.snapshot()
    eeg_connected = state.eeg.status in {SignalStatus.AVAILABLE, SignalStatus.WARNING}
    gaze_connected = state.gaze.status in {SignalStatus.AVAILABLE, SignalStatus.WARNING}
    return {
        "ok": True,
        "status": "running",
        "session_id": state.session_id,
        "condition": state.condition,
        "eeg_connected": eeg_connected,
        "gaze_connected": gaze_connected,
        "eyetracker_connected": gaze_connected,
        "eeg_quality": state.eeg.quality,
        "gaze_quality": state.gaze.quality,
        "message": (f"EEG {state.eeg.status.value} · Gaze {state.gaze.status.value}"),
    }


def _attention_payload(app: ExperimentApplication) -> Dict[str, Any]:
    state = app.synchronizer.snapshot()
    return {
        "attention_score": state.eeg.cognitive_load,
        "visual_load_index": state.eeg.cognitive_load,
        "attention": state.eeg.attention,
        "quality_status": state.eeg.quality,
        "status": state.eeg.status.value,
        "timestamp": state.eeg.timestamp.to_dict(),
    }


def _compat_policy_payload(app: ExperimentApplication) -> Dict[str, Any]:
    state = app.synchronizer.snapshot()
    payload = app.latest_policy()
    screen_mapping = state.gaze.metadata.get("screen_mapping")
    if not isinstance(screen_mapping, dict):
        screen_mapping = {"valid": False, "status": "screen_mapping_missing"}
    payload.update(
        {
            "cognitive_load": state.eeg.cognitive_load,
            "attention": state.eeg.attention,
            "signal_quality": state.eeg.quality,
            "gaze_region": state.gaze.primary_aoi,
            "eye": state.gaze.eye.to_dict(),
            # Keep the reason for a held Eye policy visible to the browser and
            # monitor; otherwise a missing layout looks identical to a normal
            # low-difficulty Trial.
            "screen_mapping": screen_mapping,
            "seconds_in_trial": state.ui.seconds_in_trial,
            "ui_phase": state.ui.phase,
        }
    )
    return payload


def _parse_eeg(payload: Dict[str, Any]) -> EEGFeatures:
    return EEGFeatures(
        timestamp=Timestamp.now(device_seconds=_optional_float(payload.get("device_timestamp"))),
        status=SignalStatus(str(payload.get("status", "available"))),
        quality=str(payload.get("quality", "pass")),
        cognitive_load=_optional_float(payload.get("cognitive_load")),
        attention=_optional_float(payload.get("attention")),
        alpha_power=_optional_float(payload.get("alpha_power")),
        alpha_peak_hz=_optional_float(payload.get("alpha_peak_hz")),
        alpha_suppression=_optional_float(payload.get("alpha_suppression")),
        frontal_theta_power=_optional_float(payload.get("frontal_theta_power")),
        posterior_alpha_power=_optional_float(payload.get("posterior_alpha_power")),
        workload_index=_optional_float(payload.get("workload_index")),
        bad_channels=[str(value) for value in payload.get("bad_channels", [])],
        source=str(payload.get("source", "brainco")),
        metadata=_dict(payload.get("metadata")),
    )


def _parse_gaze(payload: Dict[str, Any]) -> GazeFeatures:
    eye = _dict(payload.get("eye"))
    return GazeFeatures(
        timestamp=Timestamp.now(device_seconds=_optional_float(payload.get("device_timestamp"))),
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
        source=str(payload.get("source", "gaze")),
        metadata=_dict(payload.get("metadata")),
        eye=EyeFeatures(
            aoi_dwell_time=_optional_float(eye.get("aoi_dwell_time")),
            fixation_count=_optional_int(eye.get("fixation_count")),
            mean_fixation_duration=_optional_float(eye.get("mean_fixation_duration")),
            aoi_revisit_count=_optional_int(eye.get("aoi_revisit_count")),
            aoi_revisit_time=_optional_float(eye.get("aoi_revisit_time")),
        ),
    )


def _optional_float(value: object) -> Optional[float]:
    return None if value is None else float(value)


def _optional_str(value: object) -> Optional[str]:
    return None if value is None else str(value)


def _optional_int(value: object) -> Optional[int]:
    return None if value is None else int(value)


def _dict(value: object) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("metadata must be a JSON object.")
    return value


def _contains_image(payload: Dict[str, Any]) -> bool:
    messages = payload.get("messages", [])
    if not isinstance(messages, list):
        return False
    return any(
        isinstance(message, dict)
        and isinstance(message.get("content"), list)
        and any(
            isinstance(part, dict) and part.get("type") == "image_url"
            for part in message["content"]
        )
        for message in messages
    )
