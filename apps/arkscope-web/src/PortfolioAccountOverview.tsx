import type { ReactNode } from "react";

import type {
  PortfolioAccountValueSnapshot,
  PortfolioOverview,
  PortfolioOverviewAccount,
  PortfolioTotals,
} from "./api";
import { formatSystemTimestamp } from "./timeDisplay";
import { DataTable, StatusBadge, type DataTableColumn } from "./ui";


export function PortfolioAccountSummary({
  overview,
  busyAccountId,
  onToggleAggregate,
}: {
  overview: PortfolioOverview;
  busyAccountId: number | null;
  onToggleAggregate: (accountId: number, include: boolean) => void;
}) {
  const manualRows = currencyRows(overview.manual_subtotal.totals);
  return (
    <section className="ui-section-band portfolio-account-summary" aria-label="帳戶總覽">
      <div className="ui-section-head">
        <h2>帳戶總覽</h2>
      </div>
      {overview.accounts.map((account) => {
        const snapshot = account.latest_snapshot;
        const currency = snapshot?.base_currency ?? account.base_currency;
        return (
          <article className="portfolio-account-row" key={account.id}>
            <div className="ui-section-head">
              <div>
                <h3>{account.label}</h3>
                <span className="muted tiny">
                  {account.broker === "manual" ? "手動帳戶" : account.sync_mode}
                </span>
              </div>
              {account.broker === "manual" ? (
                <span className="muted tiny">無帳戶價值資料</span>
              ) : snapshot ? (
                <StatusBadge state="ready" label="已取得帳戶快照" />
              ) : (
                <StatusBadge state="empty" label="尚無帳戶快照" />
              )}
            </div>

            {account.broker !== "manual" ? (
              <div className="portfolio-account-values">
                <Metric label="Net Liquidation">
                  {formatAmount(snapshot?.net_liquidation, currency)}
                </Metric>
                <Metric label="Total Cash">
                  {formatAmount(snapshot?.total_cash_value, currency)}
                </Metric>
                <Metric label="Buying Power">
                  {formatAmount(snapshot?.buying_power, currency)}
                </Metric>
                <Metric label="今日已實現損益（ET）">
                  {formatAmount(snapshot?.daily_realized_pnl, currency)}
                </Metric>
                <Metric label="今日未實現損益（ET）">
                  {formatAmount(snapshot?.daily_unrealized_pnl, currency)}
                </Metric>
                <Metric label="今日損益合計（已實現 + 未實現，ET）">
                  {formatAmount(snapshot?.daily_total_pnl, currency)}
                </Metric>
              </div>
            ) : null}

            <div className="portfolio-account-times">
              <span className="muted tiny">
                Broker 觀察：{formatSystemTimestamp(snapshot?.as_of_utc)}
              </span>
              <span className="muted tiny">
                本地持倉核准 / 同步：{formatSystemTimestamp(account.canonical_last_sync_at)}
              </span>
            </div>
            <label className="muted tiny">
              <input
                type="checkbox"
                aria-label={`${account.label} 納入總計`}
                checked={account.include_in_total}
                disabled={busyAccountId === account.id}
                onChange={(event) => onToggleAggregate(
                  account.id,
                  event.currentTarget.checked,
                )}
              />
              納入總計
            </label>
          </article>
        );
      })}

      <section className="portfolio-manual-subtotal" aria-label="手動帳戶持倉小計">
        <div className="ui-section-head">
          <div>
            <h3>手動帳戶持倉小計</h3>
            <span className="muted tiny">
              只包含已勾選且未關閉的手動帳戶持倉；不與 IBKR Net Liquidation 相加。
            </span>
          </div>
        </div>
        {manualRows.length === 0 ? (
          <p className="muted">尚無納入總計的手動持倉。</p>
        ) : (
          <div className="portfolio-account-values">
            {manualRows.map(([currency, row]) => (
              <div className="ui-metric" key={currency}>
                <span className="ui-metric-label">{currency}</span>
                <strong>{formatAmount(row.market_value, currency)}</strong>
                <span className="muted tiny">
                  {row.position_count} 筆 · 未實現 {formatAmount(row.unrealized_pnl, currency)}
                </span>
              </div>
            ))}
            {overview.manual_subtotal.totals.broker_base ? (
              <div className="ui-metric">
                <span className="ui-metric-label">手動帳戶 broker-base 小計</span>
                <strong>
                  {formatAmount(
                    overview.manual_subtotal.totals.broker_base.market_value,
                    null,
                  )}
                </strong>
                <span className="muted tiny">
                  未實現 {formatAmount(
                    overview.manual_subtotal.totals.broker_base.unrealized_pnl,
                    null,
                  )}
                </span>
              </div>
            ) : null}
          </div>
        )}
      </section>
    </section>
  );
}


export function PortfolioAccountDetails({ overview }: { overview: PortfolioOverview }) {
  const columns: DataTableColumn<PortfolioOverviewAccount>[] = [
    {
      id: "account",
      header: "帳戶",
      render: (account) => (
        <>
          <strong>{account.label}</strong>
          <br />
          <span className="muted tiny">{account.broker}</span>
        </>
      ),
    },
    {
      id: "run",
      header: "Capture Run",
      align: "right",
      render: (account) => account.latest_snapshot?.capture_run_id ?? "—",
    },
    {
      id: "currency",
      header: "Base Currency",
      render: (account) => account.latest_snapshot?.base_currency
        ?? account.base_currency
        ?? "—",
    },
    ...moneyColumns,
    {
      id: "source",
      header: "來源",
      render: (account) => account.latest_snapshot
        ? `${account.latest_snapshot.source} · ${account.latest_snapshot.as_of_kind}`
        : account.broker === "manual" ? "無帳戶價值資料" : "尚無帳戶快照",
    },
    {
      id: "broker-time",
      header: "Broker 觀察",
      render: (account) => formatSystemTimestamp(account.latest_snapshot?.as_of_utc),
    },
    {
      id: "canonical-time",
      header: "本地持倉核准 / 同步",
      render: (account) => formatSystemTimestamp(account.canonical_last_sync_at),
    },
  ];
  return (
    <section className="ui-section-band portfolio-account-details">
      <div className="ui-section-head">
        <div>
          <h2>帳戶明細</h2>
          <p className="muted">
            最新觀察值，不是績效曲線；空值表示 provider 未回報。
          </p>
        </div>
      </div>
      <DataTable<PortfolioOverviewAccount>
        ariaLabel="帳戶最新快照明細"
        rows={overview.accounts}
        columns={columns}
        rowKey={(account) => account.id}
        rowLabel={(account) => account.label}
        emptyText="尚無帳戶"
      />
    </section>
  );
}


type MoneyField = keyof Pick<
  PortfolioAccountValueSnapshot,
  | "net_liquidation"
  | "total_cash_value"
  | "settled_cash"
  | "gross_position_value"
  | "buying_power"
  | "available_funds"
  | "initial_margin_requirement"
  | "maintenance_margin_requirement"
  | "daily_realized_pnl"
  | "daily_unrealized_pnl"
  | "daily_total_pnl"
>;

const moneyColumnSpecs: Array<[string, string, MoneyField]> = [
  ["net-liquidation", "Net Liquidation", "net_liquidation"],
  ["total-cash", "Total Cash", "total_cash_value"],
  ["settled-cash", "Settled Cash", "settled_cash"],
  ["gross-position", "Gross Position Value", "gross_position_value"],
  ["buying-power", "Buying Power", "buying_power"],
  ["available-funds", "Available Funds", "available_funds"],
  ["initial-margin", "Initial Margin", "initial_margin_requirement"],
  ["maintenance-margin", "Maintenance Margin", "maintenance_margin_requirement"],
  ["daily-realized", "今日已實現（ET）", "daily_realized_pnl"],
  ["daily-unrealized", "今日未實現（ET）", "daily_unrealized_pnl"],
  ["daily-total", "今日合計（已實現 + 未實現，ET）", "daily_total_pnl"],
];

const moneyColumns: DataTableColumn<PortfolioOverviewAccount>[] = moneyColumnSpecs
  .map(([id, header, field]) => ({
    id,
    header,
    align: "right" as const,
    render: (account: PortfolioOverviewAccount) => {
      const snapshot = account.latest_snapshot;
      const currency = snapshot?.base_currency ?? account.base_currency;
      return formatAmount(snapshot?.[field], currency);
    },
  }));


function Metric({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="ui-metric">
      <span className="ui-metric-label">{label}</span>
      <strong>{children}</strong>
    </div>
  );
}


function formatAmount(
  value: number | null | undefined,
  currency: string | null,
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  if (!currency) {
    return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
  }
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    const formatted = new Intl.NumberFormat(
      undefined,
      { maximumFractionDigits: 2 },
    ).format(value);
    return `${formatted} ${currency}`;
  }
}


function currencyRows(totals: PortfolioTotals) {
  return Object.entries(totals.per_currency)
    .sort(([left], [right]) => left.localeCompare(right));
}
