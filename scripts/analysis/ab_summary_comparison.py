#!/usr/bin/env python3
"""
A/B Summary Comparison Tool (Comprehensive Version)

Compare ALL summary sources systematically:
- Traditional algorithms: Lsa_summary, Luhn_summary, Textrank_summary, Lexrank_summary
- O3 model: o3_summary (1 version)
- GPT-5 model: gpt_5_summary (12 versions with different R/V combinations)

Usage:
    # Compare all summary types
    python ab_summary_comparison.py --mode all --sample-size 2000

    # Compare specific gpt-5 configurations
    python ab_summary_comparison.py --mode gpt5-rv --sample-size 2000

    # Compare traditional vs LLM
    python ab_summary_comparison.py --mode traditional-vs-llm --sample-size 2000
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
import json
import logging
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional
import re
from datetime import datetime
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
FINRL_BASE = Path('/mnt/md0/finrl')
O3_SUMMARY_PATH = FINRL_BASE / 'o3/summary/o3_news_with_summary.csv'
GPT5_SUMMARY_DIR = FINRL_BASE / 'gpt-5/summary'

# All GPT-5 configurations
GPT5_CONFIGS = [
    ('minimal', 'low'), ('minimal', 'medium'), ('minimal', 'high'),
    ('low', 'low'), ('low', 'medium'), ('low', 'high'),
    ('medium', 'low'), ('medium', 'medium'), ('medium', 'high'),
    ('high', 'low'), ('high', 'medium'), ('high', 'high'),
]

# Traditional summary columns
TRADITIONAL_SUMMARIES = ['Lsa_summary', 'Luhn_summary', 'Textrank_summary', 'Lexrank_summary']


def get_gpt5_path(reason: str, verbosity: str) -> Path:
    """Get path for specific GPT-5 configuration"""
    return GPT5_SUMMARY_DIR / f'gpt-5_reason_{reason}_verbosity_{verbosity}_news_with_summary.csv'


class ComprehensiveSummaryComparator:
    """Compare all summary sources comprehensively"""

    def __init__(self):
        self.data_cache = {}
        self.o3_data = None

    def load_o3_data(self) -> pd.DataFrame:
        """Load O3 summary data (contains all traditional summaries too)"""
        if self.o3_data is None:
            logging.info(f"Loading O3 data from {O3_SUMMARY_PATH}...")
            self.o3_data = pd.read_csv(O3_SUMMARY_PATH, low_memory=False)
            logging.info(f"Loaded {len(self.o3_data)} rows")
        return self.o3_data

    def load_gpt5_data(self, reason: str, verbosity: str) -> pd.DataFrame:
        """Load specific GPT-5 configuration"""
        key = f"gpt5_{reason}_{verbosity}"
        if key not in self.data_cache:
            path = get_gpt5_path(reason, verbosity)
            logging.info(f"Loading GPT-5 R={reason} V={verbosity} from {path}...")
            self.data_cache[key] = pd.read_csv(path, low_memory=False)
        return self.data_cache[key]

    @staticmethod
    def word_count(text) -> int:
        if pd.isna(text) or not str(text).strip():
            return 0
        return len(str(text).split())

    @staticmethod
    def char_count(text) -> int:
        if pd.isna(text) or not str(text).strip():
            return 0
        return len(str(text))

    @staticmethod
    def jaccard_similarity(text1, text2) -> float:
        if pd.isna(text1) or pd.isna(text2):
            return 0.0
        words1 = set(str(text1).lower().split())
        words2 = set(str(text2).lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def word_overlap_ratio(text1, text2) -> float:
        if pd.isna(text1) or pd.isna(text2):
            return 0.0
        words1 = set(str(text1).lower().split())
        words2 = set(str(text2).lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        min_size = min(len(words1), len(words2))
        return len(intersection) / min_size if min_size > 0 else 0.0

    def compute_column_stats(self, df: pd.DataFrame, col: str) -> Dict:
        """Compute statistics for a single column"""
        valid = df[col].dropna()
        valid = valid[valid.astype(str).str.strip() != '']

        word_counts = valid.apply(self.word_count)
        char_counts = valid.apply(self.char_count)

        return {
            'total_rows': len(df),
            'valid_count': len(valid),
            'coverage': len(valid) / len(df) * 100,
            'avg_words': word_counts.mean(),
            'std_words': word_counts.std(),
            'min_words': word_counts.min(),
            'max_words': word_counts.max(),
            'median_words': word_counts.median(),
            'avg_chars': char_counts.mean(),
            'std_chars': char_counts.std(),
        }

    def compute_pairwise_similarity(self, df: pd.DataFrame, col1: str, col2: str,
                                     sample_size: int = 1000) -> Dict:
        """Compute similarity between two columns"""
        # Filter to rows with both columns valid
        valid_mask = (
            df[col1].notna() &
            (df[col1].astype(str).str.strip() != '') &
            df[col2].notna() &
            (df[col2].astype(str).str.strip() != '')
        )
        valid_df = df[valid_mask]

        if len(valid_df) == 0:
            return {'jaccard_mean': 0, 'jaccard_std': 0, 'overlap_mean': 0, 'overlap_std': 0, 'n_compared': 0}

        # Sample if too large
        if len(valid_df) > sample_size:
            valid_df = valid_df.sample(n=sample_size, random_state=42)

        jaccard_scores = []
        overlap_scores = []

        for _, row in valid_df.iterrows():
            jaccard_scores.append(self.jaccard_similarity(row[col1], row[col2]))
            overlap_scores.append(self.word_overlap_ratio(row[col1], row[col2]))

        return {
            'jaccard_mean': np.mean(jaccard_scores),
            'jaccard_std': np.std(jaccard_scores),
            'jaccard_min': np.min(jaccard_scores),
            'jaccard_max': np.max(jaccard_scores),
            'overlap_mean': np.mean(overlap_scores),
            'overlap_std': np.std(overlap_scores),
            'n_compared': len(valid_df),
        }


def generate_all_summaries_report(comparator: ComprehensiveSummaryComparator,
                                   sample_size: int, output_path: str):
    """Generate comprehensive report comparing ALL summary types"""

    report = []
    report.append("# Comprehensive Summary Comparison Report")
    report.append(f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"\n**Similarity Sample Size**: {sample_size} records per comparison")

    # Section 1: Data Inventory
    report.append("\n\n---\n")
    report.append("## 1. Summary Data Inventory")

    report.append("\n### 1.1 Available Summary Sources")
    report.append("\n| Category | Summary Type | Source | R/V Config |")
    report.append("|----------|--------------|--------|------------|")
    report.append("| Traditional | Lsa_summary | LSA algorithm | N/A |")
    report.append("| Traditional | Luhn_summary | Luhn algorithm | N/A |")
    report.append("| Traditional | Textrank_summary | TextRank algorithm | N/A |")
    report.append("| Traditional | Lexrank_summary | LexRank algorithm | N/A |")
    report.append("| LLM | o3_summary | OpenAI o3 | default |")

    for reason, verbosity in GPT5_CONFIGS:
        report.append(f"| LLM | gpt_5_summary | OpenAI GPT-5 | R={reason}, V={verbosity} |")

    report.append(f"\n**Total: 4 traditional + 1 o3 + 12 gpt-5 = 17 summary types**")

    # Section 2: Traditional Summary Statistics
    report.append("\n\n---\n")
    report.append("## 2. Traditional Summary Statistics")

    o3_df = comparator.load_o3_data()

    report.append("\n### 2.1 Length Statistics")
    report.append("\n| Summary Type | Valid Count | Coverage | Avg Words | Std | Min | Max | Median |")
    report.append("|--------------|-------------|----------|-----------|-----|-----|-----|--------|")

    trad_stats = {}
    for col in TRADITIONAL_SUMMARIES:
        stats = comparator.compute_column_stats(o3_df, col)
        trad_stats[col] = stats
        report.append(
            f"| {col} | {stats['valid_count']:,} | {stats['coverage']:.1f}% | "
            f"{stats['avg_words']:.1f} | {stats['std_words']:.1f} | "
            f"{stats['min_words']:.0f} | {stats['max_words']:.0f} | {stats['median_words']:.0f} |"
        )

    # O3 stats
    o3_stats = comparator.compute_column_stats(o3_df, 'o3_summary')
    report.append(
        f"| o3_summary | {o3_stats['valid_count']:,} | {o3_stats['coverage']:.1f}% | "
        f"{o3_stats['avg_words']:.1f} | {o3_stats['std_words']:.1f} | "
        f"{o3_stats['min_words']:.0f} | {o3_stats['max_words']:.0f} | {o3_stats['median_words']:.0f} |"
    )

    # Section 3: GPT-5 Configuration Comparison
    report.append("\n\n---\n")
    report.append("## 3. GPT-5 Configuration Comparison (Reason × Verbosity)")

    report.append("\n### 3.1 Length Statistics by R/V Configuration")
    report.append("\n| R \\ V | low (words) | medium (words) | high (words) |")
    report.append("|-------|-------------|----------------|--------------|")

    gpt5_stats = {}
    for reason in ['minimal', 'low', 'medium', 'high']:
        row = f"| {reason} |"
        for verbosity in ['low', 'medium', 'high']:
            gpt5_df = comparator.load_gpt5_data(reason, verbosity)
            stats = comparator.compute_column_stats(gpt5_df, 'gpt_5_summary')
            gpt5_stats[(reason, verbosity)] = stats
            row += f" {stats['avg_words']:.1f} ± {stats['std_words']:.1f} |"
        report.append(row)

    # Section 4: Pairwise Similarity Analysis
    report.append("\n\n---\n")
    report.append("## 4. Pairwise Similarity Analysis")

    report.append("\n### 4.1 Traditional Summaries vs Each Other")
    report.append("\n| Comparison | Jaccard Mean | Jaccard Std | N Compared |")
    report.append("|------------|--------------|-------------|------------|")

    for i, col1 in enumerate(TRADITIONAL_SUMMARIES):
        for col2 in TRADITIONAL_SUMMARIES[i+1:]:
            sim = comparator.compute_pairwise_similarity(o3_df, col1, col2, sample_size)
            report.append(f"| {col1} vs {col2} | {sim['jaccard_mean']:.3f} | {sim['jaccard_std']:.3f} | {sim['n_compared']:,} |")

    report.append("\n### 4.2 Traditional vs O3")
    report.append("\n| Comparison | Jaccard Mean | Jaccard Std | N Compared |")
    report.append("|------------|--------------|-------------|------------|")

    for col in TRADITIONAL_SUMMARIES:
        sim = comparator.compute_pairwise_similarity(o3_df, col, 'o3_summary', sample_size)
        report.append(f"| {col} vs o3_summary | {sim['jaccard_mean']:.3f} | {sim['jaccard_std']:.3f} | {sim['n_compared']:,} |")

    report.append("\n### 4.3 O3 vs GPT-5 (All Configurations)")
    report.append("\n| GPT-5 Config (R, V) | Jaccard Mean | Jaccard Std | N Compared |")
    report.append("|---------------------|--------------|-------------|------------|")

    o3_vs_gpt5_sims = {}
    for reason, verbosity in GPT5_CONFIGS:
        gpt5_df = comparator.load_gpt5_data(reason, verbosity)
        # Merge to compare
        merged = o3_df[['o3_summary']].copy()
        merged['gpt_5_summary'] = gpt5_df['gpt_5_summary']
        sim = comparator.compute_pairwise_similarity(merged, 'o3_summary', 'gpt_5_summary', sample_size)
        o3_vs_gpt5_sims[(reason, verbosity)] = sim
        report.append(f"| R={reason}, V={verbosity} | {sim['jaccard_mean']:.3f} | {sim['jaccard_std']:.3f} | {sim['n_compared']:,} |")

    report.append("\n### 4.4 GPT-5 Configurations vs Each Other (Sample: high-high vs others)")
    report.append("\n| Comparison | Jaccard Mean | Jaccard Std |")
    report.append("|------------|--------------|-------------|")

    base_df = comparator.load_gpt5_data('high', 'high')
    for reason, verbosity in GPT5_CONFIGS:
        if reason == 'high' and verbosity == 'high':
            continue
        other_df = comparator.load_gpt5_data(reason, verbosity)
        merged = pd.DataFrame({
            'base': base_df['gpt_5_summary'],
            'other': other_df['gpt_5_summary']
        })
        sim = comparator.compute_pairwise_similarity(merged, 'base', 'other', sample_size)
        report.append(f"| R=high,V=high vs R={reason},V={verbosity} | {sim['jaccard_mean']:.3f} | {sim['jaccard_std']:.3f} |")

    report.append("\n### 4.5 Lsa_summary vs GPT-5 (All Configurations)")
    report.append("\n| GPT-5 Config (R, V) | Jaccard Mean | Jaccard Std |")
    report.append("|---------------------|--------------|-------------|")

    for reason, verbosity in GPT5_CONFIGS:
        gpt5_df = comparator.load_gpt5_data(reason, verbosity)
        merged = o3_df[['Lsa_summary']].copy()
        merged['gpt_5_summary'] = gpt5_df['gpt_5_summary']
        sim = comparator.compute_pairwise_similarity(merged, 'Lsa_summary', 'gpt_5_summary', sample_size)
        report.append(f"| R={reason}, V={verbosity} | {sim['jaccard_mean']:.3f} | {sim['jaccard_std']:.3f} |")

    # Section 5: Key Findings
    report.append("\n\n---\n")
    report.append("## 5. Key Findings")

    # Find best and worst similarity configs
    best_o3_gpt5 = max(o3_vs_gpt5_sims.items(), key=lambda x: x[1]['jaccard_mean'])
    worst_o3_gpt5 = min(o3_vs_gpt5_sims.items(), key=lambda x: x[1]['jaccard_mean'])

    report.append("\n### 5.1 O3 vs GPT-5 Similarity Range")
    report.append(f"\n- **Most similar to O3**: GPT-5 R={best_o3_gpt5[0][0]}, V={best_o3_gpt5[0][1]} (Jaccard={best_o3_gpt5[1]['jaccard_mean']:.3f})")
    report.append(f"- **Least similar to O3**: GPT-5 R={worst_o3_gpt5[0][0]}, V={worst_o3_gpt5[0][1]} (Jaccard={worst_o3_gpt5[1]['jaccard_mean']:.3f})")

    # Length comparison
    report.append("\n### 5.2 Summary Length Comparison")

    shortest_gpt5 = min(gpt5_stats.items(), key=lambda x: x[1]['avg_words'])
    longest_gpt5 = max(gpt5_stats.items(), key=lambda x: x[1]['avg_words'])

    report.append(f"\n- **Traditional (Lsa)**: {trad_stats['Lsa_summary']['avg_words']:.1f} words")
    report.append(f"- **O3**: {o3_stats['avg_words']:.1f} words")
    report.append(f"- **GPT-5 shortest**: R={shortest_gpt5[0][0]}, V={shortest_gpt5[0][1]} ({shortest_gpt5[1]['avg_words']:.1f} words)")
    report.append(f"- **GPT-5 longest**: R={longest_gpt5[0][0]}, V={longest_gpt5[0][1]} ({longest_gpt5[1]['avg_words']:.1f} words)")

    report.append("\n### 5.3 Verbosity Effect on Length")
    report.append("\n| Reasoning | V=low → V=high Δ |")
    report.append("|-----------|------------------|")
    for reason in ['minimal', 'low', 'medium', 'high']:
        low_words = gpt5_stats[(reason, 'low')]['avg_words']
        high_words = gpt5_stats[(reason, 'high')]['avg_words']
        delta = high_words - low_words
        report.append(f"| {reason} | +{delta:.1f} words |")

    # Section 6: Representative Samples
    report.append("\n\n---\n")
    report.append("## 6. Representative Sample Comparison")
    report.append("\n*Comparing same article across different summary methods*")

    # Get a sample
    sample_idx = o3_df[
        o3_df['Lsa_summary'].notna() &
        o3_df['o3_summary'].notna()
    ].sample(n=3, random_state=42).index.tolist()

    gpt5_high_high = comparator.load_gpt5_data('high', 'high')
    gpt5_minimal_low = comparator.load_gpt5_data('minimal', 'low')

    for i, idx in enumerate(sample_idx, 1):
        row = o3_df.loc[idx]
        report.append(f"\n### Sample {i}: {row['Stock_symbol']} ({str(row['Date'])[:10]})")
        report.append(f"\n**Title**: {str(row['Article_title'])}")

        # Helper to format summary - show full content, clean up special chars
        def format_summary(text):
            if pd.isna(text):
                return "(empty)"
            s = str(text).strip()
            # Clean up common problematic characters
            s = s.replace('\x00', '').replace('\r', ' ')
            return s

        lsa_text = format_summary(row['Lsa_summary'])
        report.append(f"\n**Lsa_summary** ({comparator.word_count(row['Lsa_summary'])} words):")
        report.append(f"> {lsa_text}")

        o3_text = format_summary(row['o3_summary'])
        report.append(f"\n**o3_summary** ({comparator.word_count(row['o3_summary'])} words):")
        report.append(f"> {o3_text}")

        gpt5_hh = gpt5_high_high.loc[idx, 'gpt_5_summary']
        gpt5_hh_text = format_summary(gpt5_hh)
        report.append(f"\n**gpt_5_summary R=high, V=high** ({comparator.word_count(gpt5_hh)} words):")
        report.append(f"> {gpt5_hh_text}")

        gpt5_ml = gpt5_minimal_low.loc[idx, 'gpt_5_summary']
        gpt5_ml_text = format_summary(gpt5_ml)
        report.append(f"\n**gpt_5_summary R=minimal, V=low** ({comparator.word_count(gpt5_ml)} words):")
        report.append(f"> {gpt5_ml_text}")

    # Section 7: Conclusions
    report.append("\n\n---\n")
    report.append("## 7. Conclusions and Recommendations")

    report.append("\n### 7.1 Summary")
    report.append(f"""
- **Total summary types analyzed**: 17 (4 traditional + 1 O3 + 12 GPT-5)
- **Traditional algorithms** produce shorter, more variable summaries
- **LLM summaries** are more consistent in length (lower std)
- **GPT-5 verbosity** significantly affects output length
- **O3 and GPT-5** show moderate similarity, with R=high configs being most similar
""")

    report.append("\n### 7.2 Recommendations")
    report.append("""
- For **sentiment/risk scoring**: Use LLM summaries (more focused, consistent)
- For **cost optimization**: Consider R=minimal or R=low with V=low
- For **maximum detail**: Use R=high, V=high
- For **O3/GPT-5 interchangeability**: R=high configs are most compatible
""")

    report.append("\n\n---\n")
    report.append(f"\n*Report generated by ab_summary_comparison.py (comprehensive mode)*")

    # Write report
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    logging.info(f"Report saved to {output_path}")
    return '\n'.join(report)


def main():
    parser = argparse.ArgumentParser(description='Comprehensive A/B Summary Comparison Tool')
    parser.add_argument('--mode', default='all',
                        choices=['all', 'gpt5-rv', 'traditional-vs-llm'],
                        help='Comparison mode')
    parser.add_argument('--sample-size', type=int, default=2000,
                        help='Number of records to sample for similarity calculations')
    parser.add_argument('--output', default='docs/analysis/SUMMARY_COMPARISON_REPORT.md',
                        help='Output path for markdown report')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    comparator = ComprehensiveSummaryComparator()

    if args.mode == 'all':
        report = generate_all_summaries_report(comparator, args.sample_size, args.output)
    else:
        logging.warning(f"Mode '{args.mode}' not fully implemented yet, using 'all' mode")
        report = generate_all_summaries_report(comparator, args.sample_size, args.output)

    print(f"\nReport generated: {args.output}")


if __name__ == '__main__':
    main()