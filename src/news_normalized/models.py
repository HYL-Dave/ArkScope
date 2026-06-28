from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple


class KeyKind(str, Enum):
    PROVIDER_ID = "provider_id"
    URL = "url"
    FALLBACK = "fallback"


class BodyStatus(str, Enum):
    PENDING = "pending"
    FETCHED = "fetched"
    EMPTY = "empty"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ArticleKey:
    source: str
    kind: KeyKind
    value: str
    strong: bool

    def __post_init__(self) -> None:
        expected_strength = self.kind in (KeyKind.PROVIDER_ID, KeyKind.URL)
        if self.strong != expected_strength:
            raise ValueError(
                f"{self.kind.value} key strength must be {expected_strength}"
            )


@dataclass(frozen=True)
class BodyCandidate:
    status: BodyStatus = BodyStatus.PENDING
    raw_body: Optional[str] = None
    raw_format: Optional[str] = None
    retrieval_method: Optional[str] = None
    retrieval_source: Optional[str] = None
    source_url: Optional[str] = None
    fetched_at: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class ArticleCandidate:
    source: str
    title: str
    published_at: str
    provider_article_id: Optional[str] = None
    publisher: str = ""
    url: str = ""
    primary_ticker: Optional[str] = None
    related_tickers: Tuple[str, ...] = field(default_factory=tuple)
    observed_at: Optional[str] = None
    content_kind: str = "unknown"
    body: BodyCandidate = field(default_factory=BodyCandidate)

    def __post_init__(self) -> None:
        object.__setattr__(self, "related_tickers", tuple(self.related_tickers))


@dataclass(frozen=True)
class WriterBudget:
    max_articles: int
    max_body_fetches: int

    def __post_init__(self) -> None:
        if self.max_articles < 0 or self.max_body_fetches < 0:
            raise ValueError("writer budgets must be non-negative")


@dataclass(frozen=True)
class WriterContinuation:
    deferred_tickers: Tuple[str, ...] = field(default_factory=tuple)
    deferred_body_ids: Tuple[str, ...] = field(default_factory=tuple)
    cursor: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "deferred_tickers", tuple(self.deferred_tickers))
        object.__setattr__(self, "deferred_body_ids", tuple(self.deferred_body_ids))


@dataclass(frozen=True)
class WriterResult:
    status: str
    articles_seen: int
    articles_inserted: int
    bodies_fetched: int
    errors: Dict[str, str]
    continuation: Optional[WriterContinuation]
