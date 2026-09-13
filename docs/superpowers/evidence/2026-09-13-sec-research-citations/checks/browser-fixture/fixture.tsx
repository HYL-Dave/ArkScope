import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { I18nextProvider } from "react-i18next";
import { FileSearch, RefreshCw } from "lucide-react";
import { ResearchEvidenceDrawer } from "@product/ResearchEvidenceDrawer";
import type { Message } from "@product/researchReducer";
import { bootstrapUiLocale } from "@product/i18n";
import { Button, PageHeader } from "@product/ui";
import { installUiTokens } from "@product/ui/tokens";
import "@product/styles.css";
import "@product/shell/shell.css";
import "@product/ui/primitives.css";

const locale = new URLSearchParams(location.search).get("locale") === "zh-Hant" ? "zh-Hant" : "en";
installUiTokens(document.documentElement);
bootstrapUiLocale({ instance: i18n, cache: { read: () => locale, write: () => {} }, root: document.documentElement });

function Fixture() {
  const [message, setMessage] = useState<Message | null>(null);
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [loads, setLoads] = useState(0);
  const opener = useRef<HTMLButtonElement>(null);
  async function reload() {
    const response = await fetch("/fixture/message");
    if (!response.ok) throw new Error("fixture message unavailable");
    setMessage(await response.json());
    setLoads((value) => value + 1);
  }
  useEffect(() => { void reload(); }, []);
  return (
    <main className="main" data-fixture-load={loads}>
      <PageHeader title="SEC research" actions={<Button icon={<RefreshCw size={16} />} onClick={() => void reload()}>Reload saved turn</Button>} />
      <p>{message?.content}</p>
      <Button ref={opener} icon={<FileSearch size={16} />} disabled={!message} onClick={() => setOpen(true)}>Open evidence</Button>
      <ResearchEvidenceDrawer open={open} pinned={pinned} onClose={() => setOpen(false)}
        onPinnedChange={setPinned} returnFocusRef={opener} message={message}
        activeTrace={[]} activeRun={null} developerMode={false} />
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<I18nextProvider i18n={i18n}><Fixture /></I18nextProvider>);
