# Desktop App Vision — Draft (pre-rename handoff)

> **狀態 / Status**: DRAFT — sketch-derived product intent, **NOT a spec**. 本文件捕捉 2026-05 一批桌面 app 草圖（22 頁 PDF + 7 張手繪）背後的設計意圖，作為本地 rename 前的 context handoff。
> **建立日期**: 2026-05-31（由 9-source extract → synthesize → adversarial-review workflow 產生，再人工套用 canonical-lock 修正）
> **權威關係 / Authority**: 凡與 [`LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`](LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md) 衝突處，**一律以 SPEC 為準**。本文件是 SPEC 之上的「UI / UX / 產品表面」意圖層，不重新仲裁 SPEC 已鎖定的架構、儲存、非目標。
> **為什麼存在**: rename 後即使 Claude Code memory 沒搬過去，讀這一份就能接手「桌面 app 想做什麼、哪些舊工具可重用、哪些要重寫、下一步做什麼」。
> **相關文件**: [`LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`](LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md)（架構/儲存/非目標權威）、[`PROJECT_PRIORITY_MAP.md`](PROJECT_PRIORITY_MAP.md)（backlog 排序 + alias mapping）、`ARKSCOPE_RENAME_PHASE2.md`（rename runbook；removed 2026-06-07, see git history + memory project_rename_arkscope.md）、[`PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md`](PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md) / [`PHASE_D_ANALYSIS_PIPELINE_SKETCH.md`](PHASE_D_ANALYSIS_PIPELINE_SKETCH.md)（v2 候選設計）。

---

## 0. 命名警告（先讀）

草圖裡出現多個工作名：**AIRA Desk**、**ARK Desk**、**ArkScope**、vault 路徑 `/AIRA_Research_Vault/`。

PRIORITY_MAP §1 身份：`MindfulRL-Intraday` → `ArkScope` 本地 + code/docs 改名已於 2026-05-31 執行;剩餘小寫 `mindfulrl`(DB/host/addon/歷史文件)刻意保留,且**「do NOT silently introduce a fourth name」**(最終產品品牌名若隨 workbench 定位另改則另議)。

→ **`AIRA Desk` / `ARK Desk` 是草圖階段的探索性 artifact，不是已決定的產品名，也不是可互換的工作名。** 本文件一律用 ArkScope 指稱產品。最終產品名是 open question（見 §7），且**正式改名（rename Phase 2 / P3.2）gated on workbench v1 ship**——不在這次本地 rename 一起做。本地 rename 只搬目錄路徑，不決定品牌。

---

## 1. Vision summary

一個 **local-first、BYOK、no-sign-in 的桌面投資研究工作台**，把三種東西揉在一起：

- **Bloomberg / TradingView 等級的資訊密度**（多面板 cockpit、KPI 條、heatmap、watchlist）
- **結構化、可追溯、有引用的 AI 研究輸出**（固定卡片 schema 取代「買/賣/觀望」式聊天）
- **Obsidian 風格的本地知識持久化**（Markdown vault、筆記、thesis、決策紀錄，zip-and-go 跨機）

產品表面是一個**暗色多面板 cockpit**，使用者在其中把研究物件（ticker、新聞、告警、thesis、筆記）沿著一條明確的 lifecycle 推進，AI 作為**嵌入每一頁的連接組織**而非獨立的 chat tab。

> **架構歸屬**：草圖把後端畫成 4 層（Workbench UI → Decision/Knowledge → Reasoning/LLM → Local Data Cooperation）。這對應 SPEC §1.2 鎖定的 **5 層**（Workbench UI → Agent → Data → **Profile** → **Portability**）——草圖把 Profile + Portability 合併成「Local Cooperation」。**以 SPEC 的 5 層為準。** 桌面 wrapper（Electron/Tauri/任何選擇）依 SPEC §2.1 必須讀同一個 local profile directory，不得自建 DB 或 config 層。

---

## 2. 架構對應（草圖 4 層 → SPEC 5 層）

| 草圖層 (sketch 4) | 對應 SPEC 層 | 本文件補充 |
|---|---|---|
| Workbench UI | 1. Workbench UI | 全新建（見 §8 needs-rewrite）；list-first、右側 detail panel、bulk toolbar、右鍵選單 |
| Decision / Knowledge | 跨 2 (Agent) + 4 (Profile) | lifecycle 狀態機、tags、decision log、thesis、notes vault |
| Reasoning / LLM | 2. Agent Layer | 既有 dual-SDK（OpenAI + Anthropic）+ provider switcher；structured-card 輸出契約 |
| Local Data Cooperation | 3 (Data) + 4 (Profile) + 5 (Portability) | 既有 data_sources/* + DAL；SQLite/DuckDB 遷移（SPEC §8）+ zip-and-go |

**依賴方向**（SPEC 鎖定）：UI 消費 Agent + Data；Agent 消費 Data、讀寫 Profile；Data 住在 Profile；Profile 由 Portability 打包。**禁止向上依賴。**

---

## 3. AI 輸出契約（核心差異化 — 不只是「卡片」）

這是整個產品最有區別性的部分，分三件事：

### 3.1 結構化輸出卡片（固定 schema）

取代自由聊天，每則 AI 結論固定欄位：
> 核心觀察 / 操作建議 / 趨勢預測 / **關鍵點位**（理想入場、次優入場、止損、上方目標）/ 相關資訊 / 數據追溯
>
> 進一步要求欄位：結論 · 主要理由 · **反方理由** · 關鍵假設 · **觸發條件** · **失效條件** · 風險 · 觀察清單 · 資料來源 · 分析時間 · **可信度 / 資料完整度**

### 3.2 決策性問題契約（review 指出 synthesis 漏掉，已補回）

PDF 明列「AI 應能回答的決策性問題」——這定義了輸出何時「有用」，比卡片欄位更上位：

- 我現在的判斷差在哪裡？
- 主要敘事是什麼？市場共識是什麼？
- 失效訊號是什麼？
- 下次該觀察什麼？
- **與上次分析相比，改變了什麼？**（時間軸對比 — 暗示 thesis 需要版本/歷史）

### 3.3 可追溯性 metadata

每則結論宣告：用了哪些資料 · 資料時間點 · 是否即時 · 是否單模型推論 · 新聞/財報/技術指標是否齊備。
> 與 `CLAUDE.md` 既有「只用 reasoning model」政策一致；與既有 `src/tools/freshness.py`（真相來源是資料本身）一致。

---

## 4. 統一研究物件 lifecycle

所有列表型物件（stock/ETF、watchlist item、position、alert、news、research task、note、thesis、AI result）共用**一套狀態機 + 一套動作詞彙 + 一個 priority 欄位 + 一組 tags**。

**通用主 lifecycle**：`Inbox → Watching → Active Research → Owned → Archived → Deleted`

> **重要 nuance（review 指出 synthesis 過度壓平，已修正）**：PDF pp.12-22 其實對不同型別畫了**各自的子狀態**，不該全壓成一條：
> - **News**: New / Important / Linked-to-Thesis / Archived / Ignored
> - **Alert**: Active / **Snoozed** / Triggered / Archived / Deleted
> - **Stock research**: Inbox / Watching / Active Research / **Thesis Built** / Owned / Position Open / Archived / Deleted
>
> → 設計時：共用主 lifecycle + 動作詞彙，但保留 per-type 子狀態（`Snoozed`、`Thesis Built` 等）。

**通用動作**：view / edit / follow(⭐) / tag / note(📝) / move / archive / delete + per-row AI 動作（analyze / summarize / explain / generate note / add to thesis / suggest next step）。

**互動原語**（桌面原生）：列勾選框 → 多選 floating bulk toolbar；右鍵 context menu（同一套 lifecycle 動作）；點任一列 → 右側 detail panel（Overview / Notes / History / Related News / Related Alerts / AI summary / Actions），**不換頁**。

**Soft-delete 模型**：先進 trash；AI 分析 / 研究筆記 / thesis / 決策紀錄預設 **archive-only（不可硬刪）**；bulk delete 需確認；有 archive 過濾視圖。

---

## 5. Feature inventory（按信心分層）

來源代號：`P1`=PDF pp.1-11, `P2`=PDF pp.12-22, `S1`–`S7`=7 張草圖（見 §11 對應）。

### Tier A — Decided & v1-relevant（跨來源、與 SPEC 不衝突）

| Feature | 來源 | 備註 |
|---|---|---|
| 左側 module 導航 rail | P1,P2,S1–S7 | 全草圖一致；底部釘 workspace identity + alert badge |
| Workbench/Overview 作為 home（非 chat 頁） | P2,S1,S2,S3,S6 | 第一屏是密集多面板，明確不是聊天頁 |
| Watchlist（rank/score 欄 + per-row 動作） | P1,P2,S1,S2,S3,S6 | 可排序、star/follow、note、tag、move/archive |
| News feed（per-item AI 摘要 / link-to-thesis） | P1,P2,S1,S2,S6,S7 | 時間戳 + 來源；AI 動作：摘要/判斷影響/歸檔/忽略 |
| Alert Center（價格/技術/新聞/AI 規則 + badge + 歷史） | P1,P2,S3,S4,S6,S7 | 單/多標的、方向（上破/下破）、嚴重級別、觸發歷史、通知測試 |
| 結構化 AI 輸出卡片（§3.1） | P1,S7 | 固定 schema |
| AI 可追溯性 metadata（§3.3） | P1,S7 | |
| 三層 AI 入口 | P1,P2 | L1 全域 Cmd/Ctrl+K + AI 研究頁；L2 per-row inline；L3 多選 bulk |
| Local-only / BYOK / No-sign-in 姿態（頂列 chips） | S2,S4,S7 | 也進 footer 隱私原則 |
| Multi-LLM provider switcher | P1,S4,S5,S7 | **鎖定 4 provider**：OpenAI / Anthropic / OpenAI-compatible / Ollama 本地；per-task 可切 |
| Dark theme 預設 | S1–S7 | 全草圖；light theme 只在 S7 有 sun icon（未畫） |
| 全域 search / command bar（Cmd/Ctrl+K） | P1,S1,S2,S5,S6,S7 | ticker/ETF/公司/主題 + Ask-AI |
| 統一 lifecycle 物件模型（§4） | P2 | |
| 統一 row 動作 + 右鍵 + 多選 bulk toolbar + 右側 detail panel | P2 | 桌面原生 UX 原語 |
| Soft-delete / Archive / Restore / Trash | P2 | AI 分析/筆記/thesis archive-only |
| Note template 欄位 | P2 | 關注理由/風險/催化劑/入場條件/失效條件/下次檢查日 + 提醒 |
| Research records / Reports browser | P1,S7 | 時間過濾（今天/昨天/本週/本月） |
| 右側 Evidence & Data panel（AI 研究頁） | S7 | 見 §5.1 子卡片 |
| AI 研究對話 toolbar | S7 | Copy / Add to note / Export Markdown / Build watchlist + 「已存入本地 vault」 |
| Settings 卡片網格 | S5 | Workspace / Sync & Backup / Model Providers / Language & Region / System / Plugins |
| Sync & Backup 後端（多選） | S5 | Local-Only（預設）/ Git / WebDAV / S3-Compatible / External Folder |
| Telemetry off-by-default / Privacy by Design | S4 | footer 原則 |
| Workbench 快速過濾 chips | P2 | Holdings / Watch / High-priority / Has alerts / Pending research / Has notes / Unread news |
| Workbench 內 tabs | P2 | Market / Portfolio / Watchlist / Monitor / Today's events / AI summary / Research tasks |
| 桌面原生：背景監控 + 系統通知 + tray icon | P1 | 暗示 Electron/Tauri-class shell |
| **桌面原生：多視窗 / 多面板** | P1 | review 補回；web 做不到的差異化 |
| 離線讀歷史分析 | P1,S7 | 與 local-vault-only 一致 |
| Portfolio import（本地呼叫層，CSV/券商匯出） | S4 | **非** 強制 live broker API |

#### 5.1 右側 Evidence & Data 子卡片（S7，review 補回具體欄位）

S7 把右側證據面板畫成幾張**獨立子卡**，不是一坨：
- **價格圖**：1Y / range chart + 期間切換 + 52W 統計
- **財報摘要卡**：FY24 Q1 revenue / net-income / FCF / EPS / op-margin
- **宏觀 & 產業 context 卡**：bullet 形式
- **分析師共識卡**：強力買入 66% / 買入 26% / 持有 7% / 賣出 1%
- **目標價卡**：12 個月目標 $585.24，區間 $440–$650，based on 36 reports

> 另：S7 的 AI 研究頁是**對話氣泡格式**（10:28 user / 10:29 ArkScope + 模型 badge「Claude 3.5 Sonnet」），不是單張報告卡。對話 + 時間戳 + 模型標記 + 下方 toolbar。

### Tier B — Exploratory / 單一來源 / 未決（不要當成已拍板）

> 以下多為單一草圖出現、或來源自己標「待決」、或 inferred-from-visual。**decided=false。**

| Feature | 來源 | 為什麼未決 |
|---|---|---|
| Portfolio summary 卡（value + donut + 績效線 + 持股） | S1,S2,S6 | 資料來源（手動/CSV/IBKR）未定 |
| 市場指數 + 板塊 heatmap 面板 | S1,S2,S6 | 可自訂 vs 固定未定 |
| AI Research 頁最終命名 | P1,P2,S4,S7 | AI Research / Deep Research / Research Workbench 三選一未定 |
| Watch/Follow vs Note 命名 | P2 | Watch Note / Research Note / Attention Note 未定 |
| Markdown + backlinks + Obsidian 相容 vault | P2,S4,S7 | 雙向 sync 語意未定；priority 應降為 secondary |
| 標準模式 vs Terminal 高密度模式切換 | P1 | PDF 自己標「若非高頻交易可能 overkill」 |
| Local-KB vs Web live-search 檢索切換 | P1,S7 | web 後端（Tavily/SerpAPI/Brave/Bocha/SearXNG）未選 |
| Decision Log + Workstream + Thesis Tracking | S4 | 三者邊界未定 |
| 外部通知通道（Webhook/Discord/飛書/企業微信） | P1 | 單一來源、列在 settings 參數；engine 已存在（src/monitor）但非 v1 commit |
| 多資料源（SEC/FRED/Polygon/Alpha Vantage/News API） | S4,S6 | **只有 SEC + FRED 跨來源確認**；其餘單一來源、decided=false |
| 更廣 provider menu（Gemini/Grok/DeepSeek/Moonshot/OpenRouter） | P1 | 超出鎖定 4-provider，aspirational |
| Settings Simple vs Expert 模式 | P1 | 哪些欄位歸哪邊未定 |
| Plugins 卡 | S5 | 第三方安裝範圍未定；skills 系統是天然 host |
| Live ops KPI tiles + status feed | S3 | |
| Background sync worker + last-sync 時間戳 | S7 | 來源是 inferred（看到指示燈推測） |
| 券商交易紀錄匯入（單向） | P1 | 單一來源；SPEC 鎖「informational only，無 live order entry」 |
| Researcher 預設 agent persona（出廠即帶） | S4 | persona-as-shippable-default |
| Agent system（ReAct/multi-agent/event monitor/strategy routing） | P1 | 列為「進階功能」；與鎖定 5 層的關係未架構化 |

### Tier C — SPEC 已 deferred 為 v2（不是這次的目標）

> 這些在草圖出現，但 SPEC §1.4 / §11 已**明確鎖為 v1 非目標**。列在這裡是為了「deferral 是明示的，不是被默默漏掉」。

| Feature | 草圖來源 | SPEC 鎖定 |
|---|---|---|
| 本地知識圖譜（Obsidian 風格 node-link） | S2,S4,S7 | §1.4「Knowledge graph (Phase A — deferred)」；設計在 `PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md` |
| Backtest 模組 UI | P1,S4 | §1.4「Backtest framework UI（DuckDB 存結果但 v1 無 UI surface）」 |
| Algo 模組（sidebar 入口） | P2,S3,S4,S7 | 舊實作已退役；未來能力需重新設計，內部內容未畫 |
| Vector search | — | §1.4 deferred |
| Reasoning-layer 具名能力（Orchestration / Evidence Synthesis / Summarization / Screening Assistant） | S4 | 僅 S4 層圖出現，S4 自己註記「是 layer map 不是 screen」；decided=false |
| Strategy 模組（15 個具名策略） | P1 | PDF 自承「每策略需真實欄位/條件/失效/回測邏輯」是**最大未完成區**；現為 analysis templates 非 declarative spec |

> PDF 列的 15 策略（供未來 spec 用）：通用分析、多頭趨勢、均線金叉、放量突破、熱點題材、縮量回踩、事件驅動、籌碼籌選、成長股、底部放量、頂部重估、波浪理論、龍頭策略、情緒週期、一陽夾三陰。

---

## 6. Sketch-vs-SPEC 張力（必須先解決，否則會默默擴散）

review 對照 canonical docs 找出的衝突，**已逐條對 SPEC 驗證屬實**：

1. **4 層 vs 5 層**：草圖畫 4 層；SPEC §1.2 鎖 5 層。→ 本文件 §2 已重述為「草圖是 5 層的壓平呈現」。
2. **Multi-workspace vs single-profile**：S5 畫多 workspace（各有路徑 + folder picker）；SPEC §3.1 鎖 **單一 profile dir per app instance**（`ProfileLocator.resolve()` 解析一個；`.workbench.lock` per-profile；multi-profile 只是 test/實驗 override）。→ S5 的多 workspace UI 與 SPEC 有張力；若要做，需先改 SPEC 或定義為「切換 = 換 `WORKBENCH_PROFILE_DIR` env」。
3. **品牌名**：見 §0。AIRA/ARK Desk 違反「no fourth name」鎖；rename 本身 gated on v1 ship。
4. **多市場範圍**：S6 watchlist 有國旗欄（暗示非美股）；S4 chip 寫「US Market focused」；P1 資料源含 Tushare/PYTDX（A 股）。→ **直接矛盾**，需定範圍。
5. **Open Source + Pro Sign-in（S2）vs strict No-Sign-in（S4,S7）**：→ 語意（tier？mode？channel？）未定且互相張力。
6. **Real-time order entry**：SPEC §1.4 鎖「informational only」。券商匯入若做，必須是單向、唯讀，不可開 live 下單的門。

---

## 7. Open questions（彙整）

- 最終產品名（gated；§0）
- v1 MVP 頁數：S4 畫 6 tiles（Dashboard/AI Research/News/Alerts/Algo/Notes），MVP rail 只確認 5 又加 Backtest → Alerts / Algo 的 MVP 身分模糊
- Backtest 擺哪：Research 子頁？Algo 子頁？獨立頁？（但 SPEC 已鎖 v1 無 UI → 實務上 = v2）
- AI Research 頁命名、Note 系統命名（見 Tier B）
- Web search 後端選哪家
- 多市場 / 多 provider / 多資料源範圍（見 §6）
- 知識圖譜互通：純視覺 vs 真 Obsidian 雙向 sync
- Plugin 範圍：first-party only vs 第三方 disk/URL 安裝
- KPI tile / 面板：固定 vs 可拖拉自訂
- Sync provider 語意：單目標（radio）vs 多目標 mirror
- Light theme：已決定 vs aspirational
- 底部 status bar 內容（market session / 資料新鮮度 / sync 狀態）
- Settings Simple vs Expert 分界

---

## 8. 可重用 vs 需重寫

> 使用者立場：「最有價值的是我們做的工具，或許有些還能用，但我已看開，大部分工具需要重寫翻新。」以下據此**保守**列。

### 8.1 可重用（具體、與鎖定的層對得上）

**Data Layer（最穩，鎖定資料源直接適用）**
- `data_sources/sec_edgar_*`（financials/source/insider/filings/earnings）— SEC 是鎖定 layer-4 源；XBRL 基本面 + 季報已實作
- `data_sources/fred_client.py` + `src/macro_calendar/fred_ingestion.py` — FRED 鎖定；對應 S7 宏觀卡
- `data_sources/polygon_source.py`、`finnhub_source.py` + `finnhub_calendar_client.py` — 價格 + 新聞/財報日曆
- `data_sources/financial_datasets_client.py` + `financial_metrics_calculator.py` — SEC→FD fallback 鏈，已本地快取，符合 vault 故事

**Tools（右側 Evidence panel 的後端）**
- `src/tools/`：`sec_tools` / `earnings_tools` / `news_tools` / `analyst_tools` / `sa_tools` / `macro_calendar_tools` — 直接對應 §5.1 子卡（價格/財報/新聞/分析師/宏觀）
- `src/tools/report_tools.py` + `data/reports/` — Research Records 列表 + Markdown 報告的現成骨架
- `src/tools/backends/local_capabilities.py` — 明確的本地能力介面，對得上 profile + vault 儲存切分
- `src/tools/freshness.py` — 「真相來源是資料本身」已落地，對應 §3.3 可追溯性

**Agent Layer（reasoning 後端）**
- `src/agents/{anthropic,openai}_agent` + `shared/model_catalog.py` + `token_tracker.py` — dual-provider scaffolding + token 計帳 → provider switcher（OpenAI/Anthropic 鎖定）
- `src/agents/shared/skills.py` + `config/skills/*.yaml` — 對應 Plugins 卡；goal-oriented 設計對上 reasoning 能力
- `src/agents/shared/{attachments,subagent}.py` + `memory_tools.py` — PDF/圖附件 + 4 角色 subagent + episodic memory
- `src/agents/shared/replay.py` + `tests/replay_fixtures/` — **重構安全網**：把 tool dispatch 重切進 5 層時防行為漂移

**Service / Signals / Analysis**
- `src/monitor/`（engine/scheduler/notifiers/watchers/discord_bot）— Alert Center + 背景監控 + Discord 已實作
- `src/service/job_runs_store.py` — 對應 S3 live-ops feed + last-sync 指示
- `src/signals/`（anomaly/event_chain/event_tagger/sector_aggregator/synthesizer）— 餵 S6 gauges + strategy 訊號欄
- `src/analysis/`（context_builder/factory/pipeline/renderer/...）— 對應結構化卡輸出 + scheduler spine（設計見 `PHASE_D_ANALYSIS_PIPELINE_SKETCH.md`）
- `src/api/` + routes — FastAPI sidecar 將本地能力投影為 UI DTO
- `config/user_profile.yaml` — workspace 路徑 / BYOK keys / provider 偏好 / skill 優先序的天然落點

### 8.2 需重寫（預期內，沒關係）

- **整個桌面 shell + UI**：今天不存在。sidebar + 全域 search + KPI 條 + 多面板 grid + 右側 detail panel + bulk toolbar + 右鍵 = 全新建（Electron/Tauri + chart/graph libs）
- **統一 lifecycle 物件 store**：現在是 per-type 表（research_reports/memories/sa_alpha_picks/news_scores），無共用狀態機 + tag + lifecycle 抽象
- **Notes 模組**：Markdown + backlinks + Obsidian 相容 + 雙向連結 + graph 視圖 — report_tools 存報告但非可編輯雙鏈筆記
- **Watch/Follow vs Note 原語 + priority 欄 + tag taxonomy** — 現資料模型沒有
- **互動原語**：右鍵 / 多選 bulk / 右側 detail panel — CLI-only 產品無對應
- **Soft-delete + trash + restore + archive 過濾** — 現無 soft-delete 模型
- **Workspace 概念**（若採多 workspace，先解 §6.2 張力）
- **Sync & Backup 後端**（Git/WebDAV/S3/External mirror）— 目前只有本地 profile 可攜式契約
- **大型分析儲存**（DuckDB 或獨立分析檔）— 僅在現有 SQLite 分工不足時立案
- **Plugin 系統 / 擴充框架** — skills 最接近但非 plugin 契約；install/load/sandbox 待設計
- **Top-bar chips / footer 原則 / dark-mode design system / i18n 字串目錄** — 全新；需完整 design-system pass
- **Alert 規則 UI 層** — engine 在 `src/monitor/` 但管理 UI + alert-as-lifecycle-object 是新的
- **Portfolio import + 顯示**（donut + 線 + 持股 + value）— 今天無 portfolio 模組
- **In-app LLM provider switcher chrome** — dual-agent scaffolding 在但無使用者可見切換器
- **Local-KB vs Web live-search 切換**（segmented control + provider 選擇）— 無 RAG-over-local-vault
- **結構化 AI 卡 schema（含 confidence + traceability）作為通用契約** — 現報告 schema 較自由；需正式 output type + renderer
- **全域 Cmd/Ctrl+K command bar** — 無對應
- **Settings 卡片網格 + Simple/Expert split** — 現只有 YAML
- **背景 monitor daemon → tray icon + OS 通知整合** — monitor 跑 service 但無桌面 tray
- **Strategy 模組（每策略真實欄位/條件/失效/回測）** — PDF 自承最大未完成；現為 analysis templates

---

## 9. Next concrete steps（已對 SPEC 排序修正）

> 修正自 workflow synthesis：(a) 移除「rename 後立刻決定品牌名」——違反 gating；(b)「docs governance cleanup」**已完成**（2026-05 的 5-Group docs consolidation，commits `e6b071c`→`2e920ea`）；(c) 遷移順序改為引用 SPEC §8.1 而非自訂。

1. **（本地 rename 完成後，文件層）對齊命名**：在 MEMORY.md + 草圖層標註 AIRA/ARK Desk 是 sketch artifact、非第四個名字。**不動 repo 品牌**（rename Phase 2 gated on v1 ship）。
2. **鎖 v1 頁面 IA**：把 S4 的 6 tiles、S7 的左 nav、P2 修訂的左 nav 收斂成**一棵**導航樹；明確把 Backtest / Algo / Knowledge Graph defer 到 v2（與 SPEC §1.4 一致）。產出單一 canonical IA 段落（可併入本文件或 SPEC §6 頁 IA）。
3. **設計統一研究物件資料模型**（單一 object table + 狀態機 + tags + lifecycle 動作 + per-type 子狀態），寫 SQLite schema（`workbench.db`）。這是每個 list 視圖 + soft-delete/archive 的前置。
4. **定義結構化 AI 輸出卡契約**（typed schema + renderer + §3.2 決策問題 + §3.3 traceability），retrofit 一個既有工具（如 `report_tools.save_report` 或 analysis pipeline）先吐這個 schema。在 UI 依賴它之前鎖死契約，逼 reasoning 層在邊界 tool-agnostic。
5. **建唯讀 UI skeleton**（暗色 shell + sidebar + 全域 search + 一個 list 視圖 + 一個右側 detail panel）對既有 FastAPI 唯讀端點。**先驗證框架選型**（Electron vs Tauri）、chart libs（線 + donut + heatmap）、右側 panel 模式——用真資料，在 SQLite 遷移之前。
6. **（前 5 步後）開始 SPEC §8.1 鎖定的遷移順序**：`research_reports` 先 → 立即第二機 zip-and-go smoke → `agent_memories` → job_definitions split → chat_history_index → SA 表 → news_scores。**不要**壓平成單一 cut。

---

## 10. 與 RL / 舊定位的關係

- **舊的強化學習實作已退役**。草圖的 Algo nav 入口僅代表未來可能性，內容維持 deferred。
- **OpenClaw 不是 roadmap**；**Discord 只做 notifier / 輕量 command surface**；未來自動化 = ArkScope 自有 local agent + scheduler 優先，external cowork 次之（PRIORITY_MAP §1 clarified 2026-05-25）。
- 本桌面 app 就是「local agent + scheduler + workbench」這條線的**產品表面**。

---

## 11. Source provenance（traceback 用）

原始輸入（2026-05-31，存於使用者 `~/Downloads/`，非 repo 追蹤）：

| 代號 | 檔案 | 內容主軸 |
|---|---|---|
| P1 | `投資研究桌面應用設計.pdf` pp.1–11 | 定位、結構化輸出、雙密度模式、AI 分層入口、桌面原生能力、策略模組、可追溯性 |
| P2 | 同 PDF pp.12–22 | 統一 lifecycle 物件模型、per-type 狀態機、row 動作、bulk、右側 panel、mockup 下一步 |
| S1 | `06ab1f0a-…png` | Dashboard mockup（指數/watchlist/portfolio/news） |
| S2 | `7cc0e8bc-…png` | Dashboard + header 姿態 chips（Open Source / Pro Sign-in）+ KG 提及 |
| S3 | `018356bd-…png` | Ops/monitoring 視圖（KPI tiles + workflow 圖 + alerts） |
| S4 | `690020c5-…png` | **層架構圖（4 層）** + MVP tiles + 資料源 + reasoning 能力 + telemetry |
| S5 | `b47818f8-…png` | Settings 頁（Workspace/Sync/Providers/Language/System/Plugins 卡） |
| S6 | `c43ed97d-…png` | Dashboard 變體（國旗欄 + heatmap + gauges + 資料源 footer） |
| S7 | `df1b8b8d-…png` | **AI Research 頁**（對話氣泡 + evidence 子卡 + vault + local-vs-web 切換） |

> 草圖與 PDF **皆非定稿**。本文件記錄當下意圖，供 rename 後接續；任何此處與 SPEC 衝突，以 SPEC 為準。

---

*產生方式：9-source parallel extract → synthesize → adversarial review workflow（11 agents），review verdict = needs_revision，已人工套用全部 canonical-lock 修正（5-layer、§1.4 非目標、single-profile、rename gating、§8.1 遷移序、per-type 狀態機、決策問題契約、單一來源 decided 降級）後寫成本文件。*
