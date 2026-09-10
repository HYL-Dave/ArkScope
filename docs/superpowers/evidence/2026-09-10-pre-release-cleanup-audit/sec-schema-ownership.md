# SEC Cleanup Schema Ownership Checkpoint

Source ownership inspection started at `df97352b`; the September 11 helper
checkpoint below updates completed source removals. No production counts are
asserted here: the single authorized read failed before inventory queries.
Current-store read authorization and digest-bound disposal approval are separate
from source-code removal.

## What Can Disappear Without A Data Conversion

- `sec_corporate_actions` SourceDef, provider mapping, module entrypoint and
  schedule-specific frontend copy/cache invalidation. The generic schedule API
  must reject the absent source before provider configuration or worker launch.
- Old case-scoped web HTTP routes, router shutdown hook and their executable
  controller, after current workers and confirmation DTO acquire their own owner.
- Unmounted legacy investigation screens and old-only frontend clients/types.

These deletions do not imply that all similarly named tables are unreferenced.
The active SEC credential/identity configuration and financial queries remain.

## Actual Data Boundaries

| Structures | Current owner / reason to retain until conversion | Disposal requirement |
| --- | --- | --- |
| Market `security_lifecycle_observations`, `security_lifecycle_observation_kinds` and their indexes | Raw original intake plus possible accepted-history citations; current collector removal stops new SEC intake, but does not erase reference obligations | Count original observations and kinds separately; inspect FK/accepted-reference closure before removing owned rows or definitions |
| Profile `security_lifecycle_cases`, assessments, assessment outcomes/evidence | Current listing decisions and target investigation acceptances use these shared tables, including direct FK from `lifecycle_investigation_acceptances.assessment_id` | Keep current shape unless required historical references have been moved; never select for DROP by prefix |
| Profile `security_lifecycle_provider_checks` and append-only guards | Current Massive/EODHD listing authority and `ticker_identity_history` match approved observation digests against these rows | Retain provider observations and immutable guards |
| Profile legacy investigation runs, automation facts/blockers/evidence/translations, acknowledgements and proposals | Some are old-only workflows; `security_lifecycle_evidence` and automation runs also support accepted listing/history relationships | Classify exact reader/writer and retained FK closure before deleting columns/tables; old-only translation UI removal alone is not proof all cited evidence is disposable |
| Profile `lifecycle_web_installation`, runs, calls, actions, pages, results and acceptances | `ticker_identity_history._llm` still reads case-scoped accepted history. `_web_passages` locates approved quotations in old pages and verifies the pinned passage digest. `lifecycle_web_review` guards existing acceptance/reversal material | Move actual retained history into a current immutable readable representation, verify same explanatory material/digests, then remove old writer/helper/schema. Never replace a missing history source with a fabricated explanation |
| Profile `lifecycle_investigation_*` tables and immutable guards | Current target-bound jobs, sources, calls, results, acceptances and recovery | Retain; no reset/reinstallation as a cleanup shortcut |
| Profile `ticker_identity_*`, Former membership acceptance/removal records | Applied/scheduled transitions, reversal readiness and user suppression survive imports/aliases | Retain all current receipts, identities and tombstones |
| Profile `schedule.sec_corporate_actions.*` keys and old source runtime rows | No runtime owner after source removal; values must not enable the new research schedule | Delete only enumerated source-owned keys/rows in approved actual-store operation; preserve unrelated source schedules, credentials and routes |
| Migration/disposal receipts | Guard incomplete prior operations and prove already-applied changes | Preserve evidence; remove spent executable conversion entrypoints only after verified rollout, not while a current repair/disposal operation imports them |

## Existing Operator Primitives

`lifecycle_investigation.disposal.preview_disposal` and `apply_disposal_stage`
already implement dependency-aware case closure, profile/market stages, a WAL-safe
backup and immutable digest-bound receipts. The code explicitly excludes provider
checks and migration receipts from its disposable set. An unfinished execution,
human assessment, unknown child FK or external dependency prevents disposal.
These are useful primitives, not proof that every old table can already be removed:
the current operation deletes eligible rows and reinstates guards, not schemas.

`lifecycle_investigation.migration._snapshot` hashes complete profile contents for
an explicit backed-up installation. It is **not** suitable for a narrowly
authorized statistics-only inspection: it reads unrelated profile rows too.
Use a separate allowlisted metadata/count/reference query for that read permission;
do not quietly invoke the broad snapshot under a narrower authorization.

## Remaining Source Extraction

This is an actionable remainder, not a reason to preserve dead execution forever:

- `lifecycle_web_store.ValidatedWebRead`, `validated_read` and
  `read_on_connection` still support current adoption and retained evidence.
  Its old `start`, `heartbeat`, phase/cancel writes, call reservations,
  `complete`/`fail`, recovery and `JournalControl` need a separate exact-caller
  disposition after removing the old controller. A live reader does not make
  every writer in the same module live.
- Shared canonical encoding/digests were extracted to
  `src.lifecycle_journal_codec` in `5d41f570`, with exact bytes preserved.
  `58e1929b` additionally guards against reintroducing the old `_json`/`_sha`
  exports or imports. This dependency is resolved; it does not resolve the
  old store's live validated readers or `WebJournalError` ownership.
- `lifecycle_web_review` is still used by current investigation confirmation,
  `security_lifecycle_review` and `ticker_identity_transition`. Move current
  freshness, provider veto, adoption and acceptance/transition guards together.
  Deleting only its old route leaves these real dependencies to resolve.
- `security_lifecycle_web_pipeline._read_one` is still consumed by the current
  investigation agent. Its old fixed two-call orchestrator and the useful
  source-read primitive have separate ownership; do not delete by filename.
- `security_lifecycle_current` still uses `lifecycle_web_projection` for its
  old review-detail projection. Current Settings status and provider packet
  confirmation also use some case-based services. Removing unmounted UI does
  not authorize removing all case APIs or their shared assessment schema.

After the old UI/client deletion at `302106d2`, five HTTP candidates were
individually checked and removed in `0c5896a5`:

- `GET /security-lifecycle/cases/{case_id}/audit`
- `GET /security-lifecycle/reviews/{review_id}`
- `POST /security-lifecycle/evidence/{evidence_id}/translations`
- `POST /security-lifecycle/cases/{case_id}/automation/run`
- `GET /security-lifecycle/review-confirmations/{transition_id}`

The measured App inventory changed from 221 to 216 entries, with no other route
change. Current tool review, provider confirmation, history, global automation,
acknowledgement and reversal remain. Six integrity test owners were moved to
their actual service/tool/global route, not weakened to assert a missing route.
The old translation orchestrator and its exclusive store methods were also
deleted after losing their final runtime caller. AI-card/content translation
and the historical `list_evidence` translation JOIN remain. The current census
cannot prepare that JOIN because its synthetic union schema lacks the joined
evidence table; its nine table/column candidates are not deletion evidence.

The unused confirmation-service forwarding method left by the route removal was
removed in `e61accaf`, with six existing test readbacks transferred. The real `_result`
and `confirmation_for` receipt readers remain current. See
[helper cleanup evidence](sec-retention-helper-cleanup/README.md) for checkpoint
heads, exact test accounting and the remaining production read boundary.

Current old-web declarations name seven tables (`installation`, `runs`, `calls`,
`actions`, `pages`, `results`, `acceptances`), an active-case unique index and
immutable identity/page/result/acceptance/call guards. These are source counts,
not observations of the user's installation. Accepted historical evidence must
be moved with its guard/digest semantics, or proven unused, before dropping them.
The two old schedule keys are `schedule.sec_corporate_actions.enabled` and
`schedule.sec_corporate_actions.interval_minutes`; source result/job history has
separate owners and must not be deleted by a broad string-prefix match.

## Next Actual-Store Manifest

The first authorized attempt used read-only SQLite URIs and a nonwritable
filesystem view. It failed at ATTACH before any inventory query; absent WAL/SHM
coordination files are a reproduced synthetic explanation, not a proven
production diagnosis. No row counts, empty-table finding or reference closure
were obtained. No second read or coordination-file write is authorized by that
failure; the user was asked about this narrow SQLite coordination requirement.

1. Resolve only the named market/profile stores, open `mode=ro`, set `query_only`,
   and capture consistent schema/row-count/reference bounds. No credentials,
   provider acquisition, source-body rendering or automatic retries.
2. Enumerate owned tables, indexes, triggers and exact schedule keys; report
   counts and reference classes, not document text or token material.
3. Distinguish retained current rows, accepted historical evidence, unreferenced
   abandoned rows and unknown dependencies. An empty result is an observation,
   not permission to remove unrelated tables.
4. Construct the candidate canonical shape and explicit retention projection.
   Tests must cover a fresh DB and an existing populated DB, FK integrity,
   interrupted publication, retained history/reversal and unrelated-data digests.
5. Present the exact backup/disposition digest for approval before production
   writes. Separate source cleanup completion from actual schema disposal.

This checkpoint does not implement the new three-tool SEC research service and
does not claim that the old web schema or every obsolete lifecycle helper is gone.
