import { Database } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { ApiStatus, RuntimeConfig } from "./api";
import {
  presentSystemStatus,
  type SystemStatusState,
} from "./i18n/systemPresentation";
import type { NavigationTarget } from "./shell/navigation";
import { Button } from "./ui";

export type StatusState = SystemStatusState;

export function DashboardView({
  status,
  runtime,
  onRetry,
  developerMode,
  onDeveloperModeChange,
  onNavigate,
}: {
  status: StatusState;
  runtime?: RuntimeConfig | null;
  onRetry: () => void;
  developerMode: boolean;
  onDeveloperModeChange: (enabled: boolean) => void;
  onNavigate: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("system");
  const statusPresentation = presentSystemStatus(status, developerMode, t);
  return (
    <main className="main">
      {statusPresentation.kind === "loading" && (
        <p className="muted">{statusPresentation.message}</p>
      )}
      {statusPresentation.kind === "error" && (
        <div className="errorbox">
          <p>{statusPresentation.title}</p>
          {statusPresentation.diagnostics.length > 0 ? (
            <p className="muted" data-system-diagnostic>
              {statusPresentation.diagnostics.join(" · ")}
            </p>
          ) : null}
          <button onClick={onRetry}>{statusPresentation.retryLabel}</button>
        </div>
      )}
      {statusPresentation.kind === "ready" && !developerMode ? (
        <p>{statusPresentation.message}</p>
      ) : null}
      <Button
        size="compact"
        icon={<Database size={14} />}
        onClick={() => onNavigate({ kind: "settings_section", section: "data_sources" })}
      >
        {t(($) => $.dataSourceSettings)}
      </Button>

      <section aria-labelledby="developer-mode-heading">
        <h2 id="developer-mode-heading" className="section">
          {t(($) => $.developer.heading)}
        </h2>
        <label>
          <input
            type="checkbox"
            checked={developerMode}
            onChange={(event) => onDeveloperModeChange(event.target.checked)}
          />{" "}
          {t(($) => $.developer.showDiagnostics)}
        </label>
      </section>

      {developerMode && runtime ? <RuntimePanel rt={runtime} /> : null}
      {developerMode && status.kind === "ready" ? <StatusTiles status={status.status} /> : null}
    </main>
  );
}

function RuntimePanel({ rt }: { rt: RuntimeConfig }) {
  const { t } = useTranslation("system");
  const keyRow = (label: string, set: boolean) => (
    <div className="rt-row" key={label}>
      <span>{label}</span>
      <span className={set ? "up" : "down"}>
        {set ? t(($) => $.runtime.keySet) : t(($) => $.runtime.keyMissing)}
      </span>
    </div>
  );
  return (
    <>
      <h2 className="section">{t(($) => $.runtime.modelsInUse)}</h2>
      <div className="rt-list">
        <div className="rt-row">
          <span>{t(($) => $.runtime.cardSynthesis)}</span>
          <span className="mono">{rt.card_synthesis.provider} · {rt.card_synthesis.model}</span>
        </div>
        <div className="rt-row">
          <span>{t(($) => $.runtime.cardTranslation)}</span>
          <span className="mono">{rt.card_translation.provider} · {rt.card_translation.model}</span>
        </div>
        <div className="rt-row">
          <span>{t(($) => $.runtime.anthropicDefaultAdvanced)}</span>
          <span className="mono">{rt.anthropic.model} / {rt.anthropic.model_advanced}</span>
        </div>
        <div className="rt-row">
          <span>{t(($) => $.runtime.openAIDefaultAdvanced)}</span>
          <span className="mono">{rt.openai.model} / {rt.openai.model_advanced}</span>
        </div>
      </div>
      <h2 className="section">{t(($) => $.runtime.apiKeysPresent)}</h2>
      <div className="rt-list">
        {keyRow("anthropic", rt.anthropic.key_set)}
        {keyRow("openai", rt.openai.key_set)}
        {Object.entries(rt.data_keys).map(([k, v]) => keyRow(k, v))}
      </div>
    </>
  );
}

function StatusTiles({ status }: { status: ApiStatus }) {
  const { t } = useTranslation("system");
  const knownDataSourceLabels = {
    news_tickers: t(($) => $.status.dataSourceLabels.newsTickers),
    price_tickers: t(($) => $.status.dataSourceLabels.priceTickers),
    fundamentals_tickers: t(($) => $.status.dataSourceLabels.storedSecFundamentals),
  } satisfies Record<"news_tickers" | "price_tickers" | "fundamentals_tickers", string>;

  const dataSourceLabel = (key: string): string => {
    if (Object.prototype.hasOwnProperty.call(knownDataSourceLabels, key)) {
      return knownDataSourceLabels[key as keyof typeof knownDataSourceLabels];
    }
    return t(($) => $.status.dataSourceLabels.unknown, { value: key });
  };

  return (
    <div className="dashboard">
      <section className="tilerow">
        <Tile label={t(($) => $.status.registryTools)} value={status.tools_registered} />
        <Tile label={t(($) => $.status.serverTime)} value={new Date(status.timestamp).toLocaleTimeString()} />
        <Tile label={t(($) => $.status.status)} value={status.status} />
      </section>

      <h2 className="section">{t(($) => $.status.toolCategories)}</h2>
      <div className="grid">
        {Object.entries(status.tool_categories).map(([k, v]) => (
          <Tile key={k} label={k} value={v} />
        ))}
      </div>

      <h2 className="section">{t(($) => $.status.dataSourcesTickers)}</h2>
      <div className="grid">
        {Object.entries(status.data_sources).map(([k, v]) => (
          <Tile key={k} label={dataSourceLabel(k)} value={v} />
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
