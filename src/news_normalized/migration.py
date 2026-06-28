"""Streaming, read-only inputs for normalized-news migration planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterator, Sequence

import pyarrow.parquet as pq

from src.news_identity import canonical_article_hash
from .identity import fallback_identity_hash, normalize_stable_url, normalize_timestamp
from .tickers import canonical_ticker, load_ticker_aliases


@dataclass(frozen=True)
class ParquetEvidence:
    source: str
    provider_article_id: str | None
    ticker: str
    title: str
    published_at: str
    publisher: str
    url: str
    related_tickers: tuple[str, ...]
    raw_body: str | None
    content_status: str | None
    content_fetch_attempts: int
    content_fetched_at: str | None
    collected_at: str | None
    source_path: str


@dataclass(frozen=True)
class InputFileInfo:
    path: str
    rows: int
    size_bytes: int
    mtime_ns: int


@dataclass(frozen=True)
class SourceInventory:
    legacy_rows: int = 0
    parquet_rows: int = 0
    distinct_provider_ids: int = 0
    provider_articles_with_body: int = 0
    provider_articles_without_body: int = 0
    sqlite_rows_matched_to_parquet: int = 0
    sqlite_rows_with_parquet_body: int = 0
    sqlite_match_rate: float = 0.0
    body_match_rate: float = 0.0


@dataclass(frozen=True)
class InputInventory:
    sources: dict[str, SourceInventory]
    parquet_files: tuple[InputFileInfo, ...]


@dataclass(frozen=True)
class PreviewConflict:
    kind: str
    source: str
    identity: str
    count: int


@dataclass(frozen=True)
class SourcePreview:
    legacy_rows: int
    parquet_rows: int
    planned_articles: int
    provider_id_matched: int
    fallback_only: int
    sqlite_rows_enriched_from_parquet: int
    body_match_count: int
    body_match_rate: float
    body_fetched: int
    body_missing: int


@dataclass(frozen=True)
class MigrationPreview:
    sources: dict[str, SourcePreview]
    planned_ticker_links: int
    planned_titles: int
    cross_ticker_rows_collapsed: int
    blocking_conflicts: tuple[PreviewConflict, ...]
    weak_ambiguities: tuple[PreviewConflict, ...]
    fingerprint: str
    would_apply: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class _PlanGroup:
    source: str
    identity: str
    provider_article_id: str | None = None
    legacy_ids: set[int] = field(default_factory=set)
    tickers: set[str] = field(default_factory=set)
    titles: set[str] = field(default_factory=set)
    publishers: set[str] = field(default_factory=set)
    urls: set[str] = field(default_factory=set)
    published_at: set[str] = field(default_factory=set)
    body_hashes: set[str] = field(default_factory=set)
    sentiment_values: set[float] = field(default_factory=set)

    def fingerprint_record(self) -> dict:
        return {
            "source": self.source,
            "identity": self.identity,
            "provider_article_id": self.provider_article_id,
            "legacy_ids": sorted(self.legacy_ids),
            "tickers": sorted(self.tickers),
            "titles": sorted(self.titles),
            "publishers": sorted(self.publishers),
            "urls": sorted(self.urls),
            "published_at": sorted(self.published_at),
            "body_hashes": sorted(self.body_hashes),
            "sentiment_values": sorted(self.sentiment_values),
        }


_PARQUET_COLUMNS = (
    "article_id",
    "ticker",
    "title",
    "published_at",
    "source_api",
    "description",
    "content",
    "url",
    "publisher",
    "related_tickers",
    "collected_at",
    "content_status",
    "content_fetch_attempts",
    "content_fetched_at",
)


def _text(value) -> str:
    return "" if value is None else str(value)


def _optional_text(value) -> str | None:
    text = _text(value).strip()
    return text or None


def _parse_related_tickers(value) -> tuple[str, ...]:
    try:
        items = json.loads(value) if isinstance(value, str) else (value or [])
    except (TypeError, ValueError):
        items = []
    if not isinstance(items, (list, tuple, set)):
        return ()
    return tuple(sorted({_text(item).strip().upper() for item in items if _text(item).strip()}))


def iter_legacy_news(path: Path, *, batch_size: int = 2000) -> Iterator[sqlite3.Row]:
    """Yield legacy rows without creating SQLite WAL/SHM sidecars."""
    conn = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT id,ticker,title,description,url,publisher,source,published_at,"
            "article_hash,sentiment_score,sentiment_source,sentiment_scale "
            "FROM news ORDER BY id"
        )
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            yield from rows
    finally:
        conn.close()


def _source_from_path(path: Path) -> str:
    if len(path.parents) >= 2:
        return path.parents[1].name.strip().casefold()
    return ""


def _parquet_row_to_evidence(row: dict, path: Path) -> ParquetEvidence:
    source = (_optional_text(row.get("source_api")) or _source_from_path(path)).casefold()
    raw_body = _optional_text(row.get("content")) or _optional_text(row.get("description"))
    attempts = row.get("content_fetch_attempts")
    try:
        attempts_int = int(attempts or 0)
    except (TypeError, ValueError):
        attempts_int = 0
    return ParquetEvidence(
        source=source,
        provider_article_id=_optional_text(row.get("article_id")),
        ticker=_text(row.get("ticker")).strip().upper(),
        title=_text(row.get("title")),
        published_at=_text(row.get("published_at")),
        publisher=_text(row.get("publisher")),
        url=_text(row.get("url")),
        related_tickers=_parse_related_tickers(row.get("related_tickers")),
        raw_body=raw_body,
        content_status=_optional_text(row.get("content_status")),
        content_fetch_attempts=max(0, attempts_int),
        content_fetched_at=_optional_text(row.get("content_fetched_at")),
        collected_at=_optional_text(row.get("collected_at")),
        source_path=str(path),
    )


def iter_parquet_news(
    paths: Sequence[Path], *, batch_size: int = 2048
) -> Iterator[list[ParquetEvidence]]:
    """Yield bounded Parquet batches and tolerate older files missing optional columns."""
    for raw_path in sorted(Path(item) for item in paths):
        parquet = pq.ParquetFile(raw_path)
        available = set(parquet.schema.names)
        columns = [name for name in _PARQUET_COLUMNS if name in available]
        for batch in parquet.iter_batches(batch_size=batch_size, columns=columns):
            yield [
                _parquet_row_to_evidence(row, raw_path)
                for row in batch.to_pylist()
            ]


def _read_ticker_aliases(path: Path) -> dict[str, str]:
    conn = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)
    try:
        return load_ticker_aliases(conn)
    finally:
        conn.close()


def inventory_inputs(
    market_db: Path, parquet_paths: Sequence[Path]
) -> InputInventory:
    """Summarize inputs without retaining or returning licensed body content."""
    aliases = _read_ticker_aliases(Path(market_db))
    legacy_counts: dict[str, int] = {}
    legacy_rows: list[tuple[str, str]] = []
    for row in iter_legacy_news(Path(market_db)):
        source = _text(row["source"]).strip().casefold()
        legacy_counts[source] = legacy_counts.get(source, 0) + 1
        legacy_rows.append(
            (
                source,
                canonical_article_hash(
                    canonical_ticker(_text(row["ticker"]), aliases),
                    _text(row["title"]),
                    _text(row["published_at"]),
                ),
            )
        )

    parquet_counts: dict[str, int] = {}
    provider_ids: dict[str, set[str]] = {}
    provider_has_body: dict[tuple[str, str], bool] = {}
    legacy_hash_to_provider: dict[tuple[str, str], set[str]] = {}
    file_infos: list[InputFileInfo] = []

    paths = sorted(Path(item) for item in parquet_paths)
    for path in paths:
        metadata = pq.ParquetFile(path).metadata
        stat = path.stat()
        file_infos.append(
            InputFileInfo(
                path=str(path),
                rows=int(metadata.num_rows),
                size_bytes=int(stat.st_size),
                mtime_ns=int(stat.st_mtime_ns),
            )
        )

    for batch in iter_parquet_news(paths):
        for evidence in batch:
            source = evidence.source
            parquet_counts[source] = parquet_counts.get(source, 0) + 1
            provider_id = evidence.provider_article_id
            if not provider_id:
                continue
            provider_ids.setdefault(source, set()).add(provider_id)
            key = (source, provider_id)
            provider_has_body[key] = provider_has_body.get(key, False) or bool(
                evidence.raw_body
            )
            mention_hash = canonical_article_hash(
                canonical_ticker(evidence.ticker, aliases),
                evidence.title,
                evidence.published_at,
            )
            legacy_hash_to_provider.setdefault((source, mention_hash), set()).add(
                provider_id
            )

    sources = sorted(set(legacy_counts) | set(parquet_counts))
    output: dict[str, SourceInventory] = {}
    for source in sources:
        matched = matched_with_body = 0
        for row_source, article_hash in legacy_rows:
            if row_source != source:
                continue
            matches = legacy_hash_to_provider.get((source, article_hash), set())
            if matches:
                matched += 1
                if any(provider_has_body.get((source, item), False) for item in matches):
                    matched_with_body += 1
        ids = provider_ids.get(source, set())
        with_body = sum(
            1 for provider_id in ids if provider_has_body.get((source, provider_id), False)
        )
        output[source] = SourceInventory(
            legacy_rows=legacy_counts.get(source, 0),
            parquet_rows=parquet_counts.get(source, 0),
            distinct_provider_ids=len(ids),
            provider_articles_with_body=with_body,
            provider_articles_without_body=len(ids) - with_body,
            sqlite_rows_matched_to_parquet=matched,
            sqlite_rows_with_parquet_body=matched_with_body,
            sqlite_match_rate=round(
                matched / legacy_counts.get(source, 0), 6
            ) if legacy_counts.get(source, 0) else 0.0,
            body_match_rate=round(
                matched_with_body / legacy_counts.get(source, 0), 6
            ) if legacy_counts.get(source, 0) else 0.0,
        )
    return InputInventory(sources=output, parquet_files=tuple(file_infos))


def _fallback_key(
    *, source: str, publisher: str, title: str, published_at: str
) -> str:
    return "fallback:" + fallback_identity_hash(
        source=source,
        publisher=publisher,
        title=title,
        published_at=published_at,
    )


def _provider_key(source: str, provider_article_id: str) -> str:
    return f"provider:{source}:{provider_article_id}"


def _group_for_parquet(
    groups: dict[str, _PlanGroup], evidence: ParquetEvidence
) -> _PlanGroup:
    if evidence.provider_article_id:
        identity = _provider_key(evidence.source, evidence.provider_article_id)
    else:
        identity = _fallback_key(
            source=evidence.source,
            publisher=evidence.publisher,
            title=evidence.title,
            published_at=evidence.published_at,
        )
    return groups.setdefault(
        identity,
        _PlanGroup(
            source=evidence.source,
            identity=identity,
            provider_article_id=evidence.provider_article_id,
        ),
    )


def _add_parquet_evidence(
    group: _PlanGroup, evidence: ParquetEvidence, aliases: dict[str, str]
) -> None:
    if evidence.ticker:
        group.tickers.add(canonical_ticker(evidence.ticker, aliases))
    group.tickers.update(
        canonical_ticker(ticker, aliases) for ticker in evidence.related_tickers
    )
    if evidence.title:
        group.titles.add(evidence.title)
    if evidence.publisher:
        group.publishers.add(evidence.publisher)
    stable_url = normalize_stable_url(evidence.url)
    if stable_url:
        group.urls.add(stable_url)
    if evidence.published_at:
        group.published_at.add(evidence.published_at)
    if evidence.raw_body:
        group.body_hashes.add(
            hashlib.sha256(evidence.raw_body.encode("utf-8")).hexdigest()
        )


def _add_legacy_row(
    group: _PlanGroup, row: sqlite3.Row, aliases: dict[str, str]
) -> None:
    group.legacy_ids.add(int(row["id"]))
    ticker = canonical_ticker(_text(row["ticker"]), aliases)
    if ticker:
        group.tickers.add(ticker)
    title = _text(row["title"])
    if title:
        group.titles.add(title)
    publisher = _text(row["publisher"])
    if publisher:
        group.publishers.add(publisher)
    stable_url = normalize_stable_url(_text(row["url"]))
    if stable_url:
        group.urls.add(stable_url)
    published = _text(row["published_at"])
    if published:
        group.published_at.add(published)
    sentiment = row["sentiment_score"]
    if sentiment is not None:
        group.sentiment_values.add(float(sentiment))


def _plan_conflicts(
    groups: dict[str, _PlanGroup],
    mention_conflicts: list[PreviewConflict],
    mention_ambiguities: list[PreviewConflict],
) -> tuple[tuple[PreviewConflict, ...], tuple[PreviewConflict, ...]]:
    blocking = list(mention_conflicts)
    weak = list(mention_ambiguities)
    for group in groups.values():
        publication_dates = {
            normalize_timestamp(value)[:10]
            for value in group.published_at
            if value
        }
        if group.provider_article_id and len(publication_dates) > 1:
            blocking.append(
                PreviewConflict(
                    "provider_id_reuse", group.source, group.identity, len(publication_dates)
                )
            )
        if len(group.body_hashes) > 1:
            conflict = PreviewConflict(
                "body_variant", group.source, group.identity, len(group.body_hashes)
            )
            if group.provider_article_id:
                blocking.append(conflict)
            else:
                weak.append(conflict)
        if len(group.sentiment_values) > 1:
            blocking.append(
                PreviewConflict(
                    "sentiment_conflict",
                    group.source,
                    group.identity,
                    len(group.sentiment_values),
                )
            )
        if not group.provider_article_id and len(group.urls) > 1:
            weak.append(
                PreviewConflict(
                    "weak_url_ambiguity", group.source, group.identity, len(group.urls)
                )
            )
    ordered_blocking = tuple(
        sorted(blocking, key=lambda item: (item.source, item.kind, item.identity))
    )
    ordered_weak = tuple(
        sorted(weak, key=lambda item: (item.source, item.kind, item.identity))
    )
    return ordered_blocking, ordered_weak


def plan_news_normalization(
    market_db: Path, parquet_paths: Sequence[Path]
) -> MigrationPreview:
    """Build a deterministic, body-redacted migration preview without writing inputs."""
    aliases = _read_ticker_aliases(Path(market_db))
    groups: dict[str, _PlanGroup] = {}
    mention_to_groups: dict[tuple[str, str], set[str]] = {}
    url_to_groups: dict[tuple[str, str], set[str]] = {}
    fallback_to_groups: dict[tuple[str, str], set[str]] = {}
    parquet_rows: dict[str, int] = {}

    for batch in iter_parquet_news(parquet_paths):
        for evidence in batch:
            group = _group_for_parquet(groups, evidence)
            _add_parquet_evidence(group, evidence, aliases)
            parquet_rows[evidence.source] = parquet_rows.get(evidence.source, 0) + 1
            mention_hash = canonical_article_hash(
                canonical_ticker(evidence.ticker, aliases),
                evidence.title,
                evidence.published_at,
            )
            mention_to_groups.setdefault(
                (evidence.source, mention_hash), set()
            ).add(group.identity)
            stable_url = normalize_stable_url(evidence.url)
            if stable_url:
                url_to_groups.setdefault(
                    (evidence.source, stable_url), set()
                ).add(group.identity)
            fallback = _fallback_key(
                source=evidence.source,
                publisher=evidence.publisher,
                title=evidence.title,
                published_at=evidence.published_at,
            )
            fallback_to_groups.setdefault(
                (evidence.source, fallback), set()
            ).add(group.identity)

    legacy_counts: dict[str, int] = {}
    matched_legacy: dict[str, int] = {}
    mention_conflicts: list[PreviewConflict] = []
    mention_ambiguities: list[PreviewConflict] = []
    for row in iter_legacy_news(Path(market_db)):
        source = _text(row["source"]).strip().casefold()
        legacy_counts[source] = legacy_counts.get(source, 0) + 1
        stable_url = normalize_stable_url(_text(row["url"]))
        fallback = _fallback_key(
            source=source,
            publisher=_text(row["publisher"]),
            title=_text(row["title"]),
            published_at=_text(row["published_at"]),
        )
        url_matches = (
            url_to_groups.get((source, stable_url), set()) if stable_url else set()
        )
        fallback_matches = fallback_to_groups.get((source, fallback), set())
        mention_matches = mention_to_groups.get(
            (
                source,
                canonical_article_hash(
                    canonical_ticker(_text(row["ticker"]), aliases),
                    _text(row["title"]),
                    _text(row["published_at"]),
                ),
            ),
            set(),
        )
        if url_matches:
            matches = url_matches
            match_kind = "url"
        elif fallback_matches:
            matches = fallback_matches
            match_kind = "fallback"
        else:
            matches = mention_matches
            match_kind = "mention"
        if len(matches) == 1:
            identity = next(iter(matches))
            matched_legacy[source] = matched_legacy.get(source, 0) + 1
        else:
            identity = fallback
            if len(matches) > 1:
                conflict = PreviewConflict(
                    "legacy_multiple_strong_url_matches"
                    if match_kind == "url"
                    else "legacy_weak_identity_ambiguity",
                    source,
                    stable_url if match_kind == "url" else fallback,
                    len(matches),
                )
                if match_kind == "url":
                    mention_conflicts.append(conflict)
                else:
                    mention_ambiguities.append(conflict)
        group = groups.setdefault(
            identity, _PlanGroup(source=source, identity=identity)
        )
        _add_legacy_row(group, row, aliases)

    blocking, weak = _plan_conflicts(
        groups, mention_conflicts, mention_ambiguities
    )
    source_names = sorted(
        set(legacy_counts) | set(parquet_rows) | {group.source for group in groups.values()}
    )
    sources: dict[str, SourcePreview] = {}
    for source in source_names:
        source_groups = [group for group in groups.values() if group.source == source]
        provider_matched = sum(
            1
            for group in source_groups
            if group.provider_article_id and group.legacy_ids
        )
        fallback_only = sum(
            1
            for group in source_groups
            if not group.provider_article_id and group.legacy_ids
        )
        body_count = sum(bool(group.body_hashes) for group in source_groups)
        legacy_total = legacy_counts.get(source, 0)
        matched = matched_legacy.get(source, 0)
        matched_with_body = sum(
            len(group.legacy_ids)
            for group in source_groups
            if group.provider_article_id and group.body_hashes
        )
        sources[source] = SourcePreview(
            legacy_rows=legacy_total,
            parquet_rows=parquet_rows.get(source, 0),
            planned_articles=len(source_groups),
            provider_id_matched=provider_matched,
            fallback_only=fallback_only,
            sqlite_rows_enriched_from_parquet=matched,
            body_match_count=matched_with_body,
            body_match_rate=round(matched_with_body / legacy_total, 6)
            if legacy_total
            else 0.0,
            body_fetched=body_count,
            body_missing=len(source_groups) - body_count,
        )

    payload = {
        "groups": [
            groups[key].fingerprint_record() for key in sorted(groups)
        ],
        "blocking": [asdict(item) for item in blocking],
        "weak": [asdict(item) for item in weak],
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    planned_legacy_articles = sum(
        1 for group in groups.values() if group.legacy_ids
    )
    legacy_total = sum(legacy_counts.values())
    return MigrationPreview(
        sources=sources,
        planned_ticker_links=sum(len(group.tickers) for group in groups.values()),
        planned_titles=sum(len(group.titles) for group in groups.values()),
        cross_ticker_rows_collapsed=max(0, legacy_total - planned_legacy_articles),
        blocking_conflicts=blocking,
        weak_ambiguities=weak,
        fingerprint=fingerprint,
        would_apply=not blocking and not weak,
    )
