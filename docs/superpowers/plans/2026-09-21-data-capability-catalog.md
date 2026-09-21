# Data Capability Catalog

## Scope

Deliver the category-first inventory in Settings without adding a second owner
for acquisition policy. The catalog distinguishes implemented adapters from
selected candidates, and describes execution/access requirements, not live
entitlements, enabled schedules or source health. Financial entries derive their
eligible and unimplemented providers from the existing routing catalog.

Settings can browse categories and navigate to the existing financial, schedule,
connection, storage or SA-extension status controls. Browser collection remains
owned by the extension. A candidate has no acquisition control. Inspecting the
catalog must not create a DAL/store, probe a provider, launch a browser/native
host, start a job or write configuration.

No new provider adapter, subscription recommendation, acquisition permission,
freshness policy, SA financial capture or external MCP is delivered here. The
catalog is a bounded current-integration map, not an exhaustive vendor survey.

## Progress

- [x] RED-first catalog contract and side-effect tests (13 expected failures).
- [x] Metadata endpoint and Settings category navigation.
- [x] Focused backend, full frontend/build and isolated browser acceptance.
- [ ] Root contract, verification record and commit/merge cleanup; no push.

## Acceptance

- Existing financial routing remains the sole selection authority.
- All ten existing source-scheduler IDs are accounted for; SA is represented
  separately and never invented as an eleventh API-sidecar job.
- SA articles, comments, recommendations and market news remain distinct from
  unavailable structured financial/rating capture.
- Integration never claims account entitlement, complete capture or live data.
- Candidate sources have no working-looking enable/refresh control.
- Category navigation, reload/error handling and Settings directory anchors work
  in both locales and at narrow/mobile widths, without changing settings.
- New routes appear by full identity in both exact route-inventory assertions.

Durable owner: [Data Acquisition And Updates](../../../DATA_ACQUISITION_AND_UPDATES.md).
