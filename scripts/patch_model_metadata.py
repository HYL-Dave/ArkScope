"""Patch existing model metadata.json with state schema fields.

For models trained before the schema-in-metadata convention was added
(2026-04-23), this script backfills:

    - ticker_order         : list[str] alphabetical, from training CSV
    - tech_indicator_list  : list[str] from training/config.py INDICATORS
    - extra_feature_cols   : list[str] (usually []; mirrors meta.feature_set)
    - llm_sentiment_col    : "llm_sentiment"
    - initial_amount       : 1_000_000
    - sentiment_scale      : "strong" (from hyperparams or default)

Derivation rules:
    - Training CSV is located by parsing the model_id's data_tag. Example:
        ppo_sb3_train_polygon_multi_both_ext_100ep_s42_... → train_polygon_multi_both_ext
      → training/data_prep/output/train_polygon_multi_both_ext.csv
    - ticker_order = sorted(unique tic on first date of CSV)
    - tech_indicator_list = INDICATORS (9 names, baseline + atr) because all
      existing production models used the default config.

Usage:
    python scripts/patch_model_metadata.py                      # dry-run
    python scripts/patch_model_metadata.py --write              # apply
    python scripts/patch_model_metadata.py --models-dir <path>  # override
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from training.config import INDICATORS  # noqa: E402

MODEL_ID_DATA_TAG = re.compile(
    r"^(?:ppo|cppo)_(?:sb3_)?(.+?)_\d+ep_s(?:rnd|\d+)_"
)


def derive_data_tag(model_id: str) -> Optional[str]:
    """Extract the training CSV tag from a model_id.

    Example:
        ppo_sb3_train_polygon_multi_both_ext_100ep_s42_20260415T...
        → "train_polygon_multi_both_ext"
    """
    m = MODEL_ID_DATA_TAG.match(model_id)
    if not m:
        return None
    return m.group(1)


def derive_csv_path(data_tag: str, output_dir: Path) -> Optional[Path]:
    """Resolve the CSV path for a given data tag."""
    candidate = output_dir / f"{data_tag}.csv"
    if candidate.exists():
        return candidate
    return None


def load_ticker_order(csv_path: Path) -> List[str]:
    """Return the alphabetical ticker list as used by the env.

    Reads only the first date's rows for speed; since the env relies on
    forward-fill to ensure every date has the same ticker set, reading
    just the first date is sufficient.
    """
    first_date = pd.read_csv(csv_path, usecols=["date"], nrows=5000)["date"].iloc[0]
    df = pd.read_csv(
        csv_path, usecols=["date", "tic"],
        dtype={"date": str, "tic": str},
    )
    tics = sorted(df.loc[df["date"] == first_date, "tic"].unique().tolist())
    return tics


def build_schema_patch(meta: dict, csv_path: Path) -> dict:
    """Build the dict of schema fields to merge into metadata."""
    tickers = load_ticker_order(csv_path)

    hp = meta.get("hyperparams") or {}
    sentiment_scale = hp.get("sentiment_scale", "strong")

    patch = {
        "ticker_order": tickers,
        "tech_indicator_list": list(INDICATORS),
        "extra_feature_cols": list(meta.get("feature_set") or []),
        "llm_sentiment_col": "llm_sentiment",
        "initial_amount": 1_000_000,
        "sentiment_scale": sentiment_scale,
    }

    expected_state_dim = (
        1
        + 2 * len(tickers)
        + (1 + len(patch["tech_indicator_list"]) + len(patch["extra_feature_cols"]))
        * len(tickers)
    )
    if meta.get("state_dim") and meta["state_dim"] != expected_state_dim:
        raise ValueError(
            f"Inferred state_dim {expected_state_dim} != metadata.state_dim "
            f"{meta['state_dim']} for model {meta.get('model_id')}. "
            "The recorded stock_dim/feature_set does not match the CSV's "
            "ticker count + INDICATORS count. Refusing to patch."
        )
    if meta.get("stock_dim") and meta["stock_dim"] != len(tickers):
        raise ValueError(
            f"Inferred stock_dim {len(tickers)} != metadata.stock_dim "
            f"{meta['stock_dim']} for model {meta.get('model_id')}."
        )

    return patch


def patch_model_dir(
    model_dir: Path, output_dir: Path, write: bool, force: bool
) -> str:
    """Patch a single model's metadata.json. Returns a status label."""
    meta_path = model_dir / "metadata.json"
    if not meta_path.exists():
        return f"skip (no metadata.json): {model_dir.name}"

    with open(meta_path) as f:
        meta = json.load(f)

    model_id = meta.get("model_id") or model_dir.name

    if all(k in meta for k in ("ticker_order", "tech_indicator_list")) and not force:
        return f"skip (already has schema): {model_id}"

    data_tag = derive_data_tag(model_id)
    if not data_tag:
        return f"skip (cannot derive data_tag): {model_id}"

    csv_path = derive_csv_path(data_tag, output_dir)
    if not csv_path:
        return f"skip (CSV not found for tag '{data_tag}'): {model_id}"

    try:
        patch = build_schema_patch(meta, csv_path)
    except ValueError as e:
        return f"error: {e}"

    meta.update(patch)

    if write:
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2, default=str)
        return f"patched: {model_id} ({len(patch['ticker_order'])} tickers)"
    return f"would patch: {model_id} ({len(patch['ticker_order'])} tickers)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument(
        "--models-dir", default=str(_REPO_ROOT / "trained_models"),
        help="Directory containing model subdirs (default: trained_models/)",
    )
    parser.add_argument(
        "--output-dir", default=str(_REPO_ROOT / "training" / "data_prep" / "output"),
        help="Directory containing training CSVs",
    )
    parser.add_argument(
        "--write", action="store_true",
        help="Apply changes (default: dry-run)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-patch even if schema fields already present",
    )
    parser.add_argument(
        "--filter", default=None,
        help="Substring filter on model_id (e.g., 'both_ext' for ext models only)",
    )
    args = parser.parse_args()

    models_dir = Path(args.models_dir)
    output_dir = Path(args.output_dir)

    if not models_dir.is_dir():
        print(f"ERROR: models-dir does not exist: {models_dir}", file=sys.stderr)
        return 2

    model_dirs = sorted(
        d for d in models_dir.iterdir()
        if d.is_dir() and (d / "metadata.json").exists()
    )
    if args.filter:
        model_dirs = [d for d in model_dirs if args.filter in d.name]

    if not model_dirs:
        print("No model directories found.")
        return 0

    print(f"{'Writing' if args.write else 'Dry-run'}: {len(model_dirs)} models")
    print()

    counts = {"patched": 0, "would patch": 0, "skip": 0, "error": 0}
    for d in model_dirs:
        status = patch_model_dir(d, output_dir, args.write, args.force)
        print(f"  {status}")
        for key in counts:
            if status.startswith(key):
                counts[key] += 1
                break

    print()
    print(
        f"Summary: patched={counts['patched']}, "
        f"would_patch={counts['would patch']}, "
        f"skipped={counts['skip']}, errors={counts['error']}"
    )
    if not args.write:
        print("(dry-run; rerun with --write to apply)")
    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())