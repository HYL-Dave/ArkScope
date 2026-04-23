"""Live RL inference smoke CLI (Phase B1b).

Hits the real IBKR Gateway and Polygon parquet store to produce live
features_df → predict → top buys/sells for one or more post-training
dates. This is a manual smoke test — not covered by pytest.

Strict behaviour:
    - if IBKR Gateway is unreachable, fail immediately with a clear
      message; do NOT fall back to DB/CSV
    - if a requested date has no rows in IBKR or no indicators
      (insufficient lookback), the builder raises and we print the
      error and move to the next date

Usage:
    # Single date
    python scripts/rl_live_inference_smoke.py --date 2026-04-14

    # Multiple dates (comma-separated)
    python scripts/rl_live_inference_smoke.py --date 2026-04-14,2026-04-15,2026-04-16

    # Different model
    python scripts/rl_live_inference_smoke.py \\
        --model-dir trained_models/ppo_sb3_..._s0_... \\
        --date 2026-04-14

Notes:
    - IBKR Gateway is expected at IBKR_HOST:IBKR_PORT (loaded from
      config/.env via prepare_training_data._fetch_ibkr_daily)
    - Each date triggers one IBKR fetch for 143 tickers × lookback_days;
      expect a few minutes per date at default lookback.
    - Avoid running for today; intraday daily bars may be incomplete.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.rl.inference import decode_action, load_model, predict_from_frame  # noqa: E402
from src.rl.live_features import (  # noqa: E402
    IBKRDailyPriceAdapter,
    ParquetSentimentAdapter,
    build_live_features,
)

_DEFAULT_MODEL_DIR = (
    _REPO_ROOT
    / "trained_models"
    / "ppo_sb3_train_polygon_multi_both_ext_100ep_s42_20260415T165924Z_9c0a66"
)


def _parse_dates(raw: str) -> List[str]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError("--date is required (single or comma-separated)")
    for d in parts:
        time.strptime(d, "%Y-%m-%d")  # raises on bad format
    return parts


def _print_header(title: str, width: int = 70) -> None:
    print()
    print("=" * width)
    print(title)
    print("=" * width)


def _run_one(
    artifacts,
    price_adapter,
    sentiment_adapter,
    date: str,
    lookback_days: int,
    top_n: int,
    buy_threshold: float,
    sell_threshold: float,
) -> bool:
    """Return True on success, False on failure."""
    schema = artifacts.schema
    _print_header(f"[date]  {date}")

    t0 = time.time()
    try:
        frame = build_live_features(
            target_date=date,
            ticker_order=schema.ticker_order,
            price_adapter=price_adapter,
            sentiment_adapter=sentiment_adapter,
            tech_indicator_list=schema.tech_indicator_list,
            lookback_days=lookback_days,
            sentiment_missing_fill=0.0,
            llm_sentiment_col=schema.llm_sentiment_col,
        )
    except Exception as exc:
        print(f"  [error]  build_live_features failed: "
              f"{type(exc).__name__}: {exc}")
        return False
    t_build = time.time() - t0

    n_with_sent = int((frame["llm_sentiment"] != 0).sum())
    print(
        f"  [frame]  {len(frame)} tickers, "
        f"sentiment non-zero: {n_with_sent} "
        f"({n_with_sent / len(frame):.1%}), "
        f"built in {t_build:.1f}s"
    )

    action = predict_from_frame(artifacts, frame)
    decoded = decode_action(
        action,
        schema.ticker_order,
        top_n=top_n,
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
    )
    dist = decoded["distribution"]
    stats = decoded["stats"]
    print(
        f"  [dist]   buy={dist['buy']}  sell={dist['sell']}  hold={dist['hold']}  "
        f"(mean={stats['mean']:+.3f} std={stats['std']:.3f} "
        f"range=[{stats['min']:+.3f}, {stats['max']:+.3f}])"
    )
    print()
    print("  Top buys:")
    if not decoded["top_buys"]:
        print("    (none above 0)")
    for e in decoded["top_buys"]:
        print(f"    {e['ticker']:6s}  action={e['action']:+.4f}  {e['signal']}")
    print()
    print("  Top sells:")
    if not decoded["top_sells"]:
        print("    (none below 0)")
    for e in decoded["top_sells"]:
        print(f"    {e['ticker']:6s}  action={e['action']:+.4f}  {e['signal']}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--model-dir", default=str(_DEFAULT_MODEL_DIR))
    parser.add_argument(
        "--date", required=True,
        help="YYYY-MM-DD, or comma-separated list",
    )
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--buy-threshold", type=float, default=0.1)
    parser.add_argument("--sell-threshold", type=float, default=-0.1)
    parser.add_argument(
        "--parquet-dir", default=str(_REPO_ROOT / "data" / "news" / "raw" / "polygon"),
        help="Root of Polygon monthly parquets (default: data/news/raw/polygon)",
    )
    args = parser.parse_args()

    try:
        dates = _parse_dates(args.date)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    model_dir = Path(args.model_dir)
    _print_header("[model] loading")
    print(f"  path      : {model_dir}")
    try:
        artifacts = load_model(model_dir)
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    schema = artifacts.schema
    print(f"  stock_dim : {schema.stock_dim}")
    print(f"  state_dim : {schema.state_dim}")
    print(f"  indicators: {schema.tech_indicator_list}")
    print(f"  tickers   : {schema.ticker_order[:5]} … {schema.ticker_order[-3:]}")

    price_adapter = IBKRDailyPriceAdapter()
    sentiment_adapter = ParquetSentimentAdapter(base_dir=args.parquet_dir)

    print()
    print(f"[run] predicting for {len(dates)} date(s): {dates}")
    print(f"      lookback_days={args.lookback_days}, top_n={args.top_n}")

    n_ok = 0
    n_fail = 0
    for date in dates:
        ok = _run_one(
            artifacts=artifacts,
            price_adapter=price_adapter,
            sentiment_adapter=sentiment_adapter,
            date=date,
            lookback_days=args.lookback_days,
            top_n=args.top_n,
            buy_threshold=args.buy_threshold,
            sell_threshold=args.sell_threshold,
        )
        if ok:
            n_ok += 1
        else:
            n_fail += 1

    _print_header(f"[summary]  {n_ok} ok / {n_fail} fail")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())