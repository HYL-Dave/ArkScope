# Repository History Slimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native, sequential execution. Opus reviews this plan and independently verifies the rehearsal. The operator alone performs the remote push. Steps use checkboxes to record actual completion.

**Goal:** Remove obsolete verification artifacts from published Git history without losing local work, changing application behavior, or interrupting acquisition.

**Architecture:** Preserve old history outside the repository, remove test dependence on historical commits, then rewrite only a fresh, independent clone. Separate the tree-identical rewrite from ordinary fixture, guard, and documentation commits. Adopt the new history in the live checkout only after rehearsing a metadata-only transition.

**Tech Stack:** Git, pinned git-filter-repo, Python standard library and pytest, existing Node/browser test tooling, GitHub Actions.

**Spec:** The operator-approved workflow and Opus's September 30 review amendments, with the constraints below. Preparation and isolated rehearsal remain separate from independent acceptance and the operator-only remote push.

## Global Constraints

- No remote writes by the implementing agent, including tag pushes or mirror pushes.
- Allow only the specified preparation and finishing commits; freeze unrelated writers throughout execution. Defer the pending SA comment-timeout, BAC parser, and news-error-code changes until history adoption is complete. Existing acquisition keeps running unchanged.
- Filter only `.superpowers/`, `docs/superpowers/evidence/`, and the already-forbidden `data/verification/` root. No extension-wide, size-based, author, or secret-content filtering.
- Do not filter `docs/superpowers/plans/` or `docs/superpowers/specs/` out of history. Clean obsolete current-version documents in a separate ordinary batch after history adoption, with dependency and unfinished-work review rather than an age or no-inbound-link rule.
- Preserve current source, provider credentials, databases, acquisition queues, installed extensions, and the running App. No reset-hard, clean, extension reload, or database migration.
- Keep original ciphertext blobs unchanged. Never publish local git-crypt keys, decoded private documents, local state archives, or backup bundles.
- Keep backups, reports, screenshots, tool environments, and rehearsal clones outside the repository and outside disposable `/tmp` cleanup scope. Only maintained fixtures, guards, this plan, and the final mapping/runbook enter Git.
- Do not delete a worktree merely because its HEAD is an ancestor of master. Working files, ignored files, and active process use are separate checks.
- Zero GitHub forks does not establish that nobody has cloned the public repository.

## Verified Baseline

Read-only inventory on September 30, 2026; recheck before execution:

| Item | Result |
| --- | --- |
| Local and remote master | `625d1970e8976d9128ee01ff642990a79ae759ba` |
| Current tree | `7d3cbdd3e17f27584a7d20f18c5f1bcf57913921` |
| Master commits | 3,657 |
| Commits reachable from all named refs | 3,694 |
| GitHub public metadata | 0 forks, 0 PRs, 0 releases; no remote tags |
| Worktrees | Main checkout plus 23 detached temporary worktrees |
| Other retained state | 4 archive tags, 1 stash, 5 reflog commit IDs not reachable from named refs |
| Main worktree | No tracked edits; the operator explicitly authorized deletion of the untracked September 3 plan |
| Historical fixture | 25 source files, 509,374 bytes; not one file |
| Tool availability | git-filter-repo not installed; install only in an isolated tool environment after approval |

The four detached heads outside master are `3132d56e`, `ba4f2619`, `650130cb`, and `ebe4c051`. Preserve all four even where an equivalent patch was merged under another ID.

Six older worktrees fail ordinary status inspection because git-crypt cannot open its key: `fable-settings-plan-review/master-wt`, `fable-trancheb-review/native-wt`, both `security-lifecycle-task3-red-*` worktrees, `security-lifecycle-task4-amendment-red`, and `trusted-lifecycle-stage3-base-census2-5d88e1b3`. Their dirtiness is **unknown**, not clean. Do not disable encryption filters or force-remove them to make an audit pass.

The first targeted-path commit is `54fb3fc08fe166725cce90e7ddeafcba3b16459d` (July 25); its parent has 2,279 ancestors including itself. Exact changed-ID counts come from the rehearsal mapping, not subtraction alone. `data/verification/` has no current named-ref history, but remains part of the prevention policy.

Reported 264-to-70 MB savings are estimates. Current loose/packed object totals and GitHub's cached repository size measure different things; measure comparable fresh-clone packs during rehearsal.

## Review Focus

1. Backup omits detached/reflog/stash/unreachable commits or unique working files: Task 1 requires named anchors, two-device copies, and restore/readback checks.
2. Old browser packaging still reads historical trees: Task 2 verifies all 25 inputs and installed-browser upgrade/rollback in a depth-one clone.
3. Clean tip hides forbidden ancestral paths: Task 3 tests add-then-delete, non-first-parent merges, identical blobs at allowed paths, and shallow-history refusal.
4. Cutover encounters concurrent commits or modified files: Tasks 4 and 6 use fixed identities, parent/tree checks, expected-old ref updates, and no forceful worktree cleanup.
5. Documentation points into removed evidence, or old state is accidentally republished: Tasks 5 and 6 distinguish archive-only references and scan every nondeleted ref proposed for push.

## Task 1: Freeze and Prove Recoverability

**Files:** Private inventory and backups only; no application file edits.

**Interfaces:** Produce a private manifest with full ref/worktree/reflog/stash IDs, index and working-file inventories, archive hashes, device IDs, and the exact remote master OID (`REMOTE_EXPECTED`). Never put credential values in the manifest.

- [ ] Confirm the operator and Opus have stopped unrelated commits, checkout changes, cleanup, and pushes. The App and acquisition continue. Recheck remote refs and GitHub metadata.
- [ ] Record every worktree HEAD and status, staged/unstaged patches, untracked files, stash entries including index/untracked parents, archive tags, and reflog-only commits. Run `git fsck --full --unreachable` and inventory every completely unreferenced commit as well; Opus reported 30, to be independently counted at the freeze boundary. Inventory ignored worktree files separately before considering deletion. The explicitly approved September 3 untracked-plan deletion is excluded from preservation.
- [ ] Pin worktree HEADs, every stash entry, reflog-only commits, and every completely unreferenced commit under private temporary `refs/backup/history-slimming-20260930/` names. Back up all such commits rather than deciding that old amended versions are worthless. Verify every recorded OID exists after restore. Do not treat those names as publishable branches or tags.
- [ ] Create a self-contained `git bundle create <private-path> --all`. Store identical copies in two private archive directories on distinct filesystems, with restrictive permissions and matching SHA-256 digests. Neither archive may be inside the repo or its temporary worktrees.
- [ ] Save working-file state and required local Git configuration separately: [bundles do not capture working-tree or configuration state](https://git-scm.com/docs/git-bundle). For each git-crypt-blocked worktree, retain the original directory until a byte-preserving private archive and recovery check succeed. Encryption key material needs private preservation outside Git. A failed status check must not become a deletion approval.
- [ ] Run `git bundle verify` for both copies. Restore each with `git clone --mirror <bundle> <isolated-restore.git>`, run `git fsck --full`, verify all anchored objects/parents and archive tags, and inspect restored stash changes. Confirm `b24a2c1d` and its fixture blobs are readable. Record encryption-key availability without displaying keys; do not promise decrypted historical recovery when a required key is unavailable.
- [ ] Keep archive repositories offline and without a push destination. Record the restore procedure. Repeat backup verification after Task 2/3 preparation commits; the final pre-rewrite input must also be recoverable.

**Gate:** Backup objects and working-file state are accounted for. Unverified worktrees remain intact. No old ref, stash, worktree, or reflog is discarded in this task.

## Task 2: Remove Historical Test Dependencies

**Files:**
- Modify `tests/sa_midfill_fixture.py` and `tests/sa_midfill_browser_fixture.py`.
- Add `tests/fixtures/sa_midfill_baseline/baseline.zip`, `manifest.json`, and `README.md`.
- Add `tests/test_sa_midfill_baseline_fixture.py`.
- Preserve the behavioral assertions in `tests/test_sa_midfill_upgrade.py` and `tests/test_sa_midfill_upgrade_browser.py`.

**Interfaces:** Keep `baseline_source(path: str) -> str`. Add `baseline_extension_paths() -> tuple[str, ...]`, returning only the frozen extension entries. Preserve `BASELINE` as provenance, not a runtime Git revision dependency.

- [ ] Work in an isolated preparation checkout. Add failing tests proving both loaders work without access to the old commit and never execute `git show` or historical `git ls-tree`. Check unknown paths, duplicate archive entries, missing bytes, and checksum mismatches fail explicitly.
- [ ] Capture raw Git blobs from `b24a2c1dfac740fde8e4b491684b7ff9b58a6b7e`: `src/sa/company_collector.py` plus all 24 direct children of `extensions/sa_alpha_picks/` with `.js`, `.json`, `.css`, or `.html` suffixes. Do not copy secrets, browser storage, installed packages, outputs, or unrelated historical source.
- [ ] Store those exact bytes in a deterministic ZIP with fixed entry metadata. Record full origin commit, path, blob ID, byte length, and SHA-256 per entry in the manifest. Document that these are test-only upgrade baselines. Keeping them archived avoids indexing an old executable source tree as current code.
- [ ] Replace historical reads with standard-library archive reads validated against the manifest. Enumerate baseline browser files from the manifest. Candidate packaging may use the current tracked file list, but must not read a historical tree. Read explicit entries, not unchecked archive extraction paths.
- [ ] Independently compare every fixture entry with the source Git blob before rewriting. Run `python3 -m pytest -q tests/test_sa_midfill_baseline_fixture.py tests/test_sa_midfill_upgrade.py` and the installed-browser tests with `ARKSCOPE_BROWSER_ACCEPTANCE=1` for both Firefox and Chromium.
- [ ] Run the same focused gates from a depth-one `file://` clone that cannot resolve `b24a2c1d`. Do not fetch old history to make the tests pass. Keep browser profiles, native stores, and outbound-network isolation as in the existing fixtures.
- [ ] Commit only the fixture, loader changes, tests, and reviewed maintenance plan. Review the exact diff; no runtime source or installed extension changes.

**Gate:** Shallow-clone tests exercise the real old/new upgrade and rollback paths without a historical-object dependency.

## Task 3: Prepare History Guards Without Premature Activation

**Files:** Extend `tests/repository_hygiene.py` and `tests/test_repository_hygiene.py`. Prepare activation edits for `.githooks/pre-push` and `.github/workflows/repository-hygiene.yml` only in Task 5.

**Interfaces:** Add mutually exclusive CLI modes `--history-ref REF` (repeatable) and `--pre-push`; keep staged/default and `--all-tracked` behavior. Exit 0 means verified clean, 1 forbidden history, and 2 unavailable/incomplete inspection. The existing forbidden-root tuple remains the authority.

- [ ] Add failing temporary-repository tests for forbidden paths later deleted, a merge's second parent, identical blobs also stored at allowed paths, root-as-file/symlink, lookalike allowed prefixes, shallow history, and missing revisions.
- [ ] Implement complete ancestry inspection of explicitly resolved commit tips using Git's path-aware full-history traversal. Match root files and descendants literally, not broad string prefixes. Reject shallow/incomplete ancestry; do not infer cleanliness from the latest tree, first-parent history, or deduplicated object-name output.
- [ ] Parse standard pre-push stdin and inspect every nondeleted proposed local tip, including peeled commit tags. Permit deletion-only pushes without scanning a nonexistent tip; reject unsupported noncommit tips and Git errors explicitly. Test multiple refs, a contaminated new branch/tag, and a deleted ref.
- [ ] Test the installed hook against a disposable local bare remote: clean push succeeds; clean-tip/dirty-history push is rejected before the remote changes. Never use GitHub for this test.
- [ ] Run `python3 -m pytest -q tests/test_repository_hygiene.py` and existing inventory/boundary tests. Commit the checker and tests without activating full-history enforcement on the still-old production history.

**Gate:** The checker can detect ancestral reintroduction. GitHub Actions is a post-push alarm, not server-side push rejection. Local hooks can be bypassed; do not claim stronger protection or change branch-protection policy implicitly.

## Task 4: Isolated Rewrite and Frozen-Tree Verification

**Files:** No further production edits. Tool environment, clone, mapping, and execution output stay in the private run directory.

**Interfaces:** Freeze prepared master as `F`, pure rewritten tip as `R`, and retain `REMOTE_EXPECTED` separately. Preparation can make F newer than the remote; this is not permission to refresh the push lease.

- [ ] Finish and review preparation commits, fast-forward them locally with only the approved maintenance-file changes, and refresh the two verified backups. Record F's commit count, tree ID, index state, refs, and application/extension file fingerprints. Freeze additional commits.
- [ ] Install a recorded, pinned git-filter-repo release into an isolated tool environment. Create an independent `git clone --no-local --single-branch --no-tags --branch master` of the prepared repo. No alternates, shared object store, backup refs, stash, or archive tags may enter the rewrite candidate.
- [ ] Rewrite only that fresh clone, without `--force`:

```bash
git filter-repo --invert-paths \
  --path .superpowers \
  --path docs/superpowers/evidence \
  --path data/verification \
  --prune-empty never --prune-degenerate never \
  --preserve-commit-hashes --preserve-commit-encoding \
  --replace-refs delete-no-add
```

`--preserve-commit-hashes` preserves hash text inside messages; it does **not** preserve rewritten commit IDs. Keeping empty/degenerate commits is necessary for the requested count/topology check. Exact root paths cover files as well as directories. See the [git-filter-repo manual](https://github.com/newren/git-filter-repo/blob/main/Documentation/git-filter-repo.txt).

- [ ] Before adding any finishing commit, prove `F^{tree} == R^{tree}`. Verify commit counts match, the commit map has one nonzero destination per input commit, and each mapped parent list preserves order/topology. Compare every mapped tree with its original minus the three excluded roots; all retained path/mode/blob tuples must match, including encrypted blobs. Audit author/committer/message/encoding fields; halt for unexpected changes or signature-loss decisions.
- [ ] Inspect every reachable candidate tree for the three forbidden roots, independently of the new guard. Confirm no old backup/replace/archive refs and no object alternates remain. Run `git fsck --full`.
- [ ] Compare packed sizes of equivalent independent pre/post clones. Report actual bytes, changed-ID count, preserved-ID count, and empty-commit count. Do not use the live checkout's loose objects or GitHub's cached size as the savings baseline.

**Gate:** The pure rewrite changes only the targeted paths in history; the current prepared tree is identical. A count or content mismatch stops the rollout.

## Task 5: Mapping, Guard Activation, and Independent Acceptance

**Files:** Add `docs/maintenance/history-map-2026-09-30.tsv` and `docs/maintenance/HISTORY_REWRITE.md`; add `.githooks/pre-push`; modify `.github/workflows/repository-hygiene.yml`. No bulk document rewrite in this batch.

**Interfaces:** Final ordinary finishing commit is `C`, descended from R. The map covers F and its ancestors, not the future commit that stores the map itself.

- [ ] Preserve the tool's complete old/new commit map as one intentional maintained TSV. Explain lookup, backup recovery, and provenance in the runbook. Do not add old-history refs or replace refs as a lookup shortcut.
- [ ] Classify old document references: surviving source/commit references can use the map; references to removed evidence must use the external archive recovery procedure. Mapping a SHA does not restore a deleted path. Do not blindly replace hash-like strings, checksums, archive-only IDs, or memory files belonging to another agent.
- [ ] Activate the tested pre-push hook. Configure Actions checkout with `fetch-depth: 0`, retain the tracked-file check, and add the full-history check for HEAD. Preserve `persist-credentials: false` and read-only permissions. Document how new clones enable `.githooks`.
- [ ] Commit only those four finishing files. Assert that the F-to-C tree delta is exactly the allowed finishing files; application, tests prepared before F, dependencies, and extension payloads remain identical.
- [ ] Validate a fresh full clone of C with `ARKSCOPE_BROWSER_ACCEPTANCE=1 python3 -m pytest -q tests`, `npm --prefix apps/arkscope-web test`, `npm --prefix apps/arkscope-web run typecheck`, `npm --prefix apps/arkscope-web run build`, and `npm --prefix apps/arkscope-web run check:i18n-literals`. Run the focused baseline/upgrade browser gates again from a depth-one clone. Full-history guard must refuse that shallow clone, while baseline fixture tests must not need old objects.
- [ ] Use isolated DB paths, browser profiles, ports, and output directories. Do not link production data or load real provider credentials for these gates. Handle any required git-crypt access privately without changing stored blobs. Record exact commands, exits, skips, tree/commit identities, and environment prerequisites; unexpected skips or unavailable browser gates are not passes.
- [ ] Give Opus the frozen F/R/C identities, two-backup verification, mapping digest, tree/count/topology results, size measurements, focused/full test results, and cutover rehearsal from Task 6's first step. Wait for independent acceptance. Corrections create a new C and require affected gates to rerun.

**Gate:** Opus verifies the actual frozen candidate, not an earlier diff. Test outputs and the acceptance handoff remain outside Git. Do not change C just to append test logs or its own commit ID to the runbook.

## Task 6: Operator Push, Live Metadata Adoption, and Cleanup

**Files:** No runtime source changes. Git metadata and the already-reviewed finishing files only.

- [ ] First rehearse the complete operation against a disposable bare remote and an old-history checkout. Verify an unexpected remote advancement makes the explicit lease reject the push. Verify a stale local expected-old ref rejects adoption. Neither refusal may change tracked files.
- [ ] Record local App/backend processes and read-only acquisition health. Recheck that the actual live checkout still matches F's index/tree and runtime file fingerprints; preserve untracked files. If unexpected tracked changes appear, stop instead of resetting them.
- [ ] Prepare a push from the verified clean candidate, sending **only** C to `refs/heads/master`, with `--force-with-lease=refs/heads/master:<REMOTE_EXPECTED_FULL_OID>`. The operator runs it. Do not use bare `--force`, `--mirror`, `--all`, `--tags`, or an implicitly refreshed lease. If the remote moved, stop and reconcile; do not overwrite the expectation automatically. The [explicit lease avoids the documented background-fetch hazard](https://git-scm.com/docs/git-push).
- [ ] After the operator reports success, verify the remote tip, fresh remote clone, full-history guard, and Actions result. A failed check is not completion. GitHub size reporting may lag; [GitHub does not offer support-assisted purging for ordinary non-sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
- [ ] Import only the verified candidate history into the live repo, without archive tags. Use an expected-old ref transaction to move local master from F to R only after proving their trees/index agree. Do not checkout or reset runtime files. Then fast-forward R to C, applying only the four reviewed maintenance files. Re-enable/verify the local hooks path and tracking configuration; preserve the existing remote authentication configuration.
- [ ] Compare runtime file bytes and mtimes, running process identities, native host/extension locations, and read-only acquisition progress. No App restart or extension reload is planned; unexpected runtime differences stop completion rather than triggering an unsolicited restart.
- [ ] Only after restore verification and remote/local acceptance, assess each old temporary worktree for active use and unique tracked/untracked/ignored content. Remove individually only when confirmed disposable. Keep git-crypt-blocked worktrees until their working state is verifiably preserved; no force-remove shortcut.
- [ ] Archive then retire obsolete stash/backup/archive refs with expected-OID checks. Re-audit every ref and reflog before any expiry/pruning. Local disk reclamation is a separate final gate: unresolved worktrees or recoverability gaps postpone local GC, not the verified remote rewrite. Never push archived refs back to the clean repository.
- [ ] Provide Opus the commit map for its own memory update. Report remote reachable pack size separately from local retained archives, old worktrees, and GitHub cached size.

**Rollback:** Before remote push, discard only the isolated candidate; the live checkout and remote remain valid. After push, stop writers and preserve both histories. Local recovery uses the verified external archive; reverting the remote requires a new, explicit operator decision and a lease against its then-current tip. Never automatically republish old history as a rollback.

## Completion Checklist

- [ ] Both external backups restored and all special refs/local work accounted for.
- [ ] Historical fixtures pass in shallow clones; installed upgrade/rollback coverage retained.
- [ ] F and R have identical current trees; retained history paths and topology verified.
- [ ] C contains only reviewed finishing changes, with full regression and independent acceptance.
- [ ] Operator-only explicit-lease push verified; a fresh remote clone has clean reachable history and its packed size has been measured against the equivalent original clone. These are the size/cleanup acceptance criteria, not GitHub's displayed storage number.
- [ ] Handoff explicitly states that old SHAs may remain accessible through GitHub caches and displayed size may lag. No guarantee of old-URL disappearance or a support-assisted purge is part of acceptance.
- [ ] Live runtime unchanged and acquisition checked without interruption.
- [ ] Old local state disposed only where proven safe; remaining items and disk savings reported honestly.

## Deferred Ordinary Documentation Cleanup

After history adoption, classify plans/specs by completed or superseded work, active design authority, and executable/test consumers. Lack of an inbound link alone is not proof that an approved but unfinished feature is obsolete. Preserve current financial/company-research, retention, and SA article-workbench authorities, this maintenance plan, and documents still read by tests. Coordinate lifecycle-dependent documents with the SEC/lifecycle retirement batch. Remove confirmed obsolete files only from the current tree, repair current documentation links (including already-broken links), and run the affected documentation/consumer gates. Do not expand the historical filter to save a small amount of text. The pre-existing untracked September 3 plan was separately authorized for deletion and does not wait for this batch.
