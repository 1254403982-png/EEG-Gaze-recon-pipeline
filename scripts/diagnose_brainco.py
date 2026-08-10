"""Bounded BrainCo discovery and control-channel diagnostic for Windows."""

from __future__ import annotations

import argparse
import asyncio
import socket
import threading
import time
from typing import Any

import bc_ecap_sdk as sdk


SERVICE = "_brainco-eeg._tcp.local."


def discover(timeout: float) -> tuple[str, int, str] | None:
    from zeroconf import IPVersion, ServiceBrowser, ServiceListener, Zeroconf

    result: tuple[str, int, str] | None = None
    ready = threading.Event()
    zc = Zeroconf()

    class Listener(ServiceListener):
        def add_service(self, z: Any, service_type: str, name: str) -> None:
            self._resolve(z, service_type, name)

        def update_service(self, z: Any, service_type: str, name: str) -> None:
            self._resolve(z, service_type, name)

        def remove_service(self, z: Any, service_type: str, name: str) -> None:
            return

        def _resolve(self, z: Any, service_type: str, name: str) -> None:
            nonlocal result
            info = z.get_service_info(service_type, name, timeout=int(timeout * 1000))
            if info is not None:
                addresses = info.parsed_addresses(IPVersion.All)
                if addresses and info.port:
                    result = addresses[0], int(info.port), name
                    ready.set()

    browser = ServiceBrowser(zc, SERVICE, listener=Listener())
    try:
        ready.wait(timeout)
        return result
    finally:
        browser.cancel()
        zc.close()


async def probe(address: str, port: int, timeout: float) -> None:
    events: list[tuple[str, tuple[Any, ...]]] = []

    def record(kind: str):
        def callback(*args: Any) -> None:
            events.append((kind, args))
            print(f"callback[{kind}]: {args!r}", flush=True)
        return callback

    sdk.set_connection_state_callback(record("connection"))
    sdk.set_received_data_callback(record("data"))
    sdk.set_msg_resp_callback(record("response"))
    parser = sdk.MessageParser("eeg-cap", sdk.MsgType.EEGCap)
    client = sdk.ECapClient(address, port)
    try:
        await asyncio.wait_for(client.start_data_stream(parser), timeout=timeout)
        print("TCP listener started; requesting device info and battery", flush=True)
        await client.get_device_info()
        await client.get_battery_level()
        await asyncio.sleep(timeout)
        print(f"callback_count={len(events)}")
    finally:
        await client.disconnect_tcp()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--address")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    if bool(args.address) != bool(args.port):
        parser.error("--address and --port must be supplied together")
    target = (
        (args.address, args.port, "manual")
        if args.address and args.port
        else discover(args.timeout)
    )
    print("discovery:", target)
    if target is None:
        raise SystemExit("BrainCo mDNS service was not found")
    address, port, _ = target
    with socket.create_connection((address, port), timeout=args.timeout):
        print(f"tcp: reachable ({address}:{port})")
    asyncio.run(probe(address, port, args.timeout))


if __name__ == "__main__":
    main()
