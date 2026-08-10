"""Background workers that connect acquisition sources to the application."""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from .acquisition import EEGSource
from .application import ExperimentApplication
from .eeg import OnlineEEGProcessor
from .gaze import GazeProvider
from .storage import JsonlRecorder, RawEEGRecorder

LOGGER = logging.getLogger(__name__)


class EEGAcquisitionWorker:
    def __init__(
        self,
        source: EEGSource,
        application: ExperimentApplication,
        *,
        processor: Optional[OnlineEEGProcessor] = None,
        raw_recorder: Optional[RawEEGRecorder] = None,
        idle_seconds: float = 0.02,
    ) -> None:
        self.source = source
        self.application = application
        self.processor = processor or OnlineEEGProcessor()
        self.raw_recorder = raw_recorder
        self.idle_seconds = idle_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._processor_session_id: Optional[str] = None
        self.last_error: Optional[Exception] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop.clear()
        self.last_error = None
        self.source.start()
        self._thread = threading.Thread(target=self._run, daemon=True, name="eeg-acquisition")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self.source.stop()

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                chunk = self.source.read()
                if chunk is None:
                    time.sleep(self.idle_seconds)
                    continue
                context = self.application.recording_context()
                self._reset_processor_for_session(str(context["session_id"]))
                if self.raw_recorder is not None:
                    self.raw_recorder.append(chunk, **context)
                features = self.processor.append(
                    chunk.samples,
                    chunk.channel_names,
                    sampling_rate_hz=chunk.sampling_rate_hz,
                    device_seconds=chunk.timestamp.device_seconds,
                    host_monotonic_ns=chunk.timestamp.host_monotonic_ns,
                )
                if features is not None:
                    features.source = chunk.source
                    self.application.update_eeg(features)
        except Exception as exc:  # worker exposes the failure to its owner
            self.last_error = exc
            LOGGER.exception("EEG acquisition worker stopped: %s", exc)
        finally:
            if self.raw_recorder is not None:
                self.raw_recorder.close()
            self.source.stop()

    def _reset_processor_for_session(self, session_id: str) -> None:
        if session_id == self._processor_session_id:
            return
        self.processor.reset()
        self._processor_session_id = session_id


class GazeAcquisitionWorker:
    """Poll any gaze provider without coupling it to Policy or HTTP."""

    def __init__(
        self,
        provider: GazeProvider,
        application: ExperimentApplication,
        *,
        session_id: str,
        raw_recorder: Optional[JsonlRecorder] = None,
        poll_seconds: float = 0.01,
    ) -> None:
        self.provider = provider
        self.application = application
        self.session_id = session_id
        self.raw_recorder = raw_recorder
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_error: Optional[Exception] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop.clear()
        self.last_error = None
        self.provider.start(self.session_id)
        self._thread = threading.Thread(target=self._run, daemon=True, name="gaze-acquisition")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self.provider.stop()

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                features = self.provider.read()
                self._persist_raw_samples()
                if features is None:
                    return
                self.application.update_gaze(features)
                time.sleep(self.poll_seconds)
        except Exception as exc:
            self.last_error = exc
            LOGGER.exception("Gaze acquisition worker stopped")
        finally:
            self._persist_raw_samples()
            self.provider.stop()

    def _persist_raw_samples(self) -> None:
        if self.raw_recorder is None:
            return
        drain = getattr(self.provider, "drain_raw_samples", None)
        if not callable(drain):
            return
        samples = drain()
        if not samples:
            return
        context = self.application.recording_context()
        self.raw_recorder.append_many(
            {
                "schema_version": "1.0",
                "event_type": "raw_gaze_sample",
                **context,
                "source": "tobii_g3",
                **sample,
            }
            for sample in samples
        )
