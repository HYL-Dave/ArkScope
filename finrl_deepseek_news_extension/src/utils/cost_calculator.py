"""
成本計算器模組
用於估算和追蹤各種API和服務的使用成本
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import tiktoken

class CostCalculator:
    """
    綜合成本計算器
    """
    
    def __init__(self):
        """初始化成本計算器"""
        # 最新的API定價表 (2025年1月)
        self.pricing = {
            'openai': {
                # GPT-4.1 家族
                'gpt-4.1': {
                    'input': 0.002,
                    'output': 0.008
                },
                'gpt-4.1-mini': {
                    'input': 0.0004,
                    'output': 0.0016
                },
                'gpt-4.1-nano': {  # ← 新增
                    'input': 0.0001,  # per 1K tokens
                    'output': 0.0004
                },
                # o-系列 reasoning
                'o4-mini': {
                    'input': 0.0011,
                    'output': 0.0044
                },
                'o3': {
                    'input': 0.002,
                    'output': 0.008
                },
                # 仍保留 4o-mini 以兼顧超低價
                'gpt-4o-mini': {
                    'input': 0.00015,
                    'output': 0.0006
                }
            },
            'news_apis': {
                'newsapi': 0.0002,
                'alpha_vantage': 0.001,
                'polygon': 0.002
            }
        }

        # token計算器
        self.tokenizers = {}
        self._init_tokenizers()
        
        # 成本追蹤
        self.cost_breakdown = {
            'llm_processing': 0.0,
            'data_storage': 0.0,
            'network_transfer': 0.0,
            'compute_resources': 0.0,
            'external_apis': 0.0
        }
        
        self.detailed_logs = []
    
    def _init_tokenizers(self):
        """初始化各種模型的tokenizer"""
        try:
            self.tokenizers['gpt-4'] = tiktoken.encoding_for_model("gpt-4")
            self.tokenizers['gpt-3.5-turbo'] = tiktoken.encoding_for_model("gpt-3.5-turbo")
        except:
            # 回退到通用tokenizer
            self.tokenizers['default'] = tiktoken.get_encoding("cl100k_base")
    
    def estimate_tokens(self, text: str, model: str = 'gpt-4o') -> int:
        """
        估算文本的token數量
        
        Args:
            text: 要估算的文本
            model: 模型名稱
            
        Returns:
            int: 估算的token數量
        """
        if not text:
            return 0
        
        # 選擇合適的tokenizer
        if model in self.tokenizers:
            tokenizer = self.tokenizers[model]
        elif 'gpt-4' in model and 'gpt-4' in self.tokenizers:
            tokenizer = self.tokenizers['gpt-4']
        elif 'gpt-3.5' in model and 'gpt-3.5-turbo' in self.tokenizers:
            tokenizer = self.tokenizers['gpt-3.5-turbo']
        else:
            tokenizer = self.tokenizers.get('default')
        
        if tokenizer:
            try:
                return len(tokenizer.encode(text))
            except:
                pass
        
        # 回退到簡單估算 (1 token ≈ 4 characters)
        return len(text) // 4
    
    def calculate_llm_cost(self, input_text: str, output_text: str, 
                          model: str = 'gpt-4o') -> Tuple[float, Dict]:
        """
        計算LLM使用成本
        
        Args:
            input_text: 輸入文本
            output_text: 輸出文本
            model: 模型名稱
            
        Returns:
            Tuple[float, Dict]: (總成本, 詳細分解)
        """
        input_tokens = self.estimate_tokens(input_text, model)
        output_tokens = self.estimate_tokens(output_text, model)
        
        # 獲取定價
        if model in self.pricing['openai']:
            rates = self.pricing['openai'][model]
        else:
            # 默認使用gpt-4o定價
            rates = self.pricing['openai']['gpt-4o']
        
        input_cost = (input_tokens / 1000) * rates['input']
        output_cost = (output_tokens / 1000) * rates['output']
        total_cost = input_cost + output_cost
        
        # 記錄成本
        self.cost_breakdown['llm_processing'] += total_cost
        
        cost_detail = {
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'input_cost_usd': round(input_cost, 6),
            'output_cost_usd': round(output_cost, 6),
            'total_cost_usd': round(total_cost, 6),
            'timestamp': datetime.now().isoformat()
        }
        
        self.detailed_logs.append({
            'type': 'llm_processing',
            'detail': cost_detail
        })
        
        return total_cost, cost_detail
    
    def estimate_batch_llm_cost(self, articles_count: int, avg_article_length: int,
                               model: str = 'gpt-4o') -> Dict:
        """
        估算批量LLM處理成本
        
        Args:
            articles_count: 文章數量
            avg_article_length: 平均文章長度（字符）
            model: 模型名稱
            
        Returns:
            Dict: 成本估算詳情
        """
        # 估算單篇文章的處理成本
        sample_input = "A" * avg_article_length  # 模擬文章
        sample_output = "3"  # 評分輸出通常很短
        
        single_cost, _ = self.calculate_llm_cost(sample_input, sample_output, model)
        
        # 計算總成本（sentiment + risk 兩次評分）
        total_cost = single_cost * 2 * articles_count
        
        return {
            'total_articles': articles_count,
            'avg_article_length': avg_article_length,
            'model': model,
            'cost_per_article_usd': round(single_cost * 2, 6),
            'total_estimated_cost_usd': round(total_cost, 2),
            'cost_breakdown': {
                'sentiment_scoring': round(single_cost * articles_count, 2),
                'risk_scoring': round(single_cost * articles_count, 2)
            },
            'recommendations': self._get_cost_recommendations(total_cost)
        }
    
    def _get_cost_recommendations(self, estimated_cost: float) -> List[str]:
        """
        根據估算成本提供建議
        
        Args:
            estimated_cost: 估算成本
            
        Returns:
            List[str]: 建議清單
        """
        recommendations = []
        
        if estimated_cost > 100:
            recommendations.append("考慮使用gpt-4o-mini模型以降低成本")
            recommendations.append("實施文章長度限制（例如最多3000字符）")
            recommendations.append("添加關鍵字預篩選以減少不相關文章的處理")
        
        if estimated_cost > 50:
            recommendations.append("考慮分批處理以控制每日成本")
            recommendations.append("實施成本監控和自動停止機制")
        
        if estimated_cost > 20:
            recommendations.append("考慮使用較短的prompt模板")
            recommendations.append("對重複內容實施去重處理")
        
        recommendations.append(f"建議設置成本上限為 ${estimated_cost * 1.2:.2f}")
        
        return recommendations
    
    def calculate_storage_cost(self, data_size_gb: float, months: int = 1) -> float:
        """
        計算數據儲存成本
        
        Args:
            data_size_gb: 數據大小（GB）
            months: 儲存月份數
            
        Returns:
            float: 儲存成本
        """
        monthly_cost = data_size_gb * self.pricing['infrastructure']['aws_s3_storage']
        total_cost = monthly_cost * months
        
        self.cost_breakdown['data_storage'] += total_cost
        
        return total_cost
    
    def calculate_bandwidth_cost(self, transfer_gb: float) -> float:
        """
        計算網路傳輸成本
        
        Args:
            transfer_gb: 傳輸數據量（GB）
            
        Returns:
            float: 傳輸成本
        """
        cost = transfer_gb * self.pricing['infrastructure']['bandwidth']
        self.cost_breakdown['network_transfer'] += cost
        
        return cost
    
    def estimate_project_total_cost(self, articles_count: int, 
                                  avg_article_length: int = 1000,
                                  model: str = 'gpt-4o-mini') -> Dict:
        """
        估算整個專案的總成本
        
        Args:
            articles_count: 預計處理的文章數量
            avg_article_length: 平均文章長度
            model: 使用的LLM模型
            
        Returns:
            Dict: 總成本估算
        """
        # LLM處理成本
        llm_estimate = self.estimate_batch_llm_cost(articles_count, avg_article_length, model)
        
        # 數據儲存成本（假設最終數據集約1GB，儲存12個月）
        storage_cost = self.calculate_storage_cost(1.0, 12)
        
        # 網路傳輸成本（假設總傳輸量5GB）
        bandwidth_cost = self.calculate_bandwidth_cost(5.0)
        
        # 計算總成本
        total_cost = (llm_estimate['total_estimated_cost_usd'] + 
                     storage_cost + bandwidth_cost)
        
        return {
            'project_summary': {
                'total_articles': articles_count,
                'model_used': model,
                'total_estimated_cost_usd': round(total_cost, 2)
            },
            'cost_breakdown': {
                'llm_processing': llm_estimate['total_estimated_cost_usd'],
                'data_storage': round(storage_cost, 2),
                'network_transfer': round(bandwidth_cost, 2),
                'other_overhead': 0.0
            },
            'cost_distribution_percent': {
                'llm_processing': round((llm_estimate['total_estimated_cost_usd'] / total_cost) * 100, 1),
                'infrastructure': round(((storage_cost + bandwidth_cost) / total_cost) * 100, 1)
            },
            'monthly_breakdown': {
                'initial_processing': llm_estimate['total_estimated_cost_usd'],
                'ongoing_storage': round(storage_cost / 12, 2),
                'maintenance': 0.0
            },
            'recommendations': llm_estimate['recommendations']
        }
    
    def get_cost_summary(self) -> Dict:
        """
        獲取目前的成本總結
        
        Returns:
            Dict: 成本總結
        """
        total_cost = sum(self.cost_breakdown.values())
        
        return {
            'total_cost_usd': round(total_cost, 4),
            'breakdown': {k: round(v, 4) for k, v in self.cost_breakdown.items()},
            'transaction_count': len(self.detailed_logs),
            'last_updated': datetime.now().isoformat()
        }
    
    def save_cost_report(self, output_path: str) -> None:
        """
        儲存詳細的成本報告
        
        Args:
            output_path: 輸出檔案路徑
        """
        report = {
            'report_metadata': {
                'generated_at': datetime.now().isoformat(),
                'report_version': '1.0'
            },
            'cost_summary': self.get_cost_summary(),
            'pricing_used': self.pricing,
            'detailed_transactions': self.detailed_logs
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    # 使用範例
    calculator = CostCalculator()
    
    # 估算處理10000篇文章的成本
    project_cost = calculator.estimate_project_total_cost(
        articles_count=10000,
        avg_article_length=1000,
        model='gpt-4o-mini'
    )
    
    print("專案成本估算:")
    print(json.dumps(project_cost, indent=2, ensure_ascii=False))
    
    # 模擬一些實際的LLM調用
    for i in range(5):
        sample_article = f"This is a sample financial article number {i+1}. " * 50
        sample_response = "4"
        
        cost, detail = calculator.calculate_llm_cost(
            sample_article, sample_response, 'gpt-4o-mini'
        )
        
        print(f"文章 {i+1} 處理成本: ${cost:.6f}")
    
    # 顯示總成本摘要
    print("\n總成本摘要:")
    print(json.dumps(calculator.get_cost_summary(), indent=2, ensure_ascii=False))
