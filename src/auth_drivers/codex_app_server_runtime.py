"""Bundled-only Codex app-server process and JSONL transport boundary."""

from __future__ import annotations

import base64
import hmac
import json
import os
import re
import selectors
import signal
import subprocess
import tempfile
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar


ALLOWED_CODEX_APP_SERVER_VERSIONS = frozenset({"0.147.0", "0.151.0"})
_VERSION_OUTPUTS = frozenset(
    f"codex-cli {version}" for version in ALLOWED_CODEX_APP_SERVER_VERSIONS
)
_DEFAULT_MAX_REQUEST_BYTES = 64 * 1024
_DEFAULT_MAX_STDOUT_BYTES = 256 * 1024
_DEFAULT_MAX_STDERR_BYTES = 64 * 1024
_T = TypeVar("_T")


class CodexAppServerRuntimeError(RuntimeError):
    """Stable, non-secret app-server runtime failure."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _fail(code: str = "protocol_incompatible") -> CodexAppServerRuntimeError:
    return CodexAppServerRuntimeError(code)


@dataclass(frozen=True)
class CodexAuthenticatedContext:
    account_id: str
    plan_type: str
    codex_home: Path


@dataclass(frozen=True)
class CodexAppServerRuntime:
    launcher: Path
    target: Path
    timeout_seconds: float
    max_request_bytes: int
    max_stdout_bytes: int
    max_stderr_bytes: int


def _validated_positive_budget(value: int, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail("adapter_unavailable")
    if value <= 0 or value > maximum:
        raise _fail("adapter_unavailable")
    return value


def _default_codex_executable() -> Path:
    try:
        from codex_cli_bin import bundled_codex_path

        return Path(bundled_codex_path())
    except (ImportError, FileNotFoundError, OSError):
        raise _fail("adapter_unavailable") from None


def resolve_codex_app_server_runtime(
    *,
    executable: str | Path | None = None,
    timeout_seconds: float = 8.0,
    max_request_bytes: int = _DEFAULT_MAX_REQUEST_BYTES,
    max_stdout_bytes: int = _DEFAULT_MAX_STDOUT_BYTES,
    max_stderr_bytes: int = _DEFAULT_MAX_STDERR_BYTES,
) -> CodexAppServerRuntime:
    """Resolve one explicit or package-bundled executable without PATH lookup."""
    try:
        timeout = float(timeout_seconds)
    except (TypeError, ValueError):
        raise _fail("adapter_unavailable") from None
    if timeout <= 0 or timeout > 7200:
        raise _fail("adapter_unavailable")

    launcher = _default_codex_executable() if executable is None else Path(executable)
    if not launcher.is_absolute():
        raise _fail("adapter_unavailable")
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise _fail("adapter_unavailable")
    target = launcher.resolve()
    if not target.is_file() or not os.access(target, os.X_OK):
        raise _fail("adapter_unavailable")
    return CodexAppServerRuntime(
        launcher=launcher,
        target=target,
        timeout_seconds=timeout,
        max_request_bytes=_validated_positive_budget(
            max_request_bytes, maximum=64 * 1024 * 1024
        ),
        max_stdout_bytes=_validated_positive_budget(
            max_stdout_bytes, maximum=256 * 1024 * 1024
        ),
        max_stderr_bytes=_validated_positive_budget(
            max_stderr_bytes, maximum=16 * 1024 * 1024
        ),
    )


def _isolated_path_entries(launcher: Path, target: Path) -> list[str]:
    entries = [str(launcher.parent)]
    if target.parent != launcher.parent:
        entries.append(str(target.parent))
    if os.name == "nt":
        system_root = os.environ.get("SystemRoot")
        if system_root:
            entries.append(str(Path(system_root) / "System32"))
    else:
        entries.extend(("/usr/bin", "/bin"))
    return entries


def isolated_codex_environment(
    launcher: Path,
    target: Path,
    codex_home: Path,
) -> dict[str, str]:
    """Build a closed child environment containing no provider credentials."""
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
    if os.name == "nt" and os.environ.get("SystemRoot"):
        environment["SystemRoot"] = os.environ["SystemRoot"]
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


def _popen_group_options() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def _process_group_exists(pgid: int) -> bool:
    if os.name == "nt":
        return False
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.stdin is not None:
        try:
            process.stdin.close()
        except OSError:
            pass
    try:
        process.wait(timeout=0.25)
    except subprocess.TimeoutExpired:
        pass

    if process.poll() is None:
        if os.name == "nt":
            process.terminate()
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    if os.name != "nt":
        term_deadline = time.monotonic() + 0.5
        while _process_group_exists(process.pid) and time.monotonic() < term_deadline:
            time.sleep(0.01)
        if _process_group_exists(process.pid):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    elif process.poll() is None:
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            process.kill()
    try:
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        raise _fail("adapter_unavailable") from None
    if os.name != "nt":
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


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _fail("timeout")
    return remaining


def _require_shebang_interpreter(
    target: Path,
    environment: dict[str, str],
) -> None:
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


def _verify_version(
    runtime: CodexAppServerRuntime,
    environment: dict[str, str],
    deadline: float,
) -> None:
    try:
        process = subprocess.Popen(
            [str(runtime.launcher), "--version"],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **_popen_group_options(),
        )
    except OSError:
        raise _fail("adapter_unavailable") from None
    try:
        stdout, stderr = process.communicate(timeout=_remaining(deadline))
    except subprocess.TimeoutExpired:
        terminate_process_group(process)
        raise _fail("timeout") from None
    terminate_process_group(process)
    if process.returncode != 0:
        raise _fail("adapter_unavailable")
    if len(stdout) > 256 or len(stderr) > 4096:
        raise _fail()
    text = stdout.decode("utf-8", errors="replace").strip()
    if not re.fullmatch(r"codex-cli [0-9]+\.[0-9]+\.[0-9]+", text):
        raise _fail()
    if text not in _VERSION_OUTPUTS:
        raise _fail("version_incompatible")


class CodexJsonlSession:
    """One bounded JSONL session with caller-owned notification admission."""

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        *,
        deadline: float,
        allowed_notifications: frozenset[str],
        max_request_bytes: int,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
    ):
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise _fail("adapter_unavailable")
        self.process = process
        self.stdin = process.stdin
        self.stdout = process.stdout
        self.stderr = process.stderr
        self.deadline = deadline
        self.allowed_notifications = allowed_notifications
        self.max_request_bytes = max_request_bytes
        self.max_stdout_bytes = max_stdout_bytes
        self.max_stderr_bytes = max_stderr_bytes
        self.stdout_buffer = bytearray()
        self.stderr_bytes = 0
        self.stdout_bytes = 0
        self._messages: deque[dict[str, Any]] = deque()
        self._notifications: deque[dict[str, Any]] = deque()
        self.selector = selectors.DefaultSelector()
        for stream, label in ((self.stdout, "stdout"), (self.stderr, "stderr")):
            os.set_blocking(stream.fileno(), False)
            self.selector.register(stream, selectors.EVENT_READ, data=label)

    def close(self) -> None:
        self.selector.close()

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._write({"method": method, "params": params or {}})

    def request(
        self,
        request_id: int,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        message: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self._write(message)
        while True:
            response = self._next_message()
            if "method" in response:
                self._notifications.append(response)
                continue
            if response.get("id") != request_id:
                raise _fail()
            if "error" in response or not isinstance(response.get("result"), dict):
                raise _fail()
            return response["result"]

    def next_notification(self) -> dict[str, Any]:
        if self._notifications:
            return self._notifications.popleft()
        message = self._next_message()
        if "method" not in message:
            raise _fail()
        return message

    def _write(self, message: dict[str, Any]) -> None:
        try:
            encoded = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
            if len(encoded) > self.max_request_bytes:
                raise _fail("protocol_resource_exhausted")
            self.stdin.write(encoded)
            self.stdin.flush()
        except (BrokenPipeError, OSError):
            raise _fail("transport_error") from None

    def _next_message(self) -> dict[str, Any]:
        while True:
            if self._messages:
                return self._messages.popleft()
            self._decode_buffered_lines()
            if self._messages:
                continue
            events = self.selector.select(_remaining(self.deadline))
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
                    if self.stderr_bytes > self.max_stderr_bytes:
                        raise _fail("protocol_resource_exhausted")
                    continue
                self.stdout_bytes += len(chunk)
                if self.stdout_bytes > self.max_stdout_bytes:
                    raise _fail("protocol_resource_exhausted")
                self.stdout_buffer.extend(chunk)
                self._decode_buffered_lines()
            if not self.selector.get_map() and self.process.poll() is not None:
                raise _fail("transport_error")

    def _decode_buffered_lines(self) -> None:
        while b"\n" in self.stdout_buffer:
            raw, _, rest = self.stdout_buffer.partition(b"\n")
            self.stdout_buffer = bytearray(rest)
            if not raw:
                continue
            self._messages.append(self._decode_message(raw))

    def _decode_message(self, raw: bytes) -> dict[str, Any]:
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
        if "id" in message or method not in self.allowed_notifications:
            raise _fail()
        if not isinstance(message.get("params", {}), dict):
            raise _fail()
        return message


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


def _validated_account_id(record: Any) -> str:
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


def run_authenticated_codex_operation(
    *,
    record: Any,
    client_name: str,
    timeout_seconds: float,
    executable: str | Path | None,
    allowed_notifications: frozenset[str],
    operation: Callable[[CodexJsonlSession, CodexAuthenticatedContext], _T],
    max_request_bytes: int = _DEFAULT_MAX_REQUEST_BYTES,
    max_stdout_bytes: int = _DEFAULT_MAX_STDOUT_BYTES,
    max_stderr_bytes: int = _DEFAULT_MAX_STDERR_BYTES,
) -> tuple[CodexAuthenticatedContext, _T]:
    """Run one isolated authenticated operation and always reap its process."""
    runtime = resolve_codex_app_server_runtime(
        executable=executable,
        timeout_seconds=timeout_seconds,
        max_request_bytes=max_request_bytes,
        max_stdout_bytes=max_stdout_bytes,
        max_stderr_bytes=max_stderr_bytes,
    )
    if not isinstance(client_name, str) or not re.fullmatch(
        r"[a-z][a-z0-9-]{0,63}", client_name
    ):
        raise _fail("adapter_unavailable")
    account_id = _validated_account_id(record)
    access_token = getattr(record, "access_token", None)
    if not isinstance(access_token, str) or not access_token:
        raise _fail("missing_token")
    requested_plan = getattr(record, "plan_type", None)
    if requested_plan is not None and not isinstance(requested_plan, str):
        raise _fail()

    deadline = time.monotonic() + runtime.timeout_seconds
    with tempfile.TemporaryDirectory(prefix="arkscope-codex-app-server-") as raw_home:
        codex_home = Path(raw_home)
        environment = isolated_codex_environment(
            runtime.launcher,
            runtime.target,
            codex_home,
        )
        _require_shebang_interpreter(runtime.target, environment)
        _verify_version(runtime, environment, deadline)
        try:
            process = subprocess.Popen(
                [str(runtime.launcher), "app-server", "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                **_popen_group_options(),
            )
        except OSError:
            raise _fail("adapter_unavailable") from None

        session: CodexJsonlSession | None = None
        try:
            session = CodexJsonlSession(
                process,
                deadline=deadline,
                allowed_notifications=allowed_notifications,
                max_request_bytes=runtime.max_request_bytes,
                max_stdout_bytes=runtime.max_stdout_bytes,
                max_stderr_bytes=runtime.max_stderr_bytes,
            )
            initialized = session.request(
                1,
                "initialize",
                {
                    "clientInfo": {"name": client_name, "version": "1"},
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
                    "chatgptPlanType": requested_plan,
                },
            )
            if login != {"type": "chatgptAuthTokens"}:
                raise _fail()
            account_result = session.request(
                3,
                "account/read",
                {"refreshToken": False},
            )
            account = account_result.get("account")
            if not isinstance(account, dict) or account.get("type") != "chatgpt":
                raise _fail("account_mismatch")
            plan_type = account.get("planType")
            if not isinstance(plan_type, str) or not plan_type.strip() or len(plan_type) > 80:
                raise _fail("account_plan_unavailable")
            email = account.get("email")
            if email is not None and (
                not isinstance(email, str) or not email or len(email) > 320
            ):
                raise _fail()
            if not isinstance(account_result.get("requiresOpenaiAuth"), bool):
                raise _fail()
            context = CodexAuthenticatedContext(
                account_id=account_id,
                plan_type=plan_type.strip().lower(),
                codex_home=codex_home,
            )
            return context, operation(session, context)
        finally:
            if session is not None:
                session.close()
            terminate_process_group(process)
