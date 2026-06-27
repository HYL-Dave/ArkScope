# News Identity Repair (S3.0a) Design

Date: 2026-06-27
Status: approved design; implementation and live apply remain gated

## Purpose

Restore one canonical identity contract for local news after ticker aliases were folded without
recomputing `article_hash`. The repair must preserve useful content, remove only proven identity
collisions, keep FTS synchronized, and prevent future ticker renames from recreating the defect.

This is a completion of S3.0, not a fuzzy-news deduplication feature. Two articles are identical for
this slice only when they resolve to the same existing canonical identity:

```text
sha256(f"{canonical_ticker}|{title}|{published_at[:10]}")
```

Ticker and title remain verbatim. Case-folding, whitespace normalization, URL similarity, and
cross-title semantic matching are explicitly out of scope because they could merge distinct news.

## Verified Live State

The 2026-06-27 read-only audit of `data/market_data.db` found:

- `news = news_fts = 371,675`, with no missing or orphaned FTS rowids.
- Every stored hash is 64 characters and there are no exact duplicate stored hashes.
- 1,148 rows nevertheless have a hash that does not match their current ticker/title/date:
  - `HAPN`: 369 stale hashes inherited from `LC`.
  - `BRK B`: 779 stale hashes inherited from `BRK.B`.
- HAPN contains 101 collision groups (202 rows): one stale LC-derived hash and one canonical
  HAPN-derived hash per group.
- In 93 of those groups, the stale row has a non-empty `description` while the canonical row does
  not. Deleting stale rows without merging would lose content.
- BRK B currently has no collision groups, but its 779 hashes violate the same invariant.

Counts are observations, not hard-coded migration inputs. The live apply must recompute a fresh
preview while holding the market write lock and refuse to proceed if the classified totals change
between preview and apply.

## Chosen Architecture

### 1. One production hash helper

Create a small shared news-identity module containing `canonical_article_hash(ticker, title,
published_at)`. It owns the SHA-256 formula and date extraction. The direct provider adapter and the
PG migration script both import this helper; neither keeps a private copy of the formula.

The helper does not canonicalize ticker aliases itself. Callers must pass the ticker that will be
stored in the row. This keeps alias resolution and identity calculation explicit and testable.

### 2. Alias-aware news reconciliation

News ticker reconciliation gets a news-specific path instead of relying on the generic
`UPDATE ticker` operation. For every alias row:

1. Resolve the canonical ticker.
2. Compute the target hash from canonical ticker, current title, and current publication date.
3. If no row owns the target hash, update ticker and hash together.
4. If another row owns the target hash, treat the pair as a proven identity collision:
   - Preserve the target/canonical row and its `id`.
   - Fill only missing target fields from the stale row.
   - Never replace a non-empty target value with a stale value.
   - Merge candidates are `description`, `url`, `publisher`, `sentiment_score`,
     `sentiment_source`, and `sentiment_scale`.
   - Delete the stale row only after the merge succeeds.

`source` and the time portion of `published_at` are deliberately not merged. The canonical owner
wins for those fields: the hash contract intentionally identifies by ticker/title/calendar date,
and changing provenance or timestamp while reconciling identity would invent a composite record.

The canonical row ID is preserved because it is already the stable owner of the canonical hash and
is the row future writes will deduplicate against.

### 3. Existing-state repair

The existing rows have already had their tickers changed, so a one-time repair cannot find them via
`ticker = alias`. It scans news identities, computes the expected hash from each row's current
ticker/title/date, and classifies mismatches as:

- `safe_update`: expected hash is unowned; update the hash.
- `collision`: expected hash is owned by another row; merge into the canonical owner, then delete
  the stale row.
- `already_canonical`: no change.

The repair is generic and therefore closes HAPN, BRK B, and any other current mismatch. It does not
assume that every stale row came from a specific alias.

The normal runtime canonicalization path must not scan the full news table on every incremental
sync. It processes only rows whose ticker is currently an alias. The full-table classifier is used
only by the explicit one-time repair and its dry-run.

Only `news` uses this identity-aware handler. Prices, IV, and fundamentals keep the existing generic
ticker reconciliation because none of their stored identities duplicate ticker inside a separate
hash column.

## Transaction and Failure Model

The live operation follows this sequence:

1. Confirm the target is the real `market_data.db` and that no temporary DB override is active.
2. Acquire `market_write_lock`, serializing against direct writers and the PG mirror.
3. Run a read-only preview and retain its classification fingerprint.
4. Create a timestamped WAL-safe backup using SQLite's backup API. Never overwrite an older backup.
5. Start one SQLite transaction.
6. Recompute the classification and require it to match the preview fingerprint.
7. Apply merges, deletes, and updates.
8. Run all post-conditions inside the transaction.
9. Commit only if every post-condition passes; otherwise rollback everything.

The backup is created while the write lock is held and before the transaction mutates data. The
operation is idempotent: a second preview/apply reports zero changes and creates no unnecessary
backup.

## Post-Conditions

The transaction must not commit unless all are true:

- Every non-null `article_hash` equals the canonical hash of the row's current ticker/title/date.
- No duplicate `article_hash` groups exist.
- No duplicate `(source, ticker, title, published_at)` groups exist that were created by an alias
  collision handled by this repair.
- No alias ticker remains in rows processed by the repair.
- `news` and `news_fts` have equal row counts.
- There are no missing or orphaned FTS rowids.
- Merged fields survive on the retained canonical rows.
- The number of deleted rows equals the number of classified collision rows.
- The second run classifies zero updates and zero collisions.

Based on the audited snapshot, the expected result is 101 deletes and 1,047 hash updates, with
`news` and `news_fts` both ending near 371,574. These values are operator expectations only; the
fresh locked preview is authoritative.

## FTS Behavior

The existing `news_au` and `news_ad` triggers remain the sole FTS writers. Field merges and hash
updates use normal `UPDATE`; collision removal uses normal `DELETE`. The repair must not write
`news_fts` manually or rebuild the entire FTS index.

## Test Strategy

Hermetic tests use temporary SQLite databases and real triggers:

1. Shared hash helper matches known SHA-256 vectors and is used by both direct and migration paths.
2. Alias-only news row updates ticker and hash atomically.
3. Collision keeps the canonical row ID and deletes the stale row.
4. A richer stale description fills an empty canonical description.
5. A stale value never overwrites an existing canonical value.
6. Sentiment fields follow the same fill-missing-only rule.
7. FTS finds merged text and has no orphan after collision deletion.
8. BRK-style non-colliding stale hashes are repaired without deleting rows.
9. Failure during a multi-row repair rolls back all changes.
10. Preview performs no writes or schema creation.
11. Apply refuses a preview/apply fingerprint mismatch.
12. A second repair is a zero-change no-op.

Regression tests cover the direct news writer, PG mirror canonicalization, bootstrap,
`preflight_canonicalize`, hash uniqueness, and FTS synchronization.

## Documentation Cleanup

Update stale comments in the module docstrings of `news_providers.py` and `news_direct.py` that still
describe the direct identity as MD5 or `dedup_hash`. Record S3.0a under
`NEWS_DIRECT_LOCAL_PLAN.md` and do not mark S3.0 fully complete until the live post-conditions pass.

## Sequencing

S3.0a is completed before S3.1 status/health work. S3.1 is also revised so run-level telemetry comes
from `provider_sync_runs`, while current per-ticker errors come from `provider_sync_meta`; a
successful aggregate run must not hide isolated ticker failures.

No S3.2 default-on cutover occurs until S3.0a live validation and the corrected S3.1 telemetry reader
are complete.
