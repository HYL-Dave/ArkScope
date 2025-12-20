# 數據收集系統使用指南

## 相關文檔

- **[DATA_DICTIONARY.md](DATA_DICTIONARY.md)** - 資料欄位定義與格式說明

---

## 架構說明

### scripts/collection/ vs data_sources/ 關係

```
專案結構:
├── data_sources/              # 底層 API 封裝 (用於測試/開發)
│   ├── polygon_source.py     # Polygon 封裝 (class-based)
│   ├── finnhub_source.py     # Finnhub 封裝 (class-based)
│   ├── ibkr_source.py        # IBKR 封裝 (需 ib_insync)
│   └── test_*.py             # API 測試腳本
│
└── scripts/collection/        # ⭐ 實際使用的收集腳本
    ├── daily_update.py           # ⭐ 統一調度入口 (推薦)
    ├── collect_polygon_news.py   # Polygon 新聞 (獨立實作)
    ├── collect_finnhub_news.py   # Finnhub 新聞 (獨立實作)
    ├── collect_ibkr_news.py      # IBKR 新聞 (使用 data_sources)
    └── collect_ibkr_prices.py    # IBKR 股價 (使用 data_sources)
```

**日常使用**: 直接執行 `scripts/collection/` 下的腳本即可

**設計說明**:
| 腳本 | 依賴 data_sources? | 說明 |
|------|-------------------|------|
| collect_polygon_news.py | ❌ 獨立 | 針對批量收集優化，直接呼叫 API |
| collect_finnhub_news.py | ❌ 獨立 | 針對批量收集優化，直接呼叫 API |
| collect_ibkr_news.py | ✅ 依賴 | 使用 `data_sources.IBKRDataSource` |
| collect_ibkr_prices.py | ✅ 依賴 | 使用 `data_sources.IBKRDataSource` |

**data_sources/ 用途**:
- API 測試和驗證 (`test_polygon.py`, `test_finnhub.py` 等)
- 比較不同 API 來源的資料品質
- 為 IBKR 股價收集提供封裝

---

## 快速開始

### 第一步：確認 API Key

確保 `config/.env` 已設定：
```bash
POLYGON_API_KEY=your_actual_key_here
FINNHUB_API_KEY=your_actual_key_here
```

### 第二步：收集策略

```
時間軸:
           2022        2023        2024        2025.12     未來
           ←──────────────────────────────────────│──────────→
Polygon:   ██████████████████████████████████████│██████████  歷史 + 持續
Finnhub:                                   ██████│██████████  7 天前 + 持續
```

| 來源 | 歷史深度 | 文章數量 | 有情緒 | 主要來源 |
|------|---------|---------|-------|---------|
| Polygon | 3+ 年 | 較少 | ✅ | Motley Fool, Benzinga |
| Finnhub | 7 天 | 較多 | ❌ | Yahoo (70%), SeekingAlpha (24%) |

**兩者互補，都要收集！**

### 第三步：執行收集

```bash
# 從專案根目錄執行
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday

# === Step 1: Finnhub 先跑 (快，~1 分鐘) ===
python scripts/collection/collect_finnhub_news.py

# === Step 2: Polygon 歷史 (慢，~10 小時) ===
# 先估算時間
python scripts/collection/collect_polygon_news.py --full-history --estimate

# 開始收集
python scripts/collection/collect_polygon_news.py --full-history
```

**重要提示**:
- 可隨時按 `Ctrl+C` 中斷，進度會自動儲存
- 中斷後用 `--resume` 繼續
- 收集過程中會顯示進度百分比

### 第四步：未來每日更新 (排程)

收集完成後，建議設定每日排程：
```bash
# crontab -e
# 每天 UTC 6:00 收集 Finnhub (快)
0 6 * * * cd /path/to/project && python scripts/collection/collect_finnhub_news.py

# 每天 UTC 7:00 收集 Polygon 前一天 (慢)
0 7 * * * cd /path/to/project && python scripts/collection/collect_polygon_news.py --days 1
```

---

## 腳本功能說明

### collect_polygon_news.py (主要)

**用途**: 收集 3+ 年歷史新聞

| 參數 | 說明 |
|------|------|
| `--full-history` | 收集 2022-01-01 至今 |
| `--start YYYY-MM-DD` | 自訂起始日期 |
| `--end YYYY-MM-DD` | 自訂結束日期 |
| `--days N` | 最近 N 天 |
| `--tickers AAPL,MSFT` | 指定股票 |
| `--resume` | 從 checkpoint 繼續 |
| `--estimate` | 僅估算時間 |
| `--incremental` | ⭐ 增量更新 (時間戳精度，見下方說明) |
| `--status` | 查看現有資料狀態 |

**Rate Limit**: 5 次/分鐘 (12 秒間隔) - 免費版限制

### collect_finnhub_news.py (補充)

**用途**: 收集最近 7 天新聞 (Finnhub 無歷史)

| 參數 | 說明 |
|------|------|
| `--days N` | 最近 N 天 (最多 7 天) |
| `--tickers AAPL,MSFT` | 指定股票 |
| `--incremental` | ⭐ 增量更新 (動態天數，見下方說明) |
| `--status` | 查看現有資料狀態 |

**Rate Limit**: 60 次/分鐘 (1 秒間隔) - 比 Polygon 快 12 倍

**注意**: Finnhub 免費版只有 ~7 天歷史，不適合歷史收集！

### collect_ibkr_news.py (高品質)

**用途**: 收集 IBKR 新聞 (Dow Jones, Briefing.com, The Fly)

| 參數 | 說明 |
|------|------|
| `--days N` | 最近 N 天 (最多 ~30 天) |
| `--tickers AAPL,MSFT` | 指定股票 |
| `--host` / `--port` | IBKR Gateway 連線設定 |
| `--incremental` | ⭐ 增量更新 (時間戳精度) |
| `--status` | 查看現有資料狀態 |

**需求**: IB Gateway/TWS 運行中 + 新聞訂閱

---

## 增量更新邏輯 (--incremental)

各來源使用不同精度的增量更新策略：

| 來源 | 精度 | 邏輯說明 |
|------|------|---------|
| **Polygon** | 秒級時間戳 | `published_utc.gte = latest_ts + 1秒` |
| **IBKR** | 秒級時間戳 | `startDateTime = latest_ts + 1秒` |
| **Finnhub** | 動態天數 | `days = ceil(hours_behind / 24)`，max 7 天 |

### Polygon / IBKR 時間戳精度

```
INCREMENTAL MODE (timestamp precision)
  Latest article: 2025-12-20T14:32:00Z
  Fetching from:  2025-12-20T14:32:01Z
```

**效益**:
- 可每小時更新，幾乎無重複資料
- API 呼叫效率最大化

### Finnhub 動態天數

```
INCREMENTAL MODE (dynamic days)
  Latest article: 2025-12-20T10:00:00
  Hours behind: 4.5h → fetching 1 days
```

**邏輯**:
- 計算距離最新文章的小時數
- 無條件進位到整數天 (`math.ceil`)
- 上限 7 天 (API 限制)

---

## 每日更新 (daily_update.py) ⭐

**推薦使用**: 統一管理所有資料源的增量更新

### 查看資料狀態

```bash
python scripts/collection/daily_update.py --status
```

輸出範例：
```
📰 POLYGON NEWS:
   Total articles: 107,713
   Latest data:    2025-12-17 (0 days ago)

📰 FINNHUB NEWS:
   Total articles: 3,484
   Latest data:    2025-12-16 (1 days ago)

📈 IBKR PRICES:
   Total bars:     1,473,563
   Tickers:        75
   Latest data:    2025-12-16 (1 days ago)
```

### 增量更新命令

```bash
# 更新所有新聞 (Polygon + Finnhub + IBKR)
python scripts/collection/daily_update.py --news

# 更新所有資料 (新聞 + 股價)
python scripts/collection/daily_update.py --all

# 只更新特定來源
python scripts/collection/daily_update.py --polygon
python scripts/collection/daily_update.py --finnhub
python scripts/collection/daily_update.py --ibkr-news    # IBKR 新聞
python scripts/collection/daily_update.py --ibkr-prices  # IBKR 股價

# 模擬執行 (不實際收集)
python scripts/collection/daily_update.py --all --dry-run
```

### Cron 排程範例

```bash
# crontab -e
# 每天 UTC 6:00 更新新聞 (~1-2 分鐘)
0 6 * * * cd /mnt/md0/PycharmProjects/MindfulRL-Intraday && python scripts/collection/daily_update.py --news

# 每天 UTC 22:00 更新股價 (美股收盤後，需要 IBKR 連線)
0 22 * * * cd /mnt/md0/PycharmProjects/MindfulRL-Intraday && python scripts/collection/daily_update.py --ibkr
```

---

## 股價收集 (IBKR)

### collect_ibkr_prices.py

**用途**: 從 IBKR 收集歷史股價 (需要 TWS 或 IB Gateway 運行中)

**前置需求**:
```bash
pip install ib_insync
# 啟動 TWS 或 IB Gateway，並啟用 API
```

### 命令參數

| 參數 | 說明 |
|------|------|
| `--output DIR` | 輸出目錄 (預設: data/prices/) |
| `--tickers AAPL,MSFT` | 指定股票 |
| `--tier tier1_core` | 使用 config 股票層級 |
| `--port 7497` | IBKR 連接埠 |
| `--hourly-only` | 只收 2023 年 1 小時資料 |
| `--minute-only` | 只收 2024+ 年 15 分鐘資料 |
| `--dry-run` | 模擬執行，不實際呼叫 API |
| `--incremental` | ⭐ 增量更新 (從最後日期開始) |
| `--status` | 查看現有資料狀態 |
| `--resume` | 從 checkpoint 繼續 |
| `--clear-checkpoint` | 清除 checkpoint 重新開始 |

### 常用命令

```bash
# 模擬執行 (先確認設定正確)
python scripts/collection/collect_ibkr_prices.py --dry-run

# 完整收集 (2023 hourly + 2024 15min)
python scripts/collection/collect_ibkr_prices.py --output data/prices/

# 只收 2023 年 hourly
python scripts/collection/collect_ibkr_prices.py --hourly-only

# 只收 2024+ 15min
python scripts/collection/collect_ibkr_prices.py --minute-only

# 指定 port (TWS paper: 7497, TWS live: 7496, GW paper: 4002, GW live: 4001)
python scripts/collection/collect_ibkr_prices.py --port 4001

# 載入所有股票 (tier1 + tier2)
python scripts/collection/collect_ibkr_prices.py --tier all

# 查看現有資料狀態
python scripts/collection/collect_ibkr_prices.py --status

# 增量更新 (只抓取最後日期之後的新資料)
python scripts/collection/collect_ibkr_prices.py --incremental --minute-only
```

### 中斷與恢復 (Checkpoint/Resume)

腳本支援中斷後恢復，可以隨時按 `Ctrl+C` 中斷：

```bash
# 開始收集 (會自動儲存 checkpoint)
python scripts/collection/collect_ibkr_prices.py --tier all

# 按 Ctrl+C 中斷後，用 --resume 繼續
python scripts/collection/collect_ibkr_prices.py --tier all --resume

# 清除 checkpoint 重新開始
python scripts/collection/collect_ibkr_prices.py --clear-checkpoint
```

**Checkpoint 檔案**: `data/prices/ibkr_checkpoint.json`

- 每完成一支股票自動儲存進度
- `--resume` 會跳過已完成的股票
- 完成後 checkpoint 自動清除

### 輸出格式

```
data/prices/
├── hourly/                    # 2023 年 1 小時資料
│   ├── AAPL_hourly_2023.csv
│   ├── MSFT_hourly_2023.csv
│   └── ...
├── 15min/                     # 2024+ 年 15 分鐘資料
│   ├── AAPL_15min_2024_2025.csv
│   ├── MSFT_15min_2024_2025.csv
│   └── ...
└── collection_summary.json    # 收集統計
```

### CSV 欄位

| 欄位 | 類型 | 說明 |
|------|------|------|
| datetime | str | ISO 時間戳 |
| open | float | 開盤價 |
| high | float | 最高價 |
| low | float | 最低價 |
| close | float | 收盤價 |
| volume | int | 成交量 |
| ticker | str | 股票代號 |

---

## 資料儲存位置

```
data/news/
├── raw/
│   ├── polygon/           # Polygon 原始資料
│   │   ├── 2022/
│   │   │   ├── 2022-01.parquet
│   │   │   ├── 2022-02.parquet
│   │   │   └── ...
│   │   ├── 2023/
│   │   ├── 2024/
│   │   └── 2025/
│   │
│   ├── finnhub/           # Finnhub 原始資料
│   │   └── 2025/
│   │       └── 2025-12.parquet
│   │
│   └── ibkr/              # IBKR 原始資料 (高品質)
│       └── 2025/
│           └── 2025-12.parquet
│
├── merged/                # 合併去重後
│   └── 2025/
│       └── 2025-12.parquet
│
└── metadata/
    ├── collection_stats.json           # Polygon 統計
    ├── finnhub_collection_stats.json   # Finnhub 統計
    ├── ibkr_collection_stats.json      # IBKR 統計
    └── polygon_collection_checkpoint.json  # 進度檔
```

---

## 收集策略比較

| 來源 | 歷史深度 | 每日文章數 | 主要發布商 | 有情緒分數 | 增量精度 |
|------|---------|----------|-----------|----------|---------|
| Polygon | 3+ 年 | ~20-40 | Motley Fool, Benzinga | ✅ | 秒級時間戳 |
| Finnhub | 7 天 | ~150+ | Yahoo (77%) | ❌ | 動態天數 |
| IBKR | ~30 天 | 高品質 | Dow Jones, Briefing.com | ❌ | 秒級時間戳 |

### 建議策略

1. **歷史收集**: 只用 Polygon (有完整歷史 + 情緒分數)
2. **每日更新**:
   - 選項 A: 只用 Polygon (品質優先)
   - 選項 B: 三者都用 + 合併 (覆蓋優先)
3. **高頻更新**: Polygon + IBKR (秒級時間戳，可每小時更新)

---

## 常見問題

### Q: 收集需要多久？

| 範圍 | 股票數 | 估計時間 |
|------|-------|---------|
| 3 年完整歷史 | 30 (tier1) | ~10 小時 |
| 1 個月 | 30 | ~12 分鐘 |
| 7 天 | 30 | ~6 分鐘 |

### Q: 可以中斷嗎？

可以！按 `Ctrl+C` 中斷，進度會自動儲存到 checkpoint。
用 `--resume` 繼續。

### Q: 收集完成後需要排程嗎？

建議設定每日排程：
```bash
# 每天早上 6:00 執行 (UTC)
0 6 * * * cd /path/to/project && python collect_polygon_news.py --days 1
```

### Q: Polygon 和 Finnhub 有重複嗎？

有。相同的 Seeking Alpha 文章可能同時出現在兩邊。
用 `collect_all_news.py --merge` 會自動去重。

---

## 資料格式 (Parquet 欄位)

| 欄位 | 類型 | 說明 |
|------|------|------|
| article_id | str | 唯一識別碼 |
| ticker | str | 股票代號 |
| title | str | 標題 |
| published_at | str | 發布時間 (ISO) |
| source_api | str | 來源 (polygon/finnhub) |
| description | str | 摘要 |
| content | str | 內容 |
| url | str | 原文連結 |
| publisher | str | 發布商 |
| source_sentiment | float | 內建情緒 (-1 to 1) |
| dedup_hash | str | 去重 hash |

---

*最後更新: 2025-12-20*