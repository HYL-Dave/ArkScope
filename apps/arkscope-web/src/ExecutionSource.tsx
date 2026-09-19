import { useTranslation } from "react-i18next";
import type { ExecutionReceipt } from "./api";
import { modelAuthModeLabel } from "./modelRoutingUx";

export function ExecutionSource({ source, receipt }: {
  source: "original" | "previous" | "next";
  receipt?: ExecutionReceipt | null;
}) {
  const { t } = useTranslation("common");
  const unknown = t(($) => $.executionSource.unknown);
  const labels = {
    original: t(($) => $.executionSource.original),
    previous: t(($) => $.executionSource.previous),
    next: t(($) => $.executionSource.next),
  };
  return <p className="execution-source muted tiny" data-execution-source={source}>
    <span>{labels[source]}: </span>
    <span>{receipt?.provider ?? unknown}{" \u00b7 "}{receipt?.model ?? unknown}</span>
    {" \u00b7 "}<span>{t(($) => $.executionSource.effort)}: {receipt?.effort ?? unknown}</span>
    {" \u00b7 "}<span>{t(($) => $.executionSource.auth)}: {receipt?.auth_mode ? modelAuthModeLabel(receipt.auth_mode, t) : unknown}</span>
  </p>;
}
