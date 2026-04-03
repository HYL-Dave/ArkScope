#!/usr/bin/env python3
"""
Train CPPO (CVaR-constrained PPO) agent using Stable-Baselines3.

Drop-in replacement for train_cppo_llm_risk.py (SpinningUp), using
the same environment and CVaR constraint logic. Single-process (no MPI),
suitable for large-scale parallel experiments (~1 CPU core per run).

The CVaR constraint modifies advantages in the rollout buffer after
collection, penalizing trajectories with poor risk-adjusted returns.

Usage:
    python training/train_cppo_sb3.py --data train.csv --device cpu
    python training/train_cppo_sb3.py --data train.csv --epochs 3 --device cpu  # quick test
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import time
from typing import Optional

import numpy as np
import pandas as pd
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from training.config import (
    INDICATORS,
    SENTIMENT_SCALES,
    TRAINED_MODEL_DIR,
    check_and_make_directories,
)
from training.envs.stocktrading_llm_risk import StockTradingEnv


# ── Data loading ────────────────────────────────────────────


def load_data(data_path):
    """Load and prepare training dataset from local CSV."""
    train = pd.read_csv(data_path)
    if "Unnamed: 0" in train.columns:
        train = train.drop("Unnamed: 0", axis=1)

    required = ["date", "tic", "close", "llm_sentiment", "llm_risk"] + list(INDICATORS)
    missing = [c for c in required if c not in train.columns]
    if missing:
        raise ValueError(
            f"CSV missing required column(s): {missing}. "
            "CPPO requires llm_sentiment + llm_risk. "
            "See training/data_prep/README.md for format spec."
        )

    train["date"] = train["date"].astype(str)
    train = train.sort_values(["date", "tic"]).reset_index(drop=True)
    unique_dates = train["date"].unique()
    date_to_idx = {date: idx for idx, date in enumerate(unique_dates)}
    train["new_idx"] = train["date"].map(date_to_idx)
    train = train.set_index("new_idx")
    train["llm_sentiment"] = train["llm_sentiment"].fillna(0)
    train["llm_risk"] = train["llm_risk"].fillna(3)

    return train


# ── Environment factory ─────────────────────────────────────


def make_env_fn(train, sentiment_scale="strong", extra_feature_cols=None):
    """Return a callable that creates the CPPO trading environment."""
    extra = extra_feature_cols or []
    stock_dimension = len(train.tic.unique())
    K = len(INDICATORS)
    F = len(extra)
    # CPPO: cash + close + shares + indicators + extra + sentiment + risk
    state_space = 1 + 2 * stock_dimension + (2 + K + F) * stock_dimension

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


# ── CVaR-constrained PPO ────────────────────────────────────


class CPPO_SB3(PPO):
    """PPO with CVaR risk constraint, ported from SpinningUp cppo.py.

    After each rollout, modifies advantages in the buffer to penalize
    trajectories with poor risk-adjusted returns.

    The CVaR constraint uses LLM risk scores extracted from observations
    (last stock_dim elements) to compute a portfolio risk factor.
    """

    def __init__(
        self,
        *args,
        stock_dim: int,
        risk_weights: Optional[dict] = None,
        alpha: float = 0.85,
        beta: float = 3000.0,
        nu_lr: float = 5e-4,
        lam_lr: float = 5e-4,
        nu_start: float = 0.1,
        lam_start: float = 0.01,
        nu_delay: float = 0.75,
        delay: float = 1.0,
        cvar_clip_ratio: float = 0.05,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.stock_dim = stock_dim
        self.risk_weights = risk_weights or SENTIMENT_SCALES["strong"]["risk_weights"]
        self.alpha = alpha
        self.beta = beta
        self.nu_lr = nu_lr
        self.lam_lr = lam_lr
        self.nu_delay = nu_delay
        self.delay = delay
        self.cvar_clip_ratio = cvar_clip_ratio

        # Adaptive CVaR parameters
        self.nu = nu_start
        self.cvarlam = lam_start

        # Per-episode tracking
        self._ep_ret = 0.0
        self._ep_returns = []

    def collect_rollouts(self, env, callback, rollout_buffer, n_rollout_steps):
        """Override to track per-step CVaR penalties during rollout."""
        # Reset episode tracking
        self._ep_returns = []
        self._step_penalties = np.zeros(n_rollout_steps, dtype=np.float32)
        self._step_values = np.zeros(n_rollout_steps, dtype=np.float32)
        self._ep_ret = 0.0
        self._ep_start_idx = 0

        # Update cvarlam at the start of each rollout (= epoch)
        self.cvarlam = self.cvarlam + self.lam_lr * (self.beta - self.nu)

        result = super().collect_rollouts(env, callback, rollout_buffer, n_rollout_steps)

        # After collection, apply CVaR penalty to advantages in the buffer
        self._apply_cvar_penalty(rollout_buffer)

        # Update nu from episode returns
        if self._ep_returns:
            self.nu = np.mean(self._ep_returns) * self.nu_delay

        return result

    def _apply_cvar_penalty(self, rollout_buffer):
        """Apply CVaR penalty to advantages, matching SpinningUp's cppo.py logic.

        For each step, compute the risk-adjusted trajectory return.
        If below threshold nu, penalize the advantage.
        """
        obs = rollout_buffer.observations
        values = rollout_buffer.values
        rewards = rollout_buffer.rewards
        advantages = rollout_buffer.advantages

        ep_ret = 0.0
        bad_trajectory_num = 0
        update_num = 0

        for t in range(rollout_buffer.buffer_size):
            if not rollout_buffer.episode_starts[t] and t > 0:
                ep_ret += rewards[t].item()
            else:
                # New episode starts
                ep_ret = rewards[t].item()

            ob = obs[t].flatten()
            v = values[t].item()
            r = rewards[t].item()

            # Extract risk scores from observation (last stock_dim elements)
            llm_risks = ob[-self.stock_dim:]

            # Map to weights
            risk_weight_arr = np.array(
                [self.risk_weights.get(int(round(rs)), 1.0) for rs in llm_risks]
            )

            # Portfolio weights from observation
            prices = ob[1:self.stock_dim + 1]
            shares = ob[self.stock_dim + 1:self.stock_dim * 2 + 1]
            stock_values = prices * shares
            total_value = np.sum(stock_values)

            if total_value > 0:
                stock_weights = stock_values / total_value
                llm_risk_factor = np.dot(stock_weights, risk_weight_arr)
            else:
                llm_risk_factor = 1.0

            adjusted_D_pi = llm_risk_factor * (ep_ret + v - r)

            if adjusted_D_pi < self.nu:
                bad_trajectory_num += 1
                penalty = self.delay * self.cvarlam / (1 - self.alpha) * (self.nu - adjusted_D_pi)
                # Clip penalty
                if penalty > abs(v) * self.cvar_clip_ratio:
                    penalty = abs(v) * self.cvar_clip_ratio
                    update_num += 1
                advantages[t] -= penalty

            # Track episode returns at episode boundaries
            if t + 1 < rollout_buffer.buffer_size and rollout_buffer.episode_starts[t + 1]:
                self._ep_returns.append(adjusted_D_pi)
                ep_ret = 0.0

        # Last episode
        if ep_ret != 0.0:
            self._ep_returns.append(ep_ret)

        # Re-normalize advantages after modification
        adv_mean = advantages.mean()
        adv_std = advantages.std()
        if adv_std > 1e-8:
            advantages[:] = (advantages - adv_mean) / adv_std

        if bad_trajectory_num > 0:
            print(f"  CVaR: bad_trajectories={bad_trajectory_num}, "
                  f"clipped={update_num}, nu={self.nu:.4f}, lam={self.cvarlam:.4f}")


# ── Logging callback ────────────────────────────────────────


class EpochLogCallback(BaseCallback):
    """Log epoch-level stats."""

    def __init__(self, epochs, verbose=1):
        super().__init__(verbose)
        self.epochs = epochs
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
        description="Train CPPO agent (SB3, CVaR-constrained PPO) with LLM risk signals",
    )
    parser.add_argument("--data", required=True, help="Training CSV path")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--steps", type=int, default=20000, help="Steps per epoch")
    parser.add_argument("--seed", "-s", type=int, default=0)
    parser.add_argument("--hid", type=int, default=512)
    parser.add_argument("--l", type=int, default=2)
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--lr", type=float, default=3e-5, help="Policy learning rate")
    parser.add_argument(
        "--device", default="cpu",
        help="Device: auto, cpu, cuda, cuda:0, cuda:1, etc.",
    )
    parser.add_argument(
        "--sentiment-scale", default="strong", choices=["strong", "weak"],
    )
    parser.add_argument(
        "--features", nargs="*", default=None,
    )
    # CVaR parameters
    parser.add_argument("--alpha", type=float, default=0.85, help="CVaR confidence level")
    parser.add_argument("--beta", type=float, default=3000.0, help="CVaR constraint bound")
    parser.add_argument(
        "--full-batch", action="store_true",
        help="Use full-batch gradient (like SpinningUp) instead of minibatch.",
    )
    args = parser.parse_args()

    check_and_make_directories([TRAINED_MODEL_DIR])

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

    print(f"\n  Device: {args.device}")
    print(f"  Stock Dimension: {stock_dimension}, State Space: {state_space}")

    # Aligned hyperparams (same as train_ppo_sb3.py)
    pi_lr = args.lr
    vf_coef = 1e-4 / pi_lr  # ≈ 3.33, matching SpinningUp's vf_lr=1e-4

    if args.full_batch:
        batch_size = args.steps
        n_epochs = 100
        batch_mode = "full-batch"
    else:
        batch_size = min(args.steps, 2000)
        n_epochs = 10
        batch_mode = "minibatch"

    scale = SENTIMENT_SCALES[args.sentiment_scale]

    model = CPPO_SB3(
        "MlpPolicy",
        env,
        device=args.device,
        learning_rate=pi_lr,
        n_steps=args.steps,
        batch_size=batch_size,
        n_epochs=n_epochs,
        gamma=args.gamma,
        gae_lambda=0.95,
        clip_range=0.7,
        target_kl=0.35,
        vf_coef=vf_coef,
        ent_coef=0.0,
        max_grad_norm=float("inf"),
        seed=args.seed,
        verbose=0,
        policy_kwargs=dict(
            net_arch=dict(pi=[args.hid] * args.l, vf=[args.hid] * args.l),
            activation_fn=torch.nn.Tanh,
        ),
        # CPPO-specific
        stock_dim=stock_dimension,
        risk_weights=scale["risk_weights"],
        alpha=args.alpha,
        beta=args.beta,
    )

    total_timesteps = args.epochs * args.steps
    print(f"  Training: {args.epochs} epochs × {args.steps} steps = {total_timesteps} total")
    print(f"  Batch mode: {batch_mode} (batch_size={batch_size}, n_epochs={n_epochs})")
    print(f"  CVaR: alpha={args.alpha}, beta={args.beta}")

    callback = EpochLogCallback(args.epochs)
    start_time = time.time()
    model.learn(total_timesteps=total_timesteps, callback=callback)
    elapsed = time.time() - start_time
    print(f"\n  Training complete in {elapsed:.1f}s ({elapsed / 60:.1f}m)")

    # Save artifacts
    from training.train_utils import generate_model_id, save_training_artifacts

    data_tag = os.path.splitext(os.path.basename(args.data))[0]
    model_id = generate_model_id(
        algorithm="cppo_sb3",
        data_tag=data_tag,
        epochs=args.epochs,
        seed=args.seed,
        data_path=args.data,
    )

    model_dir = os.path.join(TRAINED_MODEL_DIR, model_id)
    os.makedirs(model_dir, exist_ok=True)

    sb3_path = os.path.join(model_dir, "model_sb3.zip")
    model.save(sb3_path)

    state_dict = model.policy.state_dict()
    pth_path = os.path.join(model_dir, "model.pth")
    torch.save(state_dict, pth_path)

    dates = sorted(train["date"].unique())
    train_period = f"{dates[0]} ~ {dates[-1]}" if dates else ""

    save_training_artifacts(
        model_id=model_id,
        algorithm="CPPO_SB3",
        model_state_dict=state_dict,
        score_source=data_tag,
        extra_cols=extra_cols,
        stock_dim=stock_dimension,
        state_dim=state_space,
        train_period=train_period,
        epochs=args.epochs,
        seed=args.seed,
        score_type="both",
        hyperparams={
            "hid": args.hid,
            "layers": args.l,
            "gamma": args.gamma,
            "pi_lr": pi_lr,
            "vf_lr_effective": pi_lr * vf_coef,
            "vf_coef": round(vf_coef, 4),
            "n_epochs": n_epochs,
            "batch_size": batch_size,
            "batch_mode": batch_mode,
            "clip_range": 0.7,
            "target_kl": 0.35,
            "alpha": args.alpha,
            "beta": args.beta,
            "sentiment_scale": args.sentiment_scale,
            "risk_weights": scale["risk_weights"],
            "framework": "stable-baselines3",
            "device": args.device,
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