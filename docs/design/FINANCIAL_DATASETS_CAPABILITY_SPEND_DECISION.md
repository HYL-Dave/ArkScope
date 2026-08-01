# Financial Datasets Capability And Spend Decision Input

> **Status:** STATIC DECISION INPUT - NOT A CAPABILITY REGISTRY OR SPEND AUTHORIZATION
>
> **Observed:** 2026-08-01
>
> **Owner:** a separately reviewed Financial Datasets product slice

## 1. Purpose And Boundary

This document preserves the useful facts from two retired research probes
without keeping an executable that can issue metered requests during ordinary
test collection.

It does not assert that an endpoint is currently available to a credential,
classify an endpoint as free or paid, authorize a network request, or implement
the future product policy. Provider capability, credential entitlement, and
user authorization to spend are three independent facts.

No Financial Datasets provider request was made while extracting this
inventory. The extraction parsed source literals and request dictionaries
without importing either probe.

## 2. Evidence Classes

### 2.1 Retired-source inventory

The two retired files contained 29 `GET` attempts over 24 unique literal
endpoint paths. They wrote response material under
`comparison_results/financial_datasets/`, but no response artifact is accepted
or retained in the repository as current provider evidence.

The request-shape inventory below records query-key names only. Dynamic dates,
ticker values, response bodies, credentials, and historical status codes are
not capability authority.

| Endpoint | Attempts | Query-key shape | Source note |
|---|---:|---|---|
| `/analyst-estimates` | 1 | `ticker, limit` | primary probe |
| `/company/facts` | 1 | `ticker` | primary probe |
| `/crypto/prices` | 2 | `ticker, interval, interval_multiplier, start_date, end_date` | primary + retry |
| `/crypto/prices/snapshot` | 2 | `ticker` | primary + retry |
| `/crypto/prices/tickers/` | 1 | none | primary probe |
| `/crypto/tickers` | 1 | none | retry-only conflict; not a current capability claim |
| `/earnings/press-releases` | 1 | `ticker` | primary probe |
| `/filings` | 1 | `ticker, form_type, limit` | primary probe |
| `/filings/items` | 3 | `ticker, filing_type, year, item` | two primary cases + retry |
| `/filings/items/available` | 1 | none | retry-only conflict; not a current capability claim |
| `/financial-metrics` | 1 | `ticker, period, limit` | primary probe |
| `/financial-metrics/snapshot` | 1 | `ticker` | primary probe |
| `/financials` | 1 | `ticker, period, limit` | primary probe |
| `/financials/balance-sheets` | 1 | `ticker, period, limit` | primary probe |
| `/financials/cash-flow-statements` | 1 | `ticker, period, limit` | primary probe |
| `/financials/income-statements` | 1 | `ticker, period, limit` | primary probe |
| `/financials/segmented-revenues` | 1 | `ticker, period, limit` | primary probe |
| `/insider-trades` | 1 | `ticker, limit` | primary probe |
| `/institutional-ownership` | 1 | `ticker, limit` | primary probe |
| `/macro/interest-rates/snapshot` | 1 | none | primary probe |
| `/news` | 1 | `ticker, limit` | primary probe |
| `/prices` | 2 | `ticker, interval, interval_multiplier, start_date, end_date` | primary + retry |
| `/prices/snapshot` | 1 | `ticker` | primary probe |
| `/prices/snapshot/tickers/` | 1 | none | primary probe |

The retry-only `/crypto/tickers` and `/filings/items/available` literals
conflicted with the primary probe's paths/comments. Their presence proves only
that the research script tried alternate names. It does not establish which
name is supported now.

The production
[`FinancialDatasetsClient`](../../data_sources/financial_datasets_client.py)
currently implements only:

- `/financials/income-statements`;
- `/financials/balance-sheets`; and
- `/financials/cash-flow-statements`.

That client is not evidence that the other 21 inventory paths are supported by
ArkScope.

### 2.2 Rejected Task 0 observation

An unfiltered 2026-08-01 baseline accidentally collected and executed the two
probe tests without a user-attributable API credential. It made 29
unauthenticated attempts and left 28 response artifacts because one retry
reused an earlier output path. The surviving statuses were:

```text
2 x 200
1 x 400
20 x 401
4 x 404
1 x 410
```

This run is rejected admission evidence. Those responses do not classify
price, entitlement, endpoint availability, account spend, or product support.
They are retained only in the
[Tranche A evidence](../superpowers/evidence/2026-08-01-scripts-retirement-tranche-a.md)
as an explanation of why default collection must not contain live probes.

### 2.3 Official observations rechecked on 2026-08-01

These observations are dated and must be revalidated before product
implementation:

- [Pricing](https://www.financialdatasets.ai/pricing) advertised Credits as a
  one-time `$20` purchase for `1,000` requests, with premium requests consuming
  `8x`.
- The same page advertised Build at `$200/month` for `100,000` requests, with
  premium requests consuming `4x`.
- [Terms of use](https://www.financialdatasets.ai/terms-of-use) described API
  requests and MCP calls as billable units, Credits usage as drawing a prepaid
  balance, subscription overage as drawing a prepaid balance, and zero balance
  as returning HTTP `402`.
- The published [MCP tool list](https://docs.financialdatasets.ai/mcp-server),
  [documentation index](https://docs.financialdatasets.ai/llms.txt), and
  [OpenAPI inventory](https://docs.financialdatasets.ai/api/openapi.json)
  exposed no documented account-balance or remaining-usage operation.

The checked OpenAPI document used version `3.0.1`, contained 54 paths, and had
SHA-256:

```text
2f17263f7a960fca93cd7662cf1be583c6ecb68b090313139ed1aca6db702b5a
```

Searching operation paths, IDs, and summaries for account billing, credit
balance, remaining usage, or equivalent concepts found only financial
balance-sheet terminology. Absence from this dated public inventory is not a
promise that the provider will never add such an operation.

## 3. Required Product Semantics

A later reviewed product slice owns implementation. It must preserve these
requirements:

1. The existing enable control means **allow metered network requests**. It
   does not hide Financial Datasets content already present in local cache.
2. Cached data remains readable while metered requests are disabled.
3. Every callable endpoint belongs to a reviewed class such as `no_credit`,
   `core_1x`, `premium`, or `unknown`. `unknown` fails closed for automatic
   calls.
4. ArkScope does not add a user-configured daily or per-request spending cap.
   The control is permission to call, not a second billing engine.
5. Before first metered enablement, the user explicitly declares `credits` or
   `subscription`. The declaration remains editable and every change is
   audit-recorded.
6. Credits UI warns that requests consume prepaid balance.
7. Subscription UI prompts a user who declares a subscription to enable the
   source, and warns that overage may consume prepaid balance.
8. HTTP `402` becomes a typed `credits_exhausted` outcome and stops blind
   automatic retries.
9. Local request-unit counters are labelled non-authoritative. ArkScope cannot
   observe other clients, purchases, resets, or all provider-side
   multipliers.
10. Until an official balance API or MCP tool exists, the UI links to the
    provider dashboard. It does not scrape the dashboard or call a private
    endpoint.

An API key proves neither entitlement nor permission to spend. A spend toggle
proves neither endpoint capability nor credential entitlement.

## 4. Separate Implementation Slice

The following work is deliberately not part of scripts retirement:

- an endpoint capability/cost registry;
- backend request enforcement;
- Settings controls and warnings;
- i18n resources;
- billing-type audit persistence;
- typed `402` runtime handling; and
- dashboard navigation and non-authoritative usage display.

That work requires its own design, tests, and user-facing review. Historical
probe success counts must not seed a registry without fresh official evidence.
