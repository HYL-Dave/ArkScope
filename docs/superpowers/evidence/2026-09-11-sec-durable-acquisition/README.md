# SEC Durable Structured Acquisition

Base: `737f438d`. Plan:
`docs/superpowers/plans/2026-09-11-sec-durable-acquisition.md`.

This batch connects the previously pure SEC foundations to real SQLite, capture
files, governed acquisition and explicit application commands. It is **not the
complete SEC first release or a ready-for-hand-testing SEC Research workflow**.

## Implemented Boundary

- One explicit canonical `sec_research_*` schema in the effective market DB.
  Existing owned shape mismatch is rejected, not silently repaired. Fresh and
  populated unrelated stores are tested; prices/news/financial_cache survive.
- Immutable original-byte objects and catalog/fact snapshots. Decimal values are
  TEXT, with SHA256/JSON pointer provenance, distinct dates and retained revisions.
  INSERT OR REPLACE and explicit-rowid replacement cannot bypass immutability.
- Adjustable 100 GiB capture budget, deduplication, durable reservations,
  actual orphan charging, full-disk/error handling, create-only publication,
  pinned hash/length reads and moved-root reopening. No implicit pruning.
- Explicit normalized-CIK submissions/companyfacts/historical acquisition through
  SecTransport. Durable pending intent and per-source checkpoints support bounded
  resume. Missing historical pointers remain a gap, not observed-empty history.
  Old successful data is retained but cannot turn a new failed refresh into ok.
- `GET /sec-research/{cik}` reads status/counts through the same stored service.
  No capture, profile/config, installation or provider side effect occurs on GET.
  `POST /sec-research/{cik}/refresh` validates input, calls the existing write
  permission choke-point, explicitly installs, then uses profile-managed SEC
  identity. No new environment fallback, schedule, model tool or startup work.
- Same-issuer refresh receipts serialize independently of capture/market writers;
  different issuers remain independent. Latest receipt is the last durable append,
  never a wall-clock maximum that can select old success after clock rollback.

The four formerly test-only SEC foundation modules now have real consumers.
The new HTTP routes are intentionally not wired to Settings yet. No replacement
of `get_sec_filings`, existing skills or the four Research transports occurs here.

## Review Corrections

Initial independent capture review found four issues; named RED owners reproduced
all four (8 failures / 22 passes), followed by the 35-test corrected capture/lock
suite and fresh scoped approval:

1. New directory ancestry must be fsynced before the object row commits, including
   retry after interrupted mkdir. This is fault-injected syscall-order evidence,
   not a hardware power-cut experiment.
2. Lease identity cannot live in mutable capture contents. Coordination now uses
   the existing trusted `ARKSCOPE_LOCK_DIR`, keyed by capture-root hash and scope.
   Operators/cleanup must not replace that namespace while App processes run;
   this is the same operational prerequisite as market/governor locks, not an
   OS sandbox or protection against arbitrary local administration.
3. All capacity totals use one SQLite statement snapshot. A real concurrent
   reservation-to-object conversion cannot temporarily disappear from the total.
4. ENOSPC remains a capacity error during directory/lock creation as well as body
   writes. Public preflight/recovery normalize I/O/SQLite failures to closed codes.
   Partial stages and post-registration cleanup failures preserve readable objects
   and accounting.

Store review separately caught wall-clock receipt ordering. The corrected reader
and index use monotonic receipt IDs; timestamps remain unchanged diagnostics.
The inverse old ordering fails the rollback/reopening owner. Receipt input-limit
owners also reject over-budget rows/bytes before taking the market writer lock.

## Explicit Limits

- The filesystem implementation is currently POSIX-only; unsupported platforms
  return `capture_platform_unsupported`, not unlocked or unsafe writes. Linux
  fixture verification does not establish native Windows/macOS packaging support.
- Capture-root quota is not a quota for the shared SQLite DB, WAL, profile or
  exports. Metadata source responses retain SecTransport's 16 MiB decoded limit.
  Normalized source publication is bounded to 64 MiB UTF-8 JSON / 100000 rows;
  destination checks include a 256 MiB metadata/index/WAL staging margin. These
  are admission limits, not a measured whole-App memory/disk guarantee.
- Original-body capture precedes immutable snapshot publication, and snapshot
  publication precedes its receipt checkpoint in separate transactions. A crash
  in that final window leaves the source pending and may reacquire it. This is
  at-least-once, idempotent local publication, not exactly-once HTTP dispatch.
- Completed receipt locators do not yet carry snapshot IDs. Query/as-of/source
  selection must add that binding before claiming authoritative current facts.
- `max_sources` bounds source dispatches, not raw HTTP attempts. Existing
  SecTransport can retry a 429 once. Cancellation is between bounded requests,
  not an in-flight abort. A live canary budget must account for those distinctions.
- Stored status materializes snapshot metadata for counts, not financial rows or
  bodies. This is neither a streaming metadata query nor a paged financial API.
- The existing `require_db_write` helper is the application audit choke-point;
  this batch does not implement the deferred interactive permission engine.
- The offline harness isolates fixture paths/environment and rejects production
  access/network in its process; it is not an OS sandbox. No live/provider,
  production-store activation, schema disposal, installation, restart, merge or
  push is part of this batch. The relocation test uses a closed fixture DB, not
  a claim of live WAL-safe export. No new backup helper was introduced.

## Remaining Work

SEC issuer resolution, observation selection/as-of/metrics/cursors, filing documents
and exact citations, three-tool/four-transport replacement, persisted Research
citations, portable export, Settings and scheduling remain open. The old live SEC
tool is not removed ahead of its complete replacement. C11/C12 and actual old
schema disposition are also still open; a read manifest is not DROP authorization.

The 100 additional locale-leaf candidates have a named revalidation owner,
`CENSUS-I18N-001`, in the cleanup audit. They are not 100 proven dead keys. CSS
remains EIR-001, SQL union-schema completeness remains CENSUS-SQL-001. No original
artifact or previous review result is rewritten to claim broader cleanup.

## Verification

All task reviews and the independent whole-plan integration review approved the
source at the frozen patch. Parent also reran the inverse guards in isolated
processes: quota, no-replace publication, permission order, preflight, partial
coverage, checkpoint, issuer exclusion, schema shape, decimal precision,
historical retention and receipt append order all failed their named owners.
The executable `capture_inverse.py` and `inverse-*.xml.gz` retain the exact
mutations/results. Mutations changed loaded functions only, never shared source
or the separately running full-suite process.

Final source census: **1111 read / 4309 candidates / 3382 uncertainties**.
Against the preceding sealed census: two new HTTP candidates pending UI,
four former SEC Python candidates now consumed, 30 new SQL uncertainties,
zero coverage reductions, dependency changes or new main-worktree untracked
paths. The raw exit remains **2 / review_required**. SQL uncertainties remain
under CENSUS-SQL-001; passing runtime SQL tests do not repair the scanner model.
The earlier in-batch census had 31 new SQL uncertainties before the stored-route
reuse removed one duplicate query site. Raw earlier and final artifacts remain.

Implementation commits after the plan commit `562e105b`:

| Commit | Scope |
|---|---|
| `5f50ff1a` | Canonical schema and exact immutable observations |
| `e192374a` | Capture files, reservations, recovery and capacity |
| `87f316c0` | Governed structured acquisition and continuation |
| `8070d4fc` | Explicit command and stored-status application routes |
| `0f8298fa` | Two missed exact application route-count owners and named SEC pair |

Fresh parent precommit run: **142 passed**, covering all five new test files.
Exact collection: **8446**, versus the preceding sealed **8304**. No existing
node was removed. The initial run froze **794** source/test files and patch
SHA256 `452c30f1111a28a29457ef646578a8680ffeb1487e5cb6c69434c3fb80e8030c`.

The initial full run returned **4 failed / 8430 passed / 12 skipped** in 874.00s.
Its XML/log and source freeze remain as `backend-initial-failed.*` and
`source-before-initial.json`. Two missed collateral assertions still expected
216 mounted routes; the explicit new SEC pair makes 218. Both owners now name
that pair as well as the total, without weakening the existing lifecycle set.
The other two failures were existing Codex fixture-launcher tests. The temporary
runner compared resolved fixture paths with a relative WORK; changing only the
workspace environment to absolute produced **2 passed** with identical source
and tests. Normalizing WORK in the runner fixes that classification. A direct
five-case probe preserves rejection of outside provider paths and `..` escape;
all four failed owners then passed with a relative workspace as well. No OAuth
product or subscription test changed. These are test-inventory/runner corrections,
not provider availability or authentication fixes.

Fresh independent collateral review approved: **16 passed** (four affected
owners, six adjacent contract cases and six separate probes), plus **2 passed**
with the initial runner and an absolute workspace. Its in-memory baseline/current
app comparison proves exactly two added route rows and zero removals. These are
separate verification executions, not additions to the repository's node total.
Exact commands and direct path/symlink matrix are in `collateral-review.md`.

The corrected fresh full run completed: **8434 passed / 12 skipped**, zero
failures, **850.34 seconds**. Exact reconciliation confirms **8446 collected =
8446 executed**, **142 added / zero removed**, and the same twelve skipped
identities as the preceding sealed batch. All **794 source/test paths** stayed
unchanged throughout this verification, with source patch SHA256
`b001cdd5a479359478a0900f09824de66263ed59f39ae3ae4309e04d8e30525c`.
`verification-summary.json` also binds the initial failed run and proves that
only the two route-inventory test files changed between the two source freezes.

No frontend source changed or frontend/live-provider/native-platform verification
was performed in this batch. The complete SEC workflow remains unfinished as
listed above. Six commits precede evidence closeout: one plan, four product/test
implementation commits and one collateral-test commit; this is not one change
being described as a single commit. Master and origin/master remain `30bb31c7`.

## Replay Scope

The archived harness sources retain their original working layout:
`.superpowers/sdd/2026-09-11-sec-durable-acquisition/` below the implementation
worktree. Their root derivation is for that layout, not direct execution from
this evidence directory. Fixture DBs are not archived. The full-run command is:

```bash
env -i \
  PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
  ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-sec-durable-acquisition/final-full-corrected \
  /home/hyl/.virtualenvs/llm_app/bin/python -B \
  .superpowers/sdd/2026-09-11-sec-durable-acquisition/offline_pytest.py tests -q \
  --junitxml=.superpowers/sdd/2026-09-11-sec-durable-acquisition/backend-full.xml \
  > .superpowers/sdd/2026-09-11-sec-durable-acquisition/backend-full.log 2>&1
```

The verification helper compares exact collected/executed identities, unchanged
skip identities and SHA256 of every tracked source/test path. Artifact publication
is create-only with compressed-byte and decompressed readback hashes. Neither
helper activates a production store or substitutes file copying for live backup.

Publication completed with **108 artifacts / 2726293 archived bytes**. A second
manifest/readback pass checked every archived and original-byte hash and reparsed
all 8446 full-suite testcases, confirming zero failures/errors and twelve skips.
The manifest excludes this explanatory README and the manifest itself. The
archived ledger is the pre-publication checkpoint; this paragraph and the
manifest record the completed publication, without rewriting historical logs.
