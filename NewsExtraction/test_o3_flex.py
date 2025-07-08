#!/usr/bin/env python3
"""
測試 o3 模型和 Flex Processing 是否正常工作
"""

import json
import time
import httpx
from openai import OpenAI
import argparse
import sys

def test_model(api_key: str, model: str = "o3", use_flex: bool = True):
    """測試指定模型和配置"""
    
    print(f"=== 測試 {model} 模型" + (" + Flex Processing" if use_flex else "") + " ===\n")
    
    # 配置客戶端
    client = OpenAI(
        api_key=api_key,
        timeout=httpx.Timeout(300.0, connect=60.0)  # 5分鐘超時用於測試
    )
    
    # 測試新聞文本
    test_news = {
        "symbol": "AAPL",
        "title": "Apple Reports Record Q4 2023 Earnings, Beats Analyst Expectations",
        "text": """Apple Inc. reported fourth-quarter earnings that exceeded Wall Street expectations, 
        driven by strong iPhone sales and growing services revenue. The company posted earnings 
        per share of $2.18, beating analyst estimates of $2.10. Revenue came in at $119.6 billion, 
        up 2% year-over-year. CEO Tim Cook highlighted the successful launch of the iPhone 15 
        series and continued growth in the services segment.""",
        "date": "2023-11-02"
    }
    
    # 測試 prompt (英文版本)
    test_prompt = """
    Analyze the following news and its impact on {symbol} stock:
    
    Title: {title}
    Content: {text}
    Date: {date}
    
    Please provide:
    1. Sentiment score (-1 to 1)
    2. Market impact prediction
    3. Key information extraction
    
    Return in JSON format.
    """
    
    print("1. 測試基本連接...")
    start_time = time.time()
    
    try:
        # 根據模型類型構建請求
        if model in ['o3', 'o4-mini']:
            # Reasoning 模型
            messages = [{
                "role": "user",
                "content": test_prompt.format(**test_news)
            }]
            
            params = {
                "model": model,
                "messages": messages,
                "reasoning_effort": "low",  # 測試使用 low effort
                "max_completion_tokens": 1000
            }
            
            if use_flex:
                params["service_tier"] = "flex"
                
        else:
            # 一般模型 (gpt-4.1, gpt-4.1-mini)
            messages = [{
                "role": "system",
                "content": "You are a financial analyst specializing in stock market news analysis."
            }, {
                "role": "user",
                "content": test_prompt.format(**test_news)
            }]
            
            params = {
                "model": model,
                "messages": messages,
                "temperature": 0,
                "max_tokens": 1000
            }
        
        # 發送請求
        response = client.chat.completions.create(**params)
        
        elapsed_time = time.time() - start_time
        print(f"✓ 成功！響應時間: {elapsed_time:.2f} 秒")
        
        # 解析響應
        content = response.choices[0].message.content
        print(f"\n2. 響應內容:")
        print("-" * 50)
        print(content)
        print("-" * 50)
        
        # 嘗試解析 JSON
        print("\n3. 測試 JSON 解析...")
        try:
            parsed = json.loads(content)
            print("✓ JSON 解析成功")
            print(f"解析結果: {json.dumps(parsed, indent=2, ensure_ascii=False)}")
        except json.JSONDecodeError as e:
            print(f"✗ JSON 解析失敗: {e}")
        
        # 顯示使用信息
        print(f"\n4. API 使用信息:")
        print(f"- 模型: {response.model}")
        print(f"- 輸入 tokens: {response.usage.prompt_tokens}")
        print(f"- 輸出 tokens: {response.usage.completion_tokens}")
        print(f"- 總 tokens: {response.usage.total_tokens}")
        
        # 計算預估成本（示例價格，需要根據實際定價調整）
        cost_per_1k_input = {
            "o3": 0.015,
            "o4-mini": 0.003,
            "gpt-4.1": 0.005,
            "gpt-4.1-mini": 0.00015
        }.get(model, 0.01)
        
        cost_per_1k_output = {
            "o3": 0.06,
            "o4-mini": 0.012,
            "gpt-4.1": 0.015,
            "gpt-4.1-mini": 0.0006
        }.get(model, 0.03)
        
        if use_flex and model in ['o3', 'o4-mini']:
            # Flex Processing 50% 折扣
            cost_per_1k_input *= 0.5
            cost_per_1k_output *= 0.5
        
        estimated_cost = (response.usage.prompt_tokens * cost_per_1k_input + 
                         response.usage.completion_tokens * cost_per_1k_output) / 1000
        print(f"- 預估成本: ${estimated_cost:.4f} (價格僅供參考)")
        
        print(f"\n✅ 測試成功！{model}" + (" + Flex Processing" if use_flex else "") + " 正常工作")
        return True
        
    except httpx.TimeoutException:
        print(f"\n✗ 超時錯誤 (等待 {time.time() - start_time:.0f} 秒)")
        if use_flex:
            print("Flex Processing 可能需要更長時間，請增加 timeout 設置")
        return False
        
    except Exception as e:
        print(f"\n✗ 錯誤: {type(e).__name__}: {e}")
        return False


def test_standard_comparison(api_key: str):
    """對比測試標準處理（使用 gpt-4.1-mini）"""
    print("\n\n=== 對比測試：標準處理 (gpt-4.1-mini) ===\n")
    
    client = OpenAI(api_key=api_key)
    
    try:
        start_time = time.time()
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{
                "role": "user",
                "content": "Analyze AAPL stock briefly: bullish or bearish?"
            }],
            temperature=0,
            max_tokens=100
        )
        
        elapsed_time = time.time() - start_time
        print(f"✓ 標準處理響應時間: {elapsed_time:.2f} 秒")
        print(f"內容預覽: {response.choices[0].message.content[:100]}...")
        
    except Exception as e:
        print(f"✗ 標準處理測試失敗: {e}")


def main():
    parser = argparse.ArgumentParser(description='測試 o3 + Flex Processing')
    parser.add_argument('--api-key', type=str, required=True, help='OpenAI API Key')
    parser.add_argument('--compare', action='store_true', help='同時測試標準處理進行對比')
    args = parser.parse_args()
    
    print("開始測試 o3 模型與 Flex Processing...\n")
    
    # 主要測試
    success = test_o3_flex(args.api_key)
    
    # 對比測試（可選）
    if args.compare:
        test_standard_comparison(args.api_key)
    
    # 結果總結
    print("\n" + "=" * 60)
    if success:
        print("✅ 所有測試通過！您可以開始使用主腳本處理數據了。")
        print("\n建議運行命令：")
        print(f"python finrl_news_pipeline.py --openai-key {args.api_key} --model o3 --use-flex")
    else:
        print("❌ 測試失敗，請檢查：")
        print("1. API Key 是否正確")
        print("2. 是否有 o3 模型的訪問權限")
        print("3. 網絡連接是否正常")
        print("4. OpenAI 服務狀態")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
