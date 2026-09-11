### Spec Compliance

- Issues found: three Important spec/quality defects in acquisition completion ownership, primary-alias pin preservation, and index/section-selection independence, detailed below. Scope: immutable `task-4-diff.txt`, `64a25c34..f53a87a4`, against Task 4 requirements/notes and approved plan Global Constraints (lines 23-66).
- Cannot verify from this task diff: full backend baseline reconciliation, census, archival completeness, recovery registration, and final whole-change review. These remain parent gates, not missing Task 4 implementation.

### Strengths

- `apps/arkscope-web/src/api.ts:1296`: GET preserves opaque operands; acquisition sends only primary with a 600000ms allowance. The three API tests exercise actual fetch arguments and typed errors.
- `apps/arkscope-web/src/settings/SecDocumentReader.tsx:60`: stored-only index/text opening binds subsequent reads to the observed capture. Separate directory and passage state preserves navigation through unavailable secondary reads. `:95` and `:254` retain exact pagination operands and reuse cached passage pages.
- `apps/arkscope-web/src/settings/SecResearchPanel.tsx:287`: selection retains the original row object and separately keys metadata variants; the row's primary URL is not request authority. `SecDocumentReader.tsx:185` renders that selected filing identity.
- `apps/arkscope-web/src/settings/SecDocumentReader.tsx:17` and `:240`: HTTPS citation links reject credentials and invalid URLs; React plaintext rendering preserves Unicode without executing document markup. `:87` and `SecResearchPanel.tsx:350` implement heading focus/scroll and connected-opener restoration.
- Archived final frontend output records 1765 passing tests in 123 files; typecheck and i18n command records exit 0. Parent final browser command/output records four successful en/zh-Hant desktop/mobile runs, 70 HTTP observations each. Parent additionally confirms 13 citation byte/hash checks per run and final heading visibility, reader focus, and exact-opener close assertions on unchanged `f53a87a4`.

### Issues

#### Critical (Must Fix)

- None identified.

#### Important (Should Fix)

1. **[P2, Spec + Quality] Known POST completion cannot update a reader reopened while it was pending.** `apps/arkscope-web/src/settings/SecDocumentReader.tsx:48`, `:143`; `apps/arkscope-web/src/settings/SecResearchPanel.tsx:349`.
   Start acquisition, close, reopen the same filing before completion, then receive a definite HTTP200 failed attempt. The old instance clears the parent's ref-backed uncertainty set, but cannot update its unmounted local state. The new reader initialized its own `unknownOutcome` once and never observes the clearance. It continues claiming the server may be running and disables acquisition even after GET reread; another close/reopen is needed to recover. This violates the in-flight acquisition/close generation contract, not the intentionally conservative handling of genuinely lost responses. Make per-filing acquisition status reactive and owned across reader mounts while keeping stale reading results suppressed. Cover completion and definite rejection after pending-close-reopen.
   **Evidence:** the one generated offline probe, `task4-review-probe/pending-reopen.test.tsx:37`, fails on the remaining unknown-outcome message after known completion and GET reread. `task4-review-pending-reopen-02/output.log` records one executed test, one assertion failure, no suite/import error.

2. **[P2, Spec + Quality] Selecting the primary alias silently drops an existing capture pin.** `apps/arkscope-web/src/settings/SecDocumentReader.tsx:204`.
   With capture A open, select its actual `file:annual.htm` entry, then select the `primary` option, including after visiting an uncaptured secondary. `ownDocument` compares the selected ID only to the resolved `file:...` metadata ID, so it is always false for `primary`; the request omits `capture_id` and marks the reading current. If another acquisition produced B, this switches to B without the explicit current command; a failed latest attempt instead makes retained A appear unavailable. The backend supports a pinned primary alias, so dropping the pin is not an API requirement. Preserve the observed primary binding when changing aliases for the same document, or make a deliberate current transition explicit. Add an A/B or A/failed-latest regression for this selector path.
   **Contract check:** `src/sec_research/document_queries.py:99` resolves an omitted pin through `latest_attempt`; `:107` accepts `primary` against its matching pinned record.

3. **[P2, Spec + Quality] Index Back can make the visible section disagree with the submitted filter.** `apps/arkscope-web/src/settings/SecDocumentReader.tsx:173`, `:221`, `:228`.
   Visit an index page containing a later section, select that section, then go to the preceding index page. Slicing section choices through the current index position removes the selected option, but leaves `section` and the passage query unchanged. The select displays its first option, Whole document, while the displayed passages and subsequent literal-search submissions still use the hidden section ID (`:108`). Real index pages split document/section entries, so this is reachable with the required long-directory workflow. Retain already observed choices independently of index position, or retain the selected section's labeled option explicitly. Add a regression asserting both the visible selection and outgoing filter after index Back.
   **Contract check:** `src/sec_research/document_queries.py:192` pages the combined document/section inventory; later pages can contain section choices absent from earlier pages.

#### Minor (Nice to Have)

- **[Quality, pre-existing diagnostic debt; not a Task 4 regression]** `task4-frontend-diagnostics.json:1`; `task4-precommit-frontend-02/output.log:17286`. The full run is not warning-free: ANSI-normalized comparison records exactly the same 1016 warnings as the sealed frontend-post-fix baseline, comprising 930 act-environment and 86 other act warnings across eight messages, with zero additions/removals. Track this existing test-environment debt separately; it does not justify enlarging this task or rejecting its added tests. The earlier raw-line counting method is not used here.

### Assessment

**Task quality:** Needs fixes.

**Reasoning:** The implementation is scoped and its principal HTTP, plaintext, citation, pagination, and focus paths have meaningful evidence. The three uncovered state transitions can still misrepresent acquisition status, the selected capture, or the active section; the passing parent browser and frontend gates do not cover these compositions.

### Checks And Boundaries

- Read the immutable diff exactly once, in three non-overlapping chunks. No changed source file was reread, no git command was run, and no source/index/branch mutation, suite rerun, subagent, installation, provider access, production access, or App restart occurred.
- Named outside-diff integration checks: Task 3 report for the HTTP contract; `DocumentQueries._open/read/_page` for primary-alias pin resolution and real index/section page boundaries. Read `vitest.config.ts` and `src/test/setupI18n.ts` solely to construct the isolated probe using existing initialization. Other reads were supplied requirements, reports, plan constraints, and archived gate evidence.
- One generated probe scenario only, using mocked fetch and the existing offline network guard. Its first invocation (`task4-review-pending-reopen-01`) failed before collecting tests because the scratch harness assumed app-local dependencies. Correcting only scratch imports to the existing workspace packages yielded the single assertion failure in `-02`; the first invocation is not product RED evidence. Both command/environment/output records are retained.
- Writes are limited to this requested report and generated probe/check artifacts under this plan's `.superpowers` directory. Parent owns all fixes, RED/GREEN follow-through, and remaining final gates.
