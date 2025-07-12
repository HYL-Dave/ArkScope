# ⚡ 性能優化和最佳實踐指南

本指南提供 FinRL-DeepSeek 新聞爬取系統的性能優化策略和最佳實踐建議。

## 📋 目錄

- [系統架構優化](#系統架構優化)
- [爬取性能優化](#爬取性能優化)
- [LLM 處理優化](#llm-處理優化)
- [數據存儲優化](#數據存儲優化)
- [記憶體管理](#記憶體管理)
- [網路優化](#網路優化)
- [監控和調試](#監控和調試)
- [成本優化策略](#成本優化策略)

## 🏗️ 系統架構優化

### 1. 微服務架構設計

```python
# 建議的服務拆分
services = {
    'crawler_service': '負責新聞爬取',
    'processor_service': '負責數據處理和LLM評分', 
    'storage_service': '負責數據存儲和管理',
    'scheduler_service': '負責任務調度',
    'monitor_service': '負責監控和告警'
}
```

### 2. 異步處理架構

```python
# 使用 asyncio 提升並發性能
import asyncio
import aiohttp
from asyncio import Semaphore

class AsyncCrawler:
    def __init__(self, max_concurrent=10):
        self.semaphore = Semaphore(max_concurrent)
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_news(self, url):
        async with self.semaphore:
            async with self.session.get(url) as response:
                return await response.text()
    
    async def batch_fetch(self, urls):
        tasks = [self.fetch_news(url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

### 3. 消息隊列集成

```python
# 使用 Celery + Redis 進行任務分發
from celery import Celery

app = Celery('finrl_tasks', broker='redis://localhost:6379/0')

@app.task(bind=True, max_retries=3)
def process_article_batch(self, articles):
    """批量處理文章的 Celery 任務"""
    try:
        # 處理邏輯
        return process_articles(articles)
    except Exception as exc:
        self.retry(countdown=60, exc=exc)
```

## 🔄 爬取性能優化

### 1. 智能速率控制

```python
class AdaptiveRateLimiter:
    def __init__(self, initial_delay=1.0, max_delay=30.0):
        self.current_delay = initial_delay
        self.max_delay = max_delay
        self.success_count = 0
        self.error_count = 0
    
    async def wait(self):
        await asyncio.sleep(self.current_delay)
    
    def on_success(self):
        self.success_count += 1
        self.error_count = 0
        
        # 連續成功時逐漸減少延遲
        if self.success_count > 5:
            self.current_delay = max(0.5, self.current_delay * 0.9)
    
    def on_error(self, error_type):
        self.error_count += 1
        self.success_count = 0
        
        # 根據錯誤類型調整延遲
        if error_type == 'rate_limit':
            self.current_delay = min(self.max_delay, self.current_delay * 2)
        elif error_type == 'server_error':
            self.current_delay = min(self.max_delay, self.current_delay * 1.5)
```

### 2. 連接池優化

```python
# 優化 HTTP 連接池配置
import aiohttp

connector = aiohttp.TCPConnector(
    limit=100,              # 總連接數限制
    limit_per_host=10,      # 每個主機的連接數限制
    ttl_dns_cache=300,      # DNS 快取時間
    use_dns_cache=True,     # 啟用 DNS 快取
    keepalive_timeout=60,   # Keep-alive 超時
    enable_cleanup_closed=True
)

session = aiohttp.ClientSession(
    connector=connector,
    timeout=aiohttp.ClientTimeout(total=30),
    headers={'User-Agent': 'FinRL-DeepSeek/1.0'}
)
```

### 3. 快取策略

```python
import redis
import pickle
from functools import wraps

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_result(expiration=3600):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成快取鍵
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # 嘗試從快取獲取
            cached_result = redis_client.get(cache_key)
            if cached_result:
                return pickle.loads(cached_result)
            
            # 執行函數並快取結果
            result = func(*args, **kwargs)
            redis_client.setex(
                cache_key, 
                expiration, 
                pickle.dumps(result)
            )
            return result
        return wrapper
    return decorator

@cache_result(expiration=1800)  # 快取30分鐘
def get_stock_news(ticker, date):
    # 爬取邏輯
    pass
```

## 🤖 LLM 處理優化

### 1. 批量處理優化

```python
class BatchLLMProcessor:
    def __init__(self, batch_size=20, max_tokens_per_batch=150000):
        self.batch_size = batch_size
        self.max_tokens_per_batch = max_tokens_per_batch
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def create_smart_batches(self, articles):
        """根據 token 數量智能分批"""
        batches = []
        current_batch = []
        current_tokens = 0
        
        for article in articles:
            article_tokens = len(self.tokenizer.encode(article['content']))
            
            if (current_tokens + article_tokens > self.max_tokens_per_batch or 
                len(current_batch) >= self.batch_size):
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0
            
            current_batch.append(article)
            current_tokens += article_tokens
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    async def process_batch_async(self, batch):
        """異步批量處理"""
        tasks = []
        for article in batch:
            task = asyncio.create_task(
                self.process_single_article(article)
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks, return_exceptions=True)
```

### 2. Prompt 優化

```python
class OptimizedPromptManager:
    def __init__(self):
        # 預編譯的 prompt 模板
        self.sentiment_template = self._compile_sentiment_prompt()
        self.risk_template = self._compile_risk_prompt()
    
    def _compile_sentiment_prompt(self):
        """優化的情緒分析 prompt"""
        return """Rate sentiment (1-5): {title}
        
        Content: {content}
        
        1=negative, 2=somewhat negative, 3=neutral, 4=somewhat positive, 5=positive
        
        Number only:"""
    
    def create_batch_prompt(self, articles, prompt_type='sentiment'):
        """創建批量處理的 prompt"""
        template = getattr(self, f"{prompt_type}_template")
        
        batch_prompt = f"Rate {prompt_type} for each article (1-5):\n\n"
        
        for i, article in enumerate(articles, 1):
            batch_prompt += f"Article {i}:\n"
            batch_prompt += f"Title: {article['title'][:100]}...\n"
            batch_prompt += f"Content: {article['content'][:500]}...\n\n"
        
        batch_prompt += f"Respond with {len(articles)} numbers separated by commas:"
        
        return batch_prompt
```

### 3. 模型選擇策略

```python
class ModelSelector:
    def __init__(self):
        self.model_configs = {
            'gpt-4.1-mini': {
                'cost_per_token': 0.0004,
                'quality_score': 8.5,
                'speed_score': 9.0
            },
            'gpt-4.1': {
                'cost_per_token': 0.002,
                'quality_score': 9.5,
                'speed_score': 7.0
            }
        }
    
    def select_optimal_model(self, article_count, budget_limit, quality_requirement):
        """根據需求選擇最佳模型"""
        best_model = None
        best_score = 0
        
        for model, config in self.model_configs.items():
            estimated_cost = article_count * 100 * config['cost_per_token']  # 估算
            
            if estimated_cost <= budget_limit:
                # 計算綜合分數
                score = (config['quality_score'] * quality_requirement + 
                        config['speed_score'] * (1 - quality_requirement))
                
                if score > best_score:
                    best_score = score
                    best_model = model
        
        return best_model
```

## 💾 數據存儲優化

### 1. 資料庫分片策略

```python
class DatabaseSharding:
    def __init__(self):
        self.shards = {
            'shard_2023': 'postgresql://user:pass@db1:5432/finrl_2023',
            'shard_2024': 'postgresql://user:pass@db2:5432/finrl_2024', 
            'shard_2025': 'postgresql://user:pass@db3:5432/finrl_2025'
        }
    
    def get_shard_for_date(self, date_str):
        """根據日期選擇分片"""
        year = date_str[:4]
        return self.shards.get(f'shard_{year}', self.shards['shard_2024'])
    
    def insert_batch_optimized(self, articles):
        """優化的批量插入"""
        # 按分片分組
        shard_groups = {}
        for article in articles:
            shard = self.get_shard_for_date(article['date'])
            if shard not in shard_groups:
                shard_groups[shard] = []
            shard_groups[shard].append(article)
        
        # 並行插入到各分片
        tasks = []
        for shard, group in shard_groups.items():
            task = asyncio.create_task(
                self.bulk_insert_to_shard(shard, group)
            )
            tasks.append(task)
        
        return asyncio.gather(*tasks)
```

### 2. 索引優化

```sql
-- 針對查詢模式的索引優化
CREATE INDEX CONCURRENTLY idx_news_date_symbol 
ON news_articles (date, stock_symbol);

CREATE INDEX CONCURRENTLY idx_news_sentiment_date 
ON news_articles (sentiment_u, date) 
WHERE sentiment_u IS NOT NULL;

-- 分區表設計
CREATE TABLE news_articles_2024 PARTITION OF news_articles 
FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
```

### 3. 檔案格式優化

```python
import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow import compute as pc

class OptimizedFileStorage:
    def save_partitioned_parquet(self, df, base_path):
        """分區儲存 Parquet 文件"""
        # 按年月分區
        df['year_month'] = df['date'].str[:7]
        
        table = pa.Table.from_pandas(df)
        
        # 使用 Snappy 壓縮和優化參數
        pq.write_to_dataset(
            table,
            root_path=base_path,
            partition_cols=['year_month'],
            compression='snappy',
            use_dictionary=True,
            row_group_size=50000,
            data_page_size=1024*1024,  # 1MB
            flavor='spark'
        )
    
    def read_optimized(self, path, date_range=None, columns=None):
        """優化的讀取操作"""
        dataset = pq.ParquetDataset(path)
        
        # 構建過濾條件
        filters = []
        if date_range:
            filters.append(('date', '>=', date_range[0]))
            filters.append(('date', '<=', date_range[1]))
        
        return dataset.read(
            columns=columns,
            filters=filters,
            use_threads=True
        ).to_pandas()
```

## 🧠 記憶體管理

### 1. 分塊處理策略

```python
class ChunkedProcessor:
    def __init__(self, chunk_size=1000, memory_limit_gb=4):
        self.chunk_size = chunk_size
        self.memory_limit_bytes = memory_limit_gb * 1024**3
    
    def process_large_dataset(self, data_path):
        """分塊處理大型數據集"""
        chunk_iterator = pd.read_csv(
            data_path,
            chunksize=self.chunk_size,
            iterator=True
        )
        
        results = []
        for chunk_num, chunk in enumerate(chunk_iterator):
            # 檢查記憶體使用
            if self._check_memory_usage() > 0.8:
                self._trigger_garbage_collection()
            
            # 處理當前塊
            processed_chunk = self.process_chunk(chunk)
            results.append(processed_chunk)
            
            # 定期儲存中間結果
            if chunk_num % 10 == 0:
                self._save_intermediate_results(results, chunk_num)
        
        return pd.concat(results, ignore_index=True)
    
    def _check_memory_usage(self):
        """檢查記憶體使用率"""
        import psutil
        return psutil.virtual_memory().percent / 100
    
    def _trigger_garbage_collection(self):
        """觸發垃圾回收"""
        import gc
        gc.collect()
```

### 2. 資料流處理

```python
from typing import Iterator, Generator

class StreamProcessor:
    def __init__(self):
        self.buffer_size = 1000
    
    def stream_process_articles(self, articles_iter: Iterator) -> Generator:
        """流式處理文章，減少記憶體佔用"""
        buffer = []
        
        for article in articles_iter:
            buffer.append(article)
            
            if len(buffer) >= self.buffer_size:
                # 處理緩衝區
                processed = self.process_buffer(buffer)
                for result in processed:
                    yield result
                
                # 清空緩衝區
                buffer.clear()
        
        # 處理剩餘的文章
        if buffer:
            processed = self.process_buffer(buffer)
            for result in processed:
                yield result
```

## 🌐 網路優化

### 1. CDN 和邊緣快取

```python
class CDNOptimizedCrawler:
    def __init__(self):
        self.cdn_endpoints = {
            'us-east': 'https://us-east.api.example.com',
            'eu-west': 'https://eu-west.api.example.com',
            'asia-pacific': 'https://ap.api.example.com'
        }
        
    def get_optimal_endpoint(self, target_url):
        """選擇最佳的 CDN 端點"""
        # 基於地理位置或延遲選擇
        import requests
        import time
        
        best_endpoint = None
        min_latency = float('inf')
        
        for region, endpoint in self.cdn_endpoints.items():
            try:
                start_time = time.time()
                response = requests.head(endpoint, timeout=5)
                latency = time.time() - start_time
                
                if response.status_code == 200 and latency < min_latency:
                    min_latency = latency
                    best_endpoint = endpoint
            except:
                continue
        
        return best_endpoint or list(self.cdn_endpoints.values())[0]
```

### 2. 連接重用和持久化

```python
import aiohttp
import asyncio
from aiohttp import TCPConnector

class PersistentConnectionManager:
    def __init__(self):
        self.connector = TCPConnector(
            limit=100,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=60,
            enable_cleanup_closed=True
        )
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            connector=self.connector,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        await self.connector.close()
```

## 📊 監控和調試

### 1. 性能指標收集

```python
import time
import psutil
from functools import wraps

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
    
    def monitor_function(self, func_name=None):
        def decorator(func):
            name = func_name or func.__name__
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                start_memory = psutil.virtual_memory().used
                
                try:
                    result = func(*args, **kwargs)
                    success = True
                except Exception as e:
                    success = False
                    raise
                finally:
                    end_time = time.time()
                    end_memory = psutil.virtual_memory().used
                    
                    # 記錄指標
                    self.metrics[name] = {
                        'execution_time': end_time - start_time,
                        'memory_delta': end_memory - start_memory,
                        'success': success,
                        'timestamp': time.time()
                    }
                
                return result
            return wrapper
        return decorator
    
    def get_performance_report(self):
        """生成性能報告"""
        return {
            'total_functions': len(self.metrics),
            'avg_execution_time': sum(m['execution_time'] for m in self.metrics.values()) / len(self.metrics),
            'success_rate': sum(1 for m in self.metrics.values() if m['success']) / len(self.metrics),
            'details': self.metrics
        }
```

### 2. 瓶頸分析工具

```python
import cProfile
import pstats
from memory_profiler import profile

class BottleneckAnalyzer:
    def __init__(self):
        self.profiler = cProfile.Profile()
    
    def profile_function(self, func, *args, **kwargs):
        """分析函數性能瓶頸"""
        self.profiler.enable()
        try:
            result = func(*args, **kwargs)
        finally:
            self.profiler.disable()
        
        # 生成報告
        stats = pstats.Stats(self.profiler)
        stats.sort_stats('cumulative')
        stats.print_stats(20)  # 顯示前20個最耗時的函數
        
        return result
    
    @profile  # memory_profiler decorator
    def analyze_memory_usage(self, func, *args, **kwargs):
        """分析記憶體使用"""
        return func(*args, **kwargs)
```

## 💰 成本優化策略

### 1. 智能模型選擇

```python
class CostOptimizer:
    def __init__(self):
        self.cost_thresholds = {
            'daily': 50.0,
            'weekly': 300.0,
            'monthly': 1000.0
        }
        self.model_efficiency = {
            'gpt-4o-mini': {'cost': 0.00015, 'quality': 0.85},
            'gpt-4o': {'cost': 0.005, 'quality': 0.95}
        }
    
    def select_cost_effective_model(self, article_count, quality_requirement):
        """選擇成本效益最佳的模型"""
        best_model = None
        best_value = 0
        
        for model, metrics in self.model_efficiency.items():
            if metrics['quality'] >= quality_requirement:
                estimated_cost = article_count * 100 * metrics['cost']
                value_score = metrics['quality'] / metrics['cost']
                
                if estimated_cost <= self.cost_thresholds['daily'] and value_score > best_value:
                    best_value = value_score
                    best_model = model
        
        return best_model or 'gpt-4o-mini'  # 默認選擇最便宜的
```

### 2. 動態批次大小調整

```python
class DynamicBatchManager:
    def __init__(self):
        self.cost_tracker = 0
        self.daily_limit = 50.0
        self.initial_batch_size = 50
        self.current_batch_size = self.initial_batch_size
    
    def adjust_batch_size(self, current_cost, remaining_articles):
        """根據當前成本動態調整批次大小"""
        remaining_budget = self.daily_limit - current_cost
        
        if remaining_budget <= 0:
            return 0  # 停止處理
        
        # 估算每篇文章的平均成本
        avg_cost_per_article = current_cost / max(1, (remaining_articles + self.current_batch_size))
        
        # 計算可處理的最大數量
        max_affordable = int(remaining_budget / avg_cost_per_article)
        
        # 調整批次大小
        self.current_batch_size = min(max_affordable, self.initial_batch_size)
        
        return self.current_batch_size
```

## 🎯 最佳實踐總結

### 關鍵建議

1. **分層快取策略**: 實施 Redis + 本地快取的多層快取
2. **異步處理**: 使用 asyncio 提升 I/O 密集型操作的性能
3. **批量處理**: 合理設置批次大小，平衡性能和資源使用
4. **監控驅動**: 建立完整的監控體系，基於數據進行優化
5. **成本控制**: 實施動態成本控制機制，避免預算超支

### 性能基準

- **爬取速度**: 每分鐘 50-100 篇文章
- **處理延遲**: LLM 評分 < 5 秒/文章
- **記憶體使用**: < 4GB 持續使用
- **成本控制**: < $50/日 LLM 處理成本
- **錯誤率**: < 2% 處理失敗率

### 定期檢查清單

- [ ] 監控 API 速率限制使用情況
- [ ] 檢查記憶體洩漏和性能下降
- [ ] 優化資料庫查詢和索引
- [ ] 更新和調整快取策略
- [ ] 分析成本趨勢和優化機會

---

遵循這些優化策略和最佳實踐，可以顯著提升系統性能，降低運營成本，確保系統的穩定性和可擴展性。
