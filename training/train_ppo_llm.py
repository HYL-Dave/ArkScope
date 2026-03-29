#!/usr/bin/env python3
"""
Train PPO agent with LLM sentiment-enhanced stock trading environment.

Usage:
    python training/train_ppo_llm.py [options]
    python training/train_ppo_llm.py --epochs 3 --seed 42   # quick test
    python training/train_ppo_llm.py --data path/to/prepared.csv  # local CSV
    python training/train_ppo_llm.py --data prep.csv --features   # with derived features

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

    # Validate required columns before any processing
    required = ['date', 'tic', 'close', 'llm_sentiment'] + list(INDICATORS)
    missing = [c for c in required if c not in train.columns]
    if missing:
        raise ValueError(
            f"CSV missing required column(s): {missing}. "
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

    train['llm_sentiment'] = train['llm_sentiment'].fillna(0)

    return train


def make_env(train, sentiment_scale="strong", extra_feature_cols=None):
    """Create the DummyVecEnv-wrapped trading environment.

    Args:
        train: DataFrame with date index.
        sentiment_scale: "strong" or "weak".
        extra_feature_cols: List of derived feature column names.
    """
    extra = extra_feature_cols or []
    stock_dimension = len(train.tic.unique())
    F = len(extra)
    K = len(INDICATORS)
    # PPO: [cash(1)] + [close(N)] + [shares(N)] + [indicators(K*N)] + [extra(F*N)] + [sentiment(N)]
    state_space = 1 + 2 * stock_dimension + (1 + K + F) * stock_dimension
    print(f"Stock Dimension: {stock_dimension}, State Space: {state_space}")
    if extra:
        print(f"  Extra features ({F}): {extra}")

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
        "extra_feature_cols": extra,
    }

    e_train_gym = StockTradingEnv(df=train, **env_kwargs)
    env_train, _ = e_train_gym.get_sb_env()

    print("Observation space:", env_train.observation_space)
    print("Observation space shape:", env_train.observation_space.shape)
    obs = env_train.reset()
    print("Observation returned from reset:", obs.shape)

    return env_train, stock_dimension, state_space


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
    parser.add_argument(
        '--features', nargs='*', default=None,
        help='Enable derived features. No args = all defaults. '
             'Specific features: --features sentiment_7d_ma sentiment_momentum. '
             'Omit flag entirely to disable.',
    )
    parser.add_argument('extra_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()

    check_and_make_directories([TRAINED_MODEL_DIR])

    train = load_data(data_path=args.data)

    # Feature engineering (Path A / Path B detection)
    from training.train_utils import detect_and_load_features
    train, extra_cols, scaler = detect_and_load_features(
        train, args.features, data_path=args.data,
    )

    env_train, stock_dimension, state_space = make_env(
        train,
        sentiment_scale=args.sentiment_scale,
        extra_feature_cols=extra_cols,
    )

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

    # Save model + metadata + scaler — rank 0 only (MPI safety)
    from spinup.utils.mpi_tools import proc_id
    if proc_id() == 0:
        from training.train_utils import generate_model_id, save_training_artifacts

        data_tag = (
            os.path.splitext(os.path.basename(args.data))[0]
            if args.data else "huggingface"
        )
        model_id = generate_model_id(
            algorithm="ppo",
            data_tag=data_tag,
            epochs=args.epochs,
            seed=args.seed,
            data_path=args.data,
        )

        # Derive train period from data
        dates = sorted(train['date'].unique())
        train_period = f"{dates[0]} ~ {dates[-1]}" if dates else ""

        save_training_artifacts(
            model_id=model_id,
            algorithm="PPO",
            model_state_dict=trained_ppo.state_dict(),
            score_source=data_tag,
            extra_cols=extra_cols,
            stock_dim=stock_dimension,
            state_dim=state_space,
            train_period=train_period,
            epochs=args.epochs,
            seed=args.seed,
            hyperparams={
                "hid": args.hid,
                "layers": args.l,
                "gamma": args.gamma,
                "steps_per_epoch": args.steps,
                "sentiment_scale": args.sentiment_scale,
            },
            data_path=args.data,
            scaler=scaler,
        )
        print("Training finished. Model ID:", model_id)


if __name__ == "__main__":
    main()
