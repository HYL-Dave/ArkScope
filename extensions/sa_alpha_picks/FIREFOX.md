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
5. Run `Quick Refresh` from the extension popup.

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

Temporary Firefox add-ons are removed when Firefox restarts. For daily use,
either keep the collector Firefox session open or package/sign this as an
unlisted Firefox add-on later.
