import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Check, RefreshCw, Save } from "lucide-react";

import {
  applyPortfolioCaptureRun,
  getPortfolioCaptureStatus,
  triggerPortfolioCapture,
  updatePortfolioCaptureSettings,
  type PortfolioCaptureReviewChange,
  type PortfolioCaptureRun,
  type PortfolioCaptureRunState,
  type PortfolioCaptureStatus,
} from "./api";
import {
  Button,
  DataTable,
  InlineAlert,
  StatusBadge,
  type CommonUiState,
  type DataTableColumn,
} from "./ui";

const IDLE_POLL_MS = 30_000;
const RUNNING_POLL_MS = 2_000;

const RUN_LABELS: Record<PortfolioCaptureRunState, string> = {
  running: "執行中",
  succeeded: "成功",
  partial: "部分完成",
  failed: "失敗",
  blocked: "已阻擋",
  interrupted: "已中止",
};

const LEG_LABELS: Record<string, string> = {
  not_attempted: "未執行",
  complete: "完整",
  partial: "部分完成",
  failed: "失敗",
};

const TRIGGER_LABELS: Record<PortfolioCaptureRun["trigger"], string> = {
  startup: "啟動補抓",
  scheduled: "排程",
  manual: "手動",
};

function runUiState(state: PortfolioCaptureRunState): CommonUiState {
  return state === "succeeded" ? "ready" : state;
}

function formatLocalTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function parseCaptureInterval(raw: string): number | null {
  const text = raw.trim();
  if (!text) return null;
  const value = Number(text);
  return Number.isInteger(value) && value >= 5 && value <= 1440 ? value : null;
}

function isCaptureStatus(value: unknown): value is PortfolioCaptureStatus {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<PortfolioCaptureStatus>;
  return Boolean(
    candidate.settings &&
    typeof candidate.settings.enabled === "boolean" &&
    Number.isFinite(candidate.settings.interval_minutes) &&
    Array.isArray(candidate.recent_runs),
  );
}

function formatReviewMetric(
  change: PortfolioCaptureReviewChange,
  field: string,
  fallback?: number,
): string {
  const before = typeof change.before?.[field] === "number" ? change.before[field] : null;
  const afterValue = change.after?.[field] ?? fallback;
  const after = typeof afterValue === "number" ? afterValue : null;
  const format = (value: number) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(value);
  if (change.kind === "update" && before != null && after != null && before !== after) {
    return `${format(before)} → ${format(after)}`;
  }
  const value = change.kind === "remove" ? before : (after ?? before);
  return value == null ? "-" : format(value);
}

export function PortfolioCapturePanel({
  onPortfolioChanged,
}: {
  onPortfolioChanged: () => void | Promise<void>;
}) {
  const [capture, setCapture] = useState<PortfolioCaptureStatus | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [interval, setIntervalValue] = useState("15");
  const [busy, setBusy] = useState<"save" | "capture" | "apply" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const dirtyRef = useRef(false);
  const initializedRef = useRef(false);
  const lastTerminalRunIdRef = useRef<number | null>(null);
  const safeCapture = isCaptureStatus(capture) ? capture : null;

  const acceptStatus = useCallback(async (next: PortfolioCaptureStatus) => {
    setCapture(next);
    if (!dirtyRef.current) {
      setEnabled(next.settings.enabled);
      setIntervalValue(String(next.settings.interval_minutes));
    }

    const latest = next.latest_run ?? null;
    const terminal = latest && latest.state !== "running" ? latest : null;
    if (!initializedRef.current) {
      initializedRef.current = true;
      lastTerminalRunIdRef.current = terminal?.id ?? null;
      return;
    }
    if (terminal && terminal.id !== lastTerminalRunIdRef.current) {
      lastTerminalRunIdRef.current = terminal.id;
      await onPortfolioChanged();
    }
  }, [onPortfolioChanged]);

  const refresh = useCallback(async () => {
    try {
      const next: unknown = await getPortfolioCaptureStatus();
      if (!isCaptureStatus(next)) {
        throw new Error("持倉同步狀態格式不相容，請重啟應用程式後再試");
      }
      await acceptStatus(next);
      setError(null);
      return next;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      return null;
    }
  }, [acceptStatus]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!safeCapture) return;
    const timer = window.setInterval(
      () => void refresh(),
      safeCapture.running ? RUNNING_POLL_MS : IDLE_POLL_MS,
    );
    return () => window.clearInterval(timer);
  }, [safeCapture?.running, refresh]);

  async function saveSettings() {
    const parsed = parseCaptureInterval(interval);
    if (parsed === null) {
      setError("間隔必須是 5-1440 分鐘的整數");
      return;
    }
    setBusy("save");
    setError(null);
    setNotice(null);
    try {
      const next: unknown = await updatePortfolioCaptureSettings({
        enabled,
        interval_minutes: parsed,
      });
      if (!isCaptureStatus(next)) {
        throw new Error("持倉同步設定回應格式不相容，請重啟應用程式後再試");
      }
      dirtyRef.current = false;
      await acceptStatus(next);
      setNotice("排程已儲存");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  }

  async function startCapture() {
    setBusy("capture");
    setError(null);
    setNotice(null);
    try {
      const started = await triggerPortfolioCapture();
      await refresh();
      if (started.error_detail) setError(started.error_detail);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  }

  async function applyReview(runId: number) {
    setBusy("apply");
    setError(null);
    setNotice(null);
    try {
      await applyPortfolioCaptureRun(runId);
      await onPortfolioChanged();
      await refresh();
      setNotice("同步變更已套用");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  }

  const runColumns = useMemo<DataTableColumn<PortfolioCaptureRun>[]>(() => [
    {
      id: "started",
      header: "開始時間",
      render: (item) => formatLocalTime(item.started_at),
    },
    {
      id: "trigger",
      header: "來源",
      render: (item) => TRIGGER_LABELS[item.trigger],
    },
    {
      id: "state",
      header: "狀態",
      render: (item) => (
        <StatusBadge state={runUiState(item.state)} label={RUN_LABELS[item.state]} />
      ),
      className: "ui-data-table-status",
    },
    {
      id: "facts",
      header: "新增事實",
      render: (item) => `${item.inserted_execution_count} 筆成交 · ${item.inserted_commission_count} 筆費用`,
    },
  ], []);

  const reviewColumns = useMemo<DataTableColumn<PortfolioCaptureReviewChange>[]>(() => [
    {
      id: "account",
      header: "帳戶",
      render: (item) => item.account_label ?? item.broker_account_id_hash?.slice(0, 8) ?? "新帳戶",
    },
    { id: "kind", header: "變更", render: (item) => item.kind },
    { id: "symbol", header: "標的", render: (item) => item.symbol },
    {
      id: "quantity",
      header: "數量",
      render: (item) => formatReviewMetric(item, "quantity", item.quantity),
      align: "right",
    },
    {
      id: "avg-cost",
      header: "Avg Cost",
      render: (item) => formatReviewMetric(item, "avg_cost"),
      align: "right",
    },
    {
      id: "market-value",
      header: "Market Value",
      render: (item) => formatReviewMetric(item, "market_value"),
      align: "right",
    },
    {
      id: "unrealized-pnl",
      header: "Unrealized P&L",
      render: (item) => formatReviewMetric(item, "unrealized_pnl"),
      align: "right",
    },
  ], []);

  const latest = safeCapture?.latest_run ?? null;
  const providerMissing = safeCapture?.provider_issue != null || safeCapture?.settings.provider_configured === false;

  return (
    <section className="ui-section-band portfolio-capture" data-portfolio-capture-controls>
      <div className="ui-section-head">
        <div>
          <h2>同步紀錄</h2>
          <p className="muted tiny">唯讀同步會擷取 IBKR 帳戶、成交與持倉事實；ArkScope 不會下單。</p>
        </div>
        <Button
          icon={<RefreshCw size={15} />}
          onClick={() => void startCapture()}
          busy={busy === "capture"}
          disabled={busy != null || !safeCapture || safeCapture.running || providerMissing}
        >
          立即同步
        </Button>
      </div>

      {providerMissing ? (
        <InlineAlert state="blocked" title="IBKR 尚未設定">
          前往設定 &gt; Data Sources &gt; IBKR
        </InlineAlert>
      ) : null}
      {error ? <InlineAlert state="failed" title="持倉同步失敗">{error}</InlineAlert> : null}
      {notice ? <InlineAlert state="ready" title={notice} /> : null}

      <div className="portfolio-capture-settings">
        <label className="portfolio-capture-toggle">
          <input
            type="checkbox"
            aria-label="啟用持倉同步排程"
            checked={enabled}
            disabled={!safeCapture || busy != null}
            onChange={(event) => {
              dirtyRef.current = true;
              setEnabled(event.currentTarget.checked);
            }}
          />
          啟用排程
        </label>
        <label>
          <span>間隔 <span className="muted">5-1440 分鐘</span></span>
          <input
            type="number"
            min={5}
            max={1440}
            step={1}
            aria-label="持倉同步間隔（分鐘）"
            value={interval}
            disabled={!safeCapture || busy != null}
            onChange={(event) => {
              dirtyRef.current = true;
              setIntervalValue(event.currentTarget.value);
            }}
          />
        </label>
        <Button
          icon={<Save size={15} />}
          onClick={() => void saveSettings()}
          busy={busy === "save"}
          disabled={busy != null || !safeCapture}
        >
          儲存排程
        </Button>
        <div className="portfolio-capture-next muted tiny">
          {safeCapture?.settings.enabled
            ? `下一次：${formatLocalTime(safeCapture.next_due_at)}`
            : "排程已停用"}
        </div>
      </div>

      {latest ? (
        <div className="portfolio-capture-latest">
          <div className="ui-section-head">
            <div className="ui-action-row">
              <strong>最近一次</strong>
              <StatusBadge state={runUiState(latest.state)} label={RUN_LABELS[latest.state]} />
              <span className="muted tiny">{formatLocalTime(latest.finished_at ?? latest.started_at)}</span>
            </div>
          </div>
          <div className="portfolio-capture-legs">
            <span>帳戶 · {LEG_LABELS[latest.account_leg_state] ?? latest.account_leg_state}</span>
            <span>交易 · {LEG_LABELS[latest.execution_leg_state] ?? latest.execution_leg_state}</span>
            <span>持倉 · {LEG_LABELS[latest.position_leg_state] ?? latest.position_leg_state}</span>
          </div>
          {latest.new_account_count > 0 ? (
            <InlineAlert state="partial" title="待檢視">
              發現 {latest.new_account_count} 個新帳戶。
            </InlineAlert>
          ) : null}
          {latest.archived_activity_count > 0 ? (
            <InlineAlert state="partial" title="封存帳戶有新活動">
              {latest.archived_activity_count} 個封存帳戶有新觀察，未自動解除封存。
            </InlineAlert>
          ) : null}
          {latest.error_detail ? (
            <InlineAlert state={runUiState(latest.state)} title={latest.error_code ?? "同步資訊"}>
              {latest.error_detail}
            </InlineAlert>
          ) : null}
        </div>
      ) : <p className="muted">尚無同步紀錄。</p>}

      <DataTable<PortfolioCaptureRun>
        ariaLabel="持倉同步紀錄"
        rows={safeCapture?.recent_runs ?? []}
        columns={runColumns}
        rowKey={(item) => item.id}
        rowLabel={(item) => `同步 ${item.id}`}
        emptyText="尚無同步紀錄"
      />

      {safeCapture?.review ? (
        <div className="portfolio-capture-review">
          <div className="ui-section-head">
            <div className="ui-action-row">
              <strong>待套用差異</strong>
              <StatusBadge state="partial" label={`${safeCapture.review.changes.length} 項變更`} />
            </div>
            {safeCapture.review.changes.length > 0 ? (
              <Button
                tone="primary"
                icon={<Check size={15} />}
                onClick={() => void applyReview(safeCapture.review!.run_id)}
                busy={busy === "apply"}
                disabled={busy != null || safeCapture.running}
              >
                套用同步
              </Button>
            ) : null}
          </div>
          <DataTable<PortfolioCaptureReviewChange>
            ariaLabel="持倉同步待檢視差異"
            rows={safeCapture.review.changes}
            columns={reviewColumns}
            rowKey={(item) => `${safeCapture.review!.run_id}-${item.account_id ?? item.broker_account_id_hash}-${item.broker_con_id}-${item.kind}`}
            rowLabel={(item) => item.symbol}
            emptyText="沒有待套用差異"
          />
        </div>
      ) : null}
    </section>
  );
}
