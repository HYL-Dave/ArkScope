# Prebuilt Transition Cleanup

Parent baseline: `9bb80725`. User approved A+B before hand testing and explicitly
rejected a low application ID-count limit. C (prebuilt interpreter selection,
TLS, required fixes, production admission and activation) is separate and not
completed here. No source archive/compiler is needed for these checks.

## Completed Source Checkpoints

- `d82425e9`: five ID-set call sites, six SQL statements. Whole-set membership
  and exclusion, input normalization, global sorting/LIMIT, signed-int64 binding
  refusal and exact text survive. There is no application input-count ceiling.
  SQLite's actual payload/resource limits still apply; this is not unlimited
  memory. The NUL-specific JSON decoder preserves the old accepted text domain
  without temporary-table writes, and regular IDs use native `json_each`.
- `57839d76`: remove all four unused self-build modules and their optional hooks,
  plus four test modules (72 old test identities). No fallback or forwarding
  alias. Eleven source-free current-entry tests replace useful launch properties;
  native import purity is strengthened. Exact custom-package/loader/hash tests
  retire with their implementation, not as claimed prebuilt admission.
- `6be6f743`: remove fresh `agent_queries` DDL and test-only write/count wrappers.
  Existing query tables/rows and generic archive reads remain. Report/memory and
  current Research owners are unchanged. Retained-data disposition is NOT closed.
- `34a112ba` integrates reviewed C15 extraction `3132d56e`: physically remove
  the remaining listing/provider converters, extract unchanged SQLite byte
  helpers, and keep current investigation installation/disposal. Current V4 SA
  membership provisioning has an executable `src.sa_tracking_installation`
  operator with its observation, stopped-App, automation, digest, exclusive
  backup, transaction and no-op guards. Reject old V2/V3 shapes, do not convert.
- `2aeed54a`: independently fix the preview-output defect found in C15 review
  and confirmed in the pre-existing investigation CLI. Both consumers use
  `operator_preview`: alias rejection, prior-output preservation, build/serialize
  before creation, and owned-inode cleanup on handled write failure. No
  installation/disposal-engine or SQL behavior changed in this follow-up.

The C15 extraction proof is pinned to `3132d56e`, not a claim that the later
CLI output fix is byte-identical to the old CLI. Seven sealed historical
consumers remain unchanged and replay against `9bb80725`. The live module named
`lifecycle_investigation/migration.py` is deliberately retained: it installs
the current investigation system, not an obsolete converter. C15 code retirement
is closed; that filename alone is not deletion authority.

## Focused Verification

The existing disposable 89-wheel candidate/control environments are reused,
without changing installed Python, numpy, dependencies or selectors. Commands
use the repaired, guarded offline runner from the preceding compatibility
receipt. Only the disposable source snapshot is updated; no production stores
or credentials are mounted into test runs. Each run is serial in that snapshot.

| Run | Result |
| --- | --- |
| A RED, candidate 3.53.1 | 6 failed / 10 passed; five real variable-limit failures plus missing helper |
| A GREEN, candidate 3.53.1 | 261 passed |
| A control, 3.37.2 | 261 passed |
| B RED | 1 failed / 24 passed; obsolete implementation absence guard |
| B GREEN, candidate | 185 passed |
| C20 RED | 2 failed / 20 passed; fresh table and obsolete writer guards |
| C20 GREEN, candidate | 51 passed |
| B+C20 control, 3.37.2 | 236 passed |
| Combined parent checkpoint, candidate | 497 passed |
| Affinity/index and tail-strengthened A, candidate/control | 18 passed each |
| Disposable cap mutation, candidate | 5 failed / 13 passed |
| Restored A, candidate/control | 18 passed each |
| C15 integrated focus, candidate/control | 166 passed each |
| New SA preview-output RED | 13 failed / 11 passed |
| Existing investigation preview-output RED | 5 failed / 2 passed |
| Shared preview-output GREEN, candidate/control | 134 passed each |
| Interpreter-path preflight, candidate/control | 11 passed each |

Independent parent review accepted A/B/C20 implementation and closed its P3
finding after the tail-test follow-up. Its original coverage
finding (only prefix IDs had matching fixture rows) is repaired in `fe871bff`:
the tail must match in recovery/lineage and win article ordering. In a disposable
copy only, truncating both set encoders at 32,766 breaks all five large-set cases.
The copy was restored byte-for-byte before the last two passing runs. Raw
mutation output is gzip-preserved because pytest includes trailing whitespace;
the contents are not reformatted to satisfy a whitespace check.

C15 independent review found the preview-output P2 above. Its follow-up review
accepted `2aeed54a`, including the shared existing-CLI fix, with no further
blocking findings. This is handled-failure cleanup, not a claim of crash-atomic
publication or adversarial filesystem isolation. Serialization failure,
close-time flush failure and destination creation between precheck and open
are not separately injected; the tests do exercise partial-write failure and
preservation of a replacement output.

The first A invocation had an incorrect test-module import and did not collect;
the valid RED run above followed its correction. The first B run additionally
had an incorrect assertion expecting the Claude SDK overlay to omit variables
instead of explicitly blanking inherited values; corrected to its real closed
environment contract, no product security code changed. The first C20 focused
GREEN invocation named a nonexistent test file and ran zero tests; the corrected
invocation above supplies the result. None is counted as product acceptance.

Frontend verification used the same locked dependencies and source, isolated
from production. The initial clear-environment run lacked a timezone and
reported 1,831 passed / 4 failed, all four expecting Asia/Taipei rather than UTC.
Adding only `TZ=Asia/Taipei` to the test environment produced **1,835 passed
across 126 files**. Product code and assertions were unchanged. Both outputs
are preserved, not represented as two different product states.
`npm run build --workspace apps/arkscope-web` also passed, including
`tsc --noEmit`. Vite still reports the existing large-chunk advisory; no bundling
refactor was mixed into this backend cleanup.

The 33,000 historical citation test is structural retention stress, not a claim
to generate that many independently authenticated assessment digests. It checks
both surviving facts and evidence, deletion of an uncited row, FK and integrity.

## Full Acceptance

The tested product/test revision is `2aeed54a`. Each full run uses a fresh copy
of the same ArkScope git archive, not SQLite source. Archive SHA-256:
`316554c4c6e9a4ec77c84a466ecd1c28dbaef8c029c4ee62cb2034e228e20c49`.
The byte check covered 11,894 files without mismatches. Only the same three
encrypted non-runtime evaluation documents were excluded; no key was loaded.
The first archive attempt failed at git-crypt smudging and was never tested;
the complete archive used an explicit cat filter without decrypting those
excluded documents. A tar metadata comparison reported owner differences;
the subsequent check compared file bytes instead. One initial integrated
focused invocation named a nonexistent disposal test and ran zero tests;
the correct existing owner is `test_lifecycle_investigation_retirement.py`.

The first full control invocation passed **11,245 / 12 skipped** in 1,393.94s,
but its wrapper still put the candidate venv on PATH. Its main interpreter was
3.37.2; bare-command descendants were ambiguous. Preserve this result as
`full-cleanup-control`, not as authoritative engine-consistent acceptance.

The corrected wrapper derives PATH from the chosen interpreter and the runner
asserts that both `python` and `python3` resolve to that interpreter before
collection. Actual engine, PATH and resolved commands are recorded. The
source-independent `run_tests-consistent.sh` / `offline_pytest-consistent.py`
are the final runner versions; the original focused-run files are preserved.
The scratch launcher invokes its top-level `offline_pytest.py`, populated from
that consistent version. No product code was changed for the runner correction.

| Authoritative full run | Result |
| --- | --- |
| SQLite 3.37.2 control | **11,245 passed / 12 skipped**, 1,379.96s, exit 0 |
| SQLite 3.53.1 candidate | **11,245 passed / 12 skipped**, 1,423.09s, exit 0 |

Both have exactly one pytest main entry, an unchanged source diff, and all
11,894 archived files still byte-identical after execution. The 11,257 unique
test identities and all 12 skipped identities match between engines; the skips
also match the prior manual tests after removing the retired source-dependent
runtime tests. The paired summary records XML hashes, observed engine/PATH,
console versus JUnit duration and post-run source checks. Node accounting is explicit:
11,216 before - 94 removed + 135 added = **11,257**. Removed identities are
72 self-build cases, 21 obsolete converter cases and one unused query-writer
case. Added identities and their owners are in `test-node-accounting.json`.
Full runs are serial; no parallel pytest, scanner or source edits occur in the
tested copy. Documentation and immutable-revision census run in the separate
parent checkout, never in that copy. These are offline compatibility results,
not production integrity checks, TLS acceptance or runtime deployment.

## Census

Same scanner, `9bb80725` versus immutable `2aeed54a`: 4,317 to 4,302 candidates,
3,231 to 3,201 uncertainties, and 1,179 to 1,178 read files. The comparison has
one new candidate, 63 new uncertainty identities, 12 exact deleted-file
reductions, and zero dependency-metadata or untracked-name drift. Exit 2 and
`review_required` remain explicit.

The one candidate is the tested current operator `src.sa_tracking_installation`,
not an abandoned module. The 63 uncertainty identities cover one dynamic-import
absence guard and 62 SQL statements/expressions in the changed stores/helpers
and relocated current installer. File/line relocation changes their identity;
they are not 63 demonstrated regressions or DROP authorizations. Full snapshots
and per-path/kind counts are preserved. Broader static uncertainties remain
review inputs, not a claim that every unreachable symbol is gone. C21 remains
an explicitly deferred capability. Three generated obsolete runtime pycs and
their now-empty parent directory were removed; unrelated private files were not.

## C20 Protected Inventory

One current read observed `agent_queries` present with **2 rows**. Only table
type and `COUNT(*)` were authorized; no question, answer or other row columns
were read. The query runs in one read transaction with `query_only`, an explicit
column/action authorizer, mode=ro and a read-only main-file mount. No immutable
mode or explicit checkpoint is used. Synthetic absent/present tests and denied
column/write probes passed before the real inventory.

The standing WAL/SHM authorization was used: SQLite created the missing empty
WAL and initialized SHM. Payload-free syscall evidence shows the main DB opened
O_RDONLY, writes confined to SHM fd5, and no main-file write. The SQLite close
attempt to obtain a main write lock failed EBADF, then the connection closed
successfully. Do not attribute unrelated concurrent App activity to this read.
The parent directory permits new names; enumerated non-sidecar entries are
read-only mounts, not a claimed kernel filename allowlist. No stored rows,
schema or settings were changed.

User approval has been requested for verified archive-then-dispose of the two
rows. Until granted and actually executed, keep the table and generic reader.

Subsequent ruling: the user instead approved direct deletion without an archive.
The final allowlist entry is removed in the follow-up; the production operation
then completed after the user closed the old-master App: exactly two rows and
the table were removed, with fresh read-only absence verification. See
[C20 direct disposal](../2026-09-15-c20-disposal/README.md) for current status;
the paragraph above records this checkpoint's earlier proposal.

## Still Pending

The user's [SEC/current-feature hand test](../../plans/2026-09-15-sec-current-runtime-hand-test.md)
remains. A+B and C15 code retirement passed paired full acceptance; C20 code and
the separately authorized direct disposal are now closed in the follow-up. C,
Windows/macOS and Python sandbox remain explicitly separate. No merge/push,
App restart or runtime activation occurred. The only follow-up production schema
change was the approved C20 DROP, not part of this checkpoint's offline tests.
