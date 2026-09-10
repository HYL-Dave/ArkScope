# SEC Retention Inventory And Helper Cleanup

Branch: `codex/listing-sec-macro-convergence`. Plan base: `6ba563d9`;
plan commit: `8c8ac738`. This checkpoint is separate from the previously
completed [entrypoint cleanup](../sec-entrypoint-cleanup/README.md).

## Authorized Inventory: Unavailable, Not Empty

The user authorized one structure/count/reference-only inspection of the exact
production profile and market databases. No credential, URL, source body, model
prose, unrelated setting value or whole-row hash was authorized. No production
write, backup copying private content, provider call, restart or integration was
performed.

The reviewed inspector uses SQLite read-only URIs, `query_only`, a read
transaction and a column/table authorizer. The caller additionally makes the
entire filesystem read-only with `bwrap`, except the plan's output scratch, and
isolates networking. It does not use `immutable=1` to bypass live WAL data.
SQLite's read-only flags alone do not promise a nonwritable WAL coordination
surface. [SQLite WAL documentation](https://www.sqlite.org/wal.html)

The single production attempt failed during `ATTACH`, before `BEGIN` and any
schema/count/reference query, with `sqlite3.OperationalError: unable to open
database file`. No inventory JSON was created. The recorded result is
`unavailable_before_inventory`, not a fabricated zero-count manifest. No retry,
checkpoint, write-mode fallback, main-file-only copy or unprotected read followed.

Subsequent **file metadata only** showed absent profile WAL/SHM sidecars and an
empty market WAL with a present SHM. A synthetic closed WAL database without
sidecars reproduces the same error under the read-only filesystem view, while
an open synthetic writer's uncheckpointed row is correctly observed when its
sidecars already exist. This supports a WAL initialization explanation; it does
not identify which exact production file SQLite could not open. Both synthetic
cases assert unchanged main/sidecar bytes. The production databases were not
opened again to diagnose this further.

**No production row count, table-absence claim, accepted-reference closure or
safe-to-delete conclusion can be drawn from this attempt.** Any actual disposal
still requires a usable authorized snapshot/read, a retention manifest, backup
and explicit digest-bound approval. The source-cleanup tasks do not depend on
that data-disposal approval.

Exact production invocation, from the linked worktree:

```sh
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 /usr/bin/bwrap --ro-bind / / --bind /tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup /tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup --unshare-net --die-with-parent /home/hyl/.virtualenvs/llm_app/bin/python -B /tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/inventory.py /tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/production-inventory.json
```

The attempted query SHA-256 was
`f851057861c55980d4aeb114a8cf230ca7203ad1f3f2d86ca905004f833627c5`, matching the
independent scoped review. The inspector is archived as text, not installed as
another product/operator command. Its body was unchanged after that review.

## Synthetic Privacy And Reference Checks

- Initial RED: 12 failed because the inspector did not yet exist; first green:
  12 passed.
- Independent pre-read review found two real issues: read-only SQLite did not
  prove nonwritable coordination files, and ordinary mixed-affinity equality
  did not reproduce FK matching. Added synthetic tests failed 3/passed 16 before
  correction, then passed 19. Scoped independent re-review also passed all 19.
- FK matching now compares `parent = +child`, preserving the parent's affinity
  and collation, with TEXT/INTEGER and NOCASE controls checked against SQLite's
  `foreign_key_check`. Composite, nullable and external FK cases are covered.
  [SQLite foreign keys](https://www.sqlite.org/foreignkeys.html),
  [expression affinity](https://www.sqlite.org/datatype3.html)
- Exact legacy schedule/runtime key counts do not read mixed-owner payloads.
  Credential, header/body, translated-text and unrelated setting/job payload
  queries are rejected. Unknown schemas remain unavailable, not zero.
- After the refused production attempt, the additional closed-WAL fixture
  brought the final synthetic result to **20 passed**, no skips. This is local
  query-harness verification, not product backend test-count growth and not a
  successful production inventory.

The authorizer log records allowed query-column access, not a physical-page
read audit. Declared FK aggregates do not prove every application-level retained
reference is covered. Cross-store observations are not claimed to be an atomic
two-database snapshot.

## Source Tasks

Task2 (`5d41f570`) moves the exact existing journal encoding/digest implementation
to `src.lifecycle_journal_codec`. Current and retained history readers use the
neutral owner directly; no historical serialized bytes or schema are changed.
The task's independent spec/quality review passed. Its minor negative-owner
coverage gap was fixed in `58e1929b`: aliases/forwarding definitions and legacy
imports/references are now rejected by named tests. Original tests passed both
alias/import mutants; revised tests failed the intended 3/3/4/4 cases for four
mutants and passed 43 after restoration. The parent also freshly passed all 43
on the actual tree. Scoped re-review found M1 fixed with no open findings.
The task's broader pre-fix regression passed 349, with all 308 original nodes
retained and 41 additions; M1 adds two more nodes without deleting any.
The separator mutation's context patch is gzip-compressed without byte edits:
blank diff-context lines contain required leading spaces, which otherwise look
like new-file trailing whitespace to `git diff --check`.

Task3 (`0c5896a5`) removes exactly five obsolete HTTP entries: case audit, old
review detail, evidence translation, case-scoped automation and old confirmation
readback. The measured App inventory is 221 -> 216, with no other added/removed
route. The old translation orchestrator, adapter and exclusive store methods
are physically gone. Current tool review, provider confirmation, tracking
history, global automation, acknowledgement/reversal and normal card/content
translation remain.

Scoped tests: baseline 975 passed; RED 5 failed/1 passed; intermediate 6 passed/2
failed at the old count/surface owners; final and mutation-restored 962 passed.
Restoring the old confirmation registration makes the named absence owner fail.
The 24 removed/11 added IDs comprise six preserved-owner renames, 18 obsolete-only
removals and five new route-absence tests. Receipt/privacy/provenance assertions
were transferred, not discarded. The stored-translation tool projection test now
seeds its historical row directly and retains all original assertions.

Initial Task3 review passed. A subsequent scoped review found a four-line
`TickerIdentityService.get_review_confirmation` facade whose only runtime caller
was one of those deleted routes. Follow-up `e61accaf` deletes it and moves six
test calls to the live `_result` reader without changing any existing assertion
or test ID. `_result` and `confirmation_for` are unchanged.

The added absence owner fails before removal and when the original facade is
restored. All ten complete affected suites pass **293 tests** both before and
after the mutation check. The initial baseline command had 292 fixture setup
errors because the nested scratch basetemp parent was missing; creating that
parent gives the unchanged 292-pass baseline. That harness failure is archived
separately and is not product RED. This later fix is not covered by the earlier
whole-run result below. Scoped re-review passed both spec and quality, confirmed
all six original test ASTs after only call substitutions, and found no new issue.

## Backend Verification And Census

At frozen `0c5896a5`, the entire backend completed in 742.764 seconds:
**7,971 passed / 12 skipped**, no failures/errors, all **7,983 unique collected
IDs** accounted for in JUnit. Against the prior 7,953-node final baseline:
54 additions and 24 removals, net +30. `verification-summary.json` names every
addition/removal and skip. The codec adds 43 nodes; Task3 adds 11/removes 24.
No provider/live tests were enabled. The clean-environment runner isolates
HOME/stores and blocks production access/provider traffic; it is not an OS
sandbox or a claim that mocks validate provider behavior.

The census at this same head exits **2 / review_required**, not clean. It reads
1,097 files and emits 4,324 candidate rows/3,387 uncertainty rows. Against the
original baseline, 197 new unique candidate IDs comprise 88 CSS, 100 i18n and
nine SQL table/column candidates; there are 264 new uncertainty IDs and 32
coverage reductions. No dependency metadata or main-worktree untracked-name
drift is reported. Raw repeated row IDs are not counted as unique candidates.

The five HTTP candidates from the previous phase are gone. The nine new SQL
candidates concern retained historical evidence translations, not abandoned
data. The actual `list_evidence` reader joins translations to their evidence ID
and content digest. The scanner's synthetic union schema lacks
`security_lifecycle_evidence`, so its EXPLAIN fails before observing that JOIN.
A source-only in-memory probe reproduced this exact missing-table error. The
retained tool test owns provenance and exclusion of translated text from the
model-facing projection. Keep these records; queue scanner schema-completeness
under C21, not a schema DROP. `census-interpretation.json` records this limit;
the raw report and original baseline remain unchanged.

Final collection at `e61accaf`: **7,984 tests**, exactly one added absence owner,
no removed/renamed IDs since the full run. `post-facade-accounting.json` verifies
both changed test files were completely rerun and every final ID has a result:
293 IDs from the fix rerun, 7,691 from the unchanged full-run selection. The
combined unique outcome is 7,972 passed/12 skipped; this is **not** a second
whole-suite execution on `e61accaf` and not 7,971 + 293 tests.

The final census at `e61accaf` still reads 1,097 source files, with the same 4,324
candidate rows/3,387 uncertainty rows and identical candidate IDs. Its original
baseline comparison has 266 new uncertainty IDs instead of 264: the facade's
five-line removal shifts two unchanged SQL sites from 234/393 to 229/388. Raw
comparison is retained; no baseline or uncertainty suppression was performed.
All 32 coverage reductions, 197 new candidate IDs and dependency/untracked
metadata conclusions above remain unchanged.

## Decisions And Remaining Boundary

- Remove translation execution after its last runtime caller, retaining current
  card translation and historical data. If a real omitted consumer is found,
  restore only the required capability; no data was discarded by this decision.
- Add negative codec ownership tests now. The cost is stricter tests requiring
  explicit revision if a future design intentionally reintroduces that owner.
- Let the unrelated route task start while the codec's test-only M1 re-review
  finished. Final acceptance still requires that re-review; it passed. An adverse
  result would have required rechecking dependent work, not bypassing the gate.
- Delete the receipt facade left tests-only by the removed HTTP entry. The real
  receipt reader remains; a genuinely missed consumer would require restoring
  its interface, not undoing data changes.

Next data work requires an authorized usable read, an exact retention manifest
and separately approved backup/disposition. The WAL/SHM coordination question
remains unanswered; the ignored plan workspace is retained for that handoff.
Current shared journal/review/history guards and the other C01-C21 queues are
still named in `sec-schema-ownership.md` and the main audit. No schema cleanup
or new research capability is represented as completed here.

## Frontend Verification

No frontend source/package change is made by this plan. At code checkpoint
`5d41f570`, the whole frontend passed **1,692 tests / 119 files**, typecheck and
production build exited 0. Test identities and the 112 stderr-bearing cases are
identical to the earlier `task4-verified-frontend.xml.gz` final artifact. Existing
React act warnings remain; the main JS bundle remains 1,155.31 kB with the
unchanged 500 kB warning threshold. These are not silently classified as clean
output. `frontend-checks.json` records commands and the baseline reconciliation.

The current three-tool SEC research service, canonical schema conversion and
wider C01-C21 cleanup are **not** implemented by this checkpoint.
