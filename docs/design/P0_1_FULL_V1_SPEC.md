# P0.1 Replay Harness - Current Authority

> **Status:** SHIPPED. Current contract refreshed 2026-08-17 after the
> legacy-agent surface retirement. The original implementation narrative is
> retained in Git history.
>
> **Purpose:** define the replay safety net that current API and agent paths
> must preserve. This is a structural regression gate, not deterministic model
> replay.

## 1. Framing

The replay harness records enough information to detect drift in tool
availability, tool-call shape, system-prompt identity, nested subagent
expectations, and compression metadata. It does not attempt to reproduce a
model answer byte-for-byte.

### 1.1 Non-goals

The current contract does not:

- execute a live model while validating fixtures;
- compare generated prose for deterministic equality;
- merge token-level streaming chunks;
- expose a document-input schema; or
- use replay as a compatibility layer for removed product surfaces.

Future document understanding requires its own source-to-page, provenance,
security, and model-routing design. It is not part of replay schema authority.

### 1.2 Guarantees

1. **Library boundary.** Replay records behavior as data and does not import
   compressor internals or own an agent runner.
2. **Provider parity.** Anthropic and OpenAI captures use the same
   ReplayTrace and validator entry point.
3. **Required resolution.** Every recorded tool call and every explicitly
   pinned tool name must resolve through the current tool authorities.
4. **Expected additions stay green.** A newly registered tool that no fixture
   depends on does not invalidate existing fixtures.
5. **Capture is non-fatal.** Capture failures are logged and never replace the
   underlying agent result.
6. **Capture is opt-in.** ARKSCOPE_REPLAY_CAPTURE remains off by default.

## 2. Current Contract

### 2.1 Capture and canonical names

ReplayTrace records:

- schema version, timestamp, explicit api or test entrypoint, provider, model,
  session, and turn;
- system-prompt hash, user input, and sorted visible tool names;
- canonical tool calls with normalized arguments, digests, result shape,
  optional compression metadata, and optional provider bridge name;
- final answer, final-answer hash, usage, and notes; and
- optional nested subagent traces and required-resolution tool pins.

The current programmatic Anthropic and OpenAI query paths construct
ReplayCapture with an explicit entrypoint. There is no implicit presentation
surface default.

#### 2.1.1 Tool-name canonicalization

Provider bridge names are normalized to the registry name before validation.
The optional provider_tool_name field preserves the SDK-facing bridge name for
diagnostics, but validator lookup always uses the canonical name.

#### 2.1.2 Provider-native server tools

Hosted tools remain outside ToolRegistry, so replay identifies them with the
server: namespace. src/agents/shared/server_tools.py is the single source of
truth for which hosted kinds are currently wired. Capture and validation must
consult that shared authority rather than maintain parallel allowlists.

### 2.2 Fixture and schema authority

The current fixture set is:

    no_tool_turn.json
    one_tool_turn.json
    openai_no_tool_turn.json
    openai_one_tool_turn.json
    p1_4_l0_overflow.json
    subagent_turn.json

Older fixture JSON remains loadable when optional current fields are absent.
The loader requires the core trace keys, validates the schema version, and
ignores unknown keys so historical traces do not need destructive rewriting.

subagent_traces is an opt-in nested structural contract. Live nested capture is
not implied; the hand-authored fixture pins child tool resolution and
role-prefixed validation errors.

pinned_tool_names is never a skip list. Every listed name must resolve.

### 2.3 Unified resolver contract

Resolution order is:

1. ToolRegistry;
2. hosted-tool authority in src/agents/shared/server_tools.py; and
3. bridge-only authority in src/agents/shared/bridge_tools.py.

Registry tools use the live ToolDefinition argument contract. Hosted and
bridge tools use their bounded shared specs. Missing tools, missing required
arguments, and unknown arguments are errors. Prompt or availability drift that
does not break a required contract remains diagnostic.

## 3. Validation Gate

tests/test_replay_fixtures.py parametrizes every fixture and validates it
without provider traffic. tests/test_replay.py and tests/test_replay_openai.py
own schema, capture, canonicalization, hosted-tool, bridge, nested-trace, and
failure-path behavior.

The gate must fail when:

- a called or pinned tool no longer resolves;
- a required argument disappears;
- an unknown argument appears;
- a hosted or bridge authority silently disconnects; or
- nested subagent structure no longer validates.

It must remain green for unrelated registry additions and optional historical
fields.

## 4. Change Discipline

Any future schema field needs:

1. a concrete current producer or explicitly hand-authored fixture purpose;
2. load compatibility for existing traces;
3. a named validator behavior;
4. a mutation that proves the new owner can fail; and
5. no live provider request in the regression gate.

Git history is the source for the original three-commit implementation
sequence and the retired branches that are no longer current authority.
