### Finding Verdicts

- **I1: Known POST completion cannot update a pending-close-reopened reader - ADDRESSED.** `apps/arkscope-web/src/settings/SecResearchPanel.tsx:153` now owns reactive per-filing uncertainty; `:349` uses functional Set updates retaining other filings. `apps/arkscope-web/src/settings/SecDocumentReader.tsx:48` consumes that state directly. Known completion/rejection clears it without bypassing the existing reading-generation guard (`:143`). Tests at `SecDocumentReader.test.tsx:244` cover complete, failed, and 403 responses after reopen, preserve the newer search, and assert no unsolicited GET. Adjacent controls retain genuinely lost outcomes and isolate concurrent filings.
- **I2: Primary alias silently drops the observed pin - ADDRESSED.** `apps/arkscope-web/src/settings/SecDocumentReader.tsx:202` resolves alias equivalence from observed capture metadata and checks filing/capture ownership before forwarding the pin. It preserves A across direct and uncaptured-secondary navigation without borrowing a captured nonprimary document's pin. Tests at `SecDocumentReader.test.tsx:289` cover all four A/B and A/failed-latest combinations, confirm explicit current still drops the pin, and include the nonprimary control.
- **I3: Index Back hides the selected section while retaining its filter - ADDRESSED.** `apps/arkscope-web/src/settings/SecDocumentReader.tsx:171` retains section choices from every loaded capture-bound index page, independently of index position. The existing capture-bound guard remains. `SecDocumentReader.test.tsx:344` asserts actual select value/label, retained passages, exact section/search/cursor/capture operands, cached navigation, and explicit whole-document clearing.

### New Breakage in the Fix Diff

- None identified. The three-file delta changes uncertainty ownership, observed alias matching, and loaded section-option retention without changing HTTP contracts or overriding stale-reading suppression. The added tests assert user-visible state and outgoing requests rather than only internal state.

### Out-of-Scope Observations

- None newly identified. Previously recorded full-frontend React act warning debt remains reported; this rereview does not reopen it or claim the full run is pristine.

### Checks

- Reviewed the Fix Round1 report delta and immutable `task-4-fix-r1-diff.txt` exactly once, base `f53a87a4`, head `02a0fff4`. Inspection was limited to I1/I2/I3 and the three changed files, under the existing brief and Global Constraints.
- Read archived RED output: `task4-fix1-red-all-01/output.log` records the intended three I1, four I2, and one I3 failures, with 27 passing cases. No import failure substitutes for behavioral RED.
- Read archived GREEN output: `task4-fix1-green-all-01/output.log` records 83 passes across four files, including all 35 reader cases; no stderr/warning matches in that focused log. `task4-fix1-precommit-frontend-01/output.log` records 1776 passes across 123 files, matching 1765 plus 11 new cases. Typecheck and i18n command records both show exit 0.
- No tests/probes or suites rerun, no git commands, no changed source rereads, no product/index/branch edits, no subagents, and no provider/production access. Only this requested rereview artifact was written.
- Parent's independent actual-store composition RED reproduced I3 on old source. The completed `parent-reader-browser-fixed` command/output records four successful locale/viewport combinations, 84 HTTP observations each, and no page errors. Parent confirms unchanged `02a0fff4` covered I1 held definite-failed POST across close/reopen, I2 original-pin aliases against new/failed latest including missing-secondary navigation, and I3 visible section plus outgoing filter after index Back. This supplements the scoped inspection; remaining final backend/census/whole-change gates remain parent-owned and are not claimed complete here.

### Verdict

**Fix round:** All findings addressed, no new Critical/Important breakage. Scoped round1 approved; parent integration and final gates remain separate.
