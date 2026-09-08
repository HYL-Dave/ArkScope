# Lifecycle Automation Modes Verification

Worktree: `/tmp/arkscope-tracking-history-provenance`
Branch: `codex/automation-modes-gpt6`
All commands below ran from that worktree. No production code was edited before RED.

## Baselines

```sh
python -m pytest -q tests/test_security_lifecycle_automation_config.py tests/test_security_lifecycle_automation_scheduler.py tests/test_security_lifecycle_routes.py
```

Output: `236 passed in 19.70s` (exit 0).

```sh
npm test --workspace apps/arkscope-web -- src/settings/DataStorageSection.test.tsx src/ProviderSection.test.ts src/LifecycleAutomationApi.test.ts src/i18n/resources.test.ts
```

Output: `Test Files 4 passed (4); Tests 73 passed (73)` (exit 0).

```sh
python -m pytest -q tests/test_data_scheduler.py tests/test_ticker_identity_scheduler.py tests/test_security_lifecycle_automation_worker.py
```

Output: `255 passed in 14.70s` (exit 0).

## RED

```sh
python -m pytest -q tests/test_security_lifecycle_automation_config.py tests/test_security_lifecycle_routes.py tests/test_data_scheduler.py
```

Output: `3 failed, 218 passed in 14.67s` (exit 1).
All three failures exposed the legacy disabled/auto-apply state authorizing mutations:

- `test_legacy_settings_are_preserved_but_only_automatic_authorizes_mutation[false-true-False-False]`: `assert True is False`.
- `test_manual_run_bypasses_disabled_schedule_but_uses_batch_and_live_mutation_gate`: `assert mutation_allowed() is False`, received True.
- `test_legacy_disabled_auto_apply_blocks_automation_but_keeps_attended_runner`: `assert mutation_allowed() is False`, received True.

```sh
npm test --workspace apps/arkscope-web -- src/settings/DataStorageSection.test.tsx src/ProviderSection.test.ts src/LifecycleAutomationApi.test.ts src/i18n/resources.test.ts
```

Output: `Test Files 3 failed | 1 passed (4); Tests 16 failed | 64 passed (80)` (exit 1).
Failures: missing Automation mode selector, missing new translation keys, provider count text still rendered, and persisted interval 17 displayed as 5.

## GREEN

```sh
python -m pytest -q tests/test_security_lifecycle_automation_config.py tests/test_security_lifecycle_routes.py tests/test_data_scheduler.py
```

Output: `221 passed in 14.25s` (exit 0).

```sh
npm test --workspace apps/arkscope-web -- src/settings/DataStorageSection.test.tsx src/ProviderSection.test.ts src/LifecycleAutomationApi.test.ts src/i18n/resources.test.ts
```

Output: `Test Files 4 passed (4); Tests 80 passed (80)` (exit 0).
Before the final GREEN run, two stale test expectations were adjusted: retired UI copy and the translation inventory's net increase of one key. No behavior assertions were weakened.

```sh
python -m pytest -q tests/test_security_lifecycle_automation_scheduler.py tests/test_ticker_identity_scheduler.py tests/test_security_lifecycle_automation_worker.py
```

Output: `273 passed in 21.85s` (exit 0).

Final combined backend verification, including unchanged deterministic decision-policy gates:

```sh
python -m pytest -q tests/test_security_lifecycle_automation_config.py tests/test_security_lifecycle_routes.py tests/test_data_scheduler.py tests/test_security_lifecycle_automation_scheduler.py tests/test_ticker_identity_scheduler.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_decision_policy.py
```

Output: `545 passed in 34.10s` (exit 0).

```sh
npm run typecheck --workspace apps/arkscope-web
npm run check:i18n-literals --workspace apps/arkscope-web
git diff --check
```

Each exited 0. Typecheck and diff check emitted no errors. Literal scanner reported `candidateCount: 37, signatureCount: 20, debtSignatureCount: 0, allowlistCount: 20`.

## Legacy Behavior

The persisted boolean API remains unchanged. No migration or read-time normalization.

| enabled | apply_profile_transitions | UI mode | Automatic mutation authority |
| --- | --- | --- | --- |
| false | false | off | false |
| true | false | check_only | false |
| true | true | automatic | true, subject to existing deterministic delisting gates |
| false | true | off with visible legacy-conflict diagnostic | false |

Selecting a mode writes a consistent pair. Interval-only edits preserve both flags, the hidden batch limit, and the conflict diagnostic. Non-preset persisted intervals remain visible. Attended approved transitions retain their independent authority; rename, LLM, and human gates were not changed.

## Owned Changed Paths

Paths relative to the worktree above:

- `src/service/security_lifecycle_automation_config.py`
- `tests/test_security_lifecycle_automation_config.py`
- `tests/test_security_lifecycle_routes.py`
- `tests/test_data_scheduler.py`
- `apps/arkscope-web/src/settings/DataStorageSection.tsx`
- `apps/arkscope-web/src/settings/DataStorageSection.test.tsx`
- `apps/arkscope-web/src/settings/ProviderSection.tsx`
- `apps/arkscope-web/src/ProviderSection.test.ts`
- `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- `apps/arkscope-web/src/i18n/resources.test.ts`

ProviderSection changes remove exactly the two modelCount renderings. Source, time, credential/error status, and filtering remain untouched.

No live profile writes, live provider calls, App restart, migration, commit, merge, or push. Parent-owned model/card/GPT6 files were not edited. Browser/live-App verification was not performed.

## Follow-Up: Segmented Radios and Scheduler Consumer

Additional changed paths, relative to the same worktree:

- `apps/arkscope-web/src/settings/DataStorageSection.tsx`: native mutually exclusive radios, matching existing provider-toggle styling; interval remains a select. Translation lookup uses explicit keys, not a dynamic selector.
- `apps/arkscope-web/src/styles.css`: lifecycle-only equal three-column responsive tracks, bounded width, wrapping copy, checked/focus/disabled styling.
- `apps/arkscope-web/src/settings/DataStorageSection.test.tsx`: bilingual radio interaction, disabled/save behavior, repeat-click no-op, legacy states, and computed CSS track/wrapping checks at narrow/wide container widths. CSSOM tests do not claim browser geometry validation.
- `tests/test_data_scheduler.py`: eight real temporary-database cases through `tick_once`, the due-transition runner, and transition execution. All four legacy boolean pairs are crossed with automation-policy and attended-user approval authority. Checks persisted transition status, identity links, and execution attempts.

No follow-up backend production changes were required. Existing persisted automation-approved transitions remain pending in off/check-only; the automatic-mode positive control applies the same valid transition. Attended transitions apply in every mode. The test fixture uses an already-approved legacy continuation, not new rename approval.

### Follow-Up Baselines

```sh
npm test --workspace apps/arkscope-web -- src/settings/DataStorageSection.test.tsx src/SettingsCss.test.ts
```

Output: `Test Files 2 passed (2); Tests 38 passed (38)` (exit 0).

```sh
env PYTHONPATH=/tmp/arkscope-gpt6-reviewed-sdk python -m pytest -q tests/test_data_scheduler.py tests/test_ticker_identity_scheduler.py
```

Output: `181 passed in 7.20s` (exit 0). No dependency pins were edited.

### Follow-Up RED

```sh
npm test --workspace apps/arkscope-web -- src/settings/DataStorageSection.test.tsx src/SettingsCss.test.ts
```

Output after correcting test stylesheet loading: `Test Files 1 failed | 1 passed (2); Tests 16 failed | 26 passed (42)` (exit 1). Radio groups and segmented tracks were absent in the select implementation. The first CSS test harness used a Vite-rewritten asset URL and then an empty CSS import; loading the file via Node filesystem APIs corrected the harness without changing production behavior.

Scheduler-consumer mutation check: restore the old unsafe gate only in this test process's memory, without editing production files:

```sh
env PYTHONPATH=/tmp/arkscope-gpt6-reviewed-sdk python -c 'import pytest; from src.service.security_lifecycle_automation_config import SecurityLifecycleAutomationConfigState as State; State.effective_apply_profile_transitions = property(lambda self: bool(self.valid and self.config and self.config.apply_profile_transitions)); raise SystemExit(pytest.main(["-q", "tests/test_data_scheduler.py", "-k", "tick_modes_gate"]))'
```

Output: `1 failed, 7 passed, 119 deselected in 1.92s` (exit 1). The legacy `false/true` automation-policy case persisted `applied` instead of the expected `approved`. All attended cases and the automatic positive control passed, proving the regression test catches an actual consumer-side mutation, not merely a config property.

### Follow-Up GREEN

```sh
npm test --workspace apps/arkscope-web -- src/settings/DataStorageSection.test.tsx src/SettingsCss.test.ts
```

Output: `Test Files 2 passed (2); Tests 42 passed (42)` (exit 0).

```sh
env PYTHONPATH=/tmp/arkscope-gpt6-reviewed-sdk python -m pytest -q tests/test_data_scheduler.py -k tick_modes_gate
```

Output: `8 passed, 119 deselected in 2.04s` (exit 0).

```sh
env PYTHONPATH=/tmp/arkscope-gpt6-reviewed-sdk python -m pytest -q tests/test_security_lifecycle_automation_config.py tests/test_security_lifecycle_routes.py tests/test_data_scheduler.py tests/test_security_lifecycle_automation_scheduler.py tests/test_ticker_identity_scheduler.py tests/test_security_lifecycle_automation_worker.py tests/test_security_lifecycle_decision_policy.py
```

Output: `553 passed in 43.59s` (exit 0).

```sh
npm test --workspace apps/arkscope-web -- src/settings/DataStorageSection.test.tsx src/SettingsCss.test.ts src/ProviderSection.test.ts src/LifecycleAutomationApi.test.ts src/i18n/resources.test.ts
```

Output after explicit translation-key correction: `Test Files 5 passed (5); Tests 94 passed (94)` (exit 0).

### Scanner Correction

The parent's `/tmp/arkscope-automation-gpt6-frontend.log` lines 98 onward reported the same dynamic translation lookup found by the local scanner: `$.dataStorage.lifecycle.automation.modes[mode]`. It is replaced with three explicit key lookups. No scanner exemptions or inventory changes were added for this correction.

```sh
npm run check:i18n-literals --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
git diff --check
```

Each exited 0 after correction. Scanner output remains `candidateCount: 37, signatureCount: 20, debtSignatureCount: 0, allowlistCount: 20`.

Browser work remains parent-owned; no browser actions, live profile writes, provider calls, dependency pin edits, or commits were performed in this follow-up. Automatic-mode wording remains unchanged pending the parent's screenshot review.

Final focused rerun including the exact failing foundation boundary and scanner tests:

```sh
npm test --workspace apps/arkscope-web -- src/i18n/foundationBoundaries.test.ts src/i18n/visibleLiteralScanner.test.ts src/settings/DataStorageSection.test.tsx src/SettingsCss.test.ts src/ProviderSection.test.ts src/LifecycleAutomationApi.test.ts src/i18n/resources.test.ts
```

Output: `Test Files 7 passed (7); Tests 123 passed (123)` (exit 0). Duration 9.52s. The accompanying fresh scanner and typecheck commands both exited 0.

## Follow-Up: Clicking Already-Selected Off

Changed only `apps/arkscope-web/src/settings/DataStorageSection.tsx` and its `DataStorageSection.test.tsx` in this follow-up.

Native DOM click tests activate the visible Off label's span with `.click()`, forwarding the label's native activation to its already-checked radio. Tests do not call a React handler or synthesize a change event. Both English and Traditional Chinese cover legacy `false/true` and ordinary `false/false` settings.

The conflict-only `onClick` path writes `enabled=false/apply_profile_transitions=false` once. Ordinary selected Off clicks are no-ops. Other mode switches still use `onChange` and write once, including a subsequent switch back to Off. Initial reads and interval-only edits retain their existing no-normalization behavior; internal batch limits remain preserved.

### Click Regression RED/GREEN

```sh
npm test --workspace apps/arkscope-web -- src/settings/DataStorageSection.test.tsx
```

- Baseline: `Test Files 1 passed (1); Tests 32 passed (32)` (exit 0).
- RED: `Tests 2 failed | 34 passed (36)` (exit 1). The two legacy-state tests expected one write after clicking checked Off but observed zero. Both ordinary-Off positive controls passed.
- GREEN: `Test Files 1 passed (1); Tests 36 passed (36)` (exit 0), duration 2.34s.

The tests also verify diagnostic dismissal after the successful explicit save, no repeat write on another Off click, and exactly one write per subsequent check-only/automatic/Off switch.

```sh
npm run check:i18n-literals --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
git diff --check
```

All exited 0. Scanner debt remains zero. No backend production changes, browser actions, provider calls, live profile writes, dependency edits, or commits.

Final expanded click-regression verification:

```sh
npm test --workspace apps/arkscope-web -- src/i18n/foundationBoundaries.test.ts src/i18n/visibleLiteralScanner.test.ts src/settings/DataStorageSection.test.tsx src/SettingsCss.test.ts src/ProviderSection.test.ts src/LifecycleAutomationApi.test.ts src/i18n/resources.test.ts
```

Output: `Test Files 7 passed (7); Tests 127 passed (127)` (exit 0), duration 9.55s.
