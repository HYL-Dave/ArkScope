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

## Resume 2026-09-13 At 7401e656

- Task 3: complete (899b4098..7401e656; independently reviewed, sealed archive;
  full backend10583P/12S, frontend1824P). Do not redispatch.
- Task 5: in progress; Task6 follows it. Tasks7/8 remain open.
- Existing isolated worktree clean at resume; master30bb31c7 unchanged. Parent
  offline runner hashes match the sealed citation runners. New receipt names
  begin task5-/task6-; never overwrite earlier run evidence.

| Tasks | Shared surface | Preflight finding |
| --- | --- | --- |
| 3/5 | Durable citation publication and retained roots | Task3 delivered actual event/message refs; operation lifetime must include commit, not only tool return |
| 5/6 | CaptureStore, schema, operations and CLI | Shared/exclusive operation coordination and verified backup precede deletion; writer flock alone covers neither reads nor put-to-publish |
| 5/7 | ResearchService and later scheduler | Schedule calls the protected service; no new scheduler job lock in Task5 |
| 5 internal | Export inventory and original DB | Derive object requirements from backup; normalize transients only in private backup |
| 6 internal | Mismatch reset and portable export | Mismatch backup is explicitly raw, not a canonical bundle; exact owned names only |
| SQLite/5/6 | Actual-store rollout | No real reset or runtime activation under offline implementation approval |

- Ruling: preserve the approved Task5-before-Task6 order. Opus's assertion that
  no prerequisites remain is incomplete: writer exclusion does not protect
  readers or metadata/citation publication. Cost if wrong: extra coordination
  overhead; lock owner tests must prove no redundant acquisition/deadlock.
- Ruling: this continuation executes existing approved implementation, not the
  production SQLite switch. The prior admission preflight has unresolved local
  selector/package/backup-window requirements; treating it as admitted would
  expose accumulated data. Cost: activation remains separate and explicit.

- Task5 baseline: task5-resume-baseline,214P/zero failures, completed. Parent
  offline runner equals latest archived runner SHA256.
- Task5 implementer Confucius (01a099eb-50c6-7d02-b68e-2dce06593dc6), base01ca7c58,
  owns all product/tests/index until handoff. No controller test/source writer
  runs concurrently. Task6 preflight is stored separately, not implementation.

- Task6 preflight Ruling: an existing valid profile with an entirely absent
  Research namespace is observed empty for operator maintenance; missing profile
  files or any partial/inconsistent Research root schema remain blocking. The
  live constructors create Research schema lazily, so requiring table creation
  during an observational preview would be unnecessary. Keep the strict Task3
  iterator unchanged for installed roots. Cost if wrong: mistaking partial state
  for empty could lose references; explicit absent/partial/corrupt controls must
  distinguish these states before any deletion is admitted.
- Task6 preflight: reset does not unlink capture files, so reset accounting must
  continue charging retained files as orphans rather than displaying zero usage.

- Task5 checkpoint edab0f9b: operation/read/publication/executor protection
  committed. Worker records7 intended initial RED, validation-order regression
 16F/625P then756P, stale-owner/direct-write RED3F then89P, terminal RED1F,
  outer-lease inverse5F and restored checkpoint1119P. Bundle GREEN19P is an
  initial focused result, not completed Task5 acceptance. Full report pending.
- Controller queried apparent runner overlap; worker records inverse exit before
  checkpoint start (16:50:42 receipt versus16:51:09 checkpoint output creation).
  No overlap established. Do not misclassify the partial log observed later as
  evidence of concurrent test processes.
- User asked to confirm app-private unchanged-Python SQLite deployment direction;
  no answer yet. This does not stop authorized SEC implementation or admit runtime
  installation/data access. Parent Task6 preflight remains ready for handoff.

- Controller Task5 findings sent before final handoff: operation admission outside
  existing Research terminalization can strand queued runs and abort legacy SSE;
  export/restore destination containment must reject writing beneath the source
  capture root/bundle, otherwise the operation invalidates its own source layout.
  Worker owns RED/fix/covering verification for both. Task5 is not accepted yet.

- Task5 implementer handed off c47a3808 (source1704ffc4), no live sessions;
  focused1390P, frontend99P/typecheck, with admission/overlap/stranded-WAL
  regressions and inverses. Bundle source checkpoint1d27394f. Independent task
  review dispatched on01ca7c58..c47a3808; no Task6 implementation before its gate.
- The worker force-added its scratch report; controller will first archive the
  final contents in docs evidence, then remove only the scratch report's tracked
  index entry. Preserve the private working copy and all Git history.

- Scratch report archival completed in1e3c2bfb, exact SHA256 matched before
  index-only removal; source/tests still match1704ffc4. No history rewrite.
- Task5 review1 (Einstein) found R1: non-busy closed admission failures still
  strand Research executions; R2: empty bundles lose file/directory distinctions.
  Controller inspected the handlers and member verifier and accepts both.
  Fix round1 dispatched to original implementer Confucius, FIX_BASE1e3c2bfb.
  Reviewer closed after report; no reviewer tests or simultaneous runners.
- Ruling: R3 pre-existing i18next debug noise is nonblocking and is not a reason
  to alter product logging or hide warnings. Prefer an isolated-run setting if
  already supported; otherwise retain raw logs. Cost: larger evidence, no lost
  diagnostic output. Keep security/probe visibility unchanged.
- Task5 source-only census baseline/current completed:4330/4335 candidates,
 3469/3495 uncertainties. Five candidates are four dynamic i18n leaves consumed
  by researchErrors.ts plus the explicit module CLI entrypoint. No coverage,
  dependency metadata or main untracked-name drift. Raw exit2 review_required
  remains; task5-census-reconciliation.json separates position-only changes.
- Task5 fix round1 committed4dfa0d37. Read-back RED22F/9P; focused checkpoint629P,
  UI104P/typecheck, two killed inverses restored. New admission owners exercise
  real unsupported/path/flock failure paths, scheduled execution and both SSE
  ASGI versions. No worker runner remains active.
- Task5 scoped re-review1 dispatched to Jason
  (01a09a3b-78b5-7c30-bc32-4ccd1441257e) on1e3c2bfb..4dfa0d37.
  Task6 still waits for this acceptance gate, not another implementation pass.
- Task 5: complete at4dfa0d37. Scoped re-review1 approved R1/R2 with no new
  Critical/Important defect; source and actual receipts read back. Reviewer and
  implementer closed after all runners ended. R3 remains nonblocking noise,
  explicitly retained rather than suppressed. Parent milestone/Task5 checks
  updated; full continuation acceptance remains after Task6.
- Task 6: implementation next, with approved brief and controller preflight
  (including external FK/case semantics, fresh profile snapshots and persistent
  charge reconciliation). No actual-store operation authorization is inferred.
- Task6 implementer Fermat (01a09a44-723b-7b83-9805-e8313f3c72ff), baseb49e09c4,
  owns the approved maintenance/admin/CLI product and tests. Controller owns
  disjoint operator documentation and final verification/archive tools. Sole
  offline test runner policy remains; no full backend before this task review.
- Controller read Task6 intermediate evidence: initial missing-interface RED42F
  in each of two retained runs; recovery RED1F demonstrates lost absent-file
  charge before directory sync; cleanup first GREEN attempt1F/23P catches
  unrelated-market-write invalidation, corrected cleanup24P; admin19P and
  integrated64P checkpoints follow. These are not final Task6 acceptance or a
  complete backend run. Worker owns subsequent hardening/inverses/report.
- Controller prepared maintenance_accounting.py and maintenance_verify_archive.py
  alongside the existing freeze/validation/census/seal helpers. Task5-only receipt
  inventory:44 completed,26 nonzero retained, no unclassified or unfinished run.
  Final Task6 accounting will classify new intermediate failures individually.
- Task6 worker checkpoint (uncommitted) requests unknown-schema safety-backup
  ruling; no active runner, final inverses/covering suite/commit still pending.
- Ruling: exact-digest-approved unknown-schema apply may create its explicitly
  disclosed raw DB/capture backup, then MUST remain blocked at backed_up with
  inspect_raw_backup recovery, never DROP or fall back to known-subset reset.
  This fulfills the approved concrete recovery path without treating unknown
  structures as removable. Strict fresh-state/path/lease/preview admission stays;
  reference findings never become empty or deletion approval, and ordinary
  known-schema reference refusal is unchanged. Missing/unsafe/stale admission
  cannot cause surprise backup. Cost if wrong: requested backup I/O/space, not
  source mutation. Only source/fixture implementation approved, no actual store.
- Correction to controller's early cause inference: unrelated-market-write RED
  was caused by Python3.10 set_authorizer(None) restoration leaving SQL denied,
  not a whole-file fingerprint binding. Pure :memory: probe under3.10.12/3.37.2
  independently returns SELECT1=1, None-reset SELECT2=DatabaseError(not authorized),
  permissive-callback SELECT3=3. Product restoration is on a fresh dedicated admin
  connection, not the caller's profile authorization. User update corrected.
- Controller pre-freeze finding: cleanup held the global market writer flock
  during full reference/file verification and the unlink/audit loop; reset's
  post-backup full observation held it too. This can block unrelated ingestion.
  Ruling: keep SEC-exclusive protection throughout, move long reads/FS work
  outside the market writer lock, use short mutation/reconciliation transactions.
  Fresh full post-backup observation remains under SEC exclusivity, with cheap
  write-point checks as necessary. No new generation framework or unlocked
  maintenance. Cost if wrong: lock-scope regression, covered by deterministic
  different-owner market-writer positive controls and DB-phase exclusion tests.
- Task6 implementer committed e495d664 after frozen covering1025P (110.53s),
  six killed behavioral inverses with exact restoration; no runner active.
  Initial skip-recheck01 helper aborted before applying mutation or invoking
  runner, with retained receipt; it is not counted as an inverse/test result.
  Controller read the covering command/log and clean git state. Independent
  Task6 review dispatched; task is not marked complete before that gate.
- Final frontend before task review:1829P/1F, single runner completed. Missed
  Task5 collateral in resources.test.ts still expects research224/total2974;
  both locales added12 actual maintenance/admission error leaves, requiring
 236/2986. No product error inferred. Original Task5 implementer resumed with
  sole test-file scope: fix exact counts only, retained full RED and focused
  GREEN required. Task6 immutable review source is unaffected.
- Task6 review1 (Hypatia) reports two Important findings at e495d664:
  output paths protect market sidecars but not separate profile sidecars;
  exception handling publishes failure audit after releasing SEC exclusion.
  Controller read the full report and named sites and accepts both. Reviewer
  closed, no tests run. Original implementer fix round1 follows the ongoing
  two-line frontend collateral handoff; no concurrent product writer.
- Task5 collateral3194de5e read back: exactly two constant substitutions,
  focused14P/0.830s. Worker report final, worker closed/no runners. Include this
  two-line collateral in next scoped re-review. Task6 fix round1 dispatched to
  Fermat at3194de5e; controller retains disjoint docs/evidence ownership only.
- Task6 fix1 RED29F/10P read back. Disposable separate-profile journal/backup
  collisions actually prevent later normal profile writes; failure-audit lease
  owners fail as expected. New code is not yet accepted. Initial six-inverse
  source readback is pinned to e495d664 to distinguish original exact restoration
  from legitimate subsequent fixes; all six/eight assertions verified.
- Task6 fix round1 committed78157e62. Controller read restored1064P covering
  receipt (112.61s), GREEN41P and profile24F/audit5F behavioral inverse results.
  Scoped re-review dispatched over e495d664..78157e62; includes the separate
  3194de5e two-count collateral. Full backend gate still waits for this verdict.
- Frontend final restored1830P/126files, typecheck/build/i18n passed serially.
  i18next diagnostic noise remains deliberately retained. Existing build warning
  also retained: baseline task4-final-build-03 bundle1193.45kB already exceeded
 500kB; current1196.23kB, no unrelated code-splitting or warning suppression.
  Pre-full receipt accounting89 completed/51 nonzero retained, no unclassified
  failures or unfinished runner output. Source-only census follows before the
  single backend full run; no simultaneous test session.
- Task6 fix round1 re-review (Plato) accepts R1/R2/C1 with no new breakage.
  Controller read complete report and source/receipt evidence. Reviewer and
  implementer closed; no active runner. Task 6: complete at78157e62, reviewed
  source implementation, actual-store rollout unperformed. Parent Task7/8 remain
  open; maintenance continuation's full offline regression is next, not a
  claim of complete SEC release or branch merge eligibility.
- Final source census4355 candidates/3543 uncertainties/1167read, exit2.
  New25 candidates are24 genuinely consumed locale leaves and operator __main__.
  Raw177 new uncertainty IDs separate into103 positional and74 new/changed;
  detailed adjudication retained. Coverage/dependency/main-untracked drift zero.

## Maintenance Continuation Acceptance

- Task5/6 source implementations: reviewed complete at78157e62. Parent Task7/8
  remain open; no whole-release, actual-store or merge approval is inferred.
- Single full backend runner completed task6-final-backend-full:10827P/12S,
  1320.185s. It ran alone; no test, census, frontend or source/doc mutation
  concurrent with this full run. All agents had been closed before collection.
- Exact reconciliation passes:10839 collected=executed, no duplicates,244 added
  and0 removed from the sealed citation baseline; the12 skip identities unchanged.
  Retained safety and maintenance/operation/citation owners all executed/passed.
  Before/after1151 source/test/resource paths, runner, SDK hooks, packages and
  Python3.10.12/SQLite3.37.2 match; source anchor78157e62, SHA256 collection
  93c470af219d947f4d25842ae942c9d9d3fa2d40649531cf6b5044e2ceae8c91.
- Final frontend1830P/126files, typecheck/build/i18n pass; earlier inventory
  failure and existing diagnostic/build warnings remain recorded, not suppressed.
- Final accounting92 completed run receipts/52 nonzero retained; no unclassified
  failure or unfinished run. Initial/fix inverse checkpoint readbacks remain
  distinct and verified; no restoration claim is made against the wrong anchor.
- Controller post-run helper invocation error: maintenance_freeze's output is a
  cwd-relative Path, unlike maintenance_validate's scratch-relative arguments.
  Passing task6-full-after.json wrote that own output at worktree root; the first
  validator call failed FileNotFoundError before writing a receipt. Moved the
  unchanged JSON into owned scratch with no-clobber mv; validation then passed.
  No product/test edit, ignored failure, reclassification or suite rerun.
- Docs now close SEC-RECOVERY-001/002 source work and explain actual-store
  admission, raw-backup-only unknown shapes, retained failure-audit lease and
  separate-profile sidecar protection. Selected evidence is sealed independently
  of fixture stores, HOME/credentials and compiled binaries. This workspace stays
  available for unfinished parent Tasks7/8; no staging of its scratch directory.
- SQLite private-runtime direction question has no user reply. No source selector,
  real DB/config/credential access, provider call, installation, actual cleanup/
  reset/export/restore, App restart, master merge or push in this continuation.
- Pre-commit packaging check found two verbatim brief EOF blank lines and92
  compressed run logs excluded by the existing *.log.* rule. Uncommitted first
  candidate preserved in own scratch; final sealer compresses those briefs
  losslessly and selected evidence logs are explicitly staged. No ignore-rule,
  product/test or raw receipt edits; see task6-seal-note.md.
