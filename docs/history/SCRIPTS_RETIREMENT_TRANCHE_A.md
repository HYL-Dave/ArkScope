# Scripts Retirement Tranche A History

> **Status:** KNOWLEDGE AND LINEAGE RECORD
>
> **Date:** 2026-08-01

This document preserves the durable knowledge extracted while retiring
research utilities, diagnostic probes, and spent migration gates from the
root `scripts/` namespace. Git history preserves removed executable bytes.
This page does not turn any retired command into a supported runbook.

## 1. Spent Migration Owners

The completed migration behavior belongs to its reviewed design, plan, and
evidence, not to an indefinitely runnable one-shot CLI.

| Retired family | Removed CLI/core/test scope | Durable reviewed owner |
|---|---|---|
| Legacy scheduler and IV retirement | `retire_legacy_scheduler_iv.py` and its gate tests | [design](../superpowers/specs/2026-07-26-legacy-scheduler-iv-domain-retirement-design.md), [plan](../superpowers/plans/2026-07-26-legacy-scheduler-iv-domain-retirement.md), and [evidence](../superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md) |
| Local job-runs cutover | `job_runs_local_cutover.py`, `src/service/job_runs_cutover.py`, and migration-only tests | [S-H1 plan](../design/PG_EXIT_S_H1_JOB_RUNS_LOCAL_PLAN.md) and [PG-exit remainder record](../design/PG_EXIT_REMAINDER_SCOPING.md) |
| N9 batch 1 | `n9_batch1_pg_drop.py` and its tests | [N9 batch-1 executed plan](../design/PG_EXIT_N9_BATCH1_DROP_PLAN.md) |
| N9 batch 2 | `n9_batch2_cleanup.py` and its tests | [N9 batch-2 executed plan](../design/PG_EXIT_N9_BATCH2_CLEANUP_PLAN.md) |
| N9 batch 3 prices drop | `n9_batch3_prices_drop.py` and its tests | [N9 batch-3 executed plan](../design/PG_EXIT_N9_BATCH3_PRICES_DROP_PLAN.md) |
| N7 normalized-news migration | `preview_news_normalization.py`, `apply_news_normalization.py`, the three migration cores, and migration-only tests | [N7 design](../superpowers/specs/2026-06-29-news-normalization-n7-migration-design.md) and [implementation plan](../superpowers/plans/2026-06-29-news-normalization-n7-migration.md) |
| N8a normalized-news cutover | `news_n8a_cutover.py`, `src/news_normalized/cutover.py`, and its tests | [N8 design](../superpowers/specs/2026-06-30-news-n8-pg-exit-design.md), [N8a plan](../superpowers/plans/2026-06-30-news-n8a-pg-exit.md), and [direct-local closeout](../design/NEWS_DIRECT_LOCAL_PLAN.md) |
| S-G score cutover | `news_scores_cutover.py`, `src/news_normalized/score_cutover.py`, and cutover-only tests | [S-G implementation plan](../superpowers/plans/2026-07-03-s-g-scorer-cutover.md) and [PG-exit remainder record](../design/PG_EXIT_REMAINDER_SCOPING.md) |
| P0-C price reconciliation and HAPN patch | `p0c_prices_reconcile.py`, `p0c_hapn_patch.py`, both price migration cores, and migration-only tests | [P0-C executed plan](../design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md) |

Tranche A removes the migration executables and their gate-only tests only
after the exact collection delta is reviewed. Current product tests are not
replaced by historical assertions.

## 2. IBKR News Diagnostic Lineage

The fixed-ID `probe_ibkr_news_bodies.py` was created for the reviewed IBKR
historical-news-body and error-10172 investigation. It was a bounded premise
probe, not an operator workflow.

Its durable behavior is owned by:

- the [10172 capture design](../superpowers/specs/2026-06-28-ibkr-news-10172-capture-design.md);
- the [implementation plan](../superpowers/plans/2026-06-28-ibkr-news-10172-capture.md);
- `src/news_normalized/ibkr_adapter.py`; and
- the production-contract assertions in
  `tests/test_news_normalized_ibkr_adapter.py`.

Task 3 removes three tests that exist only to import or verify the spent probe.
The other 17 adapter contract nodes remain. Removing the executable does not
remove typed unavailable handling, output sanitization, or adapter behavior.

## 3. Retired News Dashboard Knowledge

The removed Streamlit/Plotly utility read historical parquet files directly.
It was not a supported ArkScope surface and its undeclared dependencies made
execution environment-dependent.

The useful product/research gap list was:

- source and publisher distribution;
- monthly publication volume;
- article content-length distribution;
- ticker coverage;
- publication-time heatmap; and
- article explorer with filter, search, and pagination.

This is a knowledge list, not a commitment to rebuild a dashboard. Any future
surface must start from current SQLite/DAL contracts and current user
workflows, not restore the old data loader.

## 4. Unusual Options Candidate

The retired `scan_unusual_activity.py` wrapper called scanner primitives that
remain in [`IBKRDataSource`](../../data_sources/ibkr_source.py). A future
unusual-options feature remains a possible product candidate, but it requires
an explicit provider capability/subscription UX and its own reviewed design.

The old wrapper was not a trustworthy supported command:

- its usage text advertised `--max-price`, but the parser had no such option;
- `--location` was printed and written to output metadata but never forwarded
  to the scanner request; and
- importing the module replaced `IBKR_CLIENT_ID` with a random value.

Deleting the wrapper does not delete the tested scanner primitives. This
record does not promise a scanner UI or authorize provider requests.

## 5. Financial Datasets Research

The two default-collected Financial Datasets probes were retired after static
extraction. Their endpoint and spend-policy input is preserved in
[Financial Datasets Capability And Spend Decision Input](../design/FINANCIAL_DATASETS_CAPABILITY_SPEND_DECISION.md).

That document is not a live capability registry. Future metered behavior is a
separate product slice.

## 6. News-Scoring Provenance

The published open dataset keeps its exact historical provenance in:

- [SCORING_PROMPTS.md](./news-scoring/SCORING_PROMPTS.md); and
- [column_mapping.md](./news-scoring/column_mapping.md).

The HuggingFace packager is retired; the published artifacts and Git history
are the release record. The current scorer and local score importer remain
transitional live owners under `scripts/scoring/` until the separately
reviewed Tranche B atomically retires the legacy per-article score contract.

This document does not promise support for rebuilding the old score dataset,
dashboard, scanner wrapper, or batch-scoring pipeline.
