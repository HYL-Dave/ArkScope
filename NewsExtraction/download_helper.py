#!/usr/bin/env python3
"""
FinRL 新聞處理系統 - 檔案下載輔助腳本
幫助整理和檢查所需檔案
"""

import os
import json
from datetime import datetime

# 所有需要的檔案清單
REQUIRED_FILES = {
    "核心腳本": [
        "finrl_news_pipeline.py",
        "quality_analysis_script.py", 
        "test_o3_flex.py",
        "cost_calculator.py"
    ],
    "配置檔案": [
        "env_config.sh",
        "requirements.txt",
        "quickstart.sh"
    ],
    "文檔": [
        "readme_o3.md",
        "o3-flex-guide.md",
        "model-selection-guide.md",
        "project-handover.md"
    ]
}

def check_files():
    """檢查檔案是否都已下載"""
    print("檢查檔案完整性...\n")
    
    missing_files = []
    present_files = []
    
    for category, files in REQUIRED_FILES.items():
        print(f"{category}:")
        for file in files:
            if os.path.exists(file):
                print(f"  ✓ {file}")
                present_files.append(file)
            else:
                print(f"  ✗ {file} (缺少)")
                missing_files.append(file)
        print()
    
    return present_files, missing_files

def create_project_info():
    """創建專案資訊檔案"""
    project_info = {
        "project_name": "FinRL 新聞數據處理系統",
        "version": "2.0.0",
        "last_updated": datetime.now().isoformat(),
        "models_supported": ["o3", "o4-mini", "gpt-4.1", "gpt-4.1-mini"],
        "key_features": [
            "Reasoning 模型支援 (o3, o4-mini)",
            "Flex Processing 整合",
            "多模型混合策略",
            "成本優化工具",
            "深度質量分析"
        ],
        "next_steps": [
            "測試模型配置: python test_o3_flex.py --api-key YOUR_KEY --model o3",
            "估算成本: python cost_calculator.py --compare",
            "運行處理: python finrl_news_pipeline.py --model o4-mini --use-flex"
        ],
        "important_notes": [
            "Reasoning 模型使用 reasoning_effort 而非 temperature",
            "只有 reasoning 模型支援 Flex Processing",
            "Flex Processing 可節省 50% 成本但響應較慢"
        ]
    }
    
    with open("project_info.json", "w", encoding="utf-8") as f:
        json.dump(project_info, f, indent=2, ensure_ascii=False)
    
    print("已創建 project_info.json")

def create_quick_test():
    """創建快速測試腳本"""
    test_script = '''#!/usr/bin/env python3
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
        print(f"\\n缺少套件: {', '.join(failed)}")
        print("請運行: pip install -r requirements.txt")
        return False
    return True

def test_api_key():
    """測試 API Key 設置"""
    print("\\n測試 API Key 設置...")
    
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
    
    print("\\n" + "=" * 40)
    if imports_ok and api_ok:
        print("✅ 環境配置完成！")
        print("\\n下一步：")
        print("1. 測試模型: python test_o3_flex.py --api-key $OPENAI_API_KEY --model o4-mini")
        print("2. 查看成本: python cost_calculator.py --compare")
    else:
        print("❌ 請先完成環境配置")
        
if __name__ == "__main__":
    main()
'''
    
    with open("quick_test.py", "w") as f:
        f.write(test_script)
    
    os.chmod("quick_test.py", 0o755)
    print("已創建 quick_test.py")

def main():
    print("FinRL 新聞處理系統 - 檔案檢查工具")
    print("=" * 50)
    
    # 檢查檔案
    present, missing = check_files()
    
    # 創建輔助檔案
    print("創建輔助檔案...")
    create_project_info()
    create_quick_test()
    
    # 總結
    print("\n" + "=" * 50)
    print(f"檔案統計：")
    print(f"  已下載: {len(present)} 個")
    print(f"  缺少: {len(missing)} 個")
    
    if missing:
        print(f"\n請確保下載以下檔案：")
        for file in missing:
            print(f"  - {file}")
    else:
        print("\n✅ 所有檔案都已就緒！")
        print("\n建議下一步：")
        print("1. 運行環境測試: python quick_test.py")
        print("2. 查看專案資訊: cat project_info.json")
        print("3. 開始使用: ./quickstart.sh")

if __name__ == "__main__":
    main()
