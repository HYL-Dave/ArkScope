"""Bounded Codex app-server adapter for ChatGPT account observations."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from src.agents.shared.output_boundary import OutputBoundaryError, OutputGuard
from src.auth_drivers.codex_app_server_runtime import (
    ALLOWED_CODEX_APP_SERVER_VERSIONS,
    CodexAppServerRuntimeError,
    CodexAuthenticatedContext,
    CodexJsonlSession,
    resolve_codex_app_server_runtime,
    run_authenticated_codex_operation,
)

from src.auth_drivers.oauth_status import (
    OAuthAccountObservation,
    OAuthAccountPayload,
    OAuthCreditsSnapshot,
    OAuthDailyUsageBucket,
    OAuthRateLimitSnapshot,
    OAuthRateLimitWindow,
    OAuthSpendControlLimit,
    OAuthUsageSummary,
)


_MAX_STDOUT_BYTES = 256 * 1024
_MAX_STDERR_BYTES = 64 * 1024
_MAX_RATE_LIMIT_BUCKETS = 16
_MAX_MODEL_PAGES = 8
_MAX_MODELS = 256
_ALLOWED_SERVER_NOTIFICATIONS = frozenset(
    {
        "account/login/completed",
        "account/rateLimits/updated",
        "account/updated",
        "remoteControl/status/changed",
    }
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MODEL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:\-]{0,79}$")
_JWT_ID_RE = re.compile(r"([A-Za-z0-9_-]+)\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_EFFORT_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}$")
_INPUT_MODALITIES = frozenset({"text", "image", "audio"})
_T = TypeVar("_T")


@dataclass(frozen=True)
class CodexSubscriptionModel:
    catalog_id: str
    model: str
    display_name: str
    description: str
    hidden: bool
    default_reasoning_effort: str
    supported_reasoning_efforts: tuple[str, ...]
    input_modalities: tuple[str, ...]
    supports_personality: bool
    is_default: bool


class CodexAccountUsageError(RuntimeError):
    """A stable, non-secret account-adapter failure."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _fail(code: str = "protocol_incompatible") -> CodexAccountUsageError:
    return CodexAccountUsageError(code)


def _account_fingerprint(credential_id: str, account_id: str) -> str:
    return hashlib.sha256(f"{credential_id}\0{account_id}".encode("utf-8")).hexdigest()


def _bounded_string(value: Any, *, optional: bool = True, maximum: int = 160) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise _fail()
    return value


def _integer(
    value: Any,
    *,
    optional: bool = True,
    minimum: int = 0,
    maximum: int = 2**63 - 1,
) -> int | None:
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail()
    if value < minimum or value > maximum:
        raise _fail()
    return value


def _boolean(value: Any, *, optional: bool = True) -> bool | None:
    if value is None and optional:
        return None
    if not isinstance(value, bool):
        raise _fail()
    return value


def _object(value: Any, *, optional: bool = False) -> dict[str, Any] | None:
    if value is None and optional:
        return None
    if not isinstance(value, dict):
        raise _fail()
    return value


def _rate_limit_window(value: Any) -> OAuthRateLimitWindow | None:
    row = _object(value, optional=True)
    if row is None:
        return None
    return OAuthRateLimitWindow(
        used_percent=_integer(
            row.get("usedPercent"), optional=False, minimum=0, maximum=100
        ),
        window_duration_minutes=_integer(row.get("windowDurationMins")),
        resets_at=_integer(row.get("resetsAt")),
    )


def _credits(value: Any) -> OAuthCreditsSnapshot | None:
    row = _object(value, optional=True)
    if row is None:
        return None
    balance = row.get("balance")
    if balance is not None:
        balance = _bounded_string(balance, maximum=80)
    return OAuthCreditsSnapshot(
        balance=balance,
        has_credits=_boolean(row.get("hasCredits"), optional=False),
        unlimited=_boolean(row.get("unlimited"), optional=False),
    )


def _spend_control(value: Any) -> OAuthSpendControlLimit | None:
    row = _object(value, optional=True)
    if row is None:
        return None
    return OAuthSpendControlLimit(
        limit=_bounded_string(row.get("limit"), optional=False, maximum=80),
        used=_bounded_string(row.get("used"), optional=False, maximum=80),
        remaining_percent=_integer(
            row.get("remainingPercent"), optional=False, minimum=0, maximum=100
        ),
        resets_at=_integer(row.get("resetsAt"), optional=False),
    )


def _rate_limit_snapshot(value: Any) -> OAuthRateLimitSnapshot:
    row = _object(value)
    assert row is not None
    return OAuthRateLimitSnapshot(
        limit_id=_bounded_string(row.get("limitId")),
        limit_name=_bounded_string(row.get("limitName")),
        plan_type=_bounded_string(row.get("planType")),
        primary=_rate_limit_window(row.get("primary")),
        secondary=_rate_limit_window(row.get("secondary")),
        rate_limit_reached_type=_bounded_string(row.get("rateLimitReachedType")),
        credits=_credits(row.get("credits")),
        individual_limit=_spend_control(row.get("individualLimit")),
        spend_control_reached=_boolean(row.get("spendControlReached")),
    )


def _rate_limits_payload(value: Any) -> tuple[
    OAuthRateLimitSnapshot, dict[str, OAuthRateLimitSnapshot], int | None
]:
    result = _object(value)
    assert result is not None
    primary = _rate_limit_snapshot(result.get("rateLimits"))

    by_id_value = result.get("rateLimitsByLimitId")
    by_id: dict[str, OAuthRateLimitSnapshot] = {}
    if by_id_value is not None:
        by_id_raw = _object(by_id_value)
        assert by_id_raw is not None
        if len(by_id_raw) > _MAX_RATE_LIMIT_BUCKETS:
            raise _fail()
        for key in sorted(by_id_raw):
            safe_key = _bounded_string(key, optional=False, maximum=80)
            bucket = _rate_limit_snapshot(by_id_raw[key])
            if bucket.limit_id is not None and bucket.limit_id != safe_key:
                raise _fail()
            by_id[safe_key] = bucket

    reset_credits = _object(result.get("rateLimitResetCredits"), optional=True)
    available_count = None
    if reset_credits is not None:
        available_count = _integer(
            reset_credits.get("availableCount"), optional=False, maximum=1_000_000
        )
    return primary, by_id, available_count


def _usage_payload(value: Any) -> tuple[OAuthUsageSummary, list[OAuthDailyUsageBucket]]:
    result = _object(value)
    assert result is not None
    summary_raw = _object(result.get("summary"))
    assert summary_raw is not None
    summary = OAuthUsageSummary(
        lifetime_tokens=_integer(summary_raw.get("lifetimeTokens")),
        peak_daily_tokens=_integer(summary_raw.get("peakDailyTokens")),
        longest_running_turn_seconds=_integer(summary_raw.get("longestRunningTurnSec")),
        current_streak_days=_integer(summary_raw.get("currentStreakDays")),
        longest_streak_days=_integer(summary_raw.get("longestStreakDays")),
    )

    daily_value = result.get("dailyUsageBuckets")
    if daily_value is None:
        return summary, []
    if not isinstance(daily_value, list):
        raise _fail()
    daily: list[OAuthDailyUsageBucket] = []
    for value_row in daily_value:
        row = _object(value_row)
        assert row is not None
        start_date = _bounded_string(row.get("startDate"), optional=False, maximum=10)
        if not _DATE_RE.fullmatch(start_date):
            raise _fail()
        daily.append(
            OAuthDailyUsageBucket(
                start_date=start_date,
                tokens=_integer(row.get("tokens"), optional=False),
            )
        )
    return summary, daily


def _model_identifier(value: Any) -> str:
    model = _bounded_string(value, optional=False, maximum=80)
    assert model is not None
    if not _MODEL_ID_RE.fullmatch(model):
        raise _fail()
    # A JWT is not a model ID; ordinary long/dotted identifiers remain valid.
    jwt = _JWT_ID_RE.fullmatch(model)
    if jwt is not None:
        header = jwt.group(1)
        try:
            decoded = json.loads(base64.b64decode(
                header + "=" * (-len(header) % 4), altchars=b"-_", validate=True,
            ))
        except (ValueError, UnicodeError):
            decoded = None
        if isinstance(decoded, dict) and isinstance(decoded.get("alg"), str):
            raise _fail()
    return model


def _display_string(value: Any, *, maximum: int) -> str:
    text = _bounded_string(value, optional=False, maximum=maximum)
    assert text is not None
    if any(ord(char) < 32 for char in text) or "@" in text:
        raise _fail()
    return text


def _model_catalog_page(
    value: Any,
) -> tuple[list[CodexSubscriptionModel], str | None]:
    result = _object(value)
    assert result is not None
    data = result.get("data")
    if not isinstance(data, list) or len(data) > _MAX_MODELS:
        raise _fail()
    models: list[CodexSubscriptionModel] = []
    for value_row in data:
        row = _object(value_row)
        assert row is not None
        efforts_raw = row.get("supportedReasoningEfforts")
        if not isinstance(efforts_raw, list) or len(efforts_raw) > 8:
            raise _fail()
        efforts: list[str] = []
        for value_effort in efforts_raw:
            effort_row = _object(value_effort)
            assert effort_row is not None
            effort = _bounded_string(
                effort_row.get("reasoningEffort"), optional=False, maximum=32
            )
            assert effort is not None
            if not _EFFORT_RE.fullmatch(effort) or effort in efforts:
                raise _fail()
            _display_string(effort_row.get("description"), maximum=240)
            efforts.append(effort)

        default_effort = _bounded_string(
            row.get("defaultReasoningEffort"), optional=False, maximum=32
        )
        assert default_effort is not None
        if not _EFFORT_RE.fullmatch(default_effort):
            raise _fail()
        if efforts and default_effort not in efforts:
            raise _fail()

        modalities_raw = row.get("inputModalities", ["text", "image"])
        if not isinstance(modalities_raw, list) or len(modalities_raw) > 3:
            raise _fail()
        modalities: list[str] = []
        for modality in modalities_raw:
            if (
                not isinstance(modality, str)
                or modality not in _INPUT_MODALITIES
                or modality in modalities
            ):
                raise _fail()
            modalities.append(modality)

        supports_personality = row.get("supportsPersonality", False)
        if not isinstance(supports_personality, bool):
            raise _fail()
        models.append(
            CodexSubscriptionModel(
                catalog_id=_model_identifier(row.get("id")),
                model=_model_identifier(row.get("model")),
                display_name=_display_string(row.get("displayName"), maximum=160),
                description=_display_string(row.get("description"), maximum=1000),
                hidden=_boolean(row.get("hidden"), optional=False),
                default_reasoning_effort=default_effort,
                supported_reasoning_efforts=tuple(efforts),
                input_modalities=tuple(modalities),
                supports_personality=supports_personality,
                is_default=_boolean(row.get("isDefault"), optional=False),
            )
        )
    cursor = _bounded_string(result.get("nextCursor"), maximum=512)
    return models, cursor


def _observed_at(value: str | datetime | None) -> str:
    if value is None:
        current = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        current = value
    elif isinstance(value, str):
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            current = datetime.fromisoformat(normalized)
        except ValueError:
            raise _fail() from None
    else:
        raise _fail()
    if current.tzinfo is None:
        raise _fail()
    return current.astimezone(timezone.utc).isoformat(timespec="seconds")


class CodexAccountUsageAdapter:
    """Read bounded account or model-catalog data without starting a thread or turn."""

    def __init__(
        self,
        *,
        executable: str | Path | None = None,
        timeout_seconds: float = 8.0,
    ):
        try:
            timeout = float(timeout_seconds)
        except (TypeError, ValueError):
            raise _fail("adapter_unavailable") from None
        if timeout <= 0 or timeout > 30:
            raise _fail("adapter_unavailable")
        self.timeout_seconds = timeout
        if executable is None:
            try:
                runtime = resolve_codex_app_server_runtime(
                    timeout_seconds=timeout,
                    max_stdout_bytes=_MAX_STDOUT_BYTES,
                    max_stderr_bytes=_MAX_STDERR_BYTES,
                )
            except CodexAppServerRuntimeError as exc:
                raise _fail(exc.code) from None
            self.executable: str | Path = runtime.launcher
        else:
            self.executable = executable

    def _resolve_launcher_and_target(self) -> tuple[Path, Path]:
        try:
            runtime = resolve_codex_app_server_runtime(
                executable=self.executable,
                timeout_seconds=self.timeout_seconds,
                max_stdout_bytes=_MAX_STDOUT_BYTES,
                max_stderr_bytes=_MAX_STDERR_BYTES,
            )
        except CodexAppServerRuntimeError as exc:
            raise _fail(exc.code) from None
        return runtime.launcher, runtime.target

    def _run_authenticated(
        self,
        *,
        record,
        operation: Callable[[CodexJsonlSession], _T],
    ) -> tuple[CodexAuthenticatedContext, _T]:
        """Run one bounded read against an isolated, credential-bound app-server."""
        try:
            context, result = run_authenticated_codex_operation(
                record=record,
                client_name="arkscope-account-observer",
                timeout_seconds=self.timeout_seconds,
                executable=self.executable,
                allowed_notifications=_ALLOWED_SERVER_NOTIFICATIONS,
                max_stdout_bytes=_MAX_STDOUT_BYTES,
                max_stderr_bytes=_MAX_STDERR_BYTES,
                operation=lambda session, _context: operation(session),
            )
        except CodexAppServerRuntimeError as exc:
            raise _fail(exc.code) from None
        return context, result

    def read_account_usage_with_plan(
        self,
        *,
        credential_id: str,
        record,
        observed_at: str | datetime | None = None,
    ) -> tuple[OAuthAccountObservation, str | None]:
        def read(session: CodexJsonlSession):
            rate_limits_result = session.request(4, "account/rateLimits/read")
            usage_result = session.request(5, "account/usage/read")
            rate_limits, by_id, reset_count = _rate_limits_payload(rate_limits_result)
            usage_summary, daily = _usage_payload(usage_result)
            return rate_limits, by_id, reset_count, usage_summary, daily

        context, values = self._run_authenticated(record=record, operation=read)
        rate_limits, by_id, reset_count, usage_summary, daily = values
        observation = OAuthAccountObservation(
            account_fingerprint=_account_fingerprint(
                credential_id, context.account_id
            ),
            source="codex_app_server",
            schema_version=1,
            observed_at=_observed_at(observed_at),
            status="available",
            payload=OAuthAccountPayload(
                rate_limits=rate_limits,
                rate_limits_by_limit_id=by_id,
                reset_credits_available=reset_count,
                usage_summary=usage_summary,
                daily_usage_buckets=daily,
            ),
        )
        return observation, context.plan_type

    def read_account_usage(
        self,
        *,
        credential_id: str,
        record,
        observed_at: str | datetime | None = None,
    ) -> OAuthAccountObservation:
        observation, _ = self.read_account_usage_with_plan(
            credential_id=credential_id,
            record=record,
            observed_at=observed_at,
        )
        return observation

    def read_model_catalog_with_plan(
        self, *, record
    ) -> tuple[list[CodexSubscriptionModel], str | None]:
        guard = OutputGuard()

        def read(session: CodexJsonlSession) -> list[CodexSubscriptionModel]:
            # Authentication has validated this supplied record; do not look up
            # another credential or borrow an unrelated research execution.
            guard.add_secret(record.access_token)
            guard.add_secret(record.refresh_token)
            guard.add_secret(record.metadata.get("id_token"))
            cursor: str | None = None
            seen_cursors: set[str] = set()
            models: list[CodexSubscriptionModel] = []
            seen_models: set[str] = set()
            for page_index in range(_MAX_MODEL_PAGES):
                result = session.request(
                    4 + page_index,
                    "model/list",
                    {"cursor": cursor, "includeHidden": False, "limit": 100},
                )
                guard.check(result)
                page, next_cursor = _model_catalog_page(result)
                for model in page:
                    if model.model in seen_models:
                        raise _fail()
                    seen_models.add(model.model)
                    if not model.hidden:
                        models.append(model)
                if len(models) > _MAX_MODELS:
                    raise _fail()
                if next_cursor is None:
                    return models
                if next_cursor in seen_cursors:
                    raise _fail()
                seen_cursors.add(next_cursor)
                cursor = next_cursor
            raise _fail()

        try:
            context, models = self._run_authenticated(record=record, operation=read)
            guard.check(context.plan_type)
        except OutputBoundaryError:
            raise _fail() from None
        if not models:
            raise _fail()
        return models, context.plan_type

    def read_model_catalog(self, *, record) -> list[CodexSubscriptionModel]:
        models, _ = self.read_model_catalog_with_plan(record=record)
        return models
