import { Search } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "../ui";
import {
  settingsGroupLabel,
  settingsSectionCopy,
  type SettingsT,
} from "./settingsCopy";
import {
  SETTINGS_GROUPS,
  searchSettings,
  settingsGroup,
  settingsParentAnchor,
  settingsSubsectionsFor,
  type SettingsGroupId,
  type SettingsLocationId,
  type SettingsSubsectionId,
} from "./settingsRegistry";

function settingsSubsectionLabel(id: SettingsSubsectionId, t: SettingsT): string {
  switch (id) {
    case "provider_health":
      return t(($) => $.dataSources.providers.health.title);
    case "sa_extension_health":
      return t(($) => $.dataSources.extension.title);
    case "provider_connections":
      return t(($) => $.dataSources.providers.config.title);
    case "source_schedules":
      return t(($) => $.dataSources.schedule.title);
    case "trading_day_coverage":
      return t(($) => $.dataStorage.coverage.title);
  }
}

export function SettingsDirectory({
  query,
  activeGroup,
  currentTarget,
  onQueryChange,
  onSelect,
}: {
  query: string;
  activeGroup: SettingsGroupId;
  currentTarget: SettingsLocationId;
  onQueryChange: (query: string) => void;
  onSelect: (id: SettingsLocationId) => void;
}) {
  const { t } = useTranslation("settings");
  const normalizedQuery = query.normalize("NFKC").trim();
  const matches = normalizedQuery
    ? searchSettings(query)
    : settingsGroup(activeGroup).sections;
  const matchIds = new Set(matches.map((section) => section.id));
  const visibleGroups = normalizedQuery ? SETTINGS_GROUPS : [settingsGroup(activeGroup)];

  return (
    <nav
      className="settings-directory"
      aria-label={t(($) => $.workspace.directory.title)}
    >
      <label className="settings-directory-search">
        <span className="ui-visually-hidden">
          {t(($) => $.workspace.directory.searchLabel)}
        </span>
        <Search size={15} aria-hidden="true" />
        <input
          type="search"
          value={query}
          aria-label={t(($) => $.workspace.directory.searchLabel)}
          placeholder={t(($) => $.workspace.directory.searchPlaceholder)}
          onChange={(event) => onQueryChange(event.currentTarget.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter" || matches.length === 0) return;
            event.preventDefault();
            onSelect(matches[0].id);
          }}
        />
      </label>

      {matches.length === 0 ? (
        <p className="settings-directory-empty">
          {t(($) => $.workspace.directory.noMatch)}
        </p>
      ) : (
        <div className="settings-directory-groups">
          {visibleGroups.map((group) => {
            const sections = group.sections.filter((section) => matchIds.has(section.id));
            if (sections.length === 0) return null;
            return (
              <div className="settings-directory-group" key={group.id}>
                <p>{settingsGroupLabel(group.id, t)}</p>
                <div className="settings-directory-links">
                  {sections.map((section) => {
                    const copy = settingsSectionCopy(section.id, t);
                    const subsections = normalizedQuery ? [] : settingsSubsectionsFor(section.id);
                    const currentParent = settingsParentAnchor(currentTarget);
                    return (
                      <div className="settings-directory-section" key={section.id}>
                        <Button
                          tone="ghost"
                          size="compact"
                          aria-current={currentTarget === section.id ? "location" : undefined}
                          data-current-parent={
                            currentParent === section.id && currentTarget !== section.id
                              ? "true"
                              : undefined
                          }
                          onClick={() => onSelect(section.id)}
                        >
                          {copy.title}
                        </Button>
                        {subsections.length > 0 ? (
                          <div className="settings-directory-sublinks">
                            {subsections.map((subsection) => (
                              <Button
                                className="settings-directory-subsection"
                                key={subsection.id}
                                tone="ghost"
                                size="compact"
                                aria-current={
                                  currentTarget === subsection.id ? "location" : undefined
                                }
                                onClick={() => onSelect(subsection.id)}
                              >
                                {settingsSubsectionLabel(subsection.id, t)}
                              </Button>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </nav>
  );
}
