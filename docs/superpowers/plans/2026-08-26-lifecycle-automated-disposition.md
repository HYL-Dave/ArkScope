# Lifecycle Automated Disposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically separate lifecycle cases into attention, monitoring, and history from grounded SEC/IBKR/professional-source evidence, while keeping only genuine exceptions for people.

**Architecture:** Add one pure projection over the existing assessment/run/readiness/transition authorities rather than storing another workflow state. Refine acquisition so announced-but-unconfirmed events remain retryable monitoring, enrich IBKR evidence with quote quality without treating price as listing authority, expose the projection through the read API, and make the Lifecycle UI default to the attention bucket. All behavior changes bump the automation policy version and are admitted offline before any scheduler/provider cutover.

**Tech Stack:** Python 3, SQLite, FastAPI, ib_insync, React 18, TypeScript, i18next, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-08-26-lifecycle-resolution-and-translation-continuation-design.md`

## Global Constraints

- SEC is the official identity/effective-date authority; IBKR is market-infrastructure corroboration; publisher evidence is context and conflict detection.
- A quote value alone never proves or disproves exchange listing.
- Delayed/frozen/stale market data never satisfies a fresh-market gate.
- A quote is fresh only when IBKR marks it live, it contains a finite positive
  last price, and its provider timestamp is no more than 15 minutes old and no
  more than 5 minutes in the future at retrieval time.
- Missing completion evidence yields dated monitoring, not a timeless negative assessment.
- Source families, not article/provider counts, determine independence.
- Models and translations are not evidence families.
- Automatic ticker mutation retains the existing reversible transition preview, authority, scheduler, activity, acknowledgement, and reverse guards.
- Do not add a second mutable case workflow column or startup DDL.
- Policy behavior changes require a new exact automation policy version.
- The version bump must not reach the running App before separately authorized live provider execution.
- Production DB access, provider calls, live cutover, merge, and push remain separate gates.
- Execute the sibling Content translation plan first. Both plans are independently
  testable, but this plan deliberately builds on its `LifecycleView` and i18n edits.

---

## File Map

- `src/security_lifecycle_disposition.py`: new pure disposition and next-check projection.
- `src/security_lifecycle_decision_policy.py`: completed-event decisions only; pending M&A does not manufacture a review task.
- `src/security_lifecycle_automation_worker.py`: shares the next-check calculation and policy version.
- `src/service/security_lifecycle_automation_scheduler.py`: typed pending-event blockers, bounded retry/backoff, and source diagnostics.
- `src/security_lifecycle_ibkr_evidence.py`: contract identity plus bounded quote-quality snapshot.
- `src/tools/security_lifecycle_tools.py`: composes and filters derived disposition fields.
- `src/api/routes/security_lifecycle.py`: admits the new read-only filter.
- `apps/arkscope-web/src/api.ts`: closed disposition/queue/source-status types.
- `apps/arkscope-web/src/lifecycle/lifecyclePresentation.ts`: exhaustive bilingual disposition and rule copy.
- `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`: attention/monitoring/history/all segmented view.
- `apps/arkscope-web/src/i18n/resources/{en,zh-Hant}/explore.ts`: copy authority.
- Existing profile schema remains unchanged unless an exact RED proves the projection cannot be represented; that condition is a hard stop, not permission to migrate.

### Task 1: Build the Pure Disposition Projection

**Files:**
- Create: `src/security_lifecycle_disposition.py`
- Create: `tests/test_security_lifecycle_disposition.py`
- Modify: `src/security_lifecycle_automation_worker.py:25-45,210-240`
- Test: `tests/test_security_lifecycle_automation_worker.py`

**Interfaces:**
- Consumes: one composed case mapping with `source_presence`, `observation`, `current_assessment`, `current_acknowledgement`, `assessment_history`, `automation_runs`, and `ticker_transition`.
- Produces:

```python
LIFECYCLE_DISPOSITIONS = frozenset({
    "confirmed_monitoring",
    "confirmed_effective",
    "not_confirmed_yet",
    "exception_required",
})
LIFECYCLE_QUEUE_BUCKETS = frozenset({"attention", "monitoring", "history"})
SOURCE_FAMILY_STATES = frozenset({
    "confirmed", "present", "missing", "unavailable", "conflict"
})

@dataclass(frozen=True)
class LifecycleDispositionProjection:
    disposition: str
    queue_bucket: str
    reason_code: str
    last_checked_at: str | None
    next_check_at: str | None
    source_family_status: Mapping[str, str]

def next_lifecycle_recheck_at(
    run: Mapping[str, object] | None,
    assessment: Mapping[str, object] | None,
    transition: Mapping[str, object] | None = None,
) -> str | None: ...

def project_lifecycle_disposition(
    case: Mapping[str, object],
) -> LifecycleDispositionProjection: ...
```

Closed `reason_code` values are:

```python
LIFECYCLE_DISPOSITION_REASONS = frozenset({
    "awaiting_initial_automation",
    "automation_running",
    "waiting_effective_date",
    "waiting_market_confirmation",
    "waiting_transition_revalidation",
    "retryable_source_unavailable",
    "event_completion_not_confirmed",
    "not_confirmed_as_of",
    "source_missing",
    "source_conflict",
    "ambiguous_event",
    "nonretryable_provider_failure",
    "automation_failure",
    "resolved_no_change",
    "resolved_assessment",
    "transition_applied",
    "transition_reversed",
    "transition_cancelled",
    "transition_needs_review",
    "reviewed_inconclusive",
})
```

- [ ] **Step 1: Write table-driven RED tests for every disposition**

Include at least these exact fixtures:

```python
@pytest.mark.parametrize(
    ("fixture", "disposition", "bucket", "reason"),
    [
        (awaiting_case(), "not_confirmed_yet", "monitoring", "awaiting_initial_automation"),
        (running_case(), "not_confirmed_yet", "monitoring", "automation_running"),
        (waiting_date_case(), "confirmed_monitoring", "monitoring", "waiting_effective_date"),
        (waiting_market_case(), "confirmed_monitoring", "monitoring", "waiting_market_confirmation"),
        (retryable_blocked_case(), "not_confirmed_yet", "monitoring", "retryable_source_unavailable"),
        (pending_event_case(), "not_confirmed_yet", "monitoring", "event_completion_not_confirmed"),
        (source_conflict_case(), "exception_required", "attention", "source_conflict"),
        (failed_case(), "exception_required", "attention", "automation_failure"),
        (resolved_no_change_case(), "confirmed_effective", "history", "resolved_no_change"),
        (approved_transition_case(), "confirmed_monitoring", "monitoring", "waiting_effective_date"),
        (applied_transition_case(), "confirmed_effective", "history", "transition_applied"),
        (review_transition_case(), "exception_required", "attention", "transition_needs_review"),
        (stale_case(), "not_confirmed_yet", "monitoring", "awaiting_initial_automation"),
    ],
)
def test_disposition_projection_is_exhaustive(fixture, disposition, bucket, reason):
    got = project_lifecycle_disposition(fixture)
    assert (got.disposition, got.queue_bucket, got.reason_code) == (
        disposition, bucket, reason
    )
```

Assert `source_missing` always becomes attention even if an old accepted assessment exists, because the current source/body relationship cannot be validated.

- [ ] **Step 2: Write next-check RED tests**

```python
def test_market_recheck_is_daily_for_first_seven_days_then_weekly():
    assert next_lifecycle_recheck_at(
        run(updated_at="2026-08-26T00:00:00Z"),
        assessment(effective_date="2026-08-24"),
    ) == "2026-08-27T00:00:00Z"
    assert next_lifecycle_recheck_at(
        run(updated_at="2026-09-10T00:00:00Z"),
        assessment(effective_date="2026-08-24"),
    ) == "2026-09-17T00:00:00Z"

def test_effective_date_is_the_first_due_time():
    assert next_lifecycle_recheck_at(
        run(action_readiness="waiting_effective_date"),
        assessment(effective_date="2026-09-05"),
    ) == "2026-09-05T00:00:00Z"
```

`waiting_transition_revalidation` stays daily. A blocked run uses its persisted `retry_at`. An unprocessed case exposes the observation `last_observed_at` as already due rather than inventing a future scheduler promise.
An approved transition uses its explicit `execute_on` date; the projection does
not claim the automation worker itself executes ticker transitions.

- [ ] **Step 3: Run the new test module and verify RED**

Run:

```bash
pytest tests/test_security_lifecycle_disposition.py -q
```

Expected: import failure because the projection module does not exist.

- [ ] **Step 4: Implement strict input normalization and projection precedence**

Use this precedence, returning once:

```python
if source_presence != "present": source_missing_attention()
elif current_transition_status in {"applied", "reversed", "cancelled"}: history()
elif current_transition_status == "needs_review": transition_review_attention()
elif current_transition_status == "approved": scheduled_transition_monitoring()
elif current_nonstale_assessment and readiness in WAITING_READINESS: confirmed_monitoring()
elif current_nonstale_assessment: confirmed_effective_history()
elif current_acknowledgement: reviewed_inconclusive_history()
elif latest_run_status in {"queued", "running"}: not_confirmed_monitoring()
elif latest_run_status == "blocked" and final_not_confirmed_context: not_confirmed_history()
elif latest_run_status == "blocked" and pending_event_context: pending_event_monitoring()
elif latest_run_status == "blocked" and all_blockers_retryable: not_confirmed_monitoring()
elif latest_run_status == "blocked": exception_attention()
elif latest_run_status == "failed": exception_attention()
elif latest_automation_draft_requires_review: exception_attention()
else: awaiting_initial_automation_monitoring()
```

Parse blocker `context_json` only when it is a mapping after JSON decode. Invalid internal shapes raise `ValueError`; they never silently become a disposition.

Derive `source_family_status` for the exact schema families `regulator`,
`market_infrastructure`, `publisher`, `general_web`, and `manual` from the
latest automation run, current case evidence, and current accepted assessment:

```python
if family_has_conflicting_current_facts_or_blocker: state = "conflict"
elif family_has_typed_unavailable_blocker: state = "unavailable"
elif family_has_evidence_cited_by_current_assessment: state = "confirmed"
elif family_has_evidence_on_latest_run: state = "present"
elif family == "manual" and family_has_current_case_evidence: state = "present"
else: state = "missing"
```

Map SEC blockers only to `regulator`, IBKR blockers only to
`market_infrastructure`, publisher/news blockers only to `publisher`, and
hosted-search blockers only to `general_web`. Manual input has no provider
availability blocker. Unknown blocker codes do not guess a family. Evidence
from older automation runs cannot turn a missing latest-run family into
`present`; a current assessment citation may still make that family
`confirmed` because its hash binding is current.

- [ ] **Step 5: Make the worker use the shared next-check function**

Replace `_due_recheck` date arithmetic with
`next_lifecycle_recheck_at(run, assessment)`. Keep the worker's due comparison
and `reserve_readiness_recheck` behavior unchanged. The read projection alone
passes `ticker_transition` as the third argument so it can show the separate
transition scheduler's `execute_on` date.

- [ ] **Step 6: Run projection and worker tests**

Run:

```bash
pytest tests/test_security_lifecycle_disposition.py tests/test_security_lifecycle_automation_worker.py -q
```

Expected: all pass and existing due-date/app-downtime catch-up owners remain GREEN.

- [ ] **Step 7: Commit**

```bash
git add src/security_lifecycle_disposition.py src/security_lifecycle_automation_worker.py tests/test_security_lifecycle_disposition.py tests/test_security_lifecycle_automation_worker.py
git commit -m "feat(lifecycle): derive automated case disposition"
```

### Task 2: Keep Announced Events in Automatic Monitoring

**Files:**
- Modify: `src/security_lifecycle_decision_policy.py`
- Modify: `src/security_lifecycle_sec_evidence.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py:45-75,430-505,600-670`
- Modify: `src/security_lifecycle_automation_worker.py`
- Test: `tests/test_security_lifecycle_decision_policy.py`
- Test: `tests/test_security_lifecycle_sec_evidence.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`
- Test: `tests/test_security_lifecycle_automation_worker.py`

**Interfaces:**
- Consumes: observation event kinds plus cited SEC facts.
- Produces: pending-event blocker context without a false accepted assessment:

```python
AutomationBlocker(
    code="sec_evidence_insufficient",
    retryable=True,
    context={
        "monitoring_reason": "event_completion_not_confirmed",
        "effective_date": "2026-09-05",  # omitted when absent
        "source_deadline": "2026-10-15",  # only when explicit in cited text
    },
)
```

After one final bounded regulator/market/publisher check on or after an explicit
source-defined termination/outside date:

```python
AutomationBlocker(
    code="sec_evidence_insufficient",
    retryable=False,
    context={
        "monitoring_reason": "not_confirmed_as_of",
        "as_of": "2026-10-15",
        "effective_date": "2026-09-05",
        "source_deadline": "2026-10-15",
    },
)
```

No new blocker code or DB CHECK value is introduced.

- [ ] **Step 1: Write RED tests for announced versus completed M&A**

```python
def test_merger_agreement_without_completion_stays_automatic_monitoring():
    bundle = load_fixture(event_kinds=("merger_agreement",), transaction_kind="stock")
    result = evaluate_or_block(bundle, at="2026-08-26T00:00:00Z")
    assert result.status == "blocked"
    assert result.blockers[0].context["monitoring_reason"] == "event_completion_not_confirmed"
    assert result.assessment is None

def test_acquisition_completed_with_stock_terms_is_prefilled_exception():
    decision = evaluate_fixture(event_kinds=("acquisition_completed",), transaction_kind="stock")
    assert decision.decision_tier == "review_suggested"
    assert decision.rule_id == "lifecycle.ma_review"

def test_explicit_outside_date_is_a_hash_cited_source_deadline():
    from src.security_lifecycle_sec_evidence import collect_sec_evidence

    case = _case("BLBD")
    case["document"] += (
        " The merger agreement may be terminated if the merger is not "
        "consummated by October 15, 2026 (the Outside Date)."
    )
    result = collect_sec_evidence(
        context=_context("BLBD"),
        transport=_FixtureTransport(case),
        retrieved_at="2026-08-26T00:00:00Z",
    )
    deadline = result.source_deadlines[0]
    assert deadline.date == "2026-10-15"
    assert deadline.rule_id == "sec.explicit_transaction_termination_date"
    assert hashlib.sha256(deadline.cited_text.encode()).hexdigest() == deadline.cited_text_sha256
```

Add cancellation/no-change fixtures that produce `verified_automatic` only from explicit cited regulator facts.

- [ ] **Step 2: Write retry/backoff RED tests**

```python
assert pending_before_date.blockers[0].retryable is True
assert pending_before_date.retry_at == "2026-08-27T00:00:00Z"
assert pending_after_seven_days.blockers[0].retryable is True
assert pending_after_seven_days.retry_at == "2026-09-19T00:00:00Z"  # weekly
assert pending_after_source_deadline.blockers[0].retryable is False
assert pending_after_source_deadline.retry_at is None
assert pending_after_source_deadline.blockers[0].context["monitoring_reason"] == "not_confirmed_as_of"
assert no_date_pending.retry_at == "2026-09-02T00:00:00Z"  # weekly
```

Add a negative owner: an effective date with no explicit source deadline never
becomes a terminal negative merely because seven days elapsed.

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```bash
pytest tests/test_security_lifecycle_decision_policy.py tests/test_security_lifecycle_sec_evidence.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_automation_worker.py -q
```

Expected: current `transaction_kind` creates `lifecycle.ma_review` immediately and `_blockers` always retries after one day with empty context.

- [ ] **Step 4: Add one hash-cited source-deadline result without changing schema authority**

Add this provider-result type; it is scheduling evidence, not an assessment
fact:

```python
@dataclass(frozen=True)
class SecSourceDeadline:
    date: str
    evidence_id: str
    span_start_byte: int
    span_end_byte: int
    cited_text: str
    cited_text_sha256: str
    rule_id: str
    rule_version: str
```

Add `source_deadlines: tuple[SecSourceDeadline, ...]` to `SecEvidenceResult`.
Extract it only from a cited sentence containing one of the closed phrases
`outside date`, `termination date`, or `may be terminated if` and an explicit
month-name or ISO date. The result keeps the sentence's byte range and uses
rule ID `sec.explicit_transaction_termination_date`. Reject two distinct
deadlines as `sec_evidence_insufficient` rather than choosing by order.

Add those same three phrases to `_evidence_excerpts`' reviewed anchor set so
the cited sentence is retained in the bounded, hash-addressed excerpt before
deadline extraction runs. Do not scan full provider bytes and then persist an
uncited date.

Bump the SEC adapter/extractor `_RULE_VERSION` from `"2"` to `"3"`; the
evidence selection and typed result behavior changed. Update exact-version
owners rather than accepting mixed v2/v3 output.

Do not infer this date from filing date, effective date, deal custom, or legal
memory. Persist the chosen date plus evidence ID, byte range, cited-text hash,
rule ID, and rule version in the blocker context. This changes no closed
`fact_type` or SQLite CHECK authority. An exact schema diff in tests must
remain empty.

- [ ] **Step 5: Detect pending completion before policy evaluation**

Add a pure helper in the scheduler:

```python
def _pending_event_monitoring(
    case: Mapping[str, object],
    facts: Iterable[object],
    *,
    source_family_results: Mapping[str, str],
    source_deadlines: Iterable[SecSourceDeadline],
    at: str,
) -> AutomationBlocker | None:
    kinds = _event_kinds(case)
    if "acquisition_completed" in kinds:
        return None
    if not kinds.intersection({"merger_agreement", "merger_proxy", "listing_status_review"}):
        return None
    if _has_terminal_or_identity_resolution(facts):
        return None
    return _event_completion_blocker(
        facts,
        source_family_results,
        source_deadlines=source_deadlines,
        at=at,
    )
```

This helper may use an explicitly extracted `effective_date`; it may not derive a deadline from filing date or legal memory.

Change `_local_news_evidence` to return its typed blocker codes as well as
evidence and diagnostics; a successful zero-row local query is `available`,
not `unavailable`. For a pending M&A/listing-review event at or after its
effective date, run the existing bounded IBKR current-contract lookup even when
there is no successor fact. `_LifecycleIbkrGateway` remains the only client and
the shared lock remains mandatory. Record source-family results as exactly
`available`, `unavailable`, or `conflict`; do not infer availability from row
count.

- [ ] **Step 6: Implement exact retry timing and final dated context**

- Before an explicit effective date: retry on that date.
- From the effective date through day 7 inclusive: retry daily.
- After day 7 and before any explicit source deadline: retry weekly.
- On or after an explicit `termination_date`: persist `not_confirmed_as_of`
  only after regulator, market-infrastructure, and publisher acquisition all
  completed without an unavailable/limited blocker in that run.
- Without an explicit date: retry weekly with no invented expiry.
- Provider-specific `Retry-After` and SEC budget rules remain unchanged and take precedence when they yield a later allowed retry.

Change `_blockers` to accept prebuilt `AutomationBlocker` values plus code-only provider blockers; do not discard context.

- [ ] **Step 7: Bump policy authority exactly once**

Change:

```python
AUTOMATION_POLICY_VERSION = "trusted-lifecycle-automation-v3"
```

Add `lifecycle.event_monitoring` to `RULE_VERSIONS` only if a completed decision row uses it. A blocked monitoring run does not invent a rule ID or assessment.

- [ ] **Step 8: Re-run focused tests**

Run:

```bash
pytest tests/test_security_lifecycle_decision_policy.py tests/test_security_lifecycle_fact_kernel.py tests/test_security_lifecycle_sec_evidence.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_automation_worker.py -q
```

Expected: all pass; pending agreements create no human draft, completed/ambiguous acquisitions still do, and v2 run identity tests are updated only where the policy version is deliberately asserted.

- [ ] **Step 9: Commit**

```bash
git add src/security_lifecycle_decision_policy.py src/security_lifecycle_sec_evidence.py src/security_lifecycle_automation_worker.py src/service/security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_decision_policy.py tests/test_security_lifecycle_sec_evidence.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_automation_worker.py
git commit -m "feat(lifecycle): monitor unconfirmed events automatically"
```

### Task 3: Enrich IBKR Evidence Without Promoting Price to Authority

**Files:**
- Modify: `src/security_lifecycle_ibkr_evidence.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py:520-600`
- Test: `tests/test_security_lifecycle_ibkr_evidence.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`
- Test: `tests/test_security_lifecycle_decision_policy.py`

**Interfaces:**
- Consumes: the already-connected read-only IBKR gateway and unique contract snapshot.
- Extends `IBKRContractGateway` with:

```python
def reqMktData(
    self,
    contract: Contract,
    genericTickList: str,
    snapshot: bool,
    regulatorySnapshot: bool,
) -> object: ...

def sleep(self, seconds: float) -> None: ...
```

- Produces optional locator field:

```python
{
    "contract_status": "found",
    "adapter_version": "2",
    "snapshot": {
        "symbol": "HAPN",
        "localSymbol": "HAPN",
        "conId": 112233,
        "secType": "STK",
        "primaryExchange": "NASDAQ",
        "validExchanges": ["NASDAQ", "NYSE", "SMART"],
        "currency": "USD",
        "retrieved_at": "2026-08-26T14:30:02Z",
    },
    "market_data": {
        "status": "live" | "delayed" | "frozen" | "delayed_frozen" | "unavailable",
        "last": "123.45" | None,
        "provider_time": "2026-08-26T14:30:00Z" | None,
        "retrieved_at": "2026-08-26T14:30:02Z",
        "fresh": True | False,
    },
}
```

This complete object is both the JSON-decoded `source_locator` and the canonical
`excerpt`; `content_sha256` hashes that exact excerpt. Contract facts remain
byte-cited from the nested `snapshot`, while quote quality is therefore bound
to the same immutable evidence payload rather than living only in unhashed
metadata.

Set payload `adapter_version` to `"2"` and emitted
`ibkr.contract_snapshot.*` fact `extractor_rule_version` to `"2"`; the
canonical cited payload changed even though the identity fact vocabulary did
not.

- [ ] **Step 1: Write market-data normalization RED tests**

Use `Ticker`-shaped fakes for IBKR market data type codes 1/2/3/4 and missing data:

```python
class _Gateway:
    def __init__(
        self,
        responses=(),
        *,
        market_ticker=None,
        connected=True,
        lock_state=None,
    ):
        self.connected = connected
        self.responses = list(responses)
        self.requests = []
        self.market_ticker = market_ticker
        self.market_requests = []
        self.sleep_calls = []
        self.lock_state = lock_state

    def isConnected(self):
        return self.connected

    def reqContractDetails(self, contract):
        assert self.lock_state is None or self.lock_state["held"] is True
        self.requests.append(contract)
        response = self.responses.pop(0) if self.responses else []
        if isinstance(response, BaseException):
            raise response
        return response

    def reqMktData(self, contract, genericTickList, snapshot, regulatorySnapshot):
        assert self.lock_state is None or self.lock_state["held"] is True
        self.market_requests.append(
            (contract, genericTickList, snapshot, regulatorySnapshot)
        )
        return self.market_ticker

    def sleep(self, seconds):
        assert self.lock_state is None or self.lock_state["held"] is True
        self.sleep_calls.append(seconds)


def _market_ticker(
    *,
    market_data_type: int = 1,
    last: float = 12.57,
    provider_time: datetime | None = datetime.fromisoformat(
        "2026-08-25T01:01:00+00:00"
    ),
):
    return SimpleNamespace(
        marketDataType=market_data_type,
        last=last,
        time=provider_time,
    )


def _read_market(market_ticker):
    state, lock = _lock_recorder()
    gateway = _Gateway(
        responses=([_details()], [_details()], [_details()]),
        market_ticker=market_ticker,
        lock_state=state,
    )
    return gateway, _read(gateway, lock)


@pytest.mark.parametrize(
    ("market_data_type", "expected"),
    [(1, "live"), (2, "frozen"), (3, "delayed"), (4, "delayed_frozen")],
)
def test_market_data_type_is_preserved(market_data_type, expected):
    _gateway, result = _read_market(
        _market_ticker(market_data_type=market_data_type)
    )
    locator = result.evidence[0].source_locator
    assert locator["market_data"]["status"] == expected
    assert locator["market_data"]["fresh"] is (expected == "live")

def test_present_delayed_price_is_not_fresh():
    gateway, result = _read_market(_market_ticker(market_data_type=3))
    locator = result.evidence[0].source_locator
    assert locator["market_data"]["last"] == "12.57"
    assert locator["market_data"]["fresh"] is False
    assert gateway.market_requests[0][1:] == ("", True, False)
    assert gateway.sleep_calls == [2.0]

def test_live_quote_older_than_fifteen_minutes_is_not_fresh():
    _gateway, result = _read_market(
        _market_ticker(
            provider_time=datetime.fromisoformat("2026-08-25T00:30:00+00:00")
        )
    )
    locator = result.evidence[0].source_locator
    assert locator["market_data"]["status"] == "live"
    assert locator["market_data"]["fresh"] is False

def test_locator_and_excerpt_are_the_same_hash_bound_payload():
    _gateway, result = _read_market(_market_ticker())
    evidence = result.evidence[0]
    assert json.loads(evidence.excerpt) == evidence.source_locator
    assert hashlib.sha256(evidence.excerpt.encode()).hexdigest() == evidence.content_sha256
```

Use decimal strings, not binary floats, in persisted JSON.

- [ ] **Step 2: Write policy regression tests**

Extend the existing
`test_terminal_delisting_separates_conclusion_from_action_readiness` so the
confirmed fixture also contains publisher evidence whose locator has
`{"last": "12.57"}`; it must remain `transition_eligible`. Add a found-contract
variant with `market_data.status="frozen"`; it must remain
`waiting_market_confirmation`.

In `test_simple_symbol_continuation_requires_regulator_market_and_eligible_preview`,
add this stale-market owner:

```python
stale_market = _evaluate(
    evidence=(
        _evidence("sec", "regulator"),
        {
            **_evidence("ibkr", "market_infrastructure"),
            "source_locator": {
                "contract_status": "found",
                "market_data": {
                    "status": "live",
                    "last": "12.57",
                    "provider_time": "2026-08-25T00:30:00Z",
                    "retrieved_at": "2026-08-25T01:02:03Z",
                    "fresh": False,
                },
            },
        },
    ),
    facts=_identity_facts(),
    transition_preview=lambda _request: (_ for _ in ()).throw(
        AssertionError("stale market data must not preview a mutation")
    ),
)
assert stale_market.decision_tier == "verified_automatic"
assert stale_market.action_readiness == "waiting_market_confirmation"
assert stale_market.transition_requested is False
```

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```bash
pytest tests/test_security_lifecycle_ibkr_evidence.py tests/test_security_lifecycle_decision_policy.py tests/test_security_lifecycle_automation_scheduler.py -q
```

Expected: gateway protocol lacks market data methods and locator has no `market_data` object.

- [ ] **Step 4: Implement bounded quote acquisition under the existing lock**

After exactly one contract snapshot is selected, request one read-only snapshot
for `Contract(conId=<selected>, exchange="SMART")`, call `gateway.sleep()` once
for a new `quote_wait_s=2.0` parameter, and never retry recursively. Validate
`0 < quote_wait_s <= 5.0`; this is separate from the existing lock-acquisition
timeout. Count the quote request in `requests_made`.
The hard per-case IBKR budget is therefore `max_queries + 1` (at most nine
requests with the existing default/effective cap of eight contract queries).
If contract selection is missing or ambiguous, no quote request occurs.

Rules:

```python
QUOTE_MAX_AGE = timedelta(minutes=15)
QUOTE_FUTURE_SKEW = timedelta(minutes=5)
age = retrieved_at - provider_time
fresh = (
    market_status == "live"
    and last is not None
    and provider_time is not None
    and -QUOTE_FUTURE_SKEW <= age <= QUOTE_MAX_AGE
)
```

Normalize `last` through `Decimal(str(value))` and persist its plain decimal
string only when it is finite and positive. Do not call local-price fallback,
another provider, or a second IBKR client. Contract-query entitlement and
gateway errors retain existing typed blockers; quote unavailability is
recorded in the payload and does not erase valid contract identity evidence.

- [ ] **Step 5: Keep decision authority contract-based**

Do not emit a new identity fact from `last`. Split continuation/venue
corroboration into `market_identity_matches` and `market_snapshot_fresh`:

`market_snapshot_fresh` re-parses status, decimal, provider timestamp, and
retrieval timestamp with the same 15-minute/5-minute bounds. It requires the
stored `fresh` flag to be `True` but never trusts that flag alone. A malformed
or internally inconsistent market-data object is not fresh and cannot reach a
preview.

- identity mismatch or ambiguity remains `review_suggested` with
  `market_corroboration_missing`;
- identity matches but the quote is stale/delayed/frozen/unavailable becomes
  `verified_automatic` + `waiting_market_confirmation`, creates no transition,
  and stays on the existing bounded readiness recheck; and
- only identity match plus a fresh snapshot can become `not_applicable` or
  `transition_eligible`.

Keep terminal action behavior:

- contract `missing` can satisfy post-date market absence;
- contract `found` remains waiting, regardless of whether its quote is live,
  delayed, frozen, or absent;
- contract ambiguity/unavailability stays typed and retryable as currently
  implemented; and
- quote quality is displayed as corroborating context.

- [ ] **Step 6: Re-run focused tests**

Run:

```bash
pytest tests/test_security_lifecycle_ibkr_evidence.py tests/test_security_lifecycle_decision_policy.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_grounded_shadow.py -q
```

Expected: all pass; existing contract facts and grounded shadow decisions are unchanged.

- [ ] **Step 7: Commit**

```bash
git add src/security_lifecycle_ibkr_evidence.py src/service/security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_ibkr_evidence.py tests/test_security_lifecycle_decision_policy.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_grounded_shadow.py
git commit -m "feat(lifecycle): record IBKR quote quality as evidence"
```

### Task 4: Expose Disposition and Queue Filters Through the Read API

**Files:**
- Modify: `src/tools/security_lifecycle_tools.py:245-410`
- Modify: `src/api/routes/security_lifecycle.py:275-315`
- Modify: `apps/arkscope-web/src/api.ts:2370-2505,2840-2910`
- Test: `tests/test_security_lifecycle_tools.py`
- Test: `tests/test_security_lifecycle_routes.py`
- Test: `apps/arkscope-web/src/apiError.test.ts`

**Interfaces:**
- Adds summary fields:

```ts
export type SecurityLifecycleDisposition =
  | "confirmed_monitoring"
  | "confirmed_effective"
  | "not_confirmed_yet"
  | "exception_required";
export type SecurityLifecycleQueueBucket = "attention" | "monitoring" | "history";
export type SecurityLifecycleSourceFamilyState =
  | "confirmed" | "present" | "missing" | "unavailable" | "conflict";
export type SecurityLifecycleDispositionReason =
  | "awaiting_initial_automation"
  | "automation_running"
  | "waiting_effective_date"
  | "waiting_market_confirmation"
  | "waiting_transition_revalidation"
  | "retryable_source_unavailable"
  | "event_completion_not_confirmed"
  | "not_confirmed_as_of"
  | "source_missing"
  | "source_conflict"
  | "ambiguous_event"
  | "nonretryable_provider_failure"
  | "automation_failure"
  | "resolved_no_change"
  | "resolved_assessment"
  | "transition_applied"
  | "transition_reversed"
  | "transition_cancelled"
  | "transition_needs_review"
  | "reviewed_inconclusive";

interface SecurityLifecycleCaseSummary {
  disposition: SecurityLifecycleDisposition;
  queue_bucket: SecurityLifecycleQueueBucket;
  disposition_reason: SecurityLifecycleDispositionReason;
  last_checked_at: string | null;
  next_check_at: string | null;
  source_family_status: Partial<Record<SecurityLifecycleEvidenceSourceFamily, SecurityLifecycleSourceFamilyState>>;
}
```

- Adds optional query `queue_bucket=attention|monitoring|history`.
- Adds response `queue_counts: { attention: number; monitoring: number; history: number }`.
  Compute counts after source-presence/ticker/workflow/relevance/event/proposal
  filters, but before the selected `queue_bucket` and before `limit`, so changing
  the segmented view does not erase the other view counts.

- [ ] **Step 1: Write service RED tests for projection and filtering**

```python
result = service.list_cases(queue_bucket="monitoring", limit=2)
assert all(row["queue_bucket"] == "monitoring" for row in result["cases"])
assert result["queue_counts"] == {
    "attention": 1,
    "monitoring": 3,
    "history": 2,
}
assert result["count"] == 3
```

Assert ticker prefix filtering and source-presence filtering still compose with the bucket before limit.

- [ ] **Step 2: Write route RED tests**

```python
response = client.get("/security-lifecycle/cases?queue_bucket=monitoring")
assert response.status_code == 200
assert response.json()["cases"][0]["disposition"] == "not_confirmed_yet"

invalid = client.get("/security-lifecycle/cases?queue_bucket=unknown")
assert invalid.status_code == 422
assert invalid.json() == {"detail": {"code": "queue_bucket"}}
```

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```bash
pytest tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py -q
```

Expected: service and route reject the unknown argument/signature.

- [ ] **Step 4: Apply the pure projection before filtering**

In `_cases`, after transitions and source context are attached:

```python
projection = project_lifecycle_disposition(item)
item.update({
    "disposition": projection.disposition,
    "queue_bucket": projection.queue_bucket,
    "disposition_reason": projection.reason_code,
    "last_checked_at": projection.last_checked_at,
    "next_check_at": projection.next_check_at,
    "source_family_status": dict(projection.source_family_status),
})
```

Validate `queue_bucket` against `LIFECYCLE_QUEUE_BUCKETS`; do not duplicate its literals in the route.

- [ ] **Step 5: Extend TypeScript contracts and query serialization**

Add the closed types and fields above. Extend `SecurityLifecycleCaseFilters` with optional `queue_bucket`; the existing `lifecycleQuery` serializer already emits non-empty fields.

- [ ] **Step 6: Re-run backend tests and frontend typecheck**

Run:

```bash
pytest tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py -q
cd apps/arkscope-web && npm run typecheck
```

Expected: all pass with no `as string` widening of disposition values.

- [ ] **Step 7: Commit**

```bash
git add src/tools/security_lifecycle_tools.py src/api/routes/security_lifecycle.py apps/arkscope-web/src/api.ts tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py
git commit -m "feat(lifecycle): expose disposition queue projections"
```

### Task 5: Add Attention, Monitoring, History, and Localized Decision Copy

**Files:**
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/lifecyclePresentation.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts`
- Modify: `apps/arkscope-web/src/styles.css`
- Test: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`
- Test: `apps/arkscope-web/src/lifecycle/lifecyclePresentation.test.ts`
- Create: `apps/arkscope-web/src/LifecycleCss.test.ts`

**Interfaces:**
- Consumes: disposition fields from Task 4.
- Produces:

```ts
export function lifecycleDispositionLabel(
  value: SecurityLifecycleDisposition,
  locale: LifecycleLocale,
): string;

export function lifecycleDispositionReasonLabel(
  value: SecurityLifecycleDispositionReason,
  locale: LifecycleLocale,
): string;

export function lifecycleSourceFamilyStateLabel(
  value: SecurityLifecycleSourceFamilyState,
  locale: LifecycleLocale,
): string;

export function lifecycleAutomationNarrative(
  assessment: SecurityLifecycleAssessment,
  ticker: string,
  locale: LifecycleLocale,
): { conclusion: string; impact: string };
```

- [ ] **Step 1: Write exhaustive presentation RED tests**

```ts
expect(lifecycleDispositionLabel("confirmed_monitoring", "zh-Hant")).toBe("已確認，持續監看");
expect(lifecycleDispositionLabel("confirmed_effective", "zh-Hant")).toBe("已確認完成");
expect(lifecycleDispositionLabel("not_confirmed_yet", "zh-Hant")).toBe("尚未確認發生");
expect(lifecycleDispositionLabel("exception_required", "zh-Hant")).toBe("需要複查");
```

For each known automation `rule_id`, assert English and Traditional Chinese narrative uses structured fields and does not equal the stored English `conclusion`. Human/legacy assessments continue to show their stored text.

- [ ] **Step 2: Write queue UI RED tests**

Mock counts and mixed cases, then assert:

```tsx
expect(selectedTab().textContent).toContain("需要處理");
expect(renderedTickers()).toEqual(["CONFLICT"]);

clickTab("監看中");
expect(renderedTickers()).toEqual(["PENDING", "WAITING"]);
expect(host!.textContent).toContain("下次查核");

clickTab("歷史");
expect(renderedTickers()).toEqual(["DONE"]);

clickTab("全部");
expect(renderedTickers()).toEqual(["CONFLICT", "PENDING", "WAITING", "DONE"]);
```

Assert opening/rendering History does not acknowledge transition activity or write any API.

- [ ] **Step 3: Run focused frontend tests and verify RED**

Run:

```bash
cd apps/arkscope-web && npm test -- lifecycle/lifecyclePresentation.test.ts lifecycle/LifecycleView.test.tsx LifecycleCss.test.ts
```

Expected: no disposition helpers or queue controls exist and automation narrative remains stored English.

- [ ] **Step 4: Implement exhaustive localized presentation**

Use `Record<SecurityLifecycleDisposition, string>` and closed maps for known reason codes. For automation rules, generate truthful generic copy from structured values:

```ts
const known: Record<KnownAutomationRuleId, NarrativeBuilder> = {
  "lifecycle.terminal_delisting": terminalNarrative,
  "lifecycle.no_identity_change": noChangeNarrative,
  "lifecycle.simple_symbol_continuation": continuationNarrative,
  "lifecycle.venue_transfer": venueNarrative,
  "lifecycle.ma_review": mergerReviewNarrative,
  "lifecycle.source_conflict": conflictNarrative,
  "lifecycle.insufficient_identity_facts": insufficientNarrative,
};
```

Unknown automation rules use localized unknown-rule copy plus rule ID; they do not map to a known conclusion. Evidence excerpts remain source-language text.

- [ ] **Step 5: Add a stable segmented queue control**

Use four compact buttons with fixed responsive dimensions and counts:

```tsx
const QUEUE_VIEWS = ["attention", "monitoring", "history", "all"] as const;
```

Default `queueView` is `attention`. For the first three views send `queue_bucket`; for `all`, omit it. Preserve the separate Investment events/Data integrity control. Changing bucket clears only the selected case if that case is absent from the new response; it does not reset ticker/event filters.

- [ ] **Step 6: Show monitoring facts without explanatory feature copy**

In the table/drawer show disposition label, typed wait reason, `last_checked_at`, `next_check_at`, and source-family status. Do not add instructional paragraphs. Use existing icons only for commands; tabs remain text because they are named views.

- [ ] **Step 7: Add restrained responsive styles**

Use existing lifecycle variables, no new card nesting, no gradient/orb decoration, 8px-or-less radius, and a stable segmented grid:

```css
.lifecycle-queue-switch {
  display: grid;
  grid-template-columns: repeat(4, minmax(8rem, 1fr));
  gap: .4rem;
}
@media (max-width: 720px) {
  .lifecycle-queue-switch { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
```

Buttons must wrap text without changing row height between active/inactive states.

- [ ] **Step 8: Run frontend gates**

Run:

```bash
cd apps/arkscope-web && npm test -- lifecycle/lifecyclePresentation.test.ts lifecycle/LifecycleView.test.tsx LifecycleCss.test.ts
cd apps/arkscope-web && npm run typecheck
cd apps/arkscope-web && npm run check:i18n-literals
cd apps/arkscope-web && npm run build
```

Expected: all pass; no source excerpt is translated or hidden by presentation helpers.

- [ ] **Step 9: Commit**

```bash
git add apps/arkscope-web/src/lifecycle/LifecycleView.tsx apps/arkscope-web/src/lifecycle/lifecyclePresentation.ts apps/arkscope-web/src/i18n/resources/en/explore.ts apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts apps/arkscope-web/src/styles.css apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx apps/arkscope-web/src/lifecycle/lifecyclePresentation.test.ts apps/arkscope-web/src/LifecycleCss.test.ts
git commit -m "feat(lifecycle): separate attention monitoring and history"
```

### Task 6: Offline Admission and Live-Cutover Hard Stop

**Files:**
- Create: `docs/superpowers/evidence/2026-08-26-lifecycle-automated-disposition/README.md`
- Create: `docs/superpowers/evidence/2026-08-26-lifecycle-automated-disposition/SHA256SUMS`
- Create: fixture/browser scripts only inside the evidence directory.

**Interfaces:**
- Consumes: Tasks 1-5.
- Produces: offline product authority and an explicit list of still-unauthorized live actions.

- [ ] **Step 1: Run mutation checks on the projection and price boundary**

Apply and restore each mutation separately:

1. map retryable blocker to attention;
2. map resolved no-change to monitoring;
3. let delayed price satisfy `fresh=True`;
4. let publisher price override missing IBKR contract;
5. render an automation assessment's stored English conclusion in zh-Hant;
6. make History rendering acknowledge activity;
7. treat an effective date as a source termination deadline;
8. remove `market_data` from the hash-bound canonical excerpt;
9. map an approved, not-yet-applied transition to History; and
10. map `event_completion_not_confirmed` to provider-unavailable copy.

Each mutation must kill at least one named owner test, produce no unexpected owner drift, and restore touched files byte-for-byte.

- [ ] **Step 2: Run focused backend gates twice**

```bash
pytest tests/test_security_lifecycle_disposition.py tests/test_security_lifecycle_decision_policy.py tests/test_security_lifecycle_sec_evidence.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_ibkr_evidence.py tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py -q
pytest tests/test_security_lifecycle_disposition.py tests/test_security_lifecycle_decision_policy.py tests/test_security_lifecycle_sec_evidence.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_ibkr_evidence.py tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py -q
```

Expected: identical counts and no network access.

- [ ] **Step 3: Run complete backend/frontend gates**

```bash
pytest -q
cd apps/arkscope-web && npm test
cd apps/arkscope-web && npm run typecheck
cd apps/arkscope-web && npm run check:i18n-literals
cd apps/arkscope-web && npm run build
```

Record current exact counts; do not pin an older collection count in advance.

- [ ] **Step 4: Run a bilingual browser matrix**

Fixtures cover all four dispositions and all five source-family status values
across the matrix, plus source conflict, frozen quote, future effective date,
post-date market wait, settled history, stale reopen, and source-missing
integrity view. Capture desktop and mobile in English and Traditional Chinese.

Browser assertions:

```js
if (externalRequests.length !== 0) throw new Error("external request");
if (renderAcknowledgementCalls !== 0) throw new Error("render acknowledged activity");
if (consoleErrors.length || pageErrors.length) throw new Error("browser error");
if (overlapCount !== 0 || clippedTextCount !== 0) throw new Error("layout failure");
```

- [ ] **Step 5: Seal the evidence package**

Record:

- exact base/head commits and linear topology;
- policy version `trusted-lifecycle-automation-v3`;
- unchanged profile schema inventory;
- zero provider/network calls;
- zero production DB reads/writes/migrations/backups/restores;
- full and focused command outputs;
- mutation owner sets and byte-identical restore hashes;
- browser screenshot hashes; and
- limitation that live IBKR market-data shape and live v3 scheduler replay remain unexercised.

Hash every payload with `SHA256SUMS`, verify it with `sha256sum -c`, and hash the manifest itself separately.

- [ ] **Step 6: Commit offline admission evidence**

```bash
git add docs/superpowers/evidence/2026-08-26-lifecycle-automated-disposition
git commit -m "test(lifecycle): seal automated disposition admission"
```

- [ ] **Step 7: Stop at the live boundary**

Do not restart the current App from the v3 tree. A restart would make the policy-version bump select cases and issue SEC/IBKR calls. Report these separate decisions to the user:

1. review/merge of the implementation branch;
2. bounded read-only SEC/IBKR v3 canary authority;
3. App cutover/restart after canary review; and
4. push.

No profile schema migration is expected. If exact preflight finds a schema need, stop and write a migration amendment before any production operation.
