import json
import unittest
from pathlib import Path

from recon_pipeline.gaze import EyeFeatureExtractor


class EyeFeatureTests(unittest.TestCase):
    def test_recorded_tobii_trajectory_produces_fixed_eye_metrics(self):
        fixture = Path(__file__).parent / "fixtures" / "tobii_mapped_trajectory.json"
        mapping = json.loads(fixture.read_text(encoding="utf-8"))

        eye = EyeFeatureExtractor().snapshot(mapping)

        self.assertGreater(eye.aoi_dwell_time, 0.2)
        self.assertGreaterEqual(eye.fixation_count, 1)
        self.assertGreater(eye.mean_fixation_duration, 0.1)
        self.assertEqual(
            set(eye.to_dict()),
            {
                "aoi_dwell_time",
                "fixation_count",
                "mean_fixation_duration",
                "aoi_revisit_count",
                "aoi_revisit_time",
            },
        )

    def test_returns_revisit_count_and_time_for_two_aoi_visits(self):
        mapping = {
            "valid": True,
            "reading_aoi": {"x_min": 0.4, "y_min": 0.4, "x_max": 0.6, "y_max": 0.6},
            "trajectory": [
                {"x_normalized": 0.45, "y_normalized": 0.45, "age_ms": 1000},
                {"x_normalized": 0.46, "y_normalized": 0.46, "age_ms": 900},
                {"x_normalized": 0.45, "y_normalized": 0.45, "age_ms": 800},
                {"x_normalized": 0.2, "y_normalized": 0.2, "age_ms": 700},
                {"x_normalized": 0.46, "y_normalized": 0.46, "age_ms": 600},
                {"x_normalized": 0.45, "y_normalized": 0.45, "age_ms": 500},
                {"x_normalized": 0.46, "y_normalized": 0.46, "age_ms": 400},
            ],
        }

        eye = EyeFeatureExtractor().snapshot(mapping)

        self.assertEqual(eye.aoi_revisit_count, 1)
        self.assertAlmostEqual(eye.aoi_revisit_time, 0.2)

    def test_invalid_mapping_does_not_fabricate_eye_metrics(self):
        eye = EyeFeatureExtractor().snapshot({"valid": False, "trajectory": []})

        self.assertIsNone(eye.aoi_dwell_time)
        self.assertIsNone(eye.fixation_count)
        self.assertIsNone(eye.mean_fixation_duration)
        self.assertIsNone(eye.aoi_revisit_count)
        self.assertIsNone(eye.aoi_revisit_time)


if __name__ == "__main__":
    unittest.main()
