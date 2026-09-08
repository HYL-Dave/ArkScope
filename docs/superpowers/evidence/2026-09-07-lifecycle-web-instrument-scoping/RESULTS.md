# Instrument Scoping And Larger Claude Investigation

## Outcome

The bounded code change passes offline admission. A fresh TA / Sonnet 5 Claude
OAuth run completes search, public-page reads, analysis, durable reopening and
the actual frontend parser. **It does not produce an action-ready finding.**
This packet does not declare lifecycle hand-test or release readiness.

The input already specified common stock / NASDAQ. A reproduced validator bug
pooled a stock identity with a same-issuer debt event/date. The repair binds
decisive events and dates to the target class and a source/identity anchor. It
also prevents an unrelated debt OTC quote from vetoing a supported stock result.
Class binding is inspectability, not a proof of every legal or event meaning.

Portfolio-derived universe sources admit stock/ETF and option underlying
symbols, not bonds. Manual lists are ticker-based. This code inventory is NOT a
production holdings census and does not claim a shipped debt/option lifecycle
manager. A debt listing must never determine its issuer's common-stock status.

## Bounds And Offline Verification

Claude OAuth defaults change from 4 searches / 4 sources / 8 source requests /
180 seconds per model phase to 12 / 8 / 24 / 600. The source request count includes
redirects. There are still exactly two host submissions. The shared source
deadline remains 180 seconds; per-page limits remain 32 MiB encoded and 128 MiB
decoded. These are ceilings, not quotas to fill. Other auth execution budgets
are unchanged; shared prompts/schema descriptions/finding validation apply to
all four transports and pass offline checks.

Only four product files and two new product test files change relative to the
previous JSON-analysis admission. No persisted field names or schema changes.

- Initial RED: 17 failed / 13 passed; first related GREEN: 177 passed.
- Whole affected focus: 2,266 passed; integration: 3,085 passed.
- Complete backend: **6,931 passed / 12 skipped**, 30 added nodes, none removed.
- All 25 named reverse mutants fail their named owners across the whole focus.
- Current preflight/readback and evidence-harness checks also run offline.
  No new browser screenshot campaign is claimed; frontend source is unchanged.
- Admitted source seal:
  `05a81e10133bbd66fe14b42fed636d4b2cd6f629cef4c379dda43000ce7d7781`.

## Measured Live Ledger

| Work | SDK submissions | Direct source HTTP | Result |
| --- | ---: | ---: | --- |
| Fresh TA investigation | 2 | 5 | Four captured pages, one 403 gap; completed/reopened, non-actionable |
| Public preview to original link | 0 | 2 | Explicit link leads to SEC filing INDEX, not the full report |
| Typed index row to primary 8-K | 0 | 2 | Public primary document captured |
| Original-document analysis R1 | 1 | 0 | Completed remote reply rejected as `model_output_invalid`; raw final text was not recorded |
| Same-input instrumented analysis R2 | 1 | 0 | Valid JSON; citation/scope/date/contradiction-label blockers remain |
| **This authorization total** | **4** | **9** | **15 of 24 direct source attempts remain unused** |

All four SDK calls observe exact `claude-sonnet-5`, literal `apiKeySource=none`,
matching sessions, and reaped children. The full run observes two WebSearch tool
uses, with main/helper models pinned to Sonnet. There is no alternate credential,
API-key billing or model fallback. SDK calls and observed tool uses are not an
exact count of hidden provider-internal HTTP. Separate diagnostic rereads of
the preview/index are counted; they are not concealed as transport retries.

## What The Failure Established

The search used only two of twelve calls. Its CapEdge 8-K page explicitly says
it is a text-only preview and ends in Item 1.02. The decisive Item 3.01 was not in
that response. HTTP byte accounting and local source selection did not remove
it. The host followed a public original link, then the index's typed 8-K row;
there was no login or access-gate bypass. The primary report is only 9,529 bytes
encoded / 64,749 decoded / 15,873 text characters, far below configured bounds.
It explicitly describes Company Stock ceasing Nasdaq trading before market open
on May 15, 2023, separately from the issuer's senior notes.

After the host supplied that original, the model could state the stock result,
but still put a note saying debt does NOT contradict the stock evidence into
`contradictions`, omitted the definition/identity span from a `Company Stock`
event quote, and produced citation/date-support problems. The first same-input
analysis also failed JSON validation. Its exact generation failure cannot be
reconstructed because that first observer kept only the failure code; the next
observer retained the private native output without altering it. A later valid
reply is not proof that the earlier failure was repaired.

An explicitly hand-constructed exact-span positive control passes both the full
capture and actual selected context with zero blockers. Its two quotations are
1,000 and 2,380 characters. It is NOT a model result, an adoption, or evidence
that the current agent can independently finish this work. Long exact-quote
reproduction and a fixed one-pass workflow remain product weaknesses.

The original live receipt reader omitted `sqlite3.Row` and incorrectly raised
`web_journal_integrity`. A separately retained wrapper sets the required row
factory; a named test reproduces the failed connection and proves corrected,
read-only reopening without changing journal bytes. The originally admitted
recorder is not rewritten. This was a harness defect, not journal corruption.

## Remaining Decision And Boundaries

The proposed next step is at most three rounds / six host model calls, with
global budgets, explicit no-progress termination, source-original follow-up and
grounding correction. The existing journal CHECK, store and usage contracts
only allow `search-1` / `analysis-1`; changing an SDK limit alone cannot fix this.
Schema authorization was requested, not assumed. See
`../../plans/2026-09-07-lifecycle-web-bounded-followup.md`.

No production write, Web journal installation, assessment/adoption, App restart,
commit, merge or push occurred. No additional auth channel was called live.
The earlier failed/captured-source campaigns retain their original seals and
are not recounted as successes or charged to this renewed source allowance.

## Receipts

- Fresh run: `live-r1/`, seal
  `bcdb7581d9447177ad386e7c85d2b4eea73b6c1d59a472d590ff86504d7a5ab1`.
- First original-analysis failure: `failed-original-analysis-r1/`, seal
  `ff1ed46b26e044e60cf8d199d7e2014669a58a429b551c9a20c03af7c877ab4d`.
- Public-original follow-up and final analysis: `public-original-followup/`, seal
  `a76271c27e134771184b0d739c1dbafaaf09f841b8a8ee86122eaf9f9984f2e4`.
- Raw source pages/native outputs remain in their private `/tmp/lifecycle-instrument-*`
  captures; public artifacts retain hashes/lengths instead of quotations.
