"""
FinRL-DeepSeek 股票清單解析器
從官方數據集中提取89檔Nasdaq股票清單
"""

import pandas as pd
from typing import List, Set
import logging
from pathlib import Path

class StockListParser:
    def __init__(self, config: dict):
        """
        初始化股票清單解析器
        
        Args:
            config: 包含數據路徑等配置的字典
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def extract_89_tickers(self, deepseek_csv_path: str) -> List[str]:
        """
        從FinRL-DeepSeek官方清洗後數據中提取89檔股票代號
        
        Args:
            deepseek_csv_path: sentiment_deepseek_new_cleaned_nasdaq_news_full.csv路徑
            
        Returns:
            List[str]: 89檔股票代號清單
        """
        try:
            # 載入官方清洗後的數據集
            df = pd.read_csv(deepseek_csv_path)
            self.logger.info(f"載入數據集成功，總計 {len(df)} 筆記錄")
            
            # 提取唯一股票代號
            unique_tickers = df['Stock_symbol'].unique()
            ticker_list = sorted(unique_tickers.tolist())
            
            self.logger.info(f"提取到 {len(ticker_list)} 檔股票")
            self.logger.info(f"股票清單預覽: {ticker_list[:10]}...")
            
            # 驗證數量是否為89檔
            if len(ticker_list) != 89:
                self.logger.warning(f"預期89檔股票，實際找到 {len(ticker_list)} 檔")
            
            return ticker_list
            
        except Exception as e:
            self.logger.error(f"提取股票清單失敗: {e}")
            raise
    
    def validate_tickers(self, tickers: List[str]) -> List[str]:
        """
        驗證股票代號格式的有效性
        
        Args:
            tickers: 股票代號清單
            
        Returns:
            List[str]: 驗證後的有效股票代號清單
        """
        valid_tickers = []
        
        for ticker in tickers:
            # 基本格式檢查
            if isinstance(ticker, str) and ticker.strip():
                clean_ticker = ticker.strip().upper()
                # 一般Nasdaq股票代號為1-5個字符
                if 1 <= len(clean_ticker) <= 5 and clean_ticker.isalpha():
                    valid_tickers.append(clean_ticker)
                else:
                    self.logger.warning(f"跳過無效股票代號: {ticker}")
            else:
                self.logger.warning(f"跳過空值股票代號: {ticker}")
        
        self.logger.info(f"驗證完成，有效股票代號: {len(valid_tickers)}/{len(tickers)}")
        return valid_tickers
    
    def save_ticker_list(self, tickers: List[str], output_path: str) -> None:
        """
        儲存股票清單到文件
        
        Args:
            tickers: 股票代號清單
            output_path: 輸出文件路徑
        """
        try:
            # 創建DataFrame並儲存
            ticker_df = pd.DataFrame({'ticker': tickers})
            ticker_df.to_csv(output_path, index=False)
            
            # 同時儲存為Python檔案供其他模組使用
            py_output_path = output_path.replace('.csv', '.py')
            with open(py_output_path, 'w') as f:
                f.write("# FinRL-DeepSeek 89檔Nasdaq股票清單\n")
                f.write("# 自動生成，請勿手動修改\n\n")
                f.write(f"NASDAQ_89_TICKERS = {tickers}\n")
                f.write(f"TICKER_COUNT = {len(tickers)}\n")
            
            self.logger.info(f"股票清單已儲存至: {output_path} 和 {py_output_path}")
            
        except Exception as e:
            self.logger.error(f"儲存股票清單失敗: {e}")
            raise
    
    def get_date_range_from_original(self, deepseek_csv_path: str) -> tuple:
        """
        從原始數據中獲取日期範圍資訊
        
        Args:
            deepseek_csv_path: 原始數據路徑
            
        Returns:
            tuple: (最早日期, 最晚日期)
        """
        try:
            df = pd.read_csv(deepseek_csv_path)
            df['Date'] = pd.to_datetime(df['Date'])
            
            min_date = df['Date'].min()
            max_date = df['Date'].max()
            
            self.logger.info(f"原始數據日期範圍: {min_date.date()} 到 {max_date.date()}")
            return min_date, max_date
            
        except Exception as e:
            self.logger.error(f"獲取日期範圍失敗: {e}")
            raise

if __name__ == "__main__":
    # 使用範例
    config = {
        'data_path': 'huggingface_datasets/FinRL_DeepSeek_sentiment/',
        'output_path': 'config/'
    }
    
    parser = StockListParser(config)
    
    # 提取89檔股票清單
    deepseek_path = "huggingface_datasets/FinRL_DeepSeek_sentiment/sentiment_deepseek_new_cleaned_nasdaq_news_full.csv"
    tickers = parser.extract_89_tickers(deepseek_path)
    
    # 驗證格式
    valid_tickers = parser.validate_tickers(tickers)
    
    # 儲存清單
    parser.save_ticker_list(valid_tickers, "config/nasdaq_89_tickers.csv")
    
    # 獲取原始日期範圍
    date_range = parser.get_date_range_from_original(deepseek_path)
