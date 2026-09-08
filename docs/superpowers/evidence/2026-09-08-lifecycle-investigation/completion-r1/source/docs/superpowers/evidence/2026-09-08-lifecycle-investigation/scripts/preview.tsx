import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { initializeI18n } from "@app/i18n";
import { withTestUiLocale } from "@app/test/testUiLocale";
import { installUiTokens } from "@app/ui/tokens";
import { LifecycleView } from "@app/lifecycle/LifecycleView";
import { InvestigationRuntimeSection } from "@app/settings/InvestigationRuntimeSection";
import { Button } from "@app/ui/Button";
import { ArrowLeft } from "lucide-react";
import "@app/styles.css";
import "@app/ui/primitives.css";

const locale = new URLSearchParams(location.search).get("locale") === "en" ? "en" : "zh-Hant";
initializeI18n(i18n, locale);
document.documentElement.lang = locale;
installUiTokens(document.documentElement);
function Preview() {
  const [settings, setSettings] = useState(false);
  return <main style={{ maxWidth: 1240, margin: "0 auto", padding: 16, minWidth: 0 }}>
    <header style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap", borderBottom: "1px solid var(--border)", paddingBottom: 12, marginBottom: 20 }}>
      <strong>ArkScope</strong><span>{locale === "en" ? "Isolated synthetic data" : "隔離合成資料"}</span>
      <nav><a href="?locale=zh-Hant">繁中</a> / <a href="?locale=en">EN</a></nav>
    </header>
    {settings ? <><Button icon={<ArrowLeft size={16} />} onClick={() => setSettings(false)}>{locale === "en" ? "Investigation" : "標的事件調查"}</Button>
      <InvestigationRuntimeSection authMode="claude_code_oauth" /></>
      : <LifecycleView initialTicker={new URLSearchParams(location.search).get("ticker") ?? "OLD"} onNavigate={() => setSettings(true)} />}
  </main>;
}
createRoot(document.getElementById("root")!).render(withTestUiLocale(<Preview />));
