"""
FinRL-DeepSeek 新聞爬取延伸專案整合測試
"""

import unittest
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

# ... 其他代碼保持不變，但注意以下變更 ...

# 在 TestCostCalculator 類中，所有的模型名稱都應該改為：
# 'gpt-4o-mini' -> 'gpt-4.1-mini'

# 例如：
class TestCostCalculator(unittest.TestCase):
    """測試成本計算器"""

    def test_llm_cost_calculation(self):
        """測試LLM成本計算"""
        input_text = "Test article content for sentiment analysis."
        output_text = "4"

        cost, detail = self.calculator.calculate_llm_cost(
            input_text, output_text, 'gpt-4.1-mini'  # 修改模型名稱
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
            model='gpt-4.1-mini'  # 修改模型名稱
        )

        self.assertIsInstance(estimate, dict)
        self.assertIn('total_estimated_cost_usd', estimate)
        self.assertIn('recommendations', estimate)

    def test_project_cost_estimation(self):
        """測試專案總成本估算"""
        project_cost = self.calculator.estimate_project_total_cost(
            articles_count=5000,
            avg_article_length=800,
            model='gpt-4.1-mini'  # 修改模型名稱
        )

        self.assertIsInstance(project_cost, dict)
        self.assertIn('project_summary', project_cost)
        self.assertIn('cost_breakdown', project_cost)
        self.assertIn('recommendations', project_cost)