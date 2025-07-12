"""
LLM情緒與風險評分器
使用OpenAI API複製FinRL-DeepSeek的評分邏輯
"""

import openai
import pandas as pd
import time
import logging
from typing import List, Tuple, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
from datetime import datetime
import tiktoken

class LLMScorer:
    def __init__(self, config: dict):
        """
        初始化LLM評分器
        
        Args:
            config: 配置字典，包含API密鑰、模型設置等
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 初始化OpenAI客戶端
        self.client = openai.OpenAI(
            api_key=config['openai_api_key']
        )
        
        # 模型配置
        self.model_config = {
            'model': config.get('model', 'gpt-4o'),
            'temperature': config.get('temperature', 0),
            'max_tokens': config.get('max_tokens', 5),
            'timeout': config.get('timeout', 30)
        }
        
        # 速率限制配置
        self.rate_limit = {
            'requests_per_minute': config.get('requests_per_minute', 100),
            'tokens_per_minute': config.get('tokens_per_minute', 30000),
            'batch_size': config.get('batch_size', 50)
        }
        
        # 成本追蹤
        self.cost_tracker = {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_requests': 0,
            'estimated_cost': 0.0
        }
        
        # 載入官方prompt模板
        self.prompts = self._load_official_prompts()
        
        # 初始化tokenizer用於成本計算
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model_config['model'])
        except:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def _load_official_prompts(self) -> Dict[str, str]:
        """
        載入FinRL-DeepSeek官方prompt模板
        
        Returns:
            Dict[str, str]: 包含sentiment和risk prompt的字典
        """
        return {
            'sentiment': """You are a financial expert with sentiment analysis and stock recommendation experience. 
Based on a specific stock ({stock_symbol}), score for range from 1 to 5, where 1 is negative, 2 is somewhat negative, 3 is neutral, 4 is somewhat positive, 5 is positive.

Article: {article_text}

Return only the number (1-5):""",
            
            'risk': """You are a financial expert specializing in risk assessment. 
Based on a specific stock ({stock_symbol}), provide a risk score from 1 to 5, where: 
1 indicates very low risk, 2 indicates low risk, 3 indicates moderate risk (default if the news is unclear), 4 indicates high risk, 5 indicates very high risk.

Article: {article_text}

Return only the number (1-5):"""
        }
    
    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的token數量
        
        Args:
            text: 要估算的文本
            
        Returns:
            int: 估算的token數量
        """
        try:
            return len(self.tokenizer.encode(text))
        except:
            # 回退到簡單估算
            return len(text) // 4
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        計算API調用成本
        
        Args:
            input_tokens: 輸入token數量
            output_tokens: 輸出token數量
            
        Returns:
            float: 估算成本（美元）
        """
        # GPT-4o pricing (2025年1月)
        pricing = {
            'gpt-4o': {'input': 0.005, 'output': 0.015},  # per 1K tokens
            'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006}
        }
        
        model = self.model_config['model']
        rates = pricing.get(model, pricing['gpt-4o'])
        
        input_cost = (input_tokens / 1000) * rates['input']
        output_cost = (output_tokens / 1000) * rates['output']
        
        return input_cost + output_cost
    
    def score_single_article(self, article_text: str, stock_symbol: str,
                           score_type: str = 'both') -> Tuple[Optional[int], Optional[int]]:
        """
        對單篇文章進行情緒與風險評分
        
        Args:
            article_text: 新聞文章內容
            stock_symbol: 股票代號
            score_type: 評分類型 ('sentiment', 'risk', 'both')
            
        Returns:
            Tuple[Optional[int], Optional[int]]: (sentiment_score, risk_score)
        """
        sentiment_score = None
        risk_score = None
        
        try:
            # 文本預處理：截斷過長的文章
            max_length = 3000  # 約1000 tokens
            if len(article_text) > max_length:
                article_text = article_text[:max_length] + "..."
            
            if score_type in ['sentiment', 'both']:
                sentiment_score = self._get_score(article_text, stock_symbol, 'sentiment')
                time.sleep(0.1)  # 簡單的速率控制
            
            if score_type in ['risk', 'both']:
                risk_score = self._get_score(article_text, stock_symbol, 'risk')
                time.sleep(0.1)
            
            return sentiment_score, risk_score
            
        except Exception as e:
            self.logger.error(f"評分失敗 {stock_symbol}: {e}")
            return None, None
    
    def _get_score(self, article_text: str, stock_symbol: str, score_type: str) -> Optional[int]:
        """
        獲取單一類型的評分
        
        Args:
            article_text: 文章內容
            stock_symbol: 股票代號
            score_type: 評分類型 ('sentiment' 或 'risk')
            
        Returns:
            Optional[int]: 1-5的評分，失敗時返回None
        """
        try:
            # 構建prompt
            prompt = self.prompts[score_type].format(
                stock_symbol=stock_symbol,
                article_text=article_text
            )
            
            # 估算token數量
            input_tokens = self._estimate_tokens(prompt)
            
            # 調用OpenAI API
            response = self.client.chat.completions.create(
                model=self.model_config['model'],
                messages=[{"role": "user", "content": prompt}],
                temperature=self.model_config['temperature'],
                max_tokens=self.model_config['max_tokens'],
                timeout=self.model_config['timeout']
            )
            
            # 解析回應
            score_text = response.choices[0].message.content.strip()
            score = self._parse_score(score_text)
            
            # 更新成本追蹤
            output_tokens = response.usage.completion_tokens if response.usage else 1
            actual_input_tokens = response.usage.prompt_tokens if response.usage else input_tokens
            
            self.cost_tracker['total_input_tokens'] += actual_input_tokens
            self.cost_tracker['total_output_tokens'] += output_tokens
            self.cost_tracker['total_requests'] += 1
            self.cost_tracker['estimated_cost'] += self._calculate_cost(actual_input_tokens, output_tokens)
            
            return score
            
        except openai.RateLimitError:
            self.logger.warning(f"API速率限制，等待重試...")
            time.sleep(60)  # 等待1分鐘
            return self._get_score(article_text, stock_symbol, score_type)
            
        except openai.APITimeoutError:
            self.logger.warning(f"API超時，使用默認分數")
            return 3  # 中性默認值
            
        except Exception as e:
            self.logger.error(f"API調用失敗: {e}")
            return None
    
    def _parse_score(self, score_text: str) -> Optional[int]:
        """
        從LLM回應中解析評分
        
        Args:
            score_text: LLM回應文本
            
        Returns:
            Optional[int]: 解析出的1-5評分
        """
        try:
            # 尋找數字
            numbers = re.findall(r'\b[1-5]\b', score_text)
            
            if numbers:
                score = int(numbers[0])
                if 1 <= score <= 5:
                    return score
            
            # 如果找不到有效數字，嘗試其他方法
            if 'negative' in score_text.lower():
                return 2 if 'somewhat' in score_text.lower() else 1
            elif 'positive' in score_text.lower():
                return 4 if 'somewhat' in score_text.lower() else 5
            elif 'neutral' in score_text.lower():
                return 3
            elif 'high risk' in score_text.lower():
                return 5 if 'very high' in score_text.lower() else 4
            elif 'low risk' in score_text.lower():
                return 1 if 'very low' in score_text.lower() else 2
            elif 'moderate' in score_text.lower():
                return 3
            
            # 默認返回中性
            self.logger.warning(f"無法解析評分: {score_text}")
            return 3
            
        except Exception as e:
            self.logger.warning(f"評分解析錯誤: {e}")
            return 3
    
    def batch_score_articles(self, df: pd.DataFrame, 
                           max_workers: int = 5) -> pd.DataFrame:
        """
        批量評分文章
        
        Args:
            df: 包含新聞數據的DataFrame
            max_workers: 最大並行工作者數
            
        Returns:
            pd.DataFrame: 添加了評分欄位的DataFrame
        """
        self.logger.info(f"開始批量評分 {len(df)} 篇文章")
        
        # 確保必要欄位存在
        required_columns = ['Article', 'Stock_symbol']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"缺少必要欄位: {missing_columns}")
        
        # 準備結果欄位
        df['sentiment_u'] = None
        df['risk_q'] = None
        df['scoring_timestamp'] = datetime.now().isoformat()
        
        # 批量處理
        total_articles = len(df)
        completed = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任務
            future_to_index = {}
            
            for idx, row in df.iterrows():
                if pd.notna(row['Article']) and row['Article'].strip():
                    future = executor.submit(
                        self.score_single_article,
                        row['Article'],
                        row['Stock_symbol']
                    )
                    future_to_index[future] = idx
                else:
                    # 空文章使用默認分數
                    df.loc[idx, 'sentiment_u'] = 3
                    df.loc[idx, 'risk_q'] = 3
                    completed += 1
            
            # 收集結果
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                completed += 1
                
                try:
                    sentiment_score, risk_score = future.result()
                    
                    df.loc[idx, 'sentiment_u'] = sentiment_score if sentiment_score is not None else 3
                    df.loc[idx, 'risk_q'] = risk_score if risk_score is not None else 3
                    
                except Exception as e:
                    self.logger.warning(f"處理第 {idx} 行失敗: {e}")
                    df.loc[idx, 'sentiment_u'] = 3
                    df.loc[idx, 'risk_q'] = 3
                
                # 進度報告
                if completed % 50 == 0:
                    progress = completed / total_articles * 100
                    self.logger.info(f"評分進度: {completed}/{total_articles} ({progress:.1f}%)")
                    self.logger.info(f"當前成本估算: ${self.cost_tracker['estimated_cost']:.4f}")
        
        self.logger.info(f"批量評分完成，總成本估算: ${self.cost_tracker['estimated_cost']:.4f}")
        return df
    
    def get_cost_summary(self) -> Dict:
        """
        獲取成本總結
        
        Returns:
            Dict: 成本統計資訊
        """
        return {
            'total_requests': self.cost_tracker['total_requests'],
            'total_input_tokens': self.cost_tracker['total_input_tokens'],
            'total_output_tokens': self.cost_tracker['total_output_tokens'],
            'estimated_cost_usd': round(self.cost_tracker['estimated_cost'], 4),
            'avg_cost_per_request': round(
                self.cost_tracker['estimated_cost'] / max(self.cost_tracker['total_requests'], 1), 4
            ),
            'model_used': self.model_config['model']
        }
    
    def save_cost_report(self, output_path: str) -> None:
        """
        儲存成本報告
        
        Args:
            output_path: 輸出路徑
        """
        cost_summary = self.get_cost_summary()
        cost_summary['report_timestamp'] = datetime.now().isoformat()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cost_summary, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"成本報告已儲存至: {output_path}")

if __name__ == "__main__":
    # 使用範例
    config = {
        'openai_api_key': 'your-api-key-here',
        'model': 'gpt-4o-mini',  # 使用更便宜的模型進行測試
        'temperature': 0,
        'requests_per_minute': 100
    }
    
    scorer = LLMScorer(config)
    
    # 測試單篇文章評分
    test_article = "Apple Inc. reported strong quarterly earnings, beating analyst expectations..."
    sentiment, risk = scorer.score_single_article(test_article, "AAPL")
    
    print(f"測試評分結果 - Sentiment: {sentiment}, Risk: {risk}")
    print(f"成本統計: {scorer.get_cost_summary()}")
