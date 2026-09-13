# Task6 Publication-Recovery Follow-up Report

## Status and Commit

- DONE within `task6-publication-brief.md`; ready for controller-owned read-only review.
- Worktree: `/tmp/arkscope-research-output-boundary`; branch: `codex/sec-research-integration`.
- BASE: `c457480014a12f965c9521276705bad532827744`.
- Commit: `d2f491c130f10c738b2158e76e3e536df207e927` (`fix(sec-research): recover interrupted publication aliases`).
- Restored frozen covering: `task6-publication-covering-frozen-01`, exit 0, **1092 passed**, 115.209s runner / 114.22s pytest.
- Seven implementer runner invocations completed, four nonzero retained, none aborted or unfinished. One nonzero was a test-hook admission failure, explicitly distinguished below.
- No active runner. Final process check found no `run_checks.py`, `offline_pytest.py`, or publication-inverse driver. Product/index worktree clean after commit; this report and inverse artifacts remain ignored.

## Exact Scope

Five committed files, 430 insertions, no deletions or migrated owners:

| File | Change |
| --- | --- |
| `src/sec_research/captures.py` | Invoke publication-alias recovery after the existing accounting transaction has committed and released the market writer lock. |
| `src/sec_research/capture_lock.py` | Two local helpers group accounted metadata by inode and verify a canonical two-link object/stage pair before removing only its redundant stage name. |
| `tests/test_sec_research_captures.py` | Actual put interruption helper, registered-read retention, commit/unlink/fsync faults and retry, live/dead published worker. |
| `tests/test_sec_research_capture_lock.py` | Foreign/extra aliases, canonical names, body digest, different-inode retention, no-follow/nonregular replacement, first-identity retention, and post-hash replacement guards. |
| `tests/test_sec_research_maintenance.py` | Both publication windows through approved cleanup of target plus unrelated orphan, and real unrelated market-write/capture-exclusion barriers. |

The helper admits exactly two locally inventoried names, canonical `objects/<64 lowercase hex>` and `staging/<32 lowercase hex>`, sharing device/inode/size with `st_nlink == 2`. Both descriptors must be regular files. It streams SHA-256 in 1 MiB chunks, retains the first validated metadata identity, and compares both open descriptors and no-follow path entries against that identity after hashing. Root/child identities are checked at entry and again before unlink. Only the stage name is unlinked; its parent is fsynced before success. Descriptors close on every exit.

The existing `inspect_owned`/`inventory` single-link rule, root/writer lease contracts, accounting transaction, schema/CLI/reference protections, and registered object reads were not relaxed. Accounting precedes alias removal even if removal later fails. Scan/hash/unlink/fsync remain outside the shared market writer lock, under the existing capture writer and root operation leases. No new trigger, CLI argument, phase enum, migration, automatic object/standalone-stage pruning, reset fallback, or repair framework was added. Existing `recover`, `preflight`, and `put` recovery call sites use the fix.

## RED / GREEN / Inverse Receipts

Every named folder below retains `command.json`, `output.log`, and `results.xml` in this plan workspace. Commands, failures, and intermediate runs were not overwritten. The controller's earlier `task6-publication-baseline-01` (178P) and `task6-publication-probe-01` (1F/1P) remain separate controller evidence, not counted as implementer runs.

| Exact runner name | Exit | Result | Runner seconds | Meaning |
| --- | --- | --- | --- | --- |
| `task6-publication-red-01` | 1 | 20F / 3P / 89 deselected | 1.757 | Before any product edit: aliases remained, validation did not reject, new I/O barriers were unreachable. The 3 controls retained stage-only/separate-inode behavior and destination no-replacement. |
| `task6-publication-green-01` | 0 | 23P / 89 deselected | 1.764 | Initial integrated helper passed the initial owners. |
| `task6-publication-identity-red-01` | 1 | 1F / 3P | 0.685 | Retained test-hook failure, NOT intended product RED: wrapping `os.open` removed it from `os.supports_dir_fd`, so platform admission stopped before the injected race. |
| `task6-publication-identity-red-02` | 1 | 1F / 3P | 0.688 | Same new race owner with truthful descriptor-support metadata for its delegating wrapper. Intended `DID NOT RAISE`: a foreign link added after the stage stat became the helper's freshly sampled baseline. The 3 pre-scan replacement controls passed. |
| `task6-publication-green-02` | 0 | 27P / 89 deselected | 1.919 | First validated identity retained instead of resampled; all expanded publication owners pass. |
| `task6-publication-inverse-omit-alias-01` | 1 | 2F / 2P | 1.036 | Omitted only the new recovery call. Both before-register owners fail; both stage-only controls pass. Wrapper exited 0 after checking intended assertions and exact restoration. |
| `task6-publication-covering-frozen-01` | 0 | 1092P | 115.209 | One restored covering run: complete changed suites, adjacent controls and unchanged controller probe. No full backend/frontend run. |

Self-review motivated the second RED cycle, not a rerun of the initial failing run: metadata must not be refreshed after the first valid two-link observation. No product change followed the test-hook failure until the corrected owner demonstrated the actual race. The three pre-scan replacement controls were already GREEN and required no additional product behavior. One unused test import was removed before the inverse/freeze; no product or test changes occurred after restoration or during covering.

### Exact Test Commands

All commands ran from `/tmp/arkscope-research-output-boundary`. Only the existing isolated runner launched pytest; no agents, provider calls, production stores/configuration, installation, restart, merge, push, or other-worktree changes were performed.

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task6-publication-red-01 backend -q tests/test_sec_research_captures.py tests/test_sec_research_capture_lock.py tests/test_sec_research_maintenance.py -k publication
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task6-publication-green-01 backend -q tests/test_sec_research_captures.py tests/test_sec_research_capture_lock.py tests/test_sec_research_maintenance.py -k publication
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task6-publication-identity-red-01 backend -q tests/test_sec_research_capture_lock.py::test_publication_recovery_does_not_refresh_identity_to_accept_new_foreign_link tests/test_sec_research_capture_lock.py::test_publication_recovery_binds_unlink_to_accounted_entry
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task6-publication-identity-red-02 backend -q tests/test_sec_research_capture_lock.py::test_publication_recovery_does_not_refresh_identity_to_accept_new_foreign_link tests/test_sec_research_capture_lock.py::test_publication_recovery_binds_unlink_to_accounted_entry
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task6-publication-green-02 backend -q tests/test_sec_research_captures.py tests/test_sec_research_capture_lock.py tests/test_sec_research_maintenance.py -k publication
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/task6-publication-inverse.py task6-publication-inverse-omit-alias-01
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task6-publication-covering-frozen-01 backend -q tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py tests/test_sec_research_operations.py tests/test_sec_research_capture_lock.py tests/test_sec_research_captures.py tests/test_sec_research_operation_admission.py tests/test_sec_research_references.py tests/test_sec_research_citations.py tests/test_sec_research_store.py tests/test_sec_research_service.py tests/test_sec_research_tool_service.py tests/test_sec_research_issuers.py tests/test_sec_research_document_store.py tests/test_sec_research_document_service.py tests/test_sec_research_document_queries.py tests/test_sec_research_queries.py tests/test_sec_research_fact_queries.py tests/test_research_threads.py tests/test_research_runs.py tests/test_research_history.py tests/test_sqlite_backup.py .superpowers/sdd/2026-09-12-sec-research-release-integration/task6-publication-probe.py
```

The inverse driver invoked this exact runner argv (the absolute helper/probe paths are intentional):

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -B /tmp/arkscope-research-output-boundary/.superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task6-publication-inverse-omit-alias-01 backend -q tests/test_sec_research_maintenance.py::test_publication_recovery_reaches_explicit_cleanup_with_unrelated_orphan /tmp/arkscope-research-output-boundary/.superpowers/sdd/2026-09-12-sec-research-release-integration/task6-publication-probe.py
```

## Durable Failure States and Recovery

These are observed fixture states, not new public API phase names. Each body is the actual 11-byte `publication` fixture unless noted.

| Injected boundary | Last observed durable state | Concrete recovery demonstrated |
| --- | --- | --- |
| Before publish | Staged body/file and staging parent synced; reservation 11; no object name. | `recover()` converts reservation to orphan 11 without unlinking the standalone stage. Repeated recovery retains it; fresh preview and explicit approved cleanup delete it plus the unrelated 16-byte orphan, charge 27 -> 0. |
| Before register | Object/stage names point to the same synced inode, nlink 2; reservation 11. Strict preview is blocked before recovery. | Recovery commits orphan 11/reservation 0, verifies and removes the stage alias, fsyncs staging, leaves object nlink 1 and charge 11. Repeated recovery is stable. Preview includes this object AND the unrelated orphan; approved cleanup removes both and charge becomes 0. |
| After register, before stage cleanup | Registry commit owns persisted 11; exact object read works; stage alias remains, nlink 2. | Recovery removes only the proven alias, returns persisted 11/orphan 0/reserved 0. Two recoveries preserve the exact registered read. |
| Accounting COMMIT denied | Transaction rolled back; reservation 11 survives; object and stage remain nlink 2. No alias unlink occurs. | Persistent fault keeps returning `capture_store_write_failed` without losing charge. Remove fixture denial and explicitly retry recovery: orphan 11, alias gone, object nlink 1; repeated retry stable. |
| Alias unlink fails | Accounting has committed orphan 11/reservation 0, verified by a separate real read connection inside the fault; both names remain. | Typed `capture_store_write_failed`; repeated failure retains charge. Restore unlink and retry: only stage alias disappears and parent sync completes; charge stays 11 for the object. |
| Post-unlink staging fsync fails | Accounting committed orphan 11; stage is visibly absent and object nlink 1, but alias-directory durability is not acknowledged. | Typed failure; persistent fault also fails the next recovery's namespace sync before accounting can be rewritten. Charge remains 11. Restore fsync and explicitly retry to make the namespace durable; repeated recovery remains 11. |
| Foreign/extra aliases, malformed pair, mismatched body | Accounting remains 11; no unproven name is unlinked. Existing typed path/integrity refusal and strict admin refusal remain. | No forced recovery. Preserve and inspect the files; resolve the external/corrupt fixture condition before a retry. A separate identical-but-independent stage is retained and charged separately (22 total), not deduplicated by content. |
| Entry/body/root replacement during proof | Original charge remains 11. Descriptor/path/root mismatch rejects before unlink; replacement and detached original names remain present. | Quiesce external edits and restore the correct root/entry identity from trusted retained data before retrying. There is deliberately no automatic repair of the replacement. |
| Live published worker | Live lease owner and reservation 11 remain; recovery returns `capture_store_busy`. | Actual child process termination releases the writer lease. Recovery then reaches the normal orphan-11/single-object result; both existing stage-only and new published-worker controls are covered. |

The ordinary-market barriers perform actual different-owner SQLite writes to an unrelated `news` table during object hashing, alias unlink, and staging fsync. At each boundary the different-owner capture writer is still denied. Tests assert retained news rows and final capture/charge state, not merely mock calls.

## Inverse Provenance and Restoration

- New ignored driver: `task6-publication-inverse.py`. It mutates source only through `apply_patch`, invokes the unchanged isolated runner, and restores in `finally`.
- New source directory: `task6-publication-inverse-omit-alias-01-source`.
- Archive additions needed: `task6-publication-inverse.py`, `task6-publication-inverse-omit-alias-01-source/receipt.json`, `captures.py.original`, and `captures.py.mutated` within that source directory. No fixture databases or capture bodies belong in the source archive.
- Only `captures.py` was mutated, by omitting `directory.recover_published_stages(files)`. `capture_lock.py` was protected and hashed unchanged. There was no aborted inverse invocation or unexplained source directory.
- Intended failures: committed owner `test_publication_recovery_reaches_explicit_cleanup_with_unrelated_orphan[before_register]` retains nlink 2; unchanged controller owner `test_interrupted_publication_can_reach_cleanup[before_register]` returns `blocked/capture_path_unsafe` instead of `ready`. Both before-publish controls pass.
- Receipt has `source_restored_exact=true`, `tests_unchanged=true`, `runners_unchanged=true`, original/mutant/restored product hashes, all three test hashes, unchanged probe hash, exact command, failure names/messages, and completed status. Final post-commit hashes were read back and match the restoration receipt.

```text
captures.py original/restored: 4a83188a504333b7ac9f4da516227b77601be985ed21d4c31390a6cf05ad8374
captures.py mutant:           77ebf36e52300cf25f400c8ea72673391e27b1103d414042d597576f8d278921
capture_lock.py unchanged:    aa86897008ba557474665f9023c5aa603e8892cb15c0d81e98fe8351af18f3f9
test_sec_research_captures.py: 9c38c6ad61eb8514fd46a813d96378301effefc1882ccdaae2274dace344aaa5
test_sec_research_capture_lock.py: 42bb39ebf05db4ba0768720a5964e718ab1e8c7009aa3692317fdf41b9e4fa52
test_sec_research_maintenance.py: 09d2a1ee4fd362323f677609c5174661a29dc8872270452dfcedeabf0ee16d85
controller probe unchanged:  9775b0135695a9f0c1eebf8951b900eaab90acc249375a19e9d1b642da627296
run_checks.py unchanged:     2c1cc48b15f817b02cc70a99cad757a0962e875e37381fa122fca8b89796247f
offline_pytest.py unchanged: 4c74153e1ef86c35f7bbc923586de624c0ffe3f577c2853e6e4c0a78426c95ff
```

## Commit / Self-Review / Limits

Verification and commit commands:

```bash
git diff --check
git add src/sec_research/captures.py src/sec_research/capture_lock.py tests/test_sec_research_captures.py tests/test_sec_research_capture_lock.py tests/test_sec_research_maintenance.py
git diff --cached --stat
git -c core.hooksPath=/dev/null commit -m 'fix(sec-research): recover interrupted publication aliases'
git log -1 --format='%H %s'
git status --short --branch
sha256sum src/sec_research/captures.py src/sec_research/capture_lock.py tests/test_sec_research_captures.py tests/test_sec_research_capture_lock.py tests/test_sec_research_maintenance.py
pgrep -af '[/]run_checks.py|[/]offline_pytest.py|[/]task6-publication-inverse.py'
```

`git diff --check` exited 0; only the five allowlisted files were staged. Commit hooks were disabled for that invocation so no unapproved test runner could start outside the isolated gate; no persistent Git configuration changed. Commit succeeded, readback returned the full hash above, status showed only the branch header, and the final process check returned exit 1/no matches (no active runner).

Self-review checked proof inputs, first-identity retention, descriptor cleanup, accounting-before-unlink, post-unlink durability retry, all existing writer recovery call sites, strict admin invariants, and the scoped diff. No unresolved architecture question or unmet brief requirement remains. The change adds 26 parameter-expanded behavioral cases; none of the old owners was removed or weakened.

Remaining limits: verification uses disposable POSIX fixtures and injected failures, not a hardware power-loss test or real-store rollout. Existing no-follow/flock ownership assumptions remain: a noncooperating privileged actor modifying the filesystem between the final identity check and unlink is not made impossible by a new atomic conditional-unlink primitive. Unproven aliases and corrupted/replaced roots are intentionally not automatically repaired. All long work stays outside the market writer lock, but recovery still hashes each candidate body and holds the existing capture writer lease while doing so. Whole-backend verification, independent review, evidence archival, operator documentation, and Task7 remain controller-owned.
