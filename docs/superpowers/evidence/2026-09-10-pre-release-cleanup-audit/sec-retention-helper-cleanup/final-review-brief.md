# Final Review: SEC Retention Inventory And Helper Cleanup

This is the whole checkpoint review of base `6ba563d9` to the immutable head
provided by the parent. Earlier cleanup before that base is context, not this
patch. Worktree: `/tmp/arkscope-listing-sec-macro-convergence`.

Read the parent's generated `final-review.diff`, then the plan
`docs/superpowers/plans/2026-09-10-sec-retention-inventory-and-helper-cleanup.md`
and evidence README in
`docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/sec-retention-helper-cleanup/`.
Inspect actual code needed to resolve findings, not just report claims. Use the
code-reviewer template from the requesting-code-review skill. Include separate
spec/quality verdicts and concrete file/line findings with severity.

## Binding Constraints

- Production permission: only named `profile_state.db` and `market_data.db`, read-only structure/count/reference aggregates. No credential value, body, URL, model prose, unrelated settings value or whole-row hashing.
- No production write/DROP, backup copying private contents, provider call, App restart, merge or push. Statistics do not authorize subsequent deletion.
- No spent operator CLI in product source. Archive this bounded query and its synthetic privacy tests as non-executable evidence after use.
- Preserve current investigation, provider confirmation, tools, routes selected by users, historical receipt/digest readers, prices/news/SA, credentials and membership removals.
- Current schema conversion and the new SEC three-tool service remain separate. No empty/retired compatibility handlers.

The actual-store inventory remains unavailable: one root-readonly bwrap caller
failed at ATTACH before explicit queries. No production counts were obtained.
A new question about WAL/SHM coordination writes is unanswered. Review that
unavailability and its consequences honestly; this checkpoint cannot complete
data disposition or claim SEC research exists. Do not open production files to
resolve it. Inspector/privacy fixtures are archived text, not runtime modules.

## Integration Review Targets

1. Byte-identical neutral JSON/digest ownership and all actual current/retained
   consumers; old exports/aliases absent; no accidental schema/hash contract drift.
2. Exactly five obsolete HTTP entries removed, real tool/history/global-action
   consumers retained, route-only translator and receipt facade not left tests-only.
3. Deleted tests account for deleted behavior; transferred integrity/privacy
   assertions and current stored-translation reader remain effective.
4. Reports distinguish frozen full-suite code, later facade scoped rerun and
   exact final collection; no overlapping-result inflation or failed-read counts.
5. Current audit/priority/ownership docs keep remaining source/data queues named.
   Census exit2, SQL preparation gaps, CSS/i18n queues and unknowns are retained.

All rulings are in `progress.md`: removing last-caller translation execution;
adding negative codec owners; allowing the unrelated route task to start while
its codec test-only re-review completed; removing the now tests-only receipt
facade. Scoped review and re-review artifacts provide evidence for each. The
scanner's missing joined-table declaration is queued under C21, not silently
suppressed or permission to DROP anything.

## Review Boundary / Output

Read-only source/diff/archive review. No index/HEAD/source changes, tests reruns,
production/config/.env/credentials reads, provider/App execution, installations,
merge/push or subagents. Existing fresh test artifacts are sufficient unless a
specific unresolved doubt requires returning a proposed narrow check to parent.
Write only `.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/final-review.md`.
Return concise verdict, named findings/risks and report path. Assess this source
checkpoint, explicitly separating the incomplete actual-store task.
