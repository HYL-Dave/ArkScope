#!/usr/bin/env python3
"""
Detailed factor comparison analysis with controlled variables.
V2: Includes full distribution comparisons (1-5 score percentages).
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass

RESULTS_DIR = Path("results/finrl_full_analysis")


@dataclass
class Config:
    """Parsed configuration from file label."""
    model: str
    reasoning: str
    input_source: str
    sum_reasoning: str = None
    sum_verbosity: str = None

    @property
    def key(self) -> str:
        return f"{self.model}|{self.reasoning}|{self.input_source}"


def parse_label(label: str) -> Config:
    """Parse configuration from file label."""
    parts = label.split(" | ")
    model = parts[0]
    reasoning = "none"
    input_source = "unknown"
    sum_reasoning = None
    sum_verbosity = None

    for part in parts[1:]:
        if part.startswith("R="):
            reasoning = part.split("=")[1]
        elif part.startswith("in="):
            input_source = part.split("=")[1]
        elif part.startswith("sumR="):
            sum_reasoning = part.split("=")[1]
        elif part.startswith("sumV="):
            sum_verbosity = part.split("=")[1]

    return Config(model, reasoning, input_source, sum_reasoning, sum_verbosity)


def load_results(task: str) -> Dict:
    with open(RESULTS_DIR / f"{task}_results.json") as f:
        return json.load(f)


def format_dist(stats: Dict) -> str:
    """Format distribution as compact string."""
    dist = stats.get("dist_pct", {})
    return f"{dist.get('1', 0):.1f}/{dist.get('2', 0):.1f}/{dist.get('3', 0):.1f}/{dist.get('4', 0):.1f}/{dist.get('5', 0):.1f}"


def format_diff(val1: float, val2: float) -> str:
    diff = val2 - val1
    if diff > 0:
        return f"+{diff:.3f}"
    return f"{diff:.3f}"


def reasoning_comparison_with_dist(data: Dict, task: str) -> List[str]:
    """Compare reasoning levels with full distribution."""
    lines = []
    lines.append(f"\n## Reasoning Level 效果詳細分析 ({task.upper()})")
    lines.append("\n控制條件: 相同模型 + 相同輸入源")
    lines.append("\n分佈格式: 1分%/2分%/3分%/4分%/5分%\n")

    per_file = data["per_file"]

    # Group by model and input_source
    groups = {}
    for label, stats in per_file.items():
        cfg = parse_label(label)
        key = (cfg.model, cfg.input_source)
        if key not in groups:
            groups[key] = {}
        groups[key][cfg.reasoning] = stats

    # Find groups with multiple reasoning levels
    for (model, input_src), reasoning_stats in sorted(groups.items()):
        if len(reasoning_stats) <= 1:
            continue
        if "none" in reasoning_stats and len(reasoning_stats) == 1:
            continue

        # Only show if meaningful comparison exists
        levels = [r for r in reasoning_stats.keys() if r != "none"]
        if len(levels) < 2:
            continue

        lines.append(f"### {model} + {input_src}\n")
        lines.append("| Reasoning | Mean | Std | 分佈 (1/2/3/4/5%) | Δ Mean |")
        lines.append("|-----------|------|-----|------------------|--------|")

        order = ["minimal", "low", "medium", "high", "none"]
        sorted_levels = sorted(reasoning_stats.keys(), key=lambda x: order.index(x) if x in order else 99)

        baseline = reasoning_stats.get("high", reasoning_stats.get(sorted_levels[-1], {}))
        baseline_mean = baseline.get("mean", 0)

        for level in sorted_levels:
            stats = reasoning_stats[level]
            diff = format_diff(baseline_mean, stats["mean"]) if level != "high" else "-"
            dist_str = format_dist(stats)
            lines.append(f"| {level} | {stats['mean']:.3f} | {stats['std']:.3f} | {dist_str} | {diff} |")

        # Add distribution shift analysis
        if len(sorted_levels) >= 2:
            first = reasoning_stats.get(sorted_levels[0], {})
            last = reasoning_stats.get(sorted_levels[-1], {})
            first_dist = first.get("dist_pct", {})
            last_dist = last.get("dist_pct", {})

            lines.append("")
            lines.append(f"**分佈變化 ({sorted_levels[0]} → {sorted_levels[-1]}):**")

            shifts = []
            for score in [1, 2, 3, 4, 5]:
                d1 = first_dist.get(str(score), first_dist.get(score, 0))
                d2 = last_dist.get(str(score), last_dist.get(score, 0))
                diff = d2 - d1
                if abs(diff) >= 1.0:  # Only report significant shifts
                    direction = "↑" if diff > 0 else "↓"
                    shifts.append(f"{score}分 {direction}{abs(diff):.1f}%")

            if shifts:
                lines.append(f"- {', '.join(shifts)}")
            else:
                lines.append("- 分佈變化不顯著 (<1%)")

        lines.append("")

    return lines


def model_comparison_with_dist(data: Dict, task: str) -> List[str]:
    """Compare models with full distribution."""
    lines = []
    lines.append(f"\n## 模型差異詳細分析 ({task.upper()})")
    lines.append("\n控制條件: 相同輸入源 (o3_summary)")
    lines.append("\n分佈格式: 1分%/2分%/3分%/4分%/5分%\n")

    per_file = data["per_file"]

    # Collect models on o3_summary
    models_data = {}
    for label, stats in per_file.items():
        if "o3_summary" not in label:
            continue
        cfg = parse_label(label)
        key = f"{cfg.model}" if cfg.reasoning == "none" else f"{cfg.model} (R={cfg.reasoning})"
        models_data[key] = stats

    if not models_data:
        return lines

    lines.append("| Model | Mean | Std | 分佈 (1/2/3/4/5%) |")
    lines.append("|-------|------|-----|------------------|")

    # Sort by mean
    sorted_models = sorted(models_data.items(), key=lambda x: x[1]["mean"])

    for model, stats in sorted_models:
        dist_str = format_dist(stats)
        lines.append(f"| {model} | {stats['mean']:.3f} | {stats['std']:.3f} | {dist_str} |")

    # Add distribution analysis
    lines.append("")
    lines.append("**分佈特徵分析:**")

    # Find extremes
    min_model, min_stats = sorted_models[0]
    max_model, max_stats = sorted_models[-1]

    min_dist = min_stats.get("dist_pct", {})
    max_dist = max_stats.get("dist_pct", {})

    lines.append(f"\n最低均值 ({min_model}):")
    for score in [1, 2, 3, 4, 5]:
        pct = min_dist.get(str(score), min_dist.get(score, 0))
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"  {score}分: {bar} {pct:.1f}%")

    lines.append(f"\n最高均值 ({max_model}):")
    for score in [1, 2, 3, 4, 5]:
        pct = max_dist.get(str(score), max_dist.get(score, 0))
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"  {score}分: {bar} {pct:.1f}%")

    lines.append("")
    return lines


def input_source_comparison_with_dist(data: Dict, task: str) -> List[str]:
    """Compare input sources with full distribution."""
    lines = []
    lines.append(f"\n## 輸入源效果詳細分析 ({task.upper()})")
    lines.append("\n控制條件: 相同模型 + 相同 reasoning")
    lines.append("\n分佈格式: 1分%/2分%/3分%/4分%/5分%\n")

    per_file = data["per_file"]

    # Group by model and reasoning
    groups = {}
    for label, stats in per_file.items():
        cfg = parse_label(label)
        key = (cfg.model, cfg.reasoning)
        if key not in groups:
            groups[key] = {}
        src = cfg.input_source.split("_verbosity")[0] if "_verbosity" in cfg.input_source else cfg.input_source
        if src not in groups[key]:
            groups[key][src] = stats

    for (model, reasoning), src_stats in sorted(groups.items()):
        if len(src_stats) <= 1:
            continue

        r_str = f"R={reasoning}" if reasoning != "none" else "no reasoning"
        lines.append(f"### {model} ({r_str})\n")
        lines.append("| Input Source | Mean | Std | 分佈 (1/2/3/4/5%) | Δ Mean |")
        lines.append("|--------------|------|-----|------------------|--------|")

        lsa_stats = src_stats.get("Lsa_summary", {})
        lsa_mean = lsa_stats.get("mean", None)

        for src, stats in sorted(src_stats.items()):
            diff = ""
            if lsa_mean is not None and src != "Lsa_summary":
                diff = format_diff(lsa_mean, stats["mean"])
            dist_str = format_dist(stats)
            lines.append(f"| {src} | {stats['mean']:.3f} | {stats['std']:.3f} | {dist_str} | {diff} |")

        # Distribution shift analysis
        if len(src_stats) >= 2:
            sources = list(src_stats.keys())
            first_stats = src_stats[sources[0]]
            last_stats = src_stats[sources[-1]]

            first_dist = first_stats.get("dist_pct", {})
            last_dist = last_stats.get("dist_pct", {})

            max_shift = 0
            for score in [1, 2, 3, 4, 5]:
                d1 = first_dist.get(str(score), first_dist.get(score, 0))
                d2 = last_dist.get(str(score), last_dist.get(score, 0))
                max_shift = max(max_shift, abs(d2 - d1))

            if max_shift < 2.0:
                lines.append(f"\n*分佈差異極小 (最大差距 {max_shift:.1f}%)，輸入源對此配置無顯著影響*")

        lines.append("")

    return lines


def cross_task_comparison(sent_data: Dict, risk_data: Dict) -> List[str]:
    """Compare sentiment and risk distributions for same configurations."""
    lines = []
    lines.append("\n## Sentiment vs Risk 分佈對比")
    lines.append("\n展示相同配置下，Sentiment 和 Risk 的分佈差異\n")

    # Find common configurations
    sent_files = sent_data["per_file"]
    risk_files = risk_data["per_file"]

    # Match by similar labels
    matches = []
    for s_label, s_stats in sent_files.items():
        s_cfg = parse_label(s_label)
        for r_label, r_stats in risk_files.items():
            r_cfg = parse_label(r_label)
            if s_cfg.model == r_cfg.model and s_cfg.reasoning == r_cfg.reasoning:
                if s_cfg.input_source == r_cfg.input_source or \
                   (s_cfg.input_source.startswith("o3_summary") and r_cfg.input_source.startswith("o3_summary")):
                    matches.append((s_label, s_stats, r_stats))
                    break

    # Show a few representative examples
    shown = set()
    lines.append("### 代表性配置對比\n")

    for s_label, s_stats, r_stats in matches[:10]:
        cfg = parse_label(s_label)
        key = f"{cfg.model}_{cfg.reasoning}"
        if key in shown:
            continue
        shown.add(key)

        lines.append(f"**{cfg.model} (R={cfg.reasoning}):**")
        lines.append("```")

        s_dist = s_stats.get("dist_pct", {})
        r_dist = r_stats.get("dist_pct", {})

        lines.append(f"         1分    2分    3分    4分    5分   Mean")
        lines.append(f"Sent:  {s_dist.get('1', s_dist.get(1, 0)):5.1f}  {s_dist.get('2', s_dist.get(2, 0)):5.1f}  {s_dist.get('3', s_dist.get(3, 0)):5.1f}  {s_dist.get('4', s_dist.get(4, 0)):5.1f}  {s_dist.get('5', s_dist.get(5, 0)):5.1f}  {s_stats['mean']:.3f}")
        lines.append(f"Risk:  {r_dist.get('1', r_dist.get(1, 0)):5.1f}  {r_dist.get('2', r_dist.get(2, 0)):5.1f}  {r_dist.get('3', r_dist.get(3, 0)):5.1f}  {r_dist.get('4', r_dist.get(4, 0)):5.1f}  {r_dist.get('5', r_dist.get(5, 0)):5.1f}  {r_stats['mean']:.3f}")
        lines.append("```")
        lines.append("")

    return lines


def generate_summary_with_dist(sent_data: Dict, risk_data: Dict) -> List[str]:
    """Generate summary with distribution insights."""
    lines = []
    lines.append("\n## 關鍵發現摘要 (含分佈分析)\n")

    # GPT-5 reasoning effect
    lines.append("### 1. GPT-5 Reasoning Level 效果\n")
    lines.append("控制條件: model=gpt-5, input=o3_summary\n")

    gpt5_sent = {}
    gpt5_risk = {}
    for label, stats in sent_data["per_file"].items():
        if "gpt-5 |" in label and "o3_summary" in label:
            cfg = parse_label(label)
            if cfg.reasoning != "none":
                gpt5_sent[cfg.reasoning] = stats
    for label, stats in risk_data["per_file"].items():
        if "gpt-5 |" in label and "o3_summary" in label:
            cfg = parse_label(label)
            if cfg.reasoning != "none":
                gpt5_risk[cfg.reasoning] = stats

    if gpt5_sent:
        lines.append("**Sentiment 分佈:**")
        lines.append("```")
        lines.append("Reasoning   1分%   2分%   3分%   4分%   5分%   Mean")
        lines.append("-" * 60)
        for r in ["minimal", "low", "medium", "high"]:
            if r in gpt5_sent:
                s = gpt5_sent[r]
                d = s.get("dist_pct", {})
                lines.append(f"{r:10s}  {d.get('1', d.get(1, 0)):5.1f}  {d.get('2', d.get(2, 0)):5.1f}  {d.get('3', d.get(3, 0)):5.1f}  {d.get('4', d.get(4, 0)):5.1f}  {d.get('5', d.get(5, 0)):5.1f}  {s['mean']:.3f}")
        lines.append("```")

        # Analyze shift
        if "minimal" in gpt5_sent and "high" in gpt5_sent:
            min_d = gpt5_sent["minimal"].get("dist_pct", {})
            high_d = gpt5_sent["high"].get("dist_pct", {})

            lines.append("\n**分佈轉移 (minimal → high):**")
            for score in [1, 2, 3, 4, 5]:
                d_min = min_d.get(str(score), min_d.get(score, 0))
                d_high = high_d.get(str(score), high_d.get(score, 0))
                diff = d_high - d_min
                if abs(diff) >= 0.5:
                    direction = "↑" if diff > 0 else "↓"
                    lines.append(f"- {score}分: {d_min:.1f}% → {d_high:.1f}% ({direction}{abs(diff):.1f}%)")

    if gpt5_risk:
        lines.append("\n**Risk 分佈:**")
        lines.append("```")
        lines.append("Reasoning   1分%   2分%   3分%   4分%   5分%   Mean")
        lines.append("-" * 60)
        for r in ["minimal", "low", "medium", "high"]:
            if r in gpt5_risk:
                s = gpt5_risk[r]
                d = s.get("dist_pct", {})
                lines.append(f"{r:10s}  {d.get('1', d.get(1, 0)):5.1f}  {d.get('2', d.get(2, 0)):5.1f}  {d.get('3', d.get(3, 0)):5.1f}  {d.get('4', d.get(4, 0)):5.1f}  {d.get('5', d.get(5, 0)):5.1f}  {s['mean']:.3f}")
        lines.append("```")

    # Model comparison
    lines.append("\n### 2. 模型間分佈差異\n")
    lines.append("控制條件: input=o3_summary, 選擇代表性配置\n")

    # Find extreme models
    models_sent = {}
    models_risk = {}
    for label, stats in sent_data["per_file"].items():
        if "o3_summary" in label:
            cfg = parse_label(label)
            key = f"{cfg.model}_{cfg.reasoning}"
            models_sent[key] = stats
    for label, stats in risk_data["per_file"].items():
        if "o3_summary" in label:
            cfg = parse_label(label)
            key = f"{cfg.model}_{cfg.reasoning}"
            models_risk[key] = stats

    if models_sent:
        sorted_sent = sorted(models_sent.items(), key=lambda x: x[1]["mean"])
        min_m, min_s = sorted_sent[0]
        max_m, max_s = sorted_sent[-1]

        lines.append("**Sentiment 極端模型比較:**")
        lines.append(f"\n{min_m} (均值最低 {min_s['mean']:.3f}):")
        d = min_s.get("dist_pct", {})
        lines.append(f"  1分: {'█' * int(d.get('1', d.get(1, 0)) / 2)}{'░' * (25 - int(d.get('1', d.get(1, 0)) / 2))} {d.get('1', d.get(1, 0)):.1f}%")
        lines.append(f"  3分: {'█' * int(d.get('3', d.get(3, 0)) / 2)}{'░' * (25 - int(d.get('3', d.get(3, 0)) / 2))} {d.get('3', d.get(3, 0)):.1f}%")
        lines.append(f"  5分: {'█' * int(d.get('5', d.get(5, 0)) / 2)}{'░' * (25 - int(d.get('5', d.get(5, 0)) / 2))} {d.get('5', d.get(5, 0)):.1f}%")

        lines.append(f"\n{max_m} (均值最高 {max_s['mean']:.3f}):")
        d = max_s.get("dist_pct", {})
        lines.append(f"  1分: {'█' * int(d.get('1', d.get(1, 0)) / 2)}{'░' * (25 - int(d.get('1', d.get(1, 0)) / 2))} {d.get('1', d.get(1, 0)):.1f}%")
        lines.append(f"  3分: {'█' * int(d.get('3', d.get(3, 0)) / 2)}{'░' * (25 - int(d.get('3', d.get(3, 0)) / 2))} {d.get('3', d.get(3, 0)):.1f}%")
        lines.append(f"  5分: {'█' * int(d.get('5', d.get(5, 0)) / 2)}{'░' * (25 - int(d.get('5', d.get(5, 0)) / 2))} {d.get('5', d.get(5, 0)):.1f}%")

    if models_risk:
        sorted_risk = sorted(models_risk.items(), key=lambda x: x[1]["mean"])
        min_m, min_s = sorted_risk[0]
        max_m, max_s = sorted_risk[-1]

        lines.append("\n**Risk 極端模型比較:**")
        lines.append(f"\n{min_m} (均值最低 {min_s['mean']:.3f}):")
        d = min_s.get("dist_pct", {})
        lines.append(f"  1分: {'█' * int(d.get('1', d.get(1, 0)) / 2)}{'░' * (25 - int(d.get('1', d.get(1, 0)) / 2))} {d.get('1', d.get(1, 0)):.1f}%")
        lines.append(f"  2分: {'█' * int(d.get('2', d.get(2, 0)) / 2)}{'░' * (25 - int(d.get('2', d.get(2, 0)) / 2))} {d.get('2', d.get(2, 0)):.1f}%")
        lines.append(f"  3分: {'█' * int(d.get('3', d.get(3, 0)) / 2)}{'░' * (25 - int(d.get('3', d.get(3, 0)) / 2))} {d.get('3', d.get(3, 0)):.1f}%")

        lines.append(f"\n{max_m} (均值最高 {max_s['mean']:.3f}):")
        d = max_s.get("dist_pct", {})
        lines.append(f"  1分: {'█' * int(d.get('1', d.get(1, 0)) / 2)}{'░' * (25 - int(d.get('1', d.get(1, 0)) / 2))} {d.get('1', d.get(1, 0)):.1f}%")
        lines.append(f"  2分: {'█' * int(d.get('2', d.get(2, 0)) / 2)}{'░' * (25 - int(d.get('2', d.get(2, 0)) / 2))} {d.get('2', d.get(2, 0)):.1f}%")
        lines.append(f"  3分: {'█' * int(d.get('3', d.get(3, 0)) / 2)}{'░' * (25 - int(d.get('3', d.get(3, 0)) / 2))} {d.get('3', d.get(3, 0)):.1f}%")

    return lines


def main():
    """Generate detailed comparison report with distributions."""
    print("Loading results...")
    sent_data = load_results("sentiment")
    risk_data = load_results("risk")

    report_lines = []
    report_lines.append("# FinRL 評分實驗 - 詳細分佈分析")
    report_lines.append("\n*本報告包含各配置的完整分數分佈 (1-5分百分比)，提供更精確的差異描述。*\n")

    # Summary with distribution
    report_lines.extend(generate_summary_with_dist(sent_data, risk_data))

    # Cross-task comparison
    report_lines.extend(cross_task_comparison(sent_data, risk_data))

    # Detailed comparisons with distribution
    report_lines.extend(reasoning_comparison_with_dist(sent_data, "sentiment"))
    report_lines.extend(reasoning_comparison_with_dist(risk_data, "risk"))

    report_lines.extend(model_comparison_with_dist(sent_data, "sentiment"))
    report_lines.extend(model_comparison_with_dist(risk_data, "risk"))

    report_lines.extend(input_source_comparison_with_dist(sent_data, "sentiment"))
    report_lines.extend(input_source_comparison_with_dist(risk_data, "risk"))

    # Write report
    report = "\n".join(report_lines)
    output_path = RESULTS_DIR / "detailed_distribution_analysis.md"
    with open(output_path, "w") as f:
        f.write(report)

    print(f"\nReport saved to: {output_path}")
    print("\n" + "="*70)
    print(report)


if __name__ == "__main__":
    main()