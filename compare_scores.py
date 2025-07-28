#!/usr/bin/env python3
"""
CSV Score Comparison Tool

比較多個CSV文件中的sentiment_deepseek或risk_deepseek分數，
找出不同分數的記錄並進行統計分析。

Usage:
    python compare_scores.py --files file1.csv file2.csv file3.csv --score-column sentiment_deepseek --output results.csv
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
import json
import sys
import logging
from collections import Counter, defaultdict

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def extract_model_name(filepath):
    """從文件路徑提取模型名稱"""
    path = Path(filepath)
    filename = path.stem
    
    # 常見模型名稱映射
    model_mappings = {
        'sentiment_o3_by_o3_summary': 'o3',
        'sentiment_o4_mini_by_o3_summary': 'o4-mini', 
        'sentiment_gpt-4.1-mini_by_o3_summary': 'gpt-4.1-mini',
        'sentiment_gpt-4.1-nano_by_o3_summary': 'gpt-4.1-nano',
        'risk_o3_by_o3_summary': 'o3',
        'risk_o4_mini_by_o3_summary': 'o4-mini',
        'risk_gpt-4.1-mini_by_o3_summary': 'gpt-4.1-mini',
        'risk_gpt-4.1-nano_by_o3_summary': 'gpt-4.1-nano'
    }
    
    if filename in model_mappings:
        return model_mappings[filename]
    
    # 如果沒有找到，嘗試從文件名中提取
    if 'o3' in filename:
        return 'o3'
    elif 'o4-mini' in filename or 'o4_mini' in filename:
        return 'o4-mini'
    elif 'gpt-4.1-mini' in filename:
        return 'gpt-4.1-mini'
    elif 'gpt-4.1-nano' in filename:
        return 'gpt-4.1-nano'
    elif 'gpt-4.1' in filename:
        return 'gpt-4.1'
    else:
        return filename

def load_and_prepare_data(filepaths, score_column):
    """載入並準備數據進行比較"""
    dataframes = {}
    
    for filepath in filepaths:
        try:
            logging.info(f"Loading {filepath}")
            df = pd.read_csv(filepath)
            
            # 檢查必要的列是否存在
            required_cols = [score_column, 'o3_summary']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logging.error(f"Missing columns in {filepath}: {missing_cols}")
                continue
                
            model_name = extract_model_name(filepath)
            
            # 使用索引作為唯一標識符，如果有Unnamed: 0.1則使用它
            if 'Unnamed: 0.1' in df.columns:
                df = df.set_index('Unnamed: 0.1')
            elif 'Unnamed: 0' in df.columns:
                df = df.set_index('Unnamed: 0')
            
            # 只保留需要的列
            keep_cols = [score_column, 'o3_summary']
            optional_cols = ['Date', 'Stock_symbol', 'Article_title']
            for col in optional_cols:
                if col in df.columns:
                    keep_cols.append(col)
            
            df_subset = df[keep_cols].copy()
            
            # 重命名分數列
            df_subset = df_subset.rename(columns={score_column: f"{score_column}_{model_name}"})
            
            dataframes[model_name] = df_subset
            logging.info(f"Loaded {len(df_subset)} records from {model_name}")
            
        except Exception as e:
            logging.error(f"Error loading {filepath}: {e}")
            continue
    
    return dataframes

def merge_dataframes(dataframes):
    """合併所有數據框"""
    if not dataframes:
        raise ValueError("No dataframes to merge")
    
    # 從第一個數據框開始
    first_key = list(dataframes.keys())[0]
    merged = dataframes[first_key].copy()
    
    # 逐個合併其他數據框
    for model_name, df in list(dataframes.items())[1:]:
        score_col = [col for col in df.columns if col.startswith(('sentiment_deepseek_', 'risk_deepseek_'))][0]
        
        # 只合併分數列
        merged = merged.merge(df[[score_col]], left_index=True, right_index=True, how='inner')
    
    return merged

def analyze_score_differences(merged_df, score_columns):
    """分析分數差異"""
    results = {}
    
    # 統計總記錄數
    total_records = len(merged_df)
    results['total_records'] = total_records
    
    # 找出有差異的記錄
    score_values = merged_df[score_columns].values
    
    # 檢查每行是否所有分數都相同
    all_same_mask = np.all(score_values == score_values[:, 0:1], axis=1)
    different_scores_df = merged_df[~all_same_mask].copy()
    same_scores_df = merged_df[all_same_mask].copy()
    
    results['records_with_differences'] = len(different_scores_df)
    results['records_all_same'] = len(same_scores_df)
    results['difference_percentage'] = (len(different_scores_df) / total_records) * 100
    
    # 分析分數分佈
    score_distributions = {}
    for col in score_columns:
        distribution = merged_df[col].value_counts().to_dict()
        score_distributions[col] = distribution
    
    results['score_distributions'] = score_distributions
    
    # 分析分數組合
    score_combinations = defaultdict(int)
    for _, row in merged_df.iterrows():
        combo = tuple(row[score_columns].values)
        score_combinations[combo] += 1
    
    # 轉換為可序列化的格式
    results['score_combinations'] = {str(k): v for k, v in score_combinations.items()}
    
    # 最常見的分數組合
    most_common_combos = Counter(score_combinations).most_common(10)
    results['most_common_combinations'] = [(str(combo), count) for combo, count in most_common_combos]
    
    return results, different_scores_df, same_scores_df

def save_results(different_scores_df, same_scores_df, analysis, output_path, stats_path):
    """保存結果到文件"""
    
    # 保存有差異的記錄
    if not different_scores_df.empty:
        different_scores_df.to_csv(output_path)
        logging.info(f"Saved {len(different_scores_df)} records with different scores to {output_path}")
    else:
        logging.info("No records with different scores found")
    
    # 保存統計信息
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    logging.info(f"Saved analysis statistics to {stats_path}")
    
    # 如果有相同分數的記錄，也保存它們
    if not same_scores_df.empty:
        same_output_path = output_path.replace('.csv', '_same_scores.csv')
        same_scores_df.to_csv(same_output_path)
        logging.info(f"Saved {len(same_scores_df)} records with same scores to {same_output_path}")

def print_summary(analysis):
    """打印摘要統計"""
    print("\n" + "="*60)
    print("SCORE COMPARISON ANALYSIS SUMMARY")
    print("="*60)
    
    print(f"Total records: {analysis['total_records']:,}")
    print(f"Records with different scores: {analysis['records_with_differences']:,}")
    print(f"Records with same scores: {analysis['records_all_same']:,}")
    print(f"Difference percentage: {analysis['difference_percentage']:.2f}%")
    
    print("\nScore Distributions:")
    for model, dist in analysis['score_distributions'].items():
        print(f"\n{model}:")
        for score, count in sorted(dist.items()):
            print(f"  {score}: {count:,} ({count/analysis['total_records']*100:.1f}%)")
    
    print("\nMost Common Score Combinations:")
    for i, (combo, count) in enumerate(analysis['most_common_combinations'][:5], 1):
        percentage = count / analysis['total_records'] * 100
        print(f"{i}. {combo}: {count:,} ({percentage:.1f}%)")

def main():
    parser = argparse.ArgumentParser(description="Compare scores across multiple CSV files")
    parser.add_argument('--files', nargs='+', required=True, 
                       help='CSV files to compare')
    parser.add_argument('--score-column', required=True,
                       choices=['sentiment_deepseek', 'risk_deepseek'],
                       help='Score column to compare')
    parser.add_argument('--output', required=True,
                       help='Output CSV file for different scores')
    parser.add_argument('--stats', 
                       help='Output JSON file for statistics (default: output_stats.json)')
    
    args = parser.parse_args()
    
    setup_logging()
    
    # 驗證輸入文件
    for filepath in args.files:
        if not Path(filepath).exists():
            logging.error(f"File not found: {filepath}")
            sys.exit(1)
    
    if len(args.files) < 2:
        logging.error("Need at least 2 files to compare")
        sys.exit(1)
    
    # 設置輸出路徑
    stats_path = args.stats or args.output.replace('.csv', '_stats.json')
    
    try:
        # 載入數據
        dataframes = load_and_prepare_data(args.files, args.score_column)
        
        if len(dataframes) < 2:
            logging.error("Need at least 2 valid dataframes to compare")
            sys.exit(1)
        
        # 合併數據框
        merged_df = merge_dataframes(dataframes)
        logging.info(f"Merged data: {len(merged_df)} records")
        
        # 獲取分數列名稱
        score_columns = [col for col in merged_df.columns if col.startswith(args.score_column)]
        
        # 分析差異
        analysis, different_scores_df, same_scores_df = analyze_score_differences(merged_df, score_columns)
        
        # 保存結果
        save_results(different_scores_df, same_scores_df, analysis, args.output, stats_path)
        
        # 打印摘要
        print_summary(analysis)
        
    except Exception as e:
        logging.error(f"Error during processing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()