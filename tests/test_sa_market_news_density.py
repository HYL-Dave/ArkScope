from __future__ import annotations

import pandas as pd

from src.service.sa_market_news_density import (
    build_density_profile,
    merge_interval_windows,
    prepare_market_news_events,
    recommend_sync_interval,
)


class TestRecommendSyncInterval:
    def test_prefers_longest_interval_under_backlog_target(self):
        assert recommend_sync_interval(2.0, target_items_per_sync=3.0) == 60
        assert recommend_sync_interval(4.0, target_items_per_sync=3.0) == 15
        assert recommend_sync_interval(15.0, target_items_per_sync=3.0) == 5


class TestPrepareMarketNewsEvents:
    def test_converts_utc_rows_into_et_buckets(self):
        events = prepare_market_news_events(
            [
                {
                    "published_at": "2026-04-22T13:15:00+00:00",
                    "fetched_at": "2026-04-22T13:16:00+00:00",
                }
            ],
            bucket_minutes=30,
        )

        assert len(events) == 1
        row = events.iloc[0]
        assert row["day_type"] == "weekday"
        assert row["minute_of_day"] == 9 * 60 + 15
        assert row["bucket_index"] == 18
        assert row["bucket_start_minute"] == 9 * 60


class TestBuildDensityProfile:
    def test_zero_fills_missing_dates_in_average(self):
        profile = build_density_profile(
            [
                {"published_at": "2026-04-20T13:05:00+00:00"},
                {"published_at": "2026-04-20T13:10:00+00:00"},
                {"published_at": "2026-04-22T13:15:00+00:00"},
            ],
            bucket_minutes=30,
            target_items_per_sync=1.0,
            day_type="weekday",
        )

        bucket = profile.loc[profile["bucket_label"] == "09:00-09:30"].iloc[0]
        assert bucket["day_count"] == 3
        assert bucket["total_items"] == 3
        assert bucket["avg_items_per_bucket_day"] == 1.0
        assert bucket["avg_items_per_hour"] == 2.0
        assert bucket["recommended_interval_minutes"] == 15

    def test_splits_weekend_profile(self):
        weekday = build_density_profile(
            [{"published_at": "2026-04-20T13:05:00+00:00"}],
            bucket_minutes=30,
            day_type="weekday",
        )
        weekend = build_density_profile(
            [{"published_at": "2026-04-19T13:05:00+00:00"}],
            bucket_minutes=30,
            day_type="weekend",
        )

        assert not weekday.empty
        assert not weekend.empty
        assert weekday["day_type"].nunique() == 1
        assert weekend["day_type"].nunique() == 1
        assert weekday["day_type"].iloc[0] == "weekday"
        assert weekend["day_type"].iloc[0] == "weekend"


class TestMergeIntervalWindows:
    def test_merges_adjacent_buckets_with_same_interval(self):
        profile = pd.DataFrame(
            [
                {
                    "day_type": "weekday",
                    "bucket_index": 0,
                    "bucket_start_minute": 0,
                    "bucket_label": "00:00-00:30",
                    "avg_items_per_hour": 0.4,
                    "recommended_interval_minutes": 60,
                },
                {
                    "day_type": "weekday",
                    "bucket_index": 1,
                    "bucket_start_minute": 30,
                    "bucket_label": "00:30-01:00",
                    "avg_items_per_hour": 0.6,
                    "recommended_interval_minutes": 60,
                },
                {
                    "day_type": "weekday",
                    "bucket_index": 2,
                    "bucket_start_minute": 60,
                    "bucket_label": "01:00-01:30",
                    "avg_items_per_hour": 4.0,
                    "recommended_interval_minutes": 15,
                },
            ]
        )

        windows = merge_interval_windows(profile)

        assert windows == [
            {
                "day_type": "weekday",
                "start_et": "00:00",
                "end_et": "01:00",
                "interval_minutes": 60,
                "avg_items_per_hour": 0.5,
                "expected_items_per_sync": 0.5,
            },
            {
                "day_type": "weekday",
                "start_et": "01:00",
                "end_et": "01:30",
                "interval_minutes": 15,
                "avg_items_per_hour": 4.0,
                "expected_items_per_sync": 1.0,
            },
        ]
