#!/usr/bin/env python3
import os, sys
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""
Backtest RL agent with OpenAI LLM-enhanced environment (sentiment/risk).
"""
import argparse
import pandas as pd
import torch
import numpy as np
import matplotlib.pyplot as plt

from training.config import INDICATORS
from training.models import MLPActorCritic

def main():
    parser = argparse.ArgumentParser(
        description="Run backtest for RL agent with sentiment/risk signals"
    )
    parser.add_argument("--data", required=True, help="Path to test CSV with features and signals")
    parser.add_argument("--model", required=True, help="Path to trained .pth model file")
    parser.add_argument(
        "--env", choices=["baseline", "sentiment", "risk"], default="sentiment",
        help="Environment type: baseline, sentiment, or risk"
    )
    parser.add_argument("--output-plot", default="equity_curve.png", help="Path to save equity curve plot")
    parser.add_argument("--hid", type=int, default=512, help="Hidden layer size (must match training)")
    parser.add_argument("--l", type=int, default=2, help="Number of hidden layers (must match training)")
    parser.add_argument(
        "--sentiment-scale", type=str, default="strong",
        choices=["strong", "weak"],
        help="Sentiment scaling preset (must match training config)",
    )
    args = parser.parse_args()

    # Load dataset
    df = pd.read_csv(args.data)
    # Normalize symbol column to 'tic' (env expects df.tic)
    if "tic" not in df.columns and "symbol" in df.columns:
        df = df.rename(columns={"symbol": "tic"})
    stock_dim = int(df["tic"].nunique())

    # Select environment and compute state_dim
    # stocktrading_llm state:      cash + close*N + shares*N + indicators*N + sentiment*N
    # stocktrading_llm_risk state: cash + close*N + shares*N + indicators*N + sentiment*N + risk*N
    n_ind = len(INDICATORS)
    if args.env in ("baseline", "sentiment"):
        from training.envs.stocktrading_llm import StockTradingEnv
        # Both baseline and sentiment use the same env (always includes sentiment in state)
        state_dim = 1 + 2*stock_dim + (1 + n_ind)*stock_dim
    else:
        from training.envs.stocktrading_llm_risk import StockTradingEnv
        state_dim = 1 + 2*stock_dim + (2 + n_ind)*stock_dim

    env = StockTradingEnv(
        df=df, stock_dim=stock_dim,
        hmax=100, initial_amount=1e6,
        num_stock_shares=[0]*stock_dim,
        buy_cost_pct=[0.001]*stock_dim,
        sell_cost_pct=[0.001]*stock_dim,
        state_space=state_dim, action_space=stock_dim,
        tech_indicator_list=INDICATORS,
        reward_scaling=1e-4,
        sentiment_scale=args.sentiment_scale,
    )

    # Load trained agent
    ac = MLPActorCritic(env.observation_space, env.action_space, hidden_sizes=[args.hid]*args.l)
    ac.load_state_dict(torch.load(args.model))
    ac.eval()

    # Run backtest
    obs, _ = env.reset()
    done = False
    equity = [env.asset_memory[0]]
    while not done:
        action = ac.act(torch.tensor(obs, dtype=torch.float32))
        obs, reward, terminated, truncated, _ = env.step(action)
        done = terminated or truncated
        equity.append(env.asset_memory[-1])

    # Performance metrics
    returns = np.diff(equity) / equity[:-1]
    ir = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
    cvar95 = np.mean(returns[returns <= np.percentile(returns, 5)])
    print(f"Final Equity: {equity[-1]:.2f}")
    print(f"Information Ratio: {ir:.3f}")
    print(f"CVaR (95%): {cvar95:.3%}")

    # Plot equity curve
    plt.figure(figsize=(8,4))
    plt.plot(equity)
    plt.title("Equity Curve")
    plt.xlabel("Step")
    plt.ylabel("Asset Value")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(args.output_plot)
    print(f"Equity curve saved to {args.output_plot}")

if __name__ == "__main__":
    main()