# SA Watchlist Financial Collector

Approved scope: App watchlist acquisition, implemented together for Chrome and
Firefox, with one explicitly designated browser installation. Initial operator
acceptance uses Firefox. No automatic failover, production activation, paid
fallback or bulk live acceptance is authorized.

## Task 1: Local Authority

- Reuse the complete read-only active-universe owner, not a DAL constructor.
  Return supported targets, unsupported symbols, membership sources and warnings.
- Persist collector selection and financial acquisition admission next to the
  selected SA database, shared by native-host invocations and both browsers.
- Serialize admission; preserve cooldown and challenge pauses across ownership
  changes. Do not expire an in-flight reservation into a competing collector.
  Explicit interrupted-work recovery requires the operator to stop the old
  collector first. Local reads never claim ownership or install a database.
- Verify success against the saved observation. Reuse successful capture times
  across browser changes, without resetting them on reads.
- Test missing stores, concurrent admission, browser transfer, cooldown, invalid
  receipts and watchlist completeness before wiring browser acquisition.

## Task 2: Both Browser Builds

- Add manual/App watchlist target selection and preview. Unsupported symbols
  remain visible; do not invent provider aliases or drop former-pick membership.
- Resolve the App list again at acquisition; fail closed on unavailable sources.
- Add explicit collector selection and interrupted-work recovery controls.
- Process one watchlist scope per alarm, retaining a manually requested queue
  across background restarts. Stop controls cancel queued work. Scheduled work
  and manual queues share admission, pacing and cooldown; no catch-up bursts.
- Keep existing manual small-list behavior and existing article/news collectors
  separate. The shared governor applies to financial page navigation, not every
  browser request and not an advertised SA request quota.
- Test both builds, queued removal, disabled schedules, browser refusal,
  popup state, reload and failure paths without contacting SA.

## Task 3: Verification And Handoff

- Update DATA_ACQUISITION_AND_UPDATES.md and the workflow status.
- Run focused Python/JS contracts, built Firefox/Chromium popup checks and a
  fresh-context review. Record exactly which acceptance was offline.
- Leave the existing private Firefox acceptance installation untouched until
  the verified build is ready. Do not turn on all-watchlist acquisition.
- Chrome implementation parity is not signed-in Google Chrome acceptance.

## Decisions

- Unmapped symbols are surfaced, not guessed. App membership authority includes
  retained former picks; changing that membership is outside this batch.
- An orphaned reservation fails closed until explicit recovery. This costs an
  operator action after a crash, instead of risking concurrent acquisition.
- A conservative one-minute gap between financial page starts is an application
  pacing choice, not a claim about SA's unpublished limits.
- Persistent service, external MCP, analytics repairs and news retention remain
  separate required workstreams, not prerequisites or silently completed here.
