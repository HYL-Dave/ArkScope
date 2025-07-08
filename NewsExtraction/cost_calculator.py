#!/usr/bin/env python3
"""
FinRL 新聞處理成本計算器
幫助估算不同模型和配置的處理成本
"""

import argparse
from typing import Dict, Tuple

# 模型定價（美元/1K tokens）
# 注意：這些是示例價格，請根據實際 OpenAI 定價更新
PRICING = {
    "o3": {
        "input": 0.015,
        "output": 0.060,
        "flex_discount": 0.5  # Flex Processing 50% 折扣
    },
    "o4-mini": {
        "input": 0.003,
        "output": 0.012,
        "flex_discount": 0.5
    },
    "gpt-4.1": {
        "input": 0.005,
        "output": 0.015,
        "flex_discount": 1.0  # 不支援 Flex
    },
    "gpt-4.1-mini": {
        "input": 0.00015,
        "output": 0.0006,
        "flex_discount": 1.0  # 不支援 Flex
    }
}

# 平均 token 使用量估算
TOKEN_USAGE = {
    "simple_analysis": {
        "input": 500,   # 新聞 + prompt
        "output": 200   # JSON 響應
    },
    "standard_analysis": {
        "input": 800,
        "output": 500
    },
    "deep_analysis": {
        "input": 1200,
        "output": 1000
    }
}

# Reasoning effort 對 token 使用的影響
EFFORT_MULTIPLIER = {
    "low": 0.8,
    "medium": 1.0,
    "high": 1.5
}


def calculate_cost(
    model: str,
    num_news: int,
    analysis_type: str = "standard_analysis",
    use_flex: bool = True,
    reasoning_effort: str = "medium"
) -> Dict[str, float]:
    """計算處理成本"""
    
    if model not in PRICING:
        raise ValueError(f"未知模型: {model}")
    
    # 獲取基礎 token 使用量
    tokens = TOKEN_USAGE[analysis_type]
    input_tokens = tokens["input"]
    output_tokens = tokens["output"]
    
    # 應用 reasoning effort 倍數（僅對 reasoning 模型）
    if model in ["o3", "o4-mini"]:
        multiplier = EFFORT_MULTIPLIER[reasoning_effort]
        output_tokens = int(output_tokens * multiplier)
    
    # 計算總 tokens
    total_input_tokens = input_tokens * num_news
    total_output_tokens = output_tokens * num_news
    
    # 獲取價格
    prices = PRICING[model]
    input_price = prices["input"]
    output_price = prices["output"]
    
    # 應用 Flex 折扣
    if use_flex and model in ["o3", "o4-mini"]:
        discount = prices["flex_discount"]
        input_price *= discount
        output_price *= discount
    
    # 計算成本
    input_cost = (total_input_tokens / 1000) * input_price
    output_cost = (total_output_tokens / 1000) * output_price
    total_cost = input_cost + output_cost
    
    return {
        "model": model,
        "num_news": num_news,
        "analysis_type": analysis_type,
        "use_flex": use_flex,
        "reasoning_effort": reasoning_effort,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "cost_per_news": total_cost / num_news
    }


def print_cost_report(result: Dict[str, float]):
    """打印成本報告"""
    print(f"\n{'='*50}")
    print(f"成本估算報告")
    print(f"{'='*50}")
    print(f"模型: {result['model']}" + 
          (" + Flex" if result['use_flex'] and result['model'] in ['o3', 'o4-mini'] else ""))
    print(f"新聞數量: {result['num_news']:,}")
    print(f"分析類型: {result['analysis_type']}")
    if result['model'] in ['o3', 'o4-mini']:
        print(f"Reasoning Effort: {result['reasoning_effort']}")
    print(f"\nToken 使用:")
    print(f"  輸入: {result['total_input_tokens']:,} tokens")
    print(f"  輸出: {result['total_output_tokens']:,} tokens")
    print(f"\n成本明細:")
    print(f"  輸入成本: ${result['input_cost']:.4f}")
    print(f"  輸出成本: ${result['output_cost']:.4f}")
    print(f"  總成本: ${result['total_cost']:.4f}")
    print(f"  每條新聞: ${result['cost_per_news']:.4f}")
    print(f"{'='*50}\n")


def compare_models(num_news: int, analysis_type: str = "standard_analysis"):
    """比較不同模型的成本"""
    print(f"\n{'='*60}")
    print(f"模型成本比較 - {num_news:,} 條新聞 ({analysis_type})")
    print(f"{'='*60}")
    print(f"{'模型':<15} {'配置':<15} {'總成本':<12} {'每條新聞':<12} {'相對成本'}")
    print(f"{'-'*60}")
    
    results = []
    
    # 測試不同配置
    configs = [
        ("o3", True, "high"),
        ("o3", True, "medium"),
        ("o3", False, "medium"),
        ("o4-mini", True, "medium"),
        ("o4-mini", False, "medium"),
        ("gpt-4.1", False, "medium"),
        ("gpt-4.1-mini", False, "medium"),
    ]
    
    for model, use_flex, effort in configs:
        result = calculate_cost(model, num_news, analysis_type, use_flex, effort)
        results.append(result)
    
    # 找出最低成本作為基準
    min_cost = min(r['total_cost'] for r in results)
    
    # 打印結果
    for r in results:
        config = ""
        if r['model'] in ['o3', 'o4-mini']:
            config = f"Flex={r['use_flex']}, {r['reasoning_effort']}"
        else:
            config = "Standard"
        
        relative_cost = r['total_cost'] / min_cost
        
        print(f"{r['model']:<15} {config:<15} ${r['total_cost']:<11.2f} "
              f"${r['cost_per_news']:<11.4f} {relative_cost:<.1f}x")
    
    print(f"{'-'*60}")
    print(f"* 最低成本: ${min_cost:.2f} ({min(results, key=lambda x: x['total_cost'])['model']})")
    print(f"* 價格為估算值，實際價格請參考 OpenAI 官方定價")


def estimate_dataset_cost(total_news: int = 50000, sample_rate: float = 0.01):
    """估算處理整個數據集的成本"""
    sample_size = int(total_news * sample_rate)
    
    print(f"\n{'='*60}")
    print(f"數據集處理成本估算")
    print(f"{'='*60}")
    print(f"總新聞數: {total_news:,}")
    print(f"抽樣率: {sample_rate:.1%}")
    print(f"處理數量: {sample_size:,}")
    print(f"\n建議方案:")
    
    # 方案 1：經濟型
    print(f"\n1. 經濟型方案 (gpt-4.1-mini)")
    cost1 = calculate_cost("gpt-4.1-mini", sample_size, "simple_analysis", False)
    print(f"   - 總成本: ${cost1['total_cost']:.2f}")
    print(f"   - 適用於: 初步篩選、簡單分類")
    
    # 方案 2：平衡型
    print(f"\n2. 平衡型方案 (o4-mini + Flex)")
    cost2 = calculate_cost("o4-mini", sample_size, "standard_analysis", True)
    print(f"   - 總成本: ${cost2['total_cost']:.2f}")
    print(f"   - 適用於: 標準質量分析、研究用途")
    
    # 方案 3：高質量型
    print(f"\n3. 高質量方案 (o3 + Flex, medium effort)")
    cost3 = calculate_cost("o3", sample_size, "deep_analysis", True, "medium")
    print(f"   - 總成本: ${cost3['total_cost']:.2f}")
    print(f"   - 適用於: 深度分析、發現複雜模式")
    
    # 方案 4：混合型
    print(f"\n4. 混合型方案 (兩階段處理)")
    # 階段 1：用 gpt-4.1-mini 處理所有
    stage1_size = sample_size
    stage1_cost = calculate_cost("gpt-4.1-mini", stage1_size, "simple_analysis", False)
    # 階段 2：用 o3 處理 20% 重要新聞
    stage2_size = int(sample_size * 0.2)
    stage2_cost = calculate_cost("o3", stage2_size, "deep_analysis", True, "high")
    total_hybrid = stage1_cost['total_cost'] + stage2_cost['total_cost']
    print(f"   - 階段 1 (gpt-4.1-mini 篩選): ${stage1_cost['total_cost']:.2f}")
    print(f"   - 階段 2 (o3 深度分析 20%): ${stage2_cost['total_cost']:.2f}")
    print(f"   - 總成本: ${total_hybrid:.2f}")
    print(f"   - 適用於: 大規模處理 + 重點深度分析")


def main():
    parser = argparse.ArgumentParser(description='FinRL 新聞處理成本計算器')
    parser.add_argument('--model', type=str, 
                       choices=['o3', 'o4-mini', 'gpt-4.1', 'gpt-4.1-mini'],
                       help='指定模型')
    parser.add_argument('--num-news', type=int, default=1000,
                       help='新聞數量 (預設: 1000)')
    parser.add_argument('--analysis-type', type=str, 
                       choices=['simple_analysis', 'standard_analysis', 'deep_analysis'],
                       default='standard_analysis',
                       help='分析類型')
    parser.add_argument('--use-flex', action='store_true',
                       help='使用 Flex Processing')
    parser.add_argument('--reasoning-effort', type=str,
                       choices=['low', 'medium', 'high'],
                       default='medium',
                       help='Reasoning effort (僅對 o3/o1 有效)')
    parser.add_argument('--compare', action='store_true',
                       help='比較所有模型')
    parser.add_argument('--estimate-dataset', action='store_true',
                       help='估算整個數據集的成本')
    
    args = parser.parse_args()
    
    if args.estimate_dataset:
        estimate_dataset_cost()
    elif args.compare:
        compare_models(args.num_news, args.analysis_type)
    elif args.model:
        result = calculate_cost(
            args.model,
            args.num_news,
            args.analysis_type,
            args.use_flex,
            args.reasoning_effort
        )
        print_cost_report(result)
    else:
        # 預設：顯示常見場景
        print("FinRL 新聞處理成本計算器")
        print("\n常見場景成本估算：")
        
        scenarios = [
            ("快速測試", "gpt-4.1-mini", 100, "simple_analysis", False, "medium"),
            ("標準處理", "o4-mini", 1000, "standard_analysis", True, "medium"),
            ("深度分析", "o3", 500, "deep_analysis", True, "high"),
        ]
        
        for name, model, num, analysis, flex, effort in scenarios:
            result = calculate_cost(model, num, analysis, flex, effort)
            print(f"\n{name}:")
            print(f"  配置: {model}" + (" + Flex" if flex and model in ['o3', 'o4-mini'] else ""))
            print(f"  數量: {num} 條新聞")
            print(f"  成本: ${result['total_cost']:.2f} (${result['cost_per_news']:.4f}/條)")
        
        print("\n運行 'python cost_calculator.py --help' 查看更多選項")


if __name__ == "__main__":
    main()
