# P1.4 Context Compression - Current Authority

> **Status:** SHIPPED. Current contract refreshed 2026-08-17 after the
> legacy-agent surface retirement. The original five-commit implementation
> narrative remains available in Git history.
>
> **Purpose:** preserve automatic, bounded context compression and durable
> overflow recovery as a reusable agent library.

## 1. Framing

Context compression is a steady-state operating layer. Large tool results are
reduced in prompt while recoverable raw payloads are stored on disk; long
histories can be summarized before a model call without changing evidence
ownership.

### 1.1 Scope

The current system includes deterministic reduction, optional provider-native
compaction, threshold-driven LLM summarization, anchor recovery, durable
overflow storage, and cross-pipeline observability.

It does not expose a user command or one-turn override. Layer 5 runs only from
configuration, message size, caller availability, and circuit state.

### 1.2 Guarantees

1. **Library, not runner.** src/agents/shared/compressor/ has no agent import
   and does not own provider loops.
2. **Raw data remains recoverable.** Layer 0 stores oversized raw tool payloads
   before replacing them in prompt.
3. **No fabricated reasoning.** Reasoning blocks are retained verbatim or
   represented as deliberately dropped; summaries may not invent them.
4. **Recent context stays concrete.** Boundary selection keeps recent turns
   verbatim and replaces only a safe prefix.
5. **Idempotent markers.** Repeated compaction replaces prior summary state
   instead of stacking duplicate summaries.
6. **Failure isolation.** A summary failure increments a bounded circuit
   breaker; a legitimate no-op does not.
7. **Configuration authority.** Master and per-layer settings determine whether
   the library participates. There is no hidden presentation-side activation.

## 2. Architecture

    provider loop
        |
        v
    ContextManager
        |
        v
    ContextCompressor
        +-- deterministic reducers and transcript projection
        +-- OverflowStore
        +-- optional provider-native adapter
        +-- optional SummaryCaller
        +-- anchor builder

The provider loop owns model calls and passes a stable message projection into
the library. The library returns transformed messages, fired-layer metadata,
and an optional safe prefix-replacement boundary.

## 3. Layer Contracts

### 3.1 Layer 0 - overflow storage

An oversized tool result is reduced through a named per-tool reducer or a
bounded generic representation. The raw payload is written beneath the
configured overflow root before the prompt receives the compact form.

The observability record contains the layer, raw/compressed byte counts,
raw/compressed digests, and overflow record ID. Replay, scratchpad, and history
receive the same metadata object.

#### 3.1.1 Record identity and integrity

OverflowStore derives a deterministic record ID from the session and payload
identity, writes atomically, and verifies the stored arguments hash, byte size,
and payload on read. A corrupt or mismatched record is rejected rather than
returned as trusted raw data.

### 3.2 Layers 1-3 - deterministic compression

- Layer 1 minifies old structured payloads.
- Layer 2 may reuse a supplied semantic scratchpad summary after its threshold.
- Layer 3 progressively replaces older tool results with bounded stubs.

These layers are cheap, deterministic, and self-gated by configuration and
thresholds.

### 3.3 Projection and native-message safety

Projection preserves the mapping back to provider-native messages. Tool-result
body patches preserve unaffected native block identity. Prefix replacement
backs up only when required to keep an assistant/tool-result group valid; it
does not consume unrelated user text.

### 3.4 Reasoning and prior-summary handling

Thinking content is labeled and retained verbatim. Redacted thinking remains a
redaction marker. Existing summary markers are detached and supplied as prior
summary input so repeated compaction can refine rather than duplicate them.

### 3.5 Layer 4 - provider-native compaction

Provider-native compaction is optional and provider-specific. The current
architecture does not pretend that Anthropic client-side and OpenAI SDK-side
mechanisms are identical.

### 3.6 Layers 5-6 - automatic full summary and anchor recovery

Layer 5 runs only when all of these are true:

- the compressor and Layer 5 are enabled;
- message size exceeds the configured threshold;
- a summary caller exists; and
- the circuit is closed.

A successful call replaces a safe old prefix with one capped summary. Three
consecutive caller failures open the default circuit; success resets it. A
short-history or boundary no-op neither invokes the caller unnecessarily nor
burns the circuit.

Layer 6 appends a bounded anchor after provider-native or Layer 5 compaction so
current tickers and recent overflow record IDs remain concrete.

## 4. Per-Tool Reducers

src/agents/shared/compressor/reducers.py owns deterministic reducers for
large-result tools. Each reducer must preserve identifiers and facts needed to
retrieve or interpret the raw record. Unknown tools use a bounded generic path;
they do not gain an unreviewed semantic reducer.

Reducer changes require realistic wrapped and unwrapped fixtures,
byte/character boundary coverage, idempotency coverage, and an overflow-read
integrity check.

## 5. Integration and Observability

ContextManager is the integration boundary. With client-side compaction
disabled it preserves the legacy manager path. With it enabled, each turn
delegates to ContextCompressor, then applies either body patches or a safe
prefix replacement.

Compression metadata is optional and forward-compatible in replay traces.
Consumers that do not understand it may ignore it; producers may not emit
different values to scratchpad, replay, and history for the same event.

## 6. Activation and Failure Semantics

AgentConfig.compaction_enabled defaults false.
compaction_layer_5_enabled also defaults false. When enabled, Layer 5 remains
threshold-driven and guarded by its circuit breaker.

Missing caller, insufficient history, disabled layers, or an open circuit are
honest no-op states. Exceptions from the summary provider are contained and do
not corrupt the caller's original messages.

## 7. Regression Owners

The current contract is owned by:

- tests/test_compressor_overflow_store.py;
- tests/test_compressor_reducers.py;
- tests/test_compressor_layers.py;
- tests/test_compressor_integration.py;
- tests/test_compressor_observability.py;
- tests/test_compressor_layer5.py; and
- tests/replay_fixtures/p1_4_l0_overflow.json.

Any future user-facing activation, model-policy change, or new agent-exposed
raw-payload reader requires a separate design and permission review.
