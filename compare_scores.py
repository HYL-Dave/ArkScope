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
    """從文件路徑提取模型名稱，支持reasoning_effort參數"""
    path = Path(filepath)
    filename = path.stem
    
    # 常見模型名稱映射（包含reasoning effort）
    model_mappings = {
        # 標準模型名稱
        'sentiment_o3_by_o3_summary': 'o3',
        'sentiment_o4_mini_by_o3_summary': 'o4-mini', 
        'sentiment_gpt-4.1-mini_by_o3_summary': 'gpt-4.1-mini',
        'sentiment_gpt-4.1-nano_by_o3_summary': 'gpt-4.1-nano',
        'risk_o3_by_o3_summary': 'o3',
        'risk_o4_mini_by_o3_summary': 'o4-mini',
        'risk_gpt-4.1-mini_by_o3_summary': 'gpt-4.1-mini',
        'risk_gpt-4.1-nano_by_o3_summary': 'gpt-4.1-nano',
        
        # 帶reasoning effort的模型名稱
        'sentiment_o3_low_by_o3_summary': 'o3-low',
        'sentiment_o3_medium_by_o3_summary': 'o3-medium',
        'sentiment_o3_high_by_o3_summary': 'o3-high',
        'risk_o3_low_by_o3_summary': 'o3-low',
        'risk_o3_medium_by_o3_summary': 'o3-medium', 
        'risk_o3_high_by_o3_summary': 'o3-high'
    }
    
    if filename in model_mappings:
        return model_mappings[filename]
    
    # 如果沒有找到精確匹配，嘗試從文件名中智能提取
    import re
    
    # 模式1: model_effort 格式 (如 o3_high, o3_medium, o3_low)
    effort_pattern = r'(o3|o4-mini|o4_mini|gpt-4\.1-mini|gpt-4\.1-nano|gpt-4\.1)_(low|medium|high)'
    effort_match = re.search(effort_pattern, filename)
    if effort_match:
        model, effort = effort_match.groups()
        model = model.replace('_', '-')  # 統一使用 - 分隔符
        return f"{model}-{effort}"
    
    # 模式2: 標準模型名稱
    model_patterns = [
        (r'o4[-_]mini', 'o4-mini'),
        (r'gpt-4\.1-mini', 'gpt-4.1-mini'),
        (r'gpt-4\.1-nano', 'gpt-4.1-nano'),
        (r'gpt-4\.1', 'gpt-4.1'),
        (r'o3', 'o3')
    ]
    
    for pattern, model_name in model_patterns:
        if re.search(pattern, filename):
            return model_name
    
    # 如果都沒有匹配，返回原始文件名
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

def analyze_pairwise_similarity(merged_df, score_columns):
    """分析模型兩兩之間的相似度"""
    from itertools import combinations
    from scipy.stats import pearsonr, spearmanr
    from sklearn.metrics import accuracy_score, cohen_kappa_score
    
    pairwise_results = {}
    model_names = [col.split('_')[-1] for col in score_columns]
    
    # 計算所有模型對的相似度指標
    for i, (col1, model1) in enumerate(zip(score_columns, model_names)):
        for j, (col2, model2) in enumerate(zip(score_columns, model_names)):
            if i >= j:  # 避免重複計算
                continue
                
            pair_key = f"{model1}_vs_{model2}"
            
            # 移除任一模型有NaN的記錄
            valid_mask = (~merged_df[col1].isna()) & (~merged_df[col2].isna())
            if valid_mask.sum() == 0:
                continue
                
            scores1 = merged_df.loc[valid_mask, col1].values
            scores2 = merged_df.loc[valid_mask, col2].values
            
            # 計算各種相似度指標
            pair_stats = {}
            
            # 1. 完全一致率 (Exact Match Rate)
            exact_match_rate = (scores1 == scores2).mean() * 100
            pair_stats['exact_match_rate'] = exact_match_rate
            
            # 2. 相差1分以內的比率
            within_1_rate = (np.abs(scores1 - scores2) <= 1).mean() * 100
            pair_stats['within_1_point_rate'] = within_1_rate
            
            # 3. 皮爾森相關係數
            try:
                pearson_r, pearson_p = pearsonr(scores1, scores2)
                pair_stats['pearson_correlation'] = pearson_r
                pair_stats['pearson_p_value'] = pearson_p
            except:
                pair_stats['pearson_correlation'] = np.nan
                pair_stats['pearson_p_value'] = np.nan
            
            # 4. 斯皮爾曼相關係數 (適合有序數據)
            try:
                spearman_r, spearman_p = spearmanr(scores1, scores2)
                pair_stats['spearman_correlation'] = spearman_r
                pair_stats['spearman_p_value'] = spearman_p
            except:
                pair_stats['spearman_correlation'] = np.nan
                pair_stats['spearman_p_value'] = np.nan
            
            # 5. Cohen's Kappa (一致性指標)
            try:
                kappa = cohen_kappa_score(scores1, scores2)
                pair_stats['cohen_kappa'] = kappa
            except:
                pair_stats['cohen_kappa'] = np.nan
            
            # 6. 平均絕對誤差 (MAE)
            mae = np.mean(np.abs(scores1 - scores2))
            pair_stats['mean_absolute_error'] = mae
            
            # 7. 分數差異分佈
            diff_distribution = {}
            differences = scores2 - scores1  # model2 - model1
            for diff in np.unique(differences):
                if not np.isnan(diff):
                    diff_distribution[float(diff)] = int(np.sum(differences == diff))
            pair_stats['difference_distribution'] = diff_distribution
            
            # 8. 混淆矩陣統計
            confusion_stats = {}
            unique_scores = sorted(set(list(scores1) + list(scores2)))
            for s1 in unique_scores:
                for s2 in unique_scores:
                    count = int(np.sum((scores1 == s1) & (scores2 == s2)))
                    if count > 0:
                        confusion_stats[f"{s1}_vs_{s2}"] = count
            pair_stats['confusion_matrix'] = confusion_stats
            
            pair_stats['total_comparisons'] = len(scores1)
            
            pairwise_results[pair_key] = pair_stats
    
    return pairwise_results

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
    
    # 添加兩兩相似度分析
    results['pairwise_similarity'] = analyze_pairwise_similarity(merged_df, score_columns)
    
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

def print_pairwise_similarity_summary(pairwise_results, top_n=None):
    """打印兩兩相似度分析摘要"""
    print("\n" + "="*80)
    print("PAIRWISE MODEL SIMILARITY ANALYSIS")
    print("="*80)
    
    if not pairwise_results:
        print("No pairwise comparisons available.")
        return
    
    # 排序模型對按相似度指標
    similarity_rankings = {}
    
    for metric in ['exact_match_rate', 'within_1_point_rate', 'pearson_correlation', 
                   'spearman_correlation', 'cohen_kappa']:
        pairs_with_metric = []
        for pair, stats in pairwise_results.items():
            if metric in stats and not np.isnan(stats[metric]):
                pairs_with_metric.append((pair, stats[metric]))
        
        if pairs_with_metric:
            # 對於相關係數，取絕對值排序；對於其他指標，直接排序
            if 'correlation' in metric:
                pairs_with_metric.sort(key=lambda x: abs(x[1]), reverse=True)
            else:
                pairs_with_metric.sort(key=lambda x: x[1], reverse=True)
            
            similarity_rankings[metric] = pairs_with_metric
    
    # 打印各種相似度指標的排名
    print("\n📊 Model Similarity Rankings:")
    print("-" * 80)
    
    # 決定顯示的條目數量
    display_count = len(pairwise_results) if top_n is None else min(top_n, len(pairwise_results))
    
    # 1. 完全一致率排名
    if 'exact_match_rate' in similarity_rankings:
        print("\n🎯 Exact Match Rate (Higher = More Similar):")
        for i, (pair, rate) in enumerate(similarity_rankings['exact_match_rate'][:display_count], 1):
            print(f"  {i}. {pair.replace('_vs_', ' ↔ ')}: {rate:.2f}%")
    
    # 2. 相差1分以內比率排名
    if 'within_1_point_rate' in similarity_rankings:
        print("\n📏 Within 1 Point Rate (Higher = More Similar):")
        for i, (pair, rate) in enumerate(similarity_rankings['within_1_point_rate'][:display_count], 1):
            print(f"  {i}. {pair.replace('_vs_', ' ↔ ')}: {rate:.2f}%")
    
    # 3. 皮爾森相關係數排名  
    if 'pearson_correlation' in similarity_rankings:
        print("\n📈 Pearson Correlation (Higher absolute value = More Similar):")
        for i, (pair, corr) in enumerate(similarity_rankings['pearson_correlation'][:display_count], 1):
            print(f"  {i}. {pair.replace('_vs_', ' ↔ ')}: {corr:.4f}")
    
    # 4. 斯皮爾曼相關係數排名
    if 'spearman_correlation' in similarity_rankings:
        print("\n📊 Spearman Correlation (Higher absolute value = More Similar):")
        for i, (pair, corr) in enumerate(similarity_rankings['spearman_correlation'][:display_count], 1):
            print(f"  {i}. {pair.replace('_vs_', ' ↔ ')}: {corr:.4f}")
    
    # 5. Cohen's Kappa排名
    if 'cohen_kappa' in similarity_rankings:
        print("\n🤝 Cohen's Kappa Agreement (Higher = More Similar):")
        for i, (pair, kappa) in enumerate(similarity_rankings['cohen_kappa'][:display_count], 1):
            print(f"  {i}. {pair.replace('_vs_', ' ↔ ')}: {kappa:.4f}")
    
    # 綜合相似度排名（基於多個指標的平均排名）
    print("\n🏆 OVERALL SIMILARITY RANKING:")
    print("-" * 50)
    
    pair_scores = defaultdict(list)
    
    # 計算每個模型對在各指標中的排名分數
    for metric, pairs in similarity_rankings.items():
        if metric in ['exact_match_rate', 'within_1_point_rate', 'cohen_kappa']:
            # 這些指標越高越好
            for rank, (pair, value) in enumerate(pairs):
                pair_scores[pair].append(len(pairs) - rank)  # 轉換為分數
        elif 'correlation' in metric:
            # 相關係數取絕對值，越高越好
            for rank, (pair, value) in enumerate(pairs):
                pair_scores[pair].append(len(pairs) - rank)
    
    # 計算平均分數並排序
    average_scores = {}
    for pair, scores in pair_scores.items():
        if len(scores) >= 3:  # 至少有3個指標的分數
            average_scores[pair] = np.mean(scores)
    
    if average_scores:
        sorted_pairs = sorted(average_scores.items(), key=lambda x: x[1], reverse=True)
        for i, (pair, avg_score) in enumerate(sorted_pairs, 1):
            models = pair.replace('_vs_', ' ↔ ')
            print(f"  {i}. {models}: {avg_score:.2f} points")
            
            # 顯示詳細指標
            if pair in pairwise_results:
                stats = pairwise_results[pair]
                details = []
                if 'exact_match_rate' in stats:
                    details.append(f"Exact: {stats['exact_match_rate']:.1f}%")
                if 'pearson_correlation' in stats and not np.isnan(stats['pearson_correlation']):
                    details.append(f"Pearson: {stats['pearson_correlation']:.3f}")
                if 'cohen_kappa' in stats and not np.isnan(stats['cohen_kappa']):
                    details.append(f"Kappa: {stats['cohen_kappa']:.3f}")
                if details:
                    print(f"     ({', '.join(details)})")
    
    # 最相似和最不相似的模型對
    if 'exact_match_rate' in similarity_rankings and similarity_rankings['exact_match_rate']:
        most_similar = similarity_rankings['exact_match_rate'][0]
        least_similar = similarity_rankings['exact_match_rate'][-1]
        
        print(f"\n🥇 Most Similar Models: {most_similar[0].replace('_vs_', ' ↔ ')} ({most_similar[1]:.2f}% exact match)")
        print(f"🥉 Least Similar Models: {least_similar[0].replace('_vs_', ' ↔ ')} ({least_similar[1]:.2f}% exact match)")

def print_summary(analysis, top_n_combos=5, top_n_similarity=None):
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
    
    # 動態決定顯示的組合數量
    combo_count = len(analysis['most_common_combinations']) if top_n_combos is None else min(top_n_combos, len(analysis['most_common_combinations']))
    print(f"\nMost Common Score Combinations (Top {combo_count}):")
    for i, (combo, count) in enumerate(analysis['most_common_combinations'][:combo_count], 1):
        percentage = count / analysis['total_records'] * 100
        print(f"{i}. {combo}: {count:,} ({percentage:.1f}%)")
    
    # 打印兩兩相似度分析
    if 'pairwise_similarity' in analysis:
        print_pairwise_similarity_summary(analysis['pairwise_similarity'], top_n_similarity)

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
    parser.add_argument('--top-n-combos', type=int, default=5,
                       help='Number of top score combinations to display (default: 5, use 0 for all)')
    parser.add_argument('--top-n-similarity', type=int, default=None,
                       help='Number of top similarity rankings to display (default: all, use specific number to limit)')
    
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
        
        # 處理參數
        top_n_combos = None if args.top_n_combos == 0 else args.top_n_combos
        
        # 打印摘要
        print_summary(analysis, top_n_combos, args.top_n_similarity)
        
    except Exception as e:
        logging.error(f"Error during processing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()