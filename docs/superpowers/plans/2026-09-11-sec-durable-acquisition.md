# SEC Durable Structured Acquisition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Persist exact SEC source snapshots and observations, enforce capture
capacity, and make explicit, resumable structured acquisition callable from the
application without prematurely replacing the Research tools.

**Architecture:** A canonical market-DB schema retains immutable original-body
objects, catalog/fact observations and refresh receipts. Short SQLite transactions
publish metadata after create-only files. A per-root writer lease protects capture
reservation/recovery; it is never held while acquiring a provider response.
The service reads raw bytes through the existing SEC transport and pure parsers.

**Tech Stack:** Python standard library, SQLite, existing SecTransport, pytest,
FastAPI; no dependency or interpreter upgrade.

**Spec:** `docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md`.
Base: `737f438d`. This plan implements structured storage/acquisition, not the
complete first release's document reader, export, three tools or Settings UI.

## Global Constraints

- Existing linked worktree only; no production DB/config/token reads or writes,
  live provider calls, installation, restart, merge or push.
- Default capture budget is 107374182400 bytes, adjustable through the existing
  SEC profile accessor; exact positive integer at most 2**53-1. A decrease below
  usage blocks growth, not reads. No automatic deletion or prefetch.
- Catalog/fact source responses use the existing 16 MiB decoded metadata limit;
  document acquisition remains a separate 32 MiB wire / 128 MiB decoded path.
- Files contain original decoded response bytes, not reserialized floats.
  Capture keys stay relative to `P.parent / (P.name + '.sec-research')`.
- No old schema/version-chain compatibility, unconditional CREATE-IF-NOT-EXISTS
  acceptance, foreign-table deletion, lifecycle mutation or financial_cache edit.
- Three SEC tools replace get_sec_filings atomically in a subsequent integration
  plan after the document reader is real. Current adapters/skills remain live.
- Existing SecTransport identity, host validation and shared governor remain;
  its bounded 429 handling is not advertised as zero retry. Cancellation is
  checked between bounded requests; this plan does not claim in-flight abort.
- This metadata publisher bounds each normalized snapshot to 64 MiB UTF-8 JSON
  and 100000 rows before BEGIN IMMEDIATE. Reserve a conservative additional
  256 MiB destination-space margin for metadata/index/WAL staging. This is a
  write-admission margin, not a guarantee about total shared WAL/DB size.

## Task 1: Canonical Schema And Immutable Structured Store

**Files:** create `src/sec_research/schema.py`, `store.py`,
`tests/test_sec_research_store.py`.

**Interfaces:**
- `schema.install(conn)` explicitly creates all owned tables/indexes/triggers in
  one transaction or validates their exact definitions. `schema.verify(conn)`
  does not create or repair anything. Error codes are ValueError arguments.
- `Store(paths: SecResearchPaths)`; `.install()`; `.connect(readonly=False)`
  context manager with explicit close; read-only is mode=ro/query_only, never
  immutable. `.publish(snapshot, *, object_sha256, observed_at, source_url)`
  returns snapshot ID, verifies object metadata exists and matches source hash.
- `.snapshots(cik, kind)` returns saved snapshot metadata; `.catalog(cik)` and
  `.facts(cik)` reopen immutable observations (not a public filtered query API).
- `.record_receipt(cik, *, status, completed, pending, gaps, observed_at)` and
  `.latest_receipt(cik)` persist refresh continuation, not a claim that a whole
  issuer has been completely observed from a partial request.

Shared capture tables (owned by schema, consumed by Task 2):
`sec_research_objects(sha256 TEXT PRIMARY KEY, object_key TEXT UNIQUE NOT NULL,
size_bytes INTEGER NOT NULL CHECK(size_bytes>=0))`;
`sec_research_reservations(reservation_id TEXT PRIMARY KEY, size_bytes INTEGER
NOT NULL CHECK(size_bytes>=0))`;
`sec_research_orphans(object_key TEXT PRIMARY KEY, size_bytes INTEGER NOT NULL
CHECK(size_bytes>=0))`. Other owned structures retain source snapshots, filing
and fact rows, and receipts with reference constraints/immutable triggers.

- [x] Add RED owners for fresh/populated installation, repeated initialization,
  explicit shape mismatch, exact fact TEXT and amendments, retained snapshots,
  hash mismatch and interruption rollback. Initial RED is missing schema/store.

```python
def test_install_preserves_populated_unrelated_tables(tmp_path):
    # Seed prices/news/financial_cache sentinel rows before explicit installation.
    store = make_store(tmp_path, populated=True)
    store.install()
    assert sentinel_rows(store) == ORIGINAL_ROWS
    store.install()
    assert sentinel_rows(store) == ORIGINAL_ROWS
```

- [x] Implement exact owned DDL verification using sqlite_master; validate all
  owned objects before installing any, reject unexpected sec_research_* objects.
  Use exact Decimal string values from the parser, source pointers and SHA256.
- [x] Limit normalized payload/row count before acquiring the writer transaction;
  idempotent snapshot identities preserve observation time through receipts.
- [x] Run `tests/test_sec_research_store.py` plus all existing SEC parser/config/
  path tests. Inverse mutations: bypass shape check, store value as float,
  overwrite an old source snapshot. Each must kill a named owner.
- [x] Review and commit the independently testable store.

## Task 2: Create-Only Captures, Capacity And Crash Recovery

**Files:** create `src/sec_research/captures.py`, `capture_lock.py`,
`tests/test_sec_research_captures.py`, `tests/test_sec_research_capture_lock.py`.

**Interfaces:** `CaptureStore(store, *, budget: Callable[[], int],
free_bytes: Callable[[Path], int] | None = None)`;
`.preflight()` checks known budget/disk failures before network;
`.put(body: bytes) -> str` returns sha256;
`.read(sha256: str) -> bytes` verifies pinned bytes;
`.status() -> dict` reports persisted, orphan and reserved charges;
`.recover() -> dict` reconciles interrupted captures under exclusive root lease.
`capture_writer(root: Path)` is a context manager; no silent unlocked fallback.

- [x] Add RED tests for exact byte reopening, duplicate quota charge, reduced
  budget readable captures, quota/disk rejection, interrupted stage/publication,
  orphan charging, two-process reservation contention and symlink rejection.

```python
def test_reduced_budget_blocks_growth_not_pinned_reads(captures):
    digest = captures.put(b'complete')
    captures.test_budget = 1
    assert captures.read(digest) == b'complete'
    with pytest.raises(ValueError, match='capture_budget_exceeded'):
        captures.put(b'new')
```

- [x] Serialize capture writes/reconciliation with a per-root OS file lease
  (fcntl on POSIX, typed unsupported failure elsewhere; never a no-op).
  Synchronization files live in the existing trusted `ARKSCOPE_LOCK_DIR`, keyed
  by the absolute capture root hash, outside mutable content. Operators must not
  replace this coordination namespace while live, as with market/governor locks.
  A distinct issuer lease serializes same-CIK refresh receipts without holding
  the capture writer or market DB lock across provider waits.
  Root/children are non-symlink regular structures; POSIX
  descriptor-relative opens protect writes against path replacement.
- [x] Reserve the exact already-buffered body length in a short transaction
  before disk writes. Source acquisition and parsing occur before this lease.
  Staged bytes plus unused reservation equal the reservation, not twice it.
- [x] Fsync a private create-only stage; publish via no-replace hard link; verify
  any existing target's length/hash. Commit the object row, then remove only this
  operation's stage. No referenced object is overwritten or automatically pruned.
- [x] Recovery can release prior reservation ownership only while the exclusive
  writer lease proves no active writer remains. Enumerate actual stage/unpublished
  object sizes as charged orphans before releasing reservations. No TTL/PID guess
  can reclaim live work. Detect missing/corrupt registered captures on read.
- [x] Test ENOSPC after preflight, fault injection before/after link and metadata
  commit, moved-root reopening and process death. Inverse quota subtraction and
  overwrite publication mutations must fail named tests. Review and commit.

## Task 3: Resumable Structured Acquisition Service

**Files:** create `src/sec_research/service.py`,
`tests/test_sec_research_service.py`.

**Interfaces:** `ResearchService(store, captures, transport, *, clock=...)`;
`.refresh(cik, *, max_sources=4, resume=False, check=None)` returns the persisted
receipt; `.stored(cik)` returns catalog/fact snapshot coverage with no transport.
Input is an explicit CIK in this stage, not guessed ticker resolution.

- [x] RED fixtures use original JSON bytes through a fake transport exposing
  `get(url, **kwargs)` and SecResponse. Named owners prove acquisition occurs
  outside write locks; recent/historical traversal; incomplete vs empty;
  malformed source retention without successful smaller data; provider failure
  receipt; original precision; preflight before transport; and persisted resume.
- [x] Request submissions then companyfacts and declared historical files only;
  deduplicate pointer names and bound each invocation's sources to max_sources.
  Persist pending/completed source locators, gaps and observation time. Resume
  consumes that pending set, never assumes omitted pointers are empty history.
  Fresh refresh starts a new observation; old successful snapshots stay readable.
- [x] Preflight before every request; transport `.body` feeds parsers directly.
  Persist valid complete source body before its parsed snapshot. Failed parses
  may preserve their original body but do not publish valid observation rows.
  Closed failure codes, not body/URL/token exception strings. Cancellation keeps
  pending work; partial results never imply complete coverage.
- [x] Inverse skip-preflight and force-complete mutations fail their owners.
  Run parser/store/capture/service suite. Review and commit.

## Task 4: Explicit Application Commands And Review Follow-Ups

**Files:** create `src/api/routes/sec_research.py`,
`tests/test_sec_research_routes.py`; modify `src/api/app.py`,
`tests/test_api.py`, `tests/test_security_lifecycle_routes.py` (the two exact
application route-count owners: 216 to 218, naming the two SEC routes),
`docs/design/PROJECT_PRIORITY_MAP.md`, `docs/design/ENGINEERING_ISSUE_REGISTER.md`
and the existing cleanup audit `README.md` (canonical CENSUS-I18N-001 owner).

- [x] RED tests prove `GET /sec-research/{cik}` creates no schema/files and makes
  no provider request; absent store is unavailable, not empty success.
  `POST /sec-research/{cik}/refresh` calls existing `require_db_write` before
  service construction, explicit installation and provider dispatch. Validate
  CIK, max_sources 1..16 and boolean resume before side effects.
- [x] Build the service from the existing profile accessor, market path and
  SecTransport identity; always close transport. No startup schema installation,
  job, new tool registration or UI control. This endpoint is the current
  structured service's application consumer; Settings will reuse it.
- [x] Name the 100 i18n candidates' cleanup owner; preserve EIR-001 CSS and
  CENSUS-SQL-001. Mark foundations consumed by service and remaining tool/UI
  wiring pending. Do not relabel candidate counts as confirmed dead code.
- [x] Review permission/read-only tests and unchanged tool inventory. Commit.

## Task 5: Integration Evidence

- [x] Run focused store/capture/service/routes and existing SEC/tool/API owners.
  Record exact RED, GREEN and inverse mutation results, not predicted counts.
- [x] Run a fresh complete offline backend suite, capture collected/executed node
  accounting and source hash stability; do not modify existing expectations to
  hide runner failures. Rerun mechanical census against the preceding sealed
  result; classify all new candidates/uncertainties explicitly.
- [x] Independent whole-change review; fix substantive findings and verify again.
- [x] Archive source/evidence hashes and final counts in
  `docs/superpowers/evidence/2026-09-11-sec-durable-acquisition/`.
- [x] Report this completed structured-service boundary and still-open document
  reader, query policy/cursors, issuer resolution, three tools/four transports,
  citations/export, schedule/UI, C11/C12 and old actual-schema disposition.
  No claim that the complete SEC first release is ready for hand testing.
