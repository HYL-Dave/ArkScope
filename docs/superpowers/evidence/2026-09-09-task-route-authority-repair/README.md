# Four-Task Route Authority Repair Evidence

Status: final fix wave implemented at `20a77373`; full suites pass, but scoped
re-review is NOT APPROVED because one P2 cold-restoration regression remains.
Not ready to merge. Historical and post-fix evidence are separated below.
This record does not authorize merge, push, an App restart, provider calls,
or production-store access.

## Scope And Authority

- Base: `fb12f27e92c182ae5ff425595a4e9d2f947d601d`.
- Branch: `codex/task-route-authority`, isolated worktree
  `/tmp/arkscope-task-route-authority`.
- Four tasks: `card_synthesis`, `card_translation`, `ai_research`,
  `lifecycle_investigation`.
- A supported selected provider/model/effort/auth tuple is bound once for an
  execution. A failed selected credential does not authorize a replacement key,
  model, effort, transport, or billing source.
- Existing capability, retirement, Spark exact-entitlement and Fable OAuth
  admission remain authoritative. This repair does not make unsupported choices
  available or certify every provider/model combination live.
- An execution receipt describes ArkScope's sent selection. It is not a claim
  that every provider independently attested its actual model. Existing
  transport-specific response checks remain in place.

## Evidence Boundaries

Backend tests use the existing offline wrapper, a new network namespace with only
loopback, and synthetic stores/credentials. No production configuration was
copied into the worktree. Checkout used command-local git-crypt smudge disabling;
encrypted files remained encrypted. Existing dependencies were reused without
installation.

Cached translations do not dispatch. Explicit retranslation creates a new saved
version and receipt only on success. A failed refresh leaves the prior version
intact. Old generation rows retain their stored provider/model; missing fields
remain unknown. Legacy translations do not acquire current Settings metadata.
An empty-prose no-op has no execution receipt and creates no translation version.

## Completed Task Checks

| Task | Commits | Verified result |
| --- | --- | --- |
| Runtime route/auth binding | `f788ef28`, `67c4fcff`, `af3f06c4` | 837 focused tests; original reviewer wire repro 1 passed; independent fix review accepts both P1 findings. |
| Card receipts and explicit refresh | `84ff0cd3` | 720 focused tests, including 42 new cases; independent task review accepts implementation. |
| UI selection and provenance | `c5146a9a` | 149 focused / 1,739 full frontend tests; typecheck/build; 64 synthetic browser screenshots; independent task review approved. |
| Integrated verification before final fixes | `090a7225` | 7,537 backend passed / 12 skipped; 1,739 frontend passed; typecheck/build passed; six mutations killed and restored; final review found two uncovered cases below. |

[Whole-branch review](whole-branch-review.md) found a remaining structured
refusal-metadata redaction gap (P1) and loss of current-conversation overrides
on ordinary App navigation (P2). The final fix wave is `86eb79cf`, `6bbb36cd`,
and `20a77373`; its implementation and focused checks are recorded in
[final fix implementation](final-fix-implementation.md). The
[scoped re-review](final-fix-review.md) accepts P1 and the warm-navigation/
caption repairs but finds the cold-restoration regression below. The earlier
suite and mutation results are not evidence that those cases were covered.

Task 1 RED evidence includes route/auth mutation failures and 10 failures against
real SDK tracing before the sensitive-data control. Task 2 includes a restored
OAuth token-store forwarding mutation that killed four named dispatch cases.
These task-level checks are not substitutes for the final integrated results.

Detailed records: [runtime implementation](runtime-implementation.md),
[initial runtime review](runtime-initial-review.md),
[runtime fix review](runtime-fix-review.md),
[card implementation](cards-implementation.md), [card review](cards-review.md),
[UI implementation](ui-implementation.md), and [UI review](ui-review.md).
These retain original commands and task-workspace references as historical
records. The card implementation report was moved out of tracked scratch without
rewriting its contents. All acceptance and final-review results below must refer
to the final restored code, not just these intermediate reports.

The initial whole-backend run found one obsolete test requiring custom Anthropic
effort to be silently omitted: 1 failed / 7,535 passed / 12 skipped / 3 existing
edgar warnings, 814.94s. The required correction updates that old contract owner,
not the approved runtime behavior. The test-only correction `090a7225` retains
the supported-model control and adds a distinct real-registry no-effort control;
its five-file focused set passed 289 tests. See
[integration correction](integration-test-correction.md). Final whole-backend
post-correction verification passed 7,537 tests / 12 skipped / 3 existing edgar
deprecation warnings in 818.88s. No new skip or runtime workaround was added.

[Pre-final-fix verification record](verification-results.json) contains reproduction commands,
JUnit digests and parsed totals, execution boundaries and changed-code hashes
at `090a7225`. Runtime code remained unchanged after mutant restoration.

## Pre-Final-Fix Mutation Checks

All six mutations ran sequentially after workers/reviewers stopped. The baseline
was 1,415 backend tests (59.80s) and 149 frontend tests (2.82s), with no failures,
skips or deselections. Each mutation used its whole relevant focused set, not
only the test file containing its anticipated owner.

| Temporary regression | Failed / passed | Representative owner |
| --- | --- | --- |
| Route-store failure becomes absent/default | 7 / 1408 | `test_task_route_read_failure_never_substitutes_yaml`, all four task IDs |
| Translation re-reads effort after capture | 13 / 1402 | `test_api_fixed_dispatch_pins_complete_selection`, both providers and both auth modes |
| SDK client reselects active key | 22 / 1393 | `test_research_captures_key_before_persistence_and_scheduling`, both providers at three handoff points |
| Cached receipt borrows current Settings | 9 / 1406 | `test_legacy_unknown_cache_never_reads_settings_or_auth` and eight fixed-dispatch/cache cases |
| Card UI forces Anthropic | 2 / 147 | AICard request assertions in localization and in-flight preservation tests |
| Research defaults to fixed Luna | 25 / 124 | Both providers' Settings-route send tests and resolver precedence tests |

The cache mutation additionally caused one teardown error on the same legacy
no-read owner. It is disclosed, not counted as another independent test owner.
All mutants caused actual assertions to fail, and each was restored with the
exact inverse patch. `git diff --quiet -- src tests apps/arkscope-web` returned
zero after every restoration. No mutation was committed.

[Machine-readable mutation record](mutation-results.json) contains exact source
changes, commands, XML hashes, and every named failure. Post-restoration full
frontend verification passed 1,739 tests / 125 files in 12.03s. Typecheck passed
without diagnostics. The production build passed in 2.75s; its existing Vite
large-chunk warning remains disclosed, not suppressed.

[Browser observation record](browser-results.json) binds the synthetic result
and all 64 screenshots by SHA-256. Each locale/viewport context made 38 mocked
requests; all four contexts have empty error and layout-overflow collections.
The actual screenshots remain under `tmp/task-3-ui` in this worktree. They are
not production screenshots or evidence of a provider execution.

## Post-Fix Checks

At `20a77373`, the restored baseline passes 1,469 backend focused tests and
214 frontend focused tests. All nine mutations ran sequentially without active
workers/reviewers reading temporary changes. Every exact inverse restoration
returned a clean runtime/test/UI diff before the next mutation.

| Temporary regression | Failed / passed |
| --- | --- |
| Route-store failure becomes absent/default | 7 / 1462 |
| Translation re-reads effort after capture | 13 / 1456 |
| SDK client reselects active key | 49 / 1420 |
| Cached receipt borrows current Settings | 9 / 1460 |
| Card UI forces Anthropic | 2 / 212 |
| Research defaults to fixed Luna | 39 / 175 |
| Refusal details retain raw provider text | 24 / 1445 |
| App omits its conversation-selection ref | 38 / 176 |
| Incomplete edit displays stale route captions | 8 / 206 |

The cache mutant again has one teardown error on the same legacy no-read owner,
not a second independent failure. The
[post-fix mutation record](post-fix-mutation-results.json) preserves exact
commands, patches, all owner names and JUnit hashes. No mutation survived or
was committed.

Fresh whole backend: 7,591 passed / 12 skipped / three existing edgar warnings
in 937.82s. Fresh whole frontend: 1,781 passed / 125 files in 11.82s. Typecheck
passes without diagnostics; build passes in 4.71s with the existing Vite
chunk-size warning. The [post-fix verification record](post-fix-verification-results.json)
binds parsed JUnit totals/digests, reproduction commands and all 44 changed code
file hashes. The scoped re-review is complete, NOT APPROVED: passing existing
tests do not negate the missed cold path below. Its report was finalized before
backend completion and is preserved verbatim, including that historical status.

The [final-fix browser record](final-fix-browser-results.json) binds 96 synthetic
screenshots: 12 scenes across both Settings providers, both locales and desktop/
mobile widths. Each of eight contexts submits five exact synthetic Research
requests, with no incomplete-selection submission, recorded error or layout
overflow. The real App navigation mounts/unmounts Research. Actual images remain
in `tmp/final-fix/browser-caption-verified`. The initial 64 and intermediate 72
image sets remain separate; the intermediate set is not final caption acceptance.
No provider or production App was used.

## Remaining Merge Blocker

On a cold App mount, session storage may identify an existing conversation but
the App-owned selection ref is still null. If the catalog loads first and the
user edits a model before history arrives, `rememberConversation` writes a
known-blank conversation and clears the saved thread association. The initial
history callback then deliberately skips restoration. Even after history
finishes loading, the next submission uses a new thread rather than the saved
one. Old threads/messages are not deleted, but the intended research context
is lost for that next execution.

The reviewer reproduced both edit and no-edit cases in the real App under the
offline wrapper. The report-local diagnostic intentionally asserts observed
behavior; its pass proves the regression, not a fix. Warm-remount tests and
browser scenes do not cover this saved-ID-only cold path.

Required follow-up: distinguish unresolved restoration from an explicit New
conversation, preserve the saved target across picker edits, and block Send
until that target resolves. Retain intentional New/delete-current reset and
same-conversation complete/incomplete choice preservation. The user has been
asked to approve this bounded correction. No second fix wave has been started.

## Rulings Made During Implementation

Native OpenAI main/child SDK runs now explicitly exclude sensitive provider
payloads from SDK tracing. Inspection showed this tracing defaulted to enabled,
including raw provider exception text before application redaction. Disabling
the sensitive payloads is necessary for the approved secret-free execution
contract. Ordinary trace metadata and ArkScope results/history remain available.
The cost is losing raw prompt/response bodies and the SDK trace response ID that
the SDK derives from the suppressed response object. Application response IDs
and results are not removed. Ten tests use an enabled in-memory SDK trace
processor, with both failure and success controls and no backend export.

During an incomplete explicit model edit, the old resolved route's auth/quota
and blocked-reason captions are hidden until effort is supplied. The inspected
mobile view otherwise selected OpenAI while still labeling the prior Claude
subscription. The cost is temporarily losing those auxiliary previews; correct
provider buttons, the pending model, the effort-required warning and disabled
Send remain. Completing the tuple restores the new route's real captions and
reason. This changes presentation, not execution admission.

The cold-restoration finding is accepted and remains open, not parked as
harmless. Merge readiness is withheld because routing a question without its
intended conversation context violates the task. The cost is a further bounded
UI correction before integration; this is not a claim of destructive data loss.

## Separate Pre-Existing Issues

- `IBKR-EVENTKIT-IMPORT-LOOP`: an alternate focused file order leaves no current
  asyncio loop before `ib_insync` imports `eventkit`. The same two lifecycle
  route-enumeration tests failed on an immutable export of Task 2 base
  `1284c28e`: 2 failed / 188 passed. This comparison establishes that Task 2 did
  not introduce the import-order failure; it does not claim the failure is fixed.
  A second comparison at original branch base `fb12f27e` reproduces the same
  family in standalone `tests/test_events.py`: 20 passed / 1 SSE setup error
  (`TestSSEEndpoint::test_stream_bad_provider`), 3.33s. Thus it also predates
  the entire branch.
  No tests were skipped or production import-order workarounds added.
- `OPENAI-RESEARCH-COMPACTION-SDK-COMPATIBILITY`: the existing zero-argument
  compaction-session factory is incompatible with the installed SDK constructor
  and is caught/disabled. Compaction defaults off. This separate issue is not
  repaired or enabled in this route-authority change.

Both follow-ups are recorded in `docs/design/PROJECT_PRIORITY_MAP.md`.

## Handoff

The operator sequence is in
`docs/superpowers/plans/2026-09-09-task-route-authority-hand-test.md`.
Use it only after separate merge approval and a manual App restart. This branch
has not changed the running production App.
