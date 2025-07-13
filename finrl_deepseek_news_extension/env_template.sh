# FinRL-DeepSeek 新聞爬取專案環境變數
# 複製此文件為 .env 並填入實際值

# OpenAI API 配置
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_ORG_ID=org-your-organization-id  # 可選

# 資料庫配置
POSTGRES_PASSWORD=your-secure-password-here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=finrl_news
POSTGRES_USER=finrl_user

# Redis 配置
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your-redis-password  # 可選

# 監控配置
GRAFANA_PASSWORD=admin-password-here
PROMETHEUS_RETENTION=30d

# 專案配置
PROJECT_ENV=production  # development, staging, production
LOG_LEVEL=INFO
DEBUG_MODE=false

# API 速率限制
OPENAI_RPM=100  # 每分鐘請求數
OPENAI_TPM=30000  # 每分鐘token數
DAILY_COST_LIMIT=50.0  # 每日成本限制(美元)

# 爬取配置
CRAWL_DELAY_MIN=2  # 最小延遲(秒)
CRAWL_DELAY_MAX=5  # 最大延遲(秒)
MAX_WORKERS=3  # 最大並行數
BATCH_SIZE=50  # 批次大小

# 代理配置 (可選)
HTTP_PROXY=
HTTPS_PROXY=
PROXY_USER=
PROXY_PASS=

# 通知配置
SLACK_WEBHOOK_URL=https://hooks.slack.com/your-webhook-url
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_TO=notifications@yourcompany.com

# 時區設定
TZ=Asia/Taipei

# 安全設定
SECRET_KEY=your-secret-key-for-encryption
API_KEY_ENCRYPTION_KEY=your-encryption-key-here

# 效能調校
MEMORY_LIMIT_GB=8
DISK_CACHE_SIZE_GB=10
PARALLEL_DOWNLOAD_LIMIT=10

# 資料保留政策
RAW_DATA_RETENTION_DAYS=30
PROCESSED_DATA_RETENTION_DAYS=90
LOG_RETENTION_DAYS=30

# 品質控制
MIN_ARTICLE_LENGTH=100
MAX_ARTICLE_LENGTH=10000
DUPLICATE_THRESHOLD=0.8
RELEVANCE_THRESHOLD=0.6

# 備份配置
BACKUP_ENABLED=true
BACKUP_SCHEDULE="0 2 * * *"  # 每天凌晨2點
BACKUP_RETENTION_DAYS=30
BACKUP_LOCATION=/backups

# 開發模式配置
DEV_SAMPLE_SIZE=100  # 開發模式時的樣本大小
DEV_SKIP_LLM=false  # 開發時跳過LLM評分
DEV_USE_MOCK_DATA=false  # 使用模擬數據

# 監控告警閾值
CPU_ALERT_THRESHOLD=80  # CPU使用率告警閾值(%)
MEMORY_ALERT_THRESHOLD=85  # 記憶體使用率告警閾值(%)
DISK_ALERT_THRESHOLD=90  # 磁碟使用率告警閾值(%)
ERROR_RATE_THRESHOLD=5  # 錯誤率告警閾值(%)

# 自動重試配置
MAX_RETRY_ATTEMPTS=3
RETRY_DELAY_SECONDS=60
EXPONENTIAL_BACKOFF=true

# 健康檢查配置
HEALTH_CHECK_INTERVAL=300  # 健康檢查間隔(秒)
HEALTH_CHECK_TIMEOUT=30  # 健康檢查超時(秒)