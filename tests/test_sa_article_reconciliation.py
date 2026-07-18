from __future__ import annotations

from src.sa_article_reconciliation import (
    ArticleEvidence,
    PickEvent,
    decide_reconciliation,
    evaluate_candidate,
    normalize_symbol,
    parse_alpha_picks_article_id,
)


BTSG_TITLE = "Stock Buy: Top Health Care Services Stock Delivers Double-Digit Growth"
BTSG_COMPANY = "BrightSpring Health Services, Inc."


def _event(
    *,
    symbol: str = "BTSG",
    company: str = BTSG_COMPANY,
    role: str = "entry",
    anchor: str | None = "2026-07-15",
) -> PickEvent:
    return PickEvent(1, symbol, company, role, anchor)


def _article(
    article_id: str = "6316639",
    *,
    published: str | None = "2026-07-15",
    title: str = BTSG_TITLE,
    body: str | None = None,
    article_type: str | None = "analysis",
    list_ticker: str | None = "BTSG",
    detail_ticker: str | None = None,
    has_content: bool = False,
) -> ArticleEvidence:
    return ArticleEvidence(
        article_id,
        published,
        title,
        body,
        article_type,
        list_ticker,
        detail_ticker,
        has_content,
    )


def test_normalize_symbol_is_trim_upper_only_and_preserves_provider_punctuation():
    assert normalize_symbol(" brk.b ") == "BRK.B"
    assert normalize_symbol("  ") is None
    assert normalize_symbol(None) is None
    assert normalize_symbol("RDS/A") == "RDS/A"


def test_canonical_alpha_picks_url_parser_rejects_wrong_hosts_paths_and_non_digits():
    assert parse_alpha_picks_article_id(
        "https://seekingalpha.com/alpha-picks/articles/6316639-stock-buy"
    ) == "6316639"
    assert parse_alpha_picks_article_id(
        "https://seekingalpha.com/alpha-picks/articles/6316639"
    ) == "6316639"
    for value in (
        "http://seekingalpha.com/alpha-picks/articles/6316639-stock-buy",
        "https://www.seekingalpha.com/alpha-picks/articles/6316639-stock-buy",
        "https://evil.example/alpha-picks/articles/6316639-stock-buy",
        "https://seekingalpha.com/article/6316639-stock-buy",
        "https://seekingalpha.com/alpha-picks/articles/not-digits",
        "https://seekingalpha.com/alpha-picks/articles/6316639?source=test",
        "",
    ):
        assert parse_alpha_picks_article_id(value) is None, value


def test_date_bands_are_exact_near_outside_or_missing():
    cases = (
        ("2026-07-15", "exact", 0),
        ("2026-07-16", "near", 1),
        ("2026-07-18", "near", 3),
        ("2026-07-19", "outside", 4),
        (None, "missing", None),
        ("not-a-date", "missing", None),
    )
    for published, band, distance in cases:
        result = evaluate_candidate(_event(), _article(published=published))
        assert (result.date_band, result.date_distance_days) == (band, distance)
    missing_anchor = evaluate_candidate(_event(anchor=None), _article())
    assert (missing_anchor.date_band, missing_anchor.date_distance_days) == ("missing", None)


def test_exact_list_ticker_and_entry_phrase_is_auto_eligible():
    decision = decide_reconciliation(
        PickEvent(1, "BTSG", BTSG_COMPANY, "entry", "2026-07-15"),
        [ArticleEvidence(
            "6316639", "2026-07-15", BTSG_TITLE,
            None, "analysis", "BTSG", None, False,
        )],
    )
    assert decision.accepted_article_id == "6316639"
    assert decision.candidates[0].strength == 3
    assert decision.candidates[0].evidence_codes == (
        "date_exact", "ticker_list_exact", "role_entry_strong",
    )


def test_exact_detail_ticker_is_independent_of_generic_title_and_body():
    result = evaluate_candidate(
        _event(),
        _article(
            title="Top Health Care Services Stock Delivers Double-Digit Growth",
            body="The Alpha Picks team issued a Stock Buy after its review.",
            list_ticker=None,
            detail_ticker="BTSG",
            has_content=True,
        ),
    )
    assert result.auto_eligible is True
    assert result.strength == 3
    assert result.evidence_codes == (
        "date_exact", "ticker_detail_exact", "role_entry_strong",
    )


def test_matching_list_and_detail_tickers_retain_both_provenance_codes():
    result = evaluate_candidate(_event(), _article(detail_ticker="BTSG"))
    assert result.auto_eligible is True
    assert result.evidence_codes == (
        "date_exact",
        "ticker_list_exact",
        "ticker_detail_exact",
        "role_entry_strong",
    )


def test_list_detail_ticker_conflict_is_review_only():
    result = evaluate_candidate(
        _event(),
        _article(list_ticker="BTSG", detail_ticker="AGX"),
    )
    assert result.auto_eligible is False
    assert result.strength == 0
    assert result.reason_code == "ticker_metadata_conflict"
    assert result.evidence_codes == ("ticker_metadata_conflict",)


def test_within_three_days_requires_explicit_ticker_and_strong_role_phrase():
    valid = evaluate_candidate(_event(), _article(published="2026-07-18"))
    assert valid.auto_eligible is True
    assert valid.strength == 2
    assert valid.evidence_codes == (
        "date_near", "ticker_list_exact", "role_entry_strong",
    )
    for candidate in (
        _article(published="2026-07-18", list_ticker=None),
        _article(published="2026-07-18", title="BTSG quarterly analysis"),
    ):
        result = evaluate_candidate(_event(), candidate)
        assert result.auto_eligible is False
        assert result.strength == 0


def test_four_days_never_auto_accepts():
    result = evaluate_candidate(_event(), _article(published="2026-07-19"))
    assert result.date_band == "outside"
    assert result.auto_eligible is False
    assert result.strength == 0
    assert result.reason_code == "outside_date_window"


def test_fallback_symbol_or_full_company_mention_requires_exact_date_and_role():
    symbol_result = evaluate_candidate(
        _event(),
        _article(title="Stock Buy: BTSG joins Alpha Picks", list_ticker=None),
    )
    company_result = evaluate_candidate(
        _event(),
        _article(
            title="Stock Buy: a health care services leader",
            body=f"Our new selection is {BTSG_COMPANY}.",
            list_ticker=None,
            has_content=True,
        ),
    )
    assert symbol_result.strength == company_result.strength == 1
    assert symbol_result.auto_eligible is company_result.auto_eligible is True
    assert "ticker_text_symbol" in symbol_result.evidence_codes
    assert "ticker_text_company" in company_result.evidence_codes

    for candidate in (
        _article(
            published="2026-07-16",
            title="Stock Buy: BTSG joins Alpha Picks",
            list_ticker=None,
        ),
        _article(title="BTSG quarterly analysis", list_ticker=None),
    ):
        result = evaluate_candidate(_event(), candidate)
        assert result.strength == 0
        assert result.auto_eligible is False


def test_article_type_and_ticker_prefix_cannot_supply_missing_identity_legs():
    for article_type in ("analysis", "commentary"):
        result = evaluate_candidate(
            _event(),
            _article(
                title="Quarterly portfolio review",
                article_type=article_type,
                list_ticker="BTSG-OLD",
            ),
        )
        assert result.strength == 0
        assert result.auto_eligible is False
        assert "ticker_list_exact" not in result.evidence_codes


def test_same_strength_tie_remains_unresolved_despite_article_id_order():
    decision = decide_reconciliation(
        _event(),
        [_article("20"), _article("10")],
    )
    assert decision.accepted_article_id is None
    assert decision.reason_code == "ambiguous_candidates"
    assert [row.article_id for row in decision.candidates] == ["10", "20"]
    assert {row.strength for row in decision.candidates} == {3}


def test_rejected_candidate_is_not_proposed_again():
    decision = decide_reconciliation(
        _event(),
        [_article("10"), _article("20"), _article("30")],
        rejected_article_ids={"10"},
    )
    assert decision.accepted_article_id is None
    assert decision.reason_code == "ambiguous_candidates"
    assert [row.article_id for row in decision.candidates] == ["20", "30"]


def test_entry_and_exit_use_their_supplied_event_anchor_without_role_substitution():
    entry = evaluate_candidate(
        _event(role="entry", anchor="2026-07-15"),
        _article(published="2026-07-15", title="Stock Buy: BTSG", list_ticker="BTSG"),
    )
    exit_result = evaluate_candidate(
        _event(role="exit", anchor="2026-07-20"),
        _article(published="2026-07-20", title="Stock Sell: BTSG", list_ticker="BTSG"),
    )
    wrong_exit_anchor = evaluate_candidate(
        _event(role="exit", anchor="2026-07-20"),
        _article(published="2026-07-15", title="Stock Sell: BTSG", list_ticker="BTSG"),
    )
    assert entry.date_band == exit_result.date_band == "exact"
    assert entry.strength == exit_result.strength == 3
    assert wrong_exit_anchor.date_band == "outside"
    assert wrong_exit_anchor.strength == 0


def test_unreviewed_agx_locking_gains_title_is_not_invented_as_entry_or_exit():
    article = _article(
        title="AGX: Locking In Additional Gains",
        list_ticker="AGX",
        published="2026-07-17",
    )
    for role in ("entry", "exit"):
        result = evaluate_candidate(
            _event(symbol="AGX", company="Argan, Inc.", role=role, anchor="2026-07-17"),
            article,
        )
        assert result.strength == 0
        assert result.auto_eligible is False
        assert result.reason_code == "role_phrase_missing"
