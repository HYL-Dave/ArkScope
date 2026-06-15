# Slice 3d — SA Capture Cutover Runbook（PG → data/sa_capture.db）

> 狀態：LOCKED 2026-06-11 · Rehearsal 2026-06-12（台灣上午）· 正式 cutover 2026-06-13（週六，美股休市）
> 範圍一句話：**SA cutover 只做「SA DB local hard cutover + 寫者暫停/恢復 + 讀寫 smoke」。
> 不順手重構 provenance、不 port comment extraction job、不刪 PG 舊列、不做 PG fallback。**

## 0. 鎖定決策（2026-06-11）

| # | 決策 | 內容 |
|---|------|------|
| L1 | 命名/語意 | **Plan 命名 + SPEC 語意**：`data/sa_capture.db` + `ARKSCOPE_SA_DB` 路徑覆寫（與 market_data.db 慣例一致；SPEC 的 `sa_cache.db`/profile-dir 命名在此 **waive**）；但授權語意照 SPEC LOCK #9：**hard cutover，flip 後 SA 域禁止 PG 讀 fallback**。鏡像式 fallback 在「寫入目標」是錯的——PG 在 flip 時凍結，fallback 只會復活 stale 列、掩蓋漏改的 reader。回滾 = 翻回 toggle，不是 fallback。 |
| L2 | tickers_core 回寫 | `_try_ticker_sync` **cutover 週末不動**（它讀 DAL 拿 picks，DB-agnostic，對 SQLite 照常運作）。退休 + 替代品（provenance seeding 改讀 sa_capture.db）= 獨立 follow-up 刀。 |
| L3 | comment signals | 36,255 列 **verbatim 遷移**（保 id / extracted_at / rule_set_version；SUM(id) 驗證）。cutover 前**暫停** `extract_sa_comment_signals`（raw psycopg2 第二寫者）；flip 後先讀舊 signals。**Layer A + B DONE（504166d / cff3466 / fd313a9）**：SA-local 已 port 回 sa_capture.db（store choke-point + batch-atomic）+ `get_sa_comment_focus` agent 工具；backlog 已抽完（3,541 筆，2026-06-13，signals 36,255→39,846、pending=0、PG 仍凍結）。job 仍只**手動觸發、未進排程**（自動增量排程另議）。 |
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
| cut-2 建庫+驗證 | migrate → data/sa_capture.db；--validate-only vs **cut-1 當場記錄的基線**（**用 COUNT+SUM(id)，不用 fetched_at**——upsert 衝突只 bump updated_at；⚠️ 不要用本文件裡的 6/11 scout 數字當 gate——extension 到 quiesce 前仍在新增資料）；**全表 content digest 全 ✓**（6 主表 + 3 junctions，PK 序 sha256；6/12 mutation drill 實證它抓得到 count/sum 抓不到的內容錯位）；foreign_key_check + integrity_check；**不變量斷言**：articles_count > 0（auto_upgrade 空表陷阱）且 closed 列中 closed_date IS NULL 的數量 = 0（與 cut-1 基線一致） | SQLite 全表 = cut-1 基線；9 content digest 全 ✓；FK/integrity 乾淨；兩個不變量成立 | 刪 sa_capture.db(+wal/shm)；PG 未動 |
| cut-3 flip | 設 `use_local_sa`；sidecar cache_clear / 重啟；重啟任何開著的 agent CLI（第三個 DAL 持有者）；{action:ping} 握手 | ping ok；GET /sa/alpha-picks 計數=基線（已從 SQLite 服務）；providers/health SA chip 正常 | 清 key → 下一個 host spawn 即寫回 PG（fresh-process 模型=寫者即時回滾）；sidecar cache_clear |
| cut-4 extension smoke | Level-2（pytest sa_tools+job_runs + framed-JSON ping/recent_ids）；Level-3：Chrome、Firefox 各一次 supervised Quick Refresh；驗 sa_capture.db deltas（meta 更新、無重複 current 列）+ read-back（need_detail、recent_ids 去重、unresolved 合理、**auto_upgrade 沒觸發**）+ 手動 fetch 含 legacy `save_detail_by_symbol` 動作（extension 對無 article-id URL 的後備**動作**——與已禁止的 DB read fallback 無關）；job_runs 成功列在 PG；file-cache JSON 同步更新；**重查 PG 六表 COUNT+SUM(id) = 基線 byte-frozen**（任何漂移=漏改的寫者） | 兩瀏覽器證據行 + 本地 delta + PG 凍結 + gate 綠 | 翻回（cut-3 回滾）；smoke 期間的列只在本地——記錄之，規模小可由下次 PG-routed refresh 重抓 |
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

## 4.5 Rehearsal 結果（2026-06-12，headless 部分全過）

PREP 全部完成：prep-1 `84eb724` · prep-2 `df26833` · prep-3 `4bf50df` · prep-4 `5ff6f6c` · prep-5 `9f496a6`。

Rehearsal 實測（對 `/tmp/rehearsal_sa.db` copy）：
- **Migration**：live PG → copy **5.6 秒**，9 fingerprint + content（**當時** row-level 只覆蓋 sa_alpha_picks/sa_refresh_meta 兩表）+ FK/integrity 全 ✓（109/2/391/39,769/18,259/36,255 + junctions 17,962/19,784/24,237）。
- **驗證強化（6/12 下午，rehearsal 之後、cutover 之前）**：補上**全表 content digest**（6 主表 + 3 junctions；PK 序 sha256；PG 側過同一 _canon 變換 + `COLLATE "C"` 對齊 SQLite BINARY 排序——locale collation 會把帶點 ticker 如 BRK.A 排去不同位置）。fresh build 全 ✓（~10.7s）；**mutation drill**：注入 comment 文字竄改、junction 成員置換（保基數）、updated_at `+00:00`→`Z` 三類 drift——9 個 COUNT+SUM 指紋**全部視而不見**，digest **精準抓到且只標被改的 3 張表**，exit code 1。舊驗證的 gap 實證存在，已封。誠實邊界：digest 的 PG 側重跑同一變換，抓不到「變換本身的 bug」——那由獨立 raw-SQL 的兩表 row diff + cut-4 read-back smoke 覆蓋。
- **Reader parity**：真 backend + 全部 prep-3 raw reader（high-value/digest/unresolved/health）從 copy 服務，PG 下毒全程未被碰；health 在 PG 斷線時降級 warning 不 crash。
- **Level-2 gate**：140 pytest + framed-JSON ping/recent_ids 對 installed launcher（PG 模式）全過——保護路徑無回歸。
- **Host-level flip + rollback drill**：真 launcher 進程 + env 隔離（`ARKSCOPE_PROFILE_DB`=rehearsal profile + `ARKSCOPE_SA_DB`=copy）→ synthetic closed-scope refresh 寫進 copy（61→62、meta ok=1）、**PG 零污染**（ZZTEST 0 列）；rollback（無 env）→ host log `Using LocalMarketDatabaseBackend`（market toggle 仍開，正確）。Log observable 確認：flip 時 `Using SACaptureDatabaseBackend (… HARD local)` —— cut-3 的驗證行可用。
- **Per-message 延遲：~23ms**（構造→寫完），遠低於 extension 2s telemetry 預算。
- 副作用已清理：copy 的 ZZTEST 列已刪；真實 file cache `portfolio_closed.json` 的 ZZTEST 已移除（meta.json closed 條目顯示 rehearsal 時戳，下次真實 refresh 整檔重寫自癒）。注意 closed-scope synthetic 不觸發 tickers_core 回寫（只有 current-scope 會）——rehearsal 選 closed 即為此。

週六 cut-2 注意：rehearsal copy 已是用過的工件，**正式 cutover 必須重新 build**（`python scripts/migrate_sa_to_sqlite.py` → data/sa_capture.db）。

## 3.5 Day Sheet（6/13 當天逐條指令；6/12 preflight 已全部演練過）

> 6/12 preflight 發現並排除：**本機沒有 pg_dump**（server PG 17.8，Ubuntu 24.04 預設 client 16 也不相容）→ 凍結改用 `scripts/sa_pg_freeze.py`（psycopg2 COPY → CSV + 指紋 manifest，零安裝，實測 1.2s/~64MB）。

**cut-0 前置確認**
```bash
python - <<'EOF'
import sqlite3, pathlib
p = pathlib.Path("data/profile_state.db")
row = sqlite3.connect(f"file:{p}?mode=ro", uri=True).execute(
    "SELECT value FROM profile_settings WHERE key='use_local_sa'").fetchone() if p.exists() else None
print(f"use_local_sa = {row[0] if row else '(unset)'}   sa_capture.db exists = {pathlib.Path('data/sa_capture.db').exists()}")
EOF
# 期望：(unset) + False
```

**cut-1**（user：關兩瀏覽器×兩 auto-sync toggle，不瀏覽 SA）
```bash
tail -n 0 -f data/logs/sa_native_host.log          # 30min 零新行
python scripts/migrate_sa_to_sqlite.py --dry-run | tee /tmp/cut1_baseline.txt   # 當天基線（9 指紋）
python scripts/sa_pg_freeze.py --out data/backups/sa_pg_freeze_20260613         # 凍結物
```

**cut-2**
```bash
python scripts/migrate_sa_to_sqlite.py    # build→驗證(9指紋+9digest+content+FK/integrity)→swap；PG 已 quiesce，驗證即是對 cut-1 基線
# 印出的 pg= 數字必須 == /tmp/cut1_baseline.txt
python - <<'EOF'
import sqlite3
c = sqlite3.connect("file:data/sa_capture.db?mode=ro", uri=True)
a = c.execute("SELECT COUNT(*) FROM sa_articles").fetchone()[0]
b = c.execute("SELECT COUNT(*) FROM sa_alpha_picks WHERE portfolio_status='closed' AND closed_date IS NULL").fetchone()[0]
print(f"articles={a} (>0?)   closed_missing_closed_date={b} (=0?)")
assert a > 0 and b == 0
EOF
```

**cut-3 flip**
```bash
python -c "from src.profile_state import ProfileStateStore; ProfileStateStore('data/profile_state.db').set_setting('use_local_sa','true')"
# 重啟 sidecar + 任何開著的 agent CLI（第三個 DAL 持有者）
python - <<'EOF'
import json, struct, subprocess, os
msg = json.dumps({"action": "ping"}).encode()
p = subprocess.run([os.path.expanduser("~/.local/share/arkscope/native-hosts/sa_alpha_picks_host.sh")],
                   input=struct.pack("=I", len(msg)) + msg, capture_output=True, timeout=30)
n = struct.unpack("=I", p.stdout[:4])[0]; print(json.loads(p.stdout[4:4+n]))
EOF
grep "Using SACaptureDatabaseBackend" data/logs/sa_native_host.log | tail -1   # HARD local 證據行
```

**cut-4 / cut-5**
```bash
python -m pytest tests/test_sa_tools.py tests/test_job_runs.py -q   # Level-2 gate
# hermetic：test_job_runs 的 /jobs/history route tests 直接呼叫 handler，注入 fake DAL；
# 不使用 TestClient、不建立 ASGI portal、不跑 app lifespan → 不起 scheduler、不跑 provider-env bridge、不碰 PG。
# 史：先前用 TestClient（即使不帶 `with`）在某些 Starlette/AnyIO/sandbox 組合仍會 hang；
# handler-level route-unit test 是這個 gate 的穩定形狀。
# user：Chrome、Firefox 各一次 supervised Quick Refresh（§3 cut-4 驗證項）
python scripts/migrate_sa_to_sqlite.py --dry-run | diff /tmp/cut1_baseline.txt -   # PG byte-frozen：必須零 diff
```

**回滾（任何 gate 失敗）**
```bash
python -c "from src.profile_state import ProfileStateStore; ProfileStateStore('data/profile_state.db').set_setting('use_local_sa','false')"
# 重啟 sidecar；下一個 host spawn 即寫回 PG（fresh-process 模型）；驗證 host log 回到 LocalMarketDatabaseBackend/PG
```

## 4.6 Cutover 執行結果（2026-06-13，cut-1 → cut-5 全過）

實際執行 = runbook §3.5 day sheet 逐條跑，每個 gate 停下驗證。

- **cut-0/cut-1 quiesce+基線**：使用者於 09:52 後關閉兩瀏覽器×四個 auto-sync toggle（09:52 是暫停前最後一筆 `sa_market_news_refresh`）。30 分鐘 log 觀測 **QUIET**（10:11→10:41 零變動；實際從 09:52 起靜默 49 分鐘）。baseline_t0：picks 109 / meta 2 / articles 392 / comments 39,841 / market_news 18,572 / signals 36,255 / junctions 18,269·19,784·24,237。**baseline_t1 == baseline_t0**（資料層靜止）。postgres MCP 獨立路徑重算九項全等。freeze → `data/backups/sa_pg_freeze_20260613`（6 CSV ~64MB + 指紋 manifest 對齊）。
- **cut-2 建庫+驗證**：`migrate_sa_to_sqlite.py` build → 9 fingerprint + **9 content digest** + content + FK + integrity 全 ✓ → swap 進 `data/sa_capture.db`（~84MB）。不變量：articles=392(>0)、closed 缺 closed_date=0。
- **cut-3 flip**：`use_local_sa=true`。無 sidecar/CLI 需重啟（fresh-process 模型）。framed-JSON ping + recent_ids → host log 出現 `Using SACaptureDatabaseBackend (… HARD local)`；in-process reader `query_sa_picks()`=109、DB ground truth=109。
- **cut-4 extension smoke（Chrome + Firefox 各一次 supervised Quick Refresh）**：兩瀏覽器全部動作路由 HARD local；`auto_upgrade=False`；refresh current 47 + closed 61、兩 scope `ok` **0→1**、`last_error` 清空（health 自癒）；comments net_new=1（Chrome）後冪等；`sa_alpha_picks` 109→109（in-place upsert，無新列）；6 個 current symbol 重複 = 合法不同-picked_date 雙筆 pick（PG verbatim、真實 key 零違規，非 cutover 產物）；job_runs run_id 6482/6485 落 **PG**（L6 接縫）；**PG sa_* 六表全程 byte-frozen == 基線**。
- **cut-5 reader 稽核（in-process，覆蓋 6 個 /sa endpoint + digest + high-value + health split）**：全部從 SQLite 服務、無錯誤；`market-news/health` **severity=ok**；`high-value-comments` 預設視窗回 0 = extract job 暫停（signals 最新 `extracted_at=2026-04-25`）的預期效應，放寬視窗即回資料（local dispatch 正常）；reads 後 PG 仍凍結。

UI：`Settings.tsx` 文案改為「SA capture 已切本地 SQLite（hard cutover，無 PG fallback）；報告與分數仍在 PG」。

**cut-6 final health（2026-06-15 20:43–20:45 CST，週一開盤前）**：PASS。PG `sa_*` 仍 byte-frozen 對齊 cut-1 基線：picks 109 / meta 2 / articles 392 / comments 39,841 / market_news 18,572 / signals 36,255 / junctions 18,269·19,784·24,237。Local `data/sa_capture.db` 持續成長且健康：comments 39,871（+30）、market_news 18,702（+130）、signals 39,853（v1.2 backlog 已抽完）、`PRAGMA integrity_check=ok`、`foreign_key_check=0`。Native-host log：HARD local (`SACaptureDatabaseBackend`) 持續寫入，`SQLITE_BUSY` / `database is locked` / `OperationalError` 全 0。Provider health：`seeking_alpha=connected`，market-news health `severity=ok`，7d 1,229 筆、detail completeness 85.76%，extension pipeline signal age 約 8 分鐘。`job_runs`：`sa_market_news_refresh` / `sa_alpha_picks_refresh` / `extract_sa_comment_signals` 都有 succeeded terminal row。cut-6 closed。

## 5. 明確 OUT OF SCOPE（3d 不做）

- ~~port `extract_sa_comment_signals`~~ → **follow-up #1 DONE**：Layer A (504166d) SQLite 抽取接回 store choke-point + Layer B (cff3466/fd313a9) `get_sa_comment_focus` agent 跨-ticker focus 工具（雙 bridge 註冊、對抗驗證過）。**job 仍只手動觸發、未進排程**（自動增量排程 = 另議的獨立決定）。
- tickers_core 回寫退休 + provenance seeding 替代（follow-up #2）
- Firefox manifest 退休（follow-up #3）
- 刪 PG sa_* 舊列（resume gate 後重訪）
- PG 讀 fallback / dual-write / local→PG 回流工具
- audit_unresolved 全文搜尋 FTS5 化（v1 LIKE 降級，顯式記錄）
