/// <reference types="node" />
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));
const css = readFileSync(resolve(here, "./styles.css"), "utf8");

function tsxSources(root: string): string[] {
  if (!existsSync(root)) return [];
  return readdirSync(root, { withFileTypes: true })
    .sort((left, right) => left.name.localeCompare(right.name))
    .flatMap((entry) => {
      const path = resolve(root, entry.name);
      if (entry.isDirectory()) return tsxSources(path);
      return entry.isFile() && entry.name.endsWith(".tsx")
        ? [readFileSync(path, "utf8")]
        : [];
    });
}

const settingsSources = [
  readFileSync(resolve(here, "./Settings.tsx"), "utf8"),
  ...tsxSources(resolve(here, "./settings")),
];

function rule(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
}

function sourceSection(start: string, end: string): string {
  const source = settingsSources.find((candidate) => candidate.includes(start)) ?? "";
  const from = source.indexOf(start);
  const to = source.indexOf(end, from + start.length);
  expect(from).toBeGreaterThanOrEqual(0);
  return source.slice(from, to > from ? to : undefined);
}

describe("Settings stabilization CSS contracts", () => {
  it("gives_wide_settings_tables_one_horizontal_scroll_owner_and_reviewed_min_widths", () => {
    expect(rule(".settings-table-scroll")).toMatch(/overflow-x:\s*auto/);
    for (const selector of [
      ".settings-provider-health-table",
      ".settings-sa-health-table",
      ".settings-fred-table",
      ".settings-provider-config-table",
      ".settings-schedule-table",
    ]) {
      expect(rule(selector)).toMatch(/min-width:\s*\d+px/);
      expect(rule(selector)).not.toMatch(/font-size:/);
    }
  });

  it("keeps_detail_cells_wrap_capable_and_normal_sections_free_of_migration_copy", () => {
    expect(rule(".settings-wrap-text")).toMatch(/white-space:\s*normal/);
    expect(rule(".settings-wrap-text")).toMatch(/overflow-wrap:\s*anywhere/);
    expect(rule(".settings-wrap-text")).not.toMatch(/font-size:/);

    const normalSections = [
      sourceSection("function DataStorageSection()", "function NewsStorageSection()"),
      sourceSection("function NewsStorageSection()", "function TradingDayCoveragePanel()"),
      sourceSection("function MacroStorageSection()", "function FragmentKV("),
      sourceSection("function DataSourcesSection({", "export function ModelRoutingSection("),
    ].join("\n");
    expect(normalSections).not.toMatch(
      /PostgreSQL|PG exit|PG mirror|PG fallback|PG 同步|PG 鏡像|SQLite|local authority|local-primary|local-only|本地市場資料庫|本地市場庫|本地路由|本地新聞庫|本地總經庫|本地快照|本地 SA|存本地|market_data\.db|macro_calendar\.db|direct-local|legacy local|legacy config|strict DB-first/,
    );
    expect(normalSections).toContain("config/.env");
  });
});
