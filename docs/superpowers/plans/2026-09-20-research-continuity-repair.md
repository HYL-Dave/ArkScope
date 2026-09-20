# Research Continuity Repair

Status: accepted follow-up scope; **not implemented**. This plan carries the
remaining problems out of the archived `research-session-continuity` branch.
Archiving the branch does not close these issues or adopt its proposed schema.

## Decision And Boundaries

The user authorized archiving `research-source-workflow` and conditionally
archiving `research-session-continuity` after its real remaining problems become
part of the next correction plan. Research remains a workbench capability.
Durable conversations are not the abandoned research-notebook feature.

This work does not reintroduce the declined token-monitoring ledger/dashboard,
research notes, cache warming, cache-TTL controls, or a new usage UI. Existing
subscription usage display/sync, generic card translation, credential authority,
failure classification, and stored research/citation data remain intact.

Historical design authority for review, not an implementation mandate:

- Tag `archive/2026-09-20/research-session-continuity`, commit `650130cb`:
  `docs/superpowers/specs/2026-09-10-research-session-continuity-design.md`.
- Tag `archive/2026-09-20/research-source-workflow`, commit `5c123120`:
  `docs/data/2026-09-19-tool-capability-audit.md` and
  `docs/data/2026-09-19-research-history-audit.md`. Their observations remain
  inputs to the broader tool-repair queue, not evidence that the archived
  fundamentals implementation has been adopted.

## Current Evidence

Rechecked against master `f0024782`; no production database or model call was
used. Reproducer and results:
`docs/superpowers/evidence/2026-09-20-research-continuity-audit/`.

| ID | Current observation | Classification and owner |
| --- | --- | --- |
| RSC-01 | `_persist_assistant_turn` swallows a write exception; the run manager still calls `mark_terminal(..., "succeeded")`. A synthetic write failure leaves a successful run and a durable `done` event, but no assistant message in the next-turn history. | Confirmed correctness defect; `src/api/routes/query.py`, `src/research_run_manager.py`, `src/research_runs.py`, `src/research_threads.py`. Repair first. |
| RSC-02 | Interrupting after the assistant commit and before terminal status leaves a completed answer on a running run. Restart reconciliation adds an error reply and marks it interrupted. The answer survives, but the terminal presentation contradicts the retained completion. | Confirmed recovery/commit gap; same owners. Repair together with RSC-01. |
| RSC-03 | Claude OAuth creates a fresh `CLAUDE_CONFIG_DIR`, calls `query`, then removes that directory. `resume` and `session_store` are unset. Prior application text is folded into the next prompt. | Confirmed native-session continuity gap, **not loss of the application transcript**. Owner: `src/auth_drivers/claude_code_sdk_driver.py` and the server-owned run context. |
| RSC-04 | The history builder intentionally forwards non-error text only, excluding tool metadata and native signed frames. The freshness instruction is appended only when history exists. | Existing contract and a future compatibility constraint, not proof of a present history-loss bug. Preserve the text contract; make first/follow-up instructions compatible before enabling native reuse. |

Cancellation and restart error terminalization already have shared-transaction
helpers and tests. Do not replace those working protections with a second
unrelated state machine. Ordinary provider-error persistence also uses a
best-effort helper today; include its analogous failure window in RSC-01/02's
RED tests rather than claiming the synthetic success cases covered it.

## Slice 1: Durable Completion And Recovery

Before adding a native transcript store, make the existing application record
trustworthy. This slice does not need a new provider session or model request.

1. Add fault-injection owners to `tests/test_research_runs.py`: assistant-write
   failure, terminal-status failure, event-write failure, restart at each commit
   boundary, ordinary error persistence, and a concurrent next-turn admission.
   Keep a successful positive control for each family.
2. Give server-owned runs one shared-database completion operation for the
   linked assistant message, authoritative terminal event and terminal status.
   Preserve tool events, citation references, prompt trace and exact execution
   receipts. Use the existing run/thread transaction and ownership patterns.
3. Do not publish durable success or release per-thread exclusion before that
   operation commits. A local persistence failure must be visible; it must not
   become `succeeded` without a readable answer. Avoid silently changing the
   legacy page-owned query endpoint's lifecycle as collateral.
4. Define idempotent recovery for pre-existing partial completions using the
   exact owning run, linked message and admitted event evidence. A `done` row
   alone is not authority to invent a complete answer/receipt. Preserve any
   surviving answer; do not append a contradictory duplicate or resend a
   completed provider request. Audit existing production rows separately before
   any repair; this plan authorizes no production rewrite.
5. Test cancellation and repeated cancellation, thread deletion, late worker
   callbacks, cross-thread contention, and a next request arriving during
   commit. Local storage retry must not become model execution retry.

Acceptance: both reproduced defects have RED-to-GREEN owners; ordinary failure
and cancellation retain their truthful state; committed answers and citations
reopen after constructing fresh stores; provider dispatch count stays one.

## Slice 2: Isolated Native Session Continuity

Only after Slice 1, review the archived storage proposal against the installed
and admitted SDK/CLI. The old two-table `SessionStore` approach is a candidate,
not permission to add those tables or assume a September 10 API still fits.

1. Bind native state to profile, thread, provider/auth channel, credential
   identity, model/effort, runtime compatibility, instructions and ordered
   committed-history digest. Use the already captured `RuntimeAuthBinding`;
   never reread active Settings credentials midway through a request.
2. Compatible native reuse sends only the new question once. A first turn or
   incompatible/missing checkpoint reconstructs from committed application
   history before dispatch, without silently truncating it. A -> B -> A must
   include B's intervening turns, not reuse a stale A transcript.
3. Failed, cancelled, incomplete or unverified mirrors cannot publish reusable
   checkpoints. Store completion and native checkpoint publication have explicit
   ordering. Mirror failure must neither erase a saved answer nor trigger a
   hidden second request, different account, model or billing channel.
4. Keep native transcripts private and separate from public history. Do not
   retain configuration directories, credentials or raw environment; do not
   rewrite signed native frames and call them resumable. Retain all current
   bundled-runtime, closed-environment, auth-source, output-boundary and tool
   permission checks on resumed calls.
5. Explicitly invalidate or delete owned native state when its thread or
   credential is deleted, and reject late appends. Test restart and profile
   relocation. Relocation may reconstruct; do not promise cross-platform native
   resume from a Linux test.

Named owners required before implementation: same-thread follow-up, profile/
thread/credential isolation, A -> B -> A, instruction/model/tool changes,
mirror failure, cancellation, late callback/deletion, and restart/relocation.
Existing stateless card, translation, investigation and legacy query tests must
continue to require their current request lifetimes; do not weaken them globally.

## Slice 3: Honest Run Details And Acceptance

- If native continuity is added, show a bounded per-run state such as new,
  resumed, reconstructed or unavailable in existing Research details. A setting
  passed to the SDK is not evidence of a successful resume, and a resume is not
  proof of a prompt-cache hit. Do not expose native IDs or raw transcript paths.
- Test existing text-history behavior on all four auth channels, including
  provider changes and restored conversations. Native continuation is initially
  Claude OAuth only; it is not permission to splice signed provider frames into
  another channel.
- Retain the existing SEC citation, route-authority, credential isolation,
  cancellation and output-boundary owners. Run each complete backend acceptance
  on one frozen revision with only one pytest process per tree, plus frontend,
  typecheck/build and browser checks if presentation changes.
- A real SDK follow-up/restart check needs separately bounded authorization and
  installed-runtime verification. No paid call, production migration, App
  restart or settings change is authorized by this documentation commit.

Existing OpenAI compaction compatibility and historical usage-counter findings
stay separately owned in `PROJECT_PRIORITY_MAP.md`; neither is certified fixed
by session continuity or bundled into a new token-monitoring project. The
earnings-event repair/scheduling plan also remains a separate capability.

## Starting Commands

Read the archived original without recreating or merging the branch:

```bash
git show archive/2026-09-20/research-session-continuity:docs/superpowers/specs/2026-09-10-research-session-continuity-design.md
python docs/superpowers/evidence/2026-09-20-research-continuity-audit/observe.py
python -m pytest tests/test_research_runs.py tests/test_research_threads.py tests/test_claude_code_sdk_driver.py tests/test_task_runtime_binding.py -q
```

The observer reports current faults; exit 0 means its working control and
isolation checks held, **not that these defects are fixed**. Convert its cases
into behavior-correct acceptance tests when Slice 1 opens. The existing baseline
suite passed 258 tests during this archive handoff.
