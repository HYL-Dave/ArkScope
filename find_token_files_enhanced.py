#!/usr/bin/env python3
"""
Enhanced Token File Scanner with Model Detection and Service Tier Analysis

Locate CSV files that include token usage information and extract model metadata
from the directory structure. Designed for /mnt/md0/finrl structure where:
- First level directories contain model names (gpt-5, gpt-4.1-mini, o3, etc.)
- CSV files in subdirectories are inference results from those models
- File names may contain service tier hints (flex, standard) and parameters
"""

import argparse
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd

STANDARD_TOKEN_COLUMNS = {"prompt_tokens", "completion_tokens", "total_tokens"}

# Known OpenAI model patterns for directory identification
KNOWN_MODELS = {
    'gpt-5', 'gpt-5-mini', 'gpt-5-nano',
    'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano',
    'gpt-4o', 'gpt-4o-mini',
    'o1', 'o1-pro', 'o1-mini',
    'o3', 'o3-pro', 'o3-mini',
    'o4-mini', 'o4-mini-deep-research'
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enhanced scan for CSV files with token usage, including model detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --root /mnt/md0/finrl
  %(prog)s --root /mnt/md0/finrl --include-model-info --summary-csv enhanced_results.csv
  %(prog)s --root /mnt/md0/finrl --models-only gpt-5 o3
        """
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("/mnt/md0/finrl"),
        help="Directory to scan. Defaults to /mnt/md0/finrl.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("enhanced_token_usage_files.txt"),
        help="Optional path for a human-readable report. Pass '-' to skip writing.",
    )
    parser.add_argument(
        "--summary-csv",
        type=Path,
        default=None,
        help="Optional CSV file recording each match with model and service tier info.",
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=["token"],
        help="Column name fragments that indicate token usage.",
    )
    parser.add_argument(
        "--include-any-token",
        action="store_true",
        help="Include CSVs containing any token-like column instead of requiring standard token columns.",
    )
    parser.add_argument(
        "--include-model-info",
        action="store_true",
        help="Include model identification and service tier detection in output.",
    )
    parser.add_argument(
        "--models-only",
        nargs="*",
        help="Only scan specified models (e.g., gpt-5 o3). If not provided, scan all.",
    )
    parser.add_argument(
        "--show-no-tokens",
        action="store_true",
        help="Also report CSV files that don't contain token columns (for completeness).",
    )
    return parser.parse_args()


def is_model_directory(dir_name: str) -> bool:
    """Check if directory name corresponds to a known model."""
    dir_lower = dir_name.lower()
    return dir_lower in KNOWN_MODELS


def extract_model_info(file_path: Path, root: Path) -> Dict[str, Optional[str]]:
    """
    Extract model information from file path structure.

    Args:
        file_path: Path to the CSV file
        root: Root directory being scanned

    Returns:
        Dictionary with model info: base_model, task_type, service_tier, reasoning_effort, verbosity
    """
    try:
        relative_path = file_path.relative_to(root)
        parts = relative_path.parts

        # Initialize result
        model_info = {
            'base_model': None,
            'task_type': None,
            'service_tier': None,
            'reasoning_effort': None,
            'verbosity': None
        }

        # Extract model from first directory level
        if len(parts) > 0 and is_model_directory(parts[0]):
            model_info['base_model'] = parts[0]

        # Extract task type from directory structure
        if len(parts) > 1:
            for part in parts[1:-1]:  # Exclude filename
                part_lower = part.lower()
                if part_lower in ['risk', 'sentiment', 'summary']:
                    model_info['task_type'] = part_lower
                    break

        # Extract parameters from filename
        filename = file_path.stem.lower()

        # Service tier detection (look for flex/standard keywords)
        if 'flex' in filename:
            model_info['service_tier'] = 'flex'
        elif 'standard' in filename:
            model_info['service_tier'] = 'standard'

        # Reasoning effort detection
        reasoning_patterns = [
            (r'reason[ing]*[_-](\w+)', 'reasoning_effort'),
            (r'r[_-](\w+)[_-]v', 'reasoning_effort'),  # R_high_V pattern
        ]

        for pattern, key in reasoning_patterns:
            match = re.search(pattern, filename)
            if match:
                effort = match.group(1).lower()
                if effort in ['minimal', 'low', 'medium', 'high']:
                    model_info['reasoning_effort'] = effort
                break

        # Verbosity detection
        verbosity_patterns = [
            (r'verbosity[_-](\w+)', 'verbosity'),
            (r'v[_-](\w+)', 'verbosity'),  # V_high pattern
        ]

        for pattern, key in verbosity_patterns:
            match = re.search(pattern, filename)
            if match:
                verb = match.group(1).lower()
                if verb in ['low', 'medium', 'high']:
                    model_info['verbosity'] = verb
                break

        return model_info

    except Exception:
        return {
            'base_model': None,
            'task_type': None,
            'service_tier': None,
            'reasoning_effort': None,
            'verbosity': None
        }


def iter_csv_files(root: Path, models_filter: Optional[List[str]] = None) -> Iterable[Path]:
    """Iterate over CSV files, optionally filtering by model directories."""
    if models_filter:
        # Only scan specified model directories
        for model in models_filter:
            model_dir = root / model
            if model_dir.exists() and model_dir.is_dir():
                for csv_path in model_dir.rglob("*.csv"):
                    if csv_path.is_file():
                        yield csv_path
    else:
        # Scan all CSV files
        for csv_path in root.rglob("*.csv"):
            if csv_path.is_file():
                yield csv_path


def read_header(file_path: Path) -> List[str]:
    """Read CSV header safely."""
    try:
        frame = pd.read_csv(file_path, nrows=0, engine="c")
        return frame.columns.tolist()
    except Exception:
        return []


def detect_token_columns(
    columns: Sequence[str],
    keywords: Sequence[str],
    require_standard: bool,
) -> List[str]:
    """Detect token-related columns in CSV headers."""
    lowered_keywords = [kw.lower() for kw in keywords]
    token_columns = [
        column
        for column in columns
        if any(keyword in column.lower() for keyword in lowered_keywords)
    ]

    if require_standard and not any(
        column.lower() in STANDARD_TOKEN_COLUMNS for column in token_columns
    ):
        return []

    return token_columns


def write_enhanced_text_report(
    output_path: Path,
    root: Path,
    total_csv: int,
    token_files: List[Dict],
    no_token_files: List[Dict],
    include_model_info: bool,
    show_no_tokens: bool,
) -> None:
    """Write enhanced human-readable report with model information."""
    coverage = (len(token_files) / total_csv * 100) if total_csv else 0.0

    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("Enhanced CSV Token Usage Report\n")
        handle.write("=" * 50 + "\n\n")
        handle.write(f"Root directory: {root}\n")
        handle.write(f"Total CSV files scanned: {total_csv:,}\n")
        handle.write(f"Files with token columns: {len(token_files):,}\n")
        handle.write(f"Coverage: {coverage:.2f}%\n\n")

        if not token_files:
            handle.write("No CSV files containing token columns were found.\n")
            return

        # Group by model for organized display
        by_model = {}
        for info in token_files:
            model = info.get('base_model', 'unknown')
            if model not in by_model:
                by_model[model] = []
            by_model[model].append(info)

        handle.write("FILES WITH TOKEN USAGE:\n")
        handle.write("-" * 30 + "\n\n")

        for model, files in sorted(by_model.items()):
            handle.write(f"🤖 Model: {model.upper()}\n")
            handle.write(f"   Files: {len(files)}\n\n")

            for info in files:
                handle.write(f"  📄 {info['relative_path']}\n")
                handle.write(f"     Token columns: {', '.join(info['token_columns'])}\n")

                if include_model_info:
                    if info.get('task_type'):
                        handle.write(f"     Task: {info['task_type']}\n")
                    if info.get('service_tier'):
                        handle.write(f"     Service tier: {info['service_tier']}\n")
                    if info.get('reasoning_effort'):
                        handle.write(f"     Reasoning: {info['reasoning_effort']}\n")
                    if info.get('verbosity'):
                        handle.write(f"     Verbosity: {info['verbosity']}\n")

                handle.write("\n")

        # Summary by model
        handle.write("\nSUMMARY BY MODEL:\n")
        handle.write("-" * 20 + "\n")
        for model, files in sorted(by_model.items()):
            handle.write(f"{model}: {len(files)} files\n")

        # Show files without tokens if requested
        if show_no_tokens and no_token_files:
            handle.write(f"\n\nFILES WITHOUT TOKEN COLUMNS ({len(no_token_files)}):\n")
            handle.write("-" * 40 + "\n")
            for info in no_token_files[:20]:  # Limit to first 20
                handle.write(f"  {info['relative_path']}\n")
            if len(no_token_files) > 20:
                handle.write(f"  ... and {len(no_token_files) - 20} more\n")


def write_enhanced_csv_summary(csv_path: Path, token_files: List[Dict]) -> None:
    """Write enhanced CSV summary with model information."""
    import csv

    fieldnames = [
        "file_path", "relative_path", "token_columns",
        "base_model", "task_type", "service_tier",
        "reasoning_effort", "verbosity"
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for info in token_files:
            writer.writerow({
                "file_path": str(info["file_path"]),
                "relative_path": str(info["relative_path"]),
                "token_columns": ";".join(info["token_columns"]),
                "base_model": info.get("base_model", ""),
                "task_type": info.get("task_type", ""),
                "service_tier": info.get("service_tier", ""),
                "reasoning_effort": info.get("reasoning_effort", ""),
                "verbosity": info.get("verbosity", ""),
            })


def main() -> None:
    args = parse_args()
    root = args.root.expanduser()

    if not root.exists():
        raise SystemExit(f"Root directory not found: {root}")

    require_standard = not args.include_any_token

    total_csv = 0
    token_files = []
    no_token_files = []
    errors = []

    print(f"🔍 Scanning {root} for CSV files with token usage...")
    if args.models_only:
        print(f"   Filtering models: {', '.join(args.models_only)}")

    for csv_file in iter_csv_files(root, args.models_only):
        total_csv += 1

        if total_csv % 1000 == 0:
            print(f"   Processed {total_csv:,} files...")

        try:
            columns = read_header(csv_file)
        except Exception as exc:
            errors.append((csv_file, str(exc)))
            continue

        token_columns = detect_token_columns(columns, args.keywords, require_standard)

        # Extract model information
        model_info = extract_model_info(csv_file, root) if args.include_model_info else {}

        file_info = {
            "file_path": csv_file,
            "relative_path": csv_file.relative_to(root),
            "token_columns": token_columns,
            **model_info
        }

        if token_columns:
            token_files.append(file_info)
        elif args.show_no_tokens:
            no_token_files.append(file_info)

    # Sort results
    token_files.sort(key=lambda item: (
        item.get('base_model', ''),
        str(item["relative_path"])
    ))

    coverage = (len(token_files) / total_csv * 100) if total_csv else 0.0

    print(f"\n📊 Scan complete!")
    print(f"CSV files scanned: {total_csv:,}")
    print(f"Files with token columns: {len(token_files):,}")
    print(f"Coverage: {coverage:.2f}%")

    if token_files:
        print(f"\n🤖 Models found:")
        model_counts = {}
        for info in token_files:
            model = info.get('base_model', 'unknown')
            model_counts[model] = model_counts.get(model, 0) + 1

        for model, count in sorted(model_counts.items()):
            print(f"  {model}: {count} files")

        print(f"\n📋 Sample files:")
        for info in token_files[:10]:
            model = info.get('base_model', 'unknown')
            columns = ", ".join(info["token_columns"])
            tier = f" ({info['service_tier']})" if info.get('service_tier') else ""
            print(f"  [{model}]{tier} {info['relative_path']} -> {columns}")

        if len(token_files) > 10:
            print(f"  ... and {len(token_files) - 10} more")
    else:
        print("No CSV files containing the requested token columns were found.")

    # Write reports
    if args.output != Path("-"):
        write_enhanced_text_report(
            args.output, root, total_csv, token_files, no_token_files,
            args.include_model_info, args.show_no_tokens
        )
        print(f"\n💾 Report written to: {args.output}")

    if token_files and args.summary_csv:
        write_enhanced_csv_summary(args.summary_csv, token_files)
        print(f"📊 CSV summary written to: {args.summary_csv}")

    if errors:
        print(f"\n⚠️  Warnings: {len(errors)} files could not be processed.")
        for path, message in errors[:5]:
            print(f"  {path}: {message}")


if __name__ == "__main__":
    main()