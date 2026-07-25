# Calibration Anthropic Refusal Micro-Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** IMPLEMENTED - INDEPENDENT REVIEW PENDING

**Goal:** Make the Investor Profile calibration Anthropic seam classify
HTTP-200 `stop_reason="refusal"` as the existing typed `model_refusal` failure
before text extraction or JSON parsing.

**Architecture:** Reuse `src.anthropic_refusal.is_refusal()` and
`AnthropicRefusalError` at the direct Anthropic response seam. The calibration
route catches that typed error before its generic responder handler, persists
`model_refusal` on the durable turn, and returns a bounded HTTP 502 response.
There is no fallback, automatic retry, prompt change, frontend change, or
schema change.

**Tech Stack:** Python 3.11, Anthropic SDK response objects, FastAPI,
SQLite-backed `CalibrationStore`, pytest.

---

## 1. Grounded Baseline

Behavior base is clean `master` at `efc358e8` on 2026-07-25.

- `src/investor_profile_calibration_agent.py:286-294` calls
  `client.messages.create(...)` and immediately passes the response to
  `_message_text_anthropic()`; it has no refusal branch.
- `src/anthropic_refusal.py` already owns the contract: branch on
  `stop_reason` only, tolerate absent `stop_details`, and raise
  `AnthropicRefusalError` without fallback.
- The three existing consumers are the Anthropic agent loop, card synthesis,
  and card translation. This micro-slice adds the fourth consumer without
  changing the shared helper.
- An empty refusal currently becomes an empty string, then
  `parse_calibration_model_json()` raises `CalibrationResultParseError`.
  `src/api/routes/investor_profile_calibration.py:238-251` therefore records
  `calibration_result_validation_failed` and returns HTTP 400.
- The mounted Investor Profile surface already renders the localized, fixed
  turn-error title from `settings.investor.workspace.errors.turn`. It does not
  render the backend message, so no frontend resource or component change is
  needed.
- Exact baseline collection:
  - full backend: `4711` nodes;
  - focused files
    `tests/test_investor_profile_calibration.py` and
    `tests/test_investor_profile_calibration_routes.py`: `46` nodes and
    `46 passed`.

Exact target is backend `+2/-0`: full collection `4713`, focused `48`, with
these two new IDs and no removals or renames:

1. `test_anthropic_calibration_raises_structured_refusal_before_text_extraction`
2. `test_calibration_refusal_records_model_refusal_instead_of_generic_failure`

## 2. Locked Scope

### Modify

- `src/investor_profile_calibration_agent.py`
- `src/api/routes/investor_profile_calibration.py`
- `tests/test_investor_profile_calibration.py`
- `tests/test_investor_profile_calibration_routes.py`
- this plan, its evidence packet, and `docs/design/PROJECT_PRIORITY_MAP.md`

### Keep byte-identical

- `src/anthropic_refusal.py`
- `src/card_synthesis.py`
- `src/agents/anthropic_agent/agent.py`
- `src/investor_profile_calibration.py`
- `src/investor_profile_calibration_policy.py`
- `src/investor_profile_calibration_schema.py`
- all frontend, i18n resource, CSS, extension, desktop, package, and lock files

### Behavior contract

- Detect refusal only with `is_refusal(response)`, which means exact
  `stop_reason == "refusal"`. Do not inspect content length, prose, category,
  or `stop_details` to decide.
- Raise `AnthropicRefusalError(model, stop_details)` before
  `_message_text_anthropic()` is called.
- Do not retry, change effort, change model, or fall back to another provider.
- Route refusal returns HTTP `502`, public code `model_refusal`, and fixed
  message `The model declined this calibration turn.`
- Durable turn state is `failed`, remains retryable through the existing turn
  mechanism, and records `error_code="model_refusal"`.
- Durable/public diagnostic is the fixed safe string
  `Model refused calibration request.` Raw response content, model output,
  `stop_details`, credentials, and exception prose never enter the response or
  database.
- Malformed non-refusal JSON remains
  `calibration_result_validation_failed` / HTTP 400. Generic provider failures
  remain `calibration_responder_failed` / HTTP 502.

## 3. Stop Conditions

Stop and amend this plan before implementation if any of the following is
required:

1. a frontend copy, component, resource, or CSS change;
2. a new refusal type or change to `src/anthropic_refusal.py`;
3. a retry, fallback, model-selection, or effort-policy change;
4. a prompt, topic catalog, proposal, journal, schema, or migration change;
5. raw `stop_details` or exception text must be persisted or displayed;
6. the baseline is not `4711` full / `46` focused before product edits;
7. either RED test fails for a reason other than the missing typed-refusal
   branch or missing route classification.

## 3.1 Independent Review Resolution

Independent review returned GREEN for both the register and this plan on
2026-07-25. It reproduced full `4711`, focused `46 collected / 46 passed`, the
three existing refusal seams, the shared stop-reason-only helper contract, the
two distinct RED locations, exact `+2/-0` arithmetic, and every protected
boundary.

One advisory is accepted with a timing constraint: the current Investor
Profile UI renders every turn failure with the same localized title, so a
future refusal-aware recovery explanation is genuine UX debt. It is not added
to the register before implementation because `model_refusal` is not yet a
calibration route outcome and the register admits only reproducible current
facts. Task 3 adds the entry after this slice makes the unused typed code real;
the owning trigger is the next Investor Profile-owned UI slice. This plan's
frontend stop condition remains unchanged.

## 4. Task 0: Review Clearance

**Files:**
- Modify: `docs/superpowers/plans/2026-07-25-calibration-anthropic-refusal.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [x] **Step 1: Receive independent plan review**

The reviewer must confirm the two RED sites are distinct:

1. provider response -> typed exception before text extraction;
2. typed exception -> durable/API `model_refusal` rather than generic or parse
   failure.

- [x] **Step 2: Record clearance**

Change plan status to `REVIEW GREEN - IMPLEMENTATION CLEARED`, add the review
resolution, update the newest priority-map entry, and commit docs only. Record:

```text
PLAN_REVIEW_CLEARANCE_COMMIT=d19d964218dcc84bdd8aa908e27b577c8f079fdd
```

Do not edit product code before this commit exists.

## 5. Task 1: Detect Refusal At The Anthropic Response Seam

**Files:**
- Modify: `tests/test_investor_profile_calibration.py`
- Modify: `src/investor_profile_calibration_agent.py`

- [x] **Step 1: Add the direct RED test**

Add imports:

```python
from types import SimpleNamespace
from unittest.mock import Mock

from src.anthropic_refusal import AnthropicRefusalError
```

Add this named node:

```python
def test_anthropic_calibration_raises_structured_refusal_before_text_extraction(
    monkeypatch,
):
    import src.auth_drivers.live_resolver as live_resolver

    response = SimpleNamespace(
        stop_reason="refusal",
        stop_details=None,
        content=[SimpleNamespace(text='{"assistant_message":"must not parse"}')],
    )
    create = Mock(return_value=response)
    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(
        live_resolver,
        "resolve_live_auth",
        lambda provider: SimpleNamespace(source="api_key", credential_id=None),
    )
    monkeypatch.setattr(live_resolver, "live_anthropic_client", lambda: client)

    with pytest.raises(AnthropicRefusalError) as exc:
        asyncio.run(
            calibration_agent._call_calibration_llm(
                provider="anthropic",
                model="claude-sonnet-5",
                instructions="Return JSON.",
                input_messages=[{"role": "user", "content": "Calibrate me."}],
            )
        )

    assert exc.value.model == "claude-sonnet-5"
    assert exc.value.stop_details == {}
    create.assert_called_once()
```

- [x] **Step 2: Prove the test is RED for the intended reason**

Run:

```bash
pytest -q \
  tests/test_investor_profile_calibration.py::test_anthropic_calibration_raises_structured_refusal_before_text_extraction
```

Expected before implementation: `FAILED` because no
`AnthropicRefusalError` is raised. A credential/config failure or JSON parser
failure is the wrong RED and triggers a stop.

- [x] **Step 3: Add the minimal response-seam branch**

At module imports:

```python
from src.anthropic_refusal import AnthropicRefusalError, is_refusal
```

In the Anthropic `_call()`, immediately after `messages.create(...)` and before
text extraction:

```python
if is_refusal(resp):
    raise AnthropicRefusalError(model, getattr(resp, "stop_details", None))
return _message_text_anthropic(resp)
```

Do not wrap this in a generic catch and do not add retry logic.

- [x] **Step 4: Run the direct and shared refusal tests**

```bash
pytest -q \
  tests/test_investor_profile_calibration.py::test_anthropic_calibration_raises_structured_refusal_before_text_extraction \
  tests/test_card_synthesis.py::test_card_synthesis_raises_structured_refusal \
  tests/test_card_synthesis.py::test_card_translation_raises_structured_refusal \
  tests/test_card_synthesis.py::test_refusal_never_triggers_effort_fallback \
  tests/test_events.py::TestAnthropicStream::test_refusal_stop_surfaces_error_not_done
```

Expected: all selected nodes pass.

- [x] **Step 5: Commit Task 1**

```bash
git add src/investor_profile_calibration_agent.py \
  tests/test_investor_profile_calibration.py
git commit -m "fix: detect calibration model refusals"
```

## 6. Task 2: Preserve Typed Refusal Through The Route

**Files:**
- Modify: `tests/test_investor_profile_calibration_routes.py`
- Modify: `src/api/routes/investor_profile_calibration.py`

- [x] **Step 1: Add the route RED test**

Import the existing type:

```python
from src.anthropic_refusal import AnthropicRefusalError
```

Add this named node alongside the existing responder-failure and malformed
result tests:

```python
def test_calibration_refusal_records_model_refusal_instead_of_generic_failure(
    stores,
    monkeypatch,
):
    cstore, _pstore = stores
    _allow_writes(monkeypatch)
    session = _start(cstore)
    calls = 0

    async def refusing_responder(**kwargs):
        nonlocal calls
        calls += 1
        raise AnthropicRefusalError(
            "private-model-name",
            {"category": "private-category", "explanation": "private-detail"},
        )

    monkeypatch.setattr(routes, "_default_responder", refusing_responder)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            routes.send_calibration_message(
                routes.CalibrationMessageBody(
                    session_id=session["id"],
                    turn_id="model-refusal",
                    content="Keep this answer for an explicit retry.",
                    provider="anthropic",
                ),
                store=cstore,
            )
        )

    failed = cstore.get_turn("model-refusal")
    state = routes.get_calibration_state(store=cstore)
    assert calls == 1
    assert exc.value.status_code == 502
    assert exc.value.detail == {
        "code": "model_refusal",
        "message": "The model declined this calibration turn.",
        "diagnostic": "Model refused calibration request.",
    }
    assert failed.status == "failed"
    assert failed.error_code == "model_refusal"
    assert failed.diagnostic == "Model refused calibration request."
    assert state["pending_turn"]["id"] == "model-refusal"
    assert state["pending_turn"]["attempt_count"] == 1
    exposed = json.dumps(
        {"turn": failed.to_dict(), "http_detail": exc.value.detail},
        ensure_ascii=False,
    )
    assert "private-model-name" not in exposed
    assert "private-category" not in exposed
    assert "private-detail" not in exposed
```

- [x] **Step 2: Prove the test is RED for the intended reason**

```bash
pytest -q \
  tests/test_investor_profile_calibration_routes.py::test_calibration_refusal_records_model_refusal_instead_of_generic_failure
```

Expected before route implementation: `FAILED` because the generic handler
returns and persists `calibration_responder_failed`. A setup, permission, or
store failure is the wrong RED.

- [x] **Step 3: Add the narrow typed catch**

Import `AnthropicRefusalError` from `src.anthropic_refusal`. Add a fixed
diagnostic helper beside the existing diagnostic helpers:

```python
def _model_refusal_diagnostic() -> str:
    return sanitize_research_detail(
        redact("Model refused calibration request.")
    )
```

Insert this catch after `CalibrationResultParseError` and before
`MissingCredentialError` / generic `Exception`:

```python
except AnthropicRefusalError as exc:
    failed = store.fail_turn(
        work.turn.id,
        error_code="model_refusal",
        diagnostic=_model_refusal_diagnostic(),
    )
    raise _bad(
        502,
        "model_refusal",
        "The model declined this calibration turn.",
        diagnostic=failed.diagnostic,
    ) from exc
```

The catch order is load-bearing. The typed error must not reach the generic
handler.

- [x] **Step 4: Run route regressions**

```bash
pytest -q \
  tests/test_investor_profile_calibration_routes.py::test_calibration_refusal_records_model_refusal_instead_of_generic_failure \
  tests/test_investor_profile_calibration_routes.py::test_send_message_wraps_responder_runtime_failure \
  tests/test_investor_profile_calibration_routes.py::test_turn_requires_client_turn_id_and_returns_retryable_state \
  tests/test_investor_profile_calibration_routes.py::test_calibration_failure_hides_provider_detail_outside_diagnostic_field
```

Expected: all pass. The three existing generic/parse/privacy contracts must not
change.

- [x] **Step 5: Commit Task 2**

```bash
git add src/api/routes/investor_profile_calibration.py \
  tests/test_investor_profile_calibration_routes.py
git commit -m "fix: preserve typed calibration refusals"
```

## 7. Task 3: Canonical Verification And Review Packet

**Files:**
- Create: `docs/superpowers/evidence/2026-07-25-calibration-anthropic-refusal.md`
- Modify: `docs/design/ENGINEERING_ISSUE_REGISTER.md`
- Modify: `docs/superpowers/plans/2026-07-25-calibration-anthropic-refusal.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [x] **Step 1: Prove the exact node ledger**

```bash
pytest --collect-only -q | tail -1
pytest --collect-only -q \
  tests/test_investor_profile_calibration.py \
  tests/test_investor_profile_calibration_routes.py | tail -1
```

Expected: full `4713`; focused `48`. Normalize base/head node IDs and require
exact `+2/-0` with only the two IDs in section 1.

- [x] **Step 2: Run the focused behavior suite**

```bash
pytest -q \
  tests/test_investor_profile_calibration.py \
  tests/test_investor_profile_calibration_routes.py
```

Expected: `48 passed`.

- [x] **Step 3: Run equal-environment virgin full A/B**

Create clean archives of `PLAN_REVIEW_CLEARANCE_COMMIT` and implementation
tip, mount the same repository `node_modules` into both, and give both the same
data/config presence. Run:

```bash
pytest -q
```

Required result:

- passed-node delta equals `+2`;
- failed/error/skip/warning node-ID sets are identical;
- no existing node is removed or renamed.

Absolute historical failure counts are environment observations, not expected
constants. Record both archive environments and normalized ID hashes.

- [x] **Step 4: Run boundary gates**

```bash
python -m src.smoke.pg_unreachable_e2e
git diff --check PLAN_REVIEW_CLEARANCE_COMMIT..HEAD
git diff --exit-code PLAN_REVIEW_CLEARANCE_COMMIT..HEAD -- \
  src/anthropic_refusal.py \
  src/card_synthesis.py \
  src/agents/anthropic_agent/agent.py \
  src/investor_profile_calibration.py \
  src/investor_profile_calibration_policy.py \
  src/investor_profile_calibration_schema.py \
  apps/arkscope-web \
  extensions \
  package.json package-lock.json
```

Expected: no-PG `ok:true` with `pg_attempts:[]`; every byte gate and diff check
passes. Inspect the two authorized product diffs and require only:

- one shared-helper import plus one refusal branch in the calibration agent;
- one typed import, one fixed diagnostic helper, and one catch in the route.

- [x] **Step 5: Write evidence and stop at review-ready**

Record RED output, GREEN output, exact node lists/hashes, full A/B, no-PG,
byte gates, and diff census in the evidence packet. Change plan status to
`IMPLEMENTED - INDEPENDENT REVIEW PENDING`, update the newest priority-map
entry, and add one evidenced register entry for the remaining UX debt:

- calibration now emits durable `model_refusal`;
- `InvestorProfilePanel.tsx` still maps every `turn` failure to the single
  `investor.workspace.errors.turn` title;
- owner/trigger is the next Investor Profile-owned UI slice;
- no frontend implementation is authorized by that entry.

Then commit docs only.

Do not merge. Independent implementation review must reproduce both RED seams,
the `+2/-0` ledger, privacy assertions, and the absence of fallback/retry.
