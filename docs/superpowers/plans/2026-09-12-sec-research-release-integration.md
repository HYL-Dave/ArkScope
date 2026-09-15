# SEC Research Release Integration Implementation Plan

2026-09-15 hand-test follow-up supersedes the embedded Settings reader and the
v4-only TOC discussion in this historical plan. Settings now exposes local
automatic filters and official browser links. Model/citation paths remain;
new plain-label linked-table observations use extraction v5 without modifying
retained captures. See the [current hand-test checklist](2026-09-15-sec-current-runtime-hand-test.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Finish usable SEC Research, all four transports and its recovery paths.
**Architecture:** Reuse the reviewed immutable source/document stores. Put issuer
resolution, freshness and bounded acquisition in one tool service; adapters share
that service. Persist exact references before admitting maintenance operations.
**Tech Stack:** Python/SQLite/FastAPI, existing SEC transports, React/TypeScript.
**Spec:** `docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md`.

Status: Tasks1/2/3/4/5/6/7 reviewed complete; Task2 uses the approved shared output
boundary. Its former SEC-specific redaction proposal is superseded, not
an outstanding authorization request. Source checkpoint `ba4f2619` is preserved;
integration proceeds on `codex/sec-research-integration` from security `41682675`.
See [integration evidence](../evidence/2026-09-12-sec-integration/README.md).
Implementation authorized by the existing spec and
the user's continuation. User asks to finish the remaining release,
including TOC quality, four-channel wiring and both recovery workflows.

Base: `c997a6c9817b80857ba7211989cdf6412d3b1003` in the existing isolated
`/tmp/arkscope-listing-sec-macro-convergence` worktree, branch
`codex/listing-sec-macro-convergence`. Baseline: 9180 backend nodes, 9168 passed /
12 unchanged skips; frontend 1776 passed. Earlier verified document work is not
redispatched. Specification: `docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md`.

## Global Constraints

- No production DB/config/.env/token access, real provider calls, installation,
  App restart, merge or push. Tests use isolated disposable stores and injected
  transport responses; implementation approval is not destructive rollout approval.
- Preserve prices/news/SA/financial_cache, present lifecycle decisions and
  research history. No model, auth, effort default or transport fallback change.
- One canonical SEC schema; mismatch is explicit. No startup repair/DROP,
  hypothetical legacy execution lane or migration chain. Retained data is not
  disposable merely because the product is pre-release.
- All three SEC tools use the existing `analysis` category and closed envelopes:
  status, data, gaps, observed_at, coverage, next_cursor. No bare-list empty
  success. Stored/pinned reads acquire nothing; revalidation never replaces pins.
- Preserve exact Decimal TEXT, immutable source hashes, UTF-8 half-open passage
  ranges, complete citation envelopes, snapshot/filter-bound cursors and current
  32 MiB wire /128 MiB decoded per-response document limits. Capture budget stays
  adjustable 100 GiB by default. No general bridge-budget increase.
- New ticker resolution is issuer metadata, not a ticker identity/rename signal.
  Ambiguity must not be collapsed to an arbitrary CIK. SEC contact/pacing use the
  existing profile-owned configuration and transport, not an env fallback.
- Three-tool replacement is atomic across registry, both API adapters, both
  OAuth allowlists, subagent inventories, seven current skills and tool catalog.
  Required tools must not silently disappear in filtering.
- Persist references before recovery admits deletion. Cleanup rechecks all
  snapshot/document/Research citation/pin/export references under coordination;
  schema reset backs up, checks live users and protects unrelated objects.
- TOC recognition requires structural evidence. Do not choose a duplicate
  heading by position or loosen ambiguity checks. Full text remains available.
- RED first with an assertion failure for the intended missing behavior, then
  focused GREEN, named inverse where the new boundary is load-bearing. Preserve
  exact commands/logs/source identities and reconcile removed/added tests.
- Only the current implementation worker owns product edits and the Git index.
  No worker/reviewer subagents; independent controller-dispatched reviews.

## Milestones

1. Issuer resolution and the three real tool contracts.
2. Atomic four-channel/subagent replacement with citation-safe result sizing.
3. Durable Research citation references and reopen UI.
4. Structural TOC detection.
5. Portable export/restore and reference protection.
6. SEC-RECOVERY-001/002: operator cleanup/reset after Tasks 3 and 5, before the
   release verification gate, not a future unspecified batch.
7. Default-disabled current-universe catalog/facts schedule and Settings.
8. Remaining live-entrypoint cleanup, fresh complete verification, census,
   review and evidence. Actual-store destructive rollout remains separate.

## Progress

- [x] Preflight and exact task contracts
- [x] Task 1: issuer/tool service (2d54a482,38529e51; focused835P; independent review approved)
- [x] Task 2: four-channel replacement (5d979910; focused994P, independent scoped re-review51P; full-release gate remains Task8)
- [x] Task 3: persistent Research citations (7401e656; sealed acceptance10583P/12S, frontend1824P)
- [x] Task 4: TOC recognition (ba5a3356,5518ae21; focused338P; independent review approved)
- [x] Task 5: operation leases/export/restore (4dfa0d37; independent review approved; final continuation10827P/12unchangedS, frontend1830P)
- [x] Task 6: cleanup/reset (78157e62; covering1064P, scoped review approved; same complete continuation gate passed; interrupted-publication follow-up d2f491c1 independently approved with1092 focused passes; actual-store rollout unperformed)
- [x] Task 7: schedule/Settings (936ede10,883b0185; focused2493P/449P; independent scoped re-review approved; full release gate remains Task8)
- [ ] Task 8: N1/P2 and route collateral closed by the September 14 follow-up; full Linux backend11050P/12unchangedS at39b6587f, frontend1833P; broader final-release checklist and actual activation are not implied complete

### Resolved Security Dependency

The user approved the shared output-boundary design, implemented and separately
reviewed at `41682675`. The abandoned SEC exemption is not an implementation
option. Diagnostics retain their strict scrubber; successful research data uses
exact-credential and common result-policy admission. The historical four OAuth
failures/758 passes explain the pause, not the current state or an open decision.

`ba4f2619` commits the complete former dirty checkpoint; `3fef138d` replays it on
the security base. `88f0512e` integrates common policies and the SEC-owned OAuth
deadline. Review found two additional actual execution defects, repaired in
`5d979910`: the native Anthropic stream must await SEC tools rather than nest
`asyncio.run`, and metadata/map cancellation must reach governor waiting and
dispatch/body/retry checkpoints. Tests now exercise the actual SDK tool-result
roundtrip and both ticker/CIK cancellation paths. The latest focused run is
994 passed; independent scoped re-review returned 51 passed with no correctness
findings. Original source branches stay
intact, and no source implementation remains solely in an untracked checkpoint.

The remaining release work is now Task8. Task3's retained references and
query-only closure are delivered at7401e656; Tasks5/6 source implementation is
accepted through78157e62. See the citation and maintenance evidence below.
The default-disabled schedule is implemented and reviewed through883b0185;
actual-store rollout
is not authorized by completing source implementation.
The integration checkpoint passed a fresh complete backend run at `ae2055e3`:
10279 passed/12 unchanged skips, exactly10291 collected/executed,123 added and10
removed against the security base. The first complete attempt's two stale-count
failures and their RED-first correction remain in evidence. Frontend1776 passed
and typecheck passed. This verifies completed changes, not unfinished release
Tasks3/5/6/7. No production change, merge or push occurred. Wider repository
cleanup and production SQLite upgrade are not represented as finished.

### September 13 Interrupted Publication Repair

User review exposed a real missing recovery window after object hardlink
publication but before registration. The unchanged178-pass baseline did not
cover it: a disposable two-window probe returned1failed/1passed. The before-
register pair retained nlink2, blocking cleanup of unrelated orphans as well.

`d2f491c1` repairs only a proven canonical object/staging alias after accounting
commits. It retains the first validated inode identity through hashing and the
pre-unlink recheck, syncs the staging directory, and never loosens strict admin
inventory. Registered reads, standalone stages, foreign links, corruption,
replacement, accounting/unlink/fsync failures and actual concurrent market
writers have separate owners. Restored-source covering is1092passed; the
inverse omitting the new call gives2intended failures/2controls passed.
Independent task review approved both compliance and quality with no findings.
This is a focused source repair, not a fresh complete backend or live-store run.
Previews remain read-only and must be regenerated after writer recovery.

### September 13 Maintenance Continuation

Task3 acceptance is sealed in
`../evidence/2026-09-13-sec-research-citations/README.md`: exact10595 backend
nodes,10583 passed/12 unchanged skips, frontend1824 passed. Its iterator reads
retained Research messages and events, including archived/event-only roots;
`sec_reference_closure` verifies their exact stored graph without acquisition.

The existing `capture_writer` is not the maintenance exclusion boundary:
`CaptureStore.put` releases it before service metadata/reference publication,
and `CaptureStore.read` uses descriptor-bound I/O without that writer lease.
Task5's operation lease protects those lifetimes and durable Research publication;
it is not another refresh mutex or a scheduler job lock. Keep Task6 after Task5
so cleanup/reset cannot race a reader, producer or export. Do not infer that the
availability of citation roots alone admits deletion. SQLite activation remains
outside this plan's explicit no-install/no-production-write boundary; the
source-only admission preflight still applies.

Tasks5/6 now pass independent task reviews and the complete maintenance
continuation gate at78157e62: **10827 passed/12 unchanged skips**, exact10839
collected/executed,244 added/0 removed from citation acceptance. All1151 frozen
source/test/resource paths and the runtime/runner match before/after. Frontend
**1830 passed**, typecheck/build/i18n pass. Original RED, intermediate failures,
review repairs and exact inverse-restoration receipts are retained in
`../evidence/2026-09-13-sec-research-maintenance/README.md`.
The operator runbook is `docs/design/SEC_RESEARCH_OPERATIONS.md`. Source-only
census remains review_required; this is not Task8 whole-release acceptance,
master-merge approval, actual-store cleanup/reset or SQLite activation.

## Verification Commands

All commands run in the isolated worktree. Use the hash-verified copies of the
previous tracked runner under this plan's scratch; never run tests against real
stores. `run_checks.py` creates each run directory only once. Use new names for
RED/GREEN/inverse/fix checkpoints, keep failed checkpoints as evidence. Example:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task1-red backend -q tests/test_sec_research_tool_service.py
```

The existing source controls already pass: corrected baseline command runs
`tests/test_sec_tools.py tests/test_subagent.py tests/test_sec_research_store.py
tests/test_sec_research_service.py`, 240 passed. The initial command mistakenly
named nonexistent `test_sec_research_schema.py`; zero tests ran, not a product
failure. Schema controls are in `test_sec_research_store.py`.

### Task 1: Issuer Resolution And Tool Service

**Files:** Create `src/sec_research/issuers.py`, `issuer_store.py`,
`tool_service.py`, `runtime.py`, `src/tools/sec_research_tools.py`;
modify `src/sec_research/schema.py`, `data_sources/sec_transport.py` and SEC route
transport construction for the narrow retry option below; tests
`tests/test_sec_research_issuers.py`, `test_sec_research_tool_service.py`,
`test_sec_research_store.py`, `test_sec_transport.py`, and the existing route
constructor double in `test_sec_research_routes.py` (accept and assert the
research no-retry option). Keep old tool registration
until Task 2.

**Interfaces:** `parse_issuer(value: str) -> tuple[str, str]` returns kind
`cik`/`ticker` and normalized value. CIK normalization uses existing common owner;
bare one-to-ten ASCII digits remain accepted as explicit CIK. Tickers use the
current SEC map's exact uppercase form `[A-Z0-9][A-Z0-9.\-]{0,19}`; no dot/hyphen
alias guessing. `parse_ticker_map(body: bytes) -> dict[str, tuple[str, ...]]`
validates the official `company_tickers.json` object, preserving duplicate-symbol
CIKs as ambiguity, not last-write-wins. Retain raw body hash and observation time
in canonical immutable issuer-map records, charged through CaptureStore. A failed
attempt is not an empty successful map and cannot be hidden by an older map.

`IssuerStore(store).resolve(issuer: str) -> dict` is a stored-only resolution
observation containing `status,cik,candidates,observed_at,source,gaps`; the source
contains official URL and body hash. `refresh(transport,captures,*,clock,check)`
performs at most one governed map request, no retries and no unrelated providers.
Map refresh uses a separate root-scoped issuer-map lease, not a market write lock
during network I/O. Explicit CIK never requires the map.

Preflight found `SecTransport.get` currently retries one429 by default. Add a
narrow constructor `max_rate_limit_retries: int=1` accepting only0/1 (not bool).
Keep1 for existing consumers; use0 in SEC research runtime/route composition.
The no-retry request budget cannot be proven by counting facade calls alone.
Test actual transport dispatch counts on429 and the positive existing default
control; no change to the governor, redirect policy or unrelated SEC consumers.

`ToolService(store, *, acquisition_factory, clock)` exposes
`invoke(name: str, arguments: dict, *, check=None) -> dict`. The lazy
`acquisition_factory()` returns a context manager of
`(captures, transport, reader_factory)` with validated profile SEC identity and
budget. No config/transport/schema creation until acquisition is needed.
`runtime.build_tool_service()` supplies the normal path/config owners. A narrow
runtime adapter may import the existing profile/data-provider dependencies and
permission choke point; domain query/parser modules may not import API routers.
Before additive acquisition call `require_db_write`, not a new permission system.

`src/tools/sec_research_tools.py` exposes the specification's three exact public
signatures (all return dict):

```python
def list_sec_filings(issuer, forms=None, filed_from=None, filed_to=None,
                     include_amendments=True, cursor=None, limit=20, freshness="auto"):
    return build_tool_service().invoke("list_sec_filings", dict(
        issuer=issuer, forms=forms, filed_from=filed_from, filed_to=filed_to,
        include_amendments=include_amendments, cursor=cursor, limit=limit,
        freshness=freshness))

def get_sec_financial_facts(issuer, metrics=None, concepts=None, fact_ids=None,
                          accession=None, as_of=None, period="all", start=None,
                          end=None, revisions="latest", cursor=None, limit=40,
                          freshness="auto"):
    # Same thin argument delegation; all selection stays in StoredQueries.
    return build_tool_service().invoke("get_sec_financial_facts", locals())

def read_sec_filing(filing_id, document_id="primary", section_id=None, query=None,
                    capture_id=None, cursor=None, max_chars=6000, freshness="auto"):
    return build_tool_service().invoke("read_sec_filing", locals())
```

Explicit schema types/docstrings are required for the handwritten adapters; this
example shows delegation, not a second parser. Validate all arguments, including
query/cursor syntax and freshness, before resolution/storage/network. Use only
closed failure codes, never exception text or profile secrets.

**Freshness policy:** 24 hours is application policy for issuer maps and
structured receipts, not a claim about SEC publication timing. `stored` never
acquires/installs. `auto` uses suitable recent observations; absent/stale metadata
gets one bounded refresh (`max_sources=4`), or resumes a current partial traversal
with pending sources. `refresh` starts revalidation. No same-call retry loop.
Documents are accession-specific: auto reuses an existing admitted capture;
explicit refresh makes a new observation. Every cursor, fact-ID reopen and
capture pin is stored-only even with default auto; reject explicit refresh for
such operands before I/O. Resolve ticker continuations against the cursor's
original CIK, not a newly downloaded map. Initial read by filing ID may obtain
its catalog before directory/document acquisition, within one structured refresh.
Missing captured secondary documents use their actual observed file ID; no URL
argument. Failed latest observations must not borrow old success.

- [ ] Write assertion-first owners in the two new test files. Use `find_spec` or
  guarded import in the initial owner so missing modules yield an assertion RED,
  not import collection errors. Real temporary Store/CaptureStore, generated raw
  JSON and injected transports, not mocks returning final envelopes.

```python
def test_ambiguous_map_never_selects_last_cik(issuer_fixture):
    result = issuer_fixture.resolve_duplicate_symbol()
    assert result["status"] == "unavailable"
    assert result["cik"] is None
    assert len(result["candidates"]) == 2

def test_stored_and_pinned_calls_never_open_acquisition(tool_fixture):
    result = tool_fixture.read_stored_fact()
    assert result["data"][0]["value"] == "1234567890123456789.123"
    assert tool_fixture.acquisitions == []
```

Also name `test_invalid_query_rejected_before_resolution`,
`test_cursor_survives_ticker_map_change`,
`test_failed_refresh_does_not_borrow_old_success`,
`test_one_map_plus_bounded_metadata_requests`,
`test_auto_resumes_partial_without_retrying_in_same_call`,
`test_document_pin_rejects_refresh_before_io`,
`test_cancel_stops_before_next_source`,
`test_missing_contact_never_installs_or_dispatches`,
`test_research_rate_limit_is_one_attempt_with_no_sleep_retry`,
`test_existing_transport_default_keeps_reviewed_retry`.
- [ ] Run named RED and record actual expected missing-contract assertion.
- [ ] Implement minimal typed map/store and service over existing queries,
  ResearchService, DocumentQueries and DocumentService. Validate/close resource
  lifetime; schema mismatch remains explicit. Keep every useful existing source
  parser/financial route unchanged. New successful map is an immutable observation.
- [ ] Run focused GREEN plus existing store/service/query/document tests. Prove
  inverses: replace ambiguity with first CIK; acquire in stored mode; allow refresh
  on pin; ignore cancelled check. Each kills its named owner, restored hashes.
- [ ] Commit scoped files and report exact commands/results/request counts and
  schema objects added. No complete-release claim from service-only delivery.

### Task 2: Atomic Four-Channel Replacement

**Files:** Modify registry, OpenAI/Anthropic tool adapters, both OAuth drivers,
`src/agents/shared/subagent.py`, shared compressor reducers/layers only at the SEC
result boundary; `src/sec_research/queries.py`, `fact_queries.py`,
`document_queries.py`, `tool_service.py`; create
`src/sec_research/tool_execution.py`, `tool_results.py` if needed for clear shared
ownership. Update seven skill files named in spec section 9 and
`docs/design/ARKSCOPE_TOOL_CATALOG.md`. Remove old `get_sec_filings` in
`src/tools/sec_tools.py` in this same change, preserving get_insider_trades.
Also remove the empty `/sec/{ticker}` route in `src/api/routes/fundamentals.py`
and its unused forwarding chain in `src/tools/analysis_tools.py`, `data_access.py`
and `src/tools/backends/{__init__,local_capabilities,file_backend,local_market_backend}.py`
(`query_sec_filings`) after exact consumer verification. Remove the now-unused
`src/tools/schemas.py::SECFiling` and its imports, not the distinct live
`data_sources/base.py::SECFiling`. In `data_sources/sec_edgar_financials.py`,
remove only the old `get_filings_list` method/module wrapper, its private
`FilingInfo` record and examples once the direct tool is removed; the inspected
full-tree references have no independent consumer. Preserve the working
SECEdgarFinancials facts/statement mapper and SECEdgarDataSource.
Update the current EDGAR section in `data_sources/API_SPECIFICATIONS.md` with
the new tool entrypoints, not historical decision records. Evolve old empty-stub
owners in `tests/test_api.py`, `test_data_access.py`, `test_tools.py` to absence
plus live new catalog controls; retain backend protocol conformance coverage.
No compatibility alias/redirect/stub remains.
Tests: create `tests/test_sec_research_tool_adapters.py`,
`test_sec_research_tool_results.py`; modify `test_subagent.py`, `test_sec_tools.py`
and the original eight count-collateral files plus the additional lifecycle and
shared-policy owners in the table below. The first complete integration run
exposed three previously missed count assertions in the two lifecycle files;
the original eight-file inventory was incomplete, not an existing test failure.

**Interfaces:** Consume Task 1's three public functions and ToolService. All use
`category="analysis"`, no DAL argument (`requires_dal=False`). The common
`invoke_sec_tool(name, arguments, *, timeout_s=None) -> Awaitable[dict]` owns SEC
worker cancellation and checks; it runs the actual tool service, not an adapter
fixture that returns invented results. Thread context is copied explicitly.
Timeout/cancel signals a cooperative stop, asks active readers to stop, awaits
the owned worker before returning, and never dispatches another source afterward.
Do not change cancellation/executor behavior of unrelated tools.

Add internal `result_fits(envelope) -> bool` query pagination control (default
None preserves HTTP 256 KiB envelope bound). Tool execution uses the minimum of
the active configured Layer0 budget and the existing 12,000-character OAuth caps,
measuring final serialization/wrapping. The inspected Layer0 default is 8,000,
so the OAuth cap alone is insufficient. Size complete
rows/passages/citations in the domain pager, keeping correct continuation offsets
and unchanged user filters. Never shrink user limit/max_chars behind a cursor's
back. When a single record plus full provenance cannot fit, emit an explicit
whole-record size gap and a valid advancing continuation, not mid-JSON truncation.
An oversized envelope alone returns a small closed unavailable result. Budgets
are per-call, no mutable module-global limit. No new result cap on unrelated tools.

The SEC reducer validates/returns a whole envelope. On malformed or oversized SEC
input it emits a small typed failure, never generic head/tail truncation. Ensure
Layer0/Layer5 and both OAuth bridges select it for SEC names. Existing security
wrapping remains. Shared exact-secret/result-policy admission replaces diagnostic
redaction on successful data. Credential-bearing or invalid structures fail with
typed errors; a cited passage is never silently rewritten. Diagnostics retain
their separately reviewed strict redaction policy.
Keep optional non-SEC omissions separate from required-SEC inventory failures.
An OAuth driver with `registry=None` is an existing intentional tool-free mode
used by model-task canaries and investor-profile calibration, not a broken
Research registry. Preserve that mode and test actual driver behavior. A supplied
Research registry lacking the new required tools must still fail explicitly.

| File | Required count collateral |
|---|---|
| tests/test_agents.py | 55->57 twice, 54->56 twice; exact names |
| tests/test_analyst_tools.py | 54->56, analysis15->17 |
| tests/test_api.py | tools_registered54->56 from actual registry |
| tests/test_memory_tools.py | 54->56 |
| tests/test_portfolio_tools.py | 54->56 |
| tests/test_sa_tools.py | 54->56 four times, 55->57 once |
| tests/test_sec_tools.py | 54->56, analysis15->17; move old owners to new contracts |
| tests/test_tools.py | 54->56 three times, analysis15->17; exact names |
| tests/test_security_lifecycle_routes.py | Entire App route count224->223 after old /sec/{ticker} removal; retain exact lifecycle/SEC route sets and assert old route absent |
| tests/test_security_lifecycle_tools.py | Both Research OAuth allowlist counts15->17; retain lifecycle tools, require three SEC names, reject old get_sec_filings |
| tests/test_tool_output_policy.py | Shared inventory56 =49 ordinary JSON +3 closed SEC JSON +4 text; no SEC redaction exception |

- [x] Write RED `test_each_research_transport_dispatches_three_real_sec_tools`
  parameterized for the actual OpenAI FunctionTool invocation, Anthropic dispatch,
  ChatGPT `_invoke_tool` and Claude `_invoke_bridged_tool` entry. Inject only acquisition
  transports/runtime-store construction, keep actual service and serialization.

```python
def test_all_subagent_tool_names_exist_in_registry(registry):
    for spec in all_subagent_specs():
        assert set(spec.tool_names) <= set(registry.names())
```

Use the actual registry API when implementing; extract the existing assertion in
`test_code_analyst_uses_existing_data_tools_without_python_execution`, do not leave
two owners for the same assertion. Add actual filtered inventory/dispatch owners.
Name `test_sec_pages_remain_complete_json_through_bridge_reduction`,
`test_sec_cancel_awaits_worker_and_prevents_later_dispatch`,
`test_non_sec_optional_omission_keeps_existing_semantics`,
`test_required_sec_omission_is_explicit`,
`test_old_catalog_tool_absent_from_all_current_skills`.
- [x] Run RED before replacement; expected missing-new-name assertion, old name
  present, or JSON boundary corruption. Record exact failing owner.
- [x] Replace all surfaces atomically and implement bounded whole pages and SEC
  cancellation. Preserve model/auth/effort selection and all other tools.
- [x] Focused GREEN runs new tests, subagent/skill owners, auth bridge owners and
  all eight count files. Inverses: omit each transport's new name; select generic
  truncation; omit worker wait; remove one subagent required tool. Named owners
  must fail for each affected boundary; do not merely assert schema counts.
  Eight process-only modes caught24 expected failures, with25 unchanged controls
  passing. Fresh union GREEN30P; no product/test bytes changed by mutations.
  Full-suite count collateral above still needs its final re-verification.
- [x] Commit the complete replacement; record changed/removed tests and exact
  route-count collateral. Do not leave an alias for the old model-facing tool.

### Task 3: Durable Research Citation References

Completed through `5235705c` under the focused
`2026-09-13-sec-research-citations.md` plan. Full backend10583P/12 unchanged S,
frontend1824P and four real-service/store browser workflows pass. Final review
found and closed cancellation between hook publication and queue consumption;
both deterministic cases now preserve durable ends, messages and closure roots.
Evidence: `../evidence/2026-09-13-sec-research-citations/README.md`.
This closes the citation prerequisite, not Tasks5/6 maintenance authorization.

**Files:** Create `src/sec_research/citations.py`, `references.py`; modify API and
OAuth event producers in `src/agents/openai_agent/agent.py`,
`src/agents/anthropic_agent/agent.py`, both OAuth drivers, query accumulation in
`src/api/routes/query.py`, recovery in `src/research_runs.py`,
`src/api/routes/research.py` and `src/research_run_manager.py` as required;
`src/api/routes/sec_research.py`; frontend `api.ts`, `researchReducer.ts`,
`ResearchEvidenceDrawer.tsx`, a focused `SecCitationView.tsx`, relevant en/zh-Hant
resources and styles. No new Research message schema solely for a JSON field.
Tests: `tests/test_sec_research_citations.py`, `test_sec_research_trace.py`,
`test_research_routes.py`, `test_research_runs.py`, `test_research_threads.py`,
adapter owners, frontend reducer/drawer and new citation-view tests.

**Interfaces:** `sec_citations_from_envelope(tool_name, envelope) -> list[dict]`
derives references from admitted whole result rows/passages without adding a
seventh top-level field to the closed model envelope. Pure
`sec_citations_from_result(tool_name, result) -> list[dict]` accepts only owned
SEC tool results, a known wrapper, plain JSON or MCP text blocks; never searches
assistant prose or a preview for citation-like text. `validate_citation(ref)`
rejects extra/malformed fields. Return/record a typed citation gap for malformed
SEC evidence, without breaking old non-SEC trace rows.

Closed union:
- document: `kind="document"` plus every existing `SecDocumentCitation` field
  (filing_id, document_id, capture_id, accession, source_url, original_sha256,
  text_sha256, extraction_version, start_byte, end_byte, nullable match_start_byte
  and match_end_byte). Validate exact half-open UTF-8 ranges and bound source.
- fact: kind, cik, fact_id, snapshot_id, source_sha256, source_pointer, source_url,
  observed_at. Exact observation, not latest-per-period selection.
- filing: kind, filing_id, snapshot_id, source_sha256, source_pointer, source_url,
  observed_at. Retain separate provenance for conflicting catalog variants.

`read_sec_citation(store, captures, *, citation) -> dict` reopens the exact saved
observation/passage under the standard six-field envelope, with zero acquisition.
It verifies captured files, IDs, snapshot/source JSON pointer and metadata rather
than trusting a supplied URL. Add read-only GET `/sec-research/citation` with a
bounded canonical encoded reference argument; register it before dynamic CIK
routes. Frontend `getSecResearchCitation(ref)` uses that route. No arbitrary
local path, fetch URL, model-visible mutation or automatic latest substitution.

Each tool_end event carries optional `call_id` and `sec_citations`, derived from
the complete post-security output before preview slicing. Start carries the same
call ID. Match IDs exactly in Python/TS accumulation, retaining end-only input;
only genuinely ID-less legacy events use old compatible pairing. Duplicate
names/out-of-order completions may not exchange references. Strip only known
wrapper `tool_` or owned `mcp__ark__` prefixes, not arbitrary provider-tool names.

OpenAI presently emits after Runner.run completes: inspect the installed local
SDK hook contract and use its actual tool-completion hook/queue so completed SEC
tools survive a later failure/cancel. Do not invent SDK APIs. Anthropic captures
before Layer0; ChatGPT takes the complete reduced output; Claude parses actual
MCP text blocks. Suppress late abandoned-worker events by run/call identity.

Persist optional fields in existing `research_run_events.data_json` and
`research_messages.tool_calls_json`. Reconstruct all durable calls, not only the
first 500 events, in restart reconciliation and no-task cancellation. Successful,
error, cancelled, interrupted and archived traces all retain refs. Old messages
without refs still load; prompt history stays role/content-only. No module-global
mutable citation collector or shared DAL state. Parent execution owns events.

`iter_research_sec_citations(profile_connection) -> Iterator[dict]` reads all
retained message AND event roots using an explicitly supplied query-only
connection. Invalid present refs fail maintenance closed, absent optional fields
are valid. `sec_reference_closure(store, *, citations) -> dict` returns sorted
IDs/keys for captures, directories, snapshots, receipts, fact/filing observations
and object hashes. Include receipt source_snapshots and all document catalog
sources, not only original/text hashes. This interface is consumed by Tasks5/6.
It does not delete anything or drop unreferenced retained history.

- [x] Write named RED owners using actual durable generated source fixtures:
  `test_sec_citations_roundtrip_event_message_and_legacy_rows`,
  `test_restart_and_no_task_cancel_rebuild_all_sec_tool_calls`,
  `test_sec_tool_end_preserves_whole_citations_by_call_id`,
  `test_completed_openai_sec_tool_survives_later_cancel`,
  `test_four_channels_keep_whole_refs_and_call_inputs` (Claude MCP text blocks),
  `test_queued_openai_completions_survive_executor_cancellation`,
  `test_research_citation_reopens_exact_bytes_after_refresh_and_relocation`,
  `test_reference_closure_retains_directory_catalog_and_fact_objects`.

```python
def test_duplicate_tool_names_do_not_exchange_citations(events):
    calls = accumulate_tool_calls(events.reversed_completions())
    assert calls[0]["call_id"] == "first"
    assert calls[0]["sec_citations"] == events.first_refs
    assert calls[1]["sec_citations"] == events.second_refs
```

- [x] Record RED for lost refs/wrong ID matching/restart truncation, not mocked
  store assertions. Run real per-channel event flows with fake provider messages.
- [x] Implement refs, exact read, persistence/recovery and a concise drawer
  citation control. Stored passage text rendered as text, no remote HTML. Display
  source/form/period concisely; keyboard focus/close restore, stale response and
  selected-message guards. Missing evidence gets an actionable typed state.
- [x] GREEN relevant backend and frontend owners. Inverses remove the optional
  field projection, match wrong call ID, drop event-only roots, ignore a bound
  hash, slice 500 recovery events. Each must kill its named owner. Browser real
  API/store read demonstrates reopened UTF-8 bytes, not fixture invented hashes.
- [x] Commit, report API count collateral and reference-closure contract to
  downstream operations. Citation persistence is now the maintenance milestone;
  no further waiting on an undefined future citation system.

### Task 4: Structural TOC Recognition

**Files:** `src/sec_research/document_text.py`, `document_service.py`,
`document_store.py` only if its metadata validator needs new extraction metadata;
create `tests/test_sec_research_document_toc.py`; extend existing text/service/query
owners. Do not add another HTML parser dependency.

**Interfaces:** Preserve `extract_document_text(body, content_type, *, check)`
return shape `(text,mime)`, adding an optional `structure_observer` callback for
the document-service caller. It receives closed `toc_ranges` (half-open UTF-8
byte ranges) and typed structural gaps after successful complete extraction.
`index_sections(text, form, *, check, toc_ranges=None)` excludes only verified
TOC-region heading candidates; None retains conservative text-only handling.
Persist extraction version `sec-document-text-v4` and the ranges used for the
new capture. Never re-extract or rewrite a retained v3 capture to use new indexes.
Canonical full text still contains TOC text, with exactly matching byte hashes.

Recognize bounded semantic TOC containers (`role="doc-toc"`, a nav with explicit
Table of Contents label) and tabular local-anchor TOCs with an explicit heading
and multiple item links. A whole document/body container is not an admissible TOC.
The parser must establish the container's end structurally; a text heading alone,
duplicate headings, page position or dotted leaders do not identify that end.
Malformed/overbroad/ambiguous markup retains an honest gap. Do not choose the last
duplicate as body. Use the existing tolerant HTML and namespace-aware XHTML
parsers and their bounds/cancellation, not regular expressions over raw markup.

- [ ] Write real extraction->index->capture->query owners, including
  `test_semantic_toc_does_not_hide_real_10k_sections`,
  `test_linked_table_toc_has_structural_end`,
  `test_unbounded_text_toc_remains_ambiguous`,
  `test_body_duplicate_is_still_ambiguous`,
  `test_toc_keeps_full_text_and_exact_utf8_ranges`,
  `test_old_capture_unchanged_after_toc_refresh`.

```python
def test_semantic_toc_does_not_hide_real_10k_sections(document_fixture):
    body = (b'<nav role="doc-toc"><h2>Table of Contents</h2>'
            b'<a href="#one">Item 1. Business</a></nav>'
            b'<h2 id="one">Item 1. Business</h2><p>Actual operations.</p>')
    result = document_fixture.capture_and_read(body, section_id="item_1")
    assert "Actual operations." in result["data"]["passages"][0]["text"]
    assert "Table of Contents" not in result["data"]["passages"][0]["text"]
```

- [ ] RED must demonstrate current section unavailable/ambiguous for structural
  TOC fixtures; no assertion about unmeasured prevalence of real filings.
- [ ] Implement bounded structural range observation and section exclusion;
  include multilingual text, XHTML namespace/case and nested container controls.
- [ ] GREEN existing text/documents/service/queries plus new TOC tests. Inverses:
  ignore ranges (real section fails), exclude entire body (full text/negative
  control fails), pick last duplicate (ambiguity owner fails). Restore bytes.
- [ ] Commit with exact before/after canonical text and citation checks, not only
  a section-count assertion.

### Task 5: Operation Leases And Portable Export

**Files:** extend `src/sec_research/capture_lock.py`, Store/CaptureStore,
ResearchService/DocumentService, issuer/tool/query/citation entrypoints;
create `src/sec_research/operations.py`, `__main__.py`; tests
`tests/test_sec_research_operations.py`, existing capture-lock/service/query tests.
Research execution/persistence owners participate in the operation lease where
they can publish SEC refs. No unrelated resource-root or lock redesign.

**Interfaces:** `research_operation(root, *, exclusive=False, create=False)` is
a reentrant owner-scoped shared/exclusive context manager in the existing trusted
root-hashed lock namespace. No missing capture-root creation on stored read or
preview. POSIX no-follow/fd checks remain; unsupported platforms fail explicitly,
not unlocked. Lock order: operation -> issuer/document -> capture writer ->
market write -> SQLite. Exclusive acquisition is bounded/nonblocking with typed
`sec_research_operation_busy`. Complete put->reference publication, multi-read
queries, exports and Research ref publication hold shared protection. A run that
has produced SEC results retains protection through durable event/message commit;
do not rely on an unprotected gap between tool return and reference publication.
Avoid transferring/reusing mutable Context objects across concurrent workers.

`export_bundle(paths, destination: Path, *, free_bytes=None) -> dict` creates an
explicit new bundle. Reuse `backup_market_db(str(source), str(staged_db),
overwrite=False)`. Derive all registered object requirements from that backup,
not the changing live DB. Include all registered historical objects, full
FK/JSON/citation reference closure; exclude unregistered staging/orphan files.
Only in the private backup, clear transient reservations/orphan accounting and
record that normalization. Never claim that normalized DB bytes equal source.
Source is unmodified, no network/config access.

`restore_bundle(bundle: Path, destination: Path, *, database_name="market_data.db",
free_bytes=None) -> dict` requires a new enclosing destination directory and a
safe basename. It restores the DB and `SecResearchPaths.from_market_db` capture
directory as one published bundle, then verifies actual readers. No existing
destination DB/capture/WAL/SHM can be overwritten; no SQL import or archive extract.
Whole market DB rows are included by SQLite backup, but the bundle packages only
SEC capture objects, not independent SA/profile credentials or other capture
roots. Manifest and CLI must state this scope accurately.

Closed version-1 manifest: format/version, DB relative name/hash/size, current
SEC schema fingerprint, exact object-key/hash/size inventory, transient
normalization policy and verified reference counts. Reject unknown versions,
duplicate or undeclared members, symlinks, special files, unsafe paths, missing
objects and invalid hashes/closure. Copies/hashes stream in bounded chunks.
Preflight full DB + object + staging needs independently of the100GiB quota;
handle ENOSPC/fsync failure after admission. Use create-only destination ownership
and atomic final verified manifest publication; no directory is a successful
bundle before that marker exists. On interruption retain a clearly incomplete
owned operation, never a success marker or overwritten user directory.

Expose `python -m src.sec_research export --destination ...` and
`restore --bundle ... --destination ... --database-name ...` through one thin CLI.
No model-facing filesystem operation. Explicit path/operation validation happens
before opening a DB; reports contain counts/digests, not source contents/secrets.

- [x] RED owners: `test_export_uses_backup_inventory_during_concurrent_publish`,
  `test_export_restore_preserves_wal_and_historical_citations`,
  `test_maintenance_cannot_enter_put_to_publish_gap`,
  `test_stored_reader_lease_does_not_create_capture_root`,
  `test_bundle_rejects_missing_corrupt_and_unsafe_members`,
  `test_create_only_publication_never_overwrites_competing_destination`,
  `test_incomplete_bundle_has_no_success_marker`,
  `test_restore_renamed_database_reopens_same_capture`.

```python
def test_export_restore_preserves_wal_and_historical_citations(bundle_fixture):
    result = bundle_fixture.export_and_restore_with_uncheckpointed_wal()
    assert result["restored_fact"] == result["original_fact"]
    assert result["restored_passage"] == result["original_passage"]
    assert result["source_digest_before"] == result["source_digest_after"]
```

- [x] Run RED: absent command/lease or admitted exclusive operation inside a
  protected publication gap. Use deterministic barriers, no provider processes.
- [x] Implement the lease at all actual current entrypoints, then export/restore
  over verified backup. Protect no-path-create behavior. Include schema/receipt
  JSON closure, not only SQL FK_check. No third generic SQLite backup primitive.
- [x] GREEN new operation tests, capture/store/service/document/citation owners,
  backup tests. Inverses: skip outer lease; enumerate live DB; omit catalog source;
  bypass hash; accept existing destination. Each kills named owner without errors.
- [x] Commit; report acquired lock order and phase failure semantics. No real
  operator export/restore occurs in this task.

### Task 6: Explicit Cleanup And Schema Recovery

**Files:** create `src/sec_research/maintenance.py`, `schema_admin.py`; extend
`__main__.py`, `operations.py` and capture/store helpers only for audited admin
transactions. Tests `tests/test_sec_research_maintenance.py`,
`test_sec_research_schema_admin.py`, `test_sec_research_cli.py`.

**Interfaces:**

```python
def preview_cleanup(paths, *, profile_connection) -> dict: ...
def apply_cleanup(paths, preview, *, approval_sha256, receipt_path,
                  profile_connection) -> dict: ...
def preview_schema_reset(paths, *, mode, profile_connection) -> dict: ...
def apply_schema_reset(paths, preview, *, approval_sha256, backup_path,
                       receipt_path, profile_connection) -> dict: ...
```

These are new synchronous operator commands, not startup behavior. CLI explicitly
opens the configured profile query-only and reads only Research citation roots;
do not use a constructor that initializes/migrates profile data. Preview does not
call recover, create roots, change accounting or write a receipt. Apply requires
an exact preview digest, new receipt path and fresh exclusive operation lease,
then rechecks root/schema/candidates/complete Task3 reference closure. Unknown or
corrupt references block, never become an empty set. File keys are descriptor-
bound owned relative keys; no generic recursive deletion command.

Cleanup distinguishes unregistered owned objects/staging from registered but
unreferenced objects. Retain every snapshot, receipt, filing/fact observation,
document/directory/attempt, issuer-map observation and Research ref, regardless
of age/current pin. Only unreferenced object registry rows are candidates. A
reviewed admin transaction can suspend the exact object DELETE guard, delete
only digest-approved rows, restore the guard and verify schema/FKs before commit.
Charge still-present files as orphans before unlink; interrupted unlink stays
charged and resumable. Shared leases protect active exports/readers/producers.
Unknown entries/symlinks/inode ambiguity block rather than being swept away.
Receipts distinguish selected, removed, remaining, blocked and measured freed
bytes. Never report reclaimed bytes before verified durable deletion.

Schema `mode` is reset/uninstall. Inventory exact known owned tables/indexes/
triggers even if their definitions mismatch; unknown owned objects or external
dependencies block pending inspection. Never DROP by a prefix alone. Verify no
retained Research/pin reference would be broken; if present, return
`sec_research_reset_references_present` with counts and leave state untouched.
Back up DB AND captures before any admitted reset. A mismatched schema's safety
backup must be labeled raw, not advertised as a canonical portable export.
Reset requires a new digest-bound observed state after backup and exclusive
operation protection. Drop/recreate only approved owned objects in a transaction;
uninstall leaves them absent. Leave SQLite shared objects and all unrelated rows,
settings, credentials and capture files untouched. Archive/audit lives outside
the removed schema and survives interruption. No live-user assertion flag is
accepted as a substitute for actual lock exclusion.

CLI subcommands `cleanup-preview`, `cleanup-apply`, `schema-preview`,
`schema-apply` read/write explicit versioned preview/receipt JSON. Approval applies
only to that preview, no automatic confirm. Actual production execution is NOT
authorized by this plan. This completes SEC-RECOVERY-001/002 implementation by
this task, before scheduling/final release verification.

- [x] RED owners: `test_cleanup_preserves_every_retained_reference_class`,
  `test_new_reference_invalidates_cleanup_preview`,
  `test_registered_orphan_unlink_failure_remains_charged`,
  `test_cleanup_restores_immutability_after_rollback`,
  `test_schema_reset_requires_backup_and_exclusive_lease`,
  `test_schema_reset_refuses_research_references`,
  `test_schema_reset_preserves_unrelated_rows_and_sqlite_sequence`,
  `test_unknown_owned_objects_are_not_prefix_drop_targets`,
  `test_maintenance_preview_is_observational`.

```python
def test_new_reference_invalidates_cleanup_preview(maintenance_fixture):
    preview = maintenance_fixture.preview()
    maintenance_fixture.publish_reference()
    result = maintenance_fixture.apply(preview)
    assert result["status"] == "blocked"
    assert maintenance_fixture.original_object_still_exists()
```

- [x] Record concrete RED before implementing operations. Small fixture stores
  only; inject failure between DB/file/receipt stages and retry explicitly.
- [x] Implement inspect/approval/recheck/backup/phase receipts, not a permanent
  old-schema execution branch. Cancellation never silently abandons a destructive
  stage; report its last durable phase accurately.
- [x] GREEN all maintenance/admin/CLI/capture/citation controls. Inverses skip
  recheck, ignore event-only citations, clear charge before unlink, omit backup,
  drop unknown prefix, ignore active lease. Named behavioral failures required.
- [x] Commit and mark the two operational owners implemented, separately from
  their unperformed actual-store rollout. Unrecoverable unknown schema retains an
  explicit blocked diagnostic plus safety-backup path, not raw SQL instructions.

### Task 7: Disabled Daily Schedule And Settings

**Files:** create `src/sec_research/scheduled.py`, `schedule_store.py`; modify
schema/service receipt scope, `src/service/data_scheduler.py`, schedule/SEC API
adapters, `apps/arkscope-web/src/api.ts`, Settings SecResearchPanel,
dataScheduleControls/settingsBackendCopy, en/zh-Hant resources. Tests
`tests/test_sec_research_schedule.py`, `test_data_scheduler.py`,
`test_scheduler_state.py`, new API/Settings owners and existing macro controls.

**Interfaces:** `run_current_universe(*, universe_reader, issuer_resolver,
service, limits, clock, progress_cb=None, check=None) -> dict` is the synchronous
core; `run_incremental(*, progress_cb=None) -> dict` composes runtime dependencies.
Register source `sec_research_filings`, default disabled, interval1440min,
`writes_market_db=True`, `universe_tickers=False`, adapter to run_incremental.
Core reads the active-universe owner each run, distinguishing valid empty from
unavailable. No fixed tickers, YAML fallbacks, profile identity changes or LLM.
Deduplicate resolved issuers by canonical CIK; retain missing/ambiguous outcomes.

Add explicit `scope="recent"` structured acquisition for scheduled work, with
separate receipt/continuation ownership from on-demand full history. It requests
only current submissions and Company Facts, never historical/documents. Preserve
historical-not-requested coverage and previous historical continuation; do not
pretend max_sources=2 alone gives a complete-history result. Normalized schedule
counts apply forms10-K/10-Q/20-F/40-F and amendments; raw source bytes unchanged.

Per run bounds: at most500 distinct issuer dispatches,1001 provider requests (one
optional map+two per issuer),15min wall budget. Check before each source. Persist
remaining CIK/ticker scope; each continuation intersects fresh active membership
and rotates deferred/new issuers so no current member starves. Request bound is
derived from this shape; no retries. Partial receipts never imply missing issuers
are empty. No automatic paid-provider fallback or full-document prefetch.
This raises the draft plan's50-issuer limit: a daily source should not split the
previously reported roughly187-member universe across four days solely because
of that arbitrary limit. The500-issuer ceiling is an application safety bound,
not a measured current universe count or a guarantee that every provider request
finishes within15min. Limits remain injectable for small deterministic fixtures.
The provider governor remains authoritative for pacing; no live run is authorized.

SEC-owned durable batch receipt records attempted/confirmed/failed/deferred CIKs,
request counts, scoped filing/fact counts and gaps; expose last attempt separately
from last successful actual acquisition. A valid empty-universe run can succeed
without claiming an acquisition timestamp. Failed work leaves earlier committed
issuer data and previous success intact. SEC-only scheduler mapping returns
succeeded/partial/failed truthfully, never generic success for unavailable/error.
Keep existing news/macro status contracts unchanged. Next run is next eligible
time, not a guaranteed provider dispatch time.

Add stored-only GET `/sec-research/schedule-status` before dynamic CIK routes;
reuse existing schedule enable/interval/Run Now controls, no second enable key.
SecResearchPanel shows last acquisition/attempt, issuer coverage, counts/gaps and
capacity separately. Terminal schedule changes refresh local status/capacity,
not pinned captures, cursor snapshots or dirty budget drafts. Old SEC enabled
keys are never inherited. Budget PUT cannot enable or dispatch.

- [x] RED owners `test_sec_schedule_disabled_even_with_old_enabled_key`,
  `test_empty_universe_success_is_not_acquisition`,
  `test_unavailable_universe_never_dispatches`,
  `test_schedule_deduplicates_cik_and_exposes_unresolved_symbols`,
  `test_recent_schedule_preserves_explicit_history_continuation`,
  `test_batch_bounds_defer_without_starving_current_members`,
  `test_sec_partial_failure_retains_previous_success`,
  `test_budget_edit_never_enables_schedule`.

```python
def test_sec_schedule_disabled_even_with_old_enabled_key(schedule_fixture):
    schedule_fixture.set_old_sec_enabled()
    state = schedule_fixture.read_current_source()
    assert state["enabled"] is False
    assert state["interval_min"] == 1440
    assert schedule_fixture.tick_dispatches() == []
```

- [x] RED with real disposable scheduler/profile/market stores; provider transport
  only fake. Use deterministic time/dispatch recorders, no supervisor launch.
- [x] Implement scoped receipts, bounded scheduler outcome mapping and real
  Settings consumer. Preserve current route/write permission controls and
  accurate current-tool/category counts if schema tests move.
- [x] GREEN schedule/API/frontend controls, macro/news unchanged controls and
  desktop/mobile screenshots. Inverses enable by default, traverse a historical
  pointer, drop partial status, erase last success, reuse removed membership.
- [x] Commit with source/body request inventory and scope definitions, leaving the
  actual user's schedule disabled and production configuration untouched.

### Task 8: Release Verification And Current-Surface Cleanup

**Files:** focused remaining SEC aliases/current descriptions discovered by
Task 2's exact reference scan; `docs/design/PROJECT_PRIORITY_MAP.md`, current SEC
spec status and new tracked evidence. Tests use actual existing owners plus
`tests/test_sec_research_release_workflow.py` and frontend integration fixtures.
No unrelated news-provider/collector rewrite is bundled into a SEC verification
fix. C09/C11/C12 and CSS/I18n-wide cleanup keep their independent recorded owners;
this gate must state their status, not claim the whole repository is clean.

**Interfaces:** End-to-end fixtures use the actual ToolService, Store,
CaptureStore, Research trace/persistence, export/restore and maintenance commands.
Only remote response bytes/time/filesystem failures and model transport messages
are injected. This is offline workflow validation, not live provider/model proof.

- [x] Write `test_research_catalog_fact_document_reload_export_restore` with a
  generated mapping, submissions, Company Facts, directory and HTML filing.
  Execute all three tools through a real adapter, persist the trace, reopen exact
  fact/passage references, export, restore to a new root and reopen again.

```python
def test_research_catalog_fact_document_reload_export_restore(release_fixture):
    before, after = release_fixture.round_trip()
    assert after["value"] == before["value"]
    assert after["text"] == before["text"]
    assert after["text_sha256"] == before["text_sha256"]
    assert after["capture_id"] == before["capture_id"]
```

Add explicit interrupted-refresh->stored-reference-read->cleanup-negative
workflow and default-disabled schedule controls. First run records the missing
workflow's concrete RED, if any; do not manufacture a regression when already
implemented behavior passes, instead label that as a positive integration check.

Workflow source `a77a7c2e` has two new integration owners and nine focused passes
including seven existing controls. Both workflows passed as positive integration
checks; two retained fixture setup failures are not product RED. Whole-change
review then found an async delegated SEC invocation defect. The final fix wave
also owns the confirmed absence of delegated citation forwarding: preserve
actual admitted SEC completions through existing parent events, not arbitrary
delegate-result metadata. Complete source acceptance waits on that repair,
scoped re-review and the frozen complete backend gate.

Final fix `911d69a2` records1349 covering passes,194 restored focused passes and
three current-source killed inverses. The single scoped re-review accepts I1,
M1 and delegated citation forwarding, but identifies ImportantN1: changing the
OpenAI delegate from sync to async moves the unchanged blocking Anthropic SDK
stream onto the parent's event loop. This is confirmed static source evidence;
a held-stream heartbeat regression has not yet been executed. The proposed next
scope is an awaitable Anthropic child client preserving captured auth/effort and
owned cancellation. It was put to the user; it is not implemented by this plan's
final fix wave. Full release acceptance and merge remain blocked. The fresh
frontend1833P/typecheck/build/literal checks and11023-node collection do not
replace the deliberately unrun final complete backend gate.

**September 14 follow-up:** The user approved the awaitable child scope.
`e447d394` and `24c10280` repair N1 and the independently discovered pre-stream
error cleanup P2. Scoped re-review accepts P2. The first full run found one
missed async SDK fixture entry, reproduced in isolation and repaired without
weakening its existing output-guard assertions in `39b6587f`. The second single
complete run passes11050/12unchanged skips with exact11062-node reconciliation,
unchanged1160 source paths/runtime/runners, and no duplicate or missing nodes.
Fresh frontend1833P/typecheck/build/i18n checks have unchanged UI source through
the final anchor. The current census has no new delta versus the integration
checkpoint, not zero repository-wide cleanup debt. See the separately sealed
`docs/superpowers/evidence/2026-09-14-anthropic-child-async/README.md` for all26
finished receipts, including8 classified nonzero attempts. This closes N1/P2
and supplies the missing complete Linux gate; the other checklist items below
retain their historical proof anchors and are not silently waived. No merge,
restart, actual-store action, SQLite activation or cross-platform proof occurred.

- [ ] Re-run mechanical repository census against the sealed document baseline;
  classify every new candidate, dependency change and coverage reduction with a
  current owner. Remove only confirmed abandoned SEC aliases/entrypoints and
  move their useful tests to the real workflow. No deletion based solely on a
  candidate ID, locale string or SQL scanner false positive.
- [ ] Run all frontend tests, typecheck, i18n checks and Playwright at desktop
  1280x960/mobile390x844 in en/zh-Hant. Real HTTP/service/store fixture, screenshots,
  no horizontal overflow or overlapping controls. Exercise stored reads,
  citations, background completion, config, schedule and operator previews;
  destructive confirmations operate only on generated stores.
- [ ] Freeze all product/test/resource/dependency paths, collect exact backend
  nodes with explicit `tests`, run one full backend suite, and reconcile every
  executed node plus the unchanged skip identities. Run inverse scripts against
  the final source; any changed boundary since its task gets fresh inverse proof.
  A fixture runner failure is recorded separately, never fixed by weakening
  product contracts or quietly skipping a test.
- [ ] Independent whole-change review over `c997a6c9..HEAD`; task reviews are not
  a substitute. Route findings through the original implementer/final-fix worker
  with focused RED/GREEN and scoped re-review. No controller product fixes.
- [ ] Seal reports, commands, logs, source identities, node reconciliation,
  inverse results, screenshots and census into
  `docs/superpowers/evidence/2026-09-12-sec-research-release-integration/`.
  Hash original and archive bytes, verify Git index bytes, exclude disposable
  DBs/tokens/user config. Publish evidence before removing this plan's scratch.
  Record every `Ruling:` in the final report with its tradeoff.
- [ ] State exactly which workflows are verified offline, which live canary is
  still unauthorized, and which actual-store rollout/old-schema disposition and
  separate wider cleanup remain. Do not merge/push/restart. Existing worktree is
  retained for explicit user review and later merge authorization.

## Evidence Format

Each implementer writes `task-N-report.md` next to its brief, with exact changed
files, RED/GREEN command paths/results and self-review. Each named inverse has
one entry in `task-N-inverses.json`:

```json
{"run":"taskN-inverse-name","restored":{"src/path.py":"sha256"},
 "mutated":{"src/path.py":"different-sha256"},
 "failed_testcases":["tests.test_module::test_named_owner"],
 "mutation_script":"task-N/inverse.py"}
```

Hashes in actual evidence are computed, not these illustrative labels. Store
re-runnable inverse scripts under this plan's scratch, not product test APIs.
No syntax/import/collection error counts as a killed behavioral owner. The final
source and named tests must match recorded restored hashes. Full-suite execution
belongs to the final gate; focused task regression suites avoid repeating the
entire backend for each implementation or review.

## Preflight Review

Spec coverage: issuer/freshness Task1; three contracts/four transports/skills and
whole pages Task2; persistent refs/reopening Task3; section quality Task4;
coordination/export Task5; both recovery owners Task6; schedule/Settings Task7;
integration/collateral/census Task8. Existing exact parsers/captures remain the
foundation. Actual-store cleanup/activation and separate news/collector cleanup
are not represented as completed by these offline steps.

The concrete interfaces above were checked against the current stores/queries,
both bridge caps and Layer0's smaller default, transport retry behavior and two
read-only preflight reports. No product files changed during preflight. The
collected baseline is exactly9180 nodes. No guessed pass totals are used for new
work. The initially missing schema-test filename is retained as a runner mistake.
