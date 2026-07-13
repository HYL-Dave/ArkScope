import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Plus, RefreshCw, Save, X } from "lucide-react";
import {
  closePortfolioPosition,
  createManualPosition,
  getPortfolio,
  updatePortfolioAccount,
  updatePortfolioPosition,
  type PortfolioPosition,
  type PortfolioSnapshot,
  type PositionUpdate,
} from "./api";
import { PortfolioCapturePanel } from "./PortfolioCapturePanel";
import {
  Button,
  ConfirmDialog,
  DataTable,
  IconButton,
  InlineAlert,
  PageHeader,
  StatusBadge,
  type DataTableColumn,
} from "./ui";

export function HoldingsView() {
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [includeClosed, setIncludeClosed] = useState(false);
  const [editing, setEditing] = useState<PortfolioPosition | null>(null);
  const [pendingClose, setPendingClose] = useState<PortfolioPosition | null>(null);
  const closeTriggerRef = useRef<HTMLElement | null>(null);
  const closedFilterRef = useRef<HTMLInputElement | null>(null);
  const tickerRef = useRef<HTMLInputElement>(null);
  const quantityRef = useRef<HTMLInputElement>(null);
  const notesRef = useRef<HTMLInputElement>(null);
  const editSymbolRef = useRef<HTMLInputElement>(null);
  const editAssetRef = useRef<HTMLInputElement>(null);
  const editQuantityRef = useRef<HTMLInputElement>(null);
  const editAvgCostRef = useRef<HTMLInputElement>(null);
  const editCurrencyRef = useRef<HTMLInputElement>(null);
  const editNotesRef = useRef<HTMLInputElement>(null);
  const editThesisRef = useRef<HTMLInputElement>(null);
  const editTagsRef = useRef<HTMLInputElement>(null);

  const manualAccount = useMemo(
    () => snapshot?.accounts.find((a) => a.broker === "manual") ?? snapshot?.accounts[0] ?? null,
    [snapshot],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      setSnapshot(await getPortfolio(includeClosed));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [includeClosed]);

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

  async function onSaveEdit() {
    if (!editing) return;
    const body: PositionUpdate = {
      notes: editNotesRef.current?.value ?? "",
      thesis: editThesisRef.current?.value ?? "",
      tags: splitTags(editTagsRef.current?.value ?? ""),
    };
    if (editing.broker === "manual") {
      const quantity = Number(editQuantityRef.current?.value ?? editing.quantity);
      if (!Number.isFinite(quantity) || quantity === 0) {
        setErr("數量必須是非零數字");
        return;
      }
      // Only a truly blank input clears avg_cost; anything non-numeric is an
      // input error, never a silent clear.
      const avgRaw = (editAvgCostRef.current?.value ?? "").trim();
      let avgCost: number | null = null;
      if (avgRaw !== "") {
        avgCost = Number(avgRaw);
        if (!Number.isFinite(avgCost)) {
          setErr("均價必須留空或為數字");
          return;
        }
      }
      body.symbol = editSymbolRef.current?.value.trim() ?? editing.symbol;
      body.asset_class = editAssetRef.current?.value.trim() ?? editing.asset_class;
      body.quantity = quantity;
      body.avg_cost = avgCost;
      body.currency = editCurrencyRef.current?.value.trim() ?? editing.currency;
    }
    setBusy(`edit-${editing.id}`);
    setErr(null);
    try {
      await updatePortfolioPosition(editing.id, body);
      setEditing(null);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function onCloseRow(position: PortfolioPosition) {
    setBusy(`close-${position.id}`);
    setErr(null);
    try {
      await closePortfolioPosition(position.id);
      if (editing?.id === position.id) setEditing(null);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
      setPendingClose(null);
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
  const viewState = err
    ? { state: "failed" as const, label: "載入失敗" }
    : snapshot == null || loading
      ? { state: "loading" as const, label: "載入持倉" }
      : busy
        ? { state: "running" as const, label: "更新中" }
        : positions.length === 0
          ? { state: "empty" as const, label: "尚無持倉" }
          : { state: "ready" as const, label: `${positions.length} 筆持倉` };
  const editorNode = editing ? (
    <div className="ui-inline-form" key={editing.id}>
      {editing.broker === "manual" && (
        <>
          <label>
            <span>Symbol</span>
            <input ref={editSymbolRef} aria-label="Edit Symbol" defaultValue={editing.symbol} />
          </label>
          <label>
            <span>Asset</span>
            <input
              ref={editAssetRef}
              aria-label="Edit Asset Class"
              defaultValue={editing.asset_class}
            />
          </label>
          <label>
            <span>Quantity</span>
            <input
              ref={editQuantityRef}
              aria-label="Edit Quantity"
              inputMode="decimal"
              defaultValue={String(editing.quantity)}
            />
          </label>
          <label>
            <span>Avg Cost</span>
            <input
              ref={editAvgCostRef}
              aria-label="Edit Avg Cost"
              inputMode="decimal"
              placeholder="留空清除"
              defaultValue={editing.avg_cost == null ? "" : String(editing.avg_cost)}
            />
          </label>
          <label>
            <span>Currency</span>
            <input ref={editCurrencyRef} aria-label="Edit Currency" defaultValue={editing.currency} />
          </label>
        </>
      )}
      <label>
        <span>Notes</span>
        <input ref={editNotesRef} aria-label="Edit Notes" defaultValue={editing.notes ?? ""} />
      </label>
      <label>
        <span>Thesis</span>
        <input ref={editThesisRef} aria-label="Edit Thesis" defaultValue={editing.thesis ?? ""} />
      </label>
      <label>
        <span>Tags</span>
        <input
          ref={editTagsRef}
          aria-label="Edit Tags"
          placeholder="逗號分隔"
          defaultValue={(editing.tags ?? []).join(", ")}
        />
      </label>
      <Button
        tone="primary"
        icon={<Save size={15} />}
        onClick={() => void onSaveEdit()}
        busy={busy === `edit-${editing.id}`}
      >
        儲存
      </Button>
      <Button icon={<X size={15} />} onClick={() => setEditing(null)}>
        取消
      </Button>
    </div>
  ) : null;

  return (
    <main className="main">
      <PageHeader
        eyebrow="Holdings"
        title="持倉"
        context={<StatusBadge state={viewState.state} label={viewState.label} />}
        actions={(
          <IconButton
            label="重新整理"
            icon={<RefreshCw size={16} />}
            onClick={() => void load()}
            disabled={loading}
          />
        )}
      />

      {err ? (
        <InlineAlert state="failed" title="持倉載入失敗">{err}</InlineAlert>
      ) : null}

      <section className="ui-section-band">
        <div className="ui-status-grid">
          {accounts.map((account) => (
            <div className="ui-metric" key={account.id}>
              <span className="ui-metric-label">{account.label}</span>
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
          <div className="ui-metric">
            <span className="ui-metric-label">Currency basis</span>
            <strong>{totals?.currency_basis === "broker_base" ? "broker-base" : "per-currency"}</strong>
            <span className="muted tiny">{currencySummary(totals)}</span>
          </div>
        </div>
      </section>

      <section className="ui-section-band">
        <div className="ui-section-head">
          <h2>新增手動持倉</h2>
        </div>
        <div className="ui-inline-form">
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
          <Button
            tone="primary"
            icon={<Plus size={15} />}
            onClick={() => void onAddManual()}
            busy={busy === "manual"}
          >
            新增持倉
          </Button>
        </div>
      </section>

      <PortfolioCapturePanel onPortfolioChanged={load} />

      <section className="ui-section-band">
        <div className="ui-section-head">
          <h2>Positions</h2>
          <div className="ui-action-row">
            <label className="muted tiny">
              <input
                ref={closedFilterRef}
                type="checkbox"
                aria-label="顯示已關閉持倉"
                checked={includeClosed}
                onChange={(event) => setIncludeClosed(event.currentTarget.checked)}
              />
              顯示已關閉
            </label>
            <span className="muted tiny">{standardPositions.length} rows</span>
          </div>
        </div>
        <PositionsTable
          positions={standardPositions}
          emptyText="尚無一般持倉"
          editingId={editing?.id ?? null}
          editor={editorNode}
          busy={busy}
          onEdit={(position) => setEditing(position)}
          onClose={(position, trigger) => {
            closeTriggerRef.current = trigger;
            setPendingClose(position);
          }}
        />
      </section>

      {optionPositions.length > 0 && (
        <section className="ui-section-band">
          <div className="ui-section-head">
            <h2>Options</h2>
            <span className="muted tiny">{optionPositions.length} rows</span>
          </div>
          <p className="muted">
            進階選擇權風險尚未建模；此區只呈現 broker 回傳的持倉快照。
          </p>
          <PositionsTable
            positions={optionPositions}
            emptyText="尚無選擇權持倉"
            editingId={editing?.id ?? null}
            editor={editorNode}
            busy={busy}
            onEdit={(position) => setEditing(position)}
            onClose={(position, trigger) => {
              closeTriggerRef.current = trigger;
              setPendingClose(position);
            }}
          />
        </section>
      )}

      <ConfirmDialog
        open={pendingClose != null}
        title={pendingClose ? `關閉 ${pendingClose.symbol}` : "關閉持倉"}
        consequence="這是軟關閉；持倉與筆記會保留，之後可在「顯示已關閉」檢視中查看。"
        confirmLabel="確認關閉"
        busy={pendingClose != null && busy === `close-${pendingClose.id}`}
        returnFocusRef={closeTriggerRef}
        fallbackFocusRef={closedFilterRef}
        onCancel={() => setPendingClose(null)}
        onConfirm={() => { if (pendingClose) void onCloseRow(pendingClose); }}
      />
    </main>
  );
}

function PositionsTable({
  positions,
  emptyText,
  editingId,
  editor,
  busy,
  onEdit,
  onClose,
}: {
  positions: PortfolioPosition[];
  emptyText: string;
  editingId: number | null;
  editor: ReactNode;
  busy: string | null;
  onEdit: (position: PortfolioPosition) => void;
  onClose: (position: PortfolioPosition, trigger: HTMLButtonElement) => void;
}) {
  const columns: DataTableColumn<PortfolioPosition>[] = [
    { id: "symbol", header: "Symbol", render: (position) => position.symbol },
    { id: "asset", header: "Asset", render: (position) => position.asset_class },
    {
      id: "quantity",
      header: "Qty",
      align: "right",
      render: (position) => formatNum(position.quantity),
    },
    { id: "currency", header: "Currency", render: (position) => position.currency },
    {
      id: "avg-cost",
      header: "Avg Cost",
      align: "right",
      render: (position) => formatMaybe(position.avg_cost),
    },
    {
      id: "market-value",
      header: "Market Value",
      align: "right",
      render: (position) => formatMaybe(position.market_value),
    },
    {
      id: "unrealized-pnl",
      header: <>Unrealized P&amp;L</>,
      align: "right",
      render: (position) => formatMaybe(position.unrealized_pnl),
    },
    { id: "notes", header: "Notes", render: (position) => position.notes ?? "" },
    {
      id: "status",
      header: "Status",
      className: "ui-data-table-status",
      render: (position) => position.closed_at
        ? <span className="muted tiny">已關閉</span>
        : position.broker === "manual"
          ? null
          : <span className="muted tiny">broker · synced</span>,
    },
  ];

  return (
    <DataTable<PortfolioPosition>
      ariaLabel="持倉"
      rows={positions}
      columns={columns}
      rowKey={(position) => position.id}
      rowLabel={(position) => position.symbol}
      emptyText={emptyText}
      actions={(position) => [
        {
          id: "edit",
          label: "編輯",
          disabled: busy != null,
          onSelect: onEdit,
        },
        ...(!position.closed_at && position.broker === "manual" ? [{
          id: "close",
          label: "關閉",
          tone: "danger" as const,
          disabled: busy != null,
          onSelect: onClose,
        }] : []),
      ]}
      renderExpandedRow={(position) => editingId === position.id ? editor : null}
    />
  );
}

function splitTags(raw: string): string[] {
  return raw
    .split(",")
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0);
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
