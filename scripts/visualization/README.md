# Visualization Scripts

視覺化和互動查詢工具。

## 檔案結構

```
scripts/visualization/
├── news_dashboard.py       # Streamlit 新聞儀表板 (進入點)
├── data_loader.py          # 數據載入模組 (被 dashboard 呼叫)
├── fundamentals_query.py   # CLI 基本面互動查詢 (獨立工具)
└── README.md
```

## 工具說明

### 1. News Dashboard (Streamlit)

新聞數據視覺化儀表板，支援 Polygon、Finnhub、IBKR 三個來源。

**執行方式:**
```bash
streamlit run scripts/visualization/news_dashboard.py
```

**功能:**
- Overview: 數據摘要和統計
- Explorer: 瀏覽和搜索文章
- Analytics: 統計分析和圖表

**依賴:** `data_loader.py` (自動載入)

### 2. Fundamentals Query (CLI)

基本面數據命令列互動查詢工具。

**執行方式:**
```bash
python scripts/visualization/fundamentals_query.py
```

**命令範例:**
```
> AAPL                    # 查詢單一股票
> AAPL MSFT GOOGL         # 比較多支股票
> top roe                 # ROE 排行 (高→低)
> low pe                  # P/E 排行 (低→高)
> pe<20 roe>15            # 篩選條件
> help                    # 顯示說明
> q                       # 離開
```

**可用欄位:**
| 欄位 | 說明 |
|------|------|
| pe | P/E 本益比 |
| pb | P/B 股價淨值比 |
| ps | P/S 股價營收比 |
| roe | 股東權益報酬率 |
| roa | 資產報酬率 |
| gm | 毛利率 |
| om | 營業利益率 |
| nm | 淨利率 |
| cap | 市值 |
| eps | 每股盈餘 |
| div | 股息殖利率 |

**數據來源:** `data_lake/raw/ibkr_fundamentals/fundamentals_summary_*.csv`

## 依賴套件

```
streamlit
pandas
plotly
```

## 相關檔案

- `scripts/collection/collect_ibkr_fundamentals.py` - 基本面數據收集
- `data_sources/ibkr_source.py` - IBKR 數據源