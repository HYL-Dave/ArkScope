# Four-Task Route Authority Repair

**Goal:** Every supported selectable task route must execute the selected provider, model, effort and authentication channel, and show the source of the actual execution instead of the current Settings value.

**Architecture:** Keep the existing four task IDs, capability admission and API/OAuth adapters. Resolve a route and its authentication once at the request boundary; carry that selection through gathering, scheduling and dispatch. Preserve old results and add closed, non-secret execution receipts for new results. Use the existing SQLite store lifecycle for additive metadata storage, tested only in temporary databases in this branch.

**Tech Stack:** Python/FastAPI/SQLite, native OpenAI/Anthropic SDK and existing subscription adapters, React/TypeScript/Vitest.

**Spec (approved in conversation):** New tasks default to Settings; an explicit choice for the current Research operation may override it. A running task does not change model, effort or credential when Settings changes. Old cards and translations keep their historical source, with missing metadata explicitly unknown. Cached translation reads never cause new model calls; a separate retranslation command starts a new execution. The user authorized implementation after the four-route audit and requires separate merge approval.

## Global Constraints

- Work only in `/tmp/arkscope-task-route-authority`, branch `codex/task-route-authority`, based on `fb12f27e`. Do not merge, push, restart the App, contact providers, or read/write production stores or credentials.
- Preserve all four task IDs and existing model/auth/entitlement admission: Spark is translation-only with exact entitlement; retired models stay retired; no new Fable OAuth admission.
- No model, effort, credential, authentication-channel or billing-source fallback after a selected execution fails. A genuinely absent saved route may still use documented defaults; a route-store read failure may not.
- Capture a route/auth selection once. Secrets may exist only in the required in-memory client binding; never in logs, repr, errors, SQLite execution metadata, frontend payloads or evidence. Preserve intentional no-active-credential env behavior, but do not silently use env credentials after a selected credential fails.
- Historical missing metadata remains unknown. Do not infer it from current Settings. Retain old translations on refresh failure and preserve successful earlier versions.
- Use RED-first behavioral tests with literal expectations and positive controls, then focused verification and review. Run backend tests only through this worktree's offline wrapper. No raw pytest.
- Offline backend command: `env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/<files>`.
- Offline frontend command, from `apps/arkscope-web`: `env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only <test files>`.
- Only use `apply_patch` for manual edits. Scope commits to owned changes. Do not update sealed historical evidence or remove user files. No worker subagents; the controller assigns independent review.

## Task 1: Bind Runtime Selection and Reject Silent Substitution

**Files:** `src/agents/config.py`, `src/auth_drivers/live_resolver.py` (and one focused binding module if needed), `src/api/routes/research.py`, `src/api/routes/query.py`, `src/research_run_manager.py`, `src/agents/openai_agent/agent.py`, `src/agents/anthropic_agent/agent.py`, the directly affected existing `src/agents/shared/subagent.py` client consumer, `src/model_credentials.py`, applicable model-test route/error helpers, and focused tests.

**Interfaces:** Expose a small reusable immutable auth capture/activation interface for Task 2. It must bind the selected provider/source/credential, prevent active-credential re-resolution from changing it, and supply safe `auth_mode`/source metadata. Snapshot the selected credential for the duration of execution or reject its mutation before dispatch; never use the replacement credential. Bind OpenAI Agents SDK models to per-run clients instead of the process-global client. Keep binding objects out of persisted Research records and normal repr/logging. Report exact helper names and lifecycle to the controller for Task 2.

**RED:** Add named behavioral cases for four-task route-read failure, absent-route default positive controls, active credential switches between Research create/schedule/dispatch, two concurrent OpenAI clients not exchanging keys, and custom Anthropic effort reaching the real messages boundary. Add an Anthropic model-test effort rejection case proving one request, no default-effort retry and no success receipt for a substituted effort. Keep API-key and both OAuth choices covered with synthetic credentials.

**Implementation:** Make `_db_route` read failures typed for all tasks. Capture Research auth before persistence/scheduling and carry it into actual streaming. Failed queued handoff or missing binding must not recapture a different credential. Cover the legacy stream entry as appropriate because it shares dispatch. Keep model admission ahead of the call. Forward admitted custom Anthropic effort, or clearly reject unsupported combinations before claiming execution. Remove Anthropic probe effort fallback and implicit SDK retry; invalid explicit effort must not be normalized into a different one at a test endpoint. Preserve tiny access-probe vs completed-generation semantics.

**Existing child-execution compatibility:** Removing the main OpenAI global client must not strand `_run_openai_subagent`, which currently relies on that global, or make a parent's single-provider auth context reject intentional cross-provider delegation. Give existing child dispatch an explicit auth boundary and per-agent OpenAI client. Keep its configured model and parent binding unchanged, preserve selected-OAuth rejection where a child direct-SDK path is unsupported, and test same-provider plus deliberate cross-provider delegation. This repairs consumers of the changed binding, not new subagent functionality.

**GREEN / Controls:** Run the relevant route, Research, native agent/replay, live resolver, credential/model-test and subscription tests through the wrapper. Show a known admitted supported model still succeeds, genuine absent route defaults still work, OAuth failure never invokes an API client, and identical requested/stored/wire tuples under Settings switches. Record RED/GREEN and representative mutation owners, without provider calls.

**Commit:** `fix(routing): bind task execution and reject silent substitution` (split coherent commits if necessary). Do not edit Task 2 or frontend files.

## Task 2: Card Execution Receipts and Explicit Retranslation

**Files:** `src/card_synthesis.py`, `src/api/routes/analysis_cards.py`, `src/card_runs.py`, directly affected evidence-translation caller only if needed, relevant backend tests. Shared Task 1 helper changes require coordination.

**Interfaces:** Add a closed public execution receipt containing `provider`, `model`, `effort`, `auth_mode` (nullable only for legacy metadata). No credential ID, key, token, hash or internal binding objects in this DTO. Generation, saved-card reads/listing, cached translations and new translations return their own receipt. Keep existing `provider`/`model` compatibility fields where consumers need them. Report the final API types to Task 3.

**Task 1 integration:** `src.auth_drivers.runtime_binding.capture_runtime_auth(provider, *, store=None, token_store=None)` returns an immutable `RuntimeAuthBinding`. Use `activate_runtime_auth(binding)` around the full fixed-task dispatch. Existing sync live clients and `resolve_live_auth` honor that context. Pass the binding's exact `credential_id` and controlled `token_store` to subscription structured output; do not serialize the binding or its private key. Its public `provider`/`auth_mode` plus the captured route's `model`/`effort` supply receipt metadata. A focused `src/card_execution.py` helper is permitted if needed to keep one immutable fixed-task selection and its closed receipt; do not create another transport framework. The receipt describes ArkScope's sent selection, not a new claim that every provider independently returns a verified model ID.

**Failure boundary:** `sanitize_runtime_error(exc, binding=captured_binding)` provides bounded selected-key redaction even after activation exits. Only the sanitized detail may reach logs or HTTP responses; do not append the raw exception or traceback afterward. Model/auth admission errors retain their existing typed meaning. Binding clients already pin the selected API-key header and standard provider destination; do not build a second client from ambient environment values.

**RED:** Exercise the actual API-to-fixed-task path using SDK-boundary fakes, both providers and OAuth/API modes. An OpenAI configured route must remain OpenAI even if Settings changes during gathering. Translation must use the once-captured model AND effort, not a second route read. Show cache hits do not dispatch, explicit refresh dispatches once, refresh failures leave prior cached results intact, and old rows without receipts read as unknown without consulting Settings. Test real SQLite reopen for metadata and earlier translation preservation.

**Implementation:** Remove internal route re-reads after a captured selection; pass the route as a complete tuple and use Task 1 auth binding throughout. Preserve deliberate explicit API provider overrides. Add narrowly scoped additive SQLite metadata/translation-version tables (no destructive migration and no modification of old result payloads). Record new execution receipts transactionally with successful outputs. Retain legacy translation JSON compatibility and earlier versions. Add optional explicit `refresh` to translation requests; normal language switching returns existing cache. Never silently overwrite history with current configuration. Fix route-error HTTP mapping without leaking exceptions.

**GREEN / Controls:** Card-run store/API/fixed-output/translation/subscription regressions all pass, including positive cached and legacy controls. Confirm no retry/fallback, no new provider access and no production database access. Provide synthetic new-schema/legacy-schema migration evidence and exact request/response examples for Task 3.

**Commit:** `fix(cards): preserve route receipts and explicit translation refresh`.

## Task 3: Four-Task Selection and Provenance UI

**Files:** `apps/arkscope-web/src/AICard.tsx`, `api.ts` and card types, `researchSelection.ts`, Research selection UI, `lifecycle/InvestigationView.tsx`, relevant locale modules and tests. Keep Settings route persistence mechanics intact.

**Interfaces:** Consume Task 2's closed execution DTO. Never substitute current Settings for a historical receipt. New Research operations, including the next turn of an existing thread, use `catalog.routes.ai_research`; explicit choices made in the currently open Research conversation still override. Reset that transient override when opening another/new conversation. Existing thread tuples remain historical and must not implicitly override Settings for a later execution.

**RED:** Replace the tests pinning the card UI's Anthropic constant with requests that omit unsolicited provider overrides. New Research selections must follow both OpenAI and Anthropic Settings routes rather than hardcoded Luna, a historical thread tuple or stale global localStorage preferences; current user override and unchanged existing message provenance have positive controls. Cards and cached translations show the correct distinct source receipts. Retranslation is an explicit command; changing language never sends refresh. Lifecycle confirmation must show current preflight provider/model/effort/auth even when the displayed previous run used different values.

**Implementation:** Remove the card provider constant. Display compact source metadata for original cards and translations, label unknown legacy metadata honestly, and provide a clear retranslation action with pending/error/retry states that retain the old translation. Use existing icons/tooltips/i18n. Separate lifecycle previous-run source from next-run confirmation. Keep text/domain-focused and avoid explanatory clutter. Retain deliberate custom model support and all existing eligibility reasons. Do not rework unrelated Settings layout.

**GREEN / Controls:** Run targeted tests, frontend typecheck/build, then full frontend suite. Verify desktop/mobile mocked-runtime screens and interactions using browser tooling without starting the production backend. Keep existing cards/history/use-saved-result workflows working; no automatic provider execution from UI mount or language toggle.

**Commit:** `fix(ui): honor task routes and show execution provenance`.

## Task 4: Integrated Verification and Handoff

**Files:** New bounded evidence/handoff document and Priority Map entry; fix only concrete integration failures via a reviewed worker.

Run the full backend suite with explicit `pytest -q tests` through the offline wrapper, the full frontend suite and build/typecheck. Verify named mutations for route read fail-open, second route read, credential switching, card provider constant, Research hardcoded default and cached-translation provenance. Review the whole branch independently. Update the operating map and provide a concise four-task hand-test guide with old cache vs new execution and supported auth combinations. Mark live testing, App restart and merge as pending. Do not claim that offline tests certify every provider/model live combination.

**Commit:** `docs: record four-task route repair verification`.
