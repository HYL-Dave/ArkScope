"""
FNSPID/FinRL-DeepSeek 格式轉換器
將爬取的新聞數據轉換為標準格式
"""

import pandas as pd
import numpy as np
from datetime import datetime
import logging
from typing import Dict, List, Optional, Union
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.summarizers.luhn import LuhnSummarizer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.summarizers.lex_rank import LexRankSummarizer
import re

class SchemaFormatter:
    def __init__(self, config: dict):
        """
        初始化格式轉換器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # FNSPID標準欄位定義
        self.standard_columns = [
            'Date',              # 日期
            'Article_title',     # 標題  
            'Stock_symbol',      # 股票代號
            'Url',              # 新聞URL
            'Publisher',        # 發佈者
            'Author',           # 作者
            'Article',          # 正文內容
            'Lsa_summary',      # LSA摘要
            'Luhn_summary',     # Luhn摘要
            'Textrank_summary', # TextRank摘要
            'Lexrank_summary',  # LexRank摘要
            'sentiment_u',      # 情緒分數 (1-5)
            'risk_q'           # 風險分數 (1-5)
        ]
        
        # 文本清理設置
        self.text_config = {
            'max_title_length': config.get('max_title_length', 200),
            'max_article_length': config.get('max_article_length', 5000),
            'summary_sentence_count': config.get('summary_sentences', 2),
            'remove_html': config.get('remove_html', True)
        }
    
    def generate_traditional_summaries(self, text: str) -> Dict[str, str]:
        """
        生成四種傳統摘要算法的摘要
        
        Args:
            text: 要摘要的文本
            
        Returns:
            Dict[str, str]: 包含四種摘要的字典
        """
        summaries = {
            'Lsa_summary': '',
            'Luhn_summary': '',
            'Textrank_summary': '',
            'Lexrank_summary': ''
        }
        
        if not text or len(text.strip()) < 100:
            return summaries
        
        try:
            # 清理文本
            cleaned_text = self._clean_text_for_summary(text)
            
            # 解析文本
            parser = PlaintextParser.from_string(cleaned_text, Tokenizer("english"))
            sentence_count = min(self.text_config['summary_sentence_count'], 
                               len(list(parser.document.sentences)))
            
            if sentence_count == 0:
                return summaries
            
            # LSA摘要
            try:
                lsa_summarizer = LsaSummarizer()
                lsa_sentences = lsa_summarizer(parser.document, sentence_count)
                summaries['Lsa_summary'] = ' '.join([str(s) for s in lsa_sentences])
            except Exception as e:
                self.logger.warning(f"LSA摘要生成失敗: {e}")
                summaries['Lsa_summary'] = text[:200] + "..."
            
            # Luhn摘要
            try:
                luhn_summarizer = LuhnSummarizer()
                luhn_sentences = luhn_summarizer(parser.document, sentence_count)
                summaries['Luhn_summary'] = ' '.join([str(s) for s in luhn_sentences])
            except Exception as e:
                self.logger.warning(f"Luhn摘要生成失敗: {e}")
                summaries['Luhn_summary'] = text[:200] + "..."
            
            # TextRank摘要
            try:
                textrank_summarizer = TextRankSummarizer()
                textrank_sentences = textrank_summarizer(parser.document, sentence_count)
                summaries['Textrank_summary'] = ' '.join([str(s) for s in textrank_sentences])
            except Exception as e:
                self.logger.warning(f"TextRank摘要生成失敗: {e}")
                summaries['Textrank_summary'] = text[:200] + "..."
            
            # LexRank摘要
            try:
                lexrank_summarizer = LexRankSummarizer()
                lexrank_sentences = lexrank_summarizer(parser.document, sentence_count)
                summaries['Lexrank_summary'] = ' '.join([str(s) for s in lexrank_sentences])
            except Exception as e:
                self.logger.warning(f"LexRank摘要生成失敗: {e}")
                summaries['Lexrank_summary'] = text[:200] + "..."
                
        except Exception as e:
            self.logger.error(f"摘要生成過程失敗: {e}")
            # 回退到簡單截斷
            short_summary = text[:200] + "..." if len(text) > 200 else text
            for key in summaries:
                summaries[key] = short_summary
        
        return summaries
    
    def _clean_text_for_summary(self, text: str) -> str:
        """
        為摘要算法清理文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理後的文本
        """
        if not text:
            return ""
        
        # 移除HTML標籤
        if self.text_config['remove_html']:
            text = re.sub(r'<[^>]+>', ' ', text)
        
        # 移除多餘空白
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符，保留基本標點
        text = re.sub(r'[^\w\s.,!?;:\'"()-]', ' ', text)
        
        # 限制長度
        max_length = self.text_config['max_article_length']
        if len(text) > max_length:
            text = text[:max_length] + "..."
        
        return text.strip()
    
    def _standardize_date(self, date_input: Union[str, pd.Timestamp, datetime]) -> str:
        """
        標準化日期格式
        
        Args:
            date_input: 各種格式的日期輸入
            
        Returns:
            str: 標準化的日期字符串 (YYYY-MM-DD)
        """
        if pd.isna(date_input) or not date_input:
            return ""
        
        try:
            if isinstance(date_input, str):
                # 嘗試解析字符串日期
                date_formats = [
                    '%Y-%m-%d',
                    '%Y/%m/%d',
                    '%m/%d/%Y',
                    '%d/%m/%Y',
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%dT%H:%M:%SZ'
                ]
                
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(date_input[:len(fmt)], fmt)
                        return parsed_date.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
                
                # 如果無法解析，嘗試pandas
                try:
                    parsed_date = pd.to_datetime(date_input)
                    return parsed_date.strftime('%Y-%m-%d')
                except:
                    pass
            
            elif isinstance(date_input, (pd.Timestamp, datetime)):
                return date_input.strftime('%Y-%m-%d')
            
            # 如果都失敗，記錄警告並返回空字符串
            self.logger.warning(f"無法解析日期: {date_input}")
            return ""
            
        except Exception as e:
            self.logger.warning(f"日期標準化失敗: {e}")
            return ""
    
    def _clean_text_field(self, text: Union[str, None], max_length: int) -> str:
        """
        清理文本欄位
        
        Args:
            text: 原始文本
            max_length: 最大長度
            
        Returns:
            str: 清理後的文本
        """
        if pd.isna(text) or not text:
            return ""
        
        text = str(text).strip()
        
        # 移除HTML標籤
        if self.text_config['remove_html']:
            text = re.sub(r'<[^>]+>', ' ', text)
        
        # 標準化空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除控制字符
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        # 限制長度
        if len(text) > max_length:
            text = text[:max_length].rstrip() + "..."
        
        return text
    
    def convert_to_standard_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        將原始新聞數據轉換為標準FNSPID格式
        
        Args:
            df: 包含原始新聞數據的DataFrame
            
        Returns:
            pd.DataFrame: 標準格式的DataFrame
        """
        self.logger.info(f"開始轉換 {len(df)} 筆記錄為標準格式")
        
        # 創建新的DataFrame
        formatted_records = []
        
        for idx, row in df.iterrows():
            try:
                # 基本欄位映射和清理
                record = {
                    'Date': self._standardize_date(row.get('Date', '')),
                    'Article_title': self._clean_text_field(
                        row.get('Article_title', ''), 
                        self.text_config['max_title_length']
                    ),
                    'Stock_symbol': str(row.get('Stock_symbol', '')).strip().upper(),
                    'Url': str(row.get('Url', '')).strip(),
                    'Publisher': self._clean_text_field(row.get('Publisher', ''), 100),
                    'Author': self._clean_text_field(row.get('Author', ''), 200),
                    'Article': self._clean_text_field(
                        row.get('Article', ''), 
                        self.text_config['max_article_length']
                    )
                }
                
                # 生成傳統摘要（如果文章內容存在）
                if record['Article']:
                    summaries = self.generate_traditional_summaries(record['Article'])
                    record.update(summaries)
                else:
                    # 空文章的默認摘要
                    for summary_type in ['Lsa_summary', 'Luhn_summary', 'Textrank_summary', 'Lexrank_summary']:
                        record[summary_type] = ""
                
                # LLM評分（如果已存在）
                record['sentiment_u'] = row.get('sentiment_u', None)
                record['risk_q'] = row.get('risk_q', None)
                
                formatted_records.append(record)
                
                # 進度報告
                if (idx + 1) % 100 == 0:
                    self.logger.info(f"轉換進度: {idx + 1}/{len(df)}")
                    
            except Exception as e:
                self.logger.error(f"轉換第 {idx} 行失敗: {e}")
                continue
        
        # 創建結果DataFrame
        result_df = pd.DataFrame(formatted_records)
        
        # 確保所有標準欄位都存在
        for col in self.standard_columns:
            if col not in result_df.columns:
                result_df[col] = None
        
        # 重新排序欄位
        result_df = result_df[self.standard_columns]
        
        self.logger.info(f"格式轉換完成，成功轉換 {len(result_df)} 筆記錄")
        
        return result_df
    
    def validate_format(self, df: pd.DataFrame) -> Dict[str, Union[bool, List[str]]]:
        """
        驗證數據格式是否符合標準
        
        Args:
            df: 要驗證的DataFrame
            
        Returns:
            Dict: 驗證結果
        """
        validation_result = {
            'is_valid': True,
            'missing_columns': [],
            'data_quality_issues': [],
            'statistics': {}
        }
        
        # 檢查必要欄位
        missing_columns = [col for col in self.standard_columns if col not in df.columns]
        if missing_columns:
            validation_result['missing_columns'] = missing_columns
            validation_result['is_valid'] = False
        
        # 數據品質檢查
        quality_issues = []
        
        # 檢查空值比例
        null_percentages = (df.isnull().sum() / len(df) * 100).round(2)
        for col, percentage in null_percentages.items():
            if col in ['Date', 'Article_title', 'Stock_symbol', 'Article'] and percentage > 10:
                quality_issues.append(f"{col} 有 {percentage}% 的空值")
        
        # 檢查日期格式
        if 'Date' in df.columns:
            invalid_dates = df[df['Date'].str.len() != 10]['Date'].count()
            if invalid_dates > 0:
                quality_issues.append(f"有 {invalid_dates} 個無效日期格式")
        
        # 檢查評分範圍
        for score_col in ['sentiment_u', 'risk_q']:
            if score_col in df.columns:
                valid_mask = df[score_col].between(1, 5, inclusive="both") | df[score_col].isna()
                invalid_scores = df[~valid_mask][score_col].count()
                if invalid_scores > 0:
                    quality_issues.append(f"{score_col} 有 {invalid_scores} 個超出1-5範圍的值")
        
        validation_result['data_quality_issues'] = quality_issues
        
        # 統計資訊
        validation_result['statistics'] = {
            'total_records': len(df),
            'unique_stocks': df['Stock_symbol'].nunique() if 'Stock_symbol' in df.columns else 0,
            'date_range': {
                'start': df['Date'].min() if 'Date' in df.columns else None,
                'end': df['Date'].max() if 'Date' in df.columns else None
            },
            'avg_article_length': df['Article'].str.len().mean() if 'Article' in df.columns else 0
        }
        
        if quality_issues:
            validation_result['is_valid'] = False
        
        return validation_result
    
    def save_formatted_data(self, df: pd.DataFrame, output_path: str, 
                           format_type: str = 'csv') -> None:
        """
        儲存格式化後的數據
        
        Args:
            df: 要儲存的DataFrame
            output_path: 輸出路徑
            format_type: 檔案格式 ('csv', 'parquet', 'json')
        """
        try:
            if format_type == 'csv':
                df.to_csv(output_path, index=False, encoding='utf-8')
            elif format_type == 'parquet':
                df.to_parquet(output_path, index=False)
            elif format_type == 'json':
                df.to_json(output_path, orient='records', lines=True, ensure_ascii=False)
            else:
                raise ValueError(f"不支援的格式: {format_type}")
            
            self.logger.info(f"數據已儲存至: {output_path}")
            
            # 儲存驗證報告
            validation_result = self.validate_format(df)
            validation_path = output_path.replace(f'.{format_type}', '_validation.json')
            
            import json
            with open(validation_path, 'w', encoding='utf-8') as f:
                json.dump(validation_result, f, indent=2, ensure_ascii=False, default=str)
            
            self.logger.info(f"驗證報告已儲存至: {validation_path}")
            
        except Exception as e:
            self.logger.error(f"儲存數據失敗: {e}")
            raise

if __name__ == "__main__":
    # 使用範例
    config = {
        'max_title_length': 200,
        'max_article_length': 5000,
        'summary_sentences': 2,
        'remove_html': True
    }
    
    formatter = SchemaFormatter(config)
    
    # 測試數據
    test_data = pd.DataFrame([
        {
            'Date': '2024-01-15',
            'Article_title': 'Apple Reports Strong Q4 Earnings',
            'Stock_symbol': 'AAPL',
            'Article': 'Apple Inc. announced its fourth quarter results today...',
            'Url': 'https://example.com/news/1',
            'Publisher': 'Financial News',
            'Author': 'John Doe'
        }
    ])
    
    # 格式轉換
    formatted_df = formatter.convert_to_standard_format(test_data)
    print(f"轉換結果: {len(formatted_df)} 筆記錄")
    print(formatted_df.columns.tolist())
    
    # 驗證格式
    validation = formatter.validate_format(formatted_df)
    print(f"格式驗證: {validation['is_valid']}")
