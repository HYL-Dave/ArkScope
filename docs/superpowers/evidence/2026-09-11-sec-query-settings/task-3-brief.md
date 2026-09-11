# Task 3: Stored Query And Capacity HTTP Contracts

Worktree /tmp/arkscope-listing-sec-macro-convergence. Read approved plan
docs/superpowers/plans/2026-09-11-sec-query-settings.md global constraints and
Task 3 plus task-1 report for concrete query interfaces. Task 2 is not implemented
yet; its public .facts signature is fixed in the plan. Build independent config,
catalog, validation and thin facts adapter/tests against that signature; report
any remaining facts execution dependency until Task 2 lands, don't invent a
placeholder facts service or weaken its integration tests. Implement only Task 3,
RED-first, no subagents. All edits apply_patch. No production data/config/token
reads or live provider operations, no installs/merge/push. Offline harness only.

Scope src/api/routes/sec_research.py, tests/test_sec_research_routes.py,
tests/test_api.py, tests/test_security_lifecycle_routes.py. Keep the two existing
stored status/explicit refresh contracts. Add four routes: GET/PUT static config
BEFORE generic /{cik}, GET /{cik}/filings, GET /{cik}/facts. All list query operands
repeatable FastAPI query args, dates/bools/limits validated strictly; use existing
StoredQueries, no adapter-side data filtering or duplicate currency/metric code.

GET config exact shape capture_budget_bytes and capacity (null if not installed,
otherwise CaptureStore.status dict). Both config routes use domain typed accessor
over get_profile_store; PUT strictly positive int<=2**53-1, rejects bool/string/
extra fields; require_db_write BEFORE constructing mutation owners. Persist quota
only, no recover/preflight/acquire/schedule/delete. PUT returns saved integer;
UI then GET readback. Bad persisted config explicit503 code, not default100GiB.
Unknown capacity for unavailable/mismatched store must not be falsely reported
as zero; preserve typed unavailable/error status rather than swallowing corruption.

GET status/query must never construct profile/transport/capture/install; verify
canonical store read-only, don't recreate absent files. Typed input errors422;
store errors closed unavailable envelope with code, no raw exceptions/paths.
Cursor validation should not become generic internal503. Verify API response
serialization preserves exact decimal strings and existing SourceRef keys.

Test against real temporary Store/CaptureStore + fake transport where needed, not
only monkeypatched query-return dicts. Existing tests total218 routes ->expected222
(derive actual), preserve original named route sets and add explicit four new
route names. No unrelated auth/test expectation edits.

Evidence via .superpowers/sdd/2026-09-11-sec-query-settings/run_checks.py using own
task-3 run names. RED/GREEN, malformed params, static route matching, no-network
read/configsave, partial/empty, permission-before-construct, pagination filter
through HTTP, source schema unchanged on GET, corruption notzero capacity.
Commit only allowed files after self-review. Report task-3-report.md here with
exact JSON response examples/signatures for UI, tests/commands/counts, raw files,
commit and any caveats.

Other agents own backend query files and frontend files; yours are disjoint.
Before staging or committing, tell parent ready-to-commit so index writes are
serialized. No commit of others' work or changes to plan/ledger. Facts-dependent
real-store tests must be rerun once parent signals Task 2 exists, before completion.
