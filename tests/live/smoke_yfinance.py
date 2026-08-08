#!/usr/bin/env python3
"""Manual yfinance dependency smoke; never collected by pytest."""

from __future__ import annotations

import argparse
import contextlib
import math
import re
import sys
from typing import Any


_PERIODS = ("5d", "1mo", "3mo", "6mo", "1y", "2y", "5y")
_INTERVALS = ("1d", "1wk", "1mo")
_REQUIRED_FIELDS = ("Open", "High", "Low", "Close", "Volume")
_TICKER_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9.-]{0,14}")
_REQUEST_TIMEOUT_SECONDS = 15


class SmokeValidationError(ValueError):
    """The provider response did not satisfy the smoke contract."""


class _DiscardOutput:
    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manually verify a small yfinance OHLCV response.",
    )
    parser.add_argument("ticker", help="Ticker to request, for example AAPL")
    parser.add_argument(
        "--period",
        choices=_PERIODS,
        default="5d",
        help="Bounded history window (default: 5d)",
    )
    parser.add_argument(
        "--interval",
        choices=_INTERVALS,
        default="1d",
        help="Bounded bar interval (default: 1d)",
    )
    return parser


def _single_column(frame: Any, field: str) -> Any:
    columns = frame.columns
    if field in columns:
        values = frame[field]
    else:
        matches = [
            column
            for column in columns
            if isinstance(column, tuple) and field in column
        ]
        if len(matches) != 1:
            raise SmokeValidationError(f"missing or ambiguous field: {field}")
        values = frame[matches[0]]

    if getattr(values, "ndim", 1) == 2:
        if values.shape[1] != 1:
            raise SmokeValidationError(f"ambiguous field: {field}")
        values = values.iloc[:, 0]
    if getattr(values, "ndim", 1) != 1:
        raise SmokeValidationError(f"invalid field shape: {field}")
    return values


def _validate_frame(frame: Any) -> tuple[str, str, float]:
    if frame is None or not hasattr(frame, "empty") or frame.empty:
        raise SmokeValidationError("empty response")
    if not hasattr(frame, "columns") or not hasattr(frame, "index"):
        raise SmokeValidationError("response is not tabular")

    columns = {field: _single_column(frame, field) for field in _REQUIRED_FIELDS}

    try:
        from pandas import isna, to_datetime

        timestamps = to_datetime(frame.index, errors="coerce", utc=True)
    except (ImportError, OSError, OverflowError, TypeError, ValueError) as exc:
        raise SmokeValidationError("unparseable timestamp index") from exc

    if len(timestamps) != len(frame.index) or bool(isna(timestamps).any()):
        raise SmokeValidationError("unparseable timestamp index")
    if not timestamps.is_monotonic_increasing or timestamps.has_duplicates:
        raise SmokeValidationError("timestamp index is not strictly ordered")

    try:
        latest_close = float(columns["Close"].iloc[-1])
    except (IndexError, TypeError, ValueError) as exc:
        raise SmokeValidationError("latest close is not numeric") from exc
    if not math.isfinite(latest_close):
        raise SmokeValidationError("latest close is not finite")

    return timestamps[0].isoformat(), timestamps[-1].isoformat(), latest_close


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if _TICKER_PATTERN.fullmatch(args.ticker) is None:
        parser.error("ticker must be 1-15 letters, digits, dots, or hyphens")
    ticker = args.ticker.upper()

    try:
        import yfinance as yf
    except (ImportError, OSError) as exc:
        print(f"yfinance import failed ({type(exc).__name__})", file=sys.stderr)
        return 3

    try:
        with contextlib.redirect_stdout(_DiscardOutput()), contextlib.redirect_stderr(
            _DiscardOutput()
        ):
            frame = yf.download(
                ticker,
                period=args.period,
                interval=args.interval,
                auto_adjust=False,
                progress=False,
                threads=False,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
    except Exception as exc:
        print(f"yfinance request failed ({type(exc).__name__})", file=sys.stderr)
        return 4

    try:
        start, end, latest_close = _validate_frame(frame)
    except SmokeValidationError as exc:
        print(f"yfinance response invalid: {exc}", file=sys.stderr)
        return 5
    except Exception as exc:
        print(
            f"yfinance response validation failed ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 5

    print(
        f"yfinance smoke OK: ticker={ticker} period={args.period} "
        f"interval={args.interval} rows={len(frame.index)} start={start} "
        f"end={end} latest_close={latest_close:.6g}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
