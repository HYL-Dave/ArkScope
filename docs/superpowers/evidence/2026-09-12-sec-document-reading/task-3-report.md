# Task 3 Report

DONE: `2f84d2de` on base `1f964efe`. Four approved files only; self-review and
scoped checks complete. No blocking contract concern. Parent owns independent
review and final browser/backend gates. No parent fixture/helper edits.

## HTTP And Frontend Types

Both methods: `/sec-research/filings/{filing_id}/document`.

| Interface | Contract |
| --- | --- |
| GET operands | `document_id: string = "primary"`; `capture_id`, `section_id`, `query`, `cursor`: optional strings; `max_chars`: canonical decimal integer 1..20000, default 6000 |
| POST body | `DocumentAcquireRequest = {document_id: "primary"}`; required, no extra fields or coercion |
| GET envelope | Exactly `status/data/gaps/observed_at/coverage/next_cursor`; status `ok/partial/empty/unavailable`; observed_at and next_cursor are string or null |
| GET selectors | `data.document` metadata or null; `data.documents[]` choices use string `document_id`/`name`; `data.sections[]` use string `section_id`/`label`; `data.passages[]` use string `text` and citation object; `data.text_start_cursor`: string or null |
| Provenance | Citation byte offsets are integer, end-exclusive UTF-8; match offsets nullable integers; hashes, filing/document/capture IDs, accession, source_url and extraction_version are strings |
| Coverage | `complete`: boolean; `capture_id`: string or null; opened captures add integer receipt_id, string mode and boolean catalog_complete; index pages add integer index_total/index_offset |
| POST attempt | Unwrapped Task2 attempt; status/gaps/outcome preserved; attempt_id: integer or null; capture_id/resolved_document_id/primary_document/invalidation_primary_document: string or null; acquisition_id/observed_at/filing_id/document_id: strings |
| Request evidence | `requests[]`: operation/url strings, request_count integer or null, dispatch_state dispatched/not_dispatched/unknown, report object or null, gaps array; use request_count, never infer zero from missing report |

Keep the exact document/filter/max_chars operands when following next_cursor.
Whole-text fallback uses text_start_cursor with section_id/query omitted and the
same max_chars. Render passage text, not acquired HTML. POST intentionally accepts
only primary; a directory choice does not mean that file has a stored capture.

422 is always `{"detail":{"code":"sec_research_query_invalid"}}`, except cursor
errors use `sec_research_cursor_invalid` or `sec_research_cursor_mismatch`.
Validation precedes paths/storage; new-route body/JSON validation is redacted.
Valid absent/corrupt reads are HTTP200 unavailable envelopes, never empty success.
POST uses existing db_write permission before owners; 503 detail codes are
`sec_identity_unconfigured` or `sec_research_document_unavailable`.

POST is synchronous with finite service timeouts, no custom background bridge.
A dispatched source timeout returns HTTP200 with the real unavailable attempt,
outcome=failed and measured dispatch evidence. An unexpected edge failure returns
503 without a fabricated attempt/no_dispatch claim. A client disconnect does not
prove failure; GET remains available for current or explicitly pinned rereads.

## Fixture Hooks And Examples

No new exported factory hook. The local `acquire_document.reader_factory` uses
`src.api.routes.sec_research.PublicSourceReader` and `SecSourcePolicy`; patch those
symbols for construction spies. Existing wire patch
`src.lifecycle_public_sources._PinnedHTTPSConnection` still works. Offline pacing
can patch `src.lifecycle_web_sec_sources.SecRequestGovernor`. Explicit profile
identity reaches both actual requests; GET opens neither identity nor budget config.

Evidence root `E = .superpowers/sdd/2026-09-12-sec-document-reading/`.
Full actual request operands and responses, including unshortened cursors:
`E/task3-precommit-01/pytest/test_real_post_get_search_and_0/interface-examples.json`.
Array entries 0..5 are POST, index GET, text GET, section-search GET, continuation
GET, and missing-section GET. Example POST body is `{"document_id":"primary"}`;
actual response projection is `{"attempt_id":3,"status":"ok","outcome":"complete","gaps":[]}`.
The text GET returns `"Item 1. Business\nneedle caf\u00e9 needle"`, bytes [0,36);
search `query=needle&section_id=item_1&max_chars=80` returns matches [17,23), [30,36).

## Commands And Results

Every command used installed Python and this plan's offline runner:
`/home/hyl/.virtualenvs/llm_app/bin/python E/run_checks.py NAME backend -q SELECTION`.
For every NAME below, exact expanded argv/cwd/environment are in
`E/NAME/command.json`, pytest output in `output.log`, counts in `results.xml`.
Selections below use D=`tests/test_sec_research_document_routes.py`,
S=`tests/test_sec_research_routes.py`, and I=the two node IDs:
`tests/test_api.py::test_local_runtime_lifespan_starts_scheduler_and_enumerates_routes`
and `tests/test_security_lifecycle_routes.py::test_app_mounts_the_exact_lifecycle_route_surface_and_retires_old_review_routes`.

| NAME | SELECTION | Actual result |
| --- | --- | --- |
| task3-red-routes-01 | D | 63 failed, absent HTTP routes |
| task3-green-routes-01 | D | 63 passed |
| task3-green-boundaries-01 | D I | 83 passed |
| task3-inverse-validation-order-01 | D::test_invalid_get_operands_precede_store_access D::test_cursor_binding_rejected_before_absent_store | 17 failed, 16 passed, 17 teardown errors |
| task3-inverse-get-budget-01 | D::test_corrupt_budget_does_not_block_existing_stored_document D::test_real_post_get_search_and_pinned_reread_keep_exact_bytes | 2 failed, 1 teardown error |
| task3-regression-01 | Selection below | 1627 passed (72.76s) |
| task3-inverse-profile-identity-01 | D::test_real_post_get_search_and_pinned_reread_keep_exact_bytes D::test_email_only_profile_identity_is_normalized_on_both_actual_requests | 2 failed |
| task3-inverse-permission-01 | D::test_shared_permission_denial_precedes_all_post_owners | 1 failed, 1 teardown error |
| task3-precommit-01 | D S I | 234 passed (10.24s) |

Regression SELECTION (single relevant set, not full backend):
`tests/test_sec_*.py tests/test_lifecycle_web_sec_sources.py tests/test_lifecycle_public_sources.py tests/test_lifecycle_public_sources_wire.py tests/test_security_lifecycle_routes.py tests/test_api.py::test_fixed_task_runtime_routes_mount_on_real_app tests/test_api.py::test_local_runtime_lifespan_starts_scheduler_and_enumerates_routes tests/test_api.py::test_local_runtime_gate_rejects_external_network_and_cleans_owners tests/test_tools.py tests/test_task_runtime_binding.py tests/test_fixed_task_runtime_config.py tests/test_model_routing.py`.

Inverse failures detected the intended boundary violations. Teardown errors are
TestClient portal shutdown after pytest.fail's BaseException from forbidden-call
guards, only under deliberate mutation. All four file hashes matched after each
restoration; source SHA256 `bcefb3040c18809967acd58a56fbb8e641848883a999d3b954c11a8a33076bde`.
Ordinary gates have zero failures/errors. Mounted inventory is 224, including all
six old SEC endpoints plus two new; task/model/tool contracts pass unchanged.
`git diff --check` and `git diff --cached --check` passed before scoped commit.

## Fix Round1: Test Diagnostics

DONE at `64a25c34`; only `tests/test_sec_research_document_routes.py` committed.
Forbidden calls now record into a per-fixture ledger and raise ordinary
`ForbiddenAccess(RuntimeError)`. The client wrapper asserts the ledger is empty
outside request execution in finally, including when a route catches the sentinel.
No product/API changes; 81 route cases and all 234 focused node IDs are unchanged.

RED-first: read the four original inverse archives before editing; their error
counts were 17/1/0/1. Current reruns below retain the intended failure counts with
no teardown errors. All mutations are process-local; product disk stayed untouched.

| K in task3-fix1-inverse-K-01 | Passed | Intended failures | Errors |
| --- | ---: | ---: | ---: |
| validation-order | 16 | 17 | 0 |
| get-budget | 0 | 2 | 0 |
| profile-identity | 0 | 2 | 0 |
| permission | 0 | 1 | 0 |

Using the same installed Python/runner and named selections in the original table,
inverse commands add `-p task3_fix1_inverse --task3-inverse K` after `backend -q`.
`task3-fix1-green-01 backend -q D`: 81 passed;
`task3-fix1-precommit-01 backend -q D S I`: 234 passed (10.26s), zero errors/skips.
Exact executed argv remain in each `E/RUN/command.json`; logs/JUnit are adjacent.

Parent-consumable manifest: `E/task3-fix1-current-inverse-evidence.json`.
Each run retains full `mutation.py`, exact replacement patch and all four scoped
before/mutated/restored SHA256 maps in `hashes.json`. Reproducer/verifier:
`E/task3_fix1_inverse.py`; run with installed Python and `-B` to recheck the
manifest, current hashes, zero-error failures and unchanged focused node IDs.
Combined archived RED/current/green results: `E/task3-fix1-evidence-summary.json`.
Current test SHA256: `07c5dad958bd3167394bd7c8be375498772ca890489d08719ac3d3b225b43981`;
source and both inventory owners retain their original hashes. Self-review and
diff checks passed; no open concern. Original reviewer scoped rereview remains.
