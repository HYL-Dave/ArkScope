# PG-Exit N9 Batch-1 Destructive Drop Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reviewable, restorable evidence packet for the first destructive PostgreSQL drop batch, then drop only the PG objects whose runtime authority has already moved local or been explicitly abandoned.

**Architecture:** N9 batch-1 is a destructive operation with a restore archive as the rollback basis, not a feature toggle. It therefore has two mandatory gates before live drop: a reader-free evidence gate and a dump-restore gate that proves the archive can restore into a disposable database with matching row fingerprints. The live drop itself must be a separate, explicit user-approved step, re-checking the reviewed evidence fingerprint immediately before any `DROP`.

**Tech Stack:** Python 3, psycopg2, SQLite, `pg_dump`/`pg_restore`, PostgreSQL catalog queries, pytest, `rg`, existing ArkScope market/profile DB helpers.

---

## Scope Lock

This plan implements **N9 batch-1** from `docs/design/PROJECT_PRIORITY_MAP.md` and `docs/design/PG_EXIT_REMAINDER_SCOPING.md`.

N9 batch-1 is allowed to archive and drop these PG authorities after evidence passes:

- `news`
- `news_scores`
- `fundamentals`
- `iv_history`
- `financial_data_cache`
- `signals`, only if present and reader-free
- Seeking Alpha tables:
  - `sa_alpha_picks`
  - `sa_refresh_meta`
  - `sa_articles`
  - `sa_article_comments`
  - `sa_market_news`
  - `sa_comment_signals`
- Empty macro/calendar tables:
  - `macro_series`
  - `macro_observations`
  - `macro_release_dates`
  - `cal_economic_events`
  - `cal_economic_event_revisions`
  - `cal_earnings_events`
  - `cal_earnings_event_revisions`
  - `cal_ipo_events`
  - `cal_ipo_event_revisions`

N9 batch-1 must also handle directly dependent score objects:

- `news_latest_scores`
- `news_sentiment_summary(VARCHAR, INTEGER, VARCHAR)`

N9 batch-1 must **not** drop or change:

- `prices` or price ingest/read paths.
- `job_runs`; it remains until the S-H1 local job-runs soak completes and batch-2 is approved.
- App-record tables such as `agent_queries`, `research_reports`, or `agent_memories`.
- Local SQLite stores (`market_data.db`, `profile_state.db`, `sa_capture.db`, `macro_calendar.db`).

SA rollback-basis ruling: this plan explicitly uses the 2026-07-03 decision in `PROJECT_PRIORITY_MAP.md` that replaces the old SA rule "PG frozen rollback basis / do NOT delete" with "compressed dump file is the rollback basis." The live PG `sa_*` tables are no longer retained as the rollback surface after the dump-restore gate passes.

## Non-Negotiable Gates

1. **No live drop from this branch.** This plan branch may add tests, hardening, evidence CLI, and docs. The destructive live drop needs a later explicit user approval with a reviewed fingerprint.
2. **No `CASCADE`.** If an unexpected dependency blocks a drop, the operation rolls back and the plan is amended. Do not hide unknown dependencies with `CASCADE`.
3. **No dump-only approval.** A dump file that exists but has not been restored into a disposable database is not a valid rollback basis.
4. **No time-window assumptions.** Evidence is fingerprinted from actual PG/local state. If a table changes between preview and apply, live drop stops.
5. **No silent runtime breakage.** Any remaining runtime path that can hit a to-be-dropped table is a blocker unless it is converted to local-only/honest-empty before the live drop.

## File Map

Create:

- `docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md` - this plan.
- `scripts/migration/n9_batch1_pg_drop.py` - evidence, dump verification, and drop orchestrator.
- `tests/test_n9_batch1_pg_drop.py` - hermetic CLI/unit tests for evidence, dump verification, and drop gating.

Modify:

- `src/service/data_scheduler.py` - stop local refresh from requesting PG `iv_history` after news PG-exit; after N9 batch-1 it may request `prices` only.
- `src/tools/backends/local_market_backend.py` - make `query_iv_history()` local-only/honest-empty when market strict is unset, because old PG `iv_history` is intentionally abandoned.
- `tests/test_data_scheduler.py` - assert post-N9 local refresh only requests `prices`.
- `tests/test_sqlite_backend.py` - update IV fallback tests to assert no PG fallback for local misses.
- `scripts/migrate_to_supabase.py` - disable active PG imports for `--news`, `--iv`, and `--fundamentals`; `--scores --archive-scores` remains archive-only only until the live N9 drop, then becomes blocked.
- `tests/test_news_scores.py` and/or a new focused test - pin the disabled migration-domain behavior.
- `docs/design/PG_EXIT_REMAINDER_SCOPING.md` - after implementation/live gates, update N9 status and retained/drop lists.
- `docs/design/PROJECT_PRIORITY_MAP.md` - after implementation/live gates, record evidence fingerprint, dump path, and approval outcome.
- `docs/design/PG_EXIT_COMPLETION_PLAN.md` - after live drop, update PG-exit status and remaining active PG dependency (`prices`).

## Target Object Manifest

Use this ordered manifest in both evidence and drop code. `DROP TABLE` can use one statement with all target tables to allow PostgreSQL to resolve intra-batch foreign-key dependencies, but dependent views/functions must be explicitly dropped first.

```python
TARGET_TABLES = (
    "news",
    "news_scores",
    "fundamentals",
    "iv_history",
    "financial_data_cache",
    "signals",
    "sa_alpha_picks",
    "sa_refresh_meta",
    "sa_articles",
    "sa_article_comments",
    "sa_market_news",
    "sa_comment_signals",
    "macro_series",
    "macro_observations",
    "macro_release_dates",
    "cal_economic_events",
    "cal_economic_event_revisions",
    "cal_earnings_events",
    "cal_earnings_event_revisions",
    "cal_ipo_events",
    "cal_ipo_event_revisions",
)

TARGET_VIEWS = ("news_latest_scores",)
TARGET_FUNCTION_SIGNATURES = (
    "news_sentiment_summary(character varying, integer, character varying)",
)

EXCLUDED_TABLES = (
    "prices",
    "job_runs",
    "agent_queries",
    "research_reports",
    "agent_memories",
)
```

The evidence command must tolerate missing optional targets (`signals` may not exist), but the report must show whether each target object is `present`, `missing_expected_optional`, or `missing_unexpected`.

## Task 1: Pre-Drop Runtime Hardening

**Files:**

- Modify: `src/service/data_scheduler.py`
- Modify: `src/tools/backends/local_market_backend.py`
- Modify: `scripts/migrate_to_supabase.py`
- Test: `tests/test_data_scheduler.py`
- Test: `tests/test_sqlite_backend.py`
- Test: `tests/test_news_scores.py`

### Task 1A: Stop local refresh from requesting PG IV

- [ ] **Step 1: Write the failing test**

Add a test beside the existing local-refresh domain tests in `tests/test_data_scheduler.py`.

```python
def test_local_refresh_after_news_pg_exit_requests_prices_only(monkeypatch, tmp_path):
    from src.service import data_scheduler as ds

    market_db = tmp_path / "market_data.db"
    market_db.write_bytes(b"stub")

    calls = []

    def fake_incremental_update(*, domains=None):
        calls.append(tuple(domains) if domains is not None else None)
        return {"ok": True, "prices": {"rows_added": 0}}

    monkeypatch.setattr(ds, "_news_pg_exit_assume_completed_for_refresh", lambda _: True)
    monkeypatch.setattr(ds, "resolve_market_db_path", lambda: str(market_db), raising=False)
    monkeypatch.setattr("src.market_data_admin.incremental_update", fake_incremental_update)

    out = ds._local_refresh()

    assert out["ok"] is True
    assert calls == [("prices",)]
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
pytest tests/test_data_scheduler.py::test_local_refresh_after_news_pg_exit_requests_prices_only -q
```

Expected before implementation: FAIL because `_local_refresh()` currently requests `("prices", "iv")`.

- [ ] **Step 3: Implement the minimal change**

In `src/service/data_scheduler.py`, change the post-news-exit local refresh domain tuple:

```python
domains = (
    ("prices",)
    if _news_pg_exit_assume_completed_for_refresh(market_db)
    else None
)
```

- [ ] **Step 4: Verify**

Run:

```bash
pytest tests/test_data_scheduler.py::test_local_refresh_after_news_pg_exit_requests_prices_only -q
```

Expected: PASS.

### Task 1B: Make IV reads local-only before dropping PG `iv_history`

- [ ] **Step 1: Write the failing tests**

Update the IV fallback tests in `tests/test_sqlite_backend.py` so a local miss no longer calls `DatabaseBackend.query_iv_history`.

```python
def test_iv_history_local_miss_is_honest_empty_no_pg_fallback(market_db, monkeypatch):
    from src.tools.backends.db_backend import DatabaseBackend
    from src.tools.backends.local_market_backend import LocalMarketDatabaseBackend

    called = False

    def fake_pg(self, ticker):
        nonlocal called
        called = True
        raise AssertionError("PG iv_history fallback must not be used after N9 batch-1")

    monkeypatch.setattr(DatabaseBackend, "query_iv_history", fake_pg)
    backend = LocalMarketDatabaseBackend("postgres://unused", market_db=str(market_db))

    df = backend.query_iv_history("UNKNOWN")

    assert df.empty
    assert called is False
```

If existing tests assert PG fallback, replace them with local-only assertions and keep a comment linking to N9 batch-1.

- [ ] **Step 2: Run the failing tests**

Run:

```bash
pytest tests/test_sqlite_backend.py -k "iv_history" -q
```

Expected before implementation: FAIL on the old fallback expectation.

- [ ] **Step 3: Implement the minimal change**

In `src/tools/backends/local_market_backend.py`, change `query_iv_history()`:

```python
def query_iv_history(self, ticker: str) -> pd.DataFrame:
    try:
        df = self._market.query_iv_history(ticker)
    except Exception as e:
        logger.warning(f"local query_iv_history failed ({e})")
        df = None
    if df is not None and not df.empty:
        provenance.record("iv", "local")
        return df
    provenance.record("iv", "none")
    return df if df is not None else pd.DataFrame()
```

Also update the module docstring:

```text
query_iv_history is local-only after N9 batch-1; old PG iv_history is intentionally abandoned.
```

- [ ] **Step 4: Verify**

Run:

```bash
pytest tests/test_sqlite_backend.py -k "iv_history" -q
```

Expected: PASS.

### Task 1C: Disable active PG import paths for dropped domains

- [ ] **Step 1: Write the failing tests**

Extend `tests/test_news_scores.py` or create `tests/test_pg_drop_domain_retirement.py` to pin the CLI behavior:

```python
def test_migrate_to_supabase_refuses_n9_retired_domains(monkeypatch):
    import pytest
    from scripts import migrate_to_supabase as migrate

    parser = migrate.build_arg_parser()

    for flag in ("--news", "--iv", "--fundamentals"):
        args = parser.parse_args([flag])
        with pytest.raises(SystemExit):
            migrate.validate_args(args)
```

If `migrate_to_supabase.py` does not yet expose `build_arg_parser()` or `validate_args()`, add those names in the implementation so tests can exercise validation without connecting to PG.

- [ ] **Step 2: Run the failing test**

Run:

```bash
pytest tests/test_pg_drop_domain_retirement.py -q
```

Expected before implementation: FAIL because the active flags are still accepted.

- [ ] **Step 3: Implement the minimal change**

In `scripts/migrate_to_supabase.py`:

1. Extract parser construction into `build_arg_parser()`.
2. Extract argument validation into `validate_args(args)`.
3. Reject `--news`, `--iv`, and `--fundamentals` with a message that names N9 batch-1 and the local authorities.
4. Keep `--prices` active.
5. Keep `--scores --archive-scores` accepted only until the live drop. If `news_scores` is absent after N9, it must fail with a clear archive-only message rather than silently recreating PG score authority.

Validation shape:

```python
N9_RETIRED_DOMAINS = ("news", "iv", "fundamentals")

def validate_args(args) -> None:
    requested = {
        "news": args.news,
        "iv": args.iv,
        "fundamentals": args.fundamentals,
    }
    retired = [name for name, enabled in requested.items() if enabled]
    if retired:
        raise SystemExit(
            "PG import disabled for N9-retired domains: "
            + ", ".join(retired)
            + ". Use local direct writers/refetch paths instead."
        )
```

- [ ] **Step 4: Verify**

Run:

```bash
pytest tests/test_pg_drop_domain_retirement.py tests/test_news_scores.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/service/data_scheduler.py src/tools/backends/local_market_backend.py scripts/migrate_to_supabase.py tests/test_data_scheduler.py tests/test_sqlite_backend.py tests/test_pg_drop_domain_retirement.py tests/test_news_scores.py
git commit -m "chore: harden retired PG domains before N9 drop"
```

## Task 2: Evidence CLI

**Files:**

- Create: `scripts/migration/n9_batch1_pg_drop.py`
- Test: `tests/test_n9_batch1_pg_drop.py`

The evidence CLI is read-only. It must not call `DROP`, `DELETE`, `UPDATE`, `INSERT`, `CREATE`, or `ALTER`.

### Task 2A: Build target inventory and fingerprint

- [ ] **Step 1: Write tests for deterministic evidence output**

Create `tests/test_n9_batch1_pg_drop.py` with fake connection/cursor objects. The fake cursor should return target counts, dependency rows, and version rows in shuffled order; the report fingerprint must remain stable.

```python
def test_evidence_report_fingerprint_is_order_stable():
    from scripts.migration import n9_batch1_pg_drop as cli

    first = cli.build_evidence_report(
        pg_snapshot={
            "server_version": "17.5",
            "objects": [
                {"kind": "table", "name": "news_scores", "present": True, "row_count": 2},
                {"kind": "table", "name": "news", "present": True, "row_count": 1},
            ],
            "dependencies": [],
            "row_fingerprints": {
                "news": "a",
                "news_scores": "b",
            },
        },
        grep_summary={"blockers": [], "allowed_hits": ["docs only"]},
    )
    second = cli.build_evidence_report(
        pg_snapshot={
            "objects": [
                {"kind": "table", "name": "news", "present": True, "row_count": 1},
                {"kind": "table", "name": "news_scores", "present": True, "row_count": 2},
            ],
            "server_version": "17.5",
            "dependencies": [],
            "row_fingerprints": {
                "news_scores": "b",
                "news": "a",
            },
        },
        grep_summary={"allowed_hits": ["docs only"], "blockers": []},
    )

    assert first["fingerprint"] == second["fingerprint"]
    assert first == second
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
pytest tests/test_n9_batch1_pg_drop.py::test_evidence_report_fingerprint_is_order_stable -q
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement deterministic report helpers**

Create `scripts/migration/n9_batch1_pg_drop.py` with:

```python
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

TARGET_TABLES = (...)
TARGET_VIEWS = ("news_latest_scores",)
TARGET_FUNCTION_SIGNATURES = (
    "news_sentiment_summary(character varying, integer, character varying)",
)
OPTIONAL_TARGETS = {"signals"}
EXCLUDED_TABLES = ("prices", "job_runs", "agent_queries", "research_reports", "agent_memories")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def build_evidence_report(*, pg_snapshot: Mapping[str, Any], grep_summary: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "scope": "pg_exit_n9_batch1",
        "targets": {
            "tables": sorted(TARGET_TABLES),
            "views": sorted(TARGET_VIEWS),
            "functions": sorted(TARGET_FUNCTION_SIGNATURES),
            "excluded_tables": sorted(EXCLUDED_TABLES),
        },
        "pg_snapshot": _sort_report_value(pg_snapshot),
        "grep_summary": _sort_report_value(grep_summary),
    }
    payload["fingerprint"] = _sha256(payload)
    return payload
```

Also implement `_sort_report_value()` recursively for dict/list values.

- [ ] **Step 4: Verify**

Run:

```bash
pytest tests/test_n9_batch1_pg_drop.py::test_evidence_report_fingerprint_is_order_stable -q
```

Expected: PASS.

### Task 2B: Collect PG inventory in read-only mode

- [ ] **Step 1: Write tests for object classification**

Add tests that feed fake `to_regclass` results:

```python
def test_classify_targets_marks_optional_signals_missing_without_blocking():
    from scripts.migration import n9_batch1_pg_drop as cli

    objects = cli.classify_target_objects({
        "news": "public.news",
        "signals": None,
        "prices": "public.prices",
    })

    assert objects["news"]["status"] == "present"
    assert objects["signals"]["status"] == "missing_expected_optional"
    assert objects["prices"]["status"] == "excluded_present"
```

- [ ] **Step 2: Implement PG read-only collector**

Implement:

```python
def collect_pg_snapshot(conn) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '30s'")
        cur.execute("SHOW server_version")
        server_version = cur.fetchone()[0]
        ...
```

Required data:

- `server_version`
- object existence for all targets and excluded tables
- row counts for present target tables
- row fingerprint for each present target table
- dependency rows for target tables/views/functions
- macro/cal counts, proving the nine macro/cal tables are empty before they are eligible for drop
- `financial_data_cache` source/unexpired summary
- `news_scores` summary:
  - count
  - max `scored_at`
  - malformed rows
- `sa_*` counts

Row fingerprint can be implemented with deterministic SQL where safe:

```sql
SELECT md5(COALESCE(string_agg(md5(row_to_json(t)::text), '' ORDER BY row_to_json(t)::text), ''))
FROM public.<quoted_table> AS t;
```

For larger tables, if this is too slow in copy dry-run, replace with a streaming Python cursor ordered by primary key and document the change. Do not use row count alone as a restore-verification fingerprint.

- [ ] **Step 3: Verify against fake tests**

Run:

```bash
pytest tests/test_n9_batch1_pg_drop.py -q
```

Expected: PASS.

### Task 2C: Reader grep summary

- [ ] **Step 1: Write tests for grep classifier**

The grep classifier should accept a list of `(path, line)` hits and classify them.

```python
def test_grep_classifier_blocks_runtime_pg_reader_for_target_table():
    from scripts.migration import n9_batch1_pg_drop as cli

    summary = cli.classify_grep_hits([
        ("src/tools/backends/local_market_backend.py", "return super().query_iv_history(ticker)"),
        ("docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md", "iv_history"),
    ])

    assert summary["blockers"] == [
        {
            "path": "src/tools/backends/local_market_backend.py",
            "reason": "runtime_reference_to_drop_target",
            "match": "return super().query_iv_history(ticker)",
        }
    ]
```

- [ ] **Step 2: Implement classification allowlist**

Allowed categories:

- tests
- docs
- SQL migration files documenting historical schema
- archive/migration scripts only when the plan explicitly marks them disabled before live drop
- local SQLite table names in `sqlite_backend.py`, `sa_capture_backend.py`, and `macro_calendar/local_store.py`
- plain PG backend dead methods only if no runtime factory can select them in hard-local mode; these must appear in `allowed_hits` with reason `dead_pg_backend_method_pending_n9_cleanup`

Blocker categories:

- `src/service/data_scheduler.py` invoking retired PG domains after Task 1
- `LocalMarketDatabaseBackend` fallback to PG for `iv_history`, `news`, `fundamentals`, or `financial_data_cache`
- app routes/tools directly importing `DatabaseBackend` for target domains
- native host or extension code writing/reading target PG tables
- `migrate_to_supabase.py` still accepting active imports for retired domains

- [ ] **Step 3: Wire preview command**

CLI shape:

```bash
python scripts/migration/n9_batch1_pg_drop.py preview \
  --database-url "$DATABASE_URL" \
  --repo-root /mnt/md0/PycharmProjects/ArkScope \
  --output /tmp/n9-batch1-preview-1.json
```

`preview` writes JSON to `--output` and prints a sanitized one-line summary:

```json
{"status":"previewed","fingerprint":"...","blockers":0,"target_tables_present":21}
```

The summary must not print credentials, DSNs, row payloads, article titles, URLs, or secrets.

- [ ] **Step 4: Verify**

Run:

```bash
pytest tests/test_n9_batch1_pg_drop.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/migration/n9_batch1_pg_drop.py tests/test_n9_batch1_pg_drop.py
git commit -m "feat: add N9 batch1 evidence preview"
```

## Task 3: Dump and Restore Verification Gate

**Files:**

- Modify: `scripts/migration/n9_batch1_pg_drop.py`
- Test: `tests/test_n9_batch1_pg_drop.py`

This task creates the rollback basis. A live drop cannot be approved without the artifacts from this task.

### Task 3A: Add dump command

- [ ] **Step 1: Write tests for command construction**

```python
def test_pg_dump_command_targets_only_batch1_objects(tmp_path):
    from scripts.migration import n9_batch1_pg_drop as cli

    cmd = cli.build_pg_dump_command(
        database_url="postgres://redacted",
        output=tmp_path / "n9.dump",
        present_tables=["news", "news_scores"],
        present_views=["news_latest_scores"],
    )

    assert "pg_dump" in cmd[0]
    assert "--format=custom" in cmd
    assert "--no-owner" in cmd
    assert "--no-privileges" in cmd
    assert "--table=public.news" in cmd
    assert "--table=public.news_scores" in cmd
    assert "--table=public.news_latest_scores" in cmd
    assert "--table=public.prices" not in cmd
```

- [ ] **Step 2: Implement dump command construction**

Implementation requirements:

- Use `pg_dump --format=custom --no-owner --no-privileges`.
- Include each present target table with `--table=public.<name>`.
- Include each present target view with `--table=public.<name>`.
- Do not include `prices`, `job_runs`, or app-record tables.
- Write dump under:

```text
data/pg_archive/n9_batch1_<UTC>/n9_batch1.dump
```

- Write sidecar files:
  - `evidence.json`
  - `manifest.json`
  - `pg_restore_list.txt`
  - `function_ddl.sql` from `pg_get_functiondef()` for target functions

If the installed `pg_dump` client is older than the PG server major version, stop with:

```text
pg_dump client is older than server; install matching/newer PostgreSQL client before destructive N9 dump.
```

Do not fall back to CSV-only freeze for N9. `scripts/sa_pg_freeze.py` is historical diagnostic tooling and is not a valid rollback basis for destructive batch-1.

- [ ] **Step 3: Verify**

Run:

```bash
pytest tests/test_n9_batch1_pg_drop.py -k "dump" -q
```

Expected: PASS.

### Task 3B: Add restore verification command

- [ ] **Step 1: Write tests for restore proof validation**

```python
def test_restore_proof_requires_matching_row_fingerprints(tmp_path):
    from scripts.migration import n9_batch1_pg_drop as cli

    evidence = {
        "fingerprint": "abc",
        "pg_snapshot": {
            "row_fingerprints": {"news": "old"},
            "objects": [{"kind": "table", "name": "news", "status": "present", "row_count": 1}],
        },
    }
    restored = {
        "row_fingerprints": {"news": "different"},
        "objects": [{"kind": "table", "name": "news", "status": "present", "row_count": 1}],
    }

    result = cli.compare_restore_to_evidence(restored, evidence)

    assert result["ok"] is False
    assert result["mismatches"][0]["table"] == "news"
```

- [ ] **Step 2: Implement restore verification**

CLI shape:

```bash
python scripts/migration/n9_batch1_pg_drop.py verify-dump \
  --database-url "$DATABASE_URL" \
  --archive-dir data/pg_archive/n9_batch1_<UTC> \
  --restore-db arkscope_n9_batch1_restore_<UTC> \
  --confirm-create-drop-restore-db
```

Behavior:

1. Create disposable restore DB.
2. Run `pg_restore --exit-on-error --dbname "$RESTORE_DB" n9_batch1.dump`.
3. Apply `function_ddl.sql` if present.
4. Recompute object counts and row fingerprints in restore DB.
5. Compare restored counts/fingerprints with `evidence.json`.
6. Write `restore_proof.json` with:
   - evidence fingerprint
   - dump sha256
   - restored counts/fingerprints
   - mismatches
   - `ok: true`
7. Drop disposable restore DB.

If restore DB cleanup fails, print only the restore DB name and a cleanup command, not credentials.

- [ ] **Step 3: Verify**

Run:

```bash
pytest tests/test_n9_batch1_pg_drop.py -k "restore" -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/migration/n9_batch1_pg_drop.py tests/test_n9_batch1_pg_drop.py
git commit -m "feat: verify N9 batch1 PG archive restore"
```

## Task 4: Drop Orchestrator

**Files:**

- Modify: `scripts/migration/n9_batch1_pg_drop.py`
- Test: `tests/test_n9_batch1_pg_drop.py`

The drop command exists only so the live destructive step is scripted and auditable. It must refuse to run unless all reviewed artifacts are present.

### Task 4A: Add apply gate tests

- [ ] **Step 1: Write refusal tests**

```python
def test_drop_refuses_without_reviewed_fingerprint(tmp_path):
    from scripts.migration import n9_batch1_pg_drop as cli

    args = cli.parse_args(["drop", "--database-url", "postgres://x"])

    result = cli.validate_drop_args(args)

    assert result.ok is False
    assert result.reason == "missing_reviewed_fingerprint"


def test_drop_refuses_without_restore_proof(tmp_path):
    from scripts.migration import n9_batch1_pg_drop as cli

    args = cli.parse_args([
        "drop",
        "--database-url", "postgres://x",
        "--reviewed-fingerprint", "abc",
        "--archive-dir", str(tmp_path),
        "--confirm-scheduler-paused",
        "--confirm-destructive-drop",
    ])

    result = cli.validate_drop_args(args)

    assert result.ok is False
    assert result.reason == "missing_restore_proof"
```

- [ ] **Step 2: Implement argument validation**

`drop` requires:

- `--reviewed-fingerprint <sha256>`
- `--archive-dir <path>`
- `--confirm-scheduler-paused`
- `--confirm-native-host-paused`
- `--confirm-destructive-drop`

`drop` also requires `restore_proof.json` with:

```json
{"ok": true, "evidence_fingerprint": "<same fingerprint>"}
```

- [ ] **Step 3: Verify**

Run:

```bash
pytest tests/test_n9_batch1_pg_drop.py -k "drop_refuses" -q
```

Expected: PASS.

### Task 4B: Add transactional drop logic

- [ ] **Step 1: Write transaction tests**

The fake cursor must assert there is no `CASCADE` in any executed SQL.

```python
def test_drop_sql_is_explicit_and_never_cascade():
    from scripts.migration import n9_batch1_pg_drop as cli

    sql = cli.build_drop_sql(
        present_tables=["news_scores", "news"],
        present_views=["news_latest_scores"],
        present_functions=["news_sentiment_summary(character varying, integer, character varying)"],
    )

    joined = "\n".join(sql)
    assert "CASCADE" not in joined.upper()
    assert "DROP VIEW IF EXISTS public.news_latest_scores" in joined
    assert "DROP FUNCTION IF EXISTS public.news_sentiment_summary(character varying, integer, character varying)" in joined
    assert "DROP TABLE IF EXISTS public.news_scores, public.news" in joined
```

- [ ] **Step 2: Implement drop SQL**

Implementation requirements:

- Re-run `preview` inside a read-only transaction before the write.
- Compare full evidence JSON fingerprint to `--reviewed-fingerprint`.
- Verify dump sha256 and restore proof.
- Start a PG transaction.
- Set `lock_timeout` and `statement_timeout`.
- Drop functions first.
- Drop views second.
- Drop tables in one explicit `DROP TABLE IF EXISTS ...` statement.
- Never use `CASCADE`.
- Re-query `to_regclass` for all dropped and excluded objects before commit:
  - target objects must be absent
  - excluded objects must remain present if they were present in preview
- Commit.

If any step fails, rollback and print sanitized JSON:

```json
{"status":"failed","stage":"drop_transaction","reason":"dependency_blocked"}
```

- [ ] **Step 3: Verify**

Run:

```bash
pytest tests/test_n9_batch1_pg_drop.py -k "drop" -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/migration/n9_batch1_pg_drop.py tests/test_n9_batch1_pg_drop.py
git commit -m "feat: gate N9 batch1 PG drop"
```

## Task 5: Offline Gate and Docs Sync Before Live Evidence

**Files:**

- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: `docs/design/PG_EXIT_COMPLETION_PLAN.md`
- Test: focused backend and CLI tests

- [ ] **Step 1: Run focused tests**

Run:

```bash
pytest \
  tests/test_n9_batch1_pg_drop.py \
  tests/test_data_scheduler.py \
  tests/test_sqlite_backend.py \
  tests/test_news_scores.py \
  tests/test_market_data_admin.py \
  tests/test_macro_calendar_local_wiring.py \
  tests/test_macro_calendar_health.py \
  tests/test_sa_local_readers.py \
  tests/test_sa_market_news_health.py \
  -q
```

Expected: PASS except for already documented environment-only tests. If any deterministic regression appears, stop and fix it before live evidence.

- [ ] **Step 2: Run grep gates**

Run:

```bash
rg -n "FROM (news|news_scores|fundamentals|iv_history|financial_data_cache|signals|sa_|macro_|cal_)" src scripts tests
rg -n "query_iv_history|query_fundamentals|get_financial_cache|query_news_scores|news_latest_scores|news_sentiment_summary" src scripts tests
rg -n "incremental_update\\(|--news|--iv|--fundamentals|--scores" src scripts tests
```

Expected:

- No runtime blocker in `src/service/data_scheduler.py`.
- No `LocalMarketDatabaseBackend` fallback to PG for `iv_history`, `fundamentals`, or `financial_data_cache`.
- `DatabaseBackend` PG methods may remain only as archive/dead-path methods before code cleanup.
- `migrate_to_supabase.py` rejects retired domains.
- Tests/docs/schema files are allowed.

- [ ] **Step 3: Commit docs preflight status**

If Tasks 1-4 are implemented and offline gates pass, update docs to say N9 batch-1 implementation is ready for live evidence, not live drop.

Commit:

```bash
git add docs/design/PG_EXIT_REMAINDER_SCOPING.md docs/design/PROJECT_PRIORITY_MAP.md docs/design/PG_EXIT_COMPLETION_PLAN.md
git commit -m "docs: stage N9 batch1 live evidence gate"
```

## Task 6: Live Evidence Preview Gate

This task reads PG and local files but performs no writes to PG or SQLite. Run only after Tasks 1-5 are merged and in a quiet window.

- [ ] **Step 1: Confirm quiet window**

Required operator state:

- Scheduler paused.
- Manual ingest paused.
- SA native host / extension sync paused.
- No migration/import script running.

Record process evidence:

```bash
ps -eo pid,ppid,etimes,stat,cmd | rg "data_scheduler|uvicorn|collect_|migrate_to_supabase|sa_native_host|n9_batch1"
```

Expected: no active writers. If this command prints an expected shell/rg process only, record it as non-writer.

- [ ] **Step 2: Run preview twice**

```bash
PY=/home/hyl/.virtualenvs/llm_app/bin/python3
SCRIPT=/mnt/md0/PycharmProjects/ArkScope/scripts/migration/n9_batch1_pg_drop.py

"$PY" "$SCRIPT" preview \
  --database-url "$DATABASE_URL" \
  --repo-root /mnt/md0/PycharmProjects/ArkScope \
  --output /tmp/n9-batch1-preview-1.json

"$PY" "$SCRIPT" preview \
  --database-url "$DATABASE_URL" \
  --repo-root /mnt/md0/PycharmProjects/ArkScope \
  --output /tmp/n9-batch1-preview-2.json

cmp /tmp/n9-batch1-preview-1.json /tmp/n9-batch1-preview-2.json
```

Expected: byte-identical.

- [ ] **Step 3: Reviewer gate**

Send the two preview files to review. Reviewer must independently verify:

- object existence
- row counts
- macro/cal empty proof
- `financial_data_cache` tiny/free SEC-only proof
- `news_scores` matches S-G expectations or any drift is explained
- `sa_*` present counts are consistent with local SA superset
- grep summary has zero blockers
- excluded tables still present

Do not proceed to dump until reviewer approves the evidence fingerprint.

## Task 7: Dump and Restore Gate

Run only after Task 6 reviewer approval.

- [ ] **Step 1: Create archive dir and dump**

```bash
UTC=$(date -u +%Y%m%dT%H%M%S%6NZ)
ARCHIVE=/mnt/md0/PycharmProjects/ArkScope/data/pg_archive/n9_batch1_$UTC
mkdir -p "$ARCHIVE"

PY=/home/hyl/.virtualenvs/llm_app/bin/python3
SCRIPT=/mnt/md0/PycharmProjects/ArkScope/scripts/migration/n9_batch1_pg_drop.py

"$PY" "$SCRIPT" dump \
  --database-url "$DATABASE_URL" \
  --expected-report /tmp/n9-batch1-preview-1.json \
  --archive-dir "$ARCHIVE"
```

Expected:

- `n9_batch1.dump`
- `evidence.json`
- `manifest.json`
- `pg_restore_list.txt`
- `function_ddl.sql`

- [ ] **Step 2: Verify restore**

```bash
RESTORE_DB=arkscope_n9_batch1_restore_$UTC

"$PY" "$SCRIPT" verify-dump \
  --database-url "$DATABASE_URL" \
  --archive-dir "$ARCHIVE" \
  --restore-db "$RESTORE_DB" \
  --confirm-create-drop-restore-db
```

Expected:

- `restore_proof.json` exists.
- `restore_proof.json` has `"ok": true`.
- restored row counts and row fingerprints match evidence.
- restore DB has been dropped.

- [ ] **Step 3: Reviewer gate**

Reviewer checks:

- dump sha256 in `manifest.json`
- restore proof `ok: true`
- counts/fingerprints match evidence
- no credentials or row payloads leaked into committed docs

Do not proceed to live drop until the user explicitly approves the reviewed fingerprint and archive path.

## Task 8: Live Destructive Drop Gate

Run only after explicit user approval. This is the first destructive live PG operation in the PG-exit program.

- [ ] **Step 1: Re-confirm quiet window**

Same requirements as Task 6. If any writer is active, stop.

- [ ] **Step 2: Run drop**

```bash
PY=/home/hyl/.virtualenvs/llm_app/bin/python3
SCRIPT=/mnt/md0/PycharmProjects/ArkScope/scripts/migration/n9_batch1_pg_drop.py

"$PY" "$SCRIPT" drop \
  --database-url "$DATABASE_URL" \
  --archive-dir "$ARCHIVE" \
  --reviewed-fingerprint "<REVIEWED_FINGERPRINT>" \
  --confirm-scheduler-paused \
  --confirm-native-host-paused \
  --confirm-destructive-drop
```

Expected sanitized output:

```json
{"status":"dropped","fingerprint":"<REVIEWED_FINGERPRINT>","dropped_tables":21}
```

- [ ] **Step 3: Post-drop PG catalog check**

Run:

```bash
"$PY" "$SCRIPT" postcheck \
  --database-url "$DATABASE_URL" \
  --archive-dir "$ARCHIVE"
```

Expected:

- every target table/view/function absent
- `prices` present
- `job_runs` present
- app-record tables present
- no unexpected dependencies remain

- [ ] **Step 4: App smoke**

With `DATABASE_URL` unset or PG unreachable where possible, smoke:

- news status/feed/search/scored local reads
- stored fundamentals local-cache honest miss/hit
- options IV history honest local result or empty, no PG fallback
- SA health/feed local reads
- macro calendar local reads
- provider health does not call dropped PG objects
- price reads still work through the remaining prices path

Any 500/error caused by missing dropped PG objects is a rollback candidate and must be triaged before proceeding.

## Task 9: Post-Live Docs and Cleanup

**Files:**

- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: `docs/design/PG_EXIT_COMPLETION_PLAN.md`

- [ ] **Step 1: Record live result**

Update docs with:

- reviewed evidence fingerprint
- archive dir path
- dump sha256
- restore proof result
- drop UTC timestamp
- dropped object list
- postcheck result
- remaining PG dependencies:
  - `prices`
  - `job_runs` until batch-2 soak collapse

- [ ] **Step 2: Record dead-path cleanup queue**

Add N9 cleanup candidates:

- `DatabaseBackend.query_news_scores`
- PG news/fundamentals/iv/archive methods that now reference absent tables
- `migrate_to_supabase` retired domain code
- old SA PG freeze/migration utilities if no longer useful after dump
- PG macro/cal store code if local-only macro is permanent

- [ ] **Step 3: Commit**

```bash
git add docs/design/PG_EXIT_REMAINDER_SCOPING.md docs/design/PROJECT_PRIORITY_MAP.md docs/design/PG_EXIT_COMPLETION_PLAN.md
git commit -m "docs: record N9 batch1 PG drop"
```

## Self-Review Checklist

- The plan does not authorize live drop without explicit user approval.
- The plan requires pre-drop hardening for IV fallback and retired migration domains.
- The plan includes reader grep evidence for every batch-1 target family.
- The plan includes macro/cal empty proof.
- The plan includes SA rollback-basis replacement by dump archive.
- The plan includes `pg_dump` plus restore verification, not just dump existence.
- The plan preserves `prices` and `job_runs`.
- The plan forbids `CASCADE`.
- The plan defines post-drop app smokes.
- The plan records docs updates after live drop.
