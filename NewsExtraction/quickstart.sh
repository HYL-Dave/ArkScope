#!/bin/bash
# FinRL 新聞數據處理 - 快速開始腳本

echo "==================================="
echo "FinRL 新聞數據處理 - 快速開始"
echo "==================================="
echo ""

# 檢查 Python 版本
echo "1. 檢查 Python 版本..."
python_version=$(python3 --version 2>&1)
if [[ $? -eq 0 ]]; then
    echo "✓ $python_version"
else
    echo "✗ 未找到 Python 3，請先安裝 Python 3.8+"
    exit 1
fi

# 創建虛擬環境
echo ""
echo "2. 創建虛擬環境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ 虛擬環境已創建"
else
    echo "✓ 虛擬環境已存在"
fi

# 激活虛擬環境
echo ""
echo "3. 激活虛擬環境..."
source venv/bin/activate
echo "✓ 虛擬環境已激活"

# 安裝依賴
echo ""
echo "4. 安裝依賴包..."
pip install --upgrade pip > /dev/null 2>&1

# 基礎依賴
echo "   安裝基礎依賴..."
pip install datasets duckdb pyarrow pandas requests tqdm numpy > /dev/null 2>&1

# OpenAI 依賴
echo "   安裝 OpenAI SDK..."
pip install openai httpx > /dev/null 2>&1

# 分析依賴
echo "   安裝分析工具..."
pip install matplotlib seaborn scikit-learn textstat > /dev/null 2>&1

# 可選：NLP 工具
echo "   安裝 NLP 工具（可選）..."
pip install spacy > /dev/null 2>&1
python -m spacy download en_core_web_sm > /dev/null 2>&1

echo "✓ 所有依賴已安裝"

# 檢查 API Key
echo ""
echo "5. 檢查 OpenAI API Key..."
if [ -z "$OPENAI_API_KEY" ]; then
    echo "✗ 未設置 OPENAI_API_KEY 環境變量"
    echo ""
    read -p "請輸入您的 OpenAI API Key: " api_key
    export OPENAI_API_KEY=$api_key
    echo "✓ API Key 已設置（僅本次會話有效）"
else
    echo "✓ 已檢測到 OPENAI_API_KEY"
fi

# 選擇模型
echo ""
echo "6. 選擇要測試的模型..."
echo "   1) o3 (最強 reasoning 模型 + Flex)"
echo "   2) o4-mini (輕量 reasoning 模型 + Flex)"
echo "   3) gpt-4.1 (最新 GPT-4)"
echo "   4) gpt-4.1-mini (輕量 GPT-4)"
echo ""
read -p "請選擇 (1-4): " model_choice

case $model_choice in
    1) MODEL="o3"; USE_FLEX="--use-flex" ;;
    2) MODEL="o4-mini"; USE_FLEX="--use-flex" ;;
    3) MODEL="gpt-4.1"; USE_FLEX="" ;;
    4) MODEL="gpt-4.1-mini"; USE_FLEX="" ;;
    *) MODEL="o3"; USE_FLEX="--use-flex"; echo "使用預設模型 o3" ;;
esac

# 測試模型
echo ""
echo "7. 測試 $MODEL 模型..."
python test_o3_flex.py --api-key "$OPENAI_API_KEY" --model "$MODEL" $USE_FLEX
test_result=$?

if [ $test_result -eq 0 ]; then
    echo ""
    echo "==================================="
    echo "✅ 環境配置成功！"
    echo "==================================="
    echo ""
    echo "您可以運行以下命令開始處理數據："
    echo ""
    echo "# 完整處理（包含 $MODEL 質量檢查）"
    echo "python finrl_news_pipeline.py --openai-key \"$OPENAI_API_KEY\" --model $MODEL $USE_FLEX"
    echo ""
    echo "# 快速處理（跳過 LLM 檢查）"
    echo "python finrl_news_pipeline.py --skip-llm"
    echo ""
    echo "# 深度分析（運行主管道後）"
    echo "python quality_analysis_script.py --openai-key \"$OPENAI_API_KEY\" --model $MODEL $USE_FLEX"
    echo ""
else
    echo ""
    echo "==================================="
    echo "❌ 測試失敗"
    echo "==================================="
    echo ""
    echo "請檢查："
    echo "1. API Key 是否正確"
    echo "2. 是否有 $MODEL 模型訪問權限"
    echo "3. 網絡連接"
    echo ""
    echo "您仍可以運行不使用 LLM 的基礎處理："
    echo "python finrl_news_pipeline.py --skip-llm"
fi

# 提示保存 API Key
echo ""
echo "提示：為了避免每次輸入 API Key，您可以："
echo "1. 使用環境配置文件："
echo "   source env_config.sh"
echo "   # 編輯 env_config.sh 文件，填入您的 API Key"
echo ""
echo "2. 或添加到 shell 配置："
echo "   echo 'export OPENAI_API_KEY=\"your-key\"' >> ~/.bashrc"
echo ""