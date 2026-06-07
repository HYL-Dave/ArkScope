# Design Docs Consolidation Review

**Created**: 2026-05-03
**Trigger**: docs governance audit (`docs/design/DOCS_GOVERNANCE_AUDIT_2026_05.md`)
deferred large-file classification to a read-driven pass after a
mechanical-archive attempt revealed that filename-level classification
was making content judgments without reading. This doc is the operating
tracker for the read-driven pass.
**Status**: in progress — pending file-by-file read + discussion + classification.

> **Update 2026-06-03**: RL→agent integration retired (commits 94861f7+6b49c74); `src/rl/` moved to `training/rl/`. RL path references below (e.g. `src/rl/__init__.py:8`) are historical, pre-move.

---

## What this is

A working journal for reviewing each pre-local-first design doc with
the user. For every candidate file the workflow is:

1. Read full content (in current location — files have NOT been pre-moved)
2. Apply the 5-question rubric below
3. Discuss with user, classify into one of five verdicts
4. Mark status here, take mechanical action in a focused per-Group commit

## What this is NOT

- **Not a duplicate** of `DOCS_GOVERNANCE_AUDIT_2026_05.md`. The audit
  classified by category (e.g. "all docs/analysis/ comparison reports →
  archive"); this doc drills file-by-file with content review.
- **Not a final classification**. It's the journal of the review process —
  rows fill in as files are read.
- **Not a substitute for actually reading the files.** Reading is the point.

---

## Verdict categories (5)

| Verdict | Action | Trigger |
|---------|--------|---------|
| **keep-current** | No move; possibly small cross-ref refresh | File still useful as canonical reference; pivot didn't supersede |
| **extract → canonical** | Read, identify residual facts, fold into named canonical doc, then `git rm` source | Has facts/numbers/observations not yet in canonical, but file as a whole shouldn't guide current work |
| **archive** | `git mv` to `docs/archive/pre_local_first_2026_05/<sub>/`; if the source path was git-crypt encrypted, add archive path to `.gitattributes` to preserve encryption | Has decision history value (rejected approaches, controversial tradeoffs, paused-but-may-resume plans) but should not guide current work |
| **pure delete** | `git rm` only | Content fully absorbed by canonical, no extraction needed; OR pure noise (snapshot / upgrade-note / regenerable-inventory) |
| **defer** | No action; flag for later | Genuinely uncertain after one read; revisit in next round |

`extract → canonical` and `pure delete` both end in `git rm` but differ
in whether content is folded into another doc first. **Decline to invent
extraction destinations** — if no canonical doc owns the residual content,
that's a signal the content is not actually load-bearing and the verdict
is `pure delete`.

---

## Already removed (commit `9ebb934`, 2026-05-03)

These were content-independent classification — no read was needed
because their pollution role was filename-obvious. Removed in
`docs: remove superseded documentation noise`:

| File | Why removed |
|------|-------------|
| `MD_FILES_AUDIT.md` | 2026-01 governance snapshot; descriptions now stale |
| `docs/COMPARISON_TOOLS_UPGRADE.md` | 2026-01 tool-upgrade history; tools at `scripts/comparison/` still active, `--help` is the current source |
| `docs/data/SCORING_DATA_INVENTORY.md` | RL-phase scoring row inventory. Not fully duplicated by `DATA_PIPELINE_DOCUMENTATION.md`, but recoverable from live `<data-root>/finrl` CSVs plus `scripts/huggingface/output/README.md`, `scripts/huggingface/column_mapping.md`, and `scripts/huggingface/merge_for_release.py`; no extraction needed. |
| `docs/strategy/SIDEQUEST_CLAUDE_CODE_PLUGINS.md` | 2026-01 Claude Code plugin survey; ecosystem evolves too fast |
| `scripts/huggingface/github_issue_draft.md` | Generated GitHub-issue draft; untracked, worktree-only `rm` |

If any tracked file's content is needed: `git show 9ebb934~1:<path>`.

---

## Reading rubric (apply to every file)

1. **Claim**: what does this file claim to describe?
2. **Absorption**: is that claim absorbed by canonical docs (`LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`, `LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md`, `PROJECT_PRIORITY_MAP.md`, `RL_COLLAPSE_FINDINGS.md`, `DOCS_GOVERNANCE_AUDIT_2026_05.md`)?
3. **Completeness**: complete or partial absorption? List specific facts/numbers/observations NOT in canonical.
4. **Destination**: if partial, which canonical doc owns the residual content (or: residual content not load-bearing, no destination)?
5. **Verdict**: one of the five categories above.

---

## Reading order (5 Groups)

By context: external positioning → architecture vision → plans/roadmap →
storage/data → research artifacts. Smaller groups first to build
calibration before the longer research-data tail.

`enc` = git-crypt encrypted (decryption is automatic locally as long as
git-crypt key is unlocked); `plain` = unencrypted.

### Group 1 — Strategy positioning (2 files, both `enc`)

| # | File | Status | Verdict |
|---|------|--------|---------|
| 1 | `docs/strategy/INTRADAY_TRADING_EVALUATION.md` | done | extract → canonical |
| 2 | `docs/strategy/STRATEGIC_DIRECTION_2026Q1.md` | done | pure delete |

### Group 2 — Architecture vision (4 files, all `enc`)

| # | File | Status | Verdict |
|---|------|--------|---------|
| 3 | `ARCHITECTURE_VISION.md` (root) | done | pure delete |
| 4 | `docs/design/MINDFULRL_ARCHITECTURE.md` | done | pure delete |
| 5 | `docs/design/SERVICE_ARCHITECTURE.md` | done | pure delete |
| 6 | `docs/design/SERVICE_FIRST_EXPANSION_PLAN.md` | done | pure delete |

### Group 3 — Plans & roadmap (3 files, all `enc`)

| # | File | Status | Verdict |
|---|------|--------|---------|
| 7 | `docs/design/MAJOR_REFACTORING_PLAN.md` | done | extract → canonical |
| 8 | `docs/design/PHASE_D_ANALYSIS_PIPELINE_SKETCH.md` | done | keep-current |
| 9 | `docs/design/RL_INFERENCE_SERVICE.md` | done | pure delete |

### Group 4 — Storage & data plans (4 files, mixed)

| # | File | Status | Verdict |
|---|------|--------|---------|
| 10 | `NEWS_STORAGE_DESIGN.md` (root, plain) | done | pure delete |
| 11 | `docs/design/DATA_STORAGE_ACCESS.md` (enc) | done | pure delete |
| 12 | `docs/data/TRADING_FREQUENCY_DATA_STRATEGY.md` (plain) | done | pure delete |
| 13 | `docs/data/L3_DAY_TRADING_FEASIBILITY.md` (plain) | done | pure delete |

### Group 5 — Experiment & research artifacts (8 files, all `plain`)

| # | File | Status | Verdict |
|---|------|--------|---------|
| 14 | `DATA_PIPELINE_DOCUMENTATION.md` (root) | done | pure delete |
| 15 | `docs/analysis/HISTORICAL_ANALYSIS_LOG.md` | N/A | gitignored (never tracked) |
| 16 | `docs/analysis/DEEPSEEK_VS_CLAUDE_COMPARISON.md` | done | pure delete |
| 17 | `docs/analysis/OPENAI_VS_CLAUDE_COMPARISON.md` | done | extract → canonical |
| 18 | `docs/analysis/RISK_SCORE_COMPARISON_REPORT.md` | done | pure delete |
| 19 | `docs/analysis/SENTIMENT_SCORE_COMPARISON_REPORT.md` | done | pure delete |
| 20 | `docs/analysis/SCORING_VALUE_VALIDATION_REPORT.md` | done | extract → canonical |
| 21 | `docs/analysis/SUMMARY_COMPARISON_REPORT.md` | done | pure delete |

---

## How to use this doc

1. Pick the next `pending` file by Group order.
2. Assistant reads file; user reads / asks questions / verifies project state as needed.
3. Apply rubric, discuss, agree on verdict.
4. Update the file's row: `Status` → `done`; `Verdict` → one of five categories.
5. Append a short rationale below in **Per-file rationale log** (1–3 sentences per file).
6. When a Group is complete, do the mechanical action(s) for that Group in a single focused commit (suggested message form: `docs: consolidate Group <N> — <verdict-summary>`).
7. Move to next Group.

**Don't batch beyond a Group.** Mixing extract / archive / delete across
all 21 in one commit defeats the point of the read-driven approach.

---

## Per-file rationale log

(Filled in as files are reviewed. One short section per file in
file-number order. Format: `### <#> <filename> — <verdict>` then 1–3
sentence rationale + key facts extracted (if any) + destination doc.)

### 1 `docs/strategy/INTRADAY_TRADING_EVALUATION.md` — extract → canonical

**Claim**: 評估盤內交易擴展（15-30 min 決策節奏，半自動掛單）所需的數據源、LLM 評分粒度、訂閱成本，並提出 Phase 1-4 實作路徑。

**Absorption**: 大部分未被吸收 — local-first spec 不討論交易頻率，priority map §10 也無此 decision。盤內交易方向在 2026-05 pivot 後已不再指導工作。**例外**: §3.0 IBKR 限制完全被 `data_sources/IBKR_GUIDE.md` 取代且更詳盡（含校準日期、per-stock 抓取時間）。

**Residual fact worth preserving**: Finnhub 免費新聞「文檔說 1 年 vs 實測 ~7 天」(2025-12-14 實測：2024/01、2023/01、2022/01 查詢均返回 0 篇) + 建議改用 Polygon 免費版作為歷史新聞替代。`IBKR_GUIDE.md:514` 表格僅記錄「7 天」此單一數值，未含反差脈絡 / 測試方法 / workaround 推薦。

**Destination**: 新建 `data_sources/DATA_SOURCE_QUIRKS.md`（living doc，未來其他 data source 的「文檔 vs 實測」差異也進此檔）。

**Rejected residuals (intentionally not extracted)**: 三方案成本表 (gpt-5.x 模型/定價已過時)、情緒衰減 Python code (RL paused 狀態下未驗證採用)、Phase 1-4 實作順序 (盤內方向已凍)、Dexter/FinRL 整合架構建議 (pivot 後 framing 錯位)。

**Mechanical action**: (1) 建 `data_sources/DATA_SOURCE_QUIRKS.md` 含 Finnhub finding；(2) `git rm docs/strategy/INTRADAY_TRADING_EVALUATION.md`。在 Group 1 commit 一併執行。

### 2 `docs/strategy/STRATEGIC_DIRECTION_2026Q1.md` — pure delete

**Claim**: 2026 Q1 策略方向決策。基於「7 個 LLM 情緒模型相關性均 < 0.03」回測結果，評估 4 方向後採「多因子信號 + FinRL 整合」混合策略，附 Phase 1-3（週 1-6）todo。

**Absorption**: §1 empirical 引用值（7 模型相關性表 + Score 5 next-day return）原始來源在 `OPENAI_VS_CLAUDE_COMPARISON.md` (Group 5 file #17，待審)，本檔只是引用彙整。本檔原創內容 = 4 方向比較推理 + Phase plan + todo 進度。

**Why pure delete (not archive)**: local-first pivot 不只暫停這條路，是**手段本身已失效** — (a) 多信號規則的觀察未來會搭配 agents 開發新工具實現，不再走 `src/signals/` 這套靜態規則路線；(b) RL 模型能力目前不足以作為決策參考，整個 FinRL 整合假設崩塌。Q1 framing 對「workbench 應該長什麼樣」此問題沒有指導價值。

**Residual not extracted**: 無 — empirical 引用待 Group 5 處理 source 檔；4 方向比較 + Phase plan 是 pre-pivot 規劃工件，無自然 destination；`src/signals/` code 的「為何存在」可由 git log + commit messages 重建。

**Mechanical action**: `git rm docs/strategy/STRATEGIC_DIRECTION_2026Q1.md`。在 Group 1 commit 一併執行。

### 3 `ARCHITECTURE_VISION.md` — pure delete

**Claim**: 2025-12 起草的整體願景（1062 行，2025-12-13 創 / 2025-12-26 v1.3）：「三層智慧架構」(即時 Reactive / 累積 Analytical / 人類 Intuitive) + 統一數據持久層 + 多 LLM Provider router (OpenAI/Anthropic/Gemini/Grok) + 數據源訂閱策略 + 雙層情緒設計（快/慢因子）+ AI Agent 與交易路徑分離 (schema-first / Pydantic) + Quiver 國會交易 + Phase 1-4 路線圖。

**Absorption**: 12 個主要章節 100% 被 canonical 取代或證實不適用：(a) 三層 framing → local-first 5-layer 架構取代（SPEC grep 0 命中）；(b) 數據源優先級 → `DATA_SOURCES_EVALUATION.md:15`「IBKR 主力 (2025-12 新增)」；(c) IBKR 新聞特性 (Dow Jones/0.5s/1月) → `IBKR_GUIDE.md:452-518` 更詳細；(d) Finnhub 7-day → Group 1 已抽至 `DATA_SOURCE_QUIRKS.md`；(e) Quiver → `DATA_SOURCES_EVALUATION.md:1219-1222` 明確記錄 2026/01 程式碼已刪除；(f) Schema-first / Agent-trading 分離 → workbench 已無交易層，前提消失；(g) 4-provider router、雙層情緒、Reactive/Analytical 代碼示例均未落地 src/；(h) LLM 訂閱 (gpt-5-mini primary) 已升級至 Opus 4.6 / gpt-5.4；(i) Phase 1-4 路線圖被 `PROJECT_PRIORITY_MAP.md` 取代。

**Why pure delete (not archive)**:
- archive verdict 在 tracker 定義是「rejected approach / contested decision history / paused-but-may-resume plan」；本檔是「過時 prose 願景」，沒有 contested decision。
- **內含主動誤導資訊**：L941 寫 Quiver「✅ 已整合」，實際程式碼 2026/01 已刪。archive 不能解決誤導 — 任何 future reader 仍會誤以為仍是參考，除非每位讀者都先檢查 commit message 知道是 frozen snapshot。
- 抽取替代方案不適用：所有可抽取的具體 facts 都已在 IBKR_GUIDE / DATA_SOURCES_EVALUATION / DATA_SOURCE_QUIRKS 中以更具體形式存在，**0 個** residual。
- 歷史可達性：`git show <pre-delete-commit>:ARCHITECTURE_VISION.md` 完整保留。

**Residual not extracted**: 無 — Absorption 表已逐項驗證。

**Mechanical action**: (1) `git rm ARCHITECTURE_VISION.md`；(2) 移除 `.gitattributes` 第 5 行 `ARCHITECTURE_VISION.md filter=git-crypt diff=git-crypt`（避免 dangling rule）。在 Group 2 commit 一併執行。

### 4 `docs/design/MINDFULRL_ARCHITECTURE.md` — pure delete

**Claim**: 1624 行（2026-01-25 創、文末 v1.9）核心架構文件。framing 為「三大主體 (Passive RL / Active Agent / 半主動 Monitor) + 共享工具層 + Supabase 三層儲存 + Dexter 模式借鑑 20+ + Data Freshness Registry 設計 + 三層記憶 + 完整數據源全景 + user_profile.yaml 個人化」。13 章 + 附錄 + 兩處版本號不一致 (頭 v1.5 / 尾 v1.9)。

**Absorption**: 13 章逐項驗證：(a) §1-4「三大主體 / 主體關係 / 工具層 / 數據流」→ SPEC + AUDIT 0 grep 命中，被 local-first 5-layer 完全取代；(b) §5 目錄結構 (`src/agent/`、`.mindful/`) 沒落地（實際 `src/agents/`、`src/workbench/`）；(c) §6 Dexter 模式 20+ 借鑑 → `AI_AGENT_ARCHITECTURE_PATTERNS.md` (active, audit keep) 完整收錄 18+ patterns；(d) §7 Supabase 儲存 → SPEC §4 改為 SQLite (workbench.db + sa_cache.db) + transient DuckDB，Supabase 方向正式退場；(e) §8 Phase 1-5 路線圖 → `PROJECT_PRIORITY_MAP.md` 取代；(f) §9 三層記憶 (Working/Episodic/Semantic) future → episodic 已實作 (sql/004 + `data/agent_memory/`, AUDIT L93)，三層 framing 沒採用；(g) §10.1-10.4 動態工具聚合 / 條件式 Compaction / 三層數據優先順序 / 擴展 Scratchpad → PATTERNS doc + 實作的 ContextManager 取代；(h) §12 完整數據源全景 → `DATA_SOURCES_EVALUATION.md` 取代；(i) §13 user_profile.yaml → SPEC / AUDIT 多次引用為 canonical 元素。

**Why pure delete (not archive, not extract → canonical)**:
- **§10.5/§10.6/§11 看似候選 residuals 已被驗證為「已落地」**：
  - §10.6 核心教訓「真相來源是數據本身、不是 stats JSON」**已體現在 `src/tools/freshness.py` + `src/tools/backends/db_backend.py:1077-1131` 的 `query_health_stats()` 設計**：直接 `SELECT MAX(published_at) FROM news`、`MAX(datetime) FROM prices`、`MAX(date) FROM iv_history` — 完全不依賴任何 stats JSON / metadata file。Code 是 lesson 的真正載體。
  - §10.5 Dexter 實測觀察 + 2026-02-07/14/23 changelog → `AI_AGENT_ARCHITECTURE_PATTERNS.md` 已將 patterns 吸收。Dexter 持續演進的 changelog 是外部資訊歷史，git history (`git show <pre-delete>:`) 可取回。
  - §11 Dexter 檔案結構分析 → PATTERNS doc 引用此為來源；patterns 本身已抽象到 PATTERNS doc，原 prose 是研究筆記，git history 足夠。
- **archive 不適用**：1624 行 prose 主要是過時 framing（Supabase、三大主體、`.mindful/`、`src/agent/` 單數、Phase 1-2 ✅ 完成的 stale status）。即使放 archive，未來 reader / agent 仍會被高污染歷史 context 誤導；archive path 對 reader 的「historical」訊號不足以對抗 1624 行 active-looking prose。
- **完全避開 git-crypt archive path 配置擴張**：當前 `.gitattributes` 不覆蓋 `docs/archive/**`；archive 此檔需新增 pattern，引入額外複雜度而無對應收益。
- **extract → canonical 不需要**：唯一 conceptual residual (§10.6 真相來源原則) 已是 code 的設計原則；建 new doc 反而會 duplicate 已落地的 invariant。

**Residual not extracted**: 無 — Absorption + 已落地驗證表已逐項覆蓋。

**Active backref handling**:
- inline 修補 (Group 2 commit 內): `README.md:774` (architecture pointer list 移除或改指 `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`); `AI_AGENT_ARCHITECTURE_PATTERNS.md:4` 標頭 (改指 `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`，符合 audit L388 second-commit-refresh 規劃)
- defer 到 Group sweep: `AGENT_EVOLUTION_TRACKER.md:27/1373/1382` (前置文件 list 含多個 Group 3 待審檔，等齊一併刷新)
- 依賴 file #5 verdict: `SERVICE_ARCHITECTURE.md` 11 處 (若 #5 也 archive/delete，自動解決；若 keep，必須一併更新)
- 不處理: `docs/design/archive/README.md` (intentional historical pointer)

**Mechanical action**: (1) `git rm docs/design/MINDFULRL_ARCHITECTURE.md`；(2) `README.md:774` inline 修；(3) `AI_AGENT_ARCHITECTURE_PATTERNS.md:4` 標頭 inline 修。在 Group 2 commit 一併執行。

### 5 `docs/design/SERVICE_ARCHITECTURE.md` — pure delete

**Claim**: 997 行（2026-02-01 v1.0）service-mode 運行架構文件，定位為 #4 的姊妹文（「系統怎麼跑」對「做什麼」）。12 章 + 附錄：兩種行為模式（On-demand + Continuous）+ 進程模型（單進程 asyncio）+ Service 生命週期 + 排程設計（含市場時間）+ 內部 API 端點清單 + Worker pattern（`BaseWorker` 抽象 + 腳本對應）+ FreshnessRegistry 設計重述 + `.mindful/` 目錄 + 錯誤恢復降級 + systemd 部署 + 技術選型（FastAPI / APScheduler / SQLite job store）+ Phase 0-4 遷移路徑 + MVS 定義。

**Absorption**: 12 章逐項：(a) §0 兩種行為模式 → SPEC v1 是 read-only UI prototype，無 continuous 模式，**與 local-first 直接矛盾**（audit L116 對 SERVICE_FIRST_EXPANSION_PLAN 用詞「Direct contradiction with current direction」同樣定性適用）；(b) §2 進程模型 / §3 啟動順序 / §9 systemd → SPEC L102 (FastAPI+Jinja2+HTMX) + AUDIT §A/B/C daemon model **deferred**；(c) §4 排程 + §10 技術選型 → SPEC L735「APScheduler/Celery/Dramatiq/Prefect 選擇 deferred 直到 model 決定」；(d) §5 API 層 → `src/api/` 已 active 演進，prose 清單不是 source of truth；(e) §6 Worker pattern + BaseWorker → **沒落地**（`src/workers/` 不存在；`src/service/` 只有 `job_runs_store.py` + `macro_calendar_health.py` 等 SA-related，無 BaseWorker class）；(f) §7.2 FreshnessRegistry「真相來源是數據本身」原則 → 已實作 `src/tools/freshness.py` + `db_backend.query_health_stats()` 直接 `SELECT MAX(...)` 而非讀 stats JSON（與 #4 同處驗證）；(g) §7.3 `.mindful/` 目錄 → SPEC §4 改為 profile dir + `workbench.db` / `sa_cache.db` / `data/`；(h) §8 錯誤恢復降級 + 冪等性 → 通用工程實踐，不需要 prose 保留；(i) §11 Phase 0-4 + §12 MVS → `PROJECT_PRIORITY_MAP.md` 取代。

**Why pure delete (not archive)**:
- Audit verdict 預設 archive（L118），但與 #4 同邏輯——避免 archive 路徑保留 997 行的過時 framing（systemd / Worker pattern / `.mindful/` / Supabase 規劃 / Phase 0-4 / MVS）持續污染。
- **0 個 non-recoverable assets**：freshness lesson 已落地為 code；Worker pattern 從未實作；API 端點清單 active 演進中；通用工程實踐（錯誤降級 / 冪等）需要時直接寫不需要 prose；§11 Phase plan 被 priority map 取代。
- **整體 framing 與 local-first 直接矛盾**：「Service-first 持續模式 + multi-client + 24/7 service」vs.「單人 local research workbench, UI 關閉時可選 daemon」是兩個方向。Audit 本身用 superseded 字眼。

**Residual not extracted**: 無 — Absorption + 已落地驗證表已逐項覆蓋。

**Active backref handling**:
- inline 修補 (Group 2 commit 內): `README.md:774` (與 #4 同一行，三檔合併修補 — 包括預先處理 Group 4 file #11 `DATA_STORAGE_ACCESS.md` 因 audit L119 verdict 也是 archive，避免 Group 4 commit 又回來修同一行)
- defer 到 Group sweep: `AGENT_EVOLUTION_TRACKER.md:29` (tree diagram 列)
- defer 到 Group 3 file #9: `RL_INFERENCE_SERVICE.md:492` (audit L121 verdict 也是 archive；該檔 verdict 出來後一併)
- 自然消滅: `MINDFULRL_ARCHITECTURE.md` (file #4 同一 commit delete)；本檔對其他檔的 N 處引用 (本檔 delete 後自然消滅)

**Mechanical action**: (1) `git rm docs/design/SERVICE_ARCHITECTURE.md`；(2) `README.md:774` 整行修補（與 #4 合併）。在 Group 2 commit 一併執行。

### 6 `docs/design/SERVICE_FIRST_EXPANSION_PLAN.md` — pure delete

**Claim**: 232 行（2026-04-21 創 / 2026-04-22 更新；Phase S1 骨架完成 + S2 規劃中）。10 章：why exists → target shape (multiple clients: CLI/Discord/SA Ext/Future web UI/Future OpenClaw) → service boundary (`analysis`/`reports`/`seeking_alpha`/`jobs`) → first slice (5 SA endpoints + jobs control 2 endpoints) → roadmap S1-S4 → design rules → immediate tasks → S1 實作狀態 (5 tasks 全 ✅) → S2 前置（與 MAJOR_REFACTORING 協調）。

**Absorption**: 10 章逐項：(a) §1-2 「service core with multiple clients」整體 framing → audit L116 用詞「**Direct contradiction with current direction**」，local-first 反轉成「single-user local research workbench」；(b) §3-4 Service Boundary + First Slice (SA endpoints + jobs control) → **S1 已落地為 code**：`src/api/routes/seeking_alpha.py` (3.9KB) + `src/api/routes/jobs.py` (5.3KB) + `src/service/jobs.py` (28.7KB) + `tests/test_service_api_slice.py` (200 行) — 已 verified；(c) §6 Phase S2「persist job run history in DB」→ `PROJECT_PRIORITY_MAP.md` **P0.2 self-contained 取代** (含 `job_runs` + `job_definitions` schema、acceptance criteria、week 1 sequencing、dependency 圖 P0.2 → P1.5 → P2.3)；(d) §6 Phase S3 (web control plane) → local-first workbench UI 取代；(e) §6 Phase S4 (multi-client / OpenClaw / Discord 統一) → 方向已被 local-first 反轉；(f) §7 Design Rules → product-level API 設計通則，可從 src/api/routes/ 推導；(g) §8-9 Immediate Tasks + S1 實作狀態 → code + git log 是 source of truth；(h) §10 S2 前置 → priority map dependency graph 已涵蓋。

**Why pure delete (not archive)**:
- Audit verdict 預設 archive（L116），但 audit 用詞「**Direct contradiction with current direction**」是 Group 2 最強——archive 路徑會持續污染 future direction 判斷（即使體量 232 行小）。
- **0 個 non-recoverable assets**：S1 已落地為 code (source of truth)、S2 已被 priority map P0.2 self-contained 取代、S3-S4 方向反轉。
- 與 #4/#5 推理一致：directional contradiction 文件不適合 archive。Archive 適用於「rejected approach / contested decision history / paused-but-may-resume plan」，但「Direct contradiction」是更強的反向定性。

**Residual not extracted**: 無 — Absorption 表已逐項覆蓋。

**Active backref handling**:
- inline 修補 (Group 2 commit 內): `PROJECT_PRIORITY_MAP.md:380` §12 Reference list 移除該行（active canonical，不能留 dangling）
- defer 到 Group sweep: `AGENT_EVOLUTION_TRACKER.md:15/38/1443` (前置文件 list / tree diagram / 2026-04-21 timeline entry)
- defer 到 Group 3 file #7: `MAJOR_REFACTORING_PLAN.md:10/49` (audit verdict = archive；該檔 verdict 出來後一併)
- 自然消滅: `SERVICE_ARCHITECTURE.md` (file #5 同 commit delete)

**Mechanical action**: (1) `git rm docs/design/SERVICE_FIRST_EXPANSION_PLAN.md`；(2) `PROJECT_PRIORITY_MAP.md:380` inline 移除。在 Group 2 commit 一併執行。

### 9 `docs/design/RL_INFERENCE_SERVICE.md` — pure delete

**Claim**: 492 行（2026-04-10 創、2026-04-25 自標 PAUSED）。RL 推理引擎 productionization roadmap（Phase 0 資料源修正 / 1 指標 DB 化 / 2 推理引擎核心 1475 維 / 3 信號記錄 rl_predictions schema / 4 API endpoints / 5 OpenClaw 整合 / 6 持倉模擬）。全部 Phase 0-6 在 PAUSED 狀態。

**Absorption**: (a) PAUSED rationale → `RL_COLLAPSE_FINDINGS.md` (353 行專用 canonical doc, 含 VecNormalize 修復、OOS NOT proven、Decision Record §11、resume criteria) + `PROJECT_PRIORITY_MAP.md` P3.1 (paused + resume gate: reward redesign + walk-forward + multi-seed agreement + baseline outperformance threshold pre-committed)。本檔 L4-6 的 PAUSED banner 是 pointer, 不是 source of truth。(b) Phase 0-6 plans 全是 PG-based schema (rl_predictions / technical_indicators / rl_portfolio 表) → local-first 架構已換 SQLite + DuckDB, RL 如果恢復需 full rewrite 而非 resume。(c) Phase 5 OpenClaw 整合 → local-first 反轉了 multi-client 方向。(d) train/serve 一致性注意事項 (ticker 排序 / stockstats / sentiment 填充) → code-derivable (training/envs/ + prepare_training_data.py)。

**Why pure delete (not archive)**:
- 本檔定位不是「RL 暫停等待復活」而是「RL productionization 這條線不再是 ArkScope 主軸」。未來自動化定位 = ArkScope-owned local agent + scheduler first；外部 operator (Codex app / Claude cowork) second。OpenClaw integration + API service + PG schema 路線完全不一致。
- 如果 RL 恢復(priority map P3.1 gate)，starting point 是 `RL_COLLAPSE_FINDINGS.md` (canonical) + 基於 local-first 架構的新 design，不是本檔的 PG-based Phase 0-6。
- archive verdict (tracker 定義: paused-but-may-resume plan) 表面適用，但實質上 resume criteria 在 RL_COLLAPSE_FINDINGS + P3.1，不在本檔。

**Residual not extracted**: 無。

**Active backref handling**:
- inline 修補 (Group 3 commit 內): `RL_COLLAPSE_FINDINGS.md:6` (Related link → 改為「inference roadmap retired; pause rationale lives in this document」); `src/rl/__init__.py:8` (doc pointer → 改指 `RL_COLLAPSE_FINDINGS.md`)
- defer 到 Group sweep: `AGENT_EVOLUTION_TRACKER.md`
- 不處理: `docs/design/archive/README.md` (archive internal)

**Mechanical action**: (1) `git rm docs/design/RL_INFERENCE_SERVICE.md`；(2) `RL_COLLAPSE_FINDINGS.md:6` inline 修；(3) `src/rl/__init__.py:8` inline 修。在 Group 3 commit 一併執行。

### 7 `docs/design/MAJOR_REFACTORING_PLAN.md` — extract → canonical

**Claim**: 409 行（2026-04-14 創、2026-04-22 更新）。Phase 0/A/B/C/D 統一重構計畫 + 參考來源 + 跨 Phase 依賴 + Service-first 協調 + 風險評估 + 驗證策略。

**Absorption**: 逐 Phase：(a) Phase 0 (Replay Harness) → P0.1 ✅ done (5e12d63 → 172b5a1)，completed task description = stale；(b) Phase B (Compression) → P1.4 ✅ done (99f90c9 → 95ff3cb)，code 在 `src/agents/shared/compressor/` package (context_compressor.py + layers + overflow_store + types + reducers)，7-layer 結構在 module layout (apply_layer_0..6) + inline docstrings 已 self-documenting；(c) Phase C (Unified Agent) → `PHASE_C_UNIFIED_RUNNER_SPEC.md` 是 canonical，本檔 §C 是 spec 摘要 = redundant；(d) Phase D → `PHASE_D_ANALYSIS_PIPELINE_SKETCH.md` (#8 keep-current) 是 canonical；(e) Service-first 協調 → `SERVICE_FIRST_EXPANSION_PLAN.md` (#6) 已 pure delete；(f) §3 優先順序 + §6 依賴 + §7 風險 + §8 驗證 → `PROJECT_PRIORITY_MAP.md` 取代。

**Residual: Phase A Knowledge Graph (L214-307, ~93 行)** — P2.2 blocked on SA + News maturity。**此 doc 是 Phase A 唯一完整設計**：Priority map P2.2:180 寫 `See MAJOR_REFACTORING_PLAN.md §Phase A.`。不可 pure delete 的關鍵內容：(1) Evidence / Claim / Inference 三層信任契約——防止社群留言直接污染圖譜；(2) Claim lifecycle (observed→triaged→verified→rejected→stale)——是 SA Comment Intelligence Stage 3 下游消費者；(3) 7 edge types + 6 node types + dynamic evolution API——不是「需要時直接寫」能輕鬆重建的信任邊界設計。

**Destination**: 新建 `docs/design/PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md`（含 v2 status banner，格式對齊 #8）。

**Mechanical action**: (1) 新建 `PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md`（Phase A 內容整理為獨立 sketch）；(2) `git rm docs/design/MAJOR_REFACTORING_PLAN.md`；(3) `PROJECT_PRIORITY_MAP.md:180` 修 P2.2 pointer → `PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md`；(4) `PHASE_D_ANALYSIS_PIPELINE_SKETCH.md:3` 修 reference → git-history pointer 或移除。在 Group 3 commit 一併執行。

### 10-13 Group 4 (Storage & data) — all pure delete

**Files**: `NEWS_STORAGE_DESIGN.md` (378 行) / `docs/design/DATA_STORAGE_ACCESS.md` (704 行) / `docs/data/TRADING_FREQUENCY_DATA_STRATEGY.md` (513 行) / `docs/data/L3_DAY_TRADING_FEASIBILITY.md` (768 行). Total 2363 行。

**Why pure delete (all 4)**: (a) #10 NEWS_STORAGE_DESIGN — filesystem + SPEC §4 are source of truth for news parquet layout; §9.4 test data is subset of DATA_SOURCES_EVALUATION L134/309/351; (b) #11 DATA_STORAGE_ACCESS — audit L119: "no daylight between this doc and spec"; PG-first DAL design completely replaced by SPEC §4.5 SQLite DAL Protocol; (c) #12 TRADING_FREQUENCY_DATA_STRATEGY — pre-pivot intraday trading frequency framing ("L4-L5 = your target zone") incompatible with research workbench positioning; (d) #13 L3_DAY_TRADING_FEASIBILITY — day-trading AI Agent feasibility analysis; pivot away from trading execution; IBKR costs are public pricing.

**Residual not extracted**: 無 — all content either in canonical docs (SPEC §4, DATA_SOURCES_EVALUATION) or publicly available (IBKR pricing) or pre-pivot framing.

**Mechanical action**: (1) `git rm` 4 files; (2) inline 修補 6 backrefs: `collect_polygon_news.py` (2 docstrings), `NEWS_DATA_INVENTORY.md` (header), `HISTORICAL_ANALYSIS_LOG.md` (header + remove stale SCORING_DATA_INVENTORY ref), `OPTIONS_FLOW_GUIDE.md` (相關文件 list), `DATA_SUBSCRIPTION_GUIDE.md` (相關文件 list). 同 commit 含 user 手動修補的 `ARKSCOPE_RENAME_PHASE2.md` + `archive/README.md` (final-sweep items pre-resolved)。

### 8 `docs/design/PHASE_D_ANALYSIS_PIPELINE_SKETCH.md` — keep-current

**Claim**: 431 行（status 2026-04-15）。Phase D Analysis Pipeline 的 implementation-oriented sketch — 定義 `src/analysis/` pipeline 的 boundary、contracts (5 dataclasses)、5-step assembly (Context → Strategies → Aggregate → Integrity → Render)、interactive vs batch paths、integrity repair pattern、delivery boundary。

**Why keep-current (not archive, not pure delete)**:
- **有已落地 code**：`src/analysis/` scaffold 已實作 10+ modules（contracts.py / context_builder.py / factory.py / pipeline.py / integrity.py / renderer.py / scheduler_hooks.py / service.py + strategies/ 含 5 strategy modules + templates/ dir）。Sketch 是 code 的 design context — pipeline contract / integrity repair / delivery boundary 這些 code 無法自我說明的設計理由都在這。
- **Architecture-neutral**：contracts 是 pure Python dataclasses，不依賴 PG / Supabase / service-mode / OpenClaw / multi-client。與 local-first 完全相容。
- **v2 candidate 路徑已鎖**：SPEC L10 + §11.1 明確保留 Phase D（analysis pipeline）為 v2 candidate，path layout pre-reserved。workbench v2 如果啟動 analysis pipeline，starting point = 此 sketch + 已有 scaffold。
- **無 pre-pivot 污染**：沒有 Supabase / 三大主體 / `.mindful/` / stale model names / stale Phase status。

**Mechanical action (Group 3 commit 內)**:
1. 檔案頂部加 v2 status banner：`Status: Active v2 candidate / deferred; NOT v1 scope. Canonical product boundary: LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md §11.`
2. 如果 #7 verdict = pure delete → L3 `[MAJOR_REFACTORING_PLAN.md]` 改為 git-history pointer 或移除。

---

## Cross-reference

- Audit: `docs/design/DOCS_GOVERNANCE_AUDIT_2026_05.md` — original
  category-level classification this doc supersedes for the 21 files
  listed above.
- Spec: `docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md` — primary
  canonical destination candidate for absorbed architecture / storage
  decisions.
- Priority map §10: `docs/design/PROJECT_PRIORITY_MAP.md` — destination
  for date-anchored decisions.
- RL findings: `docs/design/RL_COLLAPSE_FINDINGS.md` — destination for
  RL-phase empirical results.
