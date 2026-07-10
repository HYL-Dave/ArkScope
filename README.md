# ArkScope

> **Local-first financial research agent workbench** — a single-user research
> environment combining an LLM agent (Anthropic + OpenAI), a financial data layer
> (news / Seeking Alpha / macro / prices / fundamentals / signals / options), and a
> research GUI.
>
> Renamed from **MindfulRL-Intraday** on 2026-05-31. The lowercase `mindfulrl` that
> remains (PostgreSQL DB name + browser native-messaging host id) is intentional.

## What this is

ArkScope is being repositioned (2026-05) from an RL + LLM intraday-trading research
repo into a **local-first financial research agent workbench**: the agent reads its
own accumulated knowledge across sessions and machines, the user sees and edits
everything via a research GUI, and zipping the profile directory moves work between
machines.

- **Current direction & "what's next?"** → `docs/design/PROJECT_PRIORITY_MAP.md` §1
- **Authoritative doc index (read this first)** → `docs/design/CURRENT_PROJECT_CONTEXT.md`
- **v1 product contract** (storage / sync / page IA / migration) → `docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`
- **Where the project came from + open data** → `docs/PROJECT_HISTORY.md`
- **LLM auth / Claude-subscription Research driver** (design) → `docs/design/LLM_AUTH_DRIVER_PLAN.md` and `docs/design/SLICE_7B3_SDK_DRIVER_DESIGN.md`

> **Status**: local-first SQLite storage is **live** — the PG exit completed
> 2026-07-05. PostgreSQL holds frozen archives only (restore/inspect via
> `docker/README.md`); the app runtime needs no database server.

## The workbench GUI (primary surface)

The product is a desktop research workbench: an Electron shell (or browser dev
mode) over a local FastAPI sidecar. Current surfaces (as of 2026-07-10): 工作台
(Home overview) · 自選股 (Watchlist) · 全部標的 (Universe) · **AI 研究** (research
threads with per-run model/effort/stance) · **持倉** (Holdings — manual + read-only
IBKR sync) · 新聞·事件 (News, incl. Seeking Alpha capture) · System health ·
Settings (data providers, model routing, credentials, 投資人設定 incl. the
calibration chat). Alerts and Notes are planned (nav present, disabled).

```bash
# desktop app (starts its own sidecar on an ephemeral port)
npm install && npm run dev:desktop

# or: browser dev mode against a manually-run sidecar on :8420
python -m src.api            # FastAPI sidecar
npm run dev:web              # Vite dev server
```

## Operational quickstart (CLI / data paths)

Currently-supported runtime paths. These are **protected** during refactors — see
`docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md`.

```bash
# 1. install + configure
pip install -r requirements.txt
cp config/.env.template config/.env            # then fill in API keys

# 2. data collection
python -m src.daily_update --status         # check data freshness
python -m src.daily_update --all --sync-db  # collect everything + sync to DB

# 3. run the agent
python -m src.agents                           # interactive CLI (--provider openai for GPT-5.x)
```

(No database server needed — storage is local SQLite under `data/`. Docker
exists only for PG **archive** access: `docker/README.md`.)

### Seeking Alpha Alpha Picks (optional)

Reads the Alpha Picks portfolio via a browser extension → Native Messaging host →
DB. Requires an SA Alpha Picks subscription; disabled by default.

```bash
bash extensions/sa_alpha_picks/install.sh          # Chrome
bash extensions/sa_alpha_picks/install_firefox.sh  # Firefox
# then set seeking_alpha.enabled: true in config/user_profile.yaml
```

Extension design + code: `docs/design/SA_EXTENSION_ROADMAP.md` and `extensions/sa_alpha_picks/`.

## Project layout

High-level only; for the authoritative structure see
`docs/design/CURRENT_PROJECT_CONTEXT.md` (or `PROJECT_STRUCTURE.md` for the pointer
stub).

- `apps/arkscope-web/` — the workbench GUI (React + Vite); `apps/arkscope-desktop/` — Electron shell
- `src/` — agent, tools, DAL, API sidecar (`src/api/`), analysis pipeline, monitor, signals, data ingestion (`src/collectors/`, `src/daily_update.py`)
- `data_sources/` — data-source API clients
- `scripts/` — historical / one-off utilities only (no runtime paths; those live in `src/`)
- `extensions/sa_alpha_picks/` — SA browser extension + native host
- `docs/design/` — current specs & decision log (`PROJECT_PRIORITY_MAP.md` first)
- `training/` — RL training (paused; see `docs/design/RL_COLLAPSE_FINDINGS.md`)

## Open data

We open-sourced a multi-LLM financial-news scoring dataset (127,176 NASDAQ
articles re-scored by 11 LLMs for sentiment and risk). Details + HuggingFace link:
**`docs/PROJECT_HISTORY.md`**.

## License

Released under the **MIT License**.
