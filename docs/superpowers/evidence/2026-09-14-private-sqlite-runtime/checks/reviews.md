# Runtime Review Record

These are parent-authored summaries of scoped read-only reviews, not a verbatim
transcript or an independent complete-suite result. The parent owns all commands
and tests in this evidence packet. No reviewer ran alongside the full backend.

The runtime-only reviewer (`01a0a021-a5d9-7a43-8168-4487388a09c9`) examined the
new package/verifier/launcher, startup callers, tests and design. It did not
inspect installed selectors, private data/configuration or another worktree.

1. Initial review identified two actionable issues: adding the package directory
   to `sys.path` allowed an unexpected adjacent module to run before rejection;
   the direct-process verifier did not reject `LD_PRELOAD`/`LD_AUDIT` although
   the launcher did. Three RED cases independently reproduced these paths.
   Explicit hash-checked source loading without a directory import path and the
   shared process guard fixed them. The expanded focused check passed 67 cases.
2. Follow-up confirmed those fixes, then identified unbounded checksum reads of
   bootstrap FIFOs. Three bounded process-group tests demonstrated the hang.
   The selector now rejects symlink/non-regular bootstrap objects, caps size and
   bounds the checksum command. Invalid bootstrap state exits before user code.
3. Final scoped re-review found no new important findings and considered the
   earlier issues remediated. The final parent-focused run passed 278 cases;
   the subsequent frozen selected-runtime whole backend passed 11,238 cases
   with twelve unchanged skips.

The parent also demonstrated executable bootstrap-byte drift before verification
and added two RED cases before this review. Fixed shell-level hashes now precede
the first package Python code. Digests detect installation drift; this is not a
sandbox or authentication against arbitrary code running as the same OS user.

No reviewer verdict is used as evidence of production activation, database
health, actual installed Desktop/SA selection or Windows/macOS support.
