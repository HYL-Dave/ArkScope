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
from .body_policy import prepare_body
from .identity import (
    build_identity_keys,
    fallback_identity_hash,
    normalize_identity_text,
    normalize_stable_url,
    normalize_timestamp,
)
from .migration_policy import (
    N7_POLICY_VERSION,
    BodyEvidenceRef,
    LegacyEvidence,
    LegacyResolution,
    PolicyGroup,
    RejectedLegacy,
    RejectionEvidenceSummary,
    ResolvedArticle,
    reject_weak_legacy,
    resolve_body_variants,
)
from .models import ArticleKey, BodyStatus, KeyKind
from .tickers import canonical_ticker, load_ticker_aliases


class MigrationPlanDriftError(ValueError):
    pass


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
    row_group: int
    row_index: int


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
    body_variant_groups: int = 0
    cold_body_variants: int = 0


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


@dataclass(frozen=True)
class ResolvedMigrationPreview:
    input_fingerprint: str
    policy_version: str
    resolved_fingerprint: str
    rejection_evidence: RejectionEvidenceSummary
    counts: dict[str, int]
    remaining_blockers: tuple[PreviewConflict, ...]
    would_apply: bool
    sources: dict[str, SourcePreview]
    planned_ticker_links: int
    planned_titles: int
    cross_ticker_rows_collapsed: int
    weak_ambiguities: tuple[PreviewConflict, ...]

    @property
    def fingerprint(self) -> str:
        return self.resolved_fingerprint

    @property
    def blocking_conflicts(self) -> tuple[PreviewConflict, ...]:
        return self.remaining_blockers

    def to_dict(self) -> dict:
        return asdict(self) | {"fingerprint": self.fingerprint}


@dataclass(frozen=True)
class ResolvedMigrationPlan:
    preview: ResolvedMigrationPreview
    articles: tuple[ResolvedArticle, ...]
    legacy_resolutions: tuple[LegacyResolution, ...]


def require_expected_counts(
    preview: ResolvedMigrationPreview, expected: dict[str, int]
) -> None:
    drift = {
        key: (value, preview.counts.get(key))
        for key, value in expected.items()
        if preview.counts.get(key) != value
    }
    if drift:
        raise MigrationPlanDriftError(f"reviewed migration counts changed: {drift}")


@dataclass
class _PlanGroup:
    source: str
    identity: str
    provider_article_id: str | None = None
    provider_ids: set[str] = field(default_factory=set)
    legacy_ids: set[int] = field(default_factory=set)
    tickers: set[str] = field(default_factory=set)
    titles: set[str] = field(default_factory=set)
    publishers: set[str] = field(default_factory=set)
    urls: set[str] = field(default_factory=set)
    published_at: set[str] = field(default_factory=set)
    body_hashes: set[str] = field(default_factory=set)
    body_refs: dict[str, BodyEvidenceRef] = field(default_factory=dict)
    sentiment_values: set[float] = field(default_factory=set)
    mention_hashes: set[str] = field(default_factory=set)
    fallback_keys: set[str] = field(default_factory=set)
    max_fetch_attempts: int = 0
    content_statuses: set[str] = field(default_factory=set)

    def fingerprint_record(self) -> dict:
        return {
            "source": self.source,
            "identity": self.identity,
            "provider_article_id": self.provider_article_id,
            "provider_ids": sorted(self.provider_ids),
            "legacy_ids": sorted(self.legacy_ids),
            "tickers": sorted(self.tickers),
            "titles": sorted(self.titles),
            "publishers": sorted(self.publishers),
            "urls": sorted(self.urls),
            "published_at": sorted(self.published_at),
            "body_hashes": sorted(self.body_hashes),
            "body_refs": [asdict(self.body_refs[key]) for key in sorted(self.body_refs)],
            "sentiment_values": sorted(self.sentiment_values),
            "mention_hashes": sorted(self.mention_hashes),
            "fallback_keys": sorted(self.fallback_keys),
            "max_fetch_attempts": self.max_fetch_attempts,
            "content_statuses": sorted(self.content_statuses),
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


def _parquet_row_to_evidence(
    row: dict,
    path: Path,
    *,
    row_group: int,
    row_index: int,
) -> ParquetEvidence:
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
        row_group=row_group,
        row_index=row_index,
    )


def iter_parquet_news(
    paths: Sequence[Path], *, batch_size: int = 2048
) -> Iterator[list[ParquetEvidence]]:
    """Yield bounded Parquet batches and tolerate older files missing optional columns."""
    for raw_path in sorted(Path(item) for item in paths):
        parquet = pq.ParquetFile(raw_path)
        available = set(parquet.schema.names)
        columns = [name for name in _PARQUET_COLUMNS if name in available]
        for row_group in range(parquet.num_row_groups):
            row_offset = 0
            for batch in parquet.iter_batches(
                batch_size=batch_size,
                row_groups=[row_group],
                columns=columns,
            ):
                rows = batch.to_pylist()
                yield [
                    _parquet_row_to_evidence(
                        row,
                        raw_path,
                        row_group=row_group,
                        row_index=row_offset + index,
                    )
                    for index, row in enumerate(rows)
                ]
                row_offset += len(rows)


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
    group = groups.setdefault(
        identity,
        _PlanGroup(
            source=evidence.source,
            identity=identity,
            provider_article_id=evidence.provider_article_id,
        ),
    )
    if evidence.provider_article_id:
        group.provider_ids.add(evidence.provider_article_id)
    return group


def _add_parquet_evidence(
    group: _PlanGroup, evidence: ParquetEvidence, aliases: dict[str, str]
) -> None:
    canonical_observed = canonical_ticker(evidence.ticker, aliases)
    if evidence.ticker:
        group.tickers.add(canonical_observed)
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
        prepared = prepare_body(
            evidence.raw_body,
            raw_format=None,
            source=evidence.source,
            retrieval_method="parquet_backfill",
            retrieval_source=evidence.source,
            source_url=evidence.url or None,
            fetched_at=evidence.content_fetched_at or evidence.collected_at,
        )
        reference = BodyEvidenceRef(
            source_path=evidence.source_path,
            row_group=evidence.row_group,
            row_index=evidence.row_index,
            body_sha256=prepared.body_sha256,
            raw_length=len(prepared.raw_body),
            clean_length=len(prepared.body_text or ""),
            cleaner_ok=prepared.clean_error is None and bool(prepared.body_text),
            fetched_at=prepared.fetched_at,
        )
        group.body_hashes.add(reference.body_sha256)
        existing = group.body_refs.get(reference.body_sha256)
        if existing is None or (
            reference.source_path,
            reference.row_group,
            reference.row_index,
        ) < (existing.source_path, existing.row_group, existing.row_index):
            group.body_refs[reference.body_sha256] = reference
    if canonical_observed:
        group.mention_hashes.add(
            canonical_article_hash(
                canonical_observed, evidence.title, evidence.published_at
            )
        )
    group.fallback_keys.add(
        _fallback_key(
            source=evidence.source,
            publisher=evidence.publisher,
            title=evidence.title,
            published_at=evidence.published_at,
        )
    )
    group.max_fetch_attempts = max(
        group.max_fetch_attempts, evidence.content_fetch_attempts
    )
    if evidence.content_status:
        group.content_statuses.add(evidence.content_status.casefold())


def _add_input_parquet_evidence(
    group: _PlanGroup, evidence: ParquetEvidence, aliases: dict[str, str]
) -> None:
    observed_ticker = canonical_ticker(evidence.ticker, aliases)
    if evidence.ticker:
        group.tickers.add(observed_ticker)
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
    if observed_ticker:
        group.mention_hashes.add(
            canonical_article_hash(
                observed_ticker, evidence.title, evidence.published_at
            )
        )
    group.fallback_keys.add(
        _fallback_key(
            source=evidence.source,
            publisher=evidence.publisher,
            title=evidence.title,
            published_at=evidence.published_at,
        )
    )


def _input_fingerprint_record(group: _PlanGroup) -> dict:
    return {
        "source": group.source,
        "identity": group.identity,
        "provider_article_id": group.provider_article_id,
        "legacy_ids": sorted(group.legacy_ids),
        "tickers": sorted(group.tickers),
        "titles": sorted(group.titles),
        "publishers": sorted(group.publishers),
        "urls": sorted(group.urls),
        "published_at": sorted(group.published_at),
        "body_hashes": sorted(group.body_hashes),
        "sentiment_values": sorted(group.sentiment_values),
    }


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


def _merge_plan_group(target: _PlanGroup, incoming: _PlanGroup) -> None:
    target.provider_ids.update(incoming.provider_ids)
    target.legacy_ids.update(incoming.legacy_ids)
    target.tickers.update(incoming.tickers)
    target.titles.update(incoming.titles)
    target.publishers.update(incoming.publishers)
    target.urls.update(incoming.urls)
    target.published_at.update(incoming.published_at)
    target.body_hashes.update(incoming.body_hashes)
    for digest, reference in incoming.body_refs.items():
        current = target.body_refs.get(digest)
        if current is None or (
            reference.source_path,
            reference.row_group,
            reference.row_index,
        ) < (current.source_path, current.row_group, current.row_index):
            target.body_refs[digest] = reference
    target.sentiment_values.update(incoming.sentiment_values)
    target.mention_hashes.update(incoming.mention_hashes)
    target.fallback_keys.update(incoming.fallback_keys)
    target.max_fetch_attempts = max(
        target.max_fetch_attempts, incoming.max_fetch_attempts
    )
    target.content_statuses.update(incoming.content_statuses)
    target.provider_article_id = min(target.provider_ids) if target.provider_ids else None


def _resolve_polygon_url_groups(
    groups: dict[str, _PlanGroup],
) -> tuple[int, int]:
    by_url: dict[str, set[str]] = {}
    for identity, group in groups.items():
        if group.source != "polygon":
            continue
        for url in group.urls:
            by_url.setdefault(url, set()).add(identity)
    merged = demoted = 0
    for url in sorted(by_url):
        identities = sorted(identity for identity in by_url[url] if identity in groups)
        if len(identities) < 2:
            continue
        candidates = [groups[identity] for identity in identities]
        titles = {
            normalize_identity_text(title)
            for group in candidates
            for title in group.titles
            if title
        }
        dates = {
            normalize_timestamp(value)[:10]
            for group in candidates
            for value in group.published_at
            if value
        }
        if len(titles) != 1 or len(dates) != 1:
            demoted += 1
            continue
        canonical = min(
            candidates,
            key=lambda group: (
                min(group.provider_ids) if group.provider_ids else group.identity,
                group.identity,
            ),
        )
        for group in candidates:
            if group is canonical:
                continue
            _merge_plan_group(canonical, group)
            groups.pop(group.identity, None)
        merged += 1
    return merged, demoted


def _policy_group(group: _PlanGroup) -> PolicyGroup:
    return PolicyGroup(
        source=group.source,
        identity=group.identity,
        provider_ids=tuple(sorted(group.provider_ids)),
        normalized_titles=tuple(
            sorted({normalize_identity_text(item) for item in group.titles if item})
        ),
        normalized_urls=tuple(sorted(group.urls)),
        publication_dates=tuple(
            sorted(
                {
                    normalize_timestamp(item)[:10]
                    for item in group.published_at
                    if item
                }
            )
        ),
        published_at=tuple(sorted(group.published_at)),
        tickers=tuple(sorted(group.tickers)),
        sentiment_values=tuple(sorted(group.sentiment_values)),
        body_refs=tuple(group.body_refs[key] for key in sorted(group.body_refs)),
    )


def _digest(payload) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _json_value(value):
    if isinstance(value, BodyStatus):
        return value.value
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _resolved_article(group: _PlanGroup) -> ResolvedArticle:
    titles = tuple(sorted(group.titles, key=lambda item: (normalize_identity_text(item), item)))
    canonical_title = titles[0] if titles else "(untitled)"
    published_at = min(
        group.published_at,
        key=lambda item: (normalize_timestamp(item), item),
    ) if group.published_at else "1970-01-01T00:00:00Z"
    provider_ids = tuple(sorted(group.provider_ids))
    canonical_provider_id = provider_ids[0] if provider_ids else None
    publisher = sorted(group.publishers)[0] if group.publishers else None
    url = sorted(group.urls)[0] if group.urls else None
    generated = build_identity_keys(
        source=group.source,
        provider_article_id=canonical_provider_id,
        url=url,
        publisher=publisher or "",
        title=canonical_title,
        published_at=published_at,
    )
    keys: dict[tuple[str, str], ArticleKey] = {
        (key.kind.value, key.value): key for key in generated
    }
    for provider_id in provider_ids:
        key = ArticleKey(group.source, KeyKind.PROVIDER_ID, provider_id, True)
        keys[(key.kind.value, key.value)] = key
    body_refs = tuple(group.body_refs[key] for key in sorted(group.body_refs))
    active = None
    cold: tuple[BodyEvidenceRef, ...] = ()
    if body_refs:
        active, cold = resolve_body_variants(body_refs)
    if active is not None:
        body_status = BodyStatus.FETCHED
    elif group.max_fetch_attempts or "failed" in group.content_statuses:
        body_status = BodyStatus.FAILED
    else:
        body_status = BodyStatus.PENDING
    return ResolvedArticle(
        source=group.source,
        identity=group.identity,
        canonical_provider_id=canonical_provider_id,
        provider_ids=provider_ids,
        canonical_title=canonical_title,
        publisher=publisher,
        url=url,
        published_at=published_at,
        identity_keys=tuple(
            keys[key] for key in sorted(keys)
        ),
        ticker_relations=tuple((ticker, "related") for ticker in sorted(group.tickers)),
        titles=titles,
        sentiment_value=(
            next(iter(group.sentiment_values))
            if len(group.sentiment_values) == 1
            else None
        ),
        active_body=active,
        cold_bodies=cold,
        body_status=body_status,
        fetch_attempts=group.max_fetch_attempts,
    )


def build_resolved_plan(
    market_db: Path, parquet_paths: Sequence[Path]
) -> ResolvedMigrationPlan:
    """Build immutable apply records and a body-redacted preview without writes."""
    aliases = _read_ticker_aliases(Path(market_db))
    groups: dict[str, _PlanGroup] = {}
    input_groups: dict[str, _PlanGroup] = {}
    parquet_rows: dict[str, int] = {}
    for batch in iter_parquet_news(parquet_paths):
        for evidence in batch:
            group = _group_for_parquet(groups, evidence)
            _add_parquet_evidence(group, evidence, aliases)
            input_group = _group_for_parquet(input_groups, evidence)
            _add_input_parquet_evidence(input_group, evidence, aliases)
            parquet_rows[evidence.source] = parquet_rows.get(evidence.source, 0) + 1

    polygon_merged, polygon_demoted = _resolve_polygon_url_groups(groups)
    mention_to_groups: dict[tuple[str, str], set[str]] = {}
    url_to_groups: dict[tuple[str, str], set[str]] = {}
    fallback_to_groups: dict[tuple[str, str], set[str]] = {}
    for identity, group in groups.items():
        for mention in group.mention_hashes:
            mention_to_groups.setdefault((group.source, mention), set()).add(identity)
        if group.source != "polygon":
            for url in group.urls:
                url_to_groups.setdefault((group.source, url), set()).add(identity)
        for fallback in group.fallback_keys:
            fallback_to_groups.setdefault((group.source, fallback), set()).add(identity)

    input_mention_to_groups: dict[tuple[str, str], set[str]] = {}
    input_url_to_groups: dict[tuple[str, str], set[str]] = {}
    input_fallback_to_groups: dict[tuple[str, str], set[str]] = {}
    for identity, group in input_groups.items():
        for mention in group.mention_hashes:
            input_mention_to_groups.setdefault(
                (group.source, mention), set()
            ).add(identity)
        for url in group.urls:
            input_url_to_groups.setdefault((group.source, url), set()).add(identity)
        for fallback in group.fallback_keys:
            input_fallback_to_groups.setdefault(
                (group.source, fallback), set()
            ).add(identity)

    legacy_counts: dict[str, int] = {}
    matched_legacy: dict[str, int] = {}
    legacy_sources: dict[int, str] = {}
    resolutions: list[LegacyResolution] = []
    rejected: list[RejectedLegacy] = []
    pending_weak: list[tuple[LegacyEvidence, tuple[str, ...], str, str]] = []
    weak_conflicts: list[PreviewConflict] = []
    blockers: list[PreviewConflict] = []
    input_mention_conflicts: list[PreviewConflict] = []
    input_mention_ambiguities: list[PreviewConflict] = []
    legacy_evidence_records: dict[int, dict] = {}
    for row in iter_legacy_news(Path(market_db)):
        legacy_id = int(row["id"])
        source = _text(row["source"]).strip().casefold()
        legacy_sources[legacy_id] = source
        legacy_counts[source] = legacy_counts.get(source, 0) + 1
        ticker = canonical_ticker(_text(row["ticker"]), aliases)
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
                    ticker, _text(row["title"]), _text(row["published_at"])
                ),
            ),
            set(),
        )
        if (
            source == "polygon"
            and len(fallback_matches) > 1
            and len(mention_matches) == 1
        ):
            matches = mention_matches
            match_kind = "mention"
        else:
            matches = url_matches or fallback_matches or mention_matches
            match_kind = (
                "url" if url_matches else ("fallback" if fallback_matches else "mention")
            )
        legacy_evidence_records[legacy_id] = {
            "ticker": ticker,
            "sentiment": row["sentiment_score"],
        }

        input_url_matches = (
            input_url_to_groups.get((source, stable_url), set())
            if stable_url
            else set()
        )
        input_fallback_matches = input_fallback_to_groups.get(
            (source, fallback), set()
        )
        input_mention_matches = input_mention_to_groups.get(
            (
                source,
                canonical_article_hash(
                    ticker, _text(row["title"]), _text(row["published_at"])
                ),
            ),
            set(),
        )
        if input_url_matches:
            input_matches = input_url_matches
            input_match_kind = "url"
        elif input_fallback_matches:
            input_matches = input_fallback_matches
            input_match_kind = "fallback"
        else:
            input_matches = input_mention_matches
            input_match_kind = "mention"
        if len(input_matches) == 1:
            input_identity = next(iter(input_matches))
        else:
            input_identity = fallback
            if len(input_matches) > 1:
                conflict = PreviewConflict(
                    "legacy_multiple_strong_url_matches"
                    if input_match_kind == "url"
                    else "legacy_weak_identity_ambiguity",
                    source,
                    stable_url if input_match_kind == "url" else fallback,
                    len(input_matches),
                )
                if input_match_kind == "url":
                    input_mention_conflicts.append(conflict)
                else:
                    input_mention_ambiguities.append(conflict)
        _add_legacy_row(
            input_groups.setdefault(
                input_identity,
                _PlanGroup(source=source, identity=input_identity),
            ),
            row,
            aliases,
        )
        if len(matches) > 1:
            if match_kind == "url":
                blockers.append(
                    PreviewConflict(
                        "legacy_multiple_strong_url_matches",
                        source,
                        stable_url,
                        len(matches),
                    )
                )
                resolutions.append(
                    LegacyResolution(
                        legacy_id, None, "unresolved", "multiple strong URL matches"
                    )
                )
                continue
            pending_weak.append(
                (
                    LegacyEvidence(
                        legacy_news_id=legacy_id,
                        canonical_ticker=ticker,
                        sentiment_value=(
                            float(row["sentiment_score"])
                            if row["sentiment_score"] is not None
                            else None
                        ),
                    ),
                    tuple(sorted(matches)),
                    source,
                    fallback,
                )
            )
            continue
        if matches:
            identity = next(iter(matches))
            matched_legacy[source] = matched_legacy.get(source, 0) + 1
            resolution_kind = f"{match_kind}_matched"
        else:
            identity = fallback
            resolution_kind = "fallback_created"
            groups.setdefault(identity, _PlanGroup(source=source, identity=identity))
        _add_legacy_row(groups[identity], row, aliases)
        resolutions.append(
            LegacyResolution(legacy_id, identity, resolution_kind, None)
        )

    for evidence, matches, source, fallback in pending_weak:
        item = reject_weak_legacy(
            evidence,
            candidates=tuple(_policy_group(groups[identity]) for identity in matches),
        )
        rejected.append(item)
        weak_conflicts.append(
            PreviewConflict(
                "legacy_weak_identity_ambiguity", source, fallback, len(matches)
            )
        )
        resolutions.append(
            LegacyResolution(
                evidence.legacy_news_id,
                None,
                "weak_identity_rejected",
                "multiple metadata-compatible provider articles",
            )
        )

    timestamp_drifts = 0
    for group in groups.values():
        dates = {
            normalize_timestamp(value)[:10]
            for value in group.published_at
            if value
        }
        if group.provider_ids and len(dates) > 1:
            titles = {normalize_identity_text(item) for item in group.titles if item}
            urls = set(group.urls)
            if len(titles) == 1 and len(urls) == 1:
                timestamp_drifts += 1
            else:
                blockers.append(
                    PreviewConflict(
                        "provider_id_reuse", group.source, group.identity, len(dates)
                    )
                )
        if len(group.sentiment_values) > 1:
            blockers.append(
                PreviewConflict(
                    "sentiment_conflict",
                    group.source,
                    group.identity,
                    len(group.sentiment_values),
                )
            )

    articles = tuple(_resolved_article(groups[key]) for key in sorted(groups))
    strong_owners: dict[tuple[str, str, str], set[str]] = {}
    for article in articles:
        for key in article.identity_keys:
            if not key.strong:
                continue
            strong_owners.setdefault(
                (key.source, key.kind.value, key.value), set()
            ).add(article.identity)
    for (source, kind, value), owners in strong_owners.items():
        if len(owners) > 1:
            blockers.append(
                PreviewConflict(
                    "strong_key_multiple_owners",
                    source,
                    f"{kind}:{value}",
                    len(owners),
                )
            )
    for group in groups.values():
        if not group.provider_ids and len(group.urls) > 1:
            blockers.append(
                PreviewConflict(
                    "weak_url_ambiguity",
                    group.source,
                    group.identity,
                    len(group.urls),
                )
            )
    # Mirror the apply-time body-state invariant (validate_applied_plan rejects
    # ``body_status='failed' AND fetch_attempts=0``) into the preview gate so a
    # failed-without-attempts article is refused here, not after the live write.
    for article in articles:
        if article.body_status is BodyStatus.FAILED and article.fetch_attempts <= 0:
            blockers.append(
                PreviewConflict(
                    "body_failed_without_attempts",
                    article.source,
                    article.identity,
                    article.fetch_attempts,
                )
            )
    resolutions_tuple = tuple(sorted(resolutions, key=lambda item: item.legacy_news_id))
    rejected_records = [
        asdict(item)
        | {
            "canonical_ticker": legacy_evidence_records[item.legacy_news_id]["ticker"],
            "sentiment_value": legacy_evidence_records[item.legacy_news_id]["sentiment"],
        }
        for item in sorted(rejected, key=lambda item: item.legacy_news_id)
    ]
    rejected_by_id = {item.legacy_news_id: item for item in rejected}
    unique_tickers = {
        legacy_evidence_records[legacy_id]["ticker"]
        for legacy_id, item in rejected_by_id.items()
        if item.ticker_unique
    }
    rejection_summary = RejectionEvidenceSummary(
        rejected_rows=len(rejected),
        rows_with_unique_ticker=sum(item.ticker_unique for item in rejected),
        unique_ticker_relations=len(unique_tickers),
        rows_with_sentiment=sum(item.sentiment_present for item in rejected),
        rows_with_unique_sentiment=sum(item.sentiment_unique for item in rejected),
        fingerprint=_digest(rejected_records),
    )
    article_payload = [_json_value(asdict(item)) for item in articles]
    resolution_payload = [asdict(item) for item in resolutions_tuple]
    resolved_fingerprint = _digest(
        {
            "policy_version": N7_POLICY_VERSION,
            "articles": article_payload,
            "legacy_resolutions": resolution_payload,
            "rejection_evidence": asdict(rejection_summary),
            "blockers": [asdict(item) for item in blockers],
        }
    )
    input_blocking, input_weak = _plan_conflicts(
        input_groups,
        input_mention_conflicts,
        input_mention_ambiguities,
    )
    input_fingerprint = _digest(
        {
            "groups": [
                _input_fingerprint_record(input_groups[key])
                for key in sorted(input_groups)
            ],
            "blocking": [asdict(item) for item in input_blocking],
            "weak": [asdict(item) for item in input_weak],
        }
    )

    source_names = sorted(set(legacy_counts) | set(parquet_rows) | {item.source for item in articles})
    sources: dict[str, SourcePreview] = {}
    for source in source_names:
        source_groups = [group for group in groups.values() if group.source == source]
        legacy_total = legacy_counts.get(source, 0)
        matched_with_body = sum(
            len(group.legacy_ids)
            for group in source_groups
            if group.provider_ids and group.body_refs
        )
        sources[source] = SourcePreview(
            legacy_rows=legacy_total,
            parquet_rows=parquet_rows.get(source, 0),
            planned_articles=len(source_groups),
            provider_id_matched=sum(
                bool(group.provider_ids and group.legacy_ids) for group in source_groups
            ),
            fallback_only=sum(
                bool(not group.provider_ids and group.legacy_ids) for group in source_groups
            ),
            sqlite_rows_enriched_from_parquet=matched_legacy.get(source, 0),
            body_match_count=matched_with_body,
            body_match_rate=(
                round(matched_with_body / legacy_total, 6) if legacy_total else 0.0
            ),
            body_fetched=sum(bool(group.body_refs) for group in source_groups),
            body_missing=sum(not group.body_refs for group in source_groups),
            body_variant_groups=sum(
                len(group.body_refs) > 1 for group in source_groups
            ),
            cold_body_variants=sum(
                max(0, len(group.body_refs) - 1) for group in source_groups
            ),
        )
    mapped = [item for item in resolutions_tuple if item.article_identity is not None]
    mapped_articles = {item.article_identity for item in mapped}
    counts = {
        "articles": len(articles),
        "identity_keys": sum(len(item.identity_keys) for item in articles),
        "ticker_relations": sum(len(item.ticker_relations) for item in articles),
        "titles": sum(len(item.titles) for item in articles),
        "legacy_rows": len(resolutions_tuple),
        "legacy_mapped": len(mapped),
        "legacy_rejected": len(rejected),
        "timestamp_drifts": timestamp_drifts,
        "polygon_url_merges": polygon_merged,
        "polygon_url_demotions": polygon_demoted,
        "active_bodies": sum(item.active_body is not None for item in articles),
        "body_variant_groups": sum(bool(item.cold_bodies) for item in articles),
        "cold_body_variants": sum(len(item.cold_bodies) for item in articles),
        "body_fetched": sum(item.body_status is BodyStatus.FETCHED for item in articles),
        "body_failed": sum(item.body_status is BodyStatus.FAILED for item in articles),
        "body_pending": sum(item.body_status is BodyStatus.PENDING for item in articles),
        "fts_documents": len(articles),
    }
    ordered_blockers = tuple(
        sorted(blockers, key=lambda item: (item.source, item.kind, item.identity))
    )
    accounted = len(resolutions_tuple) == sum(legacy_counts.values())
    preview = ResolvedMigrationPreview(
        input_fingerprint=input_fingerprint,
        policy_version=N7_POLICY_VERSION,
        resolved_fingerprint=resolved_fingerprint,
        rejection_evidence=rejection_summary,
        counts=counts,
        remaining_blockers=ordered_blockers,
        would_apply=not ordered_blockers and accounted,
        sources=sources,
        planned_ticker_links=sum(len(item.ticker_relations) for item in articles),
        planned_titles=sum(len(item.titles) for item in articles),
        cross_ticker_rows_collapsed=max(0, len(mapped) - len(mapped_articles)),
        weak_ambiguities=tuple(
            PreviewConflict(
                "legacy_weak_identity_ambiguity",
                source,
                "reviewed_rejections",
                sum(item.source == source for item in weak_conflicts),
            )
            for source in sorted({item.source for item in weak_conflicts})
        ),
    )
    return ResolvedMigrationPlan(preview, articles, resolutions_tuple)


def plan_news_normalization(
    market_db: Path, parquet_paths: Sequence[Path]
) -> ResolvedMigrationPreview:
    return build_resolved_plan(market_db, parquet_paths).preview
