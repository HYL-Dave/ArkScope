import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";

import {
  getMacroSnapshot,
  getMacroStatus,
  type MacroSnapshot,
  type MacroSnapshotItem,
  type MacroStatus,
  type MacroTableStat,
} from "../api";
import { formatSystemTimestamp } from "../timeDisplay";
import { Button } from "../ui/Button";
import { InlineAlert } from "../ui/Status";

const MACRO_TABLE_LABELS: Array<[string, string]> = [
  ["macro_series", "FRED 序列"],
  ["macro_observations", "FRED 觀測值"],
  ["macro_release_dates", "FRED 發布資料"],
  ["cal_economic_events", "經濟事件"],
  ["cal_earnings_events", "財報事件"],
  ["cal_ipo_events", "IPO 事件"],
];

function storedCoverage(table: MacroTableStat | undefined): string {
  if (!table) return "不可用";
  const count = `${table.row_count.toLocaleString()} 筆已儲存`;
  if (table.row_count === 0) return count;
  return `${count} · 最後抓取 ${formatSystemTimestamp(table.last_fetched_at)}`;
}

function snapshotValue(item: MacroSnapshotItem): string {
  if (item.value == null || !Number.isFinite(item.value)) return "—";
  const value = item.value.toLocaleString();
  return item.units ? `${value} ${item.units}` : value;
}

export function MacroStorageSection() {
  const [status, setStatus] = useState<MacroStatus | null>(null);
  const [snapshot, setSnapshot] = useState<MacroSnapshot | null>(null);
  const [statusUnavailable, setStatusUnavailable] = useState(false);
  const [snapshotUnavailable, setSnapshotUnavailable] = useState(false);
  const [loading, setLoading] = useState(false);
  const mountedRef = useRef(false);
  const sequenceRef = useRef(0);

  const load = useCallback(async () => {
    const sequence = ++sequenceRef.current;
    setLoading(true);
    const [statusResult, snapshotResult] = await Promise.allSettled([
      getMacroStatus(),
      getMacroSnapshot(),
    ]);
    if (!mountedRef.current || sequence !== sequenceRef.current) return;

    if (statusResult.status === "fulfilled") {
      setStatus(statusResult.value);
      setStatusUnavailable(false);
    } else {
      setStatusUnavailable(true);
    }
    if (snapshotResult.status === "fulfilled") {
      setSnapshot(snapshotResult.value);
      setSnapshotUnavailable(false);
    } else {
      setSnapshotUnavailable(true);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void load();
    return () => {
      mountedRef.current = false;
    };
  }, [load]);

  const tables = status?.tables ?? {};
  const statusAvailable = Boolean(
    status?.exists && tables.macro_series && tables.macro_observations,
  );
  const bothTransportLegsUnavailable = statusUnavailable && snapshotUnavailable
    && status == null && snapshot == null;
  const oneTransportLegUnavailable = !bothTransportLegsUnavailable
    && (statusUnavailable || snapshotUnavailable);
  const domainUnavailable = (status != null && !statusAvailable)
    || (snapshot != null && !snapshot.available);

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>總經資料</h2>
          <p className="muted tiny">
            查看 FRED 序列快照、儲存量與事件資料覆蓋；排程與 Provider 健康狀態由 Data Sources 管理。
          </p>
        </div>
        <Button
          tone="ghost"
          size="compact"
          icon={<RefreshCw size={15} />}
          aria-busy={loading || undefined}
          onClick={() => void load()}
        >
          重新整理
        </Button>
      </div>

      {bothTransportLegsUnavailable ? (
        <InlineAlert state="failed" title="總經資料目前無法載入">
          請稍後重新整理；既有資料不會被清除。
        </InlineAlert>
      ) : null}
      {oneTransportLegUnavailable ? (
        <InlineAlert state="partial" title="總經資料只載入了一部分">
          可用的資料已保留，請稍後重新整理其餘狀態。
        </InlineAlert>
      ) : null}
      {domainUnavailable ? (
        <InlineAlert state="blocked" title="資料庫或必要資料表目前不可用" />
      ) : null}

      {status == null && snapshot == null && loading ? (
        <p className="muted">載入中…</p>
      ) : null}

      {statusAvailable ? (
        <div className="settings-panel">
          <h3>儲存覆蓋</h3>
          <dl className="ds-kv">
            {MACRO_TABLE_LABELS.map(([key, label]) => (
              <FragmentKV
                key={key}
                label={label}
                value={storedCoverage(tables[key])}
              />
            ))}
          </dl>
        </div>
      ) : null}

      {snapshot?.available ? (
        <div className="settings-panel">
          <div className="settings-section-head">
            <div>
              <h3>FRED 快照</h3>
              <p className="muted tiny">
                {snapshot.observation_count.toLocaleString()} 筆已儲存
                {snapshot.latest_fetched_at
                  ? ` · 最後抓取 ${formatSystemTimestamp(snapshot.latest_fetched_at)}`
                  : ""}
              </p>
            </div>
            <span className="muted tiny">
              {snapshot.auto_refresh_enabled ? "自動刷新開啟" : "自動刷新關閉"}
            </span>
          </div>

          {snapshot.items.length === 0 ? (
            <p className="muted">0 筆已儲存</p>
          ) : (
            <div className="settings-table-scroll" data-testid="fred-snapshot-scroll">
              <table className="ds-table settings-fred-table">
                <thead>
                  <tr>
                    <th>Series ID</th>
                    <th>名稱</th>
                    <th>最新值</th>
                    <th>觀測日期</th>
                    <th>最後抓取</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.items.map((item) => (
                    <tr key={item.series_id}>
                      <td>{item.series_id}</td>
                      <td>
                        <strong>{item.label}</strong>
                        {item.title && item.title !== item.label
                          ? <div className="muted tiny">{item.title}</div>
                          : null}
                      </td>
                      <td>{snapshotValue(item)}</td>
                      <td>{item.observation_date ?? "—"}</td>
                      <td>{formatSystemTimestamp(item.fetched_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function FragmentKV({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}
