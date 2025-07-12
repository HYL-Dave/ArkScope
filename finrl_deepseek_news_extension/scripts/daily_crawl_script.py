#!/usr/bin/env python3
"""
每日增量新聞爬取腳本
用於定時執行，每天爬取最新的新聞數據
"""

import os
import sys
import argparse
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# 添加專案路徑
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.data_extraction.stock_list_parser import StockListParser
from src.data_extraction.finnlp_crawler import FinNLPCrawler
from src.data_processing.llm_scorer import LLMScorer
from src.data_processing.schema_formatter import SchemaFormatter
from src.utils.logger_util import setup_logger, CostTracker
from src.utils.cost_calculator import CostCalculator

class DailyCrawlManager:
    def __init__(self, config_path: str):
        """
        初始化每日爬取管理器
        
        Args:
            config_path: 配置文件路徑
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.logger = setup_logger('daily_crawl', self.config['logging'])
        
        # 初始化組件
        self.stock_parser = StockListParser(self.config['stock_parser'])
        self.crawler = FinNLPCrawler(self.config['finnlp_crawler'])
        self.llm_scorer = LLMScorer(self.config['llm_scorer'])
        self.formatter = SchemaFormatter(self.config['schema_formatter'])
        self.cost_calculator = CostCalculator()
        
        # 成本追蹤器
        self.cost_tracker = CostTracker(
            self.logger, 
            self.config['llm_scorer'].get('daily_cost_limit', 50.0)
        )
        
        # 載入股票清單
        self.tickers = self._load_stock_tickers()
    
    def _load_stock_tickers(self) -> list:
        """載入89檔股票清單"""
        try:
            # 嘗試從已儲存的檔案載入
            ticker_file = Path("config/nasdaq_89_tickers.csv")
            if ticker_file.exists():
                df = pd.read_csv(ticker_file)
                return df['ticker'].tolist()
            else:
                # 從原始數據提取
                deepseek_path = self.config['data_sources']['finrl_deepseek_path']
                tickers = self.stock_parser.extract_89_tickers(deepseek_path)
                return self.stock_parser.validate_tickers(tickers)
        except Exception as e:
            self.logger.error(f"載入股票清單失敗: {e}")
            raise
    
    def crawl_daily_news(self, target_date: str) -> pd.DataFrame:
        """
        爬取指定日期的新聞
        
        Args:
            target_date: 目標日期 (YYYY-MM-DD)
            
        Returns:
            pd.DataFrame: 爬取的新聞數據
        """
        self.logger.info(f"開始爬取 {target_date} 的新聞")
        
        # 限制每日爬取的股票數量以控制成本
        daily_limit = self.config['crawl_strategy'].get('daily_stock_limit', 20)
        if len(self.tickers) > daily_limit:
            # 輪換股票，確保長期覆蓋所有股票
            day_of_year = datetime.strptime(target_date, '%Y-%m-%d').timetuple().tm_yday
            start_idx = (day_of_year * daily_limit) % len(self.tickers)
            selected_tickers = self.tickers[start_idx:start_idx + daily_limit]
            
            # 如果接近列表末尾，補齊數量
            if len(selected_tickers) < daily_limit:
                remaining = daily_limit - len(selected_tickers)
                selected_tickers.extend(self.tickers[:remaining])
        else:
            selected_tickers = self.tickers
        
        self.logger.info(f"今日爬取股票: {len(selected_tickers)} 檔")
        
        # 執行爬取
        daily_news = self.crawler.daily_incremental_crawl(selected_tickers, target_date)
        
        # 儲存原始數據
        if not daily_news.empty:
            raw_output_path = f"data/raw/daily_news_{target_date}.csv"
            daily_news.to_csv(raw_output_path, index=False)
            self.logger.info(f"原始數據已儲存: {raw_output_path}")
        
        return daily_news
    
    def process_daily_data(self, daily_news: pd.DataFrame, target_date: str) -> pd.DataFrame:
        """
        處理每日爬取的數據
        
        Args:
            daily_news: 原始新聞數據
            target_date: 目標日期
            
        Returns:
            pd.DataFrame: 處理後的數據
        """
        if daily_news.empty:
            self.logger.warning("無數據需要處理")
            return pd.DataFrame()
        
        self.logger.info(f"開始處理 {len(daily_news)} 篇新聞")
        
        # 格式標準化
        formatted_df = self.formatter.convert_to_standard_format(daily_news)
        
        # 品質過濾
        valid_articles = formatted_df[
            (formatted_df['Article_title'].str.len() >= 10) &
            (formatted_df['Article'].str.len() >= 100)
        ].copy()
        
        if valid_articles.empty:
            self.logger.warning("沒有符合品質要求的文章")
            return formatted_df
        
        # 成本預估
        avg_length = valid_articles['Article'].str.len().mean()
        cost_estimate = self.cost_calculator.estimate_batch_llm_cost(
            len(valid_articles), int(avg_length), 
            self.config['llm_scorer']['model']
        )
        
        estimated_cost = cost_estimate['total_estimated_cost_usd']
        self.logger.info(f"預估LLM處理成本: ${estimated_cost:.4f}")
        
        # 檢查成本限制
        if estimated_cost > self.config['llm_scorer'].get('daily_cost_limit', 50.0):
            self.logger.warning(f"預估成本超過每日限制，將處理前 {len(valid_articles)//2} 篇文章")
            valid_articles = valid_articles.head(len(valid_articles)//2)
        
        # LLM評分
        scored_df = self.llm_scorer.batch_score_articles(valid_articles, max_workers=2)
        
        # 更新成本追蹤
        actual_cost = self.llm_scorer.get_cost_summary()['estimated_cost_usd']
        self.cost_tracker.add_cost(actual_cost, "OpenAI")
        
        # 儲存處理後數據
        processed_output_path = f"data/processed/daily_processed_{target_date}.csv"
        scored_df.to_csv(processed_output_path, index=False)
        
        self.logger.info(f"處理完成，實際成本: ${actual_cost:.4f}")
        return scored_df
    
    def update_master_dataset(self, new_data: pd.DataFrame, target_date: str) -> None:
        """
        更新主資料集
        
        Args:
            new_data: 新處理的數據
            target_date: 日期
        """
        if new_data.empty:
            return
        
        # 檢查是否存在主資料集
        master_file = Path("data/final/finrl_deepseek_master.csv")
        
        if master_file.exists():
            # 載入現有數據
            master_df = pd.read_csv(master_file)
            
            # 移除目標日期的舊數據（如果存在）
            master_df = master_df[master_df['Date'] != target_date]
            
            # 合併新數據
            updated_df = pd.concat([master_df, new_data], ignore_index=True)
        else:
            updated_df = new_data
        
        # 排序並儲存
        updated_df = updated_df.sort_values(['Date', 'Stock_symbol']).reset_index(drop=True)
        updated_df.to_csv(master_file, index=False)
        
        # 同時儲存為parquet格式
        parquet_file = master_file.with_suffix('.parquet')
        updated_df.to_parquet(parquet_file, index=False)
        
        self.logger.info(f"主資料集已更新: {len(updated_df)} 筆記錄")
    
    def cleanup_old_files(self, keep_days: int = 30) -> None:
        """
        清理舊的臨時文件
        
        Args:
            keep_days: 保留天數
        """
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        
        # 清理原始數據文件
        raw_dir = Path("data/raw")
        if raw_dir.exists():
            for file_path in raw_dir.glob("daily_news_*.csv"):
                if file_path.stat().st_mtime < cutoff_date.timestamp():
                    file_path.unlink()
                    self.logger.info(f"已刪除舊文件: {file_path}")
        
        # 清理處理後數據文件
        processed_dir = Path("data/processed")
        if processed_dir.exists():
            for file_path in processed_dir.glob("daily_processed_*.csv"):
                if file_path.stat().st_mtime < cutoff_date.timestamp():
                    file_path.unlink()
                    self.logger.info(f"已刪除舊文件: {file_path}")
    
    def generate_daily_report(self, target_date: str, crawled_count: int, 
                            processed_count: int, cost: float) -> None:
        """
        生成每日執行報告
        
        Args:
            target_date: 目標日期
            crawled_count: 爬取文章數
            processed_count: 處理文章數  
            cost: 實際成本
        """
        report = {
            'date': target_date,
            'execution_time': datetime.now().isoformat(),
            'statistics': {
                'target_stocks': len(self.tickers),
                'articles_crawled': crawled_count,
                'articles_processed': processed_count,
                'processing_success_rate': (processed_count / max(crawled_count, 1)) * 100
            },
            'cost_analysis': {
                'actual_cost_usd': cost,
                'cost_per_article': cost / max(processed_count, 1),
                'daily_budget_used_percent': (cost / self.config['llm_scorer'].get('daily_cost_limit', 50.0)) * 100
            },
            'data_quality': {
                'avg_article_length': 0,  # 將在實際使用中計算
                'unique_publishers': 0,
                'duplicate_rate': 0
            }
        }
        
        # 儲存報告
        report_path = f"reports/daily_report_{target_date}.json"
        os.makedirs("reports", exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"每日報告已生成: {report_path}")
    
    def run_daily_crawl(self, target_date: str = None) -> None:
        """
        執行每日爬取流程
        
        Args:
            target_date: 目標日期，預設為昨天
        """
        if target_date is None:
            target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        try:
            self.logger.info(f"🚀 開始執行每日爬取: {target_date}")
            start_time = datetime.now()
            
            # 檢查是否已處理過該日期
            existing_file = Path(f"data/processed/daily_processed_{target_date}.csv")
            if existing_file.exists():
                self.logger.info(f"日期 {target_date} 已處理過，跳過")
                return
            
            # 步驟1: 爬取新聞
            daily_news = self.crawl_daily_news(target_date)
            crawled_count = len(daily_news)
            
            # 步驟2: 處理數據
            processed_data = self.process_daily_data(daily_news, target_date)
            processed_count = len(processed_data)
            
            # 步驟3: 更新主資料集
            self.update_master_dataset(processed_data, target_date)
            
            # 步驟4: 清理舊文件
            self.cleanup_old_files()
            
            # 步驟5: 生成報告
            total_cost = self.llm_scorer.get_cost_summary()['estimated_cost_usd']
            self.generate_daily_report(target_date, crawled_count, processed_count, total_cost)
            
            # 執行總結
            execution_time = datetime.now() - start_time
            self.logger.info(f"✅ 每日爬取完成!")
            self.logger.info(f"   📊 爬取新聞: {crawled_count} 篇")
            self.logger.info(f"   🤖 處理新聞: {processed_count} 篇")
            self.logger.info(f"   💰 總成本: ${total_cost:.4f}")
            self.logger.info(f"   ⏱️ 執行時間: {execution_time}")
            
        except Exception as e:
            self.logger.error(f"每日爬取失敗: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='每日新聞爬取腳本')
    parser.add_argument('--config', default='config/config.json', help='配置文件路徑')
    parser.add_argument('--date', help='目標日期 (YYYY-MM-DD)，預設為昨天')
    parser.add_argument('--dry-run', action='store_true', help='試運行模式')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🧪 試運行模式 - 僅檢查配置和連接")
        # TODO: 實現試運行邏輯
        return
    
    # 確保必要目錄存在
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("data/final", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # 執行每日爬取
    crawler_manager = DailyCrawlManager(args.config)
    crawler_manager.run_daily_crawl(args.date)

if __name__ == "__main__":
    main()
