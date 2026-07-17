# IBKR News 10172 Retry Recalibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Use
> `superpowers:test-driven-development` for every behavior change and
> `superpowers:verification-before-completion` before review-ready claims.
> Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** PLAN REVIEW PENDING — authority spec approved; implementation has
> not started and production still uses the live three-attempt policy.

**Goal:** Stop spending a third IBKR Gateway body request after two persisted
typed `10172` outcomes, reconcile already-known repeated failures without a
network call, and preserve every existing entitlement, privacy, scheduling,
and fresh-ingestion contract.

**Architecture:** `NormalizedNewsStore` remains the sole body-state authority.
The typed `10172` transition changes from terminal-at-three to
terminal-at-two. A new explicit, transactionally idempotent store method
terminalizes only currently entitled IBKR rows that already have repeated
typed evidence. The isolated worker invokes it under one short
`market_write_lock` after successful provider discovery and before retry
selection. The returned row count is internal evidence only and is discarded
by the worker; no child/parent/API telemetry contract changes.

**Tech Stack:** Python 3.11, SQLite, the existing normalized-news store/writer,
the isolated IBKR subprocess boundary, `ib_insync`, pytest, and the existing
no-PostgreSQL smoke harness.

## Authority and Behavioral Base

- Approved authority:
  `docs/superpowers/specs/2026-07-17-ibkr-news-10172-retry-recalibration-design.md`.
- Behavioral base: `4e7bb24` (`docs: recalibrate IBKR news 10172 retry`). The
  spec/map/plan approval commits are docs-only and do not change test behavior.
- Implementation begins only after independent review clears this plan. Create
  the branch/worktree from that review-cleared docs tip and record both the
  actual branch base and behavioral base in this plan's implementation ledger.
- Current collection baseline is `4352` backend tests. The focused baseline is
  `185` across:
  - `tests/test_news_normalized_store.py`: `25`;
  - `tests/test_news_normalized_retry_queue.py`: `9`;
  - `tests/test_normalized_ibkr_worker.py`: `28`;
  - `tests/test_news_normalized_ibkr_adapter.py`: `20`; and
  - `tests/test_data_scheduler.py`: `103`.
- Reviewed accounting target is exactly `+7/-0`: retry queue `+4`, isolated
  worker `+3`, and no net change for 1:1 policy-test renames. Expected focused
  collection is `192`; expected full backend collection is `4359`.

## Locked Decisions

1. **Two total typed attempts.** First typed `10172` is `failed` with a six-hour
   retry. Second typed `10172` is terminal `unavailable`. Attempts count is the
   persisted total, not a per-run counter.
2. **No first-attempt terminal shortcut.** The one delayed hedge remains.
3. **Explicit reconciliation only.** Do not hide mutation in schema creation,
   `NormalizedNewsStore.__init__`, status reads, queue reads, scheduler polling,
   or frontend rendering.
4. **Discovery before reconciliation.** The worker must successfully discover
   provider codes before mutating rows. If all provider-work budgets are zero,
   discovery remains skipped and reconciliation also remains skipped.
5. **Entitlement remains orthogonal.** Reconciliation receives the strict
   discovered provider-code set and updates only rows whose stored publisher is
   currently present. A successful empty set updates zero rows. `None` remains
   store-level compatibility meaning "no entitlement filter", but the live
   worker must not pass `None` after a discovery failure.
6. **Short write boundary.** Provider discovery and all Gateway waits happen
   outside `market_write_lock`. Reconciliation alone runs under one short
   market lock and one SQLite write transaction. Retry selection follows after
   that lock is released. Existing writer calls keep their own short lock
   factory.
7. **Fail closed.** Reconciliation lock/SQL failure aborts the worker before
   retry selection, body calls, or fresh headline calls. No attempt is consumed
   and no empty backlog is fabricated.
8. **No new telemetry surface.** The store method returns an integer count for
   unit tests, copied-DB evidence, and optional internal debugging. The worker
   deliberately ignores it. Do not add it to worker result data,
   `sanitize_worker_result`, child stdout, parent scheduler allowlists,
   scheduler state, API DTOs, Settings, or logs.
9. **No schema or queue change.** Reuse `news_articles` and
   `news_article_bodies`; add no table, column, migration, continuation, or
   second authority.
10. **No runtime-budget drift.** Keep retry budget `25`, first backoff six
    hours, fresh limits, scheduler cadence, manual `Run` semantics, and retry
    ordering unchanged.
11. **Run status remains truthful.** A second-10172 request made in the current
    run is `partial`; terminal history alone does not make later runs partial.
12. **Explicit recovery remains the only recovery.** Do not alter
    `allow_terminal_recovery=True` semantics.
13. **No UI scope.** The compact scheduler row gains no terminal-history count
    and no force-retry action. Frontend-owned files must remain byte-identical.
14. **No provider identity leak.** Provider codes are allowed only inside the
    existing child/store/provider boundary. Tests and copied-DB output report
    aggregate counts and booleans, never provider article IDs, provider codes,
    titles, bodies, or raw provider errors.

## Required Store Interface

Add this public method to `NormalizedNewsStore`:

```python
def reconcile_ibkr_10172_retry_policy(
    self,
    *,
    now: datetime,
    available_provider_codes: Iterable[str] | None,
) -> int:
    """Terminalize repeated typed IBKR-unavailable evidence.

    Returns the number of rows changed. The return value is internal-only and
    must not cross the isolated worker's sanitized output boundary.
    """
```

The method must:

- reject an already-active caller transaction with `RuntimeError`, matching
  the deterministic queue-read discipline;
- normalize `now` through `_retry_now_iso()`;
- derive the publisher predicate through the existing
  `_provider_entitlement_predicate()` helper;
- run `BEGIN IMMEDIATE`, one scoped `UPDATE`, and commit;
- rollback on every exception and re-raise the original error;
- return `cursor.rowcount` as a non-negative integer; and
- leave `self.conn.in_transaction is False` on success and failure.

The update predicate is exactly:

```sql
a.source = 'ibkr'
AND b.body_status = 'failed'
AND b.last_error_code = 10172
AND b.fetch_attempts >= 2
AND <publisher is in the supplied entitlement set>
```

The only assignments are:

```sql
body_status = 'unavailable'
next_retry_at = NULL
unavailable_at = COALESCE(NULLIF(TRIM(last_attempt_at), ''), :now)
```

Do not rewrite attempts, last attempt/error evidence, body payload/hash fields,
article metadata, ticker relations, provider identity, or fetched timestamps.

## File Map

- Modify `src/news_normalized/store.py`: two-attempt constant/transition and
  explicit idempotent reconciliation method.
- Modify `src/news_normalized/ibkr_cli.py`: short-lock reconciliation after
  successful provider discovery and before retry selection; discard count.
- Modify `tests/test_news_normalized_store.py`: 1:1 policy-test evolution and
  explicit-recovery terminal shape.
- Modify `tests/test_news_normalized_retry_queue.py`: four reconciliation
  contracts.
- Modify `tests/test_normalized_ibkr_worker.py`: fake-store interface sweep,
  lock/order/failure/privacy contracts, and second-attempt run semantics.
- Verify without modifying `tests/test_news_normalized_ibkr_adapter.py` and
  `tests/test_data_scheduler.py`.
- Modify at review-ready only: this plan, the authority spec status, and
  `docs/design/PROJECT_PRIORITY_MAP.md`.
- Modify only after reviewed merge: older three-attempt authority wording in
  `docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md` and the
  supersession note in
  `docs/superpowers/plans/2026-07-15-ibkr-news-durable-body-retry.md`.

## Must-Not-Modify Boundaries

- `src/news_normalized/schema.py`
- `src/news_normalized/writer.py`
- `src/news_normalized/models.py`
- `src/news_normalized/ibkr_adapter.py`
- `src/service/data_scheduler.py`
- `apps/arkscope-web/**`
- provider configuration, scheduler cadence, Gateway client IDs, headline
  catch-up, pricing, portfolio, agent/tool, order, or trading code
- real `data/market_data.db` during pre-merge gates

If implementation needs any listed owner, stop and return to design review.

---

### Task 0: Create an Isolated Worktree and Freeze the Baseline

**Files:** none

- [ ] **Step 1: Confirm the parent worktree is safe**

```bash
git status --short --branch
git log -1 --oneline
git worktree list
```

Expected: the user's existing `config/tickers_core.json` modification may be
present in the main worktree. Do not stage, copy, reset, or otherwise modify it.

- [ ] **Step 2: Create the implementation worktree from the review-cleared tip**

```bash
git worktree add .worktrees/ibkr-news-10172-recalibration \
  -b codex/ibkr-news-10172-recalibration
cd .worktrees/ibkr-news-10172-recalibration
git status --short --branch
git rev-parse HEAD
```

Record this hash as the plan/branch base. Record `4e7bb24` separately as the
behavioral A/B base.

- [ ] **Step 3: Reproduce the collection baseline before edits**

```bash
pytest --collect-only -q \
  tests/test_news_normalized_store.py \
  tests/test_news_normalized_retry_queue.py \
  tests/test_normalized_ibkr_worker.py \
  tests/test_news_normalized_ibkr_adapter.py \
  tests/test_data_scheduler.py
pytest --collect-only -q
```

Expected summaries: `185` focused and `4352` full. If collection differs before
code changes, stop and reconcile the ledger rather than carrying a false base.

- [ ] **Step 4: Run the narrow GREEN baseline**

```bash
pytest -q \
  tests/test_news_normalized_store.py \
  tests/test_news_normalized_retry_queue.py \
  tests/test_normalized_ibkr_worker.py
```

Expected: `62 passed` (`25 + 9 + 28`). Record elapsed time and warnings.

---

### Task 1: Change Typed 10172 from Terminal-at-Three to Terminal-at-Two

**Files:**
- Modify `tests/test_news_normalized_store.py`
- Modify `tests/test_normalized_ibkr_worker.py`
- Modify `src/news_normalized/store.py`

- [ ] **Step 1: Evolve the two store policy tests without changing collection**

Rename and strengthen the existing cases:

```python
def test_second_10172_becomes_terminal_unavailable(store, conn, monkeypatch):
    article = candidate("DJ-N$retry")
    result = store.upsert(article)
    conn.execute(
        "UPDATE news_article_bodies SET body_status='failed',fetch_attempts=1 "
        "WHERE article_id=?",
        (result.article_id,),
    )
    monkeypatch.setattr(
        "src.news_normalized.store._now", lambda: "2026-06-29T00:00:00Z"
    )

    store.update_body(
        article,
        BodyCandidate(
            status=BodyStatus.FAILED,
            error="IBKR news article unavailable (10172)",
            error_code=10172,
        ),
    )

    row = conn.execute(
        "SELECT body_status,fetch_attempts,last_error_code,next_retry_at,"
        "unavailable_at FROM news_article_bodies WHERE article_id=?",
        (result.article_id,),
    ).fetchone()
    assert tuple(row) == (
        "unavailable",
        2,
        10172,
        None,
        "2026-06-29T00:00:00Z",
    )
```

Rename `test_10172_before_third_attempt_sets_six_hour_retry` to
`test_first_10172_sets_six_hour_retry`; retain its exact attempts-one and
`+6h` assertions. Change
`test_unavailable_recovers_only_through_explicit_reprobe` to seed terminal
attempts `2`, not `3`, while preserving the denied-normal-update and
allowed-explicit-reprobe assertions.

- [ ] **Step 2: Add the end-to-end worker outcome test**

Add exactly one new test:

```python
def test_second_10172_run_is_partial_then_terminal_history_does_not_degrade_next_run(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "market_data.db"
    article_id = _seed_body_row(
        db_path,
        "second-10172",
        status="failed",
        attempts=1,
        next_retry_at="2000-01-01T00:00:00Z",
    )
    provider = _WorkerProvider(
        {"AAPL": []},
        {
            "DJ-N$second-10172": BodyCandidate(
                status=BodyStatus.FAILED,
                error="IBKR news article unavailable (10172)",
                error_code=10172,
            )
        },
    )
    monkeypatch.setattr(
        "src.news_normalized.store._now", lambda: "2026-07-17T00:00:00Z"
    )

    first = _run_real_worker(monkeypatch, db_path, provider)
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT body_status,fetch_attempts,next_retry_at FROM "
        "news_article_bodies WHERE article_id=?",
        (article_id,),
    ).fetchone()
    conn.close()
    second = _run_real_worker(monkeypatch, db_path, provider)

    assert first["status"] == "partial"
    assert first["retry_status"] == "partial"
    assert first["body_backlog"]["due_now"] == 0
    assert first["body_backlog"]["scheduled_later"] == 0
    assert tuple(row) == ("unavailable", 2, None)
    assert provider.body_calls == ["DJ-N$second-10172"]
    assert second["status"] == "succeeded"
```

The same provider object is intentional: the final call-list assertion proves
the terminal row was not requested a third time.

- [ ] **Step 3: Run RED and inspect the reason**

```bash
pytest -q \
  tests/test_news_normalized_store.py::test_second_10172_becomes_terminal_unavailable \
  tests/test_normalized_ibkr_worker.py::test_second_10172_run_is_partial_then_terminal_history_does_not_degrade_next_run
```

Expected RED: current code leaves attempt two as `failed` with a future retry;
the failure must not be fixture setup, connection, or timestamp parsing.

- [ ] **Step 4: Implement one named policy constant and use it once**

Near `_TERMINAL` in `src/news_normalized/store.py`, add:

```python
_IBKR_10172_MAX_ATTEMPTS = 2
```

Replace the literal threshold only:

```python
if body.error_code == 10172:
    unavailable = attempts >= _IBKR_10172_MAX_ATTEMPTS
```

Do not alter generic failures, first backoff, terminal conflict handling, or
explicit recovery.

- [ ] **Step 5: Run GREEN and the entire store/worker pair**

```bash
pytest -q \
  tests/test_news_normalized_store.py \
  tests/test_normalized_ibkr_worker.py
```

Expected: `54 passed` (`25 + 29`).

- [ ] **Step 6: Commit the state-machine change**

```bash
git add src/news_normalized/store.py \
  tests/test_news_normalized_store.py \
  tests/test_normalized_ibkr_worker.py
git commit -m "fix: bound IBKR 10172 retries to two attempts"
```

---

### Task 2: Add Idempotent Existing-Row Reconciliation

**Files:**
- Modify `tests/test_news_normalized_retry_queue.py`
- Modify `src/news_normalized/store.py`

- [ ] **Step 1: Extend the local test helper without weakening existing cases**

Allow `_set_body()` to set optional typed evidence fields while retaining its
existing defaults:

```python
def _set_body(
    conn,
    article_id,
    *,
    status,
    attempts=0,
    next_retry_at=None,
    last_attempt_at=None,
    last_error=None,
    last_error_code=None,
    unavailable_at=None,
):
    conn.execute(
        "UPDATE news_article_bodies SET body_status=?,fetch_attempts=?,"
        "next_retry_at=?,last_attempt_at=?,last_error=?,last_error_code=?,"
        "unavailable_at=? WHERE article_id=?",
        (
            status,
            attempts,
            next_retry_at,
            last_attempt_at,
            last_error,
            last_error_code,
            unavailable_at,
            article_id,
        ),
    )
    conn.commit()
```

Update the existing entitlement terminal fixture from attempts `3` to `2`.
Its behavior and test ID remain unchanged.

- [ ] **Step 2: Add four RED reconciliation contracts**

Add exactly these tests:

1. `test_reconcile_ibkr_10172_policy_terminalizes_matching_rows_and_preserves_evidence`
   - seed one entitled IBKR `failed / attempts=2 / error_code=10172` row;
   - set `last_attempt_at`, `next_retry_at`, sanitized `last_error`, and sentinel
     raw/hash/retrieval fields;
   - snapshot the complete article row and complete body row;
   - call reconciliation with `available_provider_codes={"DJ-N"}`;
   - assert return `1`, article row byte-equivalent, and body row differs only
     in `body_status`, `next_retry_at`, and `unavailable_at`;
   - assert `unavailable_at == last_attempt_at`, not reconciliation time.
2. `test_reconcile_ibkr_10172_policy_ignores_other_states_sources_and_entitlement`
   - seed a currently blocked `FLY` typed row, a `polygon` typed row, generic
     error row, attempts-one row, pending row, fetched row, and already-terminal
     row;
   - reconcile with only `DJ-N` available;
   - assert every complete row snapshot remains identical and count is `0`.
3. `test_reconcile_ibkr_10172_policy_is_idempotent_and_removes_backlog`
   - seed one matching row with due `next_retry_at` and missing/blank
     `last_attempt_at`;
   - assert backlog due count is `1` before;
   - reconcile at `NOW`, assert count `1`, fallback `unavailable_at` equals the
     normalized `NOW`, and due/scheduled counts become `0`;
   - run again and assert count `0` plus byte-identical body state.
4. `test_reconcile_ibkr_10172_policy_rejects_active_transaction_and_rolls_back_failure`
   - begin a caller transaction and assert `RuntimeError` without ending it;
   - rollback the caller transaction;
   - install a temporary `BEFORE UPDATE` trigger using `RAISE(ABORT, ...)`;
   - assert the method raises `sqlite3.IntegrityError`, leaves no active
     transaction, and preserves the complete matching body row.

The tests may use provider-code fixture strings internally, but assertion
messages and any copied-DB/report output must not print real provider values.

- [ ] **Step 3: Run RED**

```bash
pytest -q tests/test_news_normalized_retry_queue.py -k reconcile
```

Expected: four failures because the explicit method does not exist. No test may
fail because schema construction or a status read unexpectedly mutates rows.

- [ ] **Step 4: Implement the explicit transaction**

Use the existing entitlement helper and an `EXISTS` subquery so the update is
one statement:

```python
def reconcile_ibkr_10172_retry_policy(
    self,
    *,
    now: datetime,
    available_provider_codes: Iterable[str] | None,
) -> int:
    if self.conn.in_transaction:
        raise RuntimeError("10172 reconciliation requires no active transaction")

    now_iso = self._retry_now_iso(now)
    entitlement_sql, entitlement_params = self._provider_entitlement_predicate(
        available_provider_codes,
        publisher_sql="a.publisher",
    )
    try:
        self.conn.execute("BEGIN IMMEDIATE")
        cursor = self.conn.execute(
            "UPDATE news_article_bodies AS b SET "
            "body_status='unavailable',next_retry_at=NULL,"
            "unavailable_at=COALESCE(NULLIF(TRIM(last_attempt_at),''),?) "
            "WHERE b.body_status='failed' "
            "AND b.last_error_code=10172 "
            "AND b.fetch_attempts>=? "
            "AND EXISTS ("
            " SELECT 1 FROM news_articles AS a"
            " WHERE a.id=b.article_id AND a.source='ibkr'"
            f" AND ({entitlement_sql})"
            ")",
            (
                now_iso,
                _IBKR_10172_MAX_ATTEMPTS,
                *entitlement_params,
            ),
        )
        changed = max(int(cursor.rowcount), 0)
        self.conn.commit()
    except Exception:
        if self.conn.in_transaction:
            self.conn.rollback()
        raise
    assert self.conn.in_transaction is False
    return changed
```

The installed SQLite `3.37.2` was directly probed with this target-alias plus
correlated-`EXISTS` shape and updated exactly one row. Keep this one-statement
form; do not split the mutation into a read loop or multiple updates.

- [ ] **Step 5: Run GREEN and queue regressions**

```bash
pytest -q \
  tests/test_news_normalized_store.py \
  tests/test_news_normalized_retry_queue.py
```

Expected: `38 passed` (`25 + 13`). Verify the idempotence test's second return
is exactly zero.

- [ ] **Step 6: Commit reconciliation**

```bash
git add src/news_normalized/store.py tests/test_news_normalized_retry_queue.py
git commit -m "fix: reconcile repeated IBKR body unavailability"
```

---

### Task 3: Invoke Reconciliation at the Isolated Worker Choke Point

**Files:**
- Modify `tests/test_normalized_ibkr_worker.py`
- Modify `src/news_normalized/ibkr_cli.py`

- [ ] **Step 1: Sweep every fake store for the new required interface**

There are three standalone fake `Store` classes in
`tests/test_normalized_ibkr_worker.py` (current neighborhoods near lines 289,
414, and 666). Add the exact method to each. Do not use `getattr()` or optional
duck typing in production to preserve old fake shapes.

Use event/call assertions where relevant; otherwise return zero:

```python
def reconcile_ibkr_10172_retry_policy(
    self, *, now, available_provider_codes
):
    assert available_provider_codes == frozenset({"DJ-N"})
    return 0
```

Subclasses of the real `NormalizedNewsStore` inherit the method and need no
compatibility shim.

- [ ] **Step 2: Evolve the existing lock/order tests to the new contract**

In `test_ibkr_worker_standalone_acquires_gateway_lock_before_market_lock`:

- append `"reconcile"` from the fake store method;
- retain the one shared Gateway-lock assertion;
- assert the relevant strict subsequence is:

```python
assert events.index("providers") < events.index("store")
assert events.index("store") < events.index("market_enter")
assert events.index("market_enter") < events.index("reconcile")
assert events.index("reconcile") < events.index("market_exit")
assert events.index("market_exit") < events.index("write")
```

In `test_ibkr_worker_passes_market_lock_factory_without_outer_write_lock`,
replace the obsolete never-enter lock with a recording context manager. Assert:

- the market lock is active during `reconcile...`;
- it is inactive when `select_ibkr_body_retries()` begins;
- it is inactive when `write_news_batch()` begins; and
- the same factory is still passed as `write_lock_factory` for the writer's own
  short commits.

This explicitly rejects wrapping provider discovery, queue reads, or the whole
writer in the new outer lock.

- [ ] **Step 3: Add two new RED worker tests**

Add exactly:

1. `test_worker_reconciliation_failure_stops_before_retry_or_fresh_calls`
   - subclass the real store and raise `sqlite3.OperationalError` from
     reconciliation;
   - use a provider with both retry and fresh candidates;
   - assert `_run_worker()` raises, provider discovery occurred, but provider
     metadata/body events remain empty;
   - assert no body attempt or backlog result was fabricated and the DB row is
     unchanged.
2. `test_worker_reconciliation_count_stays_inside_child`
   - make the fake store return sentinel `987654321` and increment a call
     counter;
   - assert reconciliation is called once with the strict discovered set;
   - assert the raw `_run_worker()` result and `sanitize_worker_result(result)`
     contain neither the sentinel nor any reconciliation/count key;
   - assert selection and fresh work still occur normally.

Together with Task 1's new runtime test, worker collection grows from `28` to
`31`.

- [ ] **Step 4: Run RED**

```bash
pytest -q \
  tests/test_normalized_ibkr_worker.py::test_ibkr_worker_standalone_acquires_gateway_lock_before_market_lock \
  tests/test_normalized_ibkr_worker.py::test_ibkr_worker_passes_market_lock_factory_without_outer_write_lock \
  tests/test_normalized_ibkr_worker.py::test_worker_reconciliation_failure_stops_before_retry_or_fresh_calls \
  tests/test_normalized_ibkr_worker.py::test_worker_reconciliation_count_stays_inside_child
```

Expected: failures because `_run_worker()` never invokes reconciliation. The
failure test must demonstrate that current code proceeds into provider work.

- [ ] **Step 5: Add the bounded worker call**

Immediately after `store = NormalizedNewsStore(conn)` and before
`retry_query_failed = False`, add:

```python
if available_provider_codes is not None:
    with market_write_lock():
        store.reconcile_ibkr_10172_retry_policy(
            now=datetime.now(timezone.utc),
            available_provider_codes=available_provider_codes,
        )
```

Do not assign the return value. Do not catch exceptions around this block. The
existing `main()` sanitizer is the correct failure boundary. Keep the existing
queue-read exception policy unchanged: only queue selection/summary failures
may degrade to partial and continue fresh work.

- [ ] **Step 6: Run GREEN and all worker/adapter contracts**

```bash
pytest -q \
  tests/test_normalized_ibkr_worker.py \
  tests/test_news_normalized_ibkr_adapter.py
```

Expected: `51 passed` (`31 + 20`). Confirm the existing zero-budget module
startup test does not enter provider discovery or reconciliation.

- [ ] **Step 7: Commit worker orchestration**

```bash
git add src/news_normalized/ibkr_cli.py tests/test_normalized_ibkr_worker.py
git commit -m "fix: reconcile IBKR body retries before selection"
```

---

### Task 4: Run Regression, Privacy, and Copied-DB Gates

**Files:**
- Do not modify production code unless a RED-first defect is found.
- Update this plan's ledger after evidence is complete.

- [ ] **Step 1: Run exact focused verification and accounting**

```bash
pytest --collect-only -q \
  tests/test_news_normalized_store.py \
  tests/test_news_normalized_retry_queue.py \
  tests/test_normalized_ibkr_worker.py \
  tests/test_news_normalized_ibkr_adapter.py \
  tests/test_data_scheduler.py
pytest -q \
  tests/test_news_normalized_store.py \
  tests/test_news_normalized_retry_queue.py \
  tests/test_normalized_ibkr_worker.py \
  tests/test_news_normalized_ibkr_adapter.py \
  tests/test_data_scheduler.py
```

Expected: collection `192`; all `192 passed`. Verify collection diff against a
clean archive of `4e7bb24` is exactly the seven named additions and zero
removals. Test renames must be 1:1 intent-preserving replacements, not hidden
losses.

- [ ] **Step 2: Run state-machine and regression focus explicitly**

```bash
pytest -q \
  tests/test_news_normalized_store.py::test_first_10172_sets_six_hour_retry \
  tests/test_news_normalized_store.py::test_second_10172_becomes_terminal_unavailable \
  tests/test_news_normalized_store.py::test_unavailable_recovers_only_through_explicit_reprobe \
  tests/test_news_normalized_retry_queue.py \
  tests/test_normalized_ibkr_worker.py::test_retryable_10172_reports_partial_and_scheduled_backlog \
  tests/test_normalized_ibkr_worker.py::test_second_10172_run_is_partial_then_terminal_history_does_not_degrade_next_run \
  tests/test_normalized_ibkr_worker.py::test_retry_and_fresh_limits_are_independent \
  tests/test_normalized_ibkr_worker.py::test_worker_does_not_call_body_for_unentitled_provider_and_reports_count \
  tests/test_normalized_ibkr_worker.py::test_worker_provider_discovery_failure_performs_no_retry_or_fresh_calls
```

- [ ] **Step 3: Run static scope and privacy ratchets**

The following must be true:

```bash
git diff --exit-code 4e7bb24 -- \
  src/news_normalized/schema.py \
  src/news_normalized/writer.py \
  src/news_normalized/models.py \
  src/news_normalized/ibkr_adapter.py \
  src/service/data_scheduler.py \
  apps/arkscope-web

rg -n "_IBKR_10172_MAX_ATTEMPTS = 2" src/news_normalized/store.py
rg -n "attempts >= 3|attempts>=3" src/news_normalized/store.py
rg -n "reconcil.*count|reconciled.*count|10172.*reconcil" \
  src/service/data_scheduler.py apps/arkscope-web
rg -n "provider_article_id|raw_body|body_text|reconcile_ibkr_10172|10172.*reconcil|reconcil.*10172" \
  src/service/data_scheduler.py apps/arkscope-web/src/api.ts
rg -n "CREATE TABLE.*retry|news_body_retry_queue|body_retry_queue" \
  src/news_normalized
rg -n "force.?retry|placeOrder|cancelOrder|modifyOrder|exerciseOption" \
  src/news_normalized/store.py src/news_normalized/ibkr_cli.py
rg -n "psycopg|postgres|PG_DSN|DATABASE_URL" \
  src/news_normalized/store.py src/news_normalized/ibkr_cli.py
```

Expected:

- threshold constant: exactly one match;
- old threshold and every other `rg`: zero matches;
- byte-identity command: empty diff.

The reconciliation method name is expected inside store/worker/tests; the
telemetry gate is intentionally scoped to parent/API/frontend owners.

- [ ] **Step 4: Run a copied-DB mutation probe, never the real DB**

Use `sqlite3.Connection.backup()` to copy the resolved real market DB to a
unique `/tmp/arkscope-10172-reconcile-*.db`. The probe must:

1. open the source read-only or only long enough to call SQLite backup;
2. close the source before mutation;
3. count matching copied rows using aggregate SQL only;
4. compute an internal SHA-256 digest over all fetched body/article fields and
   a second digest over all matching rows excluding the three allowed mutable
   fields;
5. call `reconcile_ibkr_10172_retry_policy()` on the copy with a fixed UTC
   `now` and `available_provider_codes=None` (unit tests separately prove the
   strict entitlement filter used by the live worker);
6. call it a second time;
7. print one sanitized JSON object containing only:

```json
{
  "matching_before": 71,
  "changed_first": 71,
  "changed_second": 0,
  "matching_after": 0,
  "fetched_count_unchanged": true,
  "fetched_digest_unchanged": true,
  "article_digest_unchanged": true,
  "protected_body_fields_unchanged": true,
  "quick_check": "ok"
}
```

The numeric example is illustrative; do not assert `71` or any production
snapshot constant. Assert only `changed_first == matching_before`, second is
zero, after is zero, and every preservation boolean is true. The output must
contain no IDs, provider codes, titles, bodies, hashes, paths, or errors. Delete
the copied DB and temporary probe after recording the aggregate result.

- [ ] **Step 5: Run full backend and no-PG smoke**

```bash
pytest -q
python src/smoke/pg_unreachable_e2e.py
```

In an environment with the known bare-profile family, record raw counts and
failure identities without claiming clean full-suite PASS. The no-PG smoke
must return `ok: true` and `pg_attempts: []`.

- [ ] **Step 6: Run canonical A/B in clean virgin archives**

Compare behavioral base `4e7bb24` to the final code head, sequentially in one
process per side and the same environment. Required verdict:

- pre-existing failure sets are identical in both directions;
- skips, warnings, and errors are identical;
- passed delta equals exactly `+7`;
- collect diff is exactly `+7/-0`; and
- the seven additions are the four queue and three worker tests named in this
  plan.

If this environment hangs in the known `TestClient` family, stop the process,
record the limitation honestly, and leave reviewer canonical A/B as a merge
gate. Do not substitute a partial/file-isolated result and call it canonical.

---

### Task 5: Mark Review-Ready and Stop

**Files:**
- Modify `docs/superpowers/plans/2026-07-17-ibkr-news-10172-retry-recalibration.md`
- Modify `docs/superpowers/specs/2026-07-17-ibkr-news-10172-retry-recalibration-design.md`
- Modify `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Reconcile the implementation ledger exactly**

Record:

- branch base, behavioral base, code head, and docs head;
- every RED failure and why it was the intended old behavior;
- commits by task;
- focused/full collection and exact `+7/-0` node-ID diff;
- full-suite, no-PG, static, copied-DB, and A/B evidence;
- copied-DB aggregate counts without identifiers;
- confirmation that reconciliation count remained internal;
- any deviation, false-green, or test-ledger correction; and
- explicit statement that no live Gateway retry was forced for this gate.

- [ ] **Step 2: Change statuses without claiming LIVE**

Set:

- this plan: `IMPLEMENTED FOR REVIEW`;
- authority spec: `IMPLEMENTED FOR REVIEW — production merge/live pending`;
- map: newest-first review-ready entry with code tip and evidence.

Do not update the older live three-attempt authorities yet; production still
uses them until merge.

- [ ] **Step 3: Commit docs and stop for independent review**

```bash
git add \
  docs/superpowers/plans/2026-07-17-ibkr-news-10172-retry-recalibration.md \
  docs/superpowers/specs/2026-07-17-ibkr-news-10172-retry-recalibration-design.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: mark IBKR 10172 retry recalibration review-ready"
git status --short --branch
```

Expected: clean implementation worktree. Stop. Do not merge or run repeated
live Gateway calls before independent review.

## Reviewer Focus

1. The two-attempt threshold is the only `_upsert_body()` behavior change.
2. Reconciliation uses strict current entitlement in the live worker and does
   not terminalize derived provider-not-entitled rows.
3. Only `body_status`, `next_retry_at`, and `unavailable_at` change.
4. The write transaction is idempotent and rollback-safe.
5. Provider discovery precedes the short market lock; queue/provider work
   follows after release.
6. Reconciliation failure aborts before all retry/fresh calls.
7. Zero provider-work budgets do not trigger discovery or reconciliation.
8. The returned reconciliation count is absent from raw worker data, sanitized
   stdout, parent/API/frontend owners, and logs.
9. First-attempt six-hour backoff, budget `25`, entitlement reversibility,
   generic errors, explicit recovery, lock-busy, and fresh ingestion are
   unchanged.
10. Collection accounting is exactly `+7/-0`; no old contract silently
    disappeared under a rename.

## Stop Conditions

Stop and return to review if any of these occur:

- reconciliation needs provider data before successful strict discovery;
- provider identity must cross child stdout to implement or verify the policy;
- any schema, scheduler, writer, adapter, frontend, or API change appears
  necessary;
- reconciliation requires holding the market lock during a Gateway wait;
- a failure path would continue fresh/provider work after uncertain mutation;
- an entitlement-blocked row must be reclassified to make tests pass;
- generic errors or first-attempt backoff must change;
- copied-DB preservation cannot be proved without exposing row identity;
- canonical A/B has a new failure identity or collection delta other than
  `+7/-0`; or
- a live gate would require repeatedly forcing real due rows.

## Post-Review Merge and Live Closeout

After independent review says GREEN and the user approves merge:

1. stop any branch sidecar; this change needs no pre-merge Gateway call;
2. fast-forward merge only;
3. update the new spec/plan to `MERGED / LIVE` only after merged-tree focused,
   no-PG, and collection gates pass;
4. add a supersession note to
   `docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md` at each
   live three-attempt statement, pointing to this approved two-attempt policy;
5. add a supersession note near the global constraints/grounded baseline in
   `docs/superpowers/plans/2026-07-15-ibkr-news-durable-body-retry.md`; preserve
   its historical implementation ledger rather than rewriting history;
6. update P0-C and the newest-first map decision log with merge commit and
   final evidence;
7. restart the normal desktop app once so the merged worker policy is active;
8. wait for one natural due cycle rather than manually draining the queue;
9. use read-only aggregate telemetry to verify that currently eligible typed
   attempts-two rows no longer remain scheduled, provider-entitlement-blocked
   rows remain reversible, no third request was spent, and fresh bodies still
   ingest; and
10. remove the implementation worktree/branch after closeout. Publication/push
    remains user-owned.
