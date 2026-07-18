# P2.8 Slice 3 Research Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to execute this plan task by task. Use
> `superpowers:test-driven-development` for every behavior change and
> `superpowers:verification-before-completion` before any review-ready claim.
> Steps use checkbox syntax; completed steps become `- [x]` and the ledger
> records the exact RED and GREEN evidence.

> **Status:** IMPLEMENTATION IN PROGRESS — TASKS 1–6 COMPLETE / TASK 7 IN PROGRESS 2026-07-18

### Plan Review Clearance (2026-07-18)

Independent review reproduced all three baselines and exact accounting. Its one
must-fix found that max-tool exhaustion has four provider/auth shapes rather
than one. This revision closes that gap without changing node counts:

- Anthropic API-key: exact successful-frame answer
  `Maximum tool calls reached. Please try a simpler query.`;
- OpenAI API-key: anchored `MaxTurnsExceeded:` error prefix emitted by the
  in-repo agent wrapper;
- ChatGPT OAuth: anchored full driver message
  `Reached maximum number of turns (N)`;
- Claude SDK subscription: typed `ResultMessage.subtype == "error_max_turns"`
  is normalized by the driver to explicit `code=tool_limit_reached`.

The installed Claude Agent SDK documents `error_max_turns` as a structured
result subtype. Strengthen its existing error-result test in place; do not add a
node. Any different future SDK shape remains `provider_call_failed` and is a
stop-and-review condition, not grounds for fuzzy text inference. The shared
classifier test remains one node and loops over the three central shapes plus
near misses, including per-tool timeout text. Task 4 implementation review
later added one auth/retry regression node, so current authoritative accounting
is backend `+34/-0` and frontend `+53/-15`.

## Implementation Ledger

### Task 0 — COMPLETE (2026-07-18)

- Isolated worktree: `/tmp/arkscope-p2-8-slice-3`, branch
  `codex/p2-8-slice-3-research-workspace`, branch point and merge-base
  `5be79a658be91168dc7d10b5108344fadf4c9a7a`.
- Canonical behavior base remains `c78203a`; the later docs-only review tip is
  recorded separately and does not move A/B authority.
- Linked-worktree git-crypt key installed through the repository's established
  metadata-key pattern; checkout is clean.
- Protected-file proof: worktree `config/tickers_core.json` has no diff; the
  main worktree's user-owned `BTSG` addition remains present and untouched.
- Fresh baselines: backend `4378` collected; Research-focused `93`; frontend
  `56 files / 533 tests`; TypeScript typecheck passed.
- Structural RED inventory confirmed the permanent `research-grid`, history and
  trace asides, `window.confirm`, the second model-discovery/fallback policy,
  and current generic thread-error rendering.

### Task 1 — COMPLETE (2026-07-18)

- RED first: the absent `src.research_history` module failed collection; the
  quality hardening then reproduced three contract failures (snapshot, bounds,
  timezone offsets) plus one fractional-endpoint failure before each fix.
- Product commits: `b87d9d4` (bounded projection), `fff7d7e` (snapshot, UTC,
  and page bounds), and `bd2e306` (fractional timestamp precision).
- Exact accounting remains ten collected nodes; final focused result is
  `10 passed`. Adjacent thread/run stores remain `34 passed`.
- The projection filters before count/pagination, uses one explicit read
  transaction for count plus page consistency, creates no schema, and opens
  SQLite in read-only/query-only mode. Dependency bootstrap remains the
  reviewed owner of authoritative thread/run schema initialization.
- Independent spec review and final code-quality review both returned PASS.
  The reviewed suggestion to add an index or redesign the latest-run CTE was
  not adopted because no measured regression justified speculative storage
  or query-plan changes.

### Task 2 — COMPLETE (2026-07-18)

- RED-first lifecycle/API work landed in `3f713d6`; follow-up transaction
  reviews produced three real SQLite failures before their fixes: active-run
  archive/delete races, partial multi-field PATCH, and split history/active-run
  snapshots. Commits `464de35`, `0fdbda1`, and `41b0e2f` serialize those writes,
  make new thread/run/user-message creation atomic, snapshot prior history in
  the same writer transaction, and terminalize a failed scheduler handoff
  without leaving an active orphan.
- Exact collection accounting remains `27` thread-store nodes, `44` route
  nodes, and `10` history nodes. Final focused verification is `94 passed`;
  adjacent store coverage is `13 passed`. The known bare-environment
  `eventkit` setup family remains `20 passed, 1 error` when that file is added.
- Independent spec review returned PASS. Quality review confirmed fixed lock
  order (`run -> thread`), cross-instance `BEGIN IMMEDIATE` serialization,
  rollback on message failure, same-snapshot history, and post-commit schedule
  failure recovery.
- The same review exposed one cross-task terminal seam: cancellation and
  startup reconciliation still write terminal status before their assistant
  error turn. This is not waived. Task 3's already-accounted tests 9 and 10
  must be true SQLite interleaving tests, and Task 3 must commit status, event,
  and linked typed message atomically before its review can pass.

### Task 3 — COMPLETE (2026-07-18)

- Product commit `0b11074` added the strict Research error-code authority,
  nullable run/message linkage, deterministic latest-successful selection,
  semantic `default` persistence with one provider-wire normalization seam,
  typed DTOs, and the reviewed Claude SDK `error_max_turns` mapping.
- The two carried cancellation/restart nodes use independent stores and pause
  inside the uncommitted terminal transaction. They prove status, replay event,
  and linked error turn commit before a new run can append its user message;
  the established `run -> thread` lock order remains unchanged.
- Review commits `08ed4e2` and `9fcc7d5` removed a duplicate SDK effort owner
  and pinned every reviewed timeout/max-turn positive and near-miss boundary,
  including provider `APITimeoutError` module gating and an Anthropic `done`
  near miss that must remain successful.
- Exact accounting is `23` run-store nodes (`+10`), `46` route nodes (`+2`),
  and the Claude driver node strengthened in place. Independent focused replay
  is `70 passed`; the isolated event file is `20 passed` with its one known
  bare-environment `eventkit` setup node excluded rather than modified.
- Independent spec and quality reviewers returned final PASS. `EventType`
  remains byte-identical, public error detail is redacted/bounded, new
  selection/message contracts expose no credential identity, and all four
  API-key/OAuth branches receive `None` rather than literal `default`.

### Task 4 — COMPLETE (2026-07-18)

- RED-first product commit `3c1cca9` extracted the shipped Settings option
  policy into `modelPicker.ts`, replaced Research's permissive discovery and
  first-option fallbacks with one pure tuple resolver, and removed exactly the
  reviewed `11 + 4` obsolete policy nodes. The new authorities contributed
  exactly `8 + 12` nodes; Settings rendering stayed on the same shared reason
  and grouping functions.
- Independent review found two coupled desktop failures. The thread-selection
  request bypassed `api.ts`, so Electron's token guard returned 401; a failed
  request then left Send disabled with neither visible state nor retry. Commit
  `a4bdcf7` first proved both failures RED, moved the request through the shared
  authenticated/timeout client, and added a visible fail-closed retry without
  fallback.
- The retry contract adds one reviewed node, reconciling Task 4 to a net `+6`
  and the full frontend checkpoint to `57 files / 542 tests`. Typecheck and
  production build pass; the only build output is the pre-existing chunk-size
  warning. Independent re-review returned PASS.
- A review suggestion to use the global explicit tuple for an existing thread
  with no successful run was rejected: canonical spec §8.3 deliberately makes
  existing-thread continuity and new-thread explicit preference asymmetric.
  Such a thread therefore reaches the Settings route only when it has no
  successful thread-owned tuple; it never silently substitutes a tuple that
  belongs to another thread.

### Task 5 — COMPLETE IN PARALLEL (2026-07-18)

- RED-first commit `8e1f1fc` added exactly three Drawer contract nodes and the
  wide inline-pinned variant without a second breakpoint or new media query.
- Accessibility review then reproduced two stacked-overlay focus failures:
  breakpoint transitions could steal focus from a topmost ConfirmDialog, and
  closing that dialog after the Drawer moved inline could leave focus on the
  document body. Commits `f9f03eb` and `ccae139` keep one stable overlay-stack
  entry across modal/inline modes and restore to the present inline pin without
  granting it modal Escape or focus-trap ownership.
- Exact accounting is `13` overlay nodes (`+3`). Independent focused replay is
  `13 passed`; the complete frontend at this checkpoint is `56 files / 536
  tests`, with typecheck and build passing. Spec review and the original
  accessibility reviewer both returned final PASS.

### Task 6 — COMPLETE (2026-07-18)

- RED-first foundation commits `1bcb5c0` and `2101c63` separated bounded
  history metadata from visited transcript state, added the typed history
  clients and focus-managed Drawer, and contributed exactly ten history UI
  nodes. Product commit `789b734` removed the permanent history column,
  hydrated only the selected transcript, acknowledged shell targets once, and
  kept archived transcripts visible but inert.
- Existing shell/reducer/App nodes were strengthened in place, so review
  hardening added no collection. The RED evidence covered current-selection
  hydration before replay, stale-session `404` versus transient `500`, stale
  active-run cleanup after mutation, filtered rename/archive/delete races,
  duplicate rename submission, and Cancel/Escape/overlay focus restoration.
- Exact checkpoint is `58 files / 552 tests`; the four affected suites are
  `94 passed`. Typecheck and production build pass with only the existing
  chunk-size warning. Static checks show no production `research-threads`,
  `threadMenuId`, `window.confirm`, temporary diagnostics, or eager
  `getResearchThreads` owner.
- Two independent reviewers re-ran after every correction and returned final
  PASS: exact-thread `500` preserves the saved target while `404` alone may
  fall back; revisited replay waits for the current transcript request; all
  history mutations reload the latest server-side filters and reject stale
  responses.

**Goal:** Replace the fixed three-column AI Research page with the approved
conversation-first workspace: on-demand deterministic history, an honest
pinnable Evidence/Run-details surface, complete per-run model selection from
the Models-UX authority, bounded progress, local drafting plus explicit Stop,
and typed actionable failures.

**Architecture:** Keep `research_threads`/`research_messages` as transcript
authority and `research_runs`/`research_run_events` as execution authority. Add
one bounded SQL history projection over those existing tables, additive thread
lifecycle routes, and an exact latest-successful-tuple query. Link new durable
assistant messages to their owning run and persist a machine-readable Research
error code; legacy rows remain readable through nullable tolerant migrations.
On the frontend, extract the shipped Models-UX option policy from Settings into
one shared module, replace the page's competing selection effects with one pure
precedence resolver, lazily hydrate only the selected conversation, and compose
the existing PageHeader, Drawer, ConfirmDialog, Status, and BoundedProgress
primitives. Drawer gains only the wide inline-pinned variant first consumed by
Research. No second transcript, catalog, evidence store, or job authority is
created.

**Tech Stack:** Python 3.11, SQLite/WAL, FastAPI/Pydantic, pytest, React 18.3,
TypeScript 5.5, Vite/Vitest/jsdom, `lucide-react`, and the shipped P2.8 shell and
UI primitives.

## Authority, Base, and Exact Accounting

- Product authority:
  `docs/superpowers/specs/2026-07-12-p2-8-canonical-shell-interaction-design.md`,
  especially Sections 7.3, 8, 11, 12, 13 Slice 3, and 14.
- Models authority:
  `docs/superpowers/specs/2026-07-11-model-routing-settings-ux-design.md` and
  `src/model_effective.py`. Research consumes the same effective task/provider
  projection as Settings; it does not infer model eligibility from SDK
  presence, credential key flags, raw discovery lists, or historical messages.
  The existing `/query/providers` package-health check may remain as an
  additional fail-closed runtime veto, but it may neither add a model nor
  override an effective-view veto.
- Behavioral base: `c78203a` (`docs: close news content availability unit`),
  current `master` when this plan opened on 2026-07-18. Docs-only review commits
  may advance the implementation branch point; record that separately in the
  ledger without changing the product A/B base.
- The user's unrelated `config/tickers_core.json` modification is protected.
  Never copy, stage, revert, rewrite, export over, or include it in a commit.
- Grounded backend baseline:

  ```text
  pytest --collect-only -q
  4378 tests collected

  pytest --collect-only -q \
    tests/test_research_threads.py \
    tests/test_research_runs.py \
    tests/test_research_routes.py \
    tests/test_events.py
  93 tests collected
  ```

  The most recent canonical family is `4267 passed / 30 failed / 74 skipped /
  7 errors`, with `18 warnings`; non-passing identities are pre-existing and
  must be A/B-identical.
- Grounded frontend baseline:

  ```text
  Test Files  56 passed (56)
  Tests       533 passed (533)
  ```

- Reviewed backend target is exactly `+34/-0`:
  - new `tests/test_research_history.py`: `10` nodes;
  - `tests/test_research_threads.py`: `+6` nodes;
  - `tests/test_research_runs.py`: `+10` nodes;
  - `tests/test_research_routes.py`: `+8` nodes.
  Focused collection becomes `127`; canonical collection becomes `4412`; if
  the existing family is identical, passed becomes `4301`.
- Current frontend raw collection delta is exactly `+53/-15`, a net `+38`:
  - new `modelPicker.test.ts`: `8` nodes;
  - new `researchSelection.test.ts`: `12` nodes;
  - new `ResearchHistoryDrawer.test.tsx`: `10` nodes;
  - new `ResearchWorkspace.test.tsx`: `12` nodes;
  - new `researchErrors.test.tsx`: `7` nodes;
  - existing `ui/overlays.test.tsx`: `+3` nodes;
  - existing `ResearchShellNavigation.test.tsx`: `+1` review-hardening node
    proving authenticated selection recovery and visible fail-closed retry;
  - remove exactly `11` obsolete `modelOptions` / `defaultModel` /
    `lastAssistantSelection` nodes from `researchModels.test.ts` and exactly
    `4` obsolete `chooseResearchProvider` nodes from
    `researchProvider.test.ts`.
  The removed nodes assert the policy this slice deliberately retires: a second
  discovered-model list plus silent route/first-option fallback. Their intents
  map one-for-one into the new shared picker and precedence tests. Final
  frontend accounting is `60 files / 571 tests`.
- Existing tests may be strengthened in place, but any backend delta other than
  `+34/-0`, any frontend raw delta other than `+53/-15`, or any unexplained
  file-count change is a stop condition requiring ledger reconciliation before
  continuing.

## Grounded Constraints

1. **Conversation remains the only permanent primary region.** History is a
   transient Drawer. Evidence is on demand and may pin inline only on the wide
   side of the existing 960px shell token. Closed or empty Evidence reserves
   zero width.
2. **No invented evidence contract.** Persisted Research currently has final
   Markdown, tool names/inputs, result previews, token usage, elapsed time, and
   personalization trace. It does not have a structured claim-to-citation
   model or full tool-result store. Evidence V1 presents those real records and
   an honest empty state; it does not regex-extract citations, fabricate `E1`
   identities, or persist full tool payloads.
3. **No second model authority.** Remove Research's use of
   `discoverModels()`, `modelOptions()`, `defaultModel()`,
   `lastAssistantSelection()`, and `chooseResearchProvider()`. The effective
   `ai_research.providers` blocks, active credential contexts, and shared
   Models-UX reason policy are the only selectable-model authority. Existing
   SDK package health may only disable an otherwise effective provider with an
   explicit runtime-unavailable reason.
4. **Complete semantic tuple, provider-safe wire.** Every new run stores
   `(provider, model, effort)`, with provider default represented as the
   semantic string `default`. The single provider-dispatch seam converts
   `default` to `None` before either provider/auth driver sees it. Existing
   nullable rows read back as `default`; no literal `default` may reach an SDK.
5. **No silent fallback.** Existing thread last-successful tuple, global last
   explicit tuple, and Settings route are evaluated in that order. If the
   highest-priority existing candidate is no longer executable, the UI becomes
   blocked and requires a new explicit choice; it does not fall through to a
   lower-priority candidate or silently change effort.
6. **The precedence asymmetry is intentional.** Existing thread continuity is
   based on last successful execution. A new thread uses the most recent
   explicit user selection, stored locally in a versioned tuple containing no
   credential ID. Auto-selected thread/Settings defaults never overwrite that
   preference.
7. **Selection is one state machine.** The current configured-route reset and
   provider-auto-selection effects can overwrite each other in one React
   batch. Replace them with one pure resolver plus one owner state transition;
   do not patch effect ordering.
8. **History filters are server-side and pre-limit.** Search, ticker, updated
   date, latest-run state, and archive mode apply in SQL before count,
   deterministic ordering, offset, and limit. No Python post-filter or eager
   message hydration is allowed.
9. **Archive and delete are different.** Archive preserves transcript, runs,
   and future references and hides the thread from the normal list. Permanent
   delete uses ConfirmDialog. Both archive and delete fail with `409` while a
   run is active; the backend guard is authoritative, not UI-only.
10. **Typed reason first, raw detail second.** Normal mode renders a reviewed
    reason and next action from `error_code`. A sanitized bounded raw detail is
    available only inside Developer Mode disclosure. Tokens, credential IDs,
    and unredacted exceptions are never rendered.
11. **Server ownership remains unchanged.** Switching thread, closing a Drawer,
    or leaving Research detaches polling without cancelling. Only explicit Stop
    cancels. While active, the composer remains editable, Send remains visible
    but disabled, and no second request is queued.
12. **Bound semantics remain factual.** Queue time has no invented provider
    bound. Once `started_at` exists, the stage bound is the configured Research
    session timeout. Crossing it shows `已達上界，等待伺服器確認`; it is not a
    progress percentage and does not imply cancellation.
13. **Global work Drawer remains the shell authority.** Slice 3 enriches the
    owning Research page only. It does not create another background registry,
    copy answers/errors into shell storage, or add fixed card tasks.
14. **No collections in this slice.** Manual collections, user-defined
    classification, recurring templates, LLM grouping, Reference storage, and
    saved-report IA remain separate designs.
15. **Existing shell navigation is reused.** Typed error actions navigate via
    `NavigationTarget` to the existing `providers` or `models` Settings
    sections; copy can name the adjacent Research runtime panel. Research does
    not invent a pre-Slice-4 anchor or directly mutate credentials/task routes.
16. **Current transcript authority is preserved.** New assistant messages gain
    nullable `run_id` and `error_code` linkage. Old messages remain readable;
    legacy `/query/stream` may continue writing null linkage without being
    advertised as exact run detail.
17. **Archived current threads are visible but inert.** Archiving the selected
    thread keeps its transcript on screen with an archived badge, but blocks
    Send until the user explicitly unarchives or starts a new thread. Deleting
    the selected thread moves the workspace to a blank new-thread state.
18. **Retry does not resurrect a failed tuple.** `retry_last_failed` controls
    prompt-history exclusion only. The retry request uses the currently
    validated complete tuple; an invalid historical failed tuple cannot bypass
    the picker or force a fallback.

## Domain State Mapping

| Research fact | Common UI state | Visible meaning |
| --- | --- | --- |
| no threads / no evidence records | `empty` | honest empty surface, no reserved rail |
| selection and transcript ready | `ready` | Send may be enabled when draft is nonblank |
| queued / running run | `running` | queue or model/tool stage with elapsed time |
| history refresh failed with prior rows | `stale` | retain prior rows and offer retry |
| latest result and one ancillary detail leg disagree/fail | `partial` | preserve answer; identify missing detail |
| invalid saved tuple / missing executable credential | `blocked` | require explicit selection or Settings action |
| typed provider/runtime failure | `failed` | reason plus next action, no raw-primary copy |
| cancelled / sidecar restart | `interrupted` | explicit Stop or service interruption |

`max_tool_calls` exhaustion is not a successful answer. At the durable run
boundary it becomes `failed` with `error_code=tool_limit_reached`; any supplied
token usage and the accumulated partial tool trace remain available.
Recognition is restricted to the four reviewed shapes in Plan Review
Clearance: three exact/anchored central classifier inputs plus Claude SDK's
typed `error_max_turns` subtype normalized to an explicit code at the driver
boundary. Per-tool timeout text and near matches remain ordinary tool/provider
facts. The low-level agent event enum is unchanged.

## File Map

**Backend product owners**

- Create: `src/research_history.py`
- Create: `src/research_errors.py`
- Modify: `src/research_threads.py`
- Modify: `src/research_runs.py`
- Modify: `src/research_run_manager.py`
- Modify: `src/auth_drivers/claude_code_sdk_driver.py`
- Modify: `src/api/routes/query.py`
- Modify: `src/api/routes/research.py`
- Modify: `src/api/dependencies.py`

**Backend tests**

- Create: `tests/test_research_history.py`
- Modify: `tests/test_research_threads.py`
- Modify: `tests/test_research_runs.py`
- Modify: `tests/test_research_routes.py` (`6` lifecycle/history nodes in Task
  2 plus `2` selection/error nodes in Task 3)
- Modify in place: `tests/test_claude_code_sdk_driver.py` (strengthen one
  existing error-result node; no collection delta)

**Frontend product owners**

- Create: `apps/arkscope-web/src/modelPicker.ts`
- Create: `apps/arkscope-web/src/researchSelection.ts`
- Create: `apps/arkscope-web/src/researchErrors.ts`
- Create: `apps/arkscope-web/src/ResearchHistoryDrawer.tsx`
- Create: `apps/arkscope-web/src/ResearchEvidenceDrawer.tsx`
- Create: `apps/arkscope-web/src/ResearchRunProgress.tsx`
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/App.tsx`
- Modify: `apps/arkscope-web/src/Research.tsx`
- Modify: `apps/arkscope-web/src/researchReducer.ts`
- Modify: `apps/arkscope-web/src/researchModels.ts`
- Modify: `apps/arkscope-web/src/researchModels.test.ts`
- Modify: `apps/arkscope-web/src/researchProvider.ts`
- Delete: `apps/arkscope-web/src/researchProvider.test.ts`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Modify: `apps/arkscope-web/src/ui/Drawer.tsx`
- Modify: `apps/arkscope-web/src/ui/primitives.css`
- Modify: `apps/arkscope-web/src/styles.css`

**Frontend tests**

- Create: `apps/arkscope-web/src/modelPicker.test.ts`
- Create: `apps/arkscope-web/src/researchSelection.test.ts`
- Create: `apps/arkscope-web/src/ResearchHistoryDrawer.test.tsx`
- Create: `apps/arkscope-web/src/ResearchWorkspace.test.tsx`
- Create: `apps/arkscope-web/src/researchErrors.test.tsx`
- Modify: `apps/arkscope-web/src/ui/overlays.test.tsx`
- Modify only as required by additive props/shapes:
  `ResearchShellNavigation.test.tsx`, `ResearchPendingBubble.test.ts`,
  `researchReducer.test.ts`, `ModelRoutingSection.test.ts`, and
  `AppShell.test.tsx`. Their existing product intents and node IDs remain.

**Docs / governance**

- Modify: this plan ledger/status
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify after merge only: external Claude Design companion and memory index

## Task 0: Isolate the Branch and Re-prove the Baselines

**Files:** no product edits.

- [x] **Step 1: Create a clean linked worktree after plan review**

Use `superpowers:using-git-worktrees`. Suggested branch and path:

```bash
git worktree add /tmp/arkscope-p2-8-slice-3 \
  -b codex/p2-8-slice-3-research-workspace <review-cleared-tip>
```

Do not copy the dirty `config/tickers_core.json`. If encrypted tracked files
need the repository's existing linked-worktree key setup, use that established
mechanism and prove the worktree is clean before editing.

- [x] **Step 2: Record base, branch, environment, and protected-file proof**

```bash
git status --short --branch
git rev-parse HEAD
git merge-base master HEAD
git diff -- config/tickers_core.json
```

The implementation worktree must have no `tickers_core.json` change. The main
worktree user's diff remains untouched.

- [x] **Step 3: Re-run exact baseline collection**

```bash
pytest --collect-only -q
pytest --collect-only -q \
  tests/test_research_threads.py \
  tests/test_research_runs.py \
  tests/test_research_routes.py \
  tests/test_events.py

npm test --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
```

Stop if the counts differ from `4378`, `93`, and `56/533` before any RED test.

- [x] **Step 4: Record current structural RED facts**

The ledger records, without editing code:

```bash
rg -n "window\.confirm|research-grid|research-threads|research-trace" \
  apps/arkscope-web/src/Research.tsx apps/arkscope-web/src/styles.css
rg -n "chooseResearchProvider|discoverModels|modelOptions|defaultModel|lastAssistantSelection" \
  apps/arkscope-web/src/Research.tsx apps/arkscope-web/src/researchModels.ts
rg -n "credential_id|threadError|\.error\}" apps/arkscope-web/src/Research.tsx
```

These are diagnostic baselines, not commands to mass-rewrite files.

## Task 1: Build the Bounded Research History Projection

**Files:** create `src/research_history.py`, create
`tests/test_research_history.py`, modify `src/api/dependencies.py`.

- [x] **Step 1: Write exactly ten RED history-query nodes**

Use the real `ResearchThreadStore` and `ResearchRunStore` schemas in one temp
SQLite file. Do not hand-create reduced tables.

1. `test_query_searches_stored_title_and_ticker_before_limit`
2. `test_query_filters_exact_ticker_before_limit`
3. `test_query_filters_updated_window_before_limit`
4. `test_query_filters_latest_run_state[active]`
5. `test_query_filters_latest_run_state[succeeded]`
6. `test_query_filters_latest_run_state[failed]`
7. `test_query_filters_latest_run_state[interrupted]`
8. `test_query_filters_latest_run_state[no_run]`
9. `test_query_archive_mode[current]`
10. `test_query_archive_mode[archived]`

Every fixture includes a counterexample newer than the matching row so a
post-limit Python filter fails for the right reason. Assert deterministic
`updated_at DESC, id DESC`, exact total, and the bounded page.

- [x] **Step 2: Run RED**

```bash
pytest -q tests/test_research_history.py
```

Expected RED: import failure for `src.research_history`.

- [x] **Step 3: Implement one read-only projection**

Create immutable query/result dataclasses and `ResearchHistoryStore`. Its query
accepts:

```python
query_threads(
    *, q=None, ticker=None, updated_from=None, updated_before=None,
    run_state="all", archive_mode="current", limit=50, offset=0,
) -> ResearchHistoryPage
```

Requirements:

- one `ROW_NUMBER() OVER (PARTITION BY thread_id ORDER BY created_at DESC,
  id DESC)` latest-run CTE;
- one filtered count and one bounded item query;
- search only stored `title`/`ticker`, with escaped LIKE input;
- exact ticker comparison after uppercase normalization;
- `interrupted` means latest `cancelled` or `interrupted`;
- `active` means latest `queued` or `running`;
- `no_run` means no joined run;
- archive mode is exactly `current | archived`; V1 deliberately has no mixed
  all-state page;
- no writes, schema creation, message loads, or provider calls.

Add `get_research_history_store()` using the same `_local_state_db_path`
dependency pattern. The dependency first initializes the existing thread/run
stores so both authoritative tables exist, then opens the read projection; the
projection itself creates no schema and must not become a second DB path
authority.

- [x] **Step 4: Run GREEN and query-plan sanity**

```bash
pytest -q tests/test_research_history.py
```

Use `EXPLAIN QUERY PLAN` on a seeded temp DB to confirm indexed primary-key/run
lookups and bounded final reads. Do not invent a millisecond threshold or add
an index without evidence.

- [x] **Step 5: Commit**

```bash
git add src/research_history.py src/api/dependencies.py tests/test_research_history.py
git commit -m "feat: add bounded research history projection"
```

## Task 2: Add Thread Lifecycle and History APIs

**Files:** modify `src/research_threads.py`, `src/api/routes/research.py`,
`tests/test_research_threads.py`, and `tests/test_research_routes.py`.

- [ ] **Step 1: Add six RED store tests**

1. rename changes title/`updated_at` but preserves `created_at` and transcript;
2. archive hides from default list while exact lookup survives;
3. unarchive restores the same row/transcript;
4. archive never deletes runs or messages;
5. update of a missing thread returns false and creates nothing;
6. a pre-migration message table gains nullable `run_id` and `error_code`
   without changing existing rows.

- [ ] **Step 2: Add six RED lifecycle/history direct-route tests**

1. GET history forwards all filters before pagination and returns `total`,
   `latest_run_status`, `archived_at`, and one batch-resolved `active_run`;
2. GET exact thread returns an archived target for shell navigation;
3. PATCH rename returns the updated thread while blank/over-60 title is
   rejected without mutation (parameterized inside this node);
4. PATCH archive of an active thread returns `409` without mutation;
5. PATCH archive/unarchive preserves transcript and returns honest state;
6. DELETE of an active thread returns `409` without cascade.

Strengthen the existing default unfiltered GET node in place to prove the
response remains additive-compatible; do not rename or count it as a new node.

Use real stores and call route functions directly. Patch only the dependency
seam or use actual arguments; do not mock SQL return shapes.

- [ ] **Step 3: Run focused RED**

```bash
pytest -q tests/test_research_threads.py tests/test_research_routes.py
```

- [ ] **Step 4: Implement tolerant message linkage and lifecycle writes**

Add nullable `run_id` and `error_code` to `research_messages` in both fresh
schema and tolerant `ALTER` migration. `run_id` is a nullable
`REFERENCES research_runs(id) ON DELETE SET NULL` relationship, never a
message-deleting cascade. Extend mapper/append signature without changing
legacy callers. Add narrowly named writes:

```python
rename_thread(thread_id, title, *, now=None) -> ResearchThread | None
set_thread_archived(thread_id, archived, *, now=None) -> ResearchThread | None
```

Do not overload `ensure_thread`; it remains idempotent create/frozen-title for
legacy execution paths.

- [ ] **Step 5: Implement additive HTTP contracts**

Add:

- expanded `GET /research/threads` with `q`, `ticker`, `updated_from`,
  `updated_before`, `run_state`, `archived=current|archived`, `limit`, and
  `offset`;
- `GET /research/threads/{thread_id}` exact lookup;
- `PATCH /research/threads/{thread_id}` with optional `title` and `archived`,
  requiring at least one field;
- the active-run guard on PATCH archive and DELETE.

The default GET response still contains `threads`; `total`, archive/status
fields are additive. Resolve active run rows in one batch method, never one SQL
call per thread. Exact lookup is the path for an archived/out-of-page
`NavigationTarget`.

- [ ] **Step 6: Run GREEN and commit**

```bash
pytest -q tests/test_research_threads.py tests/test_research_routes.py
git add src/research_threads.py src/api/routes/research.py \
  tests/test_research_threads.py tests/test_research_routes.py
git commit -m "feat: add research history lifecycle APIs"
```

## Task 3: Persist Complete Selection and Typed Research Failures

**Files:** create `src/research_errors.py`; modify `src/research_runs.py`,
`src/research_run_manager.py`, `src/api/routes/query.py`,
`src/api/routes/research.py`, `src/auth_drivers/claude_code_sdk_driver.py`,
`tests/test_research_runs.py`, `tests/test_claude_code_sdk_driver.py`, and route
tests already opened in Task 2.

- [ ] **Step 1: Add exactly ten RED run tests**

1. latest successful selection ignores queued/running/failed rows and maps null
   effort to `default`;
2. latest successful selection orders by `completed_at DESC, id DESC`;
3. semantic `default` persists while OpenAI provider wire receives `None`;
4. semantic `default` persists while Anthropic provider wire receives `None`;
5. explicit event `code` survives event -> run -> linked message;
6. unknown exception becomes `provider_call_failed` with redacted bounded detail;
7. timeout exception/cause and the exact code-owned API-key/subscription
   timeout event shapes become `model_timeout`;
8. one table-driven node recognizes the Anthropic done sentinel, anchored
   OpenAI `MaxTurnsExceeded:` prefix, and exact ChatGPT OAuth max-turn message
   as failed `tool_limit_reached`, preserves any supplied usage plus accumulated
   partial tool trace, and rejects near misses including
   `tool 'x' timed out after Ns`;
9. explicit cancellation persists `run_cancelled` on run and message;
10. startup reconciliation persists `run_interrupted` on run and message.

Do not change `EventType` or its pinned enum set.

- [ ] **Step 1b: Add the remaining two RED route nodes**

7. `GET /research/threads/{thread_id}/selection` returns only the deterministic
   latest successful semantic tuple and maps legacy null effort to `default`;
8. run/message DTOs expose allowlisted `error_code` plus bounded redacted detail
   while adding no credential identity to the new selection/message contracts.

Together with Task 2's six nodes, `tests/test_research_routes.py` remains exact
`+8`. Strengthen the existing default-list compatibility node in place without
renaming it.

- [ ] **Step 2: Run RED**

```bash
pytest -q tests/test_research_runs.py
```

- [ ] **Step 3: Add one error-code authority**

`src/research_errors.py` owns the allowlist and classifier:

```text
reauth_required
missing_credential
model_refusal
model_timeout
tool_limit_reached
provider_call_failed
run_cancelled
run_interrupted
```

Rules:

- preserve an explicit allowlisted event code;
- exact Anthropic done sentinel, anchored OpenAI-agent `MaxTurnsExceeded:`
  prefix, or full-match ChatGPT OAuth `Reached maximum number of turns (N)` ->
  `tool_limit_reached`; no substring match is allowed;
- `asyncio.TimeoutError` or a provider timeout in the cause/context chain ->
  `model_timeout`;
- an anchored match of the exact timeout shapes emitted by in-repo code ->
  `model_timeout`: the ChatGPT/Claude subscription-driver deadline messages and
  the direct API-key agents' `APITimeoutError:` / `TimeoutError:` prefixes;
  these are the only reviewed message-shape classifications and require
  positive plus near-miss tests;
- unknown exceptions -> `provider_call_failed`;
- cancellation/restart are assigned at their explicit lifecycle seams;
- public detail is `src.auth_drivers.probe_harness.redact(str(value))[:500]`;
- no substring inference for auth, refusal, or credentials.

Strengthen the existing Claude SDK driver error-result test in place with a
synthetic `ResultMessage(is_error=True, subtype="error_max_turns", ...)` and
assert exactly one terminal error carrying `code=tool_limit_reached`. Generic
SDK error subtypes must not receive that code. This proves the installed typed
SDK seam without adding a test node. If implementation or a live probe reveals
a different max-turn shape, stop for review and leave it as
`provider_call_failed`; do not infer from arbitrary result prose.

- [ ] **Step 4: Extend durable run/message contracts**

Add nullable `error_code` to fresh and migrated `research_runs`; add it to the
dataclass and `mark_terminal`. Add `latest_successful_for_thread()` and bounded
`get_runs(ids)` batch lookup. New run creation stores effort `default` when the
request/route resolves to provider default.

Pass `run_id` and `error_code` through `_persist_assistant_turn` /
`_persist_error_turn` as optional keyword-only arguments. Legacy callers retain
their current call shapes. At the run-manager boundary:

- classify before persisting the terminal event/message/run;
- preserve token usage and trace for max-tool exhaustion;
- never turn an error into an empty successful assistant message;
- keep persistence best-effort ordering and terminal run completion.

For a reviewed max-tool shape, the run manager converts any Anthropic
API-key `done` frame into a durable typed `error` replay frame before storage
and classifies the two reviewed error-message shapes. The Claude SDK driver
supplies the explicit code from its typed subtype. Source agent event enums
remain unchanged, but attached and reloaded clients therefore agree that these
runs failed with `tool_limit_reached` rather than briefly committing a
successful answer and correcting it later.

The cancel-route fallback used when no in-process task is found must receive the
thread store and persist the same typed cancelled terminal; it may not leave a
dangling user turn. Startup reconciliation uses the identical linked-message
shape with `run_interrupted`.

- [ ] **Step 5: Normalize semantic effort at the single provider seam**

At `_research_provider_stream`, derive:

```python
wire_effort = None if effort in (None, "", "default") else effort
```

Pass `wire_effort` to every API-key/OAuth provider branch. Do not duplicate the
normalization in four drivers. Existing callers using `None` remain identical.

- [ ] **Step 6: Add latest-selection and typed DTO routes**

Add `GET /research/threads/{thread_id}/selection` returning either null or:

```json
{"provider":"openai","model":"gpt-5.4-mini","effort":"default"}
```

Expose additive `error_code` and sanitized `error` on run/message DTOs. Do not
render or add credential identity to any new response. Existing `credential_id`
compatibility is not expanded and will be removed only under a separate API
compatibility decision.

- [ ] **Step 7: Run GREEN and commit**

```bash
pytest -q tests/test_research_runs.py tests/test_research_routes.py tests/test_events.py \
  tests/test_claude_code_sdk_driver.py::test_is_error_result_single_error_terminal
git add src/research_errors.py src/research_runs.py src/research_run_manager.py \
  src/auth_drivers/claude_code_sdk_driver.py \
  src/api/routes/query.py src/api/routes/research.py \
  tests/test_research_runs.py tests/test_research_routes.py \
  tests/test_claude_code_sdk_driver.py
git commit -m "feat: type research runs and selections"
```

## Task 4: Share the Models-UX Picker and Replace Selection Policy

**Files:** create `modelPicker.ts`, `researchSelection.ts`, and their tests;
modify `Settings.tsx`, `Research.tsx`, `researchModels.ts`,
`researchModels.test.ts`, and `researchProvider.ts`; delete the obsolete
`researchProvider.test.ts`.

- [x] **Step 1: Write eight RED shared-picker tests**

Pin:

1. provider-level veto precedes model capability;
2. ineligible model carries `task_capability_missing`;
3. cache-ok invisible model carries `model_not_visible`;
4. route-pinned unknown remains eligible with warning;
5. visible/disabled/advanced/route grouping is stable;
6. old-sidecar compat entries retain the shipped warning semantics;
7. missing active credential is one provider veto for all entries;
8. Settings and Research receive the same disabled reason for the same fixture.

- [x] **Step 2: Write twelve RED selection tests**

Pin:

1. existing thread uses latest successful tuple;
2. a new thread uses last explicit tuple;
3. no prior choice uses Settings route;
4. invalid thread tuple blocks without falling through;
5. invalid explicit tuple blocks without falling through;
6. invalid Settings route blocks;
7. unsupported saved effort blocks rather than resetting;
8. semantic `default` is a valid complete effort;
9. user provider/model/effort action writes the versioned preference;
10. auto resolution never writes the preference;
11. subscription and API-key contexts produce distinct billing copy;
12. absent effective provider/active credential becomes blocked, not a guessed
    SDK/key fallback. A separately observed missing SDK package may only add a
    fail-closed runtime veto to that effective provider.

- [x] **Step 3: Run RED**

```bash
npm test --workspace apps/arkscope-web -- \
  src/modelPicker.test.ts src/researchSelection.test.ts
```

- [x] **Step 4: Extract, do not fork, the Settings authority**

Move `optionReason`, `groupedModelEntries`, `compatEntries`, and their public
types from `Settings.tsx` to `modelPicker.ts`. Migrate Settings imports with no
rendered or test behavior change. The shared module accepts the exact effective
provider/model DTOs; it never reads DOM or component state.

- [x] **Step 5: Implement one selection resolver**

`researchSelection.ts` owns:

- `ResearchTuple { provider, model, effort }`;
- versioned localStorage read/write for the last explicit tuple only;
- validation against `effective.tasks.ai_research.providers`, provider context,
  shared option reason, and selected model effort options;
- pure precedence resolution returning `ready | blocked | needs_selection` plus
  provenance `thread | explicit | settings | user`;
- billing/auth presentation from `MODEL_UX_LABELS.authModes`.

It stores no credential ID, prompt, ticker, run ID, or answer.

- [x] **Step 6: Remove obsolete fallback policy and reconcile the 15 nodes**

Remove Research use and implementation of permissive `modelOptions`,
`defaultModel`, `lastAssistantSelection`, and `chooseResearchProvider` policy.
Keep provider-ID normalization/constants if still consumed. Delete exactly the
15 obsolete test nodes listed in accounting and map each to the new test that
supersedes its intent in the ledger. Do not leave dead exported fallback helpers
for a future caller to rediscover.

- [x] **Step 7: Run shared/Settings GREEN and commit**

```bash
npm test --workspace apps/arkscope-web -- \
  src/modelPicker.test.ts src/researchSelection.test.ts \
  src/ModelRoutingSection.test.ts src/researchModels.test.ts
git add apps/arkscope-web/src/modelPicker.ts \
  apps/arkscope-web/src/modelPicker.test.ts \
  apps/arkscope-web/src/researchSelection.ts \
  apps/arkscope-web/src/researchSelection.test.ts \
  apps/arkscope-web/src/Settings.tsx \
  apps/arkscope-web/src/researchModels.ts \
  apps/arkscope-web/src/researchModels.test.ts \
  apps/arkscope-web/src/researchProvider.ts \
  apps/arkscope-web/src/researchProvider.test.ts
git commit -m "refactor: share research model picker authority"
```

## Task 5: Extend Drawer for Wide Pinned Evidence

**Files:** modify `ui/Drawer.tsx`, `ui/primitives.css`, and
`ui/overlays.test.tsx`.

- [ ] **Step 1: Add exactly three RED overlay contracts**

1. wide `pinnable + pinned` renders inline `complementary`, no backdrop,
   `aria-modal`, focus trap, or portal;
2. the same state at/under the shell overlay token renders the existing modal
   Drawer and hides pin affordance;
3. inline close calls `onClose` and restores the trigger, while pin toggle calls
   only `onPinnedChange`.

Stub `matchMedia` before render. Existing transient Drawer tests remain
byte-for-byte behavior authorities.

- [ ] **Step 2: Run RED**

```bash
npm test --workspace apps/arkscope-web -- src/ui/overlays.test.tsx
```

- [ ] **Step 3: Implement the additive variant**

Add optional props:

```ts
pinnable?: boolean
pinned?: boolean
onPinnedChange?: (pinned: boolean) => void
```

Rules:

- inline only when open, pinnable, pinned, and `!useShellOverlay()`;
- inline uses `<aside role="complementary">`, no portal/backdrop/modal;
- modal path remains the current portal/focus/Escape contract;
- Pin/PinOff and X use Lucide icons, accessible labels, and tooltips;
- `event.defaultPrevented` overlay stacking guard remains intact;
- no new media query or breakpoint literal;
- consumer owns auto-unpin on empty Evidence.

- [ ] **Step 4: Run GREEN and commit**

```bash
npm test --workspace apps/arkscope-web -- src/ui/overlays.test.tsx
git add apps/arkscope-web/src/ui/Drawer.tsx \
  apps/arkscope-web/src/ui/primitives.css \
  apps/arkscope-web/src/ui/overlays.test.tsx
git commit -m "feat: add pinnable drawer variant"
```

## Task 6: Build On-Demand History and Lazy Conversation Hydration

**Files:** create `ResearchHistoryDrawer.tsx`; modify `api.ts`, `Research.tsx`,
`researchReducer.ts`, `styles.css`; create
`ResearchHistoryDrawer.test.tsx`; evolve existing shell-navigation tests without
renaming them.

- [x] **Step 1: Write exactly ten RED history UI tests**

1. initial workspace renders conversation with no permanent history width;
2. History trigger opens a focus-managed Drawer and loads bounded rows;
3. search/ticker/date/state filters serialize to the API and reset offset;
4. Load more appends deterministic rows without duplicate IDs;
5. selecting a row lazily fetches only that thread's messages and closes the
   narrow Drawer;
6. shell navigation fetches an exact archived/out-of-page thread;
7. inline rename updates the row/current header and rejects blank locally;
8. archive hides from current view, archived filter restores it, active archive
   shows the backend/UI block, and an archived selected transcript remains
   visible with Send blocked until unarchived;
9. delete uses ConfirmDialog, preserves on cancel/409, and removes only after a
   successful response.
10. refresh failure with prior rows preserves them, marks the view stale, and
    retries without inventing an empty result.

Use mounted components and real API request shapes. No reducer-only test may
stand in for focus, menu, ConfirmDialog, or URL serialization.

Date controls are browser-local calendar dates. Convert the lower bound to
local midnight and the upper bound to the next local midnight, then send UTC
ISO instants; the backend compares stored UTC timestamps with an exclusive
upper bound. Do not parse a local date as UTC midnight.

- [x] **Step 2: Run RED**

```bash
npm test --workspace apps/arkscope-web -- \
  src/ResearchHistoryDrawer.test.tsx src/ResearchShellNavigation.test.tsx
```

- [x] **Step 3: Add typed frontend clients**

Extend DTOs with additive archive/latest-status/run-link/error-code fields. Add:

- `queryResearchThreads(params)`;
- `getResearchThread(id)`;
- `updateResearchThread(id, patch)`;
- `getResearchSelection(id)`.

Retain `getResearchThreads(limit)` as a small compatibility wrapper if existing
shell code still needs it; it delegates to the new query and creates no second
response parser.

- [x] **Step 4: Decouple the history index from hydrated transcript state**

The history component/hook owns rows, filters, total, offset, stale/error state,
and request sequencing. The reducer owns only visited/hydrated conversations and
the active transcript. On mount:

1. query current history metadata;
2. resolve session active ID or first row;
3. fetch exact thread if the session target is outside the page;
4. fetch messages only for that selected thread;
5. attach/replay its active run if present.

Old slow responses cannot overwrite a newer selected thread or filter result.
Refresh failure keeps prior rows and renders `stale`, never a fabricated empty
history.

- [x] **Step 5: Implement deterministic history UI**

Use PageHeader/Drawer/Button/IconButton/StatusBadge/ConfirmDialog. Row content:

- live title, ticker/topic when present;
- created and last-updated timestamps with exact local time;
- latest run state;
- rename, archive/unarchive, permanent delete actions.

Filters are deterministic metadata only. Do not add LLM grouping, collections,
tags, templates, or full-text transcript search.

Renaming an actively running thread is allowed and refreshes the title supplied
to the existing shell work registry; archive/delete remain blocked. Archiving
the selected inactive thread leaves its transcript visible but inert. Deleting
the selected thread clears the session active ID and opens a blank new-thread
workspace.

- [x] **Step 6: Run GREEN and commit**

```bash
npm test --workspace apps/arkscope-web -- \
  src/ResearchHistoryDrawer.test.tsx src/ResearchShellNavigation.test.tsx \
  src/researchReducer.test.ts
git add apps/arkscope-web/src/api.ts \
  apps/arkscope-web/src/ResearchHistoryDrawer.tsx \
  apps/arkscope-web/src/ResearchHistoryDrawer.test.tsx \
  apps/arkscope-web/src/Research.tsx \
  apps/arkscope-web/src/researchReducer.ts \
  apps/arkscope-web/src/styles.css
git commit -m "feat: add on-demand research history"
```

## Task 7: Converge the Conversation, Selection, Progress, Evidence, and Errors

**Files:** create `ResearchEvidenceDrawer.tsx`, `ResearchRunProgress.tsx`,
`researchErrors.ts`, `ResearchWorkspace.test.tsx`, and
`researchErrors.test.tsx`; modify `Research.tsx`, `researchReducer.ts`,
`App.tsx`, `api.ts`, and `styles.css`.

- [ ] **Step 1: Write exactly twelve RED workspace tests**

1. PageHeader actions expose New research, History, and Evidence with no fixed
   left/right columns;
2. complete tuple resolver fixes the configured-route effect race and renders
   the reviewed provenance;
3. provider/model/effort controls use effective blocks and disabled reasons;
4. auth/billing context distinguishes subscription quota from API-key usage;
5. invalid saved selection blocks Send and offers exact Settings navigation;
6. changing model to one that does not support current effort requires an
   explicit effort choice rather than fallback;
7. create request always includes semantic provider/model/effort;
8. active composer keeps draft editable, Send visible-disabled, and Stop
   separate, with no queued second request;
9. queued and running stages use factual timestamps/bounds, including grace;
10. narrow History/Evidence are mutually exclusive and wide nonempty Evidence
    alone may reserve a pinned column;
11. empty Evidence auto-closes/unpins and reserves zero width.
12. run-detail fetch failure preserves the completed transcript and presents a
    partial detail state rather than replacing the answer with failure.

- [ ] **Step 2: Write exactly seven RED typed-error tests**

1. `reauth_required` renders login action and no raw-primary text;
2. `missing_credential` renders provider setup action;
3. `model_timeout` renders runtime-limit action;
4. `model_refusal` and `provider_call_failed` render distinct user reasons;
5. `tool_limit_reached` retains partial trace/usage and offers simplify/retry;
6. cancelled/interrupted map to interrupted rather than failed;
7. raw sanitized detail is absent in normal mode, present only in Developer
   Mode, and credential IDs/tokens never appear.

- [ ] **Step 3: Run RED**

```bash
npm test --workspace apps/arkscope-web -- \
  src/ResearchWorkspace.test.tsx src/researchErrors.test.tsx \
  src/ResearchPendingBubble.test.ts
```

- [ ] **Step 4: Replace the fixed layout and wire exact navigation**

Use:

- `PageHeader` for title/actions;
- one flexible conversation column;
- optional inline pinned Evidence column only when it has real content;
- transient History Drawer;
- existing shell token through `useShellOverlay`, never CSS literal 960;
- `developerMode`, `runtime`, and `onNavigate` props supplied by `App`.

Remove `.research-grid`, permanent `.research-threads`, permanent
`.research-trace`, stale auth-copy claims, and raw HTML buttons where a shared
primitive exists. Preserve the message Markdown renderer and ticker navigation.

- [ ] **Step 5: Implement the complete tuple toolbar**

Render both provider choices with the effective credential context; unavailable
providers remain visible-disabled with reason. Model options use shared groups;
no free-form custom ID is introduced. A route-pinned custom/unknown entry may
appear only because the backend effective view included it. Effort options come
from the selected effective model/provider contract. `default` is visibly
labelled provider default, never `None`.

Selection state initializes once per thread/new-thread context from the pure
resolver. User actions mark provenance explicit and write the preference.
Catalog/credential changes revalidate; they never silently overwrite a valid
current explicit choice.

Retry uses this same current validated tuple. The failed message controls only
the `retry_last_failed` history flag and never forces its historical provider,
model, or effort back into the request.

- [ ] **Step 6: Implement full BoundedProgress and draft/Stop semantics**

`ResearchRunProgress` translates:

- before run response: `建立執行`;
- `queued`: `等待執行`, no provider bound;
- `running`: `模型與工具執行中`, stage elapsed from `started_at`, bound from
  `runtime.research_runtime.session_timeout_s`;
- terminal status: shared ready/failed/interrupted presentation.

Use a one-second local elapsed clock only while attached to an active run.
Polling updates are not an `aria-live` region. BoundedProgress owns Stop; the
composer keeps Send visible-disabled while active. Navigating away does not
call cancel.

- [ ] **Step 7: Implement honest Evidence and Run details**

Evidence content comes from the selected assistant message's persisted
`tool_calls` (or active reducer trace): tool name, input when present, bounded
result preview, and completion state. If none exists, show `此回合沒有可用的工具證據紀錄` and
do not permit pinned width. Thinking rows are Run-detail diagnostics, not
Evidence; normal mode never relabels internal thinking as a source.

Run details use exact linked `run_id` when available:

- provider/model/effort and current auth/billing label;
- elapsed and created/started/completed timestamps;
- input/output/cache/total token fields when supplied;
- applied stance/skills from personalization;
- tools used.

Legacy messages with null `run_id` show transcript-owned details and an honest
`此舊回合沒有精確 run 連結` note. Active/reattached runs continue consuming replay
events to build the transcript, but normal UI receives only the bounded reducer
projection. Historical diagnostic re-fetch and raw-event rendering occur only
when Developer Mode opens its diagnostic disclosure. Never render
`credential_id`; never claim structured claims/citations that are not stored.

- [ ] **Step 8: Implement typed error presentation**

`researchErrors.ts` is the frontend mapping authority for code -> title,
next-action text, common state, and optional `NavigationTarget`. Unknown/null
code maps to generic `provider_call_failed`; it never uses raw text as title.
Error bubbles and page-level history/load errors use this mapping. Developer
Mode may show the already-sanitized bounded detail inside `<details>`.

Current navigation has section-level targets, not a separate runtime anchor:
`reauth_required`/`missing_credential` navigate to `providers`; selection
blocked-state actions navigate to `models`; timeout/tool-limit actions navigate
to `models` with copy naming the adjacent AI Research execution-limits panel.
Do not invent a target kind before Slice 4 owns exact Settings anchors.

- [ ] **Step 9: Run GREEN and commit**

```bash
npm test --workspace apps/arkscope-web -- \
  src/ResearchWorkspace.test.tsx src/researchErrors.test.tsx \
  src/ResearchPendingBubble.test.ts src/researchReducer.test.ts \
  src/ResearchShellNavigation.test.tsx src/AppShell.test.tsx
git add apps/arkscope-web/src/App.tsx \
  apps/arkscope-web/src/Research.tsx \
  apps/arkscope-web/src/ResearchEvidenceDrawer.tsx \
  apps/arkscope-web/src/ResearchRunProgress.tsx \
  apps/arkscope-web/src/researchErrors.ts \
  apps/arkscope-web/src/ResearchWorkspace.test.tsx \
  apps/arkscope-web/src/researchErrors.test.tsx \
  apps/arkscope-web/src/researchReducer.ts \
  apps/arkscope-web/src/api.ts \
  apps/arkscope-web/src/styles.css
git commit -m "feat: converge research workspace"
```

## Task 8: Full Verification, Responsive/Live Gate, and Review-Ready Stop

**Files:** product files above plus this plan and project map for evidence only.

- [ ] **Step 1: Prove exact test accounting**

```bash
pytest --collect-only -q
pytest --collect-only -q \
  tests/test_research_history.py \
  tests/test_research_threads.py \
  tests/test_research_runs.py \
  tests/test_research_routes.py \
  tests/test_events.py

npm test --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
npm run build --workspace apps/arkscope-web
```

Expected: backend `4412` canonical / `127` focused; frontend exactly `60 files /
571 tests`; typecheck/build pass with only explicitly identified pre-existing
warnings.

- [ ] **Step 2: Run focused backend and no-PG smoke**

```bash
pytest -q \
  tests/test_research_history.py \
  tests/test_research_threads.py \
  tests/test_research_runs.py \
  tests/test_research_routes.py \
  tests/test_events.py
```

Run the repository's existing no-PG smoke. It must return `ok:true` and
`pg_attempts:[]`. Research history/lifecycle is local profile-state only.

- [ ] **Step 3: Run mechanical ratchets**

All must be zero or match only an explicitly reviewed compatibility owner:

```bash
rg -n "window\.confirm" apps/arkscope-web/src/Research*.tsx
rg -n "research-grid|research-threads|research-trace" \
  apps/arkscope-web/src/Research.tsx apps/arkscope-web/src/styles.css
rg -n "chooseResearchProvider|discoverModels|modelOptions|defaultModel|lastAssistantSelection" \
  apps/arkscope-web/src/Research.tsx
rg -n "credential_id" \
  apps/arkscope-web/src/Research*.tsx apps/arkscope-web/src/researchErrors.ts
rg -n "\b(?:959|960|961)\b" \
  apps/arkscope-web/src/Research*.tsx apps/arkscope-web/src/styles.css
rg -n "placeOrder|cancelOrder|modifyOrder|exerciseOptions" \
  src/research_history.py src/research_errors.py
```

Also run the existing shared-class coverage and no-new-raw-exception gates.
Run the strengthened existing Claude SDK error-result node separately; it is an
in-place contract and does not enter the `127` Research-focused collection
account.

- [ ] **Step 4: Canonical backend A/B**

Build symmetric virgin archives at behavioral base `c78203a` and final
implementation/test tip. Run the canonical backend suite sequentially in the
same environment. Required verdict:

- exact existing failure/error identity equality both directions;
- `30 failed / 74 skipped / 7 errors / 18 warnings` remains unchanged unless a
  separately proven environment-wide baseline change affects both sides;
- collect delta exactly `+34/-0`;
- no hidden removal or rename.

Do not use the dirty main worktree for either archive.

- [ ] **Step 5: Disposable browser/SQLite gate**

Use a copied/fresh profile DB, scheduler disabled, a branch sidecar, branch
Vite, and headless Chromium. Do not mutate the user's normal profile. Seed:

- current, archived, renamed, active, succeeded, failed, cancelled, and no-run
  threads;
- an exact message/run link with tools, tokens, personalization, and typed
  error;
- a legacy message with no run link;
- enough rows to exercise load-more and pre-limit filters.

Verify at `1440x900`, `1024x768`, `961px`, `960px`, `959px`, and `390x844`:

1. conversation is the sole permanent region;
2. closed/empty Drawers reserve zero width;
3. wide Evidence pins inline; at 960 and below it is modal and mutually
   exclusive with History;
4. every Drawer traps/restores focus correctly in modal mode;
5. long titles/model IDs/error copy wrap without overlap;
6. history search/ticker/date/state/archive filters and load-more work;
7. rename/archive/unarchive/delete-confirm work and active mutation is blocked;
8. exact shell target opens an archived/out-of-page thread;
9. normal mode has no raw error/internal ID, Developer Mode has sanitized detail;
10. no horizontal overflow, duplicate focusable controls, nested cards, or
    blank third column.

Screenshots and process/PID cleanup go in the ledger. Temporary ports must
refuse connections afterward.

- [ ] **Step 6: User-authorized provider smoke**

Only after the deterministic gate passes, use the normal single-sidecar
environment and the user's chosen active Research credential. Create one
disposable thread with a minimal prompt that does not request tools. Verify:

- the selected complete tuple is the tuple stored on the run;
- provider receives no literal `default` effort;
- queued/running/completed progress transitions without losing the local draft;
- the result and run details remain addressable after leaving and returning;
- no fallback provider/model/effort occurs.

Do not force an error, spend repeated calls, alter credentials/routes, or claim
tool-free execution if the model independently calls a tool. Delete the
disposable thread only through the shipped ConfirmDialog after evidence is
recorded.

- [ ] **Step 7: Self-review the changed diff**

Reviewer focus:

1. history predicates precede limit and no N+1 active-run lookup exists;
2. archive/delete active-run guards are backend-authoritative;
3. run/message linkage and migrations preserve old rows;
4. semantic `default` persists but never reaches provider wire;
5. explicit codes survive; unknown/raw errors cannot become primary UI text;
   all four reviewed max-tool paths fail consistently and near matches do not;
6. Models Settings and Research share one option/reason authority;
7. saved invalid tuple blocks with no fallback;
8. selection effect-order race is structurally removed;
9. Evidence shows only stored facts and does not invent citation structure;
10. pinned Drawer obeys the one breakpoint and empty-width contract;
11. navigation detaches but never cancels; only Stop cancels;
12. global work registry, fixed tasks, Settings routes, and transcript authority
    have not forked.

- [ ] **Step 8: Stop at implementation review-ready**

After every implementer gate passes:

1. change this plan status to `IMPLEMENTED FOR REVIEW` and preserve the exact
   RED/GREEN/A-B/visual/live ledger;
2. add a newest-first map decision-log entry with branch/tip and exact counts;
3. keep the canonical spec `APPROVED`; do not mark Slice 3 LIVE;
4. do not merge, delete the worktree, sync the external Design Kit, start
   P2.8 Slice 4, or start Alpha Picks/universe implementation before independent
   review and user approval.

## Post-Review Merge Closeout (Do Not Execute Before Approval)

1. Fast-forward merge the reviewed branch only after user approval.
2. Re-run focused backend, full frontend, typecheck/build, static ratchets, and
   a merged-tree responsive smoke.
3. Mark this plan `MERGED / LIVE` while keeping the multi-slice canonical spec
   approved rather than complete.
4. Update P2.8 map status and insert the merge/live decision-log entry.
5. Sync the external Claude Design companion with the shipped Research screen,
   pinnable Drawer, and progress/error states; record that gate separately.
6. Update memory/index, remove the clean worktree/branch, and prove no test
   services remain.
7. Return sequencing to the user: P2.8 Slice 4 and the already-designed Alpha
   Picks/universe slices are distinct candidates; do not start either
   implicitly.

## Stop Conditions

Stop and return to review before continuing if any of these becomes true:

1. deterministic history cannot filter before bounded pagination;
2. exact run details require guessing message/run identity instead of nullable
   linkage;
3. structured claims/citations would require parsing Markdown or persisting new
   full tool output;
4. provider/model availability differs from the effective Models-UX projection;
5. an invalid saved tuple would need silent fallback to keep Send enabled;
6. literal `default` effort reaches any provider SDK/driver;
7. archive/delete safety cannot be enforced behind the UI;
8. pinned layout needs a second breakpoint or reserves width when empty;
9. Developer Mode cannot prevent normal-mode raw detail/internal-ID leakage;
10. server ownership would require page-unmount cancellation or a second job
    registry;
11. canonical A/B failure identities differ or accounting cannot reconcile;
12. implementation touches `config/tickers_core.json`, Alpha Picks capture,
    universe membership, NEWS, card generation, provider credentials, or order
    APIs.
13. Claude SDK max-turn exhaustion no longer exposes the reviewed typed
    `error_max_turns` subtype and would require guessing from arbitrary prose.
