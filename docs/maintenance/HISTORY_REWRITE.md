# Repository History Maintenance

## September 30, 2026 Candidate

This candidate removes only `.superpowers`, `docs/superpowers/evidence`, and
`data/verification` from reachable history. Plans and specs remain in history;
obsolete current documents are a separate ordinary cleanup. No application,
database, provider configuration, or installed-extension migration is involved.

- Prepared original tip F: `a8906231ef5a2df1de2905df0fb873c8c13ef21e`.
- Pure rewritten tip R: `eae50790571aed5a10f726a4198cc4c503f4ea11`.
- Identical F/R tree: `3f5cdf300c1d522e878585833bc5676d4984bf55`.
- Both histories contain 3,660 commits: 2,279 IDs unchanged, 1,381 changed.
- Every retained path, mode, and blob was compared at every mapped commit.
  Parent order, authors, committers, encoding headers, and messages match.
- Empty and degenerate commits were preserved. Old hash text in commit
  messages was deliberately not rewritten.
- Independent single-branch clone packs: 228,322,263 bytes before and
  29,709,835 bytes after, excluding pack indexes and private archive refs.

These are rehearsal results, not a claim that the remote already changed.
Independent acceptance and the operator's explicit-lease push are separate
gates. Validation output and complete offline backups are stored outside Git.

The rewrite used git-filter-repo 2.47.0 with exact path exclusions,
`--prune-empty never --prune-degenerate never --preserve-commit-hashes
--preserve-commit-encoding --replace-refs delete-no-add`. It ran in a fresh,
independent clone, without `--force`. No backup refs or replacement refs are
part of the candidate.

## Old References

[history-map-2026-09-30.tsv](history-map-2026-09-30.tsv) contains every full
old/new commit pair from F's history. It does not cover later commits, the
finishing commit that stores the map, or archive-only branches and stashes.

Look up an old full ID or an unambiguous prefix:

```sh
awk -F '\t' -v old='<old-id-or-prefix>' 'NR > 1 && index($1, old) == 1' \
  docs/maintenance/history-map-2026-09-30.tsv
```

Require exactly one result before using its new ID. A mapped commit can
resolve surviving source references; it cannot restore a removed evidence
path. Do not blindly replace checksums, IDs from unrelated histories, or
archive-only references with commit IDs from this table.

For removed evidence or archive-only work, use the operator's private,
verified full-history bundle on an offline recovery copy:

```sh
git bundle verify /private/path/pre-rewrite-reviewed.bundle
git clone --mirror /private/path/pre-rewrite-reviewed.bundle /private/path/recovered.git
git -C /private/path/recovered.git remote remove origin
git -C /private/path/recovered.git show '<old-full-id>:<old-path>'
```

Bundles preserve Git objects and refs, not working files or configuration.
Local state and encryption key material require the separate private backup.
Never publish the bundle, those keys, restored backup refs, or recovered
private material. Keep unresolved old worktrees intact until independently
preserved; ancestor status alone does not establish that they are disposable.

## Prevent Reintroduction

Enable the tracked hooks in each development clone:

```sh
git config core.hooksPath .githooks
python3 -I -S tests/repository_hygiene.py --all-tracked
python3 -I -S tests/repository_hygiene.py --history-ref HEAD
```

The pre-commit hook rejects newly tracked local artifacts. The pre-push hook
examines complete ancestry of every proposed nondeleted branch or commit tag,
including merged side branches. Deletion-only pushes remain possible. A
shallow clone cannot prove clean ancestry; obtain complete history before
pushing. Historical upgrade tests use verified, frozen fixtures and do not
need old commits, even in shallow clones.

GitHub Actions checks both the current index and complete HEAD history with
`fetch-depth: 0`. CI runs after a push, so it is an alarm, not server-side
rejection. Local hooks can be bypassed. Avoid merging an old-history clone
back into the cleaned history; reapply only reviewed work onto a fresh clone.

## Adoption And Limits

Only the operator pushes the accepted candidate to `refs/heads/master`, using
`--force-with-lease=refs/heads/master:<recorded-full-remote-id>`. The expected
ID must be the frozen remote value, not an automatically refreshed tracking
ref. Any intervening remote change stops the operation for reconciliation.

For the running checkout, first verify F/R tree and index equality and an
unchanged working tree. Import only clean history, use an expected-old ref
update from F to R, then fast-forward the ordinary finishing commit. That
finishing commit changes only this runbook, the mapping, pre-push hook, and
hygiene workflow. Do not reset or rewrite running application files.

Acceptance uses the new remote tip, a fresh clone's clean reachable history,
its measured pack size, regression results, and unchanged runtime state.
GitHub's displayed size may lag and old SHA URLs may remain accessible.
[GitHub does not purge ordinary non-sensitive data on support request](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
This is repository maintenance, not a guarantee that previously published
content disappears. Remote rollback or disposal of private backups requires
a separate operator decision; never automatically push archived history back.
