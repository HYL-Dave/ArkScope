"""C' static-baseline replay for RL collapse diagnosis.

Replays a single full training episode under one of three action policies
and records summary metrics + artifacts. Used to determine whether the
observed collapse is rooted in reward/env structure rather than PPO
hyperparameters.

Three modes:
  - trained : every step uses `model.predict(obs, deterministic=True)`
  - zero    : every step uses an all-zeros action vector
  - constant: pre-compute a deterministic action at a fixed day using the
              model's `predict_from_frame` with shares=0/cash=initial, then
              feed that same vector every step throughout the episode

The constant mode is deliberately defined from the *collapse probe* path
(not a mid-replay intermediate state) so it aligns 1:1 with the
state-invariance observation we're trying to explain.

Environment construction mirrors train_ppo_sb3.py exactly — same
FeatureEngineer, same make_env_fn, same env_kwargs — so baselines are
apples-to-apples with training reward.

Usage:
    python scripts/analysis/replay_rl_static_baselines.py \\
        --model-dir trained_models/<model_id> \\
        --data training/data_prep/output/train_polygon_multi_both_ext.csv \\
        --mode {trained|constant|zero} \\
        [--action-day YYYY-MM-DD] \\
        [--seed 42]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))


def _unwrap(env):
    """Return the underlying StockTradingEnv regardless of wrappers."""
    return env.unwrapped if hasattr(env, "unwrapped") else env


def _build_env(args, meta: dict):
    """Reconstruct the exact env used at training time."""
    from training.train_ppo_sb3 import load_data
    from training.train_utils import detect_and_load_features
    from training.train_ppo_sb3 import make_env_fn

    train, csv_indicators = load_data(args.data)
    # feature_set from metadata drives whether extra_feature_cols are loaded
    feature_set = list(meta.get("feature_set") or [])
    args_features = feature_set if feature_set else None
    train, extra_cols, _scaler = detect_and_load_features(
        train, args_features, data_path=args.data,
    )

    sentiment_scale = meta.get("sentiment_scale") or meta.get("hyperparams", {}).get(
        "sentiment_scale", "strong"
    )
    tech_indicators = meta.get("tech_indicator_list") or csv_indicators

    env_fn, stock_dim, state_space = make_env_fn(
        train,
        sentiment_scale=sentiment_scale,
        extra_feature_cols=extra_cols,
        tech_indicators=tech_indicators,
        monitor_file=None,
    )
    return env_fn(), train, stock_dim, state_space, tech_indicators, extra_cols


def _constant_action_from_day(model_dir: Path, train: pd.DataFrame, action_day: str):
    """Match the probe's definition: predict at action_day with shares=0 / cash=initial."""
    from src.rl.inference import load_model, predict_from_frame

    artifacts = load_model(model_dir)
    day_frame = train[train["date"] == action_day].reset_index(drop=True)
    if day_frame.empty:
        available = sorted(train["date"].unique())
        raise ValueError(
            f"--action-day {action_day} not found in training data; "
            f"available range: {available[0]}..{available[-1]}"
        )
    action = predict_from_frame(
        artifacts, day_frame, shares=None, cash=None, deterministic=True
    )
    return np.asarray(action, dtype=float).reshape(-1), artifacts


def _sharpe(daily_returns: np.ndarray) -> Optional[float]:
    if daily_returns.size == 0:
        return None
    std = float(np.std(daily_returns))
    if std == 0:
        return None
    return float(np.sqrt(252) * np.mean(daily_returns) / std)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--mode", required=True, choices=["trained", "constant", "zero"])
    parser.add_argument("--action-day", default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    meta_path = model_dir / "metadata.json"
    if not meta_path.exists():
        print(f"ERROR: metadata.json missing at {meta_path}", file=sys.stderr)
        return 2
    meta = json.loads(meta_path.read_text())

    # Arg validation: action-day is required iff mode==constant
    if args.mode == "constant" and not args.action_day:
        print("ERROR: --action-day is required when --mode constant", file=sys.stderr)
        return 2
    if args.mode != "constant" and args.action_day:
        print(
            f"ERROR: --action-day is only valid with --mode constant (got mode={args.mode})",
            file=sys.stderr,
        )
        return 2

    print(f"[model] {meta.get('model_id')}")
    print(f"[data ] {args.data}")
    print(f"[mode ] {args.mode}" + (f" (action-day={args.action_day})" if args.action_day else ""))

    env, train, stock_dim, state_space, tech_indicators, extra_cols = _build_env(args, meta)
    print(f"[env  ] stock_dim={stock_dim} state_space={state_space} "
          f"tickers={len(train['tic'].unique())} days={train['date'].nunique()}")

    # Pre-compute action for trained / constant modes
    trained_model = None
    constant_vec = None
    if args.mode == "trained":
        from src.rl.inference import load_model
        trained_model = load_model(model_dir)
    elif args.mode == "constant":
        constant_vec, trained_model = _constant_action_from_day(
            model_dir, train, args.action_day
        )
        print(
            f"[const] action from {args.action_day}: "
            f"mean={constant_vec.mean():+.4f} std={constant_vec.std():.4f} "
            f"range=[{constant_vec.min():+.3f}, {constant_vec.max():+.3f}]"
        )

    # ── Replay loop ─────────────────────────────────────────
    obs, _info = env.reset(seed=args.seed)
    step_rewards = []
    actions_log = []

    while True:
        if args.mode == "trained":
            action, _state = trained_model.model.predict(obs, deterministic=True)
            action = np.asarray(action, dtype=float).reshape(-1)
        elif args.mode == "constant":
            action = constant_vec
        else:  # zero
            action = np.zeros(stock_dim, dtype=float)

        obs, reward, terminated, truncated, _info = env.step(action)
        step_rewards.append(float(reward))
        actions_log.append(action.copy())
        if terminated or truncated:
            break

    # ── Collect env internals ───────────────────────────────
    u = _unwrap(env)
    asset_memory = list(getattr(u, "asset_memory", []))
    total_cost = float(getattr(u, "cost", 0.0))
    total_trades = int(getattr(u, "trades", 0))
    initial_asset = float(asset_memory[0]) if asset_memory else float("nan")
    final_asset = float(asset_memory[-1]) if asset_memory else float("nan")
    num_steps = len(step_rewards)
    episode_reward_scaled = float(np.sum(step_rewards))
    episode_reward_raw = final_asset - initial_asset
    # sanity: final_reward_scaled should equal episode_reward_scaled
    reward_scaling = float(getattr(u, "reward_scaling", 1e-4))
    final_reward_scaled = episode_reward_raw * reward_scaling

    daily_returns = np.array([])
    if len(asset_memory) >= 2:
        am = np.asarray(asset_memory, dtype=float)
        daily_returns = np.diff(am) / am[:-1]
    sharpe = _sharpe(daily_returns)

    # ── Output artifacts ────────────────────────────────────
    diag_dir = model_dir / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)
    suffix = args.mode + (f"_{args.action_day}" if args.action_day else "")
    summary = {
        "model_id": meta.get("model_id"),
        "mode": args.mode,
        "seed": args.seed,
        "action_day": args.action_day,
        "num_steps": num_steps,
        "initial_asset": initial_asset,
        "final_asset": final_asset,
        "episode_reward_raw": episode_reward_raw,
        "episode_reward_scaled": episode_reward_scaled,
        "final_reward_scaled": final_reward_scaled,
        "reward_scaling": reward_scaling,
        "total_cost": total_cost,
        "total_trades": total_trades,
        "sharpe": sharpe,
        "reward_scaled_matches_final": bool(
            np.isclose(episode_reward_scaled, final_reward_scaled, rtol=1e-6, atol=1e-6)
        ),
    }

    summary_path = diag_dir / f"replay_{suffix}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str))

    # account_value.csv
    if asset_memory:
        pd.DataFrame({"step": range(len(asset_memory)), "asset": asset_memory}).to_csv(
            diag_dir / f"replay_{suffix}_account_value.csv", index=False
        )

    # actions.csv (step × stock_dim); for 143 tickers × ~1072 steps this is ~150k cells
    if actions_log:
        ticker_cols = meta.get("ticker_order") or [f"t{i}" for i in range(stock_dim)]
        pd.DataFrame(actions_log, columns=ticker_cols).to_csv(
            diag_dir / f"replay_{suffix}_actions.csv", index=False
        )

    # ── Stdout summary ──────────────────────────────────────
    print()
    print(f"=== {args.mode.upper()} replay summary ===")
    print(f"  steps                : {num_steps}")
    print(f"  initial_asset        : {initial_asset:,.2f}")
    print(f"  final_asset          : {final_asset:,.2f}")
    print(f"  episode_reward_raw   : {episode_reward_raw:+,.2f}")
    print(f"  episode_reward_scaled: {episode_reward_scaled:+.4f}")
    print(f"  final_reward_scaled  : {final_reward_scaled:+.4f}  "
          f"(match={summary['reward_scaled_matches_final']})")
    print(f"  total_cost           : {total_cost:,.2f}")
    print(f"  total_trades         : {total_trades:,d}")
    print(f"  sharpe               : {sharpe if sharpe is None else f'{sharpe:+.4f}'}")
    print(f"[saved] {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())