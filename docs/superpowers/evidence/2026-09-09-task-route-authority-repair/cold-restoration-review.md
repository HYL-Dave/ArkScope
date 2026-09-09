ADDRESSED: Prior P2, "Initial Picker Edits Discard the Saved Conversation Before Hydration" ([prior report:90](/tmp/arkscope-task-route-authority/docs/superpowers/evidence/2026-09-09-task-route-authority-repair/final-fix-review.md:90), finding through line 126).

At the reviewed head, [Research.tsx:224](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:224) seeds the existing App-owned record from the saved session ID before picker or draft edits and distinguishes `restoring`, `ready`, and `blank`. Completed selection changes preserve both target and status at [Research.tsx:317](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:317); incomplete model/provider changes do likewise at lines 812-845. Successful, sequence-current transcript hydration marks the latest record ready without replacing intervening draft/selection edits at [Research.tsx:358](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:358). The submit handler, failed-turn retry handler, retry visibility, and Send button all gate on restoration (lines 593-602, 848-857, 1025, 1211-1216). Picker edits no longer turn unresolved restoration into an explicit blank conversation.

The desired-behavior owner at [ResearchWorkspace.test.tsx:525](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/ResearchWorkspace.test.tsx:525) mounts the real App in StrictMode with only the saved ID, separately delays list and messages, and asserts retained input, disabled Send/no POST, the original eventual request ID, exact selected tuple, and unchanged historical content/provenance. Its 18 cases cover both provider directions, no-edit/complete/incomplete-custom selection, and no navigation/Home/Settings. All 18 are present and passing in the exact-head focused artifact. The prior report-local diagnostic was neither executed nor rewritten.

## New Fix-Diff Breakage

No new reportable regression found in the three-commit correction, including the deletion completion. No unresolved severity-bearing finding is added by this review.

- **Failure and recovery:** Initial list failure is forwarded only for the current initial query at [ResearchHistoryDrawer.tsx:302](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/ResearchHistoryDrawer.tsx:302), with Research checking current restoration intent at lines 1246-1249. Missing/detail/messages failures leave the intended ID and draft intact and submission blocked. [Research.tsx:422](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:422) does not fall back from a missing saved target to the first unrelated row. Retry resolves that same ID, or reloads history when no target is known (lines 445-455); New and explicit History selection remain available. The 12 failure/recovery and four unresolved-no-ID owners assert actual recovery and POST targets, including clearing the old error after successful empty-history refresh.
- **Explicit New and other-thread navigation:** [Research.tsx:653](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:653) invalidates hydration/submission generations, clears the intended selection and active reducer state, and retains input. Initial-list callbacks cannot override blank intent; old detail/message results cannot pass the generation checks. Explicit other-thread selection resets route choice as before, while selecting the same thread retains it. Seven delayed-response owners at [ResearchWorkspace.test.tsx:675](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/ResearchWorkspace.test.tsx:675) exercise New/open-other/delete-current/delete-other controls. Existing warm-remount, incomplete-effort, first-ID, and current-only selection controls at lines 837, 887, 926, and 1007 remain relevant and are included in the focused result.
- **Delayed A deletion after B was hydrated:** [Research.tsx:691](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:691) compares the deletion with the intended target, invalidates pending callbacks, and now dispatches `newThread` before deleting only A. [researchReducer.ts:420](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/researchReducer.ts:420) clears the active ID/pending state but preserves thread/message collections; the following `deleteThread` removes only its named ID. Thus the next POST cannot inherit B, and B's history is not deleted. Deleting B or C instead leaves intended A restoring until A resolves. The three owners at [ResearchShellNavigation.test.tsx:510](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/ResearchShellNavigation.test.tsx:510) assert retained input, late-response rejection/preservation, exact tuple, and fresh-versus-A request IDs. The recorded RED contains the concrete wrong `thread-b` POST; all three cases pass in the final focused artifact.
- **Context and provenance:** The two added synthetic backend owners at [test_task_runtime_binding.py:120](/tmp/arkscope-task-route-authority/tests/test_task_runtime_binding.py:120) capture the existing managed execution adapter boundary, asserting prior question/answer, no duplicated new question, original thread ID, exact new tuple, and unchanged prior message records. The existing caller passes captured history through scheduling at `src/api/routes/research.py:406` and into the adapter at `src/research_run_manager.py:128`. No backend runtime, provider policy, persistence schema, credential behavior, or cache feature changed in this package.
- **Caption/capture follow-up:** Unknown titles use existing loading/failure translations at [Research.tsx:965](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:965); known titles and deliberate New retain their existing presentation. The scrolling/rectangle checks at [task-3-browser.py:270](/tmp/arkscope-task-route-authority/docs/superpowers/evidence/2026-09-09-task-route-authority-repair/task-3-browser.py:270) are browser-harness changes, not runtime scrolling changes. The exact-head images inspected below show the corrected content in frame.

## Out-Of-Scope Observations

None reported. Prior P1/refusal work, unrelated branch behavior, and cache/cost-hint research were not reopened. This is not a whole-branch review or a review of controller-owned documentation changes.

## Checks

### Identity And Preservation

- Worktree: `/tmp/arkscope-task-route-authority` only.
- Base: `9c0d9f5cd7f7c1131eca509f5548a3e03189360f`.
- Head: `b669d45519244bf14bfafa882c8ab3b8946996d2`, confirmed at entry and before report creation.
- Commits: `c13080e4f63ca09882f3503876ca0d0299432a69`, `54148cfc6f68a4e89191ac4c9c6728add382f71f`, `b669d45519244bf14bfafa882c8ab3b8946996d2`.
- Supplied package read once: `.superpowers/sdd/2026-09-09-task-route-authority-repair/cold-restoration-review.diff`; SHA256 `033b2361aa43f8a47dc0f67f2310d129c5e13b262294b0eb41eba99d8a719ad5`. Git independently confirms the package's seven changed paths: two production frontend files, two frontend test files, browser harness/preview, and one backend test file.
- `git diff --check <base> <head>` exited 0. Working copies of the seven scoped files and backend `src/`/`tests/` matched the frozen head. `git diff --exit-code c13080e4 b669d455 -- src tests` exited 0, supporting the stated backend snapshot continuity.
- Prior canonical report SHA256 remains `1e643494cc825d3a841982772a7bacb9ac7c2e13ac47c4c3e3a9c80d150794bf`.

### Artifact Readback

These are inspected implementer/controller results, not reviewer suite reruns. JUnit was parsed structurally with the installed JSDOM XML parser; JSON with `JSON.parse`, using Node in the report's clean `env -i ... unshare --user --map-root-user --net` environment. Counts below are test cases, not individual soft-assertion failure elements.

| Artifact | Verified recorded result | Snapshot boundary |
| --- | --- | --- |
| `tmp/cold-restoration/frontend-red-verified.xml` | 29 failed / 238 passed | Behavioral RED before restoration correction |
| `tmp/cold-restoration/frontend-delete-target-red.xml` | 1 failed / 2 passed / 5 skipped; A case reports wrong B title and `thread-b` POST | Before deletion completion |
| `tmp/cold-restoration/frontend-delete-target-final-green.xml` | 274 passed / 11 files; zero failures/errors/skips | `b669d455`; includes 18 cold, 12 failure/recovery, four no-ID recovery, seven stale-response, and three delayed-deletion cases |
| `tmp/cold-restoration/frontend-full-green.xml` | 1822 passed / 125 files; zero failures/errors/skips | `c13080e4`, not the latest full-suite result |
| `tmp/cold-restoration/backend-context-green.xml` | 252 passed; both new context owners present | Backend/test snapshot unchanged by the two follow-ups |
| `tmp/cold-restoration/controller-backend-full.xml` | 7593 passed / 12 skipped; zero failures/errors | Controller-run unchanged backend/test snapshot |
| `tmp/cold-restoration-ui/attempt-5/results.json` | 56 contexts / 176 screenshots / 64 answer viewport checks | `54148cfc`, superseded for current-head browser acceptance |
| `tmp/cold-restoration-ui/controller-final/results.json` | 56 contexts / 176 screenshots / 64 answer viewport checks; no recorded errors/overflow | Controller supplement reports exit 0 at frozen `b669d455` |

Relevant artifact SHA256 values independently match the handoff:

- Final focused frontend: `cb894e725e2eae3603672bfe29e8f166dbf3b81495c97323c215a6f532fbfa97`.
- Deletion RED: `b799a819c3d06581758794967ff1ff3b41f1c61fbc6898f6678e5347b21bad1d`.
- Earlier full frontend: `1b9bfb7bd23ae02df5711181b44fbce3a81196de8dc59d68ce83d00d089e959d`.
- Focused backend: `07e02957a5b6b830aa02601dd87f24081938f72d5b6305f785a2f06cb0f0b128`.
- Controller full backend: `db0a126208d5807960dc9371b6884660f3a74f414c13f7d2cd3b9897bcd93db1`.
- Attempt-5 browser: `e1eca61bd10c3c35ea8b4dd57333d2fa6e8682060b05b4a08095296820a56250`.
- Exact-head controller browser: `368e7db821b39582968d0098794309ffcecab88c1ea172c87625794376010cd7`.

For both browser result files, readback independently checked screenshot existence, both locales/providers/widths, seven cold cases, empty recorded error/overflow arrays, all 64 answer/provenance rectangles against transcript/page bounds, original saved IDs and inverse provider direction for restored requests, fresh IDs plus first-ID continuity for New, and no historical-selection endpoint requests. I also viewed these exact-head `controller-final/` images:

- `en-390-shell-openai-cold-complete-completed-exact-context.png`: new answer and Anthropic/low provenance in the transcript viewport.
- `zh-Hant-390-shell-anthropic-cold-failed-missing-blocked.png`: explicit missing-target failure, Retry/New/History recovery, retained draft and OpenAI choice, disabled Send.
- `zh-Hant-1280-shell-anthropic-cold-incomplete-completed-exact-context.png`: completed custom OpenAI choice, new answer/provenance, and unchanged historical provenance in frame.

Typecheck/build exit 0 and the existing >500 kB chunk warning are implementer-reported results; they were not independently rerun. The controller's full frontend rerun and both inverse mutations remain pending. No mutation effectiveness is claimed from the existing GREEN artifacts.

Static tracing and available desired-behavior evidence left no concrete doubt requiring a new diagnostic. No Vitest/pytest/browser/build suite was run by this reviewer, no diagnostic file was created or changed, and the intentionally vulnerable prior diagnostic was not run. No runtime, index, HEAD, production data, prior evidence, provider state, installation, credentials, or App process was changed. Only this requested report was written, with `apply_patch`; controller-owned changes were left untouched.

## Overall Verdict

PASS for this one scoped re-review: the prior cold-restoration P2 is ADDRESSED, and no new fix-diff breakage was found through the deletion completion at `b669d455`. This does not approve the whole branch or replace the controller-owned inverse-mutation/full-frontend checks.

All reviewer-owned sessions are stopped: every inspection/artifact-readback command exited; no test, browser, development server, or subagent session remains running.
