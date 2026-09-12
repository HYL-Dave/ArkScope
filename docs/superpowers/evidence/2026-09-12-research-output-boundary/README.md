# Shared Research Output Boundary Evidence

Status: implemented in an isolated branch; automated verification passed.
The fresh whole-branch independent review returned no verdict after
a platform safety error, so final approval remains open. This is not a SEC
feature release and the branch is not merged or pushed.

Base: `18d46062c30da87b30666b1ba0f290872a28fa7f`.
Product/test candidate: `ff7c4d753ab0868aaa07a330841e0dd1de96f72c`.
Branch: `codex/research-output-boundary`.
Worktree: `/tmp/arkscope-research-output-boundary`.

## What Changed

Execution-owned exact credential protection replaces diagnostic length/entropy
rules on successful research data. Registered result policies admit lossless
JSON/text before previews or reductions; malformed or credential-bearing data
fails with typed codes. Stateful streaming protection covers public events,
durable replay, scratchpad and producer output. Secondary compaction and model
catalog paths use the same captured-credential authority.

The diagnostic `_RULES`, model/auth/effort selection, allowlists, retry/timeouts,
SDK sessions, compressor budgets, dependencies and frontend are unchanged.
No SEC-specific exemption, provider call, real credential/production DB read,
install, schema change, merge, push or restart was performed.

This protects already-captured credentials and the bounded representations
documented in the design. It does not identify every unknown or arbitrarily
transformed secret. Exact matches coinciding with public data are still rejected.

## Verification Record

- Tasks 1, 2 and 3 each have independent task approval and retained fix rounds.
- `compaction-report.md` records the later concrete finding and local fix,
  including 17 new owners, RED/inverse evidence and 1,046 restored focused passes.
- `whole-branch-review-blocked.md` records the missing final independent verdict.
  Its completed historical probe demonstrated the old error-log leak; the probe's
  two passes are NOT passing security tests.
- Complete backend: `backend-full-04`, 10,166 passed / 12 skipped, zero failures
  or errors, 1,093.18 seconds pytest (1,097.131 seconds runner). This is one
  complete `-q tests` execution, not a sum of focused runs.
- `source-freeze-04.json` and `source-freeze-05.json` verify all 1,111
  product/test/frontend files, runner and runtime identities unchanged.
  `delivery-validation.json` independently parses JUnit: all 857 cases in the
  seven new suites ran with no skips. Seven retained safety-owner families
  also ran without skips, including key echo, retry/tracing, captured card
  selection and OAuth refresh. These are subsets of the complete total.
- The 12 skipped cases are unchanged manual live tests: two SEC EDGAR,
  nine IBKR scanner and one IBKR option-chain. None belongs to the new boundary.
- Frontend: `frontend-full-01`, 123 files / 1,776 tests passed;
  `frontend-types-02` typecheck exit 0. Frontend source is unchanged from base.
- `census-final-04/reconciliation.json`: zero new candidates, coverage reductions,
  dependency metadata changes or untracked-name drift. Eleven new uncertainty
  IDs are six test imports and five identical relocated literals. Exit 2 and
  `review_required` remain; this is not a claim to clean all legacy candidates.
- `parked-sec-status.md` explicitly owns the four other-worktree feature failures.

Counts from focused runs overlap. Do not sum them into a complete-suite claim.
`backend-full-01` was a wrong invocation that collected archived evidence;
`backend-full-02` found a new test-manifest omission subsequently fixed in
`d42f29ce`; `backend-full-03` was deliberately stopped before the compaction fix
(8,068 passed / 12 skipped, exit 2), not a complete pass. Preserve these records.

## Review And Reproduction

The final code-only packet `external-review.diff.gz` covers the exact base through
the product/test candidate. Uncompressed SHA256:
`2b0909ce9c2abc4651518116503ac23a541ee5ffcca472c8864856b3593c07c8`.
The earlier `final-review.diff.gz` and supplement are historical review inputs
and predate the compaction fix. No fresh independent approval is claimed for
the final packet. User/external review remains the next decision gate.

The archived runner files are exact copies. Their root derivation expects their
working location to be `<repo>/.superpowers/sdd/<plan>/`, NOT this evidence
directory. The original working scratch is retained while final review is open.
Commands are recorded per run; use a new create-only run name when reproducing:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py rerun-unique backend -q tests
```

The runner provides a closed environment and Python/Node audit hooks with
synthetic fixtures and loopback-only test transports; it is not an OS sandbox.
Existing local dependencies are reused. No package installation is required by
this slice. Resource/version identities are in the source-freeze files.

`manifest.json` binds each sealed file and its original uncompressed content.
`verify_evidence.py <evidence-directory>` verifies both hashes and the complete
file list. Logs, JUnit, patches and collectable probe files are gzip-compressed.
Only this plan's reports/commands/results are sealed; fixture DBs, token-store
fixtures, HOME/XDG trees, private files and other plan workspaces are excluded.

Final complete-backend JUnit SHA256:
`d0c9a9d978603a0c2f7d2fb94cfef345ff41aa03695bf1e1f69f06f8acf170ea`.
Tested source-collection SHA256:
`36af98c16502f53a9f96a90e8f86b35921a723b98c4ead5a87bf3ec0c47f86e8`.
