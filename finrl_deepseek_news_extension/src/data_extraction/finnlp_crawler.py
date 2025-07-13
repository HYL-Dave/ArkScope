"""
FinNLP 風格的多源新聞爬取器（獨立實現）
支援即時爬取2024-2025年財經新聞
無需依賴 finnlp 套件
"""

import pandas as pd
import time
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, quote

class BaseNewsStreaming:
    """基礎新聞爬取類"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dataframe = pd.DataFrame()

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """獲取網頁 BeautifulSoup 對象"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            self.logger.error(f"獲取頁面失敗 {url}: {e}")
            return None

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text

class CNBC_Streaming(BaseNewsStreaming):
    """CNBC 新聞爬取器"""

    def download_streaming_search(self, keyword: str, rounds: int = 10, start_date: str = None):
        """搜索並下載 CNBC 新聞"""
        self.logger.info(f"開始爬取 CNBC 新聞: {keyword}")

        all_news = []
        base_url = "https://www.cnbc.com/search/"

        for page in range(1, rounds + 1):
            try:
                # 構建搜索 URL
                search_url = f"{base_url}?query={quote(keyword)}&page={page}"

                soup = self._get_soup(search_url)
                if not soup:
                    continue

                # 查找新聞項目（需要根據實際網頁結構調整）
                news_items = soup.find_all('div', class_='SearchResult-searchResult')

                for item in news_items:
                    try:
                        # 提取標題
                        title_elem = item.find('a', class_='SearchResult-title')
                        if not title_elem:
                            continue

                        title = self._clean_text(title_elem.get_text())
                        url = title_elem.get('href', '')

                        # 提取時間
                        time_elem = item.find('time')
                        time_str = time_elem.get('datetime', '') if time_elem else ''

                        # 提取摘要
                        summary_elem = item.find('div', class_='SearchResult-summary')
                        summary = self._clean_text(summary_elem.get_text()) if summary_elem else ''

                        news_data = {
                            'title': title,
                            'url': url,
                            'time': time_str,
                            'summary': summary,
                            'source': 'CNBC'
                        }

                        all_news.append(news_data)

                    except Exception as e:
                        self.logger.warning(f"解析新聞項目失敗: {e}")
                        continue

                # 延遲避免過於頻繁
                time.sleep(random.uniform(2, 4))

            except Exception as e:
                self.logger.error(f"爬取第 {page} 頁失敗: {e}")
                continue

        self.dataframe = pd.DataFrame(all_news)
        self.logger.info(f"CNBC 爬取完成，共 {len(all_news)} 條新聞")

class Reuters_Streaming(BaseNewsStreaming):
    """Reuters 新聞爬取器"""

    def download_streaming_search(self, keyword: str, rounds: int = 10, start_date: str = None):
        """搜索並下載 Reuters 新聞"""
        self.logger.info(f"開始爬取 Reuters 新聞: {keyword}")

        all_news = []
        base_url = "https://www.reuters.com/site-search/"

        for page in range(1, rounds + 1):
            try:
                # Reuters 使用 offset 參數
                offset = (page - 1) * 20
                search_url = f"{base_url}?blob={quote(keyword)}&offset={offset}"

                soup = self._get_soup(search_url)
                if not soup:
                    continue

                # 查找新聞項目
                news_items = soup.find_all('div', class_='search-result')

                for item in news_items:
                    try:
                        # 提取標題和 URL
                        title_elem = item.find('h3', class_='search-result__headline')
                        if not title_elem:
                            continue

                        link_elem = title_elem.find('a')
                        if not link_elem:
                            continue

                        title = self._clean_text(link_elem.get_text())
                        url = urljoin('https://www.reuters.com', link_elem.get('href', ''))

                        # 提取時間
                        time_elem = item.find('time', class_='search-result__timestamp')
                        time_str = time_elem.get_text() if time_elem else ''

                        # 提取內容預覽
                        content_elem = item.find('p', class_='search-result__excerpt')
                        content = self._clean_text(content_elem.get_text()) if content_elem else ''

                        news_data = {
                            'title': title,
                            'url': url,
                            'time': time_str,
                            'content': content,
                            'source': 'Reuters'
                        }

                        all_news.append(news_data)

                    except Exception as e:
                        self.logger.warning(f"解析新聞項目失敗: {e}")
                        continue

                time.sleep(random.uniform(2, 4))

            except Exception as e:
                self.logger.error(f"爬取第 {page} 頁失敗: {e}")
                continue

        self.dataframe = pd.DataFrame(all_news)
        self.logger.info(f"Reuters 爬取完成，共 {len(all_news)} 條新聞")

class MarketWatch_Streaming(BaseNewsStreaming):
    """MarketWatch 新聞爬取器"""

    def download_streaming_search(self, keyword: str, rounds: int = 10, start_date: str = None):
        """搜索並下載 MarketWatch 新聞"""
        self.logger.info(f"開始爬取 MarketWatch 新聞: {keyword}")

        all_news = []
        base_url = "https://www.marketwatch.com/search"

        for page in range(1, rounds + 1):
            try:
                # MarketWatch 搜索參數
                params = {
                    'q': keyword,
                    'page': page,
                    'sort': 'date'
                }

                response = self.session.get(base_url, params=params, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # 查找新聞項目
                news_items = soup.find_all('div', class_='element element--article')

                for item in news_items:
                    try:
                        # 提取標題
                        title_elem = item.find('h3', class_='article__headline')
                        if not title_elem:
                            continue

                        link_elem = title_elem.find('a')
                        if not link_elem:
                            continue

                        title = self._clean_text(link_elem.get_text())
                        url = link_elem.get('href', '')

                        # 提取時間
                        time_elem = item.find('span', class_='article__timestamp')
                        time_str = time_elem.get_text() if time_elem else ''

                        # 提取摘要
                        summary_elem = item.find('p', class_='article__summary')
                        summary = self._clean_text(summary_elem.get_text()) if summary_elem else ''

                        news_data = {
                            'title': title,
                            'url': url,
                            'datetime': time_str,
                            'summary': summary,
                            'source': 'MarketWatch'
                        }

                        all_news.append(news_data)

                    except Exception as e:
                        self.logger.warning(f"解析新聞項目失敗: {e}")
                        continue

                time.sleep(random.uniform(2, 4))

            except Exception as e:
                self.logger.error(f"爬取第 {page} 頁失敗: {e}")
                continue

        self.dataframe = pd.DataFrame(all_news)
        self.logger.info(f"MarketWatch 爬取完成，共 {len(all_news)} 條新聞")

class InvestorPlace_Streaming(BaseNewsStreaming):
    """InvestorPlace 新聞爬取器（簡化版）"""

    def download_streaming_search(self, keyword: str, rounds: int = 10, start_date: str = None):
        """搜索並下載 InvestorPlace 新聞"""
        self.logger.info(f"開始爬取 InvestorPlace 新聞: {keyword}")

        # InvestorPlace 沒有很好的搜索功能，使用股票頁面
        all_news = []
        base_url = f"https://investorplace.com/stock-quotes/{keyword.lower()}-stock-quote/"

        try:
            soup = self._get_soup(base_url)
            if soup:
                # 簡單提取相關新聞
                news_section = soup.find('div', class_='related-articles')
                if news_section:
                    articles = news_section.find_all('article')

                    for article in articles[:rounds * 5]:  # 限制數量
                        try:
                            title_elem = article.find('h3') or article.find('h2')
                            if title_elem and title_elem.find('a'):
                                title = self._clean_text(title_elem.get_text())
                                url = title_elem.find('a').get('href', '')

                                news_data = {
                                    'title': title,
                                    'url': url,
                                    'time': datetime.now().strftime('%Y-%m-%d'),
                                    'summary': '',
                                    'source': 'InvestorPlace'
                                }

                                all_news.append(news_data)

                        except Exception as e:
                            self.logger.warning(f"解析文章失敗: {e}")
                            continue

        except Exception as e:
            self.logger.error(f"爬取 InvestorPlace 失敗: {e}")

        self.dataframe = pd.DataFrame(all_news)
        self.logger.info(f"InvestorPlace 爬取完成，共 {len(all_news)} 條新聞")

class GuruFocus_Streaming(BaseNewsStreaming):
    """GuruFocus 新聞爬取器（API 版本）"""

    def download_streaming_search(self, keyword: str, rounds: int = 10, start_date: str = None):
        """搜索並下載 GuruFocus 新聞"""
        self.logger.info(f"開始爬取 GuruFocus 新聞: {keyword}")

        # GuruFocus 需要特殊處理或 API
        all_news = []

        # 由於 GuruFocus 有反爬蟲機制，這裡只是示例
        self.logger.warning("GuruFocus 需要 API 密鑰或特殊處理")

        self.dataframe = pd.DataFrame(all_news)

class FinNLPCrawler:
    """整合的新聞爬取器"""

    def __init__(self, config: dict):
        """
        初始化FinNLP爬取器

        Args:
            config: 配置字典，包含代理設置、速率限制等
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # 可用的新聞源配置
        self.news_sources = {
            'cnbc': CNBC_Streaming,
            'reuters': Reuters_Streaming,
            'marketwatch': MarketWatch_Streaming,
            'investorplace': InvestorPlace_Streaming,
            'gurufocus': GuruFocus_Streaming
        }

        # 速率限制設置
        self.rate_limit_config = config.get('rate_limiting', {
            'min_delay': 2,
            'max_delay': 5,
            'requests_per_minute': 30,
            'daily_limit': 5000
        })

        self.stats = {
            'total_crawled': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'source_stats': {}
        }

    def crawl_single_ticker_source(self, ticker: str, source_name: str,
                                  start_date: str, rounds: int = 10) -> pd.DataFrame:
        """
        爬取單一股票的單一新聞源

        Args:
            ticker: 股票代號
            source_name: 新聞源名稱 ('cnbc', 'reuters'等)
            start_date: 開始日期 (YYYY-MM-DD格式)
            rounds: 爬取輪數

        Returns:
            pd.DataFrame: 爬取到的新聞數據
        """
        try:
            # 獲取對應的新聞源類別
            source_class = self.news_sources.get(source_name)
            if not source_class:
                raise ValueError(f"不支援的新聞源: {source_name}")

            # 初始化爬取器
            downloader = source_class(self.config)

            # 執行爬取
            self.logger.info(f"開始爬取 {ticker} 從 {source_name}，日期從 {start_date}")

            downloader.download_streaming_search(
                keyword=ticker,
                rounds=rounds,
                start_date=start_date
            )

            # 獲取數據
            df = downloader.dataframe

            if df is not None and not df.empty:
                # 標準化欄位名稱
                df = self._standardize_columns(df, source_name)
                df['Stock_symbol'] = ticker
                df['Source'] = source_name
                df['Crawl_timestamp'] = datetime.now().isoformat()

                self.stats['successful_requests'] += 1
                self.logger.info(f"成功爬取 {len(df)} 筆新聞: {ticker} - {source_name}")
                return df
            else:
                self.logger.warning(f"未獲取到數據: {ticker} - {source_name}")
                return pd.DataFrame()

        except Exception as e:
            self.stats['failed_requests'] += 1
            self.logger.error(f"爬取失敗 {ticker} - {source_name}: {e}")
            return pd.DataFrame()

    def _standardize_columns(self, df: pd.DataFrame, source_name: str) -> pd.DataFrame:
        """
        標準化不同新聞源的欄位名稱

        Args:
            df: 原始數據框
            source_name: 新聞源名稱

        Returns:
            pd.DataFrame: 標準化後的數據框
        """
        # 欄位映射表
        column_mappings = {
            'cnbc': {
                'title': 'Article_title',
                'time': 'Date',
                'author': 'Author',
                'summary': 'Article',
                'url': 'Url'
            },
            'reuters': {
                'title': 'Article_title',
                'time': 'Date',
                'author': 'Author',
                'content': 'Article',
                'url': 'Url'
            },
            'marketwatch': {
                'title': 'Article_title',
                'datetime': 'Date',
                'author': 'Author',
                'content': 'Article',
                'link': 'Url'
            },
            'investorplace': {
                'title': 'Article_title',
                'time': 'Date',
                'author': 'Author',
                'summary': 'Article',
                'url': 'Url'
            },
            'gurufocus': {
                'title': 'Article_title',
                'datetime': 'Date',
                'source': 'Publisher',
                'content': 'Article',
                'url': 'Url'
            }
        }

        mapping = column_mappings.get(source_name, {})

        # 重命名欄位
        df_standardized = df.rename(columns=mapping)

        # 確保必要欄位存在
        required_columns = ['Article_title', 'Date', 'Article', 'Url']
        for col in required_columns:
            if col not in df_standardized.columns:
                df_standardized[col] = ''

        # 補充Publisher欄位
        if 'Publisher' not in df_standardized.columns:
            df_standardized['Publisher'] = source_name.title()

        return df_standardized

    def crawl_multiple_tickers(self, tickers: List[str], sources: List[str],
                              start_date: str, end_date: Optional[str] = None,
                              max_workers: int = 3) -> pd.DataFrame:
        """
        並行爬取多檔股票的多個新聞源

        Args:
            tickers: 股票代號清單
            sources: 新聞源清單
            start_date: 開始日期
            end_date: 結束日期（可選）
            max_workers: 最大並行數

        Returns:
            pd.DataFrame: 合併後的新聞數據
        """
        all_news = []
        total_tasks = len(tickers) * len(sources)
        completed_tasks = 0

        self.logger.info(f"開始爬取 {len(tickers)} 檔股票，{len(sources)} 個來源，總計 {total_tasks} 個任務")

        # 使用線程池並行處理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任務
            future_to_params = {}

            for ticker in tickers:
                for source in sources:
                    future = executor.submit(
                        self.crawl_single_ticker_source,
                        ticker, source, start_date
                    )
                    future_to_params[future] = (ticker, source)

            # 收集結果
            for future in as_completed(future_to_params):
                ticker, source = future_to_params[future]
                completed_tasks += 1

                try:
                    df = future.result()
                    if not df.empty:
                        all_news.append(df)
                        self.stats['total_crawled'] += len(df)

                    # 記錄來源統計
                    if source not in self.stats['source_stats']:
                        self.stats['source_stats'][source] = 0
                    self.stats['source_stats'][source] += len(df) if not df.empty else 0

                except Exception as e:
                    self.logger.error(f"處理任務失敗 {ticker}-{source}: {e}")

                # 進度報告
                if completed_tasks % 10 == 0:
                    self.logger.info(f"進度: {completed_tasks}/{total_tasks} ({completed_tasks/total_tasks*100:.1f}%)")

                # 速率控制
                time.sleep(random.uniform(
                    self.rate_limit_config['min_delay'],
                    self.rate_limit_config['max_delay']
                ))

        # 合併所有結果
        if all_news:
            combined_df = pd.concat(all_news, ignore_index=True)
            self.logger.info(f"爬取完成，總計 {len(combined_df)} 筆新聞")
            return combined_df
        else:
            self.logger.warning("未獲取到任何新聞數據")
            return pd.DataFrame()

    def save_crawled_data(self, df: pd.DataFrame, output_path: str,
                         include_metadata: bool = True) -> None:
        """
        儲存爬取的數據

        Args:
            df: 要儲存的數據框
            output_path: 輸出路徑
            include_metadata: 是否包含爬取元數據
        """
        try:
            # 儲存主要數據
            df.to_csv(output_path, index=False, encoding='utf-8')
            self.logger.info(f"數據已儲存至: {output_path}")

            # 儲存爬取統計資訊
            if include_metadata:
                metadata_path = output_path.replace('.csv', '_metadata.json')
                metadata = {
                    'crawl_timestamp': datetime.now().isoformat(),
                    'total_records': len(df),
                    'unique_stocks': df['Stock_symbol'].nunique() if 'Stock_symbol' in df.columns else 0,
                    'date_range': {
                        'start': df['Date'].min() if 'Date' in df.columns else None,
                        'end': df['Date'].max() if 'Date' in df.columns else None
                    },
                    'statistics': self.stats
                }

                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

                self.logger.info(f"元數據已儲存至: {metadata_path}")

        except Exception as e:
            self.logger.error(f"儲存數據失敗: {e}")
            raise

    def daily_incremental_crawl(self, tickers: List[str], target_date: str) -> pd.DataFrame:
        """
        執行特定日期的增量爬取

        Args:
            tickers: 股票代號清單
            target_date: 目標日期 (YYYY-MM-DD)

        Returns:
            pd.DataFrame: 當日爬取的新聞
        """
        self.logger.info(f"開始執行 {target_date} 的增量爬取")

        # 選擇活躍的新聞源
        active_sources = ['cnbc', 'reuters', 'marketwatch']

        # 執行爬取
        daily_news = self.crawl_multiple_tickers(
            tickers=tickers,
            sources=active_sources,
            start_date=target_date,
            max_workers=2  # 降低並行數避免被限制
        )

        # 過濾確保是目標日期的新聞
        if not daily_news.empty and 'Date' in daily_news.columns:
            daily_news['Date'] = pd.to_datetime(daily_news['Date']).dt.date
            target_date_obj = datetime.strptime(target_date, '%Y-%m-%d').date()
            daily_news = daily_news[daily_news['Date'] == target_date_obj]

        self.logger.info(f"{target_date} 增量爬取完成，獲得 {len(daily_news)} 筆新聞")
        return daily_news


if __name__ == "__main__":
    # 使用範例
    config = {
        'use_proxy': None,
        'max_retry': 3,
        'rate_limiting': {
            'min_delay': 2,
            'max_delay': 4,
            'requests_per_minute': 30,
            'daily_limit': 5000
        }
    }

    crawler = FinNLPCrawler(config)

    # 測試爬取單一股票
    test_df = crawler.crawl_single_ticker_source(
        ticker='AAPL',
        source_name='cnbc',
        start_date='2024-01-01'
    )

    print(f"測試爬取結果: {len(test_df)} 筆新聞")