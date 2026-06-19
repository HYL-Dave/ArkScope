# LLM Auth Driver Plan

> **Status:** DESIGN ONLY (no code). Drafted + gpt-5.5-reviewed, all §13 decisions RESOLVED 2026-06-15. **Next step = S0 (the `AuthDriver` contract — pure interface + unit tests, NOT wired to any route).** Grounded in Novelloom's auth subsystem (`/mnt/md0/PycharmProjects/novelloom/src/novelloom/shared/auth/`, `docs/14_llm_access_and_auth.md`, `docs/19_chatgpt_oauth_backend_compatibility.md`) and ArkScope's current auth surface (`src/model_credentials.py`, `src/tools/code_generator.py`, `src/api/routes/config_routes.py`, `src/agents/{anthropic,openai}_agent/agent.py`, `src/api/routes/query.py`). Authored via an Opus-4.8 workflow (4 grounded readers → synthesis) + a spot-check of the load-bearing Novelloom claims (base_url / token-as-api_key / Protocol shape verified against source).
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
| **Claude setup-token** (`anthropic/claude_code_oauth`) | Outside ArkScope, in a `claude -p` subprocess / Claude Code runtime | `claude -p` sees Claude Code's tool world, not ArkScope's Python functions | **Yes** — MCP or an equivalent tool bridge is required |
| **OpenAI ChatGPT-OAuth** (`openai/chatgpt_oauth`) | Still the OpenAI SDK shape, but pointed at the ChatGPT backend compatibility host | If the compatibility backend supports function/tool calls, ArkScope can keep owning the tool loop/bridge shape; this must be proven by P2 | **Probe-gated**, not assumed |

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
| anthropic | `claude_code_oauth` | `AnthropicClaudeCodeOAuthDriver` | Claude subscription (Agent-SDK credit) | Claude Agent SDK / `claude -p` with `CLAUDE_CODE_OAUTH_TOKEN` set, `ANTHROPIC_API_KEY` unset (generalize ArkScope's existing `_call_claude_cli` route) | **DOCUMENTED path; credit policy unverified; DESIGNED-not-proven** | Med-High — no Novelloom precedent; Agent-SDK/CLI route only; credit policy must be live-re-verified. |

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
4. **S3 — OpenAI `chatgpt_oauth` (B).** In-app OAuth login + token store + refresh (browser/paste; optional codex-token *import*, no CLI dependency) via keychain-backed `CredentialStore`. Capability matrix. **Run P2 FIRST; only AFTER the probe shows stable streaming + tool-call does the Settings row land** (with the "compatibility / unsupported-by-OpenAI-docs" badge).
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
- Driver method bodies / real implementation code (DESIGN ONLY).
- A `writer_profiles`-style per-task profile table (ArkScope uses `AgentConfig` + `user_profile.yaml`).
- Real subscription-quota probing (Novelloom proves it's UNKNOWN; we surface honest UNKNOWN + session tallies).
- Workload-identity federation as a *separate* mode (folded under `api_key`/standard for now; note it exists for A and D).

---

## 13. Decisions (RESOLVED 2026-06-15, gpt-5.5 review)

1. **OpenAI subscription path = in-app `chatgpt_oauth` driver; `codex_cli` is NOT a product path.** Default provider stays **`api_key`**; the subscription path is the **experimental in-app `chatgpt_oauth` driver** — ArkScope itself does the OAuth login / token capture / refresh / store, *borrowing* the Codex OAuth+backend protocol but **NOT depending on or bundling Codex CLI** (a desktop app must never require the user to install Codex CLI). `chatgpt_oauth` only becomes a real default once its probe (P2/S3) shows streaming + tool-call are stable. **`codex_cli` = dev/debug harness + an optional "import an existing Codex login's token" convenience ONLY** — never a product subscription path, never surfaced as "install Codex CLI to use OpenAI OAuth." **If `chatgpt_oauth` fails, the product fallback is "use an API key," NOT Codex CLI.**
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

**7B (next, gated on 7A):** if the driver is clean, wire it into the Anthropic
branch of `live_anthropic_client` / the Research path so a `claude_code_oauth`
active row runs Research on the subscription (replacing today's explicit env
fallback). If the CLI lifecycle proves fragile in the page-owned stream, stop at
"driver ready" and fold the wire-in into the server-owned run manager instead
(per `AI_RESEARCH_RUN_LIFECYCLE_PLAN.md`, whose §7.3 already flags the CLI as a
distinct runtime).

### Slice 7B finding — why MCP / equivalent bridge is required

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

If an official Claude Agent SDK path later offers a cleaner in-process Python
tool registration API for setup-token auth, it may replace MCP. Until that is
proven, MCP is the pragmatic bridge for making subscription Research equivalent
to API-key Research.

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
