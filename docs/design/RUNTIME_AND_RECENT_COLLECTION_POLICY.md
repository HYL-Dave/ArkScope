# Runtime And Recent Collection Policy

Date: 2026-09-14; runtime decision revised 2026-09-15 on
`codex/sec-research-integration` at `8ef04a60`. The user prioritizes lower
maintenance cost and accepts retreating from the self-built SQLite plan.
Prebuilt runtime evaluation replaces preparation for self-built activation;
no replacement artifact has been admitted or installed. The shared fourteen-day
request target and C12 retirement remain complete. Entitlement reporting and
SA targeting remain open. The original policy superseded the pending choices in the
[September 14 closeout](../superpowers/evidence/2026-09-14-runtime-cleanup-closeout/README.md).
Historical test results and operational boundaries remain unchanged.

## SQLite: Upgradeable, Not Frozen

App-private runtime isolation does not require building SQLite ourselves.
The previous private shared-library/build/launcher deployment choice is
superseded, not queued for production activation. Normal installation, source
development and application acceptance must not require a SQLite source archive,
compiler or custom SQLite build recipe. Do not silently fall back to a source
build when a matching binary is unavailable.

Evaluate a maintained prebuilt CPython distribution and a separate project
virtual environment first, preserving ordinary `import sqlite3` and existing
executable selectors. This is a candidate approach, not an approved Python or
dependency replacement. Check the actual bundled SQLite, supported platform,
Python compatibility and existing dependency versions before selecting an
artifact. Keep the installed Python/numpy/SDK environment untouched during
disposable evaluation. Prefer the distribution manager's existing download,
checksum and environment mechanisms over another custom runtime manager.

The [uv distribution documentation](https://docs.astral.sh/uv/concepts/python-versions/#cpython-distributions)
confirms it downloads prebuilt CPython from `python-build-standalone`. This
establishes a no-local-build route, not a particular SQLite version or ArkScope
compatibility. A prebuilt SQLite DBAPI wheel is a secondary alternative requiring
explicit import/connection ownership across all writers. It is not a drop-in
upgrade of the standard library merely because a wheel was installed. The
[pysqlite3 maintainer](https://github.com/coleifer/pysqlite3) now directs new
development to `cysqlite`; do not select an older package name without checking
maintenance and Python/platform support. Both sources were checked on September 15.

The disposable `python-build-standalone` 20260901 evaluation now includes 89
version-matched dependency wheels, five archived UPSERT cases and eight database
behavior probes without compilation. A single unchanged backend run produced
**11,147 pass / 26 setup errors / 43 skips**: 26 old fixture cases assume
`_sqlite3.__file__`, 31 launch cases require the obsolete source archive, and
12 skips are existing manual checks. This is not green admission. Five additional
large-ID cases fail against the candidate's 32,766 parameter limit and pass on
the system-engine control. Their three product owners and proposed JSON-parameter
repair are recorded, pending confirmation. See the
[compatibility receipt](../superpowers/evidence/2026-09-15-prebuilt-runtime-compatibility/README.md).
That is the pre-change baseline, not the current source status. The user has
since approved A+B before hand testing: exact bound-ID sets and removal of the
unused self-build machinery. The SQL repair is implemented without an ID-count
cap; existing int64 rejection and text identity are preserved. Current launch
behavior is tested without a compiler or source archive. Replacement artifact
admission, TLS, selected-engine startup rejection and activation remain C,
after hand testing. See the [implementation plan](../superpowers/plans/2026-09-15-prebuilt-transition-cleanup.md).

The A+B/C15 source checkpoint `2aeed54a` now has paired full offline acceptance:
**11,245 passed / 12 unchanged manual skips** on each engine, with identical
case identities, interpreter-consistent PATH and unchanged source bytes.
Frontend tests, typecheck and build also pass. This is compatibility evidence,
not runtime admission or activation. Current-engine hand testing and C20's two
retained query records remain outstanding; no archive or DROP is authorized by
these results. See the [final cleanup receipt](../superpowers/evidence/2026-09-15-prebuilt-transition-cleanup/README.md).

Record one admitted artifact identity per environment, not one version for the
rest of pre-release development. Review newer stable distributions and upstream
fixes regularly. Validate a separate candidate environment before switching;
do not overwrite the active interpreter or resolve an unverified latest build
at startup. Python/numpy/SDK updates remain possible through scoped acceptance.

Admission requirements:

- Before application initialization can write, verify the engine actually
  loaded by the selected interpreter against the admitted artifact and required
  application behavior. Record source ID and compile options; do not require
  equality with the old distribution's entire flag list. Requirements such as
  parameter capacity and SQL grammar need actual consumer/test owners, not just
   inheritance from the deleted custom runtime verifier. Missing required behavior
  or an unexpected engine fails visibly, never silently falls back. Do not use
  the standalone SQLite CLI's identity as Python's identity.
- Desktop, the SA native host, supported operator/development/test entrypoints
  and normal writer children must resolve the intended engine. Preserve argv,
  cwd, signals and native-host stdout. Verify the real launch/child paths, not
  only a parent-process mock. Tests on the system engine are not new-runtime
  admission evidence.
- Prefer no loader override. Do not modify shell profiles, global service-manager
  environment, `ldconfig`, Electron's environment or isolated OAuth provider
  environments. A manager's optional global PATH/setup actions are not part of
  scoped candidate evaluation or application installation.
- Use the selected manager's package inventory and removal mechanism where
  possible. Any cleanup must still verify its scope and protect active/recovery
  environments. A manifest or lockfile cannot authorize arbitrary deletion of
  unrelated files, application databases or captures.
- Review relocation, compile profile, native dependency compatibility and
  descendant loading using the existing
  [admission preflight](../superpowers/evidence/2026-09-13-maintenance-closures/checks/sqlite-admission-preflight.md).
  The internal analysis library is not a current application writer. Its
  deferred replacement is distinguished below; do not widen its closed
  environment or reconnect it to make an engine-coverage claim.

Only the prebuilt-first direction is approved; a specific distribution, version
and installation layout remain unselected. Production selector/store inspection,
writer shutdown, backups, full integrity checks and activation still require the
separately agreed operational window. Engine replacement does not repair
already-damaged data. Rollback after writes is not equivalent to merely changing
an executable path; preserve the existing recovery acceptance boundary.

Windows/macOS runtime admission and the Python sandbox are deferred. Other
platforms do not inherit Linux validation or a same-version guarantee. Do not
make their admission a prerequisite for current Linux code cleanup.

### Superseded Self-Build Checkpoint And Removal Scope

The offline builder, manifest-bound executable selector and early process guards
are implemented at `292ef27f`. The final SQLite 3.53.4 package passed its exact
UPSERT/synthetic checks and the single complete backend: 11,238 passed with
twelve unchanged skips, 11,250 identities (+70/-0). The final process actually
loaded the package library; the separate unmanaged Python still loads system
3.37.2. Original Python/numpy/SDK installations and the dormant executor are
unchanged. Bootstrap review findings and actual SQL grammar validation are
included in the [preparation receipt](../superpowers/evidence/2026-09-14-private-sqlite-runtime/README.md).

This is historical evidence for the self-built package, not replacement-runtime
acceptance or an instruction to deploy it. Neither installed selector was
inspected or switched. `docs/design/SQLITE_RUNTIME_OPERATIONS.md` now describes
candidate selection and the replacement/removal boundary. SEC, completed cleanup,
the archived UPSERT reproducer and data-safety evidence are not rolled back.

The September 15 [acceptance/cleanup follow-up](../superpowers/evidence/2026-09-15-runtime-acceptance-cleanup/README.md)
rejects missing source archives in selected-runtime artifact acceptance.
Its single full backend passed 11,204 cases with twelve unchanged skips; all
31 artifact cases executed. That fixture rebuilds a disposable package: the
source requirement is a property of that test design, not SQLite execution or
acceptance of a prebuilt artifact. This gate and the four self-build test modules
are now removed with the unused builder, manifest verifier, custom launcher and
optional import/native-host hooks. No fallback builder or compatibility alias
is retained. The historical checks remain evidence of the old artifact only.

`tests/test_app_entrypoints.py` owns source-free current launch behavior: native
IO/cwd/exit/signals, configured-interpreter/descendant identity, real Desktop
spawn, worker help, dependency features and OAuth loader isolation. Native import
purity remains in `test_sa_native_host_telemetry.py`. The exact old package's
manifest/hash/loader defenses are retired contracts, not checks that a different
runtime has passed. Before C activation, prove that supported production startup
cannot silently use an unadmitted engine. No new guard or environment selector
is invented for B; current development and hand testing use the existing engine.

### Internal Analysis Library And Sandbox Ownership

The user clarified that retaining `src/tools/code_executor.py` was transitional:
replace and remove it when implementing the planned Python sandbox, not maintain
it as a permanent compatibility layer. SQLite deployment and sandbox development
remain separate workstreams. This clarification does not delete the library,
admit arbitrary Python execution, or change its environment policy now.

Source review at `84f52f60` found direct callers only in
`tests/test_code_executor.py` and `tests/test_tool_calling.py`; the sealed
[C12 census](../superpowers/evidence/2026-09-14-news-client-cleanup/checks/census.json.gz)
classifies it as `test_only`. The compressor references its historical result
shape without importing or executing the library. Registry, bridges, prompts and
subagents keep arbitrary Python unavailable. The future
[sandbox plan](../superpowers/plans/2026-09-03-packaged-python-analysis-sandbox.md)
explicitly forbids using this executor as its transport or fallback.

Therefore this dormant library does not block admission of the current supported
application writers. Do not add loader inheritance solely for its tests, show it
as an active Research engine in Settings, or claim that every importable Python
library/child has been upgraded. An upgraded-parent test run may still exercise
this library's system-engine child; record that scope rather than treating it as
new-runtime child evidence. Any future production caller would reopen runtime
and containment admission before registration or execution.

The sandbox workstream owns removal of the old execution implementation and its
superseded direct-library tests, with preservation of useful historical result
readers. This is an explicit replacement task, not forgotten cleanup. Existing
financial calculators and prebuilt runtime evaluation do not wait for it.

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

The three former seven-day defaults now consult
`src/news_collection_policy.py::INITIAL_NEWS_LOOKBACK`, a single fourteen-day
`timedelta`. The direct Massive/Finnhub adapters, normalized Massive/Finnhub
adapters and strict IBKR gateway read it at request construction. Their date and
timestamp parsing remain distinct; saved cursors are not clamped to this target.
The non-strict IBKR compatibility path still delegates a missing start date to
its source; this change does not give that fallback strict coverage semantics.
IBKR additionally has headline-tail/coverage limits; its documented runbook-only
boundary is not removed by a larger time window. Saturated seven-day results
cannot prove completion of a fourteen-day strict request.

`tests/test_news_bootstrap_policy.py` owns the five real adapter paths, shared
authority, saved/invalid cursors, per-source/ticker initialization, writer
deduplication and incomplete IBKR results. The bounded implementation plan is
`docs/superpowers/plans/2026-09-14-news-bootstrap-policy.md`. This delivers the
request target only: it does not discover account entitlements, report an
effective shorter REST window, persist a first-run interval for retries, or
guarantee fourteen days of returned data. Those parts of the policy remain open.

Fresh acceptance and exact limits are recorded in the
[shared-target closeout](../superpowers/evidence/2026-09-14-news-bootstrap-policy/README.md):
11,114 backend cases passed, 12 unchanged skips; the new 48 cases cover the
bounded request-target contract without removing any existing tests.

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

Old-CLI capability retirement remains approved. The September 15 decision
supersedes the self-built runtime approach; only prebuilt-first evaluation is
approved, not a particular replacement or production switch. Implementation
must provide scoped executable changes and RED-first owners for shared contracts.

1. C12 code/entrypoint cleanup is CLOSED at `c30c5bb8`: live clients relocated,
   old CLI/storage owners physically removed, and current CLI news status reads
   durable telemetry without claiming completeness. Fresh full backend:
   11,168 passed / 12 unchanged skips; see the
   [C12 receipt](../superpowers/evidence/2026-09-14-news-client-cleanup/README.md).
   The shared fourteen-day request target remains intact. Account-limit
   reporting and durable initial-interval retries are separate unfinished
   recent-source policy work, not implied by the CLI cleanup.
2. Self-built runtime activation is CANCELLED in favor of prebuilt evaluation.
   Its completed preparation at `292ef27f` remains historical, not the active
   deployment plan. First evaluate a binary against actual App requirements;
   then integrate it while removing the superseded runtime code/build-only tests
   and preserving startup/child safety owners. Arrange production cutover only
   after replacement acceptance. C15/C20 cleanup remains independent.
3. SA Open-first initialization: a separate scoped follow-up; preserve current
   collection while proving new targeting and explicit unfinished work.
4. Three additional C15 migration/recovery bundles are physically removed at
   `d208eeb7`; current write guards and recovery are preserved. Finish the
   remaining evidence-script/helper chains and C20 retained-data disposition
   before claiming all cleanup complete. Cross-platform and Python sandbox
   remain deferred.

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

At the original policy review, master was an ancestor with `0 / 157` unique
commits. No merge, push, runtime installation, production database/configuration
read or application restart is authorized merely by this policy. See the
implementation evidence for fresh acceptance; the prior backend/frontend
results remain historical. Runtime switching and the full recent-collection
policy are not complete merely because the shared request target is implemented.
