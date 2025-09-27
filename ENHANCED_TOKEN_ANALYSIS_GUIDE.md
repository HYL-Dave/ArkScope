# Enhanced Token Usage Analysis Guide

## 📖 概述

根據您的需求，我們開發了增強版的 token 使用分析工具，能夠：

1. **自動識別模型**: 從 `/mnt/md0/finrl` 的目錄結構中提取模型資訊
2. **服務層級檢測**: 支援 Flex 和 Standard 定價模式
3. **精確成本計算**: 使用最新的 OpenAI 2025年定價
4. **批量處理**: 支援按模型分組的大規模分析

## 🛠️ 工具組件

### 1. `find_token_files_enhanced.py` - 增強版檔案掃描器

**新功能**:
- ✅ 從目錄結構自動識別模型 (gpt-5, gpt-4.1-mini, o3 等)
- ✅ 檢測任務類型 (risk, sentiment, summary)
- ✅ 提取推理參數 (reasoning_effort, verbosity)
- ✅ 識別服務層級提示 (flex, standard)
- ✅ 支援模型過濾掃描

**使用範例**:
```bash
# 掃描所有模型
python find_token_files_enhanced.py --root /mnt/md0/finrl --include-model-info --summary-csv results.csv

# 只掃描特定模型
python find_token_files_enhanced.py --root /mnt/md0/finrl --models-only gpt-5 o3 --include-model-info

# 包含模型資訊的詳細掃描
python find_token_files_enhanced.py --root /mnt/md0/finrl --include-model-info --show-no-tokens
```

### 2. `single_token_analyzer.py` - 增強版成本分析器

**新功能**:
- ✅ 支援 Flex/Standard/Batch 三種服務層級
- ✅ 使用最新 OpenAI 定價 (per 1M tokens)
- ✅ 自動計算 Flex 模式節省金額
- ✅ 改進的模型識別算法
- ✅ 批量分析多檔案

**使用範例**:
```bash
# 使用 Flex 定價分析單一檔案
python single_token_analyzer.py --file /path/to/file.csv --service-tier flex

# 批量分析多檔案
python single_token_analyzer.py --files file1.csv file2.csv --service-tier flex --output-dir results/

# 指定模型提示
python single_token_analyzer.py --file results.csv --model gpt-5 --service-tier standard
```

## 🔄 完整工作流程

### 方法 1: 手動分步執行

```bash
# 步驟 1: 掃描並識別檔案
python find_token_files_enhanced.py \
    --root /mnt/md0/finrl \
    --include-model-info \
    --summary-csv token_files.csv

# 步驟 2: 選擇要分析的檔案
# 查看 token_files.csv，選擇感興趣的模型/檔案

# 步驟 3: 執行成本分析
python single_token_analyzer.py \
    --files $(cut -d',' -f1 token_files.csv | tail -n +2 | head -10) \
    --service-tier flex \
    --output-dir analysis_results/
```

### 方法 2: 自動化工作流程

```bash
# 使用整合腳本一鍵執行
./enhanced_workflow.sh
```

## 📊 輸出格式

### 掃描結果 (`enhanced_results.csv`)
```csv
file_path,relative_path,token_columns,base_model,task_type,service_tier,reasoning_effort,verbosity
/mnt/md0/finrl/gpt-5/risk/file.csv,gpt-5/risk/file.csv,prompt_tokens;completion_tokens,gpt-5,risk,,high,low
```

### 分析結果 (JSON格式)
```json
{
  "cost_analysis": {
    "service_tier": "flex",
    "pricing_model_used": "gpt-5",
    "total_cost_usd": 123.45,
    "cost_savings": {
      "standard_cost": 246.90,
      "flex_cost": 123.45,
      "savings_usd": 123.45,
      "savings_percentage": 50.0
    }
  }
}
```

## 💡 使用建議

### 針對您的使用情境

根據您提到通常使用 **flex** 或 **standard** 模式：

1. **成本優化分析**: 使用 `--service-tier flex` 查看節省金額
```bash
python single_token_analyzer.py --file data.csv --service-tier flex
```

2. **模型比較**: 掃描特定模型進行比較
```bash
python find_token_files_enhanced.py --models-only gpt-5 gpt-4.1-mini --include-model-info
```

3. **大規模分析**: 使用自動化工作流程
```bash
./enhanced_workflow.sh  # 自動處理所有模型
```

### 效能考量

對於大量檔案掃描，建議：

1. **使用模型過濾**: `--models-only` 減少掃描範圍
2. **分批處理**: 先掃描，再選擇重要檔案進行詳細分析
3. **使用 fast 版本**: 對於超大規模掃描可使用 `find_token_files_fast.py`

## 📈 實際效果

### 掃描結果範例
```
🔍 Scanning /mnt/md0/finrl for CSV files with token usage...

📊 Scan complete!
CSV files scanned: 7,776
Files with token columns: 72
Coverage: 0.93%

🤖 Models found:
  gpt-5: 28 files
  gpt-5-mini: 14 files
  gpt-4.1-mini: 12 files
  o3: 8 files
  o4-mini: 6 files
```

### 成本分析範例
```
💰 Cost Analysis:
  Service tier: flex
  Pricing model: gpt-5
  Total cost: $19.3561
  Cost per record: $0.276515

  💡 Flex Mode Savings:
    Standard cost: $38.7122
    Flex cost: $19.3561
    Savings: $19.3561 (50.0%)
```

## 🔧 故障排除

### 常見問題

1. **找不到 token 欄位**: 檢查 CSV 檔案是否包含 `prompt_tokens`, `completion_tokens`, `total_tokens`
2. **模型識別錯誤**: 確認檔案路徑符合 `/model_name/task/file.csv` 結構
3. **成本計算為 $0**: 確認檔案包含完整的 prompt 和 completion tokens

### 檔案結構要求

工具期望的目錄結構：
```
/mnt/md0/finrl/
├── gpt-5/
│   ├── risk/
│   │   └── risk_gpt-5_*.csv
│   ├── sentiment/
│   └── summary/
├── o3/
│   └── risk/
│       └── risk_o3_*.csv
└── gpt-4.1-mini/
    └── risk/
        └── risk_gpt-4.1-mini_*.csv
```

## 📚 相關檔案

- `find_token_files_enhanced.py` - 增強版掃描器
- `single_token_analyzer.py` - 增強版分析器
- `enhanced_workflow.sh` - 自動化工作流程
- 原始工具: `find_token_files.py`, `find_token_files_fast.py`

---

**更新日期**: 2025-09-27
**版本**: v2.0 - Enhanced with Model Detection