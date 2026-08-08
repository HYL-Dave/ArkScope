# OAuth Lifecycle and Subscription Usage Truth

> **Status:** LIVE COMPLETE
> **Date:** 2026-08-08
> **Base:** `7257699171a81294b74ff8cde61fb90bb065a2b4`
> **Merged implementation tip:** `02f1e588c6f9d91d4710627de3699a821e0bda6f`
> **Scope:** subscription credential lifecycle truth, non-secret telemetry, and
> bounded account-usage synchronization. This document does not authorize
> implementation.

## 1. Purpose

The Settings provider surface currently answers several different questions
with one `available` boolean:

- is a credential row configured;
- is its token present;
- is its access token current;
- can refresh repair it;
- does only a new login repair it; and
- is subscription quota available.

Those are not equivalent. The user-visible result is an OAuth row that can look
available after its displayed expiry is stale, then fail only when a task runs.
The same surface has no durable account quota or reset-time witness even when
the provider transport already exposes one.

This slice makes credential state and subscription usage explicit without
performing hidden model calls or changing model routing.

## 2. Grounded facts

### 2.1 Current repository behavior

1. `src/model_credentials.py::provider_credentials()` projects every local DB
   row with `available=True`, without reading the token store or evaluating
   `expires_at`.
2. Provider and model selection then use that boolean. In particular,
   `ProviderSection.tsx` derives the active credential, provider pill, setup
   collapse, and discovery choices from `available`.
3. ChatGPT OAuth secrets and live token metadata are in the token store;
   `llm_credentials` separately stores `expires_at` and `account_label`.
4. `chatgpt_oauth_login.refresh_if_needed()` rotates and saves only the token
   record. It does not update the credential DB metadata.
5. Re-login does update both stores, but automatic refresh and re-login
   therefore have different metadata effects.
6. The existing per-credential lifecycle lock is process-local. Two sidecars
   sharing the same profile/token store can still race a rotating refresh token.
7. ChatGPT refresh errors already distinguish transient transport failures from
   typed `reauth_required` failures in the execution/discovery driver, but that
   distinction is not a durable Settings state.
8. `AnthropicClaudeCodeSdkDriver` receives typed `RateLimitEvent` objects and
   deliberately drops them in its catch-all ignore branch.
9. Every driver's `get_quota_status()` currently returns `status="unknown"`.

### 2.2 2026-08-08 ChatGPT Plus account experiment

The experiment used ArkScope's active `openai/chatgpt_oauth` credential through
Codex app-server `0.147.0` external-token mode in an isolated temporary
`CODEX_HOME`. It did not replace the developer's normal Codex CLI login and did
not start a thread or turn.

Observed account state:

- plan: `plus`;
- seven-day `usedPercent`: `100`;
- status: `rate_limit_reached`;
- credits balance: `0`, `hasCredits=false`, `unlimited=false`;
- reset: `2026-08-09 07:13:45 Asia/Taipei`.

Five consecutive `account/rateLimits/read` requests succeeded with identical
snapshots while the subscription could not run another model turn. An
`account/usage/read` snapshot before and after those five requests was
byte-equivalent at the decoded-data level; `lifetimeTokens` stayed
`14,243,654,879`. This is strong operational evidence that the account read is
a control-plane request and does not consume model-token/subscription inference
quota. It is not a promise that network requests are unlimited or free of an
independent service rate limit.

The same experiment forced a normal expired-token refresh. The token-store
expiry advanced from `2026-08-03T04:29:17+00:00` to
`2026-08-17T18:19:16+00:00`, while the credential DB expiry remained at the old
date. This proves metadata drift; it does not by itself prove the cause of every
past re-login prompt.

Official protocol reference (retrieved 2026-08-08):
<https://developers.openai.com/codex/app-server/>. The documented methods are
`account/rateLimits/read` and `account/usage/read`; external
`chatgptAuthTokens` remains experimental.

## 3. Locked decisions

### LD 1 - One owner per fact

For subscription credentials:

| Fact | Authority |
|---|---|
| row id, provider, auth mode, user alias, active selection | `llm_credentials` |
| token presence, token expiry, refresh-token presence, provider plan/account metadata | token store |
| last refresh attempt/success/error and account observations | new non-secret profile telemetry |
| live model visibility | existing credential-scoped discovery cache |

The API must not use the DB copy of ChatGPT token expiry as execution truth.
The compatibility column may remain during migration, but Settings projection
must read the token-store value. A successful automatic refresh must therefore
be visible immediately without a second metadata write.

No access token, refresh token, id token, raw account id, raw response header,
or unredacted provider error may enter SQLite, logs, API responses, or frontend
state.

### LD 2 - Closed lifecycle state set

OAuth rows expose one typed `lifecycle_state`:

| State | Meaning | Retry affordance | `available` compatibility view |
|---|---|---|---|
| `ready` | local token evidence is present and not expired | none | `true` |
| `refresh_required` | access token is expired/inside buffer and a refresh token exists | sync/automatic refresh | `false` |
| `refresh_failed_retryable` | last refresh failed transiently; retry may work | retry | `false` |
| `reauth_required` | token missing, refresh token missing, or provider rejected refresh as terminal | re-login | `false` |
| `unverifiable` | token store/protocol/status could not be read safely | retry diagnostics, not re-login by assumption | `false` |

`available` becomes a derived backwards-compatibility field, never a parallel
authority. An expired token must not remain `available=true`.

The state means "locally ready to attempt this auth channel", not entitlement,
model visibility, quota, or proof that the next provider call will succeed.
Those remain separate fields.

### LD 3 - Refresh outcomes are durable, bounded telemetry

Store only the latest non-secret lifecycle witness per credential:

- `last_refresh_attempt_at`;
- `last_refresh_success_at`;
- `last_refresh_error_at`;
- stable `last_refresh_error_code`;
- bounded redacted diagnostic text;
- `updated_at`.

Required error classes include at least `transport_error`, `invalid_grant`,
`missing_token`, `missing_refresh_token`, `token_store_unavailable`, and
`protocol_incompatible`. Unknown exceptions remain `unverifiable`; they may not
be guessed into `reauth_required`.

### LD 4 - One cross-process lifecycle critical section

Refresh, re-login completion, and delete for the same credential must share a
profile-local inter-process advisory lock in addition to the current in-process
lock. The lock covers read-current-record -> mutate token/cache/metadata ->
record outcome. Browser interaction and authorization-code exchange remain
outside it.

The lock is bounded and fail-closed. A timeout yields a typed busy/retryable
result; it never falls back to an unlocked write. Tests must use two real
processes and prove that a rotating refresh token is consumed once, a delete
cannot be followed by resurrection, and every file descriptor is released on
success and failure.

### LD 5 - ChatGPT account synchronization is automatic but bounded

`account/rateLimits/read` is an active control-plane read, not a passive event.
Because the 2026-08-08 exhausted-account control shows no model-token usage, v1
may invoke it automatically under this exact policy:

1. after successful login, re-login, or automatic refresh;
2. when Settings -> Providers becomes visible and the credential-bound snapshot
   is absent or older than five minutes;
3. when the app regains focus while that section is visible and the snapshot is
   older than five minutes; and
4. from a user-visible refresh button, with a ten-second single-flight cooldown.

There is no hidden interval poll while the section is not visible. Countdown
labels derive locally from the last reset timestamp. Multiple callers for one
credential share one in-flight sync.

If a future official app-server execution path emits
`account/rateLimits/updated`, that event may update the same snapshot without an
extra read. V1 must not claim this passive path exists when execution still uses
the current direct subscription driver.

### LD 6 - Quota and token activity preserve source semantics

The credential-bound account snapshot records:

- direct rate-limit fields: status, used percentage, window duration, reset
  timestamp, reached type, credits/overage fields when present;
- `observed_at`, source, credential id, auth mode, and a non-reversible account
  fingerprint used only for same-account validation;
- bounded `account/usage/read` summary fields and a bounded recent daily series.

The UI labels direct `usedPercent` as **已用**. If it also shows remaining
percentage, that value is explicitly labeled **推算** (`100 - usedPercent`).
Missing fields display **未知**. They are never converted to zero.

Snapshots from a different credential/account must not be displayed after an
active-credential switch. Historical snapshots may remain stored but are keyed
by credential identity and account fingerprint.

### LD 7 - Experimental Codex app-server use is optional and fail-closed

The account telemetry adapter is not the research execution transport. It may
use the official Codex app-server only when all of these hold:

- the executable version is in a reviewed compatibility allowlist;
- external-token mode is supported by that version;
- account identity matches the current credential;
- decoded responses satisfy the pinned local schema; and
- the bounded child process exits/cleans up.

Missing binary, account mismatch, version skew, protocol drift, timeout, or
malformed data returns a typed unavailable snapshot and leaves the last good
snapshot visible with its original `observed_at`. There is no fallback to a
paid API request and no model turn.

### LD 8 - Anthropic observation is passive by default

The Claude SDK driver's existing `RateLimitEvent` is no longer discarded. A
normal user-request stream may save its typed, credential-bound fields without
starting another request. Absence of an event means unknown, not unlimited.

Any Anthropic operation whose sole purpose is to obtain headers and which sends
even a minimal model request remains an explicit button action with cost copy.
It is not part of automatic preflight or page loading.

### LD 9 - Backend API split

The implementation exposes separate operations:

- credential inventory: local derived lifecycle state, no network;
- cached account observation: read-only, no network;
- account sync: explicit mutating/control-plane `POST`, bounded and
  single-flight.

Listing credentials must never silently refresh or contact a provider. The
frontend can request account sync after rendering the cached/local truth.

### LD 10 - UI integration sequence

OAuth lifecycle truth lands before the broader Settings navigation/warm-cache
slice. The provider row then renders lifecycle, last refresh result, quota/reset
and manual sync from this contract in one pass. It must not continue deriving
"configured", "usable", "entitled", and "quota available" from one green pill.

The Settings performance slice may cache these read models, but every
credential mutation, active switch, login/re-login, refresh, and account sync
must invalidate the exact affected cache key immediately.

## 4. Required RED contracts

At minimum, implementation begins with independent failing nodes for:

1. an expired ChatGPT token is not projected as available;
2. transient refresh failure differs from terminal re-login-required;
3. successful automatic refresh changes projected expiry without relying on
   stale DB metadata;
4. missing token on an OAuth row is `reauth_required`;
5. unreadable token store is `unverifiable`, not `reauth_required`;
6. two processes cannot refresh the same rotating token concurrently;
7. delete and refresh cannot resurrect a credential;
8. five exhausted-account rate-limit reads do not require a turn and preserve
   before/after token-usage summary in the controlled adapter fixture;
9. account mismatch rejects a snapshot;
10. malformed/unknown app-server protocol preserves the last good snapshot and
    reports unavailable;
11. no automatic ChatGPT sync occurs while Providers is hidden or inside the
    five-minute TTL;
12. manual sync bypasses TTL but observes its ten-second cooldown;
13. Claude `RateLimitEvent` persists a snapshot during a normal request;
14. no Claude event produces unknown and never starts a probe; and
15. every API response/log assertion proves secrets and raw account identifiers
    are absent.

## 5. Out of scope

- changing research/card execution to Codex app-server;
- model catalog additions, default-model changes, or SDK upgrades;
- Settings sticky navigation and general page caching implementation;
- Financial Datasets spend policy;
- Tranche B score retirement;
- billing prediction or scraping a private provider dashboard;
- claiming that a successful account sync proves a particular model is usable.

## 6. Review and implementation order

1. Independent review of this design and the 2026-08-08 experiment claims.
2. RED-first implementation plan with exact backend/frontend node ledgers.
3. Lifecycle authority + inter-process lock + telemetry.
4. ChatGPT cached account read/sync adapter.
5. Claude passive `RateLimitEvent` capture.
6. Provider-row UI integration.
7. Broader Settings sticky-navigation/warm-cache slice consumes the resulting
   API contract; it does not redesign auth truth.
