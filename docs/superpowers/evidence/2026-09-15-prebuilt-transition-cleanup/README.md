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

The first A invocation had an incorrect test-module import and did not collect;
the valid RED run above followed its correction. The first B run additionally
had an incorrect assertion expecting the Claude SDK overlay to omit variables
instead of explicitly blanking inherited values; corrected to its real closed
environment contract, no product security code changed. The first C20 focused
GREEN invocation named a nonexistent test file and ran zero tests; the corrected
invocation above supplies the result. None is counted as product acceptance.

The 33,000 historical citation test is structural retention stress, not a claim
to generate that many independently authenticated assessment digests. It checks
both surviving facts and evidence, deletion of an uncited row, FK and integrity.

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

## Still Pending

Independent parent review, C15 current-installation cleanup/integration, final
serial full-suite receipts and the user's SEC/current-feature hand test. C,
Windows/macOS and Python sandbox remain explicitly separate. No merge/push,
App restart, production schema change or runtime activation occurred.
