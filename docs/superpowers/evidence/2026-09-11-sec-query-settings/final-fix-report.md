# Final Fix Report

## Handoff

**Ready for commit, awaiting explicit parent permission.** No index mutation or
commit performed. The final source is restored and stable for the parent's
scoped re-review and full frontend/typecheck/i18n/browser verification. This
dispatch addresses the complete finding list: I1, one P2 catalog-rendering bug.

- Worktree: `/tmp/arkscope-listing-sec-macro-convergence`.
- Branch: `codex/listing-sec-macro-convergence`.
- HEAD before/after: `97a1aba680c5654d0f723bcf53a7e6e8c4665dff`.
- Read the final brief, independent review/probe, binding plan/progress, relevant
  Records/pagination/API contracts, backend conflict owner, and existing panel
  tests/closed runner. Applied receiving-code-review, systematic-debugging,
  RED-first TDD, and verification-before-completion workflows. No applicable
  AGENTS.md/CLAUDE.md/GEMINI.md was found in the implementation path.

## Changed Files

- `apps/arkscope-web/src/settings/SecResearchPanel.tsx`: catalog rows now use
  unique page-local positions as React keys. An inline comment explains why
  filing IDs are insufficient. The facts branch retains the exact prior key
  expression. Stateless, read-only catalog rows need no content hash, metadata
  serialization, backend identity change, or extra state to render every variant.
- `apps/arkscope-web/src/settings/SecResearchPanel.test.tsx`: one real panel
  regression uses the existing mocked-fetch boundary and actual panel, API
  helpers, Tabs, and React reconciliation. It checks all displayed cell values
  and row order/counts through 20 -> 1 -> 20 -> 1, retains both same-filing
  10-K/10-Q variants and the conflict gap, preserves the opaque cursor and limit,
  and checks zero console.error calls. Back and subsequent forward navigation
  make no new requests, even after the fixture's latest result changes.
- Scratch writes only: this report and five new `final-fix-*` runner directories
  containing command metadata, output logs, and isolated HOME directories.

Tracked diff: **2 files, 53 insertions, 1 deletion**. No observation was dropped
or deduplicated. Numeric rendering, exact fact strings, backend semantics,
pagination/cache logic, styles, and package metadata are unchanged.

## Verification

Each run below contains its exact argv, closed environment, cwd, exit code, and
duration in `command.json`, plus unabridged stdout/stderr in `output.log`.
Paths are relative to this report's directory.

| Artifact | Result |
| --- | --- |
| `final-fix-baseline/` | Exit 0; original panel suite, 39 passed. |
| `final-fix-red/` | Exit 1; 39 passed, new regression failed. |
| `final-fix-green/` | Exit 0; panel 40 + API 5 = 45 passed, 2 files. |
| `final-fix-inverse-old-key/` | Exit 1; 39 passed, regression failed again. |
| `final-fix-restored-green/` | Exit 0; panel 40 + API 5 = 45 passed, 2 files. |

RED ran before any component change. It observed **20 -> 2 -> 21 -> 3** DOM rows
instead of 20 -> 1 -> 20 -> 1, wrong cell content from stale conflict rows, and
three duplicate-key console errors. Soft row assertions deliberately expose all
three bad transitions in the same regression. This was a behavioral assertion
failure, not a runner/import/dependency failure.

The inverse removed only this dispatch's renderer change, restoring the component
byte-for-byte to its original SHA-256 while keeping the new test. It produced the
same row-count/content and duplicate-key failures. Reapplying the fix restored
both GREEN hashes, followed by a fresh passing focused run. GREEN/restored logs
have no stderr, React warnings, or assertion failures; existing i18next stdout
remains. `git diff --check` passed and `git diff --cached --name-status` was empty.

Runner prefix, from the named worktree:

```text
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-sec-query-settings/run_checks.py
```

Arguments for baseline/RED/inverse:

```text
<artifact-name> frontend test -- src/settings/SecResearchPanel.test.tsx --no-cache
```

Arguments for GREEN/restoration:

```text
<artifact-name> frontend test -- src/settings/SecResearchPanel.test.tsx src/secResearchApi.test.ts --no-cache
```

The established runner uses Node 22.14.0 from the supplied path, existing
node_modules, isolated HOME, `TZ=Asia/Taipei`, and `offline_node.cjs` to reject
real TCP/DNS/UDP. No installs or live App/provider calls were made.

## Restoration Hashes

SHA-256 values were read before edits, after RED, before inverse, at the original
key inverse, and after restoration. Source/test hashes at final handoff match
the first GREEN run.

```text
SecResearchPanel.tsx: original = RED = old-key inverse
411341e410cb0ecc2f2a2dd11892072c117aab1b4921181c68eab7626b5a22dd

SecResearchPanel.tsx: GREEN = restored final
7b018e561c6777814cc4dfe6bf33702dfe5fce9ac981b5598210438d6f0702d1

SecResearchPanel.test.tsx: original
e03d373d5a3035083a935207a98768612471bd9f46fe6d7772e55b6a48881b47

SecResearchPanel.test.tsx: RED = GREEN = inverse = restored final
c2cd1581cbcb1754f4ce06b3457f2cca7bef7c90df5a01243eaf3bdfdc0b833c

Linked-worktree index: before = after
e8784b8a249b24bade31e0649f4263cbd50648d234f7c491fd2119800b96cb07
```

Index path:
`/mnt/md0/PycharmProjects/ArkScope/.git/worktrees/arkscope-listing-sec-macro-convergence/index`.
All Git inspection used `GIT_OPTIONAL_LOCKS=0`; no add/reset/checkout/commit,
branch mutation, merge, or push was performed.

## Limits And Parent Gates

- Honored the parent's temporary component-edit hold. The parent finished its
  real HTTP/store browser RED before this dispatch's component edit; its log
  `browser-conflict-red/output.log` was read and confirms expected 1 vs actual 2
  rows. This report does not claim that run as this worker's own execution.
- No parent browser scripts, reports, other task files, or unrelated work were
  changed. No backend files, production data/config/credentials, or main-repo
  implementation files were written.
- Parent owns scoped re-review and fresh full frontend/typecheck/i18n/browser
  verification. This worker ran only the focused panel/API checks above; it did
  not launch a server, rerun a browser, or repeat backend/full-suite checks.
- Parent reported its sealed backend result: 8811 passed / 12 skipped, exact
  8823 execution/collection, +377/-0 nodes, and all 1088 pre-fix source paths
  reconciled. No backend delta is introduced here. The parent retains ownership
  of the post-fix frontend-only source-delta certificate and full-batch closeout.
- Page-local catalog keys rely on this table remaining stateless/read-only.
  Editable row state would require revisiting render identity, not changing
  stored filing identity or dropping supported variants.

## Authorized Commit

Parent subsequently granted sole index permission for the two frontend files.
This entry supersedes the pre-permission handoff's awaiting-commit status; the
earlier no-index statements and index hash describe that earlier checkpoint.

- Commit: `5d03c57e403386edca93529322f7c62a39571cc7`.
- Message: `fix(sec-research): preserve conflicting catalog rows across pages`.
- Committed only `apps/arkscope-web/src/settings/SecResearchPanel.tsx` and
  `apps/arkscope-web/src/settings/SecResearchPanel.test.tsx`.
- Commit diff: 2 files, 53 insertions, 1 deletion. Staged scope was checked
  before commit; `git diff --cached --check` passed. No other files were staged
  or committed, and no merge/push/worktree cleanup was performed.
- Fresh pre-commit focused verification in `final-fix-commit-green/` passed:
  **45 tests, 2 files, exit 0** using the same closed runner and `--no-cache`.
  Exact argv/environment/result and output remain in its command.json/output.log.
- Source and test SHA-256 values before and after commit match the frozen GREEN
  hashes above. No source/test edits occurred after the freeze signal.
- `git status --short --branch --untracked-files=normal` after commit showed
  only the branch header, with no tracked worktree or staged changes.
- Parent reported its post-fix certificate: exactly two frontend paths changed
  and all 798 backend paths unchanged. Parent full frontend/browser verification
  remains parent-owned; this commit does not change the bytes under those runs.

The commit hash was reported to the parent before this report-only append.
The scratch report is not part of the commit. Sole index use is finished.
