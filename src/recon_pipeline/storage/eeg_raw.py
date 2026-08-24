"""Crash-resilient chunked storage for acquisition-level EEG samples."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..acquisition.base import RawEEGChunk

LOGGER = logging.getLogger(__name__)
RAW_EEG_SCHEMA_VERSION = "1.0"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")
_CHUNK_NAME = re.compile(r"^chunk_(\d{6,})\.npz$")


@dataclass
class _SessionFiles:
    directory: Path
    chunks_directory: Path
    manifest_path: Path
    next_chunk_index: int = 0


class RawEEGRecorder:
    """Persist pre-mapping EEG in bounded, atomic NumPy chunks.

    A chunk never crosses a session, trial, condition, UI phase, channel layout,
    sample rate, source, or dtype boundary. This makes every file independently
    attributable even if the process exits before the experiment summary is saved.
    """

    def __init__(
        self,
        root: Path,
        *,
        chunk_seconds: float = 10.0,
        ignored_session_ids: Sequence[str] = ("not_started", "development"),
        flat_session: bool = False,
    ) -> None:
        if chunk_seconds <= 0:
            raise ValueError("chunk_seconds must be positive.")
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.chunk_seconds = float(chunk_seconds)
        self.ignored_session_ids = frozenset(ignored_session_ids)
        self.flat_session = bool(flat_session)
        self._recording_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        self._lock = threading.Lock()
        self._closed = False
        self._sessions: Dict[str, _SessionFiles] = {}
        self._context: Optional[Tuple[str, Optional[str], int, str]] = None
        self._signature: Optional[Tuple[Tuple[str, ...], float, str, str]] = None
        self._sample_parts: List[np.ndarray] = []
        self._timestamp_parts: List[np.ndarray] = []
        self._host_timestamp_parts: List[np.ndarray] = []
        self._source_chunk_offsets: List[int] = []
        self._source_chunk_host_monotonic_ns: List[int] = []
        self._source_chunk_host_utc: List[str] = []
        self._source_chunk_device_seconds: List[float] = []
        self._buffered_samples = 0

    def append(
        self,
        chunk: RawEEGChunk,
        *,
        session_id: str,
        trial_id: Optional[str],
        condition: int,
        phase: str = "unknown",
    ) -> List[Path]:
        """Append one acquisition chunk and return files completed by this call."""

        clean_session_id = str(session_id).strip()
        if not clean_session_id:
            raise ValueError("session_id must not be empty.")
        if condition not in {1, 2, 3}:
            raise ValueError("condition must be 1, 2, or 3.")

        samples = np.asarray(chunk.samples)
        if samples.ndim != 2:
            raise ValueError("EEG samples must be channels-by-samples.")
        if not np.issubdtype(samples.dtype, np.number):
            raise ValueError("EEG samples must use a numeric dtype.")
        sample_count = int(samples.shape[1])
        if sample_count == 0:
            return []

        device_timestamps = self._device_timestamps(chunk, sample_count)
        sample_period_ns = 1_000_000_000.0 / float(chunk.sampling_rate_hz)
        host_timestamps_ns = np.rint(
            int(chunk.timestamp.host_monotonic_ns)
            - np.arange(sample_count - 1, -1, -1, dtype=np.float64) * sample_period_ns
        ).astype(np.int64)
        context = (clean_session_id, trial_id, int(condition), str(phase))
        signature = (
            tuple(str(name) for name in chunk.channel_names),
            float(chunk.sampling_rate_hz),
            str(chunk.source),
            samples.dtype.str,
        )

        with self._lock:
            if self._closed:
                raise RuntimeError("RawEEGRecorder is closed.")

            completed: List[Path] = []
            if clean_session_id in self.ignored_session_ids:
                flushed = self._flush_locked()
                if flushed is not None:
                    completed.append(flushed)
                self._context = None
                self._signature = None
                return completed

            if self._buffered_samples and (
                context != self._context or signature != self._signature
            ):
                flushed = self._flush_locked()
                if flushed is not None:
                    completed.append(flushed)

            self._context = context
            self._signature = signature
            self._ensure_session_locked(clean_session_id, signature)
            target_samples = max(1, round(self.chunk_seconds * signature[1]))

            cursor = 0
            while cursor < sample_count:
                capacity = target_samples - self._buffered_samples
                take = min(capacity, sample_count - cursor)
                stop = cursor + take
                self._source_chunk_offsets.append(self._buffered_samples)
                self._source_chunk_host_monotonic_ns.append(
                    int(chunk.timestamp.host_monotonic_ns)
                )
                self._source_chunk_host_utc.append(str(chunk.timestamp.utc))
                device_seconds = chunk.timestamp.device_seconds
                self._source_chunk_device_seconds.append(
                    float(device_seconds) if device_seconds is not None else float("nan")
                )
                self._sample_parts.append(np.array(samples[:, cursor:stop], copy=True))
                self._timestamp_parts.append(
                    np.array(device_timestamps[cursor:stop], dtype=np.float64, copy=True)
                )
                self._host_timestamp_parts.append(
                    np.array(host_timestamps_ns[cursor:stop], dtype=np.int64, copy=True)
                )
                self._buffered_samples += take
                cursor = stop

                if self._buffered_samples >= target_samples:
                    flushed = self._flush_locked()
                    if flushed is not None:
                        completed.append(flushed)
                    if cursor < sample_count:
                        self._context = context
                        self._signature = signature

            return completed

    def flush(self) -> List[Path]:
        """Synchronously persist the currently buffered partial chunk."""

        with self._lock:
            if self._closed:
                return []
            destination = self._flush_locked()
            return [destination] if destination is not None else []

    def close(self) -> List[Path]:
        """Flush pending samples and make the recorder reject future writes."""

        with self._lock:
            if self._closed:
                return []
            destination = self._flush_locked()
            self._closed = True
            return [destination] if destination is not None else []

    @property
    def session_directories(self) -> Dict[str, Path]:
        with self._lock:
            return {session_id: files.directory for session_id, files in self._sessions.items()}

    @staticmethod
    def _device_timestamps(chunk: RawEEGChunk, sample_count: int) -> np.ndarray:
        if chunk.sample_timestamps is None:
            return np.full(sample_count, np.nan, dtype=np.float64)
        values = np.asarray(chunk.sample_timestamps, dtype=np.float64)
        if values.ndim != 1 or values.shape[0] != sample_count:
            raise ValueError("EEG sample_timestamps must contain one value per sample.")
        return values

    def _ensure_session_locked(
        self,
        session_id: str,
        signature: Tuple[Tuple[str, ...], float, str, str],
    ) -> _SessionFiles:
        existing = self._sessions.get(session_id)
        if existing is not None:
            return existing

        if self.flat_session:
            directory = self.root
        else:
            safe_session = _safe_component(session_id)
            directory = self.root / f"{safe_session}_{self._recording_stamp}"
            suffix = 1
            while directory.exists():
                directory = self.root / f"{safe_session}_{self._recording_stamp}_{suffix:02d}"
                suffix += 1
        chunks_directory = directory / "chunks"
        chunks_directory.mkdir(parents=True, exist_ok=True)
        manifest_path = directory / "manifest.jsonl"
        metadata_path = directory / "metadata.json"
        next_chunk_index = _next_chunk_index(manifest_path, chunks_directory)
        files = _SessionFiles(
            directory=directory,
            chunks_directory=chunks_directory,
            manifest_path=manifest_path,
            next_chunk_index=next_chunk_index,
        )
        self._sessions[session_id] = files

        channels, sampling_rate_hz, source, dtype = signature
        if metadata_path.exists():
            _validate_existing_metadata(metadata_path, session_id)
            LOGGER.info(
                "Raw EEG recording resumed at chunk %s: %s",
                next_chunk_index,
                directory,
            )
        else:
            _write_json_atomic(
                metadata_path,
                {
                    "schema_version": RAW_EEG_SCHEMA_VERSION,
                    "format": "chunked_npz",
                    "session_id": session_id,
                    "recording_started_at": _utc_now_iso(),
                    "sample_values": "device-native acquisition values before mapping or filtering",
                    "host_sample_time_basis": (
                        "reconstructed_backwards_from_chunk_receive_time_and_sampling_rate"
                    ),
                    "initial_channel_names": list(channels),
                    "initial_sampling_rate_hz": sampling_rate_hz,
                    "initial_source": source,
                    "initial_dtype": dtype,
                    "configured_chunk_seconds": self.chunk_seconds,
                    "manifest": "manifest.jsonl",
                    "chunks_directory": "chunks",
                },
            )
            LOGGER.info("Raw EEG recording started: %s", directory)
        return files

    def _flush_locked(self) -> Optional[Path]:
        if self._buffered_samples == 0:
            return None
        if self._context is None or self._signature is None:
            raise RuntimeError("Raw EEG buffer has no recording context.")

        session_id, trial_id, condition, phase = self._context
        channels, sampling_rate_hz, source, dtype = self._signature
        files = self._ensure_session_locked(session_id, self._signature)
        chunk_index = files.next_chunk_index
        filename = f"chunk_{chunk_index:06d}.npz"
        destination = files.chunks_directory / filename
        temporary = destination.with_suffix(".npz.tmp")
        samples = np.concatenate(self._sample_parts, axis=1)
        device_timestamps = np.concatenate(self._timestamp_parts)
        host_timestamps_ns = np.concatenate(self._host_timestamp_parts)

        with temporary.open("wb") as handle:
            np.savez(
                handle,
                schema_version=np.asarray(RAW_EEG_SCHEMA_VERSION),
                samples=samples,
                device_timestamps=device_timestamps,
                host_timestamps_ns=host_timestamps_ns,
                channel_names=np.asarray(channels),
                sampling_rate_hz=np.asarray(sampling_rate_hz, dtype=np.float64),
                session_id=np.asarray(session_id),
                trial_id=np.asarray(trial_id or ""),
                condition=np.asarray(condition, dtype=np.int16),
                phase=np.asarray(phase),
                source=np.asarray(source),
                source_chunk_offsets=np.asarray(self._source_chunk_offsets, dtype=np.int64),
                source_chunk_host_monotonic_ns=np.asarray(
                    self._source_chunk_host_monotonic_ns, dtype=np.int64
                ),
                source_chunk_host_utc=np.asarray(self._source_chunk_host_utc),
                source_chunk_device_seconds=np.asarray(
                    self._source_chunk_device_seconds, dtype=np.float64
                ),
            )
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(destination)

        digest = _sha256(destination)
        finite_timestamps = device_timestamps[np.isfinite(device_timestamps)]
        manifest_entry = {
            "schema_version": RAW_EEG_SCHEMA_VERSION,
            "chunk_index": chunk_index,
            "file": f"chunks/{filename}",
            "sha256": digest,
            "session_id": session_id,
            "trial_id": trial_id,
            "condition": condition,
            "phase": phase,
            "sample_count": int(samples.shape[1]),
            "channel_count": int(samples.shape[0]),
            "channel_names": list(channels),
            "sampling_rate_hz": sampling_rate_hz,
            "dtype": dtype,
            "source": source,
            "source_chunk_count": len(self._source_chunk_offsets),
            "first_host_utc": self._source_chunk_host_utc[0],
            "last_host_utc": self._source_chunk_host_utc[-1],
            "first_host_monotonic_ns": self._source_chunk_host_monotonic_ns[0],
            "last_host_monotonic_ns": self._source_chunk_host_monotonic_ns[-1],
            "first_device_timestamp": (
                float(finite_timestamps[0]) if finite_timestamps.size else None
            ),
            "last_device_timestamp": (
                float(finite_timestamps[-1]) if finite_timestamps.size else None
            ),
            "written_at": _utc_now_iso(),
        }
        with files.manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(manifest_entry, ensure_ascii=False, separators=(",", ":"))
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        files.next_chunk_index += 1
        self._clear_buffer_locked()
        return destination

    def _clear_buffer_locked(self) -> None:
        self._sample_parts.clear()
        self._timestamp_parts.clear()
        self._host_timestamp_parts.clear()
        self._source_chunk_offsets.clear()
        self._source_chunk_host_monotonic_ns.clear()
        self._source_chunk_host_utc.clear()
        self._source_chunk_device_seconds.clear()
        self._buffered_samples = 0


def _safe_component(value: str) -> str:
    safe = _SAFE_NAME.sub("_", value).strip("._")
    if safe:
        return safe
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"session_{digest}"


def _next_chunk_index(manifest_path: Path, chunks_directory: Path) -> int:
    """Return a collision-free index when reopening an existing recording."""

    indices: list[int] = []
    if manifest_path.exists():
        if not manifest_path.is_file():
            raise RuntimeError(f"Raw EEG manifest is not a file: {manifest_path}")
        for line_number, line in enumerate(
            manifest_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                indices.append(int(entry["chunk_index"]))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"Invalid raw EEG manifest entry at {manifest_path}:{line_number}"
                ) from exc

    for path in chunks_directory.iterdir():
        match = _CHUNK_NAME.fullmatch(path.name)
        if match and path.is_file():
            indices.append(int(match.group(1)))
    return max(indices, default=-1) + 1


def _validate_existing_metadata(path: Path, session_id: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"Raw EEG metadata is not a file: {path}")
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid raw EEG metadata: {path}") from exc
    expected = {
        "schema_version": RAW_EEG_SCHEMA_VERSION,
        "format": "chunked_npz",
        "session_id": session_id,
    }
    mismatches = [
        f"{key}={metadata.get(key)!r} (expected {value!r})"
        for key, value in expected.items()
        if metadata.get(key) != value
    ]
    if mismatches:
        raise RuntimeError(
            f"Raw EEG metadata does not match resumed recording {path}: "
            + ", ".join(mismatches)
        )


def _write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(content)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
