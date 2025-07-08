#!/usr/bin/env python3
"""
FinRL 新聞數據質量深度分析腳本
用於主管道運行後的詳細分析
"""

import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import openai
from typing import List, Dict, Tuple
import logging
from concurrent.futures import ThreadPoolExecutor
import time
from collections import Counter
import re
import httpx

class NewsQualityAnalyzer:
    def __init__(self, data_path: str = 'news_89_2013_2023_cleaned.parquet', 
                 openai_key: str = None):
        """初始化分析器"""
        self.data_path = data_path
        self.df = pd.read_parquet(data_path)
        self.openai_key = openai_key
        if openai_key:
            openai.api_key = openai_key
        
        # 設置日誌
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # 模型參數
        self.model = "o3"
        self.use_flex = True
        
    def analyze_temporal_distribution(self) -> Dict:
        """分析時間分佈"""
        self.logger.info("分析新聞時間分佈...")
        
        # 按年月統計
        self.df['year_month'] = self.df['Date'].dt.to_period('M')
        monthly_counts = self.df.groupby('year_month').size()
        
        # 按股票和時間統計
        stock_time_dist = self.df.groupby(['Stock_symbol', 'year']).size().unstack(fill_value=0)
        
        # 找出新聞稀疏的時期
        sparse_periods = monthly_counts[monthly_counts < monthly_counts.quantile(0.1)]
        
        # 繪製熱力圖
        plt.figure(figsize=(15, 10))
        sns.heatmap(stock_time_dist, cmap='YlOrRd', cbar_kws={'label': 'News Count'})
        plt.title('News Distribution by Stock and Year')
        plt.tight_layout()
        plt.savefig('news_temporal_heatmap.png')
        plt.close()
        
        return {
            'monthly_average': float(monthly_counts.mean()),
            'sparse_periods': sparse_periods.index.astype(str).tolist(),
            'most_active_month': str(monthly_counts.idxmax()),
            'coverage_gaps': self._find_coverage_gaps()
        }
    
    def _find_coverage_gaps(self) -> List[Dict]:
        """找出新聞覆蓋的空白期"""
        gaps = []
        
        for symbol in self.df['Stock_symbol'].unique():
            symbol_df = self.df[self.df['Stock_symbol'] == symbol].sort_values('Date')
            dates = pd.to_datetime(symbol_df['Date'])
            
            # 找出超過7天沒有新聞的時期
            date_diffs = dates.diff()
            gap_mask = date_diffs > pd.Timedelta(days=7)
            
            if gap_mask.any():
                gap_indices = gap_mask[gap_mask].index
                for idx in gap_indices:
                    gaps.append({
                        'symbol': symbol,
                        'gap_start': str(dates.iloc[dates.get_loc(idx) - 1].date()),
                        'gap_end': str(dates.loc[idx].date()),
                        'gap_days': int(date_diffs.loc[idx].days)
                    })
        
        return sorted(gaps, key=lambda x: x['gap_days'], reverse=True)[:20]
    
    def analyze_content_quality(self, sample_size: int = 200) -> Dict:
        """深度內容質量分析"""
        self.logger.info("執行深度內容質量分析...")
        
        # 傳遞正確的 sample_size
        actual_sample_size = min(sample_size, len(self.df))
        
        # 基礎統計
        results = {
            'readability_scores': self._calculate_readability(),
            'duplicate_analysis': self._analyze_duplicates(),
            'language_quality': self._check_language_quality(actual_sample_size),
            'information_density': self._calculate_information_density()
        }
        
        return results
    
    def _calculate_readability(self) -> Dict:
        """計算可讀性分數"""
        from textstat import flesch_reading_ease, flesch_kincaid_grade
        
        sample = self.df.sample(n=min(1000, len(self.df)))
        
        reading_ease_scores = []
        grade_levels = []
        
        for text in sample['News_text']:
            if text and len(text) > 50:
                reading_ease_scores.append(flesch_reading_ease(text))
                grade_levels.append(flesch_kincaid_grade(text))
        
        return {
            'avg_reading_ease': np.mean(reading_ease_scores),
            'avg_grade_level': np.mean(grade_levels),
            'ease_distribution': pd.Series(reading_ease_scores).describe().to_dict()
        }
    
    def _analyze_duplicates(self) -> Dict:
        """分析重複和相似內容"""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        # 取樣分析
        sample = self.df.sample(n=min(500, len(self.df)))
        
        # 使用 TF-IDF 找相似文章
        vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(sample['News_text'].fillna(''))
        
        # 計算相似度
        similarity_matrix = cosine_similarity(tfidf_matrix)
        
        # 找出高度相似的文章對
        similar_pairs = []
        for i in range(len(similarity_matrix)):
            for j in range(i+1, len(similarity_matrix)):
                if similarity_matrix[i][j] > 0.8:  # 相似度閾值
                    similar_pairs.append({
                        'index1': sample.index[i],
                        'index2': sample.index[j],
                        'similarity': float(similarity_matrix[i][j])
                    })
        
        return {
            'high_similarity_pairs': len(similar_pairs),
            'duplicate_titles': int(self.df.duplicated('News_title').sum()),
            'near_duplicate_estimate': len(similar_pairs) * len(self.df) / len(sample)
        }
    
    def _check_language_quality(self, sample_size: int) -> Dict:
        """使用 reasoning 模型檢查語言質量（Flex processing）"""
        if not self.openai_key:
            return {'status': 'skipped - no API key'}
        
        from openai import OpenAI
        import httpx
        
        # 配置 OpenAI 客戶端使用更長的 timeout
        client = OpenAI(
            api_key=self.openai_key,
            timeout=httpx.Timeout(1800.0, connect=60.0)  # 30分鐘 timeout
        )
        
        sample = self.df.sample(n=min(sample_size, len(self.df)))
        quality_scores = []
        
        # 英文 prompt 更適合美股新聞分析
        prompt = """
        Evaluate the quality of the following financial news text (score 1-10):
        
        Text: {text}
        
        Scoring dimensions:
        1. Grammar correctness (1-10): Grammar, spelling, punctuation accuracy
        2. Information completeness (1-10): Contains complete 5W1H information
        3. Professionalism (1-10): Accurate use of financial terminology
        4. Readability (1-10): Clear structure and logic
        5. Information value (1-10): Actual value for investors
        6. Data support (1-10): Contains specific data and citations
        7. Objectivity (1-10): Avoids excessive subjective judgment
        
        Additional analysis:
        - Identify potential bias or misleading information
        - Assess source reliability
        - Flag any suspicious or unverifiable claims
        
        Return detailed evaluation in JSON format:
        {{
            "scores": {{
                "grammar": X,
                "completeness": X,
                "professionalism": X,
                "readability": X,
                "information_value": X,
                "data_support": X,
                "objectivity": X
            }},
            "overall": X,
            "issues": [],
            "suspicious_claims": [],
            "improvement_suggestions": []
        }}
        """
        
        batch_size = 20
        for i in range(0, len(sample), batch_size):
            batch = sample.iloc[i:i+batch_size]
            self.logger.info(f"語言質量檢查批次 {i//batch_size + 1}")
            
            for _, row in batch.iterrows():
                try:
                    if self.model in ['o3', 'o4-mini']:
                        response = client.chat.completions.create(
                            model=self.model,
                            messages=[{
                                "role": "user",
                                "content": prompt.format(text=row['News_text'][:1000])
                            }],
                            reasoning_effort="medium",
                            max_completion_tokens=1500,
                            service_tier="flex" if self.use_flex else "default"
                        )
                    else:
                        response = client.chat.completions.create(
                            model=self.model,
                            messages=[{
                                "role": "system",
                                "content": "You are a professional financial news quality assessment expert with deep financial knowledge and news writing experience."
                            }, {
                                "role": "user",
                                "content": prompt.format(text=row['News_text'][:1000])
                            }],
                            temperature=0,
                            max_tokens=1500
                        )
                    
                    scores = json.loads(response.choices[0].message.content)
                    quality_scores.append(scores)
                    
                except Exception as e:
                    self.logger.warning(f"Quality check failed: {e}")
        
        if quality_scores:
            # 計算各維度平均分
            dimension_averages = {}
            for dimension in ['grammar', 'completeness', 'professionalism', 
                            'readability', 'information_value', 'data_support', 'objectivity']:
                dimension_averages[dimension] = np.mean([
                    s['scores'][dimension] for s in quality_scores 
                    if dimension in s.get('scores', {})
                ])
            
            # 統計常見問題
            all_issues = [issue for s in quality_scores for issue in s.get('issues', [])]
            issue_frequency = dict(Counter(all_issues).most_common(10))
            
            return {
                'average_scores': dimension_averages,
                'overall_average': np.mean([s.get('overall', 5) for s in quality_scores]),
                'low_quality_percentage': sum(1 for s in quality_scores if s.get('overall', 5) < 6) / len(quality_scores),
                'common_issues': issue_frequency,
                'sample_size': len(quality_scores)
            }
        
        return {'status': 'failed'}
    
    def _calculate_information_density(self) -> Dict:
        """計算信息密度"""
        # 計算每篇新聞的實體數量
        import spacy
        try:
            nlp = spacy.load("en_core_web_sm")
        except:
            return {'status': 'spacy not installed'}
        
        sample = self.df.sample(n=min(100, len(self.df)))
        entity_counts = []
        
        for text in sample['News_text']:
            if text and len(text) > 50:
                doc = nlp(text[:1000])  # 限制長度
                entities = len([ent for ent in doc.ents if ent.label_ in ['ORG', 'PERSON', 'MONEY', 'PERCENT']])
                entity_counts.append(entities / len(doc))
        
        return {
            'avg_entity_density': float(np.mean(entity_counts)),
            'entity_density_std': float(np.std(entity_counts))
        }
    
    def analyze_stock_coverage_balance(self) -> Dict:
        """分析股票覆蓋平衡性"""
        self.logger.info("分析股票覆蓋平衡性...")
        
        stock_stats = self.df.groupby('Stock_symbol').agg({
            'News_title': 'count',
            'Sentiment': 'mean',
            'importance_score': 'mean',
            'Date': ['min', 'max']
        })
        
        stock_stats.columns = ['news_count', 'avg_sentiment', 'avg_importance', 'first_news', 'last_news']
        
        # 計算 Gini 係數評估不平衡程度
        gini = self._calculate_gini(stock_stats['news_count'].values)
        
        # 找出覆蓋不足的股票
        median_count = stock_stats['news_count'].median()
        undercovered = stock_stats[stock_stats['news_count'] < median_count * 0.5]
        
        return {
            'gini_coefficient': float(gini),
            'coverage_stats': stock_stats.describe().to_dict(),
            'undercovered_stocks': undercovered.index.tolist(),
            'most_covered': stock_stats.nlargest(10, 'news_count').to_dict(),
            'least_covered': stock_stats.nsmallest(10, 'news_count').to_dict()
        }
    
    def _calculate_gini(self, values):
        """計算 Gini 係數"""
        sorted_values = np.sort(values)
        n = len(values)
        index = np.arange(1, n + 1)
        return (2 * np.sum(index * sorted_values)) / (n * np.sum(sorted_values)) - (n + 1) / n
    
    def generate_comprehensive_report(self, output_file: str = 'comprehensive_quality_report.json'):
        """生成綜合質量報告"""
        self.logger.info("生成綜合質量報告...")
        
        report = {
            'metadata': {
                'total_records': len(self.df),
                'analysis_date': datetime.now().isoformat(),
                'data_file': self.data_path
            },
            'temporal_analysis': self.analyze_temporal_distribution(),
            'content_quality': self.analyze_content_quality(),
            'coverage_balance': self.analyze_stock_coverage_balance(),
            'recommendations': self._generate_recommendations()
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"報告已保存到 {output_file}")
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """基於分析結果生成建議"""
        recommendations = []
        
        # 基於各項分析結果生成建議
        stock_coverage = self.analyze_stock_coverage_balance()
        if stock_coverage['gini_coefficient'] > 0.5:
            recommendations.append(
                f"股票覆蓋不平衡 (Gini={stock_coverage['gini_coefficient']:.2f})，"
                f"建議增加以下股票的數據來源: {', '.join(stock_coverage['undercovered_stocks'][:5])}"
            )
        
        temporal = self.analyze_temporal_distribution()
        if temporal['coverage_gaps']:
            recommendations.append(
                f"發現 {len(temporal['coverage_gaps'])} 個顯著的覆蓋空白期，"
                f"最長達 {temporal['coverage_gaps'][0]['gap_days']} 天"
            )
        
        return recommendations
    
    def export_cleaned_subset(self, quality_threshold: float = 0.7, 
                            output_file: str = 'high_quality_news.parquet'):
        """導出高質量數據子集"""
        self.logger.info(f"導出質量分數 >= {quality_threshold} 的數據...")
        
        # 根據 importance_score 篩選
        high_quality_df = self.df[self.df['importance_score'] >= quality_threshold]
        
        # 額外過濾
        high_quality_df = high_quality_df[
            (high_quality_df['title_length'] >= 20) &
            (high_quality_df['text_length'] >= 100) &
            (~high_quality_df.get('low_relevance', False))
        ]
        
        high_quality_df.to_parquet(output_file, index=False)
        self.logger.info(f"已導出 {len(high_quality_df)} 條高質量數據到 {output_file}")
        
        return high_quality_df


def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FinRL 新聞數據質量深度分析')
    parser.add_argument('--data', type=str, default='news_89_2013_2023_cleaned.parquet',
                       help='清洗後的數據文件路徑')
    parser.add_argument('--openai-key', type=str, help='OpenAI API Key')
    parser.add_argument('--export-threshold', type=float, default=0.7,
                       help='導出高質量數據的閾值')
    parser.add_argument('--model', type=str, default='o3', 
                       choices=['o3', 'o4-mini', 'gpt-4.1', 'gpt-4.1-mini'],
                       help='選擇 OpenAI 模型 (預設: o3)')
    parser.add_argument('--use-flex', action='store_true', default=True,
                       help='使用 Flex Processing (預設: True，僅對 reasoning 模型有效)')
    parser.add_argument('--sample-size', type=int, default=200,
                       help='語言質量檢查的樣本大小 (預設: 200)')
    args = parser.parse_args()
    
    # 創建分析器
    analyzer = NewsQualityAnalyzer(
        data_path=args.data,
        openai_key=args.openai_key
    )
    
    # 設置模型參數
    analyzer.model = args.model
    analyzer.use_flex = args.use_flex
    
    # 檢查模型和 Flex 兼容性
    if args.model in ['gpt-4.1', 'gpt-4.1-mini'] and args.use_flex:
        print("注意：一般模型不支援 Flex Processing，已自動關閉")
        analyzer.use_flex = False
    
    # 生成綜合報告
    report = analyzer.generate_comprehensive_report()
    
    # 導出高質量子集
    analyzer.export_cleaned_subset(quality_threshold=args.export_threshold)
    
    print("\n分析完成！")
    print(f"- 綜合報告: comprehensive_quality_report.json")
    print(f"- 時間分佈熱力圖: news_temporal_heatmap.png")
    print(f"- 高質量數據子集: high_quality_news.parquet")
    
    if args.model in ['o3', 'o4-mini']:
        print(f"\n使用 {args.model} reasoning 模型進行了深度分析，包含 7 個質量維度評估")
        if args.use_flex:
            print("已啟用 Flex Processing 以優化成本")


if __name__ == "__main__":
    main()
