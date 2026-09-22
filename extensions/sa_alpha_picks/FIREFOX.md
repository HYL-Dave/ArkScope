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

```bash
bash extensions/sa_alpha_picks/install_firefox.sh
```

Then in Firefox:

1. Open `about:debugging#/runtime/this-firefox`.
2. Click `Load Temporary Add-on...`.
3. Select `extensions/sa_alpha_picks/build/firefox/manifest.json`.
4. Sign in to Seeking Alpha in Firefox.
5. Run `Quick Update` from the extension popup.

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

The popup's **Financial statement updates** selects tickers, statements and
Annual/Quarterly views for USD/Absolute tables. Save the interval (initially seven
days) and enable **Scheduled**, or use **Update now** for an explicit new capture.
Reads stay local. Only successful scopes advance their check time; failures show
their previous successful time and retry reason. Verification or access/structure
problems pause automatic work until corrected and manually retried.

This is shared with Chrome, but each browser installation has its own schedule.
Do not enable the same scope in both browsers merely to test portability. A closed
browser or removed temporary add-on cannot run the schedule. Installed, signed-in
Firefox capture and restart/reload acceptance remain required before calling this
an operational unattended collector.

For a first controlled test, select one ticker, Income, Annual, leave Scheduled
off and run Update now. Check the saved ticker/period/currency and receipt before
adding Quarterly or more statements. Use an isolated native-host/database target
for pre-release acceptance, not an unverified production registration.

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
