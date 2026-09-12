# Maintenance Batch Final Review

## Findings

### F1 - P3: R1 evidence overstates nonempty cache coverage

Location: [README.md:53](/tmp/arkscope-research-output-boundary/docs/superpowers/evidence/2026-09-13-maintenance-closures/README.md:53).

The README attributes preservation of nonempty "price/news/cache observations"
to the corrupt-current-table and path-probe failure controls. The former tests
seed news, prices and legacy sync, but no financial-cache rows; the latter uses
`_stats(news_rows=...)`, whose cache rows default to empty. Neither asserts a
nonempty cache result through the R1 failure boundary. See
[test_provider_health.py:504](/tmp/arkscope-research-output-boundary/tests/test_provider_health.py:504)
and [test_provider_health.py:583](/tmp/arkscope-research-output-boundary/tests/test_provider_health.py:583).

Separate retained controls do exercise populated cache/projection behavior,
including the ten-row assertion in
[test_stored_sec_projection.py:232](/tmp/arkscope-research-output-boundary/tests/test_stored_sec_projection.py:232).
Clarify that distinction before sealing the evidence. This is a documentation
correction, not evidence of a cache regression or a request for new implementation
or additional tests in this batch.

No P0/P1/P2 findings or other actionable product/test defects were identified.
The prior Task2 R1 is resolved in the reviewed source, not an outstanding finding.

## Verdicts

- **Product spec: PASS** for the bounded EIR-001 + C11 source contract.
- **Product/test quality: APPROVED.** Removals are narrow; useful assertions are
  transferred to current behavior rather than discarded with obsolete controls.
- **Evidence quality: correct F1. Recommendation/workflow: `revise`, documentation
  only.** No product revision or unrelated feature work is requested.
- **Final delivery remains controller-gated:** the already-running frozen full
  backend result and committed archive verification are pending, not failed checks
  or missing product features. This review does not claim full batch completion.

## Reviewed Identity

- Checkout: `/tmp/arkscope-research-output-boundary`.
- Base: `ef5f7b48435b56a17ab4be673f2b24cedee64372`.
- Head: `055c8dae157646f8cd6ee92a2948b61b17f64cd5`.
- Product anchor: `6cddc221c31ef6a1b21ac37e06273a2ef28b31ab`.
- Artifact: `.superpowers/sdd/2026-09-13-maintenance-closures/final-review.diff`.
- Artifact SHA-256: `6bc48ce9857ec0462b5319e3d82d72442503f6db23b7f4bb9d5d67b27bb94202`.

The 34-path Git inventory matches the package: 11 product files, 17 tests and
six documentation/evidence-tool files. No whole file is deleted; dependency
metadata, migrations and SQLite runtime implementations are untouched. Product-anchor
to head changes are documentation/evidence only. Read-only final identity checks
found the same HEAD and no tracked `src`, `tests` or frontend-source divergence
from it.

## Combined Boundary Review

- **EIR-001:** only the three desktop and two media rules for exact `.page-head`
  / `.page-head-actions` selectors are removed. The CSSOM tests have nonempty
  desktop/media inventories and render the real primitive. The focused unchanged
  [PageHeader.tsx:15](/tmp/arkscope-research-output-boundary/apps/arkscope-web/src/ui/PageHeader.tsx:15)
  and [primitives.css:55](/tmp/arkscope-research-output-boundary/apps/arkscope-web/src/ui/primitives.css:55)
  were inspected to challenge accidental deletion of a live header owner.
  `detailpage-head`, current header styles and shared eyebrow styles remain.
- **Writer policy:** obsolete key/env reads, helpers and resolver arguments are
  physically gone. Current normalized-setting precedence, malformed-value and
  malformed-requirement blockers, required-source rejection and `legacy_local`
  remain. The unchanged scheduler was inspected specifically for signature and
  dispatch collateral: [data_scheduler.py:994](/tmp/arkscope-research-output-boundary/src/service/data_scheduler.py:994),
  its rejection at line 1228 and writer branches at lines 1268/1327 still select
  the existing normalized/direct implementations; IBKR still requires normalized
  policy. No collector adapter, cursor or provider credential implementation is removed.
- **No fallback on telemetry failure:**
  [news_sync_status.py:133](/tmp/arkscope-research-output-boundary/src/news_sync_status.py:133)
  copies the input, replaces only news with current telemetry or `None`, and
  propagates SQLite errors. The unchanged status/coverage callers at
  [market_data.py:64](/tmp/arkscope-research-output-boundary/src/api/routes/market_data.py:64)
  and [data_coverage_tools.py:269](/tmp/arkscope-research-output-boundary/src/tools/data_coverage_tools.py:269)
  were checked for exception-driven fallback; neither catches the error to return
  old news. At [provider_health.py:240](/tmp/arkscope-research-output-boundary/src/service/provider_health.py:240),
  provisional news is cleared before both the path probe and current query.
  Thus readable legacy news plus broken current telemetry cannot survive as
  current success/counters; the note and non-news sync remain. Successful reads
  still expose current run/error/counter observations. Massive/Finnhub publication
  timestamps remain article signals, not ingest success. IBKR's separate combined
  price/news health calculation at line 342 is unchanged.
- **Retained data:** focused unchanged price-overlay, legacy-reader, health
  SA/cache collection and populated SEC-projection assertions were inspected
  because they share the changed sync response. Price authority and observations,
  SA refresh collection and financial-cache projection remain. No stored key,
  table, row, schema-disposal operation or startup cleanup is introduced.
- **API/auth/locale:** the one deleted PUT accounts for `223 -> 222`; tests assert
  the exact five surviving news routes. With authentication admitted, the old PUT
  receives the existing ticker route's 405, not a compatibility stub. The current
  setter retains its pre-write permission hook and writes only its current key.
  The unchanged [app.py:252](/tmp/arkscope-research-output-boundary/src/api/app.py:252)
  token guard and [permissions.py:35](/tmp/arkscope-research-output-boundary/src/api/permissions.py:35)
  were inspected to distinguish actual API admission from the audit-only permission
  hook: the monkeypatched 403 test proves ordering, not a new production permission
  engine. Exactly five leaves per locale are removed (`1019 -> 1014`, total
  `2962 -> 2957`); `write/read/authority` and macro fields remain. The unchanged
  [NewsStorageSection.tsx:41](/tmp/arkscope-research-output-boundary/apps/arkscope-web/src/settings/NewsStorageSection.tsx:41)
  was checked for use of removed status fields or labels; it consumes retained
  coverage and ingest fields. Focused production-code searches found no remaining
  deleted-symbol, locale-leaf or exact retired-class consumers.
- **Read-only URI fix:** the owned news reader uses resolved `as_uri()` plus
  `mode=ro`, retaining its missing-path guard and connection cleanup. The added
  populated/missing `?`/`#` cases assert actual telemetry, unchanged bytes and no
  unintended siblings. This is not certification of every other store's URI code.

## Evidence Limits And Remaining Gates

Read the maintenance plan, current C11 plan and current evidence README before
the supplied combined diff, then all three requested task reviews. Their verdicts
were checked against the combined source, not adopted as proof. The diff was read
in non-overlapping ranges; one truncated output affected duplicated pre-read
documentation/unchanged priority-map context, not an unseen product hunk.
No changed product file was reopened wholesale; follow-ups were focused on the
specific unchanged boundaries named above.

Historical execution results remain attributed, not reviewer executions: README
reports worker 332P and controller 76P as separate checks, fixed-source frontend
1779P plus typecheck/build, and ten isolated real-primitive browser comparisons.
It distinguishes assertion RED/inverses from setup failures and documents the
300 -> 329 -> 332 scoped-node progression. No raw execution receipts were reopened;
logs cannot establish the missing cache assertion in F1. Runner isolation,
RED/GREEN chronology, screenshot pixels, skip-ID equivalence, retained-rule hashes
and census reconciliation were not independently rerun or hash-verified here.
The census's 175 raw new uncertainty IDs and `review_required` remain unresolved
scanner evidence, not proof of new defects or permission for further deletion.

The archive verifier was read as source, not executed; no manifest membership or
committed-receipt hashes are attested. The controller must obtain the actual
frozen full-backend outcome, reconcile its exact counts/skips, and complete archive
sealing/verification before final delivery. No additional runtime check is requested
on the present source evidence, and none should be started by this review while
the single controller suite is active.

SQLite remains **SOURCE-ONLY PREFLIGHT** in this batch; historical candidate evidence
is not packaging, installation, activation or actual-store integrity evidence.
SEC recovery still awaits durable Research references plus operation leases
(release Tasks 3/5); citations alone do not activate cleanup/reset. C12, C15/C20,
stored-data disposition, broader CSS/i18n/SQL queues and deferred C21 remain outside
these closures. No implementation request is made for those remaining workstreams.

Risk assessment: impact if wrong **high** because writer policy and shared API
telemetry are involved; residual likelihood **moderate**, protection **partial**
and confidence **moderate** pending controller integration evidence. Recovery is
an **easy source revert**, without migration or deleted-data recovery, but would
restore the obsolete-switch/telemetry and URI defects. Auto-merge is not endorsed.

No tests, product imports, browsers, providers, DB/private-config reads, runtime
mutations, agents or Git writes were performed. The only write was this report
via `apply_patch`; the active backend runner was not interacted with.

## F1 Follow-Up Disposition

**F1: RESOLVED. Revised evidence wording: APPROVED.**

Narrowly reviewed the current [README.md:52](/tmp/arkscope-research-output-boundary/docs/superpowers/evidence/2026-09-13-maintenance-closures/README.md:52)
paragraph. It now distinguishes nonempty price/news observations in the corrupt
current-table fixtures from nonempty news observations in the path-probe control,
explicitly states that neither seeds nonempty financial-cache rows, and attributes
the retained ten-row cache/projection assertion to its separate test. This matches
the source evidence established in the original review and removes the overclaim.

The earlier F1-only documentation `revise` verdict is superseded; no further F1
change is requested. Product spec/quality approval is unchanged. The actual full
backend outcome and archive sealing/verification remain controller-owned final
gates; this disposition does not claim integration completion or activation.

This follow-up read only the revised README excerpt and this report's append
context. No new source sweep, product imports, tests, runtime interaction or Git
writes occurred. Only this report was appended via `apply_patch`; no new execution
evidence or source-freeze verification is claimed.
