# SA Comment Intelligence Plan

> **Status: STAGE 1 SHIPPED** — comment signals live; kept as reference for C-3 / future stages.

> 目的: 將 Seeking Alpha / Alpha Picks 留言區從「原始資料庫」提升為可用的社群訊號來源，抽取高價值資訊、社群共識與待驗證訊息。
> 建立日期: 2026-04-14
> 依賴: SA comments 抓取已穩定、去重與 comment_date 問題已修復；後續可受益於 Unified Runner / Knowledge Graph / Analysis Pipeline

## 1. 問題定義

目前系統已能穩定抓取:

- Alpha Picks article comments
- Comment thread 結構（best-effort）
- Comment text / commenter / comment_date

但使用方式仍停留在「人工讀留言」。缺少:

- 高價值留言與雜訊的區分
- 社群現在在討論哪些 ticker / 候選股 / 規則問題
- 哪些留言只是重複貼 pick list，哪些留言帶有可驗證的新訊息
- 可供 agent / report / dashboard 直接使用的結構化輸出

## 2. 功能定位

這不是底層架構重構的一部分，而是上層能力。

建議定位:

- 資料來源: SA article comments / market-news comments（未來）
- 用途:
  - 社群共識候選股追蹤
  - 訊息抽取（earnings / upgrade / ADR eligibility / rule interpretation / short-term catalyst）
  - 社群情緒與風向
  - 雜訊過濾與晨報摘要

不建議定位為:

- 交易訊號的直接替代品
- 未經驗證傳聞的自動採信來源

## 3. 近期觀察（2026-04-14）

最近 7 天的 Alpha Picks comments 顯示:

- 討論高度集中在少數文章，尤其是最新 stock selection / buy-removal 類文章
- 高頻話題通常是:
  - 下一輪 pick 候選股猜測
  - ADR / market cap / rating history eligibility
  - earnings 時點與 EPS revision
  - 個別股票短期催化（upgrade / breaking news / after-hours reaction）
- 大量留言屬於低價值噪音:
  - 重複貼 pick list
  - 新手配置問題
  - 點名互動 / FOMO / 閒聊

因此這功能最有價值的輸出不是「完整留言總結」，而是:

- 社群共識候選股
- 高價值評論摘錄
- 待驗證 claims
- 雜訊分層

## 4. 建議輸出

### 4.1 Community Review

固定輸出格式:

- `high_value_signals`
  - 可能包含:
    - eligibility 變化
    - earnings / EPS revision 提示
    - analyst upgrade / downgrade
    - breaking news / company-specific catalyst
- `consensus_candidates`
  - 社群反覆提到的候選 ticker
- `needs_verification`
  - 留言中的傳聞 / 二手資訊 / 外部連結，需要回頭驗證
- `noise_summary`
  - 新手提問、配置討論、情緒性留言占比

### 4.2 Structured Fields

對每篇文章或時間窗產生:

- `ticker_mentions`
- `candidate_mentions`
- `rule_mentions`
  - ADR
  - market cap
  - rating days / strong buy duration
- `event_mentions`
  - earnings
  - revisions
  - upgrade / downgrade
  - news / catalyst
- `sentiment_direction`
  - positive / negative / mixed / uncertain

## 5. 開發方向

### Stage 1: Rule-based signal extraction ✅ COMPLETED (2026-04-25)

低風險、先做可用版本。

**Status**: 已上線 (commits `aa76cb0` Stage 1, `5e72f6f` v1.1 fixes, `ba66fde` version filter pin)
**Rule set version**: `v1.1`

#### Implementation pointers

| Component | Location |
|-----------|----------|
| Extractor (pure logic) | `src/sa/comment_signals.py` — `CommentSignalExtractor` |
| Universe loader + backfill runner | `src/sa/comment_signal_backfill.py` |
| DB schema | `sql/012_add_sa_comment_signals.sql` (FK to `sa_article_comments(id)`, GIN on tickers) |
| Job runner | `extract_sa_comment_signals` registered in `src/service/jobs.py` (gated on `sa_enabled`, observable via S2 `job_runs`) |
| Agent tool | `list_high_value_comments` — `src/tools/sa_tools.py` + registry + Anthropic / OpenAI bridges |
| Tests | `tests/test_sa_comment_signals.py` (38 unit + integration tests) |

#### Implemented behaviour

- **Ticker classification**: `ticker_mentions` (universe ∩ candidates) vs `candidate_mentions` (off-universe). Single-letter tickers only via `$X` / `(X)` form. Dot-suffix tickers (`BRK.B`, `BF.A`) supported.
- **Universe**: watchlist (`user_profile.yaml`) + all-time Alpha Picks symbols (current + closed). 102 symbols on 2026-04-25.
- **Keyword buckets** (matched terms preserved, not just bucket flag): `earnings`, `rating_change`, `eligibility`, `catalyst`, `rule_query`.
- **Score formula** (0-10 cap): `tickers * 1.0 + bucket_hits * 1.5 + has_link * 2.0 + log1p(upvotes) * 0.5`.
- **needs_verification**: word-boundary hedge match (rumor / hearing / seems / might / could / maybe / possibly / supposedly / allegedly + CJK 据说 / 听说) AND a concrete claim (ticker or bucket hit). "may" excluded when followed by date token (e.g. "earnings May 5").
- **Rule-set versioning**: `RULE_SET_VERSION` constant; bump triggers re-extract via `ON CONFLICT DO UPDATE`. Tool query pins to current version.

#### Production numbers (full backfill at v1.1)

- **36,352 comments** extracted in ~95 seconds
- **distribution**: score≥5: 1,508 / score≥8: 481 / ticker_mentions present: 10,267 / candidate_mentions present: 11,358 / needs_verification: 3,508 / bucket hits: 6,860
- **precision spot-check** (20 random rows at score≥4): ~85% precision on `ticker_mentions` (target ≥80% met)
- **dot-tickers found**: 189 rows with `BRK.B` / `BF.A` style symbols

#### Deferred from Stage 1

- `get_sa_comment_consensus` — without sentiment direction it can only represent discussion-density, not bullish/bearish. Hold for Stage 2 or later.
- `review_recent_sa_comments` summary aggregator — same reasoning.
- Thread / parent-comment grouping for consensus.

### Stage 2: LLM-assisted summarization

在 Stage 1 的 structured candidates 上做更高品質摘要。

內容:

- 先用 rule-based 選出高分 comment
- 再用 LLM 只摘要這些高分 comment
- 額外標記:
  - `high_confidence`
  - `needs_verification`
  - `likely_noise`

重點:

- 不直接把所有 comment 全丟給 LLM
- 先做過濾，降低 token 成本與 hallucination 風險

### Stage 3: Knowledge Graph integration

等 Unified Runner / KG 設計成熟後，再考慮整合。

可整合內容:

- `Comment -> Company`
- `Comment -> Event`
- `Comment -> Claim`
- `Claim -> Needs verification`
- `Community consensus -> Candidate stock`

## 6. 與 Major Refactoring Plan 的關係

這個功能不應併入基礎設施 phase 本身，但可以作為 downstream capability:

- 受益於 Phase A (Knowledge Graph)
  - 社群 claims / events / company links 可入圖
- 受益於 Phase D (Analysis Pipeline)
  - 可作為 sentiment / community layer
- 不應阻塞 Phase B / C
  - Context compression / unified runner 仍應優先

## 7. 初步 API / Tool 草案

未來可考慮新增:

- `review_recent_sa_comments(window_days=7, limit=20)`
- `get_sa_comment_consensus(window_days=7)`
- `extract_sa_comment_signals(article_id)`
- `list_high_value_comments(window_days=7, ticker=None)`

可能輸出例:

```json
{
  "high_value_signals": [
    {
      "ticker": "CRDO",
      "type": "catalyst",
      "claim": "commenters cite upgrade/news as explanation for price action",
      "confidence": "medium",
      "needs_verification": true
    }
  ],
  "consensus_candidates": ["CRDO", "AMD", "AIR", "NESR", "ENVA"],
  "noise_ratio": 0.62
}
```

## 8. 風險

### 8.1 社群留言本身噪音高

緩解:

- 先做 rule-based scoring
- 不對全量 raw comments 直接總結

### 8.2 重複留言 / thread 結構不完美

緩解:

- 目前 dedupe 已穩定
- 但 thread linkage 仍屬 best-effort，摘要時不要過度依賴 tree structure

### 8.3 傳聞與二手資訊

緩解:

- 輸出中明確分 `needs_verification`
- 不將留言視為事實來源

## 9. 建議優先級

優先級: 中

理由:

- 有價值，且與目前已抓下來的 SA comments 高度相關
- 但屬上層能力，不應打斷 Context / Runner 主線重構

建議排序:

1. 先完成 Major Refactoring Plan 中的 Phase B / C
2. 同時保留這份 plan 作為可並行的 domain feature 設計
3. 若近期需要快速產出價值，可先做 Stage 1 rule-based 版本
