# OpenAI API 配置
OPENAI_API_KEY=your-openai-api-key-here

# 模型配置
OPENAI_MODEL=o3  # 可選: o3, o4-mini, gpt-4.1, gpt-4.1-mini
USE_FLEX_PROCESSING=true  # 使用 Flex Processing (僅對 reasoning 模型有效)

# Reasoning 模型參數
REASONING_EFFORT=medium  # 可選: low, medium, high (僅對 o3/o1 有效)
MAX_COMPLETION_TOKENS=2000  # 最大輸出 token 數

# 處理參數
LLM_SAMPLE_SIZE=200  # LLM 質量檢查的樣本大小
BATCH_SIZE=10  # 每批處理的新聞數量

# 數據範圍
START_DATE=2013-01-01
END_DATE=2023-12-31

# 文件路徑
TICKERS_FILE=tickers_89.json
RAW_PARQUET=news_89_2013_2023_raw.parquet
CLEANED_PARQUET=news_89_2013_2023_cleaned.parquet
QUALITY_REPORT=data_quality_report.json

# 超時設置 (秒)
API_TIMEOUT=1800  # 30分鐘，適合 Flex Processing

# 日誌級別
LOG_LEVEL=INFO  # 可選: DEBUG, INFO, WARNING, ERROR

# 代理設置（如需要）
# HTTP_PROXY=http://your-proxy:port
# HTTPS_PROXY=https://your-proxy:port