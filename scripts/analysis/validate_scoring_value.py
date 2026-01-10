#!/usr/bin/env python3
"""
Validate the predictive value of LLM sentiment/risk scores.

This script uses four standard quantitative finance methods to validate
whether LLM-generated sentiment/risk scores have predictive value.

Methodology
===========

1. Correlation Analysis (Spearman)
----------------------------------
Question: Do stocks with higher sentiment scores actually go up?

Method:
- Calculate Spearman correlation between sentiment_score and forward_return
- Spearman is more robust for non-linear relationships than Pearson
- Tests 1-day, 2-day, 5-day, and 10-day forward returns

Interpretation:
- r > 0.05 with p < 0.05 -> Statistically significant positive relationship
- |r| < 0.02 -> No predictive power

2. Hit Rate Analysis
--------------------
Question: Do scores of 4-5 correctly predict price increases?

Method:
- bullish_hit_rate: % of score 4-5 news where next-day price actually rose
- bearish_hit_rate: % of score 1-2 news where next-day price actually fell

Interpretation:
- Hit Rate > 55% -> Has reference value
- Hit Rate = 50% -> Same as coin flip, no predictive power

3. Information Coefficient (IC) - Industry Standard
---------------------------------------------------
Question: Can scores reliably distinguish "big gainers" from "small gainers"?

Method:
- Daily calculation: Spearman correlation of score rank vs return rank
- Aggregate mean and std of IC across all days
- IC IR = mean(IC) / std(IC) -> Signal stability metric

Interpretation (Industry Standards):
- |IC| > 0.05 -> Excellent factor
- |IC| > 0.02 -> Usable factor
- |IC| < 0.01 -> Ineffective factor
- IC IR > 0.5 -> Stable signal

4. Quintile Analysis
--------------------
Question: Do stocks scored 1-5 show clearly different returns?

Method:
- Group all news by score 1-5
- Calculate mean return, std, Sharpe Ratio for each group

Ideal Result:
Score 1: -0.3% mean return
Score 2: -0.1%
Score 3:  0.0%
Score 4: +0.1%
Score 5: +0.3%
-> Should show monotonic increasing relationship

Usage
=====
    python scripts/analysis/validate_scoring_value.py --file <scoring_csv> --col <score_column>
    python scripts/analysis/validate_scoring_value.py --task sentiment --model o3

See Also
--------
- sentiment_backtest.py: Implements trading strategies based on scores
- docs/analysis/SCORING_VALIDATION_METHODOLOGY.md: Full methodology documentation
"""
import os
import argparse
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Paths
PRICE_DIR = Path("/mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_price/full_history/full_history")
SCORING_DIR = Path("/mnt/md0/finrl")


def load_price_data(symbols: list) -> pd.DataFrame:
    """Load and combine price data for given symbols."""
    all_prices = []

    for symbol in symbols:
        # Try exact match first, then case-insensitive
        csv_path = PRICE_DIR / f"{symbol}.csv"
        if not csv_path.exists():
            csv_path = PRICE_DIR / f"{symbol.lower()}.csv"
        if not csv_path.exists():
            continue

        df = pd.read_csv(csv_path)
        df['symbol'] = symbol.upper()
        df['date'] = pd.to_datetime(df['date'])
        all_prices.append(df[['date', 'symbol', 'close', 'adj close']])

    if not all_prices:
        return pd.DataFrame()

    prices = pd.concat(all_prices, ignore_index=True)
    prices = prices.sort_values(['symbol', 'date'])

    # Calculate forward returns
    for days in [1, 2, 5, 10]:
        prices[f'fwd_ret_{days}d'] = prices.groupby('symbol')['adj close'].transform(
            lambda x: x.shift(-days) / x - 1
        )

    return prices


def load_scoring_data(scoring_file: str, score_col: str) -> pd.DataFrame:
    """Load scoring data with date and symbol."""
    df = pd.read_csv(scoring_file)

    # Standardize column names
    df = df.rename(columns={
        'Stock_symbol': 'symbol',
        'Date': 'date'
    })

    # Parse date
    df['date'] = pd.to_datetime(df['date'].str.replace(' UTC', ''), errors='coerce')
    df['date'] = df['date'].dt.date
    df['date'] = pd.to_datetime(df['date'])

    # Keep only needed columns
    cols = ['date', 'symbol', score_col]
    if 'Article_title' in df.columns:
        cols.append('Article_title')

    df = df[cols].dropna(subset=[score_col])
    df[score_col] = df[score_col].astype(int)

    return df


def merge_scores_with_prices(scores: pd.DataFrame, prices: pd.DataFrame, score_col: str) -> pd.DataFrame:
    """Merge scoring data with price data."""
    merged = scores.merge(
        prices,
        on=['date', 'symbol'],
        how='inner'
    )
    return merged


def calculate_correlation(df: pd.DataFrame, score_col: str) -> dict:
    """Calculate correlation between scores and forward returns."""
    results = {}

    for days in [1, 2, 5, 10]:
        ret_col = f'fwd_ret_{days}d'
        if ret_col not in df.columns:
            continue

        valid = df[[score_col, ret_col]].dropna()
        if len(valid) < 30:
            continue

        corr, pval = stats.spearmanr(valid[score_col], valid[ret_col])
        results[f'{days}d'] = {
            'correlation': corr,
            'p_value': pval,
            'n_samples': len(valid),
            'significant': pval < 0.05
        }

    return results


def calculate_hit_rate(df: pd.DataFrame, score_col: str, is_sentiment: bool = True) -> dict:
    """Calculate directional prediction accuracy."""
    results = {}

    for days in [1, 2, 5]:
        ret_col = f'fwd_ret_{days}d'
        if ret_col not in df.columns:
            continue

        valid = df[[score_col, ret_col]].dropna()

        if is_sentiment:
            # Sentiment: 4,5 = bullish (predict up), 1,2 = bearish (predict down)
            bullish = valid[valid[score_col] >= 4]
            bearish = valid[valid[score_col] <= 2]

            bullish_hit = (bullish[ret_col] > 0).mean() if len(bullish) > 0 else np.nan
            bearish_hit = (bearish[ret_col] < 0).mean() if len(bearish) > 0 else np.nan
        else:
            # Risk: 1,2 = low risk (predict up/stable), 4,5 = high risk (predict down)
            low_risk = valid[valid[score_col] <= 2]
            high_risk = valid[valid[score_col] >= 4]

            bullish_hit = (low_risk[ret_col] > 0).mean() if len(low_risk) > 0 else np.nan
            bearish_hit = (high_risk[ret_col] < 0).mean() if len(high_risk) > 0 else np.nan

        results[f'{days}d'] = {
            'bullish_hit_rate': bullish_hit,
            'bearish_hit_rate': bearish_hit,
            'n_bullish': len(bullish) if is_sentiment else len(low_risk),
            'n_bearish': len(bearish) if is_sentiment else len(high_risk)
        }

    return results


def calculate_ic(df: pd.DataFrame, score_col: str) -> dict:
    """Calculate Information Coefficient (rank correlation) by date."""
    results = {}

    for days in [1, 2, 5]:
        ret_col = f'fwd_ret_{days}d'
        if ret_col not in df.columns:
            continue

        # Calculate IC per date, then average
        daily_ic = df.groupby('date').apply(
            lambda x: stats.spearmanr(x[score_col], x[ret_col])[0]
            if len(x.dropna(subset=[score_col, ret_col])) >= 5 else np.nan
        ).dropna()

        if len(daily_ic) < 10:
            continue

        results[f'{days}d'] = {
            'mean_ic': daily_ic.mean(),
            'std_ic': daily_ic.std(),
            'ic_ir': daily_ic.mean() / daily_ic.std() if daily_ic.std() > 0 else 0,  # IC Information Ratio
            't_stat': daily_ic.mean() / (daily_ic.std() / np.sqrt(len(daily_ic))),
            'n_days': len(daily_ic),
            'pct_positive': (daily_ic > 0).mean()
        }

    return results


def quintile_analysis(df: pd.DataFrame, score_col: str) -> pd.DataFrame:
    """Analyze returns by score quintile."""
    results = []

    for days in [1, 2, 5]:
        ret_col = f'fwd_ret_{days}d'
        if ret_col not in df.columns:
            continue

        for score in range(1, 6):
            subset = df[df[score_col] == score]
            if len(subset) < 10:
                continue

            results.append({
                'horizon': f'{days}d',
                'score': score,
                'mean_return': subset[ret_col].mean(),
                'median_return': subset[ret_col].median(),
                'std_return': subset[ret_col].std(),
                'n_samples': len(subset),
                'sharpe': subset[ret_col].mean() / subset[ret_col].std() * np.sqrt(252/days) if subset[ret_col].std() > 0 else 0
            })

    return pd.DataFrame(results)


def analyze_single_file(scoring_file: str, score_col: str, is_sentiment: bool = True) -> dict:
    """Run full analysis on a single scoring file."""
    print(f"\nAnalyzing: {os.path.basename(scoring_file)}")
    print(f"Score column: {score_col}")

    # Load data
    scores = load_scoring_data(scoring_file, score_col)
    print(f"Loaded {len(scores)} scored records")

    symbols = scores['symbol'].unique().tolist()
    prices = load_price_data(symbols)
    print(f"Loaded prices for {prices['symbol'].nunique()} symbols")

    # Merge
    merged = merge_scores_with_prices(scores, prices, score_col)
    print(f"Merged dataset: {len(merged)} records")

    if len(merged) < 100:
        print("WARNING: Too few merged records for reliable analysis")
        return None

    # Run analyses
    results = {
        'file': os.path.basename(scoring_file),
        'score_col': score_col,
        'n_records': len(merged),
        'n_symbols': merged['symbol'].nunique(),
        'date_range': f"{merged['date'].min().date()} to {merged['date'].max().date()}",
        'correlation': calculate_correlation(merged, score_col),
        'hit_rate': calculate_hit_rate(merged, score_col, is_sentiment),
        'ic': calculate_ic(merged, score_col),
        'quintile': quintile_analysis(merged, score_col)
    }

    return results


def print_results(results: dict):
    """Pretty print analysis results."""
    print("\n" + "="*70)
    print(f"VALIDATION RESULTS: {results['file']}")
    print(f"Score Column: {results['score_col']}")
    print(f"Records: {results['n_records']:,} | Symbols: {results['n_symbols']} | {results['date_range']}")
    print("="*70)

    # Correlation
    print("\n📊 CORRELATION ANALYSIS (Spearman)")
    print("-" * 50)
    for horizon, data in results['correlation'].items():
        sig = "✅" if data['significant'] else "❌"
        print(f"  {horizon}: r={data['correlation']:.4f} (p={data['p_value']:.4f}) {sig} n={data['n_samples']:,}")

    # Hit Rate
    print("\n🎯 HIT RATE ANALYSIS")
    print("-" * 50)
    for horizon, data in results['hit_rate'].items():
        bull_pct = data['bullish_hit_rate'] * 100 if not np.isnan(data['bullish_hit_rate']) else 0
        bear_pct = data['bearish_hit_rate'] * 100 if not np.isnan(data['bearish_hit_rate']) else 0
        print(f"  {horizon}: Bullish={bull_pct:.1f}% (n={data['n_bullish']}) | Bearish={bear_pct:.1f}% (n={data['n_bearish']})")

    # IC
    print("\n📈 INFORMATION COEFFICIENT (IC)")
    print("-" * 50)
    for horizon, data in results['ic'].items():
        quality = "Good" if abs(data['mean_ic']) > 0.02 else "Weak" if abs(data['mean_ic']) > 0.01 else "Poor"
        print(f"  {horizon}: IC={data['mean_ic']:.4f} ± {data['std_ic']:.4f} | IR={data['ic_ir']:.2f} | t={data['t_stat']:.2f} | {quality}")
        print(f"       {data['pct_positive']*100:.1f}% positive IC days (n={data['n_days']})")

    # Quintile
    print("\n📊 QUINTILE ANALYSIS (Mean Returns by Score)")
    print("-" * 50)
    quintile_df = results['quintile']
    if len(quintile_df) > 0:
        for horizon in ['1d', '2d', '5d']:
            subset = quintile_df[quintile_df['horizon'] == horizon]
            if len(subset) == 0:
                continue
            print(f"  {horizon}:")
            for _, row in subset.iterrows():
                bar = "█" * int(abs(row['mean_return']) * 1000)
                sign = "+" if row['mean_return'] > 0 else ""
                print(f"    Score {int(row['score'])}: {sign}{row['mean_return']*100:.3f}% | Sharpe={row['sharpe']:.2f} | n={row['n_samples']:,}")


def find_scoring_files() -> list:
    """Find all scoring files to analyze."""
    files = []

    # Define scoring files to analyze
    patterns = [
        # gpt-5
        ("gpt-5/sentiment/sentiment_gpt-5_high_by_o3_summary.csv", "sentiment_deepseek", True),
        ("gpt-5/risk/risk_gpt-5_high_by_o3_summary.csv", "risk_deepseek", False),
        # o3
        ("o3/sentiment/sentiment_o3_high_4.csv", "sentiment_deepseek", True),
        ("o3/risk/risk_o3_medium_2.csv", "risk_deepseek", False),
        # gpt-5-mini
        ("gpt-5-mini/sentiment/sentiment_gpt-5-mini_with_R_high_V_low_by_gpt-5_summary.csv", "sentiment_deepseek", True),
        ("gpt-5-mini/risk/risk_gpt-5-mini_with_R_high_V_low_by_gpt-5_summary.csv", "risk_deepseek", False),
        # gpt-4.1-mini
        ("gpt-4.1-mini/sentiment/sentiment_gpt-4.1-mini_by_o3_summary.csv", "sentiment_deepseek", True),
        ("gpt-4.1-mini/risk/risk_gpt-4.1-mini_by_o3_summary.csv", "risk_deepseek", False),
        # Claude
        ("claude/sentiment_haiku_by_gpt5_summary.csv", "sentiment_claude", True),
        ("claude/risk_haiku_by_gpt5_summary.csv", "risk_claude", False),
        ("claude/sentiment_sonnet_by_gpt5_summary.csv", "sentiment_claude", True),
        ("claude/risk_sonnet_by_gpt5_summary.csv", "risk_claude", False),
    ]

    for rel_path, score_col, is_sentiment in patterns:
        full_path = SCORING_DIR / rel_path
        if full_path.exists():
            files.append((str(full_path), score_col, is_sentiment))

    return files


def main():
    parser = argparse.ArgumentParser(description="Validate LLM scoring predictive value")
    parser.add_argument("--file", help="Specific scoring file to analyze")
    parser.add_argument("--score-col", default="sentiment_deepseek", help="Score column name")
    parser.add_argument("--sentiment", action="store_true", help="Treat as sentiment (vs risk)")
    parser.add_argument("--all", action="store_true", help="Analyze all known scoring files")
    parser.add_argument("--output", help="Save results to CSV")
    args = parser.parse_args()

    all_results = []

    if args.file:
        results = analyze_single_file(args.file, args.score_col, args.sentiment)
        if results:
            print_results(results)
            all_results.append(results)
    elif args.all:
        files = find_scoring_files()
        print(f"Found {len(files)} scoring files to analyze")

        for file_path, score_col, is_sentiment in files:
            try:
                results = analyze_single_file(file_path, score_col, is_sentiment)
                if results:
                    print_results(results)
                    all_results.append(results)
            except Exception as e:
                print(f"ERROR analyzing {file_path}: {e}")
    else:
        # Default: analyze one representative file
        default_file = SCORING_DIR / "gpt-5/sentiment/sentiment_gpt-5_high_by_o3_summary.csv"
        if default_file.exists():
            results = analyze_single_file(str(default_file), "sentiment_deepseek", True)
            if results:
                print_results(results)
                all_results.append(results)

    # Summary comparison if multiple files
    if len(all_results) > 1:
        print("\n" + "="*70)
        print("SUMMARY COMPARISON")
        print("="*70)

        summary = []
        for r in all_results:
            row = {
                'file': r['file'][:40],
                'n': r['n_records'],
            }
            # Add 1d IC
            if '1d' in r['ic']:
                row['IC_1d'] = r['ic']['1d']['mean_ic']
            # Add 1d correlation
            if '1d' in r['correlation']:
                row['Corr_1d'] = r['correlation']['1d']['correlation']
            # Add hit rates
            if '1d' in r['hit_rate']:
                row['Bull_HR'] = r['hit_rate']['1d']['bullish_hit_rate']
                row['Bear_HR'] = r['hit_rate']['1d']['bearish_hit_rate']
            summary.append(row)

        summary_df = pd.DataFrame(summary)
        print(summary_df.to_string(index=False))

    if args.output and all_results:
        # Save detailed results
        output_data = []
        for r in all_results:
            base = {
                'file': r['file'],
                'score_col': r['score_col'],
                'n_records': r['n_records'],
                'n_symbols': r['n_symbols'],
            }
            for horizon in ['1d', '2d', '5d']:
                if horizon in r['correlation']:
                    base[f'corr_{horizon}'] = r['correlation'][horizon]['correlation']
                if horizon in r['ic']:
                    base[f'ic_{horizon}'] = r['ic'][horizon]['mean_ic']
                if horizon in r['hit_rate']:
                    base[f'bull_hr_{horizon}'] = r['hit_rate'][horizon]['bullish_hit_rate']
                    base[f'bear_hr_{horizon}'] = r['hit_rate'][horizon]['bearish_hit_rate']
            output_data.append(base)

        pd.DataFrame(output_data).to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()