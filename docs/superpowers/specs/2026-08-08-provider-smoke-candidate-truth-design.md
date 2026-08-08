# Provider Evaluation Hygiene and Tiingo Tail Retirement Design

> **Status: COMPLETE ON MASTER AT `b991f543`; FOCUSED CLOSEOUT REVIEW REQUIRED.**
>
> **Date:** 2026-08-08
> **Base:** `6159fc14` (`OAuth lifecycle + subscription usage truth LIVE COMPLETE`)
> **PROVIDER_HYGIENE_CUTOVER_TIP:** `b991f543807751757fc7dd78adcba1ecbda90659`
> **Scope:** retirement of the complete January provider-evaluation script family,
> spent yfinance option helpers, one spent provider-comparison diagnostic, the
> unconsumed Tiingo implementation, and a truthful future-candidate record.
>
> **Review history:** commit `156db68c` passed independent design review under
> the earlier adapter-preservation decision. The user then clarified that future
> reconsideration does not require retaining today's unused implementation. This
> amendment supersedes only that Tiingo disposition and requires focused re-review
> before an implementation plan may be written. Focused re-review then found that
> `tests/test_finnhub_sentiment.py` had been incorrectly assigned to Tranche B;
> commit `e77cf19b` corrected that ownership and passed focused re-review. Plan
> grounding then enumerated the complete `a8970e64` batch and found fourteen
> additional files with the same manual-evaluation shape. The user's standing
> no-tail ruling required this bounded whole-family amendment before planning.
> Expanded amendment commit `db900ab8` then passed independent review with zero
> findings. Plan review of `cff928e5` then found that the first census had been
> generated from locked git-crypt bytes and omitted two encrypted research files
> plus the existing project decision log. This bounded amendment corrects only
> those census identities/classifications. Implementation remains unauthorized
> until focused re-review. Focused review of amendment `a9c70262` returned GREEN
> with zero findings. Task 0 then re-grounded every collection, partition,
> two-input census, protected-owner, and structural-RED identity without changing
> product/test/config/data bytes. Task 1 remains unauthorized until independent
> review of the Task 0 evidence. Task 0 review then returned GREEN at `8c47e994`.
> Task 1 retired exactly the fifteen-file January family, added one new manual
> yfinance smoke, and reproduced the exact `4561` stage plus `206/206` retained
> owner runtime. Independent Task 1 review returned GREEN at `ec140ae1`. Task 2
> then retired the unconsumed rate-curve/cache family, reproduced exact final
> collection `4527`, and kept the 75-node surviving option owner set green.
> Independent Task 2 review returned GREEN at `6bf47673`. Task 3 then removed the
> complete Tiingo executable/configuration tail, retained only a truthful
> non-implementation candidate record, reproduced exact final collection `4527`,
> kept the 281-node retained owner union green, and preserved all reviewed shared
> projections and protected owners. Implementation commit `d1adb954` now awaits
> independent Task 3 review. Independent review then returned GREEN at
> `50a5c0ac`. Task 4 proved all four structural contracts with independent
> mutations, exact owner restoration, dual-census and protected-owner closure,
> exact `4527` collect-only identity, and `280 passed / 1 skipped` focused
> runtime. Independent Task 4 review returned GREEN with zero findings. Task 5
> then reproduced every static/focused identity, completed fresh exact-tip native
> admission at `4527 seen / 4488 passed / 39 skipped / 0 failed`, and restored the
> fresh-worktree artifact boundary exactly without regenerating
> `risk_free_rate.json`. Independent Task 5 implementation review returned GREEN
> with zero findings and independently reproduced the same native result. Master
> then fast-forwarded through the reviewed 15-commit, zero-merge lineage to
> `b991f543`; fresh exact-master admission again returned
> `4527 seen / 4488 passed / 39 skipped / 0 failed`, with byte-identical reporter
> JSON and exact artifact restoration. The implementation is complete; only
> focused review of the docs-only closeout remains.

## 1. Purpose

The canonical suite currently reports green while the January provider-evaluation
batch still occupies `tests/` as a mixture of collected boolean-returning nodes,
whole-file skips, and direct-network commands that collect nothing. The batch
contributes 46 canonical node IDs: 13 pass without a valid assertion contract and
33 are permanently skipped. Six additional files contribute zero nodes. A second
path in `tests/test_rate_curve.py` reaches yfinance indirectly and creates
`src/data/cache/risk_free_rate.json` during native admission.

This slice removes those false contracts and the unconsumed Tiingo executable tail
without pretending that Tiingo has been permanently rejected. Tiingo remains a
possible future provider, but that possibility is represented by a concise
re-evaluation record rather than adapter, registry, credential-template, or test
code. Any eventual admission is a new product and spend decision based on
then-current API, SDK, pricing, licensing, and scheduler evidence.

## 2. Grounded facts

### 2.1 Complete January provider-evaluation batch

Current backend collection is exactly `4607` node IDs with SHA-256
`5180502f7dfe577ca758db5fb8ebdfe9ca282730a8976adcf65b7ab19c1c2d74`.
Commit `a8970e64` added the following still-tracked files on 2026-01-10:

| File | Canonical nodes | Current shape |
|---|---:|---|
| `tests/test_alpha_vantage.py` | 5 | whole-file manual skip |
| `tests/test_eodhd.py` | 5 | whole-file manual skip |
| `tests/test_finnhub.py` | 0 | direct-network command |
| `tests/test_finnhub_sentiment.py` | 0 | direct-network command and duplicate client |
| `tests/test_ibkr.py` | 6 | whole-file manual skip |
| `tests/test_ibkr_all_free_apis.py` | 0 | direct Gateway command |
| `tests/test_ibkr_fundamentals.py` | 3 | whole-file manual skip |
| `tests/test_ibkr_news.py` | 6 | whole-file manual skip |
| `tests/test_ibkr_options_greeks.py` | 2 | whole-file manual skip |
| `tests/test_ibkr_orats.py` | 0 | direct Gateway command |
| `tests/test_polygon.py` | 0 | direct-network command |
| `tests/test_sec_edgar.py` | 0 | direct-network command |
| `tests/test_sec_filings.py` | 6 | whole-file manual skip with import-time third-party side effect |
| `tests/test_tiingo.py` | 6 | boolean-returning direct-network nodes |
| `tests/test_yfinance.py` | 7 | boolean-returning public-network nodes |

The seven whole-file skip modules contribute 33 of the existing 72 skips. The
Tiingo/yfinance functions catch errors and return booleans; pytest warns with
`PytestReturnNotNoneWarning`, and returned `False` still counts as pass. The six
zero-node commands provide no admission contract at all.

No tracked runtime imports these files. Filename references outside the batch are
dated documentation/evidence or current documents that must be reconciled when the
paths leave. The existing `tests/live/` contract is the only valid home for an
explicitly maintained operator smoke: it is never collected and must return a
meaningful process exit code.

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

### 2.5 Evaluation-script retirement is not provider retirement

The January files directly instantiate provider/Gateway clients instead of testing
the current product seams. Their providers have one of two independent states:

1. Finnhub, Polygon, SEC EDGAR, and IBKR have current product owners such as
   adapters, normalized/calendar ingestion, routes, provider configuration/health,
   scheduler jobs, and hermetic tests. Those owners remain protected.
2. Alpha Vantage and EODHD retain adapters but have no automatic product path in
   this slice. Removing skipped evaluation modules neither admits nor retires those
   adapters; their eventual provider disposition requires its own consumer census.

The direct scripts are not maintained operational checks merely because the
underlying provider exists. Settings connection tests and current hermetic product
contracts own supported behavior. If a future deep operator diagnostic is needed,
it must be created from then-current product seams with explicit request/spend
controls, rather than preserving January code under `tests/`.

### 2.6 Exact retirement ledger

The retirement stream is exactly 80 existing node IDs:

| Owner family | Nodes | Admission state | Disposition |
|---|---:|---|---|
| January Tiingo + yfinance | 13 | passing without a valid assertion contract | leave canonical; only yfinance gets a new manual smoke |
| January whole-file manual skips | 33 | skipped | retire with the evaluation scripts |
| `tests/test_rate_curve.py` | 34 | passing | retire with the unconsumed rate-curve API |

The six zero-node January commands also leave physically but do not enter node
arithmetic. Removing the exact 80 IDs from the reviewed base stream produces:

| Stream | Base | Target | Delta |
|---|---|---|---:|
| canonical backend | `4607 / 5180502f7dfe577ca758db5fb8ebdfe9ca282730a8976adcf65b7ab19c1c2d74` | `4527 / 4eeb117804ad874c83ffe4c04fd25ecd4de4f460801bfbf95d15c1406f32455d` | `-80/+0` |
| retired IDs | n/a | `80 / a069a5af63bfcb3c6d63ddb4a25ca63bc897f97adde3ef159b83aef7b7be6fb8` | exact set |

Plan construction must also reproduce these independently checkable partitions:

| Partition | Identity |
|---|---|
| fifteen January paths | `15 / 2fff01e35f26d25c22ece520b491110b0066cf6fdccf31506fadab9f34fb30f2` |
| assertion-invalid Tiingo/yfinance nodes | `13 / 3ead0303136ab8742fae3fa15f916b2febda6088deb4f883c9b025db7d577016` |
| whole-file skipped nodes | `33 / 03f70d140bd4f2990674926904817667ed5f7ef28d10e4afbd71ea36f40aca58` |
| zero-node command paths | `6 / 9c2780536d4c05c9e40f4bbcab1583fe377565aa6663ba07055c2fcdf556f008` |
| collection after January family leaves | `4561 / dd127ce5dd34249a364b6a7965517aac66492b3d044ea8cc21e79a9706e58620` |

The 80 nodes comprise 47 current passes and 33 current skips. With no other node
change, native admission moves from `4535 passed / 72 skipped / 0 failed` to:

```text
4527 collected and seen
4488 passed
39 skipped
0 failed
```

### 2.7 Census execution boundary

Authoritative caller/current-authority census must use the unlocked main tree for
encrypted paths. The isolated implementation worktree may use locked git-crypt
bytes with no-op filters, but a text search in that worktree is not authority for
encrypted files. Every implementation census must enumerate
`.gitattributes`-encrypted paths and inspect them in the unlocked tree after
identity checks; it may not silently treat ciphertext as no match.

The original plan-grounding census violated that rule. Unlocked replay adds
`data_sources/DATA_SOURCES_EVALUATION.md`,
`data_sources/PAID_SUBSCRIPTION_EVALUATION.md`, and
`docs/design/PROJECT_PRIORITY_MAP.md` to Tiingo discovery. The first two are dated
historical research. The map is a `slice_decision_log`: it is included and
classified in complete discovery but excluded explicitly from the terminal
external-reference projection. The paid-evaluation document also contributes
three historical references to retiring IBKR evaluation paths.

### 2.8 Current-authority and historical-reference boundary

The evaluation/Tiingo cutover has two distinct documentation classes:

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
3. Current documents that name a retiring `tests/test_*.py` path must point to a
   real surviving product owner, the single yfinance live smoke, or remove the
   obsolete instruction. Closed plans/evidence retain their dated path claims.

Implementation must produce two complete unlocked-tree census streams:

- every tracked Tiingo hit receives exactly one of `retire_executable`,
  `update_current_authority`, `historical_reference`, or `slice_decision_log`;
- every external tracked reference to any of the fifteen retiring evaluation
  paths receives exactly one of `update_current_authority` or
  `historical_reference`. The retiring file's own contents and this slice's
  spec/plan/evidence are not members of that external-reference ledger; the three
  authority documents are separately classified by the existing fail-closed
  EIR-006 consumer census because they preserve dated path evidence.

The complete pre-cutover identities are 27 Tiingo paths and 13 external evaluation
references. The terminal external projections are 13 Tiingo rows (dated history
plus the bounded candidate record; the classified decision log is explicitly
excluded) and 10 historical evaluation-reference rows. Unknown, multiply
classified, or ownerless paths stop the slice. Current product code for Finnhub,
Polygon, SEC EDGAR, IBKR, Alpha Vantage, and EODHD is not part of either retirement
stream merely because its provider name also appeared in an evaluation file.

## 3. Locked decisions

### LD 1 - Canonical admission does not perform these provider smokes

All fifteen January evaluation paths leave `tests/`. Delete the spent files; do not
move their dated clients wholesale into `tests/live/`, add skip/xfail markers, or
retain zero-node commands as informal tools.

The sole replacement is a newly written `tests/live/smoke_yfinance.py` for the
explicitly preserved training dependency. It runs only by user/operator choice and
never by collect-all, full admission, import-time hooks, preflight, or Settings
page load. Current providers retain their product-owned Settings/health checks and
hermetic contracts; Tiingo has no remaining implementation to smoke.

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

1. Structural RED first: all fifteen January evaluation paths, their exact
   collect/skip/zero-node distribution, retired rate APIs, diagnostic, Tiingo
   adapter/export/enum/factory/key/profile surfaces, and absent yfinance live-smoke
   target must exhibit the pre-change state before edits.
2. Collection after implementation is exactly
   `4527 / 4eeb117804ad874c83ffe4c04fd25ecd4de4f460801bfbf95d15c1406f32455d`.
   The 80-ID difference is exactly
   `a069a5af63bfcb3c6d63ddb4a25ca63bc897f97adde3ef159b83aef7b7be6fb8`.
3. `tests/live/` contributes zero canonical nodes. The new yfinance script compiles
   and its help/argument paths perform no network access. No Tiingo smoke exists.
4. Python yfinance imports after cutover are confined to paused-preserve training
   and the explicit manual yfinance smoke. No canonical test or product runtime
   option helper imports it.
5. Surviving option-pricing/tool tests pass, and no import/re-export of retired rate
   symbols remains outside dated historical documents.
6. Static census proves all fifteen January paths and the Tiingo adapter, package
   export, enum, factory registration/environment mapping, credential template,
   profile fallback,
   diagnostic, and Tiingo canonical/live smoke are absent. Current product
   authorities contain no connected/live/fallback Tiingo claim; only the bounded
   candidate re-evaluation record remains. Historical references are classified
   rather than swept by raw string deletion. Current product owners for every
   non-Tiingo provider are byte-accounted and behaviorally unchanged.
7. Fresh native canonical admission observes all 4,527 nodes and returns
   `4488 passed / 39 skipped / 0 failed`; generated-artifact handling follows the
   established exact-path transaction.
8. No provider smoke is executed during implementation or admission. The yfinance
   manual smoke is reviewed structurally and through help/offline paths only.
9. Post-cutover unlocked-tree Tiingo and evaluation-path census streams are closed
   projections of their pre-cutover inputs: zero unknown/duplicate verdicts, zero
   stale current instructions, and only the Tiingo catalog candidate record plus
   classified dated history remain.

## 5. Protected boundaries

This slice does not change:

- any scheduler, collector, API route, provider-health projection, or Settings UI;
- non-Tiingo source-factory registrations, provider enums, package exports, and
  credential templates;
- current Finnhub, Polygon, SEC EDGAR, IBKR, Alpha Vantage, and EODHD adapters;
- calendar/normalized ingestion, collectors, schedulers, routes, provider
  configuration/health behavior, and hermetic contracts for retained providers;
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
3. collection differs from exact `-80/+0` or any unrelated node changes identity;
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
    implemented source after its code/configuration is removed; or
11. deleting an evaluation script requires changing a current provider product
    owner, or a node outside the exact 80-ID retirement stream.

## 7. Review and handoff

Independent amendment review must reconstruct the complete fifteen-file batch, its
46 collected IDs/33 skips/six zero-node commands, exact 80-ID ledger and target
hash, Tiingo product-surface absence, exact executable/config retirement set,
current provider ownership, training authority, and current-authority versus
historical-reference boundary from the tree. Only after GREEN may an exact
RED-first implementation plan be written.
