# SEC Retention Inventory And Helper Cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Use RED-first owners and scoped review checkpoints.

**Goal:** Measure the actual SEC/lifecycle retention boundary without reading private payloads, then remove obsolete HTTP entries and the current code's dependency on the old journal's JSON helpers.

**Architecture:** Production access is a one-time statistics-only inspection, not a disposal operation. Current and historical digests keep identical bytes while acquiring a neutral codec owner. Delete only the five HTTP handlers already identified by the census, retaining any underlying tool/history consumer.

**Tech Stack:** Python/SQLite, FastAPI, pytest, repository census.

**Spec:** `docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md` sections 3/9/11; `docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/sec-schema-ownership.md`; user's explicit approval of the two-store statistics-only read.

## Global Constraints

- Existing isolated branch `codex/listing-sec-macro-convergence`, base `6ba563d9`.
- Production permission: only named `profile_state.db` and `market_data.db`, read-only structure/count/reference aggregates. No credential value, body, URL, model prose, unrelated settings value or whole-row hashing.
- No production write/DROP, backup copying private contents, provider call, App restart, merge or push. Statistics do not authorize subsequent deletion.
- No spent operator CLI in product source. Archive this bounded query and its synthetic privacy tests as non-executable evidence after use.
- Preserve current investigation, provider confirmation, tools, routes selected by users, historical receipt/digest readers, prices/news/SA, credentials and membership removals.
- Current schema conversion and the new SEC three-tool service remain separate. No empty/retired compatibility handlers.

## Task 1: Authorized Actual-Store Inventory

- [x] Create an ignored one-time stdlib SQLite inspector plus synthetic tests. Open both exact files with `mode=ro` and `query_only`; explicit read transactions; no `immutable=1` that ignores live WAL. A SQLite authorizer rejects writes, payload columns and arbitrary table reads.
- [x] Test nonempty versus absent tables, composite/nullable FK counts, unknown external references, body/credential read rejection, denied writes and cross-store source membership statistics. Test malformed/changed schema returns an explicit gap, never zero.
- [ ] Obtain production allowlisted table/column/PK/FK/index/trigger metadata, counts and retained-reference aggregates. Exact old schedule keys may be counted, never their values. Aggregate source equality inside SQLite; do not return symbol/ref identifiers. **Unavailable: the single approved read could not open the stores under the nonwritable filesystem boundary. No actual counts were obtained.**
- [x] Attempt once only after synthetic checks and query review. Record failure phase and reviewed query digest; no repeated/unprotected read or fabricated cross-store snapshot. The caller used `bwrap` with read-only root and only plan scratch writable. Requested user clarification before any SQLite WAL/SHM coordination writes.
- [x] Archive query, synthetic tests, independent review and the unavailable attempt. This is failure evidence, not a completed retention manifest or approval to delete data.

## Task 2: Neutral Canonical Journal Codec

Files: new `src/lifecycle_journal_codec.py`, `tests/test_lifecycle_journal_codec.py`; exact `_json`/`_sha` consumers in old/current journal, adoption/review/history/migration/disposal and their tests.

- [x] RED: test the neutral module exists and current consumers no longer import codec functions from `lifecycle_web_store`. Byte fixtures must cover nested key sorting, compact separators, ASCII escaping, `ensure_ascii=False`, UTF-8 SHA-256 and rejection of NaN/Infinity.
- [x] Move the existing implementation, without changing serialization or digest semantics:

```python
def canonical_json(value, *, ensure_ascii=True):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=ensure_ascii, allow_nan=False)

def digest_json(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()
```

- [x] All consumers import the new owner directly; remove old definitions, do not keep forwarding functions. Keep unrelated codecs and schema digest algorithms untouched. Do not move `WebJournalError` or alter error classification in this task.
- [x] Run codec/current store/adoption/review/history/disposal tests and old retained-journal integrity controls. Mutation-check ASCII policy or separator drift against a literal byte/digest owner. Commit `5d41f570`: 349 passed, 41 added/0 removed, scoped spec/quality approval. Follow-up `58e1929b` adds two negative-export nodes and strengthens nine import/use owners; parent fresh 43 passed. Scoped M1 re-review passed with no remaining findings.

## Task 3: Remove Five Unused HTTP Entries

Files: `src/api/routes/security_lifecycle.py`, `src/api/routes/ticker_identity.py`, exact route-only DTO/imports and affected API/current-review/translation tests. Remove `src/security_lifecycle_translation.py` and its exclusive store methods after the last HTTP caller disappears. Do not delete the current tool methods with similarly named methods.

The five entries are:

```text
GET /security-lifecycle/cases/{case_id}/audit
GET /security-lifecycle/reviews/{review_id}
POST /security-lifecycle/evidence/{evidence_id}/translations
POST /security-lifecycle/cases/{case_id}/automation/run
GET /security-lifecycle/review-confirmations/{transition_id}
```

- [x] Reconfirm source/tool/operator callers. RED: actual App inventory excludes these exact method/path pairs, while current target/confirmation/history routes and remaining global automation action stay present.
- [x] Remove the handlers and exclusively used DTO/imports. Shared review, case audit or receipt services with actual current consumers remain. Source inspection found no other runtime consumer of `security_lifecycle_translation`: remove that module, `_translate_evidence_text` adapter and the store's exclusive `get_evidence_translation`/`assert_translation_write_available`/`save_evidence_translation` methods. Keep the shared `content_translation_failures`, AI-card/content translation feature and historical translation schema/data until separately approved disposition. No placeholder routes or redirects.
- [x] Delete route-only tests; move any unique test of retained service integrity to its real owner before removing the route. Preserve all current write permissions, confirmation and reversal checks.
- [x] Account for `tests/test_security_lifecycle_translation.py`, its standalone caller in `test_security_lifecycle_tools.py` and the obsolete adapter authority case in `test_card_execution_authority.py`. Preserve the tools test's live stored-translation provenance/no-text assertions by seeding its historical row directly; `list_evidence` still reads those rows and is not removed. Existing shared translation/model-routing tests must continue to pass; a deleted old adapter does not justify weakening active card/translation authority.
- [x] Update both whole-App route counts only after measuring the final route inventory. Measured exactly five (221 to 216), not a relaxed minimum. Restoring the old confirmation registration kills its named absence owner.
- [x] Run whole API file and affected lifecycle/identity/tool suites; `0c5896a5`: 962 passed, 24 nodes removed/11 added, including six preserved-owner renames. Initial scoped spec/quality review passed.
- [x] Follow-up `e61accaf` removes the tests-only `TickerIdentityService.get_review_confirmation`, moves six test readbacks directly to the live `security_lifecycle_review._result`, preserves all assertions and adds a mutation-verified absence owner. `_result` and `confirmation_for` are unchanged. Ten complete affected files: 293 passed. Scoped re-review passed spec/quality with no new issue; the earlier full run is not claimed to cover this later fix.

## Task 4: Integration And Remaining Work

- [x] Run relevant whole-backend regression and final collection accounting, frontend tests/typecheck for preserved clients, plus mechanical census against the original baseline. Frozen `0c5896a5` whole backend: 7,971 passed/12 skipped, 7,983 unique IDs. Frontend 1,692 passed/typecheck/build passed. Post-facade `e61accaf`: 293 passed in ten complete affected files; exact final collection 7,984, no uncovered IDs in the version-labelled combined accounting. Census stays exit2. Initial failures/coverage reductions remain distinct; no baseline rewrite to green.
- [x] Update ownership/audit/priority map with actual measurement limitations, source verification counts, remaining source/schema dependencies and the next disposal approval boundary. No claim of complete repo cleanup or implemented SEC research.
- [ ] Final independent review, archive reports, preserve branch without integration. Keep this plan's pending-read handoff while actual-store inventory is unavailable; remove its scratch only after the remaining task is completed or explicitly transferred, never sibling workspaces.

## Preflight

Task1 is independent of source edits and blocks only a data-disposal decision, not Tasks2/3. Task2 changes shared byte ownership, not schema. Task3 must preserve tool-level `get_current_review`/case audit consumers and the current provider confirmation path; absence of a frontend URL is not proof the underlying service is dead. Task4 reconciles all collateral; exact tests may decrease only with named removed behavior. No task invokes the broad disposal preview or migration snapshot under statistics-only authorization.
