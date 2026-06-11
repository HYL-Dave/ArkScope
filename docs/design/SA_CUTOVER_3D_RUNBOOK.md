# Slice 3d — SA Capture Cutover Runbook（PG → data/sa_capture.db）

> 狀態：LOCKED 2026-06-11 · Rehearsal 2026-06-12（台灣上午）· 正式 cutover 2026-06-13（週六，美股休市）
> 範圍一句話：**SA cutover 只做「SA DB local hard cutover + 寫者暫停/恢復 + 讀寫 smoke」。
> 不順手重構 provenance、不 port comment extraction job、不刪 PG 舊列、不做 PG fallback。**

## 0. 鎖定決策（2026-06-11）

| # | 決策 | 內容 |
|---|------|------|
| L1 | 命名/語意 | **Plan 命名 + SPEC 語意**：`data/sa_capture.db` + `ARKSCOPE_SA_DB` 路徑覆寫（與 market_data.db 慣例一致；SPEC 的 `sa_cache.db`/profile-dir 命名在此 **waive**）；但授權語意照 SPEC LOCK #9：**hard cutover，flip 後 SA 域禁止 PG 讀 fallback**。鏡像式 fallback 在「寫入目標」是錯的——PG 在 flip 時凍結，fallback 只會復活 stale 列、掩蓋漏改的 reader。回滾 = 翻回 toggle，不是 fallback。 |
| L2 | tickers_core 回寫 | `_try_ticker_sync` **cutover 週末不動**（它讀 DAL 拿 picks，DB-agnostic，對 SQLite 照常運作）。退休 + 替代品（provenance seeding 改讀 sa_capture.db）= 獨立 follow-up 刀。 |
| L3 | comment signals | 36,255 列 **verbatim 遷移**（保 id / extracted_at / rule_set_version；SUM(id) 驗證）。cutover 前**暫停** `extract_sa_comment_signals`（raw psycopg2 第二寫者）；flip 後先讀舊 signals；**第一個 follow-up 才 port job 到 SQLite；port 前禁止 UI/job 觸發它**。 |
| L4 | 瀏覽器 | Chrome + Firefox **都要 quiesce + smoke**（兩邊都註冊了 native host manifest）。退休 Firefox manifest = follow-up，不混進 3d。 |
| L5 | PG 舊列 | 凍結唯讀保留作回滾基準。**3d 絕不刪**；重訪時機 = 跨機遷移 resume gate 之後。 |
| L6 | job_runs | 留 PG（既鎖 Q3）。`record_extension_job` 改**明確 best-effort**（PG 斷線 capture 仍成功，telemetry 降級）。health 拆兩半：capture 指標 → SQLite、extension-run 訊號 → PG，PG 不可達時優雅降級。 |
| L7 | flip 機制 | DatabaseBackend **subclass**（~10 個 isinstance 閘門強制）+ persisted **`use_local_sa`** profile_settings key（`_make_db_backend` 內 mode=ro 輕讀，鏡像 `_local_market_enabled`）。fresh native-host process 每次 spawn 重讀 → flip / rollback 對寫者即時生效，零 launcher 改動。 |
| L8 | TEXT[]/FTS | 照 SPEC §4.1.4：**junction tables**（news_tickers、signal_ticker_mentions——可查詢欄位絕不用 JSON array）+ FTS5 鏡像（沿用 3b news 的 porter+unicode61，非 SPEC 的 trigram——記divergence）。audit_unresolved 全文 fallback v1 允許降級 LIKE（會改變 unresolved counts，顯式記錄）。 |

### 窗口的本質（user 釐清）
Extension 隨時可以暫停（popup toggle）。選週末的原因是**美股休市時新聞/資訊流最慢，暫停期間的 capture 損失最小**。平日（台灣上午=美股盤後）窗口僅 1–2 小時；週末窗口 6 小時以上。所以週六可以安心停 extension。

⚠️ 但「週末自然安靜」**不成立**：chrome.alarms 24/7 跑（Alpha Picks 每 30min；market-news auto 模式有明確的週末 ET 窗口，如六/日 20:00–22:00 ET 每 5 分鐘）。Quiesce = 手動關掉**兩個瀏覽器**的兩個 auto-sync toggle；記得 popup 重開/瀏覽器重啟會 re-arm alarm。

## 1. 現狀地圖（scouting 驗證過的錨點）

- **寫路徑**：extension（兩瀏覽器）→ native host（**fresh process per message**，`scripts/sa_native_host.py:743-759`，per-message 建 DAL `:74`）→ DAL → PG。host 看不到任何 SQLite——DSN 只來自 config/.env DATABASE_URL；拿掉會**靜默 FileBackend fallback**（refresh 假成功）。
- **原子寫**：`apply_sa_refresh`（db_backend.py:1213-1331）單交易 = mark-stale + partial-index upsert 迴圈 + meta upsert；失敗→rollback→同連線記 failure-meta。兩個 partial unique index（current/closed，sql/014/015）SQLite 3.24+ 可逐字重建+upsert。
- **isinstance 閘門**：~10 個 SA DAL 方法 gate 在 `isinstance(self._backend, DatabaseBackend)`（data_access.py:703–1140）→ subclass 是唯一不大改的路。
- **5 個 raw `_get_conn()` 繞道者**（subclass 覆寫救不了）：`sa_tools.list_high_value_comments`、`sa_digest_tools` ×3、`sa_market_news_health._run_health_query`、`comment_signal_backfill`（=L3 暫停不 port）、`data_access._compute_unresolved_symbols`（**在 extension 熱路徑上**——每次 save_articles_meta 都跑）。前四 + unresolved 必須 port，否則 flip 後它們讀凍結的 PG。
- **第二寫者**：`extract_sa_comment_signals`（sidecar job）+ DAL 維護寫（sanitize/invalidate）。窗口內不可觸發。
- **隱藏第二存儲**：`apply_sa_refresh` 雙寫 `data/cache/seeking_alpha/` JSON file cache——保留，當 smoke 的獨立 cross-check。
- **PG-isms 清單**：TEXT[]（`= ANY()`/GIN → junction）、JSONB→TEXT、TIMESTAMPTZ→**單一 canonical UTC ISO 字串**（mark-stale 變字典序比較——格式統一 = correctness-critical）、`get_sa_refresh_meta` 的 `.isoformat()` 無 hasattr 防護（TEXT 會 AttributeError→靜默回 {}，要修）、NOW()/INTERVAL/FILTER/LEFT/GREATEST/IS NOT DISTINCT FROM、RealDictCursor→sqlite3.Row、%s→?、named %(x)s params。
- **FK**：sa_comment_signals.comment_row_id → sa_article_comments(id) ON DELETE CASCADE 是 load-bearing（dedupe DELETE 靠它清 signals）→ 每連線 `PRAGMA foreign_keys=ON`；**id 必須 verbatim 保留**（否則 FK 斷 + SUM(id) 驗證失效）。
- **auto_upgrade 陷阱**：sa_articles 遷空 → 第一次 quick refresh 回 auto_upgrade=true → extension 靜默全量 200-scroll 重爬 SA。cut-2 硬斷言 391 列非空。
- **PG 現量（2026-06-11）**：picks 109 · articles 391 · comments 39,764 · signals 36,255 · market_news 18,226 · meta 2。總量小，遷移本身秒級。

## 2. PREP（6/11–12 寫好測好，不碰 live 路徑）

| 階段 | 大小 | 交付 | 驗證閘 |
|------|------|------|--------|
| prep-1 schema+store | M | sa_capture.db DDL（6 表 + 2 partial unique index 逐字 + junction 表 + FTS5 鏡像）；跨進程安全 `_ensure_schema`（CREATE IF NOT EXISTS + PRAGMA user_version fast-path；每 open：WAL + busy_timeout + foreign_keys=ON）；schema_migrations 表 | 兩進程並發建 schema；foreign_key_check 空；cascade 清 signals 測試；partial-index 唯一性行為同 PG |
| prep-2 backend port | L | `SACaptureDatabaseBackend`（DatabaseBackend subclass）：~17 個 sa_* 方法 SQLite 化（apply_sa_refresh 交易語意、失敗路徑 rollback-then-record-failure、meta `.isoformat()` 修復、datetime canonicalization helper、paramstyle/dialect 全掃） | test_sa_tools 對 SQLite 參數化重放；stale-marking TEXT 排序測試；closed NULL parity；失敗仍記 ok=FALSE meta |
| prep-3 raw-SQL+health 拆分 | L | port 4 個 raw reader（digest×3、high_value_comments、unresolved_symbols hot-path）+ health 拆 SQLite/PG 兩查詢 + PG-down 降級；record_extension_job → best-effort | test_sa_digest / test_sa_market_news_health / test_job_runs 綠；PG mock 不可達時 health 仍出 capture severity |
| prep-4 flip 機制 | S | `use_local_sa` key + `ARKSCOPE_SA_DB` + `_make_db_backend` 選擇矩陣（與 use_local_market 可組合）+ sidecar `get_dal.cache_clear()` | 選擇矩陣單元測試；真 host spawn：key on→寫 temp sa_capture.db，off→寫 fake PG |
| prep-5 migration CLI | M | `scripts/migrate_sa_to_sqlite.py`（--dry-run/--out/--validate-only；.building+驗證後 swap；id verbatim；型別 canonicalization；WAL sidecar unlink；**無「從 PG 重建」按鈕**——flip 後那會毀掉本地新 capture） | 對 live PG 跑到 scratch；--validate-only 全表 match；foreign_key_check 空 |
| prep-6 rehearsal（6/12 上午） | M | 全套週六序列對 COPY 演練：migration→驗證→launcher 指 copy→Level-2 gate→一次 supervised refresh 進 copy→**rollback drill**；quiesce checklist 定稿；per-message 延遲量測（< extension 2000ms telemetry budget） | rehearsal log：rows 進 copy 不進 PG；PG counts 全程不變；週六 timing budget 成文 |

## 3. CUTOVER-DAY（6/13；6/14 = soak + buffer）

| 階段 | 動作 | 驗證 | 回滾 |
|------|------|------|------|
| cut-1 quiesce+基線 | 關兩瀏覽器×兩 auto-sync；不瀏覽 SA；確認 extract_sa_comment_signals 不會觸發；tail host log 30min 靜默；記 PG 基線（6 表 COUNT+SUM(id)）+ pg_dump sa_* 作凍結回滾物 | 30min 零 host log；零新 sa_* job_runs | 什麼都沒變——開回 toggle 即中止 |
| cut-2 建庫+驗證 | migrate → data/sa_capture.db；--validate-only vs 基線（**用 COUNT+SUM(id)，不用 fetched_at**——upsert 衝突只 bump updated_at）；foreign_key_check + integrity_check；**硬斷言 articles=391 非空**（auto_upgrade 陷阱）、closed 61/61 有 closed_date | 全表 match；FK/integrity 乾淨 | 刪 sa_capture.db(+wal/shm)；PG 未動 |
| cut-3 flip | 設 `use_local_sa`；sidecar cache_clear / 重啟；重啟任何開著的 agent CLI（第三個 DAL 持有者）；{action:ping} 握手 | ping ok；GET /sa/alpha-picks 計數=基線（已從 SQLite 服務）；providers/health SA chip 正常 | 清 key → 下一個 host spawn 即寫回 PG（fresh-process 模型=寫者即時回滾）；sidecar cache_clear |
| cut-4 extension smoke | Level-2（pytest sa_tools+job_runs + framed-JSON ping/recent_ids）；Level-3：Chrome、Firefox 各一次 supervised Quick Refresh；驗 sa_capture.db deltas（meta 更新、無重複 current 列）+ read-back（need_detail、recent_ids 去重、unresolved 合理、**auto_upgrade 沒觸發**）+ 手動 fetch 含 legacy fallback；job_runs 成功列在 PG；file-cache JSON 同步更新；**重查 PG 六表 COUNT+SUM(id) = 基線 byte-frozen**（任何漂移=漏改的寫者） | 兩瀏覽器證據行 + 本地 delta + PG 凍結 + gate 綠 | 翻回（cut-3 回滾）；smoke 期間的列只在本地——記錄之，規模小可由下次 PG-routed refresh 重抓 |
| cut-5 reader 稽核 | 全 API（/sa/* 六端點含 health 拆分驗證）+ tools（digest、high_value_comments、/ap CLI）+ providers/health；**再查 PG counts 仍凍結**（抓漏網 raw consumer） | 全 reader 與基線一致；health severity=ok | 翻回；先對 prep-6 的 copy 重現問題再重試 |
| cut-6 soak（6/13 晚–6/14） | 開回 auto-sync（兩瀏覽器，照 L4）；tickers_core 回寫照 L2 不動；改 Settings.tsx「SA 仍在 PG」文案；PG sa_* 凍結保留（L5）；讓週末 ET alarm 窗口無人值守跑；週一開盤前最終 health 檢查 | 過夜寫入進 sa_capture.db + job_runs succeeded；無 SQLITE_BUSY；週一 health ok | 翻回 toggle；flip 後 capture 只在本地——週末規模可接受（SA 資料可重抓）；local→PG 回流工具明確 out of scope |

## 4. 風險表（前四為 HIGH）

1. **isinstance 閘門靜默丟寫**（非 subclass → DAL 跳過 DB 寫但回報成功）→ prep-2 強制 subclass；cut-4 驗真實 delta 不信 toast。
2. **窗口不安靜**（24/7 alarms×兩瀏覽器；popup/重啟 re-arm）→ cut-1 雙瀏覽器 quiesce + 30min 觀測靜默；fresh-process 模型保證沒有跨 flip 的 in-flight host。
3. **隱藏寫者 split-brain**（signals job、維護寫、5 個 raw consumer）→ port 四 reader、暫停 signals job；cut-4/5 兩度斷言 PG byte-frozen。
4. **datetime TEXT 排序毀損**（mark-stale 字典序）→ 單一 canonical UTC ISO 格式雙端強制 + 專屬單元測試。
5. MEDIUM：SQLITE_BUSY（fresh-process 冷開）→ 每 open WAL+busy_timeout；短交易；extension 本身已序列化 sync 流。
6. MEDIUM：schema 漂移（SELECT * reader）→ migration CLI 做 PG↔SQLite 欄位清單 parity 檢查。
7. MEDIUM：auto_upgrade 全量重爬 → cut-2 硬斷言非空。
8. LOW：per-message 開銷 vs extension 2000ms telemetry 超時 → user_version fast-path；prep-6 實測。

## 5. 明確 OUT OF SCOPE（3d 不做）

- port `extract_sa_comment_signals`（follow-up #1；port 前禁止觸發）
- tickers_core 回寫退休 + provenance seeding 替代（follow-up #2）
- Firefox manifest 退休（follow-up #3）
- 刪 PG sa_* 舊列（resume gate 後重訪）
- PG 讀 fallback / dual-write / local→PG 回流工具
- audit_unresolved 全文搜尋 FTS5 化（v1 LIKE 降級，顯式記錄）
