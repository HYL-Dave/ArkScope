#!/usr/bin/env python3
"""
Backtest SB3-trained PPO agent.

Loads a model saved by train_ppo_sb3.py and runs it through the
trade-period environment. Uses the same metrics and artifact pipeline
as backtest.py.

Usage:
    python training/backtest_sb3.py --data trade.csv --model trained_models/xxx/model_sb3.zip
    python training/backtest_sb3.py --data trade.csv --model-id ppo_sb3_polygon_100ep_s42_...
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import warnings

import pandas as pd
from stable_baselines3 import PPO, SAC, TD3

from training.backtest import compute_metrics, save_artifacts, _get_git_sha
from training.config import INDICATORS, TRAINED_MODEL_DIR


def main():
    parser = argparse.ArgumentParser(
        description="Backtest SB3 PPO/CPPO agent with sentiment/risk signals"
    )
    parser.add_argument("--data", required=True, help="Trade-period CSV")
    parser.add_argument("--model", default=None, help="Path to model_sb3.zip")
    parser.add_argument("--model-id", default=None, help="Model ID from registry (or 'latest')")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: model dir)")
    parser.add_argument(
        "--env", choices=["sentiment", "risk"], default="sentiment",
        help="Environment type: sentiment (PPO) or risk (CPPO)",
    )
    parser.add_argument(
        "--sentiment-scale", default="strong", choices=["strong", "weak"],
        help="Sentiment scaling (must match training)",
    )
    parser.add_argument(
        "--features", nargs="*", default=None,
        help="Override derived features (default: auto-detect from metadata).",
    )
    parser.add_argument(
        "--device", default="auto",
        help="Device: auto, cpu, cuda, cuda:0, cuda:1, etc.",
    )
    args = parser.parse_args()

    # Resolve model path
    if args.model_id and not args.model:
        from training.model_registry import ModelRegistry
        registry = ModelRegistry(models_dir=TRAINED_MODEL_DIR)
        meta = registry.get_model(
            args.model_id if args.model_id != "latest"
            else registry.get_latest_model().model_id
        )
        if meta is None:
            raise ValueError(f"Model '{args.model_id}' not found in registry.")
        # SB3 models are saved as model_sb3.zip alongside model.pth
        model_dir = os.path.join(TRAINED_MODEL_DIR, meta.model_id)
        sb3_path = os.path.join(model_dir, "model_sb3.zip")
        if not os.path.exists(sb3_path):
            raise FileNotFoundError(
                f"SB3 model not found at {sb3_path}. "
                f"This model may have been trained with SpinningUp. "
                f"Use backtest.py instead."
            )
        args.model = sb3_path
        derived_model_id = meta.model_id
    elif args.model:
        derived_model_id = os.path.basename(os.path.dirname(os.path.abspath(args.model)))
    else:
        parser.error("Either --model or --model-id is required.")

    model_dir = os.path.dirname(os.path.abspath(args.model))
    output_dir = args.output_dir or model_dir

    # Registry metadata
    from training.model_registry import ModelRegistry
    registry = ModelRegistry(models_dir=TRAINED_MODEL_DIR)
    meta = registry.get_model(derived_model_id)

    # Load data
    df = pd.read_csv(args.data)
    if "Unnamed: 0" in df.columns:
        df = df.drop("Unnamed: 0", axis=1)
    stock_dim = int(df["tic"].nunique())

    # Feature engineering
    extra_cols = []
    if args.features is not None:
        feat_list = args.features if args.features else None
    elif meta and meta.feature_set:
        feat_list = meta.feature_set
        print(f"  Auto-detected features from metadata: {feat_list}")
    else:
        feat_list = None

    if feat_list is not None:
        from training.data_prep.feature_engineering import engineer_features, FeatureScaler
        df, extra_cols, _ = engineer_features(df, features=feat_list)
        scaler_path = os.path.join(model_dir, "feature_scaler.json")
        if os.path.exists(scaler_path):
            scaler = FeatureScaler.load(scaler_path)
            scaler.validate_contract(extra_cols)
            scaler.transform(df, extra_cols)
            print(f"  Loaded scaler from {scaler_path}")
        else:
            warnings.warn(f"No feature_scaler.json in {model_dir}.")

    # Select environment
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

    # Load SB3 model
    # Auto-detect model type from registry or model_id naming
    algo = "ppo"
    if meta and meta.algorithm:
        algo = meta.algorithm.lower()
    elif "sac" in derived_model_id.lower():
        algo = "sac"

    if "sac" in algo:
        model = SAC.load(args.model, device=args.device)
    elif "td3" in algo:
        model = TD3.load(args.model, device=args.device)
    else:
        model = PPO.load(args.model, device=args.device)

    print(f"\n  Backtesting: {derived_model_id}")
    print(f"  Data: {args.data} ({stock_dim} stocks, {len(unique_dates)} days)")
    if extra_cols:
        print(f"  Features: {extra_cols}")

    # Run backtest
    obs, _ = env.reset()
    done = False
    equity = [env.asset_memory[0]]
    trade_dates = list(unique_dates)
    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, _ = env.step(action)
        done = terminated or truncated
        equity.append(env.asset_memory[-1])

    # Metrics and output (reuse from backtest.py)
    metrics = compute_metrics(equity)

    print(f"\n{'=' * 60}")
    print(f"  Backtest Results: {derived_model_id}")
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
    from datetime import datetime
    artifact_paths = save_artifacts(env, equity, metrics, trade_dates, output_dir)
    for name, path in artifact_paths.items():
        print(f"  Saved: {name} -> {path}")

    # Update registry
    if meta is not None:
        run_entry = {
            "timestamp": datetime.now().isoformat(),
            "data_file": os.path.basename(args.data),
            "data_period": f"{trade_dates[0]} ~ {trade_dates[-1]}" if trade_dates else "",
            "feature_set": extra_cols,
            "metrics": metrics,
            "code_version": _get_git_sha(),
        }
        meta.backtest_runs.append(run_entry)
        meta.backtest_results = metrics
        registry.save_metadata(meta)
        print(f"  Registry updated with backtest run for {derived_model_id}")


if __name__ == "__main__":
    main()