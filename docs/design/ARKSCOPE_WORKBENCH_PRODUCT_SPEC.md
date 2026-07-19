# ArkScope Workbench — Product Spec (canonical)

**Date**: 2026-06-04
**Status**: CANONICAL product authority (**adopted 2026-06-04**). First of three canonical docs; companions `ARKSCOPE_PROVIDER_CATALOG.md` + `ARKSCOPE_TOOL_CATALOG.md` (both adopted). Supersedes product framing scattered across older docs.

**Authority hierarchy** (read before editing):
- On **architecture / storage / sync / page-IA / migration** conflicts → [`LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`](LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md) wins. This doc does **not** re-arbitrate those.
- On **per-provider facts** (data, latency, streaming, cost, limits, config) → `ARKSCOPE_PROVIDER_CATALOG.md`.
- On **per-tool facts** (the registry tools: keep/adapt/drop, params) → `ARKSCOPE_TOOL_CATALOG.md`.
- This doc **owns**: product identity, the AI output contract, agent capability boundaries, the permission model, and cross-cutting product principles (reasoning posture, real-time/charting stance, local-first posture).

> 中文摘要：這是 ArkScope 的「產品憲法」。架構/儲存看 SPEC，資料源看 ProviderCatalog，工具看 ToolCatalog；本文件只鎖**產品定義 + agent 能力邊界 + AI 輸出契約 + 權限模型 + 核心原則**。三份 canon 寫完才開始做 desktop app 殼。

---

## 0. What this doc locks vs defers

**Locks (5)**:
1. Product identity + name (§1).
2. The AI output contract as product law (§2).
3. Reasoning posture — what the agent is *for* (§3).
4. Agent capability-boundary model: presets + advanced override + permission model (§4).
5. Core product principles: data/real-time stance, local-first posture (§5, §7).

**Defers (named so deferral is explicit, not silent)**:
- Desktop shell tech stack (Electron / Tauri / web+local-server) — decided at shell kickoff, after the 3 canon docs.
- Final product **brand** rename — gated on workbench v1 ship (SPEC §0; VISION §0). v1 ships as **ArkScope**.
- Multi-market scope, web-search backend, plugin-install scope, light theme, multi-workspace — open; tracked in `DESKTOP_APP_VISION_DRAFT.md` §6–§7. Not re-opened here.
- Embedded/stealth browser + code/doc knowledge-graph tooling — deferred **spikes** (§7).

---

## 1. Product identity (LOCK #1)

### 1.1 North star (inherited from SPEC §1.1, not re-litigated)

> The agent reads its own accumulated knowledge substrate across sessions and machines; the user sees and edits everything via a research GUI; zipping the profile directory moves a researcher's work between machines.

### 1.2 One-paragraph definition

ArkScope is a **local-first, BYOK, no-sign-in desktop financial-research agent workbench**: a controllable agent + a stable tool layer + multi-provider financial data + a portable local profile, presented as a dark multi-panel research cockpit. The agent is the connective tissue embedded in every page — not a separate chat tab — and its conclusions are structured, cited, and traceable (§2).

### 1.3 Name (LOCK)

- Single name: **ArkScope**. This product surface is referred to as **"ArkScope Workbench."**
- **No fourth name.** `AIRA Desk` / `ARK Desk` (sketch artifacts) are NOT product names. The lowercase `mindfulrl` identifiers (DB name, native-host id, addon id, historical docs) are intentionally kept (SPEC §1.5) and are NOT product-facing.
- Internal storage identifiers (profile dir name, `workbench.db` etc.) remain the SPEC's `workbench` placeholder for v1 — renaming them is a trivial deferred detail (SPEC §3.1), not a v1 task.

### 1.4 What ArkScope is NOT (LOCK; extends SPEC §1.4)

Not high-frequency trading. Not an RL trading system (retired; lives offline under `training/`, not surfaced in UI). Not a backtest-farm UI. **Not a re-scoring engine** (§3). Not multi-user / cloud-sync. Not live order entry (informational only). One user, one machine, one writer at a time.

### 1.5 Terminology (EN / 繁體中文 — both interfaces ship; LOCK)

The single terminology authority is
[`ARKSCOPE_TERMINOLOGY.md`](ARKSCOPE_TERMINOLOGY.md). It owns canonical pairs,
mixed professional-language rules, and the distinction among Universe, Pool,
Watchlist, and Holdings. This Product Spec does not duplicate that table.

English and Traditional Chinese remain target interfaces. Runtime locale
selection and string externalization are owned by the separately sequenced
[`app-wide i18n decision`](../superpowers/specs/2026-07-20-app-wide-i18n-decision.md),
not by this product-definition section.

---

## 2. The AI output contract (LOCK #2 — the product's core differentiation)

Free-form chat is allowed as the *interaction medium*. A **quick factual answer may be short** (e.g. "what's NVDA's P/E?"). But **any output that bears a judgment, a recommendation, a saved artifact, a comparison, or a trading view MUST conform to this contract** — fixed schema + traceability. This is the single most differentiating product property; it is elevated here from `DESKTOP_APP_VISION_DRAFT.md` §3 to product law. The typed schema + renderer is the contract boundary, and the reasoning layer stays provider/tool-agnostic at that boundary.

### 2.1 Fixed-schema result card

Every conclusion carries fixed fields (not prose-only):
> Conclusion · Primary reasons · **Counter-thesis (反方理由)** · Key assumptions · **Trigger conditions** · **Invalidation conditions** · Risks · Watch list · Data sources · Analysis time · **Confidence / data-completeness**.
> (Trading-oriented cards additionally carry: core observation · action suggestion · trend outlook · **key levels** — ideal entry / secondary entry / stop / upside target.)

### 2.2 Decisional-question contract

A card is only "useful" if it can answer the decisional questions (more fundamental than the field list):
- Where does my current judgment differ?
- What is the main narrative / market consensus?
- What is the invalidation signal?
- What should I watch next?
- **What changed vs the last analysis?** (implies thesis history/versioning.)

### 2.3 Per-claim traceability

Every conclusion declares: which data was used · the data's as-of time · **is it real-time?** · **is it single-model inference?** · whether news/fundamentals/technicals were complete. Consistent with `src/tools/freshness.py` ("truth is the data itself").

### 2.4 AI card generation contract

Decision-bearing AI cards are generated by a three-stage path:

1. **EvidencePacket** — deterministic collection of objective, source-labeled evidence before any LLM synthesis.
2. **Structured synthesis** — the LLM integrates the evidence into conclusion / counter-thesis / triggers / invalidation / watch-list fields.
3. **Validated ResultCard** — the output must pass the typed schema before it can be rendered or saved.

The EvidencePacket is the boundary that prevents hidden re-scoring. It may normalize and classify data, but it must not pre-bake the final judgment. Each item carries an `evidence_id`, `source`, `source_type`, `as_of`, `freshness`, and the raw / normalized value needed to reconstruct the claim. Required evidence classes:

- **Observed data**: prices, volume, fundamentals, filings, news rows, Alpha Picks state, comments, option quotes / IV, macro events.
- **Deterministic metrics**: change %, volatility / IV rank, event-chain factors, anomaly flags, coverage counts, data-quality summaries.
- **Provider-native signals**: analyst consensus, provider sentiment / factor grades, SA curated state, provider tags. These must remain source-labeled and may not be represented as ArkScope-computed facts.
- **Coverage / missing-data facts**: which sources were queried, which were stale or unavailable, and whether the data is real-time, delayed, cached, or historical.

The LLM may quote, compare, prioritize, and reason over evidence. It may not silently alter evidence values, invent provider facts, or run a new scoring scale as part of card generation. Any re-score fallback must be explicit in the EvidencePacket (`source_type = "arkscope_fallback_score"` or equivalent), with method, model, prompt/version, and as-of metadata. Every material ResultCard claim must cite one or more `evidence_id`s; uncited judgment is not renderable as a product card.

---

## 3. Reasoning posture — what the agent is *for* (LOCK #3)

- **The LLM integrates and reasons; it does not re-compute or re-score everything itself.** Its value-add is synthesis into a defensible, cited conclusion (§2) — not bespoke re-scoring of raw inputs.
- **Prefer provider-native signals** (analyst consensus, sentiment, factor grades, event tags) as evidence inputs. Re-scoring is a fallback, not the default.
- The open multi-LLM scoring dataset is a **standalone published artifact**, not a runtime dependency. Future scoring need not preserve the old scale or pipeline; provider-native signals may matter more.
- **Explainability is a hard requirement** (this is not HFT): every conclusion must be reconstructable from cited evidence. An unexplainable signal is not shippable to a decision.

---

## 4. Agent capability boundaries (LOCK #4 — net-new core)

The Agent Layer (SPEC §1.2, layer 2: memory · tools · skills · scheduler · replay · compression · subagents · attachments · prompt-caching) is bounded by **user-controllable settings** exposed in the app. Two orthogonal control surfaces: **effort presets** (§4.1–4.2, "how hard it works") and the **permission model** (§4.3, "what it may do without asking"). Presets do not change permission defaults.

### 4.1 Effort presets (bundle the work-intensity knobs)

Three presets bundle the knobs below; **Balanced is the default.** Numbers are proposed v1 defaults (tunable).

| Knob | Conservative | **Balanced (default)** | Aggressive |
|------|-------------|------------------------|------------|
| Reasoning effort | low | medium | high / max |
| Max agent steps | 8 | 20 | 40 |
| Max tool calls / query | 20 | 60 | 120 |
| Context strategy | aggressive compaction | standard | deep (retain longer, compact late) |
| Memory strategy | read-only recall | recall + suggest-write | proactive recall + auto-write candidates |
| Subagents | off | on-demand | eager fan-out |

> **Caps, not targets.** These *bound* the agent; they are not quotas to fill. The agent must early-stop when the task is done — Balanced's 20 steps / 60 calls is a ceiling for a *full* research task, not an expectation that every query runs to the limit. **Subagent tool calls count toward the parent's total tool budget** (a subagent does NOT get a fresh allocation), and `subagent_mode` bounds fan-out width *and* nesting depth so eager mode cannot blow the budget.

### 4.2 Advanced override (per-knob)

A "Custom" preset exposes every knob individually; selecting a preset just sets these.

| Knob | Type | Range | Default | Meaning |
|------|------|-------|---------|---------|
| `reasoning_effort` | enum | low / medium / high / max (model-capped) | medium | maps to model effort + thinking budget |
| `max_steps` | int | 1–100 | 20 | max agent-loop iterations before a forced summary/stop |
| `max_tool_calls` | int | 1–300 | 60 | max tool invocations per user query |
| `context_strategy` | enum | off / standard / aggressive | standard | tool-result replacement + microcompact aggressiveness |
| `memory_strategy` | enum | off / read-only / recall+suggest / proactive | recall+suggest | recall + write behaviour |
| `subagent_mode` | enum | off / on-demand / eager | on-demand | `delegate_to_subagent` availability + fan-out depth |

> These are *library*-level controls, not a new runner: the compressor is a library, not a runner (`P1_4_SPEC.md`), and these knobs configure existing capability modules — they do not introduce a parallel agent loop.

### 4.3 Permission model (orthogonal to presets)

Six action classes are **gated**. The dividing line: **local/app-data reads and reads from already-enabled providers are NOT gated; metered spend, external web access, external browser automation, code execution, DB writes, and profile/universe-state writes ARE gated.** (Many paid/web calls are technically "reads" — gating is by *cost/side-effect*, not by read-vs-write.)

| Gated action class | Covers | Default | Settings "auto-approve" toggle | Grain when prompted |
|--------------------|--------|---------|-------------------------------|---------------------|
| `metered_spend` | billable operations **beyond normal session inference** — deep-research runs, bulk paid-provider endpoints, batch LLM scoring | **ASK** | OFF | once / this-session / always |
| `code_execution` | `execute_python_analysis` (agent-authored Python) | **ASK** | OFF | once / this-session / always |
| `db_write` | **additive** writes to the local workbench DB — save memory, save report, analysis records (incl. agent-memory auto-write — §4.4); reviewable / deletable. **Not** universe/profile changes (see `profile_state_write`) | **ASK** | OFF | once / this-session / always |
| `profile_state_write` | changes to the user's **research universe / profile state** — watchlist, ticker universe, provider/agent settings, auto-follow rules — **storage-independent** (config file *or* DB). Wider blast radius than one record: reshapes daily collection, the UI, and the agent's default attention scope | **ASK** | OFF | once / this-session / always |
| `external_web_access` | web **search / fetch** against external sites (e.g. Tavily) — network egress, not browser control | **ASK** | OFF | once / this-session / always |
| `external_browser_automation` | driving a real or embedded **browser** (agent-controlled navigation/clicks; the deferred CloakBrowser-class spike, §7) — kept separate so web-access never silently grants it | **ASK** | OFF | once / this-session / always |

Rules (LOCK):
- **Default for every gated action is ASK.** Each class has a Settings "auto-approve" toggle that **defaults OFF**.
- When prompted, the user may approve **once / for this session / always**. "Always" flips that class's Settings toggle.
- **`external_web_access` ≠ `external_browser_automation`.** Web search/fetch (Tavily) is network egress; browser automation is a heavier, separately-gated capability. Auto-approving one never auto-approves the other. The **user-driven** SA extension capture is NOT an agent action and is not gated here.
- **`db_write` ≠ `profile_state_write`.** `db_write` is additive, reviewable local records (memory / report / analysis). `profile_state_write` reshapes *what the workbench studies and how it behaves* — watchlist, ticker universe, provider/agent settings, auto-follow rules — and is gated independently of **where** that state lives (today `config/tickers_core.json`, later DB/profile). A user can auto-approve routine record-keeping while still confirming every change to their research universe. (Example: `refresh_sa_alpha_picks`'s implicit ticker sync — ToolCatalog §1.3/§1.4.)
- **Reads are not gated** — local/app-data reads and reads from already-enabled providers run freely. The gates cover *metered spend, external web access, browser automation, code execution, DB writes, and profile/universe-state writes*, not reading per se.
- **Normal LLM inference is NOT gated per-call.** The user's selected reasoning provider/model is covered by session settings; routine agent reasoning never prompts — otherwise the app is unusable. `metered_spend` catches only the *extra*-cost tail (deep research, large batches of paid endpoints, bulk scoring), not every token.
- Money is real BYOK spend, so `metered_spend` is load-bearing — but scoped to that extra-cost tail.
- (Pattern credited to the three-level approval model distilled from `AI_AGENT_ARCHITECTURE_PATTERNS.md`.)

### 4.4 Memory & context (capability stance)

- **Memory**: the agent reads/writes its accumulated substrate in the Profile layer (SPEC layer 4); the `memory_strategy` knob governs *recall proactiveness*. Existing memory + compression subsystems are reused — not reinvented. **Memory recall is a free read; memory *writes* go through the `db_write` gate (§4.3).** Even under a proactive `memory_strategy`, the agent produces an *auto-write candidate* that needs user confirmation unless DB-write auto-approve is ON — `memory_strategy` sets how eagerly candidates are *proposed*, not whether they bypass the write gate.
- **Context**: `context_strategy` governs compaction aggressiveness over the existing client-side compressor.

---

## 5. Data & real-time stance (LOCK #5; per-provider detail → ProviderCatalog)

- **Foundation tier (the 基本盤 — already in daily use)**: **IBKR** (everything obtainable, free + paid), **Seeking Alpha** (everything knowable via the capture pipeline), and **general web search** (Tavily — deliberately not finance-only: politics / international / geopolitics / war context that moves markets). These three are the load-bearing spine; every other provider is supporting/optional. The provider set is **extensible but incremental** — additions are a few well-known providers at a time, NOT another research-everything-first sweep. Detail + tiering in `ARKSCOPE_PROVIDER_CATALOG.md` §0.4.
- **Multi-provider via the DAL; BYOK.** Providers are enabled + keyed in Settings; the per-provider Settings fields are defined by `ARKSCOPE_PROVIDER_CATALOG.md`.
- **Real-time price/volume charting** — within the connected provider stack, **only IBKR IB Gateway** delivers real-time streaming (`reqMktData` = streaming market data; `reqRealTimeBars` = 5-second OHLC bars). It requires a user-account **market-data subscription** **and an in-app Settings connection test** before charting is enabled. No other connected provider streams real-time (Polygon = delayed; Finnhub real-time quote but shallow news history; Tiingo/Alpha Vantage = EOD/delayed). **All pricing, waiver conditions, exact latency figures, and `verified_at` live in `ARKSCOPE_PROVIDER_CATALOG.md`, not here** — prices change, and ProductSpec must not carry them.
- **Refresh cadence is a first-class setting, separate from real-time.** The cockpit must support user-configurable update frequencies per surface/provider capability (manual only, interval polling, scheduled background refresh, or true streaming when a provider supports it). Cached/polled data must display freshness/as-of metadata; real-time streaming remains opt-in and provider-gated (currently IBKR only). "Not real-time" does **not** mean static: the app still needs controlled auto-refresh for watchlists, news, signals, and provider health.
- **Retention/resolution is separate from display cadence.** ArkScope distinguishes: (1) **Display Stream / Live View** — high-frequency UI data that may stay only in memory/short-lived cache; (2) **Operational Cache / Short-retention Store** — dense intraday or polling data kept briefly for debugging, replay, and same-day analysis, then TTL'd or downsampled; (3) **Durable Research Store** — lower-resolution, provenance-rich records kept long-term for agent reference and reproducible analysis. A provider update can be shown live without storing every tick; a short window can be stored densely without keeping that density forever. Each provider/capability must eventually declare `display_frequency`, `capture_frequency`, `short_retention`, `downsample_to`, `durable_retention`, `is_agent_referenceable`, and freshness/as-of labels.
- **LLM (reasoning) providers are distinct from data providers**: dual-SDK (OpenAI + Anthropic) with a per-task switcher; v1 locked set per VISION = OpenAI / Anthropic / OpenAI-compatible / Ollama-local.

---

## 6. Product surface (summary; detail → SPEC §6 + VISION)

- Dark multi-panel cockpit; **list-first + right-side detail panel**; global Cmd/Ctrl-K command bar; AI embedded at three entry levels (global / per-row inline / multi-select bulk) — not a separate chat tab.
- **Unified research-object lifecycle** (`Inbox → Watching → Active Research → Owned → Archived → Deleted`, with per-type sub-states) + soft-delete/archive (VISION §4).
- **Watchlists are multi-list tabs backed by profile state, not one hard-coded YAML list.** The profile-state substrate must support multiple named lists/tabs (e.g. Holdings, Interested, Themes, Alpha Picks, custom lists, Archived), stable ordering, soft archive/restore, and many-to-many ticker membership. The default cockpit hides archived rows but provides an Archived management view for review/restore/future deletion. This is recorded here but implemented with the profile-state SQLite work, not bolted onto the current `user_profile.yaml` adapter.
- 8-page v1 read-only IA is **owned by SPEC §6.1** — this doc does not re-arbitrate it.

### Signals — opportunity / risk detection (ephemeral capability; not necessarily a v1 page)

Signals are ArkScope's **opportunity/risk detection** capability — the clean replacement for the retired `signal_tools` line (llm_sentiment / news_scores / RL-era coupled → legacy, do not reuse). Locks:

- **Independent of the §2 AI card.** Signals are NOT part of the AI-card v1 EvidencePacket (ToolCatalog rule 9 / §2.4). A card may *cite* a signal only once that signal is itself clean, source-labeled, and traceable — never a black-box composite passed off as objective fact.
- **Provider-coverage-dependent.** A signal's reach scales with *enabled* providers (ProviderCatalog): free sources → basic price / news / calendar / fundamentals signals; IBKR → realtime/near-realtime quote, IV, option-chain, position context; SA → Alpha Picks / article / comment / community; Polygon / Finnhub / Financial Datasets → historical news, analyst, earnings, segment revenue. **Every signal must show which sources support it** — not a single opaque score (same spirit as §2.3 per-claim traceability).
- **Ephemeral by default.** A `signal_event` is short-lived: `{ ticker, kind, severity, direction, as_of, expires_at, source_coverage, evidence_refs }`. Default short retention (≈1–7 days or until expiry). Only an explicit user action (pin / save / convert-to-alert / convert-to-card) promotes it to durable store. **Expired signals must not silently influence an AI card** unless explicitly tagged expired/historical.
- **Surfaceable across the app, not a dedicated page in v1.** A signal can appear as Home 今日機會/風險, a Watchlist-row badge, a ticker-detail Signals panel, an Alert (when converted), or an AI-Research "scan this watchlist / ticker" action. A dedicated Signals triage page is a *later* step, justified only when volume warrants it.

### Holdings — IBKR-first (LOCK)

Holdings is **not** a generic/manual portfolio mock. It is the surface for IBKR users to sync positions, cost basis, trades, cash, and option exposure from IB Gateway. Without an IBKR connection it is a **disabled/empty state** ("連接 IB Gateway 後啟用持倉同步"), not a hand-entered portfolio. Built after an IBKR account/position endpoint is confirmed.

### AI Chat — one research-thread pool with scoped entrypoints (not per-ticker rooms)

AI conversation is a **single research-thread pool**, surfaced through scoped entrypoints — it must *look* like "every ticker has AI chat" without fragmenting into per-ticker islands. Each thread carries `{ scope: ticker|watchlist|portfolio|news|signal, ticker?, linked_card_id?, linked_note_id?, evidence_snapshot_id?, created_from }`, and should bind the `evidence_snapshot_id` of the card/packet it follows up on so "what was this said against" stays traceable (consistent with §2.3). v1: a ticker's AI summary card offers **"Follow-up in AI Research"** → creates/continues a scoped thread; the AI-Research nav later becomes the global thread/history manager (filter by ticker / watchlist / date / saved-archived). **No permanent per-stock chat rooms in v1.**

### Surface-object separation: signal · card · chat (principle)

Three distinct research objects, deliberately not merged:
- **Signal** — *detects* "possibly worth a look" (opportunity/risk). Short-lived, expirable, provider-coverage-bounded.
- **AI Card** — *structures* a question into a traceable, cited judgment (§2). Formal, validated, savable; promotable to a report.
- **AI Chat** — *explores / follows up* interactively. Not every line is worth keeping; manually upgradable into a note / card / report.

---

## 7. Posture, boundaries & deferred spikes

- **Local-first, BYOK, no-sign-in, telemetry off by default** (VISION Tier A). Single-user, single-writer, one profile dir (SPEC §3, §5).
- **Current SA ingestion stays**: Chrome/Firefox extension → Native Messaging host → DB is a **protected runtime surface** — do not break it.
- **RL** = retired/offline under `training/`; the Algo nav entry (if present) stays empty in v1.
- **Deferred spikes (not v1, not drop-in replacements):**
  - *Embedded/stealth browser* (e.g. CloakBrowser) as an alternative SA-ingestion backend — evaluate bundle size, ToS/compliance, login-profile, platform-publish cost before adopting. Not a v1 extension replacement. Before this can replace the external extension path, complete `SA_EXTENSION_ROADMAP.md` P0: runtime diagnostics, lifecycle cleanup, capture-core extraction, and soak testing.
  - *Code/doc knowledge-graph tooling* (e.g. Understand-Anything) for repo/doc navigation — a dev-tooling spike, **not** a replacement for the agent's research memory.

---

## 8. Companion docs & sequence

| Concern | Authority |
|---------|-----------|
| Architecture / storage / sync / migration / page-IA | `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md` |
| Per-provider data facts + Settings fields | `ARKSCOPE_PROVIDER_CATALOG.md` (write next) |
| Per-tool keep/adapt/drop + tool-design rules | `ARKSCOPE_TOOL_CATALOG.md` (after provider) |
| UI/UX product intent detail | `DESKTOP_APP_VISION_DRAFT.md` |
| Backlog ordering + decision log | `PROJECT_PRIORITY_MAP.md` |

**Sequence**: ProductSpec (this) → ProviderCatalog → ToolCatalog → **then** build the desktop-app shell (stack chosen at that kickoff). Old docs are retired *by reference* only after this doc is adopted — no archive/delete before then.
