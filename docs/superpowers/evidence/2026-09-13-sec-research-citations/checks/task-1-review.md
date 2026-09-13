# Task 1 Independent Spec And Quality Review

## Finding

### P2: Validate all native observation fields before projecting citations

Location: `src/sec_research/citations.py:171`, particularly the filing branch at
`:179` and fact branch at `:182`.

`_observation_shape` checks that the native fields exist, but validates only some
of their values. Starting with the real `evidence.facts` envelope, changing just
`data[0]["fiscal_year"]` to `True` passes every check and produces the original
`sec_citations`. Likewise, changing `data[0]["primary_document"]` to `{}` in
`evidence.filings` produces normal filing citations. These are JSON-serializable
but invalid native observations. This is a static control-flow finding, not a
claim that a reproduction was executed during this review.

The existing native contracts explicitly reject these values:
`src/sec_research/facts.py:67` requires a non-boolean integer fiscal year in
1..9999 or null; `src/sec_research/catalog.py:67` requires a literal document
basename or null. The citation validator also omits the fact start/end ordering,
nullable fiscal-period/frame checks, and filing report-date/acceptance-time and
primary-document/primary-URL consistency checks implemented by the native parsers
(`facts.py:63`, `facts.py:85`, `catalog.py:102`, `catalog.py:109`).

`sec_citations_from_envelope` calls this partial validator and then only extracts
provenance (`citations.py:278`). `citation_event_fields` consequently returns
ordinary references without `sec_citation_gaps` (`citations.py:359`). This violates
Task 1's explicit malformed-owned-evidence contract and can conceal a malformed
whole result behind a successfully reopening reference. It is not an arbitrary
fetch or an exact-read byte-verification bypass.

Required correction: validate the remaining native scalar and cross-field
constraints before projection, preserving legitimate nullable fields and actual
query annotations. Extend the real-envelope malformed-result tests with these
cases and assert both the closed `CitationError` and the event gap, with no
partial references. The current malformed-row owner only adds an incomplete row
(`tests/test_sec_research_citations.py:151`); it does not exercise malformed values
in otherwise complete native rows.

## Separate Verdicts

- **Spec: REVISE.** The malformed-owned-evidence requirement is incomplete as
  described above. The required Task 1 interfaces, closed reference unions,
  canonical HTTP route and closure outputs are otherwise present.
- **Quality: REQUEST CHANGES.** One concrete P2 finding. Relevant existing test
  evidence is substantial, but it does not protect the omitted native-field
  checks. No other blocking finding was established in this bounded review.
- **Recommendation/workflow label: `revise` / `revise`.** This is a Task 1 gate
  verdict, not a release or merge authorization.

## Checked Boundaries

- JSON duplicate/nonfinite rejection, whole owned wrappers and MCP blocks,
  conflicting structured content, closed reference fields and canonical query
  re-encoding: `citations.py:79`, `citations.py:131`, `citations.py:145`,
  `citations.py:293`. Unknown tools bypass parsing; valid no-reference envelopes
  remain valid. The finding concerns native row validation, not these controls.
- Exact source reads verify registered object bytes, snapshot identities,
  parsed native rows and pointers; document reads additionally verify retained
  catalog/directory metadata, original/text hashes and all UTF-8 boundaries:
  `references.py:55`, `references.py:85`, `references.py:180`,
  `references.py:195`, with `captures.py:102` and `document_store.py:38`.
- Closure expands receipt source snapshots and all document catalog sources,
  returns sorted identities, and fails on missing/corrupt reachable evidence:
  `references.py:138`, `references.py:215`, `references.py:255`.
- The removed cumulative byte/node caps have not been reintroduced. Snapshot
  payloads are processed one source at a time, and only compact metadata and
  required output identities survive: `references.py:117`, `references.py:131`.
  Exact reads do not expand unrelated receipt source objects:
  `references.py:148`, `references.py:160`, `references.py:215`.
- The citation GET validates its sole query argument before storage access and
  precedes the dynamic CIK route (`src/api/routes/sec_research.py:93`, `:110`).
  Success/unavailable reads have six fields (`citations.py:377`). No acquisition,
  latest substitution, configuration lookup or write call is introduced here.

## Evidence And Scope

Reviewed the Task 1 brief, focused plan/global constraints, parent Task 3 contract,
the immutable diff, and the finalized `task-1-report.md`. The diff was read once;
the tool truncated its rendered output, so only the omitted code sections were
recovered from exact-head file views. Dependency reads were limited to concrete
hash/metadata/JSON and native-observation-contract questions.

- Repository/worktree: `/tmp/arkscope-research-output-boundary`.
- Base: `f12663af147876a01784c9548c58cd541528585e`.
- Head: `899b4098731fbd570c7a46d9a6353f0b95889b2a`.
- Artifact: `task1-review.diff`, 73447 bytes.
- SHA-256: `e352db073266e097192377198727cbdfc6425e01c0b5e3fab7337f8eaca7ee5c`.
- Eight changed files; current hashes match all eight committed hashes in the
  implementer report. No source, index or HEAD writes were performed.

Existing command receipts and log summaries were inspected, not rerun:

| Receipt | Recorded outcome |
| --- | --- |
| `task1-baseline-01/output.log:9` | 491 passed |
| `task1-red-01/output.log:1449` | 103 failed, 81 deselected; intended missing behavior |
| `task1-self-review-red-01/output.log:475` | 10 failed, 17 passed, 91 deselected |
| `task1-self-review-green-01/output.log:5` | 208 passed |
| `task1-scale-red-01/output.log:45` | 4 failed, 5 passed, 7 deselected |
| `task1-scale-green-01/output.log:3` | 31 passed, 89 deselected |
| `task1-broad-green-01/output.log:24` | 1534 passed |

Assertions inspected include real-store relocation and forbidden acquisition
(`test_sec_research_citations.py:280`), hash/pointer/UTF-8 tampering (`:310`),
receipt reobservation (`:323`), closure identities and corruption
(`test_sec_research_references.py:14`, `:54`, `:86`), and compact processing plus
unrelated-receipt isolation (`:113`, `:148`). The scale owner is a synthetic
60-source memory regression, not a 100 GiB benchmark. Command receipts do not
independently freeze per-run source hashes; final-source correspondence relies
on the implementer report and matching committed hashes.

No tests, suite, test runners, subagents or provider/production access were used.
Only this requested review artifact was written. Event producers, persistence,
profile iteration and UI are later tasks and are not findings. The controller
owns fixes, re-review and the final suite.

## Structured Assessment

```json
{
  "schemaVersion": 1,
  "patch": {
    "repository": "/tmp/arkscope-research-output-boundary",
    "sourceType": "patch_file",
    "base": "f12663af147876a01784c9548c58cd541528585e",
    "head": "899b4098731fbd570c7a46d9a6353f0b95889b2a",
    "changedFiles": ["src/api/routes/sec_research.py", "src/sec_research/citations.py", "src/sec_research/references.py", "tests/test_api.py", "tests/test_sec_research_citations.py", "tests/test_sec_research_document_routes.py", "tests/test_sec_research_references.py", "tests/test_security_lifecycle_routes.py"],
    "sha256": "e352db073266e097192377198727cbdfc6425e01c0b5e3fab7337f8eaca7ee5c"
  },
  "recommendation": "revise",
  "workflowLabel": "revise",
  "impact": {"rating": "high", "rationale": "New public HTTP and serialized citation/maintenance contracts; impact rating describes the boundary, not the P2 finding severity."},
  "regressionLikelihood": {"rating": "high", "rationale": "Source-visible incomplete native-row validation admits malformed owned evidence."},
  "regressionProtection": {"rating": "partial", "rationale": "Relevant existing real-store and HTTP receipts pass, but no owner covers malformed values in complete native rows; per-run source hashes are not frozen in command receipts.", "exactHeadChecksPassed": false},
  "recoverability": {"rating": "easy", "rationale": "Task 1 is additive and read-only; no schema migration, source acquisition or maintenance mutation."},
  "confidence": {"rating": "high", "rationale": "Immutable identity and affected control flow verified; finding follows directly from native parsers and omitted checks, without executing subject code."},
  "applicability": {"status": "confirmed", "rationale": "The new citation HTTP route is live; projection and closure are explicitly required Task 1 public interfaces."},
  "statusQuoRisk": {"rating": "moderate", "rationale": "Without Task 1, exact durable reopening and later maintenance-root integration remain unavailable."},
  "autoMergeExclusions": ["public_contract", "other"],
  "affectedRuntimeRoots": ["GET /sec-research/citation", "citation_event_fields", "sec_reference_closure"],
  "importantCallers": ["stored_citation -> read_sec_citation -> _ReferenceReader", "sec_citations_from_result -> sec_citations_from_envelope -> _observation_shape"],
  "riskDrivers": ["Partial native observation validation", "Exact provenance and transitive closure contracts"],
  "protectiveFactors": ["No acquisition or writes", "Closed canonical reference unions", "Actual captured-byte verification", "Compact per-source traversal", "Relevant existing RED/GREEN receipts"],
  "materialBoundaries": [
    {"id": "owned_evidence", "invariant": "Malformed owned whole results produce typed gaps.", "runtimeRoot": "citation_event_fields", "counterexample": "A complete fact row with fiscal_year=true or filing row with primary_document={} passes citations.py:171 and produces references.", "legitimateControl": "Valid real-store nullable/native rows project references; facts.py:67 and catalog.py:67 reject the counterexamples.", "result": "contradicted"},
    {"id": "canonical_http", "invariant": "Only one bounded canonical reference reaches storage, with no acquisition target.", "runtimeRoot": "GET /sec-research/citation", "counterexample": "Duplicate ref, extra path, padded or noncanonical token rejected by route:93 and citations.py:145.", "legitimateControl": "Real retained document query accepted before dynamic CIK route; document route test:22.", "result": "supported"},
    {"id": "exact_bytes", "invariant": "Only exact retained bindings and UTF-8 ranges reopen.", "runtimeRoot": "read_sec_citation", "counterexample": "Hash, pointer and byte-boundary tampering rejected by references.py:85,180,195 and CaptureStore.read.", "legitimateControl": "Refresh/relocation and reobservation controls reopen exact retained bytes and Decimal TEXT.", "result": "supported"},
    {"id": "closure", "invariant": "Complete deterministic closure retains reachable objects without accumulating source payloads.", "runtimeRoot": "sec_reference_closure", "counterexample": "Missing/corrupt receipt members fail closure; aggregate source payloads are released at references.py:131.", "legitimateControl": "Real directory/catalog/fact closure and 60-source scale controls pass in existing receipts; exact reads do not expand unrelated source objects.", "result": "supported"}
  ],
  "validation": [
    {"name": "Existing baseline and Task 1 RED receipts", "status": "passed", "protects": "491 baseline passes and 103 intended missing-behavior failures establish the prior state."},
    {"name": "Existing self-review and scale RED/GREEN receipts", "status": "passed", "protects": "Recorded fixes address empty-document/MCP gaps, accumulated payload memory and unrelated source-object coupling."},
    {"name": "task1-broad-green-01", "status": "passed", "protects": "Recorded 1534 passing SEC and route-owner executions; inspected logs, not rerun."},
    {"name": "Malformed complete native-row regression", "status": "unavailable", "protects": "Required coverage for the static P2 finding is absent; reviewer ran no tests."}
  ],
  "unknowns": [{"summary": "Fresh final-suite verification and executable regression for the finding remain controller-owned; not reasons to defer the established revise verdict.", "decisionCritical": false}],
  "evidencePlan": []
}
```
