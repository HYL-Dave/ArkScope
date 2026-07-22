/// <reference types="node" />

import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));
const primitiveCss = readFileSync(resolve(here, "./primitives.css"), "utf8");
const settingsCss = readFileSync(resolve(here, "../settings/settings.css"), "utf8");
const css = [readFileSync(resolve(here, "../styles.css"), "utf8"), primitiveCss, settingsCss].join("\n");

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
  readFileSync(resolve(here, "../Settings.tsx"), "utf8"),
  ...tsxSources(resolve(here, "../settings")),
].join("\n");
const investorSources = tsxSources(resolve(here, "../settings/investor")).join("\n");

function literalClasses(source: string): string[] {
  return Array.from(source.matchAll(/className="([^"]+)"/g))
    .flatMap((match) => match[1].split(/\s+/))
    .filter(Boolean);
}

function hasSelector(name: string): boolean {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`\\.${escaped}(?=[\\s.{:#,>+~\\[])`).test(css);
}

describe("migrated component class coverage", () => {
  it.each([
    ["Holdings", resolve(here, "../Holdings.tsx")],
    ["InvestorProfilePanel", resolve(here, "../InvestorProfilePanel.tsx")],
  ])("defines every literal class used by %s", (name, path) => {
    const source = [
      readFileSync(path, "utf8"),
      name === "Holdings"
        ? settingsSources
        : name === "InvestorProfilePanel" ? investorSources : "",
    ].join("\n");
    const classes = [...new Set(literalClasses(source))];
    const missing = classes.filter((name) => !hasSelector(name)).sort();
    expect(missing).toEqual([]);
  });

  it("keeps investor proposal guardrails wrap-capable on narrow screens", () => {
    const rule = primitiveCss.match(/\.ip-guardrail\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(rule).toMatch(/flex-wrap:\s*wrap|display:\s*grid/);
  });
});
