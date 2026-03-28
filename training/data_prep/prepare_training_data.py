#!/usr/bin/env python3
"""
Unified training data preparation from multiple score sources.

Merges OHLCV price data + technical indicators + LLM scores into
CSV files ready for train_ppo_llm.py / train_cppo_llm_risk.py.

Sources:
  huggingface  - DeepSeek scores from benstaf/FinRL_DeepSeek (original)
  claude       - Claude Opus/Sonnet/Haiku re-scored (same articles)
  gpt5         - GPT-5 at various effort levels (same articles)
  polygon      - Modern Polygon API news with GPT-5.2 scores (2022-2026)

Usage:
  python -m training.data_prep.prepare_training_data --source claude --model opus
  python -m training.data_prep.prepare_training_data --source claude --model opus --score-type both
  python -m training.data_prep.prepare_training_data --source gpt5 --model high --score-type both
  python -m training.data_prep.prepare_training_data --source huggingface --score-type both
  python -m training.data_prep.prepare_training_data --source polygon

Output format: see training/data_prep/README.md for the full contract.
"""

import argparse
import itertools
import os
import sys

import pandas as pd

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from training.config import INDICATORS
from training.preprocessor import YahooDownloader, FeatureEngineer, data_split


# ── Source definitions ──────────────────────────────────────────

# NASDAQ 100 tickers (July 2023 composition, same as upstream)
NASDAQ_100 = [
    "ADBE", "ADP", "ABNB", "ALGN", "GOOGL", "GOOG", "AMZN", "AMD", "AEP", "AMGN",
    "ADI", "ANSS", "AAPL", "AMAT", "ASML", "AZN", "TEAM", "ADSK", "BKR", "BIIB",
    "BKNG", "AVGO", "CDNS", "CHTR", "CTAS", "CSCO", "CTSH", "CMCSA", "CEG", "CPRT",
    "CSGP", "COST", "CRWD", "CSX", "DDOG", "DXCM", "FANG", "DLTR", "EBAY", "EA",
    "ENPH", "EXC", "FAST", "FTNT", "GEHC", "GILD", "GFS", "HON", "IDXX", "ILMN",
    "INTC", "INTU", "ISRG", "JD", "KDP", "KLAC", "KHC", "LRCX", "LCID", "LULU",
    "MAR", "MRVL", "MELI", "META", "MCHP", "MU", "MSFT", "MRNA", "MDLZ", "MNST",
    "NFLX", "NVDA", "NXPI", "ORLY", "ODFL", "ON", "PCAR", "PANW", "PAYX", "PYPL",
    "PDD", "PEP", "QCOM", "REGN", "ROST", "SIRI", "SBUX", "SNPS", "TMUS",
    "TSLA", "TXN", "TTD", "VRSK", "VRTX", "WBA", "WBD", "WDAY", "XEL", "ZM", "ZS",
]

# Score file paths and column mappings per source
SCORE_SOURCES = {
    "huggingface": {
        "sentiment": {
            "path": "/mnt/md0/finrl/huggingface_datasets/FinRL_DeepSeek_sentiment/"
                    "sentiment_deepseek_new_cleaned_nasdaq_news_full.csv",
            "score_col": "sentiment_deepseek",
        },
        "risk": {
            "path": "/mnt/md0/finrl/huggingface_datasets/FinRL_DeepSeek_risk/"
                    "risk_deepseek_cleaned_nasdaq_news_full.csv",
            "score_col": "risk_deepseek",
        },
        "date_col": "Date",
        "symbol_col": "Stock_symbol",
    },
    "claude": {
        "sentiment": {
            "opus": ("sentiment_opus_by_gpt5_summary.csv", "sentiment_opus"),
            "sonnet": ("sentiment_sonnet_by_gpt5_summary.csv", "sentiment_sonnet"),
            "haiku": ("sentiment_haiku_by_gpt5_summary.csv", "sentiment_haiku"),
        },
        "risk": {
            "opus": ("risk_opus_by_gpt5_summary.csv", "risk_opus"),
            "sonnet": ("risk_sonnet_by_gpt5_summary.csv", "risk_sonnet"),
            "haiku": ("risk_haiku_by_gpt5_summary.csv", "risk_haiku"),
        },
        "base_dir": "/mnt/md0/finrl/claude",
        "date_col": "Date",
        "symbol_col": "Stock_symbol",
    },
    "gpt5": {
        "sentiment": {
            "high": ("sentiment_gpt-5_high_by_o3_summary.csv", "sentiment_gpt_5"),
            "medium": ("sentiment_gpt-5_medium_by_o3_summary.csv", "sentiment_gpt_5"),
            "low": ("sentiment_gpt-5_low_by_o3_summary.csv", "sentiment_gpt_5"),
            "minimal": ("sentiment_gpt-5_minimal_by_o3_summary.csv", "sentiment_gpt_5"),
        },
        "risk": {
            "high": ("risk_gpt-5_high_by_o3_summary.csv", "risk_gpt_5"),
            "medium": ("risk_gpt-5_medium_by_o3_summary.csv", "risk_gpt_5"),
            "low": ("risk_gpt-5_low_by_o3_summary.csv", "risk_gpt_5"),
            "minimal": ("risk_gpt-5_minimal_by_o3_summary.csv", "risk_gpt_5"),
        },
        "base_dir": "/mnt/md0/finrl/gpt-5",
        "date_col": "Date",
        "symbol_col": "Stock_symbol",
    },
    "polygon": {
        "base_dir": "data/news/raw/polygon",
        # Model priority: coalesce newest → oldest (first non-null wins)
        "sentiment_cols": [
            "sentiment_gpt_5_4_xhigh",
            "sentiment_gpt_5_2_xhigh",
        ],
        "risk_cols": [
            "risk_gpt_5_4_xhigh",
            "risk_gpt_5_2_xhigh",
        ],
        "date_col": "published_at",
        "symbol_col": "ticker",
    },
}


# ── Score loading ───────────────────────────────────────────────


def _load_huggingface_scores(score_type, target_col):
    """Load DeepSeek sentiment or risk scores."""
    cfg = SCORE_SOURCES["huggingface"][score_type]
    print(f"  Loading HuggingFace {score_type}: {cfg['path']}")

    cols = [
        SCORE_SOURCES["huggingface"]["date_col"],
        SCORE_SOURCES["huggingface"]["symbol_col"],
        cfg["score_col"],
    ]
    df = pd.read_csv(cfg["path"], usecols=cols)
    df = df.rename(columns={
        SCORE_SOURCES["huggingface"]["date_col"]: "Date",
        SCORE_SOURCES["huggingface"]["symbol_col"]: "tic",
        cfg["score_col"]: target_col,
    })
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df[["Date", "tic", target_col]]


def _load_model_scores(source, model, score_type, target_col):
    """Load sentiment or risk scores for Claude / GPT-5.

    Args:
        source: "claude" or "gpt5"
        model: model variant (opus/sonnet/haiku for claude; high/medium/low/minimal for gpt5)
        score_type: "sentiment" or "risk"
        target_col: output column name (e.g. "llm_sentiment" or "llm_risk")
    """
    cfg = SCORE_SOURCES[source]
    models = cfg[score_type]
    if model not in models:
        raise ValueError(
            f"Unknown {source} model: {model}. Options: {list(models.keys())}"
        )

    filename, score_col = models[model]
    path = os.path.join(cfg["base_dir"], score_type, filename)
    label = "Claude" if source == "claude" else "GPT-5"
    print(f"  Loading {label} {model} {score_type}: {path}")

    cols = [cfg["date_col"], cfg["symbol_col"], score_col]
    df = pd.read_csv(path, usecols=cols)
    df = df.rename(columns={
        cfg["date_col"]: "Date",
        cfg["symbol_col"]: "tic",
        score_col: target_col,
    })
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df[["Date", "tic", target_col]]


def _load_polygon_scores(base_dir, score_type="sentiment", target_col="llm_sentiment"):
    """Load Polygon news scores from monthly Parquet files.

    Supports multi-model coalesce: reads all available model columns
    (e.g. sentiment_gpt_5_4_xhigh, sentiment_gpt_5_2_xhigh) and picks
    the first non-null value per article in priority order (newest first).

    Args:
        base_dir: directory containing year/month parquet files
        score_type: "sentiment" or "risk"
        target_col: output column name ("llm_sentiment" or "llm_risk")
    """
    import pyarrow.parquet as pq

    cfg = SCORE_SOURCES["polygon"]
    candidate_cols = cfg["sentiment_cols"] if score_type == "sentiment" else cfg["risk_cols"]

    print(f"  Loading Polygon {score_type} scores from {base_dir}")
    print(f"  Model priority (coalesce): {candidate_cols}")

    frames = []
    for root, _dirs, files in os.walk(base_dir):
        for f in sorted(files):
            if f.endswith(".parquet"):
                path = os.path.join(root, f)
                schema_cols = pq.read_schema(path).names
                # Read whichever candidate columns exist in this file
                available = [c for c in candidate_cols if c in schema_cols]
                if not available:
                    continue
                read_cols = ["published_at", "ticker"] + available
                df = pd.read_parquet(path, columns=read_cols)
                # Coalesce: first non-null in priority order
                score_series = pd.array([pd.NA] * len(df), dtype="Float64")
                for col in candidate_cols:
                    if col in df.columns:
                        mask = pd.isna(score_series)
                        score_series[mask] = df.loc[mask, col].values
                df["_score"] = score_series
                frames.append(df[["published_at", "ticker", "_score"]])

    if not frames:
        raise FileNotFoundError(
            f"No parquet files with any of {candidate_cols} found in {base_dir}. "
            f"Run score_ibkr_news.py --mode {score_type} first."
        )

    scores = pd.concat(frames, ignore_index=True)
    scores["Date"] = pd.to_datetime(scores["published_at"]).dt.tz_localize(None)
    scores = scores.rename(columns={"ticker": "tic", "_score": target_col})

    # Aggregate: daily mean per ticker (multiple articles per day)
    daily = scores.groupby([scores["Date"].dt.date, "tic"])[target_col].mean().reset_index()
    daily.columns = ["Date", "tic", target_col]
    daily["Date"] = pd.to_datetime(daily["Date"])
    # Some article rows can have missing scores; drop all-NaN daily groups.
    missing_daily = int(daily[target_col].isna().sum())
    if missing_daily:
        print(f"  Polygon: dropping {missing_daily} daily ticker rows with missing {score_type}")
        daily = daily.dropna(subset=[target_col]).copy()

    # Round to nearest integer (scores are 1-5)
    daily[target_col] = daily[target_col].round().astype(int)

    n_tickers = daily["tic"].nunique()
    n_dates = daily["Date"].nunique()
    print(f"  Polygon: {len(scores)} articles → {len(daily)} daily ticker-scores "
          f"({n_tickers} tickers, {n_dates} dates)")
    if n_tickers < 10 or n_dates < 30:
        print(f"  ⚠ Low coverage: only {n_tickers} tickers / {n_dates} dates. "
              f"Scoring may still be in progress.")
    return daily[["Date", "tic", target_col]]


# ── Price + feature pipeline ────────────────────────────────────


def download_prices(tickers, start_date, end_date):
    """Download OHLCV + compute technical indicators via yfinance."""
    print(f"\n  Downloading prices: {len(tickers)} tickers, {start_date} to {end_date}")

    # Filter out delisted tickers that cause yfinance errors
    active_tickers = [t for t in tickers if t != "SGEN"]

    df_raw = YahooDownloader(
        start_date=start_date,
        end_date=end_date,
        ticker_list=active_tickers,
    ).fetch_data()

    print(f"  Raw OHLCV: {len(df_raw)} rows, {df_raw['tic'].nunique()} tickers")

    # Add technical indicators
    fe = FeatureEngineer(
        use_technical_indicator=True,
        tech_indicator_list=INDICATORS,
        use_vix=True,
        use_turbulence=True,
        user_defined_feature=False,
    )
    processed = fe.preprocess_data(df_raw)

    # Build full date×ticker matrix with forward-fill per ticker
    list_ticker = processed["tic"].unique().tolist()
    list_date = list(pd.date_range(
        processed["date"].min(), processed["date"].max()
    ).astype(str))
    combination = list(itertools.product(list_date, list_ticker))

    processed_full = pd.DataFrame(
        combination, columns=["date", "tic"]
    ).merge(processed, on=["date", "tic"], how="left")

    processed_full = processed_full[processed_full["date"].isin(processed["date"])]
    processed_full = processed_full.sort_values(["tic", "date"])

    # Forward-fill within each ticker to avoid cross-ticker leakage
    non_key_cols = [c for c in processed_full.columns if c not in ("date", "tic")]
    processed_full[non_key_cols] = processed_full.groupby("tic")[non_key_cols].ffill()
    processed_full = processed_full.sort_values(["date", "tic"]).reset_index(drop=True)

    print(f"  Processed: {len(processed_full)} rows, {processed_full['tic'].nunique()} tickers")
    return processed_full


def merge_scores(price_df, score_df, target_col="llm_sentiment"):
    """Left-merge scores onto price data by (date, tic)."""
    price_df = price_df.copy()
    price_df["date"] = pd.to_datetime(price_df["date"])

    merged = price_df.merge(
        score_df[["Date", "tic", target_col]],
        left_on=["date", "tic"],
        right_on=["Date", "tic"],
        how="left",
    )
    merged.drop(columns=["Date"], inplace=True, errors="ignore")
    merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")

    scored = merged[target_col].notna().sum()
    total = len(merged)
    print(f"  Merged {target_col}: {scored}/{total} rows have scores "
          f"({scored / total * 100:.1f}%)")

    return merged


# ── Main ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Prepare training data from multiple LLM score sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflow — two-phase approach:

  Phase 1 (Validation): train on past, trade on future (out-of-sample backtest).
    train-end < trade-start to avoid look-ahead bias.

  Phase 2 (Production): after validation, retrain on ALL data for deployment.
    Use --train-only to output a single file covering the full date range.

Examples:

  # ── Phase 1: Validation split ──

  # Polygon: validate model generalizes (train 2022-2024, test 2025-2026)
  %(prog)s --source polygon --score-type both \\
           --train-start 2022-01-01 --train-end 2024-12-31 \\
           --trade-start 2025-01-01 --trade-end 2026-03-26

  # HuggingFace DeepSeek (train 2013-2018, test 2019-2023)
  %(prog)s --source huggingface --score-type both

  # Claude Opus sentiment + risk (same date defaults as HuggingFace)
  %(prog)s --source claude --model opus --score-type both

  # ── Phase 2: Full retrain for production ──

  # Polygon: train on ALL data after validation passes
  %(prog)s --source polygon --score-type both --train-only \\
           --train-start 2022-01-01 --train-end 2026-03-26

  # HuggingFace: full retrain
  %(prog)s --source huggingface --score-type both --train-only \\
           --train-start 2013-01-01 --train-end 2023-12-31
        """,
    )
    parser.add_argument(
        "--source", required=True,
        choices=["huggingface", "claude", "gpt5", "polygon"],
        help="Score data source",
    )
    parser.add_argument(
        "--model", default=None,
        help="Model variant (claude: opus/sonnet/haiku; gpt5: high/medium/low/minimal)",
    )
    parser.add_argument(
        "--score-type", default="sentiment",
        choices=["sentiment", "risk", "both"],
        help="Score type (default: sentiment). 'risk'/'both' include llm_risk for CPPO. "
             "Polygon risk requires scoring with score_ibkr_news.py --mode risk first.",
    )
    parser.add_argument("--train-start", default="2013-01-01", help="Training period start")
    parser.add_argument("--train-end", default="2018-12-31", help="Training period end")
    parser.add_argument("--trade-start", default="2019-01-01",
                        help="OOS backtest period start (ignored with --train-only)")
    parser.add_argument("--trade-end", default="2023-12-31",
                        help="OOS backtest period end (ignored with --train-only)")
    parser.add_argument(
        "--train-only", action="store_true",
        help="Production mode: output a single train CSV covering train-start to train-end. "
             "No trade split. Use after Phase 1 validation confirms the model works.",
    )
    parser.add_argument(
        "--output-dir", default="training/data_prep/output",
        help="Output directory for CSV files",
    )
    parser.add_argument(
        "--features", nargs="*", default=None,
        help="Enable derived features. No args = all defaults. "
             "Specific features: --features sentiment_7d_ma sentiment_momentum. "
             "Omit flag entirely to disable.",
    )
    args = parser.parse_args()

    # Validate model argument
    if args.source in ("claude", "gpt5") and not args.model:
        parser.error(f"--model is required for source={args.source}")

    os.makedirs(args.output_dir, exist_ok=True)

    # Build output filename tag
    if args.source == "huggingface":
        tag = f"deepseek_{args.score_type}"
    elif args.source == "polygon":
        suffix = f"_{args.score_type}" if args.score_type != "sentiment" else ""
        tag = f"polygon_multi{suffix}"
    else:
        # Include score_type in tag when risk/both (default sentiment omitted for brevity)
        suffix = f"_{args.score_type}" if args.score_type != "sentiment" else ""
        tag = f"{args.source}_{args.model}{suffix}"

    # Effective end date for price download
    price_end = args.train_end if args.train_only else args.trade_end

    print(f"\n{'=' * 60}")
    print(f"  Preparing training data: {tag}")
    if args.train_only:
        print(f"  Mode: FULL RETRAIN (production)")
        print(f"  Train: {args.train_start} → {args.train_end}")
    else:
        print(f"  Mode: VALIDATION SPLIT")
        print(f"  Train: {args.train_start} → {args.train_end}")
        print(f"  Trade: {args.trade_start} → {args.trade_end}")
    print(f"{'=' * 60}")

    # Step 1: Load scores
    print("\n[1/4] Loading scores...")

    sentiment_scores = None
    risk_scores = None

    if args.source == "huggingface":
        if args.score_type in ("sentiment", "both"):
            sentiment_scores = _load_huggingface_scores("sentiment", "llm_sentiment")
        if args.score_type in ("risk", "both"):
            risk_scores = _load_huggingface_scores("risk", "llm_risk")
    elif args.source in ("claude", "gpt5"):
        if args.score_type in ("sentiment", "both"):
            sentiment_scores = _load_model_scores(args.source, args.model, "sentiment", "llm_sentiment")
        if args.score_type in ("risk", "both"):
            risk_scores = _load_model_scores(args.source, args.model, "risk", "llm_risk")
    elif args.source == "polygon":
        base = SCORE_SOURCES["polygon"]["base_dir"]
        if args.score_type in ("sentiment", "both"):
            sentiment_scores = _load_polygon_scores(base, "sentiment", "llm_sentiment")
        if args.score_type in ("risk", "both"):
            risk_scores = _load_polygon_scores(base, "risk", "llm_risk")

    # Step 2: Determine tickers from scores
    print("\n[2/4] Determining ticker universe...")

    if args.source == "polygon":
        # Use tickers that appear in Polygon data
        ref_scores = sentiment_scores if sentiment_scores is not None else risk_scores
        score_tickers = ref_scores["tic"].unique().tolist()
        tickers = sorted(score_tickers)
        print(f"  Polygon tickers: {len(tickers)}")
    else:
        tickers = NASDAQ_100

    # Step 3: Download prices + features
    print("\n[3/4] Downloading prices and computing features...")
    price_data = download_prices(tickers, args.train_start, price_end)

    # Step 4: Merge scores and split
    print("\n[4/4] Merging scores and splitting...")

    merged = price_data

    # score_type == "risk" implies CPPO, which needs both sentiment and risk.
    # Load sentiment implicitly if only risk was requested.
    if args.score_type == "risk" and sentiment_scores is None:
        if args.source == "huggingface":
            sentiment_scores = _load_huggingface_scores("sentiment", "llm_sentiment")
        elif args.source in ("claude", "gpt5"):
            sentiment_scores = _load_model_scores(
                args.source, args.model, "sentiment", "llm_sentiment",
            )
        elif args.source == "polygon":
            sentiment_scores = _load_polygon_scores(
                SCORE_SOURCES["polygon"]["base_dir"], "sentiment", "llm_sentiment",
            )

    if sentiment_scores is not None:
        merged = merge_scores(merged, sentiment_scores, "llm_sentiment")

    if risk_scores is not None:
        merged = merge_scores(
            merged.assign(date=pd.to_datetime(merged["date"])),
            risk_scores, "llm_risk",
        )

    # Feature engineering: compute on full merged df before split
    # (so rolling windows can use train tail for trade head — no leakage)
    extra_cols = []
    scaler = None
    if args.features is not None:
        from training.data_prep.feature_engineering import engineer_features, FeatureScaler

        feat_list = args.features if args.features else None  # [] → None = defaults
        merged, extra_cols, feat_meta = engineer_features(merged, features=feat_list)
        print(f"  Derived features: {extra_cols}")

    # Split into train and trade
    train = data_split(merged, args.train_start, args.train_end)

    # Fill missing scores
    train["llm_sentiment"] = train["llm_sentiment"].fillna(0)
    if "llm_risk" in train.columns:
        train["llm_risk"] = train["llm_risk"].fillna(3)

    trade = None
    if not args.train_only:
        trade = data_split(merged, args.trade_start, args.trade_end)
        trade["llm_sentiment"] = trade["llm_sentiment"].fillna(0)
        if "llm_risk" in trade.columns:
            trade["llm_risk"] = trade["llm_risk"].fillna(3)

    # Fit scaler on train, transform both (or train only)
    if extra_cols:
        from training.data_prep.feature_engineering import FeatureScaler

        fit_period = f"{args.train_start} ~ {args.train_end}"
        scaler = FeatureScaler()
        scaler.fit(
            train, extra_cols,
            shift=feat_meta.get("shift", 1),
            imputation=feat_meta.get("imputation", {}),
            fit_period=fit_period,
        )
        scaler.transform(train, extra_cols)
        if trade is not None:
            scaler.transform(trade, extra_cols)
        scaler_path = os.path.join(args.output_dir, f"feature_scaler_{tag}.json")
        scaler.save(scaler_path)
        print(f"  Scaler fitted on train, saved: {scaler_path}")

    # Save
    train_path = os.path.join(args.output_dir, f"train_{tag}.csv")
    train.to_csv(train_path)

    print(f"\n{'=' * 60}")
    print(f"  Train: {train_path} ({len(train)} rows, {train['tic'].nunique()} tickers)")
    if trade is not None:
        trade_path = os.path.join(args.output_dir, f"trade_{tag}.csv")
        trade.to_csv(trade_path)
        print(f"  Trade: {trade_path} ({len(trade)} rows, {trade['tic'].nunique()} tickers)")
    if extra_cols:
        print(f"  Features: {extra_cols}")
        print(f"  Scaler: {os.path.join(args.output_dir, f'feature_scaler_{tag}.json')}")
    print(f"{'=' * 60}")
    feat_flag = " --features" if extra_cols else ""
    print(f"\nTo train PPO:")
    print(f"  python training/train_ppo_llm.py --data {train_path}{feat_flag}")
    if "llm_risk" in train.columns:
        print(f"To train CPPO:")
        print(f"  python training/train_cppo_llm_risk.py --data {train_path}{feat_flag}")


if __name__ == "__main__":
    main()
