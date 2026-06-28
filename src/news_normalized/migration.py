"""Streaming, read-only inputs for normalized-news migration planning."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Iterator, Sequence

import pyarrow.parquet as pq

from src.news_identity import canonical_article_hash


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


def inventory_inputs(
    market_db: Path, parquet_paths: Sequence[Path]
) -> InputInventory:
    """Summarize inputs without retaining or returning licensed body content."""
    legacy_counts: dict[str, int] = {}
    legacy_rows: list[tuple[str, str]] = []
    for row in iter_legacy_news(Path(market_db)):
        source = _text(row["source"]).strip().casefold()
        legacy_counts[source] = legacy_counts.get(source, 0) + 1
        legacy_rows.append((source, _text(row["article_hash"])))

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
                evidence.ticker, evidence.title, evidence.published_at
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
