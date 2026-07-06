# Docs Sweep Disposition Table — 2026-07 (B5a)

> **Status: ✅ EXECUTED 2026-07-06 (B5b) after owner approval**, with ONE verdict
> corrected at execution time per the fold-then-delete verification discipline:
> `P0_1_FULL_V1_SPEC` was mislabeled in this table (name-pattern guess) — it is the LIVE
> Replay Harness spec authority (cited by `src/agents/shared/bridge_tools.py:15`; Phase C
> inherited contract) and was KEPT. Everything else executed as approved: 2 relocations,
> 22 status headers added (24 verified pre-existing), 2 journal deletions folded into
> `PROJECT_HISTORY.md`, figures linked from `RL_COLLAPSE_FINDINGS.md`, 2+1 internal-IP
> generalizations. Follow-up (B6-adjacent): `bridge_tools.py:15` doc citation is fine
> (doc kept), no src/ edits were needed.
>
> **Verdicts**: `keep-current` (live canonical/reference, no action) ·
> `keep-record+header` (stays as historical evidence; B5b adds/verifies a one-line
> status header) · `relocate-then-record` (live-law section moves to a canonical home
> first) · `fold-then-delete` (one-line summary absorbed, then deleted; git = archive).
> **Method**: inbound links = repo-wide grep of the basename EXCLUDING docs/superpowers
> (plan self-references don't count). `README.md`-named files show inflated counts
> (basename collision) — judged by content instead. Per stop-loss, anything uncertain
> defaulted to keep, never delete.

## 0. Summary

| Verdict | Count |
|---|---|
| keep-current | 42 |
| keep-record+header | 55 |
| relocate-then-record | 2 |
| fold-then-delete | 3 |
| owner-choice (figures) | 5 |
| publication fixes (generalize IP) | 2 lines |
| out of scope (untracked local-only) | EXTENSIONS_REFERENCE / FUNDAMENTALS_GUIDE / insights / analysis logs (gitignored by rule) |

## 1. fold-then-delete (the only deletions proposed)

| File | Why | Absorption target |
|---|---|---|
| ~~`design/P0_1_FULL_V1_SPEC.md`~~ | **VERDICT CORRECTED AT EXECUTION (B5b): keep-current.** My table mislabeled it "pre-pivot product spec" from the name pattern; the file is the **Replay Harness Spec** — live authority cited by `src/agents/shared/bridge_tools.py:15` and named a Phase C inherited contract. Fold-then-delete verification caught it before deletion | (not deleted) |
| `design/DESIGN_DOCS_CONSOLIDATION_REVIEW.md` | Completed process journal (Groups 1–5 executed 2026-06-01) — PUBLICATION_REVIEW §3 says journals fold, not standalone authority | Outcomes already executed; one-line summary → `PROJECT_HISTORY.md`; method lives in `DOCS_GOVERNANCE_AUDIT` successor line below |
| `design/DOCS_GOVERNANCE_AUDIT_2026_05.md` | Same class — the audit that produced the policy; policy itself lives in `REFACTOR_PROTECTION_SMOKE_GATES.md` | Policy = gates doc; one-line summary → `PROJECT_HISTORY.md` |

## 2. relocate-then-record (live law moves first)

| File | Live-law section | Destination | Then |
|---|---|---|---|
| `design/PG_EXIT_REMAINDER_SCOPING.md` | §5 scripts survivor table (current law, 12 inbound links) | `REFACTOR_PROTECTION_SMOKE_GATES.md` (refactor-protection home) | keep-record+header (PG-exit slice tracker = migration evidence) |
| `design/SA_CUTOVER_3D_RUNBOOK.md` | Native-host write-path detail (only detailed doc of host actions) | `SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md` (or catalog §3.9) | keep-record+header |

## 3. docs/design — keep-current (22)

`PROJECT_PRIORITY_MAP` · `CURRENT_PROJECT_CONTEXT` · `README` (design index) ·
`LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC` (23 links) · `LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT`
(locked-decision record, referenced) · `REFACTOR_PROTECTION_SMOKE_GATES` ·
`ARKSCOPE_WORKBENCH_PRODUCT_SPEC` · `ARKSCOPE_PROVIDER_CATALOG` · `ARKSCOPE_TOOL_CATALOG` ·
`DESKTOP_APP_VISION_DRAFT` + `DESKTOP_APP_CARRYOVER_ANALYSIS` (open product thread) ·
`SA_EXTENSION_HEALTH_SETUP_BOUNDARY` (P2.6 authority) · `SA_EXTENSION_ROADMAP` (live
roadmap, updated 06-27, 9 links) · `MACRO_FRED_PRODUCT_SEMANTICS` (product law) ·
`LOCAL_STORAGE_TOPOLOGY` · `DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN` (draft, review pending)
· `LLM_AUTH_DRIVER_PLAN` (S3 open, 18 links) + `SLICE_7B3_SDK_DRIVER_DESIGN` ·
`IV_PROVIDER_PROOF_PACKET_PLAN` (Task 1 pending) · `AGENT_DATA_GAP_FALLBACK_PLAN`
(header says ACTIVE backlog) · `AI_RESEARCH_SURFACE_C2_SPEC` (self-declares "remains the
contract reference"; C-2 polish → C-3 upcoming) · `AI_RESEARCH_RUN_LIFECYCLE_PLAN` (open
post-ship plan) · `RL_COLLAPSE_FINDINGS` (decision record, 13 links) ·
`PHASE_C_UNIFIED_RUNNER_SPEC` (paused with resume gate — header already says so) ·
`REPO_HYGIENE_AUDIT_2026_07` + `DOCS_SWEEP_DISPOSITION_2026_07` (this process) ·
`archive/README` (archive mechanism).

## 4. docs/design — keep-record+header (24; B5b adds/verifies a one-line status header)

| File | Header should say |
|---|---|
| `PG_EXIT_COMPLETION_PLAN` | PG-EXIT CLOSED 2026-07-05 (already flipped — verify) |
| `PG_EXIT_N9_BATCH1_DROP_PLAN` / `_BATCH2_CLEANUP_PLAN` / `_BATCH3_PRICES_DROP_PLAN` | executed live, date + archive dir |
| `PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN` / `_P0C1_PRICES_RUNTIME_HARDENING_PLAN` | executed 2026-07-04 |
| `PG_EXIT_PG_UNREACHABLE_E2E_PLAN` | shipped; smoke lives at `src/smoke/pg_unreachable_e2e.py` |
| `PG_EXIT_S_H1_JOB_RUNS_LOCAL_PLAN` / `_S_H2_FINANCIAL_CACHE_COLD_START_PLAN` (0 links) | executed 2026-07-03 |
| `PG_EXIT_S_H_ORPHAN_APP_STATE_AUDIT` | audit record 2026-07-03 |
| `P1_2_PROVIDER_DISCOVERY` / `P1_2_SPEC` / `P1_3_SPEC` / `P1_4_SPEC` / `P1_5_S3_OSS_SPIKE_DECISION` | shipped/closed (P1_4 header exists — verify others) |
| `NEWS_DIRECT_LOCAL_PLAN` | superseded by executed news slices; record |
| `CONFIG_AUTHORITY_PLAN` | S-J shipped 2026-07-05; keyring = backlog |
| `CREDENTIAL_MANAGEMENT_PLAN` | partially open (keyring backlog) — header states what shipped |
| `SCHEDULER_HARDENING_PLAN` | scoping record; hardening shipped via P0-C.1 + news-burst slices |
| `DESKTOP_SHELL_SPIKE_PLAN` | spike complete; shell lives at `apps/arkscope-desktop` |
| `MULTI_FACTOR_SIGNAL_DETECTION` | P1.1 shipped 2026-04-26 |
| `SA_ALPHA_PICKS_CONTENT_CAPTURE` / `SA_COMMENT_INTELLIGENCE_PLAN` / `SA_EVIDENCE_FEED_C1_SPEC` | shipped; reference for C-3 |
| `AGENT_EVOLUTION_TRACKER` | historical build log (pre-pivot eras) |
| `AI_AGENT_ARCHITECTURE_PATTERNS` / `SKILL_PLUGINS_RESEARCH` | reference research, dated |
| `PHASE_A_KNOWLEDGE_GRAPH_SKETCH` / `PHASE_D_ANALYSIS_PIPELINE_SKETCH` | P2 sketches (headers exist — verify) |
| `AI_RESEARCH_CONTEXT_MEMORY_PLAN` | C-2c shipped 2026-06-15 |

## 5. docs/data (9) — all keep-current except one

keep-current: `DATA_INVENTORY` · `DATA_SUBSCRIPTION_GUIDE` · `IBKR_NEWS_API_LIMITATIONS`
(live runbook appendix — catch-up audit 07-06) · `NEWS_PROVIDER_DATA_DICTIONARY` (restored
07-06 with freshness header) · `OPTIONS_BASICS_TUTORIAL` / `OPTIONS_FLOW_GUIDE` /
`OPTIONS_PRICING_THEORY` (timeless reference, live options tooling) ·
`US_STOCKS_OPTIONS_DATA_SUBSCRIPTIONS`.
keep-record (already historical-marked): `NEWS_DATA_INVENTORY`.

## 6. docs top-level + small dirs

| File | Verdict | Why |
|---|---|---|
| `PROJECT_HISTORY.md` | keep-current | canonical origins/pivot/lineage; receives §1 fold summaries |
| `PUBLICATION_REVIEW.md` | keep-current | policy + new §5 incidents |
| `analysis/FINANCIAL_METRICS_FORMULAS.md` | keep-current | timeless metric reference (fundamentals tooling) |
| `analysis/FINANCIAL_METRICS_TRADING_GUIDE.md` | keep-current | companion guide |
| `analysis/SCORING_VALIDATION_METHODOLOGY.md` | keep-record+header | scoring-era methodology; dataset shipped, scorers archived |
| `features/SENTIMENT_DERIVED_FEATURES.md` | keep-record+header | RL-training feature definitions (2026-01, paused line) |
| `history/*` (3) | keep-current | provenance records under their own 3-rule governance |
| `notes/anthropic_sdk_streaming_lesson.md` | keep-current | still-true SDK gotcha (>21333 streaming) |
| `figures/backtest_archive/*.png` (5, 772K) | **owner-choice** | zero inbound links (orphans). Recommend **keep + link from `RL_COLLAPSE_FINDINGS`** — with checkpoints deleted they are the only surviving visual evidence; alternative: delete as orphans |

## 7. docs/superpowers (25 plans + 6 specs) — keep-record family

- All plans/specs = completed implementation records → keep-record. No deletions.
- **13 plans lack a status header** (B5b adds one line each): 06-27 news-direct-cutover ·
  06-27 news-identity-repair · 06-28 ibkr-news-10172 · 06-28 news-normalization-offline ·
  06-29 n7-migration · 06-30 news-n8a-pg-exit · 07-01 s-a1-ibkr-worker ·
  07-02 s-b-fundamentals · 07-02 s-j-phase-0-1 · 07-04 data-sources-ui-cleanup ·
  07-05 news-burst-hardening · 07-06 dead-code-ui-sweep · 07-06 ibkr-news-catchup-audit.
  Specs checked for the same in the batch.
- **Publication fixes (2 lines, generalize per policy §1)**:
  `2026-06-28-news-normalization-offline-foundation.md:1297` and
  `2026-07-04-data-sources-post-pg-exit-ui-cleanup.md:451` carry the internal IBKR
  gateway IP → `<ibkr-gateway-host>`.

## 8. User-facing-content candidates (feeds P2.5 / README — no action in B5b)

Surfaced while classifying: provider capability differences
(`NEWS_PROVIDER_DATA_DICTIONARY` durable sections), options data subscription guidance
(`US_STOCKS_OPTIONS_DATA_SUBSCRIPTIONS`, `DATA_SUBSCRIPTION_GUIDE`), IBKR news 300-cap
behavior (`IBKR_NEWS_API_LIMITATIONS` runbook appendix), "why get API keys" framing.
Handed to §P2.5 as source material.
