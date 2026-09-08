import React from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { initializeI18n } from "@app/i18n";
import { withTestUiLocale } from "@app/test/testUiLocale";
import { installUiTokens } from "@app/ui/tokens";
import { DataStorageSection } from "@app/settings/DataStorageSection";
import { createSettingsReadCache } from "@app/settings/settingsReadCache";
import "@app/styles.css";
import "@app/shell/shell.css";
import "@app/ui/primitives.css";
import "@app/settings/settings.css";

const locale = new URLSearchParams(location.search).get("locale") === "en" ? "en" : "zh-Hant";
initializeI18n(i18n, locale);
document.documentElement.lang = locale;
installUiTokens(document.documentElement);
createRoot(document.getElementById("root")!).render(withTestUiLocale(
  <main style={{ maxWidth: 1100, marginInline: "auto", padding: 16, minWidth: 0 }}>
    <DataStorageSection settingsReadCache={createSettingsReadCache()} onNavigateTarget={() => {}} />
  </main>,
));
