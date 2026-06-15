# Layer C-2 — AI 研究 / AI Research (Chat surface)

> **Status:** SHIPPED through C-2b (2026-06-15): C-2a streaming surface + C-2b persisted threads/messages are implemented. This document remains the contract reference for the SSE/event reducer/UI shape. **C-2c multi-turn context and memory policy is not solved here**; see `AI_RESEARCH_CONTEXT_MEMORY_PLAN.md`.
> **Original scope:** enable the existing **AI 研究** nav surface and reuse `POST /query/stream`. C-2a added a 3-pane evidence-first chat (thread-list / conversation / evidence-trace). C-2b added local thread persistence. The next work is history/context injection, not another UI shell.
> **Predecessors:** C-1 `get_sa_feed` + `get_sa_comment_focus` + News surface — done. `POST /query/stream`, `EventType`/`AgentEvent.to_sse()`, `GET /query/providers`, `GET /config/runtime` — all exist.

## 1. Why

C-1 made SA evidence agent-queryable; C-2 gives the agent a front-door for open-ended questions. C-2 is the L1 AI entry (vision §5 Tier A): the one place to ask freeform questions and **see the agent's tool/evidence trace** — so the output is structured/traceable/cited, not free 買/賣/觀望 chat (vision §1/§3). Trace **liveness is provider-dependent** (Anthropic live; OpenAI shown on completion), so surface copy stays neutral — 「工具追蹤與證據整理，支援即時或完成後顯示，依 provider 而定」 — NOT a universal「即時 watch the agent investigate」claim. It reuses the streaming contract and the C-1 SA primitives verbatim so it "isn't just a chat box". Per audit §4.1 this surface "needs new read route over chat_history + replay traces" — additive, not blocking — and that persistence landed in **C-2b**.

**User shape locked (6 points):** ① enable the AI 研究 nav surface · ② reuse `POST /query/stream` · ③ 3-pane layout thread-list / conversation / evidence-trace · ④ inputs = freeform question + optional ticker/context + provider/model **route display** · ⑤ suggested SA/news prompt chips · ⑥ persistence-if-small-else-ephemeral → **C-2a shipped the in-memory surface, C-2b persisted it in `profile_state.db`**, sliced so persistence was a pure write-through with NO UI-state reshape.

## 2. Backend — REUSE `POST /query/stream` (no new backend in C-2a)

C-2a adds **zero** backend. It consumes the existing contract verbatim.

- **`POST /query/stream`** → `text/event-stream` (headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`). Request body `QueryRequest` = `{question: str (required), provider: "openai"|"anthropic" = "openai", model?: str|null}`. POST-only → **EventSource API is unusable**; client must `fetch()` + read `response.body` as a `ReadableStream`. (`src/api/routes/query.py:22-26,105-160`)
- **No ticker/context field, no thread_id, no effort/thinking over HTTP.** C-2a folds the optional ticker/context into the `question` string client-side (e.g. prefix `針對 {TICKER}：`). (`QueryRequest`, `src/api/routes/query.py:22-26`)
- **`GET /query/providers`** → `{providers:{openai:{available,sdk_version?|install?}, anthropic:{...}}}` — gate which provider buttons are enabled (SDK presence only, NOT key presence). (`src/api/routes/query.py:163-199`)
- **`GET /config/runtime`** → route-display source: `{anthropic:{model,model_advanced,effort,thinking,key_set}, openai:{model,model_advanced,reasoning_effort,key_set}, …}` (both entries also carry a `credentials` array; response also has top-level `card_synthesis`/`card_translation`/`data_keys` — the route chip reads only `model`/`effort`). (`src/api/routes/config_routes.py:112-159`; frontend `getRuntimeConfig()` `api.ts:454`)
- **Auth:** when sidecar sets `ARKSCOPE_API_TOKEN`, every call needs header `x-arkscope-token`; the stream `fetch()` MUST attach `authHeaders()` or 401. (`src/api/app.py:132-141`; `api.ts:384-394`)

### SSE event contract the UI consumes (EXACT)

Wire format per frame: `data: {"type":<EventType>,"data":{...}}\n\n` — no `event:`/`id:`/timestamp on the wire; `ensure_ascii=False` (中文 literal). `EventType` has exactly **7** values. (`src/agents/shared/events.py:19-47`)

| EventType | Anthropic payload | OpenAI payload | UI use |
|---|---|---|---|
| `thinking` | `{turn:int, model:str}` (every turn) | `{turn:1, model:str}` (once) | "思考中…" state; model badge |
| `thinking_content` | `{thinking:str}` (per block) | **never emitted** | inline thinking lines in trace (Anthropic only) |
| `text` | `{content:str}` (interim, pre-tool) | **never emitted** | interim conversation text |
| `tool_start` | `{tool:str, input:object}` | **never emitted** | evidence-trace row (begin) |
| `tool_end` | `{tool:str, summary:str(≤200), chars:int}` | `{tool:str}` (name ONLY) | evidence-trace row (result) |
| `done` | `{answer:str, tools_used:str[], provider:"anthropic", model:str, token_usage:obj}` | same, `provider:"openai"` | final bubble + footer; **sole completion signal** |
| `error` | `{error:str, turn:int, tools_used:str[], scratchpad:str|null}` | `{error:str, scratchpad:str|null}` | error bubble |

- `token_usage` (in `done`) = `{total_input_tokens, total_output_tokens, total_tokens, turn_count, last_input_tokens}` **+ optional** `cache_creation_tokens`, `cache_read_tokens`, `web_search_requests` (present only when nonzero — treat as optional). (`src/agents/shared/token_tracker.py:167-186`)
- **Max-turns** arrives as a normal `done` (NOT `error`) whose `answer == "Maximum tool calls reached. Please try a simpler query."` — **Anthropic-only**, `provider:"anthropic"`. (`anthropic agent.py:515-521`) See §4 for the (best-effort, fragile) detection.

### Provider asymmetry the UI MUST tolerate (load-bearing)

- **Anthropic = rich + live:** per-turn `thinking`, `thinking_content`, interim `text`, `tool_start{input}` THEN `tool_end{summary,chars}`, streamed as the agent works. (`anthropic agent.py:329,372-374,434,446-449,477-481`)
- **OpenAI = one ping, then silent, then a batch at the end:** it emits ONE `thinking` at t0 (`openai agent.py:741`), then `Runner.run()` runs to completion with **no events at all** for the entire 1–4 min turn (`openai agent.py:780`), then emits **all** `tool_end{tool}` rows in a loop AND `done` together at the end (`openai agent.py:808-810,827-833`). There is effectively **NO live trace** and **NO interim text** for OpenAI. Mark `input`/`summary`/`chars` **optional** and do NOT assume `tool_start` precedes `tool_end`.
- **Provider selection = user-chosen; NO global default** (decision 2026-06-14, refined). We do NOT declare OpenAI *or* Anthropic the product default — that is a provider-strategy choice that belongs to the user, not us. Resolution: ① if Settings `research_provider` is set → use it (**NEW — backlog**, absent in C-2a); ② else gate on availability (SDK via `GET /query/providers` + key via `GET /config/runtime` `key_set`) and — **one** provider available → auto-select it · **multiple** available → **do NOT pre-select**; render a provider chooser and let the user pick · **none** available → **disable input** + prompt to set a credential in Settings. C-2a remembers the picked provider for the **session** (in-memory); durable `research_provider` routing is C-2b/Settings. Each thread snapshots the provider/model it actually used (§6a).
- **OpenAI affordance = "silent until completion", not "trace limited":** because the UI sits on the thinking indicator for minutes with zero events, a static "追蹤受限" note reads like a stalled/frozen app. The OpenAI path MUST instead hold an explicit expectation-setting state during the silent gap, e.g. `OpenAI 執行中，完成後一次顯示追蹤` on the thinking indicator, then render the batched trace + answer when `done` arrives.
- **Two error shapes:** route-layer errors use `{message:str}` (unknown provider, top-level exception, key is `"message"`); agent errors use `{error:str,…}`. UI reads `data.error ?? data.message`. (`src/api/routes/query.py:144-154`)
- **`done.tools_used` is `list(set(...))`** — unordered, no repeats. Build the chronological trace from `tool_start`/`tool_end` events (Anthropic) or the ordered `tool_end` batch (OpenAI), NOT from `done.tools_used`.

## 3. Agent tool

**No new tool. No count-assert bump.** C-2 CONSUMES the **existing** agent tool surface — the C-1 SA primitives (`get_sa_feed`, `get_sa_comment_focus`, and the SA article/comment/market-news tools the agent already has) plus fundamentals — through the existing stream. The agent decides which tools to call; the surface only renders the resulting trace. (Mirrors C-1 §3 discipline.) The suggested prompts in §4 are deliberately scoped to the two named C-1 primitives.

## 4. Frontend — `Research.tsx` (NEW; 3-pane; needs visual verification via run/verify)

**Mount (3 edits to `App.tsx` — verify offsets against the live file at execution time; NAV also contains Holdings/Alerts/Notes so the reliable anchor is "next to the News branch", not a fixed line):**
① add `'Research'` to `ENABLED` (`App.tsx:29`) — this alone enables the nav button (the disabled-state title `${LABELS[key]} — 規劃中` is generated at `App.tsx:136`; `LABELS.Research = "AI 研究"` already exists at `App.tsx:35`).
② `import { ResearchView } from './Research';` — **`Research.tsx` / `ResearchView` are NEW**, created in execution step 3 (does not exist yet).
③ add a ternary branch `: view === 'Research' ? (<ResearchView onOpenTicker={openTicker} />)` next to the existing News branch (~`App.tsx:156-157`); this also removes the `規劃中` fall-through stub (`{LABELS[view]} — 規劃中。` at ~`App.tsx:162-165`) for this view. Component signature mirrors `NewsView`: `export function ResearchView({ onOpenTicker }: { onOpenTicker: (ticker: string) => void })`.

**SSE client (NEW — `api.ts` has no `/query` client):** add ONE async-generator `streamQuery(body, signal)` — do NOT route through `getJSON/sendJSON`/`fetchWithTimeout` (its 15s `AbortController` would kill the stream; a turn runs 1–4 min, cf. `CARD_GEN_TIMEOUT_MS=240_000`).
```ts
async function* streamQuery(
  body: {question: string; provider: string; model?: string},
  signal?: AbortSignal
): AsyncGenerator<{type: string; data: any}>
// POST `${apiBase}/query/stream`, headers {...authHeaders(), 'content-type':'application/json'},
// body JSON; res.body.getReader() + TextDecoder; buffer, split on '\n\n' (frames may span chunks
// — only parse complete frames), strip leading 'data: ', JSON.parse, yield. Own AbortController,
// aborted on thread-switch / unmount / Stop button.
```
Type frames as a discriminated union over `EventType` with `input`/`summary`/`chars` optional. `apiBase = window.arkscope?.apiBase ?? import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8420'`.

**3-pane layout** (new grid inside `.main`, reuse the dark-theme atoms — no theme work): `.research-grid { display:grid; grid-template-columns:220px 1fr 320px; height:100% }` using `var(--panel)/--border/--accent)`. Reuse `.surface-head/.surface-title`, `.btn-ghost` (+`.small/.tiny/.danger`), `.list-chip`, `.news-ticker-chip`, `.muted/.tiny/.mono`, `.errorbox`. Right pane collapsible following the `.rightrail`/`.rail-tab` precedent, scoped to the surface.

| Pane | Content | Source |
|---|---|---|
| **Left — thread list** | thread rows (`.list-chip`), "+ 新對話"; title auto-derived from first user message (client truncates to ~60 chars). Empty state when no threads. | C-2a in-memory state |
| **Center — conversation** | bubbles + timestamps + **per-message model badge** (optimistic from `thinking.model` during the stream, finalized from `done.model`; the two are the SAME `model_name` for a turn so there is no mid-stream reconciliation — NOT the stale S7 "Claude 3.5 Sonnet"); interim from `text`/`thinking_content` (Anthropic only); finalize on `done.answer`; max-turns surfaced distinctly (Anthropic only, see below). Bottom input toolbar (§ below). Empty-conversation + terminal states per "states" subsection. | SSE stream |
| **Right — evidence / tool trace** | chronological rows from `tool_start`→`tool_end` (name · `input` · `summary`≤200 · `chars`); Anthropic `thinking_content` rendered inline in the trace stream (no dedicated sub-panel in C-2a); footer shows `total_tokens` + `turn_count` only. OpenAI → "OpenAI 執行中，完成後一次顯示追蹤" during the silent gap, batched rows on `done`. Empty state before any tool runs. | SSE stream |

**Inputs (user item ④):** freeform question textarea + optional **ticker/context** field (uppercased, folded into `question` client-side) + a **route-display chip** showing active provider/model — pre-run from `GET /config/runtime`, then finalized post-turn from `done.provider`/`done.model`. Provider control gated by `GET /query/providers` (SDK) + `GET /config/runtime` `key_set` (key). **No pre-selected default** — when no Settings `research_provider` and >1 provider is available, render a chooser (no auto-pick); 1 available → auto-select; 0 → disable input (§2). Per-provider presentation comes from a client-side descriptor map (NOT hardcoded `if anthropic` branches), so OpenAI-compatible providers slot in later without render changes:
```ts
const PROVIDER_PRESENTATION: Record<string, {trace_mode: 'live' | 'post_run'; auth_mode_label: string}> = {
  anthropic: { trace_mode: 'live',     auth_mode_label: 'API key / setup-token' },
  openai:    { trace_mode: 'post_run', auth_mode_label: 'OAuth / API key' },
};
```
`trace_mode` drives the live-trace vs silent-until-done affordance; copy stays neutral. (Setting effort/thinking per-request is deferred.)

**Ticker chips:** the typed **ticker/context field is the single source** for ticker chips (uppercased). Clickable `.news-ticker-chip` → `onOpenTicker(t)` opens the full-page `TickerDetailView` overlay exactly as News does (`openTicker` at `App.tsx:54-56`). Do NOT parse the agent's `answer` for tickers — the `done` payload has no tickers field (that is a CLI-only `ChatHistory` concept). If no ticker is typed, no chips render.

**Suggested prompts (item ⑤)** — 4 chips that prefill the input, scoped to the two named C-1 primitives (default ticker SMCI/CLS/NVDA; MXL = user's seed). Each tagged with the tool(s) it exercises:

1. 最近 SA 對 SMCI 有什麼新文章和評論焦點？ — `get_sa_feed` + `get_sa_comment_focus`
2. CLS 過去 14 天的 SA 評論焦點與情緒變化？ — `get_sa_comment_focus`
3. MXL 的高價值留言在吵什麼？焦點是什麼？ — `get_sa_comment_focus`
4. NVDA 最新 SA 動態與評論焦點重點整理。 — `get_sa_feed` + `get_sa_comment_focus`

### Thread lifecycle & states (C-2a, ephemeral)

- **Boot:** app starts with an **empty thread list** (no blank placeholder thread). The first user submit creates a thread; its title is the truncated first user message.
- **"+ 新對話" / thread-switch with a stream in flight:** abort the in-flight stream via its `AbortController`, **keep the committed user message**, **drop the partial assistant turn** (no partial bubble persists). Then create/switch.
- **Unmount / nav-away mid-stream:** abort; the partial assistant turn is dropped (ephemeral).
- **Rename / delete threads:** NOT in C-2a (titles are auto-derived only). Manual rename/delete → deferred (§7).
- **Terminal states the reducer drives (define in code, not only in tests):**
  1. `done` → finalize the assistant bubble + footer (max-turns variant flagged, Anthropic only).
  2. `error` (`data.error ?? data.message`) → error bubble.
  3. abort (Stop / switch / unmount) → drop partial assistant turn, keep user message, clear thinking indicator.
  4. **stream ends with NO `done` and NO `error`** (reader throws / connection drop) → synthesize a client-side error bubble (`連線中斷`) so the bubble never hangs (`done` is the sole completion signal, so the absence path MUST be handled explicitly).
- **Thinking-indicator clear timing:** clear on the FIRST of `text` | `tool_start` | `done` (whichever arrives first). For OpenAI (no `text`/`tool_start`) it holds until the batched `done`, which is exactly why the OpenAI "silent until completion" affordance is required.
- **Max-turns detection is Anthropic-only best-effort:** matched by exact-string equality on `done.answer == "Maximum tool calls reached. Please try a simpler query."` (`anthropic agent.py:516`). This is English-only and will silently stop being detected if the message is reworded/translated; OpenAI has **no** max-turns sentinel (it returns whatever `final_output` exists). Treat as a soft heuristic, NOT a cross-provider contract.

## 5. Tests (frontend — app-free where possible)

- **`streamQuery` parser unit:** feed a synthetic byte stream — frames split mid-`\n\n` across chunks (must buffer, not parse partial); `data: ` prefix stripping; both error shapes (`data.error` and `data.message`); Anthropic full sequence (`thinking`→`thinking_content`→`text`→`tool_start`→`tool_end`→`done`) AND OpenAI sparse sequence (`thinking`→[silence]→batched `tool_end`→`done`); `done` as terminal; **stream ends with no `done`/`error` → synthesize error**; abort mid-stream.
- **Event→state reducer unit:** chronological trace built from `tool_start/tool_end` (not `done.tools_used`); optional `input/summary/chars` tolerated; max-turns `done.answer` flagged (Anthropic only); model badge from `thinking.model` then `done.model`; abort drops partial assistant turn but keeps user message.
- **Provider-gating:** `GET /query/providers` `available:false` disables that provider button.

## 6. Execution order (one clean round)

1. `streamQuery` async-generator in `api.ts` (+ parser tests).
2. Event→state reducer + in-memory `Thread`/`Message` DTO (§6a; field names == future DB columns).
3. `Research.tsx` (NEW) 3-pane shell + bubbles + evidence-trace + **provider chooser/selection (§2 — no pre-pick when >1 available)** + route-display chip + suggested-prompt chips + lifecycle/terminal states.
4. Mount: `ENABLED` += `Research`, import, ternary branch (3 edits to `App.tsx`).
5. GUI visual check (run the app); confirm Anthropic live trace + OpenAI silent-until-completion affordance.

## 6a. Thread/message data model (C-2a in-memory == C-2b columns)

C-2a holds threads in React state; **field names MUST equal the proposed `profile_state.db` columns** so C-2b is a pure write-through with NO UI-state reshape. (Structured agent fields stored as TEXT `*_json` per codebase convention; timestamps TEXT UTC ISO-seconds; IDs `INTEGER PK AUTOINCREMENT`; FK `ON DELETE CASCADE` — these idioms mirror the shipped `CardRunStore` (`src/card_runs.py`) and `watchlist_memberships` (`src/profile_state.py:47`).)

```sql
-- C-2b (NEW — to build): a SEPARATE store class (e.g. ResearchThreadStore) over data/profile_state.db,
-- modelled on the shipped CardRunStore (src/card_runs.py:79) — its own _write_lock / _connect / module _now;
-- do NOT bloat ProfileStateStore. Same local DB, NOT remote PG (card_runs.py:13).
CREATE TABLE IF NOT EXISTS research_threads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,            -- client truncates first user message (~60 chars)
  ticker TEXT,                    -- the typed ticker/context field (item ④), uppercased
  provider TEXT, model TEXT,      -- route snapshot at creation (item ④ display)
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived_at TEXT  -- archived_at unused in C-2a
);
CREATE INDEX IF NOT EXISTS idx_threads_updated ON research_threads(updated_at DESC);

CREATE TABLE IF NOT EXISTS research_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  thread_id INTEGER NOT NULL REFERENCES research_threads(id) ON DELETE CASCADE,
  role TEXT NOT NULL,             -- 'user' | 'assistant'
  content TEXT NOT NULL DEFAULT '',  -- user question OR done.answer
  provider TEXT, model TEXT,      -- from done.provider/done.model
  tools_used_json TEXT,           -- json.dumps(done.tools_used)
  tool_calls_json TEXT,           -- [{name, input, result_preview}] assembled from tool_start/tool_end (== ChatHistory.tool_calls_detail)
  token_usage_json TEXT,          -- json.dumps(done.token_usage)
  tickers_json TEXT,              -- json.dumps([typed ticker field]) or null when none typed; NOT parsed from answer
  elapsed_seconds REAL,           -- client wall-clock: start on POST, stop on done
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON research_messages(thread_id, id);
```

**Populating source for every column (so C-2a fills exactly what C-2b will, preserving pure write-through):**
- `title` — client truncates the first user message (~60 chars).
- `ticker` (thread) / `tickers_json` (message) — from the **typed ticker/context field** (uppercased); `tickers_json` is null when no field is typed. NOT derived from parsing `answer`.
- `provider`/`model` — `done.provider`/`done.model` (thread snapshot taken at first turn).
- `tools_used_json`/`token_usage_json` — `done.tools_used` / `done.token_usage`.
- `tool_calls_json` — accumulated across `tool_start`/`tool_end` during the stream, committed once on `done`.
- `elapsed_seconds` — client measures wall-clock around `streamQuery` (start on POST, stop on `done`); there is no stream/`done` field for it.
- timestamps — client ISO-seconds UTC.

An assistant `messages` row maps **1:1** onto the SSE `done` payload + the client-assembled tool trace (the same information `ChatHistory.append` already records in CLI JSONL).

**C-2a ↔ C-2b boundary:** C-2a leaves `QueryRequest` and the SSE wire shape UNCHANGED and persists nothing (multi-turn continuity, if any, = client-side history folded into `question`). C-2b is **additive**: add optional `{thread_id?, ticker?}` to `QueryRequest`; `/query/stream` calls `store.append_message(role='user',…)` before streaming and `store.append_message(role='assistant',…)` on `done` (best-effort, never fails the stream — same try/except posture as the CLI helper `_log_agent_query`, used here as an analogy, not a route call); add a `get_thread_store` dependency factory + `list_threads`/`list_messages` GET routes — mirroring the shipped `get_card_store` factory (`src/api/dependencies.py:50`) + `analysis_cards.py` route module. **No SSE event-shape change.** Keep threads LOCAL-only (never remote PG); do NOT create a second history store parallel to `data/chat_history/*.jsonl`.

## 7. Out of scope (C-2a) / deferred (C-2b+)

- **Persistence** (`research_threads`/`research_messages` tables + store methods + `{thread_id, ticker}` on `QueryRequest` + `list_threads`/`list_messages` routes) → **C-2b (NEW — to build)**. Designed above; not built in C-2a.
- **Manual thread rename / delete / archive** (the `archived_at` column + UI) → deferred; C-2a auto-derives titles only.
- **Dedicated thinking sub-panel + extended token footer** (`cache_read_tokens`/`web_search_requests`/`cache_creation_tokens` display) → deferred; C-2a renders `thinking_content` inline in the trace and shows only `total_tokens`+`turn_count`.
- **Structured AI output card** (vision §3.1/§3.2 typed schema: 結論/反方理由/觸發·失效條件/可信度, decision-questions, thesis versioning) → stubbed-but-designed, deferred; C-2a renders Markdown `answer`.
- **Right-pane rich Evidence & Data sub-cards** (price / financials / analyst-consensus / target-price, vision §5.1) → deferred; C-2a right pane = tool-trace (names + inputs + truncated summaries), NOT a clickable evidence list (the stream has no structured-evidence event).
- **Write-side toolbar actions** (Build watchlist execution, persisted Add-to-note, Export Markdown, "已存入本地 vault") → deferred; C-2a may show Copy only.
- **Per-request effort/thinking** controls over HTTP (route drops them today; needs a `QueryRequest` + `run_query_stream` thread-through) → deferred; C-2a route display is read-only.
- **Settings *research-provider* routing** — durable `research_provider` the selection rule reads first → **NEW — backlog**; until it ships, C-2a uses the user-chosen-per-session rule (§2) with **NO global default**. Never bury provider choice in a hardcoded default.
- **OpenAI live-trace parity** — give OpenAI `trace_mode:'live'` by making its bridge emit `tool_start`/`tool_end` live (if the Agents SDK exposes incremental run events), closing its silent gap → **tech-debt follow-up**. This (not a default change) is the real long-term fix for the provider UX gap.
- **Additional / OpenAI-compatible providers** (e.g. Grok — same call style as OpenAI, but we use each vendor's own SDK so it is not free to add) → OUT of C-2a scope; the descriptor model (`trace_mode`/`auth_mode_label`, §4) is designed so a new provider is a data row, not a UI rewrite.
- **Larger / fundamentals-spanning suggested prompts** (beyond the 4 SA-primitive chips) → deferred; the agent can still be asked freeform.
- ticker-detail SA sections → **C-3**.

> **Authority:** `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md` wins on any conflict. The AI Research page name (AI Research / Deep Research / Research Workbench) and the product brand remain OPEN — use the descriptive `AI 研究 / Research` nav label; do NOT freeze a name. Phase C unification is paused → build on the EXISTING dual-SDK stream, not a unified runner. Terminology: conversations = **threads** (do NOT translate to 池, reserved for filtered subsets).

## 8. Decisions (RESOLVED 2026-06-14)

1. **Persistence → C-2a ephemeral first; C-2b deferred.** The load-bearing risk in C-2 is the streaming/reducer/UX, NOT persistence: (a) `fetch`+`ReadableStream` SSE parsing across chunk boundaries / abort / error / no-`done`; (b) a reducer handling BOTH the Anthropic live-trace and OpenAI sparse-trace event shapes; (c) keeping the tool-investigation readable (not another chat box); (d) the OpenAI silent gap not reading as a frozen app; (e) the 3-pane spatial layout, tested live. Persistence is small but adds a separate change surface (store/schema/routes/`QueryRequest` extension/stream-end write/reload hydration) that would muddy the first review (UI bug = stream/reducer or persistence lifecycle?). So C-2a ships ephemeral; **C-2b follows once ask/trace/abort/error are stable.** DTO field names already == C-2b columns (§6a), so C-2b is a pure write-through.
2. **Provider selection → user-chosen; NO global default** (refined 2026-06-14). We don't declare OpenAI *or* Anthropic the product default — provider strategy is the user's call, not a technical preference we bake in. Rule (§2): Settings `research_provider` if set → else availability-gated [1 available = auto-select · multiple = chooser, **no pre-pick** · none = disable input]. C-2a remembers the session pick; durable routing = C-2b/Settings. Presentation is descriptor-driven (`trace_mode: 'live'|'post_run'`, `auth_mode_label`), NOT a hardcoded OpenAI/Anthropic binary, so OpenAI-compatible providers can slot in later (Grok et al. out of C-2a scope). OpenAI = post_run trace (OAuth/API key); Anthropic = live trace (API key / setup-token-derived). Long-term: OpenAI live-trace parity (§7), not a default.
3. **Ticker delivery → fold into `question` client-side (C-2a).** Follows decision 1: zero backend in C-2a; the typed ticker/context field is the single source for chips + `tickers_json`. The explicit `QueryRequest.ticker` field is deferred to C-2b (where `{thread_id, ticker}` are added together).
