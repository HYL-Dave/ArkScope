#!/usr/bin/env python3
"""
快速檢查專案設置是否正確
"""

import sys
import os
import json
from pathlib import Path


def check_imports():
    """檢查關鍵模組是否可以正確 import"""
    print("🔍 檢查模組 import...")

    try:
        # 添加專案路徑
        project_root = Path(__file__).parent
        sys.path.append(str(project_root))

        # 檢查關鍵模組
        from src.data_extraction.stock_list_parser import StockListParser
        print("✅ StockListParser 載入成功")

        from src.data_extraction.finnlp_crawler import FinNLPCrawler
        print("✅ FinNLPCrawler 載入成功")

        from src.data_processing.llm_scorer import LLMScorer
        print("✅ LLMScorer 載入成功")

        from src.data_processing.schema_formatter import SchemaFormatter
        print("✅ SchemaFormatter 載入成功")

        from src.integration.data_merger import DataMerger
        print("✅ DataMerger 載入成功")

        from src.utils.logger_util import setup_logger
        print("✅ logger_util 載入成功")

        from src.utils.cost_calculator import CostCalculator
        print("✅ CostCalculator 載入成功")

        return True

    except ImportError as e:
        print(f"❌ Import 錯誤: {e}")
        return False


def check_config():
    """檢查配置文件"""
    print("\n🔍 檢查配置文件...")

    config_path = Path("config/config_template.json")
    if not config_path.exists():
        print(f"❌ 找不到配置模板: {config_path}")
        return False

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 檢查關鍵配置
        model = config.get('llm_scorer', {}).get('model', '')
        if model == 'gpt-4.1-mini':
            print(f"✅ LLM 模型設置正確: {model}")
        else:
            print(f"⚠️ LLM 模型設置可能有誤: {model}")

        return True

    except Exception as e:
        print(f"❌ 配置文件錯誤: {e}")
        return False


def check_directories():
    """檢查必要目錄結構"""
    print("\n🔍 檢查目錄結構...")

    required_dirs = [
        'src/data_extraction',
        'src/data_processing',
        'src/integration',
        'src/utils',
        'scripts',
        'config',
        'tests'
    ]

    all_exist = True
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"✅ {dir_path} 存在")
        else:
            print(f"❌ {dir_path} 不存在")
            all_exist = False

    return all_exist


def check_dependencies():
    """檢查關鍵依賴"""
    print("\n🔍 檢查關鍵依賴...")

    try:
        import pandas
        print(f"✅ pandas {pandas.__version__}")

        import openai
        print(f"✅ openai {openai.__version__}")

        import tiktoken
        print("✅ tiktoken 已安裝")

        import sumy
        print("✅ sumy 已安裝")

        return True

    except ImportError as e:
        print(f"❌ 缺少依賴: {e}")
        print("請執行: pip install -r requirements.txt")
        return False


def check_model_pricing():
    """檢查模型定價一致性"""
    print("\n🔍 檢查模型定價設置...")

    try:
        from src.utils.cost_calculator import CostCalculator
        calc = CostCalculator()

        models = ['gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano']
        for model in models:
            if model in calc.pricing['openai']:
                price = calc.pricing['openai'][model]
                print(f"✅ {model}: input=${price['input']}/1K, output=${price['output']}/1K")
            else:
                print(f"⚠️ {model} 未找到定價資訊")

        return True

    except Exception as e:
        print(f"❌ 檢查定價時出錯: {e}")
        return False


def main():
    """執行所有檢查"""
    print("🚀 開始檢查 FinRL-DeepSeek 專案設置...\n")

    checks = [
        ("目錄結構", check_directories),
        ("Python 依賴", check_dependencies),
        ("模組 Import", check_imports),
        ("配置文件", check_config),
        ("模型定價", check_model_pricing)
    ]

    all_passed = True
    for name, check_func in checks:
        if not check_func():
            all_passed = False
        print()  # 空行分隔

    if all_passed:
        print("✅ 所有檢查通過！專案設置正確。")
        print("\n下一步：")
        print("1. 複製 config/config_template.json 為 config/config.json")
        print("2. 在 config.json 中填入您的 OpenAI API 密鑰")
        print("3. 執行: python scripts/run_full_pipeline.py --config config/config.json --start-date 2024-01-01")
    else:
        print("❌ 部分檢查失敗，請修正問題後重試。")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())