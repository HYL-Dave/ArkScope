# SA `use_local_sa` Local-Default Collapse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the SA capture domain to local-by-default: `use_local_sa` unset, explicit `false`, and env-unset all route SA reads/writes to `data/sa_capture.db` via `SACaptureDatabaseBackend`. The persisted flag and `ARKSCOPE_USE_LOCAL_SA` become provenance/rollback documentation only. This closes the last fresh-profile stranding hole found by the S-J Phase 2 poison-DSN smoke: on an empty profile, `DataAccessLayer._local_sa_enabled()` resolves `False` and SA readers reach the PostgreSQL backend even though the PG `sa_*` tables were dropped in N9 batch-1.

**Architecture:** One-line collapse at the existing family choke point (`_local_sa_enabled`, mirroring `_local_macro_enabled` / `_local_records_enabled`), plus removal of the pre-cutover `sa_capture.db`-exists guard in `_make_db_backend()`. Both stack-proved PG callsites (`provider_health.py:181` → `get_sa_refresh_meta`; `sa_market_news_health.py:409` `_run_health_query`) are fixed transitively: they duck-type on the backend, and `SACaptureDatabaseBackend` already overrides `get_sa_refresh_meta()` and carries `_sa_db` (which selects the local health-query branch). No per-callsite rewiring.

**Tech Stack:** Python 3, SQLite `sa_capture.db`, pytest; no frontend changes.

---

## Map Check / Authority

- `docs/design/PG_EXIT_REMAINDER_SCOPING.md` §13.6 follow-up (opened 2026-07-05, root cause + callsites pinned in `6147bba`): root cause is the truthy check at `src/tools/data_access.py:354`; stack-proved callsites are `src/service/provider_health.py:181` → `DatabaseBackend.get_sa_refresh_meta` and `src/service/sa_market_news_health.py:409` `_run_health_query` → `DatabaseBackend._get_conn`.
- `docs/design/PROJECT_PRIORITY_MAP.md` §10 (S-J Phase 2 entry) queues this follow-up explicitly.
- Semantic precedents: N9 batch-2 collapse (`use_local_market`/macro/job_runs), PG-exit closeout (`use_local_records`, `64530bb`). Same semantics: unset AND explicit false AND toggleless resolve local; legacy flag = provenance only.
- PG `sa_*` tables were dropped in N9 batch-1 (dump-once-then-drop; the archived dump is the recovery basis). There is no PG to "roll back" to — the old rollback lever is dead capital, which is why explicit `false` may safely stop meaning "PG".

**Out of scope:**

- Deleting the now-dead PG SA reader code (`sa_market_news_health` PG branch + `_HEALTH_SQL`, `db_backend.py` `sa_*` methods) — queue for the dead-code sweep; this slice only stops routing to them.
- `sa_comment_signals` writer unpause (follow-up #1 stays parked).
- The SA migration CLI rebuild guard (`test_migration_cli_refuses_rebuild_post_flip` semantics): the flag stays writable and the guard keeps reading it; with PG gone the rebuild path is permanently refused anyway.
- FileBackend DALs: SA capture remains unavailable there (no backend `_sa_db`); only the two stale toggle-referencing error strings are reworded.

## Decisions Locked For This Slice

1. **Collapse semantics (batch-2/closeout pattern):** `_local_sa_enabled()` returns `True`. Unset, explicit `false`, and `ARKSCOPE_USE_LOCAL_SA` all resolve local. Flag/env stay readable for provenance; no behavior.
2. **Missing `sa_capture.db` no longer keeps PG.** The `Path(candidate).exists()` guard in `_make_db_backend()` (comment: "enabling before migration keeps PG (safe)") is removed — post-batch-1 the PG branch reads dropped tables, so keep-PG is the unsafe branch. A fresh profile routes to `SACaptureDatabaseBackend` with an absent file and must degrade to honest-empty per surface (Task 2 pins the exact surface shapes).
3. **Suite-wide SA DB isolation.** Collapsing means every DAL construction in tests resolves an SA DB path. Add a conftest autouse `_isolate_sa_db` (`ARKSCOPE_SA_DB` → tmp), following the `_isolate_macro_calendar_db` precedent, so no test can touch the developer's real `data/sa_capture.db`.
4. **Acceptance = the criterion that exposed the hole:** fresh-profile poison-DSN E2E (`scripts.smoke.pg_unreachable_e2e` with `ARKSCOPE_PROFILE_DB` pointed at an empty DB) must report `ok: true`, `pg_attempts: []`.
5. **Explicit-DSN constructor path unchanged:** `DataAccessLayer(db_dsn="postgresql://…")` (a non-"auto" literal DSN) still builds plain `DatabaseBackend` — the docstring already classifies that as a pathological/test caller, and the runtime path is `db_dsn="auto"` → `_make_db_backend`.

## File Map

- Modify `tests/conftest.py` — add `_isolate_sa_db` autouse.
- Modify `src/tools/data_access.py` — collapse `_local_sa_enabled()`; remove the exists-guard in `_make_db_backend()`; refresh the selection-matrix docstring.
- Modify `src/tools/sa_tools.py` — reword the two `requires_local_sa` error strings that instruct enabling the retired toggle.
- Modify `tests/test_sa_routing.py` — flip the three named old contracts; add the toggleless/fresh-profile pins.
- Modify `tests/test_sa_local_readers.py` and/or `tests/test_sa_capture_backend.py` — fresh-profile (absent file) surface behavior pins.
- Possibly modify `src/tools/backends/sa_capture_backend.py` and/or `src/sa_capture_store.py` — ONLY if the Task 2 absent-file RED tests reveal a surface that raises instead of degrading; prefer the smallest read-only-connect guard.
- No changes expected: `src/service/provider_health.py`, `src/service/sa_market_news_health.py`, `src/sa/comment_signal_backfill.py` (all duck-type on the backend and are fixed transitively).

## Task 1: Hermeticity + Routing Collapse

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_sa_routing.py`
- Modify: `src/tools/data_access.py`

- [ ] **Step 0: Add suite-wide SA DB isolation**

In `tests/conftest.py`, after `_isolate_macro_calendar_db`, add:

```python
@pytest.fixture(autouse=True)
def _isolate_sa_db(tmp_path_factory, monkeypatch):
    """SA capture runtime defaults to data/sa_capture.db.

    After the use_local_sa local-default collapse, every DAL construction routes
    the SA domain to SACaptureDatabaseBackend, so a test that builds a DAL would
    otherwise resolve the developer's real sa_capture.db. Point the default at a
    throwaway path; tests that inject an explicit sa_db are unaffected.
    """
    if "ARKSCOPE_SA_DB" not in os.environ:
        monkeypatch.setenv(
            "ARKSCOPE_SA_DB",
            str(tmp_path_factory.mktemp("sa_capture") / "sa_capture.db"))
```

Note the conditional mirrors `_isolate_locks`, NOT `_isolate_profile_db`: `test_sa_routing.py` and the SA reader tests set `ARKSCOPE_SA_DB` per-test via `monkeypatch.setenv`, which layers fine either way, but an ambient operator override must not be silently discarded for suites that intentionally target a prepared fixture DB. (The profile DB is unconditional because it carries credentials; an SA capture DB does not.)

Run `pytest tests/test_sa_routing.py -q` — expected: PASS (pure isolation, no behavior change yet).

- [ ] **Step 1: Flip the three named old routing contracts (RED)**

In `tests/test_sa_routing.py`, these are the ONLY pre-existing tests that encode "unset/false/missing-file means not-SA-local". Do not touch other tests in the file.

1. `test_default_routes_local_market` — default construction now selects the SA backend (which still threads local market). Replace with:

```python
def test_default_routes_sa_local(env):
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db)
    assert b.market_db == str(env.market_db)
    assert b.strict is True
```

2. `test_sa_toggle_without_db_stays_local_market` — the exists-guard pin. Replace with:

```python
def test_sa_routes_local_even_without_existing_db_file(env):
    # PG sa_* tables are dropped (N9 batch-1): a missing local file must still
    # route local (honest empty), never resurrect the PG path.
    assert not env.sa_db.exists()
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db)
```

3. `test_rollback_is_instant_per_construction` — explicit `false` no longer selects a non-SA backend. Replace with:

```python
def test_explicit_false_is_provenance_only(env):
    env.profile.set_setting("use_local_sa", "false")
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db)
```

- [ ] **Step 2: Run the RED tests**

```bash
pytest tests/test_sa_routing.py -q
```

Expected: the three rewritten tests FAIL (current code selects `_StubLMDB` for default/false, and the exists-guard keeps `_StubLMDB` for the missing-file case). Every other test in the file must still PASS — if any OTHER test fails, STOP and report (unexpected contract coupling).

- [ ] **Step 3: Collapse the toggle and drop the exists-guard**

In `src/tools/data_access.py`, replace `_local_sa_enabled()`:

```python
    def _local_sa_enabled(self) -> bool:
        """SA capture domain → local sa_capture.db by default after the
        2026-07-05 collapse (S-J poison smoke follow-up): PG sa_* tables were
        dropped in N9 batch-1, so unset AND explicit false both resolve local —
        same collapse semantics as market/macro/job_runs/records. The legacy
        use_local_sa flag and ARKSCOPE_USE_LOCAL_SA are provenance only."""
        return True
```

In `_make_db_backend()`, replace the SA block:

```python
        sa_db = None
        if self._local_sa_enabled():
            from src.sa_capture_store import resolve_sa_db_path

            candidate = resolve_sa_db_path()
            if Path(candidate).exists():  # enabling before migration keeps PG (safe)
                sa_db = candidate
```

with:

```python
        # SA domain is hard-local (collapse 2026-07-05). A missing sa_capture.db
        # must still route local: PG sa_* was dropped in N9 batch-1, so the local
        # store is the only authority and an absent file reads as honest empty.
        sa_db = None
        if self._local_sa_enabled():
            from src.sa_capture_store import resolve_sa_db_path

            sa_db = resolve_sa_db_path()
```

Update the selection-matrix docstring bullet for SA from "SA on →" to "SA (always) →", keeping the rest of the matrix text intact.

- [ ] **Step 4: Run the routing file**

```bash
pytest tests/test_sa_routing.py -q
```

Expected: PASS (all tests, including `test_env_override_flips_without_setting` — env `true` still selects SA — and `test_migration_cli_refuses_rebuild_post_flip`, which reads the flag value, not the routing).

- [ ] **Step 5: Commit Task 1**

```bash
git add tests/conftest.py tests/test_sa_routing.py src/tools/data_access.py
git commit -m "fix: collapse sa capture to local default"
```

## Task 2: Fresh-Profile (Absent File) Surface Behavior

**Files:**
- Test: `tests/test_sa_local_readers.py`
- Modify (only if RED reveals a raise): `src/tools/backends/sa_capture_backend.py`, `src/sa_capture_store.py`

The exists-guard used to shield these paths; now an absent `sa_capture.db` is a reachable runtime state (fresh profile, first boot). `sa_capture_store.connect()` (write mode) already does `Path(path).parent.mkdir(parents=True, exist_ok=True)`, but read-only connects use a `mode=ro` URI, which raises `sqlite3.OperationalError` when the file is missing. Pin the surface behavior:

- [ ] **Step 1: Add RED tests for absent-file reads**

In `tests/test_sa_local_readers.py`, add (adapting the file's existing fixture style — it builds `SACaptureDatabaseBackend(FAKE_DSN, sa_db=...)` directly):

```python
def test_absent_sa_db_refresh_meta_is_honest_empty(tmp_path):
    backend = SACaptureDatabaseBackend(FAKE_DSN, sa_db=str(tmp_path / "missing.db"))
    meta = backend.get_sa_refresh_meta()
    assert meta == {} or meta.get("last_success") is None
    assert not (tmp_path / "missing.db").exists()  # a pure read must not create the DB


def test_absent_sa_db_market_news_query_is_honest_empty(tmp_path):
    backend = SACaptureDatabaseBackend(FAKE_DSN, sa_db=str(tmp_path / "missing.db"))
    rows = backend.query_sa_market_news(days=7, limit=5, offset=0)
    assert rows == [] or rows.get("items") == []
```

Adjust the exact call signatures to the real methods when writing the tests (the plan pins INTENT: honest empty, no exception, no file creation on read). If the current code already passes, keep the tests as regression pins and record "no code change needed" in the implementation notes.

- [ ] **Step 2: Run the RED tests**

```bash
pytest tests/test_sa_local_readers.py -q
```

Expected: the new tests either FAIL with `sqlite3.OperationalError: unable to open database file` (→ Step 3 applies) or PASS (→ skip Step 3, keep the pins).

- [ ] **Step 3 (conditional): Add the smallest read-only guard**

Prefer ONE guard at the choke point rather than per-method try/except: in `src/sa_capture_store.py`, make the read-only branch of `connect()` raise a typed sentinel or return honest-empty via the caller — the minimal shape is an existence check in `SACaptureDatabaseBackend._sa_read()` that raises the store's existing "empty" semantics. Whatever shape is chosen: no PG fallback, no file creation on read, and every SA read override degrades to its empty result. Re-run Step 2 to GREEN.

- [ ] **Step 4: End-to-end callsite proof (the two stack-proved sites)**

Add to `tests/test_sa_local_readers.py`:

```python
def test_provider_health_sa_meta_never_touches_pg_on_fresh_profile(monkeypatch, tmp_path):
    import psycopg2

    def _forbidden(*a, **k):
        raise AssertionError("SA health path must not attempt PostgreSQL")

    monkeypatch.setattr(psycopg2, "connect", _forbidden)
    backend = SACaptureDatabaseBackend(
        "postgresql://poison.invalid/arkscope", sa_db=str(tmp_path / "missing.db"))
    backend.get_sa_refresh_meta()  # must not raise AssertionError


def test_market_news_health_branch_selects_local_for_sa_backend(tmp_path):
    from src.service.sa_market_news_health import _run_health_query
    # _run_health_query branches on backend._sa_db — with the SA backend it must
    # take the local branch (no psycopg2 import path executed).
```

Complete the second test using the module's existing test conventions (there are existing `_run_health_query`/`compute_market_news_health` tests to mirror — reuse their fixture shapes rather than inventing new ones).

- [ ] **Step 5: Run the SA reader suite**

```bash
pytest tests/test_sa_local_readers.py tests/test_sa_capture_backend.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add tests/test_sa_local_readers.py
git commit -m "test: pin fresh-profile sa local degradation"
```

Include `src/tools/backends/sa_capture_backend.py` / `src/sa_capture_store.py` in the `git add` only if Step 3 was needed.

## Task 3: Stale Toggle Messaging

**Files:**
- Modify: `src/tools/sa_tools.py`
- Test: `tests/test_sa_tools.py` (only if a message is asserted verbatim)

- [ ] **Step 1: Reword the two toggle-instructing error strings**

`src/tools/sa_tools.py:538` and `:795` tell the user to enable `use_local_sa` — misleading once the toggle is provenance-only. Change both `"... requires the local sa_capture.db (use_local_sa); SA is local-first after the 3d cutover."` strings to:

```
"... requires the local sa_capture.db; this DAL backend has no SA capture routing (SA is local-only after the 2026-07-05 collapse)."
```

Keep the `empty_reason="requires_local_sa"` machine codes unchanged (consumers may assert on them; only the human text is stale).

- [ ] **Step 2: Grep for verbatim message assertions and stale copy**

```bash
rg -n "use_local_sa" src tests apps docs/design --glob '!docs/design/PG_EXIT*' | rg -v "provenance|collapse|USE_LOCAL_SA_KEY|test_sa_routing"
```

Flip any test asserting the old message text; update any active-doc copy that still describes unset→PG semantics (historical/archived docs stay as-is).

- [ ] **Step 3: Run sa_tools tests + commit**

```bash
pytest tests/test_sa_tools.py -q
git add src/tools/sa_tools.py tests/test_sa_tools.py
git commit -m "fix: retire use_local_sa wording from sa tool errors"
```

## Task 4: Focused Regression Gates

**Files:** test only

- [ ] **Step 1: Backend focused suite**

```bash
pytest \
  tests/test_sa_routing.py \
  tests/test_sa_local_readers.py \
  tests/test_sa_capture_backend.py \
  tests/test_sa_tools.py \
  tests/test_provider_health.py \
  tests/test_data_access.py \
  tests/test_sqlite_backend.py \
  tests/test_data_scheduler.py \
  -q
```

Expected: PASS. `test_provider_health.py` and `test_data_scheduler.py` are included because their DALs now route SA locally — any hidden dependence on the old PG default surfaces here, isolated by the new conftest autouse.

- [ ] **Step 2: Commit any gate fixes**

Only commit real corrections; no empty commit.

## Task 5: Poison Smoke Acceptance + Full A/B

**Files:** no code expected; scratch output stays uncommitted

- [ ] **Step 1: Fresh-profile poison-DSN E2E — THE acceptance criterion**

```bash
ARKSCOPE_PROFILE_DB=/tmp/arkscope-sa-collapse-empty-profile.db \
ARKSCOPE_DISABLE_SCHEDULER=1 \
python -m scripts.smoke.pg_unreachable_e2e --output scratchpad/sa-collapse-fresh-e2e.json
```

Expected: `ok: true`, `pg_attempts: []` — this exact invocation recorded `pg_attempts: 2` (the two SA callsites) before this slice; empty list proves the hole is closed. All 23 checks green (including `provider_config_policy` from S-J).

- [ ] **Step 2: Routine (real-profile) E2E stays green**

```bash
python -m scripts.smoke.pg_unreachable_e2e --output scratchpad/sa-collapse-real-e2e.json
```

Expected: `ok: true`, `pg_attempts: []` — the real profile (flag `true`) already routed local; the collapse must not disturb it.

- [ ] **Step 3: Full A/B**

Virgin `git archive` both sides from the main repo (NOT from a worktree — a locked-git-crypt worktree archive truncates), sequential runs, compare failure SETS. Acceptance: identical failure sets (39-entry known family as of `6147bba`); head adds only the new tests; any new deterministic failure blocks merge.

- [ ] **Step 4: Record evidence**

```text
base SHA / head SHA / base passed / head passed / failure-set diff
fresh-profile pg_attempts before: 2 → after: 0
```

## Task 6: Docs Closeout

**Files:**
- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md` (§13.6 follow-up → complete, with the before/after `pg_attempts` evidence)
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md` (top §10 entry; newest-first)
- Modify: this plan (Status header + verification record)

- [ ] **Step 1–3: Apply the three updates and commit**

```bash
git add docs/design/PG_EXIT_REMAINDER_SCOPING.md docs/design/PROJECT_PRIORITY_MAP.md docs/superpowers/plans/2026-07-05-sa-local-default-collapse.md
git commit -m "docs: close sa local default collapse"
```

## Review Gates

1. Default, explicit-false, and env-unset DAL constructions all select `SACaptureDatabaseBackend`; missing `sa_capture.db` does not resurrect PG.
2. Fresh-profile poison E2E: `pg_attempts` goes 2 → 0; routine real-profile E2E unchanged.
3. Absent-file SA reads are honest-empty, never create the file, never raise out of the health/feed surfaces.
4. `test_migration_cli_refuses_rebuild_post_flip` and `test_env_override_flips_without_setting` still pass unmodified (flag readability and env-true are unchanged).
5. No new code path reads PG `sa_*`; the dead PG readers are queued for the sweep, not deleted here.
6. Full A/B failure sets identical; only the named routing contracts were flipped, surgically.

## Known Watch Items For Review

- `_StubSABackend` in `test_sa_routing.py` masks real-backend behavior by design (selection tests); the absent-file behavior pins live in `test_sa_local_readers.py` against the REAL backend — do not conflate the two layers.
- The conftest `_isolate_sa_db` conditional (`if not in os.environ`) differs from `_isolate_profile_db`'s unconditional override — the justification is in the fixture docstring; reviewers should confirm no test relies on an ambient real `ARKSCOPE_SA_DB`.
- `sa_market_news_health`'s PG branch and `db_backend.py` `sa_*` methods become unreachable from runtime after this slice but are NOT removed — sweep item. Verify no test imports them in a way that forces earlier removal.
- `comment_signal_backfill` duck-types `_sa_db` and gains the local route automatically; its writer remains paused (follow-up #1) — this slice must not unpause it.
- Scheduler/provider-health tests construct DALs broadly; if Task 4 Step 1 surfaces failures outside the named flips, STOP and report (per the plan-test-layer discipline) rather than patching ad hoc.
