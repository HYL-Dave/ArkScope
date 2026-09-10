# Task 1 Scoped Re-Review

**Result: both prior P2 findings resolved; no remaining findings within this re-review.** This supersedes only findings 1 and 2 in `task1-review.md`, not the parent's integration checks. Scope was the added tests, retained helper owners and their exact agent execution paths.

## Finding Disposition

1. **Pending-read cancellation: resolved.** `tests/test_lifecycle_investigation_execution_cleanup.py:203` now runs the actual `run_agent` with a blocking reader for both cooperative stop and task cancellation. It waits for reader entry, checks the `stop_requested` failure, confirms stop delivery and worker exit before the await returns, and asserts exactly three model submissions, one URL read and no captured source. The model rejects any fourth submission. The retained helper tests at line 283 independently protect asynchronous joining before executor shutdown can mask an early return.

2. **Successful finding with unread supplement: resolved.** The actual-agent test at `tests/test_lifecycle_investigation_execution_cleanup.py:160` covers all four channels. It asserts the exact unread URL/reason in subsequent `source_gaps` material and final `gaps`, a successful grounded terminal-delisting action without block reasons, citations exclusively from `source-1`, one capture, and exactly one read per URL. The corrected `source_gaps` fixture field matches the current model-material contract.

**Spec/quality conclusion:** the two missing current-entrypoint behavioral controls are now present, with concrete assertions and bounded worker cleanup. The relevant agent code still persists gaps and awaits `_read_one`; its cancellation branch still shields the worker future. No product change is needed for these findings, and no unrelated surface was reopened.

## Verification

Independent scoped run: **9 passed in 1.08s**, exit 0. Ran these node families in `tests/test_lifecycle_investigation_execution_cleanup.py`:

- `test_current_agent_can_conclude_with_disclosed_unread_supplement` (4 channels).
- `test_current_agent_pending_read_stops_before_any_further_dispatch` (2 stop modes).
- `test_agent_owned_read_stops_and_awaits_worker` (3 modes).

Used only the plan's `offline_pytest.py`, `env -i`, disabled pytest plugin autoload/bytecode writes, and `ARKSCOPE_OFFLINE_TEST_WORKSPACE` set to this plan's `task1-review` directory. PATH included the virtualenv, `/home/hyl/.nvm/versions/node/v22.14.0/bin`, `/usr/bin` and `/bin`. Fresh results: `task1-review/re-review.xml`.

Parsed supplied XML evidence: `task1-review-fix-corrected.xml` records 20 passes; `task1-mutation-gap.xml` records all four mixed-outcome owners failing; `task1-mutation-sync.xml` records both pending-read owners failing. These are reviewed artifacts, not independently repeated mutations. The six-file `task1-final.xml` run is not claimed by this re-review.

Only this report was written. No source edits, provider sessions, production data, configuration, .env or token-store access.
