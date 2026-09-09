import React from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { AICardTab } from "../../../../apps/arkscope-web/src/AICard";
import { initializeI18n } from "../../../../apps/arkscope-web/src/i18n/resources";
import { installUiTokens } from "../../../../apps/arkscope-web/src/ui/tokens";
import { withTestUiLocale } from "../../../../apps/arkscope-web/src/test/testUiLocale";
import "../../../../apps/arkscope-web/src/styles.css";
import "../../../../apps/arkscope-web/src/ui/primitives.css";

const params = new URL(location.href).searchParams;
const locale = params.get("locale") === "en" ? "en" : "zh-Hant";
await initializeI18n(i18n, locale);
document.documentElement.lang = locale;
installUiTokens(document.documentElement);
createRoot(document.getElementById("root")!).render(withTestUiLocale(
  <main className="main" style={{ maxWidth: 1120, margin: "16px auto", padding: "0 16px" }}>
    <h2>AMD</h2>
    <AICardTab ticker="AMD" developerMode={params.get("diagnostics") === "1"}
      onNavigateTarget={target => { document.body.dataset.navigation = JSON.stringify(target); }} />
  </main>,
));
