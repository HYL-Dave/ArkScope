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

> **Status**: local-first SQLite + DuckDB storage is the target per the spec;
> **today** the stack still runs PostgreSQL-backed. The migration is sequenced in
> the priority map.

## Operational quickstart

Currently-supported runtime paths. These are **protected** during refactors — see
`docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md`.

```bash
# 1. install + configure
pip install -r requirements.txt
cp config/.env.template config/.env            # then fill in API keys

# 2. database (current stack)
docker compose -f docker/docker-compose.yml up -d postgres

# 3. data collection
python -m src.daily_update --status         # check data freshness
python -m src.daily_update --all --sync-db  # collect everything + sync to DB

# 4. run the agent
python -m src.agents                           # interactive CLI (--provider openai for GPT-5.x)
```

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

- `src/` — agent, tools, DAL, analysis pipeline, monitor, signals, data ingestion (`src/collectors/`, `src/daily_update.py`)
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
