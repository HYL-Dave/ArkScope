"""Tests for SA Digest tool (P1.3 commit 1).

Coverage per spec docs/design/P1_3_SPEC.md §8:

  - Disabled / unavailable backend / empty ticker → helpful payload (1-3)
  - Param clamping for days / max_* / min_comment_score (4-5)
  - Per-source normalization, ordering preserved (6-7)
  - Comments ticker vs candidate split (8)
  - Per-article cap (≤3) is the responsibility of SQL — Python just splits;
    test verifies Python split honours the kind tag and does not re-cap (9)
  - needs_verification rows kept, not filtered (10)
  - Excerpt truncation marker on long bodies (11)
  - data_quality.rows always present with zeros (12)
  - source_notes carries the opinion-not-fact disclaimer + window/cap line (13)
  - Per-source failure isolated — one source raising does not blank the others (14)
  - body_markdown / article_url missing → data_quality.missing[] (15)
  - JSON-serializable output (16)

Tests do NOT touch the registry / Anthropic / OpenAI bridges — that lives
in commit 2.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tools import sa_digest_tools as sd
from src.tools.sa_digest_tools import (
    EXCERPT_LEN,
    NEWS_DISCUSSION_GATE,
    PER_ARTICLE_COMMENT_CAP,
    get_sa_digest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enable_sa(monkeypatch):
    monkeypatch.setattr(sd, "_is_sa_enabled", lambda: True)


def _disable_sa(monkeypatch):
    monkeypatch.setattr(sd, "_is_sa_enabled", lambda: False)


def _fake_backend() -> SimpleNamespace:
    """Backend object with a `_get_conn` attr the tool will recognise."""
    return SimpleNamespace(_get_conn=lambda: object())


def _dal_with(backend) -> SimpleNamespace:
    return SimpleNamespace(_backend=backend)


def _stub_fetch_dicts(monkeypatch, mapping):
    """Patch _fetch_dicts with a per-source dispatcher.

    `mapping` is a dict keyed by a substring expected in the SQL
    (e.g. "sa_articles", "sa_market_news", "sa_comment_signals") to
    either a list of rows OR an Exception instance to raise.
    """

    def fake(backend, sql, params):
        for key, value in mapping.items():
            if key in sql:
                if isinstance(value, BaseException):
                    raise value
                return value
        return []

    monkeypatch.setattr(sd, "_fetch_dicts", fake)


# ---------------------------------------------------------------------------
# 1-3: disabled / unavailable / empty ticker
# ---------------------------------------------------------------------------


class TestDisabledOrUnavailable:
    def test_disabled_returns_helpful_string(self, monkeypatch):
        _disable_sa(monkeypatch)
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="NVDA")
        assert "disabled" in out.get("message", "").lower()

    def test_unavailable_dal_returns_pack_with_error(self, monkeypatch):
        _enable_sa(monkeypatch)
        # FileBackend has no _get_conn
        dal = SimpleNamespace(_backend=SimpleNamespace())
        out = get_sa_digest(dal=dal, ticker="NVDA")
        assert out["ticker"] == "NVDA"
        assert out["recent_articles"] == []
        assert out["data_quality"]["rows"] == {
            "articles": 0, "news": 0, "comments_ticker": 0, "comments_candidate": 0,
        }
        assert any("PostgreSQL" in e or "_get_conn" in e
                   for e in out["data_quality"]["errors"])

    def test_empty_ticker_returns_pack_with_error(self, monkeypatch):
        _enable_sa(monkeypatch)
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="   ")
        assert "ticker is required" in " ".join(out["data_quality"]["errors"])
        assert out["recent_articles"] == []


# ---------------------------------------------------------------------------
# 4-5: param clamping
# ---------------------------------------------------------------------------


class TestParamClamping:
    def test_window_days_clamped(self, monkeypatch):
        _enable_sa(monkeypatch)

        captured = {}

        def fake(backend, sql, params):
            if "sa_comment_signals" in sql:
                captured["days"] = params["days"]
            return []

        monkeypatch.setattr(sd, "_fetch_dicts", fake)
        out_lo = get_sa_digest(
            dal=_dal_with(_fake_backend()), ticker="NVDA", days=0,
        )
        assert out_lo["window"]["days"] == 1
        assert captured["days"] == 1

        out_hi = get_sa_digest(
            dal=_dal_with(_fake_backend()), ticker="NVDA", days=999,
        )
        assert out_hi["window"]["days"] == 90

    def test_max_clamps(self, monkeypatch):
        _enable_sa(monkeypatch)

        captured = {}

        def fake(backend, sql, params):
            if "sa_articles\n" in sql or "FROM sa_articles" in sql and "JOIN sa_article_comments" not in sql:
                captured["max_articles"] = params.get("max_articles")
            if "sa_market_news" in sql:
                captured["max_news"] = params.get("max_news")
            if "sa_comment_signals" in sql:
                captured["max_comments"] = params.get("max_comments")
            return []

        monkeypatch.setattr(sd, "_fetch_dicts", fake)
        get_sa_digest(
            dal=_dal_with(_fake_backend()),
            ticker="NVDA", max_articles=0, max_news=0, max_comments=0,
        )
        assert captured["max_articles"] == 1
        assert captured["max_news"] == 1
        assert captured["max_comments"] == 1

        get_sa_digest(
            dal=_dal_with(_fake_backend()),
            ticker="NVDA", max_articles=999, max_news=999, max_comments=999,
        )
        assert captured["max_articles"] == 20
        assert captured["max_news"] == 20
        assert captured["max_comments"] == 30


# ---------------------------------------------------------------------------
# 6-7: per-source normalization
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_articles_normalization_and_ordering(self, monkeypatch):
        _enable_sa(monkeypatch)
        rows = [
            {
                "article_id": "AID1",
                "title": "Strong Q3",
                "author": "Anlyst A",
                "published_date": date(2026, 4, 26),
                "url": "https://seekingalpha.com/article/A1",
                "article_type": "analysis",
                "comments_count": 47,
                "summary_excerpt": "Body excerpt",
                "body_missing": False,
            },
            {
                "article_id": "AID2",
                "title": "Quick note",
                "author": "Anlyst B",
                "published_date": date(2026, 4, 20),
                "url": "https://seekingalpha.com/article/A2",
                "article_type": "note",
                "comments_count": 5,
                "summary_excerpt": "Quick note",
                "body_missing": True,
            },
        ]
        _stub_fetch_dicts(monkeypatch, {"sa_articles\n": rows})
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="NVDA")

        assert len(out["recent_articles"]) == 2
        a0 = out["recent_articles"][0]
        assert a0["article_id"] == "AID1"
        assert a0["published_date"] == "2026-04-26"
        assert a0["url"] == "https://seekingalpha.com/article/A1"
        assert a0["comments_count"] == 47
        assert "body_missing" not in a0  # internal-only flag stripped
        # body_missing on row 2 → reflected in data_quality.missing
        missing = out["data_quality"]["missing"]
        assert any("body_markdown" in m for m in missing)

    def test_news_normalization(self, monkeypatch):
        _enable_sa(monkeypatch)
        rows = [
            {
                "news_id": "N1",
                "title": "Earnings beat",
                "url": "https://seekingalpha.com/news/N1",
                "published_at": datetime(2026, 4, 25, 13, 30, tzinfo=timezone.utc),
                "tickers": ["NVDA", "AMD"],
                "category": "earnings",
                "comments_count": 89,
                "summary_excerpt": "Beat top + bottom",
            }
        ]
        _stub_fetch_dicts(monkeypatch, {"sa_market_news": rows})
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="NVDA")
        n0 = out["high_discussion_news"][0]
        assert n0["news_id"] == "N1"
        assert n0["tickers"] == ["NVDA", "AMD"]
        assert n0["published_at"].startswith("2026-04-25T")
        assert n0["comments_count"] == 89


# ---------------------------------------------------------------------------
# 8-10: comments split / cap / verification flag
# ---------------------------------------------------------------------------


class TestCommentsSplitAndCaps:
    def test_split_ticker_vs_candidate(self, monkeypatch):
        _enable_sa(monkeypatch)
        rows = [
            {
                "comment_row_id": 1, "article_id": "A1", "comment_id": "c1",
                "commenter": "u1", "upvotes": 4,
                "comment_date": datetime(2026, 4, 25, 19, 42, tzinfo=timezone.utc),
                "preview": "great earnings call",
                "high_value_score": 6.5,
                "ticker_mentions": ["NVDA"], "candidate_mentions": [],
                "keyword_buckets": {"earnings": ["earnings", "guidance"]},
                "needs_verification": False,
                "article_url": "https://seekingalpha.com/article/A1",
                "mention_kind": "ticker",
                "rn_per_article": 1, "rn_per_kind": 1,
            },
            {
                "comment_row_id": 2, "article_id": "A2", "comment_id": "c2",
                "commenter": "u2", "upvotes": 2,
                "comment_date": datetime(2026, 4, 24, 9, 0, tzinfo=timezone.utc),
                "preview": "I hear NVDA might miss",
                "high_value_score": 5.0,
                "ticker_mentions": [], "candidate_mentions": ["NVDA"],
                "keyword_buckets": {"hedging": ["hear", "might"]},
                "needs_verification": True,
                "article_url": None,
                "mention_kind": "candidate",
                "rn_per_article": 1, "rn_per_kind": 1,
            },
        ]
        _stub_fetch_dicts(monkeypatch, {"sa_comment_signals": rows})
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="NVDA")

        ticker_list = out["high_value_comments"]["ticker_mentions"]
        candidate_list = out["high_value_comments"]["candidate_mentions"]
        assert len(ticker_list) == 1 and ticker_list[0]["comment_id"] == "c1"
        assert len(candidate_list) == 1 and candidate_list[0]["comment_id"] == "c2"
        # internal SQL-only columns stripped
        assert "mention_kind" not in ticker_list[0]
        assert "rn_per_kind" not in ticker_list[0]

    def test_needs_verification_passthrough(self, monkeypatch):
        _enable_sa(monkeypatch)
        rows = [
            {
                "comment_row_id": 1, "article_id": "A1", "comment_id": "c1",
                "commenter": "u1", "upvotes": 0,
                "comment_date": datetime(2026, 4, 25, tzinfo=timezone.utc),
                "preview": "rumor: NVDA might miss guidance",
                "high_value_score": 5.5,
                "ticker_mentions": ["NVDA"], "candidate_mentions": [],
                "keyword_buckets": {},
                "needs_verification": True,
                "article_url": "https://x/A1",
                "mention_kind": "ticker",
                "rn_per_article": 1, "rn_per_kind": 1,
            }
        ]
        _stub_fetch_dicts(monkeypatch, {"sa_comment_signals": rows})
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="NVDA")
        kept = out["high_value_comments"]["ticker_mentions"]
        assert len(kept) == 1
        assert kept[0]["needs_verification"] is True

    def test_keyword_buckets_shape_preserved(self, monkeypatch):
        """Stage 1 stores Dict[str, List[str]]; tool must NOT collapse to counts."""
        _enable_sa(monkeypatch)
        rows = [
            {
                "comment_row_id": 1, "article_id": "A1", "comment_id": "c1",
                "commenter": "u", "upvotes": 0,
                "comment_date": datetime(2026, 4, 25, tzinfo=timezone.utc),
                "preview": "", "high_value_score": 4.5,
                "ticker_mentions": ["NVDA"], "candidate_mentions": [],
                "keyword_buckets": {"earnings": ["earnings", "guidance"], "macro": ["fed"]},
                "needs_verification": False,
                "article_url": "x",
                "mention_kind": "ticker",
                "rn_per_article": 1, "rn_per_kind": 1,
            }
        ]
        _stub_fetch_dicts(monkeypatch, {"sa_comment_signals": rows})
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="NVDA")
        kept = out["high_value_comments"]["ticker_mentions"][0]
        assert kept["keyword_buckets"] == {
            "earnings": ["earnings", "guidance"], "macro": ["fed"],
        }


# ---------------------------------------------------------------------------
# 11: excerpt truncation
# ---------------------------------------------------------------------------


class TestExcerpt:
    def test_long_excerpt_marked_truncated(self, monkeypatch):
        _enable_sa(monkeypatch)
        long_text = "x" * (EXCERPT_LEN + 100)
        rows = [
            {
                "article_id": "A", "title": "T", "author": "U",
                "published_date": date(2026, 4, 25),
                "url": "x", "article_type": "analysis",
                "comments_count": 0,
                "summary_excerpt": long_text[:EXCERPT_LEN],  # SQL already truncates
                "body_missing": False,
            }
        ]
        _stub_fetch_dicts(monkeypatch, {"sa_articles\n": rows})
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="NVDA")
        excerpt = out["recent_articles"][0]["summary_excerpt"]
        assert excerpt.endswith("...")

    def test_short_excerpt_no_marker(self, monkeypatch):
        _enable_sa(monkeypatch)
        rows = [
            {
                "article_id": "A", "title": "Short", "author": "U",
                "published_date": date(2026, 4, 25),
                "url": "x", "article_type": "analysis",
                "comments_count": 0,
                "summary_excerpt": "Short body",
                "body_missing": False,
            }
        ]
        _stub_fetch_dicts(monkeypatch, {"sa_articles\n": rows})
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="NVDA")
        assert out["recent_articles"][0]["summary_excerpt"] == "Short body"


# ---------------------------------------------------------------------------
# 12-13: data_quality + source_notes
# ---------------------------------------------------------------------------


class TestDataQualityAndSourceNotes:
    def test_data_quality_rows_always_present(self, monkeypatch):
        _enable_sa(monkeypatch)
        _stub_fetch_dicts(monkeypatch, {})  # all sources return empty
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="NVDA")
        rows = out["data_quality"]["rows"]
        assert rows == {
            "articles": 0, "news": 0, "comments_ticker": 0, "comments_candidate": 0,
        }
        # Empty sources each get a per-source note, plus the disclaimer
        notes = " ".join(out["source_notes"])
        assert "No articles" in notes
        assert "No high-discussion news" in notes
        assert "No high-value comments" in notes

    def test_source_notes_disclaimer_and_window(self, monkeypatch):
        _enable_sa(monkeypatch)
        _stub_fetch_dicts(monkeypatch, {})
        out = get_sa_digest(
            dal=_dal_with(_fake_backend()), ticker="NVDA",
            days=21, max_articles=3, max_news=4, max_comments=6,
            min_comment_score=5.0,
        )
        notes_text = "\n".join(out["source_notes"])
        # Window + caps
        assert "21d back" in notes_text
        assert "cap 3" in notes_text and "cap 4" in notes_text
        assert f"<= {PER_ARTICLE_COMMENT_CAP} per article" in notes_text
        assert "<= 6 per mention kind" in notes_text
        assert "high_value_score >= 5.0" in notes_text
        # Opinion disclaimer
        assert "investor opinion" in notes_text
        assert "not fact" in notes_text
        # News gate documented
        assert f">= {NEWS_DISCUSSION_GATE} comments" in notes_text or \
               f">= {NEWS_DISCUSSION_GATE}, ordered" in notes_text


# ---------------------------------------------------------------------------
# 14: per-source failure isolation
# ---------------------------------------------------------------------------


class TestPerSourceFailure:
    def test_articles_failure_does_not_blank_other_sources(self, monkeypatch):
        _enable_sa(monkeypatch)
        news_rows = [
            {
                "news_id": "N1", "title": "ok", "url": "u",
                "published_at": datetime(2026, 4, 25, tzinfo=timezone.utc),
                "tickers": ["NVDA"], "category": "x", "comments_count": 50,
                "summary_excerpt": "...",
            }
        ]
        _stub_fetch_dicts(
            monkeypatch,
            {
                "FROM sa_articles\n": RuntimeError("boom"),
                "sa_market_news": news_rows,
            },
        )
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="NVDA")
        assert out["recent_articles"] == []
        assert any("articles:" in e for e in out["data_quality"]["errors"])
        # News still populates
        assert len(out["high_discussion_news"]) == 1


# ---------------------------------------------------------------------------
# 15: missing flags
# ---------------------------------------------------------------------------


class TestMissingFlags:
    def test_article_url_missing_appended(self, monkeypatch):
        _enable_sa(monkeypatch)
        rows = [
            {
                "comment_row_id": 1, "article_id": "A1", "comment_id": "c1",
                "commenter": "u", "upvotes": 0,
                "comment_date": datetime(2026, 4, 25, tzinfo=timezone.utc),
                "preview": "x", "high_value_score": 4.5,
                "ticker_mentions": ["NVDA"], "candidate_mentions": [],
                "keyword_buckets": {},
                "needs_verification": False,
                "article_url": None,           # parent pruned
                "mention_kind": "ticker",
                "rn_per_article": 1, "rn_per_kind": 1,
            }
        ]
        _stub_fetch_dicts(monkeypatch, {"sa_comment_signals": rows})
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="NVDA")
        missing = out["data_quality"]["missing"]
        assert any("article_url" in m for m in missing)


# ---------------------------------------------------------------------------
# 16: serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_returns_json_serializable(self, monkeypatch):
        _enable_sa(monkeypatch)
        article_rows = [
            {
                "article_id": "A1", "title": "T",
                "author": "U", "published_date": date(2026, 4, 25),
                "url": "x", "article_type": "analysis",
                "comments_count": 12, "summary_excerpt": "...",
                "body_missing": False,
            }
        ]
        news_rows = [
            {
                "news_id": "N1", "title": "ok", "url": "u",
                "published_at": datetime(2026, 4, 25, tzinfo=timezone.utc),
                "tickers": ["NVDA"], "category": "x",
                "comments_count": 50, "summary_excerpt": "...",
            }
        ]
        comment_rows = [
            {
                "comment_row_id": 1, "article_id": "A1", "comment_id": "c1",
                "commenter": "u", "upvotes": 0,
                "comment_date": datetime(2026, 4, 25, tzinfo=timezone.utc),
                "preview": "x", "high_value_score": 4.5,
                "ticker_mentions": ["NVDA"], "candidate_mentions": [],
                "keyword_buckets": {"earnings": ["earnings"]},
                "needs_verification": False,
                "article_url": "u",
                "mention_kind": "ticker",
                "rn_per_article": 1, "rn_per_kind": 1,
            }
        ]
        _stub_fetch_dicts(
            monkeypatch,
            {
                "FROM sa_articles\n": article_rows,
                "sa_market_news": news_rows,
                "sa_comment_signals": comment_rows,
            },
        )
        out = get_sa_digest(dal=_dal_with(_fake_backend()), ticker="nvda")
        # ticker uppercasing ensured at output level
        assert out["ticker"] == "NVDA"
        # Round-trip through json without errors
        json.dumps(out)


# ---------------------------------------------------------------------------
# Bonus: ticker uppercasing reaches SQL params
# ---------------------------------------------------------------------------


class TestTickerUppercase:
    def test_lowercase_input_passes_uppercase_to_sql(self, monkeypatch):
        _enable_sa(monkeypatch)
        captured = []

        def fake(backend, sql, params):
            captured.append(params.get("ticker"))
            return []

        monkeypatch.setattr(sd, "_fetch_dicts", fake)
        get_sa_digest(dal=_dal_with(_fake_backend()), ticker="nvda")
        # Three sources were queried (articles, news, comments)
        assert captured  # at least one
        assert all(t == "NVDA" for t in captured)