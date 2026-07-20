import { Search } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "../ui";
import { settingsGroupLabel, settingsSectionCopy } from "./settingsCopy";
import {
  SETTINGS_GROUPS,
  searchSettings,
  settingsGroup,
  type SettingsAnchorId,
  type SettingsGroupId,
} from "./settingsRegistry";

export function SettingsDirectory({
  query,
  currentTarget,
  activeGroup,
  onQueryChange,
  onSelect,
}: {
  query: string;
  currentTarget: SettingsAnchorId;
  activeGroup: SettingsGroupId;
  onQueryChange: (query: string) => void;
  onSelect: (id: SettingsAnchorId) => void;
}) {
  const { t } = useTranslation("settings");
  const normalizedQuery = query.normalize("NFKC").trim();
  const matches = normalizedQuery ? searchSettings(query) : settingsGroup(activeGroup).sections;
  const matchIds = new Set(matches.map((section) => section.id));

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
          {SETTINGS_GROUPS.map((group) => {
            const sections = group.sections.filter((section) => matchIds.has(section.id));
            if (sections.length === 0) return null;
            return (
              <div className="settings-directory-group" key={group.id}>
                <p>{settingsGroupLabel(group.id, t)}</p>
                <div className="settings-directory-links">
                  {sections.map((section) => {
                    const copy = settingsSectionCopy(section.id, t);
                    return (
                      <Button
                        key={section.id}
                        tone="ghost"
                        size="compact"
                        aria-current={currentTarget === section.id ? "location" : undefined}
                        onClick={() => onSelect(section.id)}
                      >
                        {copy.title}
                      </Button>
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
