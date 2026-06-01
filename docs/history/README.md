# docs/history/

Curated historical records for ArkScope — the few things worth keeping after a
component is retired, kept separate from the short narrative in
[`../PROJECT_HISTORY.md`](../PROJECT_HISTORY.md).

## What goes here (3 rules)

1. **Only small, non-recoverable provenance** — WHAT/WHY that prose can't fully
   capture (a small machine-readable mapping, a verified comparison result, the
   reasoning behind a retired decision).
2. **No outdated HOW** — retired pipelines, runbooks, and tool usage are *deleted*
   (git history recovers them); they are not parked here.
3. **No large or re-downloadable data** — datasets, model weights, and anything
   fetchable again stay out of the repo. `artifacts/` holds only tiny configs / JSON.

If a file doesn't satisfy all three, delete it (recoverable via git) or fold a
summary into `PROJECT_HISTORY.md` instead. This directory is a record, not a
dumping ground.

## Contents

- `FNSPID_NEWS_EXTRACTION.md` — lineage of the retired FNSPID news extraction that
  fed the open dataset (HYL/NASDAQ-News-Multi-LLM-Scores).
- `artifacts/fnspid_tickers_89.json` — the original 89-ticker NASDAQ universe.
