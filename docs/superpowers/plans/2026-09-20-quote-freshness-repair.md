# Quote Freshness Repair

Status: implemented with offline RED-to-GREEN checks; frozen full regression
pending. No live Gateway acceptance is claimed. Keep the quote capability.
This slice also implements the separately requested
[FD freshness contract](2026-09-20-financial-datasets-freshness.md).

## Baseline Evidence

- `src/tools/current_quote.py::_quote_from_ibkr_payload` chooses last, midpoint
  or close, then assigns `mode="ibkr_snapshot"`, `stale=False` and the current
  application time to all three. A previous close can therefore look current.
- `data_sources/ibkr_source.py::get_current_quote` returns prices/volume but no
  market-data type, quote timestamp or request-bound entitlement outcome. A
  tool-layer label alone cannot recover evidence already discarded here.
- `src/tools/schemas.py::CurrentQuoteResult` defaults `stale` to false, including
  unavailable construction paths. Consumers must not interpret missing evidence
  as a positive freshness assertion.
- `tests/test_current_quote_tools.py` covers a last-trade fixture, local bars,
  unavailable Gateway and strict source selection. It does not cover close-only,
  delayed/frozen/unknown mode, missing/old timestamps or entitlement refusal.
- `src/valuation_price.py` deliberately selects a completed-session local bar.
  It is a different price basis, not an implementation of a current quote.

## Bounded Implementation Contract

1. Preserve request-bound source evidence before normalization: contract,
   requested/received times, supplied price times, market-data type and typed
   failure. Verify the installed SDK's timestamp semantics; a receive timestamp
   must not be substituted for a trade timestamp without identifying that basis.
2. Separate selected price basis (last trade, bid/ask midpoint, previous close,
   stored bar) from transport and live/delayed/frozen/unknown evidence. Do not
   infer entitlement or freshness from a successful request alone.
3. Previous close and local bars remain useful, explicitly historical values.
   Missing timestamps/mode stay unknown, not `stale=False` plus current time.
   Validate positive finite prices, invalid booleans, crossed quotes and absent
   sides. Do not silently choose a different provider or paid entitlement.
4. Preserve strict `source="ibkr"` versus explicitly labeled `auto` fallback.
   Request-specific errors must not be inferred from unrelated Gateway activity.
   Preserve Gateway lock/client-ID ownership and disconnect/cancel cleanup.
5. Trace the two in-source quote consumers in `ibkr_source.py` plus Research wrappers
   before changing the payload. Keep the registry and all four transports honest
   about result semantics. No scheduler, alerts or external MCP is added here.

## Acceptance

- RED fixtures: close-only, unknown mode, missing timestamp, delayed/frozen,
  stale last trade, valid midpoint, crossed/one-sided quotes and invalid numbers.
- Source-to-tool tests verify metadata is actually forwarded, not invented by
  the adapter; all four transports preserve the same result/gaps.
- Timeout, entitlement denial, cancellation/disconnect and strict/no-fallback
  behavior retain their explicit owners. Deterministic tests precede live use.
- A separately approved live Gateway check covers open/closed market and the
  actual account entitlement. Capture request and quote evidence without claiming
  a single manual observation establishes all subscriptions or sessions.
- Keep this distinct from earnings announcement/session-window repair in
  `2026-09-20-earnings-observation-followup.md`.

## Implemented Contract

- `get_current_quote` and all four adapters expose `max_age_seconds` (default
  60, nonnegative integer). It classifies an evidenced live trade's age, not a
  provider's capacity or a license to call historical data current.
- `price_basis` separates last trade, bid/ask midpoint, previous close and local
  bar. `timestamp` is the selected price's known time; receipt and evaluation
  are separate. Missing/naive/future trade times or unobserved mode stay unknown
  (`stale=null`). Frozen/delayed, previous close and local bars stay historical.
  Midpoint has no invented exchange timestamp. Crossed/one-sided quotes and
  nonpositive/nonfinite/bool prices cannot form a valid midpoint/last.
- Installed ib_insync initializes `Ticker.marketDataType=1`, sets `Ticker.time`
  on local receipt, and does not retain default last-timestamp ticks 45/88.
  The source therefore observes request-ID-bound callbacks, forwarding the
  normal SDK handlers and restoring instance methods in `finally`. A new last
  price invalidates an older timestamp; live/delayed tick pairs must agree.
- The existing two-second snapshot window is preserved and explicitly partial
  unless snapshot-end arrives. No generic tick request, delayed-mode switch or
  fee-bearing regulatory snapshot is added. Contract qualification is bounded
  by the source timeout, restored after use. Requests and observers are cleaned
  up on success, timeout, exception and propagated cancellation.
- Subscription failures come only from this request's error codes, never an
  unrelated Gateway error. Strict IBKR does not choose another source. `auto`
  can still return a historical local bar with `fallback_reason` preserved.
- The direct option-strike consumers keep their existing last/close inputs.
  This slice does not certify those option analytics' price-age semantics or
  replace the separate completed-session valuation-price contract. Native
  Anthropic non-SEC dispatch is still synchronous; source cancellation cleanup
  tests are not proof of end-to-end cancellation of that dispatcher.

Vendor references: [market-data modes](https://interactivebrokers.github.io/tws-api/market_data_type.html),
[snapshot behavior](https://interactivebrokers.github.io/tws-api/md_request.html),
[tick types](https://interactivebrokers.github.io/tws-api/tick_types.html),
[error-code semantics](https://interactivebrokers.github.io/tws-api/message_codes.html).
These pages describe the installed SDK's protocol; current documentation is
linked from [IBKR's API documentation](https://www.interactivebrokers.com/docs/tws-api/doc/introduction).
