/// <reference types="node" />

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));
const primitiveCss = readFileSync(resolve(here, "./primitives.css"), "utf8");
const css = [readFileSync(resolve(here, "../styles.css"), "utf8"), primitiveCss].join("\n");

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
  ])("defines every literal class used by %s", (_name, path) => {
    const classes = [...new Set(literalClasses(readFileSync(path, "utf8")))];
    const missing = classes.filter((name) => !hasSelector(name));
    expect(missing).toEqual([]);
  });

  it("keeps investor proposal guardrails wrap-capable on narrow screens", () => {
    const rule = primitiveCss.match(/\.ip-guardrail\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(rule).toMatch(/flex-wrap:\s*wrap|display:\s*grid/);
  });
});
