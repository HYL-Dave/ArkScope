#!/usr/bin/env python3
"""
基本面數據互動查詢工具
簡單查詢、排序、篩選股票基本面數據
"""

import pandas as pd
from pathlib import Path
import sys

DATA_DIR = Path("data_lake/raw/ibkr_fundamentals")


def load_data() -> pd.DataFrame:
    """載入最新的 summary CSV"""
    csv_files = sorted(DATA_DIR.glob("fundamentals_summary_*.csv"), reverse=True)
    if not csv_files:
        print("錯誤: 找不到 fundamentals_summary CSV")
        sys.exit(1)

    df = pd.read_csv(csv_files[0])
    # 過濾無效數據 (用 -100000 表示 N/A 的情況)
    for col in ['pe_ratio', 'price_to_book', 'price_to_sales']:
        if col in df.columns:
            df.loc[df[col] < -1000, col] = pd.NA
    return df


def fmt(val, suffix="", prefix="", decimals=1, scale=1):
    """格式化數值"""
    if pd.isna(val):
        return "N/A"
    return f"{prefix}{val/scale:,.{decimals}f}{suffix}"


def show_stock(df: pd.DataFrame, ticker: str):
    """顯示單一股票詳細資訊"""
    ticker = ticker.upper()
    row = df[df['ticker'] == ticker]

    if row.empty:
        print(f"找不到: {ticker}")
        return

    r = row.iloc[0]
    print(f"\n{'='*50}")
    print(f"  {r['ticker']} - {r.get('company_name', 'N/A')}")
    print(f"{'='*50}")
    print(f"  價格: {fmt(r.get('price'), prefix='$', decimals=2)}")
    print(f"  市值: {fmt(r.get('market_cap_m'), suffix='M', prefix='$', decimals=0)}")
    print()
    print(f"  --- 估值 ---")
    print(f"  P/E:  {fmt(r.get('pe_ratio'))}")
    print(f"  P/B:  {fmt(r.get('price_to_book'))}")
    print(f"  P/S:  {fmt(r.get('price_to_sales'))}")
    print()
    print(f"  --- 獲利 ---")
    print(f"  ROE:      {fmt(r.get('roe_pct'), suffix='%')}")
    print(f"  ROA:      {fmt(r.get('roa_pct'), suffix='%')}")
    print(f"  毛利率:   {fmt(r.get('gross_margin_pct'), suffix='%')}")
    print(f"  營業利潤: {fmt(r.get('operating_margin_pct'), suffix='%')}")
    print(f"  淨利率:   {fmt(r.get('net_margin_pct'), suffix='%')}")
    print()
    print(f"  --- 每股 ---")
    print(f"  EPS:  {fmt(r.get('eps_ttm'), prefix='$', decimals=2)}")
    print(f"  淨值: {fmt(r.get('book_value_ps'), prefix='$', decimals=2)}")
    print(f"  股息殖利率: {fmt(r.get('dividend_yield_pct'), suffix='%')}")
    print()


# 欄位別名對應
FIELD_MAP = {
    'pe': 'pe_ratio',
    'pb': 'price_to_book',
    'ps': 'price_to_sales',
    'roe': 'roe_pct',
    'roa': 'roa_pct',
    'gm': 'gross_margin_pct',
    'margin': 'gross_margin_pct',
    'om': 'operating_margin_pct',
    'nm': 'net_margin_pct',
    'cap': 'market_cap_m',
    'mcap': 'market_cap_m',
    'eps': 'eps_ttm',
    'div': 'dividend_yield_pct',
    'beta': 'beta',
}


def get_column(field: str) -> str:
    """欄位別名對應"""
    return FIELD_MAP.get(field.lower(), field)


def show_top(df: pd.DataFrame, field: str, n: int = 20, ascending: bool = False):
    """顯示排行榜"""
    col = get_column(field)
    if col not in df.columns:
        print(f"無效欄位: {field}")
        print(f"可用: {list(FIELD_MAP.keys())}")
        return

    valid = df[df[col].notna() & (df[col] > -1000)].copy()
    sorted_df = valid.sort_values(col, ascending=ascending).head(n)

    order = "低→高" if ascending else "高→低"
    print(f"\n{'='*70}")
    print(f"  Top {n} by {field} ({order})")
    print(f"{'='*70}")
    print(f"{'Ticker':<8} {'Company':<22} {field:<12} {'P/E':<8} {'ROE':<8} {'MCap':<10}")
    print("-" * 70)

    for _, r in sorted_df.iterrows():
        val = r[col]
        if 'margin' in col or 'pct' in col:
            val_str = f"{val:.1f}%"
        elif col == 'market_cap_m':
            val_str = f"${val/1000:,.0f}B"
        else:
            val_str = f"{val:.1f}"

        pe = f"{r['pe_ratio']:.1f}" if pd.notna(r.get('pe_ratio')) and r.get('pe_ratio', -99999) > -1000 else "-"
        roe = f"{r['roe_pct']:.1f}%" if pd.notna(r.get('roe_pct')) else "-"
        cap = f"${r['market_cap_m']/1000:,.0f}B" if pd.notna(r.get('market_cap_m')) else "-"
        name = str(r.get('company_name', ''))[:21]

        print(f"{r['ticker']:<8} {name:<22} {val_str:<12} {pe:<8} {roe:<8} {cap:<10}")
    print()


def show_filter(df: pd.DataFrame, conditions: str):
    """篩選股票 (例如: pe<20 roe>15)"""
    result = df.copy()
    # 先過濾掉無效的 P/E
    result = result[(result['pe_ratio'].isna()) | (result['pe_ratio'] > -1000)]

    for cond in conditions.split():
        try:
            if '<' in cond:
                field, val = cond.split('<')
                col = get_column(field)
                if col in result.columns:
                    result = result[result[col].notna() & (result[col] < float(val)) & (result[col] > -1000)]
            elif '>' in cond:
                field, val = cond.split('>')
                col = get_column(field)
                if col in result.columns:
                    result = result[result[col].notna() & (result[col] > float(val))]
        except Exception as e:
            print(f"無效條件: {cond}")
            continue

    if result.empty:
        print("無符合條件的股票")
        return

    print(f"\n找到 {len(result)} 支股票:")
    print(f"{'Ticker':<8} {'Company':<20} {'P/E':<8} {'P/B':<8} {'ROE':<10} {'GM':<10} {'MCap':<10}")
    print("-" * 75)

    for _, r in result.head(30).iterrows():
        pe = f"{r['pe_ratio']:.1f}" if pd.notna(r.get('pe_ratio')) and r.get('pe_ratio', -99999) > -1000 else "-"
        pb = f"{r['price_to_book']:.1f}" if pd.notna(r.get('price_to_book')) and r.get('price_to_book', -99999) > -1000 else "-"
        roe = f"{r['roe_pct']:.1f}%" if pd.notna(r.get('roe_pct')) and r.get('roe_pct', -99999) > -1000 else "-"
        gm = f"{r['gross_margin_pct']:.1f}%" if pd.notna(r.get('gross_margin_pct')) and r.get('gross_margin_pct', -99999) > -1000 else "-"
        cap = f"${r['market_cap_m']/1000:,.0f}B" if pd.notna(r.get('market_cap_m')) else "-"
        name = str(r.get('company_name', ''))[:19]
        print(f"{r['ticker']:<8} {name:<20} {pe:<8} {pb:<8} {roe:<10} {gm:<10} {cap:<10}")
    print()


def show_compare(df: pd.DataFrame, tickers: list):
    """比較多支股票"""
    tickers = [t.upper() for t in tickers]
    subset = df[df['ticker'].isin(tickers)]

    if subset.empty:
        print("找不到指定股票")
        return

    print(f"\n{'='*85}")
    print("  股票比較")
    print(f"{'='*85}")
    print(f"{'Ticker':<8} {'Price':<10} {'P/E':<8} {'P/B':<8} {'ROE':<10} {'GM':<10} {'MCap':<12}")
    print("-" * 85)

    for _, r in subset.iterrows():
        price = f"${r['price']:,.0f}" if pd.notna(r.get('price')) else "-"
        pe = f"{r['pe_ratio']:.1f}" if pd.notna(r.get('pe_ratio')) and r.get('pe_ratio', -99999) > -1000 else "-"
        pb = f"{r['price_to_book']:.1f}" if pd.notna(r.get('price_to_book')) and r.get('price_to_book', -99999) > -1000 else "-"
        roe = f"{r['roe_pct']:.1f}%" if pd.notna(r.get('roe_pct')) else "-"
        gm = f"{r['gross_margin_pct']:.1f}%" if pd.notna(r.get('gross_margin_pct')) else "-"
        cap = f"${r['market_cap_m']/1000:,.0f}B" if pd.notna(r.get('market_cap_m')) else "-"
        print(f"{r['ticker']:<8} {price:<10} {pe:<8} {pb:<8} {roe:<10} {gm:<10} {cap:<12}")
    print()


def show_help():
    print("""
基本面查詢工具
==============

命令:
  AAPL              查詢單一股票
  AAPL MSFT GOOGL   比較多支股票
  top pe            P/E 排行 (高→低)
  top roe           ROE 排行 (高→低)
  low pe            P/E 排行 (低→高，找便宜股)
  pe<20 roe>15      篩選條件 (可組合)
  list              列出所有股票
  help              顯示說明
  q                 離開

可用欄位:
  pe    P/E 本益比
  pb    P/B 股價淨值比
  ps    P/S 股價營收比
  roe   股東權益報酬率
  roa   資產報酬率
  gm    毛利率
  om    營業利益率
  nm    淨利率
  cap   市值
  eps   每股盈餘
  div   股息殖利率

範例:
  > AAPL                    # 查詢 Apple
  > top roe                 # ROE 最高的股票
  > low pe                  # P/E 最低的股票
  > pe<25 roe>20            # 便宜又賺錢
  > AAPL MSFT NVDA GOOGL    # 比較科技巨頭
""")


def main():
    df = load_data()
    print(f"已載入 {len(df)} 支股票基本面數據")
    print("輸入 help 查看說明，q 離開\n")

    while True:
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not cmd:
            continue

        if cmd.lower() in ['q', 'quit', 'exit']:
            break

        if cmd.lower() == 'help':
            show_help()
        elif cmd.lower() == 'list':
            tickers = df['ticker'].tolist()
            print(f"共 {len(tickers)} 支: {', '.join(tickers)}")
        elif cmd.lower().startswith('top '):
            field = cmd[4:].strip()
            show_top(df, field, ascending=False)
        elif cmd.lower().startswith('low '):
            field = cmd[4:].strip()
            show_top(df, field, ascending=True)
        elif '<' in cmd or '>' in cmd:
            show_filter(df, cmd)
        elif ' ' in cmd:
            tickers = cmd.split()
            show_compare(df, tickers)
        else:
            show_stock(df, cmd)


if __name__ == "__main__":
    main()