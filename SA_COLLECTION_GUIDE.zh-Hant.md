# Seeking Alpha 採集操作指南

這份文件對照此版本套件的英文按鈕。日常同步、首次補抓、故障恢復是不同工作，不需要每次全部操作。

本指南不會替你啟用排程或補抓。安裝與重新載入方式見 [Firefox 安裝文件](extensions/sa_alpha_picks/FIREFOX.md)；技術政策見 [資料取得與更新](DATA_ACQUISITION_AND_UPDATES.md)。

## 日常使用：通常只需兩個開關

已設定好採集瀏覽器後：

1. 保持採集瀏覽器開啟，並登入具有對應訂閱權限的 SA 帳號。Premium 與 Alpha Picks 是不同權限。
2. 開啟 **Auto-sync Alpha Picks** 與 **Auto-sync Market News**，維持你選定的間隔。
3. 確認 **Routine schedules: Alpha Picks on | News on**。這一行在 **Acquisition limits and recovery** 區域內。
4. 保持 App 開啟，讓執行紀錄可以送回 App。關閉套件面板不會關閉日常排程。

啟用自動同步不代表立刻執行。需要現在更新時，使用 **Sync Latest News** 或 **Quick Update** 各自執行一次；不要連點，也不必每次重新指定採集瀏覽器。

**不要把以下按鈕當成日常啟動步驟：** Recover stopped capture、Full Article Scan、Deep Repair Scan、Force refresh。

Firefox 正式套件名稱是 **SA Alpha Picks Exporter**。臨時附加元件會在 Firefox 重啟後移除；重新載入時選 `extensions/sa_alpha_picks/build/firefox/manifest.json`，不要選原始 Chrome manifest 或任何 Test 套件。

## 看懂畫面：目前任務與歷史結果不同

套件頂端同時放了多種資訊，**不是整個面板只有一個共同狀態**：

| 畫面文字 | 代表什麼 | 怎麼判斷 |
| --- | --- | --- |
| **Acquisition: idle here · Queued: 0** | 這個套件目前沒有執行中或排隊的工作 | 不代表今天已有成功採集，也不代表自動同步已啟用 |
| **Acquisition running** | 此套件回報正在執行採集 | 不要關它開出的採集分頁；等本次結果 |
| **Stopped capture: recovery required** | 有停止後尚未處理的任務 | 依下方故障恢復流程操作 |
| **Unfinished capture record: browser activity unavailable** | 本機還有未結束紀錄，但無法確認瀏覽器活動 | 不要僅憑時間久就當成可清除；先確認實際任務與分頁 |
| **Failed: 日期時間 / Alpha Picks refresh needs attention** | 上一次 Alpha Picks 的結果 | 比對時間；恢復舊任務或成功更新新聞，不會讓舊 Alpha Picks 結果自動變成功 |
| **Last stored Market News** | 最近一次保存的新聞摘要 | 與上面的 Alpha Picks 結果不是同一件事 |
| **Complete** | 這次作業的必要階段完成 | 仍不代表所有歷史文章、正文或留言都齊全 |
| **Waiting / deferred** | 本次未取得執行條件，或有後續工作等待 | 查看原因與時間；不等於本次已保存資料 |
| **Needs attention / degraded** | 本次有部分未完成或失敗 | 已保存資料可能仍有效，需看哪個階段、哪個標的有問題 |
| **Audit recorded** | 執行紀錄已送回 App | 單靠這行不能證明抓取成功；失敗與延後也會留下紀錄 |
| **Audit pending** | 執行紀錄還沒送回 App | 確認 App 開著；不等於內容一定沒存，也不等於本次成功 |

App 的 Provider 健康表也會同時顯示「最近成功」、「最近嘗試」及「最近錯誤」。先看它們各自的時間與工作名稱，不要把昨天的失敗當成剛剛又失敗。

也要核對時間區：套件有些紀錄標示 UTC，App 可顯示 Asia/Taipei；同一天的 00:41 UTC 就是台北 08:41，不是兩次不同的工作。

判斷本次成功，應同時核對：新的執行時間、正確的工作名稱、完成狀態及保存結果。分頁自動關閉、只有成功的 native host 連線，或只有綠色歷史紀錄，都不足以證明本次成功。

## 更新套件或故障後恢復

**若首次財報補抓還有排隊工作，先依下一節的維護切換程序，不要用 Save only、Cancel queued update 或重新指定採集者來暫停。這些操作可能改變或清除佇列。**

一般重載不需要做故障恢復。只有確實停止且面板顯示需要恢復時，才執行第 3 至 5 步；否則跳到第 6 步。

1. 先暫停正式套件的自動同步與財報排程，確認採集已停止，關閉套件自動開出的採集分頁。不要在正常抓取途中任意關分頁。
2. 在 Firefox 的 `about:debugging#/runtime/this-firefox` 找到正式 **SA Alpha Picks Exporter**，按 **Reload**。不必登出 SA，也不必重新安裝 native host。
3. 若面板顯示 **Stopped capture: recovery required**，按 **Review stopped capture**。它會展開 **Financial statement updates → Acquisition limits and recovery**，將焦點移到下一格。
4. 勾選 **Previous capture stopped; its acquisition tabs are closed.**，意思是「先前採集已停止，採集分頁已關閉」。這只是確認，不會替你停止工作或關分頁。
5. 按一次 **Recover stopped capture**。這會處理舊任務，不會清除已存資料、免除冷卻或重新登入。
6. 開啟 App，恢復兩個 **Auto-sync** 開關；財報排程依原先用途恢復。切換時關掉的開關不會因重載就自動重新開啟。
7. 要立即驗證時，先按一次 **Sync Latest News**；結束後再按一次 **Quick Update**，分別看兩次新結果。

三個相鄰核取方塊用途不同：

| 核取方塊原文 | 用途 |
| --- | --- |
| **Other automated installations stopped or updated; use these acquisition settings.** | 指定採集瀏覽器或套用共用設定時，確認其他自動採集實例已停止或更新 |
| **Previous capture stopped; its acquisition tabs are closed.** | 只用於處理已停止的舊任務 |
| **Recheck all selected scopes, including reusable data.** | 同意強制重抓，包括可重用資料；一般恢復不需要勾 |

若恢復按鈕不能操作，記下頂端狀態與錯誤文字，不要清空瀏覽器儲存、重設權限、反覆重載或反覆按更新。顯示登入失效、驗證或限流時，先處理相應原因；Recover 不是繞過這些限制的按鈕。

### 首次補抓途中更新：保留佇列

這是版本維護程序，不是日常操作；先完成隔離回歸並確認切換時間。

1. 使用瀏覽器的擴充套件管理頁停用選定套件，**不要移除／解除安裝**，也不要更改套件裡的排程或按取消。確認採集分頁已關閉、native 任務沒有尚未確認的佔用，再關閉 App。
2. 維護者備份資料庫及套件狀態，記錄剩餘範圍 ID 與順序、成功紀錄、採集者、版本號和排程設定；只記「剩幾筆」不足以驗證。
3. 更新 App/native 與同一路徑、同一 ID 的套件。Firefox 臨時套件使用 Reload；重載可能同時啟用套件，新版首次接手既有安裝時會顯示 **Upgrade paused: queue verification pending**，不會自動續跑。再次重載仍保留這個暫停。不要重新指定採集者。
4. 比對前後狀態完全保留後，立即開啟 App，按 **Resume after upgrade check**。這只解除維護暫停，不改原本的排程、頁面間隔、權限或冷卻。確認先前待處理的一筆財報已保存並從佇列移除，再預覽、啟動正文工作，核對新正文收據。不要重抓全名單。

需要回退時，先取消新版正文工作並確認採集已清理，再切回同 ID 的舊版；保留已新增的正文、財報和工作紀錄，不把舊整庫備份蓋回新資料。舊基準版本的短間隔計時器有瀏覽器呼叫錯誤，新版已修正；回退後仍須驗證實際接續，不能只看排程開關。

## 要補哪些資料

先確認日常同步能正常完成，再按用途補資料，不必同時啟動所有大批次。

| 目的 | 操作 | 邊界 |
| --- | --- | --- |
| 最新新聞 | **Sync Latest News** | 當前清單與有限的詳細頁，不等於把中斷期間補齊 |
| 中斷未滿一天的新聞 | **Catch Up News (24h)** | 最近 24 小時內的有界補抓；不保證所有缺漏都能找回，也不處理更早全部歷史 |
| 更新目前／已移出持股及近期文章 | **Quick Update** | 每次至多四個不同文章詳細頁，優先較新工作；持股頁與文章清單不包含在這四頁內 |
| 補錯誤或無效的歷史正文 | **Article body repair** | 與 Quick Update 分開，預覽後按一次啟動續跑 |
| 補財報表格 | **Financial statement updates** | 按標的、報表、Annual／Quarterly 視圖逐項處理 |
| 找更早文章或修復留言連續性 | **Full Article Scan / Deep Repair Scan** | 不是日常啟動或排錯第一步；Deep 會增加歷史留言工作 |

留言日常重點是最近 30 天及理解回覆所需的上下文，不需要為了讓歷史總數看起來齊全而反覆 Deep Repair。文章很舊也可能有新留言；文章日期與留言日期要分開看。已有留言會按識別碼去重，不代表每次都能完全避免重新走訪頁面。

### 正文補抓

1. 先讓 **Quick Update** 更新持股名單；補抓優先序依本機保留的持股快照，不是即時查詢 SA 的持股。
2. 在 **Article body repair** 按 **Preview body repair**。這只讀本機候選，不會開 SA 網頁。
3. 檢查 **selected / eligible / held / excluded**：選定、符合條件、暫緩、排除。標題只列預覽樣本，不是只能補五篇。按一次 **Start repair**，背景會逐篇續跑這份固定清單。
4. 看 **saved / skipped / failed / pending**：已存、略過、失敗、待處理。`saved` 須有正文儲存與 native 收據；`skipped` 可能是已有正文或已不符範圍，不代表本次新增。
5. 關掉彈窗仍會執行。瀏覽器重開保留工作，但 Firefox 臨時套件必須以原本身分重新載入，才可能接續。

在 **Settings > 資料來源 > 文章採集** 可修改：

| 設定 | 預設 |
| --- | --- |
| 每次工作篇數 | 0，不限 |
| 文章年齡天數 | 0，不限 |
| 正文補抓範圍 | 所有保留文章，包含歷史持股 |
| 討論區更新範圍 | 目前持股 |

儲存設定不會啟動採集或刪除任何內容。開始時固定文章 ID；預覽變動會要求重新預覽。執行中縮小範圍可以略過已不符條件的文章，但不會把新目標偷偷加進原工作。要換清單，先取消、重新預覽，再開始新工作。

目前持股的選入文章／候選優先，再處理其後續與其他保留文章。設非零年齡上限時，目前持股的選入候選不因太舊被排除；無日期的非選入文章則暫緩，不拿抓取時間冒充發表日。預設不限年齡，歷史原始文章仍可補抓；這不表示其 Entry／Exit 分類已核對。

每次佔用共用採集佇列只處理一篇，再讓出給新聞與財報。沒有整批 30 分鐘上限，仍保留單頁逾時、共用間隔、已設定配額與冷卻。**waiting** 可能是冷卻、間隔或其他工作佔用；冷卻到期自動接續。登入失效、人機驗證與權限阻擋會 **paused**，自行處理來源後才按 **Resume**。

**Cancel job** 是永久取消這次意圖，不是暫停。離線時顯示 **Cancellation pending**，等 native 確認，不能清儲存資料繞過。分頁清理未確認時仍用原本的停止採集恢復流程，不會只因時間已久就解除佔用。**partial** 是工作已收尾但仍有失敗項目，不能當成全數已存。

同一已確認的證券，只要有有效且未過期的 Current，部分賣出或 Closed 後重新選入仍按 Current 抓留言；過期 Current 不算。Former 預設停止更新留言，但文章、選入日、關聯與已存留言保留。永久排除仍有效，不能用相同代號冒充另一家公司。本批不刪永久退場內容，也尚未交付 LLM 分類。

可用正文不等於已逐段與來源核對完整。原圖網址、標籤與說明也不是離線圖片副本；未下載圖片或做 OCR，不表示模型已閱讀圖表。

## 全 watchlist 財報：只設定一次範圍

**Capture Company Data** 是擷取「目前開著的 SA 公司頁」，不是啟動全 watchlist。要批次處理，使用下方 **Financial statement updates**。

1. **Targets** 選 **All App watchlist targets**。名單來自 App，不是測試用的兩家公司；留意 supported／unsupported 數字。
2. **Statements (USD)** 選需要的報表：**Income**（損益）、**Balance**（資產負債）、**Cash flow**（現金流）。
3. **Periods** 選 **Annual**、**Quarterly** 或兩者。Annual 頁也可能有 TTM，不能當成一年只改一次。
4. 看 **Initial fill / Maintenance**、**Missing checks / Due / Reusable / Blocked** 及等待時間，再決定是否縮小範圍。
5. 只想跑一輪：保持 **Scheduled financial updates** 未勾，按 **Save only**，再按 **Update missing / due**。
6. 想持續維護：勾選 **Scheduled financial updates**，展開 **Acquisition limits and recovery**，勾選 **Other automated installations stopped or updated; use these acquisition settings.**，再按 **Enable updates here**。確認排程已啟用與採集者是這個瀏覽器。

**Save only 會把財報排程存成關閉。** 它不是「保存並啟用」。未勾排程時主按鈕叫 **Use these settings here**，勾排程時叫 **Enable updates here**。如果只是查狀態或兩個日常自動同步已正常，不必重按這個主按鈕。

例如 183 個標的 × 3 種報表 × 2 種視圖 = 1,098 個範圍，不是 1,098 家公司。**Minimum pacing wait** 只算等待間隔的下限，未含載入、解析、新聞優先、休眠或驗證時間，不是完成倒數。首次可分多天補；之後只查缺漏或到期的範圍，失敗範圍仍受重試等待約束。

年報與季報的 **check (days)** 是再次檢查的週期，不是正文期限，也不是 SA 已公布新財報的日期。使用目前範圍與預估工作量決定週期，不必套用別人的數字。

### 間隔、頁數限制與停止

- **Financial gap (seconds)** 在進階區可設 15、30、60 秒或其他有效值。修改後透過上述主按鈕套用，以 **Accepted financial gap** 為準；只改輸入框不代表共用設定已生效。
- 不想設固定頁數上限，維持 **Limit pages per hour / day** 未勾，確認 **Page budget: no hourly / daily cap**。這不會解除登入、驗證、單一採集者或實際限流冷卻。
- 新聞與 Alpha Picks 在背景財報／正文工作之間優先執行，不會中途搶走正在處理的一頁。15 秒不是 SA 保證安全的頻率，也不是每 15 秒一定完成一頁。
- 關閉持續財報排程：取消 **Scheduled financial updates**，按 **Save only**。若還有手動排隊工作，再按 **Cancel queued update**；只取消手動佇列不會關掉持續排程。
- 不要為了加速而使用 **Force refresh**。它會重查可重用資料，仍不能繞過權限、冷卻或失敗等待。

## 文章關聯與分類

在 App 的 **News** 選 Seeking Alpha 分析文章，搜尋標的並調整日期範圍，可查看已保存的 **Entry / Exit / Related** 關聯及來源依據。Entry 是選入，Exit 是賣出／移除，Related 是相關但未確認事件角色。

套件的 **Article link review (advanced, optional)** 只是待處理候選，不是完整文章清單，也不是日常採集必要步驟。它依規則和可選人工決定建立關聯；有關聯不代表系統已讀完整投資論述。

**獨立的 LLM 全文分類與模型選單尚未交付。** 更換 AI Research 或翻譯模型不會啟用這項功能。先補有效正文，再確認分類設計，避免把只有標題或免責聲明的文章當作已讀全文。

## 回報問題時提供什麼

提供按下的按鈕、時間、最上方 Acquisition 狀態、本次結果與原因即可。截圖要包含日期時間；不要提供登入 cookie、帳號密碼、API key 或完整瀏覽器設定。

目前仍有介面說明債務：歷史 Alpha Picks 失敗與目前任務並列，容易被當成同一次；**What these actions do** 的 Quick Update 詳細頁上限文字尚未同步，應以本指南與目前執行限制為準。文件讓既有流程可操作，不表示介面簡化已完成。
