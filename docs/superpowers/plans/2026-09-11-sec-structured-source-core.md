# SEC Structured Source Core And Cleanup Follow-Up

> **For agentic workers:** Use superpowers:subagent-driven-development or
> superpowers:executing-plans. Complete each RED-first task and its review.

**Goal:** Finish the three review follow-ups, remove the unused OpenAI sync
entrypoint, and implement exact, provenance-bearing SEC structured-source parsing.

**Architecture:** Pure SEC parsers consume original JSON bytes, never an already
float-decoded provider dictionary. They produce immutable source-bound catalog
and fact observations. The existing live SEC tool remains until all three new
tools can replace it atomically. No incomplete tool is registered.

**Tech Stack:** Python standard library, dataclasses, Decimal, pytest; existing
OpenAI agent runtime and offline test harness.

**Spec:** `docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md`,
sections 3, 5, 6, 8 and 11. Cleanup C08 is owned by the September 10 audit.
Base: `95ad149ea4bda2569030f1dfc95f93bf3c279738`.

## Global Constraints

- Existing isolated worktree only. No production store/config/token reads,
  provider calls, runtime installation, App restart, merge or push.
- Preserve current async/streaming Research, Anthropic synchronous Research,
  authorization capture, redaction and current retry contracts.
- Do not delete master-tracked `src/audit/`: main has not merged the cleanup.
  The implementation worktree has no such directory or remaining cache.
- Preserve current approved unknown-event-date plus explicit attended execution
  date policy. Do not change lifecycle code in this batch.
- New SEC parsing has no I/O, schedule, DB activation, import-time config read
  or live model-facing registration. Persistence, capacity reservations,
  acquisition, whole-source coverage and public pagination remain distinct work.
- No implicit truncation, binary-float round trip, guessed report date,
  guessed document XML suffix, amendment overwrite or ticker-to-CIK alias claim.
- New raw parser failures have a closed code and JSON pointer, not raw source
  contents in the exception. Complete raw snapshots are all-or-nothing: malformed
  rows cannot silently become a successful smaller result.
- The approved 100 GiB adjustable budget and 32/128 MiB document transfer policy
  are unchanged; pure parsers neither allocate capacity nor bypass that policy.

## Scope And Completion Boundary

This is a testable pure-source core, not the complete SEC service. It intentionally
does not install a partial schema, fetch documents or register a subset of the
three tools. The existing tool/skills/four transports continue to work unchanged.
Canonical storage/quota, refresh traversal, query selection and durable citations,
three-tool replacement, export and Settings are subsequent implementation work.
Whole audit cleanup and actual-store disposition also remain open.

### Task 1: Reproducible SQLite Evidence And Review Closure

**Files:** New `docs/superpowers/evidence/2026-09-11-sec-structured-source-core/`
with `sqlite_upsert_repro.py`, `sqlite-upsert-result.json` and `review-followups.md`.
Existing sealed evidence is not rewritten.

**Interfaces:** Standalone standard-library diagnostic; its only SQLite target is
`:memory:`. stdout is a structured report. Exit 0 means all integrity controls
passed, 1 means the exact defect reproduced, 2 means inconclusive/probe failure.
There is no database-path argument, repair, application import or installation.

- [ ] Build the executable form of the exact SQL already archived in
  `current-journal-cleanup/sqlite-research.md`, not a newly guessed UPSERT shape.
  Keep upstream REPLACE + duplicated ON CONFLICT, the two replacement spelling
  variants, and the two single-clause controls in separate in-memory databases.

```sql
CREATE TABLE v0(c1 INTEGER PRIMARY KEY ON CONFLICT REPLACE,c2 UNIQUE);
INSERT INTO v0 VALUES(0,33),(11,22);
REPLACE INTO v0 VALUES(0,11)
 ON CONFLICT(c2) DO UPDATE SET c1=c2,c2=c2
 ON CONFLICT(c2) DO UPDATE SET c1=c1,c2=c1;
```

- [ ] Record engine version/source ID, journal mode, table/index counts, full
  integrity_check, quick_check and classified result. Expected on the previously
  inspected binary: duplicate-clause index count 3 vs table count 2; single-clause
  controls 2 vs 2 and integrity ok. Actual output, not version, decides status.
- [ ] Run with explicit interpreter and clean `env -i`, `-I -S -B`; archive
  actual output and command. Do not claim the running App has that interpreter,
  or that a memory probe inspected the user's data. Negative/inconclusive output
  is retained rather than forced into the expected classification.
- [ ] Document the checked main/worktree audit-directory distinction and the
  existing September 8 plan's limitations/execution-date policy. Run current
  execution-date positive/negative owners without changing their expectations.
- [ ] Independent review verifies the SQL, absence of filesystem-backed SQLite,
  classification and reproduction instructions. Parent commits after review.

### Task 2: Remove The Unused OpenAI Sync Entrypoint

**Files:** `src/agents/openai_agent/agent.py`, `__init__.py`,
`tests/test_task_runtime_binding.py`, `tests/test_legacy_agent_surface_retirement.py`,
new `tests/test_openai_sync_surface_cleanup.py`.

**Interfaces:** `run_query` and `run_query_stream` remain unchanged. No
`run_query_sync` export, implementation or compatibility wrapper remains.

- [ ] Add an assertion-based RED owner for absent function/export and present
  async/stream owners. Expected RED: old function/export still exists.

```python
def test_openai_sync_implementation_is_removed():
    tree = ast.parse((ROOT / "src/agents/openai_agent/agent.py").read_text())
    names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "run_query_sync" not in names
    assert {"run_query", "run_query_stream"} <= names
```

- [ ] Run existing binding/error/tracing tests as positive controls before edits.
- [ ] Delete only sync implementation and export; update module description.
  Remove the sync-only parameter cases/branches from three runtime-binding tests.
  Retain exact assertions for live stream/async and Anthropic sync, child and
  cross-provider child. Remove the old signature guard's sync declaration.
- [ ] Verify retained functions by AST comparison against the base. Run all
  binding/legacy/agent/streaming/replay tests; report exact removed/added node IDs.
  A reintroduced export/function must fail the new absence owner.
- [ ] Review and commit; no changes to actual provider transport or API routes.

### Task 3: Exact SEC Source Decoding And Catalog

**Files:** New `src/sec_research/common.py`, `catalog.py`,
`tests/test_sec_research_common.py`, `tests/test_sec_research_catalog.py`.

**Interfaces:** `SourceError(code: str, pointer: str = "")`; frozen
`SourceRef(sha256: str, pointer: str)`; `decode_object(body: bytes) -> dict`;
`normalize_cik(value: str) -> str` returns ten ASCII digits. `source_ref(body,
pointer) -> SourceRef` and `json_pointer(*parts) -> str` provide exact binding.
`parse_submissions(body: bytes, *, cik: str, historical_name: str | None = None)
-> CatalogSnapshot`. The snapshot contains canonical CIK, original-body hash,
tuple of frozen `Filing` records and tuple of `HistoricalFile` pointers.

Filing fields: `filing_id`, `cik`, `accession`, `form`, `filed_date`, optional
`report_date`, optional `accepted_at`, optional `primary_document`, optional
`primary_url`, `source`. HistoricalFile fields: `name`, optional `filing_count`,
optional `filed_from`, optional `filed_to`, `source`. Missing optional metadata
stays None; it is not supplied from another field. There is no complete-history
claim on this snapshot type; its historical pointers are explicit pending work.

- [ ] Assertion-based module RED before implementation. Then named tests:
  `test_decode_preserves_exact_decimal_and_large_integer`,
  `test_duplicate_keys_and_nonfinite_numbers_are_rejected`,
  `test_cik_requires_nonzero_ascii_digits`,
  `test_catalog_preserves_report_filed_accepted_dates_separately`,
  `test_historical_arrays_share_recent_validation`,
  `test_misaligned_arrays_never_yield_a_partial_success`,
  `test_amendments_remain_distinct_accessions`,
  `test_primary_url_uses_actual_document_name`,
  `test_historical_pointer_cannot_leave_submissions_directory`.
- [ ] Decode original UTF-8 bytes with `json.loads(parse_float=Decimal)`;
  reject duplicate object keys, non-finite constants and non-object roots. Do
  not accept str/dict as substitutes for the source bytes. RFC6901 pointer
  escaping is lossless. Bound SHA256 is over original bytes, not reserialization.
- [ ] Normalize explicit `CIK:` (case-insensitive) or numeric CIK input; trim
  outer whitespace, allow 1-10 ASCII digits, reject zero/signs/non-ASCII/overflow.
  Do not read a provider or bundled ticker map to fill missing identity.
- [ ] Parse recent arrays and historical-file root arrays. Validate column
  types/alignment before output. Required row fields are accessionNumber,
  filingDate, form; optional reportDate/acceptanceDateTime/primaryDocument are
  None when absent/empty. All present array columns must share the row count.
  Preserve actual dates; aware accepted timestamps normalize to UTC.
- [ ] Validate accession shape and real document basename (no traversal,
  slash, encoded path tricks, query/fragment, control or unsafe URL component).
  Form actual SEC directory URL only with validated CIK/accession/document.
  No inferred XML URL. Validate historical names against the same CIK and
  `CIK##########-submissions-<digits>.json`; retain declared counts/date bounds.
- [ ] GREEN and inverse mutations: ordinary float JSON decode breaks exact
  decimal owner; filing-date-for-report-date substitution breaks date owner;
  accepting malformed arrays breaks the all-or-nothing owner. Tests also cover
  truthful zero-row source, explicit missing arrays, invalid dates, conflicting
  duplicate accessions and cross-CIK payload rejection.
- [ ] Task review checks spec/quality, then parent commits scoped files.

### Task 4: Immutable Company Facts Observations

**Files:** New `src/sec_research/facts.py`, `tests/test_sec_research_facts.py`.
Consumes Task3 common.py, without changing its interface.

**Interfaces:** `parse_companyfacts(body: bytes, *, cik: str) -> FactsSnapshot`.
Snapshot contains canonical CIK, original-body hash and tuple of frozen
`FactObservation`. Observation fields: `fact_id`, `cik`, `namespace`, `concept`,
`value` (exact decimal text), `unit`, optional `start`, `end`, optional `fiscal_year`,
optional `fiscal_period`, `form`, `accession`, `filed_date`, optional `frame`,
`source`. IDs deterministically bind source hash + JSON pointer, not a mutable
latest-value key. Source reference exposes the exact original JSON location.

- [ ] Add assertion-based module RED, then tests
  `test_fractional_value_never_passes_through_binary_float`,
  `test_large_integer_and_non_usd_units_are_preserved`,
  `test_ytd_and_quarter_observations_keep_distinct_periods`,
  `test_amended_and_original_values_are_both_retained`,
  `test_fact_ids_reopen_the_exact_source_pointer`,
  `test_malformed_observation_is_not_silently_dropped`.
- [ ] Validate body CIK, namespaces/concepts/units and observation types. Accept
  only finite Decimal or int values (not booleans), store decimal text without
  rounding/clamping. Require real end/filed dates, accession and form. Optional
  fiscal labels/frame/start remain explicit; start cannot exceed end. Accept
  arbitrary valid namespace/concept/unit text without inventing currency or
  deriving numeric quarters from fiscal labels.
- [ ] Preserve every reported observation including overlapping periods,
  amendments, duplicate values at different source pointers and contradictory
  observations. Deterministic ordering follows source structure; future query
  selection owns as_of, revisions and conflict resolution, not the parser.
- [ ] GREEN; inverse mutation converting val to float must kill precision owner;
  overwriting observations by concept must kill revisions/period owner.
- [ ] Task review and commit. No scheduled write or incomplete tool registration.

### Task 5: Combined Verification And Handoff

**Files:** new evidence directory above; audit README, priority map and SEC spec
status only. Do not change historical sealed evidence or duplicate the backlog.

- [ ] Verify all task source diffs, reviewer findings and fresh focused tests.
- [ ] Run full backend under the existing offline runner with isolated fixtures,
  production-read/provider guards and reviewed Node PATH. Capture complete
  collection/execution IDs and exact changes vs this plan's base.
- [ ] Re-run mechanical census against the existing baseline, retain review
  required and explain unconnected pure modules; do not call candidates bugs or
  falsely report the full feature complete.
- [ ] Whole-batch independent review; fix findings and rerun affected/full tests
  as required. Archive source hashes, commands, results and owner accounting.
- [ ] Commit locally; report work completed, remaining full SEC/cleanup/SQLite
  installation separately. No merge/push, production-disposal or manual-test claim.
