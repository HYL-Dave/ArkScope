"""Transactional normalized-news store with conservative identity resolution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import sqlite3
from typing import Iterable, Optional

from .body_policy import PreparedBody, choose_active_body, prepare_body
from .identity import build_identity_keys, normalize_identity_text, normalize_timestamp
from .models import ArticleCandidate, ArticleKey, BodyCandidate, BodyStatus, KeyKind
from .schema import ensure_news_normalized_schema
from .tickers import canonical_ticker, load_ticker_aliases


class BodyConflictError(ValueError):
    pass


@dataclass(frozen=True)
class UpsertResult:
    article_id: Optional[int]
    inserted: bool = False
    quarantined: bool = False
    conflict_id: Optional[int] = None


@dataclass(frozen=True)
class _Resolution:
    article_id: Optional[int] = None
    conflict_kind: Optional[str] = None
    existing_ids: tuple[int, ...] = ()


_RELATION_RANK = {"observed_via": 0, "related": 1, "primary": 2}
_CONTENT_RANK = {
    "unknown": 0,
    "headline_only": 1,
    "brief": 2,
    "summary": 3,
    "full_text": 4,
}
_TERMINAL = {
    BodyStatus.FETCHED,
    BodyStatus.EMPTY,
    BodyStatus.UNAVAILABLE,
    BodyStatus.EXPIRED,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hours_after(value: str, hours: int) -> str:
    parseable = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(parseable)
    return (parsed + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def _jsonable(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


class NormalizedNewsStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        ensure_news_normalized_schema(conn)
        self._ticker_aliases = load_ticker_aliases(conn)

    def upsert(self, candidate: ArticleCandidate) -> UpsertResult:
        keys = self._identity_keys(candidate)
        resolution = self._resolve(candidate, keys)
        with self.conn:
            return self._upsert_resolved(candidate, keys, resolution)

    def upsert_uncommitted(self, candidate: ArticleCandidate) -> UpsertResult:
        """Write without opening a transaction.

        Callers that need atomic rollback must already own a transaction; otherwise
        the connection's SQLite autocommit/implicit transaction behavior applies.
        """
        keys = self._identity_keys(candidate)
        resolution = self._resolve(candidate, keys)
        return self._upsert_resolved(candidate, keys, resolution)

    def _identity_keys(self, candidate: ArticleCandidate) -> tuple[ArticleKey, ...]:
        return build_identity_keys(
            source=candidate.source,
            provider_article_id=candidate.provider_article_id,
            url=candidate.url,
            publisher=candidate.publisher,
            title=candidate.title,
            published_at=candidate.published_at,
        )

    def _upsert_resolved(
        self,
        candidate: ArticleCandidate,
        keys: tuple[ArticleKey, ...],
        resolution: _Resolution,
    ) -> UpsertResult:
        if resolution.conflict_kind:
            return self._quarantine(candidate, resolution)

        inserted = resolution.article_id is None
        article_id = resolution.article_id or self._insert_article(
            candidate, keys[0].source
        )
        self._update_article_metadata(article_id, candidate)
        self._attach_keys(article_id, keys)
        self._upsert_title(article_id, candidate)
        self._upsert_tickers(article_id, candidate)
        self._upsert_body(article_id, candidate.body, candidate.source)
        self._refresh_search_document(article_id)
        return UpsertResult(article_id=article_id, inserted=inserted)

    def update_body(
        self,
        candidate: ArticleCandidate,
        body: BodyCandidate,
        *,
        allow_terminal_recovery: bool = False,
    ) -> None:
        article_id = self._require_article_id_for_provider(candidate)
        with self.conn:
            self._update_body_for_article_id(
                article_id,
                candidate,
                body,
                allow_terminal_recovery=allow_terminal_recovery,
            )

    def update_body_uncommitted(
        self,
        candidate: ArticleCandidate,
        body: BodyCandidate,
        *,
        allow_terminal_recovery: bool = False,
    ) -> None:
        """Write body state without opening a transaction.

        Callers that need atomic rollback must already own a transaction; otherwise
        the connection's SQLite autocommit/implicit transaction behavior applies.
        """
        article_id = self._require_article_id_for_provider(candidate)
        self._update_body_for_article_id(
            article_id,
            candidate,
            body,
            allow_terminal_recovery=allow_terminal_recovery,
        )

    def _require_article_id_for_provider(self, candidate: ArticleCandidate) -> int:
        article_id = self._article_id_for_provider(
            candidate.source, candidate.provider_article_id
        )
        if article_id is None:
            raise KeyError("provider article is not present in normalized store")
        return article_id

    def _update_body_for_article_id(
        self,
        article_id: int,
        candidate: ArticleCandidate,
        body: BodyCandidate,
        *,
        allow_terminal_recovery: bool = False,
    ) -> None:
        self._upsert_body(
            article_id,
            body,
            candidate.source,
            allow_terminal_recovery=allow_terminal_recovery,
        )
        if body.status is BodyStatus.FETCHED:
            self._record_title(article_id, candidate, observed_with_body=True)
            self.conn.execute(
                "UPDATE news_articles SET canonical_title=?,content_kind='full_text',"
                "updated_at=? WHERE id=?",
                (candidate.title, _now(), article_id),
            )
        self._refresh_search_document(article_id)

    def latest_cursor(self, source: str, ticker: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT MAX(a.published_at) FROM news_articles a "
            "JOIN news_article_tickers t ON t.article_id=a.id "
            "WHERE a.source=? AND t.ticker=?",
            (source.strip().casefold(), self._canonical_ticker(ticker)),
        ).fetchone()
        return row[0] if row and row[0] else None

    def candidate_by_provider_id(
        self, source: str, provider_article_id: str
    ) -> Optional[ArticleCandidate]:
        article_id = self._article_id_for_provider(source, provider_article_id)
        if article_id is None:
            return None
        row = self.conn.execute(
            "SELECT * FROM news_articles WHERE id=?",
            (article_id,),
        ).fetchone()
        ticker_rows = self.conn.execute(
            "SELECT ticker,relation_kind FROM news_article_tickers WHERE article_id=? "
            "ORDER BY ticker",
            (row["id"],),
        ).fetchall()
        primary = next(
            (item["ticker"] for item in ticker_rows if item["relation_kind"] == "primary"),
            None,
        )
        related = tuple(item["ticker"] for item in ticker_rows)
        body_row = self.conn.execute(
            "SELECT * FROM news_article_bodies WHERE article_id=?", (row["id"],)
        ).fetchone()
        body = BodyCandidate()
        if body_row:
            body = BodyCandidate(
                status=BodyStatus(body_row["body_status"]),
                raw_body=body_row["raw_body"],
                raw_format=body_row["raw_format"],
                retrieval_method=body_row["retrieval_method"],
                retrieval_source=body_row["retrieval_source"],
                source_url=body_row["source_url"],
                fetched_at=body_row["fetched_at"],
                error=body_row["last_error"],
                error_code=body_row["last_error_code"],
                fetch_attempts=int(body_row["fetch_attempts"] or 0),
                next_retry_at=body_row["next_retry_at"],
            )
        return ArticleCandidate(
            source=row["source"],
            provider_article_id=row["provider_article_id"],
            title=row["canonical_title"],
            publisher=row["publisher"] or "",
            url=row["url"] or "",
            published_at=row["published_at"],
            primary_ticker=primary,
            related_tickers=related,
            content_kind=row["content_kind"],
            body=body,
        )

    def _resolve(
        self, candidate: ArticleCandidate, keys: tuple[ArticleKey, ...]
    ) -> _Resolution:
        strong_owners: set[int] = set()
        for key in keys:
            if not key.strong:
                continue
            strong_owners.update(self._owners(key))
        if len(strong_owners) > 1:
            return _Resolution(
                conflict_kind="strong_key_disagreement",
                existing_ids=tuple(sorted(strong_owners)),
            )
        if strong_owners:
            article_id = next(iter(strong_owners))
            row = self.conn.execute(
                "SELECT provider_article_id FROM news_articles WHERE id=?", (article_id,)
            ).fetchone()
            incoming = (candidate.provider_article_id or "").strip() or None
            if (
                row[0]
                and incoming
                and row[0] != incoming
                and not self._article_owns_provider_id(
                    article_id, candidate.source, incoming
                )
            ):
                return _Resolution(
                    conflict_kind="strong_metadata_conflict",
                    existing_ids=(article_id,),
                )
            return _Resolution(article_id=article_id)

        fallback = next(key for key in keys if key.kind is KeyKind.FALLBACK)
        weak_owners = self._owners(fallback)
        compatible = [
            article_id
            for article_id in weak_owners
            if self._weak_compatible(article_id, candidate, keys)
        ]
        if len(compatible) == 1:
            return _Resolution(article_id=compatible[0])
        if len(compatible) > 1:
            return _Resolution(
                conflict_kind="weak_key_ambiguity",
                existing_ids=tuple(sorted(compatible)),
            )
        return _Resolution()

    def _owners(self, key: ArticleKey) -> list[int]:
        return [
            int(row[0])
            for row in self.conn.execute(
                "SELECT article_id FROM news_article_keys "
                "WHERE source=? AND key_kind=? AND key_value=? ORDER BY article_id",
                (key.source, key.kind.value, key.value),
            )
        ]

    def _weak_compatible(
        self,
        article_id: int,
        candidate: ArticleCandidate,
        keys: tuple[ArticleKey, ...],
    ) -> bool:
        row = self.conn.execute(
            "SELECT provider_article_id FROM news_articles WHERE id=?", (article_id,)
        ).fetchone()
        incoming_provider = (candidate.provider_article_id or "").strip() or None
        if row[0] and incoming_provider and row[0] != incoming_provider:
            return False

        candidate_urls = {key.value for key in keys if key.kind is KeyKind.URL}
        existing_urls = {
            item[0]
            for item in self.conn.execute(
                "SELECT key_value FROM news_article_keys "
                "WHERE article_id=? AND key_kind='url'",
                (article_id,),
            )
        }
        if candidate_urls and existing_urls and candidate_urls.isdisjoint(existing_urls):
            return False

        if candidate.body.status is BodyStatus.FETCHED and candidate.body.raw_body:
            digest = hashlib.sha256(candidate.body.raw_body.encode("utf-8")).hexdigest()
            body_row = self.conn.execute(
                "SELECT body_status,body_sha256 FROM news_article_bodies WHERE article_id=?",
                (article_id,),
            ).fetchone()
            if body_row and body_row["body_status"] == "fetched":
                return body_row["body_sha256"] == digest
        return True

    def _insert_article(self, candidate: ArticleCandidate, source: str) -> int:
        now = _now()
        cursor = self.conn.execute(
            "INSERT INTO news_articles "
            "(source,provider_article_id,canonical_title,publisher,url,published_at,"
            "content_kind,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                source,
                (candidate.provider_article_id or "").strip() or None,
                candidate.title,
                candidate.publisher or None,
                candidate.url or None,
                candidate.published_at,
                candidate.content_kind,
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)

    def _update_article_metadata(
        self, article_id: int, candidate: ArticleCandidate
    ) -> None:
        row = self.conn.execute(
            "SELECT provider_article_id,content_kind FROM news_articles WHERE id=?",
            (article_id,),
        ).fetchone()
        provider_id = row[0] or ((candidate.provider_article_id or "").strip() or None)
        content_kind = (
            candidate.content_kind
            if _CONTENT_RANK[candidate.content_kind] > _CONTENT_RANK[row[1]]
            else row[1]
        )
        self.conn.execute(
            "UPDATE news_articles SET provider_article_id=?,publisher=COALESCE(NULLIF(?,''),publisher),"
            "url=COALESCE(NULLIF(?,''),url),content_kind=?,updated_at=? WHERE id=?",
            (
                provider_id,
                candidate.publisher,
                candidate.url,
                content_kind,
                _now(),
                article_id,
            ),
        )

    def _attach_keys(self, article_id: int, keys: Iterable[ArticleKey]) -> None:
        now = _now()
        for key in keys:
            exists = self.conn.execute(
                "SELECT 1 FROM news_article_keys WHERE article_id=? "
                "AND key_kind=? AND key_value=?",
                (article_id, key.kind.value, key.value),
            ).fetchone()
            if exists:
                continue
            self.conn.execute(
                "INSERT INTO news_article_keys "
                "(article_id,source,key_kind,key_value,created_at) VALUES (?,?,?,?,?)",
                (article_id, key.source, key.kind.value, key.value, now),
            )

    def _upsert_title(self, article_id: int, candidate: ArticleCandidate) -> None:
        has_body = candidate.body.status is BodyStatus.FETCHED
        self._record_title(article_id, candidate, observed_with_body=has_body)
        if has_body:
            self.conn.execute(
                "UPDATE news_articles SET canonical_title=?,updated_at=? WHERE id=?",
                (candidate.title, _now(), article_id),
            )
            return
        body_title = self.conn.execute(
            "SELECT 1 FROM news_article_titles WHERE article_id=? "
            "AND observed_with_body=1 LIMIT 1",
            (article_id,),
        ).fetchone()
        if body_title is None:
            latest = self.conn.execute(
                "SELECT title FROM news_article_titles WHERE article_id=? "
                "ORDER BY COALESCE(observed_at,'') DESC,id DESC LIMIT 1",
                (article_id,),
            ).fetchone()
            if latest:
                self.conn.execute(
                    "UPDATE news_articles SET canonical_title=?,updated_at=? WHERE id=?",
                    (latest[0], _now(), article_id),
                )

    def _record_title(
        self, article_id: int, candidate: ArticleCandidate, *, observed_with_body: bool
    ) -> None:
        self.conn.execute(
            "INSERT INTO news_article_titles "
            "(article_id,title,normalized_title,observed_at,observed_with_body) "
            "VALUES (?,?,?,?,?) ON CONFLICT(article_id,title) DO UPDATE SET "
            "observed_at=COALESCE(excluded.observed_at,news_article_titles.observed_at),"
            "observed_with_body=MAX(news_article_titles.observed_with_body,"
            "excluded.observed_with_body)",
            (
                article_id,
                candidate.title,
                normalize_identity_text(candidate.title),
                candidate.observed_at,
                int(observed_with_body),
            ),
        )

    def _upsert_tickers(self, article_id: int, candidate: ArticleCandidate) -> None:
        relations: dict[str, str] = {}
        if candidate.primary_ticker:
            relations[self._canonical_ticker(candidate.primary_ticker)] = "primary"
        for ticker in candidate.related_tickers:
            canonical = self._canonical_ticker(ticker)
            current = relations.get(canonical, "observed_via")
            if _RELATION_RANK["related"] > _RELATION_RANK[current]:
                relations[canonical] = "related"
        now = candidate.observed_at or _now()
        for ticker, kind in relations.items():
            existing = self.conn.execute(
                "SELECT relation_kind FROM news_article_tickers "
                "WHERE article_id=? AND ticker=?",
                (article_id, ticker),
            ).fetchone()
            if existing and _RELATION_RANK[existing[0]] > _RELATION_RANK[kind]:
                kind = existing[0]
            self.conn.execute(
                "INSERT INTO news_article_tickers "
                "(article_id,ticker,relation_kind,first_seen_at,last_seen_at) "
                "VALUES (?,?,?,?,?) ON CONFLICT(article_id,ticker) DO UPDATE SET "
                "relation_kind=excluded.relation_kind,last_seen_at=excluded.last_seen_at",
                (article_id, ticker, kind, now, now),
            )

    def _canonical_ticker(self, ticker: str) -> str:
        return canonical_ticker(ticker, self._ticker_aliases)

    def _upsert_body(
        self,
        article_id: int,
        body: BodyCandidate,
        source: str,
        *,
        allow_terminal_recovery: bool = False,
    ) -> None:
        current = self.conn.execute(
            "SELECT * FROM news_article_bodies WHERE article_id=?", (article_id,)
        ).fetchone()
        if current is None:
            self.conn.execute(
                "INSERT INTO news_article_bodies(article_id,body_status,fetch_attempts) "
                "VALUES (?,?,0)",
                (article_id, BodyStatus.PENDING.value),
            )
            current = self.conn.execute(
                "SELECT * FROM news_article_bodies WHERE article_id=?", (article_id,)
            ).fetchone()

        incoming = body.status
        existing = BodyStatus(current["body_status"])
        if incoming is BodyStatus.PENDING:
            return
        fetched_variant = existing is BodyStatus.FETCHED and incoming is BodyStatus.FETCHED
        explicit_recovery = (
            existing is BodyStatus.UNAVAILABLE
            and incoming is BodyStatus.FETCHED
            and allow_terminal_recovery
        )
        if existing in _TERMINAL and incoming is not existing and not explicit_recovery:
            raise BodyConflictError(
                f"cannot transition {existing.value} to {incoming.value}"
            )
        if existing in {
            BodyStatus.EMPTY,
            BodyStatus.UNAVAILABLE,
            BodyStatus.EXPIRED,
        } and incoming is existing:
            return

        attempts = int(current["fetch_attempts"] or 0) + 1
        attempted_at = _now()
        if incoming is BodyStatus.FETCHED:
            prepared = prepare_body(
                body.raw_body or "",
                raw_format=body.raw_format,
                source=source,
                retrieval_method=body.retrieval_method,
                retrieval_source=body.retrieval_source,
                source_url=body.source_url,
                fetched_at=body.fetched_at or attempted_at,
            )
            if fetched_variant:
                if current["body_sha256"] == prepared.body_sha256:
                    return
                active = self._prepared_body_from_row(current)
                winner = choose_active_body((active, prepared))
                loser = prepared if winner is active else active
                self._insert_body_variant(article_id, loser, attempted_at)
                if winner is active:
                    return
                self.conn.execute(
                    "DELETE FROM news_article_body_variants "
                    "WHERE article_id=? AND body_sha256=?",
                    (article_id, winner.body_sha256),
                )
            self._write_active_body(article_id, prepared, attempts, attempted_at)
            return

        if incoming is BodyStatus.FAILED:
            if existing not in {BodyStatus.PENDING, BodyStatus.FAILED}:
                raise BodyConflictError(f"cannot fail terminal body {existing.value}")
            if body.error_code == 10172:
                unavailable = attempts >= 3
                self.conn.execute(
                    "UPDATE news_article_bodies SET body_status=?,fetch_attempts=?,"
                    "last_attempt_at=?,next_retry_at=?,last_error=?,last_error_code=?,"
                    "unavailable_at=? WHERE article_id=?",
                    (
                        BodyStatus.UNAVAILABLE.value if unavailable else "failed",
                        attempts,
                        attempted_at,
                        None if unavailable else _hours_after(attempted_at, 6),
                        body.error,
                        10172,
                        attempted_at if unavailable else None,
                        article_id,
                    ),
                )
                return
            self.conn.execute(
                "UPDATE news_article_bodies SET body_status='failed',fetch_attempts=?,"
                "last_attempt_at=?,next_retry_at=?,last_error=?,last_error_code=? "
                "WHERE article_id=?",
                (
                    attempts,
                    attempted_at,
                    body.next_retry_at,
                    body.error,
                    body.error_code,
                    article_id,
                ),
            )
            return

        if incoming in {BodyStatus.EMPTY, BodyStatus.EXPIRED}:
            self.conn.execute(
                "UPDATE news_article_bodies SET body_status=?,fetch_attempts=?,"
                "last_attempt_at=?,next_retry_at=NULL,last_error=NULL,last_error_code=NULL "
                "WHERE article_id=?",
                (incoming.value, attempts, attempted_at, article_id),
            )

    @staticmethod
    def _prepared_body_from_row(row: sqlite3.Row) -> PreparedBody:
        return PreparedBody(
            body_sha256=row["body_sha256"],
            raw_body=row["raw_body"] or "",
            raw_format=row["raw_format"],
            body_text=row["body_text"],
            cleaner_version=row["cleaner_version"],
            clean_error=row["clean_error"],
            retrieval_method=row["retrieval_method"],
            retrieval_source=row["retrieval_source"],
            source_url=row["source_url"],
            fetched_at=row["fetched_at"],
        )

    def _insert_body_variant(
        self, article_id: int, body: PreparedBody, created_at: str
    ) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO news_article_body_variants "
            "(article_id,body_sha256,raw_body,raw_format,body_text,cleaner_version,"
            "retrieval_method,retrieval_source,source_url,fetched_at,evidence_ref,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                article_id,
                body.body_sha256,
                body.raw_body,
                body.raw_format,
                body.body_text,
                body.cleaner_version,
                body.retrieval_method,
                body.retrieval_source,
                body.source_url,
                body.fetched_at,
                body.evidence_ref,
                created_at,
            ),
        )

    def _write_active_body(
        self,
        article_id: int,
        body: PreparedBody,
        attempts: int,
        attempted_at: str,
    ) -> None:
        self.conn.execute(
            "UPDATE news_article_bodies SET body_status='fetched',raw_body=?,raw_ref=NULL,"
            "raw_format=?,body_text=?,body_sha256=?,cleaner_version=?,retrieval_method=?,"
            "retrieval_source=?,source_url=?,fetch_attempts=?,last_attempt_at=?,"
            "next_retry_at=NULL,fetched_at=?,last_error=NULL,last_error_code=NULL,"
            "unavailable_at=NULL,cleaned_at=?,clean_error=? WHERE article_id=?",
            (
                body.raw_body,
                body.raw_format,
                body.body_text,
                body.body_sha256,
                body.cleaner_version,
                body.retrieval_method,
                body.retrieval_source,
                body.source_url,
                attempts,
                attempted_at,
                body.fetched_at or attempted_at,
                attempted_at if body.clean_error is None else None,
                body.clean_error,
                article_id,
            ),
        )

    def _refresh_search_document(self, article_id: int) -> None:
        row = self.conn.execute(
            "SELECT a.canonical_title,COALESCE(b.body_text,'') AS body_text "
            "FROM news_articles a LEFT JOIN news_article_bodies b ON b.article_id=a.id "
            "WHERE a.id=?",
            (article_id,),
        ).fetchone()
        self.conn.execute(
            "INSERT INTO news_search_documents(article_id,title,body_text) VALUES (?,?,?) "
            "ON CONFLICT(article_id) DO UPDATE SET title=excluded.title,"
            "body_text=excluded.body_text",
            (article_id, row["canonical_title"], row["body_text"]),
        )

    def _article_id_for_provider(
        self, source: str, provider_article_id: Optional[str]
    ) -> Optional[int]:
        if not provider_article_id:
            return None
        row = self.conn.execute(
            "SELECT a.id FROM news_articles a JOIN news_article_keys k "
            "ON k.article_id=a.id WHERE k.source=? AND k.key_kind='provider_id' "
            "AND k.key_value=?",
            (source.strip().casefold(), provider_article_id.strip()),
        ).fetchone()
        return int(row[0]) if row else None

    def _article_owns_provider_id(
        self, article_id: int, source: str, provider_article_id: str
    ) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM news_article_keys WHERE article_id=? AND source=? "
                "AND key_kind='provider_id' AND key_value=?",
                (
                    article_id,
                    source.strip().casefold(),
                    provider_article_id.strip(),
                ),
            ).fetchone()
            is not None
        )

    def _quarantine(
        self, candidate: ArticleCandidate, resolution: _Resolution
    ) -> UpsertResult:
        payload = json.dumps(
            _jsonable(asdict(candidate)), sort_keys=True, separators=(",", ":")
        )
        keys = build_identity_keys(
            source=candidate.source,
            provider_article_id=candidate.provider_article_id,
            url=candidate.url,
            publisher=candidate.publisher,
            title=candidate.title,
            published_at=candidate.published_at,
        )
        stable_payload = json.dumps(
            {
                "source": candidate.source.strip().casefold(),
                "keys": sorted((key.kind.value, key.value) for key in keys),
                "title": normalize_identity_text(candidate.title),
                "published_at": normalize_timestamp(candidate.published_at),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(stable_payload.encode("utf-8")).hexdigest()
        existing_json = json.dumps(list(resolution.existing_ids), separators=(",", ":"))
        self.conn.execute(
            "INSERT OR IGNORE INTO news_ingest_conflicts "
            "(source,conflict_kind,candidate_fingerprint,candidate_payload_json,"
            "existing_article_ids_json,status,created_at) VALUES (?,?,?,?,?,'open',?)",
            (
                candidate.source.strip().casefold(),
                resolution.conflict_kind,
                fingerprint,
                payload,
                existing_json,
                _now(),
            ),
        )
        row = self.conn.execute(
            "SELECT id FROM news_ingest_conflicts WHERE source=? AND conflict_kind=? "
            "AND candidate_fingerprint=?",
            (
                candidate.source.strip().casefold(),
                resolution.conflict_kind,
                fingerprint,
            ),
        ).fetchone()
        return UpsertResult(
            article_id=None, quarantined=True, conflict_id=int(row[0])
        )
