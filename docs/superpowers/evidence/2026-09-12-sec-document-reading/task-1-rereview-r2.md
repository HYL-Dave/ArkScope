# Finding Verdict

- **R1-1: Case-conflated XHTML namespace identity - ADDRESSED.** `_DocumentXHTMLParser` obtains original QName and declaration spelling from the source token before binding/lookup, while retaining the parser-decoded attribute values (`src/sec_research/document_text.py:212`, `:229`). Distinct `ix`/`IX` declarations therefore no longer collide or rebind each other. Real and synthetic closing paths preserve the original QName for stack matching and namespace-delta restoration (`src/sec_research/document_text.py:233`, `:239`, `:248`).
- **Reproducer evidence:** the two unchanged reviewer probes have passing, self-closing testcase records in `task1-fix-r2-green-core-01/results.xml:1`, under `test_rereview_r1_prefix_case_probe`. Their retained pre-fix run shows the original hidden-content leak and false duplicate rejection (`task1-fix-r2-red-review-probes-01/output.log:3`, `:11`, `:37`). The product tests extend both cases to ix/IX, fact/Fact, and F/f with independent ElementTree expanded-name assertions (`tests/test_sec_research_document_text.py:129`).

## New Breakage In The Fix Diff

- **None found.** Inspected the complete supplied `task-1-fix-r2-diff.txt` once, in two non-overlapping ranges, for `6cad56cf..b07eba2b`. The change remains limited to the extraction module and its tests (`task-1-fix-r2-diff.txt:6`). No Critical, Important, or Minor fix-induced finding remains.
- **QName/display separation:** case-insensitive skip/break/void membership is isolated in `_HTMLDisplayNames`; structural and namespace names remain case-sensitive. Normalized presentation attributes still reach the shared helper (`src/sec_research/document_text.py:145`, `:196`, `:203`, `:231`). New tests cover local/declaration-name case, nested restoration, mismatched-case closes, self-closing elements, and existing tolerant display controls (`tests/test_sec_research_document_text.py:165`, `:182`, `:200`, `:209`, `:217`).
- **Named dependency risk checked:** original-token reconstruction and end-tag callback routing agree with the installed stdlib implementation. Its start-tag loop uses the same matchers and preserves decoded attribute values in token order; real end-tag callbacks occur after the same QName matcher, while synthetic closes are handled explicitly by the new subclass (`/usr/lib/python3.10/html/parser.py:435`, `:501`, `:532`; `src/sec_research/document_text.py:220`, `:233`, `:239`). No unanswered concrete doubt remained, so no new probe or test run was necessary.
- **Budget/scope preservation:** source-token work ticks before scanning and per attribute; temporary declarations are confined to the current bounded token. The change continues using declaration deltas and the existing nesting/markup/text/event guards, not inherited-map copies (`src/sec_research/document_text.py:145`, `:214`, `:220`, `:240`). Resource cases cover case-distinct prefix pairs, alternating QName scopes, cancellation, exact nesting admission, and typed limit failures (`task-1/test_fix_r2_resource_probe.py:13`, `:47`, `:64`, `:70`).
- **Interface/version check:** the XHTML MIME alone selects the refinement; other extraction paths, public signatures, section indexing, and the shared lifecycle reader have no corresponding behavior changes in this diff. Extraction version is v3 (`src/sec_research/document_text.py:21`, `:357`). Newly persisted extraction must carry that version; this review makes no downstream storage/integration claim.
- **Residual dependency:** the refinement intentionally uses installed stdlib lexical facilities. Parser-version upgrades should retain the token/chunk/QName controls. This is a documented compatibility dependency, not a blocking defect in the reviewed fix (`src/sec_research/document_text.py:5`, `:216`, `:222`, `:241`).

## Evidence Checked

- **Retained passing runs, inspected rather than rerun:** core **174P** (169 Task 1 nodes plus five supplied review probes), relevant regression **1201P**, resources **19P**, precommit **182P**. Raw evidence: `task1-fix-r2-green-core-01/output.log:5`, `task1-fix-r2-regression-01/output.log:19`, `task1-fix-r2-probe-01/output.log:3`, `task1-fix-r2-precommit-01/output.log:5`. These logs show no warnings.
- **Five inverse records and logs inspected:** declaration case **9F** (`task1-fix-r2-inverse-declaration-case-01/output.log:206`); start QName **4F** (`task1-fix-r2-inverse-start-qname-01/output.log:105`); real end QName **4F** (`task1-fix-r2-inverse-end-qname-01/output.log:95`); synthetic end QName **2F** (`task1-fix-r2-inverse-empty-qname-01/output.log:27`); token-work budget/cancellation **2F** (`task1-fix-r2-inverse-token-work-01/output.log:15`). Mutation identities and restoration records are retained in `task-1/fix-r2-inverses.json:1`; this reviewer performed no mutation.
- **Fresh read-only hash check:** `sha256sum -c .superpowers/sdd/2026-09-12-sec-document-reading/task-1/fix-r2-before-inverses.sha256` returned **OK for all five scoped files**, exit 0. No git command, suite rerun, subagent, install, product/index/branch edit, provider request, or real data/environment/credential access was performed. Only this authorized scratch report was created.

## Out-Of-Scope Observations

- None. Previously closed I1/I2 and unchanged code outside this fix were not reopened.

## Verdict

- **Fix round: All findings addressed, no new Critical/Important breakage.** R1-1 is closed.
- **Spec status: Compliant within the reviewed fix scope. Task quality: Approved for fix round 2.** This is not a fresh whole-task or downstream integration approval.
