# ArkScope Tool Catalog (canonical)

**Date**: 2026-06-04
**Status**: CANONICAL tool authority — introspection table from live `ToolRegistry` + **gpt-5.5 review folded 2026-06-04**; verdicts locked for every contested tool (web 3-way split, `codex_web_research` retire, CA definition-only narrowing, `synthesize_signal` preserve-adapt, `refresh_sa_alpha_picks` → `profile_state_write`). Third and last canonical doc (ProductSpec → ProviderCatalog → **ToolCatalog**). Code follow-ups now **done**: `codex_web_research` removed (2a168e9); `refresh_sa_alpha_picks` stripped to read-only status (842b5bf); post-catalog drift rows folded (`get_sa_feed`, `get_sa_comment_focus`, `get_ticker_data_coverage`); `get_current_quote` added as read-through quote primitive; `get_portfolio_holdings` added as the local holdings snapshot primitive. **Live registry now 56** (bridges 57). Next → build the desktop-app shell.

**Authority**: this doc owns the **registry tool layer** — what each tool is, which of the four capability classes it belongs to, and its keep/adapt/definition-only/retire verdict + the tool-design rules. Product/agent boundaries = `ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md`; per-provider facts the tools consume = `ARKSCOPE_PROVIDER_CATALOG.md`; architecture = `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`.

> 中文摘要：直接從 `ToolRegistry` introspect 出的 **56 個工具**（codex_web_research 已於 2a168e9 移除；catalog 定稿後漂移的三個工具已補列；`get_current_quote` 與 `get_portfolio_holdings` 已新增）逐一分類（穩定 primitive／composed-analysis／agent-control／retire-adapt）並標 keep/adapt/preserve-adapt/definition-only/retire。**這份是 code-introspection 出來的事實表，不是文件印象**；verdict 已折入 gpt-5.5 2026-06-04 review（web 三分、codex 退場、CA 收窄、`refresh_sa_alpha_picks`→`profile_state_write`），僅 §4「still open」待 build 時定序。

---

## 0. How to read this catalog

### 0.1 Source of truth = live introspection (NOT doc impression)

Every tool below was enumerated by constructing `ToolRegistry` and calling `register_all()` + `list_all()` on **2026-06-04**, then reconciled to the current live registry after post-catalog drift and the 2026-07 quote/holdings primitives — name, category, and parameters are authoritative from code. **Count: 56 registry tools** (+`delegate_to_subagent` injected at each agent bridge = **57** in bridges), across 11 categories. Lineage: post-RL-retirement baseline 52/53; `codex_web_research` removed 2026-06-04 (2a168e9) → 51/52; three already-registered drift tools folded (`get_sa_feed`, `get_sa_comment_focus`, `get_ticker_data_coverage`) → 54/55; `get_current_quote` added 2026-07 → 55/56; `get_portfolio_holdings` added 2026-07 → **56/57**.

> Re-run to refresh: `python -c "from src.tools.registry import ToolRegistry; r=ToolRegistry(); r.register_all(); print(len(r.list_all()))"`.

### 0.2 Capability classes (from ProductSpec §4 reasoning posture)

| Class | Meaning | Tools-as-definitions? |
|-------|---------|----------------------|
| **SP — stable primitive** | Fetch/compute a stable fact: query price / fundamentals / macro / filing / SA capture / IV / Greeks. | ❌ **No** — keep a stable implementation; the agent must NOT re-wire these ad-hoc each call. |
| **CA — composed analysis** | Compose primitives into a higher-order analysis (digest, comparison, multi-factor synthesis). | ✅ **Candidate** — can survive as a *definition / recipe / schema* a strong model composes from primitives. |
| **AC — agent-control** | Memory, reports, code execution, web access, alerts, subagents — the agent's own machinery. | ❌ No — these are infrastructure with permission gates (ProductSpec §4.3). |
| **RA — retire-adapt** | Scenario changed: provider/storage assumption wrong, methodology known-flawed, or superseded (RL already retired). | n/a — verdict is adapt or retire. |

### 0.3 Verdict vocabulary

`keep-current` (stable, no change) · `adapt` (keep the capability, fix a wrong assumption/output) · `preserve-adapt` (keep the deterministic impl, reframe its *authority/output* — e.g. evidence-not-decision) · `definition-only` (convert to a composable recipe/schema, drop the hardcoded pipeline) · `retire` (remove). Verdicts below are **folded from gpt-5.5's 2026-06-04 review** (no longer open drafts), except the §4 "still open" items.

---

## 1. Introspection table — all 56 tools (grouped by capability class)

### 1.1 Stable primitives (SP) — 33 tools · verdict: **keep-current** (keep the implementation)

> gpt-5.5 Q1: "which are stable primitive — keep the implementation, don't let the agent rewrite the wiring." These are the data/compute primitives. DAL/provider-backed; the agent calls them, never re-implements them.

| Tool | Registry cat | Params | Backed by | Verdict |
|------|-------------|--------|-----------|---------|
| `get_current_quote` | prices | ticker*, source? | IBKR snapshot + local last-bar fallback | keep-current |
| `get_ticker_prices` | prices | ticker*, interval?, days? | IBKR/Tiingo/Polygon (ProviderCatalog) | keep-current |
| `get_price_change` | prices | ticker*, days? | price providers | keep-current |
| `get_sector_performance` | prices | sector*, days? | price providers | keep-current |
| `get_ticker_news` | news | ticker*, days?, source?, limit? | IBKR/Polygon/Finnhub news | keep-current |
| `search_news_by_keyword` | news | keyword*, days?, ticker?, limit? | news store | keep-current |
| `search_news_advanced` | news | query?, tickers?, days?, scored_only?, min_sentiment?, max_risk?, limit? | news store + scores | keep-current |
| `get_news_brief` | news | tickers?, days? | news store | keep-current |
| `get_news_sentiment_summary` | news | ticker*, days? | news scores | keep-current |
| `get_sa_digest` | news | ticker*, days?, max_articles?, max_news?, max_comments?, min_comment_score? | SA capture (deterministic evidence-pack) | keep-current |
| `get_sa_feed` | news | q?, ticker?, item_type?, days?, limit?, offset? | SA capture unified evidence feed | keep-current |
| `get_sa_market_news` | news | ticker?, keyword?, limit? | SA capture | keep-current |
| `list_high_value_comments` | news | window_days?, ticker?, min_score?, limit? | SA comment intelligence | keep-current |
| `get_sa_comment_focus` | news | window_days?, min_score?, limit? | SA comment signals | keep-current |
| `get_sa_alpha_picks` | portfolio | status?, sector? | SA capture | keep-current |
| `get_sa_articles` | portfolio | ticker?, keyword?, article_type?, limit? | SA capture | keep-current |
| `get_sa_article_detail` | portfolio | article_id* | SA capture | keep-current |
| `get_sa_pick_detail` | portfolio | symbol*, picked_date? | SA capture | keep-current |
| `get_portfolio_holdings` | portfolio | account_id?, include_closed? | local profile_state.db portfolio | keep-current |
| `get_detailed_financials` | analysis | ticker* | SEC EDGAR / Financial Datasets | keep-current |
| `get_fundamentals_analysis` | analysis | ticker*, period? | IBKR→SEC→FinancialDatasets chain | keep-current |
| `get_sec_filings` | analysis | ticker*, filing_types?, limit? | SEC EDGAR | keep-current |
| `get_insider_trades` | analysis | ticker*, limit? | SEC EDGAR | keep-current |
| `get_analyst_consensus` | analysis | ticker* | provider-native analyst data | keep-current |
| `get_economic_calendar` | analysis | country?, importance?, days_back?, days_forward?, as_of?, limit? | Finnhub calendar | keep-current |
| `get_macro_value` | analysis | series_id*, observation_date*, as_of? | FRED (point-in-time) | keep-current |
| `get_ticker_data_coverage` | analysis | ticker*, target_date? | local data coverage diagnostics | keep-current |
| `get_option_chain` | options | ticker*, expiry?, num_strikes?, max_expirations_for_term_structure? | IBKR options | keep-current |
| `get_iv_analysis` | options | ticker* | IV store | keep-current |
| `get_iv_history_data` | options | ticker* | IV history parquet | keep-current |
| `get_iv_skew_analysis` | options | ticker*, expiry?, num_strikes? | IV store | keep-current |
| `calculate_greeks` | options | S*, K*, T*, r*, sigma*, option_type?, model?, dividend_yield? | pure math (Black-Scholes) | keep-current |
| `check_data_freshness` | analysis (freshness) | — | freshness meta (truth = data) | keep-current |

### 1.2 Composed analysis (CA) — 10 tools · verdict: **mixed** (2 definition-only · 3 keep-impl/adapt-output · 3 signal keep-current · 1 preserve-adapt · 1 adapt)

> gpt-5.5 Q2 + review (2026-06-04): only the **thin orchestration** digests (`get_morning_brief`, `get_watchlist_overview`) are true definition-only candidates. `get_peer_comparison` / `get_earnings_impact` / `get_portfolio_analysis` carry **real deterministic computation** (sector resolution + percentile / earnings-drift / beta+correlation+P&L) → **keep the implementation**, adapt only the *output* to the §2 card where they conclude. `synthesize_signal` is **preserve-adapt**, not definition-only (see §1.4).

| Tool | Registry cat | Params | Composes | Verdict |
|------|-------------|--------|----------|---------|
| `get_morning_brief` | analysis | — | watchlist + news + signals + macro | **definition-only / adapt-to-card** — thin orchestration; emit §2 card |
| `get_watchlist_overview` | analysis | — | watchlist + prices + news | **definition-only / adapt-to-card** — thin orchestration |
| `get_peer_comparison` | analysis | ticker?, tickers?, sector? | fundamentals across peers | **keep-current** (real impl: sector resolution, metric ranking, percentile) — adapt output to §2 where it concludes |
| `get_earnings_impact` | analysis | ticker*, quarters? | earnings + price reaction | **keep-current** (real impl: earnings-day move / drift / surprise) — adapt output |
| `get_portfolio_analysis` | portfolio | tickers?, holdings? | prices + fundamentals + signals | **keep-current** (real impl: beta, correlation, P&L, concentration) — adapt output |
| `detect_anomalies` | signals | ticker*, days?, as_of_date? | price/news/volume anomaly | keep-current (real impl in `src/signals`) |
| `detect_event_chains` | signals | ticker*, days? | event-chain pattern detection | keep-current |
| `get_signal_factors` | signals | ticker*, days?, as_of_date?, strategy? | multi-factor decomposition | keep-current (pairs w/ `synthesize_signal` = signal + explainability) |
| `synthesize_signal` | signals | ticker*, days?, strategy?, as_of_date? | weighted multi-factor synthesis | **preserve-adapt** — keep deterministic impl; surface as *evidence* signal (data_quality + traceability), weaken recommendation authority, not final decision |
| `scan_mispricing` | options | tickers*, mispricing_threshold_pct?, min_confidence? | option pricing vs Black-Scholes | **adapt** (flawed methodology — see §1.4) |

### 1.3 Agent-control (AC) — 13 tools · verdict: mostly keep-current; **1 adapt** (save_report). `codex_web_research` removed (2a168e9); `refresh_sa_alpha_picks` stripped to read-only (842b5bf)

> The agent's own machinery; permission-gated per ProductSpec §4.3. Not definition-only (infrastructure, not analysis). Web tools split three ways in §1.5.

| Tool | Registry cat | Params | Permission gate (§4.3) | Verdict |
|------|-------------|--------|------------------------|---------|
| `save_memory` | memory | title*, content*, category?, tickers?, tags?, importance? | `db_write` | keep-current |
| `recall_memories` | memory | query?, category?, tickers?, tags?, days?, limit? | none (read) | keep-current |
| `list_memories` | memory | category?, days?, limit? | none (read) | keep-current |
| `delete_memory` | memory | memory_id* | `db_write` | keep-current |
| `save_report` | reports | title*, tickers*, report_type*, summary*, content*, conclusion?, confidence? | `db_write` | **adapt** → accept/store §2 card fields + traceability (it *stores* the card; agent/report composition *generates* it) |
| `list_reports` | reports | ticker?, days?, report_type?, limit? | none (read) | keep-current |
| `get_report` | reports | report_id?, file_path? | none (read) | keep-current |
| `execute_python_analysis` | execution | code?, task?, data_json?, timeout?, background? | `code_execution` | keep-current |
| `tavily_search` | web | query*, max_results?, search_depth?, topic?, days? | `external_web_access` (+ `metered_spend` by usage) | keep-current — web-search/fetch (§1.5) |
| `tavily_fetch` | web | url*, extract_depth?, offset?, max_chars? | `external_web_access` (+ `metered_spend` by usage) | keep-current — web-search/fetch (§1.5) |
| `web_browse` | web | url*, wait_for?, extract_links?, offset?, max_chars? | `external_browser_automation` | **keep/adapt** — browser-automation; backend pluggable (§1.5) |
| `scan_alerts` | monitor | tickers? | none (read) | keep-current |
| `refresh_sa_alpha_picks` | portfolio | — | none (read) | **adapt done ✓ (842b5bf)** — implicit `tickers_core.json` sync stripped; now pure read-only status. Explicit gated 'follow' action deferred to desktop (§1.5) |

*(`codex_web_research` was here — **removed** 2a168e9, see §1.4; the deep-research capability re-homes provider-neutral in §1.5.)*

*(+ `delegate_to_subagent` — injected at each agent bridge, not in the registry's 56; AC class; `subagent_mode`-bounded per ProductSpec §4.1.)*

### 1.4 Retire-adapt (RA) flags — scenario changed

> gpt-5.5 Q3: "which must adapt/retire because the scenario changed." RL tools already retired (2026-06-03, `94861f7`+`6b49c74`). Flags below are **resolved** (gpt-5.5 review 2026-06-04); the two code follow-ups (codex removal, SA-refresh strip) are now **done** — marked ✓ with commit refs:

| Tool | Class | Flag | Why |
|------|-------|------|-----|
| `scan_mispricing` | options/CA | **adapt** | Naive Black-Scholes "market > theoretical = overpriced" is **known-flawed** — `docs/data/OPTIONS_PRICING_THEORY.md` shows VRP makes it always wrong; correct method = IV-percentile-rank vs own 252-day history. Re-base the methodology. |
| `save_report` | reports/AC | **adapt** | Must **accept/store** the ProductSpec §2 card fields (conclusion / counter-thesis / triggers / invalidation / confidence / traceability) + metadata. The card is produced by agent/report composition — `save_report` stores it, it does **not** generate it. |
| `refresh_sa_alpha_picks` | portfolio/AC | **adapt done ✓ (842b5bf)** | Implicit `tickers_core.json` sync stripped — now pure read-only status. Universe sync stays owned by the PROTECTED SA native host (unchanged). Explicit gated 'follow Alpha Picks' (`profile_state_write`) deferred to desktop (§1.5). |
| `codex_web_research` | web/AC | **retired ✓ (2a168e9)** | Removed: hard-binds external Codex CLI + OpenAI OAuth + `--full-auto --search`; bypassed BYOK and the §2 output contract. Capability re-homed as provider-neutral `deep_research` (§1.5). |
| `web_browse` | web/AC | **keep/adapt** | Gate locked to `external_browser_automation` (drives a browser). Framed as browser-automation with a pluggable backend (§1.5); seed of the CloakBrowser spike. |
| `get_morning_brief`, `get_watchlist_overview` | analysis/CA | **definition-only / adapt-to-card** | Thin orchestration digests → composable recipe that emits the §2 card; no heavy impl to preserve. |
| `synthesize_signal` | signals/CA | **preserve-adapt** | Keep the deterministic multi-factor impl; reframe output as an *evidence* signal (data_quality + traceability), weaken the recommendation authority — not definition-only. |

### 1.5 Web & research capabilities — the 3-way split (gpt-5.5 review, 2026-06-04)

The old "web" category conflated three distinct capabilities with different gates and backends. Lock them apart:

| Capability | What it is | Tools (live → target) | Gate |
|-----------|-----------|----------------------|------|
| **web_search / fetch** | search + fetch *public content* via an API — no browser driven | `tavily_search`, `tavily_fetch` (live) → + future OpenAI / Anthropic hosted web-search/fetch | `external_web_access` (+ `metered_spend` by usage) |
| **browser_automation** | drive a *real/embedded* browser — login, click, read DOM, JS-heavy pages | `web_browse` (live; Playwright now) | `external_browser_automation` |
| **deep_research** | provider-neutral multi-step research → a §2 card | **no live tool** (`codex_web_research` removed 2a168e9); candidates: OpenAI Responses web-search/deep-research, Anthropic web_search+web_fetch, or ArkScope-orchestrated search/fetch/browser | `metered_spend` + `external_web_access` |

- **`web_browse` backend is pluggable** behind one `external_browser_automation` gate: `playwright_builtin` (today) / `user_chrome` / `cloakbrowser_spike`. CloakBrowser (source-patched Chromium, Playwright/CDP drop-in, persistent profiles) is a **backend spike** (ProductSpec §7) — *not* a v1 replacement for the SA Chrome/Firefox extension pipeline (binary supply-chain, profile/session mgmt, packaging, ToS, CDP security all open).
- **`deep_research` must be provider-neutral.** `codex_web_research` was removed (2a168e9) because it hard-binds the external Codex CLI + OpenAI OAuth / `--full-auto --search`, bypassing BYOK and the §2 output contract — *not* because the capability is unwanted. Rebuild on OpenAI SDK **and** Anthropic SDK paths, same §2 card out.

**Planned tools (NOT in the live 56)** — recorded so the permission model stays ahead of them:

| Planned tool | Purpose | Gate |
|-------------|---------|------|
| `sync_sa_alpha_picks_watchlist` / `follow_sa_alpha_picks` | show an add/remove **diff** vs SA current portfolio; let the user explicitly fold picks into the research universe | `profile_state_write` |

> Long-term direction (out of this catalog's permission scope, into the **SA pipeline**): make Alpha Picks a **DB-derived universe source** (`watchlist_source = sa_alpha_picks_current`) that the UI opts into, instead of writing `config/tickers_core.json` directly; generate a config view/export only for legacy-pipeline compat. Separately, locate the source Alpha Picks article by closest-time + content match to attach a confidence/evidence link (SA-capture improvement, not a permission concern).

---

## 2. Verdict roll-up

| Verdict | Count | Tools |
|---------|------:|-------|
| **keep-current** | 50 | all SP (33) · 3 signal impls (detect_anomalies, detect_event_chains, get_signal_factors) · 3 CA compute tools (get_peer_comparison, get_earnings_impact, get_portfolio_analysis — *adapt output to §2 where they conclude*) · 11 AC (memory R/W ×4, reports R ×2, execute_python_analysis, tavily ×2, scan_alerts, refresh_sa_alpha_picks — read-only, adapt done 842b5bf) |
| **definition-only / adapt-to-card** | 2 | get_morning_brief, get_watchlist_overview |
| **preserve-adapt** | 1 | synthesize_signal |
| **adapt** | 2 | scan_mispricing, save_report |
| **keep/adapt** (gate + backend) | 1 | web_browse |
| **retired ✓** (not in live 51) | — | codex_web_research (2026-06-04, `2a168e9`) · RL tools (2026-06-03, `94861f7`+`6b49c74`) |

**Total live = 50 + 2 + 1 + 2 + 1 = 56 ✓**

---

## 3. Tool-design rules (LOCK candidates — for review)

1. **Data primitives stay implemented.** SP-class tools (price/fundamentals/macro/filing/SA/IV/Greeks) keep stable code. The agent calls them; it does **not** re-author the data wiring per query. (Stability + provider-abstraction via the DAL — ProviderCatalog.)
2. **"Tools as definitions" applies only to composed-analysis.** A strong model may compose CA recipes from SP primitives; only CA-class tools are candidates to become definition/schema rather than hardcoded pipelines.
3. **Decision-bearing output conforms to the §2 AI output contract.** Any agent/composition output bearing a conclusion/recommendation (the digests; a saved report's body) is the fixed-schema card + traceability, not free prose. `save_report` **stores** those §2 card fields + traceability metadata — it does **not** generate them.
4. **Prefer provider-native signals over re-scoring** (ProductSpec §3): analyst consensus / sentiment / factor grades enter as evidence; the LLM integrates, it doesn't re-compute everything.
5. **New tools declare a capability class + permission gate + provider dependency** at registration, so Settings + the permission model (§4.3) and ProviderCatalog stay in sync.
6. **Schema/params are part of the contract.** The introspection table is the source of truth; a param change is a catalog-touching change.
7. **Mutating the research universe / profile state is `profile_state_write`** — gated independently of `db_write` and of storage location (config file *or* DB). A tool that changes the watchlist / ticker universe / provider-or-agent settings / auto-follow rules must not pigg-back on a read or a `db_write`; the side-effect must be explicit and separately approvable.
8. **Web access, browser automation, and deep research are three separate capabilities** (§1.5) with three separate gates. Never collapse them; auto-approving one never grants another. `deep_research` is provider-neutral by construction (no hard CLI/OAuth binding).
9. **The AI-card EvidencePacket excludes ArkScope-generated LLM scores by default** (ProductSpec §2.4). `news_scores` multi-model sentiment/risk, the live `score_ibkr_news` / `score_{sentiment,risk}_anthropic` / `openai_summary` outputs, and score-derived tool fields (e.g. `get_news_sentiment_summary`'s `sentiment_mean`) are **not** objective evidence primitives — they are historical / enrichment / fallback signals. They may enter an EvidencePacket only when explicitly labeled `source_type = "arkscope_fallback_score"` / `"arkscope_derived_summary"` (with model · prompt/version · as-of · method), and in v1 are **off by default**. The news-store tools (`search_news_advanced`, `get_news_sentiment_summary`) remain live for history/enrichment/fallback, but their scores must not masquerade as raw or provider-native evidence. Objective inputs are: raw market data (price/volume/OHLC/IV/fundamentals), raw news rows (title · time · source · URL · excerpt), SEC/FRED/calendar facts, deterministic metrics, and provider-native ratings (source-labeled); SA content enters tagged as community/opinion. Triaging which scoring tools are open-dataset provenance vs live-enrichment vs retire is a **later, separate** pass — not a deletion now.

---

## 4. Decisions — resolved + still open

**Resolved (gpt-5.5 review, 2026-06-04 — folded above):**
1. **CA definition-only narrowed** to the two thin digests (`get_morning_brief`, `get_watchlist_overview`). `get_peer_comparison` / `get_earnings_impact` / `get_portfolio_analysis` keep their real impl (adapt output to §2). `synthesize_signal` = **preserve-adapt**, paired with `get_signal_factors`.
2. **`codex_web_research` → retire**; the *capability* re-homes as provider-neutral `deep_research` (§1.5).
3. **`web_browse` → `external_browser_automation`**, pluggable backend (§1.5).
4. **`refresh_sa_alpha_picks` → adapt + `profile_state_write`**; strip the implicit `tickers_core.json` sync, universe-following becomes an explicit gated action. New gate `profile_state_write` added to ProductSpec §4.3 (now **6** gated classes).

**Still open (build sequencing, not blocking adoption):**
1. **`scan_mispricing` adapt timing** — re-base on IV-percentile-rank now, or defer until an options-analysis surface exists?
2. **`deep_research` build path** — OpenAI SDK, Anthropic SDK, or ArkScope-orchestrated first? (spike, ProductSpec §7)
3. **CloakBrowser backend** — when/whether to wire `cloakbrowser_spike` behind `web_browse` vs stay on `playwright_builtin`. (spike, ProductSpec §7)
4. **Desktop-phase follow-up**: add the explicit gated `sync_sa_alpha_picks_watchlist` / `follow_sa_alpha_picks` action once `profile_state_write` enforcement + diff UI exist.
