# SEC Document Reading Evidence

Worktree: `/tmp/arkscope-listing-sec-macro-convergence`.
Batch base: `3e98bda264e024b3aa03efafd0ba0abab9a19a5a`.
Plan: `docs/superpowers/plans/2026-09-12-sec-document-reading.md`.
This is the selected-document subsystem, not the complete SEC research release.

## Scope And State

- Task1 bounded directory/extraction/section core: reviewed through `b07eba2b`.
  Fixes for aliased inline hidden content, uncertain table-of-contents headings
  and case-sensitive XHTML namespace identity have named tests and inverses.
  Extraction version is `sec-document-text-v3`; public interfaces are unchanged.
- Task2 immutable document acquisition/stored passages: reviewed through `1f964efe`.
  Early-failure aliases invalidate current reads without authorizing dispatch;
  independently observed request counts are retained even if reports are invalid.
- Task3 HTTP: reviewed through `64a25c34`, with234 focused passes. Deliberate
  forbidden-access inverses now have clean failures and no teardown errors.
- Task4 Settings reader: reviewed through `02a0fff4`. A definite POST completion
  follows a reopened reader, equivalent primary aliases preserve the original
  pin, and index Back preserves the selected section and outgoing filter.
- All four task reviews and the integrated `final-review.md` are approved,
  zero remaining findings. Complete backend and exact reconciliation pass.
- Frozen-source frontend1776P/123files, typecheck/i18n and four actual-service
  browser compositions pass. Census is review_required, not a deletion list.

Task reports, immutable review diffs, review verdicts and `progress.md` retain
intermediate failures and decisions. No passing claim covers unfinished tasks.

## Verification Boundaries

All behavioral source bodies and databases are disposable generated fixtures.
The test runner isolates HOME/XDG/database/lock/token paths and denies production
file access and provider networking in Python; the Node guard denies outbound
TCP/DNS/UDP. These are runner guards, not an OS sandbox or general child-process
containment guarantee. Existing installed Python/Node/Playwright are reused.

Browser acceptance uses the real panel, API, Store/CaptureStore and acquisition
implementation; only source transport and the local preview host are synthetic.
It independently checks citation hashes and exact UTF-8 byte ranges against
stored objects. Screenshots and actual checks are recorded only after execution.

No production DB/config/token was read, no real issuer/provider request made,
no installed dependency changed, no production reset/drop/migration applied, and
no actual App restart, merge or push performed by this batch. Public SEC/XBRL technical
documentation references are recorded in `primary-source-notes.md`.

Baseline sealed verification was 8,823 collected backend nodes (8,811 passed,
12 skipped), and 1,738 frontend tests. Final collection and execution both contain
9180nodes: **9168passed /12unchangedskips**,357added/zero removed. The complete
single backend run took928.22seconds (runner wall931.828seconds). The additions
are169pure-parser,107store/service/query and81document-route cases. Final frontend
has1776passes,38added/zero removed. `verification-summary.json` binds every node,
unchanged skip identity,17current inverses and1102source/test hashes to the same
frozen tree (`02a0fff4`, product patchSHA
`c55d413b9ab97c565110e0ea81866a617783b1e0279e2b2280c3f5aaba9ad334`). Historical
checkpoints and inverse mutants are not counted as final-suite passes.

The current inverse manifest binds17 runs with63 intended failures to current
source/test hashes. Parent fixture preflight passed the real acquire/read/revision/
failed-refresh/pin sequence. `browser-final-fixed` runs the actual stored API in
English/zh-Hant at1280x960 and390x844: each84HTTP observations,13generatedmetadata
and10generateddocument dispatches,19exact citation checks, no page errors. The
reader includes opening focus/scroll and return-to-opener, long index navigation,
primary alias pin preservation, failed latest versus retained pin, known/unknown
POST outcomes and stale responses after closing. These are generated transport
fixtures, not external SEC acquisition. Original/canonical objects are excluded
from the archive; their generated bodies and full reproduction helpers are kept.

Full frontend warnings are not hidden: `frontend-fixed-diagnostics.json` compares
the exact normalized warning multiset to the sealed baseline,1016==1016 and no
new warning. Focused reader/API suites are warning-free. Current census
`census-final-fixed/reconciliation.json` records1133filesread/4346candidates/
3460uncertainties,4newcandidateIDs/166newuncertaintyIDs,0coverage/dependency/
untracked drift. `census-notes.md` gives consumers and remaining scanner owners;
raw records are unchanged, not filtered to manufacture a clean result.

## Retained Failed Checkpoints

- Task reviews and RED/inverse runs preserve all actual failures and fixes.
- `backend-full` was intentionally interrupted before Task4's review correction:
  5008passes/12skips are partial evidence only, never the final backend result.
- `final-collect-fixed` and `backend-final-fixed` omitted the explicit `tests`
  operand, unlike prior runs, so pytest collected historical evidence copies and
  stopped on8collection errors. No source/test expectation was changed; corrected
  complete scope is `final-collect-scoped` / `backend-final-scoped`.
- The first census launcher used an absent flattened baseline filename; the
  correct sealed baseline is `2026-09-11-sec-query-settings/census-post-fix/census.json.gz`.
- Initial browser helpers were adjusted to the new accessible row name and then
  extended for review compositions. Pre-fix failures remain labeled checkpoints.

## Remaining First-Release Work

Issuer resolution, three Research tools/four channels, Research citation trace,
portable export and scheduling remain separate work. SEC-RECOVERY-001 owns
explicit orphan cleanup with full reference recheck; SEC-RECOVERY-002 owns
operator schema reset/uninstall. Neither destructive operation is implemented
or authorized by this document-reading batch. Remaining project cleanup and
SQLite upgrade are also not claimed here.

## Reproduction And Publication

`backend-final-scoped/command.json`, `final-collect-scoped/command.json`,
`frontend-final-fixed/command.json`, `typecheck-final-fixed/command.json`,
`i18n-final-fixed/command.json` and `browser-final-fixed/command.json` record the
exact commands/environments. The runner helpers are archived with their source;
recreate an isolated scratch directory and reuse existing installed dependencies,
not a production profile. Test selection for the full backend is explicitly
`tests`, excluding historical evidence copies. `final-nodes.txt.gz` is the final
collected-node source, not the initial checkpoint.

`artifact-manifest.json` records archive/source SHA256 and source sizes. Logs,
JUnit XML, diffs and large JSON are gzip-compressed; generated databases, objects,
homes/caches and unrelated plan workspaces are excluded. `archive.py` and
`check_archive.py` retain the exact selection and Git-index byte-verification
procedure. The fixture Vite server and all subagents are stopped; the source
worktree/branch are retained. Only this plan's scratch is removed after archive
verification and commit. No merge or push is included.
