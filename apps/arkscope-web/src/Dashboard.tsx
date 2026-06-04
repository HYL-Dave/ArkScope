import type { ApiStatus } from "./api";

export type StatusState =
  | { kind: "loading" }
  | { kind: "ready"; status: ApiStatus }
  | { kind: "error"; message: string };

export function DashboardView({
  status,
  onRetry,
}: {
  status: StatusState;
  onRetry: () => void;
}) {
  return (
    <>
      <main className="main">
        {status.kind === "loading" && <p className="muted">Connecting to the local sidecar…</p>}
        {status.kind === "error" && (
          <div className="errorbox">
            <p>Could not reach the sidecar.</p>
            <p className="muted">{status.message}</p>
            <button onClick={onRetry}>Retry</button>
          </div>
        )}
        {status.kind === "ready" && <StatusTiles status={status.status} />}
      </main>

      <aside className="rightpanel">
        <h3>Agent</h3>
        <p className="muted">
          Embedded agent panel — placeholder. AI lives in every page, not a separate chat tab
          (vision §1/§3). Wiring is deferred.
        </p>
      </aside>
    </>
  );
}

function StatusTiles({ status }: { status: ApiStatus }) {
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
