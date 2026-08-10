"""Manual Anthropic subscription-quota adapter.

One explicit, user-triggered Messages request against the OAuth wire shape
proven live on 2026-08-09 (`auth_token` + `oauth-2025-04-20` beta + the exact
Claude Code identity system block). The unified rate-limit response headers
are the only payload consumed; the generated body is discarded. This module
is account telemetry only — it is not a research transport, never runs
automatically, and never touches the passive RateLimitEvent path.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Callable

import anthropic

from src.auth_drivers.oauth_status import (
    OAuthAccountObservation,
    OAuthAccountPayload,
    OAuthRateLimitSnapshot,
    OAuthRateLimitWindow,
    OAuthUsageSummary,
)

PROBE_MODEL = "claude-sonnet-5"
PROBE_MAX_TOKENS = 8
PROBE_OAUTH_BETA = "oauth-2025-04-20"
PROBE_IDENTITY_BLOCK = "You are Claude Code, Anthropic's official CLI for Claude."
PROBE_USER_MESSAGE = "Reply with exactly: OK"
PROBE_TIMEOUT_SECONDS = 20.0

_HEADER_PREFIX = "anthropic-ratelimit-unified"
_STATUS_VALUES = ("allowed", "allowed_warning", "rejected")
_REASON_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")
_CLAIM_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")


class AnthropicAccountUsageError(Exception):
    """Typed adapter failure; the code is the entire externally visible detail."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> AnthropicAccountUsageError:
    return AnthropicAccountUsageError(code)


def _default_client_factory(token: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(
        auth_token=token,
        api_key=None,
        timeout=PROBE_TIMEOUT_SECONDS,
        max_retries=0,
    )


def _fingerprint(credential_id: str) -> str:
    return hashlib.sha256(
        f"anthropic\0claude_code_oauth\0{credential_id}".encode("utf-8")
    ).hexdigest()


def _utilization_percent(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if not (value == value and 0.0 <= value <= 1.0):
        return None
    return round(value * 100.0, 4)


def _unix_seconds(raw: str | None) -> int | None:
    if raw is None or not re.fullmatch(r"[0-9]{1,12}", raw):
        return None
    return int(raw)


def _status_value(raw: str | None):
    return raw if raw in _STATUS_VALUES else None

def _window(headers: Any, key: str, duration_minutes: int) -> OAuthRateLimitWindow:
    return OAuthRateLimitWindow(
        used_percent=_utilization_percent(headers.get(f"{_HEADER_PREFIX}-{key}-utilization")),
        window_duration_minutes=duration_minutes,
        resets_at=_unix_seconds(headers.get(f"{_HEADER_PREFIX}-{key}-reset")),
    )


def _snapshot_from_headers(headers: Any) -> OAuthRateLimitSnapshot:
    reason = headers.get(f"{_HEADER_PREFIX}-overage-disabled-reason")
    if reason is not None and not _REASON_PATTERN.fullmatch(reason):
        reason = None
    claim = headers.get(f"{_HEADER_PREFIX}-representative-claim")
    if claim is not None and not _CLAIM_PATTERN.fullmatch(claim):
        claim = None
    return OAuthRateLimitSnapshot(
        limit_id=claim,
        primary=_window(headers, "5h", 300),
        secondary=_window(headers, "7d", 10080),
        status=_status_value(headers.get(f"{_HEADER_PREFIX}-status")),
        overage_status=_status_value(headers.get(f"{_HEADER_PREFIX}-overage-status")),
        overage_disabled_reason=reason,
    )


def _admit_quota_snapshot(
    headers: Any, *, require_rejected: bool
) -> OAuthRateLimitSnapshot:
    """Fail-closed on the unified AUTHORITY only: the overall
    ``anthropic-ratelimit-unified-status`` must be present and valid (and a
    quota-rejected response must actually say ``rejected``). Individual
    window and auxiliary fields stay None when absent or malformed — a
    missing field is unknown, not a reason to drop the whole observation
    (plan §1.2 / design LD 7)."""
    if headers is None:
        raise _fail("quota_headers_unavailable")
    snapshot = _snapshot_from_headers(headers)
    if snapshot.status is None:
        raise _fail("quota_headers_unavailable")
    if require_rejected and snapshot.status != "rejected":
        raise _fail("quota_headers_unavailable")
    return snapshot


class AnthropicAccountUsageAdapter:
    """One bounded Messages request; unified headers in, typed outcome out."""

    def __init__(
        self,
        *,
        client_factory: Callable[[str], Any] | None = None,
    ):
        self._client_factory = client_factory or _default_client_factory

    def read_account_usage(
        self,
        *,
        credential_id: str,
        record,
        observed_at: str | None = None,
    ) -> OAuthAccountObservation:
        access_token = getattr(record, "access_token", None)
        if not isinstance(access_token, str) or not access_token:
            raise _fail("missing_token")
        if observed_at is not None and not isinstance(observed_at, str):
            raise _fail("adapter_unavailable")

        try:
            client = self._client_factory(access_token)
        except TypeError:
            raise _fail("sdk_incompatible") from None
        except Exception:  # noqa: BLE001 - construction diagnostics stay internal
            raise _fail("adapter_unavailable") from None

        try:
            raw_surface = getattr(
                getattr(client, "messages", None), "with_raw_response", None
            )
            create = getattr(raw_surface, "create", None)
            if not callable(create):
                raise _fail("sdk_incompatible")

            try:
                response = create(
                    model=PROBE_MODEL,
                    max_tokens=PROBE_MAX_TOKENS,
                    system=[{"type": "text", "text": PROBE_IDENTITY_BLOCK}],
                    messages=[{"role": "user", "content": PROBE_USER_MESSAGE}],
                    extra_headers={"anthropic-beta": PROBE_OAUTH_BETA},
                )
            except anthropic.APITimeoutError:
                raise _fail("timeout") from None
            except anthropic.APIConnectionError:
                raise _fail("transport_error") from None
            except anthropic.APIStatusError as error:
                status_code = getattr(
                    getattr(error, "response", None), "status_code", None
                )
                if status_code == 401:
                    raise _fail("provider_auth_rejected") from None
                if status_code == 403:
                    raise _fail("provider_access_rejected") from None
                if status_code == 429:
                    headers = getattr(
                        getattr(error, "response", None), "headers", None
                    )
                    snapshot = _admit_quota_snapshot(headers, require_rejected=True)
                    return self._observation(credential_id, observed_at, snapshot)
                if status_code is not None and 400 <= status_code < 500:
                    raise _fail("provider_request_rejected") from None
                raise _fail("adapter_unavailable") from None
            except AnthropicAccountUsageError:
                raise
            except Exception:  # noqa: BLE001 - never expose SDK/transport internals
                raise _fail("adapter_unavailable") from None

            snapshot = _admit_quota_snapshot(
                getattr(response, "headers", None), require_rejected=False
            )
            return self._observation(credential_id, observed_at, snapshot)
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001 - cleanup never masks the outcome
                    pass

    def _observation(
        self,
        credential_id: str,
        observed_at: str | None,
        rate_limits: OAuthRateLimitSnapshot,
    ) -> OAuthAccountObservation:
        if observed_at is None:
            # Receipt time: stamped only after the unified headers were
            # received and admitted, never before the request.
            observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return OAuthAccountObservation(
            account_fingerprint=_fingerprint(credential_id),
            source="anthropic_oauth_probe",
            observed_at=observed_at,
            payload=OAuthAccountPayload(
                rate_limits=rate_limits,
                usage_summary=OAuthUsageSummary(),
            ),
        )
