# Renewed WAL Boundary Review

September 11. Independent reviewer Hubble, thread
`01a08c73-25b2-7d00-a258-5370bd4df082`. Source-only review; the reviewer made no
production access, copies, network calls or edits. This review does not repeat
the previous product-source review or claim an independent 8,000-test run.

## Initial Verdict

Practical real-parent-directory design accepted, with two pre-read blockers:

1. A hardlinked sidecar could alias a protected main file through a writable
   pathname. Reject multiply linked files and duplicate database/sidecar inode
   identities before SQLite access.
2. Hashing source followed by SourceFileLoader did not pin executed bytes:
   `-B` prevents bytecode writes, not reads. Execute the exact bytes already
   hashed, without consulting a timestamp-valid `.pyc` or reopening source.

The parent reproduced all five new checks RED: three hardlink destinations,
duplicate main identity, and a forged matching-timestamp bytecode file that
actually executed instead of the reviewed source. These were synthetic files,
not production probes. Fixes reject hardlinks/duplicate identities and compile
the once-read, digest-verified source in a non-`__main__` module namespace.

## Accepted Scope And Limitations

- Keep the real shared WAL/SHM directory and inodes. Private sidecar copies or
  separate binds that pin stale sidecar inodes are not a concurrency solution.
- The parent directory permits creation of new names. Only enumerated existing
  non-sidecar entries are read-only mounts. This is not an exact-filename kernel
  allowlist; creation of unrelated names is not an authorized operation.
- Require payload-free syscall tracing for the real attempt. Review writable
  opens, descriptor lifetimes, mutations and mapping destinations before
  accepting the result. Shared-memory stores are not individually visible to
  strace; the mapped SHM destination is visible.
- Bounded readers can delay checkpoint/reset progress and temporarily retain
  WAL frames. Per-store read transactions are not a two-store atomic snapshot.
- Main-file size/mtime changes during a concurrent App run do not prove that
  a read-only probe checkpointed them, or that logical rows were unchanged.

## Pre-Read Acceptance

Both fixes were in the caller before the renewed production invocation. The
parent's complete synthetic focus passed **38 tests / zero skips**. The scoped
reviewer accepted the pinned dispatcher with no additional pre-read blocker,
subject to unchanged reviewed bytes, a clean environment, `-I -S -B`, one exact
invocation and mandatory post-run trace review. This was static review, not an
independent test execution or a grant of additional permissions.

Dispatcher SHA-256:
`7265952d8881106d03daae7f65ba667237ac2a2f7321b67eb25a4ec4d9f5b722`.
Caller and query identities are recorded in the retention manifest and raw
create-only attempt receipt. The initial two findings and five failing owners
remain in the archived evidence; no actual store was accessed before fixes.

The [post-run review](wal-post-run-review.md) subsequently accepted the observed
inventory and payload-free trace. It identified one stale priority-map status,
corrected separately without altering execution evidence.
