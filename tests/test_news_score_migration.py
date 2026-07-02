from src.news_normalized.score_migration import (
    ScoreSourceRow,
    build_score_migration_plan,
)


def _row(
    legacy_news_id=10,
    score_type="sentiment",
    model="gpt-5.2",
    effort="HIGH",
    score=4.0,
    scored_at="2026-07-01T00:00:00Z",
):
    return ScoreSourceRow(
        legacy_news_id=legacy_news_id,
        score_type=score_type,
        model=model,
        reasoning_effort=effort,
        score=score,
        scored_at=scored_at,
    )


def test_mapped_pg_score_becomes_local_score_row():
    plan = build_score_migration_plan([_row()], {10: 42})

    assert plan.source_rows == 1
    assert plan.mapped_rows == 1
    assert plan.unmapped_rows == 0
    assert len(plan.rows) == 1
    migrated = plan.rows[0]
    assert migrated.article_id == 42
    assert migrated.legacy_news_id == 10
    assert migrated.score_type == "sentiment"
    assert migrated.model == "gpt_5_2"
    assert migrated.reasoning_effort == "high"


def test_rejected_and_missing_legacy_rows_are_counted_unmapped():
    rows = [_row(legacy_news_id=10), _row(legacy_news_id=11), _row(legacy_news_id=12)]
    plan = build_score_migration_plan(rows, {10: 42, 11: None})

    assert plan.source_rows == 3
    assert plan.mapped_rows == 1
    assert plan.unmapped_rows == 2
    assert plan.rejected_rows == 1
    assert plan.missing_legacy_rows == 1
    assert [row.legacy_news_id for row in plan.rows] == [10]


def test_duplicate_upsert_keys_choose_latest_score_deterministically():
    older = _row(legacy_news_id=10, score=2.0, scored_at="2026-07-01T00:00:00Z")
    newer = _row(legacy_news_id=11, score=5.0, scored_at="2026-07-02T00:00:00Z")

    plan = build_score_migration_plan([older, newer], {10: 42, 11: 42})

    assert plan.source_rows == 2
    assert plan.mapped_rows == 2
    assert plan.duplicate_keys == 1
    assert len(plan.rows) == 1
    assert plan.rows[0].score == 5.0
    assert plan.rows[0].legacy_news_id == 11


def test_fingerprint_is_stable_for_input_order_changes():
    rows = [
        _row(legacy_news_id=10, score_type="sentiment", score=4.0),
        _row(legacy_news_id=11, score_type="risk", score=2.0),
        _row(legacy_news_id=12, score_type="sentiment", score=5.0),
    ]
    mapping = {10: 42, 11: 42, 12: 43}

    first = build_score_migration_plan(rows, mapping)
    second = build_score_migration_plan(list(reversed(rows)), mapping)

    assert first.fingerprint == second.fingerprint
    assert first.rows == second.rows


def test_counts_capture_score_type_model_and_effort():
    rows = [
        _row(score_type="sentiment", model="gpt-5.2", effort="HIGH"),
        _row(legacy_news_id=11, score_type="risk", model="o4-mini", effort=None),
    ]

    plan = build_score_migration_plan(rows, {10: 42, 11: 42})

    assert plan.counts["score_type:sentiment"] == 1
    assert plan.counts["score_type:risk"] == 1
    assert plan.counts["model:gpt_5_2"] == 1
    assert plan.counts["model:o4_mini"] == 1
    assert plan.counts["reasoning_effort:high"] == 1
    assert plan.counts["reasoning_effort:"] == 1
