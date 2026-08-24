"""Bounded, installation-wide transport for app-owned SEC HTTP traffic."""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

import requests

from .sec_user_agent import DEFAULT_SEC_USER_AGENT, get_sec_user_agent


_ALLOWED_HOSTS = frozenset({"data.sec.gov", "www.sec.gov", "efts.sec.gov"})
_CANONICAL_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
_EMAIL_TOKEN = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])")
_PROCESS_LOCK = threading.Lock()
_DEFAULT_JSON_BYTES = 16 * 1024 * 1024
_MAX_DIAGNOSTIC_INTEGER = 12_582_912


class SecTransportFailure(RuntimeError):
    """A closed, secret-safe SEC transport failure."""

    def __init__(self, code: str, *, status_code: int | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass
class SecRequestBudget:
    max_attempts: int = 16
    max_documents: int = 12
    max_document_bytes: int = 1_048_576
    max_total_bytes: int = 12 * 1_048_576
    attempt_count: int = 0
    document_count: int = 0
    body_bytes: int = 0

    def __post_init__(self) -> None:
        values = (
            self.max_attempts,
            self.max_documents,
            self.max_document_bytes,
            self.max_total_bytes,
        )
        if any(type(value) is not int or value < 1 for value in values):
            raise ValueError("invalid SEC request budget")

    @classmethod
    def lifecycle(cls) -> "SecRequestBudget":
        return cls()

    def reserve_attempt(self) -> None:
        if self.attempt_count >= self.max_attempts:
            raise SecTransportFailure("sec_request_budget_exhausted")
        self.attempt_count += 1

    def reserve_document(self, requested_max_bytes: int) -> None:
        if (
            self.document_count >= self.max_documents
            or requested_max_bytes > self.max_document_bytes
            or self.body_bytes >= self.max_total_bytes
        ):
            raise SecTransportFailure("sec_request_budget_exhausted")
        self.document_count += 1

    def available_body_bytes(self, requested_max_bytes: int) -> int:
        remaining = self.max_total_bytes - self.body_bytes
        if remaining <= 0:
            raise SecTransportFailure("sec_request_budget_exhausted")
        return min(requested_max_bytes, remaining)

    def record_body(self, count: int) -> None:
        if count < 0 or self.body_bytes + count > self.max_total_bytes:
            raise SecTransportFailure("sec_request_budget_exhausted")
        self.body_bytes += count

    def diagnostics(self) -> dict[str, int]:
        return {
            "attempt_count": self.attempt_count,
            "document_count": self.document_count,
            "body_bytes": self.body_bytes,
        }


class SecRequestGovernor:
    """Serialize SEC request starts across threads and local processes."""

    interval_seconds = 0.2

    def __init__(
        self,
        *,
        lock_dir: str | Path | None = None,
        process_lock: threading.Lock | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        root = lock_dir or os.environ.get("ARKSCOPE_LOCK_DIR")
        if root is None:
            root = Path(__file__).resolve().parents[1] / "data" / "locks"
        self.lock_dir = Path(root)
        self.state_path = self.lock_dir / "sec_request_governor.state"
        self._process_lock = process_lock or _PROCESS_LOCK
        self._clock = clock
        self._sleep = sleep

    @staticmethod
    def _format_instant(value: float) -> str:
        try:
            safe_value = math.ceil(value * 1_000_000) / 1_000_000
            return datetime.fromtimestamp(safe_value, timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            )
        except (OverflowError, OSError, ValueError) as exc:
            raise SecTransportFailure("sec_governor_unavailable") from exc

    @staticmethod
    def _parse_instant(value: str) -> float:
        if not _CANONICAL_INSTANT.fullmatch(value):
            raise SecTransportFailure("sec_governor_unavailable")
        try:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
                tzinfo=timezone.utc
            ).timestamp()
        except ValueError as exc:
            raise SecTransportFailure("sec_governor_unavailable") from exc

    def reserve_request_start(self) -> int:
        try:
            import fcntl
        except ImportError as exc:
            raise SecTransportFailure("sec_governor_unavailable") from exc

        try:
            self.lock_dir.mkdir(parents=True, exist_ok=True)
            with self._process_lock:
                with self.state_path.open("a+", encoding="ascii") as handle:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                    try:
                        handle.seek(0)
                        raw = handle.read()
                        if raw and (not raw.endswith("\n") or raw.count("\n") != 1):
                            raise SecTransportFailure("sec_governor_unavailable")
                        previous = self._parse_instant(raw[:-1]) if raw else None
                        now = float(self._clock())
                        if not (0 <= now < 253_402_300_800):
                            raise SecTransportFailure("sec_governor_unavailable")
                        if previous is not None and previous - now > 30:
                            raise SecTransportFailure("sec_governor_unavailable")
                        wait = max(0.0, (previous + self.interval_seconds) - now) if previous is not None else 0.0
                        if wait:
                            self._sleep(wait)
                        started = float(self._clock())
                        if started + 1e-6 < now + wait:
                            raise SecTransportFailure("sec_governor_unavailable")
                        handle.seek(0)
                        handle.truncate()
                        handle.write(self._format_instant(started) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                        return int(round(wait * 1000))
                    finally:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except SecTransportFailure:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise SecTransportFailure("sec_governor_unavailable") from exc


@dataclass(frozen=True)
class SecResponse:
    status_code: int
    body: bytes
    encoding: str = "utf-8"

    @property
    def text(self) -> str:
        return self.body.decode(self.encoding or "utf-8", errors="replace")

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode(self.encoding or "utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SecTransportFailure("sec_invalid_json") from exc

    def raise_for_status(self) -> None:
        if not 200 <= self.status_code < 300:
            raise SecTransportFailure("sec_http_error", status_code=self.status_code)


class SecTransport:
    """Strict SEC client with bounded reads and one shared request governor."""

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        session: Any | None = None,
        governor: SecRequestGovernor | None = None,
        lock_dir: str | Path | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.user_agent = str(user_agent if user_agent is not None else get_sec_user_agent()).strip()
        self._session = session or requests.Session()
        self._governor = governor or SecRequestGovernor(lock_dir=lock_dir, sleep=sleep)
        self._sleep = sleep
        self._governor_wait_ms = 0
        self._rate_limit_retries = 0

    def _validate_identity(self) -> None:
        if (
            not self.user_agent
            or self.user_agent == DEFAULT_SEC_USER_AGENT
            or _EMAIL_TOKEN.search(self.user_agent) is None
        ):
            raise SecTransportFailure("sec_identity_unconfigured")

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlsplit(str(url))
        try:
            port = parsed.port
        except ValueError as exc:
            raise SecTransportFailure("sec_url_unsupported") from exc
        if (
            parsed.scheme != "https"
            or parsed.hostname not in _ALLOWED_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or port not in (None, 443)
        ):
            raise SecTransportFailure("sec_url_unsupported")

    @staticmethod
    def _retry_after_seconds(headers: Mapping[str, str]) -> int:
        raw = str(headers.get("Retry-After", "")).strip()
        if not raw.isdigit():
            raise SecTransportFailure("sec_rate_limited")
        seconds = int(raw)
        if not 0 <= seconds <= 30:
            raise SecTransportFailure("sec_rate_limited")
        return seconds

    @staticmethod
    def _read_bounded(response: Any, max_bytes: int) -> bytes:
        raw_length = str(getattr(response, "headers", {}).get("Content-Length", "")).strip()
        if raw_length.isdigit() and int(raw_length) > max_bytes:
            raise SecTransportFailure("sec_response_too_large")
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=min(65_536, max_bytes + 1)):
            if not chunk:
                continue
            if not isinstance(chunk, bytes):
                raise SecTransportFailure("sec_transport_unavailable")
            total += len(chunk)
            if total > max_bytes:
                raise SecTransportFailure("sec_response_too_large")
            chunks.append(chunk)
        return b"".join(chunks)

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        timeout: float = 30,
        max_bytes: int | None = None,
        document: bool = False,
        budget: SecRequestBudget | None = None,
        accept: str = "application/json, application/xml, text/html",
    ) -> SecResponse:
        self._validate_identity()
        self._validate_url(url)
        if max_bytes is None:
            max_bytes = (
                budget.max_document_bytes
                if document and budget is not None
                else _DEFAULT_JSON_BYTES
            )
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("invalid SEC response bound")
        if document and budget is not None:
            budget.reserve_document(max_bytes)
        effective_max = budget.available_body_bytes(max_bytes) if budget is not None else max_bytes

        for attempt in range(2):
            if budget is not None:
                budget.reserve_attempt()
            wait_ms = self._governor.reserve_request_start()
            self._governor_wait_ms = min(
                _MAX_DIAGNOSTIC_INTEGER, self._governor_wait_ms + max(0, wait_ms)
            )
            try:
                response = self._session.get(
                    url,
                    params=dict(params) if params is not None else None,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept-Encoding": "gzip, deflate",
                        "Accept": accept,
                    },
                    timeout=timeout,
                    stream=True,
                    allow_redirects=False,
                )
            except (requests.RequestException, OSError) as exc:
                raise SecTransportFailure("sec_transport_unavailable") from exc
            try:
                if response.status_code == 429:
                    if attempt == 1:
                        raise SecTransportFailure("sec_rate_limited")
                    retry_after = self._retry_after_seconds(response.headers)
                    self._rate_limit_retries += 1
                    self._sleep(retry_after)
                    continue
                try:
                    body = self._read_bounded(response, effective_max)
                except SecTransportFailure as exc:
                    if budget is not None and exc.code == "sec_response_too_large":
                        raise SecTransportFailure(
                            "sec_request_budget_exhausted"
                        ) from exc
                    raise
                if budget is not None:
                    budget.record_body(len(body))
                return SecResponse(
                    status_code=int(response.status_code),
                    body=body,
                    encoding=str(getattr(response, "encoding", None) or "utf-8"),
                )
            finally:
                response.close()
        raise SecTransportFailure("sec_rate_limited")

    def get_json(self, url: str, **kwargs: Any) -> Any:
        response = self.get(url, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_text(self, url: str, **kwargs: Any) -> str:
        response = self.get(url, **kwargs)
        response.raise_for_status()
        return response.text

    def diagnostics(self, budget: SecRequestBudget) -> dict[str, int]:
        return {
            **budget.diagnostics(),
            "governor_wait_ms": min(_MAX_DIAGNOSTIC_INTEGER, self._governor_wait_ms),
            "rate_limit_retries": min(_MAX_DIAGNOSTIC_INTEGER, self._rate_limit_retries),
        }

    def close(self) -> None:
        close = getattr(self._session, "close", None)
        if callable(close):
            close()
