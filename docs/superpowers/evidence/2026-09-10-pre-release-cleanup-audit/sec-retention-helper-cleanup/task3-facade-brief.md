# Task3 Follow-Up: Delete The Unused Confirmation Facade

Worktree `/tmp/arkscope-listing-sec-macro-convergence`, base `0c5896a5`.
Parent will dispatch only after its frozen whole-backend run ends.

Scope: remove the four-line `TickerIdentityService.get_review_confirmation`
method in `src/ticker_identity_service.py`. Its sole runtime caller was the
HTTP entry just removed by Task3; all remaining calls are in tests. Do not keep
an alias/forwarder. Keep `src.security_lifecycle_review._result` and
`confirmation_for` unchanged: they are actual current execution/history owners.
Do not change HTTP, schema, codec, data, other helpers or configuration.

Tests: add a named absence owner against the actual service class. Observe RED
while the facade still exists. Then remove it and change the six existing calls
in `tests/test_security_lifecycle_review.py` and
`tests/test_security_lifecycle_review_routes.py` directly to `_result(service,
transition_id)` under its real module. Preserve every expected status, receipt,
integrity, action and no-write assertion. Do not remove/rename existing tests.
No new abstraction, helper module or generalized linting.

Verify the two full review files and current identity/history/route suites through
this plan's `offline_pytest.py`, exact clean environment/interpreter/PATH used by
Task3, separate `ARKSCOPE_OFFLINE_TEST_WORKSPACE=<plan-scratch>/facade-state`.
Use a separate basetemp/root per run; keep XML/logs in scratch. Restore the old
facade temporarily to prove the named absence owner fails, then restore GREEN.
All work is fixture-only; no production, `.env`, credentials, provider, App,
install, merge/push or subagents. No source edits outside the three named files.

Commit only scoped code/tests, leaving parent docs untouched. Announce immutable
head immediately; write `task3-facade-report.md` with exact counts/added test ID,
RED/GREEN/mutation evidence and any concerns. Full commands can be in JSON/logs,
not repeated as several pages. Parent owns final collection, census and broad
review; do not duplicate whole-backend execution.
