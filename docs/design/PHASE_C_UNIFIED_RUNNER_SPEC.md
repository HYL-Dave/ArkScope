# Phase C — Unified Agent Runner Spec

> **Status**: spec ready for commit 1 — review-pass-1 closed (3 High + 2 Medium + 1 Low) and §8 open questions all resolved 2026-05-02.
> **Predecessor**: P0.1 Replay Harness full v1 (`docs/design/P0_1_FULL_V1_SPEC.md`) + P1.4 Compression Phase B (`docs/design/P1_4_SPEC.md`). Both prerequisites green.
> **Goal**: collapse ~3,800 lines of dual-SDK duplication (`src/agents/anthropic_agent/` + `src/agents/openai_agent/`) into a single runner package while preserving every behaviour the replay harness can detect. **Phase C v1 is a refactor** — it does NOT replace the `openai-agents` SDK with raw Responses API (that's Phase C v2, separate cycle, separate spec). The OpenAI runner in v1 wraps `Runner.run()` from the SDK and transforms its output to the unified shape.

---

## 1. Framing

The single most important sentence of this spec:

> **Phase C is a refactor, not a feature.** Every commit must keep all 7 replay fixtures green and the 294-test cross-suite regression passing. A change that "improves" behaviour in a way the replay net cannot detect is out of scope for v1 — even if the improvement seems obviously correct.

The replay harness exists to make this safe. The whole point of P0.1 full-v1 was to give Phase C a regression vector; that vector now fires whenever pytest runs. Phase C consumes the safety net by treating fixture green-ness as an inviolable per-commit gate.

### 1.1 What's actually duplicated today

Verified file sizes (2026-05-02):

| File | LoC | Role |
|---|---|---|
| `src/agents/anthropic_agent/agent.py` | 606 | Anthropic message loop, streaming, thinking, capture wiring |
| `src/agents/anthropic_agent/tools.py` | 1,757 | Manual tool schema in Anthropic JSON shape + `execute_tool` dispatch |
| `src/agents/openai_agent/agent.py` | 882 | OpenAI agents-SDK loop wrapper, capture wiring |
| `src/agents/openai_agent/tools.py` | 1,208 | `@function_tool` wrappers around the same DAL calls |
| `src/agents/shared/subagent.py` | 567 | Per-provider subagent dispatch (mostly already shared) |
| **Total** | **5,020** | |

Most of the duplication is in `*/tools.py` (2,965 LoC combined) — the SAME DAL calls dressed in two different schema forms. Some lives in `*/agent.py` (1,488 LoC combined) — two implementations of "stream messages, accumulate tool calls, dispatch, append results." `subagent.py` is mostly already shared and is touched only where the per-provider dispatch needs the unified runner.

`shared/` already has the cleanly-extracted bits — `attachments.py`, `compressor.py`, `context_manager.py`, `replay.py`, `server_tools.py`, `bridge_tools.py`, `skills.py`, `token_tracker.py`. Phase C does not re-shape those; it adds `runner/` next to them.

### 1.2 Non-goals (explicit)

Phase C v1 does **NOT** introduce, design, or implement:

- **New behaviour.** No new tool semantics, no new flags exposed to users, no new CLI commands. If a behaviour wasn't there before, it isn't there after.
- **Removal of the `openai-agents` SDK.** Phase C v1 keeps the dependency installed AND keeps the SDK's `Runner.run()` driving the OpenAI tool loop — the unified `OpenAIRunner` is a **wrapper that adapts SDK output to the unified `ToolResult`/`AgentEvent` shape**. Replacing the SDK with raw Responses API is a behavior migration (event shape, history handling, retry semantics, `auto_previous_response_id`) that the replay net only partially covers. That migration is **Phase C v2**, with its own spec, its own fixture additions, and its own risk register. Conflating the two in one cycle violates "refactor, not feature."
- **Provider feature unification beyond what the replay net covers.** If a provider-only knob (e.g. Anthropic `cache_control` on the last tool, OpenAI `auto_previous_response_id`) doesn't show up in any fixture, Phase C treats it as a per-provider implementation detail, NOT a unified-API surface to design.
- **Skill / subagent / compaction redesign.** Those modules call into the runner; the runner doesn't re-architect them. v1 may add small adapter shims if their current API assumes a specific provider.
- **Streaming chunk merge or token-level capture.** Same status as P0.1 §1.1 — defer until a use case appears.
- **Phase A (Knowledge Graph) prerequisites.** Separate cycle; Phase C may NOT add hooks "in case Phase A wants them."
- **Performance optimisation.** If the unified path is measurably slower than the old paths on a real query, that's a finding to fix; but micro-benchmarks chasing single-digit-percent gains are out of scope.

### 1.3 Guarantees

After Phase C v1, callers / future refactors are guaranteed:

1. **Single source of truth for tool dispatch.** `ToolRegistry` is the canonical built-in tool table (current count is in `tests/test_registry.py`; do not hard-code in spec). Bridge-only tools (`delegate_to_subagent`) live in `shared/bridge_tools.py`. Server tools (`server:web_search`) live in `shared/server_tools.py`. The unified runner consults all three via the same resolver the replay validator already uses.
2. **Provider-symmetric public API.** `runner.run_stream(question, attachments)` and `runner.run(question, attachments)` produce the same event-shape regardless of whether the underlying provider is Anthropic or OpenAI. Provider-specific knobs ride inside the `AgentConfig` / per-provider runner subclass, not the public method signature.
3. **Replay capture is unchanged.** `ReplayCapture` keeps its current API; the unified runner calls `set_initial` / `record_tool_call` / `record_final` at the same lifecycle points. Existing fixtures continue to validate clean.
4. **Subagent dispatch unchanged from caller view.** `delegate_to_subagent` keeps its arg shape (`subagent`, `task`, `context_json`). The dispatch implementation may switch to use the unified runner internally, but `subagent_traces` capture continues to record the same shape.
5. **Feature flag gates the cutover.** Until the FINAL commit, `agent_config.use_unified_runner` (default OFF) selects which path runs. Final commit deletes the flag and the old paths in one step, AFTER all fixtures pass on the unified path.

---

## 2. Scope locks

### 2.1 v1 boundaries (what's in)

**In scope**:

- New package `src/agents/runner/` containing:
  - `message_types.py` — provider-neutral `ToolCall`, `ToolResult`, `TurnResult`. `AgentEvent` continues to live in `src/agents/shared/events.py` (existing — runner imports, doesn't redefine).
  - `tool_dispatch.py` — `UnifiedToolDispatch` driving `ToolRegistry` + bridge tools, plus per-provider tool-schema builders that consume `shared/server_tools.py` directly (not via the old `_build_anthropic_tools_list` / `_build_openai_all_tools` shims, which get deleted in commit 7).
  - `base.py` — `UnifiedAgentRunner` ABC with shared `_tool_loop` / `_execute_tools` / `_emit_event`
  - `anthropic.py` — `AnthropicRunner` subclass: `messages.stream()`, thinking adaptive/enabled, cache_control on last tool, capture wiring, `ContextManager` (Layer 0-6 client-side compaction).
  - `openai.py` — `OpenAIRunner` subclass: **wraps `openai-agents` SDK `Runner.run()`** and transforms output (raw_responses + final output) to the unified `ToolResult` / `AgentEvent` shape. Continues to use `OpenAIResponsesCompactionSession` / server-side compaction (the SDK's mechanism), NOT `ContextManager`. SDK stays as a runtime dependency.
- Per-provider tool-schema builders that consume `ToolRegistry` + `shared/server_tools.py` and emit Anthropic JSON / OpenAI function tool shape — replacing the hand-written schemas in `*/tools.py`.
- Subagent dispatch refactored to use the unified runner internally (no behavioural change visible to callers).
- Cutover flag `agent_config.use_unified_runner` (bool, default False) routing CLI / API / subagent through new vs old code.
- Final commit removes old `*/agent.py` + old `*/tools.py`. **`openai-agents` SDK stays installed** — its removal is Phase C v2.

**Out of scope** (defer to v1.1+):

- New provider-neutral options (e.g. unified `effort` enum across both providers — current per-provider config stays).
- Streaming token-level event capture.
- Multi-round runner (run -> review -> revise loops).
- New observability fields beyond what `Scratchpad` already emits.
- `MAJOR_REFACTORING_PLAN.md`'s "parallel tool batch" concurrency design — explicitly deferred; v1 keeps the current sequential dispatch.

### 2.2 Replay-gate use during cutover (LOAD-BEARING)

Every commit in the chain must satisfy:

1. **Pre-commit**: `python -m pytest tests/test_replay_fixtures.py tests/test_replay.py tests/test_replay_openai.py -q` exits 0.
2. **Pre-commit**: `python -m pytest tests/test_subagent.py tests/test_agents.py tests/test_tool_calling.py tests/test_attachments.py tests/test_context_manager.py -q` exits 0.
3. **For commits 4-7 only**: with `agent_config.use_unified_runner=True`, run the live capture path against a smoke query (`ARKSCOPE_REPLAY_CAPTURE=1`) and verify the produced trace validates clean against the registry. This is a manual smoke, NOT automated yet — automation lands when CI does (separate cycle).

A commit that breaks any of (1) / (2) is rolled back, NOT shipped with a "fix-up next commit" promise. The replay net is the gate; bypassing it forfeits the whole reason Phase C is safe to attempt.

### 2.3 Feature parity matrix (what must keep working)

This table is the per-commit acceptance checklist. Phase C ships when every row is ✅ on the unified path AND old paths are deleted.

| # | Behaviour | Anthropic today | OpenAI today | Unified target |
|---|---|---|---|---|
| 1 | Tool schema emission | hand-written in `tools.py` | `@function_tool` wrappers | derived from `ToolRegistry` per-provider builder in `runner/tool_dispatch.py` |
| 2 | Tool dispatch | `execute_tool()` switch | SDK auto-dispatches wrapper functions | `UnifiedToolDispatch.execute(name, args)` via `ToolRegistry` |
| 3 | Streaming / call shape | `messages.stream()` direct | SDK `Runner.run()` returns `RunResult` with `raw_responses` | Anthropic subclass: `messages.stream()` directly. OpenAI subclass: wraps `Runner.run()`, walks `raw_responses` to extract tool calls, transforms to `ToolResult` sequence. Both emit the same `AgentEvent` shape from `shared/events.py`. |
| 4 | Thinking | adaptive (Opus 4.6 / Sonnet 4.6) or enabled w/ budget | `reasoning_effort` param via SDK | provider-specific config inside subclass |
| 5 | Cache control | `cache_control` on system + last tool | SDK-automatic | Anthropic subclass adds it; OpenAI subclass no-op (SDK handles) |
| 6 | Tool-name canonicalization | Anthropic names already canonical | strip `tool_` prefix in capture | unified path stores canonical names directly |
| 7 | Server tools (web_search) | append via `_build_anthropic_tools_list` | append via `_build_openai_all_tools` | `runner/tool_dispatch.py::tools_for_provider(config)` consumes `shared/server_tools.py` directly. The old `_build_*_tools_list` shims get deleted in commit 7; the unified runner doesn't depend on them. |
| 8 | Bridge tools (delegate_to_subagent) | injected manually | `tool_delegate_to_subagent` wrapper | unified handler calls `dispatch_subagent` directly; `bridge_tools.py` spec drives schema |
| 9 | Subagent dispatch | `_run_anthropic_subagent` | `_run_openai_subagent` | `dispatch_subagent` invokes unified runner with role-specific config |
| 10 | Attachments | `to_anthropic_blocks` | `to_openai_blocks` | per-provider subclass calls existing `AttachmentManager` methods |
| 11a | Anthropic compaction Layers 0-6 (client-side) | wired via `ContextManager` → `ContextCompressor` | n/a | preserved in `AnthropicRunner` — same `ContextManager` instance, same lifecycle |
| 11b | OpenAI compaction (server-side / SDK) | n/a | `OpenAIResponsesCompactionSession` (SDK) + `server_compaction` setting | preserved in `OpenAIRunner` — keeps SDK-driven compaction. **Phase C does NOT try to unify the compaction mechanism**; the asymmetry is real and load-bearing. Layer 0-6 client-side compaction stays Anthropic-only. |
| 12 | Token tracking | per-provider counter | per-provider counter | per-subclass `_extract_tokens()` feeds shared `TokenTracker` |
| 13 | Replay capture | `ReplayCapture` set/record/save | symmetric | unified runner calls same hooks at same lifecycle points |
| 14 | Scratchpad events | `thinking`, `pause_turn`, `compaction`, `retry` | symmetric | shared event emission in `base.py`; `AgentEvent` reused from `shared/events.py` |
| 15 | Effort config | `anthropic_effort` | `openai_effort` | provider-specific config consumed by subclass |
| 16 | Skills | `expand_skill` produces a query string before runner enters | unchanged | unchanged — runner never sees the skill, only the expanded query |
| 17 | Max tool calls | `max_tool_calls` from config | `max_tool_calls` from config | shared in `_tool_loop` |
| 18 | 21333-tokens streaming workaround | `messages.stream()` | n/a | preserved in Anthropic subclass |
| 19 | `auto_previous_response_id` | n/a | OpenAI SDK Runner option | OpenAI subclass keeps SDK Runner so `auto_previous_response_id=True` continues to work as today. **Phase C v1 does NOT switch to raw Responses API** — that migration is Phase C v2 (separate spec); it would change history-replay semantics and need its own fixture coverage. |

A row marked "shared in `base.py`" is unified across providers. A row marked "per-subclass" stays in the subclass. Phase C does NOT try to abstract over rows that are genuinely provider-specific (compression in particular: row 11 splits explicitly because Anthropic uses our `ContextManager` and OpenAI uses the SDK's `CompactionSession` — these are different mechanisms with different costs and Phase C preserves both).

---

## 3. Architecture

### 3.1 Package layout

```
src/agents/runner/
  __init__.py                — public exports: AnthropicRunner, OpenAIRunner, build_runner(provider, config, dal)
  message_types.py           — ToolCall, ToolResult, TurnResult (AgentEvent reused from shared/events.py)
  tool_dispatch.py           — UnifiedToolDispatch + provider-shape tool schema builders consuming shared/server_tools.py
  base.py                    — UnifiedAgentRunner ABC + shared _tool_loop / _execute_tools / _emit_event
  anthropic.py               — AnthropicRunner concrete (messages.stream(), ContextManager, cache_control)
  openai.py                  — OpenAIRunner concrete (wraps openai-agents SDK Runner.run() + transforms output to unified shape; keeps OpenAIResponsesCompactionSession)
```

Total estimated LoC: ~900-1,100. Net delete: ~3,800 (old `*/tools.py` + old `*/agent.py`). `subagent.py` stays at ~567 with internal calls retargeted to unified runner; net delta there is small (~50 lines either direction). `openai-agents` SDK stays installed — Phase C v1 keeps it as a dependency that `OpenAIRunner` calls into. The dependency removal is Phase C v2.

### 3.2 Key types

```python
# message_types.py
@dataclass
class ToolCall:
    name: str                    # canonical registry name
    arguments: Dict[str, Any]
    raw_name: Optional[str]      # provider-side raw name for traceability

@dataclass
class ToolResult:
    call: ToolCall
    output: str                  # serialized result
    error: Optional[str]
    compression: Optional[Dict[str, Any]]  # Layer 0 marker

@dataclass
class TurnResult:
    final_text: str
    tool_calls: List[ToolResult]
    usage: Dict[str, Any]        # token tracker summary
    stop_reason: str             # provider-native code, surfaced as-is

class AgentEvent:                # already in shared/scratchpad — runner emits, doesn't redefine
    ...
```

### 3.3 Public API

```python
class UnifiedAgentRunner(ABC):
    def __init__(self, config: AgentConfig, dal: DataAccessLayer, ...): ...

    async def run_stream(
        self,
        question: str,
        attachments: Optional[List[Attachment]] = None,
        capture: Optional[ReplayCapture] = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Stream agent events. Caller is responsible for capture lifecycle if it
        wants one — runner just calls set_initial/record_tool_call/record_final
        on the passed-in object."""

    async def run(
        self,
        question: str,
        attachments: Optional[List[Attachment]] = None,
        capture: Optional[ReplayCapture] = None,
    ) -> TurnResult:
        """Convenience wrapper that consumes run_stream and aggregates."""

    # Abstract — per-provider:
    @abstractmethod
    async def _call_api(self, messages, tools, **kwargs): ...
    @abstractmethod
    def _format_messages(self, history): ...
    @abstractmethod
    def _format_tools(self, tool_names): ...
    @abstractmethod
    def _extract_tokens(self, response): ...
    @abstractmethod
    def _extract_tool_calls(self, response): ...

    # Shared concrete:
    async def _tool_loop(self, ...): ...
    async def _execute_tools(self, calls): ...
    def _emit_event(self, event): ...
```

### 3.4 Cutover flag

`AgentConfig.use_unified_runner: bool = False`. Wiring:

- `cli.py::run_anthropic_interactive` and `cli.py::run_openai_interactive` consult the flag and dispatch to either old code or new runner.
- API routes that build agents (for example `/query`) consult the same flag.
- `subagent.py::dispatch_subagent` consults the flag.

The flag is **read-only at runtime** — flipping mid-session would split state. CLI startup reads it once.

---

## 4. Commit chain

**7 implementation commits (1-7)** plus the spec landing (commit 0, this doc). The chain table below has 8 rows total because the spec is row 0.

| # | Commit | Files touched | Replay-gate state |
|---|---|---|---|
| 0 | Spec lands (this doc) | `docs/design/PHASE_C_UNIFIED_RUNNER_SPEC.md` | unchanged (doc-only) |
| 1 | `runner/message_types.py` + `runner/tool_dispatch.py` + tests | NEW: 2 files in `runner/`, NEW: `tests/test_runner_dispatch.py` | unchanged — old paths still authoritative |
| 2 | `runner/base.py` — extract tool loop + event emission from current Anthropic agent | NEW: `runner/base.py`, NEW: `tests/test_runner_base.py`; MOD: none (old code unchanged) | unchanged |
| 3 | `runner/anthropic.py` — concrete AnthropicRunner; flag wiring (default OFF) | NEW: `runner/anthropic.py`, NEW: `tests/test_runner_anthropic.py`; MOD: `cli.py`, `api/routes/query.py`, `subagent.py` to consult flag | unchanged when flag OFF; with flag ON, fixtures must validate clean |
| 4 | `runner/openai.py` — concrete OpenAIRunner **wrapping `openai-agents` SDK `Runner.run()`** (NOT raw Responses API); flag wiring | NEW: `runner/openai.py`, NEW: `tests/test_runner_openai.py`; MOD: same call sites as commit 3 | unchanged when flag OFF; with flag ON, OpenAI fixtures must validate clean |
| 5 | Subagent dispatch routes through unified runner when flag ON | MOD: `subagent.py`, NEW: `tests/test_subagent_unified.py` | subagent fixture must validate clean with flag ON |
| 6 | Flip flag default to ON; fix anything that fails | MOD: `config.py` (default), any test that hard-codes `use_unified_runner=False` and now needs to assert legacy behaviour explicitly | all fixtures must validate clean by default |
| 7 | Delete old `*/agent.py` + `*/tools.py` + flag (KEEP `openai-agents` SDK installed) | DEL: `anthropic_agent/agent.py`, `anthropic_agent/tools.py`, `openai_agent/agent.py`, `openai_agent/tools.py`; MOD: `config.py` removes `use_unified_runner` flag; MOD: imports across ~20 sites that reference the deleted modules. **`requirements.txt` is unchanged** — `openai-agents` stays installed; `OpenAIRunner` continues to import from it. SDK removal is Phase C v2. | all fixtures must validate clean |

Review checkpoint after each commit, same cadence as P1.4 / P0.1. Spec sync after each commit if any decision drifts.

---

## 5. Acceptance criteria

### 5.1 Per-commit (every commit must satisfy)

- All 7 replay fixtures validate clean (`tests/test_replay_fixtures.py`).
- 294-test cross-suite regression passes (`test_replay`, `test_replay_fixtures`, `test_replay_openai`, `test_subagent`, `test_agents`, `test_tool_calling`, `test_attachments`, `test_context_manager`).
- For commits adding new modules: ≥80% line coverage on the new module via dedicated test file.
- No new public API beyond what this spec lists.
- `OpenAIRunner` keeps the `openai-agents` SDK as the underlying tool-loop engine — no new direct calls to raw `openai.responses.create()`. The unified runner is an adapter around `Runner.run()`.

### 5.2 Per-commit (specific)

- **Commit 1**: `UnifiedToolDispatch.execute("get_ticker_news", {"ticker":"NVDA"})` returns the same string the existing dispatch would. Provider-shape builders produce schemas equal-shape to current `get_anthropic_tools()` and current `create_openai_tools(dal)`.
- **Commit 2**: `base.py::_tool_loop` driven by a synthetic `_call_api` mock produces the same `ToolResult` sequence as the current Anthropic loop given the same fixture-derived inputs.
- **Commit 3**: with `use_unified_runner=True`, running an Anthropic smoke query against the live API produces a replay trace whose tool_calls + tools_available + final_answer match a captured baseline trace from the old path (text equivalence is best-effort because LLM is non-deterministic; STRUCTURE equivalence is required).
- **Commit 4**: with `use_unified_runner=True`, running an OpenAI smoke query against the live API produces a replay trace whose tool_calls + tools_available + final_answer match a captured baseline trace from the old SDK-driven path. `OpenAIRunner` calls `openai-agents` `Runner.run()` internally; the wrapper transforms `RunResult.raw_responses` to `ToolResult` via the same walker the old capture path uses. **`auto_previous_response_id=True` keeps working** (SDK Runner option preserved). Token usage stays linear (no quadratic regression vs old SDK path). Manual smoke on the 14-tool-type query that originally exposed the context-overflow issue (per `MEMORY.md` "OpenAI Context Overflow Fix") must succeed.
- **Commit 5**: subagent fixture validates clean with `use_unified_runner=True`. Bridge-drop monkeypatch test still fires (resolver contract preserved).
- **Commit 6**: flipping flag default to True does not change any test outcome (every test that depended on the old path is either updated or now explicitly opts out via `use_unified_runner=False`).
- **Commit 7**: `grep -rn 'from src.agents.anthropic_agent\|from src.agents.openai_agent' src/ tests/ scripts/` returns zero non-test hits (test hits OK iff the test specifically targets the about-to-be-deleted modules and is itself slated for removal). `agent_config.use_unified_runner` no longer exists in `AgentConfig`. **`pip show openai-agents` still reports installed** — that's intentional. `OpenAIRunner` continues to import from `agents.*` modules.

### 5.3 Integration

- `python -m pytest -q` (full suite) is green.
- Manual smoke: `ARKSCOPE_REPLAY_CAPTURE=1 python -c "import asyncio; from src.agents.runner import build_runner; ..."` produces traces under `data/replay/` that load via `load_trace` and validate clean.

---

## 6. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `OpenAIRunner` wraps SDK Runner — output transformation (`raw_responses` → `ToolResult`) drops a field the old path consumed | Medium | High | Commit 4 acceptance asserts STRUCTURE equivalence with a baseline trace captured from the old path. The same walker used by today's capture path (proven on 8 production queries via P0.1 OpenAI fixtures) is reused inside `OpenAIRunner`. |
| `auto_previous_response_id` linear-token semantics regress because the unified loop calls `Runner.run()` differently | Medium | High | OpenAIRunner sets `auto_previous_response_id=True` when calling `Runner.run()`. Token-tracking regression test on the 14-tool-type query (per `MEMORY.md` "OpenAI Context Overflow Fix") is the gate. |
| Cache control / cache hit rate regresses on Anthropic path | Medium | Medium | `TurnUsage.cache_creation_tokens` + `cache_read_tokens` already tracked; commit-3 acceptance includes a cache-hit assertion on a repeated query. |
| Anthropic compaction Layers 0-6 re-wire under unified runner | Medium | High | `ContextCompressor` + `ContextManager` APIs are stable; `AnthropicRunner` just calls them. Layer 5 caller currently builds `AnthropicSummaryCaller` in `cli.py` — verify same construction site survives. |
| OpenAI compaction (`OpenAIResponsesCompactionSession`) re-wire under unified runner | Medium | High | The wrapper preserves SDK-driven compaction by passing the same `session=` argument shape into `Runner.run()`. **Phase C does NOT migrate OpenAI to ContextManager** — that would be a behaviour change. |
| Subagent dispatch paths fork between flag-ON and flag-OFF during commits 3-5 | High | Medium | Both dispatch paths must keep `subagent_traces` shape identical — replay fixture catches divergence. |
| Skills (`/skill full_analysis NVDA`) behaviour changes | Low | Low | Skills resolve to a query string BEFORE runner enters; runner never sees skill semantics. Verify via existing `test_skills.py`. |
| `provider_tool_name` field on capture stops being populated for OpenAI | Medium | Medium | Forward-safeguard test `test_bridge_helper_stays_in_sync_with_openai_surface` asserts the bridge-tool surface; capture-side test asserts canonicalization end-to-end. |
| Final commit deletes old code while a downstream caller still imports it | Low | High | Pre-commit check: `grep -rn 'from src.agents.anthropic_agent' src/ tests/ scripts/` returns zero non-test hits before commit 7. |
| Flag flip (commit 6) silently breaks a code path not covered by tests | Medium | Medium | Manual smoke matrix at commit 6: CLI Anthropic / CLI OpenAI / API `/query` Anthropic / API `/query` OpenAI / subagent for each role. |
| Replay capture API drifts under unified runner without fixture-level signal | Low | High | The replay validator gates `tool_calls[].name`, `tools_available`, `attachments_shape`, `subagent_traces`, `pinned_tool_names` — a capture API drift that doesn't show up across all those is unlikely; if it does, the gap becomes a v1.1 capture-spec bug. |
| Estimated LoC delta off by >50% | Medium | Low | Acceptable. The motivation is the single-source-of-truth property, not the LoC saving. If runner/ ends up at 1,500 LoC instead of 1,100, that's fine as long as old code is gone. |
| **(Phase C v2 candidates, NOT v1 risks)**: SDK `Runner.run()` event-shape drift on SDK upgrade; raw Responses API behaviour differs from agents-SDK (event shape, retry, history-replay); `auto_previous_response_id` semantics need re-implementation under raw API | n/a | n/a | All deferred to Phase C v2 spec. v2 will need additional fixtures specifically covering streaming/retry/error-event shapes that v1 fixtures do not gate. |

---

## 7. Cross-references

- `docs/design/P0_1_FULL_V1_SPEC.md` — replay harness contract Phase C inherits.
- `docs/design/P1_4_SPEC.md` — compression layer API the runner must continue to invoke.
- `docs/design/MAJOR_REFACTORING_PLAN.md` §Phase C — original framing (this spec is the authoritative version).
- `docs/design/PROJECT_PRIORITY_MAP.md` §4 P2.1 — tracker entry; status will flip to "▶ ACTIVE (commit chain)" after spec review and "✅ done" once commit 7 lands.
- `src/agents/shared/replay.py` — validator + unified resolver (don't modify in Phase C; only call).
- `src/agents/shared/server_tools.py` + `src/agents/shared/bridge_tools.py` — single source of truth for hosted + bridge tools.
- `tests/test_replay_fixtures.py` — the parametrised gate that fires every commit.
- `tests/replay_fixtures/*.json` — the 7 fixtures that must stay green.

---

## 8. Open questions — RESOLVED 2026-05-02

All five questions closed before commit 1 opens. Decisions are locks, not leans — spec follow-ups override them only with an explicit decision-log entry.

1. **`runner/__init__.py` public API**: ✅ `build_runner(provider, config, dal, ...)` is the official public entrypoint. `AnthropicRunner` / `OpenAIRunner` are also exported but labeled in their docstrings as "for tests / advanced direct construction only." Business call sites (CLI, API routes, subagent dispatch) MUST go through `build_runner`. Rationale: keeps provider-subclass selection in one place; future v2 / parallel runner / dispatch policy changes ride inside the factory without touching call sites.

2. **`AgentEvent` reuse**: ✅ Import `AgentEvent` + `EventType` exclusively from `src/agents/shared/events.py`. `runner/message_types.py` does NOT redefine them. `message_types.py` owns ONLY runner-domain data types (`ToolCall`, `ToolResult`, `TurnResult`). Rationale: events are an existing cross-module observability contract (Scratchpad consumes them); the runner emits, it doesn't fork the type.

3. **Streaming chunk granularity**: ✅ v1 emits the existing coarse `AgentEvent` shape only — no raw provider-delta passthrough on the public `run_stream` API. Anthropic subclass MAY consume `messages.stream()` deltas internally to assemble whole-message events, but those deltas do NOT leak through `run_stream`. Token-level / raw-delta stream is a Phase C v2 candidate (or later) — P0.1 explicitly does not capture token-level streams (P0.1 §1.1 non-goal), so v1 has no fixture-level signal to gate the wider event surface.

4. **subagent.py refactor scope**: ✅ Commit 5 adds a thin `dispatch_subagent_unified` (or equivalent) path that the runner consults when the flag is ON. Legacy `_run_anthropic_subagent` / `_run_openai_subagent` STAY through commit 6 and are deleted at commit 7 alongside the rest of the legacy code. Rationale: inline-replace at commit 5 makes flag-ON vs flag-OFF dispatch hard to compare during review; keeping both paths through commit 6 lets the bridge-drop / pin-rejection / arg-shape regression tests fire against either side identically.

5. **Test file naming**: ✅ Flat `tests/test_runner_*.py` — e.g. `tests/test_runner_dispatch.py`, `tests/test_runner_base.py`, `tests/test_runner_anthropic.py`, `tests/test_runner_openai.py`, `tests/test_subagent_unified.py`. Repo convention is flat (no `tests/runner/` nested dir); honoring it minimises the "where do I put / find this?" overhead. Test ordering / discovery / coverage tooling all stay unchanged.

---

## 9. Phase C v2 — deferred (separate spec, separate cycle)

Phase C v2 is **out of scope for this spec**. This section exists only to record what gets handed off:

- Replace `OpenAIRunner`'s SDK-backed `Runner.run()` adapter with raw `openai.responses.create()` calls.
- Re-implement `auto_previous_response_id` linear-token semantics directly (preserve the production fix; manual gate via the same 14-tool-type query).
- Re-implement retry-on-rate-limit, history compaction shape, error event surfacing — all currently abstracted by the SDK.
- Add fixtures specifically covering the SDK→raw-API drift cases the existing 7 fixtures do NOT gate (likely: streaming partial tool-call merge, retry-after error, multi-turn history truncation behaviour).
- Remove `openai-agents` from `requirements.txt`; remove all `from agents.* import` lines from `src/`.

v2 spec will live at `docs/design/PHASE_C_V2_OPENAI_RAW_API_SPEC.md` when started. Trigger condition: Phase C v1 is fully merged (commit 7 lands), AND a concrete reason emerges to remove the SDK (e.g. SDK becomes unmaintained, SDK upstream behaviour drift breaks fixtures, raw API gives access to features the SDK abstracts away). v2 is NOT a default-next item — it's a parked option.
