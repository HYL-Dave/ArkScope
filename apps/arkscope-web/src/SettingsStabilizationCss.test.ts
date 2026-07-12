/// <reference types="node" />
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));
const css = readFileSync(resolve(here, "./styles.css"), "utf8");

function rule(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
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

  it("lets_designated_detail_cells_wrap_without_shrinking_type", () => {
    expect(rule(".settings-wrap-text")).toMatch(/white-space:\s*normal/);
    expect(rule(".settings-wrap-text")).toMatch(/overflow-wrap:\s*anywhere/);
    expect(rule(".settings-wrap-text")).not.toMatch(/font-size:/);
  });
});
