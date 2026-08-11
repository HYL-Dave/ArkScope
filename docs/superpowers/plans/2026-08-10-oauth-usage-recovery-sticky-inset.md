# OAuth Usage Recovery and Settings Sticky Inset Implementation Plan

> **Status:** TASKS 0-6 COMPLETE; TASK 6 CLOSEOUT AT `a8f91bf8`
> INDEPENDENTLY FABLE-REVIEWED GREEN; IMPLEMENTATION/CUTOVER LINE CLOSED;
> TASK 7 NOT STARTED AND STILL REQUIRES EXPLICIT USER AUTHORIZATION
>
> **Date:** 2026-08-10
>
> **Design authority:**
> `docs/superpowers/specs/2026-08-09-oauth-usage-recovery-sticky-inset-design.md`
> at re-grounded commit `1c6774fd` (design GREEN at `43ae7ef9`, amendment GREEN
> at `14e360e3`, re-grounding GREEN at `1c6774fd`; rebased byte-equivalents
> `feb8403d`/`70f86bb9`).
>
> **Product grounding base:** `8cf85597d866c6d9cd0b75c75a24f86d73ca65a1`
> (docs-only Tranche B closure over product tip `e2706592`).
>
> **Roles (design LD 11, amended by §0.1.2):** Fable wrote this plan and
> the Task 0-3 product edits landed through `9bf2b9bd`. From the Task 3
> ownership refactor onward the roles swap: Codex implements the refactor
> and its tests; Fable writes plan amendments and performs the
> implementation review from raw artifacts; the user issues final product
> rulings. The reviewer of record never patches the implementation under
> review.

**Goal:** make ChatGPT account sync work on the real NVM/npm launcher, split
the three account-usage failure channels so the UI reports evidence instead of
`cached_read_failed` for everything, give the Claude row an explicit
cost-labeled manual quota probe, and remove the 20/12-pixel dead band above
the sticky Settings workflow row.

---

## 0. Authority, environment, and boundaries

### 0.1 Reviewed authority

This plan implements only the re-grounded design above. Design LD 1-LD 11,
the closed adapter error vocabulary, the probe wire shape proven live on
2026-08-09 (`wire_shape_accepted=true`, one request, HTTP 200; script
`18bc30a82dbf719a9332def3a5e1b649d5e98ff96ca54d06ef5477c61abc65bd`, redacted
artifact `36fa0d9c588b2a831caa651f05b8a37b75f4012fe44f003f10ea12d5798901d8`),
and the 16-row §2.6 identity table (normalized stream
`a15d95a129c7e12c17cd2282c9b62765e20035da285a9a09df3b2b76cd27a2fb`) are
admission inputs and are not reinterpreted here.

### 0.1.1 User ruling 2026-08-10: manual-only synchronization

After Task 2 review the user ruled that every provider synchronization POST
is manual-only: the ChatGPT visible/focus automatic sync (design LD 5) is
retired together with the never-built Anthropic automatic path. Even a
`max_tokens=8` probe consumes input tokens; the ChatGPT control-plane read
is provider traffic. Automatic behavior is exactly: the local cached GET,
its one bounded retry, focus revalidation of the CACHED read under the
five-minute policy, and passive `RateLimitEvent` observation. Page load,
focus, visibility, and idle send zero sync POSTs for every provider; the
per-credential manual button (ten-second cooldown, single-flight) is the
only sync trigger. This ruling supersedes the design's LD 5
ChatGPT-automatic clause and this plan's earlier §1.3 carry-over; the
design text remains dated authority.

Ledger impact: the sole automatic-sync owner cannot keep a name that says
"syncs ... once" while asserting it never auto-syncs; a lying test name is
inadmissible. It is therefore an exact `-1/+1` rename to the truthful ID
`does not sync stale ChatGPT usage without an explicit manual click`
(same describe block, removed and added in the same Task 3 RED commit).
Backend numbers are untouched; the rename itself is count-neutral, and
the frontend stage, focused, and Settings-projection identities are the
section 2 tables as re-derived under the §0.1.2 refactor ruling. The
retained-evolve set stays at exactly two nodes.

### 0.1.2 Ruling 2026-08-10: bounded state-ownership refactor and role swap

Three review rounds on Task 3 traced every real defect (channel overwrite,
deferred-GET race, cache resurrection, dropped authoritative snapshot) to
one causal seam: the account observation has DUPLICATED ownership between
component state and the Settings read cache, including a second hand-written
generation layer. Symptom patching stops here; Task 3 concludes with a
bounded refactor instead:

1. one pure reducer is the only owner of snapshot, read state, and sync
   state (no side effects inside the reducer);
2. one `useOAuthAccountUsage` hook is the only owner of cache interaction,
   epoch admission, retry, cooldown, and the manual POST; it performs cache
   operations and dispatches facts into the reducer;
3. the Settings cache stores the durable SNAPSHOT only — never a full
   `OAuthAccountSyncView` carrying transient sync status;
4. `ProviderSection` only lists credentials and renders reducer state;
5. backend DTOs, both adapters, and the generic `settingsReadCache` are
   frozen — this is not an app-wide rewrite.

Ownership locks (review-enforced):
- the cache generation governs ONLY cache storage and in-flight loader
  discard;
- the hook epoch governs ONLY credential-instance/async event admission;
- the hook may not hand-write another cache race layer (every mutation
  invalidates — raising the cache generation — before any replace, so an
  older in-flight GET always completes as discarded).

Roles for the remainder of Task 3 (executing the standing A/B agreement):
Fable wrote this amendment and the re-pinned ledger and now STOPS editing
product code; Codex reviews this amendment, then implements the refactor
and its tests; Fable performs the implementation review from raw artifacts;
the user issues the final product ruling. Task 4 (sticky inset) stays
paused until the refactor is GREEN.

The committed Task 3 symptom fixes (`b757d347`, `d679d95c`, `9bf2b9bd`)
are SUPERSEDED internals: their nine behavior nodes remain the binding
regression corpus (IDs frozen; assertion bodies may adapt to the refactored
internals without weakening the asserted behavior), while their component
state logic is replaced wholesale.

### 0.2 Owned and excluded behavior

Owned:

- `CodexAccountUsageAdapter` launcher/target dual-path resolution, isolated
  `PATH` composition, bounded shebang inspection, and the
  `interpreter_unavailable` / `version_incompatible` split;
- a new bounded Anthropic manual account adapter, its snapshot source value,
  and its dispatch from the existing account-sync service;
- the frontend split of cached-GET, sync-transport, and decoded-backend
  failure states, one bounded automatic cached-GET retry, a provider-free
  **Retry local read** action, and the cost-labeled Claude manual sync
  button with bilingual copy;
- the Settings-scoped top-inset transfer (scroll owner drops its top padding;
  a Settings lede element owns the responsive 20/12-pixel breathing room);
- the §2.4 authority-wording correction in
  `docs/design/LLM_AUTH_DRIVER_PLAN.md`; and
- deterministic backend, frontend, browser, host-live, and collection
  evidence.

Excluded (unchanged spec §6): OAuth login/refresh/token-store/credential DB
schema; the Claude Agent SDK research driver and OpenAI research execution;
any automatic Anthropic probing; model catalog/defaults; Settings groups,
directory, cache policy, or active-only mounting; Tranche B artifacts;
score-row and `config/scoring_keys.txt` dispositions.

`apps/arkscope-web/src/api.ts` already exposes the sync POST and cached GET.
Its only authorized change is one exact line: the closed
`OAuthAccountSource` union at `api.ts:210` gains the single member
`"anthropic_oauth_probe"`. Every other `api.ts` byte is protected; a second
`api.ts` hunk is a stop condition. The existing diagnostic route
`POST /config/credentials/{id}/probe` and `src/auth_drivers/claude_oauth_probe.py`
(P3b evidence: the token is NOT an `x-api-key`) remain byte-identical; the new
quota adapter is a separate module and does not touch that route.

### 0.3 Pinned toolchain

```text
package-lock.json
SHA-256 5322cb03099b873066b7572c02db68a427ddc7509fdc9850cf9d8d3948a19f2c
node_modules/.package-lock.json
SHA-256 4dd5182f8111b54dd608344c45513f3b310f39321a3cc9832b60cefc2fa241ff
Node v22.14.0 · Vite 5.4.21 · Vitest 4.1.8
decoded-list normalizer /tmp/eir006_vitest_list_normalizer.py
SHA-256 955dca592d243505ced622a84e88a35160a3fa787ffb954f38a6a43e1a72fcac
deterministic pytest reporter /tmp/eir002-green-baseline/arkscope_eir002_reporter.py
SHA-256 09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928
native wrapper /tmp/eir002-green-baseline/run_native.sh
SHA-256 e7c963f1bc97125b70b435fb3c41bf4e59d501f0da561f2ef6d921c12083c84f
anthropic SDK 0.120.2 (runtime precondition only; tests inject fakes)
Python Playwright 1.58.0 · Google Chrome 150.0.7871.128
```

The isolated implementation worktree uses only the pinned root `node_modules`
symlink; no `npm install`, no lockfile change, no provider request in any
test. The wrapper interface is one STAGE argument with cwd at repo root.

### 0.4 Plan-author grounding (executed by Fable on 2026-08-10)

| Gate | Result |
|---|---|
| backend full collection | `4,282 / 281cad976a2df29224f41d7442f39ee6deb5b78165fb9efe3945bee6d520abe3` |
| frontend full decoded collection | `99 files / 1,124 / da69a2942c03e4794e3384e6125936f9f25c1fafbad7d006b67025f8fd97bc39` |
| canonical native (my own control at the Tranche B tip, byte-identical report `252535bf...`) | `4,253 passed / 29 skipped / 0 failed` |
| backend focused baseline (section 2.5 four files, one command) | `61 passed / 0 failed` |
| frontend focused baseline (section 2.6 three files, one command) | `33 passed (3 files)` |
| Settings focused regression identity | `221 / a2c20d3607e5fd48982b4e1620089a7b59ee7346c23fc2d2709ec2935bdfe16f` |

All four collection baselines were rebuilt from raw decoded streams with the
pinned normalizer/reporter, not prose.

### 0.5 Byte-protected owners

The following paths must remain byte-identical through every task of this
plan (Git blob comparison against `8cf85597`):

```text
apps/arkscope-web/src/ui/Tabs.tsx
apps/arkscope-web/src/ui/Tabs.test.tsx
apps/arkscope-web/src/settings/settingsRegistry.ts
apps/arkscope-web/src/settings/settingsRegistry.test.ts
apps/arkscope-web/src/settings/settingsCopy.test.ts
apps/arkscope-web/src/settings/settingsReadCache.ts
apps/arkscope-web/src/settings/settingsReadCache.test.ts
apps/arkscope-web/src/InvestorProfilePanel.tsx
apps/arkscope-web/src/SettingsInvestorProfileIntegration.test.tsx
src/auth_drivers/claude_code_sdk_driver.py
src/auth_drivers/claude_oauth_probe.py
src/auth_drivers/chatgpt_oauth_login.py
src/auth_drivers/chatgpt_oauth_driver.py
src/auth_drivers/token_store.py
src/api/routes/config_routes.py
tests/test_claude_code_sdk_driver.py
tests/test_claude_oauth_probe.py
```

`apps/arkscope-web/src/api.ts` is byte-protected except the single
authorized union-member line above (Tranche B `test_sa_tools` bounded-delta
precedent: the pre/post file diff must contain exactly that one-line hunk).
All other Python/backend paths outside the section 1 owners are also
byte-protected; the backend collection may change only by the exact ledger in
section 2. Production data, `profile_state.db` bytes outside test fixtures,
and `config/scoring_keys.txt` are untouched.

### 0.6 Owned paths

| Group | Owners |
|---|---|
| Codex adapter | `src/auth_drivers/codex_account_usage.py` |
| Anthropic adapter | new `src/auth_drivers/anthropic_account_usage.py` |
| snapshot source enum + service dispatch | `src/auth_drivers/oauth_status.py`, `src/api/dependencies.py` |
| backend tests | `tests/test_subscription_account_usage.py`, new `tests/test_anthropic_account_usage.py` |
| frontend recovery + button | `apps/arkscope-web/src/settings/ProviderSection.tsx`, `apps/arkscope-web/src/ProviderSection.test.ts` |
| ownership refactor | new `apps/arkscope-web/src/settings/oauthAccountUsageReducer.ts`, new `apps/arkscope-web/src/settings/useOAuthAccountUsage.ts`, new `apps/arkscope-web/src/settings/oauthAccountUsage.test.ts`, `apps/arkscope-web/src/Settings.tsx` (idle-warmup account loader only) |
| sticky inset | `apps/arkscope-web/src/Settings.tsx`, `apps/arkscope-web/src/settings/settings.css`, `apps/arkscope-web/src/SettingsCss.test.ts`, `apps/arkscope-web/src/styles.css` (bounded: exactly one added declaration inside the existing `@media (max-width: 760px)` block, per §1.4) |
| bilingual copy | `apps/arkscope-web/src/i18n/resources/en/settings.ts`, `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts` |
| authority wording | `docs/design/LLM_AUTH_DRIVER_PLAN.md` (only the C-row/`C ≠ D` overbreadth; the x-api-key fact stays) |
| plan/evidence | this plan, its evidence file, `PROJECT_PRIORITY_MAP.md` |

---

## 1. Concrete implementation contract

### 1.1 Codex launcher repair (design LD 2)

`_resolve_executable()` returns a `(launcher, target)` pair: `launcher` is the
`shutil.which()`/explicit path **without** symlink resolution (validated
file/executable); `target` is `launcher.resolve()` used for inspection only.
`_isolated_environment()` builds `PATH` as, in order: launcher parent, target
parent when different, `/usr/bin`, `/bin`. `Popen` always receives the
launcher path.

Before `--version`, the adapter reads a bounded first line of the target
(4,096-byte cap). `#!` followed by `/usr/bin/env NAME` or an absolute
interpreter path is accepted only when `NAME`/basename matches
`^[A-Za-z0-9._-]{1,32}$`; the adapter then proves the interpreter resolves
inside the isolated `PATH` (or the absolute path is executable). A missing
interpreter returns typed `interpreter_unavailable` without spawning. A
non-shebang binary skips the check.

The version-check outcome classification becomes exact (today
`codex_account_usage.py:514` collapses every branch into
`version_incompatible`; this plan splits them and locks each with a node):

| Branch | Typed code |
|---|---|
| spawn `OSError` / timeout | `adapter_unavailable` (existing) |
| shebang interpreter absent from isolated `PATH` | `interpreter_unavailable` (new) |
| version command exits non-zero | `adapter_unavailable` |
| stdout > 256 B or stderr > 4,096 B | `protocol_incompatible` (existing default class) |
| exit 0 but output not matching `^codex-cli [0-9]+\.[0-9]+\.[0-9]+$` | `protocol_incompatible` |
| exit 0, well-formed, different version | `version_incompatible` |

The app-server spawn uses the same launcher/PATH composition.

### 1.2 Anthropic manual adapter (design LD 6-LD 8)

New `src/auth_drivers/anthropic_account_usage.py`, mirroring the Codex
adapter's shape:

- constructor takes an injectable SDK client factory (tests inject fakes; no
  test may construct a real transport);
- `read_account_usage(credential_id, record, observed_at)` sends exactly one
  Messages request: `Anthropic(auth_token=record.access_token, api_key=None,
  timeout=20.0, max_retries=0)`, `model="claude-sonnet-5"` (registry-pinned;
  a registry change stops the line for a model-identity amendment),
  `max_tokens=8`, OAuth beta `oauth-2025-04-20`, the exact Claude Code
  identity system block first, one fixed user message, no tools/stream/
  fallback;
- reads only the unified headers
  (`anthropic-ratelimit-unified-{5h,7d}-{status,utilization,reset}`, overall
  `-status`/`-reset`, `-overage-status`, `-overage-disabled-reason`,
  `-representative-claim`); `-fallback-percentage` is explicitly ignored;
- utilization must parse as finite `[0, 1]` and is stored as
  `used_percent = utilization * 100`; resets must parse as absolute Unix
  seconds; malformed fields become `None`, never `0`;
- HTTP 2xx with valid headers → observation; 429 with valid headers →
  observation with rejected status; 429 without them →
  `quota_headers_unavailable`; 401/403 → `provider_auth_rejected` /
  `provider_access_rejected`; timeout/transport keep their own classes; every
  failure preserves the last good snapshot;
- the snapshot writes through the existing
  `OAuthObservationStore.record_account_snapshot` with the new source value
  `anthropic_oauth_probe` (the `source` Literal in `oauth_status.py:118`
  gains exactly this one member) and the passive driver's
  `sha256(provider + NUL + auth_mode + NUL + credential_id)` fingerprint;
- an SDK that cannot express the pinned call shape (missing `auth_token`
  or raw-response support) is typed `sdk_incompatible` without any request;
  a provider 4xx other than 401/403/429 is typed
  `provider_request_rejected`; both preserve the last good snapshot;
- no response body, generated text, token, account identity, or raw header
  map reaches SQLite, logs, DTOs, exceptions, or evidence.

`OAuthAccountSyncService._sync_once` dispatch becomes explicit:
`openai/chatgpt_oauth` → Codex adapter; `anthropic/claude_code_oauth` →
Anthropic adapter under the same credential lock, single-flight, and
generation checks; every other pair stays `unsupported_auth_mode`.

### 1.3 Frontend recovery split (design LD 3-LD 5, LD 9)

Per the §0.1.2 refactor ruling, account state per local credential lives in
ONE pure reducer (`oauthAccountUsageReducer.ts`):

```text
snapshot:    the single authoritative validated OAuthAccountSnapshot | null
cachedRead:  idle | loading | loaded | failed   (+ failed error code)
syncSend:    idle | sending | transport_failed  (+ transport error code)
backendSync: last decoded sync_error_code | null
```

The reducer is side-effect free and holds NO admission counter; per the
§0.1.2 ownership lock, epoch admission belongs to the hook alone.
`useOAuthAccountUsage.ts` is the only caller of the Settings cache, the
only owner of epoch/retry/cooldown/single-flight, and dispatches facts
(decoded outcomes, timer fires, cache results) into the reducer; a
completion from a superseded epoch is discarded by the hook BEFORE
dispatch, so the reducer only ever receives admitted facts. The cache stores validated SNAPSHOTS only — the
idle-warmup account loader in `Settings.tsx` switches to the hook module's
exported validated-snapshot loader so every cache write path shares one
shape (witnessed by the `every cache write stores a validated snapshot
only` node). No transient `sync_status` ever enters the cache.

Rules: one channel never overwrites another; `cached_read_failed` copy is
rendered only from `cachedRead=failed`; a decoded HTTP 200 with
`sync_status="failed"` renders the stable backend code; a POST with no
decoded response renders the transport-failure copy; "仍顯示最後一次已確認的
觀察" style copy renders only when `view.snapshot` is actually present, with
its exact `observed_at`.

Recovery: a first failed cached GET schedules exactly one retry after
1,000 ms (injectable timer; unmount/credential-change/generation cancels or
discards). Every OAuth account row renders a **Retry local read** action when
`cachedRead=failed`; it invokes only the cached GET. Focus revalidation keeps
the existing five-minute policy; no repeating timer is added.

The manual sync button gate extends from `chatgpt_oauth` to
`claude_code_oauth`. The Claude button uses distinct bilingual copy
disclosing cost ("同步用量(會發送一次極小請求,消耗少量訂閱用量)" /
"Sync usage (sends one minimal request; uses a small amount of subscription
usage)"). The ten-second cooldown and single-flight are shared. Per the
§0.1.1 ruling, the ChatGPT visible/focus automatic sync effects are REMOVED:
page load, focus, visibility, and idle send zero sync POSTs for every
provider; the buttons are the only sync triggers. Focus/visibility may still
revalidate the local cached GET under the existing five-minute policy.

`OAuthAccountSource` in `api.ts` gains `"anthropic_oauth_probe"` (the one
authorized line). When the rendered snapshot's source is
`anthropic_oauth_probe`, the two windows are labeled explicitly as the
five-hour and seven-day windows ("5 小時視窗" / "7 天視窗"), not the generic
primary/secondary labels; the rendered source line shows
`來源：anthropic_oauth_probe`. Both facts are asserted inside the new
`claude row shows cost labeled manual sync and one click sends one POST`
node. New i18n keys live under `providers.accountUsage.*` in both language files;
the frozen `settingsCopy.test.ts` baseline sections are untouched (verified:
they freeze section copy, not `accountUsage` keys). The i18n literal scanner
must stay `36 / 20 / 0 / 20`, exit 0.

### 1.4 Sticky inset transfer (design LD 10; amended 2026-08-11)

Amendment: the original text said "`settings.css` only" while requiring the
narrow-viewport `12px` to live "inside the existing `@media (max-width:
760px)` block" - a contradiction, because the standing SettingsCss contract
node forbids any `@media` in `settings.css` (`SettingsCss.test.ts:56`, not
in the retained-evolve set) and the only existing 760px block (the one
holding `.main { padding: 12px; }`) lives in `styles.css:1083`. The split
ownership below replaces it; no JS or viewport-computation workaround is
permitted.

`settings.css`:

- `.main.settings-workspace { padding-top: 0; }`
- the Settings lede (the existing PageHeader block wrapped as
  `.settings-page-lede`, a Settings-scoped wrapper added in `Settings.tsx`)
  owns `padding-top: 20px;` - no `@media` is added to this file;

`styles.css` - exactly ONE added declaration, inside the EXISTING
`@media (max-width: 760px)` block that already holds
`.main { padding: 12px; }`:

- `.settings-workspace .settings-page-lede { padding-top: 12px; }`

The descendant selector is load-bearing, not stylistic: `main.tsx` imports
`styles.css` (line 15) BEFORE `settings/settings.css` (line 18), so a bare
`.settings-page-lede` media rule at specificity (0,1,0) would lose the
cascade to the later `settings.css` 20px rule at every width and be dead on
arrival; (0,2,0) wins independent of import order and stays scoped to the
Settings workspace.

Unchanged:

- the sticky row, `--settings-sticky-offset`, directory rail top, and section
  `scroll-margin-top`;
- every other byte of `styles.css`;
- no negative margin, transform, mask, overlay, or global `.main` change.

This amendment changes NO ledger number and NO pinned identity: the two
staged section-2 CSS node IDs, `1146/4ed78744...`, focused `55/df92b0c0...`,
the addition stream, and the Settings projection all stand.

Post-change invariants: at deep scroll the workflow row's top equals the
`.main.settings-workspace` scrollport top within one CSS pixel at both
`1322x777` and `390x844`; at initial scroll the visual breathing room above
the PageHeader equals the pre-change 20/12 pixels.

### 1.5 Codex app-server notification allowlist (2026-08-11 host-live stop)

The §5.1 host-live acceptance proved the §1.1 launcher repair works on the
real NVM installation - the true `codex app-server` started and completed
`initialize`/`initialized` - and then failed honestly: the server's FIRST
post-`initialized` message was the notification
`remoteControl/status/changed`, which the strict
`_ALLOWED_SERVER_NOTIFICATIONS` frozenset
(`src/auth_drivers/codex_account_usage.py:39`) rejects as
`protocol_incompatible` before any `account/rateLimits/read` or
`account/usage/read` was sent. The notification IS declared by the pinned
CLI's own schema generator (`codex app-server generate-json-schema
--experimental`, codex-cli `0.147.0`,
`remote_control_status_changed_is_declared: true`, ServerNotification schema
`6bf58bdb9d277419148878ea29804231b86b3d3d785076497204c329eabab3bb`, zero
provider requests, zero threads/turns) - the strict allowlist, not the wire,
is wrong.

Authorized product delta - exactly ONE frozenset member added:

- `_ALLOWED_SERVER_NOTIFICATIONS` gains `"remoteControl/status/changed"`.

Everything else stands: `thread/`- and `turn/`-prefixed methods and every
other unknown method stay rejected; a notification carrying an `id` stays
rejected; the params-shape check is unchanged. The `thread/started`
rejection keeps its dedicated test owner; the id-carrying and generic
unknown-method branches have NO dedicated nodes and are protected by the
product-diff bound itself - exactly one frozenset member added, every
other adapter byte unchanged. The paired §2.4 evolution replays this
notification through the session fixture and proves its payload never
leaks into the returned observation or the persisted snapshot.

### 1.6 Daily-usage history: remove the 31-row count assumption (2026-08-11)

The authorized §3.2d diagnostic ran exactly once, its redaction self-test
and Fable's independent leak audit both passed, and it found the
deterministic root cause: the REAL `account/usage/read` result is
structurally compatible (`dailyUsageBuckets` items are exactly
`{startDate: string, tokens: number}`) but carries 246 rows - the full
per-day history since the account began - while
`_MAX_DAILY_USAGE_BUCKETS = 31`
(`src/auth_drivers/codex_account_usage.py:38`) makes the `:243` guard
raise `protocol_incompatible` for every real account older than a month.
No unknown notification or login issue preceded it. Diagnostic packet:
`/tmp/oauth-usage-sticky-shape-diagnostic-82eb380b/packet` (8 payloads,
`SHA256SUMS`
`ea2deea2d8e5925f8f244c144675a21851fb7072d33192042a63e949c3760962`).

USER RULING (2026-08-11): full retention. The snapshot honestly keeps
every valid daily row the provider returns; silent truncation and a
larger fixed cap are both rejected as the same assumption-class defect.

Authorized product delta - exactly two edits in
`src/auth_drivers/codex_account_usage.py`:

- the `:243` guard drops its length clause (list-type check stays);
- the now-unused `_MAX_DAILY_USAGE_BUCKETS` constant is deleted.

Everything else stands: per-row validation (bounded `startDate` matching
`_DATE_RE`, numeric `tokens`) is unchanged, and the existing 256 KiB
stdout transport cap remains the sole physical size bound (246 rows is
about 10 KB). The paired §2.4 evolution makes the session fixture
faithful (246 rows) and witnesses full retention end-to-end.

---

## 2. Exact node accounting

### 2.1 Identities

| State | Backend | Frontend |
|---|---|---|
| base | `4,282 / 281cad976a2df29224f41d7442f39ee6deb5b78165fb9efe3945bee6d520abe3` | `99 files / 1,124 / da69a2942c03e4794e3384e6125936f9f25c1fafbad7d006b67025f8fd97bc39` |
| after Task 1 (launcher, `+7/-0`) | `4,289 / 37bc0a597398404de6247e465e44908ccd265798ba66722242bb8807c1614968` | unchanged |
| after Task 2 (Anthropic adapter + dispatch, `+14/-0`) | `4,303 / 52b862d7bf94f9d4605f8de1b2e92240ea152a41218446c3652b38716af77489` | unchanged |
| after Task 3 recovery commits (landed, `+9/-1`) | unchanged | `1,132 / 0cd20954049f4f9d56a47c8f0f5c21a685928cc0b32afb984ac74a273509fbc4` |
| after the Task 3 ownership refactor (`+12/-0`) | unchanged | `1,144 / c9deb227812c8cb7e1df5584351d6b55ba269696bbffccc4e34aaea372e14769` |
| after Task 4 (sticky inset, `+2/-0`) | unchanged | `100 files / 1,146 / 4ed7874404b462846ffc51ddd7798633a77fb1a12f46ce4b5f45ae4913d54145` |

Final accounting is backend `+21/-0` (4,303 nodes, one new test file) and
frontend `+23/-1` (net `+22`, 1,146 nodes; the refactor adds one new test
file, so the file count becomes 100). Derivation asserts every added ID
absent from base, the one removed ID present exactly once, internal
uniqueness, and `sort(unique(base - removed + added))` reproduction of each
hash. Exactly one node is renamed (section 2.3a); nothing else is removed
or renamed.

The sorted 21-node backend addition stream is
`2b540253de6578a71be09a726a11d29cce396a2e0c29421a7f8a5cfa4b3666bd`; the
sorted 23-row frontend addition stream is
`0fefb1e513bc28482f403f5438cd2969228fff8ef73d86f9814ad45650edf7e6`; the
one-row frontend removal stream is
`a1bb6e3c9fc240a2d82b80046e85b7266da305f97a9b27e9d196ae69b31c864d`.

### 2.2 Exact backend additions

Task 1 — `tests/test_subscription_account_usage.py` (`+7`):

```text
test_nvm_symlink_launcher_with_env_shebang_passes_exact_version_check
test_isolated_path_without_launcher_directory_is_interpreter_unavailable
test_missing_shebang_interpreter_is_interpreter_unavailable_not_version_skew
test_wrong_version_output_from_executable_launcher_is_version_incompatible
test_nonzero_version_exit_is_adapter_unavailable_not_version_skew
test_oversized_or_malformed_version_output_is_protocol_incompatible_not_version_skew
test_app_server_spawn_uses_launcher_path_with_launcher_and_target_dirs_on_path
```

The first node builds a REAL on-disk fixture: a `bin/codex ->
../lib/pkg/codex.js` relative symlink whose target begins
`#!/usr/bin/env fakenode`, plus an executable `fakenode` in the launcher
directory printing `codex-cli 0.147.0`. Faking only a plain executable
without the symlink+shebang seam is inadmissible (spec stop 3).

Task 2 — new `tests/test_anthropic_account_usage.py` (`+12`):

```text
test_manual_sync_sends_one_request_with_auth_token_beta_identity_block_and_max_tokens_8
test_2xx_unified_headers_record_five_hour_and_seven_day_observation
test_429_with_unified_headers_records_rejected_quota_observation
test_429_without_unified_headers_is_quota_headers_unavailable_not_a_snapshot
test_provider_401_and_403_map_to_typed_rejections_and_preserve_last_snapshot
test_missing_token_is_typed_without_provider_contact
test_malformed_utilization_reset_and_overage_fields_are_nulled_never_zeroed
test_snapshot_source_is_anthropic_oauth_probe_with_passive_fingerprint_shape
test_no_token_body_or_raw_header_reaches_snapshot_or_error_detail
test_timeout_and_transport_errors_are_typed_and_preserve_last_snapshot
test_sdk_unable_to_express_pinned_call_shape_is_sdk_incompatible
test_other_provider_4xx_is_provider_request_rejected_and_preserves_last_snapshot
```

Task 2 — `tests/test_subscription_account_usage.py` (`+2`):

```text
test_sync_dispatches_anthropic_claude_code_oauth_to_manual_messages_adapter
test_api_key_and_pool_modes_stay_unsupported_and_render_no_usage_surface
```

### 2.3 Exact frontend additions

Task 3 — `src/ProviderSection.test.ts`, new describe
`ProviderSection read and sync recovery states` (`+8`):

```text
cached read failure without snapshot says no confirmed observation
cached read failure with snapshot keeps observation and its observed_at
sync transport failure is never labeled cached_read_failed
decoded backend sync failure shows its stable backend code
first cached read failure schedules exactly one bounded retry and unmount cancels it
manual retry local read performs one GET and zero sync POSTs
claude row shows cost labeled manual sync and one click sends one POST
claude page load focus and idle send zero anthropic requests
```

### 2.3c Ownership-refactor nodes (`+12`, honestly grouped)

New file `src/settings/oauthAccountUsage.test.ts`. The PURE reducer rows
test transitions only (no cache, no timers, no DOM); the HOOK rows test the
side-effect contracts the reducer cannot own:

Describe `OAuth account usage reducer` (`+6`):

```text
success snapshot replaces the previous observation
decoded failure with snapshot adopts the authoritative snapshot
decoded failure without snapshot retains the prior observation
credential change clears the observation
read errors and sync errors never clear each other
transport failure stays distinct from decoded backend failure
```

Describe `useOAuthAccountUsage ownership` (`+6`; epoch admission is the
hook's, per the §0.1.2 lock):

```text
credential change invalidates the cache entry and focus cannot resurrect it
a read completion from before the last mutation is discarded
the bounded retry arms once per consecutive failure episode
mount focus and idle events never emit a provider post
every cache write stores a validated snapshot only
stale epoch completions are rejected
```

Re-derived identities (frontend ledger becomes `+23/-1`, net `+22`):

| State | Nodes | SHA-256 |
|---|---:|---|
| after the refactor (stage 3 final) | 1,144 | `c9deb227812c8cb7e1df5584351d6b55ba269696bbffccc4e34aaea372e14769` |
| after Task 4 (final, 100 files) | 1,146 | `4ed7874404b462846ffc51ddd7798633a77fb1a12f46ce4b5f45ae4913d54145` |
| focused after refactor (4 files) | 53 | `92572473783df6738f759de2357ab713b37ff9b2622b5aaa7cd612e7e4cede87` |
| focused final (4 files) | 55 | `df92b0c026fab6ce100a8f760397240235a882ba4f5091146401dfe9ffcfd4f2` |
| 23-row frontend addition stream | - | `0fefb1e513bc28482f403f5438cd2969228fff8ef73d86f9814ad45650edf7e6` |
| Settings 15-file projection | 231 | unchanged `ac2319b0553545b1322ffd898e99ed2bcb8ded4ae442936771697fd6a74b3217` |

The focused family gains `src/settings/oauthAccountUsage.test.ts` as its
fourth file. Backend numbers are untouched. The 2.3a rename and the 2.3b
inventory updates are already landed and unchanged.

### 2.3b Shared i18n inventory owners (Task 3 stop-and-amend, revised)

Task 3's full-suite gate exposed an undeclared shared-owner class:
`src/i18n/resources.test.ts`. The first amendment draft mis-scoped it; the
grounded structure authorizes exactly this, and nothing else, in that file:

1. Node `contains the reviewed remaining-surface namespace inventory in
   both locales` is a CURRENT-count owner: `settings: 733 -> 741` and the
   locale total `1817 -> 1825` (both locales; both deltas are exactly the
   eight new bilingual `providers.accountUsage.*` keys).
2. Node `preserves the reviewed pre-Slice-5 Settings-origin inventory
   across the Common move` is a FROZEN baseline and its frozen numbers may
   NOT chase the present: `providers: 130`, `physicalPreSliceCount: 641`,
   `movedModelCount: 23`, the `664` sum, `workspaceCount: 95`, and
   `locale: 3` all stay byte-identical. The additions flow through the
   designated post-baseline channel instead:
   - these eight exact paths join `postSliceSettingsPaths` (the
     `physicalPreSliceCount` formula already subtracts that list's length,
     so 641 is preserved structurally):

     ```text
     providers.accountUsage.syncFailedNoSnapshot
     providers.accountUsage.syncTransportFailed
     providers.accountUsage.cachedReadFailedStale
     providers.accountUsage.cachedReadFailedNone
     providers.accountUsage.retryLocalRead
     providers.accountUsage.syncClaudeCost
     providers.accountUsage.fiveHourWindow
     providers.accountUsage.sevenDayWindow
     ```

   and
   - `currentSliceDelta` changes from the hardcoded
     `subtree === "dataSources"` special case to a per-subtree prefix count
     over `postSliceSettingsPaths`, so the two existing `dataSources` paths
     and the eight new `providers` paths each offset their own subtree.

Both node IDs are preserved, no collection identity changes, and every
other assertion in the file stays behavior-protected. This section extends
the section 2.4 allowance by exactly these two inventory owners.

### 2.3a Exact frontend rename (Task 3, same RED commit)

The old ID encodes the retired automatic-sync policy and is replaced, not
retained or skipped:

```text
removed: src/ProviderSection.test.ts	ProviderSection OAuth lifecycle and account usage truth > syncs a visible stale ChatGPT snapshot once without hidden polling
added:   src/ProviderSection.test.ts	ProviderSection OAuth lifecycle and account usage truth > does not sync stale ChatGPT usage without an explicit manual click
```

Task 4 — `src/SettingsCss.test.ts`, describe
`Settings workspace CSS contract` (`+2`):

```text
settings scroll owner drops top inset while lede owns responsive breathing room
sticky offsets stay shared after the inset transfer
```

### 2.4 Retained IDs whose assertions evolve

Exactly four existing nodes may change assertion bodies; their IDs are
preserved and every other existing assertion is regression-protected (the
retired auto-sync owner is a section 2.3a rename, not an evolution):

```text
tests/test_subscription_account_usage.py::test_account_routes_split_inventory_cached_read_and_mutating_sync
tests/test_anthropic_account_usage.py::test_manual_sync_sends_one_request_with_auth_token_beta_identity_block_and_max_tokens_8
src/ProviderSection.test.ts	ProviderSection OAuth lifecycle and account usage truth > preserves_retained_account_truth_when_cached_revalidation_fails_without_sync_POST
tests/test_subscription_account_usage.py::test_codex_account_sync_reads_limits_and_usage_without_starting_thread_or_turn
```

The first asserted `anthropic/claude_code_oauth` →
`unsupported_auth_mode`; it evolved at Task 2 to assert the Anthropic
dispatch reaches the manual adapter while `api_key` stays unsupported. The
second evolves only if the three-state split renames its asserted state
field.

The Anthropic node evolves only at Task 5 after the MU5 stop below. Its
existing success-path assertions remain intact, and one HTTP 400 rejection
subcase uses the existing recording raw-client seam to assert all of:

- the typed outcome remains `provider_request_rejected`;
- exactly ONE Messages request was attempted;
- that request used the pinned `claude-sonnet-5` model and the existing
  pinned call shape;
- no fallback model request exists.

The fourth node evolved first under the §1.5 allowlist amendment (the
session fixture emits `remoteControl/status/changed` with a sentinel
payload between `initialized` and the account reads, and the node asserts
the sync still succeeds end-to-end AND the sentinel appears nowhere in the
returned observation or the persisted snapshot - the scope a backend node
can actually witness). It evolves a second time under §1.6: the fixture's
`dailyUsageBuckets` becomes a faithful 246-row array (each row exactly
`{startDate, tokens}`), RED-first against the current 31-row guard
(`protocol_incompatible`), and after the guard removal the node asserts
all 246 rows are retained in order (count, first and last row integrity)
alongside every existing assertion including the non-leak sentinels. This
second evolution edits the SAME already-authorized node - the retained
set stays exactly four. The `thread/started` rejection
node stays regression-protected as-is; the id-carrying and unknown-method
rejection branches carry no dedicated nodes and are protected by the §1.5
product-diff bound (one frozenset member, no other adapter byte).

These are test-body changes only: no node ID, collection count/hash,
focused identity, native target changes; the sole product delta is the one
§1.5 frozenset member. Any FIFTH existing-node assertion-body edit is a
stop condition.

### 2.5 Backend focused identities

Focused files: `tests/test_subscription_account_usage.py`,
`tests/test_anthropic_account_usage.py` (new),
`tests/test_claude_code_sdk_driver.py`, `tests/test_claude_oauth_probe.py`.

| State | Nodes | SHA-256 |
|---|---:|---|
| base | 61 | `b0d56cc5cf46d3dafeaf60b59825bc09be332a91c01c9f54fcfd27096f969e9b` |
| after Task 1 | 68 | `a76b86a37c2ea415e325b2872d01e72b7588c7e26728d20f1b947fb80042586e` |
| after Task 2 (final) | 82 | `1c8c9de1e6c1d137aa8db3c39fbff32107db0d42550af81eaa3d120e8a0cac55` |

Grounded baseline runtime: `61 passed / 0 failed` (one command, executed
2026-08-10).

### 2.6 Frontend focused identities

Focused files: `src/ProviderSection.test.ts`, `src/SettingsCss.test.ts`,
`src/settings/settingsCopy.test.ts` (regression witness, byte-protected);
`src/settings/oauthAccountUsage.test.ts` joins as the fourth file at the
ownership refactor.

| State | Nodes | SHA-256 |
|---|---:|---|
| base (3 files, historical) | 33 | `fb42f09afe2b1a2ba08eb936220ed5da0dd98f79a19e46ba885c6877fce815bd` |
| after the landed recovery commits (3 files) | 41 | `82dc004ab10a61a86128d917b1b3f413c912e8e0c9c4522123a8d33ea047c5fd` |
| after the ownership refactor (4 files) | 53 | `92572473783df6738f759de2357ab713b37ff9b2622b5aaa7cd612e7e4cede87` |
| after Task 4 (final, 4 files) | 55 | `df92b0c026fab6ce100a8f760397240235a882ba4f5091146401dfe9ffcfd4f2` |

Grounded baseline runtime: `33 passed (3 files)`. The Settings-line focused
regression set (15 files) contains `ProviderSection.test.ts` and
`SettingsCss.test.ts`, so it absorbs exactly the `+11/-1` portion of this
plan's frontend ledger that lands inside its 15 files; the 12 ownership-
refactor nodes live in `src/settings/oauthAccountUsage.test.ts`, OUTSIDE
the projection, so its stage-4 projection is unchanged by the refactor:
`231 / ac2319b0553545b1322ffd898e99ed2bcb8ded4ae442936771697fd6a74b3217`
(mechanically derived from the stage-4 stream; base remains
`221/a2c20d36...`). Task 5 runs this 15-file set and requires `231 passed`.

### 2.7 Native target

All 21 backend additions are hermetic (tmp-dir fixtures, injected fakes,
no network, no skip markers). Native target is therefore
`4,274 passed / 29 skipped / 0 failed` on 4,303 collected; any other split
stops the line. Frontend native target is `1,146/1,146`.

---

## 3. RED and mutation discipline

### 3.1 RED admission

Each task's RED commit adds only its exact new node IDs; collection must
match that task's staged identity before product code. RED must fail on the
intended missing contract (missing module/attribute counts as the missing
contract for Task 2's new-module nodes; an import error inside an EXISTING
file does not). Fixture, network, timer-leak, or unrelated-node failures are
wrong RED. RED transcripts and structured lists are retained per task under
`/tmp/oauth-usage-sticky-impl-<task>-<base>/`.

The three section 2.4 evolutions land with their owning gate: Task 2 for the
backend route node, Task 3 for the frontend node, and Task 5 for the
Anthropic one-request strengthening. Each has a before/after assertion diff
in evidence.

### 3.2 Required mutations (Task 5, fresh exact-tip copies, one at a time)

| ID | Mutation (exact diff recorded) | Required RED owner |
|---|---|---|
| MU1 | `_resolve_executable` returns the resolved target as the launcher again | symlink+shebang version node; app-server launcher node |
| MU2 | map interpreter absence to `version_incompatible` | interpreter-vs-version split node |
| MU3 | collapse `syncSend=transport_failed` into `cachedRead=failed` | transport-not-cached node |
| MU4 | add the Anthropic loader to the idle/auto path (fire probe on page load) | zero-anthropic-requests node |
| MU5 | retry a second model after a probe rejection | strengthened one-request node, including its rejection subcase |
| MU6 | remove `.main.settings-workspace { padding-top: 0; }` without moving the lede inset | `settings scroll owner drops top inset while lede owns responsive breathing room` RED; `sticky offsets stay shared after the inset transfer` stays GREEN; browser geometry later confirms the visible regression |

Each mutation must hit the live seam (a dead-code edit or one that leaves the
named owner GREEN is rejected), be restored byte-exactly (whole-file SHA,
`pre == tip == post`), and never stack.

### 3.2a Task 5 MU5 stop-and-amend (2026-08-11)

MU1-MU4 each hit the declared owner and restored byte-exactly. MU2's first
context-insufficient candidate changed an empty-shebang-token branch and
left the named missing-interpreter owner GREEN, so it was rejected before
the admitted live-seam mutation.

MU5 then exposed a real test gap. A faithful temporary product mutation
handled the first HTTP 400 rejection by issuing a second request against
`claude-opus-5`, then preserved the original typed
`provider_request_rejected` outcome. The raw fake recorded exactly two
models (`claude-sonnet-5,claude-opus-5`), while BOTH the declared
one-request node and the existing 4xx node remained GREEN (`2 passed`). The
mutation was therefore rejected and the product file restored byte-exactly.
MU6 and every later admission gate stopped.

The bounded §2.4 strengthening above is required before MU5 may be replayed.
All section 2 identities remain unchanged. Partial raw packet:
`/tmp/oauth-usage-sticky-impl-task5-4fbf3087` (34 payloads,
`PARTIAL_SHA256SUMS`
`fd7d0fdd574d3f69b71aae11d2fdf411c7568fc23e83d115fd061a4bf288e146`).

### 3.2b Task 5 MU5 replay and MU6 owner correction (2026-08-11)

Fable independently replayed the MU5 gap and returned amendment `a16d1b70`
GREEN. The existing one-request node was strengthened in test commit
`9a704331`; it first passed against the unchanged product, with backend
focused `82/82`. The exact MU5 fallback mutation was then replayed and the
same node failed at `len(rejected_raw.calls) == 1` after recording two
requests. The adapter restored byte-exactly. Mechanical docs erratum
`26a4be41` corrected section 7's stale evolution count from two to three.

MU6 then exposed a different plan-only overclaim. Its faithful inverse
removed only `.main.settings-workspace { padding-top: 0; }` while retaining
the lede's `20px/12px` inset. The seven-node CSS owner file produced exactly
one RED: `settings scroll owner drops top inset while lede owns responsive
breathing room`. The adjacent `sticky offsets stay shared after the inset
transfer` node correctly stayed GREEN because it owns the shared sticky
offset chain, not scroll-owner padding. Requiring it to fail would force a
duplicate assertion unrelated to that node's responsibility.

The MU6 row is therefore narrowed to the real static owner plus the already
required final browser geometry. The adjacent sticky-offset node MUST stay
GREEN under this isolated mutation. No test body, node ID, collection
identity, focused identity, native target, product behavior, or browser
contract changes. CSS restored byte-exactly; every later admission gate
stopped. Continuation packet:
`/tmp/oauth-usage-sticky-impl-task5-a16d1b70` (12 payloads,
`PARTIAL2_SHA256SUMS`
`8b4ee1a7007780cb205901ec428ec71eca420b5e96c309f405d88e1c4b86666a`).

### 3.2c Task 5 host-live stop: schema-declared notification rejected (2026-08-11)

MU1-MU6 completed under the corrected §3.2 table. The final static and
runtime gates all ran GREEN first: backend `4303/52b862d7...` (collect and
focused `82/82`), frontend `1146/4ed78744...` with a clean single-command
`1146/1146`, typecheck, build, i18n scanner, Settings 15-file projection,
and the pinned-wrapper native run `4274 passed / 29 skipped / 0 failed`.

The §5.1 host-live ChatGPT sync then stopped exactly as designed: the
launcher fix worked (real app-server spawned, `initialize`/`initialized`
completed), the server's first subsequent notification
`remoteControl/status/changed` was rejected by the strict allowlist, the
sync returned typed `protocol_incompatible` with `sync_http_status: 200`,
and NO `account/rateLimits/read`, `account/usage/read`, model thread, or
turn was reached (zero model usage). The boundary witness records every
adapter child process exited, the one temporary `CODEX_HOME` was removed,
no token content or raw account identity persisted, and the production
OAuth/credential tables are unchanged. Partial packet:
`/tmp/oauth-usage-sticky-impl-task5-admission-24d231eb` (26 payloads,
`PARTIAL_SHA256SUMS`
`1daeb78c30c047c14fa3c0b5d07412e15af8c6abec194f69d05de9eeb6f6f2c6`).

Resume order after this amendment goes GREEN: one product+test commit
(§1.5 member + §2.4 fourth evolution), backend focused `82/82` with the
rejection nodes intact, then ONE §5.1 host-live rerun which MUST succeed
before the §5.2 browser matrix runs; the remaining admission gates follow
unchanged. All section 2 identities stand.

### 3.2d Second host-live stop: one redacted shape-only diagnostic (2026-08-11)

The §1.5 fix landed as `bd32b7fe` (one frozenset member; the §2.4 fourth
evolution RED-first with the sentinel non-leak witness; focused `82/82`;
collection `4303/52b862d7...` held; Fable-reviewed GREEN). The single
authorized host-live rerun then proved the notification fix works
(`remoteControl/status/changed` accepted, launcher and initialize passed)
and stopped AGAIN with typed `protocol_incompatible` at a LATER message
whose method and shape are unknown, because the strict decoder collapses
unexpected notifications, response-shape mismatches, and JSON-RPC error
objects into one code with no detail - by secrecy design. Guess-and-fix
allowlist churn is rejected; the boundary witness shows zero child
processes, zero temporary `CODEX_HOME` leftovers, unchanged production
OAuth/credential tables. Packet:
`/tmp/oauth-usage-sticky-impl-task5-resume-bd66177a` (15 payloads,
`PARTIAL3_SHA256SUMS`
`5b13356cbb5a2388ae96c672c0db4a6980f4e69983f8a77174d5851b002d45e6`).

Authorized next step - exactly ONE redacted shape-only diagnostic run:

- The host-live harness instruments the strict-decode seam IN THE
  TEMPORARY SIDECAR PROCESS ONLY (runtime wrap; ZERO product bytes
  change and no diagnostic code is committed to `src/`).
- For every inbound app-server message until the failure point (cap 50),
  it records a SHAPE projection: the `method` string if present, `id`
  PRESENCE as a boolean (never its value), and a recursive projection of
  `params`/`result`/`error` keeping field NAMES, JSON TYPES
  (object/array/string/number/boolean/null), and ARRAY LENGTHS only
  (depth cap 6, per-object key cap 32).
- Every scalar VALUE is dropped and replaced by its type marker. No
  token, account identifier, email, URL, timestamp, numeric value, or
  error-message text may appear in the artifact; the existing
  stdout/stderr byte caps and cleanup witnesses (child processes,
  temporary `CODEX_HOME`, token/identity non-persistence, unchanged
  production tables) apply unchanged.
- The artifact lands in the diagnostic packet for Fable review and the
  user's fix ruling. NO validator, allowlist, or fixture change is
  authorized by this section; the subsequent single bounded fix plus its
  faithful fixture require their own amendment grounded on the captured
  shape.

All section 2 identities stand; no test or product byte changes under
this section.

### 3.2e Diagnostic result and resume order (2026-08-11)

The §3.2d run was clean on every witness: shape policy self-test passed,
Fable's independent leak audit found no value, identifier, or message
text; production tables' row projections are byte-identical before and
after the one POST; child processes and temporary `CODEX_HOME` are zero;
no validator, allowlist, or fixture byte changed. The finding, ruling,
and authorized delta live in §1.6.

Resume order after this amendment goes GREEN: one product+test commit
(§1.6 two-edit delta + the §2.4 second evolution of node four), backend
focused `82/82` with the rejection nodes intact, then ONE §5.1 host-live
rerun which MUST succeed before the §5.2 browser matrix; the remaining
admission gates (final collections, full frontend runtime/build, Settings
projection, native at the FINAL product tip) follow unchanged. All
section 2 identities stand; the native target stays
`4274 passed / 29 skipped / 0 failed`.

---

## 4. Task sequence

Per-gate flow: RED recorded (not committed broken), one product+test commit,
one docs evidence commit, stop for Codex review. The user may batch gates;
any stop condition still halts immediately.

**Task 0 — re-ground.** Verify branch ancestry (`8cf85597` →
spec tip), toolchain pins by full SHA, byte-protected blob manifest, base
collections (backend `4282/281cad97...`, frontend `1124/da69a294...`),
staged-stream reconstruction of every section 2 hash from the addition
lists, focused baselines (61 backend / 33 frontend, one command each),
Settings focused `221/a2c20d36...` projection and its pinned stage-4
re-derivation, and the native base (already proven at `252535bf...`; rerun
only if any product byte differs). Docs-only commit; stop.

**Task 1 — Codex launcher repair.** RED the seven launcher nodes at stage-1
identity; implement §1.1; prove focused 68-node GREEN, no `.pre`-existing
node broken, protected blobs intact. Commit; stop.

**Task 2 — Anthropic adapter + dispatch.** RED the fourteen nodes at stage-2
identity (twelve in the new file may fail on module absence); implement §1.2
plus the `source` Literal member and the §2.4 backend assertion evolution;
prove focused 82-node GREEN and zero provider/socket use under a
network-guard fixture. Commit; stop.

**Task 3 — ownership refactor gate (remaining scope).** The recovery
commits through `9bf2b9bd` are landed, superseded internals; their nine
behavior nodes are the frozen regression corpus. Codex now: RED the twelve
section 2.3c nodes at `1144/c9deb227...` (the six reducer rows may fail
on module absence; the six hook rows on the missing ownership surfaces);
implement the §0.1.2 architecture (pure reducer, hook, snapshot-only cache
including the Settings.tsx warmup loader swap) without touching backend
DTOs, adapters, or `settingsReadCache`; keep all 26 ProviderSection nodes
green (bodies may adapt per §0.1.2 without weakening behavior); prove FE
focused 53-node GREEN (4 files), i18n scanner `36/20/0/20`, typecheck, and
the protected blobs. Commit; stop for Fable implementation review.

Implementation commit `380021b5` completed this gate. Task 4 remains paused
until Fable reconstructs the Task 3 packet and returns GREEN.

**Task 4 — sticky inset.** RED the two CSS nodes at stage-4 identity;
implement §1.4; run an early dual-viewport browser spot check (deep-scroll
row top == scrollport top ±1px; initial lede spacing 20/12); prove FE focused
55-node GREEN. Commit; stop.

Implementation commit `99ca5441` completed this gate at the exact
`1146/4ed78744...` full and `55/df92b0c0...` focused identities. The
dual-viewport geometry was `20px/12px` initial inset and `0px` deep-scroll
sticky delta. Task 5 remains paused until Fable reconstructs the Task 4
packet and returns GREEN.

**Task 5 — mutations and admission.** MU1-MU6; final collections
(backend `4303/52b862d7...`, frontend `1146/4ed78744...`, both focused
finals, Settings focused re-derived pin); full frontend Vitest, typecheck,
build, i18n scanner; my own native run via the pinned wrapper
(`4274/29/0` target) plus the §5.1 host-live Codex acceptance; hermetic
browser matrix per §5.2; protected-blob recheck; artifact
manifest/cleanup. Docs evidence commit; stop for Codex implementation
review.

Task 5 began after Fable returned Task 4 GREEN. The §3.2a amendment passed
review, its exact test strengthening landed, and MU5 obtained a
discriminating RED owner. MU6 then passed under the corrected owner contract.
The two host-live stops and the bounded shape diagnostic are recorded in
§§3.2c-3.2e; the final §1.6 fix removed only the invalid 31-row cap and
retained all 246 validated daily rows. Product tip `ca61992b` passed backend
`4303/52b862d7...`, frontend `1146/4ed78744...`, focused `82/55`, Settings
projection `231`, full frontend `1146/1146`, typecheck/build/scanner,
protected `17/17` plus the single authorized `api.ts` hunk, one successful
host-live ChatGPT POST, the two-viewport browser matrix, and fresh native
`4274 passed / 29 skipped / 0 failed`. Packet
`/tmp/oauth-usage-sticky-impl-task5-final2-ca61992b` has 153 payloads and
manifest SHA-256 `11aa165f3962b3ccf7eba8af974629725d7262a8250e985cf626399bc1e44377`.
Independent Task 5 implementation review is the sole next gate.

**Task 6 — merge.** Complete. After Fable returned Task 5 GREEN, `master`
fast-forwarded from `8cf85597` to `fdb81913` through 50 linear commits with
zero merge commit and no push. Fresh exact-master worktrees reproduced all
four collections/focused gates, Settings `231`, frontend `1146/1146`,
typecheck/build/scanner, protected bytes, native `4274/29/0`, and the
two-viewport browser contract. Closeout packet
`/tmp/oauth-usage-sticky-task6-merged-fdb81913` has 44 payloads; manifest
SHA-256 `85f3b52f27f8e6560449c4612ce1340dbdd58406abd966fd171b42678c739e2c`.
Fable independently reconstructed the merge topology, product-byte boundary,
four collection streams, native report, frontend runtime, browser contract,
and packet, then returned closeout GREEN. The implementation/cutover line is
closed.

**Task 7 — live acceptance (post-merge, user-gated).** §5.3 below. Its
results are rollout evidence, not merge preconditions, except that the
ChatGPT host sync (§5.1) already ran at Task 5.

---

## 5. Live and browser acceptance

### 5.1 ChatGPT host acceptance (Task 5, native context)

On the real NVM install, through the real service boundary: one
`account/rateLimits+usage` sync against the local sidecar seam with the real
launcher; prove a decoded observation or truthful typed outcome, zero
`thread/*`/`turn/*` methods, child process group and temp `CODEX_HOME` gone.
No home-directory token content in artifacts. The known-restrictive sandbox
is not used for this step; a sandboxed transcript is rejected evidence.

### 5.2 Browser matrix (Task 5; hermetic)

Playwright + pinned Chrome, fixture-only network, `1322x777` and `390x844`,
page top and deep Data Sources scroll:

- workflow-row top equals the Settings scrollport top within 1 CSS pixel
  after deep scroll; no content strip above it inside the scrollport;
- initial lede spacing byte-equal CSS expectations (20/12) and visually
  unchanged screenshots at original resolution;
- nine directory anchors, exact-anchor focus below the sticky row, group-top
  restore, one mounted tabpanel, no overflow/clipping (Settings-line
  regressions);
- provider row: cached-read failure state renders the no-observation copy
  when the account GET fixture fails, the retry action fires exactly one
  additional GET, and zero Anthropic/OpenAI sync POSTs occur on load,
  focus, visibility, or idle — only an explicit button click may POST;
- request ledger `{GET}`-only during idle; console/page errors zero;
  processes and temp profiles cleaned.

DOM geometry is admission authority; screenshots are supporting evidence.

### 5.3 Anthropic live probe (Task 7, requires explicit user authorization)

With the user's go-ahead in chat, on the running desktop app: confirm zero
Anthropic requests at page load; click the cost-labeled button once; prove
exactly one Messages request, a rendered 5h/7d used-percent + reset, source
`anthropic_oauth_probe` with correct `observed_at`; second click inside
cooldown sends nothing; a later normal Claude request still updates the
passive snapshot. Artifacts redact everything per LD 7. Expected live cost:
one `max_tokens=8` request.

---

## 6. Stop conditions

1. any staged/final collection count or hash differs, or a node changes
   outside the `+21` backend / `+23/-1` frontend ledger (section 2.3c
   included), the one section 2.3a rename, the declared evolutions, and the
   two section 2.3b numeric count updates, or a second `api.ts` hunk beyond
   the one authorized union line;
2. RED fails for a wrong reason (import error in an existing file, fixture,
   network, timer leak) or a fake-only executable replaces the real
   symlink+shebang fixture;
3. `api.ts` changes beyond the one authorized union-member hunk, or any
   section 0.5 blob, the frozen Settings fixtures, the old probe
   route/module, or the passive RateLimitEvent path changes;
4. any test or non-Task-7 step contacts a provider, or any automatic path
   (load/focus/visibility/idle/cached-read) can reach ANY sync adapter —
   Anthropic or ChatGPT; buttons are the only sync triggers;
5. the adapter stores or logs a token, body, generated text, raw header map,
   email, or raw account id, or a malformed field becomes `0`;
6. `version_incompatible` is returned for anything other than a well-formed
   wrong version, or the launcher path stops being the `Popen` argv[0];
7. the sticky fix changes global `.main`, uses masking/negative margins, or
   the 1-pixel geometry/initial-inset invariants fail at either viewport;
8. a cache policy, registry, directory, or active-only mounting semantic
   changes;
9. the probe model pin is silently changed or more than one model is tried;
10. lockfiles change, `npm install` runs, or a sandboxed transcript is
    presented as native/host evidence;
11. the Anthropic live probe runs without explicit user authorization in
    chat, or before the button+copy exist.

---

## 7. Codex reviewer obligations

Reconstruct from raw artifacts (not prose): all section 2 streams and
hashes from the addition lists plus base; RED admissibility per task; the
three assertion evolutions against their before/after diffs; adapter secrecy
(grep artifacts for token/header leakage); MU1-MU6 diffs, RED owners, and
byte-exact restoration; focused/full/native/browser results; protected-blob
manifest; i18n scanner; and the Task 6 exact-master rerun. GREEN on Task 5
review authorizes merge; GREEN on Task 6 closeout closes the
implementation/cutover line. Task 7 remains separate rollout evidence and may
run only after explicit user authorization in chat.
