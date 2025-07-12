"""
News-Please CommonCrawl 歷史新聞回補器
用於從CommonCrawl回補2024年初至今的歷史新聞
"""

import subprocess
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Generator
import re
import logging
from pathlib import Path
import gzip
import tempfile
import os

class NewsPleaseCrawler:
    def __init__(self, config: dict):
        """
        初始化News-Please爬取器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.temp_dir = config.get('temp_dir', tempfile.gettempdir())
        
        # CommonCrawl月度索引
        self.cc_archives = self._get_cc_monthly_archives()
        
        # 財經新聞網站域名清單
        self.financial_domains = {
            'cnbc.com', 'reuters.com', 'marketwatch.com', 'bloomberg.com',
            'finance.yahoo.com', 'fool.com', 'seekingalpha.com', 
            'investorplace.com', 'benzinga.com', 'thestreet.com',
            'barrons.com', 'wsj.com', 'ft.com', 'financialnews.com'
        }
        
        # 股票相關關鍵字模式
        self.stock_patterns = {}
        
    def _get_cc_monthly_archives(self) -> List[str]:
        """
        獲取CommonCrawl的月度歸檔索引
        
        Returns:
            List[str]: 可用的歸檔索引清單
        """
        # 2024-2025年的CommonCrawl歸檔
        archives = [
            'CC-MAIN-2024-10',  # 2024年2-3月
            'CC-MAIN-2024-18',  # 2024年4月
            'CC-MAIN-2024-22',  # 2024年5月
            'CC-MAIN-2024-26',  # 2024年6月
            'CC-MAIN-2024-30',  # 2024年7月
            'CC-MAIN-2024-33',  # 2024年8月
            'CC-MAIN-2024-38',  # 2024年9月
            'CC-MAIN-2024-42',  # 2024年10月
            'CC-MAIN-2024-46',  # 2024年11月
            'CC-MAIN-2024-51',  # 2024年12月
            'CC-MAIN-2025-07',  # 2025年1月
        ]
        return archives
    
    def compile_stock_patterns(self, tickers: List[str]) -> None:
        """
        編譯股票代號的正規表達式模式
        
        Args:
            tickers: 股票代號清單
        """
        self.stock_patterns = {}
        
        for ticker in tickers:
            # 創建多種匹配模式
            patterns = [
                rf'\b{ticker}\b',                    # 完整匹配
                rf'\${ticker}\b',                    # $AAPL格式
                rf'\b{ticker}(?:\s+stock|\s+shares?)\b',  # AAPL stock
                rf'\({ticker}\)',                    # (AAPL)格式
                rf'NYSE:\s*{ticker}\b',              # 交易所標記
                rf'NASDAQ:\s*{ticker}\b',
            ]
            
            # 合併為單一正規表達式
            combined_pattern = '|'.join(patterns)
            self.stock_patterns[ticker] = re.compile(combined_pattern, re.IGNORECASE)
    
    def extract_cc_by_month(self, archive_name: str, tickers: List[str],
                           output_dir: str) -> str:
        """
        從指定月份的CommonCrawl歸檔中提取新聞
        
        Args:
            archive_name: CommonCrawl歸檔名稱
            tickers: 目標股票代號清單  
            output_dir: 輸出目錄
            
        Returns:
            str: 輸出文件路徑
        """
        self.logger.info(f"開始處理CommonCrawl歸檔: {archive_name}")
        
        output_file = os.path.join(output_dir, f"news_{archive_name}.jsonl")
        
        try:
            # 構建news-please命令
            cmd = [
                'python', '-m', 'newsplease.examples.commoncrawl',
                '--archive', archive_name,
                '--warc-files-start-index', '0',
                '--warc-files-end-index', '10',  # 限制文件數量以控制處理時間
                '--output-file', output_file,
                '--filter-language', 'en',
                '--filter-minimal-length', '500'  # 過濾太短的文章
            ]
            
            # 執行爬取
            self.logger.info(f"執行命令: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1小時超時
            )
            
            if result.returncode == 0:
                self.logger.info(f"CommonCrawl提取完成: {archive_name}")
                
                # 處理和篩選結果
                filtered_file = self._filter_financial_news(output_file, tickers)
                return filtered_file
            else:
                self.logger.error(f"CommonCrawl提取失敗: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"CommonCrawl提取超時: {archive_name}")
            return None
        except Exception as e:
            self.logger.error(f"CommonCrawl提取異常: {e}")
            return None
    
    def _filter_financial_news(self, input_file: str, tickers: List[str]) -> str:
        """
        從CommonCrawl結果中篩選財經新聞
        
        Args:
            input_file: 輸入JSONL文件
            tickers: 目標股票代號清單
            
        Returns:
            str: 篩選後的文件路徑
        """
        filtered_file = input_file.replace('.jsonl', '_filtered.jsonl')
        filtered_count = 0
        
        # 編譯股票模式
        if not self.stock_patterns:
            self.compile_stock_patterns(tickers)
        
        try:
            with open(input_file, 'r', encoding='utf-8') as infile, \
                 open(filtered_file, 'w', encoding='utf-8') as outfile:
                
                for line_num, line in enumerate(infile):
                    try:
                        article = json.loads(line.strip())
                        
                        # 檢查是否為財經網站
                        url = article.get('url', '')
                        domain = self._extract_domain(url)
                        
                        if domain not in self.financial_domains:
                            continue
                        
                        # 檢查文章內容是否包含目標股票
                        title = article.get('title', '')
                        text = article.get('text', '')
                        
                        matched_tickers = self._find_matching_tickers(
                            title + ' ' + text, tickers
                        )
                        
                        if matched_tickers:
                            # 標記匹配的股票
                            article['matched_tickers'] = matched_tickers
                            article['filter_source'] = 'commoncrawl'
                            
                            outfile.write(json.dumps(article, ensure_ascii=False) + '\n')
                            filtered_count += 1
                            
                            if filtered_count % 100 == 0:
                                self.logger.info(f"已篩選 {filtered_count} 篇相關新聞")
                    
                    except json.JSONDecodeError:
                        self.logger.warning(f"跳過無效JSON行: {line_num}")
                        continue
                    except Exception as e:
                        self.logger.warning(f"處理行 {line_num} 時出錯: {e}")
                        continue
            
            self.logger.info(f"篩選完成，共 {filtered_count} 篇財經新聞: {filtered_file}")
            return filtered_file
            
        except Exception as e:
            self.logger.error(f"篩選財經新聞失敗: {e}")
            return input_file
    
    def _extract_domain(self, url: str) -> str:
        """從URL提取域名"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # 移除www前綴
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return ''
    
    def _find_matching_tickers(self, text: str, tickers: List[str]) -> List[str]:
        """
        在文本中查找匹配的股票代號
        
        Args:
            text: 要搜索的文本
            tickers: 股票代號清單
            
        Returns:
            List[str]: 匹配到的股票代號
        """
        matched = []
        
        for ticker in tickers:
            if ticker in self.stock_patterns:
                if self.stock_patterns[ticker].search(text):
                    matched.append(ticker)
        
        return matched
    
    def convert_to_standard_format(self, jsonl_files: List[str]) -> pd.DataFrame:
        """
        將CommonCrawl的JSONL格式轉換為標準格式
        
        Args:
            jsonl_files: JSONL文件路徑清單
            
        Returns:
            pd.DataFrame: 標準格式的新聞數據
        """
        all_articles = []
        
        for file_path in jsonl_files:
            if not os.path.exists(file_path):
                self.logger.warning(f"文件不存在: {file_path}")
                continue
            
            self.logger.info(f"處理文件: {file_path}")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            article = json.loads(line.strip())
                            
                            # 為每個匹配的股票創建記錄
                            matched_tickers = article.get('matched_tickers', [])
                            
                            for ticker in matched_tickers:
                                record = {
                                    'Date': self._parse_date(article.get('date_publish')),
                                    'Article_title': article.get('title', ''),
                                    'Stock_symbol': ticker,
                                    'Url': article.get('url', ''),
                                    'Publisher': self._extract_domain(article.get('url', '')),
                                    'Author': ', '.join(article.get('authors', [])) if article.get('authors') else '',
                                    'Article': article.get('text', ''),
                                    'Source': 'CommonCrawl',
                                    'Crawl_timestamp': datetime.now().isoformat()
                                }
                                
                                all_articles.append(record)
                        
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            self.logger.warning(f"處理記錄時出錯: {e}")
                            continue
            
            except Exception as e:
                self.logger.error(f"處理文件 {file_path} 失敗: {e}")
                continue
        
        df = pd.DataFrame(all_articles)
        self.logger.info(f"轉換完成，總計 {len(df)} 筆記錄")
        
        return df
    
    def _parse_date(self, date_str: Optional[str]) -> str:
        """
        解析日期字符串
        
        Args:
            date_str: 日期字符串
            
        Returns:
            str: 格式化的日期字符串 (YYYY-MM-DD)
        """
        if not date_str:
            return ''
        
        try:
            # 嘗試多種日期格式
            date_formats = [
                '%Y-%m-%d',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S',
                '%d/%m/%Y',
                '%m/%d/%Y'
            ]
            
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(date_str[:len(fmt)], fmt)
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            # 如果所有格式都失敗，返回空字符串
            self.logger.warning(f"無法解析日期: {date_str}")
            return ''
            
        except Exception as e:
            self.logger.warning(f"日期解析錯誤: {e}")
            return ''
    
    def batch_historical_crawl(self, tickers: List[str], 
                              start_month: str = '2024-01',
                              end_month: str = '2025-01') -> pd.DataFrame:
        """
        批量歷史爬取
        
        Args:
            tickers: 股票代號清單
            start_month: 開始月份 (YYYY-MM)
            end_month: 結束月份 (YYYY-MM)
            
        Returns:
            pd.DataFrame: 歷史新聞數據
        """
        self.logger.info(f"開始批量歷史爬取: {start_month} 到 {end_month}")
        
        # 創建輸出目錄
        output_dir = os.path.join(self.temp_dir, 'commoncrawl_output')
        os.makedirs(output_dir, exist_ok=True)
        
        processed_files = []
        
        # 處理每個月的歸檔
        for archive in self.cc_archives:
            # 簡單的月份匹配邏輯（可以更精確）
            if start_month <= archive <= end_month:
                try:
                    output_file = self.extract_cc_by_month(archive, tickers, output_dir)
                    if output_file and os.path.exists(output_file):
                        processed_files.append(output_file)
                        
                except Exception as e:
                    self.logger.error(f"處理歸檔 {archive} 失敗: {e}")
                    continue
        
        # 轉換為標準格式
        if processed_files:
            combined_df = self.convert_to_standard_format(processed_files)
            return combined_df
        else:
            self.logger.warning("未處理任何歸檔文件")
            return pd.DataFrame()

if __name__ == "__main__":
    # 使用範例
    config = {
        'temp_dir': './temp_cc_data'
    }
    
    crawler = NewsPleaseCrawler(config)
    
    # 測試股票清單
    test_tickers = ['AAPL', 'MSFT', 'GOOGL']
    
    # 執行歷史爬取
    historical_df = crawler.batch_historical_crawl(
        tickers=test_tickers,
        start_month='2024-01',
        end_month='2024-12'
    )
    
    print(f"歷史爬取結果: {len(historical_df)} 筆新聞")
