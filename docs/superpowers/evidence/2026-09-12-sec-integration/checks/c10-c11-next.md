# Bounded Remaining Cleanup Decisions

These are continuation plans, not completed work or production data approval.

## Superseded C10 Premise

The initial bounded direction below was rejected after the controller's full
consumer scan: no live raw-file import/repair reader exists. The corrected
`2026-09-13-file-news-boundary-cleanup.md` plan deletes the whole orphan module.
Implementation `885c2a2d` preserves actual data and current SQLite/SA readers;
350P/1S worker and 467P/1S controller receipts exist. Independent review and the
full backend are in progress. The following original proposal is historical,
not an instruction to restore FileBackend or its unshipped tests.

Remove FileBackend.query_prices/query_fundamentals (unconditional empty stubs),
unused LocalMarketBackend._files construction/import and its now-unused base_path
constructor argument plus the DAL caller argument. Keep DataAccessLayer.base_path
itself for other capabilities. Keep actual SQLite prices, raw-news FileBackend
reader/import path, SqliteBackend.query_fundamentals, financial_cache and all
stored-SEC calculations unchanged. Do not expand this into shared fundamentals
contract removal.

RED: absent-stub assertions, current market construction does not load FileBackend,
and retained raw-news reads actually return fixture content. Transfer nominal
FileBackend DataBackend conformance test to explicit raw-news-only contract and
remove its expected import from the current backend module-graph owner. Update
the EIR006 documentation assertion that explicitly demanded retired empty
compatibility. GREEN data_access, sqlite_backend, EIR006, stored_SEC_projection,
fundamentals_SEC_cache and tool/API controls. No actual files/data removed.

## C11 Direction Verified In Source

The old use_local_news/profile/env toggle no longer selects any writer or reader.
Correction from the final source read: malformed old values still block routing,
in addition to misleading status and suppressed provider_sync telemetry. Removing
that obsolete validation must be explicit; current normalized-setting and source
requirement validation remains. Both normalized and direct-local writers use the
same telemetry authority. The switch is not an operational rollback.

Ruling: remove the abandoned boolean API/settings/helper and its status fields,
not current normalized writer selection. Status/health must report actual local
provider_sync observations independent of an obsolete setting. Keep normalized
configuration validation and source-required normalized-write blocking. Remove
the unused frontend setUseLocalNews client and dead newsRoutingLabel helper with
its obsolete display-only fields; current newsWriteRouteLabel remains. No new
settings toggle or parallel authority. Existing persisted obsolete keys are not
silently deleted; their bounded data-disposition task remains explicit.

Named RED: real resolve_news_write_route plus current telemetry must agree even
when a disposable profile contains use_local_news=false; old API/function is
absent; read-only missing stores remain uncreated; malformed normalized settings
still block. Transfer old rollback-only tests to current writer/status owners,
preserve fetch/parse/hash/cursor tests. Do not alter C12 CLI history/range behavior
inside this patch. That larger command-convergence task remains separate.

Only one product implementation worker runs at a time. C09 is accepted; C10
implementation is committed and frozen. C11 is not implemented and requires its
own exact file/test contract before GO. No global DB/settings mutation, live
providers, master merge, push or app restart.

The exact successor plan is now
`docs/superpowers/plans/2026-09-13-news-routing-cleanup.md`. It is preparation
only and may not mutate the frozen integration source during full verification.
