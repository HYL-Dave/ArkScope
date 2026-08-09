# Settings Persistent Navigation and Bounded Warm Cache Design

> **Status: DESIGN WRITTEN - INDEPENDENT REVIEW REQUIRED.**
>
> **Date:** 2026-08-09
>
> **Grounding base:** `3d18e9c0ea54d99fc4824b7919d74a4c3a38502b`
> (`provider-smoke hygiene LIVE COMPLETE`)
>
> **Scope:** Settings navigation persistence, a complete section directory,
> and a bounded app-session cache for existing read-only Settings DTOs.

## 1. Problem and grounded facts

The user supplied two 1322 x 777 screenshots of Data and Sync:

| Screenshot | SHA-256 |
|---|---|
| `Screenshot from 2026-07-20 20-46-40.png` | `6376edb13d4275800032bb83774f1b67bc836592ef887c7e3c001508817a3648` |
| `Screenshot from 2026-07-20 20-46-49.png` | `bc6187be4695f9b8a3c149cc9218dd6c19b62e59cb44500be4667fac42f816ee` |

At page top the three workflow tabs are available. After scrolling, the
directory rail remains visible but the workflow tabs are gone. The empty-query
directory also lists only the active group's four entries, so changing workflow
requires returning to the top.

The relevant implementation facts at the grounding base are:

- `.main` is the scroll owner; `.ui-tab-list` wraps and is not sticky.
- `Tabs.tsx` mounts only the selected panel. This active-only lifecycle is
  tested and must remain.
- `SettingsDirectory.tsx` searches all groups only when the query is non-empty;
  otherwise it renders `settingsGroup(activeGroup).sections`.
- The registry already owns all nine stable anchors in `4 / 1 / 4` workflow
  order, and cross-group selection already mounts and focuses an exact anchor.
- Accepted manual group changes select the new group's first anchor but do not
  restore the Settings scroller to group top.
- The directory rail is sticky; section anchors do not reserve space for a
  future sticky tab row.

### 1.1 Read and side-effect boundary

| Owner | Existing initial reads | Existing continuing behavior |
|---|---|---|
| Settings | model catalog | refresh after model/credential mutations |
| Providers | cached account-usage GET for active OAuth rows | visible-only stale sync POST and manual sync |
| Data Sources | schedule, provider health/config, SA extension health | mounted-only schedule poll; manual extension recheck |
| Data Storage | market status and 10-day 15-minute coverage | manual refresh / lookback change |
| News Storage | news status | manual refresh |
| Macro Storage | macro status and snapshot | manual refresh |
| Investor Profile | profile and calibration state | edits, calibration, and conflict handling |

`/providers/health`, schedule/config reads, and the storage reads are local
ArkScope projections. `/sa/extension-health` is different: the existing owner
documents that it spawns a native-host subprocess. It may be cached after a
visible read, but it must never be idle-prefetched.

OAuth is already LIVE COMPLETE. It owns five lifecycle states, credential-bound
snapshots, five-minute account freshness, ten-second manual cooldown,
same-account validation, visibility gating, and exact generation invalidation.
This slice consumes those read models; it does not reinterpret auth or quota.

### 1.2 Frozen and identity boundary

The `BASELINE_SECTIONS` blocks in `settingsCopy.test.ts` and
`settingsRegistry.test.ts` are frozen historical fixtures. They must remain
byte-identical. `SettingsCss.test.ts` is also an owner because it inventories
literal Settings classes.

The fourteen principal paths total 6,898 lines. Hashing the
`LC_ALL=C`-sorted `sha256sum` output for these rows yields
`b993b48d51e4dae729e83924aa84c41466b0355f1018cd815b4dfe36254280e0`.

| Path | Lines | SHA-256 |
|---|---:|---|
| `apps/arkscope-web/src/App.tsx` | 244 | `13b6bf02f75df4f02ccdcad648b1b4338f318b3d9b7e920c2e4ef3699a23f572` |
| `apps/arkscope-web/src/Settings.tsx` | 1,026 | `3f8bdb78c74f1788972569ceb05bba7fb7f8fb8966ce82673ff2d01808adab91` |
| `apps/arkscope-web/src/ui/Tabs.tsx` | 103 | `d63b8c7e41b04d4782345387149909447cd7f653e0fb4dddc0866063f73f6526` |
| `apps/arkscope-web/src/settings/SettingsDirectory.tsx` | 91 | `7998aed085f48399cfda3d5c369759820588ca705078573e79919621fe9e58d7` |
| `apps/arkscope-web/src/settings/settings.css` | 198 | `064b52fdb0ab188d065e9f148bc1da3bcf197c33bfca010abbef976a52656864` |
| `apps/arkscope-web/src/settings/DataSourcesSection.tsx` | 1,082 | `304c043ebdb30d06a24ad365fd0fd77ff49a17cf8062492b6bb56fdf2e1f213f` |
| `apps/arkscope-web/src/settings/ProviderSection.tsx` | 1,698 | `03f14d41421389d34c13465d6fa0323435bd8dabab79ae673222212d94b46606` |
| `apps/arkscope-web/src/settings/DataStorageSection.tsx` | 441 | `c250aba697210c80ce01b621b4611f329ead0b8b53273844d0d52313215008a8` |
| `apps/arkscope-web/src/settings/NewsStorageSection.tsx` | 112 | `84bc6af7132f8934f0a3315f9f6dc2279f25cb54e4bca4ef919cfb850345a87e` |
| `apps/arkscope-web/src/settings/MacroStorageSection.tsx` | 240 | `86f15683b0a6d2db7bdeac1f3d506b5cc59627add57878866c74986a56f7f49b` |
| `apps/arkscope-web/src/SettingsWorkspace.test.tsx` | 819 | `d570791c2d369dd96ddfd7b5afc975b31b03916739fc64c998ca6e48b129e1e9` |
| `apps/arkscope-web/src/SettingsCss.test.ts` | 91 | `fc3e7b831b7deccfcce699172933071bde12eb5d9ddd91b44fa2210c4bbb456d` |
| `apps/arkscope-web/src/settings/settingsCopy.test.ts` | 437 | `00babecf33c522dd32476a49cd1c439d7f85ac5991d5b49aebf24c650d401e00` |
| `apps/arkscope-web/src/settings/settingsRegistry.test.ts` | 316 | `b9ad9aef50d464ed7b7e6ecd0a9e4348dafb55eca2337e263e654c93221d7044` |

The inherited reviewed frontend identity is `97 files / 1,084 tests`, decoded
node stream
`f0e5ecda1371f0559c1cc92af367b7e32daa91663ef2f316ed67e23129ee9637`.
The implementation plan must re-ground it.

## 2. Locked product decisions

### LD 1 - Persistent workflow navigation

Only the Settings tablist becomes sticky at the top of the `.main` scroll
owner. The shared `Tabs` behavior remains unchanged.

- The PageHeader scrolls away normally.
- The row is opaque, has a bounded z-index, and uses one stable height.
- Tabs never wrap; narrow screens use horizontal overflow.
- One Settings CSS custom property supplies the sticky offset to the tablist,
  directory rail, and section anchor `scroll-margin-top`.
- It must not cover headings, directory content, or the mobile directory button.

After an accepted manual tab change, including a confirmed discard, the new
group starts at its top and the selected tab retains focus. Exact directory or
external navigation instead reveals and focuses the requested anchor. A
rejected dirty/busy guard causes no group or scroll change.

### LD 2 - Complete directory

With an empty query, the desktop rail and mobile Drawer render all nine sections
under all three group headings in registry order. Search remains bilingual and
cross-group. The active anchor keeps `aria-current="location"`; selecting a
different group's entry uses the existing guard and exact-anchor sequence.

This supersedes only the old active-group-only directory rule. It does not add,
rename, or reorder groups, sections, anchors, or visible copy.

### LD 3 - One mounted group remains mandatory

Inactive groups stay structurally unmounted. No hidden panel, React Offscreen
tree, retained portal, or CSS-hidden copy is allowed. Leaving a group still
removes its timers, focus/visibility listeners, OAuth flow UI, schedule poll,
sync effects, and subprocess triggers. Speed comes from immutable read
snapshots, not retained components.

### LD 4 - App-session memory cache

`App` owns one Settings-only cache instance. It survives workflow and Settings
route changes, then disappears on frontend reload/process exit. It is not a
module-global singleton and is replaceable per test root.

Only successful DTOs already returned by reviewed local APIs may be retained.
The cache does not become domain authority; it records resource key, receipt
time, generation, serialized size, access order, and one in-flight promise.

No cache data enters `localStorage`, `sessionStorage`, IndexedDB, profile DB,
filesystem, logs, or telemetry. It never stores tokens, unmasked keys,
authorization URLs, provider raw account IDs, draft form values, or raw
exceptions. Saved user labels and masked fields already present in a redacted
UI DTO may remain in this process-only cache; they may not be logged or
persisted.

### LD 5 - Closed resource registry

| Resource key | Fresh | Hard retention | Idle |
|---|---:|---:|---|
| `model_catalog` | 60 s | 15 min | yes |
| `oauth_account_usage:<local-credential-id>` | existing 5 min | 15 min | active OAuth GET only |
| `data_schedule` | 5 s running / 30 s idle | 5 min | yes |
| `provider_health` | 30 s | 15 min | yes |
| `provider_config` | 60 s | 15 min | yes |
| `sa_extension_health` | 5 min | 30 min | **no** |
| `market_data_status` | 60 s | 15 min | yes |
| `trading_day_coverage:15min:<lookback>` | 5 min | 30 min | default lookback 10 only |
| `news_status` | 60 s | 15 min | yes |
| `macro_status` | 60 s | 15 min | yes |
| `macro_snapshot` | 60 s | 15 min | yes |

The schedule fresh window follows its retained `running` state; visible
polling remains 5/30 seconds and is never extended by retention.

The account key uses the existing local credential-row ID, never provider raw
account ID/email/token claims. Existing response validation must confirm the
credential binding before insertion.

The cache is capped at 32 entries, 512 KiB serialized UTF-8 JSON per entry, and
4 MiB serialized total. Oversize/non-serializable responses remain usable by
the visible owner but are not retained. LRU eviction restores both caps. These
named constants have no user or URL override in v1.

### LD 6 - Freshness, single-flight, and generations

1. Fresh success renders synchronously and starts no request.
2. Retained stale success stays visible while one revalidation runs.
3. Concurrent visible/prefetch callers share one promise.
4. Only a successful current-generation response replaces a value.
5. Ordinary revalidation failure keeps the prior success and exposes refresh
   failure through the visible owner's existing bounded state.
6. Invalidation increments generation and removes the old value.
7. An older in-flight response is discarded and cannot repopulate the key.
8. Hard-expired success is evicted and never rendered.
9. Errors and rejected promises are never cache values.

Cancellation is best effort; generation is the correctness boundary. Manual
refresh bypasses freshness suppression but still joins an existing
single-flight for the same key.

### LD 7 - Explicit invalidation

| Event | Required action |
|---|---|
| model route save/import/export/reset | replace or invalidate `model_catalog` |
| credential add/import/login/re-login/activate/metadata/delete | invalidate `model_catalog` and only that credential's account key |
| cached account GET or sync POST success | replace exact account key after existing binding/generation checks |
| schedule enable/interval/run-now | replace/invalidate schedule and source-owned downstream keys |
| provider config import/save/clear | replace/invalidate provider config and health |
| completed Data Sources lifecycle transition | refresh schedule/health and invalidate source-owned storage keys |
| manual section refresh | force only that section's key set |
| SA extension recheck | force only extension health |

Downstream source mapping is:

- `ibkr_prices` -> market status and all cached coverage keys;
- `polygon_news`, `finnhub_news`, `ibkr_news` -> news and market status;
- unknown future source -> all Data and Sync read keys.

No credential mutation may clear unrelated account keys for convenience, and no
post-mutation failure may resurrect an invalidated value.

### LD 8 - One-shot local idle warmup

After first Settings paint, one cancellable idle task may prime only LD 5
resources marked for idle use. It obtains `model_catalog` first or joins its
single-flight. Only a validated catalog may supply active OAuth local IDs for
cached account-usage GETs.

The task adds no interval, recursive timeout, focus listener, or visibility
listener. Leaving Settings before it starts cancels it. It never invokes:

- SA extension health;
- account sync POST;
- credential discovery, test, login, refresh, or provider contact;
- provider/model execution;
- schedule run or mutation; or
- Investor Profile/calibration reads or mutations.

Visible Data Sources may still read/cache extension health once and recheck it
manually. Existing mounted-only schedule polling and visible-only OAuth sync
remain unchanged.

### LD 9 - Cache state must remain honest

A retained value is only a rendering optimization:

- fresh success has no cache badge;
- stale success remains visible with the owner's updating state;
- stale refresh failure retains the last success plus the owner's error/partial
  state;
- no value/hard expiry uses the existing loading or unavailable state.

Receipt time is not provider freshness. The cache may not rewrite OAuth
lifecycle/quota, provider health, scheduler outcome, source timestamps, or
partial/error semantics.

Investor Profile is excluded from v1 because it owns drafts and conflict
handling. The two frozen fixture blocks, all nine anchors, backend routes/DTOs,
and generic `Tabs` semantics remain unchanged.

## 3. Required RED and acceptance contracts

Before implementation, the plan must predeclare exact test-node changes and
start with failing contracts for:

1. sticky one-row tabs, shared offset, and opaque background;
2. all nine empty-query entries in wide rail and mobile Drawer;
3. exact cross-group anchor focus below the sticky row;
4. accepted manual tab change restoring group top without focus theft;
5. rejected navigation causing no scroll/group change;
6. inactive groups retaining zero DOM, poll, sync, or subprocess owner;
7. fresh repeat entry rendering with zero GET;
8. stale render plus exactly one shared revalidation;
9. invalidated old-generation completion being discarded;
10. ordinary refresh failure preserving prior success while mutation failure
    cannot restore it;
11. hard expiry, LRU count, per-entry bytes, and total bytes;
12. idle denylist and visible-only extension behavior;
13. exact credential invalidation and current OAuth TTL/cooldown/source states;
14. source-specific schedule invalidation and unknown-source fail-safe;
15. frozen `BASELINE_SECTIONS`, stable anchors, and active-only mount; and
16. no persistent storage, secret, raw provider account ID, or draft retention.

Semantic mutations must independently break sticky behavior, complete
directory, generation protection, idle denylist, and exact credential
invalidation. Mutating only a helper is not evidence.

### 3.1 Browser and performance acceptance

Playwright must verify both 1322 x 777 and a narrow mobile viewport at page top
and deep Data Sources scroll:

- all workflow tabs remain usable at depth;
- all nine directory entries are reachable;
- manual switch lands at group top;
- directory switch lands below the sticky row on the exact heading;
- no overlap, clipped tab text, or page-level horizontal overflow.

DOM assertions and screenshots are both required. Performance acceptance is
structural, not a flaky millisecond threshold: a fresh hit causes no loading
replacement/GET; stale data remains visible during one GET; inactive groups own
no effects; cache bounds hold.

### 3.2 Regression gates

The implementation plan must:

- re-derive decoded Vitest collection identity and account every node change;
- run focused Settings, Provider, Data Sources, storage, CSS, and frozen-fixture
  owners;
- run full Vitest, typecheck, build, i18n scanner, and browser checks; and
- prove backend canonical collection remains exactly
  `4527/4eeb1178...` with no Python product/test change.

## 4. Scope and stop conditions

Expected ownership is limited to `App.tsx`, `Settings.tsx`, a new
Settings-only cache module/tests, `SettingsDirectory.tsx`, affected
Settings read owners/tests, `settings.css`, and browser evidence.

This slice does not change backend APIs, provider/model registries or defaults,
OAuth semantics, Investor Profile behavior, calendar scheduling, Tranche B, FD
metering, fundamentals ingestion, git-crypt cleanup, or the generic Tabs mount
contract.

Stop and amend if implementation:

1. mounts more than one tabpanel or retains hidden effects;
2. triggers provider/model execution, a POST, schedule run, credential
   discovery/test/login/refresh, or extension subprocess from idle warmup;
3. persists cache data or retains a secret/draft/raw provider account ID;
4. permits stale-generation resurrection or broad account invalidation;
5. edits either frozen fixture block, group/anchor/copy, backend DTO/route, or
   generic Tabs behavior;
6. changes OAuth freshness/cooldown/visibility/no-probe semantics;
7. cannot account exactly for frontend collection drift; or
8. cannot pass the deep-scroll desktop/mobile overlap checks.

## 5. Gate order

1. Independent review reconstructs screenshot facts, current lifecycle/read
   boundary, OAuth handoff, frozen fixtures, and source identities.
2. After GREEN, create one RED-first implementation plan with exact node
   ledgers, cache policy tests, invalidation table, mutations, and browser
   matrix.
3. Implement cache core, navigation/directory behavior, then read-owner
   integration by family.
4. Run all regression and visual gates; stop for implementation review before
   merge.
5. Only after this slice merges, re-derive Tranche B's absolute identities once
   on the new base. Its reviewed relative `-138/+18` ledger remains frozen.

No product or test implementation is authorized by this design document.
