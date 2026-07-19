import { Search } from "lucide-react";

import { Button } from "../ui";
import {
  SETTINGS_GROUPS,
  searchSettings,
  type SettingsAnchorId,
} from "./settingsRegistry";

export function SettingsDirectory({
  query,
  currentTarget,
  onQueryChange,
  onSelect,
}: {
  query: string;
  currentTarget: SettingsAnchorId;
  onQueryChange: (query: string) => void;
  onSelect: (id: SettingsAnchorId) => void;
}) {
  const matches = searchSettings(query);
  const matchIds = new Set(matches.map((section) => section.id));

  return (
    <nav className="settings-directory" aria-label="設定目錄">
      <label className="settings-directory-search">
        <span className="ui-visually-hidden">搜尋設定</span>
        <Search size={15} aria-hidden="true" />
        <input
          type="search"
          value={query}
          aria-label="搜尋設定"
          placeholder="搜尋設定"
          onChange={(event) => onQueryChange(event.currentTarget.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter" || matches.length === 0) return;
            event.preventDefault();
            onSelect(matches[0].id);
          }}
        />
      </label>

      {matches.length === 0 ? (
        <p className="settings-directory-empty">找不到符合的設定</p>
      ) : (
        <div className="settings-directory-groups">
          {SETTINGS_GROUPS.map((group) => {
            const sections = group.sections.filter((section) => matchIds.has(section.id));
            if (sections.length === 0) return null;
            return (
              <div className="settings-directory-group" key={group.id}>
                <p>{group.title}</p>
                <div className="settings-directory-links">
                  {sections.map((section) => (
                    <Button
                      key={section.id}
                      tone="ghost"
                      size="compact"
                      aria-current={currentTarget === section.id ? "location" : undefined}
                      onClick={() => onSelect(section.id)}
                    >
                      {section.title}
                    </Button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </nav>
  );
}
