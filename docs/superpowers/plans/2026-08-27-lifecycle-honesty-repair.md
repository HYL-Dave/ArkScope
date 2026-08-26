# Lifecycle Honesty Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair deadline provenance, deadline extraction, failed-run replay, and History presentation so automation fails atomically, can recover after a deployment repair, and never labels an unconfirmed event as confirmed complete.

**Architecture:** Keep the existing profile schema and semantic policy authority unchanged. Add a deploy-time execution revision to run reservation, validate every deadline citation at the fact-kernel transaction boundary, replace broad date harvesting with a closed directional grammar, and derive the completed-check date through the existing pure disposition projection. The backend exposes one nullable derived date, and the frontend renders exact bilingual History copy without acknowledging the row.

**Tech Stack:** Python 3, SQLite, React 18, TypeScript, i18next, pytest, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-27-lifecycle-honesty-repair-design.md`

## Global Constraints

- Reviewed design authority is `add52f39618b9b25f983384b5454b68f93ebf024`; product/test repair base is `11e7a5d4f6856062a5ac00a8d90ed97b5c2e56cb`. Before the first product edit, require a clean linear descendant containing only the committed plan after that design authority.
- `AUTOMATION_POLICY_VERSION` remains exactly `trusted-lifecycle-automation-v3`; operational replay must not manufacture a policy bump.
- Existing SEC `_RULE_VERSION` remains exactly `"3"` for facts and evidence locators. Only `SecSourceDeadline` uses deadline rule version `"4"`.
- Invalid provenance fails loudly and atomically. Ambiguous filing prose emits no deadline and remains in Monitoring.
- Citation enforcement and execution-revision replay are one admission unit. Intermediate commits may exist on this unmerged branch, but neither mechanism may be merged, cut over, or cherry-picked without the other.
- `AUTOMATION_EXECUTION_REVISION` is deployment authority only. It never enters decision provenance, assessment acceptance authority, ticker-transition approval, or ticker-transition apply checks.
- Operator-triggered retry remains out of scope; this plan adds no endpoint, button, or attended reset command.
- Do not add a profile column, table, index, startup DDL, mutable case-state field, or migration.
- `source_deadline` is the source-defined boundary. `disposition_as_of` is the actual completed-check date and may be later after App downtime.
- Rendering History never acknowledges activity or shortens reversal availability.
- Keep the uncommitted user-owned Priority Map RED entry on `master` untouched. A separate GREEN closeout is a post-admission, merge-authorized action.
- No provider call, general Web Search, production DB read/write/preflight/backup/migration/restore, App restart, merge, or push is authorized by this plan.
- The existing packet at product/test authority `f63a044c3495dcd95db2e996345082eb492baf7d` remains historical evidence, not merge admission.

---

## File Map

- `src/security_lifecycle_automation_worker.py`: owns the deployed execution-revision constant and passes it explicitly into run reservation.
- `src/security_lifecycle_fact_kernel.py`: owns semantic-run lookup, replay-run identity, shared byte citation validation, blocker-context rewriting, and atomic persistence.
- `src/security_lifecycle_sec_evidence.py`: owns the closed deadline grammar plus deadline-only rule identity/version.
- `src/service/security_lifecycle_automation_scheduler.py`: carries cited deadline provenance and records the actual completed-check date.
- `src/security_lifecycle_disposition.py`: remains a pure projection and derives `disposition_as_of` without storing state.
- `src/tools/security_lifecycle_tools.py`: exposes `disposition_as_of` in case summaries/details.
- `apps/arkscope-web/src/api.ts`: adds the nullable derived date to the closed case contract.
- `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`: renders the dated History reason in table and drawer.
- `apps/arkscope-web/src/i18n/resources/en/explore.ts`: English dated History copy.
- `apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts`: Traditional Chinese dated History copy.
- `tests/test_security_lifecycle_fact_kernel.py`: replay and producer-to-validator contract owners.
- `tests/test_security_lifecycle_automation_worker.py`: execution-revision wiring and persist-failure replay owner.
- `tests/test_security_lifecycle_sec_evidence.py`: closed grammar, version isolation, and exact citation owners.
- `tests/test_security_lifecycle_automation_scheduler.py`: overdue catch-up date and provenance-carriage owners.
- `tests/test_security_lifecycle_disposition.py`: truthful History projection and derived-date owners.
- `tests/test_security_lifecycle_tools.py`: read-contract owner.
- `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`: bilingual visible-behavior and render-read-only owners.
- `apps/arkscope-web/src/lifecycle/lifecyclePresentation.test.ts`: exhaustive known-value fallback guard.
- `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/`: offline authority, mutation ledger, browser matrix, schema comparison, and checksums.

### Task 1: Add Deploy-Time Failed-Run Replay Authority

**Files:**
- Modify: `src/security_lifecycle_automation_worker.py`
- Modify: `src/security_lifecycle_fact_kernel.py`
- Test: `tests/test_security_lifecycle_fact_kernel.py`
- Test: `tests/test_security_lifecycle_automation_worker.py`
- Test: `tests/test_security_lifecycle_investigation.py`
- Test: `tests/test_security_lifecycle_tools.py`
- Test: `tests/test_security_lifecycle_routes.py`

**Interfaces:**
- Consumes: the existing semantic tuple `(case_id, observation_fingerprint_sha256, policy_version, mode, input_evidence_set_sha256)` and indexed `security_lifecycle_automation_runs(case_id, created_at)` rows.
- Produces:

```text
AUTOMATION_EXECUTION_REVISION = "trusted-lifecycle-execution-r1"

automation_run_key(
    *,
    case_id: str,
    observation_fingerprint_sha256: str,
    policy_version: str,
    mode: str,
    input_evidence_set_sha256: str,
) -> str

_execution_run_key(
    *,
    semantic_run_key: str,
    execution_revision: str,
    predecessor_failed_run_id: str | None,
) -> str

SecurityLifecycleFactKernel.reserve_run(
    self,
    *,
    case_id: str,
    observation_fingerprint_sha256: str,
    policy_version: str,
    mode: str,
    execution_revision: str,
    query_context: Mapping[str, object],
    diagnostics: Mapping[str, object],
    at: str,
) -> AutomationRunClaim
```

The persisted query context always contains `semantic_run_key`, `execution_revision`, and `input_evidence_set_sha256`. Replay rows additionally contain `predecessor_failed_run_id`; first attempts omit that key. Rows created before this task have no execution revision and are read as `unknown` without being rewritten.

- [ ] **Step 1: Write RED tests for replay identity and bounded selection**

Add these owners to `tests/test_security_lifecycle_fact_kernel.py`:

First extend the existing `_reserve` helper with this exact default so every
existing owner remains on the current deployed implementation unless a test
overrides it:

```python
"execution_revision": "trusted-lifecycle-execution-r1",
```

Add the same explicit keyword to the direct `reserve_run` fixture calls in
`tests/test_security_lifecycle_investigation.py`,
`tests/test_security_lifecycle_tools.py`, and
`tests/test_security_lifecycle_routes.py`. Do not make the production method
argument optional merely to preserve old test call sites.

```python
def test_failed_semantic_run_replays_once_per_execution_revision():
    _conn, store, kernel, case_id = _context()
    first = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r0",
    )
    kernel.fail_run(
        run_id=first.run_id,
        failure_code="persistence_failed",
        diagnostics={"persist_failures": 1},
        at=_LATER,
    )

    replay = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-26T00:00:00Z",
    )
    duplicate = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-26T00:00:01Z",
    )

    assert replay.should_execute is True
    assert replay.run_id != first.run_id
    assert duplicate.should_execute is False
    assert duplicate.run_id == replay.run_id
    assert store.get_automation_run(first.run_id)["status"] == "failed"

    first_row = store.get_automation_run(first.run_id)
    replay_row = store.get_automation_run(replay.run_id)
    assert first_row["run_key"].startswith("lifecycle-automation-execution-v1:")
    assert replay_row["run_key"].startswith("lifecycle-automation-execution-v1:")
    assert replay_row["run_key"] != first_row["run_key"]
    assert json.loads(replay_row["query_context_json"])["semantic_run_key"] == (
        json.loads(first_row["query_context_json"])["semantic_run_key"]
    )


def test_successful_replay_prevents_later_revision_fanout():
    _conn, store, kernel, case_id = _context()
    first = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r0",
    )
    kernel.fail_run(
        run_id=first.run_id,
        failure_code="persistence_failed",
        diagnostics={"persist_failures": 1},
        at=_LATER,
    )
    replay = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r1",
        at="2026-08-26T00:00:00Z",
    )
    evidence = _evidence()
    _succeed(
        kernel,
        replay,
        evidence=(evidence,),
        facts=(_fact(evidence),),
        at="2026-08-26T01:00:00Z",
    )

    later = _reserve(
        kernel,
        case_id,
        policy_version="trusted-lifecycle-automation-v3",
        execution_revision="trusted-lifecycle-execution-r2",
        at="2026-08-27T00:00:00Z",
    )
    assert later.should_execute is False
    assert later.run_id == replay.run_id
    assert len(store.list_automation_runs(case_id)) == 2
```

Also cover:

- a legacy failed row whose query context lacks `execution_revision` replays once;
- a failed row at the current revision does not replay at `+1 day` or `+1 year`;
- `queued`, `running`, `blocked`, `succeeded`, and `cancelled` latest semantic rows retain current behavior;
- due retryable `blocked` rows reuse the same row rather than creating a replay row; and
- two cases with the same fingerprint never cross-select predecessors.

Extend the existing `_succeed` helper with keyword `at: str = _LATER` and pass
that value to `complete_run`; this keeps every persisted timestamp monotonic in
the new replay owners without changing existing callers.

- [ ] **Step 2: Run the replay owners and verify RED**

Run:

```bash
pytest tests/test_security_lifecycle_fact_kernel.py -k "execution_revision or semantic_run or successful_replay" -q
```

Expected before implementation: failure because `reserve_run` does not accept `execution_revision`, and current failed rows remain non-executable under unchanged policy.

- [ ] **Step 3: Implement semantic lookup and execution-run identity**

Keep `automation_run_key` byte-for-byte unchanged as the semantic key. Add an execution key whose payload is exactly:

```python
payload = {
    "execution_revision": execution_revision,
    "predecessor_failed_run_id": predecessor_failed_run_id,
    "semantic_run_key": semantic_run_key,
}
return "lifecycle-automation-execution-v1:" + hashlib.sha256(
    json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
).hexdigest()
```

Inside the existing `BEGIN IMMEDIATE` reservation transaction:

1. select rows with exact `case_id`, `observation_fingerprint_sha256`, `policy_version`, and `mode`, newest by `(created_at, rowid)`;
2. parse only bounded `query_context_json` mappings;
3. retain rows whose `input_evidence_set_sha256` equals the current digest;
4. treat absent `execution_revision` as `unknown`;
5. apply existing due-blocked reuse before replay logic;
6. create a new execution-key row only when the latest semantic row is `failed` under an older/unknown revision; and
7. otherwise return the latest row with `should_execute=False`.

Reject caller-supplied `semantic_run_key`, `execution_revision`, or
`predecessor_failed_run_id` keys as reserved query context. Add the internal
values only after copying caller context so audit identity cannot be spoofed.

Do not update or delete the predecessor failed row. Generate `run_id` from the
execution key. Store the execution key in the `run_key` column for every newly
created row, including first attempts; persist the semantic key only as
`query_context["semantic_run_key"]`. Semantic lookup no longer reads the
`run_key` column: it uses the exact semantic tuple columns plus the persisted
`input_evidence_set_sha256`. Existing rows remain byte-unchanged, including
legacy rows whose `run_key` contains the semantic key. Preserve the unique
`run_key` column and all schema SQL unchanged.

- [ ] **Step 4: Wire the worker constant explicitly**

In `src/security_lifecycle_automation_worker.py`, define the constant beside the imported semantic policy authority and pass it on every `reserve_run` call:

```python
AUTOMATION_EXECUTION_REVISION = "trusted-lifecycle-execution-r1"

claim = kernel.reserve_run(
    case_id=case["case_id"],
    observation_fingerprint_sha256=case["observation_fingerprint_sha256"],
    policy_version=AUTOMATION_POLICY_VERSION,
    mode=mode,
    execution_revision=AUTOMATION_EXECUTION_REVISION,
    query_context=query_context,
    diagnostics=diagnostics,
    at=at,
)
```

Add a worker owner asserting policy stays `trusted-lifecycle-automation-v3`, query context records execution revision `r1`, and a current-revision failed run is not repeatedly selected.

- [ ] **Step 5: Prove execution revision is absent from decision authority**

Create the same completed evidence/facts in two isolated in-memory stores under `r0` and `r1`. Assert:

```python
assert result_r0.decision_provenance_sha256 == result_r1.decision_provenance_sha256
assert persisted_assessment_r0["rule_id"] == persisted_assessment_r1["rule_id"]
assert persisted_assessment_r0["rule_version"] == persisted_assessment_r1["rule_version"]
```

Also assert `execution_revision` does not occur in `src/ticker_identity_transition.py` and is absent from transition approval material returned by the scratch fixture.

- [ ] **Step 6: Run focused tests and commit**

Run:

```bash
pytest tests/test_security_lifecycle_fact_kernel.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_investigation.py tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py tests/test_ticker_identity_transition.py -q
```

Expected: all pass; `src/security_lifecycle_schema.py` remains byte-identical to `11e7a5d4`.

Commit:

```bash
git add src/security_lifecycle_fact_kernel.py src/security_lifecycle_automation_worker.py tests/test_security_lifecycle_fact_kernel.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_investigation.py tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py
git commit -m "fix(lifecycle): replay repaired failed runs"
```

### Task 2: Replace Broad Deadline Harvesting With Closed Grammar

**Files:**
- Modify: `src/security_lifecycle_sec_evidence.py`
- Test: `tests/test_security_lifecycle_sec_evidence.py`

**Interfaces:**
- Consumes: exact source sentences from SEC evidence excerpts.
- Produces: zero or one `SecSourceDeadline` per accepted sentence with rule ID `sec.explicit_transaction_termination_date` and rule version `4`.

- [ ] **Step 1: Write the true directional-extension RED and negative corpus**

Add a table-driven owner that runs each sentence through real `collect_sec_evidence` fixture transport. The required cases are:

```python
cases = {
    "The outside date was extended from March 1, 2026 to June 1, 2026.": (
        "2026-06-01",
    ),
    "The outside date was extended to June 1, 2026.": ("2026-06-01",),
    "The termination date remains 2026-11-01.": ("2026-11-01",),
    "The agreement may be terminated if closing has not occurred by October 1, 2026.": (
        "2026-10-01",
    ),
    "As of June 30, 2026, the outside date had not been extended.": (),
    "The original outside date of March 15, 2025 was extended twice.": (),
    "We do not expect the termination date of December 31, 2027 to apply.": (),
    "The outside date was extended to June 1, 2026 or July 1, 2026.": (),
    "The outside date was extended from March 1, 2026 to June 1, 2026, and further extended to September 1, 2026.": (),
    "extended from March 1, 2026 to June 1, 2026": (),
    "The outside date was extended to June 1, 2026, and the Company will file a Current Report on Form 8-K.": (
        "2026-06-01",
    ),
    "The termination date remains 2026-11-01, and the parties continue to work toward closing.": (
        "2026-11-01",
    ),
}
```

For every emitted row, assert the cited bytes decode to the exact source sentence and the digest matches those bytes.

Before changing production code, add a characterization owner over one fixture
document containing the four rejected deadline sentences plus an oversized
sentence whose deadline phrase/date appear after byte 4096. Run it against the
current implementation and freeze the exact literal set of
`(evidence_id, content_sha256)` pairs. Assert all four short sentences remain in
the resulting excerpts and that the oversized excerpt still contains its
tail-positioned deadline phrase. This owner is GREEN before the deadline repair
and must remain GREEN after it; do not duplicate the legacy matcher in the test.
The short rows exercise `_candidate_sentence`; the oversized row exercises
`_focused_candidate`. Together they prove evidence admission and excerpt
identity remain byte-equivalent while only `SecSourceDeadline` extraction
narrows.

- [ ] **Step 2: Run the grammar owner and verify RED**

Run:

```bash
pytest tests/test_security_lifecycle_sec_evidence.py -k "deadline" -q
```

Expected before implementation: the complete directional outside-date sentence emits both dates, while historical/negated sentences emit false deadlines.

- [ ] **Step 3: Implement one-target closed grammar**

Replace date harvesting inside `_source_deadlines` only with three accepted
target patterns. Keep `_SOURCE_DEADLINE_PHRASE`, `_ANY_MONTH_DATE`, and
`_ANY_ISO_DATE` byte-unchanged for `_candidate_sentence` and
`_focused_candidate`; those paths own existing evidence admission and excerpt
identity under shared `_RULE_VERSION = "3"` and must not narrow.

```python
_SOURCE_DATE_TEXT = rf"(?:{_MONTH_DATE_TEXT}|\d{{4}}-\d{{2}}-\d{{2}})"
_TERMINATE_IF_BY = re.compile(
    rf"\bmay be terminated if\b[^.]{{0,480}}?\bby\s+"
    rf"(?P<date>{_SOURCE_DATE_TEXT})\b",
    re.IGNORECASE,
)
_CURRENT_DEADLINE = re.compile(
    rf"\b(?:outside|termination) date\s+(?:is|shall be|remains)\s+"
    rf"(?P<date>{_SOURCE_DATE_TEXT})\b",
    re.IGNORECASE,
)
_EXTENDED_DEADLINE = re.compile(
    rf"\b(?:outside|termination) date\s+(?:has been|was)\s+extended"
    rf"(?:\s+from\s+{_SOURCE_DATE_TEXT})?\s+to\s+"
    rf"(?P<date>{_SOURCE_DATE_TEXT})\b",
    re.IGNORECASE,
)
_COORDINATE_TARGET = re.compile(
    rf"\A\s*(?:,\s*)?(?:or|and)\s+{_SOURCE_DATE_TEXT}\b",
    re.IGNORECASE,
)
_EXTENSION_ACTION = re.compile(
    rf"\bextended\b(?:\s+from\s+{_SOURCE_DATE_TEXT})?\s+to\s+"
    rf"{_SOURCE_DATE_TEXT}\b",
    re.IGNORECASE,
)
```

For each sentence:

- gather target matches from all three accepted patterns and require exactly one;
- count `_EXTENSION_ACTION` matches across the sentence and emit nothing when
  more than one extension-to-date action exists, including an elliptical
  `further extended to` action;
- apply `_COORDINATE_TARGET.match(sentence[target_match.end("date"):])` and emit
  nothing only when a bare `or|and <DATE>` coordinate immediately follows the
  selected target; an `and`/`or` introducing ordinary prose is not ambiguous;
- normalize the named target only; never collect every date in the sentence; and
- keep the exact sentence as the citation span.

Define in `src/security_lifecycle_sec_evidence.py`:

```python
_SOURCE_DEADLINE_RULE_ID = "sec.explicit_transaction_termination_date"
_SOURCE_DEADLINE_RULE_VERSION = "4"
```

Use those values only for `SecSourceDeadline`. Keep `_RULE_VERSION = "3"` at every existing fact and evidence-locator construction.

- [ ] **Step 4: Prove version isolation and conflict behavior**

Extend the existing deadline test to assert:

```python
assert deadline.rule_version == "4"
assert {fact.rule_version for fact in result.facts} == {"3"}
assert {row.source_locator["rule_version"] for row in result.evidence} == {"3"}
```

The characterization owner from Step 1 must still return its frozen exact
`(evidence_id, content_sha256)` set and preserve all four rejected deadline
sentences in excerpts. Checking only the string value of `rule_version` is not
evidence-identity coverage.

Retain the cross-document behavior: if distinct accepted source deadlines remain after per-sentence parsing, return no deadline and add `sec_evidence_insufficient`.

- [ ] **Step 5: Run SEC tests and commit**

Run:

```bash
pytest tests/test_security_lifecycle_sec_evidence.py -q
```

Commit:

```bash
git add src/security_lifecycle_sec_evidence.py tests/test_security_lifecycle_sec_evidence.py
git commit -m "fix(lifecycle): extract only explicit current deadlines"
```

### Task 3: Validate Deadline Citations At The Atomic Kernel Boundary

**Files:**
- Modify: `src/security_lifecycle_fact_kernel.py`
- Test: `tests/test_security_lifecycle_fact_kernel.py`
- Test: `tests/test_security_lifecycle_automation_worker.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`

**Interfaces:**
- Consumes: current-call evidence IDs, already persisted evidence IDs owned by the same automation run, and blocker contexts containing any source-deadline provenance key.
- Produces: byte-validated blocker context whose evidence ID is the deterministic persisted `sle_*` ID, or `ValueError("blocker_citation")` before terminal state commits.

The complete trigger set is:

```python
_SOURCE_DEADLINE_CONTEXT_FIELDS = frozenset({
    "source_deadline",
    "source_deadline_evidence_id",
    "source_deadline_span_start_byte",
    "source_deadline_span_end_byte",
    "source_deadline_cited_text_sha256",
    "source_deadline_rule_id",
    "source_deadline_rule_version",
})
```

- [ ] **Step 1: Write producer-to-kernel RED tests**

Build one SEC evidence row whose excerpt contains a valid outside-date sentence. Feed the actual `SecSourceDeadline` through `_pending_event_monitoring`, then pass that returned `AutomationBlocker` and the same evidence into `complete_run`.

Own both paths:

```python
@pytest.mark.parametrize(
    ("at", "expected_reason", "retry_at"),
    [
        ("2026-05-01T00:00:00Z", "event_completion_not_confirmed", "2026-05-08T00:00:00Z"),
        ("2026-08-27T00:00:00Z", "not_confirmed_as_of", None),
    ],
)
def test_producer_deadline_citation_crosses_real_kernel(
    at, expected_reason, retry_at
):
    result = kernel.complete_run(
        run_id=claim.run_id,
        evidence=(sec_evidence,),
        facts=(),
        blockers=(scheduler_blocker,),
        decision_tier=None,
        action_readiness=None,
        retry_at=retry_at,
        diagnostics={"sec_attempts": 1},
        at=at,
    )
    stored = store.get_automation_run(result.run_id)["blockers"][0]
    stored_context = json.loads(stored["context_json"])
    assert stored_context["monitoring_reason"] == expected_reason
    assert stored_context["source_deadline_evidence_id"].startswith("sle_")
```

- [ ] **Step 2: Write exact atomic-failure RED matrix**

Parameterize these mutations against the producer-created valid context. For
the UTF-8 owner, prefix the evidence excerpt with `é` and use this exact
mutator so the selected byte is an invalid standalone continuation byte:

```python
def cut_inside_multibyte_source_character(context):
    invalid_byte = "é".encode("utf-8")[1:2]
    context["source_deadline_span_start_byte"] = 1
    context["source_deadline_span_end_byte"] = 2
    context["source_deadline_cited_text_sha256"] = hashlib.sha256(
        invalid_byte
    ).hexdigest()


mutations = {
    "partial_set": lambda c: c.pop("source_deadline_span_end_byte"),
    "missing_evidence": lambda c: c.__setitem__("source_deadline_evidence_id", "missing"),
    "out_of_range": lambda c: c.__setitem__("source_deadline_span_end_byte", 999999),
    "utf8_boundary": cut_inside_multibyte_source_character,
    "forged_hash": lambda c: c.__setitem__("source_deadline_cited_text_sha256", "f" * 64),
    "wrong_rule_id": lambda c: c.__setitem__("source_deadline_rule_id", "sec.other"),
    "wrong_rule_version": lambda c: c.__setitem__("source_deadline_rule_version", "3"),
}
```

Each case must raise `ValueError("blocker_citation")`, leave the run `running`, and leave evidence/fact/blocker tables unchanged. A separate cross-run owner first persists evidence under run A, then proves run B cannot cite run A's persisted ID.

Add closed-shape controls proving:

- an `event_completion_not_confirmed` blocker with no deadline fields remains valid;
- any one deadline field triggers the complete-set requirement even before the deadline;
- kernel-generated `source_conflict` remains
  `{ "fact_types": ["successor_ticker"] }`; and
- `defer_transition_revalidation` still inserts only `{}` for its two accepted codes.

- [ ] **Step 3: Run contract tests and verify RED**

Run:

```bash
pytest tests/test_security_lifecycle_fact_kernel.py -k "blocker_citation or producer_deadline or source_conflict or transition_revalidation" -q
```

Expected before implementation: forged and out-of-range blocker citations are persisted because `_normalize_blockers` currently validates only JSON shape and size.

- [ ] **Step 4: Refactor one shared byte validator**

Extract the existing fact-citation checks into one helper:

```python
def _validate_citation(
    *,
    error_name: str,
    evidence: _EvidenceRow,
    start: object,
    end: object,
    cited_text_sha256: object,
) -> None:
    if type(start) is not int or type(end) is not int or start < 0 or end <= start:
        raise ValueError(error_name)
    encoded = evidence.excerpt.encode("utf-8")
    if end > len(encoded):
        raise ValueError(error_name)
    cited = encoded[start:end]
    try:
        cited.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(error_name) from exc
    digest = _sha256(error_name, cited_text_sha256)
    if hashlib.sha256(cited).hexdigest() != digest:
        raise ValueError(error_name)
```

Make `_normalize_facts` call this helper with `error_name="fact_citation"`; do not retain a second implementation.

- [ ] **Step 5: Normalize and rewrite deadline blocker contexts**

Add a helper that receives `run_id`, structurally normalized blockers, current evidence, and evidence already persisted for that run. It must:

1. build a lookup from current local ID to `(row, deterministic_persisted_id)`;
2. build a lookup from existing persisted ID to `(row, same_id)`;
3. trigger when any deadline field is present;
4. require all seven fields;
5. validate `source_deadline` as an ISO date;
6. require exact rule ID `sec.explicit_transaction_termination_date` and version `4`;
7. call `_validate_citation` with `error_name="blocker_citation"`, the resolved
   evidence row, both source span integers, and the supplied cited-text digest;
8. replace the local evidence ID in copied context with the deterministic persisted ID;
9. require valid ISO `as_of` only when `monitoring_reason == "not_confirmed_as_of"`; and
10. canonicalize the rewritten copy, never mutate the producer object.

Factor the existing persisted evidence-ID formula into one helper and use it for both context rewriting and evidence insertion so the two paths cannot drift.

Move DB-backed existing-evidence/fact reads, deadline validation, conflict synthesis, inserts, and terminal run update under the same existing `BEGIN IMMEDIATE` transaction. Pure normalization of current-call objects may remain before the transaction. Any exception rolls back all writes.

- [ ] **Step 6: Prove worker failure and replay are coupled**

At the worker layer, inject one forged scheduler blocker and assert:

```python
assert first_result["failed"] == 1
assert failed_run["failure_code"] == "persistence_failed"
assert json.loads(failed_run["diagnostics_json"]) == {
    "failures": 1,
    "news_evidence_count": 20,
    "sec_attempts": 7,
}
```

Then construct the same semantic input under execution revision `r2` and assert one new run is selected while the old failed row remains immutable. This owner must fail if either citation validation or replay authority is removed.

- [ ] **Step 7: Run coupled focused tests and commit**

Run:

```bash
pytest tests/test_security_lifecycle_fact_kernel.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_automation_scheduler.py -q
```

Commit:

```bash
git add src/security_lifecycle_fact_kernel.py tests/test_security_lifecycle_fact_kernel.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_automation_scheduler.py
git commit -m "fix(lifecycle): validate deadline blocker citations"
```

### Task 4: Project The Actual Completed-Check Date Truthfully

**Files:**
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Modify: `src/security_lifecycle_disposition.py`
- Modify: `src/tools/security_lifecycle_tools.py`
- Test: `tests/test_security_lifecycle_automation_scheduler.py`
- Test: `tests/test_security_lifecycle_disposition.py`
- Test: `tests/test_security_lifecycle_tools.py`

**Interfaces:**
- Consumes: validated final blocker context with separate `source_deadline` and `as_of` dates.
- Produces:

```python
@dataclass(frozen=True)
class LifecycleDispositionProjection:
    disposition: str
    queue_bucket: str
    reason_code: str
    disposition_as_of: str | None
    last_checked_at: str | None
    next_check_at: str | None
    source_family_status: Mapping[str, str]
```

`disposition_as_of` is derived only, appears in list/detail read payloads, and is `None` outside a validated `not_confirmed_as_of` History projection.

- [ ] **Step 1: Write the overdue scheduler RED**

Change the final-check fixture so the deadline and check date differ:

```python
deadline = replace(deadline, date="2026-04-01", rule_version="4")
final = scheduler._pending_event_monitoring(
    case,
    facts,
    source_family_results={
        "regulator": "available",
        "market_infrastructure": "available",
        "publisher": "available",
    },
    source_deadlines=(deadline,),
    at="2026-08-27T12:00:00Z",
)
assert final.context["source_deadline"] == "2026-04-01"
assert final.context["as_of"] == "2026-08-27"
```

Run:

```bash
pytest tests/test_security_lifecycle_automation_scheduler.py -k "pending_event or completed_check" -q
```

Expected before implementation: `as_of` incorrectly equals `2026-04-01`.

- [ ] **Step 2: Record the actual final-check date**

In `_pending_event_monitoring`, retain the validated deadline as the trigger and replace only the existing assignment:

```python
context["monitoring_reason"] = "not_confirmed_as_of"
context["as_of"] = today.isoformat()
```

Do not derive `as_of` from effective date, filing date, source publication date, or deadline.

- [ ] **Step 3: Write truthful projection RED tests**

Replace the old expected final projection with:

```python
fixture = _case(
    automation_runs=(
        _run(
            blockers=(
                _blocker(
                    "sec_evidence_insufficient",
                    retryable=False,
                    context={
                        "monitoring_reason": "not_confirmed_as_of",
                        "as_of": "2026-08-27",
                        "source_deadline": "2026-04-01",
                        "source_deadline_evidence_id": "sle_deadline",
                        "source_deadline_span_start_byte": 0,
                        "source_deadline_span_end_byte": 64,
                        "source_deadline_cited_text_sha256": "a" * 64,
                        "source_deadline_rule_id": (
                            "sec.explicit_transaction_termination_date"
                        ),
                        "source_deadline_rule_version": "4",
                    },
                ),
            ),
        ),
    ),
)
got = project_lifecycle_disposition(fixture)
assert (
    got.disposition,
    got.queue_bucket,
    got.reason_code,
    got.disposition_as_of,
) == (
    "not_confirmed_yet",
    "history",
    "not_confirmed_as_of",
    "2026-08-27",
)
assert got.next_check_at is None
```

Add owners proving all other dispositions return `disposition_as_of is None`, malformed/missing final `as_of` fails loudly, and source deadline `2026-04-01` never substitutes for completed-check date `2026-08-27`.

- [ ] **Step 4: Implement pure derivation and read exposure**

In the blocked-run branch, map `not_confirmed_as_of` to `not_confirmed_yet + history`. Parse exactly one matching blocker's `context["as_of"]` with `date.fromisoformat`; duplicate conflicting dates or missing/invalid dates raise `ValueError("disposition_as_of")`.

Add `disposition_as_of` to projection construction and
`SecurityLifecycleReadService._cases` output:

```python
"disposition_as_of": projection.disposition_as_of,
```

Add it to `_case_summary` in `src/tools/security_lifecycle_tools.py`. Do not
store it in SQLite and do not modify route filters.

- [ ] **Step 5: Run backend read-contract tests and commit**

Run:

```bash
pytest tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_disposition.py tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py -q
```

Commit:

```bash
git add src/service/security_lifecycle_automation_scheduler.py src/security_lifecycle_disposition.py src/tools/security_lifecycle_tools.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_disposition.py tests/test_security_lifecycle_tools.py
git commit -m "fix(lifecycle): date unconfirmed History honestly"
```

### Task 5: Render Exact Bilingual History Copy

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`
- Modify: `apps/arkscope-web/src/i18n/resources/en/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts`
- Test: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`
- Test: `apps/arkscope-web/src/lifecycle/lifecyclePresentation.test.ts`

**Interfaces:**
- Consumes: `SecurityLifecycleCaseSummary.disposition_as_of: string | null`.
- Produces exact visible copy:

```text
Not confirmed as of 2026-08-27; active checking stopped.
截至 2026-08-27 尚未確認；已停止主動追查。
```

- [ ] **Step 1: Write table and drawer RED tests in both locales**

Add a History fixture:

```typescript
const FINAL_UNCONFIRMED: SecurityLifecycleCaseSummary = Object.assign({}, SUMMARY, {
  disposition: "not_confirmed_yet" as const,
  queue_bucket: "history" as const,
  disposition_reason: "not_confirmed_as_of" as const,
  disposition_as_of: "2026-08-27",
  last_checked_at: "2026-08-27T12:00:00Z",
  next_check_at: null,
});
```

Assert the exact dated sentence appears in the table and drawer for each locale. Also assert the same case does not display `Confirmed complete` / `已確認完成`, opening or rendering it performs zero acknowledgement calls, and a non-final monitoring fixture does not render the stopped-checking sentence.

- [ ] **Step 2: Run frontend owner and verify RED**

Run:

```bash
cd apps/arkscope-web && npm test -- src/lifecycle/LifecycleView.test.tsx
```

Expected before implementation: the exact dated sentence is absent and the
fixture renders only the generic undated reason copy.

- [ ] **Step 3: Add the typed field and translation resources**

Add to `SecurityLifecycleCaseSummary`:

```typescript
disposition_as_of: string | null;
```

Set `disposition_as_of: null` on the shared `SUMMARY` fixture in
`LifecycleView.test.tsx`; individual final-History fixtures override it with an
ISO date. This keeps every existing spread-based case fixture type-complete.

Add resources:

```typescript
// en
notConfirmedAsOfDated: "Not confirmed as of {{date}}; active checking stopped.",

// zh-Hant
notConfirmedAsOfDated: "截至 {{date}} 尚未確認；已停止主動追查。",
```

Keep existing exhaustive labels for the general `not_confirmed_yet` disposition and `not_confirmed_as_of` reason. The dated resource is presentation composition, not a new enum value.

- [ ] **Step 4: Render one shared dated-reason component**

Add a small component used by both table and drawer:

```tsx
function LifecycleDispositionReasonText({
  reason,
  dispositionAsOf,
  locale,
}: {
  reason: SecurityLifecycleDispositionReason;
  dispositionAsOf: string | null;
  locale: LifecycleLocale;
}) {
  const { t } = useTranslation("explore");
  if (reason === "not_confirmed_as_of" && dispositionAsOf) {
    return <>{t(($) => $.lifecycle.dispositionReasons.notConfirmedAsOfDated, {
      date: dispositionAsOf,
    })}</>;
  }
  return <>{lifecycleDispositionReasonLabel(reason, locale)}</>;
}
```

Replace both direct reason-label call sites with this component. Continue rendering `last_checked_at` independently; do not use it as a fallback for a missing `disposition_as_of`.

- [ ] **Step 5: Run focused frontend gates and commit**

Run:

```bash
cd apps/arkscope-web && npm test -- src/lifecycle/LifecycleView.test.tsx src/lifecycle/lifecyclePresentation.test.ts
cd apps/arkscope-web && npm run typecheck
cd apps/arkscope-web && npm run check:i18n-literals
```

Commit:

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/lifecycle/LifecycleView.tsx apps/arkscope-web/src/i18n/resources/en/explore.ts apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx apps/arkscope-web/src/lifecycle/lifecyclePresentation.test.ts
git commit -m "fix(web): show truthful lifecycle History dates"
```

### Task 6: Rebuild Offline Admission From The Repaired Seams

**Files:**
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/README.md`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/commands.txt`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/mutation-ledger.json`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/run_mutations.py`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/offline-authority.json`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/capture_offline_authority.py`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/schema-base.json`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/schema-head.json`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/schema-comparison.json`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/capture_profile_schema.py`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/compare_profile_schema.py`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/backend-focused-a.nodes`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/backend-focused-b.nodes`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/backend-full-a.txt`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/backend-full-b.txt`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/frontend-full.txt`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/frontend-typecheck.txt`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/frontend-i18n-literals.txt`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/frontend-build.txt`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/browser-matrix.json`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/run_browser_matrix.py`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/browser/` screenshot directory populated only by the matrix script.
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/verification-summary.json`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/seal_packet.py`
- Create: `docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/SHA256SUMS`

**Interfaces:**
- Consumes: Tasks 1-5 as one inseparable product authority.
- Produces: a self-hashed offline packet that can support independent review but grants no live authority.

- [ ] **Step 1: Run and record named mutation owners**

Apply and restore each mutation independently:

1. remove deadline citation hash comparison;
2. validate deadline citations only when reason is `not_confirmed_as_of`;
3. accept a partial deadline provenance set;
4. bump shared SEC `_RULE_VERSION` from `3` to `4` instead of the deadline-only constant;
5. select the `from` date in a directional extension;
6. accept a negated or historical date sentence;
7. backdate final `as_of` to `source_deadline`;
8. map `not_confirmed_as_of` back to `confirmed_effective`;
9. omit `disposition_as_of` from the read summary;
10. render generic confirmed-complete copy for final unconfirmed History;
11. include execution revision in decision provenance or transition authority;
12. replay a failed row repeatedly at the same execution revision;
13. replay a succeeded semantic run after only execution revision changes;
14. let `source_conflict` or transition-revalidation contexts acquire deadline citation fields outside the shared validator;
15. narrow `_candidate_sentence` or `_focused_candidate` to the new deadline grammar instead of retaining the three legacy patterns; and
16. reject an accepted target merely because any `and` or `or` appears after its date instead of requiring a bare coordinated date target.

Each mutation records exact owner node IDs, failing counts, unexpected owner drift, and SHA-256 of every restored product file. All mutations must be killed and every file restored byte-identically before continuing.

- [ ] **Step 2: Capture scratch replay and citation authority**

In temporary SQLite databases only, record:

- one legacy failed row with absent revision;
- one `r1` replay under unchanged policy v3;
- immutable predecessor bytes before/after;
- one successful replacement that prevents `r2` fan-out;
- equal decision provenance under `r0` and `r1`;
- valid pre-deadline and final producer-to-kernel citations;
- forged-citation rollback with zero evidence/fact/blocker rows;
- overdue deadline `2026-04-01`, completed check `2026-08-27`;
- `not_confirmed_yet + history + disposition_as_of=2026-08-27`; and
- zero transition preview, approval, apply, reverse, or acknowledgement calls.

The report authority block is exactly:

```json
{
  "scope": "offline_fixture_and_scratch_only",
  "provider_calls": 0,
  "production_database_reads": 0,
  "production_database_writes": 0,
  "production_database_preflights": 0,
  "production_database_backups": 0,
  "production_database_migrations": 0,
  "production_database_restores": 0,
  "app_restarts": 0,
  "merges": 0,
  "pushes": 0
}
```

- [ ] **Step 3: Run focused backend gates twice with isolated temp roots**

Run:

```bash
pytest --collect-only -q tests/test_security_lifecycle_fact_kernel.py tests/test_security_lifecycle_sec_evidence.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_disposition.py tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py tests/test_ticker_identity_transition.py > docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/backend-focused-a.nodes
pytest --collect-only -q tests/test_security_lifecycle_fact_kernel.py tests/test_security_lifecycle_sec_evidence.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_disposition.py tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py tests/test_ticker_identity_transition.py > docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/backend-focused-b.nodes
pytest --basetemp=/tmp/arkscope-honesty-focused-a tests/test_security_lifecycle_fact_kernel.py tests/test_security_lifecycle_sec_evidence.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_disposition.py tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py tests/test_ticker_identity_transition.py -q
pytest --basetemp=/tmp/arkscope-honesty-focused-b tests/test_security_lifecycle_fact_kernel.py tests/test_security_lifecycle_sec_evidence.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_disposition.py tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py tests/test_ticker_identity_transition.py -q
cmp docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/backend-focused-a.nodes docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/backend-focused-b.nodes
```

Expected: identical node counts and zero failures. Capture collection node IDs separately and compare them byte-for-byte.

- [ ] **Step 4: Run complete backend and frontend gates**

Run two isolated backend passes:

```bash
set -o pipefail
pytest --basetemp=/tmp/arkscope-honesty-full-a -q | tee docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/backend-full-a.txt
pytest --basetemp=/tmp/arkscope-honesty-full-b -q | tee docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/backend-full-b.txt
```

Run frontend gates:

```bash
cd apps/arkscope-web
set -o pipefail
npm test | tee ../../docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/frontend-full.txt
npm run typecheck | tee ../../docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/frontend-typecheck.txt
npm run check:i18n-literals | tee ../../docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/frontend-i18n-literals.txt
npm run build | tee ../../docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair/frontend-build.txt
```

Record fresh counts. Do not copy the earlier `4475 passed / 12 skipped` or `106 files / 1239 passed` counts into the new authority.

- [ ] **Step 5: Prove schema and protected authority are unchanged**

Compare exact `sqlite_master`, `PRAGMA table_info`, and index SQL between product base `11e7a5d4` and repaired head. Require:

```text
owned sqlite_master diff = empty
PRAGMA table_info diff = empty
new mutable disposition columns = 0
startup DDL changes = 0
security_lifecycle_schema.py byte diff = empty
ticker_identity_transition.py execution_revision references = 0
AUTOMATION_POLICY_VERSION = trusted-lifecycle-automation-v3
SEC shared _RULE_VERSION = 3
deadline-only rule version = 4
```

Any schema or transition-authority drift is a hard stop requiring a new reviewed design; tests cannot waive it.

- [ ] **Step 6: Run the bilingual browser matrix**

Extend the existing offline Lifecycle fixture matrix with final-unconfirmed History. Capture desktop and mobile in English and Traditional Chinese. Assert:

```python
assert external_requests == 0
assert write_requests == 0
assert render_acknowledgements == 0
assert console_errors == []
assert page_errors == []
assert overlap_count == 0
assert clipped_text_count == 0
assert "Confirmed complete" not in english_final_unconfirmed_text
assert "已確認完成" not in zh_hant_final_unconfirmed_text
assert "Not confirmed as of 2026-08-27; active checking stopped." in english_final_unconfirmed_text
assert "截至 2026-08-27 尚未確認；已停止主動追查。" in zh_hant_final_unconfirmed_text
```

Rendering and tab changes must not call acknowledgement endpoints.

- [ ] **Step 7: Seal and verify the packet**

Generate `SHA256SUMS` over every payload except itself, run:

```bash
cd docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair && sha256sum -c SHA256SUMS
```

Record the SHA-256 of `SHA256SUMS` separately in the final closeout. The manifest file set must equal the on-disk payload file set exactly.

The README must state these remaining limitations:

- no provider call or production scheduler replay was performed;
- operator-triggered replay remains unimplemented;
- broader legal-language extraction remains precision-first and intentionally incomplete;
- no production migration is needed because schema authority is unchanged; and
- App restart, merge, push, and the Priority Map GREEN entry remain separate authorization events.

- [ ] **Step 8: Commit offline admission evidence and stop at hard gates**

Commit:

```bash
git add docs/superpowers/evidence/2026-08-27-lifecycle-honesty-repair
git commit -m "test(lifecycle): seal honesty repair admission"
```

Verify the branch is clean, linear, unmerged, and absent from the remote. Do not restart the App, read production DBs, merge, or push. Present the exact product/test authority commit, packet manifest digest, fresh gate counts, and limitations for independent review.

## Post-Admission Authorization Boundary

After independent GREEN, request separate authorization for merge and App restart. No live schema migration should be requested because this plan requires an exact empty schema diff. Reconcile the user-owned Priority Map only on `master` after merge authorization: preserve the dated RED entry and append a separate GREEN closeout that explicitly supersedes it. Push remains user-operated.
