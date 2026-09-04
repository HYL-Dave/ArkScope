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
- `universe-manifest`: intentionally refuses until a separate production-read
  authorization is granted.

Each provider lane records whether it executed and an exact skip reason. A
negative oracle result is a successful experiment outcome: it rejects the
candidate authority for that axis rather than turning missing coverage into a
delisting or ticker-change fact.

## Evidence Boundary

Live evidence files are create-only. They contain normalized identifiers,
parsed fields, response digests, byte/request accounting, elapsed time, and the
closed outcome vocabulary. They never retain raw provider bodies, key-bearing
URLs, authorization headers, API keys, account records, or unrelated rows.

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
