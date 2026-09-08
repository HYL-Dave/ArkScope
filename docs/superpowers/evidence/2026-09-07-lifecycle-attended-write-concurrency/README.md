# Attended Web Write Concurrency

## Scope

This offline continuation tests human confirmation of a completed Web finding
while another real controller/heartbeat worker investigates an unrelated ticker.
Only temporary profile, market and SA databases and synthetic HTTP/model replies
are used. Network/provider calls, production reads/writes, credential reads,
migration, App restart, commit, merge and push are all zero.

The human-confirmation policy is unchanged: an otherwise supported LLM finding
can disclose supplementary read gaps for explicit confirmation. Essential
uncertainty, conflicting active/OTC evidence, changed target effects and stale
evidence still prevent application. Confirmation does not become automatic.

## Reproduced Failure

The small 1 MiB control completes. At exactly 128 MiB decoded per source, the
unmodified human confirmation performs full page and finding validation inside
two consecutive write transactions lasting 43.071 and 30.865 seconds. The human
action applies, but the second worker's heartbeat waits 45.526 seconds and its
first page INSERT also fails with a lock timeout. That worker exits with zero
sources, leaving its raw journal state at `reading_sources`. This is observed
lock starvation before recovery, not proof of a permanently unrecoverable run.

The initial six-node RED owner has four expected failures: prepare permits
another writer, but confirm and execute block it during both decoding and finding
validation. Original XML, measurements, scripts and source hashes are retained
under historical directories; none is relabeled as final-source admission.

## Correction

Complete page/finding validation now precedes the profile transaction. Its
request-local result is bound to the exact profile and run, verified journal
header, terminal calls, result, source index and SQLite schema generation. Each
atomic approval/application rechecks that binding and all current mutable
authority. Existing immutable page/result triggers are still verified. Dropping
and restoring those triggers invalidates the binding even when a page hash is
left unchanged.

The same verified read is explicitly passed through preview, approval and
application in one user command. Separate commands validate again. It is neither
a global cache nor a new persistent authority. Ordinary structured-provider
decisions are unchanged. Direct caller-owned reads retain their transaction and
full-validation behavior. No busy timeout, lease, source capacity, schema or
model-request budget is relaxed by this correction.

## Capacity Results

All four final measurements share the exact final non-document source manifest.
Each uses two jobs, four complete sources per job, actual journal/readback,
explicit human acceptance and the governed tracking writer. Both jobs succeed
with all eight sources; only the intended membership changes. There are zero
SQL, heartbeat or poll failures and exactly four simulated model phases, never
live calls or retries.

| Action | Decoded Bytes Per Source | Confirmation Seconds | Write Transactions, Seconds |
| --- | ---: | ---: | --- |
| Remove | 1,048,576 | 0.240 | 0.033 / 0.048 |
| Rename | 1,048,576 | 0.234 | 0.043 / 0.031 |
| Remove | 134,217,728 | 20.231 | 0.771 / 0.379 |
| Rename | 134,217,728 | 20.067 | 0.737 / 0.359 |

The maximum removal/rename workloads take 146.155 / 146.769 seconds overall.
Maximum heartbeat latency is 1.250 / 1.353 seconds; maximum poll latency is
12.507 / 12.650 seconds. Child `ru_maxrss` is 1,909,919,744 / 1,910,161,408 bytes
(approximately 1.78 GiB). Confirmation still performs approximately 20 seconds
of real validation at this extreme size; the claim is short write contention,
not instantaneous interaction.

These workloads use ordinary disk-backed temporary databases. The Linux
supervisor separately samples child RSS every 25 ms and aborts above 4 GiB or
900 seconds; this is not an OS-level memory guarantee or a whole-App/platform
certification. Sources contain sparse relevant passages plus Unicode filler.
The test reaches the decoded limit, not both encoded and decoded limits at once;
wire-limit/dense-input controls remain in the prior capacity packet. No claim is
made that every real model accepts the resulting native context.

## Regression And History

Final full backend is 6,798 passed / 12 skipped / three existing edgartools
deprecation warnings; baseline/restored focus is 2,133, integration is 2,952 and
complete frontend is 1,578. `verification.json`, full raw results and unique-node
ledgers are generated only after both complete campaigns satisfy `seal.py`.
The added test file has 26 nodes; no prior backend/frontend node is removed.
Fifteen backend mutations run independently against the whole 2,133-node focus,
not just their named owners. Six retain gap/uncertainty/OTC policy coverage and
nine target the new binding, permission and contention behavior. Removing a
guard must fail its named owner without changing the collected node set; every
source mutation must be restored.

Relative to the prior source-gap seal, exactly four product files change:
`lifecycle_web_store.py`, `lifecycle_web_review.py`,
`security_lifecycle_review.py` and `ticker_identity_transition.py`.
`test_lifecycle_web_attended_concurrency.py` is the only added non-document file.
This is the incremental amendment, not the whole still-uncommitted worktree.

Two construction corrections are retained explicitly:

- An initial generic-execute implementation added an extra read-only profile
  connection. The existing lost-readback owner failed because execution could
  stop before application. The implementation was corrected to use its original
  connection before `BEGIN`; the existing owner was not weakened. The next
  121-node run and the final campaign use the corrected implementation.
- The first campaign selected a real-worker test as the owner of discarding an
  already validated read. That test permits the other worker to finish during
  prevalidation, so it cannot independently catch a later redundant read under
  the write lock. The campaign was interrupted and restored. The final mutant
  instead names the original writer-availability RED owner and demonstrably
  fails it. This is a verifier-owner correction, not a claim that the first
  incomplete campaign proved that mutant.

The second campaign's four shards spent most of their time waiting in
`jbd2_log_wait_commit`. Its baseline eventually passed in 314.414 seconds, but
the campaign was interrupted and restored before a mutation was admitted.
Partial mutation shard files remain historical only. The complete third backend
campaign uses RAM-backed temporary test databases under `/dev/shm`, with the
same source, tests, assertions and product budgets. The actual capacity workload
above remains disk-backed. Changing the regression filesystem is not a product
timeout change or a claim that the interrupted campaign completed.

Frontend source and DTOs are byte-identical to the prior source-gap packet. The
complete frontend suite is rerun, as are typecheck/build/i18n. No browser run or
frontend mutation is newly claimed here: the unchanged-UI hash binding points
to the earlier 24 bilingual desktop/mobile cases and 42 screenshots. All five
prior packets' seals are independently rechecked before this packet is sealed.

## Remaining Boundaries

This closes the measured maximum-source attended-write concurrency gate, not
the whole lifecycle workflow. Model-usage calibration, a separately authorized
fresh live investigation, authorized journal/population cutover and final merge
and hand testing remain open. No earlier live authorization is reused.
