import { useCallback, useEffect, useState } from "react";
import { apiBase, getRuntimeConfig, getStatus, type CockpitRow, type RuntimeConfig } from "./api";
import { DashboardView, type StatusState } from "./Dashboard";
import { HomeView } from "./Home";
import { SettingsView } from "./Settings";
import { TickerDetailView } from "./TickerDetail";
import { UniverseView } from "./Universe";
import { WatchlistView } from "./Watchlist";

// Nav aligned to the desktop-app design doc (PDF p6) — MVP subset. Keys are
// stable English ids; labels follow the mockups (Chinese-primary). Most are
// stubs for now; the old dev health view is demoted from product-home to
// "System / Health".
const NAV = [
  "Home",
  "Watchlist",
  "Universe",
  "Research",
  "Holdings",
  "Alerts",
  "News",
  "Notes",
  "System",
  "Settings",
] as const;
type Nav = (typeof NAV)[number];

const ENABLED: Nav[] = ["Home", "Watchlist", "Universe", "System", "Settings"];

const LABELS: Record<Nav, string> = {
  Home: "工作台",
  Watchlist: "自選股",
  Universe: "全部標的",
  Research: "AI 研究",
  Holdings: "持倉",
  Alerts: "告警",
  News: "新聞·事件",
  Notes: "研究筆記",
  System: "System / Health",
  Settings: "設定",
};

export function App() {
  const [status, setStatus] = useState<StatusState>({ kind: "loading" });
  const [view, setView] = useState<Nav>("Home");
  const [lastOk, setLastOk] = useState<string | null>(null);
  const [runtime, setRuntime] = useState<RuntimeConfig | null>(null);
  // Full-page ticker detail overlay (null = show the selected nav view).
  const [detail, setDetail] = useState<{ ticker: string; row?: CockpitRow } | null>(null);

  const openTicker = useCallback((ticker: string, row?: CockpitRow) => {
    setDetail({ ticker, row });
  }, []);

  const goView = useCallback((next: Nav) => {
    setDetail(null);
    setView(next);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const s = await getStatus();
      setStatus({ kind: "ready", status: s });
      setLastOk(new Date().toLocaleTimeString());
    } catch (e) {
      setStatus({ kind: "error", message: e instanceof Error ? e.message : String(e) });
    }
  }, []);

  const refreshRuntime = useCallback(async () => {
    try {
      setRuntime(await getRuntimeConfig());
    } catch {
      setRuntime(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  // Runtime config (active models + key presence) changes rarely — fetch once.
  useEffect(() => {
    void refreshRuntime();
  }, [refreshRuntime]);

  const dot = status.kind === "ready" ? "ok" : status.kind === "error" ? "bad" : "wait";

  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">ArkScope</span>
        <span className={`dot ${dot}`} />
        <span className="topbar-status">
          {status.kind === "ready"
            ? `sidecar ok · ${status.status.tools_registered} tools`
            : status.kind === "error"
              ? "sidecar unreachable"
              : "connecting…"}
        </span>
        <span className="spacer" />
        {runtime && (
          <button
            type="button"
            className="topbar-model"
            onClick={() => setView("Settings")}
            title={
              `卡片合成 ${runtime.card_synthesis.provider}/${runtime.card_synthesis.model}\n` +
              `卡片翻譯 ${runtime.card_translation.provider}/${runtime.card_translation.model}\n` +
              `Anthropic key ${runtime.anthropic.key_set ? "✓" : "✗"} · OpenAI key ${runtime.openai.key_set ? "✓" : "✗"}\n` +
              "點擊進入模型設定"
            }
          >
            ✦ {runtime.card_synthesis.provider}/{runtime.card_synthesis.model}
          </button>
        )}
        <span className="topbar-meta">{apiBase}</span>
        {lastOk && <span className="topbar-meta">updated {lastOk}</span>}
      </header>

      <div className="body">
        <nav className="leftnav">
          {NAV.map((key) => {
            const enabled = ENABLED.includes(key);
            return (
              <button
                key={key}
                className={`navitem ${view === key && !detail ? "active" : ""}`}
                disabled={!enabled}
                onClick={() => enabled && goView(key)}
                title={enabled ? LABELS[key] : `${LABELS[key]} — 規劃中`}
              >
                {LABELS[key]}
              </button>
            );
          })}
        </nav>

        {detail ? (
          <TickerDetailView
            key={detail.ticker}
            ticker={detail.ticker}
            row={detail.row}
            onBack={() => setDetail(null)}
          />
        ) : view === "Home" ? (
          <HomeView status={status} onNavigate={goView} onOpenTicker={openTicker} />
        ) : view === "Watchlist" ? (
          <WatchlistView onOpenTicker={openTicker} />
        ) : view === "Universe" ? (
          <UniverseView onOpenTicker={openTicker} />
        ) : view === "System" ? (
          <DashboardView status={status} runtime={runtime} onRetry={refresh} />
        ) : view === "Settings" ? (
          <SettingsView runtime={runtime} onRuntimeChanged={refreshRuntime} />
        ) : (
          <main className="main">
            <p className="muted">{LABELS[view]} — 規劃中。</p>
          </main>
        )}
      </div>
    </div>
  );
}
