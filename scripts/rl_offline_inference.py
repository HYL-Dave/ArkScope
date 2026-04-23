"""Offline RL inference dry-run (Phase B0).

Pick a date from a training CSV, feed the day's rows into the loaded
PPO model, and print top buys / top sells. No IBKR, no DB writes,
no live feature computation — this is the model-loading and action-decode
smoke test that precedes B1 (live feature frame) and B2 (signal report).

Usage:
    python scripts/rl_offline_inference.py
    python scripts/rl_offline_inference.py --model-dir <path> --date 2026-04-10
    python scripts/rl_offline_inference.py --top-n 15 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.rl.inference import decode_action, load_model, predict_from_frame  # noqa: E402

_DEFAULT_MODEL_DIR = (
    _REPO_ROOT
    / "trained_models"
    / "ppo_sb3_train_polygon_multi_both_ext_100ep_s42_20260415T165924Z_9c0a66"
)


def _resolve_csv_for_model(model_dir: Path) -> Path:
    """Derive the training CSV path from the model's data_tag."""
    name = model_dir.name  # e.g. "ppo_sb3_train_polygon_multi_both_ext_100ep_s42_..."
    # The tag sits between the algo prefix and "_<N>ep_s..."
    parts = name.split("_")
    try:
        ep_idx = next(i for i, p in enumerate(parts) if p.endswith("ep"))
    except StopIteration:
        raise ValueError(f"Cannot derive data tag from model_id {name}")
    tag_parts = parts[2:ep_idx]  # drop "ppo" + "sb3"
    tag = "_".join(tag_parts)
    return _REPO_ROOT / "training" / "data_prep" / "output" / f"{tag}.csv"


def _load_day_frame(csv_path: Path, date: str | None) -> tuple[pd.DataFrame, str]:
    df = pd.read_csv(csv_path, index_col=0)
    df["date"] = df["date"].astype(str)
    available = sorted(df["date"].unique())
    if date is None:
        date = available[-1]
    if date not in set(available):
        raise ValueError(
            f"Date {date} not in CSV range {available[0]}..{available[-1]}"
        )
    day_frame = df[df["date"] == date].reset_index(drop=True)
    return day_frame, date


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument(
        "--model-dir", default=str(_DEFAULT_MODEL_DIR),
        help="Path to the model artifact directory",
    )
    parser.add_argument(
        "--csv", default=None,
        help="Training CSV to sample a day from (default: derive from model tag)",
    )
    parser.add_argument(
        "--date", default=None,
        help="YYYY-MM-DD to predict for (default: last date in CSV)",
    )
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--buy-threshold", type=float, default=0.1)
    parser.add_argument("--sell-threshold", type=float, default=-0.1)
    parser.add_argument(
        "--deterministic", action=argparse.BooleanOptionalAction, default=True,
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit the full decoded signal dict as JSON (for piping)",
    )
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    csv_path = Path(args.csv) if args.csv else _resolve_csv_for_model(model_dir)

    print(f"[model]  {model_dir.name}")
    print(f"[csv]    {csv_path}")

    artifacts = load_model(model_dir)
    print(
        f"[schema] stock_dim={artifacts.schema.stock_dim}  "
        f"state_dim={artifacts.schema.state_dim}  "
        f"indicators={len(artifacts.schema.tech_indicator_list)}"
    )

    day_frame, date = _load_day_frame(csv_path, args.date)
    print(f"[date]   {date}  ({len(day_frame)} tickers in frame)")

    action = predict_from_frame(
        artifacts, day_frame, deterministic=args.deterministic
    )

    decoded = decode_action(
        action,
        artifacts.schema.ticker_order,
        top_n=args.top_n,
        buy_threshold=args.buy_threshold,
        sell_threshold=args.sell_threshold,
    )

    if args.json:
        json.dump(decoded, sys.stdout, indent=2)
        print()
        return 0

    dist = decoded["distribution"]
    stats = decoded["stats"]
    print(
        f"[dist]   buy={dist['buy']}  sell={dist['sell']}  hold={dist['hold']}  "
        f"(action mean={stats['mean']:+.3f} std={stats['std']:.3f} "
        f"range=[{stats['min']:+.3f}, {stats['max']:+.3f}])"
    )
    print()
    print("Top buys:")
    if not decoded["top_buys"]:
        print("  (none above 0)")
    for entry in decoded["top_buys"]:
        print(f"  {entry['ticker']:6s}  action={entry['action']:+.4f}  {entry['signal']}")
    print()
    print("Top sells:")
    if not decoded["top_sells"]:
        print("  (none below 0)")
    for entry in decoded["top_sells"]:
        print(f"  {entry['ticker']:6s}  action={entry['action']:+.4f}  {entry['signal']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())