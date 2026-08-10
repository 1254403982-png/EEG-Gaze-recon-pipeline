"""Integrated BrainCo EEG Cap SDK transport.

Adapted from ``oi-mi/acquisition/brainco_acquirer.py`` (MIT License,
Copyright (c) 2026 oi-mi contributors). Only the acquisition transport needed
by recon is included here.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
import threading
import time
from collections import deque
from collections.abc import Awaitable, Sequence
from typing import Any, Optional

import numpy as np

LOGGER = logging.getLogger(__name__)
_BRAINCO_MDNS_SERVICE = "_brainco-eeg._tcp.local."
_SAMPLE_RATE_TO_ENUM = {
    250: "SR_250Hz", 500: "SR_500Hz", 1000: "SR_1000Hz", 2000: "SR_2000Hz"
}
_GAIN_TO_ENUM = {
    1: "GAIN_1", 2: "GAIN_2", 4: "GAIN_4", 6: "GAIN_6",
    8: "GAIN_8", 12: "GAIN_12", 24: "GAIN_24",
}


class BrainCoSDKAcquirer:
    """Own the BrainCo SDK lifecycle and expose incremental channel samples."""

    def __init__(
        self,
        *,
        sampling_rate_hz: float = 250.0,
        channel_count: int = 32,
        buffer_seconds: float = 60.0,
        address: str = "",
        port: int = 0,
        auto_discover: bool = True,
        scan_timeout_seconds: float = 6.0,
        ready_timeout_seconds: float = 10.0,
        start_retries: int = 2,
        gain: int = 6,
        signal_source: str = "NORMAL",
        enable_imu: bool = False,
        device_id: str = "eeg-cap",
    ) -> None:
        if not 1 <= channel_count <= 32:
            raise ValueError("BrainCo EEG Cap supports 1-32 EEG channels.")
        if int(sampling_rate_hz) not in _SAMPLE_RATE_TO_ENUM:
            raise ValueError("Unsupported BrainCo sample rate: %s" % sampling_rate_hz)
        if gain not in _GAIN_TO_ENUM:
            raise ValueError("Unsupported BrainCo gain: %s" % gain)
        self.sampling_rate_hz = float(sampling_rate_hz)
        self.channel_count = int(channel_count)
        self.buffer_seconds = float(buffer_seconds)
        self.address = address.strip()
        self.port = int(port)
        self.auto_discover = bool(auto_discover)
        self.scan_timeout_seconds = float(scan_timeout_seconds)
        self.ready_timeout_seconds = float(ready_timeout_seconds)
        self.start_retries = max(1, int(start_retries))
        self.gain = int(gain)
        self.signal_source = signal_source.strip().upper() or "NORMAL"
        self.enable_imu = bool(enable_imu)
        self.device_id = device_id

        self._sdk: Any = None
        self._client: Any = None
        self._parser: Any = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._response_event = threading.Event()
        self._response_lock = threading.Lock()
        self._pending_responses: dict[int, deque[tuple[Any, ...]]] = {}
        self._generic_responses: deque[tuple[Any, ...]] = deque()
        self._pending_samples = np.empty((self.channel_count, 0), dtype=np.float32)
        self._samples_emitted = 0
        self._raw_packet_count = 0
        self._cached_target: Optional[tuple[str, int]] = None

    @property
    def is_running(self) -> bool:
        return self._client is not None and self._sdk is not None

    def start(self) -> None:
        try:
            import bc_ecap_sdk as sdk
        except ImportError as exc:
            raise RuntimeError(
                "bc_ecap_sdk is not installed; install recon with the 'brainco' extra."
            ) from exc
        if self.is_running:
            self.stop()
        last_error: Optional[Exception] = None
        for attempt in range(1, self.start_retries + 1):
            self._prepare_attempt(sdk)
            try:
                address, port = self._connect()
                sample_rate = getattr(
                    sdk.EegSampleRate, _SAMPLE_RATE_TO_ENUM[int(self.sampling_rate_hz)]
                )
                gain = getattr(sdk.EegSignalGain, _GAIN_TO_ENUM[self.gain])
                signal = getattr(sdk.EegSignalSource, self.signal_source)
                unified_start = getattr(self._client, "start_stream", None)
                if self.enable_imu and unified_start is not None:
                    LOGGER.info("Starting BrainCo EEG+IMU stream with unified SDK API")
                    self._run_sdk_call(
                        unified_start,
                        self._parser,
                        fs=sample_rate,
                        gain=gain,
                        signal=signal,
                    )
                else:
                    LOGGER.info(
                        "Starting BrainCo EEG-only stream; unused IMU transport is disabled"
                    )
                    buffer_length = max(
                        int(self.sampling_rate_hz * min(self.buffer_seconds, 60.0)), 1024
                    )
                    sdk.set_cfg(buffer_length, max(256, int(self.sampling_rate_hz)), 256)
                    start_data_stream = getattr(self._client, "start_data_stream", None)
                    if start_data_stream is None:
                        raise RuntimeError("BrainCo SDK has no EEG-only TCP stream API.")
                    self._run_sdk_call(start_data_stream, self._parser)
                    config_id = self._run_sdk_call(
                        self._client.set_eeg_config, sample_rate, gain, signal
                    )
                    self._wait_for_response(config_id, "set_eeg_config", allow_missing=True)
                    sdk.clear_eeg_buffer()
                    start_id = self._run_sdk_call(self._client.start_eeg_stream)
                    self._wait_for_response(start_id, "start_eeg_stream", allow_missing=True)
                self._wait_for_first_samples()
                LOGGER.info(
                    "BrainCo acquisition started at %s:%s %.1fHz %s channels",
                    address, port, self.sampling_rate_hz, self.channel_count,
                )
                return
            except Exception as exc:
                last_error = exc
                LOGGER.warning(
                    "BrainCo stream start attempt %s/%s failed: %s",
                    attempt, self.start_retries, exc,
                )
                self.stop()
                if attempt < self.start_retries:
                    time.sleep(0.5)
        assert last_error is not None
        raise last_error

    def stop(self) -> None:
        sdk, client = self._sdk, self._client
        self._client = None
        self._parser = None
        if client is not None:
            try:
                self._run_sdk_call(client.stop_eeg_stream)
            except Exception as exc:
                LOGGER.warning("Failed to stop BrainCo EEG stream cleanly: %s", exc)
            try:
                client.disconnect_tcp_blocking()
            except Exception as exc:
                LOGGER.warning("Failed to disconnect BrainCo TCP client cleanly: %s", exc)
        if sdk is not None:
            try:
                sdk.clear_eeg_buffer()
            except Exception:
                pass
            self._clear_callbacks()
        self._stop_loop_thread()
        self._sdk = None
        self._response_event.clear()
        with self._response_lock:
            self._pending_responses.clear()
            self._generic_responses.clear()
        self._pending_samples = np.empty((self.channel_count, 0), dtype=np.float32)
        self._raw_packet_count = 0
        LOGGER.info("BrainCo acquisition stopped")

    def read_new_samples(self) -> tuple[np.ndarray, np.ndarray]:
        if not self.is_running:
            raise RuntimeError("BrainCo stream is not started.")
        fresh = self._take_sdk_buffer()
        if self._pending_samples.shape[1]:
            fresh = np.concatenate([self._pending_samples, fresh], axis=1)
            self._pending_samples = np.empty((self.channel_count, 0), dtype=np.float32)
        if fresh.shape[1] == 0:
            return fresh, np.empty((0,), dtype=np.float64)
        first = self._samples_emitted
        self._samples_emitted += fresh.shape[1]
        timestamps = np.arange(first, self._samples_emitted, dtype=np.float64)
        return fresh, timestamps / self.sampling_rate_hz

    def _prepare_attempt(self, sdk: Any) -> None:
        self._sdk = sdk
        self._client = None
        self._response_event.clear()
        with self._response_lock:
            self._pending_responses.clear()
            self._generic_responses.clear()
        self._pending_samples = np.empty((self.channel_count, 0), dtype=np.float32)
        self._samples_emitted = 0
        self._raw_packet_count = 0
        self._start_loop_thread()

    def _connect(self) -> tuple[str, int]:
        assert self._sdk is not None
        address, port = self._resolve_target()
        self._client = self._sdk.ECapClient(address, port)
        self._parser = self._sdk.MessageParser(self.device_id, self._sdk.MsgType.EEGCap)
        self._register_callbacks()
        return address, port

    def _resolve_target(self) -> tuple[str, int]:
        if self.address and self.port > 0:
            return self.address, self.port
        if self._cached_target is not None:
            return self._cached_target
        if not self.auto_discover:
            raise RuntimeError("BrainCo address/port missing and auto_discover is disabled.")
        target = self._run_coroutine(
            # SDK scan, direct Zeroconf, and SDK callback fallback each have their
            # own bounded scan window. Let the coroutine finish those fallbacks so
            # the caller receives a useful discovery error instead of a generic
            # outer future timeout.
            self._discover_async(), timeout=(3.0 * self.scan_timeout_seconds) + 7.0
        )
        self._cached_target = target
        return target

    async def _discover_async(self) -> tuple[str, int]:
        assert self._sdk is not None
        # The native scanner in bc-ecap-sdk 0.5.0 can block inside the extension
        # on Windows, which means asyncio.wait_for cannot cancel it. Direct
        # zeroconf is both bounded and sufficient for the advertised TCP endpoint.
        target = await asyncio.to_thread(self._discover_via_zeroconf)
        if target is not None:
            LOGGER.info("BrainCo device discovered via direct zeroconf: %s:%s", *target)
            return target
        candidates: list[Any] = []
        try:
            result = await asyncio.wait_for(
                self._coerce_awaitable(self._sdk.mdns_start_scan()),
                timeout=self.scan_timeout_seconds,
            )
            if isinstance(result, Sequence) and not isinstance(
                result, (str, bytes, bytearray)
            ):
                candidates.extend(result)
            elif result is not None:
                candidates.append(result)
        except asyncio.TimeoutError:
            LOGGER.warning("BrainCo SDK mDNS scan timed out; trying fallback discovery")
        finally:
            await self._stop_mdns_scan()
        for candidate in candidates:
            target = self._coerce_target(candidate)
            if target is not None:
                return target
        target = await self._discover_via_callback()
        if target is not None:
            return target
        raise RuntimeError("BrainCo auto-discovery found no usable device endpoint.")

    async def _discover_via_callback(self) -> Optional[tuple[str, int]]:
        assert self._sdk is not None
        scan_multi = getattr(self._sdk, "mdns_start_scan_multi", None)
        if scan_multi is None:
            return None
        loop = asyncio.get_running_loop()
        discovered: asyncio.Future[tuple[str, int]] = loop.create_future()
        task: Optional[asyncio.Task[Any]] = None

        def on_device(device: Any) -> None:
            target = self._coerce_target(device)
            if target is not None and not discovered.done():
                def deliver() -> None:
                    if not discovered.done():
                        discovered.set_result(target)
                loop.call_soon_threadsafe(deliver)

        try:
            operation = scan_multi(on_device)
            if hasattr(operation, "__await__"):
                task = asyncio.create_task(self._coerce_awaitable(operation))
            return await asyncio.wait_for(discovered, timeout=self.scan_timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            await self._stop_mdns_scan()
            if task is not None and not task.done():
                task.cancel()

    async def _stop_mdns_scan(self) -> None:
        if self._sdk is None:
            return
        try:
            operation = self._sdk.mdns_stop_scan()
            if hasattr(operation, "__await__"):
                await asyncio.wait_for(
                    self._coerce_awaitable(operation),
                    timeout=min(2.0, max(0.5, self.scan_timeout_seconds)),
                )
        except Exception:
            pass

    def _discover_via_zeroconf(self) -> Optional[tuple[str, int]]:
        try:
            from zeroconf import IPVersion, ServiceBrowser, ServiceListener, Zeroconf
        except ImportError:
            return None
        resolved: Optional[tuple[str, int]] = None
        event = threading.Event()
        zeroconf = Zeroconf()
        timeout_ms = max(1000, int(self.scan_timeout_seconds * 1000))

        class Listener(ServiceListener):
            def add_service(self, zc: Any, service_type: str, name: str) -> None:
                self._resolve(zc, service_type, name)

            def update_service(self, zc: Any, service_type: str, name: str) -> None:
                self._resolve(zc, service_type, name)

            def remove_service(self, zc: Any, service_type: str, name: str) -> None:
                return

            def _resolve(self, zc: Any, service_type: str, name: str) -> None:
                nonlocal resolved
                info = zc.get_service_info(service_type, name, timeout=timeout_ms)
                if info is None:
                    return
                addresses = info.parsed_addresses(IPVersion.All)
                if addresses and int(info.port) > 0:
                    resolved = addresses[0], int(info.port)
                    event.set()

        browser: Any = None
        try:
            browser = ServiceBrowser(zeroconf, _BRAINCO_MDNS_SERVICE, listener=Listener())
            event.wait(self.scan_timeout_seconds)
            return resolved
        finally:
            if browser is not None:
                browser.cancel()
            zeroconf.close()

    def _coerce_target(self, device: Any) -> Optional[tuple[str, int]]:
        address: Any = None
        port: Any = None
        if isinstance(device, dict):
            address = (
                device.get("addr") or device.get("address") or device.get("host")
                or device.get("hostname") or device.get("ip")
            )
            port = device.get("port")
        elif isinstance(device, Sequence) and not isinstance(
            device, (str, bytes, bytearray)
        ):
            address = device[0] if len(device) else None
            port = device[1] if len(device) > 1 else None
        elif isinstance(device, (str, bytes, bytearray)):
            text = (
                device.decode(errors="ignore")
                if isinstance(device, (bytes, bytearray))
                else device
            )
            address, port = self._split_target(text)
        else:
            address = (
                getattr(device, "addr", None) or getattr(device, "address", None)
                or getattr(device, "host", None) or getattr(device, "hostname", None)
            )
            port = getattr(device, "port", None)
        try:
            numeric_port = int(port or self.port)
        except (TypeError, ValueError):
            numeric_port = 0
        if address in (None, "") or numeric_port <= 0:
            return None
        return str(address).strip(), numeric_port

    @staticmethod
    def _split_target(value: str) -> tuple[str, int]:
        text = value.strip()
        bracket = re.fullmatch(r"\[(.+)\]:(\d+)", text)
        if bracket:
            return bracket.group(1), int(bracket.group(2))
        if text.count(":") == 1:
            host, port = text.rsplit(":", 1)
            if port.isdigit():
                return host, int(port)
        return text, 0

    def _wait_for_first_samples(self) -> None:
        deadline = time.monotonic() + self.ready_timeout_seconds
        while time.monotonic() < deadline:
            data = self._take_sdk_buffer()
            if data.shape[1]:
                self._pending_samples = np.concatenate([self._pending_samples, data], axis=1)
                return
            time.sleep(0.1)
        if self._raw_packet_count <= 0:
            raise RuntimeError(
                "Timed out waiting for BrainCo EEG samples; no TCP payloads or SDK "
                "responses were observed. Check device_id and firmware protocol."
            )
        raise RuntimeError(
            "Timed out waiting for BrainCo EEG samples; TCP payloads arrived but the "
            "SDK EEG buffer remained empty."
        )

    def _take_sdk_buffer(self) -> np.ndarray:
        assert self._sdk is not None
        take = max(int(self.sampling_rate_hz * min(self.buffer_seconds, 60.0)), 256)
        return self._normalize_buffer(self._sdk.get_eeg_buffer(take, True))

    def _normalize_buffer(self, raw: Any) -> np.ndarray:
        array = np.asarray([] if raw is None else raw, dtype=np.float32)
        if array.size == 0:
            return np.empty((self.channel_count, 0), dtype=np.float32)
        if array.ndim == 1:
            if array.size % self.channel_count:
                raise RuntimeError("Unexpected BrainCo EEG buffer size: %s" % array.size)
            array = array.reshape(-1, self.channel_count)
        if array.ndim != 2:
            raise RuntimeError("Unexpected BrainCo EEG buffer shape: %s" % (array.shape,))
        if array.shape[1] == self.channel_count:
            return np.asarray(array.T, dtype=np.float32)
        if array.shape[0] == self.channel_count:
            return np.asarray(array, dtype=np.float32)
        if array.shape[1] > self.channel_count:
            return np.asarray(array[:, : self.channel_count].T, dtype=np.float32)
        if array.shape[0] > self.channel_count:
            return np.asarray(array[: self.channel_count], dtype=np.float32)
        raise RuntimeError("Unexpected BrainCo channel layout: %s" % (array.shape,))

    def _register_callbacks(self) -> None:
        assert self._sdk is not None
        self._sdk.set_connection_state_callback(self._connection_callback)
        self._sdk.set_received_data_callback(self._received_data_callback)
        self._sdk.set_imp_data_callback(self._noop_callback)
        self._sdk.set_msg_resp_callback(self._message_response_callback)

    def _clear_callbacks(self) -> None:
        assert self._sdk is not None
        for setter in (
            "set_connection_state_callback", "set_received_data_callback",
            "set_imp_data_callback", "set_msg_resp_callback",
        ):
            try:
                getattr(self._sdk, setter)(self._noop_callback)
            except Exception:
                pass

    def _connection_callback(self, *args: Any) -> None:
        if args:
            LOGGER.info("BrainCo connection state: %s", ", ".join(map(repr, args)))

    def _received_data_callback(self, *args: Any) -> None:
        del args
        self._raw_packet_count += 1
        self._response_event.set()

    def _message_response_callback(self, *args: Any) -> None:
        message_id = self._extract_message_id(args)
        with self._response_lock:
            if message_id is None:
                self._generic_responses.append(tuple(args))
            else:
                self._pending_responses.setdefault(message_id, deque()).append(tuple(args))
        self._response_event.set()

    def _wait_for_response(self, message_id: Any, label: str, *, allow_missing: bool) -> None:
        if not isinstance(message_id, int) or message_id <= 0:
            return
        deadline = time.monotonic() + self.ready_timeout_seconds
        while time.monotonic() < deadline:
            with self._response_lock:
                responses = self._pending_responses.get(message_id)
                if responses:
                    responses.popleft()
                    if not responses:
                        self._pending_responses.pop(message_id, None)
                    return
                if self._generic_responses:
                    self._generic_responses.popleft()
                    return
            if self._response_event.wait(0.1):
                self._response_event.clear()
        if allow_missing:
            LOGGER.warning(
                "Timed out waiting for BrainCo response to %s (msgId=%s); "
                "continuing until samples arrive.", label, message_id,
            )
            return
        raise RuntimeError("Timed out waiting for BrainCo response to %s." % label)

    def _extract_message_id(self, payload: Any) -> Optional[int]:
        if isinstance(payload, bool):
            return None
        if isinstance(payload, int):
            return payload if payload > 0 else None
        if isinstance(payload, dict):
            for key in ("msgId", "msg_id", "id"):
                result = self._extract_message_id(payload.get(key))
                if result is not None:
                    return result
            for value in payload.values():
                result = self._extract_message_id(value)
                if result is not None:
                    return result
            return None
        if isinstance(payload, (str, bytes, bytearray)):
            text = (
                payload.decode(errors="ignore")
                if isinstance(payload, (bytes, bytearray))
                else payload
            )
            match = re.search(r'"?msgId"?\s*[:=]\s*(\d+)', text)
            return int(match.group(1)) if match else None
        if isinstance(payload, Sequence):
            for item in payload:
                result = self._extract_message_id(item)
                if result is not None:
                    return result
        return None

    @staticmethod
    def _noop_callback(*args: Any) -> None:
        del args

    def _start_loop_thread(self) -> None:
        if self._loop is not None:
            return
        ready = threading.Event()

        def runner() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            ready.set()
            loop.run_forever()
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

        self._loop_thread = threading.Thread(
            target=runner, name="brainco-sdk-loop", daemon=True
        )
        self._loop_thread.start()
        if not ready.wait(2.0):
            raise RuntimeError("Failed to start BrainCo asyncio loop thread.")

    def _stop_loop_thread(self) -> None:
        loop, thread = self._loop, self._loop_thread
        self._loop = None
        self._loop_thread = None
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=2.0)

    async def _coerce_awaitable(self, value: Any) -> Any:
        if hasattr(value, "__await__"):
            return await value
        return value

    def _run_sdk_call(self, function: Any, *args: Any, **kwargs: Any) -> Any:
        async def runner() -> Any:
            return await self._coerce_awaitable(function(*args, **kwargs))
        return self._run_coroutine(runner(), timeout=self.ready_timeout_seconds)

    def _run_coroutine(self, coroutine: Awaitable[Any], *, timeout: float) -> Any:
        if self._loop is None:
            raise RuntimeError("BrainCo SDK event loop is not running.")
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise RuntimeError("BrainCo SDK call timed out.") from exc
