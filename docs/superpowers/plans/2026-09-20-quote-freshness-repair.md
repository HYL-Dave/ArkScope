# Quote Freshness Repair

Status: inspected follow-up, not implemented or live-tested by the source-read
governance slice. Keep the quote capability. No SEC retirement or subscription
purchase decision is needed to stop overstating freshness.

## Confirmed Local Evidence

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
