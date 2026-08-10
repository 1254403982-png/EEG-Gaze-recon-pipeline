"""Clock helpers shared by acquisition, synchronization, and logging."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class Timestamp:
    """A comparable host clock plus an auditable wall-clock timestamp."""

    host_monotonic_ns: int
    utc: str
    device_seconds: Optional[float] = None

    @classmethod
    def now(cls, device_seconds: Optional[float] = None) -> "Timestamp":
        return cls(
            host_monotonic_ns=time.monotonic_ns(),
            utc=utc_now_iso(),
            device_seconds=device_seconds,
        )

    @classmethod
    def from_monotonic_ns(
        cls, host_monotonic_ns: int, device_seconds: Optional[float] = None
    ) -> "Timestamp":
        now_ns = time.monotonic_ns()
        wall = datetime.now(timezone.utc)
        elapsed_seconds = max(0.0, (now_ns - int(host_monotonic_ns)) / 1_000_000_000.0)
        observed = datetime.fromtimestamp(wall.timestamp() - elapsed_seconds, timezone.utc)
        return cls(
            host_monotonic_ns=int(host_monotonic_ns),
            utc=observed.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            device_seconds=device_seconds,
        )

    def age_ms(self, now_monotonic_ns: Optional[int] = None) -> float:
        now = time.monotonic_ns() if now_monotonic_ns is None else now_monotonic_ns
        return max(0.0, (now - self.host_monotonic_ns) / 1_000_000.0)

    def to_dict(self) -> dict:
        return {
            "host_monotonic_ns": self.host_monotonic_ns,
            "utc": self.utc,
            "device_seconds": self.device_seconds,
        }
