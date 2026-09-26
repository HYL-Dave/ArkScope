# Firefox Collector Setup

The Chrome extension remains the default build:

- `manifest.json`
- `install.sh`

Firefox uses a generated build so the Chrome path stays untouched:

- source manifest: `manifest.firefox.json`
- Firefox-only API shim: `compat_firefox.js`
- installer/build script: `install_firefox.sh`
- generated load directory: `build/firefox/` (gitignored)

## Why Firefox needs a separate build

Chrome Manifest V3 uses `background.service_worker`. Firefox does not support
extension background service workers, so the Firefox manifest uses
`background.scripts` instead.

Firefox also exposes promise-returning APIs under `browser.*`, while this
extension's background flow expects promise-returning `chrome.*` calls. The
Firefox build loads `compat_firefox.js` before `background.js` and `popup.js` so
the existing source can run without forking the scraper.

## Install

For an existing installation, preserve its add-on ID, browser storage and native
host registration. Rebuild from the main checkout without rerunning the installer:

```bash
python extensions/sa_alpha_picks/build_firefox.py \
  --source extensions/sa_alpha_picks \
  --output extensions/sa_alpha_picks/build/firefox
```

Then use **Reload** for **SA Alpha Picks Exporter** in
`about:debugging#/runtime/this-firefox`. If it is not listed, load
`extensions/sa_alpha_picks/build/firefox/manifest.json`. Do not load a `Test`
add-on or the Chrome source manifest. Building files does not reload Firefox.

The installer below is for first setup. It writes the shared native-host config;
do not run it from a temporary worktree to update an existing production add-on.

```bash
bash extensions/sa_alpha_picks/install_firefox.sh
```

Then in Firefox:

1. Open `about:debugging#/runtime/this-firefox`.
2. Click `Load Temporary Add-on...`.
3. Select `extensions/sa_alpha_picks/build/firefox/manifest.json`.
4. Sign in to Seeking Alpha in Firefox.
5. Select this installation using the activation steps below before running a sync.

Important: do not select files from `extensions/sa_alpha_picks/` directly.
That directory is the Chrome build and its `manifest.json` uses
`background.service_worker`, which Firefox rejects. Always load the generated
`build/firefox/manifest.json`.

## Expected verification

Successful runs should append entries to:

```text
data/logs/sa_native_host.log
```

Look for:

```text
Refresh current: ... picks saved
Refresh closed: ... picks saved
save_market_news: saved=...
```

## Notes

The shared **Capture Company Data** action also supports financial statements,
valuation, peers and annual estimates/revisions. Open the desired signed-in
company page first; the operation stays on that page and may scroll to load its
tables. Unsupported pagination or incomplete tables stop capture without
replacing earlier observations. Each category has an ArkScope source-selection
switch; reading captured data never refreshes the browser.

See [Data Acquisition And Updates](../../DATA_ACQUISITION_AND_UPDATES.md#sa-valuation-peers-and-forecasts)
for exact scope, loading, freshness and retention. Rebuild/reload this Firefox
artifact after source updates; a shared build does not certify a logged-in
Firefox capture without testing it in that browser.

Temporary Firefox add-ons are removed when Firefox restarts. For daily use,
either keep the collector Firefox session open or package/sign this as an
unlisted Firefox add-on later.

## Financial Statement Refresh

The popup's **Financial statement updates** selects **All App watchlist targets**
or selected tickers, statements and Annual/Quarterly USD/Absolute views. The two
check intervals initially use seven days; successful checks, not reads, advance
them. Annual pages also contain TTM. Scope preview shows missing/due/reusable
counts and a pacing-only lower bound before activation.

**Scheduled financial updates** controls financials only. **Update missing / due**
is an explicit queue even when that schedule is off; **Force refresh** is a
separate confirmed action. **Save only** saves a disabled financial schedule;
changed configuration cancels previous manual intent, while an unchanged save
does not. Use **Cancel queued update** for a remaining manual queue. Saving does
not select the acquisition browser.

Chrome and Firefox share the implementation and native acquisition authority.
Each installation retains its local schedule settings, but only the explicitly
selected installation may acquire. Switching the owner does not enable the other
browser's schedules. A closed browser cannot collect; there is no automatic
failover. Build parity is not a claim of signed-in Chrome acceptance.

## Activate Or Restore Routine Collection

1. Keep other automated browser installations stopped. Open the formal popup.
2. In **Financial statement updates**, keep valid targets or select **All App
   watchlist targets**. Leave **Scheduled financial updates** unchecked when
   restoring news/Alpha Picks only, then click **Save only**. Check that no manual
   financial queue remains; use **Cancel queued update** if it is shown.
3. Open **Acquisition limits and recovery**. Leave **Limit pages per hour / day**
   unchecked for no count cap. Existing capped installations keep their saved
   limits until explicitly changed. Optional limits require both total values and
   both routine reserves. Financial gap is independent of these optional limits.
4. Check **Other automated installations stopped or updated; use these acquisition
   settings.** Click **Use these settings here**. Verify **Collector: firefox
   (this installation)**, **Schedule off**, and the accepted page-budget status.
   Fresh setup does not need **Recover stopped capture**.
5. Enable **Auto-sync Alpha Picks** and **Auto-sync Market News**, preserving the
   intended existing intervals. Verify **Routine schedules: Alpha Picks on | News
   on**. Activation preserves the switches' current settings, so a switch turned
   off for cutover must be explicitly enabled again. Alarms do not run immediately.
6. For an immediate first run, use **Sync Latest News**, then **Quick Update** after
   the news run finishes. Check extraction/save outcomes, capture timestamps and
   audit delivery separately. Do not use Full/Deep repair to verify routine sync.

A collector tab closing is not a success signal. News may update existing list
entries without needing any article bodies. Alpha Picks must report current and
closed pick counts and a valid run outcome; merely recording a failure is not a
completed update. `Missing host permission for the tab` is a page-script error,
not a Native Messaging consent prompt. Do not reset desktop consent or add broad
website permissions to work around it.

The App may be reopened after the controlled schema migration is complete. Local
native saving does not require its sidecar, but audit delivery does: with the App
closed, receipts remain in a bounded browser outbox (100 records / seven days).
An **Audit pending** state is not proof that saving failed, nor proof that a run
was recorded. Reopen the App for delivery; advanced news recovery also needs it.

**Article body repair** is separate from restoring routine collection. Its
**Preview body repair** reads local candidates; **Start next up to 5** manually
queues one small batch through the same owner, pacing, restriction and priority
checks. Routine jobs take priority between background pages. Leaving historical
body repair unfinished does not stop news or Alpha Picks collection. The old
isolated test kit's five-pages-per-day ceiling is not a production policy.

## Native Connection And Desktop Consent

On Snap Firefox, desktop-portal permission is separate from the add-on permission
and host-manifest registration. A command-line host ping does not test this gate.
`Local app connection unavailable` means the refresh stopped before opening SA;
it is not evidence that the SA financial table failed to load.

The Firefox shim serializes native requests per host, including pending consent.
The background owns popup reconciliation requests as well, so losing popup focus
does not own the lifetime of the native call. The bridge accepts only the popup
sender and the three existing reconciliation actions, not arbitrary native calls.

When the portal records dialog contention, do not repeatedly reload or automatically
grant access. Inspect the exact host-specific permission and reset it only with
the user's consent, then allow the user to respond to the new system prompt.
Never change another host's permission or disable browser confinement as a workaround.

If the prompt remains unavailable, an explicit user-chosen manual authorization
is a separate alternative, not an automatic repair. Use the permission store's
`SetPermission` for only the verified native-host name and browser application ID,
then read it back with `GetPermission`. A remembered `yes` must still be followed
by a real browser-to-host ping; command-line host execution alone is insufficient.
Do not grant a wildcard, overwrite other applications' entries, or claim that
manual authorization repairs the desktop prompt. In the isolated acceptance run,
this unlocked the first AMD annual capture while prompt recovery remained unproven.

## Financial Refresh Rate Limits

Managed news, Alpha Picks, comments, financial pages and body repair share the
native authority. A recognized rate-limit page starts a common cooldown at six
hours, doubling on repeated failures up to seven days. Login/verification needs
explicit operator resolution; subscription restrictions pause the affected
capability. Neither uncapped mode, force refresh, reload nor browser handoff
clears these restrictions. Accepted old observations survive failed refreshes.

The page-count budget is optional; native admission and its navigation ledger are
not. Uncapped mode still serializes tasks, prioritizes routine work, retains the
financial/body page gap and records each navigation. Enabling a cap later counts
the retained rolling-window attempts. No count limit or interval is represented
as an SA-approved rate, and activity outside managed acquisition is not measured.
