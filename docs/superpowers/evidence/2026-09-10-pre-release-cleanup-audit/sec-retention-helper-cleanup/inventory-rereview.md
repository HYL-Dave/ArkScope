# Scoped Inventory Fix Re-Review

## Result

**No remaining blockers in the scoped fixes, conditional on the stated production filesystem boundary.**

The production invocation must use `/usr/bin/bwrap --ro-bind / / --unshare-net
--die-with-parent`, adding only the stated plan scratch directory as a writable
bind for output. Production databases and their WAL/SHM sidecars must remain in
the read-only view. This conclusion does not cover a direct, unsandboxed inspector
invocation. No production invocation or production-file inspection was performed.

## Original Findings

- **P1: resolved for the specified caller boundary.**
  [inventory.py:216](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/inventory.py:216)
  replaces the unqualified filesystem-write assertion with
  `logical_database_writes: false` and identifies filesystem enforcement as the
  caller's responsibility. The
  [live-WAL regression test](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/test_inventory.py:152)
  keeps a writer open with an uncheckpointed committed row, invokes the inspector
  by import inside the actual read-only `bwrap` view, verifies append-open denial,
  observes the WAL row, and compares exact profile/main, WAL, SHM, and market bytes
  before writer closure. It passed without a skip. SQLite flags alone are still
  not claimed to enforce filesystem immutability. The additional writable output
  scratch bind is the parent's stated production procedure, not an invocation
  exercised by this test.
- **P2: fixed.**
  [inventory.py:143](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/inventory.py:143)
  removes child expression affinity using `p.key = +c.key`, preserving parent
  affinity and collation. All three
  [regression controls](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/test_inventory.py:115)
  pass against SQLite's own `PRAGMA foreign_key_check` oracle: TEXT `'01'` /
  INTEGER `1` is orphaned, the reverse affinity matches, and parent `NOCASE`
  collation matches mixed-case text. Existing nullable/composite/external-FK
  controls also remain green.

## Requested Scope Corrections

- The speculative confirmation table was removed from `PROFILE`. No
  `approved_preview` JSON access or fabricated receipt count was added.
- `evidence_content_sha256` was added to the permitted digest fields. The
  [translation composite-FK test](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/test_inventory.py:135)
  now measures the edge and excludes the private translation sentinel from output.
  Translation/body columns remain outside the authorizer allowlist.
- The [runtime additions](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/inventory.py:226)
  count only `scheduler_state.source='sec_corporate_actions'` and
  `job_runs.job_name='collect.sec_corporate_actions'` using bound parameters.
  Neither mixed-owner table was added to `PROFILE`, so no generic table count was
  introduced. Fixtures contain an unrelated row in each table and return one,
  not two. Authorization permits only the relevant key columns; direct runtime
  result and job payload reads are rejected by the expanded boundary tests.
  Missing required runtime schema is explicitly unavailable, not zero, by the
  inspected branch at line 230.

## Verification And Limits

Executed the approved synthetic command in the specified worktree:

```sh
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hyl/.virtualenvs/llm_app/bin/python -B -m pytest -q --confcutdir=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup -p no:cacheprovider .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/test_inventory.py
```

Observed result: **19 passed in 0.97s**, exit code 0, no skips. The parent's
earlier red/green sequence was not independently rerun; this is a fresh green
verification of the current files.

Reviewed content SHA-256:

- `inventory.py`: `f851057861c55980d4aeb114a8cf230ca7203ad1f3f2d86ca905004f833627c5`
- `test_inventory.py`: `3234ad81aa3ffaa29c720715571129b8b21f0af04c58310df1c28f3b14da5b3d`

This was a delta review of the supplied fixes, not a new general review or a
disposal assessment. Existing cross-database non-atomicity and declared-reference
coverage limits remain. Only this report was added. The schema checkpoint and
original review were left unchanged; no inspector/test/product/index edits,
subagents, provider/configuration/credential access, or application startup were
performed. The inspector was never executed as `__main__`.
