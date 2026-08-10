import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import numpy as np

from recon_pipeline.acquisition import BrainCoSDKAcquirer, BrainCoSource


class BrainCoSDKAdapterTests(unittest.TestCase):
    def test_normalizes_sdk_sample_major_buffer_to_32_channels(self):
        acquirer = BrainCoSDKAcquirer()
        raw = np.arange(64, dtype=np.float32).reshape(2, 32)

        normalized = acquirer._normalize_buffer(raw)

        self.assertEqual(normalized.shape, (32, 2))
        np.testing.assert_array_equal(normalized[:, 0], raw[0])

    def test_extracts_message_id_from_nested_sdk_payload(self):
        acquirer = BrainCoSDKAcquirer()

        result = acquirer._extract_message_id(({"response": {"msgId": 42}},))

        self.assertEqual(result, 42)

    def test_brainco_source_no_longer_requires_legacy_project_path(self):
        source = BrainCoSource()

        self.assertEqual(len(source.channel_names), 32)
        self.assertFalse(source.is_running)

    def test_integrated_adapter_completes_sdk_lifecycle(self):
        sdk = ModuleType("bc_ecap_sdk")
        sdk.EegSampleRate = SimpleNamespace(SR_250Hz="rate")
        sdk.EegSignalGain = SimpleNamespace(GAIN_6="gain")
        sdk.EegSignalSource = SimpleNamespace(NORMAL="source")
        sdk.MsgType = SimpleNamespace(EEGCap="cap")
        sdk.MessageParser = lambda device_id, message_type: (device_id, message_type)
        sdk.set_cfg = lambda *args: None
        sdk.clear_eeg_buffer = lambda: None
        sdk.set_connection_state_callback = lambda callback: None
        sdk.set_received_data_callback = lambda callback: None
        sdk.set_imp_data_callback = lambda callback: None
        sdk.set_msg_resp_callback = lambda callback: None
        buffers = [np.arange(320, dtype=np.float32).reshape(10, 32)]
        sdk.get_eeg_buffer = lambda count, remove: buffers.pop(0) if buffers else []

        class Client:
            async def start_data_stream(self, parser):
                return None

            async def set_eeg_config(self, sample_rate, gain, source):
                return 0

            async def start_eeg_stream(self):
                return 0

            async def stop_eeg_stream(self):
                return 0

            def disconnect_tcp_blocking(self):
                return None

        sdk.ECapClient = lambda address, port: Client()
        acquirer = BrainCoSDKAcquirer(
            address="127.0.0.1",
            port=53129,
            auto_discover=False,
            ready_timeout_seconds=0.5,
            start_retries=1,
        )

        with patch.dict("sys.modules", {"bc_ecap_sdk": sdk}):
            try:
                acquirer.start()
                samples, timestamps = acquirer.read_new_samples()
            finally:
                acquirer.stop()

        self.assertEqual(samples.shape, (32, 10))
        self.assertEqual(timestamps.shape, (10,))

    def test_sdk_05_uses_unified_start_stream(self):
        sdk = ModuleType("bc_ecap_sdk")
        sdk.EegSampleRate = SimpleNamespace(SR_250Hz="rate")
        sdk.EegSignalGain = SimpleNamespace(GAIN_6="gain")
        sdk.EegSignalSource = SimpleNamespace(NORMAL="source")
        sdk.MsgType = SimpleNamespace(EEGCap="cap")
        sdk.MessageParser = lambda device_id, message_type: (device_id, message_type)
        sdk.clear_eeg_buffer = lambda: None
        sdk.set_connection_state_callback = lambda callback: None
        sdk.set_received_data_callback = lambda callback: None
        sdk.set_imp_data_callback = lambda callback: None
        sdk.set_msg_resp_callback = lambda callback: None
        buffers = [np.arange(320, dtype=np.float32).reshape(10, 32)]
        sdk.get_eeg_buffer = lambda count, remove: buffers.pop(0) if buffers else []
        calls = []

        class Client:
            async def start_stream(self, parser, *, fs, gain, signal):
                calls.append((parser, fs, gain, signal))

            async def stop_eeg_stream(self):
                return 0

            def disconnect_tcp_blocking(self):
                return None

        sdk.ECapClient = lambda address, port: Client()
        acquirer = BrainCoSDKAcquirer(
            address="127.0.0.1",
            port=53129,
            auto_discover=False,
            ready_timeout_seconds=0.5,
            start_retries=1,
            enable_imu=True,
        )

        with patch.dict("sys.modules", {"bc_ecap_sdk": sdk}):
            try:
                acquirer.start()
            finally:
                acquirer.stop()

        self.assertEqual(calls, [(('eeg-cap', 'cap'), 'rate', 'gain', 'source')])

    def test_sdk_05_defaults_to_eeg_only_transport(self):
        sdk = ModuleType("bc_ecap_sdk")
        sdk.EegSampleRate = SimpleNamespace(SR_250Hz="rate")
        sdk.EegSignalGain = SimpleNamespace(GAIN_6="gain")
        sdk.EegSignalSource = SimpleNamespace(NORMAL="source")
        sdk.MsgType = SimpleNamespace(EEGCap="cap")
        sdk.MessageParser = lambda device_id, message_type: (device_id, message_type)
        sdk.clear_eeg_buffer = lambda: None
        sdk.set_connection_state_callback = lambda callback: None
        sdk.set_received_data_callback = lambda callback: None
        sdk.set_imp_data_callback = lambda callback: None
        sdk.set_msg_resp_callback = lambda callback: None
        sdk.set_cfg = lambda *args: None
        buffers = [np.arange(320, dtype=np.float32).reshape(10, 32)]
        sdk.get_eeg_buffer = lambda count, remove: buffers.pop(0) if buffers else []
        calls = []

        class Client:
            async def start_stream(self, parser, *, fs, gain, signal):
                calls.append("unified")

            async def start_data_stream(self, parser):
                calls.append("data")

            async def set_eeg_config(self, sample_rate, gain, source):
                calls.append("config")
                return 0

            async def start_eeg_stream(self):
                calls.append("eeg")
                return 0

            async def stop_eeg_stream(self):
                return 0

            def disconnect_tcp_blocking(self):
                return None

        sdk.ECapClient = lambda address, port: Client()
        acquirer = BrainCoSDKAcquirer(
            address="127.0.0.1",
            port=53129,
            auto_discover=False,
            ready_timeout_seconds=0.5,
            start_retries=1,
        )

        with patch.dict("sys.modules", {"bc_ecap_sdk": sdk}):
            try:
                acquirer.start()
            finally:
                acquirer.stop()

        self.assertEqual(calls, ["data", "config", "eeg"])


if __name__ == "__main__":
    unittest.main()
