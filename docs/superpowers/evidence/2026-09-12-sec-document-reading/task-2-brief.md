# Task2: Durable Documents And Exact Stored Passages

Read plan2026-09-12-sec-document-reading.md Task2 and Global Constraints, spec
sections4/7/8/10, Task1 reviewed report for concrete interfaces. Work only in this
linked worktree. No subagents, provider/production/token/env access, installation,
reset/drop, App restart or merge/push. Use apply_patch and own task-2/ scratch.
Do not stage/commit until sole-index permission. Ask before write-scope expansion.

Task2 writes document_store.py, document_service.py, document_queries.py, their
three focused test files, schema.py, capture_lock.py and exact-schema collateral.
Follow existing Store/CaptureStore/write leases instead of new path/backup APIs.
Use same offline run_checks.py with unique task2-* names, backend -q paths. Named
behavior RED, GREEN, planned inverse mutations+source restoration hashes required.
Small fixture refresh tests should use actual PublicSourceReader with only pinned
connection/DNS replaced, plus explicit fixture SecSourcePolicy. No actual sources.

Read-only behavior from queries.py is authority. Latest receipt's catalog bindings
(not every retained snapshot or arbitrary SQL latest) select primary/form metadata;
conflicting primary/form returns unavailable before *any* directory/document
dispatch. An unrelated pending historical source alone need not block reading an
exact observed row; keep its catalog coverage gap rather than claiming full catalog
coverage or applying a global availability veto. Keep record provenance and complete
source set. An observation-budget cutoff that could hide an already bound conflict
is not the same as unrelated pending history: do not choose a primary from a
truncated authority scan. Pinned captures ignore
new catalog and latest attempts, but verify stored associations and content hashes.
Latest failed attempt never offers earlier text as successful current observation.
Publish only immutable complete directory/original/text objects+rows. Distinguish
known no-dispatch failures from interrupted/request failures; never conceal raw
request/capture outcomes behind fabricated complete result. All errors content-free.

Cursor is canonical closed versioned token, not authentication. Even caller-edited
byte offsets need bounds/UTF8 validation and referenced capture/document/filter/mode
validation. Reusing helpers is welcome but no fake receipt slot. max_chars controls
Unicode characters; actual citation byte offsets must land at exact UTF8 boundaries.
Document IDs are exact/case-sensitive filenames. A citation's resolved document ID
must reopen its capture; primary alias may match only a capture bound as that
filing's primary, never another document. Test both primary and resolved-ID pinned
reopening without weakening cursor's original operand binding.
Queries are literal case-sensitive, may span multibyte characters. Index pagination
must not omit document choices/sections. Entire envelope<=256KiB, emitted complete
citations, no 'complete' from partial parsing. Empty query selection only if truly
observed; unknown section carries gap+text_start_cursor. Unknown form yields whole
text access. Test tiny output pages with a longer search term: emit a specific
page-size gap if a complete match cannot fit, never a stuck cursor or a partial
match mislabeled complete. No acquiredHTML is returned for UI rendering, only
canonical text.

Concurrency uses a distinct root-level document-acquisition lease spanning both
requests but not capture_writer/marketwrite locks over network/parsing. Capacity
and free-space preflight before each request; publication accounts directory+
original+canonical bytes via CaptureStore. Retain original decompressed bytes,
real wire/decoded observations. Request limit1/redirect0, timeout finite. If worker
thread introduced, cancellation must stop and await it; no unnecessary async layer.

Finish with self-review/report task-2-report.md, concrete API signature/return shape
examples sufficient for Tasks3/4, RED/GREEN and inverse evidence paths. Run allSEC
and public_sources/wire/locks suite once before report. Parent independently reviews.
