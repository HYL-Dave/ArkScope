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
  value. Live execution is not authorized or performed by the offline commit.
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
