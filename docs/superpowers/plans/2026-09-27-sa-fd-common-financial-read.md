# SA/FD Common Financial Read Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one source-consistent, local-first SA/FD financial read and coverage contract to tools, the ticker Data tab, Dashboard and Settings, without restoring SEC financial acquisition or treating retention TTL as financial validity.

**Architecture:** Adapt the existing SA observation reader and governed FD client into provider-neutral statements, then select one provider and calculate only supported metrics. A shared read service owns selection, identity and gaps; coverage is a projection of that result, not a second cache inventory masquerading as financial coverage. Existing acquisition owners and the shared FD cache remain intact.

**Tech Stack:** Python dataclasses/Pydantic, SQLite read-only connections, existing FD governance/coalescing, FastAPI, React/TypeScript, pytest, Vitest and fixture-only Playwright. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-27-sa-fd-financial-data-and-sec-retirement-design.md`

## Global Constraints

- **Review gate:** Review this plan and its written spec before implementing the financial contract. No product implementation is claimed by this document. After approval, make independently tested commits at task checkpoints; merge only after the final frozen regression and review.
- Planning baseline: `220fe6d26fb366e421336ecba9e17b47f7d255da`. Health/layout fixes are independently frozen at `985e2e63` in `/tmp/arkscope-sa-body-recovery`. Execute the financial work in a separate branch/worktree based on the accepted health/layout result, not by editing that frozen tree during its tests. Preserve its translation, provider-health and responsive-layout changes.
- Spec: "App opening, coverage, source selection and stored tool reads are local-only." No live providers, paid requests, formal DB access/writes, actual browser captures or real account probes during implementation verification.
- Spec: "An SA loading or coverage gap must not silently authorize spending on FD." Forced acquisition names a provider. Changing a source selector is a read, not acquisition permission.
- Spec: "A missing market DB must not hide SA observations in its independent database." Constructors used on these paths must not install schemas or create missing files.
- Spec: "Historical period values remain readable independently of an acquisition-age window." Last acquisition, read evaluation, age policy and financial period are separate facts. No next reporting date without evidence.
- Spec: "Preserve access to the original captured rows." The 13 mapped fields are the initial common normalization scope, not all data SA offers. No inferred debt/equity/shares/capex/FCF/EBITDA mappings.
- Spec: "SA observations can reopen by retained observation ID." FD is current-retained-version-only; changed identity must reject pagination, not claim historical reopening.
- Cleanup is already complete. Preserve the shared `financial_cache` table and future legitimate FD rows/file-cache reuse. Never rerun the 48-row cleanup, remove SEC identity/autocomplete/lifecycle data, or install/repopulate SEC research storage.
- No article classifier, acquisition redesign, new provider connector, versioned warehouse, extension change, or broad detailed valuation/peer-analysis port. Optional SEC filing/document tools remain separate.
- Spec: "Freeze and run complete regression before any product merge." Keep independent health/layout rollback separate from the financial delivery.

## Review Focus

1. SA exists but market/profile DBs do not: an unset local route reads SA without creating either DB; an explicitly saved FD-only route stays FD-only. Tasks 2, 4 and 5.
2. SA primary is missing/partial/stale while FD is partly cached: no mixed-source statement and no automatic FD purchase to fill SA gaps. Task 4.
3. TTM, duplicate labels, unknown currency, very large rounded values and zero denominators: retain source evidence, expose typed gaps, never invent fiscal days or zeros. Tasks 1-3.
4. A retained version changes between pages or an FD refresh fails: reject changed identity; do not silently present old data as a successful refresh. Tasks 2, 4, 6 and 7.
5. Price/news/health failure or a late response after changing source: available financial data remains visible and cannot be replaced by the wrong request's result. Tasks 5 and 7.

---

## Verified Starting Points

These are existing interfaces, not proposed names. Repository reads, not formal DB queries, established them.

| Existing owner | Verified boundary / required change |
| --- | --- |
| `data_sources/sec_edgar_financials.py:56` | `IncomeStatement`, `BalanceSheet`, `CashFlowStatement` are dataclasses with required ticker/report/fiscal/period/currency fields. FD imports them here. Move ownership, retain import aliases; do not delete SEC implementation. |
| `src/tools/schemas.py:147` | `FinancialStatement.report_period: str` currently demands a day. `FundamentalsResult` carries statement arrays, numeric metrics, `metric_basis`, `metric_gaps`, `source_observations`, `source_routes`, `acquisition_gaps`. Extend, do not manufacture SA dates. |
| `src/sa/company_store.py:76` | `read_capture(ticker, statement, view, currency, *, observation_id=None, db_path=None)` is read-only/no-create; returns content ID, first/last capture times, columns and rows. |
| `src/fundamentals/source_comparison.py` | `METRICS`, `source_value(source, metric, label, kind, month)` and `decimal`/`number` already normalize the 13 exact labels, scale/per-share exceptions and display half-step. |
| `src/tools/financial_comparison_tools.py` | `_read_source(dal, provider, ticker, statement, period, currency)` contains useful record construction, but also routing. `compare_financial_sources(...)` is descriptive comparison, not an analysis result. |
| `data_sources/financial_datasets_client.py:72` | Constructor accepts `api_key=None, cache_days=None, cache_backend=None, request_policy=None, governor=None`. `get_income_statements`/`get_cash_flow_statements(ticker, period="quarterly", limit=4, *, freshness="auto", max_age_seconds=None)`; balance default limit is 1. `observations` records acquisition metadata. |
| `src/tools/analysis_tools.py:138` | `get_fundamentals_analysis(dal, ticker, period="annual", freshness="auto", max_age_seconds=None, source="auto") -> FundamentalsResult`. Current SEC/else-FD and FD/else-SEC branches are unsafe for a third provider. `_fd_financials(..., local_only=False)` has reusable refusal/partial-statement behavior. |
| `src/fundamentals/metric_basis.py` | `derive_metrics(income, balance, cashflow, *, source=None)` has debt-component, currency/date and prior-period guards. Preserve these FD guards; do not pass month-only SA through day-based helpers. |
| `src/data_source_routing.py` | `SourceRoute.candidates`, `load_route(dataset, dal=None)`, `read_setting` and `fd_policy_from_settings` own selection/admission configuration. Code currently defaults to SEC/FD; the completed cutover receipt records the **saved** financial route as `["financial_datasets"]` and detailed route as `[]`. No migration to SA. |
| `src/api/routes/fundamentals.py` | `fundamentals(ticker, stored=False, dal=Depends(get_dal))`; `stored=true` bypasses analysis into the SEC-only TTL projection. |
| `src/tools/data_coverage_tools.py:214` | `get_ticker_data_coverage(ticker, target_date=None)` returns before reading financials when market DB is missing. `src/market_data_admin.py:345` has the same market-only assumption in `local_ticker_coverage(ticker, out_path=None)`. |
| `apps/arkscope-web/src/TickerDetail.tsx:331` | `DataTab` uses `getStoredFundamentals(ticker)` and independent `Promise.allSettled` diagnostics. `App.tsx` hosts this view; financial rendering is not implemented in App itself. |
| `apps/arkscope-web/src/Dashboard.tsx:119` | `StatusTiles` labels `/status.data_sources.fundamentals_tickers` as stored SEC fundamentals. |
| `apps/arkscope-web/src/settings/DataStorageSection.tsx:104` | Financial SEC/TTL diagnostics live here, below price coverage. `Settings.tsx` is composition/navigation; do not redesign its layout. |
| `src/api/routes/seeking_alpha.py:243` | `/sa/acquisition-status` calls `CompanyCollector().public_status()` without spawning a browser/host or installing a DB. `/sa/extension-health` can spawn a native-host ping; do not use it as a financial read dependency. |

## Delivery Contract

### Types And Ownership

Create `data_sources/financial_statements.py` for the three existing dataclasses **unchanged**, and `src/fundamentals/contracts.py` for the new small Pydantic read types below. Keep the public `FinancialStatement`/`FundamentalsResult` in `src/tools/schemas.py` to avoid unnecessary consumer churn. New metadata types have `extra="forbid"`; validate numeric inputs strictly (booleans are not integers).

| Type / field | Decision |
| --- | --- |
| `Provider`, `StatementKind`, `Period`, `Freshness` | Literals: `seeking_alpha`/`financial_datasets`; `income_statement`/`balance_sheet`/`cash_flow_statement`; `annual`/`quarterly`; `stored`/`auto`/`refresh`. |
| `FinancialQuery` | `ticker: str`, `period: Period="annual"`, `source: str="auto"`, `freshness: Freshness="stored"`, `currency: str="USD"`, `statement: StatementKind | None=None`, `end_month: str | None=None`, `observation_id: str | None=None`, `read_id: str | None=None`, `period_offset: int=0`, `period_limit: int=4`, `max_age_seconds: int | None=None`. Limit 1..8, offset >=0; currency `[A-Z]{3}`, real `YYYY-MM`, IDs lowercase 64-hex. |
| `FinancialGap` | `provider: str`, `code: str`, `dataset: str | None=None`, `metric: str | None=None`, `required_inputs: list[str]=[]`. Preserve existing provider refusal codes; use the closed new-code set listed below. No raw exception/credential text. |
| `FinancialValue` | Exact `source_value` evidence: `status`, `raw: str | int | float | None`, `normalized_value: str | None`, `scale: str | None`, `unit`, `currency`, `precision`, `display_half_step`, `label`, `section`; nullable strings except `status`. SA successful precision is `provider_display_rounded`, FD is `provider_numeric_float`. |
| `FinancialObservation` | `provider: Provider`, `dataset: str`, `observation_id: str`, `fetched_at: str`, `evaluated_at: str`, `age_seconds: float`, `max_age_seconds: int | None`, `within_max_age: bool | None`, `freshness_mode: Freshness`, `retrieval: Literal["stored","refreshed","coalesced"]`, `persisted: bool`, `source_url: str | None`, `first_captured_at: str | None`, `report_periods: list[str]`, `history: Literal["retained_observation", "current_retained_version_only", "not_retained"]`. Preserve existing `Observation.describe` meanings; an unsaved response is not reopenable. |
| Extend `FinancialStatement` | `report_period: str | None=None`; add `end_month: str | None=None`, `period_precision: Literal["day","month","unknown"]="unknown"`, `provider: str | None=None`, `observation_id: str | None=None`, `column_index: int | None=None`, `unit_note: str | None=None`, `value_metadata: dict[str, FinancialValue]={}`, `raw_reference: dict | None=None`. Keep fiscal/type/currency/basis fields. `data` becomes `dict[str, float | str | None]`: SA normalized decimal strings, FD finite numeric values. Old day-based payloads remain parseable without asserting new provenance. |
| `ProviderRead` | `provider: Provider`, `statements: dict[StatementKind, list[FinancialStatement]]`, `observations: list[FinancialObservation]`, `gaps: list[FinancialGap]`. Define next to adapters, avoiding a contracts-to-tools schema import cycle. |
| Extend `FundamentalsResult` | Add `status: Literal["ok","partial","unavailable"]="unavailable"`, `read_id: str | None=None`, `period_selection: Literal["latest_stored","explicit_month","retained_observation"]="latest_stored"`, `coverage: FinancialCoverage | None=None`, `read_gaps: list[FinancialGap]=[]`, `update_choices: list[dict]=[]`, `pagination: dict={}`. Keep existing field names and metric floats; `snapshot_date` stays null for SA. Retain legacy `source_observations: list[dict]` for cache compatibility; the common service publishes validated `FinancialObservation.model_dump()` values there. |
| `FinancialCoverage` | `ticker: str`, `status: Literal["ok","partial","unavailable"]`, `selected_source: Provider | None`, `period: Period`, `requested_currency: str`, `currency: str | None`, `read_id: str | None`, `statements: dict[StatementKind, list[dict]]` of period/precision/observation/time descriptors, `missing_statements: list[StatementKind]`, `supported_metrics: list[str]`, `metric_gaps: dict[str,str]`, `gaps: list[FinancialGap]`. Descriptors contain `report_period`, `end_month`, `fiscal_period`, `period_precision`, `precision`, `unit_note`, `observation_id`, `fetched_at`, `age_seconds`, `within_max_age`, `history`. |

Use the three singular statement kinds internally; preserve existing output array names `income_statements`, `balance_sheet`, `cash_flow_statements`. All dates/identities come from evidence. FD's exact day does not imply a valid fiscal-quarter identity: validate each separately. An SA annual page's `trailing` and `latest_report` columns remain reachable through the original table, not annual/quarterly facts.

New query/identity gap codes: `financial_query_invalid`, `financial_read_changed`, `financial_period_missing`, `financial_period_ambiguous`, `financial_observation_missing`, `financial_refresh_source_required`, `financial_historical_requires_stored`, `financial_operation_not_ported`, `financial_retention_failed`, `sa_browser_update_required`, `financial_read_page_too_large`, `financial_read_result_invalid`, `financial_coverage_store_unavailable`. New metric reasons: `mapping_not_reviewed`, `currency_unknown`, `currency_mismatch`, `same_column_required`, `positive_denominator_required`, `exact_period_identity_unavailable`; preserve existing `metric_basis.py` reasons and source-cell statuses. A missing/malformed value stays null with its reason, not zero.

`pagination` is `{period_offset, period_limit, total_periods: {statement_kind: count}, next_period_offset}`; the next offset exists if any statement has more columns. Coverage and metrics describe the unpaginated selected read, not just the visible page. Each update choice is `{provider, action, available, reason_code, capture_urls, status_url, requires_confirmation}`: actions are `capture_company_page_in_sa_extension`, `refresh_financial_datasets`, or `select_source_in_settings`; available means the action can be offered, not that paid admission or browser capture succeeded. A named FD update still checks admission at dispatch.

### Selection, Acquisition And History

- Proposed default **only when the route setting is absent**: `(seeking_alpha, financial_datasets)`. Saved FD-only, ordered lists and disabled `[]` remain authoritative; invalid/retired saved choices fail closed and are repairable through existing explicit Settings save. Do not rewrite settings/YAML or infer enablement from credentials/captures. `sa_company_financials` continues controlling the existing raw-table tool separately; normalized reads use `fundamentals_analysis`.
- `stored` and coverage inspect configured providers in order without age filtering, provider calls, file-cache promotion, locks for acquisition, schedule changes or timestamp writes. Explicit source inspects only that configured provider. A valid partial first source wins; never fill its cells/statements from a second source. Record missing statements and metric/input gaps.
- Latest `auto` first inspects local observations, then evaluates the acquisition-age policy separately. Choose the first provider with eligible retained statements; a partial selected FD may acquire its missing/out-of-window statements **only** if FD is explicit or primary. SA partials are returned with browser-update choices, not FD purchases. If none meet the age window, retained values may still be returned with `within_max_age=false` and the appropriate update/refusal gap.
- Acquisition target is the explicit provider, otherwise the first configured provider. Primary SA missing/stale/failed plus secondary FD missing/partial never authorizes FD acquisition. Already retained FD data may satisfy a later local-source choice. Primary FD `auto` preserves existing governed admission and first-refusal suppression; a local SA result can satisfy the local-first phase before any FD purchase.
- `refresh` with `source="auto"` fails before dispatch. Named FD refresh uses the existing client/governor/coalescing and never falls back to old cache as a successful refresh. UI may retain the preceding read separately while displaying refresh failure. Named SA refresh returns `sa_browser_update_required` with existing `PATHS` capture URL(s) and `/sa/acquisition-status`; it starts no browser work.
- `end_month`, `observation_id` or `read_id` pins a stored read; reject other freshness modes rather than silently acquiring. Ignore acquisition-age thresholds for pin eligibility, but disclose the threshold/age. `observation_id` additionally requires `source="seeking_alpha"` and one `statement`; reopen it via `read_capture`, including old retained observations. Multi-statement SA history is reopened as individually pinned statements, not a fabricated atomic capture bundle.
- `read_id` hashes canonical query identity, selected provider and **full selected statement content/observation identities before pagination**, excluding evaluated time and page offsets. Offset >0 requires `read_id`; reject mismatches before returning values. Include currency, period, statement and `end_month` in identity. SA recapture of identical content may change last-capture time but not content identity. FD hashes typed statement content plus original acquisition metadata, and never promises access after that cache version is overwritten.
- FD acquisition request shape stays annual income/cash-flow limit 2, quarterly limit 4, balance limit 1, matching existing v1 keys. A larger UI page does not expand paid history. Missing older FD periods return a retained-window gap; no pagination-triggered larger request. No same-month exact-day conflict is silently resolved.
- Metrics anchor at the explicit month, otherwise the latest retained eligible column, before pagination. For historical FD growth, retain older rows from that same observation as comparison inputs even when the response displays only the selected month; `previous_period` still decides eligibility. Missing prior history is a gap, never authority to fetch. FD's API has no currency request parameter: retain its declared currency, report requested-vs-declared mismatch, and exclude mismatched inputs from analysis; never relabel/convert them to USD.
- `ok` means all requested statement kinds have usable dated records, `partial` means some do, `unavailable` means none do. Metric/input gaps remain independent: four computable SA ratios do not imply full analysis. Per-statement acquisition times are not flattened into a fictitious simultaneous bundle time.

### File Responsibilities

New product files: `data_sources/financial_statements.py` (legacy dataclass ownership); `src/fundamentals/contracts.py` (query/metadata); `src/fundamentals/adapters.py` (source reads); `src/fundamentals/common_metrics.py` (eligible metrics); `src/fundamentals/read_service.py` (selection/acquisition/result); `src/fundamentals/coverage.py` (bounded coverage projection/inventory). Existing mapping, reuse, governance, collectors and storage schemas remain owners of their current responsibilities.

The only new UI component proposed is `apps/arkscope-web/src/settings/FinancialCoverageSection.tsx`. UI implementation and UI test edits below follow approval and reconciliation with the independently tested health/layout work.

## Offline Test Commands

Run from the worktree root after approval. This existing runner sanitizes provider environment, isolates application paths, blocks formal SQLite access and non-loopback Python networking. Each invocation gets a fresh directory; do not reuse a previous pytest basetemp or install packages. New fixtures additionally redirect FD `_FILE_CACHE_DIR` into `tmp_path` and use failure spies on all provider calls/writes during reads.

```bash
offline_pytest() {
  env ARKSCOPE_VERIFICATION_WORK="$(mktemp -d /tmp/arkscope-financial-test.XXXXXX)" \
    ARKSCOPE_FORMAL_DATA=/mnt/md0/PycharmProjects/ArkScope/data \
    PLAYWRIGHT_BROWSERS_PATH=/home/hyl/.cache/ms-playwright \
    /home/hyl/.virtualenvs/llm_app/bin/python \
    docs/superpowers/evidence/2026-09-27-provider-state/offline_tests.py "$@"
}
offline_web() {
  env NODE_OPTIONS="--require=$PWD/docs/superpowers/evidence/2026-09-14-runtime-cleanup-closeout/checks/offline_node.cjs" \
    npm test --workspace apps/arkscope-web -- "$@"
}
```

All RED commands below must fail on the named missing behavior/import, not infrastructure. Rerun the same command for GREEN and require zero failures. Existing live-provider skips remain skips. Store evidence outside tracked files except the final reviewed receipt; no credential, article-body or formal database exports.

## Tasks

### Task 1: Neutral Statement Ownership And Read Contract

**Files:** Create `data_sources/financial_statements.py`, `src/fundamentals/contracts.py`, `tests/test_financial_read_contract.py`. Modify `data_sources/sec_edgar_financials.py`, `data_sources/financial_datasets_client.py`, `src/tools/schemas.py`. Regression: `tests/test_sec_edgar_financials.py`, `tests/test_financial_datasets.py`.

**Interfaces:** Consume the existing dataclass constructor signatures unchanged. Produce `FinancialQuery`, metadata/coverage types and the additive schemas in Delivery Contract; no storage or provider calls in these modules.

- [ ] **1. Write failing contract tests.** `test_dataclasses_have_one_neutral_owner` asserts old SEC import `is` new import for all three classes and identical `dataclasses.fields`/`asdict` output. `test_month_statement_does_not_fabricate_a_day` constructs `FinancialStatement(report_period=None, end_month="2025-12", period_precision="month", period_type="annual", data={"revenue":"123400000"})` and asserts null day/fiscal period and unchanged decimal string. `test_old_day_payload_still_validates` exercises existing cache validators. Parameterize malformed months, bool offsets/ages, unknown source, nonfinite values and invalid IDs; require typed validation before any reader.

```python
assert LegacyIncomeStatement is NeutralIncomeStatement  # alias the two imports
assert month_statement.report_period is None and month_statement.fiscal_period is None
assert month_statement.model_dump()["data"]["revenue"] == "123400000"
```

- [ ] **2. RED:** `offline_pytest -q tests/test_financial_read_contract.py tests/test_financial_datasets.py`.
- [ ] **3. Implement the contract.** Move only the three dataclass definitions; SEC re-exports them, FD imports the neutral module. Add defaults sufficient for legacy cache parsing without granting old payloads new quality labels. Keep strict query validation and nullable precision metadata at the common boundary; do not weaken existing SEC payload validators to admit SA.
- [ ] **4. GREEN:** rerun RED, then `offline_pytest -q tests/test_sec_edgar_financials.py tests/test_financial_metric_basis.py`.
- [ ] **5. Review and commit:** verify no SEC acquisition code deletion or data/schema/config changes; commit the neutral types and contract with their tests.

### Task 2: Local SA/FD Adapters And Stable Identity

**Files:** Create `src/fundamentals/adapters.py`, `tests/financial_read_fixtures.py`, `tests/test_financial_read_adapters.py`. Modify `src/fundamentals/source_comparison.py`, `src/tools/financial_comparison_tools.py`. Regression: `tests/test_sa_company_data.py`, `tests/test_sa_company_symbols.py`, `tests/test_financial_datasets_freshness.py`.

**Interfaces:** Produce `ProviderRead`; `read_sa_statements(dal, query: FinancialQuery) -> ProviderRead`; `read_fd_statements(dal, query: FinancialQuery, *, mode: Freshness="stored", max_age_seconds: int | None=None, request_policy: dict | None=None) -> ProviderRead`. Extract pure `sa_records(body: dict, period: str) -> list[dict]` and `fd_records(statements: list[FinancialStatement], period: str) -> list[dict]` into `source_comparison.py` from the current comparator; both consumers use these and existing `METRICS`/`source_value`.

- [ ] **1. Write fixtures and failing tests.** Define fixture `financial_local(tmp_path, monkeypatch)` returning `(dal, http_spy, sec_spy)`, based on `tests/test_financial_local_reuse.py:local`, with `_sa_db` and all store/cache paths disposable. Define `sa_payload(statement="income-statement", *, ticker="AAPL", values: dict[str,str] | None=None) -> dict` from `tests/test_sa_company_data.py:capture`; extend labels before first save, so tests do not bypass structure-drift checks. FD fixtures must use the matching `MOCK_INCOME_RESPONSE`, `MOCK_BALANCE_RESPONSE`, `MOCK_CASHFLOW_RESPONSE` from `tests/test_financial_datasets.py`, not income rows relabeled as balance sheets.
- [ ] **2. Pin adapter behavior in tests.** `test_sa_without_market_db` asserts the SA value below, absence of market/profile file creation, and unchanged capture DB/time. `test_special_columns_and_unmapped_rows_preserved` asserts only dated requested-view records are normalized and original `get_sa_company_data` still returns TTM/Last Report plus an unmapped row. Test SA missing DB/table vs unreadable/corrupt DB and wrong digest with existing distinct `CompanyDataFailure` codes; test duplicate labels across sections, unknown unit, missing/mismatched currency, bool/nonfinite FD cells and same-month duplicate records with typed input gaps. FD currently collapses invalid/missing cache envelopes into `financial_datasets_cache_miss`: preserve that uncertainty, not a claim that the provider has no data; Task 5 separately reports inventory I/O failures. `test_fd_expired_retained_read_never_promotes` reads expired DB and file entries with `mode="stored"`, with no key or budget, and asserts zero HTTP/write calls and original timestamps. Include `BRK B`/`BRK-B` -> SA `BRK.B` without changing FD's query identity.

```python
assert statement.report_period is None
assert statement.end_month == "2025-12"
assert statement.data["revenue"] == "123400000"  # displayed 123.4 million
assert statement.value_metadata["revenue"].display_half_step == "50000"
assert statement.value_metadata["earnings_per_share"].normalized_value == "2.5"
```

- [ ] **3. RED:** `offline_pytest -q tests/test_financial_read_adapters.py tests/test_financial_source_comparison.py`.
- [ ] **4. Implement the adapter functions above.** SA resolves `dal._backend._sa_db` or `resolve_sa_db_path()` independently of market storage; raw references include observation ID, statement, view, currency and existing raw-tool arguments. Preserve full FD dataclass fields, not just the shared 13. Local FD calls always explicitly use `freshness="stored"`; reuse existing cache validation and its intentional no-promotion behavior. Preserve partial valid statements alongside failures. Collect per-statement observations before filtering/paging; invalid/duplicate newest records cannot silently make an older row "latest". No new storage authority.
- [ ] **5. GREEN:** rerun RED and `offline_pytest -q tests/test_sa_company_data.py tests/test_sa_company_symbols.py tests/test_financial_datasets_freshness.py`. Review original-row access and source precision, then commit the adapters and tests.

### Task 3: Justified Metrics And Typed Input Gaps

**Files:** Create `src/fundamentals/common_metrics.py`, `tests/test_common_financial_metrics.py`. Modify `src/fundamentals/metric_basis.py` only if a shared guard needs correction. Regression: `tests/test_financial_metric_basis.py`, `tests/test_financial_metrics_calculator.py`.

**Interfaces:** Consume Task 2 statements. Produce `derive_common_metrics(income: list[FinancialStatement], balance: list[FinancialStatement], cashflow: list[FinancialStatement], *, source: Provider) -> dict`, with existing `METRIC_FIELDS`, `metric_basis`, `metric_gaps`, plus `input_gaps: list[FinancialGap]` and `calculation_version="common-statements-v1"`; Task 4 merges `input_gaps` into result `read_gaps`. Do not change the legacy calculator version just for this new adapter.

- [ ] **1. Write failing cases.** `test_sa_same_column_ratios` uses revenue 100, gross 25, operating 10, net 5, current assets 50, current liabilities 20 in one column per statement and asserts `(gross_margin, operating_margin, net_margin, current_ratio) == (0.25, 0.1, 0.05, 2.5)`. Basis includes provider, observation ID, column index, month, null day and `provider_display_rounded`. `test_no_cross_column_or_currency_arithmetic` varies observation/column/currency; no ratio survives incompatible inputs. Parameterize missing/not-meaningful/ambiguous labels, zero/negative denominator, negative numerator and values above `2**53`; zero numerator is valid, missing inputs never become zero.
- [ ] **2. Pin unsupported and FD cases.** Assert SA debt/equity/FCF/cash gaps are `mapping_not_reviewed`, growth and ROA have `exact_period_identity_unavailable`, and ROE reports missing equity plus date requirements in `input_gaps.required_inputs`. Total liabilities must never become debt. FD regressions: complete vs incomplete debt components; same date/currency required for ROE/ROA; missing, duplicate or nonadjacent fiscal comparison periods do not produce growth; missing currency prevents arithmetic even if raw values remain visible. Existing FD additional fields and eligible ratios remain supported.

```python
assert tuple(metrics[k] for k in ("gross_margin", "operating_margin", "net_margin", "current_ratio")) == (0.25, 0.1, 0.05, 2.5)
assert metrics["total_debt"] is None
assert metrics["metric_gaps"]["total_debt"] == "mapping_not_reviewed"
```

- [ ] **3. RED:** `offline_pytest -q tests/test_common_financial_metrics.py tests/test_financial_metric_basis.py`.
- [ ] **4. Implement `derive_common_metrics`.** SA uses Decimal values from successful mapped cells and only the four named same-column ratios; publish finite four-decimal floats for legacy metric fields while preserving original string evidence. FD calls `derive_metrics(..., source="financial_datasets")` on day-identified statements and enriches basis with original observation references; add currency guards where existing same-column helpers do not enforce them. Unsupported valuation metrics remain null with input gaps, not optimistic zeros or inferred mappings.
- [ ] **5. GREEN:** rerun RED and `offline_pytest -q tests/test_financial_metrics_calculator.py`. Review that rounding labels survive every computed metric, then commit the metric changes and tests.

### Task 4: Common Reader And Explicit Acquisition Routing

**Files:** Create `src/fundamentals/read_service.py`, `tests/test_common_financial_read.py`. Modify `src/data_source_routing.py`, `src/data_source_catalog.py`, `src/tools/analysis_tools.py`; update `tests/test_data_source_routing.py`, `tests/test_data_source_settings.py`, `tests/test_data_source_catalog.py`, `tests/test_financial_local_reuse.py` where old SEC defaults are intentionally retired.

**Interfaces:** Produce `read_financials(dal, query: FinancialQuery) -> FundamentalsResult` and `summarize_financials(result: FundamentalsResult, query: FinancialQuery) -> FinancialCoverage`. `dal=None` constructs only the existing no-I/O `DataAccessLayer()` composition; no `ProfileStateStore` or storage installer. `get_fundamentals_analysis` becomes a thin delegating wrapper, preserving its existing positional parameters/default `freshness="auto"` and adding keyword-only `currency="USD", statement=None, end_month=None, observation_id=None, read_id=None, period_offset=0, period_limit=4`.

- [ ] **1. Write the routing matrix as parameterized failing tests.** Assert selected provider, exact HTTP count, requested endpoint(s), configuration bytes and all three output statement providers for each row:

| Inputs | Required outcome |
| --- | --- |
| Unset route, SA DB only, stored/default read | SA; zero file creation/provider calls. |
| Saved `[FD]`, SA available, FD missing | FD gap, no SA read and no setting change; explicit SA gives `data_source_not_selected`. |
| `[SA,FD]`, partial SA and complete FD | Partial SA for stored; no merged cash flow or FD call. |
| `[SA,FD]`, SA missing, eligible retained FD | Coherent FD local result, zero paid calls. |
| `[SA,FD]`, SA missing, FD partially cached or out of age | Retained FD where available plus primary-SA browser-update gap; zero paid calls. |
| `[FD,SA]`, no eligible local data, auto | Governed FD attempt only; no SEC call; first refusal suppresses remaining endpoint attempts. |
| Explicit selected FD auto, income cached | Buy only missing/out-of-window balance/cash flow with mocked transport; original income acquisition time unchanged. |
| Any route, refresh/auto-source | `financial_refresh_source_required`; zero dispatch. |
| Explicit SA refresh | `sa_browser_update_required`; zero host/collector mutation. |
| Explicit FD refresh with refusal/rate limit/lock busy | Existing typed failure; no successful old-cache fallback and no alternate provider. |
| Disabled `[]`, malformed route, unknown/retired provider | Fail closed without default substitution or configuration repair. |

- [ ] **2. Add historical identity tests.** Old SA ID reopens after a new capture; ID belonging to another ticker/view/currency fails. An old FD value remains readable by `end_month` despite expired TTL/age, but overwritten content plus old `read_id` returns `financial_read_changed` with no page values. Same-month differing FD days/duplicate SA columns yield ambiguity. Period/observation/read pins with auto/refresh fail before acquisition; unchanged paginated content has stable identity despite a new evaluation time. `test_historical_fd_growth_uses_retained_previous_period` keeps the selected month's previous fiscal period as input; `test_metrics_do_not_shift_on_page_two` keeps the original anchor. A mocked successful FD response that cannot persist returns `persisted=false`, `history="not_retained"` and `financial_retention_failed`, not reopenability. Assert reads never change acquisition/schedule bytes.

```python
assert sa_partial.data_source == "seeking_alpha" and sa_partial.cash_flow_statements == []
assert http_spy.call_count == 0 and sec_spy.call_count == 0
assert changed.status == "unavailable" and changed.read_gaps[0].code == "financial_read_changed"
```

- [ ] **3. RED:** `offline_pytest -q tests/test_common_financial_read.py tests/test_data_source_routing.py tests/test_data_source_settings.py tests/test_data_source_catalog.py`.
- [ ] **4. Implement reader and route changes.** Replace fallthrough with explicit SA/FD dispatch and the selection table above. Read FD policy only after deciding FD acquisition is authorized; reuse `fd_policy_from_settings`, `_get_fd_cache_days`, `configured_age` and the existing client/coalescer. Move orchestration helpers into the service/adapters, leaving compatibility wrappers until callers migrate; adapters must not import `analysis_tools` back into the service. Preserve `_sec_to_financial_statement` as a compatibility delegate to a neutral `to_financial_statement(obj) -> FinancialStatement` in `adapters.py`. `DATASETS["fundamentals_analysis"]` supports SA/FD, not SEC; catalog emits one SA browser-capture row with both financial route references, never an on-demand API duplicate. No reads persist the new absent-setting default. Construct results with explicit statuses and empty statement arrays for missing data, merge metric `input_gaps`, and populate source-aware update choices without invented report/check schedules.
- [ ] **5. GREEN:** rerun RED and `offline_pytest -q tests/test_financial_local_reuse.py tests/test_financial_datasets_governance.py tests/test_financial_reuse_concurrency.py`. Replace obsolete SEC auto-fallback assertions with explicit retirement assertions, preserving direct optional SEC-unit tests. Review and commit the common reader/routing changes.

### Task 5: Common Coverage And Local-Only API

**Files:** Create `src/fundamentals/coverage.py`, `tests/test_common_financial_coverage.py`, `tests/test_common_financial_api.py`. Modify `src/api/routes/fundamentals.py`, `src/api/routes/market_data.py`, `src/api/routes/health.py` (financial count only), `src/market_data_admin.py`, `src/tools/data_coverage_tools.py`, `src/tools/data_access.py`. Update financial assertions in `tests/test_api.py`, `tests/test_data_coverage_tools.py`, `tests/test_market_data_admin.py`, `tests/test_stored_sec_projection.py`.

**Interfaces:** Produce `financial_coverage(dal=None, *, tickers: list[str] | None=None, period="annual", source="auto", currency="USD", offset: int=0, limit: int=25) -> dict`. Limit 1..100. Return `{status, scope:"configured_local_candidates", candidate_count, items:list[FinancialCoverage], offset, next_offset, gaps}`. Only listed items are coverage-validated; `candidate_count` is a storage discovery count, not covered companies or an active-universe denominator. Each item is exactly `read_financials(...freshness="stored").coverage`.

- [ ] **1. Write failing coverage tests.** `test_market_absent_does_not_hide_sa` calls default service, `get_ticker_data_coverage`, `local_ticker_coverage` and API against SA-only fixtures; all agree on source/month/metrics, with no market creation. `test_price_news_failure_does_not_erase_financials` uses a malformed/unreadable market fixture and valid SA. `test_coverage_not_ttl_or_sec_row_counts` seeds old SEC rows and expired valid FD rows: SEC never contributes, retained FD does. `test_candidate_inventory_and_errors_are_honest` exercises corrupt rows/files, unselected providers, missing SA table, FD file-only reuse, sorting/deduplication, empty scope and pagination bounds. One store failure cannot erase another source's readable results; inventory failure is a gap, not a zero-coverage claim.
- [ ] **2. Write failing API tests.** `test_default_and_stored_alias_are_same_local_read` compares body with the tool using `freshness="stored"`; monkeypatch transport, writes and host spawn to raise. `GET /fundamentals/AAPL?source=seeking_alpha&end_month=2025-12` returns month precision; `stored=true` is a deprecated alias into the same service, never `read_cached_sec_fundamentals`. `test_explicit_refresh_endpoint_enforces_provider_and_write_gate` checks named provider, denied-write, refusal and partial results without live calls. Invalid HTTP query/body is 422; changed page identity is 409 with typed detail; ordinary missing/partial coverage is 200 with status/gaps.

```python
assert coverage["market_db"]["exists"] is False
assert coverage["financials"]["selected_source"] == "seeking_alpha"
assert client.get("/fundamentals/AAPL?stored=true").json()["snapshot_date"] is None
assert not market_path.exists() and http_spy.call_count == 0
```

- [ ] **3. RED:** `offline_pytest -q tests/test_common_financial_coverage.py tests/test_common_financial_api.py tests/test_data_coverage_tools.py tests/test_market_data_admin.py`.
- [ ] **4. Implement the coverage owner.** Discover candidate tickers using read-only, no-create SA `sa_company_observations` financial rows, FD-owned cache entries, and validated FD file-cache metadata, independently. Respect selected route/provider before reading content; do not scan article/research tables or infer source names from arbitrary filenames. Project only a bounded requested page through the common reader. `local_ticker_coverage` keeps price/news booleans and derives its compatibility `fundamentals` boolean from the selected common result; add `financials` with its coverage. The coverage tool returns the same `financials` even when market diagnostics fail. `DataAccessLayer.get_fundamentals(ticker)` delegates to stored common read instead of old snapshots.
- [ ] **5. Implement routes.** Declare `GET /fundamentals/coverage` before `/{ticker}`. `GET /fundamentals/{ticker}` accepts Task 4 read-only keyword parameters (plus deprecated `stored`), always stored and never auto-acquires, even with `stored=false`. Add `POST /fundamentals/{ticker}/refresh` with strict body `{source:Provider, period:Period="annual", currency:str="USD"}`; call `require_db_write("financial_refresh", {"ticker":ticker,"source":source})` before named refresh. No pagination/history inputs on acquisition. Remove financial SEC/TTL fields from `/market-data/status` and SEC financial count from `/status`; price/news endpoints remain otherwise unchanged. Internal shared-cache storage statistics may remain for their owners, not advertised as financial coverage. No provider-health or Settings-health rewrite here.
- [ ] **6. GREEN:** rerun RED and `offline_pytest -q tests/test_api.py tests/test_stored_sec_projection.py tests/test_eir006_retired_data_boundaries.py`. Retire projection-specific test assertions, not optional filing/identity tests. Review and commit the coverage/API changes.

### Task 6: Tool Channels, Evidence And Unsupported Consumers

**Files:** Modify `src/tools/registry.py`, `src/agents/openai_agent/tools.py`, `src/agents/anthropic_agent/tools.py`, `src/tools/financial_comparison_tools.py`, `src/tools/analysis_tools.py`, `src/tools/freshness.py`, `src/evidence_packet.py`, `src/data_source_routing.py`, `src/agents/shared/compressor/reducers.py`, `src/agents/shared/compressor/layers.py`, `src/agents/shared/compressor/transcript.py`. Create `src/fundamentals/tool_results.py`, `tests/test_common_financial_tool_channels.py`. Update `tests/test_financial_source_comparison.py`, `tests/test_evidence_packet.py`, `tests/test_freshness.py`, `tests/test_detailed_financials.py`, `tests/test_fundamentals_sec_cache.py`, `tests/test_tools.py` only for changed contracts.

**Interfaces:** Expose Task 4 wrapper signature consistently in registry/OpenAI/Anthropic and registry-driven ChatGPT/Claude adapters. Produce `financial_result_reducer(payload: str, *, budget: int) -> tuple[str, dict]`, selected for `get_fundamentals_analysis` and `tool_` alias. Preserve existing `get_sa_company_data` raw interface and comparator paging signature, with supported comparison providers SA/FD only.

- [ ] **1. Write failing channel cases.** Parameterize `openai`, `anthropic`, `chatgpt`, `claude` using the existing test pattern in `tests/test_financial_source_comparison.py:271`: identical stored result source/period/precision, strict bool/unknown-argument rejection, all new pins forwarded, disabled route honored and refresh/source validation before transport. `test_compressed_financial_read_preserves_basis_or_returns_gap` requires either complete bounded JSON with identity/basis/gaps or `{status:"unavailable", error_code:"financial_read_page_too_large", read_id, required_action:"repeat_same_read_with_smaller_page"}`; no prose-truncated numbers. Pin both wrapped and plain payloads and transcript retention behavior.
- [ ] **2. Pin downstream behavior.** `test_evidence_packet_keeps_sa_month_and_basis` asserts financial evidence includes `metric_basis`, `metric_gaps`, observation IDs/time and null `as_of` day for SA, without relabeling provider display numbers as filing-exact. Financial gathering uses stored mode; other evidence sources keep their contracts. `test_retired_detailed_and_peer_paths_do_not_acquire` asserts explicit unavailable/input-gap results and zero SEC/FD/Finnhub calls. `test_freshness_tool_uses_financial_coverage_not_expiry` asserts retained periods/source/gaps remain available even if price/news scan fails; no expired/valid financial counters or quarterly-update promise.

```python
assert channel_result["income_statements"][0]["period_precision"] == "month"
assert channel_result["metric_basis"]["gross_margin"]["precision"] == "provider_display_rounded"
assert reduced["error_code"] == "financial_read_page_too_large"
```

- [ ] **3. RED:** `offline_pytest -q tests/test_common_financial_tool_channels.py tests/test_evidence_packet.py tests/test_freshness.py tests/test_detailed_financials.py`.
- [ ] **4. Implement wrappers and legacy boundaries.** Describe SA/FD reported inputs and supported metrics instead of promising P/E/market cap. Default tool `auto` remains documented, but stored/history and explicit-provider refresh rules are identical to the service. Reuse extracted comparator records, remove SEC from its selection/default provider lists, deduplicate SA across route inventories, and preserve its no-authority/no-mixed-source meaning. Keep raw SA financial/research table paths and routes independent. Register lossless-or-typed-unavailable reduction, and protect pinned financial responses in the same compressor paths as other retained reads.
- [ ] **5. Implement explicit non-ported results.** `detailed_financials` has no implemented replacement provider in this delivery; retain a disabled dataset entry with no selectable SEC/FD/SA option. `get_detailed_financials` returns `financial_operation_not_ported` and input gaps before constructing the SEC calculator or querying earnings. `get_peer_comparison` likewise returns unavailable instead of counting null-valued peers as usable or inventing ranks. Keep direct calculators/optional SEC filing functions untouched. Remove financial-cache counts from `FreshnessRegistry` prompt formatting; `check_data_freshness(dal) -> str` appends a bounded common-coverage summary with source/period/gaps separately from price/news health. Preserve original acquisition times in evidence.
- [ ] **6. GREEN:** rerun RED and `offline_pytest -q tests/test_financial_source_comparison.py tests/test_freshness_tool_channels.py tests/test_fundamentals_sec_cache.py tests/test_tools.py tests/test_tool_output_channels.py tests/test_tool_output_policy.py`. Update old automatic SEC acquisition expectations without deleting useful direct-client tests. Review and commit the channel/consumer changes.

### Task 7: Main-Worker UI Integration And Browser States

**Ownership:** Future main-worker task only. Do not edit these UI files/tests in the planning lane. Integrate after the independent health/layout changes settle; preserve their lifecycle, provider-health and macro presentation fixes.

**Files:** Modify `apps/arkscope-web/src/api.ts`, `apps/arkscope-web/src/TickerDetail.tsx`, `apps/arkscope-web/src/Dashboard.tsx`, `apps/arkscope-web/src/settings/DataStorageSection.tsx`, `apps/arkscope-web/src/settings/DataSourceRoutingSection.tsx`, `apps/arkscope-web/src/settings/settingsReadCache.ts`; create `apps/arkscope-web/src/settings/FinancialCoverageSection.tsx`. Localize only changed financial copy in `apps/arkscope-web/src/i18n/resources/{en,zh-Hant}/{explore,settings,system}.ts`. `App.tsx`/`Settings.tsx` are verified composition boundaries, not planned layout rewrites.

**Tests:** Update `apps/arkscope-web/src/TickerDetail.test.tsx`, `apps/arkscope-web/src/Dashboard.test.tsx`, `apps/arkscope-web/src/SettingsLocalStorage.test.ts`, `apps/arkscope-web/src/settings/DataStorageSection.test.tsx`, `apps/arkscope-web/src/settings/DataSourceRoutingSection.test.tsx`, `apps/arkscope-web/src/settings/settingsReadCache.test.ts`, `apps/arkscope-web/src/i18n/resources.test.ts`. Create `apps/arkscope-web/src/financialReadContract.test.ts`, `apps/arkscope-web/src/settings/FinancialCoverageSection.test.tsx`, `docs/superpowers/evidence/2026-09-27-sa-fd-common-financial-read/browser_check.py`. Preserve `AppShell.test.tsx` navigation regression.

**Interfaces:** Produce `getStoredFundamentals(ticker: string, query?: FinancialReadQuery): Promise<FundamentalsResult>`, `getFinancialCoverage(query?: {period?: Period; source?: string; currency?: string; offset?: number; limit?: number}): Promise<FinancialCoveragePage>` and `refreshFinancials(ticker: string, body: {source: Provider; period: Period; currency: string}): Promise<FundamentalsResult>`. TypeScript types match Tasks 1/5, including string SA values/null day and typed gap fields. No `freshness=auto` UI read.

- [ ] **1. Write failing Vitest cases.** Require source/period/capture/precision/metric-gap agreement across ticker, Dashboard and Settings fixtures. Opening, rereading, choosing a source/period and paging issue GETs only. Explicit FD update requires named selection and confirmation; cancel makes zero POSTs, refusal retains a separately labeled previous read, busy disables duplicate clicks. SA action navigates to existing browser acquisition information and capture URL, never silently opens/queues pages. With saved `[FD]`, SA is not preselected or saved on render. No SEC/TTL financial counters remain, including developer diagnostics.

```typescript
expect(apiMocks.refreshFinancials).not.toHaveBeenCalled(); // initial/source-selection reads
expect(apiMocks.putDataSourceRoute).not.toHaveBeenCalled(); // saved FD-only route
expect(host.textContent).toContain("2025-12");
expect(host.textContent).not.toContain("2025-12-31"); // month-only SA fixture
```

- [ ] **2. RED:** `offline_web src/financialReadContract.test.ts src/TickerDetail.test.tsx src/Dashboard.test.tsx src/settings/FinancialCoverageSection.test.tsx src/settings/DataStorageSection.test.tsx src/settings/DataSourceRoutingSection.test.tsx`.
- [ ] **3. Implement financial rendering only.** Keep independent diagnostic failures via `Promise.allSettled`; add request-generation checks for source/ticker/period changes and clear obsolete pinned IDs. Show per-statement retained periods, source, original capture time, units/rounding and missing inputs; display a gap reason instead of an unexplained dash for unsupported metrics. Render decimal strings without coercing large SA values to JS Number. Dashboard gets a separate local coverage request, not the SEC count in `/status`; Settings replaces the financial cache diagnostics block with `FinancialCoverageSection`, leaving price/news/lifecycle/optional SEC filing controls separate. Clearly label the candidate inventory and page scope; do not claim all candidates have usable statements.
- [ ] **4. Implement read-state invalidation.** Add scoped `financial_coverage:${period}:${source}:${currency}:${offset}:${limit}` Settings cache keys with the existing 60-second read-cache/15-minute retention pattern; this is UI request reuse, not fact validity. Invalidate financial keys after explicit route saves and successful FD updates, not on a mere source-picker change. SA action uses existing `getSAAcquisitionStatus()`; render unconfigured/paused/rate-limited/error facts as reported. That endpoint has no per-ticker running/next-report evidence: display unknown rather than infer it. Do not make host-pinging extension health a prerequisite.
- [ ] **5. GREEN:** rerun RED, then `offline_web src/SettingsLocalStorage.test.ts src/settings/settingsReadCache.test.ts src/i18n/resources.test.ts src/AppShell.test.tsx`. Run `npm run typecheck --workspace apps/arkscope-web` and `npm run check:i18n-literals --workspace apps/arkscope-web`.
- [ ] **6. Add fixture-only browser acceptance.** Use the loopback/interception/screenshot pattern in `docs/superpowers/evidence/2026-09-27-provider-state/browser_check.py`, but new financial fixtures, not the formal sidecar. Start Vite on an unused port with `npm run dev --workspace apps/arkscope-web -- --host 127.0.0.1 --port 8488 --strictPort` (choose another unused port if occupied). Intercept **all** API routes, reject external traffic and any unapproved mutations. Run `/home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-27-sa-fd-common-financial-read/browser_check.py --url http://127.0.0.1:8488 --output /tmp/arkscope-financial-browser`; stop the fixture server afterward.

| Browser state | Required visible/interaction assertion |
| --- | --- |
| SA-only DB, no market DB | Ticker Data tab, Dashboard and Settings retain SA financials; price/news gaps are separate. |
| Annual page with TTM; quarterly page | Month labels remain months, TTM is not shown as annual; no fabricated fiscal quarter/day. |
| Partial SA / no capture / malformed capture | Missing statements vs invalid source are distinguishable; browser-update action, no paid fallback. |
| Expired retained FD / historical SA ID | Original acquisition/observation identity remains; no TTL-invalid claim or provider-latest claim. |
| FD-only saved route / disabled / invalid route | Actual selection shown, actionable Settings repair, no auto-save or automatic SA switch. |
| FD confirm/cancel/running/refused/succeeded | Only confirmed named refresh POST; last read and refresh outcome remain distinct. |
| Collector unconfigured/paused/rate-limited/unavailable | Existing state visible, no invented server refresh or future reporting date. |
| Fast source/period navigation; changed FD page identity | Late response ignored; changed identity prompts a fresh local read rather than appending inconsistent values. |
| Financial success plus price/news/status HTTP failure | Financial section remains populated; retry targets read failure without acquisition. |

Run each principal surface at 1440x1000 and 390x844 in English and Traditional Chinese. Require zero page errors/rejected unexpected requests, keyboard-accessible controls, no page-wide horizontal overflow/overlap, contained statement-table scrolling, and source/period/error text fitting its controls. Inspect screenshots, including long numeric strings and source names. No UI implementation or browser acceptance is claimed by saving this plan.

- [ ] **7. Review and commit the UI integration and its fixtures.** Do not include unrelated Settings changes in this commit.

### Task 8: Freeze, Regression And Delivery Review

**Files:** Future verification receipt only: `docs/superpowers/evidence/2026-09-27-sa-fd-common-financial-read/README.md`; raw logs/screenshots in disposable verification storage. Re-read this plan/spec and the final diff; do not edit unrelated code to make a gate green.

**Interfaces:** All seven prior tasks and the main worker's UI integration must be present before claiming a common product delivery. Partial backend completion is not acceptance.

- [ ] **1. Freeze the committed implementation tree.** Record revision/tree hashes, exact test commands and skipped prerequisites. Reconcile financial fixture expectations with the accepted health/layout contracts. Product code, tests and harnesses remain unchanged during the final gates; any repair requires a new freeze and rerun.
- [ ] **2. Run focused acceptance:** `offline_pytest -q tests/test_financial_read_contract.py tests/test_financial_read_adapters.py tests/test_common_financial_metrics.py tests/test_common_financial_read.py tests/test_common_financial_coverage.py tests/test_common_financial_api.py tests/test_common_financial_tool_channels.py`. Require green tests covering all five Review Focus entries.
- [ ] **3. Run full backend:** `offline_pytest -q -x tests`. Existing paid/live skips remain skips; unexpected skips or a missing browser prerequisite are explicitly unresolved, not passes. Unit-test the existing runner's `audit(event, args)` directly with synthetic forbidden-path/socket event arguments; do not attempt a real formal SQLite connection or external socket.
- [ ] **4. Run full frontend/build:** `offline_web`, `npm run build --workspace apps/arkscope-web`, `npm run check:i18n-literals --workspace apps/arkscope-web`, then `node --test apps/arkscope-desktop/*.test.js`. Repeat the Task 7 fixture browser suite against the frozen source. Do not run provider/cleanup scripts.
- [ ] **5. Audit reachable financial consumers.** `rg -n 'stored_annual_sec_fundamentals|read_cached_sec_fundamentals|storedSecFundamentals|financial_cache|fundamentals_tickers|sec_edgar' src/fundamentals src/tools src/api apps/arkscope-web/src` and classify remaining matches. Accept shared FD storage plumbing, direct optional SEC compatibility/calculator tests, identity/lifecycle and optional filing capabilities; reject active common-read SEC fallthrough, financial TTL coverage labels, stale schema enums and paid calls from stored reads. Verify `git diff --check`.
- [ ] **6. Present receipt and unresolved limits for review.** Record zero provider dispatch from read fixtures, unchanged disposable capture/acquisition/config metadata, FD admission/coalescing results and browser screenshots. Existing formal cleanup receipt is historical evidence only; do not reopen the formal installation or claim its counts are still zero. Commit only the final verification documentation after the freeze, then follow the agreed integration authority; no automatic push or production acquisition.

## Review Decisions And Self-Review

- **Default selection needs review:** this plan proposes SA-first only for a missing route setting. The formal installation's saved FD-only route remains untouched and will show an FD gap until the operator explicitly enables SA. Showing SA automatically on that installation would require a separately approved configuration change, not a code-side fallback.
- **API compatibility needs review:** GET becomes always local-only; acquisition moves to named POST/tool refresh. This prevents read surfaces from buying data but deliberately changes unparameterized GET behavior. `stored=true` remains an alias, not a second implementation. Check external consumers before release; none beyond the repository consumers were verified here.
- **Bounded delivery:** FD retained history remains the existing query window/current cache version. SA has month precision and independently captured statement observations. No atomic cross-statement revision guarantee, complete SA financial mapping, latest-provider guarantee, next-report calendar or detailed valuation/peer replacement is promised.
- **Existing FD diagnostic limit:** cache-envelope rejection currently becomes a generic cache miss. The plan reports explicit inventory I/O errors where observable, but does not pretend the client distinguishes every absent/corrupt cache cause or proves provider-side absence.
- **UI ownership:** Task 7 is a main-worker handoff with discovered states and concrete paths/tests, not permission to overwrite concurrent Settings work. Collector status currently lacks per-ticker running/next-check information; this delivery displays unknown instead of extending acquisition telemetry.
- **Self-review performed:** mapped spec requirements to Tasks 1-8; isolated already completed cleanup from delivery; checked path/signature references against source; reused exact 13-field mappings and FD period/debt guards; pinned no-paid-fallback and no-market-DB cases; included tool serialization/evidence, HTTP and UI-state failure paths. No provider connector, formal state migration, article work or SEC identity/lifecycle deletion is included. Product tests and browser checks listed here are execution gates, not tests run during planning.
