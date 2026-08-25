# Trusted Lifecycle Automation Stage 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` for every behavior change and `superpowers:verification-before-completion` before each GREEN claim. Execute in the existing isolated worktree; do not merge or push.

**Goal:** Turn Stage 2's cited evidence/facts into honest, deterministic two-tier lifecycle decisions, complete automation-authored assessments, safe proposals, and a bounded witnessed scheduler worker.

**Architecture:** Keep decision policy pure and provider-neutral. A bounded worker injects evidence acquisition, transition-preview, profile connection, and clock dependencies; it persists the Stage 2 run first, then creates either an automation-policy accepted assessment or a complete automation draft. The app scheduler only orchestrates a maximum of two changed cases per tick and records sanitized failure/recovery witnesses. No route, model, hosted search, UI, transition approval, or profile mutation is added here.

**Tech Stack:** Python 3.10, stdlib `sqlite3`, dataclasses, existing Stage 2 SEC/news/IBKR adapters, FastAPI/Pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-08-24-trusted-lifecycle-automation-design.md`

## Global Constraints

- Product base is exactly `5d88e1b301e62a61211e3343165ef37be90b0250`; Stage 2 product authority remains `ab6654c0c9cd7586b883a10ea4f40255fa5e3249`.
- Backend baseline collection is exactly `4348`; the fully amended focused pre-addition collection is exactly `234` nodes (`156` originally admitted plus `34` existing direct-caller nodes plus the `44`-node provider-config owner file).
- This stage adds exactly `37` backend nodes and removes none. Target collection is `4385`; target focused collection is `271`.
- Automation policy version is `trusted-lifecycle-automation-v1`; deterministic rule IDs and version `1` are closed in this plan.
- One worker tick admits at most two cases. A current non-stale accepted human/legacy/automation assessment is not overwritten.
- `verified_automatic` requires deterministic regulator facts and every rule-specific independent condition. `review_suggested` is a complete draft, never an accepted conclusion or profile-mutation authority.
- `source_conflict` is a typed `review_suggested` decision issue. It may not be majority-resolved and may not be relabeled as a provider/network failure.
- Automatic acceptance records `author=automation`, `automation_method=deterministic_rule`, and `acceptance_authority=automation_policy`. Human acceptance of an unchanged automation draft retains `author=automation` and records `acceptance_authority=human`; editing creates a separate human revision.
- General web, hosted search, model judgment, translation, transition approval/application/activity, and frontend changes are Stage 4 or later.
- No provider/network call, production database read/write/preflight/backup/migration/restore, app restart, merge, or push is authorized during implementation or verification.
- Stop and amend before any schema authority change, unexpected data shape, unlisted changed path, test-node identity drift, or need to cross a hard stop.

---

## Mechanical Authorities

- Owned paths: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-3-owned-paths.tsv`
- Focused paths: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-3-focused-paths.tsv`
- Additions: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-3-additions.nodes`
- Evolved owners: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-3-evolved-owners.tsv`
- Protected paths: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-3-protected.paths`

Every changed non-governance path must be listed before product edits. New test node IDs and existing node IDs are immutable. RED is admitted only when its failing set is exactly additions plus named evolved owners and each failure is caused by the missing/evolved behavior.

### Task 3 direct-caller amendment

A pre-edit caller census after Task 2 found three existing test helpers/direct
callers outside the original owned ledger. They invoke
`SecurityLifecycleInvestigationStore.accept_assessment(...)` directly and must
pass an explicit authority once its new required argument lands:

- `tests/test_security_lifecycle.py` preserves the legacy migration caller and
  passes `legacy_migration`;
- `tests/test_ticker_identity_routes.py` preserves its attended human fixture
  and passes `human`; and
- `tests/test_ticker_identity_scheduler.py` preserves its attended human
  fixture and passes `human`.

All three files are byte-identical to product base at the pins now recorded in
the owned ledger. Their exact current collection is `8 + 6 + 20 = 34` nodes.
They add no node, route, state, schema, or behavior; only the shared/direct
caller arguments change. The focused baseline therefore becomes `190` and the
final focused target becomes `227`; backend collection and the `37` additions
remain unchanged. Product work stopped before touching any unlisted path.

### Task 4 contract-missing RED correction

The first Task 4 tests-only RED incorrectly required an IBKR
`document_reference` row for a typed missing-contract lookup. That shape
contradicts the reviewed Stage 2 schema authority: `ibkr_contract` evidence is
closed to `source_family='market_infrastructure'` and
`kind='market_infrastructure_snapshot'`, while this stage explicitly forbids a
schema change. Product work had not started.

The corrected contract stores a snapshot of the **lookup outcome**, not a fake
contract: `kind='market_infrastructure_snapshot'`,
`source_locator.contract_status='missing'`, an excerpt containing the same
typed status and queried ticker, and no `source_locator.snapshot` or invented
contract fields. `contract_snapshot_facts(...)` returns no facts for this
shape. The `ibkr_contract_missing` blocker remains distinct; only the
post-effective terminal-delisting rule may consume the persisted absence as
market confirmation. Node identity, additions, focused/collection arithmetic,
schema bytes, and owned product paths remain unchanged. The corrected 13-node
RED must be replayed before product code.

### Task 4 stale-evidence re-entry amendment

Task 4 self-review found that the accepted staleness contract and the original
four-input run key were incompatible. Adding supplemental/manual evidence makes
an accepted assessment stale, but reserving the same case/fingerprint/policy/
mode returned the already-terminal run and could never re-enter automation.

The run key therefore also binds the pre-run digest of evidence whose
`automation_run_id IS NULL`. The kernel computes and records that digest in
`query_context_json`; callers cannot supply a competing value. Evidence written
by an automation run is excluded, preventing completion from manufacturing a
new input generation. The existing run-key owner and changed-input worker owner
gain discriminating subcases without changing node IDs or counts. Fact-kernel
product/test paths expand from `T1` to `T1/T4`; no path, schema column, closed
vocabulary, route, or collection identity is added.

### Task 7 IBKR client-id projection owner amendment

The first full-suite admission run ended `4372 passed / 1 failed / 12 skipped`.
Its sole failure was the existing
`tests/test_data_provider_config.py::test_view_exposes_client_id_domains`: the
Stage 3 `lifecycle=80` read-only domain correctly appeared in the app-managed
provider projection, while this exact-list owner still expected the eight
pre-Stage-3 domains. The focused and ownership ledgers had omitted that
downstream owner.

The test file is byte-identical to the product base at `716` lines and SHA-256
`9c291a9ea5ad99132b29915c27d955b0315636484f44c4763c89915e9671386e`; it
collects exactly `44` existing nodes. Follow-up inspection of that owner found
the corresponding product boundary was also stale: app-managed validation and
guard copy still allowed base IDs through `29`, while `lifecycle=+80` requires
the shared base to stay at or below `19` to remain outside the legacy `100+`
band. `src/data_provider_config.py` is therefore owned at its exact product-base
pin (`604` lines, SHA-256
`bfd97f197e6fdc372b658f588713ec3cf2338d80e5ef0f55ee6daca7c4a30a8d`).
Stage 3 evolves the projection owner and its existing normalization owner,
updates the shared app-managed limit/copy, and changes no node, client-id
offset, schema, route, or backend collection identity. The focused baseline is
therefore `234` and the final target is `271`. The rejected first full run
remains evidence and canonical admission restarts after the RED-first owner and
product correction.

## Closed Decision Contract

The pure policy returns `AutomationDecision` with these fields:

```python
@dataclass(frozen=True)
class AutomationDecision:
    decision_tier: Literal["verified_automatic", "review_suggested"]
    action_readiness: Literal[
        "not_applicable", "waiting_effective_date",
        "waiting_market_confirmation", "transition_eligible", "action_blocked"
    ]
    relevance: str
    confidence: str
    outcomes: tuple[str, ...]
    conclusion: str
    impact_summary: str
    successor_ticker: str | None
    destination_venue: str | None
    effective_date: str | None
    counterparty_name: str | None
    counterparty_ticker: str | None
    counterparty_cik: str | None
    consideration_currency: str | None
    cash_per_security_decimal: str | None
    exchange_ratio_decimal: str | None
    rule_id: str
    rule_version: str
    decision_issues: tuple[str, ...]
    transition_requested: bool
```

Closed rule identities are:

- `lifecycle.simple_symbol_continuation@1`;
- `lifecycle.venue_transfer@1`;
- `lifecycle.no_identity_change@1`;
- `lifecycle.terminal_delisting@1`;
- `lifecycle.ma_review@1`;
- `lifecycle.source_conflict@1`; and
- `lifecycle.insufficient_identity_facts@1`.

`evaluate_automation_decision(...)` consumes the case identity/observation, normalized persisted-or-pending evidence/facts, current New York date, active source set, and a caller-supplied transition-preview evaluator. It never opens a file, database, provider, or model.

## Task 0: Baseline And Ledger Admission

**Files:** governance files only.

- [ ] Verify clean branch `trusted-lifecycle-automation-stages3-5` at `5d88e1b3`, with `ab6654c0` as its parent product checkpoint and no merge commit.
- [ ] Verify every modify pin in the owned ledger and every add path is absent.
- [ ] Collect backend `4348` twice. The original focused ledger collected `156` existing nodes; the Task 3 direct-caller amendment independently collected `34`, and the Task 7 provider-config owner amendment adds `44`, for a final amended baseline of exactly `234`.
- [ ] Confirm every protected path is byte-identical and no production path/provider is opened.

## Task 1: Make Run Decisions Reproducible And Conflict-Aware

**Files:**
- Modify: `src/security_lifecycle_fact_kernel.py`
- Modify: `tests/test_security_lifecycle_fact_kernel.py`

**Interfaces:**
- Produces: `persisted_decision_provenance_sha256(conn, run_id) -> str`.
- Produces: `SecurityLifecycleFactKernel.reserve_readiness_recheck(...) -> AutomationRunClaim` for a due `waiting_effective_date|waiting_market_confirmation` run only.
- Evolves: `complete_run` permits only `source_conflict` beside a successful `review_suggested/action_blocked` result; every other blocker remains terminal `blocked`.

- [ ] Add the two named tests and evolve the conflict owner. RED must show that current provenance depends on caller-local evidence IDs and that conflict currently becomes a blocked run.
- [ ] Canonicalize provenance from persisted evidence/fact content and source bindings, never caller-local IDs. Recompute it after the transaction and require exact equality before an automation assessment is written.
- [ ] Preserve cited evidence/facts across a readiness recheck. Append idempotently, recompute provenance over the complete run, and never delete evidence referenced by an assessment.
- [ ] A conflict persists all facts and a `source_conflict` row, returns `succeeded/review_suggested/action_blocked`, and never selects a majority value.
- [ ] Run Task 1 RED/GREEN and commit tests before product code.

## Task 2: Implement The Pure Two-Tier Decision Policy

**Files:**
- Create: `src/security_lifecycle_decision_policy.py`
- Create: `tests/test_security_lifecycle_decision_policy.py`

**Interfaces:**
- Produces: `AUTOMATION_POLICY_VERSION = "trusted-lifecycle-automation-v1"`.
- Produces: `RULE_VERSIONS: Mapping[str, str]` and `AutomationDecision`.
- Produces: `evaluate_automation_decision(*, case, evidence, facts, current_date, active_sources, transition_preview) -> AutomationDecision`.

- [ ] Add all ten policy nodes. Initial RED must be import failure only.
- [ ] Implement exact fact-family grouping. Regulator, market-infrastructure, publisher, general-web, and manual are source-family votes; multiple rows in one family remain one family.
- [ ] Simple A-to-B requires one non-conflicting regulator old/new/date/CIK/security-class shape, one matching market-infrastructure successor/security-class/venue shape, no prohibited transaction structure, and an eligible unblocked preview. Already-normalized successor cases return verified/non-mutating and forbid A-to-A.
- [ ] Venue-only and explicit no-identity-change cases are verified/non-mutating. M&A cash/stock/mixed/unknown/spin/class-change is always a fully prefilled suggestion.
- [ ] Terminal delisting accepts the regulator conclusion before its date but returns `waiting_effective_date`; after the date it returns `waiting_market_confirmation` until a typed market-absence confirmation exists, then requests a terminal preview.
- [ ] Conflicting facts return `review_suggested/action_blocked`; missing regulator identity facts return the same tier without invented fields. Publisher/manual/general-web never authorize a mutation.
- [ ] Templates are deterministic and bounded. No model prose or translation is called.
- [ ] Run all ten policy nodes GREEN and commit tests before product code.

## Task 3: Enforce Honest Assessment And Proposal Authority

**Files:**
- Modify: `src/security_lifecycle_investigation.py`
- Modify: `src/api/routes/security_lifecycle.py`
- Modify: `tests/test_security_lifecycle_investigation.py`
- Modify: `tests/test_security_lifecycle_routes.py`
- Modify: `tests/test_security_lifecycle.py` (legacy caller argument only)
- Modify: `tests/test_ticker_identity_routes.py` (human fixture argument only)
- Modify: `tests/test_ticker_identity_scheduler.py` (human fixture argument only)

**Interfaces:**
- Evolves: `accept_assessment(..., acceptance_authority: str)` has no default.
- Produces: `derive_action_proposal_specs(*, case, assessment, sources) -> tuple[dict, ...]` used by both preview and persistence.
- Produces: `create_automation_assessment(...)` orchestration helper that binds current run provenance and persisted citations.

- [ ] Add four investigation nodes and one route node. Initial RED is exactly those five additions against unchanged existing callers.
- [ ] After the five-node RED is admitted, update every existing direct caller in the five owned test/route locations with its literal authority. The three collateral test files keep every node body and assertion unchanged.
- [ ] Human/legacy/automation acceptance authorities are explicit and coherent. `automation_policy` requires an automation deterministic-rule draft, current matching run, `verified_automatic`, matching observation/rule/provenance, and no non-review blocker.
- [ ] Human acceptance of an unchanged automation draft keeps the automation author/run/rule/provenance. The existing edit route creates a new human draft and never updates the automation row.
- [ ] Project an automation assessment stale when observation/evidence, policy version, rule version, run status, persisted provenance, or conflict state changes.
- [ ] Extract proposal derivation into one pure function without changing existing human proposal behavior. Preview and persisted proposals must consume the same action specs.
- [ ] The attended API passes `acceptance_authority="human"`; it never inherits automation authority.
- [ ] Run Task 3 RED/GREEN and commit tests before product code.

## Task 4: Wire Strict IBKR Facts And A Bounded Worker

**Files:**
- Modify: `data_sources/ibkr_client_id.py`
- Modify: `src/data_provider_config.py`
- Modify: `src/security_lifecycle_ibkr_evidence.py`
- Create: `src/security_lifecycle_automation_worker.py`
- Modify: `tests/test_ibkr_client_id.py`
- Modify: `tests/test_data_provider_config.py` (one existing projection owner only)
- Modify: `tests/test_security_lifecycle_ibkr_evidence.py`
- Create: `tests/test_security_lifecycle_automation_worker.py`

**Interfaces:**
- Produces: `contract_snapshot_facts(evidence, *, regulator_successors) -> tuple[AutomationFact, ...]` with exact JSON byte spans.
- Produces: `LifecycleAutomationEvidenceBundle` and `LifecycleAutomationWorker.run(limit=2, mode="live")`.
- Adds: dedicated IBKR client-id domain `lifecycle=80`; it remains read-only and under `ibkr_gateway_lock`.

- [ ] Add the worker's ten nodes, two IBKR nodes, and one client-id node. Evolve the existing provider-config projection and normalization owners to include the lifecycle domain and cap the shared app-managed base at `19`. RED must fail on missing interfaces, not on a provider call.
- [ ] Convert successful contract snapshots to cited `successor_ticker`, `destination_venue`, and `security_class` facts only when the canonical snapshot supports them. A typed contract-missing result remains distinct and may satisfy terminal market absence only after the effective date; gateway/entitlement/ambiguity never does.
- [ ] The worker scans stable present cases, skips a current non-stale accepted assessment, admits at most two changed/due cases, and reserves the durable run before acquisition.
- [ ] Evidence acquisition, profile connections, source context, preview evaluator, and clock are constructor-injected. Core tests prove no default path or socket is reachable.
- [ ] Persist evidence/facts first. Build a complete automation assessment from persisted citations. Verified results accept by `automation_policy` and generate proposals; suggestions remain drafts. Preview drift downgrades to suggestion rather than mutating.
- [ ] Provider outcomes retain typed blocker/retry semantics. Program/schema errors use closed automation failure codes and are never relabeled as network failures.
- [ ] Due readiness rechecks are bounded and isolated from unrelated cases.
- [ ] Run Task 4 RED/GREEN and commit tests before product code.

## Task 5: Add Scheduler Witnesses Without Hiding Provider Failures

**Files:**
- Create: `src/service/security_lifecycle_automation_scheduler.py`
- Modify: `src/service/data_scheduler.py`
- Create: `tests/test_security_lifecycle_automation_scheduler.py`
- Modify: `tests/test_data_scheduler.py`

**Interfaces:**
- Produces: `run_security_lifecycle_automation(limit=2, now=None) -> dict`.
- Produces: `record_security_lifecycle_automation_result(result, *, now) -> bool`.
- Produces: `security_lifecycle_automation_failure(reason) -> dict`.

- [ ] Add four scheduler nodes and two parent-scheduler nodes. The hermetic fixture stubs the new runner/witness by default; no existing scheduler test may open lifecycle stores.
- [ ] Return only bounded status/reason/count/case-ID fields. Schema absence before live cutover is `not_installed`; exact-schema/store failure is `unavailable`; one case failure is `partial` and does not stop the second case or ordinary provider scheduling.
- [ ] Persist deduplicated failure/recovery witnesses in `job_runs` under `security_lifecycle.automation`. Raw exception text, paths, URLs, evidence, contact, or payloads are never stored.
- [ ] Parent tick order is lifecycle automation, due transition execution, then ordinary provider dispatch. Each subsystem records its own result and cannot mask another.
- [ ] Run Task 5 RED/GREEN and commit tests before product code.

## Task 6: Project Automation Truth Through Existing Reads

**Files:**
- Modify: `src/security_lifecycle_investigation.py`
- Modify: `src/tools/security_lifecycle_tools.py`
- Modify: `tests/test_security_lifecycle_routes.py`
- Modify: `tests/test_security_lifecycle_tools.py`

**Interfaces:**
- Case detail adds bounded `automation_runs`, `automation_facts`, and each run's typed blockers; list summaries add counts/current tier/readiness only.
- Provider-neutral tools remove adapter/query internals but retain source family, citation, rule, tier, readiness, and blocker codes.

- [ ] Add the one tool node and evolve the case-detail owner.
- [ ] Include automation history in `has_history`, workflow projection, truncation metadata, and current-state staleness. Do not expose secrets or unbounded source bodies.
- [ ] Keep route/tool inventories unchanged and reads provider-free/write-free.
- [ ] Run route/tool GREEN.

## Task 7: Stage 3 Offline Admission

- [ ] Run exact additions: `37 passed`.
- [ ] Run focused paths: exact `234 + 37 = 271` node identity.
- [ ] Run backend collection twice and require `4385` both times.
- [ ] Run full backend twice with unique `--basetemp`; expected arithmetic is `4336 passed / 12 skipped + 37 = 4373 passed / 12 skipped`.
- [ ] Run route inventory, scheduler network-denial tests, direct-provider scan, default-path scan, schema verifier, `foreign_key_check`, and `integrity_check` against scratch databases only.
- [ ] Prove changed paths are a subset of the owned ledger, protected paths are byte-identical, and no provider/production path was opened.
- [ ] Produce a Stage 3 packet with exact nodes, policy matrix, assessment-authority report, scheduler witness report, and scratch decision/proposal report.
- [ ] Continue directly to the separately ledgered Stage 4 plan unless a hard stop or amendment condition occurs. Do not merge or push.

## Non-Goals And Hard Stops

- No transition `automation_policy` approval, apply/reverse activity, activity acknowledgement, translation execution/storage route, frontend/UI, browser fixture, model judgment, or hosted/general web adapter.
- No provider canary or real SEC/IBKR/news/LLM call.
- No production DB read/write/preflight/backup/migration/restore.
- No schema change. Any schema necessity is an immediate stop and docs-only amendment.
- No app restart, merge, push, rollback, secret/config edit, or prior packet mutation.
