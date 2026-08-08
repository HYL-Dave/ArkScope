# Provider Smoke Hygiene and Tiingo Tail Retirement Design

> **Status: DRAFT AMENDED - focused independent re-review required; no implementation is authorized.**
>
> **Date:** 2026-08-08
> **Base:** `6159fc14` (`OAuth lifecycle + subscription usage truth LIVE COMPLETE`)
> **Scope:** canonical-test hygiene, spent yfinance option helpers, one spent provider-comparison diagnostic, retirement of the unconsumed Tiingo implementation, and a truthful future-candidate record.
>
> **Review history:** commit `156db68c` passed independent design review under
> the earlier adapter-preservation decision. The user then clarified that future
> reconsideration does not require retaining today's unused implementation. This
> amendment supersedes only that Tiingo disposition and requires focused re-review
> before an implementation plan may be written.

## 1. Purpose

The canonical suite currently reports green while thirteen collected provider
nodes either call public services or return `False` to pytest as a non-failing
return value. A second path in `tests/test_rate_curve.py` reaches yfinance
indirectly and creates `src/data/cache/risk_free_rate.json` during native
admission.

This slice removes those false contracts and the unconsumed Tiingo executable tail
without pretending that Tiingo has been permanently rejected. Tiingo remains a
possible future provider, but that possibility is represented by a concise
re-evaluation record rather than adapter, registry, credential-template, or test
code. Any eventual admission is a new product and spend decision based on
then-current API, SDK, pricing, licensing, and scheduler evidence.

## 2. Grounded facts

### 2.1 Canonical provider smokes

1. Current backend collection is exactly `4607` node IDs with SHA-256
   `5180502f7dfe577ca758db5fb8ebdfe9ca282730a8976adcf65b7ab19c1c2d74`.
2. `tests/test_yfinance.py` contributes seven nodes and
   `tests/test_tiingo.py` contributes six. Both files entered in
   `a8970e64` on 2026-01-10 as API evaluation scripts.
3. The functions catch provider errors and return booleans. Pytest 8 warns with
   `PytestReturnNotNoneWarning`; a returned `False` is still counted as a passed
   node. Tiingo also reads a real key and may load `.env` during collection/import.
4. The existing `tests/live/` contract is the correct home for explicitly invoked
   credentialed/network smokes. Files there are not named `test_*.py`, are never
   part of admission, and must return a meaningful process exit code.

### 2.2 Hidden yfinance path

1. Six existing nodes in `tests/test_rate_curve.py` call
   `get_yield_curve()` or `get_risk_free_rate()` without a provider fake.
2. Those functions import yfinance, query public Yahoo endpoints, and may persist
   `src/data/cache/risk_free_rate.json`. Historical native admissions repeatedly
   had to quarantine that exact artifact.
3. An uncapped non-test caller census finds no consumer of
   `get_yield_curve`, `get_rate_for_dte`, or `get_risk_free_rate` outside their
   defining modules and package exports. Current `src/tools/options_tools.py`
   receives a rate from its caller and imports only the surviving pure pricing
   functions.
4. All 34 `tests/test_rate_curve.py` nodes therefore protect an unconsumed API.
   The correct no-tail action is retirement, not mocks that keep dead behavior
   green.

### 2.3 Yfinance still has one owned capability

`training/preprocessor.py` and
`training/data_prep/prepare_training_data.py` use yfinance. Current authorities
classify `training/` as paused-preserve reproducible research. Consequently
`requirements.txt` and those training paths remain owned and are not retirement
targets in this slice.

### 2.4 Tiingo is unconsumed executable residue, not product-live

1. `data_sources/tiingo_source.py`, `DataSourceType.TIINGO`, package exports,
   generic source-factory registration, and a credential template exist.
2. There is no Tiingo scheduler definition, collector, API route, provider-health
   row, Settings field, or frontend consumer.
3. `config/user_profile.yaml` says `fallback: "tiingo"`, but no runtime reader of
   `data_preferences.price_sources` exists. The line is stale declarative text,
   not a working fallback.
4. `ARKSCOPE_PROVIDER_CATALOG.md` nevertheless labels Tiingo `live`, says it is
   the current EOD fallback, and lists Settings fields that do not exist. Those
   claims are false in the current tree.
5. `data_sources/collect_aapl_comparison_data.py` is an uncalled 701-line dated
   comparison diagnostic that directly probes Tiingo, yfinance, and other
   providers and writes ignored output. It is not a scheduler or admission tool.
6. An uncapped non-document caller census finds no current consumer of the Tiingo
   adapter, enum member, factory registration, or key template beyond the six
   January evaluation nodes and that spent diagnostic. Retaining these executable
   surfaces would therefore preserve an ownerless integration, not a capability.

### 2.5 Exact retirement ledger

The retirement set is exactly 47 existing node IDs:

| Owner | Nodes | Disposition |
|---|---:|---|
| `tests/test_yfinance.py` | 7 | leave canonical; replace with an explicit manual live smoke |
| `tests/test_tiingo.py` | 6 | retire with the unconsumed Tiingo implementation; no replacement smoke |
| `tests/test_rate_curve.py` | 34 | retire with the unconsumed rate-curve API |

Removing those exact IDs from the reviewed base stream produces:

| Stream | Base | Target | Delta |
|---|---|---|---:|
| canonical backend | `4607 / 5180502f7dfe577ca758db5fb8ebdfe9ca282730a8976adcf65b7ab19c1c2d74` | `4560 / 689e3a92ddd1977c381c08ab68eb42fe8a110d54da491e1a7ca50100374f8f71` | `-47/+0` |
| retired IDs | n/a | `47 / bb82b7aaaefde021c24c9cd8d6234922d9efbf756c507112604c9cf25ada2142` | exact set |

All 47 currently pass in native admission. With no other node change, the native
target is `4488 passed / 72 skipped / 0 failed`.

### 2.6 Census execution boundary

Caller and current-authority census was performed against the unlocked main tree.
The isolated implementation worktree may use locked git-crypt bytes with no-op
filters, but a text search in that worktree is not authority for encrypted files.
Every implementation census must enumerate `.gitattributes`-encrypted paths and
either inspect them in the unlocked tree or classify them explicitly as unreadable;
it may not silently treat ciphertext as no match.

### 2.7 Current-authority and historical-reference boundary

The Tiingo cutover has two distinct documentation classes:

1. Current authorities must change with the code: `PROJECT_STRUCTURE.md`,
   `docs/design/ARKSCOPE_PROVIDER_CATALOG.md`,
   `docs/design/ARKSCOPE_TOOL_CATALOG.md`,
   `docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md`, and the paused-preserve
   training README must not describe Tiingo as an installed client, connected
   provider, price fallback, or implemented training source.
2. Dated evaluations, API research, paid-subscription studies, closed plans and
   evidence may retain historical Tiingo references. They are not current
   capability authority and are not rewritten to simulate that the experiment
   never existed.
3. `tests/test_finnhub_sentiment.py` is already owned by the reviewed Tranche B
   atomic retirement and is not edited here. Its dated recommendation strings are
   neither runtime provider configuration nor authority for retaining Tiingo.

Implementation must produce a complete, unlocked-tree reference census with one
closed verdict per tracked Tiingo hit: `retire_executable`,
`update_current_authority`, `historical_reference`, or
`queued_tranche_b_retirement`. Unknown or multiply classified paths stop the slice.

## 3. Locked decisions

### LD 1 - Canonical admission does not perform these provider smokes

The two January evaluation files leave pytest collection. The yfinance evaluation
is replaced by standalone `tests/live/smoke_yfinance.py`, run only by explicit
user/operator choice and never by collect-all, full admission, import-time hooks,
preflight, or Settings page load. There is no Tiingo replacement smoke because no
current Tiingo implementation remains to exercise.

The yfinance command must fail with a non-zero exit code when a requested response
is empty/malformed or any selected check fails. It may not repeat the pytest
boolean-return anti-pattern. The live README must state network and
current-provider-terms preconditions.

### LD 2 - Dead rate acquisition leaves completely

Delete `src/options_math/rate_curve.py`, `tests/test_rate_curve.py`, and the
unconsumed yfinance-backed risk-free-rate cache/fetch block in
`src/options_math/option_pricing.py`. Remove their package exports; do not add a
shim, re-export, fallback constant, or compatibility wrapper.

The surviving option-pricing formulas and tools keep their existing caller-owned
`risk_free_rate` contract. If a future options workflow needs a current curve, it
must start from an actual consumer and a reviewed authority/provenance/freshness
contract rather than reconnecting this retired Yahoo path.

### LD 3 - Training yfinance remains explicitly owned

Do not remove yfinance from requirements or rewrite the paused-preserve training
pipeline in this slice. The live yfinance smoke is a manual dependency check for
that research owner; it is not proof of production support.

### LD 4 - Retire the current Tiingo implementation; preserve only reconsideration

Delete `data_sources/tiingo_source.py`; remove its package export,
`DataSourceType.TIINGO`, generic factory registration and environment mapping,
`TIINGO_API_KEY` template, unread profile fallback, six-node evaluation file, and
spent comparison diagnostic. Do not add a shim, disabled registry entry, dormant
credential field, manual smoke, compatibility alias, or archived code copy.

The Provider Catalog retains one concise non-implementation candidate record:
Tiingo has no current code, configuration, scheduler, API/UI surface, health row,
or adoption decision, and may be re-evaluated only when a concrete EOD/historical
capability gap exists. Current/live/supporting-provider tables and other current
authorities must not list it as connected. Dated research documents and git history
may retain historical references; this slice does not rewrite history merely to
erase the provider name.

This is retirement of the current integration, not permanent rejection of the
provider. A future admission must implement against then-current interfaces and
pass LD 5 rather than restoring this code.

### LD 5 - Future providers use one admission standard

The existing Provider Catalog admission rubric remains authority and is clarified
to require evidence for the intended capability, not provider-name enthusiasm.
Tiingo and every future candidate must be judged on:

1. whether the free tier covers the intended personal-use workload;
2. paid price versus measurable value when free coverage is insufficient;
3. unique/non-duplicative information or a concrete reliability gap it fills;
4. rate limits, latency, stability, freshness, provenance, and error semantics;
5. licensing/cache/retention constraints;
6. fit with the local DB schema, scheduler, reconciliation, and truthful partial
   outcomes; and
7. an explicit enable/spend switch plus honest usage/cost visibility for metered
   capabilities.

Pricing, limits, and tier names must be re-verified when an admission slice opens.
This 2026-08-08 cleanup does not make current market claims about Tiingo.

### LD 6 - The spent comparison diagnostic is deleted

Delete `data_sources/collect_aapl_comparison_data.py`. Git history is the record of
the old one-off comparison. A future provider decision needs a new reviewed,
capability-scoped evaluation harness with explicit network/spend controls; the old
all-provider script is not that harness.

Ignored `data_sources/comparison_data/` files are existing local artifacts and are
not modified or deleted by this tracked-code slice. Any physical cleanup of those
untracked files requires an exact inventory and separate owner approval.

## 4. Required implementation gates

1. Structural RED first: the three collected test files, retired rate APIs,
   diagnostic, Tiingo adapter/export/enum/factory/key/profile surfaces, and absent
   yfinance live-smoke target must exhibit the pre-change state before edits.
2. Collection after implementation is exactly
   `4560 / 689e3a92ddd1977c381c08ab68eb42fe8a110d54da491e1a7ca50100374f8f71`.
   The 47-ID difference is exactly
   `bb82b7aaaefde021c24c9cd8d6234922d9efbf756c507112604c9cf25ada2142`.
3. `tests/live/` contributes zero canonical nodes. The new yfinance script compiles
   and its help/argument paths perform no network access. No Tiingo smoke exists.
4. Python yfinance imports after cutover are confined to paused-preserve training
   and the explicit manual yfinance smoke. No canonical test or product runtime
   option helper imports it.
5. Surviving option-pricing/tool tests pass, and no import/re-export of retired rate
   symbols remains outside dated historical documents.
6. Static census proves the Tiingo adapter, package export, enum, factory
   registration/environment mapping, credential template, profile fallback,
   diagnostic, and canonical/live smoke are absent. Current product authorities
   contain no connected/live/fallback claim; only the bounded candidate
   re-evaluation record remains. Historical references are classified rather than
   swept by raw string deletion.
7. Fresh native canonical admission observes all 4,560 nodes and returns
   `4488 passed / 72 skipped / 0 failed`; generated-artifact handling follows the
   established exact-path transaction.
8. No provider smoke is executed during implementation or admission. The yfinance
   manual smoke is reviewed structurally and through help/offline paths only.
9. The post-cutover unlocked-tree Tiingo census is a closed projection of the
   pre-cutover census: zero unknown paths, zero current authority claiming an
   installed capability, and only the catalog candidate record, classified dated
   history, and the separately owned Tranche B file remain.

## 5. Protected boundaries

This slice does not change:

- any scheduler, collector, API route, provider-health projection, or Settings UI;
- non-Tiingo source-factory registrations, provider enums, package exports, and
  credential templates;
- paused-preserve training behavior or the yfinance dependency;
- production databases, credentials, ignored comparison outputs, provider keys, or
  live provider state;
- OAuth lifecycle/quota truth, Financial Datasets metered policy, Tranche B owners,
  or the future Settings navigation slice.

Tranche B absolute collection identities are intentionally re-derived only after
this slice and Settings navigation have merged, so that its implementation rebases
once.

## 6. Stop conditions

Stop and amend before continuing if:

1. any non-test consumer of the retired rate APIs is found;
2. Tiingo is found in a real scheduler/API/UI path not listed here;
3. collection differs from exact `-47/+0` or any unrelated node changes identity;
4. a manual smoke becomes auto-run or is collected by pytest;
5. implementation needs a real key, provider request, or current paid entitlement;
6. a change would remove training yfinance, an unrelated provider integration, or
   a local ignored comparison artifact;
7. catalog correction is used to claim Tiingo is permanently rejected, or a
   dormant executable/configuration tail is retained solely for possible reuse; or
8. a locked-worktree grep is used as whole-tree consumer evidence; or
9. Tranche B, OAuth, Settings navigation, or provider-adoption implementation enters
   the diff; or
10. a current authority or paused-preserve training guide would retain Tiingo as an
    implemented source after its code/configuration is removed.

## 7. Review and handoff

Focused independent re-review must reconstruct the caller census, unchanged 47-ID
ledger and target hash, Tiingo product-surface absence, exact executable/config
retirement set, training authority, and current-authority versus historical-reference
boundary from the tree. Only after GREEN may an exact RED-first implementation plan
be written.
