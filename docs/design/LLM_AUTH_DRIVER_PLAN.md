# LLM Auth Driver Plan

> **Status:** PARTIALLY BUILT — was DESIGN-ONLY; drafted + gpt-5.5-reviewed, all §13 decisions RESOLVED 2026-06-15. **Built + unit-tested: S0 contract · S1 factory + `CredentialStore` delta · S2 standard `api_key` drivers (A+D) · S4 Anthropic `claude_code_oauth` SDK subscription driver — plus the 7B AI-研究 Research-stream consumer, live-validated on the Claude subscription (real tool call, built-ins locked, no token leak; commits `5f0ea35`→`9131f7f`).** **NEXT = S3 (OpenAI `chatgpt_oauth`), probe-first (run P2 before any Settings row).** S5 (full agent-loop wire-in) stays a separate future slice. Built code lives in `src/auth_drivers/` (+ `src/api/routes/query.py` for the 7B consumer); the 7B SDK-driver design detail = [SLICE_7B3_SDK_DRIVER_DESIGN.md](SLICE_7B3_SDK_DRIVER_DESIGN.md). Grounded in Novelloom's auth subsystem (`/mnt/md0/PycharmProjects/novelloom/src/novelloom/shared/auth/`, `docs/14_llm_access_and_auth.md`, `docs/19_chatgpt_oauth_backend_compatibility.md`) and ArkScope's current auth surface (`src/model_credentials.py`, `src/tools/code_generator.py`, `src/api/routes/config_routes.py`, `src/agents/{anthropic,openai}_agent/agent.py`, `src/api/routes/query.py`). Authored via an Opus-4.8 workflow (4 grounded readers → synthesis) + a spot-check of the load-bearing Novelloom claims (base_url / token-as-api_key / Protocol shape verified against source).
>
> **One-line goal:** Introduce a provider-neutral `AuthDriver` abstraction (borrowed FORM from Novelloom) that becomes the single client/strategy factory for all LLM credentials — built and tested BEFORE any rewiring of the agent loops or C-2 persistence.

---

## 1. Why / Scope

ArkScope today constructs provider clients with bare zero-arg `Anthropic()` / SDK-default OpenAI clients at ~7 independent call sites, relying entirely on SDK env-pickup of `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` populated from `config/.env`. There is **no auth abstraction**. The *only* place subscription auth already works is `code_generator._call_codex_cli` / `_call_claude_cli` (subprocess to `codex exec` / `claude -p`).

The goal is to let a user run ArkScope's agent against **a subscription (ChatGPT Plus/Pro, Claude Pro/Max) instead of a metered API key**, without rewiring the agent tool loops or the C-2 Research-thread trace/history path. We do this by:

1. Defining an `AuthDriver` contract (Novelloom's Protocol shape, adapted).
2. Adding a `(provider, auth_mode) → driver` factory (Novelloom *lacks* this — the one thing we ADD, not copy).
3. Extending `CredentialStore` so a stored credential can actually back the OAuth/setup-token modes that are currently reserved-but-stubbed.
4. Wiring the driver in **only** at client-construction boundaries, leaving `run_query_stream` event vocab and `query.py` persistence untouched.

**In scope:** driver contract, factory, credential schema delta, settings UI shape, OAuth/token storage design, falsifiable probes, slice sequence.
**Out of scope (this doc):** actually rewiring the main agent loops; building the drivers' bodies; the OpenAI Agents-SDK black-box loop internals.

---

## 2. Load-bearing truths — the THREE auth realities (do NOT conflate)

These three are **distinct legitimacy classes, distinct hosts, distinct credentials**. The entire Novelloom doc-19 exists to keep #1 and #2 apart; #3 has *no Novelloom precedent* and is designed from scratch here.

| # | Reality | Host / transport | Credential | Legitimacy | Billing | In Novelloom? |
|---|---------|------------------|------------|------------|---------|---------------|
| **A** | **OpenAI standard API** | `https://api.openai.com/v1` (Responses API; Agents-SDK default client) | `sk-...` key **or** workload-identity bearer | Stable public API | Per-token API | YES (`OpenAIApiKeyDriver`) |
| **B** | **OpenAI ChatGPT-OAuth (backend COMPATIBILITY)** | `https://chatgpt.com/backend-api/codex` (same OpenAI SDK, swapped `base_url`) | OAuth **access_token passed AS the SDK `api_key`** (a Bearer, NOT an `sk-` key) | **NON-STANDARD, reverse-engineered**; imitates Codex CLI `client_id` + `client_version`; a compatibility path, **NOT a standard/public OpenAI API path** (it IS ArkScope's product OAuth path per §13 — "not product path" would be wrong; "not standard API" is the accurate caveat); may break on backend changes | ChatGPT Plus/Pro subscription | YES (`OpenAIChatGPTOAuthDriver`) — **FORM to borrow** |
| **C** | **Anthropic setup-token (Claude Agent SDK / CLI)** | Claude Agent SDK / `claude -p` (NOT raw `Anthropic()` → `api.anthropic.com`) | `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` (1-yr pasted token) | **setup-token path is DOCUMENTED** (Claude Code auth docs) — a *different legitimacy class* from B (documented, not reverse-engineered); but the **third-party-app + monthly Agent-SDK-credit amounts/policy REQUIRE live re-verification** | Claude Pro/Max/Team/Enterprise subscription → separate monthly Agent-SDK credit (from 2026-06-15) | **NO** — design-from-scratch, **DESIGNED-not-proven** |
| (D) | *Anthropic standard API* (baseline, exists today) | `https://api.anthropic.com/v1/messages` | `x-api-key` (`ANTHROPIC_API_KEY`) | Stable public API | Per-token API | (raw SDK; not a Novelloom driver) |

### The four conflations this plan must NOT make
1. **A ≠ B.** Setting `OPENAI_API_KEY` to an OAuth token and pointing at `api.openai.com/v1` **fails**. B requires `AsyncOpenAI(api_key=<oauth_token>, base_url="https://chatgpt.com/backend-api/codex")`.
2. **B ≠ C legitimacy.** B is reverse-engineered/TOS-sensitive/**unsupported by OpenAI's API docs**; C's setup-token path is *documented* (its credit amounts/policy are TBD pending re-verify). **Do NOT paste B's "may break, compatibility path" disclaimer onto C** — but also do NOT overstate C as fully "officially sanctioned third-party" until the credit policy is live-re-verified. The accurate framing: *C = documented path, credit details unverified.*
3. **C ≠ D.** `CLAUDE_CODE_OAUTH_TOKEN` is **not** a drop-in `x-api-key`/Bearer for `api.anthropic.com`. The Messages API docs list only `x-api-key` and WIF bearers (minted via `POST /v1/oauth/token`), NOT `CLAUDE_CODE_OAUTH_TOKEN`. C MUST route through the Agent SDK / `claude -p` (ArkScope's working `_call_claude_cli` IS exactly this).
4. **Novelloom has no Anthropic driver at all.** `model_capabilities.py` lists Anthropic models + effort/thinking validators as a *forward seam only*; `writer_factory` raises `WriterConfigurationError` for `provider != "openai"`. So **everything Anthropic-side (C and D-as-driver) is DESIGNED, grounded only in Novelloom's rationale doc, not its code.**

### API-key runtime vs Claude setup-token runtime

This difference is load-bearing for Slice 7B:

| Runtime | Where the model/tool loop runs | How ArkScope tools are available | Tool bridge needed? |
|---|---|---|---|
| **Standard API key** (`openai/api_key`, `anthropic/api_key`) | Inside ArkScope's Python sidecar process | The existing OpenAI/Anthropic agent bridges call ArkScope Python functions directly (`get_sa_feed`, `get_fundamentals_analysis`, `get_price_change`, etc.) | **No** — tools are already in-process |
| **Claude setup-token** (`anthropic/claude_code_oauth`) | Via the **Claude Agent SDK** — the SDK runs the model/tool loop; ArkScope tools are bridged back **in-process** | The SDK's own runtime sees Claude Code's built-in tools, not ArkScope's Python functions, unless they are bridged in | **Yes** — an **in-process** SDK tool bridge (`create_sdk_mcp_server`), NOT an external MCP server or `claude -p --mcp-config`; see §7B |
| **OpenAI ChatGPT-OAuth** (`openai/chatgpt_oauth`) | Still the OpenAI SDK shape, but pointed at the ChatGPT backend compatibility host | If the compatibility backend supports function/tool calls, ArkScope can keep owning the tool loop/bridge shape; this must be proven by P2 | **Compatibility-gated**, not assumed |

The key point: a credential answers only **who pays / how the provider authenticates**.
It does not automatically carry ArkScope's tools into a different runtime.

Standard API-key paths do not have the Claude MCP problem because the model call
is made by ArkScope's own agent loop. The loop already has the registry/bridge
objects in memory and can execute tools as normal Python calls.

Claude setup-token is different. `export CLAUDE_CODE_OAUTH_TOKEN=...` is enough
for `claude -p` to authenticate to the subscription path, but it does not teach
Claude Code about ArkScope's data tools. Without an MCP server or equivalent
tool bridge, subscription Research would be a general Claude Code chat with
Claude Code tools, not an ArkScope financial research agent.

---

## 3. Driver matrix

Each row = one concrete driver. "Standard vs compat" is the load-bearing column.

| Provider | auth_mode | Driver class | Billing | SDK / path | Standard vs compat | Risk |
|----------|-----------|--------------|---------|------------|--------------------|------|
| openai | `api_key` | `OpenAIApiKeyDriver` | API per-token | `AsyncOpenAI(api_key=sk-…)` → `api.openai.com/v1`; for the **main loop**, set Agents-SDK default via `set_default_openai_key`/`set_default_openai_client` (Runner takes no client) | **STANDARD** | Low. Borrow Novelloom verbatim. |
| openai | `chatgpt_oauth` | `OpenAIChatGPTOAuthDriver` | ChatGPT subscription | **In-app** OAuth → `AsyncOpenAI(api_key=<oauth_token>, base_url="chatgpt.com/backend-api/codex")`; force `stream=True`+`store=False`; **strip `max_output_tokens`** | **COMPATIBILITY — UNSUPPORTED by OpenAI API docs** (reverse-eng. ChatGPT backend) | High — TOS-sensitive, borrowed Codex `client_id`, capability-restricted, can break. **Proven in Novelloom; ArkScope does its OWN OAuth, no Codex CLI dependency.** |
| openai | `codex_cli` *(DEV/DEBUG + import only — NOT a product path)* | `OpenAICodexCliDriver` | ChatGPT subscription | subprocess `codex exec` — **requires a user-installed Codex CLI** | dev/debug harness | **The desktop app must NOT require/bundle Codex CLI.** Product use = none; only an optional "import an existing Codex login's token" convenience + a dev comparison harness. |
| anthropic | `api_key` | `AnthropicApiKeyDriver` | API per-token | `Anthropic()` / `client.messages.stream()` → `api.anthropic.com` | **STANDARD** | Low-Med — **DESIGNED** (Novelloom has none); but ArkScope's loop already does this raw. |
| anthropic | `claude_code_oauth` | `AnthropicClaudeCodeSdkDriver` ✅ BUILT (7B) | Claude subscription (Agent-SDK credit) | **Python Claude Agent SDK** (`claude_agent_sdk.query`) with an **in-process** ToolRegistry→SDK MCP bridge (`create_sdk_mcp_server`), `permission_mode="dontAsk"` + `tools=[]` + Tier-1 allowlist; `CLAUDE_CODE_OAUTH_TOKEN` injected via `options.env`, `ANTHROPIC_API_KEY=""` — **NOT `claude -p`** | **DOCUMENTED path; live-validated on the subscription (`apiKeySource='none'`, no token leak)** | Med — built + smoked; Agent-SDK credit policy still live-re-verify before any UI figure. |

> **`chatgpt_oauth` (B) is THE product OpenAI-subscription path — an IN-APP OAuth driver.** ArkScope itself runs the OAuth login / token capture / refresh / store and talks to the ChatGPT backend with the OpenAI SDK (`base_url` swap). It **borrows the Codex OAuth+backend protocol but does NOT depend on, bundle, or require Codex CLI** — a desktop app must not force a CLI install on the user. **`codex_cli` is NOT a product fallback**: it's a dev/debug harness + an optional "import an already-logged-in Codex token" convenience only. **If `chatgpt_oauth` fails at runtime, the product fallback is "use an API key," never "install Codex CLI."** (Decisions §13.)

---

## 4. AuthDriver contract for ArkScope

### 4.1 Base shape (borrow Novelloom's Protocol verbatim)

A **structural `typing.Protocol`** (not ABC) carrying two class attrs + 7 members. Source of truth: `novelloom/src/novelloom/shared/auth/protocol.py:51-75` (verified).

```python
class AuthDriver(Protocol):
    provider: str        # "openai" | "anthropic"
    auth_mode: str       # "api_key" | "chatgpt_oauth" | "claude_code_oauth" | ...
    @property
    def is_authenticated(self) -> bool: ...
    async def authenticate(self) -> None: ...
    async def refresh_if_needed(self) -> None: ...           # called BEFORE every call_llm/stream_llm
    async def call_llm(self, request: LLMRequest) -> LLMResponse: ...
    def stream_llm(self, request: LLMRequest) -> AsyncIterator[ArkStreamEvent]: ...  # NOTE: sync def → async gen
    async def get_quota_status(self) -> dict[str, Any]: ...
    async def logout(self) -> None: ...
```

> **GOTCHA (carried from Novelloom):** `stream_llm` is declared `def … -> AsyncIterator`, i.e. an async **generator** returned synchronously. A caller/factory must NOT `await driver.stream_llm(...)`. The other five methods ARE `async def`. Mixing this up is an easy bug.

`LLMRequest` / `LLMResponse` / `TokenUsage` mirror Novelloom (`protocol.py:19-48`), Pydantic `extra="forbid"`:
- `LLMRequest`: `model`, `instructions|None`, `input_messages: list[dict]`, `reasoning_effort|None`, `max_output_tokens|None`, `tools: list[dict]=[]`, `response_format|None`.
- `LLMResponse`: `text`, `tool_calls: list[dict]=[]`, `usage: TokenUsage`, `raw_response: Any`.

### 4.2 ArkScope adaptation — the `ResearchProviderDriver` extension

ArkScope is more complex than Novelloom (live tool loop, C-2 SSE trace, dual SDK, thread persistence). The Novelloom Protocol's `call_llm`/`stream_llm` traffic in **provider-native tool dicts**, which is enough — but ArkScope's `stream_llm` must yield events that the existing C-2 reducer understands. We therefore subtype the protocol for ArkScope's needs. **This is the adaptation layer; cite Novelloom for the base.**

`ResearchProviderDriver(AuthDriver)` adds/specifies:

1. **Stream events.** `stream_llm` yields `ArkStreamEvent` whose `to_sse()` produces the **exact existing `AgentEvent` vocabulary** so `query.py:accumulate_tool_calls` keeps working unchanged: `thinking, thinking_content, text, tool_start{tool,input}, tool_end{tool,summary,chars}, done{answer,tools_used,provider,model,token_usage}, error`. **The driver adapts to this contract; the contract does not change.**
2. **Tool-call shape.** Provider-native passthrough, like Novelloom: `tools` passed verbatim in `LLMRequest.tools`; tool calls harvested from output items whose `type` endswith `_call` (Novelloom `openai_responses.py:83-101`). ArkScope's 52-tool registry is unaffected — drivers never enumerate tools.
3. **Model discovery.** `async discover_models() -> ModelDiscoveryResult` (reuse ArkScope's existing `ModelDiscoveryResult`/`DiscoveredModel` shape, `model_credentials.py:46-59` — **not a weaker parallel DTO**; the result is keyed by `credential_id`). **PER (provider, auth_mode) — NEVER assume parity:** the `api_key` model set ≠ the `chatgpt_oauth` set (nonstandard ChatGPT-backend list) ≠ `claude_code_oauth`. Per-mode strategy: `api_key` → provider Models API; `chatgpt_oauth` → Codex-style `extra_query={"client_version":"…"}` returning the **nonstandard `models` field** through an adapter; `claude_code_oauth`/unknown → **fall back to ArkScope's local `MODEL_CATALOG`** seed. **The "what models / capabilities work" check is therefore a SEPARATE result per auth mode, never shared.**
4. **Quota/status.** `async get_quota_status()` — **honest UNKNOWN by default.** Novelloom returns `status="unknown"` for BOTH drivers; there is **no real subscription-remaining probe**. ArkScope must surface login-state + client-side session token tallies + (for OAuth) plan_type/expiry, and must NOT claim "X% quota left."
5. **Auth test.** `async test() -> ModelTestResult` — reuse the existing `ModelTestResult` shape (`model_credentials.py:62-71`: `provider, credential_id, model, effort, status∈{ok,missing_credential,error}, latency_ms, error, warning, fallback_effort`). A tiny non-persisted call (clamped `max_output_tokens`, `store=False`), modeled on Novelloom `test_writer_profile`. Like discovery, it is **per (provider, auth_mode)** (a chatgpt_oauth `test` exercises the ChatGPT backend's capability floor, NOT the standard API). Powers the Settings "Verify" button.

> **Build-first boundary:** §4 is the abstraction to land BEFORE touching either `run_query_stream`. Drivers expose only construction + call/stream/discover/quota/test. The C-2 SSE reducer and `query.py` persistence wrap *around* `stream_llm`'s yielded events — no loop rewrite.

---

## 5. CredentialStore schema delta

ArkScope's `llm_credentials` table (`model_credentials.py:81-94`) **already** has `provider`, `auth_type` (Literal already includes `oauth`/`setup_token`), `alias`, `secret`, `active`. It is itself the credential table — unlike Novelloom's `writer_profiles`, which carries config only and has **no credential linkage** (the gap we must NOT copy: Novelloom can't distinguish two keys of the same `auth_mode`).

### 5.1 What changes
| Item | Today | Delta |
|------|-------|-------|
| `auth_type` Literal | `api_key`, `api_key_pool`, `oauth`, `setup_token` (`model_credentials.py:27`) | **Rename/extend to explicit modes** to kill the B/C/D conflation: `api_key`, `api_key_pool`, `chatgpt_oauth`, `claude_code_oauth` (keep `oauth`/`setup_token` as deprecated aliases mapped on read). A generic `oauth` can't tell B from C. |
| `_resolve_api_credential` stub | returns `None` for anything not in `(api_key, api_key_pool)` | **Driver factory replaces this hard-stop.** For OAuth modes the secret resolves via the token-store (§7), not as a raw API key. Discovery/test route through the driver's own `discover_models`/`test`. |
| `add()` auth_type | no validation in store; route validates `{api_key, oauth, setup_token}` (`config_routes.py:203`) | **Widen route allow-set** to the new modes, else create 400s. |
| credential metadata | `secret`, `active`, timestamps | **Add nullable `expires_at TEXT`, `account_label TEXT`** (redacted plan/expiry display for OAuth rows) — additive, no breaking change. The live OAuth token blob lives in the token-store (§7), NOT the `secret` column for OAuth modes; `secret` holds the API key for `api_key` modes. |

### 5.2 What we explicitly DO keep (and Novelloom lacks)
- **Credential identity / multi-credential.** ArkScope already keys credentials by row id (`local:N`) with an `active` flag and per-provider single-active invariant. This *is* the "bind a profile to a specific stored secret" linkage Novelloom omitted — keep it; do not regress to Novelloom's process-global `auth_mode → one secret`.
- DB at `0o600`, WAL. Keep.

> **No new `writer_profiles`-style table needed.** ArkScope's per-task routing already lives in `AgentConfig` + `user_profile.yaml`. The `auth_mode` dimension layers under the existing credential rows, not a separate profiles table.

---

## 6. Settings UI shape (multi-credential profiles)

Reuse the existing surface: `GET /config/runtime`, `GET/POST/PUT/DELETE /config/credentials`, `provider_credentials()` masked inventory, and the lone remaining placeholder env row `OPENAI_OAUTH_TOKEN` (S3 signpost). The two Anthropic env placeholders were removed once the Claude setup-token import shipped — the Claude path now renders as an import-created `local:` `claude_code_oauth` row (token in the token-store), not an env row.

**Per-provider credential list, each row labeled by auth_mode (echoing the driver matrix):**

- **OpenAI**
  - `api_key` rows → masked key prefix only (never full key); standard `api.openai.com`.
  - `chatgpt_oauth` row → "Signed in (ChatGPT subscription)" + session token tally + plan tier; **a visible "compatibility / may break" badge** (B is non-standard). Login = browser-or-paste (§7). Email/account-id **hidden** (redacted).
- **Anthropic**
  - `api_key` rows → masked key prefix; standard `api.anthropic.com`.
  - `claude_code_oauth` row → plan tier (Pro/Max/Team/Enterprise) + token expiry ("expires in N days") + current-month Agent-SDK credit if known; **NO "may break" badge** (C's setup-token path is documented; credit/policy live-verified later, not hardcoded). UI affordance = **"Paste a token you generated with `claude setup-token`"**, NOT "Sign in with Claude". Email/account-id hidden.

**Controls per row:** set-active (single-active per provider already enforced), Verify (calls driver `test()`), delete (`local:` only). **Capability gating:** feature-gate by `(provider, auth_mode, model, capability)` — the agent must NOT assume tool/param support on the ChatGPT backend (see §8 known-broken).

---

## 7. Token storage / refresh / login design

### 7.1 OpenAI `chatgpt_oauth` (borrow Novelloom's mechanism FORM)
Source: `novelloom/.../chatgpt_oauth_tokens.py`, `chatgpt_oauth_login.py`, `openai_chatgpt_oauth.py` (verified).

- **Token record** (mirror `ChatGPTOAuthTokenData`): `access_token, refresh_token, id_token, account_id, expires_at, plan_type, email`. `expires_at` derived from JWT `exp` (fallback `now+10d`). `is_expired = now >= expires_at - 5min`.
- **Refresh-before-every-call.** Both `call_llm`/`stream_llm` begin with `await refresh_if_needed()`; if expired, run blocking refresh via `asyncio.to_thread` and null the cached client so the next call rebuilds `AsyncOpenAI(api_key=<fresh access_token>, base_url=CHATGPT_BACKEND_BASE_URL)`. **This is what keeps token rotation transparent to ArkScope's agent loop.**
- **Refresh wire:** `POST {client_id, grant_type:"refresh_token", refresh_token}` to `https://auth.openai.com/oauth/token`. **Cross-process file lock** (`{path}.lock`, fcntl/msvcrt) to avoid refresh races — ArkScope runs multiple agents sharing one token; keep the lock.
- **Login:** PKCE(S256)+state, loopback callback server (port 1455, `/auth/callback`, dual IPv4/IPv6), **manual-paste fallback**; OR **import `~/.codex/auth.json`** as a zero-friction bootstrap. Constants (`OAUTH_CLIENT_ID="app_EMoamEEZ73f0CkXaXp7hrann"` = Codex CLI's borrowed id, `OAUTH_TOKEN_URL="https://auth.openai.com/oauth/token"`, scopes) reused only if targeting the same backend. *(Borrowed-not-sanctioned — see risks.)*
- **At-rest:** Novelloom uses plain JSON `0600`. ArkScope is local-first and has a **known plaintext-leak history (DB password)** → **DO NOT ship plaintext token files as the default.** Route OAuth tokens through `CredentialStore` with **OS-keychain or encryption**; plaintext `0600` only as an explicit dev fallback.

> **Portable storage seam:** keep Novelloom's `load()/save()/clear()/status()/refresh()` store API and the redacted status payload (only `logged_in/expired/plan_type/expires_at`) for the UI; swap the *backend* from plaintext-JSON to keychain/encrypted-via-CredentialStore.

### 7.2 Anthropic `claude_code_oauth` (DESIGNED — no Novelloom precedent)
- **Token lifecycle differs fundamentally from 7.1.** `claude setup-token` generates a **1-year** token, prints it to terminal, and **does NOT save it**; user copies it. So:
  - **UI affordance = manual paste**, not a browser/loopback flow.
  - **`refresh_if_needed` is effectively a no-op on the token** (1-yr, no refresh-token grant); it only refreshes *observed status* (plan/remaining-credit).
  - **Reuse only the STORE shape** (typed record, `load/save/clear/status`, expiry buffer, file perms / keychain) — NOT the OpenAI endpoints/`client_id`/refresh wire.
- **Call path:** route through the Claude Agent SDK or `claude -p` with `CLAUDE_CODE_OAUTH_TOKEN` set and `ANTHROPIC_API_KEY` unset — **ArkScope's existing `_call_claude_cli` (`code_generator.py:262-307`) is exactly this route** and is the proven seam to generalize. A streaming-tool-loop Anthropic OAuth driver does **not** exist anywhere yet and must be built fresh.
- **Billing/policy caveat:** Agent-SDK monthly-credit numbers + the 2026-06-15 start date were "still moving" (Novelloom doc last-checked 2026-05-16; **today IS 2026-06-15**). **Re-verify before quoting allowances.** Token is inference-only; cannot do Remote Control / Claude.ai web surfaces.

### 7.3 The factory ArkScope ADDS (Novelloom lacks)
A pure switch `build_driver(provider, auth_mode, credential) → AuthDriver` with an explicit fallthrough error for unknown modes (modeled on Novelloom's `_build_default_driver`, but Novelloom forces callers to instantiate classes directly). Resolves the concrete driver from a `CredentialStore` row's `(provider, auth_type)`. **`auth_mode` selects the driver; the specific `credential_id` selects the secret** — keep both axes (the gap §5.2).

---

## 8. Known-broken on the ChatGPT backend (B) — smoke-proven, do NOT assume support

From Novelloom doc-19 real probes (2026-05-22, backend `chatgpt.com/backend-api/codex`):
- `max_output_tokens` → **400** "Unsupported parameter" → **STRIP it**; use prompt guidance for length control.
- `previous_response_id` under `store=false` → **400** "Store must be set to false".
- Non-streaming, `store=true` → unsupported → **force `stream=True` + `store=False`**.
- Files API / Vector stores / Images endpoint / Batches / Embeddings / `file_search` / `code_interpreter` / `computer_use` → **403 HTML / out-of-scope**.
- **Supported (probe-verified):** text, structured output, one inline function-call round-trip, web_search, image input (RGB PNG), inline file_input, responses image gen/edit.
- Model discovery default `GET /models` → 400 missing `client_version`; add Codex-style `extra_query` → nonstandard `models` field (6 ids).

**Implication for ArkScope's 52-tool agent:** before upgrading any capability row to "Supported" on B, it must pass the probe (§9). Standard paths (A, D) are NOT subject to these restrictions.

---

## 9. Falsifiable probe list

Redacted smoke harness discipline (Novelloom `scripts/probe_chatgpt_oauth_backend.py`): record response shape/status/error, **never save tokens/PII**, user-triggered diagnostics only. **Per [[feedback-live-verify-cheap-models]], run live probes on gpt-5.4 / gpt-5.4-mini for cost.**

| # | Probe | Method | PASS | FAIL |
|---|-------|--------|------|------|
| **P1** | **A vs B host distinctness** (kills conflation #1) | Build `AsyncOpenAI(api_key=<an OAuth access_token>, base_url="https://api.openai.com/v1")`, do a 1-token `responses.create`. Then repeat with `base_url="https://chatgpt.com/backend-api/codex"`, `stream=True`, no `max_output_tokens`. | First call **fails** (auth/401-style); second **succeeds** and streams text. Proves the OAuth token is NOT an `sk-` key for `api.openai.com`. | If the first call *succeeds*, our A/B model is wrong — STOP and re-derive. |
| **P2** | **B capability floor** (validates §8 for ArkScope's loop) | Against `chatgpt.com/backend-api/codex`: (a) send `max_output_tokens` → expect 400; (b) one inline function-call round-trip → expect a `*_call` output item; (c) `GET /models` plain → expect 400, then with `extra_query={"client_version":…}` → expect nonstandard `models` field. | (a) 400 "Unsupported parameter"; (b) tool call harvested; (c) plain 400 + extra_query returns ≥1 model id. | Any deviation → update the capability matrix BEFORE marking that capability "Supported"; do not assume. |
| **P3** | **C is the CLI/Agent-SDK route, NOT a raw header** (kills conflation #3) | With `CLAUDE_CODE_OAUTH_TOKEN` set: (a) `claude -p --output-format text "Reply OK"` with `ANTHROPIC_API_KEY` unset → expect a completion (ArkScope's `_call_claude_cli` route). (b) Attempt a raw `Anthropic()` Messages call passing the same token as `x-api-key`/Bearer to `api.anthropic.com`. | (a) **succeeds** (subscription route works); (b) **fails / rejected** — confirming the token is not an `api.anthropic.com` header. | If (b) *succeeds*, the C≠D distinction is wrong — re-derive the Anthropic driver design. |

> P1/P3 are deliberately designed to **fail loudly if the three-realities model is wrong**. P2 is the gate for treating any B capability as usable by the 52-tool loop.

---

## 10. Slice sequence

Build the abstraction first; rewiring is the LAST slice and out of this doc's design scope.

1. **S0 — Contract.** Land `AuthDriver` Protocol + `ResearchProviderDriver` subtype + `LLMRequest/LLMResponse/TokenUsage` + `ArkStreamEvent` (maps to existing `AgentEvent` SSE vocab) as a **PURE INTERFACE + unit tests ONLY** — NOT wired to any route, no production consumer, no behavior change. *(This is the build-first boundary; the agreed next step.)*
2. **S1 — Factory + CredentialStore delta.** `build_driver(provider, auth_mode, credential)`; rename `auth_type` to explicit modes (§5.1, deprecated aliases on read) + widen the `config_routes.py:203` allow-set; add `expires_at`/`account_label` columns; replace `_resolve_api_credential` stub for OAuth with token-store lookup. **Token storage abstracted (keyring-first); no UI yet.**
3. **S2 — Standard drivers (A + D).** `OpenAIApiKeyDriver` (borrow Novelloom) + `AnthropicApiKeyDriver` (DESIGNED — wraps ArkScope's existing raw `Anthropic()` path). Prove parity with current behavior via `test()`. Run **P1** here. Default provider stays `api_key`.
4. **S3 — OpenAI `chatgpt_oauth` (B).** In-app OAuth login + token store + refresh (browser PKCE + localhost callback, manual copy-code fallback; codex-token *import* = **optional dev/bootstrap only — never a runtime fallback or the main UX**; no CLI dependency). Storage: secret → keyring-first token-store, metadata → `CredentialStore` row with `secret`=NULL. Capability matrix. **Run P2 FIRST; only AFTER the probe shows stable streaming + tool-call does the Settings row land** (with the "compatibility / unsupported-by-OpenAI-docs" badge).
5. **S4 — Anthropic `claude_code_oauth` (C).** Generalize `_call_claude_cli` into a streaming-capable driver; manual-paste token store; status-only refresh; **local `MODEL_CATALOG` seed for discovery**. **Run P3 FIRST + live-re-verify Agent-SDK credit policy; Settings row only after P3 passes** (no "may break" badge; UI shows `status: unknown`/plan, no hardcoded credit figures).
6. **S5 — Wire-in (SEPARATE plan).** Route the ~7 bare-client call sites + the Agents-SDK default-client setters through `build_driver`. Touch ONLY client construction. **Explicitly NOT designed here** — gated on S0-S4 + probes passing.

---

## 11. What must NOT be touched

- **Both `run_query_stream` event vocabularies.** `thinking, thinking_content, text, tool_start{tool,input}, tool_end{tool,summary,chars}, done{…}, error` are consumed by `query.py:accumulate_tool_calls` and the client reducer. A driver wraps client construction only; it must NEVER alter loop structure or event shapes.
- **C-2 Research-thread trace + history persistence** (`src/api/routes/query.py`): `valid_thread_id` gating, `build_thread_history` (fetched BEFORE persist), `_persist_{user,assistant,error}_turn` (best-effort), `accumulate_tool_calls`, `ResearchThreadStore`. Untouched.
- **The OpenAI Agents-SDK black-box loop** (`openai_agent/agent.py`): `Runner.run(..., auto_previous_response_id=True)` owns the tool loop and takes **no client object**. Auth there goes through SDK-global default-client setters, NOT a per-call driver-returns-client pattern. Do not attempt to inject a client into Runner.
- **The 52-tool registry + bridges.** Drivers pass tools verbatim; they never enumerate or gate tools (capability gating is a UI/matrix concern, not a registry change).

---

## 12. Out of scope

- Actually rewiring the agent loops / call sites (that is S5, a separate plan).
- Driver method bodies / real implementation code — **this doc stays design-level**; the bodies were since BUILT in S0–S2/S4 (see `src/auth_drivers/`), but their code is not reproduced here.
- A `writer_profiles`-style per-task profile table (ArkScope uses `AgentConfig` + `user_profile.yaml`).
- Real subscription-quota probing (Novelloom proves it's UNKNOWN; we surface honest UNKNOWN + session tallies).
- Workload-identity federation as a *separate* mode (folded under `api_key`/standard for now; note it exists for A and D).

---

## 13. Decisions (RESOLVED 2026-06-15, gpt-5.5 review)

1. **OpenAI subscription path = in-app `chatgpt_oauth` driver; `codex_cli` is NOT a product path.** Default provider stays **`api_key`**; the subscription path is the **compatibility-gated in-app `chatgpt_oauth` driver** — ArkScope itself does the OAuth login / token capture / refresh / store, *borrowing* the Codex OAuth+backend protocol but **NOT depending on or bundling Codex CLI** (a desktop app must never require the user to install Codex CLI). Login + token storage are live-proven; Research wire-in waits for the P1/P2 probe to confirm streaming + tool-call + model-discovery behavior on the ChatGPT backend. **`codex_cli` = dev/debug harness + an optional "import an existing Codex login's token" convenience ONLY** — never a product subscription path, never surfaced as "install Codex CLI to use OpenAI OAuth." **If `chatgpt_oauth` fails, the product fallback is "use an API key," NOT Codex CLI.**
2. **Token at-rest = keyring first, plaintext `0600` dev-fallback allowed (UI-labeled).** Production target = OS keychain / Secret Service / a `keyring` abstraction; dev fallback = plaintext `0600` **but the UI must label it "local plaintext dev storage."** Do **NOT** make the OAuth token in `llm_credentials.secret` (plaintext column) the long-term home.
3. **`auth_type` migration = explicit modes.** Rename/extend to `chatgpt_oauth` / `claude_code_oauth`; keep generic `oauth`/`setup_token` ONLY as deprecated read-aliases. No "generic + sub-mode column" (it perpetuates B/C ambiguity).
4. **Anthropic Agent-SDK credit policy = S4 must live-re-verify.** Today *is* 2026-06-15 (the moving date). **Do NOT write any credit amount / plan allowance into the UI unless confirmed from the official page at that moment.** UI shows `status: unknown` / plan-if-available, never hardcoded figures.
5. **`claude_code_oauth` model discovery = local `MODEL_CATALOG` seed default.** Live discovery (via the Agent SDK, if it has a clean API) is an *optional* probe added later — it must NOT block or gate the auth mode in S4.

---

## Appendix: provenance flags (DESIGNED-not-proven vs borrowed)

| Element | Provenance |
|---------|-----------|
| `AuthDriver` Protocol shape, `LLMRequest/Response`, refresh-before-call, `stream_llm` async-gen gotcha, `StepLimits` | **Borrowed, proven** (Novelloom code; spot-checked). |
| OpenAI `api_key` driver (A) | **Borrowed, proven.** |
| OpenAI `chatgpt_oauth` driver (B): SDK base_url swap, strip `max_output_tokens`, force stream/store=False, PKCE+loopback login, token store/refresh, capability matrix | **Borrowed, proven** (Novelloom code + 2026-05-22 smoke probes). Legitimacy = non-standard/reverse-eng. |
| `(provider, auth_mode) → driver` factory with credential_id binding | **ArkScope ADDS** (Novelloom lacks it; its profiles have no credential linkage). |
| Anthropic `api_key` driver (D-as-driver) | **DESIGNED** — Novelloom has no Anthropic driver; ArkScope's raw `Anthropic()` loop is the seam. |
| **Anthropic `claude_code_oauth` driver (C)** — Agent-SDK/`claude -p` route, manual-paste token, no-op refresh, plan/credit status | **DESIGNED-not-proven.** Grounded ONLY in Novelloom's rationale doc + ArkScope's `_call_claude_cli`. No code to borrow. Legitimacy = setup-token path DOCUMENTED, but third-party-credit amounts/policy UNVERIFIED (live re-verify in S4). |
| Keychain/encrypted at-rest storage (vs Novelloom's plaintext `0600`) | **ArkScope hardening** (local-first + prior leak history). |
| Agent-SDK monthly credit figures / 2026-06-15 start | **MUST re-verify live** (doc was "still moving", checked 2026-05-16). |

---

## Slice 7A — Claude subscription driver: spike result + contract (2026-06-19)

**Falsifiable question:** can `claude -p` produce output mappable to ArkScope's
existing `AgentEvent` vocab? **Answer: YES (proven by a live trivial probe).**

`claude -p --output-format stream-json --verbose` emits NDJSON that maps cleanly:

| stream-json line | → `AgentEvent` |
|---|---|
| `{"type":"system","subtype":"init"/"hook_*"}` | swallow (setup noise) |
| `{"type":"assistant",...content:[{"type":"text"}]}` | `text` |
| `{"type":"assistant",...content:[{"type":"tool_use"}]}` | `tool_start` |
| `{"type":"user",...content:[{"type":"tool_result"}]}` | `tool_end` |
| `{"type":"result","subtype":"success","result":…,"usage":…,"total_cost_usd":…}` | `done` (answer + token_usage + cost) |
| `subtype:"error"` / `is_error:true` / non-zero exit | `error` |

### Two load-bearing findings from the probe (the reason to spike)

1. **Config inheritance is a real hazard.** A bare `claude -p` in this repo
   inherited the dev `.claude/` config — fired the superpowers `SessionStart`
   hook (injected ~29K tokens of skill text), used the dev model
   `claude-opus-4-8`, and **cost $0.17 for a one-word answer.** A production
   Research run MUST isolate from the interactive config. **Fix: `--bare`**
   (CLI: "Minimal mode: skip hooks, LSP, plugins") + an explicit `--model` +
   our own `--system-prompt` (replace, not append) so no dev hook/skill/CLAUDE.md
   leaks in and the routed model is used.
2. **Subscription auth confirmed:** the probe ran with `apiKeySource:"none"`
   (ambient CLI session), proving `claude -p` uses the subscription, not an API
   key — the whole point of this driver.

### Driver contract (`AnthropicClaudeCodeOAuthDriver`)

- **Invocation:** `claude -p --bare --model <routed> --system-prompt <research
  prompt> --output-format stream-json --verbose --max-turns <N> <composed input>`.
- **Auth:** env copy with `CLAUDE_CODE_OAUTH_TOKEN=<token-store token>` set and
  `ANTHROPIC_API_KEY` popped (mirrors `code_generator._call_claude_cli` +
  `claude_oauth_probe`). Token loaded from the token-store by credential_id;
  NEVER from `llm_credentials.secret`, NEVER logged.
- **`stream_llm(request) -> AsyncIterator[AgentEvent]`:** spawn the subprocess,
  read stdout line-by-line, parse each NDJSON line, map per the table, yield the
  existing `AgentEvent`s. A malformed/keepalive line is skipped, not fatal.
- **Lifecycle:** explicit timeout; cancel = terminate the subprocess; non-zero
  exit or `is_error` → one `error` event (no dangling). CLI-missing → clear error.
- **`discover_models`/`test`:** reuse the seed catalog + a trivial `claude -p`
  ping (no API-key discovery for OAuth).

### Slice 7A scope (this slice — NOT full wire-in)

1. `AnthropicClaudeCodeOAuthDriver` with the invocation + NDJSON→AgentEvent
   mapper, behind the factory's `claude_code_oauth` branch (replaces the
   `NotImplementedDriver` placeholder for that mode).
2. **Fake-subprocess TDD** — feed canned stream-json (incl. the init-noise,
   text, tool_use/tool_result, result, and error shapes captured by the probe);
   assert the yielded `AgentEvent` sequence. No live `claude` in unit tests.
3. The live trivial probe (DONE) is the format proof; keep a thin, opt-in live
   smoke (gated, not in the default suite).

**7B (next, gated on 7A):** ~~if the driver is clean, wire it into the Anthropic
branch of `live_anthropic_client` / the Research path so a `claude_code_oauth`
active row runs Research on the subscription (replacing today's explicit env
fallback).~~ **CORRECTED 2026-06-19 (7B-3 §8 BLOCKER):** the SDK driver must **NOT**
be wired into `live_anthropic_client` — that accessor returns a **sync** `Anthropic`
client consumed at 6 `.messages.create/.stream` sites, and a stream-only async
driver cannot replace it. Instead the driver attaches to a **NEW Research-stream
consumer** that calls `stream_llm` (which has **no** live consumer today);
`live_anthropic_client` **stays fail-closed** for OAuth-active. The
CLI-vs-run-manager fragility note is moot now that the runtime is the **in-process
Claude Agent SDK** (not a managed `claude -p` subprocess). See
`docs/design/SLICE_7B3_SDK_DRIVER_DESIGN.md` §8 + §10 OQ-6.

### Slice 7B finding — why a tool bridge is required (bridge MECHANISM SUPERSEDED 2026-06-19)

> **SUPERSEDED — bridge mechanism only.** The *conclusion* of this section — a
> Research turn on the subscription needs a tool bridge to reach ArkScope's
> tools — still holds. The *mechanism* proposed below (an **external MCP server**
> exposed to the CLI via `claude -p --mcp-config`) was **NOT adopted**. The
> Agent-SDK probe (see "Slice 7B Agent-SDK probe — PASSED" below) proved the
> bridge is the **in-process** `create_sdk_mcp_server` — ArkScope tools are
> Python functions registered into the SDK and called back inside ArkScope's own
> process, with **no external MCP server and no `claude -p` subprocess**. Read
> this section as history; the live bridge is the in-process SDK one.

7A proved subscription auth and stream-json mapping, but it also exposed the
runtime boundary: `claude -p` runs in Claude Code, not in ArkScope's Python
agent process.

That means:

- `CLAUDE_CODE_OAUTH_TOKEN` solves authentication/billing only.
- It does not expose ArkScope's ToolRegistry to Claude Code.
- A Research turn through raw `claude -p` can use Claude Code's built-in tools,
  but not ArkScope's financial tools.
- Therefore 7B cannot be a simple "swap `live_anthropic_client` to the driver".
  It needs a tool bridge.

The preferred bridge to probe is MCP because Claude Code already supports MCP
servers via `--mcp-config`. A minimal 7B probe should expose one or two
read-only ArkScope tools, such as `get_sa_feed` and `get_price_change`, and prove:

1. `claude -p --mcp-config <temp-config>` can call an ArkScope MCP tool;
2. stream-json emits `tool_use` / `tool_result` lines that the 7A mapper can
   preserve as `tool_start` / `tool_end`;
3. Claude Code built-in file/shell tools are not accidentally expanded into the
   Research runtime beyond the intended allowlist;
4. token and tool results are redacted/sized according to ArkScope's existing
   tool-trace rules.

~~If an official Claude Agent SDK path later offers a cleaner in-process Python
tool registration API for setup-token auth, it may replace MCP. Until that is
proven, MCP is the pragmatic bridge for making subscription Research equivalent
to API-key Research.~~

**RESOLVED (2026-06-19): it did, and it was adopted.** The Claude Agent SDK's
`create_sdk_mcp_server` registers ArkScope tools in-process; the probe below
proved subscription auth + isolation + an in-process tool call + event mapping.
The external-MCP / `--mcp-config` route above is therefore **not** the bridge —
the in-process SDK bridge replaced it.

### Slice 7B auth/runtime RE-SPIKE result (2026-06-19) — `--bare` is wrong; Agent SDK is the likely path

A re-spike (gpt-5.5 finding + empirical test + doc verification via the
claude-code-guide agent) overturned a 7A assumption:

**`claude -p --bare` does NOT read `CLAUDE_CODE_OAUTH_TOKEN`.** Official docs
(headless.md / authentication.md): *"Bare mode skips OAuth and keychain reads.
Anthropic authentication must come from `ANTHROPIC_API_KEY` or an `apiKeyHelper`…
`--bare` does not read `CLAUDE_CODE_OAUTH_TOKEN`."* Empirically confirmed (ambient
login, `ANTHROPIC_API_KEY` popped, same prompt):

| invocation | result |
|---|---|
| `claude -p` **non-bare** + `--setting-sources project,local` | `apiKeySource:none`, answered OK (subscription) |
| `claude -p` **`--bare`** + same | `apiKeySource:none`, **"Not logged in"**, cost 0 |

Consequences:
- The 7A driver's `claude -p --bare` (commits c0d783f/cc3998d) **cannot
  authenticate the subscription** — the 7A-2 "Not logged in" was `--bare`, not
  (necessarily) an expired token. The driver's stream-json→AgentEvent mapper +
  token-store injection are still correct and reusable; the **invocation must
  drop `--bare`**.
- Isolation: `--setting-sources project,local` drops the global `user` hook but,
  run in the repo cwd, the *project* `.claude`/CLAUDE.md still loaded (cost $0.14
  for "OK"). Full isolation needs a neutral cwd or `setting_sources=[]`.

**The Agent SDK is the likely-better runtime** (claude-code-guide, doc-cited):
the Python `claude_agent_sdk` exposes `create_sdk_mcp_server()` for **in-process
custom tools** (no external MCP process), `setting_sources=[...]` isolation, and
an `allowed_tools` allowlist — directly solving "claude -p has no ArkScope
tools." Caveats: (a) `claude_agent_sdk` is NOT currently a dependency (the
`claude` binary IS present); (b) subscription auth via `CLAUDE_CODE_OAUTH_TOKEN`
through the SDK is LIKELY (auth fallback chain) but NOT explicitly documented —
must be probed.

**Runtime fork to decide before building 7B (the tool bridge):**

| | CLI: `claude -p` (non-bare) + `--mcp-config` | Python Claude Agent SDK |
|---|---|---|
| Dependency | `claude` binary (already here) | add `claude-agent-sdk` Python pkg |
| ArkScope tools | external MCP server process | **in-process** `create_sdk_mcp_server` |
| Isolation | `--setting-sources` + neutral cwd | `setting_sources=[...]` (explicit) |
| Subscription auth | proven (non-bare) | likely, undocumented — probe first |
| Events | stream-json (7A mapper reusable) | iterate messages / `ToolUseBlock` |

Recommended next: a tiny Agent-SDK auth probe (does `claude_agent_sdk.query` +
`CLAUDE_CODE_OAUTH_TOKEN` authenticate the subscription with `setting_sources`
isolation?). If yes → prefer the SDK (in-process tools). If no → fix the CLI
driver (drop `--bare`, neutral cwd) + an external MCP server. Do NOT build the
7B tool bridge until this fork is resolved.

### Slice 7B Agent-SDK probe — PASSED (2026-06-19); SDK is the product runtime

Standalone probe (`claude_agent_sdk` 0.2.105, did NOT touch the Research path),
all 4 conditions met:

1. **Subscription auth, no API key.** `CLAUDE_CODE_OAUTH_TOKEN` set,
   `ANTHROPIC_API_KEY` popped, `CLAUDE_CONFIG_DIR`=empty → the only possible auth
   was the subscription token; `query()` completed (`is_error: False`). (Both
   stored tokens — local:1 + local:6 — independently verified valid; the earlier
   "Not logged in" was the `--bare` bug, NOT an expired token.)
2. **Isolation.** `setting_sources=[]` + empty `CLAUDE_CONFIG_DIR` → no
   superpowers/SessionStart hook in the stream (the $0.17 pollution gone).
3. **In-process custom tool CALLED.** `create_sdk_mcp_server(tools=[get_sa_feed])`
   + `allowed_tools=["mcp__ark__get_sa_feed"]` + `permission_mode="bypassPermissions"`
   → the Python tool function actually executed in-process and its sentinel
   return became the agent's answer. **No external MCP server / managed subprocess.**
4. **Event mapping.** SDK messages (AssistantMessage{TextBlock,ToolUseBlock} /
   UserMessage{ToolResultBlock} / ResultMessage) map to the existing AgentEvent
   vocab (text / tool_start / tool_end / done; is_error → error).

**Decision:** the Python **Claude Agent SDK is the product runtime** for
`anthropic/claude_code_oauth`. The 7A `claude -p --bare` driver is superseded
(its `--bare` can't auth the subscription anyway) — keep it only as an
experimental/dev-diagnostic or remove it. Its stream→AgentEvent mapping concepts
carry over to the SDK driver.

**Next (7B build, gated):** rebuild `AnthropicClaudeCodeOAuthDriver` on the Agent
SDK — `ClaudeAgentOptions(mcp_servers={ark: create_sdk_mcp_server(...)},
allowed_tools=[...], setting_sources=[], model=..., system_prompt=...,
permission_mode=...)`, token via `CLAUDE_CODE_OAUTH_TOKEN` (pop
`ANTHROPIC_API_KEY`), an ArkScope-tools→SDK-tool bridge from the ToolRegistry
(read-only allowlist first), and message→AgentEvent mapping. Add
`claude-agent-sdk` to deps. Still gated: the 7B-3 formal design (tool allowlist,
arg schemas, timeout, secret redaction, disabling Claude Code's built-in
Bash/Edit) before wiring into Research (7B-4).

### Slice 7B-3 — formal design COMPLETE (2026-06-19) → `docs/design/SLICE_7B3_SDK_DRIVER_DESIGN.md`

The formal tool-bridge/driver design is written and adversarially reviewed (9-agent
workflow: 4 grounded-research → synthesis → 3 skeptic reviewers → revision). It is
**DESIGNED-not-proven** and **gated on human + gpt-5.5 review before any build**.
Headline findings (all grounded; see the design doc for citations):

- **Integration BLOCKER (reshapes 7B-4):** `live_anthropic_client()` is a **sync**
  `Anthropic` client called at 6 sites via `.messages.create/.stream`
  (`card_synthesis.py:146,464`; `anthropic_agent/agent.py:367,372`; `subagent.py`,
  `compressor`, `code_generator`, `cli`). The SDK driver is **async, stream-only**
  (`stream_llm`, no `.messages`) and **cannot** be dropped into those sites.
  Plan: build a NEW `AnthropicClaudeCodeSdkDriver` class, repoint only the factory,
  leave `live_anthropic_client` fail-closed, and **build the Research-stream consumer**
  (which would call `stream_llm`) — it does NOT exist on the live path yet
  (`stream_llm` has 0 consumers outside `auth_drivers/`). Live flip = prerequisite, not a guard flip.
- **The locked surface is enforced by the bundled CLI binary (2.1.183), not the
  Python SDK 0.2.105** — and the probe only exercised the **fail-OPEN** config
  (`bypassPermissions`, no `tools=[]`, no hook). §9's negative tests are BLOCKING gates re-run on any CLI bump.
  **✅ UPDATE 2026-06-19: the permission spike PASSED on Option 2 (`dontAsk` +
  `tools=[]` + allowlist)** — init `tools` list = only the ArkScope tool (built-ins
  stripped), `apiKeySource='none'`, CLI 2.1.183. **F1 PROVEN, F10 disproven.** No
  `bypassPermissions` / no hook needed; the Option-1 hinge is MOOT.
- **Token-leak vector corrected:** the real path is an **uncaught bridge-handler
  exception** (`query.py:716-721` echoes `str(e)` into model context), not
  `ProcessError.stderr` — the bridge handler needs a hard `try/except BaseException`
  + redaction; redaction (`_redact_bridge` = exact-token ∘ `probe_harness.redact`) is load-bearing, not optional.
- **Permission posture = `dontAsk` (Option 2), VALIDATED 2026-06-19:** fail-closed
  at the permission layer (anything not allow-listed is auto-denied) over `tools=[]`
  + the Tier-1 allowlist + the §4 Python-side in-process veto. **`bypassPermissions`
  is NOT used** — it was the Option-1 fallback, now moot.
- **6 open questions need a human decision** before build: web-egress posture (default:
  no web v1), the 5 §3 allowlist ambiguities (incl. `get_report` confirmed path
  traversal, `get_portfolio_analysis` holdings PII), `synthesize_signal` policy
  exclusion, model-facing redaction residual (OQ-5), Option-1-vs-2 permission posture,
  and whether the sync `.messages` sites ever get a subscription path (OUT of 7B-3).

Tier-1 allowlist (11 read-only tools): `get_sa_feed`, `get_sa_digest`,
`get_sa_alpha_picks`, `get_ticker_news`, `get_news_brief`, `search_news_advanced`,
`get_ticker_prices`, `get_price_change`, `get_fundamentals_analysis`,
`get_sec_filings`, `get_economic_calendar`.

### 7B-4/5/6 — BUILT + LIVE-VALIDATED (2026-06-20)

The SDK driver shipped as a NEW class **`AnthropicClaudeCodeSdkDriver`**
(`src/auth_drivers/claude_code_sdk_driver.py`, `5f0ea35`); the factory `(anthropic,
claude_code_oauth)` branch was repointed to it (`e52d38f`); and the **Research-stream
consumer now EXISTS** — `_anthropic_subscription_stream` + the `/query/stream` anthropic
branch (`2a0a383`). Live-smoked (driver-level + route-helper): real `get_sa_feed` on the
subscription, built-ins absent, `apiKeySource='none'`, no token leak; GUI hand-test passed
(7B closed 2026-06-20). So the "Next (7B build, gated)" entry above is **DONE** — and it
became a NEW class, not a rebuild of the superseded `--bare` `AnthropicClaudeCodeOAuthDriver`.
Full detail: `docs/design/SLICE_7B3_SDK_DRIVER_DESIGN.md` §8. **NEXT overall = S3 (OpenAI
`chatgpt_oauth`), probe-first (P1/P2).**

### S3 — OpenAI `chatgpt_oauth` probe runner BUILT (offline TDD) (2026-06-20)

The P1/P2 probe runner is built and unit-tested with a **fake transport** (no live
call): `src/auth_drivers/chatgpt_oauth_probe.py` + `tests/test_chatgpt_oauth_probe.py`.
It mirrors `claude_oauth_probe.py` — DI'd probe bodies + a monkeypatchable
`_openai_client` seam + shape-only observations through the `probe_harness` redaction —
and uses the SYNC `OpenAI` client so it is route-safe. Grounded in Novelloom's PROVEN
probe/driver: base_url swap to `https://chatgpt.com/backend-api/codex` with the OAuth
access_token as the SDK api_key and **NO custom headers**; `max_output_tokens` is sent
RAW with the same required `instructions` + low-reasoning shape as the successful
Novelloom smoke so the probe measures the backend's 400 rather than a missing-field
validation error; a flat Responses-API function tool → `*_call` item; model discovery via
`extra_query={"client_version": "0.0.0"}` → ids in the nonstandard `models` field. The
OpenAI-B path carries the **"compatibility product path, not public API host"** label
(reverse-engineered, TOS-sensitive) — distinct from the Anthropic OAuth path, which is
documented/sanctioned.

**Live P1/P2 first run (2026-06-21, user hand-test):** P1 passed (standard
`api.openai.com` rejected the OAuth token; ChatGPT backend streamed) and P2c passed
(models list with `client_version` returned 4 ids). P2a failed because the ArkScope probe
omitted `instructions` and hit backend request validation before `max_output_tokens`; fixed
in the probe shape. P2b returned no function-call output item; fixed to align the request
with Novelloom's low-reasoning shape and to report output/event types on failure. **S3
driver wire-in remains gated on a re-run of the live probe after these fixes.**

**Live P1/P2 second run (2026-06-21, user hand-test):** P1, P2a, and P2c passed. P2b
still displayed failed, but its event trace included `response.function_call_arguments.*`
and `response.output_item.*` events while `response.completed` omitted `response.output`.
That proves the backend emitted a function call; the failure was the probe parser looking
only at terminal output. Fixed: P2b now passes on either terminal `*_call` output items OR
streamed function-call item/argument events.

**Probe display/model inventory polish (2026-06-21):** P2c now includes the discovered
model ids in the redacted observed text (capped at 20 for readability), and Settings shows
a compact four-row summary: Token/backend · parameter compatibility · tool call · available
models. Raw `expected/observed/error` detail is kept behind a disclosure control. The
button label stays short; the visible explanation says the probe sends minimal diagnostics
to `api.openai.com` and the ChatGPT backend, never returns a token, and may consume a small
amount of subscription/backend quota.

### S3-auth design correction — product path = ArkScope's OWN in-app OAuth (2026-06-20)

Locked after a design pushback (a "import from `~/.codex/auth.json` first" suggestion was a
drift; §10 S3 + §13 #1 already decided in-app OAuth — this re-affirms + sharpens it):
- **Product path = ArkScope's OWN in-app OAuth login.** A Settings button starts the flow
  (PKCE + localhost callback, with a manual copy-code fallback); ArkScope captures
  access_token / refresh_token / expires_at / account metadata, stores them, and refreshes
  before each call. This is THE `chatgpt_oauth` path — no Codex CLI install is ever required.
- **`~/.codex/auth.json` import = optional dev/bootstrap convenience ONLY** — never the main
  UX, never a runtime fallback. If `chatgpt_oauth` fails at runtime, the product fallback is
  "use an API key," not Codex CLI (§13 #1).
- **Storage = the existing two-store split (REUSE; do NOT add a 3rd store).** The secret
  (access/refresh token, expires_at, account metadata) → the **token-store** (keyring-first;
  plaintext-JSON `0600` only as the UI-labeled dev fallback). The credential METADATA row
  (provider, auth_type, alias, active, expires_at, account_label) → SQLite `llm_credentials`
  with `secret` = **NULL**. NEVER the `llm_credentials.secret` column (§13 #2; the project has
  a plaintext-secret leak history). This is exactly how the Claude `claude_code_oauth` path
  already stores tokens, and the write path (`add_oauth_credential` + `token_store.save`,
  with rollback) is already provider-generic — so **S3's new work is the OAuth login
  FRONT-END (PKCE/callback/exchange), not storage.**
- **Build order:** design-correction (this) + P1a auth-class narrowing → in-app OAuth login
  skeleton → live P1/P2 probe (gated on a real token in the store) → driver + Research
  wire-in (only after live P1/P2 pass; fallback policy explicit — never a silent paid
  API-key fallback).

**P1a narrowing — DONE** (`chatgpt_oauth_probe.py`): the standard-host call counts as a
"rejected" PASS **only** for an auth-class error (HTTP 401/403). A network/timeout, 404
model_not_found, 400 unsupported-parameter, or 429 rate-limit is **inconclusive → NOT a
pass** (a transient error must not masquerade as the A≠B proof). The rejection is labelled
by type+status (never the error message), and all probe output stays redacted. 22 tests in
`tests/test_chatgpt_oauth_probe.py`.

### S3 — in-app OAuth login design + fallback boundaries (Option 2) (2026-06-20)

Product login flow, grounded in Novelloom's proven `chatgpt_oauth_login.py`; ArkScope runs
its OWN flow (no Codex CLI). Per the user: loopback-localhost primary + a NARROW copy-code
fallback.

**OAuth params (Codex-compatibility — borrowed client registration):**
- `client_id = app_EMoamEEZ73f0CkXaXp7hrann` (the Codex app id; OpenAI exposes no third-party
  ChatGPT-OAuth app registration — THIS borrowing is the "compatibility / reverse-engineered"
  crux, accepted in §13 #1).
- authorize `https://auth.openai.com/oauth/authorize`, token `https://auth.openai.com/oauth/token`.
- `redirect_uri = http://localhost:1455/auth/callback` — FIXED by the borrowed client_id, so
  the loopback MUST bind `:1455`. scopes `openid profile email offline_access
  api.connectors.read api.connectors.invoke`; PKCE **S256**; authorize extras
  `id_token_add_organizations=true`, `codex_cli_simplified_flow=true`, `originator=arkscope`.
- access_token expiry from its JWT `exp`; account_id/plan/email from id_token claims; refresh
  = `grant_type=refresh_token` (5-min expiry buffer).

**Routes / structure** (offline-TDD-able CORE in `chatgpt_oauth_login.py`; routes are thin
wrappers; the loopback HTTP server + Settings UI are thin transport on top):
1. `POST /config/credentials/openai/oauth/start` → gen state + PKCE verifier/challenge, put
   {verifier, expires_at} in a short-TTL **in-memory** state store (NEVER the token-store),
   return `{auth_url, state, expires_at, manual_code_supported: true}`.
2. `POST .../oauth/callback` (loopback delivers code+state) → validate state → exchange
   code+verifier → write CredentialStore metadata row + token-store → **no token in the response**.
3. `POST .../oauth/complete-manual` (paste the redirect URL/code) → the SAME validate →
   exchange → store path.
4. `refresh_if_needed(credential_id)` → refresh only when expired (buffer); a per-credential
   refresh lock serializes concurrent refreshes; on failure the credential status is visible —
   never a silent fallback.

**OAuth Login Fallback boundaries (the copy-code fallback is NARROW):**
1. **Primary = loopback localhost** — Settings "登入 ChatGPT" → state+PKCE → open browser →
   `127.0.0.1:1455/auth/callback` → auto-exchange → store.
2. **Copy-code handles ONLY callback-transport failure** (the user finished the browser login
   but ArkScope never got the localhost callback). It is NOT a second auth mode; it changes
   nothing about provider/token-store/refresh/metadata; the ONLY difference is the auth code
   arrives by paste instead of by callback.
3. **Copy-code MUST NOT mask OAuth/token errors — these all FAIL, no fallback:** state mismatch ·
   PKCE verifier mismatch · token exchange 400/401 · refresh-token missing or refresh failure ·
   scope/account/workspace mismatch · probe P1/P2 not passing · token-store write failure
   (→ rollback, fail).
4. **No fallback to Codex CLI** (no install requirement; `~/.codex/auth.json` import = dev
   convenience only, not a login fallback).
5. **No automatic fallback to an API key** — a failed ChatGPT-OAuth login does NOT silently use
   `OPENAI_API_KEY`; whether runtime API-key fallback is allowed is a later explicit
   fallback-policy setting. The login flow only obtains a `chatgpt_oauth` token.
6. **UI:** primary button "登入 ChatGPT"; waiting screen "等待瀏覽器登入完成…"; fallback entry
   "沒有自動返回？手動貼上授權碼" with copy "只在瀏覽器已完成登入但本機 callback 沒收到時使用".

**Offline TDD (no browser, no OpenAI):** token exchange + refresh go through monkeypatchable
seams; the state store + write path use injectable stores. Tests cover state mismatch, expired
state, exchange-error (400/401) no-fallback, incomplete-token, token-store write-fail rollback,
no-token-echo, and the refresh path.

### S3 thin transport — backend BUILT + audited (2026-06-20)

Backend transport for the in-app login. Three new modules + routes, TDD'd:
- `chatgpt_oauth_callback_server.py` — ephemeral loopback that captures the one
  `GET /auth/callback` on **127.0.0.1:1455** (GET-only, exact-path), **explicit fail on
  port-in-use (no fallback port)**, cancel/timeout. Localhost integration tests.
- `chatgpt_oauth_manager.py` — `OAuthLoginManager`: `begin()` (mint state+PKCE, **bind
  the loopback callback server before returning auth_url**, then spawn the wait thread)
  → `status()` poll (pending/success/error/unknown) → `complete_manual()` copy-code
  fallback. Single-use state ⇒ no double token-exchange; sticky success; results return
  MASKED metadata only. Binding first is required: a fast browser redirect can otherwise
  hit `localhost:1455` before the listener exists and produce `ERR_CONNECTION_REFUSED`.
- `config_routes.py` — `POST /config/credentials/openai/oauth/start`, `GET …/status`,
  `POST …/complete-manual` (bare code or redirect-URL extract + state-match guard); the
  `…/{id}/probe` route widened to dispatch openai `chatgpt_oauth` → P1/P2. Write-gated;
  responses never carry a token. `get_oauth_login_manager` singleton (in-memory login state).

**Adversarial transport audit (4 skeptics):** token/PII egress, loopback CSRF/binding, and
fallback-discipline all **clean** (127.0.0.1-only, 256-bit single-use state is sufficient
CSRF, no silent fallback port/credential/API-key anywhere). Two real lifecycle defects found
and FIXED: (1) a bind→register window let a manual completion leave the loopback holding
:1455 for the full timeout; this was first fixed with a cancellation marker, then simplified
after `begin()` was changed to bind+register before returning the auth URL (the marker became
dead code and was removed); (2) the singleton's `_results` grew unbounded → fixed with TTL +
cap eviction; (3) hand-testing found a browser-redirect race → fixed by binding the loopback
before returning the auth URL. 187 auth+route tests passed at the original transport gate;
later S3 checks cover the race fix.

### S3 Settings UI — BUILT (2026-06-20)

Frontend login surface in `apps/arkscope-web` (gpt-5.5 commit #2). `api.ts` gains the
`startOpenAIOAuth` / `openAIOAuthStatus` / `completeOpenAIOAuthManual` clients; the
flow logic is extracted to `chatgptOAuth.ts` (`pollOAuthStatus` state machine —
pending→success/error/unknown/timeout; `buildManualCompletion` — code-vs-redirect-URL),
unit-tested with injected clock/statusFn (no DOM/network), mirroring `researchProvider.ts`.
`Settings.tsx` ProviderSection gains an OpenAI block: 「登入 ChatGPT」 → system-browser open
+ loopback poll → on success refresh the credential list; a copy-login-link button and a
NARROW copy-code fallback ("沒有自動返回？手動貼上授權碼" → `complete-manual`); the probe
button (`實測 OAuth`) widened to `chatgpt_oauth`; the probe result explains the real
diagnostic calls and displays available ChatGPT-backend model ids from P2c. Copy marks it
**ChatGPT backend compatibility, NOT an API key**; a backend error surfaces as-is (no silent
fallback); the auth_url is opened/copied, never rendered as text. **20 chatgptOAuth vitest +
FE tests pass, tsc + vite build clean.** Test approach = vitest + injected fakes
(the project has no Playwright; introducing it would be its own infra slice).

**Desktop-shell requirement (2026-06-21 hand-test fix):** Electron must open the OAuth
authorize URL in the user's default system browser via `shell.openExternal`, never inside an
ArkScope `BrowserWindow`. The redirect target is the fixed loopback callback
`http://localhost:1455/auth/callback`; loading it inside Electron can fail with
`ERR_CONNECTION_REFUSED` and is also a worse login UX. Same-origin ArkScope navigation stays
inside the shell; cross-origin HTTP(S) navigation opens externally.

**Still HELD (gated on user): re-run LIVE P1/P2 after the 2026-06-21 probe-shape fixes.**
Login + token storage are live-proven; S3 driver wire-in waits for the corrected live probe.
