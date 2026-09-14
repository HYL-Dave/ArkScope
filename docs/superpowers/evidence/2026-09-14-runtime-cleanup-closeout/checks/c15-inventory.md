# C15: Bounded First Removal Commit

Static inventory, 2026-09-14. Worktree: `/tmp/arkscope-research-output-boundary`.
HEAD verified as `a065a0c30a4f75995215cabc0e39dd2579c17c3d`; master as
`30bb31c779f26d5b691ceb29b0cabe91dcd9ff41`. Product/test worktree was clean.
Authority: [C15 audit row](/tmp/arkscope-research-output-boundary/docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md:413).

## Decision

**First commit: physically delete only `src/massive_config_migration.py` and
`src/security_lifecycle_retirement.py`, with the exact test collateral below.**
Neither needs current behavior relocated. Do not delete either mixed current
test coverage or any schema/backup owner to achieve this batch.

The other five C15 modules are excluded from this first commit. Three bundle
typed backup/restore responsibilities; two have executable inbound caller
chains. This is a partial C15 source cleanup, not C15 closure or permission to
change retained data.

## Exact Six-File Change Set

| Action | Path | Change |
| --- | --- | --- |
| Delete | `src/massive_config_migration.py` | Entire obsolete, explicit Polygon-to-Massive row-conversion module. |
| Delete | `src/security_lifecycle_retirement.py` | Entire V1-only Tavily storage preflight. Not the current investigation retirement/disposal tools. |
| Delete | `tests/test_tavily_retirement.py` | All four tests exercise only the deleted V1 preflight. |
| Modify | `tests/test_massive_config_authority.py` | Remove the migration import and five migration-only test definitions; retain the two current store tests and their helpers. |
| Modify | `tests/test_massive_brand_surface.py` | Remove only the `_ALLOWLIST` entry for `src/massive_config_migration.py`. |
| Modify | `tests/test_abandoned_surface_cleanup.py` | Add the two deleted source paths to `test_abandoned_leaf_is_physically_absent`'s existing parameter list. |

No other product, test, fixture, schema, operator, or current documentation change
is needed for this first boundary. Do not mark the audit's whole C15 item closed.

### Massive: Exact Collateral

The only direct importer is
[test_massive_config_authority.py:9](/tmp/arkscope-research-output-boundary/tests/test_massive_config_authority.py:9).
Delete its import of `MassiveConfigMigrationApprovalMismatch`,
`MassiveConfigMigrationConflict`, `migrate_massive_config_authority`, and
`preflight_massive_config_migration`.

Remove these five test definitions, including the parameterization belonging
to the fourth:

- `test_legacy_only_row_moves_exactly_and_preserves_timestamp` (line 55).
- `test_equal_duplicate_keeps_current_row_and_removes_legacy` (line 97).
- `test_different_duplicate_fails_closed_without_writes` (line 126).
- `test_absent_or_current_only_migration_is_an_idempotent_noop` (line 156).
- `test_apply_rejects_a_stale_preflight_under_the_write_lock` (line 181).

**Keep in the same file, without moving behavior:**

- [test_massive_is_the_only_current_config_namespace](/tmp/arkscope-research-output-boundary/tests/test_massive_config_authority.py:40): current Massive store round-trip and rejection of new Polygon writes.
- [test_store_startup_does_not_implicitly_migrate_a_legacy_row](/tmp/arkscope-research-output-boundary/tests/test_massive_config_authority.py:81): existing legacy rows remain unchanged on startup. Keep `_insert`, `_rows`, and the store/config, `sqlite3`, and `pytest` imports these tests use.

The brand test is a literal source-content owner, not an importer. Its
[allowlist entry](/tmp/arkscope-research-output-boundary/tests/test_massive_brand_surface.py:23)
must go because
[test_product_and_current_document_surfaces_have_only_reviewed_polygon_mentions](/tmp/arkscope-research-output-boundary/tests/test_massive_brand_surface.py:130)
rejects stale entries as well as new mentions. Keep every other brand/durable-wire exception.

Whole-module deletion also removes `MassiveConfigMigrationError`,
`MassiveConfigMigrationPreflight`, `MassiveConfigMigrationResult`, the two
derived exceptions and both public functions
([definitions](/tmp/arkscope-research-output-boundary/src/massive_config_migration.py:20),
[entrypoints](/tmp/arkscope-research-output-boundary/src/massive_config_migration.py:123)).
No backup API or canonical schema implementation lives in this file. Do not
change `src/data_provider_config.py`, stored keys, timestamps, or environment
resolution as collateral.

### Tavily: Exact Collateral

[security_lifecycle_retirement.py:9](/tmp/arkscope-research-output-boundary/src/security_lifecycle_retirement.py:9)
explicitly aliases `verify_v1_profile_connection`; its public API is only
`preflight_tavily_retirement`, `TavilyRetirementPreflight`,
`TavilyRetirementUnavailable`, and `TavilyRetirementBlocked`. It neither installs
current schema nor disposes of any data.

Delete [tests/test_tavily_retirement.py](/tmp/arkscope-research-output-boundary/tests/test_tavily_retirement.py:13),
whose fixture creates V1 schema and whose only test definitions are:

- `test_preflight_requires_explicit_existing_profile_path_and_never_creates` (line 32).
- `test_preflight_accepts_empty_legacy_storage_without_writes` (line 52).
- `test_preflight_rejects_stored_tavily_runs_with_exact_counts` (line 75).
- `test_preflight_rejects_stored_tavily_evidence_with_exact_counts` (line 115).

Those are obsolete-preflight contracts, not current disposal tests. The retained
V1-to-V2 converter's separate stored-Tavily/retired-web refusal remains owned by
[test_preflight_rejects_stored_tavily_or_retired_web_evidence_before_writes](/tmp/arkscope-research-output-boundary/tests/test_security_lifecycle_automation_migration.py:339).
Removing the preflight proves nothing about actual stored-row counts and does
not authorize dropping, transforming, or clearing those rows.

## Caller Boundary

For the two selected modules, exact module-name and public-entrypoint searches
found no product importer, registration, current-doc invocation, or dynamic
caller in the inspected source surfaces. Neither module has a `__main__` guard
or CLI parser. Massive has the importer and literal allowlist above; Tavily has
only its four-test importer. No other test imports those test modules.

The Tavily module and a `python -c` invocation remain in the dated
[2026-08-24 implementation plan](/tmp/arkscope-research-output-boundary/docs/superpowers/plans/2026-08-24-tavily-retirement.md:183).
That is historical instruction, not a current executable caller. Leave the
dated plan and evidence intact; do not create a replacement compatibility API.

These are bounded static findings, not certification of external/private
automation or installed data. Any separately identified still-required operator
invocation of these APIs would invalidate this first-commit boundary.

## Remaining Five: Do Not Include

| Module | Concrete reason to defer; exact affected test/caller owner |
| --- | --- |
| `src/security_lifecycle_migration.py` | Contains typed `CoordinatedBackups`, `CoordinatedRestoreRequired`, `create_coordinated_backups`, and `restore_coordinated_backups` ([line 699](/tmp/arkscope-research-output-boundary/src/security_lifecycle_migration.py:699)); preserve `tests/test_security_lifecycle_migration.py::test_migration_restore_requires_both_databases_before_reopen` (486). That file also owns the **current** `test_incomplete_receipt_blocks_all_lifecycle_writes` (144), which must move to a current schema/store test owner before any future file deletion. Its other tests exercise the obsolete conversion/resume path. |
| `src/security_lifecycle_automation_migration.py` | Typed `AutomationProfileBackup`, `AutomationRestoreRejected`, `create_automation_profile_backup`, and `restore_automation_profile_backup` ([line 650](/tmp/arkscope-research-output-boundary/src/security_lifecycle_automation_migration.py:650)). Preserve `tests/test_security_lifecycle_automation_migration.py`, especially backup/restore (619), retained-row mapping (402), honest legacy acceptance (435), and manual-evidence/attended-transition authority (464). Current-schema versions of the retained-data assertions and backup ownership must be established before deleting this bundle. |
| `src/ticker_identity_migration.py` | Typed `ProfileBackup`, `TickerIdentityRestoreRejected`, `create_profile_backup`, and `restore_profile_backup` ([line 351](/tmp/arkscope-research-output-boundary/src/ticker_identity_migration.py:351)). Preserve `tests/test_ticker_identity_migration.py`: bound restore (267), existing idle target refusal (316), durable sync (343), and sidecar-race refusal (371). Current schema tests are not substitutes for these recovery contracts. |
| `src/security_lifecycle_provider_migration.py` | Beyond `tests/test_security_lifecycle_provider_migration.py`, direct callers remain in `docs/superpowers/evidence/2026-09-05-lifecycle-terminal-cutover/scripts/install.py:39`, `fresh_check_v1.py:30`, and `fresh_check_v2.py:30`. Dynamic continuation through `2026-09-05-lifecycle-terminal-fresh-check/scripts/resume_check.py:18` calls `base.preflight_provider_upgrade` (165); rehearsal and archived tests load that chain. Also preserve the dual-source current-lineage test (11), create-only backup test (49), atomic membership test (88), and evidence/translation/identity preservation test (120). Not a standalone leaf deletion. |
| `src/security_lifecycle_provider_census.py` | Direct test importer: `tests/test_security_lifecycle_provider_census.py:9`. Additional caller: `docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/run_census.py:41`. `tests/test_lifecycle_provider_census_runner.py:35` dynamically loads that runner at collection and line 1710 invokes its CLI. The same file owns retained sealed-attestation (723) and stale-oracle receipt (1444) checks. Deleting only the oracle breaks this chain; deleting the runner tests wholesale loses saved-receipt ownership. Leave all of it out of this first commit. |

No new generic backup API, restored legacy conversion path, relocated canary,
or larger operator cleanup is proposed here.

## Protected Positive And Negative Owners

- Physical absence: extend [test_abandoned_leaf_is_physically_absent](/tmp/arkscope-research-output-boundary/tests/test_abandoned_surface_cleanup.py:11) with exactly the two selected paths. Existing tests elsewhere are not weakened to permit their return.
- Current typed schema/transition: retain `src/security_lifecycle_schema.py`, `src/ticker_identity_schema.py`, `src/ticker_identity_transition.py`, and all their tests. Current profile SQL still composes older declarations ([line 442](/tmp/arkscope-research-output-boundary/src/security_lifecycle_schema.py:442), [line 753](/tmp/arkscope-research-output-boundary/src/security_lifecycle_schema.py:753)); old version constants/verifiers are not deletion collateral. Positive schema owners include `tests/test_security_lifecycle_schema.py:89` and `tests/test_ticker_identity_schema.py:153`; negative mismatch owners include `tests/test_ticker_identity_schema.py:240` and `tests/test_security_lifecycle_automation_schema.py:1034`.
- Migration receipts remain live data: [assert_lifecycle_writes_available](/tmp/arkscope-research-output-boundary/src/security_lifecycle_schema.py:912) still refuses incomplete receipts through current writers. Keep its current-writer test noted above; do not drop `security_lifecycle_migration_receipts` because a module name resembles it.
- Current installation/disposal: retain `src/lifecycle_investigation/{__main__,migration,retirement,disposal}.py`. The CLI directly owns install/disposal commands ([line 8](/tmp/arkscope-research-output-boundary/src/lifecycle_investigation/__main__.py:8)). Keep `tests/test_lifecycle_investigation_migration.py::test_cutover_is_explicit_backed_up_and_preserves_existing_content`, `test_changed_installation_preview_is_rejected_before_backup`, both CLI tests, and all `tests/test_lifecycle_investigation_retirement.py` tests. Positive retained-investigation coverage is at line 120; negative dependency and receipt gates are at lines 180 and 265. These are different from the deleted Tavily-only module.
- Current listing authority: retain `data_sources/lifecycle_provider_census_transport.py`, `data_sources/listing_authority_transport.py`, `src/security_lifecycle_provider_scan.py`, `src/security_lifecycle_provider_authority.py`, and their tests. The live scan imports both transports ([line 11](/tmp/arkscope-research-output-boundary/src/security_lifecycle_provider_scan.py:11)). Positive/negative owners include `tests/test_security_lifecycle_provider_authority.py::test_terminal_requires_positive_delisting_and_all_independent_veto_checks` and `test_omitting_any_terminal_component_never_means_delisted`.
- Keep every saved receipt, seal, fixture, and backup. In particular, `tests/fixtures/security_lifecycle_legacy_37.json` has other test readers (`test_security_lifecycle_grounded_shadow.py:15`, `test_security_lifecycle_sec_evidence.py:165`). No fixture deletion is part of the six-file change set.

## Verification Limit

Only source/document/test inspection and this report write were performed.
No product/test edits, test collection, pytest, application imports, migrations,
collectors, network/providers, production data/configuration, environment files,
or credentials were accessed/executed. No agents were spawned. The separate
SQLite and CENSUS-SQL workstreams were not investigated. Test names above are
static ownership evidence, not newly passing results. This report is the only
file written in this task.
