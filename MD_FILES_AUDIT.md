# Markdown 文檔審計報告

> **生成日期**: 2026-01-06
> **最後審核**: 2026-01-11
> **總計**: 64 個 .md 檔案 (原 73，已刪除 12，gitignore 新增 12，新增 3)
> **目的**: 分類整理，決定各檔案處理方式
>
> **審核紀錄**:
> - [x] NEWS_DATA_INVENTORY.md - 已加版本說明 ✅ 已提交
> - [x] SCORING_DATA_INVENTORY.md - 已加版本說明 ✅ 已提交
> - [x] 根目錄 note.md - ✅ 已刪除 (數據與 notebook 實際輸出差異過大)
> - [x] FLEX_MODE_EXTENSION.md - ✅ 已刪除 (功能已實作於 score_sentiment_openai.py)
> - [x] FNSPID_usage.md - ✅ 已刪除 (引用的腳本已不存在)
> - [x] DYNAMIC_ANALYSIS_TOOLKIT.md - ✅ 已刪除 (相關腳本已刪除)
> - [x] ENHANCED_TOKEN_ANALYSIS_GUIDE.md - ✅ 已刪除 (相關腳本已刪除)
> - [x] docs/data/POLYGON_SCORING_GAP_ANALYSIS.md - ✅ 已刪除 (問題已解決，數據已修復)
> - [x] INTRADAY_TRADING_EVALUATION.md - ✅ 已移至 docs/strategy/ 並提交
> - [x] docs/design/** 及 docs/features/** - ✅ 已加入 git-crypt 加密
> - [x] NewsExtraction/ 所有 markdown - 已審核，保留
> - [x] docs/ 所有 markdown - 已審核，保留
> - [x] PROJECT_STRUCTURE.md - ✅ 更新腳本清單、數據源、待整理項目 (2026-01-10)
> - [x] README.md - ✅ 更新欄位命名、腳本路徑、移除不存在的腳本引用 (2026-01-10)
> - [x] docs/analysis/SCORING_VALIDATION_METHODOLOGY.md - ✅ 新增評分驗證方法論
> - [x] scripts/visualization/README.md - ✅ 新增視覺化工具指南
> - [x] scripts/scoring/README.md - ✅ 新增評分工具指南
> - [x] PROJECT_PROPOSAL.md - ✅ 已刪除 (完全過時)
> - [x] research_note.md - ✅ 已刪除 (Section 9 prompts 已實作於評分腳本)
> - [x] Claude-FinRL Contest 2025 Project Strategy.md - ✅ 已刪除 (過時策略)
> - [x] NewsExtraction/project-improvements.md - ✅ 已刪除 (建議已實作)
> - [x] docs/analysis/gpt5_summary_analysis_20250921.json - ✅ 已刪除 (結論已記錄於 SUMMARY_COMPARISON_REPORT.md)
> - [x] docs/analysis/SCORING_VALUE_VALIDATION_REPORT.md - ✅ 已提交 (b95b1df)
> - [x] 多個內部文檔 - ✅ 已加入 .gitignore (2026-01-11)

---

## 處理方式說明

| 代碼 | 處理方式 | 說明 |
|------|----------|------|
| 🟢 **PUBLIC** | 正常 commit | 公開文檔，一般用戶需要 |
| 🔵 **INTERNAL** | `export-ignore` | 開發者內部文檔，commit 但發布排除 |
| 🟡 **TEMP** | 可刪除或 gitignore | 暫時性文檔，問題解決後可刪 |
| 🔴 **DELETE** | 建議刪除 | 過時或重複的文檔 |
| ⚫ **GITIGNORE** | 不 commit | 本地工具輸出/敏感資訊 |

## 狀態代碼說明

| 代碼 | 說明 |
|------|------|
| ✅ Tracked | 已在 git 追蹤中 |
| 📝 Modified | 已追蹤但有未提交的修改 |
| ➕ Staged | 已暫存待提交 |
| ❓ Untracked | 尚未追蹤 |
| 🔒 git-crypt | 在 .gitattributes 設定加密 |
| 🚫 gitignore | 在 .gitignore 設定忽略 |

---

## 1. 根目錄文檔 (15 個)

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `README.md` | 專案主說明文件 | 🟢 PUBLIC | 📝 Modified |
| `CLAUDE.md` | Claude Code 專案指示 | 🟢 PUBLIC | 🚫 gitignore |
| `PROJECT_STRUCTURE.md` | 目錄結構說明 | 🟢 PUBLIC | 📝 Modified |
| `DATA_PIPELINE_DOCUMENTATION.md` | 資料處理流程文檔 | 🟢 PUBLIC | ✅ Tracked |
| `OPENAI_SCRIPTS.md` | OpenAI 腳本使用說明 | 🟢 PUBLIC | 📝 Modified |
| `NEWS_STORAGE_DESIGN.md` | 新聞儲存設計 | 🟢 PUBLIC | 📝 Modified |
| `ARCHITECTURE_VISION.md` | 三層智慧架構設計 | 🔵 INTERNAL | ✅ Tracked 🔒 git-crypt |
| ~~`PROJECT_PROPOSAL.md`~~ | ~~專案提案文檔~~ | 🔴 DELETE | ✅ 已刪除 (完全過時) |
| ~~`ANALYSIS_FINDINGS.md`~~ | ~~代碼分析發現~~ | 🔴 DELETE | ✅ 已刪除 |
| ~~`note.md`~~ | ~~情緒版 vs 無情緒版筆記~~ | 🔴 DELETE | ✅ 已刪除 (數據與 notebook 差異過大) |
| ~~`research_note.md`~~ | ~~30分鐘盤中評估 + OpenAI 模型建議~~ | 🔴 DELETE | ✅ 已刪除 (prompts 已實作) |
| ~~`Claude-FinRL Contest 2025 Project Strategy.md`~~ | ~~競賽策略 (Claude 對話導出)~~ | 🔴 DELETE | ✅ 已刪除 (過時策略) |
| ~~`DYNAMIC_ANALYSIS_TOOLKIT.md`~~ | ~~動態模型比較工具~~ | 🔴 DELETE | ✅ 已刪除 (相關腳本已刪除) |
| ~~`ENHANCED_TOKEN_ANALYSIS_GUIDE.md`~~ | ~~Token 分析指南~~ | 🔴 DELETE | ✅ 已刪除 (相關腳本已刪除) |
| ~~`FLEX_MODE_EXTENSION.md`~~ | ~~Flex 模式擴展說明~~ | 🔴 DELETE | ✅ 已刪除 (功能已實作) |
| ~~`FNSPID_usage.md`~~ | ~~FNSPID 數據使用說明~~ | 🔴 DELETE | ✅ 已刪除 (腳本已不存在) |
| `GIT_CRYPT_GUIDE.local.md` | Git-Crypt 使用指南 | ⚫ GITIGNORE | 🚫 gitignore (*.local.md) |
| `REPAIR_LOG_COLUMN_CLEANUP_20251229.md` | 欄位清理修復記錄 | 🟡 TEMP | ✅ Tracked |
| `REPAIR_PLAN_O3_SUMMARY.md` | o3_summary 修復計畫 | 🟡 TEMP | ✅ Tracked |

---

## 2. docs/design/ (4 個) - 架構設計

> 整個目錄已設定 `docs/design/** filter=git-crypt diff=git-crypt`

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `FINRL_INTEGRATION_DESIGN.md` | FinRL 整合架構設計 | 🔵 INTERNAL | 📝 Modified 🔒 git-crypt |
| `IBKR_NEWS_COLLECTION_IMPROVEMENTS.md` | IBKR 新聞收集改進 | 🔵 INTERNAL | ✅ Tracked 🔒 git-crypt |
| `MULTI_FACTOR_SIGNAL_DETECTION.md` | 多因子信號檢測設計 | 🔵 INTERNAL | 📝 Modified 🔒 git-crypt |
| `TRAINING_PIPELINE_ARCHITECTURE.md` | 訓練管道架構 | 🔵 INTERNAL | ✅ Tracked 🔒 git-crypt |

---

## 3. docs/strategy/ (3 個) - 策略規劃

> 整個目錄已設定 `docs/strategy/** filter=git-crypt diff=git-crypt`

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `INTRADAY_TRADING_EVALUATION.md` | 日內交易策略評估 | 🔵 INTERNAL | ✅ Tracked 🔒 git-crypt |
| `SIDEQUEST_CLAUDE_CODE_PLUGINS.md` | Claude Code 插件評估 | 🔵 INTERNAL | 📝 Modified 🔒 git-crypt |
| `STRATEGIC_DIRECTION_2026Q1.md` | 2026 Q1 策略方向 | 🔵 INTERNAL | ✅ Tracked 🔒 git-crypt |

---

## 4. docs/analysis/ (8 個) - 分析報告

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `DEEPSEEK_VS_CLAUDE_COMPARISON.md` | DeepSeek vs Claude 比較 | 🔵 INTERNAL | ✅ Tracked |
| `OPENAI_VS_CLAUDE_COMPARISON.md` | OpenAI vs Claude 比較 | 🔵 INTERNAL | ✅ Tracked |
| `HISTORICAL_ANALYSIS_LOG.md` | 歷史分析紀錄 | 🔵 INTERNAL | 🚫 gitignore |
| `NEWS_TIMING_ANALYSIS.md` | 新聞時效性分析 | 🔵 INTERNAL | 🚫 gitignore |
| `RISK_SCORE_COMPARISON_REPORT.md` | 風險評分比較 (自動生成) | 🟡 TEMP | ✅ Tracked |
| `SENTIMENT_SCORE_COMPARISON_REPORT.md` | 情緒評分比較 (自動生成) | 🟡 TEMP | ✅ Tracked |
| `SUMMARY_COMPARISON_REPORT.md` | Summary 比較 (自動生成) | 🟡 TEMP | ✅ Tracked |
| `SCORING_VALUE_VALIDATION_REPORT.md` | 評分價值驗證報告 | 🔵 INTERNAL | ✅ Tracked |

---

## 5. docs/data/ (3 個) - 數據文檔

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `NEWS_DATA_INVENTORY.md` | 新聞數據清單 | 🟢 PUBLIC | ✅ Tracked |
| `SCORING_DATA_INVENTORY.md` | 評分數據清單 | 🟢 PUBLIC | ✅ Tracked |
| `IBKR_NEWS_API_LIMITATIONS.md` | IBKR API 限制分析 | 🔵 INTERNAL | 📝 Modified |
| ~~`POLYGON_SCORING_GAP_ANALYSIS.md`~~ | ~~Polygon 缺口分析~~ | 🔴 DELETE | ✅ 已刪除 (問題已解決) |

---

## 6. docs/features/ (1 個)

> 整個目錄已設定 `docs/features/** filter=git-crypt diff=git-crypt`

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `SENTIMENT_DERIVED_FEATURES.md` | 情緒衍生特徵定義 | 🔵 INTERNAL | ✅ Tracked 🔒 git-crypt |

---

## 7. docs/insights/ (1 個)

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `sector_breakout_patterns.md` | 板塊爆發模式案例 | 🔵 INTERNAL | 🚫 gitignore (docs/insights/) |

---

## 8. docs/ 其他 (3 個)

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `COMPARISON_TOOLS_UPGRADE.md` | 比較工具升級報告 | 🔵 INTERNAL | 📝 Modified |
| `EXTENSIONS_REFERENCE.md` | Claude Code 擴展參考 | 🔵 INTERNAL | 🚫 gitignore |
| `FUNDAMENTALS_GUIDE.md` | 基本面分析指南 | 🔵 INTERNAL | 🚫 gitignore |

---

## 9. data_sources/ (5 個)

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `API_SPECIFICATIONS.md` | API 規格說明 | 🔵 INTERNAL | ✅ Tracked |
| `DATA_SOURCES_EVALUATION.md` | 數據源評估 | 🔵 INTERNAL | 📝 Modified 🔒 git-crypt |
| `IBKR_GUIDE.md` | IBKR 使用指南 | 🔵 INTERNAL | ✅ Tracked |
| `IBKR_INVESTOR_DATA_VALUE.md` | IBKR 投資者數據價值分析 | 🔵 INTERNAL | ✅ Tracked 🔒 git-crypt |
| `PAID_SUBSCRIPTION_EVALUATION.md` | 付費訂閱評估 | 🔵 INTERNAL | ✅ Tracked 🔒 git-crypt |

---

## 10. data_sources/comparison_data/ (1 個)

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `NEWS_PROVIDERS_COMPARISON.md` | 新聞提供商比較 | 🟡 TEMP | ❓ Untracked |

---

## 11. NewsExtraction/ (12 個)

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `CLAUDE.md` | 子模組 Claude 指示 | 🟢 PUBLIC | 🚫 gitignore |
| `README.md` | 模組說明 | 🟢 PUBLIC | ✅ Tracked |
| `finrl_news_pipeline_documentation.md` | Pipeline v2.0 說明 | 🔵 INTERNAL | 🚫 gitignore |
| `quality_analysis_script_documentation.md` | 品質分析腳本說明 | 🔵 INTERNAL | 🚫 gitignore |
| `download-checklist.md` | 下載檢查清單 | 🔵 INTERNAL | ✅ Tracked |
| `model-selection-guide.md` | 模型選擇指南 | 🔵 INTERNAL | ✅ Tracked |
| `o3-flex-guide.md` | o3 Flex 使用指南 | 🔵 INTERNAL | ✅ Tracked |
| `readme_o3.md` | o3 版本說明 | 🔵 INTERNAL | ✅ Tracked |
| `project-handover.md` | 專案交接文件 | 🔵 INTERNAL | ✅ Tracked |
| ~~`project-improvements.md`~~ | ~~專案改進建議~~ | 🔴 DELETE | ✅ 已刪除 (建議已實作) |
| `quality-analysis-deep-dive.md` | 品質分析深度解析 | 🔵 INTERNAL | 🚫 gitignore |
| `usage-workflow.md` | 使用流程說明 | 🔵 INTERNAL | 🚫 gitignore |

---

## 12. scripts/ (2 個)

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `scripts/collection/README.md` | 數據收集指南 | 🟢 PUBLIC | ✅ Tracked |
| `scripts/collection/DATA_DICTIONARY.md` | 資料字典 | 🟢 PUBLIC | ✅ Tracked |

---

## 13. results/ (3 個) - 分析結果

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `results/finrl_full_analysis/analysis_report.md` | 跨模型評分分析 | 🔵 INTERNAL | ❓ Untracked |
| `results/finrl_full_analysis/detailed_distribution_analysis.md` | 詳細分佈分析 | 🔵 INTERNAL | ❓ Untracked |
| `results/finrl_full_analysis/detailed_factor_analysis.md` | 詳細變因分析 | 🔵 INTERNAL | ❓ Untracked |

---

## 14. training/ (1 個)

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `training/README.md` | 訓練模組說明 | 🟢 PUBLIC | ✅ Tracked |

---

## 15. src/ (1 個)

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `src/signals/README.md` | 信號模組使用指南 | 🟢 PUBLIC | ❓ Untracked |

---

## 16. 系統/工具生成 (應 gitignore)

| 檔案 | 內容摘要 | 建議 | 目前狀態 |
|------|----------|------|----------|
| `.claude/agents/code-reviewer.md` | Claude Code agent | ⚫ GITIGNORE | 🚫 gitignore (.claude/) |
| `.serena/memories/code_style.md` | Serena 記憶：代碼風格 | ⚫ GITIGNORE | 🚫 gitignore (.serena/) |
| `.serena/memories/project_overview.md` | Serena 記憶：專案概覽 | ⚫ GITIGNORE | 🚫 gitignore (.serena/) |
| `.serena/memories/suggested_commands.md` | Serena 記憶：建議命令 | ⚫ GITIGNORE | 🚫 gitignore (.serena/) |
| `.pytest_cache/README.md` | pytest 緩存 | ⚫ GITIGNORE | 🚫 gitignore (.pytest_cache/) |

---

## 統計摘要

### 按建議分類

| 類別 | 數量 | 處理 |
|------|------|------|
| 🟢 **PUBLIC** | 13 | 正常 commit |
| 🔵 **INTERNAL** | 32 | `export-ignore` 或加密 |
| 🟡 **TEMP** | 5 | 問題解決後可刪除 |
| 🔴 **DELETE** | 0 | 無待刪除檔案 (12 個已刪除) |
| ⚫ **GITIGNORE** | 19 | 不追蹤 (含新增 12 個) |

### 按目前狀態分類

| 狀態 | 數量 | 說明 |
|------|------|------|
| ✅ Tracked | 28 | 已追蹤且無變更 |
| 📝 Modified | 10 | 有未提交修改 |
| ➕ Staged | 0 | 無 (已提交) |
| ❓ Untracked | 1 | 尚未追蹤 (src/) |
| 🚫 gitignore | 19 | 已設定忽略 |
| 🔒 git-crypt | 12 | 已設定加密 |

---

## 現有配置檢視

### .gitignore 中與 .md 相關的設定
```gitignore
.claude/
.serena/
CLAUDE.md
*/CLAUDE.md
**/CLAUDE.md
ANALYSIS_FINDINGS.md
*.local.md
```

### .gitattributes 中的 git-crypt 設定
```gitattributes
# 敏感研究文件
data_sources/PAID_SUBSCRIPTION_EVALUATION.md filter=git-crypt diff=git-crypt
data_sources/*_EVALUATION.md filter=git-crypt diff=git-crypt
data_sources/*_VALUE.md filter=git-crypt diff=git-crypt
ARCHITECTURE_VISION.md filter=git-crypt diff=git-crypt

# 內部設計與特徵文件
docs/design/** filter=git-crypt diff=git-crypt
docs/features/** filter=git-crypt diff=git-crypt

# 策略決策文件
docs/strategy/** filter=git-crypt diff=git-crypt
```

---

## 建議行動

### 1. 立即可做
- [x] 刪除 `ANALYSIS_FINDINGS.md` (過時內容) ✅ 已完成
- [x] 將 `.serena/` 加入 `.gitignore` ✅ 已完成
- [x] 刪除 `note.md` ✅ 已刪除 (數據與 notebook 實際輸出差異過大)
- [x] 刪除 `FLEX_MODE_EXTENSION.md` ✅ 已刪除 (功能已實作於 `score_sentiment_openai.py`)
- [x] 刪除 `FNSPID_usage.md` ✅ 已刪除 (引用的腳本已不存在)

### 2. 問題解決後刪除
- [ ] `REPAIR_LOG_COLUMN_CLEANUP_20251229.md`
- [ ] `REPAIR_PLAN_O3_SUMMARY.md`
- [x] ~~`docs/data/POLYGON_SCORING_GAP_ANALYSIS.md`~~ ✅ 已刪除 (問題已解決，數據已修復)
- [ ] `docs/analysis/*_COMPARISON_REPORT.md` (自動生成的)

### 3. 需要決定的 Untracked 檔案

**已完成 (2026-01-11)**:
- ~~`docs/data/NEWS_DATA_INVENTORY.md`~~ ✅ 已提交
- ~~`docs/data/SCORING_DATA_INVENTORY.md`~~ ✅ 已提交
- ~~`docs/FUNDAMENTALS_GUIDE.md`~~ 🚫 已 gitignore (學習筆記)
- ~~`NewsExtraction/finrl_news_pipeline_documentation.md`~~ 🚫 已 gitignore
- ~~`NewsExtraction/quality_analysis_script_documentation.md`~~ 🚫 已 gitignore
- ~~`PROJECT_PROPOSAL.md`~~ ✅ 已刪除 (完全過時)
- ~~`research_note.md`~~ ✅ 已刪除 (prompts 已實作於評分腳本)
- ~~`Claude-FinRL Contest 2025 Project Strategy.md`~~ ✅ 已刪除 (過時策略)
- ~~`docs/analysis/HISTORICAL_ANALYSIS_LOG.md`~~ 🚫 已 gitignore
- ~~`docs/analysis/NEWS_TIMING_ANALYSIS.md`~~ 🚫 已 gitignore
- ~~`docs/insights/sector_breakout_patterns.md`~~ 🚫 已 gitignore (docs/insights/)
- ~~`docs/EXTENSIONS_REFERENCE.md`~~ 🚫 已 gitignore
- ~~`NewsExtraction/project-improvements.md`~~ ✅ 已刪除 (建議已實作)
- ~~`NewsExtraction/quality-analysis-deep-dive.md`~~ 🚫 已 gitignore
- ~~`NewsExtraction/usage-workflow.md`~~ 🚫 已 gitignore

**待處理**:
- `src/signals/README.md` - 稍後處理

**已完成但漏記**:
- ~~`docs/analysis/SCORING_VALUE_VALIDATION_REPORT.md`~~ ✅ 已提交 (b95b1df)

### 4. 已加入 .gitignore ✅
```gitignore
# Serena MCP memories
.serena/

# Internal Documentation (detailed docs, learning notes, exploration)
NewsExtraction/finrl_news_pipeline_documentation.md
NewsExtraction/quality_analysis_script_documentation.md
NewsExtraction/quality-analysis-deep-dive.md
NewsExtraction/usage-workflow.md
docs/EXTENSIONS_REFERENCE.md
docs/FUNDAMENTALS_GUIDE.md
docs/analysis/HISTORICAL_ANALYSIS_LOG.md
docs/analysis/NEWS_TIMING_ANALYSIS.md
docs/insights/
```

### 5. 建議更新 .gitattributes (export-ignore)
```gitattributes
# Developer-only documentation (exclude from releases)
docs/design/** export-ignore
docs/analysis/** export-ignore
docs/insights/** export-ignore
results/** export-ignore
NewsExtraction/*-guide.md export-ignore
NewsExtraction/project-*.md export-ignore
NewsExtraction/quality-*.md export-ignore
NewsExtraction/usage-*.md export-ignore
```

---

*此報告由 Claude Code 自動生成，請人工審核後決定最終處理方式。*