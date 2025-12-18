# IBKR (Interactive Brokers) 數據源指南

## 概述

IBKR 提供免費的歷史數據存取（含交易帳戶），適合作為 FinRL 訓練的主要數據來源。

## 運行方式比較

### TWS vs IB Gateway vs Docker

| 選項 | 資源使用 | GUI | 自動重啟 | 維護複雜度 | 適用場景 |
|------|---------|-----|---------|-----------|---------|
| **TWS** | 最高 (~600MB+) | 完整圖形介面 | 需設定 | 低 | 開發測試、需要看盤 |
| **IB Gateway** | **較低 (-40%)** | 最小化視窗 | 內建 (v974+) | 低 | **純 API 使用 (推薦)** |
| **Docker** | 最低 | 完全無 | 容器管理 | 中 | VPS/雲端、完全無人值守 |

> **API 角度三者功能完全相同**：From the perspective of an API application, IB Gateway and TWS are identical; both represent a server to which an API client application can open a socket connection.
> — [IBKR API Documentation](https://interactivebrokers.github.io/tws-api/initial_setup.html)

### 推薦選擇

| 情境 | 推薦 | 原因 |
|------|------|------|
| 有 Desktop 環境，需要看盤 | TWS | 完整功能 |
| **純 API，長期運行** | **IB Gateway** | 官方支援、資源少 40%、穩定 |
| VPS/雲端，完全無人值守 | Docker | 真正 headless |
| 偶爾手動 + API 自動化 | IB Gateway + 手機 App | 分開使用 |

### 作業系統比較

| 考量 | Ubuntu | Windows | macOS |
|------|--------|---------|-------|
| **穩定性** | 最穩定 (server 專用) | 穩定 | 穩定 |
| **資源消耗** | 最低 | 中 | 中 |
| **長期運行** | 最佳 | 需防止自動更新重啟 | 需防止睡眠 |
| **Headless 支援** | Xvfb + systemd | 需 RDP/VNC | 較麻煩 |
| **社群資源** | 最多教學 | 最簡單安裝 | 較少 |
| **Docker 支援** | 原生 | WSL2 | Docker Desktop |
| **伺服器部署** | **最適合** | 可以但非最佳 | 不建議 |

**推薦：Ubuntu** - 專為 server 設計，資源消耗最低，systemd 管理方便，社群資源豐富。

### IB Gateway 安裝 (Ubuntu)

```bash
# 下載 IB Gateway (Stable)
wget https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh

chmod +x ibgateway-stable-standalone-linux-x64.sh
./ibgateway-stable-standalone-linux-x64.sh

# 需要 X11 環境 (可用 Xvfb 虛擬)
sudo apt install xvfb
Xvfb :99 -screen 0 1024x768x24 &
export DISPLAY=:99
```

### IB Gateway + systemd 設定

```ini
# /etc/systemd/system/ibgateway.service
[Unit]
Description=IB Gateway
After=network.target

[Service]
Type=simple
User=trading
Environment=DISPLAY=:99
ExecStartPre=/usr/bin/Xvfb :99 -screen 0 1024x768x24 &
ExecStart=/home/trading/Jts/ibgateway/974/ibgateway
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ibgateway
sudo systemctl start ibgateway
```

## 連接方式

### Port 對照表

| Port | 說明 |
|------|------|
| 7497 | TWS Paper Trading |
| 7496 | TWS Live Trading |
| 4002 | IB Gateway Paper |
| 4001 | IB Gateway Live |
| 8888 | Docker (extrange/ibkr) |

### 連接範例

```python
from data_sources import IBKRDataSource

# TWS Paper Trading
ibkr = IBKRDataSource(port=7497)

# IB Gateway Paper
ibkr = IBKRDataSource(port=4002)

# IB Gateway Live
ibkr = IBKRDataSource(port=4001)

# Docker headless
ibkr = IBKRDataSource(port=8888)

# 使用 context manager (推薦)
with IBKRDataSource(port=4001) as ibkr:
    prices = ibkr.fetch_prices(['AAPL'], start_date=date(2023, 1, 1))
```

## 多重登入與額外 Username

### 核心概念

**額外 Username 是同一個帳戶的不同登入身份**，共用：
- 同樣的資金
- 同樣的持倉
- 同樣的交易紀錄

```
帳戶 U1234567 (你的資金、持倉都在這裡)
│
├── Username: your_main (主要)
│   ├── 手機 IBKR Mobile App
│   └── 偶爾用 TWS 看盤
│
└── Username: your_api (額外建立，免費)
    └── IB Gateway (Ubuntu server)
        ├── API Client 1 (client_id=1): 數據抓取
        └── API Client 2 (client_id=2): RL 自動交易

✓ 兩個 username 可以同時登入不同應用
✓ 操作的是同一個帳戶、同樣的錢
✓ your_api 下單 = your_main 看到持倉變化
```

### 登入限制規則

| 情境 | 是否允許 | 說明 |
|------|---------|------|
| 同一 username 登入多個交易應用 | **否** | 會被踢掉 |
| 同一 IB Gateway 接多個 API client | 是 | 最多 32 個 (不同 client_id) |
| 不同 username 同時登入不同應用 | **是** | 推薦做法 |

### 建立額外 Username 步驟

1. 登入 [Client Portal](https://www.interactivebrokers.com/portal)
2. 點擊右上角 **頭像圖示** → **Settings**
3. 找到 **Users & Access Rights**
4. 點擊 **+** 新增 User
5. 設定權限：
   - **Trading**: 允許交易
   - **Market Data**: 允許取得報價
   - **Account Information**: 允許查看帳戶

### 權限設定建議

| Username | Trading | Market Data | Funding | 用途 |
|----------|---------|-------------|---------|------|
| your_main | ✓ | ✓ | ✓ | 主要帳戶、手動操作 |
| your_api | ✓ | ✓ | ✗ | API 專用、禁止出入金 |

## Pacing 限制 (Rate Limits)

### 請求頻率限制

| 規則 | 限制 | 建議 |
|------|------|------|
| 10 分鐘限制 | 最多 60 請求 | 每請求間隔 ≥ 10 秒 |
| 2 秒限制 | 同 contract/type 最多 6 請求 | 避免快速重複 |
| 15 秒規則 | 相同請求不可重複 | 使用快取 |
| 併發限制 | 最多 50 同時請求 | 使用佇列 |

### 數據可用性

| Bar 頻率 | 最大歷史深度 | 以 2025-12 為基準可回溯至 |
|---------|-------------|------------------------|
| 1 秒 | 1 週 | 1 週前 |
| 5 秒 | 1 個月 | 2025-11 |
| 10/15/30 秒 | 6 個月 | 2025-06 |
| **1 分鐘** | **6 個月** | **2025-06** |
| **5 分鐘** | **~2 年** | **~2024-01** |
| **15 分鐘** | **~2 年** | **~2024-01** |
| 30 分鐘 | ~2 年 | ~2024-01 |
| **1 小時** | **多年** | **2020 以前** |
| **日線** | **多年** | **2000 以前** |
| 已到期期貨 | 2 年 | |
| 已下市股票 | 不可用 | |

> ⚠️ **關鍵限制**:
> - **15 分鐘 bars 無法取得 2023 年數據** (僅約 2 年歷史)
> - 若需 2023/01/01 起的完整日內數據，建議使用 **1 小時 bars**
> - 1 分鐘 bars 僅有 **6 個月**，不適合長期回測

## 可用數據類型

### Historical Bar Types (`whatToShow`)

| 類型 | 說明 | 使用場景 |
|------|------|---------|
| `TRADES` | 成交價 OHLCV | 標準價格數據 |
| `MIDPOINT` | 中間價 (bid+ask)/2 | 外匯、流動性分析 |
| `BID` | 買價 | 訂單簿分析 |
| `ASK` | 賣價 | 訂單簿分析 |
| `BID_ASK` | 時間加權價差 | 價差分析 |
| `ADJUSTED_LAST` | 調整後股價 (含股息/分割) | **RL 訓練 (推薦)** |
| `HISTORICAL_VOLATILITY` | 歷史波動率 | 風險指標 |
| `OPTION_IMPLIED_VOLATILITY` | 期權 IV | 期權策略 |
| `FEE_RATE` | 做空借券費率 | 做空成本分析 |

### 其他數據

| 數據 | API 方法 | Generic Tick |
|------|---------|-------------|
| 基本面比率 (P/E, EPS, Beta) | `reqMktData(contract, '258')` | 258 |
| 股息資訊 | `reqMktData(contract, '456')` | 456 |
| 新聞 | `reqHistoricalNews()` | 需訂閱 |
| WSH 事件 (財報日) | `getWshMetaData()` | 需訂閱 |

## API 方法對照

### IBKRDataSource 方法

```python
# 價格數據
fetch_prices(tickers, start_date, end_date, frequency)
fetch_intraday_prices(ticker, trade_date, interval)
fetch_historical_intraday(tickers, start_date, end_date, interval)
fetch_adjusted_prices(tickers, start_date, end_date)

# 其他數據
fetch_historical_volatility(ticker, start_date, end_date)
fetch_short_borrow_rate(ticker, start_date, end_date)
fetch_fundamental_ratios(ticker)
fetch_dividends(ticker)

# 合約資訊
get_contract_details(ticker)
get_current_quote(ticker)

# 連接管理
connect()
disconnect()
validate_credentials()
```

## Headless 運行 (Docker)

適用於完全無人值守的 VPS/雲端環境。

### 方案一：extrange/ibkr-docker

```yaml
# docker-compose.yml
services:
  ibkr:
    image: ghcr.io/extrange/ibkr:stable
    ports:
      - "8888:8888"  # API
      - "5900:5900"  # VNC (debug)
    environment:
      - IBKR_USERNAME=${IBKR_USERNAME}
      - IBKR_PASSWORD=${IBKR_PASSWORD}
      - TRADING_MODE=paper  # or 'live'
    restart: unless-stopped
```

```bash
# 啟動
docker-compose up -d

# 連接
ibkr = IBKRDataSource(port=8888)
```

### 方案二：IBGA (支援 TOTP)

```bash
docker run -d \
  -e TOTP_KEY=your_totp_secret \
  -p 4002:4002 \
  heshiming/ibga
```

### 取得 TOTP Secret

1. 登入 Client Portal
2. Settings > Security > Secure Login System
3. 重新設定 2FA，選擇「I want to manage my own key」
4. 記錄 Base32 secret key

## FinRL 訓練建議

### 推薦配置

```python
from data_sources import IBKRDataSource
from datetime import date
import pandas as pd

# 數據參數
START_DATE = date(2023, 1, 1)
END_DATE = date.today()
INTERVAL = "15 mins"  # 平衡精度與數據量
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", ...]

# 抓取歷史數據
with IBKRDataSource(port=4001) as ibkr:
    data = ibkr.fetch_historical_intraday(
        TICKERS,
        start_date=START_DATE,
        end_date=END_DATE,
        interval=INTERVAL
    )

    # 儲存為 parquet
    for ticker, bars in data.items():
        df = pd.DataFrame([vars(b) for b in bars])
        df.to_parquet(f"data_lake/raw/ibkr/{ticker}_15min.parquet")
```

### 時間估算

#### 15 分鐘 bars (~2 年數據, 2024/01 ~ 2025/12)

**基準：約 500 個交易日**

計算方式：
- 15 分鐘 bars，每次請求可抓 ~60 天
- 500 天 ÷ 60 天/請求 = ~9 次請求/股票
- Pacing 安全間隔: ~10 秒/請求

| 股票數 | 請求數 | 估計時間 |
|-------|--------|---------|
| 10 | 90 | ~15 分鐘 |
| 30 | 270 | ~45 分鐘 |
| 50 | 450 | ~75 分鐘 (~1.25 小時) |
| 100 | 900 | ~150 分鐘 (~2.5 小時) |

#### 1 小時 bars (完整 3 年, 2023/01 ~ 2025/12)

**基準：約 743 個交易日**

| 股票數 | 請求數 | 估計時間 |
|-------|--------|---------|
| 30 | ~60 | ~10 分鐘 |
| 50 | ~100 | ~17 分鐘 |
| 100 | ~200 | ~35 分鐘 |

> **建議策略**:
> - **2024/01 起**: 使用 15 分鐘 bars (較精細)
> - **2023 年補齊**: 使用 1 小時 bars (可降採樣至 15 分鐘)

## 常見問題

### Q: Pacing violation 怎麼處理？

```python
# 程式已內建處理，但如果還是遇到：
# 1. 增加 REQUEST_DELAY
ibkr = IBKRDataSource(port=4001)
ibkr.REQUEST_DELAY = 2.0  # 增加到 2 秒

# 2. 分批處理，中間休息
from itertools import batched
for batch in batched(tickers, 10):
    ibkr.fetch_prices(list(batch), ...)
    time.sleep(60)  # 每批休息 1 分鐘
```

### Q: 連不上 IB Gateway？

1. 確認 IB Gateway 正在運行
2. 確認 API 已啟用：Configure > API > Settings
   - Enable ActiveX and Socket Clients
   - Socket port: 4001 (live) 或 4002 (paper)
   - Allow connections from localhost
3. 確認防火牆沒有阻擋（詳見下方 Windows 防火牆章節）

### Q: Windows 防火牆導致 TWS 無法遠端連線？

**症狀**：IB Gateway 能遠端連線，但 TWS 被防火牆阻擋。關閉防火牆後 TWS 正常。

**根本原因**：TWS 自動更新會改變安裝路徑，導致防火牆規則失效。

```
TWS 更新前: C:\Jts\1028\jre\bin\java.exe  ← 防火牆規則指向這裡
TWS 更新後: C:\Jts\1030\jre\bin\java.exe  ← 實際執行的位置（被阻擋）
```

**為什麼 IB Gateway 不受影響？**
- IB Gateway 是 "offline" 版本，不會自動更新
- 安裝路徑穩定，防火牆規則持續有效

**解決方案 1：更新防火牆規則指向新路徑**

```powershell
# 1. 找出 TWS 實際的 Java 執行檔路徑
Get-ChildItem "C:\Jts" -Recurse -Filter "java.exe" | Select-Object FullName

# 2. 查看現有的 TWS 防火牆規則
Get-NetFirewallRule -DisplayName "*TWS*" | Get-NetFirewallApplicationFilter
Get-NetFirewallRule -DisplayName "*Trader*" | Get-NetFirewallApplicationFilter

# 3. 移除舊規則
Remove-NetFirewallRule -DisplayName "Trader Workstation" -ErrorAction SilentlyContinue

# 4. 為 TWS 的 Java 添加新規則（替換成實際路徑）
New-NetFirewallRule -DisplayName "TWS Java" -Direction Inbound -Program "C:\Jts\1030\jre\bin\java.exe" -Action Allow
```

> ⚠️ **注意**：每次 TWS 更新後都需要重新執行此步驟

**解決方案 2：改用 IB Gateway（推薦）**

既然 API 功能完全相同，使用 IB Gateway 是更穩定的選擇：

| 比較 | TWS | IB Gateway |
|------|-----|------------|
| 自動更新 | ✓（會破壞防火牆規則） | **✗（路徑穩定）** |
| 資源使用 | 較高 | **低 40%** |
| API 功能 | 完整 | **完整** |
| 遠端連線穩定性 | 需維護防火牆 | **穩定** |

**解決方案 3：僅允許本機連線**

如果可以在 TWS 所在的機器上執行 Python 腳本：

```python
# 本機連線不受防火牆影響
ib.connect('127.0.0.1', 7496, clientId=1)
```

**相關資源**：
- [Elite Trader: IB TWS and firewall](https://www.elitetrader.com/et/threads/ib-tws-and-firewall.352215/)
- [TWS API Connectivity](https://interactivebrokers.github.io/tws-api/connection.html)

### Q: 數據缺失？

- 已下市股票沒有數據
- 30 秒以下 bars 只有 6 個月歷史
- 確認有 Market Data 訂閱 (影響即時數據，不影響歷史數據)

### Q: 額外 Username 可以交易嗎？

可以！額外 Username 操作的是同一個帳戶：
- 同樣的資金池
- 同樣的持倉
- 下單後主帳戶立即看到

只需確保該 Username 有 Trading 權限。

### Q: IB Gateway vs Docker 怎麼選？

| 考量 | IB Gateway 原生 | Docker |
|------|----------------|--------|
| 官方支援 | ✓ | ✗ (社群維護) |
| 資源消耗 | 稍高 (需 Xvfb) | 較低 |
| 自動 2FA | 需手動或腳本 | 內建 TOTP |
| Debug 容易度 | 較容易 | 需 VNC |
| 推薦 | 本地 server | VPS/雲端 |

## 參考資料

- [IBKR TWS API Documentation](https://interactivebrokers.github.io/tws-api/)
- [Historical Data Limitations](https://interactivebrokers.github.io/tws-api/historical_limitations.html)
- [TWS vs IB Gateway Comparison](https://www.crazygeeks.org/questions/interactive-brokers-api-trader-workstation-tws-vs-ib-gateway)
- [Creating Users & User Roles](https://www.interactivebrokers.com/campus/trading-lessons/creating-users-and-user-roles/)
- [ib_insync Documentation](https://ib-insync.readthedocs.io/)
- [extrange/ibkr-docker](https://github.com/extrange/ibkr-docker)
- [heshiming/ibga](https://github.com/heshiming/ibga)