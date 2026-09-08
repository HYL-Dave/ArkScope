# Attended Web Write Concurrency

## Scope

Continue the approved September 7 source-gap policy and capacity work, using
temporary profiles and synthetic HTTPS/model replies only. No production data,
provider calls, credential reads, migration, App restart, merge or push.
Earlier sealed evidence remains immutable.

## Measured RED

`2026-09-07-lifecycle-attended-write-concurrency/measure_attended.py` executes the
real controller, heartbeat, reader, journal, human adoption and tracking writer.
One completed finding is confirmed while a second, unrelated ticker's worker
starts reading. Both use four full sources. The 1 MiB control passes.
At 128 MiB decoded per source, confirmation applies correctly but its two
consecutive write transactions take 43.071 and 30.865 seconds. The second
worker's heartbeat waits 45.526 seconds and fails; its first source INSERT also
times out. It retains zero sources and remains `reading_sources` after the
worker exits. Sampled child RSS is 1,905,016,832 bytes, below the 4 GiB benchmark
threshold. This is lock starvation, not excessive memory or a live provider
finding. Original reports and exact source manifests are retained separately.

## Repair Contract

1. Validate complete retained sources and the finding before entering the
   profile transaction. This is request-local work, not a persisted cache,
   automatic approval or model summary replacing source evidence.
2. Bind the resulting verified read to the exact profile, run/header, terminal
   model records, result, source index and SQLite schema generation. Recheck
   those bindings inside each atomic write, including the central writer.
   Page/result immutability triggers remain verified. Schema replacement during
   validation or before adoption invalidates the proof even if trigger names
   are restored; added sources and changed terminal state also invalidate it.
3. A verified read is internal and explicitly passed down the governed preview,
   approval and application calls. It never changes a caller-owned transaction,
   becomes a global cache or crosses requests. Existing direct connection reads
   keep their caller's atomicity. The ordinary structured-provider lane is
   unchanged. Missing proof uses the existing full-validation path, not a bypass.
4. Recheck mutable facts in the transaction: observation, source-specific
   membership effects, open holdings, positive active/OTC evidence, freshness,
   accepted disclosure, assessment authority and the exact human packet digest.
   No auto-retry, changed busy/lease budgets, relaxed source limits or new DDL.

## Owners And Admission

- RED owner: `test_attended_web_source_validation_leaves_other_profile_writers_available`,
  covering both source decoding and finding validation at prepare, confirm and
  scheduled execution. The positive control must actually commit another write
  and apply only the synthetic target.
- Add a real-worker contention owner, source/result/terminal/schema/profile
  binding controls, changed mutable state controls and request-local reuse
  controls. Keep the existing caller-transaction atomicity owner unchanged.
- Run independent mutations against the whole affected focused set, retaining
  named failures and source restoration, not just a single test file.
- Repeat small and maximum-source removal and rename workloads. Require both
  workers' full receipts, all eight retained sources, no SQL/heartbeat/poll
  failures, correct final memberships and the unchanged live-call count of zero.
- Full backend, frontend/typecheck/build/i18n and a source-bound evidence seal
  precede any new live-test request. The Linux RSS supervisor samples the child
  every 25 ms and aborts above 4 GiB; this is not a whole-App or OS hard-cap claim.

Model-usage calibration, a separately authorized fresh live canary and the
authorized production cutover remain subsequent gates.

## Measured Correction

The full decoded-source limit is repeated for both removal and rename, alongside
1 MiB controls. Both workers complete with four sources each and verified human
effects; no SQL, heartbeat or poll errors occur. Maximum-size confirmation takes
20.231 / 20.067 seconds. Its two write transactions take 0.771 / 0.379 seconds
for removal and 0.737 / 0.359 seconds for rename, without changing busy/lease
budgets. Peak child `ru_maxrss` is 1,909,919,744 / 1,910,161,408 bytes. The
measurement uses ordinary temporary disk storage and sparse relevant passages;
it is not a dense native-model context or whole-App memory certification.

Twenty-six new regression nodes include independent path/schema/source-race
controls, permission and mutable-state checks, actual concurrent writer commits,
another real controller/heartbeat worker, separate-command revalidation and the
generic review path. All 15 selected mutants fail their named owners across the
whole 2,133-node focus; the restored focus and 2,952-node integration pass.
Complete backend is 6,798 passed / 12 skipped / three existing warnings;
complete frontend is 1,578 passed. No earlier test node is removed. Exactly four
product files change relative to the previous source-gap seal, with this one
added test file; the larger worktree still contains earlier uncommitted work.
The full final campaigns, raw measurements, original RED and verifier/harness
corrections are bound by
`docs/superpowers/evidence/2026-09-07-lifecycle-attended-write-concurrency/`.
Its generated `verification.json` is the final admission record, not a claim
that interrupted campaigns finished.
