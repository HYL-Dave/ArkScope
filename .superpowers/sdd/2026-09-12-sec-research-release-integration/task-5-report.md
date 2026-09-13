# Task 5 Report

Status: operation/Research protection verified; portable export/restore in progress.
Base: 01ca7c58, branch codex/sec-research-integration, requested existing worktree.
No subagents, other worktrees, provider calls, real stores/config, install,
activation, app lifecycle, merge or push. The full release gate remains controller-owned.

## Checkpoint 1

Commit: operation protection checkpoint (hash recorded in the next checkpoint).
Changes: capture_lock, captures, Store, issuer/tool/service/query/document/citation
owners; Research executor, legacy SSE executor, direct message/event/atomic error
publication; tests/test_sec_research_operations.py. No scheduler lock.

Operation order: operation -> issuer/document -> capture writer -> market write
-> SQLite. POSIX no-follow regular-file lock in the existing trusted root-hashed
namespace. Shared and exclusive acquisitions are nonblocking; busy is the typed
ValueError code sec_research_operation_busy. Missing stored roots are not created.
Thread-local active ownership includes process/thread/async-task identity; neither
child/copied nor stale Context objects convey reentrancy. Upgrade fails closed.
Executor protection precedes tool production and ends after terminal durable
publication, including cancellation. Direct durable reference writers also enter
the lease before their write mutex/SQLite boundary. Each worker has its own
existing copy_context invocation; no shared mutable Context reuse was introduced.

## Exact Verification

Every run uses `/home/hyl/.virtualenvs/llm_app/bin/python -B
.superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py
NAME backend ARGS`. Each create-only NAME directory retains command.json with
the complete executed argv/environment, output.log and results.xml.

Runner SHA256: run_checks.py
2c1cc48b15f817b02cc70a99cad757a0962e875e37381fa122fca8b89796247f;
offline_pytest.py
4c74153e1ef86c35f7bbc923586de624c0ffe3f577c2853e6e4c0a78426c95ff.
Both scratch files match the tracked sealed copies.

- task5-operation-red-01: 7 failed in 0.55s, assertion failures including actual
  maintenance admission after put before metadata publication (no collection errors).
- task5-operation-green-01: 16 failed, 625 passed in 62.16s. Preserved regression
  evidence: 15 document/citation guards initially preceded pure validation; one
  read lease unnecessarily fsynced existing lock directories. Fixed in product,
  no expectation relaxation.
- task5-research-red-01: 3 failed, 7 deselected in 3.12s. Actual executor result,
  event and message boundaries admitted maintenance for success/error/cancel.
- task5-operation-green-02: 756 passed in 86.83s.
- task5-owner-red-01: 3 failed, 10 deselected in 2.68s. Stale copied Context and
  direct message/event publication assertions; no errors.
- task5-owner-green-01: 89 passed in 8.94s.
- task5-terminal-red-01: 1 failed, 3 passed, 11 deselected in 3.19s. Direct atomic
  error-terminal publication admitted maintenance. Legacy SSE protection passed.
- task5-inverse-outer-lease-01: 5 failed, 10 deselected in 3.55s. Skipped outer
  acquisition/executor/SSE leases only; put-to-publish, three Research terminal
  paths and legacy stream all failed by maintenance admission, not errors.
- task5-operation-checkpoint-01: 1119 passed in 105.43s. Tests: operations,
  capture_lock, service, queries, fact_queries, captures, store, document_service,
  document_queries, citations, tool_service, trace (test_sec_research_ prefix),
  test_research_runs.py, test_research_threads.py, test_research_output_events.py.

No concurrent runners. Inverse receipt creation: 2026-09-13 16:50:42.536905947
+0800, checkpoint output creation: 16:51:09.783027683 +0800. Inverse runner exit
was observed before restoration and checkpoint launch; source stayed frozen
during every test run.

Inverse original/restored versus mutated SHA256:

- capture_lock.py: a3c7f88d7f8b26a4562349da662b99c64aed87ff6a626b3855374ba5fc0bbc6c
  / 4b22ba4ed6f4f1de045e62e481227870f96521b4fd55ab5051a6affa40eac42a
- research_run_manager.py: a833700d14b96bed29e7c777c75f4e6f75a77566afe71ba7473cf8a9897d9fe3
  / a5456dd238516e2213a97ad4ea3996ba500a5507554fe0e08cb453da7d2cf302
- api/routes/query.py: 1eb932ffb343d25dd60f88c314472177d23d32d0f4791e7fd9cf6081e63d82ac
  / f495ca550d0de56b682a835a28973dbeb4dbbbac8ac4e428ae99a72727f604dc

## Remaining Work

Portable export/restore, bundle failure/inverse tests and checkpoint 2 follow.
Task6 deletion/reset is not implemented or admitted by this checkpoint. Coordination
assumes the existing trusted lock namespace is not replaced externally. Research
leases conservatively span whole executions, including provider waits; this is
intentional maintenance exclusion, not provider/job serialization.
