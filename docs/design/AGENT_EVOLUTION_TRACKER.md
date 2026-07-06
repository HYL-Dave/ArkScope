# Agent 架構演進追蹤

> **Status: HISTORICAL BUILD LOG** — pre-pivot agent-era phases; paths/flows described here predate the local-first pivot.

> **目的**: 追蹤 agent 系統從 MVP 到成熟架構的演進，記錄設計決策與實作狀態
> **創建日期**: 2026-02-08
> **最後更新**: 2026-04-25
> **下一步排序總控**: [PROJECT_PRIORITY_MAP.md](PROJECT_PRIORITY_MAP.md) ← 任何「該做什麼」的問題都先回到這張圖
> **前置文件**:
> - [PROJECT_PRIORITY_MAP.md](PROJECT_PRIORITY_MAP.md) (P0/P1/P2/P3 排序總表 + 訂閱策略 + 依賴圖)
> - [LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md](LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md) (canonical product spec)
> - [AI_AGENT_ARCHITECTURE_PATTERNS.md](AI_AGENT_ARCHITECTURE_PATTERNS.md) (Dexter 模式參考)
> - [SKILL_PLUGINS_RESEARCH.md](SKILL_PLUGINS_RESEARCH.md) (Skills & Plugins 架構研究)
> - [SA_COMMENT_INTELLIGENCE_PLAN.md](SA_COMMENT_INTELLIGENCE_PLAN.md) (SA 留言社群訊號提取規劃)
> - [SA_EXTENSION_ROADMAP.md](SA_EXTENSION_ROADMAP.md) (Seeking Alpha extension 擴充路線)
> - [PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md](PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md) (KG v2 candidate; extracted from retired MAJOR_REFACTORING_PLAN)
> - [PHASE_D_ANALYSIS_PIPELINE_SKETCH.md](PHASE_D_ANALYSIS_PIPELINE_SKETCH.md) (Phase D v2 candidate)
> - [PHASE_C_UNIFIED_RUNNER_SPEC.md](PHASE_C_UNIFIED_RUNNER_SPEC.md) (unified runner, PAUSED)
> - ARKSCOPE_RENAME_PHASE2.md (穩定後的本地遷移清單) (removed 2026-06-07; see git history + memory project_rename_arkscope.md)
> - [RL_COLLAPSE_FINDINGS.md](RL_COLLAPSE_FINDINGS.md) (RL collapse 診斷 + 暫停決策；P3)
>
> **已歸檔**: `archive/` 包含 daily_stock_analysis 借鑑筆記、RL 線暫停前的設計文件、已完成的部署/收集筆記等（見 [archive/README.md](archive/README.md)）

### 文件定位

```
CURRENT_PROJECT_CONTEXT.md          (pointer index — canonical sources of truth)
    │
    ▼
PROJECT_PRIORITY_MAP.md             (排序總表 — P0/P1/P2/P3、訂閱策略、依賴圖)
LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md  (canonical product spec — storage/sync/UI/scheduler)
    │
    ▼ 解釋實作細節時往下展開
AGENT_EVOLUTION_TRACKER.md  ← 本文件 (Agent 當前狀態 + 演進歷史 + 下一步)
    ├── AI_AGENT_ARCHITECTURE_PATTERNS.md (Dexter 設計模式參考)
    ├── SKILL_PLUGINS_RESEARCH.md   (Skills & Plugins 架構研究，Anthropic FSP 分析)
    ├── SA_COMMENT_INTELLIGENCE_PLAN.md (SA 留言社群訊號; P0.3)
    ├── SA_EXTENSION_ROADMAP.md (Seeking Alpha extension 擴充路線)
    ├── PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md (KG v2 candidate; P2.2)
    ├── PHASE_D_ANALYSIS_PIPELINE_SKETCH.md (Phase D v2 candidate; src/analysis/ scaffold)
    ├── PHASE_C_UNIFIED_RUNNER_SPEC.md (unified runner, PAUSED; P2.1)
    ├── MULTI_FACTOR_SIGNAL_DETECTION.md (signals 因子設計; P1.1)
    ├── SA_ALPHA_PICKS_CONTENT_CAPTURE.md (SA Alpha Picks 抓取限制與現況)
    ├── RL_COLLAPSE_FINDINGS.md (RL collapse 診斷 + 暫停決策; P3.1)
    └── ARKSCOPE_RENAME_PHASE2.md (MindfulRL-Intraday → ArkScope 遷移; P3.2)

archive/  (見 archive/README.md — pre-pivot design + RL-phase + deployment notes)
```

> **Retired in docs consolidation (2026-05)**: `MINDFULRL_ARCHITECTURE.md`, `SERVICE_ARCHITECTURE.md`,
> `SERVICE_FIRST_EXPANSION_PLAN.md`, `MAJOR_REFACTORING_PLAN.md`, `DATA_STORAGE_ACCESS.md`,
> `RL_INFERENCE_SERVICE.md`, `ARCHITECTURE_VISION.md`, `NEWS_STORAGE_DESIGN.md`, + 8 scoring/data reports.
> Extracted residuals live in `DATA_SOURCE_QUIRKS.md`, `PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md`,
> `SCORING_VALIDATION_METHODOLOGY.md` §五. Full tracker: [DESIGN_DOCS_CONSOLIDATION_REVIEW.md](DESIGN_DOCS_CONSOLIDATION_REVIEW.md).

**與已歸檔 `AI_AGENT_IMPLEMENTATION_PLAN.md` 的關係**：
- PLAN 是 2026-01 的初始框架選型文件，規劃了 Phase 1-6
- 實際開發走了策略 B (雙軌 SDK)，Phase 1 和 Phase 6 已完成，Phase 2-5 部分跳過
- 本文件接續 PLAN，聚焦在 agent 控制循環的下一步演進（token tracking → scratchpad → context management → streaming → code execution → subagent）

---

## 1. 現狀快照 (2026-03-21)

### 1.1 已完成的基礎設施

| 元件 | 狀態 | 說明 |
|------|------|------|
| Tool Registry | ✅ 成熟 | 50 個 tools（registry）+ delegate_to_subagent = 51 (bridges)，schema export (OpenAI/Anthropic 格式) |
| DataAccessLayer | ✅ 成熟 | FileBackend + DatabaseBackend，config-driven |
| OpenAI Agent | ✅ 可用 | `openai-agents` SDK `Runner.run()`，黑盒 loop |
| Anthropic Agent | ✅ 可用 | 手動 `messages.create()` loop，可見迭代 |
| Config 系統 | ✅ 成熟 | `user_profile.yaml`，model priority 外部化 |
| news_scores 多模型評分 | ✅ 完成 | SQL migration + backend + scoring script |
| HTTP API | ✅ 可用 | FastAPI，代理 agent 查詢 |
| Monitor System | ✅ 成熟 | Discord bot（8 slash commands + 3 Views + free chat），4 Watchers，AlertDeduplicator，MonitorScheduler |
| Shared Model Catalog | ✅ 完成 | `src/agents/shared/model_catalog.py`：4 models（Opus 4.7, Sonnet 4.6, GPT-5.2, GPT-5.2 Codex），CLI + Discord bot 共用 |

### 1.2 設計模式實作狀態

以下為 `AI_AGENT_ARCHITECTURE_PATTERNS.md` 中記錄的 Dexter 模式，標注實作狀態與本專案適用性判斷：

| # | 模式 | 實作狀態 | 本專案適用性 | 備註 |
|---|------|----------|-------------|------|
| 1 | Agent Loop | ✅ 基本 | 核心 | OpenAI SDK 隱藏 loop；Anthropic 顯式 loop |
| 2 | Scratchpad JSONL | ✅ 完成 | 🔴 高 | `scratchpad.py`，整合雙 agent + CLI (`/scratchpad`) |
| 3 | Context Compaction | ✅ 完成 | 🟡 中 | `context_manager.py`，Anthropic loop 整合 |
| 4 | Tool Registry | ✅ 完成 | 核心 | `src/tools/registry.py` |
| 5 | Lazy Init | ⚠️ 部分 | 低 | DAL 每次 query 重建 |
| 6 | Event-driven UI | ✅ 完成 | 🟡 中 | Phase 4: AgentEvent + SSE streaming |
| 7 | Token Budget | ✅ 基本 | 🔴 高 | Phase 1 tracker + Phase 3 threshold |
| 8 | Graceful Exit | ✅ 基本 | 🟡 中 | `/turns` CLI 命令，預設 30，partial results |
| 9 | Skills System | ✅ 完成 | 🟡 中 | 目標導向 workflow，Phase 13 |
| 10 | Context Clearing | ✅ 完成 | 🔴 高 | Phase 3 compact_messages |
| 11 | Subagent Router | ✅ 完成 | 🟡 中 | Phase 6+14: 4 predefined subagents (code_analyst, deep_researcher, data_summarizer, reviewer) + delegate_to_subagent tool |
| 12 | Repository Cache | ❌ 未實作 | 🟢 低 | DAL 有簡單 TTL cache |
| 13 | Prompt Caching | ✅ 完成 | 🟢 低 | Anthropic cache_control + OpenAI auto + TokenTracker |

### 1.3 目前的 Agent 執行流程

```
User query (CLI / Discord / HTTP API)
  → TokenTracker 初始化
  → Single LLM call loop (OpenAI Runner.run() 或 Anthropic messages loop)
    → Tool dispatch (52 tools via registry + delegate_to_subagent; RL tools retired 2026-06)
      → Security wrapping (_serialize_result + XML boundary tags)
      → Direct tool execution → result append to messages
      → Subagent dispatch (4 roles: code_analyst, deep_researcher, data_summarizer, reviewer)
    → ContextManager: should_compact → compact_messages (L1 client-side)
    → Optional: Server-side compaction (L2, Anthropic/OpenAI)
    → Scratchpad JSONL 紀錄
    → Loop until stop_reason != tool_use 或 max_turns
  → Return dict { answer, tools_used, provider, model, token_usage }
  → ChatHistory per-session JSONL + Agent query DB logging
```

**架構演進**: 從初始的 17 tools flat dispatch 演進至完整的 registry-backed tools + 4-subagent 系統，
包含 token tracking、context management (L1+L2)、scratchpad、prompt caching、security wrapping、
skills system、episodic memory、research reports、file attachments、Seeking Alpha Alpha Picks（portfolio + articles + comments）。

**入口點**: CLI (`cli.py`), Discord bot (`discord_bot.py`), HTTP API (`http_api.py`)
- Discord bot 使用 `BotSessionState` + `asyncio.Lock` 管理 model/provider/effort 狀態
- CLI 使用 `SessionState` 管理相同設定

---

## 2. 設計決策記錄

### 2.1 Context Management 策略

**決策日期**: 2026-02-08
**狀態**: 設計確認，待實作

**核心原則（非照搬 Dexter 三層機制）**：

1. **簡單任務保持原樣** — 完整 messages 陣列是最佳做法，不需要 pruning
2. **複雜任務優先分解** — 第一步應考慮如何合理分割成子任務，讓每個子任務的上下文自然足夠
3. **子任務結果即為 compact** — 子任務返回的結果已經是原始資料的精煉，相當於自然的 compaction
4. **Context Clearing 是自動行為** — 不是閾值觸發的機械式清除，而是 agent 判斷哪些舊訊息不再重要：
   - 使用者持續與服務互動時，最初的問題和資訊可能已不重要
   - Agent 建議不再將過時內容放入後續 input
   - 原始資料只要記錄取得方式，可以重新獲取，不必一直放在上下文裡

**與 Dexter 的差異**：

| Dexter 做法 | 本專案做法 | 理由 |
|-------------|-----------|------|
| 超閾值時清除最舊 results | Agent 智慧判斷何時清除 | 機械式清除可能丟失關鍵資料 |
| 完整保留最新 N 個 results | 記錄取得方式，可重新獲取 | 減少上下文膨脹 |
| Token Budget 強制選擇 | 任務分解使每個子上下文自然合理 | 從根本減少問題 |
| 三層機制固定流程 | 依情境彈性選擇 | 金融場景需要靈活性 |

**Input token 計算方式**（跨 provider）：

| Provider | Token 計算 | API 回報 | 備註 |
|----------|-----------|----------|------|
| OpenAI | tiktoken BPE (`o200k_base`) | `usage.prompt_tokens` | 每輪 = system + 全部 messages |
| Anthropic | 自有 tokenizer | `usage.input_tokens` | 每輪 = system + 全部 messages |
| 共通風險 | — | — | 第 N 輪 input ≈ system + 前 N-1 輪所有內容，線性增長 |

### 2.2 Subagent 與跨模型協作

**決策日期**: 2026-02-08
**狀態**: 設計討論中

**使用情境**：
- 主 agent 使用通用模型（如 gpt-5.2）處理查詢
- 發現需要 coding 協助時，dispatch 到 coding 專用模型（如 gpt-5.2-codex）
- 不同模型擅長不同任務，協作可提升整體品質

**框架決策**：

#### Q1: LangChain 統一框架 vs 獨立 SDK？ — ✅ 已決策

**決策 (2026-02-08)**: 維持獨立 SDK 路線，不使用 LangChain。

| 方案 | 優點 | 缺點 |
|------|------|------|
| ~~LangChain~~ | 統一 API 跨 provider；LangGraph 狀態管理 | 抽象層重，debug 困難；無法使用各 SDK 獨特功能 |
| **獨立 SDK + 自建 dispatch** ✅ | 可用各 SDK 最強功能（Handoff, Skills）| 需自己處理跨 provider 訊息格式轉換 |

**理由**：
- 現有 `src/agents/` 已走獨立 SDK 路線，轉 LangChain 需全部重寫
- 獨立 SDK 可使用各 provider 的原生功能（OpenAI Handoff、Anthropic cache_control 等）
- 跨 provider dispatch 通過結構化 JSON 結果傳遞，不需要 LangChain 的統一抽象

**保留彈性**：若未來 LangChain 能完全取代兩個原生 SDK 且功能更完善，可重新評估。

#### Q2: 跨 Provider 記憶如何同步？ — ✅ 已決策

**決策**：Subagent 之間只傳遞結構化的任務結果（JSON），不傳遞對話歷史。

各 provider 的 messages 格式不同（OpenAI 用 `tool_calls`，Anthropic 用 `tool_use`），
直接傳遞完整對話歷史不可行。

**具體做法**：
- 每個 subagent 從 clean state 開始
- 接收：任務描述（text）+ 必要上下文（JSON data）
- 返回：結構化結果（JSON）
- 主 agent 收到結果後整合到自己的 context 中

### 2.3 Dynamic Code Generation

**決策日期**: 2026-02-08
**狀態**: 設計討論中

**兩條路線**：

| 路線 | 描述 | 複雜度 | 優點 | 缺點 |
|------|------|--------|------|------|
| **A: 內部 tool** | 加 `execute_python` tool | 低 | 簡單整合，agent 自主決定 | 安全性需 sandbox；agent 可能寫 buggy code |
| **B: Code subagent** | 專用 coding subagent | 高 | 隔離性好，可用專門模型 | 需先實作 subagent pattern |

**暫定決策**：先走路線 A（簡單），在 subagent pattern 成熟後可切換到路線 B。
兩者都需要 Python sandbox：

```
最簡方案: subprocess + timeout + resource limits
進階方案: Docker container / Pyodide / RestrictedPython
```

> **待驗證**：路線 A 和 B 的效果對比缺乏實證，先實作 A 收集經驗。

### 2.4 外部參考：Beads 專案的借鑒

**調研日期**: 2026-02-08
**來源**: [steveyegge/beads](https://github.com/steveyegge/beads) — 分散式 git-backed 圖形化 issue tracker，專為 AI coding agents 設計

**決策：不直接整合**，原因：
- Beads 是 Go CLI 工具，解決的是跨 session 多天任務追蹤（issue tracking），而非單次查詢的 context management
- Daemon 進程、git sync、multi-repo 支援等功能超出我們的需求
- 增加外部依賴複雜度（npm/brew/go install）

**Beads 核心架構**（供參考）：

```
CLI (bd create/ready/update)
  → SQLite (.beads/beads.db, gitignored, 快速查詢)
    → JSONL (.beads/issues.jsonl, git-tracked, 真實來源)
```

關鍵概念：
- **Molecule (Mol)**: 持久的工作單元（sync 到 git）
- **Wisp**: 短暫任務實例（不 sync，用完即丟）
- **Squash**: 將 wisp 壓縮為永久 digest（保留結論，丟棄過程）
- **bd prime**: 注入 ~1-2k tokens 的 workflow context 到 agent（而非載入完整歷史）

**借鑒模式（已納入 Phase 2-3 設計）**：

| Beads 模式 | 應用到的 Phase | 具體做法 |
|-----------|---------------|---------|
| JSONL + SQLite 雙層 | Phase 2 (Scratchpad) | JSONL 為主寫入，未來可加 SQLite 做歷史查詢 |
| Ephemeral / Persistent 區分 | Phase 3 (Context Mgmt) | tool results 標為 ephemeral（可重取），分析結論標為 persistent |
| Squash → Digest | Phase 3 (Context Clearing) | 舊 context 壓縮為摘要 + 取得方式（tool name + params） |
| bd prime 最小注入 | 未來 Session 管理 | Agent 啟動時注入前次 session digest，不載入完整歷史 |
| Hash-based ID | Phase 2 (Scratchpad) | 用 content hash 而非 sequential ID，便於跨 session 引用 |

---

## 3. 實作路線圖

> **順序確認日期**: 2026-02-08 (Phase 1-6), 2026-02-15 (Phase 7-15)
> **已完成**: Phase 0-15 全部 ✅ + Phase A/B/C/D/E/F ✅ + Prompt Caching ✅ + Custom Skills ✅ + Financial Datasets API ✅ + Monitor Phase 1-3 ✅ + Monitor Batch A/B ✅ + Shared Model Catalog ✅ + Observability Batch ✅ + RL Phase 1c ✅ + RL Phase 1a+1b ✅ + 多輪 Bug Fix ✅
> **待完成**: RL Phase 1d (推論) → 11d (Unusual Whales, 待訂閱) → **Phase G (Skills 升級)** → Vector Embeddings Pipeline → 多頻道 Gateway
> **框架**: 獨立 SDK (OpenAI + Anthropic)，不使用 LangChain

### 後續能力掛點

- `SA Comment Intelligence`
  - 見 [SA_COMMENT_INTELLIGENCE_PLAN.md](SA_COMMENT_INTELLIGENCE_PLAN.md)
  - 定位為上層 domain feature，不併入 Context / Runner 主線 phase
  - 可在 Unified Runner / Analysis Pipeline 穩定後，作為社群訊號層接入

### Phase 0: 基礎設施 (已完成)

- [x] Tool Registry (44 tools, schema export)
- [x] DataAccessLayer (FileBackend + DatabaseBackend)
- [x] OpenAI Agent (Runner.run)
- [x] Anthropic Agent (messages loop)
- [x] Config 系統 (user_profile.yaml)
- [x] news_scores 多模型評分 (SQL + backends + scoring)
- [x] HTTP API (FastAPI)

### Phase 1: Token Tracking — ✅ 完成

**目標**: 知道每次 API call 消耗了多少 tokens，為 context management 提供依據
**優先級**: 🔴 高（所有 context management 的前置條件）
**實際**: ~120 LOC (token_tracker.py) + agent 整合
**狀態**: ✅ 完成 (2026-02-08)

**實作要點**：
- [x] 從 API response 提取 `usage` (input_tokens, output_tokens)
- [x] 累計追蹤整個 session 的 token 消耗
- [x] 每輪 loop 記錄 token 使用量 + `last_input_tokens` (context 增長指標)
- [x] 支援 OpenAI 和 Anthropic 兩種 usage 格式 (含 prompt_tokens fallback)
- [x] `token_usage` summary 加入 agent response dict
- [x] 19 個單元測試通過

**檔案**：
- `src/agents/shared/token_tracker.py` — `TokenTracker`, `TurnUsage`
- `src/agents/anthropic_agent/agent.py` — 每輪 `record_anthropic(response)`
- `src/agents/openai_agent/agent.py` — 結束後 `record_openai_result(result)`
- `tests/test_token_tracker.py` — 19 tests

### Phase 2: Scratchpad — ✅ 完成

**目標**: JSONL 格式記錄 agent 每次執行的決策過程
**優先級**: 🔴 高（決策審計、crash recovery）
**預估**: ~200 LOC → 實際 ~180 LOC
**狀態**: ✅ 完成

**實作要點**：
- [x] JSONL 檔案：`data/agent_scratchpad/YYYY-MM-DD-HHMMSS_{session_hash}.jsonl`
- [x] 記錄事件類型：`init`, `tool_call`, `tool_result`, `final_answer`, `max_turns`
- [x] 每個事件包含 seq, timestamp, session ID, data, token_usage
- [x] Append-only 寫入 + 即時 flush（crash-safe）
- [x] 整合到 Anthropic agent loop（per-turn: tool_call + tool_result）
- [x] 整合到 OpenAI agent（post-run: 從 raw_responses 提取 tool calls + final_answer）
- [x] Hash-based session ID（sha256[:8]，借鑒 Beads）
- [x] `_safe_serialize()` 處理非 JSON 類型
- [x] `read_scratchpad()` 讀取歷史記錄
- [x] Context manager (`with Scratchpad(...) as pad:`)
- [x] `enabled=False` 可完全禁用

**檔案**：
- `src/agents/shared/scratchpad.py` — 新建（~180 LOC）
- `src/agents/anthropic_agent/agent.py` — 整合 pad.log_tool_call/result/final_answer/max_turns
- `src/agents/openai_agent/agent.py` — 整合 pad（async + sync 兩個入口）
- `src/agents/shared/__init__.py` — export Scratchpad
- `tests/test_scratchpad.py` — 32 tests

### Phase 3: Context Management — ✅ 完成

**目標**: 根據 §2.1 設計決策實作智慧 context 管理
**優先級**: 🔴 高
**預估**: ~200 LOC → 實際 ~190 LOC
**狀態**: ✅ 完成

**實作要點**：
- [x] Token 閾值監控（基於 Phase 1 的 tracker.last_input_tokens）
- [x] Heuristic 判斷：input_tokens > model_context_limit * 0.4 且 turns > keep_recent
- [x] 清除策略：記錄 tool name + params + preview，丟棄原始大量內容
- [x] Ephemeral/Persistent 區分（借鑒 Beads）：
  - Ephemeral: tool results → 壓縮為 `[Compacted] tool(params) → N chars. Preview: ...`
  - Persistent: user question + assistant text → 完整保留
- [x] Squash 機制：`_build_compact_summary()` 保留取得方式 + 內容預覽
- [x] 保留最近 N 輪完整結果（預設 keep_recent_turns=2）
- [x] 整合到 Anthropic agent loop — `agent.py` `run_query_stream()`（每輪結束後檢查）
- [x] CLI 路徑已整合 — `cli.py` `run_anthropic_interactive()` 加入 ContextManager + L1 compaction
- [x] 已壓縮的結果不會重複壓縮（`_COMPACT_MARKER` 檢查）
- [x] 簡單查詢不觸發（turns ≤ keep_recent 時直接跳過）
- [x] OpenAI agent 不受影響（SDK 黑盒，無法中途 compact）

**設計特點**：
- 不是機械式閾值清除 — 只壓縮 ephemeral 內容，persistent 永遠保留
- 模型感知：自動查詢模型上下文限制（Claude 200K, GPT 400K）
- 可配置：threshold_ratio, keep_recent_turns, preview_chars 皆可調

**檔案**：
- `src/agents/shared/context_manager.py` — 新建（~190 LOC）
- `src/agents/anthropic_agent/agent.py` — 整合 ctx.should_compact + compact_messages
- `src/agents/shared/__init__.py` — export ContextManager
- `tests/test_context_manager.py` — 40 tests

### Phase 4: AsyncGenerator Event Streaming — ✅ 完成

**目標**: 改 return dict 為 yield events，支援中間進度回報
**優先級**: 🟡 中
**預估**: ~150 LOC → 實際 ~240 LOC
**狀態**: ✅ 完成 (2026-02-09)

**實作要點**：
- [x] 定義 event types: `thinking`, `text`, `tool_start`, `tool_end`, `error`, `done`
- [x] Anthropic agent 新增 `async def run_query_stream() -> AsyncGenerator[AgentEvent, None]`，5 個 yield 點
- [x] 原有 `run_query()` 改為 wrapper（收集 events 返回 dict，完全向後相容）
- [x] OpenAI agent 新增 `run_query_stream()`（前/後包裝，SDK 黑盒限制）
- [x] HTTP API 新增 `POST /query/stream` SSE 端點（`StreamingResponse`）
- [x] 向後相容：`run_query()`, `run_query_sync()`, `POST /query` 簽名不變
- [x] 14 個單元測試通過（EventType, AgentEvent, stream 序列, backward compat, SSE endpoint）

**檔案**：
- `src/agents/shared/events.py` — 新建 `EventType` enum + `AgentEvent` dataclass (~55 LOC)
- `src/agents/shared/__init__.py` — export AgentEvent, EventType
- `src/agents/anthropic_agent/agent.py` — 新增 `run_query_stream()`，`run_query()` 改為 wrapper
- `src/agents/openai_agent/agent.py` — 新增 `run_query_stream()`
- `src/api/routes/query.py` — 新增 `POST /query/stream` SSE 端點
- `tests/test_events.py` — 14 tests

### Phase 5: Code Execution Tool

**目標**: Agent 可即時撰寫 Python 分析代碼並執行
**優先級**: 🟡 中
**狀態**: ✅ 完成 (2026-02-11)

**實作內容**：
- [x] `execute_python_analysis` tool — subprocess 隔離執行 agent 生成的 Python
- [x] Blocklist 模組安全管控（os, sys, subprocess, socket, http 等）
- [x] 雙層防禦：AST 靜態檢查 + subprocess 隔離 + timeout
- [x] Data 注入機制：`data_json` → stdin → `data` 變數
- [x] 預設 120s timeout，可配置
- [x] Background 模式：Popen 非阻塞，結果寫 temp 檔
- [x] 18th tool 整合：Registry + Anthropic bridge + OpenAI bridge
- [x] 36 tests (validate_code, execute, background, serialization)

**檔案**：
- `src/tools/code_executor.py` — 新建（核心執行器 ~200 LOC）
- `src/tools/registry.py` — 註冊 `execute_python_analysis`
- `src/agents/anthropic_agent/tools.py` — schema + dispatch
- `src/agents/openai_agent/tools.py` — @function_tool wrapper
- `src/agents/shared/prompts.py` — system prompt 更新
- `tests/test_code_executor.py` — 36 tests

### Phase 5b: Code Generation Agent

**目標**: 指定 coding 專用模型生成 + 自動修正 Python 分析代碼
**優先級**: 🔴 高（Phase 5 的延伸）
**狀態**: ✅ 完成 (2026-02-11)

**核心設計：Error-Correcting Code Agent Loop**

```
task → code_model 生成 code → AST 驗證 → subprocess 執行 → 成功? → 回傳結果
                                                           ↓ 失敗
                                              把 error + code 回傳給 code_model
                                                           ↓
                                              code_model 修正 → 重新執行 (max N retries)
```

**設計決策**：
- `code_model` 可配置（config + CLI `/code-model`），獨立於主 agent 模型
- Provider 從 model name 自動偵測（gpt-* → OpenAI, claude-* → Anthropic）
- Tool 加 `task` 參數：`execute_python_analysis(task="計算相關性")` → 內部用 code_model 生成 code
- LLM conversation 保留 context（前一次的 code + error），讓 model 精準修正
- 自動 strip markdown code blocks（LLM 有時包 ` ```python `）
- MODEL_CATALOG 加入 Codex 系列：`gpt-5.2-codex`（已發布）、`gpt-5.3-codex`（API phased rollout）
- Code gen 一律給模型最大 output（OpenAI 128K / Anthropic 128K or 64K），reasoning/thinking tokens 從中扣
- 移除 `config.temperature` 死欄位（定義但全 codebase 無人讀取，各 agent 自行 hardcode 0.0）
- ⚠️ **Token 上限風險**: Anthropic non-streaming + 大 `max_tokens`（如 128K）理論上可能觸發 server HTTP timeout。實務上 code gen output 遠小於上限，且可透過加長 HTTP/後端逾時設定降低風險。若未來遇到 timeout，改用 streaming 即可解決。

**實作內容**：
- [x] `src/tools/code_generator.py` — code gen + retry loop (~200 LOC)
- [x] `src/tools/code_executor.py` — 加 `task` 參數 + `generated_code` field，委派到 code_generator
- [x] `src/agents/config.py` — 加 `code_model`, `code_max_retries`
- [x] `src/agents/cli.py` — `/code-model` 互動選擇指令 + Codex models in MODEL_CATALOG
- [x] Registry + Agent bridges — 加 `task` 參數（Anthropic schema + dispatch, OpenAI @function_tool）
- [x] `src/agents/openai_agent/agent.py` — `_OPENAI_MODEL_MAX_OUTPUT` 加入 Codex 系列
- [x] `tests/test_code_generator.py` — 27 tests (provider detect, code extract, mock LLM retry, task mode)

**檔案**：
- `src/tools/code_generator.py` — 新建（~200 LOC）
- `src/tools/code_executor.py` — 修改（task 參數 + generated_code field）
- `src/agents/config.py` — 修改（code_model + code_max_retries）
- `src/agents/cli.py` — 修改（/code-model, MODEL_CATALOG + Codex entries）
- `src/agents/openai_agent/agent.py` — 修改（Codex max output mapping）
- `src/agents/anthropic_agent/tools.py` — 修改（task schema + dispatch）
- `src/agents/openai_agent/tools.py` — 修改（task parameter）
- `src/tools/registry.py` — 修改（task 參數 + description 更新）
- `tests/test_code_generator.py` — 新建（27 tests）
- `tests/test_tools.py` — 修改（17→18 count）

### Phase 6: Subagent Pattern + 1M Context Beta

**目標**: 主 agent 可 dispatch 子任務到專門的 subagent；支援 Anthropic 1M context beta
**優先級**: 🟡 中（依賴 Phase 1-3）
**預估**: ~290 LOC（subagent.py）+ bridge/config/cli 修改
**狀態**: ✅ 完成（2026-02-13）

**實作要點**：
- [x] SubagentConfig dataclass：model + system prompt + tool_names + reasoning config
- [x] 主 agent 通過 `delegate_to_subagent` tool（#19）觸發
- [x] Subagent 之間只傳遞結構化結果（JSON），不傳對話歷史
- [x] 支援跨 provider dispatch（_detect_provider() 自動路由）
- [x] 預定義 3 subagents（Phase 14 擴充為 4）：
  - `code_analyst` — gpt-5.2-codex reasoning=xhigh（量化計算，Phase 14 合併 programmer）
  - `deep_researcher` — gpt-5.2 reasoning=xhigh（多源深度調查）
  - `data_summarizer` — claude-sonnet-4-6 + adaptive thinking（快速摘要，Phase 14 降成本 40%）
  - `reviewer` — claude-opus-4-7 thinking+max（對抗性審查，Phase 14 新增）
- [x] 1M context beta：`betas=["context-1m-2025-08-07"]`，Opus 4.7 + Sonnet 4.6
- [x] CLI `/context` 切換命令
- [x] 42 unit tests (all pass)

**檔案**：
- `src/agents/shared/subagent.py` — 新建（~290 LOC，核心模組）
- `src/agents/anthropic_agent/tools.py` — 修改（schema + dispatch entry）
- `src/agents/openai_agent/tools.py` — 修改（@function_tool + list）
- `src/agents/shared/prompts.py` — 修改（SUBAGENT DELEGATION section）
- `src/agents/shared/__init__.py` — 修改（export 新 symbols）
- `src/agents/config.py` — 修改（extended_context field + profile loading）
- `src/agents/anthropic_agent/agent.py` — 修改（1M beta stream）
- `src/agents/cli.py` — 修改（/context 命令 + beta stream in interactive loop）
- `tests/test_subagent.py` — 新建（42 tests）

**已決策**（見 §2.2）：
- ✅ 使用獨立 SDK + 自建 dispatch（不用 LangChain / OpenAI Handoff）
- ✅ 跨 provider 只傳結構化 JSON 結果，不傳對話歷史
- ✅ 遞迴防護：無 subagent 含 delegate_to_subagent tool
- ✅ 1M context 為 opt-in（config + CLI toggle），預設 off

---

### Phase 7: Context Management — Server-Side Compaction + OpenAI Overflow 修復

**目標**: 整合 server-side compaction API + 解決 OpenAI context overflow 問題
**優先級**: 🔴 高（OpenAI overflow 為生產級 bug）
**預估**: ~400 LOC
**狀態**: ✅ 7a + 7b 已完成

#### 7a: Server-Side Compaction ✅ 已完成（2026-02-16）

**研究結論** (2026-02-09)：
- Claude: `compact-2026-01-12` beta，僅 Opus 4.7，API 內 `context_management` 參數
- OpenAI: `OpenAIResponsesCompactionSession` (agents SDK 0.7.0 GA)，wrap session 自動壓縮
- LangChain: 全部 client-side（trim_messages, summarization node, Deep Agents offloading）
- Dexter: client-side 3 層（chat history relevance selection, scratchpad clearing, token budget）
- 詳見 `memory/compaction_research.md`

**雙層架構**：
- L1 (Phase 3, 已有): `ContextManager` — 免費、任何模型、tool_result 替換 (threshold ~140K for 200K models)
- L2 (Phase 7a, 新增): Server-side — 模型語意摘要、品質高、需額外 token

**實作內容** (2026-02-16)：
- `src/agents/config.py`: `server_compaction: bool = False` — 預設關閉，需明確啟用
- **Anthropic**: beta header `compact-2026-01-12` + `context_management={"edits": [{"type": "compact_20260112"}]}` + `stop_reason == "compaction"` 處理（Opus 4.7 only）
- **OpenAI**: `_make_compaction_session()` → `OpenAIResponsesCompactionSession`，傳入 `Runner.run(session=...)` 的 3 處調用
- CLI: `/compaction` (`/cmp`) toggle 命令，顯示 Anthropic + OpenAI 兩者狀態
- `tests/test_server_compaction.py`: 13 tests（config defaults, model support, session fallback, YAML propagation）
- 全量回歸 372 tests 通過

#### 7b: OpenAI Context Overflow 修復（2026-02-15 新增）

**問題描述**：
GPT-5.2 (400K context) 在複雜多 tool 查詢中拋 `context_length_exceeded`，
而 Opus 4.7 (200K context) 在相同查詢下成功完成（52 tool calls, 341.6s）。
兩者都未觸發 compaction（Phase 3 ContextManager 僅限 Anthropic path）。

**實測數據** (2026-02-15)：
- 查詢：「調查我追蹤的股票中，哪一個目前最有進場的潛力，需要數據輔助」
- GPT-5.2 xhigh: `Error 400 context_length_exceeded`（scratchpad 僅有 init event，零 tool calls）
- Opus 4.7 adaptive+max: 成功，52 tool calls，total tool results ~55K chars (~14K tokens)

**排除的假設**：
- ~~Compaction 差異~~：Opus 也沒用到 compact（total data 遠低於 threshold）
- ~~工具定義過大~~：19 tools ~10.8K chars (~2.7K tokens)
- ~~System prompt 過大~~：4,917 chars (~1,229 tokens)

**真正的根因（待深入驗證）**：
1. **GPT-5.2 行為差異** — 可能每輪產生更多 tool calls / 更冗長的 reasoning tokens
2. **OpenAI Responses API 格式開銷** — `Runner.run()` 將 `original_input + all generated_items` 每輪重送，格式開銷可能遠大於 Anthropic
3. **SDK 未用功能** — `openai-agents` SDK 有以下功能我們完全未使用：
   - `auto_previous_response_id=True` — 讓 API 自動引用前次 response，避免重送完整歷史
   - `OpenAIResponsesCompactionSession` — SDK 內建 session compaction
   - `SQLiteSession` — 持久化 session state
4. **零 debug 可見性** — `Runner.run()` 失敗時，scratchpad 無法記錄任何中間狀態

**修復方向**：
- [x] **DEBUG 層**: `logger.debug()` pre-run/post-run/post-extraction 結構化日誌（2026-03-01）
- [x] **auto_previous_response_id**: 已啟用於全部 4 個 `Runner.run()` 調用（2026-02-15），修復 context_length_exceeded
- [x] **OpenAIResponsesCompactionSession**: 已整合（Phase 7a），`_make_compaction_session()` 可用
- [x] **Scratchpad 容錯**: `_extract_tool_info()` 共用 helper + call_id mapping + retry/error logging（2026-03-01）

**LangChain 替代方案**：
用戶問「把 openai-agents 換成 LangChain 能解決嗎？」
- LangChain 的 context management 全部是 client-side（trim_messages, summarization node）
- 它不會自動解決 overflow，但提供更多手動控制的 hook
- **暫不遷移**：先嘗試 SDK 內建功能（auto_previous_response_id + CompactionSession），成本更低
- 若 SDK 方案無效，再評估 LangChain 或直接調用 OpenAI Responses API

**實際修改檔案** (7a + 7b)：
- [x] `src/agents/config.py` — `server_compaction: bool = False` + YAML 載入
- [x] `src/agents/anthropic_agent/agent.py` — `_COMPACTION_BETA`, `_supports_compaction()`, beta header + `context_management` + `stop_reason=="compaction"` 處理
- [x] `src/agents/openai_agent/agent.py` — `_make_compaction_session()` + 3 處 `Runner.run()` 加入 `session=` param + `auto_previous_response_id=True` (Phase 7b)
- [x] `src/agents/cli.py` — `/compaction` (`/cmp`) toggle + status line + config 傳播
- [x] `tests/test_server_compaction.py` — 13 tests
- [x] 預設關閉（向後相容）
- 注：未建獨立 `server_compaction.py` helper 模組（邏輯足夠簡單，直接寫在各 agent.py 中）

---

### Phase 8: Anthropic Effort + Adaptive Thinking — ✅ 完成

**目標**: 整合 Anthropic `effort` 參數和 `extended thinking`，讓 Anthropic agent 也有推理控制能力
**優先級**: 🟢 低（功能增強）
**預估**: ~230 LOC
**狀態**: ✅ 完成 (2026-02-09)

**模型支援矩陣**：

| 模型 | Thinking 模式 | Effort |
|------|-------------|--------|
| Opus 4.7 | `adaptive` | `max`/`high`/`medium`/`low` |
| Sonnet 4.6 | `adaptive` | `high`/`medium`/`low` |

> 注：Opus 4.5, Sonnet 4.5, Haiku 4.5 已棄用（2026-02-16 更新至 4.6 系列）

**設計決策**：
- `max_tokens` 和 `budget_tokens` 全自動推導，不設為 config
- `_MODEL_MAX_OUTPUT` mapping: Opus 4.7=128K, 其他=64K
- thinking 開啟 → `effective_max_tokens` = 模型最大 output
- `budget_tokens` = model_max_output - config.max_tokens（留 max_tokens 給 response）
- Adaptive 模式 (Opus 4.7) 不需 budget，Claude 自動調配
- 只需 2 個設定：`anthropic_effort` + `anthropic_thinking`

**實作內容**：
- [x] `src/agents/config.py` — 2 個新設定欄位 + `user_profile.yaml` loading
- [x] `src/agents/anthropic_agent/agent.py` — `_MODEL_MAX_OUTPUT`, `_build_thinking_param()` 自動推導、effort/thinking kwargs
- [x] `src/agents/shared/events.py` — `EventType.thinking_content` 新事件
- [x] `src/agents/cli.py` — `/effort`、`/thinking` 命令、`--effort`/`--thinking` CLI 參數、status line 顯示
- [x] `config/user_profile.yaml` — 設定文檔（預設註解掉）
- [x] 測試：20 tests (test_events) + 21 tests (test_agents)

---

### Phase 9: Analysis Depth — System Prompt 重寫

**目標**: 讓 agent 的分析從「表面綜合」進化到「批判性深度分析」
**優先級**: 🔴 高（直接影響分析品質）
**預估**: ~100 LOC（prompt 重寫 + 測試驗證）
**狀態**: ✅ 完成（2026-02-12）

**問題診斷**（2026-02-12 實測）：
- Agent 推薦 PYPL（P/E=11.9, 跌 27%），但沒問「為什麼便宜/為什麼跌」
- 沒有做 adversarial analysis（找反面證據否定結論）
- 沒有揭露 data gaps（SEC 數據空、缺少分析師共識、缺少事件背景）
- 沒有主動觸發 `execute_python_analysis(task=...)` 做量化驗證
- code_model 從未被使用過（因為 prompt 沒有引導）

**實作內容**：
- [x] `src/agents/shared/prompts.py` — 重寫 `SYSTEM_PROMPT`（5 區塊結構）
  - Role + Context（角色 + 工具分類概覽）
  - Analysis Framework（5 步分析框架：收集 → 假設 → 反證 → 缺口 → 信心度）
  - Critical Thinking Rules（value trap 警示、大跌必有原因、證據 vs 無反證的區別）
  - Tool Usage Guide（引導使用 `execute_python_analysis(task=...)` 做量化計算）
  - Output Standards（每次分析需含：數據來源、關鍵發現、反面論點、數據缺口、信心等級）
- [x] 移除未使用的 `SYSTEM_PROMPT_SYNTHESIS`
- [ ] 手動 A/B 測試：同樣問題，比較新舊 prompt 的回答品質

---

### Phase 10: Web Search — Agent 即時搜尋能力 — ✅ 完成

**目標**: 讓 agent 能即時搜尋網路驗證結論、查找最新新聞和分析師觀點
**優先級**: 🔴 高（解決「不知道為什麼 PYPL 跌了 27%」的根本問題）
**預估**: ~200 LOC → 實際 ~1084 LOC（含測試）
**狀態**: ✅ 完成 (2026-02-15)

**4 種搜尋提供者**（各自獨立開關）：

| 提供者 | 類型 | 適用 Agent | 工具名 | 費用 |
|--------|------|-----------|--------|------|
| **Tavily** | 自訂工具 | 兩者皆可 | `tavily_search`, `tavily_fetch` | 免費 1000 credits/月 |
| **Claude Web Search** | 伺服器端工具 | Anthropic only | `web_search` (server) | $10/1K searches |
| **OpenAI WebSearchTool** | SDK 內建 | OpenAI only | SDK built-in | 包含在 API 費用 |
| **Playwright** | 自訂工具 | 兩者皆可 | `web_browse` | 免費（本地 headless） |

**設計特點**：
- 條件性工具注入（config flags 控制啟停）
- 分頁讀取（offset/max_chars）取代硬截斷
- Tavily 改名 `tavily_search`/`tavily_fetch` 避免與 Claude server tool `web_search` 衝突
- System prompt 含搜尋策略指引（query crafting, refinement, sufficiency, source assessment）
- `pause_turn` stop reason 處理（Claude server-side web search）
- deep_researcher subagent 加入 `tavily_search` + `web_browse`

**實作內容**：
- [x] `src/tools/web_tools.py` — 3 函數：`web_search()`, `web_fetch()`, `web_browse()`
- [x] `src/agents/config.py` — 5 新欄位 (web_tavily, web_claude_search, web_openai_search, web_playwright, web_claude_max_uses)
- [x] `config/user_profile.yaml` — web_search 配置區段
- [x] `config/.env.template` — TAVILY_API_KEY
- [x] `src/tools/registry.py` — `_register_web_tools()` 註冊 3 工具
- [x] `src/agents/anthropic_agent/tools.py` — 條件性 schema + dispatch
- [x] `src/agents/anthropic_agent/agent.py` — Claude server tool + pause_turn
- [x] `src/agents/openai_agent/tools.py` — 條件性 @function_tool
- [x] `src/agents/openai_agent/agent.py` — 條件性 WebSearchTool()
- [x] `src/agents/shared/prompts.py` — web search + strategy sections
- [x] `src/agents/shared/subagent.py` — deep_researcher tools + pause_turn
- [x] `requirements.txt` — tavily-python, playwright
- [x] `tests/test_web_tools.py` — 27 tests（全 mock）
- [x] 既有測試更新（tool count 18→21, 19→22）

**工具數量**: Registry 22（18 base + 3 web + 1 analyst）, Bridges 23（+delegate_to_subagent）, OpenAI agent 24（+SDK WebSearchTool）

---

### Phase 11: 數據源整合深化

**目標**: 整合已有但未接入 agent 的數據源，填補分析盲區
**優先級**: 🟡 中
**預估**: ~300 LOC（分子任務可獨立推進）
**狀態**: ✅ 主體完成（11a + 11b + 11c + 11c-v2 + 11c-v3 ✅，11d 待外部條件）

#### Data Strategy Summary（Phase 11-pre，2026-02-16 統整）

基於 `data_sources/PAID_SUBSCRIPTION_EVALUATION.md` 等 5 份評估文件分析：

**第三方數據源**：

| 優先級 | 數據源 | 費用 | 決策 | 理由 |
|--------|--------|------|------|------|
| P0 | Finnhub 免費 analyst endpoints | $0 | **✅ 實作** | recommendations + earnings surprise（Phase 11b） |
| P0 | SEC EDGAR (insider/earnings) | $0 | **待接入** | `sec_insider_trades.py` 已完成，未接入 tool 層 |
| P1 | Unusual Whales | $50/月 | **待訂閱** | options flow 唯一可行來源 |
| P2 | Polygon.io 升級 | $29/月 | **考慮** | options history + futures |
| P3 | Financial Datasets | $20 PAYG | **測試** | 獨有 segmented revenue |
| 延後 | Finnhub Premium, EODHD, AV | — | **延後** | 免費方案已覆蓋核心需求 |

**IBKR 市場數據訂閱**：

| 項目 | 費用 | 狀態 | 理由 |
|------|------|------|------|
| 免費項目（Cboe One + IEX + 研究源） | $0 | ✅ 已訂閱 | 100 snapshots/月、60+ 研究源（Morningstar, Zacks, TipRanks 等） |
| OPRA Options L1 | $1.50/月 | ✅ 已訂閱 | options 報價 |
| Base Bundle (US Securities Snapshot + Futures) | $10/月（佣金≥$30 免除） | **建議訂閱** | NYSE/NASDAQ/AMEX snapshot + futures；實盤必備 |
| Add-On Streaming Bundle | $4.50/月 | **建議訂閱** | 即時串流 + Options Greeks；搭配 Base Bundle |
| Dow Jones Newswires | $10-35/月 | **延後** | Finnhub + Tavily 已覆蓋多數需求 |

> **IBKR 策略**：Base + Add-On Streaming 合計 $14.50/月（佣金≥$30 時降至 $4.50/月），實盤前訂閱。

**子任務**：

#### 11a: SEC 數據接入 ✅ 完成（2026-02-16）
- 新建 `src/tools/sec_tools.py`：2 個函數直接調用 `data_sources/` 模組（`requires_dal=False`）
- `get_sec_filings()` 從返回空 → 直接調用 `sec_edgar_financials.get_filings_list()`
- `get_insider_trades()` 新增 — 結構化 Form 4 XML 解析（名字/職位/交易日期/股數/價格/持股）
- **工具數量**: Registry 23（+1 insider trades）, Bridges 24（+1）

**SEC 模組解析能力評估決策（2026-02-15）**：
- `sec_insider_trades.py`：✅ 完全結構化（Form 4 XML 解析）— **已接入**，高信號、低 token
- `sec_edgar_financials.py`：⚡ 僅 metadata（filing_type, date, URL）— **已修復**既有空實作
- `sec_earnings_releases.py`：⚠️ Raw text dump（BeautifulSoup 去 HTML，但無 EPS/revenue 結構化提取）— **暫不接入**

**暫不接入 earnings releases 原因**：
原文可達 5K-20K 字符，含大量法律 boilerplate，token 效益差。
付費 provider（如 Financial Datasets API）的價值正是在於結構化解析這些原始內容。

**未來計畫**：
1. 接入 Unusual Whales 或其他付費 provider 的結構化 earnings 數據作為主要來源
2. 屆時回頭接入 `sec_earnings_releases.py` 作為「替代觀點」工具
3. 與付費 provider 交叉比對（同一事件、不同來源）拓寬分析廣度

#### 11b: 分析師共識（Finnhub 免費 API）✅ 完成（2026-02-16）
- 新增 tool：`get_analyst_consensus(ticker)` — 評級分佈、earnings surprise、upcoming earnings
- Finnhub 免費端點：`/stock/recommendation`、`/stock/earnings`、`/calendar/earnings`
- `/stock/price-target` 為 Premium，graceful fallback → null
- **工具數量（11b 完成時）**: Registry 22（18 base + 3 web + 1 analyst）, Bridges 23（+delegate_to_subagent）
- **工具數量（11a 完成後）**: Registry 23（+1 insider trades）, Bridges 24

#### 11c: Seeking Alpha Alpha Picks 整合 ✅ 完成（2026-03-14）

SA 無官方 API。初始嘗試 Playwright（headless + headed）均被 PerimeterX 反爬偵測攔截，最終改用 **Chrome Extension + Native Messaging** 架構，在使用者真實 Chrome 中執行 DOM 讀取，零偵測風險。

**架構**：
```
Chrome Extension (MV3)               Python (Native Messaging Host)
════════════════════                 ════════════════════════════════
popup.html/js (Refresh UI)          scripts/sa_native_host.py
background.js (service worker)        ├─ DataAccessLayer(db_dsn="auto")
  ├─ chrome.tabs.create(SA URL)       ├─ dal.apply_sa_refresh(scope, picks, ...)
  ├─ waitForTableReady (polling)      ├─ dal.record_sa_refresh_failure(scope, ...)
  ├─ scrape.js (executeScript)        └─ sync_tickers_to_collection()
  └─ sendNativeMessage → host
```
**資料流**：Extension DOM scrape → structured JSON → Native Messaging (stdin/stdout) → `sa_native_host.py` → DAL `apply_sa_refresh()` → DB + file cache

**檔案**：
- `extensions/sa_alpha_picks/` — manifest.json, background.js, scrape.js, popup.html/js, install.sh, uninstall.sh
- `scripts/sa_native_host.py` — Native Messaging host（固定 cwd 至 PROJECT_ROOT）
- `data_sources/sa_alpha_picks_client.py` — 純 DAL reader + ticker sync（~220 LOC，無 Playwright）
- `src/tools/sa_tools.py` — 3 個 tool functions（category="portfolio"）
- `src/tools/data_access.py` — 6 公開 + 7 私有 DAL methods（DB + file dual-backend）
- `src/tools/backends/db_backend.py` — 6 個 SA methods（含 `apply_sa_refresh()` compound transaction）
- DB schema: `sa_alpha_picks`（UNIQUE(symbol, picked_date)）+ `sa_refresh_meta`（per-tab atomic metadata）
- `scripts/sa_login.py` — 已標記 deprecated（保留作參考，待 detail report 替換完成後刪除）

**設計要點**：
- `portfolio_status`（業務：current/closed）與 `is_stale`（同步：bool）分離
- Per-tab atomic refresh：current/closed 獨立 scrape + 獨立 meta，任一失敗不影響另一 tab
- Detail URL 從 table row 的 `<a href>` 擷取，存入 `raw_data` JSONB 以生存 DB round-trip
- Ticker 自動同步：native host 在 current scope refresh 成功時呼叫 `sync_tickers_to_collection()`
- Config guard：`sa_enabled: false` 預設，所有 tool 回 "not enabled"
- **行為變更**：`/ap refresh` 不再由 Python 主動 scrape，改為回傳 `refresh_hint` 指引使用者點 extension

**DOM 偵測**：
- SA current page: `/alpha-picks/picks/current`，removed page: `/alpha-picks/picks/removed`
- Header 有 Company 欄但 data rows 沒有（兩頁皆如此）
- Current data: Symbol | Picked | Return% | Sector | Rating | Holding%
- Removed data: Symbol | Picked | Closed | Return% | Sector | Rating
- `waitForTableReady()` 輪詢 table selector + paywall/login redirect 偵測

**工具（3 個）**：
- `get_sa_alpha_picks(status, sector)` — portfolio 表格（cached, stale_warning if old）
- `get_sa_pick_detail(symbol, picked_date)` — 個股 pick metadata（detail report 待 Phase 11c-v2）
- `refresh_sa_alpha_picks()` — 回傳 refresh_hint + 當前狀態

**CLI**：`/alpha-picks`（alias `/ap`）— `/ap`, `/ap closed`, `/ap NVDA`, `/ap NVDA 2025-06-15`, `/ap refresh`

**工具數量**: Registry 44→47（+3 SA），Bridges 45→48
**測試**: 34 個新測試（`tests/test_sa_tools.py`），含 native host、stale reconciliation、DAL dual-backend、bridge integration
**Migration**: `sql/007_add_sa_alpha_picks.sql`

**已知限制**：
- Python 無法主動觸發 extension refresh（Native Messaging 是 extension→host 單向），`/ap refresh` 改回 hint
- Detail report 尚未實作（`get_pick_detail` 僅回 metadata，detail_report=None）— 待 Phase 11c-v2
- Detail URL 取決於 SA DOM 結構（若改版，gracefully degrade 至 metadata only）

#### 11c-v2: SA Alpha Picks Detail Report Scraping ✅ 完成（2026-03-20）

Extension v1 只抓 portfolio 表格，`detail_report` 為 NULL。v2 從 `/alpha-picks/articles` 頁面增量抓取分析文章，配對到各 pick。

**架構**：Portfolio table 的 `<a href>` 指向 `/symbol/...`（stock page），**不是**文章。文章在 `/alpha-picks/articles` 頁面，每張 card 含 ticker + URL。Extension 先 scroll articles 頁面載入文章列表，再配對 current picks 逐一抓取。

**三種模式**：
- **Quick Refresh**（藍色按鈕）：portfolio + 5 次 scroll（~15 秒），日常用
- **Full Scan**（紫色按鈕）：portfolio + 深度 scroll 到底（幾分鐘），首次或補齊用
- **Fetch Manual**（橘色按鈕）：使用者手動貼 URL 補齊邊界案例（如改名 ticker、隱藏 ticker 標題）

**新增/修改**：
- `extensions/sa_alpha_picks/scrape_detail.js` — Detail page DOM→Markdown 擷取（TreeWalker, recursive exclusion）
- `extensions/sa_alpha_picks/scrape_articles_list.js` — Articles 頁面文章列表擷取（ticker + URL from card text）
- `extensions/sa_alpha_picks/background.js` — `doDetailFetch()` + `doManualFetch()` + `scrollToLoadAll()`（viewport-step scroll 觸發 IntersectionObserver）
- `extensions/sa_alpha_picks/popup.html/js` — 3 按鈕 UI + manual URL textarea（chrome.storage 持久化）+ missing article 提示
- `scripts/sa_native_host.py` — `check_detail_cache`（articles matching + detail_cache_days 過期）+ `save_detail` + `save_detail_by_symbol`（手動模式）
- `data_sources/sa_alpha_picks_client.py` — `detail_stale_warning` 端到端
- `src/tools/data_access.py` — `save_sa_pick_detail()` persistence contract + `get_sa_pick_detail()` file-backend metadata merge
- `src/agents/cli.py` — `/ap NVDA` 顯示 Analysis Report + stale warning

**Ticker 配對**：
- Canadian exchange suffix（`KGCK:CA` → `KGC`, `CLSCLS:CA` → `CLS`）
- Doubled tickers（`SSRMSSRM` → prefix match `SSRM`）
- `BRK.B` dot notation、單字母 ticker `B`、無 Comments 的舊文章
- 改名 ticker（`ATGE` → `CVSA`）需手動 Fetch Manual

**覆蓋率**: 40/40 current picks (100%)
**測試**: 34 → 48 tests（+14 detail 相關，7 個新 test classes）

#### 11c-v3: SA Alpha Picks Articles + Comments ✅ 完成（2026-03-22）

將 SA Alpha Picks articles 作為**獨立資源**存儲（不依附於 picks），並抓取完整留言樹。

**架構**：
- `sa_articles` 表：獨立文章存儲（所有類型：analysis, recap, webinar, commentary, removal）
- `sa_article_comments` 表：巢狀留言樹（synthetic dedup key）
- `sa_alpha_picks.canonical_article_id`：pick→article 關聯（auto-sync）
- Extension 三步流程：save_articles_meta → save_article_content（compound） → audit_unresolved

**核心決策**：
- `sa_articles` 是 canonical source；`sa_alpha_picks.detail_report` 自動同步（backward compat）
- Canonical article matching：`article_type IN ('analysis', 'removal')`，`published_date` 距離排序
- Compound write（article body + comments + pick sync）在單一 DB transaction，暫時關閉 autocommit
- Comments TTL（策略 B）：Quick 只抓新文章，Full Scan 重抓過期留言
- Articles/comments 為 DB-only（不實作 file backend fallback）
- 自然 dwell time：comment scroll 取代人工延遲（避免反爬偵測）

**新增/修改**：
- `sql/008_add_sa_articles.sql` — 3 個 DDL（2 新表 + 1 ALTER）
- `extensions/sa_alpha_picks/scrape_articles_list.js` — 全部文章 + article_id/type/comments_count
- `extensions/sa_alpha_picks/scrape_comments.js` — 留言樹 DOM 擷取
- `extensions/sa_alpha_picks/background.js` — v3 flow + scrollToComments + auto_upgrade
- `scripts/sa_native_host.py` — 4 new actions（save_articles_meta, save_article_content, save_comments_only, audit_unresolved）
- `src/tools/data_access.py` — 6 new DAL methods（DB-only）
- `src/tools/backends/db_backend.py` — 7 new DB methods（compound transaction pattern）
- `src/tools/sa_tools.py` — 2 new tools（get_sa_articles, get_sa_article_detail）
- `src/tools/registry.py` — 47→49 tools
- Anthropic + OpenAI bridges — 48→50 schemas + dispatch
- 清理：`scripts/sa_login.py` 刪除 + `sa_session_file` config 移除

**工具（+2 個）**：
- `get_sa_articles(ticker, keyword, article_type, limit)` — 搜尋 Alpha Picks 文章
- `get_sa_article_detail(article_id)` — 文章內容 + 留言

**測試**: 48 → 58 tests（+10 v3 tests），21+ count assertions 跨 10 個 test files 更新
**Migration**: `sql/008_add_sa_articles.sql`

**實測數據**（2026-03-22 首次 Full Scan）：
- 362 篇文章，317 篇含留言
- 21,484 留言（9,309 replies，43% reply rate）
- 平均留言長度 257 字，99.9% 有時間戳
- 留言時間範圍：2023-08-29 ~ 2026-03-20

**已知限制**：
- Reply parent 關聯為 @username 啟發式（SA flat DOM 無 explicit parent ID）
- 極長討論串（>200 comments）可能因 scroll 深度不足而截斷
- Comments TTL 只在 Full Scan 時重抓（Quick Refresh 不觸發）
- 文章正文目前為 DOM→Markdown 擷取；表格轉 Markdown table，圖片本體不存，右側 Factor Grades 不在正文擷取路徑內。詳見 `docs/design/SA_ALPHA_PICKS_CONTENT_CAPTURE.md`

#### SA Alpha Picks — 未來計畫（11c-v3 完成後待實現）

以下項目在 Phase 11c 開發過程中討論但歸類為未來，優先級由高到低：

| # | 項目 | 說明 | 依賴 |
|---|------|------|------|
| 1 | **Symbol Page 資料** | SA `/symbol/NVDA` 頁面有分析師文章、圖表、評分。不同於 Alpha Picks 文章，是獨立分析師內容。需新 scraper。 | 新 extension scraper |
| 2 | **Alpha Picks 績效分析** | Win rate、sector exposure、平均報酬。純分析，可用現有 `sa_alpha_picks` 資料。可做 `get_sa_picks_analytics()` tool。 | 無（現有資料足夠） |
| 3 | **chrome.alarms 自動排程** | Extension `chrome.alarms` API 定期自動 Quick Refresh（如每 24h）。省去手動點擊。 | 小改 extension |
| 4 | **SA 一般文章** | SA 整站文章（非 Alpha Picks 專區），範圍大、URL pattern 不同。 | 大範圍擴展 |
| 5 | **Comments 深度改進** | 部分文章 300-400 留言需更深 scroll。目前 ~30 viewport 已足夠日常使用。Reply parent 為 @username 啟發式（SA flat DOM 限制）。 | DOM 研究 |
| 6 | **Seeking Alpha Extension 擴充路線** | 從 Alpha Picks 擴展到 `market-news`、`latest-articles`、`key_markets`、Factor Grades 等資料面。近期優先、metadata-first、snapshot-first。詳見 `docs/design/SA_EXTENSION_ROADMAP.md` | 新 extension scraper + 新表設計 |

#### SA-R1: Market News v1（2026-04-07）

- `market-news` recent feed metadata scraper（title/url/time/tickers/summary/comments_count）
- `sql/009_add_sa_market_news.sql` — 新增 `sa_market_news`
- `DataAccessLayer` + `DatabaseBackend` — save/query market-news metadata
- `scripts/sa_native_host.py` — `save_market_news` action
- `src/tools/sa_tools.py` — `get_sa_market_news(ticker, keyword, limit)`
- `src/tools/registry.py` — 49→50 registry tools，`news` category 5→6
- Anthropic + OpenAI bridges — 50→51 schemas/tools

SA-R1 後續運維補強（2026-04-23）：

- `News Catchup` mode：`current + bounded backfill` queue 分離
- Market News backfill 僅補 **最近 24 小時內已知新聞**
- Auto-sync `Auto` 改為 ET publish-density 驅動窗口，而非手寫 market-hours 規則
- 相關分析資產：
  - `src/service/sa_market_news_density.py` — 可重用的 ET bucket / schedule recommendation helper
  - `scripts/analysis/analyze_sa_market_news_density.py` — 用 DB 實測近期密度並輸出 weekday/weekend 建議窗口
  - `tests/test_sa_market_news_density.py` — interval recommendation / bucket aggregation / merged windows coverage

#### 11d: Unusual Whales Options Flow（待訂閱）
- 有 API，$50/月
- 如果訂閱，新增 tool：`get_options_flow(ticker)` — sweep, block, unusual volume

**實作順序建議**: 11b ✅ → 11a ✅ → 11c（v1+v2+v3）✅ → 11d (UW, 付費)

---

### Phase 12: 數據管道修復 — 自建 PostgreSQL + pgvector

**目標**: 結束 FileBackend raw parquet 權宜方案，回到預定的 DatabaseBackend 架構
**優先級**: 🟡 中（功能正常但架構偏離設計）
**狀態**: ✅ 全部完成（Part A-D + 12c/12e/12f/12g ✅）

**背景**（2026-02-13 診斷結果）：

Agent 所有新聞工具回傳 0 筆資料，根因追蹤如下：

```
數據收集 → data/news/raw/ (新鮮至 2026-02-12) ✅
LLM 評分 → *_scored_final.* (停在 2025-12/2026-01) ❌ ← 評分流程未執行
遷移腳本 → Supabase DB (停在 2026-01-03) ❌ ← 讀的是 stale scored files
DB 查詢 → DatabaseBackend → 0 results (2026-01-13 之後無資料) ❌
```

同時 Supabase 免費方案已超限（629 MB / 500 MB），寫入被阻擋。

**架構決策（2026-02-18）**：純 PostgreSQL + pgvector（非 Supabase）

決策理由：
- 本專案零 Supabase SDK 依賴（`DatabaseBackend` 通過 `psycopg2` 直連）
- 未使用 Supabase Auth、Storage、Realtime、PostgREST、RLS
- `pgvector/pgvector:pg17` Docker image 直接支援語意搜尋
- 單一 container + named volume，遷移最簡單（`pg_dump` → `pg_restore`）
- 未來需要 Auth 可走 FastAPI middleware，不需 Supabase 13+ containers

**部署架構**：
```
開發機（本機）  ──── LAN port 15432 ────  DB 機（遠端 Docker）
  程式碼/IDE/MCP                           PostgreSQL 17 + pgvector
```

**Phase 12 修復步驟（Part A: 程式碼修改 ✅）**：

- [x] **12-A1**: SQL schema headers 更新（Supabase → PostgreSQL，pgvector 保留）
- [x] **12-A2**: `docker/docker-compose.yml` 新建（pgvector:pg17, port 15432, named volume）
- [x] **12-A3**: `src/tools/db_config.py` 新建（DRY: 3 處重複 .env 解析 → 1 處共用）
- [x] **12-A4**: `config/.env.template` 更新（DATABASE_URL 為主，SUPABASE_DB_URL 為 legacy fallback）
- [x] **12-A5**: `data_access.py` + `db_backend.py` 更新（sslmode 自動推導，移除 Supabase 引用）
- [x] **12-A6**: `migrate_to_supabase.py` + `daily_update.py` + `test_db_backend.py` 更新
- [x] **12-A7**: `docker/README.md` 新建（快速啟動 + 備份 + 遷移指南）

**Phase 12 部署步驟（Part B-D: ✅ 已完成 2026-02-18）**：

- [x] **12-B**: 遠端 DB 機器部署 Docker Compose — PG 17.8 + pgvector 0.8.1, healthy
- [x] **12-C**: 數據導入 + 驗證 — 138K news + 277K scores + 1.8M prices, 20/20 tests pass
- [x] **12-D**: MCP PostgreSQL 配置 — crystaldba/postgres-mcp (Docker, stdio), 9 tools
- [x] **12e: `_load_raw_news()` 決策** — **保留**作為 FileBackend fallback（DB 不可用時自動降級，正常情況是死代碼）
- [x] **12f: `scored_only` 設計確認** — `get_ticker_news` 保持 `scored_only=False`（通用查詢），`get_news_sentiment_summary` 用 `scored_only=True`（情緒分析）— 設計合理，無需變更
- [x] **12c: 數據管道修復** — `migrate_to_supabase.py` 修復 recursive glob + raw parquet import，DB 更新至 202K news + 385K scores（含 GPT-5.2 xhigh 108K 筆）

**部署詳情**: 見 archive/PHASE12_DATABASE_DEPLOYMENT.md (歷史記錄，已歸檔) (removed 2026-06-07, recoverable via git; see docs/design/archive/README.md)

**變更檔案（Part A）**：

| 檔案 | 類型 | 說明 |
|------|------|------|
| `sql/001_init_schema.sql` | 修改 | Header: Supabase → PostgreSQL（pgvector 保留）|
| `sql/002_add_news_scores.sql` | 修改 | Header 同步更新 |
| `docker/docker-compose.yml` | 新建 | pgvector:pg17, port 15432, healthcheck |
| `docker/README.md` | 新建 | 快速啟動 + 備份 + 遷移指南 |
| `src/tools/db_config.py` | 新建 | 共用 DSN 載入 + sslmode 推導（~70 LOC）|
| `config/.env.template` | 修改 | DATABASE_URL 為主，移除死設定 |
| `src/tools/data_access.py` | 修改 | 改用 db_config，sslmode 自動推導 |
| `src/tools/backends/db_backend.py` | 修改 | sslmode 預設 "prefer"，移除 Supabase 引用 |
| `scripts/migrate_to_supabase.py` | 修改 | 改用 db_config，sslmode 不再硬編碼 |
| `scripts/collection/daily_update.py` | 修改 | Help text: SUPABASE_DB_URL → DATABASE_URL |
| `tests/test_db_backend.py` | 修改 | 改用 db_config，sslmode 自動推導 |

#### 12g: Ticker 數據收集同步問題（2026-02-15 發現 → ✅ 已修復）

**問題**: Agent 查詢某些追蹤股票時回報「No price data available」

**根因**：`config/tickers_core.json` 與 `config/user_profile.yaml` watchlists 不同步。
初始診斷聲稱 7 個 ticker 缺失，經驗證實際只有 IBM 缺失（IONQ/RGTI/QBTS/DELL/ANET/AFRM 已在同日稍早加入，SQ 已更名 XYZ）。

**修復**：
- [x] **12g-1**: IBM 加入 `config/tickers_core.json` tier3_user_watchlist/quantum_computing（2026-02-16）
- [x] **12g-2**: 自動同步機制 — `daily_update.py` 的 `sync_watchlist_tickers()` 啟動時讀 `user_profile.yaml` watchlists，
  自動合併到 `tickers_core.json`（line 103-173, called at line 775）

---

### Phase 13: Skills System — 目標導向 Workflow 模板 ✅

**目標**: 讓 agent 支援預定義的多步驟分析流程，用戶可一鍵觸發複雜工作流
**優先級**: 🟡 中
**預估**: ~300 LOC
**狀態**: ✅ 已完成（2026-02-19）

**參考**: Dexter 的 SKILL.md 模式 (`AI_AGENT_ARCHITECTURE_PATTERNS.md` #9)

**設計決策（最終）**：
- **目標導向** — 不規定步驟順序，只定義 Goal + Minimum Data Sources + Output Requirements + Post-action
- 模型自行決定工具選擇、調用順序、分析策略。新工具加入後自動受惠（tool-agnostic）
- 用戶透過 `/skill <name> [args]` 觸發，skill prompt 注入到 agent question
- 與 subagent 的區別：skill 是 **目標模板**，subagent 是 **專門角色**

**初步構想的 Skills**：

| Skill Name | 步驟 | 用途 |
|------------|------|------|
| `full_analysis` | 收集新聞 → 收集價格 → 量化分析 → 反面驗證 → 總結 | 單支股票完整分析 |
| `portfolio_scan` | 遍歷 watchlist → 每支做快速篩選 → 排序 → Top N 深入 | 全持倉掃描 |
| `earnings_prep` | 查 earnings date → 歷史 surprise → analyst consensus → risk | 財報前準備 |
| `sector_rotation` | 各 sector ETF 動態 → 資金流向 → 強弱排序 | 板塊輪動分析 |

**設計要點**：
- [x] Skill 定義格式 — YAML (`config/skills/*.yaml`) + Python dataclass (`SkillDefinition`)
- [x] 執行引擎 — `expand_skill()` + `parse_skill_command()` 目標導向 prompt 展開
- [x] 與 subagent 的協作 — skill 展開後自然支持 subagent delegation
- [x] CLI 整合 — `/skill <name> <params>`, `/sk` alias, `/skill` 列表
- [x] 錯誤處理 — 參數驗證 + graceful fallback

**已確認**：
- Skill 定義在 `config/skills/` YAML（custom）+ `src/agents/shared/skills.py`（built-in）
- 用戶可自定義 skill（YAML auto-load，built-in 受保護）
- 目標導向設計，不規定步驟順序，新工具自動受惠

---

### Phase 14: Subagent Enhancement — Reviewer + 角色優化 ✅

**目標**: 擴充 subagent 系統，加入 reviewer 角色，增強 code_analyst，優化 data_summarizer
**優先級**: 🟡 中（Phase 6 的延伸）
**預估**: ~200 LOC（在 subagent.py 基礎上擴充）
**狀態**: ✅ 已完成（2026-02-19）

**背景**: 原始設計規劃了 reviewer 和 programmer 角色。
Phase 6 實作了基礎 3-role pattern，Phase 14 最終決策：
- 新增 reviewer（對抗性審查）
- 合併 programmer 進 code_analyst（增強工具集和 prompt）
- data_summarizer: Opus 4.7 → Sonnet 4.6（降成本 40%）+ adaptive thinking

**最終 4-role 架構**：

| Role | 模型 | 職責 | 核心工具 |
|------|------|------|---------|
| `code_analyst` | gpt-5.2-codex (xhigh) | 量化 Python 分析 + 自主設計（合併 programmer） | execute_python_analysis, get_ticker_prices, get_fundamentals_analysis, tavily_search |
| `deep_researcher` | gpt-5.2 (xhigh) | 多源深度調查 (10 tools) | get_ticker_news, get_sector_performance, get_iv_analysis, synthesize_signal, tavily_search, web_browse + more |
| `data_summarizer` | claude-sonnet-4-6 (adaptive thinking) | 快速數據摘要 + 多 ticker 掃描 | get_news_brief, get_ticker_news, get_watchlist_overview, get_morning_brief, get_fundamentals_analysis |
| `reviewer` | claude-opus-4-7 (thinking+max) | 對抗性審查：邏輯漏洞、遺漏風險、數據充分性 | tavily_search, get_ticker_news |

**Reviewer 設計**：
- 接收：主 agent 的分析結論 + 使用的數據摘要
- 觸發：agent 主動判斷需要時 delegate（非每次自動）
- 回傳：`{issues: [...], confidence_adjustment: float, recommendation: str}`

**已確認決策**（原 "待確認" 已全部解決）：
- ✅ reviewer 觸發時機 → agent 自主判斷
- ✅ programmer 合併進 code_analyst → 增強工具集 (fundamentals + tavily) + prompt 支持自主分析設計
- ✅ 每個 subagent 有精選 tool 子集（`_filter_anthropic_tools()` / `_filter_openai_tools()` 過濾）

---

### Phase 15: Security Content Wrapping ✅

**目標**: 對 tool results 加入安全性包裝，防止 prompt injection
**優先級**: 🟢 低 → 已完成
**預估**: ~100 LOC
**狀態**: ✅ 已完成（2026-02-16）

**參考**: Dexter 的 Security Content Wrapping 模式 (`AI_AGENT_ARCHITECTURE_PATTERNS.md` #16)

**實作內容**：
- `src/agents/shared/security.py`: `wrap_tool_result(content, tool_name)` — XML boundary tags
- 在兩個 bridge 的 `_serialize_result()` 層統一注入，覆蓋所有工具（40 registry + delegate_to_subagent）
- Anthropic bridge: `execute_tool()` → `_serialize_result(result, tool_name)` → `<tool_output>`
- OpenAI bridge: 每個 `@function_tool` wrapper 直接傳 tool_name 給 `_serialize_result()`
- System prompt 加入 `─── TOOL OUTPUT FORMAT ───` 區塊，指導 LLM 視 tool output 為 DATA
- `tests/test_security.py`: 11 tests（wrap 函數 + 兩個 bridge 包裝驗證 + prompt 檢查）

**設計決策**：
- 在 `_serialize_result()` 層統一處理（而非每個工具單獨加），確保零遺漏
- 使用 `<tool_output tool="name">` 格式（非 `<tool_result>`），因為 tool_result 是 Anthropic API 的保留名詞
- `tool_name` 參數為 optional（預設空字串不包裝），保持向後兼容
- CLI 和 subagent 自動受惠（都通過同一 serialize 路徑）

### Prompt Caching + Custom Skills ✅

**目標**: 啟用 Anthropic prompt caching 減少 input token 成本，追蹤兩家 provider 的 cache 統計，支援用戶自定義 skills
**狀態**: ✅ 已完成（2026-02-19）

**Prompt Caching 實作**：
- `_prepare_cached_system(prompt)` — string → array format with `cache_control: {"type": "ephemeral"}`
- `_prepare_cached_tools(tools)` — last tool 加 cache_control（shallow copy 不變更原 list）
- 應用於: `agent.py` run_query_stream, `subagent.py` _run_anthropic_subagent, `cli.py` run_anthropic_interactive
- Cache 前綴: tools → system → messages，tools 變更影響全部，system 變更影響 system+messages
- TokenTracker: `cache_creation_tokens` + `cache_read_tokens` 追蹤 Anthropic + OpenAI
- CLI `print_summary()`: 顯示 Cache read/write 統計 + token usage

**Custom Skills 實作**：
- `config/skills/*.yaml` — 每檔一個 skill，import 時自動載入
- `load_custom_skills()` — 讀取 YAML, 建構 SkillDefinition, merge 到 SKILL_REGISTRY + _ALIAS_MAP
- Built-in skills (4 個) 受 `_BUILTIN_SKILL_NAMES` frozenset 保護，不可覆寫
- 壞 YAML 只 warning 不中斷啟動

**測試**：14 (prompt_caching) + 17 (cache in token_tracker) + 8 (custom skills) = 39 new tests

---

### Phase A: SEC EDGAR Fundamentals Fallback ✅

**目標**: `get_fundamentals_analysis()` 在無 Polygon 付費數據時自動用 SEC EDGAR XBRL 查詢
**狀態**: ✅ 完成（2026-02-19）

**實作內容**：
- `data_sources/sec_edgar_financials.py` → `SECEdgarFinancials` class
- 衍生指標：ROE, ROA, D/E, current ratio, margins, revenue/earnings growth, FCF
- SEC EDGAR quarterly (Q1-Q3) 已實作，Q4 不由 10-K 反推（需 Financial Datasets API）
- 單季 vs YTD 累計自動偵測（`_is_single_quarter()` via start/end duration ≤105 days）

---

### Phase B: Research Reports System ✅

**目標**: Agent 分析後可存儲研究報告，支援跨 session 查閱
**狀態**: ✅ 完成（2026-02-19）

**實作內容**：
- `src/tools/report_tools.py` — `save_report()`, `list_reports()`, `get_report()`
- DB: `research_reports` table (`sql/003_add_reports.sql`)
- Files: `data/reports/YYYY-MM-DD_TICKER_hash.md`
- CLI: `/reports`, `/reports <id>`, `/reports <TICKER>`

---

### Phase C: Agent Query Logging ✅

**目標**: 記錄每次 agent 查詢到 DB（best-effort）
**狀態**: ✅ 完成（2026-02-19）

**實作內容**：
- `db_backend.insert_agent_query()` — logs to `agent_queries` table
- Called from `_log_agent_query()` in `cli.py` after each query
- Answer truncated to 2000 chars

---

### Phase D: File Attachment ✅

**目標**: 支援用戶附加 PDF/圖片/文本到 agent 查詢
**優先級**: 🟡 中
**狀態**: ✅ 完成（2026-02-19）

**實作內容**：
- `src/agents/shared/attachments.py` — Attachment, AttachmentManager, PDFProcessor
- **Anthropic**: 原生 PDF (`document` type, base64) + 圖片 (`image` type) + 文本
- **OpenAI**: 圖片 (`input_image`, data URL), PDF → text via PyMuPDF, 文本 (`input_text`)
- CLI: `/attach <path> [pages]`, `/attach list`, `/attach clear` (alias `/at`)
- 依賴：`pymupdf>=1.24.0`
- 附件在查詢發送後自動清除
- 40 tests

---

### Phase E: Episodic Memory System ✅

**目標**: 跨 session 知識持久化 — agent 可存儲/回憶分析結論、洞察、偏好
**優先級**: 🔴 高
**狀態**: ✅ 完成（2026-02-19）

**實作內容**：
- `src/tools/memory_tools.py` — `save_memory()`, `recall_memories()`, `list_memories()`, `delete_memory()`
- DB: `agent_memories` table (`sql/004_add_memories.sql`) with full-text search (GIN + tsvector)
- Files: `data/agent_memory/YYYY-MM-DD_CATEGORY_hash.md`（human-readable dual storage）
- Categories: analysis, insight, preference, fact, note
- Sources: agent_auto, user_manual, subagent
- CLI: `/memory`, `/memory save`, `/memory search <q>`, `/memory <id>`, `/memory delete <id>` (alias `/mem`)
- System prompt 指導 agent 何時自動存儲
- **工具數量**: 當時 Registry 30（+4 memory tools），最終增至 40 registry + 41 bridges（2026-02-27）
- 29 tests

### Phase F: Financial Datasets API Integration ✅

**目標**: 付費 API fallback，補齊 SEC EDGAR 不足的 Q4 單季和 TTM 數據
**狀態**: ✅ 完成（2026-02-20）

**實作內容**：
- `data_sources/financial_datasets_client.py` — HTTP client + DB/file 雙層快取
- `sql/005_add_financial_cache.sql` — 快取 table（cache_key UNIQUE, JSONB data, expires_at）
- `src/tools/analysis_tools.py` — 3-tier fallback: IBKR → SEC EDGAR → Financial Datasets
- `config/user_profile.yaml` — `paid_sources.financial_datasets` 開關 + TTL 配置
- 共用 `_build_result_from_statements()` for SEC + FD paths
- `_is_fd_enabled(dal)` 檢查 env var + config toggle
- `_to_dataclass()` FD JSON → SEC EDGAR dataclass（欄位 1:1 映射）
- 12 tests (`tests/test_financial_datasets.py`)

**設計特點**：
- disabled 時零開銷（不 import、不呼叫、不佔 token）
- 快取 TTL: 年報 180 天、季報 90 天、TTM 30 天
- 無 API key 時回傳空列表（不報錯）
- DB + file 雙寫，graceful degradation

---

### Monitor System: Phase 1+2+3 + Batch A + Batch B ✅

**目標**: 從零建構完整的監控系統 — 從 Watcher library 到 Discord 雙向互動 Gateway
**狀態**: ✅ 全部完成（2026-02-24 ~ 2026-02-27）

#### Monitor Phase 1: Watcher Library + CLI ✅（2026-02-24）

**實作內容**：
- `src/monitor/watchers.py` — 4 Watchers: Price, Sentiment, Signal, Sector
- `src/monitor/engine.py` — MonitorEngine 協調 watchers + alert dispatch
- `src/monitor/notifiers.py` — Alert model + Console/Log notifiers
- CLI `/monitor` 命令 + `scan_alerts` tool（registry tool #40）

#### Monitor Phase 2: Scheduler + Discord Bot ✅（2026-02-25）

**實作內容**：
- `src/monitor/scheduler.py` — MonitorScheduler（asyncio.create_task, 5 分鐘間隔）
  - 同步 scan 在 background thread 執行（`asyncio.to_thread`），不阻塞 Discord gateway heartbeat
- `src/monitor/discord_bot.py` — MindfulDiscordBot 基礎框架
- DiscordNotifier — 將 alert embeds 推送到指定 channel
- `scripts/monitor_service.py --discord` 啟動入口

#### Monitor Phase 3: Discord Gateway ✅（2026-02-25）

**實作內容**：
- 8 Slash commands: `/ask`, `/analyze`, `/news`, `/scan`, `/skill`, `/model`, `/effort`, `/reasoning`
- 3 Interactive Views: AlertActionView（Analyze+News buttons）, SkillSelectView（4 skills dropdown）, TickerModal
- Free chat: @mention bot → agent query
- `_run_agent_query()` — 非同步 agent 呼叫（`asyncio.to_thread`），返回 `(answer, model_name)` tuple
- `_send_long_followup()` / `_send_long_message()` / `_send_as_embeds()` — Markdown → Discord embed 分段
- Severity-based routing: CRITICAL/HIGH → report channel, MEDIUM/LOW → log channel

#### Monitor Batch A: 穩定性修復 ✅（2026-02-26）

**實作內容**：
- **Heartbeat 修復**: scheduler scan 改用 `asyncio.to_thread()` 在 background thread 執行，避免 blocking main loop 導致 Discord gateway 逾時
- **Alert 去重**: `src/monitor/dedup.py` — `AlertDeduplicator`（in-memory, cooldown 30m + value threshold 1.5pp）
- **Response formatting**: `_send_as_embeds()` 支援 Markdown → Discord embed，分段 4000 chars 限制
- 45 tests（`tests/test_monitor.py`）

#### Monitor Batch B: Model Selection ✅（2026-02-27）

**實作內容**：
- **Shared Model Catalog**: `src/agents/shared/model_catalog.py` — 從 `cli.py` 抽出 `ModelEntry`, `MODEL_CATALOG`, `find_model()`, effort 常數
  - `cli.py` 改為 re-export（向後相容）
- **BotSessionState**: dataclass（provider, model, anthropic_effort, anthropic_thinking, reasoning_effort）
  - `snapshot()` — copy-based 快照，thread-safe（query 進入前拍攝，thread 內用 immutable snap）
  - `effective_model()` — None → config default 自動解析
- **asyncio.Lock**: 保護 `/model`, `/effort`, `/reasoning` 狀態切換
- **Permission control**: `_is_admin()` — `manage_guild` 權限檢查，DM 拒絕
- **ModelSelectView**: 動態從 MODEL_CATALOG 生成 `discord.ui.Select` options
- **Footer model name**: `_run_agent_query()` 回傳 `(answer, model_name)` tuple，footer 用 query-specific model
- 93 tests（`tests/test_monitor.py`），含 model selection + permission + snapshot 測試

**檔案**：
- `src/monitor/discord_bot.py` — 主要 Discord bot（~1100 LOC）
- `src/monitor/scheduler.py` — 排程器
- `src/monitor/engine.py` — 監控引擎
- `src/monitor/watchers.py` — 4 Watchers
- `src/monitor/notifiers.py` — Alert + Notifiers (Console/Log/Discord)
- `src/monitor/dedup.py` — Alert 去重
- `src/agents/shared/model_catalog.py` — 共用 model catalog
- `scripts/monitor_service.py` — 啟動腳本
- `tests/test_monitor.py` — 93 tests

---

### Bug Fix Sessions ✅

**2026-02-26 ~ 2026-02-27**: 多輪高優先級 bug fix

| 日期 | 修復 | 影響 |
|------|------|------|
| 2026-02-26 | 5 high-priority bugs: event chain 資料遺失、bearish filter、DB duplicates、rolling leak、median | `src/tools/` 多個分析工具 |
| 2026-02-26 | Dynamic risk-free rate: ^IRX 即時利率 + cache key 含 years_for_growth | `options_tools.py`, `analysis_tools.py` |
| 2026-02-26 | as_of_date 精確錨定 + LOW_CONFIDENCE fallback + ATM scope marker | `analysis_tools.py`, `options_tools.py` |
| 2026-02-27 | Wire dynamic risk-free rate into scan tool + ticker-specific anchor | `analysis_tools.py` |
| 2026-02-27 | yfinance readonly SQLite 修復（`set_tz_cache_location()`） | `options_tools.py` |
| 2026-02-27 | Persist last-known-good risk-free rate + validate as_of_date format | `options_tools.py`, `analysis_tools.py` |
| 2026-02-27 | /save crash + WebSocket transport + Finnhub rate limiter | `cli.py`, `ws_server.py`, `finnhub_news.py` |

---

## 4. 測試策略

### 單元測試

| Phase | 測試重點 | 測試檔案 |
|-------|---------|---------|
| 1 | Token 計數準確性、累計追蹤 | `tests/test_token_tracker.py` |
| 2 | JSONL 寫入/讀取、事件格式 | `tests/test_scratchpad.py` |
| 3 | 清除邏輯、閾值判斷 | `tests/test_context_manager.py` |
| 4 | Event 格式、stream 序列、SSE、backward compat | `tests/test_events.py` (20 tests) |
| 8 | Effort kwargs、thinking blocks、model detect、config defaults | `tests/test_events.py` + `tests/test_agents.py` |
| 5 | Sandbox 安全性、timeout | `tests/test_code_executor.py` (36 tests) |
| 5b | Provider detect, code extract, mock LLM retry, task mode | `tests/test_code_generator.py` (27 tests) |
| 6 | Dispatch 路由、結果合併 | `tests/test_subagent.py` |
| 7 | Compaction params、response 解析、config | `tests/test_server_compaction.py` (13 tests) |
| 9 | Prompt A/B 比較（手動）、adversarial output 品質 | 手動 CLI 測試 |
| 10 | Web search mock HTTP、結果解析、tool 整合 | `tests/test_web_tools.py` |
| 11 | SEC 數據接入、Finnhub analyst API、tool 整合 | `tests/test_data_integration.py` |
| 15 | Security wrapping、boundary tags、bridge integration | `tests/test_security.py` (11 tests) |
| 12 | Backend 切換驗證、raw parquet 讀取、agent 端到端 | 手動 CLI 測試 |
| 13 | Skill 定義解析、步驟執行、錯誤處理、CLI 整合 | `tests/test_skills.py` |
| 14 | Reviewer 結論審查、Programmer 代碼生成、subagent 擴充 | `tests/test_subagent.py` 擴充 |
| 15 | Content wrapping、tag injection 防禦 | `tests/test_security_wrapping.py` |
| PC | Prompt caching helpers、cache token tracking、custom skills YAML | `tests/test_prompt_caching.py`, `tests/test_token_tracker.py`, `tests/test_skills.py` |
| D | Attachment loading、PDF/image/text 轉換、Anthropic/OpenAI 格式 | `tests/test_attachments.py` (40 tests) |
| Mem | Memory CRUD、full-text search、file fallback、registry 整合 | `tests/test_memory_tools.py` (29 tests) |
| F | FD client、cache hit/miss/expired、fallback chain、config toggle | `tests/test_financial_datasets.py` (12 tests) |
| Mon | Scheduler, dedup, severity routing, agent query, model selection, permissions, snapshot | `tests/test_monitor.py` (93 tests) |
| B0 | Model catalog find/match, effort options, CLI re-exports | `tests/test_monitor.py` (TestModelCatalogShared) |

### 整合測試

每個 Phase 完成後：
1. 跑全部現有測試（確認不 break） — **目前 950 tests 全過**（2026-02-27）
2. 手動測試 CLI query（`python -m src.agents.openai_agent.agent "分析 NVDA 近期走勢"`）
3. 測試 HTTP API endpoint
4. 手動測試 Discord bot（`python scripts/monitor_service.py --discord`）

---

## 4.5 已知缺口 / 未來工作

### Context Management 缺口

| 項目 | 狀態 | 說明 |
|------|------|------|
| L1 Client-side compaction — `agent.py` `run_query_stream()` | ✅ 已整合 | ContextManager + should_compact + compact_messages |
| L1 Client-side compaction — `cli.py` `run_anthropic_interactive()` | ✅ 已整合 | ContextManager + should_compact + compact_messages（2026-02-24 修復） |
| L2 Server-side compaction (Phase 7a) | ✅ 已整合 | Anthropic (Opus 4.7 + Sonnet 4.6) + OpenAI (CompactionSession)，預設 OFF |

**狀態**: L1 + L2 全部整合完成。L2 Sonnet 4.6 支援於 2026-02-24 修復（原先只列 Opus 4.7）。

### Vector Embeddings（Smart Data Retrieval Phase 4）

| 項目 | 狀態 | 說明 |
|------|------|------|
| `news.embedding VECTOR(1536)` 欄位 | ✅ 已建立 | DB 欄位存在（sql/006），但全部為空 |
| Embedding 生成 + 寫入 pipeline | ❌ 未做 | 需選擇 embedding model (OpenAI ada-3? local?) + batch 寫入 |
| Semantic search tool | ❌ 未做 | `search_news_semantic(query, ticker, ...)` — 依賴上方 pipeline |
| pgvector 相似度查詢 | ❌ 未做 | `ORDER BY embedding <=> $1 LIMIT N` |

**優先級**: 低 — DB full-text search (tsvector + GIN) 已覆蓋大部分搜尋需求。
Vector search 的增量價值在於語義相似度（如「通膨壓力」匹配「CPI 超預期」），
但需要 embedding 成本（~$0.02/M tokens for ada-3）和 pipeline 維護。

---

## 4.6 未來路線圖 (Roadmap)

### Batch 2: 系統完善（中期）
- [x] **Scratchpad 增強** — 新增 thinking/pause_turn/compaction/retry 事件，CLI 渲染 + token_usage 顯示（2026-03-01）
  - 參考: Dexter Scratchpad Pattern (#1)、MINDFULRL_ARCHITECTURE §4.2
- [x] **安全內容包裝** — Phase 15 完成（`_serialize_result()` + XML boundary tags + 所有工具覆蓋）
- [x] **監控系統框架 Phase 1** — Watcher library + CLI `/monitor` + Agent tool `scan_alerts`
  - `src/monitor/` — Alert, Notifier (Console/Log/Discord), 4 Watchers, MonitorEngine, AlertDeduplicator
- [x] **監控系統 Phase 2** — MonitorScheduler + Discord Bot（單向通知） + 排程掃描
- [x] **監控系統 Phase 3** — Discord Gateway（雙向互動：slash commands, buttons, free chat, skills dropdown）
- [x] **監控系統 Batch A** — 穩定性修復（heartbeat, alert dedup, response formatting）
- [x] **監控系統 Batch B** — Model Selection（/model, /effort, /reasoning + BotSessionState + shared MODEL_CATALOG）
- [x] **Data Freshness Registry** — `FreshnessRegistry` singleton + `check_data_freshness` tool + `freshness_in_prompt` feature flag（2026-03-01）
  - 參考: MINDFULRL_ARCHITECTURE §10.6
- [x] **Token Budget（safety rail）** — L1/L2 compaction 已覆蓋 context/token 失控防護，不做內容降級（2026-03-01）
  - 參考: Dexter Token Budget (#7)，品質導向決策：不降質，現有機制已足夠

### Batch 3: 核心策略 + 平台整合（長期）
- [P3 PAUSED · agent 整合 RETIRED 2026-06-03] **RL Pipeline** — 端到端整合：特徵工程 → 訓練 → 推論 → ~~Agent 工具~~（訓練暫停 2026-04-25；**agent 整合下架 2026-06-03**：3 個 get_rl_* 工具移出 registry/bridges、config 假開關移除，commits 94861f7+6b49c74；RL 研究碼移至 `training/`；當前狀態見 [RL_COLLAPSE_FINDINGS.md](RL_COLLAPSE_FINDINGS.md)；原設計已歸檔: archive/RL_PIPELINE_DESIGN.md (removed 2026-06-07, recoverable via git; see docs/design/archive/README.md)）
  - [x] Phase 1c: Agent 整合 — 3 工具 + model registry + config guard（2026-03-01）
  - [x] Phase 1a+1b: 特徵工程 + 回測增強 + 訓練增強（2026-03-02）
    - `feature_engineering.py`: 5 衍生特徵 + FeatureScaler (Z-score, schema version, contract validation)
    - env `extra_feature_cols`: PPO/CPPO state vector 支援 + CPPO risk tail invariant
    - `train_utils.py`: Path A/B 偵測 + `save_training_artifacts()` (MPI rank 0 guard)
    - `backtest.py`: 完整指標 (Sharpe/Sortino/Calmar/CVaR/MDD/win rate) + dated artifacts + registry runs
    - `rl_tools.py`: IR=None + ir_note 契約
    - 125 tests (36 feature eng + 16 env + 13 train utils + 18 backtest + 38 rl_tools + 4 integration)
  - _以下 Phase 1d–2 已於 2026-06-03 隨 RL→agent 整合下架（RETIRED；commits 94861f7+6b49c74）；保留作歷史 roadmap 記錄。_
  - [ ] Phase 1d: 推論實作（state construction → forward pass → action interpretation）
  - [ ] Phase 1e: MVO Baseline — `pypfopt` Mean-Variance Optimization 加入 backtest.py 作為額外 baseline 比較（參考 FinRL `stock_backtest.py`）
  - [ ] Phase 1f: Turbulence Index — rolling covariance-based market turbulence 指標加入 feature engineering（參考 FinRL EODHD `processor_eodhd.py`，需評估與現有 8 技術指標重疊度）
  - [ ] Phase 2（日內）: 分鐘線環境 + real-time sentiment + IBKR 執行（長期）
- [x] **Signal 回測框架** — 歷史驗證信號有效性（納入 RL Pipeline Phase 1a+1b, 2026-03-02）
- [ ] **自動化數據收集排程** — 定時抓取新聞/價格，確保新 ticker 自動覆蓋
  - **現狀**：SA Extension sync → `tickers_core.json` 自動更新，但 collection scripts 需手動執行
  - **缺口**（2026-03-22 確認）：9 個 SA-only ticker 無 Polygon 資料（`B`, `BRK.B`, `CVSA`, `DY`, `FN`, `GM`, `LITE`, `NEM`, `TIGO`），因加入時間晚於上次收集
  - **已知限制**：`--incremental` 用全域最新 timestamp，新 ticker 不會被補抓歷史。需 `--tickers X --start YYYY-MM-DD` 手動補
  - **方案待定**：
    - 方案 A: cron job（簡單，`daily_update.py --news` 每日定時跑）
    - 方案 B: 長期運行 service（可根據事件觸發，如 SA Extension refresh 後自動補抓新 ticker）
    - **兩案都需解決新 ticker backfill**：偵測 `tickers_core.json` 新增 ticker → 觸發 `--tickers <new> --start` 補抓
  - **範圍**：Polygon + Finnhub 新聞、IBKR 價格、IV history
  - **依賴**：各 collection script 已支援 `--incremental`，`tickers_core.json` 讀取已就位
- [ ] **Skills 升級 (Phase G)** — Rich SKILL.md 格式 + Auto-trigger + Anthropic FSP 改裝
  - 調研文件: [SKILL_PLUGINS_RESEARCH.md](SKILL_PLUGINS_RESEARCH.md)
  - 從 Anthropic Financial Services Plugins (41 skills) 中篩選 9 個直接適用 + 6 個部分適用
  - 升級方向: SKILL.md Markdown 格式（500+ 行深度指引）、keyword auto-trigger、data source mapping
  - Phase G-1: SKILL.md 格式解析（向下相容 YAML）
  - Phase G-2: 現有 4 built-in skills → SKILL.md enrichment
  - Phase G-3: Auto-trigger（keyword matching → 自動注入 skill context）
  - Phase G-4: 從 Anthropic repo 改裝 5-6 個 skills（comps, DCF, earnings-analysis, catalyst, idea-gen, thesis-tracker）
  - Phase G-5: Progressive Disclosure（context 緊張時只注入關鍵段落）
  - Phase G-6: Data source mapping + registry 驗證
  - 雙模型支援: Skill 是 prompt injection，天然支援 Anthropic + OpenAI（共用 ToolRegistry）
- [ ] **Vector Embeddings Pipeline** — 語義搜尋增強（DB column 已存在，見 §4.5）
- [ ] **多頻道 Gateway 系統** — 串接 WhatsApp / Telegram（Discord 已完成）
  - Discord 已有完整實作：slash commands + buttons + free chat + model selection
  - 設計方向: ChannelPlugin 抽象（WhatsApp / Telegram）+ 認證 + 權限控制
  - 可複用: 現有 Agent loop + Tool layer + BotSessionState pattern

---

## 5. 變更日誌

| 日期         | 變更 | 備註 |
|------------|------|------|
| 2026-04-27 | P1.3 done — SA Digest / Reading Workflow v1 (3 commits + 4 follow-ups) | `src/tools/sa_digest_tools.py` 提供 `get_sa_digest(ticker, days, max_articles, max_news, max_comments, min_comment_score)` deterministic evidence pack（reframed from 原計畫「SA Latest Articles metadata」——診斷是「資料夠了，缺的是把它變成決策入口」，不再加新表，改建使用層）；composes `sa_articles` + `sa_market_news` + `sa_comment_signals` ↔ `sa_article_comments` 三來源；comments SQL 用 layered CTE（per-article ≤3 先過再算 per-kind ≤max_comments，避開 parallel-windows 形狀的 underfill）；`needs_verification=true` 不過濾、`min_comment_score` clamp `[0.0, 10.0]`、`keyword_buckets` 保留 `Dict[str, List[str]]`、ticker 上 SQL 前大寫；per-source try/except 讓單一來源 fail 不會 blank 整個 digest；無內部 LLM call；output: `recent_articles` / `high_discussion_news` / `high_value_comments.{ticker_mentions, candidate_mentions}` / `data_quality` / `source_notes`；registry 註冊 `category="news"`，Anthropic + OpenAI bridge 完整 wiring；2 個 built-in skill prompt 同步更新（`earnings-prep/SKILL.md` 必呼叫 `days=30`、`full-analysis/SKILL.md` 建議呼叫 `days=14`，`data_sources` frontmatter 同步）；22 unit tests + 2 skill body tests + 1 dispatch regression test + envelope 嚴格 assertion；bridge counts: registry 55 / news category 8 / Anthropic + OpenAI 56 (`ce5f780`, `1108310`, `55c02bd`, `70065c5`, `a19441e`, `68a60a5`, `fd9fb80`, `1db2789`) |
| 2026-04-27 | P1.2 done — commits 5-6 + 2 follow-ups close 6/6 series | `src/service/macro_calendar_health.py`（cadence-based job freshness + table coverage，market-hours upgrade for `fetch_economic_calendar_recent`，periodic flow 把 `job_recent_failure` additively layer 在 cadence severity 之上）；`src/api/routes/macro_calendar.py` `/macro/health[?strict]` + 4 read routes（`/economic-calendar` / `/earnings-calendar` / `/ipo-calendar` / `/series/{series_id}`），全部 gate 在 `macro_calendar.enabled`；`src/macro_calendar/store.py` 加 4 個 list helpers（INNER JOIN LATERAL for events、ALFRED window for series）；`src/tools/macro_calendar_tools.py` 2 個 agent tools（`get_economic_calendar` / `get_macro_value`）；ToolRegistry 54 / Anthropic+OpenAI bridge 55；as_of date-only → EOD UTC（spec §6.1），`from_date` → SOD、`to_date`/`as_of` → EOD via `_parse_iso_datetime_start` / `_parse_iso_datetime_end` 拆分；importance enum 移除（CSV 'high,medium' 可用）；同步 stale tool-count assertions 跨 5 個 test 檔；230+ tests (`b8454a2`, `a5b24d3`, `2478e74`, `7eeffb0`, `95a644d`) |
| 2026-04-27 | P1.2 commit 4 + follow-ups: Finnhub job wiring + API/spec alignment | `src/service/jobs.py` 加 4 個 Finnhub `JobDefinition`（`fetch_economic_calendar_recent` / `_backfill` / `fetch_earnings_calendar` / `fetch_ipo_calendar`）、dispatcher、summary heuristics、watchlist-by-default earnings selection；`JobRunRequest` 補 `from_date`/`to_date`/`years_back`/`symbols`/`series_ids`/`release_ids`/`full_refresh`/`limit≤1000`；`fetch_fred_release_dates` 補 limit forwarding；`P1_2_SPEC.md` §4/§9 sync 至實作（job 名稱 / default window / commit 拆分）；161 tests (`2edea5e`, `3bde0ec`, `6cca46a`) |
| 2026-04-27 | P1.2 commit 3 + rename: Finnhub calendar client + ingestion + src/p1_2 → src/macro_calendar | `data_sources/finnhub_calendar_client.py`（UTC parse, impact/hour/status normalisation, 60 req/min budget）；`src/macro_calendar/finnhub_ingestion.py`（economic / earnings / IPO，per-symbol earnings dedup on `(symbol,year,quarter)`）；`src/p1_2/` → `src/macro_calendar/`，`p1_2_macro_series.yaml` → `macro_calendar_series.yaml`，`p1_2_enabled` → `macro_calendar_enabled`；142 tests (`d3ec85a`, `5b376aa`, `35e8d4f`) |
| 2026-04-26 | P1.2 commits 1-2: schema + DAL + FRED ingestion | `sql/013_add_p1_2_macro_calendar.sql`（cal_*_events + revisions, macro_series + observations + release_dates）；`MacroCalendarStore` canonical/revision upsert + as-of read，baseline-on-first-insert + observed-state-not-prior 不變式；`data_sources/fred_client.py`（ALFRED vintage 支援，`output_type=1/4` 鎖定）；`src/macro_calendar/fred_ingestion.py`（`latest_only` + `full_vintages` 兩條策略，`output_type=4` 取首次發布、`=1` 取完整修訂史）；88 tests (`e8fc1db`, `926a81c`, `f03cf86`, `6536652`, `959c589`) |
| 2026-04-26 | P1.2 provider discovery 完成 | [P1_2_PROVIDER_DISCOVERY.md](P1_2_PROVIDER_DISCOVERY.md) 紀錄 FRED + Finnhub free-tier smoke 結果：FRED ALFRED vintage 可用、`output_type` 行為差異；Finnhub `/calendar/economic` UTC、free tier 含 actual/historical（與初稿假設相反），earnings 永遠不返回 actual、需 per-symbol 才能 cover watchlist；之後 [P1_2_SPEC.md](P1_2_SPEC.md) 設計依此 6-commit 拆分 |
| 2026-04-23 | 文檔大盤點 + 歸檔整理 | 新增 ARKSCOPE_RENAME_PHASE2.md 正式化遷移清單；`MAJOR_REFACTORING_PLAN` 併入 Service-first 協調、標註 Phase D 骨架狀態；`MULTI_FACTOR_SIGNAL_DETECTION` 補標 `src/signals/` 實作度；歸檔 `AI_AGENT_IMPLEMENTATION_PLAN`、`DEXTER_ISSUES_ANALYSIS`、`DAILY_STOCK_ANALYSIS_CODE_ANALYSIS_CHECKLIST` 到 `archive/` |
| 2026-04-23 | 補充 `daily_stock_analysis` 深入讀碼 checklist | 新增 `DAILY_STOCK_ANALYSIS_CODE_ANALYSIS_CHECKLIST.md`（已歸檔到 `archive/`），把第一輪/第二輪筆記收斂成可執行的 code-level walkthrough 清單、分析順序與輸出格式 |
| 2026-04-23 | SA Market News auto-sync 改為 density-driven ET windows + 補齊分析工具鏈 | `News Catchup` queue 分離（current/backfill），backfill 限縮到最近 24h 已知新聞；新增 `src/service/sa_market_news_density.py`、`scripts/analysis/analyze_sa_market_news_density.py`、`tests/test_sa_market_news_density.py`；修復 extension `Auto` label runtime error |
| 2026-04-21 | Service-first slice 啟動：API 邊界 + job control 規劃 | 新增 `SERVICE_FIRST_EXPANSION_PLAN.md`（retired during docs consolidation; S1 landed in `src/api/routes/`, S2+ absorbed by priority map P0.2），將下一步聚焦於 SA read APIs、`jobs/status`、`jobs/run` 與多 client 共用的後端能力邊界 |
| 2026-03-23 | Skills 升級研究：Anthropic Financial Services Plugins 分析 | [SKILL_PLUGINS_RESEARCH.md](SKILL_PLUGINS_RESEARCH.md) — 41 skills 中 9 個直接適用、6 個部分適用，Phase G 規劃（SKILL.md 格式、auto-trigger、data source mapping） |
| 2026-03-22 | Phase 11c-v3 完成：SA Articles + Comments | sa_articles + sa_article_comments 表，canonical_article_id sync，compound transaction，scrape_comments.js，comments TTL，scrollToComments 自然 dwell time，2 new tools（get_sa_articles, get_sa_article_detail），49 registry / 50 bridges，58 tests，`sql/008`，`sa_login.py` 刪除 |
| 2026-03-20 | Phase 11c-v2 完成：SA Alpha Picks Detail Report Scraping | Articles 頁面增量抓取（scroll + ticker 配對），3 模式（Quick/Full Scan/Manual Fetch），DAL persistence 修復，detail_stale_warning E2E，Canadian ticker + 改名 ticker 處理，100% 覆蓋率（40/40），48 tests（+14） |
| 2026-03-14 | Phase 11c 完成：Seeking Alpha Alpha Picks 整合 | Chrome Extension + Native Messaging（PerimeterX 反爬阻擋 Playwright），3 tools (get_sa_alpha_picks/get_sa_pick_detail/refresh_sa_alpha_picks)，DAL dual-backend (DB compound transaction + file cache)，per-tab atomic refresh + stale reconciliation，CLI `/ap`，ticker auto-sync → tickers_core.json，`sql/007_add_sa_alpha_picks.sql`，34 new tests，Registry 44→47, Bridges 45→48 |
| 2026-03-02 | RL Pipeline Phase 1a+1b: 特徵工程 + 回測增強 + 訓練增強 | `feature_engineering.py` (5 features + FeatureScaler), env `extra_feature_cols` + CPPO risk tail invariant, `train_utils.py` (Path A/B + rank 0 guard), `backtest.py` (full metrics + artifacts + registry runs), `rl_tools.py` IR=None contract, 125 tests across 6 test files |
| 2026-03-01 | RL Pipeline Phase 1c: Agent 整合 | `training/model_registry.py` (ModelMetadata + ModelRegistry)，`src/tools/rl_tools.py` (3 tools: get_rl_model_status/get_rl_prediction/get_rl_backtest_report)，config guard (`rl_pipeline.enabled: false`)，system prompt RL status section，44 registry tools, 45 bridge tools, 33 new tests |
| 2026-03-01 | Observability Batch: Freshness + Scratchpad + OpenAI 容錯 + DEBUG | `src/tools/freshness.py` (FreshnessRegistry singleton + check_data_freshness tool), `db_backend.query_health_stats()`, scratchpad 新增 thinking/pause_turn/compaction/retry 事件, `_extract_tool_info()` 共用 helper (call_id mapping + retry logging), OpenAI Runner DEBUG logging, `freshness_in_prompt` feature flag, 41 registry tools, 42 bridge tools, 991 tests pass |
| 2026-02-27 | Monitor Batch B: Discord bot model selection | `src/agents/shared/model_catalog.py` 新增，BotSessionState + snapshot + Lock，`/model` `/effort` `/reasoning` slash commands，ModelSelectView 動態生成，admin permission control，footer model name，93 monitor tests，950 total tests |
| 2026-02-27 | Bug fixes: /save + WebSocket + Finnhub rate limiter | `/save` crash fix，WebSocket transport 改善，Finnhub API rate limiter |
| 2026-02-27 | Bug fixes: risk-free rate + as_of_date precision | Dynamic ^IRX risk-free rate + DB persistence + last-known-good fallback，as_of_date anchor + LOW_CONFIDENCE fallback + ATM scope marker，yfinance readonly SQLite fix |
| 2026-02-26 | Monitor Batch A: heartbeat + dedup + formatting | `asyncio.to_thread` heartbeat fix，`AlertDeduplicator` (cooldown 30m + value threshold)，`_send_as_embeds()` Markdown→Discord embed 分段 |
| 2026-02-26 | 5 high-priority bug fixes | Event chain 資料遺失、bearish filter 邏輯、DB duplicates、rolling window leak、median 計算 |
| 2026-02-25 | Monitor Phase 2+3: Discord bot + scheduler + gateway | MonitorScheduler (asyncio, 5m)，MindfulDiscordBot 8 slash commands + 3 Views + free chat + severity routing，45 → 78 tests |
| 2026-02-24 | Monitor System Phase 1 | `src/monitor/` package — Alert, Notifier (Console/Log), 4 Watchers (Price/Sentiment/Signal/Sector), MonitorEngine, CLI `/monitor` command, `scan_alerts` tool，40 registry tools, 41 bridge tools |
| 2026-02-24 | CLI L1 compaction 補完 + L2 Sonnet 4.6 修復 | `cli.py` `run_anthropic_interactive()` 加入 ContextManager，`_COMPACTION_MODELS` 加入 sonnet-4-6，新增 §4.6 未來路線圖 |
| 2026-02-23 | Web Search 完善 + Codex Deep Research | Claude web_search 升級 (20260209) + CLI pause_turn + web search 費用追蹤 + `codex_web_research()` 工具 (OAuth, --search) + Smart Data Retrieval (get_news_brief, search_news_advanced, DB FTS)，39 registry tools, 40 bridge tools |
| 2026-02-22 | `/save` 指令 + ChatHistory per-session 改造 | `/save` 互動式儲存報告，per-session JSONL (`data/chat_history/`)，擴充欄位 (tickers, tool_calls_detail, token_usage)，`/history` 增強，prompt save_report 改為建議 |
| 2026-02-22 | DB stale connection 修復 | `_get_conn()` 加 `SELECT 1` ping 偵測 server-side idle 斷線 |
| 2026-02-21 | Batch 3 完成：portfolio_analysis + iv_skew + earnings_impact | `get_portfolio_analysis()`, `get_iv_skew_analysis()`, `get_earnings_impact()`，36 registry tools, 37 bridge tools |
| 2026-02-21 | Batch 2 完成：option_chain + detailed_financials + peer_comparison | `get_option_chain()`, `get_detailed_financials()`, `get_peer_comparison()`，33 registry tools, 34 bridge tools |
| 2026-02-21 | Batch 1 完成：valuation_metrics + analyst_estimates + sector_heatmap | `get_valuation_metrics()`, `get_analyst_estimates()`, `get_sector_heatmap()`，30 → 33 tools (registry) |
| 2026-02-20 | Phase F 完成：Financial Datasets API Integration | HTTP client + DB/file 快取 + 3-tier fallback + config toggle，12 tests |
| 2026-02-20 | SEC EDGAR quarterly 修復 | Q1-Q3 from 10-Q 已實作，Q4-from-10K 移除（累計 vs 單季自動偵測） |
| 2026-02-20 | README.md + CLAUDE.md 更新 | 30 tools, 新 slash commands, PostgreSQL MCP 規則 |
| 2026-02-19 | Phase D+E 完成：File Attachments + Episodic Memory | PDF/圖片/文本附件（PyMuPDF），agent_memories 全文搜索（GIN+tsvector），30 registry tools, 31 bridge tools, 69 new tests |
| 2026-02-19 | Prompt Caching + Custom Skills 完成 | Anthropic cache_control (system array + last tool), OpenAI auto-cache 追蹤, TokenTracker cache_creation/read_tokens, CLI cache stats, custom skills YAML (config/skills/), 165 tests pass |
| 2026-02-19 | Phase 13+14 完成：Skills System + Subagent Enhancement | 4 目標導向 skills (full_analysis/portfolio_scan/earnings_prep/sector_rotation), reviewer 角色 (Opus 4.7+thinking+max), code_analyst 增強 (加 fundamentals+tavily), data_summarizer 改 Sonnet 4.6+thinking, CLI `/skill`, 28+5 new tests |
| 2026-02-19 | Phase A+B+C 完成：Fundamentals SEC EDGAR fallback + Research Reports + Agent Query Logging | SEC XBRL 即時查詢（免費覆蓋所有美股）, research_reports 表 + Markdown 存儲, agent_queries 啟用, 3 新工具 (save/list/get_report), CLI `/reports`, 系統提示更新 |
| 2026-02-18 | 新增 claude-sonnet-4-6 + 修復 3 agent bugs | 事件循環 RuntimeError, DB daily 價格聚合, CLI NameError |
| 2026-02-18 | Phase 12 全部完成：自建 PostgreSQL + pgvector 部署 | 純 PG，docker-compose，db_config.py DRY，遠端部署，202K news + 385K scores 匯入，MCP 配置 |
| 2026-02-18 | migrate_to_supabase.py 修復：recursive glob + raw parquet import | 原 `*.parquet` 改 `**/*.parquet`，新增 3 源 raw article 匯入，GPT-5.2 xhigh 108K 分數入庫 |
| 2026-02-16 | Phase 7a 完成：Server-Side Compaction L2 | Anthropic beta `compact-2026-01-12` (Opus 4.7) + OpenAI `CompactionSession`，config toggle + CLI `/compaction`，13 tests，372 total pass |
| 2026-02-16 | Phase 15 完成：Security Content Wrapping | `<tool_output>` boundary tags on all tools via `_serialize_result()` 層，11 tests，system prompt guidance |
| 2026-02-16 | Phase 11a 完成：SEC Data Integration | `get_insider_trades()` 新增 + `get_sec_filings()` 修復，Registry 23, Bridges 24。Earnings releases 暫不接入（raw text, token 效益差） |
| 2026-02-16 | Phase 11b 完成：Analyst Consensus Tool (Finnhub 免費 API) | `get_analyst_consensus()` — recommendations + earnings surprise + upcoming，Registry 22, Bridges 23 |
| 2026-02-16 | Phase 12g 修復：IBM 加入 tickers_core.json | 原報 7 缺失，實際只有 IBM（其餘已在前次加入） |
| 2026-02-16 | Phase 11-pre 完成：Data Strategy Summary 統整 | 第三方數據源 + IBKR 訂閱評估結論，寫入 tracker |
| 2026-02-15 | Phase 10 完成：Web Search 4 提供者 (Tavily/Claude/OpenAI/Playwright) | 16 files, +1084 LOC, 27 new tests, 條件性工具注入 + 分頁 + pause_turn |
| 2026-02-15 | Phase 13-15 新增：Skills System + Subagent Enhancement + Security Wrapping | 基於 Dexter 模式分析和用戶設計討論 |
| 2026-02-15 | Phase 7 擴充：OpenAI context overflow 調查結論 | GPT-5.2 400K overflow 但 Opus 200K 成功；SDK 未用 auto_previous_response_id / CompactionSession |
| 2026-02-15 | Phase 12g 新增：tickers_core.json 同步問題 | 初報 7 缺失，驗證後實際只有 IBM 缺失（2026-02-16 已修復） |
| 2026-02-13 | Phase 12 記錄：數據管道權宜方案 | 註解 SUPABASE_DB_URL、FileBackend 讀 raw parquet、get_ticker_news scored_only=False |
| 2026-02-12 | Phase 9 完成：System Prompt 重寫 | 5 區塊結構（分析框架 + 批判思考 + 工具引導 + 輸出標準），移除未用 SYSTEM_PROMPT_SYNTHESIS |
| 2026-02-12 | Phase 9-11 計畫：分析深度提升路線圖 | Prompt 重寫 + Web Search + 數據源整合，源於 PYPL 案例診斷 |
| 2026-02-12 | Anthropic SDK streaming 修復 | `messages.create` → `messages.stream` 繞過 max_tokens>21333 限制 |
| 2026-02-11 | 移除 config.temperature 死欄位 + 記錄 token 上限風險 | code gen 一律用 model max output，HTTP timeout 為已知低風險 |
| 2026-02-11 | Phase 5b 完成：Code Generation Agent + Codex models | Error-correcting retry loop, `/code-model` CLI, gpt-5.2-codex/5.3-codex, 27 tests |
| 2026-02-11 | Phase 5 完成：Code Execution Tool | AST blocklist + subprocess + background mode, 36 tests, tool #18 |
| 2026-02-09 | OpenAI agent max_output_tokens 修正 | 自動設 128K (reasoning) / config.max_tokens (none)，3 new tests |
| 2026-02-09 | Phase 8 完成：Anthropic effort + adaptive thinking 整合 | 6 new tests, config/agent/CLI/events, ~230 LOC |
| 2026-02-09 | Phase 4 完成：AsyncGenerator Event Streaming + SSE | 14 tests, ~240 LOC, Dexter pattern #6 完成 |
| 2026-02-09 | Phase 7 計畫完成：server-side compaction 雙層架構 | Claude beta + OpenAI SDK GA，研究含 LangChain/Dexter 對比 |
| 2026-02-09 | 模型更新：Opus 4.5→4.6，修正 context limits (200K standard, 1M beta) | 全專案 7 檔案更新 |
| 2026-02-08 | Phase 3 完成：ContextManager + Anthropic 整合 + 40 tests | 智慧 context 壓縮，ephemeral/persistent 區分 |
| 2026-02-08 | Phase 2 完成：Scratchpad + 雙 agent 整合 + 32 tests | JSONL 決策紀錄，crash-safe |
| 2026-02-08 | Phase 1 完成：TokenTracker + agent 整合 + 19 tests | `token_usage` 加入 response dict |
| 2026-02-08 | 新增 §2.4 Beads 借鑒；更新 Phase 2-3 實作要點 | 不整合 beads，借鑒 5 個模式 |
| 2026-02-08 | 確認實作順序 1→2→3→4→5→6；決策不用 LangChain | 框架: 獨立 SDK + 自建 dispatch |
| 2026-02-08 | 初始版本，記錄現狀和 Phase 1-6 規劃 | 基於 gap analysis 和設計討論 |
