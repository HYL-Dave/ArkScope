import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { AICardTab, CardModal } from "../../../../apps/arkscope-web/src/AICard";
import { App } from "../../../../apps/arkscope-web/src/App";
import { ResearchView } from "../../../../apps/arkscope-web/src/Research";
import { SettingsView } from "../../../../apps/arkscope-web/src/Settings";
import { LifecycleView } from "../../../../apps/arkscope-web/src/lifecycle/InvestigationView";
import { createSettingsReadCache } from "../../../../apps/arkscope-web/src/settings/settingsReadCache";
import { initializeI18n } from "../../../../apps/arkscope-web/src/i18n/resources";
import { installUiTokens } from "../../../../apps/arkscope-web/src/ui/tokens";
import { withTestUiLocale } from "../../../../apps/arkscope-web/src/test/testUiLocale";
import "../../../../apps/arkscope-web/src/styles.css";
import "../../../../apps/arkscope-web/src/shell/shell.css";
import "../../../../apps/arkscope-web/src/ui/primitives.css";
import "../../../../apps/arkscope-web/src/settings/settings.css";

const params = new URL(location.href).searchParams;
const locale = params.get("locale") === "en" ? "en" : "zh-Hant";
await initializeI18n(i18n, locale);
document.documentElement.lang = locale;
installUiTokens(document.documentElement);
const cache = createSettingsReadCache();

function Preview() {
  const [view, setView] = useState(params.get("view") ?? "cards");
  const [modal, setModal] = useState(false);
  const navigate = () => setView("settings");
  if (view === "shell") return <App />;
  return <div style={{ maxWidth: 1120, margin: "16px auto", padding: "0 16px" }}>
    <nav aria-label="Fixture views" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
      {["cards", "research", "settings", "lifecycle"].map(name => <button key={name} onClick={() => setView(name)}>{name}</button>)}
    </nav>
    {view === "cards" && <>
      <main className="main">
        <button onClick={() => setModal(true)}>Saved card</button>
        <AICardTab ticker="AAPL" developerMode={false} onNavigateTarget={navigate} />
      </main>
      {modal && <CardModal runId={1} onClose={() => setModal(false)} developerMode={false} onNavigateTarget={navigate} />}
    </>}
    {view === "research" && <ResearchView onOpenTicker={() => {}} developerMode={false} onNavigate={navigate} />}
    {view === "settings" && <SettingsView runtime={null} developerMode={false} onRuntimeChanged={async () => {}}
      settingsReadCache={cache} navigationRequest={{ sequence: 1, target: { kind: "settings_section", section: "models" } }} />}
    {view === "lifecycle" && <LifecycleView initialTicker="TA" onNavigate={navigate} />}
  </div>;
}

createRoot(document.getElementById("root")!).render(withTestUiLocale(<Preview />));
