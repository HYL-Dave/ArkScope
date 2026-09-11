# Task 2 Report

Status: implemented and scoped verification complete; ready for independent parent review.
No commits or staging performed. Base: `2842c497dabfdb0b13c315e22b206128eba9f57d`.
Workspace: `/tmp/arkscope-listing-sec-macro-convergence`.
Scope: assigned Task 2 files only, plus this scratch report and test artifacts.
No commits, production data/configuration, external network, installs, or restarts.

## Checkpoints

- Read plan Global Constraints, Task 2, approved SEC spec sections 4/9/11,
  schema ownership checkpoint, and offline runner.
- Existing linked worktree verified on `codex/listing-sec-macro-convergence`.
- Task 1 owns current `store.JournalError`, old store/review/projection deletion,
  and current store/source/history tests. Task 2 does not edit these files.
- Live model-tool detail remains; only obsolete `web_runs` is removed.
- No old-web data migration: all seven tables were absent in the approved
  inventory. Unknown external FK children remain disposal blockers.

## Baseline

Command (run from the workspace):

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-baseline /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_lifecycle_web_migration.py tests/test_security_lifecycle_population.py tests/test_security_lifecycle_current.py tests/test_security_lifecycle_policy_rollover.py tests/test_lifecycle_investigation_retirement.py tests/test_lifecycle_investigation_migration.py --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-baseline.xml
```

Result: **138 passed in 19.88s**, exit 0.
JUnit: `task2-baseline.xml`.

## Changed Files

| Action | File |
| --- | --- |
| Add | `src/sqlite_backup.py` |
| Modify | `src/lifecycle_investigation/migration.py` |
| Modify | `src/lifecycle_investigation/disposal.py` |
| Modify | `src/security_lifecycle_population.py` |
| Modify | `src/security_lifecycle_current.py` |
| Delete | `src/lifecycle_web_schema.py` |
| Delete | `src/lifecycle_web_migration.py` |
| Add | `tests/test_sqlite_backup.py` |
| Modify | `tests/test_lifecycle_investigation_retirement.py` |
| Modify | `tests/test_security_lifecycle_population.py` |
| Modify | `tests/test_security_lifecycle_current.py` |
| Delete | `tests/test_lifecycle_web_migration.py` |

`tests/test_security_lifecycle_policy_rollover.py` and parent-owned
`tests/test_lifecycle_investigation_migration.py` were exercised unchanged.
Scratch-only additions are this report and eight JUnit/fixture-root runs.
No additional product or test files were needed.

## Behavior Owners And Transfers

- `sqlite_backup.backup_connection(conn, path)` owns the useful primitive from
  the deleted old migration: `O_CREAT | O_EXCL`, mode 0600, real SQLite backup,
  explicit destination closure even on failure. Existing destinations and
  dangling symlinks are not replaced; the source connection remains open.
- Current installation and disposal directly import that helper. Approval
  digests, stopped-App requirements, same-path rejection, revalidation,
  atomic rollback, receipts and resumption remain.
- Disposal no longer adds old-web tables to its owned set, recognizes an
  old-web execution table, or disables/reinstates old-web triggers. Shared
  cases/assessments/evidence closure remains. Unknown external FK children
  retain the parent case and corresponding market observations; a child added
  after preview invalidates execution.
- Population capture/retention physically remove the old inventory reader and
  validator. The material shape is closed: even a correctly re-sealed
  `web_journal_inventory` field is rejected. Shared assessment, evidence,
  fact, translation and identity transition reference/digest validation remains.
- `get_current_review` stays live through the service and Research model-tool.
  Its version/as_of/item result and list/detail behavior remain; only obsolete
  `web_runs` and its projection import/error branch disappear.
- Six old migration test nodes disappear with that implementation. Useful
  stopped-App, backup preservation, approval-race, idempotency and rollback
  behavior moves to current installation in `test_sqlite_backup.py`.
  The old `before_backup` case is already covered by unchanged
  `tests/test_lifecycle_investigation_migration.py::test_changed_installation_preview_is_rejected_before_backup`.
- Old-web dependency deletion/guard-restoration coverage is retired. Useful
  atomic disposal rollback moves to shared automation evidence/facts, tested
  through failed receipt publication, exact preview readback, retained backup,
  current journal verification and successful retry. No old writer fixture stays.

## RED And Safety Evidence

Runtime edits followed the recorded assertion-based RED:
two failures prove obsolete schema/migration presence, five fail on the missing
backup owner, two expose the extra population inventory field, and one proves
a correctly sealed obsolete field was silently accepted. No ImportErrors.

Eleven pre-runtime controls passed: current installation backup
preservation/idempotency, stopped-App rejection, post-backup race and overwrite
rejection, postflight rollback, three existing migration owners, unrelated child
FK retention, scoped disposal/unrelated-data retention, and rejection of an
unrecognized material key.

The real WAL test keeps the source open and disables autocheckpoint. An immutable
main-file-only read sees no row while the WAL contains the committed row; the
backup includes that row and passes integrity_check. No mocked backup or
file-copy-only test.

Every inverse mutation was a narrow apply_patch edit to an owned runtime file,
followed by its command below and immediate finally restoration:

| Mutation | Observed failure |
| --- | --- |
| Backup: replace O_EXCL with O_TRUNC | Existing-destination owner: DID NOT RAISE FileExistsError |
| Disposal: replace external-child blocker assignment with pass | Preview exposes a disposable root; changed-preview execution reaches a late FK IntegrityError instead of preflight ValueError |
| Backup: use connection context manager without closing | Both closure owners fail: destination remains queryable |
| Detail: re-add web_runs: [] | Service and actual Research tool assertions fail on the extra field |

The detail mutation is supplemental shape evidence, not initial RED. Parent
already deleted the old projection while tests were being prepared; no transient
unresolved import was counted as product evidence.

Unchanged preservation controls exercised include:
- `test_retention_inventories_actual_evidence_and_translations_without_prose`
- `test_dangling_evidence_dependency_blocks_population_cleanup`
- `test_receipt_digest_corruption_never_becomes_a_historical_success`
- `test_disposal_deletes_draft_dependencies_but_retains_human_acceptance`
- `test_disposal_market_stage_requires_profile_receipt_and_receipts_cannot_be_forged`
- `test_market_dependencies_are_retained_before_profile_disposal`
- Current listing-source, reused-ticker history, confirmation effects,
  scheduling and policy-rollover controls in the full scoped run.

## Exact Remaining Test Commands

All commands ran from the workspace above using the supplied runner unchanged.
Each run has its own scratch fixture root.

### red

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-red /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_sqlite_backup.py tests/test_security_lifecycle_population.py::test_population_material_contains_only_current_reference_owners tests/test_security_lifecycle_population.py::test_population_manifest_rejects_unexpected_material_even_when_sealed tests/test_lifecycle_investigation_retirement.py::test_unrelated_child_reference_retains_case_and_market_observation tests/test_lifecycle_investigation_retirement.py::test_retirement_disposal_is_scoped_and_preserves_other_data tests/test_lifecycle_investigation_migration.py --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-red.xml
```

Result: 10 failed, 11 passed in 1.74s; exit 1, assertion-based RED. JUnit: `task2-red.xml`.

### green

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-green /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_sqlite_backup.py tests/test_security_lifecycle_population.py tests/test_security_lifecycle_current.py tests/test_security_lifecycle_policy_rollover.py tests/test_lifecycle_investigation_retirement.py tests/test_lifecycle_investigation_migration.py --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-green.xml
```

Result: 149 passed in 21.18s; exit 0. JUnit: `task2-green.xml`.

### mutation-overwrite

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-mutation-overwrite /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_sqlite_backup.py::test_backup_never_overwrites_an_existing_destination --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-mutation-overwrite.xml
```

Result: 1 failed in 0.19s; exit 1, mutation killed. JUnit: `task2-mutation-overwrite.xml`.

### mutation-external-fk

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-mutation-external-fk /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_lifecycle_investigation_retirement.py::test_unrelated_child_reference_retains_case_and_market_observation tests/test_lifecycle_investigation_retirement.py::test_disposal_stops_for_new_dependency_and_never_requires_quiescing_unrelated_sa --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-mutation-external-fk.xml
```

Result: 2 failed in 0.69s; exit 1, mutation killed. JUnit: `task2-mutation-external-fk.xml`.

### mutation-closure

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-mutation-closure /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_sqlite_backup.py::test_backup_explicitly_closes_destination_on_success_and_failure --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-mutation-closure.xml
```

Result: 2 failed in 0.19s; exit 1, mutation killed. JUnit: `task2-mutation-closure.xml`.

### mutation-detail

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-mutation-detail /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_security_lifecycle_current.py::test_current_review_and_list_share_one_closed_projection tests/test_security_lifecycle_current.py::test_research_reads_exactly_the_same_current_projection_and_no_mutation_tool --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-mutation-detail.xml
```

Result: 2 failed in 0.96s; exit 1, mutation killed. JUnit: `task2-mutation-detail.xml`.

### final

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-final /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_sqlite_backup.py tests/test_security_lifecycle_population.py tests/test_security_lifecycle_current.py tests/test_security_lifecycle_policy_rollover.py tests/test_lifecycle_investigation_retirement.py tests/test_lifecycle_investigation_migration.py --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-final.xml
```

Result: 149 passed in 20.21s; exit 0, all mutations restored. JUnit: `task2-final.xml`.

## Node Accounting

Counts parsed from actual baseline/GREEN JUnit records. Final confirms the same
149 passing nodes; no skips.

| File | Baseline | Final |
| --- | ---: | ---: |
| test_lifecycle_web_migration.py | 6 | 0 |
| test_sqlite_backup.py | 0 | 12 |
| test_security_lifecycle_population.py | 66 | 70 |
| test_security_lifecycle_current.py | 44 | 44 |
| test_security_lifecycle_policy_rollover.py | 9 | 9 |
| test_lifecycle_investigation_retirement.py | 10 | 11 |
| test_lifecycle_investigation_migration.py (unchanged parent owner) | 3 | 3 |
| Total | 138 | 149 |

Seven removed nodes, eighteen added, net +11.

Removed exact node IDs:

```text
tests/test_lifecycle_investigation_retirement.py::test_v1_web_dependencies_are_deleted_atomically_and_their_guards_restored
tests/test_lifecycle_web_migration.py::test_web_installation_has_digest_bound_backup_and_keeps_all_existing_rows
tests/test_lifecycle_web_migration.py::test_web_installation_rejects_changed_approval_and_never_overwrites_a_backup[after_backup]
tests/test_lifecycle_web_migration.py::test_web_installation_rejects_changed_approval_and_never_overwrites_a_backup[backup_exists]
tests/test_lifecycle_web_migration.py::test_web_installation_rejects_changed_approval_and_never_overwrites_a_backup[before_backup]
tests/test_lifecycle_web_migration.py::test_web_installation_requires_stopped_app_before_opening_any_store
tests/test_lifecycle_web_migration.py::test_web_installation_rolls_back_all_new_schema_on_failure_and_preserves_backup
```

Added exact node IDs:

```text
tests/test_lifecycle_investigation_retirement.py::test_disposal_rolls_back_shared_evidence_when_receipt_publication_fails
tests/test_lifecycle_investigation_retirement.py::test_unrelated_child_reference_retains_case_and_market_observation
tests/test_security_lifecycle_population.py::test_population_manifest_rejects_unexpected_material_even_when_sealed[unreviewed_retention]
tests/test_security_lifecycle_population.py::test_population_manifest_rejects_unexpected_material_even_when_sealed[web_journal_inventory]
tests/test_security_lifecycle_population.py::test_population_material_contains_only_current_reference_owners[False]
tests/test_security_lifecycle_population.py::test_population_material_contains_only_current_reference_owners[True]
tests/test_sqlite_backup.py::test_backup_captures_committed_wal_rows_without_changing_the_source
tests/test_sqlite_backup.py::test_backup_explicitly_closes_destination_on_success_and_failure[False]
tests/test_sqlite_backup.py::test_backup_explicitly_closes_destination_on_success_and_failure[True]
tests/test_sqlite_backup.py::test_backup_never_overwrites_an_existing_destination
tests/test_sqlite_backup.py::test_backup_rejects_a_dangling_destination_symlink
tests/test_sqlite_backup.py::test_current_installation_backup_preserves_unrelated_rows_and_is_idempotent
tests/test_sqlite_backup.py::test_current_installation_rejects_backup_races_and_existing_destinations[after_backup]
tests/test_sqlite_backup.py::test_current_installation_rejects_backup_races_and_existing_destinations[backup_exists]
tests/test_sqlite_backup.py::test_current_installation_requires_stopped_app_before_opening_any_store
tests/test_sqlite_backup.py::test_current_installation_rolls_back_schema_on_postflight_failure
tests/test_sqlite_backup.py::test_current_journal_has_no_obsolete_schema_owner[lifecycle_web_migration.py]
tests/test_sqlite_backup.py::test_current_journal_has_no_obsolete_schema_owner[lifecycle_web_schema.py]
```

## Static Checks And Concerns

```sh
git diff --check -- src/sqlite_backup.py src/lifecycle_investigation/migration.py src/lifecycle_investigation/disposal.py src/security_lifecycle_population.py src/security_lifecycle_current.py src/lifecycle_web_schema.py src/lifecycle_web_migration.py tests/test_sqlite_backup.py tests/test_lifecycle_web_migration.py tests/test_security_lifecycle_population.py tests/test_security_lifecycle_current.py tests/test_security_lifecycle_policy_rollover.py tests/test_lifecycle_investigation_retirement.py
rg -n 'lifecycle_web_|web_journal_inventory|web_journal|WEB_TABLES|WEB_TRIGGERS|web_review_id|web_runs' src/sqlite_backup.py src/lifecycle_investigation/migration.py src/lifecycle_investigation/disposal.py src/security_lifecycle_population.py src/security_lifecycle_current.py
rg -n 'lifecycle_web_(schema|migration|projection|store|review)' src tests -g '*.py'
```

Scoped diff check: exit 0, no output. Owned-runtime scan: exit 1, no matches.
Broad scan: exit 0, only tests remained, including Task 2 physical-absence names
and Task 1's in-progress old/source test transfers. No unowned files edited.

No Task 2 blocker known. Parent owns independent review, remaining Task 1 test
transfers, full integration/census, documentation and reviewed commits.
The supplied full baseline (7978 collected, 7966 passed, 12 skipped) was not
rerun or claimed as a final full-suite result here. This is source cleanup and
temporary-fixture validation only, not production schema disposal or a
user-ready SEC research workflow.

## JUnit SHA-256

Command: `sha256sum .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-*.xml`.

```text
5536210dc6e9de82221894ae302c4ea1bceeb1d99fdba80840bb0fe403f31a38  task2-baseline.xml
90c881e8ddad86c1c6def0b49246c9a21d6b28aa9f0bdd6cdbe788778df6547d  task2-final.xml
6cb71f8aff00e9bd1acc8123e17dd6636911eab22bf4eb89a0aec93a7882c03f  task2-green.xml
7e05c6c2bc5d2557d7f97e6f2a8be948ffb6c89dfac8558f57ce45f5b443ddc0  task2-mutation-closure.xml
1c2416680e69affcfd4c0b8eff92e59bafa24ad46a04b67645045e1ad4c24215  task2-mutation-detail.xml
a82b20dd77bcbacf12854f6691f1175bd3bf118cf879f06b15e8464f2a8b47c8  task2-mutation-external-fk.xml
e7d554898cdbf1c7bf3bcabb10d66b8069053646f640638415568c66d2aefabe  task2-mutation-overwrite.xml
ab5f8bc49a6b362d72a822e3736f7d1812388d8374e0fe3aa12a33abdf964c0e  task2-red.xml
```
