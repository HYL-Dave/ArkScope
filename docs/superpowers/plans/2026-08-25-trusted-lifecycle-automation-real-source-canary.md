# Trusted Lifecycle Automation Real-Source Canary Plan

**User authorization:** one bounded run covering four exact SEC primary
documents and one read-only IBKR contract-shape session. This authorization
does not include another provider run, a production-data read beyond the four
app-managed provider-config fields, any database write/migration, merge, push,
or app cutover.

## Exact Scope

- Product/test authority remains
  `7cb479a8058793dc29cbb75bb4ab98b9d6a6f231`; later commits are docs/evidence
  only.
- The preparation check already read exactly `sec_edgar.user_agent` and
  `ibkr.host/port/client_id` once from the explicit live profile. The executor
  may read those same four rows once more through SQLite `mode=ro` and
  `query_only=ON` because the values were deliberately not retained. Total
  production config reads for this canary are therefore two queries and eight
  rows. Do not output or persist their values.
- Fetch exactly these four public SEC primary documents through `SecTransport`
  and the App's shared governor:
  - HAPN benchmark: accession `0001409970-26-000087`;
  - QBTS benchmark: accession `0001907982-26-000099`;
  - CCL benchmark: accession `0001104659-26-057200`;
  - BLBD benchmark: accession `0001589526-26-000044`.
- Do not call live SEC submissions metadata. Build a one-row local submissions
  shape from the reviewed 37-row fixture so the only SEC network calls are the
  four authorized document URLs.
- Use one shared SEC budget: four attempts, four documents, 1 MiB per document,
  4 MiB total. A rate-limit retry consumes the same attempt budget and can make
  the run partial; it does not expand authorization.
- Persist each exact public response body, its SHA-256, bounded excerpts,
  extracted facts, typed blockers, and diagnostics. Never persist request
  headers or the SEC identity value.
- Run one IBKR session through the production `_LifecycleIbkrGateway`, shared
  cross-process lock, derived lifecycle client ID, and `readonly=True`. Query at
  most the reviewed first-discovery candidates `LC` and `HAPN`; make no market,
  account, order, or historical-data request.
- Persist only canonical contract evidence, typed status/blockers, request
  count, and extracted market facts. Do not persist configured host, port,
  client ID, account values, or credentials.

## Stop Rules

- A URL, accession, CIK, document count, budget, product byte, config-field
  set, or output-path mismatch stops before provider traffic.
- A dirty worktree, a profile path other than the main checkout's live
  `data/profile_state.db`, or a lock path other than its shared `data/locks`
  stops before provider traffic.
- A provider failure is evidence, not permission to retry. A second live run
  requires new authorization.
- Parser mismatches are repaired offline against the captured source bytes with
  RED-first tests. They do not authorize a broader fetch.
- Formal migration, merge, push, and cutover remain separate hard stops.
