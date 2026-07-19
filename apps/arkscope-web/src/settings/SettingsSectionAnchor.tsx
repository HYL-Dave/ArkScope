import type { ReactNode } from "react";

import { settingsAnchorDomId, type SettingsAnchorId } from "./settingsRegistry";

export function SettingsSectionAnchor({
  id,
  children,
}: {
  id: SettingsAnchorId;
  children: ReactNode;
}) {
  return (
    <section
      id={settingsAnchorDomId(id)}
      className="settings-section-anchor"
      data-settings-anchor={id}
      tabIndex={-1}
    >
      {children}
    </section>
  );
}
