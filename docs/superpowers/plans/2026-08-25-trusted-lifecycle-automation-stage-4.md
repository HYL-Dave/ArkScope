# Trusted Lifecycle Automation Stage 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`, `superpowers:test-driven-development`, and `superpowers:verification-before-completion`. Steps use checkbox (`- [ ]`) syntax for tracking. Execute in the existing isolated worktree; do not merge or push.

**Goal:** Make automation-authorized ticker transitions reversible and visibly auditable, expose complete decision/evidence truth in the Lifecycle UI, and add optional hash-bound evidence translation without changing the reviewed schema authority.

**Architecture:** Stage 4 consumes the exact Stage 2 schema and Stage 3 decision output. It adds no table, column, status, rule, provider, or model-judgment path. Transition approval remains distinct from transition execution; apply/reverse activity is append-only, acknowledgement only reduces prominence, and translation is a derived cache beside immutable original evidence.

**Tech Stack:** Python 3.10, stdlib `sqlite3`, FastAPI/Pydantic, React 18, TypeScript, i18next, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-08-24-trusted-lifecycle-automation-design.md`

## Global Constraints

- Stage 4 base is exactly `1af6bc69c6e2ccbe1cd1e25e899325ba758c671b`; the tested Stage 3 product/test authority is `f57457e48018ec212d9d92a0b4c52b3a23eaf6ea`.
- Existing Stage 2 profile/ticker schema bytes and migration bytes are protected. Stage 4 uses `approval_authority`, `ticker_identity_transition_activity`, and `security_lifecycle_evidence_translations` exactly as shipped.
- Backend baseline collection is `4385`; this stage adds exactly `20` nodes and removes none, for target collection `4405`. Backend focused baseline is `126`, target `146`.
- Frontend baseline is `104` files / `1220` tests. Stage 4 adds one test file and exactly `7` tests, for target `105` files / `1227` tests. Focused baseline is `53`, target `60`.
- Route baseline is `184`; exactly three routes are added, for target `187`: activity list, activity acknowledgement, and evidence translation. Tool/bridge inventories remain unchanged.
- `approved + execute_on` remains the only waiting-to-execute representation. Do not add `verified_pending_effective` or another transition status.
- Automation transition approval requires an accepted `author=automation`, `acceptance_authority=automation_policy`, deterministic rule identity, matching run policy, and exact decision provenance. Attended approval remains attended.
- Apply and reverse append activity in the same `BEGIN IMMEDIATE` transaction as profile mutation. A failed transaction leaves no activity row.
- Rendering never acknowledges activity. Acknowledgement is explicit, idempotent, and cannot shorten or remove reversal availability.
- Original source-language evidence remains authoritative and is always rendered. Translation is adjacent, labeled machine-generated, hash/locale-bound, never cited, and cannot change case/decision state.
- No provider/network call, production database read/write/preflight/backup/migration/restore, merge, or push is authorized. Translation execution is tested through injected fakes only.
- Stop and amend before any schema authority change, unlisted changed path, unexpected test identity/count drift, need for a new closed value, or need to cross a hard stop.

---

## Mechanical Authorities

- Owned paths: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-4-owned-paths.tsv`
- Focused paths: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-4-focused-paths.tsv`
- Additions: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-4-additions.nodes`
- Evolved owners: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-4-evolved-owners.tsv`
- Protected paths: `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-4-protected.paths`

Every changed non-governance path must already appear in the owned ledger. Before each RED, search all backend/frontend tests for the changed route, enum, resource subtree, and symbol names; an unlisted owner is a stop, not an incidental full-suite repair.

## Closed Interfaces

```python
def build_automation_transition_preflight(
    conn: sqlite3.Connection,
    *,
    case: Mapping[str, object],
    request: Mapping[str, object],
    sources: Iterable[str],
) -> dict: ...

class TickerIdentityTransitionStore:
    def approve_automation(
        self,
        *,
        preview: Mapping[str, object],
        approved_preview_sha256: str,
    ) -> dict: ...

    def list_activity(self, *, limit: int, unacknowledged_only: bool = False) -> dict: ...
    def acknowledge_activity(self, activity_id: str, *, at: str) -> dict: ...
    def reverse_readiness(self, transition_id: str) -> dict: ...

@dataclass(frozen=True)
class EvidenceTranslationResult:
    translated_text: str
    provider: str
    model: str
    harness: str

def translate_evidence(
    store: SecurityLifecycleInvestigationStore,
    *,
    evidence_id: str,
    locale: str,
    translator: Callable[[str, str], EvidenceTranslationResult],
    at: str,
) -> dict: ...
```

`LifecycleAutomationWorker` gains one required constructor dependency, `transition_approver`. It is invoked only after a `verified_automatic/transition_eligible` assessment is accepted and proposals exist. The production scheduler supplies the real provider-free preflight and approver; tests supply fakes.

## Task 0: Baseline And Ledger Admission

**Files:** governance files only.

- [x] Verify clean branch at `1af6bc69`, linear from `64af5092`, not merged or remotely published.
- [x] Verify every modify pin and every absent add path in the owned ledger.
- [x] Collect backend focused paths as exactly `126` and backend collection twice as exactly `4385`.
- [x] Run the three frontend focused files plus ticker presentation as exactly `53`; run full frontend as `104/1220`.
- [x] Confirm route inventory `184`, no added route yet, protected bytes exact, and no production/provider access.

## Task 1: Bind Automation Transition Authority

**Files:**
- Modify: `src/ticker_identity_transition.py`
- Modify: `src/ticker_identity_service.py`
- Modify: `src/security_lifecycle_automation_worker.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Modify: `tests/test_ticker_identity_transition.py`
- Modify: `tests/test_security_lifecycle_automation_worker.py`
- Modify: `tests/test_security_lifecycle_automation_scheduler.py`

**Interfaces:** Produces `build_automation_transition_preflight`, `approve_automation`, `TickerIdentityService.approve_automation_case`, and the worker's required `transition_approver` seam.

- [x] Add the six Task 1 nodes named in the additions ledger. RED may show missing interfaces or the current `action_executor_not_available`; it may not open a provider or production path.
- [x] Build a prospective preview from the same profile-effect functions as the durable preview. Synthetic assessment/proposal identities are permitted only inside this read-only preflight and are never stored.
- [x] Keep attended `approve(...)` behavior unchanged. `approve_automation(...)` derives and verifies author, acceptance authority, policy, rule, and provenance from current persisted assessment/run rows; caller claims cannot replace them.
- [x] Wire the worker so only `verified_automatic + transition_eligible + transition_requested` invokes the approver after accepted assessment and proposal persistence. Non-mutating verified decisions and suggestions never approve a transition.
- [x] Replace the scheduler's unavailable preview stub with the real provider-free preflight and approver. Preview drift or authority mismatch is typed and cannot apply profile changes.
- [x] Run the exact Task 1 RED/GREEN set, then its full owned backend files. Commit tests before product code.

## Task 2: Append And Expose Reversible Activity

**Files:**
- Modify: `src/ticker_identity_transition.py`
- Modify: `src/ticker_identity_service.py`
- Modify: `src/api/routes/ticker_identity.py`
- Modify: `src/tools/security_lifecycle_tools.py`
- Modify: `tests/test_ticker_identity_transition.py`
- Modify: `tests/test_ticker_identity_routes.py`
- Modify: `tests/test_security_lifecycle_tools.py`
- Modify: `tests/test_api.py`

**Interfaces:** Produces activity list/acknowledge reads and routes, reverse readiness, and transition activity in case detail.

- [x] Add the six Task 2 nodes. Evolve both exact route-count owners from `184` to `186` and lifecycle route count from `14` to `16` after the two activity-route RED is admitted; Task 3 adds the translation route and reaches the final `187` / `17` inventory.
- [x] In the same apply transaction, append one `applied` activity containing bounded typed change counts, retained provider facts, post-state digest, rule identity, provenance, and time. Add the row before commit; rollback removes it.
- [x] In the same reverse transaction, append one `reversed` activity bound to the restored state digest. Blocked reverse creates an attempt but no activity.
- [x] Factor reverse blockers into a read-only `reverse_readiness` used by both reverse and presentation. It must report exact state drift and later-lineage blockers without mutating attempts.
- [x] List activity newest-first with total/unacknowledged counts. Acknowledge by explicit command only; repeated acknowledgement returns the original timestamp and leaves transition/activity payload and reversal readiness unchanged.
- [x] Add `GET /security-lifecycle/transition-activity` and `POST /security-lifecycle/transition-activity/{activity_id}/acknowledge`, with read-before-permission validation and typed 404/422/503 errors.
- [x] Add approval provenance and bounded activity history to the existing case-detail transition projection. Provider-neutral tools may expose typed provenance/activity but never raw snapshot JSON.
- [x] Run exact Task 2 RED/GREEN, intermediate route inventory `186` with `16` lifecycle routes, and provider-free read/write boundary tests. Commit tests before product code.

## Task 3: Add Hash-Bound On-Demand Evidence Translation

**Files:**
- Create: `src/security_lifecycle_translation.py`
- Modify: `src/card_synthesis.py`
- Modify: `src/security_lifecycle_investigation.py`
- Modify: `src/api/routes/security_lifecycle.py`
- Modify: `src/tools/security_lifecycle_tools.py`
- Create: `tests/test_security_lifecycle_translation.py`
- Modify: `tests/test_security_lifecycle_routes.py`
- Modify: `tests/test_security_lifecycle_tools.py`
- Modify: `tests/test_card_synthesis.py`

**Interfaces:** Produces `translate_text` for a one-field fixed translation, `EvidenceTranslationResult`, `translate_evidence`, and `POST /security-lifecycle/evidence/{evidence_id}/translations`.

- [ ] Add the eight Task 3 backend nodes. Initial RED is missing translation interfaces/routes only.
- [ ] Reuse the existing `card_translation` model route and timeout. Translate one bounded excerpt field, preserve source text byte-for-byte, and return explicit provider/model/harness provenance.
- [ ] Validate locale (`en | zh-Hant`) and evidence identity before permission/provider work. Return a current hash-bound cache hit without permission or translator invocation.
- [ ] On a miss, read and close any write transaction before translator invocation, then re-read the evidence hash before insertion. Changed/deleted evidence rejects the result; provider failure stores nothing and does not change workflow state.
- [ ] Mask provider exception text behind closed `translation_timeout | translation_failed | translation_output_invalid` API codes. Never store prompts, credentials, raw frames, or untranslated source bodies beyond the existing excerpt.
- [ ] Project translations adjacent to their source evidence in the UI read DTO. Provider-neutral agent tools omit translated text so it cannot be mistaken for authoritative evidence.
- [ ] Run exact Task 3 RED/GREEN and card-translation regression tests with all model calls faked. Commit tests before product code.

## Task 4: Render Complete Decision Truth And Reversible Visibility

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Create: `apps/arkscope-web/src/lifecycle/LifecycleActivityBand.tsx`
- Create: `apps/arkscope-web/src/lifecycle/LifecycleActivityBand.test.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/lifecyclePresentation.ts`
- Modify: `apps/arkscope-web/src/lifecycle/lifecyclePresentation.test.ts`
- Modify: `apps/arkscope-web/src/lifecycle/tickerIdentityPresentation.ts`
- Modify: `apps/arkscope-web/src/lifecycle/tickerIdentityPresentation.test.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.test.ts`
- Modify: `apps/arkscope-web/src/styles.css`

**Interfaces:** Adds compile-time closed API types/presentations, a first-view activity band, complete automation/fact views, suggestion prefill, and adjacent translation controls.

- [ ] Add the seven frontend nodes. RED must be confined to the named additions/evolved owners; a fifth resource owner or unrelated visible-literal failure is an amendment stop.
- [ ] Add exact TypeScript unions/interfaces for decision tier, readiness, author/method/acceptance authority, source family, facts, blockers, translations, transition approval, and activity. Unknown boundary values render as unknown, never another known label.
- [ ] Render unacknowledged automatic activity before filters/table. Each item states old/new or terminal action, effective/applied time, changed user-owned categories, retained provider-owned data, rule/version, acknowledgement, Reverse, or exact reverse blocker. Render does not call acknowledgement.
- [ ] Keep acknowledged activity in recent history and case detail. Acknowledge only lowers prominence; it is not approval/consent and does not hide Reverse.
- [ ] Group evidence by typed source family. Always show verbatim source excerpt, URL, publisher/time, and extraction facts. Show machine translation adjacent with provider/model provenance and a clear derived label; loading/error never removes original text.
- [ ] Render automation tier, action readiness, author, acceptance authority, rule/version, citations, structured assessment fields, facts, and typed blockers. Prefill the edit form from the newest automation draft; accepting unchanged uses the existing accept command, while saving edits creates the existing human revision.
- [ ] Keep manual text/URL controls secondary. Preserve exhaustive status/outcome/proposal mappings and source-language content.
- [ ] Run focused frontend `60`, typecheck, visible-literal scanner, and production build. Commit tests before product/UI code.

## Task 5: Scratch Apply, Acknowledge, And Reverse

**Files:** test/evidence artifacts only; no production path.

- [ ] Build explicit scratch market/profile databases with the reviewed schema and a synthetic eligible `OLD -> NEW` case.
- [ ] Execute observation -> facts/evidence -> verified automation assessment -> proposals -> automation-policy transition approval -> due scheduler apply -> activity read -> explicit acknowledgement -> exact reverse.
- [ ] Prove user-owned rows after reverse are byte-for-byte equal to the pre-apply snapshot, provider-owned/history rows never changed, acknowledgement survives as history, and no activity rendered itself acknowledged.
- [ ] Run a state-drift scratch variant that blocks reverse with the exact reason and preserves the user's later edit.
- [ ] Capture a bounded JSON report with IDs/digests/counts only; no source body, prompt, credential, path, or provider payload.

## Task 6: Stage 4 Offline Admission

- [ ] Run exact backend additions `20 passed`; focused backend exact identity `126 + 20 = 146`; collection twice `4405`.
- [ ] Run full backend twice with unique `--basetemp`; expected `4393 passed / 12 skipped / 0 failed`.
- [ ] Run frontend focused `60`, full `105 files / 1227 tests`, typecheck, visible-literal scanner, and production build.
- [ ] Verify route inventory `187`, lifecycle routes `17`, and unchanged tool/bridge inventories.
- [ ] Run owned backend additions under network syscall denial/trace; no provider connection is permitted. Loopback test harness binds must be classified, not mislabeled.
- [ ] Prove every changed non-governance path is owned, all protected bytes match, branch is linear/clean/unpublished, and production/provider counters remain zero.
- [ ] Produce a Stage 4 evidence packet with exact node streams, activity/authority matrix, translation cache/failure report, scratch apply/ack/reverse report, frontend artifacts, and a checksummed manifest.
- [ ] Continue directly to Stage 5 grounded admission unless a hard stop or amendment condition occurs. Do not merge or push.

## Non-Goals And Hard Stops

- No schema or migration edits.
- No provider canary, SEC/IBKR/model call, hosted search, or translation execution against a real credential.
- No automatic M&A/cash-out/spin-off/class-change transition.
- No production DB operation, app cutover/restart against this feature tree, merge, or push.
- No model-authored assessment, translated evidence citation, or translation-based automatic gate.
