#!/usr/bin/env python3
"""
Train PPO agent using Stable-Baselines3 (GPU/CPU).

Drop-in replacement for train_ppo_llm.py (SpinningUp), using the same
environment, data pipeline, and model registry. The key difference is
SB3's PPO runs on GPU (via PyTorch CUDA) or CPU, selectable via --device.

Usage:
    # GPU (auto-detect)
    python training/train_ppo_sb3.py --data train.csv --device auto

    # Explicit GPU
    python training/train_ppo_sb3.py --data train.csv --device cuda

    # CPU (same as SpinningUp but single-process, no MPI)
    python training/train_ppo_sb3.py --data train.csv --device cpu

    # Quick test
    python training/train_ppo_sb3.py --data train.csv --epochs 3 --device auto

Hyperparameters are matched to the SpinningUp version by default so that
results are comparable. The environment (stocktrading_llm.py) is identical —
all sentiment scaling logic lives there, not in the PPO algorithm.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import time

import pandas as pd
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from training.config import (
    INDICATORS,
    TRAINED_MODEL_DIR,
    check_and_make_directories,
)
from training.envs.stocktrading_llm import StockTradingEnv


# ── Data loading (shared with train_ppo_llm.py) ────────────


def load_data(data_path):
    """Load and prepare training dataset from local CSV."""
    train = pd.read_csv(data_path)
    if "Unnamed: 0" in train.columns:
        train = train.drop("Unnamed: 0", axis=1)

    required = ["date", "tic", "close", "llm_sentiment"] + list(INDICATORS)
    missing = [c for c in required if c not in train.columns]
    if missing:
        raise ValueError(
            f"CSV missing required column(s): {missing}. "
            "See training/data_prep/README.md for format spec."
        )

    train["date"] = train["date"].astype(str)
    train = train.sort_values(["date", "tic"]).reset_index(drop=True)
    unique_dates = train["date"].unique()
    date_to_idx = {date: idx for idx, date in enumerate(unique_dates)}
    train["new_idx"] = train["date"].map(date_to_idx)
    train = train.set_index("new_idx")
    train["llm_sentiment"] = train["llm_sentiment"].fillna(0)

    return train


# ── Environment factory ─────────────────────────────────────


def make_env_fn(train, sentiment_scale="strong", extra_feature_cols=None):
    """Return a callable that creates the trading environment.

    SB3 expects a factory function (not a pre-built env) for vectorized envs.
    """
    extra = extra_feature_cols or []
    stock_dimension = len(train.tic.unique())
    K = len(INDICATORS)
    F = len(extra)
    state_space = 1 + 2 * stock_dimension + (1 + K + F) * stock_dimension

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

    def _make():
        return Monitor(StockTradingEnv(df=train, **env_kwargs))

    return _make, stock_dimension, state_space


# ── Logging callback ────────────────────────────────────────


class EpochLogCallback(BaseCallback):
    """Log epoch-level stats similar to SpinningUp's EpochLogger."""

    def __init__(self, epochs, steps_per_epoch, verbose=1):
        super().__init__(verbose)
        self.epochs = epochs
        self.steps_per_epoch = steps_per_epoch
        self.start_time = None
        self.current_epoch = 0

    def _on_training_start(self):
        self.start_time = time.time()

    def _on_rollout_end(self):
        self.current_epoch += 1
        if self.verbose:
            elapsed = time.time() - self.start_time
            ep_info = self.model.ep_info_buffer
            if ep_info:
                mean_reward = sum(e["r"] for e in ep_info) / len(ep_info)
                mean_len = sum(e["l"] for e in ep_info) / len(ep_info)
            else:
                mean_reward = float("nan")
                mean_len = float("nan")
            print(
                f"Epoch {self.current_epoch}/{self.epochs} | "
                f"EpRet: {mean_reward:.1f} | "
                f"EpLen: {mean_len:.0f} | "
                f"Time: {elapsed:.1f}s"
            )

    def _on_step(self):
        return True


# ── Main ────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Train PPO agent (SB3, GPU/CPU) with LLM sentiment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Hyperparameter mapping (SpinningUp → SB3):
  clip_ratio=0.7      → clip_range=0.7
  pi_lr=3e-5          → learning_rate=3e-5
  gamma=0.995         → gamma=0.995
  steps_per_epoch=20k → n_steps=20000
  train_pi_iters=100  → n_epochs=100 (SB3 minibatch epochs per rollout)
  target_kl=0.35      → target_kl=0.35
  lam=0.95            → gae_lambda=0.95
  hid=512, l=2        → net_arch=[512, 512]
        """,
    )
    parser.add_argument("--data", required=True, help="Training CSV path")
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs (rollout cycles)")
    parser.add_argument("--steps", type=int, default=20000, help="Steps per epoch (n_steps)")
    parser.add_argument("--seed", "-s", type=int, default=42)
    parser.add_argument("--hid", type=int, default=512, help="Hidden layer size")
    parser.add_argument("--l", type=int, default=2, help="Number of hidden layers")
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--lr", type=float, default=3e-5, help="Learning rate")
    parser.add_argument(
        "--device", default="auto", choices=["auto", "cpu", "cuda"],
        help="Device: auto (GPU if available), cpu, or cuda",
    )
    parser.add_argument(
        "--sentiment-scale", default="strong", choices=["strong", "weak"],
        help="Sentiment scaling preset: strong (±10%%) or weak (±0.1%%)",
    )
    parser.add_argument(
        "--features", nargs="*", default=None,
        help="Enable derived features. No args = all defaults.",
    )
    parser.add_argument(
        "--n-envs", type=int, default=1,
        help="Number of parallel environments (1=DummyVecEnv, >1=SubprocVecEnv)",
    )
    args = parser.parse_args()

    check_and_make_directories([TRAINED_MODEL_DIR])

    # Device info
    if args.device == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device_name = args.device
    print(f"\n  Device: {device_name}")
    if device_name == "cuda":
        print(f"  GPU: {torch.cuda.get_device_name(0)}")

    # Load data
    train = load_data(args.data)

    # Feature engineering
    from training.train_utils import detect_and_load_features
    train, extra_cols, scaler = detect_and_load_features(
        train, args.features, data_path=args.data,
    )

    # Create environment
    env_fn, stock_dimension, state_space = make_env_fn(
        train, sentiment_scale=args.sentiment_scale, extra_feature_cols=extra_cols,
    )

    if args.n_envs > 1:
        env = SubprocVecEnv([env_fn for _ in range(args.n_envs)])
        effective_steps = args.steps // args.n_envs
        print(f"  Parallel envs: {args.n_envs} (SubprocVecEnv)")
    else:
        env = DummyVecEnv([env_fn])
        effective_steps = args.steps

    print(f"  Stock Dimension: {stock_dimension}, State Space: {state_space}")
    if extra_cols:
        print(f"  Extra features ({len(extra_cols)}): {extra_cols}")

    # Build SB3 PPO model
    # Hyperparams matched to SpinningUp defaults for comparability
    model = PPO(
        "MlpPolicy",
        env,
        device=args.device,
        learning_rate=args.lr,
        n_steps=effective_steps,
        batch_size=min(effective_steps, 2000),  # factor of 20000 to avoid truncated minibatch
        n_epochs=10,              # SB3 inner optimization epochs per rollout
        gamma=args.gamma,
        gae_lambda=0.95,
        clip_range=0.7,
        target_kl=0.35,
        vf_coef=0.5,
        ent_coef=0.0,
        seed=args.seed,
        verbose=0,
        policy_kwargs=dict(
            net_arch=dict(pi=[args.hid] * args.l, vf=[args.hid] * args.l),
            activation_fn=torch.nn.Tanh,
        ),
    )

    total_timesteps = args.epochs * args.steps
    print(f"\n  Training: {args.epochs} epochs × {args.steps} steps = {total_timesteps} total")
    print(f"  Network: {[args.hid] * args.l}")

    # Train
    callback = EpochLogCallback(args.epochs, args.steps)
    start_time = time.time()
    model.learn(total_timesteps=total_timesteps, callback=callback)
    elapsed = time.time() - start_time
    print(f"\n  Training complete in {elapsed:.1f}s ({elapsed / 60:.1f}m)")

    # Save artifacts compatible with model registry
    from training.train_utils import generate_model_id, save_training_artifacts

    data_tag = os.path.splitext(os.path.basename(args.data))[0]
    model_id = generate_model_id(
        algorithm="ppo_sb3",
        data_tag=data_tag,
        epochs=args.epochs,
        seed=args.seed,
        data_path=args.data,
    )

    # Save SB3 model (zip) + extract state_dict for registry compatibility
    model_dir = os.path.join(TRAINED_MODEL_DIR, model_id)
    os.makedirs(model_dir, exist_ok=True)

    # SB3 native save (complete model, for SB3 loading)
    sb3_path = os.path.join(model_dir, "model_sb3.zip")
    model.save(sb3_path)

    # Also save PyTorch state_dict (for backtest.py compatibility)
    # Extract the policy network weights
    state_dict = model.policy.state_dict()
    pth_path = os.path.join(model_dir, "model.pth")
    torch.save(state_dict, pth_path)

    dates = sorted(train["date"].unique())
    train_period = f"{dates[0]} ~ {dates[-1]}" if dates else ""

    save_training_artifacts(
        model_id=model_id,
        algorithm="PPO_SB3",
        model_state_dict=state_dict,
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
            "learning_rate": args.lr,
            "n_steps": args.steps,
            "clip_range": 0.7,
            "target_kl": 0.35,
            "gae_lambda": 0.95,
            "device": device_name,
            "n_envs": args.n_envs,
            "sentiment_scale": args.sentiment_scale,
            "framework": "stable-baselines3",
        },
        data_path=args.data,
        scaler=scaler,
    )

    print(f"\n  SB3 model: {sb3_path}")
    print(f"  State dict: {pth_path}")
    print(f"  Model ID: {model_id}")

    # Print next steps
    print(f"\nTo backtest (SB3 native):")
    feat_flag = " --features" if extra_cols else ""
    print(f"  python training/backtest_sb3.py --data <trade.csv> --model {sb3_path}{feat_flag}")
    print(f"\nTo backtest (SpinningUp-compatible, if architecture matches):")
    print(f"  python training/backtest.py --data <trade.csv> --model {pth_path}{feat_flag}")


if __name__ == "__main__":
    main()