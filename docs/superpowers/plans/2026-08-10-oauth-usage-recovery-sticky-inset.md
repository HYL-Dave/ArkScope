# OAuth Usage Recovery and Settings Sticky Inset Implementation Plan

> **Status:** WRITTEN BY FABLE (IMPLEMENTATION SIDE) - INDEPENDENT CODEX PLAN
> REVIEW REQUIRED; IMPLEMENTATION NOT AUTHORIZED
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
> **Roles (design LD 11):** Fable writes this plan and the product edits;
> Codex performs independent plan review, per-gate implementation review, and
> the final merged review. Codex does not patch the implementation under
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
| sticky inset | `apps/arkscope-web/src/Settings.tsx`, `apps/arkscope-web/src/settings/settings.css`, `apps/arkscope-web/src/SettingsCss.test.ts` |
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

`ProviderSection.tsx` account state per local credential becomes:

```text
cachedRead:  idle | loading | loaded | failed   (+ failed error code)
syncSend:    idle | sending | transport_failed  (+ transport error code)
backendSync: last decoded sync_status + sync_error_code from a decoded view
view:        last validated OAuthAccountSyncView, if any
```

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
usage)"). The ten-second cooldown and single-flight are shared. The ChatGPT
automatic visible/focus sync policy is unchanged and remains ChatGPT-only;
no automatic path may reach the Anthropic adapter (page load, focus, idle,
cached read all send zero Anthropic requests).

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

### 1.4 Sticky inset transfer (design LD 10)

`settings.css` only:

- `.main.settings-workspace { padding-top: 0; }`
- the Settings lede (the existing PageHeader block wrapped as
  `.settings-page-lede`, a Settings-scoped wrapper added in `Settings.tsx`)
  owns `padding-top: 20px`, and `12px` inside the existing
  `@media (max-width: 760px)` block;
- the sticky row, `--settings-sticky-offset`, directory rail top, and section
  `scroll-margin-top` are unchanged;
- no negative margin, transform, mask, overlay, or global `.main` change.

Post-change invariants: at deep scroll the workflow row's top equals the
`.main.settings-workspace` scrollport top within one CSS pixel at both
`1322x777` and `390x844`; at initial scroll the visual breathing room above
the PageHeader equals the pre-change 20/12 pixels.

---

## 2. Exact node accounting

### 2.1 Identities

| State | Backend | Frontend |
|---|---|---|
| base | `4,282 / 281cad976a2df29224f41d7442f39ee6deb5b78165fb9efe3945bee6d520abe3` | `99 files / 1,124 / da69a2942c03e4794e3384e6125936f9f25c1fafbad7d006b67025f8fd97bc39` |
| after Task 1 (launcher, `+7/-0`) | `4,289 / 37bc0a597398404de6247e465e44908ccd265798ba66722242bb8807c1614968` | unchanged |
| after Task 2 (Anthropic adapter + dispatch, `+14/-0`) | `4,303 / 52b862d7bf94f9d4605f8de1b2e92240ea152a41218446c3652b38716af77489` | unchanged |
| after Task 3 (frontend recovery, `+8/-0`) | unchanged | `1,132 / 778d64be3239dbb94df475e2cccde1b61878af3a627a28a677038191ea6a6e9d` |
| after Task 4 (sticky inset, `+2/-0`) | unchanged | `99 files / 1,134 / 941067a028c7bb6b15c3e3f64012dcf251995804e3f55c9a712cb230d4a4ba64` |

Final accounting is backend `+21/-0` (4,303 nodes, one new test file) and
frontend `+10/-0` (1,134 nodes; both frontend additions land in existing
files, so the file count stays 99). Derivation asserts every added ID absent from base, internal
uniqueness, and `sort(unique(base + added))` reproduction of each hash. No
node is removed or renamed anywhere in this plan.

The sorted 21-node backend addition stream is
`2b540253de6578a71be09a726a11d29cce396a2e0c29421a7f8a5cfa4b3666bd`; the
sorted 10-row frontend addition stream is
`e900aa107304d88a41eb9d2443ed525c381f2a985778ef4f416b8a3ae207aafb`.

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

Task 4 — `src/SettingsCss.test.ts`, describe
`Settings workspace CSS contract` (`+2`):

```text
settings scroll owner drops top inset while lede owns responsive breathing room
sticky offsets stay shared after the inset transfer
```

### 2.4 Retained IDs whose assertions evolve

Exactly two existing nodes may change assertion bodies; their IDs are
preserved and every other existing assertion is regression-protected:

```text
tests/test_subscription_account_usage.py::test_account_routes_split_inventory_cached_read_and_mutating_sync
src/ProviderSection.test.ts	ProviderSection OAuth lifecycle and account usage truth > preserves_retained_account_truth_when_cached_revalidation_fails_without_sync_POST
```

The first currently asserts `anthropic/claude_code_oauth` →
`unsupported_auth_mode` (line ~520); it evolves to assert the Anthropic
dispatch reaches the manual adapter while `api_key` stays unsupported. The
second evolves only if the three-state split renames its asserted state
field; its behavior contract (no POST on cached failure, truth retained) is
unchanged. Any third existing-node edit is a stop condition.

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
`src/settings/settingsCopy.test.ts` (regression witness, byte-protected).

| State | Nodes | SHA-256 |
|---|---:|---|
| base | 33 | `fb42f09afe2b1a2ba08eb936220ed5da0dd98f79a19e46ba885c6877fce815bd` |
| after Task 3 | 41 | `efc6accc536387ec7b6badd1d89a1dbc2c7efa075fc0c4686eecdcf92f9dc7c7` |
| after Task 4 (final) | 43 | `853c9cefacf8408c8dda768bdbeea4447ab1ae8cc72dba812243e7aeebac0754` |

Grounded baseline runtime: `33 passed (3 files)`. The Settings-line focused
regression set (15 files) contains `ProviderSection.test.ts` and
`SettingsCss.test.ts`, so it absorbs exactly the ten additions: its stage-4
projection is `231 / e0bb619016a9355e78ffd97559139744c1b5ec6ffd6e8854c7d0eaac0187677d`
(mechanically derived from the stage-4 stream; base remains
`221/a2c20d36...`). Task 5 runs this 15-file set and requires `231 passed`.

### 2.7 Native target

All 21 backend additions are hermetic (tmp-dir fixtures, injected fakes,
no network, no skip markers). Native target is therefore
`4,274 passed / 29 skipped / 0 failed` on 4,303 collected; any other split
stops the line. Frontend native target is `1,134/1,134`.

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

The two section 2.4 evolutions land in the same commit as their task's GREEN
(Task 2 for the backend node, Task 3 for the frontend node), each with a
before/after assertion diff in evidence.

### 3.2 Required mutations (Task 5, fresh exact-tip copies, one at a time)

| ID | Mutation (exact diff recorded) | Required RED owner |
|---|---|---|
| MU1 | `_resolve_executable` returns the resolved target as the launcher again | symlink+shebang version node; app-server launcher node |
| MU2 | map interpreter absence to `version_incompatible` | interpreter-vs-version split node |
| MU3 | collapse `syncSend=transport_failed` into `cachedRead=failed` | transport-not-cached node |
| MU4 | add the Anthropic loader to the idle/auto path (fire probe on page load) | zero-anthropic-requests node |
| MU5 | retry a second model after a probe rejection | one-request node |
| MU6 | restore `.main.settings-workspace` top padding without moving the lede inset | both new CSS nodes + browser geometry |

Each mutation must hit the live seam (a dead-code edit or one that leaves the
named owner GREEN is rejected), be restored byte-exactly (whole-file SHA,
`pre == tip == post`), and never stack.

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

**Task 3 — frontend recovery split.** RED the eight nodes at stage-3
identity; implement §1.3 with i18n keys in both languages; prove FE focused
41-node GREEN, i18n scanner `36/20/0/20`, typecheck. Commit; stop.

**Task 4 — sticky inset.** RED the two CSS nodes at stage-4 identity;
implement §1.4; run an early dual-viewport browser spot check (deep-scroll
row top == scrollport top ±1px; initial lede spacing 20/12); prove FE focused
43-node GREEN. Commit; stop.

**Task 5 — mutations and admission.** MU1-MU6; final collections
(backend `4303/52b862d7...`, frontend `1134/941067a0...`, both focused
finals, Settings focused re-derived pin); full frontend Vitest, typecheck,
build, i18n scanner; my own native run via the pinned wrapper
(`4274/29/0` target) plus the §5.1 host-live Codex acceptance; hermetic
browser matrix per §5.2; protected-blob recheck; artifact
manifest/cleanup. Docs evidence commit; stop for Codex implementation
review.

**Task 6 — merge.** After Codex GREEN: ff-merge only, no push; fresh
exact-master worktree rerun (collections, focused, native, browser); docs
closeout; stop for Codex closeout review.

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
  additional GET, and zero Anthropic/OpenAI sync POSTs occur without an
  explicit click;
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
   outside the `+21/+10` ledger and the two declared evolutions, or a second
   `api.ts` hunk beyond the one authorized union line;
2. RED fails for a wrong reason (import error in an existing file, fixture,
   network, timer leak) or a fake-only executable replaces the real
   symlink+shebang fixture;
3. `api.ts` changes beyond the one authorized union-member hunk, or any
   section 0.5 blob, the frozen Settings fixtures, the old probe
   route/module, or the passive RateLimitEvent path changes;
4. any test or non-Task-7 step contacts a provider, or any automatic path
   (load/focus/idle/cached-read) can reach the Anthropic adapter;
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
two assertion evolutions against their before/after diffs; adapter secrecy
(grep artifacts for token/header leakage); MU1-MU6 diffs, RED owners, and
byte-exact restoration; focused/full/native/browser results; protected-blob
manifest; i18n scanner; and the Task 6 exact-master rerun. GREEN on Task 5
review authorizes merge; GREEN on Task 6 closeout authorizes the Task 7
user-gated live probe and line closure.
