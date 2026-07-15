import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { RefreshCw, RotateCcw } from "lucide-react";

import {
  deletePortfolioActivityAnnotation,
  getPortfolioActivity,
  isPortfolioAnnotatableActivity,
  isPortfolioBrokerActivity,
  putPortfolioActivityAnnotation,
  type PortfolioActivityAnnotation,
  type PortfolioActivityFilters,
  type PortfolioActivityItem,
  type PortfolioActivityPage,
  type PortfolioAnnotatableActivityItem,
  type PortfolioIntentLabel,
} from "./api";
import { formatMarketTimestamp, formatSystemTimestamp } from "./timeDisplay";
import {
  Button,
  ConfirmDialog,
  DataTable,
  Drawer,
  InlineAlert,
  StatusBadge,
  type DataTableAction,
  type DataTableColumn,
} from "./ui";

const INTENT_LABELS_ZH: Record<PortfolioIntentLabel, string> = {
  profit_take: "獲利了結",
  stop_loss: "停損",
  rebalance: "再平衡",
  thesis_broken: "投資論點失效",
  cash_need: "資金需求",
  other: "其他",
};

const SOURCE_LABELS = {
  broker: "Broker",
  manual: "手動紀錄",
  system: "系統覆蓋",
} as const;

const OUTCOME_LABELS = {
  gain: "已實現獲利",
  loss: "已實現虧損",
  flat: "已實現損益為零",
  unknown: "結果未知",
} as const;

const initialDraft = {
  date_from_et: "",
  date_to_et: "",
  account_id: "",
  symbol: "",
  source: "",
  state: "",
};

type FilterDraft = typeof initialDraft;

export function PortfolioActivity({
  localTimeZone,
}: {
  localTimeZone?: string;
}) {
  const [page, setPage] = useState<PortfolioActivityPage | null>(null);
  const [draft, setDraft] = useState<FilterDraft>(initialDraft);
  const [activeFilters, setActiveFilters] = useState<PortfolioActivityFilters>({});
  const [loading, setLoading] = useState(true);
  const [appending, setAppending] = useState(false);
  const [readFailed, setReadFailed] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editorId, setEditorId] = useState<string | null>(null);
  const [intentDraft, setIntentDraft] = useState<PortfolioIntentLabel | "">("");
  const [noteDraft, setNoteDraft] = useState("");
  const [mutationBusy, setMutationBusy] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const requestGeneration = useRef(0);
  const editorReturnFocusRef = useRef<HTMLElement | null>(null);
  const deleteReturnFocusRef = useRef<HTMLButtonElement | null>(null);

  const load = useCallback(async (
    filters: PortfolioActivityFilters,
    append = false,
  ) => {
    const generation = ++requestGeneration.current;
    if (append) setAppending(true);
    else {
      setPage(null);
      setLoading(true);
      setReadFailed(false);
    }
    try {
      const loaded = await getPortfolioActivity(filters);
      if (generation !== requestGeneration.current) return;
      setPage((current) => append && current
        ? appendActivityPage(current, loaded)
        : loaded);
      setReadFailed(false);
    } catch {
      if (generation !== requestGeneration.current) return;
      setReadFailed(true);
    } finally {
      if (generation !== requestGeneration.current) return;
      if (append) setAppending(false);
      else setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load({});
  }, [load]);

  const editorItem = page?.items.find((item) => item.id === editorId);
  const annotatableEditorItem = editorItem && isPortfolioAnnotatableActivity(editorItem)
    ? editorItem
    : null;

  const updateDraft = (key: keyof FilterDraft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const applyFilters = () => {
    const filters = filtersFromDraft(draft);
    setActiveFilters(filters);
    setExpandedId(null);
    void load(filters);
  };

  const resetFilters = () => {
    setDraft(initialDraft);
    setActiveFilters({});
    setExpandedId(null);
    void load({});
  };

  const openEditor = (
    item: PortfolioAnnotatableActivityItem,
    trigger: HTMLButtonElement,
  ) => {
    editorReturnFocusRef.current = trigger;
    setEditorId(item.id);
    setIntentDraft(item.annotation?.intent_label ?? "");
    setNoteDraft(item.annotation?.note ?? "");
    setMutationError(null);
  };

  const closeEditor = () => {
    if (mutationBusy) return;
    setEditorId(null);
    setConfirmDelete(false);
    setMutationError(null);
  };

  const saveAnnotation = async () => {
    if (!annotatableEditorItem) return;
    setMutationBusy(true);
    setMutationError(null);
    try {
      const annotation = await putPortfolioActivityAnnotation(
        annotatableEditorItem.id,
        { intent_label: intentDraft || null, note: noteDraft },
      );
      replaceLocalAnnotation(annotatableEditorItem.id, annotation, setPage);
      setEditorId(null);
    } catch {
      setMutationError("註記未儲存；請重試");
    } finally {
      setMutationBusy(false);
    }
  };

  const deleteAnnotation = async () => {
    if (!annotatableEditorItem) return;
    setMutationBusy(true);
    setMutationError(null);
    try {
      await deletePortfolioActivityAnnotation(annotatableEditorItem.id);
      replaceLocalAnnotation(annotatableEditorItem.id, null, setPage);
      setConfirmDelete(false);
      setEditorId(null);
    } catch {
      setMutationError("註記未清除；請重試");
      setConfirmDelete(false);
    } finally {
      setMutationBusy(false);
    }
  };

  const columns: DataTableColumn<PortfolioActivityItem>[] = [
    {
      id: "time",
      header: "時間",
      className: "portfolio-activity-time",
      render: (item) => isPortfolioBrokerActivity(item)
        ? formatMarketTimestamp(item.occurred_at_utc, { localTimeZone })
        : formatSystemTimestamp(item.occurred_at_utc, { localTimeZone }),
    },
    {
      id: "account",
      header: "帳戶",
      render: (item) => item.account?.label ?? "全部帳戶",
    },
    {
      id: "event",
      header: "Symbol / 事件",
      render: (item) => eventLabel(item),
    },
    {
      id: "source",
      header: "來源",
      render: (item) => SOURCE_LABELS[item.source],
    },
    {
      id: "objective",
      header: "客觀結果",
      render: (item) => <ObjectiveSummary item={item} />,
    },
    {
      id: "intent",
      header: "確認意圖",
      render: (item) => <IntentSummary item={item} />,
    },
  ];

  const actions = (item: PortfolioActivityItem): DataTableAction<PortfolioActivityItem>[] => {
    const rowActions: DataTableAction<PortfolioActivityItem>[] = [{
      id: "detail",
      label: expandedId === item.id ? "收合明細" : "查看明細",
      onSelect: () => setExpandedId((current) => current === item.id ? null : item.id),
    }];
    if (isPortfolioAnnotatableActivity(item)) {
      rowActions.push({
        id: "annotation",
        label: "編輯註記",
        onSelect: (_, trigger) => openEditor(item, trigger),
      });
    }
    return rowActions;
  };

  return (
    <section className="portfolio-activity" aria-label="投資組合活動">
      <div className="portfolio-activity-head">
        <div>
          <h2>活動紀錄</h2>
          <p className="muted">日期篩選以美東時間（ET）為準。</p>
        </div>
        {loading ? (
          <StatusBadge state="loading" label="載入活動" />
        ) : page ? (
          <StatusBadge state={page.items.length ? "ready" : "empty"} label={`已載入 ${page.items.length} 筆`} />
        ) : null}
      </div>

      <form
        className="portfolio-activity-filters"
        onSubmit={(event) => {
          event.preventDefault();
          applyFilters();
        }}
      >
        <label>
          開始日期（ET）
          <input aria-label="開始日期（ET）" type="date" value={draft.date_from_et} onChange={(event) => updateDraft("date_from_et", event.currentTarget.value)} />
        </label>
        <label>
          結束日期（ET）
          <input aria-label="結束日期（ET）" type="date" value={draft.date_to_et} onChange={(event) => updateDraft("date_to_et", event.currentTarget.value)} />
        </label>
        <label>
          帳戶
          <select aria-label="帳戶篩選" value={draft.account_id} onChange={(event) => updateDraft("account_id", event.currentTarget.value)}>
            <option value="">全部帳戶</option>
            {page?.accounts.map((activityAccount) => (
              <option key={activityAccount.id} value={activityAccount.id}>{activityAccount.label}</option>
            ))}
          </select>
        </label>
        <label>
          Symbol
          <input aria-label="Symbol 篩選" value={draft.symbol} onChange={(event) => updateDraft("symbol", event.currentTarget.value)} />
        </label>
        <label>
          來源
          <select aria-label="來源篩選" value={draft.source} onChange={(event) => updateDraft("source", event.currentTarget.value)}>
            <option value="">全部來源</option>
            <option value="broker">Broker</option>
            <option value="manual">手動紀錄</option>
            <option value="system">系統覆蓋</option>
          </select>
        </label>
        <label>
          狀態
          <select aria-label="狀態篩選" value={draft.state} onChange={(event) => updateDraft("state", event.currentTarget.value)}>
            <option value="">全部狀態</option>
            <option value="realized_gain">已實現獲利</option>
            <option value="realized_loss">已實現虧損</option>
            <option value="realized_flat">已實現損益為零</option>
            <option value="outcome_unknown">結果未知</option>
            <option value="unmatched">未匹配變動</option>
            <option value="manual_adjustment">手動調整</option>
            <option value="coverage_gap">覆蓋缺口</option>
            <option value="history_start">歷史起點</option>
          </select>
        </label>
        <div className="portfolio-activity-filter-actions">
          <Button type="submit" size="compact" icon={<RefreshCw size={15} />}>套用篩選</Button>
          <Button type="button" size="compact" tone="ghost" icon={<RotateCcw size={15} />} onClick={resetFilters}>重設</Button>
        </div>
      </form>

      {readFailed ? (
        <InlineAlert
          state="failed"
          title="活動載入失敗；請重新整理"
          action={<Button size="compact" onClick={() => void load(activeFilters)}>重新整理</Button>}
        />
      ) : null}

      {page ? (
        <>
          <p className="portfolio-activity-history muted">
            {page.history_started_at_utc
              ? `活動歷史起點：${formatSystemTimestamp(page.history_started_at_utc, { localTimeZone })}`
              : "活動歷史尚未開始；目前沒有可確認的 Broker 擷取範圍。"}
          </p>
          <DataTable<PortfolioActivityItem>
            ariaLabel="投資組合活動紀錄"
            rows={page.items}
            columns={columns}
            rowKey={(item) => item.id}
            rowLabel={(item) => eventLabel(item)}
            emptyText="尚無活動紀錄"
            actions={actions}
            renderExpandedRow={(item) => expandedId === item.id
              ? <ActivityDetail item={item} localTimeZone={localTimeZone} />
              : null}
          />
          {page.next_cursor ? (
            <div className="portfolio-activity-more">
              <Button
                size="compact"
                busy={appending}
                onClick={() => void load({ ...activeFilters, cursor: page.next_cursor ?? undefined }, true)}
              >
                載入更多
              </Button>
            </div>
          ) : null}
        </>
      ) : null}

      <Drawer
        open={Boolean(annotatableEditorItem)}
        title="編輯活動註記"
        onClose={closeEditor}
        returnFocusRef={editorReturnFocusRef}
        footer={(
          <div className="portfolio-activity-editor-actions">
            {annotatableEditorItem?.annotation ? (
              <Button ref={deleteReturnFocusRef} tone="danger" disabled={mutationBusy} onClick={() => setConfirmDelete(true)}>清除註記</Button>
            ) : null}
            <span className="portfolio-activity-editor-spacer" />
            <Button disabled={mutationBusy} onClick={closeEditor}>取消</Button>
            <Button
              tone="primary"
              busy={mutationBusy}
              disabled={!intentDraft && !noteDraft.trim()}
              onClick={() => void saveAnnotation()}
            >
              儲存註記
            </Button>
          </div>
        )}
      >
        <div className="portfolio-activity-editor">
          <label>
            確認意圖
            <select aria-label="確認意圖" value={intentDraft} onChange={(event) => setIntentDraft(event.currentTarget.value as PortfolioIntentLabel | "")}>
              <option value="">未確認</option>
              {Object.entries(INTENT_LABELS_ZH).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            註記
            <textarea aria-label="註記" rows={7} value={noteDraft} onChange={(event) => setNoteDraft(event.currentTarget.value)} />
          </label>
          {mutationError ? <InlineAlert state="failed" title={mutationError} /> : null}
        </div>
      </Drawer>

      <ConfirmDialog
        open={confirmDelete}
        title="清除活動註記"
        consequence="已確認的意圖與註記將被清除；Broker 與手動活動事實不受影響。"
        confirmLabel="確認清除"
        busy={mutationBusy}
        onConfirm={() => void deleteAnnotation()}
        onCancel={() => setConfirmDelete(false)}
        returnFocusRef={deleteReturnFocusRef}
        fallbackFocusRef={editorReturnFocusRef}
      />
    </section>
  );
}

function filtersFromDraft(draft: FilterDraft): PortfolioActivityFilters {
  return {
    ...(draft.date_from_et ? { date_from_et: draft.date_from_et } : {}),
    ...(draft.date_to_et ? { date_to_et: draft.date_to_et } : {}),
    ...(draft.account_id ? { account_id: Number(draft.account_id) } : {}),
    ...(draft.symbol.trim() ? { symbol: draft.symbol.trim() } : {}),
    ...(draft.source ? { source: draft.source as PortfolioActivityFilters["source"] } : {}),
    ...(draft.state ? { state: draft.state as PortfolioActivityFilters["state"] } : {}),
  };
}

function appendActivityPage(
  current: PortfolioActivityPage,
  loaded: PortfolioActivityPage,
): PortfolioActivityPage {
  const items = [...current.items];
  const seen = new Set(items.map((item) => item.id));
  for (const item of loaded.items) {
    if (!seen.has(item.id)) {
      seen.add(item.id);
      items.push(item);
    }
  }
  return {
    ...loaded,
    accounts: loaded.accounts.length ? loaded.accounts : current.accounts,
    history_started_at_utc: loaded.history_started_at_utc ?? current.history_started_at_utc,
    items,
    summary: { ...loaded.summary, item_count: items.length },
  };
}

function replaceLocalAnnotation(
  id: string,
  annotation: PortfolioActivityAnnotation | null,
  setPage: React.Dispatch<React.SetStateAction<PortfolioActivityPage | null>>,
) {
  setPage((current) => current ? {
    ...current,
    items: current.items.map((item) => item.id === id && isPortfolioAnnotatableActivity(item)
      ? { ...item, annotation } as PortfolioActivityItem
      : item),
  } : current);
}

function eventLabel(item: PortfolioActivityItem): string {
  switch (item.kind) {
    case "order": return item.symbol ? `${item.symbol} 訂單成交` : "訂單成交";
    case "execution": return item.symbol ? `${item.symbol} 獨立成交` : "獨立成交";
    case "unmatched": return item.symbol ? `${item.symbol} 未匹配變動` : "未匹配變動";
    case "manual_adjustment": return `${item.symbol} 手動調整`;
    case "coverage_gap": return item.reason_code === "broker_day_gap" ? "Broker 日期覆蓋缺口" : "成交覆蓋不完整";
    case "history_start": return "活動歷史起點";
  }
}

function ObjectiveSummary({ item }: { item: PortfolioActivityItem }) {
  let content: ReactNode;
  switch (item.kind) {
    case "order":
    case "execution":
      content = (
        <>
          <strong>{OUTCOME_LABELS[item.objective.realized_outcome]}</strong>
          <span className="muted tiny">{sideLabel(item.objective.side)} · {formatNumber(item.objective.quantity)}</span>
        </>
      );
      break;
    case "unmatched":
      content = <><strong>未匹配持倉變動</strong><span className="muted tiny">殘差 {formatNumber(item.residual_quantity)}</span></>;
      break;
    case "manual_adjustment":
      content = <><strong>手動調整</strong><span className="muted tiny">{manualActionLabel(item.action)}</span></>;
      break;
    case "coverage_gap":
      content = <StatusBadge state={item.reason_code === "broker_day_gap" ? "stale" : "partial"} label="覆蓋不完整" />;
      break;
    case "history_start":
      content = <StatusBadge state="ready" label="歷史起點" />;
      break;
  }
  return <div className="portfolio-activity-objective">{content}</div>;
}

function IntentSummary({ item }: { item: PortfolioActivityItem }) {
  if (!isPortfolioAnnotatableActivity(item)) {
    return <div className="portfolio-activity-intent muted">不適用</div>;
  }
  const label = item.annotation?.intent_label
    ? INTENT_LABELS_ZH[item.annotation.intent_label]
    : "未確認";
  return (
    <div className="portfolio-activity-intent">
      <strong>{label}</strong>
      {item.annotation?.note ? <span className="muted tiny">{item.annotation.note}</span> : null}
    </div>
  );
}

function ActivityDetail({
  item,
  localTimeZone,
}: {
  item: PortfolioActivityItem;
  localTimeZone?: string;
}) {
  let content: ReactNode;
  switch (item.kind) {
    case "order":
    case "execution":
      content = (
        <div className="portfolio-activity-fill-list">
          <dl className="portfolio-activity-detail-grid">
            <Detail label="成交均價" value={formatNumber(item.objective.average_price)} />
            <Detail label="名目金額（確定性算術）" value={formatNumber(item.objective.gross_notional)} />
            <Detail label="佣金" value={formatAmount(item.objective.commission, item.objective.commission_currency)} />
            <Detail label="已實現損益" value={formatAmount(item.objective.realized_pnl, item.currency)} />
            <Detail label="持倉方向" value={positionDirectionLabel(item.objective.position_direction)} />
            <Detail label="平倉範圍" value={closeScopeLabel(item.objective.close_scope)} />
          </dl>
          {item.fills.map((fill) => (
            <section key={fill.family_root_id} className="portfolio-activity-fill">
              <strong>成交家族 #{fill.family_root_id}</strong>
              {fill.revisions.map((execution) => (
                <div key={execution.id} className="portfolio-activity-revision">
                  <span className="portfolio-activity-revision-head">
                    Exec {execution.exec_id}
                    {execution.corrects_exec_id ? ` · 修正 ${execution.corrects_exec_id}` : ""}
                    {execution.is_effective ? " · 生效版本" : " · 歷史版本"}
                  </span>
                  <span className="muted tiny">
                    {execution.side} {formatNumber(execution.quantity)} @ {formatNumber(execution.price)} · {formatMarketTimestamp(execution.execution_time_utc, { localTimeZone })}
                  </span>
                  <span className="muted tiny">
                    首次觀察 Run #{execution.first_observed_run_id} · {formatSystemTimestamp(execution.first_observed_at_utc, { localTimeZone })}
                  </span>
                  {execution.commission_revisions.length ? (
                    <ul>
                      {execution.commission_revisions.map((commission) => (
                        <li key={commission.id}>
                          Commission #{commission.id} · {formatAmount(commission.commission, commission.currency)} · 已實現損益 {formatAmount(commission.realized_pnl, commission.currency)} · 首次觀察 Run #{commission.first_observed_run_id} · {formatSystemTimestamp(commission.first_observed_at_utc, { localTimeZone })} · Yield {formatNumber(commission.yield_value)} · 贖回日 {commission.yield_redemption_date ?? "未知"}{commission.is_latest ? " · 最新" : ""}
                        </li>
                      ))}
                    </ul>
                  ) : <span className="muted tiny">佣金修訂：未知</span>}
                </div>
              ))}
            </section>
          ))}
        </div>
      );
      break;
    case "unmatched":
      content = (
        <dl className="portfolio-activity-detail-grid">
          <Detail label="調整前" value={formatNumber(item.before_quantity)} />
          <Detail label="調整後" value={formatNumber(item.after_quantity)} />
          <Detail label="預期" value={formatNumber(item.expected_quantity)} />
          <Detail label="殘差" value={formatNumber(item.residual_quantity)} />
          <Detail label="Capture 範圍" value={`Run #${item.from_run_id} → #${item.to_run_id}`} />
          <Detail label="時間窗" value={`${formatSystemTimestamp(item.from_as_of_utc, { localTimeZone })} → ${formatSystemTimestamp(item.to_as_of_utc, { localTimeZone })}`} />
          <Detail label="成交覆蓋" value={coverageLabel(item.execution_coverage)} />
          <Detail label="原因" value={item.reason_code || "未知"} />
        </dl>
      );
      break;
    case "manual_adjustment":
      content = (
        <div className="portfolio-activity-change-list">
          <span>Position #{item.position_id} · {manualActionLabel(item.action)}</span>
          {item.changes.map((change, index) => (
            <div key={`${change.field}-${index}`}>
              <strong>{change.field}</strong> {formatUnknown(change.before)} → {formatUnknown(change.after)}
            </div>
          ))}
        </div>
      );
      break;
    case "coverage_gap":
      content = (
        <dl className="portfolio-activity-detail-grid">
          <Detail label="Capture 範圍" value={`Run #${item.from_run_id ?? "未知"} → #${item.to_run_id}`} />
          <Detail label="開始" value={item.from_as_of_utc
            ? formatSystemTimestamp(item.from_as_of_utc, { localTimeZone })
            : "未知"} />
          <Detail label="結束" value={formatSystemTimestamp(item.to_as_of_utc, { localTimeZone })} />
          <Detail label="原因" value={eventLabel(item)} />
        </dl>
      );
      break;
    case "history_start":
      content = <span>首次成功擷取 Run #{item.capture_run_id} · {formatSystemTimestamp(item.occurred_at_utc, { localTimeZone })}</span>;
      break;
  }
  return <div className="portfolio-activity-detail">{content}</div>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}{" "}</dt><dd>{value}</dd></div>;
}

function formatNumber(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "未知";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(value);
}

function formatAmount(value: number | null, currency: string | null): string {
  const number = formatNumber(value);
  return number === "未知" ? number : currency ? `${number} ${currency}` : number;
}

function formatUnknown(value: unknown): string {
  if (value == null) return "未知";
  if (typeof value === "string") return value || "未知";
  if (typeof value === "number") return Number.isFinite(value) ? formatNumber(value) : "未知";
  if (typeof value === "boolean") return value ? "true" : "false";
  try {
    return JSON.stringify(value) || "未知";
  } catch {
    return "未知";
  }
}

function sideLabel(value: "buy" | "sell" | "mixed" | "unknown") {
  return { buy: "買進", sell: "賣出", mixed: "混合", unknown: "方向未知" }[value];
}

function manualActionLabel(value: "create" | "update" | "close") {
  return { create: "建立", update: "更新", close: "關閉" }[value];
}

function coverageLabel(value: "complete" | "incomplete" | "gap") {
  return { complete: "覆蓋完整", incomplete: "覆蓋不完整", gap: "覆蓋缺口" }[value];
}

function positionDirectionLabel(value: "increase" | "reduce" | "unknown") {
  return { increase: "增加", reduce: "減少", unknown: "未知" }[value];
}

function closeScopeLabel(value: "none" | "partial" | "complete" | "unknown") {
  return { none: "未平倉", partial: "部分平倉", complete: "完全平倉", unknown: "未知" }[value];
}
