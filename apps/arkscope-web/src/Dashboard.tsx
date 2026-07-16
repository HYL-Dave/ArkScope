import type { ApiStatus, RuntimeConfig } from "./api";

export type StatusState =
  | { kind: "loading" }
  | { kind: "ready"; status: ApiStatus }
  | { kind: "error"; message: string };

export function DashboardView({
  status,
  runtime,
  onRetry,
  developerMode,
  onDeveloperModeChange,
}: {
  status: StatusState;
  runtime?: RuntimeConfig | null;
  onRetry: () => void;
  developerMode: boolean;
  onDeveloperModeChange: (enabled: boolean) => void;
}) {
  return (
    <main className="main">
      {status.kind === "loading" && <p className="muted">正在連線至本機 Sidecar…</p>}
      {status.kind === "error" && (
        <div className="errorbox">
          <p>無法連線至本機 Sidecar</p>
          {developerMode ? <p className="muted">{status.message}</p> : null}
          <button onClick={onRetry}>重試</button>
        </div>
      )}
      {status.kind === "ready" && !developerMode ? <p>本機 Sidecar 已連線。</p> : null}

      <section aria-labelledby="developer-mode-heading">
        <h2 id="developer-mode-heading" className="section">Developer Mode</h2>
        <label>
          <input
            type="checkbox"
            checked={developerMode}
            onChange={(event) => onDeveloperModeChange(event.target.checked)}
          />{" "}
          顯示本機診斷資訊
        </label>
      </section>

      {developerMode && runtime ? <RuntimePanel rt={runtime} /> : null}
      {developerMode && status.kind === "ready" ? <StatusTiles status={status.status} /> : null}
    </main>
  );
}

function RuntimePanel({ rt }: { rt: RuntimeConfig }) {
  const keyRow = (label: string, set: boolean) => (
    <div className="rt-row" key={label}>
      <span>{label}</span>
      <span className={set ? "up" : "down"}>{set ? "✓ set" : "✗ missing"}</span>
    </div>
  );
  return (
    <>
      <h2 className="section">Models in use</h2>
      <div className="rt-list">
        <div className="rt-row">
          <span>card synthesis</span>
          <span className="mono">{rt.card_synthesis.provider} · {rt.card_synthesis.model}</span>
        </div>
        <div className="rt-row">
          <span>card translation</span>
          <span className="mono">{rt.card_translation.provider} · {rt.card_translation.model}</span>
        </div>
        <div className="rt-row">
          <span>anthropic (default / advanced)</span>
          <span className="mono">{rt.anthropic.model} / {rt.anthropic.model_advanced}</span>
        </div>
        <div className="rt-row">
          <span>openai (default / advanced)</span>
          <span className="mono">{rt.openai.model} / {rt.openai.model_advanced}</span>
        </div>
      </div>
      <h2 className="section">API keys present</h2>
      <div className="rt-list">
        {keyRow("anthropic", rt.anthropic.key_set)}
        {keyRow("openai", rt.openai.key_set)}
        {Object.entries(rt.data_keys).map(([k, v]) => keyRow(k, v))}
      </div>
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
