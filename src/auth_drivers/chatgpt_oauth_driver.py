"""S3 step 1 — OpenAI ChatGPT/Codex-backend OAuth driver (READ-ONLY discovery).

This driver makes an openai ``chatgpt_oauth`` credential report ITS OWN available
models — the ChatGPT/Codex backend's list, NOT the api-key seed catalog — so the
plan's "availability is PER (provider, auth_mode), NEVER shared" lock becomes real
on the wire. Discovery uses the P2c shape (plain ``models.list`` may 400; the codex
backend needs a Codex-style ``client_version`` via ``extra_query``), reusing the
probe's model-id extraction.

SCOPE (S3 step 1): discovery ONLY. Execution (``call_llm``/``stream_llm``) stays
gated — the ChatGPT-backend request differences (no ``max_output_tokens``, forced
``stream``/``store=False``, effort clamp) are S3 step 4, not done here. The real
P1/P2 capability check is the probe route (``run_chatgpt_oauth_probe``); this
driver's ``test()`` is an honest deferral, never a fake "ok".

The OpenAI client is built behind ``_discovery_client`` (a monkeypatchable seam),
and the token is loaded from the token-store ONLY (never ``credential.secret``).
Any surfaced error is redacted — the token can never leak into a result.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from src.model_credentials import DiscoveredModel, ModelDiscoveryResult, ModelTestResult, _seed_models

from .chatgpt_oauth_login import ChatGPTOAuthLoginError
from .chatgpt_oauth_login import refresh_if_needed as _refresh_login
from .chatgpt_oauth_probe import CHATGPT_BACKEND_BASE_URL, _CLIENT_VERSION, _PROBE_MODEL, _model_ids
from .probe_harness import redact

_S3_EXEC = "OpenAI chatgpt_oauth execution isn't wired yet (S3 step 4 — backend request differences)."

# A well-formed model id: starts alphanumeric, then [A-Za-z0-9._:-], ≤80 chars. Real
# model ids — gpt-5.4-mini, gpt-3.5-turbo, claude-opus-4-8, ft:gpt-..., dated ids —
# all satisfy it; it rejects spaces / @ / / + = (email + base64/JWT padding). Because
# a SHORT JWT (eyJ....eyJ....sig) uses only [A-Za-z0-9.], the regex alone can't catch
# it (version dots like 5.4 are legitimate), so an id is kept ONLY if it ALSO survives
# the fail-closed redact() unchanged (which catches JWT/base64/high-entropy shapes).
# Defense-in-depth: a hostile/odd backend can't reflect a token-shaped string into the
# picker; non-matching discovered ids are DROPPED, not shown.
_VALID_MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:\-]{0,79}$")


def _well_formed_ids(ids: list[str]) -> list[str]:
    return [mid for mid in ids if _VALID_MODEL_ID.fullmatch(mid) and redact(mid) == mid]


def _discovery_client(token: str) -> Any:  # seam for tests
    """A sync OpenAI client pointed at the ChatGPT/Codex backend, with a short
    timeout (discovery must not hang the request thread)."""
    from openai import OpenAI

    return OpenAI(api_key=token, base_url=CHATGPT_BACKEND_BASE_URL, timeout=15)


def _err(exc: BaseException) -> str:
    """Token-free, shape-only error string (redacted as defense-in-depth)."""
    return redact(f"{type(exc).__name__}: {exc}")[:200]


class OpenAIChatGPTOAuthDriver:
    """ResearchProviderDriver for (openai, chatgpt_oauth). Discovery is real;
    execution is gated to S3 step 4."""

    provider = "openai"
    auth_mode = "chatgpt_oauth"

    def __init__(self, *, credential: Any = None, token_store: Any = None):
        self.credential = credential
        self._token_store = token_store
        self._credential_id = (
            f"local:{credential.id}"
            if credential is not None and getattr(credential, "id", None) is not None
            else None
        )

    # --- auth state ------------------------------------------------------
    @property
    def is_authenticated(self) -> bool:
        return self._load_token() is not None

    async def authenticate(self) -> None:  # token arrives via the in-app OAuth login
        return None

    async def refresh_if_needed(self) -> None:
        # Refresh the rotating ChatGPT access token if expired (the login core handles
        # the 5-min buffer + the actual grant). No-op when there's nothing to refresh.
        if self._token_store is None or not self._credential_id:
            return None
        _refresh_login(credential_id=self._credential_id, token_store=self._token_store)
        return None

    async def get_quota_status(self) -> dict[str, Any]:
        return {"provider": self.provider, "auth_mode": self.auth_mode, "status": "unknown"}

    async def logout(self) -> None:  # token lives in the token-store; logout is instance-local
        return None

    def _load_token(self) -> Optional[str]:
        # Token from the token-store ONLY — NEVER credential.secret.
        if self._token_store is None or not self._credential_id:
            return None
        rec = self._token_store.load(
            provider="openai", auth_mode="chatgpt_oauth", credential_id=self._credential_id,
        )
        return rec.access_token if rec and getattr(rec, "access_token", None) else None

    # --- ResearchProviderDriver surface ---------------------------------
    async def discover_models(self) -> ModelDiscoveryResult:
        if self._token_store is None or not self._credential_id or not self._load_token():
            # No token → can't query the backend; the seed is the honest candidate list.
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="missing_credential", models=_seed_models("openai"),
            )
        # Refresh the (possibly expired) access token FIRST so "available models" doesn't
        # intermittently degrade. A refresh failure means the login is stale → surface a
        # clear re-login hint (redacted), not a silent seed fallback with no reason.
        try:
            rec = _refresh_login(credential_id=self._credential_id, token_store=self._token_store)
            token = rec.access_token if rec else None
        except ChatGPTOAuthLoginError as exc:
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="error", models=_seed_models("openai"),
                error=f"re-login needed (token refresh failed): {_err(exc)}",
            )
        if not token:
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="missing_credential", models=_seed_models("openai"),
            )
        try:
            client = _discovery_client(token)
            try:
                page = client.models.list()  # may 400 if the backend requires client_version
            except Exception:  # noqa: BLE001 — fall through to the Codex-style extra_query
                page = client.models.list(extra_query={"client_version": _CLIENT_VERSION})
            ids = _well_formed_ids(_model_ids(page))  # drop token/PII-shaped ids (defense-in-depth)
        except Exception as exc:  # noqa: BLE001 — never raise discovery; degrade to seed
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="error", models=_seed_models("openai"), error=_err(exc),
            )
        if not ids:
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="error", models=_seed_models("openai"),
                error="the ChatGPT backend returned no model ids",
            )
        models = [DiscoveredModel(id=mid, provider="openai", label=mid, source="provider_api") for mid in ids]
        return ModelDiscoveryResult(
            provider="openai", credential_id=self._credential_id,
            status="ok", models=models, source_url=CHATGPT_BACKEND_BASE_URL,
        )

    async def test(self) -> ModelTestResult:
        # Honest deferral: the real backend capability check is the P1/P2 probe route
        # (run_chatgpt_oauth_probe), NOT this method. Never report a fake "ok".
        if not self._load_token():
            return ModelTestResult(
                provider="openai", credential_id=self._credential_id, model="", effort="",
                status="missing_credential", error="no ChatGPT OAuth token stored for this credential",
            )
        return ModelTestResult(
            provider="openai", credential_id=self._credential_id, model=_PROBE_MODEL, effort="",
            status="error",
            warning="run the ChatGPT OAuth probe (P1/P2) from Settings; this driver does not call the backend here",
        )

    # --- execution gated to S3 step 4 -----------------------------------
    async def call_llm(self, request: Any):
        raise NotImplementedError(_S3_EXEC)

    def stream_llm(self, request: Any):
        raise NotImplementedError(_S3_EXEC)
