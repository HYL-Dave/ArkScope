import { useCallback, useEffect, useState } from "react";
import { getNewsStatus, type NewsStatus } from "../api";
import { formatSystemTimestamp } from "../timeDisplay";

export function NewsStorageSection() {
  const [status, setStatus] = useState<NewsStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await getNewsStatus());
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const sync = status?.sync;
  const providerErrors = sync
    ? Object.entries(sync.providers)
        .filter(([, provider]) => provider.last_error)
        .map(([provider, state]) => `${provider}: ${state.last_error}`)
        .join("；")
    : "";

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>新聞資料狀態 · News Data</h2>
          <p className="muted tiny">
            顯示新聞資料量、最新文章、最近收集時間與錯誤。各來源排程與手動執行由 Data Sources 管理。
          </p>
        </div>
        <button className="btn-ghost" onClick={() => void load()}>↻ 重新整理</button>
      </div>

      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      {!status ? (
        <p className="muted">載入中…</p>
      ) : (
        <div className="settings-panel">
          <dl className="ds-kv">
            <dt>新聞資料</dt>
            <dd>
              {status.exists
                ? `${status.news.row_count.toLocaleString()} 篇 · ${status.news.source_count} 來源 · 最新 ${status.news.latest_published ?? "—"}`
                : "尚無資料"}
            </dd>
            <dt>最近收集成功</dt>
            <dd>{formatSystemTimestamp(sync?.last_success)}</dd>
            <dt>最近收集嘗試</dt>
            <dd>{formatSystemTimestamp(sync?.last_attempt)}</dd>
            <dt>收集狀態</dt>
            <dd>{sync?.status ?? "尚未執行"}</dd>
            <dt>最近錯誤</dt>
            <dd className={providerErrors ? "refresh-err" : undefined}>{providerErrors || sync?.last_error || "—"}</dd>
          </dl>

        </div>
      )}
    </div>
  );
}
