# Scripts Retirement Tranche A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **Status:** TASK 0 BLOCKED - PROVIDER-SAFE BASE AMENDMENT REVIEW REQUIRED
>
> **Date:** 2026-08-01
>
> **Decision authority:** `d89d433c`
>
> **Grounding commit:** `24202182032670f0d762dbd98581a74e5427b818`

**Goal:** Complete the repository-only first tranche of root `scripts/`
retirement while preserving current product behavior, the old score read
contract, production data, and every explicitly deferred Tranche B decision.

**Architecture:** Move the three maintained manual smokes to a non-collected
`tests/live/` owner, move score/HuggingFace provenance to `docs/history/`,
extract static knowledge from paid/research probes, and delete spent migration,
diagnostic, and research executables together with their gate-only code. Keep
the whole `scripts/scoring/` package and its 36 directly coupled tests through
Tranche A so the score producer/importer, Tool Catalog contract, Desktop
carry-over ruling, and local credential owner remain coherent until the atomic
Tranche B product decision.

**Tech stack:** Git, Python 3.10, pytest, Markdown, shell structural gates.

---

## 0. Authority And Execution Boundary

This plan implements only Section 6.1 of:

```text
docs/design/SCRIPTS_RETIREMENT_DECISION.md
authority commit: d89d433c
authority blob SHA-256:
0ae53860bb8407d07f7f7aad574530b60488f52c6049964fc9555f563c2bc791
plan-gate status evolution SHA-256:
40749aec44871f26526721b477e49fb458297db5e34529ba553a1c6e2746ad24
```

The second SHA differs only because the plan-gate commit records the completed
independent decision review and the next review gate in the document header.
It does not change a locked disposition.

Implementation remains in:

```text
worktree: /tmp/arkscope-scripts-retirement
branch:   codex/scripts-retirement-decision
base:     d89d433c
```

The main worktree contains the protected pre-authority draft:

```text
/mnt/md0/PycharmProjects/ArkScope/docs/design/SCRIPTS_RETIREMENT_DECISION.md
SHA-256:
79d4eac97d7692684d83f0a067f5987fe434bb76746b98af3e44f1c8ba4bf277
```

Do not edit, stage, delete, overwrite, or use that untracked file as the
implementation authority. All edits occur in the isolated worktree against the
committed authority.

### 0.1 Tranche boundary

Tranche A keeps these exact nine tracked paths:

```text
scripts/__init__.py
scripts/scoring/README.md
scripts/scoring/__init__.py
scripts/scoring/import_news_scores_local.py
scripts/scoring/openai_summary.py
scripts/scoring/score_ibkr_news.py
scripts/scoring/score_risk_anthropic.py
scripts/scoring/score_sentiment_anthropic.py
scripts/scoring/validate_scores.py
```

All eight `scripts/scoring/` paths and the root package marker remain
byte-present through Tranche A. Tranche A must not:

- alter score runtime semantics, score schemas, score readers, score DTOs,
  routes, tools, agents, frontend types, or production score rows;
- alter `src/daily_update.py`, `docs/design/ARKSCOPE_TOOL_CATALOG.md`, or
  `docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md`;
- retire or rename any of the 36 score-coupled test nodes in Section 2.2;
- inspect, print, hash into tracked evidence, move, chmod, or delete
  `config/scoring_keys.txt`; or
- claim that the old score product contract is already retired.

The current scorer remains the named credential consumer under
`CONFIG_AUTHORITY_PLAN.md` and `CREDENTIAL_MANAGEMENT_PLAN.md` until Tranche B.
This is the closed Section 5.2.1 disposition for Tranche A. It is not a claim
that the scorer survives the final programme.

### 0.2 Production and provider boundary

No admitted Tranche A verification may perform a provider request, Gateway
connection, scheduler action, production database write, production-data
migration, ignored archive change, or local-secret operation. In particular:

- automated admission must exclude both Financial Datasets probe files at
  collection time and may not execute either probe;
- do not execute the IBKR diagnostic or any moved live smoke;
- do not run any retired migration CLI;
- do not change anything under `data/backups/`;
- do not delete the legacy scheduler/IV archive or edit its ignored
  `RESTORE.txt`; and
- do not read the contents of `config/scoring_keys.txt`.

The first Task 0 native attempt exposed a contradiction in the reviewed plan:
this section prohibited executing the two probes while Task 0 Step 5 ran the
unfiltered 4,730-node suite that collected both of them. That attempt made 29
unauthenticated Financial Datasets request attempts under `env -i`; it supplied
no Financial Datasets API key attributable to the user's account. Its surviving
28 response artifacts contain `200`, `400`, `401`, `404`, and `410` statuses,
but they are not cost, entitlement, or capability classification evidence.
The user subsequently confirmed that bounded testing spend can be approved,
but that clarification does not retroactively make this run an admitted
provider-free base.

Preserve the first attempt as immutable rejected evidence. Do not overwrite its
report, transcript, or exact-path quarantine. The replacement provider-safe
base must use the reviewed `--ignore` arguments in Task 0 Step 5, must never
create `comparison_results/`, and must be the only native base admitted to the
Tranche A A/B ledger.

This correction also applies to how earlier EIR-002 full-suite history is read:
those commands used a blank credential environment, but they did not exclude
the two probe nodes and therefore made the same unauthenticated request shape.
Their test and collection results remain valid for their stated purposes; they
are not evidence that those historical runs were network-free.

### 0.3 Canonical admission boundary

Collection and narrow non-ASGI checks may run in the managed sandbox. The
canonical full suite must run in the same native boundary accepted by EIR-002,
after the pinned wakeup probe returns exact `true/0/0`.

Pinned assets:

```text
/tmp/arkscope_asyncio_wakeup_probe.py
SHA-256:
10647c1e64c49fc2e082701d7a735e40782620314c125cd103a9a3f9bb37bc2e

/tmp/eir002-green-baseline/arkscope_eir002_reporter.py
SHA-256:
09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928

/tmp/eir002-green-baseline/run_native.sh
SHA-256:
e7c963f1bc97125b70b435fb3c41bf4e59d501f0da561f2ef6d921c12083c84f
```

The native wrapper requires Node `v22.14.0`, creates its own blank runtime
stores, strips credentials through `env -i`, and writes a structured reporter.
Do not copy or edit it for this tranche.

The sole allowed link into the production-root worktree during fresh-worktree
admission is the pinned test toolchain:

```text
target: /mnt/md0/PycharmProjects/ArkScope/node_modules
package-lock.json SHA-256:
5322cb03099b873066b7572c02db68a427ddc7509fdc9850cf9d8d3948a19f2c
node_modules/.package-lock.json SHA-256:
4dd5182f8111b54dd608344c45513f3b310f39321a3cc9832b60cefc2fa241ff
Node: v22.14.0
jsdom: 29.1.1
```

---

## 1. File Map

### 1.1 Move maintained manual checks

| From | To |
|---|---|
| `scripts/live/sdk_driver_smoke.py` | `tests/live/sdk_driver_smoke.py` |
| `scripts/live/sdk_route_smoke.py` | `tests/live/sdk_route_smoke.py` |
| `scripts/p1_2/smoke_fred.py` | `tests/live/smoke_fred.py` |
| `scripts/live/README.md` | Fold into new `tests/live/README.md` |

Also evolve:

- `docs/design/MACRO_FRED_PRODUCT_SEMANTICS.md`
- `tests/test_fred_ingestion.py`

The three moved Python filenames deliberately do not start with `test_`.
Default pytest collection must remain unchanged after this task.

### 1.2 Extract knowledge, then remove research/probe families

Create or move:

```text
docs/design/FINANCIAL_DATASETS_CAPABILITY_SPEND_DECISION.md
docs/history/SCRIPTS_RETIREMENT_TRANCHE_A.md
docs/history/news-scoring/SCORING_PROMPTS.md
docs/history/news-scoring/column_mapping.md
```

Remove after the owning documents exist:

```text
scripts/analysis/scan_unusual_activity.py
scripts/diagnostics/probe_ibkr_news_bodies.py
scripts/huggingface/merge_for_release.py
scripts/testing/test_financial_datasets_api.py
scripts/testing/test_financial_datasets_api_retry.py
scripts/visualization/README.md
scripts/visualization/data_loader.py
scripts/visualization/news_dashboard.py
```

Move, preserving bytes:

```text
scripts/huggingface/SCORING_PROMPTS.md
  -> docs/history/news-scoring/SCORING_PROMPTS.md
scripts/huggingface/column_mapping.md
  -> docs/history/news-scoring/column_mapping.md
```

Update their current links in:

```text
scripts/scoring/README.md
docs/data/NEWS_DATA_INVENTORY.md
docs/history/FNSPID_NEWS_EXTRACTION.md
.gitignore
data_sources/PAID_SUBSCRIPTION_EVALUATION.md
data_sources/PAID_SUBSCRIPTION_EVALUATION.tex
data_sources/DATA_SOURCES_EVALUATION.md
docs/data/OPTIONS_PRICING_THEORY.md
```

### 1.3 Retire spent migrations and gate-only code

Remove all eleven migration CLIs:

```text
scripts/migration/apply_news_normalization.py
scripts/migration/job_runs_local_cutover.py
scripts/migration/n9_batch1_pg_drop.py
scripts/migration/n9_batch2_cleanup.py
scripts/migration/n9_batch3_prices_drop.py
scripts/migration/news_n8a_cutover.py
scripts/migration/news_scores_cutover.py
scripts/migration/p0c_hapn_patch.py
scripts/migration/p0c_prices_reconcile.py
scripts/migration/preview_news_normalization.py
scripts/migration/retire_legacy_scheduler_iv.py
```

Remove the eight spent domain migration cores:

```text
src/service/job_runs_cutover.py
src/prices_patch.py
src/prices_reconcile.py
src/news_normalized/migration.py
src/news_normalized/migration_policy.py
src/news_normalized/migration_apply.py
src/news_normalized/cutover.py
src/news_normalized/score_cutover.py
```

Keep `src/news_normalized/score_import.py`; it is the current score-import
implementation and belongs to Tranche B.

Remove the twelve whole migration test files listed in Section 2.3. Update the
legacy scheduler/IV evidence in the same commit that removes its CLI.

### 1.4 Reconcile current authorities and broken instructions

Modify:

```text
README.md
PROJECT_STRUCTURE.md
docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md
docs/design/REPO_HYGIENE_B6_MODULE_DISPOSITION.md
docker/README.md
src/auth_drivers/chatgpt_oauth_probe.py
docs/design/LLM_AUTH_DRIVER_PLAN.md
docs/design/RL_COLLAPSE_FINDINGS.md
docs/design/SA_EXTENSION_ROADMAP.md
docs/data/IBKR_NEWS_API_LIMITATIONS.md
docs/data/NEWS_PROVIDER_DATA_DICTIONARY.md
training/data_prep/state_builder.py
training/model_registry.py
training/rl/inference.py
training/scripts/rl_vlite_rerun.sh
docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md
```

Authority and execution evidence:

```text
docs/design/SCRIPTS_RETIREMENT_DECISION.md
docs/design/PROJECT_PRIORITY_MAP.md
docs/superpowers/plans/2026-08-01-scripts-retirement-tranche-a.md
docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md
```

---

## 2. Immutable Accounting

### 2.1 Canonical collection

The accepted EIR-002 report is:

```text
/tmp/eir002-green-baseline/reports/merged-v2-full.json
collected: 4730
seen:      4730
passing:   4658
skipped:   72
nonpassing: 0
exitstatus: 0
```

Its ordered `collected_node_ids` stream is:

```text
4730
c34de9a0fe53e400409d3ec26d75a8c907ee277b121279693ea9f69c8638aabb
```

Plan construction removed only the exact nodes classified below and reproduced:

| Stage | Delta from base | Count | Ordered stream SHA-256 |
|---|---:|---:|---|
| Base | `+0/-0` | 4,730 | `c34de9a0fe53e400409d3ec26d75a8c907ee277b121279693ea9f69c8638aabb` |
| Paid probes retired | `+0/-2` | 4,728 | `49e4a32b5f536cea97053578f2fba4456ffbbe0c10a4b66540c4f26d2b55329f` |
| Diagnostic probe retired | `+0/-5` | 4,725 | `64ce4a619039fa586f065533b900416b1fd3fcbf6d78a99a43c9295a02a83e1d` |
| Migration gates retired | `+0/-177` | 4,553 | `69152591306a8dee5e66e2efeb2f1ec12720c8a1a1ffe36def613f4fe5a676ca` |

The final Tranche A delta is exactly `+0/-177`. No helper may be collected,
and no retained node may be renamed, parametrized into a different identity,
skipped, or marked xfail.

Physical collection identity and executable admission identity are deliberately
separate at the base:

```text
physical collect-only authority:
4730 / c34de9a0fe53e400409d3ec26d75a8c907ee277b121279693ea9f69c8638aabb

provider-safe native base after exact two-file exclusion:
4728 / 49e4a32b5f536cea97053578f2fba4456ffbbe0c10a4b66540c4f26d2b55329f
4656 passed / 72 skipped / 0 failed
```

The native executable A/B therefore compares the 4,728 safe base nodes with
the 4,553 final nodes: exactly 175 executed base nodes leave after Task 0.
The repository collection ledger still proves the full physical `-177/+0`,
including the two paid-probe nodes removed in Task 2. Neither identity may be
substituted for the other.

The final 4,553-node physical collection contains the same 72 intentional
skips, so final native admission is:

```text
4553 collected and seen
4481 passed
72 skipped
0 failed
empty non-passing SHA:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

### 2.2 Complete 159-node direct-coupling disposition

Every directly coupled node has one closed Tranche A disposition:

| Family | Count | Tranche A disposition |
|---|---:|---|
| Migration-script direct nodes | 118 | remove with spent gates |
| Diagnostic-probe nodes | 3 | remove; adapter contract remains |
| Financial Datasets root nodes | 2 | remove after static knowledge extraction |
| Score-coupled nodes | 36 | retain unchanged for Tranche B |
| **Total** | **159** | **123 remove / 36 retain** |

The canonical sorted `node_id<TAB>disposition` stream is:

```text
159 rows
15f54aeae019936c660c48eecc6165156ae050604fe4267f780250f98f72728a
```

The 118 migration-script nodes are:

| Owning test group | Count | Rule |
|---|---:|---|
| `tests/test_legacy_scheduler_iv_retirement.py` | 17 | all IDs |
| `tests/test_n9_batch1_pg_drop.py` | 29 | all IDs |
| `tests/test_n9_batch2_cleanup.py` | 11 | all IDs |
| `tests/test_n9_batch3_prices_drop.py` | 16 | all IDs |
| `tests/test_news_n8a_cutover.py` | 26 | all IDs |
| `tests/test_news_scores_cutover_cli.py` | 3 | all IDs |
| `tests/test_job_runs_cutover.py` | 1 | `test_cli_accepts_subcommand_market_db_alias` |
| `tests/test_news_normalization_migration.py` | 1 | `test_preview_cli_is_read_only_and_emits_json` |
| `tests/test_news_normalization_apply.py` | 8 | exact IDs below |
| `tests/test_prices_patch.py` | 4 | exact IDs below |
| `tests/test_prices_reconcile.py` | 2 | exact IDs below |
| **Total** | **118** | remove |

The eight direct normalization-apply IDs are:

```text
tests/test_news_normalization_apply.py::test_apply_cli_requires_scheduler_paused_confirmation
tests/test_news_normalization_apply.py::test_disk_preflight_refuses_before_backup
tests/test_news_normalization_apply.py::test_orchestrator_integrates_backup_apply_reopen_and_replan
tests/test_news_normalization_apply.py::test_orchestrator_orders_lock_backup_begin_and_postcheck
tests/test_news_normalization_apply.py::test_orchestrator_refuses_each_fingerprint_before_backup[expected_input_fingerprint-bad-input]
tests/test_news_normalization_apply.py::test_orchestrator_refuses_each_fingerprint_before_backup[expected_rejection_evidence_fingerprint-bad-rejection]
tests/test_news_normalization_apply.py::test_orchestrator_refuses_each_fingerprint_before_backup[expected_resolved_fingerprint-bad-resolved]
tests/test_news_normalization_apply.py::test_orchestrator_rolls_back_on_validation_failure
```

The four direct price-patch IDs are:

```text
tests/test_prices_patch.py::test_cli_apply_inserts_updates_validates_and_is_idempotent
tests/test_prices_patch.py::test_cli_apply_refuses_fingerprint_mismatch_and_blocked_rows
tests/test_prices_patch.py::test_cli_build_produces_model_order_rows
tests/test_prices_patch.py::test_cli_dry_run_reports_plan_without_writing
```

The two direct price-reconcile IDs are:

```text
tests/test_prices_reconcile.py::test_reconcile_cli_writes_deterministic_report
tests/test_prices_reconcile.py::test_reconcile_report_groups_pg_only_and_value_mismatch_rows
```

The three diagnostic IDs are:

```text
tests/test_news_normalized_ibkr_adapter.py::test_probe_output_never_contains_body_or_exception_payload
tests/test_news_normalized_ibkr_adapter.py::test_probe_classifies_ibkr_unavailable_without_payload
tests/test_news_normalized_ibkr_adapter.py::test_probe_has_five_reviewed_default_cases
```

The two paid-probe IDs are:

```text
scripts/testing/test_financial_datasets_api.py::test_all_endpoints
scripts/testing/test_financial_datasets_api_retry.py::test_failed_endpoints
```

The 36 retained score IDs are every collected ID under:

```text
tests/test_news_score_import.py              7
tests/test_score_ibkr_keys.py               11
tests/test_scoring_api_routing.py            1
tests/test_scoring_continue_from.py         17
```

They remain byte-present and green. Tranche A does not reinterpret any of them.

### 2.3 Additional 54 domain-core nodes

Deleting the spent migration cores also removes 54 nodes that do not directly
bind a root script but exist only to prove the completed one-shot migrations:

| File | Direct script nodes | Domain-core-only nodes | Total removed |
|---|---:|---:|---:|
| `tests/test_job_runs_cutover.py` | 1 | 5 | 6 |
| `tests/test_legacy_scheduler_iv_retirement.py` | 17 | 0 | 17 |
| `tests/test_n9_batch1_pg_drop.py` | 29 | 0 | 29 |
| `tests/test_n9_batch2_cleanup.py` | 11 | 0 | 11 |
| `tests/test_n9_batch3_prices_drop.py` | 16 | 0 | 16 |
| `tests/test_news_n8a_cutover.py` | 26 | 0 | 26 |
| `tests/test_news_normalization_apply.py` | 8 | 9 | 17 |
| `tests/test_news_normalization_migration.py` | 1 | 29 | 30 |
| `tests/test_news_scores_cutover_apply.py` | 0 | 3 | 3 |
| `tests/test_news_scores_cutover_cli.py` | 3 | 0 | 3 |
| `tests/test_prices_patch.py` | 4 | 3 | 7 |
| `tests/test_prices_reconcile.py` | 2 | 5 | 7 |
| **Total** | **118** | **54** | **172** |

The sorted 54-node domain-core-only stream is:

```text
54 rows
5259ce298190e13ea6a7a4456dcb54b3d0f3c54c0a65e64a56da975209e175d0
```

Remove these twelve whole files. Do not move their assertions into current
product tests: the reviewed specs, plans, evidence, hashes, and Git history are
the durable owners of completed migration behavior.

### 2.4 Required retained regression gates

These suites remain:

```text
pytest -q \
  tests/test_news_score_import.py \
  tests/test_score_ibkr_keys.py \
  tests/test_scoring_api_routing.py \
  tests/test_scoring_continue_from.py
expected: 36 passed

pytest -q tests/test_news_normalized_ibkr_adapter.py
expected after Task 3: 17 passed

pytest -q \
  tests/test_sqlite_backend.py \
  tests/test_fundamentals_sec_cache.py \
  tests/test_news_scores.py \
  tests/test_db_backend.py
expected: 94 passed, 18 skipped
```

`tests/test_legacy_iv_retirement_boundaries.py` remains unchanged in Tranche A.
Its non-migration-scripts node still scans the retained scoring package and is
not renamed into a final no-`scripts/` assertion before Tranche B.

---

## 3. Structural Contracts

### 3.1 `tests/live/`

`tests/live/README.md` must state all of:

- files are manual, never default-collected checks;
- they can require real credentials, network, Gateway state, and provider
  entitlement, and may incur spend;
- no automated admission command runs them;
- exact commands are:

```text
python tests/live/sdk_driver_smoke.py
python tests/live/sdk_route_smoke.py
python tests/live/smoke_fred.py
```

Do not rename them to `test_*.py`. Do not execute them during this tranche.

### 3.2 Financial Datasets inventory

`docs/design/FINANCIAL_DATASETS_CAPABILITY_SPEND_DECISION.md` is a static,
dated decision input, not a capability registry and not spend authorization.
It must record:

- 29 request attempts in the two retired files;
- no product assertion and no retained result artifact;
- the 24 unique literal endpoint paths below;
- `/crypto/tickers` and `/filings/items/available` as retry-only conflicts,
  not current capability claims;
- that the production client currently covers only the three financial
  statement endpoints, not this inventory;
- capability, credential entitlement, and user spend authorization as separate
  facts; and
- no provider call was made while extracting the inventory.

It must also separate three evidence classes:

1. the literal endpoint/request-shape inventory extracted from the retired
   files;
2. the rejected Task 0 observation: 29 unauthenticated attempts and 28
   surviving response artifacts, explicitly not accepted as endpoint cost,
   entitlement, or availability evidence; and
3. dated official observations rechecked on 2026-08-01:
   - Credits is advertised as `$20` for `1,000` requests and premium requests
     consume `8x`;
   - Build is advertised as `$200/month` for `100,000` requests and premium
     requests consume `4x`;
   - the Terms state that API and MCP calls are billable units, Credits draws
     prepaid balance, subscription overage draws prepaid balance, and an empty
     balance yields HTTP `402`; and
   - the published MCP tool list, API documentation index, and OpenAPI
     inventory expose no documented account-balance or remaining-usage
     operation.

The dated official source URLs are:

```text
https://www.financialdatasets.ai/pricing
https://www.financialdatasets.ai/terms-of-use
https://docs.financialdatasets.ai/mcp-server
https://docs.financialdatasets.ai/llms.txt
https://docs.financialdatasets.ai/api/openapi.json
```

The decision input must preserve these owner-directed requirements for a later
product slice without implementing them in Tranche A:

- the existing enable control means "allow metered network requests", not
  "hide cached Financial Datasets data";
- cached data remains readable while metered requests are disabled;
- endpoint policy uses a reviewed classification such as
  `no_credit`, `core_1x`, `premium`, or `unknown`, with `unknown` failing
  closed for automatic calls;
- the product does not impose a user-configured daily or per-request cap;
- before first metered enablement the user explicitly selects `credits` or
  `subscription`; the declaration is editable and changes are audit-recorded;
- Credits UI warns that requests consume prepaid balance, while subscription
  UI prompts a user who declared a subscription to enable the source and warns
  that overage may draw prepaid balance;
- HTTP `402` becomes typed `credits_exhausted` and stops blind automatic
  retries;
- locally observed request units are labelled non-authoritative because other
  clients, purchases, resets, and provider-side multipliers are not fully
  observable; and
- until an official balance API or MCP tool exists, the UI links to the
  provider dashboard rather than scraping or calling a private endpoint.

Registry implementation, backend enforcement, Settings UI, i18n, audit
persistence, and typed runtime handling form a separate reviewed product slice.
They are not Tranche A work.

Exact endpoint set:

```text
/analyst-estimates
/company/facts
/crypto/prices
/crypto/prices/snapshot
/crypto/prices/tickers/
/crypto/tickers
/earnings/press-releases
/filings
/filings/items
/filings/items/available
/financial-metrics
/financial-metrics/snapshot
/financials
/financials/balance-sheets
/financials/cash-flow-statements
/financials/income-statements
/financials/segmented-revenues
/insider-trades
/institutional-ownership
/macro/interest-rates/snapshot
/news
/prices
/prices/snapshot
/prices/snapshot/tickers/
```

### 3.3 Historical extraction

`docs/history/SCRIPTS_RETIREMENT_TRANCHE_A.md` must retain:

1. a migration owner table mapping each removed CLI/core/test family to its
   existing reviewed design/plan/evidence owner;
2. diagnostic-probe lineage and the fact that the adapter's 17 production
   contract nodes remain;
3. the visualization gap list: source/publisher distribution, monthly volume,
   content-length distribution, ticker coverage, publication heatmap, and
   article explorer/filter/search/pagination;
4. the unusual-options candidate and known wrapper defects: documented
   `--max-price` absent, `--location` not forwarded, and random import-time
   client ID; and
5. links to the moved scoring prompts and column mapping, while stating that
   the scorer/importer remain transitional live owners until Tranche B.

This document records knowledge. It does not promise to rebuild a dashboard,
scanner UI, or score pipeline.

### 3.4 Legacy scheduler/IV rollback language

In
`docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md`,
replace the current executable restore instruction with a dated reclassification:

- rollback is no longer supported;
- Git history retains the retired executable;
- the ignored archive and its `RESTORE.txt` are lineage-only pending the
  separately approved Section 6.3 deletion;
- tracked aggregate/digest evidence remains;
- no archive byte changed in Tranche A.

Do not edit the ignored archive's `RESTORE.txt` in this Git tranche.

### 3.5 Current authority wording

After Tranche A:

- `README.md` and `PROJECT_STRUCTURE.md` describe only the transitional
  `scripts/scoring/` owner and state final root retirement is Tranche B;
- `REFACTOR_PROTECTION_SMOKE_GATES.md` replaces the old broad survivor table
  with the approved interim rule: only the nine Section 0.1 paths are allowed;
- `REPO_HYGIENE_B6_MODULE_DISPOSITION.md` labels its old Section 3 table
  superseded by the approved decision and Tranche A;
- FRED authority names `tests/live/smoke_fred.py`;
- paid-provider evaluation documents link to the static dated decision input,
  not a runnable test, and their already-deleted
  `scripts/collection/collect_ibkr_fundamentals.py` examples are explicitly
  historical rather than runnable;
- Docker describes old N9 CLIs as historical evidence, not current operators;
- the IBKR news limitations/data-dictionary/SA-roadmap documents do not present
  removed `scripts/collection/*` or analysis paths as current cron/operator
  commands;
- the RL findings document labels its removed extraction utility as historical
  and points to retained TensorBoard/`monitor.csv` telemetry;
- the OAuth probe references Novelloom's path as upstream provenance, not a
  local file;
- broken training instructions tell maintainers to re-export/retrain with
  required metadata and to use retained TensorBoard/`monitor.csv` telemetry,
  not nonexistent root scripts; and
- historical specs/plans/evidence may retain dated old paths without becoming
  runnable current instructions.

---

## 4. Tasks

### Task 0: Ground The Reviewed Ledger Before Edits

**Files:**
- Create: `docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Prove branch, authority, and protected draft identities**

```bash
reviewed_plan_tip="$(git rev-parse HEAD)"
test -n "$reviewed_plan_tip"
git merge-base --is-ancestor \
  24202182032670f0d762dbd98581a74e5427b818 \
  HEAD
test "$(git show d89d433c:docs/design/SCRIPTS_RETIREMENT_DECISION.md \
  | sha256sum | awk '{print $1}')" \
  = 0ae53860bb8407d07f7f7aad574530b60488f52c6049964fc9555f563c2bc791
test "$(sha256sum docs/design/SCRIPTS_RETIREMENT_DECISION.md \
  | awk '{print $1}')" \
  = 40749aec44871f26526721b477e49fb458297db5e34529ba553a1c6e2746ad24
test "$(sha256sum \
  /mnt/md0/PycharmProjects/ArkScope/docs/design/SCRIPTS_RETIREMENT_DECISION.md \
  | awk '{print $1}')" \
  = 79d4eac97d7692684d83f0a067f5987fe434bb76746b98af3e44f1c8ba4bf277
git status --short --untracked-files=all
```

Record `reviewed_plan_tip` in evidence. Independent review applies to that
exact immutable commit; any later plan change requires another review.

- [ ] **Step 2: Reproduce base and target streams from the accepted report**

Use `.collected_node_ids`, not terminal prose:

```bash
report=/tmp/eir002-green-baseline/reports/merged-v2-full.json
jq -r '.collected_node_ids[]' "$report" \
  > /tmp/scripts-retirement-a-base.nodes
test "$(wc -l < /tmp/scripts-retirement-a-base.nodes)" -eq 4730
test "$(sha256sum /tmp/scripts-retirement-a-base.nodes | awk '{print $1}')" \
  = c34de9a0fe53e400409d3ec26d75a8c907ee277b121279693ea9f69c8638aabb
```

Generate each stage by removing exactly the Section 2 node IDs/prefixes.
Require:

```text
stage paid:       4728 / 49e4a32b5f536cea97053578f2fba4456ffbbe0c10a4b66540c4f26d2b55329f
stage diagnostic: 4725 / 64ce4a619039fa586f065533b900416b1fd3fcbf6d78a99a43c9295a02a83e1d
final:            4553 / 69152591306a8dee5e66e2efeb2f1ec12720c8a1a1ffe36def613f4fe5a676ca
removed:          177
added:            0
```

Persist the exact 159-node disposition stream and the 54 additional domain
nodes under `/tmp/scripts-retirement-tranche-a/ledger/`. Record their SHA-256
values in evidence. The 159 stream must classify every row as
`remove_migration`, `remove_diagnostic`, `remove_paid_probe`, or
`retain_scoring`; an unclassified or duplicate row stops execution.

Require:

```text
direct disposition:
159 / 15f54aeae019936c660c48eecc6165156ae050604fe4267f780250f98f72728a
domain-core-only:
54 / 5259ce298190e13ea6a7a4456dcb54b3d0f3c54c0a65e64a56da975209e175d0
```

- [ ] **Step 3: Prove physical inventory and secret boundary**

```bash
git ls-files scripts | LC_ALL=C sort \
  > /tmp/scripts-retirement-tranche-a/base-scripts.paths
test "$(wc -l < /tmp/scripts-retirement-tranche-a/base-scripts.paths)" -eq 34
test "$(sha256sum /tmp/scripts-retirement-tranche-a/base-scripts.paths \
  | awk '{print $1}')" \
  = 59cf1e8e6cbdbfa0877aafad87ae8fd7107222afba2030fb87066376b1ee66a5

main_root=/mnt/md0/PycharmProjects/ArkScope
test -f "$main_root/config/scoring_keys.txt"
test "$(stat -c '%a' "$main_root/config/scoring_keys.txt")" = 600
git -C "$main_root" check-ignore -q config/scoring_keys.txt
```

Do not run `cat`, `sha256sum`, `wc`, `sed`, `head`, or any content-reading
command on the main worktree's `config/scoring_keys.txt`. Do not copy the
secret into the isolated worktree.

- [ ] **Step 4: Reproduce canonical collection and retained gates**

Collect with the pinned reporter and require
`4730/c34de9a0fe53e400409d3ec26d75a8c907ee277b121279693ea9f69c8638aabb`.
Then run:

```bash
pytest -q \
  tests/test_news_score_import.py \
  tests/test_score_ibkr_keys.py \
  tests/test_scoring_api_routing.py \
  tests/test_scoring_continue_from.py

pytest -q \
  tests/test_sqlite_backend.py \
  tests/test_fundamentals_sec_cache.py \
  tests/test_news_scores.py \
  tests/test_db_backend.py
```

Expected:

```text
36 passed
94 passed, 18 skipped
```

- [ ] **Step 5: Run one provider-safe native base admission**

Before the run, require no `config/.env`, create only an empty `data/`, and
link the reviewed `node_modules` toolchain exactly as in EIR-002. Inventory
`data` and `src/data`, ordinary/ignored status, and symlinks before the run.

First preserve and classify the already completed unfiltered attempt:

```text
/tmp/eir002-green-baseline/reports/scripts-a-base-full.json
/tmp/eir002-green-baseline/reports/scripts-a-base-full.txt
/tmp/scripts-retirement-tranche-a/quarantine/task0-base-full/
```

It is immutable rejected evidence and must not enter the A/B ledger. Record:

```text
report SHA-256:
9babd7b9f24dda99594436dfa98d10c2af86b1b59b3ea5f19313489f4b1c5b9e
transcript SHA-256:
c913fea3daef11d4b61335a13e055a7782b241db51d46bec511ae6704fe4db2b
pre-quarantine and quarantined ignored-artifact SHA manifest:
3e90b5ba1780547bdc8b77c5abf2cda5cf358f1c1fb82fd284f3b148545ca313
4730 collected / 4730 seen / exitstatus 0
29 unauthenticated request attempts
28 surviving response artifacts because one retry output overwrote an earlier
artifact with the same path
surviving statuses: 2x 200, 1x 400, 20x 401, 4x 404, 1x 410
```

Do not infer free/paid classification, entitlement, capability, or account
spend from those statuses.

Require `comparison_results/` to be absent before the replacement run. Run
natively with exactly these two exclusions:

```bash
/tmp/eir002-green-baseline/run_native.sh \
  scripts-a-base-provider-safe-full \
  --ignore=scripts/testing/test_financial_datasets_api.py \
  --ignore=scripts/testing/test_financial_datasets_api_retry.py
```

Require reporter facts:

```text
4728 collected
4728 seen
ordered collected stream:
49e4a32b5f536cea97053578f2fba4456ffbbe0c10a4b66540c4f26d2b55329f
4656 passed
72 skipped
0 non-passing
exitstatus 0
```

Require `comparison_results/` still absent after pytest exits. Any appearance
means a paid probe imported or executed and invalidates the attempt.

Manifest and exact-path quarantine every newly generated repository-relative
artifact. Restore the pre-run inventory byte-for-byte. Do not touch a
pre-existing file.

- [ ] **Step 6: Create and commit Task 0 evidence**

Create:

```markdown
# Scripts Retirement Tranche A Evidence

> **Status:** IMPLEMENTATION IN PROGRESS
>
> **Date:** 2026-08-01
> **Decision authority:** `d89d433c`
> **Reviewed plan tip:** record the exact `reviewed_plan_tip` captured in Step 1

## 1. Grounding And Protected Boundaries
## 2. 159-Node Direct Disposition
## 3. Collection Ledger
## 4. Structural RED/GREEN
## 5. Native Admission And Artifact Transactions
## 6. Independent Review And Merge
```

Replace the reviewed-plan instruction with the observed SHA before committing.
Section 5 must distinguish the rejected 4,730-node unfiltered attempt from the
admitted 4,728-node provider-safe attempt, retain their artifacts separately,
and include the historical EIR-002 qualification from Section 0.2. It must say
that no admitted Task 0 run executed a Financial Datasets probe; it must not
claim that all historical full-suite runs were network-free.

Add a newest-first priority-map entry stating Task 0 is grounded and
implementation remains blocked until independent evidence review.

```bash
git add \
  docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: ground scripts retirement tranche A"
```

Stop for focused evidence review.

---

### Task 1: Move Manual Smokes Without Collection Drift

**Files:**
- Move: `scripts/live/sdk_driver_smoke.py`
- Move: `scripts/live/sdk_route_smoke.py`
- Move: `scripts/p1_2/smoke_fred.py`
- Replace/move: `scripts/live/README.md`
- Create: `tests/live/README.md`
- Modify: `docs/design/MACRO_FRED_PRODUCT_SEMANTICS.md`
- Modify: `tests/test_fred_ingestion.py`
- Modify: evidence

- [ ] **Step 1: Record structural RED**

Before editing, prove:

```bash
test ! -e tests/live
```

Expected: non-zero. This is the structural RED for the new owner.

- [ ] **Step 2: Move with Git and write the manual contract**

Use `git mv` for the three Python files. Fold the existing live README into
`tests/live/README.md` and add every Section 3.1 warning and exact command.
Update the FRED authority and test docstring to the new path in the same commit.

- [ ] **Step 3: Prove no default collection delta**

```bash
test -f tests/live/sdk_driver_smoke.py
test -f tests/live/sdk_route_smoke.py
test -f tests/live/smoke_fred.py
test -f tests/live/README.md
test -z "$(find tests/live -maxdepth 1 -type f -name 'test_*.py' -print -quit)"
python -m py_compile \
  tests/live/sdk_driver_smoke.py \
  tests/live/sdk_route_smoke.py \
  tests/live/smoke_fred.py
pytest -q tests/test_fred_ingestion.py
```

Do not execute a moved smoke. Recollect canonical nodes and require the base
identity `4730/c34de9a0...`.

- [ ] **Step 4: Commit**

```bash
git add \
  tests/live \
  docs/design/MACRO_FRED_PRODUCT_SEMANTICS.md \
  tests/test_fred_ingestion.py \
  docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md
git commit -m "refactor: move manual live smokes to tests"
```

---

### Task 2: Extract Research Knowledge And Retire Paid/Research Utilities

**Files:** Section 1.2 paths.

- [ ] **Step 1: RED-first inventory checks**

Prove the two destination documents and history directory do not yet exist.
Capture the 24 endpoint literals from source without executing either probe.
Require exactly 24 unique paths and exactly the Section 3.2 set.

- [ ] **Step 2: Create the static Financial Datasets decision input**

Write `docs/design/FINANCIAL_DATASETS_CAPABILITY_SPEND_DECISION.md` with the
Section 3.2 contract. Update all three evaluation documents to link to this
dated static input instead of advertising a runnable probe. In both paid
evaluation formats, label the nonexistent
`scripts/collection/collect_ibkr_fundamentals.py` examples as historical
pre-consolidation instructions; do not invent a replacement collector or imply
that current collection exists.

- [ ] **Step 3: Move provenance and extract compact historical knowledge**

Use `git mv` for both HuggingFace Markdown files. Create
`docs/history/SCRIPTS_RETIREMENT_TRANCHE_A.md` with the visualization,
diagnostic, unusual-options, migration-owner, and scoring-lineage sections in
Section 3.3. Update all moved links. Remove the obsolete
`scripts/huggingface/output/` ignore rule.

- [ ] **Step 4: Delete only the approved Task 2 executables**

Delete:

```text
scripts/analysis/scan_unusual_activity.py
scripts/huggingface/merge_for_release.py
scripts/testing/test_financial_datasets_api.py
scripts/testing/test_financial_datasets_api_retry.py
scripts/visualization/README.md
scripts/visualization/data_loader.py
scripts/visualization/news_dashboard.py
```

The diagnostic probe remains until Task 3.

- [ ] **Step 5: Prove exact `-2/+0`**

Recollect and require:

```text
4728
49e4a32b5f536cea97053578f2fba4456ffbbe0c10a4b66540c4f26d2b55329f
```

Use `comm` against the base stream. The only removed IDs must be the two
Section 2.2 paid-probe IDs. Run Markdown link validation used by the repository
and `git diff --check`.

- [ ] **Step 6: Commit**

```bash
git add \
  .gitignore \
  scripts/analysis/scan_unusual_activity.py \
  scripts/huggingface/SCORING_PROMPTS.md \
  scripts/huggingface/column_mapping.md \
  scripts/huggingface/merge_for_release.py \
  scripts/scoring/README.md \
  scripts/testing/test_financial_datasets_api.py \
  scripts/testing/test_financial_datasets_api_retry.py \
  scripts/visualization/README.md \
  scripts/visualization/data_loader.py \
  scripts/visualization/news_dashboard.py \
  docs/design/FINANCIAL_DATASETS_CAPABILITY_SPEND_DECISION.md \
  docs/history/SCRIPTS_RETIREMENT_TRANCHE_A.md \
  docs/history/news-scoring/SCORING_PROMPTS.md \
  docs/history/news-scoring/column_mapping.md \
  docs/history/FNSPID_NEWS_EXTRACTION.md \
  docs/data/NEWS_DATA_INVENTORY.md \
  docs/data/OPTIONS_PRICING_THEORY.md \
  data_sources/PAID_SUBSCRIPTION_EVALUATION.md \
  data_sources/PAID_SUBSCRIPTION_EVALUATION.tex \
  data_sources/DATA_SOURCES_EVALUATION.md \
  docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md
git commit -m "chore: retire scripts research utilities"
```

---

### Task 3: Retire The Fixed IBKR Diagnostic Probe

**Files:**
- Delete: `scripts/diagnostics/probe_ibkr_news_bodies.py`
- Modify: `tests/test_news_normalized_ibkr_adapter.py`
- Modify: historical/evidence docs as needed

- [ ] **Step 1: Prove the deletion boundary**

Run the adapter file before editing and require 20 passing nodes. Record that
exactly three IDs import/verify the spent executable while 17 adapter contract
nodes do not need it.

- [ ] **Step 2: Remove exactly three tests and the probe**

Delete the three Section 2.2 functions and the probe file. Do not alter any
adapter implementation or the other 17 tests.

- [ ] **Step 3: Prove exact stage identity**

```bash
pytest -q tests/test_news_normalized_ibkr_adapter.py
```

Expected:

```text
17 passed
```

Recollect and require:

```text
4725
64ce4a619039fa586f065533b900416b1fd3fcbf6d78a99a43c9295a02a83e1d
```

`comm` must show only the two paid-probe IDs plus the three diagnostic IDs
missing from base.

- [ ] **Step 4: Commit**

```bash
git add \
  scripts/diagnostics/probe_ibkr_news_bodies.py \
  tests/test_news_normalized_ibkr_adapter.py \
  docs/history/SCRIPTS_RETIREMENT_TRANCHE_A.md \
  docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md
git commit -m "chore: retire IBKR news diagnostic probe"
```

---

### Task 4: Retire Spent Migration Gates Atomically

**Files:** Section 1.3 paths plus legacy evidence and history map.

- [ ] **Step 1: Reprove no live source consumer**

Before deleting, run a consumer census for each of the eight domain cores and
eleven CLIs. Current runtime modules under `src/` may not import any target.
The only allowed executable consumers are the twelve test files being removed.
Current docs may point to existing historical owners but may not require a
target as a supported operator command.

Any unclassified live consumer stops this task and requires a plan amendment.

- [ ] **Step 2: Reclassify rollback before removing its tool**

Apply Section 3.4 to the legacy scheduler/IV evidence. Record the existing
manifest identity:

```text
30c01ea8fd009a3d47c5ac96ffd4dd9b0282a1adef03faafb91c3dd50dd92fad
```

Do not inspect or modify ignored archive bytes.

- [ ] **Step 3: Delete exact migration files**

Delete the eleven CLIs, eight domain cores, and twelve whole test files from
Sections 1.3 and 2.3. Keep:

```text
src/news_normalized/score_import.py
tests/test_news_score_import.py
scripts/scoring/import_news_scores_local.py
```

- [ ] **Step 4: Prove exact final collection**

Recollect and require:

```text
4553
69152591306a8dee5e66e2efeb2f1ec12720c8a1a1ffe36def613f4fe5a676ca
```

`comm` against base must show exactly 177 removed and zero added. Compare the
removed stream with the pre-reviewed `/tmp/scripts-a-final.nodes` derivation.

Run:

```bash
pytest -q \
  tests/test_news_score_import.py \
  tests/test_score_ibkr_keys.py \
  tests/test_scoring_api_routing.py \
  tests/test_scoring_continue_from.py \
  tests/test_news_normalized_ibkr_adapter.py \
  tests/test_legacy_iv_retirement_boundaries.py
```

Expected retained score count is 36 and adapter count is 17; all selected nodes
must pass. No historical migration test may remain collected.

- [ ] **Step 5: Prove current imports and package markers**

```bash
test -f scripts/__init__.py
test -f scripts/scoring/__init__.py
test -f scripts/scoring/import_news_scores_local.py
test -f src/news_normalized/score_import.py
test ! -d scripts/migration
```

Run `python -m compileall -q src scripts/scoring`.

- [ ] **Step 6: Commit**

```bash
git add \
  scripts/migration/apply_news_normalization.py \
  scripts/migration/job_runs_local_cutover.py \
  scripts/migration/n9_batch1_pg_drop.py \
  scripts/migration/n9_batch2_cleanup.py \
  scripts/migration/n9_batch3_prices_drop.py \
  scripts/migration/news_n8a_cutover.py \
  scripts/migration/news_scores_cutover.py \
  scripts/migration/p0c_hapn_patch.py \
  scripts/migration/p0c_prices_reconcile.py \
  scripts/migration/preview_news_normalization.py \
  scripts/migration/retire_legacy_scheduler_iv.py \
  src/service/job_runs_cutover.py \
  src/prices_patch.py \
  src/prices_reconcile.py \
  src/news_normalized/migration.py \
  src/news_normalized/migration_policy.py \
  src/news_normalized/migration_apply.py \
  src/news_normalized/cutover.py \
  src/news_normalized/score_cutover.py \
  tests/test_job_runs_cutover.py \
  tests/test_legacy_scheduler_iv_retirement.py \
  tests/test_n9_batch1_pg_drop.py \
  tests/test_n9_batch2_cleanup.py \
  tests/test_n9_batch3_prices_drop.py \
  tests/test_news_n8a_cutover.py \
  tests/test_news_normalization_apply.py \
  tests/test_news_normalization_migration.py \
  tests/test_news_scores_cutover_apply.py \
  tests/test_news_scores_cutover_cli.py \
  tests/test_prices_patch.py \
  tests/test_prices_reconcile.py \
  docs/history/SCRIPTS_RETIREMENT_TRANCHE_A.md \
  docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md \
  docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md
git commit -m "chore: retire spent migration gates"
```

---

### Task 5: Reconcile Current Authorities And Final Tranche A Tree

**Files:** Section 1.4 paths and current-link owners in Section 1.2.

- [ ] **Step 1: Update current layout and survivor authorities**

Apply Section 3.5. The interim survivor rule must list the exact nine remaining
paths, not broad directories. It must say Tranche B owns final root removal.

- [ ] **Step 2: Fix broken current instructions**

Make these exact semantic changes:

- `training/data_prep/state_builder.py`: tell the user to re-export or retrain a
  model with required schema metadata;
- `training/model_registry.py`: describe required schema metadata without a
  nonexistent patch script;
- `training/rl/inference.py`: same recovery direction in its exception docs;
- `training/scripts/rl_vlite_rerun.sh`: remove the nonexistent extraction
  command and retain TensorBoard/`monitor.csv` as the supported telemetry;
- OAuth files: label the Novelloom path as upstream historical provenance; and
- Docker: label N9 CLIs as historical evidence;
- `docs/data/IBKR_NEWS_API_LIMITATIONS.md` and
  `docs/data/NEWS_PROVIDER_DATA_DICTIONARY.md`: mark old collection commands as
  pre-consolidation history and direct operators to the current app-owned
  scheduler/settings surface without fabricating a replacement CLI;
- `docs/design/SA_EXTENSION_ROADMAP.md`: mark the removed density script command
  as completed historical evidence; and
- `docs/design/RL_COLLAPSE_FINDINGS.md`: mark the removed metrics extractor as
  historical and retain TensorBoard/`monitor.csv` as supported telemetry.

Do not change `training/data_prep/prepare_training_data.py`, `training/README.md`,
`src/daily_update.py`, Tool Catalog, Desktop carry-over, config authority, or
credential authority in Tranche A because their scoring owner still exists.

- [ ] **Step 3: Prove the exact physical tree**

```bash
git ls-files scripts | LC_ALL=C sort \
  > /tmp/scripts-retirement-tranche-a/tranche-a-scripts.paths
```

Require byte-for-byte:

```text
scripts/__init__.py
scripts/scoring/README.md
scripts/scoring/__init__.py
scripts/scoring/import_news_scores_local.py
scripts/scoring/openai_summary.py
scripts/scoring/score_ibkr_news.py
scripts/scoring/score_risk_anthropic.py
scripts/scoring/score_sentiment_anthropic.py
scripts/scoring/validate_scores.py
```

No empty retired subdirectory, wrapper, tombstone, symlink, or compatibility
module may remain.

- [ ] **Step 4: Build a classified old-path census**

Search tracked current code/docs for:

```text
scripts/
scripts/analysis/
scripts/diagnostics/
scripts/collection/
scripts/huggingface/
scripts/live/
scripts/migration/
scripts/p1_2/
scripts/testing/
scripts/visualization/
scripts.migration
scripts.diagnostics
```

Classify every remaining hit as one of:

```text
historical_record
upstream_provenance
rejected_old_path
non_root_owner
```

There may be no `current_runnable` hit. Current layout files, runbooks, source
docstrings, tests, and provider evaluations must use final Tranche A owners.
Historical specs/plans/evidence may retain dated paths.
App-relative paths such as `apps/arkscope-web/scripts/i18n/` and nested owners
such as `training/scripts/` are not root `scripts/` consumers; record them as
`non_root_owner` rather than rewriting them.

- [ ] **Step 5: Reprove secret and score boundaries**

Repeat only metadata checks from Task 0 for `config/scoring_keys.txt`; do not
read or hash its content. Run the 36 retained scoring nodes and require all
pass. Prove these files are byte-identical to Task 0 unless only the reviewed
relative provenance links in `scripts/scoring/README.md` changed:

```text
scripts/scoring/import_news_scores_local.py
scripts/scoring/openai_summary.py
scripts/scoring/score_ibkr_news.py
scripts/scoring/score_risk_anthropic.py
scripts/scoring/score_sentiment_anthropic.py
scripts/scoring/validate_scores.py
src/daily_update.py
src/news_normalized/score_import.py
docs/design/ARKSCOPE_TOOL_CATALOG.md
docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md
```

- [ ] **Step 6: Commit**

```bash
git add \
  README.md \
  PROJECT_STRUCTURE.md \
  docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md \
  docs/design/REPO_HYGIENE_B6_MODULE_DISPOSITION.md \
  docker/README.md \
  src/auth_drivers/chatgpt_oauth_probe.py \
  docs/design/LLM_AUTH_DRIVER_PLAN.md \
  docs/design/RL_COLLAPSE_FINDINGS.md \
  docs/design/SA_EXTENSION_ROADMAP.md \
  docs/data/IBKR_NEWS_API_LIMITATIONS.md \
  docs/data/NEWS_PROVIDER_DATA_DICTIONARY.md \
  training/data_prep/state_builder.py \
  training/model_registry.py \
  training/rl/inference.py \
  training/scripts/rl_vlite_rerun.sh \
  docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md
git commit -m "docs: reconcile scripts tranche A authorities"
```

---

### Task 6: Canonical Admission And Review Packet

**Files:**
- Modify: evidence
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Reproduce final collection**

Require:

```text
4553
69152591306a8dee5e66e2efeb2f1ec12720c8a1a1ffe36def613f4fe5a676ca
```

Reporter collection, the precomputed target stream, and a fresh
`pytest --collect-only` stream must be byte-identical.

- [ ] **Step 2: Run focused structural and retained-contract gates**

Run:

```bash
pytest -q \
  tests/test_news_score_import.py \
  tests/test_score_ibkr_keys.py \
  tests/test_scoring_api_routing.py \
  tests/test_scoring_continue_from.py

pytest -q tests/test_news_normalized_ibkr_adapter.py

pytest -q \
  tests/test_sqlite_backend.py \
  tests/test_fundamentals_sec_cache.py \
  tests/test_news_scores.py \
  tests/test_db_backend.py

python -m compileall -q src scripts/scoring tests/live
git diff --check 24202182...HEAD
```

Expected:

```text
36 passed
17 passed
94 passed, 18 skipped
```

- [ ] **Step 3: Run native final admission**

Use a fresh exact-tip worktree with:

- no `config/.env`;
- an existing empty `data/`;
- no project DB, historical dataset, provider credential, or production-root
  symlink;
- only the pinned `node_modules` toolchain link; and
- unchanged wrapper/reporter/wakeup-probe identities.

Run:

```bash
/tmp/eir002-green-baseline/run_native.sh scripts-a-final-full
```

Require:

```text
4553 collected
4553 seen
4481 passed
72 skipped
0 failed
0 errors
exitstatus 0
empty non-passing SHA:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

The run is invalid if reporter `seen_node_ids` differs from
`collected_node_ids`, regardless of terminal prose.

- [ ] **Step 4: Reconcile generated artifacts**

Use the EIR-002 pre/post ordinary status, ignored status, `data`, `src/data`,
and symlink inventory protocol. Record exact path, inode, size, mtime, and
SHA-256 for each new path, quarantine by exact path, and prove byte-identical
restoration. Never glob or match by basename. Any modified pre-existing file
is a Stop Condition.

- [ ] **Step 5: Complete evidence**

Evidence must contain:

- reviewed authority/plan SHAs;
- all four collection identities;
- exact 159-node disposition and 54-node domain-core ledger;
- every structural RED/GREEN result;
- exact endpoint inventory proof with no provider call during Task 2 static
  extraction;
- the rejected Task 0 request observation, kept separate from classification
  and from the admitted provider-safe base;
- dated official pricing/billing/no-balance-interface observations and the
  separately scoped product-policy requirements from Section 3.2;
- old-path classified census;
- secret metadata-only checks;
- retained score/adapter/protected results;
- provider-safe native base and final reporter JSON plus their empty
  non-passing sets;
- artifact manifests and quarantine transactions; and
- protected main-draft SHA before and after.

Set status to `IMPLEMENTATION REVIEW READY`. Add the newest-first priority-map
entry. Do not claim final root `scripts/` retirement; Tranche B remains open.

- [ ] **Step 6: Commit and stop for independent review**

```bash
git add \
  docs/superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: prepare scripts tranche A review"
git status --short --untracked-files=all
```

Do not merge before independent implementation review reproduces the collection
delta, current tree, retained gates, old-path census, and native admission.

---

### Task 7: Reviewed Merge And Tranche A Checkpoint

- [ ] **Step 1: Require independent implementation review**

The reviewer must independently reproduce:

- physical collect-only base `4730/c34de9a0...`;
- provider-safe native base `4728/49e4a32b...` with
  `4656 passed / 72 skipped / 0 failed`, exact two-file exclusion, and no
  `comparison_results/`;
- final `4553/69152591...`;
- exact `+0/-177`;
- 159 direct dispositions and 54 additional domain nodes;
- final nine-path `scripts/` tree;
- 36 retained scoring nodes and 17 retained adapter nodes;
- protected `94 passed / 18 skipped`;
- native `4481 passed / 72 skipped / 0 failed`; and
- zero provider, production-data, archive, or secret operation in every
  admitted run, with the rejected request-bearing attempt reported separately.

- [ ] **Step 2: Fast-forward master to the exact reviewed tip**

Verify linear ancestry from `24202182` and use `git merge --ff-only`. Do not
stage or overwrite the protected main-worktree draft. If that untracked path
would block checkout, compare its SHA to `79d4eac9...`, move it reversibly to a
unique `/tmp` quarantine path with inode/size/mtime/SHA evidence, fast-forward,
then keep the committed authority as the sole current file. Do not delete the
draft without preserving that transaction.

- [ ] **Step 3: Run merged verification from a fresh exact-master worktree**

Repeat Task 6 collection, focused gates, native full admission, and artifact
transaction. Use new single-use wrapper stage names. Do not run canonical
admission in the data-bearing production root.

- [ ] **Step 4: Record `SCRIPTS_TRANCHE_A_TIP`**

Record the exact reviewed implementation tip in authority/evidence and the
priority map. State:

```text
Tranche A complete
Tranche B not started
root scripts/ intentionally remains only for scripts/scoring/
no production score data or local secret changed
```

Commit docs-only closeout after focused review. Do not begin Tranche B without
its separate score-consumer/product-data spec and approval.

---

## 5. Stop Conditions

Stop immediately if:

1. authority, base report, wrapper, reporter, or wakeup-probe identity differs;
2. base collection is not exact `4730/c34de9a0...`;
3. any of the 159 directly coupled nodes is unclassified or duplicated;
4. any of the 36 score nodes changes identity or result in Tranche A;
5. target construction is not exact `4553/69152591...` before edits;
6. collection differs from exact `+0/-177`;
7. a moved live smoke enters default pytest collection;
8. after this amendment, any admitted run touches a provider, Gateway,
   scheduler, paid endpoint, or production DB;
9. `config/scoring_keys.txt` content is read, hashed into evidence, moved,
   altered, staged, or deleted;
10. a live source consumer of a migration core/CLI is found;
11. `src/news_normalized/score_import.py` or a current score consumer is
    removed or behaviorally changed;
12. archive bytes or ignored `RESTORE.txt` change;
13. a current runbook still offers a removed executable;
14. a historical path is silently rewritten so dated evidence loses truth;
15. a wrapper, tombstone, symlink, empty retired directory, or generic
    replacement dumping ground is introduced;
16. EIR-006, old price CSV deletion, scanner dead-code work, calendar-aware
    scheduling, extended-hours capture, or provider-outcome work enters scope;
17. canonical full admission is attempted in the incompatible managed sandbox;
18. native reporter sees fewer nodes than it collected;
19. a pre-existing ignored/user file changes during verification;
20. an unaccounted repository-relative artifact remains; or
21. an admitted provider-safe run creates `comparison_results/`, or its
    collected stream differs from exact `4728/49e4a32b...`;
22. the rejected unfiltered Task 0 report, transcript, or quarantine is
    overwritten, deleted, or promoted into the A/B ledger; or
23. the protected main-worktree draft is modified or lost without the exact
    reviewed quarantine/identity transaction.

## 6. Plan Self-Review Map

| Decision requirement | Owning task |
|---|---|
| Authority re-grounded before execution | Task 0 |
| Exact 159-node direct disposition | Task 0 / Section 2.2 |
| Final target hash derived before deletion | Task 0 / Section 2.1 |
| Manual live checks preserved but never collected | Task 1 |
| Financial Datasets static knowledge extracted without a provider call | Task 2 |
| Rejected request-bearing base separated from provider-safe admission | Task 0 |
| Metered-provider policy recorded but implementation deferred | Task 2 / separate product slice |
| HuggingFace prompts/mapping retained as history | Task 2 |
| Visualization and unusual-options knowledge retained, code removed | Task 2 |
| Diagnostic executable leaves; adapter behavior stays | Task 3 |
| Migration executable/core/tests retire together | Task 4 |
| Legacy archive becomes lineage-only; bytes untouched | Task 4 |
| Transitional scorer and credential owner retained | Tasks 0-6 |
| Current authorities use final Tranche A owners | Task 5 |
| Broken local instructions are not left runnable-looking | Task 5 |
| Final tree is exact nine paths | Task 5 |
| Exact `+0/-177` and full-green native admission | Task 6 |
| Independent review before merge | Task 7 |
| Tranche B remains a separate atomic product/data decision | All tasks |
