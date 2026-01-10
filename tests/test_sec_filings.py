#!/usr/bin/env python3
"""
SEC Filings 整合模組測試

測試 SECFilingsClient 的所有功能：
- 結構化財務數據 (XBRL)
- 10-K 章節內容解析
- 財務報表 DataFrame
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources.sec_filings import SECFilingsClient


def test_basic_info():
    """測試基本資訊"""
    print("=" * 60)
    print("1. 基本資訊")
    print("=" * 60)

    client = SECFilingsClient('AAPL')
    print(f"Ticker: {client.ticker}")
    print(f"公司名稱: {client.company_name}")
    print(f"CIK: {client.cik}")

    return client


def test_financial_metrics(client):
    """測試財務指標取得"""
    print("\n" + "=" * 60)
    print("2. 財務指標 (XBRL)")
    print("=" * 60)

    # 取得最新財務指標
    print("\n--- 最新財務指標 ---")
    latest = client.get_latest_metrics([
        'revenue', 'net_income', 'total_assets', 'eps_diluted', 'cash'
    ])

    for name, metric in latest.items():
        if metric.unit == 'USD':
            value_str = f"${metric.value/1e9:.2f}B"
        elif metric.unit == 'USD/shares':
            value_str = f"${metric.value:.2f}"
        else:
            value_str = f"{metric.value:,.0f}"

        print(f"  {name}: {value_str} ({metric.end_date}, {metric.form})")

    # 取得歷史數據
    print("\n--- 淨利歷史 (5年) ---")
    net_income_history = client.get_metric('net_income', periods=5)
    for m in net_income_history:
        print(f"  {m.end_date}: ${m.value/1e9:.2f}B")

    return latest


def test_10k_sections(client):
    """測試 10-K 章節解析"""
    print("\n" + "=" * 60)
    print("3. 10-K 章節內容")
    print("=" * 60)

    sections = ['business', 'risk_factors', 'mda']

    for section in sections:
        print(f"\n--- {section.upper()} (前 500 字) ---")
        content = client.get_10k_section(section, max_length=500)
        if content:
            print(f"[Item {content.item_number}] {content.filing_date}")
            print(content.content)
        else:
            print("  [無法取得]")


def test_financial_statements(client):
    """測試財務報表 DataFrame"""
    print("\n" + "=" * 60)
    print("4. 財務報表 DataFrame")
    print("=" * 60)

    # 資產負債表
    print("\n--- 資產負債表 ---")
    bs = client.get_balance_sheet()
    if bs is not None:
        print(f"Shape: {bs.shape}")
        print(bs.head(10))
    else:
        print("  [無法取得 DataFrame]")

    # 損益表
    print("\n--- 損益表 ---")
    inc = client.get_income_statement()
    if inc is not None:
        print(f"Shape: {inc.shape}")
        print(inc.head(10))
    else:
        print("  [無法取得 DataFrame]")


def test_filings_list(client):
    """測試財報列表"""
    print("\n" + "=" * 60)
    print("5. 財報列表")
    print("=" * 60)

    filings = client.get_filings_list(form_types=['10-K', '10-Q'])
    print(f"找到 {len(filings)} 份財報")

    for f in filings[:5]:
        print(f"  {f.filing_date} - {f.filing_type}: {f.title}")


def test_summary(client):
    """測試摘要功能"""
    print("\n" + "=" * 60)
    print("6. 公司財務摘要")
    print("=" * 60)

    summary = client.summary()
    print(f"Ticker: {summary['ticker']}")
    print(f"Company: {summary['company_name']}")
    print(f"CIK: {summary['cik']}")
    print("\nLatest Metrics:")
    for name, data in summary['latest_metrics'].items():
        print(f"  {name}: {data['value']:,.0f} {data['unit']} ({data['end_date']})")


def main():
    print("=" * 60)
    print("SEC Filings 整合模組測試")
    print("=" * 60)

    # 1. 基本資訊
    client = test_basic_info()

    # 2. 財務指標
    test_financial_metrics(client)

    # 3. 10-K 章節
    test_10k_sections(client)

    # 4. 財務報表 DataFrame
    test_financial_statements(client)

    # 5. 財報列表
    test_filings_list(client)

    # 6. 摘要
    test_summary(client)

    print("\n" + "=" * 60)
    print("✅ 所有測試完成")
    print("=" * 60)


if __name__ == '__main__':
    main()