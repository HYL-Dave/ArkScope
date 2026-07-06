# SA Alpha Picks Content Capture

> **Status: SHIPPED** — capture pipeline live; kept as reference for C-3 ticker-detail SA sections.

Last updated: 2026-04-03

## Current behavior

SA article detail pages are scraped into **Markdown**, not raw HTML.

Current flow:

1. Extension detail scraper reads the article body DOM.
2. The body is converted into `body_markdown`.
3. `body_markdown` is stored in `sa_articles.body_markdown`.
4. When an article is matched as a pick's canonical article, the same Markdown body is also synced into `sa_alpha_picks.detail_report` for backward compatibility.

Relevant code:

- `extensions/sa_alpha_picks/scrape_detail.js`
- `src/tools/data_access.py`
- `src/tools/backends/db_backend.py`

## What is preserved today

### Headings, paragraphs, lists, blockquotes

These are converted into plain Markdown text.

### Tables

HTML `<table>` elements are converted into Markdown tables row by row.

Implications:

- Cell text is preserved.
- Basic table structure is preserved.
- Styling is lost.
- Complex layout fidelity is lost:
  - merged cells
  - nested formatting
  - column widths
  - other HTML-only presentation details

### Images

Images are **not explicitly captured** today.

Current scraper behavior:

- No dedicated `<img>` handling
- No binary download
- No image URL persistence
- No OCR

If an image is wrapped in a `figure` that also has visible caption text, the caption text may survive because the scraper keeps descendant text nodes. The image asset itself does not.

## What is not captured today

### Right-side Factor Grades

The Factor Grades panel normally shown on the right side of the article page should currently be treated as **not captured**.

Reason:

- The detail scraper targets the article body container, not the full page layout.
- `aside` and sidebar-like content are excluded.
- Factor Grades in the right rail are therefore outside the main content capture path.

If Factor Grades become important, they should be scraped as a **separate structured block**, not assumed to be part of article body extraction.

## Storage model

Canonical storage:

- `sa_articles.body_markdown`

Backward-compatible sync:

- `sa_alpha_picks.detail_report`

This means downstream tools currently consume a **text-first Markdown representation**, not a faithful HTML archive of the article page.

## Practical implications

Today the system is good for:

- reading article text
- searching article text
- syncing article content into pick detail reports
- preserving simple tables in a readable form

Today the system is weak for:

- image-heavy articles
- chart/image preservation
- layout-faithful archival
- sidebar widgets such as Factor Grades
- exact HTML round-trip rendering

## Upgrade options

### Option A: Store image URL + alt text

Scope:

- Detect `<img>`
- Persist image URL
- Persist alt text or nearby caption text
- Optionally emit Markdown like `![alt](url)` or store image metadata separately

Pros:

- Smallest change
- Cheap in storage
- Improves traceability for image-heavy articles
- Keeps the article body pipeline mostly unchanged

Cons:

- URL availability may not be durable
- Alpha Picks is paywalled, so image URLs may require authenticated cookies or may be short-lived
- A stored URL does not guarantee future readability
- Still does not preserve charts/tables embedded as images in a robust way

Assessment:

- Reasonable as a lightweight improvement
- Useful mainly as a reference trail, not as durable archival

### Option B: Store HTML + Markdown side by side

Scope:

- Keep current `body_markdown`
- Also store sanitized raw article-body HTML

Pros:

- Preserves richer structure
- Allows future re-parsing if Markdown extraction changes
- Better for complex tables, embedded figures, and layout-sensitive content

Cons:

- More storage
- More parsing/cleanup complexity
- HTML is more DOM-fragile across site redesigns
- Does not automatically solve right-rail Factor Grades, because those are outside the current body container selection

Assessment:

- More future-proof than URL-only image capture
- Better if the goal is archival fidelity or later re-extraction
- Probably unnecessary if the goal remains text-centric analysis only

## Recommendation

Short term:

1. Keep Markdown as the primary text representation.
2. Do not change table storage yet; current Markdown table conversion is probably sufficient for most analysis use cases.
3. If images matter, add **image URL + alt/caption capture** first as a low-cost improvement.
4. If archival fidelity becomes important, add **HTML + Markdown dual storage** later.

Important note:

If the real requirement is "capture Factor Grades reliably", neither of the two options above is the main fix. Factor Grades should instead be implemented as an explicit sidebar/structured scraper.

## Image URL verification

A direct CDN image URL was spot-checked on 2026-04-03:

- `https://static.seekingalpha.com/uploads/2026/3/13/56421291-17734237209306552_origin.png?io=w640`
- unauthenticated request returned `HTTP 200`
- `content-type: image/png`

This suggests that at least some Alpha Picks article images are served from a public/static CDN URL and can be fetched without an active logged-in page session.

## Open question

Even though the sampled URL was readable on 2026-04-03, long-term durability under Alpha Picks authentication still has **not been fully verified**.

Possible outcomes:

- some URLs may remain readable after login session changes
- some URLs may require active authenticated cookies
- some URLs may be signed, transformed, or temporary

So "store URL only" should currently be treated as a useful reference trail, not guaranteed durable archival.
