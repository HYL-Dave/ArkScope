# SEC Structured Source Core And Cleanup Follow-Up

Date: 2026-09-11. Base: `95ad149ea4bda2569030f1dfc95f93bf3c279738`.
Worktree: `/tmp/arkscope-listing-sec-macro-convergence`.
Status: scoped implementation and independent reviews passed. Fresh complete
backend verification: **8,292 passed / 12 unchanged skips**, 1,108.57 seconds.
Exactly 8,304 collected and executed cases; no failures, errors or source drift.

| Local commit | Scope |
| --- | --- |
| `96990ef5` | RED-first plan and explicit completion boundary |
| `755cba8d` | Executable SQLite diagnostic and observed evidence |
| `41ab878e` | Unused OpenAI synchronous entrypoint removal |
| `82512b8b` | Exact source decoder and submissions catalog |
| `dd93bcf8` | Exact immutable Company Facts observations |

This batch does not complete the full cleanup audit or the SEC research workflow.
No provider request, production-store/config/token read or write, installation,
runtime upgrade, App restart, merge or push occurred. Synthetic fixtures do not
establish actual SEC coverage or actual database health.

## Implemented Scope

- Preserve the exact five-case SQLite UPSERT diagnostic as an executable with
  only in-memory connections. All three duplicate-conflict cases reproduce the
  index mismatch under the explicit SQLite 3.37.2 interpreter; both single-clause
  controls pass. The script classifies behavior, not versions. A failed control
  or unknown result is inconclusive, never evidence that an upgrade succeeded.
- Close cleanup C08: remove the unused OpenAI synchronous entrypoint and export.
  Current async/streaming Research, Anthropic's live synchronous entrypoint,
  authorization, model selection and transport behavior remain unchanged. The
  16 retained functions/classes have identical ASTs against the base.
- Add pure original-byte SEC JSON decoding with exact Decimal/integer values,
  explicit CIK identity, typed malformed-source errors and lossless source
  pointers. No binary-float round trip or implicit identity lookup is allowed.
- Parse recent and historical submissions without guessing report dates or XML
  filenames. Keep amendments, original-byte hashes and actual document URLs.
  Missing historical-file metadata differs from observed empty metadata; neither
  a partial source nor a historical pointer claims whole-history coverage.
- Preserve every Company Facts observation with exact decimal text, units,
  periods, filing identity, amendments and an original-source pointer. Do not
  turn YTD into a standalone quarter, select a latest value, merge contradictions
  or substitute a currency. Invalid rows reject the snapshot before publication.

The new catalog/facts modules are intentionally not yet registered in tools or
schedules. The existing tool and all four Research transports remain unchanged
until the complete three-tool replacement can be integrated atomically.

## Review Follow-Ups

The [executable diagnostic](sqlite_upsert_repro.py),
[actual result](sqlite-upsert-result.json) and
[dated implementation report](review-followups.md) are additive to the previous
sealed SQLite research. The source SQL had already been archived; this batch
makes that exact matrix directly runnable for later runtime comparison.

```bash
env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B \
  docs/superpowers/evidence/2026-09-11-sec-structured-source-core/sqlite_upsert_repro.py
```

Exit 0 is all controls/cases passing, 1 is the exact defect reproduced with
passing controls, and 2 is inconclusive. This run returned **1**: table/index
counts 2/3 in three cases, 2/2 in two controls. `quick_check` returned `ok` even
in the defect cases; full `integrity_check` found the index mismatch. All five
cases use a memory journal, so this defect is not WAL-dependent. No running-App
interpreter or production database is identified or checked by the script.

The implementation worktree has no `src/audit/` directory. Main at `30bb31c7`
still tracks four old audit files because this branch has not been merged.
Deleting that main directory as if it were disposable bytecode would be wrong;
no such deletion occurred.

The current unknown-event-date plus explicit attended execution-date policy was
already recorded in the September 8 completion plan. Its limitation/blocker,
date-selection and provider-veto owners remain unchanged and were exercised.
There is no lifecycle policy change in this batch.

## Verification

The full-backend command exited 0. All **783 source/test paths** and the exact
patch against the base match their pre-run signatures, which also match the
independent review. The patch SHA256 is
`5b17c54189dd8d7fd908a3db8ac54ae990d0ddad18ea2396c7812d109c75bfdd`.
The [verification summary](verification-summary.json) records exact collection,
execution, added/removed and unchanged skipped IDs; partial or focused runs are
not substituted for the complete gate.

| Scope | Removed IDs | Added IDs | Net |
| --- | ---: | ---: | ---: |
| Unused OpenAI sync entrypoint | 5 | 3 | -2 |
| SEC exact source decoding | 0 | 58 | +58 |
| SEC catalog | 0 | 66 | +66 |
| SEC Company Facts | 0 | 54 | +54 |
| Total: 8,128 -> 8,304 collected | 5 | 181 | +176 |

The five removals are sync-only parameter nodes in runtime binding tests; the
retained 136 runtime-binding and 86 legacy-surface assertions are unchanged.
No live async/stream/Anthropic binding owner was deleted. The full-run's 12 skips
are exactly the same named live-data tests as the prior baseline.

| Scope | Assertion RED | GREEN / controls | Inverse evidence |
| --- | --- | --- | --- |
| SQLite diagnostic | Six tests fail before implementation | Six diagnostic tests pass; worker, parent and reviewer repeat actual matrix | Synthetic classifier/CLI controls reject false success and inconclusive masking |
| OpenAI sync removal | 2 failed / 280 passed | 447 passed; restored absence scope 3 passed | Restored function/export: 2 failed / 1 passed |
| SEC common/catalog | 2 assertion failures | 120 passed initially; 124 after presence-bit follow-up | Float/date/alignment mutants killed; four isolated follow-up mutants killed |
| Historical-file observation bit | 4 assertion failures | Included in final 124 | Always-observed mutation: 1 failed / 3 passed |
| SEC facts | 1 runtime-owner assertion failure | 54 passed | Float round trip: 4 failed; concept overwrite: 2 failed |
| Combined new/existing SEC owners | Not a new RED cycle | 332 passed | Includes existing config/path/tool/transport/identity controls |
| Parent parser precommit check | Not a new RED cycle | 178 passed | Sources unchanged from reviewed snapshot |
| Independent Task 1/2 review | Both scopes PASS | 459 passed plus six diagnostic tests | Retained assertions and ASTs independently checked |
| Independent Task 3/4/integration review | All scopes PASS | 181 focused + 54 synthetic passed | Exact reviewed source patch unchanged |

The initial facts selection before module creation produced 53 setup errors,
not a valid RED. A separate runtime-owner assertion was then demonstrated before
implementation. The first broad Task 2 GREEN command named a nonexistent test
file and exited 4; it is not acceptance evidence. The corrected command's 447
passes and the subsequent independent/full runs are the valid controls.

Worker reports preserve their original checkpoint wording, including then-pending
reviews or restored reruns. The independent reviews and final summary supersede
those status statements; they do not rewrite the earlier observations.

The full run uses the preceding reviewed offline runner, an empty inherited
environment, isolated fixture stores/HOME and the reviewed Node PATH. Its audit
hooks reject production data and external network access in that test process;
this is a test harness, not an OS sandbox. No frontend source changed, and no
frontend build or browser hand-test result is claimed by this batch.

Actual full command, from the worktree with `login=false`:

```bash
env -i \
  PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-sec-structured-source-core/final-full \
  /home/hyl/.virtualenvs/llm_app/bin/python -B \
  .superpowers/sdd/2026-09-11-sec-structured-source-core/offline_pytest.py -q tests \
  --junitxml=.superpowers/sdd/2026-09-11-sec-structured-source-core/backend-full.xml \
  > .superpowers/sdd/2026-09-11-sec-structured-source-core/backend-full.log
```

For a fresh reproduction, restore the archived runner/verification helpers to
this plan's scratch layout and use a new fixture-workspace name. They are exact
execution records with scratch-relative paths, not installed application tools.
The standalone SQLite diagnostic above does not depend on that scratch layout.

The [artifact manifest](artifact-manifest.json) binds 54 archived reports, XML,
console logs, census and source/collection snapshots. Generated artifacts were
copied create-only and their decompressed/original bytes were compared on readback.
The six-test SQLite diagnostic control run is separate from the backend count.
Raw inverse-test XML and console logs retain pytest-rendered whitespace;
unscoped `git diff --check` reports those evidence bytes, not source defects.
Source, tests and documentation pass the scoped whitespace check excluding raw
XML/log artifacts. Logs are
explicitly tracked despite the repository's general log-ignore rule, and every
manifest entry is verified against both disk and the staged Git blob.

## Census And Remaining Work

The scan against the immediately preceding frozen census reports **1,100 files
read, 4,311 candidates and 3,352 uncertainties**. Its raw exit remains
**2 / review_required**. The only new candidates are test-only
`src.sec_research.catalog` and `src.sec_research.facts`; there are no new
uncertainties, coverage reductions, dependency changes or untracked-name changes.
The existing config/paths modules remain intentionally awaiting service wiring.
Candidate counts are not a count of bugs or an approved deletion list.
The staged-document recheck in `census-final.json.gz` preserves exactly the same
read-source manifest and comparison. Its additional excluded-document manifest
entries are not a new runtime/source candidate. The raw exit remains 2.

Still unfinished:

- Canonical SEC storage and shape checks, quota reservations/deduplication and
  recovery under the approved adjustable 100 GiB budget.
- Governed acquisition, historical traversal/coverage, as-of financial queries,
  safe pagination and on-demand documents/citations under the approved limits.
- The atomic three-tool replacement, four Research transports, deep researcher,
  retained Research citations, portable export, scheduling and Settings.
- C03/C10's old catalog/backend boundaries, C09's provider/CLI cluster,
  C11/C12's actual news routing/projection dependencies, existing CSS/SQL scan
  issues and separately scoped actual-store disposition.
- App-local Python/SQLite upgrade verification and cross-platform packaging.
  This diagnostic does not replace that work or repair existing data.

No retired shell is added to postpone these decisions. Equally, live tools,
stored research/market data and membership intent are not deletion candidates
merely because their surrounding subsystem has historical names.
