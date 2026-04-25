"""SA comment signal extraction (Stage 1, rule-based, no LLM).

Pure functions on a single comment's text. Backfill / tool layers live
elsewhere (``src/service/jobs.py``, ``src/tools/sa_tools.py``).

Outputs (per comment):

  - ``ticker_mentions``       — uppercase symbols that match the user's
                                trusted universe (watchlist + Alpha
                                Picks history). Recall < precision here.
  - ``candidate_mentions``    — uppercase symbols that look like tickers
                                but are NOT in the universe; surfaced
                                separately so an analyst can promote
                                them later without polluting trusted
                                signals.
  - ``keyword_buckets``       — ``{bucket_name: [matched_term, ...]}``.
                                The matched terms (not just bucket
                                booleans) are stored so the rule set can
                                be tuned without losing audit trail.
  - ``high_value_score``      — 0..10 weighted sum (see ``_score()``).
  - ``needs_verification``    — True iff the comment contains a hedging
                                word (rumor / hearing / might / ...) AND
                                a concrete claim (ticker or bucket hit).
                                NOT a noise flag — it tags claims that
                                deserve human/agent verification.
  - ``rule_set_version``      — bumped here when rules / buckets change
                                so backfill can selectively re-extract.

Single-letter ticker handling: bare uppercase ``B`` is too noisy
(pronoun-like in some contexts), so single-letter symbols are only
accepted when written as ``$B`` or ``(B)``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Set

RULE_SET_VERSION = "v1.1"
# v1.1 (2026-04-25): word-boundary hedge matching (no "mighty"→"might"
#                   false positive), "May" as month name skipped when
#                   followed by a date, dot-suffix tickers (BRK.B / BF.A).
# v1.0 (2026-04-25): initial release.


# ---------------------------------------------------------------------------
# Stopwords + buckets
# ---------------------------------------------------------------------------

# Uppercase tokens that look like tickers but are usually English words /
# common abbreviations. Universe membership wins over stopwords — a token
# present in the user's trusted universe is always a ticker_mention.
COMMON_STOPWORDS: FrozenSet[str] = frozenset({
    # English short forms / pronouns / fillers
    "I", "A", "OK", "NO", "YES", "ALL", "NEW", "OLD", "BIG",
    "GOOD", "BAD", "BEST", "REAL", "TRUE", "MORE", "MOST",
    "JUST", "ONLY", "VERY", "LIKE", "LOVE", "HATE",
    "ABLE", "EVEN", "OVER", "BACK", "DOWN", "WHEN", "WHAT",
    "WHY", "HOW", "WHO", "WHERE", "WHICH", "THAT", "THIS", "THEY",
    "WITH", "FROM", "INTO", "ONTO", "ALSO", "HAVE", "HAS", "HAD",
    "WILL", "WOULD", "SHOULD", "COULD", "MAY", "MIGHT",
    "FOR", "AS", "AT", "ON", "TO", "IN", "OF", "BY", "OR", "IF",
    "BE", "DO", "IT", "IS", "ME", "MY", "SO", "UP", "WE", "US",
    "AM", "AN", "PM",
    "ADD", "BUY", "SELL", "HOLD", "SOLD", "OWN", "OWNED",
    # Finance acronyms (only stops if not in universe)
    "USA", "ETF", "ADR", "IPO", "EPS", "PE", "PB", "PS", "PEG",
    "ATH", "ATL", "AI", "EV", "VR", "AR",
    "FDA", "SEC", "FY", "Q1", "Q2", "Q3", "Q4",
    "ESG", "MA", "FX", "USD", "EUR", "GBP", "JPY",
    "BTC", "ETH", "DCA", "FOMO", "TBA", "TBD", "EOY", "YTD",
    "RIP", "OP", "LP", "LLC", "INC", "CORP", "ETN", "DOW", "SP",
    "CEO", "CFO", "COO", "CTO", "CIO", "VP", "SVP",
    "AP", "AB",
})

KEYWORD_BUCKETS: Dict[str, List[str]] = {
    "earnings": [
        "earnings", "eps", "beats", "misses", "guidance",
        "revenue", "consensus estimate",
        "earnings beat", "earnings miss",
        "earnings report", "earnings call", "post-earnings",
    ],
    "rating_change": [
        "upgrade", "downgrade", "upgraded", "downgraded",
        "strong buy", "buy rating", "hold rating", "sell rating",
        "raised", "lowered", "price target",
    ],
    "eligibility": [
        "adr", "market cap", "eligible", "ineligible",
        "rating days", "hold limit", "180d", "180-day",
        "new pick", "removed pick",
    ],
    "catalyst": [
        "fda", "contract", "lawsuit", "breaking",
        "announcement", "merger", "acquisition", "buyout",
        "partnership", "spin-off", "spinoff",
    ],
    "rule_query": [
        "ap-clock", "rating history", "max hold",
    ],
}

# Hedging words trigger needs_verification when paired with a concrete claim.
# ASCII hedges are matched as whole words (regex below); CJK hedges are
# substring-matched since they have no word boundaries in Chinese text.
HEDGE_WORDS_ASCII: FrozenSet[str] = frozenset({
    "rumor", "rumored", "hearing", "heard",
    "seems", "seemingly", "might", "could",
    "maybe", "possibly", "supposedly", "allegedly",
})
HEDGE_WORDS_CJK: FrozenSet[str] = frozenset({"据说", "听说"})

_HEDGE_ASCII_RE = re.compile(
    r"\b(" + "|".join(sorted(HEDGE_WORDS_ASCII, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# "may" is special: HEDGE_WORDS would clash with the month name in
# earnings-date contexts (e.g. "earnings May 5"). Match "may" as a hedge
# only when it does NOT immediately precede a day-of-month token. Tested
# in tests/test_sa_comment_signals.py.
_MAY_HEDGE_RE = re.compile(
    r"\bmay\b(?!\s+(?:\d{1,2}|first|second|third|fourth|\d{1,2}(?:st|nd|rd|th)))",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

# Three forms — explicit ones (dollar / paren) accept single-char tickers.
# Bare uppercase requires >= 2 chars.
# Dot tickers (BRK.B, BF.A) are supported by allowing an optional ".X" suffix
# in all three forms.
_TICKER_BODY = r"[A-Z]{1,5}(?:\.[A-Z]{1,2})?"
_TICKER_DOLLAR_RE = re.compile(r"\$(" + _TICKER_BODY + r")\b")
_TICKER_PAREN_RE = re.compile(r"\((" + _TICKER_BODY + r")\)")
# Bare match still requires >= 2 alpha chars in the head to avoid matching
# pronoun-like single letters; dot suffix optional.
_TICKER_BARE_RE = re.compile(r"\b([A-Z]{2,5}(?:\.[A-Z]{1,2})?)\b")

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommentSignals:
    """Result of extracting signals from one comment's text."""

    ticker_mentions: List[str]
    candidate_mentions: List[str]
    keyword_buckets: Dict[str, List[str]]
    high_value_score: float
    needs_verification: bool
    rule_set_version: str = RULE_SET_VERSION

    def is_empty(self) -> bool:
        return (
            not self.ticker_mentions
            and not self.candidate_mentions
            and not self.keyword_buckets
            and self.high_value_score == 0.0
        )


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class CommentSignalExtractor:
    """Stateless rule-based extractor over a fixed ticker universe.

    Construct once per backfill batch (universe + rule set version are
    immutable for the lifetime of an instance).
    """

    def __init__(
        self,
        universe: Iterable[str],
        *,
        rule_set_version: str = RULE_SET_VERSION,
        stopwords: Optional[Iterable[str]] = None,
        keyword_buckets: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self.universe: Set[str] = {t.upper() for t in universe if t}
        self.rule_set_version = rule_set_version
        self.stopwords: FrozenSet[str] = frozenset(
            (s.upper() for s in stopwords) if stopwords is not None else COMMON_STOPWORDS
        )
        self.keyword_buckets = keyword_buckets or KEYWORD_BUCKETS

    def extract(self, comment_text: str, *, upvotes: int = 0) -> CommentSignals:
        if not comment_text or not comment_text.strip():
            return CommentSignals(
                ticker_mentions=[],
                candidate_mentions=[],
                keyword_buckets={},
                high_value_score=0.0,
                needs_verification=False,
                rule_set_version=self.rule_set_version,
            )

        explicit, bare = self._collect_uppercase_tokens(comment_text)
        ticker_mentions, candidate_mentions = self._classify_tokens(explicit, bare)

        text_lower = comment_text.lower()
        keyword_hits = self._match_buckets(text_lower)
        has_link = bool(_URL_RE.search(comment_text))

        score = self._score(
            tickers=len(ticker_mentions),
            bucket_hits=sum(len(v) for v in keyword_hits.values()),
            has_link=has_link,
            upvotes=upvotes,
        )

        has_claim = bool(ticker_mentions) or bool(keyword_hits)
        has_hedge = self._has_hedge_word(comment_text, text_lower)

        return CommentSignals(
            ticker_mentions=ticker_mentions,
            candidate_mentions=candidate_mentions,
            keyword_buckets=keyword_hits,
            high_value_score=round(score, 2),
            needs_verification=has_hedge and has_claim,
            rule_set_version=self.rule_set_version,
        )

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _collect_uppercase_tokens(text: str) -> tuple[Set[str], Set[str]]:
        explicit: Set[str] = set()
        for m in _TICKER_DOLLAR_RE.findall(text):
            explicit.add(m.upper())
        for m in _TICKER_PAREN_RE.findall(text):
            explicit.add(m.upper())
        bare: Set[str] = {m.upper() for m in _TICKER_BARE_RE.findall(text)}
        return explicit, bare

    def _classify_tokens(
        self,
        explicit: Set[str],
        bare: Set[str],
    ) -> tuple[List[str], List[str]]:
        ticker_mentions: List[str] = []
        candidate_mentions: List[str] = []

        for sym in sorted(explicit | bare):
            if sym in self.universe:
                ticker_mentions.append(sym)
                continue
            if sym in self.stopwords:
                # Stopword and not in universe → drop entirely.
                continue
            if len(sym) >= 2:
                candidate_mentions.append(sym)
                continue
            # Single-letter and not in universe / stopwords. Only accept when
            # the user explicitly wrote $X or (X); bare match never gets here
            # because _TICKER_BARE_RE requires >= 2 chars.
            if sym in explicit:
                candidate_mentions.append(sym)
        return ticker_mentions, candidate_mentions

    def _match_buckets(self, text_lower: str) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for bucket, terms in self.keyword_buckets.items():
            matched: List[str] = []
            for term in terms:
                if term.lower() in text_lower:
                    matched.append(term)
            if matched:
                out[bucket] = matched
        return out

    @staticmethod
    def _has_hedge_word(text: str, text_lower: str) -> bool:
        """Word-boundary aware hedge detection.

        ASCII hedges are matched via regex word boundaries (so "may" matches
        but "mayor" doesn't). The bare "may" is further filtered: it counts
        as a hedge only when not followed by a day-of-month token, since
        "earnings May 5" should not flag the comment as needs_verification.
        CJK hedges are substring-matched — Chinese has no word boundaries.
        """
        # ASCII hedges (excluding "may" which has its own rule)
        if _HEDGE_ASCII_RE.search(text):
            return True
        # "may" only when not followed by a date-ish token
        if _MAY_HEDGE_RE.search(text):
            return True
        # CJK
        if any(h in text_lower for h in HEDGE_WORDS_CJK):
            return True
        return False

    @staticmethod
    def _score(
        *,
        tickers: int,
        bucket_hits: int,
        has_link: bool,
        upvotes: int,
    ) -> float:
        score = (
            tickers * 1.0
            + bucket_hits * 1.5
            + (2.0 if has_link else 0.0)
            + math.log1p(max(upvotes, 0)) * 0.5
        )
        return min(score, 10.0)