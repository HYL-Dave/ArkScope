# Data Source Quirks

短索引：本專案實測過程中發現的「官方文檔聲稱 vs 實際行為」差異。

每條 entry 採短摘要 + 指向 detailed source。新加 entry 請放最上方
（newest-first），不要放 detail；detail 寫到對應的 evaluation/guide
doc。

---

## Seeking Alpha Alpha Picks — Open/Closed dual membership

- **Observed (2026-05-29)**: Some picks can appear in both Open/Current and
  Closed/Removed tabs with the same `(symbol, picked_date)`. Examples observed
  locally: `AGX` and `APP`.
- **Implication**: This is a source-state inconsistency, not an extension
  scraper bug. Storage must preserve tab membership instead of treating
  `(symbol, picked_date)` as globally unique.
- **Workaround / Fix**: PostgreSQL migration
  `sql/014_sa_alpha_picks_closed_date_and_dual_membership.sql` adds
  `closed_date` and changes the uniqueness contract to
  `(symbol, picked_date, portfolio_status)`.

---

## Finnhub Free Tier — 新聞歷史深度

- **聲稱**: 1 年（見 [API_SPECIFICATIONS.md](./API_SPECIFICATIONS.md)
  Finnhub 新聞 API §呼叫限制歷史紀錄）
- **實測 (2025-12-14)**: ~7 天
- **Workaround**: 歷史新聞改用 Polygon Free Tier（3+ 年 + AI 情緒標籤）
- **Detailed sources**:
  - [DATA_SOURCES_EVALUATION.md](./DATA_SOURCES_EVALUATION.md) §1
    — 完整測試紀錄（5 股票 × 多時段、跨源對比）
  - `docs/strategy/INTRADAY_TRADING_EVALUATION.md` — 最初成文位置，
    已於 Group 1 consolidation commit 刪除
