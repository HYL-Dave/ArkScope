# SDD ledger - plan: docs/superpowers/plans/2026-09-12-sec-research-release-integration.md

## Resume 2026-09-12

- Task 1: complete (2d54a482, 38529e51; existing reviewed evidence).
- Task 4: complete (ba5a3356, 5518ae21; existing reviewed evidence).
- Task 2: in progress. Original checkpoint ba4f2619 preserves all 57 paths
  from the dirty SEC worktree. Known historical RED: 4 OAuth failures/758 passed.
- Security base: 41682675 (product ff7c4d75), user-supplied Opus independent
  review reports 10166P/12S and complete split-secret/known-secret/public-data checks.
  This is attributed external review, not a new local execution.
- Integration replay: 3fef138d, on codex/sec-research-integration; source branches
  and master preserved. Five textual conflicts resolved out of nine overlapping
  files relative to common base 18d46062. SEC-specific redaction is not restored.
- Task 3, 5, 6, 7, 8: pending, not complete-release-ready.

## Integration progress

- 88f0512e: shared-policy integration, async OpenAI callback, common Anthropic
  guards, identical catalog/fact/document bytes, SEC-owned OAuth deadline.
- Runs: red-02 40F/38P, red-03 7F; green-02 1133P; timeout RED2F/8P and GREEN187P.
- Task2 read-only review dispatched to Mencius against immutable
  41682675..88f0512e and task2-review.diff; no full release claim.
- Ruling: independent C09 leaf cleanup can run before Tasks3/5/6/7. It changes
  no storage or SEC execution and the user explicitly requested remaining
  cleanup. No other product implementer runs concurrently; controller owns
  integration/index. If a live caller appears, retain and report that dependency.
- SQLite-only candidate build runs in isolated scratch; production remains
  unchanged. Python3.13 upgrade scope was asked of the user, not assumed.

## Pre-flight continuation rulings

| Tasks | Shared surface | Ruling |
| --- | --- | --- |
| 1/2 | ToolService/envelopes | Use existing service; no provider calls in checks |
| 2/security | Four bridges/registry/compression | Common result policy owns admission; remove historical SEC redactor |
| 2/3 | Tool result evidence/events | Keep full citations; durable Research pinning remains Task 3 |
| 3/5/6 | Durable references/export/recovery | Recovery cannot delete before current reference ownership is implemented |
| 4/2 | Document pagination/TOC | Completed document service retained; reverify adapters |
| 7/8 | Schedule/cleanup | No activation until release verification; no actual DB disposal |
| SQLite/all | Linked runtime and stores | Isolated candidate first; production baseline/activation are not inferred |

The original Task 2 redaction paragraph was superseded by the approved shared
output-boundary slice. Successful structured results are admitted unchanged;
credential-bearing/invalid structures receive typed rejection, not edited quotes.
Checkpoint commits are preservation artifacts and make no test-pass claim.
Offline runner source copied verbatim from tracked security evidence into this
plan's own scratch; it blocks production paths and outbound providers but is not
an OS sandbox. New runs use disposable data and synthetic secrets only.

## Review Repairs And C09

- Task2 reviewer reproduced native Anthropic nested-event-loop failure and
  governor-wait cancellation dispatch. New actual-producer/transport owners:
  12F before edits, 2F/233P after repairs (old fixture placement), then 994P.
  Exact result bytes survive the actual model tool-result roundtrip. Re-review
  required before acceptance; not an extension of previous security approval.
- C09 f30ee8fc preserves four unused source/factory deletions with 196P worker
  and controller verification. Mencius independently reviews that immutable
  change; worker is paused with restored files/no live mutant.
- SQLite candidate 3.53.4 privately built. Controller verified actual mapped
  library/source ID and reran the unchanged UPSERT script: all five pass.
  No runtime activation, Python minor upgrade, actual DB read or data deletion.
- SQLite application-storage verification: `sqlite-application-stores` 330P
  after candidate source-ID/mapped-library admission. Process-only override;
  production and Python minor choice unchanged.
- C09 worker closed before final supplemental inverses. Controller verified
  no C09 test processes and all possible mutated product/test paths match HEAD.
  Remaining inverses are not silently marked done; first restored-leaf inverse
  and the initial six intended RED failures remain recorded.
- C10 preflight/implementation delegated to Singer under the concrete
  2026-09-13 file-news cleanup plan; sole product writer after explicit GO.
- Task2 scoped re-review complete: 51P, no correctness findings. Only cosmetic
  EOF blank assigned to current worker. Full release and remaining Task8 gate
  still open; no whole-security re-review claim.
- C09 independent source review no findings. Controller completed remaining
  fault injections in-process: obsolete export / missing current export /
  wrong key precedence each caused exactly one named owner failure, then
  unmutated196P. No on-disk mutation or source restoration needed for these.

## Frozen Verification Checkpoint

- C10 `885c2a2d` deletes the whole orphan FileBackend, following the corrected
  consumer inventory. Worker350P/1S and controller467P/1S, no source/test edits
  after this checkpoint. Independent review assigned to Locke; full backend
  is running. Singer finished all sessions and was closed.
- C10 supplemental routing assertions remain on DAL._base; original 13-file
  baseline311P/1S, initial RED4F/2P, corrected absence RED2F/2P are separate
  receipts. Net original test nodes +1 (+2 absence, -1 dead protocol claim).
- Census at `885c2a2d`: 4345 candidates/3471 uncertainties, no new candidates,
  no dependency/untracked drift; five coverage reductions are exactly four C09
  source deletions and FileBackend. All34 added/34 removed SQL warning IDs have
  equal AST signatures at shifted locations, proven by reconcile_census.py.
  Underlying SQL uncertainty is not resolved and exit2 remains review_required.
- Task2 focused GREEN and independent review have passed, but its plan's
  explicit additional inverses still need receipts. Bohr owns process-local
  injections only, never changes source under the full-suite run.

- Task2 inverses completed: four inventories, generic truncation, missing worker
  join, removed subagent guard and removed required spec tool. Eight modes24F/
  25P, fresh unmutated union30P. All11 runs/worker sessions finished and closed.
- C10 independent review no findings,32P. First complete backend on885c2a2d:
  10277P/2F/12S; exact10291 collected/executed,123 added/10 removed since the
  sealed security run and identical12 skip IDs. All retained security owners ran.
- The two failures are our missed count collateral in lifecycle routes/tools:
  route224->223 and both OAuth inventories15->17. Named RED2F, then126P over
  four affected files. ae2055e3 corrects those tests, adds positive tool/negative
  old-entry checks and expands the plan inventory; product source unchanged.
- Full retry backend-full-reconciled runs on frozenae2055e3. Its before snapshot
  is source-before-reconciled-full.json. Never substitute aggregate results for
  this complete run. First attempt/midrun/after-first-full receipts stay intact.
- C11 exact plan prepared without source edits; old malformed-toggle blocking
  was newly acknowledged. SQLite/Python scope corrected:3.13 would also require
  reviewing numpy1.26.4 compatibility. SQLite-only admission need not wait for it.

- Ledger correction during sealing: final c09-report.md includes completed
  worker c09-resume inverses (three1F, three1P restorations,196P final), all
  predating controller's00:13 process-local replication and full runs. Earlier
  controller notes treated that final worker status as still partial; that was
  a missed handoff read, not an actual unfinished guard. Raw JUnit read back and
  possible mutant files match the frozen anchor. Preserve both independent sets.

## Verified Delivery Checkpoint

- The second complete backend run ended with10279P/12 unchanged S, zero failures,
  errors or warnings; exactly10291 collected/executed,123 added/10 removed and
  no duplicate nodes against the sealed security baseline. All ten automated
  checks in integration-validation.json are true, including retained credential,
  auth/tracing guards and new regression-suite execution. Before/after1130-file
  source collection, runner, packages and Python3.10.12/SQLite3.37.2 match.
- Full frontend1776P/123 files and typecheck exit0 were read back; no subsequent
  frontend source changes. Candidate SQLite3.53.4 application stores330P remain
  separate from full-suite runtime and production admission.
- Run accounting contains65 completed receipts,32 nonzero intermediate/RED/
  inverse/census/invocation results, no unfinished run folder. SQLite per-step
  commands have a separate ledger. Full-run failures are never replaced by a
  union of subsequent focused successes.
- The archive's unfinished-run guard was exercised before completion: it refused
  backend-full-reconciled and did not create checks/. Final publication selects
  reports/scripts/commands/logs/structured test and census results only, never
  fixture databases, credential fixtures, HOME trees or compiled binaries.
- C10/full verification is accepted within scope. C11 has only a concrete plan;
  SEC Tasks3/5/6/7/8, broader cleanup and runtime/data admission remain open.
  All controller/reviewer command sessions have completed; no live mutation,
  product/test change, main merge, provider call or production access followed.
