# Alpha Picks Article Reconciliation Mini-Design

> **Status:** IMPLEMENTED / LIVE as of 2026-07-19. Independent review, canonical
> A/B, copied-DB migration/state-machine, repeated-Quick, merged popup/privacy,
> and production migration gates are GREEN. The reviewed stack is merged through
> `bf378f1`; production `sa_capture.db` is schema v2 with integrity/FK checks and
> legacy logical-fact digests preserved. The universe/JSON decision remains a
> separate, not-yet-implemented slice.

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

### 2.5 Captured row IDs are not lifecycle identity

The current upsert keys differ by tab: current rows use
`(symbol, picked_date, portfolio_status)`, while closed rows additionally use
`closed_date`. Migration 014 explicitly permits current/closed dual membership,
and migration 015 explicitly permits multiple closed events for one
`(symbol, picked_date)` when close dates differ.

A read-only 2026-07-18 example makes the consequence concrete: RCL with picked
date `2024-03-15` has stale current row `807` and live closed rows `116511` and
`122696` with different close dates. Attaching links or rejection history to any
one of those row IDs would strand the entry relationship across lifecycle
changes. These IDs and counts are diagnostic evidence, not acceptance
constants.

## 3. Locked Relationship Model

### 3.1 Stable lineages and event roles

`sa_alpha_picks.id` identifies one captured current/closed membership row, not a
stable recommendation lifecycle. Current-to-closed movement creates a new row,
and the reviewed source model permits the same `(symbol, picked_date)` in both
tabs and multiple times in the closed tab when `closed_date` differs. Links,
rejections, and review work therefore must not use that row ID as identity.

V1 introduces a persistent `sa_pick_lineages` authority keyed by the source
symbol normalized with trim+uppercase only (provider punctuation is retained)
and canonical `picked_date`:

```text
sa_pick_lineages
  lineage_id
  symbol_key
  picked_date
  created_at
  UNIQUE(symbol_key, picked_date)
```

`sa_alpha_picks` gains a non-cascading `lineage_id` reference. Migration first
creates one lineage per distinct normalized source symbol/picked date, then
attaches every existing observation row before new links are allowed. Refreshes
resolve or create the lineage before inserting membership rows; stale marking
never deletes it. A current row and all closed rows sharing the same source
symbol and picked date therefore retain the same entry identity across
lifecycle changes. Distinct `closed_date` values remain distinct exit events
inside that lineage; they are not silently collapsed as date corrections.

The V1 matching targets are:

| Role | Stable target | Anchor | Cardinality |
|---|---|---|---|
| `entry` | lineage | `picked_date` | at most one accepted article per lineage |
| `exit` | lineage + exit event | `closed_date` | at most one accepted article per distinct exit date |
| `update` | lineage | no automatic anchor in V1 | zero or more explicit future links |

An exit candidate is never compared to `picked_date`. A current pick has no
exit target. Missing/unparseable anchor dates make the event unmatchable rather
than authorizing a ticker-only guess.

A changed `picked_date` is ambiguous without a provider event ID: it may be a
correction or a genuine re-entry. V1 creates a new lineage, preserves the old
lineage and all audit history, and surfaces the possible correction for review;
it never migrates links by symbol alone. Lineage merge/alias is deferred until
there is real correction evidence and is not required for current-to-closed
continuity.

### 3.2 Persistent accepted links, derived candidates

A dedicated relationship table is the eventual authority:

```text
sa_pick_article_links
  link_id
  lineage_id
  article_id
  role                 entry | exit | update
  event_anchor_date    entry picked_date | exit closed_date | null for update
  link_source          auto | user
  evidence_codes       deterministic JSON array
  supersedes_link_id   nullable
  linked_at
  revoked_at           nullable
```

Foreign keys reference `sa_pick_lineages.lineage_id` and
`sa_articles.article_id`. Active `entry` uniqueness is `(lineage_id, role)`;
active `exit` uniqueness is `(lineage_id, role, event_anchor_date)`; `update`
may repeat. A replacement revokes the prior row and inserts a new row with
`supersedes_link_id` in one transaction. The prior row is retained. A separate
candidate-decision log records explicit rejections keyed by
`(lineage_id, role, event_anchor_date, article_id)` so a rejected candidate is
not silently proposed again. Link history and rejection history are never
encoded by mutating article metadata.

Candidate sets and scores are derived from current local evidence at read time.
They do not become accepted links merely because they sort first. The future
schema plan owns exact keys and indexes, including a partial uniqueness rule for
active `entry`/`exit` links, but may not weaken the retained replacement and
rejection semantics above.

The existing `canonical_article_id` and copied `detail_report` remain a
compatibility projection while readers migrate. They are not the new authority.
For compatibility, an accepted `entry` may project to the legacy fields on all
observation rows in its lineage; an `exit` must not overwrite it. Existing
legacy values require a preview/reclassification pass and are not grandfathered
merely because they are populated.

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

### 3.4 Single-writer cutover

The accepted-link authority is the only automatic association writer in this
slice. The two existing nearest/same-ticker mutation paths must be retired in
the same implementation release:

- `save_article_with_comments()` must stop calling
  `_sync_canonical_to_picks()`; article/body/comment capture commits first, then
  the new matcher runs in a separate bounded reconciliation step so matcher
  failure cannot roll back captured provider facts.
- `audit_unresolved_symbols()` may remain as a read projection over unresolved
  lineage events, but its branch that chooses an article and updates
  `canonical_article_id`/`detail_report` must be removed or redirected through
  the reviewed matcher and acceptance policy.

There is no dual-writer compatibility window. Legacy
`canonical_article_id`/`detail_report` writes occur only as a projection of an
accepted `entry` link, transactionally with that link decision. No title,
ticker-prefix, or unbounded nearest-date helper may write those fields directly.
Static and behavioral tests must prove the old writer is unreachable before the
new writer is enabled.

### 3.5 Bounded recent-comment continuity recovery

The provider's article-level comment count, the comments currently exposed in
one browser DOM, and ArkScope's cumulative deduplicated comment inventory are
three different facts. The live gate made the distinction concrete: one article
reported `983` provider comments, a bounded full-profile browser pass exposed
about `207`, and the local store had accumulated `592` across prior sessions.
None of those values proves that the other two are wrong.

The existing scheduler incorrectly treats
`provider comments_count > stored_comments_count` as permanent unfinished work.
That comparison can never converge when Seeking Alpha exposes only a recent
window, and it repeatedly spends Quick refresh time on inaccessible historical
comments. A pure count checkpoint fixes the permanent retry but is too weak: it
would also waive a recoverable middle interval created while the extension was
stopped. V1 therefore separates provider-count observation from a bounded
continuity-recovery state:

```text
sa_articles
  comments_count                         existing provider list observation
  comments_count_observed_at             nullable; parser proved the count was visible
  provider_comments_count_at_last_scan   nullable; last provider count acknowledged
                                         by a usable comment-page scan
  comment_recovery_state                 repaired | pending | unreachable_terminal
  comment_recovery_started_at            nullable; start of the current pending epoch
  comment_recovery_baseline_max_row_id    nullable; frozen pre-upsert comment-row watermark
  comment_recovery_full_miss_count        non-negative; consecutive usable Full misses
  comment_recovery_parked_at              nullable; Full stopped selecting this pending gap
  comment_recovery_last_terminal_at       nullable; retained audit of a stop-chasing decision
  comment_recovery_last_terminal_reason   nullable; reviewed reason code
```

`provider_comments_count_at_last_scan` is an observation checkpoint, not a
coverage or completeness claim. `stored_comments_count` remains a local
inventory fact and may be shown or audited with a signed difference, but the
difference never schedules comment work. `repaired` means only that no
post-enable continuity break is outstanding; it never means lifetime-complete.
`unreachable_terminal` records a decision to stop pursuing an older interval,
not proof that the missing comments do not exist.

The list parser must distinguish an explicit `0 Comments` from an unparseable or
absent count. An explicit count records `comments_count_observed_at`; an unknown
count leaves the observation null and must not overwrite the last known provider
count or trigger/reset the checkpoint. No arbitrary page-wide number scan may
manufacture a count.

For a usable scan, an explicit provider count of zero closes the current
continuity question: current state becomes `repaired`, pending watermark/miss/
park fields clear, and any prior terminal audit remains. This is not a lifetime-
completeness claim; it records that the provider currently exposes no comment
interval to bridge.

Quick comment work is limited to articles in the current list scrape that
already have usable body content. It is scheduled only when a current explicit
provider count differs from `provider_comments_count_at_last_scan`. A null
checkpoint plus a positive explicit count is first evidence and schedules one
scan; null plus explicit zero does not require work. Count decreases also
schedule one scan so moderation/deletion can reset the checkpoint instead of
masking future additions.

The checkpoint detects count changes, not identity changes at an unchanged
total. A deletion and addition that cancel numerically cannot be inferred from
the list card; an explicit Full/Backfill TTL scan may discover it, but Quick does
not claim that coverage.

#### Continuity evidence and frozen baseline

Comment identity is the existing deterministic normalized `comment_id`; the
same identity already owns deduplication and re-parenting. A large sudden drop
in overlap rate is therefore a parser/identity diagnostic, not evidence that
all comments changed.

For every usable scan, the backend must load the existing comment rows,
including their SQLite `id`, before the upsert loop. When an explicit provider
count changed, the article already had existing comments, and the scan overlaps
none of those pre-existing identities, the backend raises `pending`. It freezes
`MAX(existing.id)` as `comment_recovery_baseline_max_row_id` before inserting
the newly scraped comments. A first-ever article scan has no prior continuity
claim and never raises a gap.

While pending, only overlap with an existing comment row whose `id` is at or
below that frozen watermark proves continuity. Comments first inserted by the
gap-raising scan have larger IDs and cannot later repair their own gap. The
watermark and start time remain frozen across nested count changes. Any mode may
clear pending immediately when it reaches one qualifying baseline identity;
proof, not mode name, owns repair.

This row-ID watermark is deliberate. `fetched_at` is insert-only, but its
canonical representation has one-second precision, so a strict timestamp
comparison cannot safely distinguish baseline and new rows in a same-second
transaction.

#### Mode responsibilities and bounded termination

The three modes remain distinct:

- **Quick** is the high-frequency automatic path. It performs the shallow
  count-change scan, may raise pending, and may clear pending when it happens to
  reach the frozen baseline. A usable Quick miss does not increment the Full
  miss counter. Parked articles still receive Quick work when their provider
  count changes, so parking never stops capture of new comments.
- **Full** is bounded routine repair. It prioritizes unparked pending articles,
  then retains bounded newest-first TTL work under the existing Full limit. A
  usable Full scan with no qualifying overlap increments
  `comment_recovery_full_miss_count`; two consecutive misses set
  `comment_recovery_parked_at`. Full has no terminal authority and no longer
  selects a parked gap. Any later qualifying overlap, including one observed by
  Quick or Backfill, repairs it immediately.
- **Backfill** is the explicit deep repair path. It includes parked pending
  articles and retains its larger bounded TTL budget. It is the only mode that
  may transition a gap to `unreachable_terminal`, and only when a usable scan
  reports at least five consecutive rounds at the page bottom with no DOM
  comment growth, no visible loading indicator, and no load-more control
  activated. Timeout, max-scroll exhaustion, navigation failure, and parser
  failure are not terminal evidence.

Terminalization records the audit timestamp/reason, clears the old pending
watermark and park counter, and re-anchors future continuity to the comments
then stored. A later count change may begin a new epoch and move the current
state to `pending` or `repaired`, but it never erases the retained terminal
audit. An unchanged-count scan cannot move `unreachable_terminal` back to
`repaired`, even if it happens to expose an older comment. Terminal rows are not
selected for Full/Backfill work solely because their comment TTL is stale; a
fresh explicit provider-count change may schedule the current epoch normally.
Old comments that become visible during any otherwise eligible scan are still
inserted; the past stop-chasing decision is not retroactively relabelled as
repaired.

Full and Backfill also use the same checkpoint-delta rule for currently scanned
articles. They never rank work by provider-versus-inventory difference and
never promise lifetime reconstruction. There is deliberately no fixed 30/90-day
definition of "old": a post-enable middle interval is pursued until overlap,
parking, or reviewed Backfill terminal evidence; deficits predating this
contract are waived structurally.

A comment-page scan is usable when at least one valid comment was parsed, or
when an explicit provider count of zero was observed and zero comments were
parsed. A positive provider count with zero valid comments is a parser/readiness
failure: body capture may still commit, but `comments_fetched_at` and the
checkpoint do not advance, and a comments-only refresh is not counted as
refreshed. Navigation, native-host, persistence, or parser failures likewise
cannot raise, clear, park, or terminalize recovery. Comment upserts,
`comments_fetched_at`, checkpoint advancement, frozen-watermark creation, and
every recovery-state transition occur in one SQLite transaction.

Because production remains schema v1 until merge, this addendum extends the
not-yet-shipped v1-to-v2 migration instead of introducing a production v3. The
migration seeds `provider_comments_count_at_last_scan = comments_count` only for
rows with an existing `comments_fetched_at`. It seeds no pending flag or frozen
watermark: pre-migration historical deficits are waived structurally, and only
post-enable usable scans may create a recovery epoch. Rows never successfully
scanned retain a null checkpoint. Pre-addendum disposable v2 gate copies are
recreated, never upgraded in place.

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

Unresolved work is keyed by
`(lineage_id, role, event_anchor_date)`, not only by symbol or a transient
`sa_alpha_picks.id`. Each row shows:

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

- bind to one explicit lineage event, not every same-symbol observation row;
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
- Repeated refreshes are idempotent under lineage-event/article identity and do not
  duplicate accepted links.
- Current and closed observation rows with the same `(symbol_key, picked_date)`
  share one lineage; each distinct `closed_date` is a separate exit event.
- A changed `picked_date` creates a new lineage because V1 cannot distinguish a
  correction from a re-entry. The old lineage and decision audit remain intact,
  and no symbol-only migration occurs.
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
- automatic merge/alias of possible picked-date corrections;
- deleting the manual escape hatch before live coverage is measured;
- changing Alpha Picks capture cadence; or
- promising or reconstructing lifetime-complete article comments;
- defining comment recency with a fixed age cutoff; or
- implementing DB-universe/JSON retirement in the same slice.

## 9. Verification Contract

The future implementation plan must prove, RED first:

1. a sanitized BTSG list-card fixture with date, time, separators, ticker, and
   comment count extracts `BTSG` rather than `null`;
2. a sanitized BTSG detail-header fixture extracts `BTSG` independently of its
   generic article title and body;
3. list/detail ticker observations persist independently, while a mismatch
   remains unresolved as `ticker_metadata_conflict`;
4. current and closed rows with the same normalized source symbol and
   `picked_date` resolve to one lineage, preserving the entry link across the
   lifecycle transition;
5. multiple closed rows in one lineage remain distinct exit events by
   `closed_date`, while a changed `picked_date` creates a separate lineage;
6. entry uses `picked_date`; exit uses its exact `closed_date`;
7. exact-date exact-ticker unique candidates auto-link;
8. ticker-less exact-date candidates require strong body/title evidence;
9. candidates outside three days never auto-link;
10. ties remain unresolved and stable ordering does not decide identity;
11. repeated-symbol lineages link independently;
12. exit links do not overwrite the compatibility entry projection;
13. refresh/detail-enrichment reruns are idempotent and bounded;
14. manual selection binds one
    `(lineage_id, role, event_anchor_date)`, rejects malformed/non-SA URLs, and
    never populates list/detail provider observations;
15. existing suspicious canonical links are reported by preview rather than
    silently preserved;
16. `_sync_canonical_to_picks()` and the mutating branch of
    `audit_unresolved_symbols()` cannot write outside the new accepted-link
    authority, with no dual-writer test configuration;
17. article/pick capture facts survive matcher/review failures byte-for-byte;
    and
18. automated browser/fixture gates cover ticker-less body assistance and
    list/detail conflict, while a live extension gate proves BTSG automatic
    metadata capture without manual symbol injection and retains unrelated
    ambiguity for review;
19. list parsing distinguishes explicit zero comments from an unknown count and
    never overwrites a prior observation with unknown;
20. v1-to-v2 migration seeds the checkpoint only for previously scanned rows,
    seeds no recovery flag/watermark, and preserves every article/comment row;
21. Quick schedules on explicit provider-count change, including a decrease,
    but does not schedule a stable historical inventory difference;
22. a first-ever article scan establishes a baseline without raising pending;
23. a gap-raising scan freezes the existing maximum comment row ID before its
    upserts, and a later scan that overlaps only comments inserted after that
    watermark cannot falsely repair the gap;
24. any mode repairs pending immediately when it overlaps a qualifying frozen-
    baseline identity, while unusable scans cannot change recovery state;
25. two consecutive usable Full misses park pending without terminalizing it;
    Quick count-change capture and evidence-based repair remain available while
    parked;
26. Backfill terminalizes only after five stable-bottom rounds with no growth,
    loader, or activated load-more control; timeout/max-scroll/failure evidence
    leaves pending intact;
27. terminalization re-anchors future capture and retains its audit timestamp
    and reason through later recovery epochs; unchanged-count overlap cannot
    erase terminal state, and terminal rows do not re-enter work from TTL alone;
28. Full/Backfill prioritize eligible recovery state, retain bounded newest-
    first TTL work, and never use inventory-gap size as priority or backlog;
29. positive provider count plus zero parsed comments leaves the checkpoint,
    `comments_fetched_at`, and recovery state unchanged;
30. explicit provider zero plus zero parsed comments, and positive provider
    count plus at least one parsed comment, commit their permitted checkpoint
    and state changes atomically;
31. body capture survives an unusable comment scan without falsely reporting a
    comment refresh; and
32. a copied-DB/live rerun proves a stable provider count does not rescan a
    waived historical difference, while a fixture-backed interrupted interval
    remains pending until frozen-baseline overlap or explicit Backfill terminal
    evidence.

## 10. Sequence

P2.8 Slice 3 and this independent reconciliation line are complete. Core and
comment-continuity implementation, independent review, copied-DB/live proof,
merged-tree verification, and the exclusive production v1-to-v2 migration are
closed. The Advanced manual URL escape hatch remains available until observed
automatic coverage justifies a separate removal decision. DB-universe/JSON
retirement remains an independent next-line candidate.
