#!/usr/bin/env python3
"""
Train PPO agent with LLM sentiment-enhanced stock trading environment.

Usage:
    python training/train_ppo_llm.py [options]
    python training/train_ppo_llm.py --epochs 3 --seed 42   # quick test
    python training/train_ppo_llm.py --data path/to/prepared.csv  # local CSV

The actual PPO algorithm lives in training/ppo.py; this script handles
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
    TRAINED_MODEL_DIR,
    check_and_make_directories,
)
from training.envs.stocktrading_llm import StockTradingEnv
from training.models import MLPActorCritic
from training.ppo import ppo


def load_data(data_path=None):
    """Load and prepare training dataset.

    Args:
        data_path: Local CSV path. If None, downloads from HuggingFace.
            The CSV must contain at minimum: date, tic, close,
            8 tech indicators (see config.INDICATORS), and llm_sentiment.
            See training/data_prep/README.md for the full format spec.
    """
    if data_path is not None:
        train = pd.read_csv(data_path)
        # Drop index column if present (common in saved CSVs)
        if 'Unnamed: 0' in train.columns:
            train = train.drop('Unnamed: 0', axis=1)
    else:
        from datasets import load_dataset
        dataset = load_dataset(
            "benstaf/nasdaq_2013_2023",
            data_files="train_data_deepseek_sentiment_2013_2018.csv",
        )
        train = pd.DataFrame(dataset['train'])
        train = train.drop('Unnamed: 0', axis=1)

    # Ensure correct time ordering before building date index
    train['date'] = train['date'].astype(str)
    train = train.sort_values(['date', 'tic']).reset_index(drop=True)

    # Create a new index based on unique dates
    unique_dates = train['date'].unique()  # already sorted
    date_to_idx = {date: idx for idx, date in enumerate(unique_dates)}
    train['new_idx'] = train['date'].map(date_to_idx)
    train = train.set_index('new_idx')

    # Validate required columns
    if 'llm_sentiment' not in train.columns:
        raise ValueError(
            "CSV missing required column 'llm_sentiment'. "
            "See training/data_prep/README.md for format spec."
        )

    train['llm_sentiment'].fillna(0, inplace=True)

    return train


def make_env(train, sentiment_scale="strong"):
    """Create the DummyVecEnv-wrapped trading environment."""
    stock_dimension = len(train.tic.unique())
    state_space = 1 + 2 * stock_dimension + (1 + len(INDICATORS)) * stock_dimension
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

    print("Observation space:", env_train.observation_space)
    print("Observation space shape:", env_train.observation_space.shape)
    obs = env_train.reset()
    print("Observation returned from reset:", obs.shape)

    return env_train


def main():
    parser = argparse.ArgumentParser(description="Train PPO agent with LLM sentiment")
    parser.add_argument('--hid', type=int, default=512)
    parser.add_argument('--l', type=int, default=2)
    parser.add_argument('--gamma', type=float, default=0.995)
    parser.add_argument('--seed', '-s', type=int, default=42)
    parser.add_argument('--cpu', type=int, default=4)
    parser.add_argument('--steps', type=int, default=20000)
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--exp_name', type=str, default='ppo')
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
    parser.add_argument('extra_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()

    check_and_make_directories([TRAINED_MODEL_DIR])

    train = load_data(data_path=args.data)
    env_train = make_env(train, sentiment_scale=args.sentiment_scale)

    from spinup.utils.run_utils import setup_logger_kwargs
    logger_kwargs = setup_logger_kwargs(args.exp_name, args.seed)

    trained_ppo = ppo(
        lambda: env_train,
        actor_critic=MLPActorCritic,
        ac_kwargs=dict(hidden_sizes=[args.hid] * args.l),
        gamma=args.gamma,
        seed=args.seed,
        steps_per_epoch=args.steps,
        epochs=args.epochs,
        logger_kwargs=logger_kwargs,
    )

    # Save the model — derive filename from data source + params
    data_tag = os.path.splitext(os.path.basename(args.data))[0] if args.data else "huggingface"
    model_name = f"agent_ppo_{data_tag}_{args.epochs}ep_s{args.seed}.pth"
    model_path = os.path.join(TRAINED_MODEL_DIR, model_name)
    torch.save(trained_ppo.state_dict(), model_path)
    print("Training finished and saved in " + model_path)


if __name__ == "__main__":
    main()
