# Model Routing Settings UX Design

> **Status: DRAFT FOR USER REVIEW, 2026-07-11.** This is a focused P2.8 design
> slice prompted by the first live inspection of the P2.7 picker. It preserves
> the existing Settings boundary: `Providers` owns credentials, login, and
> credential-scoped discovery; `Models` owns per-task provider/model/effort
> routing. No implementation work starts until this document is approved.

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
   `claude_code_oauth`. That channel is honestly `seed_only`: it can execute AI
   research, but cannot live-list provider models and cannot execute card tasks.
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
`never_discovered` is rendered as `尚未檢查此登入可見模型`, never as empty or
unavailable. A timestamped discovery result is an observation, not a permanent
entitlement promise.

## 4. Task Card Interaction

Each task card follows one fixed vertical order:

1. Task title, description, and current route-authority badge.
2. Provider segmented control.
3. Active credential summary and status.
4. Model selector.
5. Effort/thinking selector.
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

### 4.2 Missing or incompatible credentials

If no active credential exists, the card shows `尚未設定此 provider 的登入` and a
`前往 Providers` action. Model selection, actual testing, and saving that draft
route are disabled.

If the active auth mode cannot execute the task, the card names the reason. For
example, Claude OAuth may be valid for AI research while card synthesis remains
API-key-only. The selector does not silently borrow another credential or switch
providers.

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
- ChatGPT OAuth and Claude OAuth are testable only for AI research, through their
  respective subscription drivers.
- Card tasks with an OAuth-active provider fail closed before a network call and
  explain that an API-key credential is required.
- `api_key_pool` remains unsupported until direct runtime execution is wired; the
  UI states that reason instead of borrowing a single key.

The check validates authentication, model id, effort, and the selected auth path.
It does not claim report quality, market-data completeness, or successful future
calls. Results are ephemeral in v1 and include `tested_at`, latency, auth mode,
and a machine-readable failure code. Tests never persist a route or research
artifact.

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
            "models": [],
            "cache_state": "ok",
            "discovered_at": "..."
          },
          "anthropic": {
            "executable": true,
            "reason_code": null,
            "models": [],
            "cache_state": "seed_only",
            "discovered_at": "..."
          }
        }
      }
    }
  }
}
```

Each model entry carries one status classification (`visible`, `seed`,
`advanced`, or `route`) plus task eligibility. Secrets and raw broker/provider
responses never enter this view.

During migration, the old task-level `verified`/`advanced` fields may remain as
an alias for the current provider so old frontends do not break. New UI reads
only the provider-indexed shape; the implementation plan must define the removal
gate for the alias rather than leaving it indefinitely.

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
- `model_not_visible`;
- `model_not_in_registry`;
- `discovery_unavailable`;
- `provider_call_failed`.

The UI maps these to specific next actions. It never collapses all failures to
`模型不可用`, never offers re-login for wiring failures, and never suggests
discovery can prove an OAuth task executable when the task/auth matrix says no.

## 7. Compatibility and Authority

On adoption, this design narrowly supersedes two statements in
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
7. A task cannot save a newly selected provider with no active credential.
8. OAuth card testing makes zero provider calls and returns an explicit
   unsupported reason; OAuth research testing uses its subscription driver.
9. A route-pinned unknown/old model remains visible with a warning and is never
   auto-replaced.
10. Providers remains the only surface with credential mutation controls.

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
- an exact test proving the old checkbox and duplicate manual model selector are
  gone;
- zero-call tests for unsupported auth/task combinations;
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
