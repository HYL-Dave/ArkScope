#!/usr/bin/env python3
import os, sys
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""
Backtest RL agent with LLM-enhanced environment (sentiment/risk).

Computes full performance metrics, saves dated artifacts (CSV + PNG),
and updates model registry with backtest run history.

Usage:
    python training/backtest.py --data trade.csv --model trained_models/xxx/model.pth
    python training/backtest.py --data trade.csv --model-id ppo_claude_100ep_s42_...
    python training/backtest.py --data trade.csv --model-id latest
"""
import argparse
import subprocess
import warnings
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

from training.config import INDICATORS, TRAINED_MODEL_DIR
from training.models import MLPActorCritic


# ── Performance metrics ──────────────────────────────────────


def compute_metrics(
    equity: list,
    risk_free_rate: float = 0.02,
) -> dict:
    """Compute full backtest performance metrics.

    Args:
        equity: List of daily portfolio values (len >= 2 for meaningful results).
        risk_free_rate: Annual risk-free rate for Sharpe/Sortino calculation.

    Returns:
        Dict with all metrics. Ratio metrics are None when undefined,
        with corresponding _note fields explaining why.
    """
    equity = np.array(equity, dtype=float)
    metrics = {}

    # Edge case: too few data points
    if len(equity) < 2:
        return {
            "final_equity": float(equity[-1]) if len(equity) else 0.0,
            "total_return": None,
            "total_return_note": "Insufficient data (< 2 equity points)",
            "sharpe_ratio": None,
            "sharpe_ratio_note": "Insufficient data",
            "information_ratio": None,
            "ir_note": "Requires --benchmark flag (e.g. SPY). Only Sharpe Ratio is available.",
            "max_drawdown": None,
            "calmar_ratio": None,
            "sortino_ratio": None,
            "win_rate": None,
            "cvar_95": None,
        }

    # Daily returns
    returns = np.diff(equity) / equity[:-1]
    n_days = len(returns)

    # Basic stats
    metrics["final_equity"] = float(equity[-1])
    metrics["initial_equity"] = float(equity[0])
    metrics["total_return"] = float((equity[-1] / equity[0]) - 1)
    metrics["annualized_return"] = float((1 + metrics["total_return"]) ** (252 / n_days) - 1)

    # Sharpe ratio
    daily_rf = (1 + risk_free_rate) ** (1 / 252) - 1
    excess_returns = returns - daily_rf
    std = float(np.std(returns))
    if std > 1e-10:
        metrics["sharpe_ratio"] = float(np.mean(excess_returns) / std * np.sqrt(252))
    else:
        metrics["sharpe_ratio"] = 0.0
        metrics["sharpe_ratio_note"] = "Zero volatility — no excess performance"

    # Information ratio — requires benchmark, currently not available
    metrics["information_ratio"] = None
    metrics["ir_note"] = "Requires --benchmark flag (e.g. SPY). Only Sharpe Ratio is available."

    # Max drawdown
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    metrics["max_drawdown"] = float(np.min(drawdown))

    # Calmar ratio
    mdd = abs(metrics["max_drawdown"])
    if mdd > 1e-10:
        metrics["calmar_ratio"] = float(metrics["annualized_return"] / mdd)
    else:
        metrics["calmar_ratio"] = None
        metrics["calmar_ratio_note"] = "No drawdown — ratio undefined"

    # Sortino ratio
    downside = excess_returns[excess_returns < 0]
    if len(downside) > 0:
        downside_std = float(np.std(downside))
        if downside_std > 1e-10:
            metrics["sortino_ratio"] = float(np.mean(excess_returns) / downside_std * np.sqrt(252))
        else:
            metrics["sortino_ratio"] = 0.0
            metrics["sortino_ratio_note"] = "Zero downside volatility"
    else:
        metrics["sortino_ratio"] = None
        metrics["sortino_ratio_note"] = "No negative returns — ratio undefined"

    # Win rate
    metrics["win_rate"] = float(np.mean(returns > 0))

    # CVaR 95% (Expected Shortfall)
    percentile_5 = np.percentile(returns, 5)
    tail_returns = returns[returns <= percentile_5]
    if len(tail_returns) > 0:
        metrics["cvar_95"] = float(np.mean(tail_returns))
    else:
        metrics["cvar_95"] = float(percentile_5)

    metrics["n_trading_days"] = n_days

    return metrics


# ── Artifact saving ──────────────────────────────────────────


def save_artifacts(env, equity, metrics, dates, output_dir: str) -> dict:
    """Save backtest artifacts: daily_returns.csv, actions_log.csv, equity_curve.png.

    Args:
        env: Trading environment with save_action_memory().
        equity: List of daily equity values.
        metrics: Dict from compute_metrics().
        dates: List of date strings corresponding to equity points.
        output_dir: Directory to save artifacts.

    Returns:
        Dict mapping artifact name to file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = {}

    # 1. Daily returns CSV with drawdown
    equity_arr = np.array(equity, dtype=float)
    peak = np.maximum.accumulate(equity_arr)
    drawdown = (equity_arr - peak) / peak
    daily_return = np.concatenate([[0.0], np.diff(equity_arr) / equity_arr[:-1]])

    # Align dates with equity (equity may have one more point from initial)
    if len(dates) < len(equity_arr):
        dates = ["initial"] + list(dates)

    df_returns = pd.DataFrame({
        "date": dates[:len(equity_arr)],
        "equity": equity_arr,
        "daily_return": daily_return,
        "drawdown": drawdown,
    })
    csv_path = os.path.join(output_dir, "daily_returns.csv")
    df_returns.to_csv(csv_path, index=False)
    paths["daily_returns"] = csv_path

    # 2. Actions log (if env supports it)
    if hasattr(env, "save_action_memory"):
        try:
            actions_df = env.save_action_memory()
            actions_path = os.path.join(output_dir, "actions_log.csv")
            actions_df.to_csv(actions_path)
            paths["actions_log"] = actions_path
        except Exception:
            pass

    # 3. Equity curve plot with dates
    fig, ax = plt.subplots(figsize=(10, 5))
    if dates and dates[0] != "initial":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            x = pd.to_datetime(dates[:len(equity_arr)], errors="coerce")
        if x.notna().all():
            ax.plot(x, equity_arr)
            fig.autofmt_xdate()
        else:
            ax.plot(equity_arr)
            ax.set_xlabel("Step")
    else:
        ax.plot(equity_arr)
        ax.set_xlabel("Step")

    sharpe = metrics.get("sharpe_ratio")
    title = f"Equity Curve — Sharpe: {sharpe:.2f}" if sharpe is not None else "Equity Curve"
    ax.set_title(title)
    ax.set_ylabel("Portfolio Value ($)")
    ax.grid(True, alpha=0.3)
    ax.ticklabel_format(style="plain", axis="y")
    fig.tight_layout()
    plot_path = os.path.join(output_dir, "equity_curve.png")
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    paths["equity_curve"] = plot_path

    return paths


# ── Git SHA helper ───────────────────────────────────────────


def _get_git_sha() -> str:
    """Get current git commit SHA (short). Returns "" if not in a git repo."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return ""


# ── Main ─────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Run backtest for RL agent with sentiment/risk signals"
    )
    parser.add_argument("--data", required=True, help="Path to test CSV with features and signals")
    parser.add_argument("--model", default=None, help="Path to trained .pth model file")
    parser.add_argument("--model-id", default=None, help="Model ID from registry (or 'latest')")
    parser.add_argument(
        "--env", choices=["baseline", "sentiment", "risk"], default="sentiment",
        help="Environment type: baseline, sentiment, or risk"
    )
    parser.add_argument("--output-dir", default=None, help="Output directory for artifacts (default: model dir)")
    parser.add_argument("--hid", type=int, default=512, help="Hidden layer size (must match training)")
    parser.add_argument("--l", type=int, default=2, help="Number of hidden layers (must match training)")
    parser.add_argument(
        "--sentiment-scale", type=str, default="strong",
        choices=["strong", "weak"],
        help="Sentiment scaling preset (must match training config)",
    )
    parser.add_argument(
        "--features", nargs="*", default=None,
        help="Override derived features (default: auto-detect from metadata). "
             "No args = all defaults. Specific: --features sentiment_7d_ma.",
    )
    args = parser.parse_args()

    # Resolve model path and model_id
    if args.model_id and not args.model:
        # Load from registry
        from training.model_registry import ModelRegistry
        registry = ModelRegistry(models_dir=TRAINED_MODEL_DIR)
        if args.model_id == "latest":
            meta = registry.get_latest_model()
        else:
            meta = registry.get_model(args.model_id)
        if meta is None:
            raise ValueError(f"Model '{args.model_id}' not found in registry.")
        args.model = os.path.join(TRAINED_MODEL_DIR, meta.model_path)
        derived_model_id = meta.model_id
    elif args.model:
        # Derive model_id from path: trained_models/<model_id>/model.pth
        derived_model_id = os.path.basename(os.path.dirname(os.path.abspath(args.model)))
    else:
        parser.error("Either --model or --model-id is required.")

    model_dir = os.path.dirname(os.path.abspath(args.model))
    output_dir = args.output_dir or model_dir

    # Try to load metadata from registry
    from training.model_registry import ModelRegistry
    registry = ModelRegistry(models_dir=TRAINED_MODEL_DIR)
    meta = registry.get_model(derived_model_id)

    # Load dataset
    df = pd.read_csv(args.data)
    if "tic" not in df.columns and "symbol" in df.columns:
        df = df.rename(columns={"symbol": "tic"})
    if "Unnamed: 0" in df.columns:
        df = df.drop("Unnamed: 0", axis=1)
    stock_dim = int(df["tic"].nunique())

    # Feature engineering: auto-detect from metadata or --features override
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
            import warnings
            warnings.warn(f"No feature_scaler.json in {model_dir}. Features not standardized.")

    # Select environment and compute state_dim
    n_ind = len(INDICATORS)
    F = len(extra_cols)
    if args.env in ("baseline", "sentiment"):
        from training.envs.stocktrading_llm import StockTradingEnv
        state_dim = 1 + 2 * stock_dim + (1 + n_ind + F) * stock_dim
    else:
        from training.envs.stocktrading_llm_risk import StockTradingEnv
        state_dim = 1 + 2 * stock_dim + (2 + n_ind + F) * stock_dim

    # Ensure date ordering
    df["date"] = df["date"].astype(str)
    df = df.sort_values(["date", "tic"]).reset_index(drop=True)
    unique_dates = df["date"].unique()
    date_to_idx = {date: idx for idx, date in enumerate(unique_dates)}
    df["new_idx"] = df["date"].map(date_to_idx)
    df = df.set_index("new_idx")

    # Fill missing scores
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

    # Load trained agent
    ac = MLPActorCritic(env.observation_space, env.action_space, hidden_sizes=[args.hid] * args.l)
    ac.load_state_dict(torch.load(args.model, weights_only=True))
    ac.eval()

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
        action = ac.act(torch.tensor(obs, dtype=torch.float32))
        obs, reward, terminated, truncated, _ = env.step(action)
        done = terminated or truncated
        equity.append(env.asset_memory[-1])

    # Compute metrics
    metrics = compute_metrics(equity)

    # Print summary
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
    ir_note = metrics.get("ir_note", "")
    if ir_note:
        print(f"  Information Ratio: {ir_note}")
    print(f"{'=' * 60}")

    # Save artifacts
    artifact_paths = save_artifacts(env, equity, metrics, trade_dates, output_dir)
    for name, path in artifact_paths.items():
        print(f"  Saved: {name} -> {path}")

    # Update registry with backtest run
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
        meta.backtest_results = metrics  # latest snapshot
        registry.save_metadata(meta)
        print(f"  Registry updated with backtest run for {derived_model_id}")


if __name__ == "__main__":
    main()
