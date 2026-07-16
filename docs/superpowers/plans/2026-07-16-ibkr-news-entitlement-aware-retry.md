# IBKR News Entitlement-Aware Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** IMPLEMENTED FOR REVIEW — 2026-07-16. Code head `442911e` on `codex/ibkr-news-entitlement-hotfix`; do not merge before independent review. Grounded baseline: expanded focused backend `201`, full backend collection `4302`, focused frontend `47`, full frontend `44 files / 426 tests`. Final accounting: backend `+13/-0`, frontend `+2/-0`.

**Goal:** Stop unavailable IBKR news-provider entitlements from consuming the durable body-retry budget while retaining headlines and automatically resuming bounded retries when access later appears.

**Architecture:** One strict `reqNewsProviders` observation becomes the per-worker capability snapshot and is reused by both retry and fresh-headline legs. The normalized SQLite queue remains the only body authority: entitlement is a derived, reversible filter over unresolved rows, not a second queue or a terminal article-state rewrite. Sanitized telemetry carries only an aggregate `provider_not_entitled` count so Settings can explain retained headlines and automatic recovery without exposing provider identity.

**Tech Stack:** Python 3, ib_insync, SQLite, pytest, React 18, TypeScript, Vitest.

## Implementation Ledger

- **RED-first evidence:** Task 1 produced three intended missing-interface failures while the compatibility-wrapper pin remained green; Task 2 produced three missing-keyword failures; Task 3 produced five relevant worker/parser failures before wiring (the sixth new case exercised an already-safe branch); Task 4 produced two presentation failures with `47` existing focused tests still green.
- **Focused GREEN:** expanded news backend `214 passed` (`201 + 13`); explicit entitlement/10172/restart/budget/lock reliability selection `14 passed`; focused frontend `49 passed` (`47 + 2`).
- **Full frontend:** `44 files / 428 tests`, typecheck and production build pass; only the existing chunk-size warning remains.
- **Canonical backend A/B:** base `b657349` = `30 failed / 4191 passed / 74 skipped / 18 warnings / 7 errors`; code head = `30 failed / 4204 passed / 74 skipped / 18 warnings / 7 errors`. Failure/error sets are identical and collection is exactly `4302 -> 4315` (`+13/-0`).
- **Boundaries:** provider/article/body identity, second-queue, force-retry, order-API, and budget gates pass; `DEFAULT_MAX_RETRY_BODY_FETCHES = 25` has exactly one authority. No-PG smoke passes with `pg_attempts: []`.
- **Copied-DB one-Gateway proof:** a successful capability observation returned a non-empty aggregate provider set; `78` unresolved rows were classified as entitlement-blocked, generated zero body calls, and did not consume the `25` available-provider retry calls. An available-provider control returned normally or typed `10172`. A provider-set-only replay made one copied blocked row eligible under limit `1` without changing body status or attempts. Real market and profile DB digests were byte-identical before/after.
- **Responsive proof:** fixture-backed Settings checks at `1440x900`, `1024x768`, and `390x844` show the explanation inside its own cell, clear of the previous action cell, with no document overflow and no false retry action.
- **Deviation ledger:** no architecture or behavior deviation. Task 1's planned RED count said four, but the deliberately preserved compatibility-wrapper test was already green; the ledger records the actual three failing new interfaces rather than manufacturing a fourth failure.

### Reviewer verification ✅ (Fable, 2026-07-16) — all reviewer gates closed

Independent reviewer canonical A/B (virgin `git archive` of base `b657349`
versus tip `19144b0`, sequential single-process full pytest, reviewer
environment, no hang): both sides identical on the pre-existing family
(`30 failed / 74 skipped / 18 warnings / 7 errors`); failure sets empty in
both directions; passed `4191 -> 4204` = exactly **`+13`**, collect `+13/-0`,
and all 13 added node IDs are the named entitlement tests across the four
expected files. Work dir `/tmp/ab_entl_6njw`. Reviewer also re-ran: frontend
`44 files / 428 tests` PASS + typecheck + production build; focused backend
`214 passed`; and the static gates (provider identity absent from
scheduler/API/display/Settings boundaries; no new queue table, force-retry,
or order API; `DEFAULT_MAX_RETRY_BODY_FETCHES = 25` single authority;
`provider_not_entitled` implemented as a derived SQL count that never touches
`BodyStatus.UNAVAILABLE`). Reviewer grounding of the two load-bearing design
facts: (1) IBKR articles store `provider_code` as `publisher`
(`ibkr_adapter.py:67/:85`), so the publisher-based SQL predicate is a true
entitlement filter, not a string coincidence; (2) the old
`fetch_news(providers=None)` already defaulted to the account's available
provider list via the compat wrapper, so the explicit strict-discovery filter
is semantically equivalent for fresh scans while additionally fixing the
pre-existing failure-as-empty defect (discovery failure now fails closed with
a sanitized error instead of silently scanning nothing). All reviewer gates
are closed; merge remains the user's decision.

## Global Constraints

- Preserve the existing independent retry budget exactly: `DEFAULT_MAX_RETRY_BODY_FETCHES = 25`.
- Preserve `10172`: attempts one and two schedule six hours later; attempt three becomes terminal `BodyStatus.UNAVAILABLE`.
- `provider_not_entitled` is reversible capability state and must not write `BodyStatus.UNAVAILABLE` or alter `fetch_attempts`.
- A failed provider-list observation is not an empty provider set: perform no body/headline calls, no body-state mutation, and return a sanitized failure.
- Provider codes, article IDs, titles, bodies, and licensed provider errors remain absent from child stdout, parent scheduler state, API payloads, logs, DOM, screenshots, and review ledgers.
- No new queue table, cadence/config option, force-retry action, PG path, tool/prompt surface, or trading API.
- The copied-DB live gate may read the real provider configuration and Gateway but must leave the real `market_data.db` byte-identical.

---

### Task 1: Strict Provider Discovery and One-Run Capability Snapshot

**Files:**
- Modify: `data_sources/ibkr_source.py`
- Modify: `src/news_normalized/ibkr_runtime.py`
- Test: `tests/test_news_normalized_ibkr_adapter.py`
- Test: `tests/test_normalized_ibkr_worker.py`

**Interfaces:**
- Produces: `IBKRDataSource.get_news_providers_strict() -> list[dict[str, str]]`.
- Produces: `IBKRRuntimeGateway.discover_news_provider_codes() -> frozenset[str]`.
- Changes: `IBKRRuntimeGateway.fetch_headlines()` reuses the discovered set and passes a deterministic `+`-joined provider filter to `fetch_news()`.

- [x] **Step 1: Write failing strict-discovery tests**

Add tests that use a fake `reqNewsProviders()` client and prove all three states:

```python
def test_ibkr_strict_news_provider_discovery_distinguishes_empty_from_failure():
    empty = NewsProviderClient(result=[])
    assert body_source(empty).get_news_providers_strict() == []

    error = RuntimeError("provider list unavailable")
    failed = NewsProviderClient(error=error)
    with pytest.raises(RuntimeError) as caught:
        body_source(failed).get_news_providers_strict()
    assert caught.value is error


def test_ibkr_compat_news_provider_discovery_still_returns_empty_on_failure():
    source = body_source(NewsProviderClient(error=RuntimeError("provider list unavailable")))
    assert source.get_news_providers() == []
```

Add runtime tests proving normalized/deduplicated codes are cached and reused:

```python
def test_runtime_gateway_discovers_once_and_reuses_provider_filter_for_headlines():
    source = RuntimeSource(provider_rows=[{"code": "DJ-N"}, {"code": " dj-rta "}, {"code": "DJ-N"}])
    gateway = IBKRRuntimeGateway(source)

    assert gateway.discover_news_provider_codes() == frozenset({"DJ-N", "DJ-RTA"})
    list(gateway.fetch_headlines("AAPL", None))

    assert source.provider_calls == 1
    assert source.fetch_news_calls[0][1]["providers"] == "DJ-N+DJ-RTA"


def test_runtime_gateway_with_successful_empty_provider_set_makes_no_headline_call():
    source = RuntimeSource(provider_rows=[])
    gateway = IBKRRuntimeGateway(source)
    assert gateway.discover_news_provider_codes() == frozenset()
    assert list(gateway.fetch_headlines("AAPL", None)) == []
    assert source.fetch_news_calls == []
```

- [x] **Step 2: Run RED**

```bash
pytest tests/test_news_normalized_ibkr_adapter.py tests/test_normalized_ibkr_worker.py -k "provider_discovery or provider_filter" -q
```

Expected/observed: three RED failures because strict discovery and runtime caching do not exist; the compatibility-wrapper pin remains green by design.

- [x] **Step 3: Implement the strict compatibility split**

Implement `get_news_providers_strict()` as the only direct `reqNewsProviders()` caller. Keep `get_news_providers()` as the compatibility wrapper that catches, logs, and returns `[]`.

In `IBKRRuntimeGateway`, keep `_provider_codes: frozenset[str] | None`; normalize codes using `str(...).strip().upper()`, remove empty/duplicate values, and require discovery before `fetch_headlines()`. A successful empty set returns no headlines without calling `fetch_news`; a non-empty set passes `providers="+".join(sorted(codes))`.

- [x] **Step 4: Run GREEN and regression tests**

```bash
pytest tests/test_news_normalized_ibkr_adapter.py tests/test_normalized_ibkr_worker.py -q
```

Expected: all tests pass; existing strict body and runtime cleanup contracts remain green.

- [x] **Step 5: Commit**

```bash
git add data_sources/ibkr_source.py src/news_normalized/ibkr_runtime.py tests/test_news_normalized_ibkr_adapter.py tests/test_normalized_ibkr_worker.py
git commit -m "fix: discover IBKR news entitlements strictly"
```

---

### Task 2: Entitlement-Aware Durable Queue Projection

**Files:**
- Modify: `src/news_normalized/models.py`
- Modify: `src/news_normalized/store.py`
- Test: `tests/test_news_normalized_retry_queue.py`

**Interfaces:**
- Changes: `BodyRetryBacklog` gains `provider_not_entitled: int = 0`.
- Changes: `select_ibkr_body_retries(*, now, limit, available_provider_codes=None)`.
- Changes: `summarize_ibkr_body_backlog(*, now, available_provider_codes=None)`.
- `None` preserves compatibility for non-worker callers/tests; the production worker always passes a successfully observed set.

- [x] **Step 1: Write failing queue tests**

```python
def test_entitlement_filter_excludes_unavailable_provider_and_counts_it(tmp_path):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        entitled = _seed(store, "entitled", publisher="DJ-N")
        _seed(store, "blocked", provider_id="FLY$blocked", publisher="FLY")

        selection = store.select_ibkr_body_retries(
            now=NOW,
            limit=10,
            available_provider_codes=frozenset({"DJ-N"}),
        )

        assert selection.article_ids == (entitled,)
        assert selection.backlog.due_now == 1
        assert selection.backlog.never_attempted == 1
        assert selection.backlog.provider_not_entitled == 1
    finally:
        conn.close()


def test_provider_access_return_reenters_same_rows_under_existing_limit(tmp_path):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        first = _seed(store, "first", provider_id="FLY$first", publisher="FLY")
        second = _seed(store, "second", provider_id="FLY$second", publisher="FLY")

        blocked = store.select_ibkr_body_retries(
            now=NOW, limit=1, available_provider_codes=frozenset({"DJ-N"})
        )
        restored = store.select_ibkr_body_retries(
            now=NOW, limit=1, available_provider_codes=frozenset({"DJ-N", "FLY"})
        )

        assert blocked.article_ids == ()
        assert blocked.backlog.provider_not_entitled == 2
        assert restored.article_ids == (first,)
        assert restored.backlog.due_now == 2
        assert restored.backlog.provider_not_entitled == 0
        assert second not in restored.article_ids
    finally:
        conn.close()


def test_entitlement_filter_does_not_reclassify_terminal_10172(tmp_path):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        terminal = _seed(store, "terminal", publisher="FLY")
        _set_body(conn, terminal, status="unavailable", attempts=3)
        summary = store.summarize_ibkr_body_backlog(
            now=NOW, available_provider_codes=frozenset({"DJ-N"})
        )
        assert summary.provider_not_entitled == 0
        assert summary.due_now == 0
    finally:
        conn.close()
```

- [x] **Step 2: Run RED**

```bash
pytest tests/test_news_normalized_retry_queue.py -k "entitlement or provider_access" -q
```

Expected: three failures due to missing parameters/count.

- [x] **Step 3: Implement one SQL capability predicate**

Normalize the optional set once. Build SQL placeholders only from normalized codes; never interpolate code values. Apply the same predicate to selection and summary:

- `available_provider_codes is None`: all identity-valid unresolved rows remain eligible and blocked count is zero (compatibility mode);
- empty set: no unresolved row is retry-eligible and all unresolved rows count as `provider_not_entitled`;
- non-empty set: `UPPER(TRIM(a.publisher)) IN (...)` is eligible; the complement is blocked.

Keep terminal rows outside all four counts. Do not update `news_article_bodies`, `fetch_attempts`, errors, or timestamps.

- [x] **Step 4: Run GREEN and all queue/store policy tests**

```bash
pytest tests/test_news_normalized_retry_queue.py tests/test_news_normalized_store.py -q
```

Expected: all tests pass, including existing deterministic order, restart, and third-`10172` pins.

- [x] **Step 5: Commit**

```bash
git add src/news_normalized/models.py src/news_normalized/store.py tests/test_news_normalized_retry_queue.py
git commit -m "fix: filter news retries by active entitlement"
```

---

### Task 3: Worker Wiring and Sanitized Aggregate Telemetry

**Files:**
- Modify: `src/news_normalized/ibkr_cli.py`
- Modify: `src/service/data_scheduler.py`
- Test: `tests/test_normalized_ibkr_worker.py`
- Test: `tests/test_data_scheduler.py`

**Interfaces:**
- The worker calls `gateway.discover_news_provider_codes()` once before opening retry selection.
- Both queue methods receive that exact immutable set.
- Sanitized `body_backlog.status="ok"` gains only `provider_not_entitled`.

- [x] **Step 1: Write failing worker and boundary tests**

Add real-store worker coverage:

```python
def test_worker_does_not_call_body_for_unentitled_provider_and_reports_count(tmp_path, monkeypatch):
    db_path = tmp_path / "market_data.db"
    _seed_body_row(db_path, "blocked", provider_id="FLY$blocked", publisher="FLY")
    provider = _WorkerProvider({"AAPL": [_headline("fresh")]})

    result = _run_real_worker(
        monkeypatch,
        db_path,
        provider,
        available_provider_codes=frozenset({"DJ-N"}),
    )

    assert all("FLY" not in str(event) for event in provider.events)
    assert result["body_backlog"]["provider_not_entitled"] == 1
    assert result["fresh_status"] == "succeeded"


def test_worker_provider_discovery_failure_performs_no_retry_or_fresh_calls(monkeypatch, capsys):
    from src.news_normalized import ibkr_cli as worker

    events = []
    secret = "licensed provider payload FLY"

    class Source:
        def __init__(self, client_id=None):
            self.client_id = client_id

        def disconnect(self):
            events.append("disconnect")

    class Gateway:
        def __init__(self, source):
            self.source = source

        def discover_news_provider_codes(self):
            events.append("discover")
            raise RuntimeError(secret)

        def close(self):
            self.source.disconnect()

    def forbidden(*args, **kwargs):
        raise AssertionError("discovery failure must stop before store/provider work")

    monkeypatch.setattr("data_sources.ibkr_source.IBKRDataSource", Source)
    monkeypatch.setattr("src.news_normalized.ibkr_runtime.IBKRRuntimeGateway", Gateway)
    monkeypatch.setattr("src.news_normalized.ibkr_adapter.IBKRNormalizedProvider", forbidden)
    monkeypatch.setattr("src.news_normalized.store.NormalizedNewsStore", forbidden)
    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)

    code = worker.main(["--tickers", "AAPL", "--gateway-lock-held"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["status"] == "failed"
    assert payload["error_classes"] == ["RuntimeError"]
    assert payload["error"] == ""
    assert secret not in repr(payload)
    assert events == ["discover", "disconnect"]
```

Extend `_seed_body_row()` with explicit `provider_id` and `publisher` keyword arguments, and extend `_run_real_worker()` / `_WorkerGateway` with an `available_provider_codes` fixture value. Those helpers must default to the current `DJ-N` behavior so all existing tests remain unchanged.

Strengthen the existing fake-store wiring test so selection and summary both receive the same
`frozenset({"DJ-N"})` and provider discovery is called once.

Add sanitizer/parser tests:

```python
def test_worker_stdout_preserves_only_aggregate_entitlement_block_count():
    payload = sanitize_worker_result({
        "status": "succeeded",
        "body_backlog": {
            "status": "ok",
            "due_now": 0,
            "scheduled_later": 0,
            "never_attempted": 0,
            "earliest_next_retry_at": None,
            "provider_not_entitled": 78,
        },
    })
    assert payload["body_backlog"]["provider_not_entitled"] == 78
    assert "FLY" not in repr(payload)


def test_worker_stdout_rejects_invalid_entitlement_block_count():
    for value in (-1, 1.5, True, "78"):
        payload = sanitize_worker_result({
            "status": "succeeded",
            "body_backlog": {
                "status": "ok", "due_now": 0, "scheduled_later": 0,
                "never_attempted": 0, "earliest_next_retry_at": None,
                "provider_not_entitled": value,
            },
        })
        assert payload["body_backlog"] == {"status": "unavailable"}
```

Add two parser-boundary tests in `tests/test_data_scheduler.py`:

```python
def test_worker_stdout_parse_preserves_entitlement_block_count():
    payload = ds._parse_sanitized_worker_stdout(json.dumps({
        "status": "succeeded",
        "body_backlog": {
            "status": "ok",
            "due_now": 0,
            "scheduled_later": 0,
            "never_attempted": 0,
            "earliest_next_retry_at": None,
            "provider_not_entitled": 78,
        },
    }))
    assert payload is not None
    assert payload["body_backlog"]["provider_not_entitled"] == 78


def test_worker_stdout_parser_rejects_malformed_entitlement_block_count():
    for value in (-1, 1.5, True, "78"):
        payload = ds._parse_sanitized_worker_stdout(json.dumps({
            "status": "partial",
            "body_backlog": {
                "status": "ok",
                "due_now": 0,
                "scheduled_later": 0,
                "never_attempted": 0,
                "provider_not_entitled": value,
            },
        }))
        assert payload is not None
        assert payload["body_backlog"] == {"status": "unavailable"}
```

- [x] **Step 2: Run RED**

```bash
pytest tests/test_normalized_ibkr_worker.py tests/test_data_scheduler.py -k "entitlement or provider_discovery or body_backlog" -q
```

Expected: new tests fail because the worker does not discover/filter providers and sanitizers do not recognize the new count.

- [x] **Step 3: Wire discovery before retry selection**

Call `discover_news_provider_codes()` once inside the existing Gateway lock before opening SQLite selection. Pass the returned `frozenset` to both queue calls. Let discovery exceptions escape `_run_worker`; `main()` already owns the sanitized failure boundary and `finally` disconnects.

Extend `_sanitize_body_backlog()` and scheduler `_parse_body_backlog()` with the same strict non-negative-integer validation used by existing counts. A malformed count makes the whole body backlog `unavailable`, never zero.

- [x] **Step 4: Run GREEN and focused worker/scheduler suites**

```bash
pytest tests/test_normalized_ibkr_worker.py tests/test_data_scheduler.py -q
```

Expected: all pass; existing fresh/retry independence, queue-failure, lock, and privacy tests remain green.

- [x] **Step 5: Commit**

```bash
git add src/news_normalized/ibkr_cli.py src/service/data_scheduler.py tests/test_normalized_ibkr_worker.py tests/test_data_scheduler.py
git commit -m "fix: report entitlement-blocked news bodies"
```

---

### Task 4: Truthful Settings Presentation

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/marketDataDisplay.ts`
- Test: `apps/arkscope-web/src/marketDataDisplay.test.ts`
- Test: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`

**Interfaces:**
- `ScheduleBodyBacklog.provider_not_entitled?: number` is additive.
- `schedulerBodyBacklogPresentation()` renders blocked rows as a separate fact and never offers a retry command.

- [x] **Step 1: Write failing frontend tests**

```typescript
it("explains entitlement-blocked bodies without calling them missing", () => {
  const view = schedulerBodyBacklogPresentation({
    last_status: "succeeded",
    continuation: null,
    running_stale: false,
    running_stale_reason: null,
    last_result: {
      source: "ibkr_news",
      status: "succeeded",
      collect: {
        body_backlog: {
          status: "ok",
          due_now: 0,
          scheduled_later: 0,
          never_attempted: 0,
          earliest_next_retry_at: null,
          provider_not_entitled: 78,
        },
      },
    },
  });
  expect(view?.label).toContain("78 篇來源目前未訂閱");
  expect(view?.label).toContain("標題已保留");
  expect(view?.label).toContain("開通後自動重試");
  expect(view?.label).not.toContain("永久");
});
```

Mounted Settings coverage must assert the IBKR row shows the same explanation, still has only the ordinary `Run` command, has no `補抓`/provider code/article ID, and may show due/scheduled counts alongside the blocked count.

- [x] **Step 2: Run RED**

```bash
cd apps/arkscope-web
npm test -- --run src/marketDataDisplay.test.ts src/SettingsProviderConfig.test.ts
```

Expected: two new tests fail because the new field is ignored.

- [x] **Step 3: Implement additive typing and copy**

Validate `provider_not_entitled` with `backlogCount()`. If invalid, return the existing unavailable presentation. If positive, append:

`N 篇來源目前未訂閱（標題已保留，開通後自動重試）`

Return a presentation even when due-now and scheduled-later are both zero but the blocked count is positive. Keep tone `muted`; entitlement block is not a failed operation and never creates a button.

- [x] **Step 4: Run GREEN and frontend gates**

```bash
cd apps/arkscope-web
npm test -- --run src/marketDataDisplay.test.ts src/SettingsProviderConfig.test.ts
npm test
npm run typecheck
npm run build
```

Expected: focused tests pass; full frontend increases by exactly two tests; typecheck/build pass with only the existing chunk-size warning.

- [x] **Step 5: Commit**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/marketDataDisplay.ts apps/arkscope-web/src/marketDataDisplay.test.ts apps/arkscope-web/src/SettingsProviderConfig.test.ts
git commit -m "fix: explain unavailable news entitlements"
```

---

### Task 5: Verification, Copied-DB Live Gate, and Review Handoff

**Files:**
- Verify: all Task 1-4 files
- Modify after evidence: `docs/superpowers/plans/2026-07-16-ibkr-news-entitlement-aware-retry.md`
- Modify after evidence: `docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md`
- Modify after evidence: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Produces review-ready evidence only. Do not merge or mark the follow-up LIVE before independent review.

- [x] **Step 1: Run the focused backend ledger**

```bash
pytest tests/test_news_normalized_ibkr_adapter.py tests/test_news_normalized_store.py tests/test_news_normalized_retry_queue.py tests/test_news_normalized_writer.py tests/test_news_normalized_writer_locking.py tests/test_normalized_ibkr_worker.py tests/test_data_scheduler.py -q
```

Expected: `214 passed`, exactly baseline `201 + 13`; no removals or warning delta.

- [x] **Step 2: Run explicit behavior and privacy gates**

Run the new entitlement tests plus existing `10172`, restart, independent-budget, lock-busy, and scheduler-persistence pins. Then require zero provider identity in parent/frontend surfaces:

```bash
rg -n "available_provider_codes|provider_article_id|retry_body_ids|raw_body|body_text" \
  src/service/data_scheduler.py \
  apps/arkscope-web/src/api.ts \
  apps/arkscope-web/src/marketDataDisplay.ts \
  apps/arkscope-web/src/Settings.tsx

rg -n "CREATE TABLE.*entitlement|news_provider_entitlement|body_retry_queue" \
  src/news_normalized

rg -n "force.?retry|placeOrder|cancelOrder|modifyOrder|exerciseOption" \
  src/news_normalized src/service/data_scheduler.py

rg -n "DEFAULT_MAX_RETRY_BODY_FETCHES = 25" src/news_normalized/ibkr_cli.py
```

Expected: first three gates return zero matches; the final gate returns exactly one match.

- [x] **Step 3: Run full automated verification**

```bash
pytest -q
cd apps/arkscope-web
npm test
npm run typecheck
npm run build
cd ../..
python src/smoke/pg_unreachable_e2e.py
```

Record raw known baseline failures rather than claiming a clean full pass. Run canonical virgin A/B against `b657349`; require identical pre-existing failure/error/skip/warning sets and backend collection `4302 -> 4315`, exactly `+13/-0`.

- [x] **Step 4: Run one-Gateway copied-DB proof**

With the desktop sidecar closed and one Gateway consumer only:

1. copy the real `market_data.db` using SQLite backup API;
2. record only aggregate pre-state counts and the real DB digest;
3. run the branch worker against the copy and real provider configuration;
4. prove the current successful provider observation excludes all FLY unresolved rows from body calls and reports them only as `provider_not_entitled`;
5. prove one available-provider control remains eligible/fetchable or follows typed `10172` without exposing its identity/content;
6. run a provider-set-only local store proof that adding `FLY` makes a blocked copied row eligible under limit `1` without changing its body status or attempt count; and
7. prove the real DB digest is byte-identical.

No provider code, provider article ID, title, body, or licensed error text may enter the terminal transcript or ledger.

- [x] **Step 5: Run responsive Settings gate**

At `1440x900`, `1024x768`, and `390x844`, verify the blocked-entitlement explanation wraps without covering progress/last-run cells, causes no document overflow, and shows no false action. Use fixture data if the live backlog naturally changes; do not edit the real profile/market DB to manufacture UI state.

- [x] **Step 6: Reconcile docs and commit review handoff**

Update the plan header with RED/GREEN counts, canonical A/B, copied-DB evidence, and any deliberate deviations. Mark the spec `ENTITLEMENT FOLLOW-UP IMPLEMENTED FOR REVIEW`, insert the newest-first map entry, and commit only those docs. Stop review-ready; do not merge.

---

## Stop Conditions

Stop and report before continuing if any of these occur:

1. `reqNewsProviders` cannot distinguish successful empty from failure without parsing provider text;
2. entitlement filtering requires provider IDs to leave the isolated child process;
3. a blocked row must be rewritten to terminal `unavailable` to make selection work;
4. existing `10172` timing/attempt semantics or the `25`-request budget changes;
5. fresh headline work requires a second provider-list call or loses its independent budget;
6. a provider-list failure can mutate body state or masquerade as an empty entitlement set;
7. full A/B changes an existing failure family; or
8. the copied-DB live gate would require mutating the real market DB or exposing licensed content.

## Self-Review

- **Spec coverage:** Tasks 1-4 implement strict observation, reversible queue filtering, aggregate telemetry, UI explanation, and automatic bounded re-entry. Task 5 covers privacy, `10172`, copied-DB, responsive, and A/B gates.
- **Placeholder scan:** No task delegates unspecified behavior; helper signature changes and failure-path fakes are specified in their owning test files.
- **Type consistency:** `provider_not_entitled` is a non-negative integer in Python dataclass, child sanitizer, scheduler parser, TypeScript DTO, and presentation helper. The queue parameter is named `available_provider_codes` in both store methods and worker wiring.
