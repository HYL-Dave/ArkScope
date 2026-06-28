"""Pure, data-derived policy for resolving normalized-news migration evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .identity import normalize_timestamp
from .models import ArticleKey, BodyStatus, KeyKind


N7_POLICY_VERSION = "news-n7-v1"


@dataclass(frozen=True)
class BodyEvidenceRef:
    source_path: str
    row_group: int
    row_index: int
    body_sha256: str
    raw_length: int
    clean_length: int
    cleaner_ok: bool
    fetched_at: Optional[str]


@dataclass(frozen=True)
class RejectedLegacy:
    legacy_news_id: int
    reason: str
    ticker_unique: bool
    sentiment_present: bool
    sentiment_unique: bool


@dataclass(frozen=True)
class RejectionEvidenceSummary:
    rejected_rows: int
    rows_with_unique_ticker: int
    unique_ticker_relations: int
    rows_with_sentiment: int
    rows_with_unique_sentiment: int
    fingerprint: str


@dataclass(frozen=True)
class LegacyEvidence:
    legacy_news_id: int
    canonical_ticker: str
    sentiment_value: Optional[float]


@dataclass(frozen=True)
class PolicyGroup:
    source: str
    identity: str
    provider_ids: tuple[str, ...]
    normalized_titles: tuple[str, ...]
    normalized_urls: tuple[str, ...]
    publication_dates: tuple[str, ...]
    published_at: tuple[str, ...]
    tickers: tuple[str, ...]
    sentiment_values: tuple[float, ...]
    body_refs: tuple[BodyEvidenceRef, ...]


@dataclass(frozen=True)
class ResolvedArticle:
    source: str
    identity: str
    canonical_provider_id: Optional[str]
    provider_ids: tuple[str, ...]
    canonical_title: str
    publisher: Optional[str]
    url: Optional[str]
    published_at: str
    identity_keys: tuple[ArticleKey, ...]
    ticker_relations: tuple[tuple[str, str], ...]
    titles: tuple[str, ...]
    sentiment_value: Optional[float]
    active_body: Optional[BodyEvidenceRef]
    cold_bodies: tuple[BodyEvidenceRef, ...]
    body_status: BodyStatus
    fetch_attempts: int


@dataclass(frozen=True)
class LegacyResolution:
    legacy_news_id: int
    article_identity: Optional[str]
    resolution_kind: str
    rejection_reason: Optional[str]


@dataclass(frozen=True)
class TimestampDriftResolution:
    canonical_published_at: str
    resolution_kind: str


@dataclass(frozen=True)
class ResolvedPolicyGroup:
    group: PolicyGroup
    identity_keys: tuple[ArticleKey, ...]


@dataclass(frozen=True)
class PolygonURLResolution:
    action: str
    canonical_provider_id: Optional[str]
    provider_ids: tuple[str, ...]
    identity_keys: tuple[ArticleKey, ...]
    groups: tuple[ResolvedPolicyGroup, ...]


def _provider_keys(source: str, provider_ids: tuple[str, ...]) -> tuple[ArticleKey, ...]:
    return tuple(
        ArticleKey(source, KeyKind.PROVIDER_ID, provider_id, True)
        for provider_id in sorted(set(provider_ids))
        if provider_id
    )


def resolve_timestamp_drift(group: PolicyGroup) -> TimestampDriftResolution:
    if (
        not group.provider_ids
        or len(set(group.normalized_titles)) != 1
        or len(set(group.normalized_urls)) != 1
        or not group.published_at
    ):
        raise ValueError("group is not a computed provider timestamp drift")
    canonical = min(
        group.published_at,
        key=lambda value: normalize_timestamp(value),
    )
    return TimestampDriftResolution(
        canonical_published_at=canonical,
        resolution_kind="provider_timestamp_drift",
    )


def resolve_polygon_shared_url(
    groups: tuple[PolicyGroup, ...],
) -> PolygonURLResolution:
    if not groups or any(group.source != "polygon" for group in groups):
        raise ValueError("Polygon URL policy requires Polygon groups")
    titles = {
        title for group in groups for title in group.normalized_titles if title
    }
    dates = {date for group in groups for date in group.publication_dates if date}
    provider_ids = tuple(
        sorted({item for group in groups for item in group.provider_ids if item})
    )
    if len(titles) == 1 and len(dates) == 1:
        return PolygonURLResolution(
            action="merge",
            canonical_provider_id=provider_ids[0] if provider_ids else None,
            provider_ids=provider_ids,
            identity_keys=_provider_keys("polygon", provider_ids),
            groups=(),
        )
    separated = tuple(
        ResolvedPolicyGroup(
            group=group,
            identity_keys=_provider_keys("polygon", group.provider_ids),
        )
        for group in groups
    )
    return PolygonURLResolution(
        action="demote",
        canonical_provider_id=None,
        provider_ids=provider_ids,
        identity_keys=(),
        groups=separated,
    )


def reject_weak_legacy(
    evidence: LegacyEvidence,
    *,
    candidates: tuple[PolicyGroup, ...],
) -> RejectedLegacy:
    candidate_tickers = {
        ticker for candidate in candidates for ticker in candidate.tickers
    }
    candidate_sentiments = {
        value for candidate in candidates for value in candidate.sentiment_values
    }
    sentiment_present = evidence.sentiment_value is not None
    return RejectedLegacy(
        legacy_news_id=evidence.legacy_news_id,
        reason="legacy_weak_identity_ambiguity",
        ticker_unique=bool(
            evidence.canonical_ticker
            and evidence.canonical_ticker not in candidate_tickers
        ),
        sentiment_present=sentiment_present,
        sentiment_unique=bool(
            sentiment_present and evidence.sentiment_value not in candidate_sentiments
        ),
    )


def _timestamp_rank(value: Optional[str]) -> float:
    normalized = normalize_timestamp(value or "")
    if not normalized:
        return float("-inf")
    parseable = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError:
        return float("-inf")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _body_rank(item: BodyEvidenceRef) -> tuple:
    return (
        -(1 if item.cleaner_ok else 0),
        -item.clean_length,
        -item.raw_length,
        -_timestamp_rank(item.fetched_at),
        item.body_sha256,
    )


def resolve_body_variants(
    bodies: tuple[BodyEvidenceRef, ...],
) -> tuple[BodyEvidenceRef, tuple[BodyEvidenceRef, ...]]:
    unique = {item.body_sha256: item for item in bodies}
    if not unique:
        raise ValueError("at least one body evidence reference is required")
    ordered = tuple(sorted(unique.values(), key=_body_rank))
    return ordered[0], tuple(sorted(ordered[1:], key=lambda item: item.body_sha256))
