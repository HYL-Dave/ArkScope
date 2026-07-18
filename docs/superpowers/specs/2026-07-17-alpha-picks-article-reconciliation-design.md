# Alpha Picks Article Reconciliation Mini-Design

> **Status:** DRAFT FOR WRITTEN REVIEW, revised 2026-07-18 with live BTSG
> capture evidence. The universe/JSON decision does not pre-approve this
> design, and no implementation plan is open.

## 1. Purpose

Automatically associate an Alpha Picks entry or exit event with the correct
Alpha Picks article using event date plus content evidence, then fetch missing
body/comments through the existing extension path. Ambiguous cases remain
visible for review instead of requiring the user to discover and paste a
`TICKER URL` line by default.

This design concerns the Alpha Picks portfolio in `sa_capture.db`. General
ArkScope holdings and the broader Seeking Alpha market-news feed are not
membership or matching inputs here.

## 2. Ground Truth and Current Failure Modes

### 2.1 Capture already happens automatically

A quick/full Alpha Picks refresh already:

1. scrapes current and removed picks;
2. stores both snapshots in `sa_alpha_picks`;
3. scrapes the Alpha Picks article listing;
4. stores article metadata in `sa_articles`;
5. fetches bodies/comments selected by the existing cache policy; and
6. runs an unresolved-symbol audit.

The popup shows `Paste missing article URLs (TICKER URL per line)` only when
unresolved current picks remain. Successful manual fetches store the article
and clear the symbol from extension-local unresolved state.

### 2.2 Automatic capture drops explicit provider ticker evidence

User-supplied live screenshots on 2026-07-18 prove that the Alpha Picks
surfaces expose ticker identity independently of the article title:

- the analysis-list card shows
  `Jul 15, 2026, 12:00 PM \u2022 BTSG \u2022 265 Comments`; and
- the article detail header shows
  `BrightSpring Health Services, Inc. (BTSG) Stock` below a generic title.

This is explicit provider metadata, not a title/body inference. The current
extension nevertheless loses both facts:

- `scrape_articles_list.js` captures only the calendar-date prefix, then applies
  an anchored ticker regex to the remaining text as though the ticker followed
  the date immediately. For the confirmed BTSG shape, the remainder begins
  with `, 12:00 PM` and separators, so the reviewed current expression returns
  `null` before reaching `BTSG`.
- `scrape_detail.js` returns title, author, publication date, body, URL, and
  scrape time, but does not extract the security-header ticker.
- the manual URL path supplies the user's symbol directly when saving article
  metadata. This explains why manually pasting the BTSG URL repaired the link;
  it does not prove that automatic association was correct.

The failure is therefore an extension parser defect, not evidence that Seeking
Alpha omitted ticker identity. BTSG is the sole live symbol claim established
by this evidence; other symbols require their own fixture or live proof and are
not assumed by analogy.

The implementation must prefer a ticker-bearing element or metadata node from
the same article card. A reviewed normalized-text grammar may be a fallback,
but it must admit the confirmed optional time and separators and must not scan
arbitrary uppercase page text. Detail extraction independently reads the
security header adjacent to the article heading. Sanitized DOM fixtures from
the real BTSG list and detail surfaces are required before selectors are
implemented; screenshots establish visible truth but do not establish DOM
structure.

### 2.3 Existing association is not event-safe

The current backend has one `canonical_article_id` per pick and copies its body
into `detail_report`. Automatic association:

- accepts only heuristic `analysis`/`removal` article types;
- compares every candidate with `picked_date`, including removal articles;
- uses nearest date only when replacing an existing canonical link;
- has no maximum date distance;
- may apply one article to every same-symbol pick; and
- falls back to ticker prefix or `%symbol%` title/body matching.

The extension's article-type classifier is title-keyword based. If no ticker is
extracted, an entry article may be labelled `commentary`; if a ticker is
present, a generic article may be labelled `analysis`. Classification is
therefore evidence, not identity.

A read-only 2026-07-17 snapshot found `50` current picks with `39` missing
canonical links and `61` closed picks with `58` missing links. Of fourteen
existing links, ten entry dates matched exactly; the remaining examples
included removal articles correctly dated to `closed_date` but hundreds of days
from `picked_date`, plus clearly suspicious current links hundreds of days away.
These numbers are diagnostic snapshots, not acceptance constants.

### 2.4 One canonical field cannot represent the domain

One pick can have distinct articles for:

- the original entry;
- the exit/removal; and
- later updates or reviews.

Overwriting one `canonical_article_id` loses this distinction. Matching must
therefore be modelled as a relationship, not as another nearest-article update
to the existing column.

## 3. Locked Relationship Model

### 3.1 Event roles

The V1 matching targets are:

| Role | Pick anchor | Cardinality |
|---|---|---|
| `entry` | `picked_date` | at most one accepted article per pick |
| `exit` | `closed_date` | at most one accepted article per closed pick |
| `update` | no automatic anchor in V1 | zero or more explicit future links |

An exit candidate is never compared to `picked_date`. A current pick has no
exit target. Missing/unparseable anchor dates make the event unmatchable rather
than authorizing a ticker-only guess.

### 3.2 Persistent accepted links, derived candidates

A dedicated relationship table is the eventual authority:

```text
sa_pick_article_links
  link_id
  pick_id
  article_id
  role                 entry | exit | update
  link_source          auto | user
  evidence_codes       deterministic JSON array
  supersedes_link_id   nullable
  linked_at
  revoked_at           nullable
```

Foreign keys reference `sa_alpha_picks.id` and `sa_articles.article_id`.
`entry` and `exit` each permit at most one non-revoked accepted link per pick;
`update` may repeat. A replacement revokes the prior row and inserts a new row
with `supersedes_link_id` in one transaction. The prior row is retained. A
separate candidate-decision log records explicit rejections keyed by
`(pick_id, role, article_id)` so a rejected candidate is not silently proposed
again. Link history and rejection history are never encoded by mutating article
metadata.

Candidate sets and scores are derived from current local evidence at read time.
They do not become accepted links merely because they sort first. The future
schema plan owns exact keys and indexes, including a partial uniqueness rule for
active `entry`/`exit` links, but may not weaken the retained replacement and
rejection semantics above.

The existing `canonical_article_id` and copied `detail_report` remain a
compatibility projection while readers migrate. They are not the new authority.
For compatibility, an accepted `entry` may project to the legacy field; an
`exit` must not overwrite it. Existing links require a preview/reclassification
pass and are not grandfathered merely because they are populated.

### 3.3 Provider ticker sources remain separable

The existing single `sa_articles.ticker` field cannot retain list/detail
provenance or represent disagreement. The new capture contract therefore adds
`list_ticker`, `list_ticker_observed_at`, `detail_ticker`, and
`detail_ticker_observed_at` to `sa_articles`. `null` means no explicit ticker was
captured from that source; it is not proof that the provider supplied none.
Only the corresponding scraper may update its source observation.

The existing `ticker` field remains a compatibility projection for old readers.
It may be refreshed from a non-conflicting resolved provider identity, but the
new matcher never treats that legacy projection as independent provider
evidence. Existing legacy values are not backfilled into either new source and
must be recaptured or remain fallback/review-only. A manually supplied symbol
is user evidence on an explicit link; it never populates or impersonates the
list/detail provider observations.

## 4. Deterministic Matching Policy

### 4.1 Candidate evidence and provenance

Candidate construction uses six independent facts:

1. event-role anchor date;
2. article publication date;
3. exact ticker from the Alpha Picks analysis-list metadata;
4. exact ticker from the article detail security header;
5. fallback ticker/company evidence from title or stored body; and
6. role evidence from title/body language and the heuristic article type.

List and detail ticker evidence retain distinct provenance codes. Each explicit
provider surface is sufficient to establish exact ticker identity when the
other is absent. When both are present they must normalize to the same ticker;
disagreement is `ticker_metadata_conflict`, remains review-only, and cannot be
overridden by title/body matching. Missing explicit metadata permits the
bounded fallback in Section 4.3 but is never silently reinterpreted as provider
confirmation.

Ticker-prefix matching alone is not strong enough for automatic acceptance.
Article type alone is not strong enough either. No LLM call participates in
identity or acceptance.

### 4.2 Date windows

Matching proceeds in two bounded bands:

1. exact calendar date; then
2. at most three calendar days on either side, to tolerate publication/timezone
   and non-trading-day presentation differences.

Anything outside the three-day band is review-only and is not proposed as the
default candidate. There is no unbounded nearest-date fallback.

### 4.3 Automatic acceptance

An article is auto-linked only when exactly one candidate satisfies one of
these high-confidence shapes:

- exact anchor date + non-conflicting explicit provider ticker metadata +
  compatible role evidence;
- within three days + non-conflicting explicit provider ticker metadata +
  strong role phrase; or
- exact anchor date + strong role phrase + an unambiguous ticker/company
  mention in title or stored body, when both explicit provider ticker sources
  are absent.

Entry phrases include explicit buy/add/initiation language; exit phrases
include sold/closing/removing/stake-exit language. The implementation plan must
centralize the reviewed phrase sets and test them against real captured title
shapes. A generic `analysis` or `commentary` label cannot supply the missing
role/ticker leg.

If two candidates meet the same strongest band, neither is accepted. Stable
article ID may order the review list but may not break an identity tie.

### 4.4 Bounded enrichment before decision

An exact-date/role candidate whose list metadata lacks ticker evidence may be
queued for the existing extension detail fetch before final matching. The
detail result enriches article metadata with the independently extracted
security-header ticker as well as the body; it does not require a title or body
mention when that explicit header is present. This is a bounded enrichment
request, not acceptance. After the enriched metadata/body is committed, the
matcher runs again using the new local evidence.

The extension must not fetch every historical article merely to resolve one
pick. Per-refresh candidate-enrichment limits and normal cache/idempotency rules
remain explicit in the implementation plan.

## 5. Review Queue and Manual Escape Hatch

Unresolved work is keyed by `(pick_id, role)`, not only by symbol. Each row
shows:

- ticker/company;
- event role and anchor date;
- candidate article date/title;
- evidence provenance and ambiguity reason, including list/detail ticker
  disagreement; and
- whether body enrichment is pending, failed, or complete.

The default workflow offers a candidate selection or a scoped `使用目前文章`
action. The raw multiline `TICKER URL` textarea is retained only as an Advanced
escape hatch during transition, then may retire after live coverage evidence.

Manual input must:

- bind to one explicit pick event, not every same-symbol pick;
- accept only a canonical Alpha Picks article URL/ID;
- fetch and store metadata/body/comments through the existing native-host
  boundary;
- display date/role mismatch before confirmation; and
- clear only the exact resolved event after the accepted link is durable.

Pasting a URL must never force a silent link to an unrelated date or replace an
already accepted entry/exit link without explicit confirmation.

## 6. Failure and Integrity Rules

- Pick and article capture commit independently of matching success. An
  ambiguous link cannot roll back provider facts.
- Repeated refreshes are idempotent under pick/article identity and do not
  duplicate accepted links.
- Current and closed rows for the same symbol are separate events.
- A pick date correction invalidates the derived candidate set but does not
  erase the prior decision audit.
- Missing article list/body access remains visible; it does not manufacture a
  `no article exists` conclusion.
- Historical pick/article/body rows are never deleted when a link changes.
- Extension/native-host payloads retain existing sanitization and do not expose
  SA session credentials.

## 7. Alternatives Rejected

### 7.1 Strengthen the existing single canonical field

Rejected because it still cannot represent entry and exit independently and
would preserve body-copy/overwrite semantics.

### 7.2 Choose the closest same-ticker article

Rejected because repeated picks, removals, updates, ticker extraction errors,
and an unbounded date distance produce plausible but false links.

### 7.3 LLM matching

Rejected for V1 because identity must be deterministic, reviewable, cheap, and
replayable. LLM assistance may summarize candidate evidence later but cannot
be the acceptance authority.

## 8. Non-Goals

- matching general SA articles to every ArkScope holding;
- arbitrary web search or server-side SA scraping;
- semantic clustering of update/recap/webinar articles;
- deleting the manual escape hatch before live coverage is measured;
- changing Alpha Picks capture cadence; or
- implementing DB-universe/JSON retirement in the same slice.

## 9. Verification Contract

The future implementation plan must prove, RED first:

1. a sanitized BTSG list-card fixture with date, time, separators, ticker, and
   comment count extracts `BTSG` rather than `null`;
2. a sanitized BTSG detail-header fixture extracts `BTSG` independently of its
   generic article title and body;
3. list/detail ticker observations persist independently, while a mismatch
   remains unresolved as `ticker_metadata_conflict`;
4. entry uses `picked_date`; exit uses `closed_date`;
5. exact-date exact-ticker unique candidates auto-link;
6. ticker-less exact-date candidates require strong body/title evidence;
7. candidates outside three days never auto-link;
8. ties remain unresolved and stable ordering does not decide identity;
9. repeated-symbol picks link independently;
10. exit links do not overwrite the compatibility entry projection;
11. refresh/detail-enrichment reruns are idempotent and bounded;
12. manual selection binds one `(pick_id, role)`, rejects malformed/non-SA
    URLs, and never populates list/detail provider observations;
13. existing suspicious canonical links are reported by preview rather than
    silently preserved;
14. capture facts survive matcher/review failures byte-for-byte; and
15. automated browser/fixture gates cover ticker-less body assistance and
    list/detail conflict, while a live extension gate proves BTSG automatic
    metadata capture without manual symbol injection and retains unrelated
    ambiguity for review.

## 10. Sequence

P2.8 Slice 3 is complete. This revised document receives fresh written review;
after approval it may open its own implementation plan, independently from the
DB-universe/JSON-retirement slice.
