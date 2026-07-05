# PG-Exit N9 Batch-3 Prices Drop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** ✅ **LIVE COMPLETE 2026-07-05.** PG `prices` (2,314,293 rows, frozen at `2026-07-02 14:15 UTC`, row fingerprint `e4b8e5d304bd45775f9c33f8986deeda`) and its dependent function `get_recent_prices(character varying,character varying,integer)` were dropped in one no-`CASCADE` transaction after explicit user approval.
>
> **Live record:**
> - Approved evidence fingerprint: `028efacdc3a41f917eb6fa795ca97e5dff3e3c7f3508715d2d133a37711b902b` (second package; the first was invalidated — see the invalidated-packet note below).
> - Archive: `data/pg_archive/n9_batch3_prices_20260705T010022Z/` — dump sha256 `76b6cb6d33a5b66d861612d24746517b358bb0c3f75c923bfa0bbe0731b27f7b`, `function_ddl.sql` included, two-stage restore proof (`pg_restore` + function DDL apply) `ok:true`, `mismatches:[]` (`restore_proof.json`).
> - Preview ×2 byte-identical (each consuming a different green E2E report file); reviewer independently reproduced the PG row fingerprint hours apart via a second path.
> - Drop: 13-check validation → in-CLI re-preview fingerprint match → single txn `DROP FUNCTION` → `DROP TABLE` → in-txn catalog verification → commit. Output `{"status": "dropped", "dropped_tables": 1}`.
> - Postcheck `ok:true`, `targets_still_present:[]`, `protected_missing:[]`.
> - Pre-drop E2E ×2: `scratchpad/pg-unreachable-e2e-batch3-20260705T005907Z/`; post-drop E2E ×2: `scratchpad/pg-unreachable-e2e-post-batch3-20260705T012220Z/` — all four runs `ok:true`, `pg_attempts:[]`, 22/22 checks. Local NVDA smoke: 104 bars, no PG attempt.
> - PG public schema now contains exactly the three protected app-record archive tables: `agent_memories`, `agent_queries`, `research_reports`.

> **Offline gate:** `pytest tests/test_db_backend_retired_prices.py tests/test_n9_batch3_prices_drop.py tests/test_pg_unreachable_e2e.py tests/test_sqlite_backend.py::test_p0c_prices_miss_is_honest_empty_no_pg tests/test_provider_health.py tests/test_data_scheduler.py -q` -> 134 passed; `python -m compileall scripts/migration/n9_batch3_prices_drop.py scripts/smoke/pg_unreachable_e2e.py` -> pass; `git diff --check` -> pass; batch-3 grep classifier -> blockers 0 / allowed hits 197.

> **Invalidated live packet:** evidence fingerprint `b0ca91b932484191a551f0679cdbf12f2f4233d614f768540cd8a15b8e69e24e` / archive `data/pg_archive/n9_batch3_prices_20260705T003318Z/` is rejected because `get_recent_prices(character varying,character varying,integer)` has a normal rowtype dependency on `prices`. Task 4-5 must be rerun after this fixup to produce a new approval packet.

**Goal:** Archive and physically drop the final PG market-data table (`prices`) after proving the local price store is the runtime authority and the PG `prices` table is archive-only.

**Architecture:** Batch-3 reuses the N9 destructive-drop discipline: offline hardening first, read-only evidence preview, targeted `pg_dump`, restore proof into a disposable DB, explicit user approval, single-transaction no-`CASCADE` drop, postcheck, and pre/post PG-unreachable E2E smoke. Unlike batch-1/2, the archive semantics are narrower: the PG `prices` dump is a frozen pre-cutover mirror archive, not a backup of current local prices.

**Tech Stack:** Python, psycopg2, PostgreSQL catalog queries, `pg_dump`/`pg_restore`/`psql`, local SQLite `market_data.db`, pytest, existing `scripts/smoke/pg_unreachable_e2e.py`.

---

## Map Check

Active authority:

- `docs/design/PROJECT_PRIORITY_MAP.md` P0-B: PG-unreachable E2E is green; next PG-exit item is batch-3 PG `prices` archive/drop.
- `docs/design/PG_EXIT_REMAINDER_SCOPING.md` §8: N9 batch-1 and batch-2 are live-complete; PG `prices` remains archive/rollback only and needs a fresh N9-style dump/restore/drop packet.
- `docs/design/PG_EXIT_COMPLETION_PLAN.md`: normal runtime no longer needs PG; physical PG `prices` remains the last market-data PG object before full archive-only completion.
- `docs/design/PG_EXIT_PG_UNREACHABLE_E2E_PLAN.md`: pre/post batch-3 must reuse the PG-unreachable smoke as a permanent gate.

This plan is on-map and does not change product priority. App-record archive tables stay out of scope.

## Scope

In scope:

- Stub the final `DatabaseBackend` PG prices read methods before the table is dropped.
- Add a dedicated batch-3 archive/drop CLI or a clearly separated mode that targets only PG `prices`.
- Produce an evidence report with PG `prices` row count/fingerprint/latest timestamp and local `market_data.db.prices` authority stats.
- Write an archive manifest that explicitly says the dump is a frozen **pre-cutover mirror archive**, not a current local-price backup.
- Prove the PG archive restores with matching row count and row fingerprint.
- Drop PG `prices` only after explicit approval.
- Run PG-unreachable E2E smoke before and after the drop.
- Update docs after live drop.

Out of scope:

- Do not touch app-record archive tables: `agent_queries`, `research_reports`, `agent_memories`.
- Do not mutate local `market_data.db` prices; current local price backups are the local DB backup chain, not this PG dump.
- Do not reintroduce PG price sync or an archive-price writer.
- Do not change scheduler/provider behavior except for tests proving it remains direct-local.
- Do not decide app-record archive policy.

## Critical Semantics

### PG `prices` Dump Meaning

The batch-3 dump is **not** a backup of current ArkScope prices.

It is a frozen archive of the old PG mirror as it existed before and during P0-C cutover. Current facts at plan time:

- PG `prices`: 2,314,293 rows, last known bar `2026-07-02T14:15`, archive/rollback only.
- Local `market_data.db.prices`: runtime authority since P0-C; rows already exceed the PG mirror and continue to grow through direct-local ingestion.

Restoring the batch-3 PG dump restores the old mirror table only. It does **not** restore current local prices. Current price data recovery belongs to the local `market_data.db` backup/portability chain.

This sentence must appear in:

- `docs/design/PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md`
- the archive manifest (`manifest.json`)
- the live record in `PG_EXIT_REMAINDER_SCOPING.md`

### Protected Tables

Batch-1 and batch-2 CLIs protected `prices` because it was still retained. Batch-3 must consciously flip that protection:

- Batch-3 target tables: `prices`
- Batch-3 protected/excluded tables: `agent_queries`, `research_reports`, `agent_memories`
- `prices` must not appear in batch-3 `EXCLUDED_TABLES` / `PROTECTED_TABLES`.
- The three app-record archive tables must remain protected.

If implementation reuses batch-1/batch-2 helpers, add a test that proves the batch-3 manifest removes `prices` from protection while retaining the app-record tables.

### Post-Drop Runtime Semantics

After the drop, no normal runtime route may have a PG `prices` fallback. The following PG methods become dead/archive stubs in this batch:

- `src/tools/backends/db_backend.py::DatabaseBackend.query_prices`
- `src/tools/backends/db_backend.py::DatabaseBackend.query_health_stats` prices SQL

The app-record methods in `DatabaseBackend` remain retained for the separate app-record archive decision.

## Non-Negotiable Gates

1. **No live drop from a plan commit.** Live drop requires reviewed evidence, restore proof, and explicit user approval.
2. **No `CASCADE`.** Unexpected dependencies must rollback and amend the target/dependency evidence.
3. **No dump-only rollback basis.** Restore proof is mandatory.
4. **No stale evidence.** Drop must re-run preview and compare the reviewed fingerprint before any `DROP`.
5. **No provider writes during destructive window.** Scheduler, manual writers, and native host must be quiet until postcheck + post-drop E2E complete.
6. **No PG runtime fallback after drop.** PG-unreachable E2E smoke must pass pre-drop and post-drop with `pg_attempts:[]`.
7. **No app-record damage.** Postcheck must prove `agent_queries`, `research_reports`, and `agent_memories` still exist.

## File Map

Create:

- `docs/design/PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md` - this plan.
- `scripts/migration/n9_batch3_prices_drop.py` - evidence/dump/restore/drop/postcheck CLI.
- `tests/test_n9_batch3_prices_drop.py` - hermetic tests for manifest semantics, target/protected table sets, evidence fingerprinting, dump command, restore proof, drop validation, and postcheck.

Modify:

- `src/tools/backends/db_backend.py` - stub PG `query_prices()` and remove the last prices SQL from `query_health_stats()`.
- `tests/test_db_backend.py` or a new `tests/test_db_backend_retired_prices.py` - pin no-PG behavior for retired price methods while preserving app-record archive methods.
- `docs/design/PG_EXIT_REMAINDER_SCOPING.md` - after live drop, record archive path, fingerprint, dump semantics, and remaining PG objects.
- `docs/design/PROJECT_PRIORITY_MAP.md` - decision log entry for plan opening and, after live, drop completion.
- `docs/design/PG_EXIT_COMPLETION_PLAN.md` - after live drop, mark PG market-data tables fully physically removed.

Do not modify:

- `scripts/migrate_to_supabase.py` except if tests reveal stale `--prices` language after batch-2.
- scheduler/source runtime except if a pre-drop E2E or grep gate proves a live PG price path.
- app-record migration routes.

## Target Manifest

Use this manifest in the batch-3 CLI:

```python
TARGET_TABLES = ("prices",)
TARGET_FUNCTION_SIGNATURES = (
    "get_recent_prices(character varying,character varying,integer)",
)
PROTECTED_TABLES = (
    "agent_queries",
    "research_reports",
    "agent_memories",
)
ARCHIVE_SEMANTIC_NOTE = (
    "This dump is a frozen pre-cutover PG prices mirror archive, not a backup "
    "of current local market_data.db prices. Current price recovery depends on "
    "the local market_data.db backup chain."
)
```

The evidence command must fail if `prices` is listed as protected in the batch-3 mode.
It must also fail if the dependency scan finds any normal `pg_proc` rowtype
dependency on `prices` that is not covered by `TARGET_FUNCTION_SIGNATURES`.

## Task 1 - Stub Final PG Price Runtime Methods

### Intent

Remove the final live `DatabaseBackend` SQL references to PG `prices` before the destructive drop.

### Files

- Modify: `src/tools/backends/db_backend.py`
- Test: `tests/test_db_backend_retired_prices.py` (new) or `tests/test_db_backend.py`

### Red Tests

- [ ] Create `tests/test_db_backend_retired_prices.py`.
- [ ] Add a helper backend whose `_query_df()` and `_get_conn()` fail if touched:

```python
import pandas as pd
import pytest

from src.tools.backends.db_backend import DatabaseBackend


class NoPgDatabaseBackend(DatabaseBackend):
    def __init__(self):
        super().__init__("postgresql://unused")

    def _query_df(self, sql, params=()):
        raise AssertionError(f"PG query must not run: {sql}")

    def _get_conn(self):
        raise AssertionError("PG connection must not be opened")
```

- [ ] Add `test_query_prices_is_retired_stub_after_batch3()`:

```python
def test_query_prices_is_retired_stub_after_batch3():
    backend = NoPgDatabaseBackend()

    out = backend.query_prices("NVDA", interval="15min", days=7)

    assert isinstance(out, pd.DataFrame)
    assert list(out.columns) == ["datetime", "open", "high", "low", "close", "volume"]
    assert out.empty
```

- [ ] Add `test_query_health_stats_no_longer_queries_prices_after_batch3()`:

```python
def test_query_health_stats_no_longer_queries_prices_after_batch3():
    backend = NoPgDatabaseBackend()

    stats = backend.query_health_stats()

    assert stats["prices"] == {"rows": [], "error": None}
    assert stats["news"] == {"rows": [], "error": None}
    assert stats["iv_history"] == {"rows": [], "error": None}
    assert stats["financial_cache"] == {"rows": [], "error": None}
```

- [ ] Add `test_app_record_archive_methods_are_not_removed_by_batch3()`:

```python
def test_app_record_archive_methods_are_not_removed_by_batch3():
    backend = NoPgDatabaseBackend()

    assert hasattr(backend, "insert_report")
    assert hasattr(backend, "query_reports")
    assert hasattr(backend, "get_report_metadata")
    assert hasattr(backend, "insert_memory")
    assert hasattr(backend, "query_memories")
    assert hasattr(backend, "list_memories_meta")
    assert hasattr(backend, "delete_memory")
    assert hasattr(backend, "insert_agent_query")
```

### Verify RED

Run:

```bash
pytest tests/test_db_backend_retired_prices.py -q
```

Expected before implementation: at least `query_prices` and `query_health_stats` tests fail because the methods attempt PG SQL.

### Implementation

- [ ] In `src/tools/backends/db_backend.py`, replace `query_prices()` SQL with a retired stub:

```python
def query_prices(self, ticker: str, interval: str = "15min", days: int = 30) -> pd.DataFrame:
    """Retired PG prices surface; runtime authority is local SQLite after P0-C/batch-3."""
    return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
```

- [ ] Replace `query_health_stats()` with no PG connection:

```python
def query_health_stats(self) -> Dict[str, Any]:
    """Retired PG market-data health surface; provider health reads local stores after N9."""
    return {
        "news": {"rows": [], "error": None},
        "prices": {"rows": [], "error": None},
        "iv_history": {"rows": [], "error": None},
        "financial_cache": {"rows": [], "error": None},
    }
```

- [ ] Update the module docstring to say `prices` is also retired after batch-3, while app-record archive methods remain retained.

### Verify GREEN

Run:

```bash
pytest tests/test_db_backend_retired_prices.py -q
pytest tests/test_pg_unreachable_e2e.py -q
```

Expected: both pass.

### Commit

```bash
git add src/tools/backends/db_backend.py tests/test_db_backend_retired_prices.py
git commit -m "fix: retire pg prices backend methods"
```

## Task 2 - Build Batch-3 Archive/Drop CLI

### Intent

Create a dedicated batch-3 CLI so no one has to mutate batch-1/batch-2 target lists at live time.

### Files

- Create: `scripts/migration/n9_batch3_prices_drop.py`
- Create: `tests/test_n9_batch3_prices_drop.py`

### Red Tests

- [ ] Create `tests/test_n9_batch3_prices_drop.py`.
- [ ] Add `test_target_and_protected_tables_are_batch3_specific()`:

```python
def test_target_and_protected_tables_are_batch3_specific():
    from scripts.migration import n9_batch3_prices_drop as cli

    assert cli.TARGET_TABLES == ("prices",)
    assert "prices" not in cli.PROTECTED_TABLES
    assert set(cli.PROTECTED_TABLES) == {
        "agent_queries",
        "research_reports",
        "agent_memories",
    }
```

- [ ] Add `test_archive_manifest_declares_pre_cutover_mirror_semantics()`:

```python
def test_archive_manifest_declares_pre_cutover_mirror_semantics():
    from scripts.migration import n9_batch3_prices_drop as cli

    manifest = cli.build_manifest(
        evidence={"fingerprint": "abc", "pg_snapshot": {"row_counts": {"prices": 1}}},
        dump_sha256="sha",
        dump_file="n9_batch3_prices.dump",
    )

    note = manifest["archive_semantics"]
    assert "pre-cutover" in note
    assert "not a backup of current local" in note
    assert manifest["scope"] == "pg_exit_n9_batch3_prices"
```

- [ ] Add `test_evidence_fingerprint_is_order_stable()`:

```python
def test_evidence_fingerprint_is_order_stable():
    from scripts.migration import n9_batch3_prices_drop as cli

    a = cli.build_evidence_report(
        pg_snapshot={"row_counts": {"prices": 2}, "objects": [{"name": "prices", "status": "present"}]},
        local_snapshot={"row_count": 3, "ticker_count": 1},
        grep_summary={"allowed_hits": [{"path": "b"}, {"path": "a"}], "blockers": []},
        e2e_summary={"ok": True, "pg_attempts": []},
    )
    b = cli.build_evidence_report(
        pg_snapshot={"objects": [{"status": "present", "name": "prices"}], "row_counts": {"prices": 2}},
        local_snapshot={"ticker_count": 1, "row_count": 3},
        grep_summary={"blockers": [], "allowed_hits": [{"path": "a"}, {"path": "b"}]},
        e2e_summary={"pg_attempts": [], "ok": True},
    )

    assert a["fingerprint"] == b["fingerprint"]
```

- [ ] Add `test_dump_command_targets_prices_only_and_keeps_dsn_out_of_argv()`:

```python
def test_dump_command_targets_prices_only_and_keeps_dsn_out_of_argv(tmp_path):
    from scripts.migration import n9_batch3_prices_drop as cli

    cmd = cli.build_pg_dump_command(
        database_url="postgresql://u:secret@host/db",
        output=tmp_path / "prices.dump",
        present_tables=["prices"],
    )

    joined = " ".join(cmd)
    assert "--table=public.prices" in cmd
    assert "agent_queries" not in joined
    assert "secret" not in joined
```

- [ ] Add `test_drop_sql_has_no_cascade()`:

```python
def test_drop_sql_has_no_cascade():
    from scripts.migration import n9_batch3_prices_drop as cli

    sql = cli.build_drop_sql(present_tables=["prices"])

    assert sql == ["DROP TABLE IF EXISTS public.prices"]
    assert "CASCADE" not in " ".join(sql).upper()
```

- [ ] Add `test_validate_drop_args_requires_restore_proof_and_e2e()` using temporary files:

```python
from argparse import Namespace


def test_validate_drop_args_requires_restore_proof_and_e2e(tmp_path):
    from scripts.migration import n9_batch3_prices_drop as cli

    args = Namespace(
        archive_dir=str(tmp_path),
        reviewed_fingerprint="abc",
        confirm_scheduler_paused=True,
        confirm_native_host_paused=True,
        confirm_destructive_drop=True,
    )

    result = cli.validate_drop_args(args)

    assert result.ok is False
    assert result.reason == "missing_restore_proof"
```

- [ ] Add `test_postcheck_requires_prices_absent_and_app_records_present()`:

```python
def test_postcheck_requires_prices_absent_and_app_records_present():
    from scripts.migration import n9_batch3_prices_drop as cli

    ok = cli.verify_post_drop_snapshot({
        "objects": [
            {"kind": "table", "name": "prices", "status": "missing_expected"},
            {"kind": "protected_table", "name": "agent_queries", "status": "protected_present"},
            {"kind": "protected_table", "name": "research_reports", "status": "protected_present"},
            {"kind": "protected_table", "name": "agent_memories", "status": "protected_present"},
        ],
    })

    assert ok["ok"] is True
```

### Verify RED

Run:

```bash
pytest tests/test_n9_batch3_prices_drop.py -q
```

Expected: FAIL because `scripts.migration.n9_batch3_prices_drop` does not exist.

### Implementation

- [ ] Create `scripts/migration/n9_batch3_prices_drop.py` by extracting only the needed discipline from `n9_batch2_cleanup.py`.
- [ ] Implement constants from the Target Manifest section.
- [ ] Implement these commands:

```text
preview --database-url --repo-root --market-db --e2e-report --output
dump --database-url --expected-report --archive-dir
verify-dump --database-url --archive-dir --restore-db --confirm-create-drop-restore-db
drop --database-url --archive-dir --reviewed-fingerprint --repo-root --confirm-scheduler-paused --confirm-native-host-paused --confirm-destructive-drop
postcheck --database-url --archive-dir
```

- [ ] `preview` must collect:
  - PG server version.
  - PG `prices` presence, row count, row fingerprint, distinct ticker count, min/max datetime, interval distribution.
  - Protected app-record table presence.
  - Dependency scan through `pg_depend`, including rowtype dependencies.
  - Dependency coverage: `get_recent_prices(character varying,character varying,integer)` is the only approved normal `pg_proc` rowtype dependency on `prices`; any other normal `pg_proc` dependency rejects the evidence.
  - Repo grep summary for runtime `FROM prices` / `JOIN prices` / `DatabaseBackend.query_prices` blockers.
  - Local `market_data.db.prices` row count, ticker count, latest datetime, and database path.
  - E2E summary loaded from the reviewed PG-unreachable smoke JSON (`ok:true`, `pg_attempts:[]`).
- [ ] `preview` must refuse if the E2E report is missing, false, or has any PG attempts.
- [ ] `dump` must:
  - refuse if the evidence fingerprint is absent;
  - verify `pg_dump` client major is not older than the server major;
  - write `evidence.json`, `manifest.json`, `pg_restore_list.txt`, `function_ddl.sql`, and `n9_batch3_prices.dump`;
  - include `ARCHIVE_SEMANTIC_NOTE` in `manifest.json`.
- [ ] `verify-dump` must:
  - create a disposable DB;
  - restore the dump;
  - apply `function_ddl.sql` after table restore;
  - compare row count, row fingerprint, and target function presence to evidence;
  - drop the disposable DB;
  - write `restore_proof.json`.
- [ ] `drop` must:
  - validate restore proof, manifest, dump sha, reviewed fingerprint, and confirmations;
  - re-run `preview` using the same live E2E report and compare fingerprint;
  - execute `DROP FUNCTION IF EXISTS public.get_recent_prices(character varying,character varying,integer)` before `DROP TABLE IF EXISTS public.prices` in one transaction;
  - use `SET LOCAL lock_timeout` and `SET LOCAL statement_timeout`;
  - verify in the same transaction that `get_recent_prices` and `prices` are absent and protected app-record tables are present;
  - commit only after post-drop catalog validation passes.
- [ ] `postcheck` must return sanitized JSON:

```json
{
  "ok": true,
  "targets_still_present": [],
  "protected_missing": []
}
```

### Verify GREEN

Run:

```bash
pytest tests/test_n9_batch3_prices_drop.py -q
python -m compileall scripts/migration/n9_batch3_prices_drop.py
```

Expected: PASS.

### Commit

```bash
git add scripts/migration/n9_batch3_prices_drop.py tests/test_n9_batch3_prices_drop.py
git commit -m "feat: add batch3 prices drop gate"
```

## Task 3 - Offline Integration Gate

### Intent

Prove the batch-3 code changes do not regress runtime before any live PG evidence.

### Commands

Run:

```bash
pytest \
  tests/test_db_backend_retired_prices.py \
  tests/test_n9_batch3_prices_drop.py \
  tests/test_pg_unreachable_e2e.py \
  tests/test_sqlite_backend.py::test_p0c_prices_miss_is_honest_empty_no_pg \
  tests/test_provider_health.py \
  tests/test_data_scheduler.py \
  -q
```

Expected: PASS.

Run:

```bash
python -m compileall scripts/migration/n9_batch3_prices_drop.py scripts/smoke/pg_unreachable_e2e.py
git diff --check
```

Expected: PASS / no output.

Run a grep gate:

```bash
rg -n "FROM prices|JOIN prices|UPDATE prices|INSERT INTO prices|query_prices|query_health_stats" src scripts tests docs
```

Expected:

- no runtime PG SQL against `prices` outside `n9_batch3_prices_drop.py`, tests, docs, local SQLite code, and direct-local writer code;
- `DatabaseBackend.query_prices` is a retired stub;
- app-record PG methods remain present.

### Commit

```bash
git add docs/design/PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md
git commit -m "docs: update batch3 offline gate status"
```

## Task 4 - Live Evidence Preview

### Intent

Build the reviewed, read-only evidence packet. This task is non-destructive but should run during a quiet window so row fingerprints stay stable between approval and drop.

### Preconditions

- [ ] Scheduler paused.
- [ ] Firefox/native host or SA sync quiet.
- [ ] No manual provider runs.
- [ ] Repo freeze begins after the reviewed evidence packet is produced.
- [ ] PG-unreachable E2E smoke has just been run twice and passed.

### Commands

Run PG-unreachable E2E:

```bash
PY=/home/hyl/.virtualenvs/llm_app/bin/python3
E2E_DIR="scratchpad/pg-unreachable-e2e-batch3-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$E2E_DIR"
ARKSCOPE_DISABLE_SCHEDULER=1 "$PY" scripts/smoke/pg_unreachable_e2e.py \
  --poison-dsn "postgresql://pg-poison.invalid/arkscope?connect_timeout=1" \
  --output "$E2E_DIR/run-1.json" > "$E2E_DIR/run-1.stdout.json"
ARKSCOPE_DISABLE_SCHEDULER=1 "$PY" scripts/smoke/pg_unreachable_e2e.py \
  --poison-dsn "postgresql://pg-poison.invalid/arkscope?connect_timeout=1" \
  --output "$E2E_DIR/run-2.json" > "$E2E_DIR/run-2.stdout.json"
```

Expected:

- both reports `ok:true`;
- both reports `pg_attempts:[]`;
- 22 checks, 0 failures.

Run preview twice:

```bash
DB_URL="$DATABASE_URL"
MARKET_DB="/mnt/md0/PycharmProjects/ArkScope/data/market_data.db"
OUT_DIR="scratchpad/n9-batch3-prices-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT_DIR"

"$PY" scripts/migration/n9_batch3_prices_drop.py preview \
  --database-url "$DB_URL" \
  --repo-root "$PWD" \
  --market-db "$MARKET_DB" \
  --e2e-report "$E2E_DIR/run-1.json" \
  --output "$OUT_DIR/preview-1.json"

"$PY" scripts/migration/n9_batch3_prices_drop.py preview \
  --database-url "$DB_URL" \
  --repo-root "$PWD" \
  --market-db "$MARKET_DB" \
  --e2e-report "$E2E_DIR/run-2.json" \
  --output "$OUT_DIR/preview-2.json"
```

Expected:

- byte-identical fingerprints;
- grep blockers `0`;
- PG `prices` present;
- protected app-record tables present;
- local snapshot row count >= PG row count is not required as a hard gate, but report must show local row count and latest datetime;
- evidence includes `ARCHIVE_SEMANTIC_NOTE`.

### Review Gate

Stop here and send the preview JSONs to review. Do not dump or drop until the reviewer independently checks:

- PG `prices` count/fingerprint/latest datetime;
- local `market_data.db.prices` count/latest datetime;
- protected app-record table presence;
- dependency scan;
- grep blockers;
- E2E summaries.

## Task 5 - Archive And Restore Proof

### Intent

Create the rollback archive and prove it restores. This is still non-destructive to the source PG.

### Commands

```bash
ARCHIVE_DIR="data/pg_archive/n9_batch3_prices_$(date -u +%Y%m%dT%H%M%SZ)"

"$PY" scripts/migration/n9_batch3_prices_drop.py dump \
  --database-url "$DB_URL" \
  --expected-report "$OUT_DIR/preview-1.json" \
  --archive-dir "$ARCHIVE_DIR"

"$PY" scripts/migration/n9_batch3_prices_drop.py verify-dump \
  --database-url "$DB_URL" \
  --archive-dir "$ARCHIVE_DIR" \
  --restore-db "arkscope_n9_batch3_restore_$(date -u +%Y%m%d%H%M%S)" \
  --confirm-create-drop-restore-db
```

Expected:

- `manifest.json` has `scope == "pg_exit_n9_batch3_prices"`;
- `manifest.json` includes the pre-cutover mirror archive semantic note;
- `restore_proof.json` has `ok:true`, `mismatches:[]`;
- dump sha256 in manifest matches the actual file.

### Review Gate

Stop here for approval. The approval package must include:

- reviewed evidence fingerprint;
- archive directory;
- dump sha256;
- restore proof `ok:true`;
- explicit reminder: restoring this dump does not restore current local prices.

## Task 6 - Live Drop

### Intent

Physically remove PG `prices` after explicit user approval.

### Preconditions

- [ ] User explicitly approves the reviewed fingerprint and archive path.
- [ ] Repo freeze still active.
- [ ] Scheduler/native host/manual writers still quiet.
- [ ] Archive and restore proof are retained.

### Command

```bash
"$PY" scripts/migration/n9_batch3_prices_drop.py drop \
  --database-url "$DB_URL" \
  --archive-dir "$ARCHIVE_DIR" \
  --reviewed-fingerprint "<APPROVED_FINGERPRINT>" \
  --repo-root "$PWD" \
  --confirm-scheduler-paused \
  --confirm-native-host-paused \
  --confirm-destructive-drop
```

Expected:

- if current evidence fingerprint differs, the command exits before `DROP`;
- if any dependency blocks drop, transaction rolls back; do not use `CASCADE`;
- on success, JSON reports `status:"dropped"` and `dropped_tables:1`.

## Task 7 - Postcheck And PG-Unreachable E2E

### Intent

Prove the destructive drop did not harm normal runtime and did not touch protected app-record archives.

### Commands

```bash
"$PY" scripts/migration/n9_batch3_prices_drop.py postcheck \
  --database-url "$DB_URL" \
  --archive-dir "$ARCHIVE_DIR"
```

Expected:

- `ok:true`
- `targets_still_present:[]`
- `protected_missing:[]`

Run PG-unreachable E2E again:

```bash
POST_E2E_DIR="scratchpad/pg-unreachable-e2e-post-batch3-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$POST_E2E_DIR"
ARKSCOPE_DISABLE_SCHEDULER=1 "$PY" scripts/smoke/pg_unreachable_e2e.py \
  --poison-dsn "postgresql://pg-poison.invalid/arkscope?connect_timeout=1" \
  --output "$POST_E2E_DIR/run-1.json" > "$POST_E2E_DIR/run-1.stdout.json"
ARKSCOPE_DISABLE_SCHEDULER=1 "$PY" scripts/smoke/pg_unreachable_e2e.py \
  --poison-dsn "postgresql://pg-poison.invalid/arkscope?connect_timeout=1" \
  --output "$POST_E2E_DIR/run-2.json" > "$POST_E2E_DIR/run-2.stdout.json"
```

Expected:

- both reports `ok:true`;
- `pg_attempts:[]`;
- 22 checks, 0 failures.

Also run a direct local price smoke:

```bash
"$PY" - <<'PY'
from src.tools.data_access import DataAccessLayer
dal = DataAccessLayer(db_dsn="auto")
res = dal.get_prices("NVDA", interval="15min", days=7)
print({"bars": len(res.bars), "ticker": res.ticker})
assert len(res.bars) > 0
PY
```

Expected: local NVDA bars present; no PG attempt.

## Task 8 - Docs Sync

### Intent

Record the destructive operation and make the next state unambiguous.

### Files

- Modify: `docs/design/PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md`
- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: `docs/design/PG_EXIT_COMPLETION_PLAN.md`

### Steps

- [ ] Mark this plan `LIVE COMPLETE` with:
  - approved fingerprint;
  - archive path;
  - dump sha256;
  - restore proof path;
  - postcheck result;
  - pre/post E2E paths.
- [ ] In `PG_EXIT_REMAINDER_SCOPING.md` §8:
  - mark batch-3 live executed;
  - list remaining PG tables as app-record archive tables only;
  - restate the archive semantic note.
- [ ] In `PROJECT_PRIORITY_MAP.md`:
  - add newest-first decision log entry;
  - set P0-B status to PG market-data physical drop complete;
  - set next PG-exit item to app-record archive policy or close PG-exit if app-record archives are explicitly accepted as out-of-runtime.
- [ ] In `PG_EXIT_COMPLETION_PLAN.md`:
  - mark normal runtime and market-data PG exit complete;
  - document any remaining PG app-record archive decision.
- [ ] Commit:

```bash
git add docs/design/PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md \
        docs/design/PG_EXIT_REMAINDER_SCOPING.md \
        docs/design/PROJECT_PRIORITY_MAP.md \
        docs/design/PG_EXIT_COMPLETION_PLAN.md
git commit -m "docs: record batch3 prices drop"
```

## Self-Review Checklist

- [ ] The plan states that the PG prices dump is a pre-cutover mirror archive, not current local-price backup.
- [ ] Batch-3 target/protected table sets consciously remove `prices` from protection and keep all three app-record archive tables protected.
- [ ] `DatabaseBackend.query_prices` and `query_health_stats` price SQL are stubbed before live drop.
- [ ] Pre-drop and post-drop PG-unreachable E2E smoke are mandatory.
- [ ] No task authorizes `CASCADE`.
- [ ] Live drop is separated from implementation and requires explicit user approval.
- [ ] App-record archive policy is not mixed into this batch.
