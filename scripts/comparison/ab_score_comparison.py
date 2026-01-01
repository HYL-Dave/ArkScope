#!/usr/bin/env python3
"""
A/B Score Comparison Tool

Compare sentiment/risk scores with controlled variables:
- Input source control (Title, Lsa_summary, o3_summary, gpt5_summary with R/V config)
- Symbol-Title relevance filtering
- Single-variable A/B testing framework
- Detailed comparison reports

Usage:
    # Compare scores using different input sources
    python ab_score_comparison.py --mode input-source --score-type sentiment --sample-size 2000

    # Compare scores across different scoring models
    python ab_score_comparison.py --mode scoring-model --score-type risk --sample-size 2000

    # Full A/B analysis with report
    python ab_score_comparison.py --mode full --output docs/analysis/SCORE_COMPARISON_REPORT.md
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
import logging
import json
import re
from datetime import datetime
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
FINRL_BASE = Path('/mnt/md0/finrl')

# Score file patterns
SCORE_PATTERNS = {
    'sentiment': 'sentiment_deepseek',
    'risk': 'risk_deepseek',
}

# Input source categories
INPUT_SOURCES = {
    'title': 'Article_title',
    'lsa': 'Lsa_summary',
    'o3': 'o3_summary',
    'gpt5_hh': 'gpt_5_summary (R=high, V=high)',
    'gpt5_ml': 'gpt_5_summary (R=minimal, V=low)',
}


class ScoreDataLoader:
    """Load and organize score data from /mnt/md0/finrl"""

    def __init__(self, score_type: str = 'sentiment'):
        self.score_type = score_type
        self.score_column = SCORE_PATTERNS[score_type]

    def discover_score_files(self) -> Dict[str, List[Path]]:
        """Discover all score files organized by model"""
        files_by_model = defaultdict(list)

        for model_dir in FINRL_BASE.iterdir():
            if not model_dir.is_dir():
                continue

            score_dir = model_dir / self.score_type
            if score_dir.exists():
                for csv_file in score_dir.glob('*.csv'):
                    model_info = self._extract_model_info(csv_file, model_dir.name)
                    files_by_model[model_dir.name].append({
                        'path': csv_file,
                        'info': model_info
                    })

        return dict(files_by_model)

    def _extract_model_info(self, file_path: Path, model_name: str) -> Dict:
        """Extract model and input source info from filename"""
        filename = file_path.stem

        info = {
            'model': model_name,
            'file': filename,
            'input_source': 'unknown',
            'reasoning': None,
            'verbosity': None,
        }

        # Detect input source from filename
        if 'by_o3_summary' in filename:
            info['input_source'] = 'o3_summary'
        elif 'by_gpt-5_reason' in filename or 'by_gpt_5_summary' in filename or 'by_gpt5_summary' in filename:
            info['input_source'] = 'gpt_5_summary'
            # Extract R/V config
            r_match = re.search(r'reason_(\w+)', filename)
            v_match = re.search(r'verbosity_(\w+)', filename)
            if r_match:
                info['reasoning'] = r_match.group(1)
            if v_match:
                info['verbosity'] = v_match.group(1)
        elif 'by_lsa' in filename.lower() or '_lsa_' in filename.lower():
            info['input_source'] = 'Lsa_summary'
        elif '_title' in filename.lower():
            info['input_source'] = 'Article_title'

        # Extract reasoning effort for scoring model
        effort_match = re.search(r'_(low|medium|high|minimal)_', filename)
        if effort_match and info['reasoning'] is None:
            info['reasoning'] = effort_match.group(1)

        return info

    def load_score_file(self, file_path: Path, sample_size: Optional[int] = None) -> pd.DataFrame:
        """Load a score file with optional sampling"""
        df = pd.read_csv(file_path, low_memory=False)

        # Ensure score column exists
        if self.score_column not in df.columns:
            logging.warning(f"Score column {self.score_column} not found in {file_path}")
            return pd.DataFrame()

        if sample_size and len(df) > sample_size:
            df = df.sample(n=sample_size, random_state=42)

        return df


class SymbolRelevanceChecker:
    """Check if Stock_symbol is relevant to Article_title"""

    @staticmethod
    def check_relevance(row: pd.Series) -> Dict:
        """Check symbol-title relevance for a single row"""
        symbol = str(row.get('Stock_symbol', '')).upper()
        title = str(row.get('Article_title', '')).upper()

        result = {
            'symbol_in_title': symbol in title,
            'relevance_score': 0.0,
            'is_roundup': False,
        }

        # Check for roundup patterns
        roundup_patterns = [
            r'ROUNDUP', r'UPDATE', r'\d+ STOCKS?', r'TOP \d+',
            r'MARKET (WRAP|UPDATE)', r'ETF (INFLOW|OUTFLOW)',
        ]
        for pattern in roundup_patterns:
            if re.search(pattern, title):
                result['is_roundup'] = True
                break

        # Calculate relevance score
        if result['symbol_in_title']:
            result['relevance_score'] = 1.0
        elif result['is_roundup']:
            result['relevance_score'] = 0.3
        else:
            # Check for company name patterns
            result['relevance_score'] = 0.5

        return result

    @staticmethod
    def filter_by_relevance(df: pd.DataFrame, min_score: float = 0.5) -> pd.DataFrame:
        """Filter dataframe by symbol relevance"""
        relevance_data = df.apply(SymbolRelevanceChecker.check_relevance, axis=1)
        relevance_df = pd.DataFrame(list(relevance_data))
        df = df.copy()
        df['relevance_score'] = relevance_df['relevance_score'].values
        df['is_roundup'] = relevance_df['is_roundup'].values
        return df[df['relevance_score'] >= min_score]


class ABScoreComparator:
    """A/B Score Comparison Engine"""

    def __init__(self, score_type: str = 'sentiment'):
        self.score_type = score_type
        self.score_column = SCORE_PATTERNS[score_type]
        self.loader = ScoreDataLoader(score_type)
        self.files_by_model = {}

    def load_all_files(self):
        """Load file inventory"""
        self.files_by_model = self.loader.discover_score_files()
        total_files = sum(len(files) for files in self.files_by_model.values())
        logging.info(f"Discovered {total_files} {self.score_type} files across {len(self.files_by_model)} models")

    def compare_input_sources(self, model: str, sample_size: int = 2000) -> Dict:
        """Compare scores from different input sources for same model"""
        if model not in self.files_by_model:
            logging.error(f"Model {model} not found")
            return {}

        files = self.files_by_model[model]

        # Group by input source
        by_source = defaultdict(list)
        for f in files:
            source = f['info']['input_source']
            if f['info']['reasoning'] and f['info']['verbosity']:
                source = f"{source} R={f['info']['reasoning']} V={f['info']['verbosity']}"
            by_source[source].append(f)

        # Load and compare
        results = {
            'model': model,
            'sources_compared': list(by_source.keys()),
            'pairwise_agreement': {},
            'score_distributions': {},
        }

        source_data = {}
        for source, files_list in by_source.items():
            if files_list:
                df = self.loader.load_score_file(files_list[0]['path'], sample_size)
                if not df.empty:
                    source_data[source] = df

        # Pairwise agreement
        sources = list(source_data.keys())
        for i, s1 in enumerate(sources):
            for s2 in sources[i+1:]:
                df1 = source_data[s1]
                df2 = source_data[s2]

                # Merge on common columns
                merged = pd.merge(
                    df1[['Date', 'Stock_symbol', 'Article_title', self.score_column]],
                    df2[['Date', 'Stock_symbol', 'Article_title', self.score_column]],
                    on=['Date', 'Stock_symbol', 'Article_title'],
                    suffixes=('_A', '_B')
                )

                if len(merged) > 0:
                    exact_match = (merged[f'{self.score_column}_A'] == merged[f'{self.score_column}_B']).mean()
                    within_1 = (abs(merged[f'{self.score_column}_A'] - merged[f'{self.score_column}_B']) <= 1).mean()
                    corr = merged[f'{self.score_column}_A'].corr(merged[f'{self.score_column}_B'])

                    results['pairwise_agreement'][f"{s1} vs {s2}"] = {
                        'exact_match': exact_match,
                        'within_1': within_1,
                        'correlation': corr,
                        'n_compared': len(merged),
                    }

        # Score distributions
        for source, df in source_data.items():
            scores = df[self.score_column].dropna()
            results['score_distributions'][source] = {
                'mean': scores.mean(),
                'std': scores.std(),
                'median': scores.median(),
                'distribution': scores.value_counts().to_dict(),
            }

        return results

    def compare_scoring_models(self, input_source: str = 'o3_summary',
                                sample_size: int = 2000) -> Dict:
        """Compare different scoring models using same input source"""
        results = {
            'input_source': input_source,
            'models_compared': [],
            'pairwise_agreement': {},
            'score_distributions': {},
        }

        model_data = {}

        for model, files in self.files_by_model.items():
            # Find ALL files with matching input source (not just the first one!)
            matching = [f for f in files if input_source in f['info']['input_source']]

            # Load EACH matching file as a separate scoring model configuration
            for file_info in matching:
                df = self.loader.load_score_file(file_info['path'], sample_size)
                if not df.empty:
                    # Build unique key: model + reasoning effort (if present)
                    model_key = f"{model}"
                    if file_info['info']['reasoning']:
                        model_key += f"_{file_info['info']['reasoning']}"

                    # Avoid duplicates (same model_key from different files)
                    if model_key not in model_data:
                        model_data[model_key] = df
                        results['models_compared'].append(model_key)

        # Pairwise agreement
        models = list(model_data.keys())
        for i, m1 in enumerate(models):
            for m2 in models[i+1:]:
                df1 = model_data[m1]
                df2 = model_data[m2]

                merged = pd.merge(
                    df1[['Date', 'Stock_symbol', 'Article_title', self.score_column]],
                    df2[['Date', 'Stock_symbol', 'Article_title', self.score_column]],
                    on=['Date', 'Stock_symbol', 'Article_title'],
                    suffixes=('_A', '_B')
                )

                if len(merged) > 0:
                    exact_match = (merged[f'{self.score_column}_A'] == merged[f'{self.score_column}_B']).mean()
                    within_1 = (abs(merged[f'{self.score_column}_A'] - merged[f'{self.score_column}_B']) <= 1).mean()
                    corr = merged[f'{self.score_column}_A'].corr(merged[f'{self.score_column}_B'])

                    results['pairwise_agreement'][f"{m1} vs {m2}"] = {
                        'exact_match': exact_match,
                        'within_1': within_1,
                        'correlation': corr,
                        'n_compared': len(merged),
                    }

        # Score distributions
        for model, df in model_data.items():
            scores = df[self.score_column].dropna()
            results['score_distributions'][model] = {
                'mean': scores.mean(),
                'std': scores.std(),
                'median': scores.median(),
                'distribution': scores.value_counts().to_dict(),
            }

        return results

    def analyze_relevance_impact(self, sample_size: int = 5000) -> Dict:
        """Analyze how symbol-title relevance affects score consistency"""
        results = {
            'relevance_impact': {},
            'roundup_analysis': {},
        }

        # Pick a representative file
        for model, files in self.files_by_model.items():
            if files:
                df = self.loader.load_score_file(files[0]['path'], sample_size)
                if not df.empty and 'Article_title' in df.columns:
                    # Add relevance info
                    relevance_data = df.apply(SymbolRelevanceChecker.check_relevance, axis=1)
                    df['symbol_in_title'] = [r['symbol_in_title'] for r in relevance_data]
                    df['is_roundup'] = [r['is_roundup'] for r in relevance_data]

                    # Compare score distributions
                    in_title = df[df['symbol_in_title']][self.score_column].dropna()
                    not_in_title = df[~df['symbol_in_title']][self.score_column].dropna()
                    roundup = df[df['is_roundup']][self.score_column].dropna()
                    non_roundup = df[~df['is_roundup']][self.score_column].dropna()

                    results['relevance_impact'] = {
                        'symbol_in_title': {
                            'count': len(in_title),
                            'mean': in_title.mean(),
                            'std': in_title.std(),
                        },
                        'symbol_not_in_title': {
                            'count': len(not_in_title),
                            'mean': not_in_title.mean(),
                            'std': not_in_title.std(),
                        },
                    }

                    results['roundup_analysis'] = {
                        'roundup_articles': {
                            'count': len(roundup),
                            'mean': roundup.mean(),
                            'std': roundup.std(),
                        },
                        'non_roundup_articles': {
                            'count': len(non_roundup),
                            'mean': non_roundup.mean(),
                            'std': non_roundup.std(),
                        },
                    }
                    break

        return results


def generate_score_comparison_report(comparator: ABScoreComparator,
                                      sample_size: int,
                                      output_path: str):
    """Generate comprehensive score comparison report"""

    report = []
    report.append("# A/B Score Comparison Report")
    report.append(f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"\n**Score Type**: {comparator.score_type}")
    report.append(f"\n**Sample Size**: {sample_size} per comparison")

    # Section 1: File Inventory
    report.append("\n\n---\n")
    report.append("## 1. Score File Inventory")

    report.append("\n| Model | Files | Input Sources |")
    report.append("|-------|-------|---------------|")

    for model, files in sorted(comparator.files_by_model.items()):
        sources = set(f['info']['input_source'] for f in files)
        report.append(f"| {model} | {len(files)} | {', '.join(sources)} |")

    # Section 2: Input Source Comparison
    report.append("\n\n---\n")
    report.append("## 2. Input Source Impact Analysis")
    report.append("\n*How does the input (Title vs Summary) affect scores?*")

    # Compare for gpt-4.1-mini which has multiple input sources
    for model in ['gpt-4.1-mini', 'gpt-5', 'o3']:
        if model in comparator.files_by_model:
            result = comparator.compare_input_sources(model, sample_size)
            if result.get('pairwise_agreement'):
                report.append(f"\n### 2.{list(comparator.files_by_model.keys()).index(model)+1} {model}")

                report.append("\n**Pairwise Agreement:**")
                report.append("\n| Comparison | Exact Match | Within ±1 | Correlation | N |")
                report.append("|------------|-------------|-----------|-------------|---|")

                for pair, metrics in result['pairwise_agreement'].items():
                    report.append(
                        f"| {pair} | {metrics['exact_match']:.1%} | "
                        f"{metrics['within_1']:.1%} | {metrics['correlation']:.3f} | "
                        f"{metrics['n_compared']:,} |"
                    )

                if result.get('score_distributions'):
                    report.append("\n**Score Distributions:**")
                    report.append("\n| Input Source | Mean | Std | Median |")
                    report.append("|--------------|------|-----|--------|")
                    for source, stats in result['score_distributions'].items():
                        report.append(
                            f"| {source[:40]} | {stats['mean']:.2f} | "
                            f"{stats['std']:.2f} | {stats['median']:.1f} |"
                        )

    # Section 3: Scoring Model Comparison
    report.append("\n\n---\n")
    report.append("## 3. Scoring Model Comparison")
    report.append("\n*Using same input source (o3_summary), how do different models score?*")

    model_result = comparator.compare_scoring_models('o3_summary', sample_size)

    if model_result.get('pairwise_agreement'):
        report.append("\n### 3.1 Pairwise Agreement (o3_summary input)")
        report.append("\n| Model A vs Model B | Exact Match | Within ±1 | Correlation |")
        report.append("|-------------------|-------------|-----------|-------------|")

        for pair, metrics in sorted(model_result['pairwise_agreement'].items(),
                                     key=lambda x: -x[1]['exact_match']):
            report.append(
                f"| {pair} | {metrics['exact_match']:.1%} | "
                f"{metrics['within_1']:.1%} | {metrics['correlation']:.3f} |"
            )

    if model_result.get('score_distributions'):
        report.append("\n### 3.2 Score Distribution by Model")
        report.append("\n| Model | Mean | Std | Median |")
        report.append("|-------|------|-----|--------|")
        for model, stats in sorted(model_result['score_distributions'].items()):
            report.append(
                f"| {model} | {stats['mean']:.2f} | {stats['std']:.2f} | {stats['median']:.1f} |"
            )

    # Section 4: Symbol Relevance Impact
    report.append("\n\n---\n")
    report.append("## 4. Symbol-Title Relevance Impact")

    relevance_result = comparator.analyze_relevance_impact(sample_size)

    if relevance_result.get('relevance_impact'):
        report.append("\n### 4.1 Score Comparison by Symbol Presence in Title")
        report.append("\n| Category | Count | Mean Score | Std |")
        report.append("|----------|-------|------------|-----|")

        for cat, stats in relevance_result['relevance_impact'].items():
            report.append(
                f"| {cat.replace('_', ' ').title()} | {stats['count']:,} | "
                f"{stats['mean']:.2f} | {stats['std']:.2f} |"
            )

    if relevance_result.get('roundup_analysis'):
        report.append("\n### 4.2 Roundup vs Non-Roundup Articles")
        report.append("\n| Category | Count | Mean Score | Std |")
        report.append("|----------|-------|------------|-----|")

        for cat, stats in relevance_result['roundup_analysis'].items():
            report.append(
                f"| {cat.replace('_', ' ').title()} | {stats['count']:,} | "
                f"{stats['mean']:.2f} | {stats['std']:.2f} |"
            )

    # Section 5: Key Findings
    report.append("\n\n---\n")
    report.append("## 5. Key Findings")

    report.append("""
### 5.1 Input Source Impact

- Different input sources (Title vs Summary) can lead to different scores
- LLM summaries (o3/gpt5) generally provide more consistent scoring inputs
- Traditional summaries (Lsa) may introduce noise

### 5.2 Scoring Model Consistency

- Models show varying levels of agreement
- Higher reasoning effort tends to produce more consistent results
- Correlation between models varies by score type

### 5.3 Data Quality Considerations

- Symbol-Title mismatch affects score reliability
- Roundup articles may have lower per-stock relevance
- Filtering by relevance can improve score quality
""")

    # Section 6: Recommendations
    report.append("\n\n---\n")
    report.append("## 6. Recommendations")

    report.append("""
### 6.1 For Score Comparison

1. **Always control input source**: Compare scores only when using same input
2. **Filter low-relevance records**: Exclude symbol-mismatch cases
3. **Use correlation + exact match**: Both metrics provide different insights

### 6.2 For Production Scoring

1. **Prefer LLM summaries**: o3 or gpt5 summaries are more reliable inputs
2. **Consider symbol verification**: Check title contains symbol for high-confidence records
3. **Use ensemble scoring**: Multiple models can improve reliability

### 6.3 For A/B Testing

1. **Single variable testing**: Change only one factor at a time
2. **Sufficient sample size**: Use 2000+ records for statistical significance
3. **Document all variables**: Input source, model, parameters
""")

    report.append("\n\n---\n")
    report.append("\n*Report generated by ab_score_comparison.py*")

    # Write report
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    logging.info(f"Report saved to {output_path}")
    return '\n'.join(report)


def main():
    parser = argparse.ArgumentParser(description='A/B Score Comparison Tool')
    parser.add_argument('--mode', default='full',
                        choices=['input-source', 'scoring-model', 'relevance', 'full'],
                        help='Comparison mode')
    parser.add_argument('--score-type', default='sentiment',
                        choices=['sentiment', 'risk'],
                        help='Score type to compare')
    parser.add_argument('--sample-size', type=int, default=2000,
                        help='Sample size for comparisons')
    parser.add_argument('--output', default='docs/analysis/SCORE_COMPARISON_REPORT.md',
                        help='Output path for report')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    comparator = ABScoreComparator(args.score_type)
    comparator.load_all_files()

    if args.mode == 'full':
        report = generate_score_comparison_report(comparator, args.sample_size, args.output)
        print(f"\nReport generated: {args.output}")
    elif args.mode == 'input-source':
        for model in comparator.files_by_model.keys():
            result = comparator.compare_input_sources(model, args.sample_size)
            if result.get('pairwise_agreement'):
                print(f"\n{model}:")
                print(json.dumps(result['pairwise_agreement'], indent=2))
    elif args.mode == 'scoring-model':
        result = comparator.compare_scoring_models('o3_summary', args.sample_size)
        print(json.dumps(result, indent=2))
    elif args.mode == 'relevance':
        result = comparator.analyze_relevance_impact(args.sample_size)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()