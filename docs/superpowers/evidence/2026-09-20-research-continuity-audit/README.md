# Research Continuity Archive Handoff

Source inspected: master `f0024782abee641a4c859cfab86ae3b1666a7b28`.
Historical draft: `650130cbcd50108cb4a5fdbc3f3e21eb9ccd3675`.

The user approved archiving both remaining branches, with a condition that the
real issues in the continuity draft enter the next repair plan. The active owner
is now `docs/superpowers/plans/2026-09-20-research-continuity-repair.md`, also
listed in `docs/design/PROJECT_PRIORITY_MAP.md`. Native sessions, native storage
schema and cache controls are not implemented by this archive operation.

## Offline Observation

Command:

```bash
python docs/superpowers/evidence/2026-09-20-research-continuity-audit/observe.py
```

The script executes the real run manager against a synthetic stream and temporary
SQLite stores. Python audit hooks deny network/subprocess activity and SQLite
paths outside its private temporary directory. No production profile, private
conversation, credential, live provider or external SDK session is used.

| Case | Before fresh-store recovery | After recovery | Provider dispatches |
| --- | --- | --- | --- |
| Positive control | `succeeded`, one assistant, one `done` event | Unchanged; user/assistant history available | 1 |
| Assistant persistence raises | `succeeded`, **zero assistants**, one `done` | Still successful without an answer in next-turn history | 1 |
| Interrupt before terminal status | `running`, one saved assistant, one `done` | `interrupted`, **two assistant messages**, one is an error; `done` plus `error` events | 1 |

The last case preserves the real answer; the defect is inconsistent completion
and an extra error reply, not deletion of that answer. The first failure also
retains an answer in the replay event, so it is a materialization/history defect,
not evidence that every recoverable copy has been lost. No production frequency
or data-loss claim is made from these synthetic cases.

The observer exits 0 when its positive control and isolation assertions pass.
That is **not** RED-to-GREEN acceptance of the defects. The repair plan names the
required failing behavioral tests and scopes them to the server-owned run path.

## Existing Protections And Limits

Rechecked current source:

- Claude OAuth still uses a temporary SDK configuration directory and no native
  resume. `_compose_input` does carry prior application text into each question.
- `build_thread_history` retains the non-error text contract; it does not promise
  full tool-frame or hidden-reasoning transfer.
- Run admission, cancellation and interrupted-run error persistence already use
  shared database transactions. Preserve these tests when adding a successful
  completion transaction; do not describe them as missing today.
- Captured runtime authentication still owns execution credentials. Native state
  cannot replace that authority.
- Token-monitoring/notebook work is not revived. Existing subscription usage
  display, translation and error attribution remain available.

Baseline regression, one pytest process:

```bash
python -m pytest tests/test_research_runs.py tests/test_research_threads.py tests/test_claude_code_sdk_driver.py tests/test_task_runtime_binding.py -q --tb=short --disable-warnings
```

Result: **258 passed**, 15.94 seconds. These are existing protections, not tests
that prove native resume or the newly observed persistence defects fixed. No
complete backend/frontend rerun was needed for this docs/observer-only handoff.
