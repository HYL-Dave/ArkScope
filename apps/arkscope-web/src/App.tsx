import { useCallback, useEffect, useState } from "react";
import { apiBase, getStatus, type ApiStatus } from "./api";

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; status: ApiStatus }
  | { kind: "error"; message: string };

const NAV = ["Dashboard", "Watchlist", "News", "Signals", "Options", "Reports", "Settings"];

export function App() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [lastOk, setLastOk] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const status = await getStatus();
      setState({ kind: "ready", status });
      setLastOk(new Date().toLocaleTimeString());
    } catch (e) {
      setState({ kind: "error", message: e instanceof Error ? e.message : String(e) });
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 10_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const dotClass = state.kind === "ready" ? "ok" : state.kind === "error" ? "bad" : "wait";

  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">ArkScope</span>
        <span className={`dot ${dotClass}`} />
        <span className="topbar-status">
          {state.kind === "ready"
            ? `sidecar ok · ${state.status.tools_registered} tools`
            : state.kind === "error"
              ? "sidecar unreachable"
              : "connecting…"}
        </span>
        <span className="spacer" />
        <span className="topbar-meta">{apiBase}</span>
        {lastOk && <span className="topbar-meta">updated {lastOk}</span>}
      </header>

      <div className="body">
        <nav className="leftnav">
          {NAV.map((label, i) => (
            <button key={label} className={`navitem ${i === 0 ? "active" : ""}`} disabled={i !== 0}>
              {label}
            </button>
          ))}
        </nav>

        <main className="main">
          {state.kind === "loading" && <p className="muted">Connecting to the local sidecar…</p>}
          {state.kind === "error" && (
            <div className="errorbox">
              <p>
                Could not reach the sidecar at <code>{apiBase}</code>.
              </p>
              <p className="muted">{state.message}</p>
              <button onClick={() => void refresh()}>Retry</button>
            </div>
          )}
          {state.kind === "ready" && <Dashboard status={state.status} />}
        </main>

        <aside className="rightpanel">
          <h3>Agent</h3>
          <p className="muted">
            Embedded agent panel — placeholder. AI lives in every page, not a separate chat tab
            (vision §1/§3). Wiring is deferred past the shell spike.
          </p>
        </aside>
      </div>
    </div>
  );
}

function Dashboard({ status }: { status: ApiStatus }) {
  return (
    <div className="dashboard">
      <section className="tilerow">
        <Tile label="Registry tools" value={status.tools_registered} />
        <Tile label="Server time" value={new Date(status.timestamp).toLocaleTimeString()} />
        <Tile label="Status" value={status.status} />
      </section>

      <h2 className="section">Tool categories</h2>
      <div className="grid">
        {Object.entries(status.tool_categories).map(([k, v]) => (
          <Tile key={k} label={k} value={v} />
        ))}
      </div>

      <h2 className="section">Data sources (tickers)</h2>
      <div className="grid">
        {Object.entries(status.data_sources).map(([k, v]) => (
          <Tile key={k} label={k.replace(/_/g, " ")} value={v} />
        ))}
      </div>
    </div>
  );
}

function Tile({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="tile">
      <div className="tile-value">{value}</div>
      <div className="tile-label">{label}</div>
    </div>
  );
}
