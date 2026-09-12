# Task 1 Independent Code And Spec Review

## Findings

### 1. P1: Shared registration and matcher publication can lose credentials

**Original commit: confirmed. Supplementary commit: resolved.**

Locations at `2f0cedeb`: `src/agents/shared/output_boundary.py:207`, `src/agents/shared/output_boundary.py:214`, and `src/agents/shared/output_boundary.py:221`.

Two registrations can both read the old `_patterns`, derive different unions, and overwrite each other. `_secrets` then contains both credentials but the final matcher protects only one; adding the missing credential again returns early as a duplicate. Independently, `_get_matcher()` can start building from old patterns, race a successful registration/cache invalidation, and publish the old matcher afterward. Subsequent checks and streams can therefore admit a captured credential even AFTER registration returns. Register-before-provider-use does not cure either failure.

P1 is warranted for the explicitly intended executor/child-thread sharing: this defeats the primitive's main protection and must block integration. It is not a claim of an existing production leak; this task only introduces the primitive. The original sequential late-registration and unrelated-async-scope tests do not exercise either interleaving.

The minimal correction is one guard-owned lock covering duplicate/budget checks, read-union-write registration, and matcher construction/publication, plus a coherent matcher/longest/marker-safety snapshot for each stream slice. `f2068c75` implements that correction at [output_boundary.py:210](/tmp/arkscope-research-output-boundary/src/agents/shared/output_boundary.py:210), [output_boundary.py:228](/tmp/arkscope-research-output-boundary/src/agents/shared/output_boundary.py:228), and [output_boundary.py:356](/tmp/arkscope-research-output-boundary/src/agents/shared/output_boundary.py:356). The immutable matcher can be scanned outside the lock. Registry additions/removals and cleanup snapshots also use that lock.

The supplementary test at [test_output_boundary.py:574](/tmp/arkscope-research-output-boundary/tests/test_output_boundary.py:574) forces both interleavings using events and an acquisition observer around a real RLock, then checks both credentials' representations. `task1-red-concurrency-22` records both cases failing with `DID NOT RAISE`; runs 23 and 24 record both passing within the 112-test focused set. Source inspection supports resolving the named race without another patch or rerun.

### 2. P2: A replacement can construct a registered secret across both marker edges

**Open in both commits.** Location: [output_boundary.py:111](/tmp/arkscope-research-output-boundary/src/agents/shared/output_boundary.py:111) at `f2068c75`, corresponding to `src/agents/shared/output_boundary.py:107` at `2f0cedeb`. Missing coverage: the marker-conflict cases at [test_output_boundary.py:188](/tmp/arkscope-research-output-boundary/tests/test_output_boundary.py:188).

`_safe_marker()` rejects a pattern contained in the marker and partial overlaps at either edge. It does not reject the reverse containment: the complete marker inside a larger protected pattern. For example:

```python
guard = OutputGuard(["xyz", "a[REDACTED]b"])
guard.prose("axyzb")  # returns "a[REDACTED]b", a complete registered secret
```

The second credential is absent from the original text, yet appears in the emitted display projection. This violates the exact-known-secret coincidence rule and the module's unsafe-marker guarantee. P2, rather than P1, reflects the narrow prerequisite: an accepted captured string must itself contain the literal marker. No real-provider exposure is asserted.

The independent probe [task1-reviewer-marker-probe.py](./task1-reviewer-marker-probe.py) loads the immutable `2f0cedeb` source with read-only `git show`, not the moving checkout. It confirms the registered composite is rejected by `check()` and unrelated public prose is preserved, then fails for prose, character-at-a-time feeds, and all six split positions of `axyzb`: **8 failed in 0.06s**, exit 1. Evidence: [task1-reviewer-marker-01/results.xml](./task1-reviewer-marker-01/results.xml). The supplementary diff does not change the helper or marker insertion logic, so the finding remains applicable by source inspection; the probe was not rerun unnecessarily against unchanged code.

Minimal correction: include `REDACTION_MARKER in pattern` in the unsafe-marker condition and retain the existing fail-closed `redaction_marker_conflict` behavior only when redaction is needed. Add this two-sided composition case to prose and split/character stream tests, with the unrelated-public-text control. No implementation patch was made by this reviewer.

## Independent Verdicts

| Target | Spec verdict | Quality verdict |
| --- | --- | --- |
| Original `e0b0ed4a..2f0cedeb` | Not approved: shared-thread capture and marker composition violate the boundary contract. Corrected normal EOF behavior is compliant. | Changes required: P1 and P2 above. |
| Supplement `2f0cedeb..f2068c75`, named concurrency concern | Pass within the documented per-operation snapshot and single-consumer stream contract. | The correction is appropriately scoped; both decisive race owners have observed RED/GREEN evidence. |
| Combined `e0b0ed4a..f2068c75` | Not approved while the P2 marker-composition case remains. | **Changes required. Recommendation/workflow label: `revise`.** Only finding 2 remains open. |

## Contract Checks

- **Normal EOF/public preservation:** `finish()` processes all remaining raw text, redacts complete matches, and flushes unmatched prefixes unchanged. `abort()` clears the suffix and closes the stream. Original tests at `tests/test_output_boundary.py:122`, `:135`, and `:147` distinguish every partial prefix, abort, and public words ending in a JWT's first character. Normal unmatched suffixes are not findings and must not be discarded as a fix.
- **Splits/overlap:** the literal trie reports the longest match ending at each raw offset, sufficient to cover shorter matches ending there. Raw interval union and `_covered`/`_redacting` carry preserve overlapping and touching matches across cuts without indexing replacement text. All representation split points, one-character feeds, six overlap cases, the internal 64 Ki-character boundary, and the separate 400-input raw-mask oracle are named owners. The marker-output composition gap is distinct from raw-input matching.
- **Representations/state:** the ten documented single-step forms are bounded, deduplicated, and case-sensitive; raw, JSON, URL, both base64 alphabets, and padding cases are covered. Failed registration does not partially install a credential. Pending text is rescanned after sequential additions; `f2068c75` makes shared registration and cache snapshots coherent. Unsupported objects are rejected without arbitrary repr/str coercion. No unknown-secret or recursive-encoding guarantee is inferred.
- **Lifetimes:** guards and streams reject pickle/copy and have content-free reprs. Streams retain a bounded raw suffix, not full answers. Default scopes isolate unrelated executions; inherited scopes and borrowed activation preserve the retained execution guard. Root exit aborts unfinished streams, borrowed exit does not, and cancellation restores context. The actual provider iterator's closure belongs to later integration, not these two files.
- **Bounds/public JSON:** strict built-in JSON traversal checks strings and keys without mutation, with explicit depth/node/text bounds and public numeric/identifier/URL controls. Numeric spellings, canonical serialization, and credential-field policies are explicitly assigned to the later result-policy owner; this review does not silently claim those are implemented here.

## Evidence And Scope

- Workspace: `/tmp/arkscope-research-output-boundary`. Only the two requested product files were assessed. The task brief, current tracked design, original review package, supplementary review package, implementer report, and this plan's named test artifacts were inspected. No other plan scratch or whole-branch review was used.
- Base: `e0b0ed4aafd1fce1687ff7fa6b7dc6e391c9a469`; original head: `2f0cedeb62c6663e1d55ebf82e8623833c631095`; supplementary/final head: `f2068c7599cb71f2aa86112b6659f7f88eac7f30`.
- Original review-package SHA-256: `ca8b3092e36e6ced3f8cc7d3bec8e3f16c1421ea4c72e041b55be297d5754c34`.
- Supplementary review-package SHA-256: `6d5396e452a667632efc6809e9696f4260da9936104ba12e667036a59aceca1f`.
- Current design SHA-256: `708f60bd36febf9ebd862e74cdd31aafb18afb5ae217a0b7cf2963a88f1b22e4`.
- Independently hashed all four immutable source/test blobs: original blobs match `restoration_files` and final blobs match `files` in `task-1-checks.json`. JUnit hashes for runs 21, 22, 23, and 24 also match that record. Counts are evidence from supplied actual runs, not a fresh reviewer suite run.
- Confirmed `task1-final-21/output.log`: **110 passed in 3.05s**. Confirmed `task1-green-concurrency-23/output.log`: **112 passed in 3.09s**; `task1-final-concurrency-24/output.log`: **112 passed in 3.03s**, comprising 74 primitive and 38 unchanged compatibility tests. No full-backend pass is claimed.
- Confirmed inverse logs: known-match bypass (1 failure), premature suffix emission at raw split 1 (1), unrelated-scope sharing (1), abort/cancellation tail release (2), and stale sequential patterns (1). Each corresponding restoration records 72 passed. The initial missing-boundary and naive split-1 RED owners are present in the checks record. Collection-error run 08 is not treated as useful RED evidence.
- Only new executable evidence was the concrete marker-composition probe, run with this plan's `offline_pytest.py`, a cleared environment, disabled plugin autoload/bytecode, and unique `task1-reviewer-marker-01` scratch. No product edits, index changes, commits, installs, subagents, provider/network operations, credential/.env reads, or production-data access were performed.

## Residual Integration Requirements

The race fix does not make one `SecretStream` concurrently consumable. Its owner must sequence feed/finish/abort and settle child work before root cleanup; taking a locked registry snapshot is not a cancellation/join mechanism. Checks and internal slices linearize at their pattern snapshots, so credentials must be registered before provider use. Context must be restored before public yields, and only true normal EOF may call finish. These are documented caller obligations, not additional blockers against the narrow supplement. End-to-end adapter/event/replay/scratchpad enforcement and whole-backend verification remain outside this task-scoped gate.
