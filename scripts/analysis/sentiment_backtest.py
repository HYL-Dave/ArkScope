#!/usr/bin/env python3
"""
Signal-Based Backtesting for LLM Sentiment Scores.

Implements multiple trading strategies based on sentiment scores and evaluates
performance using standard financial metrics.

Trading Strategies
==================

1. Long-Only Top (strategy_long_only_top)
-----------------------------------------
Rule:
- Daily: Buy all stocks with sentiment >= 5
- Equal weight or score-weighted allocation
- Sell next day

Use Case: Conservative approach, only go long on strong positive signals.

2. Long-Short (strategy_long_short)
-----------------------------------
Rule:
- Long: sentiment >= 5 (50% capital)
- Short: sentiment <= 1 (50% capital)
- Daily rebalancing

Use Case: Market-neutral strategy to test pure stock selection ability
by eliminating market beta exposure.

3. Score-Weighted (strategy_score_weighted)
-------------------------------------------
Rule:
- Score 1 -> weight -1 (short)
- Score 3 -> weight 0 (neutral)
- Score 5 -> weight +1 (long)

Use Case: Continuous signal utilization, positions scaled by conviction level.

Performance Metrics
===================

| Metric            | Description                         | Good Threshold      |
|-------------------|-------------------------------------|---------------------|
| Sharpe Ratio      | Excess return per unit risk         | > 1.0 good, > 2.0 excellent |
| Sortino Ratio     | Sharpe using only downside risk     | > Sharpe = good downside control |
| Max Drawdown      | Largest peak-to-trough decline      | < -20% acceptable   |
| Calmar Ratio      | Annual return / Max drawdown        | > 1.0 good          |
| Information Ratio | Excess return / Tracking error      | > 0.5 has alpha     |
| Win Rate          | % of profitable days                | > 50% with stability |
| Profit Factor     | Gross gains / Gross losses          | > 1.5 good          |

Usage
=====
    python scripts/analysis/sentiment_backtest.py --file <scoring_csv> --col <score_column>
    python scripts/analysis/sentiment_backtest.py --strategy long-short --output results.csv

See Also
--------
- validate_scoring_value.py: Validates predictive power before backtesting
- docs/analysis/SCORING_VALIDATION_METHODOLOGY.md: Full methodology documentation

Inspired by FinRL backtesting framework.
"""
import os
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# Paths
PRICE_DIR = Path("/mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_price/full_history/full_history")
SCORING_DIR = Path("/mnt/md0/finrl")


class PerformanceMetrics:
    """Calculate standard financial performance metrics."""

    @staticmethod
    def calculate_metrics(returns: pd.Series, rf_rate: float = 0.0) -> Dict:
        """
        Calculate comprehensive performance metrics.

        Args:
            returns: Daily returns series
            rf_rate: Annual risk-free rate (default 0)

        Returns:
            Dictionary of performance metrics
        """
        if len(returns) < 2:
            return {}

        # Clean data
        returns = returns.dropna()
        if len(returns) < 2:
            return {}

        # Basic metrics
        total_return = (1 + returns).prod() - 1
        n_days = len(returns)
        ann_factor = 252

        # Annualized return
        ann_return = (1 + total_return) ** (ann_factor / n_days) - 1

        # Volatility
        volatility = returns.std() * np.sqrt(ann_factor)

        # Sharpe Ratio
        excess_returns = returns - rf_rate / ann_factor
        sharpe = excess_returns.mean() / returns.std() * np.sqrt(ann_factor) if returns.std() > 0 else 0

        # Sortino Ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(ann_factor) if len(downside_returns) > 0 else 0
        sortino = ann_return / downside_std if downside_std > 0 else 0

        # Maximum Drawdown
        cum_returns = (1 + returns).cumprod()
        rolling_max = cum_returns.cummax()
        drawdown = (cum_returns - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        # Calmar Ratio
        calmar = ann_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # Win Rate
        win_rate = (returns > 0).mean()

        # Profit Factor
        gains = returns[returns > 0].sum()
        losses = abs(returns[returns < 0].sum())
        profit_factor = gains / losses if losses > 0 else np.inf

        # Information Ratio (assuming 0 benchmark)
        tracking_error = returns.std() * np.sqrt(ann_factor)
        info_ratio = ann_return / tracking_error if tracking_error > 0 else 0

        return {
            'total_return': total_return,
            'annual_return': ann_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'info_ratio': info_ratio,
            'n_trades': n_days,
        }


class SentimentBacktester:
    """Backtest sentiment-based trading strategies."""

    def __init__(
        self,
        initial_capital: float = 1_000_000,
        transaction_cost: float = 0.001,  # 0.1% per trade
        max_position_pct: float = 0.1,    # Max 10% per stock
    ):
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.max_position_pct = max_position_pct

    def load_data(self, scoring_file: str, score_col: str) -> pd.DataFrame:
        """Load and merge scoring data with prices."""
        # Load scores
        scores = pd.read_csv(scoring_file)
        scores = scores.rename(columns={'Stock_symbol': 'symbol', 'Date': 'date'})
        scores['date'] = pd.to_datetime(scores['date'].str.replace(' UTC', ''), errors='coerce')
        scores['date'] = scores['date'].dt.floor('D')
        scores = scores[['date', 'symbol', score_col]].dropna(subset=[score_col])
        scores[score_col] = scores[score_col].astype(int)

        # Load prices
        symbols = scores['symbol'].unique()
        all_prices = []

        for symbol in symbols:
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
            raise ValueError("No price data found")

        prices = pd.concat(all_prices, ignore_index=True)
        prices = prices.sort_values(['symbol', 'date'])

        # Calculate forward returns
        prices['fwd_ret_1d'] = prices.groupby('symbol')['adj close'].transform(
            lambda x: x.shift(-1) / x - 1
        )

        # Merge
        merged = scores.merge(prices, on=['date', 'symbol'], how='inner')
        return merged

    def strategy_long_only_top(
        self,
        data: pd.DataFrame,
        score_col: str,
        min_score: int = 5,
        equal_weight: bool = True
    ) -> pd.DataFrame:
        """
        Long-only strategy: Buy stocks with score >= min_score.

        Args:
            data: Merged data with scores and returns
            score_col: Score column name
            min_score: Minimum score to buy
            equal_weight: If True, equal weight; else score-weighted

        Returns:
            DataFrame with daily portfolio returns
        """
        results = []

        for date in sorted(data['date'].unique()):
            day_data = data[data['date'] == date].copy()

            # Filter for high scores
            signals = day_data[day_data[score_col] >= min_score]

            if len(signals) == 0:
                results.append({'date': date, 'return': 0, 'n_positions': 0})
                continue

            # Calculate weights
            if equal_weight:
                weights = 1 / len(signals)
            else:
                # Score-weighted
                weights = signals[score_col] / signals[score_col].sum()

            # Portfolio return (before costs)
            port_return = (signals['fwd_ret_1d'] * weights).sum()

            # Transaction costs (simplified: assume full turnover)
            cost = self.transaction_cost * 2  # Buy and sell

            results.append({
                'date': date,
                'return': port_return - cost,
                'n_positions': len(signals)
            })

        return pd.DataFrame(results)

    def strategy_long_short(
        self,
        data: pd.DataFrame,
        score_col: str,
        long_threshold: int = 5,
        short_threshold: int = 1
    ) -> pd.DataFrame:
        """
        Long-Short strategy: Long high scores, short low scores.

        Args:
            data: Merged data
            score_col: Score column
            long_threshold: Score >= this for long
            short_threshold: Score <= this for short

        Returns:
            DataFrame with daily returns
        """
        results = []

        for date in sorted(data['date'].unique()):
            day_data = data[data['date'] == date].copy()

            longs = day_data[day_data[score_col] >= long_threshold]
            shorts = day_data[day_data[score_col] <= short_threshold]

            long_ret = longs['fwd_ret_1d'].mean() if len(longs) > 0 else 0
            short_ret = shorts['fwd_ret_1d'].mean() if len(shorts) > 0 else 0

            # Long-short return (50/50 allocation)
            port_return = 0.5 * long_ret - 0.5 * short_ret

            # Transaction costs
            n_trades = len(longs) + len(shorts)
            cost = self.transaction_cost * 2 * (n_trades / max(len(day_data), 1))

            results.append({
                'date': date,
                'return': port_return - cost,
                'n_long': len(longs),
                'n_short': len(shorts)
            })

        return pd.DataFrame(results)

    def strategy_score_weighted(
        self,
        data: pd.DataFrame,
        score_col: str
    ) -> pd.DataFrame:
        """
        Score-weighted strategy: Weight positions by normalized score.

        Score 5 -> long weight
        Score 1 -> short weight
        Score 3 -> neutral

        Returns:
            DataFrame with daily returns
        """
        results = []

        for date in sorted(data['date'].unique()):
            day_data = data[data['date'] == date].copy()

            # Normalize scores to [-1, 1]
            # Score 1 -> -1, Score 3 -> 0, Score 5 -> +1
            day_data['weight'] = (day_data[score_col] - 3) / 2

            # Normalize weights to sum to 1 (absolute)
            total_abs_weight = day_data['weight'].abs().sum()
            if total_abs_weight > 0:
                day_data['norm_weight'] = day_data['weight'] / total_abs_weight
            else:
                day_data['norm_weight'] = 0

            # Portfolio return
            port_return = (day_data['fwd_ret_1d'] * day_data['norm_weight']).sum()

            # Transaction costs
            cost = self.transaction_cost * 2

            results.append({
                'date': date,
                'return': port_return - cost,
                'n_positions': len(day_data[day_data['weight'] != 0])
            })

        return pd.DataFrame(results)

    def strategy_quintile_spread(
        self,
        data: pd.DataFrame,
        score_col: str
    ) -> pd.DataFrame:
        """
        Quintile spread strategy: Long top quintile, short bottom quintile.
        Based on daily cross-sectional rankings.
        """
        results = []

        for date in sorted(data['date'].unique()):
            day_data = data[data['date'] == date].copy()

            if len(day_data) < 5:
                results.append({'date': date, 'return': 0})
                continue

            # Rank by score
            day_data['rank'] = day_data[score_col].rank(pct=True)

            # Top and bottom 20%
            top = day_data[day_data['rank'] >= 0.8]
            bottom = day_data[day_data['rank'] <= 0.2]

            long_ret = top['fwd_ret_1d'].mean() if len(top) > 0 else 0
            short_ret = bottom['fwd_ret_1d'].mean() if len(bottom) > 0 else 0

            port_return = 0.5 * long_ret - 0.5 * short_ret

            results.append({
                'date': date,
                'return': port_return,
                'n_long': len(top),
                'n_short': len(bottom)
            })

        return pd.DataFrame(results)


def run_backtest(
    scoring_file: str,
    score_col: str,
    output_dir: Optional[str] = None
) -> Dict:
    """Run full backtest suite and generate report."""

    print(f"\n{'='*70}")
    print(f"BACKTEST: {os.path.basename(scoring_file)}")
    print(f"{'='*70}")

    backtester = SentimentBacktester()

    # Load data
    data = backtester.load_data(scoring_file, score_col)
    print(f"Loaded {len(data):,} records | {data['symbol'].nunique()} symbols")
    print(f"Date range: {data['date'].min().date()} to {data['date'].max().date()}")

    # Run strategies
    strategies = {}

    # 1. Long-only Score 5
    print("\n📈 Running Long-Only Score 5 strategy...")
    strat1 = backtester.strategy_long_only_top(data, score_col, min_score=5)
    strategies['Long_Score5'] = strat1

    # 2. Long-only Score 4+
    print("📈 Running Long-Only Score 4+ strategy...")
    strat2 = backtester.strategy_long_only_top(data, score_col, min_score=4)
    strategies['Long_Score4+'] = strat2

    # 3. Long-Short (5 vs 1)
    print("📊 Running Long-Short (5 vs 1) strategy...")
    strat3 = backtester.strategy_long_short(data, score_col, long_threshold=5, short_threshold=1)
    strategies['LongShort_5v1'] = strat3

    # 4. Long-Short (4+ vs 2-)
    print("📊 Running Long-Short (4+ vs 2-) strategy...")
    strat4 = backtester.strategy_long_short(data, score_col, long_threshold=4, short_threshold=2)
    strategies['LongShort_4v2'] = strat4

    # 5. Score-weighted
    print("⚖️ Running Score-Weighted strategy...")
    strat5 = backtester.strategy_score_weighted(data, score_col)
    strategies['ScoreWeighted'] = strat5

    # Calculate metrics for each strategy
    print("\n" + "="*70)
    print("PERFORMANCE SUMMARY")
    print("="*70)

    results = {}
    for name, strat_df in strategies.items():
        returns = strat_df['return'].dropna()
        metrics = PerformanceMetrics.calculate_metrics(returns)
        results[name] = metrics

        if not metrics:
            continue

        print(f"\n📊 {name}:")
        print(f"   Total Return:   {metrics['total_return']*100:+.2f}%")
        print(f"   Annual Return:  {metrics['annual_return']*100:+.2f}%")
        print(f"   Volatility:     {metrics['volatility']*100:.2f}%")
        print(f"   Sharpe Ratio:   {metrics['sharpe_ratio']:.3f}")
        print(f"   Sortino Ratio:  {metrics['sortino_ratio']:.3f}")
        print(f"   Max Drawdown:   {metrics['max_drawdown']*100:.2f}%")
        print(f"   Calmar Ratio:   {metrics['calmar_ratio']:.3f}")
        print(f"   Win Rate:       {metrics['win_rate']*100:.1f}%")

    # Equity curves
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

        # Save strategy returns
        for name, strat_df in strategies.items():
            strat_df['cum_return'] = (1 + strat_df['return']).cumprod()
            strat_df.to_csv(f"{output_dir}/{name}_returns.csv", index=False)

        # Save summary
        summary_df = pd.DataFrame(results).T
        summary_df.to_csv(f"{output_dir}/backtest_summary.csv")
        print(f"\n💾 Results saved to: {output_dir}/")

    return results


def compare_models(output_dir: str = "docs/analysis/backtest_results"):
    """Compare backtest results across multiple scoring models."""

    scoring_files = [
        ("gpt-5/sentiment/sentiment_gpt-5_high_by_o3_summary.csv", "sentiment_deepseek"),
        ("o3/sentiment/sentiment_o3_high_4.csv", "sentiment_deepseek"),
        ("gpt-4.1-mini/sentiment/sentiment_gpt-4.1-mini_by_o3_summary.csv", "sentiment_deepseek"),
    ]

    all_results = {}

    for rel_path, score_col in scoring_files:
        full_path = SCORING_DIR / rel_path
        if not full_path.exists():
            print(f"Skipping {rel_path} (not found)")
            continue

        model_name = rel_path.split('/')[0]
        results = run_backtest(str(full_path), score_col)
        all_results[model_name] = results

    # Comparison table
    print("\n" + "="*70)
    print("MODEL COMPARISON (Long-Short 5v1 Strategy)")
    print("="*70)

    comparison = []
    for model, strategies in all_results.items():
        if 'LongShort_5v1' in strategies:
            metrics = strategies['LongShort_5v1']
            comparison.append({
                'Model': model,
                'Annual Return': f"{metrics['annual_return']*100:.2f}%",
                'Sharpe': f"{metrics['sharpe_ratio']:.3f}",
                'Max DD': f"{metrics['max_drawdown']*100:.2f}%",
                'Win Rate': f"{metrics['win_rate']*100:.1f}%"
            })

    if comparison:
        df = pd.DataFrame(comparison)
        print(df.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description="Backtest sentiment scoring strategies")
    parser.add_argument("--file", help="Specific scoring file to backtest")
    parser.add_argument("--score-col", default="sentiment_deepseek")
    parser.add_argument("--output", default="docs/analysis/backtest_results")
    parser.add_argument("--compare", action="store_true", help="Compare multiple models")
    args = parser.parse_args()

    if args.compare:
        compare_models(args.output)
    elif args.file:
        run_backtest(args.file, args.score_col, args.output)
    else:
        # Default: backtest best model
        default_file = SCORING_DIR / "gpt-5/sentiment/sentiment_gpt-5_high_by_o3_summary.csv"
        if default_file.exists():
            run_backtest(str(default_file), "sentiment_deepseek", args.output)


if __name__ == "__main__":
    main()