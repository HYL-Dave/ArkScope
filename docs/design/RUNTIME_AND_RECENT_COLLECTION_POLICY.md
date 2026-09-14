# Runtime And Recent Collection Policy

Date: 2026-09-14. Source review: `d90c13fa`,
`codex/sec-research-integration`. Status: user decisions accepted; deployment,
collector retirement and the revised initialization behavior are not implemented
by this document. This supersedes the two pending choices in the
[September 14 closeout](../superpowers/evidence/2026-09-14-runtime-cleanup-closeout/README.md).
Its historical test results and operational boundaries remain unchanged.

## SQLite: Upgradeable, Not Frozen

Adopt the Linux-only app-private SQLite library plus executable launcher under
`~/.local/share/arkscope/runtimes/`. The current source tree, Python and numpy are
not bundled or upgraded as a side effect. Ordinary source edits do not require
rebuilding the SQLite package. This is not the packaged Python sandbox project.

Pin one admitted package identity per process generation, not one version for
the rest of pre-release development. Prefer reviewing current stable upstream
fixes rather than indefinitely retaining the first admitted version. Prepare a
new immutable version directory, verify it, then deliberately switch generations.
Do not overwrite an active library or download/select an unverified latest build
at startup. A subsequent Python/numpy/SDK upgrade remains possible through its
own scoped admission; this SQLite change does not freeze those dependencies.

Admission requirements:

- Before application initialization can write, verify the engine actually
  loaded by the selected interpreter. Version alone is insufficient: compare
  source ID and required compile features/limits with the admitted package,
  alongside artifact hashes. A mismatch fails visibly, never silently falls
  back. Do not use the standalone SQLite CLI's identity as Python's identity.
- Desktop, the SA native host, supported operator/development/test entrypoints
  and normal writer children must resolve the intended engine. Preserve argv,
  cwd, signals and native-host stdout. Verify the real launch/child paths, not
  only a parent-process mock. Tests on the system engine are not new-runtime
  admission evidence.
- Set loader variables only for the selected Python process and intended
  children. Do not modify shell profiles, global service-manager environment,
  `ldconfig`, Electron's environment or isolated OAuth provider environments.
  A future service may invoke the approved launcher; that is different from
  installing a global loader override.
- A manifest enumerates owned package objects but cannot by itself authorize
  arbitrary deletion. Validate paths beneath the managed runtime root, ownership
  and actual object shape, and exclude active generations and retained recovery
  packages. Never delete unrelated files, application databases or captures.
- Review relocation, compile profile, native dependency compatibility and
  descendant loading using the existing
  [admission preflight](../superpowers/evidence/2026-09-13-maintenance-closures/checks/sqlite-admission-preflight.md).
  The sanitized internal analysis child remains an explicit exception to solve
  or restrict before claiming complete writer coverage; do not widen its closed
  environment implicitly.

The source-only deployment decision is approved. Production selector/store
inspection, writer shutdown, backups, full integrity checks and actual activation
still require the separately agreed operational window. Engine replacement does
not repair already-damaged data. Rollback after writes is not equivalent to merely
changing a launcher path; preserve the existing recovery acceptance boundary.

Windows/macOS runtime admission and the Python sandbox are deferred. Other
platforms do not inherit Linux validation or a same-version guarantee. Do not
make their admission a prerequisite for current Linux code cleanup.

## News: A Recent Target Subject To Real Access

Retire the old Massive/Finnhub file-writing CLIs, including arbitrary-date,
full-history, old checkpoint/resume/estimate and raw-file status operations.
Keep the current provider fetch/parse code, active-universe scoping, incrementally
collected local news, identities, projection, locks and telemetry. Keep already
collected files and databases; code retirement is not permission to purge them.

The desired first-fetch target is the recent **14 calendar days**, independently
per source and ticker, including newly added tickers. Around one month can be a
useful larger recent window, not a required minimum or a reason to collect an
entire available archive. An entitlement exposing years of history does not
automatically increase this product target. Expensive historical news is not a
prerequisite for the app's longer-term financial/SEC/macro research features.

Separate three facts in the implementation and its status:

1. The requested recent target.
2. The effective request window allowed by known endpoint/account constraints.
3. The observed result and unresolved coverage, including pagination, item caps,
   access errors, interruption and request-budget exhaustion.

If reliable account/endpoint evidence limits history to seven days, request at
most seven and expose the shorter scope instead of claiming fourteen complete
days. Do not hardcode that ceiling for every free account or every provider.
An unknown entitlement is unknown, not seven days, unlimited access or an
automatic authorization failure. Use explicit provider contract/response evidence
and any subsequently verified account capability; do not infer a history ceiling
from empty results or the oldest article returned. No payment, plan upgrade,
credential switch or repeated probing is implied by this policy.

Do not silently move a persisted collection frontier forward to conceal a gap.
Retries must retain the intended unfinished scope; any bounded catch-up that
abandons older unobserved coverage must report it. Increasing a page/request
budget does not prove that the provider exposes more historical articles.

### Source Facts Checked Here

The existing first-fetch defaults are still seven days in all three owners:
`src/news_providers.py`, `src/news_normalized/provider_adapters.py` and
`src/news_normalized/ibkr_runtime.py`. Thus changing a single constant would not
produce consistent behavior. IBKR additionally has headline-tail/coverage limits;
its documented runbook-only boundary is not removed by a larger time window.

[Massive's News endpoint](https://massive.com/docs/rest/stocks/news) currently
documents date filters, continuation via `next_url`, and history access exceeding
the fourteen-day target even for its Basic plan. That public contract supports
the request target; it is not a measurement of this user's subscription or data.

[Finnhub's Company News documentation](https://finnhub.io/docs/api/company-news)
defines `symbol`, `from` and `to`, but the endpoint entry does not state a
seven-day free-tier history ceiling. The browser-text tool returned no body;
the embedded documentation JSON was separately parsed from the public HTML
without executing its scripts. The retrieved HTML SHA-256 was
`6f358aca7a65966c4344af7d3a0d23d9b1c885acecca82f9a9c8dcd74b0d87f0`.
The official
[OpenAPI definition](https://github.com/Finnhub-Stock-API/finnhub-go/blob/master/api/openapi.yaml)
also exposes date parameters without that ceiling. Neither source proves this
account's actual history access. Old collector comments asserting seven days
are not sufficient provider authority and must not be copied into the new owner
as a verified capability. No credential-bearing API request was made here.

## Alpha Picks: Open Positions First

There is no fixed one-year initialization contract. Synchronize all currently
Open recommendations regardless of their original pick date. Try to complete
their relevant recommendation information and prioritize recent analysis/updates.
Older material has lower routine priority, not an automatic expiry/deletion rule;
an older original recommendation can still matter for a position that remains
Open. Neither six months nor one year is a new hard cutoff.

Do not spend routine initialization work backfilling Closed positions' old
articles or comments. Preserve already captured Closed history. Continue any
lightweight status observation needed to detect Open-to-Closed changes and keep
the active list correct; this is distinct from retrieving Closed historical
content. Preserve existing manual reading of retained material and current
tracking/tombstone authority.

SA market news remains news, not Alpha Picks recommendation history. It must not
inherit a one-year target or a guarantee inferred from REST-provider capabilities.

Current empty-article-store `quick -> full` promotion in
`extensions/sa_alpha_picks/background.js` uses larger scroll budgets, with `full`
and `backfill` each allowing 200 rounds. It is not a date or exhaustion proof.
The current DAL selects missing content from the scanned article IDs, not a
verified Open-only or time-bounded set. This remains a separate implementation
follow-up, not an already satisfied contract or justification to retain the old
Massive/Finnhub CLI.

Acceptance distinguishes membership from best-effort content:

- Current Open membership must be synchronized from the authoritative list with
  failed/partial observations explicit; age cannot exclude a member.
- Article retrieval is prioritized and bounded. Record which targeted Open
  recommendation information remains missing and why. Reaching a scroll/time/
  request cap is a stop reason, not proof that the source list is exhausted.
- The date of the oldest stored article alone cannot prove interval coverage or
  completeness. Do not replace a scroll-count assertion with that equally weak
  assertion. Only independently evidenced source exhaustion or the defined
  target's completed work can support such a claim.

## Work Order And Completion Accounting

The runtime location/approach and old-CLI capability retirement are no longer
pending user choices. Engineering must still provide reviewed executable plans
and RED-first owners before changing these shared contracts.

1. C12: move live clients, remove old CLI/storage owners, fix current CLI status
   truth, and implement/verify the recent-source policy without reviving global
   file cursors or copying unverified subscription restrictions.
2. Linux runtime: prepare and admit the final package and entrypoint checks;
   arrange the production cutover separately. This does not block independent
   C12/C15/C20 source cleanup.
3. SA Open-first initialization: a separate scoped follow-up; preserve current
   collection while proving new targeting and explicit unfinished work.
4. Finish remaining C15/C20 retained-data/ownership decisions before claiming all
   cleanup complete. Cross-platform and Python sandbox remain deferred.

Suggested behavioral owners for the subsequent plans: existing
`tests/test_news_providers.py`, `tests/test_news_normalized_provider_adapters.py`,
`tests/test_news_normalized_ibkr_adapter.py`, `tests/test_news_normalized_writer.py`,
`tests/test_news_direct.py`, `tests/test_data_scheduler.py`,
`tests/test_daily_update_wrapper.py`, `tests/test_sa_tools.py`,
`tests/test_sa_extension_reconciliation_flow.py` and the client/CLI collateral in
the [C12 inventory](../superpowers/evidence/2026-09-14-runtime-cleanup-closeout/checks/c12-inventory.md).
These are test-owner locations, not newly executed tests or an implementation
plan. Include empty-store/new-ticker behavior, both REST writer routes, known
short entitlements, unknown capability, empty responses, pagination/caps,
interrupted work, de-duplication, Open members older than a year and retained data.

At review time, master remains an ancestor with `0 / 157` unique commits. No
divergent master commits were found; no merge, push, runtime installation,
production database/configuration read or application restart occurred. The
previous backend/frontend acceptance remains historical; this is a policy-only
change and does not claim that fourteen-day initialization or runtime switching
has been delivered.
