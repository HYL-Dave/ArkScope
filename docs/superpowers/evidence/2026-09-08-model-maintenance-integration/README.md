# Model Maintenance Integration

The user authorized local integration, retaining manual App restart and push.
`master` fast-forwarded from `168a94cd` to `10cb4775` through three commits:

- `c1bcc571`: automation mode controls, removal of redundant model counts, GPT-6 Astra.
- `d97ff291`: representative verification and the retained mutation-harness incident.
- `10cb4775`: SDK 0.2.152 / CLI 2.1.259 admission and GPT-5.6 fixed-output repair.

No new model execution, data-provider call, migration, production setting write,
App restart or push was performed during this integration. Official documentation
was read. Previous sealed evidence remains historical, unchanged evidence.

## Post-merge test-isolation finding

Both checkouts have identical runtime/test source at `10cb4775`. The original
scheduler fixture set synthetic environment values but retained process-global
file/app provenance from preceding tests. A preceding model test can invoke the
legacy env loader; a synthetic replacement then incorrectly remains marked as
file-sourced and the real strict provider preflight returns `not_configured`.
The affected fixture and source-bookkeeping code predate this model-maintenance
batch. This is not evidence of a new provider outage or an App credential change.

| Verification | Observed result |
| --- | --- |
| Pre-merge full canonical backend, isolated network | 7,331 passed / 12 skipped / three existing edgar warnings |
| Pre-merge full frontend | 1,700 passed / 124 files |
| Pre-merge build/typecheck and i18n | Passed |
| Main-checkout post-merge build/typecheck | Passed; existing bundle-size warning |
| Main-checkout original ordered 548-node focus | 36 failed / 512 passed |
| Worktree identical ordered focus | 548 passed |
| Scheduler alone, main and worktree separately | 127 passed in each |
| Synthetic provenance RED, before fixture repair | 65 failed / 67 passed |
| Synthetic provenance GREEN, after fixture repair | 132 passed |
| Repaired complete focus with synthetic provenance | 553 passed |
| Final full canonical backend after fixture repair | 7,336 passed / 12 skipped / three existing edgar warnings |
| Main-checkout complete focus after `9dcf1b79`, with poisoning | 553 passed |

`tests/offline_scheduler_provenance.py` is opt-in. It temporarily marks all five
synthetic scheduler fields as file-sourced before fixture setup and restores the
original set after each scheduler test. It does not read any env file or use any
real credential. This is a broader poison than the observed main-checkout state;
the 65 failures are not claimed to be the same 36 failures.

The repair changes only `tests/test_data_scheduler.py`: the fixture clears the
file/app source markers for exactly the five values it replaces, using
`monkeypatch` restoration. It does not bypass provider preflight or weaken a
missing-config assertion. Five named provenance tests join the existing
positive/negative scheduler owners; no tests are removed. The normal full-suite
plugin configuration is unchanged.

The test-only repair is locally merged at `9dcf1b79`. Final full verification
took 769.12 seconds; the main-checkout focus took 13.05 seconds. No runtime,
frontend or dependency bytes differ from the live-verified `10cb4775` baseline.
Both pre-existing artifact manifests and the current live-source manifest verify
from the main checkout. The final suite collects 7,348 tests: exactly five more
than the pre-repair tree, with the same twelve skips.

Independent read-only review reported no actionable findings and ran twelve
poisoned controls, including missing-config/setup-required rejection and mocked
dispatch. It assessed restoration of the original provenance sets statically;
explicit `_APP_APPLIED` poisoning and teardown object-identity assertions were
not added. No claim of exercising those additional scenarios is made.

Publication scans use the prior packet's credential-shape patterns. Any retained
token-shaped redaction-test parameter is accepted only for the exact existing
`tests.test_probe_harness` case, a previously reviewed digest and literal presence
in that test's source. XML is inspected structurally; raw artifacts are unchanged.

## Reproduction

All backend runs use the credential-filtered, loopback-only network namespace:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q -p tests.offline_scheduler_provenance tests/test_data_scheduler.py --tb=short
```

The retained RED/GREEN XML names the individual assertions. `poisoned-focus.xml`
contains the complete OpenAI fixed-output, model/task, Claude SDK/auth and
scheduler focus, rather than a single-file success claim.

## Hand Test And Follow-ons

Integration verification is complete. The user restarts the App manually:

1. With an explicitly selected Luna API-key route, generate a new card and
   translate previously untranslated content so a cached result is not the test.
2. With Sonnet 5 / Claude OAuth, verify the existing selected task works. Do not
   infer Fable 5.1 OAuth admission from this SDK upgrade.
3. Check Settings automation modes and removal of redundant model counters.
   GPT-6 Astra is a new choice, not a silently changed task default.

The accepted SEC Research/Notes direction and OpenAI Responses convergence are
recorded separately in `docs/design/PROJECT_PRIORITY_MAP.md`. SEC collector/UI
changes and remaining Chat Completions migration are not implemented here. The
custom-model compatibility question remains open; no compatibility mode is
removed while awaiting the user's preference.
