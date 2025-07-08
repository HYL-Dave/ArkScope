#!/usr/bin/env python3
"""快速測試腳本 - 驗證環境配置"""

import os
import sys

def test_imports():
    """測試所有必要的導入"""
    print("測試 Python 套件導入...")
    
    required_packages = [
        "datasets", "duckdb", "pyarrow", "pandas", 
        "numpy", "requests", "tqdm", "openai", "httpx"
    ]
    
    failed = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package}")
            failed.append(package)
    
    if failed:
        print(f"\n缺少套件: {', '.join(failed)}")
        print("請運行: pip install -r requirements.txt")
        return False
    return True

def test_api_key():
    """測試 API Key 設置"""
    print("\n測試 API Key 設置...")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        print("  ✓ OPENAI_API_KEY 已設置")
        return True
    else:
        print("  ✗ OPENAI_API_KEY 未設置")
        print("  請設置: export OPENAI_API_KEY='your-key'")
        return False

def main():
    print("FinRL 新聞處理系統 - 環境測試")
    print("=" * 40)
    
    imports_ok = test_imports()
    api_ok = test_api_key()
    
    print("\n" + "=" * 40)
    if imports_ok and api_ok:
        print("✅ 環境配置完成！")
        print("\n下一步：")
        print("1. 測試模型: python test_o3_flex.py --api-key $OPENAI_API_KEY --model o4-mini")
        print("2. 查看成本: python cost_calculator.py --compare")
    else:
        print("❌ 請先完成環境配置")
        
if __name__ == "__main__":
    main()
