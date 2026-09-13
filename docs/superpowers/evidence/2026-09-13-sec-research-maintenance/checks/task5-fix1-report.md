# Task5 Fix Round 1 Report

Status: R1 and R2 implemented and verified; ready for independent review.
R3 is explicitly deferred as nonblocking, pre-existing test-output noise.

- FIX_BASE: `1e3c2bfb`; source baseline: `1704ffc4`.
- Branch/workspace: `codex/sec-research-integration`, `/tmp/arkscope-research-output-boundary`.
- Product/test commit: `4dfa0d37` (`fix(sec-research): terminalize closed admission failures and validate member types`).
- Review input: `task5-review-1.md`, R1/R2, with R3 considered only for scope/deferral.
- Sole product/test writer; no subagents, reviewer processes, other worktrees,
  real providers/network/credentials/stores, install, activation, app lifecycle,
  merge or push. Only disposable offline fixtures were exercised.
- This report and all run receipts remain in ignored scratch. No scratch file was
  force-added or staged. Controller owns durable evidence archival and next review.

## R1: Closed Admission Failures

Confirmed the actual operation API and its underlying failure paths before edits:

| Exact Code | Existing Owner / Underlying API |
| --- | --- |
| `sec_research_operation_busy` | `research_operation`: shared-to-exclusive upgrade or nonblocking `fcntl.flock` contention |
| `capture_platform_unsupported` | `research_operation`: `_supported()` is false |
| `capture_path_unsafe` | Root validation / no-follow directory and file admission; `_io_failure` maps ELOOP, ENOTDIR, ENOENT |
| `sec_research_operation_invalid` | `research_operation`: `exclusive` or `create` is not a bool |
| `storage_space_insufficient` | `_io_failure`: ENOSPC from protected lease I/O |
| `capture_store_write_failed` | `_io_failure`: other protected lease OSError, including the ENOLCK fixture |

No operation primitive, path authority or scheduler lock was changed. The new
`classify_sec_research_admission_failure(error)` in `src/research_errors.py`
recognizes only exact `ValueError` instances with one string argument matching
these six codes. It returns a fixed, truthful `ResearchFailure`, or `None` for an
unknown shape/code. Public/durable error validation admits these same exact codes.
Unknown ValueError prose and a RuntimeError containing a recognized code are not
normalized, broadly caught, or mistaken for closed operation failures.

`execute_research_run` and the legacy SSE generator call this classifier only in
their pre-execution lease-admission handler. They retain their existing protected
execution scope after successful admission. No unsupported-platform or other
failure takes an unlocked fallback.

Managed closed failures reuse the existing reference-free atomic
`ResearchRunStore.fail_queued_run_handoff` API. A queued run commits `failed`
status, exactly one error event and one linked assistant error message, with its
actual admission code. No started time, personalization, token usage or tool
references are fabricated. This path does not acquire the unavailable SEC lease
or change the guarded result-bearing terminalization APIs. The actual scheduled
executor also completes and removes its task-registry entry.

Legacy closed failures yield one truthful error SSE with the same code and normal
final HTTP body completion. They admit no new user turn and invoke no provider
factory. ASGI 2.3 and 2.4 owners are both covered, without an app server/lifecycle.
English and Traditional Chinese UI presentations preserve the five new non-busy
codes and do not describe unsupported protection as maintenance or provider work.

The new actual-path regression module has 28 cases: five non-busy failures and
two unknown-exception controls, each through direct, scheduled, SSE 2.3 and SSE
2.4 execution. Faults exercise `_supported() == False`, a real root symlink,
delegation to `research_operation(create="invalid")`, and syscall-level
`fcntl.flock` fault injection for ENOSPC/ENOLCK and unknown exception controls.
The syscall fixtures exercise actual lease exception translation and fd cleanup;
they are not fake admission context managers returning the desired error code.
After removing the injected fault, a different owner can acquire exclusive
protection, and no missing capture root remains created. The no-tool provider
factory is instrumented at invocation, not only iterator advancement.

## R2: Closed Member Types

`_members` now retains each no-follow stat result's `stat.S_IFMT` type, rather
than discarding types into a name set. `_expected` declares the database,
manifest and every registered object as `stat.S_IFREG`; the capture root,
objects and staging entries must be `stat.S_IFDIR`. Private verification uses
a regular `.incomplete` marker in place of the final regular manifest.

The actual/expected maps must match before content/SQLite verification and before
restore destination creation. Empty inventories no longer bypass directory
validation. Existing rejection of symlinks, special files, unknown members,
corrupt data and invalid closure is unchanged.

Three regression cases start from a valid empty export: independently replace
objects or staging with a regular file, or retain the valid layout. Both mutated
bundles fail with `sec_research_bundle_members_invalid` before the destination
exists. The valid empty bundle still restores and reopens its empty object table
through Store. Every case checks that source member types/digests remain unchanged.

## RED And Inverse Evidence

All new behavioral assertions were run before product edits. Static review had
not run any tests; these are this worker's actual reproductions.

| Receipt | Exact Output / Interpretation |
| --- | --- |
| `task5-fix1-red-01` | `22 failed, 9 passed in 3.70s`: 20 known non-busy admission failures and 2 malformed empty bundles failed assertions; 8 unknown-exception controls and valid empty restore passed |
| `task5-fix1-ui-red-01` | `5 failed, 8 passed`, 366ms: the five non-busy public codes were incorrectly presented as provider failures |
| `task5-fix1-green-01` | `629 passed in 69.10s (0:01:09)` |
| `task5-fix1-inverse-admission-01` | `8 failed, 20 deselected in 2.64s`: temporarily made the classifier busy-only; unsupported/unsafe actual direct, scheduled and both SSE owners killed it by assertion |
| `task5-fix1-inverse-members-01` | `2 failed, 1 passed in 2.56s`: temporarily compared only member-name sets; objects-file and staging-file owners killed it, valid empty restore remained passing |
| `task5-fix1-ui-green-01` | `104 passed`, 3 files, 406ms |
| `task5-fix1-typecheck-01` | `tsc --noEmit`, exit 0, runner 11.474s |
| `task5-fix1-checkpoint-01` | `629 passed in 69.11s (0:01:09)`, exit 0, final frozen source after both restorations |

RED/inverse failures are assertions, not collection/test errors. Existing busy,
available, publication, cancellation and output-lifetime expectations were not
relaxed. No test result is attributed to runner interference.

Inverse hashes, individually verified after restoration and before further runs:

| File | Original And Restored SHA256 | Mutant SHA256 |
| --- | --- | --- |
| `src/research_errors.py` | `5a4f996a46b44714f13043bd9a83a5399efb65c3e691420190fc22f0360ef8db` | `38f5bad6687d73543cd74fe29f40851a45d4ef2d5e3cb1e2396527c0bb6755ca` |
| `src/sec_research/operations.py` | `660c8cf3aa9adb58553ea4ca970b05b7159982158b9e8aecd7f3c5052c642d0d` | `fc353e7e7128667795ae32ed58c62279cafde792cedd3be4bb404f7b5e590487` |

## Exact Commands

All checks used the existing hash-verified own-plan runner, with create-only new
`task5-fix1-*` names. No ordinary pytest or controller full release runner ran.
Each receipt directory contains complete `command.json` argv/environment and
`output.log`; backend receipts also contain `results.xml`.

Runner SHA256 values:

```text
run_checks.py    2c1cc48b15f817b02cc70a99cad757a0962e875e37381fa122fca8b89796247f
offline_pytest.py 4c74153e1ef86c35f7bbc923586de624c0ffe3f577c2853e6e4c0a78426c95ff
```

Final backend command (the first GREEN used the same selection):

```sh
/home/hyl/.virtualenvs/llm_app/bin/python -B \
  .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py \
  task5-fix1-checkpoint-01 backend -q \
  tests/test_sec_research_operation_admission.py \
  tests/test_sec_research_operations.py \
  tests/test_research_runs.py tests/test_research_threads.py \
  tests/test_research_output_events.py tests/test_research_output_lifetimes.py \
  tests/test_sec_research_trace.py tests/test_sec_research_capture_lock.py \
  tests/test_sqlite_backup.py
```

Other exact runner tails after the same Python/script prefix:

```text
task5-fix1-red-01 backend -q tests/test_sec_research_operation_admission.py tests/test_sec_research_operations.py::test_empty_restore_requires_directory_members_before_destination
task5-fix1-ui-red-01 frontend test -- src/researchErrors.test.tsx
task5-fix1-inverse-admission-01 backend -q tests/test_sec_research_operation_admission.py -k 'unsupported or unsafe'
task5-fix1-inverse-members-01 backend -q tests/test_sec_research_operations.py::test_empty_restore_requires_directory_members_before_destination
task5-fix1-ui-green-01 frontend test -- src/researchErrors.test.tsx src/researchReducer.test.ts src/i18n/researchPresentation.test.ts
task5-fix1-typecheck-01 frontend run typecheck
```

Every runner exited before edits, restoration or the next runner. Source was
frozen for each run. Receipt timestamps confirm all eight fix-round runs were
sequential with zero overlaps; creation of each output.log follows completion of
the previous command.json. UTC ordering on 2026-09-13:

```text
red-01                09:54:28.867 -> 09:54:33.405  session 40324
ui-red-01             09:55:36.652 -> 09:55:37.383  completed in initial exec
green-01              09:57:10.163 -> 09:58:20.872  session 23624
inverse-admission-01  09:58:51.197 -> 09:58:54.660  session 40931
inverse-members-01    09:59:14.928 -> 09:59:18.303  session 37323
ui-green-01           10:00:20.514 -> 10:00:21.275  completed in initial exec
typecheck-01          10:00:49.005 -> 10:01:00.479  session 27642
checkpoint-01         10:01:26.579 -> 10:02:37.065  session 86736
```

All listed sessions are closed. Active runner IDs at handoff: none.

## Changed Files

Only these product/test paths are in `4dfa0d37`, relative to FIX_BASE:

```text
apps/arkscope-web/src/i18n/resources/en/research.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/research.ts
apps/arkscope-web/src/researchErrors.test.tsx
apps/arkscope-web/src/researchErrors.ts
src/api/routes/query.py
src/research_errors.py
src/research_run_manager.py
src/sec_research/operations.py
tests/test_sec_research_operation_admission.py
tests/test_sec_research_operations.py
```

## Limits And Deferral

- R3 remains nonblocking: the shared initializer selects i18next debug through
  `import.meta.env.DEV`; routine initialization/language logging remains in the
  isolated test receipts. No product logging change, warning suppression or
  failure suppression was made merely to silence it. The 104-pass result and
  typecheck receipt are valid, not represented as pristine output.
- Unknown programming exceptions deliberately propagate rather than being
  mislabeled as closed admission failures. Known failures still require a
  writable Research database to persist their reference-free terminal state;
  existing reconciliation is unchanged for storage/process failures.
- Lease owner identity, operation-to-writer/SQLite lock order and complete
  result-to-durable-commit protection remain unchanged. No shared mutable Context
  reuse or unlocked fallback was introduced, and no scheduler lock was added.
- Source-platform limits remain: POSIX/no-follow locking and supported atomic
  no-replace bundle publication are required; unsupported protection is now
  reported truthfully at Research admission, not bypassed or labeled busy.
  Trusted lock-namespace/cooperating-writer assumptions remain in force.
- This is focused fix verification, not a full release gate or actual-store
  rollout. No Task6 source, preflight, destructive maintenance or deployment
  direction was changed. Controller owns next review and release verification.

No further product changes or runners will start after this report handoff.
