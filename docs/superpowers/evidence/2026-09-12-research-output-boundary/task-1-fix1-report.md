# Task 1 Fix Round 1

## Outcome

Fixed review finding 2 with the requested minimal correction.

- Commit: `5f22762d747743185b808c7c21cf19d25077c312`.
- Parent: `f2068c7599cb71f2aa86112b6659f7f88eac7f30`.
- Changed and committed ONLY `src/agents/shared/output_boundary.py` and `tests/test_output_boundary.py`.
- Full Task 1 final verification: **83 passed, 0 failed, 0 errors, 0 skipped**.
- Task 2's new test file and coordinator plan/spec edits were not staged or changed.
- This report and runner outputs are plan-local scratch artifacts.

## Finding And Fix

With captured strings `xyz` and `a[REDACTED]b`, replacing `xyz` in `axyzb` constructed the second captured string. The input did not contain that complete credential. The existing marker safety check covered patterns inside the marker and partial overlaps, but not a whole marker inside a longer pattern.

The only production change is the unsafe-marker condition:

```python
if pattern in REDACTION_MARKER or REDACTION_MARKER in pattern:
    return False
```

The existing shared `redaction_marker_conflict` failure path now protects prose, all six split positions (0 through 5), and single-character feeds. Marker generation is still allowed for safe guards, and unsafe-marker guards still preserve unrelated text when no replacement is needed. No normal-EOF semantics, RLock behavior, interfaces, representation bounds, or other policies changed.

## RED Owners

New nodes in `tests/test_output_boundary.py`:

- `test_marker_inside_known_secret_cannot_be_created_by_prose`.
- `test_marker_inside_known_secret_cannot_be_created_at_any_split[0]` through `[5]`.
- `test_marker_inside_known_secret_cannot_be_created_by_single_character_feeds`.
- `test_marker_inside_known_secret_preserves_unrelated_public_text` (positive control).

Before the fix, the eight failure-path cases all failed with `DID NOT RAISE OutputBoundaryError`; the public control passed. The control also verifies that `check("a[REDACTED]b")` rejects the already-registered composite, while check/prose/character-stream projection preserve `ordinary public source`.

## Verification

Every product test ran through the required offline runner:

```text
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task1-fix1-red-01 backend -q tests/test_output_boundary.py -k marker_inside_known_secret
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task1-fix1-green-02 backend -q tests/test_output_boundary.py
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task1-fix1-inverse-03 backend -q tests/test_output_boundary.py -k marker_inside_known_secret
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task1-fix1-restored-04 backend -q tests/test_output_boundary.py
```

| Run | Passed | Failed | Errors | Skipped | Deselected | Exit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| task1-fix1-red-01 | 1 | 8 | 0 | 0 | 74 | 1 |
| task1-fix1-green-02 | 83 | 0 | 0 | 0 | 0 | 0 |
| task1-fix1-inverse-03 | 1 | 8 | 0 | 0 | 74 | 1 |
| task1-fix1-restored-04 | 83 | 0 | 0 | 0 | 0 | 0 |

Counts and JUnit digests were parsed from this fix round's four results.xml files using a cleared-environment, standard-library-only metadata reader. Deselected counts come from the corresponding output.log summaries. Each directory also contains its exact command.json and output.log.

JUnit SHA-256 values:

- task1-fix1-red-01: `7287c2b1925bb4983fb3a0670c14c3ff6a7d2eef412b14f8a16148e2c454f442`
- task1-fix1-green-02: `1eb1dd10819c8ebc8747ddda7b4bcd248225dbdc4ebde81929ec1b71fc1922d2`
- task1-fix1-inverse-03: `f12803acbba9a2c2f2d2544b6459719bb63169839edc796f19e234f75bea325a`
- task1-fix1-restored-04: `3f4c6d680ba9d2ce1cd5db7f88f7da3be2d994a7e781edc8da58dade818f55ab`

Both unstaged and staged owned-file `git diff --check` validations passed. Final diff review confirmed one production condition change and the nine regression/control test cases.

## Inverse And Restoration

The inverse removed ONLY `or REDACTION_MARKER in pattern`. It reproduced all eight new failure-path failures with the public positive still passing. The same condition was then restored with apply_patch; the full 83-test primitive suite passed again.

The inverse source matched the parent version:

- Source SHA-256: `409d4814e92b906039b2f74abd7b9b4314162e418cd48b43bf3e85229131af3b`.

Before and after this inverse, the fixed files matched exactly:

- Source SHA-256: `975563ed82d3edcc9e3b0832e942ab756711dd2946fe32dd475df267d3bdb9a1`.
- Tests SHA-256: `3f0cc160d482c94a2a21e3c6080b481592dfc7284d3c868739ef18d9ffa3a6d6`.

The previously proven five inverse groups were not rerun, as requested. Full Task 1 GREEN includes the existing normal-EOF and deterministic concurrent-registration/matcher-publication owners.

## Review And Limits

Self-review traced `_safe_marker` through locked registration, the coherent stream snapshot, and the single shared marker-emission branch used by prose/feed/finish. The added condition covers the missing whole-marker containment for every registered representation. The existing edge-overlap checks remain intact, and the positive control demonstrates that unrelated public output is not rejected merely because a captured string contains the marker.

No wider redesign, sibling-finding work, additional provider/adapter checks, or independent-review approval is claimed. This is synthetic offline verification, not evidence of real-provider exposure. Existing exact-known-secret and finite-representation limitations remain; there is no unknown-secret or semantic zero-false-positive claim. No subagents, network/provider use, production data, tokens, .env reads, installs, merges, pushes, or restarts were performed.
