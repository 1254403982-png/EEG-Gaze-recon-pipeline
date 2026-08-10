import unittest

import numpy as np

from recon_pipeline.acquisition import BRAINCO_32_CHANNELS
from recon_pipeline.eeg import (
    CognitiveWorkloadDecoder,
    EEGDecoderResult,
    OnlineEEGProcessor,
    PosteriorAlphaDecoder,
)


def _sine_matrix(frequency_by_channel, *, fs=250, seconds=4):
    time = np.arange(fs * seconds) / fs
    return np.vstack(
        [
            8.0 * np.sin(2 * np.pi * frequency_by_channel[name] * time)
            for name in BRAINCO_32_CHANNELS
        ]
    ).astype(np.float32)


class MeanPowerDecoder:
    decoder_id = "mean_power"

    def reset(self):
        return

    def decode(self, window):
        channels = ("F3", "F4")
        indices = window.channel_indices(channels)
        value = float(np.mean(window.power_spectral_density[list(indices)]))
        return EEGDecoderResult(
            decoder_id=self.decoder_id,
            quality="pass",
            metrics={"mean_power": value},
            channels_requested=channels,
            channels_used=channels,
        )


class OnlineEEGProcessorTests(unittest.TestCase):
    def test_workload_decoder_combines_frontal_theta_and_posterior_alpha(self):
        frequencies = {name: 10.0 for name in BRAINCO_32_CHANNELS}
        for name in ("FZ", "F3", "F4", "FC1", "FC2"):
            frequencies[name] = 6.0
        decoder = CognitiveWorkloadDecoder()
        processor = OnlineEEGProcessor(decoders=[decoder], primary_decoder="cognitive_workload")

        result = processor.append(_sine_matrix(frequencies), BRAINCO_32_CHANNELS)

        assert result is not None
        self.assertEqual(result.quality, "pass")
        self.assertIsNotNone(result.frontal_theta_power)
        self.assertIsNotNone(result.posterior_alpha_power)
        self.assertIsNotNone(result.workload_index)
        self.assertIsNone(result.attention)

    def test_full_32_channel_window_emits_primary_alpha_features(self):
        fs = 250
        frequencies = {name: 10.0 for name in BRAINCO_32_CHANNELS}
        samples = _sine_matrix(frequencies, fs=fs)
        processor = OnlineEEGProcessor(sampling_rate_hz=fs)

        result = processor.append(samples[:, :500], BRAINCO_32_CHANNELS)
        self.assertIsNone(result)
        result = processor.append(samples[:, 500:], BRAINCO_32_CHANNELS)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.quality, "pass")
        self.assertEqual(result.metadata["channel_count"], 32)
        self.assertEqual(result.metadata["channels"], list(BRAINCO_32_CHANNELS))
        self.assertEqual(
            result.metadata["quality_control"]["thresholds"]["extreme_sample_count"],
            500.0,
        )
        self.assertEqual(result.metadata["quality_control"]["bad_channel_reasons"], {})
        self.assertAlmostEqual(result.alpha_peak_hz, 10.0, delta=0.6)
        self.assertEqual(result.cognitive_load, 50.0)

    def test_quality_control_reports_each_bad_channel_reason(self):
        frequencies = {name: 30.0 for name in BRAINCO_32_CHANNELS}
        samples = _sine_matrix(frequencies)
        processor = OnlineEEGProcessor()

        result = processor.append(samples, BRAINCO_32_CHANNELS)

        assert result is not None
        reasons = result.metadata["quality_control"]["bad_channel_reasons"]
        self.assertIn("high_frequency", reasons["P3"])

    def test_decoder_channel_selection_is_independent_from_preprocessing(self):
        frequencies = {name: 12.0 for name in BRAINCO_32_CHANNELS}
        selected = ("P3", "P4", "PZ", "O1", "O2")
        for name in selected:
            frequencies[name] = 10.0
        samples = _sine_matrix(frequencies)
        decoder = PosteriorAlphaDecoder(channels=selected, min_good_channels=3)
        processor = OnlineEEGProcessor(decoders=[decoder])

        result = processor.append(samples, BRAINCO_32_CHANNELS)

        self.assertIsNotNone(result)
        assert result is not None
        output = result.metadata["decoder_outputs"]["posterior_alpha"]
        self.assertEqual(output["channels_used"], list(selected))
        self.assertAlmostEqual(result.alpha_peak_hz, 10.0, delta=0.6)

    def test_posterior_decoder_allows_three_but_not_four_bad_channels(self):
        posterior = ("P3", "P4", "P7", "P8", "PZ", "O1", "O2")

        def analyze(bad_count):
            frequencies = {name: 10.0 for name in BRAINCO_32_CHANNELS}
            for name in posterior[:bad_count]:
                frequencies[name] = 30.0
            processor = OnlineEEGProcessor()
            result = processor.append(_sine_matrix(frequencies), BRAINCO_32_CHANNELS)
            assert result is not None
            return result

        three_bad = analyze(3)
        four_bad = analyze(4)

        self.assertEqual(three_bad.quality, "pass")
        self.assertEqual(
            three_bad.metadata["decoder_outputs"]["posterior_alpha"]["bad_channels"],
            list(posterior[:3]),
        )
        self.assertEqual(four_bad.quality, "warning")

    def test_additional_decoder_publishes_metrics_without_changing_policy_contract(self):
        frequencies = {name: 10.0 for name in BRAINCO_32_CHANNELS}
        samples = _sine_matrix(frequencies)
        alpha = PosteriorAlphaDecoder()
        processor = OnlineEEGProcessor(
            decoders=[alpha, MeanPowerDecoder()],
            primary_decoder="posterior_alpha",
        )

        result = processor.append(samples, BRAINCO_32_CHANNELS)

        self.assertIsNotNone(result)
        assert result is not None
        outputs = result.metadata["decoder_outputs"]
        self.assertIn("mean_power", outputs)
        self.assertGreater(outputs["mean_power"]["metrics"]["mean_power"], 0.0)
        self.assertIsNotNone(result.cognitive_load)

    def test_rejects_channel_layout_changes_within_one_session(self):
        samples = np.zeros((32, 10), dtype=np.float32)
        processor = OnlineEEGProcessor()
        processor.append(samples, BRAINCO_32_CHANNELS)

        with self.assertRaisesRegex(ValueError, "layout changed"):
            processor.append(samples, tuple(reversed(BRAINCO_32_CHANNELS)))

    def test_preserves_acquisition_host_timestamp(self):
        samples = _sine_matrix({name: 10.0 for name in BRAINCO_32_CHANNELS})
        processor = OnlineEEGProcessor()

        result = processor.append(
            samples,
            BRAINCO_32_CHANNELS,
            device_seconds=4.0,
            host_monotonic_ns=123_000_000,
        )

        assert result is not None
        self.assertEqual(result.timestamp.host_monotonic_ns, 123_000_000)
        self.assertEqual(result.timestamp.device_seconds, 4.0)

    def test_missing_decoder_channels_count_against_quality(self):
        available = ("P3", "P4", "P7")
        time = np.arange(1000) / 250.0
        samples = np.vstack(
            [8.0 * np.sin(2 * np.pi * 10.0 * time) for _ in available]
        ).astype(np.float32)
        processor = OnlineEEGProcessor()

        result = processor.append(samples, available)

        self.assertIsNotNone(result)
        assert result is not None
        output = result.metadata["decoder_outputs"]["posterior_alpha"]
        self.assertEqual(result.quality, "warning")
        self.assertEqual(output["missing_channels"], ["P8", "PZ", "O1", "O2"])


if __name__ == "__main__":
    unittest.main()
