import { useTranslation } from "react-i18next";

import type { PersonalizationTrace } from "./api";
import { assistantStanceEffect } from "./settings/investor/investorProfileDisplay";

export function ResearchPersonalizationContext({
  trace,
}: {
  trace: PersonalizationTrace | null;
}) {
  const { t: researchT } = useTranslation("research");
  const { t: settingsT } = useTranslation("settings");
  const snapshot = trace?.context_snapshot ?? null;

  return (
    <section className="research-personalization-context">
      <details>
        <summary>{researchT(($) => $.personalization.title)}</summary>
        <p className="muted tiny">
          {researchT(($) => $.personalization.runNotice)}
        </p>
        {snapshot === null ? (
          <p>{researchT(($) => $.personalization.unavailable)}</p>
        ) : snapshot === "" ? (
          <p>{researchT(($) => $.personalization.disabled)}</p>
        ) : (
          <>
            <p>{researchT(($) => $.personalization.active)}</p>
            <p
              className="muted"
              data-testid="research-personalization-stance-effect"
            >
              {assistantStanceEffect(trace!.assistant_stance, settingsT)}
            </p>
            <pre className="research-personalization-context-source">{snapshot}</pre>
          </>
        )}
      </details>
    </section>
  );
}
