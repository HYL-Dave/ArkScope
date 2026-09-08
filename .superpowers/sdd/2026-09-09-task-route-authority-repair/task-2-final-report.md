# Task 2 Final Report

Status: DONE_WITH_CONCERNS (test-order concern below; all 720 final relevant tests pass).

Worktree: `/tmp/arkscope-task-route-authority`.
Branch: `codex/task-route-authority`.
BASE: `1284c28e0d80a26279913fd2e503005e5582d5e2`.
Scoped commit subject: `fix(cards): preserve route receipts and explicit translation refresh`.

Read authority: `task-2-final-brief.md`, the controller's two clarifications, and directly relevant source/tests. No whole plan or prior-session history was read. No subagents, helpers, or reviewers were dispatched. Controller review remains pending.

## Implementation

- Added the small `src/card_execution.py` helper. `CardExecution` copies task/provider/model/effort into immutable fields and holds the reviewed `RuntimeAuthBinding` only in memory, excluded from its repr. `ExecutionReceipt` is frozen, rejects extra fields, and contains only provider/model/effort/auth_mode.
- Card generation captures route and auth before gathering. The fixed synthesis function accepts that selection and never re-reads Settings. Deliberate explicit provider overrides retain the existing advanced-model/high-effort defaults for the overridden provider. An omitted provider on direct synthesis now follows the configured route.
- Card translation captures once before runtime resolution/dispatch. The captured model AND effort reach the SDK. The API-key clients are the reviewed binding-aware live clients, with zero retries and pinned key/header/standard host; no second ambient client is created.
- OAuth uses the original credential ID from the reviewed binding-aware live resolver and forwards the captured token store explicitly. Normal refresh remains on that original ID. Missing/revoked tokens or failed refresh never select the replacement active credential or an environment API key.
- Fixed functions activate the binding across the actual provider dispatch. Generation errors use `sanitize_runtime_error(exc, binding=execution.auth)` after activation exits. No raw exception or traceback is appended to logs or HTTP errors. Translation keeps its existing closed failure classifier; it does not emit raw provider details. Typed model/auth admission details remain typed HTTP 400 responses. Route-read failure maps to HTTP 503 instead of an unhandled 500/default route.
- Added two tables only: `ai_card_execution_receipts` and `ai_card_translation_versions`, plus a version index. No new columns or destructive migrations were added to the existing run table. Existing historical migrations remain unchanged.
- New generation output and receipt commit together. Translation append-version/output/receipt/cache update commit together. SQLite read transactions keep compatible output and side-table metadata in one snapshot. `BEGIN IMMEDIATE` serializes translation read/merge/write across store instances.
- Existing `result_card_json` is not rewritten. Existing `translations_json` remains the current compatible per-language cache. Earlier successful translations remain in the version table. A legacy cached translation is retained with unknown metadata before its first successful replacement; failed refresh does not write anything.
- Historical run provider/model values remain known facts. Missing effort/auth are null, never filled from Settings. Legacy translations with no source metadata have all four receipt fields null. No history read selects a route or credential.
- `refresh` is optional and defaults to false. Cache hits do not read route/auth, dispatch, or write. Explicit refresh executes exactly once. Empty-prose translation is explicitly `no_op: true`, returns a null receipt, and does not select, dispatch, or create a cache/version.
- The only other caller changed is `_translate_evidence_text` in `src/api/routes/security_lifecycle.py`: six added lines and one replaced line pass the already captured selection into `translate_text`. Its existing API/result DTO is unchanged. A RED SDK-boundary test showed its old model-plus-new-effort mismatch.

## Files

- `src/card_execution.py`: immutable selection and closed receipt.
- `src/card_synthesis.py`: complete selection handoff, binding activation, OAuth token-store forwarding, typed admission, no-op predicate.
- `src/api/routes/analysis_cards.py`: capture before work, safe errors, receipts in generation/detail/list/cache/new translation, explicit refresh/no-op.
- `src/card_runs.py`: additive receipt/version tables and transactional persistence/read snapshots.
- `src/api/routes/security_lifecycle.py`: directly affected text-translation caller only.
- `tests/test_card_execution_authority.py`: 42 new tests/parameterized controls using real routes, fixed functions, SDK boundaries, in-memory synthetic tokens, and temporary SQLite.
- `tests/test_analysis_cards_api.py`: explicit synthetic environment credentials for existing synthesis fakes; additive `execution` keyword accepted and asserted by the translation fake.
- This requested report. No frontend, controller plan/brief, sealed evidence, common auth-binding implementation, or unrelated limit changes.

## RED / GREEN Evidence

Every backend test command used the required wrapper below. Every invocation reported loopback-only interfaces, `external_probe: ENETUNREACH`, and `inherited_credentials: false`. Test stores were temporary, under the existing conftest isolation. No live provider request, production-store operation, credential retrieval, .env read/copy by the agent, application restart, merge, or push was performed.

### Baseline

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_card_runs.py tests/test_analysis_cards_api.py
```

Result: **34 passed in 3.72s**.

### Initial RED And Iteration

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_card_execution_authority.py
```

Initial result: **17 failed in 3.86s**. Behavioral failures covered provider/model/effort/auth drift, changed destination, selected-key leakage, absent receipts/refresh/version tables, and route-read HTTP mapping. Four OAuth cases initially failed in fixture setup because `CredentialStore.add` intentionally rejects OAuth. Those four were not treated as valid behavioral RED evidence; the fixture was corrected to `add_oauth_credential` and its sensitivity was checked separately below.

The same command after initial implementation: **4 failed, 14 passed in 4.01s**, only the OAuth fixture errors. After correcting them: **18 passed in 3.63s**.

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_card_execution_authority.py -k empty_prose
```

No-op RED: **1 failed, 17 deselected, 1 error in 2.06s**. The old API attempted route selection and returned 500 instead of the required no-op. The teardown error came from `pytest.fail` crossing TestClient's worker boundary; that test guard was changed to an ordinary exception. The no-op implementation then passed in all later focused and broad runs.

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_analysis_cards_api.py tests/test_card_runs.py tests/test_card_synthesis.py
```

Intermediate result: **1 failed, 98 passed in 4.59s**. Existing strict translation fake did not accept the additive `execution` keyword. Its call count, timeout, and positive cache assertions were preserved when updating its signature.

### Corrected OAuth Sensitivity

Temporarily changed only subscription forwarding from the captured token store to `None`, using apply_patch. The fixture changes Settings and the default token store after capture. With that deliberate regression:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_card_execution_authority.py -k oauth
```

Result: **4 failed, 14 deselected in 2.61s**. Both providers and both fixed tasks failed at the original selection contract. Captured-token-store forwarding was restored with apply_patch. The later expanded matrix checks both same-provider model/effort changes and cross-provider changes.

### Directly Affected Caller RED

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_card_execution_authority.py -k direct_evidence
```

Result: **1 failed, 18 deselected in 3.18s**. The actual text-translation caller sent `gpt-5.6-luna` with new effort `low` rather than captured effort `xhigh`, after runtime-resolution-time Settings mutation. The expanded full authority file still showed **1 failed, 39 passed in 5.39s** before fixing that caller.

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_card_execution_authority.py tests/test_analysis_cards_api.py tests/test_card_runs.py tests/test_card_synthesis.py
```

Result after the caller fix: **139 passed in 7.01s**.

### Additional Focused Checks

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_subscription_structured_output.py tests/test_openai_fixed_output_compatibility.py tests/test_security_lifecycle_routes.py tests/test_security_lifecycle_translation.py tests/test_personalization_prompt.py
```

Result: **2 failed, 188 passed in 11.49s**. Both failures are the route-enumeration/eventkit import-order concern below, not provider/translation assertions.

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_card_execution_authority.py tests/test_security_lifecycle_routes.py
```

Result while adding normal-refresh controls: **2 failed, 81 passed in 13.26s**. The synthetic expiry used a `Z` suffix, which the existing Python 3.10 `datetime.fromisoformat` path does not parse. Changed the fixture to the runtime's normal `+00:00` representation; no shared OAuth/parser code was changed. The lifecycle route checks passed in this order.

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_card_execution_authority.py tests/test_analysis_cards_api.py
```

Result: **64 passed in 6.18s**. Includes original-ID normal refresh, grant failure with zero dispatch, raw legacy-cache failure preservation, explicit provider override, genuine no-active environment behavior, broken-selected-credential rejection, closed DTO rejection, and typed retirement/Fable/Spark admission.

### Final Broad Relevant Set

Run once after focused iteration, with the loop-sensitive lifecycle enumeration checks first. No skips or deselection:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_security_lifecycle_routes.py tests/test_card_execution_authority.py tests/test_card_runs.py tests/test_analysis_cards_api.py tests/test_card_synthesis.py tests/test_openai_fixed_output_compatibility.py tests/test_fixed_task_runtime_config.py tests/test_security_lifecycle_translation.py tests/test_content_translation_failures.py tests/test_subscription_structured_output.py tests/test_codex_translation_adapter.py tests/test_task_runtime_binding.py tests/test_model_routing.py tests/test_model_capabilities.py tests/test_model_route_store.py tests/test_auth_drivers.py tests/test_auth_factory.py tests/test_personalization_prompt.py
```

Result: **720 passed in 30.35s**, exit 0. This includes the existing exact Spark entitlement/translation adapter controls, subscription regressions, retirement and Fable admission controls, and reviewed common auth-binding tests. Full repository suite and UI verification are deliberately left to controller Task 4.

`git diff --check` also passed with no output.

## Synthetic SQLite Evidence

- New-schema generation: API output and receipt survive constructing a new `CardRunStore` against the same temporary database; detail and listing return the same receipt after Settings changes.
- Legacy schema: create an actual historical `ai_card_runs` table, insert an old card and translation, reopen through the new store, and verify the original `result_card_json` text is byte-for-byte unchanged. Receipt fields remain unknown where not stored. After successful replacement, reopen again and read both old and new translation versions in order.
- New-schema refresh: first success, zero-dispatch cache hit, explicit second success using a changed model/effort, then failed refresh. Reopen and verify the second result remains current and both successful versions/receipts remain available.
- Raw legacy refresh failure: seed `translations_json` directly without receipt/version rows, remove the originally captured OAuth token, then request refresh. The legacy cache survives and no version is invented.
- Atomicity: SQLite abort triggers reject generation receipt insertion or translation version insertion. The corresponding new output is rolled back; the prior translation and version count remain intact after reopen.
- Public API and card-database dumps are checked against synthetic auth sentinels and forbidden credential fields. No credential identifiers, keys, tokens, hashes, or binding objects enter a receipt.

## Task 3 Interface

The new public property is **`execution_receipt`**, outside the existing `card` payload. It describes **ArkScope's sent selection**, not blanket provider-attested identity. Do not derive historical labels from current Settings or copy the generation receipt onto translations.

```typescript
type ExecutionReceipt = Readonly<{
  provider: string | null;
  model: string | null;
  effort: string | null;
  auth_mode: "api_key" | "chatgpt_oauth" | "claude_code_oauth" | null;
}>;

type TranslateBody = {
  lang?: "zh-Hant" | "zh-Hans"; // default: "zh-Hant"
  refresh?: boolean;            // default: false
};

type TranslationResponse = {
  run_id: number;
  lang: string;
  card: ResultCard;
  cached: boolean;
  execution_receipt: ExecutionReceipt | null; // null only for explicit no-op
  no_op?: true;
};
```

- `POST /analysis/card/{ticker}`: existing response plus `execution_receipt`. Existing top-level `provider`, `model`, `effort`, `fallback_effort`, and `warning` remain. Ordinary new receipts have all four non-null fields; compatibility fallback/warning fields remain null on ordinary success and do not imply a fallback was performed.
- `GET /analysis/cards/{run_id}`: existing full run plus its generation `execution_receipt`.
- `GET /analysis/cards`: each existing list row plus its generation `execution_receipt`.
- `POST /analysis/cards/{run_id}/translate`: same receipt-bearing shape for new execution and cache hit, with each translation's own receipt. Normal language switching uses omitted/false refresh. A separate explicit retranslation action sends `refresh: true`.
- Historical generation can be `{provider: "openai", model: "gpt-5.4-mini", effort: null, auth_mode: null}`. A historical translation with no metadata has all four fields null. Preserve known values and render the missing ones as unknown.
- Empty-prose no-op returns `execution_receipt: null` and `no_op: true`, not an all-null legacy receipt. It stores no result/version. The `ResultCard` type above is the ordinary valid-card case; the no-op control can also return an unchanged legacy partial card.
- No new translation-history HTTP endpoint is added. Backend `translation_versions(run_id, lang)` exposes oldest-first stored versions for audit/testing, each with `version_id`, `card`, `created_at`, and `execution_receipt`; legacy archived version time is null.
- Python compatibility: `synthesize_card` still returns `(ResultCard, meta)`; `translate_card` still returns the full card dict; `translate_text` still returns `{translated_text, provider, model, harness}`. Each accepts additive optional `execution: CardExecution`. Once supplied, no route is re-read. Stores accept additive `execution_receipt: ExecutionReceipt | None` and never accept the binding as metadata.

### Request / Response Examples

These are synthetic values, not live provider evidence. Paths are the backend paths as registered, with no additional `/api` prefix in this router. First configure the relevant task route; requests do not accept arbitrary receipt/auth objects.

Generate with the configured OpenAI synthesis route:

```http
POST /analysis/card/AAPL
Content-Type: application/json

{"include_sa": false}
```

Receipt-bearing response fields (the existing card/evidence/personalization payloads are unchanged and omitted in this projection):

```json
{"run_id":1,"status":"generated","provider":"openai","model":"gpt-5.6-luna","effort":"xhigh","execution_receipt":{"provider":"openai","model":"gpt-5.6-luna","effort":"xhigh","auth_mode":"api_key"},"fallback_effort":null,"warning":null,"generated_at":"2026-09-09T00:00:00+00:00"}
```

Explicitly translate/refresh using the configured translation route:

```http
POST /analysis/cards/1/translate
Content-Type: application/json

{"lang":"zh-Hant","refresh":true}
```

Complete synthetic response for the minimal card used in the tests:

```json
{
  "run_id": 1,
  "lang": "zh-Hant",
  "card": {
    "ticker": "AAPL", "question": null, "horizon": null,
    "card_type": "analysis", "analysis_time": "2026-09-09T00:00:00Z",
    "conclusion": "second", "primary_reasons": [], "counter_thesis": ["risk"],
    "key_assumptions": [], "trigger_conditions": [], "invalidation_conditions": [],
    "risks": [], "watch_list": [], "market_narrative": null, "divergence": null,
    "changes_vs_last": null, "confidence_level": "low", "confidence_rationale": null,
    "traceability": {
      "data_sources": [], "is_single_model_inference": true,
      "completeness": {"news": false, "fundamentals": false, "technicals": false, "note": null},
      "claims": []
    },
    "core_observation": null, "action_suggestion": null, "trend_outlook": null, "key_levels": null
  },
  "cached": false,
  "execution_receipt": {"provider":"openai","model":"gpt-5.6-sol","effort":"low","auth_mode":"api_key"}
}
```

Subsequent `POST /analysis/cards/1/translate` with `{"lang":"zh-Hant"}` returns exactly that stored `card` and `execution_receipt`, with `cached: true`, even if Settings now select another model/provider/auth mode. It dispatches zero times. OAuth receipt variants use `auth_mode: "chatgpt_oauth"` or `"claude_code_oauth"`; there is no credential identifier in the DTO.

Exact empty-prose control response for a legacy source card `{"ticker":"AAPL"}`:

```json
{"run_id":1,"lang":"zh-Hant","card":{"ticker":"AAPL"},"cached":false,"no_op":true,"execution_receipt":null}
```

Route-read failure is HTTP 503:

```json
{"detail":{"code":"model_route_unavailable"}}
```

Selected malformed/unavailable auth at capture is HTTP 503:

```json
{"detail":{"code":"runtime_auth_unavailable"}}
```

Examples of preserved typed admission HTTP 400 responses:

```json
{"detail":{"code":"model_retired","field":"model"}}
```

```json
{"detail":{"code":"model_auth_unverified","field":"model"}}
```

Selected OAuth token missing during explicit refresh is HTTP 502, without deleting the prior translation:

```json
{"detail":{"code":"translation_auth_rejected","retryable":false,"provider":"openai","model":"gpt-5.6-luna","harness":"chatgpt_subscription_structured_output"}}
```

## Self-Review And Remaining Concerns

- Reviewed every changed production path and the diff against BASE. The four task IDs and model registry/admission rules are unchanged. Spark remains translation-only with exact entitlement delegated to the unchanged adapter; retired models remain retired; Fable OAuth remains rejected.
- Reviewed once-capture behavior, explicit provider override behavior, selected auth failure vs genuine missing-active environment behavior, absence of retry/fallback, context restoration, and post-activation sanitization. SDK-boundary tests exercise both providers in API-key/OAuth modes with Settings changes during gathering and translation.
- Reviewed public/durable receipt field closure, no binding serialization, no receipt inside old card payloads, legacy known/unknown handling, no-op distinction, and transactional output/receipt/version behavior. Temporary DB reopening and rollback tests pass.
- No shared Task 1 helper changes were necessary. No frontend, application restart, provider/production-store/credential access, production migration, limit change, merge, or push was performed. Existing card evidence payload structure and text/character/token limits are unchanged.
- **Concern for controller Task 4:** the focused command that ran subscription tests before lifecycle route enumeration produced two failures in unmodified `eventkit.util` while importing `ib_insync`: no current asyncio event loop in the main thread. The failures are `test_app_mounts_the_exact_lifecycle_route_surface_and_retires_old_review_routes` and `test_old_integer_event_and_relationship_routes_are_absent`. Both pass when lifecycle enumeration runs before tests that close the default loop. The final 720-test command uses that order with no skips. This report does not claim arbitrary-order or full-suite success; no unrelated loop/import behavior was changed.
- Full repository suite, UI verification, controller review, and any production rollout/migration are intentionally not performed here and remain controller-managed Tasks 3/4. No unresolved Task 2 requirement ambiguity or implementation blocker remains.
