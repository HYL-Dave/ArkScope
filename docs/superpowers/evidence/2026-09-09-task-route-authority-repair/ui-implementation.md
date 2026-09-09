# Task 3 Final Report

Status: DONE

Worktree: `/tmp/arkscope-task-route-authority`
Branch: `codex/task-route-authority`
Base: `84ff0cd306d40b8b997512b3615fb08ab8ccf2e6`
Implementation commit: `c5146a9a581f7e81ee5890a109e3f9ae81047ce9`
Commit subject: `fix(ui): honor task routes and show execution provenance`
Commit scope: 21 owned frontend/test/harness files. Local commit used `core.hooksPath=/dev/null` and `commit.gpgsign=false` to avoid unrequested hook execution or signing-credential access. No merge or push.

## Scope and Authorization

Implemented the Task 3 final brief and its reviewed backend handoff. Read only the Task 3 Interface section of the Task 2 report for response details, not the full plan or session history.

All implementation changes are frontend-only. No backend code/tests, provider execution, production backend/App restart, production stores, credentials, private config, or `.env` access. No dependency installation, merge, push, helper, subagent, or reviewer process. The existing dependency link was used. Independent review remains controller-owned.

Controller-owned Priority Map, repair plan, and evidence README were not edited or staged. The reference settings browser harness was read-only. This scratch report and `tmp/task-3-ui/` outputs are not included in the implementation commit.

## Implemented Contracts

- Card generation no longer sends an unsolicited `provider: "anthropic"`; provider/model/effort route authority remains backend Settings.
- `ExecutionReceipt` is a readonly four-field DTO: `provider`, `model`, `effort`, `auth_mode`. Provider/model/effort accept strings or legacy nulls. Auth accepts only `api_key`, `chatgpt_oauth`, `claude_code_oauth`, or null.
- Generation, detail, list, and translation adapters validate present receipts as closed objects. Invalid/null/array receipts, extra credential fields, non-string tuple fields, and invalid auth values become `ApiError` with code `card_payload_invalid` and null diagnostic. They are not silently rendered as unknown or replaced by Settings.
- Older payloads without the field preserve only known historical top-level provider/model; effort/auth stay unknown. Custom model IDs are retained verbatim without an invented length restriction.
- `translateCard(runId, lang, runtime, options?)` preserves the existing third runtime/timeout argument. Only an explicit `{ refresh: true }` option adds the request flag. Normal language selection omits it.
- `CardTranslationResult` distinguishes an explicit `no_op: true`, null receipt, `cached: false`, partial-card response from an actual translation. The UI retains the original content and does not claim a translation receipt for no-op responses.
- Original and translated cards use separate compact source lines. Missing fields are localized as unknown. Auth labels use existing shared i18n presentation; no credential identity, key, token, or hash is added to the UI.
- The retranslation icon has the existing tooltip/accessibility semantics and disabled/busy state. Old translation content and receipt survive pending/error states; retry remains explicit refresh. Switching away and back reuses the old result without a refresh request.
- Research selects `catalog.routes.ai_research` for new operations, including existing-thread next turns, unless the user explicitly selected in the currently open conversation. Historical metadata and global localStorage preferences are not execution authority.
- Current overrides survive successful first sends and later turns, including the current protocol's client UUID/server acknowledgment. Reset occurs on new/open-other/current-delete actions, not server acknowledgment or same-conversation reopening. No reducer or backend identity protocol was changed.
- Historical Research messages retain their original model/effort metadata. Existing custom-model admission, retired-model rejection, effort validation, SDK availability, model/auth/entitlement reasons, Spark task restrictions, and Fable OAuth block remain intact.
- Research provider toggles now show provider plus auth/rejection reason only. The actual selected model remains in the existing model dropdown/header. A stale `/query/providers.model` or first eligible catalog model cannot appear as a contradictory toggle model. Inspection showed the old label came from `firstReady`, not directly from the query response; both stale-query and differing-selected-route fixtures are covered.
- Lifecycle previous-run source is read only from that run's execution. Next-run confirmation separately shows the complete current preflight provider/model/effort/auth tuple. Existing consent, limits, policy, and action behavior were not changed.

## Changed Files

- `apps/arkscope-web/src/api.ts`: receipt DTO/validation, legacy adaptation, no-op response discrimination, explicit refresh request option.
- `apps/arkscope-web/src/ExecutionSource.tsx`: shared compact source rendering.
- `apps/arkscope-web/src/AICard.tsx`: generation authority, original/translation source state, refresh/no-op/preservation flow.
- `apps/arkscope-web/src/Research.tsx`, `researchSelection.ts`: Settings/current-conversation authority and provider/auth-only toggle presentation.
- `apps/arkscope-web/src/lifecycle/InvestigationView.tsx`: previous execution versus next preflight source.
- `apps/arkscope-web/src/styles.css`: source wrapping, stable card toolbar controls, and readable saved-card modal alerts. No Settings layout or unrelated limits changes.
- `apps/arkscope-web/src/i18n/resources/{en,zh-Hant}/{common,explore}.ts`: source labels and retranslation/no-op copy.
- Tests: `AICard.test.tsx`, new `CardExecutionApi.test.ts`, `ResearchWorkspace.test.tsx`, `ResearchShellNavigation.test.tsx`, `researchSelection.test.ts`, `lifecycle/InvestigationView.test.tsx`, `i18n/resources.test.ts`.
- Owned evidence harness: `docs/superpowers/evidence/2026-09-09-task-route-authority-repair/task-3-browser.py`, `task-3-preview.tsx`, `task-3-vite.mjs`.

## RED Evidence

Commands below ran from `apps/arkscope-web` in the requested clean, network-disabled environment. No dependencies were installed.

Initial card/API/lifecycle RED: 19 failed, 25 passed, 44 tests across 3 files.

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only src/AICard.test.tsx src/CardExecutionApi.test.ts src/lifecycle/InvestigationView.test.tsx
```

Initial Research authority RED: 9 failed, 53 passed, 62 tests across 2 files.

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only src/researchSelection.test.ts src/ResearchWorkspace.test.tsx
```

Additional focused RED controls used the same exact clean command prefix, with these file arguments:

| Files | Observed RED | Correction |
| --- | --- | --- |
| `src/CardExecutionApi.test.ts` | 4 failed / 10 passed | Reject auth arrays instead of string coercion. |
| `src/CardExecutionApi.test.ts` | 4 failed / 14 passed | Preserve long custom model IDs; remove invented receipt length cap. |
| `src/researchSelection.test.ts src/CardExecutionApi.test.ts` | 1 failed / 44 passed | Invalid explicit choice must not silently fall back to Settings. |
| `src/AICard.test.tsx` | 1 failed / 16 passed | Stable language label while explicit refresh is pending. |
| `src/ResearchWorkspace.test.tsx` | 2 failed / 40 passed | Both locales reject model names in provider toggles beside a different actual selected route. |

The first full frontend integration run found 5 failures / 1723 passes: obsolete thread-selection-fetch assumptions, locale inventory updates, and the new source helper's dynamic i18n lookup. These were corrected using the new authority contract and static i18n selectors. A subsequent label-change integration found one obsolete shell-test selector (1 failed / 148 passed); it now selects the provider control semantically. A test-only optional `effective.providers` type error was also fixed before final typecheck.

Browser RED controls exposed cramped card toolbar controls and an unreadable saved-modal alert column. The enhanced saved-modal readability assertion failed with a 102px prose column even at desktop width. Card-scoped layout corrections and accurate fixture containment now pass desktop/mobile checks. Fixture selector issues, missing terminal events, and inconsistent fixture timestamps were corrected in the owned harness; those earlier screenshots are not claimed as successful-run evidence.

## Final GREEN Evidence

Focused frontend: 149 passed, 9 files, exit 0, 2.81 seconds.

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only src/AICard.test.tsx src/CardExecutionApi.test.ts src/lifecycle/InvestigationView.test.tsx src/researchSelection.test.ts src/ResearchWorkspace.test.tsx src/CardApiTimeout.test.ts src/ResearchShellNavigation.test.tsx src/i18n/resources.test.ts src/i18n/foundationBoundaries.test.ts
```

Full frontend: 1739 passed, 125 files, no failures, exit 0, 11.59 seconds.

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/vitest/vitest.mjs run --silent=passed-only
```

Typecheck: exit 0, no diagnostics.

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node ../../node_modules/typescript/bin/tsc --noEmit
```

Build: exit 0, Vite 5.4.21, 2209 modules, 2.59 seconds. Built JS 1162.66 kB / gzip 350.55 kB; CSS 99.45 kB / gzip 16.51 kB. Used the repository Vite configuration with `envFile: false`, so no `.env` file is loaded. Generated `dist/` is not staged.

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 /usr/bin/unshare --user --map-root-user --net /home/hyl/.nvm/versions/node/v22.14.0/bin/node --input-type=module -e 'import { build } from "vite"; await build({ envFile: false });'
```

`git diff --check` and `git diff --cached --check`: exit 0. Final staged-path review excluded backend files, controller docs, the scratch report, screenshots, and generated build output. Post-commit `git status --short --untracked-files=all` lists only controller-owned Priority Map, repair plan, and evidence README; all owned implementation/harness changes are committed. This scratch report remains untracked under the existing ignored `.superpowers` directory.

## Browser Evidence

Run from `/tmp/arkscope-task-route-authority`:

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin HOME=/tmp LANG=C.UTF-8 PLAYWRIGHT_BROWSERS_PATH=/home/hyl/.cache/ms-playwright /usr/bin/unshare --user --map-root-user --net /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-09-task-route-authority-repair/task-3-browser.py
```

Final result: exit 0, 4 contexts, 64 screenshots. Locales: `en`, `zh-Hant`. Viewports: desktop 1280x960 and mobile 390x844. Each context recorded 38 fully synthetic API requests, 16 screenshots/layout checks, zero page errors, zero external/unexpected requests, zero checked text overflow, and zero narrow-prose failures.

The harness mounts actual AICardTab, CardModal, ResearchView, SettingsView, and LifecycleView components with application styles. Vite runs only on isolated loopback port 8467 with `.env` loading disabled. The network namespace has no external network; browser interception also denies external and unexpected API requests. Browser contexts are fresh, extensions disabled, service workers blocked, and fixtures use no real accounts. No provider request is forwarded to any backend.

Verified workflow coverage:

- Generation omits provider/model/effort overrides; original request is OpenAI Luna / xhigh / API key.
- Cached translation is separately Spark / high / ChatGPT subscription sign-in, with no refresh flag on normal toggles and no repeated request after toggling away/back.
- Explicit refresh pending and auth-rejected failure retain the old content/receipt; retry sends `refresh: true` and updates only after success. Saved-modal failure also preserves the all-unknown legacy translation source.
- Older missing-receipt saved cards retain `openai / gpt-5.4-mini`; only effort/auth are unknown. Legacy translation metadata is entirely unknown. Malformed present receipt produces a safe alert; partial no-op retains original prose without a translation source.
- Existing Research history remains `gpt-5.4-mini` while Settings initially selects Sol / low. Actual Settings route edit/save changes Research to Sonnet / medium without changing other task routes.
- Explicit new-conversation override selects Sol / high for two successful turns with the same server-acknowledged thread ID. Opening another conversation resets to Sonnet / medium. Provider toggles show auth only, independent of stale query models. Synthetic `done` events now produce completed answer bubbles and consistent completed progress with nonnegative elapsed times.
- Previous Lifecycle result remains OpenAI / gpt-5.4-mini / low / API key; next confirmation is Anthropic / claude-sonnet-5 / xhigh / Claude subscription sign-in. No investigation POST occurs before consent.

Output directory: `/tmp/arkscope-task-route-authority/tmp/task-3-ui/`
Machine-readable record: `/tmp/arkscope-task-route-authority/tmp/task-3-ui/results.json`
Isolated Vite log: `/tmp/arkscope-task-route-authority/tmp/task-3-ui/vite.log`

Screenshot pattern: `{locale}-{width}-{scene}.png`. The final 16 scenes in each locale/width are:

`card-original`, `card-cached`, `card-refresh-pending`, `card-refresh-failed`, `card-refreshed`, `card-legacy-saved`, `card-saved-refresh-failed`, `card-malformed-safe-error`, `card-no-op`, `research-openai-settings`, `settings-research-route`, `research-anthropic-settings`, `research-current-override`, `research-open-other-reset`, `lifecycle-previous`, `lifecycle-next-confirmation`.

Representative final files for controller inspection:

- `/tmp/arkscope-task-route-authority/tmp/task-3-ui/zh-Hant-1280-research-current-override.png`
- `/tmp/arkscope-task-route-authority/tmp/task-3-ui/en-390-card-saved-refresh-failed.png`
- `/tmp/arkscope-task-route-authority/tmp/task-3-ui/zh-Hant-390-card-refresh-failed.png`
- `/tmp/arkscope-task-route-authority/tmp/task-3-ui/zh-Hant-390-card-legacy-saved.png`
- `/tmp/arkscope-task-route-authority/tmp/task-3-ui/en-1280-card-refresh-pending.png`
- `/tmp/arkscope-task-route-authority/tmp/task-3-ui/en-390-lifecycle-next-confirmation.png`

These representative final files were also visually inspected after regeneration, in addition to the automated assertions. The earlier standalone-card containment, missing-done-event, and negative-elapsed screenshots were superseded by the final run.

Cleanup: harness closes all browser contexts/browser and terminates/waits for its isolated Vite process group in `finally`. All final Vitest, typecheck, and build sessions exited. `ss -ltn 'sport = :8467'` showed no listener; targeted `pgrep` for the owned browser/Vite/Playwright driver found no processes.

## Self-Review and Concerns

- Reviewed the changed API boundary, source rendering, refresh transitions, Research conversation resets/default/override rules, provider presentation, and lifecycle preflight/history distinction against the brief. No unresolved Task 3 blocker identified.
- Receipt parsing deliberately fails closed only for the added contract and response envelope; it does not redesign validation of the pre-existing ResultCard prose schema. Unknown historical metadata never consults Settings.
- Existing Research selection compatibility/storage helpers remain exported for legacy callers/tests, but the execution resolver and UI no longer read/write global preferences as authority. No unrelated cleanup was included.
- No backend/model/auth/entitlement gate was loosened. Positive custom-model and negative effort/retirement/Spark/subscription/Fable gate controls pass in the frontend suite. This report does not claim live provider or production-account verification.
- The build retains the pre-existing Vite warning for chunks over 500 kB. Chunk splitting is outside Task 3 and was not changed.
- Backend integration and the previously reported old custom-effort backend-test correction remain controller-owned; no backend work was performed here.
- Independent implementation review and evidence archival are pending controller assignment, as required. Scratch report and screenshots remain outside the implementation commit.
