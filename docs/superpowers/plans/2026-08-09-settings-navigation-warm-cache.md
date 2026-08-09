# Settings Persistent Navigation and Bounded Warm Cache Implementation Plan

> **Status:** TASK 3 COMPLETE; TASKS 4-5 BATCH EXECUTION IN PROGRESS
>
> **Date:** 2026-08-09
>
> **Design authority:** `dbd92b86b14a2a8c4349002c8b114a4a16e5e50f`
>
> **Product grounding base:** `3d18e9c0ea54d99fc4824b7919d74a4c3a38502b`

**Goal:** Keep Settings workflow navigation available at deep scroll, expose a
complete nine-section directory, and make repeat Settings navigation feel
immediate without retaining inactive component trees or weakening the truth of
existing backend DTOs.

**Architecture:** `App` owns one replaceable, memory-only
`SettingsReadCache`. The cache has a closed resource registry, synchronous
fresh/stale inspection, one promise per resource key, generation-safe
replacement, exact invalidation, and bounded LRU retention. `SettingsView`
keeps active-only tab mounting, schedules one cancellable local-GET idle
warmup, and passes the cache to existing read owners. Settings-only CSS makes
the workflow row sticky and non-wrapping; the directory renders all registry
sections. No backend API, provider request, persistent store, generic Tabs
contract, or Investor Profile lifecycle changes.

**Tech stack:** React 18, TypeScript, Vitest 4.1.8, Vite 5.4.21, Python
Playwright 1.58.0, system Google Chrome 150.0.7871.128.

---

## 0. Authority, environment, and boundaries

### 0.1 Reviewed authority

This plan implements only:

```text
docs/superpowers/specs/2026-08-09-settings-navigation-warm-cache-design.md
reviewed commit: dbd92b86b14a2a8c4349002c8b114a4a16e5e50f
worktree: /tmp/arkscope-settings-navigation-warm-cache
branch: codex/settings-navigation-warm-cache
```

Independent design review returned GREEN with zero findings. The review
reconstructed all fourteen source identities, the nine-section `4 / 1 / 4`
registry, the `.main` scroll owner, active-only tab mounting, the current
Data Sources remount/read shape, and both screenshot identities. Those facts
remain admission inputs; the implementation may not reinterpret them.

The reviewed design bytes at `dbd92b86` are 348 lines / 17,627 bytes /
`0b7ba0568164fd1d49c75be385e6ccc9f6252fd4239c659d6a4ff484b579ac12`.
The plan-gate working copy is
`751469028542c1f0a46988771a5c6cbb22a557b62e987ba49d251ecca2d9d7a6`;
its only delta is the status/review handoff at the header. The reviewed body is
not amended by this plan.

### 0.2 Owned and excluded behavior

Owned:

- Settings-only sticky workflow navigation and scroll offsets;
- complete desktop and mobile section directory;
- App-session memory cache for the exact read resources in design LD 5;
- one-shot allowlisted idle warmup;
- integration of existing model catalog, account usage, Data Sources, and
  storage GET owners with that cache;
- exact post-mutation invalidation; and
- deterministic frontend, browser, and collection evidence.

Excluded:

- backend routes, DTOs, Python product/test code, or provider behavior;
- generic `Tabs` semantics or mounting more than one panel;
- model discovery/execution, credential discovery/test/login/refresh, account
  sync from idle work, provider requests, and schedule mutation/run from idle;
- Investor Profile, drafts, calibration, local/session storage, IndexedDB,
  profile DB, filesystem cache, telemetry, or cache badges;
- calendar scheduling, Tranche B, FD metering, fundamentals ingestion, and
  git-crypt cleanup.

`apps/arkscope-web/src/api.ts` already exposes every required DTO and endpoint.
Changing it is not expected and triggers a stop unless an independently
reviewed amendment proves a missing contract.

### 0.3 Pinned local toolchain

```text
package-lock.json
SHA-256 5322cb03099b873066b7572c02db68a427ddc7509fdc9850cf9d8d3948a19f2c

node_modules/.package-lock.json
SHA-256 4dd5182f8111b54dd608344c45513f3b310f39321a3cc9832b60cefc2fa241ff
Node v22.14.0

/tmp/eir006_vitest_list_normalizer.py
62 lines / 2,233 bytes
SHA-256 955dca592d243505ced622a84e88a35160a3fa787ffb954f38a6a43e1a72fcac

/tmp/eir002-green-baseline/arkscope_eir002_reporter.py
SHA-256 09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928

Python Playwright 1.58.0
/usr/bin/google-chrome 150.0.7871.128
```

The normalizer JSON-decodes `vitest list --json`, rejects malformed names and
paths, and writes sorted `relative_file<TAB>full_test_name` UTF-8 records. Raw
JSON text extraction, `jq @tsv`, or prose parsing is not an equivalent node
identity.

The isolated implementation worktree may use only the symlink to the pinned
root `node_modules`. It must not run `npm install`, modify either lockfile, or
silently select another browser.

### 0.4 Plan-author grounding

Before this plan was written, the unchanged design tip reproduced:

| Gate | Result |
|---|---|
| Full decoded Vitest collection | 97 files / 1,084 nodes / `f0e5ecda1371f0559c1cc92af367b7e32daa91663ef2f316ed67e23129ee9637` |
| Focused decoded collection, Section 2.2 | 14 files / 182 nodes / `1c56ecf00a6d89d2d51191bcbd95946a8dd00c039f26c3c1d3d0bb979878c002` |
| Focused runtime | 182 passed across the exact fourteen files |
| Full runtime, admitted retry | 97 files / 1,084 passed |
| Typecheck | exit 0 |
| Build | exit 0; pre-existing `>500 kB` chunk warning only |
| i18n literal scanner | `36 / 20 / 0 / 20`, exit 0 |

The first full runtime is rejected evidence: one concurrently executed
`ResearchHistoryDrawer.test.tsx` owner produced 15 failures with overlapping
`act()` symptoms. The exact owner immediately passed `16/16` in isolation and
the second full run passed `1084/1084`. Task 0 must rerun an admitted baseline;
the rejected transcript may be recorded, but may not be called a pass or used
to weaken a later deterministic failure.

### 0.5 Byte-protected owners

The following ten paths must remain byte-identical. Their sorted
`sha256sum`-row aggregate is
`4eae072b4eae3069b67d5fc0528227b2023500e7582d4063f51a9a288278fef4`.

| Path | SHA-256 |
|---|---|
| `apps/arkscope-web/src/api.ts` | `d426950f15b560bdbe15ba72a2d8724ef7eb241afa7ba906de960e1774b51017` |
| `apps/arkscope-web/src/ui/Tabs.tsx` | `d63b8c7e41b04d4782345387149909447cd7f653e0fb4dddc0866063f73f6526` |
| `apps/arkscope-web/src/ui/Tabs.test.tsx` | `893ce82ef05f8448990d482825d90a23284523d0eef01ab2f1a073aa79d556df` |
| `apps/arkscope-web/src/settings/settingsCopy.test.ts` | `00babecf33c522dd32476a49cd1c439d7f85ac5991d5b49aebf24c650d401e00` |
| `apps/arkscope-web/src/settings/settingsRegistry.test.ts` | `b9ad9aef50d464ed7b7e6ecd0a9e4348dafb55eca2337e263e654c93221d7044` |
| `apps/arkscope-web/src/settings/settingsRegistry.ts` | `6220227f1eaab74c201804c8c0476705abf66e166a5f5771c0d6981dd1eecdeb` |
| `apps/arkscope-web/src/InvestorProfilePanel.tsx` | `0d22c5f910fe831a68fa5ff33da87af8a267945f33d103376a6c51c4e0cfb88d` |
| `apps/arkscope-web/src/SettingsInvestorProfileIntegration.test.tsx` | `6f14d679ba9e052861946264ed2825ac0a530b9b90b21f0aa63bdf8c27b1b24c` |
| `apps/arkscope-web/src/i18n/resources/en/settings.ts` | `9844a82c1c3f86de00750600361977de0f75b04ead7778146da548c12839fce1` |
| `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts` | `6efe230246784de2717a6106300f82808f25e68d332e156898dcf858e1d8e3d7` |

All Python paths and backend test/configuration owners are also byte-protected.
The backend decoded canonical identity remains exactly
`4527/4eeb117804ad874c83ffe4c04fd25ecd4de4f460801bfbf95d15c1406f32455d`.

---

## 1. Concrete implementation contract

### 1.1 Cache owner and public surface

Add `apps/arkscope-web/src/settings/settingsReadCache.ts`. It is a Settings
utility, not a generic application query framework. It owns:

```text
SettingsReadCache
  inspect(key, now?) -> missing | fresh success | stale success
  load(key, loader, { force? }) -> one shared promise and typed outcome
  replace(key, value, now?) -> current-generation success or non-retained success
  invalidate(key)
  invalidateCredentialAccount(localCredentialId)
  invalidateDataSource(source)
  invalidateAllDataSyncReads()
  clear()

createSettingsReadCache({ clock? })
settingsReadPolicy(key)
oauthAccountUsageKey(localCredentialId)
tradingDayCoverageKey(lookback)
scheduleSettingsIdleWarmup(...)
```

Equivalent names are allowed only if this remains one owner. Required
semantics:

- `App` creates one instance lazily per React root and passes it to
  `SettingsView`; no module singleton is allowed.
- `SettingsViewProps` keeps source compatibility for direct isolated render
  owners: an omitted cache gets one per-`SettingsView` `useRef` fallback that
  dies on unmount. Production `App` always supplies the App-owned instance;
  the fallback may not be exported or shared and cannot provide route-remount
  retention. Idle warmup runs only when the cache was explicitly supplied, so
  legacy direct-render tests do not acquire hidden background requests.
- `inspect` is synchronous and never invokes a loader.
- each current key generation has one in-flight promise shared by visible,
  polling, refresh, and idle callers; invalidation severs the old generation,
  whose still-running promise may finish only as a discarded outcome;
- `force` bypasses freshness suppression but joins an existing promise;
- a loader captures the generation at launch and may write only when that
  generation still matches at successful completion;
- ordinary revalidation error leaves an existing stale success intact;
- invalidation removes the success and increments generation before any
  mutation; a failed mutation cannot restore it;
- errors, promises, and non-serializable/oversize values are never retained;
- all values returned to a component remain usable for that call even when
  retention is refused.

The closed policy constants are exactly:

```text
MAX_ENTRIES = 32
MAX_ENTRY_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
```

The closed resource table is:

| Key | Fresh | Hard retention | Idle |
|---|---:|---:|---|
| `model_catalog` | 60 s | 15 min | yes |
| `oauth_account_usage:<local-credential-id>` | 5 min | 15 min | validated active OAuth GET only |
| `data_schedule` | 5 s when retained state has any running source; otherwise 30 s | 5 min | yes |
| `provider_health` | 30 s | 15 min | yes |
| `provider_config` | 60 s | 15 min | yes |
| `sa_extension_health` | 5 min | 30 min | no |
| `market_data_status` | 60 s | 15 min | yes |
| `trading_day_coverage:15min:<lookback>` | 5 min | 30 min | lookback 10 only |
| `news_status` | 60 s | 15 min | yes |
| `macro_status` | 60 s | 15 min | yes |
| `macro_snapshot` | 60 s | 15 min | yes |

No URL, environment, profile, or UI override is added.

Serialized byte size means UTF-8 bytes of `JSON.stringify(value)`. A thrown
serializer, `undefined`, cycle, or value over the entry cap is usable but not
retained. LRU access is updated on successful `inspect`, successful replace,
and shared-load consumption. Eviction removes only retained success; it does
not cancel or validate an unrelated request.

### 1.2 React integration rule

Do not introduce a second generic loading/error state that can overwrite
existing owner truth. Each owner follows this sequence:

1. inspect synchronously during initialization/effect entry;
2. render retained fresh or stale success immediately when present;
3. invoke `load`; fresh returns without GET, stale/missing starts or joins one;
4. on current successful outcome, use the exact backend DTO;
5. on ordinary error, retain old visible success and set the owner's existing
   bounded error/updating state;
6. on no value/hard expiry, preserve the existing loading/unavailable state;
7. cleanup prevents set-state after unmount, while cache correctness remains
   generation-based rather than cancellation-based.

Receipt time is never presented as provider freshness. Cached DTO fields,
including OAuth lifecycle, quota source, provider timestamps, partial outcome,
and scheduler state, remain byte-semantic inputs to the existing renderers.

### 1.3 Navigation and layout

Only the Settings workflow row gets a Settings-owned wrapper/class. Do not
change `ui/Tabs.tsx`.

- define one Settings CSS custom property for the sticky row height/offset;
- sticky row: `position: sticky`, `top: 0`, opaque existing surface color,
  bounded z-index, stable block size;
- tab list: one row, no wrapping, horizontal overflow on narrow screens;
- directory sticky offset and section `scroll-margin-top` consume the same
  custom property;
- PageHeader remains ordinary scrolling content;
- no page-level horizontal overflow is introduced.

`SettingsDirectory` renders all three group headings and all nine anchors for
an empty query, in registry order. Existing bilingual search filtering and
`aria-current="location"` stay intact.

Navigation intent is explicit:

- accepted manual group switch, including confirmed discard: mount the target
  group, restore the Settings scroll owner to group top, then keep focus on the
  selected tab;
- exact directory/external anchor: mount target group, reveal heading below
  sticky offset, and focus the heading;
- rejected dirty/busy guard: no group, scroll, or focus change.

No inactive panel may remain in the DOM after any navigation.

### 1.4 Idle warmup

After the first committed Settings paint, schedule one cancellable idle task.
Use `requestIdleCallback` when available and a bounded zero-delay fallback when
not; both scheduler and clock must be injectable for deterministic tests.

The task may call only these local GET loaders:

```text
model_catalog
data_schedule
provider_health
provider_config
market_data_status
trading_day_coverage:15min:10
news_status
macro_status
macro_snapshot
oauth_account_usage:<validated-active-local-id>
```

It must obtain or join `model_catalog` before deriving active OAuth local row
IDs. Account responses still pass the existing credential-binding validator
before replacement. The task runs at most once per `SettingsView` mount,
creates no repeating timer/listener, and is cancelled if Settings unmounts
before it starts.

The denylist is structural: no SA extension health, account sync POST,
discovery, credential test/login/refresh, model/provider request, schedule
mutation/run, or Investor Profile request may be supplied to or reached from
the idle loader map. An unknown registry resource is rejected, not skipped
silently.

### 1.5 Existing read owners

| Owner | Cache integration | Behavior that must remain |
|---|---|---|
| `Settings.tsx` | model catalog read/replace/invalidate; warmup owner | mutation refresh and navigation guards |
| `ProviderSection.tsx` | exact account key read/replace/invalidate | five lifecycle states, binding check, 5 min freshness, 10 s cooldown, visible/focus sync POST only |
| `DataSourcesSection.tsx` | schedule/health/config plus visible extension key | extension is visible-only; schedule poll remains 5 s running / 30 s idle and forces/join-loads each tick |
| `DataStorageSection.tsx` | market status and coverage per lookback | 10/15/30/60 keys do not alias; manual refresh forces only storage keys |
| `NewsStorageSection.tsx` | news status | existing partial/error rendering |
| `MacroStorageSection.tsx` | status and snapshot as independent keys | one leg may succeed while the other fails; no all-or-nothing cache write |

Provider mutation rules remain exact:

- model route save/import/export/reset replaces or invalidates catalog;
- credential add/import/login/re-login/activate/metadata/delete invalidates
  catalog and only the affected local credential account key;
- successful cached-account GET/sync replaces only that account key after the
  existing binding and generation checks.

Data Sources rules remain exact:

- schedule enable/interval/run-now invalidates or replaces schedule;
- config import/save/clear invalidates config and health;
- a `running -> terminal` transition invalidates downstream source keys;
- `ibkr_prices` invalidates market status and every retained coverage key;
- `polygon_news`, `finnhub_news`, and `ibkr_news` invalidate news plus market
  status;
- an unknown source invalidates all Data and Sync keys;
- manual extension recheck forces only extension health.

---

## 2. Exact node accounting

### 2.1 Identity derivation

Each stage is derived before implementation from the decoded base stream:

```text
target = sort(unique(base - exact_removed_ids + exact_added_ids))
```

The derivation must assert:

- every removed ID exists exactly once in base;
- every added ID is absent from base;
- added and removed streams are internally unique;
- full target count is `base - removed + added`;
- focused target is independently built from the exact focused file list plus
  the new cache test file, not projected from prose.

### 2.2 Focused owner set

Base focused identity is 14 files / 182 nodes /
`1c56ecf00a6d89d2d51191bcbd95946a8dd00c039f26c3c1d3d0bb979878c002`:

```text
src/AppShell.test.tsx                                      20
src/SettingsWorkspace.test.tsx                             27
src/SettingsCss.test.ts                                     3
src/SettingsInvestorProfileIntegration.test.tsx             3
src/SettingsModelRouting.test.ts                            14
src/ProviderSection.test.ts                                 15
src/SettingsProviderConfig.test.ts                          37
src/SettingsPostPgExitStorage.test.ts                       10
src/SettingsNewsStorage.test.ts                              5
src/SettingsStabilizationCss.test.ts                         2
src/settings/MacroStorageSection.test.tsx                    9
src/settings/settingsBackendCopy.test.ts                    12
src/settings/settingsCopy.test.ts                           10
src/settings/settingsRegistry.test.ts                       15
```

The final focused set adds only
`src/settings/settingsReadCache.test.ts` as its fifteenth file.

### 2.3 Staged identities

| Stage | Delta at stage | Full nodes / SHA-256 | Focused nodes / SHA-256 |
|---|---:|---|---|
| Base | - | `1084 / f0e5ecda1371f0559c1cc92af367b7e32daa91663ef2f316ed67e23129ee9637` | `182 / 1c56ecf00a6d89d2d51191bcbd95946a8dd00c039f26c3c1d3d0bb979878c002` |
| Task 1 cache core | `+17/-0` | `1101 / 6f77e16694bc7994ea62a0e51ec13a7ee79fc9f03851da7a55519b04bcbc801f` | `199 / 543ebdffdf922d73045fa42c1e19ae2aba5cf598e8804c359ec0c868ce27fee3` |
| Task 2 navigation | `+6/-1` | `1106 / 10965b1c8e5a51cbf5d38950b0db8410faef1a528e6dc2856e391267019a37bc` | `204 / e34c217edb518485ebacbbe382a44f47f36e536c9a15f13125add0664910a085` |
| Task 3 lifetime/warmup | `+7/-0` | `1113 / eefdbdaa10c83786cdbf9054b76dcf0bae822bafb129aece422958d3e20f0ee8` | `211 / d74255067e3ca4531c6a2f8590156f20175613c0fdcffd453ab448881ec1bac3` |
| Task 4 Provider | `+3/-0` | `1116 / 09d31fa1bd22d3b0519c8dce2c606d7ec91c41d5b9251437299a2e3a95d74888` | `214 / d44260d583bda710fabd963c1f9af8730aa92835cd8b5a7177ba5f092f381632` |
| Task 5 Data/Storage | `+7/-0` | `1123 / 9262d7b15a926d7eeb60952e4c351c6c9b944772904fdb82438c62a2a51f6c1c` | `221 / a2c20d3607e5fd48982b4e1620089a7b59ee7346c23fc2d2709ec2935bdfe16f` |

Final accounting is exactly `+40/-1`, net `+39`, 98 full files and 15
focused files. The task-labelled additions TSV is
`0437cf44d53244a8baea5151d14ab19bc626a579154807ed6df89d406b464a7b`;
after dropping the task field and C-sorting, its normalized node stream is
`e1d32f68d625316cdc658f5c3a6763f394c34da561314d69f9276a6e374d7a14`.
The task-labelled removal TSV is
`551f6620590eb90b8fccdeaf536e5a60f999736dc56e7b8062025b4ea64f38e7`;
its normalized node stream is
`0042e6192d9d8263ce4ca2767fb8d8da9504b10df17f40d82ff4c7d9980ff9ed`.

### 2.4 Exact additions

The first field is the owning task:

```text
1	src/settings/settingsReadCache.test.ts	Settings read cache > returns_a_fresh_retained_value_without_invoking_its_loader
1	src/settings/settingsReadCache.test.ts	Settings read cache > renders_a_stale_retained_value_while_one_revalidation_runs
1	src/settings/settingsReadCache.test.ts	Settings read cache > shares_one_loader_across_visible_and_idle_callers
1	src/settings/settingsReadCache.test.ts	Settings read cache > discards_old_generation_completion_after_invalidation
1	src/settings/settingsReadCache.test.ts	Settings read cache > preserves_stale_success_after_ordinary_revalidation_failure
1	src/settings/settingsReadCache.test.ts	Settings read cache > does_not_resurrect_invalidated_success_after_mutation_failure
1	src/settings/settingsReadCache.test.ts	Settings read cache > evicts_hard_expired_success_before_render
1	src/settings/settingsReadCache.test.ts	Settings read cache > evicts_least_recently_used_entries_at_the_entry_cap
1	src/settings/settingsReadCache.test.ts	Settings read cache > refuses_retention_above_the_per_entry_byte_cap
1	src/settings/settingsReadCache.test.ts	Settings read cache > evicts_least_recently_used_entries_at_the_total_byte_cap
1	src/settings/settingsReadCache.test.ts	Settings read cache > returns_but_does_not_retain_non_serializable_values
1	src/settings/settingsReadCache.test.ts	Settings read cache > forces_manual_refresh_past_freshness_while_joining_single_flight
1	src/settings/settingsReadCache.test.ts	Settings read cache > invalidates_only_one_local_credential_account_key
1	src/settings/settingsReadCache.test.ts	Settings read cache > maps_price_and_news_sources_to_exact_downstream_keys
1	src/settings/settingsReadCache.test.ts	Settings read cache > invalidates_all_data_sync_reads_for_an_unknown_source
1	src/settings/settingsReadCache.test.ts	Settings read cache > idle_warmup_calls_only_allowlisted_local_GETs_once
1	src/settings/settingsReadCache.test.ts	Settings read cache > idle_warmup_primes_account_usage_only_from_validated_active_OAuth_local_ids
2	src/SettingsWorkspace.test.tsx	Settings workspace > searches_all_groups_and_empty_directory_lists_all_nine_sections
2	src/SettingsWorkspace.test.tsx	Settings workspace > manual_tab_switch_restores_group_top_without_stealing_selected_tab_focus
2	src/SettingsWorkspace.test.tsx	Settings workspace > confirmed_dirty_discard_restores_new_group_top_and_selected_tab_focus
2	src/SettingsWorkspace.test.tsx	Settings workspace > busy_rejection_preserves_group_scroll_and_selected_tab_focus
2	src/SettingsCss.test.ts	Settings workspace CSS contract > keeps_settings_tabs_sticky_nonwrapping_and_horizontally_bounded
2	src/SettingsCss.test.ts	Settings workspace CSS contract > shares_one_sticky_offset_with_directory_and_section_anchors
3	src/AppShell.test.tsx	App shell integration > keeps_one_Settings_cache_across_view_unmount_and_remount
3	src/AppShell.test.tsx	App shell integration > creates_a_fresh_Settings_cache_for_a_new_App_root
3	src/SettingsModelRouting.test.ts	Settings model route save gate > renders_retained_catalog_synchronously_and_joins_idle_revalidation
3	src/SettingsModelRouting.test.ts	Settings model route save gate > replaces_cached_catalog_after_model_route_mutation
3	src/SettingsModelRouting.test.ts	Settings model route save gate > discards_pre_mutation_catalog_completion_after_route_save
3	src/SettingsWorkspace.test.tsx	Settings workspace > starts_one_idle_warmup_after_first_paint
3	src/SettingsWorkspace.test.tsx	Settings workspace > cancels_idle_warmup_before_start_when_Settings_unmounts
4	src/ProviderSection.test.ts	ProviderSection OAuth lifecycle and account usage truth > renders_retained_account_usage_immediately_and_revalidates_with_cached_GET_only
4	src/ProviderSection.test.ts	ProviderSection OAuth lifecycle and account usage truth > preserves_retained_account_truth_when_cached_revalidation_fails_without_sync_POST
4	src/ProviderSection.test.ts	ProviderSection OAuth lifecycle and account usage truth > manual_sync_replaces_only_the_affected_account_cache_entry
5	src/SettingsProviderConfig.test.ts	Settings provider config authority > renders_cached_schedule_health_and_config_before_one_stale_refresh
5	src/SettingsProviderConfig.test.ts	Settings provider config authority > keeps_schedule_polling_mounted_only_with_retained_cache_truth
5	src/SettingsProviderConfig.test.ts	Settings provider config authority > caches_extension_health_only_after_visible_mount_and_manual_recheck
5	src/SettingsProviderConfig.test.ts	Settings provider config authority > invalidates_price_news_and_unknown_downstream_keys_after_source_completion
5	src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > keys_trading_day_coverage_by_lookback_and_forces_only_storage_reads
5	src/SettingsNewsStorage.test.ts	SettingsView news storage copy > renders_cached_news_status_while_one_stale_refresh_runs
5	src/settings/MacroStorageSection.test.tsx	MacroStorageSection > caches_status_and_snapshot_independently_and_refreshes_only_requested_legs
```

### 2.5 Exact removal

The first field is the owning task. The existing name encodes the superseded
active-group-only behavior. Replace, do not retain or skip, this one node:

```text
2	src/SettingsWorkspace.test.tsx	Settings workspace > searches_all_groups_while_empty_directory_stays_in_active_group
```

No other existing ID may disappear or be renamed.

---

## 3. RED-first and mutation discipline

### 3.1 RED admission

Each task adds its exact test IDs before product code. RED is admissible only
when:

- collection succeeds and matches that task's staged identity;
- every new owner executes;
- failure is caused by the absent or old product contract, not an import,
  fixture, syntax, timer leak, unhandled promise, or network error;
- no unrelated pre-existing node fails; and
- the RED transcript and structured list output are retained under a fresh
  task artifact root.

The Task 2 replacement node must be removed and added in the same RED commit;
there is no intermediate duplicate-contract state.

### 3.2 Required mutations

After all product tasks are GREEN, execute five mutations independently from a
fresh exact-tip copy. Each mutation has an exact diff, owning command, RED
outcome, and pre/post owner SHA equality.

| ID | Semantic mutation | Required RED owner |
|---|---|---|
| M1 | remove/change Settings sticky positioning or wrapping rule | sticky CSS node |
| M2 | restore active-group-only empty directory | complete-nine-section node |
| M3 | remove current-generation equality before cache replacement | old-generation discard node |
| M4 | add `sa_extension_health` or another forbidden operation to idle allowlist | idle denylist node |
| M5 | broaden credential invalidation from one local ID to all account keys | exact credential invalidation cache and Provider nodes |

An edit to dead code, a helper bypassed by the owner, or a mutation that leaves
the named owner GREEN is rejected evidence. Never stack mutations. Restore by
the reviewed exact diff and verify the entire owning file SHA, not a selected
hunk.

---

## 4. Task sequence

For Tasks 1-5, RED is recorded but not committed as a broken tree. Each GREEN
family lands as one scoped product/test commit followed by one docs-only
evidence/status commit. Stop after that pair for independent review; a later
task is unauthorized until the preceding review is GREEN.

> **Post-Task-0 execution ruling:** Independent review returned GREEN at
> `8aca8c1a`. The user then authorized Tasks 1-5 as one continuous batch.
> Per-task RED/GREEN artifacts, staged identities, product/docs commit pairs,
> and every stop condition remain mandatory; only the intermediate wait for
> independent review is waived. Any drift stops the batch. Task 2's early
> browser check, Task 6, and Task 7 remain hard gates.

> **Task 2 stop-and-amend ruling:** The exact stage-2 stream matched before
> implementation, and the intended RED was admissible. The expanded focused
> GREEN gate then exposed one additional pre-existing assertion owner:
> `SettingsPostPgExitStorage.test.ts` still required the superseded
> active-group-only directory. Task 2 therefore stopped before commit or
> browser work. This amendment adds only that existing test file and its
> existing node to Task 2 assertion ownership. The node name is unchanged, so
> every reviewed full/focused identity and the global `+40/-1` ledger remain
> byte-identical. Independent focused review of this amendment is required
> before Task 2 resumes; Tasks 3-5 remain unstarted.
>
> **Batch-authorization clarification:** The preceding extra review wait was an
> over-conservative interpretation. The user clarified that the existing
> Tasks 1-5 batch authorization already covers this bounded assertion-owner
> correction. That clarification waives only the added wait; the stop record,
> scoped amendment, exact stage identities, full focused rerun, early browser
> gate, product/docs commit pair, and all later stop conditions remain binding.

### Task 0 - Re-ground and open evidence

No product/test code changes.

> Executed at reviewed plan tip `5755ed54`. The 72-entry raw packet is rooted
> at `/tmp/settings-navigation-warm-cache-task0-5755ed54`; its `SHA256SUMS`
> identity is
> `d0da19c1d76153f3ece27281f8948d5a332ce246602a6123c139604923cb19fe`.
> All Steps 1-8 completed, no product/test byte changed, and Task 1 remains
> unauthorized pending independent Task 0 review.

1. Verify branch, design authority, product base ancestry, clean main/worktree,
   lockfiles, node_modules identity, Node version, normalizer identity,
   Playwright version, and Chrome version.
2. Rebuild full and focused decoded base streams. Require the two base hashes
   in Section 2.
3. Mechanically reconstruct all stage streams from Sections 2.4/2.5 and require
   every count/hash in Section 2.3.
4. Run the exact fourteen-file focused baseline in one command: 182 passed.
5. Run full Vitest once. Any failure is not admitted by history; diagnose it.
   A retry may be admitted only with the first transcript retained and an
   isolated owning-file control.
6. Run typecheck, build, and i18n literal scanner.
7. Create the ten-path byte-protection manifest and a full backend path
   manifest. Reproduce backend collect-only `4527` and its full SHA with zero
   test bodies executed.
8. Create
   `docs/superpowers/evidence/2026-08-09-settings-navigation-warm-cache.md`
   with raw artifact paths/hashes and explicit unstarted-task statements.
9. Commit docs/evidence only, then stop for independent Task 0 review.

### Task 1 - Cache core

Owned paths:

```text
apps/arkscope-web/src/settings/settingsReadCache.ts
apps/arkscope-web/src/settings/settingsReadCache.test.ts
```

> Complete at product/test commit `e34aaef8`. Stage 1 reproduced exact
> `1101/6f77e166...` and focused `199/543ebdff...`; owner `17/17`, focused
> `199/199`, and typecheck are GREEN. Raw packet:
> `/tmp/settings-navigation-warm-cache-task1-8aca8c1a` (`38` entries,
> manifest `b63d5cdf...`).

1. Add all seventeen Task 1 nodes and prove admissible RED at exact stage 1.
2. Implement the closed policy registry, synchronous inspection, single-flight,
   generation-safe load/replace/invalidate, exact account/source invalidation,
   LRU/byte bounds, and injected clock/idle scheduler.
3. Keep the module free of React, `api.ts` imports, storage APIs, logging,
   telemetry, and provider-specific raw DTO parsing. Loaders are injected.
4. Prove 17/17 GREEN, stage-1 full/focused identities, no open timers, and no
   filesystem/network call.
5. Commit product+tests and docs evidence separately, then stop for review.

### Task 2 - Sticky navigation and complete directory

Owned paths:

```text
apps/arkscope-web/src/Settings.tsx
apps/arkscope-web/src/settings/SettingsDirectory.tsx
apps/arkscope-web/src/settings/settings.css
apps/arkscope-web/src/SettingsWorkspace.test.tsx
apps/arkscope-web/src/SettingsCss.test.ts
apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts
```

> Complete at product/test commit `ecf87f0c`. Stage 2 reproduced exact
> `1106/10965b1c...` and focused `204/e34c217e...`; direct owners ended
> `45/45`, the complete focused set ended `204/204`, typecheck and all ten
> protected rows are GREEN, and the hermetic desktop/mobile browser gate found
> no sticky overlap, clipping, horizontal overflow, inactive panel retention,
> or focus/scroll error. Raw packet:
> `/tmp/settings-navigation-warm-cache-task2-4745b359` (`17` entries,
> manifest `73f1a4cd...`).

1. Replace the superseded directory node and add the other five exact Task 2
   nodes. Require stage-2 identity and admissible RED.
2. Add a Settings-only sticky wrapper/offset and complete directory rendering.
3. Make manual-group and exact-anchor navigation two explicit post-mount
   effects. Rejected guards must schedule neither.
4. Evolve the existing
   `post-PG-exit storage panels > uses_normal_user_outcomes_in_the_enabled_settings_directory`
   assertion from four active-group links to the complete nine-section
   registry order. Its node ID must not change. Re-run all existing Settings
   workspace/CSS/registry/copy/active-mount owners.
5. Run an early desktop/mobile browser check for sticky overlap, all nine
   entries, group-top restore, and exact anchor focus.
6. Verify generic Tabs and frozen fixtures byte-identical; commit and stop.

### Task 3 - App lifetime, catalog cache, and idle warmup

Owned paths:

```text
apps/arkscope-web/src/App.tsx
apps/arkscope-web/src/Settings.tsx
apps/arkscope-web/src/AppShell.test.tsx
apps/arkscope-web/src/SettingsModelRouting.test.ts
apps/arkscope-web/src/SettingsWorkspace.test.tsx
apps/arkscope-web/src/settings/settingsReadCache.ts
apps/arkscope-web/src/settings/settingsReadCache.test.ts
```

> **Bounded Task 3 integration amendment:** Wiring the reviewed idle account
> warmup against the real credential DTO exposed that stored credential IDs
> are `local:<positive-int>`, while Task 1's key validator rejected every
> colon. Synthetic `local-oauth` passed the cache-only probe but could not
> exercise the product shape. Task 3 therefore also owns the existing cache
> validator and its existing
> `idle_warmup_primes_account_usage_only_from_validated_active_OAuth_local_ids`
> node: accept only the exact stored-local-ID shape when a colon is present and
> replace the synthetic fixture with `local:7`. No test node is added, removed,
> renamed, or skipped; stage `1113/211`, global `+40/-1`, cache bounds, secret
> exclusion, API DTOs, and every protected byte remain unchanged. The user's
> Tasks 1-5 batch authorization covers this bounded correction without an
> added review wait; all technical gates remain binding.

> Complete at product/test commit `462bb8af`. The seven exact nodes produced
> `64P/7F` before product wiring and then GREEN; the Task 3/cache owner group is
> `88/88`, the wider App/Settings/protected group is `121/121`, typecheck is
> GREEN, and exact identities are `1113/eefdbdaa...` plus focused
> `211/d7425506...`. The real `local:7` fixture correction is included without
> node drift. Packet:
> `/tmp/settings-navigation-warm-cache-task3-d4e4bc4d` (`11` payload entries,
> manifest `77e338a2...`). The intentionally wider intermediate focused run is
> retained as rejected `202P/9F`; Task 5 must remove those duplicate GETs by
> joining the shared cache, not by weakening call-count owners.

1. Add seven exact Task 3 nodes and prove stage-3 RED.
2. Create one cache lazily per App root and pass it through `SettingsView`.
3. Convert model-catalog initialization and every reviewed catalog mutation to
   inspect/load/replace/invalidate without changing route/model semantics.
4. Schedule one post-paint idle warmup with the exact allowlist. Cancel before
   start on Settings unmount. Do not retain a listener or timer afterward.
5. Prove route-away/back reuses data, a new App root does not, stale catalog
   remains visible during one revalidation, and pre-mutation completion cannot
   repopulate.
6. Re-run App shell, model routing, Settings active-mount, protected owners,
   typecheck, and stage identities; commit and stop.

### Task 4 - OAuth account read integration

Owned paths:

```text
apps/arkscope-web/src/Settings.tsx
apps/arkscope-web/src/settings/ProviderSection.tsx
apps/arkscope-web/src/ProviderSection.test.ts
```

Bounded Task 4 ownership amendment: `Settings.tsx` is an existing Task 3
owner and the only component that holds the App-owned `SettingsReadCache` at
the Provider render site. Task 4 may change that call site only to pass the
same cache instance into `ProviderSection`; it may not add a module-global
cache, create another App-lifetime owner, or otherwise change Settings
behavior. This amendment changes no test node, staged identity, or `+3/-0`
Task 4 ledger.

1. Add three exact Task 4 nodes and prove stage-4 RED.
2. Replace Provider-local snapshot retention/generation maps with the shared
   exact account key. Keep component display state, existing credential-bound
   response validation, visible/focus stale sync, ten-second manual cooldown,
   and lifecycle rendering.
3. A cached GET may revalidate automatically; a sync POST is reached only by
   the already-reviewed visible/focus/manual policy, never by generic warmup.
4. Credential mutation invalidates only its local account key and catalog.
   Successful sync replaces only after the existing binding/generation checks.
5. Prove no POST on retained read/error, no raw account ID key, unrelated
   account survival, all Provider tests, and stage identities; commit and stop.

### Task 5 - Data Sources and storage readers

Owned paths:

```text
apps/arkscope-web/src/settings/DataSourcesSection.tsx
apps/arkscope-web/src/settings/DataStorageSection.tsx
apps/arkscope-web/src/settings/NewsStorageSection.tsx
apps/arkscope-web/src/settings/MacroStorageSection.tsx
apps/arkscope-web/src/SettingsProviderConfig.test.ts
apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts
apps/arkscope-web/src/SettingsNewsStorage.test.ts
apps/arkscope-web/src/settings/MacroStorageSection.test.tsx
```

1. Add seven exact Task 5 nodes and prove final-stage RED.
2. Integrate schedule/health/config with independent outcomes. Initial visible
   read may use cache; every mounted schedule poll force-loads/joins so the
   5/30-second cadence is unchanged.
3. Keep extension health outside warmup; visible mount may cache it and manual
   recheck force-loads only it.
4. Detect reviewed `running -> terminal` source transitions and apply the exact
   downstream invalidation map. Unknown source clears all Data/Sync read keys.
5. Integrate market status, per-lookback coverage, news status, macro status,
   and macro snapshot. Preserve independent macro leg outcomes.
6. Run all focused owners, all four final collection identities, protected
   owners, typecheck, and browser request-ledger spot check; commit and stop.

### Task 6 - Mutations and final admission

No feature expansion is allowed.

1. Run M1-M5 independently with exact mutation diffs and exact restoration.
2. Rebuild final full/focused streams and require `1123/9262d7b1...` plus
   `221/a2c20d36...`; verify the `+40/-1` delta by exact node ID.
3. Run the exact 15-file focused owner set, then full Vitest. Require 1,123
   passed and zero failed. Existing explicit skips remain only if they belong
   to the final list output; never infer runtime arithmetic from collection.
4. Run typecheck, build, and i18n scanner; record the existing chunk warning
   separately from exit status.
5. Recheck all ten protected path bytes and every Python/backend path byte.
   Reproduce backend collect-only `4527` and
   `4eeb117804ad874c83ffe4c04fd25ecd4de4f460801bfbf95d15c1406f32455d`.
   A backend runtime is not substituted for the stronger
   no-Python-byte-change proof;
   any Python drift stops the line and requires amendment.
6. Execute the browser matrix in Section 5, save DOM/result JSON and both
   screenshots, and inspect screenshots at original resolution.
7. Manifest every generated/ignored/untracked artifact. Remove only exact new
   paths; any pre-existing modified artifact is a stop.
8. Complete evidence with raw paths/hashes and stop for independent
   implementation review before merge.

### Task 7 - Merge and closeout

Only after independent Task 6 GREEN:

1. prove product base/design/implementation ancestry and a clean main tree;
2. fast-forward merge only; do not push;
3. use a fresh exact-master worktree and new artifact names to rerun final
   collection, focused/full Vitest, typecheck/build/scanner, protected bytes,
   backend collect-only identity, and browser matrix;
4. commit docs-only closeout after independent focused review; and
5. only then re-derive Tranche B's absolute identities once. Its reviewed
   relative `-138/+18` ledger is not changed by this slice.

---

## 5. Browser verification contract

### 5.1 Hermetic harness

Use Python Playwright 1.58.0 with the pinned system Chrome and a temporary
browser profile. Start Vite on a free loopback port. Route every ArkScope API
request through an in-process deterministic fixture table; unknown requests
fail the run. Do not start the sidecar, read production profile data, inherit
credentials, or allow external network.

The fixture table must contain realistic valid shapes for catalog, local
account snapshots, schedule, provider health/config, market status, coverage,
news, macro status/snapshot, and visible extension health. It must record
method, normalized path, start/end sequence, and response generation. Raw
tokens/account IDs are absent; local credential IDs use explicit test values.

The harness source, fixture payload, Vite log, Chrome log, request ledger, DOM
result JSON, screenshots, and process cleanup receipt receive SHA-256 entries.
Vite, Chrome, child process groups, and the temporary profile must be absent
after completion.

### 5.2 Viewport matrix and assertions

Run `1322 x 777` and `390 x 844` at page top and deep Data Sources scroll.

For each relevant case assert:

- workflow tabs remain visible and clickable at depth;
- the wide rail or mobile Drawer exposes exactly nine unique anchors under
  three groups in registry order;
- manual group switch lands at the new group top and keeps selected-tab focus;
- cross-group directory selection lands the exact heading below the sticky row
  and focuses it;
- rejected navigation leaves group, scroll, and focus unchanged;
- no inactive tabpanel/section effect owner remains mounted;
- no page-level horizontal overflow, overlap, clipped tab label, or hidden
  mobile directory control;
- fresh route-away/back renders retained content with no duplicate GET or
  loading replacement;
- stale fixture remains visible while exactly one GET is pending;
- request ledger contains only allowlisted local GETs during idle warmup, with
  no POST, provider/model call, discovery, schedule run, or extension-health
  idle request; and
- console errors, page errors, failed unknown routes, and leaked processes are
  zero.

DOM assertions are admission authority; screenshots are required visual proof
for framing/overlap and must not replace DOM or request-ledger checks.

---

## 6. Stop conditions

Stop and amend before continuing if any of the following occurs:

1. design authority, product base, toolchain, or decoded base identity differs;
2. any staged node count/hash differs or a node changes outside `+40/-1`;
3. RED is a collection/import/fixture/network/timer failure rather than the
   intended missing contract;
4. more than one Settings tabpanel or inactive effect owner remains mounted;
5. generic `Tabs`, frozen fixture, registry anchor/order/copy, API DTO, backend,
   or Investor Profile protected bytes change;
6. cache becomes module-global, persistent, unbounded, or retains a
   secret/draft/raw account ID/raw exception;
7. stale generation can repopulate, mutation failure restores invalidated
   data, or credential invalidation broadens beyond one local row;
8. ordinary refresh error hides prior success or cache receipt time is shown as
   provider freshness;
9. idle work reaches a POST, provider/model execution, discovery, credential
   mutation/refresh/test, schedule run, extension subprocess, or Investor
   Profile;
10. schedule polling changes from mounted-only 5/30-second behavior or OAuth
    visible/focus/cooldown/binding semantics change;
11. source invalidation omits a reviewed dependent key or silently ignores an
    unknown source;
12. a cache size/freshness constant gains a runtime override;
13. browser fixtures permit unknown network, browser/Vite processes survive,
    or screenshots/DOM show overlap, clipping, or page overflow;
14. full Vitest failure is dismissed as the known baseline transient without
    owner isolation and a clean admitted rerun;
15. a mutation leaves its owning node GREEN or restoration is not byte-exact;
16. a pre-existing generated/data/profile path changes;
17. implementation requires a backend/API change, persistent storage, or a
    second query/cache abstraction; or
18. Settings completion is used to alter Tranche B's reviewed relative ledger.

---

## 7. Independent review obligations

The reviewer must reconstruct from raw list/runtime/browser artifacts rather
than trust evidence prose:

- base and all staged full/focused node streams;
- exact `+40/-1`, the one replacement, and zero other ID drift;
- cache policy constants, resource registry, byte/LRU behavior, and generation
  outcomes;
- exact invalidation table and idle denylist;
- active-only DOM/effect ownership;
- M1-M5 semantic RED and byte-exact restoration;
- final focused/full Vitest, typecheck/build/scanner results;
- protected frontend and complete backend byte/collection identity;
- browser DOM/request/process results and screenshot framing at both viewports;
- artifact cleanup and clean worktrees.

Until that review is GREEN, Task 7 merge and the Tranche B identity rebase are
unauthorized.
