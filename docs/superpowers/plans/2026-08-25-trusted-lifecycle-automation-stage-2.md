# Trusted Lifecycle Automation Stage 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` for every behavior change and `superpowers:verification-before-completion` before each GREEN claim. This plan is executed in one isolated worktree without subagents.

**Goal:** Deliver the offline evidence/fact kernel for trusted lifecycle automation: exact profile schema authority and migration tooling, one shared fail-closed SEC transport, bounded SEC filing-chain acquisition, strict local-news and IBKR evidence adapters, and atomic typed evidence/fact persistence.

**Architecture:** Keep the reviewed design's authority boundaries explicit. Current V2 lifecycle/ticker schemas become the runtime authority while named V1 builders/verifiers remain only for prior migration/rollback reproducibility. A new migration module rebuilds the owned profile component transactionally and hashes only owned schema/rows, never mutable unrelated scheduler tables. All active app-owned SEC HTTP callers share one transport and installation-wide governor. Stage 2 acquires and validates evidence/facts but does not classify a case, accept an assessment, create an automatic proposal, mutate a universe, expose new UI, or run a scheduler.

**Tech Stack:** Python 3.10, stdlib `sqlite3`, `fcntl`, `threading`, `hashlib`, `json`, `requests`, existing IBKR gateway lock, pytest.

**Spec:** `docs/superpowers/specs/2026-08-24-trusted-lifecycle-automation-design.md`

## Status And Authority

- Product-grounding base is exactly `2dc8f4c17a48e689352f364f4a71275171fbf6c0` on `master`; `origin/master` matched that commit and the worktree was clean when Task 0 was recorded. Every line/SHA pin in the owned ledger is evaluated against this base.
- The implementation worktree must start from the later docs-only `master` tip that contains this plan and all five ledgers, not directly from the product-grounding base. Task 0 proves `2dc8f4c1` is its ancestor and that the intervening paths are only this plan/ledgers plus the Priority Map entry; this prevents a plan-authority bootstrap gap.
- Baseline backend collection is exactly `4294`. The focused Stage 2 pre-addition set is exactly `279` nodes.
- This plan adds exactly 54 backend nodes and removes none. Target collection is `4348`; target focused collection is `333`.
- Stage 1 Tavily retirement is complete. No executable Tavily route/tool/adapter may return.
- The user authorized continuous offline progress through Stage 2, with a schema-authority checkpoint before Stage 3.
- This plan does **not** authorize provider/network calls, production database reads or writes, live preflight/backup/migration/restore, app restart, merge, push, or rollback.
- Stop and amend before continuing on any product-semantic change, unexpected schema/data shape, unlisted changed path, unexpected test-node drift, or provider/live-path requirement.

## Mechanical Authorities

- Owned paths: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-2-owned-paths.tsv`
- Focused paths: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-2-focused-paths.tsv`
- Additions: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-2-additions.nodes`
- Evolved owners: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-2-evolved-owners.tsv`
- Protected paths: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-2-protected.paths`

Every changed non-governance path must appear in the owned-path ledger before its product edit. Every new test node must appear byte-for-byte in the additions ledger before collection. Existing node IDs are immutable. An extra failure, missing failure, changed parameterized ID, or collection mismatch is a B-class stop and docs-only amendment.

## Closed Stage 2 Vocabulary

The schema checkpoint reviews these literals, not paraphrases:

- evidence source families: `regulator`, `market_infrastructure`, `publisher`, `general_web`, `manual`;
- attended investigation-run adapters: `manual` only;
- trusted evidence adapters shipped now: `sec_edgar`, `internal_news`, `ibkr_contract`, `manual`; storage also reserves provider-neutral `hosted_search` for the separately reviewed later adapter, with no executable path in this stage;
- evidence kinds: `regulator_excerpt`, `market_infrastructure_snapshot`, `publisher_excerpt`, `hosted_search_citation`, `manual_url`, `manual_text`, `document_reference`;
- fact types: `source_ticker`, `successor_ticker`, `source_venue`, `destination_venue`, `effective_date`, `security_class`, `issuer_cik`, `transaction_structure`, `tracked_security_effect`;
- automation modes: `live`, `historical`;
- run statuses: `queued`, `running`, `succeeded`, `blocked`, `failed`, `cancelled`;
- decision tiers: `verified_automatic`, `review_suggested`;
- action readiness: `not_applicable`, `waiting_effective_date`, `waiting_market_confirmation`, `transition_eligible`, `action_blocked`;
- assessment authors: `human`, `legacy_review`, `automation`;
- automation methods: `deterministic_rule`, `model_assisted`;
- acceptance authorities: `human`, `automation_policy`, `legacy_migration`;
- transition approval authorities: `attended_user`, `automation_policy`.

Stage 2 stores the complete destination vocabulary but does not emit an automatic assessment, decision tier, proposal, transition, activity, or translation. Those writes begin in Stages 3-4.

## Schema Mapping Authority

### Existing rows

- Every V1 case, acknowledgement, proposal, receipt, outcome, and assessment-evidence row is copied without semantic reinterpretation.
- Every V1 `legacy_review` assessment maps to `acceptance_authority='legacy_migration'`; its four user-visible assessment fields and timestamps remain byte-identical.
- An accepted or superseded V1 `human` assessment maps to `acceptance_authority='human'`; a draft has `acceptance_authority=NULL`.
- All V1 rows have `automation_method`, `automation_run_id`, `rule_id`, `rule_version`, and `decision_provenance_sha256` as `NULL`. No migration invents automation history.
- Existing manual evidence maps to `source_family='manual'`; `manual_url`, `manual_text`, and `document_reference` retain their kind. Existing `adapter='manual'` remains `manual`.
- Any stored run/evidence with `adapter='tavily'` or kind `web_search_result|web_page_excerpt` blocks preflight. It is never silently dropped or relabeled.
- Existing ticker transitions map to `approval_authority='attended_user'`; automation policy/rule fields remain `NULL`. Current production was empty at the prior cutover, but migration must preserve any rows created before this cutover.

### Current exact authority

- `security_lifecycle_investigation_runs` remains the attended/manual acquisition history surface. Its trigger/adapter vocabulary evolves without recreating a Tavily executor.
- `security_lifecycle_automation_runs` owns durable automation identity, bounded blocker/query/diagnostic JSON, retry time, decision tier, action readiness, and timestamps.
- `security_lifecycle_automation_facts` owns cited normalized facts. Each row binds one evidence ID, half-open UTF-8 byte offsets that must land on code-point boundaries, exact cited-text SHA-256, rule ID/version, and canonical value JSON.
- `security_lifecycle_evidence` gains required source family, optional automation run, optional source-document digest/locator, and a dedupe key. The existing `content_sha256` remains the digest of the stored verbatim excerpt.
- `security_lifecycle_evidence_translations` is derived storage keyed to evidence hash/locale with provider/model/harness provenance; it is never referenceable by assessment evidence.
- `security_lifecycle_assessments` gains honest author/method/acceptance/run/rule/provenance columns with CHECK coherence.
- `ticker_identity_transitions` gains approval authority, optional automation policy/rule identity, and decision digest.
- `ticker_identity_transition_activity` is append-only storage for later applied/reversed visibility and explicit acknowledgement.

## Shared SEC Transport Authority

- All active app-owned SEC HTTP calls in `sec_edgar_source`, `sec_edgar_financials`, `sec_earnings_releases`, `sec_insider_trades`, `symbol_catalog`, and the explicit provider probe use `data_sources.sec_transport`.
- `data_sources/sec_filings.py` remains an explicitly dormant `edgartools` integration. Stage 2 neither advertises nor retires it. A static reachability test proves no active `src/` runtime imports it; adding such a caller requires a later design amendment because its network stack bypasses this transport.
- A process-wide `threading.Lock` plus strict `fcntl.flock` state file under `ARKSCOPE_LOCK_DIR` serializes request starts across threads/processes. Missing `fcntl`, unavailable lock directory, corrupt state, or unsupported clock state raises `sec_governor_unavailable`; no in-process-only fallback exists.
- The state file stores only a canonical UTC request-start timestamp. The lock is held while waiting and publishing the next start, then released before network I/O.
- Request starts are at least 200 ms apart installation-wide. Waiting never occurs inside a caller-owned SQLite transaction.
- Valid HTTPS hosts are closed to `data.sec.gov`, `www.sec.gov`, and `efts.sec.gov`. Missing or placeholder contact raises `sec_identity_unconfigured` before session invocation.
- Lifecycle budget is 16 attempts including retries, 12 documents, 1 MiB per document, and 12 MiB aggregate. A worker tick later admits at most two cases.
- HTTP 429 permits exactly one retry. `Retry-After` must parse to 0-30 seconds; otherwise fail `sec_rate_limited`. Budget exhaustion is `sec_request_budget_exhausted`.
- Diagnostics contain bounded integer counts/wait duration only; no URL, User-Agent/contact, response body, or exception text is persisted.

## Task 0: Baseline, Worktree, And Ledger Admission

**Files:** governance files only.

- [ ] On the main tree, verify `git status --short` is empty, `HEAD == origin/master`, and `git merge-base --is-ancestor 2dc8f4c1 HEAD` succeeds. Prove `2dc8f4c1..HEAD` changes only the six Stage 2 plan/ledger files and `docs/design/PROJECT_PRIORITY_MAP.md`.
- [ ] Verify every modify path's product-grounding line count/SHA-256 with `git show 2dc8f4c1:<path>` and verify every add path is absent at `2dc8f4c1`.
- [ ] Collect backend `4294` and the focused ledger `279`; compare exact node sets, not counts only.
- [ ] Confirm protected paths are byte-identical and no production path/provider is opened.
- [ ] Create `/tmp/arkscope-lifecycle-automation-stage2` on branch `trusted-lifecycle-automation-stage2` from the docs-only plan-authority tip, so the isolated executor has the literal ledgers it must enforce.

## Task 1: Establish Exact V2 Schema Authority

**Primary files:** `src/security_lifecycle_schema.py`, `src/ticker_identity_schema.py`, `src/security_lifecycle_investigation.py`, `src/security_lifecycle_manual_evidence.py`, `src/ticker_identity_transition.py`, `src/ticker_identity_service.py`, their schema/core tests.

- [ ] Add the six schema additions and evolve every named T1 owner before product edits. The exact-schema owners establish V2 authority; the investigation owners replace dormant Tavily vocabulary with the surviving attended/manual contract without weakening their original assertions.
- [ ] Run only schema/core nodes and record exact RED. Expected failures are missing tables/columns/vocabulary/coherence, never fixture SQL syntax.
- [ ] Preserve named `V1_PROFILE_TABLE_SQL`, `V1_PROFILE_INDEX_SQL`, `verify_v1_profile_connection`, `V1_IDENTITY_TABLE_SQL`, `V1_IDENTITY_INDEX_SQL`, and `verify_v1_ticker_identity_connection`; current unqualified builders/verifiers become V2 only.
- [ ] Implement all §Schema Mapping Authority objects and constraints. JSON columns are bounded and validated canonically by application code; digest columns require 64 lowercase hex characters, not length alone.
- [ ] Keep manual assessment and attended transition APIs working by passing explicit `human`/`attended_user` authority. Defaults must not allow an automation caller to inherit human authority.
- [ ] Run schema and core GREEN. Confirm current verifier rejects V1 and V1 verifier rejects V2.
- [ ] Commit tests first, then product implementation.

## Task 2: Build Exact V1-To-V2 Migration, Backup, And Restore Tools

**Primary files:** new `src/security_lifecycle_automation_migration.py`; evolved legacy migration/retirement authorities; migration tests.

- [ ] Add all ten migration nodes before implementation and obtain exact RED for the missing module/interfaces.
- [ ] Expose keyword-only, no-default-path APIs for `preflight_automation_migration`, `create_automation_profile_backup`, `restore_automation_profile_backup`, and `migrate_automation_profile_schema`.
- [ ] Preflight uses `mode=ro`, starts a read transaction, verifies V1 exact authorities, rejects dormant Tavily/web rows, enumerates every mapped lifecycle/ticker row, and hashes only owned object SQL plus owned rows. Unrelated `job_runs` or scheduler writes cannot change approval digest.
- [ ] Under `BEGIN IMMEDIATE`, re-read and compare that owned digest. Disable foreign keys only outside the transaction, rebuild all owned parent/child tables in dependency order, copy mapped rows, create exact V2 indexes, run `foreign_key_check` and `integrity_check`, then commit. Fault injection at each DDL/copy phase must leave V1 byte/logical state intact.
- [ ] Reject unowned views/triggers that depend on rebuilt owned tables unless the migration explicitly preserves and verifies them. Preserve every unrelated table/index/view/trigger and row digest exactly.
- [ ] Backup uses SQLite online backup into an explicit new path, fsyncs file and parent, and verifies the copied logical digest. Restore refuses missing/mismatched backup or an existing target before mutation, installs through a scratch file, fsyncs, and verifies V1 authority.
- [ ] Adapt prior migration/retirement modules to call explicit V1 authorities. Historical documents and prior live receipts remain untouched.
- [ ] Run migration GREEN and a scratch V1 -> V2 -> verified backup restore cycle. No production path is read.

## Task 3: Replace Instance-Local SEC HTTP With One Shared Governor

**Primary files:** new `data_sources/sec_transport.py`; six active SEC HTTP owners and focused tests.

- [ ] Add ten transport nodes and evolve named SEC owners before implementation.
- [ ] Implement typed failures, strict identity validation, strict HTTPS host validation, cross-thread/process governor, one-retry 429 handling, bounded JSON/document reads, request budgets, and bounded diagnostics with injected session/clock/sleep/lock directory.
- [ ] Route each active direct SEC call through the transport. Preserve public data-source return shapes and existing cache semantics; do not hide a transport failure as an honest empty result in the new evidence path.
- [ ] Add an AST/static inventory that fails if active SEC owners import/call `requests` directly or if `src/` gains a runtime import of dormant `data_sources.sec_filings`.
- [ ] Prove two client instances share a 200 ms schedule, two governor instances coordinate via one state file, lock/state failure is fail-closed, and the lock is released before session I/O.
- [ ] Run all existing SEC/provider/symbol tests plus transport GREEN. No real socket call is allowed.

## Task 4: Build Bounded SEC Filing-Chain Evidence And Deterministic Facts

**Primary files:** new `src/security_lifecycle_sec_evidence.py`, fixture, and tests.

- [ ] Add ten SEC-chain nodes and a synthetic, source-shape fixture for HAPN/QBTS/CCL/BLBD. Fixture text is test data, not a claim that live source bytes were captured.
- [ ] Define immutable identity context from case ID, normalized CIK, issuer, current ticker, known aliases/conIds, filing date, accession, form, and event kinds. Ticker is never the sole join key.
- [ ] Query same-CIK filings in `[-30,+45]` days, widening once to 120 days only on typed insufficiency. Admit Form 25/25-NSE, 8-K/A Item 3.01, 8-A12B, and 8-K12B as identity-chain forms. M&A forms remain evidence and never imply continuation by form alone.
- [ ] Fetch primary documents through the lifecycle request budget. Store bounded verbatim excerpts, document/excerpt SHA-256, locator, retrieval time, and extractor rule/version.
- [ ] Emit only facts with exact cited spans. Normalize ticker/CIK/date/venue values deterministically and preserve source text. Incompatible current values become typed conflicts, not majority votes.
- [ ] Prove HAPN distinguishes symbol+venue, QBTS venue-only, CCL no tracked-security transition, and BLBD asset acquisition/no registrant identity transition at the fact layer. These offline fixtures do not count as Stage 5 grounded precision evidence.

## Task 5: Add Strict Local Publisher Evidence

**Primary files:** new `src/security_lifecycle_news_evidence.py` and tests.

- [ ] Add five nodes before implementation.
- [ ] Require caller-owned, already-open normalized-news and SA connections; no path default, schema creation, or network path exists.
- [ ] Query explicit identity aliases and inclusive date bounds against normalized news and SA market news. Bound rows and excerpts, preserve URL/title/publisher/time/body provenance, and distinguish missing schema/unavailable DB from honest zero rows.
- [ ] Deduplicate exact stored rows but count all publishers collectively as one `publisher` source family. Article count never becomes corroboration count.

## Task 6: Add Strict IBKR Contract Evidence

**Primary files:** new `src/security_lifecycle_ibkr_evidence.py` and tests.

- [ ] Add five nodes before implementation.
- [ ] Require an injected connected gateway/client and the existing shared `ibkr_gateway_lock`; never instantiate, connect, or read runtime configuration inside the adapter.
- [ ] Return one of success, `ibkr_gateway_unavailable`, `ibkr_contract_missing`, `ibkr_contract_ambiguous`, or `ibkr_entitlement_denied`. Do not reuse the existing helper that collapses all exceptions to `None`.
- [ ] On success persist only bounded symbol/localSymbol/conId/secType/primaryExchange/validExchanges/currency/retrieved-at fields. No broker/provider state is mutated.
- [ ] Run with fake gateway and lock only; zero live IBKR calls.

## Task 7: Persist Evidence And Facts Atomically

**Primary files:** new `src/security_lifecycle_fact_kernel.py`, evolved investigation store, and tests.

- [ ] Add eight kernel nodes before implementation.
- [ ] Implement canonical automation run key from case, observation fingerprint, policy version, and mode; terminal rows dedupe unless inputs change or retry time is reached.
- [ ] Validate evidence source-family/adapter/kind coherence, excerpt/document digests, locator JSON, fact types, canonical values, spans, and cited-text hashes before opening the write transaction.
- [ ] Persist one run's evidence/facts atomically. A failure leaves no partial rows. Expected provider/evidence conditions become `blocked` with typed blockers; programmer/schema faults remain `failed` or propagate and are never relabeled network failures.
- [ ] Derive family sets from persisted rows and conflict sets from normalized current facts. Translation/model prose/article count cannot satisfy a family or erase a conflict.
- [ ] Recomputing with changed evidence, observation fingerprint, or rule version produces a new provenance digest and makes the prior run non-current without deleting history.

## Task 8: Offline Admission And Stage 3 Checkpoint

- [ ] Run the exact additions ledger: `54 passed`.
- [ ] Run the focused ledger: `333 passed` with no skips unless the 279-node baseline already contained them; compare exact node set.
- [ ] Run full backend collection twice and require `4348` both times.
- [ ] Run full backend execution twice using unique `--basetemp` roots and no overlapping pytest sessions. Expected arithmetic is baseline `4282 passed / 12 skipped + 54 = 4336 passed / 12 skipped`.
- [ ] Run static direct-SEC scan, default-path signature scan, network-denial tests, `PRAGMA integrity_check`, `foreign_key_check`, and scratch V1/V2 verifier cross-rejection.
- [ ] Prove changed paths are a subset of the owned ledger, every owned changed path differs from its pin, protected paths are unchanged, and no production DB/config secret/provider was opened.
- [ ] Produce a Stage 2 evidence packet with node lists, exact schema SQL hashes, V1 mapping report, governor budget report, and scratch migration/restore report.
- [ ] **Stop before Stage 3.** Present the schema authority, legacy row mapping, dormant Tavily/web handling, SEC lock ownership, and numeric request budgets for the agreed checkpoint. No Stage 3 code starts until that checkpoint is GREEN.

## Non-Goals And Hard Stops

- No model or hosted-search adapter, automatic assessment, proposal generation, scheduler worker, API route, frontend/UI, translation execution, or transition activity behavior.
- No general web search and no provider canary.
- No live SEC, IBKR, news-provider, or LLM call.
- No production DB read/write/preflight/backup/migration/restore.
- No changes to `config/.env`, private keys, auth drivers, tool registries/bridges, app process, or prior evidence packets.
- No merge or push. Those remain explicit user actions after independent review.
