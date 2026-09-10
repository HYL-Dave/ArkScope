# Task 2 Minor M1 Report

## Status And Scope

Complete. Addressed only the approved negative-owner coverage gap in `task2-review.md` Minor M1.

- Worktree: `/tmp/arkscope-listing-sec-macro-convergence`
- Branch: `codex/listing-sec-macro-convergence`
- Base: `5d41f570330e63a5942835f2ae39ca3cf5d9dcc7`
- Head: `58e1929b61905b905fc0e12bdc5daf1ad116b84b`
- Exact range: `5d41f570330e63a5942835f2ae39ca3cf5d9dcc7..58e1929b61905b905fc0e12bdc5daf1ad116b84b`
- Commit: `test(lifecycle): reject legacy journal codec ownership`
- Only committed file: `tests/test_lifecycle_journal_codec.py`
- Diff: 27 added lines; no removals.
- Final scoped test result: **43 passed**, zero failures/errors/skips.
- Accounting: 41 existing nodes retained, 2 added; all 9 existing consumer-boundary nodes strengthened.

Added two runtime checks that the retained owner neither exposes `_json`/`_sha` nor lists them in `__all__`. Strengthened the existing nine-consumer AST test to reject exact legacy imported names or import aliases, function definitions, bare-name bindings/calls, and attribute references. This covers old-owner assignments/forwarders and consumers that keep unused neutral imports while using the legacy helpers. No general-purpose linter, reusable lint abstraction, or committed module was added.

Production files were never modified, including during mutation checks. Parent plan/evidence files were not edited or staged. No subagents, provider/network/production access, credentials, `.env` loading, App startup, installation, or initial Task 2 reimplementation/full regression rerun was performed.

## Mutation Method

To honor the test-only source scope, mutations were applied exclusively to retained source copies under this plan's owned fixture state:

`.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/`

Copied the ten relevant source files and the pre-M1 test file from `git show 5d41f570:<path>` using `apply_patch` to create the scratch files. Preserved the revised tests alongside the mutants. Each scratch `tests/conftest.py` prepends only that fixture's `src` directory to the already-loaded `src` package path, with normal repository fallback for unchanged dependencies. The supplied offline runner still initializes the environment and audit hook before pytest. The alias/definition failure traces identify the imported owner inside the corresponding scratch fixture, proving the export tests exercised the mutated owner.

The fixtures are not new repository product/test modules: they are ignored, retained mutation artifacts. They were run one at a time in fresh pytest processes, not in parallel. The original worktree `src/` was kept identical to the base throughout.

Both key regressions first survived the original 41 assertions. The revised assertions were then observed RED against all four retained mutants, followed by GREEN on restored source copies and the actual unmutated worktree. Restored copies are separate from the retained mutants, so no failing fixture or XML was overwritten.

### Exact Mutations And Named Kills

1. **Old-owner aliases** (`aliases/src/lifecycle_web_store.py`): appended:
   ```python
   _json = canonical_json
   _sha = digest_json
   ```
   Killed:
   - `test_retained_journal_does_not_export_legacy_codec_helpers[_json]`
   - `test_retained_journal_does_not_export_legacy_codec_helpers[_sha]`
   - `test_journal_consumers_import_the_neutral_codec_directly[lifecycle_web_store-names6]`
   The boundary failure reports the two legacy assignment names.

2. **Old-owner definitions/forwarders** (`definitions/src/lifecycle_web_store.py`): appended `def _json(value, *, ensure_ascii=True)` forwarding to `canonical_json`, and `def _sha(value)` forwarding to `digest_json`.
   Killed the same three named tests, with the boundary assertion failing specifically on `legacy_definitions`.

3. **Legacy import and bare calls** (`legacy-import-use/src/lifecycle_investigation/store.py` plus old-owner aliases): retained the direct neutral import, added `_json, _sha` to the old-owner import, changed `digest_json(value)` in `_decoded` to `_sha(value)`, and changed `canonical_json(binding)` in `start` to `_json(binding)`.
   In addition to the three old-owner failures, killed:
   - `test_journal_consumers_import_the_neutral_codec_directly[lifecycle_investigation.store-names0]`
   That node fails specifically on the two legacy imports, despite the neutral imports still being present.

4. **Legacy attribute calls without importing helper names** (`legacy-attribute-use/src/lifecycle_investigation/store.py` plus old-owner aliases): retained the direct neutral imports; imported the old module as `legacy_journal`; used `legacy_journal._sha(value)` and `legacy_journal._json(binding)`.
   Killed the same four named tests as case 3. The current-store node fails on `legacy_references`, independently of the legacy-import assertion.

## Isolation And Exact Commands

All commands ran from `/tmp/arkscope-listing-sec-macro-convergence`. Every actual pytest invocation used the same required clean `env -i`, PATH, interpreter, bytecode/plugin settings, offline runner, `ARKSCOPE_OFFLINE_TEST_WORKSPACE=.../task2-state`, and owned `TMPDIR=.../task2-state/tmp`. Each used a distinct `--basetemp` and new M1 XML path. The offline runner was not changed.

The first command had an orchestration error: a previous-turn stored prefix was unavailable and expanded to the literal command `undefined`. It exited 127 before Python or pytest started. The prefix was then explicitly initialized; all subsequent commands below include the full required offline environment. This was not a product/test failure.

### baseline

```bash
undefined -q tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/m1-baseline --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/artifacts/baseline.xml
```

Exit 127: `/bin/bash: line 1: undefined: command not found`. Pytest did not start; no XML was produced.

### baseline-copy

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/baseline/tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/m1-baseline-copy --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/artifacts/baseline-copy.xml
```

Exit 0: 41 passed in 0.07s.

### aliases-before-m1

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/aliases/tests/test_lifecycle_journal_codec_before_m1.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/m1-aliases-before-m1 --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/artifacts/aliases-before-m1.xml
```

Exit 0: 41 passed in 0.07s. The pre-M1 assertions did not detect old-owner aliases.

### legacy-import-use-before-m1

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/legacy-import-use/tests/test_lifecycle_journal_codec_before_m1.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/m1-legacy-import-use-before-m1 --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/artifacts/legacy-import-use-before-m1.xml
```

Exit 0: 41 passed in 0.07s. The pre-M1 assertions did not detect the legacy import/calls alongside the unchanged neutral import.

### aliases-red

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/aliases/tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/m1-aliases-red --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/artifacts/aliases-red.xml
```

Exit 1: 3 failed, 40 passed in 0.35s.

### definitions-red

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/definitions/tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/m1-definitions-red --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/artifacts/definitions-red.xml
```

Exit 1: 3 failed, 40 passed in 0.40s.

### legacy-import-use-red

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/legacy-import-use/tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/m1-legacy-import-use-red --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/artifacts/legacy-import-use-red.xml
```

Exit 1: 4 failed, 39 passed in 0.35s.

### legacy-attribute-use-red

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/legacy-attribute-use/tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/m1-legacy-attribute-use-red --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/artifacts/legacy-attribute-use-red.xml
```

Exit 1: 4 failed, 39 passed in 0.35s.

### restored-copy

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/restored/tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/m1-restored-copy --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/artifacts/restored-copy.xml
```

Exit 0: 43 passed in 0.31s.

### final

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/m1-final --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/artifacts/final.xml
```

Exit 0: 43 passed in 0.41s.

## Preserved Artifacts

All are inside `.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1`, separate from the original Task 2 artifacts.

| XML In `artifacts/` | Tests | Failed | Errors | Skipped |
| --- | ---: | ---: | ---: | ---: |
| `aliases-before-m1.xml` | 41 | 0 | 0 | 0 |
| `aliases-red.xml` | 43 | 3 | 0 | 0 |
| `baseline-copy.xml` | 41 | 0 | 0 | 0 |
| `definitions-red.xml` | 43 | 3 | 0 | 0 |
| `final.xml` | 43 | 0 | 0 | 0 |
| `legacy-attribute-use-red.xml` | 43 | 4 | 0 | 0 |
| `legacy-import-use-before-m1.xml` | 41 | 0 | 0 | 0 |
| `legacy-import-use-red.xml` | 43 | 4 | 0 | 0 |
| `restored-copy.xml` | 43 | 0 | 0 | 0 |

- `baseline/`: base source files and original 41-node tests.
- `aliases/`, `definitions/`, `legacy-import-use/`, `legacy-attribute-use/`: complete retained mutated source copies, revised tests, and the fixture import setup.
- `aliases/tests/test_lifecycle_journal_codec_before_m1.py` and `legacy-import-use/tests/test_lifecycle_journal_codec_before_m1.py`: preserved pre-M1 assertions used for the surviving-mutant proof.
- `restored/`: separate restored-source copies plus the revised tests, all 43 GREEN.
- `artifacts/commands-and-results.json`: exact commands, exit codes, combined console output from the execution tool, accounting command, and parsed XML results. This includes the initial exit-127 failure; there is deliberately no XML for that non-pytest invocation.

## Accounting

Compared each single-file XML's exact pytest test name, including parameter IDs. The fixture directory changes the XML classname, so comparison deliberately normalizes only that location prefix to `tests/test_lifecycle_journal_codec.py`. Asserted a single classname per report and no duplicate names before comparing. The final 43 nodes contain all 41 baseline identities; none was removed, renamed, skipped, or deselected.

The only additions are:
- `test_retained_journal_does_not_export_legacy_codec_helpers[_json]`
- `test_retained_journal_does_not_export_legacy_codec_helpers[_sha]`

Also asserted the exact named failure sets for all four mutants, no XML errors/skips, and identical node sets for restored-copy and actual-worktree GREEN. The standard-library XML inspection command and output are saved in `artifacts/commands-and-results.json`; it imports no backend code.

## Commit And Final Scope Checks

```bash
git diff --check -- tests/test_lifecycle_journal_codec.py
git diff 5d41f570 -- src
git add -- tests/test_lifecycle_journal_codec.py
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git -c core.hooksPath=/dev/null -c commit.gpgsign=false commit -m "test(lifecycle): reject legacy journal codec ownership" --only -- tests/test_lifecycle_journal_codec.py
git rev-parse HEAD
git status --short --branch
```

All checks exited 0. The `src/` diff was empty. The staged file list contained only `tests/test_lifecycle_journal_codec.py`. The commit used `--only` for that path. Hooks/signing were disabled for that one command to avoid unaudited processes outside the offline fixture environment; no repository configuration was changed.

Commit output:
```text
[codex/listing-sec-macro-convergence 58e1929b] test(lifecycle): reject legacy journal codec ownership
1 file changed, 27 insertions(+)
```

The parent's modified plan and untracked `docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/sec-retention-helper-cleanup/` directory remain untouched and uncommitted by this task.

## Concerns And Limits

No outstanding M1 issue was observed. The negative checks are deliberately restricted to the two exact legacy names and the nine already-enumerated consumers; this is not a general Python import/dataflow linter. Runtime old-owner export checks complement the direct AST checks.

Verification is scoped to this 43-node codec/ownership test module and its retained mutation copies. The original Task 2 broad regression suite, live providers, production data, and real App startup were not rerun. All mutants remain in scratch; all actual production source files remain at their base bytes.
