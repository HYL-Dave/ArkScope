# Task 2 Review

## Spec Compliance

**Verdict: PASS for the scoped implementation.** No missing, extra, or misunderstood product requirement was found. Process-evidence limits are stated below.

- Reviewed the supplied requirements, implementer report, and complete 17-file patch for `8c8ac7383d7e04defebaf803fc6a8fa7328cc879..5d41f570330e63a5942835f2ae39ca3cf5d9dcc7`, in that order. The supplied review package is the revision authority; no git commands were run.
- Exact serialization and digest expressions are preserved: `src/lifecycle_journal_codec.py:7` keeps the keyword-only `ensure_ascii=True` argument; line 8 retains `sort_keys=True`, compact separators, the supplied ASCII mode, and `allow_nan=False`; line 12 retains SHA-256 over the default canonical rendering's `.encode()` bytes. These match the removed implementations in the patch, including default UTF-8 encoding and exception behavior.
- All nine product consumers use unaliased public imports directly from the neutral owner. The old helper definitions are deleted from `src/lifecycle_web_store.py`; the patch adds no `_json`/`_sha` aliases or forwarders. The six existing test consumers change only helper imports and references; all new tests are in `tests/test_lifecycle_journal_codec.py`.

| Product Consumer | Direct Import | Reviewed Change |
| --- | --- | --- |
| Current store | `src/lifecycle_investigation/store.py:14` | Header, step, source, result serialization and integrity digests |
| Adoption | `src/lifecycle_investigation/adoption.py:16` | Observation and passage digests |
| Agent | `src/lifecycle_investigation/agent.py:23` | Prompt and repeated-action digests |
| Target | `src/lifecycle_investigation/target.py:15` | Preflight digest creation and comparison |
| Migration | `src/lifecycle_investigation/migration.py:9` | Existing canonical snapshot and approval digests |
| Disposal | `src/lifecycle_investigation/disposal.py:17` | Existing scope, approval, and receipt codec calls |
| Retained journal | `src/lifecycle_web_store.py:14` | Header/result integrity and serialization; page rendering |
| Review/confirmation | `src/lifecycle_web_review.py:14` | Passage digest and accepted-packet serialization |
| History | `src/ticker_identity_history.py:10` | Bound JSON and passage digest comparisons |

- Retained-page rendering still explicitly uses `ensure_ascii=False`, while `_page_material_digest(material)` and `_capture_digest(page)` remain separate and unchanged (`src/lifecycle_web_store.py:213`, `:216`). Current and retained reader call sites retain their original comparisons and error handling; only the codec name changes (`src/lifecycle_investigation/store.py:51`, `src/lifecycle_web_store.py:110`, `src/ticker_identity_history.py:121`).
- Error ownership is preserved: the current store still imports `WebJournalError` from `src.lifecycle_web_store` (`src/lifecycle_investigation/store.py:16`), and the retained store still obtains it from `src.lifecycle_web_schema` (`src/lifecycle_web_store.py:16`). The patch does not alter `safe_code` classification or add exception wrapping in the codec.
- Unrelated algorithms and schemas remain outside the edit: migration keeps its row/cell hashing (`src/lifecycle_investigation/migration.py:19`), disposal keeps `_sha_file` (`src/lifecycle_investigation/disposal.py:268`), and history keeps raw quote hashing (`src/ticker_identity_history.py:159`). No schema file, DDL, reader SQL, unrelated codec, parent plan, or inventory artifact is changed in the supplied patch.
- Required literal tests cover nesting, recursive sorting, compact separators, ASCII and control escaping, non-ASCII UTF-8 rendering, fixed SHA-256 values, and scalar/nested NaN and both infinities (`tests/test_lifecycle_journal_codec.py:11`, `:58`, `:64`, `:69`, `:81`). Saved evidence corroborates RED, GREEN, mutation detection/restoration, and 41 additions with no baseline-node loss.

## Strengths

- The neutral owner has only standard-library dependencies and two small functions, with no compatibility layer or new abstraction (`src/lifecycle_journal_codec.py:3`, `:7`, `:11`).
- Literal byte strings and digest constants provide an independent expected-value boundary instead of testing only writer/reader agreement (`tests/test_lifecycle_journal_codec.py:11`, `:58`, `:64`).
- Existing tamper-detection and retained Unicode-page tests keep their assertions and database behavior; edits are limited to the moved names (`tests/test_lifecycle_source_capacity.py:47`, `tests/test_lifecycle_source_context.py:122`, `tests/test_lifecycle_web_gaps.py:146`).

## Findings

### Critical

None.

### Important

None.

### Minor

**M1: The import-boundary test does not enforce absence of legacy helpers.** `tests/test_lifecycle_journal_codec.py:102` collects direct neutral imports and line 112 only requires that the expected names are present. Reintroducing `_json = canonical_json` / `_sha = digest_json` in the old owner would leave this test and the public-function ownership check at line 51 satisfied. Likewise, an unused neutral import would satisfy this assertion even alongside legacy helper use. The current patch has neither problem, so this is a nonblocking regression-coverage gap, not a present spec violation. Add focused negative AST assertions against legacy helper definitions/aliases and imports to protect the explicit no-forwarders requirement.

## Quality Assessment

**Verdict: APPROVED, with nonblocking Minor M1.** The changed behavior is confined to ownership and naming, and the serializer/digest expressions are identical to the removed implementations. No current correctness regression or blocking maintainability issue was found in the scoped patch.

## Evidence Checked

- Independently parsed all nine saved JUnit XML files with standard-library `xml.etree.ElementTree`, compared `(classname, name)` identities, and checked counts against the report. This was artifact inspection, not application import or test execution. The command used clean `env -i`, the report's PATH, `PYTHONDONTWRITEBYTECODE=1`, and `/home/hyl/.virtualenvs/llm_app/bin/python -B -c`.

| Saved Artifact Under `task2-state/artifacts/` | Observed Result |
| --- | --- |
| `baseline.xml` | 266 setup errors, all identified as FileNotFoundError; not a successful baseline |
| `baseline-green.xml` | 308 tests, no failures/errors/skips |
| `codec-red.xml` | 41 failures: 32 ModuleNotFoundError and 9 direct-import assertions; no setup/collection errors |
| `codec-green.xml` | 41 tests, no failures/errors/skips |
| `regression-green.xml` | 349 tests, no failures/errors/skips |
| `mutation-ascii-red.xml` | 5 failures: 2 literal-byte, 2 literal-digest, 1 explicit UTF-8/invariant-digest test |
| `mutation-ascii-restored.xml` | 41 tests, no failures/errors/skips |
| `mutation-separators-red.xml` | 11 failures: 5 literal-byte, 5 literal-digest, 1 explicit UTF-8 test |
| `final-restored-green.xml` | 349 tests, no failures/errors/skips |

- The final XML contains all 308 baseline identities plus exactly 41 new codec identities, with no duplicates or removals. Additions are 1 owner check, 6 byte cases, 6 digest cases, 1 explicit UTF-8 case, 18 nonfinite-number cases, and 9 direct-import cases. Artifact timestamps are consistent with the reported baseline/RED/GREEN/mutation/restoration order.
- Read `task2-state/artifacts/mutation-ascii.patch:5` and `mutation-separators-context.patch:12`: the former changes only the ASCII default, the latter only separators. Neither mutation was applied or replayed during this review. The reported intermediate fixture-directory and minimal-context patch issues are disclosed and followed by successful saved evidence (`task2-report.md:98`, `:111`, `:119`, `:210`).

## Outside-Diff Checks

- **R1, overlooked consumer after private-helper removal:** performed one symbol-focused `rg` scan for `lifecycle_web_store`, `_json`, and `_sha` in Python files under `src` and `tests`, with changed-file exclusions. No remaining reference to the removed journal helpers was found in the searched source/tests. Remaining matches concern journal classes/errors/constants or other helpers and JSON aliases; those implementations were not opened. For example, retained store/error imports remain at `tests/test_lifecycle_web_store.py:20` and `tests/test_lifecycle_source_progress.py:24`. The command also named `scripts`, which does not exist, so it returned exit 2 while still returning `src`/`tests` results; no scripts coverage is claimed. This is a static named-reference check, not proof against constructed dynamic lookups or external consumers.
- **R2, report accounting or mutation evidence could mask missing tests or unrestored drift:** inspected only the named Task 2 XML/mutation artifacts as described above. All 12 reported artifacts were located. An initial `rg --files` listing returned no paths because the scratch artifacts are ignored; the explicit `--hidden --no-ignore` listing resolved that lookup. No test suite was rerun to regenerate evidence.
- No unchanged implementation file was opened for a broader review. No changed file was reread in full outside the supplied diff. Parent-owned data inventory was not inspected and is not part of either verdict.

## Test And Evidence Limits

- No pytest run, synthetic test, source import, network request, production DB access, `.env`/credential access, App startup, or subagent dispatch occurred in this review. Static equivalence and the saved focused/regression evidence left no concrete runtime doubt requiring a new synthetic test.
- The report's backend commands specify the required offline runner, clean environment, isolated `task2-state` workspace/TMPDIR, and distinct pytest roots (`task2-report.md:108`, `:116`, `:124`, `:172`). Their execution isolation and source bytes at each historical run are not independently proven by the diff or XML. The TDD ordering and lack of production activity remain historical claims supported, but not authenticated, by those artifacts.
- The XML files contain no captured stdout/stderr streams. They establish reported node outcomes, not pristine console output; warning-free terminal output cannot be independently confirmed. No warning is reported in the supplied implementation report.
- This is a Task 2 gate, not a whole-branch, full-suite, live-provider, production-data compatibility, or inventory sign-off. The review used the supplied commit package without rereading git state. The only review write is this requested scratch report; no source, index, HEAD, branch, test, plan, or evidence file was modified.
