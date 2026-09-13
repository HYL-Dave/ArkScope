# Durable SEC Research Citations

Completed source: `5235705c` on `codex/sec-research-integration`, based on
`ca49b454`. This closes release-integration **Task3**, not the whole SEC release.
Task and whole-change reviews approve, including the final cancellation repair.
No provider-data call, production DB/config/token access, data deletion, migration,
SQLite activation, actual App restart, master merge or push occurred.

Plan: [focused implementation](../../plans/2026-09-13-sec-research-citations.md).
Parent: [release integration](../../plans/2026-09-12-sec-research-release-integration.md).

## Delivered Chain

- All three SEC tools through both API-key and both OAuth channels derive closed
  document/fact/filing references from whole admitted results, before preview or
  Layer0 reduction. Actual MCP text blocks work. Unknown tools/free prose cannot
  assert authority; malformed owned evidence records a typed gap.
- Exact call IDs retain references and end-only inputs through live events,
  successful/error/cancelled messages, archive and restart. ID-less legacy rows
  still load without capturing identified calls. Recovery reads all events,
  including the only citation after event500. Prompt history remains role/content.
- GET `/sec-research/citation?ref=...` reopens the bound stored observation or exact
  UTF-8 byte range. It validates IDs, source hashes, pointers and metadata, never
  fetches a supplied URL or substitutes latest data. Missing/corrupt sources have
  explicit typed unavailable results. No new Research schema is needed.
- Research drawer retains references through reload and selection changes; source
  text is plain text, financial values stay exact Decimal strings. Retry, stale
  response guards and keyboard focus/close behavior are covered in both locales.
- Query-only profile enumeration includes messages AND event-only roots.
  `sec_reference_closure` verifies and returns sorted retained capture/directory/
  snapshot/receipt/observation/object identities, including receipt and catalog
  provenance. Malformed roots or gaps veto maintenance; no cleanup is performed.
  Traversal processes one bounded source at a time without a new small cumulative
  store limit. The existing adjustable100GiB capacity is unchanged.

## Final Verification

| Check | Actual accepted result |
| --- | --- |
| Complete backend, `backend-final-full` | **10583 passed /12 skipped**, zero failures/errors,1216.176 runner seconds |
| Collection/execution | **10595 exact nodes**, no duplicates;272added/zero removed from accepted10311P/12S baseline |
| Skip and source identity | Same12 skip IDs;1142 files, Python, SQLite, package/hook and runner hashes unchanged across the full run |
| Final frontend, `frontend-census-cleanup-final` | **1824 passed /126 files**,14.516 runner seconds |
| Final typecheck/build/i18n | All exit0; existing act warnings and build large-chunk advisory are not hidden |
| Final browser, `citations-browser-cleanup-final` | Four real temporary API/store workflows; en/zh-Hant at1280/390;9.033 runner seconds |
| Five process-only inverses | Each kills its named owner; restored16P; no on-disk product mutation |
| Final census |4330candidates/3469uncertainties/1158readfiles; no new candidates or coverage/dependency/untracked drift; exit2 retained |

Backend source anchor is `dbc8f7e5`. The only later product difference in
`5235705c` deletes one ineffective CSS selector discovered by census; all backend
source/tests are unchanged. Frontend, browser and census were rerun after deletion.
`checks/closure-validation.json` and `checks/final-validation.json` bind these
separate source checkpoints. No backend total is assembled from overlapping runs.

The browser uses generated source bodies with actual service/route/store writes
and reads, not invented citation responses. It persists events and assistant
trace, acquires a distinct newer revision, relocates the generated market DB and
capture root, then opens the old176-byte UTF-8 passage through the actual GET.
The21-digit value `123456789012345678945` and Unicode JSON pointer remain exact.
Missing original content returns a typed gap; restoring it and Retry reopens the
same source. Persisted-message reload and focus restoration pass. Zero page errors,
horizontal overflow or clipped buttons were observed. Final desktop/mobile
screenshots were visually inspected. No opening action caused new acquisition.
The isolated loopback preview was stopped; it was not the user's App.

## Review Repair

The whole-change reviewer found one P1: a native OpenAI tool could finish and
enqueue its citation, then executor cancellation could interrupt queue consumption
before durable persistence. The prior tests cancelled only after consuming the end.

`dbc8f7e5` first disables publication, delivers the already-admitted finite queue
through the unchanged protected event stream, then rethrows cancellation. Existing
cleanup still cancels/awaits the same SDK worker through repeated cancellation.
No new retry/fallback, secret exemption or success-after-cancel behavior is added.

`test_queued_openai_completions_survive_executor_cancellation[False/True]` enqueues
two whole SEC results and cancels before consumer wake. RED: both durable end
lists empty. GREEN: exact IDs/inputs/refs survive in reopened events, cancelled
messages and maintenance roots; late secret-bearing cleanup publication is ignored.
Focused709P and independent scoped re-review approve. The original P1 report is
retained alongside its resolution, not erased from the record.

## Inverse Owners

| Inverse | Named owner / actual failure |
| --- | --- |
| Bound source hash ignored | `test_bound_hash_pointer_metadata_and_utf8_tampering_is_unavailable[fact-change0]`;1F/11P |
| Optional metadata lost | `test_sec_tool_end_preserves_whole_citations_by_call_id`;1F |
| Wrong call ID | `test_sec_tool_end_preserves_whole_citations_by_call_id`;1F |
| Event-only roots omitted | `test_profile_iterator_enumerates_message_and_event_only_roots`;1F |
| Recovery sliced to500 | `test_restart_and_no_task_cancel_rebuild_all_sec_tool_calls[restart/no-task-cancel]`;2F |

Exact recipes, diffs, function hashes and IDs are in
`checks/citation-inverse-validation.json` and `checks/inverse-*/`.
The first500 inverse attempt failed in launcher annotation setup and is excluded
from proof; rerun02 produced the two intended failures. Restored16P ran unchanged.

## Census And Receipts

First final census found one genuine unused new rule targeting `.ui-status`;
the component actually renders `.ui-status-badge`. Removal leaves no new candidate.
151 new uncertainty IDs comprise145 mechanically matched position changes and
six new statements: one consumed HTTP template and five real query/closure SQL
statements outside the scanner's complete modeling. SQL position matches additionally
compare original source AST fragments. `checks/census-review.md` assigns the five
SQL limitations to CENSUS-SQL-001; raw review_required stays intact. This does not
declare the repository clean or authorize removal of any stored data.

All78 command receipts are inventoried in `checks/run-accounting.json`.
Thirty-six nonzero checkpoints include intended REDs/inverses, intermediate
implementation/collateral failures, and clearly classified setup mistakes. They
are retained, not presented as final failures or counted as passes. Examples:
wrong Anthropic fixture target, generic SDK hook alias misuse, missed call-ID/locale
count collateral, reserved i18next ordinal option, a nonexistent test filename and
the preview test-guard listener rejection. Corrected final receipts are named above.
The last preview launch also corrected a wrong nested node_modules path; it never
started a listener. No product policy was relaxed to accommodate harness mistakes.

Historical baseline is the prior **accepted** full receipt in
`2026-09-13-maintenance-closures/checks/backend-accepted-full/results.xml.gz`,
not that batch's first failed run. Complete-suite execution was isolated from
other test programs, source writers, browsers and census. All source/hook/runner
hashes, raw logs/JUnit and command environments are retained.

## Remaining Work

- Parent Tasks5/6: operation leases, portable export/restore, SEC orphan cleanup
  and schema reset. Citation references are now a concrete prerequisite delivered,
  not a reason to postpone those tasks indefinitely. No deletion is authorized here.
- Parent Task7: default-disabled SEC research schedule and truthful job outcomes.
- Cleanup C12, C15/C20, CENSUS-I18N-001, broader CSS, CENSUS-SQL-001 and actual
  stored-data/schema disposition. C21 remains intentionally deferred.
- SQLite runtime admission/activation and native cross-platform verification.
  Current test runtime remains3.37.2; prior3.53.4 candidate evidence is not a
  deployable install or evidence of existing production corruption.

## Archive

`checks/manifest.json` lists exact admitted reports, recipes, commands, logs,
JUnit, census and screenshots with stored/source SHA256. Fixture databases,
home/XDG trees, tokens and other plan scratch are excluded. Failed receipts remain.
Gzip artifacts preserve the original content hash. The companion verifier checks
both exact membership and every object from Git, not only the local filesystem:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -B docs/superpowers/evidence/2026-09-13-sec-research-citations/verify_archive.py HEAD
```

Post-seal verification at `e20632e7` passed:278 expected/committed files, zero
missing/extra objects or hash mismatches. Receipt: `archive-verification.json`.
This plan's disposable scratch was then removed; no other worktree/plan scratch
was deleted. The branch and worktree remain. Merge/push/production activation
are separate. All cited check paths above now refer to this retained archive.
