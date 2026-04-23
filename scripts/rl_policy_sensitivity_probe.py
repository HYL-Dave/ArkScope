"""Probe policy sensitivity across models and dates.

Diagnostic — not a permanent production tool. Answers the question:
  "Does the trained policy respond to state differences, or is it
   producing near-constant deterministic actions regardless of input?"

Per model, computes:
  - deterministic action at N widely separated training dates
  - pairwise action correlation matrix across those dates
  - corresponding observation delta (sanity check the inputs really differ)
  - stochastic-mode action spread on a single frame (policy variance)

A healthy policy: obs changes → action changes; corr across different
dates should be well below 1.0. A collapsed policy: obs changes → action
stays nearly constant; corr ≈ 1.0 everywhere.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.rl.inference import load_model, predict_from_frame  # noqa: E402
from training.data_prep.state_builder import build_observation  # noqa: E402


_DATES = ["2023-06-15", "2024-01-05", "2024-08-20", "2025-03-10", "2025-07-10", "2026-04-13"]


def _load_frames(csv_path: Path, dates: Sequence[str]) -> dict:
    df = pd.read_csv(csv_path, index_col=0)
    df["date"] = df["date"].astype(str)
    frames = {}
    for d in dates:
        sub = df[df["date"] == d].reset_index(drop=True)
        if not sub.empty:
            frames[d] = sub
    return frames


def _probe_model(model_dir: Path, frames: dict) -> dict:
    art = load_model(model_dir)
    schema = art.schema
    actions = {}
    obss = {}
    for d, f in frames.items():
        obss[d] = build_observation(f, schema)
        actions[d] = predict_from_frame(art, f, deterministic=True)

    # stochastic spread on one frame
    first = next(iter(frames))
    a_s1 = predict_from_frame(art, frames[first], deterministic=False)
    a_s2 = predict_from_frame(art, frames[first], deterministic=False)
    stoch_spread = float(np.abs(a_s1 - a_s2).mean())

    # pairwise correlations
    date_list = list(actions.keys())
    n = len(date_list)
    corr = np.zeros((n, n), dtype=float)
    for i, di in enumerate(date_list):
        for j, dj in enumerate(date_list):
            corr[i, j] = float(np.corrcoef(actions[di], actions[dj])[0, 1])

    # obs delta magnitude — confirm inputs really are different
    first_obs = obss[date_list[0]]
    last_obs = obss[date_list[-1]]
    obs_delta_mean = float(np.abs(first_obs - last_obs).mean())

    # action range
    all_actions = np.stack(list(actions.values()))
    per_date_mean = all_actions.mean(axis=1)
    return {
        "model_id": art.metadata["model_id"],
        "actions_per_date_mean": per_date_mean.tolist(),
        "corr_min_offdiag": float(np.min(corr + np.eye(n))),  # exclude diagonal (always 1)
        "corr_max_offdiag": float(np.max(corr - 2 * np.eye(n))),
        "obs_delta_mean_first_last": obs_delta_mean,
        "stoch_spread_same_frame": stoch_spread,
        "det_action_std_across_dates": float(all_actions.std()),
    }


def _csv_for_model(model_dir: Path) -> Path:
    """Map model_id → training CSV used, via the data_tag in model_id."""
    name = model_dir.name
    parts = name.split("_")
    try:
        ep_idx = next(i for i, p in enumerate(parts) if p.endswith("ep"))
    except StopIteration:
        raise ValueError(f"Cannot derive data tag from model_id {name}")
    tag = "_".join(parts[2:ep_idx])  # drop algo prefix
    return _REPO_ROOT / "training" / "data_prep" / "output" / f"{tag}.csv"


def main() -> int:
    models_dir = _REPO_ROOT / "trained_models"
    all_models = sorted(
        p for p in models_dir.iterdir()
        if p.is_dir()
        and p.name.startswith("ppo_sb3_train_polygon")
        and (p / "metadata.json").exists()
    )

    # group models by (variant, is_extended) so we probe diverse configurations
    ext = [p for p in all_models if "both_ext" in p.name]
    baseline_ab = [p for p in all_models if "_77b42b" in p.name]  # A/B baseline seeds
    baseline_srnd = [p for p in all_models if "_e8c66f" in p.name]  # production ensemble seeds

    print(
        f"[counts] ext={len(ext)}  baseline_ab={len(baseline_ab)}  "
        f"baseline_srnd={len(baseline_srnd)}"
    )
    print()

    # Cache frames per CSV (baseline CSV differs from ext)
    csv_cache: dict[Path, dict] = {}
    for mdir in ext + baseline_ab + baseline_srnd:
        csv = _csv_for_model(mdir)
        if csv not in csv_cache:
            if csv.exists():
                csv_cache[csv] = _load_frames(csv, _DATES)
            else:
                csv_cache[csv] = {}

    def probe_group(label: str, models: list[Path]) -> None:
        if not models:
            return
        print(f"\n=== {label} ({len(models)} models) ===")
        print(
            f"{'model':60s}  {'stoch':>8s}  {'det_std':>8s}  {'obs_Δ':>8s}  {'corr_range':>15s}"
        )
        print("-" * 115)
        for mdir in models:
            csv = _csv_for_model(mdir)
            frames = csv_cache.get(csv, {})
            if not frames:
                print(f"SKIP {mdir.name}: CSV missing {csv}")
                continue
            try:
                r = _probe_model(mdir, frames)
            except Exception as e:
                print(f"FAIL {mdir.name}: {type(e).__name__}: {e}")
                continue
            short = r["model_id"][-50:]
            corr_range = f"[{r['corr_min_offdiag']:.3f},{r['corr_max_offdiag']:.3f}]"
            print(
                f"{short:60s}  "
                f"{r['stoch_spread_same_frame']:8.3f}  "
                f"{r['det_action_std_across_dates']:8.4f}  "
                f"{r['obs_delta_mean_first_last']:8.1f}  "
                f"{corr_range:>15s}"
            )

    probe_group("EXT (9 indicators, A/B ext + full-data)", ext)
    probe_group("BASELINE A/B seeds (8 indicators)", baseline_ab)
    probe_group("BASELINE production ensemble (srnd, 8 indicators)", baseline_srnd)

    print()
    print("Key: stoch = policy variance on fixed input (>0 means network works)")
    print("     det_std = action variation across all dates (small → near-constant output)")
    print("     obs_Δ = observation mean diff between first/last date (large means input varies)")
    print("     corr = pairwise corr range across dates (near 1 → action doesn't change with state)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())