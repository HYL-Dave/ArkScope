# Interrupted Publication Recovery

Source: `c457480014a12f965c9521276705bad532827744` ->
`d2f491c130f10c738b2158e76e3e536df207e927`, on
`codex/sec-research-integration`. This is a focused repair, not complete SEC
release acceptance, actual-store cleanup or SQLite deployment.

## Defect And Repair

The unchanged178-pass baseline missed publication before registration. A real
disposable-put probe gave1failed/1passed: that crash left object/staging hardlinks
with nlink2, so strict admin inventory blocked every cleanup candidate.

Writer recovery now commits accounting before removing only a proven redundant
stage link. Both canonical names must reference the same regular inode with
exactly two links and the expected content hash. First identity is retained
through hashing and the unlink recheck; parent fsync completes the operation.
Admin inventory is not broadened. Registered bytes, standalone stages and
unproven/external links are not deleted by recovery.

## Verification

- Restored-source focused covering: **1092passed**, zero failures/errors/skips.
  It includes both original probe cases and the complete affected suites.
- Actual preview/approval/apply removes the recovered and unrelated orphan,
  leaving zero charge. Registered reads and repeated recovery remain exact.
- Accounting commit, unlink, fsync, entry replacement and foreign-link faults
  have named behavioral owners. Different-owner market writes succeed during
  hash/unlink/fsync while capture-writer exclusion remains.
- Inverse omitting alias recovery: **2intended failures/2passing controls**.
  Original/mutant/restored source, test, probe and runner hashes are retained.
- Independent task review: compliance PASS, quality Approved, no findings.

`checks/task6-publication-report.md` contains every command/result, including
the test-wrapper platform-admission mistake and its corrected actual RED.
`checks/task6-publication-review-01.md` records independent checks and limits.
The controller's first archive invocation failed before creating the absent
parent directory; after this README created that parent, publication retried
into the still-new `checks` destination. No product or test changed for it.

The closed manifest hashes stored and decompressed source bytes. Only selected
receipts, source/inverse artifacts and reproducible helpers are included, never
generated databases, credentials, capture bodies or compiled runtimes.
All execution was offline on disposable POSIX stores. This is not a hardware
power-loss test or proof against noncooperating post-check filesystem mutation.

Read-only previews do not repair. Existing admitted writer preflight/put and
explicit CaptureStore recovery use the fix; regenerate preview afterward.
The [operator runbook](../../../design/SEC_RESEARCH_OPERATIONS.md) states the
recovery boundary. Default-disabled scheduling and final release verification
continue separately; wider cleanup and SQLite activation are not closed here.
