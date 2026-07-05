# Dead-Code / UI Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove post-PG-exit dead runtime paths and stale Data Sources/UI copy without deleting protected macro/SA capabilities or legacy provenance flags.

**Architecture:** This is a sweep, not a product redesign. Runtime-dead PG readers become explicit tombstone stubs or unreachable-code removals at existing boundaries; UI cleanup removes misleading controls/copy that no longer map to live behavior; one live profile cleanup is approval-gated and data-only. Legacy `use_local_*` keys remain as provenance unless this plan explicitly says otherwise.

**Tech Stack:** Python 3, pytest, SQLite local stores, React/TypeScript/Vitest, existing PG-unreachable smoke.

---

## Map Check

- This work is on the active queue created by the PG-exit, S-J, and macro-snapshot closeouts.
- It does **not** reopen PG-exit: PG remains archive-only; no live PG fallback is reintroduced.
- It does **not** enable FRED refresh, Finnhub calendars, C-2/C-3 macro context, or IBKR long-catch-up changes.
- It does **not** remove macro capability. `src/macro_calendar/`, `/macro/*`, `get_macro_value`, `get_economic_calendar`, and `scripts/p1_2/` are protected by `MACRO_FRED_PRODUCT_SEMANTICS.md` §6.7.

## Files

Expected code/test files:

- Modify `src/tools/backends/db_backend.py` — replace already-dropped PG SA table readers/writers with explicit retired stubs; keep method names so old imports fail safe.
- Modify `src/service/sa_market_news_health.py` — remove the non-local PG health branch after SA local-default collapse.
- Modify `tests/test_db_backend.py` or create `tests/test_db_backend_retired_pg_sa.py` — prove retired SA stubs never open PG.
- Modify `tests/test_sa_local_readers.py` — flip the old PG-mode health assertion to a no-PG retired-path assertion.
- Modify `src/app_records_store.py`, `src/tools/backends/local_market_backend.py`, `src/tools/macro_calendar_tools.py`, `src/tools/registry.py`, and bridge descriptions if grep shows stale current-runtime copy.
- Modify `apps/arkscope-web/src/api.ts`, `apps/arkscope-web/src/Settings.tsx`, `apps/arkscope-web/src/marketDataDisplay.ts`, and their tests for unreachable post-PG-exit UI/API helpers and stale labels.
- Modify `tests/test_tools.py`, `tests/test_agents.py`, `tests/test_analyst_tools.py`, and `tests/test_sec_tools.py` only where they encode stale tool counts/names.
- Modify `docs/design/PROJECT_PRIORITY_MAP.md` and this plan for closeout.

Live data-only cleanup:

- `data/profile_state.db` `scheduler_state` row for the stale durable `price_backfill` `"REAL RUNNER CALLED"` marker, only after an exact-match dry run and explicit approval. No code should be added solely to keep this one-off cleanup.

## Stop-Loss Triggers

Stop and report before continuing if any of these happen:

- A grep shows a live runtime caller still depending on `DatabaseBackend` PG SA implementations rather than `SACaptureDatabaseBackend`.
- A test requires deleting macro/SA capability rather than changing stale copy.
- `REAL RUNNER CALLED` cleanup finds more than one row, a different source, or a row whose `last_error`/`last_result` does not exactly match the stale marker.
- Any full A/B run has a head-only deterministic failure.
- A proposed UI removal has a live import/callsite outside tests.

## Review Gates

1. `rg -n "REAL RUNNER CALLED" src apps tests docs --glob '!docs/superpowers/plans/**'` returns no code/test hit after the live cleanup record is documented.
2. `rg -n "Default-OFF|inherited PG behaviour|requires PostgreSQL DAL backend|Requires macro_calendar.enabled=true" src apps tests` returns only explicitly allowed historical docs or economic-calendar-only copy.
3. `rg -n "bootstrapMarketData|updateMarketData|validateMarketData|setUseLocalMarket|setUseLocalMacro|hintRows" apps/arkscope-web/src` shows no unreachable exports/paths, or the remaining hits are justified in comments/tests.
4. `pytest tests/test_db_backend_retired_pg_sa.py tests/test_sa_local_readers.py -q` passes.
5. `pytest tests/test_tools.py tests/test_agents.py tests/test_analyst_tools.py tests/test_sec_tools.py -q` passes or has only already-known live-data failures with an A/B-identical set.
6. Frontend gates pass: `npm test -- SettingsProviderConfig.test.ts SettingsPostPgExitStorage.test.ts marketDataDisplay.test.ts` and `npm run build`.
7. PG-unreachable smoke stays green: `ARKSCOPE_DISABLE_SCHEDULER=1 python -m scripts.smoke.pg_unreachable_e2e`.
8. Full A/B failure set is identical except for up to two named base-only ledger
   fixes that this plan intentionally repairs:
   `tests/test_agents.py::TestAnthropicToolSchemas::test_tool_names` and
   `tests/test_sec_tools.py::TestBridgeIntegration::test_analysis_category_6`.
   Zero head-only deterministic failures are allowed.

---

## Task 1: Retire PG SA Runtime Readers

**Files:**

- Modify: `src/tools/backends/db_backend.py`
- Modify: `src/service/sa_market_news_health.py`
- Test: `tests/test_db_backend_retired_pg_sa.py`
- Test: `tests/test_sa_local_readers.py`

- [ ] **Step 1: Write retired-stub tests**

Create `tests/test_db_backend_retired_pg_sa.py`:

```python
from datetime import datetime, timezone

from src.tools.backends.db_backend import DatabaseBackend


class _NoPGSA(DatabaseBackend):
    def __init__(self):
        pass

    def _get_conn(self):  # pragma: no cover - assertion surface
        raise AssertionError("retired PG SA method attempted to open PG")


def test_retired_pg_sa_methods_do_not_connect():
    b = _NoPGSA()
    now = datetime(2026, 7, 6, tzinfo=timezone.utc)

    assert b.apply_sa_refresh("current", [], now, now) == 0
    assert b.record_sa_refresh_failure("current", now, "x") is None
    assert b.query_sa_picks() == []
    assert b.get_sa_pick_detail("NVDA") is None
    assert b.update_sa_pick_detail("NVDA", "2026-01-01", "body") is False
    assert b.get_sa_refresh_meta() == {}
    assert b.upsert_sa_market_news([]) == 0
    assert b.query_sa_market_news() == []
    assert b.query_sa_market_news_recent_ids() == []
    assert b.query_sa_market_news_need_detail() == []
    assert b.invalidate_dirty_sa_market_news_detail() == 0
    assert b.save_sa_market_news_detail("n1", "body") is False
    assert b.upsert_sa_articles_meta([]) == 0
    assert b.sanitize_corrupted_sa_comments_counts() == 0
    assert b.cleanup_mixed_null_date_comment_duplicates() == {
        "groups_processed": 0,
        "comments_deleted": 0,
        "parent_links_repointed": 0,
    }
    assert b.save_article_with_comments("a1", "body", []) == {
        "ok": False,
        "synced_picks": 0,
        "prepared_comments": 0,
        "stored_comments_total": 0,
        "net_new_comments": 0,
        "reason": "pg_sa_retired",
    }
    assert b.update_article_comments("a1", []) == {
        "prepared_comments": 0,
        "stored_comments_total": 0,
        "net_new_comments": 0,
    }
    assert b.audit_unresolved_symbols() == {"unresolved_symbols": [], "resolved_by_fulltext": 0}
    assert b.query_sa_articles() == []
    assert b.get_sa_article_with_comments("a1") is None
```

In `tests/test_sa_local_readers.py`, replace `TestHealthSplit.test_pg_mode_dispatch_unchanged` with:

```python
def test_non_local_sa_backend_does_not_query_pg(pg_dal, pg_calls):
    from src.service.sa_market_news_health import compute_market_news_health

    report = compute_market_news_health(pg_dal)

    assert not pg_calls
    assert report["severity"] == "critical"
    assert any(r["code"] == "db_unavailable" for r in report["reasons"])
    assert "SA capture local backend unavailable" in report["reasons"][0]["message"]
```

- [ ] **Step 2: Run RED**

Run:

```bash
pytest tests/test_db_backend_retired_pg_sa.py tests/test_sa_local_readers.py::TestHealthSplit::test_non_local_sa_backend_does_not_query_pg -q
```

Expected: FAIL. The new retired-stub test opens PG for at least one SA method, and the health test records the old PG branch call.

- [ ] **Step 3: Implement retired SA stubs**

In `src/tools/backends/db_backend.py`, replace the PG-backed Seeking Alpha method bodies (`apply_sa_refresh` through `get_sa_article_with_comments`) with explicit stubs matching the test returns. Keep method names and signatures. Remove private helpers that are no longer called by any remaining method in this class.

Use this comment above the section:

```python
    # ================================================================
    # Seeking Alpha (retired PG surface)
    # ================================================================
    # PG sa_* tables were archived/dropped in N9 batch-1. Runtime SA reads/writes
    # route through SACaptureDatabaseBackend / sa_capture.db. These methods remain
    # as tombstone-compatible stubs so old DatabaseBackend call sites fail closed
    # without opening PG.
```

In `src/service/sa_market_news_health.py`:

- Remove `_HEALTH_SQL` if it is used only by the PG branch.
- In `compute_market_news_health`, after resolving `backend`, require `getattr(backend, "_sa_db", None)` before calling `_run_health_query`.
- If `_sa_db` is absent, return `_db_unavailable_report(now, merged_thresholds, error="SA capture local backend unavailable; PG sa_* health path is retired.")`.
- Simplify `_run_health_query` to the local `_query_capture_stats_local` path plus `_query_extension_run` degradation.

- [ ] **Step 4: Run GREEN**

Run:

```bash
pytest tests/test_db_backend_retired_pg_sa.py tests/test_sa_local_readers.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tools/backends/db_backend.py src/service/sa_market_news_health.py tests/test_db_backend_retired_pg_sa.py tests/test_sa_local_readers.py
git commit -m "refactor: retire pg seeking-alpha dead paths"
```

---

## Task 2: Copy, Comments, And Macro Guardrail Sweep

**Files:**

- Modify: `src/app_records_store.py`
- Modify: `src/tools/backends/local_market_backend.py`
- Modify: `src/tools/macro_calendar_tools.py`
- Modify: `src/tools/registry.py`
- Modify: `src/agents/anthropic_agent/tools.py`
- Test: existing focused tests plus grep gate

- [ ] **Step 1: Write grep gate command**

Run the current grep to capture RED inventory:

```bash
rg -n "Default-OFF|inherited PG behaviour|requires PostgreSQL DAL backend|Requires macro_calendar.enabled=true|設定尚未翻成預設|本地功能未啟用（不會 fallback PG）" src apps tests
```

Expected before implementation: hits in `app_records_store.py`, `local_market_backend.py`, tool descriptions, and UI label tests.

- [ ] **Step 2: Update stale comments and descriptions**

Make these surgical text changes:

- `src/app_records_store.py`: change the `USE_LOCAL_RECORDS_KEY` comment from "Default-OFF" to "legacy provenance key; runtime defaults local after PG-exit closeout".
- `src/tools/backends/local_market_backend.py`: remove "Everything else ... inherited PG behaviour" from the class docstring. Replace with wording that local-market overrides market reads, while app-records/SA/job-runs now have their own local stores and remaining inherited PG methods are archive/tombstone stubs.
- `src/tools/macro_calendar_tools.py`: keep `get_economic_calendar` disabled wording, but ensure `get_macro_value` descriptions do not say it requires `macro_calendar.enabled=true`.
- `src/tools/registry.py` and `src/agents/anthropic_agent/tools.py`: for `get_macro_value`, change description from "Requires macro_calendar.enabled=true" to "Reads the local FRED snapshot even when automatic refresh is disabled." Do not change `get_economic_calendar` unless its description incorrectly claims FRED snapshot behavior.

- [ ] **Step 3: Update local label copy if still stale**

If `apps/arkscope-web/src/marketDataDisplay.ts` still labels a default-collapsed path as "設定尚未翻成預設", replace it with a provenance-aware label:

```ts
return "本地權威（legacy flag 未設定；PG fallback 已退役）";
```

If `macroRoutingLabel()` is still used for a storage route panel and says "本地功能未啟用", replace the inactive local-default case with:

```ts
return "本地快照讀取可用；自動刷新未啟用";
```

Update `apps/arkscope-web/src/marketDataDisplay.test.ts` expected strings exactly.

- [ ] **Step 4: Run focused tests and grep**

Run:

```bash
pytest tests/test_macro_calendar_read.py tests/test_tools.py::TestRegistry -q
npm test -- marketDataDisplay.test.ts SettingsProviderConfig.test.ts
rg -n "Default-OFF|inherited PG behaviour|requires PostgreSQL DAL backend|Requires macro_calendar.enabled=true|設定尚未翻成預設" src apps tests
```

Expected: tests PASS; grep hits only for allowed historical docs or `get_economic_calendar`.

- [ ] **Step 5: Commit**

```bash
git add src/app_records_store.py src/tools/backends/local_market_backend.py src/tools/macro_calendar_tools.py src/tools/registry.py src/agents/anthropic_agent/tools.py apps/arkscope-web/src/marketDataDisplay.ts apps/arkscope-web/src/marketDataDisplay.test.ts
git commit -m "docs: align local-first runtime copy"
```

---

## Task 3: Frontend Dead API And Hint Path Sweep

**Files:**

- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Modify: `apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts` if labels change

- [ ] **Step 1: Prove helpers are orphaned**

Run:

```bash
rg -n "bootstrapMarketData|updateMarketData|validateMarketData|setUseLocalMarket|setUseLocalMacro" apps/arkscope-web/src --glob '*.ts' --glob '*.tsx'
```

Expected: only definitions in `api.ts`. If any live consumer remains, stop and report.

- [ ] **Step 2: Remove orphan exports**

Remove these exports from `apps/arkscope-web/src/api.ts` if Step 1 proves no consumers:

- `bootstrapMarketData`
- `updateMarketData`
- `validateMarketData`
- `setUseLocalMarket`
- `setUseLocalMacro`

Do not remove types still used by status routes.

- [ ] **Step 3: Remove unreachable provider-config hintRows path**

In `apps/arkscope-web/src/Settings.tsx`, the IBKR grouped renderer owns all `client_id_domains` display. The generic table path's `hintRows` / sub-row logic is now unreachable. Remove:

- `const hintRows = rows.filter(...)`
- `rowSpan={rows.length + hintRows}` arithmetic
- the extra `Fragment` sub-row that renders generic `client_id_domains` hints

Keep the grouped IBKR block (`data-testid='ibkr-config-group'`) and its tests intact.

- [ ] **Step 4: Run frontend tests**

Run:

```bash
npm test -- SettingsProviderConfig.test.ts SettingsPostPgExitStorage.test.ts marketDataDisplay.test.ts
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/SettingsProviderConfig.test.ts apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts
git commit -m "refactor: remove retired data-source ui helpers"
```

---

## Task 4: Tool Registry Test Ledger Cleanup

**Files:**

- Modify: `tests/test_tools.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_analyst_tools.py`
- Modify: `tests/test_sec_tools.py`

- [ ] **Step 1: Reproduce stale ledger failures**

Run:

```bash
pytest tests/test_tools.py::TestRegistry::test_tool_names tests/test_agents.py::TestAnthropicToolSchemas::test_tool_names tests/test_analyst_tools.py::TestBridgeIntegration tests/test_sec_tools.py::TestBridgeIntegration -q
```

Expected before implementation: at least one stale tool-name/count assertion fails. `get_ticker_data_coverage` is already registered in both bridge layers and should be treated as a test-ledger lag, not a feature gap.

- [ ] **Step 2: Update expected names/counts only**

Apply only these kinds of changes:

- Add `"get_ticker_data_coverage"` to stale expected-name sets that omit it.
- Update count assertions to match `create_default_registry().list_all()`, `list_by_category("analysis")`, and bridge tool exports.
- Do not delete a bridge test wholesale if it still proves a real bridge includes a tool.
- Do not change runtime registry code in this task unless a test proves a real missing registration.

- [ ] **Step 3: Run focused tests**

Run:

```bash
pytest tests/test_tools.py tests/test_agents.py tests/test_analyst_tools.py tests/test_sec_tools.py -q
```

Expected: PASS, or the same known live-data failures as base. If any failure is caused by the ledger change, stop.

- [ ] **Step 4: Commit**

```bash
git add tests/test_tools.py tests/test_agents.py tests/test_analyst_tools.py tests/test_sec_tools.py
git commit -m "test: refresh tool registry ledgers"
```

---

## Task 5: Live Scheduler-State Marker Cleanup

**Files:**

- No repo code changes expected.
- Docs closeout records the before/after evidence.

This is a live data mutation and must be approval-gated. It cleans only the stale durable `price_backfill` marker observed during macro snapshot live verification:

```text
source = price_backfill
last_status = failed
last_error contains REAL RUNNER CALLED
```

- [ ] **Step 1: Dry-run exact match**

Run read-only:

```bash
python - <<'PY'
import json, sqlite3
from pathlib import Path
db = Path("data/profile_state.db")
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT source,last_status,last_error,last_result,updated_at FROM scheduler_state "
    "WHERE source=? AND (last_error LIKE ? OR last_result LIKE ?)",
    ("price_backfill", "%REAL RUNNER CALLED%", "%REAL RUNNER CALLED%"),
).fetchall()
print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
conn.close()
PY
```

Expected: exactly one row. If zero or more than one row, stop and report.

- [ ] **Step 2: Approval checkpoint**

Ask the user to approve clearing only the matched row's stale failure fields. Do not mutate before approval.

- [ ] **Step 3: Backup then clear exact row**

After approval:

```bash
cp data/profile_state.db data/profile_state.db.bak-pre-dead-code-sweep-scheduler-marker-$(date -u +%Y%m%dT%H%M%SZ).db
python - <<'PY'
import sqlite3
from pathlib import Path
db = Path("data/profile_state.db")
conn = sqlite3.connect(db)
cur = conn.execute(
    "UPDATE scheduler_state "
    "SET last_status=NULL, last_error=NULL, last_result=NULL, continuation=NULL, updated_at=datetime('now') "
    "WHERE source=? AND last_status='failed' AND (last_error LIKE ? OR last_result LIKE ?)",
    ("price_backfill", "%REAL RUNNER CALLED%", "%REAL RUNNER CALLED%"),
)
if cur.rowcount != 1:
    conn.rollback()
    raise SystemExit(f"expected one row, updated {cur.rowcount}")
conn.commit()
print({"updated": cur.rowcount})
conn.close()
PY
```

- [ ] **Step 4: Verify no marker remains**

Run:

```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect("file:data/profile_state.db?mode=ro", uri=True)
n = conn.execute(
    "SELECT COUNT(*) FROM scheduler_state WHERE last_error LIKE ? OR last_result LIKE ?",
    ("%REAL RUNNER CALLED%", "%REAL RUNNER CALLED%"),
).fetchone()[0]
print({"real_runner_called_rows": n})
conn.close()
PY
```

Expected: `{"real_runner_called_rows": 0}`.

---

## Task 6: Final Gates And Docs Closeout

**Files:**

- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: this plan

- [ ] **Step 1: Run code gates**

Run:

```bash
pytest tests/test_db_backend_retired_pg_sa.py tests/test_sa_local_readers.py tests/test_tools.py tests/test_agents.py tests/test_analyst_tools.py tests/test_sec_tools.py -q
npm test -- SettingsProviderConfig.test.ts SettingsPostPgExitStorage.test.ts marketDataDisplay.test.ts
npm run build
ARKSCOPE_DISABLE_SCHEDULER=1 python -m scripts.smoke.pg_unreachable_e2e
```

Expected: PASS or known A/B-identical live-data failures only.

- [ ] **Step 2: Run grep gates**

Run:

```bash
rg -n "REAL RUNNER CALLED" src apps tests docs --glob '!docs/superpowers/plans/**'
rg -n "Default-OFF|inherited PG behaviour|requires PostgreSQL DAL backend|Requires macro_calendar.enabled=true" src apps tests
rg -n "bootstrapMarketData|updateMarketData|validateMarketData|setUseLocalMarket|setUseLocalMacro|hintRows" apps/arkscope-web/src
```

Expected: no live-code hits except explicitly reviewed economic-calendar descriptions or historical docs.

- [ ] **Step 3: Full A/B**

Run the standard virgin-to-virgin A/B suite against the branch base and head.
Expected: identical failure set except up to two named base-only entries:

- `tests/test_agents.py::TestAnthropicToolSchemas::test_tool_names`
- `tests/test_sec_tools.py::TestBridgeIntegration::test_analysis_category_6`

These two are intentional stale-ledger fixes from Task 4. Any head-only deterministic
failure blocks merge. The existing `TestAnthropicToolExecution` / OpenAI live-data
setup errors are not ledger fixes and should remain A/B-identical.

- [ ] **Step 4: Docs closeout**

Update this plan header to `LIVE COMPLETE` and insert a newest-first `PROJECT_PRIORITY_MAP.md` §10 entry:

- branch/commit range;
- SA tombstone + health branch removed;
- UI/API dead helpers removed;
- tool ledger corrected;
- `REAL RUNNER CALLED` cleanup result and backup path, or "not present" if dry-run found none;
- gates and A/B result;
- next queue: IBKR news long-catch-up audit; future decisions remain FRED refresh cadence, Finnhub calendar enablement, C-2/C-3 macro context.

- [ ] **Step 5: Commit closeout**

```bash
git add docs/superpowers/plans/2026-07-06-dead-code-ui-sweep.md docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: close dead-code ui sweep"
```

---

## Self-Review Notes

- Protected capability boundary is explicit: macro and SA runtime capability stays; only dead PG/archive paths and stale copy are swept.
- Live data mutation is isolated in Task 5 and requires explicit user approval.
- Legacy `use_local_*` profile keys are not removed. They remain provenance after the local-default collapses.
- The plan does not touch model list, token monitoring, IBKR catch-up behavior, FRED refresh cadence, Finnhub calendars, or C-2/C-3 macro integration.
