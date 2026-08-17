# Phase C Unified Runner - Paused Architecture Contract

> **Status:** PAUSED. Re-grounded 2026-08-17 after the legacy-agent surface
> retirement. This document preserves current constraints; it is not an
> implementation authorization.
>
> **Prerequisites:** the current replay contract in
> P0_1_FULL_V1_SPEC.md and context-compression contract in P1_4_SPEC.md.

## 1. Objective

Phase C may eventually remove duplicated provider-loop orchestration while
preserving observable behavior across the current Research, query, Card,
subagent, tool, replay, and compaction contracts.

The target is an internal runner library selected through one factory. It is
not a new product entrypoint and must not restore a retired presentation
surface.

## 2. Current Inputs

The re-grounded implementation surface is:

- HTTP Research and query routes;
- Anthropic and OpenAI programmatic agent functions;
- subagent dispatch;
- ToolRegistry, hosted-tool, and bridge authorities;
- replay capture and fixture validation;
- token tracking and usage projection; and
- provider-specific compaction behavior.

Document payload handling is not a current runner input. A future Document
Intelligence design must establish that contract before any runner accepts it.

## 3. Target Shape

    Research / query / subagent caller
                   |
                   v
    build_runner(provider, config, dal, ...)
                   |
           +-------+-------+
           |               |
           v               v
    AnthropicRunner   OpenAIRunner
           |               |
           +-------+-------+
                   |
                   v
    AgentEvent / TurnResult

build_runner(...) is the business-call-site entrypoint. Concrete runner
classes may remain exported for tests and advanced direct construction, but
provider selection belongs in the factory.

The public methods are provider-symmetric:

    async def run_stream(question: str):
        ...

    async def run(question: str):
        ...

Provider-specific settings remain in configuration or the concrete runner.
The shared result/event contract may not leak raw SDK response classes.

## 4. Behavior That Must Remain Provider-Specific

Unification does not mean pretending the providers have identical mechanics.

- Anthropic currently uses client-side ContextManager / ContextCompressor
  integration for Layers 0-6.
- OpenAI retains its SDK-owned server compaction path where configured.
- hosted web tools use provider-native definitions behind one shared kind
  authority;
- tool-call extraction follows each SDK's response structure; and
- retry, refusal, reasoning, and usage details retain explicit provider
  adapters.

The shared runner owns orchestration order and event projection, not false
mechanical symmetry.

## 5. Preserved Contracts

Any implementation plan must prove all of these before cutover:

1. run_query, streaming query, Research, and subagent behavior retain their
   current typed outcomes.
2. Current tool names and argument contracts resolve through the registry,
   hosted-tool, and bridge authorities.
3. Replay fixtures remain clean, including nested subagent and compression
   owners.
4. Automatic compaction, safe prefix replacement, circuit breaker, overflow
   storage, and observability remain live.
5. Token usage and refusal/error projection preserve current semantics.
6. Provider-native hosted tools remain available only when enabled.
7. No new user-facing command, route, setting, or compatibility shim appears
   as a side effect of the refactor.

## 6. Rollout Contract

The previous cutover sketch is not executable after the 2026-08-17 surface
change. Before code opens, a new RED-first plan must:

1. recollect current call sites and node identities;
2. enumerate a provider-by-provider behavior matrix from current code;
3. define one read-once rollout decision for each server-owned run;
4. run old/new paths against the same fixture and tool authorities;
5. prove event, result, usage, and failure parity;
6. delete old loops only after all current callers use the factory; and
7. remove the rollout branch once the new path is the sole owner.

No compatibility wrapper may survive solely to preserve a deleted caller.

## 7. Replay and Test Gates

At minimum, the implementation plan must run:

- all current replay fixtures;
- registry, hosted-tool, and bridge mutation owners;
- Anthropic and OpenAI query tests;
- Research and subagent route tests;
- context-manager and compressor suites;
- refusal, usage, and model-routing owners; and
- socket-guarded canonical native and frontend regression gates.

The replay gate checks structural behavior. It does not replace provider-loop
tests for retries, streaming, cancellation, or SDK-specific error handling.

## 8. Resume Gate

Phase C stays paused until all three existing product gates are true:

1. local-first workbench v1 is shipped;
2. at least two weeks of stable single-user storage, scheduler, and sync use
   have been observed; and
3. at least one verified cross-machine migration has completed.

After those gates, re-grounding and independent plan review are still required.
This document alone does not open implementation.

## 9. Explicit Non-Goals

- changing provider SDKs;
- updating model inventories;
- designing Document Intelligence;
- changing Track B skill policy;
- changing alert transport;
- inventing a new user-facing runner surface;
- unifying provider compaction mechanisms; or
- changing storage/profile architecture.

Git history contains the original commit-by-commit Phase C proposal and is the
reference for historical alternatives, not current implementation authority.
