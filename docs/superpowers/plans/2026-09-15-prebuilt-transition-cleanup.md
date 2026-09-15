# Prebuilt Transition Cleanup

Authority: September 15 user approval of A+B before hand testing, then a
separate interpreter decision/activation. The retained-data and current-feature
constraints in `docs/design/RUNTIME_AND_RECENT_COLLECTION_POLICY.md` still apply;
its old ordering (admit a candidate before removing the unused builder) is
superseded. No production writes, activation, dependency upgrades or merge.

## A: Exact ID Sets

- Own five call sites/six statements in SA recovery, reconciliation and lifecycle
  retention. Replace per-ID binds, not whole-set semantics or global ordering.
- No application item-count ceiling; SQLite's actual payload/resource limits
  remain. Preserve int64 binding rejection after existing lineage normalization.
- `tests/test_sqlite_id_sets.py`: RED on the candidate's real 32,766 variable
  limit; cover 33,000 IDs, precision, overflow, empty/None, ordering, quoted and
  NUL-bearing text, retained citations and both deletes. Related suites must
  pass on candidate 3.53.1 and control 3.37.2.
- A shared text-set helper is justified by three owners. Old JSON decoding of
  NUL must not silently change IDs: only that case uses double-encoded JSON
  strings and a connection-local Python JSON decoder, including on readonly
  connections. No table writes or SQL interpolation of values.

## B: Retire The Unused Self-Build Runtime

- Delete the four `src/sqlite_runtime` modules, four matching test modules,
  `src` import hook and native script hook. No fallback, alias or new manager.
- Preserve native import purity; transfer actual SA launcher/desktop child,
  worker, dependency and OAuth closed-environment behavior to source-independent
  tests. Retire custom manifest/build/loader-only assertions, not generic safety.
- RED absence guard, then focused startup/native tests on both interpreters.
- Current development/hand-test interpreter remains unchanged. Actual admitted
  production entrypoint identity and no-fallback guard are C, not B claims.

## C15: Remove Obsolete Converters, Keep Current Installation

- Move live SQLite digest/encoding helpers out of the listing converter.
- Preserve current investigation installation and disposal behavior and tests.
- Move current-V4 tracking-membership installation into an explicit current
  owner. Preserve observation, disabled-automation, stopped-App, digest, backup,
  transaction and no-op guards; remove old V2/V3 conversion paths.
- Transfer relevant converter safety tests to current-schema fixtures. Add
  absence guards and helper contracts, see RED, then run focused tests.
- Sealed historical scripts stay byte-identical and replay against their pinned
  historical revision; document this instead of leaving forwarding modules.

## C20: Separate Code Retirement From Retained Data

- Remove fresh `agent_queries` DDL and unused insert/count wrappers. Keep generic
  archive reading of existing tables, reports, memories and current Research.
- RED fresh-schema absence plus existing-row preservation; keep no-create tests.
- Historical records are not an authorized DROP. Obtain a current, restricted
  read-only inventory before requesting archive/disposal approval. No question
  or answer contents in tool output or evidence. Retained-data disposition stays
  open until actually authorized and handled.

## Acceptance

Tasks share only documentation and final suite/receipt ownership. A, B and C20
are parent-owned; C15 may use a separate worktree. No concurrent pytest runs in
one source tree. Final full suites run serially with no other work on that tree.
Preserve raw RED/GREEN results and name every remaining limitation. Hand testing
precedes C activation; no claim that source-free compatibility testing is a
completed runtime deployment or that cross-platform work is complete.
