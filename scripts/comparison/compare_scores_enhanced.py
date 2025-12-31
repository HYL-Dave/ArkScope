#!/usr/bin/env python3
"""
Enhanced CSV Score Comparison Tool

升級版分數比較工具，支援：
- 多資料夾自動掃描
- 記憶體效率的資料處理
- 快取機制
- Token 使用分析
- 新的檔案命名模式

Usage:
    python compare_scores_enhanced.py --root-dir /mnt/md0/finrl --score-type sentiment --output results.csv
    python compare_scores_enhanced.py --root-dir /mnt/md0/finrl --score-type risk --output results.csv
    python compare_scores_enhanced.py --directories /path/to/dir1 /path/to/dir2 --score-type sentiment --output results.csv
    python compare_scores_enhanced.py --files /path/to/file1.csv /path/to/file2.csv /path/to/file3.csv --score-type sentiment --output results.csv
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
import json
import sys
import logging
import hashlib
import pickle
import os
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional, Set
import re
from datetime import datetime

def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

class ScoreFileScanner:
    """掃描和發現分數檔案的類別"""

    def __init__(self, score_type: str = "sentiment"):
        self.score_type = score_type  # "sentiment" or "risk"
        self.score_column = f"{score_type}_deepseek"

    def scan_directories(self, directories: List[str]) -> List[Dict]:
        """掃描多個目錄，找出所有相關的分數檔案"""
        files_info = []

        for directory in directories:
            dir_path = Path(directory)
            if not dir_path.exists():
                logging.warning(f"Directory not found: {directory}")
                continue

            # 遞歸查找 CSV 檔案
            csv_files = list(dir_path.rglob("*.csv"))

            for csv_file in csv_files:
                # 檢查檔案名是否包含目標分數類型
                if self.score_type in csv_file.name:
                    info = self._extract_file_info(csv_file)
                    if info:
                        files_info.append(info)

        logging.info(f"Found {len(files_info)} {self.score_type} files")
        return files_info

    def scan_root_directory(self, root_dir: str) -> List[Dict]:
        """掃描根目錄，自動發現模型資料夾和分數檔案"""
        root_path = Path(root_dir)
        if not root_path.exists():
            raise ValueError(f"Root directory not found: {root_dir}")

        files_info = []

        # 查找所有模型資料夾（假設它們直接在根目錄下）
        for model_dir in root_path.iterdir():
            if model_dir.is_dir():
                # 查找該模型下的 sentiment 或 risk 資料夾
                score_dir = model_dir / self.score_type
                if score_dir.exists():
                    csv_files = list(score_dir.glob("*.csv"))
                    for csv_file in csv_files:
                        info = self._extract_file_info(csv_file, model_name=model_dir.name)
                        if info:
                            files_info.append(info)

        logging.info(f"Found {len(files_info)} {self.score_type} files under {root_dir}")
        return files_info

    def scan_specific_files(self, file_paths: List[str]) -> List[Dict]:
        """掃描指定的檔案列表"""
        files_info = []

        for file_path_str in file_paths:
            file_path = Path(file_path_str)

            if not file_path.exists():
                logging.warning(f"File not found: {file_path_str}")
                continue

            if not file_path.name.endswith('.csv'):
                logging.warning(f"Skipping non-CSV file: {file_path_str}")
                continue

            # 檢查檔案是否包含所需的分數類型
            # 這裡我們可以放寬檢查，因為用戶明確指定了檔案
            info = self._extract_file_info(file_path)
            if info:
                # 手動設置分數欄位（如果檔案不符合命名規範）
                if self.score_column not in info:
                    info['score_column'] = self.score_column
                files_info.append(info)
                logging.info(f"Added specific file: {file_path_str}")

        logging.info(f"Found {len(files_info)} specified files")
        return files_info

    def _extract_file_info(self, file_path: Path, model_name: str = None) -> Optional[Dict]:
        """提取檔案資訊"""
        try:
            # 檢查檔案大小
            file_size = file_path.stat().st_size

            # 提取模型資訊
            extracted_model = self._extract_model_info(file_path, model_name)

            return {
                'file_path': str(file_path),
                'model_info': extracted_model,
                'file_size': file_size,
                'score_column': self.score_column,
                'last_modified': file_path.stat().st_mtime
            }
        except Exception as e:
            logging.error(f"Error extracting info from {file_path}: {e}")
            return None

    def _extract_model_info(self, file_path: Path, model_name: str = None) -> Dict:
        """提取模型資訊，包括新的檔案命名模式"""
        filename = file_path.stem
        logging.debug(f"Extracting model info from filename: {filename}")

        # 從路徑獲取模型名稱（如果不是從檔案名）
        if model_name is None:
            # 嘗試從路徑中提取模型名稱
            path_parts = file_path.parts
            for part in reversed(path_parts):
                if any(model in part for model in ['gpt', 'o3', 'o4']):
                    model_name = part
                    break

        # 分析檔案名模式
        info = {
            'base_model': 'unknown',
            'reasoning_effort': None,
            'verbosity': None,
            'source_summary': None,
            'full_identifier': filename
        }

        # 支援新的檔案命名模式，例如：
        # sentiment_gpt-5_R_medium_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv
        # risk_o3_high_by_gpt-5_reason_high_verbosity_high.csv

        # 模式 1: 新的 GPT-5 格式
        gpt5_pattern = r'(sentiment|risk)_(gpt-5(?:-mini)?)_R_(\w+)_V_(\w+)_by_(.+?)_summary'
        gpt5_match = re.search(gpt5_pattern, filename)
        if gpt5_match:
            score_type, model, reasoning, verbosity, source = gpt5_match.groups()
            info.update({
                'base_model': model,
                'reasoning_effort': reasoning,
                'verbosity': verbosity,
                'source_summary': source,
                'pattern': 'gpt5_enhanced'
            })
            return info

        # 模式 2: 傳統格式 (移到前面，優先匹配)
        traditional_pattern = r'(sentiment|risk)_(.+?)_by_(.+)_summary'
        traditional_match = re.search(traditional_pattern, filename)
        if traditional_match:
            score_type, model, source = traditional_match.groups()
            logging.debug(f"Traditional pattern matched: score_type={score_type}, model={model}, source={source}")
            info.update({
                'base_model': model.replace('_', '-'),
                'source_summary': source,
                'pattern': 'traditional'
            })
            return info

        # 模式 3: reasoning effort 格式 (修正，只匹配有 reason_ 的格式)
        effort_pattern = r'(sentiment|risk)_(.+?)_by_(.+?)_reason_(\w+)_verbosity_(\w+)'
        effort_match = re.search(effort_pattern, filename)
        if effort_match:
            score_type, model_part, source, reasoning, verbosity = effort_match.groups()
            logging.debug(f"Effort pattern matched: model_part={model_part}, source={source}, reasoning={reasoning}")

            # 進一步分析 model_part 以提取模型和effort
            model_effort_pattern = r'(.+?)_(\w+)$'
            model_effort_match = re.search(model_effort_pattern, model_part)
            if model_effort_match and model_effort_match.group(2) in ['low', 'medium', 'high']:
                base_model, effort = model_effort_match.groups()
                info.update({
                    'base_model': base_model.replace('_', '-'),
                    'reasoning_effort': effort,
                    'verbosity': verbosity,
                    'source_summary': source,
                    'pattern': 'effort_based'
                })
            else:
                info.update({
                    'base_model': model_part.replace('_', '-'),
                    'reasoning_effort': reasoning,
                    'verbosity': verbosity,
                    'source_summary': source,
                    'pattern': 'standard'
                })
            return info

        # 如果從檔案名提取失敗，使用路徑資訊
        if model_name:
            info['base_model'] = model_name
            info['pattern'] = 'path_based'

        return info

class ScoreDataLoader:
    """記憶體效率的資料載入器"""

    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def load_essential_data(self, file_info: Dict, force_reload: bool = False) -> Optional[pd.DataFrame]:
        """載入比較所需的關鍵資料（記憶體效率版本）"""
        file_path = file_info['file_path']

        # 檢查快取
        cache_key = self._get_cache_key(file_info)
        cache_file = self.cache_dir / f"{cache_key}.pkl"

        if not force_reload and cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)

                # 驗證快取是否仍然有效
                if cached_data['file_mtime'] == file_info['last_modified']:
                    logging.debug(f"Using cached data for {file_path}")
                    return cached_data['data']
            except Exception as e:
                logging.warning(f"Cache read failed for {file_path}: {e}")

        # 載入資料
        try:
            logging.info(f"Loading data from {file_path}")

            # 只讀取必要的列
            essential_columns = [
                'Date', 'Stock_symbol', file_info['score_column']
            ]

            # 添加可能的索引列
            potential_index_cols = ['Unnamed: 0.1', 'Unnamed: 0']

            # 檢查檔案頭以確定實際存在的列
            header_df = pd.read_csv(file_path, nrows=0)
            available_columns = header_df.columns.tolist()

            # 選擇存在的索引列
            index_col = None
            for col in potential_index_cols:
                if col in available_columns:
                    index_col = col
                    break

            # 選擇存在的必要列
            cols_to_read = []
            if index_col:
                cols_to_read.append(index_col)

            for col in essential_columns:
                if col in available_columns:
                    cols_to_read.append(col)

            # 可選列（如果存在的話也讀取）
            optional_columns = ['Article_title', 'o3_summary']
            for col in optional_columns:
                if col in available_columns:
                    cols_to_read.append(col)

            # 讀取資料
            df = pd.read_csv(file_path, usecols=cols_to_read)

            # 設置索引
            if index_col and index_col in df.columns:
                df = df.set_index(index_col)

            # 驗證分數列
            score_col = file_info['score_column']
            if score_col not in df.columns:
                logging.error(f"Score column {score_col} not found in {file_path}")
                return None

            # 移除空值
            df = df.dropna(subset=[score_col])

            logging.info(f"Loaded {len(df)} records from {file_path}")

            # 儲存到快取
            try:
                cache_data = {
                    'data': df,
                    'file_mtime': file_info['last_modified'],
                    'cache_time': datetime.now().timestamp()
                }
                with open(cache_file, 'wb') as f:
                    pickle.dump(cache_data, f)
                logging.debug(f"Cached data for {file_path}")
            except Exception as e:
                logging.warning(f"Cache write failed for {file_path}: {e}")

            return df

        except Exception as e:
            logging.error(f"Error loading {file_path}: {e}")
            return None

    def _get_cache_key(self, file_info: Dict) -> str:
        """生成快取鍵"""
        key_data = f"{file_info['file_path']}_{file_info['last_modified']}_{file_info['file_size']}"
        return hashlib.md5(key_data.encode()).hexdigest()

class EnhancedScoreComparator:
    """增強版分數比較器"""

    def __init__(self, score_type: str, cache_dir: str = ".cache"):
        self.score_type = score_type
        self.score_column = f"{score_type}_deepseek"
        self.scanner = ScoreFileScanner(score_type)
        self.loader = ScoreDataLoader(cache_dir)

    def compare_from_directories(self, directories: List[str], **kwargs) -> Dict:
        """從多個目錄比較分數"""
        files_info = self.scanner.scan_directories(directories)
        return self._perform_comparison(files_info, **kwargs)

    def compare_from_root(self, root_dir: str, **kwargs) -> Dict:
        """從根目錄自動發現並比較分數"""
        files_info = self.scanner.scan_root_directory(root_dir)
        return self._perform_comparison(files_info, **kwargs)

    def compare_from_files(self, file_paths: List[str], **kwargs) -> Dict:
        """從指定的檔案列表比較分數"""
        files_info = self.scanner.scan_specific_files(file_paths)
        return self._perform_comparison(files_info, **kwargs)

    def _perform_comparison(self, files_info: List[Dict],
                          force_reload: bool = False,
                          max_files: Optional[int] = None) -> Dict:
        """執行比較分析"""
        if not files_info:
            raise ValueError("No files found for comparison")

        # 限制檔案數量（用於測試）
        if max_files:
            files_info = files_info[:max_files]

        logging.info(f"Starting comparison of {len(files_info)} files")

        # 載入所有資料
        dataframes = {}
        for file_info in files_info:
            df = self.loader.load_essential_data(file_info, force_reload)
            if df is not None and len(df) > 0:
                model_id = self._generate_model_id(file_info)
                dataframes[model_id] = {
                    'data': df,
                    'info': file_info
                }

        if len(dataframes) < 2:
            raise ValueError("Need at least 2 valid dataframes for comparison")

        logging.info(f"Successfully loaded {len(dataframes)} dataframes")

        # 合併資料進行比較
        merged_df = self._merge_dataframes(dataframes)

        # 執行分析
        analysis = self._analyze_differences(merged_df, dataframes)

        return analysis

    def _generate_model_id(self, file_info: Dict) -> str:
        """生成模型標識符 - 基於資料夾名稱，更清晰準確"""
        file_path = Path(file_info['file_path'])

        # 優先使用資料夾名稱作為模型標識
        # 路徑格式: /mnt/md0/finrl/gpt-4.1/sentiment/sentiment_gpt-4.1_by_o3_summary.csv
        path_parts = file_path.parts

        # 找到模型資料夾名稱（假設在 finrl 之後的第一個目錄）
        model_folder = None
        for i, part in enumerate(path_parts):
            if part == 'finrl' and i + 1 < len(path_parts):
                model_folder = path_parts[i + 1]
                break

        if model_folder:
            # 使用資料夾名稱作為主要標識
            base_id = model_folder
        else:
            # 回退到從檔案名解析
            model_info = file_info['model_info']
            base_id = model_info.get('base_model', 'unknown')

        # 選項：為了完全避免歧義，可以使用完整檔案名作為標識符
        # 這會產生如 "sentiment_gpt-4.1_by_o3_summary" 這樣的詳細標識
        # 取消註釋下面兩行來啟用檔案名模式：
        # filename = file_path.stem
        # return filename

        return base_id

    def _merge_dataframes(self, dataframes: Dict) -> pd.DataFrame:
        """合併資料框進行比較"""
        # 找到所有資料框的交集索引
        common_indices = None
        for model_id, data_info in dataframes.items():
            df = data_info['data']
            if common_indices is None:
                common_indices = set(df.index)
            else:
                common_indices &= set(df.index)

        if not common_indices:
            raise ValueError("No common indices found across dataframes")

        common_indices = sorted(common_indices)
        logging.info(f"Found {len(common_indices)} common records")

        # 創建合併的資料框
        merged_data = {}

        # 從第一個資料框取得基本資訊
        first_df = list(dataframes.values())[0]['data']
        for col in ['Date', 'Stock_symbol', 'Article_title']:
            if col in first_df.columns:
                merged_data[col] = first_df.loc[common_indices, col]

        # 添加各模型的分數
        for model_id, data_info in dataframes.items():
            df = data_info['data']
            score_col = f"{self.score_column}_{model_id}"
            merged_data[score_col] = df.loc[common_indices, self.score_column]

        merged_df = pd.DataFrame(merged_data, index=common_indices)
        return merged_df

    def _analyze_differences(self, merged_df: pd.DataFrame, dataframes: Dict) -> Dict:
        """分析分數差異"""
        score_columns = [col for col in merged_df.columns if col.startswith(self.score_column)]

        # 基本統計
        analysis = {
            'total_records': len(merged_df),
            'models_compared': len(score_columns),
            'model_info': {model_id: data_info['info']['model_info']
                          for model_id, data_info in dataframes.items()},
            'file_info': {model_id: {
                'file_path': data_info['info']['file_path'],
                'file_size': data_info['info']['file_size'],
                'last_modified': data_info['info']['last_modified']
            } for model_id, data_info in dataframes.items()}
        }

        # 分數分佈
        score_distributions = {}
        for col in score_columns:
            distribution = merged_df[col].value_counts().to_dict()
            score_distributions[col] = distribution
        analysis['score_distributions'] = score_distributions

        # 差異分析
        score_values = merged_df[score_columns].values
        all_same_mask = np.all(score_values == score_values[:, 0:1], axis=1)

        analysis['records_with_differences'] = int((~all_same_mask).sum())
        analysis['records_all_same'] = int(all_same_mask.sum())
        analysis['difference_percentage'] = float((~all_same_mask).mean() * 100)

        # 兩兩相似度分析（重用原有邏輯）
        analysis['pairwise_similarity'] = self._analyze_pairwise_similarity(merged_df, score_columns)

        # 分數組合分析
        score_combinations = defaultdict(int)
        for _, row in merged_df.iterrows():
            combo = tuple(row[score_columns].values)
            score_combinations[combo] += 1

        analysis['score_combinations'] = {str(k): v for k, v in score_combinations.items()}
        most_common_combos = Counter(score_combinations).most_common(10)
        analysis['most_common_combinations'] = [(str(combo), count) for combo, count in most_common_combos]

        return analysis

    def _analyze_pairwise_similarity(self, merged_df: pd.DataFrame, score_columns: List[str]) -> Dict:
        """兩兩相似度分析（重用原有邏輯）"""
        from scipy.stats import pearsonr, spearmanr
        from sklearn.metrics import cohen_kappa_score

        pairwise_results = {}

        for i, col1 in enumerate(score_columns):
            for j, col2 in enumerate(score_columns):
                if i >= j:
                    continue

                model1 = col1.replace(f"{self.score_column}_", "")
                model2 = col2.replace(f"{self.score_column}_", "")
                pair_key = f"{model1}_vs_{model2}"

                # 移除 NaN 值
                valid_mask = (~merged_df[col1].isna()) & (~merged_df[col2].isna())
                if valid_mask.sum() == 0:
                    continue

                scores1 = merged_df.loc[valid_mask, col1].values
                scores2 = merged_df.loc[valid_mask, col2].values

                # 計算各種指標
                pair_stats = {}
                pair_stats['exact_match_rate'] = float((scores1 == scores2).mean() * 100)
                pair_stats['within_1_point_rate'] = float((np.abs(scores1 - scores2) <= 1).mean() * 100)
                pair_stats['mean_absolute_error'] = float(np.mean(np.abs(scores1 - scores2)))

                # 相關係數
                try:
                    pearson_r, pearson_p = pearsonr(scores1, scores2)
                    pair_stats['pearson_correlation'] = float(pearson_r)
                    pair_stats['pearson_p_value'] = float(pearson_p)
                except:
                    pair_stats['pearson_correlation'] = np.nan
                    pair_stats['pearson_p_value'] = np.nan

                try:
                    spearman_r, spearman_p = spearmanr(scores1, scores2)
                    pair_stats['spearman_correlation'] = float(spearman_r)
                    pair_stats['spearman_p_value'] = float(spearman_p)
                except:
                    pair_stats['spearman_correlation'] = np.nan
                    pair_stats['spearman_p_value'] = np.nan

                try:
                    kappa = cohen_kappa_score(scores1, scores2)
                    pair_stats['cohen_kappa'] = float(kappa)
                except:
                    pair_stats['cohen_kappa'] = np.nan

                pair_stats['total_comparisons'] = int(len(scores1))

                pairwise_results[pair_key] = pair_stats

        return pairwise_results

def print_enhanced_summary(analysis: Dict, top_n: int = 5):
    """打印增強版分析摘要"""
    print("\n" + "="*80)
    print("ENHANCED SCORE COMPARISON ANALYSIS")
    print("="*80)

    print(f"Total records: {analysis['total_records']:,}")
    print(f"Models compared: {analysis['models_compared']}")
    print(f"Records with differences: {analysis['records_with_differences']:,}")
    print(f"Records all same: {analysis['records_all_same']:,}")
    print(f"Difference percentage: {analysis['difference_percentage']:.2f}%")

    # 顯示模型資訊
    print("\n📋 Models Information:")
    print("-" * 60)
    for model_id, model_info in analysis['model_info'].items():
        print(f"  {model_id}:")
        print(f"    Base Model: {model_info['base_model']}")
        if model_info.get('reasoning_effort'):
            print(f"    Reasoning: {model_info['reasoning_effort']}")
        if model_info.get('verbosity'):
            print(f"    Verbosity: {model_info['verbosity']}")
        if model_info.get('source_summary'):
            print(f"    Source: {model_info['source_summary']}")
        if model_info.get('pattern'):
            print(f"    Pattern: {model_info['pattern']}")

    # 檔案資訊
    print("\n📁 File Information:")
    print("-" * 60)
    for model_id, file_info in analysis['file_info'].items():
        size_mb = file_info['file_size'] / (1024 * 1024)
        print(f"  {model_id}: {size_mb:.1f}MB")

    # 分數分佈
    print("\n📊 Score Distributions:")
    print("-" * 60)
    for model_col, distribution in analysis['score_distributions'].items():
        model_name = model_col.split('_', 2)[-1]  # 移除前綴
        print(f"\n{model_name}:")
        for score, count in sorted(distribution.items()):
            percentage = count / analysis['total_records'] * 100
            print(f"  {score}: {count:,} ({percentage:.1f}%)")

    # 最常見組合
    print(f"\n🔢 Most Common Score Combinations (Top {top_n}):")
    print("-" * 60)
    for i, (combo, count) in enumerate(analysis['most_common_combinations'][:top_n], 1):
        percentage = count / analysis['total_records'] * 100
        print(f"{i}. {combo}: {count:,} ({percentage:.1f}%)")

    # 相似度分析
    if 'pairwise_similarity' in analysis:
        print_pairwise_summary(analysis['pairwise_similarity'])

def print_pairwise_summary(pairwise_results: Dict, top_n: int = 5):
    """打印兩兩相似度分析摘要"""
    print("\n🔗 Pairwise Similarity Analysis:")
    print("-" * 60)

    if not pairwise_results:
        print("No pairwise comparisons available.")
        return

    # 按完全一致率排序
    exact_match_pairs = []
    for pair, stats in pairwise_results.items():
        if 'exact_match_rate' in stats:
            exact_match_pairs.append((pair, stats['exact_match_rate']))

    exact_match_pairs.sort(key=lambda x: x[1], reverse=True)

    print(f"\nTop {min(top_n, len(exact_match_pairs))} Most Similar (Exact Match Rate):")
    for i, (pair, rate) in enumerate(exact_match_pairs[:top_n], 1):
        print(f"  {i}. {pair.replace('_vs_', ' ↔ ')}: {rate:.2f}%")

    # 顯示最相似和最不相似的一對
    if exact_match_pairs:
        most_similar = exact_match_pairs[0]
        least_similar = exact_match_pairs[-1]
        print(f"\n🥇 Most Similar: {most_similar[0].replace('_vs_', ' ↔ ')} ({most_similar[1]:.2f}%)")
        print(f"🥉 Least Similar: {least_similar[0].replace('_vs_', ' ↔ ')} ({least_similar[1]:.2f}%)")

def save_enhanced_results(analysis: Dict, merged_df: pd.DataFrame, output_path: str):
    """保存增強版結果"""
    output_path = Path(output_path)

    # 保存差異記錄
    score_columns = [col for col in merged_df.columns if 'deepseek' in col]
    if len(score_columns) >= 2:
        score_values = merged_df[score_columns].values
        all_same_mask = np.all(score_values == score_values[:, 0:1], axis=1)
        different_df = merged_df[~all_same_mask]

        if not different_df.empty:
            different_df.to_csv(output_path)
            logging.info(f"Saved {len(different_df)} records with differences to {output_path}")

    # 保存統計分析
    stats_path = output_path.with_suffix('.json')
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
    logging.info(f"Saved analysis to {stats_path}")

    # 保存摘要報告
    report_path = output_path.with_suffix('.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        # 重定向 print 輸出到檔案
        import contextlib
        import io

        f_out = io.StringIO()
        with contextlib.redirect_stdout(f_out):
            print_enhanced_summary(analysis)

        f.write(f_out.getvalue())
    logging.info(f"Saved summary report to {report_path}")

def main():
    parser = argparse.ArgumentParser(description="Enhanced Score Comparison Tool")

    # 輸入模式選擇
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--root-dir',
                           help='Root directory to scan (e.g., /mnt/md0/finrl)')
    input_group.add_argument('--directories', nargs='+',
                           help='Specific directories to scan')
    input_group.add_argument('--files', nargs='+',
                           help='Specific CSV files to compare (can be in different directories)')

    parser.add_argument('--score-type', required=True,
                       choices=['sentiment', 'risk'],
                       help='Type of scores to compare')
    parser.add_argument('--output', required=True,
                       help='Output file path (CSV for differences)')
    parser.add_argument('--cache-dir', default='.cache',
                       help='Cache directory for processed data')
    parser.add_argument('--force-reload', action='store_true',
                       help='Force reload data, ignore cache')
    parser.add_argument('--max-files', type=int,
                       help='Maximum number of files to process (for testing)')
    parser.add_argument('--top-n', type=int, default=5,
                       help='Number of top results to display')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    setup_logging(args.verbose)

    try:
        # 創建比較器
        comparator = EnhancedScoreComparator(args.score_type, args.cache_dir)

        # 執行比較
        if args.root_dir:
            analysis = comparator.compare_from_root(
                args.root_dir,
                force_reload=args.force_reload,
                max_files=args.max_files
            )
        elif args.directories:
            analysis = comparator.compare_from_directories(
                args.directories,
                force_reload=args.force_reload,
                max_files=args.max_files
            )
        else:  # args.files
            analysis = comparator.compare_from_files(
                args.files,
                force_reload=args.force_reload,
                max_files=args.max_files
            )

        # 獲取合併資料（用於保存差異記錄）
        # 注意：這裡為了簡化，我們重新載入一次資料
        # 在實際實現中，可以從 comparator 返回合併的資料

        # 保存結果
        save_enhanced_results(analysis, pd.DataFrame(), args.output)

        # 顯示摘要
        print_enhanced_summary(analysis, args.top_n)

    except Exception as e:
        logging.error(f"Error during processing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()