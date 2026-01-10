#!/usr/bin/env python3
"""
Full analysis of Risk/Sentiment scores across /mnt/md0/finrl dataset.
Memory-efficient implementation that only loads score columns.

Usage:
    python scripts/analysis/analyze_finrl_scores_full.py --task both
"""

import os
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import json
from collections import defaultdict

FINRL_BASE = Path("/mnt/md0/finrl")


@dataclass
class ScoredFile:
    """Metadata for a scored file."""
    path: Path
    task: str
    model: str
    reasoning: Optional[str]
    input_source: str
    summary_reasoning: Optional[str] = None
    summary_verbosity: Optional[str] = None

    @property
    def short_label(self) -> str:
        """Short label for tables."""
        parts = [self.model]
        if self.reasoning:
            parts.append(self.reasoning)
        return "_".join(parts)

    @property
    def full_label(self) -> str:
        """Full descriptive label."""
        parts = [self.model]
        if self.reasoning:
            parts.append(f"R={self.reasoning}")
        parts.append(f"in={self.input_source}")
        if self.summary_reasoning and self.input_source == "gpt_5_summary":
            parts.append(f"sumR={self.summary_reasoning}")
            parts.append(f"sumV={self.summary_verbosity}")
        return " | ".join(parts)


def discover_files(task: str) -> List[ScoredFile]:
    """Discover all scored files for a task."""
    files = []

    # Model directories to scan
    model_dirs = [
        ("o3", "o3"),
        ("o4-mini", "o4-mini"),
        ("gpt-4.1", "gpt-4.1"),
        ("gpt-4.1-mini", "gpt-4.1-mini"),
        ("gpt-4.1-nano", "gpt-4.1-nano"),
        ("gpt-5", "gpt-5"),
        ("gpt-5-mini", "gpt-5-mini"),
    ]

    for model, dirname in model_dirs:
        task_dir = FINRL_BASE / dirname / task
        if not task_dir.exists():
            continue

        for csv_path in task_dir.glob("*.csv"):
            sf = parse_file(csv_path, task, model)
            if sf:
                files.append(sf)

    # Claude files
    claude_dir = FINRL_BASE / "claude" / task
    if claude_dir.exists():
        for csv_path in claude_dir.glob("*.csv"):
            for model_name in ["haiku", "sonnet", "opus"]:
                if model_name in csv_path.name:
                    files.append(ScoredFile(
                        path=csv_path,
                        task=task,
                        model=f"claude-{model_name}",
                        reasoning=None,
                        input_source="gpt_5_summary",
                        summary_reasoning="high",
                        summary_verbosity="high"
                    ))
                    break

    return files


def parse_file(path: Path, task: str, model: str) -> Optional[ScoredFile]:
    """Parse filename to extract configuration."""
    fname = path.name

    # Early numbered experiments (Lsa_summary)
    if "_high_1" in fname or "_high_4" in fname:
        return ScoredFile(path=path, task=task, model=model, reasoning="high",
                         input_source="Lsa_summary")
    if "_medium_2" in fname:
        return ScoredFile(path=path, task=task, model=model, reasoning="medium",
                         input_source="Lsa_summary")

    # *_by_o3_summary.csv
    if "_by_o3_summary" in fname:
        reasoning = None
        for r in ["minimal", "low", "medium", "high"]:
            if f"_{r}_by" in fname:
                reasoning = r
                break
        return ScoredFile(path=path, task=task, model=model, reasoning=reasoning,
                         input_source="o3_summary")

    # *_by_gpt-5_* or *_by_gpt5_*
    if "_by_gpt-5_" in fname or "_by_gpt5_" in fname:
        import re
        sum_r = re.search(r"reason[_-](\w+)", fname)
        sum_v = re.search(r"verbosity[_-](\w+)", fname)
        sum_reasoning = sum_r.group(1) if sum_r else "high"
        sum_verbosity = sum_v.group(1) if sum_v else "high"

        # R_*_V_* pattern for scoring reasoning
        scoring_r = re.search(r"_R_(\w+)_V_", fname)
        reasoning = scoring_r.group(1) if scoring_r else None

        return ScoredFile(path=path, task=task, model=model, reasoning=reasoning,
                         input_source="gpt_5_summary", summary_reasoning=sum_reasoning,
                         summary_verbosity=sum_verbosity)

    return None


def load_score_column(file: ScoredFile) -> pd.Series:
    """Load only the score column from a file."""
    score_col = f"{file.task}_claude" if "claude" in file.model else f"{file.task}_deepseek"

    try:
        df = pd.read_csv(file.path, usecols=[score_col], low_memory=True)
        return df[score_col].dropna().astype(int)
    except Exception as e:
        print(f"  Error loading {file.path.name}: {e}")
        return pd.Series(dtype=int)


def compute_stats(scores: pd.Series) -> Dict:
    """Compute statistics for a score series."""
    if len(scores) == 0:
        return {}

    vc = scores.value_counts().sort_index()
    dist = {int(k): int(v) for k, v in vc.items()}
    total = len(scores)

    return {
        "n": total,
        "mean": round(float(scores.mean()), 3),
        "std": round(float(scores.std()), 3),
        "median": float(scores.median()),
        "dist": dist,
        "dist_pct": {k: round(v/total*100, 1) for k, v in dist.items()}
    }


def run_analysis(task: str) -> Dict:
    """Run full analysis for a task."""
    print(f"\n{'='*70}")
    print(f"  FULL ANALYSIS: {task.upper()}")
    print(f"{'='*70}")

    files = discover_files(task)
    print(f"\nDiscovered {len(files)} scored files\n")

    results = {
        "task": task,
        "n_files": len(files),
        "per_file": {},
        "by_model": defaultdict(list),
        "by_reasoning": defaultdict(list),
        "by_input_source": defaultdict(list),
    }

    # Load and analyze each file
    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}] Loading {f.path.name}...", end=" ", flush=True)
        scores = load_score_column(f)

        if len(scores) == 0:
            print("EMPTY")
            continue

        stats = compute_stats(scores)
        results["per_file"][f.full_label] = stats
        print(f"n={stats['n']:,}, mean={stats['mean']:.3f}, std={stats['std']:.3f}")

        # Aggregate by factors
        results["by_model"][f.model].append(scores)
        results["by_reasoning"][f.reasoning or "default"].append(scores)
        results["by_input_source"][f.input_source].append(scores)

    # Compute aggregated statistics
    print("\n--- Aggregated by Model ---")
    results["model_stats"] = {}
    for model, score_lists in sorted(results["by_model"].items()):
        combined = pd.concat(score_lists, ignore_index=True)
        stats = compute_stats(combined)
        results["model_stats"][model] = stats
        print(f"  {model:15s}: n={stats['n']:>10,}, mean={stats['mean']:.3f}, std={stats['std']:.3f}")

    print("\n--- Aggregated by Reasoning Level ---")
    results["reasoning_stats"] = {}
    for r, score_lists in sorted(results["by_reasoning"].items()):
        combined = pd.concat(score_lists, ignore_index=True)
        stats = compute_stats(combined)
        results["reasoning_stats"][r] = stats
        print(f"  {r:15s}: n={stats['n']:>10,}, mean={stats['mean']:.3f}, std={stats['std']:.3f}")

    print("\n--- Aggregated by Input Source ---")
    results["input_source_stats"] = {}
    for src, score_lists in sorted(results["by_input_source"].items()):
        combined = pd.concat(score_lists, ignore_index=True)
        stats = compute_stats(combined)
        results["input_source_stats"][src] = stats
        print(f"  {src:15s}: n={stats['n']:>10,}, mean={stats['mean']:.3f}, std={stats['std']:.3f}")

    # Clean up for JSON serialization
    del results["by_model"]
    del results["by_reasoning"]
    del results["by_input_source"]

    return results


def generate_markdown(sent_res: Dict, risk_res: Dict) -> str:
    """Generate markdown report."""
    md = []

    md.append("### 10.9 FinRL 跨模型評分比較分析\n")
    md.append("使用 `/mnt/md0/finrl` 數據集（約 209 萬筆新聞）進行完整分析。\n")

    md.append("#### 實驗設計\n")
    md.append("- **數據源**: HuggingFace FinRL DeepSeek dataset\n")
    md.append("- **評分模型**: o3, o4-mini, gpt-4.1系列, gpt-5系列, Claude系列\n")
    md.append("- **輸入源**: Lsa_summary (原版), o3_summary, gpt_5_summary\n")
    md.append("- **Reasoning levels**: minimal, low, medium, high\n\n")

    # Sentiment results
    md.append("#### Sentiment 評分結果\n\n")

    md.append("**按模型分組:**\n\n")
    md.append("| Model | N | Mean | Std | 1分% | 2分% | 3分% | 4分% | 5分% |\n")
    md.append("|-------|---|------|-----|------|------|------|------|------|\n")
    for model, stats in sorted(sent_res.get("model_stats", {}).items()):
        dist = stats.get("dist_pct", {})
        md.append(f"| {model} | {stats['n']:,} | {stats['mean']:.3f} | {stats['std']:.3f} | "
                 f"{dist.get(1, 0):.1f} | {dist.get(2, 0):.1f} | {dist.get(3, 0):.1f} | "
                 f"{dist.get(4, 0):.1f} | {dist.get(5, 0):.1f} |\n")

    md.append("\n**按 Reasoning Level 分組:**\n\n")
    md.append("| Reasoning | N | Mean | Std |\n")
    md.append("|-----------|---|------|-----|\n")
    for r, stats in sorted(sent_res.get("reasoning_stats", {}).items()):
        md.append(f"| {r} | {stats['n']:,} | {stats['mean']:.3f} | {stats['std']:.3f} |\n")

    md.append("\n**按輸入源分組:**\n\n")
    md.append("| Input Source | N | Mean | Std |\n")
    md.append("|--------------|---|------|-----|\n")
    for src, stats in sorted(sent_res.get("input_source_stats", {}).items()):
        md.append(f"| {src} | {stats['n']:,} | {stats['mean']:.3f} | {stats['std']:.3f} |\n")

    # Risk results
    md.append("\n#### Risk 評分結果\n\n")

    md.append("**按模型分組:**\n\n")
    md.append("| Model | N | Mean | Std | 1分% | 2分% | 3分% | 4分% | 5分% |\n")
    md.append("|-------|---|------|-----|------|------|------|------|------|\n")
    for model, stats in sorted(risk_res.get("model_stats", {}).items()):
        dist = stats.get("dist_pct", {})
        md.append(f"| {model} | {stats['n']:,} | {stats['mean']:.3f} | {stats['std']:.3f} | "
                 f"{dist.get(1, 0):.1f} | {dist.get(2, 0):.1f} | {dist.get(3, 0):.1f} | "
                 f"{dist.get(4, 0):.1f} | {dist.get(5, 0):.1f} |\n")

    md.append("\n**按 Reasoning Level 分組:**\n\n")
    md.append("| Reasoning | N | Mean | Std |\n")
    md.append("|-----------|---|------|-----|\n")
    for r, stats in sorted(risk_res.get("reasoning_stats", {}).items()):
        md.append(f"| {r} | {stats['n']:,} | {stats['mean']:.3f} | {stats['std']:.3f} |\n")

    md.append("\n**按輸入源分組:**\n\n")
    md.append("| Input Source | N | Mean | Std |\n")
    md.append("|--------------|---|------|-----|\n")
    for src, stats in sorted(risk_res.get("input_source_stats", {}).items()):
        md.append(f"| {src} | {stats['n']:,} | {stats['mean']:.3f} | {stats['std']:.3f} |\n")

    # Key findings
    md.append("\n#### 關鍵發現\n\n")
    md.append("**Sentiment 評分趨勢:**\n")
    md.append("1. TBD based on results\n\n")
    md.append("**Risk 評分趨勢:**\n")
    md.append("1. TBD based on results\n\n")

    md.append("---\n")
    md.append("*分析日期: 2025-12-27*\n")

    return "".join(md)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["sentiment", "risk", "both"], default="both")
    parser.add_argument("--output", default="results/finrl_full_analysis")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    sent_res = None
    risk_res = None

    if args.task in ["sentiment", "both"]:
        sent_res = run_analysis("sentiment")
        with open(f"{args.output}/sentiment_results.json", "w") as f:
            json.dump(sent_res, f, indent=2, default=str)

    if args.task in ["risk", "both"]:
        risk_res = run_analysis("risk")
        with open(f"{args.output}/risk_results.json", "w") as f:
            json.dump(risk_res, f, indent=2, default=str)

    if sent_res and risk_res:
        md = generate_markdown(sent_res, risk_res)
        with open(f"{args.output}/analysis_report.md", "w") as f:
            f.write(md)
        print(f"\n{'='*70}")
        print("  MARKDOWN REPORT")
        print(f"{'='*70}")
        print(md)

    print(f"\nResults saved to {args.output}/")


if __name__ == "__main__":
    main()