# Obsolete Config And Preflight Cleanup Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task-by-task.

**Goal:** Remove the unused Massive credential converter and V1 Tavily
preflight without changing current configuration, schemas or stored records.

**Architecture:** Delete the two leaf modules, not a forwarding alias. Preserve
current store behavior and its tests; remove only tests for the deleted APIs.

**Tech Stack:** Python, pytest, source-only Git inventory.

**Spec:** `docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md`, C15.

## Constraints

- Baseline: `a065a0c30a4f75995215cabc0e39dd2579c17c3d`, isolated integration worktree.
- No production database, credential, provider, runtime or selector access.
- Keep current installation/disposal, migration receipts and typed backup owners.
- This closes two leaf removals, not all C15, SQLite admission, or cross-platform work.

## Task 1: Remove Two Obsolete Leaves

Delete `src/massive_config_migration.py`, `src/security_lifecycle_retirement.py`
and `tests/test_tavily_retirement.py`. Modify
`tests/test_massive_config_authority.py`, `tests/test_massive_brand_surface.py`
and `tests/test_abandoned_surface_cleanup.py`.

- [x] Add the two source paths to the existing physical-absence guard. Run it
  before deletion: expect exactly two failures, `abandoned leaf remains`.
- [x] Delete both modules. Remove the migration import and five migration-only
  test definitions (six parameterized cases); remove the four Tavily tests.
  Remove the converter's now-stale brand allowlist entry.
- [x] Preserve and run `test_massive_is_the_only_current_config_namespace` and
  `test_store_startup_does_not_implicitly_migrate_a_legacy_row` unchanged.
- [x] Run absence, brand, provider config and current lifecycle schema/migration,
  investigation-retirement and listing-authority controls in one offline session.
  Expect zero failures. Full collection must lose only the ten obsolete cases
  and gain the two absence cases (net -8).
- [x] Repeat unbounded source/registration/current-doc reference searches; only
  absence guards may mention the deleted modules. Historical evidence remains.
- [x] Record exact commands/results and remaining boundaries; commit only this
  reviewed scope. No master merge or live operational changes.

Completed at `c4cb7109`; combined frozen acceptance and exact removed-node
inventory: `docs/superpowers/evidence/2026-09-14-runtime-cleanup-closeout/README.md`.
