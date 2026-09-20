# Research Usage And Repair Priorities

Date: 2026-09-20. Inventory baseline: `ec574482` (56 registered tools).
This is evidence for prioritization, not an automatic retirement/subscription
decision. No archived fundamentals implementation is adopted.

## Corpus And Limits

The prior private read-only snapshot contains 23 threads, 108 messages (54 user),
33 runs and 32,887 events. A fresh `mode=ro`, `query_only` read of only the four
research tables verifies that the question, message/tool, run and event evidence
still matches the snapshot's canonical fingerprint. No credential tables,
application stores, provider calls or production writes are involved.

The latest historical run is **2026-09-09**. These records predate the OAuth
argument reconciliation, SEC wiring and recent source-isolation repairs. They
cannot measure today's success rate. The 33 run statuses are 32 succeeded and
one failed; that is execution status, not financial-answer correctness.

Private questions, holdings, answers and tool previews remain outside git.
[The evidence directory](../superpowers/evidence/2026-09-20-research-usage/README.md)
contains the reproducible method, aggregate JSON and topic annotations, not raw
conversations.

The earlier complete 56-tool source/effect/cost/rate-owner matrix and full
saved-research review remain recoverable at archive commit `5c123120` (tag
`archive/2026-09-20/research-source-workflow`), respectively:
`docs/data/2026-09-19-tool-capability-audit.md` and
`docs/data/2026-09-19-research-history-audit.md`. They are dated findings, not
current acceptance: the report-file boundary, SEC defaults and FD governance
have since changed. Preserving that evidence does not adopt the archived 57th
fundamentals tool or its unaccepted implementation.

## Questions Actually Asked

One manually reviewed primary intent per user message. Follow-ups use their
thread context. The groups are editorial judgments; counts are reproducible.
The deduplicated column removes only identical prompts within the same thread,
not separate questions across threads. Thread counts overlap across topics.

| Primary topic | Stored questions | Distinct thread/prompts | Threads |
| --- | ---: | ---: | ---: |
| Entry/exit, position and short-horizon research | 24 | 17 | 14 |
| Themes and candidate screening | 9 | 8 | 6 |
| Company news and investment thesis | 5 | 5 | 4 |
| Data availability, time/session and source checks | 5 | 5 | 4 |
| SA article/comment discussion focus | 4 | 4 | 4 |
| Fundamentals and peer comparisons | 3 | 3 | 3 |
| Sector cycles and holding horizon | 3 | 3 | 1 |
| Direct price-trend review | 1 | 1 | 1 |
| **Total** | **54** | **46** | **23 distinct overall** |

Eight repeated submissions matter: treating retries as eight additional product
requirements would overstate demand. SA and price needs also occur inside the
entry/exit category; the primary-topic table is not a complete source-need map.

## Tool Evidence

Historical events contain no stable call IDs. We retain **recorded start
attempts**, not a fabricated exact provider-dispatch count. A single outstanding
same-name start can be paired with its next substantive end in that run;
overlapping same-name calls remain ambiguous. Equal arguments do not prove a
duplicate, so complete repeated attempts are retained.

- 1,242 starts; 534 explicitly non-error completions, 493 explicit errors and
  215 unknown outcomes (including 28 ambiguous starts).
- 152 additional native OpenAI API `tool_end` headers contain only a name. They
  are neither new starts nor success evidence.
- 1,603 saved-message tool records are a **separate** observation surface. They
  overlap events; 761 lack a run link. Do not add them to starts or infer their
  auth channel from provider/model names.
- Outcome flags/short previews do not establish complete or correct data.
  No complete preview proved a typed unavailable/partial outcome; that is **not**
  proof none occurred. The actual data-success rate is unobservable here.

In the table, **S/E/?** means explicitly reported non-error/error/unknown for
starts. **Flag rate** is S/(S+E), excluding unknown, and is only a historical
transport completion measure. **C/L** are ChatGPT OAuth/Claude OAuth starts.
**API headers** are name-only OpenAI API observations, shown separately.

| Current tool | Starts | S / E / ? | Flag rate | C / L | API headers | Message records |
| --- | ---: | --- | ---: | --- | ---: | ---: |
| `get_price_change` | 263 | 105 / 105 / 53 | 50.00% | 210 / 53 | 4 | 284 |
| `get_ticker_news` | 133 | 54 / 54 / 25 | 50.00% | 108 / 25 | 14 | 175 |
| `get_current_quote` | 125 | 57 / 58 / 10 | 49.57% | 114 / 11 | 0 | 125 |
| `get_fundamentals_analysis` | 124 | 57 / 57 / 10 | 50.00% | 114 / 10 | 2 | 154 |
| `get_ticker_prices` | 120 | 48 / 48 / 24 | 50.00% | 96 / 24 | 12 | 150 |
| `get_sa_digest` | 103 | 45 / 45 / 13 | 50.00% | 90 / 13 | 8 | 141 |
| `get_sa_feed` | 62 | 28 / 0 / 34 | 100.00% | 28 / 34 | 12 | 85 |
| `get_sa_alpha_picks` | 51 | 46 / 0 / 5 | 100.00% | 46 / 5 | 0 | 51 |
| `get_news_brief` | 34 | 22 / 0 / 12 | 100.00% | 22 / 12 | 4 | 46 |
| `get_ticker_data_coverage` | 25 | 10 / 10 / 5 | 50.00% | 20 / 5 | 0 | 25 |
| `get_economic_calendar` | 20 | 12 / 0 / 8 | 100.00% | 12 / 8 | 1 | 25 |
| `search_news_advanced` | 19 | 10 / 0 / 9 | 100.00% | 10 / 9 | 4 | 37 |
| `list_security_lifecycle_reviews` | 2 | 0 / 0 / 2 | unknown | 0 / 2 | 0 | 2 |
| `get_analyst_consensus` | 0 | unknown | unknown | 0 / 0 | 20 | 25 |
| `get_detailed_financials` | 0 | unknown | unknown | 0 / 0 | 8 | 13 |
| `get_sa_comment_focus` | 0 | unknown | unknown | 0 / 0 | 5 | 9 |
| `detect_event_chains` | 0 | unknown | unknown | 0 / 0 | 2 | 2 |
| `get_earnings_impact` | 0 | unknown | unknown | 0 / 0 | 0 | 2 |
| `get_insider_trades` | 0 | unknown | unknown | 0 / 0 | 0 | 2 |
| `get_option_chain` | 0 | unknown | unknown | 0 / 0 | 2 | 2 |
| `get_peer_comparison` | 0 | unknown | unknown | 0 / 0 | 0 | 2 |
| `check_data_freshness` | 0 | unknown | unknown | 0 / 0 | 1 | 1 |
| `get_morning_brief` | 0 | unknown | unknown | 0 / 0 | 1 | 1 |
| `get_sa_article_detail` | 0 | unknown | unknown | 0 / 0 | 1 | 1 |
| `get_sector_performance` | 0 | unknown | unknown | 0 / 0 | 1 | 1 |
| `get_watchlist_overview` | 0 | unknown | unknown | 0 / 0 | 1 | 1 |
| `save_memory` | 0 | unknown | unknown | 0 / 0 | 1 | 1 |
| `scan_alerts` | 0 | unknown | unknown | 0 / 0 | 1 | 1 |

These are **28 observed current names**, not 28 fully verified capabilities.
The remaining 28 current tools are listed as unobserved in `summary.json`.
There is no retained Anthropic API-key run among these 33 runs; older unlinked
Anthropic messages cannot establish that channel either.

Historical non-current names are not folded into their replacements:
`get_sec_filings` has 159 starts (40/114/5; C154/L5), while
`execute_python_analysis` has two starts (0/2/0; L2) and 14 API headers.
`get_iv_analysis`, `get_signal_factors`, `get_news_sentiment_summary`,
`synthesize_signal`, `detect_anomalies` and `delegate_to_subagent` have only
message/header observations. These eight names are detailed in `summary.json`.

The prior complete audit traced 490 of the 493 errors to historical empty
required arguments in ChatGPT OAuth. That transport defect has its own repaired
owner (`13248718`). The remaining three were two unavailable Python-executor
attempts and one quote timeout. This is not evidence that half of current price
or fundamentals calls fail, nor that buying data subscriptions fixes the errors.

## Next Repair Order

1. **Quote truthfulness and price basis.** High observed use plus direct user
   corrections about real-time prices. Preserve the useful tool; distinguish
   previous close, live/delayed/frozen/unknown, request time and observation time.
   Add deterministic boundary tests and a separately authorized live Gateway
   check. The [bounded follow-up](../superpowers/plans/2026-09-20-quote-freshness-repair.md)
   records the source-to-tool repair and acceptance boundary. The implementation
   now separates receipt from trade time and retains unknown freshness; the
   frozen full regression and a separately approved live check remain distinct.
2. **SA article/comment access and holdings context across auth channels.** The
   archived 17-tool OAuth allowlists omit direct article/comment/holdings tools.
   The saved questions need those capabilities even when a particular tool has
   zero starts. Audit dynamic exposure, paging and honest body/comment coverage;
   do not create an external MCP server as a shortcut.
3. **Financial comparability and earnings event semantics.** Retain capabilities;
   repair numerator/period/session/window labels or suppress unjustified derived
   values. The archived fundamentals alternative is not accepted replacement
   evidence. Earnings scheduling follows correct event alignment, not vice versa.
   The native API-key wrappers' omitted `period` option was repaired with FD
   freshness forwarding, and offline four-channel tests now preserve quarterly
   results and their original acquisition time. This is not acceptance of the
   legacy financial formulas or of a provider subscription's coverage.
   Paid-fallback descriptions and the metered HTTP guard are covered across
   all four channels in this slice.
4. **Operational decisions still separate.** Provider alternatives and plan
   upgrades require coverage/cost evidence. Unattended lifetime/failure delivery,
   retained-source policy, external authorization, native-session continuity,
   SQLite replacement and platform/sandbox work remain explicit workstreams.

No research history, articles, notes, translations, backups or provider source
is retired by this table. No subscription is purchased or enabled.
