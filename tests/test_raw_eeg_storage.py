import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from recon_pipeline.acquisition.base import RawEEGChunk
from recon_pipeline.clock import Timestamp
from recon_pipeline.storage import RawEEGRecorder


def raw_chunk(start: int, sample_count: int, *, sampling_rate_hz: float = 10.0):
    samples = np.vstack(
        [
            np.arange(start, start + sample_count, dtype=np.float32),
            np.arange(100 + start, 100 + start + sample_count, dtype=np.float32),
        ]
    )
    timestamps = np.arange(start, start + sample_count, dtype=np.float64) / sampling_rate_hz
    return RawEEGChunk(
        samples=samples,
        channel_names=("C1", "C2"),
        sampling_rate_hz=sampling_rate_hz,
        timestamp=Timestamp(
            host_monotonic_ns=1_000_000_000 + start,
            utc=f"2026-07-24T00:00:{start:02d}.000Z",
            device_seconds=float(timestamps[-1]),
        ),
        sample_timestamps=timestamps,
        source="brainco-test",
    )


class RawEEGRecorderTests(unittest.TestCase):
    def test_writes_full_and_partial_chunks_without_losing_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = RawEEGRecorder(Path(directory), chunk_seconds=1.0)

            first_result = recorder.append(
                raw_chunk(0, 6),
                session_id="S001",
                trial_id="T01",
                condition=3,
                phase="reading",
            )
            second_result = recorder.append(
                raw_chunk(6, 9),
                session_id="S001",
                trial_id="T01",
                condition=3,
                phase="reading",
            )
            close_result = recorder.close()

            self.assertEqual(first_result, [])
            self.assertEqual(len(second_result), 1)
            self.assertEqual(len(close_result), 1)

            session_directory = recorder.session_directories["S001"]
            chunks = sorted((session_directory / "chunks").glob("chunk_*.npz"))
            self.assertEqual(len(chunks), 2)

            stored_samples = []
            stored_timestamps = []
            for chunk_path in chunks:
                with np.load(chunk_path, allow_pickle=False) as payload:
                    stored_samples.append(payload["samples"])
                    stored_timestamps.append(payload["device_timestamps"])
                    self.assertEqual(payload["session_id"].item(), "S001")
                    self.assertEqual(payload["trial_id"].item(), "T01")
                    self.assertEqual(payload["condition"].item(), 3)
                    self.assertEqual(payload["source"].item(), "brainco-test")

            expected = np.concatenate([raw_chunk(0, 6).samples, raw_chunk(6, 9).samples], axis=1)
            np.testing.assert_array_equal(np.concatenate(stored_samples, axis=1), expected)
            np.testing.assert_allclose(
                np.concatenate(stored_timestamps),
                np.arange(15, dtype=np.float64) / 10.0,
            )

            manifest = [
                json.loads(line)
                for line in (session_directory / "manifest.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual([entry["sample_count"] for entry in manifest], [10, 5])
            for entry, chunk_path in zip(manifest, chunks):
                digest = hashlib.sha256(chunk_path.read_bytes()).hexdigest()
                self.assertEqual(entry["sha256"], digest)

    def test_context_change_flushes_before_next_trial(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = RawEEGRecorder(Path(directory), chunk_seconds=10.0)
            recorder.append(
                raw_chunk(0, 4),
                session_id="S001",
                trial_id="T01",
                condition=1,
                phase="reading",
            )

            completed = recorder.append(
                raw_chunk(4, 4),
                session_id="S001",
                trial_id="T02",
                condition=2,
                phase="reading",
            )
            recorder.close()

            self.assertEqual(len(completed), 1)
            session_directory = recorder.session_directories["S001"]
            manifest = [
                json.loads(line)
                for line in (session_directory / "manifest.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(
                [(entry["trial_id"], entry["condition"]) for entry in manifest],
                [("T01", 1), ("T02", 2)],
            )

    def test_development_session_is_not_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = RawEEGRecorder(Path(directory), chunk_seconds=1.0)

            result = recorder.append(
                raw_chunk(0, 10),
                session_id="development",
                trial_id=None,
                condition=1,
            )
            recorder.close()

            self.assertEqual(result, [])
            self.assertEqual(recorder.session_directories, {})
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_rejects_misaligned_device_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = RawEEGRecorder(Path(directory), chunk_seconds=1.0)
            chunk = raw_chunk(0, 4)
            chunk.sample_timestamps = np.arange(3, dtype=np.float64)

            with self.assertRaisesRegex(ValueError, "one value per sample"):
                recorder.append(
                    chunk,
                    session_id="S001",
                    trial_id="T01",
                    condition=1,
                )


if __name__ == "__main__":
    unittest.main()
