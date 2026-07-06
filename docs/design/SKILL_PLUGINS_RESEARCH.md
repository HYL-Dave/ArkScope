# Skills & Plugins 架構研究

> **Status: REFERENCE (dated)** — research notes; skills implementation lives in resources/skills/ + src/agents.

> **目的**: 研究 Anthropic Financial Services Plugins 架構，評估如何將類似能力整合到本專案
> **調研日期**: 2026-03-23
> **來源**: [anthropics/financial-services-plugins](https://github.com/anthropics/financial-services-plugins) (Apache 2.0, 6.7k stars)
> **前置**: [AGENT_EVOLUTION_TRACKER.md](AGENT_EVOLUTION_TRACKER.md) Phase 13 (現有 Skills System)

---

## 1. Anthropic Financial Services Plugins 概覽

### 1.1 架構三層

```
Core Layer
  └─ financial-analysis (必裝)
       ├─ 11 MCP data connectors
       ├─ 11 skills (comps, DCF, LBO, 3-statement, ...)
       └─ 基礎建模工具

Add-on Layer (4 業務線)
  ├─ investment-banking (CIM, buyer list, merger model)
  ├─ equity-research (earnings, coverage, catalyst, morning note)
  ├─ private-equity (sourcing, DD, IC memo, KPI)
  └─ wealth-management (client prep, planning, rebalancing, tax-loss)

Partner Layer
  ├─ LSEG (bond, yield curve, FX, options)
  └─ S&P Global (tearsheets, earnings previews)
```

### 1.2 核心數字

| 項目 | 數量 | 說明 |
|------|------|------|
| Skills | 41 | 自動觸發的領域知識（SKILL.md） |
| Commands | 38 | 使用者手動呼叫的 slash commands |
| MCP Connectors | 11 | 外部金融數據源（Daloopa, FactSet, Morningstar, ...） |
| Plugins | 5 core + 2 partner | 模組化業務包 |

### 1.3 Plugin 目錄結構

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json           # 清單 {name, version, description, author}
├── .mcp.json                 # MCP server connections
├── commands/                 # 使用者手動呼叫的 slash commands (.md)
│   ├── comps.md
│   └── dcf.md
├── skills/                   # 自動觸發的領域知識
│   ├── comps-analysis/
│   │   └── SKILL.md          # 500+ 行詳細指引
│   └── dcf-model/
│       └── SKILL.md
└── hooks/                    # Event-driven automation
```

### 1.4 SKILL.md 格式

每個 skill 是一個 Markdown 文件，包含：

```markdown
---
name: comps-analysis
description: Build institutional-grade comparable company analyses...
Perfect for: [適用場景列表]
Not ideal for: [不適用場景列表]
---

## Data Source Priority
1. MCP sources (S&P Kensho, FactSet, Daloopa)
2. Bloomberg / SEC EDGAR (fallback)
3. NEVER use web search as primary

## Core Philosophy
"Build the right structure first..."

## Step-by-Step Verification
...（每個主要段落後向使用者確認）

## Industry-Specific Additions
...（SaaS / Manufacturing / Financial Services / Retail 各自指標）

## Quality Checks
...（品質檢查清單）
```

**本質**：SKILL.md 是詳細的 prompt injection，不是程式碼。技術上等同於我們的 `skills.py` prompt templates，但**深度差 10-20 倍**（我們 ~30 行 vs 他們 ~500 行）。

### 1.5 執行機制

```
Progressive Disclosure:
1. Metadata loading (~100 tokens)  → Claude 掃描可用 skills
2. Full instructions (<5K tokens)  → 確認 skill 適用後載入完整指引
3. Bundled resources               → 需要時才載入附帶的模板/範例

觸發方式:
- 自動: Claude 偵測到任務類型匹配 → 自動注入 skill context
- 手動: /comps NVDA → 直接呼叫 comps-analysis skill
```

---

## 2. 11 MCP Data Connectors

### 2.1 完整列表

| # | 提供者 | MCP URL | 資料類型 | 訂閱 |
|---|--------|---------|----------|------|
| 1 | Daloopa | `mcp.daloopa.com/server/mcp` | 精準財報數據 | 付費 |
| 2 | Morningstar | `mcp.morningstar.com/mcp` | 基本面/評級 | 付費 |
| 3 | S&P Global (Kensho) | `kfinance.kensho.com/integrations/mcp` | 公司資料/估值 | 付費 |
| 4 | FactSet | `mcp.factset.com/mcp` | 財務數據/估值 | 付費 |
| 5 | Moody's | `api.moodys.com/genai-ready-data/m1/mcp` | 信評/風險 | 付費 |
| 6 | MT Newswires | `vast-mcp.blueskyapi.com/mtnewswires` | 即時新聞 | 付費 |
| 7 | Aiera | `mcp-pub.aiera.com` | Earnings call 分析 | 付費 |
| 8 | LSEG | `api.analytics.lseg.com/lfa/mcp` | 債券/FX/衍生品 | 付費 |
| 9 | PitchBook | `premium.mcp.pitchbook.com/mcp` | PE/VC 交易數據 | 付費 |
| 10 | Chronograph | `ai.chronograph.pe/mcp` | PE portfolio | 付費 |
| 11 | Egnyte | `mcp-server.egnyte.com/mcp` | 文件管理 | 付費 |

### 2.2 我們的替代方案

| 他們的 MCP | 我們的替代 | 覆蓋度 | 說明 |
|-----------|-----------|--------|------|
| Daloopa（精準財報） | SEC EDGAR XBRL + Financial Datasets | ✅ 高 | XBRL 免費覆蓋所有 US 股；FD 付費補 Q4+TTM |
| Morningstar（基本面） | `get_detailed_financials()` + IBKR | ✅ 高 | 40+ 指標（EV/EBITDA, ROIC, Rule of 40 等） |
| FactSet（估值/consensus） | Finnhub analyst + IBKR snapshot | ⚠️ 中 | 缺 forward estimates 細節 |
| S&P Kensho（公司資料） | SEC EDGAR + Web Search + Finnhub | ⚠️ 中 | 精度略低但免費 |
| MT Newswires（新聞） | Polygon + Finnhub + IBKR news | ✅ 高 | 三來源 + LLM 評分已整合 |
| Aiera（earnings call） | SEC filings + Web Search | ❌ 低 | 無 earnings call transcript 結構化解析 |
| LSEG（債券/FX） | N/A | N/A | 不在我們的交易範圍 |
| PitchBook（PE data） | N/A | N/A | 不在我們的交易範圍 |
| Moody's（信評） | N/A | N/A | 非核心需求 |
| Chronograph（PE portfolio）| N/A | N/A | 不在我們的交易範圍 |
| Egnyte（文件管理） | 本地檔案系統 | N/A | 不需要 |

**結論**: 5/11 connector 有可用替代，3/11 與我們無關，3/11 有缺口（FactSet consensus, Aiera earnings call, Moody's）。

---

## 3. 41 Skills 適用性分析

### 3.1 Financial Analysis Core（11 skills）

| Skill | 適用? | 說明 |
|-------|-------|------|
| `comps-analysis` | ✅ | 可比公司估值分析 → 加強 `full_analysis` |
| `dcf-model` | ✅ | DCF 估值建模 → 新 skill |
| `lbo-model` | ❌ | LBO 槓桿收購模型 → PE 專用 |
| `3-statement-model` | ⚠️ | 三表建模 → 太重，可簡化版採用 |
| `competitive-analysis` | ✅ | 競爭分析 → 加強行業理解 |
| `audit-xls` | ❌ | Excel 審計 → 無 Excel 產出需求 |
| `clean-data-xls` | ❌ | Excel 清洗 → 同上 |
| `deck-refresh` | ❌ | PPT 更新 → 無 PPT 需求 |
| `ib-check-deck` | ❌ | IB pitch deck QC → 不適用 |
| `ppt-template-creator` | ❌ | PPT 模板 → 不適用 |
| `skill-creator` | ⚠️ | Meta-skill：教 Claude 建新 skill → 參考價值 |

### 3.2 Equity Research（9 skills）

| Skill | 適用? | 說明 |
|-------|-------|------|
| `earnings-analysis` | ✅ | 財報後分析 → 取代/增強 `earnings_prep` |
| `earnings-preview` | ✅ | 財報前預覽 → 補充 `earnings_prep` |
| `catalyst-calendar` | ✅ | 催化劑追蹤 → 全新 skill |
| `idea-generation` | ✅ | 選股篩選 → 加強 `portfolio_scan` |
| `thesis-tracker` | ✅ | 投資論文追蹤 → 利用 episodic memory 系統 |
| `initiating-coverage` | ⚠️ | 首次覆蓋報告 → 太正式，可簡化 |
| `model-update` | ⚠️ | 模型更新 → 需要估值模型基礎 |
| `morning-note` | ✅ | 晨報 → 類似 `portfolio_scan` 但更結構化 |
| `sector-overview` | ✅ | 行業概覽 → 加強 `sector_rotation` |

### 3.3 Investment Banking（~10 skills）— 不適用

CIM drafting, buyer list, merger models, deal tracking, strip profiles 等 — 全部 IB 專用。

### 3.4 Private Equity（~6 skills）— 不適用

Deal sourcing, due diligence, IC memos, KPI monitoring 等 — 全部 PE 專用。

### 3.5 Wealth Management（~5 skills）— 部分適用

| Skill | 適用? | 說明 |
|-------|-------|------|
| `portfolio-rebalancing` | ⚠️ | 再平衡分析 → RL pipeline 未來可能需要（註：RL→agent 整合 2026-06 已下架，見 RL_COLLAPSE_FINDINGS.md） |
| `tax-loss-harvesting` | ⚠️ | 稅務虧損收割 → 與 CPPO risk 相關但目前非核心 |
| `client-meeting-prep` | ❌ | 客戶會議 → 不適用 |
| `financial-planning` | ❌ | 財務規劃 → 不適用 |
| `client-report` | ❌ | 客戶報告 → 不適用 |

### 3.6 適用性總結

| 類別 | 可用 | 部分可用 | 不適用 |
|------|------|----------|--------|
| Financial Analysis | 2 | 2 | 7 |
| Equity Research | 7 | 2 | 0 |
| Investment Banking | 0 | 0 | ~10 |
| Private Equity | 0 | 0 | ~6 |
| Wealth Management | 0 | 2 | 3 |
| **合計** | **9** | **6** | **~26** |

**直接可用 9 個 skills**，部分可用 6 個（需改裝），其餘 26 個不適用。

---

## 4. 我們現有 Skills System 的差距

### 4.1 現有架構（Phase 13, 2026-02-19）

```python
# src/agents/shared/skills.py
class SkillDefinition:
    name: str
    description: str
    prompt_template: str      # ~30 行 prompt
    required_params: List[str]
    aliases: List[str]

# 4 built-in skills:
# full_analysis, portfolio_scan, earnings_prep, sector_rotation

# Custom skills: config/skills/*.yaml (YAML format)
```

### 4.2 差距分析

| 維度 | 我們 | Anthropic Plugins | 差距 |
|------|------|-------------------|------|
| **Skill 深度** | ~30 行 prompt template | ~500 行 SKILL.md（含決策框架、品質檢查、行業特化） | 10-20x |
| **觸發方式** | 僅 `/skill` 手動呼叫 | 手動 + 自動觸發（keyword matching） | 缺自動觸發 |
| **資料來源映射** | "use relevant tools"（隱式） | 明確的 Data Source Priority 區塊 | 缺顯式映射 |
| **Progressive Disclosure** | 無（全量載入） | 100 tokens metadata → 5K full → resources | 缺漸進式載入 |
| **模組化** | Flat list（4 skills） | Plugin 包（按業務線分組） | 缺分組管理 |
| **格式** | Python 硬編碼 + YAML custom | Markdown SKILL.md + JSON manifest | 缺 Markdown 支援 |
| **品質框架** | 無 | Step-by-step verification + sanity checks | 缺品質保證 |
| **雙模型支援** | ✅ 已支援（prompt 注入） | 僅 Claude | 我們更強 |
| **自有工具層** | ✅ 49 tools via registry | MCP 連接器（外部付費服務） | 我們有本地工具 |

### 4.3 核心優勢（我們有、他們沒有的）

1. **雙模型支援** — Anthropic + OpenAI 都能用 skill（prompt injection 天然跨模型）
2. **本地工具層** — 49 tools 直接可用，不依賴外部付費 MCP
3. **Episodic Memory** — skill 分析結論可持久化（`save_memory()`），Anthropic plugins 沒有
4. **Subagent 協作** — skill 可觸發 subagent delegation（reviewer, deep_researcher）
5. ~~**RL Pipeline 整合** — skill 可讀取 RL 模型預測（`get_rl_prediction`）~~ — **歷史（2026-06-03）**：RL→agent 整合已下架（`get_rl_*` 工具移除，commits 94861f7+6b49c74），此優勢不再適用；見 RL_COLLAPSE_FINDINGS.md。

---

## 5. 升級設計建議

### 5.1 Layer 1: Rich Skill Format（SKILL.md 支援）

**目標**: 從 ~30 行 prompt → ~200-500 行結構化 SKILL.md

```
resources/skills/              ← repo-owned（git tracked）
├── builtin/                   Tier 1: hard failure if broken
│   ├── full-analysis/SKILL.md
│   ├── portfolio-scan/SKILL.md
│   ├── earnings-prep/SKILL.md
│   └── sector-rotation/SKILL.md
├── financial-analysis/        Tier 2: packaged（從 Anthropic FSP 改裝）
│   ├── comps-analysis/SKILL.md
│   ├── dcf-model/SKILL.md
│   └── competitive-analysis/SKILL.md
└── equity-research/           Tier 2: packaged
    ├── earnings-analysis/SKILL.md
    ├── catalyst-calendar/SKILL.md
    └── idea-generation/SKILL.md

config/skills/                 ← user-owned
├── custom/                    Tier 3a: 可覆蓋 Tier 2
│   └── .gitkeep
└── *.yaml                     Tier 3b: legacy YAML
```

**SKILL.md frontmatter 擴展格式**:

```markdown
---
name: comps-analysis
description: Build comparable company analyses with valuation multiples
trigger: comps|comparable|peer comparison|valuation comparison
required_params: [ticker]
aliases: [comps, comp]
category: financial-analysis
data_sources:
  required: [get_fundamentals_analysis, get_detailed_financials]
  optional: [search_web, get_sec_filings]
output: report                        # 自動 save_report()
---

# Comparable Company Analysis

## Data Source Priority
1. get_detailed_financials → SEC EDGAR fundamentals (免費)
2. get_fundamentals_analysis → IBKR snapshot (即時)
3. search_web → 補充最新資料

## Workflow
...（詳細步驟 + 決策框架）

## Quality Checks
...（品質檢查清單）

## Industry-Specific Guidance
...（SaaS / Manufacturing / Financial Services 各自指標選擇）
```

**向下相容**: 現有 `config/skills/*.yaml` 繼續支援。新增 `*/SKILL.md` 為 rich format。

### 5.2 Layer 2: Auto-Trigger 機制

```python
class SkillEngine:
    """Model-agnostic skill loader with auto-trigger support."""

    def load_all(self) -> Dict[str, SkillDefinition]:
        """Load from YAML + SKILL.md, parse frontmatter."""

    def auto_match(self, user_query: str) -> Optional[str]:
        """Match user query to skill via trigger keywords.

        使用 frontmatter 的 trigger 欄位做 keyword matching，
        不需 LLM 推理就能快速判斷。
        """

    def expand_for_model(self, skill: SkillDefinition,
                         params: dict,
                         model_type: str  # "anthropic" | "openai"
                         ) -> str:
        """Expand skill prompt, adapting for model context limits.

        - Anthropic (1M context): 注入完整 SKILL.md body
        - OpenAI (1M context): 同上（gpt-5.4 也有 1M）
        - Context 緊張時: 只注入關鍵段落（Progressive Disclosure）
        """
```

**Auto-trigger 流程**:

```
User query: "compare NVDA with AMD and INTC valuations"
  → SkillEngine.auto_match() → 匹配 trigger "comparable|peer comparison|valuation comparison"
  → 自動注入 comps-analysis SKILL.md context
  → Agent 使用 skill 指引 + 本地 tools 執行分析
```

### 5.3 Layer 3: Data Source Mapping

每個 SKILL.md 的 `data_sources` 欄位明確宣告需要哪些 tools。Engine 可做：

1. **驗證**: 啟動時檢查宣告的 tools 都已在 registry 註冊
2. **提示**: 若 optional tool 不可用（如 FD API 未啟用），在 prompt 中提示替代方案
3. **未來擴展**: 若接入新 MCP connector（如 Unusual Whales），自動更新 skill 的可用工具列表

### 5.4 實作路徑

| Phase | 內容 | 工作量 | 依賴 |
|-------|------|--------|------|
| G-1 | SKILL.md 格式支援 — 解析 Markdown frontmatter + body，向下相容 YAML | 小 | 無 |
| G-2 | 現有 4 built-in skills → SKILL.md 格式，enrichment（加深度到 200+ 行） | 中 | G-1 |
| G-3 | Auto-trigger 機制（keyword matching → 自動注入 skill context） | 小 | G-1 |
| G-4 | 從 Anthropic repo 改裝 5-6 個 skills（替換 data sources） | 中 | G-1 |
| G-5 | Progressive Disclosure（context 緊張時只注入關鍵段落） | 小 | G-1 |
| G-6 | Data source mapping + 驗證（registry 整合） | 小 | G-1 |

**G-1 + G-3 是最有價值的**，讓系統從「手動 /skill」→「自動識別任務類型 → 注入最佳 skill」。

---

## 6. 跨模型執行策略

### 6.1 為什麼 Skill 天然支援雙模型？

Skill 本質是 **prompt injection** — 在使用者 query 前面附加領域知識。這與 LLM provider 無關：

```
Final prompt = SKILL.md body + user_query
    ↓
Anthropic API (Claude) → 使用 skill 指引 + 本地 tools 完成分析
    或
OpenAI API (GPT-5.x) → 同上
```

兩個 agent 共用同一套 ToolRegistry（49 tools），skill prompt 中引用的 tool name 兩邊都能識別。

### 6.2 Model-Specific 差異處理

| 差異 | 處理方式 |
|------|----------|
| Context size | 兩家都 1M+ → 通常不需裁剪。若需裁剪，Progressive Disclosure |
| Tool 格式 | Registry 已統一轉換（Anthropic schema / OpenAI function_tool） |
| 思考能力 | Anthropic thinking + OpenAI reasoning → skill 只定義目標，不規定思考方式 |
| 回應風格 | Skill 的 REQUIRED OUTPUT 區塊統一格式要求 |

### 6.3 Subagent 協作

Skill 可宣告建議的 subagent delegation：

```yaml
# SKILL.md frontmatter
subagent_hints:
  - role: reviewer
    when: "after analysis complete, if confidence < High"
  - role: deep_researcher
    when: "if web search needed for catalyst/news"
```

---

## 7. Claude Code / Codex CLI Skills 機制（2026-03-24 補充）

### 7.1 Claude Code Skills

- Skills 是 **CLI-level feature**，不是 API-level feature
- SKILL.md 格式：YAML frontmatter + Markdown body
- 遵循 [Agent Skills](https://agentskills.io) 開放標準
- Progressive Disclosure：description 常駐 context（2% window budget），full body 按需載入
- 一次一個 skill（不同時注入多個）
- 支援 `context: fork`（subagent 執行）、`allowed-tools`（限制工具）、`$ARGUMENTS` 替換
- `disable-model-invocation: true` 可阻止自動觸發
- 直接 `/<name>` 觸發（無需 `/skill` prefix）

### 7.2 OpenAI Codex CLI Skills

- 也支援 SKILL.md（同一 Agent Skills 開放標準）
- 用 `$skill-name` 觸發
- 掃描 `.agents/skills/` 目錄
- 支援 auto-select based on prompt

### 7.3 API 層面

**Skills 與 API 無關** — 兩家的 skills 都是 CLI 層的 prompt injection，API 只是收到更長的 prompt。
我們的 Phase G 做的事情等價於 Claude Code/Codex CLI 的 skill 機制。

---

## 8. 外部整合策略：API vs MCP（2026-03-24 決策）

### 8.1 使用場景定位

```
本專案 = 智慧核心                     OpenClaw = 跨系統調度者
─────────────────                    ──────────────────────
49 tools + skills                    呼叫本專案 HTTP API
CLI/Discord 直接使用                  操控 email、監測世界事件
標準分析流程（更精確、低隨機性）         跨系統 bug tracking、自動化
DB 查詢等小事直接做                   複雜多步驟調度 → 結果轉 Discord
```

### 8.2 Standard API 優先，MCP 可選

**優先擴展現有 FastAPI**（`http_api.py`）：
- 已有 FastAPI 基礎設施，擴展成本極低
- OpenAPI spec 自動生成 → 任何 client auto-discover
- Perplexity 公開宣布脫離 MCP，MCP 維護成本高
- **MCP 不排除但需評估必要性**

### 8.3 Skills 的分工

| 本專案 Skills | OpenClaw Skills |
|--------------|----------------|
| comps_analysis, dcf_model | monitor-world-events |
| earnings_analysis, catalyst_calendar | check-email-alerts |
| full_analysis, portfolio_scan | cross-project-synthesis |
| idea_generation, competitive_analysis | bug-tracking-workflow |

- 本專案 skills = 金融分析領域知識 → CLI/Discord 直接使用 + API 內部指引
- OpenClaw skills = 跨系統調度知識 → 整合本專案 + 其他來源
- SKILL.md 內容 source-compatible，但 tool names 綁定本專案，需適配

---

## 9. 參考連結

- [anthropics/financial-services-plugins](https://github.com/anthropics/financial-services-plugins) — 主倉庫（Apache 2.0, 6.7k stars）
- [Claude Code Skills Docs](https://code.claude.com/docs/en/skills) — 官方 skill 文檔
- [Codex Skills Docs](https://developers.openai.com/codex/skills) — OpenAI Codex skill 文檔
- [OpenAI Skills GitHub](https://github.com/openai/skills) — Codex Skills Catalog
- [CLAUDE.md (plugins repo)](https://github.com/anthropics/financial-services-plugins/blob/main/CLAUDE.md) — 插件開發指南
- [Anthropic Finance Plugin Page](https://claude.com/plugins/finance) — 官方頁面
- [BlockTempo 報導](https://www.blocktempo.com/anthropic-claude-financial-services-plugins-41-skills-11-data-providers/) — 中文報導

---

*最後更新: 2026-03-25*