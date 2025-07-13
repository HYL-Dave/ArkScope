#!/usr/bin/env python3
"""
FinRL 新聞數據完整處理管道 v2.2
增強功能：錯誤恢復、資料驗證、多語言支援、多格式導出
修正：確保只處理 89 檔股票（同時有新聞和價格數據）
更新：修復 Excel 時區問題和索引不匹配問題，移除不需要的導出格式
"""

import json
import pathlib
import re
import requests
import textwrap
import pandas as pd
import numpy as np
from datetime import datetime
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from datasets import load_dataset
from tqdm import tqdm
import openai
from typing import List, Dict, Tuple, Optional, Union
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import httpx
import pickle
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('finrl_news_pipeline.log'),
        logging.StreamHandler()
    ]
)


# ===== 資料驗證層 =====
@dataclass
class NewsRecord:
    """新聞記錄資料結構 - 使用 FNSPID 原始欄位名稱"""
    Date: str
    Stock_symbol: str
    Article_title: str  # 使用原始名稱
    Article: str  # 使用原始名稱
    Sentiment: float
    # 額外欄位（可選）
    Url: str = ""
    Publisher: str = ""
    Author: str = ""
    Lsa_summary: str = ""

    # 修改 NewsRecord 的 validate 方法
    def validate(self) -> List[str]:
        """驗證資料完整性（放寬版本）"""
        errors = []

        # 只檢查必要欄位
        # 日期格式驗證
        if not self.Date:
            errors.append("Date is missing")
        else:
            try:
                pd.to_datetime(self.Date)
            except:
                errors.append(f"Invalid date format: {self.Date}")

        # 股票代碼驗證
        if not self.Stock_symbol:
            errors.append("Stock symbol is missing")
        # 移除大寫檢查，因為有些股票代碼可能有特殊情況

        # 標題驗證（放寬長度要求）
        if not self.Article_title:
            errors.append("Title is missing")

        # 文章內容驗證（放寬長度要求）
        if not self.Article:
            errors.append("Article content is missing")

        # 情感分數驗證（如果有值才檢查範圍）
        if self.Sentiment is not None and not -1 <= self.Sentiment <= 1:
            errors.append(f"Sentiment out of range: {self.Sentiment}")

        return errors


class Language(Enum):
    """支援的語言"""
    EN = "en"
    ZH = "zh"
    ES = "es"
    JP = "jp"


class ExportFormat(Enum):
    """支援的導出格式"""
    PARQUET = "parquet"
    CSV = "csv"
    JSON = "json"


# ===== 檢查點管理器 =====
class CheckpointManager:
    """管理處理進度的檢查點"""

    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = pathlib.Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)

    def save_checkpoint(self, stage: str, data: Union[pd.DataFrame, Dict],
                        metadata: Dict = None):
        """保存檢查點"""
        checkpoint_file = self.checkpoint_dir / f"{stage}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"

        checkpoint_data = {
            'stage': stage,
            'timestamp': datetime.now(),
            'data': data,
            'metadata': metadata or {}
        }

        with open(checkpoint_file, 'wb') as f:
            pickle.dump(checkpoint_data, f)

        # 保存最新檢查點的引用
        latest_file = self.checkpoint_dir / f"{stage}_latest.txt"
        latest_file.write_text(str(checkpoint_file))

        return checkpoint_file

    def load_checkpoint(self, stage: str) -> Optional[Dict]:
        """載入最新的檢查點"""
        latest_file = self.checkpoint_dir / f"{stage}_latest.txt"

        if not latest_file.exists():
            return None

        checkpoint_file = pathlib.Path(latest_file.read_text().strip())

        if not checkpoint_file.exists():
            return None

        with open(checkpoint_file, 'rb') as f:
            return pickle.load(f)

    def get_resume_point(self) -> Optional[str]:
        """獲取可以恢復的最新階段"""
        stages = ['download', 'basic_clean', 'llm_check', 'advanced_clean', 'final']

        for stage in reversed(stages):
            if self.load_checkpoint(stage):
                return stage

        return None


# ===== 多語言提示詞管理器 =====
class PromptManager:
    """管理多語言提示詞"""

    PROMPTS = {
        Language.EN: {
            'quality_check': """
            Perform a comprehensive analysis of the following financial news related to stock {symbol}.

            Title: {title}
            Content: {text_snippet}
            Date: {date}
            Original Sentiment Score: {original_sentiment}

            Please provide analysis in JSON format with all required fields.
            """,
            'system': "You are a professional financial data analyst."
        },
        Language.ZH: {
            'quality_check': """
            請對以下與股票 {symbol} 相關的財經新聞進行綜合分析。

            標題：{title}
            內容：{text_snippet}
            日期：{date}
            原始情感分數：{original_sentiment}

            請以 JSON 格式提供分析結果，包含所有必需字段。
            """,
            'system': "您是專業的金融數據分析師。"
        },
        Language.ES: {
            'quality_check': """
            Realice un análisis integral de las siguientes noticias financieras relacionadas con la acción {symbol}.

            Título: {title}
            Contenido: {text_snippet}
            Fecha: {date}
            Puntuación de sentimiento original: {original_sentiment}

            Proporcione el análisis en formato JSON con todos los campos requeridos.
            """,
            'system': "Eres un analista profesional de datos financieros."
        },
        Language.JP: {
            'quality_check': """
            株式 {symbol} に関連する以下の金融ニュースを総合的に分析してください。

            タイトル：{title}
            内容：{text_snippet}
            日付：{date}
            元の感情スコア：{original_sentiment}

            必要なすべてのフィールドを含むJSON形式で分析を提供してください。
            """,
            'system': "あなたはプロの金融データアナリストです。"
        }
    }

    @classmethod
    def get_prompt(cls, prompt_type: str, language: Language, **kwargs) -> str:
        """獲取指定語言的提示詞"""
        return cls.PROMPTS[language][prompt_type].format(**kwargs)


# ===== 主處理器類 =====
class FinRLNewsProcessor:
    def __init__(self, openai_api_key: str = None, language: Language = Language.EN):
        """初始化處理器"""
        self.logger = logging.getLogger(__name__)
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.language = language

        if self.openai_api_key:
            self.logger.info(f"OpenAI API 已配置 (語言: {language.value})")
        else:
            self.logger.warning("未配置 OpenAI API Key，部分功能將無法使用")

        # 設定參數
        self.START_DATE = "2013-01-01"
        self.END_DATE = "2023-12-31"
        self.TICKERS_FILE = "tickers_89.json"
        self.RAW_PARQUET = "fnspid_89_2013_2023_raw.parquet"
        self.CLEANED_PARQUET = "fnspid_89_2013_2023_cleaned.parquet"
        self.QUALITY_REPORT = "data_quality_report.json"

        # 模型相關參數
        self.model = "o3"
        self.use_flex = True
        self.sample_size = 100
        self.batch_size = 10
        self.reasoning_effort = "medium"

        # 初始化檢查點管理器
        self.checkpoint_manager = CheckpointManager()

        # 錯誤恢復設置
        self.max_retries = 3
        self.retry_delay = 5  # 秒

    # 修改 validate_dataframe 方法
    def validate_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """驗證整個 DataFrame 的資料品質（放寬版本）"""
        self.logger.info("開始資料驗證...")

        valid_rows = []
        invalid_rows = []

        for idx, row in df.iterrows():
            try:
                # 只檢查必要欄位是否存在
                required_fields = ['Date', 'Stock_symbol', 'Article_title', 'Article']
                missing_fields = [field for field in required_fields if
                                  pd.isna(row.get(field, None)) or row.get(field, '') == '']

                if missing_fields:
                    invalid_rows.append({
                        'index': idx,
                        'errors': [f"Missing required fields: {missing_fields}"],
                        'data': row.to_dict()
                    })
                else:
                    # 創建記錄，可選欄位使用 get 方法
                    record = NewsRecord(
                        Date=str(row['Date']),
                        Stock_symbol=row['Stock_symbol'],
                        Article_title=row['Article_title'],
                        Article=row['Article'],
                        Sentiment=float(row.get('Sentiment', 0.0)) if pd.notna(row.get('Sentiment')) else 0.0,
                        # 可選欄位
                        Url=str(row.get('Url', '')) if pd.notna(row.get('Url')) else '',
                        Publisher=str(row.get('Publisher', '')) if pd.notna(row.get('Publisher')) else '',
                        Author=str(row.get('Author', '')) if pd.notna(row.get('Author')) else '',
                        Lsa_summary=str(row.get('Lsa_summary', '')) if pd.notna(row.get('Lsa_summary')) else ''
                    )

                    # 執行基本驗證
                    errors = record.validate()

                    if errors:
                        invalid_rows.append({
                            'index': idx,
                            'errors': errors,
                            'data': row.to_dict()
                        })
                    else:
                        valid_rows.append(row)

            except Exception as e:
                invalid_rows.append({
                    'index': idx,
                    'errors': [f"Validation exception: {str(e)}"],
                    'data': row.to_dict()
                })

        valid_df = pd.DataFrame(valid_rows)

        # 保存無效資料報告
        if invalid_rows:
            with open('invalid_records_report.json', 'w', encoding='utf-8') as f:
                json.dump(invalid_rows, f, indent=2, ensure_ascii=False, default=str)
            self.logger.warning(f"發現 {len(invalid_rows)} 筆無效資料，詳見 invalid_records_report.json")

        self.logger.info(f"資料驗證完成：有效 {len(valid_df)} 筆，無效 {len(invalid_rows)} 筆")

        return valid_df, pd.DataFrame([r['data'] for r in invalid_rows])

    def retry_with_exponential_backoff(self, func, *args, **kwargs):
        """指數退避重試機制"""
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e

                wait_time = self.retry_delay * (2 ** attempt)
                self.logger.warning(f"錯誤: {e}. 重試 {attempt + 1}/{self.max_retries}，等待 {wait_time} 秒...")
                time.sleep(wait_time)

    def step1_fetch_tickers(self) -> List[str]:
        """步驟1: 獲取股票代碼列表（從已準備好的 89 檔列表）"""
        self.logger.info("步驟1: 讀取股票代碼列表")

        # 檢查是否有檢查點
        checkpoint = self.checkpoint_manager.load_checkpoint('tickers')
        if checkpoint:
            self.logger.info("從檢查點恢復股票列表")
            return checkpoint['data']

        try:
            # 直接讀取已準備好的 tickers_89.json
            if not pathlib.Path(self.TICKERS_FILE).exists():
                raise FileNotFoundError(
                    f"找不到 {self.TICKERS_FILE} 文件。\n"
                    f"請確保該文件存在於當前目錄中。\n"
                    f"該文件應包含 89 個經過驗證的 NASDAQ 股票代碼。"
                )

            with open(self.TICKERS_FILE, 'r') as f:
                tickers = json.load(f)

            # 驗證格式
            if not isinstance(tickers, list) or not all(isinstance(t, str) for t in tickers):
                raise ValueError(f"{self.TICKERS_FILE} 格式不正確，應為字符串列表")

            # 驗證數量
            if len(tickers) != 89:
                self.logger.warning(f"預期 89 檔股票，但找到 {len(tickers)} 檔")

            # 保存檢查點
            self.checkpoint_manager.save_checkpoint('tickers', tickers)

            self.logger.info(f"✅ 成功讀取 {len(tickers)} 個股票代碼")
            self.logger.info(f"股票列表: {', '.join(tickers[:10])}... (顯示前10個)")

            return tickers

        except Exception as e:
            self.logger.error(f"讀取股票代碼失敗: {e}")
            raise

    def step2_download_news(self, tickers: List[str]) -> None:
        """步驟2: 下載新聞數據（支援斷點續傳）"""
        self.logger.info("步驟2: 開始下載新聞數據")

        # 檢查是否有下載檢查點
        checkpoint = self.checkpoint_manager.load_checkpoint('download')
        start_index = 0
        existing_records = []

        if checkpoint:
            start_index = checkpoint['metadata'].get('last_index', 0)
            existing_records = checkpoint['data']
            self.logger.info(f"從檢查點恢復，已處理 {start_index} 條記錄")

        TICKERS_SET = set(tickers)

        # 載入數據集
        ds = load_dataset("Zihan1004/FNSPID", split="train", streaming=True)

        # 建立 Parquet Schema - 使用 FNSPID 原始欄位名稱
        schema = pa.schema([
            ('Date', pa.string()),
            ('Stock_symbol', pa.string()),
            ('Article_title', pa.string()),
            ('Article', pa.string()),
            ('Sentiment', pa.float64()),
            ('Url', pa.string()),
            ('Publisher', pa.string()),
            ('Author', pa.string()),
            ('Lsa_summary', pa.string())
        ])

        # 如果是恢復下載，先寫入已有記錄
        if existing_records:
            temp_df = pd.DataFrame(existing_records)
            temp_df.to_parquet(self.RAW_PARQUET + '.tmp')

        count = start_index
        batch_records = []
        batch_size = 1000  # 每批保存檢查點
        missing_fields_count = 0

        try:
            for idx, row in enumerate(tqdm(ds, desc="下載新聞", initial=start_index)):
                if idx < start_index:
                    continue

                # 檢查必要欄位是否存在
                if 'Stock_symbol' not in row or 'Date' not in row:
                    missing_fields_count += 1
                    if missing_fields_count <= 10:  # 只記錄前10個錯誤
                        self.logger.debug(f"記錄 {idx} 缺少必要欄位: {list(row.keys())}")
                    continue

                # 安全地檢查條件
                try:
                    stock_symbol = row.get("Stock_symbol", "")
                    date_str = row.get("Date", "")[:10] if row.get("Date") else ""

                    if (stock_symbol in TICKERS_SET and
                            date_str and
                            self.START_DATE <= date_str <= self.END_DATE):

                        # 保持 FNSPID 原始欄位名稱
                        clean_row = {
                            'Date': row.get('Date', ''),
                            'Stock_symbol': row.get('Stock_symbol', ''),
                            'Article_title': row.get('Article_title', ''),
                            'Article': row.get('Article', ''),
                            'Sentiment': float(row.get('Sentiment', 0.0)),
                            'Url': row.get('Url', ''),
                            'Publisher': row.get('Publisher', ''),
                            'Author': row.get('Author', ''),
                            'Lsa_summary': row.get('Lsa_summary', '')
                        }

                        batch_records.append(clean_row)
                        count += 1

                        # 定期保存檢查點
                        if len(batch_records) >= batch_size:
                            all_records = existing_records + batch_records
                            self.checkpoint_manager.save_checkpoint(
                                'download',
                                all_records,
                                {'last_index': idx, 'missing_fields': missing_fields_count}
                            )
                            existing_records = all_records
                            batch_records = []

                except Exception as e:
                    self.logger.debug(f"處理記錄 {idx} 時出錯: {e}")
                    continue

            # 保存最終數據
            final_records = existing_records + batch_records
            final_df = pd.DataFrame(final_records)
            final_df.to_parquet(self.RAW_PARQUET)

            self.logger.info(f"成功下載 {count} 條新聞數據")
            if missing_fields_count > 0:
                self.logger.warning(f"跳過 {missing_fields_count} 條缺少必要欄位的記錄")

        except Exception as e:
            self.logger.error(f"下載中斷: {e}")
            # 保存當前進度
            if batch_records:
                all_records = existing_records + batch_records
                self.checkpoint_manager.save_checkpoint(
                    'download',
                    all_records,
                    {'last_index': idx if 'idx' in locals() else count,
                     'missing_fields': missing_fields_count}
                )
            raise

    def step3_basic_cleaning(self) -> pd.DataFrame:
        """步驟3: 基礎數據清洗（含資料驗證）"""
        self.logger.info("步驟3: 開始基礎數據清洗")

        # 檢查清洗檢查點
        checkpoint = self.checkpoint_manager.load_checkpoint('basic_clean')
        if checkpoint:
            self.logger.info("從檢查點載入已清洗數據")
            return checkpoint['data']

        # 讀取原始數據
        df = pd.read_parquet(self.RAW_PARQUET)
        self.logger.info(f"讀取到 {len(df)} 條原始數據")

        # 資料驗證
        df, invalid_df = self.validate_dataframe(df)

        # 如果有無效資料，保存供後續檢查
        if len(invalid_df) > 0:
            invalid_df.to_parquet('invalid_records.parquet')

        # 3.1 轉換日期格式（移除時區信息以避免導出問題）
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)

        # 3.2 移除重複數據
        before_dedup = len(df)
        df = df.drop_duplicates(subset=['Stock_symbol', 'Date', 'Article_title'])
        self.logger.info(f"移除 {before_dedup - len(df)} 條重複數據")

        # 3.3 處理缺失值
        df['Article_title'] = df['Article_title'].fillna('')
        df['Article'] = df['Article'].fillna('')
        df['Sentiment'] = df['Sentiment'].fillna(0.0)

        # 處理額外欄位的缺失值
        if 'Url' in df.columns:
            df['Url'] = df['Url'].fillna('')
        if 'Publisher' in df.columns:
            df['Publisher'] = df['Publisher'].fillna('')
        if 'Author' in df.columns:
            df['Author'] = df['Author'].fillna('')
        if 'Lsa_summary' in df.columns:
            df['Lsa_summary'] = df['Lsa_summary'].fillna('')

        # 3.4 文本清洗
        def clean_text(text):
            if not text:
                return ""
            # 移除多餘空白
            text = ' '.join(text.split())
            # 移除控制字符
            text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
            return text.strip()

        df['Article_title'] = df['Article_title'].apply(clean_text)
        df['Article'] = df['Article'].apply(clean_text)

        # 清洗 LSA 摘要
        if 'Lsa_summary' in df.columns:
            df['Lsa_summary'] = df['Lsa_summary'].apply(clean_text)

        # 3.5 排序
        df = df.sort_values(['Stock_symbol', 'Date'])

        # 3.6 添加基礎特徵
        df['title_length'] = df['Article_title'].str.len()
        df['text_length'] = df['Article'].str.len()
        df['weekday'] = df['Date'].dt.day_name()
        df['month'] = df['Date'].dt.month
        df['year'] = df['Date'].dt.year

        # 保存檢查點
        self.checkpoint_manager.save_checkpoint('basic_clean', df)

        self.logger.info(f"基礎清洗完成，剩餘 {len(df)} 條數據")

        # 顯示每個股票的新聞數量
        stock_counts = df['Stock_symbol'].value_counts()
        self.logger.info(f"股票新聞分佈：\n{stock_counts.head(10)}")

        # 顯示欄位資訊
        self.logger.info(f"資料欄位: {list(df.columns)}")

        return df

    def step4_quality_check_with_llm(self, df: pd.DataFrame, sample_size: int = 100) -> Dict:
        """步驟4: 使用 reasoning 模型進行數據質量檢查（支援多語言）"""
        self.logger.info(f"步驟4: 開始使用 {self.model} 模型進行 LLM 數據質量檢查 (語言: {self.language.value})")

        if not self.openai_api_key:
            self.logger.warning("未配置 OpenAI API，跳過 LLM 檢查")
            return {}

        # 檢查 LLM 檢查點
        checkpoint = self.checkpoint_manager.load_checkpoint('llm_check')
        if checkpoint:
            self.logger.info("從檢查點載入 LLM 檢查結果")
            return checkpoint['data']

        from openai import OpenAI
        client = OpenAI(
            api_key=self.openai_api_key,
            timeout=httpx.Timeout(1800.0, connect=60.0)
        )

        quality_results = {
            'relevance_checks': [],
            'sentiment_validation': [],
            'content_quality': [],
            'topic_classification': [],
            'market_impact_analysis': []
        }

        # 隨機抽樣
        sample_df = df.sample(n=min(sample_size, len(df)), random_state=42)

        # 獲取對應語言的提示詞
        comprehensive_prompt = PromptManager.get_prompt(
            'quality_check',
            self.language,
            symbol='{symbol}',
            title='{title}',
            text_snippet='{text_snippet}',
            date='{date}',
            original_sentiment='{original_sentiment}'
        )

        batch_results = []
        processed_count = 0

        for i in range(0, len(sample_df), self.batch_size):
            batch = sample_df.iloc[i:i + self.batch_size]
            self.logger.info(f"處理批次 {i // self.batch_size + 1}/{(len(sample_df) - 1) // self.batch_size + 1}")

            for idx, row in batch.iterrows():
                try:
                    # 使用重試機制調用 API
                    response = self.retry_with_exponential_backoff(
                        self._call_openai_api,
                        client,
                        comprehensive_prompt.format(
                            symbol=row['Stock_symbol'],
                            title=row['Article_title'],
                            text_snippet=row['Article'][:1000],
                            date=row['Date'],
                            original_sentiment=row['Sentiment']
                        )
                    )

                    result = json.loads(response.choices[0].message.content)
                    result['index'] = idx
                    result['stock_symbol'] = row['Stock_symbol']
                    result['date'] = str(row['Date'])
                    batch_results.append(result)

                    processed_count += 1

                    # 定期保存進度
                    if processed_count % 20 == 0:
                        self.checkpoint_manager.save_checkpoint(
                            'llm_check_progress',
                            {'results': batch_results, 'processed': processed_count}
                        )

                except Exception as e:
                    self.logger.warning(f"分析失敗 (index {idx}): {e}")

            self.logger.info(f"批次 {i // self.batch_size + 1} 完成，已處理 {len(batch_results)} 條新聞")

        # 整理結果
        for result in batch_results:
            quality_results['relevance_checks'].append({
                'index': result['index'],
                **result.get('relevance', {})
            })
            # ... 其他結果整理 ...

        # 保存最終檢查點
        self.checkpoint_manager.save_checkpoint('llm_check', quality_results)

        return quality_results

    def _call_openai_api(self, client, prompt: str):
        """調用 OpenAI API 的內部方法"""
        if self.model in ['o3', 'o4-mini']:
            # Reasoning 模型
            return client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                reasoning_effort=self.reasoning_effort,
                max_completion_tokens=2000,
                service_tier="flex" if self.use_flex else "default"
            )
        else:
            # 一般模型
            system_prompt = PromptManager.get_prompt('system', self.language)
            return client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "system",
                    "content": system_prompt
                }, {
                    "role": "user",
                    "content": prompt
                }],
                temperature=0,
                max_tokens=2000
            )

    def export_data(self, df: pd.DataFrame, format: ExportFormat, filename: str = None):
        """支援多種格式導出"""
        if filename is None:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        export_functions = {
            ExportFormat.PARQUET: lambda: df.to_parquet(f"{filename}.parquet", index=False),
            ExportFormat.CSV: lambda: df.to_csv(f"{filename}.csv", index=False, encoding='utf-8-sig'),
            ExportFormat.JSON: lambda: df.to_json(f"{filename}.json", orient='records',
                                                  force_ascii=False, indent=2)
        }

        try:
            export_functions[format]()
            self.logger.info(f"數據已導出為 {format.value} 格式: {filename}.{format.value}")
        except Exception as e:
            self.logger.error(f"導出失敗: {e}")
            raise

    def step7_create_final_dataset(self, df: pd.DataFrame) -> None:
        """步驟7: 創建最終數據集（支援多格式導出）"""
        self.logger.info("步驟7: 創建最終數據集")

        # 保存為多種格式（只保留需要的格式）
        formats_to_export = [
            ExportFormat.PARQUET,
            ExportFormat.CSV
        ]

        for format in formats_to_export:
            try:
                self.export_data(df, format, self.CLEANED_PARQUET.replace('.parquet', ''))
            except Exception as e:
                self.logger.warning(f"無法導出 {format.value} 格式: {e}")

        # 創建 DuckDB 數據庫
        con = duckdb.connect('finrl_fnspid.db')
        con.execute(f"CREATE TABLE IF NOT EXISTS fnspid AS SELECT * FROM df")
        con.execute("CREATE INDEX IF NOT EXISTS idx_symbol_date ON fnspid(Stock_symbol, Date)")
        con.close()
        self.logger.info("DuckDB 數據庫已創建")

        # 創建每日聚合版本
        daily_agg = {
            'Article_title': lambda x: ' | '.join(x),
            'Article': lambda x: ' '.join(x[:3]),  # 只取前3篇文章的內容
            'Sentiment': 'mean',
            'importance_score': 'max',
            'tags': lambda x: list(set([tag for tags in x for tag in tags]))
        }

        # 如果有 LSA 摘要，添加到聚合字典
        if 'Lsa_summary' in df.columns:
            daily_agg['Lsa_summary'] = lambda x: ' '.join(x[:3])  # 合併前3篇的摘要

        daily_df = df.groupby(['Stock_symbol', 'Date']).agg(daily_agg).reset_index()

        self.export_data(daily_df, ExportFormat.PARQUET, 'fnspid_89_2013_2023_daily')
        self.logger.info("每日聚合數據已創建")

        # 創建統計摘要
        stats_summary = {
            'total_records': len(df),
            'date_range': f"{df['Date'].min()} to {df['Date'].max()}",
            'stocks_count': df['Stock_symbol'].nunique(),
            'avg_news_per_stock': len(df) / df['Stock_symbol'].nunique(),
            'sentiment_stats': df['Sentiment'].describe().to_dict(),
            'top_publishers': df['Publisher'].value_counts().head(10).to_dict() if 'Publisher' in df.columns else {}
        }

        with open('data_summary.json', 'w', encoding='utf-8') as f:
            json.dump(stats_summary, f, indent=2, ensure_ascii=False, default=str)

        self.logger.info("數據統計摘要已保存")

    def run_pipeline(self, skip_download: bool = False, skip_llm: bool = False,
                     resume: bool = True):
        """運行完整管道（支援斷點續傳）"""
        self.logger.info("=" * 50)
        self.logger.info("開始運行 FinRL 新聞數據處理管道 v2.2")
        self.logger.info(f"語言設置: {self.language.value}")
        self.logger.info("=" * 50)

        try:
            # 檢查是否需要從檢查點恢復
            if resume:
                resume_point = self.checkpoint_manager.get_resume_point()
                if resume_point:
                    self.logger.info(f"發現檢查點，從 '{resume_point}' 階段恢復")

            # 步驟1: 獲取股票列表
            if pathlib.Path(self.TICKERS_FILE).exists():
                tickers = json.load(open(self.TICKERS_FILE))
                self.logger.info(f"從緩存讀取 {len(tickers)} 個股票代碼")
            else:
                tickers = self.step1_fetch_tickers()

            # 步驟2: 下載數據
            if not skip_download and not pathlib.Path(self.RAW_PARQUET).exists():
                self.step2_download_news(tickers)
            else:
                self.logger.info("跳過下載步驟，使用現有數據")

            # 步驟3: 基礎清洗
            df = self.step3_basic_cleaning()

            # 步驟4: LLM 質量檢查
            quality_results = {}
            if not skip_llm:
                quality_results = self.step4_quality_check_with_llm(df, sample_size=self.sample_size)

            # 步驟5: 進階清洗
            df = self.step5_advanced_cleaning(df, quality_results)

            # 步驟6: 生成報告
            report = self.step6_generate_quality_report(df, quality_results)

            # 步驟7: 創建最終數據集
            self.step7_create_final_dataset(df)

            self.logger.info("=" * 50)
            self.logger.info("管道執行完成！")
            self.logger.info(f"最終數據集: {len(df)} 條新聞")
            self.logger.info(f"涵蓋股票: {df['Stock_symbol'].nunique()} 檔")
            self.logger.info(f"查看質量報告: {self.QUALITY_REPORT}")
            self.logger.info("=" * 50)

        except Exception as e:
            self.logger.error(f"管道執行失敗: {e}")
            self.logger.info("可以使用 --resume 參數從中斷處繼續")
            raise

    def step5_advanced_cleaning(self, df: pd.DataFrame, quality_results: Dict) -> pd.DataFrame:
        """步驟5: 基於質量檢查的進階清洗"""
        self.logger.info("步驟5: 開始進階清洗")

        # 5.1 標記低質量數據
        if quality_results.get('relevance_checks'):
            low_relevance_indices = [
                r['index'] for r in quality_results['relevance_checks']
                if r.get('relevance_score', 0) < 5
            ]
            df['low_relevance'] = df.index.isin(low_relevance_indices)
        else:
            df['low_relevance'] = False

        # 5.2 添加新聞標籤
        def extract_keywords(text, lsa_summary=''):
            """從標題和 LSA 摘要提取關鍵詞"""
            keywords = {
                'earnings': ['earnings', 'revenue', 'profit', 'quarterly', 'EPS'],
                'merger': ['merger', 'acquisition', 'acquire', 'buyout', 'deal'],
                'product': ['launch', 'release', 'announce', 'introduce', 'unveil'],
                'legal': ['lawsuit', 'sue', 'court', 'legal', 'investigation'],
                'analyst': ['upgrade', 'downgrade', 'rating', 'target', 'analyst'],
                'market': ['market', 'index', 'S&P', 'NASDAQ', 'DOW'],
                'tech': ['AI', 'cloud', 'software', 'hardware', 'chip']
            }

            tags = []
            # 結合標題和 LSA 摘要進行關鍵詞提取
            combined_text = f"{text} {lsa_summary}".lower()

            for tag, words in keywords.items():
                if any(word.lower() in combined_text for word in words):
                    tags.append(tag)
            return tags

        # 使用標題和 LSA 摘要（如果有）來提取標籤
        if 'Lsa_summary' in df.columns:
            df['tags'] = df.apply(lambda row: extract_keywords(row['Article_title'], row.get('Lsa_summary', '')),
                                  axis=1)
        else:
            df['tags'] = df['Article_title'].apply(lambda x: extract_keywords(x))

        # 5.3 計算新聞重要性分數
        df['importance_score'] = (
                df['title_length'].clip(upper=100) / 100 * 0.2 +
                (df['text_length'] > 100).astype(int) * 0.3 +
                df['Sentiment'].abs() * 0.3 +
                (~df['low_relevance']).astype(int) * 0.2
        )

        # 5.4 處理異常值
        df = df[df['title_length'] > 10]  # 移除過短的標題
        df = df[df['text_length'] > 50]  # 移除過短的內容

        self.logger.info(f"進階清洗完成，最終數據量: {len(df)}")
        return df

    def step6_generate_quality_report(self, df: pd.DataFrame, quality_results: Dict) -> Dict:
        """步驟6: 生成數據質量報告"""
        self.logger.info("步驟6: 生成數據質量報告")

        # 計算情感分佈，將 Interval 轉換為字符串
        sentiment_bins = pd.cut(df['Sentiment'], bins=5)
        sentiment_dist = sentiment_bins.value_counts().sort_index()
        sentiment_dist_dict = {str(k): int(v) for k, v in sentiment_dist.items()}

        # 轉換所有 numpy/pandas 類型為 Python 原生類型的輔助函數
        def convert_to_native(obj):
            import numpy as np
            if isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
                return int(obj)
            elif isinstance(obj, (np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, pd.Series):
                return {str(k): convert_to_native(v) for k, v in obj.to_dict().items()}
            elif isinstance(obj, dict):
                return {str(k): convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(item) for item in obj]
            elif pd.isna(obj):
                return None
            else:
                return obj

        report = {
            'summary': {
                'total_records': int(len(df)),
                'date_range': f"{df['Date'].min()} to {df['Date'].max()}",
                'unique_stocks': int(df['Stock_symbol'].nunique()),
                'stocks_list': df['Stock_symbol'].unique().tolist(),
                'language': self.language.value,
                'processing_date': datetime.now().isoformat()
            },
            'data_coverage': {
                'by_year': convert_to_native(df.groupby('year').size().to_dict()),
                'by_stock': convert_to_native(df.groupby('Stock_symbol').size().to_dict()),
                'missing_stocks': list(set(json.load(open(self.TICKERS_FILE))) - set(df['Stock_symbol'].unique()))
            },
            'data_quality': {
                'null_values': convert_to_native(df.isnull().sum().to_dict()),
                'text_length_stats': {
                    'title': convert_to_native(df['title_length'].describe().to_dict()),
                    'text': convert_to_native(df['text_length'].describe().to_dict())
                },
                'sentiment_distribution': sentiment_dist_dict,  # 使用轉換後的字典
                'sentiment_stats': {  # 新增情感統計
                    'mean': float(df['Sentiment'].mean()),
                    'std': float(df['Sentiment'].std()),
                    'min': float(df['Sentiment'].min()),
                    'max': float(df['Sentiment'].max()),
                    'median': float(df['Sentiment'].median())
                },
                'low_relevance_count': int(df['low_relevance'].sum()) if 'low_relevance' in df.columns else 0
            },
            'llm_validation': quality_results,
            'recommendations': []
        }

        # 生成建議
        if report['data_coverage']['missing_stocks']:
            report['recommendations'].append(
                f"有 {len(report['data_coverage']['missing_stocks'])} 隻股票缺少新聞數據"
            )

        if report['data_quality']['low_relevance_count'] > len(df) * 0.1:
            report['recommendations'].append(
                "超過10%的新聞被標記為低相關性，建議進一步過濾"
            )

        # 保存報告
        with open(self.QUALITY_REPORT, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        self.logger.info(f"質量報告已保存到 {self.QUALITY_REPORT}")
        return report


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description='FinRL 新聞數據處理管道 v2.2')
    parser.add_argument('--openai-key', type=str, help='OpenAI API Key')
    parser.add_argument('--skip-download', action='store_true', help='跳過下載步驟')
    parser.add_argument('--skip-llm', action='store_true', help='跳過 LLM 檢查')
    parser.add_argument('--model', type=str, default='o3',
                        choices=['o3', 'o4-mini', 'gpt-4.1', 'gpt-4.1-mini'],
                        help='選擇 OpenAI 模型 (預設: o3)')
    parser.add_argument('--use-flex', action='store_true', default=True,
                        help='使用 Flex Processing (預設: True，僅對 reasoning 模型有效)')
    parser.add_argument('--sample-size', type=int, default=100,
                        help='LLM 質量檢查的樣本大小 (預設: 100)')
    parser.add_argument('--batch-size', type=int, default=5,
                        help='每批處理的新聞數量 (預設: 5)')
    parser.add_argument('--reasoning-effort', type=str, default='high',
                        choices=['low', 'medium', 'high'],
                        help='Reasoning effort for o3/o1 models (預設: high)')
    parser.add_argument('--language', type=str, default='en',
                        choices=['en', 'zh', 'es', 'jp'],
                        help='分析語言 (預設: en)')
    parser.add_argument('--resume', action='store_true', default=True,
                        help='從檢查點恢復 (預設: True)')
    parser.add_argument('--export-formats', nargs='+',
                        default=['parquet', 'csv'],
                        choices=['parquet', 'csv', 'json'],
                        help='導出格式 (預設: parquet csv)')
    args = parser.parse_args()

    # 創建處理器並運行
    language_map = {'en': Language.EN, 'zh': Language.ZH, 'es': Language.ES, 'jp': Language.JP}
    processor = FinRLNewsProcessor(
        openai_api_key=args.openai_key,
        language=language_map[args.language]
    )

    # 設置模型相關參數
    processor.model = args.model
    processor.use_flex = args.use_flex
    processor.batch_size = args.batch_size
    processor.reasoning_effort = args.reasoning_effort
    processor.sample_size = args.sample_size

    processor.run_pipeline(
        skip_download=args.skip_download,
        skip_llm=args.skip_llm,
        resume=args.resume
    )


if __name__ == "__main__":
    main()