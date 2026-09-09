# Cold Restoration Correction Report

## Latest Handoff

Current completion HEAD: **`b669d45519244bf14bfafa882c8ab3b8946996d2`**, after `c13080e4f63ca09882f3503876ca0d0299432a69` (cold restoration) and `54148cfc6f68a4e89191ac4c9c6728add382f71f` (caption/capture follow-up). The two display observations and the subsequently reproduced delayed-ID/delete-current candidate are resolved. Exact evidence and commands are appended chronologically below.

- Latest frontend focus: **274/274 GREEN**, `tmp/cold-restoration/frontend-delete-target-final-green.xml`.
- Latest browser: **56 contexts / 176 screenshots GREEN**, **`tmp/cold-restoration-ui/attempt-5/`**, including 64 answer/provenance viewport checks. This display-acceptance run is at `54148cfc`; it was not repeated for the subsequent delete-handler-only change, which has the new RED owner and whole-focus GREEN.
- Latest typecheck/build: **exit 0**, existing chunk warning only.
- Full frontend **1822/1822** was run once at the initial `c13080e4` implementation, before the follow-ups. It was not rerun after them and is not presented as a new full-suite result for the latest HEAD.
- Focused backend **252/252** remains valid for the unchanged backend/test snapshot. Root backend `src/` and `tests/` remained frozen; no backend rerun was performed by this worker.
- Controller whole backend: **7593 passed / 12 skipped**, zero failures/errors, read back from `tmp/cold-restoration/controller-backend-full.xml`; controller reported three existing edgar warnings and 830.31s, snapshot unchanged. This is controller-run evidence, not a worker rerun.
- All worker sessions have stopped. Controller-owned re-review/inverse mutation remains pending. No known blocker in this correction; controller's docs remain unstaged.

The initial checkpoint sections below retain their original evidence chronology. **Attempt-4 is superseded, not the final acceptance capture.** Use the latest paths above and the display follow-up section for handoff.

## Initial Status And Commit

Implemented the five approved acceptance checks in the existing single-current-conversation lifetime. No backend runtime changes, cache hints, new settings, historical route store, fallback policy, provider retries, helpers, or reviewers.

- Worktree: `/tmp/arkscope-task-route-authority`, branch `codex/task-route-authority`.
- Immutable starting HEAD: `9c0d9f5cd7f7c1131eca509f5548a3e03189360f`.
- Scoped completion commit: `c13080e4f63ca09882f3503876ca0d0299432a69` (`fix(research): preserve cold conversation restoration intent`).
- Final relevant frontend: **271 passed, 11 files, zero failures/errors/skips**.
- Full frontend, run once: **1822 passed, 125 files, zero failures/errors/skips**.
- Focused offline backend: **252 passed, zero failures/errors/skips**. No whole-backend worker run.
- Final typecheck and build: exit **0**. Existing Vite chunk-size warning remains.
- Final browser: **56 contexts / 176 screenshots**, zero page errors, external requests, unexpected APIs, or overflow violations.
- All worker test/browser/build sessions exited before this report. Controller's separately announced whole-backend verification is not included in these counts and was not interrupted. No `src/` or `tests/` edits after the controller's freeze request.

## Files And Decisions

Seven owned files are committed; controller's Priority Map, cache-hint research, ignored ledger/brief, and evidence index are not staged or edited by the worker.

| File | Change |
| --- | --- |
| `apps/arkscope-web/src/Research.tsx` | Seed the existing App-owned conversation record from the saved session ID before edits; distinguish `restoring`, `ready`, and `blank`; retain question/ticker draft with the current tuple/incomplete selection; gate Send/run retry until transcript resolution; retain exact target on failure; explicit restoration retry; invalidate stale hydration after New/open/delete. |
| `apps/arkscope-web/src/ResearchHistoryDrawer.tsx` | Report initial unfiltered list failure to Research, using existing request sequencing and latest callback refs. |
| `apps/arkscope-web/src/ResearchWorkspace.test.tsx` | 41 new real-App StrictMode cases covering cold restore, error recovery, and late responses, alongside existing warm/first-ID/route/caption controls. |
| `apps/arkscope-web/src/ResearchShellNavigation.test.tsx` | Replace the old missing-target auto-fallback expectation with retained missing target plus explicit History navigation. Historical selection remains non-authoritative. |
| `tests/test_task_runtime_binding.py` | Two synthetic managed-run context controls, one per provider direction. Backend runtime remains unchanged. |
| `docs/superpowers/evidence/2026-09-09-task-route-authority-repair/task-3-browser.py` | Isolated cold-only browser matrix, delayed list/messages, typed failures, exact request assertions, and per-thread synthetic transcripts. Existing modes retained. |
| `docs/superpowers/evidence/2026-09-09-task-route-authority-repair/task-3-preview.tsx` | Cold-only query flag mounts the real App in StrictMode with existing production CSS. |

The App already owns one conversation ref. No new owner/store was added. Drafts and explicit route choices live only in that in-memory record; session storage still contains only the active thread ID, not question text, tuples, or credentials. A warm thread rehydrates before submission. A deliberate blank stays blank on remount. With no saved target and no explicit blank intent, initial first-row selection remains the existing behavior.

Question/picker edits preserve the unresolved intended ID and status. Successful hydration marks the latest record ready without overwriting intervening input. Failed list/detail/messages or a missing saved target keep submission blocked and show existing translated errors. Retry reads the same target, or reloads initial history if no target is known. New and explicit other-thread actions remain usable. Successful empty-history refresh clears its earlier error.

Existing incomplete-selection caption suppression, route admission, Spark restriction, retired/Fable OAuth policy, execution receipts, privacy, and historical provenance are unchanged. New/open-other reset the route as before; delete-other preserves it; delete-current clears the intended current conversation even during hydration. Sequence invalidation prevents late responses from restoring a discarded conversation.

## Acceptance Evidence

- `restores cold saved context from $from after $edit selection and $page navigation`: 18 cases, both provider directions, no-edit/complete/incomplete-custom selection, and no navigation/Home/Settings. Only session ID exists at cold App mount; list and messages have separate gates. Assert retained draft/ID, no early POST, exact eventual thread/tuple/question, and unchanged historical model/effort/content.
- `blocks cold $failure restoration without losing input and supports explicit $recovery`: 12 cases, list/detail/messages/missing failures crossed with Retry/New/other. Assert no accidental new/different submission and exact recovered route/target.
- `recovers unresolved initial history with no saved ID (hasHistory=$hasHistory, $recovery)`: four cases, empty/nonempty history and Retry/History refresh. Covers retained input and clearing a stale failure after successful empty refresh.
- `does not let late cold $phase restoration undo $action`: seven cases, delayed list/detail/messages and New/other/delete-current/delete-other.
- Existing relevant owners still cover warm complete/incomplete navigation, first accepted ID, both-provider captions, custom choice, Settings defaults, actual new/open/delete, background work, and historical source display.
- Existing `test_create_run_route_persists_user_and_schedules_with_prior_history` and `test_query_stream_threads_history_into_provider` cover scheduling and legacy adapter history separately. New `test_managed_research_keeps_prior_context_with_new_explicit_tuple` crosses persisted history -> managed create -> execute -> actual adapter boundary for OpenAI Sol/low and Anthropic Sonnet/medium. It asserts exactly one adapter call, prior question/answer without duplicating the new question, exact selected tuple/original thread ID, successful persistence, and byte-identical prior message fields. All storage/auth/adapter inputs are synthetic and isolated.

## RED And Intermediate Runs

These are retained evidence, not final GREEN claims. Artifact paths below are relative to the worktree.

| Artifact | Actual result |
| --- | --- |
| `tmp/cold-restoration/frontend-red.xml` | Initial test-authoring syntax error: Workspace transform failed; 145 other tests passed and one missing-target expectation failed. JUnit represents the failed suite as an additional case (147 total / 2 failures). Not clean behavioral RED. |
| `tmp/cold-restoration/frontend-red-verified.xml` | After correcting only the extra test parenthesis, before runtime changes: **29 failed / 238 passed**, 267 total. Clean behavioral RED for lost ID/draft, early Send, missing recovery, and disallowed target fallback. |
| `tmp/cold-restoration/frontend-focus-green.xml` | Initial runtime implementation: **267 passed**. Superseded by the expanded final focus. |
| `tmp/cold-restoration/frontend-empty-recovery-red.xml` | Four additional controls: **2 failed / 2 passed / 121 skipped**. Both failures used a nonexistent `Close history` label; test harness issue, not behavioral RED. |
| `tmp/cold-restoration/frontend-empty-recovery-red-verified.xml` | Correct existing `Close` label: **1 failed / 3 passed / 121 skipped**. Behavioral RED: successful empty refresh left the prior failure visible. Fixed by clearing the initial-history error on success. |
| `tmp/cold-restoration-ui/attempt-1/` | Three scene captures plus `failure.png`; stopped on a harness assertion expecting `openai · model` instead of the existing `openai/model` historical caption. Also corrected an error-container selector before the next run. |
| `tmp/cold-restoration-ui/attempt-2/` | 20 scene captures plus `failure.png`; stopped because the synthetic missing-target 404 supplied an unrelated machine code. Corrected the fixture to the real backend's `detail: "thread not found"` contract. |
| `tmp/cold-restoration-ui/attempt-3/` | All 56 contexts / 176 scenes passed assertions, but visual inspection found the old shared transcript fixture incorrectly supplying historical content to a newly created thread after navigation. **Not final verified evidence.** Cold fixtures now keep per-thread messages; New's navigation control also asserts its first answer survives and the old answer is absent. |

No intermediate artifact was overwritten. No inverse mutation was executed by the worker.

## Exact Commands

Frontend commands ran from `/tmp/arkscope-task-route-authority/apps/arkscope-web`. The complete clean RED command was:

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only src/AICard.test.tsx src/CardExecutionApi.test.ts src/lifecycle/InvestigationView.test.tsx src/researchSelection.test.ts src/ResearchWorkspace.test.tsx src/ResearchHistoryDrawer.test.tsx src/CardApiTimeout.test.ts src/ResearchShellNavigation.test.tsx src/AppShell.test.tsx src/i18n/resources.test.ts src/i18n/foundationBoundaries.test.ts --reporter=default --reporter=junit --outputFile=../../tmp/cold-restoration/frontend-red-verified.xml
```

The initial syntax-error run and initial 267-case GREEN used that identical command with only the output basename changed to `frontend-red.xml` and `frontend-focus-green.xml`, respectively. The additional recovery RED command was:

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only src/ResearchWorkspace.test.tsx -t 'recovers unresolved initial history' --reporter=default --reporter=junit --outputFile=../../tmp/cold-restoration/frontend-empty-recovery-red-verified.xml
```

Its earlier selector-error run differed only in output basename, `frontend-empty-recovery-red.xml`. Final relevant/full/typecheck/build commands:

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only src/AICard.test.tsx src/CardExecutionApi.test.ts src/lifecycle/InvestigationView.test.tsx src/researchSelection.test.ts src/ResearchWorkspace.test.tsx src/ResearchHistoryDrawer.test.tsx src/CardApiTimeout.test.ts src/ResearchShellNavigation.test.tsx src/AppShell.test.tsx src/i18n/resources.test.ts src/i18n/foundationBoundaries.test.ts --reporter=default --reporter=junit --outputFile=../../tmp/cold-restoration/frontend-focus-final-green.xml
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only --reporter=default --reporter=junit --outputFile=../../tmp/cold-restoration/frontend-full-green.xml
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/typescript/bin/tsc --noEmit
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node --input-type=module -e 'import { build } from "vite"; await build({ envFile: false });'
```

Observed summaries: focus `11 passed`, `271 passed`, duration `10.07s`; full `125 passed`, `1822 passed`, duration `13.37s`. Typecheck was silent with exit 0 (also passed once earlier before the four extra recovery controls). Build exit 0: `2209 modules transformed`, `built in 2.65s`; JS `dist/assets/index-BYqjJDEO.js` 1164.26 kB / gzip 351.03 kB. The existing warning, `Some chunks are larger than 500 kB after minification`, was not suppressed. No later runtime or frontend test edits occurred after final focus/full/typecheck/build.

Backend command ran once from the worktree root through the required wrapper:

```sh
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_research_runs.py tests/test_research_routes.py tests/test_task_runtime_binding.py --tb=short --junitxml=tmp/cold-restoration/backend-context-green.xml
```

Observed isolation: `{"interfaces": ["lo"], "external_probe": "ENETUNREACH", "inherited_credentials": false}`. Final output: `252 passed in 16.97s`. No raw pytest, private production configuration/store reads, live provider calls, installs, migrations, or production App restart.

Final browser command, from the frontend directory:

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 PLAYWRIGHT_BROWSERS_PATH=/home/hyl/.cache/ms-playwright ARKSCOPE_UI_EVIDENCE_DIR=tmp/cold-restoration-ui/attempt-4 ARKSCOPE_COLD_RESTORATION_ONLY=1 /usr/bin/unshare --user --map-root-user --net /home/hyl/.virtualenvs/llm_app/bin/python ../../docs/superpowers/evidence/2026-09-09-task-route-authority-repair/task-3-browser.py
```

Attempts 1-3 used the identical command with only `ARKSCOPE_UI_EVIDENCE_DIR` changed to the matching attempt directory. Final exact summary:

```json
{"status": "passed", "contexts": 56, "screenshots": 176, "output": "/tmp/arkscope-task-route-authority/tmp/cold-restoration-ui/attempt-4"}
```

## Initial Checkpoint Artifacts

| Final artifact | SHA256 |
| --- | --- |
| `tmp/cold-restoration/frontend-focus-final-green.xml` | `aeb2e2cde91be6a9543e617234e10423c917bcaa5f64ded5838c3af57be8dbee` |
| `tmp/cold-restoration/frontend-full-green.xml` | `1b9bfb7bd23ae02df5711181b44fbce3a81196de8dc59d68ce83d00d089e959d` |
| `tmp/cold-restoration/backend-context-green.xml` | `07e02957a5b6b830aa02601dd87f24081938f72d5b6305f785a2f06cb0f0b128` |
| `tmp/cold-restoration-ui/attempt-4/results.json` | `5d2f279b0c5b94ddf7efa25b75cfe39c3642dc432a22183445bcf24015dd4f3c` |

JUnit totals were read back with an XML parser, not inferred from artifact names. Final browser JSON was read back: both locales (`en`, `zh-Hant`), both widths (1280 and 390; heights 960 and 844), both Settings providers, and seven cold cases (`complete`, `incomplete`, `new`, `failed-list`, `failed-detail`, `failed-messages`, `failed-missing`). Requests, layouts, and screenshot paths are all in that JSON. All 176 scenes assert real App CSS, overflow, privacy, and provider/source presentation. Cold controls also assert disabled Send/no early POST, draft retention, pending/completed captions, exact original ID/tuple, deliberate New's first-ID continuity, and failure retry.

Representative final screenshots manually inspected under `tmp/cold-restoration-ui/attempt-4/`:

- `en-1280-shell-anthropic-cold-new-new-first-id-retained.png`: new conversation contains its own first/second turns, not the old transcript.
- `en-390-shell-openai-cold-failed-list-blocked.png`: translated failure, usable Retry, retained draft, disabled Send.
- `zh-Hant-390-shell-openai-cold-failed-missing-blocked.png`: missing-target failure, no silent fallback.
- `zh-Hant-390-shell-anthropic-cold-incomplete-restored-effort-required.png`: pending custom OpenAI model, no stale Claude composer captions, required effort, disabled Send, original historical provenance.
- `zh-Hant-390-shell-anthropic-cold-incomplete-completed-exact-context.png`: completed OpenAI choice restores actual ChatGPT auth/quota captions.
- `zh-Hant-1280-shell-openai-cold-incomplete-completed-exact-context.png`: reverse-provider completion restores actual Claude captions while retaining old message provenance.

## Evidence Preservation And Shutdown

Before the browser work, SHA256 snapshots covered every PNG and `results.json` in `tmp/task-3-ui`, `tmp/final-fix/browser`, `tmp/final-fix/browser-final`, `tmp/final-fix/browser-verified`, and `tmp/final-fix/browser-caption-verified`, plus canonical `final-fix-review.md`. Readback comparison: **383 files unchanged** (377 PNGs, five JSON results, one canonical review). No old evidence was overwritten, including the original 64 screenshots and previous browser-verified evidence.

Canonical review and its intentionally vulnerable report-local diagnostic remain byte-for-byte unchanged: SHA256 `1e643494cc825d3a841982772a7bacb9ac7c2e13ac47c4c3e3a9c80d150794bf`.

All worker sessions reported exit completion: focused/full Vitest, both typechecks, build, the single focused offline backend run, and browser attempts 1-4. The harness closes Chromium and terminates/waits for its isolated Vite process in `finally`. Post-run `pgrep` for the browser script/server, Vitest, TypeScript, Playwright browser path, and this worker's exact focused backend command returned no matches (exit 1). Controller's distinct full-backend run was not stopped or counted. `git diff --check` and staged diff checks passed. After commit, only controller-owned Priority Map/cache research remained visible in status.

## Controller-Only Inverse Mutation Proposal

**Proposed only; not executed.** At `apps/arkscope-web/src/Research.tsx:319`, inside `rememberUserSelection`, replace exactly:

```ts
rememberConversation(current.threadId, tuple, null, current.status);
```

with:

```ts
rememberConversation(current.status === "restoring" ? null : current.threadId, tuple);
```

This deliberately turns a completed picker edit during restoration into known-blank intent, clears the saved target, and reenables early submission. It is the bounded inverse of preserving target/status during selection editing, without changing auth, backend, or unrelated controls.

It must kill these two named owners and their Home/Settings variants (six complete-choice cases in total) in `ResearchWorkspace.test.tsx:527`:

- `restores cold saved context from 'openai' after 'complete' selection and 'none' navigation`
- `restores cold saved context from 'anthropic' after 'complete' selection and 'none' navigation`

Controller ruling: run the WHOLE relevant 11-file frontend focus for inverse verification, not only a test-name filter. This includes the no-edit, incomplete-custom, and delete-other positive controls. Use this complete scope for each inverse and again after restoration; preserve final GREEN artifacts when selecting controller output paths:

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only src/AICard.test.tsx src/CardExecutionApi.test.ts src/lifecycle/InvestigationView.test.tsx src/researchSelection.test.ts src/ResearchWorkspace.test.tsx src/ResearchHistoryDrawer.test.tsx src/CardApiTimeout.test.ts src/ResearchShellNavigation.test.tsx src/AppShell.test.tsx src/i18n/resources.test.ts src/i18n/foundationBoundaries.test.ts
```

## Concerns And Limits

No known remaining blocker within the approved correction. Validation is deliberately offline/synthetic; actual provider network behavior was not exercised. The Vite chunk warning is existing debt. The inverse mutation, scoped re-review, and controller's broad backend verification remain controller-owned; this report does not claim their completion. Draft persistence remains in-memory for this App lifetime, not a new reload-persistent or per-history draft feature. Cache-cost hint design remains unimplemented and unapproved here.

## Display Follow-Up At 54148cfc

Commit: `54148cfc6f68a4e89191ac4c9c6728add382f71f` (`fix(research): clarify restoration and verify visible answers`). Only four owned frontend files changed: `Research.tsx`, `ResearchWorkspace.test.tsx`, `ResearchShellNavigation.test.tsx`, and the existing browser harness. No root backend code or test changes.

1. An unknown conversation title during restoration now uses the existing `history.loadingAria` translation; a failed restoration uses existing `history.loadFailedTitle`. Known thread titles remain intact, and deliberate New still displays its normal heading. No new strings, loading policy, or route behavior.
2. The new answer missing from the controller's English mobile screenshot was **internal transcript scrolling**, not missing execution or response data. Playwright's `to_be_visible()` did not establish that the answer was inside the scroll viewport. The harness now waits for succeeded progress, scrolls the target answer into view, settles two animation frames, and checks both answer-body and provenance rectangles against the transcript viewport and page bounds before capture. No runtime scrolling/CSS change was made.

### Follow-Up RED And GREEN

- `tmp/cold-restoration/frontend-heading-red.xml`: **28 failed / 102 passed**, 130 total in the two affected files, no errors/skips. These were strengthened existing owners failing on misleading `New conversation` headings, not a transform/selector issue. SHA256 `dc61b5fca9b7613ed114cf12f76bd7ffd4c7e0ddadafed9f2ad3e3fc03e4b4ae`.
- `tmp/cold-restoration/frontend-display-final-green.xml`: **271 passed / 11 files**, zero failures/errors/skips; duration `10.36s`. SHA256 **`159c5c365500a71c94d30972a5bc00e0a0fcb3af7275e3a474d8152f3b2bc962`**. No new case-count inflation; existing cold and navigation owners now also assert truthful headings.
- Latest typecheck: silent, exit 0. Latest build: exit 0, `2209 modules transformed`, `built in 2.80s`; `dist/assets/index-CaZ9-cLu.js` 1164.31 kB / gzip 351.05 kB. Existing >500 kB warning retained.
- `tmp/cold-restoration-ui/attempt-5/results.json`: **56 contexts / 176 screenshots**, no page errors or overflow failures, **64 completed-answer viewport checks**. SHA256 **`e1eca61bd10c3c35ea8b4dd57333d2fa6e8682060b05b4a08095296820a56250`**.

Exact follow-up commands, from `apps/arkscope-web`:

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only src/ResearchWorkspace.test.tsx src/ResearchShellNavigation.test.tsx --reporter=default --reporter=junit --outputFile=../../tmp/cold-restoration/frontend-heading-red.xml
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only src/AICard.test.tsx src/CardExecutionApi.test.ts src/lifecycle/InvestigationView.test.tsx src/researchSelection.test.ts src/ResearchWorkspace.test.tsx src/ResearchHistoryDrawer.test.tsx src/CardApiTimeout.test.ts src/ResearchShellNavigation.test.tsx src/AppShell.test.tsx src/i18n/resources.test.ts src/i18n/foundationBoundaries.test.ts --reporter=default --reporter=junit --outputFile=../../tmp/cold-restoration/frontend-display-final-green.xml
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/typescript/bin/tsc --noEmit
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node --input-type=module -e 'import { build } from "vite"; await build({ envFile: false });'
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 PLAYWRIGHT_BROWSERS_PATH=/home/hyl/.cache/ms-playwright ARKSCOPE_UI_EVIDENCE_DIR=tmp/cold-restoration-ui/attempt-5 ARKSCOPE_COLD_RESTORATION_ONLY=1 /usr/bin/unshare --user --map-root-user --net /home/hyl/.virtualenvs/llm_app/bin/python ../../docs/superpowers/evidence/2026-09-09-task-route-authority-repair/task-3-browser.py
```

Final browser output:

```json
{"status": "passed", "contexts": 56, "screenshots": 176, "output": "/tmp/arkscope-task-route-authority/tmp/cold-restoration-ui/attempt-5"}
```

The controller's exact affected acceptance images have replacements in `attempt-5` and were manually inspected:

- `zh-Hant-390-shell-anthropic-cold-failed-missing-blocked.png`: failure heading, correct typed error/Retry, retained draft and OpenAI choice, disabled Send.
- `en-390-shell-openai-cold-complete-completed-exact-context.png`: the new synthetic answer and `anthropic/claude-sonnet-5` / `low` provenance are visibly in-frame. Recorded transcript scroll position changed from 0 to 165; viewport vertical bounds were 295.75-407.8125, metadata 306.640625-323.890625, answer body 327.890625-368.171875. These measurements are stored in that scene's `answer_visibility` JSON.
- `zh-Hant-390-shell-anthropic-cold-complete-list-pending-after-settings.png`: existing loading-history heading, retained draft/route, disabled Send during unresolved initial history.
- `zh-Hant-390-shell-openai-cold-failed-missing-blocked.png`: reverse-provider failure heading and recovery remain correct.

Attempts 1-4 remain untouched. Attempt-4 JSON still hashes to `5d2f279b0c5b94ddf7efa25b75cfe39c3642dc432a22183445bcf24015dd4f3c`; its earlier apparent GREEN did not include the new heading/in-viewport acceptance checks. The original 383-file preservation snapshot was compared again after this follow-up with zero changes. Final follow-up test/typecheck/build/browser sessions all exited before this amendment; the same targeted process check again returned no worker matches. No inverse mutation or full-backend run was executed by the worker. The proposed inverse and six named killed-owner expectations above remain unchanged.

## Delayed Target Deletion At b669d455

Commit: **`b669d45519244bf14bfafa882c8ab3b8946996d2`** (`fix(research): clear loaded thread when intended target is deleted`). Only `apps/arkscope-web/src/Research.tsx` and `apps/arkscope-web/src/ResearchShellNavigation.test.tsx` changed.

The controller's candidate was reproduced through the public navigation-request boundary in a mounted StrictMode Research view and actual History delete controls: hydrate B, enter a draft, navigate by ID to A with its detail response held, then delete A. Before the fix the intended record became blank but the reducer retained B; the actual subsequent POST used `thread-b`. This was a real wrong-context submission, not merely a heading mismatch.

The bounded fix adds the existing reducer `newThread` action when deleting the intended current target. It clears the last-loaded active reducer ID as well as the intended record, while the existing `deleteThread` action still removes only the deleted thread. Previously loaded B's history is not deleted. Existing sequence invalidation rejects A's late response. Deleting B or a third thread C instead preserves intended A, keeps Send blocked until A resolves, and ultimately submits to A.

New parameterized owner: `keeps the intended target after deleting thread %s during delayed ID navigation` in `ResearchShellNavigation.test.tsx`. The `a` case asserts a fresh non-A/B/C request ID and ignores the late A response; `b` and `c` are the delete-other preservation controls. All three assert retained input and the exact request tuple.

### Final Verification

| Artifact | Actual result | SHA256 |
| --- | --- | --- |
| `tmp/cold-restoration/frontend-delete-target-red.xml` | **1 failed / 2 passed / 5 skipped**; failing case explicitly records `thread-b` as the wrong POST target | `b799a819c3d06581758794967ff1ff3b41f1c61fbc6898f6678e5347b21bad1d` |
| `tmp/cold-restoration/frontend-delete-target-final-green.xml` | **274 passed, 11 files**, zero failures/errors/skips, `10.18s` | `cb894e725e2eae3603672bfe29e8f166dbf3b81495c97323c215a6f532fbfa97` |
| `tmp/cold-restoration/controller-backend-full.xml` | **Controller-run:** 7605 cases, 7593 passed / 12 skipped, zero failures/errors | `db0a126208d5807960dc9371b6884660f3a74f414c13f7d2cd3b9897bcd93db1` |

Latest typecheck: silent, exit 0. Latest build: exit 0, 2209 modules, `built in 2.66s`; `dist/assets/index-Q02xfy9W.js` 1164.34 kB / gzip 351.06 kB. Existing chunk warning remains. No additional full frontend/backend or browser run was made for this two-file completion; the exact earlier full-suite/browser snapshot boundaries are stated in Latest Handoff.

Exact worker commands from `apps/arkscope-web`:

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only src/ResearchShellNavigation.test.tsx -t 'keeps the intended target after deleting' --reporter=default --reporter=junit --outputFile=../../tmp/cold-restoration/frontend-delete-target-red.xml
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only src/AICard.test.tsx src/CardExecutionApi.test.ts src/lifecycle/InvestigationView.test.tsx src/researchSelection.test.ts src/ResearchWorkspace.test.tsx src/ResearchHistoryDrawer.test.tsx src/CardApiTimeout.test.ts src/ResearchShellNavigation.test.tsx src/AppShell.test.tsx src/i18n/resources.test.ts src/i18n/foundationBoundaries.test.ts --reporter=default --reporter=junit --outputFile=../../tmp/cold-restoration/frontend-delete-target-final-green.xml
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/typescript/bin/tsc --noEmit
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node --input-type=module -e 'import { build } from "vite"; await build({ envFile: false });'
```

The `-t` command above records the initial candidate RED only. It is NOT the controller inverse-verification scope. Controller inverse runs use the full 11-file command in the mutation section.

Additional exact inverse proposal, **not executed**: remove only `dispatch({ kind: "newThread" });` under `if (conversationRef.current?.threadId === threadId)` in `handleThreadDeleted` (the line following the new intended-vs-hydrated comment). It must kill `keeps the intended target after deleting thread a during delayed ID navigation`; the `b` and `c` cases must remain GREEN. Use the whole relevant focus for this inverse and its restored GREEN, as directed by the controller.

All new worker sessions exited. Targeted `pgrep` again returned no worker matches; `git diff --check` passed. `git diff c13080e4 -- src tests` was empty, confirming the backend source/test snapshot remains unchanged since the main implementation. Controller's Priority Map, plan, cache-hint research, and ignored coordination docs remain unstaged by the worker. Report updated only after committing and stopping all own sessions.
