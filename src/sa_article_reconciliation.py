"""Deterministic Alpha Picks event-to-article reconciliation authority."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import AbstractSet, Literal
from urllib.parse import urlsplit


Role = Literal["entry", "exit"]
DateBand = Literal["exact", "near", "outside", "missing"]


ENTRY_ROLE_PATTERNS = (
    re.compile(r"\bstock buy\b", re.I),
    re.compile(r"\b(?:initiat(?:e|es|ed|ing|ion)|initial stake)\b", re.I),
    re.compile(r"\bnew (?:position|stake)\b", re.I),
    re.compile(r"\b(?:add|adds|added|adding)\b.{0,40}\b(?:position|stake|shares?)\b", re.I),
)
EXIT_ROLE_PATTERNS = (
    re.compile(r"\bstock sell\b", re.I),
    re.compile(r"\b(?:sell|sells|sold|selling)\b", re.I),
    re.compile(r"\bclos(?:e|es|ed|ing)(?: out)?\b", re.I),
    re.compile(r"\bremov(?:e|es|ed|ing)\b", re.I),
    re.compile(r"\bexit(?:s|ed|ing)?\b", re.I),
)


@dataclass(frozen=True)
class PickEvent:
    lineage_id: int
    symbol_key: str
    company: str
    role: Role
    event_anchor_date: str | None


@dataclass(frozen=True)
class ArticleEvidence:
    article_id: str
    published_date: str | None
    title: str
    body_markdown: str | None
    article_type: str | None
    list_ticker: str | None
    detail_ticker: str | None
    has_content: bool


@dataclass(frozen=True)
class CandidateEvaluation:
    article_id: str
    date_band: DateBand
    date_distance_days: int | None
    evidence_codes: tuple[str, ...]
    strength: int
    auto_eligible: bool
    reason_code: str | None
    needs_enrichment: bool


@dataclass(frozen=True)
class ReconciliationDecision:
    accepted_article_id: str | None
    candidates: tuple[CandidateEvaluation, ...]
    reason_code: str | None


def normalize_symbol(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    return normalized or None


def parse_alpha_picks_article_id(url: str) -> str | None:
    try:
        parsed = urlsplit(str(url))
    except (TypeError, ValueError):
        return None
    if (
        parsed.scheme != "https"
        or parsed.netloc != "seekingalpha.com"
        or parsed.query
        or parsed.fragment
    ):
        return None
    match = re.fullmatch(r"/alpha-picks/articles/(\d+)(?:-[^/]+)?/?", parsed.path)
    return match.group(1) if match else None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return None


def _date_band(anchor: str | None, published: str | None) -> tuple[DateBand, int | None]:
    anchor_date = _parse_date(anchor)
    published_date = _parse_date(published)
    if anchor_date is None or published_date is None:
        return "missing", None
    distance = abs((published_date - anchor_date).days)
    if distance == 0:
        return "exact", 0
    if distance <= 3:
        return "near", distance
    return "outside", distance


def _normalized_text(*values: str | None) -> str:
    return " ".join(" ".join(str(value).split()) for value in values if value)


def _role_matches(role: Role, text: str) -> bool:
    patterns = ENTRY_ROLE_PATTERNS if role == "entry" else EXIT_ROLE_PATTERNS
    return any(pattern.search(text) for pattern in patterns)


def _contains_symbol(text: str, symbol: str) -> bool:
    if not symbol:
        return False
    return re.search(
        rf"(?<![A-Z0-9.]){re.escape(symbol)}(?![A-Z0-9.])",
        text.upper(),
    ) is not None


def _contains_company(text: str, company: str) -> bool:
    company_text = _normalized_text(company).upper()
    return bool(company_text) and company_text in text.upper()


def evaluate_candidate(event: PickEvent, article: ArticleEvidence) -> CandidateEvaluation:
    date_band, distance = _date_band(event.event_anchor_date, article.published_date)
    symbol = normalize_symbol(event.symbol_key) or ""
    list_ticker = normalize_symbol(article.list_ticker)
    detail_ticker = normalize_symbol(article.detail_ticker)

    if list_ticker and detail_ticker and list_ticker != detail_ticker:
        return CandidateEvaluation(
            article_id=article.article_id,
            date_band=date_band,
            date_distance_days=distance,
            evidence_codes=("ticker_metadata_conflict",),
            strength=0,
            auto_eligible=False,
            reason_code="ticker_metadata_conflict",
            needs_enrichment=False,
        )

    evidence: list[str] = []
    if date_band == "exact":
        evidence.append("date_exact")
    elif date_band == "near":
        evidence.append("date_near")
    elif date_band == "outside":
        evidence.append("date_outside")
    else:
        evidence.append("date_missing")

    explicit_tickers = tuple(value for value in (list_ticker, detail_ticker) if value)
    explicit_exact = bool(explicit_tickers) and all(value == symbol for value in explicit_tickers)
    if list_ticker == symbol and list_ticker is not None:
        evidence.append("ticker_list_exact")
    if detail_ticker == symbol and detail_ticker is not None:
        evidence.append("ticker_detail_exact")

    text = _normalized_text(article.title, article.body_markdown)
    symbol_fallback = not explicit_tickers and _contains_symbol(text, symbol)
    company_fallback = (
        not explicit_tickers
        and not symbol_fallback
        and _contains_company(text, event.company)
    )
    if symbol_fallback:
        evidence.append("ticker_text_symbol")
    elif company_fallback:
        evidence.append("ticker_text_company")

    role_match = event.role in ("entry", "exit") and _role_matches(event.role, text)
    if role_match:
        evidence.append(f"role_{event.role}_strong")

    strength = 0
    if role_match and explicit_exact and date_band in ("exact", "near"):
        strength = 3 if date_band == "exact" else 2
    elif (
        role_match
        and not explicit_tickers
        and date_band == "exact"
        and (symbol_fallback or company_fallback)
    ):
        strength = 1

    needs_enrichment = bool(
        strength == 0
        and date_band == "exact"
        and role_match
        and not explicit_tickers
        and not symbol_fallback
        and not company_fallback
        and not article.has_content
        and not article.body_markdown
    )

    reason_code: str | None = None
    if strength == 0:
        if date_band == "missing":
            reason_code = "date_missing"
        elif date_band == "outside":
            reason_code = "outside_date_window"
        elif not role_match:
            reason_code = "role_phrase_missing"
        elif explicit_tickers and not explicit_exact:
            reason_code = "ticker_mismatch"
        elif date_band == "near" and not explicit_tickers:
            reason_code = "explicit_ticker_required"
        elif needs_enrichment:
            reason_code = "needs_enrichment"
        else:
            reason_code = "ticker_identity_missing"

    return CandidateEvaluation(
        article_id=article.article_id,
        date_band=date_band,
        date_distance_days=distance,
        evidence_codes=tuple(evidence),
        strength=strength,
        auto_eligible=strength > 0,
        reason_code=reason_code,
        needs_enrichment=needs_enrichment,
    )


def _article_id_sort_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)


def decide_reconciliation(
    event: PickEvent,
    articles: Sequence[ArticleEvidence],
    *,
    rejected_article_ids: AbstractSet[str] = frozenset(),
) -> ReconciliationDecision:
    candidates = [
        evaluate_candidate(event, article)
        for article in articles
        if article.article_id not in rejected_article_ids
    ]
    candidates.sort(
        key=lambda row: (
            -row.strength,
            row.date_distance_days if row.date_distance_days is not None else 10**9,
            _article_id_sort_key(row.article_id),
        )
    )
    candidate_tuple = tuple(candidates)
    if not candidates:
        return ReconciliationDecision(None, candidate_tuple, "no_candidates")

    best_strength = candidates[0].strength
    winners = [
        row for row in candidates
        if row.auto_eligible and row.strength == best_strength
    ]
    if len(winners) == 1:
        return ReconciliationDecision(winners[0].article_id, candidate_tuple, None)
    if len(winners) > 1:
        return ReconciliationDecision(None, candidate_tuple, "ambiguous_candidates")
    return ReconciliationDecision(None, candidate_tuple, candidates[0].reason_code)
