/// <reference types="node" />

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();
const source = (path: string) => readFileSync(resolve(root, path), "utf8");
const shellCss = source("src/shell/shell.css");
const legacyCss = source("src/styles.css");
const primitiveCss = source("src/ui/primitives.css");
const mainSource = source("src/main.tsx");
const appSource = source("src/App.tsx");
const shellSources = [
  "src/shell/ShellNavigation.tsx",
  "src/shell/ShellTopBar.tsx",
  "src/shell/BackgroundWorkIndicator.tsx",
].map(source);
const allCss = [legacyCss, primitiveCss, shellCss].join("\n");

function literalClasses(value: string): string[] {
  return Array.from(value.matchAll(/className="([^"]+)"/g))
    .flatMap((match) => match[1].split(/\s+/))
    .filter(Boolean);
}

function hasSelector(name: string): boolean {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`\\.${escaped}(?=[\\s.{:#,>+~\\[])`).test(allCss);
}

function cssBlock(sourceText: string, marker: string): string {
  const markerAt = sourceText.indexOf(marker);
  const openAt = markerAt < 0 ? -1 : sourceText.indexOf("{", markerAt);
  if (openAt < 0) return "";
  let depth = 0;
  for (let index = openAt; index < sourceText.length; index += 1) {
    if (sourceText[index] === "{") depth += 1;
    if (sourceText[index] !== "}") continue;
    depth -= 1;
    if (depth === 0) return sourceText.slice(openAt + 1, index);
  }
  return "";
}

describe("responsive application shell CSS", () => {
  it("keeps the topbar primary row wrap-safe for long localized labels", () => {
    const primary = shellCss.match(/\.shell-topbar-primary\s*\{([^}]*)\}/)?.[1] ?? "";

    expect(primary).toMatch(/flex-wrap:\s*wrap/);
  });

  it("stacks narrow surface chrome before localized copy collapses", () => {
    const narrow = cssBlock(legacyCss, "@media (max-width: 760px)");
    const surfaceHead = cssBlock(narrow, ".surface-head");
    const surfaceMeta = cssBlock(narrow, ".surface-head > .muted");
    const surfaceSpacer = cssBlock(narrow, ".surface-head > .spacer");
    const inlineAlert = cssBlock(narrow, ".main .ui-inline-alert");
    const inlineActionRules = Array.from(
      narrow.matchAll(/\.main \.ui-inline-alert > \.ui-inline-alert-action\s*\{([^}]*)\}/g),
      (match) => match[1] ?? "",
    );

    expect(surfaceHead).toMatch(/flex-wrap:\s*wrap/);
    expect(surfaceMeta).toMatch(/flex:\s*1\s+1\s+180px/);
    expect(surfaceSpacer).toMatch(/display:\s*none/);
    expect(inlineAlert).toMatch(/grid-template-columns:\s*minmax\(0,\s*1fr\)/);
    expect(inlineActionRules.some((rule) => /flex-wrap:\s*wrap/.test(rule))).toBe(true);
  });

  it("defines a two-column wide shell and no third rail track", () => {
    const layout = shellCss.match(/\.app-shell-layout\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(layout).toMatch(/grid-template-columns:\s*minmax\([^;]+\)\s+minmax\(0,\s*1fr\)/);
    expect(shellCss).not.toMatch(/rightrail|rail-tab|320px/);
  });

  it("bounds each page root so the page owns vertical scrolling", () => {
    const contentRules = Array.from(
      shellCss.matchAll(/\.app-shell-content\s*\{([^}]*)\}/g),
      (match) => match[1] ?? "",
    );
    const pageRoot = shellCss.match(/\.app-shell-content\s*>\s*\.main\s*\{([^}]*)\}/)?.[1] ?? "";

    expect(contentRules.some((rule) => (
      /display:\s*flex/.test(rule)
      && /flex-direction:\s*column/.test(rule)
      && /overflow:\s*hidden/.test(rule)
    ))).toBe(true);
    expect(pageRoot).toMatch(/flex:\s*1\s+1\s+auto/);
    expect(pageRoot).toMatch(/min-height:\s*0/);
  });

  it("switches overlay layout through data-shell-overlay without an at-media rule", () => {
    expect(shellCss).toMatch(/\.app-shell\[data-shell-overlay="true"\]\s+\.app-shell-layout/);
    expect(shellCss).not.toMatch(/@media/i);
  });

  it("contains no legacy rightrail rail-tab rail-open or rail-closed selector", () => {
    expect(`${legacyCss}\n${shellCss}`).not.toMatch(/\.(?:rightrail|rail-tab|rail-open|rail-closed)(?=[\s.{:#,>+~\[])/);
  });

  it("defines every literal app-shell class used by App and shell components", () => {
    const classes = [...new Set([appSource, ...shellSources].flatMap(literalClasses))]
      .filter((name) => name.startsWith("app-shell") || name.startsWith("shell-"));
    expect(classes.filter((name) => !hasSelector(name))).toEqual([]);
  });

  it("imports shell css from main and keeps the canonical breakpoint in tokens only", () => {
    const stylesAt = mainSource.indexOf('import "./styles.css"');
    const shellAt = mainSource.indexOf('import "./shell/shell.css"');
    const primitivesAt = mainSource.indexOf('import "./ui/primitives.css"');
    expect(stylesAt).toBeGreaterThanOrEqual(0);
    expect(shellAt).toBeGreaterThan(stylesAt);
    expect(primitivesAt).toBeGreaterThan(shellAt);
    expect(shellCss).not.toMatch(/\b(?:959|960|961)\b/);
  });
});
