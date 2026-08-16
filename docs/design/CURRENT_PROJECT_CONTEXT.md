# Current Project Context

> This is a pointer index for assistants and developers starting work in ArkScope.
> It is not an instruction file and does not duplicate active plans.

## Canonical Sources

Read these in order:

1. `docs/design/PROJECT_PRIORITY_MAP.md`
   - Section 1 summarizes the current direction.
   - Section 10 is the newest-first decision log and owns current sequencing.
2. `docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`
   - Product shape, deployment, storage, sync, page structure, and capability
     boundaries.
3. `docs/design/CONFIG_AUTHORITY_PLAN.md`
   - Settings authority, credential ownership, and configuration retirement gates.
4. `docs/design/PHASE_C_UNIFIED_RUNNER_SPEC.md`
   - Deferred runner work; it is not current implementation authority.
5. `docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md`
   - Current data collection and browser-extension paths that must survive
     refactors.

If these disagree, the newest applicable entry in the priority map wins. The
design index at `docs/design/README.md` supplies document titles and maturity.

## Project Identity

The repository and product are named ArkScope. Lowercase `mindfulrl` remains only
where existing browser extension identifiers require it. Do not introduce another
project name without an explicit product decision.

## Current Architecture

ArkScope is a local-first financial research workbench:

- Electron desktop shell and local FastAPI sidecar;
- React research and Settings surfaces;
- explicit SQLite owners under `data/`;
- scheduled and attended collection through shared service functions;
- browser-extension capture through the native host;
- provider credentials and lifecycle state owned by local Settings storage.

Do not infer the next implementation task from a dated phase list in another
document. Read the priority map and the active design or plan named there.

## Tool Memory

Tool-side memories, IDE caches, and private notes are navigation aids only. When a
cache disagrees with the canonical documents, update the cache rather than changing
product authority to match it.

Operational commands belong in tool configuration; implementation details belong
in source and active plans. Keep this file short and limited to durable pointers.
