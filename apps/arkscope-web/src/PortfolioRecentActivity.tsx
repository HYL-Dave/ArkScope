import { ArrowRight } from "lucide-react";

import type { PortfolioActivityItem, PortfolioActivityPage } from "./api";
import { formatMarketTimestamp, formatSystemTimestamp } from "./timeDisplay";
import { Button } from "./ui";

const OUTCOME_LABELS = {
  gain: "已實現獲利",
  loss: "已實現虧損",
  flat: "已實現損益為零",
  unknown: "結果未知",
} as const;

export function PortfolioRecentActivity({
  page,
  onOpenActivity,
}: {
  page: PortfolioActivityPage;
  onOpenActivity: () => void;
}) {
  if (page.items.length === 0 && page.summary.unmatched_count === 0) return null;

  const days = page.summary.recent_window_days ?? 7;
  return (
    <aside
      className="portfolio-recent-activity"
      aria-labelledby="portfolio-recent-title"
    >
      <div className="portfolio-recent-head">
        <div>
          <h2 id="portfolio-recent-title">近期活動</h2>
          <p className="muted tiny">最近 {days} 日</p>
        </div>
        <Button
          size="compact"
          icon={<ArrowRight size={15} />}
          aria-label="開啟完整活動"
          onClick={onOpenActivity}
        >
          全部
        </Button>
      </div>

      {page.summary.unmatched_count > 0 ? (
        <p className="portfolio-recent-unmatched">
          近 {days} 日有 {page.summary.unmatched_count} 筆未匹配變動
        </p>
      ) : null}

      {page.items.length > 0 ? (
        <ul className="portfolio-recent-list">
          {page.items.map((item) => (
            <li key={item.id}>
              <strong>{eventLabel(item)}</strong>
              <span>{compactFact(item)}</span>
              <span className="muted tiny">
                {accountLabel(item)} · {compactTime(item)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </aside>
  );
}

function eventLabel(item: PortfolioActivityItem): string {
  switch (item.kind) {
    case "order": return item.symbol ? `${item.symbol} 訂單成交` : "訂單成交";
    case "execution": return item.symbol ? `${item.symbol} 獨立成交` : "獨立成交";
    case "unmatched": return item.symbol ? `${item.symbol} 未匹配變動` : "未匹配變動";
    case "manual_adjustment": return `${item.symbol} 手動調整`;
    case "coverage_gap": return item.reason_code === "broker_day_gap"
      ? "Broker 日期覆蓋缺口"
      : "成交覆蓋不完整";
    case "history_start": return "活動歷史起點";
  }
}

function compactFact(item: PortfolioActivityItem): string {
  switch (item.kind) {
    case "order":
    case "execution":
      return [
        `${sideLabel(item.objective.side)} ${formatNumber(item.objective.quantity)}`,
        OUTCOME_LABELS[item.objective.realized_outcome],
      ].join(" · ");
    case "unmatched":
      return `殘差 ${formatNumber(item.residual_quantity)}`;
    case "manual_adjustment":
      return `${manualActionLabel(item.action)} · ${item.changes.length} 項欄位`;
    case "coverage_gap":
      return item.reason_code === "broker_day_gap"
        ? "Broker 日期資料缺口"
        : "成交資料不完整";
    case "history_start":
      return "開始保留活動紀錄";
  }
}

function accountLabel(item: PortfolioActivityItem): string {
  return item.account?.label ?? "所有帳戶";
}

function compactTime(item: PortfolioActivityItem): string {
  const formatted = item.source === "broker"
    ? formatMarketTimestamp(item.occurred_at_utc)
    : formatSystemTimestamp(item.occurred_at_utc);
  return formatted.split(" · ")[0];
}

function sideLabel(value: "buy" | "sell" | "mixed" | "unknown"): string {
  return { buy: "買入", sell: "賣出", mixed: "混合", unknown: "方向未知" }[value];
}

function manualActionLabel(value: "create" | "update" | "close"): string {
  return { create: "建立", update: "更新", close: "關閉" }[value];
}

function formatNumber(value: number | null): string {
  return value == null
    ? "—"
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: 6 }).format(value);
}
