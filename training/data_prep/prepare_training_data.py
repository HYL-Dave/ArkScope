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
        "score_col": "sentiment_gpt_5_2_xhigh",
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


def _load_polygon_scores(base_dir):
    """Load Polygon news scores from monthly Parquet files."""
    print(f"  Loading Polygon scores from {base_dir}")
    frames = []
    for root, _dirs, files in os.walk(base_dir):
        for f in sorted(files):
            if f.endswith(".parquet"):
                path = os.path.join(root, f)
                df = pd.read_parquet(path, columns=["published_at", "ticker", "sentiment_gpt_5_2_xhigh"])
                frames.append(df)

    if not frames:
        raise FileNotFoundError(f"No .parquet files found in {base_dir}")

    scores = pd.concat(frames, ignore_index=True)
    scores["Date"] = pd.to_datetime(scores["published_at"]).dt.tz_localize(None)
    scores = scores.rename(columns={
        "ticker": "tic",
        "sentiment_gpt_5_2_xhigh": "llm_sentiment",
    })

    # Aggregate: daily mean per ticker (multiple articles per day)
    daily = scores.groupby([scores["Date"].dt.date, "tic"])["llm_sentiment"].mean().reset_index()
    daily.columns = ["Date", "tic", "llm_sentiment"]
    daily["Date"] = pd.to_datetime(daily["Date"])
    # Round to nearest integer (scores are 1-5)
    daily["llm_sentiment"] = daily["llm_sentiment"].round().astype(int)

    print(f"  Polygon: {len(scores)} articles → {len(daily)} daily ticker-scores")
    return daily[["Date", "tic", "llm_sentiment"]]


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
Examples:
  # Claude Opus sentiment only (for PPO)
  %(prog)s --source claude --model opus

  # Claude Opus sentiment + risk (for CPPO)
  %(prog)s --source claude --model opus --score-type both

  # GPT-5 high effort sentiment only
  %(prog)s --source gpt5 --model high

  # GPT-5 high effort sentiment + risk (for CPPO)
  %(prog)s --source gpt5 --model high --score-type both

  # HuggingFace DeepSeek sentiment (original pipeline)
  %(prog)s --source huggingface --score-type sentiment

  # HuggingFace sentiment + risk (for CPPO)
  %(prog)s --source huggingface --score-type both

  # Polygon modern data (2022-2026, sentiment only)
  %(prog)s --source polygon --train-start 2022-06-01 --train-end 2024-12-31 \\
           --trade-start 2025-01-01 --trade-end 2026-02-28
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
             "Not supported for polygon (sentiment only).",
    )
    parser.add_argument("--train-start", default="2013-01-01", help="Training period start")
    parser.add_argument("--train-end", default="2018-12-31", help="Training period end")
    parser.add_argument("--trade-start", default="2019-01-01", help="Trading/test period start")
    parser.add_argument("--trade-end", default="2023-12-31", help="Trading/test period end")
    parser.add_argument(
        "--output-dir", default="training/data_prep/output",
        help="Output directory for CSV files",
    )
    args = parser.parse_args()

    # Validate model argument
    if args.source in ("claude", "gpt5") and not args.model:
        parser.error(f"--model is required for source={args.source}")

    # Polygon only has sentiment scores
    if args.source == "polygon" and args.score_type != "sentiment":
        parser.error(
            f"--score-type={args.score_type} is not supported for --source=polygon. "
            "Polygon data only provides sentiment scores."
        )

    os.makedirs(args.output_dir, exist_ok=True)

    # Build output filename tag
    if args.source == "huggingface":
        tag = f"deepseek_{args.score_type}"
    elif args.source == "polygon":
        tag = "polygon_gpt52xhigh"
    else:
        # Include score_type in tag when risk/both (default sentiment omitted for brevity)
        suffix = f"_{args.score_type}" if args.score_type != "sentiment" else ""
        tag = f"{args.source}_{args.model}{suffix}"

    print(f"\n{'=' * 60}")
    print(f"  Preparing training data: {tag}")
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
        sentiment_scores = _load_polygon_scores(SCORE_SOURCES["polygon"]["base_dir"])

    # Step 2: Determine tickers from scores
    print("\n[2/4] Determining ticker universe...")

    if args.source == "polygon":
        # Use tickers that appear in Polygon data
        score_tickers = sentiment_scores["tic"].unique().tolist()
        tickers = sorted(score_tickers)
        print(f"  Polygon tickers: {len(tickers)}")
    else:
        tickers = NASDAQ_100

    # Step 3: Download prices + features
    print("\n[3/4] Downloading prices and computing features...")
    price_data = download_prices(tickers, args.train_start, args.trade_end)

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

    if sentiment_scores is not None:
        merged = merge_scores(merged, sentiment_scores, "llm_sentiment")

    if risk_scores is not None:
        merged = merge_scores(
            merged.assign(date=pd.to_datetime(merged["date"])),
            risk_scores, "llm_risk",
        )

    # Split into train and trade
    train = data_split(merged, args.train_start, args.train_end)
    trade = data_split(merged, args.trade_start, args.trade_end)

    # Fill missing scores
    train["llm_sentiment"] = train["llm_sentiment"].fillna(0)
    trade["llm_sentiment"] = trade["llm_sentiment"].fillna(0)
    if "llm_risk" in train.columns:
        train["llm_risk"] = train["llm_risk"].fillna(3)
        trade["llm_risk"] = trade["llm_risk"].fillna(3)

    # Save
    train_path = os.path.join(args.output_dir, f"train_{tag}.csv")
    trade_path = os.path.join(args.output_dir, f"trade_{tag}.csv")
    train.to_csv(train_path)
    trade.to_csv(trade_path)

    print(f"\n{'=' * 60}")
    print(f"  Train: {train_path} ({len(train)} rows, {train['tic'].nunique()} tickers)")
    print(f"  Trade: {trade_path} ({len(trade)} rows, {trade['tic'].nunique()} tickers)")
    print(f"{'=' * 60}")
    print(f"\nTo train PPO:")
    print(f"  python training/train_ppo_llm.py --data {train_path}")
    if "llm_risk" in train.columns:
        print(f"To train CPPO:")
        print(f"  python training/train_cppo_llm_risk.py --data {train_path}")


if __name__ == "__main__":
    main()
