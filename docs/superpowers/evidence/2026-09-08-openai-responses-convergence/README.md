# OpenAI Responses Convergence

Base: `65c673cf`. Branch: `codex/openai-responses-convergence`.
This packet covers the four remaining direct OpenAI Chat Completions calls.
It does not change Anthropic or subscription transports, enable a Codex harness,
change credentials, or perform a provider call, migration, App restart, merge
or push. Production stores were not inspected or changed for this work.

## Contract

| Entry point | Responses request | Preserved behavior |
| --- | --- | --- |
| Card synthesis, including custom IDs | Existing function-output helper | Model, effort, credential, schema, timeout and 8,192-token output budget |
| Content Translation, including custom IDs | Same helper | Model, effort, credential, schema, timeout and 4,096-token output budget |
| API-key model-access probe | No-tool text request | Selected credential/model/effort and 16-token diagnostic budget |
| Investor-profile calibration | No-tool JSON mode via `text.format` | Instruction/history order and existing six-field calibration parser |

Custom model IDs are still sent unchanged. No actual requirement for a
Chat-Completions-only model was established; an old test pinned ArkScope's
endpoint choice, not a provider capability. The obsolete per-model
`uses_responses_for_tools` transport flag is removed. No new model, task default,
entitlement, SDK version, output schema, frontend/API DTO or data schema changes.

All migrated OpenAI boundaries disable SDK retries. The model probe also stops
its former automatic retry with default effort. Rejections do not change model,
effort, key, endpoint or billing source. Anthropic's existing behavior is not
silently changed by this OpenAI-only migration.

Task responses must complete, match the requested model under the existing
reviewed-alias rules, and contain the expected output. Custom IDs and explicit
snapshots cannot change. Fixed tasks require their one expected function call
and valid schema; calibration rejects tools, refusals, empty/partial messages
and incomplete responses. No hosted tools, conversation storage or automatic
truncation is enabled (`store=false`).

The tiny access probe has one deliberate distinction: an exact-model response
with `status=incomplete`, no error and reason `max_output_tokens` establishes
request acceptance only. It returns a warning explicitly stating that output
generation was not verified. Other incomplete/failed results are errors. This
preserves its existing cost bound without claiming a completed real task or
quietly retrying with different settings.

The future Codex-harness/direct-API comparison is recorded separately in the
Priority Map. Responses convergence is not a decision to adopt that harness.
The parameter mapping follows the [official migration guide](https://developers.openai.com/api/docs/guides/migrate-to-responses).

## Verification

All backend runs use the existing, unchanged Linux network-namespace wrapper:

```sh
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python \
  docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py \
  pytest -q tests --tb=short
```

The observed wrapper witness is loopback only, `ENETUNREACH` for an external
route and no inherited provider credentials. Real OpenAI SDK clients use
`httpx.MockTransport` and synthetic credentials, not real API calls.

The focused set is these eight files:

```text
tests/test_openai_responses_convergence.py
tests/test_openai_fixed_output_compatibility.py
tests/test_gpt6_admission.py
tests/test_card_synthesis.py
tests/test_model_credentials_characterization.py
tests/test_model_task_test.py
tests/test_investor_profile_calibration.py
tests/test_investor_profile_calibration_routes.py
```

- Pre-change six-file baseline: 305 passed.
- New RED set: 63 failed / 81 passed, including wrong endpoint and retry behavior.
- First expanded run: 1 failed / 418 passed. The old card fixture serialized
  nullable internal defaults into fields whose existing tool schema requires
  strings when present. The fixture now omits those absent fields; the production
  schema and validation are not relaxed.
- Corrected expanded focus: 419 passed.
- Final full backend: **7,401 passed / 12 skipped / three existing edgar
  deprecation warnings**, 781.46 seconds; exit code zero. All focused tests also
  pass in this unmutated, whole-suite execution after the harness correction.

Three old test nodes intentionally change contract/name: the two custom-model
endpoint cases and one legacy synthesis-shape case now require Responses while
retaining model and schema assertions. There are 65 additional nodes: 37 probe/
calibration cases and 28 legacy/custom fixed-output cases. No other test owner
is removed to make this migration pass.

Each opt-in mutation runs the entire 419-node focused set under the same wrapper:

| Mutation | Failed / passed | Named ownership |
| --- | --- | --- |
| Return fixed tasks to Chat Completions | 134 / 285 | `test_custom_fixed_tasks_use_responses_without_rewriting_model_id` and HTTP contract matrix |
| Remove model receipt rejection | 15 / 404 | Model mismatch/sibling/snapshot controls across fixed and no-tool tasks |
| Ignore completion/error state | 8 / 411 | Failed/error/incomplete controls |
| Ignore unexpected no-tool output items, corrected harness | 2 / 417 | `test_no_tool_responses_reject_invalid_results[tool-probe]` and `[tool-calibration]` |
| Restore OpenAI effort-default retry | 3 / 416 | 400/429/500 probe failures must dispatch once |
| Restore calibration SDK retries | 3 / 416 | 429/500/timeout calibration failures must dispatch once |

The initial text-items campaign only failed the probe owner: calibration had
imported the old function by value, so the mutation did not reach it. Independent
review caught this harness defect. The corrected plugin rebinds that import;
both named owners fail, and the reviewer independently measured two failures
under mutation and two baseline passes. The initial result is retained and is
not evidence of calibration coverage. Review reported no product-code findings.

An initial full-suite command omitted `tests` and incorrectly collected archived
evidence scripts, producing five collection errors before execution. It is
retained separately from the corrected canonical backend run; archived scripts
are not edited or counted as the product suite.

JUnit reports preserve failed attempts separately. `results.json` records
counts and named failures; `source-files.sha256` binds the reviewed source/tests,
pin and offline wrapper, and `artifact-files.sha256` binds this packet. This is
offline protocol/regression evidence, not a new live provider certification.
No frontend source changed and no new frontend or browser test run is claimed.
Publication permits only the two digest-pinned, preexisting redaction-fixture
literals at their exact full-backend test IDs; other secret-shaped content
fails the seal check. The original reports are not rewritten to pass scanning.

## After Integration

Restart the App from the merged tree before hand testing. One OpenAI API-key
model at explicit effort can cover model-access verification, card synthesis
and Content Translation; also check one investor-profile calibration exchange
if that feature is in use. No exhaustive model-by-model live sweep is required.
OAuth remains on its existing independent path. This branch is not merged by
the implementation step.
