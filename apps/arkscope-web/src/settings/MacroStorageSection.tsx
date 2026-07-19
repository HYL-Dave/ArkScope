import { useCallback, useEffect, useState } from "react";
import { getMacroStatus, type MacroStatus } from "../api";
import { formatSystemTimestamp } from "../timeDisplay";

const MACRO_TABLE_LABELS: Array<[string, string]> = [
  ["macro_series", "FRED 序列"],
  ["macro_observations", "FRED 觀測值"],
  ["macro_release_dates", "發布排程"],
  ["cal_economic_events", "經濟行事曆"],
  ["cal_earnings_events", "財報行事曆"],
  ["cal_ipo_events", "IPO 行事曆"],
];

export function MacroStorageSection() {
  const [status, setStatus] = useState<MacroStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await getMacroStatus());
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const exists = status?.exists ?? false;
  const tables = status?.tables ?? {};
  const totalObs = (tables.macro_observations?.row_count ?? 0).toLocaleString();
  const seriesCount = (tables.macro_series?.row_count ?? 0).toLocaleString();

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>總經與行事曆 · Macro / Calendar</h2>
          <p className="muted tiny">
            顯示 FRED 序列與觀測值，以及經濟、財報與 IPO 行事曆資料。
            經濟行事曆需要 Finnhub 付費方案；未取得授權時會維持不可用。
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
            <dt>總經資料</dt>
            <dd>{exists ? `可用 · ${seriesCount} 序列 · ${totalObs} 觀測值` : "尚無資料"}</dd>
            {MACRO_TABLE_LABELS.map(([key, label]) => {
              const t = tables[key];
              return (
                <FragmentKV
                  key={key}
                  label={label}
                  value={
                    exists && t
                      ? `${t.row_count.toLocaleString()} 列 · 最新抓取 ${formatSystemTimestamp(t.last_fetched_at)}`
                      : "—"
                  }
                />
              );
            })}
          </dl>
        </div>
      )}
    </div>
  );
}
// A <dt>/<dd> pair (a fragment can't carry a key cleanly inside .map for the dl).
function FragmentKV({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}
