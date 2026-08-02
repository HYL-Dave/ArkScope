# EIR-006 Valuation Price Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **Status:** TASK 0 EVIDENCE REVIEW NEXT - TASK 1 NOT STARTED
>
> **Date:** 2026-08-03
>
> **Design authority:** `124622bc`
>
> **Grounding commit:** `fd6d1b86383df2a98f97b235d9796d4bcaaa7a58`

**Goal:** Stop detailed-financials valuation from presenting repository CSV
closes as current, make stored-fundamentals status follow the positive annual
SEC cache contract, and retire every current product reference to the old
price/fundamentals authorities before a separately approved physical deletion.

**Architecture:** Extract the existing completed-session calendar into one
shared authority, add a no-create read-only selector over
`market_data.db.prices`, and split detailed-financials into cacheable static SEC
facts plus request-time valuation derived from an explicitly qualified local
price. Reuse one positive annual SEC-cache projection across API/status/tool
consumers; make FileBackend and sync projections honestly empty for retired
domains; update the three frontend surfaces and current documentation. Merge
and verify the product cutover before constructing an exact deletion manifest.

**Tech stack:** Python 3.10, pytest, SQLite, pandas, Pydantic, FastAPI, React,
TypeScript, Vitest, i18next, Git, shell structural gates.

---

## 0. Authority And Execution Boundary

### 0.1 Canonical authority

This plan implements only:

```text
docs/superpowers/specs/2026-08-01-eir-006-valuation-price-truth-design.md
reviewed design commit: 124622bc
reviewed design blob SHA-256:
7ec313d12e87b0e6557172c173d7f9d55468f36551514d463f6faaa0ff62bee4
plan-gate status evolution SHA-256:
a5c155d45ba690fd7e29aeaa37d49eeb44dc224496d51f3733f717afa0686f6c
```

The second SHA differs only in the status/header and Section 14 gate handoff;
it does not change a locked product or deletion ruling.

Implementation remains in:

```text
worktree: /tmp/arkscope-eir-006
branch:   codex/eir-006-valuation-price-truth
base:     124622bc
```

The design fixes the product and data rulings. This plan may sequence and
mechanize them, but it may not reinterpret them. In particular:

- `market_data.db` 15-minute rows are the sole valuation-price authority;
- the latest completed US session uses the existing 16:30 ET contract;
- one valid row establishes day presence; 26-slot completeness is forbidden;
- there is no older-day fallback;
- unavailability is exactly `no_qualified_price`;
- all nine dynamic valuation fields are null when no price qualifies;
- static SEC facts use the new v2 cache key and old cache keys are never read;
- the annual SEC/Financial Datasets analysis order and spend gate remain
  unchanged except that the retired local snapshot may no longer short-circuit
  them;
- no provider request is needed for implementation or verification; and
- product-cutover approval is not physical-deletion approval.

### 0.2 Product and data separation

Tasks 0-7 own the product cutover, tests, frontend copy, current documentation,
merge, and read-only rollout observations. They may not move or delete a CSV,
delete a SQLite row, stop or alter the scheduler, or write a production DB.

Task 8 may build a fresh read-only destructive manifest after the product
cutover is merged. It may not execute it. Task 9 is blocked until all of these
are true:

1. Task 8 has a reviewed exact manifest;
2. a bounded amendment pins the exact destructive controller bytes, exact
   path list, exact row keys, database identity, rollback transaction, and
   verification commands;
3. independent review clears that amendment; and
4. the user separately approves that exact manifest.

No approval of this plan, Tasks 0-7, a product implementation review, or a
merge substitutes for item 4.

### 0.3 Provider and production boundary

Automated tests use fixture SQLite databases and provider doubles. They must
not inherit provider credentials, dial IBKR, SEC, Financial Datasets, Finnhub,
Polygon, or any other network endpoint, start a scheduler, or use a production
browser profile. Existing earnings-history and upcoming-earnings behavior is
tested through doubles; it is not removed or silently skipped.

Before every admitted native backend run:

- run the exact wakeup probe below in the same native execution context;
- use the unchanged EIR-002 native wrapper and deterministic reporter;
- use a fresh exact-tip worktree with no `config/.env`, an existing empty
  `data/`, absent `src/data`, and only the pinned test-toolchain link;
- inventory ordinary/ignored status, `data`, `src/data`, symlinks, and
  toolchain identities before and after;
- exact-path quarantine new test artifacts and prove byte-identical boundary
  restoration; and
- stop on any modified pre-existing file.

Pinned assets:

```text
/tmp/arkscope_asyncio_wakeup_probe.py
SHA-256:
10647c1e64c49fc2e082701d7a735e40782620314c125cd103a9a3f9bb37bc2e
required result:
{"callback_fired": true, "ready_count": 0, "wake_bytes": 0}

/tmp/eir002-green-baseline/arkscope_eir002_reporter.py
SHA-256:
09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928

/tmp/eir002-green-baseline/run_native.sh
SHA-256:
e7c963f1bc97125b70b435fb3c41bf4e59d501f0da561f2ef6d921c12083c84f

/mnt/md0/PycharmProjects/ArkScope/package-lock.json
SHA-256:
5322cb03099b873066b7572c02db68a427ddc7509fdc9850cf9d8d3948a19f2c

/mnt/md0/PycharmProjects/ArkScope/node_modules/.package-lock.json
SHA-256:
4dd5182f8111b54dd608344c45513f3b310f39321a3cc9832b60cefc2fa241ff

Node: v22.14.0
jsdom: 29.1.1
```

The managed sandbox remains valid for collection, static checks, frontend
tests, and compatible focused backend tests. It is not canonical full-suite
admission when the wakeup probe reports the known sandbox-incompatible shape.

### 0.4 Git and artifact discipline

The isolated worktree requires the repository's reviewed git-crypt no-op
configuration because the key is unavailable there:

```bash
git -c filter.git-crypt.smudge=cat \
    -c filter.git-crypt.clean=cat \
    -c filter.git-crypt.required=false <command>
```

Do not use `git reset --hard`, broad restore commands, basename matching,
destructive globs, or an existing evidence directory as a fresh run. Each
runtime stage name is single-use. Every mutation cycle records the pre-mutation
blob SHA, exact diff, owning-node result, restore operation, and restored SHA.

---

## 1. File Map

### 1.1 Product owners

| File | Responsibility |
|---|---|
| `src/market_sessions.py` | New shared ET clock, 16:30 completion, and latest-completed-session authority |
| `src/market_data_direct.py` | Import/re-export the shared calendar helpers without changing collection behavior |
| `src/valuation_price.py` | New no-create read-only 15-minute qualified-price selector |
| `src/tools/schemas.py` | Add `ValuationPriceBasis` and nest it in `DetailedFinancials` |
| `src/fundamentals/cache.py` | Own detailed-financials v2 key/payload validation and positive annual SEC projection |
| `data_sources/financial_metrics_calculator.py` | Remove repository-file/IBKR snapshot reads and calculate valuation only from explicit price and base-unit facts |
| `src/tools/analysis_tools.py` | Cache static facts, select price every request, derive dynamic values, remove legacy snapshot short circuits, report peer absence |
| `src/tools/backends/file_backend.py` | Return exact empty retired price/fundamentals shapes without path probes |
| `src/tools/backends/sqlite_backend.py` | Project fundamentals tickers from positive annual SEC cache rows, not the legacy table |
| `src/tools/backends/local_market_backend.py` | Treat local SEC-cache fundamentals ticker projection as authoritative even when empty |
| `src/market_data_admin.py` | Project stored SEC fundamentals and suppress retired fundamentals sync telemetry |
| `src/tools/data_coverage_tools.py` | Use the same stored SEC projection and return `sync.fundamentals=null` |
| `src/daily_update.py` | Read current SQLite price statistics rather than repository files |
| `src/tools/registry.py` | Remove the old model-visible valuation-source claim |
| `src/agents/anthropic_agent/tools.py` | Keep the Anthropic tool description byte-aligned with the registered contract |
| `src/agents/openai_agent/tools.py` | Keep the OpenAI tool description byte-aligned with the registered contract |

No database schema migration is planned. No price collector, current quote,
provider, scheduler, or Financial Datasets policy owner may change.

### 1.2 Frontend owners

| File | Responsibility |
|---|---|
| `apps/arkscope-web/src/api.ts` | Add exact `local_cache` `SourcePath` and keep API shapes typed |
| `apps/arkscope-web/src/TickerDetail.tsx` | Render `local_cache` as localized stored-SEC copy |
| `apps/arkscope-web/src/Dashboard.tsx` | Map stored data-source keys to localized product labels rather than raw IDs |
| `apps/arkscope-web/src/settings/DataStorageSection.tsx` | Describe stored SEC coverage and no retired fundamentals sync |
| `apps/arkscope-web/src/i18n/resources/{en,zh-Hant}/{explore,settings,system}.ts` | Add exact locale-parity stored-SEC labels and revised current copy |
| `apps/arkscope-web/src/settings/settingsCopy.ts` | Keep Settings static search/copy authority synchronized |

### 1.3 Current documentation owners

The current-authority census must decide every hit before editing. The known
owners that require wording changes are:

```text
training/data_prep/prepare_training_data.py
training/data_prep/README.md
docs/analysis/FINANCIAL_METRICS_FORMULAS.md
docs/data/DATA_INVENTORY.md
docs/data/DATA_SUBSCRIPTION_GUIDE.md
docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md
```

Historical specs/evidence remain truthful historical records and must not be
silently rewritten. `data_sources/ibkr_client_id.py` comments are classified
by the census; edit them only if they make a current runnable claim about a
retired collector, not merely because they contain a lexical match.

### 1.4 New and evolved backend tests

| File | Responsibility |
|---|---|
| `tests/test_valuation_price.py` | Ten independent selector/calendar/no-create contracts |
| `tests/test_financial_metrics_calculator.py` | Explicit-price units, dependent nulls, and no legacy-file convenience paths |
| `tests/test_stored_sec_projection.py` | One shared stored-SEC projection across all backend consumers |
| `tests/test_eir006_retired_data_boundaries.py` | Current-copy and fail-closed static consumer census |
| `tests/test_detailed_financials.py` | Evolve schema/integration nodes; replace the obsolete IBKR override node; add v2/static-cache contracts |
| `tests/test_fundamentals_sec_cache.py` | Prove the annual analysis path ignores the legacy snapshot and preserves SEC/FD order |
| `tests/test_peer_comparison.py` | Count/name unavailable valuation peers and exclude null values |
| `tests/test_daily_update_wrapper.py` | Prove SQLite status without repository scanning |
| `tests/test_db_backend_retired_prices.py` | Prove FileBackend retired-domain shapes and no probes |
| `tests/test_market_data_admin.py` | Evolve stored-fundamentals and sync assertions |
| `tests/test_data_coverage_tools.py` | Evolve stored-fundamentals and sync assertions |
| `tests/test_sqlite_backend.py` | Evolve ticker projection/routing assertions |
| `tests/test_api.py` | Evolve `/status`, stored-only fundamentals, and source-path contracts |
| `tests/test_tools.py` | Evolve tool result shape without provider access |
| `tests/test_evidence_packet.py` | Keep downstream institutional evidence behavior explicit |
| `tests/test_market_data_direct.py` | Preserve all existing calendar/backfill node identities after extraction |

### 1.5 Frontend tests

| File | Disposition |
|---|---|
| `apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts` | Evolve existing storage node(s), no rename |
| `apps/arkscope-web/src/TickerDetail.test.tsx` | Evolve existing source-path/localization node(s), no rename |
| `apps/arkscope-web/src/i18n/resources.test.ts` | Evolve existing resource inventory node(s), no rename |
| `apps/arkscope-web/src/settings/settingsCopy.test.ts` | Evolve existing static-copy node(s), no rename |
| `apps/arkscope-web/src/Dashboard.test.tsx` | New one-node product-label contract |

### 1.6 Authority and evidence files

| File | Responsibility |
|---|---|
| `docs/superpowers/specs/2026-08-01-eir-006-valuation-price-truth-design.md` | Record GREEN design review and next gate only |
| `docs/superpowers/plans/2026-08-03-eir-006-valuation-price-truth.md` | This exact RED-first execution authority |
| `docs/superpowers/evidence/2026-08-03-eir-006-valuation-price-truth.md` | Record execution, review, merge, rollout, manifest, and deletion evidence |
| `docs/design/ENGINEERING_ISSUE_REGISTER.md` | Keep EIR-006 promoted through product merge and physical closeout |
| `docs/design/PROJECT_PRIORITY_MAP.md` | Newest-first gate handoffs |

---

## 2. Immutable Accounting

### 2.1 Backend collection identities

The base was reproduced at `124622bc` through the deterministic reporter. The
target stream was constructed before edits by deleting the one obsolete node
and inserting the 29 exact new IDs in Section 2.3, followed by `LC_ALL=C sort`.

| Stage | Delta from base | Nodes | Sorted node-ID SHA-256 |
|---|---:|---:|---|
| Base | `+0/-0` | 4,553 | `69152591306a8dee5e66e2efeb2f1ec12720c8a1a1ffe36def613f4fe5a676ca` |
| Task 1 | `+10/-0` | 4,563 | `5fdc93f3dc78548048d7269d8088715028a57b1e2c54fe1ac422154d187f3986` |
| Task 2 | `+19/-1` | 4,571 | `b247d173d3520668a5d475b0ed02f948d117c1097ed5ad86063a2dbf76d07b68` |
| Task 3 | `+21/-1` | 4,573 | `e0ee195eb90bc9172dae36680b15b3285b3d82013c7c762e1989c955be6ea3b1` |
| Task 4 | `+27/-1` | 4,579 | `6672d3df26b7c420d3253e4826b7104bfd0e5640ae16a1616ea75dd605b38639` |
| Final | `+29/-1` | 4,581 | `6e4994bb664501cff75cb06dbad18db82ba68cbbe4b2b26c4d480250d7c4699f` |

Final runtime admission is exact:

```text
4,581 collected and seen
4,509 passed
72 skipped
0 failed
0 errors
non-passing stream SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

No helper may be named `test_*`. No existing node may be renamed, newly
parametrized, skipped, or marked xfail. The sole removal is explicit in Section
2.2. Any other collection delta is a Stop Condition.

### 2.2 Exact removed node

```text
tests/test_detailed_financials.py::TestGetDetailedFinancials::test_ibkr_enrichment_overrides
```

It is replaced, not silently weakened, by the new exact node:

```text
tests/test_detailed_financials.py::TestGetDetailedFinancials::test_legacy_ibkr_snapshot_cannot_override_sec_or_price_basis
```

### 2.3 Exact new backend nodes

```text
tests/test_valuation_price.py::test_before_completion_uses_previous_market_date
tests/test_valuation_price.py::test_after_completion_accepts_today
tests/test_valuation_price.py::test_weekend_and_holiday_select_previous_completed_session
tests/test_valuation_price.py::test_one_row_qualifies_without_slot_completeness
tests/test_valuation_price.py::test_missing_required_date_does_not_fallback_to_older_bar
tests/test_valuation_price.py::test_missing_store_is_typed_unavailable_and_no_create
tests/test_valuation_price.py::test_unreadable_schema_and_query_failures_are_typed_sanitized
tests/test_valuation_price.py::test_et_market_date_not_raw_utc_date_owns_selection
tests/test_valuation_price.py::test_invalid_close_values_do_not_qualify
tests/test_valuation_price.py::test_alias_resolves_to_canonical_price_rows
tests/test_detailed_financials.py::TestGetDetailedFinancials::test_old_metrics_cache_key_is_ignored
tests/test_detailed_financials.py::TestGetDetailedFinancials::test_v2_static_cache_excludes_price_and_dynamic_fields
tests/test_detailed_financials.py::TestGetDetailedFinancials::test_static_cache_hit_recomputes_dynamic_metrics_without_static_refetch
tests/test_detailed_financials.py::TestGetDetailedFinancials::test_no_qualified_price_preserves_static_and_nulls_dynamic_fields
tests/test_detailed_financials.py::TestGetDetailedFinancials::test_legacy_ibkr_snapshot_cannot_override_sec_or_price_basis
tests/test_detailed_financials.py::TestGetDetailedFinancials::test_data_source_remains_static_sec_source
tests/test_financial_metrics_calculator.py::test_explicit_price_uses_base_unit_shares_without_million_scaling
tests/test_financial_metrics_calculator.py::test_missing_inputs_null_only_dependent_valuation_fields
tests/test_financial_metrics_calculator.py::test_no_price_convenience_and_cli_paths_cannot_read_legacy_files
tests/test_fundamentals_sec_cache.py::test_annual_analysis_ignores_legacy_snapshot_and_preserves_sec_fd_order
tests/test_peer_comparison.py::TestDataQuality::test_unavailable_valuation_prices_are_counted_named_and_excluded
tests/test_daily_update_wrapper.py::test_price_status_uses_sqlite_stats_without_scanning_repository_files
tests/test_db_backend_retired_prices.py::test_file_backend_prices_and_fundamentals_are_empty_without_path_probes
tests/test_stored_sec_projection.py::test_legacy_fundamentals_row_does_not_project_as_stored
tests/test_stored_sec_projection.py::test_positive_annual_sec_cache_is_the_shared_projection_authority
tests/test_stored_sec_projection.py::test_nonpositive_and_nonannual_cache_rows_do_not_project_as_stored
tests/test_stored_sec_projection.py::test_fundamentals_sync_is_null_while_price_and_news_remain_unchanged
tests/test_eir006_retired_data_boundaries.py::test_current_docs_training_and_tool_copy_name_only_current_authorities
tests/test_eir006_retired_data_boundaries.py::test_current_runtime_consumer_census_is_closed_and_exact
```

### 2.4 Backend focused identity

The focused set is the exact union of these 18 files:

```text
tests/test_agents.py
tests/test_api.py
tests/test_daily_update_wrapper.py
tests/test_data_coverage_tools.py
tests/test_db_backend_retired_prices.py
tests/test_detailed_financials.py
tests/test_eir006_retired_data_boundaries.py
tests/test_evidence_packet.py
tests/test_financial_metrics_calculator.py
tests/test_fundamentals_cache.py
tests/test_fundamentals_sec_cache.py
tests/test_market_data_admin.py
tests/test_market_data_direct.py
tests/test_peer_comparison.py
tests/test_sqlite_backend.py
tests/test_stored_sec_projection.py
tests/test_tools.py
tests/test_valuation_price.py
```

| Collection | Files | Nodes | Sorted node-ID SHA-256 |
|---|---:|---:|---|
| Existing affected files | 14 | 307 | `46f8c9d0cd9e3b525d051e2231d4d48ed2975192886cdeb293ec71662341ae51` |
| Final focused | 18 | 335 | `58230b548925b29035cff401520e0948b01dcaed8da2deed41149bea6b4a5ae1` |

### 2.5 Existing backend nodes that evolve in place

The following existing identities are load-bearing and may change assertions or
fixtures without changing names:

```text
tests/test_detailed_financials.py::TestDetailedFinancialsSchema::test_minimal_creation
tests/test_detailed_financials.py::TestDetailedFinancialsSchema::test_full_creation
tests/test_detailed_financials.py::TestDetailedFinancialsSchema::test_model_dump
tests/test_detailed_financials.py::TestGetDetailedFinancials::test_returns_detailed_financials_type
tests/test_tools.py::TestAnalysisTools::test_get_fundamentals_analysis
tests/test_api.py::TestFundamentalsEndpoints::test_fundamentals
tests/test_api.py::TestHealth::test_status
tests/test_api.py::test_fundamentals_stored_mode_reads_local_cache_without_provider_fetch
tests/test_api.py::test_fundamentals_stored_source_path_mapping
tests/test_api.py::test_fundamentals_stored_expired_cache_is_honest_empty
tests/test_evidence_packet.py::test_packet_has_expected_sources_and_tags
tests/test_evidence_packet.py::test_one_failing_source_degrades_to_coverage
tests/test_market_data_admin.py::test_local_stats_financial_cache_counts
tests/test_market_data_admin.py::test_local_ticker_coverage
tests/test_market_data_admin.py::test_status_news_sync_follows_active_writer_only
tests/test_market_data_admin.py::test_p0c_market_status_reports_prices_local_authority
tests/test_data_coverage_tools.py::test_ticker_data_coverage_explains_weekend_price_gap
tests/test_data_coverage_tools.py::test_ticker_coverage_news_sync_follows_active_writer_only
tests/test_sqlite_backend.py::test_get_available_tickers
tests/test_sqlite_backend.py::test_available_tickers_routing
```

All 70 existing `tests/test_market_data_direct.py` nodes must remain present and
green after the calendar extraction. Existing agent/tool schema nodes remain
present and are rerun because model-visible descriptions change.

### 2.6 Frontend identities

The canonical frontend list is normalized from `vitest list --json` as sorted
`relative_file<TAB>full_test_name` rows.

The normalizer is part of the identity contract. It must JSON-decode the
`name` field before writing it. Raw JSON text extraction and `jq @tsv` are
forbidden because they preserve or add an escape layer around literal
backslashes. Materialize the source between the markers byte-for-byte; the
identity covers the shebang through the final newline after `main()`:

```text
62 lines / 2,233 bytes
SHA-256:
955dca592d243505ced622a84e88a35160a3fa787ffb954f38a6a43e1a72fcac
```

<!-- EIR006_VITEST_LIST_NORMALIZER_START -->
```python
#!/usr/bin/env python3
"""Normalize decoded Vitest list JSON into deterministic node rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--web-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _reject_record_separator(value: str, *, field: str) -> None:
    if any(separator in value for separator in ("\t", "\n", "\r")):
        raise ValueError(f"{field} contains a record separator")


def main() -> None:
    args = _arguments()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("Vitest list JSON must be an array")

    web_root = args.web_root.resolve(strict=True)
    rows: list[str] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise TypeError(f"entry {index} must be an object")
        file_value = item.get("file")
        name = item.get("name")
        if not isinstance(file_value, str) or not isinstance(name, str):
            raise TypeError(f"entry {index} requires string file and name")

        file_path = Path(file_value)
        if not file_path.is_absolute():
            raise ValueError(f"entry {index} file must be absolute")
        try:
            relative_file = file_path.resolve(strict=True).relative_to(web_root)
        except ValueError as exc:
            raise ValueError(f"entry {index} escapes web root") from exc

        relative_text = relative_file.as_posix()
        _reject_record_separator(relative_text, field=f"entry {index} file")
        _reject_record_separator(name, field=f"entry {index} name")
        rows.append(f"{relative_text}\t{name}")

    if len(rows) != len(set(rows)):
        raise ValueError("normalized Vitest node rows must be unique")

    rows.sort(key=lambda row: row.encode("utf-8"))
    output = "" if not rows else "\n".join(rows) + "\n"
    args.output.write_bytes(output.encode("utf-8"))


if __name__ == "__main__":
    main()
```
<!-- EIR006_VITEST_LIST_NORMALIZER_END -->

| Collection | Files | Nodes | SHA-256 |
|---|---:|---:|---|
| Base full | 96 | 1,076 | `ef7f106054745c137ff70fe6ef2043bb7655185379de1f0a6ec3b1b2997b9396` |
| Target full | 97 | 1,077 | `3f5e9f5bbe88d5ac48015a8c9e9d669dcd649a53a2ac868fc8a98d21f8d7e4eb` |
| Base focused | 4 | 45 | `09a2b4ef080a5badab79fb674b5c5c6b85a0eb7c639c2fe9534616eff2b5bb84` |
| Target focused | 5 | 46 | `5d64841ccdd943eb81f1cea50870115ed60dffe57ff6fc9867179552a4a7f127` |

The exact new normalized row is inside the named `describe` block. In the
following representation, `<TAB>` means one literal U+0009 tab byte:

```text
src/Dashboard.test.tsx<TAB>Dashboard stored data-source presentation > renders stored SEC fundamentals in both locales without raw stable ids
```

The other four frontend files evolve existing nodes in place and add none:

```text
src/SettingsPostPgExitStorage.test.ts
src/TickerDetail.test.tsx
src/i18n/resources.test.ts
src/settings/settingsCopy.test.ts
```

### 2.7 Consumer-census ledgers

Task 0 writes two sorted TSVs under a fresh single-use evidence root:

```text
consumer-census.tsv
behavior-propagation.tsv
```

`consumer-census.tsv` columns are exactly:

```text
path<TAB>line<TAB>symbol_or_pattern<TAB>verdict<TAB>planned_owner
```

Allowed verdicts are exactly:

```text
rewired_current_consumer
retired_current_consumer
low_level_empty_compatibility
historical_reference
test_fixture_reference
unrelated_lexical_hit
```

`behavior-propagation.tsv` separately records every current caller of
`get_fundamentals_analysis()` and its existing/new owning tests. Unknown,
duplicate, empty, or silently dropped rows stop work. The exact row counts and
SHAs are grounded in Task 0 before implementation and then become immutable
plan-amendment fields; they are not invented in advance from prose.

Task 0 grounded the two ledgers as follows:

```text
consumer discovery:
375 rows / 0c105ac7b247e78d1528efb138f8823fb196c9bb1c92092dba8f52ac194b4b29

consumer census:
375 rows / a8d165a2947f429a6918675fbd1357d8ddbbd11595a4e42b75c6027d8cd2b971

behavior propagation:
4 rows / 613024acc6568296cb798a2832fb8ca1e67fba05a9857c4e4bd5629755c556ba
```

The structured discovery producer emitted 383 raw submatches. Eight were exact
duplicate `(path,line,symbol_or_pattern)` occurrences caused by overlapping
search expressions; the producer audits that count and defines the discovery
identity as the 375-row unique tuple stream. Removing verdict/owner from the
census reconstructs that stream byte-for-byte. The final census contains no
duplicate or unknown row.

`behavior-propagation.tsv` columns are exactly:

```text
caller_path<TAB>caller_symbol<TAB>callee<TAB>owning_test_nodes<TAB>planned_disposition
```

The four current callers are the Anthropic bridge, OpenAI bridge,
`/fundamentals` route, and institutional evidence packet. This Task 0 finding
adds the OpenAI bridge to Sections 1.1 and Task 5 and adds its existing
reachability node to Task 3. It changes no test identity or planned collection
hash.

---

## 3. Locked Implementation Shape

### 3.1 Shared completed-session authority

Create `src/market_sessions.py` and move, without semantic expansion:

```python
EXCHANGE_TZ = "America/New_York"
RTH_COMPLETE_AFTER_ET = time(16, 30)

def normalize_now_et(now_et: datetime | None) -> datetime: ...
def is_session_complete(day: date, now_et: datetime) -> bool: ...
def complete_trading_days(start: date, end: date, now_et: datetime) -> list[date]: ...
def latest_completed_market_date(now_et: datetime | None = None) -> date | None: ...
```

`complete_trading_days()` and `latest_completed_market_date()` call the
existing `src.tools.data_coverage_tools._market_day_status`; they do not create
a second holiday table. `latest_completed_market_date()` walks backward from
the normalized ET date until it finds a trading day that is complete. The walk
has a small explicit safety bound (14 calendar days); exhaustion returns
`None`, not a guessed date.

`src/market_data_direct.py` imports aliases so its private call sites and all
existing tests keep the same product semantics:

```python
from src.market_sessions import (
    EXCHANGE_TZ as _EXCHANGE_TZ,
    RTH_COMPLETE_AFTER_ET as _RTH_COMPLETE_AFTER_ET,
    complete_trading_days as _complete_trading_days,
    is_session_complete as _is_session_complete,
    normalize_now_et as _norm_now_et,
)
```

Do not change `include_incomplete_today`, gap detection, top-up target identity,
provider fetch, or write-lock behavior.

### 3.2 Qualified valuation selector

Create `src/valuation_price.py` with one public function:

```python
def get_valuation_price_basis(
    ticker: str,
    *,
    db_path: str | None = None,
    now_et: datetime | None = None,
) -> ValuationPriceBasis:
    ...
```

Required behavior:

1. normalize ticker and derive `required_market_date` first;
2. use `db_path or resolve_market_db_path()`;
3. use `os.path.lexists` so broken symlinks fail closed;
4. never create a path, parent, SQLite file, journal, WAL, table, or alias row;
5. open only `file:<quoted-path>?mode=ro` with `uri=True`, then execute
   `PRAGMA query_only=ON`;
6. validate `prices` and exact required columns
   `ticker, datetime, interval, close` through SQLite metadata;
7. resolve known aliases from `ticker_aliases` when that table exists, and use
   the normalized input unchanged when it does not;
8. query only `interval='15min'` rows in a conservative UTC bracket around the
   required ET date;
9. parse every timestamp as timezone-aware, convert to ET, and compare the ET
   date to `required_market_date`;
10. reject null, boolean, non-numeric, non-finite, zero, and negative closes;
11. choose the latest valid timestamp on that exact ET date; and
12. return exact typed unavailable for every missing/unreadable/schema/query/
    calendar failure without exposing exception text or a filesystem path.

Unavailable construction is centralized and never accepts arbitrary error
text:

```python
def _unavailable(required_market_date: date | None) -> ValuationPriceBasis:
    return ValuationPriceBasis(
        available=False,
        source=None,
        interval=None,
        required_market_date=(
            required_market_date.isoformat() if required_market_date else None
        ),
        market_date=None,
        timestamp=None,
        price=None,
        empty_reason="no_qualified_price",
    )
```

The available result uses `source="local_market_db"`, `interval="15min"`,
identical required/actual market dates, a normalized ISO timestamp, positive
finite float price, and `empty_reason=None`.

### 3.3 Response schema

Add the exact closed model:

```python
class ValuationPriceBasis(BaseModel):
    available: bool = False
    source: Optional[Literal["local_market_db"]] = None
    interval: Optional[Literal["15min"]] = None
    required_market_date: Optional[str] = None
    market_date: Optional[str] = None
    timestamp: Optional[str] = None
    price: Optional[float] = None
    empty_reason: Optional[Literal["no_qualified_price"]] = "no_qualified_price"
```

`DetailedFinancials` gains:

```python
valuation_price_basis: ValuationPriceBasis = Field(
    default_factory=ValuationPriceBasis
)
```

No `error`, raw exception, path, provider guess, entitlement guess, halt guess,
or volume explanation is added.

### 3.4 Static detailed-financials cache

`src/fundamentals/cache.py` owns these stable interfaces:

```python
DETAILED_FINANCIALS_DYNAMIC_FIELDS = (
    "market_cap",
    "enterprise_value",
    "pe_ratio",
    "pb_ratio",
    "ps_ratio",
    "ev_to_ebitda",
    "ev_to_revenue",
    "fcf_yield",
    "peg_ratio",
)

CALCULATOR_DYNAMIC_FIELDS = (
    "market_cap",
    "enterprise_value",
    "price_to_earnings_ratio",
    "price_to_book_ratio",
    "price_to_sales_ratio",
    "enterprise_value_to_ebitda_ratio",
    "enterprise_value_to_revenue_ratio",
    "free_cash_flow_yield",
    "peg_ratio",
)

def detailed_financials_cache_key(ticker: str) -> str:
    return f"detailed_financials:v2:sec_edgar:{ticker.strip().upper()}:annual:y2"

def validate_detailed_financials_static_payload(
    payload: object,
    *,
    ticker: str,
) -> dict[str, object] | None:
    ...
```

The payload is a closed versioned object containing only:

```text
version = 2
ticker
period = annual
years_for_growth = 2
data_source = sec_edgar
report_date
static_metrics
tech_metrics
valuation_inputs
```

`valuation_inputs` contains base-unit SEC facts required by the nine dynamic
fields, including outstanding shares, cash, debt, revenue, EBITDA, free cash
flow, equity/book value, earnings/EPS inputs, and growth inputs when available.
It contains no current price or precomputed dynamic valuation field.

Validation rejects unknown version/source/period/ticker and any recursive key
matching `price`, `timestamp`, `market_date`, `valuation_price_basis`, any
product dynamic field, or any calculator dynamic field. This catches both
`pe_ratio` and its internal source name `price_to_earnings_ratio`; no naming
translation may smuggle a computed value into static cache. It does not adapt
old payloads. The exact old `metrics_{TICKER}_annual_y2` key is never
constructed or read.

### 3.5 Storage-agnostic calculator

In `data_sources/financial_metrics_calculator.py`:

- remove `_get_current_price_ibkr`, `_load_ibkr_data`, `Path`/JSON file state,
  `ibkr_data_path`, and all repository price/fundamentals reads;
- keep SEC statement fetching and all non-price calculation behavior;
- make valuation accept an explicit optional price and explicit base-unit
  statement facts;
- expose the exact cacheable `valuation_inputs` used by request-time
  calculation; and
- make all convenience/CLI paths default to `price=None`, which yields null
  dynamic valuation rather than reading a fallback.

Use one module-level pure interface as the single formula owner:

```python
def calculate_valuation_metrics(
    *,
    price: float | None,
    valuation_inputs: Mapping[str, float | None],
) -> dict[str, float | None]:
    ...
```

`FinancialMetricsCalculator.get_valuation_metrics(...)` delegates to that
function with either explicitly supplied inputs or the instance's SEC-derived
inputs. `analysis_tools.py` calls the pure module-level function directly on a
static-cache hit, so it does not construct `FinancialMetricsCalculator` and
cannot refetch SEC merely to recompute valuation.

The calculator exposes these exact storage-free assembly seams:

```python
def get_valuation_inputs(self) -> dict[str, float | None]: ...
def get_static_metrics_dict(self) -> dict[str, object]: ...
def get_all_metrics(self, *, price: float | None = None) -> FinancialMetrics: ...
def get_metrics_dict(self, *, price: float | None = None) -> dict[str, object]: ...
def get_snapshot(self, *, price: float | None = None) -> dict[str, object]: ...
```

`get_static_metrics_dict()` includes report date and every non-dynamic standard
metric but none of `DETAILED_FINANCIALS_DYNAMIC_FIELDS`. `get_all_metrics()`
and its convenience wrappers combine that static result with the pure dynamic
function. Their default `price=None` is an honest all-nine-null result, not a
file/provider lookup.

The result contains exactly the nine dynamic field names. Shares and all
monetary facts are base units. No magnitude heuristic and no implicit `1e6`
conversion is allowed. A missing input nulls only dependent outputs, except
that missing price nulls all nine by design.

### 3.6 Detailed-financials assembly

`get_detailed_financials()` executes this order on every request:

1. normalize ticker;
2. read only the v2 static cache key;
3. on a valid hit, use static/tech/input facts without constructing the SEC
   calculator;
4. on a miss/invalid hit, construct the calculator, call
   `get_static_metrics_dict()`, `get_tech_metrics()`, and
   `get_valuation_inputs()`, and cache the validated static payload only;
5. call `get_valuation_price_basis()` on every request, including cache hits;
6. derive all nine dynamic fields from the qualified price plus cached/fresh
   `valuation_inputs`, or null all nine when unavailable;
7. call the existing earnings-history and upcoming-earnings functions through
   their existing seams; and
8. build `DetailedFinancials` with static `data_source`, never
   `ibkr+sec_edgar`.

Delete the old `dal.get_fundamentals()` enrichment block. A legacy snapshot
cannot override SEC facts, price basis, units, or source identity.

### 3.7 Annual fundamentals analysis

In `get_fundamentals_analysis()` remove only the legacy-snapshot positive
short circuit. Keep this order:

```text
positive/negative annual SEC cache
  -> SEC EDGAR fixture/provider path
  -> existing Financial Datasets enabled gate and fallback
  -> typed empty FundamentalsResult
```

The function may still call `dal.get_fundamentals()` only where an unrelated
current interface requires an honest empty compatibility shape; it may not use
a snapshot as product facts. The new owning test injects a snapshot sentinel,
an SEC-cache/SEC result, and an FD spy, then proves the snapshot is ignored and
the existing gate order is unchanged. No real provider is called.

### 3.8 Shared positive annual SEC projection

`src/fundamentals/cache.py` adds a connection-level projection that is shared,
not reimplemented by every consumer:

```python
def validate_positive_annual_sec_payload(
    payload: object,
    *,
    ticker: str,
) -> FundamentalsResult | None:
    ...

def stored_annual_sec_fundamentals(
    conn: sqlite3.Connection,
    *,
    now_utc: datetime | None = None,
) -> dict[str, dict[str, object]]:
    ...
```

Admission requires all of:

- cache key matches exact
  `fundamentals_analysis:sec_edgar:{TICKER}:annual:v1` construction;
- `source == "sec_edgar"`;
- `expires_at > now`;
- JSON parses as `FundamentalsResult`;
- payload ticker matches the key ticker;
- payload `data_source == "sec_edgar"`;
- payload is positive, not `_negative`; and
- payload has a non-null snapshot date.

Malformed, negative, expired, quarterly, old detailed-financials, v2
detailed-financials, and Financial Datasets endpoint rows are excluded.
`read_cached_sec_fundamentals()` delegates payload acceptance to the same
validator, so `stored=true` and every projection cannot disagree about whether
one cache row is positive.

The shared projection owns:

- `market_data_admin.local_market_stats()` fundamentals row/ticker/latest date;
- `market_data_admin.local_ticker_coverage()` fundamentals summary;
- `SqliteBackend.get_available_tickers("fundamentals")`;
- `LocalMarketDatabaseBackend.get_available_tickers("fundamentals")`, which
  returns the local projection even when it is empty and never falls to PG;
- `/status` through the DAL ticker count; and
- `get_ticker_data_coverage()` fundamentals summary.

`read_sync_meta()` and coverage `_sync_meta()` retain the response key but
project `fundamentals: null`; price/news values remain byte-equivalent in shape
and value.

### 3.9 Retired file authorities

`FileBackend.query_prices()` constructs the standard empty price DataFrame
directly. `FileBackend.get_available_tickers("prices")` and
`get_available_tickers("fundamentals")` return `[]` directly. They must not
call `Path.exists`, `glob`, `rglob`, `read_csv`, `read_parquet`, or helper
loaders. After the Task 0 census proves no current caller, remove now-unused
price-file loaders rather than retaining an ownerless dormant reader.

`daily_update.get_ibkr_prices_status()` calls
`market_data_admin.local_market_stats()` and maps its `prices` object into the
existing closed shape:

```text
exists
total_bars
latest_date
tickers
```

It does not walk a directory or open a CSV.

### 3.10 Frontend and current-copy contract

Add `"local_cache"` to `SourcePath`. Map it explicitly in Ticker Detail to
localized "stored SEC fundamentals" copy. Unknown future source IDs retain the
existing safe fallback behavior; the known stable ID must never be rendered
raw.

Settings must distinguish:

- stored SEC fundamentals coverage, derived from positive annual cache rows;
- generic financial-cache storage; and
- absent retired fundamentals sync telemetry.

`DataStorageSection.syncLine()` and developer sync diagnostics use only current
price/news telemetry. They do not format, interpolate, or diagnose
`sync.fundamentals`; the typed API key remains present as `null` solely for
response compatibility.

Dashboard maps the exact backend keys (`news_tickers`, `price_tickers`,
`fundamentals_tickers`) to localized labels and never derives user copy by
replacing underscores. The fundamentals label says stored SEC fundamentals.

Current code, training help, data/formula guides, canonical workbench spec,
tool registry, Anthropic schema, and response comments stop claiming the old
directory, collection summary, or "IBKR real-time" valuation source. Historical
records remain untouched and are excluded by explicit path, not by excluding
all docs.

---

## 4. Tasks

### Task 0: Re-Ground Every Authority Before Product Edits

**Files:**

- Modify: `docs/superpowers/plans/2026-08-03-eir-006-valuation-price-truth.md`
- Modify: `docs/superpowers/evidence/2026-08-03-eir-006-valuation-price-truth.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Read only: all product/test/data paths named by the design

- [x] **Step 1: Verify exact branch, authority, and clean boundary**

```bash
cd /tmp/arkscope-eir-006
git status --short --branch
git rev-parse HEAD
git merge-base --is-ancestor fd6d1b86383df2a98f97b235d9796d4bcaaa7a58 HEAD
sha256sum \
  docs/superpowers/specs/2026-08-01-eir-006-valuation-price-truth-design.md \
  /tmp/arkscope_asyncio_wakeup_probe.py \
  /tmp/eir002-green-baseline/arkscope_eir002_reporter.py \
  /tmp/eir002-green-baseline/run_native.sh
```

Expected: `HEAD` is the independently reviewed plan tip after plan review; the
design matches the plan-gate status-evolution SHA in Section 0.1 and the three
native assets match Section 0.3. Ordinary worktree status contains no
pre-existing implementation edit.

Create a fresh single-use root only after proving it does not exist:

```bash
test ! -e /tmp/eir006-valuation-price-truth
mkdir -p /tmp/eir006-valuation-price-truth/{baseline,census,protected,artifacts}
```

- [x] **Step 2: Reproduce canonical backend collection**

```bash
cd /tmp/arkscope-eir-006
PRICE_TRUTH_TIER_REPORT=/tmp/eir006-valuation-price-truth/baseline/backend-collect.json \
PYTHONPATH=/tmp/eir002-green-baseline \
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest \
  --collect-only -q -p arkscope_eir002_reporter
jq -r '.collected_node_ids[]' \
  /tmp/eir006-valuation-price-truth/baseline/backend-collect.json \
  | LC_ALL=C sort \
  > /tmp/eir006-valuation-price-truth/baseline/backend.nodes
wc -l /tmp/eir006-valuation-price-truth/baseline/backend.nodes
sha256sum /tmp/eir006-valuation-price-truth/baseline/backend.nodes
```

Expected: exact `4553 / 69152591306a8dee...`. Reporter exit is zero,
`seen_node_ids=[]`, and `nonpassing_node_ids=[]` because this is collect-only.

- [x] **Step 3: Reproduce backend focused base and preconstruct all targets**

Collect the 14 existing affected files from Section 2.4 and record exact:

```text
307 / 46f8c9d0cd9e3b525d051e2231d4d48ed2975192886cdeb293ec71662341ae51
```

From the base stream, mechanically:

1. delete only Section 2.2;
2. insert Section 2.3 nodes at their matching stage;
3. sort with `LC_ALL=C`; and
4. compare every count/SHA to Section 2.1.

Write these immutable pre-edit streams:

```text
/tmp/eir006-valuation-price-truth/baseline/stage-task1.nodes
/tmp/eir006-valuation-price-truth/baseline/stage-task2.nodes
/tmp/eir006-valuation-price-truth/baseline/stage-task3.nodes
/tmp/eir006-valuation-price-truth/baseline/stage-task4.nodes
/tmp/eir006-valuation-price-truth/baseline/stage-final.nodes
/tmp/eir006-valuation-price-truth/baseline/focused-final.nodes
```

Stop if a claimed ID already exists, the removed ID is absent/multiple, or any
precomputed SHA differs.

- [x] **Step 4: Reproduce frontend base and preconstruct target**

Use the exact installed toolchain from the main repository only after checking
both lockfile SHAs recorded by Tranche A. Materialize the exact Section 2.6
normalizer under the fresh evidence root, then require its exact
`62 / 2233 / 955dca592d243505...` identity before use. Run
`vitest list --json` into an unmodified JSON artifact and invoke that pinned
normalizer with the exact frontend root. The normalizer parses JSON with
`json.loads()` and writes each decoded row as:

```text
relative_file<TAB>full_test_name
```

Do not parse the JSON as text, copy its quoted representation, or pass decoded
names through `jq @tsv`; all three violate the runtime-name contract. Record
exact:

```text
base full:    96 files / 1076 / ef7f106054745c13...
base focused:  4 files /   45 / 09a2b4ef080a5bad...
target full:  97 files / 1077 / 3f5e9f5bbe88d5ac...
target focus:  5 files /   46 / 5d64841ccdd943eb...
```

The target construction inserts only the exact Dashboard node in Section 2.6.
Do not parse human console prose and do not use whitespace-delimited node IDs.

- [x] **Step 5: Materialize the closed pre-edit consumer census**

Run broad searches over current source, tests, training, current docs, config,
and app code for at least:

```bash
rg -n \
  -e 'data/prices' \
  -e 'prices/15min' \
  -e 'prices/hourly' \
  -e 'collection_summary\.json' \
  -e '_get_current_price_ibkr' \
  -e 'metrics_.*_annual_y' \
  -e 'dal\.get_fundamentals' \
  -e 'query_fundamentals' \
  -e 'ibkr_fundamentals' \
  -e 'FROM fundamentals' \
  -e 'local_ticker_coverage' \
  -e 'local_market_stats' \
  -e 'get_available_tickers' \
  -e 'get_ticker_data_coverage' \
  -e 'market_sync_meta' \
  src data_sources apps training docs tests config
```

Do not send the raw output through an ad hoc whitespace parser. Convert each
match to the exact TSV schema in Section 2.7 using path/line fields from a
structured or NUL-safe producer. Add a disposition for every row and assert:

- allowed verdict only;
- nonempty owner;
- unique `(path,line,symbol_or_pattern)`;
- sorted deterministic stream;
- no unknown verdict; and
- removing the verdict/owner columns reconstructs the complete discovery
  stream without loss.

Separately enumerate every `get_fundamentals_analysis()` caller and its owning
tests in `behavior-propagation.tsv`. Task 0 found exactly the four callers and
the immutable stream identity recorded in Section 2.7. The route, evidence,
Anthropic bridge, and OpenAI bridge must all remain represented. This grounded
docs-only amendment requires focused independent review before Task 1.

- [x] **Step 6: Pin protected paths and current production identities read-only**

Record path/blob SHAs for all out-of-scope owners:

```text
price collector/scheduler/provider modules
current quote tool
Financial Datasets client and enablement policy
Tranche B scoring owners
production data path inventory
```

Record metadata-only production identities required to prove no implementation
write:

```text
data/market_data.db path/inode/size/mtime_ns/SHA-256
data/prices exact path/count/metadata stream SHA
current old-cache/fundamentals/sync row counts (query_only)
scheduler state/cadence read-only snapshot
```

Do not read secrets. Do not query a provider. These dated observations are a
before/after safety boundary, not acceptance constants for deletion.

- [x] **Step 7: Run native green base under the canonical boundary**

Create a fresh detached exact-tip worktree with no `config/.env`, empty
`data/`, absent `src/data`, and the pinned `node_modules` link. Run the wakeup
probe in the same native context, then:

The pinned wrapper takes exactly one single-use stage name and runs against its
current working directory; it does not accept a worktree path. Therefore run:

```bash
cd /path/to/fresh-worktree
/tmp/eir002-green-baseline/run_native.sh \
  eir006-task0-native-base-e261abc2
```

The wrapper itself executes the pinned wakeup probe in that same native
context. Passing the worktree as an argument is invalid and must not be used by
later base/tip gates.

Expected:

```text
4553 collected = 4553 seen
4481 passed / 72 skipped / 0 failed / 0 errors
empty non-passing SHA e3b0c442...
```

Inventory and exact-path quarantine every new artifact. A modified pre-existing
file or reporter mismatch stops Task 0.

- [x] **Step 8: Commit the Task 0 evidence checkpoint and stop for review**

Update evidence with exact census counts/SHAs, base collections, native result,
protected identities, and artifact transaction. Update priority map newest
first. Commit docs only:

```bash
git add \
  docs/superpowers/plans/2026-08-03-eir-006-valuation-price-truth.md \
  docs/superpowers/evidence/2026-08-03-eir-006-valuation-price-truth.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: ground EIR-006 implementation ledger"
```

Independent review must reproduce the two collections, all preconstructed
targets, census closure, native base, and no-write boundary before Task 1.

---

### Task 1: Share The Session Authority And Add The Qualified Selector

**Files:**

- Create: `src/market_sessions.py`
- Create: `src/valuation_price.py`
- Modify: `src/market_data_direct.py`
- Modify: `src/tools/schemas.py`
- Create: `tests/test_valuation_price.py`
- Modify: `tests/test_detailed_financials.py`
- Test: `tests/test_market_data_direct.py`

- [ ] **Step 1: Write the ten selector tests before product code**

Use fixture-only SQLite builders. The `prices` fixture stores timestamps in the
real `YYYY-MM-DDTHH:MM:SS+0000` shape and creates `ticker_aliases` only in the
alias test. Patch only the market calendar status where a synthetic holiday is
needed; do not patch `latest_completed_market_date()` in selector tests.

Each node owns one independent contract:

1. 16:29:59 ET chooses the prior completed session even when today has a row;
2. 16:30:00 ET accepts today;
3. weekend plus synthetic exchange holiday choose the prior trading session;
4. exactly one row qualifies;
5. prior-day row cannot fill a missing required day;
6. nonexistent nested DB path remains nonexistent and returns exact typed
   unavailable;
7. directory, broken symlink, junk DB, missing table, missing columns, and a
   forced query exception all sanitize to the same public reason;
8. a `00:15Z` row maps to the preceding ET market date;
9. null/NaN/infinity/zero/negative closes are all rejected; and
10. `LC` resolves to canonical `HAPN` rows.

The multi-shape assertions within nodes 7 and 9 use local helper loops inside
the owning node. Do not parametrize them or create extra collected IDs.

- [ ] **Step 2: Run structural/product RED and verify the failure reason**

```bash
pytest tests/test_valuation_price.py -q
```

Expected: all ten nodes collect and fail because `src.market_sessions`,
`src.valuation_price`, and `ValuationPriceBasis` do not yet satisfy the
contract. Import/fixture SQL/path errors are wrong RED and must be fixed in
tests before product edits.

Collect the full backend and compare to exact Task 1 identity:

```text
4563 / 5fdc93f3dc78548048d7269d8088715028a57b1e2c54fe1ac422154d187f3986
```

- [ ] **Step 3: Extract the calendar without semantic drift**

Implement Section 3.1. Keep private aliases in `market_data_direct.py`. Run:

```bash
pytest tests/test_market_data_direct.py -q
```

Expected: all 70 existing nodes pass; collection is byte-identical to base for
that file. Any renamed helper/node or changed backfill behavior stops work.

- [ ] **Step 4: Implement schema and selector**

Implement Sections 3.2-3.3. Use read-only URI mode and metadata validation.
Do not call `_ensure_ticker_aliases`, a writable backend, or a DAL. The selector
must be independently usable for the post-merge read-only smoke.

- [ ] **Step 5: Run selector GREEN and no-create witnesses**

```bash
pytest tests/test_valuation_price.py tests/test_market_data_direct.py \
  tests/test_detailed_financials.py::TestDetailedFinancialsSchema -q
```

Expected: green. Record pre/post directory inventory for the missing path,
broken symlink, and junk DB fixtures; no `-journal`, `-wal`, `-shm`, parent,
or SQLite file may appear.

- [ ] **Step 6: Commit the bounded product slice**

```bash
git add \
  src/market_sessions.py \
  src/market_data_direct.py \
  src/valuation_price.py \
  src/tools/schemas.py \
  tests/test_valuation_price.py \
  tests/test_detailed_financials.py
git commit -m "feat: qualify valuation prices from local sessions"
```

Record RED/GREEN, stage collection, no-create witnesses, and product blob SHAs.

---

### Task 2: Split Static Financial Facts From Dynamic Valuation

**Files:**

- Modify: `src/fundamentals/cache.py`
- Modify: `data_sources/financial_metrics_calculator.py`
- Modify: `src/tools/analysis_tools.py`
- Modify: `tests/test_detailed_financials.py`
- Create: `tests/test_financial_metrics_calculator.py`
- Test: `tests/test_fundamentals_cache.py`
- Test: `tests/test_agents.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: Replace the obsolete test identity and add nine new contracts**

Delete only:

```text
TestGetDetailedFinancials::test_ibkr_enrichment_overrides
```

Add the six reviewed `TestGetDetailedFinancials` nodes and three calculator
nodes from Section 2.3. Evolve the three schema nodes and
`test_returns_detailed_financials_type` in place to assert the complete nested
price-basis shape.

Use a backend double that records every cache key and write payload, a selector
double that can return two different prices on two calls, a calculator/SEC
double that records construction, and separate earnings doubles. Do not derive
expected fields by calling the implementation under test.

- [ ] **Step 2: Run RED and inspect exact causes**

```bash
pytest \
  tests/test_detailed_financials.py \
  tests/test_financial_metrics_calculator.py \
  -q
```

Expected RED causes:

- old key is still read;
- static payload still contains precomputed dynamic metrics;
- cache hits freeze valuation instead of reselecting price;
- unavailable price does not null all nine fields;
- old snapshot still overrides values/source;
- the calculator still opens repository files; and
- million scaling/magnitude heuristics violate base-unit assertions.

Any real SEC/earnings/network call, fixture import error, or unexpected cache
write is wrong RED.

Collect and compare exact Task 2 identity:

```text
4571 / b247d173d3520668a5d475b0ed02f948d117c1097ed5ad86063a2dbf76d07b68
```

- [ ] **Step 3: Implement the v2 static cache contract**

Implement Section 3.4 in `src/fundamentals/cache.py`. Add recursive forbidden
key validation and explicit version/ticker/source/period checks. Keep existing
annual SEC v1 cache helpers backward-compatible for their own contract; do not
rename or repurpose that key family.

- [ ] **Step 4: Make the calculator storage agnostic**

Implement Section 3.5. Delete repository-file readers and instance state only
after the Task 0 consumer ledger proves no separate current owner. Keep all
static profitability/growth/tech calculations intact.

The explicit-price unit test uses facts such as:

```text
price = 10.0
outstanding_shares = 2_000_000
cash = 1_000_000
debt = 3_000_000
revenue = 5_000_000
```

and independently expects `market_cap == 20_000_000`. A `1e6` multiplier or
divider must be visibly wrong.

- [ ] **Step 5: Reassemble detailed financials from static plus dynamic facts**

Implement Section 3.6. Build one closed mapping from calculator field names to
the nine `DetailedFinancials` field names; do not duplicate formula logic in
`analysis_tools.py`.

On unavailable price, set the nine dynamic fields from the constant tuple to
`None`. Do not clear static margins, growth, cash, debt, EPS, tech metrics,
report date, or earnings fields.

- [ ] **Step 6: Run GREEN plus affected existing contracts**

```bash
pytest \
  tests/test_detailed_financials.py \
  tests/test_financial_metrics_calculator.py \
  tests/test_fundamentals_cache.py \
  tests/test_agents.py \
  tests/test_tools.py \
  -q
```

Expected: green with existing node IDs preserved except the exact one-for-one
replacement. Provider doubles show zero live calls. Inspect one cache write and
prove recursively that no forbidden field is present.

- [ ] **Step 7: Commit the static/dynamic split**

```bash
git add \
  src/fundamentals/cache.py \
  data_sources/financial_metrics_calculator.py \
  src/tools/analysis_tools.py \
  tests/test_detailed_financials.py \
  tests/test_financial_metrics_calculator.py
git commit -m "fix: separate valuation prices from static financial cache"
```

Record stage collection, exact removed/replacement IDs, cache payload witness,
and pre/post source SHAs.

---

### Task 3: Remove The Legacy Fundamentals Short Circuit And Report Peer Absence

**Files:**

- Modify: `src/tools/analysis_tools.py`
- Modify: `tests/test_fundamentals_sec_cache.py`
- Modify: `tests/test_peer_comparison.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_tools.py`
- Modify: `tests/test_evidence_packet.py`

- [ ] **Step 1: Add the two new nodes and evolve downstream fixtures**

Add:

```text
tests/test_fundamentals_sec_cache.py::test_annual_analysis_ignores_legacy_snapshot_and_preserves_sec_fd_order
tests/test_peer_comparison.py::TestDataQuality::test_unavailable_valuation_prices_are_counted_named_and_excluded
```

The annual-analysis node runs two subcases within one node:

1. positive SEC cache hit with a contradictory legacy snapshot: SEC cache wins,
   no SEC/FD request occurs;
2. cache miss with SEC fixture result and enabled/disabled FD spies: SEC-first
   order and existing FD gate remain exactly as before.

The peer node returns three peers: two qualified, one
`no_qualified_price`. Assert exact unavailable count/list/reason map and prove
sector statistics/rankings count only the two numeric values.

Evolve existing API/tool/evidence fixtures to current positive SEC-cache shapes
without renaming nodes or making providers reachable.

- [ ] **Step 2: Run RED**

```bash
pytest \
  tests/test_fundamentals_sec_cache.py::test_annual_analysis_ignores_legacy_snapshot_and_preserves_sec_fd_order \
  tests/test_peer_comparison.py::TestDataQuality::test_unavailable_valuation_prices_are_counted_named_and_excluded \
  -q
```

Expected: first node fails because the snapshot still short-circuits; second
fails because data-quality output lacks the three reviewed fields. Provider
access or an error string leak is wrong RED.

Collect exact Task 3 identity:

```text
4573 / e0ee195eb90bc9172dae36680b15b3285b3d82013c7c762e1989c955be6ea3b1
```

- [ ] **Step 3: Remove only the legacy positive short circuit**

Delete the old snapshot-return branch in `get_fundamentals_analysis()`. Do not
change the annual SEC cache key, negative-cache TTL, SEC result builder, FD
enablement function, FD retry/spend behavior, or typed empty result.

- [ ] **Step 4: Add closed peer data-quality fields**

Derive unavailable peers from each `DetailedFinancials.valuation_price_basis`.
Sort ticker lists deterministically and count reasons from the stable enum. Do
not include exception strings. Existing `errors` keeps its separate meaning
for thrown tool failures.

- [ ] **Step 5: Run the full behavior-propagation ledger**

At minimum:

```bash
pytest \
  tests/test_fundamentals_sec_cache.py \
  tests/test_peer_comparison.py \
  tests/test_api.py::TestFundamentalsEndpoints::test_fundamentals \
  tests/test_api.py::test_fundamentals_stored_mode_reads_local_cache_without_provider_fetch \
  tests/test_api.py::test_fundamentals_stored_source_path_mapping \
  tests/test_api.py::test_fundamentals_stored_expired_cache_is_honest_empty \
  tests/test_tools.py::TestAnalysisTools::test_get_fundamentals_analysis \
  tests/test_agents.py::TestAnthropicToolSchemas::test_tool_names \
  tests/test_agents.py::TestOpenAIToolCreation::test_tools_have_names \
  tests/test_evidence_packet.py::test_packet_has_expected_sources_and_tags \
  tests/test_evidence_packet.py::test_one_failing_source_degrades_to_coverage \
  -q
```

Expected: green, zero provider requests, existing route/evidence behavior
preserved. Every row in `behavior-propagation.tsv` has an executed owner.

- [ ] **Step 6: Commit the bounded tool behavior change**

```bash
git add \
  src/tools/analysis_tools.py \
  tests/test_fundamentals_sec_cache.py \
  tests/test_peer_comparison.py \
  tests/test_api.py \
  tests/test_tools.py \
  tests/test_evidence_packet.py
git commit -m "fix: keep legacy fundamentals out of live analysis"
```

Record SEC/FD call-order spies and stage identity.

---

### Task 4: Make Stored SEC Cache The Only Fundamentals Projection

**Files:**

- Modify: `src/fundamentals/cache.py`
- Modify: `src/market_data_admin.py`
- Modify: `src/tools/data_coverage_tools.py`
- Modify: `src/tools/backends/sqlite_backend.py`
- Modify: `src/tools/backends/local_market_backend.py`
- Modify: `src/tools/backends/file_backend.py`
- Modify: `src/daily_update.py`
- Create: `tests/test_stored_sec_projection.py`
- Modify: `tests/test_market_data_admin.py`
- Modify: `tests/test_data_coverage_tools.py`
- Modify: `tests/test_sqlite_backend.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_daily_update_wrapper.py`
- Modify: `tests/test_db_backend_retired_prices.py`

- [ ] **Step 1: Add the six reviewed nodes before product edits**

Add the four `test_stored_sec_projection.py` nodes plus the daily-update and
FileBackend nodes from Section 2.3.

Build one fixture `market_data.db` with:

- a valid `prices` row and `news` row;
- a legacy `fundamentals` row;
- exact price/news/fundamentals `market_sync_meta` rows;
- old detailed-financials and v2 detailed-financials cache rows;
- negative, expired, malformed, quarterly, and FD cache rows; and
- one positive unexpired annual SEC v1 cache row with a snapshot date that
  differs from `fetched_at`.

The shared-authority node calls every backend/status/tool projection against
that same fixture and asserts identical one-ticker ownership and snapshot date.
It also calls the stored-only route through a dependency override so API and
projection acceptance cannot drift.

- [ ] **Step 2: Run RED**

```bash
pytest \
  tests/test_stored_sec_projection.py \
  tests/test_daily_update_wrapper.py::test_price_status_uses_sqlite_stats_without_scanning_repository_files \
  tests/test_db_backend_retired_prices.py::test_file_backend_prices_and_fundamentals_are_empty_without_path_probes \
  -q
```

Expected RED:

- legacy fundamentals row still establishes coverage/ticker count;
- consumers do not share the positive cache contract;
- fundamentals sync still appears;
- `daily_update` still scans CSVs; and
- FileBackend still probes repository paths.

Wrong RED includes fixture schema errors, FastAPI lifespan entry, provider
access, or a missing existing helper unrelated to the contract.

Collect exact Task 4 identity:

```text
4579 / 6672d3df26b7c420d3253e4826b7104bfd0e5640ae16a1616ea75dd605b38639
```

- [ ] **Step 3: Implement and reuse the positive SEC projection**

Implement Section 3.8 once in `src/fundamentals/cache.py`. Consumers may format
counts/summaries, but may not write their own key regex, expiry, positivity, or
payload acceptance rule.

`local_market_stats()` returns the existing `fundamentals` object shape using
projection count/distinct ticker/max payload snapshot date. Generic
`financial_cache` stats remain independently reported and do not imply stored
fundamentals.

`local_ticker_coverage()` and `get_ticker_data_coverage()` report positive
stored SEC facts only. A legacy table row does not count even if it has a newer
date.

- [ ] **Step 4: Remove retired sync projection without affecting price/news**

Filter domain `fundamentals` inside the shared status readers before response
construction. Preserve exact keys:

```json
{"prices": {}, "news": {}, "fundamentals": null}
```

where price/news values equal the fixture inputs. Do not delete the production
row in this task.

- [ ] **Step 5: Make FileBackend and daily-update honest**

Implement Section 3.9. In the FileBackend test, monkeypatch `Path.exists`,
`Path.glob`, `Path.rglob`, `pandas.read_csv`, and `pandas.read_parquet` to raise
if reached; then assert exact empty DataFrame columns and `[]` ticker results.

In the daily-update test, monkeypatch every repository scanning primitive to
raise and inject exact SQLite stats. Assert the unchanged four-key return
shape, total row count, latest date, and ticker count.

- [ ] **Step 6: Run all backend projection owners**

```bash
pytest \
  tests/test_stored_sec_projection.py \
  tests/test_market_data_admin.py \
  tests/test_data_coverage_tools.py \
  tests/test_sqlite_backend.py \
  tests/test_api.py::TestHealth::test_status \
  tests/test_api.py::test_fundamentals_stored_mode_reads_local_cache_without_provider_fetch \
  tests/test_api.py::test_fundamentals_stored_source_path_mapping \
  tests/test_api.py::test_fundamentals_stored_expired_cache_is_honest_empty \
  tests/test_daily_update_wrapper.py \
  tests/test_db_backend_retired_prices.py \
  -q
```

Expected: green. Assert no PG method and no provider method was touched.

- [ ] **Step 7: Commit the authority projection**

```bash
git add \
  src/fundamentals/cache.py \
  src/market_data_admin.py \
  src/tools/data_coverage_tools.py \
  src/tools/backends/sqlite_backend.py \
  src/tools/backends/local_market_backend.py \
  src/tools/backends/file_backend.py \
  src/daily_update.py \
  tests/test_stored_sec_projection.py \
  tests/test_market_data_admin.py \
  tests/test_data_coverage_tools.py \
  tests/test_sqlite_backend.py \
  tests/test_api.py \
  tests/test_daily_update_wrapper.py \
  tests/test_db_backend_retired_prices.py
git commit -m "fix: project stored fundamentals from SEC cache"
```

Record exact Task 4 collection and the one-fixture multi-consumer equality
witness.

---

### Task 5: Reconcile Frontend, Current Copy, And The Static Census

**Files:**

- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/TickerDetail.tsx`
- Modify: `apps/arkscope-web/src/Dashboard.tsx`
- Modify: `apps/arkscope-web/src/settings/DataStorageSection.tsx`
- Modify: `apps/arkscope-web/src/settings/settingsCopy.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/system.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/system.ts`
- Create: `apps/arkscope-web/src/Dashboard.test.tsx`
- Modify: `apps/arkscope-web/src/TickerDetail.test.tsx`
- Modify: `apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.test.ts`
- Modify: `apps/arkscope-web/src/settings/settingsCopy.test.ts`
- Modify: `src/tools/registry.py`
- Modify: `src/agents/anthropic_agent/tools.py`
- Modify: `src/agents/openai_agent/tools.py`
- Modify: `src/tools/analysis_tools.py`
- Modify: `src/tools/schemas.py`
- Modify: `src/tools/backends/file_backend.py`
- Modify: current documentation owners from Section 1.3
- Create: `tests/test_eir006_retired_data_boundaries.py`

- [ ] **Step 1: Add the backend static-boundary tests first**

Add the two exact nodes from Section 2.3. Embed the reviewed Task 0 census as
closed constants grouped by verdict; do not execute the Task 0 implementation
or derive the allowlist from current hits.

`test_current_runtime_consumer_census_is_closed_and_exact` reruns the same
discovery roots/pattern families, normalizes rows, and compares them to the
reviewed post-cutover disposition. It must fail on:

- a new current `data/prices` reader;
- old detailed-financials key construction/read;
- a product use of legacy `fundamentals` rows or sync telemetry;
- a current writer that can repopulate a retired family; or
- any unknown hit.

The test explicitly excludes exact historical paths and the EIR-006
design/plan/evidence files. It does not exclude all docs, all tests, all
comments, all training, or all configuration.

`test_current_docs_training_and_tool_copy_name_only_current_authorities` reads
the named current files and asserts current authority language, including no
"IBKR real-time" valuation claim. It does not scan historical evidence.

- [ ] **Step 2: Add/evolve frontend tests before frontend code**

Create `Dashboard.test.tsx` with one `describe` and one node exactly matching
Section 2.6. Render `StatusTiles` through the public Dashboard surface in each
locale, supply all three known keys plus a future unknown key, and assert:

- stored SEC fundamentals localized copy appears;
- known raw IDs do not appear;
- values remain unchanged; and
- unknown-key behavior stays safe and explicit.

Evolve existing tests in place:

- Ticker Detail known `local_cache` maps in both locales and does not render
  raw `local_cache`;
- Settings says stored SEC fundamentals, keeps generic cache separate, and
  renders no retired fundamentals sync update;
- resources preserve exact locale key parity and nonempty leaves; and
- Settings static copy/search reflects the new wording.

- [ ] **Step 3: Run RED and lock final collection identities**

```bash
pytest tests/test_eir006_retired_data_boundaries.py -q
npm test --workspace apps/arkscope-web -- --run \
  src/Dashboard.test.tsx \
  src/TickerDetail.test.tsx \
  src/SettingsPostPgExitStorage.test.ts \
  src/i18n/resources.test.ts \
  src/settings/settingsCopy.test.ts
```

Expected: backend nodes fail on current stale references; frontend owning nodes
fail because `local_cache`/stored-SEC labels and Dashboard mapping do not exist.
No unrelated jsdom/runtime/import failure is acceptable.

Collect and compare final identities before product edits:

```text
backend: 4581 / 6e4994bb664501cff75cb06dbad18db82ba68cbbe4b2b26c4d480250d7c4699f
frontend full: 97 files / 1077 / 3f5e9f5bbe88d5ac48015a8c9e9d669dcd649a53a2ac868fc8a98d21f8d7e4eb
frontend focused: 5 files / 46 / 5d64841ccdd943eb81f1cea50870115ed60dffe57ff6fc9867179552a4a7f127
```

- [ ] **Step 4: Implement exact frontend source/copy mapping**

Add `local_cache` to the union, map all known status keys through a typed
exhaustive map, add both locale resources, and update Settings/Ticker Detail.
Do not place raw stable IDs into user-facing copy. Do not add a generic
`replace(/_/g, " ")` fallback for known keys.

Keep UI layout, navigation, API request timing, and unrelated source-path
behavior unchanged. This slice changes truth/copy, not the information
architecture.

- [ ] **Step 5: Reconcile current model-visible and documentation claims**

Update only current authorities. Required outcomes:

- detailed-financials tool descriptions say static SEC facts plus qualified
  local completed-session price, or typed unavailable;
- no response comment says `IBKR real-time`;
- training help no longer offers retired CSV paths as inputs;
- current data/formula/subscription guides point to `market_data.db` and state
  the completed-session qualification;
- the canonical workbench spec no longer presents CSV/parquet files as current
  price authority; and
- FileBackend/module comments describe its retired empty compatibility shape.

Do not rewrite dated historical evidence or old design supersession records.

- [ ] **Step 6: Run backend/frontend GREEN and copy scanners**

```bash
pytest tests/test_eir006_retired_data_boundaries.py \
  tests/test_agents.py tests/test_tools.py -q
npm test --workspace apps/arkscope-web -- --run \
  src/Dashboard.test.tsx \
  src/TickerDetail.test.tsx \
  src/SettingsPostPgExitStorage.test.ts \
  src/i18n/resources.test.ts \
  src/settings/settingsCopy.test.ts
npm run typecheck --workspace apps/arkscope-web
npm run check:i18n-literals --workspace apps/arkscope-web
```

Expected: backend 2 new nodes green; frontend focused 46/46; typecheck/scanner
green. Rerun Task 0 census and prove every pre-edit
`rewired_current_consumer` is now rewired or retired and no unknown appeared.

- [ ] **Step 7: Commit frontend and current-authority reconciliation**

Stage only the named source/test/current-doc files and inspect `git diff
--cached --name-status` before committing:

```bash
git commit -m "fix: expose truthful stored financial authorities"
```

Record final backend/frontend collection streams and post-cutover census SHA.

---

### Task 6: Mutation Proof, Canonical Admission, And Implementation Review Packet

**Files:**

- Modify: `docs/superpowers/evidence/2026-08-03-eir-006-valuation-price-truth.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Read/test: all product and test owners from Tasks 1-5

- [ ] **Step 1: Reproduce exact final collection identities**

Use the deterministic backend reporter and frontend JSON normalizer. Compare
actual streams byte-for-byte to the preconstructed Task 0 targets:

```text
backend full:    4581 / 6e4994bb664501cff75cb06dbad18db82ba68cbbe4b2b26c4d480250d7c4699f
backend focused:  335 / 58230b548925b29035cff401520e0948b01dcaed8da2deed41149bea6b4a5ae1
frontend full:   1077 / 3f5e9f5bbe88d5ac48015a8c9e9d669dcd649a53a2ac868fc8a98d21f8d7e4eb
frontend focused:  46 / 5d64841ccdd943eb81f1cea50870115ed60dffe57ff6fc9867179552a4a7f127
```

Also prove:

- every Section 2.3 new ID appears exactly once;
- Section 2.2 is absent;
- every Section 2.5 existing ID remains exactly once; and
- all 70 market-data-direct nodes remain exactly present.

- [ ] **Step 2: Run the ten exact mutation cycles**

For each cycle: record pre-mutation product SHA, apply the smallest exact diff,
save `mutation.diff`, run only the owning node/set, require RED for the intended
assertion, restore contextually, and prove the original SHA and owning GREEN
return before continuing.

| Mutation | Exact semantic change | Owning RED node/set |
|---|---|---|
| M1 | Allow most-recent older day when required day has no row | `test_missing_required_date_does_not_fallback_to_older_bar` |
| M2 | Require `stored_row_count == 26` instead of day presence | `test_one_row_qualifies_without_slot_completeness` |
| M3 | Compare `datetime[:10]`/UTC date instead of ET date | `test_et_market_date_not_raw_utc_date_owns_selection` |
| M4 | Read `metrics_{TICKER}_annual_y2` on v2 miss | `test_old_metrics_cache_key_is_ignored` |
| M5 | Insert price or one dynamic field into static cache payload | `test_v2_static_cache_excludes_price_and_dynamic_fields` |
| M6 | Multiply or divide outstanding shares by `1e6` | `test_explicit_price_uses_base_unit_shares_without_million_scaling` |
| M7 | Restore legacy `dal.get_fundamentals().snapshot` override | `test_legacy_ibkr_snapshot_cannot_override_sec_or_price_basis` |
| M8 | Restore FileBackend CSV path probing/read | `test_file_backend_prices_and_fundamentals_are_empty_without_path_probes` |
| M9 | Restore `daily_update` directory scan | `test_price_status_uses_sqlite_stats_without_scanning_repository_files` |
| M10 | Count the legacy `fundamentals` table as stored | `test_legacy_fundamentals_row_does_not_project_as_stored` plus `test_positive_annual_sec_cache_is_the_shared_projection_authority` |

M2 must alter the target/day-presence admission predicate, not append a dead
condition after an empty target set. M5 must mutate the production cache writer,
not only a test fixture. M10 must mutate the shared projection or one consuming
authority in a way the multi-consumer node observes.

- [ ] **Step 3: Run backend focused and protected gates**

Run the exact 18-file focused set from Section 2.4. Expected `335 passed` except
for the repo's unchanged manually skipped/live nodes if any are present in
those files; report exact pass/skip totals rather than assuming.

Separately run protected owners for:

```text
price collection truth and all market_data_direct nodes
current quote behavior
Financial Datasets enablement/cache/client semantics
stored=true provider-free behavior
earnings history/upcoming earnings doubles
coverage v2 session behavior
job/scheduler price outcome behavior
Tranche B scoring byte boundaries
```

Do not run a live/provider-marked test. Record exact node IDs and results rather
than only file totals.

- [ ] **Step 4: Run frontend full, typecheck, build, and scanner**

```bash
npm test --workspace apps/arkscope-web -- --run
npm run typecheck --workspace apps/arkscope-web
npm run build --workspace apps/arkscope-web
npm run check:i18n-literals --workspace apps/arkscope-web
```

Expected: `97 files / 1077 passed`, zero TypeScript errors, successful Vite
build, and scanner debt not increased. Record build warnings honestly; do not
convert an existing non-blocking bundle-size warning into a new failure claim.

- [ ] **Step 5: Run static no-provider/no-PG/protected-byte checks**

At minimum prove:

- no provider credential is present in the admitted environment;
- provider spies/counters remain empty across owning tests;
- no PG method is reached from market/fundamentals projections;
- current quote/provider source files are byte-identical to Task 0;
- price collector/scheduler partial-truth files are byte-identical;
- Financial Datasets spend-policy owners are byte-identical;
- Tranche B scoring owners are byte-identical;
- production DB/data/scheduler metadata match Task 0; and
- no old-data deletion/movement occurred.

Rerun post-cutover `consumer-census.tsv` and
`behavior-propagation.tsv` reconstruction. Zero unknowns and no remaining
current old-data consumer/writer are required before review-ready status.

- [ ] **Step 6: Run fresh native canonical admission**

Create a new exact-tip detached worktree under a new path. Recheck pinned
wrapper/reporter/probe/toolchain identities and the fresh-worktree boundary.
Run the probe and then:

```bash
cd /path/to/fresh-exact-tip-worktree
/tmp/eir002-green-baseline/run_native.sh \
  eir006-task6-native-tip-REPLACE_WITH_TIP_SHORT_SHA
```

The stage name is single-use and must be replaced with the actual reviewed tip
identity before execution. The wrapper owns the probe, report, and transcript;
the operator must not pass worktree or output paths as positional arguments.

Expected exact admission:

```text
4581 collected = 4581 seen
4509 passed / 72 skipped / 0 failed / 0 errors
exit 0
non-passing SHA e3b0c442...
```

The base/tip runs use the same native protocol and comparable fresh-worktree
shape. A sandbox run, partial transcript, focused aggregate, or monolithic run
with a different environment cannot substitute.

- [ ] **Step 7: Reconcile every generated artifact**

Use the exact EIR-002/Tranche A pre/post protocol:

- ordinary and ignored status;
- complete `data`/`src/data` path inventory;
- symlink inventory;
- exact path, inode, mode, size, mtime_ns, SHA for every new artifact;
- exact-path quarantine only; and
- byte-identical restoration of the pre-run boundary.

Never truncate or restore a production file from this isolated run. Any
modified pre-existing file is a Stop Condition.

- [ ] **Step 8: Complete evidence and commit review packet**

Evidence must contain:

- reviewed authority/plan SHAs;
- base/stage/final backend and frontend collection streams;
- exact `+29/-1` and `+1/-0` ledgers;
- Task 0 and post-cutover census streams plus behavior propagation;
- every RED/GREEN result and exact wrong-RED disposition;
- all ten mutation diffs/results/restored SHAs;
- focused/protected/frontend/typecheck/build/scanner results;
- provider/PG/protected-byte counters;
- native base/tip reporter JSON and empty non-passing streams;
- artifact transactions; and
- production no-write metadata comparison.

Set plan/evidence status to `IMPLEMENTATION REVIEW READY`; update the priority
map newest first and EIR-006 `next_action` to independent implementation review.
Commit only docs:

```bash
git add \
  docs/superpowers/plans/2026-08-03-eir-006-valuation-price-truth.md \
  docs/superpowers/evidence/2026-08-03-eir-006-valuation-price-truth.md \
  docs/design/ENGINEERING_ISSUE_REGISTER.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: prepare EIR-006 implementation review"
```

Stop. Product merge and deletion manifest remain unauthorized pending review.

---

### Task 7: Independent Review, Fast-Forward Merge, And Product Rollout

- [ ] **Step 1: Require independent implementation review**

The reviewer must reconstruct from raw artifacts, not evidence prose:

- all four final collection identities;
- exact backend `+29/-1`, frontend `+1/-0`, and existing-ID preservation;
- all ten mutation outcomes and restored product SHAs;
- static cache forbidden-field witness;
- selector no-create/read-only witness;
- shared stored-SEC multi-consumer equality;
- SEC/FD/earnings provider-spy results;
- consumer and behavior-propagation census closure;
- protected byte boundaries;
- native `4509/72/0`; and
- zero production data/scheduler/provider change.

Any finding returns to a bounded amendment/fix/re-review; do not merge a
partially cleared tip.

- [ ] **Step 2: Fast-forward master to the exact reviewed product tip**

Prove linear ancestry from `fd6d1b86` through the reviewed branch tip and use
`git merge --ff-only`. Do not cherry-pick or synthesize a merge commit. Record
pre/post master and origin pointers. Do not push unless separately requested.

- [ ] **Step 3: Repeat merged verification from a fresh exact-master worktree**

Use new single-use stage names and repeat:

- backend/frontend collections;
- backend focused/protected;
- frontend full/typecheck/build/scanner;
- native canonical admission; and
- artifact transaction.

Expected identities/results equal Task 6 exactly. Any mismatch stops rollout.

- [ ] **Step 4: Perform bounded read-only rollout observations**

With no provider or full detailed-financials call:

1. open production `market_data.db` read-only/query-only;
2. call only `get_valuation_price_basis()` for one known ticker and record the
   typed shape, required/actual market date, timestamp, and source without
   treating the observed numeric price as a test constant;
3. run a fixture-only missing/unreadable selector smoke;
4. use fixture/provider doubles to prove old `metrics_*_annual_y2` remains
   ignored even while rows still exist;
5. call `get_ibkr_prices_status()` read-only and compare it to
   `local_market_stats()["prices"]`; and
6. query current status/coverage projections read-only and verify stored SEC
   counts agree with the shared cache reader and fundamentals sync is null.

Do not warm a cache, call SEC/FD/IBKR, run a scheduler, or change a row.

- [ ] **Step 5: Record `EIR006_PRODUCT_CUTOVER_TIP`**

Commit docs-only merged rollout evidence after focused review. Keep EIR-006
`promoted`; set the next action to the fresh deletion manifest. State plainly:

```text
product truth cutover merged
physical old data still present
no deletion approval has been granted
EIR-006 remains open
```

---

### Task 8: Build The Fresh Exact Deletion Manifest - Read Only

This task begins only after Task 7 closeout is merged. It builds decision
evidence; it does not move or delete anything.

- [ ] **Step 1: Re-ground current product and writer state**

Record exact merged product/test commit, current consumer-census SHA, scheduler
enabled/cadence state, sidecar/scheduler PIDs, all current market-data writer
processes, writable DB holder census, and production DB metadata. If a current
old-data consumer/writer exists, stop and reopen product implementation.

- [ ] **Step 2: Build exact file manifest without globs in execution output**

Discovery may enumerate the two reviewed directories, but the result becomes a
sorted exact relative-path list. For every one of the expected 300 CSVs plus
the collection summary record:

```text
relative path
family
ticker/raw ticker
size
mode
inode
mtime_ns
SHA-256
row count
minimum/maximum normalized absolute timestamp
```

Require exactly 225 `15min`, 75 `hourly`, and one summary. Any additional file
or different family stops for review. Record empty-directory cleanup targets
separately; they are not wildcard authority.

- [ ] **Step 3: Recompute raw and canonical CSV-to-SQLite views**

Pin the comparison implementation bytes and exact alias input. Normalize all
timestamps to absolute instants. Produce both views and require the design's
decision-relevant facts:

```text
physical rows:                  2,547,747
raw unique keys:                2,314,293
raw duplicate rows:               233,454
raw conflicting duplicate keys:        58
raw apparent DB value diffs:           161

canonical unique keys:          2,298,763
canonical duplicate rows:          248,984
canonical conflicting keys:            176
canonical DB value diffs:                43
  volume-only:                          23
  including OHLC:                       20
canonical keys absent from DB:           0
LC keys overlapped by HAPN:          15,530
LC/HAPN alias conflicts:                118
```

Only the canonical view is deletion admission. A raw-view match cannot
substitute. If current DB growth changes unrelated row totals but any reviewed
CSV key is absent, stop. Do not copy differing values into SQLite.

- [ ] **Step 4: Build exact DB-row manifest**

Using `mode=ro` and `PRAGMA query_only=ON`, list exact primary keys and metadata
for:

- every old `metrics_*_annual_y2` detailed-financial cache row;
- every legacy `fundamentals` row;
- the exact `market_sync_meta` fundamentals row; and
- zero rows from any current cache family.

Do not use SQL `LIKE` as execution authority. Enumerate exact keys in the
manifest and require later equality. Record row counts/ticker/snapshot/expiry/
source metadata without retaining payload contents in tracked evidence.

- [ ] **Step 5: Re-run the final consumer/training/current-doc census**

Require:

- zero current reader of quarantined file families;
- zero current writer capable of repopulating them;
- no training input owner;
- no status/API/tool/frontend projection using legacy fundamentals rows;
- no retired fundamentals sync projection;
- stored-only route and all stored-SEC projections agree; and
- every remaining low-level empty compatibility method has an explicit owner.

- [ ] **Step 6: Write a manifest packet and stop for independent review**

The packet includes only metadata, identities, comparison summaries, exact path
and row-key authorities, saved operational state, and rollback requirements.
It contains no secret and no archived data payload.

At this gate, amend this plan with:

- exact manifest SHA;
- exact destructive-controller source and SHA;
- exact same-filesystem quarantine root;
- exact DB row-snapshot format/location and validation SHA;
- exact SQL transaction with parameter count;
- exact pre/post/rollback commands;
- exact scheduler stop/start owner and state restoration; and
- fresh stop conditions discovered by the manifest.

Independent review must clear the amendment. Then ask the user for separate
approval of the exact manifest. Until that approval, Task 9 remains unchecked
and no destructive command may run.

---

### Task 9: Execute The Separately Approved Physical Closeout

This task is intentionally blocked at plan publication. Its mechanics become
executable only through the reviewed Task 8 amendment and explicit user
approval.

- [ ] **Step 1: Verify approval and exact identities**

Require exact approved manifest/controller/product/DB/file identities. A
changed file, row, alias, writer state, scheduler state, or product commit
invalidates approval and returns to Task 8.

- [ ] **Step 2: Quiesce writers and preserve exact operational state**

Save scheduler enablement/cadence, stop sidecar/scheduler/market writers through
their reviewed owner, and prove no writable DB holder remains. Read-only
observer processes are classified; ambiguity stops execution.

- [ ] **Step 3: Establish verified temporary rollback assets**

Move only exact approved file paths to a same-filesystem temporary quarantine.
Create and verify a temporary full-row snapshot of only approved DB rows while
writers remain stopped. No durable archive is created and no glob determines a
destructive target.

- [ ] **Step 4: Execute the exact SQLite transaction**

Delete only enumerated old cache keys, all enumerated legacy fundamentals rows,
and the exact retired fundamentals sync row in one explicit transaction.
Assert affected-row counts equal the approved manifest before commit; otherwise
rollback immediately.

- [ ] **Step 5: Verify product truth while rollback remains available**

With writers still stopped, prove:

- old files/rows are absent from active paths;
- current cache families are byte/row identical;
- no product reads quarantine;
- focused/backend/frontend/canonical provider-free gates are green;
- selector available/unavailable fixture contracts are green;
- stored SEC projections agree; and
- current price/news data is unchanged.

- [ ] **Step 6: Restore on any failure, or permanently remove rollback assets**

On any failure: restore exact file paths and DB rows, verify equality to the
manifest, and only then restore scheduler state. Do not attempt a partial
forward repair.

On full success: permanently remove the exact temporary file quarantine and
row snapshot, verify no durable archive remains, then restore the exact saved
scheduler enablement/cadence and verify readback.

- [ ] **Step 7: Close EIR-006 with independently reviewed evidence**

Record no data contents. Evidence must prove:

```text
225 15-minute CSVs absent
75 hourly CSVs absent
collection summary absent
retired empty directories absent
old detailed-financial cache keys absent
legacy fundamentals rows absent
retired fundamentals sync row absent
no durable archive
canonical admission green
read-only production behavior truthful
saved scheduler state restored exactly
```

After independent closeout review, set EIR-006 `closed` with exact product,
manifest, execution, verification, and closeout commits.

---

## 5. Stop Conditions

Stop immediately and amend/re-review if:

1. design, wrapper, reporter, wakeup probe, base collection, or frontend
   collection identity differs;
2. Task 0 cannot close every census hit or behavior-propagation caller;
3. a current runtime consumer of hourly CSVs or training consumer of any price
   CSV is found;
4. the existing completed-session calendar cannot be extracted without
   changing market-data-direct semantics;
5. qualified price selection requires a provider call or writable SQLite
   connection;
6. a selector failure creates a file/path/journal/WAL/SHM or leaks exception
   text/path data;
7. one-row presence is replaced by slot completeness or an older-day fallback;
8. dynamic valuation or price provenance enters the static cache payload;
9. old cache keys are read, adapted, or migrated;
10. a unit conversion depends on magnitude guessing;
11. old IBKR snapshot data can override SEC facts or local price basis;
12. annual SEC/FD ordering, enablement, spend, retry, or provider-call behavior
    changes;
13. earnings-history or upcoming-earnings behavior changes;
14. any stored-fundamentals consumer implements a separate positive-cache rule;
15. a legacy fundamentals row or sync row remains a current product authority;
16. FileBackend or daily-update can reopen/scan retired price paths;
17. current UI renders known stable IDs instead of localized product copy;
18. historical evidence is rewritten as though it were current documentation;
19. any new/removed/renamed/parametrized/skipped/xfail node exists outside the
    exact backend/frontend ledgers;
20. any reviewed mutation survives or fails for an unrelated reason;
21. a provider, PG market fallback, scheduler, production write, or secret read
    occurs during Tasks 0-7;
22. a protected price collector/current quote/FD-policy/Tranche-B byte changes;
23. native reporter sees fewer nodes than collected, a partial transcript is
    called pass, or canonical admission runs in the incompatible sandbox;
24. a pre-existing file changes or a generated artifact remains unaccounted;
25. product cutover is not independently reviewed and merged before manifest
    construction;
26. deletion manifest method, alias input, file set, DB identity, or row set
    changes between review and execution;
27. any canonical CSV key is absent from SQLite;
28. a current writer/consumer remains at deletion time;
29. rollback assets cannot be created and verified before deletion;
30. affected SQLite row counts differ from the approved exact list;
31. user has not separately approved the exact destructive manifest;
32. a destructive glob/basename match is used after manifest approval;
33. scheduler state cannot be restored exactly; or
34. deletion would create a durable archive or migrate the discarded 2023
    hourly data.

## 6. Plan Self-Review Map

| Design requirement | Owning task/section |
|---|---|
| Existing 16:30 ET calendar is the sole authority | Task 1 / Section 3.1 |
| No-create read-only selector | Task 1 / Section 3.2 |
| ET date, one-row presence, no older fallback | Task 1 + M1-M3 |
| Closed typed price basis | Task 1 / Section 3.3 |
| New static semantic cache; old key ignored | Task 2 / Sections 3.4-3.6 + M4-M5 |
| Base-unit valuation; no heuristics | Task 2 + M6 |
| Legacy snapshot cannot override | Tasks 2-3 + M7 |
| SEC-first and existing FD gate preserved | Task 3 |
| Peer absence visible and nulls excluded | Task 3 |
| One stored annual SEC cache authority | Task 4 / Section 3.8 + M10 |
| Retired fundamentals sync absent | Task 4 |
| FileBackend/daily-update cannot resurrect files | Task 4 + M8-M9 |
| Settings/Ticker Detail/Dashboard truthful in both locales | Task 5 |
| Current docs/model descriptions truthful | Task 5 |
| Closed static consumer census | Tasks 0, 5, 8 |
| Exact backend/frontend node accounting | Sections 2.1-2.6; Tasks 0, 6, 7 |
| Provider-free and production-write-free implementation | Tasks 0-7 |
| Canonical native green admission | Tasks 0, 6, 7 |
| Product merge precedes manifest | Task 7 before Task 8 |
| Raw/canonical manifest methods both explicit | Task 8 |
| Exact separate deletion approval | Tasks 8-9 / Section 0.2 |
| Same-line final physical removal with rollback | Task 9 |
| EIR remains open until physical closeout | Tasks 7-9 |
