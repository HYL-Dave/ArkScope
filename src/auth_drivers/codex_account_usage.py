"""Bounded Codex app-server adapter for ChatGPT account observations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


ALLOWED_CODEX_APP_SERVER_VERSION = "0.147.0"
_VERSION_OUTPUT = f"codex-cli {ALLOWED_CODEX_APP_SERVER_VERSION}"
_MAX_STDOUT_BYTES = 256 * 1024
_MAX_STDERR_BYTES = 64 * 1024
_MAX_RATE_LIMIT_BUCKETS = 16
_MAX_DAILY_USAGE_BUCKETS = 31
_ALLOWED_SERVER_NOTIFICATIONS = frozenset(
    {
        "account/login/completed",
        "account/rateLimits/updated",
        "account/updated",
        "remoteControl/status/changed",
    }
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CodexAccountUsageError(RuntimeError):
    """A stable, non-secret account-adapter failure."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _fail(code: str = "protocol_incompatible") -> CodexAccountUsageError:
    return CodexAccountUsageError(code)


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise _fail("account_identity_unavailable")
    encoded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded))
    except (ValueError, TypeError, json.JSONDecodeError):
        raise _fail("account_identity_unavailable") from None
    if not isinstance(payload, dict):
        raise _fail("account_identity_unavailable")
    return payload


def _validated_account_id(record) -> str:
    metadata = getattr(record, "metadata", None)
    if not isinstance(metadata, dict):
        raise _fail("account_identity_unavailable")
    account_id = metadata.get("account_id")
    id_token = metadata.get("id_token")
    if not isinstance(account_id, str) or not account_id or len(account_id) > 512:
        raise _fail("account_identity_unavailable")
    if not isinstance(id_token, str) or not id_token:
        raise _fail("account_identity_unavailable")
    payload = _decode_jwt_payload(id_token)
    auth = payload.get("https://api.openai.com/auth")
    claimed_id = auth.get("chatgpt_account_id") if isinstance(auth, dict) else None
    if not isinstance(claimed_id, str) or not claimed_id:
        raise _fail("account_identity_unavailable")
    if not hmac.compare_digest(account_id, claimed_id):
        raise _fail("account_mismatch")
    return account_id


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
    if not isinstance(daily_value, list) or len(daily_value) > _MAX_DAILY_USAGE_BUCKETS:
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


def _isolated_path_entries(launcher: Path, target: Path) -> list[str]:
    """Launcher directory first, resolved-target directory when different,
    then the reviewed system directories. The launcher stays the spawn path;
    an ``#!/usr/bin/env`` interpreter that ships beside the launcher (the
    NVM/npm layout) must stay reachable after symlink inspection."""
    entries = [str(launcher.parent)]
    if target.parent != launcher.parent:
        entries.append(str(target.parent))
    entries.extend(("/usr/bin", "/bin"))
    return entries


def _isolated_environment(
    launcher: Path, target: Path, codex_home: Path
) -> dict[str, str]:
    environment: dict[str, str] = {
        "CODEX_HOME": str(codex_home),
        "HOME": str(codex_home),
        "XDG_CACHE_HOME": str(codex_home / "cache"),
        "XDG_CONFIG_HOME": str(codex_home / "config"),
        "XDG_DATA_HOME": str(codex_home / "data"),
        "TMPDIR": str(codex_home / "tmp"),
        "PATH": os.pathsep.join(_isolated_path_entries(launcher, target)),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "TZ": "UTC",
    }
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    ):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    for directory in ("cache", "config", "data", "tmp"):
        (codex_home / directory).mkdir(mode=0o700)
    return environment


def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.stdin is not None:
        try:
            process.stdin.close()
        except OSError:
            pass
    try:
        process.wait(timeout=0.25)
    except subprocess.TimeoutExpired:
        pass

    if _process_group_exists(process.pid):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    term_deadline = time.monotonic() + 0.5
    while _process_group_exists(process.pid) and time.monotonic() < term_deadline:
        time.sleep(0.01)
    if _process_group_exists(process.pid):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        raise _fail("adapter_unavailable") from None
    kill_deadline = time.monotonic() + 0.5
    while _process_group_exists(process.pid) and time.monotonic() < kill_deadline:
        time.sleep(0.01)
    if _process_group_exists(process.pid):
        raise _fail("adapter_unavailable")
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


class _JsonlSession:
    def __init__(self, process: subprocess.Popen[bytes], *, timeout_seconds: float):
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise _fail("adapter_unavailable")
        self.process = process
        self.stdin = process.stdin
        self.stdout = process.stdout
        self.stderr = process.stderr
        self.timeout_seconds = timeout_seconds
        self.stdout_buffer = bytearray()
        self.stderr_bytes = 0
        self.stdout_bytes = 0
        self.selector = selectors.DefaultSelector()
        for stream, label in ((self.stdout, "stdout"), (self.stderr, "stderr")):
            os.set_blocking(stream.fileno(), False)
            self.selector.register(stream, selectors.EVENT_READ, data=label)

    def close(self) -> None:
        self.selector.close()

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._write({"method": method, "params": params or {}})

    def request(
        self, request_id: int, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        message: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self._write(message)
        return self._wait_for_response(request_id)

    def _write(self, message: dict[str, Any]) -> None:
        try:
            encoded = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
            if len(encoded) > 64 * 1024:
                raise _fail()
            self.stdin.write(encoded)
            self.stdin.flush()
        except (BrokenPipeError, OSError):
            raise _fail("transport_error") from None

    def _wait_for_response(self, request_id: int) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _fail("timeout")
            events = self.selector.select(remaining)
            if not events:
                raise _fail("timeout")
            for key, _ in events:
                stream = key.fileobj
                try:
                    chunk = os.read(stream.fileno(), 16 * 1024)
                except BlockingIOError:
                    continue
                if not chunk:
                    self.selector.unregister(stream)
                    continue
                if key.data == "stderr":
                    self.stderr_bytes += len(chunk)
                    if self.stderr_bytes > _MAX_STDERR_BYTES:
                        raise _fail()
                    continue
                self.stdout_bytes += len(chunk)
                if self.stdout_bytes > _MAX_STDOUT_BYTES:
                    raise _fail()
                self.stdout_buffer.extend(chunk)
                while b"\n" in self.stdout_buffer:
                    raw, _, rest = self.stdout_buffer.partition(b"\n")
                    self.stdout_buffer = bytearray(rest)
                    if not raw:
                        continue
                    response = self._decode_message(raw)
                    if response is None:
                        continue
                    response_id = response.get("id")
                    if response_id != request_id:
                        raise _fail()
                    if "error" in response or not isinstance(response.get("result"), dict):
                        raise _fail("protocol_incompatible")
                    return response["result"]
            if not self.selector.get_map() and self.process.poll() is not None:
                raise _fail("transport_error")

    @staticmethod
    def _decode_message(raw: bytes) -> dict[str, Any] | None:
        try:
            message = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise _fail() from None
        if not isinstance(message, dict):
            raise _fail()
        method = message.get("method")
        if method is None:
            return message
        if not isinstance(method, str):
            raise _fail()
        if method.startswith(("thread/", "turn/")):
            raise _fail()
        if method not in _ALLOWED_SERVER_NOTIFICATIONS or "id" in message:
            raise _fail()
        if not isinstance(message.get("params", {}), dict):
            raise _fail()
        return None


class CodexAccountUsageAdapter:
    """Read one account snapshot without starting a model thread or turn."""

    def __init__(
        self,
        *,
        executable: str | Path = "codex",
        timeout_seconds: float = 8.0,
    ):
        self.executable = executable
        try:
            timeout = float(timeout_seconds)
        except (TypeError, ValueError):
            raise _fail("adapter_unavailable") from None
        if timeout <= 0 or timeout > 30:
            raise _fail("adapter_unavailable")
        self.timeout_seconds = timeout

    def _resolve_launcher_and_target(self) -> tuple[Path, Path]:
        """The launcher (which()/explicit path, symlinks preserved) is what we
        spawn; the resolved target is inspected only. Resolving before spawn
        broke NVM installs: ``bin/codex -> ../lib/.../codex.js`` lost the
        ``bin`` directory that owns ``node``."""
        value = str(self.executable)
        resolved = shutil.which(value) if os.sep not in value else value
        if not resolved:
            raise _fail("adapter_unavailable")
        launcher = Path(resolved)
        if not launcher.is_file() or not os.access(launcher, os.X_OK):
            raise _fail("adapter_unavailable")
        target = launcher.resolve()
        if not target.is_file() or not os.access(target, os.X_OK):
            raise _fail("adapter_unavailable")
        return launcher, target

    def _require_shebang_interpreter(
        self, target: Path, environment: dict[str, str]
    ) -> None:
        """For an ``#!`` target, prove the interpreter is reachable inside the
        isolated PATH before spawning; a missing interpreter is a typed
        environment fact, not version skew."""
        try:
            with target.open("rb") as handle:
                first_line = handle.readline(4096)
        except OSError:
            raise _fail("adapter_unavailable") from None
        if not first_line.startswith(b"#!"):
            return
        tokens = first_line[2:].decode("utf-8", errors="replace").strip().split()
        if not tokens:
            raise _fail("interpreter_unavailable")
        interpreter = tokens[0]
        if Path(interpreter).name == "env":
            if len(tokens) < 2:
                raise _fail("interpreter_unavailable")
            name = tokens[1]
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", name):
                raise _fail("interpreter_unavailable")
            for entry in environment["PATH"].split(os.pathsep):
                candidate = Path(entry) / name
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return
            raise _fail("interpreter_unavailable")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", Path(interpreter).name):
            raise _fail("interpreter_unavailable")
        if not (Path(interpreter).is_file() and os.access(interpreter, os.X_OK)):
            raise _fail("interpreter_unavailable")

    def _verify_version(self, launcher: Path, environment: dict[str, str]) -> None:
        try:
            process = subprocess.Popen(
                [str(launcher), "--version"],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError:
            raise _fail("adapter_unavailable") from None
        try:
            stdout, stderr = process.communicate(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            _terminate_process_group(process)
            raise _fail("adapter_unavailable") from None
        _terminate_process_group(process)
        if process.returncode != 0:
            raise _fail("adapter_unavailable")
        if len(stdout) > 256 or len(stderr) > 4096:
            raise _fail("protocol_incompatible")
        text = stdout.decode("utf-8", errors="replace").strip()
        if not re.fullmatch(r"codex-cli [0-9]+\.[0-9]+\.[0-9]+", text):
            raise _fail("protocol_incompatible")
        if text != _VERSION_OUTPUT:
            raise _fail("version_incompatible")

    def read_account_usage(
        self,
        *,
        credential_id: str,
        record,
        observed_at: str | datetime | None = None,
    ) -> OAuthAccountObservation:
        account_id = _validated_account_id(record)
        access_token = getattr(record, "access_token", None)
        if not isinstance(access_token, str) or not access_token:
            raise _fail("missing_token")
        plan_type = getattr(record, "plan_type", None)
        if plan_type is not None and not isinstance(plan_type, str):
            raise _fail()

        launcher, target = self._resolve_launcher_and_target()
        with tempfile.TemporaryDirectory(prefix="arkscope-codex-account-") as raw_home:
            codex_home = Path(raw_home)
            environment = _isolated_environment(launcher, target, codex_home)
            self._require_shebang_interpreter(target, environment)
            self._verify_version(launcher, environment)
            try:
                process = subprocess.Popen(
                    [str(launcher), "app-server", "--stdio"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=environment,
                    start_new_session=True,
                )
            except OSError:
                raise _fail("adapter_unavailable") from None

            session: _JsonlSession | None = None
            try:
                session = _JsonlSession(process, timeout_seconds=self.timeout_seconds)
                initialized = session.request(
                    1,
                    "initialize",
                    {
                        "clientInfo": {
                            "name": "arkscope-account-observer",
                            "version": "1",
                        },
                        "capabilities": {"experimentalApi": True},
                    },
                )
                if initialized.get("codexHome") != str(codex_home):
                    raise _fail()
                session.notify("initialized")
                login = session.request(
                    2,
                    "account/login/start",
                    {
                        "type": "chatgptAuthTokens",
                        "accessToken": access_token,
                        "chatgptAccountId": account_id,
                        "chatgptPlanType": plan_type,
                    },
                )
                if login != {"type": "chatgptAuthTokens"}:
                    raise _fail()
                account = session.request(3, "account/read", {"refreshToken": False})
                account_row = _object(account.get("account"))
                if account_row is None or account_row.get("type") != "chatgpt":
                    raise _fail("account_mismatch")
                _bounded_string(account_row.get("planType"), optional=False, maximum=80)
                email = account_row.get("email")
                if email is not None:
                    _bounded_string(email, maximum=320)
                _boolean(account.get("requiresOpenaiAuth"), optional=False)
                rate_limits_result = session.request(4, "account/rateLimits/read")
                usage_result = session.request(5, "account/usage/read")
                rate_limits, by_id, reset_count = _rate_limits_payload(rate_limits_result)
                usage_summary, daily = _usage_payload(usage_result)
            finally:
                if session is not None:
                    session.close()
                _terminate_process_group(process)

        return OAuthAccountObservation(
            account_fingerprint=_account_fingerprint(credential_id, account_id),
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
