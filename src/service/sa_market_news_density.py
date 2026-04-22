"""Market-news density analysis helpers for Seeking Alpha auto-sync planning."""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

import pandas as pd

NEW_YORK_TZ = "America/New_York"
DEFAULT_ALLOWED_INTERVALS = (5, 15, 60)


def recommend_sync_interval(
    avg_items_per_hour: float,
    *,
    target_items_per_sync: float = 3.0,
    allowed_intervals: Sequence[int] = DEFAULT_ALLOWED_INTERVALS,
) -> int:
    """Choose the longest allowed interval that keeps expected backlog bounded."""
    intervals = sorted({int(v) for v in allowed_intervals if int(v) > 0}, reverse=True)
    if not intervals:
        raise ValueError("allowed_intervals must contain at least one positive integer")

    rate = max(0.0, float(avg_items_per_hour or 0.0))
    for interval in intervals:
        expected_items = rate * (interval / 60.0)
        if expected_items <= target_items_per_sync:
            return interval
    return min(intervals)


def prepare_market_news_events(
    rows: Iterable[Mapping],
    *,
    bucket_minutes: int = 30,
) -> pd.DataFrame:
    """Normalize raw market-news rows into ET-localized event buckets."""
    if 60 % int(bucket_minutes) != 0:
        raise ValueError("bucket_minutes must divide 60 evenly")

    frame = pd.DataFrame(list(rows))
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "event_ts",
                "event_ts_et",
                "date_et",
                "weekday_num",
                "day_type",
                "minute_of_day",
                "bucket_index",
                "bucket_start_minute",
            ]
        )

    if "event_ts" not in frame.columns:
        event_ts = frame.get("published_at")
        if event_ts is None:
            event_ts = frame.get("fetched_at")
        else:
            fetched = frame.get("fetched_at")
            if fetched is not None:
                event_ts = event_ts.fillna(fetched)
        frame["event_ts"] = event_ts

    frame["event_ts"] = pd.to_datetime(frame["event_ts"], errors="coerce", utc=True)
    frame = frame.dropna(subset=["event_ts"]).copy()
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "event_ts",
                "event_ts_et",
                "date_et",
                "weekday_num",
                "day_type",
                "minute_of_day",
                "bucket_index",
                "bucket_start_minute",
            ]
        )

    frame["event_ts_et"] = frame["event_ts"].dt.tz_convert(NEW_YORK_TZ)
    frame["date_et"] = frame["event_ts_et"].dt.date
    frame["weekday_num"] = frame["event_ts_et"].dt.weekday
    frame["day_type"] = frame["weekday_num"].apply(
        lambda value: "weekday" if int(value) < 5 else "weekend"
    )
    frame["minute_of_day"] = (
        frame["event_ts_et"].dt.hour.astype(int) * 60
        + frame["event_ts_et"].dt.minute.astype(int)
    )
    frame["bucket_index"] = (frame["minute_of_day"] // int(bucket_minutes)).astype(int)
    frame["bucket_start_minute"] = frame["bucket_index"] * int(bucket_minutes)
    return frame


def build_density_profile(
    rows: Iterable[Mapping],
    *,
    bucket_minutes: int = 30,
    target_items_per_sync: float = 3.0,
    allowed_intervals: Sequence[int] = DEFAULT_ALLOWED_INTERVALS,
    day_type: str = "weekday",
) -> pd.DataFrame:
    """Aggregate market-news event density for one ET day type."""
    events = prepare_market_news_events(rows, bucket_minutes=bucket_minutes)
    return build_density_profile_from_events(
        events,
        bucket_minutes=bucket_minutes,
        target_items_per_sync=target_items_per_sync,
        allowed_intervals=allowed_intervals,
        day_type=day_type,
    )


def build_density_profile_from_events(
    events: pd.DataFrame,
    *,
    bucket_minutes: int = 30,
    target_items_per_sync: float = 3.0,
    allowed_intervals: Sequence[int] = DEFAULT_ALLOWED_INTERVALS,
    day_type: str = "weekday",
) -> pd.DataFrame:
    """Aggregate market-news event density for one ET day type from prepared events."""
    bucket_minutes = int(bucket_minutes)
    buckets_per_day = 1440 // bucket_minutes
    profile_columns = [
        "day_type",
        "bucket_index",
        "bucket_start_minute",
        "bucket_label",
        "day_count",
        "total_items",
        "avg_items_per_bucket_day",
        "median_items_per_bucket_day",
        "p90_items_per_bucket_day",
        "avg_items_per_hour",
        "recommended_interval_minutes",
        "expected_items_per_sync",
    ]
    if events.empty:
        return pd.DataFrame(columns=profile_columns)

    if day_type not in {"weekday", "weekend"}:
        raise ValueError("day_type must be 'weekday' or 'weekend'")

    date_frame = _build_local_date_frame(events)
    date_frame = date_frame[date_frame["day_type"] == day_type].copy()
    if date_frame.empty:
        return pd.DataFrame(columns=profile_columns)

    scoped = events[events["day_type"] == day_type].copy()
    counts = (
        scoped.groupby(["date_et", "bucket_index"])
        .size()
        .rename("item_count")
        .reset_index()
    )

    dense_index = pd.MultiIndex.from_product(
        [date_frame["date_et"].tolist(), range(buckets_per_day)],
        names=["date_et", "bucket_index"],
    ).to_frame(index=False)
    dense = dense_index.merge(counts, on=["date_et", "bucket_index"], how="left")
    dense["item_count"] = dense["item_count"].fillna(0).astype(float)

    bucket_stats = (
        dense.groupby("bucket_index")["item_count"]
        .agg(
            total_items="sum",
            avg_items_per_bucket_day="mean",
            median_items_per_bucket_day="median",
            p90_items_per_bucket_day=lambda s: float(s.quantile(0.9)),
        )
        .reset_index()
    )
    bucket_stats["day_type"] = day_type
    bucket_stats["day_count"] = int(len(date_frame))
    bucket_stats["bucket_start_minute"] = bucket_stats["bucket_index"] * bucket_minutes
    bucket_stats["bucket_label"] = bucket_stats["bucket_start_minute"].apply(
        lambda minute: format_minute_range(minute, minute + bucket_minutes)
    )
    bucket_stats["avg_items_per_hour"] = (
        bucket_stats["avg_items_per_bucket_day"] * (60.0 / bucket_minutes)
    )
    bucket_stats["recommended_interval_minutes"] = bucket_stats["avg_items_per_hour"].apply(
        lambda rate: recommend_sync_interval(
            rate,
            target_items_per_sync=target_items_per_sync,
            allowed_intervals=allowed_intervals,
        )
    )
    bucket_stats["expected_items_per_sync"] = (
        bucket_stats["avg_items_per_hour"]
        * (bucket_stats["recommended_interval_minutes"] / 60.0)
    )
    return bucket_stats[profile_columns].sort_values("bucket_index").reset_index(drop=True)


def merge_interval_windows(profile: pd.DataFrame) -> list[dict]:
    """Merge adjacent buckets with the same recommended interval."""
    if profile is None or profile.empty:
        return []

    rows = profile.sort_values("bucket_index").to_dict(orient="records")
    windows: list[dict] = []
    current = None
    for row in rows:
        start_minute = int(row["bucket_start_minute"])
        label = str(row["bucket_label"])
        end_minute = _parse_bucket_end_minute(label)
        interval = int(row["recommended_interval_minutes"])
        avg_per_hour = float(row["avg_items_per_hour"])
        day_type = str(row["day_type"])

        if current and current["interval_minutes"] == interval and current["end_minute"] == start_minute:
            current["end_minute"] = end_minute
            current["avg_items_per_hour_values"].append(avg_per_hour)
            continue

        if current:
            windows.append(_finalize_window(current))

        current = {
            "day_type": day_type,
            "start_minute": start_minute,
            "end_minute": end_minute,
            "interval_minutes": interval,
            "avg_items_per_hour_values": [avg_per_hour],
        }

    if current:
        windows.append(_finalize_window(current))
    return windows


def summarize_market_news_density(
    rows: Iterable[Mapping],
    *,
    bucket_minutes: int = 30,
    target_items_per_sync: float = 3.0,
    allowed_intervals: Sequence[int] = DEFAULT_ALLOWED_INTERVALS,
) -> dict:
    """Return a full density-analysis summary for weekday/weekend planning."""
    events = prepare_market_news_events(rows, bucket_minutes=bucket_minutes)
    total_items = int(len(events))
    if events.empty:
        return {
            "total_items": 0,
            "date_range_et": None,
            "bucket_minutes": int(bucket_minutes),
            "target_items_per_sync": float(target_items_per_sync),
            "weekday_profile": [],
            "weekend_profile": [],
            "weekday_windows": [],
            "weekend_windows": [],
        }

    weekday_profile = build_density_profile_from_events(
        events,
        bucket_minutes=bucket_minutes,
        target_items_per_sync=target_items_per_sync,
        allowed_intervals=allowed_intervals,
        day_type="weekday",
    )
    weekend_profile = build_density_profile_from_events(
        events,
        bucket_minutes=bucket_minutes,
        target_items_per_sync=target_items_per_sync,
        allowed_intervals=allowed_intervals,
        day_type="weekend",
    )
    min_date = events["date_et"].min()
    max_date = events["date_et"].max()
    return {
        "total_items": total_items,
        "date_range_et": {
            "start": min_date.isoformat() if min_date else None,
            "end": max_date.isoformat() if max_date else None,
        },
        "bucket_minutes": int(bucket_minutes),
        "target_items_per_sync": float(target_items_per_sync),
        "weekday_profile": weekday_profile.to_dict(orient="records"),
        "weekend_profile": weekend_profile.to_dict(orient="records"),
        "weekday_windows": merge_interval_windows(weekday_profile),
        "weekend_windows": merge_interval_windows(weekend_profile),
    }


def format_minute_range(start_minute: int, end_minute: int) -> str:
    """Format a minute-range as HH:MM-HH:MM."""
    return f"{_format_hhmm(start_minute)}-{_format_hhmm(end_minute % 1440)}"


def _format_hhmm(minute_of_day: int) -> str:
    minute_of_day = int(minute_of_day) % 1440
    hour = minute_of_day // 60
    minute = minute_of_day % 60
    return f"{hour:02d}:{minute:02d}"


def _parse_bucket_end_minute(bucket_label: str) -> int:
    _, end = bucket_label.split("-", 1)
    hh, mm = end.split(":")
    total = int(hh) * 60 + int(mm)
    if total == 0:
        return 1440
    return total


def _build_local_date_frame(events: pd.DataFrame) -> pd.DataFrame:
    min_date = events["date_et"].min()
    max_date = events["date_et"].max()
    all_dates = pd.date_range(start=min_date, end=max_date, freq="D")
    date_frame = pd.DataFrame({"date_et": all_dates.date})
    weekday_num = pd.to_datetime(date_frame["date_et"]).dt.weekday
    date_frame["day_type"] = weekday_num.apply(
        lambda value: "weekday" if int(value) < 5 else "weekend"
    )
    return date_frame


def _finalize_window(window: dict) -> dict:
    avg_items_per_hour = sum(window["avg_items_per_hour_values"]) / len(
        window["avg_items_per_hour_values"]
    )
    return {
        "day_type": window["day_type"],
        "start_et": _format_hhmm(window["start_minute"]),
        "end_et": _format_hhmm(window["end_minute"] % 1440),
        "interval_minutes": int(window["interval_minutes"]),
        "avg_items_per_hour": round(avg_items_per_hour, 3),
        "expected_items_per_sync": round(
            avg_items_per_hour * (int(window["interval_minutes"]) / 60.0), 3
        ),
    }
