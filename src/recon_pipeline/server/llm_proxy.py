"""Credential-safe OpenAI-compatible LLM proxy used by the experiment UI."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from ..config import LLMConfig


class LLMProxy:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def complete(
        self, payload: Dict[str, Any], request_authorization: Optional[str] = None
    ) -> Tuple[int, bytes]:
        if not self.config.enabled:
            return 503, _error("LLM proxy is disabled.", 503)
        api_key = os.getenv(self.config.api_key_env, "").strip()
        authorization = (request_authorization or "").strip()
        if not authorization and api_key:
            authorization = f"Bearer {api_key}"
        if not authorization:
            return 401, _error(
                f"Missing API key. Set environment variable {self.config.api_key_env}.", 401
            )

        outgoing = dict(payload)
        requested_model = str(outgoing.get("model", "")).strip()
        if not requested_model:
            outgoing["model"] = self.config.default_model
        body = json.dumps(outgoing, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.config.endpoint,
            data=body,
            headers={"Content-Type": "application/json", "Authorization": authorization},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                return int(response.status), response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read()
            return int(exc.code), body or _error("Upstream LLM HTTP error.", int(exc.code))
        except urllib.error.URLError as exc:
            if os.name == "nt":
                fallback = self._complete_with_windows_curl(body, authorization)
                if fallback is not None:
                    return fallback
            return 502, _error(f"Upstream LLM network error: {exc.reason}", 502)
        except Exception as exc:
            if os.name == "nt":
                fallback = self._complete_with_windows_curl(body, authorization)
                if fallback is not None:
                    return fallback
            return 500, _error(f"Local LLM proxy error: {exc}", 500)

    def _complete_with_windows_curl(
        self, body: bytes, authorization: str
    ) -> Optional[Tuple[int, bytes]]:
        """Use Schannel's best-effort revocation mode when the CRL is offline."""
        try:
            result = subprocess.run(
                [
                    "curl.exe",
                    "--silent",
                    "--show-error",
                    "--ssl-revoke-best-effort",
                    "--max-time",
                    str(max(1, int(self.config.timeout_seconds))),
                    "--header",
                    "Content-Type: application/json",
                    "--header",
                    f"Authorization: {authorization}",
                    "--data-binary",
                    "@-",
                    "--write-out",
                    "\n%{http_code}",
                    self.config.endpoint,
                ],
                input=body,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.config.timeout_seconds + 5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        response_body, separator, status_text = result.stdout.rpartition(b"\n")
        if not separator:
            return None
        try:
            return int(status_text.strip()), response_body
        except ValueError:
            return None


def _error(message: str, status: int) -> bytes:
    return json.dumps({"error": {"message": message, "status": status}}, ensure_ascii=False).encode(
        "utf-8"
    )
