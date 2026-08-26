# Lifecycle Content Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the shared translation route accurately named, hash-reused, diagnosable, and actionable while preserving side-by-side original lifecycle evidence.

**Architecture:** Keep the stored task ID `card_translation` and the existing evidence-translation table. Add one provider-neutral failure classifier at the translation boundary, return only safe route identity and closed error metadata, and render that metadata in the existing Lifecycle evidence component. Card translation retains its switch UI; Lifecycle retains adjacent original and translated text.

**Tech Stack:** Python 3, FastAPI, SQLite, React 18, TypeScript, i18next, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-08-26-lifecycle-resolution-and-translation-continuation-design.md`

## Global Constraints

- Keep the internal task ID `card_translation`; do not migrate stored routing keys.
- Use the one existing provider/model/effort/runtime route for cards and lifecycle evidence.
- Never replace or hide the original lifecycle evidence excerpt.
- Reuse `(evidence_id, evidence_content_sha256, locale)` without a provider call.
- Do not automatically retranslate unchanged evidence after route/model changes.
- Do not silently fall back to another provider.
- Do not return credentials, prompts, provider response bodies, source excerpts, or raw exception messages.
- Product-rule copy is localized with i18n, not an LLM call.
- Provider calls, production DB access, merge, and push remain separate gates.

---

## File Map

- `src/model_routing.py`: stable task metadata returned by the routing API.
- `src/fixed_task_runtime_config.py`: fixed-task runtime display metadata.
- `src/card_synthesis.py`: existing bounded text translation and provider dispatch.
- `src/content_translation_failures.py`: new provider-neutral safe failure classifier.
- `src/security_lifecycle_translation.py`: evidence cache/conflict boundary and typed failure DTO.
- `src/api/routes/security_lifecycle.py`: route identity capture and safe HTTP detail.
- `apps/arkscope-web/src/api.ts`: typed safe translation error metadata.
- `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`: side-by-side evidence, retry, and Settings recovery action.
- `apps/arkscope-web/src/Universe.tsx`: passes existing shell navigation into Lifecycle.
- `apps/arkscope-web/src/i18n/resources/{en,zh-Hant}/{settings,explore}.ts`: user copy.
- Existing backend/frontend tests remain the authority; no new test-only product seams.

### Task 1: Rename the Shared User-Facing Translation Task

**Files:**
- Modify: `src/model_routing.py:80-88`
- Modify: `src/fixed_task_runtime_config.py:33-45`
- Modify: `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- Modify: `apps/arkscope-web/src/settings/settingsRegistry.ts`
- Test: `tests/test_model_routing.py`
- Test: `tests/test_fixed_task_runtime_config.py`
- Test: `apps/arkscope-web/src/ModelRoutingSection.test.ts`
- Test: `apps/arkscope-web/src/FixedTaskRuntimeSection.test.tsx`
- Test: `apps/arkscope-web/src/SettingsModelRouting.test.ts`
- Test: `apps/arkscope-web/src/SettingsWorkspace.test.tsx`
- Test: `apps/arkscope-web/src/settings/settingsCopy.test.ts`

**Interfaces:**
- Consumes: stored task key `card_translation` and current Settings routing payload.
- Produces: the same key with English label `Content translation` and Traditional Chinese label `內容翻譯`.

- [ ] **Step 1: Write failing backend label tests**

Add exact assertions without changing the stored ID:

```python
translation = next(task for task in result["tasks"] if task["id"] == "card_translation")
assert translation["label"] == "Content translation"

runtime = resolve_fixed_task_runtime("card_translation", store=store)
assert runtime.task == "card_translation"
assert FIXED_TASK_RUNTIME_TASKS["card_translation"].label == "內容翻譯"
```

- [ ] **Step 2: Write failing frontend Settings-copy tests**

```tsx
expect(host!.textContent).toContain("內容翻譯 Model");
expect(host!.textContent).toContain("內容翻譯 - 模型執行上限（秒）");
expect(host!.textContent).not.toContain("卡片翻譯 Model");
```

Keep `卡片翻譯` and `Card translation` only as Settings search aliases so an old search still finds the renamed control.

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```bash
pytest tests/test_model_routing.py tests/test_fixed_task_runtime_config.py -q
cd apps/arkscope-web && npm test -- ModelRoutingSection.test.ts FixedTaskRuntimeSection.test.tsx SettingsModelRouting.test.ts SettingsWorkspace.test.tsx settings/settingsCopy.test.ts
```

Expected: label assertions fail because current copy says Card/Card translation.

- [ ] **Step 4: Change display metadata and localized copy only**

Use this exact backend metadata shape:

```python
TaskInfo(
    id="card_translation",
    label="Content translation",
    description=(
        "Translate cards and source excerpts while preserving structure, "
        "citations, identifiers, and numbers."
    ),
    default_provider="anthropic",
    recommended_model="claude-sonnet-4-6",
)
```

Change the Traditional Chinese runtime label to `內容翻譯`. Update English and Traditional Chinese Settings resources and search keywords; do not rename API fields, test IDs, environment keys, or DB values.

- [ ] **Step 5: Re-run focused tests and visible-literal scan**

Run:

```bash
pytest tests/test_model_routing.py tests/test_fixed_task_runtime_config.py -q
cd apps/arkscope-web && npm test -- ModelRoutingSection.test.ts FixedTaskRuntimeSection.test.tsx SettingsModelRouting.test.ts SettingsWorkspace.test.tsx settings/settingsCopy.test.ts
cd apps/arkscope-web && npm run check:i18n-literals
```

Expected: all pass; old wording remains only in explicit search-alias fixtures.

- [ ] **Step 6: Commit**

```bash
git add src/model_routing.py src/fixed_task_runtime_config.py apps/arkscope-web/src/i18n/resources/en/settings.ts apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts apps/arkscope-web/src/settings/settingsRegistry.ts apps/arkscope-web/src/ModelRoutingSection.test.ts apps/arkscope-web/src/FixedTaskRuntimeSection.test.tsx apps/arkscope-web/src/SettingsModelRouting.test.ts apps/arkscope-web/src/SettingsWorkspace.test.tsx apps/arkscope-web/src/settings/settingsCopy.test.ts tests/test_model_routing.py tests/test_fixed_task_runtime_config.py
git commit -m "refactor(translation): name the shared content route"
```

### Task 2: Add a Closed Safe Translation Failure Boundary

**Files:**
- Create: `src/content_translation_failures.py`
- Modify: `src/card_synthesis.py:618-715`
- Modify: `src/security_lifecycle_translation.py`
- Modify: `src/api/routes/security_lifecycle.py:235-255,369-405`
- Test: `tests/test_security_lifecycle_translation.py`
- Test: `tests/test_security_lifecycle_routes.py`
- Create: `tests/test_content_translation_failures.py`

**Interfaces:**
- Consumes: exceptions from API-key SDK calls and `SubscriptionStructuredOutputError(code, message)`.
- Produces:

```python
TRANSLATION_FAILURE_CODES: frozenset[str]

@dataclass(frozen=True)
class ContentTranslationFailure:
    code: str
    retryable: bool

def classify_content_translation_failure(exc: Exception) -> ContentTranslationFailure: ...

def translation_harness(provider: str) -> str: ...
```

`EvidenceTranslationFailure` becomes a safe structured exception:

```python
class EvidenceTranslationFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        provider: str | None,
        model: str | None,
        harness: str | None,
    ) -> None: ...

    def detail(self) -> dict[str, object]: ...
```

Its constructor validates `code` against `TRANSLATION_FAILURE_CODES`, bounds
the three route strings to the same 64/160/160 limits as stored provenance,
and never accepts or stores an exception message.

`EvidenceTranslationFailure.detail()` produces:

```python
{
    "code": "translation_auth_rejected",
    "provider": "anthropic",
    "model": "claude-sonnet-5",
    "harness": "claude_subscription_structured_output",
    "retryable": False,
}
```

Route identity values may be `None` only for `translation_route_unavailable`, where no route could be resolved.

- [ ] **Step 1: Write classifier RED tests for every closed code**

Use fake exceptions with no raw secret-bearing message assertions:

```python
class _StatusError(RuntimeError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__("secret-value")


class _CodeError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__("secret-value")


class _StatusCodeError(_StatusError):
    def __init__(self, status_code: int, code: str):
        self.code = code
        super().__init__(status_code)


@pytest.mark.parametrize(
    ("exc", "code", "retryable"),
    [
        (MissingCredentialError("secret-value"), "translation_credential_missing", False),
        (SubscriptionStructuredOutputError("reauth_required", "secret-value"), "translation_auth_rejected", False),
        (_StatusError(404), "translation_model_unavailable", False),
        (_StatusError(429), "translation_rate_limited", True),
        (_CodeError("insufficient_quota"), "translation_quota_exhausted", False),
        (_StatusCodeError(429, "insufficient_quota"), "translation_quota_exhausted", False),
        (TimeoutError("secret-value"), "translation_timeout", True),
        (TextTranslationOutputInvalid("bad"), "translation_output_invalid", False),
        (RuntimeError("secret-value"), "translation_provider_error", True),
    ],
)
def test_translation_failures_are_closed_and_safe(exc, code, retryable):
    got = classify_content_translation_failure(exc)
    assert (got.code, got.retryable) == (code, retryable)
    assert "secret-value" not in repr(got)
```

Also assert unsupported/invalid route resolution maps to `translation_route_unavailable` at the route boundary rather than the generic provider code.

- [ ] **Step 2: Run classifier tests and verify RED**

Run:

```bash
pytest tests/test_content_translation_failures.py -q
```

Expected: import failure because the classifier module does not exist.

- [ ] **Step 3: Implement the classifier without response-body inspection**

Implement these precedence rules:

```python
if isinstance(exc, (ModelExecutionTimeout, TimeoutError)):
    return ContentTranslationFailure("translation_timeout", True)
if isinstance(exc, TextTranslationOutputInvalid):
    return ContentTranslationFailure("translation_output_invalid", False)
if isinstance(exc, MissingCredentialError):
    return ContentTranslationFailure("translation_credential_missing", False)
if isinstance(exc, SubscriptionStructuredOutputError):
    if exc.code == "reauth_required":
        return ContentTranslationFailure("translation_auth_rejected", False)
    if exc.code in {"insufficient_quota", "usage_limit_reached"}:
        return ContentTranslationFailure("translation_quota_exhausted", False)
status = getattr(exc, "status_code", None)
if status in {401, 403}:
    return ContentTranslationFailure("translation_auth_rejected", False)
if status == 404:
    return ContentTranslationFailure("translation_model_unavailable", False)
if getattr(exc, "code", None) in {"insufficient_quota", "usage_limit_reached"}:
    return ContentTranslationFailure("translation_quota_exhausted", False)
if status == 429:
    return ContentTranslationFailure("translation_rate_limited", True)
return ContentTranslationFailure("translation_provider_error", True)
```

Do not parse `str(exc)`, response JSON, headers, or provider message text.

- [ ] **Step 4: Write route and cache RED tests**

Add tests that prove:

```python
assert response.status_code == 502
assert response.json() == {
    "detail": {
        "code": "translation_auth_rejected",
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "harness": "claude_subscription_structured_output",
        "retryable": False,
    }
}
assert "secret-value" not in response.text
```

For an existing cached row, monkeypatch the translator to raise if called and assert the route returns `cached=True` without invoking it.

- [ ] **Step 5: Expose route identity and preserve typed failures**

Rename the private `_translation_harness` helper to public `translation_harness` and keep its current values. In `_translate_evidence_text`, resolve `task_route("card_translation")` before the call, pass its provider/model explicitly to `translate_text`, classify provider exceptions, and raise `EvidenceTranslationFailure` with route identity.

Add a no-fallback owner: make the configured provider raise a planted error,
install a spy for the other provider, and assert the response attributes the
configured route while the alternate-provider spy has zero calls.

In `translate_evidence`, preserve an incoming `EvidenceTranslationFailure`:

```python
except EvidenceTranslationFailure:
    raise
except (ModelExecutionTimeout, TimeoutError):
    raise EvidenceTranslationFailure(
        "translation_timeout",
        retryable=True,
        provider=None,
        model=None,
        harness=None,
    ) from None
```

In the FastAPI route use `exc.detail()`; never add `str(exc)`.

- [ ] **Step 6: Re-run backend translation tests**

Run:

```bash
pytest tests/test_content_translation_failures.py tests/test_security_lifecycle_translation.py tests/test_security_lifecycle_routes.py -q
```

Expected: all pass, cache test reports zero translator calls, and no failure payload contains the planted secret.

- [ ] **Step 7: Commit**

```bash
git add src/content_translation_failures.py src/card_synthesis.py src/security_lifecycle_translation.py src/api/routes/security_lifecycle.py tests/test_content_translation_failures.py tests/test_security_lifecycle_translation.py tests/test_security_lifecycle_routes.py
git commit -m "fix(translation): expose safe actionable failures"
```

### Task 3: Render Actionable Lifecycle Translation Failures

**Files:**
- Modify: `apps/arkscope-web/src/api.ts:890-935,2610-2635,2941-2951`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx:660-740,797-850,1040-1100`
- Modify: `apps/arkscope-web/src/Universe.tsx:70-95`
- Modify: `apps/arkscope-web/src/i18n/resources/en/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts`
- Test: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`
- Test: `apps/arkscope-web/src/Universe.test.tsx`
- Test: `apps/arkscope-web/src/apiError.test.ts`

**Interfaces:**
- Consumes: FastAPI detail fields `code`, `provider`, `model`, `harness`, and `retryable`.
- Produces:

```ts
export interface TranslationFailureMetadata {
  provider: string | null;
  model: string | null;
  harness: string | null;
  retryable: boolean;
}

export type TranslationFailureCode =
  | "translation_route_unavailable"
  | "translation_credential_missing"
  | "translation_auth_rejected"
  | "translation_rate_limited"
  | "translation_quota_exhausted"
  | "translation_model_unavailable"
  | "translation_timeout"
  | "translation_output_invalid"
  | "translation_provider_error"
  | "evidence_changed";

type TranslationErrorState = TranslationFailureMetadata & {
  code: TranslationFailureCode | "translation_unknown";
};

const TRANSLATION_FAILURE_CODES: readonly TranslationFailureCode[] = [
  "translation_route_unavailable",
  "translation_credential_missing",
  "translation_auth_rejected",
  "translation_rate_limited",
  "translation_quota_exhausted",
  "translation_model_unavailable",
  "translation_timeout",
  "translation_output_invalid",
  "translation_provider_error",
  "evidence_changed",
];

function isTranslationFailureCode(value: string | null): value is TranslationFailureCode {
  return value !== null
    && TRANSLATION_FAILURE_CODES.includes(value as TranslationFailureCode);
}
```

`LifecycleView` gains optional `onNavigate?: (target: NavigationTarget) => void`; `Universe` passes its existing `onNavigateTarget` callback.

- [ ] **Step 1: Write API error-metadata RED tests**

Feed `parseResponseError` a fixture response and assert only the reviewed fields survive:

```ts
expect(error.code).toBe("translation_auth_rejected");
expect(error.metadata).toEqual({
  provider: "anthropic",
  model: "claude-sonnet-5",
  harness: "claude_subscription_structured_output",
  retryable: false,
});
expect(JSON.stringify(error)).not.toContain("secret-value");
```

Add `metadata` as an optional final `ApiError` constructor argument so existing five-argument test fixtures remain source-compatible.

- [ ] **Step 2: Write Lifecycle component RED tests**

Cover all behavior classes:

```tsx
expect(host!.textContent).toContain("Anthropic · claude-sonnet-5");
expect(host!.textContent).toContain("重新登入或調整內容翻譯設定");
expect(host!.querySelector("[data-action='open-content-translation-settings']")).not.toBeNull();
expect(host!.textContent).toContain("重試翻譯"); // retryable failure
expect(host!.textContent).toContain(originalExcerpt);
expect(host!.textContent).toContain(translatedExcerpt);
```

Assert the Settings action emits exactly:

```ts
{ kind: "settings_section", section: "models" }
```

Table-drive all ten `TranslationFailureCode` values through the presentation
helper. Assert each receives reviewed English and Traditional Chinese copy,
the retry command appears only for retryable/output-invalid failures, and the
Settings command appears only for route/auth/credential/quota/model failures.

- [ ] **Step 3: Run frontend focused tests and verify RED**

Run:

```bash
cd apps/arkscope-web && npm test -- apiError.test.ts lifecycle/LifecycleView.test.tsx Universe.test.tsx
```

Expected: metadata is discarded, all failures use generic copy, and Lifecycle has no Settings navigation prop.

- [ ] **Step 4: Parse only safe error metadata**

Extend `ParsedResponseError` and `ApiError` with a nullable `metadata` object. Admit only exact string fields with bounded lengths and a boolean `retryable`; ignore all other server fields:

```ts
function boundedNullableString(value: unknown, maxLength: number): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength || normalized.includes("\0")) {
    return null;
  }
  return normalized;
}

const metadata = {
  provider: boundedNullableString(value.provider, 64),
  model: boundedNullableString(value.model, 160),
  harness: boundedNullableString(value.harness, 160),
  retryable: value.retryable === true,
};
```

Do not retain the raw detail object.

Pass `parsed.metadata` through both `getJSON` and `sendJSON`; leaving either
constructor call unchanged is a test failure.

- [ ] **Step 5: Implement closed bilingual error presentation**

Replace `Record<string, string>` with `Record<string, TranslationErrorState>`.
Define `TranslationFailurePresentation` as
`{ message: string; action: "retry" | "settings" | null }`, use
`Record<TranslationFailureCode, TranslationFailurePresentation>` for known
copy, and keep an explicit unknown fallback. Render route identity only when
non-null.

Normalize an unrecognized `ApiError.code` to local-only
`translation_unknown`; never cast an arbitrary server string into the closed
map.

- Retryable (`timeout`, `rate_limited`, `provider_error`) keeps a `重試翻譯`/`Retry translation` command.
- Route, credential, auth, quota, and model failures show the Models Settings action.
- Output-invalid shows retry plus a truthful invalid-output message.
- `evidence_changed` asks the user to refresh the case.

Continue rendering the original excerpt and any successful translation together.

- [ ] **Step 6: Wire exact Settings navigation through Universe**

Pass the existing callback without introducing location manipulation:

```tsx
<LifecycleView
  initialCaseId={caseId}
  onNavigate={onNavigateTarget}
/>
```

The recovery button calls:

```tsx
onNavigate?.({ kind: "settings_section", section: "models" });
```

- [ ] **Step 7: Re-run frontend tests, typecheck, and i18n scan**

Run:

```bash
cd apps/arkscope-web && npm test -- apiError.test.ts lifecycle/LifecycleView.test.tsx Universe.test.tsx
cd apps/arkscope-web && npm run typecheck
cd apps/arkscope-web && npm run check:i18n-literals
```

Expected: all pass with no raw visible literal or TypeScript widening of the closed error codes.

- [ ] **Step 8: Commit**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/lifecycle/LifecycleView.tsx apps/arkscope-web/src/Universe.tsx apps/arkscope-web/src/i18n/resources/en/explore.ts apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx apps/arkscope-web/src/Universe.test.tsx apps/arkscope-web/src/apiError.test.ts
git commit -m "feat(lifecycle): explain evidence translation failures"
```

### Task 4: Translation Admission and Browser Evidence

**Files:**
- Modify only if a gate exposes a defect in files owned by Tasks 1-3.
- Create: `docs/superpowers/evidence/2026-08-26-lifecycle-content-translation/README.md`
- Create: `docs/superpowers/evidence/2026-08-26-lifecycle-content-translation/SHA256SUMS`

**Interfaces:**
- Consumes: completed Tasks 1-3.
- Produces: offline admission evidence; no live provider result is required for merge readiness.

- [ ] **Step 1: Run focused backend tests twice**

```bash
pytest tests/test_content_translation_failures.py tests/test_security_lifecycle_translation.py tests/test_security_lifecycle_routes.py tests/test_model_routing.py tests/test_fixed_task_runtime_config.py -q
pytest tests/test_content_translation_failures.py tests/test_security_lifecycle_translation.py tests/test_security_lifecycle_routes.py tests/test_model_routing.py tests/test_fixed_task_runtime_config.py -q
```

Expected: identical pass counts and zero network calls.

- [ ] **Step 2: Run full backend and frontend gates**

```bash
pytest -q
cd apps/arkscope-web && npm test
cd apps/arkscope-web && npm run typecheck
cd apps/arkscope-web && npm run check:i18n-literals
cd apps/arkscope-web && npm run build
```

Expected: all pass. Record exact counts rather than copying earlier baselines.

- [ ] **Step 3: Run an offline bilingual browser matrix**

Use fixture API responses for: successful adjacent translation, cached translation, retryable timeout, auth rejection, quota exhaustion, invalid output, and evidence-changed conflict. Capture English and Traditional Chinese at desktop and mobile widths.

Assert in the browser harness:

```js
if (externalRequests.length !== 0) throw new Error("external request");
if (!pageText.includes(originalExcerpt)) throw new Error("original hidden");
if (scenario === "success" && !pageText.includes(translatedExcerpt)) {
  throw new Error("translation missing");
}
if (consoleErrors.length || pageErrors.length) throw new Error("browser error");
```

- [ ] **Step 4: Write the evidence manifest**

Record git head, commands, exact counts, zero-provider-call authority, screenshot dimensions, and known limitation that no live translation provider was called. Hash every payload and then hash `SHA256SUMS` separately.

- [ ] **Step 5: Commit evidence**

```bash
git add docs/superpowers/evidence/2026-08-26-lifecycle-content-translation
git commit -m "test(lifecycle): seal content translation admission"
```

Stop before any live translation canary, merge, or push. Those remain explicit user decisions.
