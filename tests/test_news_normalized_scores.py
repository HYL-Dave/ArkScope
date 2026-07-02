import pytest

from src.news_normalized.scores import (
    latest_score_cte,
    normalize_reasoning_effort,
    normalize_score_model,
    normalize_score_type,
    score_key,
)


def test_normalize_score_model_matches_parquet_column_style():
    assert normalize_score_model("gpt-5.2") == "gpt_5_2"
    assert normalize_score_model(" GPT 5.2 ") == "gpt_5_2"
    assert normalize_score_model("o4-mini") == "o4_mini"
    with pytest.raises(ValueError):
        normalize_score_model(None)
    with pytest.raises(ValueError):
        normalize_score_model("  ")


def test_normalize_reasoning_effort_keeps_null_as_empty_string():
    assert normalize_reasoning_effort(None) == ""
    assert normalize_reasoning_effort("") == ""
    assert normalize_reasoning_effort(" HIGH ") == "high"
    assert normalize_reasoning_effort("xHigh") == "xhigh"


def test_score_key_normalizes_type_model_and_effort():
    assert score_key(42, "Sentiment", "gpt-5.2", " HIGH ") == (
        42,
        "sentiment",
        "gpt_5_2",
        "high",
    )
    assert normalize_score_type("risk") == "risk"
    with pytest.raises(ValueError):
        normalize_score_type("quality")


def test_latest_score_cte_encodes_deterministic_tiebreakers():
    sql = latest_score_cte("sentiment", alias="latest_sentiment")

    assert "latest_sentiment" in sql
    assert "score_type = 'sentiment'" in sql
    assert "ROW_NUMBER()" in sql
    assert "ORDER BY scored_at DESC, model DESC, reasoning_effort DESC" in sql


def test_latest_score_cte_can_filter_model():
    sql = latest_score_cte("risk", alias="latest_risk", model="gpt-5.2")

    assert "score_type = 'risk'" in sql
    assert "model = 'gpt_5_2'" in sql
