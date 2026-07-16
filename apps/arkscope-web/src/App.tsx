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
import { ShellNavigation } from "./shell/ShellNavigation";
import { ShellTopBar } from "./shell/ShellTopBar";
import { readDeveloperMode, writeDeveloperMode } from "./shell/shellPreferences";
import { shellViewLabel, type ShellView } from "./shell/navigation";

export function App() {
  const [status, setStatus] = useState<StatusState>({ kind: "loading" });
  const [view, setView] = useState<ShellView>("Home");
  const [lastOk, setLastOk] = useState<string | null>(null);
  const [runtime, setRuntime] = useState<RuntimeConfig | null>(null);
  const [developerMode, setDeveloperMode] = useState(() => readDeveloperMode());
  // Full-page ticker detail overlay (null = show the selected nav view).
  const [detail, setDetail] = useState<{ ticker: string } | null>(null);
  // Right rail is collapsed by default — it only reserves width when opened.
  const [railOpen, setRailOpen] = useState(false);

  const openTicker = useCallback((ticker: string) => {
    setDetail({ ticker });
  }, []);

  const goView = useCallback((next: ShellView) => {
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

  const updateDeveloperMode = useCallback((enabled: boolean) => {
    setDeveloperMode(enabled);
    writeDeveloperMode(enabled);
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

  return (
    <div className="shell">
      <ShellTopBar
        contextLabel={detail?.ticker ?? shellViewLabel(view)}
        status={status}
        developerMode={developerMode}
        diagnostics={{
          apiBase,
          toolsRegistered: status.kind === "ready" ? status.status.tools_registered : null,
          lastStatusAt: lastOk,
          cardModel: runtime
            ? `${runtime.card_synthesis.provider}/${runtime.card_synthesis.model}`
            : null,
        }}
        onNavigate={(target) => {
          if (target.kind === "view") goView(target.view);
        }}
      />

      <div className={`body ${railOpen ? "rail-open" : "rail-closed"}`}>
        <nav className="leftnav">
          <ShellNavigation currentView={view} onNavigate={(target) => {
            if (target.kind === "view") goView(target.view);
          }} />
        </nav>

        {detail ? (
          <TickerDetailView
            key={detail.ticker}
            ticker={detail.ticker}
            onBack={() => setDetail(null)}
            runtime={runtime}
          />
        ) : view === "Home" ? (
          <HomeView status={status} onNavigate={goView} onOpenTicker={openTicker} runtime={runtime} />
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
          <DashboardView
            status={status}
            runtime={runtime}
            onRetry={refresh}
            developerMode={developerMode}
            onDeveloperModeChange={updateDeveloperMode}
          />
        ) : (
          <SettingsView runtime={runtime} onRuntimeChanged={refreshRuntime} />
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
