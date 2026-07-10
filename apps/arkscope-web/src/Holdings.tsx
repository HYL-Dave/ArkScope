import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  applyIbkrPortfolioSync,
  createManualPosition,
  getPortfolio,
  previewIbkrPortfolioSync,
  updatePortfolioAccount,
  type PortfolioPosition,
  type PortfolioSnapshot,
  type PortfolioSyncPreview,
} from "./api";

export function HoldingsView() {
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  const [preview, setPreview] = useState<PortfolioSyncPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const tickerRef = useRef<HTMLInputElement>(null);
  const quantityRef = useRef<HTMLInputElement>(null);
  const notesRef = useRef<HTMLInputElement>(null);

  const manualAccount = useMemo(
    () => snapshot?.accounts.find((a) => a.broker === "manual") ?? snapshot?.accounts[0] ?? null,
    [snapshot],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      setSnapshot(await getPortfolio());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onAddManual() {
    const symbol = tickerRef.current?.value.trim().toUpperCase() ?? "";
    const quantity = Number(quantityRef.current?.value || "0");
    if (!symbol || !Number.isFinite(quantity) || quantity === 0) {
      setErr("Ticker and non-zero quantity are required");
      return;
    }
    setBusy("manual");
    setErr(null);
    try {
      await createManualPosition({
        account_id: manualAccount?.id ?? null,
        symbol,
        quantity,
        asset_class: "stock",
        currency: "USD",
        notes: notesRef.current?.value ?? "",
      });
      if (tickerRef.current) tickerRef.current.value = "";
      if (quantityRef.current) quantityRef.current.value = "";
      if (notesRef.current) notesRef.current.value = "";
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function onPreviewIbkr() {
    setBusy("preview");
    setErr(null);
    try {
      setPreview(await previewIbkrPortfolioSync());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function onApplyIbkr() {
    setBusy("apply");
    setErr(null);
    try {
      await applyIbkrPortfolioSync();
      setPreview(null);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function onToggleAggregate(accountId: number, include: boolean) {
    setBusy(`account-${accountId}`);
    setErr(null);
    try {
      await updatePortfolioAccount(accountId, { include_in_total: include });
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const positions = snapshot?.positions ?? [];
  const optionPositions = positions.filter((position) => position.asset_class === "option");
  const standardPositions = positions.filter((position) => position.asset_class !== "option");
  const accounts = snapshot?.accounts ?? [];
  const totals = snapshot?.totals;

  return (
    <main className="main">
      <section className="section-band">
        <div className="section-head">
          <div>
            <p className="eyebrow">Holdings</p>
            <h1>持倉</h1>
          </div>
          <button type="button" className="btn-secondary" onClick={() => void load()} disabled={loading}>
            重新整理
          </button>
        </div>

        {err && <p className="error">{err}</p>}

        <div className="status-grid">
          {accounts.map((account) => (
            <div className="metric" key={account.id}>
              <span className="metric-label">{account.label}</span>
              <strong>{account.sync_mode}</strong>
              <span className="muted tiny">{account.broker}{account.base_currency ? ` · ${account.base_currency}` : ""}</span>
              <label className="muted tiny">
                <input
                  type="checkbox"
                  aria-label={`${account.label} 納入總計`}
                  checked={account.include_in_total !== false}
                  disabled={busy === `account-${account.id}`}
                  onChange={(event) => {
                    void onToggleAggregate(account.id, event.currentTarget.checked);
                  }}
                />
                納入總計
              </label>
            </div>
          ))}
          <div className="metric">
            <span className="metric-label">Currency basis</span>
            <strong>{totals?.currency_basis === "broker_base" ? "broker-base" : "per-currency"}</strong>
            <span className="muted tiny">{currencySummary(totals)}</span>
          </div>
        </div>
      </section>

      <section className="section-band">
        <div className="section-head">
          <h2>新增手動持倉</h2>
        </div>
        <div className="inline-form">
          <label>
            <span>Ticker</span>
            <input ref={tickerRef} aria-label="Ticker" placeholder="NVDA" />
          </label>
          <label>
            <span>Quantity</span>
            <input ref={quantityRef} aria-label="Quantity" inputMode="decimal" placeholder="1" />
          </label>
          <label>
            <span>Notes</span>
            <input ref={notesRef} aria-label="Notes" placeholder="optional" />
          </label>
          <button type="button" className="btn-primary" onClick={() => void onAddManual()} disabled={busy === "manual"}>
            新增持倉
          </button>
        </div>
      </section>

      <section className="section-band">
        <div className="section-head">
          <h2>IBKR 同步</h2>
          <div className="actions">
            <button type="button" className="btn-secondary" onClick={() => void onPreviewIbkr()} disabled={busy != null}>
              預覽 IBKR 同步
            </button>
            {preview && preview.changes.length > 0 && (
              <button type="button" className="btn-primary" onClick={() => void onApplyIbkr()} disabled={busy != null}>
                套用同步
              </button>
            )}
          </div>
        </div>
        <p className="muted">
          唯讀同步，只讀取 Gateway 可見帳戶與持倉；ArkScope 不會下單。
        </p>
        {preview && (
          <div>
            <p className="muted tiny">
              預覽結果，尚未寫入本地持倉；按「套用同步」後才會保存。
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Change</th>
                    <th>Symbol</th>
                    <th>Qty</th>
                    <th>Avg Cost</th>
                    <th>Market Value</th>
                    <th>Unrealized P&amp;L</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.changes.length === 0 ? (
                    <tr><td colSpan={6}>沒有差異</td></tr>
                  ) : preview.changes.map((change, idx) => (
                    <tr key={`${change.broker_con_id ?? change.symbol}-${idx}`}>
                      <td>{change.kind}</td>
                      <td>{change.symbol}</td>
                      <td>
                        {formatChangeMetric(
                          change.kind,
                          change.before,
                          change.after,
                          "quantity",
                          change.quantity,
                        )}
                      </td>
                      <td>
                        {formatChangeMetric(change.kind, change.before, change.after, "avg_cost")}
                      </td>
                      <td>
                        {formatChangeMetric(change.kind, change.before, change.after, "market_value")}
                      </td>
                      <td>
                        {formatChangeMetric(change.kind, change.before, change.after, "unrealized_pnl")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      <section className="section-band">
        <div className="section-head">
          <h2>Positions</h2>
          <span className="muted tiny">{standardPositions.length} rows</span>
        </div>
        <PositionsTable positions={standardPositions} emptyText="尚無一般持倉" />
      </section>

      {optionPositions.length > 0 && (
        <section className="section-band">
          <div className="section-head">
            <h2>Options</h2>
            <span className="muted tiny">{optionPositions.length} rows</span>
          </div>
          <p className="muted">
            進階選擇權風險尚未建模；此區只呈現 broker 回傳的持倉快照。
          </p>
          <PositionsTable positions={optionPositions} emptyText="尚無選擇權持倉" />
        </section>
      )}
    </main>
  );
}

function PositionsTable({
  positions,
  emptyText,
}: {
  positions: PortfolioPosition[];
  emptyText: string;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Asset</th>
            <th>Qty</th>
            <th>Currency</th>
            <th>Avg Cost</th>
            <th>Market Value</th>
            <th>Unrealized P&amp;L</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {positions.length === 0 ? (
            <tr><td colSpan={8}>{emptyText}</td></tr>
          ) : positions.map((position) => (
            <tr key={position.id}>
              <td>{position.symbol}</td>
              <td>{position.asset_class}</td>
              <td>{formatNum(position.quantity)}</td>
              <td>{position.currency}</td>
              <td>{formatMaybe(position.avg_cost)}</td>
              <td>{formatMaybe(position.market_value)}</td>
              <td>{formatMaybe(position.unrealized_pnl)}</td>
              <td>{position.notes ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatChangeMetric(
  kind: string,
  before: Record<string, unknown> | null | undefined,
  after: Record<string, unknown> | null | undefined,
  field: string,
  fallback?: number,
): string {
  const beforeValue = finiteNumber(before?.[field]);
  const afterValue = finiteNumber(after?.[field]) ?? finiteNumber(fallback);
  if (
    kind === "update" &&
    beforeValue != null &&
    afterValue != null &&
    beforeValue !== afterValue
  ) {
    return `${formatNum(beforeValue)} → ${formatNum(afterValue)}`;
  }
  if (kind === "remove") return formatMaybe(beforeValue);
  return formatMaybe(afterValue ?? beforeValue);
}

function finiteNumber(value: unknown): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value)) return undefined;
  return value;
}

function currencySummary(totals: PortfolioSnapshot["totals"] | undefined): string {
  if (!totals) return "";
  return Object.entries(totals.per_currency)
    .map(([currency, row]) => `${currency}: ${row.position_count}`)
    .join(" · ");
}

function formatMaybe(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "";
  return formatNum(value);
}

function formatNum(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(value);
}
