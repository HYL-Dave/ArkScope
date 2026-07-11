# Models Routing UX — Implementation Plan (focused P2.8 slice)

> **Status: DRAFT FOR REVIEW 2026-07-11.** Roles: Claude authors + implements,
> user reviews. Implements the APPROVED spec
> `docs/superpowers/specs/2026-07-11-model-routing-settings-ux-design.md`
> (round 2 absorbed). Authority on any conflict: the spec. Sequence per spec
> §11: S3 lifecycle hotfix SHIPPED 2026-07-11 (`e7e144b`) — this slice is next.
>
> **Live evidence already in hand (S3 §7 gate)**: the ChatGPT backend LISTS
> `gpt-5.6-luna` but execution rejects it ("Model not found") while
> `gpt-5.4-mini` executes — the exact 「此登入可見 ≠ 實際呼叫通過」 divergence
> §3.4 splits. That pair is pinned below as the first §4.4 live acceptance
> case.

## 0. Grounding corrections to the spec (verified against code 2026-07-11)

1. **§4.4 `--tools ""`** — the Claude research path is the **Agent SDK driver**
   (`claude_code_sdk_driver.py`), not a raw `claude -p` invocation; the bound
   is enforced via SDK options `tools=[]` + an `mcp__ark__*` allowlist that is
   EMPTY when `registry=None` (driver docstring :15, ctor :402 accepts
   `registry/dal/max_turns/timeout_s`). Same effect, different mechanism; the
   spec's intent (no built-ins, no ArkScope tools) is enforceable as written.
2. **Both subscription drivers** accept `max_turns` + `timeout_s` +
   `registry=None` through `build_driver(...)` (factory.py:88) — the §4.4
   canary bounds need no driver changes.
3. `EffectiveModelPicker` (Settings.tsx:2029) and the manual-override
   `<details>` (:2168) are the two structures §4.1/§10 remove; both live
   inside `ModelRoutingSection` (:2096, exported + tested).

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
          "models": [ {id, label, status, eligible, reason_code, thinking_mode} ],
          "cache_state": "ok|seed_only|never_discovered",
          "discovered_at": str | null } } } } }
```

Model-entry classification (P2.7 invariants preserved verbatim):
- `visible`: walk DISCOVERED ids when `cache_state=ok`, classify via
  `capability_for(discovered_id)`, keep the provider's REAL id;
  registry-unknown discovered ids are EXCLUDED (route pin is their only path).
- `seed`: default-visibility registry models not visible, ONLY when the
  channel is `seed_only`/`never_discovered`.
- `advanced`: advanced-visibility registry models, always listed.
- `route`: the saved route model when not already present. **Ruling encoded**
  (spec §4.1 + acceptance 9): a route entry is `eligible=true` (it IS the
  current route — never auto-replaced, never unselectable) with
  `reason_code="model_not_in_registry"` when unknown (the warning source) and
  `thinking_mode="none"` (no known behavior to display).
- `pinned_only` models appear ONLY as a route entry — never via visible/seed.
- `eligible` = `task_auth_executable(task, provider, auth_mode, cap)`;
  per-model capability misses → `reason_code="task_capability_missing"`.
- Provider-level `executable=false` carries the auth-mode-wide veto:
  `missing_active_credential` (no active credential — entries still listed,
  all ineligible) or `task_auth_mode_unsupported` (e.g. cards × OAuth).
- `thinking_mode` from the registry capability (five values).

**D2 — legacy alias derived, not duplicated.** The existing
`effective_model_view()` becomes an adapter over v2: for each task, take
`providers[current_provider]` and fold entries back to the old
`verified` (status=visible & eligible) / `advanced` (everything else, badge =
status) partition. One computation → the two shapes can never drift; the ten
existing `tests/test_model_effective.py` pins keep passing UNCHANGED and
become the adapter's regression net. **Alias removal gate (spec §5.1)**: a
separate follow-up slice removes the task-level alias only after (a) this
slice's UI is live-verified AND (b) the desktop app has shipped one release
whose ONLY consumer is the provider-indexed shape; filed in §8, not built.

**D3 — catalog route composition** (config_routes.py `model_catalog`): the
try/except block calls v2 once; response gains `effective.providers` +
provider-indexed `effective.tasks[*].providers` while keeping the alias keys
(`verified`/`advanced`/`cache_state`/`discovered_at`) at the task level —
additive-only, best-effort unchanged. Per-provider scope is resolved ONCE
(2 cache.get calls total, not 2×3).

**D4 — task-scoped test endpoint** `POST /config/model-task-test` (new; the
existing `/config/model-test` keeps its API-key-only meaning). Request
`{task, provider, model, effort}`; the backend resolves the ACTIVE credential
itself (spec §5.2 — a caller can never pass a credential id). Dispatch:

| active auth_mode | cards | ai_research |
|---|---|---|
| none | zero-call `missing_active_credential` | same |
| api_key | reuse `test_model()` (existing minimal paid call incl. effort-fallback) | same |
| api_key_pool | zero-call `task_test_unsupported` (pool execution unwired) | same |
| chatgpt_oauth | zero-call `task_auth_mode_unsupported` | bounded canary (below) |
| claude_code_oauth | zero-call `task_auth_mode_unsupported` | bounded canary (below) |

OAuth canary: `build_driver(provider, auth_mode, credential, token_store,
registry=None, dal=None, max_turns=1, timeout_s=45)` → drive `stream_llm`
with a minimal fixed prompt + the requested model/effort; collect events.
`done` → ok. `error` event: `code=reauth_required` → `reauth_required`;
otherwise `provider_call_failed` (redacted detail passthrough). **Any
tool-seeking event = failed canary** → abort, `task_test_unsupported`
(bounds not enforceable). Response: `{task, provider, model, effort,
auth_mode, credential_id, status: ok|error|unsupported, error_code,
latency_ms, tested_at, fallback_effort, warning}` — no secret ever
serialized; api_key results are translated (`missing_credential` →
`missing_active_credential`, error → `provider_call_failed`).

**D5 — frontend task card** (Settings.tsx, replacing the :2029 picker and the
:2168 manual override): fixed §4 order —
1. title/description/route-authority badge (kept as-is);
2. provider segmented control `OpenAI | Anthropic` (draft-only; switching
   clears an invalid model, resets effort to `default`, never auto-saves);
3. active-credential summary line (label + auth-mode zh label +
   discovery state + 最後驗證可見) from `effective.providers` — read-only;
   missing → 「尚未設定此 provider 的登入」+ 前往 Providers link, selector
   and save disabled **in the frontend only** (backend stays warning-only);
4. ONE grouped `<select>`: optgroups 此登入可見 / 候選／未驗證 / 舊版／進階 /
   目前路由; ineligible options rendered `disabled` with the reason in
   `title`; 自訂 model id = a button beside the selector revealing the inline
   input (not a second picker), value always marked unverified;
5. effort select + read-only thinking line (five-mode zh copy from
   `thinking_mode`);
6. 更新可用清單 (reuses `runDiscoveryAndRefreshCatalog` with the selected
   provider's active credential id) + 實際測試目前選擇 (new endpoint; result
   line shows status/latency/auth-mode/error-code action text);
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
   acceptance-9 ruling (eligible=true + `model_not_in_registry`).
5. `test_v2_missing_credential_provider_reason` — provider executable=false,
   `missing_active_credential`, entries all ineligible.
6. `test_v2_thinking_mode_carried_from_registry` — five-mode passthrough +
   route-unknown → "none".
7. `test_legacy_alias_is_derived_from_v2` — for the P2.7 fixture scenarios,
   `effective_model_view()` output is byte-equal to folding v2 (and the ten
   EXISTING tests stay green untouched — the real adapter net).

**Task 2 — catalog composition (config_routes.py).**
RED (tests/test_model_effective.py route test + tests/test_model_routing.py):
1. `test_model_catalog_effective_gains_provider_indexed_shape` — additive:
   old task-level alias intact, new `providers` maps present, single
   best-effort try still swallows a v2 failure into `{"tasks": {}}`.
2. Ledger: `test_model_catalog_route_gains_additive_effective_block` (:170)
   must stay green unchanged.

**Task 3 — task-test endpoint (config_routes.py + src/model_task_test.py).**
Dispatch core lives in a new module (route stays thin, handler-direct
testable). RED (new tests/test_model_task_test.py, house fakes):
1. `test_dispatch_matrix_zero_call_arms` — none/pool/cards×oauth arms return
   the pinned error_codes with a recording fake proving ZERO client/driver
   construction (§10 zero-call requirement).
2. `test_api_key_arm_reuses_test_model_and_translates` — fake `test_model`
   capture: called once with model/effort/credential_id=active; ok passes
   latency/fallback through; missing→`missing_active_credential`;
   error→`provider_call_failed`.
3. `test_oauth_research_canary_bounds` — recording fake driver: built with
   `max_turns=1`, `registry is None`, `timeout_s<=45`; minimal prompt; done →
   ok + latency + tested_at.
4. `test_oauth_canary_reauth_and_model_not_found` — error event with
   `code=reauth_required` → `reauth_required`; plain error → 
   `provider_call_failed` with redacted detail (the luna case's offline twin).
5. `test_oauth_canary_tool_event_aborts_unsupported` — a tool event → 
   `task_test_unsupported`, stream abandoned.
6. `test_no_secret_in_response` — serialized response contains no token/key
   material (fake secrets planted in every store).
7. Route-level: `test_task_test_route_shape` — request validation (unknown
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
   credential disables selector+save with 前往 Providers`.
6. `thinking line renders per thinking_mode (five modes), read-only`.
7. `task-test button posts {task,provider,model,effort}; result renders
   status+latency; error_code maps to the D6 action copy`.
8. `route-pinned unknown model appears in 目前路由 group, selectable, with
   warning` (evolves :208).
9. `compat mode: providers absent → provider control still present, legacy
   partition for current provider, alternate provider = registry seeds
   unverified, test button disabled with 請重啟／更新 sidecar; checkbox/manual
   override NOT revived` (replaces :170 — intent moved).
10. api.ts DTO additions (`EffectiveProviderModels`, provider-indexed
    `EffectiveTaskModels.providers?`, `TaskModelTestResult`) — typecheck-level.
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
- tests/test_model_effective.py ten pins must stay GREEN untouched (adapter
  net) — any edit there is a red flag.
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

- (pending review round 1)
