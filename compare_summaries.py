#!/usr/bin/env python3
"""
Summary Text Comparison Tool

專門比較總結文本的工具，支援：
- 文本相似度分析 (BLEU, ROUGE, Jaccard, Cosine)
- 長度統計和分佈分析
- 空值和品質檢查
- 關鍵詞提取和比較
- 文本重複度分析

Usage:
    python compare_summaries.py --root-dir /mnt/md0/finrl --output summary_comparison.json
    python compare_summaries.py --files file1.csv file2.csv --columns o3_summary gpt_5_summary --output comparison.json
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
import json
import sys
import logging
import re
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional, Set
import hashlib
from datetime import datetime

# 文本相似度計算所需的庫
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn not available. Cosine similarity will be disabled.")

def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

class TextSimilarityCalculator:
    """文本相似度計算器"""

    @staticmethod
    def jaccard_similarity(text1: str, text2: str) -> float:
        """計算 Jaccard 相似度"""
        if pd.isna(text1) or pd.isna(text2):
            return 0.0

        # 轉換為小寫並分詞
        words1 = set(str(text1).lower().split())
        words2 = set(str(text2).lower().split())

        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def word_overlap_ratio(text1: str, text2: str) -> float:
        """計算詞彙重疊率"""
        if pd.isna(text1) or pd.isna(text2):
            return 0.0

        words1 = set(str(text1).lower().split())
        words2 = set(str(text2).lower().split())

        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        min_words = min(len(words1), len(words2))

        return len(intersection) / min_words if min_words > 0 else 0.0

    @staticmethod
    def length_ratio(text1: str, text2: str) -> float:
        """計算長度比率 (較短/較長)"""
        if pd.isna(text1) or pd.isna(text2):
            return 0.0

        len1, len2 = len(str(text1)), len(str(text2))

        if len1 == 0 and len2 == 0:
            return 1.0
        if len1 == 0 or len2 == 0:
            return 0.0

        return min(len1, len2) / max(len1, len2)

    @staticmethod
    def cosine_similarity_score(text1: str, text2: str) -> float:
        """計算餘弦相似度"""
        if not SKLEARN_AVAILABLE:
            return 0.0

        if pd.isna(text1) or pd.isna(text2):
            return 0.0

        try:
            texts = [str(text1), str(text2)]
            vectorizer = TfidfVectorizer().fit(texts)
            tfidf_matrix = vectorizer.transform(texts)
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return similarity
        except:
            return 0.0

    @staticmethod
    def simple_bleu_score(reference: str, candidate: str) -> float:
        """簡化版 BLEU 分數 (unigram only)"""
        if pd.isna(reference) or pd.isna(candidate):
            return 0.0

        ref_words = str(reference).lower().split()
        cand_words = str(candidate).lower().split()

        if not ref_words and not cand_words:
            return 1.0
        if not cand_words:
            return 0.0

        # 計算 precision
        ref_counter = Counter(ref_words)
        cand_counter = Counter(cand_words)

        matching = 0
        for word in cand_counter:
            matching += min(cand_counter[word], ref_counter.get(word, 0))

        precision = matching / len(cand_words) if cand_words else 0.0

        # 簡化的 brevity penalty
        bp = min(1.0, len(cand_words) / len(ref_words)) if ref_words else 0.0

        return precision * bp

class SummaryFileScanner:
    """掃描包含總結文本的檔案"""

    def __init__(self):
        self.summary_columns = ['o3_summary', 'gpt_5_summary']

    def scan_root_directory(self, root_dir: str) -> List[Dict]:
        """掃描根目錄，找出包含總結文本的檔案"""
        root_path = Path(root_dir)
        if not root_path.exists():
            raise ValueError(f"Root directory not found: {root_dir}")

        files_info = []

        # 查找所有模型的 summary 資料夾
        for model_dir in root_path.iterdir():
            if model_dir.is_dir():
                summary_dir = model_dir / 'summary'
                if summary_dir.exists():
                    csv_files = list(summary_dir.glob("*.csv"))
                    for csv_file in csv_files:
                        info = self._extract_file_info(csv_file, model_name=model_dir.name)
                        if info:
                            files_info.append(info)

        logging.info(f"Found {len(files_info)} files with summary columns")
        return files_info

    def scan_specific_files(self, file_paths: List[str]) -> List[Dict]:
        """掃描指定的檔案"""
        files_info = []

        for file_path in file_paths:
            path = Path(file_path)
            if path.exists():
                info = self._extract_file_info(path)
                if info:
                    files_info.append(info)

        return files_info

    def _extract_file_info(self, file_path: Path, model_name: str = None) -> Optional[Dict]:
        """提取檔案資訊"""
        try:
            # 檢查檔案是否包含總結欄位
            header_df = pd.read_csv(file_path, nrows=0)
            available_columns = header_df.columns.tolist()

            summary_cols_found = []
            for col in self.summary_columns:
                if col in available_columns:
                    summary_cols_found.append(col)

            if not summary_cols_found:
                return None

            # 提取模型和配置資訊
            model_info = self._extract_model_info(file_path, model_name)

            return {
                'file_path': str(file_path),
                'model_info': model_info,
                'summary_columns': summary_cols_found,
                'file_size': file_path.stat().st_size,
                'last_modified': file_path.stat().st_mtime
            }

        except Exception as e:
            logging.error(f"Error extracting info from {file_path}: {e}")
            return None

    def _extract_model_info(self, file_path: Path, model_name: str = None) -> Dict:
        """提取模型資訊"""
        filename = file_path.stem

        # 從路徑提取模型名稱
        if model_name is None:
            path_parts = file_path.parts
            for part in reversed(path_parts):
                if any(model in part for model in ['gpt', 'o3', 'o4']):
                    model_name = part
                    break

        info = {
            'base_model': model_name or 'unknown',
            'reasoning_effort': None,
            'verbosity': None,
            'full_identifier': filename
        }

        # 提取 reasoning effort 和 verbosity
        reason_pattern = r'reason_(\w+)_verbosity_(\w+)'
        reason_match = re.search(reason_pattern, filename)
        if reason_match:
            info['reasoning_effort'] = reason_match.group(1)
            info['verbosity'] = reason_match.group(2)

        return info

class SummaryComparator:
    """總結文本比較器"""

    def __init__(self):
        self.scanner = SummaryFileScanner()
        self.similarity_calc = TextSimilarityCalculator()

    def compare_from_root(self, root_dir: str, **kwargs) -> Dict:
        """從根目錄比較總結文本"""
        files_info = self.scanner.scan_root_directory(root_dir)
        return self._perform_comparison(files_info, **kwargs)

    def compare_specific_files(self, file_paths: List[str], summary_columns: List[str] = None, **kwargs) -> Dict:
        """比較指定檔案的總結文本"""
        files_info = self.scanner.scan_specific_files(file_paths)

        # 如果指定了總結欄位，過濾檔案
        if summary_columns:
            filtered_files = []
            for info in files_info:
                if any(col in info['summary_columns'] for col in summary_columns):
                    filtered_files.append(info)
            files_info = filtered_files

        return self._perform_comparison(files_info, target_columns=summary_columns, **kwargs)

    def _perform_comparison(self, files_info: List[Dict],
                          target_columns: List[str] = None,
                          sample_size: int = None) -> Dict:
        """執行比較分析"""
        if not files_info:
            raise ValueError("No files with summary columns found")

        logging.info(f"Starting comparison of {len(files_info)} files")

        # 載入資料
        datasets = {}
        for file_info in files_info:
            dataset = self._load_summary_data(file_info, target_columns, sample_size)
            if dataset is not None and not dataset.empty:
                model_id = self._generate_model_id(file_info)
                datasets[model_id] = {
                    'data': dataset,
                    'info': file_info
                }

        if len(datasets) < 1:
            raise ValueError("No valid datasets loaded")

        logging.info(f"Successfully loaded {len(datasets)} datasets")

        # 執行分析
        analysis = self._analyze_summaries(datasets)
        return analysis

    def _load_summary_data(self, file_info: Dict, target_columns: List[str] = None, sample_size: int = None) -> Optional[pd.DataFrame]:
        """載入總結數據"""
        try:
            file_path = file_info['file_path']
            logging.info(f"Loading summary data from {file_path}")

            # 確定要讀取的欄位
            cols_to_read = ['Date', 'Stock_symbol']

            # 選擇總結欄位
            summary_cols = file_info['summary_columns']
            if target_columns:
                summary_cols = [col for col in summary_cols if col in target_columns]

            cols_to_read.extend(summary_cols)

            # 可能存在的索引欄位
            potential_index_cols = ['Unnamed: 0.1', 'Unnamed: 0']

            # 檢查實際存在的欄位
            header_df = pd.read_csv(file_path, nrows=0)
            available_columns = header_df.columns.tolist()

            # 添加存在的索引欄位
            index_col = None
            for col in potential_index_cols:
                if col in available_columns:
                    index_col = col
                    cols_to_read.insert(0, col)
                    break

            # 只保留存在的欄位
            final_cols = [col for col in cols_to_read if col in available_columns]

            # 讀取資料
            df = pd.read_csv(file_path, usecols=final_cols)

            # 設置索引
            if index_col and index_col in df.columns:
                df = df.set_index(index_col)

            # 抽樣（如果指定）
            if sample_size and len(df) > sample_size:
                df = df.sample(n=sample_size, random_state=42)

            logging.info(f"Loaded {len(df)} records from {file_path}")
            return df

        except Exception as e:
            logging.error(f"Error loading {file_path}: {e}")
            return None

    def _generate_model_id(self, file_info: Dict) -> str:
        """生成模型標識符"""
        model_info = file_info['model_info']

        base = model_info['base_model']

        # 添加配置資訊
        if model_info.get('reasoning_effort'):
            base += f"_r{model_info['reasoning_effort']}"

        if model_info.get('verbosity'):
            base += f"_v{model_info['verbosity']}"

        return base

    def _analyze_summaries(self, datasets: Dict) -> Dict:
        """分析總結文本"""
        analysis = {
            'summary': {
                'total_files': len(datasets),
                'total_records': 0,
                'analysis_timestamp': datetime.now().isoformat()
            },
            'by_model': {},
            'by_column': {},
            'cross_model_comparison': {},
            'text_quality_analysis': {},
            'files_analyzed': []
        }

        # 分析每個數據集
        for model_id, dataset_info in datasets.items():
            df = dataset_info['data']
            file_info = dataset_info['info']

            model_analysis = self._analyze_single_dataset(df, file_info)
            analysis['by_model'][model_id] = model_analysis
            analysis['summary']['total_records'] += model_analysis['record_count']

            # 記錄檔案資訊
            analysis['files_analyzed'].append({
                'model_id': model_id,
                'file_path': file_info['file_path'],
                'summary_columns': file_info['summary_columns'],
                'records': model_analysis['record_count']
            })

        # 跨模型比較（如果有多個模型）
        if len(datasets) > 1:
            analysis['cross_model_comparison'] = self._cross_model_analysis(datasets)

        return analysis

    def _analyze_single_dataset(self, df: pd.DataFrame, file_info: Dict) -> Dict:
        """分析單個數據集"""
        summary_cols = [col for col in file_info['summary_columns'] if col in df.columns]

        analysis = {
            'record_count': len(df),
            'summary_columns_analyzed': summary_cols,
            'column_analysis': {}
        }

        for col in summary_cols:
            col_analysis = self._analyze_summary_column(df[col])
            analysis['column_analysis'][col] = col_analysis

        return analysis

    def _analyze_summary_column(self, series: pd.Series) -> Dict:
        """分析單個總結欄位"""
        # 基本統計
        total_count = len(series)
        non_null_count = series.notna().sum()
        null_count = series.isna().sum()

        # 文本長度統計
        lengths = series.dropna().astype(str).str.len()

        # 空字串檢查
        empty_strings = (series.astype(str).str.strip() == '').sum()

        # 重複內容檢查
        duplicates = series.dropna().duplicated().sum()
        unique_count = series.dropna().nunique()

        # 詞彙統計
        all_text = ' '.join(series.dropna().astype(str).tolist())
        word_count = len(all_text.split()) if all_text else 0
        unique_words = len(set(all_text.lower().split())) if all_text else 0

        analysis = {
            'basic_stats': {
                'total_records': int(total_count),
                'non_null_records': int(non_null_count),
                'null_records': int(null_count),
                'null_percentage': float(null_count / total_count * 100) if total_count > 0 else 0.0,
                'empty_strings': int(empty_strings),
                'duplicates': int(duplicates),
                'unique_summaries': int(unique_count)
            },
            'length_stats': {
                'mean_length': float(lengths.mean()) if len(lengths) > 0 else 0.0,
                'median_length': float(lengths.median()) if len(lengths) > 0 else 0.0,
                'min_length': int(lengths.min()) if len(lengths) > 0 else 0,
                'max_length': int(lengths.max()) if len(lengths) > 0 else 0,
                'std_length': float(lengths.std()) if len(lengths) > 0 else 0.0
            },
            'vocabulary_stats': {
                'total_words': word_count,
                'unique_words': unique_words,
                'vocabulary_richness': float(unique_words / word_count) if word_count > 0 else 0.0
            }
        }

        return analysis

    def _cross_model_analysis(self, datasets: Dict) -> Dict:
        """跨模型分析"""
        analysis = {
            'pairwise_comparisons': {},
            'overall_similarity': {}
        }

        # 找到所有數據集的共同索引
        common_indices = None
        for model_id, dataset_info in datasets.items():
            df = dataset_info['data']
            if common_indices is None:
                common_indices = set(df.index)
            else:
                common_indices &= set(df.index)

        if not common_indices:
            logging.warning("No common indices found for cross-model comparison")
            return analysis

        common_indices = sorted(list(common_indices))
        logging.info(f"Found {len(common_indices)} common records for comparison")

        # 進行兩兩比較
        model_ids = list(datasets.keys())
        for i, model1 in enumerate(model_ids):
            for j, model2 in enumerate(model_ids):
                if i >= j:
                    continue

                pair_key = f"{model1}_vs_{model2}"
                pair_analysis = self._compare_model_pair(
                    datasets[model1], datasets[model2], common_indices
                )
                if pair_analysis:
                    analysis['pairwise_comparisons'][pair_key] = pair_analysis

        return analysis

    def _compare_model_pair(self, dataset1: Dict, dataset2: Dict, common_indices: List) -> Optional[Dict]:
        """比較兩個模型的輸出"""
        df1 = dataset1['data'].loc[common_indices]
        df2 = dataset2['data'].loc[common_indices]

        info1 = dataset1['info']
        info2 = dataset2['info']

        # 找到可比較的欄位
        cols1 = info1['summary_columns']
        cols2 = info2['summary_columns']

        comparison_results = {}

        for col1 in cols1:
            for col2 in cols2:
                if col1 in df1.columns and col2 in df2.columns:
                    pair_key = f"{col1}_vs_{col2}"
                    comparison = self._compare_text_columns(df1[col1], df2[col2])
                    comparison_results[pair_key] = comparison

        if not comparison_results:
            return None

        return {
            'model1_info': info1['model_info'],
            'model2_info': info2['model_info'],
            'common_records': len(common_indices),
            'column_comparisons': comparison_results
        }

    def _compare_text_columns(self, series1: pd.Series, series2: pd.Series) -> Dict:
        """比較兩個文本欄位"""
        # 確保索引一致
        aligned_data = pd.DataFrame({
            'text1': series1,
            'text2': series2
        }).dropna()

        if len(aligned_data) == 0:
            return {'error': 'No valid pairs for comparison'}

        # 計算各種相似度指標
        similarities = {
            'jaccard': [],
            'word_overlap': [],
            'length_ratio': [],
            'cosine': [],
            'bleu': []
        }

        for _, row in aligned_data.iterrows():
            text1, text2 = row['text1'], row['text2']

            similarities['jaccard'].append(
                self.similarity_calc.jaccard_similarity(text1, text2)
            )
            similarities['word_overlap'].append(
                self.similarity_calc.word_overlap_ratio(text1, text2)
            )
            similarities['length_ratio'].append(
                self.similarity_calc.length_ratio(text1, text2)
            )
            similarities['cosine'].append(
                self.similarity_calc.cosine_similarity_score(text1, text2)
            )
            similarities['bleu'].append(
                self.similarity_calc.simple_bleu_score(text1, text2)
            )

        # 計算統計量
        stats = {}
        for metric, values in similarities.items():
            if values:
                stats[metric] = {
                    'mean': float(np.mean(values)),
                    'median': float(np.median(values)),
                    'std': float(np.std(values)),
                    'min': float(np.min(values)),
                    'max': float(np.max(values))
                }

        return {
            'valid_pairs': len(aligned_data),
            'similarity_metrics': stats
        }

def print_summary_analysis(analysis: Dict):
    """打印總結分析結果"""
    print("\n" + "="*80)
    print("SUMMARY TEXT COMPARISON ANALYSIS")
    print("="*80)

    summary = analysis['summary']
    print(f"Total files analyzed: {summary['total_files']}")
    print(f"Total records: {summary['total_records']:,}")

    # 按模型分析
    print("\n📊 Analysis by Model:")
    print("-" * 60)
    for model_id, model_analysis in analysis['by_model'].items():
        print(f"\n{model_id}:")
        print(f"  Records: {model_analysis['record_count']:,}")
        print(f"  Summary columns: {', '.join(model_analysis['summary_columns_analyzed'])}")

        for col, col_analysis in model_analysis['column_analysis'].items():
            basic = col_analysis['basic_stats']
            length = col_analysis['length_stats']
            vocab = col_analysis['vocabulary_stats']

            print(f"\n  {col}:")
            print(f"    Valid summaries: {basic['non_null_records']:,} ({100-basic['null_percentage']:.1f}%)")
            print(f"    Avg length: {length['mean_length']:.1f} chars")
            print(f"    Length range: {length['min_length']}-{length['max_length']}")
            print(f"    Unique summaries: {basic['unique_summaries']:,}")
            print(f"    Vocabulary richness: {vocab['vocabulary_richness']:.3f}")

    # 跨模型比較
    if 'cross_model_comparison' in analysis and analysis['cross_model_comparison'].get('pairwise_comparisons'):
        print("\n🔗 Cross-Model Similarity Analysis:")
        print("-" * 60)

        for pair_key, pair_analysis in analysis['cross_model_comparison']['pairwise_comparisons'].items():
            print(f"\n{pair_key.replace('_vs_', ' ↔ ')}:")
            print(f"  Common records: {pair_analysis['common_records']:,}")

            for col_pair, comparison in pair_analysis['column_comparisons'].items():
                if 'similarity_metrics' in comparison:
                    metrics = comparison['similarity_metrics']
                    print(f"\n  {col_pair}:")
                    if 'jaccard' in metrics:
                        print(f"    Jaccard similarity: {metrics['jaccard']['mean']:.3f} ± {metrics['jaccard']['std']:.3f}")
                    if 'word_overlap' in metrics:
                        print(f"    Word overlap: {metrics['word_overlap']['mean']:.3f} ± {metrics['word_overlap']['std']:.3f}")
                    if 'length_ratio' in metrics:
                        print(f"    Length ratio: {metrics['length_ratio']['mean']:.3f} ± {metrics['length_ratio']['std']:.3f}")
                    if SKLEARN_AVAILABLE and 'cosine' in metrics:
                        print(f"    Cosine similarity: {metrics['cosine']['mean']:.3f} ± {metrics['cosine']['std']:.3f}")

def main():
    parser = argparse.ArgumentParser(description="Summary Text Comparison Tool")

    # 輸入模式選擇
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--root-dir',
                           help='Root directory to scan (e.g., /mnt/md0/finrl)')
    input_group.add_argument('--files', nargs='+',
                           help='Specific files to compare')

    parser.add_argument('--columns', nargs='+',
                       help='Specific summary columns to compare (e.g., o3_summary gpt_5_summary)')
    parser.add_argument('--output', required=True,
                       help='Output JSON file for analysis results')
    parser.add_argument('--sample-size', type=int,
                       help='Sample size for analysis (for large files)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    setup_logging(args.verbose)

    try:
        # 創建比較器
        comparator = SummaryComparator()

        # 執行比較
        if args.root_dir:
            analysis = comparator.compare_from_root(
                args.root_dir,
                sample_size=args.sample_size
            )
        else:
            analysis = comparator.compare_specific_files(
                args.files,
                summary_columns=args.columns,
                sample_size=args.sample_size
            )

        # 保存結果
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
        logging.info(f"Summary comparison analysis saved to {args.output}")

        # 顯示結果
        print_summary_analysis(analysis)

    except Exception as e:
        logging.error(f"Error during analysis: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()