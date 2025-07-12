"""
成本計算器模組
用於估算和追蹤各種 API 和服務的使用成本
最後更新：2025-07-12
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
        # ✅ 最新的 API 定價表（已與外部同步）
        self.pricing = {
            'openai': {
                # GPT-4.1 家族
                'gpt-4.1':        {'input': 0.002,  'output': 0.008},
                'gpt-4.1-mini':   {'input': 0.0004, 'output': 0.0016},
                'gpt-4.1-nano':   {'input': 0.0001, 'output': 0.0004},
                # o-系列 reasoning
                'o4-mini':        {'input': 0.0011, 'output': 0.0044},
                'o3':             {'input': 0.002,  'output': 0.008},
                # super-low-cost
                'gpt-4o-mini':    {'input': 0.00015, 'output': 0.0006},
            },
            'news_apis': {
                'newsapi': 0.0002,
                'alpha_vantage': 0.001,
                'polygon': 0.002
            }
            # ❌ 不再包含 infrastructure
        }

        # token 計算器
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

    # ------------------------------------------------------------------
    # 初始化 tokenizer
    # ------------------------------------------------------------------
    def _init_tokenizers(self):
        """初始化各種模型的 tokenizer"""
        model_names = [
            "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
            "o4-mini", "o3", "gpt-4o-mini"
        ]
        for name in model_names:
            try:
                self.tokenizers[name] = tiktoken.encoding_for_model(name)
            except Exception:
                pass

        # 通用備援
        if "default" not in self.tokenizers:
            self.tokenizers["default"] = tiktoken.get_encoding("cl100k_base")

    # ------------------------------------------------------------------
    # token 估算
    # ------------------------------------------------------------------
    def estimate_tokens(self, text: str, model: str = 'gpt-4.1-mini') -> int:
        """
        估算文本的 token 數量
        """
        if not text:
            return 0

        tokenizer = (
            self.tokenizers.get(model)
            or self.tokenizers.get("default")
        )
        try:
            return len(tokenizer.encode(text))
        except Exception:
            # 回退簡易估算（1 token ≈ 4 chars）
            return len(text) // 4

    # ------------------------------------------------------------------
    # LLM 成本計算
    # ------------------------------------------------------------------
    def calculate_llm_cost(
        self,
        input_text: str,
        output_text: str,
        model: str = 'gpt-4.1-mini'
    ) -> Tuple[float, Dict]:
        """
        計算 LLM 使用成本
        """
        input_tokens = self.estimate_tokens(input_text, model)
        output_tokens = self.estimate_tokens(output_text, model)

        # 取得定價；若未知則 fallback 到最便宜的 gpt-4.1-nano
        rates = (
            self.pricing['openai'].get(model)
            or self.pricing['openai']['gpt-4.1-nano']
        )

        input_cost = (input_tokens / 1000) * rates['input']
        output_cost = (output_tokens / 1000) * rates['output']
        total_cost = input_cost + output_cost

        # 累加到總表
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
        self.detailed_logs.append({'type': 'llm_processing', 'detail': cost_detail})

        return total_cost, cost_detail

    # ------------------------------------------------------------------
    # 批量 LLM 成本估算
    # ------------------------------------------------------------------
    def estimate_batch_llm_cost(
        self,
        articles_count: int,
        avg_article_length: int,
        model: str = 'gpt-4.1-mini'
    ) -> Dict:
        """
        估算批量 LLM 處理成本（sentiment + risk 兩次評分）
        """
        sample_input = "A" * avg_article_length
        sample_output = "3"  # 評分輸出通常很短

        single_cost, _ = self.calculate_llm_cost(sample_input, sample_output, model)
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

    # ------------------------------------------------------------------
    # 成本最佳化建議
    # ------------------------------------------------------------------
    def _get_cost_recommendations(self, estimated_cost: float) -> List[str]:
        """
        根據估算成本提供建議
        """
        rec = []

        if estimated_cost > 100:
            rec += [
                "考慮改用 gpt-4.1-nano 進一步降低成本",
                "實施文章長度上限（如 3,000 字符）",
                "先做關鍵詞過濾以減少不必要處理"
            ]
        if estimated_cost > 50:
            rec += [
                "分批處理以控制每日費用",
                "啟用成本監控與自動停止機制"
            ]
        if estimated_cost > 20:
            rec += [
                "縮短 prompt，減少冗餘上下文",
                "對重複內容做去重"
            ]

        rec.append(f"建議設定成本上限 ≈ ${estimated_cost * 1.2:.2f}")
        return rec

    # ------------------------------------------------------------------
    # 儲存與頻寬成本（可選）
    # ------------------------------------------------------------------
    def calculate_storage_cost(self, data_size_gb: float, months: int = 1) -> float:
        """
        計算資料儲存成本；若沒有 infrastructure 價格則返回 0
        """
        infra = self.pricing.get('infrastructure', {})
        rate = infra.get('aws_s3_storage', 0.0)
        total_cost = data_size_gb * rate * months

        self.cost_breakdown['data_storage'] += total_cost
        return total_cost

    def calculate_bandwidth_cost(self, transfer_gb: float) -> float:
        """
        計算網路傳輸成本；若沒有 infrastructure 價格則返回 0
        """
        infra = self.pricing.get('infrastructure', {})
        rate = infra.get('bandwidth', 0.0)
        cost = transfer_gb * rate

        self.cost_breakdown['network_transfer'] += cost
        return cost

    # ------------------------------------------------------------------
    # 整體專案成本估算
    # ------------------------------------------------------------------
    def estimate_project_total_cost(
        self,
        articles_count: int,
        avg_article_length: int = 1000,
        model: str = 'gpt-4.1-mini'
    ) -> Dict:
        """
        估算整個專案的總成本
        """
        llm_est = self.estimate_batch_llm_cost(articles_count, avg_article_length, model)
        storage_cost = self.calculate_storage_cost(1.0, 12)    # 1 GB, 12 個月
        bandwidth_cost = self.calculate_bandwidth_cost(5.0)     # 5 GB

        total_cost = llm_est['total_estimated_cost_usd'] + storage_cost + bandwidth_cost

        return {
            'project_summary': {
                'total_articles': articles_count,
                'model_used': model,
                'total_estimated_cost_usd': round(total_cost, 2)
            },
            'cost_breakdown': {
                'llm_processing': llm_est['total_estimated_cost_usd'],
                'data_storage': round(storage_cost, 2),
                'network_transfer': round(bandwidth_cost, 2),
                'other_overhead': 0.0
            },
            'cost_distribution_percent': {
                'llm_processing': round((llm_est['total_estimated_cost_usd'] / total_cost) * 100, 1),
                'infrastructure': round(((storage_cost + bandwidth_cost) / total_cost) * 100, 1)
            },
            'monthly_breakdown': {
                'initial_processing': llm_est['total_estimated_cost_usd'],
                'ongoing_storage': round(storage_cost / 12, 2),
                'maintenance': 0.0
            },
            'recommendations': llm_est['recommendations']
        }

    # ------------------------------------------------------------------
    # 成本總結與報告
    # ------------------------------------------------------------------
    def get_cost_summary(self) -> Dict:
        total = sum(self.cost_breakdown.values())
        return {
            'total_cost_usd': round(total, 4),
            'breakdown': {k: round(v, 4) for k, v in self.cost_breakdown.items()},
            'transaction_count': len(self.detailed_logs),
            'last_updated': datetime.now().isoformat()
        }

    def save_cost_report(self, output_path: str) -> None:
        report = {
            'report_metadata': {
                'generated_at': datetime.now().isoformat(),
                'report_version': '1.1'
            },
            'cost_summary': self.get_cost_summary(),
            'pricing_used': self.pricing,
            'detailed_transactions': self.detailed_logs
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)


# ----------------------------------------
# 範例執行（僅示範，部署時可刪除）
# ----------------------------------------
if __name__ == "__main__":
    calc = CostCalculator()
    project = calc.estimate_project_total_cost(
        articles_count=10_000,
        avg_article_length=1_000,
        model='gpt-4.1-mini'
    )
    print(json.dumps(project, indent=2, ensure_ascii=False))
