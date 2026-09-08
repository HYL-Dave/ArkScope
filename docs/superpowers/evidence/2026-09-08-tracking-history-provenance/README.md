# Tracking History Explanation Repair

Base: `4839c0f2962c0fa42108932d14eed64eed8d75be`.
Branch: `codex/tracking-history-provenance`.
Scope: the tracking-activity service projection and its bilingual UI.
No migration, production DB access, provider/App LLM calls, App restart, merge, or push.

## Contract

- History shows its linked explanation, evidence providers, assessment method,
  recorded model/auth channel when recoverable, and approval authority separately.
- New reviews use the approval's frozen packet, not the latest assessment,
  current provider lookup, current Settings route, or current model registry.
- Pre-packet reviews bind the assessment ID and evidence, but their fingerprints
  do not seal assessment prose, event date, or method. Those records explicitly
  show `legacy_assessment_unsealed`; the UI does not claim "No LLM used" for them.
  This repair cannot retroactively create an approval snapshot.
- Legacy provider evidence must match the approved observation fingerprint.
  Malformed unrelated envelopes are skipped, never substituted for that receipt.
- LLM identity comes from the bound journal header/result and completed calls.
  V2 cited metadata is bound by the approved passage digest. V1 source metadata
  is reconstructed with quotation byte offsets in SQLite and checked against the
  approved SourcePassage digest; full source bodies are not loaded into Python.
  This proves the displayed citation metadata, not a fresh revalidation of the
  complete source document. Damaged sources are not displayed as verified links.
- Publisher-date text remains the publisher's text. Event dates, observation
  timestamps, scheduled action dates, and receipt timestamps remain distinct.
- Missing explanatory material is explicit. This does not relax validity checks
  for transition/effect receipts or authorize a reversal of damaged state.
- Full explanation and sources expand locally. Acknowledgement and reversal
  retain their existing explicit commands and write guards.

## Verification

The code/test diff under `apps`, `src`, and `tests` was frozen for final verification:
`68d3f2dd827be17b10ef3f4f63ddd07d4f43293e4891f23d09a7c2177b151c96`
(`git diff --cached --binary -- apps src tests | sha256sum` against the base).

- New history backend contract suite: 25 passed.
- Affected backend suite: 246 passed across history, transitions/routes, provider
  review, both LLM review generations, current-review projection, and frontend contracts.
- Complete frontend suite: 1660 passed / 124 files.
- TypeScript/build and visible-literal checks passed. Vite retained its existing
  large-chunk advisory; no dependencies or build settings were changed.
- Final frozen full-backend run: 7139 passed, 12 skipped, 3 existing edgartools
  deprecation warnings, in 753.39 seconds. The frozen code/test digest was
  unchanged at completion.
- An earlier full run was discarded because review revisions changed fixtures
  after collection: 7126 passed, 12 skipped, 2 fixture mismatches. It is not the
  final release result.
- Playwright checked the real InvestigationView and API parsers using synthetic
  responses in English and Traditional Chinese at 1280x960 and 390x844. Both
  collapsed and expanded history were checked: 3 rows, 6 provider source links,
  no page errors or horizontal overflow. Only the three mocked GET endpoints
  were called; expanding details made no additional request or write.
- Offline HTML previews were also checked with JavaScript disabled: expandable
  details work, every command is disabled, and no external request is made.

The fixtures are synthetic, including the ARCH/LTHM/TA-shaped legacy tests; no
production records were copied. The complete API fixture and separate provider/LLM
decision fixtures are owned by real persisted SQLite workflows and consumed by
the frontend parser tests. The LLM fixture includes non-ISO publisher-date text.

## Review And Mutation Owners

Independent review found four issues in the initial implementation. They were
reproduced and addressed: unsealed legacy assessment claims, publisher-date
producer/parser mismatch, malformed unbound provider envelopes, and unbound v1
Web metadata. A final follow-up also removed categorical LLM non-use claims for
unsealed legacy records, with a separate positive control for sealed provider reviews.

Three process-local mutations were run without editing the frozen source files:

| Mutation | Owning test | Observed result |
| --- | --- | --- |
| Bypass the v1 approved passage digest | `test_legacy_web_source_metadata_must_match_the_approved_passage_digest` | 4 failed |
| Remove the legacy qualification | `test_unsealed_legacy_assessment_is_qualified_even_when_its_fingerprint_still_matches` | 1 failed |
| Show "No LLM used" for unsealed legacy rows | `shows legacy reason, evidence and approval without inventing LLM use or non-use` | 2 failed, one per locale |

The ordinary history suites passed again after the mutation processes exited.

## Attended Check After Merge

1. Open Tracking Changes. Verify ARCH/LTHM/TA retain their removal receipts and
   show the linked explanation, original provider names, and human approval.
2. Expand a source list. Check its recorded listing state and observation time;
   absence from a directory must not be relabelled as independent proof of delisting.
3. On an LLM-backed receipt, check actual recorded provider/model/channel and the
   distinct human approval. Changing Settings must not rewrite that history.
4. Existing unsealed or missing metadata must remain visibly qualified. Merely
   opening or expanding history must not acknowledge or restore anything.
