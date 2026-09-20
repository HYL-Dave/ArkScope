# Spark Retirement And Audit Review

Date: 2026-09-19. Owner: `SPARK-RETIREMENT`.
Base: `52037620f1f661bfc7fd8f696de7e101fdfdff5c` (local master).
Implementation branch: `codex/spark-retirement`.

The Spark-only feature boundary below was committed as `544d8dfd` and is
confirmed by the user's September 20 clarification: card translation stays.
Our subsequent full-feature removal was an interpretation error and was never
activated. The correction restores this boundary. The latest September 20
review narrows the prepared cleanup to Spark version rows and a hash-proven
run 13 / zh-Hant cache entry, with a mandatory private backup. All other
translations and subscription usage display/sync remain. The App stays open;
cleanup and merge are on hold. This supersedes the earlier all-results scope. See
`../2026-09-19-card-translation-retirement/README.md` for that correction and
current verification. The original test results below belong to `544d8dfd`.

The remainder is the original September 19 audit. Its no-cleanup/no-merge
authorization boundary and retained-output policy were subsequently updated
by the user's record-only cleanup and appropriate merge permissions, not by
permission to remove the feature. The report-file defect below is also now
fixed independently; current acceptance is recorded in the correction packet.

The user requested rechecking disagreements with the tool audit review and
explicitly authorized removing Spark use, options and its translation-specific
implementation. This is not authorization to remove other translation models,
erase saved research, replace financial tools with the unaccepted SEC report,
make paid calls, change production settings, restart the App, merge or push.
The separate `codex/research-source-workflow` branch at `ae0c00c0` and its audit
documents remain untouched. Its 31 commits are not silently included here.

## Decisions That Differ From The Review

1. **The new fundamental report is not an earnings-event replacement.**
   `src/fundamentals/` on the source-workflow branch contains financial periods,
   equity/enterprise valuation and peer rules, not an earnings-release timestamp
   to exchange-session return pipeline. Do not retire `get_earnings_impact`
   claiming that replacement exists. Its actual-release alignment, complete
   observation windows and statistical labels require repair or explicit
   unavailability. Five bars can mean five trading sessions; that alone is not
   an error. Truncated windows still named `5d` and fiscal periods treated as
   announcements are errors.
2. **Financial replacement is not yet admitted.** Correcter SEC formulas do
   not prove practical coverage or user acceptance. Keep provider acquisition
   distinct from calculations. Removing the old ratio path must not silently
   remove Financial Datasets access, claim a paid source was queried, or make
   mandatory SEC parsing the default again. No such retirement is performed.
3. **Quote freshness is automatable.** The audit already reproduced close-only
   input returning fresh-snapshot metadata with synthetic data. Test last/mid/
   previous-close selection, invalid numbers, observed versus request times and
   delayed/frozen/unknown evidence offline. Real Gateway close-of-session and
   entitlement checks complement these tests; they are not the only way to
   catch this defect. Neither success nor a local receipt time proves freshness.
4. **SEC has a shared governor, but not external authorization.**
   `data_sources/sec_transport.py:SecRequestGovernor` already uses a process
   lock and `flock` state with a 0.2-second request-start interval. Instances
   must share the same lock root; this does not limit every machine or unrelated
   installation sharing an IP. `freshness=stored` is a useful read contract, not
   a permission engine. `require_db_write` is currently audit-only. Explicit
   acquisition authority, no-create read paths and a shared service limiter
   remain prerequisites for any future externally exposed read-only surface.
   Do not test this by fetching into production or comparing live WAL database
   bytes; isolated stores, SQL traces and fetch spies can prove side effects.
5. **Path validation must protect the open, not only the string.** The confirmed
   `get_report` escapes remain a priority repair. An allowed extension plus
   `resolve/is_relative_to` is not by itself a complete check/open race defense.
   Use owned report identities and a confined open boundary, covering absolute
   paths, traversal and symlinks with synthetic canaries. Moving `.env` does not
   solve arbitrary file reading. No real credential file was read in our audit.
6. **Unattended acceptance is more than surviving window close.** It also needs
   single job ownership, no duplicate collection, cancellation/retry/rate and
   spend limits, failure visibility and delivery. An external MCP server is
   deferred, not a required live test for this retirement. These reviews do not
   claim those future features exist or that remaining defects are fixed.

## Retirement Contract

- Spark is absent from current/seed/eligible model options for every task.
- The registry keeps only a history/rejection identity: `new_execution_allowed`
  and `runtime_ready` are false. Deleting that identity would let a saved or
  manually entered ID be treated as an unknown custom model.
- Old saved routes are not rewritten. They appear as blocked historical routes
  and return `model_retired`; neither a plan name, model discovery nor an old
  quota bucket can reactivate them. There is no automatic model/auth fallback.
- Admission rejects before credential/provider work in fixed-card capture,
  route save, task canary, subscription output and both OAuth stream drivers.
  The OpenAI native builder also rejects before client construction, including
  `reasoning_effort=none`, which bypasses the output-limit helper.
- Remove `codex_translation_adapter.py`, its exclusive contract fixture/tests,
  the subscription dispatch/owned-thread wrapper, the special harness choice,
  and Spark quota-to-picker hints in API, TypeScript and both locales.
- Keep other-model Content Translation, stored translations and their exact
  execution receipts. No database schema, saved route, history or cache is
  migrated or deleted. Raw provider diagnostic model/quota records may still
  name historical Spark; they are not selectable execution options.
  Preserving historical output does not certify its translation accuracy:
  the separately observed numeric/meaning inversion remains an audit finding.
- Keep the bundled Codex runtime, account/model discovery and lifecycle Web
  investigation. Fifteen shared validator functions are moved to
  `src/auth_drivers/codex_event_contract.py`; their ASTs are identical after
  renaming `CodexTranslationError` to `CodexEventError`. The notification-set
  rename is structural only. The live lifecycle adapter imports this module.

This is the user's ArkScope product-retirement decision. The current English
[Codex model guide](https://learn.chatgpt.com/docs/models) does not list Spark,
but that alone does not establish a universal retirement date for every account
and provider surface. No live model probe was needed or authorized.

## Coverage Ownership

| Removed or changed behavior | Current owner |
| --- | --- |
| Spark exact-model translation, startup, output parsing, timeout/cancellation | Adapter removed; `test_spark_retirement.py` proves dispatch is unreachable, with forbidden credential/client/runtime spies. General runtime/child cleanup tests remain. |
| Shared identity, settings, reroute, verification and closed errors | `test_codex_event_contract.py`, unchanged lifecycle Web/runtime integration tests, plus AST-equivalence review. |
| Former Spark-positive route/admission/canary tests | Converted to retirement, zero-dispatch and unchanged-selection assertions. |
| Generic discovery metadata, token-generation and diagnostic persistence | `test_chatgpt_oauth_driver.py` retained; a stale Spark row advertises no task. |
| Shared route editing, effort facts, discovery drawer and dirty-state behavior | Existing frontend tests use current or explicit fixture models, not active Spark fixtures. |
| Historical translation and identity | Existing card/API/cache/receipt tests remain; new route rejection does not affect cached reads. |
| Quota revalidation hint | Deleted with its two locale leaves and API field; replaced by tests that quota evidence cannot promote retired Spark. |

## Verification

- Initial retirement tests: 14 expected failures before implementation.
- Additional lower-level bypass tests: 4 expected failures before guards
  (native no-reasoning, both OAuth drivers, direct task canary).
- Related backend: **940 passed**, including card execution, both OAuth
  drivers, native agents, model routes, runtime binding and lifecycle Web.
- Frontend focus: **167 passed / 6 files**.
- Complete frontend: **1,854 passed / 124 files**.
- `npm run build --workspace apps/arkscope-web`: TypeScript and production build
  pass; the existing large-JavaScript-chunk warning remains.
- Shared validator AST comparison: **15 unchanged functions** after the error
  type rename and **6 unchanged notification constants** after the set rename.
  `git diff --check` passes.
- i18n literal scan: **zero debt signatures**.
- First complete-backend attempt stopped after **1,185 passed / 3 failed**.
  All failures were in unchanged `test_app_records_store.py`: June 20 fixtures
  fell outside the implicit 90-day window on September 19. Isolated replay of
  the unchanged file reproduced **21 passed / 3 failed**. Tests now use the
  existing `today` argument; two added September 18/19 boundary cases and an
  explicit metadata-row assertion prevent vacuous success. The product store
  is unchanged. This file now passes **26 tests**.
- Complete backend: **11,400 passed / 12 skipped**, exit 0, in **1,847.10s**
  (30m47s), using one `pytest tests/ -q --tb=short --disable-warnings` process.
  No other pytest process ran in this worktree during that campaign. This
  validates the current retirement patch on the stated master base, not the
  separate source-workflow branch or the unchanged base revision alone.
- Before/after fingerprints match across **1,163 source/test/frontend files**:
  `1c96eaa1b33930cc0ce83a6f97e9fe2c5c170640728766e0eb414088eb50e362`.
  The fingerprint hashes a sorted JSON map of file paths to SHA-256 values
  under `src/`, `data_sources/`, `tests/` and `apps/`, including untracked files
  and excluding deleted files. Only this evidence and priority status were
  updated after the campaign.
- Main worktree status is unchanged: master remains at the stated base, with
  its two pre-existing untracked documentation entries. Source-workflow audit
  documents and commits remain separate. The retirement work is uncommitted
  in its own worktree; it has not been merged or activated in the running App.

Commands use `/home/hyl/.virtualenvs/llm_app/bin/python -m pytest` and existing
Node dependencies. No dependency upgrade, live model/Gateway/SEC call,
production data access, App restart, merge or push is part of this work.
