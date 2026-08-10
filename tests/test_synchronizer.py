import unittest

from recon_pipeline.clock import Timestamp
from recon_pipeline.models import EEGFeatures, GazeFeatures, SignalStatus
from recon_pipeline.synchronization import MultimodalSynchronizer


class SynchronizerTests(unittest.TestCase):
    def test_marks_old_eeg_as_stale(self):
        synchronizer = MultimodalSynchronizer(max_eeg_age_ms=100)
        synchronizer.start_session("S001", condition=3)
        timestamp = Timestamp(host_monotonic_ns=1_000_000_000, utc="test")
        synchronizer.update_eeg(
            EEGFeatures(timestamp, SignalStatus.AVAILABLE, "pass", cognitive_load=50)
        )

        snapshot = synchronizer.snapshot(now_monotonic_ns=1_200_000_000)

        self.assertEqual(snapshot.eeg.status, SignalStatus.STALE)
        self.assertEqual(snapshot.gaze.status, SignalStatus.UNAVAILABLE)

    def test_rejects_unknown_condition(self):
        with self.assertRaisesRegex(ValueError, "1, 2, or 3"):
            MultimodalSynchronizer().start_session("S001", condition=4)

    def test_reports_host_clock_alignment_between_eeg_and_gaze(self):
        synchronizer = MultimodalSynchronizer()
        synchronizer.start_session("S001", condition=3)
        synchronizer.update_eeg(
            EEGFeatures(Timestamp(2_020_000_000, "eeg"), SignalStatus.AVAILABLE, "pass")
        )
        synchronizer.update_gaze(
            GazeFeatures(Timestamp(2_000_000_000, "gaze"), SignalStatus.AVAILABLE, "pass")
        )

        payload = synchronizer.snapshot(now_monotonic_ns=2_030_000_000).to_dict()

        self.assertEqual(payload["synchronization"]["clock"], "host_monotonic")
        self.assertEqual(payload["synchronization"]["eeg_minus_gaze_ms"], 20.0)
        self.assertEqual(payload["synchronization"]["absolute_skew_ms"], 20.0)


if __name__ == "__main__":
    unittest.main()
