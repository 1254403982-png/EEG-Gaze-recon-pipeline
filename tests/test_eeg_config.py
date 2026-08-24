import unittest
from pathlib import Path

from recon_pipeline.config import load_config
from recon_pipeline.eeg import build_eeg_processor


class EEGConfigTests(unittest.TestCase):
    def test_development_config_builds_32_channel_decoder_graph(self):
        root = Path(__file__).resolve().parents[1]
        config = load_config(root / "configs" / "development.json")

        processor = build_eeg_processor(config.eeg)

        self.assertEqual(config.policy.eeg_weight, 0.60)
        self.assertEqual(config.policy.gaze_weight, 0.40)
        self.assertEqual(config.policy.required_confirmations, 2)
        self.assertEqual(config.policy.minimum_evidence_seconds, 0.20)
        self.assertEqual(config.policy.minimum_trial_seconds, 20.0)
        self.assertEqual(config.policy.max_automatic_offers_per_trial, 0)
        self.assertTrue(config.policy.require_screen_mapping)
        self.assertEqual(config.policy.gaze_min_valid_ratio, 0.50)
        self.assertEqual(config.policy.brief_threshold, 40)
        self.assertEqual(config.policy.c3_policy_version, "v1")
        self.assertEqual(config.policy.example_threshold, 60)
        self.assertEqual(config.policy.detailed_threshold, 80)
        self.assertEqual(config.policy.fixation_reference_ms, 1000)
        self.assertTrue(config.policy.allow_degraded_c3)
        self.assertEqual(config.policy.eye_baseline_seconds, 5.0)
        self.assertEqual(config.policy.cooldown_seconds, 8.0)
        self.assertEqual(config.policy.eye_abnormal_ratio, 1.25)
        self.assertEqual(config.policy.eye_single_feature_ratio, 1.70)
        self.assertEqual(config.policy.eye_mild_threshold, 1.35)
        self.assertEqual(config.policy.eye_moderate_threshold, 1.55)
        self.assertEqual(config.policy.eye_strong_threshold, 2.00)
        self.assertEqual(config.policy.c2_eye_abnormal_ratio, 1.20)
        self.assertEqual(config.policy.c2_eye_single_feature_ratio, 1.70)
        self.assertEqual(config.policy.c2_eye_mild_threshold, 1.15)
        self.assertEqual(config.policy.c2_eye_moderate_threshold, 1.55)
        self.assertEqual(config.policy.c2_eye_strong_threshold, 2.00)
        self.assertEqual(config.policy.c2_cooldown_seconds, 30.0)
        self.assertEqual(config.policy.c2_max_automatic_offers_per_trial, 2)
        self.assertEqual(config.policy.eye_revisit_count_weight, 0.15)
        self.assertEqual(config.policy.eye_revisit_time_weight, 0.15)
        self.assertEqual(config.policy.eeg_medium_threshold, 50)
        self.assertEqual(config.policy.eeg_high_threshold, 80)
        self.assertEqual(config.policy.attention_low_threshold, 40)
        self.assertEqual(config.eeg.primary_decoder, "cognitive_workload")
        self.assertEqual(config.eeg.quality["line_power_threshold"], 10)
        self.assertEqual(config.eeg.quality["high_frequency_power_threshold"], 30)
        self.assertEqual(config.eeg.quality["extreme_amplitude_threshold"], 100)
        self.assertEqual(config.eeg.quality["max_bad_channel_ratio"], 0.45)
        self.assertFalse(config.eeg.brainco.enable_imu)
        workload = next(
            decoder for decoder in config.eeg.decoders
            if decoder.decoder_id == "cognitive_workload"
        )
        self.assertEqual(workload.options["min_good_frontal_channels"], 1)
        self.assertEqual(processor.primary_decoder, "cognitive_workload")
        self.assertEqual(len(processor.decoders), 1)
        self.assertEqual(
            processor.decoders[0].channels,
            ("FZ", "F3", "F4", "FC1", "FC2", "P3", "P4", "P7", "P8", "PZ", "O1", "O2"),
        )
        self.assertEqual(processor.decoders[0].max_bad_channel_ratio, 0.45)

    def test_c3_v2_profile_inherits_hardware_and_preserves_v1_default(self):
        root = Path(__file__).resolve().parents[1]
        original = load_config(root / "configs" / "development.json")
        revised = load_config(root / "configs" / "development_c3_v2.json")

        self.assertEqual(original.policy.c3_policy_version, "v1")
        self.assertEqual(revised.policy.c3_policy_version, "v2")
        self.assertEqual(revised.policy.max_automatic_offers_per_trial, 2)
        self.assertFalse(revised.policy.allow_degraded_c3)
        self.assertEqual(revised.policy.cooldown_seconds, 30.0)
        self.assertEqual(revised.eeg, original.eeg)
        self.assertEqual(revised.llm, original.llm)


if __name__ == "__main__":
    unittest.main()
