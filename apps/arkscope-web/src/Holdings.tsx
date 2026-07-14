import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import { Plus, RefreshCw, Save, X } from "lucide-react";
import {
  closePortfolioPosition,
  createManualPosition,
  getPortfolio,
  getPortfolioOverview,
  updatePortfolioAccount,
  updatePortfolioPosition,
  type PortfolioOverview,
  type PortfolioPosition,
  type PortfolioSnapshot,
  type PositionUpdate,
} from "./api";
import {
  PortfolioAccountDetails,
  PortfolioAccountSummary,
} from "./PortfolioAccountOverview";
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

type PortfolioView = "holdings" | "account_details" | "sync_records";

const PORTFOLIO_VIEWS: Array<{ id: PortfolioView; label: string }> = [
  { id: "holdings", label: "持倉" },
  // Slice 3 inserts the activity view here.
  { id: "account_details", label: "帳戶明細" },
  { id: "sync_records", label: "同步紀錄" },
];

export function HoldingsView() {
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  const [overview, setOverview] = useState<PortfolioOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [overviewErr, setOverviewErr] = useState<string | null>(null);
  const [includeClosed, setIncludeClosed] = useState(false);
  const [activeView, setActiveView] = useState<PortfolioView>("holdings");
  const [positionAccountId, setPositionAccountId] = useState<number | "all">("all");
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
  const tabRefs = useRef<Record<PortfolioView, HTMLButtonElement | null>>({
    holdings: null,
    account_details: null,
    sync_records: null,
  });

  const manualAccount = useMemo(
    () => snapshot?.accounts.find((a) => a.broker === "manual") ?? snapshot?.accounts[0] ?? null,
    [snapshot],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    setOverviewErr(null);
    setOverview(null);
    try {
      setSnapshot(await getPortfolio(includeClosed));
      try {
        setOverview(await getPortfolioOverview());
      } catch (overviewError) {
        setOverviewErr(
          overviewError instanceof Error
            ? overviewError.message
            : String(overviewError),
        );
      }
    } catch (portfolioError) {
      setErr(
        portfolioError instanceof Error
          ? portfolioError.message
          : String(portfolioError),
      );
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
  const accounts = snapshot?.accounts ?? [];
  const accountLabels = useMemo(() => {
    const safe = new Map(
      (overview?.accounts ?? []).map((account) => [account.id, account.label]),
    );
    return new Map(
      (snapshot?.accounts ?? []).map((account) => [
        account.id,
        safe.get(account.id) ?? account.label,
      ]),
    );
  }, [overview, snapshot]);
  const filteredPositions = positionAccountId === "all"
    ? positions
    : positions.filter((position) => position.account_id === positionAccountId);
  const optionPositions = filteredPositions.filter(
    (position) => position.asset_class === "option",
  );
  const standardPositions = filteredPositions.filter(
    (position) => position.asset_class !== "option",
  );

  useEffect(() => {
    if (
      positionAccountId !== "all"
      && !accounts.some((account) => account.id === positionAccountId)
    ) {
      setPositionAccountId("all");
    }
  }, [accounts, positionAccountId]);

  function onTabKeyDown(
    event: ReactKeyboardEvent<HTMLButtonElement>,
    current: PortfolioView,
  ) {
    const currentIndex = PORTFOLIO_VIEWS.findIndex((view) => view.id === current);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % PORTFOLIO_VIEWS.length;
    }
    if (event.key === "ArrowLeft") {
      nextIndex = (
        currentIndex - 1 + PORTFOLIO_VIEWS.length
      ) % PORTFOLIO_VIEWS.length;
    }
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = PORTFOLIO_VIEWS.length - 1;
    if (nextIndex == null) return;
    event.preventDefault();
    const next = PORTFOLIO_VIEWS[nextIndex].id;
    setActiveView(next);
    tabRefs.current[next]?.focus();
  }
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

      {overviewErr ? (
        <InlineAlert state="partial" title="帳戶總覽無法載入；持倉仍可使用">
          請重新整理；若剛更新版本，請重啟應用程式後再試。
        </InlineAlert>
      ) : null}

      {overview ? (
        <PortfolioAccountSummary
          overview={overview}
          busyAccountId={
            busy?.startsWith("account-") ? Number(busy.slice(8)) : null
          }
          onToggleAggregate={(accountId, include) => {
            void onToggleAggregate(accountId, include);
          }}
        />
      ) : null}

      <div className="portfolio-view-tabs" role="tablist" aria-label="持倉檢視">
        {PORTFOLIO_VIEWS.map((view) => (
          <button
            key={view.id}
            ref={(node) => { tabRefs.current[view.id] = node; }}
            id={`portfolio-tab-${view.id}`}
            className="portfolio-view-tab"
            type="button"
            role="tab"
            tabIndex={activeView === view.id ? 0 : -1}
            aria-selected={activeView === view.id}
            aria-controls={`portfolio-panel-${view.id}`}
            onClick={() => setActiveView(view.id)}
            onKeyDown={(event) => onTabKeyDown(event, view.id)}
          >
            {view.label}
          </button>
        ))}
      </div>

      {activeView === "holdings" ? (
        <div
          id="portfolio-panel-holdings"
          role="tabpanel"
          aria-labelledby="portfolio-tab-holdings"
        >
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
                <input
                  ref={quantityRef}
                  aria-label="Quantity"
                  inputMode="decimal"
                  placeholder="1"
                />
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

          <section className="ui-section-band">
            <div className="ui-section-head">
              <h2>Positions</h2>
              <div className="ui-action-row">
                <label className="muted tiny">
                  <span>帳戶</span>
                  <select
                    aria-label="持倉帳戶篩選"
                    value={positionAccountId}
                    onChange={(event) => {
                      setPositionAccountId(
                        event.currentTarget.value === "all"
                          ? "all"
                          : Number(event.currentTarget.value),
                      );
                    }}
                  >
                    <option value="all">全部帳戶</option>
                    {accounts.map((account) => (
                      <option key={account.id} value={account.id}>
                        {accountLabels.get(account.id) ?? account.label}
                      </option>
                    ))}
                  </select>
                </label>
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
              accountLabels={accountLabels}
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
                accountLabels={accountLabels}
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
            onConfirm={() => {
              if (pendingClose) void onCloseRow(pendingClose);
            }}
          />
        </div>
      ) : null}

      {activeView === "account_details" ? (
        <div
          id="portfolio-panel-account_details"
          role="tabpanel"
          aria-labelledby="portfolio-tab-account_details"
        >
          {overview ? (
            <PortfolioAccountDetails overview={overview} />
          ) : (
            <InlineAlert
              state={loading ? "loading" : "empty"}
              title={loading ? "載入帳戶明細" : "帳戶明細目前不可用"}
            />
          )}
        </div>
      ) : null}

      {activeView === "sync_records" ? (
        <div
          id="portfolio-panel-sync_records"
          role="tabpanel"
          aria-labelledby="portfolio-tab-sync_records"
        >
          <PortfolioCapturePanel onPortfolioChanged={load} />
        </div>
      ) : null}
    </main>
  );
}

function PositionsTable({
  positions,
  accountLabels,
  emptyText,
  editingId,
  editor,
  busy,
  onEdit,
  onClose,
}: {
  positions: PortfolioPosition[];
  accountLabels: ReadonlyMap<number, string>;
  emptyText: string;
  editingId: number | null;
  editor: ReactNode;
  busy: string | null;
  onEdit: (position: PortfolioPosition) => void;
  onClose: (position: PortfolioPosition, trigger: HTMLButtonElement) => void;
}) {
  const columns: DataTableColumn<PortfolioPosition>[] = [
    {
      id: "account",
      header: "Account",
      render: (position) => (
        accountLabels.get(position.account_id) ?? `#${position.account_id}`
      ),
    },
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

function formatMaybe(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "";
  return formatNum(value);
}

function formatNum(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(value);
}
