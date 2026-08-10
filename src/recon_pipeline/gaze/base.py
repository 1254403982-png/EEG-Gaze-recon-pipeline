"""Hardware-neutral gaze acquisition contract."""

from __future__ import annotations

from typing import Optional, Protocol

from ..models import GazeFeatures


class GazeProvider(Protocol):
    @property
    def is_running(self) -> bool: ...

    def start(self, session_id: str) -> None: ...

    def read(self) -> Optional[GazeFeatures]: ...

    def stop(self) -> None: ...
