"""Thread-safe append-only JSONL recorder."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Iterable


class JsonlRecorder:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, payload: Dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")

    def append_many(self, payloads: Iterable[Dict[str, Any]]) -> None:
        lines = [
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
            for payload in payloads
        ]
        if not lines:
            return
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
            handle.write("\n")
