# Refactor Protection Smoke Gates

> **Status**: active guardrail for large refactors.
> **Purpose**: preserve current data-ingestion and extension runtime paths while allowing old architecture/docs/framing to be deleted, archived, or rewritten.
> **Rule of thumb**: protect operational paths and reusable capabilities, not pre-pivot architecture.

---

## 1. Protected Runtime Surface

These paths must keep working through docs cleanup, local-first migration, and module-level refactors:

- `python -m src.daily_update --all --scope active-universe --sync-db`
  — protection level since 3e-E / F6 (2026-06-11): **flag-compatible + same effects**,
  NOT byte-identical. daily_update is now a thin CLI wrapper over the app scheduler
  core (`src/service/data_scheduler.run_source`): same flag set, same per-source step
  set (collect → PG sync → local mirror refresh), exit 0/1 semantics, `--dry-run`
  prints the plan and never touches IBKR/DB/job_runs. What changed by design:
  per-step telemetry is now the scheduler's `collect.<source>` rows
  (trigger_source='cli') plus one `daily_update.run` summary row; news sources run
  in-process (adapters), IBKR sources stay subprocesses; runs share the app's
  per-source/IBKR locks (an app-scheduled run in the same sidecar makes the CLI
  skip, not double-fetch — separate processes still can't see each other's locks).
  The gate when refactoring: `--help` exits 0, the protected command's `--dry-run`
  lists the same sources, no-scope invocations error with exit 1, and a real run
  produces the same collected/synced data.
  (History: slice 2 / 2026-06-08 retired `--tier all` + the tickers_core writeback
  and made price scope explicit; 3e-B / 2026-06-10 added per-step telemetry;
  3e-E / 2026-06-11 extended the explicit-scope requirement to EVERY source —
  `config/tickers_core.json` no longer serves any runtime default, in daily_update
  or in the collectors themselves. `--scores` stays a separate opt-in subprocess.)
- Chrome SA Alpha Picks extension -> Native Messaging host -> DB
- Firefox SA Alpha Picks extension -> Native Messaging host -> DB
- SA native host stable launcher:
  - `~/.local/share/arkscope/native-hosts/sa_alpha_picks_host.sh`
  - `~/.config/arkscope/sa_native_host.json`
- Existing DB-backed data reads/writes used by collection scripts, SA extension, and current agent tools.

Breaking these is a regression even if the refactor is architecturally correct.

---

## 2. Reusable Capabilities

These can be moved, adapted, or re-wrapped, but should not be casually deleted:

- Data source clients and collection orchestration.
- `DataAccessLayer` / backend protocol boundaries.
- SA ingestion, comment intelligence, article/market-news capture, and job recording.
- Tools registry and financial tool surface used by agents.
- Reports, memory, attachments, replay, compression, subagents, and structured output contracts.
- Macro/news/signals/options functionality that supports the local-first workbench.

If a module is rewritten, preserve the capability boundary or explicitly record what replaces it.

---

## 3. Replaceable Surface

These are allowed to change aggressively after an absorption check:

- Root entrypoint prose that still describes RL/CLI/Postgres-first positioning.
- Pre-pivot HOW documents: service-first, RL-productionization, PG-first, Supabase-first, Discord-first, CLI-first.
- One-off scoring / comparison / model-bakeoff research scripts and generated reports.
- `NewsExtraction` / FNSPID-era batch workflow docs, unless a current import/runtime dependency is found.
- Training/RL docs and scripts not on the protected runtime path; paused means preserve code/history as needed, not keep active-looking docs.

Delete is acceptable when residual facts are already absorbed into canonical docs or can be recovered from git history.

---

## 4. Gate Levels

### Level 0 -- Docs-only cleanup

Use for pure docs deletes, archive moves, and entrypoint rewrites.

```bash
# Catch leftover hardcoded absolute paths or the pre-rename project name.
rg -n "MindfulRL-Intraday" .
rg -n -e "/home/[a-z]" -e "/mnt/" -- '*.py' '*.sh' '*.json'
```

Remaining hits must be historical/runbook/archive references, not executable paths.

### Level 1 -- Shell/script path changes

Use when editing `scripts/`, `training/scripts/`, installer scripts, or path-handling code.

```bash
bash -n extensions/sa_alpha_picks/install.sh
bash -n extensions/sa_alpha_picks/install_firefox.sh
bash -n training/scripts/run_polygon_production.sh
bash -n training/scripts/run_feature_comparison.sh
python -m src.daily_update --help
# Plan-only (must list polygon_news/finnhub_news/ibkr_news/ibkr_prices and exit 0
# without touching IBKR/DB/job_runs):
python -m src.daily_update --all --scope active-universe --sync-db --dry-run
```

### Level 2 -- SA/native-host/API/DB-touching changes

Use when editing SA extension, native host, DAL, job runs, API routes, or DB-backed tools.

```bash
python -m pytest tests/test_sa_tools.py tests/test_job_runs.py -q
```

Then smoke the installed native host from outside network-restricted sandboxes:

```bash
python - <<'PY'
import json
import struct
import subprocess

launcher = "~/.local/share/arkscope/native-hosts/sa_alpha_picks_host.sh"
for msg in (
    {"action": "ping"},
    {"action": "get_market_news_recent_ids", "limit": 5},
):
    payload = json.dumps(msg).encode("utf-8")
    proc = subprocess.run(
        [launcher],
        input=struct.pack("<I", len(payload)) + payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=True,
    )
    size = struct.unpack("<I", proc.stdout[:4])[0]
    print(proc.stdout[4:4 + size].decode("utf-8"))
PY
```

Expected: both responses have `"status": "ok"` and `ping` returns `project_root=<repo-root>`.

### Level 3 -- Live data path changes

Use before/after storage migration cuts, collection refactors, installer changes, or browser-extension recovery.

```bash
# News + prices (prices need an explicit scope since slice 2). Add --scores to
# also push news_scores (now a separate opt-in).
python -m src.daily_update --all --scope active-universe --sync-db
```

For browser extension validation:

1. Chrome: load unpacked from `<repo-root>/extensions/sa_alpha_picks`, then re-run `extensions/sa_alpha_picks/install.sh` with Chrome's current extension ID.
2. Firefox: load temporary add-on from `<repo-root>/extensions/sa_alpha_picks/build/firefox/manifest.json`.
3. Run Quick Refresh in each browser.
4. Confirm fresh log entries:

```bash
tail -n 120 data/logs/sa_native_host.log
```

Passing evidence is a timestamped `record_extension_job ... status=succeeded` for each browser path being validated.

---

## 5. Refactor Policy

- Do not keep stale docs just because their implementation once existed.
- Do not delete active runtime code only because its old product framing is wrong.
- Do not create the old repo path symlink as normal architecture; use it only as emergency recovery.
- When a file is deleted, record where any residual useful fact was absorbed, or state that git history is the recovery path.
- For risky changes, run the smallest gate that covers the touched surface; do not turn every docs edit into a live crawler run.

---

## 6. `scripts/` survivor rule (AUTHORITY — relocated from `PG_EXIT_REMAINDER_SCOPING.md` §5, 2026-07-06)

- **`scripts/` holds only app-unrelated or historical material.** `src/` never imports
  `scripts/`. Anything runnable that the app, its gates, or its operators actively depend
  on is `python -m src.<module>` — the only exceptions are the explicitly user-ruled
  retained families below.
- **Provider clients stay in `data_sources/` unless deliberately migrated.** Runtime
  orchestration / domain logic lives in `src/<domain>/...` modules. Do **not** create a
  second provider layer under `src/providers/`.

**Survivor table (anything else appearing under `scripts/` is residue):**

| Retained | Why (one line) |
|---|---|
| `scripts/analysis/` | One-off options research scans (BS-vs-American, mispricing, unusual activity) — research, not runtime |
| `scripts/diagnostics/` | Manual operator probes (`probe_ibkr_news_bodies.py`) — ad hoc, keyed, never scheduled |
| `scripts/huggingface/` | Open-data release tooling + scoring prompts — historical record (user-ruled retained) |
| `scripts/live/` | Manual live-API smokes (SDK driver/route) — operator-run with real keys, deliberately outside CI |
| `scripts/migration/` | Completed PG-exit migration CLIs kept as gate evidence (N8a/N9 batches, cutovers, reconciles) |
| `scripts/p1_2/` | FRED provider-evaluation smoke — historical evidence for P1.2 |
| `scripts/scoring/` | Scoring archive + occasional local score-import CLI (`import_news_scores_local.py`) — user-ruled retained |
| `scripts/testing/` | Manual paid-API experiments (financial datasets) — exploratory, not gates |
| `scripts/visualization/` | Legacy news dashboard/data-loader — historical |
| `scripts/__init__.py` | Retained package marker: historical tests import `scripts.scoring` / `scripts.migration` namespaces |

Changing this table = changing a standing ruling (owner decision + map §10 entry), not a
refactor detail. Execution record of the consolidation that finalized it:
`docs/superpowers/plans/2026-07-06-scripts-runtime-consolidation.md` + map §10 2026-07-06.
