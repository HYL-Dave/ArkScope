import { useEffect, useState } from "react";
import { Settings } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getSAAcquisitionStatus, type SAAcquisitionStatus } from "../api";
import { Button } from "../ui/Button";
import { InlineAlert } from "../ui/Status";
import type { NavigationTarget } from "./navigation";

export function SAAcquisitionNotice({ onNavigate }: { onNavigate: (target: NavigationTarget) => void }) {
  const { t } = useTranslation("shell");
  const [status, setStatus] = useState<SAAcquisitionStatus | null>(null);
  useEffect(() => {
    let mounted = true, pending = false;
    const read = async () => {
      if (pending || document.visibilityState === "hidden") return;
      pending = true;
      try {
        const result = await getSAAcquisitionStatus();
        if (mounted) setStatus(result);
      } catch {
        if (mounted) setStatus({ status: "error" });
      } finally { pending = false; }
    };
    void read();
    const timer = window.setInterval(() => void read(), 60_000);
    window.addEventListener("focus", read);
    document.addEventListener("visibilitychange", read);
    return () => {
      mounted = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", read);
      document.removeEventListener("visibilitychange", read);
    };
  }, []);
  if (!status) return null;
  const capabilities = Object.keys(status.capability_pauses ?? {});
  const reason = status.paused_reason;
  if (status.status === "ok" && !reason && !status.rate_limited && !capabilities.length) return null;
  const capabilityText = capabilities.map(capability => {
    switch (capability) {
      case "financials": return t(($) => $.saAcquisition.financials);
      case "alpha_picks": return t(($) => $.saAcquisition.alphaPicks);
      case "news": return t(($) => $.saAcquisition.news);
      default: return t(($) => $.saAcquisition.otherContent);
    }
  }).join(", ");
  const description = status.status === "error" ? t(($) => $.saAcquisition.unavailable)
    : reason === "login_required" ? t(($) => $.saAcquisition.login)
    : reason === "human_verification_required" ? t(($) => $.saAcquisition.verification)
    : status.rate_limited ? t(($) => $.saAcquisition.cooldown)
    : capabilities.length ? t(($) => $.saAcquisition.access, { capabilities: capabilityText })
    : t(($) => $.saAcquisition.paused);
  return (
    <div className="sa-acquisition-notice">
      <InlineAlert state="blocked" title={t(($) => $.saAcquisition.title)} action={
        <Button size="compact" icon={<Settings size={14} />} onClick={() => onNavigate({ kind: "settings_section", section: "data_sources" })}>
          {t(($) => $.saAcquisition.openSettings)}
        </Button>
      }>{description}</InlineAlert>
    </div>
  );
}
