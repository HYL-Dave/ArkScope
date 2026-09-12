# September 13 Maintenance Closures

Base: `ef5f7b48`. Worktree: `/tmp/arkscope-research-output-boundary`, branch
`codex/sec-research-integration`. Main/master is untouched. This evidence records
bounded finished items, not completion of every SEC or cleanup task.

## Current Checkpoint

- EIR-001/C13: closed at `eec66b9e`, independent task review approved.
- C11: implemented at `a4bf0a73`, review fix `6cddc221`; task re-review approved.
- Fixed-source frontend1779P, typecheck/build and census completed; the single
  full backend run and Git archive verification are still pending.
- SQLite: source-only admission path reviewed; no build/install/activation here.

## EIR-001

Removed exactly five rules for two obsolete class tokens: `.page-head` and
`.page-head-actions`, including desktop and mobile rules. The substring
`detailpage-head` is a distinct live owner, not a sixth deletion target.
All908 retained rules/2857 declarations are identical; parsing and independently
removing only the five old rules also reproduces the exact final CSS bytes.

Three named tests enforce desktop/media absence and a real PageHeader positive
control. Actual assertion RED is distinct from two earlier fixture-loading
errors. Independently restoring a desktop rule or media rule fails only its
named owner. All failed receipts are retained, not counted as passing checks.

Controller focused rerun38P; full frontend1779P/124files, typecheck/build pass.
Ten real-primitive browser cases (general and Settings headers at
320/390/760/761/1440px) have identical before/after pixels and geometry, real
click/disabled-state checks, and no overlap or horizontal overflow. This is an
isolated component/CSS fixture, not a live production Settings session.
Existing React act-warning categories and Vite chunk-size warning are recorded;
neither is silently suppressed or represented as a newly introduced defect.

The wider CSS census queue remains open. The original audit C13 row specifically
shares this EIR-001 scope, so that row can close without claiming all CSS clean.

## C11

The obsolete `use_local_news` setting/environment switch, helper/arguments, PUT
`/news/settings`, five news-only status fields and unused frontend setter/label
are physically removed. The current normalized/direct writers, configuration
blockers, permission ordering, read routes and actual stored rows remain.
The removed PUT returns405 through the retained ticker GET route, not a stub.

Actual provider_sync observations now own news overlay/health. Neither the old
setting nor article publication time can replace ingest success. Non-news sync
and IBKR's existing combined market-health semantics remain. Review R1 identified
the exceptional path that retained old news when current acquisition failed;
`6cddc221` clears that provisional slice before both the path probe and query,
keeping degradation notes and all other data. Real corrupt-current-table tests
and a path-probe failure control preserve nonempty price/news/cache observations.

The same owned news reader also incorrectly interpolated `?`/`#` filenames into
a SQLite URI, bypassing the intended read-only option and creating an unintended
empty sibling in disposable RED fixtures. Resolved `as_uri()` encoding fixes
this narrow defect; populated/missing-path tests prove correct reads, unchanged
fixture bytes and noncreation. No actual user-store failure is inferred.

Original scoped300nodes became329 (34removed/63added), then R1 added3 without
removal. Final worker332P and controller76P are separate checks, not a combined
full-suite total. Old-value validation, telemetry suppression and health-failure
ordering each have independent inverse failures followed by restored GREEN.
Initial fixture/import/constraint mistakes and their corrected assertion RED
receipts remain explicitly distinguished. The current normalized switch and
malformed-current-setting blockers were not relaxed.

Only source consumers/writers of the abandoned key are removed. The key's actual
stored-data disposal is still a separate inventory/backup operation; this source
cleanup never deletes it automatically or changes unrelated profile settings.

## Census

Against `ef5f7b48`, final source `6cddc221` gives1148read/4330candidate
occurrences/3463uncertainties. No new candidate IDs, coverage reductions,
dependency metadata changes or main-worktree untracked-name drift. Fifteen
removed occurrences are exactly5CSSrules+10pairedlocaleleaves; they have13unique
IDs because repeated desktop/media selectors share two IDs.

Raw comparison still reports175newuncertainty IDs and review_required/exit2.
All175 match prior metadata excluding location (2 also match Python source
nodes);8 unmatched removals are the five old translation calls, one test binding
and the old setting read/write. This does not turn metadata matching into proof
of all program semantics or resolve the existing scanner queues. The first
unique-ID reconciliation and subsequent multiplicity-aware report both remain.

## SQLite Admission

The prior3.53.4 candidate evidence remains
[separately sealed](../2026-09-12-sec-integration/sqlite-candidate.md).
This batch does not rerun or overwrite it. Source-only examination identifies
an app-private immutable SQLite library and an executable wrapper around the
unchanged Python as the minimal Linux preparation path. Electron and installed
SA host have separate executable selectors; both must participate. The analysis
Python child deliberately strips loader variables, so it needs a narrow runtime
admission change, not wholesale inherited environment access.

Preserve existing bind-capacity/privacy behavior by default and verify package
relocation, actual mapped library/source ID, every writing child, and rollback.
The official [compile-options documentation](https://sqlite.org/compile.html)
explains that these settings affect behavior and recommends testing customized
builds; the historical candidate tests do not certify a differently built
deployment artifact. Actual configuration readback, a stopped-writer maintenance
window, coherent backups and full integrity checking still precede activation.
No actual-store health or corruption is inferred from a synthetic reproducer.

## Remaining Work

- SEC durable Research references, operation leases/export/restore, recovery
  commands and schedule. Release Tasks3/5 protect references and operations;
  recovery Task6 depends on them. Backend document citations alone are not all
  durable Research roots, so cleanup/reset cannot be treated as ready independent
  deletions.
- C12 collector/news entrypoints, C15/C20 and actual old stored-data/schema/key
  disposition; i18n, broader CSS and SQL-scanner queues. C21 remains deferred.
- Formal SQLite packaging/readmission/activation, not a Python/numpy upgrade.

No production DB/config/key read, provider call, real data deletion, actual App
restart, installation, master merge or push occurred. Test stores/browser homes
are disposable; one product writer/test runner owns this worktree at a time.
