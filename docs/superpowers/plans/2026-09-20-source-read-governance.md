# Source Read Governance And Usage Evidence

Status: implementation and focused RED-to-GREEN checks complete; frozen full
regression pending. Base: `ec574482`. No production writer/provider probe or
purchase is authorized by this plan.

## This Slice

1. **SEC defaults: implemented.** Service omission and all three typed adapter
   defaults are `stored`. Registry/bridge schemas inherit the signatures. Missing
   or old data stays a gap/local snapshot, not acquisition. `auto` and `refresh`
   remain explicit side-effecting modes; pinned references and source leases
   keep their existing invariants. Settings refresh and registered schedules
   are not changed. Old acquisition tests now request `auto` explicitly rather
   than being removed or allowed to stop before their cancellation/rate checks.
2. **Financial Datasets admission: implemented, no live activation.** Cached
   reads need no request grant. HTTP dispatch requires an explicitly enabled
   trusted policy with positive integer `daily_request_limit` and
   `requests_per_minute`. Missing/invalid values fail closed. Values are not
   guessed from key presence or marketing plans. A per-installation/key SQLite
   governor commits an attempt before HTTP, atomically across threads/processes.
   UTC-day and rolling-minute limits are separate. Errors/uncertain dispatches
   consume the reservation; no implicit retry/redirect/second paid source.
3. **Actual research usage: complete.** The four research tables' current
   question/tool evidence matches the previous read-only private snapshot.
   Two [tables](../../data/2026-09-20-research-usage.md) distinguish topic judgment,
   recorded starts, name-only headers, saved-message copies, outcome flags,
   unknown outcomes and missing auth provenance. No research is deleted.
4. **Named abandoned worktree: removed.** `lifecycle-final-audit` HEAD `a6f2fe4f`
   is an ancestor of master. Its 868 staged deletions and residual ~11 MB tree
   were not treated as a clean checkout. The remaining files were copied and
   byte-compared under the private existing retained-data root before removing
   its registration/directory. Local `lsof` found no handles, with existing
   Docker namespace visibility warnings. Other historical trees are untouched.

## Configuration And Cost Meaning

The existing operator file owns this fallback's policy:
`config/user_profile.yaml` -> `data_preferences.paid_sources.financial_datasets`.
The two new values are deliberately `null`. Enabled + unknown limits means
cache-only, not unlimited. Resolve the actual account allowance and authorized
daily **request** budget before populating them and restarting consumers that
cache configuration. They are not model-controlled tool parameters.

The old generic `cost_control.daily_budget_usd: 1.0` is not an implemented dollar
cap. This slice does not convert dollars to requests with an invented price.
Per-request credits/multipliers, fixed subscriptions and auto-reload remain
account evidence to obtain, not assumptions. A cold legacy fallback attempts
at most the existing three statement endpoints and stops fan-out on the first
refusal/failure. Partial acquired statements survive with `acquisition_gaps`;
denied acquisition is not represented as proved absence of financial data.

The governor stores hashed key identity, UTC-day counters, recent request-start
times and provider cooldown, not the API key, ticker, response or research text.
Location: `${ARKSCOPE_LOCK_DIR}/financial_datasets_requests.db`, otherwise the
installation's `data/locks/financial_datasets_requests.db`. This is **durable
budget evidence, not a disposable lock file**. Do not clear it to retry. All
consumers in an installation must use the same directory. Different hosts,
roots, keys sharing one billing account or direct external scripts are not
covered by this ledger. Stop/restart consumers together for policy changes.

429 Retry-After is retained without an automatic retry. Time regression,
invalid/corrupt or partially missing storage and ledger contention refuse dispatch.
The governor initializes only a new empty ledger, never silently repairs a
previous ledger by recreating lost counters. Wrong endpoint response shapes are
rejected before caching, not treated as empty financial data. Local cache
promotion/file-fallback behavior is preserved; cache-only is not a claim that
cache reads never promote an existing entry into the market cache.

## Remaining Boundaries

- SEC `require_db_write` is still an audit hook, not the future interactive
  authorization engine. Explicit model-supplied `auto` is not user consent.
  The new default fixes surprise acquisition but does not authorize exposing
  those modes to external agents. External capability enforcement remains
  required before MCP/HTTP exposure; no external server is added here.
- Existing legacy SEC financial mapping is outside the three stored-by-default
  tools. Its automatic fetching/ratio/period defects are not silently declared
  fixed. Provider and tool retirement require accepted replacement evidence.
- Next product repairs: current quote freshness/basis; SA article/comment and
  holdings channel access; financial comparability and earnings release/session
  alignment. No-use is not a retirement rule. Unattended delivery/lifetime,
  retention/disposal, native SDK reuse, runtime upgrade and platform/sandbox
  work retain separate owners.

## Verification Owners

- `test_sec_research_stored_default.py`: missing/empty/old data across all four
  actual bridges and direct service; compare database/WAL and capture bytes;
  signatures/registry defaults; retained document reads. Existing operation,
  citation, cancellation, paging, SEC governor and schedule tests remain.
- `test_financial_datasets_governance.py`: key-alone RED; missing/invalid/disabled
  policy; cache hits; durable/key-scoped and cross-process limits; UTC rollover
  with rolling-window continuity; time regression; corrupt/partial ledger; no-refund
  timeout; 429 cooldown; redirects/access denial; all four output channels;
  typed refusal, invalid-response cache exclusion and partial-result preservation.
- `test_financial_datasets.py`: prior conversion/cache/backend-promotion/file
  fallback coverage retained with explicit offline policy. HTTP failure is now
  a typed failure rather than a success-shaped empty array. Its file cache is
  isolated per test instead of writing under the real repository data path.
- `test_research_usage_audit.py`: ambiguity, duplicate headers/copies, separate
  attempts, outcome uncertainty, annotation coverage, readonly/no-create access
  and dated inventory/count consistency. No live metadata is recomputed by tests.

Full regression runs alone in an isolated worktree after the code/test revision
is frozen. Frontend/build and desktop checks run outside that backend session.
Final evidence belongs in
`docs/superpowers/evidence/2026-09-20-source-read-governance/README.md`.
