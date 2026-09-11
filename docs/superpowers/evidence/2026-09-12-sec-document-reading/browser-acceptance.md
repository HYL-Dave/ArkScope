# Parent Browser Acceptance

Use actual FastAPI/TestClient + Store/CaptureStore/DocumentService/DocumentQueries.
Only generated source transport and UI host are fixtures; no canned document
envelopes. Keep previous catalog/facts/config workflows as regression controls.

- Both locales (en/zh-Hant), 1280x960 and 390x844. No external network, tokens,
  existing profile or actual App process. Assert no page errors/duplicate keys.
- Opening a catalog row issues stored GET only; absent capture visibly exposes
  explicit acquisition. Count source requests before and after opening.
- Explicit acquisition uses the directory plus selected original document once.
  Show primary source, capture identity, observation and selectable sections.
- Whole-text pagination preserves original capture, max_chars/filter/cursor.
  Previous page must reproduce the cached page without fetching another source.
- Literal search returns source citations and exact canonical byte-range text.
  Returned excerpts must match text objects in the disposable real capture store.
- Keep the selected capture after a fixture source revision. Reading it remains
  identical. Deliberately choose latest only through the offered command.
- Simulate a failed newer acquisition. Latest reports failure; older pinned read
  remains available, never implicitly portrayed as the successful latest attempt.
- Simulate a lost POST response after actual completion. Show outcome unknown;
  stored reread recovers it with GET and zero automatic repeated POSTs.
- Select observed but uncaptured secondary document; it reports absence without
  borrowing primary text. Return to the observed primary alias with the same pin.
  Unknown section reports gap with whole-text access.
- Rapid switch/close must not display an earlier row's delayed response.
- Screenshot initial, index, passage and failure/pinned states. Inspect rendered
  images, check document widths, toolbar/button/SVG containment, long identifiers,
  text wrapping and scroll regions. Original acquired HTML is never rendered.

The parent adapts browser_check.py only after reviewed Task3 result shapes and
Task4 DOM exist. Frontend worker owns no parent fixture/helper files.

## Completed Frozen-Source Run

`browser-final-fixed` on02a0fff4 passed all four combinations in44.538seconds.
Each observes84actualHTTP calls,13generatedmetadata and10generateddocument
dispatches,19 independently checked citations and zero page errors. Generated
source requests are not calls to the real SEC. The actual retained request and
response records live beside screenshots under that run's browser/ directory.
Additional review compositions keep the selected section on index Back, preserve
the primary pin against changed/failed latest captures and uncaptured-secondary
navigation, and react to a definite failed POST after closing/reopening while it
was pending. Truly lost outcomes remain conservative GET-only, with no retry.
Current catalog/facts/config/conflict pagination remain positive controls.
