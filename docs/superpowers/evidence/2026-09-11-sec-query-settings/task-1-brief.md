# Task 1: Receipt Bindings And Catalog Pagination

Worktree: /tmp/arkscope-listing-sec-macro-convergence
Plan: docs/superpowers/plans/2026-09-11-sec-query-settings.md (read global constraints
and Task 1; full spec is linked). Implement Task 1 only, RED-first, directly in
this worktree. All manual edits use apply_patch. Do not merge/push or read actual
data, config/.env, credentials; no network/provider calls. No new dependency.

Write scope: src/sec_research/{schema,store,service,queries}.py and
tests/test_sec_research_{store,service,queries}.py. You may add a small focused
query helper module if it removes real duplication; document exact interface for
Task 2. No other product/plan/ledger files. You own tests/implementation and
must preserve all existing tests except necessary receipt shape fixtures.

Key issues: current receipts list completed locators but no snapshot binding;
publish returns snapshot id. Do not let old good snapshots satisfy a newer
unavailable receipt. Bind sources to snapshot identity plus observation time,
validate issuer/kind/historical locator. Queries must reopen pinned receipt id
and bound snapshots, filter before limit, strict cursor query/filter/receipt
binding, no in-memory latest substitution. Purely read-only, no install/network.
Handle duplicate identical filing metadata across recent/history vs conflicts.
No broad shape-migration compatibility. Existing direct record_receipt callers
can be explicitly unbound and must be unavailable to query authority.

Keep AUTOINCREMENT per plan. Prove max rowid exhaustion cannot generate a lower
receipt and shared SQLite sequence for unrelated autoincrement tables untouched.

Offline harness copied from prior sealed evidence:
  .superpowers/sdd/2026-09-11-sec-query-settings/offline_pytest.py
Run with env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1
ARKSCOPE_OFFLINE_TEST_WORKSPACE=<absolute own subdir of this plan scratch>
/home/hyl/.virtualenvs/llm_app/bin/python -B <harness> <test paths> -q
--junitxml=<own evidence filename>. Save full red/green/inverse subprocess
stdout via a tiny subprocess runner only if needed (apply_patch to create it).
Never run ordinary pytest with actual HOME/config.

Before done: tests green, apply inverse mutations in scratch copy or scoped
restore to your own clean files with byte hashes proving restoration; named
owners must fail. Self-review, commit only your explicit files. Write report to
.superpowers/sdd/2026-09-11-sec-query-settings/task-1-report.md including commit,
changed files, exact tests/counts, RED messages, mutation evidence and public
helper signatures for next task. Return brief status plus report path.
