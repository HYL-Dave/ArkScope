# Recent SA Comment Priority

Approved by the operator on September 24. Work stays on `feat/sa-company-data`;
no production data deletion, extension replacement, merge or push.

## Requirements

- Prioritize each comment/reply's last 30 days, not the age of its article or parent.
- Keep necessary older parent context and already-loaded older comments.
- Treat unknown dates/ordering conservatively. An old row is not a stop proof.
- Explicit Deep Repair includes historical text expansion. Initial/routine scans
  and manual article linking do not imply a historical request.
- Improve traversal through materialized comments without increasing existing
  capture budgets/retries or weakening navigation, identity or website gates.
- Preserve stored comments and bodies. Distinguish scoped traversal from full
  history completion and do not manufacture a recent coverage denominator.

## Progress

- Implemented: shared extraction/date reading, recent/context priority,
  explicit scope separate from time profile, loaded-frontier traversal.
- Implemented: v6 scan receipt, native/DAL/store/read contracts, separate recent
  provider-count observation for routine change detection; old checkpoint kept.
- Implemented: harness scope selector and root data-acquisition policy.
- Verified in isolation: Chromium/Firefox bounded traversal fixture; adversarial
  comment controls, unchanged persistence and concurrent migration tests.
- Reviewed: intermediate observer skipping, implicit destructive duplicate
  cleanup, inconsistent historical-pending admission and null-count checkpoint
  replacement were reproduced and fixed. No remaining production review finding.
- Prepared: separate private Firefox 1.0.5 package with two recent-only slots,
  prior attempt/stop records preserved, and no production database permission.
- Pending: frozen-revision whole-project regression before merge.
- Pending: new signed-in large-thread and routine acceptance. The prior large
  pair failed (53 missing baseline comments, all within 30 days) and remains failed.

The current implementation neither proves website-wide recent completeness nor
provides a provider-level incremental cursor. The browser can still load older
parent threads to discover new replies. Live artifacts stay outside Git.
