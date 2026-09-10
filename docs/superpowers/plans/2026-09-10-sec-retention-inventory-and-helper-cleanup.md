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

- [ ] Create an ignored one-time stdlib SQLite inspector plus synthetic tests. Open both exact files with `mode=ro` and `query_only`; explicit read transactions; no `immutable=1` that ignores live WAL. A SQLite authorizer rejects writes, payload columns and arbitrary table reads.
- [ ] Test nonempty versus absent tables, composite/nullable FK counts, unknown external references, body/credential read rejection, denied writes and cross-store source membership statistics. Test malformed/changed schema returns an explicit gap, never zero.
- [ ] Inventory allowlisted table names, column names/types, PK/FK/index/trigger metadata and counts. Count referenced/unreferenced cases, old/current accepted runs and retained transitions. Exact old schedule keys may be counted, never their values. Aggregate source equality inside SQLite; do not return symbol/ref identifiers.
- [ ] Run once against the authorized stores only after synthetic checks and query review. Record per-store observation bounds, source revision and query digest. Do not claim atomicity across independently changing databases or infer safe deletion from a count alone.
- [ ] Archive statistics, query, tests and interpretation. Review the evidence and explicitly separate zero rows from uninstalled/malformed structures.

## Task 2: Neutral Canonical Journal Codec

Files: new `src/lifecycle_journal_codec.py`, `tests/test_lifecycle_journal_codec.py`; exact `_json`/`_sha` consumers in old/current journal, adoption/review/history/migration/disposal and their tests.

- [ ] RED: test the neutral module exists and current consumers no longer import codec functions from `lifecycle_web_store`. Byte fixtures must cover nested key sorting, compact separators, ASCII escaping, `ensure_ascii=False`, UTF-8 SHA-256 and rejection of NaN/Infinity.
- [ ] Move the existing implementation, without changing serialization or digest semantics:

```python
def canonical_json(value, *, ensure_ascii=True):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=ensure_ascii, allow_nan=False)

def digest_json(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()
```

- [ ] All consumers import the new owner directly; remove old definitions, do not keep forwarding functions. Keep unrelated codecs and schema digest algorithms untouched. Do not move `WebJournalError` or alter error classification in this task.
- [ ] Run codec/current store/adoption/review/history/disposal tests and old retained-journal integrity controls. Mutation-check ASCII policy or separator drift against a literal byte/digest owner. Record accounting, commit and review.

## Task 3: Remove Five Unused HTTP Entries

Files: `src/api/routes/security_lifecycle.py`, `src/api/routes/ticker_identity.py`, exact route-only DTO/imports and affected API/current-review/translation tests. Do not delete the current tool methods with similarly named methods.

The five entries are:

```text
GET /security-lifecycle/cases/{case_id}/audit
GET /security-lifecycle/reviews/{review_id}
POST /security-lifecycle/evidence/{evidence_id}/translations
POST /security-lifecycle/cases/{case_id}/automation/run
GET /security-lifecycle/review-confirmations/{transition_id}
```

- [ ] Reconfirm source/tool/operator callers. RED: actual App inventory excludes these exact method/path pairs, while current target/confirmation/history routes and remaining global automation action stay present.
- [ ] Remove the handlers and exclusively used DTO/imports. Shared review, case audit, translation or receipt services with actual current consumers remain. No placeholder routes or redirects.
- [ ] Delete route-only tests; move any unique test of retained service integrity to its real owner before removing the route. Preserve all current write permissions, confirmation and reversal checks.
- [ ] Update both whole-App route counts only after measuring the final route inventory. Expected delta is exactly five (221 to 216), not a relaxed minimum. Mutation-check restoring one old registration kills its named absence owner.
- [ ] Run whole API file and affected lifecycle/identity/tool suites; record removed/added test identities, commit and review.

## Task 4: Integration And Remaining Work

- [ ] Run relevant whole-backend regression and final collection accounting, frontend tests/typecheck for preserved clients, plus mechanical census against the original baseline. Keep initial failures/coverage reductions distinguishable; no baseline rewrite to green.
- [ ] Update ownership/audit/priority map with measured counts, no-body read limitations, remaining source/schema dependencies and the next disposal approval boundary. No claim of complete repo cleanup or implemented SEC research.
- [ ] Final independent review, archive reports, preserve branch without integration. Remove only this plan's ignored scratch after evidence is committed.

## Preflight

Task1 is independent of source edits and blocks only a data-disposal decision, not Tasks2/3. Task2 changes shared byte ownership, not schema. Task3 must preserve tool-level `get_current_review`/case audit consumers and the current provider confirmation path; absence of a frontend URL is not proof the underlying service is dead. Task4 reconciles all collateral; exact tests may decrease only with named removed behavior. No task invokes the broad disposal preview or migration snapshot under statistics-only authorization.
