#!/usr/bin/env python3
"""
分析 Polygon vs Finnhub 的 Seeking Alpha 新聞重疊程度

關鍵問題：
1. 同一時間範圍內，兩邊的 Seeking Alpha 文章數是否相同？
2. 如果不同，是否表示即使同一來源，兩邊取得的內容也不同？
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict


def load_env_file(env_path: str = None) -> dict:
    """Load environment variables from .env file."""
    search_paths = []
    if env_path:
        search_paths.append(Path(env_path))
    project_root = Path(__file__).parent
    search_paths.extend([
        project_root / "config" / ".env",
        project_root / ".env",
    ])

    env_vars = {}
    for path in search_paths:
        if path.exists():
            print(f"Loading env from: {path}")
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if not value.startswith('your_'):
                            env_vars[key] = value
                            os.environ[key] = value
            break
    return env_vars


def fetch_polygon_news(ticker: str, start_date: str, end_date: str, api_key: str) -> list:
    """Fetch news from Polygon API."""
    url = "https://api.polygon.io/v2/reference/news"
    params = {
        "ticker": ticker,
        "published_utc.gte": start_date,
        "published_utc.lte": end_date,
        "limit": 1000,
        "apiKey": api_key
    }

    all_articles = []
    while True:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"Polygon error: {resp.status_code} - {resp.text}")
            break

        data = resp.json()
        articles = data.get("results", [])
        all_articles.extend(articles)

        next_url = data.get("next_url")
        if not next_url:
            break

        url = next_url
        params = {"apiKey": api_key}
        time.sleep(0.3)  # Rate limit

    return all_articles


def fetch_finnhub_news(ticker: str, start_date: str, end_date: str, api_key: str) -> list:
    """Fetch news from Finnhub API."""
    url = "https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": ticker,
        "from": start_date,
        "to": end_date,
        "token": api_key
    }

    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        print(f"Finnhub error: {resp.status_code} - {resp.text}")
        return []

    return resp.json()


def analyze_seeking_alpha(polygon_articles: list, finnhub_articles: list) -> dict:
    """Analyze Seeking Alpha articles from both sources."""

    # Filter Seeking Alpha articles
    polygon_sa = [a for a in polygon_articles
                  if a.get("publisher", {}).get("name", "").lower() == "seeking alpha"]

    finnhub_sa = [a for a in finnhub_articles
                  if a.get("source", "").lower() == "seekingalpha"]

    # Extract titles for comparison
    polygon_titles = set()
    for a in polygon_sa:
        title = a.get("title", "").strip().lower()
        if title:
            polygon_titles.add(title[:80])  # First 80 chars for fuzzy match

    finnhub_titles = set()
    for a in finnhub_sa:
        title = a.get("headline", "").strip().lower()
        if title:
            finnhub_titles.add(title[:80])

    # Find overlaps
    common_titles = polygon_titles & finnhub_titles
    polygon_only = polygon_titles - finnhub_titles
    finnhub_only = finnhub_titles - polygon_titles

    return {
        "polygon_seeking_alpha_count": len(polygon_sa),
        "finnhub_seeking_alpha_count": len(finnhub_sa),
        "polygon_titles_sample": list(polygon_titles)[:5],
        "finnhub_titles_sample": list(finnhub_titles)[:5],
        "common_titles_count": len(common_titles),
        "polygon_only_count": len(polygon_only),
        "finnhub_only_count": len(finnhub_only),
        "common_titles_sample": list(common_titles)[:5],
    }


def analyze_by_publisher(articles: list, source_name: str) -> dict:
    """Count articles by publisher."""
    publisher_counts = defaultdict(int)

    for a in articles:
        if source_name == "Polygon":
            pub = a.get("publisher", {}).get("name", "Unknown")
        else:  # Finnhub
            pub = a.get("source", "Unknown")
        publisher_counts[pub] += 1

    return dict(sorted(publisher_counts.items(), key=lambda x: -x[1]))


def main():
    # Load API keys
    load_env_file()
    polygon_key = os.environ.get("POLYGON_API_KEY")
    finnhub_key = os.environ.get("FINNHUB_API_KEY")

    if not polygon_key or not finnhub_key:
        print("Error: Missing API keys")
        print(f"POLYGON_API_KEY: {'set' if polygon_key else 'NOT SET'}")
        print(f"FINNHUB_API_KEY: {'set' if finnhub_key else 'NOT SET'}")
        sys.exit(1)

    # Test parameters
    ticker = "AAPL"

    # Test different time ranges
    test_ranges = [
        ("recent_7d",
         (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
         datetime.now().strftime("%Y-%m-%d")),
        ("1_month_ago",
         "2024-11-01", "2024-11-30"),
        ("6_months_ago",
         "2024-06-01", "2024-06-30"),
    ]

    results = {}

    for range_name, start_date, end_date in test_ranges:
        print(f"\n{'='*60}")
        print(f"Testing: {range_name} ({start_date} to {end_date})")
        print('='*60)

        # Fetch from both sources
        print(f"\nFetching Polygon news for {ticker}...")
        polygon_articles = fetch_polygon_news(ticker, start_date, end_date, polygon_key)
        time.sleep(1)  # Rate limit

        print(f"Fetching Finnhub news for {ticker}...")
        finnhub_articles = fetch_finnhub_news(ticker, start_date, end_date, finnhub_key)

        # Analyze by publisher
        polygon_by_pub = analyze_by_publisher(polygon_articles, "Polygon")
        finnhub_by_pub = analyze_by_publisher(finnhub_articles, "Finnhub")

        print(f"\n--- Polygon ({len(polygon_articles)} total) ---")
        for pub, count in polygon_by_pub.items():
            print(f"  {pub}: {count}")

        print(f"\n--- Finnhub ({len(finnhub_articles)} total) ---")
        for pub, count in finnhub_by_pub.items():
            print(f"  {pub}: {count}")

        # Analyze Seeking Alpha overlap
        sa_analysis = analyze_seeking_alpha(polygon_articles, finnhub_articles)

        print(f"\n--- Seeking Alpha 比較 ---")
        print(f"Polygon Seeking Alpha: {sa_analysis['polygon_seeking_alpha_count']} 篇")
        print(f"Finnhub SeekingAlpha: {sa_analysis['finnhub_seeking_alpha_count']} 篇")
        print(f"重疊標題數: {sa_analysis['common_titles_count']}")
        print(f"Polygon 獨有: {sa_analysis['polygon_only_count']}")
        print(f"Finnhub 獨有: {sa_analysis['finnhub_only_count']}")

        if sa_analysis['common_titles_sample']:
            print(f"\n重疊標題範例:")
            for t in sa_analysis['common_titles_sample'][:3]:
                print(f"  - {t}")

        results[range_name] = {
            "polygon_total": len(polygon_articles),
            "finnhub_total": len(finnhub_articles),
            "polygon_by_publisher": polygon_by_pub,
            "finnhub_by_publisher": finnhub_by_pub,
            "seeking_alpha_analysis": sa_analysis,
        }

        time.sleep(2)  # Be nice to APIs

    # Save results
    output_path = Path(__file__).parent / "comparison_results" / "seeking_alpha_overlap.json"
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "ticker": ticker,
            "results": results,
        }, f, indent=2, ensure_ascii=False)

    print(f"\n\nResults saved to: {output_path}")

    # Summary
    print("\n" + "="*60)
    print("總結")
    print("="*60)

    for range_name, data in results.items():
        sa = data['seeking_alpha_analysis']
        print(f"\n{range_name}:")
        print(f"  Polygon total: {data['polygon_total']}, Finnhub total: {data['finnhub_total']}")
        print(f"  Seeking Alpha - Polygon: {sa['polygon_seeking_alpha_count']}, Finnhub: {sa['finnhub_seeking_alpha_count']}")
        print(f"  重疊: {sa['common_titles_count']}, Polygon獨有: {sa['polygon_only_count']}, Finnhub獨有: {sa['finnhub_only_count']}")


if __name__ == "__main__":
    main()