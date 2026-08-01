# `scripts/` Comprehensive Retirement — Decision Document

> **Status: APPROVED DECISION AUTHORITY; TRANCHE A COMPLETE; TRANCHE B NOT STARTED**
>
> Written 2026-07-27 against clean `master` tip `5ba12673`, then fully
> re-grounded on 2026-08-01 against exact clean tip
> `24202182032670f0d762dbd98581a74e5427b818`. The protected pre-review draft was
> `79d4eac97d7692684d83f0a067f5987fe434bb76746b98af3e44f1c8ba4bf277`;
> the physical `scripts/` tree is byte-unchanged between those two commits, but
> its consumers, test ledger, and standing authorities were re-audited.
>
> Independent full-document review returned GREEN with zero findings, and the
> reviewed bytes were committed alone as `d89d433c`. This authority records the
> user's disposition rulings, including the target that root `scripts/`
> physically disappears. It does not by itself authorize deletion, move,
> rewrite, product edit, live provider call, or production-data operation:
> implementation remains blocked on independent review clearance of the
> RED-first Tranche A plan. Any production-data deletion or potentially billable
> provider revalidation requires a second explicit approval at execution time.
>
> Tranche A implementation received independent GREEN review and `master`
> fast-forwarded linearly to the exact reviewed checkpoint:
> `SCRIPTS_TRANCHE_A_TIP=d6ef3b9726c00d1ffbbeb70ea11a74aa8ae24678`.
> The root package now remains intentionally only for `scripts/scoring/` and its
> package marker. Tranche B has not started; no production score data or local
> scoring secret changed in Tranche A.
>
> Supersedes nothing.
> `REPO_HYGIENE_B6_MODULE_DISPOSITION.md` §3 and
> `REFACTOR_PROTECTION_SMOKE_GATES.md` §6 remain the standing survivor rulings
> until this document produces an approved replacement.

## 1. Why this document exists

The `scripts/` retirement question has been deferred three times, most recently
by the legacy scheduler/IV retirement spec, which removed exactly two
`scripts/analysis` files and explicitly left the broader line open.

The reason it keeps getting deferred is that "retire `scripts/`" has been posed
as a single yes/no per file, when the real question has at least four
independent dimensions. A file can be simultaneously unreachable from the
product, load-bearing for a test, valuable as knowledge, and misplaced in the
tree. Collapsing those into "keep or delete" produces either over-deletion or
the standing survivor table, which is what happened in B6.

### 1.1 The originating account (user, 2026-07-27)

The scoring line is the clearest case and it drives the framing:

> Sentiment and risk scoring were the earliest features of this repository.
> Their purpose was to train the RL model. As other providers' news was
> collected, scoring was extended beyond CSV to other formats. Later it was
> exposed to agents, primarily so they could read sentiment scores as
> additional reference information.
>
> Per-article scoring has severe limitations. Which information matters has to
> be understood in context; it is not credible that every article carries the
> same weight. The RL model's practical utility turned out to be much lower
> than expected, and it was retired.
>
> Sentiment scores are not worthless to this tool, but their reference value
> will be reduced substantially. If scoring is done again, the criteria and
> scope change: not one score per article. Given the cost, buying a provider
> that already scores news is preferable. Scoring a specific symbol at a
> specific point in time may be worth the cost; scoring every article is not.

Two consequences follow, and they are the frame for this whole document:

1. **`scripts/scoring` is not "news tooling". It is the production line of a
   research programme that has been retired.** Its artifacts are still read,
   but the reason they were produced no longer holds.
2. **Deletion is not the only cleanup.** Several files are worth keeping only
   as documentation; several are worth keeping as code but not where they
   live; one is a live operational path that should never have been a script.

## 2. The four axes (do not conflate)

Every prior discussion has mixed these. They are independent, and a file's
disposition is a point in this space, not a single label.

| Axis | Question | Values |
|---|---|---|
| **A. Reachability** | Does anything live point at it? | `runtime-named` / `pytest-collected` / `test-covered` / `docs-only` / `unreferenced` |
| **B. Purpose lifecycle** | Is the line it serves still alive? | `active-ops` / `one-shot-gate-spent` / `paused-line` / `retired-line` / `research-era` |
| **C. What is worth keeping** | If we keep something, what? | `the code` / `the knowledge only` / `nothing` |
| **D. Correct home** | If the code is kept, where does it belong? | `src/` proper entry point / `training/` / `docs/` / stays in `scripts/` |

Axis A is a fact. Axis B is mostly fact with one judgement (`paused` vs
`retired`). Axis C and D were the user rulings that are now locked in §5.

**Axis A is not a proxy for Axis B.** `import_news_scores_local.py` is
`runtime-named` yet serves a line whose value the user just downgraded.
`n9_batch1_pg_drop.py` is `test-covered` yet its gate was spent a month ago.

## 3. Complete inventory

Re-grounded observation, 2026-08-01, `master` `24202182`. The tree remains
exactly 29 Python files (27 scripts plus 2 package markers) and 5 Markdown files,
12,141 lines total. All 34 paths, all per-file line counts, all 61 textual
`src/docs/tests` reachability cells, and all 11 `imp` cells below still match the
2026-07-27 draft. The tracked path stream is
`59cf1e8e6cbdbfa0877aafad87ae8fd7107222afba2030fb87066376b1ee66a5`;
`git diff 5ba12673..24202182 -- scripts` is empty. Counts must still be rederived
at implementation-plan baseline rather than copied from this document.

Reachability was measured as: named in `src/` or `apps/` (`src`), named in
`docs/` (`docs`), referenced by a file under `tests/` (`tests`), and whether the
script imports `src.` (`imp`).

### 3.1 `scripts/scoring/` — the retired research programme's production line

| File | Lines | src | docs | tests | imp | Axis A | Axis B |
|---|---:|---:|---:|---:|---:|---|---|
| `import_news_scores_local.py` | 59 | **1** | 8 | 1 | 1 | runtime-named | active-ops |
| `score_ibkr_news.py` | 986 | 0 | 6 | 2 | 1 | test-covered | retired-line |
| `score_sentiment_anthropic.py` | 1,049 | 0 | 2 | 0 | 0 | docs-only | retired-line |
| `score_risk_anthropic.py` | 932 | 0 | 2 | 0 | 0 | docs-only | retired-line |
| `openai_summary.py` | 428 | 0 | 1 | 1 | 0 | test-covered | retired-line |
| `validate_scores.py` | 73 | 0 | 1 | 0 | 0 | docs-only | retired-line |
| `README.md` | 218 | — | — | — | — | knowledge | — |

`import_news_scores_local.py` is the outlier and the reason this directory
cannot be moved as a unit. `src/daily_update.py` names it in five places as the
active replacement for the retired PostgreSQL score sync, it imports
`src.news_normalized.score_import`, and it writes production
`market_data.db.news_article_scores`. It is product operations wearing a
script's clothes.

The three large scorers plus the summary generator are offline batch jobs
against Anthropic/OpenAI Batch APIs. They are the cost the user is declining to
pay again at per-article granularity.

### 3.2 `scripts/huggingface/` — downstream publication + provenance

| File | Lines | src | docs | tests | imp | Axis A | Axis B |
|---|---:|---:|---:|---:|---:|---|---|
| `merge_for_release.py` | 367 | 0 | 2 | 0 | 0 | docs-only | retired-line |
| `SCORING_PROMPTS.md` | 191 | — | 2 | — | — | knowledge | provenance |
| `column_mapping.md` | 232 | — | — | — | — | knowledge | provenance |

`merge_for_release.py` reads `scores.parquet` / `summaries*.parquet` and
packages the public HuggingFace dataset. The two Markdown files are pure
provenance: exact prompts and dataset column mapping, cross-referenced from
`scripts/scoring/README.md`. They are the reproducibility record for a dataset
already published under an external identity.

### 3.3 `scripts/migration/` — spent one-shot gates

| File | Lines | docs | tests | Axis A | Axis B |
|---|---:|---:|---:|---|---|
| `retire_legacy_scheduler_iv.py` | 1,098 | 2 | 1 | test-covered | one-shot-gate-spent (2026-07-27) |
| `n9_batch1_pg_drop.py` | 973 | 5 | 1 | test-covered | one-shot-gate-spent |
| `n9_batch3_prices_drop.py` | 958 | 1 | 1 | test-covered | one-shot-gate-spent |
| `n9_batch2_cleanup.py` | 788 | 2 | 1 | test-covered | one-shot-gate-spent |
| `p0c_hapn_patch.py` | 278 | 0 | 1 | test-covered | one-shot-gate-spent |
| `p0c_prices_reconcile.py` | 260 | 1 | 1 | test-covered | one-shot-gate-spent |
| `apply_news_normalization.py` | 233 | 1 | 1 | test-covered | one-shot-gate-spent |
| `news_n8a_cutover.py` | 134 | 2 | 1 | test-covered | one-shot-gate-spent |
| `news_scores_cutover.py` | 94 | 1 | 2 | test-covered | one-shot-gate-spent |
| `job_runs_local_cutover.py` | 84 | 1 | 1 | test-covered | one-shot-gate-spent |
| `preview_news_normalization.py` | 52 | 2 | 1 | test-covered | one-shot-gate-spent |

Every migration script has a companion test. This is the tightest coupling in
the inventory: retiring any of them moves the backend node ledger, and several
of these tests are the only surviving record of what a spent migration
guaranteed. The IV retirement spec previously ruled that N9 scripts and their
tests stay because they document and verify a historical drop. §5 supersedes
that keep-executable approach once this decision passes written review: tracked
specs/plans/evidence become the durable historical record instead.

`retire_legacy_scheduler_iv.py` is a special case only at the operation layer.
Its `restore` mode is a convenience wrapper around the ignored 76 KiB archive
under `data/backups/`; it is not required to preserve code history or the
already tracked aggregate/digest evidence. The user has explicitly ruled that
the legacy scheduler/IV product state will not be restored. The final
disposition is therefore to retire the script and, through a separate
production-data approval, delete that archive rather than leave a dangling
`RESTORE.txt` that advertises unsupported rollback.

### 3.4 Live smokes and probes — deliberately outside pytest

| File | Lines | docs | tests | imp | Axis A | Axis B |
|---|---:|---:|---:|---:|---|---|
| `live/sdk_driver_smoke.py` | 131 | 0 | 0 | 8 | unreferenced | active-ops (manual) |
| `live/sdk_route_smoke.py` | 93 | 0 | 0 | 5 | unreferenced | active-ops (manual) |
| `live/README.md` | 23 | — | — | — | knowledge | — |
| `diagnostics/probe_ibkr_news_bodies.py` | 139 | 3 | 1 | 2 | test-covered | one-shot-gate-spent |
| `p1_2/smoke_fred.py` | 149 | 0 | 1 | 2 | manual-only | active-ops (manual) |

These are intentionally not collected by pytest because they spend real money
or need a live Gateway. `live/README.md` says so explicitly. They are the
category most at risk of being deleted by a purely reachability-driven sweep,
because "no test references it" is exactly their design.

The fixed-ID IBKR diagnostic is the exception within this table: three adapter
tests import its helper seams, but its five-article premise probe is spent and
is not a standing operator workflow.

The `tests` count for `smoke_fred.py` is textual only:
`tests/test_fred_ingestion.py` says that live calls belong in that smoke, but
does not import or execute it. It is therefore not test-covered.

### 3.5 `scripts/testing/` — inside the pytest collection and hitting a paid API

| File | Lines | Axis A | Axis B |
|---|---:|---|---|
| `test_financial_datasets_api.py` | 643 | **pytest-collected** | research-era |
| `test_financial_datasets_api_retry.py` | 230 | **pytest-collected** | research-era |

These two contribute the exact two `scripts/`-rooted nodes in the canonical
4,730-node backend collection:

```text
scripts/testing/test_financial_datasets_api.py::test_all_endpoints
scripts/testing/test_financial_datasets_api_retry.py::test_failed_endpoints
```

They read `FINANCIAL_DATASETS_API_KEY` and issue live requests to
`https://api.financialdatasets.ai`. They are named `test_*` in a `scripts/`
subdirectory, which is why pytest collects them. Retiring them changes the
top-level node ledger by exactly `-2`: `4730/c34de9a0fe53e400409d3ec26d75a8c907ee277b121279693ea9f69c8638aabb`
becomes
`4728/49e4a32b5f536cea97053578f2fba4456ffbbe0c10a4b66540c4f26d2b55329f`
when only those two IDs are removed, with `+0`.

They are also an active default-suite hazard rather than useful automated
tests. Their test functions do not enforce the `__main__` API-key guard, perform
29 request attempts across the two files, write under
`comparison_results/financial_datasets/`, and contain no product assertion that
can fail when the provider contract is wrong. The first file creates its output
directory at import time. Knowledge extraction must precede deletion, but no
future canonical suite may retain this accidental live-call shape.

### 3.6 Unreferenced leftovers

| File | Lines | src | docs | tests | Axis A | Axis B |
|---|---:|---:|---:|---:|---|---|
| `visualization/news_dashboard.py` | 557 | 0 | 0 | 0 | unreferenced | research-era |
| `visualization/data_loader.py` | 312 | 0 | 0 | 0 | unreferenced | research-era |
| `visualization/README.md` | 93 | — | — | — | knowledge | — |
| `analysis/scan_unusual_activity.py` | 279 | 0 | 3 | 0 | docs-only | research-era |

The visualization pair is a Streamlit + Plotly dashboard over
`data/news/raw/**.parquet`. Neither `streamlit` nor `plotly` is declared in
`requirements.txt`; both happen to be installed in the current environment, so
the scripts run today by accident of the environment rather than by declared
contract.

`scan_unusual_activity.py` is the B6 survivor that the IV retirement spec
deliberately left untouched. It imports `IBKRDataSource` from the root-level
`data_sources/` package (not `src.data_sources`), works via a `sys.path`
insert, and `--help` exits 0. Re-grounding also found that its documented
`--max-price` option does not exist, its `--location` value is not forwarded to
the scanner call, and import-time setup overwrites the client ID with a random
value. The reusable scanner primitives remain in `IBKRDataSource`; the wrapper
is not a reliable supported command.

### 3.7 Package markers

`scripts/__init__.py` (4 lines) and `scripts/scoring/__init__.py` (1 line)
exist so the namespaces are importable. Their fate follows their directories.

## 4. What the classification shows

### 4.1 The directory boundaries do not match the lifecycle boundaries

`scripts/scoring/` holds one live operational path and five retired-line batch
jobs. `scripts/` as a whole holds spent migration gates, deliberately
un-collected live smokes, two pytest-collected paid-API probes, and abandoned
research tooling. No single ruling fits a directory.

### 4.2 Test coupling is the dominant constraint

Fifteen of twenty-seven executable Python files have a direct import,
subprocess, or dedicated companion-test binding. They span 16 files under
`tests/`: all eleven migration gates, the fixed IBKR diagnostic, the score
importer, `score_ibkr_news.py` (two files), and `openai_summary.py`. The FRED
docstring reference is not a test binding.

Against the accepted 4,730-node stream, the static direct-coupling census is
157 nodes: migration 118, scoring 36, and diagnostics 3. Adding the two
`scripts/testing/` nodes gives 159 nodes touched by a root-script relationship.
This is a dependency census, **not** a deletion ledger: several companion files
also own current product contracts, so an implementation plan must decide each
node as retained/evolved/removed and precompute the exact target collection
before editing. Whole-file deletion is not implied by a script import.

### 4.3 The scoring artifacts are frozen, still product-readable, and coverage-blind

Independent of the scripts themselves, the data they produced is in this state
(read-only transaction observed 2026-08-01T02:10:47Z):

- `news_article_scores` holds 491,808 rows across six `(score_type, model)`
  pairs: `haiku` 132,615 each, `gpt_5_2` 109,490 each, `gpt_5_4` 3,799 each;
- the newest `scored_at` in every pair is **2026-06-07** — no new scoring in
  roughly eight weeks;
- the database reader is `src/tools/backends/sqlite_backend.py`, via a
  latest-score-per-article subquery driven by `scored_only` / `model`;
- direct consumers include ordinary news/search DTOs, registered news tools,
  `get_news_sentiment_summary`, overview/profile payloads, monitor and analysis
  paths, signal synthesis/factor tools, `GET /news/{ticker}/sentiment`, and
  `/signals/*`; no frontend surface calls those sentiment/signals routes today,
  but frontend API types still carry score-derived fields;
- the reader first filters articles by `published_at`, so a default 7-day query
  does **not** simply reuse a June score as if it were current;
- the score population remains 140,152 distinct articles dated 2022-01-01
  through 2026-04-27. In the fixed 90-day window beginning
  `2026-05-03T02:10:47Z`, there were 83,774 canonical articles, 45,080 with a
  legacy-map identity comparable to the historical score population, and zero
  scored articles; the newest canonical article was
  `2026-07-31T23:36:47Z`. These are dated observations rather than acceptance
  constants; the live corpus can move during review;
- `get_news_sentiment_summary` asks for `scored_only=True`, then exposes the
  resulting count as `article_count`. In a zero-coverage window it can therefore
  report `article_count=0` even though unscored news exists. The field means
  "scored article count", not "article count".

The defect is not old scores masquerading as fresh scores. It is that scoring
coverage stopped while APIs and tools still advertise a scored-news capability,
do not expose coverage, and use an ambiguous count. That product contract must
be retired or redesigned atomically; moving or deleting scorer files cannot
solve it.

This section explicitly retires two preliminary inventory claims: that the
scores were agent-only/no-route data, and that default lookbacks necessarily
served June scores as current. Both were conclusions drawn before following the
full call and date-filter chains.

### 4.4 A structural observation outside this scope

`data_sources/` is a top-level package at the repository root, outside `src/`,
imported by eight `src/` modules. It is not a `scripts/` file and is out of
scope here, but any "better structure" ruling that touches script imports will
run into it.

Three adjacent lines stay explicitly separate:

- EIR-006 owns the live stale-price valuation fallback; old price CSV deletion
  waits for that truth contract plus its own consumer census and approval;
- dead-code candidates inside `data_sources/` (including scanner methods with
  no `src/` caller) require their own disposition and may not ride this cleanup;
- `training/` is paused-preserve. This decision may correct its references and
  archive scorer lineage, but does not retire the RL tree or its historical
  inputs.

### 4.5 Current path and authority references the programme must reconcile

The original three-reference list was incomplete. The 2026-08-01 census found
no tracked systemd, service, CI, desktop, or web-app runtime consumer of root
`scripts/`, but it found these current bindings. Each bullet names its owning
tranche; no tranche may silently contradict an authority assigned to the other:

- `src/daily_update.py` names
  `scripts/scoring/import_news_scores_local.py` in operator-facing errors, help,
  and logs. It is a live instruction even though there is no subprocess call;
- `training/data_prep/prepare_training_data.py` and `training/README.md` tell a
  maintainer to generate score columns with `score_ibkr_news.py`. This is a data
  contract, not an import. If regeneration is retired, the training owner must
  say that historical scored inputs remain usable but their old producer is no
  longer supported;
- the legacy scheduler/IV retirement evidence still contains an executable
  `restore` command for `retire_legacy_scheduler_iv.py`. The user has ruled that
  rollback is unsupported. That instruction and the ignored archive's
  `RESTORE.txt` must be reclassified as lineage-only before the script
  disappears; the archive bytes remain untouched until §6.3 approval;
- `README.md` and `PROJECT_STRUCTURE.md` still list `scripts/` as a current
  top-level owner, while `REFACTOR_PROTECTION_SMOKE_GATES.md` §6 is the standing
  survivor authority that this decision must replace atomically;
- `MACRO_FRED_PRODUCT_SEMANTICS.md` §6.7 hard-locks `scripts/p1_2/` as protected
  capability. Tranche A may move its manual FRED smoke to `tests/live/`, but the
  same reviewed change must evolve that authority from path preservation to
  capability/test-contract preservation;
- `ARKSCOPE_TOOL_CATALOG.md` §3 rule 9 says score tools and score-derived fields
  remain live for history/enrichment/fallback and assigns their retirement to a
  later triage. `DESKTOP_APP_CARRYOVER_ANALYSIS.md` §5.3 independently marks
  the scoring read path and several scorer executables `preserve-adapt`.
  Tranche B is that later atomic product-contract decision: it must explicitly
  supersede or revise both authorities rather than leave them contradicting the
  final tree;
- `CONFIG_AUTHORITY_PLAN.md` and `CREDENTIAL_MANAGEMENT_PLAN.md` assign the
  scorer's rotation pool to the gitignored `config/scoring_keys.txt`. The
  production-local file exists with mode `0600`; its contents were not read.
  Because deleting the scorer removes its current owner, Tranche A must give
  this secret bridge a named retained/migrated owner or obtain separate explicit
  approval for local secret deletion before the scorer disappears;
- `docker/README.md` describes its archive-restore pattern by reference to the
  N9 migration CLIs. The pattern may remain, but its wording cannot imply that
  deleted CLIs are current operators;
- `.gitignore` owns `scripts/huggingface/output/`, and
  `docs/data/NEWS_DATA_INVENTORY.md`, `training/README.md`, the scoring README,
  and current-looking data/runbook prose still name score/HuggingFace commands
  or paths. Historical records may retain dated paths; current instructions
  must move to their final owners or state that regeneration is unsupported;
- `src/auth_drivers/chatgpt_oauth_probe.py` and
  `docs/design/LLM_AUTH_DRIVER_PLAN.md` cite the nonexistent
  `scripts/probe_chatgpt_oauth_backend.py`. These are upstream provenance, not a
  local runtime path, and must be labelled as such;
- two already-broken training instructions point at nonexistent root scripts:
  `scripts/patch_model_metadata.py` and
  `scripts/analysis/extract_sb3_train_metrics.py`. Retirement may not leave
  these as apparently runnable local recovery steps;
- tests directly import the 15 script owners enumerated in §4.2, and one dynamic
  boundary test (`tests/test_legacy_iv_retirement_boundaries.py`) scans
  non-migration scripts. Their node dispositions belong in the implementation
  ledger, not in a string-replacement sweep.

Self-contained commands inside a script/README are part of the file's own
disposition. Explicitly historical specs, plans, and evidence may retain dated
paths. `apps/arkscope-web/scripts/...` is an app-relative directory and is not a
root `scripts/` consumer; a repository-wide bare-string ban would wrongly catch
it.

### 4.6 Re-grounding verdict

The physical inventory and the user's final family dispositions remain valid.
The 2026-08-01 audit changes the execution contract in five ways:

1. the green canonical base is 4,730 nodes, not 4,691;
2. FRED is manual-only, while the paid Financial Datasets files are accidental
   default-suite network/write hazards;
3. current path/authority cleanup is broader than the original three references
   and is assigned explicitly between Tranches A and B;
4. scorer deletion requires a closed disposition for its local credential
   bridge; and
5. Tranche B's score-consumer map must include the full read/DTO/monitor/
   analysis/agent/frontend surface, not only the explicit sentiment route.

These corrections do not authorize implementation and do not reverse the
selected end state.

## 5. Locked decisions

### 5.1 End state: retire the directory, not merely its current contents

The selected option is full semantic retirement. The final tree has no
`scripts/` directory and no compatibility wrappers at its old paths. This is
not a mechanical delete: each survivor moves to the owner implied by its real
contract, while spent or research-era code is removed after its durable
knowledge has been extracted.

The rejected alternatives are:

- a smaller chartered `scripts/`, because it preserves the early-repository
  habit of using one directory for unrelated experimental and operational code;
- a delete-only sweep, because it cannot distinguish historical evidence,
  product contracts, live validation, and genuinely dead code.

### 5.2 Disposition by family

| Current family | Final disposition | Required retained value |
|---|---|---|
| offline scorer code (`score_*`, `openai_summary.py`, `validate_scores.py`) | delete | prompts, model/pipeline/training lineage, score scale, column meanings, and an explicit statement that the old scored-input regeneration path is unsupported under `docs/history/` |
| HuggingFace packager | delete | move `SCORING_PROMPTS.md` and `column_mapping.md` into the same historical provenance owner |
| `import_news_scores_local.py` | delete in the legacy-score product tranche | no replacement CLI; future scoring is a new on-demand/provider-native semantic contract |
| eleven spent migration gates and their gate-only test portions | delete | existing reviewed specs, plans, evidence, hashes, and dated priority-map entries remain the history; mixed test files and domain migration cores require explicit per-node/per-module dispositions |
| SDK driver/route and FRED live smokes | move to `tests/live/` | one explicit README contract: manual, real network/credentials, possible spend, never default-collected |
| fixed-ID IBKR news-body probe | delete | retain its already reviewed evidence and adapter contract, not the executable probe |
| Financial Datasets paid probes | delete after knowledge extraction | a separately owned inventory of all 24 literal endpoint paths and request shapes, including dated status for conflicting retry-only paths; no historical price-tier claim becomes current truth |
| Streamlit/Plotly visualization | delete | preserve a compact knowledge-only gap list for publisher/monthly/content-length/ticker/heatmap analytics; this does not commit the product to rebuilding them |
| unusual-options CLI wrapper | delete | keep the tested scanner primitives in `IBKRDataSource`; record a gated product candidate requiring subscription/capability UX |
| package markers | delete only after all importing tests/modules leave | none |

#### 5.2.1 Scorer credential bridge is not deletion collateral

`config/scoring_keys.txt` is outside `scripts/`, gitignored, and contains local
secrets. This decision does not authorize reading, printing, staging, hashing
into tracked evidence, moving, or deleting its contents. Before the current
scorer owner is removed, the reviewed Tranche A plan must close exactly one
disposition:

1. retain it under a named live credential consumer and current authority;
2. migrate its ownership through a separately reviewed credential change,
   without exposing the secret; or
3. prove that no live consumer remains and request explicit user approval for a
   separate local-secret deletion operation.

Leaving the file in place with no owner is not an acceptable fourth outcome.
Any approved deletion is an operational filesystem action, not part of a Git
commit, and its evidence must not contain the secret or a derived digest.

### 5.3 The legacy score product contract is one atomic follow-up

Deleting the old producers is not enough. The implementation programme must
inventory and atomically retire or redesign all consumers of the per-article
1-5 score domain, including:

- SQLite score schema/read projection and the parallel FileBackend
  `*_scored_final`/raw score-column path;
- ordinary ticker-news/search/brief DTO score fields as well as
  `GET /news/{ticker}/sentiment`;
- `get_news_sentiment_summary`, advanced search, and score filters on news
  tools;
- `scored_only`, `model`, `min_sentiment`, and `max_risk` contracts;
- sentiment-dependent anomaly, synthesis, context, factor, and factor-rank
  paths, while preserving any independently useful volume/event-chain behavior;
- monitor watchers and default analysis strategy/context paths, including API,
  CLI, and scheduled-analysis entry points;
- overview, cockpit/watchlist, profile/universe, and watchlist-tool payloads;
- tool registries, Anthropic/OpenAI bridges, subagent allowlists, and prompts;
- frontend API DTOs and their Home/Watchlist/Universe contract tests, even
  though no current web surface calls the sentiment/signals routes directly;
- ambiguous count fields such as `article_count` when the actual population is
  only scored articles;
- EIR-002 LD 6's retained sentiment route/tool/backend nodes and all other
  score-specific tests;
- the `news_article_scores` table, legacy/local score columns, migration audit
  state, scored-final files, backups, and the 491,808-row production dataset.

The user has ruled that the old per-article batch-scoring semantic will not be
maintained. Future sentiment or risk work must use a new semantic ID and explicit
scope, preferably provider-native evidence or an on-demand evaluation for a
named symbol and time context. It must not silently reuse the old table or tool
names. Physical score-data deletion remains a separately reviewed production
migration with a fresh manifest and explicit approval.

This is a semantic retirement, not permission to delete mixed features wholesale.
The Tranche B spec must decide, node by node, whether ordinary news/search,
brief/overview, volume anomaly, event-chain, monitor, and analysis behavior
survives without score fields or leaves with the old score contract. No default
is inferred from this decision document.

### 5.4 Financial Datasets is a separate product decision

The paid probes are research artifacts, but the product capability question is
real and stays outside scripts retirement. The two files contain 24 unique
literal endpoint paths; the existing production client implements only three
financial-statement calls and is not a replacement for that inventory. Before
deleting the probes, extract every endpoint, request shape, dated observation,
and script-recorded conflict/404 observation into a new
`FINANCIAL_DATASETS_CAPABILITY_SPEND_DECISION.md`. The future effective policy is
the intersection of three independent facts:

1. provider-declared endpoint capability and dated cost classification;
2. per-credential observed entitlement (`unknown`, `available`, or typed
   denied/unavailable evidence);
3. user authorization to make a call that may incur spend.

An API key is not spend authorization, and a spend toggle is not an entitlement
claim. Unknown price is treated as potentially paid and fails closed. A typed
402/403 may update observed entitlement and must not enter a blind retry loop.
No pricing or free-tier claim copied from the old probes is timeless.
Re-running either probe to refresh entitlement or endpoint status is a
potentially billable operation and requires separate approval; knowledge
extraction itself is static and must not call the provider.
`data_sources/PAID_SUBSCRIPTION_EVALUATION.tex` repeats part of the old probe
result and must be cited as dated evidence, not silently promoted into the new
capability registry.

### 5.5 The replacement location rules

| Contract | Correct owner after retirement |
|---|---|
| supported product/operator command | `src/<domain>/...`, invoked with `python -m src...` |
| deterministic automated verification | `tests/` |
| manual real-service, real-credential, or billable verification | `tests/live/` with explicit opt-in |
| active or paused research code that is still maintained | `training/` or another named research owner |
| historical method, prompt, mapping, or lineage only | `docs/history/` |
| one-shot migration | core under its domain while active; after reviewed cutover, retain spec/evidence and retire executable code |
| unproven experiment | a temporary branch/worktree until promoted to one of the owners above |

Creating another generic `tools/`, `utilities/`, or `experiments/` dumping ground
does not satisfy this decision.

## 6. Programme order and checkpoints

The two independent correctness/reliability prerequisites are now complete:

1. `/sa/feed` now reports typed unavailable-store truth and reserves
   `available=true` for a readable, schema-compatible store;
2. EIR-002 closed at `24202182` with canonical collection
   `4730/c34de9a0fe53e400409d3ec26d75a8c907ee277b121279693ea9f69c8638aabb`
   and native full result `4658 passed / 72 skipped / 0 failed`.

That canonical baseline is the admission authority for this programme, not a
historical comparison convenience. The implementation plan must use the same
fresh exact-tip boundary: no `config/.env`, an existing empty `data/`, the
pinned `node_modules` toolchain link, wakeup probe
`10647c1e64c49fc2e082701d7a735e40782620314c125cd103a9a3f9bb37bc2e`,
reporter
`09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928`,
and native wrapper
`e7c963f1bc97125b70b435fb3c41bf4e59d501f0da561f2ef6d921c12083c84f`
unless a separately reviewed protocol amendment supersedes them.

The scripts implementation then uses two reviewable tranches:

### 6.1 Tranche A: repository-only retirement

Extract historical knowledge, delete spent/research-era code and its gate-only
tests, relocate durable live smokes, remove the unusual-activity wrapper while
preserving provider primitives, and create the separate Financial Datasets
decision inventory. Reconcile every current path/authority class in §4.5,
that is owned by Tranche A, including the standing survivor rule, FRED
hard-lock, project layouts, training instructions, Docker wording, ignored
output owner, active rollback instruction, and scorer credential bridge.
The Tool Catalog and desktop carry-over score rulings remain unchanged until
Tranche B.
Tranche A must not change product behavior, production databases, collected
payloads, or the old score read contract.

Before the first edit, record the canonical base stream and a complete
retained/evolved/removed decision for all 159 directly coupled nodes described
in §4.2. The two top-level Financial Datasets nodes alone have the mechanically
known `4730 -> 4728`, `-2/+0` target from §3.5; **4728 is not the whole-Tranche-A
target**, because companion tests contain both spent gates and current product
contracts. The plan must derive and independently review the final Tranche A
target hash before deletion.

Deleting `retire_legacy_scheduler_iv.py` is permitted only in the same reviewed
change that removes current restore instructions and labels the ignored archive
as lineage awaiting §6.3 deletion, not as supported rollback material. No
archive byte changes in Tranche A.

Deleting the current scorer is permitted only after §5.2.1 has a closed,
reviewed disposition. Tranche A may not inspect or alter the local secret merely
to complete repository cleanup.

Record a named `SCRIPTS_TRANCHE_A_TIP` commit plus exact collection/node ledger,
canonical full-green admission, default-collection proof for `tests/live/`, and
a classified old-path census. Final review compares base to this checkpoint
independently.

Tranche A completed at:

```text
SCRIPTS_TRANCHE_A_TIP=d6ef3b9726c00d1ffbbeb70ea11a74aa8ae24678
```

The reviewed checkpoint has exact collection `4553/69152591...`, native
admission `4481 passed / 72 skipped / 0 failed`, the reviewed nine-path
physical tree, and zero `current_runnable` old-path census verdicts. Root
`scripts/` remains only for the transitional scoring owner and package marker.
This checkpoint does not authorize Tranche B, production score-data changes,
local-secret changes, or archive deletion.

### 6.2 Tranche B: legacy score contract and final closure

Retire the local score importer and stale `daily_update --scores` tombstone,
then execute the separately reviewed atomic legacy-score product-contract
decision from §5.3, including an explicit disposition for every stored score
artifact. Physical production-data deletion still requires its own manifest and
approval and is not implied by the Git tranche. Delete package markers and the
now-empty `scripts/` directory only after every product and test consumer has a
named disposition.

The same reviewed Tranche B change must reconcile
`ARKSCOPE_TOOL_CATALOG.md` §3 rule 9 and
`DESKTOP_APP_CARRYOVER_ANALYSIS.md` §5.3 with the selected score-contract end
state. It may not retire the implementation while leaving current authorities
that still direct maintainers to preserve or operate it.

Tranche B's plan must carry independent backend and frontend collection
ledgers. It must explicitly account for the EIR-002 LD 6 sentiment nodes,
ordinary score-bearing DTO tests, signal/monitor/analysis owners, registry and
agent inventory tests, and Home/Watchlist/Universe frontend DTO consumers.
`News.tsx`'s score-free feed contract remains protected.

Final review compares both base -> Tranche A and Tranche A -> final. Tranche B
may not hide a Tranche A regression.

### 6.3 Post-merge production operation

The ignored legacy scheduler/IV archive is not changed by a Git commit. Its
deletion requires a fresh check that the manifest is the reviewed
`30c01ea8fd009a3d47c5ac96ffd4dd9b0282a1adef03faafb91c3dd50dd92fad`, confirmation
that tracked evidence retains the agreed aggregate/digest record, stopped
writers where relevant, and a second explicit user approval immediately before
filesystem deletion. A mismatch is a stop condition.

## 7. Durable gates

- Every removed, moved, renamed, or evolved test node has an exact per-tranche
  `+N/-M` ledger and pre-reviewed target collection hash. Every tranche ends
  with zero non-passing nodes under the canonical boundary; the green baseline
  may evolve only by an explained node delta.
- `src/`, application code, configuration, and current runbooks contain no
  import, subprocess target, or runnable instruction under `scripts/`.
- Current layout/governance authorities no longer claim that root `scripts/`
  survives. This document must replace, not merely coexist with, the survivor
  table in `REFACTOR_PROTECTION_SMOKE_GATES.md`.
- The FRED authority preserves the manual capability at its final `tests/live/`
  owner rather than hard-locking the removed path. Tool Catalog and desktop
  carry-over score rulings are reconciled atomically with Tranche B.
- Current provenance text cannot present an upstream historical `scripts/`
  path as if it were a repo-local owner; the README cannot list a directory
  that no longer exists.
- The physical final-tree assertion is that `scripts/` does not exist. A
  compatibility wrapper, tombstone, or empty package fails the gate.
- Historical specs/plans/evidence may retain dated old paths. They are not
  rewritten merely to achieve a repository-wide zero-string result.
- App-relative paths such as `apps/arkscope-web/scripts/` are not root
  `scripts/` residue and must not be renamed by a broad textual sweep.
- `tests/live/` is absent from default pytest collection and every entry states
  network, credential, side-effect, and spend requirements before execution.
- Removing the fixed IBKR probe cannot weaken the product adapter's sanitized
  unavailable/error contracts.
- Financial Datasets endpoint knowledge exists in its new decision owner before
  either paid probe disappears; all 24 literal paths are classified without a
  live call, and conflicting retry-only paths are not promoted to capabilities.
- Tranche A keeps production databases, collected data, package locks, and
  product API/tool behavior byte- or behavior-identical as applicable.
- Legacy score consumers and data change only through Tranche B's atomic
  contract; no interval may expose two definitions of scored coverage.
- Training remains paused but preserved: its historical scored inputs and
  lineage remain understandable, while current prose no longer promises a
  deleted regeneration command.
- Removing the scorer cannot leave `config/scoring_keys.txt` ownerless. The
  bridge has a named live owner, a separately reviewed migration, or a
  separately approved local deletion; no secret content or digest enters
  tracked evidence.
- Once the restore script is gone, no current file may advertise legacy
  scheduler/IV rollback as supported. The ignored archive remains untouched
  until its separately approved deletion.
- The future unusual-options capability may not be represented by a retained
  dead CLI. Its reusable IBKR primitives and tests remain; productization needs
  a separate capability/subscription decision.

## 8. Stop conditions

Stop and amend the spec/plan if any of the following is found:

- a `scripts/` file has a current runtime, schedule, packaging, or operator
  consumer absent from the inventory;
- a migration target is not actually live-complete or its only durable evidence
  exists solely in the executable/test being removed;
- any score reader, route, agent bridge, signal path, schema owner, or frontend
  consumer is absent from the Tranche B map;
- a current Tool Catalog, carry-over, FRED, credential, or other standing
  authority would contradict the selected final tree after its owning tranche;
- scorer retirement would leave `config/scoring_keys.txt` without a named
  owner, expose any secret material, or delete it without separate explicit
  user approval;
- a mixed companion test or domain core is deleted merely because one script
  import was found, without a node/module ownership ruling;
- moving a live smoke makes it default-collected or able to spend/call a real
  service without explicit operator action;
- any Financial Datasets revalidation issues a network request without explicit
  spend approval;
- the Financial Datasets probes contain unique contract knowledge not yet
  captured by the new decision document;
- visualization deletion would discard the unique analytics-gap inventory
  without first recording it as knowledge-only;
- the restore script is removed while a current restore command still points at
  it or the archive is still described as supported rollback material;
- archive identity differs from §6.3, or deletion would include any file outside
  that exact ignored directory;
- canonical collection differs from the accepted base/target ledger, any
  tranche has a non-passing node, or a generated repo-relative artifact cannot
  be accounted for and exactly quarantined.

## 9. Completion contract

This line is complete only when all of the following are true:

- the already-complete `/sa/feed` and EIR-002 prerequisite evidence remains
  intact;
- both scripts tranches have independent reviewed A/B evidence;
- the repository has no `scripts/` directory and no current executable reference
  to it;
- every retained live validation has an explicit owner and opt-in contract;
- scoring provenance and Financial Datasets endpoint knowledge survive without
  retaining obsolete executable probes;
- the old per-article score producer and product contracts have one reviewed
  disposition, with production data handled through a separate approval;
- the scorer credential bridge has a named live owner, reviewed migration, or
  separately approved local deletion, with no secret material in Git evidence;
- the ignored legacy scheduler/IV archive has been deliberately deleted after
  its own approval, and current documentation no longer calls it standing
  rollback material.
