# Current Journal Cleanup And SEC Foundation

> Execute with subagent-driven development and RED-first task reviews.

**Goal:** Remove obsolete case-scoped journal implementations without losing
current investigation confirmation/history, and implement the first concrete SEC
research storage/configuration components.

**Base:** `2842c497dabfdb0b13c315e22b206128eba9f57d`.

**Spec:** `docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md`,
especially sections 4, 9 and 11. Retention authority is the already-recorded
`docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/sec-schema-ownership.md`.

**Architecture:** Current investigation owns its review and validated journal
reads directly. Generic lifecycle transitions retain their approval and reversal
contracts. Shared backup is an actual SQLite connection backup primitive, not an
obsolete feature facade. SEC configuration and paths implement approved storage
policy without prematurely registering incomplete tools.

## Global Constraints

- Work only in the existing isolated worktree. No merge, push, App restart,
  provider calls, dependency installation or production DB access this batch.
- Do not repeat the completed production retention inventory. No production
  DROP, row disposal, settings deletion or schema reset is authorized here.
- Physically remove abandoned code, not forwarding aliases or retired shells.
  Preserve current confirmations, reversals, digest-bound provenance and source
  captures. Existing shared tables are not garbage selected by prefix.
- Old web tables were absent in the authorized inventory. Do not create an old
  journal migration to support hypothetical unreleased installations. Unknown
  child references in an explicit cleanup fixture must still block disposal.
- Preserve persisted current `sla_web_` assessment IDs, packet `web` keys and
  error contracts where they are still consumed. A historical key is not an
  executable legacy branch.
- Read large current source material before opening a mutable transaction, then
  revalidate its binding inside the transaction. No missing provenance becomes a
  successful approval or history explanation.
- SEC default capture budget is 107374182400 bytes (100 GiB), adjustable up and
  down, positive whole bytes no larger than 2**53-1. Missing key alone defaults;
  explicit NULL or malformed persisted values fail explicitly.
- `SecResearchPaths` resolves the existing market DB authority and uses
  `P.parent / (P.name + ".sec-research")`; persist relative object keys only.
  Reject absolute/traversal/symlink-escape paths, including foreign-platform
  absolute forms. This task does not authorize downloads or preallocation.
- Offline tests use a clean environment, temporary stores, denied external
  network/production data, and the existing reviewed runner including Node PATH.

## Scope And Readiness

Tasks 1-2 finish the shared old journal dependency batch, not the entire cleanup
audit or actual-store disposal. Task 3 implements SEC foundation only. Catalog,
facts, captures/quota reservations, export/restore, three-tool atomic registration,
four-channel integration, schedule and UI remain separate implementation steps;
the new SEC feature must not be called user-ready after this plan.

### Task 1: Current Review, History And Source Owners

**Files:** Create `src/lifecycle_investigation/review.py`; modify current
`adoption.py`, `store.py`, `src/api/routes/lifecycle_investigation.py`,
`src/security_lifecycle_review.py`, `src/ticker_identity_transition.py`,
`src/ticker_identity_history.py`. Review-driven current producer fixes also touch
`agent.py`, `src/security_lifecycle_web_contract.py` and the now-unused two-phase
report helpers in `src/auth_drivers/lifecycle_web_usage.py`.
Delete `src/lifecycle_web_store.py`,
`src/lifecycle_web_review.py`, `src/lifecycle_web_projection.py` after consumers
are transferred. Own review/history/source-capacity/context/progress/read-report
tests, current journal/routes tests, journal-codec tests, and old journal/review/
read/gaps/attended-concurrency/usage tests (not old migration tests).

**Interfaces:** New review exports the same current function signatures as the
used old helpers: `assessment_id_for`, `acceptance_for`, `prepare`,
`prepare_on_connection`, `validated_adoption_read`, `confirm`, and
`investigation_transition_guard`. `store.JournalError(code)` owns current typed
journal failures. Use `adoption.validated_read` and `read_on_connection` directly;
no old-store dispatcher. Task 2 removes the obsolete projection consumer.

- [x] Add `tests/test_current_investigation_ownership.py` with physical absence
  and actual current preparation/confirmation owners; RED is an assertion that
  the old module is present or the new module is absent, not an ImportError.

```python
def test_current_review_has_no_abandoned_store_dependency():
    assert not (ROOT / "src/lifecycle_web_review.py").exists()
    assert (ROOT / "src/lifecycle_investigation/review.py").is_file()
```

- [x] Run the new absence RED owner and existing current confirmation/history
  positive controls before changing runtime code; record exact results.
- [x] Move only current review logic. Remove old-table acceptance/reader branches
  and old writer/options/control classes. Keep provider veto, target identity,
  date/freshness, evidence revision, binding/digest, atomic rollback, idempotency
  and automation-rejection checks. History must still use captured model/auth,
  not today's registry, and must report unavailable for unbound evidence.
- [x] Transfer useful old tests onto the current `li_` fixture and real current
  agent/store. Remove tests only when the behavior exclusively served the deleted
  old feature. Do not keep old product implementations inside test fixtures.
- [x] GREEN the affected tests. Inverse mutation: disable current validated-read
  binding verification; a named approval/concurrency owner must fail. Keep source
  gap and cancellation owners, not only AST absence checks.
- [x] Bind durable calls and steps, validate observations on reopen, and keep
  interrupted producers consistent with those read guarantees. Stop on host
  journal callback/read failure without another dispatch or a fabricated final
  payload, including a committed write whose acknowledgement fails. Current
  controller readback remains available with an explicit failed/unknown outcome.
  Normal cancellation/deadline preserves successfully recorded usage. These are
  real-controller temporary-store RED controls, not row-tampering simulations.
- [x] Report exact removed/added node IDs and behavioral owner transfers for
  review. Parent stages/commits task files after independent task review.

### Task 2: Schema, Backup And Population Dependency Cleanup

**Files:** Create `src/sqlite_backup.py`, `tests/test_sqlite_backup.py`; modify
`src/lifecycle_investigation/migration.py`, `disposal.py`,
`src/security_lifecycle_population.py`, `src/security_lifecycle_current.py`,
population/current/retirement/migration tests. Delete
`src/lifecycle_web_schema.py`, `src/lifecycle_web_migration.py` and its exclusive
tests. Parent owns documentation and shared absence integration checks.

**Interfaces:** `backup_connection(conn: sqlite3.Connection, path: Path) -> None`
uses SQLite backup with create-exclusive destination and explicit connection
closure. It must not replace an existing backup. Task 1 owns current journal
errors and the new review module. `get_current_review` is still a model-tool
consumer: preserve the current review result, remove only its obsolete
`web_runs` projection. Do not delete that live detail function.

- [x] Add physical old-schema absence RED and real temporary WAL backup tests.
  Expected RED: obsolete schema exists; new backup module does not yet exist.
  Positive controls cover unrelated populated tables and current journal setup.

```python
def test_backup_never_overwrites_an_existing_destination(tmp_path):
    existing = tmp_path / "backup.db"
    existing.write_bytes(b"owned-backup")
    with sqlite3.connect(":memory:") as conn:
        with pytest.raises(FileExistsError):
            backup_connection(conn, existing)
    assert existing.read_bytes() == b"owned-backup"
```

- [x] Extract the useful backup primitive; delete obsolete migration/schema.
  Current migration/disposal continue using exact approval/backup/receipt guards.
  Remove old-table hardcoded ownership and trigger disabling. Unknown foreign-key
  dependencies remain retained blockers, proven using an unrelated child table.
- [x] Remove old web inventory and retention projections from population capture
  and accepted material shape. Keep current case/assessment/translation/transition
  reference closure. Reject unexpected manifest material rather than ignoring it.
- [x] Preserve current model-tool detail/list behavior without obsolete web_runs;
  keep current listing-source/history controls. Delete old projection imports.
- [x] GREEN affected tests. Inverse mutations: allow destination overwrite and
  ignore external FK child; each must fail its named behavioral owner.
- [x] Report task test counts and schema/reference-safety evidence; no actual DB
  disposition is performed. Parent stages/commits after independent review.

### Task 3: SEC Typed Configuration And Portable Paths

**Files:** Create `src/sec_research/__init__.py`, `config.py`, `paths.py`,
`tests/test_sec_research_config.py`, `tests/test_sec_research_paths.py`.

**Interfaces:** `get_capture_budget_bytes(store) -> int` and
`set_capture_budget_bytes(store, value: int) -> int` wrap ProfileStateStore's
string storage (`get_settings_snapshot`, `set_setting`), keyed by
`sec_research.capture_budget_bytes`. `SecResearchPaths.resolve()` obtains the
existing market path; `SecResearchPaths.from_market_db(path)` binds an explicit
path for tests/export. `object_path(key: str) -> Path` resolves a safe relative
object key without creating directories or files. No new path env variable.

- [x] Add an assertion-based RED owner for each new module, then behavior tests
  using only temporary real profile stores. Cover default/NULL/malformed values,
  bool/float/nonfinite/fractional/overflow rejection, exact large integers,
  increases/decreases and unrelated settings unchanged.

```python
def test_budget_defaults_only_when_the_key_is_absent(profile):
    assert get_capture_budget_bytes(profile) == 107374182400
    profile.set_setting("sec_research.capture_budget_bytes", None)
    with pytest.raises(ValueError):
        get_capture_budget_bytes(profile)
```

- [x] Implement the typed accessor, absent-vs-NULL distinction and canonical
  decimal serialization without defaults masking corruption. A setting change
  cannot enable a schedule or create a capture root.
- [x] Test market env/default authority, relocated-root resolution, absolute and
  parent traversal, Windows drive/UNC paths, malformed keys and symlink escapes.
  Implement path identity/validation without filesystem writes.
- [x] GREEN; inverse mutations substitute default on NULL and omit escape checks,
  and prove named tests fail. Do not allocate 100 GiB or add incomplete UI/tools.
- [x] Report this as foundation complete, SEC workflow still in progress.

### Task 4: Integration, Census And SQLite Assessment

**Files:** Evidence in a new `current-journal-cleanup` child of the cleanup audit;
current audit/priority map updates. SQLite report uses primary-source URLs and
clean runtime probes, not app imports or actual database queries.

- [x] Collect current baseline node IDs before deletions, plus affected positive
  controls. Keep each test run's temporary data root separate.
- [x] Inventory old imports/names after integration; distinguish active stored
  receipt keys from obsolete executable names. Review every changed test owner.
- [x] Run complete backend suite, node-set accounting, census compare against
  `2842c497`; keep review_required output truthful. No fabricated expected counts.
- [x] Read-only task review and broad final review; fix findings and rerun affected
  owners. Preserve exact result and inverse-mutation logs in evidence.
- [x] Verify the reported UPSERT bug's actual preconditions and fixed version
  from SQLite sources, separately from WAL bugs. Measure Python's loaded SQLite
  and inspect app SQL/packaging. No system replacement, corruption claim or
  production integrity check without evidence/authorization.
- [x] Archive and hash evidence, commit reviewed work locally, and report cleanup,
  production-disposal, SEC-readiness and SQLite-upgrade status separately.

## Completed Checkpoint

Runtime/test commits: `e2f77cb7` (Tasks1-2) and `3095e1ad` (Task3). Final combined
backend: 8,116 passed / 12 unchanged skips, 772.31 seconds, exact 8,128 collected
and executed nodes. 191 removed / 341 added IDs are fully accounted for; 51
source/test identities are unchanged from the reviewed test snapshot. Task1 R4,
Task2 R1, Task3 and final R4 integration reviews have no remaining scoped blocker.
Publication verified 140 indexed artifacts, 4,523,445 bytes, exact tested patch
and source hashes. Evidence: `../evidence/2026-09-10-pre-release-cleanup-audit/current-journal-cleanup/README.md`.
Whole audit cleanup, actual-store disposition, complete SEC workflow and SQLite
runtime replacement are not completed by this plan. No merge or push performed.
