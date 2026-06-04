import { useCallback, useEffect, useState } from "react";
import { apiBase, getStatus, type ApiStatus } from "./api";
import { DashboardView, type StatusState } from "./Dashboard";
import { WatchlistView } from "./Watchlist";

const NAV = ["Dashboard", "Watchlist", "News", "Signals", "Options", "Reports", "Settings"] as const;
type Nav = (typeof NAV)[number];
const ENABLED: Nav[] = ["Dashboard", "Watchlist"];

export function App() {
  const [status, setStatus] = useState<StatusState>({ kind: "loading" });
  const [view, setView] = useState<Nav>("Watchlist");
  const [lastOk, setLastOk] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await getStatus();
      setStatus({ kind: "ready", status: s });
      setLastOk(new Date().toLocaleTimeString());
    } catch (e) {
      setStatus({ kind: "error", message: e instanceof Error ? e.message : String(e) });
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(id);
  }, [refresh]);

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
        <span className="topbar-meta">{apiBase}</span>
        {lastOk && <span className="topbar-meta">updated {lastOk}</span>}
      </header>

      <div className="body">
        <nav className="leftnav">
          {NAV.map((label) => {
            const enabled = ENABLED.includes(label);
            return (
              <button
                key={label}
                className={`navitem ${view === label ? "active" : ""}`}
                disabled={!enabled}
                onClick={() => enabled && setView(label)}
              >
                {label}
              </button>
            );
          })}
        </nav>

        {view === "Dashboard" ? (
          <DashboardView status={status} onRetry={refresh} />
        ) : (
          <WatchlistView />
        )}
      </div>
    </div>
  );
}
