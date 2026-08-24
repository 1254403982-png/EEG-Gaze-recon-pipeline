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
        stall_timeout_seconds: float = 3.0,
        reconnect_delay_seconds: float = 2.0,
    ) -> None:
        if stall_timeout_seconds <= 0:
            raise ValueError("stall_timeout_seconds must be positive.")
        if reconnect_delay_seconds < 0:
            raise ValueError("reconnect_delay_seconds must not be negative.")
        self.source = source
        self.application = application
        self.processor = processor or OnlineEEGProcessor()
        self.raw_recorder = raw_recorder
        self.idle_seconds = idle_seconds
        self.stall_timeout_seconds = float(stall_timeout_seconds)
        self.reconnect_delay_seconds = float(reconnect_delay_seconds)
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
            last_chunk_at = time.monotonic()
            while not self._stop.is_set():
                try:
                    chunk = self.source.read()
                except Exception as exc:
                    self._reconnect_source(exc)
                    last_chunk_at = time.monotonic()
                    continue
                if chunk is None:
                    stalled_for = time.monotonic() - last_chunk_at
                    if stalled_for >= self.stall_timeout_seconds:
                        self._reconnect_source(
                            TimeoutError(
                                "BrainCo produced no EEG samples for "
                                f"{stalled_for:.1f} seconds"
                            )
                        )
                        last_chunk_at = time.monotonic()
                    else:
                        self._stop.wait(self.idle_seconds)
                    continue
                last_chunk_at = time.monotonic()
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

    def _reconnect_source(self, reason: Exception) -> None:
        if self._stop.is_set():
            return
        self.last_error = reason
        LOGGER.warning("EEG stream interrupted; reconnecting: %s", reason)
        if self.raw_recorder is not None:
            self.raw_recorder.flush()
        # Never analyze one window containing samples from both sides of a data gap.
        self.processor.reset()
        try:
            self.source.stop()
        except Exception as exc:
            LOGGER.warning("Failed to stop interrupted EEG source cleanly: %s", exc)
        if self._stop.is_set():
            return
        try:
            self.source.start()
        except Exception as exc:
            self.last_error = exc
            LOGGER.exception(
                "EEG reconnect attempt failed; retrying in %.1f seconds: %s",
                self.reconnect_delay_seconds,
                exc,
            )
            self._stop.wait(self.reconnect_delay_seconds)
            return
        self.last_error = None
        LOGGER.info("EEG stream reconnected; waiting for a fresh analysis window")

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
