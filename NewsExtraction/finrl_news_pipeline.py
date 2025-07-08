#!/usr/bin/env python3
"""
FinRL 新聞數據完整處理管道
包含：數據抓取、清洗、質量檢查（含 OpenAI API）
"""

import json
import pathlib
import re
import requests
import textwrap
import pandas as pd
import numpy as np
from datetime import datetime
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from datasets import load_dataset
from tqdm import tqdm
import openai
from typing import List, Dict, Tuple
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import httpx

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('finrl_news_pipeline.log'),
        logging.StreamHandler()
    ]
)

class FinRLNewsProcessor:
    def __init__(self, openai_api_key: str = None):
        """初始化處理器"""
        self.logger = logging.getLogger(__name__)
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if self.openai_api_key:
            self.logger.info("OpenAI API 已配置")
        else:
            self.logger.warning("未配置 OpenAI API Key，部分功能將無法使用")
        
        # 設定參數
        self.START_DATE = "2013-01-01"
        self.END_DATE = "2023-12-31"
        self.TICKERS_FILE = "tickers_89.json"
        self.RAW_PARQUET = "news_89_2013_2023_raw.parquet"
        self.CLEANED_PARQUET = "news_89_2013_2023_cleaned.parquet"
        self.QUALITY_REPORT = "data_quality_report.json"
        
        # 模型相關參數（預設使用 o3 + Flex）
        self.model = "o3"
        self.use_flex = True
        self.sample_size = 100
        self.batch_size = 10
        self.reasoning_effort = "medium"
        
    def step1_fetch_tickers(self) -> List[str]:
        """步驟1: 獲取股票代碼列表"""
        self.logger.info("步驟1: 開始獲取股票代碼列表")
        
        RAW_URL = ("https://raw.githubusercontent.com/Open-Finance-Lab/"
                   "FinRL_Contest_2025/main/Task_1_FinRL_DeepSeek_Stock/"
                   "train_trade_data.py")
        
        try:
            code = requests.get(RAW_URL, timeout=10).text
            m = re.search(r"nasdaq_100_tickers_july_17_2023\s*=\s*\[(.*?)\]", code, re.S)
            if not m:
                raise ValueError("無法從代碼中提取股票列表")
                
            tickers = [t.strip().strip('"').strip("'") 
                      for t in m.group(1).split(",") if t.strip()]
            
            pathlib.Path(self.TICKERS_FILE).write_text(json.dumps(tickers, indent=2))
            self.logger.info(f"成功獲取 {len(tickers)} 個股票代碼，已保存到 {self.TICKERS_FILE}")
            return tickers
            
        except Exception as e:
            self.logger.error(f"獲取股票代碼失敗: {e}")
            raise
    
    def step2_download_news(self, tickers: List[str]) -> None:
        """步驟2: 下載新聞數據"""
        self.logger.info("步驟2: 開始下載新聞數據")
        
        TICKERS_SET = set(tickers)
        
        # 載入數據集
        ds = load_dataset("Zihan1004/FNSPID", split="train", streaming=True)
        
        # 建立 Parquet Writer
        schema = pa.schema([
            ('Date', pa.string()),
            ('Stock_symbol', pa.string()),
            ('News_title', pa.string()),
            ('News_text', pa.string()),
            ('Sentiment', pa.float64()),
            ('Topic', pa.string())
        ])
        
        sink = pq.ParquetWriter(self.RAW_PARQUET, schema)
        
        count = 0
        for row in tqdm(ds, desc="下載新聞"):
            if row["Stock_symbol"] in TICKERS_SET and self.START_DATE <= row["Date"][:10] <= self.END_DATE:
                sink.write_table(pa.Table.from_pylist([row], schema=schema))
                count += 1
                
        sink.close()
        self.logger.info(f"成功下載 {count} 條新聞數據")
    
    def step3_basic_cleaning(self) -> pd.DataFrame:
        """步驟3: 基礎數據清洗"""
        self.logger.info("步驟3: 開始基礎數據清洗")
        
        # 讀取原始數據
        df = pd.read_parquet(self.RAW_PARQUET)
        self.logger.info(f"讀取到 {len(df)} 條原始數據")
        
        # 3.1 轉換日期格式
        df['Date'] = pd.to_datetime(df['Date'])
        
        # 3.2 移除重複數據
        before_dedup = len(df)
        df = df.drop_duplicates(subset=['Stock_symbol', 'Date', 'News_title'])
        self.logger.info(f"移除 {before_dedup - len(df)} 條重複數據")
        
        # 3.3 處理缺失值
        df['News_title'] = df['News_title'].fillna('')
        df['News_text'] = df['News_text'].fillna('')
        df['Sentiment'] = df['Sentiment'].fillna(0.0)
        df['Topic'] = df['Topic'].fillna('Unknown')
        
        # 3.4 文本清洗
        def clean_text(text):
            if not text:
                return ""
            # 移除多餘空白
            text = ' '.join(text.split())
            # 移除控制字符
            text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
            return text.strip()
        
        df['News_title'] = df['News_title'].apply(clean_text)
        df['News_text'] = df['News_text'].apply(clean_text)
        
        # 3.5 排序
        df = df.sort_values(['Stock_symbol', 'Date'])
        
        # 3.6 添加基礎特徵
        df['title_length'] = df['News_title'].str.len()
        df['text_length'] = df['News_text'].str.len()
        df['weekday'] = df['Date'].dt.day_name()
        df['month'] = df['Date'].dt.month
        df['year'] = df['Date'].dt.year
        
        self.logger.info(f"基礎清洗完成，剩餘 {len(df)} 條數據")
        return df
    
    def step4_quality_check_with_llm(self, df: pd.DataFrame, sample_size: int = 100) -> Dict:
        """步驟4: 使用 reasoning 模型進行數據質量檢查（Flex processing）"""
        self.logger.info(f"步驟4: 開始使用 {self.model} 模型進行 LLM 數據質量檢查")
        
        if not self.openai_api_key:
            self.logger.warning("未配置 OpenAI API，跳過 LLM 檢查")
            return {}
        
        # 配置 OpenAI 客戶端使用更長的 timeout
        from openai import OpenAI
        client = OpenAI(
            api_key=self.openai_api_key,
            timeout=httpx.Timeout(1800.0, connect=60.0)  # 30分鐘 timeout for Flex processing
        )
        
        quality_results = {
            'relevance_checks': [],
            'sentiment_validation': [],
            'content_quality': [],
            'topic_classification': [],
            'market_impact_analysis': []
        }
        
        # 隨機抽樣
        sample_df = df.sample(n=min(sample_size, len(df)), random_state=42)
        
        # 4.1 使用 reasoning 模型進行綜合分析
        self.logger.info(f"使用 {self.model} 進行綜合新聞分析...")
        
        # 英文 prompt 更適合美股新聞分析
        comprehensive_prompt = """
        Perform a comprehensive analysis of the following financial news related to stock {symbol}.
        
        Title: {title}
        Content: {text_snippet}
        Date: {date}
        Original Sentiment Score: {original_sentiment}
        
        Please provide the following analysis:
        
        1. Relevance Assessment:
           - Relevance score (0-10)
           - Is it directly related to the stock? (true/false)
           - Relevance type (company news/industry news/market news/macroeconomic/unrelated)
           - Impact timing (immediate/short-term/long-term)
        
        2. Sentiment Validation:
           - Actual sentiment score (-1 to 1)
           - Sentiment category (strongly positive/positive/neutral/negative/strongly negative)
           - Is the original score accurate? (true/false)
           - Confidence level (0-10)
        
        3. Content Quality Assessment:
           - Information density (0-10)
           - Credibility (0-10)
           - Contains concrete data or facts? (true/false)
           - Is it rumor or speculation? (true/false)
        
        4. Market Impact Prediction:
           - Expected market reaction (large gain/small gain/neutral/small loss/large loss)
           - Impact duration (hours/days/weeks/months)
           - Impact scope (this stock only/entire sector/entire market)
        
        5. Key Entity and Event Extraction:
           - Key people mentioned
           - Organizations involved
           - Key amounts or percentages
           - Event types
        
        Return a structured JSON response with all numeric values as reasonable numbers:
        {{
            "relevance": {{
                "score": <0-10>,
                "directly_related": <true/false>,
                "type": "...",
                "impact_timing": "..."
            }},
            "sentiment": {{
                "actual_score": <-1 to 1>,
                "category": "...",
                "original_accurate": <true/false>,
                "confidence": <0-10>
            }},
            "content_quality": {{
                "information_density": <0-10>,
                "credibility": <0-10>,
                "has_concrete_data": <true/false>,
                "is_rumor_or_speculation": <true/false>
            }},
            "market_impact": {{
                "expected_reaction": "...",
                "duration": "...",
                "scope": "..."
            }},
            "key_entities": {{
                "people": [],
                "organizations": [],
                "amounts": [],
                "event_types": []
            }}
        }}
        """
        
        batch_results = []
        batch_size = 10  # 每批處理的新聞數量
        
        for i in range(0, len(sample_df), batch_size):
            batch = sample_df.iloc[i:i+batch_size]
            self.logger.info(f"處理批次 {i//batch_size + 1}/{(len(sample_df)-1)//batch_size + 1}")
            
            for idx, row in batch.iterrows():
                try:
                    # 根據模型類型設置不同的參數
                    if self.model in ['o3', 'o4-mini']:  # reasoning 模型
                        # Reasoning 模型直接使用 user message，不需要 system prompt
                        response = client.chat.completions.create(
                            model=self.model,
                            messages=[{
                                "role": "user",
                                "content": comprehensive_prompt.format(
                                    symbol=row['Stock_symbol'],
                                    title=row['News_title'],
                                    text_snippet=row['News_text'][:1000],
                                    date=row['Date'],
                                    original_sentiment=row['Sentiment']
                                )
                            }],
                            reasoning_effort=self.reasoning_effort,  # 使用配置的 reasoning effort
                            max_completion_tokens=2000,  # 輸出 token 限制
                            service_tier="flex" if self.use_flex else "default"
                        )
                    else:  # 一般模型 (gpt-4.1, gpt-4.1-mini)
                        response = client.chat.completions.create(
                            model=self.model,
                            messages=[{
                                "role": "system",
                                "content": "You are a professional financial data analyst specializing in news quality assessment and market impact analysis."
                            }, {
                                "role": "user",
                                "content": comprehensive_prompt.format(
                                    symbol=row['Stock_symbol'],
                                    title=row['News_title'],
                                    text_snippet=row['News_text'][:1000],
                                    date=row['Date'],
                                    original_sentiment=row['Sentiment']
                                )
                            }],
                            temperature=0,
                            max_tokens=2000
                        )
                    
                    result = json.loads(response.choices[0].message.content)
                    result['index'] = idx
                    result['stock_symbol'] = row['Stock_symbol']
                    result['date'] = str(row['Date'])
                    batch_results.append(result)
                    
                    # 分解結果到各個類別
                    quality_results['relevance_checks'].append({
                        'index': idx,
                        **result.get('relevance', {})
                    })
                    
                    quality_results['sentiment_validation'].append({
                        'index': idx,
                        'original_sentiment': row['Sentiment'],
                        **result.get('sentiment', {})
                    })
                    
                    quality_results['content_quality'].append({
                        'index': idx,
                        **result.get('content_quality', {})
                    })
                    
                    quality_results['market_impact_analysis'].append({
                        'index': idx,
                        **result.get('market_impact', {})
                    })
                    
                except Exception as e:
                    self.logger.warning(f"o3 分析失敗 (index {idx}): {e}")
                    # Flex processing 可能需要更長時間，不需要額外 sleep
            
            self.logger.info(f"批次 {i//batch_size + 1} 完成，已處理 {len(batch_results)} 條新聞")
        
        # 使用 o3 進行整體模式識別
        if len(batch_results) > 20:
            self.logger.info("使用 o3 進行整體模式識別...")
            pattern_analysis = self._analyze_patterns_with_o3(batch_results, client)
            quality_results['pattern_analysis'] = pattern_analysis
        
        return quality_results
    
    def _analyze_patterns_with_o3(self, results: List[Dict], client) -> Dict:
        """使用 reasoning 模型分析整體模式"""
        pattern_prompt = """
        Based on the analysis results of {count} news articles, identify overall patterns and trends:
        
        {results_summary}
        
        Please analyze:
        1. Overall data quality patterns
        2. Common issue types
        3. Anomalies for specific stocks or time periods
        4. Specific recommendations for improving data quality
        
        Return analysis results in JSON format.
        """
        
        # 準備結果摘要
        results_summary = json.dumps(results[:50], indent=2)  # 只用前50條避免超過 token 限制
        
        try:
            if self.model in ['o3', 'o4-mini']:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{
                        "role": "user",
                        "content": pattern_prompt.format(
                            count=len(results),
                            results_summary=results_summary
                        )
                    }],
                    reasoning_effort="high",  # 模式分析使用更高的 reasoning effort
                    max_completion_tokens=3000,
                    service_tier="flex" if self.use_flex else "default"
                )
            else:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{
                        "role": "user",
                        "content": pattern_prompt.format(
                            count=len(results),
                            results_summary=results_summary
                        )
                    }],
                    temperature=0.2,
                    max_tokens=3000
                )
            
            return json.loads(response.choices[0].message.content)
        
        except Exception as e:
            self.logger.warning(f"Pattern analysis failed: {e}")
            return {}
    
    def step5_advanced_cleaning(self, df: pd.DataFrame, quality_results: Dict) -> pd.DataFrame:
        """步驟5: 基於質量檢查的進階清洗"""
        self.logger.info("步驟5: 開始進階清洗")
        
        # 5.1 標記低質量數據
        if quality_results.get('relevance_checks'):
            low_relevance_indices = [
                r['index'] for r in quality_results['relevance_checks'] 
                if r.get('relevance_score', 0) < 5
            ]
            df['low_relevance'] = df.index.isin(low_relevance_indices)
        else:
            df['low_relevance'] = False
        
        # 5.2 添加新聞標籤
        def extract_keywords(text):
            keywords = {
                'earnings': ['earnings', 'revenue', 'profit', 'quarterly', 'EPS'],
                'merger': ['merger', 'acquisition', 'acquire', 'buyout', 'deal'],
                'product': ['launch', 'release', 'announce', 'introduce', 'unveil'],
                'legal': ['lawsuit', 'sue', 'court', 'legal', 'investigation'],
                'analyst': ['upgrade', 'downgrade', 'rating', 'target', 'analyst'],
                'market': ['market', 'index', 'S&P', 'NASDAQ', 'DOW'],
                'tech': ['AI', 'cloud', 'software', 'hardware', 'chip']
            }
            
            tags = []
            text_lower = text.lower()
            for tag, words in keywords.items():
                if any(word in text_lower for word in words):
                    tags.append(tag)
            return tags
        
        df['tags'] = df['News_title'].apply(extract_keywords)
        
        # 5.3 計算新聞重要性分數
        df['importance_score'] = (
            df['title_length'].clip(upper=100) / 100 * 0.2 +
            (df['text_length'] > 100).astype(int) * 0.3 +
            df['Sentiment'].abs() * 0.3 +
            (~df['low_relevance']).astype(int) * 0.2
        )
        
        # 5.4 處理異常值
        df = df[df['title_length'] > 10]  # 移除過短的標題
        df = df[df['text_length'] > 50]   # 移除過短的內容
        
        self.logger.info(f"進階清洗完成，最終數據量: {len(df)}")
        return df
    
    def step6_generate_quality_report(self, df: pd.DataFrame, quality_results: Dict) -> Dict:
        """步驟6: 生成數據質量報告"""
        self.logger.info("步驟6: 生成數據質量報告")
        
        report = {
            'summary': {
                'total_records': len(df),
                'date_range': f"{df['Date'].min()} to {df['Date'].max()}",
                'unique_stocks': df['Stock_symbol'].nunique(),
                'stocks_list': df['Stock_symbol'].unique().tolist()
            },
            'data_coverage': {
                'by_year': df.groupby('year').size().to_dict(),
                'by_stock': df.groupby('Stock_symbol').size().to_dict(),
                'missing_stocks': list(set(json.load(open(self.TICKERS_FILE))) - set(df['Stock_symbol'].unique()))
            },
            'data_quality': {
                'null_values': df.isnull().sum().to_dict(),
                'text_length_stats': {
                    'title': df['title_length'].describe().to_dict(),
                    'text': df['text_length'].describe().to_dict()
                },
                'sentiment_distribution': df['Sentiment'].value_counts(bins=5).to_dict(),
                'low_relevance_count': df['low_relevance'].sum() if 'low_relevance' in df.columns else 0
            },
            'llm_validation': quality_results,
            'recommendations': []
        }
        
        # 生成建議
        if report['data_coverage']['missing_stocks']:
            report['recommendations'].append(
                f"有 {len(report['data_coverage']['missing_stocks'])} 隻股票缺少新聞數據"
            )
        
        if report['data_quality']['low_relevance_count'] > len(df) * 0.1:
            report['recommendations'].append(
                "超過10%的新聞被標記為低相關性，建議進一步過濾"
            )
        
        # 保存報告
        with open(self.QUALITY_REPORT, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"質量報告已保存到 {self.QUALITY_REPORT}")
        return report
    
    def step7_create_final_dataset(self, df: pd.DataFrame) -> None:
        """步驟7: 創建最終數據集"""
        self.logger.info("步驟7: 創建最終數據集")
        
        # 保存清洗後的完整數據
        df.to_parquet(self.CLEANED_PARQUET, index=False)
        self.logger.info(f"清洗後數據已保存到 {self.CLEANED_PARQUET}")
        
        # 創建 DuckDB 數據庫以便快速查詢
        con = duckdb.connect('finrl_news.db')
        con.execute(f"CREATE TABLE IF NOT EXISTS news AS SELECT * FROM df")
        con.execute("CREATE INDEX IF NOT EXISTS idx_symbol_date ON news(Stock_symbol, Date)")
        con.close()
        self.logger.info("DuckDB 數據庫已創建")
        
        # 創建每日聚合版本
        daily_df = df.groupby(['Stock_symbol', 'Date']).agg({
            'News_title': lambda x: ' | '.join(x),
            'News_text': lambda x: ' '.join(x[:3]),  # 只保留前3條新聞的文本
            'Sentiment': 'mean',
            'importance_score': 'max',
            'tags': lambda x: list(set([tag for tags in x for tag in tags]))
        }).reset_index()
        
        daily_df.to_parquet('news_89_2013_2023_daily.parquet', index=False)
        self.logger.info("每日聚合數據已創建")
    
    def run_pipeline(self, skip_download: bool = False, skip_llm: bool = False):
        """運行完整管道"""
        self.logger.info("=" * 50)
        self.logger.info("開始運行 FinRL 新聞數據處理管道")
        self.logger.info("=" * 50)
        
        try:
            # 步驟1: 獲取股票列表
            if pathlib.Path(self.TICKERS_FILE).exists():
                tickers = json.load(open(self.TICKERS_FILE))
                self.logger.info(f"從緩存讀取 {len(tickers)} 個股票代碼")
            else:
                tickers = self.step1_fetch_tickers()
            
            # 步驟2: 下載數據
            if not skip_download and not pathlib.Path(self.RAW_PARQUET).exists():
                self.step2_download_news(tickers)
            else:
                self.logger.info("跳過下載步驟，使用現有數據")
            
            # 步驟3: 基礎清洗
            df = self.step3_basic_cleaning()
            
            # 步驟4: LLM 質量檢查
            quality_results = {}
            if not skip_llm:
                quality_results = self.step4_quality_check_with_llm(df, sample_size=self.sample_size)
            
            # 步驟5: 進階清洗
            df = self.step5_advanced_cleaning(df, quality_results)
            
            # 步驟6: 生成報告
            report = self.step6_generate_quality_report(df, quality_results)
            
            # 步驟7: 創建最終數據集
            self.step7_create_final_dataset(df)
            
            self.logger.info("=" * 50)
            self.logger.info("管道執行完成！")
            self.logger.info(f"最終數據集: {len(df)} 條新聞")
            self.logger.info(f"查看質量報告: {self.QUALITY_REPORT}")
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"管道執行失敗: {e}")
            raise


def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FinRL 新聞數據處理管道')
    parser.add_argument('--openai-key', type=str, help='OpenAI API Key')
    parser.add_argument('--skip-download', action='store_true', help='跳過下載步驟')
    parser.add_argument('--skip-llm', action='store_true', help='跳過 LLM 檢查')
    parser.add_argument('--model', type=str, default='o3', 
                       choices=['o3', 'o4-mini', 'gpt-4.1', 'gpt-4.1-mini'], 
                       help='選擇 OpenAI 模型 (預設: o3)')
    parser.add_argument('--use-flex', action='store_true', default=True,
                       help='使用 Flex Processing (預設: True，僅對 reasoning 模型有效)')
    parser.add_argument('--sample-size', type=int, default=100,
                       help='LLM 質量檢查的樣本大小 (預設: 100)')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='每批處理的新聞數量 (預設: 10)')
    parser.add_argument('--reasoning-effort', type=str, default='medium',
                       choices=['low', 'medium', 'high'],
                       help='Reasoning effort for o3/o1 models (預設: medium)')
    args = parser.parse_args()
    
    # 創建處理器並運行
    processor = FinRLNewsProcessor(openai_api_key=args.openai_key)
    
    # 設置模型相關參數
    if args.model in ['o3', 'o4-mini'] and not args.use_flex:
        print("警告：reasoning 模型 (o3, o4-mini) 建議使用 Flex Processing 以獲得最佳性價比")
    elif args.model in ['gpt-4.1', 'gpt-4.1-mini'] and args.use_flex:
        print("注意：一般模型 (gpt-4.1, gpt-4.1-mini) 不支援 Flex Processing")
        args.use_flex = False
    
    # 傳遞額外參數
    processor.model = args.model
    processor.use_flex = args.use_flex
    processor.batch_size = args.batch_size
    processor.reasoning_effort = args.reasoning_effort
    
    # 修改 step4 的調用
    if not args.skip_llm:
        processor.sample_size = args.sample_size
    
    processor.run_pipeline(
        skip_download=args.skip_download,
        skip_llm=args.skip_llm
    )


if __name__ == "__main__":
    main()
