# Final Integrated Review

## Verdict And Findings

**Spec: PASS for the approved document-reading batch. Quality: APPROVED.**
No new actionable findings: **Critical 0, Important 0, Minor 0**. No product fixes requested.

**Ready to merge? No, not yet as a release-gate claim.** This independent code review approves the integrated change; the parent's fresh complete backend execution, exact node/skip reconciliation and final evidence publication remain separate pending gates. This is not merge, push or production-activation authorization.

## Scope And Method

- Reviewed base `3e98bda264e024b3aa03efafd0ba0abab9a19a5a` through HEAD `02a0fff4403e3fe7f1be02b97c91a4dec8cfde9b`.
- Read `final-review-brief.md` first, then the requirements plan, approved spec (particularly sections 4/7/8/10), reports, final task rulings and `progress.md`. Applied `requesting-code-review/code-reviewer.md` to one whole-batch review, not four renewed task gates.
- Official artifact: `final-diff.txt`, 284581 bytes / 5280 lines; SHA256 `277188305b3f063221e7f08a17009e56cc54b57a182e2d6b8fe6cef01c0eb11e`. Read once in nonoverlapping ranges: 1-430, 431-860, 861-1290, 1291-1720, 1721-2150, 2151-2580, 2581-3010, 3011-3440, 3441-3870, 3871-4300, 4301-4730, 4731-5160, 5161-5280.
- Followed relevant unchanged dependencies in `lifecycle_public_sources.py`, `captures.py`, `queries.py` and `store.py`. Checked current line references and inspected retained desktop/mobile screenshots. No suites or historical probes were rerun; no new generated probe was necessary.

## Integrated Assessment

| Contract | Assessment and source evidence |
| --- | --- |
| Acquisition authority | Exact canonical filing ID establishes the accession root; observed safe directory entries grant file access. Receipt-bound catalog traversal rejects conflicting primary/form metadata and bounded-source failure before dispatch. A filer-agent accession prefix need not equal issuer CIK. `documents.py:34`, `documents.py:61`, `document_service.py:49`. |
| Parsing and compatibility | The optional callback leaves the default public reader extraction path intact. Document parsing separately bounds decoded input, markup, nesting, events/fragments and canonical text; cancellation propagates. XHTML QName identity remains distinct from tolerant display rules, and namespace scopes restore without inherited-map copies. Ambiguous TOC/duplicate headings remain gaps rather than invented sections. `src/lifecycle_public_sources.py:513`, `document_text.py:145`, `document_text.py:212`, `document_text.py:334`, `document_text.py:411`. |
| Capacity and publication | A separate root-wide acquisition lease spans resolution/read/publication, while writer transactions remain short. Both requests preflight capacity; directory bytes are charged before document dispatch; original/canonical bytes use CaptureStore and are hash-read before immutable associations publish. Publication failure may retain charged objects, not a successful incomplete capture. `capture_lock.py:189`, `document_service.py:88`, `document_service.py:169`, `document_service.py:216`, `document_store.py:85`; unchanged `captures.py:91`, `captures.py:132`. |
| Failure, latest and pin semantics | Interruption markers prevent stale success from masquerading as the latest attempt. Remembered primary aliases invalidate both spellings without supplying fresh dispatch authority. Independent request counts survive malformed reports/cleanup failures; unknown is not fabricated zero. Explicit captures bypass latest selection and verify their original receipt/source bindings and bytes. `document_service.py:111`, `document_service.py:171`, `document_store.py:38`, `document_store.py:119`, `document_store.py:130`, `document_queries.py:98`. |
| Stored queries and citations | Pure cursor/operand validation precedes storage. Index and passage modes have separate continuation, with explicit oversized-entry gaps; whole-text fallback clears section/query bindings. Literal search is case-sensitive and nonoverlapping; citations slice exact canonical UTF-8 bytes and bind capture, source, accession and both hashes. Cursor filters include page size and cannot silently switch snapshots. `document_queries.py:47`, `document_queries.py:154`, `document_queries.py:194`, `document_queries.py:227`. |
| HTTP integration | GET never installs, preflights, reads profile budget or acquires. POST validates the exact primary-only body and shared write permission before configuration/install, then injects managed SEC identity into the real reader policy. The six old SEC endpoints remain alongside the two new routes. Error adapters avoid source/path disclosure and do not manufacture a no-dispatch attempt for a lost server response. `src/api/routes/sec_research.py:258`, `src/api/routes/sec_research.py:286`; `tests/test_api.py:169`, `tests/test_security_lifecycle_routes.py:468`. |
| Reader composition | Stored-only opening, capture-bound index/text requests, cached Back, explicit current reads and plaintext citation rendering agree with backend contracts. Parent-owned uncertainty survives close/reopen; definite completion clears it without replacing a newer reading. Primary alias selection preserves only an observed equivalent capture, and loaded section choices survive index Back. `apps/arkscope-web/src/settings/SecDocumentReader.tsx:60`, `:134`, `:171`, `:203`; `SecResearchPanel.tsx:153`, `:348`. |

Source paths in the table without a leading directory are under `src/sec_research/` unless the surrounding frontend path identifies the owner.

## Strengths

- Authority, invalidation memory, immutable evidence and presentation state have distinct owners. Their integration does not introduce a second provider path or reinterpret old citations through current catalogs.
- Focused tests exercise real PublicSourceReader/service/store behavior with generated wire bodies, failure publication boundaries, forbidden-call ledgers, relocation and exact byte ranges. Frontend tests cover outgoing operands and visible selection state rather than only component internals.
- The scope is disciplined: no incomplete Research tool replacement, automatic prefetch, migration chain or destructive recovery was smuggled into the reader. Existing tool/transport boundaries remain unchanged in the official diff.

## Evidence Considered

- Prior findings and accepted refinements remain closed after integrated inspection: Task1 hidden namespaces/TOC/QName identity (`task-1-rereview-r2.md`); Task2 alias invalidation/dispatch evidence (`task-2-rereview-r1.md`); Task3 test-side forbidden-call diagnostics (`task-3-rereview-r1.md`); Task4 remounted acquisition state/primary pin/index section selection (`task-4-rereview-r1.md`). No new cross-task failure was identified.
- `current-inverse-evidence.json` lists 17 runs and 63 intended testcase failures. Independently checked every unique restored-file SHA256 in that manifest: all 17 backend source/test paths match. Also checked eight relevant frontend source/test paths against `source-before.json`: all match. `git diff --name-only HEAD -- src tests apps/arkscope-web` returned no differences. These are identity checks, not rerun claims.
- Retained Task1 resource evidence covers bounded synthetic HTML/XML allocations, namespace-depth growth, XHTML case-sensitive scopes, cancellation and exact limits. The report distinguishes input allocation and traced parser allocations from process RSS; no whole-App 4-GiB guarantee is inferred (`task-1-report.md:184`, `:479`).
- Fresh parent `frontend-final-fixed/output.log` records **1776 passed / 123 files**; its command and the `typecheck-final-fixed` / `i18n-final-fixed` command records have exit 0. Existing React act-warning debt is explicitly retained in diagnostics rather than described as a warning-free baseline.
- `browser-final-fixed/command.json` records exit 0. Its results cover en/zh-Hant at 1280x960 and 390x844, **84 HTTP observations each**, no page errors, and primary-pin/index-Back/stale-response controls. Inspected `en-1280-reader-only.png` and `zh-Hant-390-reader-only.png`: identifiers wrap, controls remain contained, plaintext is bounded, and no incoherent overlap is visible. Browser execution and object-byte assertions belong to the parent's retained evidence, not a reviewer rerun.
- Fresh census remains **review_required**, with 4346 candidates / 3460 uncertainties / 1133 source files read. `census-notes.md` explains the composed GET URL, translated opener keys and compound selector consumers; these have real code/browser consumers. This is not a clean-census or authorized-deletion claim.
- `final-collect-scoped/output.log` records **9180 collected tests**. At report preparation `backend-final-scoped` was still executing, so no final backend pass count or exact executed/skip reconciliation is claimed. The eight-error archived-test collection launch is retained as a parent launcher mistake, not a product defect or passing verification.

## Limits And Recommendations

Complete the parent's frozen-source backend/reconciliation and archive gates before treating the batch as fully verified. Preserve the current parser lexical-dependency controls on Python upgrades. Full-object verification on each stored page favors integrity over large-document paging speed; no throughput/RSS certification was performed here.

Conservative section omission, primary-only HTTP acquisition, explicit pre-release schema mismatch, and charged failed-publication objects are approved scope decisions, not new findings. SEC-RECOVERY-001/002 remain open; issuer resolution, three Research tools/four channels, persisted Research citations, export, schedule, remaining cleanup and SQLite upgrade are not delivered by this batch.

This review performed no production DB/config/token access, provider request, dependency installation, subagent dispatch, product/index/HEAD edit, merge, push or activation. Only this report was created, once, in the authorized scratch directory.
