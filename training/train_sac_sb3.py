#!/usr/bin/env python3
"""
Train SAC (Soft Actor-Critic) agent using Stable-Baselines3.

SAC is off-policy with automatic entropy tuning — no target_kl to calibrate,
and the replay buffer reuses all past experience (more sample-efficient than PPO).

Key differences from PPO:
  - Off-policy: replay buffer stores all past transitions
  - Automatic entropy: ent_coef="auto" adjusts exploration dynamically
  - Twin critics: two Q-networks reduce overestimation
  - No clip/KL: trust region constraints not needed (different update mechanism)
  - Continuous actions only (our environment qualifies)

Usage:
    python training/train_sac_sb3.py --data train.csv --device cuda:0
    python training/train_sac_sb3.py --data train.csv --epochs 100 --device cpu
    python training/train_sac_sb3.py --data train.csv --epochs 3 --device cpu  # quick test
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import time

import pandas as pd
import torch
from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from training.config import (
    INDICATORS,
    TRAINED_MODEL_DIR,
    check_and_make_directories,
)
from training.envs.stocktrading_llm import StockTradingEnv


# ── Data loading ────────────────────────────────────────────


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
    """Return a callable that creates the trading environment."""
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
    """Log epoch-level stats for SAC.

    SAC doesn't have epochs like PPO. We define an "epoch" as
    steps_per_epoch environment steps for logging consistency.
    """

    def __init__(self, steps_per_epoch, total_epochs, verbose=1):
        super().__init__(verbose)
        self.steps_per_epoch = steps_per_epoch
        self.total_epochs = total_epochs
        self.start_time = None
        self.current_epoch = 0
        self.last_log_step = 0

    def _on_training_start(self):
        self.start_time = time.time()

    def _on_step(self):
        if self.num_timesteps - self.last_log_step >= self.steps_per_epoch:
            self.current_epoch += 1
            self.last_log_step = self.num_timesteps
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
                    f"Epoch {self.current_epoch}/{self.total_epochs} | "
                    f"EpRet: {mean_reward:.1f} | "
                    f"EpLen: {mean_len:.0f} | "
                    f"Time: {elapsed:.1f}s"
                )
        return True


# ── Main ────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Train SAC agent (SB3) with LLM sentiment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SAC vs PPO key differences:
  - Off-policy: replay buffer reuses all past experience
  - Automatic entropy: no target_kl calibration needed
  - Twin critics: reduces Q-value overestimation
  - Typically needs more total timesteps but each step is more efficient
        """,
    )
    parser.add_argument("--data", required=True, help="Training CSV path")
    parser.add_argument("--epochs", type=int, default=100, help="Number of epoch-equivalents")
    parser.add_argument("--steps", type=int, default=20000, help="Steps per epoch-equivalent")
    parser.add_argument("--seed", "-s", type=int, default=42)
    parser.add_argument("--hid", type=int, default=256, help="Hidden layer size (SAC default smaller than PPO)")
    parser.add_argument("--l", type=int, default=2, help="Number of hidden layers")
    parser.add_argument("--gamma", type=float, default=0.99, help="Discount factor (SAC default 0.99)")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate (SAC default 3e-4)")
    parser.add_argument(
        "--buffer-size", type=int, default=1000000,
        help="Replay buffer size",
    )
    parser.add_argument(
        "--learning-starts", type=int, default=1000,
        help="Steps before learning starts (random exploration)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=256,
        help="Minibatch size for gradient updates",
    )
    parser.add_argument(
        "--device", default="auto",
        help="Device: auto, cpu, cuda, cuda:0, cuda:1, etc.",
    )
    parser.add_argument(
        "--sentiment-scale", default="strong", choices=["strong", "weak"],
    )
    parser.add_argument(
        "--features", nargs="*", default=None,
    )
    args = parser.parse_args()

    check_and_make_directories([TRAINED_MODEL_DIR])

    # Device info
    if args.device == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device_name = args.device
    print(f"\n  Device: {device_name}")
    if device_name.startswith("cuda"):
        gpu_idx = int(device_name.split(":")[-1]) if ":" in device_name else 0
        print(f"  GPU: {torch.cuda.get_device_name(gpu_idx)}")

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
    env = DummyVecEnv([env_fn])

    print(f"  Stock Dimension: {stock_dimension}, State Space: {state_space}")
    if extra_cols:
        print(f"  Extra features ({len(extra_cols)}): {extra_cols}")

    # Build SAC model
    model = SAC(
        "MlpPolicy",
        env,
        device=args.device,
        learning_rate=args.lr,
        buffer_size=args.buffer_size,
        learning_starts=args.learning_starts,
        batch_size=args.batch_size,
        tau=0.005,                   # soft update coefficient
        gamma=args.gamma,
        train_freq=1,                # update after every step
        gradient_steps=1,            # 1 gradient step per env step
        ent_coef="auto",             # automatic entropy tuning
        target_entropy="auto",       # target entropy = -dim(action)
        seed=args.seed,
        verbose=0,
        policy_kwargs=dict(
            net_arch=[args.hid] * args.l,  # SAC uses shared arch, not dict(pi=, vf=)
        ),
    )

    total_timesteps = args.epochs * args.steps
    print(f"\n  Training: {args.epochs} epochs × {args.steps} steps = {total_timesteps} total")
    print(f"  Network: {[args.hid] * args.l} (actor + 2 critics)")
    print(f"  Buffer: {args.buffer_size}, learning_starts: {args.learning_starts}")
    print(f"  Entropy: auto")

    # Train
    callback = EpochLogCallback(args.steps, args.epochs)
    start_time = time.time()
    model.learn(total_timesteps=total_timesteps, callback=callback)
    elapsed = time.time() - start_time
    print(f"\n  Training complete in {elapsed:.1f}s ({elapsed / 60:.1f}m)")

    # Save artifacts
    from training.train_utils import generate_model_id, save_training_artifacts

    data_tag = os.path.splitext(os.path.basename(args.data))[0]
    model_id = generate_model_id(
        algorithm="sac_sb3",
        data_tag=data_tag,
        epochs=args.epochs,
        seed=args.seed,
        data_path=args.data,
    )

    model_dir = os.path.join(TRAINED_MODEL_DIR, model_id)
    os.makedirs(model_dir, exist_ok=True)

    # SB3 native save
    sb3_path = os.path.join(model_dir, "model_sb3.zip")
    model.save(sb3_path)

    # State dict for registry
    state_dict = model.policy.state_dict()
    pth_path = os.path.join(model_dir, "model.pth")
    torch.save(state_dict, pth_path)

    dates = sorted(train["date"].unique())
    train_period = f"{dates[0]} ~ {dates[-1]}" if dates else ""

    save_training_artifacts(
        model_id=model_id,
        algorithm="SAC_SB3",
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
            "buffer_size": args.buffer_size,
            "learning_starts": args.learning_starts,
            "batch_size": args.batch_size,
            "tau": 0.005,
            "ent_coef": "auto",
            "train_freq": 1,
            "gradient_steps": 1,
            "sentiment_scale": args.sentiment_scale,
            "framework": "stable-baselines3",
            "device": device_name,
        },
        data_path=args.data,
        scaler=scaler,
    )

    print(f"\n  SB3 model: {sb3_path}")
    print(f"  Model ID: {model_id}")
    feat_flag = " --features" if extra_cols else ""
    print(f"\nTo backtest:")
    print(f"  python training/backtest_sb3.py --data <trade.csv> --model {sb3_path}{feat_flag}")


if __name__ == "__main__":
    main()