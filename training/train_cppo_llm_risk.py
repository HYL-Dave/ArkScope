#!/usr/bin/env python3
"""
Train CPPO (CVaR-constrained PPO) agent with LLM risk-enhanced environment.

Usage:
    python training/train_cppo_llm_risk.py [options]
    python training/train_cppo_llm_risk.py --epochs 3 --seed 42   # quick test
    python training/train_cppo_llm_risk.py --data path/to/prepared.csv

For MPI parallel training:
    OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 \
        mpirun -np 4 python3 training/train_cppo_llm_risk.py

The actual CPPO algorithm lives in training/cppo.py; this script handles
data loading, environment setup, argument parsing, and model saving.
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse

import pandas as pd
import torch

from training.config import (
    INDICATORS,
    SENTIMENT_SCALES,
    TRAINED_MODEL_DIR,
    check_and_make_directories,
)
from training.envs.stocktrading_llm_risk import StockTradingEnv
from training.models import MLPActorCritic
from training.cppo import cppo


def load_data(data_path=None):
    """Load and prepare training dataset.

    Args:
        data_path: Local CSV path. If None, downloads from HuggingFace.
            The CSV must contain at minimum: date, tic, close,
            8 tech indicators (see config.INDICATORS), llm_sentiment,
            and llm_risk. See training/data_prep/README.md for the full
            format spec.
    """
    if data_path is not None:
        train = pd.read_csv(data_path)
        if 'Unnamed: 0' in train.columns:
            train = train.drop('Unnamed: 0', axis=1)
    else:
        from datasets import load_dataset
        dataset = load_dataset(
            "benstaf/nasdaq_2013_2023",
            data_files="train_data_deepseek_risk_2013_2018.csv",
        )
        train = pd.DataFrame(dataset['train'])
        train = train.drop('Unnamed: 0', axis=1)

    # Validate required columns before any processing
    required = ['date', 'tic', 'close', 'llm_sentiment', 'llm_risk'] + list(INDICATORS)
    missing = [c for c in required if c not in train.columns]
    if missing:
        raise ValueError(
            f"CSV missing required column(s): {missing}. "
            "CPPO requires all technical indicators + llm_sentiment + llm_risk. "
            "See training/data_prep/README.md for format spec."
        )

    # Ensure correct time ordering before building date index
    train['date'] = train['date'].astype(str)
    train = train.sort_values(['date', 'tic']).reset_index(drop=True)

    # Create a new index based on unique dates
    unique_dates = train['date'].unique()  # already sorted
    date_to_idx = {date: idx for idx, date in enumerate(unique_dates)}
    train['new_idx'] = train['date'].map(date_to_idx)
    train = train.set_index('new_idx')

    train['llm_sentiment'].fillna(0, inplace=True)   # 0 is outside scope (min is 1)
    train['llm_risk'].fillna(3, inplace=True)         # neutral risk score is 3

    return train


def make_env(train, sentiment_scale="strong"):
    """Create the DummyVecEnv-wrapped trading environment."""
    stock_dimension = len(train.tic.unique())
    # +2 for llm_sentiment + llm_risk per stock
    state_space = 1 + 2 * stock_dimension + (2 + len(INDICATORS)) * stock_dimension
    print(f"Stock Dimension: {stock_dimension}, State Space: {state_space}")

    env_kwargs = {
        "hmax": 100,
        "initial_amount": 1000000,
        "num_stock_shares": [0] * stock_dimension,
        "buy_cost_pct": [0.001] * stock_dimension,
        "sell_cost_pct": [0.001] * stock_dimension,
        "state_space": state_space,
        "stock_dim": stock_dimension,
        "tech_indicator_list": INDICATORS,
        "action_space": stock_dimension,
        "reward_scaling": 1e-4,
        "sentiment_scale": sentiment_scale,
    }

    e_train_gym = StockTradingEnv(df=train, **env_kwargs)
    env_train, _ = e_train_gym.get_sb_env()

    return env_train, stock_dimension


def main():
    parser = argparse.ArgumentParser(
        description="Train CPPO agent with LLM risk signals"
    )
    parser.add_argument('--hid', type=int, default=512)
    parser.add_argument('--l', type=int, default=2)
    parser.add_argument('--seed', '-s', type=int, default=0)
    parser.add_argument('--cpu', type=int, default=4)
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--exp_name', type=str, default='cppo')
    parser.add_argument(
        '--sentiment-scale', type=str, default='strong',
        choices=['strong', 'weak'],
        help='Sentiment scaling preset: strong (±10%%) or weak (±0.1%%)',
    )
    parser.add_argument(
        '--data', type=str, default=None,
        help='Local CSV path (skip HuggingFace download). '
             'See training/data_prep/README.md for required format.',
    )
    parser.add_argument('-f', '--file', type=str, help='Kernel connection file')
    parser.add_argument('extra_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()

    check_and_make_directories([TRAINED_MODEL_DIR])

    train = load_data(data_path=args.data)
    env_train, stock_dimension = make_env(train, sentiment_scale=args.sentiment_scale)

    from spinup.utils.run_utils import setup_logger_kwargs
    logger_kwargs = setup_logger_kwargs(args.exp_name, args.seed)

    scale = SENTIMENT_SCALES[args.sentiment_scale]
    trained_cppo = cppo(
        lambda: env_train,
        stock_dim=stock_dimension,
        risk_weights=scale["risk_weights"],
        actor_critic=MLPActorCritic,
        ac_kwargs=dict(hidden_sizes=[args.hid] * args.l),
        seed=args.seed,
        epochs=args.epochs,
        logger_kwargs=logger_kwargs,
    )

    # Save the model — derive filename from data source + params
    data_tag = os.path.splitext(os.path.basename(args.data))[0] if args.data else "huggingface"
    model_name = f"agent_cppo_{data_tag}_{args.epochs}ep_s{args.seed}.pth"
    model_path = os.path.join(TRAINED_MODEL_DIR, model_name)
    torch.save(trained_cppo.state_dict(), model_path)
    print("Training finished and saved in " + model_path)


if __name__ == "__main__":
    main()
