#!/usr/bin/env python3
"""
FinRL 新聞數據質量深度分析腳本 v2.0
增強功能：更多品質維度、多語言支援、更豐富的分析指標
"""

import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import openai
from typing import List, Dict, Tuple, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import time
from collections import Counter
import re
import httpx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from dataclasses import dataclass
from enum import Enum
import warnings

warnings.filterwarnings('ignore')

# 設置中文字體支援
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


# 品質維度定義
@dataclass
class QualityDimensions:
    """擴展的品質維度"""
    # 原有維度
    grammar: float  # 語法正確性
    completeness: float  # 信息完整性
    professionalism: float  # 專業性
    readability: float  # 可讀性
    information_value: float  # 信息價值
    data_support: float  # 數據支撐
    objectivity: float  # 客觀性

    # 新增維度
    timeliness: float  # 時效性
    source_credibility: float  # 來源可信度
    fact_density: float  # 事實密度
    citation_quality: float  # 引用品質
    cross_reference: float  # 交叉引用
    market_relevance: float  # 市場相關性
    regulatory_compliance: float  # 合規性
    uniqueness: float  # 獨特性（非重複內容）
    clarity: float  # 清晰度
    actionability: float  # 可操作性

    def to_dict(self) -> Dict:
        return {k: v for k, v in self.__dict__.items()}

    @property
    def overall_score(self) -> float:
        """計算綜合分數"""
        weights = {
            'information_value': 0.15,
            'market_relevance': 0.15,
            'data_support': 0.10,
            'timeliness': 0.10,
            'source_credibility': 0.10,
            'objectivity': 0.08,
            'clarity': 0.08,
            'professionalism': 0.06,
            'completeness': 0.06,
            'fact_density': 0.06,
            'grammar': 0.03,
            'readability': 0.03
        }

        total = sum(getattr(self, dim, 0) * weight
                    for dim, weight in weights.items())
        return round(total, 2)


class Language(Enum):
    """支援的語言"""
    EN = "en"
    ZH = "zh"
    ES = "es"
    JP = "jp"


class NewsQualityAnalyzer:
    def __init__(self, data_path: str = 'news_89_2013_2023_cleaned.parquet',
                 openai_key: str = None, language: Language = Language.EN):
        """初始化分析器"""
        self.data_path = data_path
        self.df = pd.read_parquet(data_path)
        self.openai_key = openai_key
        self.language = language

        # 移除過時的 openai.api_key 設置
        # if openai_key:
        #     openai.api_key = openai_key

        # 設置日誌
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # 模型參數
        self.model = "o3"
        self.use_flex = True

        # 多語言提示詞
        self.prompts = self._load_multilingual_prompts()

    def _load_multilingual_prompts(self) -> Dict:
        """載入多語言提示詞"""
        return {
            Language.EN: {
                'quality_check': """
                Evaluate the quality of the following financial news text across 17 dimensions (score 1-10):

                Text: {text}

                Dimensions to evaluate:
                1. Grammar correctness (1-10)
                2. Information completeness (1-10)
                3. Professionalism (1-10)
                4. Readability (1-10)
                5. Information value (1-10)
                6. Data support (1-10)
                7. Objectivity (1-10)
                8. Timeliness indicators (1-10)
                9. Source credibility markers (1-10)
                10. Fact density (facts per 100 words)
                11. Citation quality (1-10)
                12. Cross-reference quality (1-10)
                13. Market relevance (1-10)
                14. Regulatory compliance indicators (1-10)
                15. Uniqueness/originality (1-10)
                16. Clarity of expression (1-10)
                17. Actionability for investors (1-10)

                Also identify:
                - Key facts and figures
                - Potential biases or misleading information
                - Missing critical information
                - Improvement suggestions

                Return comprehensive evaluation in JSON format.
                """,
                'pattern_analysis': """
                Analyze patterns in the following batch of financial news quality assessments:

                {results_summary}

                Identify:
                1. Common quality issues across articles
                2. Patterns by stock, time period, or topic
                3. Systemic biases or gaps
                4. Anomalies requiring attention
                5. Specific recommendations for data improvement

                Return detailed analysis in JSON format.
                """
            },
            Language.ZH: {
                'quality_check': """
                請評估以下財經新聞文本在17個維度上的質量（評分1-10）：

                文本：{text}

                評估維度：
                1. 語法正確性 (1-10)
                2. 信息完整性 (1-10)
                3. 專業性 (1-10)
                4. 可讀性 (1-10)
                5. 信息價值 (1-10)
                6. 數據支撐 (1-10)
                7. 客觀性 (1-10)
                8. 時效性指標 (1-10)
                9. 來源可信度標記 (1-10)
                10. 事實密度（每100字的事實數）
                11. 引用質量 (1-10)
                12. 交叉引用質量 (1-10)
                13. 市場相關性 (1-10)
                14. 監管合規指標 (1-10)
                15. 獨特性/原創性 (1-10)
                16. 表達清晰度 (1-10)
                17. 投資者可操作性 (1-10)

                同時識別：
                - 關鍵事實和數據
                - 潛在偏見或誤導信息
                - 缺失的關鍵信息
                - 改進建議

                請以JSON格式返回綜合評估結果。
                """,
                'pattern_analysis': """
                分析以下批量財經新聞質量評估中的模式：

                {results_summary}

                識別：
                1. 文章中的常見質量問題
                2. 按股票、時間段或主題的模式
                3. 系統性偏見或缺口
                4. 需要關注的異常
                5. 數據改進的具體建議

                請以JSON格式返回詳細分析。
                """
            }
        }

    def analyze_temporal_distribution(self) -> Dict:
        """增強的時間分佈分析"""
        self.logger.info("執行增強時間分佈分析...")

        # 確保Date欄位是datetime類型
        if not pd.api.types.is_datetime64_any_dtype(self.df['Date']):
            self.df['Date'] = pd.to_datetime(self.df['Date'])

        # 基礎時間分析
        self.df['year_month'] = self.df['Date'].dt.to_period('M')
        self.df['quarter'] = self.df['Date'].dt.to_period('Q')
        self.df['year'] = self.df['Date'].dt.year
        self.df['month'] = self.df['Date'].dt.month
        self.df['weekday'] = self.df['Date'].dt.dayofweek
        self.df['hour'] = pd.to_datetime(self.df['Date']).dt.hour if 'timestamp' in self.df.columns else 0

        # 按不同時間粒度統計
        temporal_stats = {
            'monthly': self.df.groupby('year_month').size().to_dict(),
            'quarterly': self.df.groupby('quarter').size().to_dict(),
            'weekly_pattern': self.df.groupby(self.df['Date'].dt.dayofweek).size().to_dict(),
            'yearly_trend': self.df.groupby('year').size().to_dict()
        }

        # 識別特殊時期（財報季、假期等）
        earnings_seasons = self._identify_earnings_seasons()
        market_events = self._identify_market_events()

        # 找出新聞稀疏和密集時期
        monthly_counts = self.df.groupby('year_month').size()
        sparse_periods = monthly_counts[monthly_counts < monthly_counts.quantile(0.1)]
        dense_periods = monthly_counts[monthly_counts > monthly_counts.quantile(0.9)]

        # 生成增強熱力圖
        self._create_enhanced_heatmap()

        # 計算覆蓋空白
        coverage_gaps = self._find_coverage_gaps()

        return {
            'temporal_statistics': temporal_stats,
            'earnings_seasons_analysis': earnings_seasons,
            'market_events_correlation': market_events,
            'sparse_periods': sparse_periods.index.astype(str).tolist(),
            'dense_periods': dense_periods.index.astype(str).tolist(),
            'coverage_gaps': coverage_gaps,
            'temporal_quality_correlation': self._analyze_temporal_quality_correlation()
        }

    def _identify_earnings_seasons(self) -> Dict:
        """識別財報季模式"""
        # 財報季通常在1、4、7、10月
        earnings_months = [1, 4, 7, 10]

        earnings_data = self.df[self.df['month'].isin(earnings_months)].copy()
        regular_data = self.df[~self.df['month'].isin(earnings_months)].copy()

        return {
            'earnings_season_coverage': len(earnings_data) / len(self.df),
            'avg_news_earnings_season': len(earnings_data) / len(earnings_months),
            'avg_news_regular_season': len(regular_data) / (12 - len(earnings_months)),
            'sentiment_diff': earnings_data['Sentiment'].mean() - regular_data['Sentiment'].mean()
        }

    def _identify_market_events(self) -> List[Dict]:
        """識別重大市場事件"""
        # 簡化版：通過新聞激增識別事件
        daily_counts = self.df.groupby(self.df['Date'].dt.date).size()
        threshold = daily_counts.mean() + 2 * daily_counts.std()

        events = []
        for date, count in daily_counts[daily_counts > threshold].items():
            event_news = self.df[self.df['Date'].dt.date == date]
            events.append({
                'date': str(date),
                'news_count': int(count),
                'avg_sentiment': float(event_news['Sentiment'].mean()),
                'top_stocks': event_news['Stock_symbol'].value_counts().head(3).to_dict()
            })

        return events

    def _create_enhanced_heatmap(self):
        """創建增強的時間分佈熱力圖"""
        # 準備數據
        pivot_data = self.df.groupby(['Stock_symbol', 'year', 'month']).size().reset_index(name='count')
        pivot_table = pivot_data.pivot_table(
            index='Stock_symbol',
            columns=['year', 'month'],
            values='count',
            fill_value=0
        )

        # 創建圖表
        plt.figure(figsize=(20, 12))

        # 主熱力圖
        ax1 = plt.subplot(2, 1, 1)
        sns.heatmap(pivot_table, cmap='YlOrRd', cbar_kws={'label': 'News Count'},
                    ax=ax1, xticklabels=3)
        ax1.set_title('News Distribution by Stock and Time', fontsize=16)
        ax1.set_xlabel('Year-Month')
        ax1.set_ylabel('Stock Symbol')

        # 時間序列趨勢
        ax2 = plt.subplot(2, 1, 2)
        monthly_total = self.df.groupby('year_month').size()
        monthly_total.plot(ax=ax2, kind='line', figsize=(20, 4))
        ax2.set_title('Monthly News Volume Trend', fontsize=14)
        ax2.set_xlabel('Time')
        ax2.set_ylabel('News Count')
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('enhanced_temporal_heatmap.png', dpi=300, bbox_inches='tight')
        plt.close()

    def _analyze_temporal_quality_correlation(self) -> Dict:
        """分析時間與質量的關聯"""
        if 'importance_score' not in self.df.columns:
            return {}

        # 按時間段計算平均質量
        quality_by_time = {
            'by_year': self.df.groupby('year')['importance_score'].mean().to_dict(),
            'by_month': self.df.groupby('month')['importance_score'].mean().to_dict(),
            'by_weekday': self.df.groupby('weekday')['importance_score'].mean().to_dict()
        }

        # 找出質量最高和最低的時期
        yearly_quality = self.df.groupby('year')['importance_score'].mean()

        return {
            'quality_trends': quality_by_time,
            'best_quality_year': int(yearly_quality.idxmax()),
            'worst_quality_year': int(yearly_quality.idxmin()),
            'quality_improvement_rate': float(
                (yearly_quality.iloc[-1] - yearly_quality.iloc[0]) / yearly_quality.iloc[0]
            )
        }

    def analyze_content_quality(self, sample_size: int = 200) -> Dict:
        """增強的內容質量分析"""
        self.logger.info("執行增強內容質量分析...")

        results = {
            'readability_scores': self._calculate_enhanced_readability(),
            'duplicate_analysis': self._analyze_duplicates_advanced(),
            'language_quality': self._check_language_quality_enhanced(sample_size),
            'information_density': self._calculate_information_density(),
            'linguistic_features': self._analyze_linguistic_features(),
            'topic_coherence': self._analyze_topic_coherence(),
            'fact_checking_indicators': self._identify_fact_checking_needs()
        }

        return results

    def _calculate_enhanced_readability(self) -> Dict:
        """計算多種可讀性指標"""
        try:
            from textstat import (
                flesch_reading_ease, flesch_kincaid_grade, gunning_fog,
                automated_readability_index, coleman_liau_index,
                linsear_write_formula, dale_chall_readability_score,
                text_standard
            )
        except ImportError:
            self.logger.warning("textstat not installed, using fallback method")
            return self._calculate_basic_readability()

        sample = self.df.sample(n=min(1000, len(self.df)))

        readability_metrics = {
            'flesch_reading_ease': [],
            'flesch_kincaid_grade': [],
            'gunning_fog': [],
            'automated_readability': [],
            'coleman_liau': [],
            'linsear_write': [],
            'dale_chall': [],
            'consensus_grade': []
        }

        for text in sample['News_text']:
            if text and len(text) > 50:
                try:
                    readability_metrics['flesch_reading_ease'].append(flesch_reading_ease(text))
                    readability_metrics['flesch_kincaid_grade'].append(flesch_kincaid_grade(text))
                    readability_metrics['gunning_fog'].append(gunning_fog(text))
                    readability_metrics['automated_readability'].append(automated_readability_index(text))
                    readability_metrics['coleman_liau'].append(coleman_liau_index(text))
                    readability_metrics['linsear_write'].append(linsear_write_formula(text))
                    readability_metrics['dale_chall'].append(dale_chall_readability_score(text))

                    # 獲取綜合等級
                    grade = text_standard(text, float_output=True)
                    readability_metrics['consensus_grade'].append(grade)
                except:
                    continue

        # 計算統計數據
        stats = {}
        for metric, values in readability_metrics.items():
            if values:
                stats[metric] = {
                    'mean': float(np.mean(values)),
                    'std': float(np.std(values)),
                    'min': float(np.min(values)),
                    'max': float(np.max(values)),
                    'median': float(np.median(values))
                }

        # 解釋性分析
        avg_grade = np.mean(readability_metrics.get('consensus_grade', [12]))
        interpretation = {
            'average_grade_level': avg_grade,
            'interpretation': self._interpret_readability(avg_grade),
            'recommendation': self._readability_recommendation(avg_grade)
        }

        return {
            'metrics': stats,
            'interpretation': interpretation
        }

    def _interpret_readability(self, grade_level: float) -> str:
        """解釋可讀性等級"""
        if grade_level < 6:
            return "非常容易理解（小學水平）"
        elif grade_level < 9:
            return "容易理解（初中水平）"
        elif grade_level < 13:
            return "標準難度（高中水平）"
        elif grade_level < 16:
            return "較難理解（大學水平）"
        else:
            return "非常困難（研究生水平）"

    def _readability_recommendation(self, grade_level: float) -> str:
        """提供可讀性改進建議"""
        if grade_level < 10:
            return "可讀性良好，適合大眾投資者"
        elif grade_level < 14:
            return "可讀性適中，適合有經驗的投資者"
        else:
            return "建議簡化語言，使用更短的句子和常用詞彙"

    def _analyze_duplicates_advanced(self) -> Dict:
        """進階重複內容分析"""
        try:
            from datasketch import MinHash, MinHashLSH
        except ImportError:
            self.logger.warning("datasketch not installed, using fallback method")
            return self._analyze_duplicates_fallback()

        # 使用 MinHash 進行大規模相似度檢測
        sample_size = min(2000, len(self.df))
        sample = self.df.sample(n=sample_size)

        # 設置 LSH
        lsh = MinHashLSH(threshold=0.7, num_perm=128)
        minhashes = {}

        # 創建 MinHash
        for idx, text in enumerate(sample['News_text'].fillna('')):
            if len(text) > 50:
                m = MinHash(num_perm=128)
                for word in text.split():
                    m.update(word.encode('utf8'))
                lsh.insert(f"doc_{idx}", m)
                minhashes[f"doc_{idx}"] = m

        # 找出相似文檔群
        similar_groups = []
        processed = set()

        for key, minhash in minhashes.items():
            if key not in processed:
                similar = lsh.query(minhash)
                if len(similar) > 1:
                    similar_groups.append(similar)
                    processed.update(similar)

        # 計算詳細相似度
        detailed_similarities = []
        for group in similar_groups[:10]:  # 只分析前10組
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    idx1 = int(group[i].split('_')[1])
                    idx2 = int(group[j].split('_')[1])

                    # 計算 Jaccard 相似度
                    similarity = minhashes[group[i]].jaccard(minhashes[group[j]])

                    detailed_similarities.append({
                        'doc1_index': sample.index[idx1],
                        'doc2_index': sample.index[idx2],
                        'similarity': similarity,
                        'doc1_stock': sample.iloc[idx1]['Stock_symbol'],
                        'doc2_stock': sample.iloc[idx2]['Stock_symbol'],
                        'same_stock': sample.iloc[idx1]['Stock_symbol'] == sample.iloc[idx2]['Stock_symbol']
                    })

        return {
            'total_documents': len(minhashes),
            'similar_groups_found': len(similar_groups),
            'estimated_duplicate_rate': len([g for g in similar_groups if len(g) > 1]) / len(minhashes) if len(minhashes) > 0 else 0,
            'cross_stock_duplicates': sum(1 for s in detailed_similarities if not s['same_stock']),
            'top_similar_pairs': sorted(detailed_similarities,
                                        key=lambda x: x['similarity'],
                                        reverse=True)[:5]
        }

    def _analyze_duplicates_fallback(self) -> Dict:
        """備用重複檢測方法（不依賴 datasketch）"""
        sample = self.df.sample(n=min(1000, len(self.df)))
        
        # 使用 TF-IDF 向量化
        vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        texts = sample['News_text'].fillna('')
        
        try:
            tfidf_matrix = vectorizer.fit_transform(texts)
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
            # 找出高相似度對
            threshold = 0.8
            similar_pairs = []
            
            for i in range(len(similarity_matrix)):
                for j in range(i + 1, len(similarity_matrix)):
                    if similarity_matrix[i][j] > threshold:
                        similar_pairs.append({
                            'doc1_index': sample.index[i],
                            'doc2_index': sample.index[j],
                            'similarity': float(similarity_matrix[i][j]),
                            'same_stock': sample.iloc[i]['Stock_symbol'] == sample.iloc[j]['Stock_symbol']
                        })
            
            return {
                'method': 'tfidf_cosine',
                'total_documents': len(sample),
                'similar_pairs_found': len(similar_pairs),
                'estimated_duplicate_rate': len(similar_pairs) / len(sample) if len(sample) > 0 else 0,
                'cross_stock_duplicates': sum(1 for s in similar_pairs if not s['same_stock']),
                'top_similar_pairs': sorted(similar_pairs, key=lambda x: x['similarity'], reverse=True)[:5]
            }
            
        except Exception as e:
            self.logger.warning(f"Fallback duplicate detection failed: {e}")
            return {'status': 'failed', 'error': str(e)}

    def _check_language_quality_enhanced(self, sample_size: int) -> Dict:
        """使用增強的品質維度檢查語言質量"""
        if not self.openai_key:
            return {'status': 'skipped - no API key'}

        from openai import OpenAI
        client = OpenAI(
            api_key=self.openai_key,
            timeout=httpx.Timeout(1800.0, connect=60.0)
        )

        sample = self.df.sample(n=min(sample_size, len(self.df)))
        quality_assessments = []

        # 獲取對應語言的提示詞
        prompt = self.prompts[self.language]['quality_check']

        # 批次處理
        batch_size = 10
        for i in range(0, len(sample), batch_size):
            batch = sample.iloc[i:i + batch_size]
            self.logger.info(f"語言質量檢查批次 {i // batch_size + 1}")

            for _, row in batch.iterrows():
                try:
                    response = self._call_quality_api(client, prompt.format(text=row['News_text'][:1000]))

                    assessment = json.loads(response.choices[0].message.content)

                    # 創建品質維度對象
                    dimensions = QualityDimensions(
                        grammar=assessment.get('scores', {}).get('grammar', 5),
                        completeness=assessment.get('scores', {}).get('completeness', 5),
                        professionalism=assessment.get('scores', {}).get('professionalism', 5),
                        readability=assessment.get('scores', {}).get('readability', 5),
                        information_value=assessment.get('scores', {}).get('information_value', 5),
                        data_support=assessment.get('scores', {}).get('data_support', 5),
                        objectivity=assessment.get('scores', {}).get('objectivity', 5),
                        timeliness=assessment.get('scores', {}).get('timeliness', 5),
                        source_credibility=assessment.get('scores', {}).get('source_credibility', 5),
                        fact_density=assessment.get('scores', {}).get('fact_density', 5),
                        citation_quality=assessment.get('scores', {}).get('citation_quality', 5),
                        cross_reference=assessment.get('scores', {}).get('cross_reference', 5),
                        market_relevance=assessment.get('scores', {}).get('market_relevance', 5),
                        regulatory_compliance=assessment.get('scores', {}).get('regulatory_compliance', 5),
                        uniqueness=assessment.get('scores', {}).get('uniqueness', 5),
                        clarity=assessment.get('scores', {}).get('clarity', 5),
                        actionability=assessment.get('scores', {}).get('actionability', 5)
                    )

                    assessment['overall_score'] = dimensions.overall_score
                    assessment['dimensions'] = dimensions.to_dict()
                    quality_assessments.append(assessment)

                except Exception as e:
                    self.logger.warning(f"Quality assessment failed: {e}")

        if quality_assessments:
            # 統計分析
            dimension_stats = self._calculate_dimension_statistics(quality_assessments)
            issue_analysis = self._analyze_common_issues(quality_assessments)

            return {
                'sample_size': len(quality_assessments),
                'dimension_statistics': dimension_stats,
                'overall_quality_score': np.mean([a['overall_score'] for a in quality_assessments]),
                'common_issues': issue_analysis,
                'quality_distribution': self._create_quality_distribution(quality_assessments),
                'recommendations': self._generate_quality_recommendations(dimension_stats)
            }

        return {'status': 'failed'}

    def _call_quality_api(self, client, prompt: str):
        """調用品質檢查 API"""
        if self.model in ['o3', 'o4-mini']:
            return client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                reasoning_effort="medium",
                max_completion_tokens=3000,
                service_tier="flex" if self.use_flex else "default"
            )
        else:
            return client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=3000
            )

    def _calculate_dimension_statistics(self, assessments: List[Dict]) -> Dict:
        """計算各維度的統計數據"""
        dimension_scores = {}

        # 收集所有維度分數
        for assessment in assessments:
            for dim, score in assessment.get('dimensions', {}).items():
                if dim not in dimension_scores:
                    dimension_scores[dim] = []
                dimension_scores[dim].append(score)

        # 計算統計
        stats = {}
        for dim, scores in dimension_scores.items():
            if scores:
                stats[dim] = {
                    'mean': float(np.mean(scores)),
                    'std': float(np.std(scores)),
                    'min': float(np.min(scores)),
                    'max': float(np.max(scores)),
                    'median': float(np.median(scores)),
                    'low_quality_percentage': float(sum(1 for s in scores if s < 6) / len(scores))
                }

        return stats

    def _analyze_common_issues(self, assessments: List[Dict]) -> Dict:
        """分析常見問題"""
        all_issues = []
        issue_categories = {
            'grammar': [],
            'completeness': [],
            'objectivity': [],
            'data_quality': [],
            'clarity': []
        }

        for assessment in assessments:
            issues = assessment.get('issues', [])
            all_issues.extend(issues)

            # 分類問題
            for issue in issues:
                issue_lower = issue.lower()
                if any(word in issue_lower for word in ['grammar', 'spelling', 'punctuation']):
                    issue_categories['grammar'].append(issue)
                elif any(word in issue_lower for word in ['missing', 'incomplete', 'lack']):
                    issue_categories['completeness'].append(issue)
                elif any(word in issue_lower for word in ['bias', 'subjective', 'opinion']):
                    issue_categories['objectivity'].append(issue)
                elif any(word in issue_lower for word in ['data', 'number', 'fact', 'source']):
                    issue_categories['data_quality'].append(issue)
                else:
                    issue_categories['clarity'].append(issue)

        # 統計頻率
        issue_frequency = Counter(all_issues)
        category_stats = {
            cat: len(issues) for cat, issues in issue_categories.items()
        }

        return {
            'top_issues': dict(issue_frequency.most_common(10)),
            'issue_categories': category_stats,
            'total_issues': len(all_issues)
        }

    def _create_quality_distribution(self, assessments: List[Dict]) -> Dict:
        """創建質量分佈圖"""
        overall_scores = [a['overall_score'] for a in assessments]

        plt.figure(figsize=(10, 6))
        plt.hist(overall_scores, bins=20, edgecolor='black', alpha=0.7)
        plt.axvline(np.mean(overall_scores), color='red', linestyle='--',
                    label=f'Mean: {np.mean(overall_scores):.2f}')
        plt.xlabel('Overall Quality Score')
        plt.ylabel('Frequency')
        plt.title('Distribution of News Quality Scores')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig('quality_score_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()

        # 計算分位數
        percentiles = np.percentile(overall_scores, [10, 25, 50, 75, 90])

        return {
            'mean': float(np.mean(overall_scores)),
            'std': float(np.std(overall_scores)),
            'percentiles': {
                '10th': float(percentiles[0]),
                '25th': float(percentiles[1]),
                '50th': float(percentiles[2]),
                '75th': float(percentiles[3]),
                '90th': float(percentiles[4])
            }
        }

    def _generate_quality_recommendations(self, dimension_stats: Dict) -> List[str]:
        """基於維度統計生成改進建議"""
        recommendations = []

        # 檢查每個維度
        critical_dimensions = []
        for dim, stats in dimension_stats.items():
            if stats['mean'] < 6:
                critical_dimensions.append((dim, stats['mean']))

        # 排序並生成建議
        critical_dimensions.sort(key=lambda x: x[1])

        for dim, score in critical_dimensions[:5]:
            if dim == 'data_support':
                recommendations.append(
                    f"增強數據支撐（當前平均分: {score:.1f}）：添加更多具體數據、統計和引用"
                )
            elif dim == 'clarity':
                recommendations.append(
                    f"提高表達清晰度（當前平均分: {score:.1f}）：簡化複雜句子，使用明確的術語"
                )
            elif dim == 'source_credibility':
                recommendations.append(
                    f"改善來源可信度（當前平均分: {score:.1f}）：引用權威來源，標註信息出處"
                )
            elif dim == 'timeliness':
                recommendations.append(
                    f"增強時效性（當前平均分: {score:.1f}）：確保新聞及時更新，標註時間戳"
                )
            elif dim == 'actionability':
                recommendations.append(
                    f"提高可操作性（當前平均分: {score:.1f}）：提供具體的投資建議或行動指引"
                )

        return recommendations

    def _analyze_linguistic_features(self) -> Dict:
        """分析語言特徵"""
        sample = self.df.sample(n=min(500, len(self.df)))

        features = {
            'avg_sentence_length': [],
            'avg_word_length': [],
            'vocabulary_richness': [],
            'sentiment_consistency': []
        }

        for text in sample['News_text']:
            if text and len(text) > 50:
                # 句子長度
                sentences = re.split(r'[.!?]+', text)
                avg_sent_len = np.mean([len(s.split()) for s in sentences if s.strip()])
                features['avg_sentence_length'].append(avg_sent_len)

                # 詞彙長度
                words = text.split()
                avg_word_len = np.mean([len(w) for w in words])
                features['avg_word_length'].append(avg_word_len)

                # 詞彙豐富度（Type-Token Ratio）
                unique_words = set(words)
                ttr = len(unique_words) / len(words) if words else 0
                features['vocabulary_richness'].append(ttr)

        return {
            'sentence_length': {
                'mean': float(np.mean(features['avg_sentence_length'])),
                'std': float(np.std(features['avg_sentence_length']))
            },
            'word_length': {
                'mean': float(np.mean(features['avg_word_length'])),
                'std': float(np.std(features['avg_word_length']))
            },
            'vocabulary_richness': {
                'mean': float(np.mean(features['vocabulary_richness'])),
                'std': float(np.std(features['vocabulary_richness']))
            }
        }

    def _analyze_topic_coherence(self) -> Dict:
        """分析主題連貫性"""
        from sklearn.decomposition import LatentDirichletAllocation
        from sklearn.feature_extraction.text import CountVectorizer

        # 準備數據
        sample = self.df.sample(n=min(1000, len(self.df)))
        texts = sample['News_text'].fillna('')

        # 向量化
        vectorizer = CountVectorizer(
            max_features=500,
            stop_words='english',
            min_df=5,
            max_df=0.8
        )

        try:
            doc_term_matrix = vectorizer.fit_transform(texts)

            # LDA 主題建模
            n_topics = 10
            lda = LatentDirichletAllocation(
                n_components=n_topics,
                random_state=42,
                max_iter=10
            )
            lda.fit(doc_term_matrix)

            # 計算主題連貫性
            feature_names = vectorizer.get_feature_names_out()
            topics = []

            for topic_idx, topic in enumerate(lda.components_):
                top_indices = topic.argsort()[-10:][::-1]
                top_words = [feature_names[i] for i in top_indices]
                topics.append({
                    'topic_id': topic_idx,
                    'keywords': top_words,
                    'coherence': self._calculate_topic_coherence_score(top_words, texts)
                })

            return {
                'n_topics': n_topics,
                'topics': topics,
                'avg_coherence': float(np.mean([t['coherence'] for t in topics]))
            }

        except Exception as e:
            self.logger.warning(f"Topic coherence analysis failed: {e}")
            return {'status': 'failed', 'error': str(e)}

    def _calculate_topic_coherence_score(self, words: List[str], texts: pd.Series) -> float:
        """計算主題連貫性分數"""
        # 簡化版連貫性計算
        co_occurrences = 0
        total_pairs = 0

        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                total_pairs += 1
                # 計算共現次數
                co_occur = sum(1 for text in texts if words[i] in text and words[j] in text)
                if co_occur > 0:
                    co_occurrences += 1

        return co_occurrences / total_pairs if total_pairs > 0 else 0

    def _identify_fact_checking_needs(self) -> Dict:
        """識別需要事實核查的內容"""
        sample = self.df.sample(n=min(500, len(self.df)))

        fact_check_indicators = {
            'unverified_claims': [],
            'suspicious_numbers': [],
            'missing_sources': [],
            'conflicting_info': []
        }

        # 定義需要核查的模式
        claim_patterns = [
            r'reportedly', r'allegedly', r'sources say', r'rumored',
            r'unconfirmed', r'speculation', r'could be', r'might'
        ]

        number_pattern = r'\b\d+\.?\d*\s*(?:billion|million|thousand|%|percent)\b'

        for idx, row in sample.iterrows():
            text = row['News_text'].lower()

            # 檢查未經證實的聲明
            for pattern in claim_patterns:
                if re.search(pattern, text):
                    fact_check_indicators['unverified_claims'].append({
                        'index': idx,
                        'pattern': pattern,
                        'stock': row['Stock_symbol']
                    })
                    break

            # 檢查可疑數字
            numbers = re.findall(number_pattern, text)
            if len(numbers) > 5:  # 過多數字可能需要核實
                fact_check_indicators['suspicious_numbers'].append({
                    'index': idx,
                    'number_count': len(numbers),
                    'stock': row['Stock_symbol']
                })

            # 檢查缺少來源
            if 'according to' not in text and 'reported' not in text and len(text) > 200:
                fact_check_indicators['missing_sources'].append({
                    'index': idx,
                    'stock': row['Stock_symbol']
                })

        return {
            'unverified_claims_count': len(fact_check_indicators['unverified_claims']),
            'suspicious_numbers_count': len(fact_check_indicators['suspicious_numbers']),
            'missing_sources_count': len(fact_check_indicators['missing_sources']),
            'fact_check_priority_percentage': (
                    len(set(
                        [item['index'] for sublist in fact_check_indicators.values()
                         for item in sublist]
                    )) / len(sample)
            )
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

    def _calculate_information_density(self) -> Dict:
        """計算信息密度"""
        # 多種 NLP 庫的兼容性處理
        try:
            import spacy
            nlp = spacy.load("en_core_web_sm")
            use_spacy = True
        except:
            use_spacy = False
            self.logger.warning("SpaCy not available, using basic entity detection")

        sample = self.df.sample(n=min(100, len(self.df)))
        entity_counts = []
        financial_terms_density = []

        # 金融術語列表
        financial_terms = {
            'metrics': ['revenue', 'earnings', 'EPS', 'P/E', 'profit', 'margin', 'growth'],
            'actions': ['buy', 'sell', 'hold', 'upgrade', 'downgrade', 'merger', 'acquisition'],
            'indicators': ['bull', 'bear', 'volatility', 'momentum', 'trend', 'resistance', 'support']
        }

        for text in sample['News_text']:
            if text and len(text) > 50:
                if use_spacy:
                    doc = nlp(text[:1000])  # 限制長度
                    entities = len([ent for ent in doc.ents if ent.label_ in
                                    ['ORG', 'PERSON', 'MONEY', 'PERCENT', 'DATE']])
                    entity_density = entities / len(doc) if len(doc) > 0 else 0
                else:
                    # 基礎實體識別
                    entities = len(re.findall(r'\$[\d,]+\.?\d*[MBK]?|\d+%', text))
                    words = len(text.split())
                    entity_density = entities / words if words > 0 else 0

                entity_counts.append(entity_density)

                # 計算金融術語密度
                text_lower = text.lower()
                term_count = sum(1 for category in financial_terms.values()
                                 for term in category if term in text_lower)
                term_density = term_count / len(text.split()) if text.split() else 0
                financial_terms_density.append(term_density)

        return {
            'entity_density': {
                'mean': float(np.mean(entity_counts)),
                'std': float(np.std(entity_counts))
            },
            'financial_terms_density': {
                'mean': float(np.mean(financial_terms_density)),
                'std': float(np.std(financial_terms_density))
            },
            'information_richness_score': float(
                np.mean(entity_counts) * 0.6 + np.mean(financial_terms_density) * 0.4
            )
        }

    def analyze_stock_coverage_balance(self) -> Dict:
        """分析股票覆蓋平衡性"""
        self.logger.info("分析股票覆蓋平衡性...")

        stock_stats = self.df.groupby('Stock_symbol').agg({
            'News_title': 'count',
            'Sentiment': ['mean', 'std'],
            'importance_score': ['mean', 'std'] if 'importance_score' in self.df.columns else 'mean',
            'Date': ['min', 'max']
        })

        # 扁平化列名
        stock_stats.columns = ['_'.join(col).strip() for col in stock_stats.columns.values]
        stock_stats = stock_stats.rename(columns={
            'News_title_count': 'news_count',
            'Sentiment_mean': 'avg_sentiment',
            'Sentiment_std': 'sentiment_volatility',
            'Date_min': 'first_news',
            'Date_max': 'last_news'
        })

        # 計算 Gini 係數和其他不平衡指標
        gini = self._calculate_gini(stock_stats['news_count'].values)
        herfindahl = self._calculate_herfindahl_index(stock_stats['news_count'].values)

        # 找出異常股票
        median_count = stock_stats['news_count'].median()
        undercovered = stock_stats[stock_stats['news_count'] < median_count * 0.5]
        overcovered = stock_stats[stock_stats['news_count'] > median_count * 2]

        # 計算覆蓋一致性
        coverage_consistency = self._calculate_coverage_consistency()

        return {
            'balance_metrics': {
                'gini_coefficient': float(gini),
                'herfindahl_index': float(herfindahl),
                'coverage_ratio': float(stock_stats['news_count'].max() / stock_stats['news_count'].min())
            },
            'coverage_stats': stock_stats.describe().to_dict(),
            'undercovered_stocks': {
                'count': len(undercovered),
                'stocks': undercovered.index.tolist(),
                'avg_news_count': float(undercovered['news_count'].mean())
            },
            'overcovered_stocks': {
                'count': len(overcovered),
                'stocks': overcovered.index.tolist(),
                'avg_news_count': float(overcovered['news_count'].mean())
            },
            'coverage_consistency': coverage_consistency,
            'sentiment_balance': self._analyze_sentiment_balance(stock_stats)
        }

    def _calculate_gini(self, values):
        """計算 Gini 係數"""
        sorted_values = np.sort(values)
        n = len(values)
        index = np.arange(1, n + 1)
        return (2 * np.sum(index * sorted_values)) / (n * np.sum(sorted_values)) - (n + 1) / n

    def _calculate_herfindahl_index(self, values):
        """計算赫芬達爾指數"""
        total = np.sum(values)
        shares = values / total
        return np.sum(shares ** 2)

    def _calculate_coverage_consistency(self) -> Dict:
        """計算覆蓋一致性"""
        # 按月計算每隻股票的新聞數量變異係數
        monthly_coverage = self.df.groupby([
            self.df['Date'].dt.to_period('M'),
            'Stock_symbol'
        ]).size().unstack(fill_value=0)

        consistency_scores = {}
        for stock in monthly_coverage.columns:
            counts = monthly_coverage[stock]
            if counts.mean() > 0:
                cv = counts.std() / counts.mean()  # 變異係數
                consistency_scores[stock] = 1 / (1 + cv)  # 轉換為一致性分數

        return {
            'avg_consistency': float(np.mean(list(consistency_scores.values()))),
            'most_consistent': sorted(consistency_scores.items(),
                                      key=lambda x: x[1], reverse=True)[:5],
            'least_consistent': sorted(consistency_scores.items(),
                                       key=lambda x: x[1])[:5]
        }

    def _analyze_sentiment_balance(self, stock_stats: pd.DataFrame) -> Dict:
        """分析情感平衡性"""
        # 計算整體情感分佈
        sentiment_distribution = {
            'positive_stocks': len(stock_stats[stock_stats['avg_sentiment'] > 0.1]),
            'neutral_stocks': len(stock_stats[
                                      (stock_stats['avg_sentiment'] >= -0.1) &
                                      (stock_stats['avg_sentiment'] <= 0.1)
                                      ]),
            'negative_stocks': len(stock_stats[stock_stats['avg_sentiment'] < -0.1])
        }

        # 找出情感極端的股票
        extreme_positive = stock_stats.nlargest(5, 'avg_sentiment')
        extreme_negative = stock_stats.nsmallest(5, 'avg_sentiment')

        return {
            'distribution': sentiment_distribution,
            'extreme_positive': extreme_positive[['news_count', 'avg_sentiment']].to_dict(),
            'extreme_negative': extreme_negative[['news_count', 'avg_sentiment']].to_dict(),
            'sentiment_spread': float(
                stock_stats['avg_sentiment'].max() - stock_stats['avg_sentiment'].min()
            )
        }

    def generate_comprehensive_report(self, output_file: str = 'comprehensive_quality_report.json'):
        """生成綜合質量報告"""
        self.logger.info("生成增強版綜合質量報告...")

        report = {
            'metadata': {
                'total_records': len(self.df),
                'analysis_date': datetime.now().isoformat(),
                'data_file': self.data_path,
                'language': self.language.value,
                'analysis_version': '2.0'
            },
            'temporal_analysis': self.analyze_temporal_distribution(),
            'content_quality': self.analyze_content_quality(),
            'coverage_balance': self.analyze_stock_coverage_balance(),
            'advanced_metrics': {
                'anomaly_detection': self._detect_anomalies(),
                'trend_analysis': self._analyze_quality_trends(),
                'correlation_analysis': self._analyze_correlations()
            },
            'recommendations': self._generate_comprehensive_recommendations(),
            'executive_summary': self._generate_executive_summary()
        }

        # 保存報告
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        # 生成視覺化報告
        self._generate_visual_report(report)

        self.logger.info(f"增強版報告已保存到 {output_file}")
        return report

    def _detect_anomalies(self) -> Dict:
        """異常檢測"""
        features = []
        feature_names = ['text_length', 'title_length', 'Sentiment']

        if 'importance_score' in self.df.columns:
            feature_names.append('importance_score')

        # 準備特徵
        for col in feature_names:
            if col in self.df.columns:
                features.append(self.df[col].fillna(0).values.reshape(-1, 1))

        if not features:
            return {'status': 'no features available'}

        # 組合特徵
        X = np.hstack(features)

        # 標準化
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # 異常檢測
        iso_forest = IsolationForest(contamination=0.05, random_state=42)
        anomalies = iso_forest.fit_predict(X_scaled)

        # 分析異常
        anomaly_indices = np.where(anomalies == -1)[0]
        anomaly_df = self.df.iloc[anomaly_indices]

        # 異常特徵分析
        anomaly_characteristics = {
            'total_anomalies': len(anomaly_indices),
            'anomaly_rate': len(anomaly_indices) / len(self.df),
            'by_stock': anomaly_df['Stock_symbol'].value_counts().head(10).to_dict(),
            'by_year': anomaly_df['year'].value_counts().to_dict() if 'year' in anomaly_df.columns else {},
            'anomaly_patterns': self._analyze_anomaly_patterns(anomaly_df, self.df)
        }

        return anomaly_characteristics

    def _analyze_duplicates_fallback(self) -> Dict:
        """備用的重複分析方法"""
        sample_size = min(1000, len(self.df))
        sample = self.df.sample(n=sample_size)
        
        # 使用 TF-IDF 向量化進行相似度計算
        vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(sample['News_text'].fillna(''))
        
        # 計算相似度矩陣
        similarity_matrix = cosine_similarity(tfidf_matrix)
        
        # 找出相似度超過閾值的文檔對
        threshold = 0.7
        similar_pairs = []
        
        for i in range(len(similarity_matrix)):
            for j in range(i+1, len(similarity_matrix)):
                if similarity_matrix[i][j] > threshold:
                    similar_pairs.append({
                        'doc1_index': sample.index[i],
                        'doc2_index': sample.index[j],
                        'similarity': float(similarity_matrix[i][j]),
                        'doc1_stock': sample.iloc[i]['Stock_symbol'],
                        'doc2_stock': sample.iloc[j]['Stock_symbol']
                    })
        
        return {
            'total_documents': len(sample),
            'similar_pairs_found': len(similar_pairs),
            'estimated_duplicate_rate': len(similar_pairs) / len(sample) if len(sample) > 0 else 0,
            'method': 'fallback_tfidf'
        }

    def _calculate_basic_readability(self) -> Dict:
        """基礎可讀性計算備用方法"""
        sample = self.df.sample(n=min(1000, len(self.df)))
        
        basic_metrics = {
            'avg_word_length': [],
            'avg_sentence_length': [],
            'syllable_count': []
        }
        
        for text in sample['News_text']:
            if text and len(text) > 50:
                words = text.split()
                sentences = len([s for s in text.split('.') if s.strip()])
                
                # 基礎指標
                avg_word_len = sum(len(word) for word in words) / len(words) if words else 0
                avg_sent_len = len(words) / sentences if sentences > 0 else 0
                
                basic_metrics['avg_word_length'].append(avg_word_len)
                basic_metrics['avg_sentence_length'].append(avg_sent_len)
        
        return {
            'metrics': {
                'avg_word_length': {
                    'mean': float(np.mean(basic_metrics['avg_word_length'])),
                    'std': float(np.std(basic_metrics['avg_word_length']))
                },
                'avg_sentence_length': {
                    'mean': float(np.mean(basic_metrics['avg_sentence_length'])),
                    'std': float(np.std(basic_metrics['avg_sentence_length']))
                }
            },
            'interpretation': {
                'method': 'basic_fallback',
                'note': 'Advanced readability metrics unavailable, using basic calculations'
            }
        }

    def _analyze_anomaly_patterns(self, anomaly_df: pd.DataFrame, full_df: pd.DataFrame) -> Dict:
        """分析異常模式"""
        patterns = {}

        # 文本長度異常
        if 'text_length' in anomaly_df.columns:
            avg_length = full_df['text_length'].mean()
            anomaly_avg_length = anomaly_df['text_length'].mean()
            patterns['text_length_pattern'] = {
                'normal_avg': float(avg_length),
                'anomaly_avg': float(anomaly_avg_length),
                'difference': float(anomaly_avg_length - avg_length)
            }

        # 情感異常
        if 'Sentiment' in anomaly_df.columns:
            patterns['sentiment_pattern'] = {
                'extreme_positive': len(anomaly_df[anomaly_df['Sentiment'] > 0.8]),
                'extreme_negative': len(anomaly_df[anomaly_df['Sentiment'] < -0.8]),
                'sentiment_variance': float(anomaly_df['Sentiment'].var())
            }

        return patterns

    def _analyze_quality_trends(self) -> Dict:
        """分析質量趨勢"""
        if 'importance_score' not in self.df.columns:
            return {'status': 'no quality scores available'}

        # 按時間分析質量趨勢
        quality_trends = {
            'yearly': self.df.groupby('year')['importance_score'].agg(['mean', 'std']).to_dict(),
            'monthly': self.df.groupby(
                self.df['Date'].dt.to_period('M')
            )['importance_score'].mean().to_dict()
        }

        # 計算趨勢指標
        yearly_means = self.df.groupby('year')['importance_score'].mean()
        if len(yearly_means) > 1:
            # 簡單線性回歸
            years = np.array(range(len(yearly_means)))
            scores = yearly_means.values
            trend_coefficient = np.polyfit(years, scores, 1)[0]

            quality_trends['trend_analysis'] = {
                'trend_direction': 'improving' if trend_coefficient > 0 else 'declining',
                'trend_strength': float(abs(trend_coefficient)),
                'projected_next_year': float(scores[-1] + trend_coefficient)
            }

        return quality_trends

    def _analyze_correlations(self) -> Dict:
        """分析各指標間的相關性"""
        # 準備數據
        corr_features = ['Sentiment', 'text_length', 'title_length']
        if 'importance_score' in self.df.columns:
            corr_features.append('importance_score')

        # 計算相關性矩陣
        corr_matrix = self.df[corr_features].corr()

        # 找出強相關
        strong_correlations = []
        for i in range(len(corr_features)):
            for j in range(i + 1, len(corr_features)):
                corr_value = corr_matrix.iloc[i, j]
                if abs(corr_value) > 0.5:
                    strong_correlations.append({
                        'feature1': corr_features[i],
                        'feature2': corr_features[j],
                        'correlation': float(corr_value)
                    })

        return {
            'correlation_matrix': corr_matrix.to_dict(),
            'strong_correlations': strong_correlations
        }

    def _generate_comprehensive_recommendations(self) -> List[str]:
        """生成綜合建議"""
        recommendations = []

        # 基於各項分析結果生成建議
        stock_coverage = self.analyze_stock_coverage_balance()
        if stock_coverage['balance_metrics']['gini_coefficient'] > 0.5:
            recommendations.append(
                f"⚠️ 股票覆蓋嚴重不平衡 (Gini={stock_coverage['balance_metrics']['gini_coefficient']:.2f})。"
                f"建議：1) 增加覆蓋不足股票的數據源；2) 平衡熱門股票的報導"
            )

        temporal = self.analyze_temporal_distribution()
        if len(temporal['coverage_gaps']) > 10:
            recommendations.append(
                f"📅 發現 {len(temporal['coverage_gaps'])} 個顯著覆蓋空白期。"
                f"建議：檢查數據收集系統在這些時期的運行狀況"
            )

        # 內容質量建議
        content_quality = self.analyze_content_quality()
        if content_quality.get('readability_scores', {}).get('metrics', {}).get('consensus_grade', {}).get('mean',
                                                                                                           12) > 14:
            recommendations.append(
                "📖 內容可讀性偏低（平均需要大學以上程度）。"
                "建議：簡化語言，使用更短的句子和段落"
            )

        return recommendations

    def _generate_executive_summary(self) -> Dict:
        """生成執行摘要"""
        total_records = len(self.df)
        date_range = f"{self.df['Date'].min().date()} 至 {self.df['Date'].max().date()}"

        # 關鍵指標
        key_metrics = {
            'total_news': total_records,
            'date_coverage': date_range,
            'unique_stocks': self.df['Stock_symbol'].nunique(),
            'avg_news_per_stock': total_records / self.df['Stock_symbol'].nunique(),
            'data_quality_score': 'N/A'  # 需要從其他分析中獲取
        }

        # 主要發現
        key_findings = []

        # 添加基於分析的發現
        coverage = self.analyze_stock_coverage_balance()
        if coverage['balance_metrics']['gini_coefficient'] > 0.6:
            key_findings.append("數據覆蓋存在顯著不平衡")

        return {
            'key_metrics': key_metrics,
            'key_findings': key_findings,
            'data_quality_grade': self._calculate_overall_grade(),
            'priority_actions': self._generate_comprehensive_recommendations()[:3]
        }

    def _calculate_overall_grade(self) -> str:
        """計算整體數據質量等級"""
        # 基於多個指標計算綜合等級
        scores = []

        # 這裡簡化處理，實際應該基於完整分析結果
        if 'importance_score' in self.df.columns:
            avg_importance = self.df['importance_score'].mean()
            scores.append(avg_importance * 10)

        overall_score = np.mean(scores) if scores else 5.0

        if overall_score >= 8:
            return "A"
        elif overall_score >= 7:
            return "B"
        elif overall_score >= 6:
            return "C"
        elif overall_score >= 5:
            return "D"
        else:
            return "F"

    def _generate_visual_report(self, report_data: Dict):
        """生成視覺化報告"""
        # 創建多頁報告
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))

        # 1. 覆蓋平衡圖
        ax1 = axes[0, 0]
        coverage_data = report_data['coverage_balance']['coverage_stats']
        if 'news_count' in coverage_data:
            counts = list(coverage_data['news_count'].values())
            ax1.hist(counts, bins=20, edgecolor='black', alpha=0.7)
            ax1.set_title('News Count Distribution by Stock')
            ax1.set_xlabel('Number of News Articles')
            ax1.set_ylabel('Number of Stocks')

        # 2. 質量分佈圖
        ax2 = axes[0, 1]
        if 'importance_score' in self.df.columns:
            self.df['importance_score'].hist(ax=ax2, bins=20, edgecolor='black', alpha=0.7)
            ax2.set_title('Quality Score Distribution')
            ax2.set_xlabel('Quality Score')
            ax2.set_ylabel('Frequency')

        # 3. 時間趨勢圖
        ax3 = axes[1, 0]
        monthly_counts = self.df.groupby(self.df['Date'].dt.to_period('M')).size()
        monthly_counts.plot(ax=ax3, kind='line')
        ax3.set_title('Monthly News Volume Trend')
        ax3.set_xlabel('Month')
        ax3.set_ylabel('News Count')
        ax3.grid(True, alpha=0.3)

        # 4. 情感分佈圖
        ax4 = axes[1, 1]
        self.df['Sentiment'].hist(ax=ax4, bins=30, edgecolor='black', alpha=0.7)
        ax4.set_title('Sentiment Distribution')
        ax4.set_xlabel('Sentiment Score')
        ax4.set_ylabel('Frequency')
        ax4.axvline(0, color='red', linestyle='--', alpha=0.5)

        plt.suptitle('FinRL News Quality Analysis Report', fontsize=16)
        plt.tight_layout()
        plt.savefig('comprehensive_quality_report.png', dpi=300, bbox_inches='tight')
        plt.close()

    def export_cleaned_subset(self, quality_threshold: float = 0.7,
                              output_file: str = 'high_quality_news.parquet',
                              export_formats: List[str] = ['parquet', 'csv']):
        """導出高質量數據子集（支援多格式）"""
        self.logger.info(f"導出質量分數 >= {quality_threshold} 的數據...")

        # 根據 importance_score 篩選
        if 'importance_score' not in self.df.columns:
            self.logger.warning("No importance_score column, using basic filters")
            high_quality_df = self.df[
                (self.df['title_length'] >= 20) &
                (self.df['text_length'] >= 100)
                ]
        else:
            high_quality_df = self.df[self.df['importance_score'] >= quality_threshold]

        # 額外過濾
        high_quality_df = high_quality_df[
            (high_quality_df['title_length'] >= 20) &
            (high_quality_df['text_length'] >= 100)
            ]

        if 'low_relevance' in high_quality_df.columns:
            high_quality_df = high_quality_df[~high_quality_df['low_relevance']]

        # 導出多種格式
        base_filename = output_file.rsplit('.', 1)[0]

        for format in export_formats:
            try:
                if format == 'parquet':
                    high_quality_df.to_parquet(f'{base_filename}.parquet', index=False)
                elif format == 'csv':
                    high_quality_df.to_csv(f'{base_filename}.csv', index=False, encoding='utf-8-sig')
                elif format == 'excel':
                    high_quality_df.to_excel(f'{base_filename}.xlsx', index=False, engine='openpyxl')
                elif format == 'json':
                    high_quality_df.to_json(f'{base_filename}.json', orient='records',
                                            force_ascii=False, indent=2)

                self.logger.info(f"已導出 {len(high_quality_df)} 條高質量數據到 {base_filename}.{format}")
            except Exception as e:
                self.logger.warning(f"無法導出 {format} 格式: {e}")

        return high_quality_df

    def _count_syllables(self, word: str) -> int:
        """計算單詞的音節數"""
        word = word.lower()
        vowels = "aeiouy"
        count = 0
        prev_char_was_vowel = False
        
        for char in word:
            if char in vowels:
                if not prev_char_was_vowel:
                    count += 1
                prev_char_was_vowel = True
            else:
                prev_char_was_vowel = False
        
        # 處理以 'e' 結尾的詞
        if word.endswith('e') and count > 1:
            count -= 1
        
        return max(1, count)  # 每個詞至少有一個音節


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description='FinRL 新聞數據質量深度分析 v2.0')
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
    parser.add_argument('--language', type=str, default='en',
                        choices=['en', 'zh', 'es', 'jp'],
                        help='分析語言 (預設: en)')
    parser.add_argument('--export-formats', nargs='+',
                        default=['parquet', 'csv'],
                        choices=['parquet', 'csv', 'excel', 'json'],
                        help='導出格式 (預設: parquet csv)')
    args = parser.parse_args()

    # 創建分析器
    language_map = {'en': Language.EN, 'zh': Language.ZH, 'es': Language.ES, 'jp': Language.JP}
    analyzer = NewsQualityAnalyzer(
        data_path=args.data,
        openai_key=args.openai_key,
        language=language_map[args.language]
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
    analyzer.export_cleaned_subset(
        quality_threshold=args.export_threshold,
        export_formats=args.export_formats
    )

    print("\n分析完成！")
    print(f"- 綜合報告: comprehensive_quality_report.json")
    print(f"- 增強熱力圖: enhanced_temporal_heatmap.png")
    print(f"- 質量分佈圖: quality_score_distribution.png")
    print(f"- 視覺化報告: comprehensive_quality_report.png")
    print(f"- 高質量數據子集: high_quality_news.{args.export_formats[0]}")

    if args.model in ['o3', 'o4-mini']:
        print(f"\n使用 {args.model} reasoning 模型進行了深度分析，包含 17 個質量維度評估")
        if args.use_flex:
            print("已啟用 Flex Processing 以優化成本")


if __name__ == "__main__":
    main()