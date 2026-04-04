#!/usr/bin/env python3
"""
Ensemble backtest: combine PPO + SAC + TD3 actions via Sharpe-weighted voting.

Loads multiple trained SB3 models, runs them on the same trade data,
and combines their actions using validation-Sharpe-weighted averaging.

The ensemble approach is based on FinRL Contest results (arXiv:2501.10709)
which showed MDD improvement via model combination.

Usage:
    # Basic: equal-weight average
    python training/backtest_ensemble.py \
      --data trade.csv \
      --models model1.zip model2.zip model3.zip

    # With Sharpe weighting (provide validation Sharpe for each model)
    python training/backtest_ensemble.py \
      --data trade.csv \
      --models model1.zip model2.zip model3.zip \
      --sharpe-weights 0.90 0.76 0.77

    # With env type for CPPO models
    python training/backtest_ensemble.py \
      --data trade.csv \
      --models ppo.zip sac.zip td3.zip \
      --env sentiment
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import warnings

import numpy as np
import pandas as pd
from stable_baselines3 import PPO, SAC, TD3

from training.backtest import compute_metrics, save_artifacts, _get_git_sha
from training.config import INDICATORS, TRAINED_MODEL_DIR


def _detect_algo(model_path):
    """Detect algorithm from model path or parent directory name."""
    name = os.path.basename(os.path.dirname(os.path.abspath(model_path))).lower()
    if "sac" in name:
        return "sac", SAC
    elif "td3" in name:
        return "td3", TD3
    else:
        return "ppo", PPO


def main():
    parser = argparse.ArgumentParser(
        description="Ensemble backtest: Sharpe-weighted action averaging across models",
    )
    parser.add_argument("--data", required=True, help="Trade-period CSV")
    parser.add_argument(
        "--models", nargs="+", required=True,
        help="Paths to model_sb3.zip files (2 or more)",
    )
    parser.add_argument(
        "--sharpe-weights", nargs="*", type=float, default=None,
        help="Validation Sharpe for each model (for weighting). "
             "If omitted, uses equal weights.",
    )
    parser.add_argument(
        "--env", choices=["sentiment", "risk"], default="sentiment",
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--sentiment-scale", default="strong", choices=["strong", "weak"],
    )
    parser.add_argument("--features", nargs="*", default=None)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    if len(args.models) < 2:
        parser.error("Ensemble requires at least 2 models")

    # Validate Sharpe weights
    if args.sharpe_weights:
        if len(args.sharpe_weights) != len(args.models):
            parser.error(f"--sharpe-weights count ({len(args.sharpe_weights)}) "
                         f"must match --models count ({len(args.models)})")
        # Normalize to sum=1, use softmax-like scaling to emphasize better models
        sw = np.array(args.sharpe_weights)
        sw = np.maximum(sw, 0.01)  # floor at 0.01 to avoid zero weight
        weights = sw / sw.sum()
        print(f"  Sharpe weights: {dict(zip([os.path.basename(m) for m in args.models], weights))}")
    else:
        weights = np.ones(len(args.models)) / len(args.models)
        print(f"  Equal weights: {1/len(args.models):.3f} each")

    # Load data
    df = pd.read_csv(args.data)
    if "Unnamed: 0" in df.columns:
        df = df.drop("Unnamed: 0", axis=1)
    stock_dim = int(df["tic"].nunique())

    # Feature engineering
    extra_cols = []
    if args.features is not None:
        from training.data_prep.feature_engineering import engineer_features, FeatureScaler
        feat_list = args.features if args.features else None
        df, extra_cols, _ = engineer_features(df, features=feat_list)

    # Build environment
    K = len(INDICATORS)
    F = len(extra_cols)
    if args.env == "risk":
        from training.envs.stocktrading_llm_risk import StockTradingEnv
        state_dim = 1 + 2 * stock_dim + (2 + K + F) * stock_dim
    else:
        from training.envs.stocktrading_llm import StockTradingEnv
        state_dim = 1 + 2 * stock_dim + (1 + K + F) * stock_dim

    df["date"] = df["date"].astype(str)
    df = df.sort_values(["date", "tic"]).reset_index(drop=True)
    unique_dates = df["date"].unique()
    date_to_idx = {date: idx for idx, date in enumerate(unique_dates)}
    df["new_idx"] = df["date"].map(date_to_idx)
    df = df.set_index("new_idx")

    if "llm_sentiment" in df.columns:
        df["llm_sentiment"] = df["llm_sentiment"].fillna(0)
    if "llm_risk" in df.columns:
        df["llm_risk"] = df["llm_risk"].fillna(3)

    env = StockTradingEnv(
        df=df, stock_dim=stock_dim,
        hmax=100, initial_amount=1e6,
        num_stock_shares=[0] * stock_dim,
        buy_cost_pct=[0.001] * stock_dim,
        sell_cost_pct=[0.001] * stock_dim,
        state_space=state_dim, action_space=stock_dim,
        tech_indicator_list=INDICATORS,
        reward_scaling=1e-4,
        sentiment_scale=args.sentiment_scale,
        extra_feature_cols=extra_cols,
    )

    # Load all models
    models = []
    for model_path in args.models:
        algo_name, algo_class = _detect_algo(model_path)
        model = algo_class.load(model_path, device=args.device)
        models.append((algo_name, model))
        print(f"  Loaded: {algo_name} from {os.path.basename(os.path.dirname(model_path))}")

    print(f"\n  Ensemble: {len(models)} models, {stock_dim} stocks, {len(unique_dates)} days")

    # Run ensemble backtest
    obs, _ = env.reset()
    done = False
    equity = [env.asset_memory[0]]
    trade_dates = list(unique_dates)

    while not done:
        # Get action from each model
        actions = []
        for algo_name, model in models:
            action, _ = model.predict(obs, deterministic=True)
            actions.append(action)

        # Weighted average
        ensemble_action = np.zeros_like(actions[0])
        for i, action in enumerate(actions):
            ensemble_action += weights[i] * action

        obs, reward, terminated, truncated, _ = env.step(ensemble_action)
        done = terminated or truncated
        equity.append(env.asset_memory[-1])

    # Metrics
    metrics = compute_metrics(equity)

    # Determine output dir
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = os.path.join(TRAINED_MODEL_DIR, "ensemble_backtest")
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"  Ensemble Backtest Results")
    print(f"  Models: {', '.join(n for n, _ in models)}")
    print(f"{'=' * 60}")
    print(f"  Final Equity:      ${metrics['final_equity']:,.2f}")
    tr = metrics.get("total_return")
    print(f"  Total Return:      {tr * 100:.2f}%" if tr is not None else "  Total Return:      N/A")
    print(f"  Sharpe Ratio:      {metrics.get('sharpe_ratio', 'N/A')}")
    print(f"  Max Drawdown:      {metrics.get('max_drawdown', 'N/A')}")
    print(f"  Calmar Ratio:      {metrics.get('calmar_ratio', 'N/A')}")
    print(f"  Sortino Ratio:     {metrics.get('sortino_ratio', 'N/A')}")
    print(f"  Win Rate:          {metrics.get('win_rate', 'N/A')}")
    print(f"  CVaR (95%):        {metrics.get('cvar_95', 'N/A')}")
    print(f"  Trading Days:      {metrics.get('n_trading_days', 'N/A')}")
    print(f"{'=' * 60}")

    # Save artifacts
    artifact_paths = save_artifacts(env, equity, metrics, trade_dates, output_dir)
    for name, path in artifact_paths.items():
        print(f"  Saved: {name} -> {path}")


if __name__ == "__main__":
    main()