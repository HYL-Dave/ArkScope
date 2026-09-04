# Lifecycle Provider Authority Shadow Census

This packet is a detached measurement surface. It does not feed the lifecycle
scheduler, change profile membership, create an identity alias, or write an
application database.

## Modes

- `dry-run`: lists the frozen cases, spec digest, and maximum request budget.
  Massive, EODHD, and Nasdaq are all skipped with reason `dry_run`; no
  credential resolver or network transport is touched.
- `fixture-replay`: replays digest-bound synthetic normalized observations.
  Massive, EODHD, and Nasdaq are marked as synthetic fixture lanes; no
  credential, socket, or application database is accessed.
- `known-case-live`: remains gated by an exact spec digest, admitted commit,
  and `14 Massive + 2 EODHD + 2 Nasdaq` acknowledgement. A missing profile
  key is recorded as `credential_unavailable`, not replaced by an environment
  value. Massive request starts are spaced by at least 12.5 seconds, and a
  failed request retains only its normalized local failure code.
- `ticker-event-revalidation`: binds the sealed Attempt 2 `LC`/`HAPN`
  Composite FIGI observation and permits exactly one new Massive Ticker Events
  request. EODHD and Nasdaq have zero budget. This mode exists only to validate
  the corrected official timeline parser; it cannot read a production DB or
  substitute a second provider request.
- `universe-manifest`: requires an exact spec/commit/network-zero
  acknowledgement plus explicit profile and Alpha Picks database paths. It
  uses the existing read-only active-universe projection, never resolves a
  credential or creates a transport, and emits a private `0700/0600` manifest
  plus a ticker-free public attestation. It does not authorize or execute the
  derived provider budget.

Each provider lane records whether it executed and an exact skip reason. A
negative oracle result is a successful experiment outcome: it rejects the
candidate authority for that axis rather than turning missing coverage into a
delisting or ticker-change fact.

## Evidence Boundary

Live evidence files are create-only. They contain normalized identifiers,
parsed fields, response digests, byte/request accounting, elapsed time, and the
closed outcome vocabulary. They never retain raw provider bodies, key-bearing
URLs, authorization headers, API keys, account records, or unrelated rows.

The full-universe manifest is stricter because it reflects private watchlist,
portfolio, and Alpha Picks membership. Its exact rows stay under the
git-ignored profile data boundary. Only aggregate counts and cryptographic
digests enter this tracked evidence directory; per-ticker source provenance is
never published.

Offline admission:

```bash
pytest -q tests/test_security_lifecycle_provider_census.py \
  tests/test_lifecycle_provider_census_transport.py \
  tests/test_lifecycle_provider_census_runner.py \
  tests/test_data_provider_config.py
python docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/run_census.py \
  --mode fixture-replay
```

## Known-Case Attempt 1

The separately authorized run at `2026-09-04T12:11:11Z` was bound to commit
`a4c0605957e5885e6d347fddf19864359cd17894` and the spec digest recorded in
`census-summary.json`. It made 14 HTTP attempts: 12 Massive, zero EODHD, and
two Nasdaq Trader requests.

- Massive exact listing rows confirmed `ARCH` and `LTHM` inactive. `LC` was
  inactive and `HAPN` active under the same Composite FIGI. OpenFIGI's
  allocation rules make that strong same-instrument continuity evidence, but
  the required ticker-event request did not complete. The attempt therefore
  validated a known candidate pair without validating how ArkScope would
  discover an unknown replacement ticker; no end-to-end ticker-change
  authority was established.
- `TA`, `AAPL`, and `SMCI` remained ambiguous because their listing requests
  did not complete. The aggregate oracle therefore produced two `confirmed`
  and four `ambiguous` results.
- The EODHD profile field was absent. The lane recorded
  `credential_unavailable` and made zero EODHD requests; it did not consult an
  environment variable.
- Nasdaq Trader completed both directory requests and observed `AAPL`, `HAPN`,
  and `SMCI` in the Nasdaq file and `CNR` in the other-listed file.

Neither active Massive control (`AAPL` or `SMCI`) completed. Although the
Nasdaq directory observed both, this attempt did not demonstrate that the
candidate Massive listing-state method distinguishes an independently active
security from an inactive one. `ARCH` and `LTHM` are useful observations, not
admission of terminal authority. The whole first attempt is therefore
insufficient rather than partially passing an authority axis.

The first five Massive requests completed and every later attempted Massive
request returned a 4xx status family. The packet intentionally retained only
the status family, so it does not prove the exact HTTP status. This sequence is
consistent with the official Stocks Basic limit of five API calls per minute:
<https://massive.com/pricing?product=stocks>. It must not be interpreted as
Ticker Events coverage or entitlement evidence. The subsequent runner revision
adds pre-request pacing and retains the normalized local failure code without
retaining response text. It does not retry any failed request.

The seal verifies, the packet contains no raw response body, and a comparison
against the one admitted profile credential found zero credential-value
matches. This attempt changes no application state and does not admit any axis
for full-universe execution.

## Known-Case Attempt 2

The separately authorized paced run at `2026-09-04T14:19:17Z` was bound to
commit `af80fe6008900c6e210dc79e80a6b2f7efaf2968`, the frozen spec digest, and
the exact `14 Massive + 2 EODHD + 2 Nasdaq` envelope. It made all 18 requests,
exactly once each. No redirect, retry, fallback, environment credential, or
application write occurred.

- Massive returned complete exact listing rows for all required state cases
  except `ALTM`, which was absent from that exact lookup. It observed `LC`,
  `ARCH`, `LTHM`, and `TA` inactive; `HAPN`, `CNR`, `AAPL`, and canonical
  `SMCI` active. `LC` and `HAPN` retained the same non-null Composite FIGI,
  while `ARCH` and `CNR` retained different FIGIs.
- EODHD completed both bounded lists and partitioned every requested symbol:
  `AAPL`, `CNR`, `HAPN`, and `SMCI` active; `ALTM`, `ARCH`, `LC`, `LTHM`, and
  `TA` delisted. Nasdaq Trader again observed the four currently listed
  controls across its two files.
- These positive and negative controls pass the known-case listing-state gate.
  This admits only a separately authorized full-universe listing-state census;
  it does not change runtime authority or authorize a terminal transition.
- The `LC` and `AAPL` Ticker Events requests returned successful Massive
  envelopes but were rejected by ArkScope as `massive_event_ticker_invalid`.
  Official Massive responses place each ticker on its timeline event and do
  not expose the `results.ticker` field required by the original adapter. The
  other three event requests returned the normalized `massive_not_found`
  result. Therefore the ticker-change gate remains unadmitted.

The provider response bodies were not retained, so the parser repair is owned
by the official response-shape regression rather than reconstructed provider
content. A later `LC` event revalidation is a new explicitly budgeted request,
not a retry hidden inside this attempt. The `attempt-2/SHA256SUMS` seal verifies,
and comparison against both admitted profile credential values found zero
plaintext matches in the normalized packet.

## Ticker-Event Revalidation

The separately authorized revalidation at `2026-09-04T14:31:35Z` was bound to
commit `6097b3c59516b0482405d1fa713163eb3010d242`, the exact parser-repair spec,
the sealed Attempt 2 summary, and a one-request Massive-only budget. It made
exactly one request, received one 2xx response, and parsed exact
`LC -> HAPN` on `2026-06-22` from the shared Composite FIGI timeline. EODHD and
Nasdaq made zero requests; no retry, fallback, raw body, credential value, or
application write occurred.

The immutable packet under `attempt-2-event-revalidation/` says
`contradicted` because its frozen expected date was incorrectly set to
`2026-06-27`. Happen's filed Form 8-K states that the symbol change became
effective at market open on `2026-06-22` and that the common stock's CUSIP
remained unchanged. The provider result is therefore correct and the old
oracle is not. A RED-first regression reproduced this false contradiction
before the runner oracle was corrected. The original packet and seal are
retained byte-for-byte; no second provider request was made.

Primary-source check:
<https://www.sec.gov/Archives/edgar/data/1409970/000140997026000140/lc-20260622.htm>.

Post-correction verification is `256` focused tests and `5709 passed / 12
skipped` for the complete backend suite. The RED owner first failed with the
old `2026-06-27` oracle and `contradicted` outcome before the implementation
was corrected.

## Full-Universe Manifest

The separately authorized read-only snapshot at `2026-09-04T15:10:49Z` was
bound to implementation commit `f931cd1b40ac8c6a3a6048571a61fdd32cbc1ff8`
and spec digest
`e3f751b7d5780836d79a27097c95bf793a55dc5afedc4567fc7ed1a91c0d3faf`.
It opened the explicit profile and Alpha Picks databases through the existing
SQLite `mode=ro` and `query_only=ON` projection. Both database file digests
were unchanged before and after the run. No credential resolver, provider
transport, HTTP request, retry, fallback, or application write occurred.

The fresh projection contains 186 sorted unique symbols. Aggregate source
membership counts are 148 manual-list, 10 open-portfolio, 45 current Alpha
Picks, 56 former Alpha Picks, and zero legacy-seed memberships. A symbol may
belong to more than one source, so these counts intentionally do not sum to
186. There were no source warnings and exactly one reviewed provider spelling
override.

The exact active-pass envelope derived from the sealed manifest is 186
Massive exact-listing requests, two EODHD list requests, and two Nasdaq Trader
directory requests: 190 HTTP attempts in total, with zero retry or fallback.
That envelope is recorded as `not_authorized`; this manifest run executed none
of it. Inactive/event requests are not included and remain a later,
missing-subset authorization boundary.

The exact ticker/source rows and their seal remain in the git-ignored profile
data boundary with directory/file modes `0700/0600`. The tracked
`universe-manifest/` packet contains only aggregate values and cryptographic
digests, and its seal verifies. Verification after adding the manifest mode
was 266 focused tests and `5720 passed / 12 skipped` for the complete backend
suite.
