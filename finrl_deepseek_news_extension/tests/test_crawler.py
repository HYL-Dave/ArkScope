#!/usr/bin/env python3
"""
測試獨立的新聞爬蟲實現
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# 添加專案路徑
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.data_extraction.finnlp_crawler import FinNLPCrawler


def test_single_source():
    """測試單一新聞源爬取"""
    print("🧪 測試單一新聞源爬取...")

    config = {
        'rate_limiting': {
            'min_delay': 2,
            'max_delay': 4,
            'requests_per_minute': 30,
            'daily_limit': 5000
        }
    }

    crawler = FinNLPCrawler(config)

    # 測試 CNBC
    print("\n📰 測試 CNBC 爬取...")
    df_cnbc = crawler.crawl_single_ticker_source(
        ticker='AAPL',
        source_name='cnbc',
        start_date='2024-07-01',
        rounds=2  # 只爬取2頁進行測試
    )

    if not df_cnbc.empty:
        print(f"✅ CNBC 爬取成功: {len(df_cnbc)} 筆新聞")
        print(f"欄位: {df_cnbc.columns.tolist()}")
        print(f"第一筆新聞: {df_cnbc.iloc[0]['Article_title'][:50]}...")
    else:
        print("⚠️ CNBC 未爬取到數據")

    return df_cnbc


def test_multiple_sources():
    """測試多源爬取"""
    print("\n🧪 測試多源爬取...")

    config = {
        'rate_limiting': {
            'min_delay': 2,
            'max_delay': 4,
            'requests_per_minute': 30,
            'daily_limit': 5000
        }
    }

    crawler = FinNLPCrawler(config)

    # 測試多個新聞源
    tickers = ['AAPL', 'MSFT']
    sources = ['cnbc', 'reuters']

    print(f"\n📊 爬取股票: {tickers}")
    print(f"📰 新聞源: {sources}")

    df_all = crawler.crawl_multiple_tickers(
        tickers=tickers,
        sources=sources,
        start_date='2024-07-01',
        max_workers=2
    )

    if not df_all.empty:
        print(f"\n✅ 多源爬取成功: {len(df_all)} 筆新聞")
        print(f"\n統計資訊:")
        print(f"- 不同股票數: {df_all['Stock_symbol'].nunique()}")
        print(f"- 不同新聞源數: {df_all['Source'].nunique()}")
        print(f"- 各新聞源統計:")
        print(df_all['Source'].value_counts())

        # 儲存測試結果
        output_path = "test_crawl_results.csv"
        crawler.save_crawled_data(df_all, output_path)
        print(f"\n💾 結果已儲存至: {output_path}")
    else:
        print("⚠️ 多源爬取未獲得數據")

    return df_all


def test_daily_crawl():
    """測試每日增量爬取"""
    print("\n🧪 測試每日增量爬取...")

    config = {
        'rate_limiting': {
            'min_delay': 2,
            'max_delay': 4,
            'requests_per_minute': 30,
            'daily_limit': 5000
        }
    }

    crawler = FinNLPCrawler(config)

    # 測試今天的爬取
    today = datetime.now().strftime('%Y-%m-%d')
    tickers = ['AAPL']

    print(f"\n📅 爬取日期: {today}")
    print(f"📊 爬取股票: {tickers}")

    df_daily = crawler.daily_incremental_crawl(tickers, today)

    if not df_daily.empty:
        print(f"✅ 每日爬取成功: {len(df_daily)} 筆新聞")
    else:
        print("⚠️ 今日未爬取到新聞（可能是週末或假日）")

    return df_daily


def main():
    """執行所有測試"""
    # 設置日誌
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🚀 開始測試獨立新聞爬蟲...\n")

    # 測試1：單一新聞源
    df1 = test_single_source()

    # 測試2：多源爬取
    # df2 = test_multiple_sources()

    # 測試3：每日爬取
    # df3 = test_daily_crawl()

    print("\n✅ 測試完成！")
    print("\n💡 提示：")
    print("1. 如果爬取失敗，可能是網站結構有變化")
    print("2. 建議降低爬取頻率避免被封鎖")
    print("3. 某些新聞源可能需要代理或特殊處理")


if __name__ == "__main__":
    main()