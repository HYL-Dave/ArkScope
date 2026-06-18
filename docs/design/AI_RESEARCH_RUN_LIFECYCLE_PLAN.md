# AI Research Run Lifecycle Plan

> **Status:** ACTIVE PLAN (2026-06-18). This is the follow-up plan after
> C-2a/C-2b/C-2c shipped the AI Research surface, local thread persistence, and
> per-thread history injection. It records the next architecture change needed
> for background-safe research runs, per-run model selection, and independent
> thread execution. It is a planning document; no production code is implied by
> this file alone.

## 1. Why This Exists

The current AI Research surface is useful, but its live execution lifecycle is
still owned by the React page:

- `ResearchView` owns one `AbortController`.
- The reducer has one global `pending` turn, not a per-thread/per-run pending
  state.
- Navigating away from AI Research unmounts the component and aborts the stream.
- Switching threads during a live turn has to be blocked to avoid corrupting the
  single pending state.
- The input-area "switch" is a provider/research-route switch, not a complete
  model selector.

That means the current safety patch prevents accidental interruption, but it
does not support the desired product behavior: multiple independent research
threads can run, the user can inspect another thread or Settings while work
continues, and each run records exactly which provider/model/effort/auth path it
used.

The correct direction is to move from **page-owned streaming** to
**server-owned research runs**.

## 2. Related Authority

- `AI_RESEARCH_SURFACE_C2_SPEC.md` — shipped surface, SSE event vocabulary,
  trace rendering, thread/message DTO shape.
- `AI_RESEARCH_CONTEXT_MEMORY_PLAN.md` — per-thread memory principles,
  no silent truncation, future compaction.
- `CONFIG_AUTHORITY_PLAN.md` — Settings/DB authority and file/env fallback rules.
- `CREDENTIAL_MANAGEMENT_PLAN.md` — credential active-row workflow, Slice 6
  api-key wire-in, Slice 7 Claude subscription driver.
- `LLM_AUTH_DRIVER_PLAN.md` — provider/auth-mode driver abstraction and
  Claude/OpenAI OAuth boundaries.
- `ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md` §6 — one research-thread pool with scoped
  entrypoints, not permanent per-ticker chat rooms.

On conflict, the canon hierarchy in `docs/design/README.md` still applies.

## 3. Decisions

### 3.1 Settings route is the default; AI Research can override per run

Settings -> Models -> AI Research should define the default route. The AI
Research page should also expose a full per-run selector:

- provider;
- model;
- effort/reasoning setting where applicable;
- eventually auth/credential route if multiple credentials are relevant.

The default selector value is the Settings route. Changing the selector in AI
Research affects the next submitted run only, unless the user explicitly saves
it as the default in Settings. A run stores the resolved provider/model/effort
with the user message/assistant result so later review is traceable.

The page should not force users to choose "OpenAI vs Anthropic" first. The
selector should list actual model routes, grouped by provider, for example:

- `OpenAI / gpt-5.4-mini / low`;
- `OpenAI / gpt-5.5`;
- `Anthropic / claude-sonnet-4-6`;
- `Anthropic / claude-opus-4-8`.

### 3.2 Thread memory is independent; global memory is a separate layer

Current C-2c behavior is correct as a baseline: prior context is fetched by
`thread_id`, and each thread's transcript is independent. The run lifecycle work
must preserve that invariant.

Global memory, user strategy memory, and reusable skills are future product
layers. They may be available as explicit memory/tool inputs later, but they
must not silently merge separate thread histories.

### 3.3 A research run must outlive the page

Submitting a question should create a durable local run record. The sidecar
owns execution after creation. Closing the page, switching threads, opening
Settings, or reloading the app must not cancel a run.

Cancellation should be explicit:

- user clicks Stop/Cancel on that run;
- app shuts down;
- a future policy cancels old queued work with visible status.

### 3.4 Live trace is attach/replay, not direct ownership

The browser should attach to a run's event stream. If it detaches and later
reattaches, it should replay stored events from a sequence number, then tail new
events. The event vocabulary can remain the existing `AgentEvent` / C-2 SSE
shape.

OpenAI can still have post-run trace semantics. Anthropic can still stream live.
The lifecycle architecture should not require both providers to have identical
event cadence.

### 3.5 Multiple conversations should be possible, with explicit concurrency limits

The target product behavior is that different threads can run independently.
However, implementation must respect provider/auth constraints:

- OpenAI Slice 6 currently uses the Agents SDK global client in at least one
  path. That is not a safe final basis for concurrent runs using different
  credentials.
- Until per-run client isolation is proven, OpenAI concurrent runs may need to
  be serialized or restricted.
- Anthropic API-key runs are less exposed to the OpenAI global-client issue, but
  the future Claude setup-token driver is a different runtime and needs its own
  lifecycle handling.

The plan should not claim "parallel everything" until the auth/client isolation
work has verified it.

## 4. Proposed Data Model

Keep the existing `research_threads` and `research_messages` tables as the
transcript store. Add run-level tables in the same local `profile_state.db`
family:

```sql
CREATE TABLE IF NOT EXISTS research_runs (
  id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL REFERENCES research_threads(id) ON DELETE CASCADE,
  status TEXT NOT NULL,             -- queued | running | succeeded | failed | cancelled
  question TEXT NOT NULL,
  ticker TEXT,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  effort TEXT,
  auth_mode TEXT,
  credential_id TEXT,
  started_at TEXT,
  completed_at TEXT,
  error TEXT,
  token_usage_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_research_runs_thread ON research_runs(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_runs_status ON research_runs(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS research_run_events (
  run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  type TEXT NOT NULL,
  data_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, seq)
);
```

Notes:

- `research_messages` remains the final transcript authority.
- `research_run_events` is the attach/replay trace log. It can later be TTL'd or
  compacted if needed, but v1 should keep enough to reattach during and after a
  run.
- The user turn should be persisted when the run is created.
- The assistant turn should be persisted on terminal success/error.
- If a run fails, the error assistant message should be persisted, matching the
  C-2b hardening rule against dangling user turns.

## 5. Proposed API

Keep `/query/stream` as a legacy/direct stream path until the new run API is
proven. Add Research-owned endpoints:

| Endpoint | Purpose |
|---|---|
| `POST /research/runs` | Create a run, persist the user turn, enqueue/start execution, return `{run_id, thread_id}`. |
| `GET /research/runs/{run_id}` | Return run metadata/status. |
| `GET /research/runs/{run_id}/events?after=N` | Poll/replay events after sequence `N`. Useful before SSE tail exists. |
| `GET /research/runs/{run_id}/stream?after=N` | SSE replay from `after`, then tail live events. |
| `POST /research/runs/{run_id}/cancel` | Explicit cancellation. |
| `GET /research/threads` | Include current/last run status summary per thread. |
| `DELETE /research/threads/{thread_id}` | Idempotent delete; refuse or require confirmation if a run is active. |

The run creation request should include:

```json
{
  "thread_id": "client-owned uuid or null",
  "question": "raw user question",
  "ticker": "optional typed ticker",
  "provider": "openai|anthropic",
  "model": "resolved model id",
  "effort": "optional effort"
}
```

The server resolves/records the effective credential/auth path. The client
should not send secret-bearing auth data.

## 6. UI Shape

### 6.1 Thread list

Each thread row should show:

- title;
- ticker/scope chip when available;
- latest run status: queued/running/succeeded/failed/cancelled;
- a spinner/progress affordance for active runs;
- `...` action menu for rename/archive/delete later.

Clicking another thread during a run should be allowed. It should switch the
view and attach to that thread's run if it has one. It must not abort another
thread's run.

### 6.2 Input model selector

The input area should contain a real model selector, not only a provider switch.

Default:

- use Settings -> Models -> AI Research route;
- show it as the selected route on new thread/new turn.

Override:

- user can select any available model route from the catalog;
- effort selector updates according to provider/model support;
- submit records provider/model/effort on the run;
- optional future action: "save this route as default".

### 6.3 Conversation body

Each assistant message should keep the current markdown renderer and show a
model badge from the finalized run. If a run is active for the current thread,
the pending area should attach to that run's live or replayed events.

Switching away and back should show the same run state, because the run is owned
by the server and event log, not the component instance.

### 6.4 Evidence/tool trace

The right pane should render from `research_run_events` while a run is active,
and from the finalized assistant message/tool calls after completion. For a
reattached run, it should replay events from `seq=0` or the last known sequence.

## 7. Auth And Provider Constraints

### 7.1 Slice 6 dependency

Before building true concurrent runs, Slice 6 must be fully verified on the live
surface:

- DB-selected OpenAI key affects a real AI Research run;
- switching OpenAI active credential affects the next run;
- Anthropic OAuth-active fallback is explicit and visible;
- no stale OpenAI global client is reused after fallback.

The current Slice 6 implementation is a foundation, but the OpenAI global-client
pattern is a concurrency risk.

### 7.2 Per-run auth isolation

The run manager should execute with a credential/client resolved for that run.
If the OpenAI Agents SDK path cannot avoid a process-global client, the first
server-owned run slice must choose one of these explicit policies:

1. serialize OpenAI runs per process;
2. reject concurrent OpenAI runs with a visible message;
3. refactor the OpenAI run path to accept a per-run client/session safely.

Do not silently allow concurrent OpenAI runs if they can cross-use a stale or
wrong credential.

### 7.3 Slice 7 Claude setup-token driver

`claude_code_oauth` is currently imported/probed and visible in Settings, but
AI Research still falls back to the Anthropic API key. Slice 7 is the work that
actually routes Research through the Claude subscription path.

There are two defensible orders:

- **If subscription auth is the priority:** finish Slice 7 before the run manager
  so the run lifecycle is designed around the real driver.
- **If interruption-free UX is the priority:** build the run manager first using
  existing API-key/fallback paths, but keep Claude OAuth clearly marked as not
  a live Research runtime until Slice 7.

The recommended order is in §9.

## 8. Memory And Context Rules

The run manager must keep C-2c's guarantees:

- history is fetched by `thread_id`;
- no cross-thread transcript injection;
- the stored transcript is never truncated for prompt budget reasons;
- prompt context selection is recorded or at least inspectable;
- provider context overflow becomes a persisted visible error until compaction
  policies are explicitly built.

When a run is created, the server should build history before appending the
current user turn to provider input, as C-2c already does, so the current turn
is not duplicated.

Global memory, strategy profiles, generated skills, and news-filter preferences
are separate tools or artifacts. They can be offered to the agent later, but
they are not implicit thread history.

## 9. Recommended Sequencing

### Phase 0 — Document and hold current safety behavior

Keep the current UI safety patch until the run manager exists:

- pending run blocks thread switching inside the current page;
- navigation can still abort because the stream is page-owned;
- this is a known limitation, not the final architecture.

Do not keep polishing this mode indefinitely.

### Phase 1 — Close Slice 6 live verification

Run the cheap live test now that AI Research model routing exists:

1. Settings -> Models -> AI Research = OpenAI / cheap model / low effort.
2. Run an OpenAI AI Research query with active primary key.
3. Switch active OpenAI credential, run another query.
4. Run Anthropic with Claude OAuth active and confirm explicit env fallback.
5. Switch Anthropic API key active, run once, then restore Claude OAuth if
   desired.

This confirms the current live credential routing before deeper lifecycle work.

### Phase 2 — Decide Slice 7 vs run manager first

Recommended default:

1. Do the small AI Research model selector UI if it remains painful during
   manual testing.
2. Finish Slice 7 Claude subscription Research driver if subscription usage is
   a near-term goal.
3. Then build server-owned runs.

Alternative:

- If interruption-free navigation is more urgent than Claude subscription, do
  server-owned runs first, but explicitly keep Claude OAuth as Settings/probe
  only and preserve env fallback copy.

### Phase 3 — Server-owned run substrate

Build the backend store and API with tests:

- `ResearchRunStore`;
- `research_runs` / `research_run_events`;
- create/status/events/cancel routes;
- idempotent and local-only behavior;
- no PG writes;
- active-run summary on thread list.

Use polling replay first if SSE tailing adds too much risk. Polling every 1-2s
is acceptable for a local desktop app and easier to harden; SSE tail can follow.

### Phase 4 — Background runner

Move execution from request-held `/query/stream` into a sidecar-owned task:

- create run;
- resolve auth/model/effort;
- build per-thread history;
- stream provider events into `research_run_events`;
- persist terminal assistant/error message;
- update run status.

This phase must include explicit cancellation and shutdown behavior.

### Phase 5 — Research UI attach/replay

Update `Research.tsx`:

- submit creates a run instead of owning provider stream directly;
- thread list shows per-thread run status;
- switching threads is allowed;
- nav-away/reload does not cancel;
- current thread attaches to active run events;
- completed thread renders from persisted transcript and trace.

### Phase 6 — Concurrency unlock

Only after per-run auth/client isolation is verified:

- allow multiple threads to run at once;
- show all active runs in the thread list;
- enforce provider-specific concurrency limits visibly.

If OpenAI still requires a process-global client, serialize OpenAI runs or
surface a clear "one OpenAI research run at a time" rule.

### Phase 7 — Long-thread compaction and evidence snapshots

After run lifecycle is stable:

- adapt `AI_RESEARCH_CONTEXT_MEMORY_PLAN.md` summary-plus-recent policy;
- persist evidence snapshots used by a run;
- let later turns refer to exact evidence packets, not only prior prose.

## 10. Acceptance Criteria

The run lifecycle work is not complete until:

- navigating away from AI Research does not cancel an active run;
- switching threads does not cancel another thread's run;
- at least one active run can be reattached after reload or navigation;
- each run records provider/model/effort/auth route;
- each thread's history remains independent;
- deletion/archive behavior is defined for active runs;
- OpenAI credential isolation or serialization is explicit;
- Claude OAuth active state is not presented as live Research subscription use
  until Slice 7 actually wires it;
- tests cover create/run status/event replay/cancel/error persistence;
- GUI verification covers switching threads and opening Settings while a run is
  active.

## 11. Out Of Scope For The First Run-Lifecycle Slice

- Global user memory.
- Strategy/skill generation.
- Vector/graph memory.
- Rich report cards with charts/images beyond current markdown rendering.
- Provider-auto-selection based on cost or quality.
- Running unlimited parallel jobs.
- Replacing the C-2 event vocabulary.

## 12. Open Questions For Review

1. Should the first run manager use polling replay before SSE tailing?
2. Should deleting an active thread be blocked, cancel-and-delete, or archive
   first?
3. Should per-run model override be built before server-owned runs, or bundled
   into run creation?
4. Should Slice 7 Claude subscription driver precede server-owned runs?
5. What concurrency rule should v1 expose if OpenAI remains process-global:
   serialize, reject concurrent OpenAI, or refactor first?

## 13. Reviewer refinements (verified, 2026-06-18)

Review verdict: sound, no blockers. Three additive refinements, each verified
against the installed code, not just opinion:

### 13.1 Per-run OpenAI client isolation IS achievable — target option 3, not "serialize forever"

§7.2 treats the process-global client as possibly unavoidable. It is avoidable.
The installed `openai-agents` SDK exposes `RunConfig(model_provider=...)`,
`OpenAIProvider`, `MultiProvider`, and `OpenAIResponsesModel(openai_client=...)`
(verified: `RunConfig` has a `model_provider` field; these classes are exported).
So a run can pass `Runner.run(agent, run_config=RunConfig(model_provider=
OpenAIProvider(openai_client=<per-run client>)))` (or build the `Agent` with
`model=OpenAIResponsesModel(openai_client=<per-run client>)`) and NEVER touch the
process-global `set_default_openai_client`. §7.2 option 3 (per-run client) should
therefore be the TARGET, and the Phase-4 background runner should adopt it from
the start rather than shipping serialize-only.

Also load-bearing: **serialize-only (option 1) is NOT actually safe today**, because
the global is also written by non-run OpenAI paths (`_build_agent`'s per-build
`apply_openai_live_client`, and card-synthesis/translation). Even one OpenAI run
at a time can have its global stomped by a concurrent card-synthesis call. So the
honest framing is: per-run client isolation is the only correct basis for *any*
concurrency, and once it lands the "serialize OpenAI" fallback is unnecessary.
(Migrating `_build_agent`'s global-set to a per-run `RunConfig` also retires the
Slice-6 process-global risk noted in CREDENTIAL_MANAGEMENT_PLAN — a clean win.)

### 13.2 Orphaned-run reconciliation on sidecar startup (gap in the data model + acceptance)

§3.3 lists "app shuts down" as a cancellation path, but a sidecar restart mid-run
leaves a `research_runs` row stuck at `running` (its in-process task is gone). The
background runner has no way to resume an in-flight provider call across a process
restart. Add an explicit boot-time reconcile: on `ResearchRunStore` init, sweep
`status IN ('queued','running')` rows whose owning process is gone → mark
`interrupted` (a terminal status; persist a matching error assistant turn per the
C-2b no-dangling-user-turn rule). Add to §4 (data model notes) and §10 (acceptance:
"a run left `running` by a sidecar crash is reconciled to a terminal state on next
boot, not shown as perpetually running").

### 13.3 `research_run_events` is a replay buffer, not an archive — prune on terminal

`research_messages` is the final transcript authority (§4 says so), so the event
log only needs to live during a run + a short reattach grace. To bound SQLite
growth (every thinking/text/tool delta is a row), v1 should DELETE a run's events
on terminal + grace (or a small per-run cap with a logged truncation marker — no
silent drop, per the project's no-silent-cap rule). The finalized assistant
message + tool_calls remain the post-run trace source (§6.4 already says this).

These do not change the plan's direction or sequencing — they sharpen §7.2 (the
concurrency story is "isolate", not "serialize"), close the restart gap, and bound
the event log.

