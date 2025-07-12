# 🚀 FinRL-DeepSeek 部署指南

本指南涵蓋在不同環境中部署 FinRL-DeepSeek 新聞爬取系統的詳細步驟。

## 📋 目錄

- [系統需求](#系統需求)
- [本地開發環境](#本地開發環境)
- [Docker 部署](#docker-部署)
- [生產環境部署](#生產環境部署)
- [雲端部署](#雲端部署)
- [監控和維護](#監控和維護)
- [故障排除](#故障排除)

## 🔧 系統需求

### 最低需求
- **CPU**: 2 核心
- **記憶體**: 4GB RAM
- **儲存**: 50GB 可用空間
- **網路**: 穩定的網際網路連接
- **作業系統**: Linux (Ubuntu 20.04+), macOS, Windows 10+

### 推薦配置
- **CPU**: 4 核心或以上
- **記憶體**: 8GB RAM 或以上
- **儲存**: 100GB SSD
- **網路**: 高速穩定連接（處理大量API請求）

### 軟體需求
- Python 3.8+
- Docker 20.10+ (可選)
- Docker Compose v2+ (可選)
- Git

## 🏠 本地開發環境

### 1. 克隆專案

```bash
git clone https://github.com/your-username/finrl-deepseek-extension.git
cd finrl-deepseek-extension
```

### 2. 設置虛擬環境

```bash
# 使用 venv
python -m venv venv

# 啟動虛擬環境
# Linux/Mac
source venv/bin/activate
# Windows
venv\Scripts\activate

# 升級 pip
pip install --upgrade pip
```

### 3. 安裝依賴

```bash
# 安裝基本依賴
pip install -r requirements.txt

# 開發環境額外依賴
pip install -r requirements-dev.txt

# 下載 NLTK 資料
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"
```

### 4. 配置環境

```bash
# 複製環境變數模板
cp .env.template .env

# 編輯環境變數（設置 OpenAI API 密鑰等）
nano .env

# 複製配置模板
cp config/config_template.json config/config.json

# 編輯配置文件
nano config/config.json
```

### 5. 準備數據

```bash
# 創建數據目錄
mkdir -p huggingface_datasets/FinRL_DeepSeek_sentiment/

# 下載原始 FinRL-DeepSeek 數據集
# 將 sentiment_deepseek_new_cleaned_nasdaq_news_full.csv 放入上述目錄
```

### 6. 運行測試

```bash
# 運行單元測試
python -m pytest tests/ -v

# 運行集成測試
python -m pytest tests/test_integration.py -v

# 檢查代碼品質
flake8 src/
black --check src/
```

### 7. 試運行

```bash
# 測試配置
python scripts/run_full_pipeline.py --config config/config.json --dry-run

# 小規模測試（處理少量數據）
python scripts/run_daily_crawl.py --config config/config.json --date 2024-07-12
```

## 🐳 Docker 部署

### 1. 準備環境

```bash
# 確保 Docker 和 Docker Compose 已安裝
docker --version
docker-compose --version

# 複製環境變數
cp .env.template .env
# 編輯 .env 文件，設置必要的環境變數
```

### 2. 構建和啟動

```bash
# 構建映像
docker-compose build

# 啟動服務
docker-compose up -d

# 檢查服務狀態
docker-compose ps
```

### 3. 初始化數據

```bash
# 進入容器
docker-compose exec finrl-crawler bash

# 運行初始化腳本
python scripts/initialize_data.py

# 測試爬取
python scripts/run_daily_crawl.py --date 2024-07-12
```

### 4. 監控服務

```bash
# 查看日誌
docker-compose logs -f finrl-crawler

# 查看資源使用
docker stats

# 訪問監控面板
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

## 🏭 生產環境部署

### 1. 服務器準備

```bash
# 更新系統
sudo apt update && sudo apt upgrade -y

# 安裝必要軟體
sudo apt install -y python3 python3-pip python3-venv git nginx supervisor

# 創建專用用戶
sudo useradd -m -s /bin/bash finrl
sudo usermod -aG sudo finrl
```

### 2. 應用部署

```bash
# 切換到 finrl 用戶
sudo su - finrl

# 克隆專案到生產目錄
git clone https://github.com/your-username/finrl-deepseek-extension.git /opt/finrl-deepseek
cd /opt/finrl-deepseek

# 設置虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 配置生產環境
cp .env.template .env
cp config/config_template.json config/config_production.json

# 編輯配置文件以適應生產環境
```

### 3. 系統服務配置

創建 systemd 服務文件：

```bash
sudo nano /etc/systemd/system/finrl-daily-crawl.service
```

```ini
[Unit]
Description=FinRL DeepSeek Daily News Crawler
After=network.target

[Service]
Type=oneshot
User=finrl
Group=finrl
WorkingDirectory=/opt/finrl-deepseek
Environment=PATH=/opt/finrl-deepseek/venv/bin
ExecStart=/opt/finrl-deepseek/venv/bin/python /opt/finrl-deepseek/scripts/run_daily_crawl.py --config /opt/finrl-deepseek/config/config_production.json
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

創建定時器：

```bash
sudo nano /etc/systemd/system/finrl-daily-crawl.timer
```

```ini
[Unit]
Description=Run FinRL DeepSeek Daily Crawler
Requires=finrl-daily-crawl.service

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

啟用服務：

```bash
sudo systemctl daemon-reload
sudo systemctl enable finrl-daily-crawl.timer
sudo systemctl start finrl-daily-crawl.timer
```

### 4. Nginx 配置（可選）

如果需要 Web 界面：

```bash
sudo nano /etc/nginx/sites-available/finrl-deepseek
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static/ {
        alias /opt/finrl-deepseek/static/;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/finrl-deepseek /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## ☁️ 雲端部署

### AWS EC2 部署

```bash
# 啟動 EC2 實例（推薦 t3.medium 或以上）
# 配置安全組（開放必要端口）

# 連接到實例
ssh -i your-key.pem ubuntu@your-ec2-ip

# 安裝 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# 部署應用
git clone https://github.com/your-username/finrl-deepseek-extension.git
cd finrl-deepseek-extension
cp .env.template .env
# 編輯 .env 文件

docker-compose up -d
```

### Google Cloud Platform 部署

```bash
# 創建 Compute Engine 實例
gcloud compute instances create finrl-deepseek \
    --machine-type=e2-medium \
    --image-family=ubuntu-2004-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=100GB

# 連接到實例
gcloud compute ssh finrl-deepseek

# 安裝和配置（同上述步驟）
```

### Azure Container Instances 部署

```bash
# 創建資源群組
az group create --name finrl-rg --location eastus

# 部署容器
az container create \
    --resource-group finrl-rg \
    --name finrl-deepseek \
    --image your-registry/finrl-deepseek:latest \
    --cpu 2 --memory 4 \
    --environment-variables OPENAI_API_KEY=your-key
```

## 📊 監控和維護

### 1. 日誌監控

```bash
# 查看應用日誌
tail -f logs/finrl_extension.log

# 查看系統日誌
sudo journalctl -u finrl-daily-crawl -f

# 日誌輪轉配置
sudo nano /etc/logrotate.d/finrl-deepseek
```

### 2. 健康檢查

```bash
# 創建健康檢查腳本
#!/bin/bash
# health_check.sh

HEALTH_ENDPOINT="http://localhost:8000/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_ENDPOINT)

if [ $RESPONSE -eq 200 ]; then
    echo "Service is healthy"
    exit 0
else
    echo "Service is unhealthy (HTTP $RESPONSE)"
    exit 1
fi
```

### 3. 自動備份

```bash
# 創建備份腳本
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/finrl-$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# 備份數據
cp -r /opt/finrl-deepseek/data $BACKUP_DIR/
cp -r /opt/finrl-deepseek/logs $BACKUP_DIR/
cp -r /opt/finrl-deepseek/reports $BACKUP_DIR/

# 壓縮備份
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

# 清理舊備份（保留30天）
find /backups -name "finrl-*.tar.gz" -mtime +30 -delete
```

### 4. 性能監控

使用 Prometheus + Grafana：

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'finrl-deepseek'
    static_configs:
      - targets: ['localhost:8000']
```

## 🔧 故障排除

### 常見問題和解決方案

#### 1. OpenAI API 錯誤

```bash
# 檢查 API 密鑰
python -c "import openai; print(openai.api_key)"

# 測試 API 連接
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models
```

#### 2. 記憶體不足

```bash
# 檢查記憶體使用
free -h
top

# 調整配置
# 在 config.json 中減少 batch_size 和 max_workers
```

#### 3. 網路連接問題

```bash
# 檢查網路連接
ping google.com
curl -I https://api.openai.com

# 檢查代理設置
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

#### 4. 權限問題

```bash
# 檢查文件權限
ls -la data/
ls -la logs/

# 修復權限
sudo chown -R finrl:finrl /opt/finrl-deepseek
sudo chmod -R 755 /opt/finrl-deepseek
```

#### 5. 服務無法啟動

```bash
# 檢查服務狀態
sudo systemctl status finrl-daily-crawl

# 查看詳細錯誤
sudo journalctl -u finrl-daily-crawl -n 50

# 重新載入配置
sudo systemctl daemon-reload
sudo systemctl restart finrl-daily-crawl
```

## 📞 技術支援

如需技術支援，請：

1. 檢查 [故障排除文檔](TROUBLESHOOTING.md)
2. 查看 [FAQ](FAQ.md)
3. 提交 [GitHub Issue](https://github.com/your-username/finrl-deepseek-extension/issues)
4. 聯絡技術團隊：tech-support@yourcompany.com

## 🔄 更新和維護

### 版本更新

```bash
# 備份當前版本
cp -r /opt/finrl-deepseek /opt/finrl-deepseek.backup

# 拉取最新代碼
cd /opt/finrl-deepseek
git pull origin main

# 更新依賴
source venv/bin/activate
pip install -r requirements.txt

# 重啟服務
sudo systemctl restart finrl-daily-crawl
```

### 定期維護

- **每週**：檢查日誌和錯誤報告
- **每月**：備份重要數據
- **每季**：檢查和更新依賴包
- **每年**：檢查和更新系統配置

---

**注意**：生產環境部署前請務必進行充分測試，並確保有適當的備份和恢復策略。
