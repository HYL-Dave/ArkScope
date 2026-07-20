import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getMarketDataStatus,
  getTradingDayCoverage,
  type MarketDataStatus,
  type SyncMeta,
  type TradingDayCoverage,
  type TradingDayRow,
} from "../api";
import { coverageStatusLabel } from "../marketDataDisplay";
import { formatSystemTimestamp } from "../timeDisplay";

export function shortTs(iso: string | null | undefined): string {
  return formatSystemTimestamp(iso);
}
function syncLine(status: MarketDataStatus): string {
  const fmt = (m: SyncMeta | null) => {
    if (!m) return "—";
    if (m.last_error) return `錯誤（${m.last_error.slice(0, 40)}）`;
    if (!Number.isFinite(m.rows_added)) return "—";
    const ts = formatSystemTimestamp(m.last_success);
    return `+${m.rows_added.toLocaleString()} @ ${ts}`;
  };
  const s = status.sync;
  if (!s.prices && !s.news && !s.iv && !s.fundamentals) return "尚未增量更新";
  return `價格 ${fmt(s.prices)} · 新聞 ${fmt(s.news)} · IV ${fmt(s.iv)} · 基本面 ${fmt(s.fundamentals)}`;
}

export function DataStorageSection() {
  const [status, setStatus] = useState<MarketDataStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await getMarketDataStatus());
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const exists = status?.exists ?? false;
  const pr = status?.prices;
  const nw = status?.news;
  const iv = status?.iv;
  const fd = status?.fundamentals;
  const fc = status?.financial_cache;

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>市場資料 · Market Data</h2>
          <p className="muted tiny">
            顯示價格、新聞、隱含波動率、基本面與財務快取的資料量、最新時間及最近更新。
            資料抓取由 Data Sources 管理。
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
            <dt>市場資料</dt>
            <dd>{exists ? "可用" : "尚無資料"}</dd>
            <dt>價格</dt>
            <dd>{exists ? `${pr!.row_count.toLocaleString()} 列 · ${pr!.ticker_count} 檔 · 最新 ${pr!.latest_datetime ?? "—"}` : "—"}</dd>
            <dt>新聞</dt>
            <dd>{exists ? `${nw!.row_count.toLocaleString()} 篇 · ${nw!.source_count} 來源 · 最新 ${nw!.latest_published ?? "—"}` : "—"}</dd>
            <dt>IV</dt>
            <dd>{exists ? `${iv!.row_count.toLocaleString()} 列 · ${iv!.ticker_count} 檔 · 最新 ${iv!.latest_date ?? "—"}` : "—"}</dd>
            <dt>基本面</dt>
            <dd>{exists ? `${fd!.row_count.toLocaleString()} 列 · ${fd!.ticker_count} 檔 · 最新 ${fd!.latest_date ?? "—"}` : "—"}</dd>
            <dt>財務快取</dt>
            <dd>
              {exists
                ? `${fc!.row_count.toLocaleString()} 列（有效 ${fc!.valid_count} · 過期 ${fc!.expired_count}）· 最新抓取 ${formatSystemTimestamp(fc!.latest_fetched_at)}`
                : "—"}
            </dd>
            <dt>最近增量更新</dt>
            <dd>{syncLine(status)}</dd>
          </dl>
        </div>
      )}

      <TradingDayCoveragePanel />
    </div>
  );
}

// ---- 交易日 / 價格覆蓋唯讀診斷 (Slice B) — read-only; renders backend coverage_status ----

function coverageToneColor(tone: "ok" | "warn" | "muted" | "bad"): string {
  return tone === "ok" ? "var(--ok)" : tone === "bad" ? "var(--bad)"
    : tone === "warn" ? "var(--warn, #b8860b)" : "var(--muted, #888)";
}

function TradingDayCoveragePanel() {
  const { t } = useTranslation("settings");
  const [cov, setCov] = useState<TradingDayCoverage | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [lookback, setLookback] = useState(10);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setCov(await getTradingDayCoverage(lookback, "15min"));
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [lookback]);
  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div style={{ marginTop: 24, borderTop: "1px solid var(--border, #333)", paddingTop: 16 }}>
      <div className="settings-section-head">
        <div>
          <h2>交易日 / 價格覆蓋 · Trading-day coverage</h2>
          <p className="muted tiny">
            最近 {lookback} 天的 15min 價格覆蓋。每列以 coverage_status 為準：
            覆蓋完整 / 部分覆蓋 / 疑似不足 / 缺資料 / 盤中 / 週末假日。點開可看缺漏與 partial 標的、以及 provider 錯誤。
            <strong>唯讀診斷，不會自動補抓</strong>；full/partial/missing 僅作為「相對當天覆蓋最佳標的」的 drill-down。
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label className="muted tiny">
            天數{" "}
            <select
              value={lookback}
              disabled={busy}
              onChange={(e) => setLookback(Number(e.target.value))}
            >
              {[10, 15, 30, 60].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
          <button className="btn-ghost" onClick={() => void load()} disabled={busy}>↻ 重新整理</button>
        </div>
      </div>

      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      {!cov ? (
        <p className="muted">載入中…</p>
      ) : (
        <div className="settings-panel">
          <p className="muted tiny">
            universe {cov.universe_count} 檔 · interval {cov.interval} · 產生於 {shortTs(cov.generated_at_et)}
          </p>
          <table className="ds-table" style={{ width: "100%", marginTop: 8 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>日期</th>
                <th style={{ textAlign: "left" }}>狀態</th>
                <th style={{ textAlign: "right" }}>最多 bars</th>
                <th style={{ textAlign: "right" }}>覆蓋</th>
                <th style={{ textAlign: "right" }}>缺</th>
                <th style={{ textAlign: "right" }}>partial</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {cov.days.map((d) => {
                const cs = coverageStatusLabel(d, t);
                const open = expanded === d.date;
                // in_progress: the session is open, so "missing/partial" is just not-fetched-yet,
                // not a gap — don't offer an alarming drill-down. Only completed days drill.
                const drillable =
                  d.coverage_status !== "in_progress" &&
                  d.is_trading_day &&
                  ((d.missing ?? 0) > 0 || (d.partial ?? 0) > 0);
                return (
                  <CoverageRow
                    key={d.date}
                    row={d}
                    label={cs.label}
                    tone={cs.tone}
                    open={open}
                    drillable={drillable}
                    onToggle={() => setExpanded(open ? null : d.date)}
                    providerErrors={cov.provider_errors}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function CoverageRow({
  row, label, tone, open, drillable, onToggle, providerErrors,
}: {
  row: TradingDayRow;
  label: string;
  tone: "ok" | "warn" | "muted" | "bad";
  open: boolean;
  drillable: boolean;
  onToggle: () => void;
  providerErrors: TradingDayCoverage["provider_errors"];
}) {
  // Show numeric coverage only for COMPLETED trading days. Non-trading → "—"; in_progress →
  // "—" too (mid-session counts aren't a gap; the status cell already says 盤中).
  const showCounts = row.is_trading_day && row.coverage_status !== "in_progress";
  const dash = (n: number | null) => (showCounts && n != null ? n.toLocaleString() : "—");
  // provider errors are universe-wide (not per-day); show them only under a day that has misses.
  const relErrors = drillable
    ? providerErrors.filter((e) => row.missing_tickers.includes(e.ticker))
    : [];
  return (
    <>
      <tr
        onClick={drillable ? onToggle : undefined}
        style={{ cursor: drillable ? "pointer" : "default" }}
      >
        <td>{row.date}{drillable ? (open ? " ▾" : " ▸") : ""}</td>
        <td style={{ color: coverageToneColor(tone) }}>{label}</td>
        <td style={{ textAlign: "right" }}>{dash(row.max_observed_bar_count)}</td>
        <td style={{ textAlign: "right" }}>{dash(row.covered)}</td>
        <td style={{ textAlign: "right" }}>{dash(row.missing)}</td>
        <td style={{ textAlign: "right" }}>{dash(row.partial)}</td>
        <td />
      </tr>
      {open && drillable && (
        <tr>
          <td colSpan={7} style={{ background: "var(--panel-2, #1a1a1a)", padding: "8px 12px" }}>
            {row.missing_tickers.length > 0 && (
              <p className="tiny" style={{ margin: "0 0 4px" }}>
                缺（{row.missing_tickers.length}）：{row.missing_tickers.join(", ")}
              </p>
            )}
            {row.partial_tickers.length > 0 && (
              <p className="tiny" style={{ margin: "0 0 4px" }}>
                partial：{row.partial_tickers.map((p) => `${p.ticker}(${p.bars})`).join(", ")}
              </p>
            )}
            {relErrors.length > 0 && (
              <p className="tiny refresh-err" style={{ margin: 0 }}>
                provider 錯誤：{relErrors.map((e) => `${e.ticker}: ${e.last_error}`).join("；")}
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
