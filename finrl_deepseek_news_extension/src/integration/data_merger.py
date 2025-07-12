"""
數據合併器
負責將新爬取的2024-2025數據與原始FinRL-DeepSeek數據集合併
"""

import pandas as pd
import numpy as np
from datetime import datetime
import logging
from typing import Dict, List, Tuple, Optional
import warnings

class DataMerger:
    def __init__(self, config: dict):
        """
        初始化數據合併器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 合併策略配置
        self.merge_config = {
            'overlap_strategy': config.get('overlap_strategy', 'prefer_new'),  # 重疊處理策略
            'date_validation': config.get('date_validation', True),            # 日期驗證
            'schema_validation': config.get('schema_validation', True),        # 格式驗證
            'quality_filters': config.get('quality_filters', {}),             # 品質過濾
            'deduplication': config.get('deduplication', True)                # 去重處理
        }
        
        # 必要欄位定義
        self.required_columns = [
            'Date', 'Article_title', 'Stock_symbol', 'Url', 'Publisher', 'Author',
            'Article', 'Lsa_summary', 'Luhn_summary', 'Textrank_summary', 
            'Lexrank_summary', 'sentiment_u', 'risk_q'
        ]
        
        # 合併統計
        self.merge_stats = {
            'original_records': 0,
            'new_records': 0,
            'duplicates_removed': 0,
            'invalid_records_filtered': 0,
            'final_records': 0,
            'date_range_original': {},
            'date_range_new': {},
            'date_range_final': {}
        }
    
    def validate_schema_compatibility(self, df1: pd.DataFrame, df2: pd.DataFrame) -> Dict[str, List[str]]:
        """
        驗證兩個數據集的格式相容性
        
        Args:
            df1: 原始數據集
            df2: 新數據集
            
        Returns:
            Dict[str, List[str]]: 驗證結果
        """
        validation_result = {
            'missing_in_df1': [],
            'missing_in_df2': [],
            'type_mismatches': [],
            'warnings': []
        }
        
        # 檢查缺失欄位
        df1_columns = set(df1.columns)
        df2_columns = set(df2.columns)
        required_columns = set(self.required_columns)
        
        validation_result['missing_in_df1'] = list(required_columns - df1_columns)
        validation_result['missing_in_df2'] = list(required_columns - df2_columns)
        
        # 檢查共同欄位的資料型別
        common_columns = df1_columns & df2_columns
        
        for col in common_columns:
            if col in ['sentiment_u', 'risk_q']:
                # 檢查評分欄位是否在有效範圍內
                df1_invalid = df1[~df1[col].between(1, 5, na=True)][col].count()
                df2_invalid = df2[~df2[col].between(1, 5, na=True)][col].count()
                
                if df1_invalid > 0:
                    validation_result['warnings'].append(f"df1 的 {col} 有 {df1_invalid} 個超出1-5範圍的值")
                if df2_invalid > 0:
                    validation_result['warnings'].append(f"df2 的 {col} 有 {df2_invalid} 個超出1-5範圍的值")
        
        return validation_result
    
    def preprocess_dataframe(self, df: pd.DataFrame, source_name: str) -> pd.DataFrame:
        """
        預處理數據框
        
        Args:
            df: 要處理的數據框
            source_name: 數據來源名稱
            
        Returns:
            pd.DataFrame: 預處理後的數據框
        """
        self.logger.info(f"正在預處理 {source_name} 數據，原始記錄: {len(df)}")
        
        processed_df = df.copy()
        
        # 確保所有必要欄位存在
        for col in self.required_columns:
            if col not in processed_df.columns:
                if col in ['sentiment_u', 'risk_q']:
                    processed_df[col] = 3  # 默認中性值
                else:
                    processed_df[col] = ''
        
        # 日期格式標準化
        if 'Date' in processed_df.columns:
            processed_df['Date'] = pd.to_datetime(processed_df['Date'], errors='coerce')
            processed_df['Date'] = processed_df['Date'].dt.strftime('%Y-%m-%d')
            
            # 移除無效日期的記錄
            invalid_dates = processed_df['Date'].isna().sum()
            if invalid_dates > 0:
                self.logger.warning(f"{source_name}: 移除 {invalid_dates} 筆無效日期記錄")
                processed_df = processed_df.dropna(subset=['Date'])
        
        # 股票代號標準化
        if 'Stock_symbol' in processed_df.columns:
            processed_df['Stock_symbol'] = processed_df['Stock_symbol'].str.upper().str.strip()
            
            # 移除空股票代號
            empty_symbols = processed_df['Stock_symbol'].str.len() == 0
            if empty_symbols.sum() > 0:
                self.logger.warning(f"{source_name}: 移除 {empty_symbols.sum()} 筆空股票代號記錄")
                processed_df = processed_df[~empty_symbols]
        
        # 評分欄位範圍檢查
        for score_col in ['sentiment_u', 'risk_q']:
            if score_col in processed_df.columns:
                # 將超出範圍的值設為3（中性）
                out_of_range = ~processed_df[score_col].between(1, 5, na=True)
                if out_of_range.sum() > 0:
                    self.logger.warning(f"{source_name}: 修正 {out_of_range.sum()} 個超出範圍的 {score_col} 值")
                    processed_df.loc[out_of_range, score_col] = 3
                
                # 填充空值
                processed_df[score_col] = processed_df[score_col].fillna(3)
        
        # 文本欄位清理
        text_columns = ['Article_title', 'Article', 'Author', 'Publisher']
        for col in text_columns:
            if col in processed_df.columns:
                processed_df[col] = processed_df[col].fillna('').astype(str)
        
        # 品質過濾（如果啟用）
        if self.merge_config['quality_filters']:
            processed_df = self._apply_quality_filters(processed_df, source_name)
        
        self.logger.info(f"{source_name} 預處理完成，處理後記錄: {len(processed_df)}")
        return processed_df
    
    def _apply_quality_filters(self, df: pd.DataFrame, source_name: str) -> pd.DataFrame:
        """
        應用品質過濾器
        
        Args:
            df: 要過濾的數據框
            source_name: 數據來源名稱
            
        Returns:
            pd.DataFrame: 過濾後的數據框
        """
        filters = self.merge_config['quality_filters']
        original_count = len(df)
        
        # 最小標題長度過濾
        if 'min_title_length' in filters:
            min_len = filters['min_title_length']
            title_filter = df['Article_title'].str.len() >= min_len
            df = df[title_filter]
            self.logger.info(f"{source_name}: 標題長度過濾移除 {original_count - len(df)} 筆記錄")
        
        # 最小文章長度過濾
        if 'min_article_length' in filters:
            min_len = filters['min_article_length']
            article_filter = df['Article'].str.len() >= min_len
            df = df[article_filter]
            self.logger.info(f"{source_name}: 文章長度過濾移除 {original_count - len(df)} 筆記錄")
        
        # URL有效性過濾
        if 'require_valid_url' in filters and filters['require_valid_url']:
            url_filter = df['Url'].str.startswith(('http://', 'https://'))
            df = df[url_filter]
            self.logger.info(f"{source_name}: URL有效性過濾移除 {original_count - len(df)} 筆記錄")
        
        return df
    
    def identify_duplicates(self, df1: pd.DataFrame, df2: pd.DataFrame) -> Dict[str, pd.Index]:
        """
        識別重複記錄
        
        Args:
            df1: 原始數據集
            df2: 新數據集
            
        Returns:
            Dict[str, pd.Index]: 重複記錄的索引
        """
        duplicate_info = {
            'url_duplicates': pd.Index([]),
            'title_stock_duplicates': pd.Index([]),
            'content_similarity_duplicates': pd.Index([])
        }
        
        # 基於URL的重複檢測
        if 'Url' in df1.columns and 'Url' in df2.columns:
            common_urls = set(df1['Url']) & set(df2['Url'])
            if common_urls:
                url_duplicates = df2[df2['Url'].isin(common_urls)].index
                duplicate_info['url_duplicates'] = url_duplicates
                self.logger.info(f"發現 {len(url_duplicates)} 個基於URL的重複記錄")
        
        # 基於標題+股票的重複檢測
        if all(col in df1.columns and col in df2.columns for col in ['Article_title', 'Stock_symbol']):
            df1_title_stock = df1[['Article_title', 'Stock_symbol']].apply(
                lambda x: f"{x['Article_title']}_{x['Stock_symbol']}", axis=1
            )
            df2_title_stock = df2[['Article_title', 'Stock_symbol']].apply(
                lambda x: f"{x['Article_title']}_{x['Stock_symbol']}", axis=1
            )
            
            common_title_stock = set(df1_title_stock) & set(df2_title_stock)
            if common_title_stock:
                title_stock_duplicates = df2[df2_title_stock.isin(common_title_stock)].index
                duplicate_info['title_stock_duplicates'] = title_stock_duplicates
                self.logger.info(f"發現 {len(title_stock_duplicates)} 個基於標題+股票的重複記錄")
        
        return duplicate_info
    
    def handle_overlapping_period(self, df1: pd.DataFrame, df2: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        處理重疊時期的數據
        
        Args:
            df1: 原始數據集
            df2: 新數據集
            
        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: 處理後的數據集
        """
        if 'Date' not in df1.columns or 'Date' not in df2.columns:
            return df1, df2
        
        # 轉換日期格式進行比較
        df1_dates = pd.to_datetime(df1['Date'])
        df2_dates = pd.to_datetime(df2['Date'])
        
        # 找出重疊的日期範圍
        df1_min, df1_max = df1_dates.min(), df1_dates.max()
        df2_min, df2_max = df2_dates.min(), df2_dates.max()
        
        overlap_start = max(df1_min, df2_min)
        overlap_end = min(df1_max, df2_max)
        
        if overlap_start <= overlap_end:
            self.logger.info(f"發現重疊期間: {overlap_start.date()} 到 {overlap_end.date()}")
            
            strategy = self.merge_config['overlap_strategy']
            
            if strategy == 'prefer_new':
                # 保留新數據，移除原始數據中重疊期間的記錄
                overlap_mask = (df1_dates >= overlap_start) & (df1_dates <= overlap_end)
                removed_count = overlap_mask.sum()
                df1_filtered = df1[~overlap_mask].copy()
                
                self.logger.info(f"重疊處理策略 'prefer_new': 從原始數據移除 {removed_count} 筆記錄")
                return df1_filtered, df2
                
            elif strategy == 'prefer_original':
                # 保留原始數據，移除新數據中重疊期間的記錄
                overlap_mask = (df2_dates >= overlap_start) & (df2_dates <= overlap_end)
                removed_count = overlap_mask.sum()
                df2_filtered = df2[~overlap_mask].copy()
                
                self.logger.info(f"重疊處理策略 'prefer_original': 從新數據移除 {removed_count} 筆記錄")
                return df1, df2_filtered
                
            elif strategy == 'merge_all':
                # 保留所有數據，稍後通過去重處理
                self.logger.info("重疊處理策略 'merge_all': 保留所有數據，將通過去重處理")
                return df1, df2
        
        return df1, df2
    
    def remove_duplicates_across_datasets(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        在合併後的數據集中移除重複記錄
        
        Args:
            df: 合併後的數據框
            
        Returns:
            pd.DataFrame: 去重後的數據框
        """
        if not self.merge_config['deduplication']:
            return df
        
        original_count = len(df)
        
        # 基於URL去重
        if 'Url' in df.columns:
            df = df.drop_duplicates(subset=['Url'], keep='first')
            self.logger.info(f"URL去重移除 {original_count - len(df)} 筆記錄")
        
        # 基於標題+股票+日期去重
        dedup_columns = ['Article_title', 'Stock_symbol', 'Date']
        available_columns = [col for col in dedup_columns if col in df.columns]
        
        if available_columns:
            before_count = len(df)
            df = df.drop_duplicates(subset=available_columns, keep='first')
            removed = before_count - len(df)
            if removed > 0:
                self.logger.info(f"標題+股票+日期去重移除 {removed} 筆記錄")
        
        self.merge_stats['duplicates_removed'] = original_count - len(df)
        return df
    
    def merge_datasets(self, original_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
        """
        主要合併函數
        
        Args:
            original_df: 原始FinRL-DeepSeek數據
            new_df: 新爬取的2024-2025數據
            
        Returns:
            pd.DataFrame: 合併後的完整數據集
        """
        self.logger.info("=" * 50)
        self.logger.info("開始數據合併流程")
        self.logger.info("=" * 50)
        
        # 記錄初始統計
        self.merge_stats['original_records'] = len(original_df)
        self.merge_stats['new_records'] = len(new_df)
        
        # 格式相容性驗證
        if self.merge_config['schema_validation']:
            validation_result = self.validate_schema_compatibility(original_df, new_df)
            if validation_result['missing_in_df1'] or validation_result['missing_in_df2']:
                self.logger.warning(f"格式相容性問題: {validation_result}")
        
        # 數據預處理
        processed_original = self.preprocess_dataframe(original_df, "原始數據")
        processed_new = self.preprocess_dataframe(new_df, "新數據")
        
        # 處理重疊期間
        processed_original, processed_new = self.handle_overlapping_period(
            processed_original, processed_new
        )
        
        # 合併數據集
        self.logger.info("正在合併數據集...")
        merged_df = pd.concat([processed_original, processed_new], ignore_index=True)
        
        # 去重處理
        final_df = self.remove_duplicates_across_datasets(merged_df)
        
        # 最終排序（按日期和股票代號）
        if 'Date' in final_df.columns and 'Stock_symbol' in final_df.columns:
            final_df = final_df.sort_values(['Date', 'Stock_symbol']).reset_index(drop=True)
        
        # 更新統計資訊
        self.merge_stats['final_records'] = len(final_df)
        
        if 'Date' in final_df.columns:
            self.merge_stats['date_range_final'] = {
                'start': final_df['Date'].min(),
                'end': final_df['Date'].max()
            }
        
        # 生成合併報告
        self._generate_merge_report(final_df)
        
        self.logger.info("數據合併完成!")
        self.logger.info(f"最終數據集: {len(final_df)} 筆記錄")
        
        return final_df
    
    def _generate_merge_report(self, final_df: pd.DataFrame) -> None:
        """
        生成合併報告
        
        Args:
            final_df: 最終合併的數據框
        """
        report = {
            'merge_timestamp': datetime.now().isoformat(),
            'statistics': self.merge_stats,
            'data_quality': {
                'unique_stocks': final_df['Stock_symbol'].nunique() if 'Stock_symbol' in final_df.columns else 0,
                'date_coverage_days': 0,
                'records_per_stock': {},
                'missing_data_summary': {}
            }
        }
        
        # 計算日期覆蓋範圍
        if 'Date' in final_df.columns:
            try:
                date_range = pd.to_datetime(final_df['Date'])
                coverage_days = (date_range.max() - date_range.min()).days
                report['data_quality']['date_coverage_days'] = coverage_days
            except:
                pass
        
        # 每檔股票的記錄數統計
        if 'Stock_symbol' in final_df.columns:
            stock_counts = final_df['Stock_symbol'].value_counts().to_dict()
            report['data_quality']['records_per_stock'] = {
                'top_10': dict(list(stock_counts.items())[:10]),
                'average_per_stock': len(final_df) / max(final_df['Stock_symbol'].nunique(), 1)
            }
        
        # 缺失數據摘要
        missing_summary = {}
        for col in self.required_columns:
            if col in final_df.columns:
                missing_count = final_df[col].isna().sum()
                missing_percentage = (missing_count / len(final_df)) * 100
                missing_summary[col] = {
                    'missing_count': int(missing_count),
                    'missing_percentage': round(missing_percentage, 2)
                }
        
        report['data_quality']['missing_data_summary'] = missing_summary
        
        # 儲存報告
        report_path = f"reports/data_merge_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        
        try:
            import json
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
            self.logger.info(f"合併報告已儲存至: {report_path}")
        except Exception as e:
            self.logger.warning(f"儲存合併報告失敗: {e}")
    
    def get_merge_statistics(self) -> Dict:
        """
        獲取合併統計資訊
        
        Returns:
            Dict: 合併統計
        """
        return self.merge_stats.copy()

if __name__ == "__main__":
    # 使用範例
    config = {
        'overlap_strategy': 'prefer_new',
        'date_validation': True,
        'schema_validation': True,
        'deduplication': True,
        'quality_filters': {
            'min_title_length': 10,
            'min_article_length': 50,
            'require_valid_url': True
        }
    }
    
    merger = DataMerger(config)
    
    # 模擬數據測試
    original_data = pd.DataFrame([
        {
            'Date': '2023-12-31',
            'Article_title': 'Year End Market Summary',
            'Stock_symbol': 'AAPL',
            'Article': 'Market summary content...',
            'sentiment_u': 4,
            'risk_q': 2
        }
    ])
    
    new_data = pd.DataFrame([
        {
            'Date': '2024-01-01',
            'Article_title': 'New Year Market Outlook',
            'Stock_symbol': 'AAPL',
            'Article': 'Market outlook content...',
            'sentiment_u': 3,
            'risk_q': 3
        }
    ])
    
    # 執行合併
    merged_result = merger.merge_datasets(original_data, new_data)
    print(f"合併結果: {len(merged_result)} 筆記錄")
    print(f"統計資訊: {merger.get_merge_statistics()}")
