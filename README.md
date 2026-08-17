# ArkScope

> **Local-first financial research workbench** — a single-user desktop environment
> combining Anthropic and OpenAI research workflows with local financial data
> (news, Seeking Alpha, macro, prices, fundamentals, portfolios, and options).
>
> Renamed from **MindfulRL-Intraday** on 2026-05-31. The lowercase `mindfulrl`
> retained by browser extension identifiers is intentional.

## Overview

ArkScope is a local-first financial research workbench. The Electron shell runs a
React interface and starts a local FastAPI sidecar on an ephemeral loopback port.
Primary app state, job history, and collected data are stored in local SQLite files
under `data/`; the app does not require an external database server.

The current GUI contains Home, Watchlist, Universe, News, AI Research, Holdings,
System, and Settings. AI Research owns persisted threads and model runs; Settings
owns provider configuration, model credentials and routing, collection schedules,
storage status, and investor-profile calibration.

Alerts and Notes remain planned product surfaces. They are not yet shipped and
therefore are intentionally absent from the current navigation rather than shown
as disabled placeholders.

Canonical project information:

- **Current context and authority order** → `docs/design/CURRENT_PROJECT_CONTEXT.md`
- **Product contract** → `docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md`
- **Architecture and storage contract** → `docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`
- **Current priorities and decision log** → `docs/design/PROJECT_PRIORITY_MAP.md`
- **Design-document status index** → `docs/design/README.md`

## Run locally

```bash
# one-time setup
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
npm install

# desktop app: starts Vite, Electron, and its own FastAPI sidecar
npm run dev:desktop
```

Configure credentials, provider settings, and schedules from Settings. The private
`config/.env` file remains an optional operator/import surface, not the default app
configuration authority.

Browser development uses two terminals:

```bash
python -m src.api  # FastAPI sidecar on 127.0.0.1:8420
npm run dev:web    # Vite dev server on 127.0.0.1:8430
```

## Operator checks and collection

Routine schedules and manual runs belong in Settings. `src.daily_update` remains a
thin operator wrapper over the same scheduler services:

```bash
python -m src.daily_update --status
python -m src.daily_update --all --scope active-universe --dry-run
python -m src.daily_update --all --scope active-universe  # provider calls + local writes
```

The wrapper requires an explicit ticker scope. Its `--all` flag covers the Polygon,
Finnhub, and IBKR news sources plus IBKR prices; macro and SEC schedules are managed
separately by the app.

### Seeking Alpha browser collector (optional)

The browser extension captures Alpha Picks, articles, comments, and Market News
through a Native Messaging host into `data/sa_capture.db`. It requires a compatible
Seeking Alpha subscription and a signed-in browser session.

```bash
# Chrome: first load extensions/sa_alpha_picks/ as an unpacked extension.
bash extensions/sa_alpha_picks/install.sh

# Firefox: builds the Firefox variant and registers its native host.
bash extensions/sa_alpha_picks/install_firefox.sh
```

Follow `extensions/sa_alpha_picks/FIREFOX.md` for the temporary add-on steps. Runtime
health and capture history are visible in Settings. Design and implementation live
in `docs/design/SA_EXTENSION_ROADMAP.md` and `extensions/sa_alpha_picks/`.

## Project layout

High-level only; use `docs/design/CURRENT_PROJECT_CONTEXT.md` for authority and
`PROJECT_STRUCTURE.md` for the short structure pointer.

- `apps/arkscope-web/` — React/Vite workbench; `apps/arkscope-desktop/` — Electron shell
- `src/` — research runtimes, tools, local data access, API sidecar, monitoring, and collection
- `data_sources/` — provider API clients
- `extensions/sa_alpha_picks/` — Seeking Alpha browser extension and native host
- `config/` — reviewed defaults plus ignored private overrides
- `data/` — ignored local SQLite stores, logs, and runtime artifacts
- `docs/design/` — product and architecture authorities, plans, and decision records

Retired implementations are recovered from Git history rather than kept as dormant
compatibility surfaces.

## Open data

The project includes research datasets and evidence generated from public market
data. Published datasets must follow `docs/PUBLICATION_REVIEW.md`.

## License

Unless otherwise noted, project-authored source code and documentation are
licensed under the [Apache License, Version 2.0](LICENSE). Third-party
components, assets, and data remain subject to their respective licenses and
terms.
