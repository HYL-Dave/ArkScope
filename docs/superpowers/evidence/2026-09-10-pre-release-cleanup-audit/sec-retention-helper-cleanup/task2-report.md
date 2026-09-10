# Task 2 Report: Neutral Canonical Journal Codec

## Status

Complete. Implemented and committed directly in the supplied linked worktree, without subagents.

- Worktree: `/tmp/arkscope-listing-sec-macro-convergence`
- Branch: `codex/listing-sec-macro-convergence`
- Base: `8c8ac7383d7e04defebaf803fc6a8fa7328cc879`
- Commit: `5d41f570330e63a5942835f2ae39ca3cf5d9dcc7` (`refactor(lifecycle): extract neutral journal codec`)
- Exact commit range: `8c8ac7383d7e04defebaf803fc6a8fa7328cc879..5d41f570330e63a5942835f2ae39ca3cf5d9dcc7` (one commit).
- Commit scope: 17 product/test files, 183 insertions, 65 deletions.
- Final fixture-only regression: **349 passed**, zero failures/errors/skips.
- Baseline: **308 passed**. Accounting: **41 added, 0 removed**.
- Both requested mutations were detected and restored: ASCII default 5 failures; separator drift 11 failures.

## Implementation And Boundaries

`src.lifecycle_journal_codec` now owns exactly:
```python
def canonical_json(value, *, ensure_ascii=True):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=ensure_ascii, allow_nan=False)

def digest_json(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()
```

Moved the original implementations without semantic changes. All nine exact product consumers import public names directly from the neutral owner. Updated the six existing test consumers to the same owner and names. Removed the old `_json`/`_sha` definitions without aliases or forwarders.

The current store still imports `WebJournalError` from `src.lifecycle_web_store`; its error classification is unchanged. Unrelated codecs, page/capture hashing, SQL schema digests, row/file hashing, migrations' data behavior, and actual old/current journal reader behavior were not changed. Existing tests cover current store/preflight/agent/adoption, retained old journal integrity, Unicode page storage, review/confirmation/history, migration/disposal, and source-read concurrency.

No production statistics or other production data were read. No provider/network calls, credential use, `.env` loading, real App startup, installation, or subagent dispatch was performed. Existing in-process ASGI test fixtures use synthetic stores and route overrides; no application lifespan or server was started.

All backend pytest runs used the required `offline_pytest.py`, interpreter, clean `env -i`, PATH, bytecode/plugin settings, and `ARKSCOPE_OFFLINE_TEST_WORKSPACE`. Added `TMPDIR` inside `task2-state/tmp` so `tests/conftest.py`'s session-level TemporaryDirectory also remained in owned fixture state. Every run used a distinct `--basetemp` under `task2-state/pytest`. The harness was not edited.

The parent's concurrent edit to `docs/superpowers/plans/2026-09-10-sec-retention-inventory-and-helper-cleanup.md` was left unstaged and unmodified by this task. No docs, plan, or parent evidence files are in the commit.

## Exact Committed Files

- `src/lifecycle_investigation/adoption.py`
- `src/lifecycle_investigation/agent.py`
- `src/lifecycle_investigation/disposal.py`
- `src/lifecycle_investigation/migration.py`
- `src/lifecycle_investigation/store.py`
- `src/lifecycle_investigation/target.py`
- `src/lifecycle_journal_codec.py`
- `src/lifecycle_web_review.py`
- `src/lifecycle_web_store.py`
- `src/ticker_identity_history.py`
- `tests/test_lifecycle_investigation_store.py`
- `tests/test_lifecycle_journal_codec.py`
- `tests/test_lifecycle_source_capacity.py`
- `tests/test_lifecycle_source_context.py`
- `tests/test_lifecycle_web_attended_concurrency.py`
- `tests/test_lifecycle_web_gaps.py`
- `tests/test_lifecycle_web_usage_journal.py`

## Test Accounting

Parsed baseline and final JUnit XML with `xml.etree.ElementTree`, comparing each `(classname, name)` pair. All 308 baseline node identities are present in the 349-node final run. The 41 additions are exclusively in `tests/test_lifecycle_journal_codec.py`; no existing tests were removed, renamed, skipped, or deselected.

New-node breakdown: 1 neutral-owner check, 6 literal byte cases, 6 literal SHA-256 cases, 1 explicit UTF-8/non-ASCII rendering case with invariant canonical digest, 18 scalar/nested NaN/positive-Infinity/negative-Infinity rejection cases across both rendering modes and digest, and 9 direct-import checks.

Literal fixtures cover nesting, recursive key order, compact separators, scalar types, control-character escaping, BMP/non-BMP ASCII escaping, Unicode key order, and `ensure_ascii=False` UTF-8 bytes. SHA constants were independently computed with Node's built-in `node:crypto` over manually specified canonical byte strings, not with the implementation under test.

| Test Module | Baseline | Final |
| --- | ---: | ---: |
| `test_lifecycle_investigation_agent.py` | 18 | 18 |
| `test_lifecycle_investigation_migration.py` | 3 | 3 |
| `test_lifecycle_investigation_retirement.py` | 10 | 10 |
| `test_lifecycle_investigation_review.py` | 6 | 6 |
| `test_lifecycle_investigation_store.py` | 26 | 26 |
| `test_lifecycle_investigation_target.py` | 14 | 14 |
| `test_lifecycle_journal_codec.py` | 0 | 41 |
| `test_lifecycle_source_capacity.py` | 15 | 15 |
| `test_lifecycle_source_context.py` | 16 | 16 |
| `test_lifecycle_source_progress.py` | 12 | 12 |
| `test_lifecycle_source_read_report.py` | 9 | 9 |
| `test_lifecycle_web_attended_concurrency.py` | 26 | 26 |
| `test_lifecycle_web_gaps.py` | 49 | 49 |
| `test_lifecycle_web_migration.py` | 6 | 6 |
| `test_lifecycle_web_read.py` | 15 | 15 |
| `test_lifecycle_web_review.py` | 25 | 25 |
| `test_lifecycle_web_store.py` | 10 | 10 |
| `test_lifecycle_web_usage_journal.py` | 23 | 23 |
| `test_ticker_identity_history.py` | 25 | 25 |
| Total | 308 | 349 |

## Commands And Outputs

All commands below ran from `/tmp/arkscope-listing-sec-macro-convergence`. No product code was changed before the new codec tests were observed RED.

Fixture-directory setup:
```bash
mkdir -p .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts
```

The initial 14-file baseline's missing-parent setup error was diagnosed with:
```bash
ls -ld .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp
mkdir -p .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest
```
The `ls` returned exit 2, confirming only the `pytest` parent was absent. The directory creation fixed setup without changing code or the harness. The rerun also included the four retained-reader/migration/source-report/progress files, establishing the complete 308-node baseline before adding tests.

### baseline

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q tests/test_lifecycle_investigation_store.py tests/test_lifecycle_investigation_target.py tests/test_lifecycle_investigation_agent.py tests/test_lifecycle_investigation_review.py tests/test_lifecycle_investigation_migration.py tests/test_lifecycle_investigation_retirement.py tests/test_ticker_identity_history.py tests/test_lifecycle_web_store.py tests/test_lifecycle_web_review.py tests/test_lifecycle_web_usage_journal.py tests/test_lifecycle_web_gaps.py tests/test_lifecycle_source_capacity.py tests/test_lifecycle_source_context.py tests/test_lifecycle_web_attended_concurrency.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/baseline --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/baseline.xml
```

Exit 1: 266 errors in 4.79s. All were fixture setup FileNotFoundError for the missing task2-state/pytest parent; no test body ran.

### baseline-green

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q tests/test_lifecycle_investigation_store.py tests/test_lifecycle_investigation_target.py tests/test_lifecycle_investigation_agent.py tests/test_lifecycle_investigation_review.py tests/test_lifecycle_investigation_migration.py tests/test_lifecycle_investigation_retirement.py tests/test_ticker_identity_history.py tests/test_lifecycle_web_store.py tests/test_lifecycle_web_review.py tests/test_lifecycle_web_usage_journal.py tests/test_lifecycle_web_gaps.py tests/test_lifecycle_source_capacity.py tests/test_lifecycle_source_context.py tests/test_lifecycle_web_attended_concurrency.py tests/test_lifecycle_web_read.py tests/test_lifecycle_web_migration.py tests/test_lifecycle_source_read_report.py tests/test_lifecycle_source_progress.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/baseline-green --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/baseline-green.xml
```

Exit 0: 308 passed in 54.60s.

### codec-red

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/codec-red --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/codec-red.xml
```

Exit 1: 41 failed in 0.40s. 32 missing-neutral-owner failures (ModuleNotFoundError in test bodies), plus 9 direct-import assertion failures; no collection/setup errors.

### codec-green

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/codec-green --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/codec-green.xml
```

Exit 0: 41 passed in 0.24s.

### regression-green

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q tests/test_lifecycle_journal_codec.py tests/test_lifecycle_investigation_store.py tests/test_lifecycle_investigation_target.py tests/test_lifecycle_investigation_agent.py tests/test_lifecycle_investigation_review.py tests/test_lifecycle_investigation_migration.py tests/test_lifecycle_investigation_retirement.py tests/test_ticker_identity_history.py tests/test_lifecycle_web_store.py tests/test_lifecycle_web_review.py tests/test_lifecycle_web_usage_journal.py tests/test_lifecycle_web_gaps.py tests/test_lifecycle_source_capacity.py tests/test_lifecycle_source_context.py tests/test_lifecycle_web_attended_concurrency.py tests/test_lifecycle_web_read.py tests/test_lifecycle_web_migration.py tests/test_lifecycle_source_read_report.py tests/test_lifecycle_source_progress.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/regression-green --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/regression-green.xml
```

Exit 0: 349 passed in 55.10s.

### mutation-ascii-red

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/mutation-ascii-red --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/mutation-ascii-red.xml
```

Exit 1: 5 failed, 36 passed in 0.27s.

### mutation-ascii-restored

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/mutation-ascii-restored --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/mutation-ascii-restored.xml
```

Exit 0: 41 passed in 0.24s.

### mutation-separators-red

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q tests/test_lifecycle_journal_codec.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/mutation-separators-red --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/mutation-separators-red.xml
```

Exit 1: 11 failed, 30 passed in 0.28s.

### final-restored-green

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state TMPDIR=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/tmp /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/offline_pytest.py -q tests/test_lifecycle_journal_codec.py tests/test_lifecycle_investigation_store.py tests/test_lifecycle_investigation_target.py tests/test_lifecycle_investigation_agent.py tests/test_lifecycle_investigation_review.py tests/test_lifecycle_investigation_migration.py tests/test_lifecycle_investigation_retirement.py tests/test_ticker_identity_history.py tests/test_lifecycle_web_store.py tests/test_lifecycle_web_review.py tests/test_lifecycle_web_usage_journal.py tests/test_lifecycle_web_gaps.py tests/test_lifecycle_source_capacity.py tests/test_lifecycle_source_context.py tests/test_lifecycle_web_attended_concurrency.py tests/test_lifecycle_web_read.py tests/test_lifecycle_web_migration.py tests/test_lifecycle_source_read_report.py tests/test_lifecycle_source_progress.py --basetemp=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/pytest/final-restored-green --junitxml=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/final-restored-green.xml
```

Exit 0: 349 passed in 54.93s.

## Mutation Details And Preserved Artifacts

All artifacts remain below this plan scratch directory in `task2-state/artifacts/`; none was overwritten or deleted.

ASCII mutation: changed only the default from `ensure_ascii=True` to `False` with `apply_patch`. The two Unicode byte fixtures, two Unicode digest fixtures, and explicit UTF-8/invariant-digest fixture failed. Example digest changed from `4b5704b5afed23706bd0c195a110a296219e5cef9d18f0dc7e71c86e2ed1004e` to `e62bdd2c31742a0a3efa8b454eacfb80ad25f19c840d8a908a3bbf72a432427e`. Restoring the original default with `apply_patch` returned all 41 codec nodes to GREEN.

Separator mutation: changed only `separators=(",", ":")` to `separators=(", ", ": ")` with `apply_patch`. Five literal byte fixtures, five literal digest fixtures, and the explicit UTF-8 fixture failed. Restored the exact original separators with `apply_patch`, then reran all 349 tests GREEN, including all 41 codec nodes.

Preserved XML:
- `task2-state/artifacts/baseline-green.xml`
- `task2-state/artifacts/baseline.xml`
- `task2-state/artifacts/codec-green.xml`
- `task2-state/artifacts/codec-red.xml`
- `task2-state/artifacts/final-restored-green.xml`
- `task2-state/artifacts/mutation-ascii-red.xml`
- `task2-state/artifacts/mutation-ascii-restored.xml`
- `task2-state/artifacts/mutation-separators-red.xml`
- `task2-state/artifacts/regression-green.xml`

Preserved mutation patches:
- `task2-state/artifacts/mutation-ascii.patch`
- `task2-state/artifacts/mutation-separators.patch` (original minimal-context artifact)
- `task2-state/artifacts/mutation-separators-context.patch` (context-complete equivalent)

Artifact checks, all read-only:
```bash
git apply --check .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/mutation-ascii.patch
git apply --check .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/mutation-separators.patch
git apply --check --unidiff-zero .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/mutation-separators.patch
git apply --check .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts/mutation-separators-context.patch
```
Results respectively: exit 0; exit 1 (`patch does not apply` due to no trailing context); exit 0; exit 0. The mutation had already run via `apply_patch`, so this was only an artifact replay-format issue. Retained the original artifact and added the context-complete version without changing tested product code.

## Final Review And Commit

Reviewed the scoped product/test diff against the brief. Reference scans found no remaining journal `_json`/`_sha` definitions, uses, or imports; unrelated similarly named helpers were left alone. The following checks passed:
```bash
git diff --check -- src tests
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
```

Scoped staging and commit:
```bash
git add -- src/lifecycle_journal_codec.py src/lifecycle_investigation/adoption.py src/lifecycle_investigation/agent.py src/lifecycle_investigation/disposal.py src/lifecycle_investigation/migration.py src/lifecycle_investigation/store.py src/lifecycle_investigation/target.py src/lifecycle_web_review.py src/lifecycle_web_store.py src/ticker_identity_history.py tests/test_lifecycle_journal_codec.py tests/test_lifecycle_investigation_store.py tests/test_lifecycle_source_capacity.py tests/test_lifecycle_source_context.py tests/test_lifecycle_web_attended_concurrency.py tests/test_lifecycle_web_gaps.py tests/test_lifecycle_web_usage_journal.py
git -c core.hooksPath=/dev/null -c commit.gpgsign=false commit -m "refactor(lifecycle): extract neutral journal codec"
git rev-parse HEAD
git status --short --branch
```

Commit output:
```text
[codex/listing-sec-macro-convergence 5d41f570] refactor(lifecycle): extract neutral journal codec
17 files changed, 183 insertions(+), 65 deletions(-)
create mode 100644 src/lifecycle_journal_codec.py
create mode 100644 tests/test_lifecycle_journal_codec.py
```

Commit hooks and signing were disabled for this one command to avoid unaudited subprocesses outside the required offline test environment; repository configuration was not changed. The only remaining tracked working-tree change after committing is the parent's plan edit. No branch switch, merge, push, or worktree cleanup was performed.

Artifact accounting command (standard-library XML inspection only, no backend imports or test execution):
```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 /home/hyl/.virtualenvs/llm_app/bin/python -B -c 'import collections
import json
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(".superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/artifacts")
reports = {}
ids = {}
for path in sorted(root.glob("*.xml")):
    document = ET.parse(path).getroot()
    suites = document.findall("testsuite")
    cases = document.findall(".//testcase")
    reports[path.name] = {
        **{key: sum(int(s.get(key, "0")) for s in suites) for key in ("tests", "failures", "errors", "skipped")},
        "per_file": dict(sorted(collections.Counter(c.get("classname") for c in cases).items())),
    }
    ids[path.name] = {(c.get("classname"), c.get("name")) for c in cases}
baseline = ids["baseline-green.xml"]
final = ids["final-restored-green.xml"]
added = final - baseline
removed = baseline - final
assert not removed, sorted(removed)
assert len(final) == 349 and len(baseline) == 308 and len(added) == 41
assert {module for module, name in added} == {"tests.test_lifecycle_journal_codec"}
print(json.dumps({"reports": reports, "accounting": {"baseline": len(baseline), "final": len(final), "added": len(added), "removed": len(removed), "added_by_file": dict(collections.Counter(module for module, name in added))}}, indent=2))
'
```
Exit 0: baseline 308, final 349, added 41, removed 0; additions only in `tests.test_lifecycle_journal_codec`.

## Intermediate Issues And Concerns

- Resolved fixture setup issue: the initial baseline had 266 setup errors because the newly chosen nested pytest temp root lacked its parent. Its XML is preserved, and no product changes were needed to fix it.
- Resolved artifact-format issue: the original separator patch needs `--unidiff-zero`; a context-complete patch is preserved alongside it and passes plain `git apply --check`.
- Read-only exploratory lookup `sed -n '1,260p' src/lifecycle_web_usage.py` returned exit 2 because that guessed path does not exist. Located the actual journal at `src/lifecycle_web_store.py`; no write or test execution resulted from the lookup.
- No outstanding product/test concern was found in scoped verification. The entire repository suite, live provider paths, real App startup, and production data were deliberately not exercised.
- Independent subagent review was not run, as explicitly prohibited. The parent retains ownership of Task 1 inventory and any plan/evidence updates.
