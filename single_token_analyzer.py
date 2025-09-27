#!/usr/bin/env python3
"""
Single File Token Analysis Tool

專門分析單一 CSV 檔案的 token 使用情況和成本估算。
設計原則：
- 只處理指定的單一檔案，不自動掃描
- 提供詳細的統計分析（平均值、中位數、分佈等）
- 準確的成本估算基於 OpenAI 最新價格
- 支援不同模型的自動識別和價格匹配
- 輸出格式友好，適合進一步分析

Features:
- 單檔案深度分析
- 自動模型識別和價格匹配
- 詳細統計指標（均值、中位數、標準差、分位數）
- 成本估算和每記錄成本分析
- 靈活的輸出格式（JSON/TXT）
- 錯誤處理和數據驗證

Usage:
    # 分析單一檔案
    python single_token_analyzer.py --file model_results.csv

    # 指定輸出格式和模型
    python single_token_analyzer.py --file results.csv --output analysis.json --model gpt-4.1

    # 分析多個檔案（分別處理）
    python single_token_analyzer.py --files file1.csv file2.csv file3.csv --output-dir ./analysis/

Author: Claude Code
Date: 2025-09-27
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
import json
import logging
from typing import Dict, List, Optional, Union
import re
from datetime import datetime
import sys

def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

class SingleTokenAnalyzer:
    """
    單檔案 Token 使用分析器

    專門分析單一 CSV 檔案中的 token 使用情況，提供詳細統計和成本估算。
    不會自動掃描或合併多個檔案，確保分析結果的獨立性和準確性。
    """

    # OpenAI API 價格表 (per 1M tokens, 2025年9月最新價格)
    # 支援不同服務層級：Standard (預設) 和 Flex
    TOKEN_PRICES = {
        'standard': {
            # GPT-5 系列
            'gpt-5': {'input': 1.25, 'cached_input': 0.125, 'output': 10.00},
            'gpt-5-mini': {'input': 0.25, 'cached_input': 0.025, 'output': 2.00},
            'gpt-5-nano': {'input': 0.05, 'cached_input': 0.005, 'output': 0.40},

            # GPT-4.1 系列
            'gpt-4.1': {'input': 2.00, 'cached_input': 0.50, 'output': 8.00},
            'gpt-4.1-mini': {'input': 0.40, 'cached_input': 0.10, 'output': 1.60},
            'gpt-4.1-nano': {'input': 0.10, 'cached_input': 0.025, 'output': 0.40},

            # GPT-4o 系列
            'gpt-4o': {'input': 2.50, 'cached_input': 1.25, 'output': 10.00},
            'gpt-4o-mini': {'input': 0.15, 'cached_input': 0.075, 'output': 0.60},

            # o 系列推理模型
            'o1': {'input': 15.00, 'cached_input': 7.50, 'output': 60.00},
            'o1-pro': {'input': 150.00, 'output': 600.00},
            'o1-mini': {'input': 1.10, 'cached_input': 0.55, 'output': 4.40},
            'o3': {'input': 2.00, 'cached_input': 0.50, 'output': 8.00},
            'o3-pro': {'input': 20.00, 'output': 80.00},
            'o3-mini': {'input': 1.10, 'cached_input': 0.55, 'output': 4.40},
            'o4-mini': {'input': 1.10, 'cached_input': 0.275, 'output': 4.40},
            'o4-mini-deep-research': {'input': 2.00, 'cached_input': 0.50, 'output': 8.00},

            # 其他模型
            'computer-use-preview': {'input': 3.00, 'output': 12.00},
        },
        'flex': {
            # GPT-5 系列
            'gpt-5': {'input': 0.625, 'cached_input': 0.0625, 'output': 5.00},
            'gpt-5-mini': {'input': 0.125, 'cached_input': 0.0125, 'output': 1.00},
            'gpt-5-nano': {'input': 0.025, 'cached_input': 0.0025, 'output': 0.20},

            # o 系列推理模型
            'o3': {'input': 1.00, 'cached_input': 0.25, 'output': 4.00},
            'o4-mini': {'input': 0.55, 'cached_input': 0.138, 'output': 2.20},
        },
        'batch': {
            # GPT-5 系列
            'gpt-5': {'input': 0.625, 'cached_input': 0.0625, 'output': 5.00},
            'gpt-5-mini': {'input': 0.125, 'cached_input': 0.0125, 'output': 1.00},
            'gpt-5-nano': {'input': 0.025, 'cached_input': 0.0025, 'output': 0.20},

            # GPT-4.1 系列
            'gpt-4.1': {'input': 1.00, 'output': 4.00},
            'gpt-4.1-mini': {'input': 0.20, 'output': 0.80},
            'gpt-4.1-nano': {'input': 0.05, 'output': 0.20},

            # GPT-4o 系列
            'gpt-4o': {'input': 1.25, 'output': 5.00},
            'gpt-4o-mini': {'input': 0.075, 'output': 0.30},

            # o 系列推理模型
            'o1': {'input': 7.50, 'output': 30.00},
            'o1-pro': {'input': 75.00, 'output': 300.00},
            'o1-mini': {'input': 0.55, 'output': 2.20},
            'o3': {'input': 1.00, 'output': 4.00},
            'o3-pro': {'input': 10.00, 'output': 40.00},
            'o3-mini': {'input': 0.55, 'output': 2.20},
            'o4-mini': {'input': 0.55, 'output': 2.20},
            'o4-mini-deep-research': {'input': 1.00, 'output': 4.00},

            # 其他模型
            'computer-use-preview': {'input': 1.50, 'output': 6.00},
        },
        # 通用備選價格 (Standard 層級)
        'default': {'input': 1.00, 'output': 3.00}
    }

    def __init__(self):
        """初始化分析器"""
        self.logger = logging.getLogger(__name__)

    def analyze_file(self, file_path: Union[str, Path],
                    model_hint: Optional[str] = None,
                    service_tier: str = 'standard') -> Dict:
        """
        分析單一 CSV 檔案的 token 使用情況

        Args:
            file_path: CSV 檔案路徑
            model_hint: 模型名稱提示（可選，用於價格匹配）

        Returns:
            包含完整分析結果的字典

        Raises:
            FileNotFoundError: 檔案不存在
            ValueError: 檔案格式錯誤或無 token 欄位
            pd.errors.EmptyDataError: 檔案為空
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        self.logger.info(f"Analyzing token usage in: {file_path}")

        # 檢查檔案和讀取資料
        df, token_columns = self._load_and_validate_file(file_path)

        # 提取檔案資訊
        file_info = self._extract_file_info(file_path, model_hint)

        # 計算統計分析
        statistics = self._calculate_statistics(df, token_columns)

        # 成本分析
        cost_analysis = self._calculate_cost_analysis(
            statistics, file_info['model_info'], service_tier
        )

        # 組裝完整分析結果
        analysis = {
            'analysis_timestamp': datetime.now().isoformat(),
            'file_info': file_info,
            'data_summary': {
                'total_records': len(df),
                'valid_records': len(df.dropna(subset=token_columns)),
                'token_columns_found': token_columns
            },
            'token_statistics': statistics,
            'cost_analysis': cost_analysis,
            'efficiency_metrics': self._calculate_efficiency_metrics(statistics, cost_analysis)
        }

        self.logger.info(f"Analysis complete: {len(df)} records processed")
        return analysis

    def _load_and_validate_file(self, file_path: Path) -> tuple[pd.DataFrame, List[str]]:
        """載入並驗證 CSV 檔案"""
        try:
            # 先檢查檔案頭
            header_df = pd.read_csv(file_path, nrows=0, engine='c')
            columns = header_df.columns.tolist()

            # 尋找 token 相關欄位
            token_columns = []
            possible_columns = ['prompt_tokens', 'completion_tokens', 'total_tokens',
                              'input_tokens', 'output_tokens']

            for col in possible_columns:
                if col in columns:
                    token_columns.append(col)

            if not token_columns:
                raise ValueError(f"No token columns found in {file_path}. "
                               f"Expected one of: {possible_columns}")

            # 讀取完整檔案
            df = pd.read_csv(file_path, engine='c')

            if len(df) == 0:
                raise pd.errors.EmptyDataError(f"File is empty: {file_path}")

            self.logger.debug(f"Found token columns: {token_columns}")
            self.logger.debug(f"Loaded {len(df)} records")

            return df, token_columns

        except Exception as e:
            self.logger.error(f"Error loading file {file_path}: {e}")
            raise

    def _extract_file_info(self, file_path: Path, model_hint: Optional[str] = None) -> Dict:
        """提取檔案資訊"""
        file_info = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_size_mb': file_path.stat().st_size / (1024 * 1024),
            'last_modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            'model_info': self._identify_model(file_path, model_hint),
            'task_type': self._identify_task_type(file_path)
        }
        return file_info

    def _identify_model(self, file_path: Path, model_hint: Optional[str] = None) -> Dict:
        """識別模型資訊"""
        if model_hint:
            base_model = model_hint
        else:
            # 從檔案路徑和名稱推斷模型
            path_str = str(file_path).lower()
            filename = file_path.stem.lower()

            # 檢查常見模型名稱
            model_patterns = [
                (r'gpt-5-mini', 'gpt-5-mini'),
                (r'gpt-5', 'gpt-5'),
                (r'gpt-4\.1-nano', 'gpt-4.1-nano'),
                (r'gpt-4\.1-mini', 'gpt-4.1-mini'),
                (r'gpt-4\.1', 'gpt-4.1'),
                (r'gpt-4', 'gpt-4'),
                (r'o4-mini', 'o4-mini'),
                (r'o4', 'o4'),
                (r'o3', 'o3'),
            ]

            base_model = 'unknown'
            for pattern, model_name in model_patterns:
                if re.search(pattern, path_str) or re.search(pattern, filename):
                    base_model = model_name
                    break

        # 提取推理參數
        reasoning_effort = None
        verbosity = None

        reason_pattern = r'reason[ing]*[_-](\w+)'
        verb_pattern = r'verbosity[_-](\w+)'

        filename = file_path.stem
        reason_match = re.search(reason_pattern, filename)
        verb_match = re.search(verb_pattern, filename)

        if reason_match:
            reasoning_effort = reason_match.group(1)
        if verb_match:
            verbosity = verb_match.group(1)

        return {
            'base_model': base_model,
            'reasoning_effort': reasoning_effort,
            'verbosity': verbosity,
            'full_identifier': filename,
            'pricing_model': self._get_pricing_model(base_model)
        }

    def _identify_task_type(self, file_path: Path) -> str:
        """識別任務類型"""
        filename = file_path.name.lower()
        path_str = str(file_path).lower()

        if 'sentiment' in filename or 'sentiment' in path_str:
            return 'sentiment'
        elif 'risk' in filename or 'risk' in path_str:
            return 'risk'
        elif 'summary' in filename or 'summary' in path_str:
            return 'summary'
        else:
            return 'unknown'

    def _get_pricing_model(self, model_name: str) -> str:
        """獲取適用的價格模型"""
        model_lower = model_name.lower().replace('_', '-')

        # 優先完整匹配
        for tier in ['standard', 'flex', 'batch']:
            tier_prices = self.TOKEN_PRICES.get(tier, {})
            if model_lower in tier_prices:
                return model_lower

        # 模糊匹配 - 檢查模型名稱是否包含價格表中的模型
        for tier in ['standard', 'flex', 'batch']:
            tier_prices = self.TOKEN_PRICES.get(tier, {})
            for price_model in tier_prices.keys():
                if price_model.lower() in model_lower or model_lower in price_model.lower():
                    return price_model

        return 'default'

    def _calculate_statistics(self, df: pd.DataFrame, token_columns: List[str]) -> Dict:
        """計算詳細統計分析"""
        statistics = {}

        for col in token_columns:
            if col not in df.columns:
                continue

            # 清理數據
            series = pd.to_numeric(df[col], errors='coerce').dropna()

            if len(series) == 0:
                statistics[col] = {'error': 'No valid numeric data'}
                continue

            # 基本統計
            stats = {
                'count': int(len(series)),
                'total': int(series.sum()),
                'mean': float(series.mean()),
                'median': float(series.median()),
                'std': float(series.std()) if len(series) > 1 else 0.0,
                'min': int(series.min()),
                'max': int(series.max()),
                'q25': float(series.quantile(0.25)),
                'q75': float(series.quantile(0.75)),
                'iqr': float(series.quantile(0.75) - series.quantile(0.25))
            }

            # 額外指標
            stats.update({
                'variance': float(series.var()) if len(series) > 1 else 0.0,
                'skewness': float(series.skew()) if len(series) > 1 else 0.0,
                'kurtosis': float(series.kurtosis()) if len(series) > 1 else 0.0,
                'cv': float(stats['std'] / stats['mean']) if stats['mean'] > 0 else 0.0,  # 變異係數
                'zero_count': int((series == 0).sum()),
                'non_zero_count': int((series > 0).sum())
            })

            statistics[col] = stats

        # 如果同時有 prompt 和 completion tokens，計算比例
        if 'prompt_tokens' in statistics and 'completion_tokens' in statistics:
            prompt_total = statistics['prompt_tokens']['total']
            completion_total = statistics['completion_tokens']['total']
            total_tokens = prompt_total + completion_total

            if total_tokens > 0:
                statistics['token_ratios'] = {
                    'prompt_ratio': prompt_total / total_tokens,
                    'completion_ratio': completion_total / total_tokens,
                    'total_tokens': total_tokens
                }

        return statistics

    def _calculate_cost_analysis(self, statistics: Dict, model_info: Dict, service_tier: str = 'standard') -> Dict:
        """計算成本分析"""
        pricing_model = model_info['pricing_model']

        # 根據服務層級選擇價格
        tier_prices = self.TOKEN_PRICES.get(service_tier, {})
        prices = tier_prices.get(pricing_model, self.TOKEN_PRICES['default'])

        cost_analysis = {
            'pricing_model_used': pricing_model,
            'service_tier': service_tier,
            'rates_per_1M_tokens': prices  # 更新為 1M tokens
        }

        # 計算各種成本 (注意：價格現在是 per 1M tokens)
        if 'prompt_tokens' in statistics and 'total' in statistics['prompt_tokens']:
            prompt_tokens = statistics['prompt_tokens']['total']
            prompt_cost = (prompt_tokens / 1_000_000) * prices['input']
            cost_analysis['prompt_cost'] = {
                'total_tokens': prompt_tokens,
                'cost_usd': prompt_cost,
                'rate_per_1M': prices['input']
            }

        if 'completion_tokens' in statistics and 'total' in statistics['completion_tokens']:
            completion_tokens = statistics['completion_tokens']['total']
            completion_cost = (completion_tokens / 1_000_000) * prices['output']
            cost_analysis['completion_cost'] = {
                'total_tokens': completion_tokens,
                'cost_usd': completion_cost,
                'rate_per_1M': prices['output']
            }

        # 總成本
        total_cost = 0
        if 'prompt_cost' in cost_analysis:
            total_cost += cost_analysis['prompt_cost']['cost_usd']
        if 'completion_cost' in cost_analysis:
            total_cost += cost_analysis['completion_cost']['cost_usd']

        cost_analysis['total_cost_usd'] = total_cost

        # 每記錄成本
        if 'prompt_tokens' in statistics and statistics['prompt_tokens']['count'] > 0:
            record_count = statistics['prompt_tokens']['count']
            cost_analysis['cost_per_record'] = total_cost / record_count

        # 如果有 Flex 模式，計算節省的成本
        if service_tier == 'flex' and pricing_model in self.TOKEN_PRICES['standard']:
            standard_prices = self.TOKEN_PRICES['standard'][pricing_model]
            standard_cost = 0
            if 'prompt_cost' in cost_analysis:
                standard_cost += (cost_analysis['prompt_cost']['total_tokens'] / 1_000_000) * standard_prices['input']
            if 'completion_cost' in cost_analysis:
                standard_cost += (cost_analysis['completion_cost']['total_tokens'] / 1_000_000) * standard_prices['output']

            cost_analysis['cost_savings'] = {
                'standard_cost': standard_cost,
                'flex_cost': total_cost,
                'savings_usd': standard_cost - total_cost,
                'savings_percentage': ((standard_cost - total_cost) / standard_cost * 100) if standard_cost > 0 else 0
            }

        return cost_analysis

    def _calculate_efficiency_metrics(self, statistics: Dict, cost_analysis: Dict) -> Dict:
        """計算效率指標"""
        efficiency = {}

        # Token 效率
        if 'prompt_tokens' in statistics and 'completion_tokens' in statistics:
            prompt_stats = statistics['prompt_tokens']
            completion_stats = statistics['completion_tokens']

            if prompt_stats['count'] > 0:
                efficiency['avg_tokens_per_record'] = {
                    'prompt': prompt_stats['mean'],
                    'completion': completion_stats['mean'],
                    'total': prompt_stats['mean'] + completion_stats['mean']
                }

                # Token 比例效率
                if prompt_stats['total'] + completion_stats['total'] > 0:
                    total = prompt_stats['total'] + completion_stats['total']
                    efficiency['token_efficiency'] = {
                        'prompt_percentage': (prompt_stats['total'] / total) * 100,
                        'completion_percentage': (completion_stats['total'] / total) * 100,
                        'compression_ratio': completion_stats['total'] / prompt_stats['total'] if prompt_stats['total'] > 0 else 0
                    }

        # 成本效率
        if 'cost_per_record' in cost_analysis:
            efficiency['cost_efficiency'] = {
                'cost_per_record_usd': cost_analysis['cost_per_record'],
                'cost_per_1k_total_tokens': None
            }

            if 'token_ratios' in statistics:
                total_tokens = statistics['token_ratios']['total_tokens']
                if total_tokens > 0:
                    efficiency['cost_efficiency']['cost_per_1k_total_tokens'] = (cost_analysis['total_cost_usd'] / total_tokens) * 1000

        return efficiency

    def analyze_multiple_files(self, file_paths: List[Union[str, Path]],
                             output_dir: Optional[Union[str, Path]] = None,
                             model_hint: Optional[str] = None,
                             service_tier: str = 'standard') -> Dict[str, Dict]:
        """
        分析多個檔案，但分別記錄結果（不合併）

        Args:
            file_paths: 檔案路徑列表
            output_dir: 輸出目錄（可選）
            model_hint: 模型提示（可選）
            service_tier: OpenAI 服務層級 (standard/flex/batch)

        Returns:
            檔案路徑到分析結果的字典映射
        """
        results = {}

        for file_path in file_paths:
            file_path = Path(file_path)
            try:
                analysis = self.analyze_file(file_path, model_hint, service_tier)
                results[str(file_path)] = analysis

                # 如果指定了輸出目錄，保存個別結果
                if output_dir:
                    output_dir = Path(output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)

                    output_file = output_dir / f"{file_path.stem}_token_analysis.json"
                    self.save_analysis(analysis, output_file)

            except Exception as e:
                self.logger.error(f"Failed to analyze {file_path}: {e}")
                results[str(file_path)] = {'error': str(e)}

        return results

    def save_analysis(self, analysis: Dict, output_path: Union[str, Path],
                     format: str = 'json') -> None:
        """保存分析結果"""
        output_path = Path(output_path)

        if format.lower() == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
        else:
            raise ValueError(f"Unsupported format: {format}")

        self.logger.info(f"Analysis saved to: {output_path}")

def print_analysis_summary(analysis: Dict) -> None:
    """打印分析結果摘要"""
    file_info = analysis['file_info']
    data_summary = analysis['data_summary']
    cost_analysis = analysis['cost_analysis']

    print(f"\n{'='*80}")
    print(f"TOKEN ANALYSIS REPORT")
    print(f"{'='*80}")

    print(f"\n📁 File Information:")
    print(f"  File: {file_info['file_name']}")
    print(f"  Size: {file_info['file_size_mb']:.1f} MB")
    print(f"  Model: {file_info['model_info']['base_model']}")
    print(f"  Task: {file_info['task_type']}")

    print(f"\n📊 Data Summary:")
    print(f"  Total records: {data_summary['total_records']:,}")
    print(f"  Valid records: {data_summary['valid_records']:,}")
    print(f"  Token columns: {', '.join(data_summary['token_columns_found'])}")

    # Token 統計
    if 'token_statistics' in analysis:
        stats = analysis['token_statistics']
        print(f"\n🔢 Token Statistics:")

        for col, data in stats.items():
            if col == 'token_ratios':
                continue
            if 'error' in data:
                print(f"  {col}: {data['error']}")
                continue

            print(f"  {col}:")
            print(f"    Total: {data['total']:,}")
            print(f"    Mean: {data['mean']:.1f}")
            print(f"    Median: {data['median']:.1f}")
            print(f"    Std: {data['std']:.1f}")
            print(f"    Range: {data['min']:,} - {data['max']:,}")

    # 成本分析
    print(f"\n💰 Cost Analysis:")
    print(f"  Service tier: {cost_analysis['service_tier']}")
    print(f"  Pricing model: {cost_analysis['pricing_model_used']}")
    print(f"  Total cost: ${cost_analysis['total_cost_usd']:.4f}")
    if 'cost_per_record' in cost_analysis:
        print(f"  Cost per record: ${cost_analysis['cost_per_record']:.6f}")

    # 顯示 Flex 模式節省資訊
    if 'cost_savings' in cost_analysis:
        savings = cost_analysis['cost_savings']
        print(f"  💡 Flex Mode Savings:")
        print(f"    Standard cost: ${savings['standard_cost']:.4f}")
        print(f"    Flex cost: ${savings['flex_cost']:.4f}")
        print(f"    Savings: ${savings['savings_usd']:.4f} ({savings['savings_percentage']:.1f}%)")

def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description="Single File Token Analysis Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --file model_results.csv
  %(prog)s --file results.csv --output analysis.json --model gpt-4.1
  %(prog)s --files file1.csv file2.csv --output-dir ./analysis/
        """
    )

    # 輸入選項
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--file', type=Path,
                           help='Single CSV file to analyze')
    input_group.add_argument('--files', nargs='+', type=Path,
                           help='Multiple CSV files to analyze separately')

    # 輸出選項
    parser.add_argument('--output', type=Path,
                       help='Output JSON file (for single file analysis)')
    parser.add_argument('--output-dir', type=Path,
                       help='Output directory (for multiple files analysis)')

    # 其他選項
    parser.add_argument('--model', type=str,
                       help='Model name hint for pricing (e.g., gpt-4.1, o3)')
    parser.add_argument('--service-tier', choices=['standard', 'flex', 'batch'],
                       default='standard',
                       help='OpenAI service tier for pricing (default: standard)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress summary output')

    args = parser.parse_args()

    # 設置日誌
    setup_logging(args.verbose)

    try:
        analyzer = SingleTokenAnalyzer()

        if args.file:
            # 單檔案分析
            analysis = analyzer.analyze_file(args.file, args.model, args.service_tier)

            if args.output:
                analyzer.save_analysis(analysis, args.output)

            if not args.quiet:
                print_analysis_summary(analysis)

        else:
            # 多檔案分析
            results = analyzer.analyze_multiple_files(
                args.files, args.output_dir, args.model, args.service_tier
            )

            if not args.quiet:
                print(f"\n{'='*80}")
                print(f"MULTIPLE FILES ANALYSIS SUMMARY")
                print(f"{'='*80}")

                successful = len([r for r in results.values() if 'error' not in r])
                failed = len(results) - successful

                print(f"Files processed: {len(results)}")
                print(f"Successful: {successful}")
                print(f"Failed: {failed}")

                if failed > 0:
                    print(f"\nFailed files:")
                    for file_path, result in results.items():
                        if 'error' in result:
                            print(f"  {file_path}: {result['error']}")

    except Exception as e:
        logging.error(f"Analysis failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()