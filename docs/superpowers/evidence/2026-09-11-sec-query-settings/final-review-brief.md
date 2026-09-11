# Whole-Batch Review: Stored SEC Queries And Settings

Review this batch from 483e8f3e through the head stated in final-diff.txt, not
the entire unmerged historical branch. Prior batches have their separate sealed
reviews. The binding scope is docs/superpowers/plans/2026-09-11-sec-query-settings.md;
the broader SEC spec remains the first-release authority but is deliberately not
claimed complete here. Read progress.md for all decisions and task review loops.

Main integration risks:

- Receipt source bindings vs retained snapshots: failed refresh cannot borrow old
  success. Ordinary cursors pin exact receipt/filter/binding identity. Immutable
  fact IDs use a different shared-codec kind and snapshot watermark, independent
  of current receipt status. Shared validation must run before storage checks.
- Genuine no-observation vs empty vs partial results; aggregate row/source/encoded
  byte limits cannot infer absent data. Exact numbers stay strings through SQL,
  query, HTTP and rendering. Filing availability is not reporting-period end.
- Quota is exact positive integer and only profile-setting mutation; existing
  objects remain readable below budget. Null capacity is unknown, not zero.
- HTTP permission precedes mutations; stored GETs do not acquire/install/recover.
  Four new routes coexist with status/refresh, and the actual Settings consumers
  use all six. New malformed-domain checks must not duplicate query logic.
- UI has independent read/filter/issuer/acquisition/save ownership. Lost POST
  outcome is unconfirmed, followed only by explicit GET; no automatic retry.
  Ten-minute client wait is neither server cancellation nor a wall-clock bound.
- Browser checks use real FastAPI routes, service, SQLite and captures under
  disposable fixture paths. Only source transport/audit are substituted. Both
  languages and 1280/390px layouts, exact huge values, continuation, filters,
  over-budget reads and icon containment are covered. No real source call.

Task reviews and focused inverse evidence are in task-*-report/review files.
Parent complete backend/collection/frontend/typecheck/i18n and final browser
checks are separate final gates; do not rerun whole suites as a reviewer.
Only focused probes for a named unresolved risk are permitted in own scratch.
No product/index/branch writes, agents, production DB/config/token reads, live
sidecar/provider calls, installs, merge or push. Write final-review.md only plus
any minimal probe evidence. Review the frozen full diff once; adjacent source
reads must address a named risk and be listed. Review all applicable differences,
not just task reports. Do not confuse the explicitly absent future tools with an
accidental removal: existing 54/55-tool Research surfaces are unchanged here.

Keep residual census limitations explicit. Current stored status/refresh now
have frontend references. The dynamic URL query helpers and shared translator
props can still look unreferenced to the static scanner despite runtime browser
evidence. Candidate lists are not deletion permission; no scanner whitelist or
old artifact rewrite is proposed to obtain a clean count. C11/C12, old-schema
disposition, documents/citations, three tools/four transports, issuer resolution,
export/schedule and native packaging/SQLite upgrade remain outside this batch.
