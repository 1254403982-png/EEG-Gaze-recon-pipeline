"""Condition-scoped storage activated only by a real experiment session."""

from __future__ import annotations

import copy
import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, Iterable, Optional

from ..clock import Timestamp
from .eeg_raw import RawEEGRecorder

_INVALID_PATH = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_INACTIVE_SESSIONS = {"", "development", "not_started"}
_RUN_STAMP = re.compile(r"^\d{8}_\d{6}_\d{6}$")


class ExperimentRunManager:
    """Own one single-condition experiment directory and its subject history."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self._lock = threading.RLock()
        self._subject_id: Optional[str] = None
        self._stamp: Optional[str] = None
        self._started: Optional[Timestamp] = None
        self._condition: Optional[int] = None
        self._directories: Dict[int, Path] = {}
        self._flush_callbacks: list[Callable[[], object]] = []

    @property
    def active(self) -> bool:
        with self._lock:
            return self._subject_id is not None and self._stamp is not None

    @property
    def current_condition(self) -> Optional[int]:
        with self._lock:
            return self._condition

    @property
    def current_stamp(self) -> Optional[str]:
        with self._lock:
            return self._stamp

    def register_flush_callback(self, callback: Callable[[], object]) -> None:
        with self._lock:
            self._flush_callbacks.append(callback)

    def start_session(
        self,
        subject_id: str,
        condition: int,
        *,
        resume_stamp: Optional[str] = None,
    ) -> Optional[Path]:
        clean = str(subject_id).strip()
        if clean.lower() in _INACTIVE_SESSIONS:
            return None
        _validate_condition(condition)
        self._flush_recorders()
        with self._lock:
            self._subject_id = clean
            requested_stamp = str(resume_stamp or "").strip()
            can_resume = bool(_RUN_STAMP.fullmatch(requested_stamp))
            candidate = (
                self.root / f"{_safe_component(clean)}_condition_{int(condition)}_{requested_stamp}"
                if can_resume
                else None
            )
            if candidate is not None and candidate.is_dir():
                self._stamp = requested_stamp
            else:
                self._stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
            self._started = Timestamp.now()
            self._condition = int(condition)
            self._directories = {int(condition): candidate} if candidate is not None and candidate.is_dir() else {}
            return self._ensure_condition_locked(int(condition))

    def set_condition(self, condition: int) -> Optional[Path]:
        _validate_condition(condition)
        if not self.active:
            return None
        self._flush_recorders()
        with self._lock:
            self._condition = int(condition)
            return self._ensure_condition_locked(int(condition))

    def end_session(self) -> None:
        self._flush_recorders()
        with self._lock:
            self._subject_id = None
            self._stamp = None
            self._started = None
            self._condition = None
            self._directories = {}

    def condition_directory(self, condition: Optional[int] = None) -> Optional[Path]:
        with self._lock:
            if self._subject_id is None or self._stamp is None:
                return None
            selected = self._condition if condition is None else int(condition)
            if selected is None:
                return None
            _validate_condition(selected)
            return self._ensure_condition_locked(selected)

    def append_jsonl(
        self,
        relative_path: str,
        payload: Dict[str, Any],
        *,
        condition: Optional[int] = None,
    ) -> Optional[Path]:
        with self._lock:
            directory = self.condition_directory(condition or _payload_condition(payload))
            if directory is None:
                return None
            destination = directory / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
            with destination.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.write("\n")
            return destination

    def save_experiment(self, payload: Dict[str, Any]) -> Optional[Path]:
        with self._lock:
            if not self.active:
                return None
            destinations: list[Path] = []
            conditions = sorted(self._directories)
            for condition in conditions:
                directory = self._ensure_condition_locked(condition)
                scoped = _condition_experiment_payload(payload, condition)
                destination = directory / "experiment.json"
                temporary = destination.with_suffix(".json.tmp")
                temporary.write_text(
                    json.dumps(scoped, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
                temporary.replace(destination)
                destinations.append(destination)
            return destinations[0] if destinations else None

    def used_question_ids(self, subject_id: str) -> list[str]:
        """Return questions previously exposed to this subject on this machine."""

        clean = str(subject_id).strip()
        if not clean:
            raise ValueError("subject_id must not be empty.")
        with self._lock:
            history = self._read_question_history_locked()
            entries = history.get(clean.casefold(), [])
            question_ids = (
                str(entry.get("question_id", ""))
                for entry in entries
                if entry.get("question_id")
            )
            return list(dict.fromkeys(question_ids))

    def reserve_questions(
        self, subject_id: str, question_ids: Iterable[str], condition: int
    ) -> list[str]:
        """Atomically record questions as used as soon as they are presented."""

        clean = str(subject_id).strip()
        if not clean:
            raise ValueError("subject_id must not be empty.")
        _validate_condition(condition)
        if isinstance(question_ids, (str, bytes)):
            raise ValueError("question_ids must be an array.")
        requested = list(
            dict.fromkeys(str(value).strip() for value in question_ids if str(value).strip())
        )
        if not requested:
            return []
        with self._lock:
            history = self._read_question_history_locked()
            key = clean.casefold()
            entries = history.setdefault(key, [])
            used = {str(entry.get("question_id", "")) for entry in entries}
            timestamp = Timestamp.now().to_dict()
            for question_id in requested:
                if question_id not in used:
                    entries.append(
                        {
                            "subject_id": clean,
                            "question_id": question_id,
                            "condition": int(condition),
                            "timestamp": timestamp,
                        }
                    )
                    used.add(question_id)
            self._write_question_history_locked(history)
            return requested

    def _read_question_history_locked(self) -> Dict[str, list[Dict[str, Any]]]:
        path = self.root / "_subject_question_history.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_question_history_locked(self, payload: Dict[str, list[Dict[str, Any]]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "_subject_question_history.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _ensure_condition_locked(self, condition: int) -> Path:
        existing = self._directories.get(condition)
        if existing is not None:
            return existing
        assert self._subject_id is not None and self._stamp is not None
        subject = _safe_component(self._subject_id)
        directory = self.root / f"{subject}_condition_{condition}_{self._stamp}"
        directory.mkdir(parents=True, exist_ok=False)
        started = self._started or Timestamp.now()
        metadata = {
            "schema_version": "2.0",
            "subject_id": self._subject_id,
            "condition": condition,
            "experiment_stamp": self._stamp,
            "recording_begins_at_phase": "rest_calibration",
            "clock": {
                "primary": "host_monotonic_ns",
                "audit": "utc",
                "device_timestamps": "retained_but_not_used_for_online_alignment",
            },
            "experiment_started": started.to_dict(),
        }
        (directory / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._directories[condition] = directory
        return directory

    def _flush_recorders(self) -> None:
        with self._lock:
            callbacks = tuple(self._flush_callbacks)
        for callback in callbacks:
            callback()


class RunEventRecorder:
    """Route dense features away from sparse experimental events."""

    _PATHS: ClassVar[Dict[str, str]] = {
        "eeg_features": "eeg/features.jsonl",
        "gaze_features": "gaze/features.jsonl",
    }
    _MIN_INTERVAL_NS: ClassVar[Dict[str, int]] = {
        "eeg_features": 200_000_000,
        "gaze_features": 200_000_000,
    }

    def __init__(self, manager: ExperimentRunManager) -> None:
        self.manager = manager
        self._lock = threading.Lock()
        self._last_written: Dict[tuple[int, str], int] = {}

    def append(self, payload: Dict[str, Any]) -> None:
        event_type = str(payload.get("event_type", "event"))
        condition = _payload_condition(payload)
        timestamp = payload.get("timestamp", {})
        host_ns = int(timestamp.get("host_monotonic_ns", 0)) if isinstance(timestamp, dict) else 0
        minimum = self._MIN_INTERVAL_NS.get(event_type, 0)
        if minimum and condition is not None and host_ns:
            key = (condition, event_type)
            with self._lock:
                if host_ns - self._last_written.get(key, 0) < minimum:
                    return
                self._last_written[key] = host_ns
        self.manager.append_jsonl(
            self._PATHS.get(event_type, "events.jsonl"), payload, condition=condition
        )


class RunPolicyRecorder:
    """Record policy changes immediately and unchanged state at most once per second."""

    def __init__(self, manager: ExperimentRunManager) -> None:
        self.manager = manager
        self._lock = threading.Lock()
        self._last_signature: Dict[int, str] = {}
        self._last_written_ns: Dict[int, int] = {}

    def append(self, payload: Dict[str, Any]) -> None:
        condition = _payload_condition(payload)
        if condition is None:
            return
        timestamp = payload.get("timestamp", {})
        host_ns = int(timestamp.get("host_monotonic_ns", 0)) if isinstance(timestamp, dict) else 0
        signature_payload = {
            key: value for key, value in payload.items() if key not in {"policy_id", "timestamp"}
        }
        signature = json.dumps(signature_payload, sort_keys=True, default=str)
        with self._lock:
            unchanged = signature == self._last_signature.get(condition)
            recent = host_ns - self._last_written_ns.get(condition, 0) < 1_000_000_000
            if unchanged and recent:
                return
            self._last_signature[condition] = signature
            self._last_written_ns[condition] = host_ns
        self.manager.append_jsonl("policy/decisions.jsonl", payload, condition=condition)


class RunJsonlRecorder:
    def __init__(self, manager: ExperimentRunManager, relative_path: str) -> None:
        self.manager = manager
        self.relative_path = relative_path

    def append(self, payload: Dict[str, Any]) -> None:
        self.manager.append_jsonl(self.relative_path, payload)

    def append_many(self, payloads: Iterable[Dict[str, Any]]) -> None:
        for payload in payloads:
            self.append(payload)


class RunRawEEGRecorder:
    def __init__(self, manager: ExperimentRunManager, *, chunk_seconds: float = 10.0) -> None:
        self.manager = manager
        self.chunk_seconds = float(chunk_seconds)
        self._lock = threading.Lock()
        self._recorders: Dict[Path, RawEEGRecorder] = {}
        self._active: Optional[RawEEGRecorder] = None
        manager.register_flush_callback(self.flush)

    def append(self, chunk: Any, **context: Any) -> list[Path]:
        condition = int(context["condition"])
        directory = self.manager.condition_directory(condition)
        if directory is None:
            return []
        eeg_directory = directory / "eeg"
        with self._lock:
            recorder = self._recorders.get(eeg_directory)
            if recorder is None:
                recorder = RawEEGRecorder(
                    eeg_directory,
                    chunk_seconds=self.chunk_seconds,
                    ignored_session_ids=(),
                    flat_session=True,
                )
                self._recorders[eeg_directory] = recorder
            if self._active is not None and self._active is not recorder:
                self._active.flush()
            self._active = recorder
            return recorder.append(chunk, **context)

    def flush(self) -> list[Path]:
        with self._lock:
            return self._active.flush() if self._active is not None else []

    def close(self) -> list[Path]:
        with self._lock:
            completed: list[Path] = []
            for recorder in self._recorders.values():
                completed.extend(recorder.close())
            self._active = None
            return completed


class RunDocumentStore:
    def __init__(self, manager: ExperimentRunManager) -> None:
        self.manager = manager

    def save(self, payload: Dict[str, Any]) -> Path:
        destination = self.manager.save_experiment(payload)
        if destination is None:
            raise RuntimeError("No active experiment run.")
        return destination


def _condition_experiment_payload(payload: Dict[str, Any], condition: int) -> Dict[str, Any]:
    scoped = copy.deepcopy(payload)
    experiment = scoped.get("experimentData")
    if isinstance(experiment, dict):
        trials = experiment.get("trials")
        if isinstance(trials, list):
            experiment["trials"] = [
                trial
                for trial in trials
                if isinstance(trial, dict) and trial.get("condition") == condition
            ]
        experiment["condition_scope"] = condition
    scoped["condition"] = condition
    return scoped


def _payload_condition(payload: Dict[str, Any]) -> Optional[int]:
    try:
        value = int(payload.get("condition"))
    except (TypeError, ValueError):
        return None
    return value if value in {1, 2, 3} else None


def _safe_component(value: str) -> str:
    cleaned = _INVALID_PATH.sub("_", value).strip(" .")
    return (cleaned or "unknown")[:80]


def _validate_condition(condition: int) -> None:
    if int(condition) not in {1, 2, 3}:
        raise ValueError("condition must be 1, 2, or 3.")
