#!/usr/bin/env python3
"""
Rename scoring columns from generic 'sentiment_deepseek'/'risk_deepseek'
to model-specific names for open-source release.

This script processes all scoring CSV files and creates renamed versions
with proper column names reflecting the actual model used.

Output options:
1. --output-dir: Create renamed files in a separate directory (preserving structure)
2. --output-suffix: Add suffix to original filenames
3. --in-place: Overwrite original files (use with caution!)

Usage examples:
  # Create renamed files in /mnt/md0/finrl/renamed/ (recommended)
  python rename_score_columns.py --output-dir /mnt/md0/finrl/renamed

  # Dry run to see what would be done
  python rename_score_columns.py --output-dir /mnt/md0/finrl/renamed --dry-run

  # Process single file
  python rename_score_columns.py --single-file /path/to/file.csv --output-dir /output
"""

import os
import re
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from datetime import datetime
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Base directory for finrl data
FINRL_BASE = "/mnt/md0/finrl"

# Model name to column suffix mapping
# Column naming convention: sentiment_{suffix}, risk_{suffix}
MODEL_COLUMN_MAP = {
    # OpenAI reasoning models
    "o3": "o3",
    "o4-mini": "o4_mini",
    # GPT-5 family
    "gpt-5": "gpt_5",
    "gpt-5-mini": "gpt_5_mini",
    # GPT-4.1 family
    "gpt-4.1": "gpt_4_1",
    "gpt-4.1-mini": "gpt_4_1_mini",
    "gpt-4.1-nano": "gpt_4_1_nano",
    # Claude models - use specific model names
    "sonnet": "sonnet",
    "haiku": "haiku",
    "opus": "opus",
}


def detect_model_from_path(file_path: str) -> Optional[str]:
    """Detect the scoring model from file path."""
    path = Path(file_path)
    parts = path.parts

    # Check parent directory first (e.g., /finrl/o3/sentiment/...)
    for i, part in enumerate(parts):
        if part == "finrl" and i + 1 < len(parts):
            model_dir = parts[i + 1]
            if model_dir in MODEL_COLUMN_MAP:
                return model_dir
            # Handle claude subdirectory
            if model_dir == "claude":
                # Check filename for specific claude model
                fname = path.stem.lower()
                for model in ["sonnet", "haiku", "opus"]:
                    if model in fname:
                        return model
                return "claude"

    return None


def get_column_suffix(model: str) -> str:
    """Get the column suffix for a model."""
    return MODEL_COLUMN_MAP.get(model, model.replace("-", "_").replace(".", "_"))


def rename_columns_in_file(
    input_path: str,
    output_path: str,
    model: str,
    dry_run: bool = False,
    remove_unnamed: bool = True,
) -> Dict:
    """
    Rename scoring columns in a CSV file.

    Args:
        input_path: Path to input CSV
        output_path: Path to output CSV
        model: Model name for column naming
        dry_run: If True, only report what would be done
        remove_unnamed: If True, remove 'Unnamed:' columns

    Returns:
        Dict with stats about the operation
    """
    stats = {
        "input_path": input_path,
        "output_path": output_path,
        "model": model,
        "columns_renamed": [],
        "columns_removed": [],
        "rows": 0,
        "success": False,
    }

    try:
        df = pd.read_csv(input_path, low_memory=False)
        stats["rows"] = len(df)
        original_cols = list(df.columns)

        suffix = get_column_suffix(model)
        rename_map = {}

        # Detect task type from filename
        fname = Path(input_path).stem.lower()
        is_sentiment = "sentiment" in fname
        is_risk = "risk" in fname

        # Build rename mapping
        # Note: Claude files already have proper _claude columns and the deepseek columns
        # are from the original base dataset, so we skip renaming for Claude models
        is_claude_model = model in ["haiku", "sonnet", "opus"]

        if is_sentiment:
            if "sentiment_deepseek" in df.columns:
                new_name = f"sentiment_{suffix}"
                # Skip if this is a Claude model (deepseek column is base dataset score)
                # Skip if target column already exists
                if not is_claude_model and new_name not in df.columns:
                    rename_map["sentiment_deepseek"] = new_name

        if is_risk:
            if "risk_deepseek" in df.columns:
                new_name = f"risk_{suffix}"
                # Skip if this is a Claude model (deepseek column is base dataset score)
                # Skip if target column already exists
                if not is_claude_model and new_name not in df.columns:
                    rename_map["risk_deepseek"] = new_name

        stats["columns_renamed"] = list(rename_map.items())

        if dry_run:
            logging.info(f"[DRY RUN] Would rename in {input_path}:")
            for old, new in rename_map.items():
                logging.info(f"  {old} -> {new}")
            stats["success"] = True
            return stats

        # Apply renames
        if rename_map:
            df = df.rename(columns=rename_map)

        # Remove unnamed columns if requested
        if remove_unnamed:
            unnamed_cols = [c for c in df.columns if c.startswith("Unnamed:")]
            if unnamed_cols:
                df = df.drop(columns=unnamed_cols)
                stats["columns_removed"] = unnamed_cols

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save
        df.to_csv(output_path, index=False)
        stats["success"] = True

        logging.info(f"Created: {output_path}")
        if stats["columns_renamed"]:
            for old, new in stats["columns_renamed"]:
                logging.info(f"  Renamed: {old} -> {new}")
        if stats["columns_removed"]:
            logging.info(f"  Removed: {stats['columns_removed']}")

    except Exception as e:
        logging.error(f"Error processing {input_path}: {e}")
        stats["error"] = str(e)

    return stats


def find_scoring_files(base_dir: str = FINRL_BASE) -> list:
    """Find all scoring CSV files (excluding backups)."""
    files = []
    for root, dirs, filenames in os.walk(base_dir):
        # Skip backup directories
        if "backup" in root.lower() or "huggingface" in root.lower():
            continue

        for fname in filenames:
            if fname.endswith(".csv"):
                if "sentiment" in fname or "risk" in fname:
                    files.append(os.path.join(root, fname))

    return sorted(files)


def process_all_files(
    base_dir: str = FINRL_BASE,
    output_dir: Optional[str] = None,
    output_suffix: str = "_renamed",
    in_place: bool = False,
    dry_run: bool = False,
    save_manifest: bool = True,
) -> List[Dict]:
    """
    Process all scoring files and rename columns.

    Args:
        base_dir: Base directory to search
        output_dir: If provided, create files here preserving directory structure
        output_suffix: Suffix to add to output files (if not output_dir or in_place)
        in_place: If True, overwrite original files
        dry_run: If True, only report what would be done
        save_manifest: If True, save a manifest JSON of all operations

    Returns:
        List of stats dicts for each file
    """
    files = find_scoring_files(base_dir)
    logging.info(f"Found {len(files)} scoring files to process")

    all_stats = []
    skipped_files = []  # Files that don't need renaming

    for fpath in files:
        model = detect_model_from_path(fpath)
        if model is None:
            logging.warning(f"Could not detect model for: {fpath}")
            continue

        # Determine output path
        if in_place:
            output_path = fpath
        elif output_dir:
            # Preserve directory structure relative to base_dir
            rel_path = os.path.relpath(fpath, base_dir)
            output_path = os.path.join(output_dir, rel_path)
        else:
            # Add suffix before .csv
            base, ext = os.path.splitext(fpath)
            output_path = f"{base}{output_suffix}{ext}"

        stats = rename_columns_in_file(fpath, output_path, model, dry_run=dry_run)

        if stats.get("columns_renamed"):
            all_stats.append(stats)
        else:
            skipped_files.append({
                "path": fpath,
                "model": model,
                "reason": "Already has correct column names or no deepseek columns"
            })

    # Save manifest if requested and not dry run
    if save_manifest and output_dir and not dry_run:
        manifest = {
            "timestamp": datetime.now().isoformat(),
            "base_dir": base_dir,
            "output_dir": output_dir,
            "files_processed": len(all_stats),
            "files_skipped": len(skipped_files),
            "column_renames": {
                s["input_path"]: {
                    "output": s["output_path"],
                    "model": s["model"],
                    "renames": s["columns_renamed"],
                    "rows": s["rows"],
                }
                for s in all_stats if s.get("success")
            },
            "skipped_files": skipped_files,
        }
        manifest_path = os.path.join(output_dir, "rename_manifest.json")
        os.makedirs(output_dir, exist_ok=True)
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        logging.info(f"Saved manifest to: {manifest_path}")

    return all_stats, skipped_files


def main():
    parser = argparse.ArgumentParser(
        description="Rename scoring columns to model-specific names",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create renamed files in separate directory (recommended)
  python rename_score_columns.py --output-dir /mnt/md0/finrl/renamed

  # Dry run to preview changes
  python rename_score_columns.py --output-dir /mnt/md0/finrl/renamed --dry-run

  # Add suffix to original filenames
  python rename_score_columns.py --output-suffix _v2

  # Process single file
  python rename_score_columns.py --single-file /path/to/file.csv --model o3
        """
    )
    parser.add_argument(
        "--base-dir", default=FINRL_BASE,
        help=f"Base directory to search (default: {FINRL_BASE})"
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory (preserves structure from base-dir)"
    )
    parser.add_argument(
        "--output-suffix", default="_renamed",
        help="Suffix for output files when --output-dir not used (default: _renamed)"
    )
    parser.add_argument(
        "--in-place", action="store_true",
        help="Overwrite original files (use with caution!)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Only show what would be done, don't write files"
    )
    parser.add_argument(
        "--single-file", type=str, default=None,
        help="Process only a single file"
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Specify model name (auto-detected if not provided)"
    )

    args = parser.parse_args()

    if args.single_file:
        if args.model is None:
            model = detect_model_from_path(args.single_file)
            if model is None:
                parser.error("Could not detect model; please specify --model")
        else:
            model = args.model

        if args.in_place:
            output_path = args.single_file
        elif args.output_dir:
            rel_path = os.path.relpath(args.single_file, args.base_dir)
            output_path = os.path.join(args.output_dir, rel_path)
        else:
            base, ext = os.path.splitext(args.single_file)
            output_path = f"{base}{args.output_suffix}{ext}"

        stats = rename_columns_in_file(
            args.single_file, output_path, model, dry_run=args.dry_run
        )
        print(f"\nResult: {stats}")
    else:
        all_stats, skipped = process_all_files(
            base_dir=args.base_dir,
            output_dir=args.output_dir,
            output_suffix=args.output_suffix,
            in_place=args.in_place,
            dry_run=args.dry_run,
        )

        # Summary
        success = sum(1 for s in all_stats if s.get("success"))
        failed = sum(1 for s in all_stats if not s.get("success"))

        print(f"\n{'='*60}")
        print(f"=== Summary ===")
        print(f"{'='*60}")
        print(f"Files with column renames: {len(all_stats)}")
        print(f"  - Successful: {success}")
        print(f"  - Failed: {failed}")
        print(f"Files skipped (already correct): {len(skipped)}")

        if skipped:
            print(f"\nSkipped files:")
            for s in skipped:
                print(f"  - {s['path'].replace(args.base_dir + '/', '')}")
                print(f"    Reason: {s['reason']}")


if __name__ == "__main__":
    main()