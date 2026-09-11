# Task 2 Revision 1: SQLite FK Target Identity

Status: fixed, scoped verification complete, files frozen for independent
re-review. No staging or commits.

Workspace: `/tmp/arkscope-listing-sec-macro-convergence`.
Review input: `task2-review.md`, P1 differently cased FK target retention.
Read the full independent review and traced the finding in the current source.

## Scope And Root Cause

Only these already-owned files were edited in this revision:

- `src/lifecycle_investigation/disposal.py`
- `tests/test_lifecycle_investigation_retirement.py`

All other runtime/test files and original Task 2 artifacts remain untouched.
This report and six distinct temporary test roots/JUnit logs are scratch-only.
No production DB, configuration/.env/token, external network/provider,
installation, restart, full-suite, Git index, commit, merge or push operations.

The reported pre-existing bug was reproduced before runtime edits. PRAGMA
foreign_key_list retains declared parent spelling, while closure,
market_dependency and deletion ordering used Python identity comparisons.
Thus valid differently cased CASCADE children were absent from retention
selection and both pre-backup and locked revalidation repeated the omission.
Postflight FK checks cannot detect rows already removed by a valid cascade.

## Fix

`foreign_keys` now resolves each declared parent through:

```sql
SELECT name FROM sqlite_master
WHERE type='table' AND name=? COLLATE NOCASE
```

Edges carry the actual catalog table name. All existing consumers share that
resolution; no separate comparison fixes or old-schema ownership branches.
SQLite determines identity, not Unicode casefold. A declared target without a
catalog entry keeps its original spelling, preserving existing missing-target
handling. Approval digests, row selection, backup/receipt guards and current
schema definitions are unchanged.

The additional runtime change relative to the reviewed Task 2 snapshot is:

```python
# PRAGMA preserves declared spelling; ownership uses SQLite identities.
target = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=? COLLATE NOCASE",
    (ordered[0][2],)).fetchone()
parent = target[0] if target is not None else ordered[0][2]
edges.append((table, parent, tuple((row[3], row[4]) for row in ordered)))
```

## RED, Controls And Mutations

- Four preview/apply tests cover uppercase and mixed-case parent targets on
  profile cases and market observations, all with ON DELETE CASCADE. They
  verify retained roots/market IDs, execute both empty stages, and retain actual
  parent/child rows with clean foreign_key_check results.
- Eight apply-guard tests add those children after preview or after the real
  backup but before BEGIN IMMEDIATE. The former fails before backup creation;
  the latter fails at locked revalidation with its backup retained. Both keep
  the parent and child and publish no completion receipt. Market tests first
  complete the real required profile stage.
- Two positive controls use a distinct external table with U+017F at the start
  of its name. SQLite does not alias it to the ASCII owned table; Unicode
  casefold would. Approved disposal removes only the intended owned rows and
  retains the distinct external table/child.
- A real current investigation is prepared/confirmed, then an independent SEC
  fixture is disposed. The current journal read is identical afterward and
  repeated current confirmation returns already_applied.
- All eleven prior retirement controls remain unchanged, including lowercase
  profile/market external references, late dependencies, human acceptance,
  current action history, receipt guards, rollback and resumability.

Initial RED: all 12 requested cased-CASCADE owners failed as expected. The two
Unicode fixtures initially used the protected security_lifecycle_ prefix and
were rejected before the identity behavior was reached. Their names were
corrected to start with U+017F, outside that ASCII schema namespace, without
changing runtime. Both initial and corrected logs are retained. Clean RED was
**12 failed / 14 passed**, no collection/import errors. Eight apply tests failed
because ValueError was not raised; four previews wrongly offered disposable
roots. The fix followed that confirmed RED.

The GREEN retirement run passed all 26 nodes.

Inverse mutations used apply_patch in disposal.py, ran the named owners, and
were immediately restored in finally before the next run:

1. Replace `parent = target[0] if target is not None else ordered[0][2]` with
   `parent = ordered[0][2]`: **12 failed**, reproducing the original preview
   omissions and eight unblocked applies.
2. Replace it with `parent = ordered[0][2].casefold()`: **2 failed**, because
   the distinct-Unicode controls wrongly retained the actual owned roots.
   Exact assertion: expected the disposable case, got an empty roots list.

Final scope: **164 passed**, zero failure/error/skip records. Parsed JUnit
comparison with original task2-final.xml: fifteen added nodes, none removed.
Per-file counts: backup 12, population 70, current 44, policy rollover 9,
retirement 26, current migration 3. Full frozen-suite acceptance remains parent
owned; no whole-branch result is claimed.

## Exact Commands And Logs

All commands ran from the workspace above with the supplied runner unchanged.
Every invocation used a unique scratch root.

### red

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-red /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_lifecycle_investigation_retirement.py --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-red.xml
```

Actual console result: 14 failed, 12 passed in 3.73s; exit 1. Twelve real cased-CASCADE failures plus two fixture schema-prefix failures; not the clean RED checkpoint.
Exact testcase/failure log: `task2-r1-red.xml`.

### red-confirmed

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-red-confirmed /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_lifecycle_investigation_retirement.py --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-red-confirmed.xml
```

Actual console result: 12 failed, 14 passed in 3.72s; exit 1. Expected assertion failures only; runtime unchanged.
Exact testcase/failure log: `task2-r1-red-confirmed.xml`.

### green

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-green /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_lifecycle_investigation_retirement.py --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-green.xml
```

Actual console result: 26 passed in 3.66s; exit 0.
Exact testcase/failure log: `task2-r1-green.xml`.

### mutation-declared

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-mutation-declared /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_is_retained_by_preview_and_empty_apply tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_added_after_preview_blocks_apply --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-mutation-declared.xml
```

Actual console result: 12 failed in 1.69s; exit 1. Mutation caught by every cased-CASCADE owner.
Exact testcase/failure log: `task2-r1-mutation-declared.xml`.

### mutation-casefold

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-mutation-casefold /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_lifecycle_investigation_retirement.py::test_disposal_does_not_casefold_distinct_non_ascii_fk_targets --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-mutation-casefold.xml
```

Actual console result: 2 failed in 0.70s; exit 1. Both distinct-Unicode controls caught overbroad folding.
Exact testcase/failure log: `task2-r1-mutation-casefold.xml`.

### final

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-final /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q tests/test_sqlite_backup.py tests/test_security_lifecycle_population.py tests/test_security_lifecycle_current.py tests/test_security_lifecycle_policy_rollover.py tests/test_lifecycle_investigation_retirement.py tests/test_lifecycle_investigation_migration.py --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-final.xml
```

Actual console result: 164 passed in 22.60s; exit 0. All mutations restored, no skips or errors.
Exact testcase/failure log: `task2-r1-final.xml`.

## Added Node IDs

```text
tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_added_after_preview_blocks_apply[after_backup-market-mixed]
tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_added_after_preview_blocks_apply[after_backup-market-upper]
tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_added_after_preview_blocks_apply[after_backup-profile-mixed]
tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_added_after_preview_blocks_apply[after_backup-profile-upper]
tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_added_after_preview_blocks_apply[after_preview-market-mixed]
tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_added_after_preview_blocks_apply[after_preview-market-upper]
tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_added_after_preview_blocks_apply[after_preview-profile-mixed]
tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_added_after_preview_blocks_apply[after_preview-profile-upper]
tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_is_retained_by_preview_and_empty_apply[market-mixed]
tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_is_retained_by_preview_and_empty_apply[market-upper]
tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_is_retained_by_preview_and_empty_apply[profile-mixed]
tests/test_lifecycle_investigation_retirement.py::test_cased_cascade_fk_is_retained_by_preview_and_empty_apply[profile-upper]
tests/test_lifecycle_investigation_retirement.py::test_disposal_does_not_casefold_distinct_non_ascii_fk_targets[market-distinct-unicode]
tests/test_lifecycle_investigation_retirement.py::test_disposal_does_not_casefold_distinct_non_ascii_fk_targets[profile-distinct-unicode]
tests/test_lifecycle_investigation_retirement.py::test_disposal_preserves_approved_current_investigation_and_idempotent_confirmation
```

## Frozen File Hashes

Command:

```sh
sha256sum src/lifecycle_investigation/disposal.py tests/test_lifecycle_investigation_retirement.py
git diff --check -- src/lifecycle_investigation/disposal.py tests/test_lifecycle_investigation_retirement.py
```

Diff check: exit 0, no output.

```text
d55cd056293761452c47762d1511c70cd535c9911d149ef54d8e1fd9b80a8865  src/lifecycle_investigation/disposal.py
6a6d281e5ba1e741143a09f4c05d295c6676ee33a7af651486468300c2167418  tests/test_lifecycle_investigation_retirement.py
```

These supersede the old reviewed hashes
`8cf0c7394b7b89686aa3dea8334132329cea7001fefaa6748c8711dd3151ddef`
and `dd9f21ea82d5d1cca7749e21904e050005efe40b42ecffc89e0456173322fd67`.
Parent updates the review package; the old package was not edited.

## Evidence Hashes

Command: `sha256sum .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-r1-*.xml`.

```text
a5c19ad704c95c008b90d00770d567d25ff5082c94eeee0218f861d2a168cbd4  task2-r1-final.xml
dd01683cead321af4e1836838e78c384d882869381b5b5d6d9712a3a48e52813  task2-r1-green.xml
13188b7042ca98cb4497dcec4978cfb7b7154ba77f075c0d18c232cb156c97cb  task2-r1-mutation-casefold.xml
ee96e8c41d6f2cd03d261ecc433c11f313ed1eaf69412d23b51e7f14f57c14ba  task2-r1-mutation-declared.xml
09bc5247df53351a77aa2ca55c26e3666c64924fe10cae1f5b5b10149c357d9e  task2-r1-red-confirmed.xml
afadb12ac2f3823ca5ba8c5151ce1fdfe12642e99a1ff0d2e1916198f759a520  task2-r1-red.xml
```

No outstanding blocker is known for this named revision. Independent re-review
and parent full-suite execution remain pending. No real-store disposition is
authorized or performed by these fixture tests.

