# Repo Hygiene Audit — 2026-07-06

> **Status**: inventory delivered 2026-07-06; owner rulings received same day (§7 answers
> folded into §8); **B1–B3 EXECUTED 2026-07-06** (§8 deletion record below); B4/B5 have
> their own plan (`docs/superpowers/plans/2026-07-06-repo-hygiene-b4-b5.md`). This executes the
> long-pending "module-level cleanup pass" from the docs-governance line
> (`DOCS_GOVERNANCE_AUDIT_2026_05.md` scoped it; scripts-runtime-consolidation proved the
> method). Every disposition below is a RECOMMENDATION; §7 lists the rulings the owner must
> make before any batch executes. Recovery rule: delete>archive — git history is the
> archive; each deletion batch records its pre-deletion sha.

## 1. Executive summary

| Area | What it is | Verdict class |
|---|---|---|
| `training/` (53 tracked) | Paused RL line code+docs (FinRL_DeepSeek lineage) | KEEP per P3.1 paused-preserve; artifacts = disk policy |
| `trained_models/` (2 tracked + **131 untracked**, 1.2G) | RL run registry + model checkpoints | ~~Registry stays tracked~~ **SUPERSEDED by §7 ruling / §8 execution: registry git-rm'd with the checkpoints; whole dir gitignored** |
| `docker/` (2 files) | PG compose (**compromised password**) | KEEP as archive-access tool; rotate password + README repurpose |
| `scripts/` (35 tracked, ruled 07-06) | Survivor table is authoritative | No change; `huggingface/output` 984M = disk policy |
| `analysis/` (3 tracked) | **LIVE runtime** (options pricing, imported by `src/tools/options_tools.py`) | Not cleanup; future home = packaging-slice domain reorg |
| `config/` (7 tracked) | Live config; `tickers_core.json` has ~10 live readers | KEEP all; only the uncommitted local edit needs disposition |
| Root `audit_stock_news.py` + `filter_fns_data_by_date.py` | FNSPID/CSV-era one-offs, **zero references** | DELETE (dead batch) |
| `comparison_results/` `data_lake/` (untracked) | 2025-12〜2026-01 provider-comparison + ibkr_fundamentals outputs | Disk policy (delete candidates) |
| `docs/` (109 tracked) | 60 design + guides/history/data | Sweep: status-header flips + archive moves + few deletions (§4) |
| Working tree | `tickers_core.json` M, `trained_models` M+D uncommitted for months | Ruling: commit or revert (§5) |

## 2. Per-area detail (context + evidence)

### training/ — the paused RL line
Code: envs (`stocktrading_llm*`), PPO/CPPO/SB3 trainers, backtests, `data_prep/`, research
probes, 8 analysis docs (`experiment_log`, `ppo_cppo_deep_dive`, `sb3_*` findings),
`UPSTREAM.md` (benstaf/FinRL_DeepSeek lineage + our fixes). Ruling P3.1 (2026-04-25 +
RL_COLLAPSE_FINDINGS §11): paused, OOS predictability not shown; C+ retirement (2026-06-03)
already made `src/`+`scripts/` RL-inference-free. `REFACTOR_PROTECTION_SMOKE_GATES.md`
Level 1 still `bash -n`'s two training scripts (intentional).
**Recommendation**: tracked content stays as-is (preserve code/history per ruling). Disk:
`training/data_prep/output` = **917M** of regenerable prepared-training-data artifacts
(gitignored) → delete candidate after owner confirms no pending RL resume needs them.

### trained_models/ — 1.2G, and the git-status noise source
Tracked: `registry.json` (readers: `training/model_registry.py` + trainers/backtests only)
+ one `metadata.json`. Untracked: **131 files / 37 run dirs** (2026-04 `ppo_sb3_train_polygon_multi_*`
multi-seed runs — the evidence base behind RL_COLLAPSE_FINDINGS). NOT gitignored → they
have polluted `git status` since April.
**Recommendation**: (a) gitignore `trained_models/*` except `registry.json` (+ tracked
metadata if kept); (b) checkpoints stay on disk (or move to external storage) — they are
paused-line evidence, not repo content; (c) resolve the pending working-tree `M registry.json`
+ `D ppo_test_10ep_s42_.../metadata.json` (commit if the test-run purge was intentional).

### docker/ — archive-access tool with a known compromised secret
`docker-compose.yml` + README. PG is archive-only since PG-exit closed (3 app-record
tables) — the compose's ONLY remaining purpose is spinning PG up to read archives /
restore `data/pg_archive/*` dumps. The dev password (published pre-2026-07; literal deliberately not repeated) is ruled
COMPROMISED (publication review) — rotation is a standing pending item.
**Recommendation**: keep both files; one small batch = rotate password (user executes,
archive DB) + rewrite README to "archive access only; PG is not a runtime dependency".

### scripts/ — already ruled
Survivor table in `PG_EXIT_REMAINDER_SCOPING.md` §5 (2026-07-06) is authoritative; no
re-litigation. Disk: `scripts/huggingface/output` = **984M** HF-release build output — the
dataset is published on HuggingFace; local copy is a rebuildable master → delete candidate
after owner confirm.

### analysis/ — live runtime, not cleanup material
`option_pricing.py` + `rate_curve.py`, imported by `src/tools/options_tools.py` (+3 test
files). A root-level loose package only because it predates `src/` conventions; its move
belongs to the packaging-slice domain reorg (locked-deferred), not to hygiene.

### config/ — all live; correction of a wrong guess
`tickers_core.json` still has ~10 live readers (profile route, collectors, daily_update,
native host, scheduler, Watchlist UI) — 3e-E only removed its *runtime default-scope*
role. NOT a retirement candidate. Everything else (`user_profile.yaml`, `sectors.yaml`,
`macro_calendar_series.yaml`, `event_types.yaml`, `.env.template`, `skills/`) is live.

### Root loose scripts — the class scripts-consolidation didn't scan
`audit_stock_news.py` (news-CSV ordering audit, mtime 2025-07) and
`filter_fns_data_by_date.py` (FNSPID CSV date filter, mtime 2025-06): pre-parquet
FNSPID-era one-offs, zero references repo-wide. **DELETE** (recovery = this audit's
closeout sha). The consolidation swept `scripts/` but never root-level `*.py`.

### Untracked data dirs (gitignore already covers them)
- `comparison_results/` (752K, 2026-01-14): provider-comparison experiment outputs
  (financial_datasets, news-source comparisons) — fed the DATA_DICTIONARY-era analysis,
  now absorbed into `docs/data/NEWS_PROVIDER_DATA_DICTIONARY.md`. Delete candidate.
- `data_lake/raw/ibkr_fundamentals` (2.7M, 2025-12-25): output of
  `collect_ibkr_fundamentals.py`, which was deleted as dead in the consolidation. Delete
  candidate.
- `NewsExtraction/` no longer exists (already cleaned in an earlier pass).

### resources/ + sql/
`resources/skills/` = live agent skills. `sql/` = 15 migration files = schema lineage
record (cheap, keep).

## 3. Disk reclaim summary (all gitignored artifacts, zero repo risk)

| Path | Size | Note |
|---|---|---|
| `trained_models/` checkpoints | ~1.2G | or move to external storage (RL evidence) |
| `scripts/huggingface/output` | 984M | published on HF |
| `training/data_prep/output` | 917M | regenerable |
| `comparison_results/` + `data_lake/` | ~3.4M | absorbed/dead-source |
| **Total** | **~3.1G** | |

## 4. docs/ classification (60 design files + 49 others)

Policy (already ruled): decision records + completed-thread evidence STAY; superseded HOW
that would mislead gets deleted after absorption; `docs/design/archive/` exists.

- **Live canonical (keep, no action)**: PROJECT_PRIORITY_MAP, CURRENT_PROJECT_CONTEXT,
  LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC + AUDIT, REFACTOR_PROTECTION_SMOKE_GATES,
  ARKSCOPE_PROVIDER_CATALOG, ARKSCOPE_TOOL_CATALOG, ARKSCOPE_WORKBENCH_PRODUCT_SPEC,
  DESKTOP_APP_VISION_DRAFT + CARRYOVER, SA_EXTENSION_HEALTH_SETUP_BOUNDARY,
  MACRO_FRED_PRODUCT_SEMANTICS, LOCAL_STORAGE_TOPOLOGY, DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN
  (draft, pending review), LLM_AUTH_DRIVER_PLAN (S3 still open), IV_PROVIDER_PROOF_PACKET_PLAN
  (Task 1 pending), README.
- **Completed-thread records (keep; add/verify a one-line status header where missing)**:
  the 11 `PG_EXIT_*`, SA_CUTOVER_3D_RUNBOOK, NEWS_DIRECT_LOCAL_PLAN, CONFIG_AUTHORITY_PLAN,
  SCHEDULER_HARDENING_PLAN, AI_RESEARCH_* ×3 (C-2 shipped), P1_2/P1_3/P1_4 specs,
  P1_5 decision, DESKTOP_SHELL_SPIKE_PLAN, SLICE_7B3, CREDENTIAL_MANAGEMENT_PLAN,
  AGENT_DATA_GAP_FALLBACK_PLAN, DESIGN_DOCS_CONSOLIDATION_REVIEW, DOCS_GOVERNANCE_AUDIT_2026_05,
  SA_ALPHA_PICKS_CONTENT_CAPTURE, SA_COMMENT_INTELLIGENCE_PLAN, SA_EVIDENCE_FEED_C1_SPEC,
  SA_EXTENSION_ROADMAP, MULTI_FACTOR_SIGNAL_DETECTION, AGENT_EVOLUTION_TRACKER.
- **Paused-line docs (keep, headers already say paused)**: PHASE_C_UNIFIED_RUNNER_SPEC,
  PHASE_A_KNOWLEDGE_GRAPH_SKETCH, PHASE_D_ANALYSIS_PIPELINE_SKETCH, RL_COLLAPSE_FINDINGS,
  AI_AGENT_ARCHITECTURE_PATTERNS, SKILL_PLUGINS_RESEARCH.
- **Needs a per-doc look in the execution batch (stale-HOW risk)**: P0_1_FULL_V1_SPEC
  (pre-pivot v1 framing) and any doc whose body still teaches retired paths
  (grep `scripts/collection`, `use_local_`, PG-first flows) — the sweep flips headers or
  archives, deleting only where content would actively mislead.
- Non-design: `docs/data` 9 (live reference incl. the restored provider dictionary),
  `figures` 5, `history` 3, `analysis` 3, `notes` 1, `features` 1, top-level guides 4.

## 5. Working-tree pending changes (months old)

`M config/tickers_core.json`, `M trained_models/registry.json`,
`D trained_models/ppo_test_10ep_s42_20260301T000000Z_abc123/metadata.json` — uncommitted
since ~April. Ruling: commit (if the classification import / test-run purge was
intentional) or revert. They add permanent noise to every `git status` read.

## 6. Proposed execution batches (each small; gate level per REFACTOR_PROTECTION)

- **B1 — dead root scripts** (delete 2 files, Level 0 + grep-zero proof). Zero A/B risk.
- **B2 — trained_models gitignore + pending M/D resolution** (Level 0; unblocks clean git status).
- **B3 — disk artifacts** (~3.1G; owner confirms each of the four paths; no git change).
- **B4 — docker repurpose + password rotation** (owner executes rotation; README rewrite).
- **B5 — docs sweep** (status headers / archive moves / misleading-HOW deletions; Level 0;
  one commit per bucket, dispositions listed in the commit).
- **B6 — nothing else**: scripts/ survivors, config/, analysis/, resources/, sql/ = no action.

## 7. Rulings needed from the owner — ANSWERED 2026-07-06

1. Disk artifacts: **delete directly, no external copy** (data + training code remain;
   retraining is cheap). Manifest required (→ §8), no checksums.
2. `trained_models/`: delete AND still gitignore (deletion cleans the present; ignore
   prevents the next training run from re-polluting `git status`).
3. M/D trio: `tickers_core.json` diff identified as rename-fix + SA Alpha Picks auto
   ticker-sync → **commit separately (B3)**; `trained_models` M/D resolves inside the B2
   `git rm` (no transitional commit). Config db-ification stays a future migration
   (readers first), NOT a pre-emptive file deletion.
4. docker: keep **archive-access-only** (not a dev quickstart — app runtime has zero PG);
   rewrite README/compose copy; rotation in the same batch (B4).
5. docs sweep: **deeper** — 4-tier rule (keep+update canonical / fold-summary-then-delete
   completed HOW / status-header big-migration evidence / decision log untouchable), with
   fold-then-delete verified per file (B5).

## 8. Deletion record — B2 executed 2026-07-06 (owner-ruled: delete, no external copy)

Disk artifacts deleted permanently (NOT git-recoverable). Manifest per ruling:

| Path | Size | Purpose | Rebuild basis |
|---|---|---|---|
| `trained_models/` (37 run dirs, 131 files) | 1.2G | 2026-04 PPO/SB3 multi-seed checkpoints behind RL_COLLAPSE_FINDINGS | Retrain via `training/train_*_sb3.py` (code + prepared-data pipeline intact); conclusions live in `RL_COLLAPSE_FINDINGS.md`; run metadata history in git (`registry.json` pre-deletion state at this commit's parent) |
| `scripts/huggingface/output/` | 984M | HF open-dataset release build | Dataset published on HuggingFace; rebuild via `merge_for_release.py` |
| `training/data_prep/output/` | 917M | Prepared RL training CSVs | Regenerate via `training/data_prep/prepare_training_data.py` from local news/price stores |
| `comparison_results/` | 752K | 2025-12〜2026-01 provider-comparison outputs | Conclusions absorbed into `docs/data/NEWS_PROVIDER_DATA_DICTIONARY.md` |
| `data_lake/` | 2.7M | `collect_ibkr_fundamentals.py` outputs (script deleted in scripts-consolidation) | Re-collect via IBKR if ever needed |

Tracked deletions in the same commit: `trained_models/registry.json` +
`trained_models/ppo_test_.../metadata.json` (checkpoints gone → registry rows point at
nothing; `model_registry._load_index` returns `[]` on missing file and future training
recreates it). `tests/test_inference_offline.py` now skips (by design — it `pytest.skip`s
on missing artifacts; un-skips after any retraining).

**Artifact policy (standing)**: model checkpoints / training outputs / HF build outputs
never enter the repo — `.gitignore` carries `trained_models/`; keeping a specific model
means an explicit export outside the working tree, never the repo.
