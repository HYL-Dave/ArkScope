# ArkScope Tool Catalog (canonical)

**Updated**: 2026-08-21
**Status**: CANONICAL current registry authority
**Live registry**: 52 tools; agent bridges add `delegate_to_subagent` for 53

This document describes the current `ToolRegistry`, not removed implementations
or possible future products. Historical catalog versions remain recoverable from
Git. Product boundaries belong to `ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md`; provider
facts belong to `ARKSCOPE_PROVIDER_CATALOG.md`.

## 0. Rules

1. Registry name, category, and parameters come from code introspection.
2. Raw facts remain distinct from model conclusions and provider-native labels.
3. A tool that mutates state declares the narrow permission gate for that state.
4. Web search, browser automation, and deep research are separate capabilities.
5. Removed recommendation semantics are not compatibility aliases. A future
   Signals product starts from a reviewed hypothesis, evidence contract, OOS
   validation, and kill criteria.

Rebuild the list with:

```text
python -c "from src.tools.registry import create_default_registry; r=create_default_registry(); print(len(r.list_all())); print(*r.list_names(), sep='\n')"
```

## 1. Live registry

### 1.1 All 52 tools

| Tool | Category | Parameters | Current role |
|---|---|---|---|
| `get_ticker_news` | news | ticker*, days?, source?, limit? | raw ticker news |
| `search_news_by_keyword` | news | keyword*, days?, ticker?, limit? | raw keyword search |
| `get_news_brief` | news | tickers?, days? | raw count/date brief |
| `search_news_advanced` | news | query?, tickers?, days?, limit? | raw multi-ticker search |
| `detect_news_volume_anomaly` | news | ticker*, days?, as_of_date? | deterministic count-window anomaly |
| `detect_event_chains` | news | ticker*, days? | deterministic title-event sequence; impact unavailable |
| `get_sa_market_news` | news | ticker?, keyword?, limit? | captured SA market news |
| `get_sa_digest` | news | ticker*, days?, max_articles?, max_news?, max_comments?, min_comment_score? | source-labelled SA evidence digest |
| `list_high_value_comments` | news | window_days?, ticker?, min_score?, limit? | rule-based SA comment ranking |
| `get_sa_comment_focus` | news | window_days?, min_score?, limit? | rule-based SA comment focus |
| `get_sa_feed` | news | q?, ticker?, item_type?, days?, limit?, offset? | unified SA evidence feed |
| `get_current_quote` | prices | ticker*, source? | typed quote or qualified local bar |
| `get_ticker_prices` | prices | ticker*, interval?, days? | local market-data bars |
| `get_price_change` | prices | ticker*, days? | deterministic price change |
| `get_sector_performance` | prices | sector*, days? | deterministic sector performance |
| `calculate_greeks` | options | S*, K*, T*, r*, sigma*, option_type?, model?, dividend_yield? | pure caller-supplied option math |
| `get_option_chain` | options | ticker*, expiry?, num_strikes?, max_expirations_for_term_structure? | live IBKR option chain |
| `get_iv_skew_analysis` | options | ticker*, expiry?, num_strikes? | live-chain skew calculation |
| `get_fundamentals_analysis` | analysis | ticker*, period? | cached SEC facts with qualified local price |
| `get_detailed_financials` | analysis | ticker* | normalized SEC/provider financial facts |
| `get_sec_filings` | analysis | ticker*, filing_types?, limit? | SEC filings |
| `get_insider_trades` | analysis | ticker*, limit? | SEC insider transactions |
| `get_watchlist_overview` | analysis | none | watchlist price and raw-news overview |
| `get_morning_brief` | analysis | none | deterministic raw-news activity brief |
| `get_peer_comparison` | analysis | ticker?, tickers?, sector? | deterministic peer metrics |
| `get_earnings_impact` | analysis | ticker*, quarters? | earnings and price-reaction facts |
| `get_analyst_consensus` | analysis | ticker* | provider-native analyst consensus |
| `check_data_freshness` | analysis | none | local freshness evidence |
| `get_ticker_data_coverage` | analysis | ticker*, target_date? | local coverage diagnostics |
| `get_economic_calendar` | analysis | country?, importance?, days_back?, days_forward?, as_of?, limit? | Finnhub economic calendar |
| `get_macro_value` | analysis | series_id*, observation_date*, as_of? | point-in-time FRED value |
| `list_security_lifecycle_cases` | analysis | ticker?, workflow_state?, source_presence?, limit? | provider-neutral local lifecycle case list |
| `get_security_lifecycle_case` | analysis | case_id* | provider-neutral local lifecycle evidence and workflow detail |
| `get_portfolio_analysis` | portfolio | tickers?, holdings? | deterministic beta/correlation/P&L analysis |
| `get_portfolio_holdings` | portfolio | account_id?, include_closed? | local holdings snapshot |
| `get_sa_alpha_picks` | portfolio | status?, sector? | captured Alpha Picks portfolio |
| `get_sa_pick_detail` | portfolio | symbol*, picked_date? | captured Alpha Pick detail |
| `refresh_sa_alpha_picks` | portfolio | none | read-only extension refresh status |
| `get_sa_articles` | portfolio | ticker?, keyword?, article_type?, limit? | captured SA article index |
| `get_sa_article_detail` | portfolio | article_id* | captured SA article detail |
| `save_report` | reports | title*, tickers*, report_type*, summary*, content*, conclusion?, confidence? | permission-gated report write |
| `list_reports` | reports | ticker?, days?, report_type?, limit? | report index read |
| `get_report` | reports | report_id?, file_path? | report read |
| `save_memory` | memory | title*, content*, category?, tickers?, tags?, importance? | permission-gated memory write |
| `recall_memories` | memory | query?, category?, tickers?, tags?, days?, limit? | memory search |
| `list_memories` | memory | category?, days?, limit? | memory index read |
| `delete_memory` | memory | memory_id* | permission-gated memory delete |
| `web_browse` | web | url*, wait_for?, extract_links?, offset?, max_chars? | browser automation |
| `execute_python_analysis` | execution | code?, task?, data_json?, timeout?, background? | permission-gated local analysis |
| `scan_alerts` | monitor | tickers? | current monitor scan |

### 1.2 Evidence boundaries

- Raw news tools expose title, source, timestamp, URL, excerpt, counts, and date
  ranges. They do not expose ArkScope legacy 1-5 score fields.
- `detect_news_volume_anomaly` uses raw count windows.
- `detect_event_chains` preserves deterministic event order and returns typed
  unavailable impact rather than manufacturing direction or a numeric score.
- Provider-native analyst labels, Polygon source sentiment, SA community data,
  and investor risk preferences remain source-labelled distinct contracts.
- Option pricing accepts the caller's rate. Provider-backed estimates are a
  separate future capability, not a hidden network fallback.
- Lifecycle tools read the local market/profile stores only. They expose
  observation and review evidence but never search the web, write state, or
  apply an action proposal.

### 1.3 Permission boundaries

| Capability | Gate |
|---|---|
| report or generic DB write | `db_write` |
| profile/universe mutation | `profile_state_write` |
| local code execution | `code_execution` |
| public search/fetch | `external_web_access` and metered approval where needed |
| browser automation | `external_browser_automation` |
| future multi-step research | explicit spend and external-access approval |

### 1.4 Retire-adapt

The former ArkScope scoring, composite recommendation, offline RL, and Phase D
recommendation-shaped implementations are retired. Git history is their only
archive. Reintroducing a capability requires a new reviewed semantic and current
data/provider contract; it must not restore old modules, tables, fields, prompts,
or aliases.

The following concepts remain intentional future work, without runnable legacy
scaffolds:

- Signals research with explicit hypotheses, point-in-time data, OOS evaluation,
  provenance, freshness, source coverage, and kill criteria.
- Provider-backed option estimates evaluated through the common provider rubric.
- Provider-neutral deep research that emits the structured evidence/card contract.

## 2. Maintenance

Any registry change must update this table in the same reviewed change and keep
the executable registry/catalog equality test green. Removed tools leave the
current table completely; historical rationale remains in Git rather than in
active-looking rows.
