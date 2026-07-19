/// <reference types="node" />

import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { SETTINGS_ANCHOR_IDS } from "./settings/settingsRegistry";

const here = fileURLToPath(new URL(".", import.meta.url));
const settingsPath = resolve(here, "./Settings.tsx");
const settingsRoot = resolve(here, "./settings");
const stylesCss = readFileSync(resolve(here, "./styles.css"), "utf8");
const primitivesCss = readFileSync(resolve(here, "./ui/primitives.css"), "utf8");
const settingsCss = readFileSync(resolve(settingsRoot, "./settings.css"), "utf8");
const allCss = [stylesCss, primitivesCss, settingsCss].join("\n");

function sourceFiles(root: string): string[] {
  if (!existsSync(root)) return [];
  return readdirSync(root, { withFileTypes: true })
    .sort((left, right) => left.name.localeCompare(right.name))
    .flatMap((entry) => {
      const path = resolve(root, entry.name);
      if (entry.isDirectory()) return sourceFiles(path);
      return entry.isFile() && entry.name.endsWith(".tsx") ? [path] : [];
    });
}

const settingsSourcePaths = [settingsPath, ...sourceFiles(settingsRoot)];
const settingsSources = settingsSourcePaths.map((path) => readFileSync(path, "utf8")).join("\n");

function literalClasses(source: string): string[] {
  return Array.from(source.matchAll(/className="([^"]+)"/g))
    .flatMap((match) => match[1].split(/\s+/))
    .filter(Boolean);
}

function hasSelector(name: string): boolean {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`\\.${escaped}(?=[\\s.{:#,>+~\\[])`).test(allCss);
}

function ruleBody(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return settingsCss.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
}

describe("Settings workspace CSS contract", () => {
  it("uses_data_driven_shell_overlay_without_numeric_breakpoint_literals", () => {
    expect(settingsSources).toContain("useShellOverlay");
    expect(settingsSources).toContain("data-settings-overlay");
    expect(settingsCss).toContain('[data-settings-overlay="true"]');
    expect(settingsCss).not.toMatch(/@media\s*\(/);
    expect(`${settingsSources}\n${settingsCss}`).not.toMatch(/\b(?:959|960|961)(?:px)?\b/);
    expect(ruleBody(".settings-directory-links .ui-button")).toMatch(/white-space:\s*normal/);
    expect(ruleBody(".settings-directory-links .ui-button")).toMatch(/overflow-wrap:\s*anywhere/);
    expect(ruleBody(".settings-workspace-groups")).toMatch(/min-width:\s*0/);
    expect(ruleBody(".settings-workspace-group")).not.toMatch(/background|border-radius/);
    expect(ruleBody(".settings-workspace .settings-grid")).toMatch(/repeat\(auto-fit/);
    expect(ruleBody(".settings-workspace .provider-grid")).toMatch(/repeat\(auto-fit/);
    expect(ruleBody(".settings-workspace .credential-actions")).toMatch(/repeat\(auto-fit/);
    expect(ruleBody(".settings-workspace .runtime-limit-grid")).toMatch(/repeat\(auto-fit/);
  });

  it("defines_every_literal_class_in_extracted_settings_modules", () => {
    const classes = [...new Set(settingsSourcePaths.flatMap((path) =>
      literalClasses(readFileSync(path, "utf8"))))];
    expect(classes.filter((name) => !hasSelector(name)).sort()).toEqual([]);
  });

  it("removes_legacy_directory_runtime_band_and_confirm_owners", () => {
    for (const selector of ["settings-nav-card", "settings-section-button", "settings-band"]) {
      expect(settingsSources).not.toContain(selector);
      expect(allCss.includes(`.${selector}`)).toBe(false);
    }
    expect(settingsSources).not.toContain("window.confirm");
    expect(SETTINGS_ANCHOR_IDS).not.toContain("app_records");
    expect(SETTINGS_ANCHOR_IDS).not.toContain("permissions");
  });
});
