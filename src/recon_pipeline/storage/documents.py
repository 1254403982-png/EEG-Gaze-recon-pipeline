"""Atomic JSON document storage for completed experiment payloads."""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


class JsonDocumentStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory.expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def save(self, payload: Dict[str, Any]) -> Path:
        subject = str(payload.get("subjectId") or payload.get("subject_id") or "unknown")
        safe_subject = _SAFE_NAME.sub("_", subject).strip("._") or "unknown"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        destination = self.directory / f"{safe_subject}_{stamp}.json"
        temporary = destination.with_suffix(".json.tmp")
        content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        with self._lock:
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(destination)
        return destination
