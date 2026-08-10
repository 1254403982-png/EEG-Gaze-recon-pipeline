import json
import tempfile
import unittest
from pathlib import Path

from recon_pipeline.runtime import EEGAcquisitionWorker, GazeAcquisitionWorker
from recon_pipeline.storage import JsonlRecorder


class _Source:
    def start(self):
        return

    def read(self):
        return None

    def stop(self):
        return


class _Processor:
    def __init__(self):
        self.reset_count = 0

    def reset(self):
        self.reset_count += 1


class EEGAcquisitionWorkerTests(unittest.TestCase):
    def test_processor_resets_only_when_session_changes(self):
        processor = _Processor()
        worker = EEGAcquisitionWorker(_Source(), object(), processor=processor)

        worker._reset_processor_for_session("development")
        worker._reset_processor_for_session("development")
        worker._reset_processor_for_session("participant-001")

        self.assertEqual(processor.reset_count, 2)


class _RawGazeProvider:
    def drain_raw_samples(self):
        return [
            {
                "timestamp": {"host_monotonic_ns": 10, "device_seconds": 1.25},
                "x_normalized": 0.2,
                "y_normalized": 0.8,
                "valid": True,
            }
        ]


class _Application:
    def recording_context(self):
        return {"session_id": "S001", "trial_id": "T01", "condition": 3, "phase": "reading"}


class GazeAcquisitionWorkerTests(unittest.TestCase):
    def test_raw_gaze_samples_are_attributed_and_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw_gaze.jsonl"
            worker = GazeAcquisitionWorker(
                _RawGazeProvider(),
                _Application(),
                session_id="S001",
                raw_recorder=JsonlRecorder(path),
            )

            worker._persist_raw_samples()

            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["event_type"], "raw_gaze_sample")
            self.assertEqual(record["trial_id"], "T01")
            self.assertEqual(record["phase"], "reading")
            self.assertEqual(record["x_normalized"], 0.2)


if __name__ == "__main__":
    unittest.main()
