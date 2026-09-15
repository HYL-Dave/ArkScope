# SEC Form Selector And Browser Hand-Off

Base: `2e71a99c`. The user accepted automatic local filtering, requested a
filing-type dropdown and reported that SEC original did nothing. They approved
a multi-select whose options come from the issuer's complete locally observed
catalog, not just the current result page. This is a bounded Settings change,
not a runtime switch, merge, new acquisition policy or sandbox implementation.

## Browser Diagnosis

The previous check verified anchor attributes, not the operating-system browser
handoff. The missing live check allowed a hand-test environment defect through.

The isolated Desktop uses a private HOME/XDG configuration and a read-only host
filesystem. Its HTTPS handler resolved to `firefox.desktop`, while the normal
desktop resolves to `google-chrome.desktop`. Under the same isolation, tracing
the URL opener established this sequence:

- `xdg-open` calls `gio open`, which starts the Firefox launcher.
- `gio` and `xdg-open` exit successfully, before the launched browser fails.
- The launcher hands off to Snap Firefox. It cannot update its host-side user
  directory on the read-only filesystem and fails creating a transient scope
  with a PID from the isolated namespace (exit 46).

This is why adding a catch to the Electron promise would not fix the reported
case: the operating-system handoff reported success. The product's navigation
code has not changed. No host filesystem, DB or session-bus access was relaxed.

The hand-test profile now has a private desktop entry for installed Chrome,
using a separate browser profile, no first-run/default-browser prompts and no
sync. Only the private MIME configuration was changed. The normal desktop
handler remains `google-chrome.desktop`.

An actual click in the running Electron SEC table opened
`https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/aapl-20260627.htm`
in that separate Chrome window. CDP confirmed the exact URL, document title
`aapl-20260627` and 86,456 body-text characters. A settled screenshot showed the
rendered filing; the Electron renderer retained its local application page.
The first immediate screenshot was blank before painting settled, so it was
not accepted as visual proof. This test did make a public browser request; it
did not invoke SEC acquisition, a model, or a production database.

This repair covers the Linux isolated hand-test fixture. It does not claim
Windows/macOS browser validation or detection of every failure occurring after
an operating-system opener reports success.

## Selector Contract

- One read-only local options request for the selected issuer. No source
  fetch, profile credentials, schema installation or DB writes on that GET.
- Exact form strings, including spaces and amendments, deduplicated across
  receipt-bound catalog sources, independent of list pagination and filters.
- Unknown, partial and empty coverage stay distinct. A limited or incomplete
  local observation must not be advertised as exhaustive SEC coverage.
- Selecting multiple values filters automatically; All clears the selection.
  Selection changes reset the result cursor chain. Stale responses must not
  restore options or records for another issuer.

The official [SEC forms index](https://www.sec.gov/submit-filings/forms-index)
and [submission-type index](https://www.sec.gov/file/edgarfilermmanual-vol2-c3)
define many form/submission codes. The UI does not maintain a small hardcoded
subset or require users to type those codes from memory.

## Verification

Browser diagnosis above was completed on the running `f859e0d6` product before
selector changes. The new read-only route increases the exact route inventory
from 222 to 223; both count owners and the named route assertions are updated.
The model-facing tool set and the three SEC tool adapters are unchanged.

The worker's initial backend RED was 12 failures / 6 passes. Its first GREEN
attempt found an incorrect test assertion (17 passes / 1 failure); correcting
that assertion yielded 18 passes. Direct follow-up tests cover 130 distinct
options without a 100-item cap, latest successful-but-unbound receipts, and
row/byte/source/envelope limits. Worker backend output was session-only, not a
retained report. The parent subsequently ran the complete SEC/API selection
once under read-only, network-disabled isolation: **2,230 passed**, no failures
or skips (`checks/backend-current.xml.gz`). This is not the full backend suite.

Frontend RED demonstrated the missing dropdown/API (39 failures / 50 passes),
then separate RED cases caught growing trigger height and refresh-completion
focus loss. The final focused selection passes 129 tests in five files. The
trigger is fixed at 32px, with an ellipsis and full-value tooltip. If replacing
options removes the focused item, focus returns to All; surviving menu focus
is preserved. Independent static review closed that focus finding and found
no remaining issue in the bounded frontend/backend scope. The eight existing
Desktop navigation/sidecar-config tests also pass.

The parent full frontend run passes **1,846 tests in 124 files**, no failures or
skips (`checks/frontend.json.gz`). It runs after the worker's targeted process
has exited, with file parallelism disabled and private Vite caches. Typecheck
and production build also pass; the existing >500 kB bundle warning remains.
No full backend, replacement-runtime or cross-platform claim is made here.

Final actual-browser selector verification is pending the isolated relaunch.
