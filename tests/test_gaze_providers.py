import asyncio
import tempfile
import unittest
from pathlib import Path

from recon_pipeline.gaze import (
    AOIRegion,
    ReplayGazeProvider,
    TobiiG3Provider,
    TobiiGazeFeatureExtractor,
    UnavailableGazeProvider,
)
from recon_pipeline.gaze.tobii import _drain_async_queue, _rtsp_url_for_transport
from recon_pipeline.models import SignalStatus


class GazeProviderTests(unittest.TestCase):
    def test_unavailable_provider_never_fabricates_measurements(self):
        provider = UnavailableGazeProvider()
        provider.start("S001")

        result = provider.read()

        self.assertEqual(result.status, SignalStatus.UNAVAILABLE)
        self.assertIsNone(result.x_normalized)
        self.assertIsNone(result.pupil_dilation)

    def test_replay_provider_preserves_explicit_features(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "gaze.jsonl"
            source.write_text(
                '{"status":"available","quality":"pass",'
                '"primary_aoi":"reading","gaze_entropy":0.7,'
                '"eye":{"aoi_dwell_time":1.2,"fixation_count":3,'
                '"mean_fixation_duration":0.25}}\n',
                encoding="utf-8",
            )
            provider = ReplayGazeProvider(source)
            provider.start("S001")

            result = provider.read()

            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.primary_aoi, "reading")
            self.assertEqual(result.gaze_entropy, 0.7)
            self.assertEqual(result.eye.fixation_count, 3)
            self.assertEqual(result.eye.aoi_dwell_time, 1.2)
            self.assertIsNone(provider.read())

    def test_tobii_extractor_builds_quality_gated_policy_features(self):
        extractor = TobiiGazeFeatureExtractor(
            window_seconds=3.0,
            min_valid_samples=3,
            aoi_regions=[AOIRegion("reading_content", 0.4, 0.4, 0.7, 0.7)],
        )
        extractor.add({"gaze2d": [0.50, 0.50]}, 10.00, received_monotonic=100.00)
        extractor.add({"gaze2d": [0.51, 0.49]}, 10.02, received_monotonic=100.02)
        extractor.add({"gaze2d": [0.50, 0.51]}, 10.04, received_monotonic=100.04)

        result = extractor.snapshot(now_monotonic=100.05)

        self.assertEqual(result.status, SignalStatus.AVAILABLE)
        self.assertEqual(result.quality, "pass")
        self.assertEqual(result.primary_aoi, "reading_content")
        self.assertEqual(result.metadata["scene_region"], "scene_center")
        self.assertAlmostEqual(result.valid_sample_ratio, 1.0)
        self.assertIsNotNone(result.fixation_duration_ms)
        self.assertIsNotNone(result.gaze_entropy)
        self.assertEqual(
            result.metadata["coordinate_system"],
            "tobii_scene_camera_normalized",
        )

    def test_tobii_extractor_does_not_mark_invalid_samples_as_available(self):
        extractor = TobiiGazeFeatureExtractor(min_valid_samples=2)
        extractor.add({"gaze2d": [0.2, 0.4]}, received_monotonic=200.0)
        extractor.add({"gaze2d": [1.4, 0.4]}, received_monotonic=200.1)
        extractor.add({}, received_monotonic=200.2)

        result = extractor.snapshot(now_monotonic=200.3)

        self.assertEqual(result.status, SignalStatus.WARNING)
        self.assertNotEqual(result.quality, "pass")
        self.assertAlmostEqual(result.valid_sample_ratio, 1.0 / 3.0)

    def test_tobii_extractor_returns_rolling_trajectory(self):
        extractor = TobiiGazeFeatureExtractor(window_seconds=2.0)
        extractor.add({"gaze2d": [0.1, 0.2]}, received_monotonic=100.0)
        extractor.add({"gaze2d": [0.3, 0.4]}, received_monotonic=101.0)
        extractor.add({"gaze2d": [0.5, 0.6]}, received_monotonic=102.5)

        points = extractor.recent_valid_points(now_monotonic=102.6)

        self.assertEqual([(x, y) for x, y, _ in points], [(0.3, 0.4), (0.5, 0.6)])
        self.assertAlmostEqual(points[-1][2], 100.0)

    def test_tobii_provider_exposes_raw_samples_with_both_clocks(self):
        provider = TobiiG3Provider()

        provider._record_gaze_payload(
            {"gaze2d": [0.25, 0.75]},
            12.5,
            received_monotonic=123.0,
        )
        samples = provider.drain_raw_samples()

        self.assertEqual(len(samples), 1)
        self.assertTrue(samples[0]["valid"])
        self.assertEqual(samples[0]["timestamp"]["device_seconds"], 12.5)
        self.assertEqual(samples[0]["timestamp"]["host_monotonic_ns"], 123_000_000_000)
        self.assertEqual(provider.drain_raw_samples(), [])

    def test_tobii_calibration_requires_an_active_device_connection(self):
        provider = TobiiG3Provider()

        with self.assertRaisesRegex(RuntimeError, "not connected"):
            provider.request_calibration()

        status = provider.calibration_status()
        self.assertEqual(status["status"], "idle")
        self.assertFalse(status["connected"])

    def test_tobii_rtcp_queue_is_drained_without_blocking(self):
        queue = asyncio.Queue()
        queue.put_nowait("gaze-rtcp")
        queue.put_nowait("scene-rtcp")

        drained = _drain_async_queue(queue)

        self.assertEqual(drained, 2)
        self.assertTrue(queue.empty())

    def test_tobii_uses_interleaved_tcp_transport_by_default(self):
        provider = TobiiG3Provider()

        self.assertEqual(provider.rtsp_transport, "tcp")
        self.assertEqual(
            _rtsp_url_for_transport(
                "rtsp://169.254.217.102:8554/live/all",
                provider.rtsp_transport,
            ),
            "rtspt://169.254.217.102:8554/live/all",
        )

    def test_tobii_udp_transport_remains_available_for_fallback(self):
        provider = TobiiG3Provider(rtsp_transport="udp")

        self.assertEqual(
            _rtsp_url_for_transport(
                "rtspt://169.254.217.102:8554/live/all",
                provider.rtsp_transport,
            ),
            "rtsp://169.254.217.102:8554/live/all",
        )

    def test_tobii_gaze_only_mode_disables_scene_camera(self):
        provider = TobiiG3Provider(scene_camera=False)

        self.assertFalse(provider.scene_camera_enabled)
        self.assertIsNone(provider.latest_scene_frame())


if __name__ == "__main__":
    unittest.main()
