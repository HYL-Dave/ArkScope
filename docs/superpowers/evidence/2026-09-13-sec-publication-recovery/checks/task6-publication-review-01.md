# Task6 Publication Recovery: Independent Review 01

## Verdicts

- **Spec compliance: PASS.** All required properties of the publication-recovery brief are supported by the supplied patch, the focused unchanged-code checks below, and retained fixture receipts.
- **Quality: Approved.** No required fixes identified in this patch.
- This is the Task6 publication follow-up gate only, not a whole-branch review, Task7 approval, merge authorization, or destructive rollout approval.

## Findings

- **Critical:** None.
- **Important:** None.
- **Minor:** None.

## Reviewed Artifact

- Worktree: `/tmp/arkscope-research-output-boundary`.
- BASE: `c457480014a12f965c9521276705bad532827744`.
- HEAD: `d2f491c130f10c738b2158e76e3e536df207e927`, also confirmed by `git rev-parse HEAD`.
- Immutable artifact: `task6-publication-review-01.diff`, 607 lines / 26,892 bytes, read once in full with its context.
- Artifact SHA-256, computed during that same read: `8b5227c50c05de4f222bf0d84df59727138b02a3bd768c51db68f71c09b9802f`.
- Scope: `src/sec_research/captures.py`, `src/sec_research/capture_lock.py`, and the three specified capture/lock/maintenance test files; 430 additions, no deletions. No schema, dependency, transport, configuration, or scheduling change.

## Spec Compliance

| Requirement | Verdict and concrete evidence |
| --- | --- |
| Account before unlink | PASS. [captures.py:39](/tmp/arkscope-research-output-boundary/src/sec_research/captures.py:39) commits or rolls back inside `_write`; the new call at [captures.py:81](/tmp/arkscope-research-output-boundary/src/sec_research/captures.py:81) runs only after that context exits. The commit-denial fixture retains reservation 11 and both links. Unlink/fsync fault hooks independently read the committed orphan row and zero reservations. |
| Exact canonical two-name proof, no arbitrary link-count acceptance | PASS. [capture_lock.py:269](/tmp/arkscope-research-output-boundary/src/sec_research/capture_lock.py:269) requires exactly two locally observed entries for a candidate inode, canonical object/staging names, and equal sizes. [capture_lock.py:286](/tmp/arkscope-research-output-boundary/src/sec_research/capture_lock.py:286) opens both with no-follow/nonblocking flags, requires regular files, the accounted device/inode/size, and exactly two links. Foreign/extra aliases and malformed names are rejected; a separate identical stage is retained and charged separately. Singleton entries do not authorize any unlink. |
| Verify again at unlink boundary | PASS. The first descriptor identity includes device, inode, size, nlink, mtime and ctime. After streaming the object hash, [capture_lock.py:306](/tmp/arkscope-research-output-boundary/src/sec_research/capture_lock.py:306) rechecks root/child identities and both no-follow entries against both descriptors and that retained identity, then compares SHA-256 with the canonical object name before unlink at line 316. The baseline is not refreshed to accept a newly added foreign link. Accounted-entry and post-hash replacement cases retain unproven names. |
| Published bytes and registered evidence untouched | PASS. Only the proven staging name is removed. Registry rows and the registered-read path are unchanged. The after-register owner checks exact bytes, persisted 11/orphan 0/reserved 0, one surviving object link, and two recoveries. No standalone staged body or published object is implicitly pruned. |
| Strict admin inventory preserved | PASS. The unchanged [capture_lock.py:323](/tmp/arkscope-research-output-boundary/src/sec_research/capture_lock.py:323) still requires a regular single-link entry; `inventory` additionally rejects duplicate identities. Unsafe pairs remain blocked. Both actual publication windows reach approved cleanup of the target plus unrelated orphan only after recovery, with final charge 27 -> 0. |
| Failure/retry charging and directory durability | PASS. Unlink and post-unlink fsync failures return the existing typed storage error after accounting has committed. Staging fsync is required before success. [captures.py:61](/tmp/arkscope-research-output-boundary/src/sec_research/captures.py:61) syncs the namespace before re-accounting on retry, including when the staging name is already absent. Persistent-fault and restored-retry assertions preserve charge and converge. |
| Long filesystem work outside market lock | PASS. Scan/sync precede `_write`; candidate hashing, unlink and post-unlink fsync follow it. Actual different-owner market writes succeed at all three new filesystem barriers, with committed `news` rows checked. |
| Cooperating writer exclusion | PASS. `recover`, `preflight`, and every `put` recovery call stay within `capture_writer`. The existing operation and writer leases enclose the helper and its durability work. Competing threads remain busy at the filesystem barriers; the published child-process owner blocks recovery until terminated, after which recovery retains the object and its charge. |

## Focused Unchanged-Code Checks

These were named risks, not a general caller or branch review. No changed implementation was reread from Git/source after the immutable diff.

| Named risk | Actual inspection and result |
| --- | --- |
| Accounting could retain the stage key that recovery subsequently removes | Checked `CaptureDirectory.__init__` and `files` at [capture_lock.py:155](/tmp/arkscope-research-output-boundary/src/sec_research/capture_lock.py:155) and [capture_lock.py:243](/tmp/arkscope-research-output-boundary/src/sec_research/capture_lock.py:243), plus the supplied `_recover` context. Children are ordered objects before staging; inode deduplication retains the surviving object key, while registered inodes remain charged by the registry. No stale-stage accounting defect found. |
| Commit might still be pending, or failed directory durability might be acknowledged on retry | Checked `_write`, `_storage_errors`, `_recover`'s unchanged prefix, `sync`, and [store.py:132](/tmp/arkscope-research-output-boundary/src/sec_research/store.py:132). Connections are caller-committed; rollback precedes error propagation; filesystem sync occurs before rebuilding accounting. The existing fault receipts resolve this risk. |
| A caller could release exclusion early or hold the market lock throughout hashing | Checked `preflight`, `put`, `_lease`, `_capture_lease`, `research_operation`, and the unchanged `market_writer` fixture at [test_sec_research_maintenance.py:90](/tmp/arkscope-research-output-boundary/tests/test_sec_research_maintenance.py:90). Writer ownership spans the helper, while the barrier fixture really acquires the market lock and commits a separate SQLite write. No shortened lease or mock-only concurrency proof found. |
| Recovery could weaken admin eligibility or registered-read integrity | Checked `read`/`_verify` at [captures.py:108](/tmp/arkscope-research-output-boundary/src/sec_research/captures.py:108), descriptor reads, and the remainder of inventory/owned removal. Registered reads still verify expected size and digest; admin single-link and approved-identity checks remain separate. No acceptance rule was widened. |

The unchanged fixture constructors were also checked for evidence validity: they create tiny disposable stores, not configured application stores. No production entrypoint was executed.

## Existing Receipts Verified

All paths in this section are relative to `.superpowers/sdd/2026-09-12-sec-research-release-integration/`. I parsed each named `command.json` and `results.xml` and checked its `output.log`; these are existing runs, not reviewer reruns.

| Receipt directory | Exit | Verified result / interpretation |
| --- | --- | --- |
| `task6-publication-red-01` | 1 | 20 failed / 3 passed / 89 deselected; failures observe retained aliases, missing rejection and unreached I/O barriers. |
| `task6-publication-green-01` | 0 | 23 passed / 89 deselected. |
| `task6-publication-identity-red-01` | 1 | 1 failed / 3 passed; `capture_platform_unsupported` from the wrapper admission mistake, not intended product RED. |
| `task6-publication-identity-red-02` | 1 | 1 failed / 3 passed; intended `DID NOT RAISE` for the newly added foreign link. |
| `task6-publication-green-02` | 0 | 27 passed / 89 deselected. |
| `task6-publication-inverse-omit-alias-01` | 1 | 2 failed / 2 passed; committed before-register owner retains nlink 2, unchanged probe remains `blocked/capture_path_unsafe`; both stage-only controls pass. |
| `task6-publication-covering-frozen-01` | 0 | 1092 passed, zero failures/errors/skips; includes every new publication owner and both unchanged probe cases. Exact log tail reports 114.22s. |

Additional focused checks actually performed:

- Parsed `task6-publication-inverse-omit-alias-01-source/receipt.json`: completed inverse, expected failure names/messages, exact restoration, unchanged tests and runners.
- Fingerprinted the five current product/test files, unchanged controller probe, both runners, and archived `captures.py.original` / `captures.py.mutated`: all ten SHA-256 values match that receipt. This was a byte-integrity check, not another source/diff review. Original/restored source hashes match; the mutant differs only as recorded.
- Confirmed the covering command uses the isolated offline runner and the prescribed suites/probe. No suite or focused product test was launched by this review; no unresolved named doubt justified one.
- Read-only Git status showed an existing unrelated modification to `docs/design/SEC_RESEARCH_OPERATIONS.md`; its contents were not reviewed or edited. No product, index, HEAD, runner, dependency, or existing receipt was changed. The sole review write is this report.

## Quality and Limits

The two local helpers fit `CaptureDirectory`, retain the original identity across hashing, close opened descriptors on failure paths, and preserve existing error/accounting ownership. Tests observe bytes, inode/link state, durable rows, approved cleanup and real competing writers rather than treating mock calls as outcomes. No quality finding requiring a fix remains.

The consequence of a faulty unlink would be high because persistent filesystem state is involved; narrow semantics and relevant passing behavioral controls reduce regression likelihood, not that consequence. Recovery after injected I/O faults remains explicit and idempotent. Reverting the patch would reintroduce the interrupted-publication cleanup blockage; no migration or alias recreation is required for already-recovered objects.

Evidence is fixture-only POSIX execution, not hardware power-loss or real-store rollout validation. The existing trusted lock namespace and cooperating-writer assumptions remain. There is still no atomic conditional-unlink primitive against a noncooperating actor changing names after the final check; this is the disclosed existing model, not a new finding. Unproven/corrupt aliases remain deliberately unrepaired. Whole-backend/branch review and rollout remain controller-owned.

## Machine-Readable Patch Assessment

The advisory `merge` label below applies only to the supplied Task6 patch assessment. It does not authorize a branch merge or rollout. The JSON is embedded here so this report remains the only review-created file.

```json
{
  "schemaVersion": 1,
  "patch": {
    "repository": "/tmp/arkscope-research-output-boundary",
    "sourceType": "patch_file",
    "base": "c457480014a12f965c9521276705bad532827744",
    "head": "d2f491c130f10c738b2158e76e3e536df207e927",
    "changedFiles": ["src/sec_research/capture_lock.py", "src/sec_research/captures.py", "tests/test_sec_research_capture_lock.py", "tests/test_sec_research_captures.py", "tests/test_sec_research_maintenance.py"],
    "sha256": "8b5227c50c05de4f222bf0d84df59727138b02a3bd768c51db68f71c09b9802f"
  },
  "recommendation": "merge",
  "workflowLabel": "human_review_required",
  "impact": {"rating": "high", "rationale": "An incorrect alias unlink or accounting update affects persistent capture state; the scope is the Task6 patch only."},
  "regressionLikelihood": {"rating": "low", "rationale": "Strict canonical two-link descriptor proof, retained identity, post-hash checks, unchanged caller leases and direct fixture coverage support the narrow change."},
  "regressionProtection": {"rating": "strong", "rationale": "Within this fixture-only task gate, restored-source receipts cover actual put windows, failures/retries, alias and replacement refusal, strict inventory, explicit cleanup and concurrency; the frozen run has 1092 passes and source/test fingerprints match restoration.", "exactHeadChecksPassed": true},
  "recoverability": {"rating": "managed", "rationale": "I/O faults require explicit idempotent recovery; no schema migration or object deletion is introduced. Reversion restores the original cleanup blockage for future interruptions."},
  "confidence": {"rating": "high", "rationale": "Immutable patch identity, named unchanged-code risks, required behaviors and retained execution/provenance receipts were checked independently; no decision-critical task-gate unknown remains."},
  "applicability": {"status": "confirmed", "rationale": "The changed helper is reached by CaptureStore.recover, preflight and put inside the existing capture writer lease."},
  "statusQuoRisk": {"rating": "moderate", "rationale": "The retained inverse reproduces an interrupted before-register pair that blocks cleanup of both the target and an unrelated orphan."},
  "autoMergeExclusions": ["persistent_state"],
  "affectedRuntimeRoots": ["CaptureStore.recover", "CaptureStore.preflight", "CaptureStore.put"],
  "importantCallers": ["CaptureStore._recover", "CaptureStore._write", "capture_writer/_lease/_capture_lease", "CaptureDirectory.files/sync"],
  "riskDrivers": ["Persistent namespace deletion", "Durable accounting and retry ordering", "Filesystem identity across hashing"],
  "protectiveFactors": ["Only a canonical same-inode two-link pair can authorize unlink", "First descriptor identity is retained through post-hash checks", "Accounting commits before stage unlink and parent sync", "Strict admin inventory is unchanged", "Recorded behavioral inverse and real competing-writer fixtures"],
  "materialBoundaries": [
    {"id": "accounting", "invariant": "Charge survives before any alias unlink.", "runtimeRoot": "CaptureStore._recover at captures.py:61", "counterexample": "A failed COMMIT must not remove the stage or retire reservation 11.", "legitimateControl": "The committed orphan uses the surviving object key; before-register recovery keeps a single charge and later approved cleanup reaches zero.", "result": "supported"},
    {"id": "identity", "invariant": "Only the currently proven canonical object/stage inode pair with exactly two links can authorize unlink.", "runtimeRoot": "CaptureDirectory._remove_published_stage at capture_lock.py:286", "counterexample": "A foreign link added after the first stat, or an entry/body/root replaced during hashing, must not be accepted by refreshing identity.", "legitimateControl": "The valid published pair is hashed and rechecked against the first identity and both no-follow names before only the stage is removed.", "result": "supported"},
    {"id": "durability", "invariant": "Success requires staging-directory durability; retry cannot lose charge.", "runtimeRoot": "CaptureStore._recover and capture_lock.py:317", "counterexample": "Unlink succeeds but staging fsync fails, leaving the alias absent without acknowledged durability.", "legitimateControl": "Persistent failure remains typed and charged; namespace sync precedes retry accounting and a restored retry converges.", "result": "supported"},
    {"id": "preservation", "invariant": "Registered bytes and strict admin eligibility remain unchanged; standalone stages are not automatically deleted.", "runtimeRoot": "CaptureStore.read and CaptureDirectory.inventory", "counterexample": "Treating equal content or an arbitrary hardlink count as deletion authority could remove a separate body or broaden admin acceptance.", "legitimateControl": "Separate identical stages remain charged twice, unsafe aliases remain blocked, and registered reads retain exact bytes and persisted charge after recovery.", "result": "supported"},
    {"id": "concurrency", "invariant": "Long filesystem work permits ordinary market writers while excluding a competing capture writer.", "runtimeRoot": "CaptureStore.recover/preflight/put under capture_writer", "counterexample": "Holding the market lock during hashing/fsync blocks unrelated writes; releasing the capture lease early admits a competing owner.", "legitimateControl": "Committed different-owner news writes succeed at hash/unlink/fsync barriers while capture competitors stay busy; a live child excludes recovery until termination.", "result": "supported"}
  ],
  "validation": [
    {"name": "Single immutable-diff review and named unchanged-code checks", "status": "passed", "protects": "Task-specific account/identity/durability/preservation/concurrency contracts; no whole-branch claim."},
    {"name": "task6-publication-covering-frozen-01 receipt inspection", "status": "passed", "protects": "Existing offline execution: 1092 passes, zero failures/errors/skips, including required publication owners and unchanged probe; not rerun by reviewer."},
    {"name": "RED, GREEN and inverse evidence inspection", "status": "passed", "protects": "Historical intended failure outcomes were confirmed, the admission-hook failure was distinguished, and no failed check remains at assessed HEAD."},
    {"name": "Inverse restoration and ten SHA-256 comparisons", "status": "passed", "protects": "Current product/tests, probe, runners and archived original/mutant match retained provenance without changing or executing the product."}
  ],
  "unknowns": [
    {"summary": "Hardware power-loss, actual-store rollout and whole-backend/branch gates were not exercised and are outside this fixture-only review.", "decisionCritical": false},
    {"summary": "The existing POSIX/cooperating-writer model does not provide atomic conditional unlink against a noncooperating post-check filesystem mutation.", "decisionCritical": false}
  ],
  "evidencePlan": []
}
```
