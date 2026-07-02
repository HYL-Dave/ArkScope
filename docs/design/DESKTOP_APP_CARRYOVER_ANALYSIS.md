# Desktop App Carry-over Analysis — analysis-tools + memory

> **狀態 / Status**: ANALYSIS — code-grounded preservation matrix. 比 [`DESKTOP_APP_VISION_DRAFT.md`](DESKTOP_APP_VISION_DRAFT.md) §8 更深一層：逐元件、有程式碼 + docs 佐證的「desktop app 後保留什麼」判斷。
> **建立日期**: 2026-05-31（8-agent map → synthesize → adversarial-review workflow；review verdict = needs_revision，已套用全部修正）
> **權威關係 / Authority**: 凡與 [`LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`](LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md) 衝突，**SPEC 為準**。本文件是執行層的 carry-over 清單，不重新仲裁架構/儲存/非目標。
> **範圍**: 聚焦使用者指定的兩個子系統 — **分析工具** + **記憶**，外加 scoring / signals / RL / options 邊界區。
> **相關**: [`DESKTOP_APP_VISION_DRAFT.md`](DESKTOP_APP_VISION_DRAFT.md)（產品表面意圖）、[`PROJECT_PRIORITY_MAP.md`](PROJECT_PRIORITY_MAP.md) §10（what-survives 清單）、[`PHASE_D_ANALYSIS_PIPELINE_SKETCH.md`](PHASE_D_ANALYSIS_PIPELINE_SKETCH.md)、[`PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md`](PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md)。

---

## 1. Executive summary

評估了 ~87 個元件。整體 carry-over 故事三句話：

- **不動就能用的耐久核心** = agent 能力 stack + 純計算 analytics：tools registry + Pydantic schemas、5 個 signals 模組 + options pricing 數學、subagents、P1.4 壓縮、attachments、token tracking、replay bridge_tools、code_executor。全部 provider/storage 無關，已達或超過 Hermes parity。
- **最大的一桶是「保留但要 adapt」** = 任何碰儲存或輸出形狀的東西：DAL（加 SQLiteBackend + 暫時性 DuckDB OLAP，同一 Protocol）、SPEC 明列的 8 個 PG-coupled 檔案（freshness / macro_calendar / report_tools / memory_tools / SA / job_runs）re-point、PG schema 轉 SQLite（news_scores/reports/memories：`TEXT[]`→junction table + 強制 FTS5-trigram 中文搜尋）、CLI-print 工具改吐 GUI DTO。
- **真正砍掉的是 pre-pivot / FNSPID 研究 cruft** = CSV-only OpenAI scorers、o3/FNSPID batch shell、4 個一次性 model-bakeoff 分析腳本、PG news tsvector-trigger migration（v1 用 LIKE，FTS5 只給 memory/SA）、codex-CLI deep-research shell（外部 binary + OAuth，繞過 BYOK + 結構化卡契約）。

**RL stack 是唯一被修正的 verdict**：mapping agent 原判 `drop`，違反 hard-lock #5（RL 暫停 = 保留不動、只是不在 v1 UI 出現）→ 改 `defer-v2`，`training/` 程式碼留在 repo 不動，只是不上產品表面。

> **Update 2026-06-03**：agent-facing RL 工具已 **RETIRED**（3 個 `get_rl_*` 從 registry + 兩個 bridge 移除、config 假開關刪除，commits 94861f7+6b49c74）；`src/rl/` + 診斷探針已併入 `training/`（`training/rl/`、`training/research/`）。§5.1 下方 `rl_tools.py` 的 defer-v2 判定**已過時**——agent surface 不再有 RL；`training/`（含研究碼）仍留 repo、離線、defer-v2。

### Verdict 分佈

| Verdict | 數 | 意思 |
|---|---|---|
| `preserve-as-is` | 20 | 幾乎不用改（provider/storage 無關、已是乾淨契約） |
| `preserve-adapt` | 32 | 留 impl 但要 adapt（PG→SQLite、CLI-print→GUI DTO、path→profile dir） |
| `preserve-concept` | 10 | idea 留、impl 重寫（太 CLI/RL-coupled 但概念 load-bearing） |
| `defer-v2` | 8 | 對應 SPEC 已延後功能（KG/backtest/RL/pipeline） |
| `drop` | 7 | pre-pivot cruft / 一次性研究腳本 / 被取代 |
| +補 (§7) | ~10 | review + synthesis 找出漏評的元件 |

---

## 2. 形塑每個 verdict 的 hard locks（精簡）

完整 14 條見 canonical extract；最 load-bearing 的：

1. **PG retired** → v1 只有 SQLite（app state）+ DuckDB（暫時性 OLAP on parquet）。唯一存活的 PG 用途 = 一次性 `migrate_pg_to_local.py` import。PG-coupled ≠ drop，是 **adapt**。
2. **Two-SQLite split**：`workbench.db`（UI/agent 寫）+ `sa_cache.db`（SA native host 專寫）。SA 永不開 `workbench.db` 寫。
3. **FTS5-trigram 強制**：SQLite 無 GIN/tsvector → `agent_memories` + SA body search 用 FTS5 `trigram`（中文可搜，fail-fast probe）。`TEXT[]`→junction table，不用 JSON array。
4. **RL/Phase-D/Phase-C 全 paused = defer 不 drop**：程式碼留 repo 不動，不上 v1 UI。
5. **「what survives unchanged」清單**（replay / 壓縮 / job_runs / SA / macro / tools registry / skills / 記憶工具 / attachments / prompt caching）= 強制保留；周邊儲存/UI 可變，**能力本身留**。
6. **Migration order 鎖死不可壓平**（SPEC §8.1）：research_reports 先 → 跨機 smoke gate → agent_memories → job split → chat_history → SA → news_scores。
7. **DESKTOP_APP_VISION_DRAFT 不是 spec、低於 SPEC**。

---

## 3. 分析工具 carry-over

### 3.1 Analysis pipeline（`src/analysis/`）— 結構化卡契約留、引擎 defer

| 元件 | Verdict | 動作 |
|---|---|---|
| `contracts.py` | **preserve-concept** | 最接近 desktop「結構化 AI 輸出卡」契約。confidence 升為 typed top-level 欄位（綁 §3.2 決策問題）；evidence 加 per-claim citation/traceability（靠 freshness.py）；UI 依賴前先凍結卡契約（vision §9 step4） |
| `integrity.py` | **preserve-concept** | 「render 前保證 confidence+decision 在場」的修復模式留；validator re-point 到正式卡 schema；缺欄位在 GUI 顯式標 low-confidence/unknown，不靜默填 'TBD' |
| `renderer.py` + `templates/` | **preserve-concept** | prose-string → DTO serializer 餵 GUI panel；Markdown variant 只留給 vault/report export；HTML template drop（GUI 取代） |
| `context_builder.py` | **preserve-adapt** | 無直接 PG（全走 DAL）→ 換 backend 透明；確認 SQLite/DuckDB 實作 get_prices/get_news/get_detailed_financials 同 DTO |
| `service.py` | **preserve-adapt** | live 整合 seam（3 callers）；save path re-point SQLite report store；回正式卡 DTO；confidence-label→0.35/0.6/0.8 折進 typed 欄位 |
| `factory.py` / `pipeline.py` / `strategies/` / `scheduler_hooks.py` | **defer-v2** | PHASE_D banner 已標 v2；clean + storage-agnostic 整份留作 v2 分析引擎；strategy base Protocol + degradation 契約是 keeper，真實策略邏輯 v2 重寫 |
| `src/api/routes/analysis.py` | **preserve-adapt** | 回結構化卡 DTO（非 Markdown string 欄位）；feature flag 接 v2 pipeline；DAL 解析 SQLite |
| `cli.py::handle_analyze_command` (`/analyze`) | **preserve-concept** | 只留 dev/test；產品 analyze = GUI 控制打 `/analysis/run` DTO 端點 |

### 3.2 財務資料工具（`src/tools/`）— 撐 evidence 子卡，多數 as-is

| 元件 | Verdict | 動作 / 對應 feature |
|---|---|---|
| `registry.py` (ToolRegistry) | **preserve-as-is** | tool dispatch + provider switcher（同 schema 餵兩個 SDK） |
| `schemas.py` (Pydantic I/O) | **preserve-as-is** | 所有 §5.1 evidence 子卡 + 結構化卡來源資料 |
| `sec_tools.py` | **preserve-as-is** | SEC filings 卡 + insider-trades 卡 |
| `earnings_tools.py` | **preserve-as-is** | earnings 卡（earnings-day move / surprise→reaction / drift） |
| `analyst_tools.py` | **preserve-as-is** | analyst-consensus + 12M 目標價卡 |
| `portfolio_tools.py` | **preserve-as-is** | Portfolio panel（P&L / beta / 相關矩陣 / 集中度） |
| `analysis_tools.py` (fundamentals/evidence) | **preserve-adapt** | SQLite/DuckDB 實作 get/set_financial_cache（sql/005）；IBKR override 腿處理 |
| `data_access.py` (DataAccessLayer) | **preserve-adapt** | **核心 seam**：加 SQLiteBackend + 暫時 DuckDB OLAP 實作 DataBackend Protocol；config 走 profile dir |
| `freshness.py` (FreshnessRegistry) | **preserve-adapt** | 在 SQLiteBackend 實作 query_health_stats()；放寬 DatabaseBackend-only guard。**「真相=資料本身」已落地** |
| `news_tools.py` | **preserve-adapt** | query_news_search/stats 改 DuckDB-over-parquet + LIKE（**非 FTS** — SPEC §4.2 FTS5 只給 memory/SA） |
| `price_tools.py` | **preserve-adapt** | tool body 不動；依賴 DAL price query 移 DuckDB-over-parquet |
| `macro_calendar_tools.py` | **preserve-adapt** | MacroCalendarStore + vintage/revision 表移 SQLite（去 PG `_get_conn`）。FRED 是鎖定 layer-4 源 |
| `web_tools.py::web_browse` (Playwright) | **preserve-as-is** | JS 頁面 web evidence fallback（vendor-neutral 本地 Chromium，無 API key）。*註：review 修正——此項 vision §8.1 並未列，引用更正* |
| `web_tools.py::web_search/web_fetch` (Tavily) | **preserve-concept** | 引入 web-search provider interface（Tavily 為一實作）讓 Local-KB↔Web 切換 |
| `web_tools.py::codex_web_research` | **drop** | 外部 Codex CLI binary + OAuth，繞過 BYOK + 結構化卡契約 |

### 3.3 Signals（`src/signals/`）— 5 模組全留，撐 alert/dashboard

| 元件 | Verdict | 對應 feature |
|---|---|---|
| `anomaly_detector.py` | **preserve-as-is** | research-home「今日異常」panel + ticker signals panel |
| `event_chain.py` | **preserve-as-is** | catalyst chains（引用文章+日期）餵 AI-summary「why」 |
| `event_tagger.py` | **preserve-as-is** | news 列標籤 + event_type 供 event-chain |
| `sector_aggregator.py` | **preserve-as-is** | sector-rotation gauges；sector 定義移 profile config |
| `synthesizer.py` | **preserve-as-is** | ticker AI-summary 卡（action+confidence+risk gauge+factor bars） |
| `signal_tools.py` | **preserve-adapt** | dal.get_news/get_strategy_weights 解析 SQLite+DuckDB；signals 讀進 DAL Protocol |
| `monitor_tools.py::scan_alerts` | **preserve-adapt** | 回結構化 Alert DTO（非只 format_scan_summary 字串） |
| `MULTI_FACTOR_SIGNAL_DETECTION.md` | **preserve-concept** | 重寫 §4 整合（RL pipeline→workbench panels/alert）；retire §5 Dexter framing；factor 定義留 |

---

## 4. 記憶 carry-over

### 4.1 Episodic + reports（`src/tools/` + sql）— priority-map 明列 survives

| 元件 | Verdict | 動作 |
|---|---|---|
| `memory_tools.py` | **preserve-adapt** | re-point SQLiteBackend；PG ts_rank GIN → **FTS5 `trigram`**（§10.2 中文可搜 fail-fast）；對應「記憶/notes browser」(UI page 4, 新 GET /memory) |
| `report_tools.py` | **preserve-adapt** | dal._backend metadata PG→SQLiteBackend；tickers `TEXT[]`+GIN → junction `report_tickers`；對應 Research Records browser (UI page 5) + Markdown vault |
| `sql/003_add_reports.sql` | **preserve-adapt** | 重寫 `sql/sqlite/app/001_research_reports.sql`：INTEGER PK；tickers junction；JSONB→TEXT。**migration cut #1（最先）** |
| `sql/004_add_memories.sql` | **preserve-adapt** | 重寫 `002_agent_memories.sql`：GIN tsvector → `agent_memories_fts` FTS5 trigram。**migration cut #2** |
| `sql/006_add_news_search.sql` | **drop** | PG tsvector-trigger artifact；v1 用 LIKE，未來 news_fts 是全新 SQLite 物件非此 migration |

> **synthesis 自列 gap（記憶語意，非只儲存）**：`memory_tools.py` 只評了 PG→FTS5 儲存遷移，但 agent-side 行為（何時自動存記憶、importance scoring、recall ranking/relevance、expiry policy）—— 即「agent 讀自己累積的知識基質」這個 north star —— **尚未評估為要保留 vs 演進的能力**。這是 v1 設計時要補的一塊（見 §8 open questions）。

### 4.2 Agent 能力 stack（`src/agents/shared/`）— Hermes-parity 層，多數 as-is

| 元件 | Verdict | 動作 / 對應 feature |
|---|---|---|
| `subagent.py` (4 roles) | **preserve-as-is** | Agent Layer task delegation（deep-research/reviewer/summarizer 撐結構化輸出） |
| `bridge_tools.py` | **preserve-as-is** | replay-validator bridge-tool schema 源（遷移安全網） |
| `attachments.py` | **preserve-as-is** | workbench 檔案輸入（拖放 PDF/image/text 進 query/evidence panel） |
| `compressor/` (P1.4) | **preserve-as-is** | Agent Layer 壓縮契約（深層多工具 research run 穩態） |
| `token_tracker.py` | **preserve-as-is** | cost/token 用量指示（per-query + cache-hit） |
| `compressor/overflow_store.py` | **preserve-adapt** | overflow root 解析到 profile device-local scratch（排除 export bundle） |
| `context_manager.py` | **preserve-concept** | should_compact/compact re-host 進 desktop Agent loop（v1 仍 dual-SDK，Phase C paused） |
| `scratchpad.py::Scratchpad` | **preserve-adapt** | base_dir → profile device-local scratch；對應 agent investigation-trace panel |
| `scratchpad.py::ChatHistory` | **preserve-adapt** | _CHAT_HISTORY_DIR → profile dir（synced）；加 DAL/route 讓 GUI history panel 讀 session |
| `skills.py` | **preserve-adapt** | _CUSTOM_DIR/_RESOURCES_DIR 走 Profile Layer（非 repo-relative parents[3]）；對應 **Plugins 卡** |
| `config/skills/*.yaml` + resources/skills | **preserve-adapt** | built-in 隨 app install；custom 移 profile dir 進 export bundle |

---

## 5. 邊界區：RL + options + scoring

### 5.1 RL（agent 工具 **RETIRED** 2026-06；研究碼 defer-v2，已移入 `training/`）

| 元件 | Verdict | 動作 |
|---|---|---|
| `src/tools/rl_tools.py` | **RETIRED 2026-06** | 已刪除（從 registry + 兩個 bridge 移除、config 假開關刪，commit 94861f7）；agent surface 無 RL |
| `training/rl/`（原 `src/rl/`） | **defer-v2（離線）** | 已移入 `training/`（commit 6b49c74）；repo 保留、不上 v1 UI；reactivation gated on RL 線解除暫停 |
| `training/` (PPO/CPPO/SAC/TD3 …) | **defer-v2** | repo 內不動；不上 v1 UI；RL 線復活才回來 |

### 5.2 Options（pricing 數學 as-is，IV/chain 要換資料源）

| 元件 | Verdict | 動作 |
|---|---|---|
| `analysis/option_pricing.py` + `rate_curve.py` | **preserve-as-is** | 純數學；撐 Greeks 計算器 + mispricing scanner + IV panel |
| `options_tools.py::calculate_greeks` | **preserve-as-is** | evidence panel Greeks widget |
| `options_tools.py::get_iv_analysis` / `get_iv_history_data` | **preserve-adapt** | iv_history 源 PG/parquet → DuckDB-on-parquet（tool 邏輯不動） |
| `option_chain_tools.py::get_option_chain` | **preserve-adapt** | 換掉 module-level `_get_ibkr()` singleton → data-layer provider 抽象（無 IBKR gateway 時 graceful degrade） |
| `iv_skew_tools.py::get_iv_skew_analysis` | **preserve-adapt** | 繼承 get_option_chain 的 provider adaptation |
| `options_tools.py::scan_mispricing` | **preserve-adapt** | IV-history 讀 DuckDB/parquet；option_quotes cache 走 provider 抽象 |

> Options 工具全部 `preserve-*`（無 drop）—— 它們對應 vision §5.1 的 volatility/options 子 panel，是 Tier B（exploratory）但有實質實作，留著等 UI 決定要不要曝露。

### 5.3 Scoring & enrichment（live scoring 留、研究腳本砍）

| 元件 | Verdict | 動作 |
|---|---|---|
| scoring read-path (detect/resolve_score_columns, local `news_article_scores`) | **preserve-adapt** | news/sentiment evidence panel；score-dependent reads use SQLite-local scores, not PG `news_scores` |
| `score_ibkr_news.py` | **preserve-adapt** | keep as the Parquet-producing/manual scorer for now; active DB import is `scripts/scoring/import_news_scores_local.py`, not `migrate_to_supabase --scores` |
| `score_sentiment_anthropic.py` + `score_risk_anthropic.py` | **preserve-adapt** | 丟 CSV --input/--output，收斂 parquet + --data-dir；provider switcher 的 Anthropic 後端 |
| `openai_summary.py` | **preserve-adapt** | 解耦 CSV I/O，曝露為 callable enrichment step。*註：review 修正——它 **並未** 被 anthropic scorers import（原 rationale 錯），價值在 summarization-for-evidence，自帶獨立 routing* |
| `sql/002_add_news_scores.sql` | **preserve-adapt** | DDL 移 SQLite（BIGSERIAL→INTEGER PK、TIMESTAMPTZ→TEXT/INTEGER） |
| `validate_scores.py` | **preserve-concept** | 重寫成 parquet/SQLite 上的 post-scoring 驗證步（score∈1..5、coverage%）餵 job_runs/health view |
| `validate_scoring_value.py` | **preserve-concept** | 若 v2 復活：重建在 DuckDB-on-parquet，回結構化 DTO（非 stdout） |
| `sentiment_backtest.py` | **defer-v2** | 對應 SPEC-deferred backtest framework |
| `score_sentiment_openai.py` + `score_risk_openai.py` | **drop** | FNSPID/CSV-only；`score_ibkr_news.py` 已涵蓋 OpenAI on live parquet。⚠️ **action**：drop 會弄壞 `tests/test_scoring_api_routing.py`（直接 import 這兩個 module）— 同步更新/移除該測試 |
| batch `.sh`（risk/sentiment/template） | **drop** | o3/FNSPID batch shell pipeline |
| `detailed_factor_comparison.py` / `analyze_finrl_scores.py` / `ab_summary_comparison.py` | **drop** | 一次性 model-bakeoff 研究腳本（baseline 已存進 SCORING_VALIDATION_METHODOLOGY §五） |

---

## 6. Adversarial review 修正

Review verdict = needs_revision，但 **`false_preserves=[]`、`false_drops=[]`**（無 verdict 錯判）。修正全是 rationale + 補漏：

**Rationale 更正**（verdict 不變，已折進上面各列）：
1. `openai_summary.py` — 宣稱被 anthropic scorers import → **驗證為假**（無人 import，自帶 duplicate routing）。keep 成立但理由改成 summarization-for-evidence。
2. `score_*_openai.py` drop — 「shared routing 在 openai_summary」理由不成立（各自獨立 routing）；且 `tests/test_scoring_api_routing.py` import 這兩個 → **drop 需同步處理該測試**。
3. `web_browse` — 過度引用 vision §8.1（實際未列）→ 引用更正，verdict 不變。

---

## 7. 補上的元件（review + synthesis 找出的 coverage gaps）

mapping 漏評、但屬於範圍內的：

| 元件 | 推定 Verdict | 理由 |
|---|---|---|
| **`code_executor.py` + `code_generator.py`** | **preserve-as-is**（packaging 時 adapt sandbox） | review 抓到的真漏洞。撐 live 註冊的 `execute_python_analysis` tool（registry.py:891）—— agent 的計算/資料分析原語，第一級能力，沙箱 numpy/pandas/scipy。**必須加** |
| `src/monitor/{scheduler,notifiers,discord_bot,dedup}.py` | preserve-adapt（engine 留；scheduler **model** defer SPEC §7；Discord = notifier-only vision §10；alert-mgmt UI 重寫） | 原只評了 watchers+engine。per-module 處置要明示 |
| `src/tools/db_config.py` | preserve-for-import-only | PG-DSN helper；PG retired 後只活在 `migrate_pg_to_local.py` import 路徑（同 LegacyPostgresBackend） |
| `src/tools/sa_tools.py` + `sa_digest_tools.py` | preserve-adapt | SA 是 survives 能力 + hard-lock #3；writer 隔離到 `sa_cache.db`（migration cut #5）。在 SPEC §351 的 8-psycopg2 清單 |
| `model_catalog.py`（model-priority 解析） | preserve-adapt | 撐 in-app provider switcher（vision §8.1）；config model priority → active model |
| `src/tools/backends/{file,db}_backend.py` | DataBackend Protocol 存活+成長 | 新 SQLiteBackend 實作同 Protocol；DatabaseBackend→LegacyPostgresBackend import-only。新 backend 本身是 net-new，不在保留 matrix |

---

## 8. Open questions / 後續 pass

1. **記憶 save/recall 語意演進**（§4.1 gap）：importance scoring / recall ranking / expiry / auto-save 時機 —— 「agent 讀自己知識基質」north star 的實質，v1 設計要決定保留現狀 vs 演進。
2. **chat_history ↔ episodic-memory ↔ reports 統一**：vision draft flag 了 Notes 模組橫跨三者；v1 要決定收斂成單一 notes/lifecycle 物件 vs 維持三個獨立 Markdown vault store。
3. **scheduler model**（A 嵌入 / B daemon / C OS cron）：SPEC §7 只鎖 storage+process interface + 延後 trigger，model 選擇等具體 trigger。
4. **options panel 是否曝露**：工具全留著，但 vision Tier B（exploratory）—— UI 決定要不要做 volatility 子 panel。

---

## 9. 對應鎖定的 migration order（SPEC §8.1）

本 matrix 的 `preserve-adapt` 儲存遷移，**必須照 SPEC §8.1 順序、不可壓平**：

```
cut #1  research_reports (sql/003 → sqlite/app/001)   ← 最先，小且已是檔案
        ↓ 跨機 zip-and-go SMOKE GATE（插在 #1 #2 之間，非最後）
cut #2  agent_memories (sql/004 → +FTS5 trigram +junction)
cut #3  job_definitions / job_runs split
cut #4  chat_history_index
cut #5  sa_articles (+ SA native host psycopg2→SQLite，寫 sa_cache.db)
cut #6  news_scores (sql/002, + DuckDB ATTACH proof)
cut #7  剩餘 SA + macro/cal_* 表
```

kill criterion（cut #1）：zip-and-go 在第二台機器能跑。

---

## 10. Provenance

8-agent map（A 分析 pipeline · B 財務工具 · C signals · D scoring/validation · E 記憶 episodic+reports · F agent 能力 stack · G RL+options · H canonical-intent）→ synthesize（77 元件 matrix，逐 verdict 對 14 hard-locks 校準）→ adversarial review（false_preserves/false_drops 各 0，3 rationale 修正 + 3 coverage gap）。10 agents, ~1.1M tokens。

> 凡與 SPEC 衝突以 SPEC 為準。本文件未 commit（可跟 vision draft 一起過 rename）。
