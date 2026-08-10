import unittest

import numpy as np

from recon_pipeline.acquisition.brainco import BRAINCO_32_CHANNELS
from recon_pipeline.eeg.brainco_mapping import BrainCoNeuraDockMapper


class BrainCoMappingTests(unittest.TestCase):
    def test_maps_real_and_surrogate_channels_explicitly(self):
        channels = list(BRAINCO_32_CHANNELS)
        samples = np.vstack([np.full(4, index, dtype=np.float32) for index in range(len(channels))])
        output = BrainCoNeuraDockMapper().transform(samples, channels)
        index = {name: position for position, name in enumerate(channels)}

        self.assertEqual(output.shape, (7, 4))
        np.testing.assert_allclose(output[0], samples[index["CP5"]])
        np.testing.assert_allclose(output[2], (samples[index["P3"]] + samples[index["O1"]]) / 2)
        np.testing.assert_allclose(
            output[5],
            (samples[index["PZ"]] + samples[index["O1"]] + samples[index["O2"]]) / 3,
        )

    def test_rejects_missing_channels(self):
        with self.assertRaisesRegex(ValueError, "Missing required"):
            BrainCoNeuraDockMapper().transform(np.zeros((2, 10)), ["CP5", "CP6"])


if __name__ == "__main__":
    unittest.main()
