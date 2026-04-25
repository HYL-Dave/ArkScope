"""Tests for SA comment signal extraction (Stage 1, rule-based).

Covers:
  - empty / whitespace input
  - ticker / candidate split based on universe membership
  - single-letter tickers only via $X / (X), never bare
  - stopwords filter (universe wins over stopword)
  - keyword bucket detection (stores matched terms, not just bucket flag)
  - external link bonus
  - upvote bonus is logarithmic
  - score clamped to 10.0
  - needs_verification = hedge + concrete claim
  - rule_set_version threaded through
"""

from __future__ import annotations

import pytest

from src.sa.comment_signals import (
    COMMON_STOPWORDS,
    KEYWORD_BUCKETS,
    RULE_SET_VERSION,
    CommentSignalExtractor,
    CommentSignals,
)


def _ext(universe=("NVDA", "AMD", "B")):
    return CommentSignalExtractor(universe=universe)


# ---------------------------------------------------------------------------
# Empty / whitespace
# ---------------------------------------------------------------------------


def test_empty_string_returns_empty_signals():
    sig = _ext().extract("")
    assert sig.is_empty()
    assert sig.rule_set_version == RULE_SET_VERSION


def test_whitespace_returns_empty_signals():
    sig = _ext().extract("   \n  \t ")
    assert sig.is_empty()


# ---------------------------------------------------------------------------
# Ticker classification
# ---------------------------------------------------------------------------


def test_universe_ticker_extracted_as_mention():
    sig = _ext().extract("I'm bullish on NVDA going into earnings")
    assert sig.ticker_mentions == ["NVDA"]
    assert sig.candidate_mentions == []


def test_off_universe_token_goes_to_candidate():
    sig = _ext().extract("Looking at XYZ for a swing trade")
    assert sig.ticker_mentions == []
    assert sig.candidate_mentions == ["XYZ"]


def test_universe_ticker_overrides_stopword():
    """If the user trusts AI as a ticker, stopword rule must NOT block it."""
    extractor = CommentSignalExtractor(universe=("NVDA", "AI"))
    sig = extractor.extract("AI keeps making new highs")
    assert "AI" in sig.ticker_mentions


def test_stopword_not_in_universe_is_dropped():
    sig = _ext().extract("ETF flows are strong this week, AI hype too")
    assert sig.ticker_mentions == []
    # ETF and AI are stopwords, not in universe → not even candidates.
    assert "ETF" not in sig.candidate_mentions
    assert "AI" not in sig.candidate_mentions


def test_pronoun_i_never_matches():
    sig = _ext().extract("I think I should buy more")
    assert sig.ticker_mentions == []
    assert sig.candidate_mentions == []


def test_single_letter_only_via_dollar_form():
    """Bare 'B' must NOT match (single char). $B should classify as ticker."""
    ext = _ext()  # universe includes 'B'
    sig_bare = ext.extract("B is interesting today")
    assert "B" not in sig_bare.ticker_mentions
    assert "B" not in sig_bare.candidate_mentions

    sig_dollar = ext.extract("$B is interesting today")
    assert sig_dollar.ticker_mentions == ["B"]


def test_single_letter_paren_form_off_universe_is_candidate():
    extractor = CommentSignalExtractor(universe=("NVDA",))
    sig = extractor.extract("Looking at (B) for a long entry")
    # B not in universe → candidate (single-letter explicit form is intentional)
    assert sig.candidate_mentions == ["B"]


def test_multiple_tickers_and_candidates():
    sig = _ext().extract("NVDA up, AMD steady, ABCD pumping, XYZ next?")
    assert sig.ticker_mentions == ["AMD", "NVDA"]
    assert sig.candidate_mentions == ["ABCD", "XYZ"]


def test_dollar_and_bare_dedupe():
    sig = _ext().extract("$NVDA NVDA $NVDA")
    assert sig.ticker_mentions == ["NVDA"]


# ---------------------------------------------------------------------------
# Keyword buckets
# ---------------------------------------------------------------------------


def test_earnings_bucket_stores_matched_terms():
    sig = _ext().extract("NVDA earnings beat consensus estimate")
    bucket = sig.keyword_buckets.get("earnings", [])
    assert "earnings" in bucket
    assert "consensus estimate" in bucket


def test_rating_change_bucket():
    sig = _ext().extract("Got a downgrade today, hold rating from analyst")
    rc = sig.keyword_buckets.get("rating_change", [])
    assert "downgrade" in rc
    assert "hold rating" in rc


def test_eligibility_bucket():
    sig = _ext().extract("Concerned about ADR eligibility and 180d hold limit")
    e = sig.keyword_buckets.get("eligibility", [])
    assert "adr" in e
    assert "180d" in e or "hold limit" in e


def test_no_buckets_when_chitchat():
    sig = _ext().extract("just saying hi to everyone here")
    assert sig.keyword_buckets == {}


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------


def test_chitchat_scores_zero():
    sig = _ext().extract("nice weather today")
    assert sig.high_value_score == 0.0


def test_score_increases_with_ticker_and_bucket():
    sig = _ext().extract("NVDA earnings beat — strong buy from analyst")
    # Has 1 ticker, multiple bucket terms → score should be > 0
    assert sig.high_value_score > 1.0


def test_external_link_adds_bonus():
    text_no_link = "NVDA earnings"
    text_with_link = "NVDA earnings https://example.com/article"
    s_no = _ext().extract(text_no_link).high_value_score
    s_yes = _ext().extract(text_with_link).high_value_score
    assert s_yes > s_no
    assert s_yes - s_no >= 1.5  # link adds 2.0


def test_upvotes_have_logarithmic_effect():
    text = "NVDA earnings beat"
    s_low = _ext().extract(text, upvotes=0).high_value_score
    s_mid = _ext().extract(text, upvotes=10).high_value_score
    s_high = _ext().extract(text, upvotes=1000).high_value_score
    assert s_mid > s_low
    assert s_high > s_mid
    # Logarithmic: 10x more upvotes does NOT yield 10x score boost.
    boost_low_to_mid = s_mid - s_low
    boost_mid_to_high = s_high - s_mid
    assert boost_mid_to_high < boost_low_to_mid * 5  # generous bound


def test_score_caps_at_ten():
    very_loaded = (
        "NVDA AMD earnings beat upgrade strong buy ADR market cap "
        "FDA contract acquisition merger https://x.com https://y.com"
    )
    sig = _ext().extract(very_loaded, upvotes=10000)
    assert sig.high_value_score == 10.0


# ---------------------------------------------------------------------------
# needs_verification
# ---------------------------------------------------------------------------


def test_needs_verification_requires_hedge_and_claim():
    # Hedge alone, no claim → False
    s = _ext().extract("might be wrong about everything")
    assert s.needs_verification is False

    # Claim alone, no hedge → False
    s = _ext().extract("NVDA earnings beat consensus")
    assert s.needs_verification is False

    # Both → True
    s = _ext().extract("hearing NVDA might beat earnings this quarter")
    assert s.needs_verification is True


def test_needs_verification_chinese_hedge():
    s = _ext().extract("据说 NVDA 下季度 earnings 会超预期")
    assert s.needs_verification is True


# ---------------------------------------------------------------------------
# Real-world-flavoured fixtures
# ---------------------------------------------------------------------------


def test_alpha_picks_radar_post():
    """The wid1990 weekly radar style post — high info density."""
    text = (
        "🔥 Weekly AP Quant Radar — Technical Focus List "
        "[AP-Clock - Near 180d Hold Limit]: NONE "
        "Add / Momentum Leaders LITE | ADD | strong buy | "
        "earnings May 5"
    )
    extractor = CommentSignalExtractor(universe=("LITE",))
    sig = extractor.extract(text)
    assert "LITE" in sig.ticker_mentions
    assert "earnings" in sig.keyword_buckets.get("earnings", [])
    assert "strong buy" in sig.keyword_buckets.get("rating_change", [])
    assert "180d" in sig.keyword_buckets.get("eligibility", []) or \
           "hold limit" in sig.keyword_buckets.get("eligibility", [])
    assert sig.high_value_score > 3.0


def test_chatty_filler_post():
    text = "Oh and by the way I have an android phone and using the app"
    sig = _ext().extract(text)
    assert sig.ticker_mentions == []
    assert sig.candidate_mentions == []
    assert sig.keyword_buckets == {}
    assert sig.high_value_score == 0.0
    assert sig.needs_verification is False


def test_dividend_query():
    text = "@VincentD.2000 It's payable on April 27th to shareholders of record as of April 17th."
    sig = _ext().extract(text)
    # No ticker mentions, no bucket matches → score 0
    assert sig.high_value_score == 0.0


# ---------------------------------------------------------------------------
# Rule set version
# ---------------------------------------------------------------------------


def test_rule_set_version_is_threaded_through():
    extractor = CommentSignalExtractor(universe=("NVDA",), rule_set_version="v1.1-test")
    sig = extractor.extract("NVDA earnings")
    assert sig.rule_set_version == "v1.1-test"


def test_default_rule_set_version_is_current():
    from src.sa.comment_signals import RULE_SET_VERSION
    sig = _ext().extract("NVDA")
    assert sig.rule_set_version == RULE_SET_VERSION
    assert sig.rule_set_version.startswith("v1.")


# ---------------------------------------------------------------------------
# Dot-suffix tickers (BRK.B, BF.A, etc.)
# ---------------------------------------------------------------------------


def test_dot_ticker_dollar_form():
    extractor = CommentSignalExtractor(universe=("BRK.B", "NVDA"))
    sig = extractor.extract("$BRK.B earnings beat consensus")
    assert "BRK.B" in sig.ticker_mentions
    assert "BRK" not in sig.candidate_mentions  # must not split on the dot


def test_dot_ticker_paren_form():
    extractor = CommentSignalExtractor(universe=("BRK.B",))
    sig = extractor.extract("Berkshire (BRK.B) outperformed")
    assert sig.ticker_mentions == ["BRK.B"]


def test_dot_ticker_bare_form():
    extractor = CommentSignalExtractor(universe=("BRK.B", "BF.A"))
    sig = extractor.extract("BRK.B and BF.A both quality compounders")
    assert "BRK.B" in sig.ticker_mentions
    assert "BF.A" in sig.ticker_mentions


def test_dot_ticker_off_universe_is_candidate():
    extractor = CommentSignalExtractor(universe=("NVDA",))
    sig = extractor.extract("Watching $XYZ.A")
    assert "XYZ.A" in sig.candidate_mentions
    assert sig.ticker_mentions == []


# ---------------------------------------------------------------------------
# "May" hedge handling
# ---------------------------------------------------------------------------


def test_may_as_month_does_not_trigger_verification():
    extractor = CommentSignalExtractor(universe=("LITE",))
    sig = extractor.extract("LITE earnings May 5 — buying ahead")
    # "May 5" is a date, should not be a hedge
    assert sig.needs_verification is False
    assert "LITE" in sig.ticker_mentions


def test_may_with_ordinal_date_not_hedge():
    extractor = CommentSignalExtractor(universe=("NVDA",))
    sig = extractor.extract("NVDA report May 12th")
    assert sig.needs_verification is False


def test_may_as_modal_verb_is_hedge():
    extractor = CommentSignalExtractor(universe=("NVDA",))
    sig = extractor.extract("NVDA may beat earnings this quarter")
    # "may" not followed by a date → modal verb hedge
    assert sig.needs_verification is True


def test_hedge_substring_match_does_not_fire_on_unrelated_word():
    """'mayor' must NOT match the 'may' hedge."""
    extractor = CommentSignalExtractor(universe=("NVDA",))
    sig = extractor.extract("NVDA earnings — the mayor of nowhere")
    assert sig.needs_verification is False


def test_hedge_word_boundary_for_might():
    """Verify regex respects word boundaries for ASCII hedges."""
    extractor = CommentSignalExtractor(universe=("NVDA",))
    sig = extractor.extract("NVDA might beat next quarter")
    assert sig.needs_verification is True

    # 'mighty' must not match 'might'
    sig2 = extractor.extract("NVDA had a mighty rally")
    assert sig2.needs_verification is False


def test_chinese_hedges_still_work():
    """Chinese hedges have no word boundary, substring match retained."""
    extractor = CommentSignalExtractor(universe=("NVDA",))
    sig = extractor.extract("据说 NVDA 下季度 earnings 会超预期")
    assert sig.needs_verification is True


# ---------------------------------------------------------------------------
# Backfill: max_extracted enforced inside the row loop
# ---------------------------------------------------------------------------


def test_backfill_max_extracted_caps_inside_batch():
    """max_extracted=3 with batch_size=10 must stop at row 3, not row 10."""
    from unittest.mock import MagicMock, patch
    from src.sa.comment_signal_backfill import run_backfill

    # Fake DAL with DatabaseBackend-shaped backend
    dal = MagicMock()
    backend = MagicMock()
    conn = MagicMock()
    backend._get_conn.return_value = conn
    dal._backend = backend
    # No watchlist / alpha picks
    dal.get_watchlist.return_value = MagicMock(tickers=[])

    # Build a stream of fake batch rows (10 per batch, 3 batches available)
    rows_per_batch = [
        [
            (i, f"art-{i}", f"cm-{i}", f"NVDA earnings update #{i}", 0)
            for i in range(1, 11)
        ],
        [
            (i, f"art-{i}", f"cm-{i}", f"AMD beat #{i}", 0)
            for i in range(11, 21)
        ],
        [],  # exhausted
    ]
    cursors = []

    def cursor_factory(**_kwargs):
        cur = MagicMock()
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        cursors.append(cur)
        return cur

    conn.cursor.side_effect = cursor_factory

    # First call: alpha picks SELECT (universe build) → empty
    # Second call: count pending → 30
    # Third call: fetch first batch → rows
    # ... etc. The pattern is loose; we control fetchone/fetchall via side_effect.
    fetchone_results = iter([
        (30,),  # count_pending
    ])
    fetchall_results = iter([
        [],            # alpha picks SELECT (universe)
        rows_per_batch[0],
        rows_per_batch[1],
        rows_per_batch[2],
    ])

    def make_cursor():
        cur = MagicMock()
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        cur.fetchone.side_effect = lambda: next(fetchone_results, None)
        cur.fetchall.side_effect = lambda: next(fetchall_results, [])
        cur.execute = MagicMock()
        return cur

    conn.cursor.side_effect = lambda *a, **k: make_cursor()

    result = run_backfill(dal, batch_size=10, max_extracted=3)
    # Cap must apply inside the batch — only 3 rows extracted, not 10.
    assert result["extracted_count"] == 3