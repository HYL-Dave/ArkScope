# SDD ledger - plan: docs/superpowers/plans/2026-09-11-sec-durable-acquisition.md

Base 737f438d; linked worktree verified; no existing changes.

| Tasks | Shared interface / self-consistency | Preflight result |
|---|---|---|
| 1 | schema/store/tests, immutable source metadata | exact DDL and fresh/populated tests agree |
| 2 | captures/lock/tests, quota versus object accounting | stage+remaining counted once; recovery owns file lock |
| 3 | service/tests, raw acquisition and saved receipts | incomplete stays incomplete; no tool exposure |
| 4 | HTTP commands/tests, explicit writes versus pure reads | permission check precedes construction; no startup writes |
| 5 | verification/evidence/docs | fresh counts required, first-release gaps explicit |
| 1 + 2 | schema owns three capture tables; captures uses Store.connect | identical columns; no separate capture DB |
| 1 + 3 | Store.publish/record_receipt/latest_receipt | same signatures; receipt JSON lists preserve pending locators |
| 2 + 3 | CaptureStore.preflight/put/read | preflight before network, put after response; no lock held across network |
| 3 + 4 | ResearchService.refresh/stored | explicit CIK until issuer-resolution task; bounds validated twice |
| 4 + 5 | priority map and issue register | parent is sole editor; update after verification |

Ruling: parent implements Task 2's capture critical path; fresh worker implements
independent Task 1 with the shared table contract. Task 3 can start against these
interfaces while parent integrates routes after its return. No model override.

Ruling: fixed metadata publication bounds are admission limits with typed errors,
not fabricated whole-application storage guarantees. Future export uses existing
backup_market_db; no third backup primitive in this plan.

Task 1: complete - 5f50ff1a, task1-rereview approves clock-order fix; 48 owners.
Task 2: complete - e192374a, task2-rereview approves R1-R4; 35 owners.
Task 3: complete - 87f316c0, task34-review approves service; 47 owners.
Task 4: complete - 8070d4fc, task34-rereview approves GET consumer; 12 owners.
Task 5: verification/reviews complete; archive publication/readback next.
Fresh final8434P/12unchangedS/850.34s. Exact8446 collection/execution,142added,
zero removed,794 source/test paths stable. Initial four failures accounted below.

Task 1 implementation returned 44P / 348 focused; review requested receipt
ordering by append ID (clock rollback must not resurrect old successful receipt).
Worker fixed owned files; task1-rereview subsequently approved.
Task 3 implementation returned 47P / 439 expanded; checkpoint, partial-state,
preflight and issuer-exclusion inverse probes caught. Integration review approved.

Task 2 review round 1: R1-R4 accepted. Actual RED8F/22P then final35P. R1 fsync
parent ancestry including retries; R2 trusted external coordination namespace
(explicit operator boundary, no arbitrary-local-mutator security claim); R3
one-statement status snapshot plus actual conversion-interleaving test; R4 closed
I/O/disk errors and partial-write/post-commit preservation. Scoped review approved.

Source frozen: 794 source/test paths, patch SHA256
452c30f1111a28a29457ef646578a8680ffeb1487e5cb6c69434c3fb80e8030c.
Collected 8446 nodes; previous sealed baseline8304; new142, no removals.
Fresh parent precommit focused142P. Initial backend session22194 completed:
4F/8430P/12S, 874.00 seconds. Retained backend-initial-failed.xml/log and
source-before-initial.json bind that run. Two failures were missed route-count
collateral (216->218) in test_api and test_security_lifecycle_routes. The two
subscription fixture-launcher failures came from comparing resolved fixture
paths to the relative runner WORK: unchanged source/tests with only absolute
workspace environment passed2. Normalize WORK in the runner, not product code.
Direct non-spawning scope probe: initial2 fixture classification failures;
fixed5/5 including outside-provider and dotdot rejection. Corrected relative
workspace rerun of all four previously failed owners:4P/3.67s.

Final integration reviewer Plato01a09045-fe03-7b60-878c-b19c6066b4fd approved
737f438d..8070d4fc. R1/R2/R3/R4 and GETaddendum approved. Collateral reviewer
Aquinas01a09057-9e90-7ef1-9d8b-7e171b15b92f approved the two test edits and
runner correction:16P scoped/probes,2P original-runner absolute control. Exact
actual app delta is two named SEC routes, no removed route or auth change.
Reviewer closed; no auth product or subscription test was changed.

Corrected source freeze still794 paths, patchSHA256
b001cdd5a479359478a0900f09824de66263ed59f39ae3ae4309e04d8e30525c.
Fresh complete session37195 used a new absolute fixture root and exited0.
Exact node/source/initial-collateral reconciliation passed. Collateral test commit
0f8298fa is reviewed; no product/auth repair was needed. All workers are closed
and verification processes completed. Subsequent publication is recorded by
artifact-manifest.json; no further source/test changes are part of this batch.

Ruling: add issuer_refresh(root,cik) lease independent of capture_writer. Concurrent
same-issuer requests otherwise interleave append-only continuation receipts; the
lease blocks only the same issuer, never holds a market transaction across network.
Named cross-issuer/capture-writer positive control added after actual RED.

Task 2 initial RED: 2 assertion failures. Initial focused GREEN interrupted after
10P: parent test finally called multiprocessing.Event.set after terminating its
waiter; stdlib synchronize.py:290 waits for the dead waiter's wake acknowledgement.
Removed only that redundant test cleanup notification. Retest 20P; no product or
existing test expectations changed to accommodate the runner. Then added separate
issuer lease/racing destination owners, both explicit failure/positive checks.

Task 4 initial RED: route module absent (1F), then 10P. Expanded actual command
test initially caught fake get_settings_snapshot's missing positional argument;
fixture signature corrected to match the real accessor. Integrated route/lock
run 21P. API permission helper is the existing audit choke-point, not a claim
that this batch implements the deferred desktop permission engine.

Ruling: capture filesystem operations are currently POSIX admitted; non-POSIX
returns capture_platform_unsupported, never unsafe unlocked writes. Portable
relative data keys/moved-root reads are tested on Linux; Windows native locking
and secure publication remain explicit platform work, not a claimed completion.
