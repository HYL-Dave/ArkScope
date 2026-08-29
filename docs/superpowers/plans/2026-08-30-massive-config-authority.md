# Massive Configuration Authority Implementation Plan

## Goal

Move the active Massive credential namespace from `polygon.api_key` to
`massive.api_key` without rewriting historical Polygon source identities or
reviving `.env` authority.

## RED-First Tasks

1. Add scratch-store tests for all five legacy/current row states, preflight
   binding, exact timestamp preservation, and atomic conflict rejection.
2. Change the provider catalog and API projection to expose only `massive`;
   prove both Massive and legacy Polygon `.env` names remain unavailable as
   import/runtime-file sources through both provider-specific and generic
   environment loaders.
3. Retarget scheduler, lifecycle, runtime-config, connection-test, and provider
   health configuration lookups to `massive`, while retaining underlying
   `polygon` news/price source IDs.
4. Update Settings copy and fixtures so the current card and health row use
   `massive`.
5. Run focused backend/frontend tests, typecheck/build, then the full gates.

## Cutover

Do not touch the production profile database during implementation. Before App
restart, explicitly preflight the profile row migration. Apply it only after a
separate production-write authorization. If neither row exists, enter the new
Massive key in Settings after the new App is running.

## Offline Closeout

- Migration authority: eight scratch-only tests covering namespace admission,
  all row states, no startup mutation, exact preservation, conflict rollback,
  and stale-preflight rejection.
- Focused backend: 225 passed before the generic-loader addition; final related
  loader/config set: 194 passed.
- Full backend: 4,914 passed, 12 skipped.
- Frontend: 106 files, 1,306 passed; TypeScript and production build passed.
- Four reverse-mutation probes were killed by named owners: stale approval,
  conflict admission, provider-specific Massive fallback, and generic-loader
  exclusion (the last produced two named failures).
- Provider calls, production DB operations, App startup, merge, and push: zero.
