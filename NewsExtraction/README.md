# NewsExtraction 目录说明文档

## 📋 概述

`NewsExtraction` 目录包含了完整的新闻数据处理和分析工具集，专为 FinRL Contest 2025 设计。该系统提供从数据下载到质量分析的端到端解决方案，支持多种模型、多语言处理和企业级数据验证。

## 🗂️ 目录结构

```
NewsExtraction/
├── 📜 核心脚本
│   ├── finrl_news_pipeline.py                    # 主数据处理管道 v2.2
│   └── quality_analysis_script.py                # 深度质量分析工具 v2.0
│
├── 📊 数据文件
│   ├── tickers_89.json                          # 89档股票代码列表
│   ├── fnspid_89_2013_2023_cleaned.csv          # 清洗后的FNSPID数据集 (218,654条)
│   ├── fnspid_89_2013_2023_cleaned.parquet      # Parquet格式数据
│   ├── fnspid_89_2013_2023_daily.parquet        # 每日聚合数据
│   ├── fnspid_unique_articles.csv               # 与DeepSeek比对后的独有文章 (143,373条)
│   └── finrl_fnspid.db                          # DuckDB数据库
│
├── 📋 报告文件
│   ├── data_quality_report.json                 # 数据质量报告
│   ├── data_summary.json                        # 数据统计摘要
│   └── invalid_records_report.json              # 无效记录报告
│
├── 📚 文档
│   ├── finrl_news_pipeline_documentation.md     # 主管道文档
│   ├── quality_analysis_script_documentation.md # 质量分析文档
│   ├── project-improvements.md                  # 项目改进建议
│   └── README.md                                # 本文档
│
├── 🔧 配置和日志
│   ├── finrl_news_pipeline.log                 # 执行日志
│   ├── requirements.txt                        # Python依赖
│   └── checkpoints/                            # 检查点目录
│       ├── download_latest.txt
│       └── basic_clean_latest.txt
│
└── 🗂️ 其他文件
    ├── project_info.json                       # 项目信息
    └── invalid_records.parquet                 # 无效记录备份
```

## 🛠️ 核心脚本详解

### 1. finrl_news_pipeline.py - 主数据处理管道

**功能**：完整的新闻数据下载、清洗和处理管道

**主要特性**：
- ✅ 从 HuggingFace FNSPID 数据集下载新闻
- ✅ 支持检查点和断点续传
- ✅ 多语言支持（英文、中文、西班牙文、日文）
- ✅ 数据验证和质量检查
- ✅ OpenAI reasoning 模型集成（o3, o4-mini）
- ✅ 多格式导出（Parquet, CSV, JSON）

**使用方法**：
```bash
# 基本运行
python finrl_news_pipeline.py --openai-key "YOUR_API_KEY"

# 跳过下载，使用现有数据
python finrl_news_pipeline.py --skip-download

# 使用不同模型
python finrl_news_pipeline.py --model o4-mini --language zh

# 从检查点恢复
python finrl_news_pipeline.py --resume
```

**输出文件**：
- `fnspid_89_2013_2023_cleaned.csv/parquet` - 清洗后的完整数据集
- `fnspid_89_2013_2023_daily.parquet` - 每日聚合数据
- `data_quality_report.json` - 详细质量报告
- `finrl_fnspid.db` - DuckDB 数据库

### 2. quality_analysis_script.py - 深度质量分析工具

**功能**：对新闻数据进行 17 个维度的深度质量分析

**主要特性**：
- 📊 17 个质量维度评估
- 🔍 异常检测（Isolation Forest）
- 📈 时间分布和趋势分析
- 🔄 重复内容检测（MinHash + LSH）
- 🎯 主题连贯性分析（LDA）
- 📱 多语言支持
- 📉 可视化报告生成

**使用方法**：
```bash
# 基本分析
python quality_analysis_script.py --openai-key "YOUR_API_KEY"

# 指定数据文件
python quality_analysis_script.py --data fnspid_89_2013_2023_cleaned.parquet

# 跳过 LLM 分析（节省成本）
python quality_analysis_script.py --skip-llm

# 多语言分析
python quality_analysis_script.py --language zh --model o4-mini
```

**输出文件**：
- `comprehensive_quality_report.json` - 完整质量分析报告
- `enhanced_temporal_heatmap.png` - 时间分布热力图
- `quality_score_distribution.png` - 质量分数分布图
- `high_quality_news.parquet` - 高质量数据子集

### 3. FNSPID vs DeepSeek 数据集比对结果 (2025-01 执行)

以下是 FNSPID 与 DeepSeek 情感数据集的比对分析结果：

| 指标 | 数值 |
|------|------|
| FNSPID 总文章数 | 218,654 |
| DeepSeek 总文章数 | 127,176 |
| FNSPID 独有文章 | **143,373** (65.57%) |
| 重叠率 | 34.43% |
| 日期范围 | 2013-01-02 至 2023-12-31 |
| 共同股票数 | 75 档 |

**各年独有文章分布**：
| 年份 | 独有文章数 |
|------|-----------|
| 2013 | 2,115 |
| 2014 | 4,131 |
| 2015 | 5,055 |
| 2016 | 5,522 |
| 2017 | 10,163 |
| 2018 | 11,778 |
| 2019 | 8,580 |
| 2020 | 10,595 |
| 2021 | 10,609 |
| 2022 | 26,418 |
| 2023 | 48,407 |

**独有文章数 Top 10 股票**：
AAPL (8,115), MSFT (7,927), TSLA (7,837), NVDA (7,763), GOOG (7,096),
INTC (6,978), AMD (6,824), GILD (5,150), MU (4,523), AMZN (4,403)

> 比对方法：使用 MD5 hash (标题 + 内容前200字符) 进行文章指纹比对
>
> 独有文章已导出至 `fnspid_unique_articles.csv`

## 📊 数据文件说明

### 主要数据集

| 文件名 | 大小 | 记录数 | 描述 |
|--------|------|--------|------|
| `fnspid_89_2013_2023_cleaned.csv` | ~779MB | 218,654 | 清洗后的完整 FNSPID 数据集 |
| `fnspid_unique_articles.csv` | ~779MB | 143,373 | 与 DeepSeek 比对后的独有文章 |
| `fnspid_89_2013_2023_daily.parquet` | ~50MB | ~45,000 | 每日聚合数据 |

### 数据结构

**主要字段**：
```
- Date: 新闻日期
- Stock_symbol: 股票代码
- Article_title: 新闻标题
- Article: 新闻内容
- Sentiment: 情感分数 (-1 到 1)
- Url: 新闻链接
- Publisher: 发布者
- Author: 作者
- Lsa_summary: LSA 摘要
```

**增强字段**（处理后添加）：
```
- title_length: 标题长度
- text_length: 内容长度
- weekday: 星期几
- month, year: 月份和年份
- tags: 新闻标签 ['earnings', 'merger', 'tech', etc.]
- importance_score: 重要性分数 (0-1)
- low_relevance: 低相关性标记
```

### 股票覆盖

**涵盖的 75 档股票**：
```
AAPL, ADBE, ADI, ADP, ADSK, AEP, ALGN, AMAT, AMD, AMGN, AMZN, ANSS, 
ASML, AVGO, AZN, BIIB, BKNG, BKR, CDNS, CHTR, CMCSA, COST, CPRT, 
CRWD, CSGP, CSX, CTAS, CTSH, DDOG, DLTR, DXCM, EA, EBAY, ENPH, 
EXC, FANG, FAST, FTNT, GILD, GOOG, INTC, KHC, KLAC, LRCX, MELI, 
MNST, MRVL, MSFT, MU, NVDA, ODFL, ON, ORLY, PANW, PAYX, PCAR, 
PDD, PEP, PYPL, QCOM, REGN, ROST, SBUX, SIRI, TEAM, TMUS, TSLA, 
TXN, VRSK, VRTX, WBA, WDAY, XEL, ZM, ZS
```

**缺失的 14 档股票**：
```
CSCO, GOOGL, IDXX, ILMN, INTU, JD, LULU, MAR, MCHP, MDLZ,
NFLX, NXPI, SGEN, SNPS
```

> **缺失原因分析 (2026-01 调查)**：
>
> 这 14 档股票在 FNSPID 原始数据集中**确实存在**，但被过滤的原因：
> 1. **数据截止于 2020-06-10** - 所有 14 档的最新记录都停在 2020 年中
> 2. **情感分数全为 0.0** - 原始数据未提供有效情感标注
>
> | 股票 | 原始记录数 | 日期范围 |
> |------|-----------|----------|
> | NFLX | 3,028 | 2016-08 ~ 2020-06 |
> | GOOGL | 1,579 | 2018-07 ~ 2020-06 |
> | MAR | 1,325 | 2009-08 ~ 2020-06 |
> | CSCO | 1,010 | 2016-08 ~ 2020-06 |
> | LULU | 50 | 2020-04 ~ 2020-06 |
>
> 注：GOOGL 与 GOOG 在 FNSPID 中分开记录，本数据集使用 GOOG (8,665 条)

## 📈 数据统计

### 时间分布
- **日期范围**：2013-01-02 至 2023-12-31
- **总时长**：11 年
- **平均每日新闻**：~54 条
- **最活跃年份**：2022-2023年（近年来新闻数量显著增加）

### 股票分布
- **平均每股新闻**：~2,915 条
- **新闻最多的股票**：AMD (8,806条), AAPL (8,669条), GOOG (8,665条)
- **新闻最少的股票**：XEL (989条), WDAY (1,498条)

### 质量分布
- **有效记录率**：48.6% (218,654 / 454,627)
- **无效记录**：233,396 条（缺失必要字段或格式错误）
- **重复记录**：2,576 条（已移除）

## 🛠️ 技术特性

### 错误处理和恢复
- **检查点机制**：支持断点续传
- **指数退避重试**：API 调用失败时自动重试
- **数据验证层**：完整的 schema 验证
- **错误日志**：详细的错误记录和报告

### 性能优化
- **批处理**：避免 API 限制
- **并行处理**：多线程处理提高效率
- **内存管理**：大数据集的分批处理
- **缓存机制**：避免重复计算

### 安全特性
- **API Key 管理**：支持环境变量
- **敏感信息过滤**：自动过滤个人识别信息
- **本地处理**：大部分分析在本地完成

## 🚀 快速开始

### 1. 环境设置

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 API Key（可选）
export OPENAI_API_KEY="your-api-key-here"
```

### 2. 完整流程

```bash
# 步骤1: 运行主管道（如果还未运行）
python finrl_news_pipeline.py --openai-key "$OPENAI_API_KEY" --model o4-mini

# 步骤2: 深度质量分析
python quality_analysis_script.py --data fnspid_89_2013_2023_cleaned.parquet

# 步骤3: 数据集比对结果已记录在本文档第 3 节
# 独有文章已导出至 fnspid_unique_articles.csv
```

### 3. 数据使用示例

```python
import pandas as pd
import duckdb

# 方法1: 读取 CSV/Parquet
df = pd.read_parquet('fnspid_89_2013_2023_cleaned.parquet')

# 方法2: 使用 DuckDB
con = duckdb.connect('finrl_fnspid.db')
result = con.execute("SELECT * FROM fnspid WHERE Stock_symbol = 'AAPL' LIMIT 10").fetchdf()

# 方法3: 过滤高质量数据
high_quality = df[df['importance_score'] > 0.7]
```

## 📊 支持的模型

### OpenAI Reasoning 模型（推荐）
| 模型 | Flex 支持 | 成本 | 性能 | 推荐用途 |
|------|-----------|------|------|----------|
| o3 | ✅ | 高 | 最佳 | 深度质量分析 |
| o4-mini | ✅ | 中 | 优秀 | 日常处理（推荐） |

### 一般模型
| 模型 | Flex 支持 | 成本 | 性能 | 推荐用途 |
|------|-----------|------|------|----------|
| gpt-4.1 | ❌ | 中 | 良好 | 批量处理 |
| gpt-4.1-mini | ❌ | 低 | 基本 | 开发测试 |

## 🌐 多语言支持

- **英文 (en)**：适用于美股新闻（默认）
- **中文 (zh)**：适用于中文财经新闻
- **西班牙文 (es)**：适用于拉美市场
- **日文 (jp)**：适用于日本市场

## 📋 质量维度说明

### 17 个质量维度分类

#### 语言质量 (5个)
1. **语法正确性** - 语法错误、拼写错误、标点符号
2. **完整性** - 信息完整度、缺失关键信息
3. **专业性** - 术语使用、写作风格
4. **可读性** - 句子复杂度、词汇难度
5. **清晰度** - 表达清晰、逻辑连贯

#### 内容质量 (4个)
6. **信息价值** - 独特性、重要性
7. **数据支撑** - 具体数据、统计支持
8. **客观性** - 偏见程度、平衡报道
9. **事实密度** - 每100字的事实数量

#### 来源质量 (3个)
10. **来源可信度** - 来源权威性、引用标准
11. **引用品质** - 引用准确性、完整性
12. **交叉引用** - 多源验证、一致性

#### 市场相关性 (3个)
13. **市场相关性** - 对市场的影响力
14. **时效性** - 新闻时效、更新频率
15. **合规性** - 法规遵循、披露要求

#### 实用性 (2个)
16. **独特性** - 原创性、非重复内容
17. **可操作性** - 投资建议、具体指导

## 🔍 故障排除

### 常见问题

#### 1. 依赖库缺失
```bash
# 解决方法
pip install datasketch textstat spacy
python -m spacy download en_core_web_sm
```

#### 2. API 权限错误
```
openai.error.InvalidRequestError: The model o3 does not exist
```
**解决方法**：
- 确认 API Key 有相应模型权限
- 降级使用 `gpt-4.1-mini`
- 或使用 `--skip-llm` 跳过 LLM 分析

#### 3. 内存不足
```bash
# 解决方法：减少样本大小
python quality_analysis_script.py --sample-size 100 --export-threshold 0.6
```

#### 4. 检查点文件损坏
```bash
# 解决方法：清除检查点
rm -rf checkpoints/
python finrl_news_pipeline.py  # 重新开始
```

### 性能优化建议

1. **开发阶段**：使用小样本（`--sample-size 50`）
2. **生产环境**：启用 Flex Processing（`--use-flex`）
3. **大数据集**：使用 Parquet 格式和分批处理
4. **成本控制**：定期评估是否需要 LLM 分析

## 📝 最佳实践

### 数据处理
1. **定期备份**：重要检查点和结果文件
2. **监控日志**：关注 `finrl_news_pipeline.log` 中的错误
3. **验证输出**：检查 `data_quality_report.json` 中的统计
4. **版本管理**：使用 Git 管理代码变更

### 成本管理
1. **模型选择**：根据用途选择合适的模型等级
2. **批次处理**：合理设置 `--batch-size` 避免 API 限制
3. **Flex 模式**：生产环境启用 `--use-flex` 降低成本
4. **缓存利用**：利用检查点避免重复处理

### 质量保证
1. **多维度分析**：关注综合分数低于 6 的维度
2. **异常检测**：分析异常检测结果的业务含义
3. **趋势监控**：结合时间趋势理解质量变化
4. **可视化辅助**：使用生成的图表辅助决策

## 🔗 相关资源

- [FinRL Contest 2025 GitHub](https://github.com/AI4Finance-Foundation/FinRL-Contest-2025)
- [FNSPID 数据集](https://huggingface.co/datasets/Zihan1004/FNSPID)
- [OpenAI API 文档](https://platform.openai.com/docs)
- [pandas 文档](https://pandas.pydata.org/docs/)
- [DuckDB 文档](https://duckdb.org/docs/)

## 📄 许可证

MIT License

## 👥 维护者

FinRL Team - MindfulRL-Intraday Project

---

**版本**：v2.2  
**最后更新**：2025-01-12  
**文档版本**：1.0