import { useCallback, useEffect, useRef, useState } from "react";
import { Menu } from "lucide-react";
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
import { BackgroundWorkIndicator } from "./shell/BackgroundWorkIndicator";
import { useResearchWorkRegistry } from "./shell/researchWork";
import { readDeveloperMode, writeDeveloperMode } from "./shell/shellPreferences";
import { Drawer } from "./ui/Drawer";
import { IconButton } from "./ui/Button";
import { useShellOverlay } from "./ui/useShellOverlay";
import {
  nextNavigationRequest,
  resolveNavigationTarget,
  shellViewLabel,
  type NavigationTarget,
  type ResearchNavigationRequest,
  type SettingsNavigationRequest,
  type ShellView,
} from "./shell/navigation";

export function App() {
  const [status, setStatus] = useState<StatusState>({ kind: "loading" });
  const [view, setView] = useState<ShellView>("Home");
  const [lastOk, setLastOk] = useState<string | null>(null);
  const [runtime, setRuntime] = useState<RuntimeConfig | null>(null);
  const [developerMode, setDeveloperMode] = useState(() => readDeveloperMode());
  // Full-page ticker detail overlay (null = show the selected nav view).
  const [detail, setDetail] = useState<{ ticker: string } | null>(null);
  const navigationSequenceRef = useRef(0);
  const [researchNavigation, setResearchNavigation] = useState<ResearchNavigationRequest | null>(null);
  const [settingsNavigation, setSettingsNavigation] = useState<SettingsNavigationRequest | null>(null);
  const researchWork = useResearchWorkRegistry();
  const shellOverlay = useShellOverlay();
  const [navigationOpen, setNavigationOpen] = useState(false);

  const navigate = useCallback((target: NavigationTarget) => {
    const request = nextNavigationRequest(navigationSequenceRef.current, target);
    navigationSequenceRef.current = request.sequence;
    const resolved = resolveNavigationTarget(request);
    setDetail(resolved.ticker ? { ticker: resolved.ticker } : null);
    if (resolved.view) setView(resolved.view);
    if (resolved.research) setResearchNavigation(resolved.research);
    if (resolved.settings) setSettingsNavigation(resolved.settings);
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

  useEffect(() => {
    if (!shellOverlay) setNavigationOpen(false);
  }, [shellOverlay]);

  const researchSessionSeconds = runtime?.research_runtime.session_timeout_s;
  const researchSessionBoundMs = typeof researchSessionSeconds === "number"
    && Number.isFinite(researchSessionSeconds)
    && researchSessionSeconds >= 0
    ? researchSessionSeconds * 1_000
    : null;

  const selectedSurface = detail ? (
    <TickerDetailView
      key={detail.ticker}
      ticker={detail.ticker}
      onBack={() => setDetail(null)}
      runtime={runtime}
    />
  ) : view === "Home" ? (
    <HomeView
      status={status}
      onNavigate={(next) => navigate({ kind: "view", view: next })}
      onOpenTicker={(ticker) => navigate({ kind: "ticker", ticker })}
      runtime={runtime}
    />
  ) : view === "Watchlist" ? (
    <WatchlistView onOpenTicker={(ticker) => navigate({ kind: "ticker", ticker })} />
  ) : view === "Universe" ? (
    <UniverseView onOpenTicker={(ticker) => navigate({ kind: "ticker", ticker })} />
  ) : view === "News" ? (
    <NewsView onOpenTicker={(ticker) => navigate({ kind: "ticker", ticker })} />
  ) : view === "Research" ? (
    <ResearchView
      onOpenTicker={(ticker) => navigate({ kind: "ticker", ticker })}
      navigationRequest={researchNavigation}
      onNavigationConsumed={(sequence) => {
        setResearchNavigation((current) => (
          current?.sequence === sequence ? null : current
        ));
      }}
      onObserveRun={researchWork.observeRun}
    />
  ) : view === "Holdings" ? (
    <HoldingsView />
  ) : view === "System" ? (
    <DashboardView
      status={status}
      runtime={runtime}
      onRetry={refresh}
      developerMode={developerMode}
      onDeveloperModeChange={updateDeveloperMode}
      onNavigate={navigate}
    />
  ) : (
    <SettingsView
      runtime={runtime}
      onRuntimeChanged={refreshRuntime}
      navigationRequest={settingsNavigation}
    />
  );

  return (
    <div className="app-shell" data-shell-overlay={String(shellOverlay)}>
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
        workControl={researchWork.activeCount > 0 || researchWork.attentionCount > 0 ? (
          <BackgroundWorkIndicator
            work={researchWork}
            researchSessionBoundMs={researchSessionBoundMs}
            onNavigate={navigate}
          />
        ) : undefined}
        onNavigate={navigate}
        menuControl={shellOverlay ? (
          <IconButton
            icon={<Menu size={18} />}
            label="開啟導覽"
            tone="ghost"
            onClick={() => setNavigationOpen(true)}
          />
        ) : null}
      />

      <div className="app-shell-layout">
        {!shellOverlay ? (
          <aside className="app-shell-navigation" aria-label="主要導覽">
            <ShellNavigation currentView={view} onNavigate={navigate} />
          </aside>
        ) : null}
        <div className="app-shell-content">{selectedSurface}</div>
      </div>

      <Drawer
        open={shellOverlay && navigationOpen}
        title="導覽"
        onClose={() => setNavigationOpen(false)}
      >
        <nav className="app-shell-navigation-drawer" aria-label="主要導覽">
          <ShellNavigation
            currentView={view}
            onNavigate={navigate}
            onAfterNavigate={() => setNavigationOpen(false)}
          />
        </nav>
      </Drawer>
    </div>
  );
}
