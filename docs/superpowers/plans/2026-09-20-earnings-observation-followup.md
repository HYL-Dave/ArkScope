# Earnings Event Observation

Status: scoped follow-up, not implemented or enabled by this retirement.
Owner: market-data / research tools. Required before any earnings monitor is
advertised as an unattended opportunity alert.

## User Decision

Keep the capability to study price reactions after earnings. It answers a
market-behavior question, not the financial-statement question answered by the
unaccepted fundamentals branch. Scheduled observation and timely delivery are
useful additions. Do not retire `get_earnings_impact` on the false premise that
SEC fundamentals replace it, or schedule the current approximation unchanged.

## Required Contract

1. Bind an observation to a real announcement timestamp, its provider and time
   zone. Distinguish fiscal period end, scheduled announcement and confirmed
   release. If the source cannot establish release timing, report that gap;
   do not match a fiscal date to the nearest available price bar.
2. Identify pre-market, regular-session and after-hours releases. Select price
   windows against an exchange calendar and session boundaries. A five-session
   result requires five complete intervals; partial coverage must not be named
   `5d`. Preserve raw timestamps, price source, adjustment policy and coverage.
3. Separate an immediate observed reaction from subsequent session and
   multi-session observations. Delayed or frozen prices cannot be labeled live.
   This is descriptive evidence, not a guaranteed trading signal or causal proof.
   A small historical average is not an options-implied move or a calibrated
   forecast; a few beat/up observations must not become a predictive-confidence
   claim. Expose the sample and coverage instead.
4. Disclose provider entitlement, per-request cost, available history and
   freshness before selecting cadence. No new subscription purchase or paid
   probe is authorized by this plan; use the provider-capability inventory.
5. Schedule each event/window idempotently under one service owner. Enforce
   request budgets, rate limits, cancellation and bounded retries in that
   service, not in the model caller. Preserve the original observations so later
   data corrections do not silently rewrite what was first seen.
6. Deliver success, partial coverage and failures through an explicit local
   status/notification contract, with duplicate suppression. A job staying alive
   after closing the window is necessary but not sufficient acceptance.
7. Expose the retained observations to in-App research first. A future external
   agent may read/analyze them through separately authorized tools; logging does
   not grant write, fetch, subscription-spend or schedule authority.

## Acceptance

- Release-date versus fiscal-period fixtures, before/after market close, weekends,
  early closes, timestamp changes, missing sessions and insufficient windows.
- Exact source/timestamp/precision provenance and typed entitlement/freshness gaps.
- Descriptive versus predictive labels, sample size and partial-history refusal;
  do not inherit the old `surprise_predictive` label from a small sample.
- Restart, overlapping runs, missed schedules, cancellation, rate-limit and
  delivery tests. No duplicate paid fetch or automatic model/provider fallback.
- Separately approved live checks for the selected calendar and market sources.

The existing `get_current_quote` freshness defect and the current
`get_earnings_impact` alignment/window defects remain open. This document does
not certify either implementation or start any collection.
