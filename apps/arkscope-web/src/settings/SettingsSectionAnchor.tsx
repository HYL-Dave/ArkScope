import type { ReactNode } from "react";

import {
  settingsAnchorDomId,
  settingsLocationDomId,
  type SettingsAnchorId,
  type SettingsSubsectionId,
} from "./settingsRegistry";

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
      data-settings-location={id}
      tabIndex={-1}
    >
      {children}
    </section>
  );
}

export function SettingsSubsectionAnchor({
  id,
  children,
}: {
  id: SettingsSubsectionId;
  children: ReactNode;
}) {
  return (
    <div
      id={settingsLocationDomId(id)}
      className="settings-subsection-anchor"
      data-settings-location={id}
      tabIndex={-1}
    >
      {children}
    </div>
  );
}
