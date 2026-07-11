# S3 Credential-Lifecycle Hotfix — chatgpt_oauth re-login + delete cascade

> **Status: REVIEWED — CLEARED FOR IMPLEMENTATION 2026-07-11.** Roles: Claude authors + implements,
> user reviews. Origin: P2.7 live verification hit local:7 (openai
> chatgpt_oauth) failing discovery with a refresh-401; the user triaged it as a
> product lifecycle gap (five code claims, all independently verified) and
> adopted the six-item hotfix plus review additions A–E.
>
> **Scope ruling (user 2026-07-11): re-login machinery is chatgpt_oauth-ONLY.**
> The Anthropic claude_code_oauth token comes from `claude setup-token` with
> ~1-year validity — add-only re-import at a yearly cadence is acceptable, so no
> anthropic re-login is built and no follow-up is filed. The delete cascade
> (§3 D5) lives on the shared delete route and naturally covers BOTH providers.
>
> Interim guidance until this ships: do NOT delete local:7 (delete currently
> orphans its token — the very bug); no need to create a temporary duplicate row
> either, since re-login lands here and fixes local:7 in place.

## 1. Problem (all anchors verified 2026-07-11)

1. **Re-login doesn't exist.** `OAuthStartRequest` carries only `make_active`
   (src/api/routes/config_routes.py:453); `complete_login` unconditionally calls
   `add_oauth_credential(...)` (src/auth_drivers/chatgpt_oauth_login.py:329) —
   so "log in again" mints local:8 and strands local:7. Settings credential rows
   offer 儲存顯示資訊 / discovery / probe / delete only (grep 重新登入 = 0 hits).
2. **Delete orphans the token.** `delete_credential`
   (src/api/routes/config_routes.py:596) calls only `store.delete()`;
   `token_store.delete()` (src/auth_drivers/token_store.py:118) has zero
   callers. It also leaves the credential's P2.7 discovery-cache rows behind —
   pure hygiene, no resurrection hazard: `llm_credentials` id is
   `AUTOINCREMENT` (src/model_credentials.py:112), ids never reused.
3. **A dead token is opaque.** The driver returns
   `error="re-login needed (token refresh failed): …"` as free text
   (src/auth_drivers/chatgpt_oauth_driver.py:337); nothing machine-readable, the
   row keeps `available: true`, and the UI shows raw error text with no exit.
4. **Stale UI/caller commentary claims research is unwired.** The primary sites
   are Settings.tsx:2937 「AI 研究『執行』尚未接上…」 and api.ts:911
   ("execution is unwired … Research fail-closes when active"); matching stale
   rationale also survives in Settings.tsx:2487/:2742,
   credentialDisplay.ts:85, and two tests. In reality query.py:208 routes
   chatgpt_oauth research through `_openai_subscription_stream`. Wire-up is a
   code fact that has never passed live (S3 live P1/P2 pending); §7 closes the
   runtime claim and the ledger sweep closes every stale-code occurrence.

## 2. Non-goals

- Anthropic re-import in-place update (ruled out — header).
- Probe-path reauth affordance: the probe route loads the RAW stored token with
  **no refresh step** (config_routes.py:544) — an expired token shows as a
  failing P2 floor, which is honest. Discovery is the canonical health check.
- OAuth cache fingerprint per account-id: P2.7 keeps the constant `fp="oauth"`
  on BOTH read and write sides; the explicit cache clear (D3) is the
  compensating control. Account-scoped fingerprints = possible later
  refinement, noted in the map decision log, not built here.
- Persistent `needs_reauth` column on the credential row (review point E,
  decided minimal): this slice surfaces reauth on the discovery result + an
  inline re-login button. A durable row flag is follow-up only if the transient
  affordance proves insufficient live.

## 3. Design

**D1 — re-login threading (item 1).**
`OAuthStartRequest` gains `relogin_credential_id: str | None = None`. The start
route (config_routes.py:461) fail-fast validates a provided target: row exists
(else 404), `provider == "openai"` and `auth_type == "chatgpt_oauth"` (else
400); the `require_profile_state_write` detail gains the target id.
`OAuthLoginManager.begin()` (chatgpt_oauth_manager.py:71) gains
`relogin_credential_id: str | None = None` and threads it to `start_login()`
(chatgpt_oauth_login.py:134) → new `_PendingLogin.relogin_credential_id` field
(:95, default None) — carried in pending state exactly like `make_active`, so
BOTH completion paths (loopback `_await_callback` and copy-code
`complete_manual`) honor it and neither can bypass it.

**D2 — one lifecycle lock + recoverable in-place replacement (item 2 + review A).**
`chatgpt_oauth_login.py` exposes a small `oauth_credential_lock(credential_id)`
context manager backed by the existing `_lock_for()` map. `refresh_if_needed`,
re-login completion, and ChatGPT-OAuth deletion all use this SAME lock. The
lock covers only completion/storage work, never the user's browser interaction
or authorization-code exchange. **This is a process-local guarantee only.**
Within one sidecar it prevents an in-flight refresh from overwriting a newly
authorized token, or writing a refreshed old token back after deletion. Two
sidecars that share the same profile DB/token store do not share this Python
lock; the pre-merge live gate therefore runs with exactly one sidecar, and a
credential-scoped inter-process lifecycle lock is filed in §6.

`complete_login` gains
`invalidate_relogin_cache: Callable[[str], int] | None = None` and branches on
`pending.relogin_credential_id`; the callback is required only for a re-login:
- Enter `oauth_credential_lock(target)`, then re-validate the target at
  completion time (`credential_store.get`): missing
  row or wrong provider/auth_type → raise `ChatGPTOAuthLoginError`; **never
  fall back to creating a new row** (no-fallback boundary).
- Load the old token record for rollback. Run the required cache invalidator
  supplied by the manager (D3) BEFORE replacing the token. Cache invalidation
  failure aborts completion while token + profile metadata are still untouched.
- `token_store.save(credential_id=target, record=record)` follows. A save
  failure leaves the old token UNTOUCHED. The cache may already be empty, which
  is safe (the picker returns to `never_discovered`); it may never retain the
  previous account's entitlement after a re-login attempt.
- Then `credential_store.update(target, expires_at=record.expires_at or "",
  account_label=label)` (src/model_credentials.py update, verified: `""` forces
  NULL, `None` means don't-touch — a new token with no JWT exp must CLEAR the
  old expiry, hence `or ""`). **alias and active are NOT passed** — preserved
  by design (item 2). If update raises, make a best-effort attempt to restore
  the old token (or delete the new token when no old record existed) before
  propagating the ORIGINAL metadata error. If compensation itself fails, log
  that secondary failure without replacing the original exception. If
  `update()` returns None because the row vanished, apply the same best-effort
  cleanup. Normal rollback is tested; a double storage failure cannot honestly
  promise a clean terminal state. A failed re-login must never intentionally
  leave "token replaced, metadata row gone" as a terminal state.
- `pending.make_active` is IGNORED on this branch (D8).
- Return payload gains `"relogin": true` (same masked-metadata shape,
  credential_id == the target), `"discovery_cache_cleared": true`, and the
  deleted-row count. No successful result carries a false cache-clear flag.

**D3 — discovery-cache clear on re-login success (item 3 + review B).**
New `ModelDiscoveryCache.delete_scope(*, provider, credential_id,
auth_mode=None) -> int` (src/model_discovery_cache.py — currently only
`record_run`/`get`): one transaction deleting matching rows from BOTH tables
(`model_discovery_runs` + `model_discovery_models`); `auth_mode=None` = all
modes for that credential; returns total rows removed; idempotent.
Call site: `OAuthLoginManager._complete` (:133) supplies a required invalidator
callback to `complete_login` — NOT the route — so loopback and manual paths both
clear. The callback executes
`ModelDiscoveryCache(self._cs.db_path).delete_scope(provider="openai",
credential_id=target, auth_mode="chatgpt_oauth")` inside D2's lifecycle lock and
before token replacement. A clear failure fails the login completion with a
redacted actionable error; it is not downgraded to an ignored boolean because
the effective picker would otherwise continue serving old-account entitlement.
Effect: the P2.7 effective view for that credential returns to
`never_discovered` → the picker's existing 探索 nudge IS the re-verify
affordance; no new UI state invented. Old-account entitlement cannot linger.

**D4 — machine-readable reauth (item 4).**
`ChatGPTOAuthLoginError` (chatgpt_oauth_login.py:58) gains optional attrs
`status_code: int | None` and `reauth_required: bool` (constructor kwargs,
default None/False — all existing single-arg raise sites unchanged).
`_http_post` (:186) sets `status_code=exc.code` on the HTTPError path.
`refresh_if_needed` (:393) marks `reauth_required=True` on: missing stored
token (:413), missing refresh_token (:417), and any refresh exchange failure
whose `status_code in (400, 401)` (400 on a refresh grant ≈ invalid_grant).
`_http_post` already wraps an `OSError` as `ChatGPTOAuthLoginError` with
`status_code=None`; that wrapped shape stays transient.
Consumers:
- `discover_models` catch (chatgpt_oauth_driver.py:333): result gains
  `error_code="reauth_required"` when flagged, else None.
  `ModelDiscoveryResult` (src/model_credentials.py:81) gains
  `error_code: str | None = None` (additive; discovery route already
  duck-types via `model_dump()`, untouched).
- `_stream` catch (:452): the error event payload gains
  `"code": "reauth_required"` when flagged (additive dict key).
- The pre-refresh early exits are split, not collapsed. When BOTH
  `self._token_store` and `self._credential_id` exist but `_load_token()` finds
  no stored token, the OAuth metadata row is repairable by re-login:
  `discover_models` returns `missing_credential` with
  `error_code="reauth_required"`; `_stream` yields one classified error event
  with that code and returns. By contrast, a missing token-store dependency or
  missing credential id is driver wiring/configuration failure, which re-login
  cannot repair: discovery keeps `status="missing_credential"` with
  `error_code="missing_credential"`, and `_stream` yields the same classified
  code (never a bare `MissingCredentialError`), so the UI does NOT show a
  re-login affordance for those two arms.

**D5 — delete cascade (item 5 + review C; shared route, both providers).**
`delete_credential` (config_routes.py:596) gains
`token_store=Depends(get_oauth_token_store)`. New flow: resolve `cred` (404 if
None) → write gate → enter `oauth_credential_lock(credential_id)` and re-read
the row → clear discovery cache first → for OAuth rows load+delete the token →
delete the metadata row last.

- Cache-clear failure returns 502 before token/metadata mutation.
- OAuth token-store load/delete exception returns 502 and KEEPS the metadata
  row, so the user has a visible retry target. Because `KeyringTokenStore`
  deliberately collapses a backend delete exception to `False`, interpret the
  boolean against the preloaded record: old record present + `False` = cleanup
  not proven, return 502 and keep the row; old record absent + `False` = nothing
  secret remained and deletion may continue.
- If metadata deletion fails after a token was removed, best-effort restore the
  previously loaded token before returning an error. A restore failure is
  logged while the original metadata-deletion error remains authoritative.
  Cache rows need not be restored; an empty cache is safe and forces
  re-verification.
- Within one process, ChatGPT deletion shares D2's lock with refresh/re-login,
  so an in-flight old refresh cannot resurrect the token. Claude uses the same
  lock harmlessly even though its setup-token driver does not rotate. The
  cross-process residual risk and follow-up are explicit in D2/§6.

Response: `{"deleted": true, "id": …, "token_deleted": true|null,
"discovery_cache_rows_deleted": int}` (additive).
`token_deleted=true` means an existing OAuth token was confirmed removed;
`null` means no token cleanup was required (non-OAuth row or OAuth metadata
with no stored token). `false` is intentionally unreachable in a 200 response:
failure to prove deletion when a token was preloaded returns 502.

**D6 — frontend (items 1/4/6).**
- `api.ts`: `startOpenAIOAuth(makeActive = false, reloginCredentialId?:
  string)` — body gains `relogin_credential_id` only when provided (:910);
  `ModelDiscoveryResult` DTO gains `error_code?: string | null` (:147); the
  stale :911 comment is rewritten (item 6's second site).
- `chatgptOAuth.ts` keeps its existing poll/manual helpers; it has no start
  seam. The optional target is threaded by `api.ts` + `Settings.tsx` only
  (chatgptOAuth.test.ts remains the request-shape test home).
- `Settings.tsx`: `CredentialList` (exported, tested by CredentialList.test.ts)
  — chatgpt_oauth rows gain a 重新登入 button invoking the same login flow
  with the row's id; `DiscoveryResultView` (exported, tested) — when
  `error_code === "reauth_required"`, render 「token 已失效 — 重新登入」 with
  the button instead of bare error text (relogin trigger passed as an optional
  prop, so existing render sites stay valid). A row/result re-login first
  expands the OpenAI `SetupDisclosure`, where waiting/manual/cancel controls
  already live. Every ChatGPT login/re-login trigger is disabled while
  `pollBusy || manualBusy || oauth != null`, preventing two flows from racing
  for the fixed `:1455` callback port.
- Copy fix (Settings.tsx:2937), three-axis honest rewrite (exact zh wording at
  implementation, content fixed): AI 研究可走 ChatGPT 訂閱後端（experimental,
  本 slice live 驗證）；卡片合成／翻譯仍需 API key（fail-closed —
  `task_auth_executable` 契約）；discovery／probe 可用。**This copy flips only
  if §7's live research smoke passes** — if live fails, the copy line is
  reverted to accurate-negative before merge and a follow-up is filed.

**D7 — what re-login deliberately allows.** Logging into a DIFFERENT ChatGPT
account on the same credential slot is allowed (that's an account swap):
account_label updates, D3 wipes the old entitlement. Noted in tests.

**D8 — active-state invariance.** Re-login never touches `active` — not the
target's, not other rows' (no `UPDATE … SET active = 0` sweep on this branch).

## 4. Tasks (TDD — every test RED before its code)

**Task 1 — login core (chatgpt_oauth_login.py).**
Reuse the file's existing fakes: `_CredStore` (:80), `_TokStore` (:98),
`_seed` (:112), `_ok_exchange` (:60). `_CredStore` will need `get()`/`update()`
with the real store's semantics (`""` → clear, `None` → don't-touch) — extend
the fake, and per seam-mock discipline add ONE real-store test (below). Every
re-login core test supplies `invalidate_relogin_cache=lambda _target: 0`,
except the dedicated missing-invalidator test.
RED tests (tests/test_chatgpt_oauth_login.py):
1. `test_relogin_replaces_token_in_place` — seed cred local:1 + old token;
   start_login(relogin_credential_id="local:1") → complete_login → returned
   credential_id == "local:1", `relogin` true, token record replaced,
   store row count unchanged (no add), alias/active untouched,
   expires_at/account_label updated.
2. `test_relogin_token_save_failure_keeps_old_token` — `_TokStore.save`
   raises → raises ChatGPTOAuthLoginError; old record still loads;
   row metadata unchanged. (Sibling of :239's rollback test — inverted.)
3. `test_relogin_target_vanished_fails_no_new_credential` — target deleted
   after start → raises; `add_oauth_credential` never called; nothing written.
4. `test_relogin_wrong_target_type_rejected` — target is api_key (or
   anthropic oauth) row → raises; nothing written.
5. `test_relogin_ignores_make_active` — start with make_active=True +
   relogin target on an INACTIVE row → row stays inactive; active row
   elsewhere untouched.
6. `test_relogin_clears_expiry_when_new_token_has_none` — new token without
   JWT exp → row expires_at becomes NULL (the `or ""` contract).
7. `test_relogin_in_place_with_real_credential_store` — seed a REAL
   `CredentialStore` on a tmp path, re-login local:1 through a fake token store,
   and assert row count/id/alias/active invariance plus refreshed metadata —
   seam-mock discipline's real-shape test.
8. `test_refresh_failure_classification` — refresh HTTP 401 → raised error has
   `reauth_required is True` + `status_code == 401`; a
   `ChatGPTOAuthLoginError(status_code=None)` matching `_http_post`'s wrapped
   network-error shape → `reauth_required is False`; missing refresh_token →
   True; missing stored token → True. (Uses the existing monkeypatchable
   `refresh` seam without inventing a raw-OSError contract.)
9. `test_relogin_serializes_with_inflight_refresh` — a barrier-controlled
   refresh holds the credential lock; re-login completion waits, then writes
   last. Final token is the newly authorized token, never the refreshed old
   account token.
10. `test_relogin_metadata_failure_restores_or_deletes_token` — update raises
    with an old token present → when compensation succeeds, old token is
    restored; vanished row/no old token → new token removed.
11. `test_relogin_compensation_failure_preserves_original_error` — metadata
    update raises and rollback save/delete also raises → rollback failure is
    logged, but the original metadata error is the propagated cause; the test
    does NOT claim a clean token-store state after this double failure.
12. `test_relogin_requires_cache_invalidator` — relogin with no invalidator
    fails before token/profile mutation; create-login remains valid with the
    default `None` callback.

**Task 2 — cache delete_scope (model_discovery_cache.py).**
RED tests (tests/test_model_discovery_cache.py):
1. `test_delete_scope_removes_runs_and_models_scoped` — two credentials
   recorded; delete one scope → its rows gone from BOTH tables, count
   returned, the other credential's rows untouched.
2. `test_delete_scope_all_auth_modes_and_idempotent` — auth_mode=None wipes
   every mode for that credential; second call returns 0.

**Task 3 — manager + routes.**
RED tests (tests/test_chatgpt_oauth_manager.py, reusing `stores` fixture +
`_FakeServer`:52; tests/test_chatgpt_oauth_routes.py, handler-direct per house
rule):
1. manager: `test_begin_threads_relogin_target_to_completion` — begin(...,
   relogin_credential_id="local:1") → loopback completes → same id, no new
   row, result carries `relogin` + `discovery_cache_cleared`.
2. manager: `test_relogin_cache_clear_failure_aborts_before_token_replace` —
   cache raises → terminal error; old token/profile metadata unchanged; no
   success result and no stale effective-view claim.
3. routes: `test_oauth_start_validates_relogin_target` — unknown id → 404;
   api_key/anthropic target → 400; valid target → manager.begin called with
   the kwarg + gate detail includes it.
4. routes: `test_credential_delete_cascades_oauth_token_and_cache` — oauth
   row: recording fake token_store's `delete` called with exact scope triple;
   cache rows gone; response fields `token_deleted: true`,
   `discovery_cache_rows_deleted` ≥ 1.
5. routes: `test_credential_delete_api_key_skips_token_store` —
   `token_deleted: null`, cache still cleared, no token_store call.
6. routes: `test_credential_delete_token_store_failure_keeps_retryable_row` —
   token_store.delete raises → 502; credential row and token remain.
7. routes: `test_credential_delete_false_with_loaded_token_keeps_row` — a
   keyring-shaped fake loads an old record but returns False from delete; route
   returns 502 and retains the row (False is not treated as proof of absence).
8. routes: `test_credential_delete_with_real_plaintext_token_store` — REAL
   `CredentialStore` + `PlaintextTokenStore` + dummy OAuth row/token/cache;
   delete removes all three without real authentication.
9. routes: `test_delete_serializes_with_inflight_refresh` — barrier-controlled
   refresh finishes before delete; final state has no metadata row and no token
   (the process-local old refresh cannot resurrect it).
10. routes: `test_credential_delete_oauth_without_stored_token_returns_null` —
    OAuth metadata row exists but the preloaded token is absent; deletion may
    continue and the 200 response reports `token_deleted: null`, never false.

**Task 4 — driver error_code (chatgpt_oauth_driver.py + ModelDiscoveryResult).**
RED tests (tests/test_chatgpt_oauth_driver.py, existing seam style):
1. `test_discover_models_refresh_401_sets_reauth_error_code` — refresh seam
   raises flagged error → result.status "error",
   `error_code == "reauth_required"`, seeds still listed as candidates.
2. `test_discover_models_transient_failure_has_no_error_code` — network-style
   failure → error_code None.
3. `test_stream_refresh_401_event_carries_code` — `_stream` error event
   payload has `code == "reauth_required"`.
4. `test_discover_missing_token_requires_reauth` — an existing OAuth metadata
   row, token-store dependency, and credential id are all present, but the
   token record is absent → `missing_credential` + reauth error_code.
5. `test_stream_missing_token_yields_reauth_event` — no bare exception; one
   classified reauth error event and no backend call, with store/id present.
6. `test_discover_missing_driver_wiring_is_not_reauth` — missing token-store
   dependency and missing credential id (parameterized) return
   `missing_credential` with `error_code="missing_credential"`, not
   `reauth_required`.
7. `test_stream_missing_driver_wiring_yields_non_reauth_event` — the same two
   wiring arms yield one classified `missing_credential` event and no backend
   call; no bare exception and no re-login code.

**Task 5 — frontend (`api.ts`, `Settings.tsx`, `credentialDisplay.ts`, and
their existing focused tests; `chatgptOAuth.ts` remains unchanged).**
House harness (createRoot/act/vi.stubGlobal). RED tests:
1. chatgptOAuth.test.ts: start with relogin target → fetch body carries
   `relogin_credential_id`; without → key absent.
2. CredentialList.test.ts: chatgpt_oauth row renders 重新登入; clicking calls
   the handler with the row id; api_key + claude_code_oauth rows do NOT render
   it (scope ruling pinned in UI); busy=true disables the action.
3. DiscoveryResultView.test.ts: `error_code: "reauth_required"` → renders the
   re-login affordance (and not for a plain error); busy=true disables it.
4. ProviderSection integration test (`ProviderSection` becomes exported like
   the neighboring testable settings sections): clicking row/result re-login
   opens the OpenAI setup disclosure and exposes waiting/manual/cancel status
   in the same visible region; a second trigger cannot start while one flow is
   active.
5. Copy assertion: 尚未接上 absent; new copy present (exact string pinned).
Then typecheck + build.

**Task 6 — gates, A/B, review-ready.**
Run the focused gates exactly:

```bash
pytest -q \
  tests/test_chatgpt_oauth_login.py \
  tests/test_model_discovery_cache.py \
  tests/test_chatgpt_oauth_manager.py \
  tests/test_chatgpt_oauth_routes.py \
  tests/test_chatgpt_oauth_driver.py \
  tests/test_model_routing.py
npm --prefix apps/arkscope-web test -- \
  chatgptOAuth.test.ts CredentialList.test.ts DiscoveryResultView.test.ts \
  ProviderSection.test.ts credentialDisplay.test.ts
npm --prefix apps/arkscope-web run typecheck
npm --prefix apps/arkscope-web run build
python src/smoke/pg_unreachable_e2e.py
```

Expected: focused tests/typecheck/build green; smoke reports `ok:true` and
`pg_attempts:[]`. Then run the existing no-PG static gate and full virgin A/B
per house protocol (git archive both sides from the main repo, sequential full
pytest, failure SETS + collect-diff
accounting; expected: identical failure sets, passed +N == collected +N).
Then review-ready hand-off; §7 live gate BEFORE merge.

## 5. Ledger sweep (checked at RED time, per plan-test-layer discipline)

- `manager.begin` call-shape assertions in test_chatgpt_oauth_manager.py /
  test_chatgpt_oauth_routes.py (:97/:148 region) — additive kwarg; any strict
  `assert_called_with(make_active=…)` needs the new kwarg accounted.
- Handler-direct callers of `delete_credential(...)` in ALL test files — the
  new `token_store` Depends param changes the direct-call signature; grep
  `delete_credential(` and update fakes.
- `ModelDiscoveryResult` gains a field → grep exact `model_dump()` dict
  comparisons (test_chatgpt_oauth_routes.py is subset-style since P2.7;
  test_model_credentials_characterization.py and test_chatgpt_oauth_driver.py
  may pin exact shapes).
- `_PendingLogin` repr test (:259) — new field must not leak the verifier;
  repr stays masked.
- CredentialList / DiscoveryResultView existing render sites — new props are
  optional; no churn expected, verify.
- api.ts `startOpenAIOAuth` runtime caller Settings.tsx:2590; request-shape
  tests live in chatgptOAuth.test.ts. `chatgptOAuth.ts` itself has no start call.
- Stale-copy sweep includes Settings.tsx:2487/:2742/:2937,
  credentialDisplay.ts:85, api.ts:911, test_chatgpt_oauth_routes.py:70, and
  chatgptOAuth.test.ts:31. Gate those scoped files for `execution is unwired`,
  `尚未接上`, and `fail-closed Research`; default-off remains valid but its
  rationale becomes "do not silently switch the active credential."

## 6. Out-of-slice follow-ups (filed, not built)

- Durable `needs_reauth` on the credential row (only if live shows the
  transient affordance is not enough).
- OAuth cache fingerprint = account-id (would let P2.7's fingerprint-mismatch
  machinery subsume D3's manual clear; touches read+write convention).
- **Cross-process credential lifecycle lock.** The Python `_lock_for()` map is
  process-local, while desktop and standalone sidecars can share the same
  profile DB/token store. A follow-up must add a credential-scoped advisory
  file lock (for example `flock`) held across the FULL
  load/refresh/save/re-login/delete critical section. `PlaintextTokenStore`'s
  read-modify-write operations also need this lock to prevent lost updates;
  locking `_write_all()` alone is insufficient because a stale refresh can be
  computed before the lock and written after a re-login.

## 7. Live verification gate (BEFORE merge; order matters)

1. I stop every standalone/old sidecar, restart exactly ONE sidecar on the
   branch, regression-check discovery on
   local:3 (api_key, must stay `ok`/cached) and confirm local:7 discovery now
   returns `error_code: "reauth_required"`.
2. **User performs the browser auth** (I never handle login credentials):
   Settings → local:7 列 → 重新登入 → complete. I verify from outside: same
   `credential_id` local:7, alias 「ChatGPT subscription Plus」 preserved,
   active flag unchanged, token replaced (probe P1/P2), old cache rows gone.
   The one-sidecar precondition remains in force until this lifecycle window
   completes; starting 8420 or another desktop sidecar during re-login is a
   stop condition.
3. I run discovery on local:7 → expect live ChatGPT-backend list (status `ok`,
   provider_api models, cache row lands with fresh discovered_at).
4. Research live smoke (S3 live P1/P2, closes the copy claim): temporarily
   activate local:7 (openai), run ONE minimal ai_research query through the
   subscription backend, verify stream completes; restore local:3 active +
   original routes verbatim. If this step FAILS: revert the :2937/:911 copy to
   accurate-negative, keep the lifecycle fixes, file the execution bug as S3
   follow-up — merge decision returns to the user.
5. Delete-cascade live check: create a throwaway api_key credential, delete
   it, confirm response fields + zero cache rows. OAuth cascade is exercised
   with a dummy row/token in a temporary `PlaintextTokenStore` integration
   test; no real OAuth credential is sacrificed.

## 8. Review log

- Round 1 (2026-07-11): 4 must-fix + 3 should-fix accepted. Fixed delete
  fail-open ordering, shared refresh/relogin/delete lifecycle locking,
  post-save orphan cleanup, missing-token early exits, mandatory cache
  invalidation, collapsed/busy re-login UI, full stale-copy sweep, and a real
  temporary token-store cascade test. Broad Settings model IA redesign remains
  P2.8; this hotfix changes only the re-login path it owns.
- Round 2 (2026-07-11): 2 must-fix + 2 should-fix accepted with one technical
  strengthening. The lifecycle lock is now explicitly process-local; live
  re-login requires one sidecar and the follow-up calls for a full
  credential-scoped inter-process critical section (not merely a locked final
  write). Missing driver wiring is separated from a genuinely absent token, so
  only the latter offers re-login. Rollback is explicitly best-effort under a
  double storage failure, and successful delete responses use
  `token_deleted: true|null` with false reserved for no successful response.
- Round 3 (2026-07-11): independent re-check GREEN. The reviewer verified the
  process boundary/live gate/inter-process follow-up, the three-way missing
  credential split, best-effort compensation semantics, and the
  `token_deleted: true|null` response/test shape against current code. No open
  plan findings remain; Task 1 may start.
