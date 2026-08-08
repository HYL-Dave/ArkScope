# Provider Evaluation Hygiene and Tiingo Tail Retirement Implementation Plan

> **Status:** DRAFT AMENDED - FOCUSED RE-REVIEW REQUIRED; NO IMPLEMENTATION AUTHORIZED
>
> **Date:** 2026-08-09
>
> **Design authority:** `db900ab8ad6a8a5651ec61c75587bec81b5ce63c`
>
> **Product grounding base:** `6159fc14956800dc04c4d6c944a2941b9c6c12db`

**Goal:** Remove the complete dated January provider-evaluation family, the
unconsumed yfinance-backed option-rate API, and the unconsumed Tiingo executable
tail while preserving current provider behavior, paused-training yfinance, and a
truthful future-provider reconsideration record.

**Architecture:** Treat the change as retirement, not compatibility migration.
Fifteen stale provider scripts leave `tests/`; only a newly written, explicit
manual yfinance smoke remains for the paused training owner. The dead rate-curve
module, its package exports, and its cache-producing fallback leave atomically.
Tiingo code/configuration/registry tails leave completely; current authorities
describe only a non-implementation candidate decision. Exact collection streams,
two unlocked-tree reference censuses, byte-protected retained providers, shared
registry projections, and native provider-free admission make collateral visible.

**Tech stack:** Git, Python 3.10, pytest, AST/static verification, Markdown, shell,
and the existing deterministic native reporter.

---

## 0. Authority and execution boundary

### 0.1 Reviewed authority

This plan implements only:

```text
docs/superpowers/specs/2026-08-08-provider-smoke-candidate-truth-design.md
reviewed commit: db900ab8ad6a8a5651ec61c75587bec81b5ce63c
reviewed blob SHA-256:
729a8e028b06fff3bbbf3533eb7a32cd98aa56bf8c07004eab4b1c6902bdc493
plan-gate status/ledger-clarification blob SHA-256:
a6aff86e77d697a04ef3e323b6948126afe12cce0562f9219d4e43b7152e0d50
census-amended design blob SHA-256:
93008b2fd05542db872486bac8180aec6573c2fbadf5516e37581765f1092593

worktree: /tmp/arkscope-provider-smoke-hygiene
branch:   codex/provider-smoke-hygiene
```

Independent design review returned GREEN with zero findings and reconstructed all
five partitions in Section 2.1. The first plan-gate commit made two bounded
authority clarifications:

1. the design status/review history now records that GREEN handoff; and
2. the evaluation-path ledger is explicitly an *external* reference ledger. A
   retiring file's self-reference is not an external consumer, while this slice's
   own spec/plan/evidence remain separately owned by the existing EIR-006 census.

Plan review then found that the initial census generator had searched locked
git-crypt bytes. Unlocked replay adds two encrypted historical documents and one
pre-existing decision-log path. This amendment changes only the census identities
and classifications in Section 2.3: it does not change a product disposition,
retirement path, node identity, collection target, protected owner, product
decision, or native target. Record all three design blob identities in Task 0
evidence before implementation.

### 0.2 No-provider execution boundary

No implementation or admission command may execute any of the fifteen January
scripts, the comparison diagnostic, `tests/test_rate_curve.py`, or the new manual
yfinance smoke. Do not supply provider credentials, start Gateway, call Yahoo,
Tiingo, Finnhub, Polygon, Alpha Vantage, EODHD, SEC EDGAR, or any paid endpoint.

Allowed validation is limited to:

- collect-only collection of the current/final suite;
- AST/text/static checks of retiring paths and the manual smoke;
- `--help` for the manual smoke after proving its provider import is lazy;
- hermetic retained-provider tests with fake/local transports;
- pure option-pricing/tool tests; and
- final native canonical admission after every public-network evaluation path and
  dead rate-fetch path has left collection.

The reviewed OAuth native report is the runtime base authority:

```text
/tmp/eir002-green-baseline/reports/oauth-merged-02f1e588-full.json
4607 collected / 4607 seen / 4535 passed / 72 skipped / 0 failed / exit 0
collection SHA-256:
5180502f7dfe577ca758db5fb8ebdfe9ca282730a8976adcf65b7ab19c1c2d74
```

Product/test bytes are unchanged from that report through `6159fc14`; subsequent
commits through `db900ab8` are docs-only. Do not rerun the unfiltered current
runtime: it would deliberately execute the provider paths this slice retires.

### 0.3 Known docs-tip RED and fresh-worktree prerequisite

Plan grounding ran the 206-node retained-provider owner set in the isolated
worktree. With the required empty `data/` root marker, it produced exactly:

```text
205 passed / 1 failed
failing node:
tests/test_eir006_retired_data_boundaries.py::test_current_runtime_consumer_census_is_closed_and_exact
```

The failure is expected structural RED: this slice's authority documents contain
the dated path `tests/test_ibkr_fundamentals.py`, and the EIR-006 fail-closed census
has not yet classified them. Before the plan existed, the first sorted unclassified
path was the design; at committed plan tip `cff928e5`, it is the plan file. Task 1
must classify this slice's spec, plan, and evidence as historical path-evidence
owners and remove the retired fixture path from `_TEST_FIXTURES`; the node identity
remains unchanged. This RED must not be described as an OAuth baseline failure or
silently excluded.

Fresh worktrees also require an existing empty `data/` directory for FileBackend
root detection. Create only that empty marker immediately before focused/native
runs, manifest it, and remove it afterward. A file under it, a pre-existing
`src/data`, or failure to remove it is a stop.

### 0.4 Native canonical boundary

Canonical admission runs outside the managed sandbox in a fresh exact-tip
worktree. Reuse, do not copy or edit, these reviewed assets:

```text
/tmp/arkscope_asyncio_wakeup_probe.py
SHA-256 10647c1e64c49fc2e082701d7a735e40782620314c125cd103a9a3f9bb37bc2e
required result {"callback_fired": true, "ready_count": 0, "wake_bytes": 0}

/tmp/eir002-green-baseline/arkscope_eir002_reporter.py
SHA-256 09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928

/tmp/eir002-green-baseline/run_native.sh
SHA-256 e7c963f1bc97125b70b435fb3c41bf4e59d501f0da561f2ef6d921c12083c84f

package-lock.json
SHA-256 5322cb03099b873066b7572c02db68a427ddc7509fdc9850cf9d8d3948a19f2c

node_modules/.package-lock.json
SHA-256 4dd5182f8111b54dd608344c45513f3b310f39321a3cc9832b60cefc2fa241ff
Node v22.14.0
```

The fresh worktree has no `config/.env`, starts with empty `data/`, has absent
`src/data`, and links only the pinned `node_modules`. Inventory ordinary/ignored
status, symlinks, `data`, and `src/data` before and after. Quarantine new artifacts
by exact path; modification of a pre-existing file is a stop.

### 0.5 Git-crypt census boundary

The implementation worktree uses locked git-crypt bytes with no-op filters. All
commits there use:

```bash
git -c filter.git-crypt.clean=cat \
    -c filter.git-crypt.smudge=cat \
    -c filter.git-crypt.required=false ...
```

Text census is authoritative only after `.gitattributes` paths are enumerated.
Inspect encrypted paths in the unlocked main tree and prove their tracked blobs
are unchanged; inspect all unencrypted paths in the implementation worktree. A
locked ciphertext grep is never evidence of absence.

The exact census algorithm therefore has two inputs: unencrypted tracked files at
the implementation tip, plus plaintext reads of every git-crypt path from the
unlocked main tree after proving its tracked blob is unchanged. The complete
discovery also includes `docs/design/PROJECT_PRIORITY_MAP.md`; it receives the
explicit `slice_decision_log` disposition and is then excluded from the terminal
external-reference projection. The slice spec/plan/evidence are generated
authority and remain excluded from that external projection, but Task 1 classifies
them in the independent EIR-006 census. No path may disappear merely because it is
encrypted or belongs to a decision log.

---

## 1. Exact file map

### 1.1 Complete January evaluation family

Delete these exact fifteen files. Do not move them wholesale to `tests/live/`:

```text
tests/test_alpha_vantage.py
tests/test_eodhd.py
tests/test_finnhub.py
tests/test_finnhub_sentiment.py
tests/test_ibkr.py
tests/test_ibkr_all_free_apis.py
tests/test_ibkr_fundamentals.py
tests/test_ibkr_news.py
tests/test_ibkr_options_greeks.py
tests/test_ibkr_orats.py
tests/test_polygon.py
tests/test_sec_edgar.py
tests/test_sec_filings.py
tests/test_tiingo.py
tests/test_yfinance.py
```

Create only:

```text
tests/live/smoke_yfinance.py
```

Evolve:

```text
tests/live/README.md
docs/data/IBKR_NEWS_API_LIMITATIONS.md
tests/test_eir006_retired_data_boundaries.py
```

The Finnhub/Alpha Vantage current instructions in the news limitations document
must point to surviving product owners, not renamed copies of the January scripts.
Closed evidence/plans keep their dated path claims.

### 1.2 Dead option-rate family

Delete:

```text
src/options_math/rate_curve.py
tests/test_rate_curve.py
```

Modify:

```text
src/options_math/__init__.py
src/options_math/option_pricing.py
```

Remove `RateCurve`, `get_rate_for_dte`, `get_yield_curve`, `make_flat_curve`,
`get_risk_free_rate`, `_rfr_cache`, `_RFR_PERSIST_PATH`, `_load_persisted_rfr`,
and `_persist_rfr`, together with imports made unused only by that deletion. Keep
all pure pricing functions and the caller-supplied `risk_free_rate` contract.

### 1.3 Tiingo executable/configuration tail

Delete:

```text
data_sources/tiingo_source.py
data_sources/collect_aapl_comparison_data.py
```

Modify only to remove Tiingo-specific executable/configuration surfaces:

```text
data_sources/__init__.py
data_sources/base.py
data_sources/source_factory.py
config/.env.template
config/user_profile.yaml
```

Remove the import/export, enum member, registry entry, environment mapping,
credential template, and unread fallback. Other providers' members and behavior
must survive byte-equivalently under the shared-surface projection in Section 3.4.

### 1.4 Current authority corrections

Update:

```text
PROJECT_STRUCTURE.md
docs/design/ARKSCOPE_PROVIDER_CATALOG.md
docs/design/ARKSCOPE_TOOL_CATALOG.md
docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md
training/data_prep/README.md
```

Required terminal truth:

- Tiingo is absent from current/live/supporting/fallback/provider-settings tables;
- the Provider Catalog retains exactly one non-implementation candidate record
  governed by the seven admission criteria in the design;
- `get_ticker_prices` is described by its current DAL/local-market-data behavior,
  not an IBKR/Tiingo/Polygon chain that the tool does not execute;
- workbench charting copy lists only actually connected providers; and
- paused training documents yfinance as its implemented downloader and does not
  claim Tiingo is a current choice.

Dated research remains untouched except for `docs/data/IBKR_NEWS_API_LIMITATIONS.md`
where current runnable instructions are being corrected under Section 1.1.

### 1.5 Explicitly protected data and capabilities

Do not modify:

- `requirements.txt` yfinance ownership;
- `training/preprocessor.py` or
  `training/data_prep/prepare_training_data.py` behavior;
- `data_sources/comparison_data/` or any ignored comparison output;
- credentials, provider keys, profile/market databases, scheduler state, Gateway,
  or production data;
- Tranche B, OAuth, Settings navigation, FD metered policy, or provider adoption;
  or
- any current Finnhub, Polygon, SEC EDGAR, IBKR, Alpha Vantage, or EODHD product
  owner outside the shared files whose Tiingo projection must change.

---

## 2. Immutable accounting

### 2.1 Canonical node ledger

All streams are newline-terminated, byte-sorted canonical node IDs from the
reviewed deterministic reporter. Do not parse pytest transcript text.

| Stage | Count | SHA-256 | Delta from base |
|---|---:|---|---:|
| reviewed base | 4607 | `5180502f7dfe577ca758db5fb8ebdfe9ca282730a8976adcf65b7ab19c1c2d74` | n/a |
| after January family | 4561 | `dd127ce5dd34249a364b6a7965517aac66492b3d044ea8cc21e79a9706e58620` | `-46/+0` |
| final after rate family | 4527 | `4eeb117804ad874c83ffe4c04fd25ecd4de4f460801bfbf95d15c1406f32455d` | `-80/+0` |
| exact retired stream | 80 | `a069a5af63bfcb3c6d63ddb4a25ca63bc897f97adde3ef159b83aef7b7be6fb8` | exact set |

Required independent partitions:

| Partition | Identity |
|---|---|
| fifteen January paths | `15 / 2fff01e35f26d25c22ece520b491110b0066cf6fdccf31506fadab9f34fb30f2` |
| assertion-invalid Tiingo/yfinance nodes | `13 / 3ead0303136ab8742fae3fa15f916b2febda6088deb4f883c9b025db7d577016` |
| whole-file skipped nodes | `33 / 03f70d140bd4f2990674926904817667ed5f7ef28d10e4afbd71ea36f40aca58` |
| zero-node January paths | `6 / 9c2780536d4c05c9e40f4bbcab1583fe377565aa6663ba07055c2fcdf556f008` |
| `tests/test_rate_curve.py` | `34` nodes |

The 80 retired nodes comprise 47 current passes and 33 current skips. Final native
admission is exactly:

```text
4527 collected
4527 seen
4488 passed
39 skipped
0 failed
empty non-passing stream SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
exitstatus 0
```

### 2.2 Retained focused identities

The retained provider owner set is these twelve files:

```text
tests/test_data_provider_config.py
tests/test_provider_config_startup.py
tests/test_provider_health.py
tests/test_finnhub_ingestion.py
tests/test_news_normalized_provider_adapters.py
tests/test_news_normalized_ibkr_adapter.py
tests/test_news_providers.py
tests/test_sec_edgar_financials.py
tests/test_ibkr_source_event_loop.py
tests/test_ibkr_source_import_safety.py
tests/test_ibkr_source_intraday.py
tests/test_eir006_retired_data_boundaries.py
```

Its collection is `206 / 349552ac414fd067ce8cce2b918f5ae4bec5cbf3e725d313a3f42fbc272de737`
before and after. After Task 1 it must be `206 passed`.

The surviving option owner set is:

```text
tests/test_option_pricing.py
tests/test_option_chain_tools.py
```

Its collection remains `75 / b710ec5c6d50f541fed94994e863a1e2feaf0ec87aeb11c6e3a98eb4e2da099f`
and runtime remains `74 passed / 1 skipped`. The union is
`281 / 26aee6cf51eafd774b3015783729259beabaeecb9a17fc3cd27c9bae6c204e89`.

### 2.3 External-reference census identities

The original locked-worktree identities (`24/8a3b656a...`, disposition
`4c75ae8d...`; evaluation `10/ae345de1...`, disposition `6c875337...`) are
superseded and must never be used for admission.

Complete unlocked Tiingo discovery, excluding only the generated slice
spec/plan/evidence, is:

```text
27 paths / bb78255d82beddcfa5084159ccfb86d204d89d05e7a4930a90d94837a8c71ba4
27-row disposition TSV /
7bd0928bd49e040ffff4d7f3653e2610435ebf63c893b8d76169db2e7d30bcf9
```

The disposition rows are fixed:

| Path | Pre-cutover disposition |
|---|---|
| `PROJECT_STRUCTURE.md` | `update_current_authority` |
| `config/.env.template` | `retire_executable` |
| `config/user_profile.yaml` | `retire_executable` |
| `data_sources/API_SPECIFICATIONS.md` | `historical_reference` |
| `data_sources/DATA_SOURCES_EVALUATION.md` | `historical_reference` |
| `data_sources/PAID_SUBSCRIPTION_EVALUATION.md` | `historical_reference` |
| `data_sources/PAID_SUBSCRIPTION_EVALUATION.tex` | `historical_reference` |
| `data_sources/__init__.py` | `retire_executable` |
| `data_sources/base.py` | `retire_executable` |
| `data_sources/collect_aapl_comparison_data.py` | `retire_executable` |
| `data_sources/source_factory.py` | `retire_executable` |
| `data_sources/tiingo_source.py` | `retire_executable` |
| `docs/data/DATA_SUBSCRIPTION_GUIDE.md` | `historical_reference` |
| `docs/data/IBKR_NEWS_API_LIMITATIONS.md` | `historical_reference` |
| `docs/data/US_STOCKS_OPTIONS_DATA_SUBSCRIPTIONS.md` | `historical_reference` |
| `docs/design/ARKSCOPE_PROVIDER_CATALOG.md` | `update_current_authority` |
| `docs/design/ARKSCOPE_TOOL_CATALOG.md` | `update_current_authority` |
| `docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md` | `update_current_authority` |
| `docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md` | `historical_reference` |
| `docs/design/PG_EXIT_REMAINDER_SCOPING.md` | `historical_reference` |
| `docs/design/PROJECT_PRIORITY_MAP.md` | `slice_decision_log` |
| `docs/superpowers/evidence/2026-07-25-calibration-anthropic-refusal.md` | `historical_reference` |
| `docs/superpowers/evidence/2026-08-08-oauth-lifecycle-quota-truth.md` | `historical_reference` |
| `docs/superpowers/plans/2026-07-02-s-j-provider-config-authority-phase-0-1.md` | `historical_reference` |
| `tests/test_finnhub_sentiment.py` | `retire_executable` |
| `tests/test_tiingo.py` | `retire_executable` |
| `training/data_prep/README.md` | `update_current_authority` |

Terminal Tiingo external projection explicitly excludes the classified decision
log and is exactly thirteen rows: twelve dated historical references plus one
Provider Catalog `candidate_record`:

```text
13-row SHA-256:
0ba6820c5b4ce2afdc26fdbb379ea6a44eb38f8c33954ed49b9a2a5b65c6c517
```

Complete unlocked external evaluation-path references are:

```text
13 rows / 76b31a5c05d6dbe0a2a75af7f2b6d8e61d89bf415a698c8aff1521901b5efde2
13-row disposition TSV /
f9f830dd8941ecb2efb1800cf408b1a477af9f137f1c50223aa763f5d09b602f
```

The external reference rows are fixed:

| Owner | Retiring path | Disposition |
|---|---|---|
| `data_sources/PAID_SUBSCRIPTION_EVALUATION.md` | `tests/test_ibkr_all_free_apis.py` | `historical_reference` |
| `data_sources/PAID_SUBSCRIPTION_EVALUATION.md` | `tests/test_ibkr_fundamentals.py` | `historical_reference` |
| `data_sources/PAID_SUBSCRIPTION_EVALUATION.md` | `tests/test_ibkr_options_greeks.py` | `historical_reference` |
| `docs/data/IBKR_NEWS_API_LIMITATIONS.md` | `tests/test_alpha_vantage.py` | `update_current_authority` |
| `docs/data/IBKR_NEWS_API_LIMITATIONS.md` | `tests/test_finnhub.py` | `update_current_authority` |
| `docs/superpowers/evidence/2026-07-29-lifespan-stall-causal-diagnosis.md` | `tests/test_sec_filings.py` | `historical_reference` |
| `docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/consumer-census.tsv` | `tests/test_ibkr_fundamentals.py` | `historical_reference` |
| `docs/superpowers/evidence/2026-08-08-oauth-lifecycle-quota-truth.md` | `tests/test_yfinance.py` | `historical_reference` |
| `docs/superpowers/plans/2026-06-28-ibkr-news-10172-capture.md` | `tests/test_ibkr_news.py` | `historical_reference` |
| `docs/superpowers/plans/2026-06-29-news-normalization-n7-migration.md` | `tests/test_ibkr_news.py` | `historical_reference` |
| `docs/superpowers/plans/2026-07-29-lifespan-stall-causal-diagnosis.md` | `tests/test_sec_filings.py` | `historical_reference` |
| `docs/superpowers/specs/2026-07-29-lifespan-stall-causal-diagnosis-design.md` | `tests/test_sec_filings.py` | `historical_reference` |
| `tests/test_eir006_retired_data_boundaries.py` | `tests/test_ibkr_fundamentals.py` | `update_current_authority` |

Three current rows leave or change owner; ten dated historical rows remain:

```text
10-row terminal SHA-256:
0625d1220d4f94110ca84c93bfa951fc4e69fa00f7ccf76ee9004184772d160c
```

Persist exact pre/post TSVs in Task 0/5 evidence. Unknown, duplicate, encrypted,
decision-log, or silently dropped rows stop the slice.

### 2.4 Byte-protected retained owners

Generate rows as `path<TAB>sha256<TAB>bytes<LF>` in the exact order below. The
30-row aggregate is:

```text
4ca66f0b373031fa64c73c537575a8d9fc25bba4fec663522cca59ed766b2fd2
```

| Path | SHA-256 | Bytes |
|---|---|---:|
| `requirements.txt` | `3ad1dd8110306a41d5bd9b78a91815c309c26bb446cbfb83ec7a2331fd2f3419` | 1137 |
| `data_sources/alpha_vantage_source.py` | `6adeefb67bbc93f8e505d2525697d51519e54706ac28ff6233dba4cdfdb3d519` | 15180 |
| `data_sources/eodhd_source.py` | `f03d4a7cb70bfd70c8eab74112b3ee786796dfa6af70d184af9fbe3334e94135` | 14145 |
| `data_sources/finnhub_calendar_client.py` | `22a6c16e472c8991cdc40f3af0225439d5e312d6885896bd20cf753d22740375` | 13230 |
| `data_sources/finnhub_source.py` | `216bd7d68e6ab1ef22a845c360e5a6c07377b685d92bb2ba1ffdb5601c7b72b4` | 14492 |
| `data_sources/ibkr_client_id.py` | `60e53af57f7f45d6d064a15ca5ed3a1aef998957ccf6be9d65579fe6f3fcfd83` | 3631 |
| `data_sources/ibkr_source.py` | `27b648ed60136336be4665e6aca98ea880d99735a83def0f507003e94191c969` | 80941 |
| `data_sources/polygon_source.py` | `e8b334e8a7f753327323688e36ee89078112d8c96ec14847d3fa4cab050fdce8` | 15841 |
| `data_sources/sec_edgar_financials.py` | `0fe1b9e08375db2f77ecce4472abb25478d8c447d0eb61405d509b64b23f55ec` | 32927 |
| `data_sources/sec_edgar_source.py` | `13b1dc58a9890a0af8a393de9f6d4a4d723b0cbb020416b73b637944feddbd3c` | 14341 |
| `src/api/routes/jobs.py` | `686ebfdadc8329beaa0dea5168792f8c7556807f1383d01492f8f5d884da0112` | 11576 |
| `src/api/routes/macro_calendar.py` | `9ec34c6cd1f8202330d37ecbe541f52c2632c2a3e9022120a9fe457d793721c9` | 13301 |
| `src/api/routes/providers_config.py` | `12728dc10731ac4c34b94ca44884a50db9bdb8fdcd4bf8c6e0354a7e64b2d3a8` | 12385 |
| `src/collectors/finnhub_news.py` | `07d1820855dc6bc05c151259ff6fd105acee35c39fb3b1954d6af1d0460b79cd` | 28698 |
| `src/collectors/polygon_news.py` | `6db8408d5c3c8ad633c27037cc2fcb2c6404804c9b00931ee8fe4e3bcbee7f12` | 40916 |
| `src/data_provider_config.py` | `70f17ab66b2093f783123343dc4d691e77ad11e98482baf398e02b272633633b` | 21896 |
| `src/macro_calendar/__init__.py` | `2b82f0be0965d114af58e95c7d356054ae998f8c90995282eff236c591b0037f` | 923 |
| `src/macro_calendar/finnhub_ingestion.py` | `9ce4cb75a92963c7be1433ef359c440bc7515f3e7cd95c83d9ebeefe7b713e13` | 9938 |
| `src/macro_calendar/fred_ingestion.py` | `3cb50fd7da6bbf4c7c0cc513ccb283f472cb4cb4bdd7e53d60eafe51489a5c63` | 19447 |
| `src/macro_calendar/local_store.py` | `3666ac0e634b40282a1b53a73f5082bb9d318efe633bcd3081016ac5bd255a57` | 37596 |
| `src/macro_calendar/store.py` | `c8db30f67bd38aad44e98f82c37596779b344a044a050288c15ef55f3cd1e165` | 42936 |
| `src/news_normalized/ibkr_adapter.py` | `19f3fe52cec7aed0eacc40584b388dc05e16251b1cf69bd6b38ee701d448c860` | 4706 |
| `src/news_normalized/provider_adapters.py` | `826a78b2fb6b7865403bc8d87f456f17a0a8e328c091ff11f76cb3626f84278a` | 5115 |
| `src/service/data_scheduler.py` | `37f2cea8b01b433f3dd285c5b2230d5cb1e7a890cc52e59426a55439f541f4cc` | 62458 |
| `src/service/provider_health.py` | `237a3dd634eeda3c1e7cb10cecd8b433e06513ec1727c4b9cdfd544d6ecafcce` | 20825 |
| `src/tools/macro_calendar_tools.py` | `6c9ef3f5344d7df4ac4b8980d9e662d11ce394d558f1db80386dbdfc4da126f4` | 9835 |
| `src/tools/option_chain_tools.py` | `bef0b8578ad468012c02d9cade97a91a0cac85eafd868762e36e4b9a362e7d46` | 12519 |
| `src/tools/options_tools.py` | `617cb53de820661157ef5d4dc4a7b5fb6c03bdd7580d1b8de2ef68546bd523ac` | 1616 |
| `training/preprocessor.py` | `9bfb616bcc9440fe67e1e0868f586d28860e4240bdae696e924cc0687b8eb5d0` | 9516 |
| `training/data_prep/prepare_training_data.py` | `412665767c36b9901c28e16c1c89b87e27c77b972e206d343090d18c8b15a732` | 33239 |

Any byte drift in this table is a stop, not a request to update the pin.

---

## 3. Structural contracts

### 3.1 Manual yfinance smoke

`tests/live/smoke_yfinance.py` is a new operator CLI, not a moved pytest file.
It must:

1. parse `--help` before importing yfinance;
2. require an explicit ticker and accept bounded period/interval choices;
3. make no request until argument validation succeeds;
4. require a non-empty frame with required OHLCV fields, a parseable ordered
   timestamp index, and finite latest close;
5. print a bounded summary without cookies, headers, or local cache contents;
6. return zero only when every selected check passes and non-zero for empty,
   malformed, import, request, or validation failure; and
7. remain uncollected by canonical pytest.

No automated test may invoke its provider path. Structural verification parses
its AST and executes only `--help` with a temporary import sentinel proving that
top-level yfinance import did not occur.

### 3.2 January-family deletion contract

The pre-edit RED is structural and exact:

- all fifteen paths exist;
- their path stream is `2fff01e3...`;
- the nine collected modules contribute exactly 46 IDs split 13 pass-contract
  invalid plus 33 skipped;
- six modules contribute zero IDs; and
- `tests/live/smoke_yfinance.py` is absent.

After Task 1 all fifteen paths are absent, no replacement starts with `test_`,
the full collection is the exact 4561 stage, and the retained-provider set is
206/206 green. Runtime pass of the old boolean tests is never accepted as RED.

### 3.3 Rate-family deletion contract

Before edits, prove all retired definitions, exports, and 34 node IDs exist and
that no non-test consumer exists outside their defining modules/package exports.
After edits, AST/import census must find no current symbol owner or import. Do not
replace the curve with a constant, shim, optional import, or deprecation wrapper.
The 75-node surviving option set is the behavior authority.

### 3.4 Shared provider projection

`data_sources/__init__.py`, `data_sources/base.py`, and
`data_sources/source_factory.py` must be parsed with `ast`, not compared through
ad hoc substring replacement. Capture before and after:

- all `DataSourceType` name/value pairs except `TIINGO`;
- all `_SOURCE_REGISTRY` key/class pairs except `tiingo`;
- all provider environment-map key/value pairs except `tiingo`; and
- all package `__all__` members except `TiingoDataSource`.

The non-Tiingo projection must be byte-identical. For `config/.env.template` and
`config/user_profile.yaml`, diff hunks may remove only the grounded Tiingo key and
fallback claims; all other settings remain byte-identical. Any generic refactor is
out of scope.

### 3.5 Dual census closure

Task 0 materializes the two reviewed pre-cutover TSVs. Task 3 reruns discovery
from the final tree and proves:

- every pre-cutover row has one terminal disposition;
- no new external Tiingo/evaluation-path owner appears;
- removed executable/current instructions are absent;
- the terminal Tiingo projection is the exact thirteen-row stream in Section 2.3;
- the terminal evaluation projection is the exact ten-row stream;
- the priority map has the explicit `slice_decision_log` disposition and is not
  silently counted as terminal external capability evidence;
- slice authority docs are classified in the existing EIR-006 census; and
- all git-crypt paths were enumerated and examined through the unlocked boundary.

Do not use `rg` return code alone as closure evidence.

### 3.6 Current authority and candidate language

The Provider Catalog candidate record may say Tiingo can be reconsidered. It may
not imply installed code, configuration, current credentials, scheduler support,
live health, an EOD fallback, or permanent rejection. Re-admission is a new slice
against then-current interfaces and the seven criteria; git history is the only
code archive.

### 3.7 No-request witness

Task evidence records every command. Any command capable of provider access must
be rejected before execution. Final review must show:

- old January/rate files never ran;
- the manual smoke ran only `--help` with import blocked;
- no credential was supplied;
- no comparison output/cookie/tz cache was created; and
- canonical native admission occurred only after the network paths left.

---

## 4. Tasks

### Task 0: Re-ground the reviewed authority before edits

**Files:** plan/design/map only; then create evidence.

- [ ] **Step 1: Verify branch and authority identities**

Require exact branch/worktree/base, clean status, reviewed design commit ancestry,
reviewed design blob SHA, and all five pinned native/toolchain assets. Verify main
remains `6159fc14` and no product/test/data path differs from the reviewed branch.

- [ ] **Step 2: Rebuild collection and all partitions without running tests**

Use the deterministic reporter with `--collect-only` under a fresh single-use
stage. Require base `4607/5180502f...`, seen set empty, and no provider call. Derive
the 15-path, 13-node, 33-node, 6-path, 34-node, 80-node, 4561-stage, and 4527-final
streams independently from the base JSON. Compare every count/SHA in Section 2.1.

- [ ] **Step 3: Record exact structural RED**

Prove all retiring files/symbols/Tiingo surfaces exist, the manual smoke is absent,
and the current authorities contain the stale grounded claims. Record the known
206-node focused run as `205 passed / 1 failed` after creating only empty `data/`;
the sole failure must be the EIR-006 census node and exact unclassified path in
Section 0.3. Any other failure is wrong RED and stops.

- [ ] **Step 4: Rebuild both external censuses and protected manifest**

Reproduce all Section 2.3 streams through the two-input unlocked/plaintext boundary
in Section 0.5. The result must include both encrypted research documents and the
priority-map decision log. Reproduce all 30 protected rows and aggregate in Section
2.4. Persist commands, row streams, and SHA files outside the repository under one
new single-use Task 0 root.

- [ ] **Step 5: Create Task 0 evidence and commit docs only**

Create:

```text
docs/superpowers/evidence/2026-08-09-provider-smoke-candidate-truth.md
```

Required sections:

```text
1. Authority and boundary identities
2. Collection and retirement ledger
3. Dual reference census
4. Protected-owner manifest
5. Structural RED and known docs-tip census RED
6. No-provider command log
7. Task reviews, native admission, and merge
```

Update the plan checkboxes and priority map. Commit evidence/docs only, then stop
for independent Task 0 review. Task 1 remains unauthorized until GREEN.

---

### Task 1: Retire the complete January family and add one truthful manual smoke

**Delete:** all Section 1.1 January paths.

**Create/modify:** the Section 1.1 replacement and owners, plus evidence.

- [ ] **Step 1: Preserve RED evidence and delete exact paths**

Use `git rm` on exactly the fifteen files. Do not move their contents. Require the
deleted path stream to equal the reviewed 15-path stream; a sixteenth path or a
missing path stops.

- [ ] **Step 2: Write the manual yfinance CLI and live contract**

Implement Section 3.1 from scratch. Update `tests/live/README.md` with the explicit
network/manual/current-terms warning and exact invocation. Run only compile, AST,
argument-error, and import-blocked `--help`; never invoke a ticker request.

- [ ] **Step 3: Reconcile current path references and EIR census ownership**

Update the two current instructions in
`docs/data/IBKR_NEWS_API_LIMITATIONS.md`. In
`tests/test_eir006_retired_data_boundaries.py`:

- remove `tests/test_ibkr_fundamentals.py` from `_TEST_FIXTURES`;
- classify this slice's spec, plan, and evidence as historical path-evidence
  owners; and
- preserve both existing node IDs and every other classification byte.

- [ ] **Step 4: Prove the exact 4561 stage and retained behavior**

Recollect and require `4561/dd127ce5...`. `comm` against base must equal exactly
the 46 January IDs; additions are empty. Require zero collected nodes under
`tests/live/`. With only an empty `data/` marker, run the 206-node retained-provider
set and require `206 passed`. Remove the marker and verify clean status.

- [ ] **Step 5: Commit and stop for review**

Commit the exact family as one atomic product/test change, then a docs-only evidence
update if needed. Suggested product commit:

```text
test: retire dated provider evaluation scripts
```

Stop for independent Task 1 review before Task 2.

---

### Task 2: Retire the unconsumed option-rate API

**Files:** Section 1.2 plus evidence.

- [ ] **Step 1: Reconfirm no consumer and exact reverse-TDD RED**

Run the uncapped symbol/import census and require only definitions, package exports,
and `tests/test_rate_curve.py`. Require all 34 IDs. A new consumer stops the task.

- [ ] **Step 2: Remove the module, exports, and cache-producing fallback**

Delete the two files and remove only the listed symbols/imports from the two shared
option files. Do not alter formulas or caller-owned rate inputs.

- [ ] **Step 3: Prove final identity and surviving option behavior**

Require `4527/4eeb1178...`; the stage difference is exactly the 34 rate IDs and no
additions. Run the 75-node option owner set and require `74 passed / 1 skipped`.
Compile `src/options_math`. Prove no `risk_free_rate.json` path or retired symbol
remains in current product/test code.

- [ ] **Step 4: Commit and stop for review**

Suggested product commit:

```text
refactor: retire unconsumed option rate curve
```

Update evidence and stop for independent Task 2 review.

---

### Task 3: Remove the Tiingo executable tail and correct current authorities

**Files:** Sections 1.3 and 1.4 plus evidence.

- [ ] **Step 1: Capture shared projections before editing**

Run the AST projection in Section 3.4 and save its canonical JSON/SHA. Capture exact
pre-edit hashes of both config files and all current authority documents.

- [ ] **Step 2: Delete Tiingo code/diagnostic and remove shared entries**

Delete exactly the two remaining Tiingo-owned executable paths. Remove only the
Tiingo import/export/enum/registry/env/template/profile surfaces. No shim, disabled
entry, alias, archived copy, or TODO implementation remains.

- [ ] **Step 3: Reconcile current authorities**

Apply every terminal statement in Section 1.4. Keep one concise Provider Catalog
candidate record and no other current implementation claim. Do not update dated
research to make history disappear.

- [ ] **Step 4: Close shared projections and both censuses**

Require non-Tiingo AST/config projections byte-equivalent, protected 30-row manifest
unchanged, final Tiingo external stream `13/0ba6820c...`, final evaluation stream
`10/0625d122...`, zero unknown/duplicate verdicts, and zero executable/config tail.
Confirm ignored `data_sources/comparison_data/` is byte/metadata untouched.

- [ ] **Step 5: Re-run focused behavior and collection**

Require final collection still `4527/4eeb1178...`; run the 206 retained-provider
and 75 option nodes for `280 passed / 1 skipped`. No provider request is allowed.

- [ ] **Step 6: Commit and stop for review**

Suggested product commit:

```text
refactor: retire Tiingo integration tail
```

Update evidence and stop for independent Task 3 review.

---

### Task 4: Mutation self-review and boundary verification

- [ ] **Step 1: Pin current owner SHAs before mutation**

Record the exact current SHA of each mutation owner and require clean status.

- [ ] **Step 2: Run four independent, exact mutations**

Each mutation starts from a clean restored owner, records an exact diff/SHA, must
turn only its owning gate RED, and restores the pre-mutation SHA before continuing:

1. **M1 - manual smoke collection/import:** rename/copy the smoke to a `test_*.py`
   path or move its yfinance import to module scope; the live-smoke structural gate
   must reject it before any request.
2. **M2 - Tiingo registry resurrection:** restore one Tiingo registry member; the
   shared AST projection/census gate must turn RED.
3. **M3 - retired rate export resurrection:** restore one retired package export;
   the retired-symbol gate must turn RED.
4. **M4 - false current claim:** restore one current-authority `live`/fallback
   Tiingo claim; the current-authority projection must turn RED.

An ineffective mutation, a RED from syntax/collection error unrelated to the
owned contract, or an inexact restore stops the task.

- [ ] **Step 3: Revalidate every protected boundary**

Require the 30-row protected manifest, shared non-Tiingo projections, dual census,
all three collection streams, and clean worktree. Update evidence with commands,
diff hashes, failure reasons, and restored hashes.

Stop for independent Task 4 review.

---

### Task 5: Canonical native admission and implementation review packet

- [ ] **Step 1: Re-run all static/focused gates**

Require:

```text
canonical collection 4527 / 4eeb1178...
retired difference   80 / a069a5af...
retained providers   206 passed
surviving options    74 passed / 1 skipped
tests/live nodes     0
protected paths      30 / 4ca66f0b...
Tiingo terminal      13 / 0ba6820c...
evaluation terminal 10 / 0625d122...
```

Run `git diff --check`, compile changed Python/live files, and prove no provider
credential/request command occurred.

- [ ] **Step 2: Run fresh exact-tip native admission**

Create a fresh detached exact-tip worktree with the Section 0.4 boundary. Verify
the wakeup probe, wrapper/reporter/toolchain hashes, no `.env`, empty `data/`,
absent `src/data`, and clean pre-manifests. Run one new single-use stage through
the pinned wrapper. Require exact final facts from Section 2.1.

- [ ] **Step 3: Transactionally restore generated artifacts**

Manifest every new path with inode/size/mode/mtime/SHA where applicable, quarantine
by exact path, and prove pre/post ordinary/ignored/symlink/data manifests equal.
The retired `src/data/cache/risk_free_rate.json` must not be generated. A modified
pre-existing file or unaccounted artifact stops the task.

- [ ] **Step 4: Complete the review packet and stop**

Fill all evidence sections, record product commits and exact artifact/report SHAs,
mark implementation complete but merge blocked, and add a newest-first priority
entry. Commit docs only. Stop for independent implementation review; Task 6 is
unauthorized until GREEN.

---

### Task 6: Reviewed fast-forward merge and exact-master closeout

- [ ] **Step 1: Reviewer reconstructs from raw evidence**

Independent review must rebuild the base/final streams, exact 80-ID difference,
all partitions, dual census, AST projections, mutations, protected manifest,
focused results, and native reporter facts. Prose alone is not evidence.

- [ ] **Step 2: Fast-forward only**

Prove `6159fc14` is an ancestor of the exact reviewed tip and the lineage contains
no merge commit. Fast-forward master with `git merge --ff-only`. Do not push.

- [ ] **Step 3: Re-run exact-master admission**

Use a second fresh detached exact-master worktree and new single-use stage. Repeat
the full Section 0.4 boundary and require the same 4527/4488/39/0 result and empty
non-passing stream. Restore artifacts exactly.

- [ ] **Step 4: Close out docs**

Record the merged tip, merged report/artifact identities, and candidate-data
boundary. Mark design/plan/evidence complete. Do not claim Tiingo is permanently
rejected or training yfinance retired. Stop for focused closeout review.

---

## 5. Stop conditions

Stop and amend before continuing if:

1. any count/hash/ID in Section 2 cannot be reproduced;
2. the current collection delta is not exact `-80/+0`;
3. any non-test consumer of a retired rate symbol exists;
4. any real Tiingo scheduler/API/UI/health consumer exists outside the grounded
   tail;
5. any old provider script, comparison diagnostic, rate test, or manual smoke is
   executed;
6. any provider credential/request, Gateway connection, or paid entitlement is
   needed;
7. `tests/live/` contributes a canonical node or imports yfinance before validated
   CLI arguments;
8. a January script is moved/renamed, skipped, or archived instead of deleted;
9. a retired rate/Tiingo shim, re-export, disabled entry, alias, or code archive is
   introduced;
10. paused-training yfinance, requirements, or behavior changes;
11. a protected retained-provider byte in Section 2.4 changes;
12. a non-Tiingo shared enum/registry/export/env projection changes;
13. either census has an unknown, duplicate, new unowned row, or silent omission;
14. locked-worktree ciphertext is used as absence evidence, an encrypted path is
    omitted, or the priority-map decision log is silently excluded;
15. current authorities still claim Tiingo is implemented/live/fallback, or claim
    permanent rejection;
16. ignored comparison output, production data, credentials, scheduler state, or
    provider state changes;
17. Tranche B, OAuth, Settings navigation, FD metered policy, or provider adoption
    enters the diff;
18. the known EIR-006 census RED is hidden, broadened, or fixed by weakening its
    fail-closed classification;
19. a mutation is ineffective, fails for the wrong reason, or is not restored to
    the exact pre-mutation SHA;
20. native admission runs in the managed sandbox or before provider paths leave;
21. native admission is incomplete, non-passing, or generates an unaccounted
    repository-relative artifact; or
22. merge would require a non-fast-forward history operation or discard reviewed
    work.

## 6. Plan self-review map

| Design requirement | Plan owner |
|---|---|
| complete January family, no tail | Sections 1.1, 3.2, Task 1 |
| exact `-80/+0` accounting | Section 2.1, Tasks 0/1/2/5 |
| manual yfinance only for training | Sections 1.1, 3.1, Task 1 |
| retire dead rate/cache path | Sections 1.2, 3.3, Task 2 |
| retire current Tiingo implementation | Sections 1.3/1.4, Task 3 |
| future Tiingo reconsideration, not permanent rejection | Sections 3.6, Task 3 |
| external/historical reference truth | Sections 2.3, 3.5, Tasks 0/3 |
| git-crypt unlocked census | Section 0.5, Tasks 0/3 |
| preserve current providers | Sections 2.2/2.4, Tasks 1/3/5 |
| preserve paused training yfinance | Sections 1.5/2.4, all stop gates |
| no provider request | Sections 0.2/3.7, all runtime tasks |
| native provider-free admission | Sections 0.4/2.1, Tasks 5/6 |
| review before each family/merge | every task close |

No implementation begins until independent review reconstructs this plan and
returns GREEN.
