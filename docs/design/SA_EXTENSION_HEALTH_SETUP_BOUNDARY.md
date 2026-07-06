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
- Sidecar telemetry endpoint the host POSTs to — **display it** (default
  `http://127.0.0.1:8420`, from `ARKSCOPE_API_HOST/PORT/BASE_URL` + optional
  `ARKSCOPE_API_TOKEN`, `sa_native_host.py:721-730`), and the one-click test must cover the
  telemetry leg, not just the ping.
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

## Incident grounding (2026-07-06 cutover test) — structural, not ops

During the consolidation cutover test, every `record_extension_job` POST got Connection
refused while all `sa_capture.db` writes succeeded — and follow-up tracing showed this is
**structural under the daily `npm run dev:desktop` workflow**, not a forgotten process:

- The Electron shell **already** spawns the sidecar on an **ephemeral port with a per-run
  token** (`apps/arkscope-desktop/main.js:98-112`; observed live: `python -m src.api` on
  127.0.0.1:34145). The renderer learns the port from the shell; the **native host cannot**
  — it is spawned by the browser and inherits the browser's environment, so it POSTs to the
  default `127.0.0.1:8420` (`sa_native_host.py:721-730`) and would be rejected by the token
  check (`src/api/app.py:151-153`) even if it guessed the port.
- Consequence: extension telemetry only ever lands when a **standalone** no-token sidecar
  happens to be listening on 8420 (true during live-verification sessions — last successful
  row `sa_market_news_refresh/extension` at `2026-07-05T16:05Z`); under dev:desktop alone it
  silently fails while the extension sees "ok" (best-effort by design) and the data lands.
  That invisible split is exactly what this surface must show.
- Port map for the record: sidecar API default **8420** (`src/api/__main__.py`), web dev
  **8430** (`vite.config.ts`), ArkScope-owned 84xx block; dev:desktop sidecar = ephemeral.

**Design constraint (dynamic ports)**: the API base + token MUST travel through the
app-writable config file (add `api_base`/`api_token` to
`~/.config/arkscope/sa_native_host.json`; the launcher exports them, or the host reads the
config directly), written by the Electron shell at spawn time — it already knows both.
Env-var-only steering of the telemetry target is not a viable mechanism.

**Sub-fix not gated on Desktop App Vision**: this config-file plumbing (shell writes
`api_base`/`api_token` on spawn; host prefers config over env defaults) is a small
standalone slice with no UI — it can ship before the rest of P2.6 whenever prioritized.

**RESOLVED 2026-07-06**: part 1 shipped + live-proven (plan
`2026-07-06-sa-extension-telemetry-health.md`, map §10 closeout). Both resolution paths
verified with real Quick Refresh rows in `job_runs`: dev:desktop via `source=config`
(run_id=13702) and standalone-8420 via `default` (run_id=13703); clean shutdown clears the
config api fields. Precedence shipped as env > config > default. The health panel covers
the segment checklist; part 2 (embedded browser question) stays open.

## Existing building blocks (reuse, don't redesign)

- Native host → sidecar **job telemetry POST** (S-H1) → local `job_runs`
  (`run_summary_by_name` for SA jobs).
- `src/service/sa_market_news_health.py` health report.
- `REFACTOR_PROTECTION_SMOKE_GATES.md` Level 2 host smoke (the length-prefixed ping snippet)
  is the prototype of the app's simulated round-trip.
- `extensions/sa_alpha_picks/install.sh` / `install_firefox.sh` are the CLI precursors of the
  app's setup surface — keep them simple; they get absorbed, not extended.
