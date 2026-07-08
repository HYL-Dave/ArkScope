import { useCallback, useEffect, useState } from "react";
import { apiBase, getRuntimeConfig, getStatus, type RuntimeConfig } from "./api";
import { DashboardView, type StatusState } from "./Dashboard";
import { HoldingsView } from "./Holdings";
import { HomeView } from "./Home";
import { SettingsView } from "./Settings";
import { NewsView } from "./News";
import { ResearchView } from "./Research";
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

const ENABLED: Nav[] = ["Home", "Watchlist", "Universe", "Research", "Holdings", "News", "System", "Settings"];

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
  const [detail, setDetail] = useState<{ ticker: string } | null>(null);
  // Right rail is collapsed by default — it only reserves width when opened.
  const [railOpen, setRailOpen] = useState(false);

  const openTicker = useCallback((ticker: string) => {
    setDetail({ ticker });
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
            onClick={() => goView("Settings")}
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

      <div className={`body ${railOpen ? "rail-open" : "rail-closed"}`}>
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
            onBack={() => setDetail(null)}
          />
        ) : view === "Home" ? (
          <HomeView status={status} onNavigate={goView} onOpenTicker={openTicker} />
        ) : view === "Watchlist" ? (
          <WatchlistView onOpenTicker={openTicker} />
        ) : view === "Universe" ? (
          <UniverseView onOpenTicker={openTicker} />
        ) : view === "News" ? (
          <NewsView onOpenTicker={openTicker} />
        ) : view === "Research" ? (
          <ResearchView onOpenTicker={openTicker} />
        ) : view === "Holdings" ? (
          <HoldingsView />
        ) : view === "System" ? (
          <DashboardView status={status} runtime={runtime} onRetry={refresh} />
        ) : view === "Settings" ? (
          <SettingsView runtime={runtime} onRuntimeChanged={refreshRuntime} />
        ) : (
          <main className="main">
            <p className="muted">{LABELS[view]} — 規劃中。</p>
          </main>
        )}

        {railOpen ? (
          <aside className="rightrail">
            <div className="rightrail-head">
              <h3>面板</h3>
              <span className="spacer" />
              <button className="btn-ghost" onClick={() => setRailOpen(false)} title="收合">✕</button>
            </div>
            <p className="muted tiny">
              嵌入式 AI 助手與「今日重點」（事件 / 告警 / 摘要）將放這裡。AI 嵌入各頁，
              AI 研究頁集中管理對話 threads（vision §1/§3）。規劃中。
            </p>
          </aside>
        ) : (
          <button
            className="rail-tab"
            onClick={() => setRailOpen(true)}
            title="展開側面板"
          >
            面板 ‹
          </button>
        )}
      </div>
    </div>
  );
}
