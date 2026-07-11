# Models Routing UX — Implementation Plan (focused P2.8 slice)

> **Status: IMPLEMENTED FOR REVIEW 2026-07-11. NOT MERGED; §6 live gate pending.**
> Roles: Claude authored the plan; **Codex implemented on `codex/models-ux`,
> user/Claude reviews**. Implements the APPROVED spec
> `docs/superpowers/specs/2026-07-11-model-routing-settings-ux-design.md`
> (round 2 absorbed). Authority on any conflict: the spec. Sequence per spec
> §11: S3 lifecycle hotfix SHIPPED 2026-07-11 (`e7e144b`) — this slice is next.
>
> **Live evidence already in hand (S3 §7 gate)**: the ChatGPT backend LISTS
> `gpt-5.6-luna` but execution rejects it ("Model not found") while
> `gpt-5.4-mini` executes — the exact 「此登入可見 ≠ 實際呼叫通過」 divergence
> §3.4 splits. That pair is pinned below as the first §4.4 live acceptance
> case.
>
> **Implementation verification ledger (`9f5b664` → `6a8568b`):** focused
> backend `126 passed`; frontend `30 files / 281 tests`; typecheck and
> production build pass; no-PG smoke `24/24`, `pg_attempts: []`; Playwright
> desktop/mobile inspection found no horizontal overflow and confirmed the
> four model groups plus removal of the old checkbox/duplicate override.
> Full collect is `4059 → 4106`, exactly `+47 / -0` nodes. A review-time
> collect gate found that production file `src/model_task_test.py` matched
> pytest's `*_test.py` pattern and accidentally collected its imported
> `test_model`; RED pin + rename to `src/model_task_canary.py` removed that
> phantom node without adding a test (`6a8568b`).
>
> **A/B environment limitation:** the required virgin single-process base
> suite did not finish in this Codex environment because existing
> TestClient/event-loop state hangs in unrelated base tests. It is therefore
> NOT claimed as a full-protocol PASS. The broad symmetric fallback ran every
> test file in its own virgin pytest process with a 60-second file timeout:
> failure/error nodes `27 = 27`, timeout files `4 = 4` (both directional
> diffs empty), non-timeout passed `3768 → 3815 = +47`, skipped `73 = 73`,
> warnings `20 = 20`, errors `1 = 1`. Reviewer still owns the canonical
> single-process full A/B before merge.

## 0. Grounding corrections to the spec (verified against code 2026-07-11; round-2 re-verified)

1. **§4.4 Claude OAuth canary — RULING (round-2 MF1): `task_test_unsupported`
   in this slice.** The Claude research path is the Agent SDK driver; my
   round-1 claim that `registry=None` yields an empty allowlist was WRONG —
   `build_ark_mcp_server` (claude_code_sdk_driver.py:354) fail-fasts with a
   RuntimeError when the 13 allow-listed tools are missing, before any model
   call. The spec's own fallback applies verbatim: "If an auth driver cannot
   enforce these bounds, that path reports `task_test_unsupported` and does
   not run a normal research session." So: `ai_research × claude_code_oauth`
   task-test = ZERO-CALL `task_test_unsupported` with copy pointing at the
   probe (P3) as that channel's health check. A driver `tools_disabled` mode
   (explicit `tools=[]`/`allowed_tools=[]`/`mcp_servers={}` build path, proven
   by REAL option-building tests, not fake factory kwargs) is filed as a
   follow-up in §5 — not built here.
2. **The ChatGPT driver** accepts `max_turns` + `timeout_s` + `registry=None`
   through `build_driver(...)` (factory.py:88) and its `_build_tools` returns
   `[]` with no registry — the openai canary bounds need no driver changes.
   Its missing-token/refresh failures are CLASSIFIED events (S3), but the
   endpoint still defends against ANY driver raising (round-2 MF4, D4).
3. `EffectiveModelPicker` (Settings.tsx:2029) and the manual-override
   `<details>` (:2168) are the two structures §4.1/§10 remove; both live
   inside `ModelRoutingSection` (:2096, exported + tested). The global 儲存
   button + `save()` live OUTSIDE it (Settings.tsx:252) — save gating needs
   page-level wiring, not just component tests (round-2 MF5, D5).
4. `ActiveCredential` (model_effective.py:31) has NO label field — the v2
   `providers` block sources `label` from the credentials inventory at the
   catalog-route join (round-2 SF2).
5. Frontend `DEFAULT_TIMEOUT_MS = 15_000` (api.ts) is BELOW the backend
   canary bound — the new test helper must use its own higher timeout
   (round-2 MF5, D4/D5).

## 1. Scope

Backend: provider-indexed effective view v2 (single computation source; the
P2.7 task-level `verified`/`advanced` becomes a derived ALIAS), task-scoped
test endpoint with the §4.4 dispatch matrix. Frontend: task cards rebuilt to
the §4 fixed order (provider segmented control / credential summary / ONE
grouped selector / effort + read-only thinking line / refresh + actual-call
test), checkbox + duplicate manual selector REMOVED, old-sidecar compat mode.
Non-goals: everything in spec §8 (no credential mutation in Models, no
per-task credential binding, no route-schema thinking field, no test-history
persistence).

## 2. Design

**D1 — `effective_model_view_v2` (src/model_effective.py) is the single
source.** Shape per spec §5.1:

```
{ "providers": { "<p>": {credential_id, auth_mode, label} | null },
  "tasks": { "<task>": {
      "current_provider": "<p>",
      "providers": { "<p>": {
          "executable": bool,            # auth-mode-wide veto for this task
          "reason_code": str | null,
          "models": [ {id, label, status, visible_to_credential,
                       eligible, reason_code, thinking_mode} ],
          "cache_state": "ok|seed_only|never_discovered",
          "discovered_at": str | null } } } } }
```

Model-entry classification (P2.7 invariants preserved verbatim). **Round-2
MF2: discovery visibility and picker tier are ORTHOGONAL** — the entry gains
`visible_to_credential: true | false | null` (true = in this credential's
last successful listing, alias-resolved; false = `cache_state=ok` and absent;
null = channel can't establish it, i.e. `seed_only`/`never_discovered`).
`status` stays the VALUE-TIER GROUP:
- `visible`: default-tier registry models DISCOVERED under `cache_state=ok`
  (classify via `capability_for(discovered_id)`, keep the provider's REAL id;
  registry-unknown discovered ids EXCLUDED — route pin is their only path).
- `seed`: default-tier registry models ONLY when the channel is
  `seed_only`/`never_discovered` (`visible_to_credential=null`).
- `advanced`: advanced-tier registry models, always listed — with
  `visible_to_credential` annotated true/false/null (a discovered previous-gen
  model reads 舊版／進階 AND 此登入可見; single status could not say both).
- `route`: the saved route model when not already present — added ONLY to the
  route's own provider block (round-2 SF1). `eligible` = the provider-level
  veto result (an unknown model on a healthy provider stays selectable per
  acceptance 9 with `reason_code="model_not_in_registry"`,
  `thinking_mode="none"`; under `missing_active_credential` it is
  `eligible=false` like everything else — §4.2 disables the whole card).
- `pinned_only` models appear ONLY as a route entry — never via visible/seed.
- `eligible` = `task_auth_executable(task, provider, auth_mode, cap)`;
  per-model capability misses → `reason_code="task_capability_missing"`.
- Provider-level `executable=false` carries the auth-mode-wide veto:
  `missing_active_credential` (no active credential — entries still listed,
  all ineligible) or `task_auth_mode_unsupported` (e.g. cards × OAuth).
- `thinking_mode` from the registry capability (five values).

**D2 — legacy alias derived, not duplicated.** The existing
`effective_model_view()` becomes an adapter over v2: for each task, take
`providers[current_provider]` and fold back to the old shape — `verified` =
status `visible` AND `eligible`; `advanced` = status `advanced`/`seed`/`route`
entries (badge = status). **Round-2 MF2 counterexample encoded: a DISCOVERED
default-tier model that fails task capability (status=visible,
eligible=false) is EXCLUDED from the alias entirely** — matching today's
behavior at model_effective.py:107-129, where such a model enters neither
verified (executable check) nor advanced (the seed arm only fires on non-ok
channels). One computation → the two shapes can never drift; the ten
existing `tests/test_model_effective.py` pins keep passing with their BODIES
unchanged and become the adapter's regression net. **Alias removal gate (spec §5.1)**: a
separate follow-up slice removes the task-level alias only after (a) this
slice's UI is live-verified AND (b) the desktop app has shipped one release
whose ONLY consumer is the provider-indexed shape; filed in §8, not built.

**D3 — catalog route composition** (config_routes.py `model_catalog`): the
try/except block calls v2 once; response gains `effective.providers` +
provider-indexed `effective.tasks[*].providers` while keeping the alias keys
(`verified`/`advanced`/`cache_state`/`discovered_at`) at the task level —
additive-only, best-effort unchanged. Per-provider scope is resolved ONCE
(2 cache.get calls total, not 2×3). **Round-2 SF2**: `providers[p].label`
(and auth-mode display data) is joined from the `provider_credentials`
inventory the route already builds — `ActiveCredential` itself stays
label-free; exact-shape test pins the joined block.

**D4 — task-scoped test endpoint** `POST /config/model-task-test` (new; the
existing `/config/model-test` keeps its API-key-only meaning). Request
`{task, provider, model, effort}`; the backend resolves the ACTIVE credential
itself (spec §5.2 — a caller can never pass a credential id). Dispatch:

Auth-mode axis:

| active auth_mode | cards | ai_research |
|---|---|---|
| none | zero-call `missing_active_credential` | same |
| api_key | reuse `test_model()` (existing minimal paid call incl. effort-fallback) | same |
| api_key_pool | zero-call `task_test_unsupported` (pool execution unwired) | same |
| chatgpt_oauth | zero-call `task_auth_mode_unsupported` | bounded canary (below) |
| claude_code_oauth | zero-call `task_auth_mode_unsupported` | zero-call `task_test_unsupported` (§0-1 ruling; probe = that channel's health check) |

**Dispatch precedence (round-3 MF1 — ONE fixed order; each step only runs
when every earlier step passed, so an auth-mode veto can never be
misreported as a capability miss):**
1. **Credential**: no active credential → zero-call
   `missing_active_credential`.
2. **Auth-mode-wide veto**: cards×OAuth → `task_auth_mode_unsupported`;
   api_key_pool → `task_test_unsupported`; ai_research×claude_code_oauth →
   `task_test_unsupported` (§0-1). All zero-call.
3. **Model/task capability** — via a NEW standalone helper
   `task_capability_ok(task, capability) -> bool` extracted from
   `task_auth_executable`'s capability conditions (cards: tool_calling +
   structured_output; research: tool_calling) and REUSED by it, so the two
   can never drift. `task_auth_executable` is NOT called here — it folds the
   auth axis in and would misreport (e.g. cards×chatgpt_oauth on a fully
   capable gpt-5.4-mini returns False on the auth leg alone). Provider
   mismatch (`model_provider(model)` infers the other provider) or a
   known-registry model failing the helper → zero-call
   `task_capability_missing`.
4. **Visibility veto**: resolve the model through registry aliases FIRST
   (`capability_for`), then — ONLY when the active credential's cache is
   `cache_state=ok` — a model absent from the discovered listing →
   zero-call `model_not_visible`. `seed_only`/`never_discovered` NEVER veto
   (the explicit test is the first live evidence). Registry-unknown
   route/custom ids follow the same rule. **Cache READ failure at this step
   → zero-call `discovery_unavailable` for EVERY auth mode** (round-3 MF1:
   one fact, one behavior — the veto cannot be evaluated, so no billing
   path proceeds; api_key is not special-cased).
5. **Provider call** (api_key `test_model` / chatgpt canary).

OAuth (chatgpt) canary: `build_driver(provider, auth_mode, credential,
token_store, registry=None, dal=None, max_turns=1, timeout_s=45)` → drive
`stream_llm` with a minimal fixed prompt + the requested model/effort,
wrapped in `asyncio.wait_for(<endpoint budget>)`; collect events. `done` →
ok. `error` event: `code=reauth_required` → `reauth_required`; otherwise
`provider_call_failed` (redacted detail passthrough). **Any tool-seeking
event = failed canary** → abort + generator `aclose()`, `task_test_unsupported`.
**Round-2 MF4 hardening**: the whole dispatch wraps driver interaction in
try/except — a bare pre-flight raise (e.g. `MissingCredentialError` — the
Claude driver's sanctioned first-iteration raise, claude_code_sdk_driver.py:497,
kept as defense-in-depth even with the §0-1 ruling) maps to
`reauth_required`; any other exception → `provider_call_failed`, NEVER a 500.
Timeout → `provider_call_failed` with a timeout detail + the stream torn
down (`aclose()`), asserted by test. **Zero persistence**: the canary never
touches the thread store / chat history / research-run seams — pinned by a
construction-recording test.
Response: `{task, provider, model, effort, auth_mode, credential_id,
status: ok|error|unsupported, error_code, latency_ms, tested_at,
fallback_effort, warning}` — no secret ever serialized; api_key results are
translated (`missing_credential` → `missing_active_credential`, error →
`provider_call_failed`).

**D5 — frontend task card** (Settings.tsx, replacing the :2029 picker and the
:2168 manual override): fixed §4 order —
1. title/description/route-authority badge (kept as-is);
2. provider segmented control `OpenAI | Anthropic` (draft-only; switching
   clears an invalid model, resets effort to `default`, never auto-saves);
3. active-credential summary line (label + auth-mode zh label +
   discovery state + 最後驗證可見) from `effective.providers` — read-only;
   missing → 「尚未設定此 provider 的登入」+ 前往 Providers link, selector
   and save disabled **in the frontend only** (backend stays warning-only).
   **Round-2 MF5 + round-3 MF3 — save gating is PAGE-level and
   compat-safe**: the 儲存 button and `save()` live in Settings (:252),
   outside ModelRoutingSection. A normalization layer
   `providerContexts(effective?.providers, catalog.credentials)` is the
   SINGLE source for per-provider active-credential context (v2 block when
   present; otherwise derived from the active row in `catalog.credentials` —
   the spec's compat rule), shared by the task-card summary AND the save
   gate. The gate itself is `blockedRouteSaves(draft, baseline, contexts) ->
   {task, reason}[]` where `baseline = catalog.routes`. **Ruling (round-3
   MF3): only DIRTY tasks block** — a task blocks the global save iff the
   user changed it this session (`draft[task] != baseline[task]`) AND its
   drafted provider has no active credential; a pre-existing
   missing-credential route never locks unrelated tasks out of saving.
   Unit tests on both helpers (incl. compat-mode derivation and the
   dirty-vs-pre-existing split) + ONE Settings-level wiring test proving
   the button/`save()` actually consult the gate;
4. ONE grouped `<select>`: optgroups 此登入可見 / 候選／未驗證 / 舊版／進階 /
   目前路由; a discovered advanced-tier entry additionally reads
   ·此登入可見 from `visible_to_credential` (round-2 MF2 orthogonality);
   ineligible options rendered `disabled` **with the reason INSIDE the option
   text** (e.g. 「GPT-5.5 — 缺結構化輸出」) plus an adjacent note listing the
   card's ineligible reasons and `aria-disabled` — `title` on `<option>` is
   unreliable/unfocusable (round-2 SF3); 自訂 model id = a button beside the
   selector revealing the inline input (not a second picker), value always
   marked unverified;
5. effort select + read-only thinking line (five-mode zh copy from
   `thinking_mode`);
6. 更新可用清單 (reuses `runDiscoveryAndRefreshCatalog` with the selected
   provider's active credential id — the card→helper wiring gets its own
   test, round-2 MF5) + 實際測試目前選擇 (new endpoint via a dedicated
   `runTaskModelTest` api.ts helper whose timeout is **60_000 ms — strictly
   above the backend's 45 s canary bound** (DEFAULT_TIMEOUT_MS=15_000 would
   abort the UI while the paid backend call keeps running); pinned by test.
   **Round-3 MF2 — the result is a SNAPSHOT, not a task-level flag**: the
   stored result carries `{task, provider, model, effort, credential_id}`
   captured at test time; it renders ONLY while ALL five still equal the
   current draft + the current active credential (from `providerContexts`).
   Any provider/model/effort change or a discovery-refresh that lands a
   different active credential hides it immediately (replaced by 「選擇已
   變更——重新測試」) — a mini-PASS can never keep claiming 實際呼叫通過
   after switching to Luna. Result line shows status/latency/auth-mode/
   error-code action text);
7. existing reset + status text.
`reauth_required` anywhere → text + 前往 Providers link (re-login stays in
Providers, §4.2). **Compat mode** (new frontend, old sidecar — spec §5.1):
`effective.tasks[task].providers` absent → provider control still renders;
current provider uses the legacy verified/advanced partition; the alternate
provider lists registry seeds marked unverified; task-test button disabled
with 「請重啟／更新 sidecar」; the old checkbox / manual override are NOT
revived.

**D6 — error-code → UI action map** (spec §6): one exported
`taskTestActionCopy(error_code)` table —
`missing_active_credential`→前往 Providers;`reauth_required`→前往 Providers
(重新登入);`task_auth_mode_unsupported`→此任務需 API key;
`model_not_visible`(only under `cache_state=ok`)→跑 更新可用清單;
`model_not_in_registry`→自訂/未知模型警告;`discovery_unavailable`→稍後重試;
`provider_call_failed`→顯示 redacted detail;`task_capability_missing`→此模型
缺此任務能力;`task_test_unsupported`→此通道無法安全測試。Never a blanket
「模型不可用」.

## 3. Tasks (TDD — every test RED before its code)

**Task 1 — v2 view + classification (model_effective.py).**
RED (tests/test_model_effective.py, reusing its store/cache fixtures):
1. `test_v2_both_providers_present_regardless_of_route` — all three tasks
   openai-routed; anthropic block still fully populated (THE §10 regression).
2. `test_v2_entry_schema_and_grouping` — visible/seed/advanced/route statuses,
   real dated id kept, registry-unknown discovered ids absent, pinned_only
   absent unless routed.
3. `test_v2_eligibility_split_provider_vs_model` — cards×oauth: provider veto
   `task_auth_mode_unsupported` with entries listed; a
   no-structured-output model under cards: entry-level
   `task_capability_missing`, still listed, `eligible=false`.
4. `test_v2_route_pin_unknown_model_is_eligible_with_warning` — the
   acceptance-9 ruling (eligible=true + `model_not_in_registry`), AND the
   route entry appears ONLY in the route provider's block (round-2 SF1);
   under a missing credential it is eligible=false like its siblings.
5. `test_v2_missing_credential_provider_reason` — provider executable=false,
   `missing_active_credential`, entries all ineligible.
6. `test_v2_thinking_mode_carried_from_registry` — five-mode passthrough +
   route-unknown → "none".
7. `test_v2_visibility_is_orthogonal_to_tier` (round-2 MF2) — a DISCOVERED
   advanced-tier model: status="advanced" AND visible_to_credential=true;
   an undiscovered one under cache ok: false; seed channel: null.
8. `test_v2_discovered_ineligible_default_stays_out_of_alias` (round-2 MF2
   counterexample) — a discovered default-tier model failing task capability:
   present in v2 (visible, eligible=false, task_capability_missing) and
   ABSENT from the folded legacy alias — byte-matching today's exclusion.
9. `test_legacy_alias_is_derived_from_v2` — for the P2.7 fixture scenarios,
   `effective_model_view()` output is byte-equal to folding v2 (and the ten
   EXISTING test bodies stay green unmodified — the real adapter net).

**Task 2 — catalog composition (config_routes.py).**
RED (tests/test_model_effective.py route test + tests/test_model_routing.py):
1. `test_model_catalog_effective_gains_provider_indexed_shape` — additive:
   old task-level alias intact, new `providers` maps present (label joined
   from the credentials inventory — exact shape), single best-effort try
   still swallows a v2 failure into `{"tasks": {}}`.
2. `test_v2_resolves_each_provider_scope_once` (round-3 SF3) — a recording
   cache fake counts `get` calls: exactly 2 for the full catalog (the
   performance contract becomes a test, not prose).
3. Ledger: `test_model_catalog_route_gains_additive_effective_block` (:170)
   must stay green unchanged.

**Task 3 — task-test endpoint (config_routes.py + src/model_task_canary.py).**
Dispatch core lives in a new module (route stays thin, handler-direct
testable). RED (new tests/test_model_task_test.py, house fakes):
1. `test_dispatch_matrix_zero_call_arms` — none/pool/cards×oauth arms AND
   `ai_research×claude_code_oauth` (§0-1 ruling → `task_test_unsupported`)
   return the pinned error_codes with a recording fake proving ZERO
   client/driver construction (§10 zero-call requirement).
2. `test_model_axis_zero_call_vetoes` (round-2 MF3) — provider mismatch →
   `task_capability_missing`; known-registry model missing the task
   capability (via `task_capability_ok`) → `task_capability_missing`;
   `cache_state=ok` + model absent from the listing → `model_not_visible`;
   an ALIAS of a listed model (e.g. `gpt-5.6` → sol) is NOT vetoed; all
   zero-call.
2b. `test_dispatch_precedence_auth_before_capability` (round-3 MF1) —
   cards × chatgpt_oauth with a FULLY capable model (gpt-5.4-mini) →
   `task_auth_mode_unsupported`, NEVER `task_capability_missing`; and
   `task_capability_ok` is asserted equal to `task_auth_executable`'s
   verdict under `auth_mode="api_key"` for every registry model (the
   no-drift pin between helper and source).
3. `test_seed_channels_never_visibility_veto` (round-2 MF3) — seed_only /
   never_discovered: unknown/custom model proceeds to the canary (first live
   evidence).
3b. `test_cache_read_failure_is_discovery_unavailable_for_all_auth_modes`
   (round-3 MF1) — cache raising at veto time → zero-call
   `discovery_unavailable` for api_key AND chatgpt_oauth alike (recording
   fakes prove `test_model`/driver never constructed).
4. `test_api_key_arm_reuses_test_model_and_translates` — fake `test_model`
   capture: called once with model/effort/credential_id=active; ok passes
   latency/fallback through; missing→`missing_active_credential`;
   error→`provider_call_failed`.
5. `test_oauth_research_canary_bounds` — recording fake driver: built with
   `max_turns=1`, `registry is None`, `timeout_s<=45`; minimal prompt; done →
   ok + latency + tested_at.
6. `test_oauth_canary_reauth_and_model_not_found` — error event with
   `code=reauth_required` → `reauth_required`; plain error → 
   `provider_call_failed` with redacted detail (the luna case's offline twin).
7. `test_oauth_canary_tool_event_aborts_unsupported` — a tool event → 
   `task_test_unsupported`, stream `aclose()`d (teardown recorded).
8. `test_canary_timeout_and_bare_raise_never_500` (round-2 MF4) — a fake
   driver that hangs → endpoint budget timeout → `provider_call_failed`
   (timeout detail) + stream torn down; a fake driver whose stream RAISES
   `MissingCredentialError` on first `__anext__` → `reauth_required`; any
   other bare exception → `provider_call_failed`; the handler never raises.
9. `test_canary_zero_persistence` (round-2 MF4) — thread-store / chat-history
   / research-run seams monkeypatched to record: zero constructions/writes
   across every arm.
10. `test_no_secret_in_response` — serialized response contains no token/key
    material (fake secrets planted in every store).
11. Route-level: `test_task_test_route_shape` — request validation (unknown
    task/provider → 422/400), response schema keys pinned.

**Task 4 — frontend task card (Settings.tsx + api.ts + tests).**
RED (ModelRoutingSection.test.ts + new TaskModelCard tests, house harness):
1. `provider control visible without any disclosure; switching updates draft,
   clears incompatible model, resets effort` (replaces :177 — intent moved).
2. `one grouped selector renders four optgroups; ineligible options disabled
   with reason title` (replaces :132).
3. `EXACT absence test: no 顯示進階模型 checkbox, no manual-override details,
   no duplicate full-seed selector` (§10; replaces :158's collapsed pin).
4. `custom-id button reveals inline input marked unverified`.
5. `credential summary renders label/auth-mode/state/timestamp; missing
   credential disables the selector with 前往 Providers`.
6. `blockedRouteSaves helper: drafted task on a credential-less provider →
   blocked with reason; healthy drafts → empty` + `Settings-level wiring
   test: the 儲存 button disables and save() refuses while blocked`
   (round-2 MF5 — page-level, not component-level).
7. `card refresh button invokes runDiscoveryAndRefreshCatalog with the
   SELECTED provider's active credential id` (round-2 MF5 wiring).
8. `thinking line renders per thinking_mode (five modes), read-only`.
9. `runTaskModelTest helper uses a 60_000ms timeout (pinned above the 45s
   backend bound); task-test button posts {task,provider,model,effort};
   result renders status+latency; error_code maps to the D6 action copy;
   ineligible reason appears in option TEXT + adjacent note (not title)`.
10. `route-pinned unknown model appears in 目前路由 group, selectable, with
    warning` (evolves :208).
11. `compat mode: providers absent → provider control still present, legacy
    partition for current provider, alternate provider = catalog.models seeds
    ALL marked 未驗證（舊 sidecar 相容模式）, test button disabled with
    請重啟／更新 sidecar; checkbox/manual override NOT revived` (replaces
    :170 — intent moved). **Round-3 SF1 ruling: the temporary widening is
    ACCEPTED and labeled** — `catalog.models` (routing-seed view) includes
    two pinned_only ids (gpt-5.5 / gpt-5.4) the frontend cannot filter
    (ModelOption carries no visibility tier); compat is a degraded mode, every
    entry is explicitly unverified, and upgrading the sidecar restores the
    honest partition. Pinned by the same test.
11b. `oauth research test copy: 「消耗訂閱額度，非 API 帳單」 renders beside
    the task-test control when the selected provider's auth mode is OAuth`
    (round-3 SF2 — the spec-required billing copy gets a named test).
11c. `test-result snapshot guard (round-3 MF2): test with mini → result
    shows; switch model to Luna → result replaced by 選擇已變更; switch
    back → still hidden (stale); provider/effort switches and an active-
    credential change via refreshed catalog behave the same`.
11d. `providerContexts normalization: v2 present → passthrough; absent →
    derived from catalog.credentials active row; neither → null context
    (selector disabled)` + `blockedRouteSaves dirty-vs-pre-existing split:
    a baseline route already on a credential-less provider does NOT block;
    the same task freshly drafted onto it DOES` (round-3 MF3).
12. api.ts DTO additions (`EffectiveProviderModels`, provider-indexed
    `EffectiveTaskModels.providers?`, `visible_to_credential`,
    `TaskModelTestResult`) — typecheck-level.
Then typecheck + build.

**Task 5 — acceptance sweep + copy.**
Walk spec §9's 11 criteria; each maps to a named test from Tasks 1–4 (matrix
in the PR notes); add any gap test found. Copy pass: zh labels for statuses/
groups/thinking modes/action texts pinned in one exported table (terminology
rule: no invented shorthand).

**Task 6 — gates, A/B, review-ready.**
Focused backend (test_model_effective, test_model_routing,
test_model_task_test, test_chatgpt_oauth_routes) + FULL frontend suite +
typecheck + build + no-PG smoke. Full virgin A/B per house protocol (failure
SETS + collect-diff exact accounting). Review-ready hand-off; §7 live gate
BEFORE merge.

## 4. Ledger sweep (checked at RED time)

- ModelRoutingSection.test.ts :132/:158/:170/:177 = obsolete siblings
  (replacement mapping in Task 4; :208 evolves; :91/:97/:148 unaffected).
- tests/test_model_effective.py: the ten EXISTING test bodies must stay
  GREEN **unmodified** (adapter net) — Task 1 ADDS tests to the same file,
  which is expected; edits to the existing bodies are the red flag
  (round-2 SF4 wording).
- `EffectiveModelPicker` deleted → grep its references (Settings.tsx only);
  `EFFECTIVE_BADGE_LABELS` repurposed or removed with it.
- api.ts `EffectiveTaskModels` consumers; `modelSelect.ts` helper reused
  as-is (its 2 tests untouched).
- `test_chatgpt_oauth_routes.py` discovery tests unaffected (endpoint
  untouched); new task-test route must NOT import-cycle model_effective ↔
  config_routes (dispatch module keeps the route thin).
- Frontend suite count changes: expect net +N with removals accounted
  one-by-one in the A/B report (removed tests named, not netted).

## 5. Out of scope / follow-ups (filed, not built)

- Task-level alias removal slice (gate in D2).
- Test-history persistence (spec §8).
- Provider capability display P2.5 overlap — unchanged.
- **Claude SDK driver `tools_disabled` mode** (round-2 MF1 option A): an
  explicit build path emitting `tools=[]` / `allowed_tools=[]` /
  `mcp_servers={}`, proven by REAL option-building tests (not fake factory
  kwargs) — would upgrade `ai_research × claude_code_oauth` task-test from
  `task_test_unsupported` to a true bounded canary.

## 6. Live gate (§7, BEFORE merge; premium calls user-gated)

1. Sidecar restart on the branch; catalog shows both providers for every
   task; picker inspection per §9 criteria 1–4.
2. OpenAI api_key route flow: select provider, pick a visible model, 實際測試
   (gpt-5.4-mini class), save; verify route persisted.
3. Anthropic api_key route flow: same on the anthropic side (sonnet-class
   test call — cheap tier per live-verify rule).
4. **The luna acceptance pair (from the S3 gate)**: with local:7
   (chatgpt_oauth) active, task-test `gpt-5.6-luna` → expect
   `provider_call_failed` ("Model not found" family, redacted); task-test
   `gpt-5.4-mini` → expect ok — list-vs-execute rendered honestly in the UI.
5. reauth affordance path: only if a token is actually stale at gate time
   (do NOT manufacture one); otherwise covered by tests.
6. Compat mode spot-check: new UI against the OLD sidecar build (pre-merge
   master) — provider control + degraded copy, no crash.

## 7. Review log

- Round 2 (2026-07-11): 3 must-fix + 3 should-fix, all verified real. MF1 —
  `task_auth_executable` has no separable capability leg (cards×oauth returns
  False on the auth axis before capability is ever evaluated) → D4 now fixes
  ONE five-step precedence (credential → auth veto → NEW `task_capability_ok`
  helper extracted from and reused by `task_auth_executable` → visibility →
  call), plus the :160 contradiction resolved: cache-read failure at veto
  time → `discovery_unavailable` for EVERY auth mode (one fact, one
  behavior); precedence + no-drift + all-modes tests added (2b/3b). MF2 —
  test results become five-field SNAPSHOTS `{task, provider, model, effort,
  credential_id}` rendered only while equal to the current draft + active
  credential; any switch or credential change hides them (「選擇已變更——重新
  測試」); interaction test 11c. MF3 — `providerContexts(effective?.providers,
  catalog.credentials)` normalization shared by card summary and save gate
  (compat-safe per the spec's credentials fallback); gate re-signed
  `blockedRouteSaves(draft, baseline, contexts)` with the RULING that only
  DIRTY tasks block (pre-existing missing-credential routes never lock
  unrelated saves); tests 11d. SF1 — compat widening (two pinned_only ids
  via catalog.models) ACCEPTED + labeled 未驗證（舊 sidecar 相容模式）,
  frontend cannot filter tiers; SF2 — billing copy gets named test 11b;
  SF3 — D1 shape example carries `visible_to_credential`, and the 2×
  cache.get contract becomes counting test (Task 2-2).
- Round 1 (2026-07-11): 5 must-fix + 4 should-fix, ALL verified real against
  code before fixing. MF1 — my grounding was wrong: `registry=None` fail-fasts
  in `build_ark_mcp_server` (:354) before any model call → RULED
  `task_test_unsupported` for the Claude OAuth arm this slice (spec §4.4's own
  fallback), driver `tools_disabled` mode filed as follow-up. MF2 — the
  everything-else adapter was NOT byte-identical (discovered-but-ineligible
  default models are excluded today, model_effective.py:107-129) → entry
  gains orthogonal `visible_to_credential: true|false|null`, status stays the
  value-tier group, adapter excludes ineligible-visible; counterexample +
  orthogonality tests added. MF3 — model-axis zero-call rules defined
  (provider mismatch / capability miss → `task_capability_missing`;
  alias-resolved absence under `cache_state=ok` → `model_not_visible`; seed
  channels never veto — first-evidence canaries allowed; cache-read failure →
  `discovery_unavailable`). MF4 — endpoint hardening: bare pre-flight raises
  (MissingCredentialError :497) classified not 500; timeout + `aclose()`
  teardown + zero-persistence tests added. MF5 — save gating moved to a
  page-level pure helper (`blockedRouteSaves`) with a Settings wiring test
  (save() lives at Settings.tsx:252, outside the section); refresh→helper
  wiring test added; `runTaskModelTest` pinned at 60s > the 45s backend
  bound (DEFAULT_TIMEOUT_MS=15s would abort the UI mid-paid-call). SF1
  route entry only in its provider block + veto-gated eligible; SF2 label
  joined from the credentials inventory (ActiveCredential stays label-free);
  SF3 reasons in option text + adjacent note + ARIA, not `title`; SF4 ledger
  reworded to "existing test bodies unmodified". Roles updated: user side
  implements, Claude reviews.
