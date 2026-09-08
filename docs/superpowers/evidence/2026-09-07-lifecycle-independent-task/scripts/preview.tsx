import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { initializeI18n } from "@app/i18n";
import { withTestUiLocale } from "@app/test/testUiLocale";
import { installUiTokens } from "@app/ui/tokens";
import { SettingsView } from "@app/Settings";
import { getRuntimeConfig, type RuntimeConfig } from "@app/api";
import "@app/styles.css";
import "@app/shell/shell.css";
import "@app/ui/primitives.css";

const locale = new URLSearchParams(location.search).get("locale") === "en" ? "en" : "zh-Hant";
initializeI18n(i18n, locale);
document.documentElement.lang = locale;
installUiTokens(document.documentElement);

function Preview({ initial }: { initial: RuntimeConfig }) {
  const [runtime, setRuntime] = useState(initial);
  return <SettingsView runtime={runtime} developerMode={false}
    navigationRequest={{ sequence: 1, target: { surface: "settings", section: "models" } }}
    onRuntimeChanged={async () => { setRuntime(await getRuntimeConfig()); }} />;
}

getRuntimeConfig().then((runtime) => {
  createRoot(document.getElementById("root")!).render(withTestUiLocale(
    <main style={{ maxWidth: 1200, marginInline: "auto", padding: 16, minWidth: 0 }}>
      <Preview initial={runtime} />
    </main>,
  ));
});
