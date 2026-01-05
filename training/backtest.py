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

from finrl.config import INDICATORS
from training.train_ppo_llm import MLPActorCritic

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
    args = parser.parse_args()

    # Load dataset
    df = pd.read_csv(args.data)
    # Determine symbol column
    symbol_col = "tic" if "tic" in df.columns else "symbol"
    stock_dim = int(df[symbol_col].nunique())
    state_dim = 1 + 2*stock_dim + (1 + len(INDICATORS))*stock_dim

    # Select environment
    if args.env == "baseline":
        from env_stocktrading import StockTradingEnv
    elif args.env == "sentiment":
        from training.envs.stocktrading_llm import StockTradingEnv
    else:
        from training.envs.stocktrading_llm_risk import StockTradingEnv

    env = StockTradingEnv(
        df=df, stock_dim=stock_dim,
        hmax=100, initial_amount=1e6,
        num_stock_shares=[0]*stock_dim,
        buy_cost_pct=[0.001]*stock_dim,
        sell_cost_pct=[0.001]*stock_dim,
        state_space=state_dim, action_space=stock_dim,
        tech_indicator_list=INDICATORS,
        reward_scaling=1e-4
    )

    # Load trained agent
    ac = MLPActorCritic(env.observation_space, env.action_space, hidden_sizes=[256,128])
    ac.load_state_dict(torch.load(args.model))
    ac.eval()

    # Run backtest
    obs, _ = env.reset()
    done = False
    equity = [env.asset_memory[0]]
    while not done:
        action = ac.act(torch.tensor(obs, dtype=torch.float32))
        obs, reward, done, _ = env.step(action)
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