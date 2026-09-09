# Combined Final-Review Fix Report

## Status And Commits

Both accepted findings are fixed in the one authorized wave, including the
controller's additional incomplete-selection preservation control. Focused
verification is GREEN. Ready for the controller's complete suites and scoped
re-review; this report is not a merge authorization or independent re-review.

- Worktree: `/tmp/arkscope-task-route-authority`
- Branch: `codex/task-route-authority`
- Immutable starting HEAD: `090a72258e76f84367c886da0e41ae79e181d2c0`
- P1 commit: `86eb79cfd15d25f2481344cc024f24af20b40136`
  (`fix(research): redact and bound structured refusal details`)
- P2 commit: `6bbb36cd92676981e2d7193a617155121ea30c22`
  (`fix(research): retain current selection across shell navigation`)
- Final focused backend: **1,469 passed**, zero failures/errors/skips.
- Final focused frontend: **206 passed**, 10 files, zero failures/errors/skips.
- Typecheck and build: passed. Browser: **72 scenes/screenshots**, 8 contexts,
  zero page errors, with synthetic request and geometry assertions.

Only the following ten scoped files were committed. This report was written
after the commits, outside those commits, as requested.

| Commit | Changed File | Purpose |
| --- | --- | --- |
| P1 | `src/anthropic_refusal.py` | Shared closed, bounded, sanitized refusal details and safe exception text. |
| P1 | `src/agents/anthropic_agent/agent.py` | Supply the already-selected native client's API key before logging/emitting refusal. |
| P1 | `src/api/routes/query.py` | Enforce the safe detail shape at the legacy Research error-event boundary. |
| P1 | `src/research_run_manager.py` | Enforce the same shape with the captured binding before managed event persistence. |
| P1 | `tests/test_task_runtime_binding.py` | 54 new parametrized refusal privacy/projection/replay cases. |
| P2 | `apps/arkscope-web/src/App.tsx` | Own one transient current-conversation selection record above page unmount. |
| P2 | `apps/arkscope-web/src/Research.tsx` | Preserve complete and incomplete choices for that conversation; reset on actual conversation changes. |
| P2 | `apps/arkscope-web/src/ResearchWorkspace.test.tsx` | 34 new actual App shell navigation, reset, custom-ID, first-ID and delayed-hydration controls. |
| P2 | `docs/superpowers/evidence/2026-09-09-task-route-authority-repair/task-3-browser.py` | Opt-in actual shell navigation mode and separate evidence output directory. |
| P2 | `docs/superpowers/evidence/2026-09-09-task-route-authority-repair/task-3-preview.tsx` | Actual App preview with production shell and Settings styles. |

## P1 Correction And Controls

`safe_refusal_details` accepts only string values for `type`, `category` and
`explanation`, from SDK objects or adapter dictionaries. Each value uses the
existing `sanitize_runtime_error`, which redacts the captured key before its
500-character bound. Unknown fields, nested values, malformed fields and
null/scalar payloads do not become public diagnostic data. Benign strings are
retained. This is a closed refusal projection, not recursive event rewriting.

The native exception projects details and sanitizes its text before the native
warning log and event. It uses the active captured binding and the already
selected client's key; it does not resolve another active credential. The
legacy SSE and managed event builder also apply the helper independently with
the captured binding, protecting against an adapter that emits raw structured
details. Managed classification explicitly retains that binding too.

The named regression owner is
`test_refusal_details_are_private_closed_and_replayable`. Its 54 cases combine
six paths (bound native, unbound native, legacy, managed, raw legacy adapter,
raw managed adapter) with nine detail shapes: category key, explanation-only
key, type key, benign, unknown/nested fields, null, malformed scalar,
malformed fields, and redact-before-bound.

Native/legacy/managed cases use real Anthropic SDK clients with HTTP transport
fakes returning HTTP 200 and `stop_reason=refusal`. They assert one request,
the exact selected key/model, typed `model_refusal`, and no success/fallback.
The selected synthetic key is replaced in the fixture's active credential
store after capture, proving the captured authority remains effective. Raw
adapter cases assert one adapter invocation and no SDK request. Managed cases
reopen the real temporary SQLite store and call the public replay route;
assertions cover replay, persisted Research rows, public SSE and captured logs.
Only synthetic fixture keys are involved.

The complete relevant backend set also preserves existing successful streams,
Research run/replay behavior, events/refusal semantics, fixed-task callers,
card execution/receipts, fixed-output compatibility, subscription controls,
custom model IDs and native/child runtime binding controls.

## P2 Correction And Controls

App owns a single ref record containing current thread ID, valid explicit
tuple, and the separate incomplete provider/model edit. Research uses a local
ref fallback for standalone consumers. Neither a historical override map nor
a global/localStorage preference store was added. Existing session storage
continues to hold only the active thread ID.

Hydration retains both selection fields only for the same actual conversation.
New conversation, open-another, and delete-current clear them; delete-other
preserves them. A deliberately blank/new conversation stays blank on remount
instead of reopening the first history row. Submission associates the draft's
selection with its client-created, server-confirmed first thread ID.

An incomplete model choice stays selected and effort-required after Home or
Settings, including for a new conversation. It cannot silently become the
prior valid tuple or Settings route. A deliberate supported effort is required
to enable Send, and deliberately selected custom IDs remain admitted.

The final delayed-hydration controls also hold Send disabled while a recalled
conversation is loading and bind intervening picker edits to the retained
conversation ID, not the reducer's temporary null ID. After hydration, the
exact edited tuple executes against the original conversation.

Tests render real App and Research in StrictMode and click actual shell nav
buttons. They assert the old textarea is detached and the remounted textarea
is a different DOM element. Only unrelated Home/Settings data views are mocked
in unit tests; the browser harness uses real App, Home, Settings and Research.
The 34 new cases cover both OpenAI and Anthropic Settings defaults: eight
complete-choice round trips, eight incomplete custom-choice round trips,
sixteen complete/incomplete reset and delete-other preservation controls, and
two delayed-hydration controls. Exact run request tuples/thread IDs, first-ID
continuity, later turns, ignored stale global preferences, and absence of
historical `/selection` authority are asserted. Existing standalone Research,
selection, App/shell, card receipt/API timeout and lifecycle controls also pass.

## RED/GREEN Record

All paths below are relative to the worktree. JUnit records were read back
with an XML parser to confirm testcase counts, failures, errors and skips.

| Artifact In `tmp/final-fix/` | Result | Interpretation |
| --- | --- | --- |
| `backend-red.xml` | 40 failed / 104 passed | RED before P1 runtime changes. Category, explanation, type and closed-shape cases fail at all six paths; malformed controls fail too. Six long-padding cases also fail and have the fixture correction below. |
| `backend-owner-green.xml` | 6 failed / 138 passed | Intermediate run, despite filename. Only the long-padding expectation was wrong: a 492-character token-like `x` run is itself redacted by the existing generic sanitizer. |
| `backend-focus-green.xml` | 1,469 passed, 63.97 s | Corrected padding to `"x " * 246`; exact selected-key redaction is asserted before the 500-character bound. Full relevant backend focus GREEN. |
| `frontend-red.xml` | 16 failed / 97 passed | Initial fixture selector mistakes (`Research` versus `AI Research`, New Research capitalization); not claimed as product RED. |
| `frontend-red-verified.xml` | 14 failed / 99 passed | Corrected selectors; product RED for lost override or a blank/new conversation reopening history. Open-other positive controls pass. |
| `frontend-owner-green.xml` | 113 passed | Initial current-conversation lifetime fix GREEN. |
| `frontend-incomplete-red.xml` | 10 failed / 119 passed | Added controller preservation cases expose lost incomplete choice on remount, including delete-other preservation. |
| `frontend-focus-green.xml` | 204 passed, 6.00 s | Complete/incomplete lifetime fix and relevant frontend controls GREEN. |
| `frontend-hydration-red.xml` | 2 failed / 204 passed, 6.15 s | Added delayed-history controls: Send was enabled before the recalled conversation hydrated. |
| `frontend-final-green.xml` | 2 failed / 204 passed, 6.21 s | Intermediate run, despite filename. Send guard passes, but StrictMode fixture reused a consumed Response, preventing history from loading. |
| `frontend-verified-green.xml` | 206 passed, 6.22 s | Fixture now gates delivery and creates a fresh Response per request. Delayed hydration, exact retained edits/ID and all relevant controls GREEN. |

No vulnerable-behavior doctest was edited or rerun to manufacture success.
No inverse mutations were used. The RED-first regressions above are the new
owners; controller mutation records were not changed.

### Backend Commands

Run from `/tmp/arkscope-task-route-authority`. The two owner invocations were:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_task_runtime_binding.py --tb=short --junitxml=tmp/final-fix/backend-red.xml
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_task_runtime_binding.py --tb=short --junitxml=tmp/final-fix/backend-owner-green.xml
```

The final complete relevant focus invocation was:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests/test_agent_history.py tests/test_agents.py tests/test_ai_research_route.py tests/test_analysis_cards_api.py tests/test_auth_drivers.py tests/test_auth_factory.py tests/test_card_execution_authority.py tests/test_card_runs.py tests/test_card_synthesis.py tests/test_chatgpt_oauth_driver.py tests/test_claude_code_sdk_driver.py tests/test_codex_translation_adapter.py tests/test_content_translation_failures.py tests/test_events.py tests/test_fixed_task_runtime_config.py tests/test_lifecycle_investigation_controller.py tests/test_lifecycle_investigation_routing.py tests/test_lifecycle_investigation_task_test.py tests/test_lifecycle_web_controller.py tests/test_lifecycle_web_models.py tests/test_lifecycle_web_preflight.py tests/test_live_resolver.py tests/test_model_capabilities.py tests/test_model_credentials_characterization.py tests/test_model_route_store.py tests/test_model_routing.py tests/test_model_task_test.py tests/test_openai_fixed_output_compatibility.py tests/test_openai_responses_convergence.py tests/test_openai_transport.py tests/test_personalization_prompt.py tests/test_replay.py tests/test_replay_fixtures.py tests/test_replay_openai.py tests/test_research_routes.py tests/test_research_runs.py tests/test_research_runtime_config.py tests/test_security_lifecycle_routes.py tests/test_security_lifecycle_translation.py tests/test_subagent.py tests/test_subscription_structured_output.py tests/test_task_runtime_binding.py --tb=short --junitxml=tmp/final-fix/backend-focus-green.xml
```

These all used the prescribed offline wrapper, not raw pytest. The wrapper
reported isolated loopback-only networking, external probe `ENETUNREACH`, and
no inherited credentials. No backend warning was reported in this focused run.

### Frontend Commands

Run from `/tmp/arkscope-task-route-authority/apps/arkscope-web`. The following
factored shell notation gives the exact command arguments and file lists for
the Vitest invocations above; it does not imply they were all run against the
final code, since the RED and intermediate artifacts record earlier states.

```bash
owner_files=(src/researchSelection.test.ts src/ResearchWorkspace.test.tsx src/ResearchShellNavigation.test.tsx src/AppShell.test.tsx)
focus_files=(src/AICard.test.tsx src/CardExecutionApi.test.ts src/lifecycle/InvestigationView.test.tsx src/researchSelection.test.ts src/ResearchWorkspace.test.tsx src/CardApiTimeout.test.ts src/ResearchShellNavigation.test.tsx src/AppShell.test.tsx src/i18n/resources.test.ts src/i18n/foundationBoundaries.test.ts)
frontend_test() {
  local report="$1"
  shift
  env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only "$@" --reporter=default --reporter=junit --outputFile="../../tmp/final-fix/$report"
}
frontend_test frontend-red.xml "${owner_files[@]}"
frontend_test frontend-red-verified.xml "${owner_files[@]}"
frontend_test frontend-owner-green.xml "${owner_files[@]}"
frontend_test frontend-incomplete-red.xml "${owner_files[@]}"
frontend_test frontend-focus-green.xml "${focus_files[@]}"
frontend_test frontend-hydration-red.xml "${focus_files[@]}"
frontend_test frontend-final-green.xml "${focus_files[@]}"
frontend_test frontend-verified-green.xml "${focus_files[@]}"

env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/typescript/bin/tsc --noEmit
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node --input-type=module -e 'import { build } from "vite"; await build({ envFile: false });'
```

Typecheck passed after the final fixture correction. The latest build passed
after the final runtime change: 2,209 modules, 2.71 s, JS 1,163.34 kB
(350.72 kB gzip). Only the existing Vite over-500-kB chunk warning was emitted.
Frontend failed runs include ordinary i18next debug output, not an additional
runtime failure. No dependencies were installed or private `.env` files loaded.

## Browser Evidence And Preservation

The final run used this command, from `apps/arkscope-web`:

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 PLAYWRIGHT_BROWSERS_PATH=/home/hyl/.cache/ms-playwright ARKSCOPE_UI_EVIDENCE_DIR=tmp/final-fix/browser-verified ARKSCOPE_SHELL_NAVIGATION_ONLY=1 /usr/bin/unshare --user --map-root-user --net /home/hyl/.virtualenvs/llm_app/bin/python ../../docs/superpowers/evidence/2026-09-09-task-route-authority-repair/task-3-browser.py
```

Earlier runs used the identical command with only
`ARKSCOPE_UI_EVIDENCE_DIR=tmp/final-fix/browser` and then
`ARKSCOPE_UI_EVIDENCE_DIR=tmp/final-fix/browser-final`. All are separate from
the controller's original `tmp/task-3-ui` images/results. The first run passed
its 72 behavioral scenes but lacked production shell CSS, found by screenshot
inspection; it is not accepted as final visual evidence. The harness was
corrected to load shell/Settings styles and assert the shell's grid layout.
The second and final runs each passed all 72 scenes with those styles; the
final run also includes the final delayed-hydration runtime guard.

Final evidence:

- Results: `tmp/final-fix/browser-verified/results.json`
- Results SHA-256: `24e1c93a1b0c5b2a5011e77a41bc848a039a4d56011bfc2470879ed624249348`
- Screenshots: `tmp/final-fix/browser-verified/*.png`
- Eight contexts: OpenAI/Anthropic Settings defaults x English/Traditional
  Chinese x desktop 1280x960/mobile 390x844.
- Nine scenes per context: Settings default, incomplete after Home, incomplete
  after Settings, complete after Home, complete after Settings, new reset,
  new incomplete after Home, first-ID retained, open-other reset.
- Exact four run bodies per context asserted, including two turns in the
  original conversation and two sharing the new conversation ID. No POST is
  allowed for the incomplete selection. Historical-selection lookup is an
  explicit harness failure. Page errors are empty. Overflow and narrow text
  geometry assertions passed. All API responses are synthetic and request
  interception rejects non-loopback/unexpected routes.

Final screenshots directly inspected: English desktop OpenAI incomplete after
Settings; Traditional Chinese mobile Anthropic-default incomplete after
Settings; English mobile OpenAI first-ID retained; Traditional Chinese desktop
Anthropic-default complete after Settings. Current choice, effort-required
state, disabled/ready submission, historical source and subsequent-turn source
remain distinguishable, with no incoherent overlap in these inspected screens.

Read-only SHA-256 verification against the controller's
`docs/superpowers/evidence/2026-09-09-task-route-authority-repair/browser-results.json`
(archived code `c5146a9a581f7e81ee5890a109e3f9ae81047ce9`) confirmed **all 64
original screenshot hashes match**, with zero mismatches. Original
`tmp/task-3-ui/results.json` also still matches
`ffa53a59cc0c68de14eede097d4faaae67e900d0c42babb3df8aa4fa4ccdcf0a`.
No original images/results or controller-owned JSON were overwritten. The
existing Vite cache path is unchanged; it is not a screenshot/result artifact.

## Hand-Test Delta For Controller

No controller-owned hand-test or plan document was edited. Incorporate these
behavior checks there as appropriate:

1. With OpenAI Settings defaults, explicitly choose another full Research
   tuple in the current conversation; visit Home and Settings and return.
   Both the picker and next exact execution tuple must retain that choice.
   Repeat with Anthropic Settings defaults.
2. Choose an explicit model but no effort. Visit Home/Settings and return;
   the model remains selected, effort remains required, and a filled question
   cannot be submitted. Choosing a supported effort deliberately enables Send.
   Repeat in a new conversation and with a visible custom model ID.
3. Submit that new conversation, navigate away and return, and submit another
   turn. Both requests must share the same first assigned thread ID and retain
   the current explicit tuple.
4. New, open-another, and delete-current must reset to Settings. Returning to
   an earlier thread must not resurrect an override collection. Deleting a
   different conversation must retain the current full or incomplete choice.
5. With delayed history loading on return, Send stays blocked until the same
   conversation hydrates; picker edits made meanwhile remain bound to it.

## Remaining Concerns And Boundaries

- No unresolved P1/P2 implementation blocker. Controller complete backend and
  frontend suites plus scoped re-review remain pending, intentionally not
  duplicated here. No live provider/account acceptance is claimed.
- Existing Vite chunk-size warning remains. The pre-existing compaction and
  eventkit issues identified by the controller were not changed or worked
  around. No new backend warnings occurred in the focused run.
- Existing incomplete-picker presentation limitation remains: auxiliary
  auth/quota text follows the previously resolved tuple until effort is
  chosen, even when the pending model belongs to another provider. The model,
  effort-required warning and blocked Send reflect the pending edit; this
  lifetime fix does not redesign that pre-existing caption behavior.
- Controller-owned uncommitted plans, priority map, evidence/JSON, and the
  moved Task 2 report/deletion were preserved and excluded from commits. The
  post-commit worktree status contains only those original controller changes.
  The index is empty; both working diff and BASE-to-final diff checks pass.
- No provider calls, credential/store/config inspection outside isolated
  synthetic fixtures, production database access, raw pytest, dependency
  installation, subagents, merge, push or App restart. No model registry,
  admission, transport, compaction or unrelated runtime refactor. Synthetic
  browser server and test processes exited; no App/dev server was left running.

## P2 Caption Completion In The Same Fix Wave

This supplement supersedes the earlier incomplete-picker caption concern and
the earlier frontend/browser final counts. The controller ruled that stale
captions contradict truthful display and must be corrected within this wave.
The original report and all earlier artifacts remain intact as chronology.

**Completion commit:** `20a7737300fb0557cbc0e1712f833163cadb61ce`
(`fix(research): hide stale captions during incomplete selection`), based on
`6bbb36cd92676981e2d7193a617155121ea30c22`. No backend file changed and no backend
test was rerun. The previously accepted 1,469-test backend evidence is unchanged.

### Bounded Correction

- `apps/arkscope-web/src/Research.tsx`: two rendering guards. While
  `incompleteSelection` exists, the resolved selection presentation is absent,
  suppressing its auth/quota captions. The separate blocked-reason branch is
  also suppressed, including its raw `selection.reasonCode` fallback.
- Correct provider buttons, pending model, effort-required warning, disabled
  Send, and all current-conversation lifetime behavior remain intact. Completing
  effort restores the actual new tuple's normal auth/quota/reason captions.
  If its runtime is unavailable, that new route's reason remains visible and
  Send stays disabled; this does not remove valid diagnostics.
- `apps/arkscope-web/src/ResearchWorkspace.test.tsx`: eight new real-App shell
  controls cover both provider directions, ready/blocked prior routes, and
  ready/unavailable destination runtimes. Both Home and Settings unmounts are
  exercised. Expectations distinguish subscription and API quota captions,
  exclude stale localized and raw blocked reasons, preserve provider buttons,
  and check exact completed run tuple/thread ID when execution is available.
- `docs/superpowers/evidence/2026-09-09-task-route-authority-repair/task-3-browser.py`:
  caption assertions in existing shell scenes plus three reverse-provider
  scenes per context. No new production text, feature, setting, admission rule,
  translation resource, stylesheet or policy was added.

### Exact Verification Record

The same ten-file relevant frontend set was run, preserving all previous 206
cases and adding eight caption controls, for **214 tests** total. Using the
`frontend_test` command and `focus_files` definition above, the exact invocations
were, in order:

```bash
frontend_test frontend-caption-red.xml "${focus_files[@]}"
frontend_test frontend-caption-green.xml "${focus_files[@]}"
frontend_test frontend-caption-red-verified.xml "${focus_files[@]}"
frontend_test frontend-caption-green-verified.xml "${focus_files[@]}"
```

| Artifact In `tmp/final-fix/` | Result | Meaning |
| --- | --- | --- |
| `frontend-caption-red.xml` | 8 failed / 206 passed, 7.24 s | New controls reproduce stale auth/quota captions in both directions and stale reasons for blocked prior routes. |
| `frontend-caption-green.xml` | 214 passed, 7.14 s | Intermediate behavioral GREEN. Subsequent typecheck found the fixture's invented reason was not a member of `ModelReasonCode`; this is not the final accepted artifact. |
| `frontend-caption-red-verified.xml` | 8 failed / 206 passed, 7.10 s | Fixture corrected to existing `model_task_unsupported`. Only the two new rendering guards were temporarily inverted with apply_patch to repeat RED on the final typed fixture. |
| `frontend-caption-green-verified.xml` | 214 passed, 7.10 s | Final GREEN after restoring both guards with apply_patch. All ten files passed; zero errors or skips. |

Initial typecheck diagnostic, corrected in the test fixture without casts or
runtime/type-policy changes:

```text
src/ResearchWorkspace.test.tsx(538,7): error TS2322: Type '"fixture_prior_block"' is not assignable to type 'ModelReasonCode | null'.
```

Latest frontend summary output, with terminal styling removed:

```text
 Test Files  10 passed (10)
      Tests  214 passed (214)
   Start at  09:21:15
   Duration  7.10s (transform 2.77s, setup 1.49s, import 3.31s, tests 8.35s, environment 3.59s)

JUNIT report written to /tmp/arkscope-task-route-authority/tmp/final-fix/frontend-caption-green-verified.xml
```

JUnit XML was parsed to independently confirm both RED records contain eight
failed testcases and both GREEN records contain zero failures/errors/skips.
The RED runs include ordinary i18next debug output. No tests were skipped or
removed. The final implementation contains both restored guards.

Final typecheck and build commands, from `apps/arkscope-web`:

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/typescript/bin/tsc --noEmit
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node --input-type=module -e 'import { build } from "vite"; await build({ envFile: false });'
```

Final typecheck: **exit 0, no output**. Final build: **exit 0**, 2,209 modules,
2.81 s. Output assets: CSS 99.45 kB / 16.51 kB gzip; JS 1,163.35 kB / 350.72 kB
gzip. Existing warning only: `Some chunks are larger than 500 kB after
minification.` An earlier build of the identical runtime guards also passed
in 2.74 s; the 2.81-second run is the latest one after restoration.

### New Browser Evidence

One new browser run was performed for this completion, in a directory that
did not previously exist. Exact command, from `apps/arkscope-web`:

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 PLAYWRIGHT_BROWSERS_PATH=/home/hyl/.cache/ms-playwright ARKSCOPE_UI_EVIDENCE_DIR=tmp/final-fix/browser-caption-verified ARKSCOPE_SHELL_NAVIGATION_ONLY=1 /usr/bin/unshare --user --map-root-user --net /home/hyl/.virtualenvs/llm_app/bin/python ../../docs/superpowers/evidence/2026-09-09-task-route-authority-repair/task-3-browser.py
```

Exact final browser output:

```json
{"status": "passed", "contexts": 8, "screenshots": 96, "output": "/tmp/arkscope-task-route-authority/tmp/final-fix/browser-caption-verified"}
```

- Latest results: `tmp/final-fix/browser-caption-verified/results.json`
- Results SHA-256: `91de9c434c35ad95754e95c9467e14a0e1f6d85bfaa80d9e891ecd17d6228013`
- Latest screenshots: `tmp/final-fix/browser-caption-verified/*.png`
- Eight contexts remain English/Traditional Chinese x desktop/mobile x both
  Settings providers. Twelve scenes each now include the three reverse-provider
  scenes: incomplete after Home, incomplete after Settings, complete after
  Settings. Caption, geometry, no-page-error and closed-request assertions pass.
  Each context makes exactly five synthetic Research run requests; the fifth
  is `history-b / anthropic / claude-sonnet-5 / medium`. Neither direction's
  incomplete state dispatches a run.

Directly inspected these new images for both directions' pending and completed
states, correct captions and coherent layout:

- `zh-Hant-390-shell-anthropic-incomplete-after-settings.png`
- `zh-Hant-390-shell-anthropic-complete-after-settings.png`
- `en-1280-shell-openai-reverse-incomplete-after-settings.png`
- `en-1280-shell-openai-reverse-complete-after-settings.png`

The reported Traditional Chinese mobile case now has OpenAI/Sol selected,
effort required, no prior Claude composer caption/quota, and disabled Send.
After effort completes, it shows ChatGPT auth/quota. The reverse direction
suppresses prior ChatGPT captions and restores Claude auth/quota on completion.
Provider buttons retain their correct per-provider labels throughout.

### Preservation And Handoff

SHA-256 comparison before and after the new browser run confirmed all 72
`browser-verified` screenshots and its results JSON are unchanged. Its results
hash remains `24e1c93a1b0c5b2a5011e77a41bc848a039a4d56011bfc2470879ed624249348`;
the sorted path/hash manifest hash remains
`a6bac0b2c3568c0b4c02e47f04b3dc447e1f3dabeffb7f39fce38a0247391cd6`.
The original 64 `tmp/task-3-ui` images and results also still match the
controller's archived hashes. No controller-owned JSON/docs were changed.

All worker Vitest, typecheck, build and browser commands have completed; a
post-run process check found no worker test/browser/Vite/Chromium processes.
No backend rerun, full-suite duplication, provider call, App restart, subagent,
merge, push or installation occurred. The index is empty after the scoped
commit; only controller-owned uncommitted changes remain. The caption concern
is resolved, not deferred. The existing Vite chunk warning and controller-owned
complete suites/scoped re-review remain the only handoff items for this work.
