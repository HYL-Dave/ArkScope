"""Extract SB3 training metrics from a model's tensorboard events file.

Pulls the rollout/* and train/* scalars that V-lite triage needs, joins
them on step, writes train_metrics.csv under the model dir, and prints
a short summary table for root-cause interpretation.

Usage:
    python scripts/analysis/extract_sb3_train_metrics.py \\
        --model-dir trained_models/<model_id>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

# Tags to extract — train/* first because they are the actor/critic diagnostics,
# rollout/* second as context. train/std may be absent in some SB3 versions;
# extractor falls back to train/entropy_loss for exploration signal.
_PRIMARY_TAGS = [
    "train/approx_kl",
    "train/clip_fraction",
    "train/std",
    "train/entropy_loss",
    "train/policy_gradient_loss",
    "train/value_loss",
    "train/explained_variance",
    "rollout/ep_rew_mean",
    "rollout/ep_len_mean",
    "time/total_timesteps",
]


def _find_tfevents(model_dir: Path) -> Path:
    """Locate the first events.out.tfevents* file under model_dir/tb/**."""
    hits = sorted(model_dir.rglob("events.out.tfevents.*"))
    if not hits:
        raise FileNotFoundError(
            f"No events.out.tfevents* under {model_dir}. "
            f"Ensure training was run with --telemetry."
        )
    return hits[0]


def _load_scalars(tfevents_path: Path, tags: List[str]) -> Dict[str, pd.DataFrame]:
    from tensorboard.backend.event_processing.event_accumulator import (
        EventAccumulator,
    )

    ea = EventAccumulator(str(tfevents_path), size_guidance={"scalars": 0})
    ea.Reload()

    available = set(ea.Tags().get("scalars", []))
    per_tag = {}
    for tag in tags:
        if tag not in available:
            per_tag[tag] = pd.DataFrame(columns=["step", tag])
            continue
        events = ea.Scalars(tag)
        df = pd.DataFrame(
            {"step": [e.step for e in events], tag: [e.value for e in events]}
        )
        per_tag[tag] = df
    return per_tag


def _outer_join_by_step(per_tag: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    combined = None
    for tag, df in per_tag.items():
        if df.empty:
            continue
        if combined is None:
            combined = df
        else:
            combined = combined.merge(df, on="step", how="outer")
    if combined is None:
        return pd.DataFrame(columns=["step"] + list(per_tag.keys()))
    for tag in per_tag:
        if tag not in combined.columns:
            combined[tag] = pd.NA
    return combined.sort_values("step").reset_index(drop=True)


def _summary_row(series: pd.Series, name: str) -> str:
    s = series.dropna()
    if s.empty:
        return f"  {name:32s} : (no data)"
    return (
        f"  {name:32s} : first={s.iloc[0]:+.4f}  last={s.iloc[-1]:+.4f}  "
        f"min={s.min():+.4f}  max={s.max():+.4f}  mean={s.mean():+.4f}  "
        f"n={len(s)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--model-dir", required=True, help="trained_models/<model_id>")
    parser.add_argument(
        "--output-csv", default=None,
        help="Output path for joined CSV (default: <model-dir>/train_metrics.csv)"
    )
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    if not model_dir.is_dir():
        print(f"ERROR: not a directory: {model_dir}", file=sys.stderr)
        return 2

    try:
        tfevents = _find_tfevents(model_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(f"[src] {tfevents}")
    per_tag = _load_scalars(tfevents, _PRIMARY_TAGS)

    found = [t for t, df in per_tag.items() if not df.empty]
    missing = [t for t in _PRIMARY_TAGS if t not in found]
    if missing:
        print(f"[warn] missing tags: {missing}")

    combined = _outer_join_by_step(per_tag)
    out_csv = Path(args.output_csv) if args.output_csv else model_dir / "train_metrics.csv"
    combined.to_csv(out_csv, index=False)
    print(f"[out] {out_csv}  ({len(combined)} rows)")

    print()
    print("=== Actor update regime ===")
    print(_summary_row(combined.get("train/approx_kl", pd.Series(dtype=float)), "approx_kl"))
    print(_summary_row(combined.get("train/clip_fraction", pd.Series(dtype=float)), "clip_fraction"))
    print(_summary_row(combined.get("train/std", pd.Series(dtype=float)), "std (policy)"))
    print(_summary_row(combined.get("train/entropy_loss", pd.Series(dtype=float)), "entropy_loss"))
    print(_summary_row(combined.get("train/policy_gradient_loss", pd.Series(dtype=float)), "policy_gradient_loss"))

    print()
    print("=== Critic health ===")
    print(_summary_row(combined.get("train/value_loss", pd.Series(dtype=float)), "value_loss"))
    print(_summary_row(combined.get("train/explained_variance", pd.Series(dtype=float)), "explained_variance"))

    print()
    print("=== Rollout reward (context) ===")
    print(_summary_row(combined.get("rollout/ep_rew_mean", pd.Series(dtype=float)), "ep_rew_mean"))
    print(_summary_row(combined.get("rollout/ep_len_mean", pd.Series(dtype=float)), "ep_len_mean"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())