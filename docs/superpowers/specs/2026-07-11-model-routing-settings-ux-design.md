# Model Routing Settings UX Design

> **Status: ADOPTED; LIVE COMPLETE, 2026-07-12. Merged through `2fb1c4f`.**
> This is a focused P2.8 design slice prompted by the first live inspection of
> the P2.7 picker. It preserves
> the existing Settings boundary: `Providers` owns credentials, login, and
> credential-scoped discovery; `Models` owns per-task provider/model/effort
> routing. Implementation and review are complete; the live gate proved both
> the successful-call and honest-failure states before merge.
>
> **2026-07-12 subscription-task amendment:** task routing uses the active
> credential for the selected provider as its transport and billing authority.
> Card generation and translation therefore use API billing for an active API
> key, ChatGPT subscription allowance for active `chatgpt_oauth`, and Claude
> subscription allowance for active `claude_code_oauth`. Unsupported models
> fail explicitly; ArkScope never borrows another credential, provider, model,
> or billing path.

## 1. Problem

P2.7 made model availability honest in the backend, but the Models UI hides the
reasoning needed to use it:

- each task's effective list is calculated only for that task's currently saved
  provider, so three OpenAI routes produce three OpenAI-only pickers;
- the four visible OpenAI entries are the intended default-value set, but the UI
  does not explain that they are the intersection for the active OpenAI
  credential;
- changing to Anthropic is possible only inside a collapsed `手動覆寫` block;
- a checkbox controls whether older, seed, custom, and pinned entries appear;
- `已驗證可用` conflates several different facts: discovery visibility,
  deterministic task eligibility, and a real model call;
- `測試此模型` is currently a direct API-key SDK call even when the active
  credential is OAuth, so the button can test a different path from the route
  the user is configuring.

The observed result is not user misunderstanding. The surface presents one
provider as the normal path, hides the other as an override, and assigns
overlapping labels to different checks.

## 2. Grounded Current State

The design is based on these current code facts:

1. Settings already has separate `models` and `providers` sections. This split
   remains.
2. `effective_model_view()` reads `route.provider` before resolving a credential,
   so it returns one provider partition per task, not both provider alternatives.
3. `EffectiveModelPicker` owns the `顯示進階模型` checkbox; the full cross-provider
   selector lives under `手動覆寫`.
4. `/config/model-test` calls `test_model()`, which resolves a direct API-key
   credential and does not dispatch through ChatGPT OAuth or Claude OAuth.
5. The active Anthropic credential observed in the P2.7 live run was
   `claude_code_oauth`. That channel is honestly `seed_only`: it cannot
   live-list provider models. The original implementation also left card tasks
   unwired; the 2026-07-12 amendment closes that execution gap through the
   installed Claude Agent SDK's JSON-schema output mode.
6. The active OpenAI API-key credential had live discovery data, so OpenAI's four
   default-value models appeared as verified options.

## 3. Product Decisions

### 3.1 Preserve the existing ownership boundary

`Providers` remains the only place to:

- create, edit, activate, delete, log in, or re-login a credential;
- inspect every credential row;
- run credential-level OAuth probes;
- view detailed discovery results for a specific credential.

`Models` remains the place to choose the provider, model, and effort for each
task. It may read the selected provider's active credential status, trigger the
existing discovery operation for that active credential as a contextual
shortcut, and run a task-scoped model check. It never mutates credential
metadata or lets a task bind directly to a credential id.

### 3.2 Provider first, then model

Each task card exposes a visible provider segmented control:

`OpenAI | Anthropic`

Provider selection is no longer inferred from a model hidden in an advanced
control. Switching provider:

- changes only the draft route;
- clears the draft model unless it is valid for the new provider;
- resets effort to `default` because effort vocabularies differ;
- does not auto-save or auto-select a model.

Both providers are always visible. A provider with no active credential may be
selected for inspection, but its model selector and save path remain disabled
until the user activates a credential in Providers.

### 3.3 One active credential per provider remains the authority

Models displays the provider's active credential as read-only context:

- display label;
- auth mode (`API key`, `ChatGPT OAuth`, or `Claude OAuth`);
- availability/discovery state;
- last successful discovery timestamp when present.

Changing the active credential remains a Providers action. V1 does not add
per-task credential binding.

### 3.4 Three states must never share one label

The UI uses these distinct terms:

| State | Meaning | Authority |
|---|---|---|
| `此登入可見` | The selected active credential's last successful discovery contained this model. | Discovery cache |
| `可供此任務使用` | Registry capabilities and the task/auth-mode matrix permit this route. No network call implied. | Code-reviewed registry + `task_auth_executable()` |
| `實際呼叫通過` | The user explicitly ran a small call through the selected provider/auth path and it succeeded at that time. | Ephemeral test result |

`seed_only` is rendered as `候選模型，無法由此登入線上列出`, never as verified.
`never_discovered` is rendered as `尚未檢查此登入可見模型` or the equivalent
`尚未探索此登入的模型`, never as empty or unavailable. The same visible
verification action may serve first discovery and later re-verification. A
timestamped discovery result is an observation, not a permanent entitlement
promise.

## 4. Task Card Interaction

Each task card follows one fixed vertical order:

1. Task title, description, and current route-authority badge.
2. Provider segmented control.
3. Active credential summary and status.
4. Model selector.
5. Effort selector plus read-only thinking behavior.
6. Availability refresh and actual-call test actions.
7. Existing reset action and result/status text.

### 4.1 Model selector

There is one model selector for the selected provider. It replaces both the
checkbox-controlled picker and the duplicate hidden full-seed selector.

Options are grouped and labeled inside the selector:

- `此登入可見`;
- `候選／未驗證`;
- `舊版／進階`;
- `目前路由` when a pinned model would otherwise disappear.

The value-oriented P2.7 policy remains: current high-value models are the normal
group; previous-generation entries are secondary; `pinned_only` models appear
only when already routed. Unknown provider-discovered ids do not flood the list.

Custom model ids remain supported through a clearly labeled `自訂 model id`
command adjacent to the selector. They are not hidden inside a second model
picker. A custom id is always marked unverified until an explicit call succeeds.

When `cache_state="ok"`, an advanced entry with
`visible_to_credential=false` remains listed but is disabled with
`model_not_visible`; this matches the task-test endpoint's zero-call visibility
veto and prevents selecting a model that this credential's successful listing
omitted. This stronger selector veto does not apply when visibility is unknown
under `seed_only` or `never_discovered`. A `route` entry is also exempt from the
selector veto so an existing saved route remains visible and selectable rather
than being silently displaced; an explicit task test may still report
`model_not_visible`.

### 4.2 Missing or incompatible credentials

If no active credential exists, the card shows `尚未設定此 provider 的登入` and a
`前往 Providers` action. Model selection, actual testing, and saving that draft
route are disabled **in the frontend**. The backend `PUT /config/model-routes`
keeps its existing warning-only capability contract for compatibility with
custom ids, import/export, and older clients; this slice does not turn a missing
active credential into a new backend 400.

If the active auth mode cannot execute the task, the card names the reason. The
task runtime must first attempt the selected provider's active credential path:
API-key clients use API billing; OAuth clients use that provider's subscription
backend. A model-specific or transport-specific incompatibility disables or
fails that model honestly. The selector never silently borrows another
credential or switches providers.

If reauthentication is required, Models links to the affected row in Providers;
the re-login control itself stays in Providers.

### 4.3 Discovery refresh

`更新可用清單` runs the existing credential-scoped discovery operation for the
selected provider's active credential, then refetches the catalog. This is a
contextual shortcut, not a second credential manager.

- API-key and ChatGPT OAuth channels can produce live visibility.
- Claude OAuth reports `seed_only` and keeps the candidate wording.
- A failure preserves the last successful cache and shows the refresh error plus
  the old timestamp; it never re-labels stale data as freshly verified.

### 4.4 Actual-call test

`實際測試目前選擇` accepts task, provider, model, and effort. It resolves the same
active credential authority used by runtime routing.

- API-key routes use a minimal paid provider call.
- ChatGPT OAuth card tasks use the ChatGPT/Codex Responses backend with one
  inline function schema; Claude OAuth card tasks use Claude Agent SDK
  `output_format={"type":"json_schema"}` with all tools disabled. Both consume
  subscription allowance rather than API-key billing.
- OAuth AI research continues through its provider-specific subscription
  driver. Card and research tests remain separate because their runtime shapes
  differ.
- `api_key_pool` remains unsupported until direct runtime execution is wired; the
  UI states that reason instead of borrowing a single key.

OAuth tests are deliberately bounded. Research uses a minimal prompt,
`max_turns=1`, no ArkScope registry/tool dispatch, and a short dedicated timeout.
Card canaries request one tiny structured object and never invoke market tools,
research stores, or report persistence. Claude subscription cards pass
`tools=[]`, `allowed_tools=[]`, `setting_sources=[]`, and an isolated config
directory. They allow two Agent-SDK turns only because the internal
`StructuredOutput` call is turn one and its terminal result is turn two;
external tools remain disabled. ChatGPT subscription cards expose only the one
output function.
Any unexpected tool event is a failed canary, not permission to continue a loop.
The UI states that OAuth tests consume subscription allowance rather than API-key
billing. If an auth driver cannot enforce these bounds, that path reports
`task_test_unsupported` and does not run a normal research session.

The tiny task-test deadline is not the production card deadline. Full card
synthesis and translation may use high/max reasoning over a larger evidence or
translation payload: subscription provider execution is bounded at 210 seconds,
while the web request waits 300 seconds so the backend can return its classified
result and finish bounded SDK subprocess cleanup.

The check validates authentication, model id, effort, and the selected auth path.
It does not claim report quality, market-data completeness, or successful future
calls. Results are ephemeral in v1 and include `tested_at`, latency, auth mode,
and a machine-readable failure code. Tests never persist a route or research
artifact.

### 4.5 Effort and thinking behavior

V1 stores only `provider`, `model`, and `effort` in `TaskRoute`. It does **not**
add a task-level thinking toggle or a new route-schema field.

Effort choices are model-specific registry facts, not a provider-wide menu.
`default` means ArkScope omits the wire override and therefore cannot promise a
fixed tier; `none` is an explicit no-reasoning value and must be sent as such.
For the current OpenAI catalog, GPT-5.6 exposes
`none|low|medium|high|xhigh|max`, while GPT-5.4/5.5/5.2 expose
`none|low|medium|high|xhigh`; `minimal` is not offered for these models.
Unknown/custom model ids show only `default` until their capability contract is
known. Route validation uses the selected model's set and never silently maps
one valid tier to another. An auth backend may still reject a model/effort pair;
the task-scoped actual-call test is the authority for that execution path.

The card shows effort as the editable control. Beneath it, a read-only line
describes the selected model's registry-derived `thinking_mode`:

- `none`: no Anthropic thinking behavior;
- `manual_budget` or `adaptive_opt_in`: follows the existing global Anthropic
  thinking setting;
- `adaptive_default_on`: provider default is on; the existing global off setting
  sends the explicit disabled shape;
- `adaptive_always_on`: always on and cannot be disabled by this route.

This line explains runtime behavior but never pretends thinking is independently
saved per task. A task-level thinking control requires a separate schema/API
design and is outside this slice.

## 5. Backend Contract

### 5.1 Effective view becomes task by provider

The effective catalog must no longer let the currently saved route provider hide
the alternative provider. The additive target shape is:

```json
{
  "effective": {
    "providers": {
      "openai": {
        "credential_id": "local:3",
        "auth_mode": "api_key",
        "label": "OpenAI primary"
      },
      "anthropic": {
        "credential_id": "local:1",
        "auth_mode": "claude_code_oauth",
        "label": "Claude subscription"
      }
    },
    "tasks": {
      "ai_research": {
        "current_provider": "openai",
        "providers": {
          "openai": {
            "executable": true,
            "reason_code": null,
            "models": [
              {
                "id": "gpt-5.6-luna",
                "label": "GPT-5.6 Luna",
                "status": "visible",
                "eligible": true,
                "reason_code": null,
                "thinking_mode": "none",
                "effort_options": ["none", "low", "medium", "high", "xhigh", "max"]
              }
            ],
            "cache_state": "ok",
            "discovered_at": "..."
          },
          "anthropic": {
            "executable": true,
            "reason_code": null,
            "models": [
              {
                "id": "claude-sonnet-5",
                "label": "Claude Sonnet 5",
                "status": "seed",
                "eligible": true,
                "reason_code": null,
                "thinking_mode": "adaptive_default_on"
              }
            ],
            "cache_state": "seed_only",
            "discovered_at": "..."
          }
        }
      }
    }
  }
}
```

The model-entry contract is:

```text
{
  id: string,
  label: string,
  status: "visible" | "seed" | "advanced" | "route",
  eligible: bool,
  reason_code: string | null,
  effort_options: string[],
  thinking_mode: "none" | "manual_budget" | "adaptive_opt_in" |
                 "adaptive_default_on" | "adaptive_always_on"
}
```

Eligibility is per model, not inferred only from the provider block. A model
that is visible/seeded/pinned but fails task capability requirements remains in
the list with `eligible=false`, is disabled in the selector, and carries a
reason such as `task_capability_missing`. This lets the UI explain why it cannot
be selected instead of silently dropping it. The provider-level `executable`
field represents an auth-mode-wide veto such as an unwired key pool or a
provider/auth mismatch. Provider-matching OAuth card execution is supported by
the subscription structured-output adapters. Secrets and raw provider responses
never enter this view.

During migration, the old task-level `verified`/`advanced` fields may remain as
an alias for the current provider so old frontends do not break. The new UI's
normal path reads only the provider-indexed shape; the implementation plan must
define the removal gate for the alias rather than leaving it indefinitely.

The reverse version-skew path is also explicit. If a new frontend receives an
old catalog without `effective.tasks[task].providers`, it enters compatibility
mode: the provider control remains visible; the current provider uses the legacy
`verified`/`advanced` partition; the alternate provider uses registry candidates
marked unverified; active-credential display is derived from the existing
`catalog.credentials`; and the new task-scoped test is disabled with
`請重啟／更新 sidecar` rather than silently calling the API-key-only endpoint.
This fallback must not restore the old checkbox or hide Anthropic under manual
override.

### 5.2 Task-scoped test endpoint

Add a task-aware endpoint rather than changing the meaning of the existing
API-key-only `/config/model-test` in place. The request includes:

```json
{
  "task": "ai_research",
  "provider": "anthropic",
  "model": "claude-sonnet-5",
  "effort": "low"
}
```

The backend resolves the provider's active credential itself. A caller cannot
supply a different credential id and bypass the active-credential contract. The
response reports `status`, `error_code`, `credential_id`, `auth_mode`,
`tested_at`, `latency_ms`, and any effort fallback. No secret is serialized or
logged.

## 6. Error Handling

Machine-readable reasons include at least:

- `missing_active_credential`;
- `reauth_required`;
- `task_auth_mode_unsupported`;
- `task_capability_missing`;
- `task_test_unsupported`;
- `model_not_visible`;
- `model_not_in_registry`;
- `discovery_unavailable`;
- `provider_call_failed`.

`model_not_visible` is valid only when `cache_state="ok"` proves that a
successful live discovery omitted the model. It must not block a seed candidate
under `seed_only` or a candidate under `never_discovered`, because those states
cannot establish non-visibility; the explicit test is allowed to provide the
first live evidence.

The UI maps these to specific next actions. It never collapses all failures to
`模型不可用`, never offers re-login for wiring failures, and never suggests
discovery can prove an OAuth task executable when the task/auth matrix says no.

## 7. Compatibility and Authority

This adopted design narrowly supersedes two statements in
`docs/design/CREDENTIAL_MANAGEMENT_PLAN.md` section 11:

1. `Settings -> Models = task routing ONLY; no credential checks there` becomes:
   Models owns routing and may display active-credential state, refresh that
   credential's availability cache, and run a task-scoped check; credential
   mutation remains Providers-only.
2. `model-test is API-key path only` remains true for the existing endpoint, but
   is no longer the Models button's complete contract. The new task-scoped test
   dispatches OAuth only where the actual task runtime supports OAuth.

The credential operations matrix, single-active-per-provider invariant, and
Providers ownership remain authoritative.

## 8. Non-goals

- No credential creation, login, re-login, activation, or deletion in Models.
- No per-task credential id binding.
- No automatic provider/model recommendation changes.
- No silent fallback to another provider, credential, model, or billing path.
- No provider-wide model mirror; the registry remains ArkScope-relevant.
- No broad Settings decomposition or visual-theme overhaul in this slice.
- No persistence of test history in v1.

## 9. Acceptance Criteria

1. An OpenAI-routed task still shows the Anthropic provider control without
   opening an advanced disclosure.
2. Selecting Anthropic immediately shows the active Anthropic credential and
   its honest `seed_only`, live-visible, missing, or incompatible state.
3. No checkbox controls whether a provider is discoverable.
4. There is one model selector, not a verified selector plus hidden duplicate.
5. `此登入可見`, `可供此任務使用`, and `實際呼叫通過` are independently testable
   states and never used as synonyms.
6. A provider switch cannot retain an incompatible model or effort silently.
7. The frontend cannot save a newly selected provider with no active credential;
   the backend remains warning-only for compatibility and custom routes.
8. OAuth card generation, translation, and task testing use the selected
   provider's subscription backend. A model-specific failure is reported
   without falling back to an API key, another provider, or another model.
9. A route-pinned unknown/old model remains visible with a warning and is never
   auto-replaced.
10. Providers remains the only surface with credential mutation controls.
11. Thinking behavior is shown from the registry but no task-level thinking
    field is written to the route store or API.
12. The effort selector follows the selected model: GPT-5.6 includes `max` and
    excludes `minimal`; GPT-5.4-class models exclude both `minimal` and `max`.
    `default` and explicit `none` are visibly distinct.

## 10. Verification Shape

The implementation plan must include:

- backend matrix tests for every task x provider x auth mode combination;
- a regression proving an OpenAI current route does not remove Anthropic from
  the effective view;
- discovery states `ok`, `seed_only`, `never_discovered`, stale-preserved after
  failure, and `reauth_required`;
- frontend interaction tests for provider switching, model/effort reset,
  missing credential, seed-only Anthropic, refresh, task-scoped testing, custom
  id, and route-pinned models;
- model-entry rendering tests proving ineligible entries remain visible,
  disabled, and paired with their reason code;
- an exact test proving the old checkbox and duplicate manual model selector are
  gone;
- zero-call tests for unsupported auth/task combinations;
- bounded OAuth canary tests proving research uses `max_turns=1`, Claude
  structured card checks use exactly two internal SDK turns with no external
  tools, timeout handling, subscription-billing copy, and zero normal research
  persistence;
- a seed-only/never-discovered test proving `model_not_visible` cannot veto an
  explicit canary;
- new-frontend/old-sidecar compatibility tests proving provider visibility and
  task-test disablement without reviving the old checkbox/manual selector;
- full frontend typecheck/build, focused backend tests, no-PG smoke, and virgin
  full A/B before merge;
- live verification with one OpenAI API-key route, one Anthropic API-key route,
  and one OAuth AI-research route. Premium model calls remain user-gated.

## 11. Sequence

1. Finish and live-verify the S3 credential-lifecycle hotfix so stale OAuth rows
   have a repair path.
2. Implement this focused Models UX slice.
3. Continue the broader P2.8 current-UI audit and canonical shell spec; do not
   use this focused slice as a substitute for that larger pass.

## 12. Review Log

- Live closeout (2026-07-12): the amended implementation passed the final
  user-run acceptance pair. ChatGPT OAuth `gpt-5.6-luna`, although visible in
  discovery, rendered a redacted `provider_call_failed` after 906 ms;
  `gpt-5.4-mini` rendered `ok` after 1,589 ms. That is the intended proof that
  discovery visibility and actual execution are separate facts. Supporting
  pre-merge verification was backend focused `187 passed`, frontend `284
  passed`, production build green, and no-PG smoke `24/24` with no PostgreSQL
  attempts. The unresolved third-party OAuth client-identity behavior is a
  transport follow-up; no hidden fallback was introduced.

- Live-gate amendment (2026-07-12): ChatGPT OAuth listed GPT-5.6 models but
  rejected `gpt-5.6-luna` before effort validation, while `gpt-5.4-mini`
  executed. Repeating Luna with different effort values therefore did not test
  effort support. The inspection also found two implementation defects: OpenAI
  effort choices were provider-wide (`minimal` everywhere, no `max`), and the
  OAuth driver silently mapped `xhigh|max` to `high` while omitting explicit
  `none`. The adopted contract above makes effort model-specific, sends explicit
  values unchanged, and keeps backend-specific acceptance behind the actual-call
  test. Early canary termination also exposed an unclosed `AsyncOpenAI` client;
  deterministic generator cleanup is part of the same pre-merge amendment.

- Implementation review (2026-07-12): GREEN with canonical single-process
  virgin A/B `30=30`, passed `3948→3995` (`+47`, exactly the collect delta),
  and flat skips/warnings/errors. Accepted the implementation's stronger
  advanced-entry visibility veto described in §4.1, including the seed/unknown
  and route-pin exceptions. Also accepted the semantically equivalent
  never-discovered copy and shared visible verification action. Legacy alias
  seed ordering remains cosmetic compatibility behavior; the source-string
  zero-persistence guard is accepted as an implementation note, not elevated
  into a broader architecture guarantee.
- Round 1 (2026-07-11): 2 must-fix + 4 should-fix verified and absorbed.
  V1 now has an effort control plus read-only registry-derived thinking behavior
  rather than an undefined thinking route field; model entries have an explicit
  status/eligibility/reason/thinking schema and ineligible entries remain visible
  but disabled. Missing-active-credential save blocking is frontend-only;
  OAuth research canaries are one-turn/no-tools/timed and identify subscription
  consumption; `model_not_visible` applies only after successful live discovery;
  and new-frontend/old-sidecar degradation is defined in both directions.
