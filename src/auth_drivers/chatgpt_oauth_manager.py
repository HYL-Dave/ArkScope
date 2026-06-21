"""S3 thin-transport — OAuthLoginManager.

Orchestrates the in-app ChatGPT OAuth login over the pure core (chatgpt_oauth_login)
and the ephemeral loopback server (chatgpt_oauth_callback_server):

  begin()           → mint state+PKCE, bind the loopback callback server, return the
                      authorize URL, and spawn a background thread that waits for the
                      redirect and completes the login (exchange + store). Binding before
                      returning avoids a fast-browser redirect race.
  status(state)     → poll: pending | success | error (+ masked credential / detail).
  complete_manual() → the copy-code fallback: complete the SAME login from a pasted code
                      (cancels the still-waiting loopback). Used ONLY when the localhost
                      callback never arrived — it changes how the code is delivered, not
                      the auth mode, the store, or the validation.

Results carry MASKED metadata only — the token lands in the token-store via the core's
complete_login and never appears in a status/result payload. State is single-use (CSRF):
the loopback thread and a manual paste race to pop it; exactly one wins, so the token
exchange never runs twice. A completed 'success' is sticky — a late loopback timeout or a
cancelled wait can never clobber it.

This is the server-side glue for the FastAPI routes (a singleton per process); the routes
are thin wrappers used by the Settings UI.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .chatgpt_oauth_callback_server import LoopbackCallbackServer
from .chatgpt_oauth_login import ChatGPTOAuthLoginError, _StateStore, complete_login, start_login

_DEFAULT_TIMEOUT = 120.0
_RESULT_TTL = timedelta(minutes=15)  # evict a settled (success/error) result after this
_RESULT_CAP = 256  # hard cap on retained results (oldest terminal dropped first)


class OAuthLoginManager:
    def __init__(
        self,
        *,
        credential_store: Any,
        token_store: Any,
        server_factory: Callable[[str], Any] | None = None,
        exchange: Callable[..., dict] | None = None,
        clock: Callable[[], datetime] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        alias: str = "ChatGPT subscription",
        result_ttl: timedelta = _RESULT_TTL,
        result_cap: int = _RESULT_CAP,
    ) -> None:
        self._cs = credential_store
        self._ts = token_store
        self._state_store = _StateStore()
        # factory receives the minted state (the real LoopbackCallbackServer ignores it;
        # tests use it to echo the expected state back without a real port).
        self._server_factory = server_factory or (lambda _state: LoopbackCallbackServer())
        self._exchange = exchange
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout = timeout
        self._alias = alias
        self._result_ttl = result_ttl
        self._result_cap = result_cap
        self._results: dict[str, dict] = {}
        self._result_ts: dict[str, datetime] = {}  # state -> last-update time (for eviction)
        self._servers: dict[str, Any] = {}
        self._lock = threading.Lock()

    def begin(self, make_active: bool = False) -> dict:
        """Start a login. Returns {auth_url, state, expires_at, manual_code_supported}.
        make_active (carried through the pending state to the loopback callback) decides
        whether the resulting credential becomes the active one on completion. Default
        FALSE (unified-activation policy): callers opt in to switching the active one."""
        now = self._clock()
        started = start_login(state_store=self._state_store, now=now, make_active=make_active)
        state = started["state"]
        server = self._server_factory(state)
        with self._lock:
            self._prune_locked(now)  # bound the singleton's in-memory result history
            self._results[state] = {"status": "pending", "credential": None, "detail": None}
            self._result_ts[state] = now
        try:
            # Bind before returning auth_url. A fast browser redirect can otherwise
            # hit localhost:1455 before the background thread starts listening.
            server.start()
        except ChatGPTOAuthLoginError as exc:
            self._finish(state, status="error", detail=str(exc))
            return started
        with self._lock:
            self._servers[state] = server
        threading.Thread(target=self._await_callback, args=(state, server), daemon=True).start()
        return started

    def status(self, state: str) -> dict:
        with self._lock:
            return dict(self._results.get(state, {"status": "unknown", "credential": None, "detail": None}))

    def cancel_login(self, state: str) -> None:
        """Cancel an in-flight login. EVICT the pending state FIRST — so a late loopback
        callback's complete_login pops None → raises → no credential is created — then
        tear down the loopback server (frees :1455). Idempotent; unknown state = no-op."""
        self._state_store.discard(state)  # the key fix: close the late-callback gap
        self._finish(state, status="error", detail="login cancelled")
        self._cancel(state)  # mark cancelled + server.cancel() to unblock wait_for_code

    def complete_manual(self, *, state: str, code: str) -> dict:
        """Copy-code fallback: complete the SAME login from a pasted code. Raises on a
        bad/expired/forged state (the route maps that to a 4xx) — never a fallback."""
        credential = self._complete(state=state, code=code)
        self._finish(state, status="success", credential=credential)
        self._cancel(state)  # unblock + free the still-waiting loopback
        return credential

    # --- internal ---------------------------------------------------------
    def _await_callback(self, state: str, server: Any) -> None:
        try:
            code, recv_state = server.wait_for_code(self._timeout)
            credential = self._complete(state=recv_state or state, code=code)
            self._finish(state, status="success", credential=credential)
        except ChatGPTOAuthLoginError as exc:
            self._finish(state, status="error", detail=str(exc))
        finally:
            self._drop_server(state)

    def _complete(self, *, state: str, code: str) -> dict:
        return complete_login(
            state=state, code=code, credential_store=self._cs, token_store=self._ts,
            alias=self._alias, state_store=self._state_store, now=self._clock(), exchange=self._exchange,
        )

    def _finish(self, state: str, *, status: str, credential: dict | None = None, detail: str | None = None) -> None:
        with self._lock:
            cur = self._results.get(state)
            if cur and cur.get("status") == "success":
                return  # sticky: a completed login is never clobbered (e.g. a late loopback timeout/cancel)
            self._results[state] = {"status": status, "credential": credential, "detail": detail}
            self._result_ts[state] = self._clock()

    def _cancel(self, state: str) -> None:
        """Ask the loopback for `state` to abandon."""
        with self._lock:
            server = self._servers.get(state)
        if server is not None:
            try:
                server.cancel()
            except Exception:  # noqa: BLE001
                pass

    def _drop_server(self, state: str) -> None:
        with self._lock:
            server = self._servers.pop(state, None)
        self._close(server)

    @staticmethod
    def _close(server: Any) -> None:
        if server is not None:
            try:
                server.close()
            except Exception:  # noqa: BLE001
                pass

    def _prune_locked(self, now: datetime) -> None:
        """Evict settled results past the TTL, then enforce the cap (oldest terminal
        first). Caller holds self._lock. Pending entries are never evicted."""
        def _terminal(state: str) -> bool:
            return self._results.get(state, {}).get("status") in ("success", "error")

        stale = [s for s, ts in self._result_ts.items() if _terminal(s) and (now - ts) > self._result_ttl]
        for s in stale:
            self._forget_locked(s)
        # Leave room for the one begin() is about to insert, so the post-insert total
        # stays <= cap. Only terminal results are evictable; pending ones are kept.
        target = max(0, self._result_cap - 1)
        if len(self._results) > target:
            terminal = sorted((ts, s) for s, ts in self._result_ts.items() if _terminal(s))
            for _ts, s in terminal[: len(self._results) - target]:
                self._forget_locked(s)

    def _forget_locked(self, state: str) -> None:
        self._results.pop(state, None)
        self._result_ts.pop(state, None)
        self._servers.pop(state, None)
