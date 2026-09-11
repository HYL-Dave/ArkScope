# Task 1 Test Transfer (Complete, Tests Frozen)

Tests-only specialist; no runtime edits, commits, provider calls, or real stores.

## Exact Runs

- `task1-tests-baseline.xml`: 129 passed, 2 failed, 27.72s. Runtime deletion happened during this control run; failures are the two codec AST owners for the deleted old store/review paths. This is not a clean pre-edit baseline. Parent owns baseline85P and absence RED4.

## Runtime Handoff

- `task1-tests-concurrency-red.xml`: 12 failed / 17 passed, 10.20s; INVALID as runtime evidence for writer/cancellation arms: test attempted updates to an immutable succeeded job. Only appended-request arm independently demonstrated a real failure.
- `task1-tests-concurrency-red-corrected.xml`: 1 failed / 28 passed, 9.33s. `test_current_validated_read_rechecks_its_binding_inside_the_transaction[model_request_added]` did not raise. WAL controls passed. Cancellation now explicitly bypasses/restores triggers and is schema-generation defense, not running cancellation.
- `task1-tests-call-decode-red.xml`: 6 failed / 15 passed / 19 deselected, 8.82s. Five `test_current_source_validation_leaves_profile_writers_available[DELETE-<command>-decode]` arms expected a real unrelated writer commit and successful prepare/confirm/execute; observed `investigation_recording_unavailable` from the held read transaction. WAL and finding-validation arms pass. Appended `call_added` expected `investigation_integrity`, observed no exception. Parent is fixing raw-capture/decode ownership and step/call binding.
- `task1-tests-gap-history.xml`: 7 failed / 49 passed, 21.98s. Four real current gap-validation REDs (`test_current_adoption_rejects_malformed_saved_gaps_even_with_valid_payload_hash`): NULL -> TypeError; object/credential-bearing URL/raw exception reason -> accepted. Three history arms incorrectly targeted the source table instead of current history's approved result/passages snapshot and are being corrected, not reported as runtime defects.
- `task1-tests-source-red.xml`: 9 passed, 2.59s; despite the filename, parent runtime fix was already loaded, so this is GREEN-only evidence. Includes real running heartbeat/cancel wait, DELETE-mode owned read, no-transaction cursor release, caller-owned write transaction, and snapshot under late source plus step writes.
- `task1-tests-source-history-green.xml`: 1 failed / 72 passed, 22.95s. Remaining current malformed model-context RED: `test_current_adoption_requires_citations_from_the_recorded_model_context[None]` expected `investigation_integrity`, observed `TypeError`. Corrected historical passage binding and re-signed missing-web owners all passed; current adoption/reversal/provider safety controls passed.
- `task1-tests-usage-read-report-red.xml`: 6 failed / 12 passed, 4.60s. All six `test_current_reopened_usage_rechecks_call_binding_and_integrity` arms expected `investigation_integrity`, observed no exception after re-signing the offending current step/result: `remote_id`, `unknown_call`, `duplicate`, `malformed_usage`, `malformed_observation`, `aggregate`. Positive real-agent known/unknown/failure/lost-outcome usage and durable source diagnostics passed.

## Transfer Status

- Current review/routes/history imports transferred; no executable legacy aliases retained.
- All useful old adoption, concurrency, source, usage, and gap owner transfers are frozen.
- Five new owner files, nine modified owner files, six obsolete test files physically deleted. Full list: `task1-tests-frozen-paths.txt`.
- Exact removed-node accounting and comprehensive verification are complete. Ready for independent Task 1 review.

## Inverse Mutations (In Memory Only)

- `task1-tests-inverse-skip_binding.xml`: 1 failed, 0.64s. Disabling `ValidatedInvestigationRead.on_connection` binding checks makes `test_current_confirmation_rejects_source_added_after_validation` apply an approval it must reject (`DID NOT RAISE`).
- `task1-tests-inverse-missing_history_binding.xml`: 1 failed, 1.07s. Routing history by `web` presence only makes `test_current_history_rejects_resigned_missing_or_corrupt_investigation_binding[missing]` fabricate a manual explanation from a re-signed current receipt with missing provenance.
- `task1-tests-inverse-skip_passage_digest.xml`: 3 failed, 1.78s. Removing the historical passage digest guard makes all three `test_current_history_requires_approved_passage_digest_even_when_result_is_resigned` arms accept unbound source URL/time/quotation edits.
- Mutations use scratch `task1_mutation_plugin.py`; no product files changed. Each mutation process exits before the next starts.

## Baseline Census

- Exported untouched `2842c497` source/tests and required support files into ignored scratch; no product files edited. Collection only, no baseline test fixtures executed.
- First two collection attempts had 9 import errors (118 partial nodes): missing support tree, then an interrupted support archive. They are NOT census evidence.
- A support archive initially failed git-crypt smudge on an unrelated encrypted research document. The final archive preserved encrypted blobs opaque using command-scoped filter settings, without reading keys or decrypting material.
- Corrected reviewed offline runner collection: **331 nodes, 1.67s**, saved as `task1-tests-baseline-nodes.txt`.
- Provisional collection before the final four inherited proof cases: 286 nodes, 1.27s.
- Final frozen owned-file collection: **290 nodes, 1.32s**, saved as `task1-tests-final-nodes.txt`.

## Latest Integration

- `task1-tests-owned-integration.xml`: **274 passed, 12 failed, 70.82s**. Eleven failures are the reported gap/usage/malformed-context defects. One was a fixture regression introduced by Task 2's correct installer transaction guard: the unrelated seed write was not committed before install; fixed in this test owner without changing runtime.
- No source files were edited by this specialist. The parent implemented all reported product fixes.
- `task1-tests-final-gap-proof.xml`: **54 passed, 24.96s** after the parent fixes. Includes the last four transferred essential-proof-with-gaps cases.
- `task1-tests-final-verification.xml`: **428 passed, 83.17s**, exit 0. All 290 frozen owned tests plus 138 existing controller/agent/finding/usage/absence controls pass. No remaining runtime failures, skips, or expected-failure markers in this run. In-memory inverse mutations are absent from this process, so their five owners also have restored GREEN evidence.
- `git diff --check`: exit 0. Obsolete store/review/schema/projection imports and deleted-test imports in all surviving owned files: zero matches (rg exit 1).
- Parent separately reported 684 passed / 7390 deselected, 98.49s for broader Task 1/2/3 focused integration. That is parent evidence, not a run by this specialist. The complete repository suite is the parent's Task 4 responsibility.

## Owner Accounting

Exact node delta: **331 baseline -> 290 frozen = 147 retained IDs + 143 added IDs; 184 removed IDs**.

- `task1-tests-owner-accounting.json` lists every exact removed and added node ID. Each removed ID has either exact passing current replacement IDs or an explicit exclusively-legacy-removal reason.
- Removed classifications: **169 transferred**, **14 exclusively legacy removed**, **1 changed current policy** (unknown event date now requires an explicit attended execution date, not a fabricated model date).
- `task1-tests-owner-transfers.md` groups the same accounting by the 77 removed test function owners for human review.
- Current owners cover actual li_ agent/controller/store/adoption, four channels, gap acknowledgement and proof vetoes, exact source/result/header/call/step binding, DELETE/WAL concurrency, permission recheck, source snapshot consistency, caller transaction isolation, idempotency, rollback, future execution, evidence/provider/position changes, reversal, source context retention, usage and remote-outcome truth, and captured model/auth/passages in history.
- Pure public source hashing/context/byte-range tests remain. The source-read-report validator remains a pure contract owner alongside real current agent emission/persistence tests.
- Intentional obsolete subcontracts are itemized in the JSON ledger: old population/projection shapes; fixed two-phase usage envelope and old complete/fail write APIs; old per-source-ID failure dictionaries; old page-specific encoding/capture schema; mutable succeeded-job semantics; old source-table history interpretation. No legacy runtime was copied into active fixtures.

## Frozen Files

All paths are under `tests/`; exact paths are also in `task1-tests-frozen-paths.txt`.

Modified:
- `test_lifecycle_investigation_review.py`
- `test_lifecycle_investigation_store.py`
- `test_lifecycle_investigation_routes.py`
- `test_lifecycle_journal_codec.py`
- `test_lifecycle_source_capacity.py`
- `test_lifecycle_source_context.py`
- `test_lifecycle_source_progress.py`
- `test_lifecycle_source_read_report.py`
- `test_ticker_identity_history.py`

Added:
- `test_lifecycle_investigation_adoption_safety.py`
- `test_lifecycle_investigation_attended_concurrency.py`
- `test_lifecycle_investigation_gaps.py`
- `test_lifecycle_investigation_source_journal.py`
- `test_lifecycle_investigation_usage_journal.py`

Deleted:
- `test_lifecycle_web_store.py`
- `test_lifecycle_web_review.py`
- `test_lifecycle_web_read.py`
- `test_lifecycle_web_gaps.py`
- `test_lifecycle_web_attended_concurrency.py`
- `test_lifecycle_web_usage_journal.py`

Not touched: runtime source, migration/retirement/population/current tests, parent's current-ownership absence tests, real databases/config.env, provider/network/install/restart/merge/push. No commit or staging by this specialist.

## Reproduction

Each run used the reviewed `offline_pytest.py` with `env -i`, PATH `/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin`, `PYTHONDONTWRITEBYTECODE=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, and a distinct `ARKSCOPE_OFFLINE_TEST_WORKSPACE=<scratch>/task1-tests-*` root. The final command is preserved verbatim in `task1-tests-final-command.txt`.

Inverse runs additionally set `PYTHONPATH=<scratch>`, `TASK1_INVERSE_MUTATION=<name>`, and `-p task1_mutation_plugin`; no source files are patched. The baseline export is only ignored scratch collection material, not an active fixture or a compatibility implementation to ship.
