# Attended Confirmation With Source Gaps

This offline amendment implements the September 7 user decision: a complete,
source-supported LLM finding can reach explicit human confirmation when an
additional reference cannot be read. The human reviews the concise conclusion,
disclosed gaps and concrete effects; they do not redo the investigation or fill
missing evidence fields. Prior source-capacity and live-canary packets remain
immutable historical evidence. This packet does not declare the whole production
lifecycle workflow ready for hand testing.

## Product Contract

- Massive/EODHD remain the primary structured sources. Web/news and SEC evidence
  supplement unresolved questions; this amendment does not change that ordering.
- A failed supplementary read alone no longer disables every proposed action.
  Search and analysis must still finish, with at least one complete supporting
  source, exact cited passages, matching security identity, supported event and
  effective date. Actual unresolved conditions, contradictions, active/OTC vetoes,
  stale findings and changed effects remain blockers.
- The analysis prompt asks for a concise conclusion, decisive evidence and any
  action-changing uncertainty. It forbids citing or claiming to have reviewed
  unread material. This is prompt guidance plus structural checks, not a proof
  that an LLM's interpretation is infallible or unread material has no conflict.
- The host, not the LLM, records unread URLs and typed read-failure reasons.
  The same closed `{url, reason}` disclosure reaches UI and Research readback,
  action preview and the final confirmation. Links display only the hostname;
  their full admitted URL remains available in the link and hover title.
- The final dialog repeats the reviewed conclusion, the gaps and actual changes.
  No extra checkbox, evidence form or new manual investigation step is added.
  Only the existing action-specific human confirmation writes anything.
- The packet digest binds disclosure to evidence and exact effects. The writer
  independently compares the accepted disclosure to the validated journal.
  A nonempty disclosure also requires literal `acknowledge_source_gaps=true`,
  sent by the current final-confirmation action. An old client that ignores the
  new field cannot silently apply the action. This acknowledgment does not waive
  a material blocker or replace the digest. Replays stay idempotent.
- Old records without a URL map retain an explicit unknown URL for each recorded
  failure. Present malformed data is rejected, not treated as absent. Old
  findings can be reconsidered under this new policy, but still require a new
  explicit attended confirmation; they never become automatic authority.
- No schema, source/model budget, retry, fallback, deterministic authority or
  automatic application changes. The four existing provider/auth combinations
  share this policy; synthetic tests do not claim new live channel validation.

## Verification

`verification.json`, `node-changes.json` and the final `files.sha256.json` are
the measured admission record. `verify.py` reuses the entire previous affected
focus and integration lists, including the new Web tests. Each backend mutation
runs that whole focus; each frontend mutation runs the complete frontend suite.
Every mutation must fail its named owner with unchanged collected nodes, no
collection errors and restored source hashes. Baseline/restored, integration,
complete backend, typecheck/build/i18n and browser results are source-bound.

Final regression: 2,107 baseline/restored focus tests, 2,926 integration tests,
6,772 passed / 12 skipped in the complete backend, and 1,578 baseline/restored
frontend tests. The backend emits the same three edgartools deprecation warnings.
All 14 backend and ten frontend mutants fail their named owners, with the three
inner-field mutants also checked against their exact named parameter cases.
The source snapshot has 1,069 non-document files: 26 changed files and one new
test file relative to the prior capacity packet. Backend nodes increase by 70;
18 old node names are explicitly mapped to preserved/expanded or intentionally
replaced owners, with no unexplained deletion. Frontend nodes increase by 16,
with no prior node removed; all 1,578 current node identifiers are unique.

The 14 backend mutations cover unread-only eligibility, failure-URL handoff,
malformed/unsafe URL metadata, both public projections, independently bound
acceptance, absent/nonliteral acknowledgment, changed confirmation digest,
essential uncertainty, active OTC, no complete source and prompt semantics.
The ten frontend mutations cover result/dialog disclosure, reviewed summary,
runtime shape parsing, review projection, acknowledgment, neutral wording for an
unknown source-read reason, extra internal fields, raw error strings and unsafe
URLs. These are named regression owners, not exhaustive formal verification of
all possible findings.

The browser runner uses the actual UI with intercepted fixture APIs, never the
production App. Its 24 cases cover English/Traditional Chinese, 1440/390/320 px,
removal, rename, blocked findings and legacy missing URLs. All 42 screenshots
must be nonblank, with no overlap, clipping, overflow or runtime errors. A
fixture confirmation occurs exactly once after the final click, never before;
blocked cases issue none. No browser scenario starts a real investigation.

The old unread-only blocker test is deliberately replaced by the newly approved
contract. Existing essential-gap and shared-read owners are expanded to both
with-gap and no-gap controls, and the pipeline failure owner now covers all four
auth combinations. The node ledger maps every replaced node explicitly; no
unexplained test deletion is permitted.

## Historical Iterations

`historical-iterations` retains incremental RED/GREEN and preliminary suite logs;
they are not substituted for final source-bound admission. Initial backend RED
fails on the old blanket blocker and missing URL handoff. The old-client
confirmation RED demonstrates why a packet digest alone cannot ensure that an
older UI displayed a newly added field. A later RED catches an unfinished-run
lookup error in that new guard; the final code leaves incomplete runs subject to
the existing complete-finding requirement. Bilingual unknown-reason RED catches
wording that incorrectly called a complete investigation a failure. Compact-link
RED prevents a long URL from dominating the confirmation dialog.

Some preliminary frontend failures were fixture expectations: translated button
text, the newly explicit legacy-null field and exact vocabulary counts. Those
iterations remain recorded rather than being represented as final product
failures. The independent mutations and complete restored suites are the final
ownership evidence. The first browser pass used long visible URL paths; only the
third browser pass is final admission for the current source.

The first mutation campaign exposed a test-construction defect during the
sealer's independent unique-node check: Vitest unpacked array-valued `it.each`
rows, so nested malformed-gap cases actually passed an object to the outer list
validator. Two node labels also collided. The cases now use named object rows,
and three additional independent mutants require inner-field owners to fail.
The first backend campaign was stopped and restored before completing full
admission; the first frontend campaign is historical despite passing assertions.
Neither is substituted for the corrected, fully repeated campaigns. The stricter
unique-node check was retained, not bypassed.

## Scope And Remaining Work

No provider/LLM calls, production reads/writes, migration, App restart, commit,
merge or push are performed for this amendment. The prior 32 MiB encoded /
128 MiB decoded source-capacity measurements were not rerun here and are not
relabeled as measurements of this newer source snapshot. That memory, token and
source-selection policy is unchanged.

Maximum-size attended-write concurrency alongside a running investigation,
model-usage calibration, a separately authorized fresh live investigation,
authorized journal/population cutover and merge/hand testing remain distinct
steps. This decision removes the unresolved product-policy question about unread
supplements; it does not turn earlier all-source-read failures into a successful
live investigation. No complete supporting source still means no adoption.

Reproduce with `verify.py --help`, `run_browser.py --help` and `seal.py --help`.
Use fresh external staging/output directories. The sealer verifies the current
code, restored clone, full-suite node ledger, browser snapshot, unchanged schemas,
prior packet digests and synthetic-fixture-aware secret scan before publication.
