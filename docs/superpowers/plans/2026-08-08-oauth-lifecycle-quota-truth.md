# OAuth Lifecycle and Subscription Usage Truth Implementation Plan

> **Status:** PLAN REVIEW GREEN; TASKS 0-4 COMPLETE; TASK 4 EVIDENCE READY FOR INDEPENDENT REVIEW
>
> **Date:** 2026-08-08
>
> **Design authority:** `f2f12ba5e1dac6f20a53d733b80e85c6e0533d1e`
>
> **Grounding base:** `7257699171a81294b74ff8cde61fb90bb065a2b4`

**Goal:** Make OAuth credential readiness, refresh repairability, and
subscription usage separate truthful facts; serialize rotating-token lifecycle
mutations across processes; expose cached and explicitly synchronized account
usage without hidden model calls.

**Architecture:** Add one no-secret profile-state store for the latest refresh
witness and credential-bound account snapshot. Project OAuth lifecycle from the
credential row, token-store record, and latest typed witness while preserving
the existing API-key/environment availability contract. Put refresh, re-login
completion, and delete behind one bounded thread + process lock. Read ChatGPT
account limits through a version-pinned, bounded Codex app-server adapter that
never starts a thread/turn. Persist Claude SDK `RateLimitEvent` only when a
normal user request already emits it. Render those backend facts in the existing
Provider section with visibility/focus TTL behavior and a manual sync button.

**Tech stack:** Python 3.10, FastAPI, Pydantic, SQLite, `fcntl`, subprocess
JSONL, React, TypeScript, Vitest, pytest, multiprocessing.

---

## 0. Authority and boundaries

### 0.1 Reviewed authority

This plan implements only:

```text
docs/superpowers/specs/2026-08-08-oauth-lifecycle-quota-truth-design.md
reviewed commit: f2f12ba5e1dac6f20a53d733b80e85c6e0533d1e
worktree: /tmp/arkscope-oauth-lifecycle
branch: codex/oauth-lifecycle-quota-truth
```

Independent design review returned GREEN. Its two advisories are binding here:

1. availability behavior for `api_key` and environment-derived rows is frozen;
2. the terminal ownership of `llm_credentials.expires_at` is explicit in
   Section 1.3 below.

The official Codex app-server reference retrieved on 2026-08-08 is
<https://developers.openai.com/codex/app-server/>. It documents initialize /
initialized, external `chatgptAuthTokens`, `account/rateLimits/read`,
`account/rateLimits/updated`, and `account/usage/read`. External-token mode is
experimental, so this plan pins an allowlist rather than treating the protocol
as timeless.

### 0.2 Product scope

Owned behavior:

- local OAuth lifecycle projection;
- one latest bounded refresh witness per credential;
- one latest credential-bound account-usage snapshot;
- one cross-process lifecycle critical section;
- ChatGPT cached account read and bounded explicit sync;
- passive Claude `RateLimitEvent` capture;
- Provider Settings lifecycle/quota presentation and synchronization cadence.

Not owned:

- model catalog changes or new model ids;
- model/provider fallback, execution transport, prompts, agent loops, or task
  routing policy;
- broad Settings sticky navigation or page-cache implementation;
- API-key quota probing;
- Financial Datasets spend policy;
- Scripts Tranche B;
- scraping private dashboards;
- provider billing prediction.

### 0.3 Provider and secret boundary

All automated tests use token-store doubles, temporary profile databases,
pinned JSONL fixtures, and local child-process fixtures. They must not:

- contact OpenAI, Anthropic, ChatGPT backend, or any provider;
- start a model thread, turn, message, or completion;
- read the user's real token store, keyring, profile DB, `~/.codex`, or browser
  profile;
- inherit provider credentials; or
- serialize/log access tokens, refresh tokens, id tokens, raw account ids,
  authorization headers, or unredacted provider errors.

The 2026-08-08 exhausted-account experiment is dated grounding, not a test
fixture that authorizes another live call. Product tests replay only the redacted
protocol shape.

### 0.4 Canonical verification boundary

Focused development may run in the managed sandbox. Canonical backend admission
must run natively in a fresh exact-tip worktree because EIR-005 proved the
sandbox selector-wakeup incompatibility.

Pinned assets:

```text
/tmp/arkscope_asyncio_wakeup_probe.py
SHA-256 10647c1e64c49fc2e082701d7a735e40782620314c125cd103a9a3f9bb37bc2e
required native result {"callback_fired": true, "ready_count": 0, "wake_bytes": 0}

/tmp/eir002-green-baseline/arkscope_eir002_reporter.py
SHA-256 09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928

/tmp/eir002-green-baseline/run_native.sh
SHA-256 e7c963f1bc97125b70b435fb3c41bf4e59d501f0da561f2ef6d921c12083c84f

package-lock.json
SHA-256 5322cb03099b873066b7572c02db68a427ddc7509fdc9850cf9d8d3948a19f2c

node_modules/.package-lock.json
SHA-256 4dd5182f8111b54dd608344c45513f3b310f39321a3cc9832b60cefc2fa241ff
Node v22.14.0
```

Fresh native admission uses no `config/.env`, an existing empty `data/`, absent
`src/data`, and only the pinned `node_modules` link. Pre/post ordinary status,
ignored status, symlinks, `data`, and `src/data` are manifested. New artifacts
are quarantined by exact path; modification of a pre-existing file is a stop.

---

## 1. Concrete implementation contract

### 1.1 Product owners

| Path | Responsibility |
|---|---|
| `src/auth_drivers/oauth_status.py` | New closed lifecycle enum, projection, bounded telemetry/snapshot DTOs, and profile-state store |
| `src/auth_drivers/codex_account_usage.py` | New version-pinned app-server JSONL adapter and response validator |
| `src/auth_drivers/chatgpt_oauth_login.py` | Thread + process lifecycle lock and refresh witness writes |
| `src/auth_drivers/chatgpt_oauth_manager.py` | Re-login completion under the shared lock and post-success sync trigger seam |
| `src/auth_drivers/claude_code_sdk_driver.py` | Passive typed `RateLimitEvent` observer |
| `src/auth_drivers/factory.py` | Inject observation sink without changing driver selection |
| `src/model_credentials.py` | Lifecycle-aware credential inventory and runtime-resolution separation |
| `src/api/dependencies.py` | Singleton local observation store and bounded sync service |
| `src/api/routes/config_routes.py` | Local inventory, cached observation GET, explicit sync POST, exact invalidation |
| `apps/arkscope-web/src/api.ts` | Closed lifecycle/account DTOs and cached/sync client calls |
| `apps/arkscope-web/src/settings/ProviderSection.tsx` | Lifecycle/quota rendering, visibility/focus TTL, manual sync, exact invalidation |
| `apps/arkscope-web/src/i18n/resources/{en,zh-Hant}/settings.ts` | Lifecycle, used/reset, inferred remaining, unknown, and sync copy |

Names may move only through a reviewed plan amendment. Do not add a second
lifecycle owner in `model_credentials.py` or a second quota store in the
frontend.

### 1.2 Storage schema

`OAuthObservationStore` uses the existing local `profile_state.db`. It owns two
bounded tables, not append-only history:

```text
oauth_refresh_status
  credential_id PRIMARY KEY
  provider
  auth_mode
  last_refresh_attempt_at
  last_refresh_success_at
  last_refresh_error_at
  last_refresh_error_code
  last_refresh_error_detail
  updated_at

oauth_account_snapshot
  credential_id PRIMARY KEY
  provider
  auth_mode
  account_fingerprint
  source
  schema_version
  observed_at
  status
  payload_json
  updated_at
```

Requirements:

- rows are replaced atomically per credential; there is no unbounded event log;
- diagnostic text is normalized, redacted, and length-bounded before storage;
- account fingerprint is a credential-bound digest of the opaque account id;
  raw account id never leaves the token-store process boundary;
- account payload has an allowlisted typed shape; raw headers/responses are not
  stored;
- cached reads use no-create semantics when the DB/table is absent;
- deleting a credential removes its two observation rows inside the same
  lifecycle critical section;
- schema writes use the existing profile-state write permission path.

### 1.3 Terminal `expires_at` ownership

The shared SQLite column remains permanently mode-scoped rather than ownerless:

- `claude_code_oauth`: `llm_credentials.expires_at` is the canonical optional
  user-declared setup-token expiry and remains editable/displayable. Any old
  duplicate token-record expiry is ignored for lifecycle projection.
- `chatgpt_oauth`: token-store `StoredTokenRecord.expires_at` is the only live
  expiry. The DB column is ignored, is no longer written by login/refresh, is
  not editable in Settings, and may be physically removed only in a later
  schema-migration slice after a zero-reader census.
- `api_key` / `api_key_pool`: behavior remains unchanged; no expiry semantics
  are introduced.

This ruling prevents another two-owner drift while preserving the useful manual
Claude date field.

### 1.4 Lifecycle and runtime resolution are separate

`ProviderCredential.lifecycle_state` is the closed five-state set in the
design. For OAuth rows, `available` is derived as `lifecycle_state == "ready"`.
For non-OAuth rows, the existing availability calculation is byte-behaviorally
unchanged.

The runtime credential resolver must not reuse that display boolean as an OAuth
selection veto. An explicitly active OAuth row remains runtime-resolvable in
`refresh_required` or `refresh_failed_retryable` so its driver can enter the
existing typed refresh path. It must not silently select another credential or
provider. Missing/terminal/unverifiable token evidence still reaches the driver
as the selected credential and returns its typed auth error; no model call is
made before repair.

This is compatibility preservation, not a routing-policy change.

### 1.5 ChatGPT account adapter

V1 compatibility allowlist is exactly Codex app-server `0.147.0`. A version
change requires a reviewed fixture/schema update; semver range matching is
forbidden.

The adapter:

1. resolves the reviewed executable and verifies its exact reported version;
2. starts `codex app-server` in an isolated temporary `CODEX_HOME`;
3. initializes with experimental API capability and external
   `chatgptAuthTokens` supplied only in-memory;
4. reads `account/rateLimits/read` and bounded `account/usage/read`;
5. never calls thread/start, turn/start, responses, or model APIs;
6. validates account identity against the token-store account id before
   accepting data;
7. validates only allowlisted fields and records unknown optional fields as
   absent, not zero;
8. terminates the child and process group on success, protocol error, timeout,
   cancellation, or malformed output.

An unavailable adapter preserves the last good snapshot and its original
`observed_at`; it returns a typed current sync error separately. It never
relabels stale data as newly observed.

### 1.6 API surface

```text
GET  /config/credentials
  local lifecycle inventory only; no refresh, provider, or app-server call

GET  /config/credentials/{credential_id}/account-usage
  cached snapshot only; no network/process start

POST /config/credentials/{credential_id}/account-usage/sync
  bounded mutating control-plane sync; one in-flight call per credential
```

The sync route supports only `openai/chatgpt_oauth` in v1. Unsupported auth
modes return a typed error without process launch. The POST uses the existing
`profile_state_write` permission gate; the cached GET remains read-only and
no-create. Login/re-login/automatic refresh may invoke the same sync service
after token mutation completes; sync failure does not roll back a valid token
and does not make quota up.

Credential mutation invalidates only that credential's account read cache.
Credential list responses remain network-free.

### 1.7 Frontend cadence and copy

The Provider section first renders local lifecycle plus cached account data.
For the active ChatGPT credential it then syncs only when:

- the section is visible and the snapshot is absent or at least five minutes
  old;
- the window regains focus while the section is visible and the snapshot is at
  least five minutes old; or
- the user presses the sync button, subject to a ten-second single-flight
  cooldown.

There is no interval timer that contacts the backend while hidden. Reset
countdowns are local display timers and do not trigger sync.

Copy rules:

- direct `usedPercent` is labeled `已用` / `Used`;
- `100 - usedPercent`, if shown, is labeled `推算剩餘` / `Estimated remaining`;
- reset timestamp is rendered in the existing system-time formatter;
- missing values are `未知` / `Unknown`, never zero;
- lifecycle uses distinct retryable-refresh, re-login-required, and
  unverifiable states;
- cached data keeps its real `observed_at` when a new sync fails.

---

## 2. Exact node ledger

### 2.1 Canonical base

| Collection | Count | SHA-256 of canonical node stream |
|---|---:|---|
| backend full | 4581 | `6e4994bb664501cff75cb06dbad18db82ba68cbbe4b2b26c4d480250d7c4699f` |
| backend OAuth focused | 246 | `57583e93f68a62ef8a2ac82efa70fd3d5374957f0c2156d1f58f337daccfce07` |
| frontend full | 1077 | `3f5e9f5bbe88d5ac48015a8c9e9d669dcd649a53a2ac868fc8a98d21f8d7e4eb` |
| frontend ProviderSection focused | 8 | `08aad36811d22f5d7ca55f16891d17c5d2a2345f9f2ad4802c11db85e223b83a` |

Backend focused files:

```text
tests/test_model_credentials_characterization.py
tests/test_chatgpt_oauth_login.py
tests/test_chatgpt_oauth_driver.py
tests/test_chatgpt_oauth_manager.py
tests/test_chatgpt_oauth_routes.py
tests/test_oauth_import_route.py
tests/test_claude_code_sdk_driver.py
tests/test_credential_env_routes.py
```

The target focused set is those eight files plus the three new files named in
Section 2.3: `test_oauth_lifecycle_status.py`,
`test_oauth_cross_process_lock.py`, and `test_subscription_account_usage.py`.
No implicit directory-wide collection is used to obtain the target hash.

The base focused runtime is `246 passed`. The frontend canonical stream is
produced by the EIR-006 pinned JSON-decoding normalizer:

```text
/tmp/eir006_vitest_list_normalizer.py
SHA-256 955dca592d243505ced622a84e88a35160a3fa787ffb954f38a6a43e1a72fcac
```

### 2.2 Backend staged and final identities

| Stage | Delta from prior | Full count / SHA-256 | Focused count / SHA-256 |
|---|---:|---|---|
| base | - | `4581 / 6e4994bb664501cff75cb06dbad18db82ba68cbbe4b2b26c4d480250d7c4699f` | `246 / 57583e93f68a62ef8a2ac82efa70fd3d5374957f0c2156d1f58f337daccfce07` |
| lifecycle/store | `+11/-0` | `4592 / 7f9d48845e7d0a4cde3e5c3e91b944eccc3cbcaf4109c0d11a01ef9a72dbfc54` | `257 / b875fd44906f15fff83dee815516f6dc4b99ec1565a2777b0dbd1d88649faeef` |
| process lock | `+4/-0` | `4596 / b9056110d25f64dc399e176502871a118b091bd4c3a4714933cb348dbc1d7b40` | `261 / a4b9af293b9c17c9bb93e82c8b99b5a181f06c2ebb9ea023381013998904dca7` |
| account adapter/API | `+9/-0` | `4605 / 3b6cbd5ffbe0decccddb2914d422c650c50c58f72667ccb285f9cf4a74b20c08` | `270 / d9b03cc7320a697abdc4a9049957d390f690d5223e6e5cecd4429a7c34b09338` |
| Claude event final | `+3/-1` | `4607 / 5180502f7dfe577ca758db5fb8ebdfe9ca282730a8976adcf65b7ab19c1c2d74` | `272 / 6c706f9d524ba65adc9b143479c0477516a2f2bd16a766a28ef27a46f2a8c4a4` |

Final backend accounting is exactly `+27/-1`, net `+26`. Native admission
target is `4535 passed / 72 skipped / 0 failed`, all 4607 nodes seen, empty
non-passing stream.

### 2.3 New backend node ids

`tests/test_oauth_lifecycle_status.py`:

```text
test_expired_chatgpt_token_projects_refresh_required_and_not_available
test_expired_chatgpt_token_without_refresh_projects_reauth_required
test_missing_chatgpt_token_projects_reauth_required
test_unreadable_token_store_projects_unverifiable_without_guessing_reauth
test_retryable_refresh_failure_projects_separately_from_reauth_required
test_successful_refresh_projection_uses_token_store_expiry_not_credential_db
test_api_key_and_environment_availability_remain_unchanged
test_refresh_telemetry_keeps_only_latest_bounded_nonsecret_witness
test_chatgpt_db_expiry_is_ignored_while_claude_manual_expiry_remains_owned
test_lifecycle_api_payload_and_logs_exclude_secrets_and_raw_account_ids
test_refreshable_active_oauth_remains_runtime_resolvable_while_not_available
```

`tests/test_oauth_cross_process_lock.py`:

```text
test_two_processes_consume_one_rotating_refresh_token
test_cross_process_delete_cannot_be_followed_by_refresh_resurrection
test_cross_process_lock_timeout_is_retryable_and_never_runs_unlocked
test_cross_process_lock_releases_file_descriptors_on_success_and_failure
```

`tests/test_subscription_account_usage.py`:

```text
test_codex_account_sync_reads_limits_and_usage_without_starting_thread_or_turn
test_exhausted_account_fixture_preserves_usage_across_five_rate_limit_reads
test_account_sync_rejects_account_mismatch_without_replacing_last_good_snapshot
test_account_sync_rejects_unknown_protocol_and_preserves_last_good_snapshot
test_account_sync_requires_allowlisted_codex_version_and_cleans_child
test_cached_account_status_is_credential_bound_and_missing_is_unknown
test_account_routes_split_inventory_cached_read_and_mutating_sync
test_account_sync_is_singleflight_per_credential
test_listing_credentials_never_refreshes_or_contacts_provider
```

`tests/test_claude_code_sdk_driver.py`:

```text
test_stream_event_is_ignored_but_rate_limit_event_is_persisted
test_no_rate_limit_event_means_unknown_without_probe
test_rate_limit_event_snapshot_is_credential_bound_and_redacted
```

The only removed id is:

```text
tests/test_claude_code_sdk_driver.py::test_streaming_and_ratelimit_events_ignored
```

It evolves into the three explicit event contracts; no other existing node may
be renamed or removed.

### 2.4 Frontend identity

Seven nodes are added under the existing top-level test file and one new
`describe("ProviderSection OAuth lifecycle and account usage truth", ...)`:

```text
renders retryable refresh failure separately from re-login required
does not treat an expired OAuth credential as active or collapse setup
renders direct used percentage and reset time with inferred remaining labeled
renders missing account fields as unknown instead of zero
syncs a visible stale ChatGPT snapshot once without hidden polling
manual sync bypasses the TTL and observes the ten-second cooldown
credential mutation invalidates only the affected account snapshot
```

| Collection | Base | Target |
|---|---|---|
| frontend full | `1077 / 3f5e9f5bbe88d5ac48015a8c9e9d669dcd649a53a2ac868fc8a98d21f8d7e4eb` | `1084 / f0e5ecda1371f0559c1cc92af367b7e32daa91663ef2f316ed67e23129ee9637` |
| ProviderSection focused | `8 / 08aad36811d22f5d7ca55f16891d17c5d2a2345f9f2ad4802c11db85e223b83a` | `15 / 887a712a206a272d6db3e75c55a1d77ea2bfe032650186458a874c8495fe04bf` |

No existing frontend node may be renamed or removed. Before editing frozen
Settings fixtures, explicitly inspect `BASELINE_SECTIONS`, the
`settingsRegistry` frozen copy, and Settings CSS class-contract tests. A frozen
copy is not updated merely to follow new copy.

---

## 3. RED-first task sequence

### Task 0 - Re-ground and bank the base

- [x] Verify branch, merge base, clean worktree, git-crypt no-op config, and all
  pinned tool identities.
- [x] Recollect the four base streams and require the exact identities in
  Section 2.1.
- [x] Run the eight-file backend focused base and require `246 passed`.
- [x] Prove product tests have no live provider endpoints, real token-store
  paths, real profile paths, or credential inheritance.
- [x] Record protected-path SHAs for model routing, agent loops, prompts,
  Financial Datasets policy, Tranche B, and Settings navigation owners.
- [x] Stop for independent Task 0 review before product edits.

### Task 1 - Lifecycle projection and bounded store

- [x] Add all eleven lifecycle nodes first. Imports must be function-level so a
  missing new module produces test failures, not collection errors.
- [x] Confirm all eleven RED for absent lifecycle/store contracts.
- [x] Implement `oauth_status.py`, no-create reads, bounded writes, redaction,
  and the five-state projection.
- [x] Make OAuth `available` derived and freeze API-key/environment behavior.
- [x] Separate runtime OAuth resolution from display availability; do not add
  provider/credential fallback.
- [x] Apply the mode-scoped `expires_at` ruling from Section 1.3.
- [x] Require stage identity `4592/7f9d4884...` and
  `257/b875fd44...`, then run the focused stage GREEN.
- [x] Commit lifecycle/store as one reviewed family.

### Task 2 - Cross-process lifecycle lock

- [x] Add four real-process tests first and confirm RED under the current
  process-local lock.
- [x] Use two spawned Python processes, a temporary plaintext token store, one
  rotating-token test grant, explicit barriers, and bounded joins. A thread-only
  test is not equivalent.
- [x] Add one profile-local lock file per credential. Sanitize/hash the file
  name; create lock directories/files with restrictive permissions. Resolve
  the root as `ARKSCOPE_LOCK_DIR/oauth_credentials` when the reviewed test/
  runtime override exists, otherwise `<profile_state.db parent>/locks/oauth_credentials`.
- [x] Acquire the existing thread lock and a bounded POSIX `flock` before any
  token/cache/telemetry mutation. Missing `fcntl`, timeout, invalid path, or fd
  error fails closed with `refresh_failed_retryable`; never run unlocked.
- [x] Cover refresh, re-login completion, and delete with the same critical
  section. Browser wait and code exchange stay outside it.
- [x] Prove fd release after success and every raised path.
- [x] Require stage identity `4596/b9056110...` and
  `261/a4b9af29...`, then GREEN and commit.

### Task 3 - Bounded ChatGPT account adapter and API

- [x] Add nine adapter/store/route tests from Section 2.3 and confirm RED.
- [x] Build redacted fixtures for initialize, account identity,
  `account/rateLimits/read`, and `account/usage/read`; fixture fields may contain
  obvious sentinels proving raw account ids/tokens never leave the adapter.
- [x] Implement the exact `0.147.0` allowlist, isolated `CODEX_HOME`, bounded
  JSONL request ids, stdout/stderr limits, timeout, and child/process-group
  cleanup.
- [x] Reject thread/turn notifications or methods in the fixture transcript.
- [x] Store only validated typed fields and preserve the last good snapshot on
  current failure/account mismatch.
- [x] Add cached GET and explicit sync POST; inventory GET remains local-only.
- [x] Implement per-credential backend single-flight. Manual frontend cooldown
  is not a substitute.
- [x] Require stage identity `4605/3b6cbd5f...` and
  `270/d9b03cc7...`, then GREEN and commit.

### Task 4 - Wire refresh, login, delete, and exact invalidation

- [x] Record refresh attempt before the grant and success/error after it using
  stable codes; do not persist raw exceptions.
- [x] Successful refresh immediately changes lifecycle/expiry projection from
  token-store truth without a DB expiry write.
- [x] Re-login and import establish the correct mode-scoped expiry owner.
- [x] Credential delete removes token, discovery cache, refresh status, and
  account snapshot under the one lock; partial failure remains typed and does
  not resurrect state.
- [x] Login/re-login/refresh may request account sync only after the token
  mutation commits. Sync failure cannot roll back valid auth.
- [x] Re-run lifecycle, lock, account, existing route, manager, driver, import,
  discovery, and task-canary owners. Collection identity must not change.
- [x] Commit wiring separately so lifecycle/store and integration remain
  independently reviewable.

### Task 5 - Passive Claude RateLimitEvent capture

- [ ] Replace the one broad ignore node with the three explicit nodes from
  Section 2.3; confirm the persistence node RED before implementation.
- [ ] Continue ignoring ordinary `StreamEvent` and unrelated SDK events.
- [ ] Persist only allowlisted typed quota/reset fields from an event emitted by
  a normal user request. Absence is unknown and starts no request.
- [ ] Credential id/auth mode/observed time are required; raw event repr and
  unknown nested data are forbidden.
- [ ] Require final backend identities `4607/5180502f...` and
  `272/6c706f9d...`, then focused GREEN and commit.

### Task 6 - Provider Settings lifecycle and quota UI

- [ ] Add seven frontend nodes under the exact describe owner; confirm RED for
  missing state rendering/cadence/invalidation, not imports or fixture shape.
- [ ] Extend `api.ts` with closed typed DTOs and the cached/sync split.
- [ ] Render lifecycle-specific actions/status without one generic green pill.
- [ ] Render direct used/reset/overage fields, inferred remaining label, source,
  and `observed_at`; missing means unknown.
- [ ] Implement visibility/focus five-minute TTL, ten-second manual cooldown,
  and one local in-flight sync. No hidden interval poll.
- [ ] On add/import/login/re-login/activate/delete/update, invalidate only the
  affected credential snapshot and refresh local inventory immediately.
- [ ] Preserve the setup form/navigation guard, all secret-absence assertions,
  frozen Settings copy fixtures, and existing model-discovery behavior.
- [ ] Require focused `15/887a712a...`, full
  `1084/f0e5ecda...`, typecheck, build, and i18n scanner GREEN.
- [ ] Commit frontend/i18n as one family.

### Task 7 - Mutation, full admission, review, and merge

- [ ] Run each mutation in Section 4 against only its owning node, capture exact
  diff and RED reason, restore exact pre-mutation SHA, and re-run GREEN.
- [ ] Recollect all four final streams and require exact target identities.
- [ ] Run backend focused, relevant existing task-canary/discovery tests,
  frontend focused/full, typecheck, build, scanner, and secret/residue gates.
- [ ] Run native canonical admission with the pinned wakeup probe/wrapper and
  require `4607 seen`, `4535 passed / 72 skipped / 0 failed`, empty non-passing.
- [ ] Manifest/quarantine generated artifacts and prove worktree restoration.
- [ ] Produce a review packet containing node streams, protocol fixtures,
  process-lock timeline, child cleanup proof, mutation diffs, and secret-absence
  scans. Stop for independent implementation review.
- [ ] Only after GREEN review: fast-forward merge, fresh exact-master admission,
  and docs-only closeout. Do not push unless requested.

---

## 4. Required mutation sensitivity

| ID | Mutation | Owning proof must turn RED |
|---|---|---|
| M1 | Restore unconditional `available=True` for OAuth | expired token is not available |
| M2 | Read ChatGPT expiry from `llm_credentials.expires_at` | refresh projection uses token-store expiry |
| M3 | Collapse retryable refresh failure into `reauth_required` | retryable vs terminal node |
| M4 | Reuse display `available` as OAuth runtime veto | refreshable active OAuth remains runtime-resolvable |
| M5 | Remove/skip process flock while keeping thread lock | two processes consume rotating token once |
| M6 | Accept account mismatch or raw account id in snapshot | mismatch rejection and secret/redaction nodes |
| M7 | Convert absent usage to zero or replace last good snapshot on protocol error | unknown/preserve-last-good nodes |
| M8 | Drop Claude `RateLimitEvent` into the old ignore branch | passive event persistence node |
| M9 | Start account sync while Provider section is hidden or inside TTL | visible stale sync cadence node |
| M10 | Broadly clear all account snapshots after one credential mutation | exact affected-cache invalidation node |

A mutation is valid only when it changes the target semantic, not when it adds a
dead condition after an unreachable branch. Each mutation diff is retained in
the evidence packet.

---

## 5. Stop conditions

Stop and amend the plan before continuing if any of these occurs:

1. a base or target collection identity differs;
2. a new test is collected outside the exact ledger, or an existing id other
   than the one named Claude ignore node disappears;
3. RED is caused by collection/import/fixture/path errors rather than the absent
   contract;
4. a live provider, model, browser, real token store, keyring, profile DB, or
   `~/.codex` is touched by tests;
5. any secret/raw account id/raw header enters SQLite, logs, API, fixtures, or
   frontend state;
6. API-key/environment availability changes;
7. OAuth runtime resolution silently selects another credential/provider or can
   no longer enter refresh for an explicitly active refreshable row;
8. `llm_credentials.expires_at` gains a second owner or ChatGPT begins reading
   it again;
9. cross-process lock failure degrades to unlocked execution;
10. a lock or child-process fd survives success/failure;
11. app-server version/protocol is accepted outside the exact allowlist;
12. account sync starts a thread/turn/model request or falls back to paid API;
13. stale/mismatched account data is relabeled current or displayed for another
    credential;
14. Claude quota collection creates a probe request;
15. Settings adds hidden interval polling or permanently mounts unrelated
    groups;
16. a frozen Settings fixture is edited to follow product copy without explicit
    contract review;
17. model catalog/routing/defaults/prompts/agent execution, Financial Datasets,
    Tranche B, or broad Settings navigation changes;
18. canonical native admission cannot produce a complete reporter record;
19. a pre-existing repository artifact changes during admission; or
20. implementation needs an additional node, file owner, live experiment, or
    product ruling not listed here.

---

## 6. Review packet and completion definition

Independent review reconstructs, rather than trusts prose:

- four base and four target node streams;
- exact `+27/-1` backend and `+7/-0` frontend deltas;
- all protocol fixtures and app-server method ids;
- two-process rotating-token and delete/refresh timelines;
- fd/process-group cleanup on all terminal paths;
- lifecycle truth tables for ChatGPT, Claude, API-key, and env rows;
- mode-scoped `expires_at` ownership;
- cached-read versus sync route call graphs;
- frontend TTL/cooldown/invalidation behavior;
- all ten mutation diffs and owning REDs;
- complete native reporter and empty non-passing stream;
- protected-path and secret-absence scans.

The slice is complete only when the merged product:

1. never presents an expired OAuth token as ready;
2. distinguishes retryable refresh from re-login and unverifiable states;
3. serializes lifecycle mutation across processes;
4. reports direct quota/reset facts with source/time and honest unknowns;
5. makes no hidden model request for quota;
6. passively retains Claude quota only when already observed;
7. preserves all API-key/environment behavior and routing policy; and
8. has the exact green canonical baseline defined above.
