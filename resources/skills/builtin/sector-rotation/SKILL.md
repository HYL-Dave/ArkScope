---
name: sector_rotation
description: Cross-sector relative strength and rotation analysis
trigger: sector rotation|sector analysis|sector performance|relative strength
required_params: []
aliases: [sectors, sr]
category: builtin
auto_apply: false
data_sources:
  required: [get_sector_performance]
  optional: [get_price_change, tavily_search, execute_python_analysis]
output: report
---

Analyze current sector rotation dynamics across the market.

GOAL: Identify which sectors are gaining/losing relative strength and why.

MINIMUM DATA SOURCES:
- Sector performance data (all major sectors)
- Sector ETF price changes across multiple timeframes
- Web search for macro catalysts (Fed policy, economic data, geopolitical)

QUANTITATIVE ANALYSIS:
- Rank sectors by relative strength (multi-timeframe)
- Identify rotation patterns (cyclical vs defensive, growth vs value)
- Compare current rotation to historical patterns

REQUIRED OUTPUT:
1. Sector performance table (1w, 1m, 3m returns)
2. Relative strength ranking
3. Rotation direction (where money is flowing from/to)
4. Macro catalysts driving the rotation
5. Sectors to overweight/underweight
6. Specific ticker ideas within favored sectors

AFTER ANALYSIS: Save as a research report using save_report() with report_type="sector_review".
