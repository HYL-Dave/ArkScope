# Security Lifecycle Listing Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace publisher/news-driven lifecycle automation with deterministic SEC and current-listing authority, using Nasdaq Trader without credentials, Massive reference data through the existing Polygon key when needed, and IBKR only as optional corroboration or conflict detection.

**Architecture:** Evolve the exact lifecycle schema from v2 to v3 with additive legacy vocabulary and a new `listing_authority` evidence family. A tick-scoped, bounded listing session fetches the two Nasdaq symbol directories once and performs at most four deduplicated Massive exact-ticker lookups; the scheduler persists cited normalized records, the pure policy evaluates SEC/listing convergence, and the API/UI renders only regulator, listing, optional IBKR, and manual evidence. Existing publisher rows remain durable but no longer participate in acquisition, projection, or active case detail.

**Tech Stack:** Python 3, SQLite exact-schema authorities, `requests`, pytest, FastAPI/Pydantic, React 19, TypeScript, Vitest, i18next, Playwright/browser fixtures.

**Spec:** `docs/superpowers/specs/2026-08-28-lifecycle-listing-authority-design.md`

## Global Constraints

- Do not call SEC, Nasdaq Trader, Massive, IBKR, or any other provider while implementing or running offline gates.
- Do not read, write, back up, restore, preflight, or migrate the production profile or market database.
- Do not merge, restart the production App, or push.
- Keep `publisher`, `internal_news`, and `publisher_excerpt` legal for existing v2 rows; new v4 runs must never produce or consume them.
- Keep the durable provider ID `polygon` and the single profile field
  `polygon.api_key`. Use only `MASSIVE_API_KEY` as its process bridge; do not
  resolve `POLYGON_API_KEY` at runtime or read either key from `config/.env` for
  Massive execution/import.
- Use `https://api.massive.com` for new Massive requests and never persist the key in a URL, diagnostic, locator, or exception.
- Nasdaq absence is `not_found`, never `inactive` or `delisted`.
- IBKR contract or quote absence is not delisting evidence; a price is never listing authority.
- `AUTOMATION_POLICY_VERSION` becomes `trusted-lifecycle-automation-v4`; `AUTOMATION_EXECUTION_REVISION` remains unchanged.
- Use the real producer-to-fact-kernel boundary in contract tests for every new adapter.
- All source text and test fixtures are ASCII unless a file's established localization content requires Traditional Chinese.

## File Structure

- `src/security_lifecycle_schema.py`: v1, v2, and current v3 exact schema authorities and verifiers.
- `src/security_lifecycle_listing_migration.py`: explicit v2-to-v3 preflight, backup, scratch migration, and restore authority.
- `data_sources/listing_authority_transport.py`: allowlisted, budgeted Nasdaq/Massive HTTP boundary.
- `src/security_lifecycle_listing_evidence.py`: strict parsers, normalized listing records, evidence, cited facts, and tick-scoped lookup session.
- `src/security_lifecycle_decision_policy.py`: pure SEC/listing/IBKR decision matrix.
- `src/service/security_lifecycle_automation_scheduler.py`: one listing session per tick, no news acquisition, optional IBKR.
- `src/security_lifecycle_fact_kernel.py`: adapter-to-family/kind validation for listing evidence.
- `src/security_lifecycle_disposition.py`: active source-family projection without publisher.
- `src/tools/security_lifecycle_tools.py`: active-detail filtering and provider-neutral listing serialization.
- `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`: compact listing evidence and source distinction.
- `apps/arkscope-web/src/lifecycle/lifecyclePresentation.ts`: listing labels and deterministic explanations.
- `apps/arkscope-web/src/settings/settingsBackendCopy.ts`: Massive (Polygon) provider presentation.
- `src/data_provider_config.py`: official Massive endpoint for the explicit connection probe.
- `tests/fixtures/listing_authority/`: real-shaped offline Nasdaq and Massive payloads.
- `docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority/`: reproducible offline admission packet.

---

### Task 1: Establish Exact Schema V3 and Reversible V2 Migration

**Files:**
- Modify: `src/security_lifecycle_schema.py`
- Modify: `src/security_lifecycle_automation_migration.py`
- Create: `src/security_lifecycle_listing_migration.py`
- Modify: `tests/test_security_lifecycle_automation_schema.py`
- Modify: `tests/test_security_lifecycle_automation_migration.py`
- Create: `tests/test_security_lifecycle_listing_migration.py`
- Modify: `tests/test_security_lifecycle_disposition.py` (adjacent closed-family owner only)

**Interfaces:**
- Consumes: exact v2 `PROFILE_TABLE_SQL`, `PROFILE_INDEX_SQL`, and all ticker-identity authorities at `fda1641f`.
- Produces: `V2_PROFILE_TABLE_SQL`, `V2_PROFILE_INDEX_SQL`, `create_v2_profile_schema(conn)`, `verify_v2_profile_connection(conn)`, current v3 `PROFILE_TABLE_SQL`, and four explicit migration functions:

```python
preflight_listing_authority_migration(path: str | Path) -> ListingMigrationPreflight
create_listing_authority_backup(path: str | Path, destination: str | Path, *, approval_sha256: str) -> ListingProfileBackup
migrate_listing_authority_schema(path: str | Path, *, approval_sha256: str, backup_sha256: str) -> ListingMigrationResult
restore_listing_authority_backup(path: str | Path, backup: str | Path, *, backup_sha256: str) -> ListingRestoreResult
```

- [x] **Step 1: Write schema REDs for all three authorities**

Add tests that create v1, v2, and current schemas independently and assert the closed vocabularies:

```python
def test_v3_schema_adds_listing_authority_without_removing_v2_values():
    conn = sqlite3.connect(":memory:")
    create_profile_schema(conn)
    sql = schema_sql(conn, "security_lifecycle_evidence")
    for value in (
        "listing_authority",
        "nasdaq_symbol_directory",
        "massive_reference",
        "listing_directory_snapshot",
        "publisher",
        "internal_news",
        "publisher_excerpt",
    ):
        assert f"'{value}'" in sql


def test_v2_schema_remains_byte_exact_and_rejects_v3_listing_rows():
    conn = sqlite3.connect(":memory:")
    create_v2_profile_schema(conn)
    verify_v2_profile_connection(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_listing_evidence(conn, adapter="nasdaq_symbol_directory")
```

- [x] **Step 2: Run schema REDs**

Run:

```bash
pytest tests/test_security_lifecycle_automation_schema.py -q
```

Expected: fail because no v2 authority or listing vocabulary exists.

- [x] **Step 3: Split the v2 authority before defining v3**

Refactor the second-generation schema definitions so the existing SQL is first
captured as v2, then only the evidence table is regenerated with additive v3
values:

```python
V2_PROFILE_TABLE_SQL = dict(PROFILE_TABLE_SQL)
V2_PROFILE_INDEX_SQL = dict(PROFILE_INDEX_SQL)
V2_EVIDENCE_SOURCE_FAMILIES = EVIDENCE_SOURCE_FAMILIES
V2_EVIDENCE_ADAPTERS = EVIDENCE_ADAPTERS
V2_EVIDENCE_KINDS = EVIDENCE_KINDS
V2_AUTOMATION_BLOCKER_CODES = AUTOMATION_BLOCKER_CODES

EVIDENCE_SOURCE_FAMILIES = V2_EVIDENCE_SOURCE_FAMILIES | {"listing_authority"}
EVIDENCE_ADAPTERS = V2_EVIDENCE_ADAPTERS | {
    "nasdaq_symbol_directory",
    "massive_reference",
}
EVIDENCE_KINDS = V2_EVIDENCE_KINDS | {"listing_directory_snapshot"}
AUTOMATION_BLOCKER_CODES = V2_AUTOMATION_BLOCKER_CODES | {
    "listing_directory_unavailable",
    "listing_directory_schema_mismatch",
    "listing_directory_stale",
    "listing_status_unresolved",
    "listing_authority_conflict",
    "massive_credential_missing",
    "massive_access_denied",
    "massive_rate_limited",
    "massive_reference_unavailable",
}
```

Regenerate only the v3 evidence table and
`security_lifecycle_automation_run_blockers` table. Define the v3 adapter CHECK
as an additional branch while retaining every v2 branch verbatim:

```sql
OR (
  adapter IN ('massive_reference','nasdaq_symbol_directory')
  AND source_family = 'listing_authority'
  AND kind = 'listing_directory_snapshot'
  AND run_id IS NULL
  AND automation_run_id IS NOT NULL
  AND source_url LIKE 'https://%'
  AND source_document_sha256 IS NOT NULL
  AND source_locator_json IS NOT NULL
)
```

Add `create_v2_profile_schema` and `verify_v2_profile_connection`. Update the
existing v1-to-v2 migration to import and target the new `V2_*` names so its
meaning does not silently become v1-to-v3.

- [x] **Step 4: Run schema tests GREEN**

Run:

```bash
pytest tests/test_security_lifecycle_automation_schema.py tests/test_security_lifecycle_automation_migration.py -q
```

Expected: pass; v1-to-v2 behavior and exact v2 verification remain covered.

- [x] **Step 5: Write v2-to-v3 migration REDs**

Seed every v2 lifecycle table, including one publisher evidence row with a
translation and one automation fact/citation chain. Assert:

```python
def test_v2_to_v3_preserves_every_existing_cell_and_adds_no_listing_rows(tmp_path):
    source = seeded_v2_profile(tmp_path)
    before = snapshot_all_owned_rows(source)
    before_rowids = snapshot_lifecycle_rowids(source)
    before_sequences = snapshot_lifecycle_sequences(source)
    preflight = preflight_listing_authority_migration(source)
    backup = create_listing_authority_backup(
        source,
        tmp_path / "backup.db",
        approval_sha256=preflight.approval_sha256,
    )
    result = migrate_listing_authority_schema(
        source,
        approval_sha256=preflight.approval_sha256,
        backup_sha256=backup.sha256,
    )
    assert result.source_schema_version == "v2"
    assert result.target_schema_version == "v3"
    assert snapshot_all_preexisting_columns(source) == before
    assert snapshot_lifecycle_rowids(source) == before_rowids
    assert snapshot_lifecycle_sequences(source) == before_sequences
    assert count_listing_evidence(source) == 0
    verify_profile_path(source)
```

Also test stale approval rejection, wrong backup digest, foreign-key failure,
unowned table preservation, idempotent v3 no-op, restore digest mismatch,
and successful byte-identical restore to v2.

- [x] **Step 6: Run migration REDs**

Run:

```bash
pytest tests/test_security_lifecycle_listing_migration.py -q
```

Expected: import failure for the missing migration module.

- [x] **Step 7: Implement the explicit migration**

Follow the existing automation migration discipline, but expose distinct v2
and v3 detection:

```python
def _detect_schema_version(conn: sqlite3.Connection) -> str:
    for version, verifier in (
        ("v3", verify_profile_connection),
        ("v2", verify_v2_profile_connection),
    ):
        try:
            verifier(conn)
            verify_ticker_identity_connection(conn)
            return version
        except (LifecycleSchemaMismatch, TickerIdentitySchemaMismatch):
            continue
    raise ListingMigrationRejected("owned_schema_mismatch")
```

Within one `BEGIN IMMEDIATE`, snapshot all lifecycle rows with explicit hidden
`rowid`, snapshot lifecycle-owned `sqlite_sequence` entries, drop lifecycle
tables in child-first order, create v3 authorities, reinsert every source column
and exact `rowid` without default synthesis, restore the sequence values, verify
row/rowid/sequence digests, counts, and foreign keys, and commit. Leave
ticker-identity tables physically intact while proving their schema and row
digests unchanged. Preserve all unowned row and schema digests before and after.
Backups use SQLite backup,
owner-only `0700/0600` permissions, post-copy logical verification, and exact
SHA-256 binding.

- [x] **Step 8: Run migration tests GREEN and mutation checks**

Run:

```bash
pytest tests/test_security_lifecycle_listing_migration.py tests/test_security_lifecycle_automation_migration.py tests/test_security_lifecycle_automation_schema.py -q
```

Then temporarily remove each new adapter/family/kind from v3 SQL and confirm a
named schema owner fails. Restore each mutation before continuing.

- [x] **Step 9: Commit Task 1**

```bash
git add src/security_lifecycle_schema.py src/security_lifecycle_automation_migration.py src/security_lifecycle_listing_migration.py tests/test_security_lifecycle_automation_schema.py tests/test_security_lifecycle_automation_migration.py tests/test_security_lifecycle_listing_migration.py tests/test_security_lifecycle_disposition.py
git commit -m "feat(lifecycle): define listing authority schema v3"
```

### Task 2: Build Bounded Nasdaq and Massive Transports

**Files:**
- Create: `data_sources/listing_authority_transport.py`
- Create: `tests/test_listing_authority_transport.py`
- Create: `tests/fixtures/listing_authority/nasdaqlisted.txt`
- Create: `tests/fixtures/listing_authority/otherlisted.txt`
- Create: `tests/fixtures/listing_authority/massive-active.json`
- Create: `tests/fixtures/listing_authority/massive-otc.json`
- Create: `tests/fixtures/listing_authority/massive-inactive.json`

**Interfaces:**
- Consumes: `requests.Session` and an API key supplied by the caller.
- Produces: mutable dataclass `ListingRequestBudget` with separate Nasdaq and
  Massive request/byte counters and immutable maximums, plus frozen dataclass
  `ListingHttpPayload(source_url: str, retrieved_at: str, status_code: int,
  content_type: str, body: bytes)`.
- Produces: `ListingRequestBudget.lifecycle() -> ListingRequestBudget`.
- Produces: `ListingAuthorityTransport.fetch_nasdaq(source_url: str, *, budget: ListingRequestBudget) -> ListingHttpPayload`.
- Produces: `ListingAuthorityTransport.fetch_massive_ticker(ticker: str, *, expected_active: bool, market: str, api_key: str, budget: ListingRequestBudget) -> ListingHttpPayload`.
- Produces: `ListingAuthorityTransport.diagnostics(budget: ListingRequestBudget) -> Mapping[str, int]` and `close() -> None`.

- [x] **Step 1: Add transport REDs**

Use an injected fake session and assert exact allowlists and budgets:

```python
def test_transport_allows_only_two_exact_nasdaq_files():
    transport = ListingAuthorityTransport(session=FakeSession())
    budget = ListingRequestBudget.lifecycle()
    transport.fetch_nasdaq(NASDAQ_LISTED_URL, budget=budget)
    transport.fetch_nasdaq(OTHER_LISTED_URL, budget=budget)
    with pytest.raises(ListingTransportFailure, match="nasdaq_request_budget"):
        transport.fetch_nasdaq(NASDAQ_LISTED_URL, budget=budget)


def test_massive_query_secret_never_leaves_the_request_boundary():
    transport = ListingAuthorityTransport(session=FakeSession())
    budget = ListingRequestBudget.lifecycle()
    transport.fetch_massive_ticker(
        "AAPL",
        expected_active=True,
        market="stocks",
        api_key="secret-value",
        budget=budget,
    )
    assert "secret-value" not in json.dumps(transport.diagnostics(budget))
```

Cover wrong host/path, redirect, 8 MiB file cap, 12 MiB Nasdaq aggregate cap,
1 MiB Massive response cap, four Massive requests, exact-ticker normalization,
timeout, 401/403, 404, 429, wrong content type, and malformed response bytes.

- [x] **Step 2: Run transport REDs**

Run:

```bash
pytest tests/test_listing_authority_transport.py -q
```

Expected: missing module failure.

- [x] **Step 3: Implement the transport**

Use exact constants:

```python
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
MASSIVE_TICKERS_URL = "https://api.massive.com/v3/reference/tickers"
MAX_NASDAQ_REQUESTS = 2
MAX_MASSIVE_REQUESTS = 4
MAX_NASDAQ_FILE_BYTES = 8 * 1024 * 1024
MAX_NASDAQ_TOTAL_BYTES = 12 * 1024 * 1024
MAX_MASSIVE_RESPONSE_BYTES = 1024 * 1024
```

Disable automatic redirects. Pass Massive authorization without storing a URL
containing the key: the official REST contract uses the `apiKey` query
parameter, so attach it only in `Session.get(..., params={"apiKey": api_key})`
while keeping `ListingHttpPayload.source_url` canonical and credential-free.
Redact request exceptions before they leave the transport. Normalize all raised
conditions to `ListingTransportFailure` with closed codes and no raw response
body. The request parameters are exactly `ticker`, `active`, `market`, `limit=2`,
and `apiKey`. Reject more than one returned exact ticker; never follow
`next_url`. Use `active=true` to confirm current candidates and `active=false`
to confirm terminal candidates with `delisted_utc`. The persisted canonical URL
contains the first four non-secret parameters in stable order and omits
`apiKey`.

- [x] **Step 4: Run transport tests GREEN**

Run:

```bash
pytest tests/test_listing_authority_transport.py -q
```

Expected: pass with zero network access.

- [x] **Step 5: Commit Task 2**

```bash
git add data_sources/listing_authority_transport.py tests/test_listing_authority_transport.py tests/fixtures/listing_authority
git commit -m "feat(lifecycle): add bounded listing transports"
```

### Task 3: Normalize Listing Evidence and Cross the Fact-Kernel Boundary

**Files:**
- Create: `src/security_lifecycle_listing_evidence.py`
- Modify: `src/security_lifecycle_fact_kernel.py`
- Modify: `src/security_lifecycle_investigation.py`
- Modify: `src/security_lifecycle_translation.py`
- Create: `tests/test_security_lifecycle_listing_evidence.py`
- Modify: `tests/test_security_lifecycle_fact_kernel.py`
- Modify: `tests/test_security_lifecycle_investigation.py`
- Modify: `tests/test_security_lifecycle_translation.py`

**Interfaces:**
- Consumes: `ListingAuthorityTransport`, `ListingRequestBudget`, SEC `IdentityContext`, queried successor tickers, `src.market_sessions.latest_completed_market_date`, and `retrieved_at`.
- Produces: `LISTING_STATUSES = frozenset({"active", "inactive", "not_found", "unverified"})`.
- Produces explicit frozen `ListingEvidence` and `ListingFact` dataclasses that
  implement the field protocol consumed by fact-kernel `_normalize_evidence`
  and `_normalize_facts`, plus frozen dataclass
  `ListingEvidenceResult(evidence: tuple[ListingEvidence, ...], facts:
  tuple[ListingFact, ...], blockers: tuple[str, ...], diagnostics: Mapping[str,
  int])`.
- Produces: `ListingAuthoritySession.lookup(*, context: IdentityContext, candidate_tickers: tuple[str, ...], require_explicit_inactive: bool) -> ListingEvidenceResult` and `close() -> None`.

- [x] **Step 1: Write strict parser REDs**

Add real-shaped fixture tests:

```python
def test_nasdaq_parser_preserves_current_exchange_status_and_document_hash():
    snapshot = parse_nasdaq_directories(
        nasdaq_bytes=fixture("nasdaqlisted.txt"),
        other_bytes=fixture("otherlisted.txt"),
        retrieved_at="2026-08-28T22:00:00Z",
    )
    visn = snapshot.lookup("VISN")
    cde = snapshot.lookup("CDE")
    assert [(row.listing_status, row.primary_exchange) for row in visn] == [
        ("active", "XNAS")
    ]
    assert [row.primary_exchange for row in cde] == ["XNYS"]
    missing = snapshot.lookup("DOESNOTEXIST")
    assert [(row.directory, row.listing_status) for row in missing] == [
        ("nasdaq_listed", "not_found"),
        ("other_listed", "not_found"),
    ]


def test_massive_inactive_requires_explicit_false_and_delisted_date():
    record = parse_massive_ticker(fixture("massive-inactive.json"), "OLD")
    assert record.listing_status == "inactive"
    assert record.delisted_utc == "2026-08-20"
```

Reject missing footer, stale source date, changed headers, duplicate symbol,
invalid exchange code, too many rows, trailing unparsed data, `active=false`
without `delisted_utc`, future delisted date, mismatched returned ticker, a
Massive `next_url`, and invalid CIK/FIGI shapes.

- [x] **Step 2: Run parser REDs**

Run:

```bash
pytest tests/test_security_lifecycle_listing_evidence.py -q
```

Expected: missing module failure.

- [x] **Step 3: Implement canonical records and evidence**

Canonical excerpts use stable JSON with no provider payload surplus:

```python
excerpt = json.dumps(
    {
        "authority": authority,
        "directory": directory,
        "ticker": ticker,
        "listing_status": status,
        "market": market,
        "primary_exchange": primary_exchange,
        "security_type": security_type,
        "issuer_cik": issuer_cik,
        "delisted_utc": delisted_utc,
        "source_as_of": source_as_of,
        "provider_last_updated_utc": provider_last_updated_utc,
    },
    sort_keys=True,
    separators=(",", ":"),
)
```

Hash the exact excerpt. Facts cite byte spans from that exact excerpt. Nasdaq
lookups run first. Massive runs only for the four typed fallback conditions and
is deduplicated inside `ListingAuthoritySession`. A Nasdaq miss produces two
evidence rows, one per complete directory and exact file hash; no aggregate
document digest is allowed. For Massive, lookup time is `source_as_of` and the
provider's optional `last_updated_utc` remains a distinct locator field.
The durable locator also carries `locator_kind`, `adapter`, and
`expected_active_state` so Task 4 can select current material by the exact
component identity without reconstructing request intent from URLs.

- [x] **Step 4: Add adapter contracts to schema-facing validators**

Extend `_ADAPTER_SHAPES` in the fact kernel:

```python
"nasdaq_symbol_directory": ("listing_authority", "listing_directory_snapshot"),
"massive_reference": ("listing_authority", "listing_directory_snapshot"),
```

Extend the investigation store's adapter/family/kind map for readback. Add
closed blocker values:

```text
listing_directory_unavailable
listing_directory_schema_mismatch
listing_directory_stale
listing_status_unresolved
listing_authority_conflict
massive_credential_missing
massive_access_denied
massive_rate_limited
massive_reference_unavailable
```

At the translation preparation boundary, reject
`kind == "listing_directory_snapshot"` with the existing unsupported-content
error immediately after reading the evidence and before cached-translation
lookup, route resolution, provider invocation, or write authority. Add owners
that replace each downstream boundary with functions that fail the test if
called.

- [x] **Step 5: Write producer-to-kernel RED/GREEN contracts**

For each adapter, feed real producer output into `SecurityLifecycleFactKernel.complete_run`:

```python
@pytest.mark.parametrize("adapter", ["nasdaq_symbol_directory", "massive_reference"])
def test_listing_adapter_output_is_accepted_by_real_fact_kernel(adapter, seeded_run):
    result = listing_result_for(adapter)
    kernel.complete_run(
        run_id=seeded_run,
        evidence=result.evidence,
        facts=result.facts,
        blockers=(),
        decision=verified_no_change_decision(),
        diagnostics={},
        retry_at=None,
        at="2026-08-28T22:00:00Z",
    )
    assert persisted_listing_rows(adapter) == 1
```

Mutate the producer excerpt after hashing and mutate one cited span. Each must
fail at the actual kernel validation point with
`evidence_content_sha256` / `fact_citation`.

- [x] **Step 6: Run evidence and kernel tests GREEN**

Run:

```bash
pytest tests/test_security_lifecycle_listing_evidence.py tests/test_security_lifecycle_fact_kernel.py tests/test_security_lifecycle_investigation.py tests/test_security_lifecycle_translation.py -q
```

- [x] **Step 7: Commit Task 3**

```bash
git add src/security_lifecycle_listing_evidence.py src/security_lifecycle_fact_kernel.py src/security_lifecycle_investigation.py src/security_lifecycle_translation.py tests/test_security_lifecycle_listing_evidence.py tests/test_security_lifecycle_fact_kernel.py tests/test_security_lifecycle_investigation.py tests/test_security_lifecycle_translation.py
git commit -m "feat(lifecycle): persist cited listing authority"
```

### Task 4: Replace Market-Quote Gates with Listing-Authority Decisions

**Files:**
- Modify: `src/security_lifecycle_decision_policy.py`
- Modify: `tests/test_security_lifecycle_decision_policy.py`
- Modify: `tests/fixtures/security_lifecycle_grounded_shadow.json`
- Modify: `tests/test_security_lifecycle_grounded_shadow.py`

**Interfaces:**
- Consumes: regulator facts, `listing_authority` facts/locators, optional
  `market_infrastructure` IBKR evidence, current date, and existing transition preview.
- Produces: the existing `AutomationDecision` shape and policy version
  `trusted-lifecycle-automation-v4`.

- [x] **Step 1: Write decision REDs for the complete matrix**

Add a complete parametrized matrix with concrete expected decisions:

```python
@pytest.mark.parametrize(
    ("fixture_name", "tier", "readiness", "outcomes"),
    [
        ("nms_symbol_continuation", "verified_automatic", "transition_eligible", ("symbol_changed",)),
        ("otc_symbol_continuation", "verified_automatic", "transition_eligible", ("symbol_changed", "venue_transfer")),
        ("same_symbol_venue_transfer", "verified_automatic", "not_applicable", ("venue_transfer",)),
        ("terminal_delisting", "verified_automatic", "transition_eligible", ("listing_ended",)),
        ("nasdaq_absence_only", "verified_automatic", "waiting_market_confirmation", ("undetermined",)),
        ("ibkr_conflict", "review_suggested", "action_blocked", ("undetermined",)),
        ("completed_acquirer_active", "verified_automatic", "not_applicable", ("no_tracked_security_change",)),
        ("active_without_sec_role", "review_suggested", "action_blocked", ("undetermined",)),
    ],
)
def test_listing_authority_decision_matrix(fixture_name, tier, readiness, outcomes):
    decision = evaluate_fixture(fixture_name)
    assert decision.decision_tier == tier
    assert decision.action_readiness == readiness
    assert decision.outcomes == outcomes


def test_publisher_evidence_cannot_change_v4_decision():
    baseline = evaluate_fixture("nms_symbol_continuation")
    with_publisher = evaluate_fixture("nms_symbol_continuation", add_publisher=True)
    assert with_publisher == baseline
```

Each test must include a negative sibling that removes one material gate. Add
owners proving that an equal-time disagreement inside one listing component
fails closed, a newer component record supersedes only its own older record,
and stale publisher/general-web/manual facts cannot veto selected current
authority.

- [x] **Step 2: Run decision REDs**

Run:

```bash
pytest tests/test_security_lifecycle_decision_policy.py -q
```

Expected: terminal and continuation tests fail because current policy selects
IBKR as the only current market material.

- [x] **Step 3: Separate listing and broker evidence**

Keep latest-only selection scoped independently per
`(adapter, candidate_ticker, expected_active_state, market)`; never collapse
Nasdaq and Massive or different candidates into one global latest record.
Equal-time disagreement inside one component is a conflict. Add the exact pure interfaces
`_listing_records(evidence, ticker) -> tuple[_Evidence, ...]`,
`_listing_active(evidence, ticker) -> bool`,
`_listing_explicit_inactive(evidence, ticker, today) -> bool`,
`_listing_not_found(evidence, ticker, authority) -> bool`, and
`_listing_conflicts(evidence, ticker) -> tuple[str, ...]`.

Compare facts only when they describe the same identity dimension. Do not count
Nasdaq and Massive as votes; any positive contradiction is a conflict. Build
conflicts only from selected current SEC, listing-authority, and positive IBKR
material. Legacy publisher/general-web facts and stale receipts cannot veto a
v4 decision.

- [x] **Step 4: Implement the matrix and bump policy v4**

Set:

```python
AUTOMATION_POLICY_VERSION = "trusted-lifecycle-automation-v4"
```

Use listing facts for `market_matches`. Remove `_market_snapshot_fresh` as an
acceptance gate. Keep quote freshness only as optional context tests. Terminal
delisting requires both Nasdaq `not_found` and Massive explicit inactive. For a
completed unchanged event, require deterministic SEC role/effect plus active
same-ticker listing. Nasdaq absence without explicit Massive inactivity produces
an automatically maintained `undetermined` Monitoring assessment; it never
persists `listing_ended` and never requests a transition.

- [x] **Step 5: Run decision and shadow tests GREEN**

Run:

```bash
pytest tests/test_security_lifecycle_decision_policy.py tests/test_security_lifecycle_grounded_shadow.py -q
```

Expected: all matrix tests pass; BLBD/CCL/QBTS/HAPN remain restrained and no
fixture depends on publisher evidence.

- [x] **Step 6: Perform policy mutations**

Independently mutate and restore:

1. treat Nasdaq `not_found` as inactive;
2. treat IBKR missing as terminal;
3. restore live-price requirement;
4. allow publisher facts into `market_matches`;
5. ignore a Massive/SEC CIK conflict.

Each mutation must kill a named owner from Step 1.

- [x] **Step 7: Commit Task 4**

```bash
git add src/security_lifecycle_decision_policy.py tests/test_security_lifecycle_decision_policy.py tests/fixtures/security_lifecycle_grounded_shadow.json tests/test_security_lifecycle_grounded_shadow.py
git commit -m "feat(lifecycle): decide from current listing authority"
```

### Task 5: Integrate One Listing Session per Scheduler Tick and Retire News Acquisition

**Files:**
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Modify: `src/security_lifecycle_automation_worker.py`
- Modify: `src/security_lifecycle_disposition.py`
- Modify: `tests/test_security_lifecycle_automation_scheduler.py`
- Modify: `tests/test_security_lifecycle_automation_worker.py`
- Modify: `tests/test_security_lifecycle_disposition.py`
- Keep unchanged: `src/security_lifecycle_news_evidence.py`

**Interfaces:**
- Consumes: Task 3 `ListingAuthoritySession.lookup`, v4 policy, existing SEC and optional IBKR adapters.
- Produces: one lazily fetched Nasdaq snapshot and one shared Massive budget per tick; no publisher evidence/blockers; active source statuses for regulator, listing authority, optional IBKR, and manual.

- [x] **Step 1: Write scheduler REDs**

Add tests that use injected fake sessions:

```python
def test_two_case_tick_fetches_each_nasdaq_directory_once():
    summary = run_tick_with_cases("CASE-A", "CASE-B")
    assert summary["processed"] == 2
    assert listing_transport.urls == [NASDAQ_LISTED_URL, OTHER_LISTED_URL]


def test_v4_scheduler_never_opens_local_news_databases(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", reject_market_news_connection)
    result = load_evidence_for_case()
    assert all(row.source_family != "publisher" for row in result.evidence)
    assert "internal_news_unavailable" not in blocker_codes(result)
```

Also assert missing Massive key is ignored for a Nasdaq-confirmed NMS symbol,
but blocks an OTC/terminal case with `massive_credential_missing`; IBKR
unavailable is diagnostic-only when listing authority is sufficient; IBKR
ambiguity/conflict blocks; and `AUTOMATION_EXECUTION_REVISION` is unchanged.

- [x] **Step 2: Run scheduler REDs**

Run:

```bash
pytest tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_disposition.py -q
```

- [x] **Step 3: Add a tick-scoped lazy session**

Create one explicit tick-local session whose value owns transport, budget,
parsed Nasdaq snapshot, and Massive memoization. Bind it into a per-tick
`evidence_loader` closure passed to `_worker`; close it in `finally`:

```python
session = ListingAuthoritySession(
    transport=ListingAuthorityTransport(),
    budget=ListingRequestBudget.lifecycle(),
    retrieved_at=_timestamp(instant),
    massive_api_key=provider_field_env_value("polygon", "api_key"),
)
try:
    worker = _worker(
        evidence_loader=lambda case, *, mode, at: _load_evidence(
            case,
            mode=mode,
            at=at,
            listing_session=session,
        )
    )
    return _bounded_result(worker.run(limit=limit, mode="live"))
finally:
    session.close()
```

The session fetches nothing until the first selected case calls `lookup`.

- [x] **Step 4: Remove news from `_load_evidence`**

Delete `_local_news_evidence` calls, news diagnostics, publisher source state,
and publisher blockers from the active flow. Do not delete the historical module
or stored vocabulary.

Build candidate tickers from the current case ticker and regulator successor
facts. Run listing lookup after SEC. Query IBKR only when configured and useful;
convert availability/missing results to source status/diagnostics rather than a
decision-blocking error. Preserve positive ambiguity/conflict as a blocker.

- [x] **Step 5: Update monitoring and disposition source families**

Require `regulator` plus the listing components material to the case: Nasdaq for
NMS checks, Massive for OTC continuation and terminal confirmation, and neither
optional Massive nor optional IBKR for an already sufficient NMS result.
Persist component diagnostics separately while projecting their combined active
family as `listing_authority`.
Remove `publisher` from `_pending_event_monitoring`. In disposition, project
only active families:

```python
ACTIVE_SOURCE_FAMILIES = (
    "regulator",
    "listing_authority",
    "market_infrastructure",
    "manual",
)
```

Map new listing/Massive blocker codes to their separate component states under
`listing_authority`; a missing optional component must not make the family
unavailable. Publisher rows in old runs must not create missing/unavailable
source status or affect queue selection.

- [x] **Step 6: Run scheduler/worker/disposition tests GREEN**

Run:

```bash
pytest tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_disposition.py -q
```

- [x] **Step 7: Commit Task 5**

```bash
git add src/service/security_lifecycle_automation_scheduler.py src/security_lifecycle_automation_worker.py src/security_lifecycle_disposition.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_disposition.py
git commit -m "feat(lifecycle): replace news acquisition with listing checks"
```

### Task 6: Expose Concise Listing Evidence and Hide Legacy Publisher Rows

**Files:**
- Modify: `src/tools/security_lifecycle_tools.py`
- Modify: `src/api/routes/security_lifecycle.py`
- Modify: `tests/test_security_lifecycle_tools.py`
- Modify: `tests/test_security_lifecycle_routes.py`
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/lifecyclePresentation.ts`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/lifecyclePresentation.test.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts`

**Interfaces:**
- Consumes: provider-neutral case detail with v3 evidence locator fields.
- Produces: active detail without `publisher`; typed `listing_authority`; compact listing card; translation only for source prose, not structured listing snapshots.

- [x] **Step 1: Write API serialization REDs**

Seed regulator, listing, IBKR, publisher, and manual evidence. Assert:

```python
def test_active_case_detail_uses_the_closed_family_allowlist_but_preserves_storage():
    detail = service.detail("CASE-1")
    assert {row["source_family"] for row in detail["evidence"]} == {
        "regulator", "listing_authority", "market_infrastructure", "manual"
    }
    assert raw_evidence_count("CASE-1", family="publisher") == 1
    assert raw_evidence_count("CASE-1", family="general_web") == 1


def test_listing_locator_is_whitelisted_without_raw_payload_or_secret():
    row = next(item for item in detail["evidence"] if item["source_family"] == "listing_authority")
    assert row["listing"] == {
        "authority": "massive",
        "directory": None,
        "candidate_ticker": "B",
        "listing_status": "active",
        "market": "stocks",
        "primary_exchange": "XNAS",
        "source_as_of": "2026-08-28",
    }
    assert "source_locator_json" not in row
```

- [x] **Step 2: Run API REDs**

Run:

```bash
pytest tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py -q
```

- [x] **Step 3: Implement server-side filtering and explicit listing projection**

Do not filter `SecurityLifecycleReadService.get_case()` or
`SecurityLifecycleInvestigationStore.list_evidence()`: transition, mutation,
and audit callers require complete storage history. Add one outward active-case
projector used by GET list/detail and `_provider_neutral_case`. Before
truncation/counting, allow only `regulator`, `listing_authority`,
`market_infrastructure`, and `manual` evidence and source-family status; this
excludes both legacy `publisher` and inactive `general_web`. Parse only the
closed listing locator keys above before `_provider_neutral_case` removes raw
`source_locator_json`; reject invalid status or authority rather than forwarding
arbitrary locator JSON. Preserve facts, citations, and assessment history.

- [x] **Step 4: Write frontend REDs**

Add fixtures containing all source families and assert:

```tsx
expect(screen.queryByText("Publisher reporting")).not.toBeInTheDocument();
expect(screen.getByText("Listing authority")).toBeInTheDocument();
expect(screen.getByText("Active")).toBeInTheDocument();
expect(screen.getByText("XNAS")).toBeInTheDocument();
expect(within(listingItem).queryByRole("button", { name: /translate/i })).not.toBeInTheDocument();
expect(within(regulatorItem).getByRole("button", { name: /translate/i })).toBeInTheDocument();
```

The same test must distinguish `not_found` as "Not found in this completed
snapshot" / 「在這份完整快照中找不到」 and must not contain "Delisted" /
「已下市」.

- [x] **Step 5: Implement compact listing presentation**

Extend the TypeScript family union with `listing_authority`. Add a compact
definition-list rendering branch for `listing_directory_snapshot`; keep the
existing collapsible original/translation component only for prose evidence.
Keep source links and as-of dates visible. Default all evidence details closed
so only source, ticker, state, venue, and date appear in the scan path. Render
families through the same closed four-family allowlist in fixed order, not raw
insertion order. Citation labels for listing evidence use the compact typed
listing label and never `excerpt.slice(...)`, so canonical JSON cannot leak into
the active UI.

- [x] **Step 6: Run backend and frontend GREEN**

Run:

```bash
pytest tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py -q
npm --prefix apps/arkscope-web test -- LifecycleView.test.tsx lifecyclePresentation.test.ts
npm --prefix apps/arkscope-web run typecheck
```

- [x] **Step 7: Commit Task 6**

```bash
git add src/tools/security_lifecycle_tools.py src/api/routes/security_lifecycle.py tests/test_security_lifecycle_tools.py tests/test_security_lifecycle_routes.py apps/arkscope-web/src/api.ts apps/arkscope-web/src/lifecycle/LifecycleView.tsx apps/arkscope-web/src/lifecycle/lifecyclePresentation.ts apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx apps/arkscope-web/src/lifecycle/lifecyclePresentation.test.ts apps/arkscope-web/src/i18n/resources/en/explore.ts apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts
git commit -m "feat(lifecycle): show concise listing authority"
```

### Task 7: Keep One Profile Credential For Massive

**Files:**
- Modify: `src/data_provider_config.py`
- Modify: `config/.env.template`
- Modify: `tests/test_data_provider_config.py`
- Modify: `tests/test_provider_config_startup.py`
- Modify: `apps/arkscope-web/src/settings/settingsBackendCopy.ts`
- Modify: `apps/arkscope-web/src/settings/settingsBackendCopy.test.ts`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`

**Interfaces:**
- Consumes: provider ID `polygon`, field `api_key`, and existing masked profile storage.
- Produces: user label **Massive (Polygon)** and an explicit one-call test against `api.massive.com`.

- [x] **Step 1: Write credential-authority REDs**

Assert there is exactly one provider field, one process bridge, and no dotenv
import/runtime fallback:

```python
def test_massive_reuses_the_polygon_credential_authority():
    assert [(f.field, f.env_var) for f in PROVIDER_FIELDS["polygon"]] == [
        ("api_key", "MASSIVE_API_KEY")
    ]
    assert importable_env_vars(PROVIDER_FIELDS["polygon"][0]) == ()
    assert "massive" not in PROVIDER_FIELDS
```

Patch `_http_probe` and assert the explicit probe URL begins with
`https://api.massive.com/v3/reference/tickers` and contains no persisted/logged
secret material.

- [x] **Step 2: Run backend Settings REDs**

Run:

```bash
pytest tests/test_data_provider_config.py tests/test_provider_config_startup.py -q
```

- [x] **Step 3: Update the official endpoint and template copy**

Keep the provider ID and profile field unchanged. Use the current process
bridge and user-triggered probe base without reviving the retired alias:

```python
if provider == "polygon":
    key = provider_field_env_value("polygon", "api_key")
    if not key:
        return {"ok": False, "latency_ms": None, "detail": "缺 API key"}
    return _http_probe(
        "https://api.massive.com/v3/reference/tickers?limit=1",
        params={"apiKey": key},
        redact_query_keys={"apiKey"},
    )
```

If the existing HTTP helper cannot keep query secrets out of returned details
and exceptions, extend the helper with the narrow `params` and
`redact_query_keys` contract above. Do not concatenate the key into the URL.

- [x] **Step 4: Write and satisfy frontend label REDs**

Assert both locales render `Massive (Polygon)`, while
the API payload and save call still use `polygon` and `api_key`. Ensure only one
secret input exists in the row.

Run:

```bash
npm --prefix apps/arkscope-web test -- SettingsProviderConfig.test.ts settingsBackendCopy.test.ts
```

- [x] **Step 5: Run Settings gates GREEN**

Run:

```bash
pytest tests/test_data_provider_config.py tests/test_provider_config_startup.py -q
npm --prefix apps/arkscope-web test -- SettingsProviderConfig.test.ts settingsBackendCopy.test.ts
npm --prefix apps/arkscope-web run typecheck
```

- [x] **Step 6: Commit Task 7**

```bash
git add src/data_provider_config.py config/.env.template tests/test_data_provider_config.py tests/test_provider_config_startup.py apps/arkscope-web/src/settings/settingsBackendCopy.ts apps/arkscope-web/src/settings/settingsBackendCopy.test.ts apps/arkscope-web/src/SettingsProviderConfig.test.ts apps/arkscope-web/src/i18n/resources/en/settings.ts apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
git commit -m "feat(settings): present Polygon credentials as Massive"
```

### Task 8: Build Offline Shadow, Mutation, Browser, and Migration Admission

**Files:**
- Create: `docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority/README.md`
- Create: `docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority/run_shadow.py`
- Create: `docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority/run_mutations.py`
- Create: `docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority/run_browser_matrix.py`
- Create: `docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority/capture_offline_authority.py`
- Create: `docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority/commands.txt`
- Create at runtime: bounded JSON/text results, browser PNGs, and `SHA256SUMS` in the same directory.

**Interfaces:**
- Consumes: Tasks 1-7 and only repository fixtures/temporary SQLite databases.
- Produces: deterministic packet with schema v2/v3, scratch migration/restore,
  decision matrix, mutations, browser matrix, full gates, and declared zero live authority.

- [x] **Step 1: Write the offline authority observer**

Patch and calibrate every forbidden boundary before running scenarios:

```python
FORBIDDEN = (
    "requests.sessions.Session.request",
    "data_sources.sec_transport.SecTransport.get",
    "src.security_lifecycle_ibkr_evidence.read_ibkr_contract_evidence",
    "data_sources.listing_authority_transport.ListingAuthorityTransport.fetch_nasdaq",
    "data_sources.listing_authority_transport.ListingAuthorityTransport.fetch_massive_ticker",
    "src.security_lifecycle_listing_migration.migrate_listing_authority_schema",
)
```

Calibration must invoke and intercept every patched target in a disposable
context. The packet labels zero provider/production/merge/push values as
`declared_not_authorized`, not measured runtime facts.

- [x] **Step 2: Build shadow fixtures**

Use exact offline payloads for:

```text
HAPN  LC -> HAPN, active XNAS, already normalized: no transition preview
QBTS  same symbol venue transfer: notify, no remap
CCL   completed issuer event, active same symbol: no tracked change only with SEC role fact
BLBD  asset acquisition, active same symbol: no tracked change
NMS-A synthetic old -> new active XNYS: eligible reversible transition preview
OTC-A synthetic old -> new active OTC: eligible only with Massive active OTC
TERM  synthetic Form 25 + Nasdaq not_found + Massive inactive: eligible terminal preview
MISS  synthetic Form 25 + Nasdaq not_found + no Massive: Monitoring
CONFLICT synthetic SEC/Listing CIK mismatch: attention, no preview
```

Assert publisher evidence injection changes no v4 output and
`transition_preview_calls == 0` for all non-transition examples.

- [x] **Step 3: Add named mutations**

The ledger must apply and restore each mutation independently and require one
or more named owners to fail. Include at least:

```text
M01 remove nasdaq host/path allowlist
M02 turn Nasdaq not_found into inactive
M03 accept a missing Nasdaq footer
M04 ignore Nasdaq file freshness
M05 follow Massive next_url
M06 log Massive API key
M07 accept Massive inactive without delisted_utc
M08 remove producer-to-kernel hash validation
M09 remove producer-to-kernel citation validation
M10 select one latest listing record and discard the rest
M11 allow IBKR missing to prove delisting
M12 require a fresh quote for listing acceptance
M13 allow publisher evidence into v4 material
M14 restore publisher as pending-monitoring required family
M15 expose publisher evidence through active detail
M16 translate a listing snapshot
M17 add a second Massive secret field
M18 fail to preserve one v2 publisher row during migration
M19 change one v2 translated-text byte during migration
M20 allow a v3 binary to verify a v2 database without migration
```

- [x] **Step 4: Build the browser matrix**

Record desktop `1440x900` and mobile `390x844`, English and Traditional Chinese,
for active, not-found Monitoring, explicit inactive History, conflict Attention,
OTC continuation, and Settings Massive key. Assert zero console/page errors,
zero external requests, no publisher family text, no listing translation button,
no render acknowledgement, and no command calls.

- [x] **Step 5: Run focused gates twice**

```bash
pytest --basetemp=/tmp/arkscope-listing-focused-a \
  tests/test_listing_authority_transport.py \
  tests/test_security_lifecycle_listing_evidence.py \
  tests/test_security_lifecycle_listing_migration.py \
  tests/test_security_lifecycle_fact_kernel.py \
  tests/test_security_lifecycle_decision_policy.py \
  tests/test_security_lifecycle_automation_scheduler.py \
  tests/test_security_lifecycle_automation_worker.py \
  tests/test_security_lifecycle_disposition.py \
  tests/test_security_lifecycle_tools.py \
  tests/test_security_lifecycle_routes.py -q
pytest --basetemp=/tmp/arkscope-listing-focused-b \
  tests/test_listing_authority_transport.py \
  tests/test_security_lifecycle_listing_evidence.py \
  tests/test_security_lifecycle_listing_migration.py \
  tests/test_security_lifecycle_fact_kernel.py \
  tests/test_security_lifecycle_decision_policy.py \
  tests/test_security_lifecycle_automation_scheduler.py \
  tests/test_security_lifecycle_automation_worker.py \
  tests/test_security_lifecycle_disposition.py \
  tests/test_security_lifecycle_tools.py \
  tests/test_security_lifecycle_routes.py -q
```

Expected: both pass with identical collected node sets.

- [x] **Step 6: Run complete gates twice**

```bash
pytest --basetemp=/tmp/arkscope-listing-full-a -q
pytest --basetemp=/tmp/arkscope-listing-full-b -q
npm --prefix apps/arkscope-web test
npm --prefix apps/arkscope-web run typecheck
npm --prefix apps/arkscope-web run check:i18n-literals
npm --prefix apps/arkscope-web run build
```

Expected: zero failures; backend collection counts match across both runs.

- [x] **Step 7: Run scratch migration and old-code restore probes**

Create a v2 fixture database with rows in every owned table. Run v2 preflight,
backup, v3 migration, v3 startup verifier, restore, and v2 startup verifier. No
production path may appear in the report. Assert exact row/cell digests and
foreign-key integrity at every stage.

- [x] **Step 8: Run mutation and browser packets**

```bash
python docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority/run_mutations.py
python docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority/capture_offline_authority.py
npm --prefix apps/arkscope-web run dev -- --host 127.0.0.1 --port 4208 --strictPort
ARKSCOPE_LISTING_APP_URL=http://127.0.0.1:4208/ python docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority/run_browser_matrix.py
```

The checked-in `commands.txt` must start Vite in the background, capture its
PID, install an `EXIT` trap, wait for readiness, run the browser matrix, and
terminate that exact process before proceeding. The two foreground commands
above document the components only; they are not the unattended packet runner.

- [x] **Step 9: Seal and verify the packet**

Generate `SHA256SUMS` from the exact file allowlist, verify every hash, and
assert the manifest set equals the disk set. The README must list known limits:
no live SEC/Nasdaq/Massive/IBKR call, no real production A-to-B execution, and
no production migration.

- [x] **Step 10: Commit Task 8**

```bash
git add docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority tests/fixtures/listing_authority
git commit -m "test(lifecycle): admit listing authority offline"
```

### Task 9: Stop at the Live Authorization Boundary

**Files:**
- Modify after GREEN: `docs/design/PROJECT_PRIORITY_MAP.md`
- Do not modify: production databases, runtime processes, remote branches.

**Interfaces:**
- Consumes: sealed Task 8 packet and clean branch.
- Produces: an exact user-facing authorization inventory; no live action.

- [x] **Step 1: Record offline GREEN without claiming live admission**

Add a dated decision-log entry that states the branch tip, exact gate counts,
packet digest, schema version, policy version, and all unexercised live paths.
Do not mark production cutover complete.

- [x] **Step 2: Verify branch and boundary state**

Run:

```bash
git status --short --branch
git log --oneline --decorate --no-merges master..HEAD
git diff --check master...HEAD
git branch -r --contains HEAD
```

Expected: clean feature branch, linear commits, no remote branch containing the
tip, and no whitespace errors.

- [x] **Step 3: Report the six separate next decisions**

Report, without executing:

1. read-only production v2 inventory;
2. bounded live Nasdaq/Massive/IBKR canary;
3. production migration preflight/backup/restore/migration;
4. fast-forward merge;
5. App restart/cutover and bounded case replay; and
6. push.

Include the exact expected provider request caps and the rollback consequence
that v2 code requires restoring the bound v2 backup after schema v3 migration.

**2026-08-29 offline closeout:** Product/controller authority `ce9c9dd5` was
replayed from a clean tree and sealed by evidence commit `c77d3407`. The packet
digest is `18d0a4ee8e666319e897fd313fa6199a04c6cb674fbd2946ee7136d11c09248d`.
It records schema v3, automation policy
`trusted-lifecycle-automation-v4`, `45/45` killed mutations, focused A/B
`358P`, backend A/B `4894P/13S/0F` with identical 4,907-node manifests,
frontend `106 files/1306P`, packet contracts `25P`, and 24 browser entries
with zero measured external requests, writes, overlap, clipped text, or
console/page errors. The 63-file seal and an independent secret rescan both
verify with zero findings. This is offline admission only.

The six remaining actions are still independent decisions and were not
performed by this plan:

1. read-only production v2 inventory;
2. bounded live Nasdaq/Massive/IBKR canary (a prior four-request Massive
   observation is unsealed and does not substitute for this combined gate);
3. production v3 migration preflight, bound backup, restore probe, and
   migration;
4. fast-forward merge;
5. App restart/cutover plus bounded case replay; and
6. push.

The provider ceilings are Nasdaq at most two requests per tick, 8 MiB per
file and 12 MiB aggregate; Massive at most four requests per tick, 1 MiB per
response and 4 MiB aggregate; and optional IBKR at most eight contract queries
plus one market-data request under the broker lock. An IBKR missing-contract
result never proves delisting. After a schema v3 migration, rolling code back
to v2 requires restoring the bound v2 database backup and therefore discards
all profile writes made after that backup.

### Task 10: Close Post-Admission Credential And Seam Findings

**Hard boundary:** no provider call, production DB operation, App restart,
merge, or push. The four earlier Massive observations were explicitly
authorized in the user thread, but retained no provider bytes and are not
packet admission evidence.

- [x] Make `polygon.api_key` the sole durable Massive authority and
  `MASSIVE_API_KEY` its sole process bridge. Remove `POLYGON_API_KEY` runtime
  fallback and Massive reads/imports from `config/.env`. Preserve existing
  profile rows exactly.
- [x] Add a real transport-to-parser timestamp contract owner and prove it
  kills an `isoformat(sep=" ")` mutation.
- [x] Add real policy-admission owners for source family and locator kind and
  prove they kill broadened `_listing_snapshot` mutations.
- [x] Re-evaluate adjacent blocker classification, compact-reader, and
  provider-as-of semantics against the same normalized listing contract.
- [x] Rebuild the sealed packet and all gates before requesting merge.

**2026-08-30 Task 10 closeout:** Product/controller authority
`63ceb8cb5ab08b262926a3dd36ed21096ea81f49` was replayed from a clean
tree. The resulting 67-file packet digest is
`83f1f2cf22b74fa86272e8441eae58617a509e379dd61b060c07187ffc036055`.
It records `51/51` killed mutations, focused backend A/B `362P`,
full backend A/B `4898P/13S/0F` with identical 4,911-node manifests,
frontend A/B `106 files/1306P`, clean typecheck/i18n/build gates, and
24 browser entries with zero measured external requests, writes, overlap,
clipped text, console errors, or page errors. Provider calls, production DB
operations, App restart, merge, and push remained unexecuted.
