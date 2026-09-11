# Task 2 Review Fixes

R1: `_directory` now fsyncs the parent whenever creating/opening a directory in
the write path, including retry after a prior interrupted mkdir. Original body
and objects/staging entry fsyncs remain. Named first-capture ancestry owner checks
DB parent and capture-root inode fsync BEFORE `_register`. Directory-fsync EIO
prevents registration; retry returns the exact bytes.

R2: synchronization files are now in the existing trusted `ARKSCOPE_LOCK_DIR`
namespace, not mutable capture contents. Their keys bind the absolute effective
capture root hash and writer/normalized-CIK scope. Root content replacement of
old `.writer.lock`/`.refresh-*` names cannot replace live coordination. Existing
crossprocess child owner now replaces the old capture-root pathname before
attempted recovery; it stays busy until child death. Symlinked coordination
namespace is rejected. Explicit trust boundary: as for existing market/SEC
governor locks, operators must not replace the configured coordination directory
or its live leases while the App runs. This does not claim protection from an
arbitrary local actor who can change all synchronization authorities.

R3: all three totals are scalar subqueries of ONE SQLite statement. Added both
statement-shape owner and an actual interleaving test: after fetching the first
aggregate a normal `put` converts a reserved orphan to a registered object; the
returned charge cannot become zero during that conversion.

R4: path errors distinguish ENOSPC, unsafe path shape and generic I/O before
dropping errno. Shared capture error boundary normalizes public mutation,
preflight, status and recovery SQLite/I/O failures. Named root/objects/staging
and lease-file ENOSPC owners, generic preflight/recovery failure owners remain
closed and contain no injected private text. Added partial-stage write and
post-registration cleanup-failure owners; complete bytes remain readable and
actual orphan allocation stays charged.

Actual review RED: 8 failed / 22 passed. After primary fixes: 30 passed.
Expanded sync/retry/partial-stage/post-register/lease-ENOSPC owners: 34 passed.
Final actual interleaving and crossprocess replacement suite: 35 passed.
XML stems: task2-review-red, task2-review-green, task2-fix-final,
task2-fix-complete. No production reads or actual provider calls.

Platform limitation remains explicit: POSIX descriptor-relative filesystem I/O
is admitted; unsupported systems fail closed. No Windows readiness claim.
