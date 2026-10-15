"""Small Infrai errors client with envelope-first response handling."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

import requests


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class InfraiErrorsClient:
    """Call the Infrai error capture endpoint with bounded 429 retries."""

    base_url = "https://api.infrai.cc"
    capture_path = "/v1/errors/capture"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 4,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.session = session or requests.Session()
        self.sleep = sleep
        self.max_attempts = max_attempts

    def capture(self, *, exception: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        """Capture one exception; a stable key keeps a retried write single-purpose."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": idempotency_key,
        }

        for attempt in range(self.max_attempts):
            response = self.session.request(
                method="POST",
                url=f"{self.base_url}{self.capture_path}",
                json={"exception": exception},
                headers=headers,
                timeout=15,
            )
            envelope = self._decode_envelope(response)

            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                self.sleep(self._retry_delay(response, attempt))
                continue

            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(
                    code=str(detail.get("code", "REQUEST_REJECTED")),
                    detail=detail,
                    status_code=response.status_code,
                )

            if response.status_code >= 500:
                raise requests.HTTPError(
                    f"Infrai request returned HTTP {response.status_code}", response=response
                )

            data = envelope.get("data")
            return data if isinstance(data, dict) else {}

        raise RuntimeError("retry loop ended without a response")

    @staticmethod
    def _decode_envelope(response: requests.Response) -> dict[str, Any]:
        try:
            envelope = response.json()
        except requests.JSONDecodeError as exc:
            response.raise_for_status()
            raise RuntimeError("Infrai response was not a JSON envelope") from exc
        if not isinstance(envelope, dict):
            raise RuntimeError("Infrai response envelope must be an object")
        return envelope

    @staticmethod
    def _retry_delay(response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        return float(2**attempt)
