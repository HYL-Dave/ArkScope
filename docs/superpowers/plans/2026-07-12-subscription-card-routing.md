# Subscription Card Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Status: IMPLEMENTED FOR REVIEW, 2026-07-12.** Automated gates are green;
> the real ChatGPT/Claude subscription card + translation gate remains pending.

**Goal:** Make AI card generation and card translation consume the active selected provider credential, including ChatGPT and Claude subscription allowance, without silent billing fallback.

**Architecture:** Keep the existing API-key SDK paths byte-compatible. Add one focused subscription structured-output adapter: ChatGPT OAuth uses the already-proven Codex-backend Responses function-call shape; Claude OAuth uses Claude Agent SDK JSON-schema output with all tools disabled. Effective-model eligibility and task canaries derive from the same executable matrix, so the UI unlocks only after the runtime path exists.

**Tech Stack:** Python 3.10, OpenAI async Responses client with a sync worker-route facade, Claude Agent SDK 0.2.105, Pydantic, pytest, React/TypeScript derived Models UI.

## Global Constraints

- The selected provider's active credential is the transport and billing authority.
- Never fall back to another credential, provider, model, or API-key environment variable.
- API-key call shapes and existing effort fallback metadata remain unchanged.
- Subscription structured calls have no ArkScope tools, no research persistence, and no report persistence.
- Missing/expired tokens and provider/model failures return redacted, classified errors.
- `api_key_pool` remains fail-closed.

---

### Task 1: Subscription structured-output adapter

**Files:**
- Create: `src/auth_drivers/subscription_structured_output.py`
- Test: `tests/test_subscription_structured_output.py`

**Interfaces:**
- Produces: `run_subscription_structured_output(*, provider, auth_mode, credential_id, model, system, user, output_name, output_description, schema, effort="default", token_store=None, timeout_s=90.0) -> dict[str, Any]`.
- Produces: `await run_subscription_structured_output_async(...)` for task canaries; the sync facade is restricted to worker-thread card routes and never creates a nested provider executor.
- Produces: `SubscriptionStructuredOutputError(code: str, message: str)` with `code` equal to `reauth_required`, `provider_call_failed`, or `task_auth_mode_unsupported`.

- [x] **Step 1: Write OpenAI RED tests** proving a `chatgpt_oauth` token is refreshed and sent only to `https://chatgpt.com/backend-api/codex`, the request uses one flat function tool with `stream=True`/`store=False`, explicit effort is preserved, the function arguments are returned, and both stream and client close.
- [x] **Step 2: Run the OpenAI tests and verify RED** because the adapter module does not exist.
- [x] **Step 3: Implement the minimal OpenAI adapter** using the existing token store, `refresh_if_needed`, redaction helpers, and streaming function-call parser. Do not send `max_output_tokens` and do not construct a public API client.
- [x] **Step 4: Run the OpenAI tests and verify GREEN.**
- [x] **Step 5: Write Claude RED tests** proving the adapter passes `output_format={"type":"json_schema","schema":schema}`, `tools=[]`, `allowed_tools=[]`, `mcp_servers={}`, `setting_sources=[]`, `max_turns=2`, subscription-only environment variables, and returns `ResultMessage.structured_output` after closing the generator and deleting its temporary config directory. The SDK-internal `StructuredOutput` call consumes turn one; turn two is required for the terminal `ResultMessage`. This does not permit an ArkScope or external tool turn.
- [x] **Step 6: Run the Claude tests and verify RED** for the missing branch.
- [x] **Step 7: Implement the minimal Claude adapter** with a bounded async query executed from the synchronous card path. Reject missing structured output, tool use, SDK errors, and timeouts with redacted classified errors.
- [x] **Step 8: Add negative tests** for missing token, refresh reauthentication, malformed/no function call, provider failure redaction, unsupported provider/auth pairs, and no hidden API-key fallback.
- [x] **Step 9: Run `pytest -q tests/test_subscription_structured_output.py` and verify all tests pass.**

### Task 2: Card generation and translation dispatch

**Files:**
- Modify: `src/card_synthesis.py`
- Modify: `tests/test_card_synthesis.py`

**Interfaces:**
- Consumes: `run_subscription_structured_output(...)` from Task 1.
- Preserves: `_synthesize_openai`, `_translate_openai`, `_synthesize_anthropic`, and `_translate_anthropic` public test seams and return shapes.

- [x] **Step 1: Write RED tests** for all four OAuth paths: OpenAI synthesis/translation and Anthropic synthesis/translation dispatch to the subscription adapter when `resolve_live_auth()` reports `oauth_driver_unwired`.
- [x] **Step 2: Add strict regression tests** proving API-key/env paths still call `live_openai_client()` or `live_anthropic_client()` with the existing SDK request shape and never call the subscription adapter.
- [x] **Step 3: Run the focused tests and verify the OAuth cases fail for the current fail-closed direct clients.**
- [x] **Step 4: Implement conditional dispatch inside each provider `run_once`**. Pass the exact selected model, effort, prompt, schema, and output name to the adapter; keep Pydantic validation and translation cardinality checks at their existing boundaries.
- [x] **Step 5: Run `pytest -q tests/test_card_synthesis.py tests/test_subscription_structured_output.py` and verify GREEN.**

### Task 3: Eligibility and bounded task tests

**Files:**
- Modify: `src/model_effective.py`
- Modify: `src/model_task_canary.py`
- Modify: `tests/test_model_effective.py`
- Modify: `tests/test_model_task_test.py`

**Interfaces:**
- OAuth card canaries call the same Task-1 adapter directly from the sync route's short-lived `asyncio.run()` loop, with provider-level timeouts and a schema requiring one boolean `ok` field. A second executor is forbidden because it can outlive that loop in the sandbox/runtime worker shape.
- `task_capability_ok()` remains the model-capability authority; auth mode decides transport only.

- [x] **Step 1: Change matrix expectations to RED**: OpenAI `chatgpt_oauth` and Anthropic `claude_code_oauth` are executable for both card tasks; pool and cross-provider auth remain false.
- [x] **Step 2: Add canary RED tests** proving OAuth card tests issue exactly one structured subscription call, return `ok`, classify missing token as `reauth_required`, classify provider/model errors as `provider_call_failed`, and do not construct a research driver or write any store.
- [x] **Step 3: Run the matrix/canary tests and verify RED for the current auth-wide veto.**
- [x] **Step 4: Update `_task_auth_mode_ok()` and `_auth_veto()`** to allow only the provider-matching OAuth card paths.
- [x] **Step 5: Dispatch OAuth card canaries to the subscription adapter** while retaining the current bounded OAuth research path.
- [x] **Step 6: Run `pytest -q tests/test_model_effective.py tests/test_model_task_test.py` and verify GREEN.**

### Task 4: Integration verification and closeout

**Files:**
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: `docs/superpowers/plans/2026-07-12-subscription-card-routing.md`

- [x] **Step 1: Run focused backend tests:** `pytest -q tests/test_subscription_structured_output.py tests/test_card_synthesis.py tests/test_analysis_cards_api.py tests/test_model_effective.py tests/test_model_task_test.py tests/test_live_resolver.py`.
- [x] **Step 2: Run frontend Models tests and typecheck:** `npm --workspace apps/arkscope-web test -- --run ModelRoutingSection.test.ts modelRoutingUx.test.ts` and `npm --workspace apps/arkscope-web run typecheck`.
- [x] **Step 3: Run production build and no-PG smoke:** `npm --workspace apps/arkscope-web run build` and `python src/smoke/pg_unreachable_e2e.py`.
- [x] **Step 4: Run regression tests for OAuth lifecycle and both subscription drivers.**
- [ ] **Step 5: Live gate on the branch sidecar before merge:** stop the desktop/master sidecar, start this branch against the real profile DB, then generate one ChatGPT OAuth `gpt-5.4-mini` card and translate it; with Claude OAuth active, run one low-cost supported model card/translation. Confirm the task-test and real task both consume subscription allowance, no API key is touched, and an unsupported model fails without fallback. Merge only after this gate and review pass; restart the desktop app once after merge.
- [x] **Step 6: Mark this plan `IMPLEMENTED FOR REVIEW` and add a newest-first map entry with automated evidence.**
- [ ] **Step 7: After the live gate, mark `LIVE COMPLETE` and append the live evidence.**

### Execution ledger

- OpenAI adapter RED: module absent; GREEN: subscription backend/function-call/effort/close contract.
- Claude adapter RED: `_claude_query` seam absent; GREEN: locked Agent SDK `output_format` path, including async-host execution.
- Card dispatch RED: all four OAuth paths attempted the API-key client; GREEN: all four use the subscription adapter.
- Eligibility RED: OAuth cards returned `task_auth_mode_unsupported`; GREEN: provider-matching OAuth cards are executable and canary-tested.
- Review fix RED: an OAuth provider error containing `effort` was caught by the legacy API-key retry heuristic, causing all four card/translation paths to call the subscription backend again with `default`; GREEN: `SubscriptionStructuredOutputError` is never effort-retried, while the existing API-key fallback contract remains unchanged (four parametrized pins).
- Independent review round 1 caught four runtime-only gaps: Claude's SDK-internal `StructuredOutput` tool was rejected, `apiKeySource` was not verified, provider streams lacked a real deadline, and expired Claude tokens were not classified as reauthentication. RED/GREEN fixes now allow only the internal structured-output tool, require subscription auth evidence and clear inherited billing variables, use an async OpenAI client with SDK retries disabled, directly await the async canary adapter, and reject expired Claude credentials before SDK startup.
- Independent review round 2 caught two remaining timeout gaps: credential preflight was still synchronous, and Claude cleanup inherited only the expired provider deadline. RED/GREEN fixes place keyring/refresh work in a deadline-bounded preflight worker that never owns an LLM client, and reserve 11 seconds for the pinned SDK's documented graceful-exit/SIGTERM/SIGKILL teardown. Round 3 re-review: GREEN, no blocking findings.
- First live gate exposed two independent failures. ChatGPT returned the same HTTP 401 invalidated-token response through both the pre-existing AI Research driver and the new card adapter, proving credential invalidation rather than a card-routing regression; runtime HTTP 401 is now classified narrowly as `reauth_required`, while 404/model and other provider failures remain generic. Claude Sonnet 5 returned `Reached maximum number of turns (1)`; a no-code live probe with the identical locked options and `max_turns=2` returned the requested structured result. RED/GREEN pins now preserve the two-turn internal structured-output exchange with all external tools still disabled.
- The repaired tiny Claude task tests passed, but the first real MU card used the saved `max` effort and hit the adapter's 90s default twice while the web client was already budgeted for 240s. RED/GREEN follow-up gives full subscription synthesis and translation a 210s provider deadline and both UI calls a 300s deadline; bounded 45s task tests remain unchanged. Cleanup inspection also found exited Claude children waiting to be reaped. Raising the outer close budget from 11s to 20s was necessary but a live canary proved it insufficient: the SDK convenience generator still left its direct child defunct after successful close, and one immediate `WNOHANG` check ran just before child exit. The adapter now retains its explicitly constructed subprocess transport, records that transport's exact child PID, runs normal SDK close, then polls `waitpid(pid, WNOHANG)` on the same event loop for up to five seconds (already-reaped children are a no-op). Unit coverage pins exact-PID ownership and the exit-after-close race; post-restart live acceptance requires no new zombie after a canary.
- One test-only `asyncio.to_thread()` experiment hung after the worker returned; faulthandler showed the short-lived loop blocked in `select()`. The final canary directly awaits the bounded async adapter in the sync route's single `asyncio.run()` loop; no second provider executor exists.
- Automated evidence: focused backend 132 passed; subscription-driver adjacency 166 passed; frontend 30 files/284 tests; TypeScript typecheck and production build passed; no-PG smoke 24/24 with `pg_attempts: []`.
- Full-suite limitation is recorded rather than overstated: the warmed branch run reached the repository's known long-hang family. Its first two data-dependent failures (`test_execute_get_ticker_news` and `test_execute_get_price_change`) were then run against a detached `c7256c8` base worktree with an empty `data/` directory and failed identically, proving those two failures predate this slice. A canonical full A/B remains a review gate.

## Stop Conditions

- If the ChatGPT backend rejects the proven flat function-tool shape for card payloads, stop and report the wire response; do not route to `api.openai.com`.
- If Claude Agent SDK ignores `output_format` or enables tools despite the locked options, keep Claude OAuth card tasks disabled and split a provider-specific follow-up.
- If supporting OAuth requires changing API-key request shape, stop and separate the refactor.
- If a model is listed but execution fails, preserve the model-specific failure; do not add automatic model fallback.
