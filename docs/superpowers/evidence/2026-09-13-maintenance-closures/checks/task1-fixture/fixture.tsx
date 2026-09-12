import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { Download, RefreshCw } from "lucide-react";
import { Button } from "@product/ui/Button";
import { PageHeader } from "@product/ui/PageHeader";
import { installUiTokens } from "@product/ui/tokens";
import "@product/styles.css";
import "@product/shell/shell.css";
import "@product/ui/primitives.css";
import "@product/settings/settings.css";

installUiTokens(document.documentElement);
const settings = new URLSearchParams(location.search).get("surface") === "settings";

function Fixture() {
  const [refreshed, setRefreshed] = useState(false);
  const header = (
    <PageHeader
      eyebrow={settings ? undefined : "Portfolio"}
      title={settings ? "Settings" : "Holdings and account activity"}
      context={settings ? undefined : <span>9 positions across two accounts. Updated just now.</span>}
      actions={
        <>
          <Button icon={<RefreshCw size={16} />} onClick={() => setRefreshed(true)}>Refresh</Button>
          <Button icon={<Download size={16} />} disabled>Export activity</Button>
        </>
      }
    />
  );
  return (
    <main className={settings ? "main settings-workspace" : "main"}>
      {settings ? <div className="settings-page-lede">{header}</div> : header}
      <div className="detailpage-head">
        <button type="button" className="btn-ghost">Back</button>
        <span className="mono strong detailpage-ticker">DEMO</span>
        <span className="muted">Ticker detail</span>
      </div>
      <p role="status">{refreshed ? "Refreshed" : "Ready"}</p>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<Fixture />);
