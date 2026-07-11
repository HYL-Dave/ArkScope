"""S3 — in-app ChatGPT/Codex OAuth login (PKCE) core for ArkScope.

ArkScope runs its OWN OAuth flow — no Codex CLI. Grounded in Novelloom's PROVEN
`chatgpt_oauth_login.py`. This module is the offline-TDD-able CORE:

  start_login()                  -> generate state + PKCE, stash the verifier in a
                                    short-TTL in-memory state store, return the auth_url.
  complete_login(state, code)    -> validate state -> exchange code+verifier for tokens
                                    -> write a CredentialStore metadata row + the token
                                    to the token-store (rollback on store-write failure)
                                    -> return masked metadata (NEVER the token).
  refresh_if_needed(credential_id) -> refresh only when expired (5-min buffer), under a
                                    per-credential lock; failures RAISE (no silent fallback).

Boundaries (per LLM_AUTH_DRIVER_PLAN.md "OAuth Login Fallback"): state mismatch / expiry,
PKCE mismatch, token exchange 400/401, incomplete tokens, refresh failure, and token-store
write failure all FAIL — none is ever masked by a fallback. The loopback HTTP server +
FastAPI routes + Settings UI are thin transport on top of this core; the copy-code path
reuses `complete_login` unchanged (it only changes how the code is delivered).

The OAuth `client_id` is the Codex app id (OpenAI exposes no third-party ChatGPT-OAuth
registration) — this is the documented "compatibility / reverse-engineered" path.
Token exchange + refresh go through monkeypatchable seams so this core needs no network.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import secrets
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib import error, request
from urllib.parse import parse_qs, urlencode, urlparse

from .probe_harness import redact
from .token_store import StoredTokenRecord

# --- OAuth params (Codex-compatibility — borrowed client registration) ---------
OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"  # Codex app id; no 3rd-party ChatGPT-OAuth app exists
OAUTH_AUTHORIZATION_URL = "https://auth.openai.com/oauth/authorize"
OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
OAUTH_REDIRECT_PORT = 1455
OAUTH_REDIRECT_URI = f"http://localhost:{OAUTH_REDIRECT_PORT}/auth/callback"  # fixed by the client_id
OAUTH_SCOPES = "openid profile email offline_access api.connectors.read api.connectors.invoke"
ORIGINATOR = "arkscope"

PROVIDER = "openai"
AUTH_MODE = "chatgpt_oauth"
_STATE_TTL = timedelta(minutes=10)
_EXPIRY_BUFFER = timedelta(minutes=5)


logger = logging.getLogger(__name__)


class ChatGPTOAuthLoginError(RuntimeError):
    """A login/refresh failure. Routes map it to an HTTP error; it NEVER carries a token.

    `status_code` carries the upstream HTTP status when one exists (set by
    `_http_post`; None for transport/parse failures). `reauth_required` marks
    failures only a fresh browser login can repair (set by `refresh_if_needed`:
    missing/unrefreshable stored tokens and invalid-grant-family refresh
    rejections); wiring and transient transport failures stay False."""

    def __init__(self, message: str, *, status_code: int | None = None, reauth_required: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.reauth_required = reauth_required


# --- PKCE + state -------------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, S256 code_challenge)."""
    verifier = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def generate_state() -> str:
    return _b64url(secrets.token_bytes(32))


def build_authorize_url(*, state: str, code_challenge: str) -> str:
    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": OAUTH_SCOPES,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": ORIGINATOR,
    }
    return f"{OAUTH_AUTHORIZATION_URL}?{urlencode(params)}"


@dataclass
class _PendingLogin:
    # repr=False so the PKCE code_verifier never renders in a repr/log/exception
    code_verifier: str = field(repr=False)
    expires_at: datetime = field()
    # The "set this credential active on completion?" choice is made at START and
    # carried here, so the SERVER-SIDE loopback callback honors it (it is not a
    # client cosmetic the callback path could bypass). Unified-activation policy.
    make_active: bool = field(default=True)
    # S3 re-login: when set, completion replaces THIS credential's token in
    # place (no new row). Carried in pending state exactly like make_active so
    # BOTH completion paths (loopback + copy-code) honor it.
    relogin_credential_id: str | None = field(default=None)


class _StateStore:
    """Short-TTL in-memory map state -> pending login (holds the PKCE verifier). The
    verifier NEVER touches the token-store or any response; entries are single-use."""

    def __init__(self) -> None:
        self._d: dict[str, _PendingLogin] = {}
        self._lock = threading.Lock()  # FastAPI route + loopback callback may run on different threads

    def put(self, state: str, code_verifier: str, *, expires_at: datetime, make_active: bool = True,
            relogin_credential_id: str | None = None) -> None:
        with self._lock:
            self._d[state] = _PendingLogin(
                code_verifier=code_verifier, expires_at=expires_at, make_active=make_active,
                relogin_credential_id=relogin_credential_id,
            )

    def pop(self, state: str, *, now: datetime) -> _PendingLogin | None:
        with self._lock:
            pending = self._d.pop(state, None)  # single-use: remove on any lookup
        if pending is None or now >= pending.expires_at:
            return None
        return pending

    def discard(self, state: str) -> None:
        # Evict a pending login (cancel): a later loopback callback's complete_login
        # then pops None → raises → no credential created. Idempotent.
        with self._lock:
            self._d.pop(state, None)


_STATE_STORE = _StateStore()


def start_login(*, now: datetime | None = None, state_store: _StateStore | None = None, make_active: bool = False,
                relogin_credential_id: str | None = None) -> dict:
    """Begin a login: mint state + PKCE, stash the verifier (+ the make_active choice),
    return the authorize URL. The response is safe to expose — it carries the
    code_challenge, never the verifier. `make_active` is carried in the pending state
    so the loopback callback completion honors it. Default FALSE (unified-activation
    policy): adding a credential never silently switches the active one — callers opt in.
    `relogin_credential_id` (S3) marks this login as an IN-PLACE token replacement for
    that existing chatgpt_oauth credential — validated again at completion."""
    now = now or datetime.now(timezone.utc)
    store = state_store if state_store is not None else _STATE_STORE
    verifier, challenge = generate_pkce_pair()
    state = generate_state()
    expires_at = now + _STATE_TTL
    store.put(state, verifier, expires_at=expires_at, make_active=make_active,
              relogin_credential_id=relogin_credential_id)
    return {
        "auth_url": build_authorize_url(state=state, code_challenge=challenge),
        "state": state,
        "expires_at": expires_at.isoformat(),
        "manual_code_supported": True,
    }


def extract_code_from_redirect_url(redirect_url: str) -> dict:
    """Pull {code, state} out of a pasted redirect URL (copy-code fallback). An OAuth
    `error` param or a missing code FAILS — it is not swallowed."""
    params = parse_qs(urlparse(redirect_url).query)
    if "error" in params:
        raise ChatGPTOAuthLoginError(f"OAuth error in redirect: {redact(params['error'][0])}")
    code = params.get("code", [None])[0]
    if not code:
        raise ChatGPTOAuthLoginError("the redirect URL is missing the authorization code")
    return {"code": code, "state": params.get("state", [None])[0]}


# --- error-body redaction (a backend/proxy could echo a secret) ----------------
# Redact the VALUE of any known-secret field by key, regardless of length/charset —
# the generic length/entropy heuristics in probe_harness.redact() can miss a short or
# oddly-shaped echo (e.g. a `code_verifier` value), so this fail-closed key pass runs
# FIRST, then redact() is the catch-all. Longer keys precede shorter so `code` can't
# shadow `code_verifier` (the closing quote already anchors it; ordering is belt-and-braces).
_SECRET_FIELD_RE = re.compile(
    r'("(?:code_verifier|code_challenge|access_token|refresh_token|id_token|'
    r'client_secret|authorization|code|secret|token)"\s*:\s*)"[^"]*"',
    re.I,
)


def _redact_oauth_error(text: str) -> str:
    """Strip known-secret field values, then fail-closed redact, then bound the length."""
    scrubbed = _SECRET_FIELD_RE.sub(r'\1"[REDACTED]"', text)
    return redact(scrubbed)[:200]


# --- token exchange / refresh (monkeypatchable seams) -------------------------
def _http_post(url: str, *, data: bytes, content_type: str, what: str) -> dict:
    req = request.Request(url, data=data, headers={"Content-Type": content_type}, method="POST")
    try:
        with request.urlopen(req, timeout=30) as resp:
            value = json.loads(resp.read())
    except error.HTTPError as exc:
        # A token-exchange/refresh error body could echo the code/code_verifier/
        # refresh_token (proxy, mock, or a future backend). Keep the status, but
        # fail-closed redact the body before it reaches a route/UI/log.
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise ChatGPTOAuthLoginError(
            f"ChatGPT OAuth {what} failed ({exc.code}): {_redact_oauth_error(detail)}",
            status_code=exc.code,
        ) from None
    except (OSError, json.JSONDecodeError) as exc:
        raise ChatGPTOAuthLoginError(f"ChatGPT OAuth {what} failed: {_redact_oauth_error(str(exc))}") from None
    if not isinstance(value, dict):
        raise ChatGPTOAuthLoginError(f"ChatGPT OAuth {what} failed: expected a JSON object")
    return value


def _exchange_authorization_code(*, code: str, code_verifier: str) -> dict:  # seam for tests
    return _http_post(
        OAUTH_TOKEN_URL,
        data=urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "client_id": OAUTH_CLIENT_ID,
            "code_verifier": code_verifier,
        }).encode(),
        content_type="application/x-www-form-urlencoded",
        what="token exchange",
    )


def _refresh_token_grant(*, refresh_token: str) -> dict:  # seam for tests
    return _http_post(
        OAUTH_TOKEN_URL,
        data=json.dumps({
            "client_id": OAUTH_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }).encode(),
        content_type="application/json",
        what="refresh",
    )


# --- JWT claim/expiry extraction ----------------------------------------------
def _str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _decode_jwt_payload(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ChatGPTOAuthLoginError("invalid JWT: expected header.payload.signature")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        value = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, TypeError):
        # static message + `from None`: never interpolate/chain anything derived from the
        # JWT segment (defense-in-depth; this is swallowed by both callers regardless).
        raise ChatGPTOAuthLoginError("invalid JWT payload") from None
    if not isinstance(value, dict):
        raise ChatGPTOAuthLoginError("invalid JWT payload: expected an object")
    return value


def _extract_access_token_expiry(access_token: str) -> str | None:
    try:
        payload = _decode_jwt_payload(access_token)
    except ChatGPTOAuthLoginError:
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        return datetime.fromtimestamp(float(exp), tz=timezone.utc).isoformat()
    return None


def _extract_id_token_claims(id_token: str) -> dict:
    try:
        payload = _decode_jwt_payload(id_token)
    except ChatGPTOAuthLoginError:
        return {}
    auth_claims = payload.get("https://api.openai.com/auth", {})
    if not isinstance(auth_claims, dict):
        auth_claims = {}
    return {
        "account_id": _str(auth_claims.get("chatgpt_account_id")),
        "plan_type": _str(auth_claims.get("chatgpt_plan_type")),
    }


def _account_label(plan_type: str) -> str:
    # NON-PII display label (no email) — raw account internals stay in the token metadata.
    return f"ChatGPT {plan_type}".strip() if plan_type else "ChatGPT subscription"


def _token_response_to_record(resp: dict) -> tuple[StoredTokenRecord, str, str]:
    access = _str(resp.get("access_token"))
    refresh = _str(resp.get("refresh_token"))
    id_token = _str(resp.get("id_token"))
    if not access or not refresh:
        raise ChatGPTOAuthLoginError("OAuth token exchange returned incomplete token data (missing access/refresh token)")
    claims = _extract_id_token_claims(id_token) if id_token else {}
    plan_type = claims.get("plan_type", "")
    label = _account_label(plan_type)
    record = StoredTokenRecord(
        access_token=access,
        refresh_token=refresh,
        expires_at=_extract_access_token_expiry(access),
        plan_type=plan_type or None,
        account_label=label,
        metadata={"account_id": claims.get("account_id", ""), "id_token": id_token},
    )
    return record, plan_type, label


def complete_login(
    *,
    state: str,
    code: str,
    credential_store: Any,
    token_store: Any,
    alias: str = "ChatGPT subscription",
    now: datetime | None = None,
    state_store: _StateStore | None = None,
    exchange: Callable[..., dict] | None = None,
    invalidate_relogin_cache: Callable[[str], int] | None = None,
) -> dict:
    """Finish a login (used by BOTH the loopback callback and the copy-code paste). Returns
    masked metadata only — the token is NEVER echoed. Any failure raises; nothing is left
    half-built (a token-store write failure rolls back the credential row). The
    make_active choice comes from the pending state (set at start_login), NOT an arg —
    so the server-side callback completion can't bypass it.

    When the pending state carries `relogin_credential_id` (S3), completion REPLACES that
    credential's token in place instead of creating a row — see `_complete_relogin`.
    `invalidate_relogin_cache` (the manager-supplied discovery-cache invalidator) is
    REQUIRED for that path and unused for creates."""
    now = now or datetime.now(timezone.utc)
    store = state_store if state_store is not None else _STATE_STORE
    pending = store.pop(state, now=now)
    if pending is None:
        raise ChatGPTOAuthLoginError("OAuth state is unknown or expired — the login was not started here or it timed out")

    exchange = exchange or _exchange_authorization_code
    resp = exchange(code=code, code_verifier=pending.code_verifier)  # 400/401 raises — NO fallback; BEFORE any lock
    record, plan_type, label = _token_response_to_record(resp)

    if pending.relogin_credential_id:
        return _complete_relogin(
            target=pending.relogin_credential_id, record=record, plan_type=plan_type, label=label,
            credential_store=credential_store, token_store=token_store,
            invalidate_relogin_cache=invalidate_relogin_cache,
        )

    cred = credential_store.add_oauth_credential(
        provider=PROVIDER, auth_mode=AUTH_MODE, alias=alias, make_active=pending.make_active,
        expires_at=record.expires_at, account_label=label,
    )
    cid = f"local:{cred.id}"
    try:
        token_store.save(provider=PROVIDER, auth_mode=AUTH_MODE, credential_id=cid, record=record)
    except Exception:  # noqa: BLE001 — roll back so no half-built credential remains
        credential_store.delete(cid)
        # `from None`: the cause (a token_store.save failure) can wrap the full serialized
        # record; the message is static, so sever the chain rather than carry that cause.
        raise ChatGPTOAuthLoginError("failed to store the token securely; nothing was saved") from None

    return {
        "credential_id": cid,
        "alias": cred.alias,
        "expires_at": cred.expires_at,
        "account_label": cred.account_label,
        "plan_type": plan_type,
    }


def _complete_relogin(
    *,
    target: str,
    record: StoredTokenRecord,
    plan_type: str,
    label: str,
    credential_store: Any,
    token_store: Any,
    invalidate_relogin_cache: Callable[[str], int] | None,
) -> dict:
    """In-place token replacement for an EXISTING openai chatgpt_oauth credential
    (plan D2/D3). Ordering inside the lifecycle lock: re-validate the target →
    clear its discovery cache (old-account entitlement must not survive) → save
    the new token → refresh row metadata. Atomicity is the INVERSE of the create
    path: every failure leaves the OLD token in place (or removes the new one) —
    never a half-adopted login, never a fallback to creating a new row.
    alias and active are deliberately untouched."""
    if invalidate_relogin_cache is None:
        raise ChatGPTOAuthLoginError("re-login requires a discovery-cache invalidator; nothing was changed")
    with oauth_credential_lock(target):
        cred = credential_store.get(target)
        if cred is None or getattr(cred, "provider", None) != PROVIDER \
                or getattr(cred, "auth_type", None) != AUTH_MODE:
            raise ChatGPTOAuthLoginError(
                "re-login target is not an existing openai chatgpt_oauth credential; nothing was changed",
            )
        old_record = token_store.load(provider=PROVIDER, auth_mode=AUTH_MODE, credential_id=target)
        try:
            rows_deleted = invalidate_relogin_cache(target)
        except Exception:  # noqa: BLE001 — abort while token + metadata are untouched
            # An empty cache is safe (picker returns to never_discovered); a stale
            # one serving the previous account's entitlement is not.
            raise ChatGPTOAuthLoginError(
                "re-login aborted: could not clear the discovery cache; nothing was changed",
            ) from None
        try:
            token_store.save(provider=PROVIDER, auth_mode=AUTH_MODE, credential_id=target, record=record)
        except Exception:  # noqa: BLE001 — static message; never carry the record via the cause
            raise ChatGPTOAuthLoginError("failed to store the new token; the previous token is unchanged") from None
        try:
            updated = credential_store.update(target, expires_at=record.expires_at or "", account_label=label)
        except Exception as exc:
            compensated = _rollback_relogin_token(target=target, old_record=old_record, token_store=token_store)
            # The ORIGINAL metadata error stays the cause; the message is redacted+bounded
            # and reports the REAL compensation outcome (F2: never claim a rollback
            # that did not land).
            raise ChatGPTOAuthLoginError(
                f"re-login metadata update failed: {redact(str(exc))[:200]}; "
                f"{_relogin_rollback_outcome(compensated, old_record)}",
            ) from exc
        if updated is None:
            compensated = _rollback_relogin_token(target=target, old_record=old_record, token_store=token_store)
            raise ChatGPTOAuthLoginError(
                "re-login target row vanished during completion; "
                f"{_relogin_rollback_outcome(compensated, old_record)}",
            )
        return {
            "credential_id": target,
            "alias": updated.alias,
            "expires_at": updated.expires_at,
            "account_label": updated.account_label,
            "plan_type": plan_type,
            "relogin": True,
            "discovery_cache_cleared": True,
            "discovery_cache_rows_deleted": rows_deleted,
        }


def _rollback_relogin_token(*, target: str, old_record: StoredTokenRecord | None, token_store: Any) -> bool:
    """Best-effort compensation for a failed re-login after the new token landed:
    restore the old record, or drop the new one when none existed. Returns
    whether the compensation LANDED. A rollback failure is LOGGED and never
    replaces the original error — a double storage failure cannot honestly
    promise a clean terminal state."""
    try:
        if old_record is not None:
            token_store.save(provider=PROVIDER, auth_mode=AUTH_MODE, credential_id=target, record=old_record)
        else:
            token_store.delete(provider=PROVIDER, auth_mode=AUTH_MODE, credential_id=target)
    except Exception:  # noqa: BLE001
        logger.warning(
            "re-login rollback failed for %s; the token store may still hold the new token",
            target, exc_info=True,
        )
        return False
    return True


def _relogin_rollback_outcome(compensated: bool, old_record: StoredTokenRecord | None) -> str:
    """The honest one-liner for a failed re-login's terminal token state (F2)."""
    if not compensated:
        return "the token store may still hold the new token"
    return "the previous token was restored" if old_record is not None else "the new token was removed"


# --- refresh ------------------------------------------------------------------
_refresh_locks: dict[str, threading.Lock] = {}
_refresh_locks_guard = threading.Lock()


def _lock_for(credential_id: str) -> threading.Lock:
    with _refresh_locks_guard:
        lock = _refresh_locks.get(credential_id)
        if lock is None:
            lock = threading.Lock()
            _refresh_locks[credential_id] = lock
        return lock


@contextmanager
def oauth_credential_lock(credential_id: str):
    """The per-credential lifecycle lock (plan D2): token refresh, re-login
    completion, and ChatGPT-OAuth credential deletion all serialize on it, so a
    stale in-flight refresh can never clobber a freshly authorized token or
    resurrect a deleted one. PROCESS-LOCAL ONLY — two sidecars sharing one
    token store do not share this Python lock (cross-process advisory lock =
    plan §6 follow-up). Never hold it across browser interaction or the
    authorization-code exchange; it covers completion/storage work only. The
    lock is NOT re-entrant — callers must not nest it for the same id."""
    with _lock_for(credential_id):
        yield


def _is_expired(record: StoredTokenRecord, *, now: datetime) -> bool:
    if not record.expires_at:
        return False  # unknown expiry — don't auto-refresh; callers force before critical ops
    try:
        exp = datetime.fromisoformat(record.expires_at)
    except ValueError:
        return False
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return now >= exp - _EXPIRY_BUFFER


def _refresh_response_to_record(resp: dict, prev: StoredTokenRecord) -> StoredTokenRecord:
    access = _str(resp.get("access_token")) or prev.access_token
    refresh = _str(resp.get("refresh_token")) or prev.refresh_token
    id_token = _str(resp.get("id_token")) or _str((prev.metadata or {}).get("id_token"))
    claims = _extract_id_token_claims(id_token) if id_token else {}
    plan_type = claims.get("plan_type") or (prev.plan_type or "")
    return StoredTokenRecord(
        access_token=access,
        refresh_token=refresh,
        expires_at=_extract_access_token_expiry(access),
        plan_type=plan_type or None,
        account_label=_account_label(plan_type) if plan_type else (prev.account_label or "ChatGPT subscription"),
        metadata={"account_id": claims.get("account_id") or (prev.metadata or {}).get("account_id", ""), "id_token": id_token},
    )


def refresh_if_needed(
    *,
    credential_id: str,
    token_store: Any,
    now: datetime | None = None,
    force: bool = False,
    refresh: Callable[..., dict] | None = None,
) -> StoredTokenRecord:
    """Return a fresh token record, refreshing iff expired (5-min buffer) or forced. Runs
    under a per-credential lock so concurrent agents don't double-refresh. A missing
    refresh_token or a failed refresh RAISES — never a silent fallback to a stale/other token.

    INTERNAL ONLY — the returned StoredTokenRecord carries the live access_token /
    refresh_token / id_token. A ROUTE MUST NEVER serialize this return value. The
    chatgpt_oauth driver reads only `record.access_token` for the Bearer header; any
    Settings/route surface exposes masked metadata only (the credential DTO or
    `token_store.status()`, which omit the secrets)."""
    now = now or datetime.now(timezone.utc)
    with oauth_credential_lock(credential_id):
        record = token_store.load(provider=PROVIDER, auth_mode=AUTH_MODE, credential_id=credential_id)
        if record is None:
            # An OAuth row without a stored token is only repairable by re-login.
            raise ChatGPTOAuthLoginError("no stored token for this credential", reauth_required=True)
        if not force and not _is_expired(record, now=now):
            return record
        if not record.refresh_token:
            raise ChatGPTOAuthLoginError(
                "cannot refresh: no refresh_token is stored for this credential", reauth_required=True,
            )
        refresh = refresh or _refresh_token_grant
        try:
            resp = refresh(refresh_token=record.refresh_token)  # failure raises — NO silent fallback
        except ChatGPTOAuthLoginError as exc:
            # Classify (plan D4): 401/400 on a refresh grant is the invalid-grant
            # family — the login itself is stale and only a fresh browser login
            # repairs it. Transport failures (status_code None) stay transient.
            exc.reauth_required = exc.reauth_required or exc.status_code in (400, 401)
            raise
        new_record = _refresh_response_to_record(resp, record)
        token_store.save(provider=PROVIDER, auth_mode=AUTH_MODE, credential_id=credential_id, record=new_record)
        return new_record
