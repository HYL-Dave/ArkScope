#!/usr/bin/env python3
"""
FinRL-DeepSeek 新聞爬取延伸專案主要執行腳本
完整流程：股票清單 -> 新聞爬取 -> 數據處理 -> 格式轉換 -> 資料合併
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# 添加項目根目錄到Python路徑
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.data_extraction.stock_list_parser import StockListParser
from src.data_extraction.finnlp_crawler import FinNLPCrawler
from src.data_extraction.newsplease_crawler import NewsPleaseCrawler
from src.data_processing.llm_scorer import LLMScorer
from src.data_processing.schema_formatter import SchemaFormatter
from src.integration.data_merger import DataMerger
from src.utils.logger import setup_logger
from src.utils.cost_calculator import CostCalculator

class FinRLDeepSeekPipeline:
    def __init__(self, config_path: str):
        """
        初始化完整處理流程
        
        Args:
            config_path: 配置文件路徑
        """
        self.config = self._load_config(config_path)
        self.logger = setup_logger('finrl_pipeline', self.config['logging'])
        
        # 初始化各個組件
        self.stock_parser = StockListParser(self.config['stock_parser'])
        self.finnlp_crawler = FinNLPCrawler(self.config['finnlp_crawler'])
        self.newsplease_crawler = NewsPleaseCrawler(self.config['newsplease_crawler'])
        self.llm_scorer = LLMScorer(self.config['llm_scorer'])
        self.schema_formatter = SchemaFormatter(self.config['schema_formatter'])
        self.data_merger = DataMerger(self.config['data_merger'])
        self.cost_calculator = CostCalculator()
        
        # 建立輸出目錄
        self._setup_directories()
        
        # 執行統計
        self.stats = {
            'start_time': datetime.now(),
            'tickers_count': 0,
            'crawled_articles': 0,
            'processed_articles': 0,
            'final_records': 0,
            'total_cost': 0.0
        }
    
    def _load_config(self, config_path: str) -> dict:
        """載入配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"載入配置文件失敗: {e}")
            sys.exit(1)
    
    def _setup_directories(self):
        """建立必要的目錄結構"""
        dirs = [
            'data/raw', 'data/processed', 'data/final',
            'logs', 'reports', 'temp'
        ]
        
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def step1_extract_stock_list(self) -> list:
        """
        步驟1：提取89檔股票清單
        
        Returns:
            list: 股票代號清單
        """
        self.logger.info("=" * 50)
        self.logger.info("步驟 1: 提取股票清單")
        self.logger.info("=" * 50)
        
        try:
            # 從FinRL-DeepSeek數據集提取股票清單
            deepseek_path = self.config['data_sources']['finrl_deepseek_path']
            tickers = self.stock_parser.extract_89_tickers(deepseek_path)
            
            # 驗證和清理
            valid_tickers = self.stock_parser.validate_tickers(tickers)
            
            # 儲存股票清單
            output_path = "data/processed/nasdaq_89_tickers.csv"
            self.stock_parser.save_ticker_list(valid_tickers, output_path)
            
            self.stats['tickers_count'] = len(valid_tickers)
            self.logger.info(f"✅ 成功提取 {len(valid_tickers)} 檔股票")
            
            return valid_tickers
            
        except Exception as e:
            self.logger.error(f"❌ 股票清單提取失敗: {e}")
            raise
    
    def step2_crawl_news(self, tickers: list, start_date: str, end_date: str) -> pd.DataFrame:
        """
        步驟2：爬取新聞數據
        
        Args:
            tickers: 股票代號清單
            start_date: 開始日期
            end_date: 結束日期
            
        Returns:
            pd.DataFrame: 爬取的新聞數據
        """
        self.logger.info("=" * 50)
        self.logger.info("步驟 2: 爬取新聞數據")
        self.logger.info("=" * 50)
        
        crawl_strategy = self.config['crawl_strategy']['primary_method']
        all_news = pd.DataFrame()
        
        try:
            if crawl_strategy == 'finnlp':
                self.logger.info("使用 FinNLP 進行即時爬取")
                
                # FinNLP爬取
                sources = self.config['finnlp_crawler']['active_sources']
                news_df = self.finnlp_crawler.crawl_multiple_tickers(
                    tickers=tickers,
                    sources=sources,
                    start_date=start_date,
                    max_workers=self.config['finnlp_crawler']['max_workers']
                )
                
                if not news_df.empty:
                    output_path = f"data/raw/finnlp_news_{start_date}_{end_date}.csv"
                    self.finnlp_crawler.save_crawled_data(news_df, output_path)
                    all_news = pd.concat([all_news, news_df], ignore_index=True)
            
            # 如果啟用CommonCrawl補充
            if self.config['crawl_strategy']['use_commoncrawl_supplement']:
                self.logger.info("使用 CommonCrawl 進行歷史補充")
                
                cc_news = self.newsplease_crawler.batch_historical_crawl(
                    tickers=tickers,
                    start_month=start_date[:7],  # YYYY-MM
                    end_month=end_date[:7]
                )
                
                if not cc_news.empty:
                    output_path = f"data/raw/commoncrawl_news_{start_date}_{end_date}.csv"
                    cc_news.to_csv(output_path, index=False)
                    all_news = pd.concat([all_news, cc_news], ignore_index=True)
            
            # 去重處理
            if not all_news.empty:
                before_dedup = len(all_news)
                all_news = self._deduplicate_news(all_news)
                after_dedup = len(all_news)
                
                self.logger.info(f"去重處理: {before_dedup} -> {after_dedup} 筆")
                
                # 儲存合併後的原始數據
                raw_output_path = f"data/raw/combined_raw_news_{start_date}_{end_date}.csv"
                all_news.to_csv(raw_output_path, index=False)
                
                self.stats['crawled_articles'] = len(all_news)
                self.logger.info(f"✅ 成功爬取 {len(all_news)} 篇新聞")
            else:
                self.logger.warning("⚠️ 未爬取到任何新聞數據")
            
            return all_news
            
        except Exception as e:
            self.logger.error(f"❌ 新聞爬取失敗: {e}")
            raise
    
    def _deduplicate_news(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        新聞去重處理
        
        Args:
            df: 包含新聞的DataFrame
            
        Returns:
            pd.DataFrame: 去重後的DataFrame
        """
        if df.empty:
            return df
        
        # 基於URL去重
        df = df.drop_duplicates(subset=['Url'], keep='first')
        
        # 基於標題和股票組合去重
        if 'Article_title' in df.columns and 'Stock_symbol' in df.columns:
            df = df.drop_duplicates(subset=['Article_title', 'Stock_symbol'], keep='first')
        
        return df.reset_index(drop=True)
    
    def step3_process_data(self, raw_news_df: pd.DataFrame) -> pd.DataFrame:
        """
        步驟3：數據處理和LLM評分
        
        Args:
            raw_news_df: 原始新聞數據
            
        Returns:
            pd.DataFrame: 處理後的數據
        """
        self.logger.info("=" * 50)
        self.logger.info("步驟 3: 數據處理和LLM評分")
        self.logger.info("=" * 50)
        
        try:
            if raw_news_df.empty:
                self.logger.warning("⚠️ 無數據需要處理")
                return pd.DataFrame()
            
            # 首先進行格式標準化
            self.logger.info("正在進行格式標準化...")
            formatted_df = self.schema_formatter.convert_to_standard_format(raw_news_df)
            
            # 過濾有效文章（需要有標題和內容）
            valid_articles = formatted_df[
                (formatted_df['Article_title'].str.len() > 10) &
                (formatted_df['Article'].str.len() > 50)
            ].copy()
            
            self.logger.info(f"有效文章篩選: {len(formatted_df)} -> {len(valid_articles)} 篇")
            
            if valid_articles.empty:
                self.logger.warning("⚠️ 無有效文章進行LLM評分")
                return formatted_df
            
            # LLM評分
            self.logger.info("開始LLM情緒與風險評分...")
            scored_df = self.llm_scorer.batch_score_articles(
                valid_articles,
                max_workers=self.config['llm_scorer']['max_workers']
            )
            
            # 合併評分結果
            if len(scored_df) < len(formatted_df):
                # 將評分結果合併回完整數據集
                formatted_df.loc[valid_articles.index, 'sentiment_u'] = scored_df['sentiment_u'].values
                formatted_df.loc[valid_articles.index, 'risk_q'] = scored_df['risk_q'].values
                final_df = formatted_df
            else:
                final_df = scored_df
            
            # 為未評分的記錄設置默認值
            final_df['sentiment_u'] = final_df['sentiment_u'].fillna(3)
            final_df['risk_q'] = final_df['risk_q'].fillna(3)
            
            # 儲存處理後的數據
            processed_output_path = f"data/processed/processed_news_{datetime.now().strftime('%Y%m%d')}.csv"
            final_df.to_csv(processed_output_path, index=False)
            
            # 儲存成本報告
            cost_report_path = f"reports/llm_cost_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            self.llm_scorer.save_cost_report(cost_report_path)
            
            self.stats['processed_articles'] = len(final_df)
            self.stats['total_cost'] = self.llm_scorer.get_cost_summary()['estimated_cost_usd']
            
            self.logger.info(f"✅ 數據處理完成，共 {len(final_df)} 筆記錄")
            self.logger.info(f"💰 LLM處理成本: ${self.stats['total_cost']:.4f}")
            
            return final_df
            
        except Exception as e:
            self.logger.error(f"❌ 數據處理失敗: {e}")
            raise
    
    def step4_merge_with_original(self, new_data_df: pd.DataFrame) -> pd.DataFrame:
        """
        步驟4：與原始FinRL-DeepSeek數據合併
        
        Args:
            new_data_df: 新處理的數據
            
        Returns:
            pd.DataFrame: 合併後的完整數據集
        """
        self.logger.info("=" * 50)
        self.logger.info("步驟 4: 與原始數據合併")
        self.logger.info("=" * 50)
        
        try:
            if new_data_df.empty:
                self.logger.warning("⚠️ 無新數據需要合併")
                return pd.DataFrame()
            
            # 載入原始FinRL-DeepSeek數據
            original_data_path = self.config['data_sources']['finrl_deepseek_path']
            original_df = pd.read_csv(original_data_path)
            
            self.logger.info(f"原始數據: {len(original_df)} 筆記錄")
            self.logger.info(f"新增數據: {len(new_data_df)} 筆記錄")
            
            # 使用數據合併器進行合併
            merged_df = self.data_merger.merge_datasets(original_df, new_data_df)
            
            # 最終驗證
            validation_result = self.schema_formatter.validate_format(merged_df)
            
            if validation_result['is_valid']:
                self.logger.info("✅ 數據格式驗證通過")
            else:
                self.logger.warning(f"⚠️ 數據格式問題: {validation_result['data_quality_issues']}")
            
            # 儲存最終結果
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            
            # CSV格式
            final_csv_path = f"data/final/finrl_deepseek_extended_{timestamp}.csv"
            merged_df.to_csv(final_csv_path, index=False)
            
            # Parquet格式（更高效）
            final_parquet_path = f"data/final/finrl_deepseek_extended_{timestamp}.parquet"
            merged_df.to_parquet(final_parquet_path, index=False)
            
            # 儲存統計報告
            stats_report = {
                'merge_timestamp': datetime.now().isoformat(),
                'original_records': len(original_df),
                'new_records': len(new_data_df),
                'final_records': len(merged_df),
                'date_range': {
                    'start': merged_df['Date'].min(),
                    'end': merged_df['Date'].max()
                },
                'unique_stocks': merged_df['Stock_symbol'].nunique(),
                'validation_result': validation_result
            }
            
            stats_path = f"reports/merge_statistics_{timestamp}.json"
            with open(stats_path, 'w', encoding='utf-8') as f:
                json.dump(stats_report, f, indent=2, ensure_ascii=False, default=str)
            
            self.stats['final_records'] = len(merged_df)
            self.logger.info(f"✅ 數據合併完成，最終 {len(merged_df)} 筆記錄")
            self.logger.info(f"📁 結果已儲存至: {final_csv_path}")
            
            return merged_df
            
        except Exception as e:
            self.logger.error(f"❌ 數據合併失敗: {e}")
            raise
    
    def generate_final_report(self) -> None:
        """生成最終執行報告"""
        self.logger.info("=" * 50)
        self.logger.info("生成最終執行報告")
        self.logger.info("=" * 50)
        
        end_time = datetime.now()
        execution_time = end_time - self.stats['start_time']
        
        report = {
            'execution_summary': {
                'start_time': self.stats['start_time'].isoformat(),
                'end_time': end_time.isoformat(),
                'total_execution_time': str(execution_time),
                'status': 'completed'
            },
            'data_statistics': {
                'target_stocks': self.stats['tickers_count'],
                'crawled_articles': self.stats['crawled_articles'],
                'processed_articles': self.stats['processed_articles'],
                'final_records': self.stats['final_records']
            },
            'cost_analysis': {
                'llm_processing_cost_usd': self.stats['total_cost'],
                'cost_per_article': self.stats['total_cost'] / max(self.stats['processed_articles'], 1)
            },
            'pipeline_config': self.config
        }
        
        # 儲存報告
        report_path = f"reports/final_execution_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        # 打印總結
        self.logger.info("🎉 執行完成總結:")
        self.logger.info(f"   📊 處理股票: {self.stats['tickers_count']} 檔")
        self.logger.info(f"   📰 爬取新聞: {self.stats['crawled_articles']} 篇")
        self.logger.info(f"   🤖 LLM處理: {self.stats['processed_articles']} 篇")
        self.logger.info(f"   📁 最終記錄: {self.stats['final_records']} 筆")
        self.logger.info(f"   💰 總成本: ${self.stats['total_cost']:.4f}")
        self.logger.info(f"   ⏱️ 執行時間: {execution_time}")
        self.logger.info(f"   📋 詳細報告: {report_path}")
    
    def run_full_pipeline(self, start_date: str, end_date: str) -> None:
        """
        執行完整流程
        
        Args:
            start_date: 開始日期 (YYYY-MM-DD)
            end_date: 結束日期 (YYYY-MM-DD)
        """
        try:
            self.logger.info("🚀 開始執行 FinRL-DeepSeek 新聞爬取延伸流程")
            self.logger.info(f"📅 目標日期範圍: {start_date} 到 {end_date}")
            
            # 步驟1: 提取股票清單
            tickers = self.step1_extract_stock_list()
            
            # 步驟2: 爬取新聞
            raw_news = self.step2_crawl_news(tickers, start_date, end_date)
            
            # 步驟3: 數據處理
            processed_news = self.step3_process_data(raw_news)
            
            # 步驟4: 數據合併
            final_dataset = self.step4_merge_with_original(processed_news)
            
            # 生成最終報告
            self.generate_final_report()
            
        except Exception as e:
            self.logger.error(f"💥 流程執行失敗: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='FinRL-DeepSeek 新聞爬取延伸專案')
    parser.add_argument('--config', required=True, help='配置文件路徑')
    parser.add_argument('--start-date', required=True, help='開始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', default=datetime.now().strftime('%Y-%m-%d'), 
                       help='結束日期 (YYYY-MM-DD), 默認為今天')
    parser.add_argument('--dry-run', action='store_true', help='試運行模式（不執行實際爬取）')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🧪 試運行模式 - 不會執行實際爬取")
        # TODO: 實現試運行邏輯
        return
    
    # 初始化並執行流程
    pipeline = FinRLDeepSeekPipeline(args.config)
    pipeline.run_full_pipeline(args.start_date, args.end_date)

if __name__ == "__main__":
    main()
