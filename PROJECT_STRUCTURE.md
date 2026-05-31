# ArkScope — Project Structure

> This file is intentionally a **short pointer**. A hand-maintained full directory
> tree drifts too fast to trust; the authoritative, current structure lives in the
> canonical docs below.

**Start here:**

- `docs/design/CURRENT_PROJECT_CONTEXT.md` — authoritative pointer index (canonical sources of truth)
- `docs/design/PROJECT_PRIORITY_MAP.md` — §1 current direction, §10 decision log ("what's next?")
- `docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md` — v1 product / storage / sync contract
- `README.md` — operational quickstart + protected runtime paths
- `docs/PROJECT_HISTORY.md` — origins, open data, and the 2026-05 pivot

**Top-level layout (high level only):**

| Path | What |
|------|------|
| `src/` | Agent, tools, DAL, analysis pipeline, monitor, multi-factor signals |
| `data_sources/` | Data-source API clients (Finnhub, Tiingo, SEC EDGAR, Polygon, IBKR, …) |
| `scripts/collection/` | Data ingestion / daily update — **protected runtime path** |
| `extensions/sa_alpha_picks/` | Seeking Alpha browser extension + Native Messaging host |
| `training/` | RL training — **paused** (see `docs/design/RL_COLLAPSE_FINDINGS.md`) |
| `config/` | `.env`, `user_profile.yaml`, watchlists, sectors, skills |
| `docs/` | Design docs, data/feature guides, project history |

*For anything more detailed than this, read the canonical docs above rather than
trusting a hand-maintained tree.*
