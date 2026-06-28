from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


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
