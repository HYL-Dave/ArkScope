# Spec Compliance

- **Issues found.** Two Important defects violate current-versus-pinned alias semantics and truthful request accounting: `src/sec_research/document_service.py:143`, `src/sec_research/document_store.py:116`, and `src/sec_research/document_service.py:107`. Both are reproduced below; Task2 needs fixes.
- **Cannot verify from this diff:** whole-App preservation, four transport-boundary integration, production profile wiring and browser acceptance remain parent checks under `docs/superpowers/plans/2026-09-12-sec-document-reading.md:28`. No expansion into those tasks or Task1 parser internals was performed.

## Strengths

- `src/sec_research/document_store.py:40` binds capture identity to immutable metadata, checks relational fields and directory identity, and verifies exact retained receipt/source associations. `src/sec_research/schema.py:37` adds the four owned tables with foreign keys; the diff extends UPDATE/DELETE/REPLACE guards without changing structured receipt kinds.
- `src/sec_research/document_service.py:41` uses receipt-bound catalog observations, rejects conflicts and observation-budget gaps before dispatch, and retains pending-history coverage gaps without vetoing an observed filing. `src/sec_research/document_service.py:170` admits only a resolved ID present in the observed directory.
- `src/sec_research/document_service.py:80` preflights each operation and supplies one request, zero redirects, finite timeout and the required 16/16 MiB directory and 32/128 MiB document limits. `src/sec_research/document_service.py:173` charges the directory before the second request; `src/sec_research/document_service.py:192` hash-checks and CaptureStore-publishes original/canonical bytes before document rows.
- `src/sec_research/document_queries.py:47` validates canonical closed cursor shape and operand bindings before I/O; `src/sec_research/document_queries.py:140` takes the capture from the cursor, not latest. `src/sec_research/document_queries.py:222` checks actual section bounds and UTF-8 boundaries; `src/sec_research/document_queries.py:238` pages by Unicode characters and `src/sec_research/document_queries.py:249` searches literal, non-overlapping matches with exact byte citations.
- `src/sec_research/document_queries.py:185` provides whole-text fallback for unknown sections; `src/sec_research/document_queries.py:192` paginates document/section entries and explicitly gaps an un-emittable entry while advancing. `src/sec_research/document_queries.py:245` rejects a page too small for a complete match. `src/sec_research/document_queries.py:183` enforces the complete encoded-envelope ceiling.
- `tests/test_sec_research_document_queries.py:30` exercises restart/relocation and primary/resolved pinned reopening. The diff also contains meaningful actual-reader tests for gzip observations, limits, locks, quota, corrupt/missing objects, interruption, and all four planned inverse owners; all eight requested implementation/test paths are present.

## Issues

### Important: Early Failure Leaves The Other Alias Serving Stale Success

- **Location:** `src/sec_research/document_service.py:143`, `src/sec_research/document_service.py:147`, `src/sec_research/document_store.py:116`.
- The first interruption marker has null `resolved_document_id` and `primary_document`. If the initial check cancels or catalog resolution finds a conflict, the final failure also has null aliases. `latest_attempt()` matches only the requested operand or aliases on that individual row, so the other spelling skips the new failure and selects the previous successful capture.
- Reproduction: acquire `primary` as `file:actual.htm`, then introduce a receipt-bound primary conflict and refresh either spelling. Reading the requested spelling is unavailable, but reading the other spelling returns the old capture with `status=ok`. Early cancellation reproduces the same result in both directions. Explicit pinned reads remain unchanged, as required.
- This defeats the binding rule that a failed refresh must not present retained text as the current successful observation. Preserve the previously established alias relationship for invalidating current observations, independently of successful new catalog resolution; do not use historical metadata to authorize dispatch through a conflict. Cover both directions for pre-resolution failures and interruption markers.
- **Evidence:** `task-2/test_review_probes.py:38`; four failing cases in `task2-review-probes-01/output.log:3`. Existing alias failure tests resolve metadata before failing, so they miss this branch.

### Important: Report Validation Can Erase An Actual Request

- **Location:** `src/sec_research/document_service.py:105`, `src/sec_research/document_service.py:107`, `src/sec_research/document_service.py:206`.
- `_read()` appends request evidence only after `validate_source_read_report()` succeeds. If validation raises, the actual reader count and observations are discarded; `refresh()` then infers dispatch exclusively from the surviving reports and can persist `outcome=no_dispatch` with `requests=[]` despite an actual directory request.
- Reproduction uses the real PublicSourceReader and generated fixture response status 600, with only the established connection/DNS substitutions. The reader has one request and one status-600 observation; its report validator rejects that status. The returned/durable attempt instead says `no_dispatch`. No body or document is published, but acquisition accounting is false and the original request failure is replaced by report-validation failure.
- Preserve independently captured dispatch/count evidence even when report validation or cleanup fails. Keep the malformed-report error explicit and content-free, but never equate missing validated reports with known zero dispatch or fabricate a complete report. Add the directory failure owner and ensure the same path retains the second request after a successful directory operation.
- **Evidence:** `task-2/test_review_probes.py:68`; reproduced failure at `task2-review-probes-01/output.log:35`. The unchanged reader records response status at `src/lifecycle_public_sources.py:500`; its report validator rejects values above 599 at `src/lifecycle_public_sources.py:139`.

### Critical / Minor

- No additional Critical or Minor findings identified within this task scope.

## Checks And Evidence

- **Immutable provenance:** `task-2-diff.txt:1` declares `b07eba2b..eeffb971`. Read its 1,448 lines once in nonoverlapping ranges 1-370, 371-740, 741-1100, 1101-1448. `task-2/test_review_probes.py:14` passed: all eight current files match both the diff's head Git-blob prefixes and `task-2/final-inverse-hashes.json:2` SHA-256 baselines. No Git commands or state changes were used.
- **Named outside-diff check, authority truncation/provenance:** inspected `src/sec_research/queries.py:120`, `src/sec_research/queries.py:211`, `src/sec_research/store.py:238` and `src/sec_research/store.py:321`. They bind exact receipts/snapshots, preserve observation metadata and expose bounded-source gaps; the new service rejects an incomplete authority scan. No broader catalog/parser review.
- **Named outside-diff check, quota and content integrity:** inspected `src/sec_research/captures.py:91`, `src/sec_research/captures.py:108` and `src/sec_research/captures.py:132`. Preflight/put use short writer leases, deduplicate/account persisted objects, and hash-verify reads. The document lease is distinct; no async document worker is introduced. Worker lock probes remain the concurrency evidence.
- **Named outside-diff check, exceptional request accounting:** inspected `src/lifecycle_public_sources.py:129`, `src/lifecycle_public_sources.py:399` and the read/body-report boundary at `src/lifecycle_public_sources.py:453`. This establishes the real reader's cleanup, counts, observations and validator mismatch used by the focused probe; oversized declared lengths are already sanitized, not an additional finding.
- **Named outside-diff check, exact filenames/cursor encoding:** inspected `src/sec_research/catalog.py:67` and `src/sec_research/queries.py:25`. The reused basename validator preserves exact case-sensitive ASCII IDs; cursor encoding is canonical JSON/base64 rather than an integer receipt-slot workaround.
- **Worker evidence inspected, not rerun:** `task2-regression-01/output.log:20` reports 1,292 passed; `task2-precommit-01/output.log:4` reports 87 passed; `task2-final-inverse-restored-01/output.log:3` reports 4 passed. These logs have no warnings. The regression precedes the documented final oversized-index fix; the 87-test run covers that final change.
- **RED/inverse evidence inspected:** `task2-red-behavior-01/output.log:1` and the logs under `task2-inverse-latest-final-01`, `task2-inverse-query-binding-final-01`, `task2-inverse-primary-absence-01`, `task2-inverse-truncated-complete-01` show the named assertion failures. Final-source hashes match as noted above; no inverse or suite was rerun.
- **Focused reviewer execution:** `task2-review-probes-01/command.json:1` records the plan offline runner invocation for only `task-2/test_review_probes.py`: **5 failed, 1 passed**, exit 1, 1.00s pytest time. The failures are the five targeted reproductions of the two findings; provenance passed. No real provider/data/config/token access, installation, restart, subagents, product/index/Git edits or integration/browser work. Only review scratch/evidence and this report were created.

## Assessment

- **Spec compliance: Issues found. Task quality: Needs fixes.** Immutable capture storage and bounded stored reads are substantially implemented, but alias invalidation and exceptional dispatch accounting break explicit Task2 contracts. Fix both paths and add their focused owners before approving this task.
