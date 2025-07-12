"""
FinRL-DeepSeek 新聞爬取延伸專案整合測試
"""

import unittest
import pandas as pd
import tempfile
import os
import json
from datetime import datetime, timedelta
import sys
from pathlib import Path

# 添加專案路徑
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.data_extraction.stock_list_parser import StockListParser
from src.data_processing.schema_formatter import SchemaFormatter
from src.data_processing.llm_scorer import LLMScorer
from src.integration.data_merger import DataMerger
from src.utils.cost_calculator import CostCalculator

class TestStockListParser(unittest.TestCase):
    """測試股票清單解析器"""
    
    def setUp(self):
        """設置測試環境"""
        self.config = {'data_path': './test_data'}
        self.parser = StockListParser(self.config)
        
        # 創建測試數據
        self.test_data = pd.DataFrame([
            {'Stock_symbol': 'AAPL', 'Date': '2023-01-01', 'Article_title': 'Apple News 1'},
            {'Stock_symbol': 'MSFT', 'Date': '2023-01-02', 'Article_title': 'Microsoft News 1'},
            {'Stock_symbol': 'GOOGL', 'Date': '2023-01-03', 'Article_title': 'Google News 1'},
        ])
        
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        self.test_data.to_csv(self.temp_file.name, index=False)
        self.temp_file.close()
    
    def tearDown(self):
        """清理測試環境"""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_extract_tickers(self):
        """測試股票代號提取"""
        tickers = self.parser.extract_89_tickers(self.temp_file.name)
        
        self.assertIsInstance(tickers, list)
        self.assertEqual(len(tickers), 3)
        self.assertIn('AAPL', tickers)
        self.assertIn('MSFT', tickers)
        self.assertIn('GOOGL', tickers)
    
    def test_validate_tickers(self):
        """測試股票代號驗證"""
        test_tickers = ['AAPL', 'MSFT', '', '123INVALID', 'VALID']
        valid_tickers = self.parser.validate_tickers(test_tickers)
        
        self.assertEqual(len(valid_tickers), 3)
        self.assertIn('AAPL', valid_tickers)
        self.assertIn('MSFT', valid_tickers)
        self.assertIn('VALID', valid_tickers)
        self.assertNotIn('', valid_tickers)
        self.assertNotIn('123INVALID', valid_tickers)

class TestSchemaFormatter(unittest.TestCase):
    """測試格式轉換器"""
    
    def setUp(self):
        """設置測試環境"""
        self.config = {
            'max_title_length': 200,
            'max_article_length': 5000,
            'summary_sentences': 2,
            'remove_html': True
        }
        self.formatter = SchemaFormatter(self.config)
        
        # 創建測試數據
        self.test_news = pd.DataFrame([
            {
                'Date': '2024-01-01',
                'Article_title': 'Apple Reports Strong Q4 Earnings',
                'Stock_symbol': 'AAPL',
                'Article': 'Apple Inc. announced its fourth quarter results today. The company reported revenue of $89.5 billion, up 1% year over year. This exceeded analyst expectations and showed strong performance across all product categories.',
                'Url': 'https://example.com/news/1',
                'Publisher': 'Financial News',
                'Author': 'John Doe'
            },
            {
                'Date': '2024-01-02',
                'Article_title': 'Microsoft Cloud Growth Accelerates',
                'Stock_symbol': 'MSFT',
                'Article': 'Microsoft Corporation today reported strong growth in its Azure cloud computing platform. The cloud division generated $24.3 billion in revenue, representing a 30% increase from the previous quarter.',
                'Url': 'https://example.com/news/2',
                'Publisher': 'Tech Today',
                'Author': 'Jane Smith'
            }
        ])
    
    def test_generate_summaries(self):
        """測試摘要生成"""
        test_text = self.test_news.iloc[0]['Article']
        summaries = self.formatter.generate_traditional_summaries(test_text)
        
        # 檢查所有四種摘要都生成了
        required_keys = ['Lsa_summary', 'Luhn_summary', 'Textrank_summary', 'Lexrank_summary']
        for key in required_keys:
            self.assertIn(key, summaries)
            self.assertIsInstance(summaries[key], str)
    
    def test_format_conversion(self):
        """測試格式轉換"""
        formatted_df = self.formatter.convert_to_standard_format(self.test_news)
        
        # 檢查必要欄位存在
        required_columns = [
            'Date', 'Article_title', 'Stock_symbol', 'Url', 'Publisher', 'Author',
            'Article', 'Lsa_summary', 'Luhn_summary', 'Textrank_summary', 'Lexrank_summary'
        ]
        
        for col in required_columns:
            self.assertIn(col, formatted_df.columns)
        
        # 檢查數據完整性
        self.assertEqual(len(formatted_df), len(self.test_news))
        self.assertEqual(formatted_df.iloc[0]['Stock_symbol'], 'AAPL')
        self.assertEqual(formatted_df.iloc[1]['Stock_symbol'], 'MSFT')
    
    def test_validation(self):
        """測試格式驗證"""
        formatted_df = self.formatter.convert_to_standard_format(self.test_news)
        validation_result = self.formatter.validate_format(formatted_df)
        
        self.assertIsInstance(validation_result, dict)
        self.assertIn('is_valid', validation_result)
        self.assertIn('statistics', validation_result)

class TestDataMerger(unittest.TestCase):
    """測試數據合併器"""
    
    def setUp(self):
        """設置測試環境"""
        self.config = {
            'overlap_strategy': 'prefer_new',
            'date_validation': True,
            'schema_validation': True,
            'deduplication': True
        }
        self.merger = DataMerger(self.config)
        
        # 創建測試數據集
        self.original_data = pd.DataFrame([
            {
                'Date': '2023-12-30',
                'Article_title': 'Year End Market Summary',
                'Stock_symbol': 'AAPL',
                'Article': 'Market summary content...',
                'Url': 'https://old.com/news/1',
                'Publisher': 'Old News',
                'Author': 'Old Author',
                'Lsa_summary': 'Old summary',
                'Luhn_summary': 'Old summary',
                'Textrank_summary': 'Old summary',
                'Lexrank_summary': 'Old summary',
                'sentiment_u': 4,
                'risk_q': 2
            }
        ])
        
        self.new_data = pd.DataFrame([
            {
                'Date': '2024-01-01',
                'Article_title': 'New Year Market Outlook',
                'Stock_symbol': 'AAPL',
                'Article': 'Market outlook content...',
                'Url': 'https://new.com/news/1',
                'Publisher': 'New News',
                'Author': 'New Author',
                'Lsa_summary': 'New summary',
                'Luhn_summary': 'New summary',
                'Textrank_summary': 'New summary',
                'Lexrank_summary': 'New summary',
                'sentiment_u': 3,
                'risk_q': 3
            }
        ])
    
    def test_schema_validation(self):
        """測試格式驗證"""
        validation_result = self.merger.validate_schema_compatibility(
            self.original_data, self.new_data
        )
        
        self.assertIsInstance(validation_result, dict)
        self.assertIn('missing_in_df1', validation_result)
        self.assertIn('missing_in_df2', validation_result)
    
    def test_data_preprocessing(self):
        """測試數據預處理"""
        processed_df = self.merger.preprocess_dataframe(self.new_data, "test_data")
        
        self.assertEqual(len(processed_df), 1)
        self.assertEqual(processed_df.iloc[0]['Stock_symbol'], 'AAPL')
    
    def test_merge_datasets(self):
        """測試數據合併"""
        merged_df = self.merger.merge_datasets(self.original_data, self.new_data)
        
        # 檢查合併結果
        self.assertEqual(len(merged_df), 2)  # 應該有兩筆記錄
        
        # 檢查必要欄位存在
        required_columns = [
            'Date', 'Article_title', 'Stock_symbol', 'sentiment_u', 'risk_q'
        ]
        for col in required_columns:
            self.assertIn(col, merged_df.columns)
        
        # 檢查統計資訊
        stats = self.merger.get_merge_statistics()
        self.assertEqual(stats['original_records'], 1)
        self.assertEqual(stats['new_records'], 1)
        self.assertEqual(stats['final_records'], 2)

class TestCostCalculator(unittest.TestCase):
    """測試成本計算器"""
    
    def setUp(self):
        """設置測試環境"""
        self.calculator = CostCalculator()
    
    def test_token_estimation(self):
        """測試token估算"""
        test_text = "This is a test article for token estimation."
        tokens = self.calculator.estimate_tokens(test_text)
        
        self.assertIsInstance(tokens, int)
        self.assertGreater(tokens, 0)
    
    def test_llm_cost_calculation(self):
        """測試LLM成本計算"""
        input_text = "Test article content for sentiment analysis."
        output_text = "4"
        
        cost, detail = self.calculator.calculate_llm_cost(
            input_text, output_text, 'gpt-4o-mini'
        )
        
        self.assertIsInstance(cost, float)
        self.assertGreater(cost, 0)
        self.assertIsInstance(detail, dict)
        self.assertIn('total_cost_usd', detail)
    
    def test_batch_cost_estimation(self):
        """測試批量成本估算"""
        estimate = self.calculator.estimate_batch_llm_cost(
            articles_count=1000,
            avg_article_length=500,
            model='gpt-4o-mini'
        )
        
        self.assertIsInstance(estimate, dict)
        self.assertIn('total_estimated_cost_usd', estimate)
        self.assertIn('recommendations', estimate)
    
    def test_project_cost_estimation(self):
        """測試專案總成本估算"""
        project_cost = self.calculator.estimate_project_total_cost(
            articles_count=5000,
            avg_article_length=800,
            model='gpt-4o-mini'
        )
        
        self.assertIsInstance(project_cost, dict)
        self.assertIn('project_summary', project_cost)
        self.assertIn('cost_breakdown', project_cost)
        self.assertIn('recommendations', project_cost)

class TestIntegrationWorkflow(unittest.TestCase):
    """測試完整工作流程整合"""
    
    def setUp(self):
        """設置測試環境"""
        # 創建臨時目錄
        self.temp_dir = tempfile.mkdtemp()
        
        # 準備測試配置
        self.config = {
            'stock_parser': {'data_path': self.temp_dir},
            'schema_formatter': {
                'max_title_length': 200,
                'max_article_length': 5000,
                'summary_sentences': 1,
                'remove_html': True
            },
            'data_merger': {
                'overlap_strategy': 'prefer_new',
                'deduplication': True
            }
        }
        
        # 創建測試數據文件
        self.create_test_data()
    
    def tearDown(self):
        """清理測試環境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_data(self):
        """創建測試數據"""
        # 模擬原始FinRL-DeepSeek數據
        original_data = pd.DataFrame([
            {
                'Date': '2023-12-31',
                'Article_title': 'Year End Summary',
                'Stock_symbol': 'AAPL',
                'Article': 'Year end market analysis content here.',
                'Url': 'https://example.com/old/1',
                'Publisher': 'Finance Daily',
                'Author': 'Market Analyst',
                'Lsa_summary': 'Year end summary',
                'Luhn_summary': 'Year end summary',
                'Textrank_summary': 'Year end summary',
                'Lexrank_summary': 'Year end summary',
                'sentiment_u': 3,
                'risk_q': 2
            },
            {
                'Date': '2023-12-30',
                'Article_title': 'Microsoft Cloud Growth',
                'Stock_symbol': 'MSFT',
                'Article': 'Microsoft cloud platform shows strong growth.',
                'Url': 'https://example.com/old/2',
                'Publisher': 'Tech News',
                'Author': 'Tech Reporter',
                'Lsa_summary': 'Cloud growth summary',
                'Luhn_summary': 'Cloud growth summary',
                'Textrank_summary': 'Cloud growth summary',
                'Lexrank_summary': 'Cloud growth summary',
                'sentiment_u': 4,
                'risk_q': 1
            }
        ])
        
        self.original_file = os.path.join(self.temp_dir, 'original_data.csv')
        original_data.to_csv(self.original_file, index=False)
        
        # 模擬新爬取的數據
        new_raw_data = pd.DataFrame([
            {
                'Date': '2024-01-01',
                'Article_title': 'Apple New Year Announcement',
                'Stock_symbol': 'AAPL',
                'Article': 'Apple announces new products for the new year.',
                'Url': 'https://example.com/new/1',
                'Publisher': 'Apple News',
                'Author': 'Apple Reporter'
            }
        ])
        
        self.new_raw_file = os.path.join(self.temp_dir, 'new_raw_data.csv')
        new_raw_data.to_csv(self.new_raw_file, index=False)
    
    def test_end_to_end_workflow(self):
        """測試端到端工作流程"""
        # 步驟1: 解析股票清單
        parser = StockListParser(self.config['stock_parser'])
        tickers = parser.extract_89_tickers(self.original_file)
        
        self.assertEqual(len(tickers), 2)
        self.assertIn('AAPL', tickers)
        self.assertIn('MSFT', tickers)
        
        # 步驟2: 載入和格式化新數據
        new_raw_df = pd.read_csv(self.new_raw_file)
        formatter = SchemaFormatter(self.config['schema_formatter'])
        formatted_df = formatter.convert_to_standard_format(new_raw_df)
        
        # 檢查格式化結果
        self.assertEqual(len(formatted_df), 1)
        self.assertIn('Lsa_summary', formatted_df.columns)
        
        # 步驟3: 數據合併
        original_df = pd.read_csv(self.original_file)
        merger = DataMerger(self.config['data_merger'])
        final_df = merger.merge_datasets(original_df, formatted_df)
        
        # 檢查最終結果
        self.assertEqual(len(final_df), 3)  # 原有2筆 + 新增1筆
        self.assertTrue(all(col in final_df.columns for col in [
            'Date', 'Article_title', 'Stock_symbol', 'sentiment_u', 'risk_q'
        ]))
        
        # 驗證日期排序
        final_df['Date'] = pd.to_datetime(final_df['Date'])
        self.assertTrue(final_df['Date'].is_monotonic_increasing)

if __name__ == '__main__':
    # 設置測試運行器
    unittest.main(verbosity=2)
