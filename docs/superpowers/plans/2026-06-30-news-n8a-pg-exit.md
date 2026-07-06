# News N8a PG-Exit Implementation Plan

> **Status: COMPLETED — historical implementation record; closeout entry in `PROJECT_PRIORITY_MAP.md` §10.**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route Polygon, Finnhub, and IBKR news through one normalized local writer with an atomic legacy projection, then remove news PostgreSQL sync/fallback while preserving current reader behavior.

**Architecture:** The normalized store becomes ingest authority and transactionally maintains `news`/`news_fts` as a compatibility projection. Polygon/Finnhub remain in-process; IBKR keeps subprocess isolation. A persisted exit marker makes only news hard-local and prevents any route back to PG. N8b normalized reads are a later plan.

**Tech Stack:** Python 3, SQLite/WAL/FTS5, FastAPI, React/TypeScript, pytest, Vitest, `ib_insync`, existing scheduler/file locks.

---

## File Map

- Create `src/news_normalized/routing.py`: writer route and post-exit invariants.
- Modify `src/news_normalized/schema.py`: projection map and cutover audit table.
- Modify `src/news_normalized/store.py`: caller-owned transaction methods.
- Create `src/news_normalized/legacy_projection.py`: normalized-to-legacy projection.
- Modify `src/news_normalized/writer.py` and `models.py`: atomic projection and counters.
- Create `src/news_normalized/ibkr_runtime.py` and
  `scripts/collection/collect_ibkr_news_normalized.py`: isolated IBKR runtime.
- Modify `src/service/data_scheduler.py`: route all three providers.
- Create `src/news_normalized/cutover.py` and
  `scripts/migration/news_n8a_cutover.py`: immutable delta/cutover gate.
- Modify `src/market_data_admin.py`: domain-selective mirror.
- Modify DAL/local backend/API/Settings for news hard-local state.

## Locked Toggle Matrix

`E=news_pg_exit_completed`, `N=use_normalized_news_writes`, `L=use_local_news`:

| E | N | L | Route |
|---|---|---|---|
| false | true | any | normalized + legacy projection |
| false | false/unset | true | current legacy-local REST path; IBKR PG path |
| false | false/unset | false | current PG/mirror path |
| true | true/unset | any | normalized + legacy projection |
| true | false | any | blocked; never PG |

Environment values override profile values. After exit, disabling normalized writes or selecting
the old PG route must fail closed.

---

### Task 1: Freeze writer routing

**Files:**
- Create: `src/news_normalized/routing.py`
- Test: `tests/test_news_normalized_routing.py`

- [ ] **Step 1: Write failing matrix tests**

```python
@pytest.mark.parametrize(("exit_done", "normalized", "local", "expected"), [
    (False, True, True, NewsWriteMode.NORMALIZED),
    (False, None, True, NewsWriteMode.LEGACY_LOCAL),
    (False, False, False, NewsWriteMode.LEGACY_PG),
    (True, None, False, NewsWriteMode.NORMALIZED),
    (True, False, True, NewsWriteMode.BLOCKED),
])
def test_route_matrix(exit_done, normalized, local, expected):
    route = resolve_news_write_route(
        exit_completed=exit_done,
        normalized_value=normalized,
        local_value=local,
    )
    assert route.mode is expected
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_news_normalized_routing.py`

Expected: module import failure.

- [ ] **Step 3: Implement pure resolver and profile/env constants**

```python
class NewsWriteMode(str, Enum):
    NORMALIZED = "normalized"
    LEGACY_LOCAL = "legacy_local"
    LEGACY_PG = "legacy_pg"
    BLOCKED = "blocked"

@dataclass(frozen=True)
class NewsWriteRoute:
    mode: NewsWriteMode
    reason: str
```

Use `news_providers.parse_news_toggle`; explicit env wins. When exit is complete, unset means
normalized and explicit false means blocked.

- [ ] **Step 4: Verify and commit**

Run: `pytest -q tests/test_news_normalized_routing.py tests/test_news_providers.py`

```bash
git add src/news_normalized/routing.py tests/test_news_normalized_routing.py
git commit -m "feat: define normalized news routing state"
```

---

### Task 2: Expose caller-owned store transactions

**Files:**
- Modify: `src/news_normalized/store.py`
- Test: `tests/test_news_normalized_store.py`

- [ ] **Step 1: Write rollback/compatibility tests**

```python
def test_uncommitted_upsert_rolls_back(store):
    store.conn.execute("BEGIN IMMEDIATE")
    store.upsert_uncommitted(candidate("p1"))
    store.conn.rollback()
    assert store.conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 0

def test_existing_upsert_still_commits(store):
    store.upsert(candidate("p1"))
    assert store.conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 1
```

Add the same contract for `update_body_uncommitted`.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_news_normalized_store.py -k "uncommitted or still_commits"`

Expected: missing uncommitted methods.

- [ ] **Step 3: Extract transaction-neutral internals**

```python
def upsert(self, candidate):
    with self.conn:
        return self.upsert_uncommitted(candidate)

def upsert_uncommitted(self, candidate):
    return self._upsert_impl(candidate)

def update_body(self, candidate, body, *, allow_terminal_recovery=False):
    with self.conn:
        return self.update_body_uncommitted(
            candidate, body, allow_terminal_recovery=allow_terminal_recovery
        )
```

Move existing logic without changing identity, body retry/ranking, or FTS behavior.

- [ ] **Step 4: Verify and commit**

Run: `pytest -q tests/test_news_normalized_store.py tests/test_news_normalization_apply.py`

```bash
git add src/news_normalized/store.py tests/test_news_normalized_store.py
git commit -m "refactor: expose transaction-owned news store writes"
```

---

### Task 3: Build deterministic legacy projection

**Files:**
- Modify: `src/news_normalized/schema.py`
- Create: `src/news_normalized/legacy_projection.py`
- Test: `tests/test_news_normalized_projection.py`

- [ ] **Step 1: Write failing parity tests**

Test one article/two tickers -> two legacy rows, body -> <=500-char clean snippet, rerun -> zero
duplicates, title correction -> same mapped rows, no ticker -> counted skip, injected conflict ->
rollback, and both FTS indexes remain consistent. For a Polygon/Finnhub fixture, compare projected
ticker/title/source/url/publisher/timestamp/hash/description directly with the current
`news_direct._article_row` result so compatibility is measured against today's writer.

```python
result = project_article_uncommitted(conn, article_id)
rows = conn.execute("SELECT ticker,description FROM news ORDER BY ticker").fetchall()
assert result.inserted == 2
assert [r[0] for r in rows] == ["AAPL", "MSFT"]
assert all(len(r[1]) <= 500 and "<p>" not in r[1] for r in rows)
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_news_normalized_projection.py`

Expected: module import failure.

- [ ] **Step 3: Add projection ownership schema**

```sql
CREATE TABLE IF NOT EXISTS news_legacy_projection_map (
  article_id INTEGER NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  legacy_news_id INTEGER NOT NULL UNIQUE,
  projected_at TEXT NOT NULL,
  PRIMARY KEY(article_id,ticker)
);
```

Do not FK `legacy_news_id` to `news`; N9 must be able to drop the compatibility table.

- [ ] **Step 4: Implement transaction-neutral projector**

```python
@dataclass(frozen=True)
class ProjectionResult:
    inserted: int = 0
    updated: int = 0
    skipped_no_ticker: int = 0

def project_article_uncommitted(conn, article_id):
    article = _read_article_with_body(conn, article_id)
    tickers = _read_canonical_tickers(conn, article_id)
    if not tickers:
        return ProjectionResult(skipped_no_ticker=1)
    description = clean_snippet(article["body_text"] or "")
    # For every ticker, update mapped row or insert/adopt a compatible canonical-hash row.
```

Use `canonical_article_hash`, existing news FTS triggers, and no manual FTS write/commit. Raise
`LegacyProjectionConflict` on incompatible hash ownership.

- [ ] **Step 5: Verify and commit**

Run: `pytest -q tests/test_news_normalized_projection.py tests/test_news_normalized_store.py`

```bash
git add src/news_normalized/schema.py src/news_normalized/legacy_projection.py \
  tests/test_news_normalized_projection.py
git commit -m "feat: project normalized news to legacy local rows"
```

---

### Task 4: Integrate projection into the common writer

**Files:**
- Modify: `src/news_normalized/models.py`
- Modify: `src/news_normalized/writer.py`
- Test: `tests/test_news_normalized_writer.py`

- [ ] **Step 1: Write failing atomicity tests**

```python
result = write_news_batch(
    store, provider, ["AAPL"], WriterBudget(10, 10), project_legacy=True
)
assert result.legacy_rows_inserted == 1
assert store.conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 1
```

Inject projector failure and assert both normalized and legacy counts remain zero.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_news_normalized_writer.py -k "projection or atomic"`

- [ ] **Step 3: Add result counters and transaction boundaries**

Add defaulted `legacy_rows_inserted`, `legacy_rows_updated`, and
`projection_skipped_no_ticker` fields. For each metadata mutation:

```python
store.conn.execute("BEGIN IMMEDIATE")
try:
    upsert = store.upsert_uncommitted(candidate)
    projected = project_article_uncommitted(store.conn, upsert.article_id)
    store.conn.commit()
except Exception:
    store.conn.rollback()
    raise
```

Provider body calls happen outside a DB transaction. A successful body update uses a second
transaction and re-projects the snippet. Telemetry helpers run after data commit.

- [ ] **Step 4: Verify and commit**

Run: `pytest -q tests/test_news_normalized_writer.py tests/test_news_normalized_projection.py`

```bash
git add src/news_normalized/models.py src/news_normalized/writer.py \
  tests/test_news_normalized_writer.py
git commit -m "feat: atomically project normalized news writes"
```

---

### Task 5: Route Polygon/Finnhub normalized writes

**Files:**
- Modify: `src/service/data_scheduler.py`
- Test: `tests/test_data_scheduler.py`
- Test: `tests/test_news_normalized_provider_adapters.py`

- [ ] **Step 1: Write routing tests for normalized, legacy-local, legacy-PG, blocked**

Pin that normalized mode fetches once, calls `write_news_batch(..., project_legacy=True)`, has no
`sync`, and skips mirror. Pin old routes unchanged before exit and blocked mode makes no provider
call.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_data_scheduler.py -k "normalized_news or post_exit"`

- [ ] **Step 3: Implement normalized REST runner**

Open `market_data.db`, create `NormalizedNewsStore`, choose existing Polygon/Finnhub normalized
provider, and run a bounded writer under `market_write_lock`. Always close the connection. Resolve
the Task 1 route once per scheduler run; normalized wins over the current direct branch.

- [ ] **Step 4: Verify and commit**

Run: `pytest -q tests/test_data_scheduler.py tests/test_news_normalized_provider_adapters.py tests/test_news_providers.py`

```bash
git add src/service/data_scheduler.py tests/test_data_scheduler.py \
  tests/test_news_normalized_provider_adapters.py
git commit -m "feat: route REST news through normalized writer"
```

---

### Task 6: Add isolated normalized IBKR worker

**Files:**
- Modify: `src/news_normalized/ibkr_adapter.py`
- Create: `src/news_normalized/ibkr_runtime.py`
- Create: `scripts/collection/collect_ibkr_news_normalized.py`
- Modify: `src/service/data_scheduler.py`
- Test: `tests/test_news_normalized_ibkr_adapter.py`
- Create: `tests/test_normalized_ibkr_worker.py`
- Test: `tests/test_data_scheduler.py`

- [ ] **Step 1: Write lock/lifecycle/sanitization tests**

```python
provider = IBKRNormalizedProvider(fake_gateway, acquire_gateway_lock=False)
assert isinstance(provider.operation(), nullcontext)
```

Assert connected runtime always disconnects in `finally`, malformed provider IDs are rejected,
and worker JSON contains no title, URL, article ID, provider text, or body.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_news_normalized_ibkr_adapter.py tests/test_normalized_ibkr_worker.py -k "lock or disconnect or sanitized"`

- [ ] **Step 3: Implement explicit lock ownership**

`IBKRNormalizedProvider(..., acquire_gateway_lock=True)` returns `ibkr_gateway_lock()` normally and
`nullcontext()` only for the scheduler child whose parent holds both locks.

- [ ] **Step 4: Implement runtime adapter and worker**

The runtime adapter wraps one `IBKRDataSource`, strictly extracts the existing provider article ID,
delegates strict body fetch, and disconnects in `finally`. The worker requires explicit tickers,
supports bounded article/body budgets, applies DB-managed provider config, writes normalized plus
projection under `market_write_lock`, and defaults to acquiring the Gateway lock. Only
`--gateway-lock-held` skips the Gateway lock.

- [ ] **Step 5: Route scheduler to child**

Parent retains current Gateway locks and launches:

```python
[sys.executable, str(_COLLECT_DIR / "collect_ibkr_news_normalized.py"),
 "--tickers", ",".join(scope), "--gateway-lock-held"]
```

Normalized mode has no PG sync or mirror refresh. Legacy modes keep the old subprocess unchanged.

- [ ] **Step 6: Verify and commit**

Run: `pytest -q tests/test_news_normalized_ibkr_adapter.py tests/test_normalized_ibkr_worker.py tests/test_data_scheduler.py -k "ibkr or normalized"`

```bash
git add src/news_normalized/ibkr_adapter.py src/news_normalized/ibkr_runtime.py \
  scripts/collection/collect_ibkr_news_normalized.py src/service/data_scheduler.py \
  tests/test_news_normalized_ibkr_adapter.py tests/test_normalized_ibkr_worker.py \
  tests/test_data_scheduler.py
git commit -m "feat: add isolated normalized IBKR news worker"
```

---

### Task 7: Add immutable delta/cutover audit

**Files:**
- Modify: `src/news_normalized/schema.py`
- Create: `src/news_normalized/cutover.py`
- Create: `scripts/migration/news_n8a_cutover.py`
- Test: `tests/test_news_n8a_cutover.py`

- [ ] **Step 1: Write read-only and blocker tests**

```python
before = file_identity(db_path)
report = preview_news_pg_exit(db_path)
assert report.unmapped_legacy_rows == 0
assert len(report.fingerprint) == 64
assert file_identity(db_path) == before
```

Add a legacy-only row and assert begin raises `CutoverBlocked("unmapped legacy rows: 1")` before
backup/schema/profile writes.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_news_n8a_cutover.py`

- [ ] **Step 3: Add cutover audit table and mode-ro preview**

```sql
CREATE TABLE IF NOT EXISTS news_pg_exit_runs (
  id INTEGER PRIMARY KEY,
  preflight_fingerprint TEXT NOT NULL UNIQUE,
  legacy_max_id INTEGER NOT NULL,
  legacy_row_count INTEGER NOT NULL,
  normalized_row_count INTEGER NOT NULL,
  normalized_only_count INTEGER NOT NULL,
  backup_path TEXT,
  status TEXT NOT NULL CHECK(status IN ('testing','completed','rolled_back')),
  started_at TEXT NOT NULL,
  completed_at TEXT,
  validation_json TEXT
);
```

Fingerprint sorted JSON of counts, per-source latest/counts, max legacy ID, and every unmapped
row's identity fields. Preview uses `mode=ro`, never ensures schema, and emits no generated-at
field so two reports are byte-identical. If delta is nonzero, stop; do not implement a time-window
guess. A separate reviewed delta slice is required only if this gate actually fires.

- [ ] **Step 4: Add operator CLI**

Commands: `preview --output REPORT.json`,
`begin --expected-report REPORT.json --backup PATH --confirm-scheduler-paused`,
`finalize --run-id --validation-json`, and `rollback --run-id`. The report contains the fingerprint
and full reviewed counts; begin recomputes and compares all report fields, not only the digest. No
`--force`. Begin creates a WAL-safe O_EXCL backup before adding cutover/projection DDL, then
creates the `testing` row only after exact report/zero-delta checks.

- [ ] **Step 5: Verify and commit**

Run: `pytest -q tests/test_news_n8a_cutover.py`

```bash
git add src/news_normalized/schema.py src/news_normalized/cutover.py \
  scripts/migration/news_n8a_cutover.py tests/test_news_n8a_cutover.py
git commit -m "feat: gate news PG exit on zero delta"
```

---

### Task 8: Make only news hard-local and support no DSN

**Files:**
- Modify: `src/tools/data_access.py`
- Modify: `src/tools/backends/db_backend.py`
- Modify: `src/tools/backends/local_market_backend.py`
- Modify: `src/tools/backends/sa_capture_backend.py`
- Test: `tests/test_sqlite_backend.py`
- Test: `tests/test_sa_routing.py`
- Create: `tests/test_news_pg_unreachable.py`

- [ ] **Step 1: Write no-DSN/no-PG tests**

```python
seed_profile(tmp_path, news_pg_exit_completed="true", use_local_market="false")
seed_market_db(tmp_path)
dal = DataAccessLayer(base_path=tmp_path, db_dsn="auto")
assert isinstance(dal._backend, LocalMarketDatabaseBackend)
assert dal._backend._news_strict is True
```

Monkeypatch every `DatabaseBackend.query_news*` to raise `AssertionError("PG called")`; assert
local empty/search/feed/stats return honestly. Assert `_strict` remains false so IV/fundamentals
policy is unchanged.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_news_pg_unreachable.py tests/test_sqlite_backend.py -k "hard_local or no_dsn"`

Expected: no-DSN selects `FileBackend` or news calls PG.

- [ ] **Step 3: Thread `news_strict` separately**

Add `news_strict=False` to local/SA constructors. All four news methods treat
`self._strict or self._news_strict` as no-fallback; prices/IV/fundamentals continue using only
global `_strict`.

- [ ] **Step 4: Build local composite without DATABASE_URL**

Resolve local markers before choosing `FileBackend`. If local DBs/markers are active, call the
existing composite constructor with an empty DSN. `DatabaseBackend._get_conn` raises
`RuntimeError("PostgreSQL is not configured")` before psycopg2 when DSN is empty. The news exit
marker forces market routing and news hard-local even if the obsolete market toggle is off.

- [ ] **Step 5: Verify and commit**

Run: `pytest -q tests/test_news_pg_unreachable.py tests/test_sqlite_backend.py tests/test_sa_routing.py tests/test_sa_capture_backend.py`

```bash
git add src/tools/data_access.py src/tools/backends/db_backend.py \
  src/tools/backends/local_market_backend.py src/tools/backends/sa_capture_backend.py \
  tests/test_news_pg_unreachable.py tests/test_sqlite_backend.py tests/test_sa_routing.py
git commit -m "feat: make exited news hard local without PG DSN"
```

---

### Task 9: Expose safe cutover state in API and Settings

**Files:**
- Modify: `src/api/routes/news.py`
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Modify: `apps/arkscope-web/src/marketDataDisplay.ts`
- Test: `tests/test_news_settings_route.py`
- Test: `apps/arkscope-web/src/marketDataDisplay.test.ts`

- [ ] **Step 1: Write API tests**

```python
body = client.get("/news/status").json()
assert body["write_route"] == "normalized"
assert body["news_hard_local"] is True
assert body["pg_news_route_available"] is False
assert client.put(
    "/news/settings/normalized-writes", json={"enabled": False}
).status_code == 409
```

Also assert permission enforcement and that post-exit `set_use_local_news(false)` returns 409.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_news_settings_route.py`

- [ ] **Step 3: Extend backend state contract**

Add `normalized_writes_setting`, env override, `write_route`, `news_pg_exit_completed`,
`news_hard_local`, and `pg_news_route_available`. Add permission-gated normalized-write PUT.
Never expose a post-exit action that can select PG.

- [ ] **Step 4: Update Settings UI**

Before exit show both legacy-local and normalized test state. After exit show locked status:

```text
新聞寫入: Normalized SQLite + legacy local projection
PostgreSQL: 已退出（不可回退到 PG）
新聞讀取: Legacy local compatibility surface (N8b pending)
```

- [ ] **Step 5: Verify and commit**

Run: `pytest -q tests/test_news_settings_route.py`

Run: `cd apps/arkscope-web && npm test -- --run marketDataDisplay.test.ts && npm run typecheck`

```bash
git add src/api/routes/news.py tests/test_news_settings_route.py \
  apps/arkscope-web/src/api.ts apps/arkscope-web/src/Settings.tsx \
  apps/arkscope-web/src/marketDataDisplay.ts apps/arkscope-web/src/marketDataDisplay.test.ts
git commit -m "feat: expose normalized news cutover state"
```

---

### Task 10: Retire only news PG sync/mirror scheduling

**Files:**
- Modify: `src/market_data_admin.py`
- Modify: `src/service/data_scheduler.py`
- Test: `tests/test_market_data_admin.py`
- Test: `tests/test_data_scheduler.py`

- [ ] **Step 1: Write domain-selective tests**

```python
result = incremental_update(domains=("prices", "iv", "fundamentals"))
assert result["news"]["skipped"] == "domain disabled"
assert calls == ["prices", "iv", "fundamentals"]
```

Post-exit IBKR test must see `collect_ibkr_news_normalized.py`, no
`collect_ibkr_news.py`, no `migrate_to_supabase.py --news`, and no news mirror query.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_market_data_admin.py tests/test_data_scheduler.py -k "exclude_news or post_exit_ibkr"`

- [ ] **Step 3: Add explicit mirror domains**

`incremental_update(..., domains=None)` preserves existing behavior. Omitted domains return typed
skips and execute no PG query. After the exit marker, `_local_refresh` excludes only news. Keep
prices, IV, and fundamentals unchanged. Keep migration scripts for archive/manual use until N9.

- [ ] **Step 4: Verify and commit**

Run: `pytest -q tests/test_market_data_admin.py tests/test_data_scheduler.py tests/test_daily_update_wrapper.py`

```bash
git add src/market_data_admin.py src/service/data_scheduler.py \
  tests/test_market_data_admin.py tests/test_data_scheduler.py
git commit -m "feat: retire news from PG mirror scheduling"
```

---

### Task 11: Wire guarded begin/finalize profile transitions

**Files:**
- Modify: `src/news_normalized/cutover.py`
- Modify: `scripts/migration/news_n8a_cutover.py`
- Test: `tests/test_news_n8a_cutover.py`

- [ ] **Step 1: Write transition tests**

Begin must set `use_normalized_news_writes=true` but not the exit marker. Finalize requires exact
`passed` values for Polygon, Finnhub, IBKR, projection parity, and PG-unreachable checks, then sets
`news_pg_exit_completed=true`. Rollback is allowed only from `testing`.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_news_n8a_cutover.py -k "begin or finalize or rollback"`

- [ ] **Step 3: Implement idempotent cross-store sequence**

Begin order: fingerprint -> backup -> audit row -> normalized profile flag. Finalize order:
validation JSON -> completed audit row -> exit profile marker. If the final profile write fails,
the run remains safely repeatable. Never write global `use_local_market_strict`.

- [ ] **Step 4: Verify and commit**

Run: `pytest -q tests/test_news_n8a_cutover.py tests/test_news_normalized_routing.py tests/test_news_settings_route.py`

```bash
git add src/news_normalized/cutover.py scripts/migration/news_n8a_cutover.py \
  tests/test_news_n8a_cutover.py
git commit -m "feat: orchestrate guarded news PG exit"
```

---

### Task 12: Full offline verification and documentation gate

**Files:**
- Modify: `docs/design/NEWS_DIRECT_LOCAL_PLAN.md`
- Modify: `docs/design/PG_EXIT_COMPLETION_PLAN.md`

- [ ] **Step 1: Run focused backend suite**

```bash
pytest -q tests/test_news_normalized_*.py tests/test_news_n8a_cutover.py \
  tests/test_normalized_ibkr_worker.py tests/test_data_scheduler.py \
  tests/test_market_data_admin.py tests/test_sqlite_backend.py \
  tests/test_sa_routing.py tests/test_news_settings_route.py \
  tests/test_news_pg_unreachable.py
```

Expected: all hermetic tests pass; configured live-IBKR tests may skip.

- [ ] **Step 2: Run frontend and hygiene checks**

```bash
cd apps/arkscope-web && npm test -- --run && npm run typecheck && npm run build
python -m compileall -q src/news_normalized src/service/data_scheduler.py \
  scripts/collection/collect_ibkr_news_normalized.py scripts/migration/news_n8a_cutover.py
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 3: Correct stale docs without claiming live completion**

Record N7 live, scorer outside PG exit, N8a code built but not live, N8b pending, and the
news-specific hard-local correction. Then commit:

```bash
git add docs/design/NEWS_DIRECT_LOCAL_PLAN.md docs/design/PG_EXIT_COMPLETION_PLAN.md
git commit -m "docs: record news N8a implementation gate"
```

---

### Task 13: Hard-gated live cutover

**Files/state:**
- Live: `data/market_data.db`, `data/profile_state.db`
- Backup: a unique path exported as `N8A_BACKUP`, using a microsecond UTC timestamp.
- Modify after success: the two design status documents

Do not run this task after implementation alone. Require independent code review, two identical
read-only previews, and explicit operator approval.

- [ ] **Step 1: Confirm quiet window and run preview twice**

```bash
python scripts/migration/news_n8a_cutover.py preview \
  --db data/market_data.db --output /tmp/news-n8a-preview-1.json
python scripts/migration/news_n8a_cutover.py preview \
  --db data/market_data.db --output /tmp/news-n8a-preview-2.json
cmp /tmp/news-n8a-preview-1.json /tmp/news-n8a-preview-2.json
```

Require identical fingerprint, `unmapped_legacy_rows=0`, no DB mutation, and explained
normalized-only count (baseline 7,100).

- [ ] **Step 2: Review exact gate and begin**

After explicit approval:

```bash
export N8A_BACKUP="data/market_data.db.bak-pre-news-n8a-$(date -u +%Y%m%dT%H%M%S%6NZ).db"
python scripts/migration/news_n8a_cutover.py begin \
  --db data/market_data.db \
  --expected-report /tmp/news-n8a-preview-1.json \
  --backup "$N8A_BACKUP" \
  --confirm-scheduler-paused
```

- [ ] **Step 3: Run bounded provider smokes**

Use one ticker/small budget for Polygon, Finnhub, then isolated IBKR. Rerun each and prove
idempotence. Validate projection snippet parity, both FTS missing/orphan counts zero, body-state
invariants, projection map ownership, and no back-projection of historical normalized-only rows.

- [ ] **Step 4: Run no-DSN/PG-unreachable E2E**

With scheduler disabled except explicit smoke, start sidecar without `DATABASE_URL`. Verify feed,
ticker query, FTS search, stats, status, and direct writes never touch PG. Verify IV/fundamentals
were not globally marked strict or complete.

- [ ] **Step 5: Finalize and observe scheduler**

Finalize with five passed validations, confirm post-exit false toggles are blocked, resume scheduler,
and observe one cycle: all news normalized-local; IV/fundamentals unchanged; no news PG sync/mirror.

- [ ] **Step 6: Record live evidence**

Commit timestamp, run ID, fingerprint, backup, smoke/invariant counts, and the honest status:
news-domain PG exit complete; ArkScope-wide PG exit incomplete; N8b pending.

Retain N7/N8a backups through N8b. Do not delete legacy tables/projection, Parquet, scorer, or old
migration scripts in N8a.
