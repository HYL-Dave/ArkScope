# SA Extension Integration — Health / Setup Surface Boundary Note

> **Status**: boundary record only (2026-07-06, filed during scripts-runtime-consolidation review).
> **Backlog entry**: `PROJECT_PRIORITY_MAP.md` §P2.6. **Gated on** Desktop App Vision decisions
> (`DESKTOP_APP_VISION_DRAFT.md`) — do not build UI before the product surface settles.
> Scope here is deliberately one page: record the ownership boundary while the knowledge is
> fresh, so the future slice doesn't have to re-derive it.

## Why now (and why only this much)

The future desktop app must let a user confirm the SA extension pipeline works end to end:
extension captures → native host writes the local SA DB → app reads it. Some of that is
app-configurable, some is inherently browser-side. The scripts consolidation (2026-07-06)
touched every file involved, so the boundary is recorded now; implementation waits for the
Desktop App Vision to finalize.

## Registration chain (current, verified 2026-07-06)

```
Firefox/Chrome manifest (~/.mozilla/native-messaging-hosts/com.mindfulrl.sa_alpha_picks.json,
                         ~/.config/google-chrome/NativeMessagingHosts/…)
  └─ path → stable launcher ~/.local/share/arkscope/native-hosts/sa_alpha_picks_host.sh   (outside repo)
       └─ reads ~/.config/arkscope/sa_native_host.json  { project_root, python_path, host_script }
            └─ exec python src/sa_native_host.py        (fresh process per message, cwd=project_root)
```

Host id `com.mindfulrl.sa_alpha_picks` is **locked** (intentionally lowercase `mindfulrl`).
Repo moves/renames only ever require editing the config JSON — never the browser manifests.

## Ownership boundary

**App-owned (configurable / repairable from the app)**
- Launcher + config existence and validity checks; repair/rewrite of
  `~/.config/arkscope/sa_native_host.json` (`project_root`, `python_path`, `host_script`).
- Sidecar URL/port the host POSTs telemetry to.
- SA DB path + read/write health (freshness of last capture).
- **Simulated round-trip**: app spawns the host exactly as the launcher does and sends a
  length-prefixed `{"action":"ping"}` over stdin — verifies python/config/host/DB
  write-read without any browser.

**Browser/extension-owned (app cannot control, only document)**
- SA login/session; extension install/enable; browser permissions; page capture behavior
  and manual capture actions.
- **The real browser→host spawn hop.** Native messaging is initiated by the extension only;
  the app has no way to make the browser exercise it. App-side we can only verify its
  preconditions and show indirect evidence.

**App-display (status view)**
- Firefox/Chrome manifest present + points at the launcher; launcher exists + executable;
  config points at the current repo; simulated host ping OK.
- Last real extension write (timestamp via `job_runs` telemetry) and whether the app can
  read it back — the indirect evidence for the browser-owned hop.

## Existing building blocks (reuse, don't redesign)

- Native host → sidecar **job telemetry POST** (S-H1) → local `job_runs`
  (`run_summary_by_name` for SA jobs).
- `src/service/sa_market_news_health.py` health report.
- `REFACTOR_PROTECTION_SMOKE_GATES.md` Level 2 host smoke (the length-prefixed ping snippet)
  is the prototype of the app's simulated round-trip.
- `extensions/sa_alpha_picks/install.sh` / `install_firefox.sh` are the CLI precursors of the
  app's setup surface — keep them simple; they get absorbed, not extended.
