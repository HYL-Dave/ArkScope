"""Ensemble scan across models × post-training dates.

What it does:
  1. Fetch IBKR daily bars ONCE covering all target dates' lookback window
  2. Compute the 9 indicators ONCE on that full history
  3. For each target date, slice the enriched frame + attach sentiment
  4. For each model, predict deterministic action on each target date
  5. Report per-model per-date action stats, ensemble mean/std, and
     alignment with actual next-day returns (where available)

Designed for: verifying whether a fleet of trained PPO models produces
meaningfully different signals across a post-training window, and whether
those signals have any predictive value against realised returns.

Caches IBKR fetch once to keep this under 5 minutes total.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.rl.inference import load_model, predict_from_frame  # noqa: E402
from src.rl.live_features import ParquetSentimentAdapter  # noqa: E402
from training.data_prep.state_builder import build_observation  # noqa: E402


def _parse_dates(raw: str) -> List[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


def _trading_days_in_range(start: str, end: str) -> List[str]:
    """Weekdays only — IBKR weekend bars don't exist, holidays handled by drop."""
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    d1 = datetime.strptime(end, "%Y-%m-%d").date()
    out = []
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _resolve_csv_for_model(model_dir: Path) -> Path:
    """Map model_id → training CSV path."""
    parts = model_dir.name.split("_")
    try:
        ep_idx = next(i for i, p in enumerate(parts) if p.endswith("ep"))
    except StopIteration:
        raise ValueError(f"Cannot derive data tag from model_id {model_dir.name}")
    tag = "_".join(parts[2:ep_idx])
    return _REPO_ROOT / "training" / "data_prep" / "output" / f"{tag}.csv"


def _fetch_ibkr_once(
    tickers: Sequence[str], start_date: str, end_date: str
) -> pd.DataFrame:
    """Single IBKR fetch covering the widest range needed by all target dates."""
    from training.data_prep.prepare_training_data import _fetch_ibkr_daily
    return _fetch_ibkr_daily(list(tickers), start_date, end_date)


def _compute_indicators(
    prices: pd.DataFrame, tech_indicator_list: Sequence[str]
) -> pd.DataFrame:
    from training.preprocessor import FeatureEngineer
    fe = FeatureEngineer(
        use_technical_indicator=True,
        tech_indicator_list=list(tech_indicator_list),
        use_vix=False,
        use_turbulence=False,
        user_defined_feature=False,
    )
    return fe.preprocess_data(prices)


def _build_day_frame(
    enriched: pd.DataFrame,
    target_date: str,
    ticker_order: Sequence[str],
    tech_indicator_list: Sequence[str],
    sent_adapter: ParquetSentimentAdapter,
    sentiment_missing_fill: float = 0.0,
) -> pd.DataFrame:
    """Slice the enriched DataFrame for one target_date and attach sentiment."""
    day = enriched[enriched["date"] == target_date].copy()
    if day.empty:
        raise ValueError(f"No enriched rows for {target_date}")
    sent_map = sent_adapter.fetch_day_sentiment(list(ticker_order), target_date)
    day["llm_sentiment"] = (
        day["tic"].map(lambda t: sent_map.get(t, sentiment_missing_fill))
    )
    required = ["date", "tic", "close"] + list(tech_indicator_list) + ["llm_sentiment"]
    for c in required:
        if c not in day.columns:
            raise ValueError(f"Missing column {c} on {target_date}")
    day = day[required].set_index("tic").reindex(list(ticker_order))
    if day["close"].isna().any():
        bad = day.index[day["close"].isna()].tolist()
        raise ValueError(f"{target_date}: missing close for {bad[:5]}...")
    for ind in tech_indicator_list:
        if day[ind].isna().any():
            bad = day.index[day[ind].isna()].tolist()
            raise ValueError(f"{target_date}: missing {ind} for {bad[:5]}...")
    return day.reset_index().assign(date=target_date)


def _next_day_returns(enriched: pd.DataFrame, date: str, ticker_order: Sequence[str]):
    """Return dict {ticker: next-day close-to-close pct change} using enriched frame."""
    dates_sorted = sorted(enriched["date"].unique())
    try:
        idx = dates_sorted.index(date)
    except ValueError:
        return {}
    if idx + 1 >= len(dates_sorted):
        return {}
    next_date = dates_sorted[idx + 1]
    today = enriched[enriched["date"] == date].set_index("tic")["close"]
    tomorrow = enriched[enriched["date"] == next_date].set_index("tic")["close"]
    joined = pd.concat([today.rename("c0"), tomorrow.rename("c1")], axis=1).dropna()
    ret = (joined["c1"] - joined["c0"]) / joined["c0"]
    return ret.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument(
        "--start-date", default="2026-04-14",
        help="First post-training trading day to predict (inclusive)"
    )
    parser.add_argument(
        "--end-date", default="2026-04-23",
        help="Last post-training trading day to predict (inclusive)"
    )
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument(
        "--model-filter", default="both_ext",
        help="Substring match on model_id (default: ext models only). "
             "Use '' for all patched polygon models."
    )
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument(
        "--output-json", default=None,
        help="If set, write per-model per-date signal dict to this path"
    )
    args = parser.parse_args()

    target_dates = _trading_days_in_range(args.start_date, args.end_date)
    print(f"[dates] target trading days: {target_dates}")

    models_dir = _REPO_ROOT / "trained_models"
    candidate = sorted(
        p for p in models_dir.iterdir()
        if p.is_dir()
        and p.name.startswith("ppo_sb3_train_polygon")
        and (p / "metadata.json").exists()
        and (args.model_filter in p.name if args.model_filter else True)
    )
    # Filter to models whose metadata has schema (ticker_order present)
    usable = []
    for m in candidate:
        with open(m / "metadata.json") as f:
            meta = json.load(f)
        if meta.get("ticker_order"):
            usable.append((m, meta))
    print(f"[models] {len(usable)} patched models matching '{args.model_filter}'")
    if not usable:
        return 2

    # Determine ticker universe — verify all models share the same ticker_order
    ticker_order = tuple(usable[0][1]["ticker_order"])
    stock_dim = len(ticker_order)
    for m, meta in usable:
        if tuple(meta["ticker_order"]) != ticker_order:
            raise ValueError(
                f"Model {m.name} has different ticker_order — "
                "cannot share a single IBKR fetch. Rerun with a narrower filter."
            )
    tech_indicator_list = tuple(usable[0][1]["tech_indicator_list"])
    for m, meta in usable:
        if tuple(meta["tech_indicator_list"]) != tech_indicator_list:
            raise ValueError(
                f"Model {m.name} uses different indicators — cannot share enriched frame. "
                "Rerun with a narrower filter."
            )

    # Fetch IBKR once — start = earliest_target - lookback, end = latest_target + 1
    fetch_start = (
        datetime.strptime(target_dates[0], "%Y-%m-%d").date()
        - timedelta(days=args.lookback_days)
    ).isoformat()
    fetch_end = (
        datetime.strptime(target_dates[-1], "%Y-%m-%d").date()
        + timedelta(days=1)  # need next day for realised return
    ).isoformat()

    print(f"[ibkr ] fetching {stock_dim} tickers {fetch_start} → {fetch_end} ...")
    t0 = time.time()
    prices = _fetch_ibkr_once(ticker_order, fetch_start, fetch_end)
    prices["date"] = pd.to_datetime(prices["date"]).dt.strftime("%Y-%m-%d")
    print(f"[ibkr ] {len(prices)} rows in {time.time() - t0:.1f}s")

    print(f"[feat ] computing {len(tech_indicator_list)} indicators...")
    t0 = time.time()
    enriched = _compute_indicators(prices, tech_indicator_list)
    print(f"[feat ] done in {time.time() - t0:.1f}s")

    sent_adapter = ParquetSentimentAdapter()

    # Build day frames for all target dates
    day_frames: Dict[str, pd.DataFrame] = {}
    for d in target_dates:
        try:
            day_frames[d] = _build_day_frame(
                enriched, d, ticker_order, tech_indicator_list, sent_adapter
            )
        except ValueError as e:
            print(f"[skip] {d}: {e}")
    good_dates = list(day_frames.keys())
    print(f"[ready] {len(good_dates)} dates with complete frames")

    # Pre-compute realised returns per date
    returns_per_date = {d: _next_day_returns(enriched, d, ticker_order) for d in good_dates}

    # Per-model per-date predictions
    actions: Dict[str, Dict[str, np.ndarray]] = {}  # model_id → {date → action}
    for mdir, meta in usable:
        art = load_model(mdir)
        mid = art.metadata["model_id"]
        actions[mid] = {}
        for d in good_dates:
            actions[mid][d] = predict_from_frame(art, day_frames[d], deterministic=True)

    # Analysis 1: per-model cross-date variability
    print()
    print(f"=== Per-model action stability across {len(good_dates)} post-training days ===")
    print(f"{'model':50s}  {'det_std':>8s}  {'corr_min':>8s}  {'corr_max':>8s}")
    print("-" * 90)
    for mid, by_date in actions.items():
        stack = np.stack([by_date[d] for d in good_dates])  # (n_dates, stock_dim)
        corr = np.corrcoef(stack)
        off_diag = corr - np.eye(len(good_dates))
        off_diag_vals = off_diag[off_diag != 0]
        det_std = float(stack.std())
        print(
            f"{mid[-50:]:50s}  "
            f"{det_std:8.4f}  "
            f"{off_diag_vals.min():8.4f}  "
            f"{off_diag_vals.max():8.4f}"
        )

    # Analysis 2: ensemble mean action per date → top picks + realised returns
    print()
    print(f"=== Ensemble (mean across {len(actions)} models) top-{args.top_n} per date ===")
    for d in good_dates:
        stack = np.stack([actions[mid][d] for mid in actions])  # (n_models, stock_dim)
        ensemble = stack.mean(axis=0)
        ret_map = returns_per_date.get(d, {})
        ranked = sorted(zip(ticker_order, ensemble.tolist()), key=lambda x: -x[1])
        top_buys = ranked[:args.top_n]
        top_sells = ranked[-args.top_n:]

        def _line(tic, score):
            r = ret_map.get(tic)
            r_s = f"{r:+.2%}" if r is not None else "  n/a"
            return f"{tic:6s} score={score:+.3f} next-day={r_s}"

        print(f"\n[{d}] realised-return coverage: {len(ret_map)}/{stock_dim} tickers")
        print("  top buys :")
        for tic, s in top_buys:
            print(f"    {_line(tic, s)}")
        print("  top sells:")
        for tic, s in top_sells:
            print(f"    {_line(tic, s)}")

        # Signal-return correlation on the ensemble for this date
        if ret_map:
            pairs = [(ensemble[i], ret_map[t])
                     for i, t in enumerate(ticker_order) if t in ret_map]
            if len(pairs) >= 20:
                scores, rets = zip(*pairs)
                corr = np.corrcoef(scores, rets)[0, 1]
                print(f"  score↔next-day-return corr: {corr:+.3f} (n={len(pairs)})")

    if args.output_json:
        payload = {
            "target_dates": good_dates,
            "tickers": list(ticker_order),
            "actions": {mid: {d: by_date[d].tolist() for d in good_dates}
                        for mid, by_date in actions.items()},
            "returns": {d: returns_per_date.get(d, {}) for d in good_dates},
        }
        with open(args.output_json, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        print(f"\n[saved] {args.output_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())