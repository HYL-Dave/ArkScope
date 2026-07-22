/// <reference types="node" />

import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));
const primitiveCss = readFileSync(resolve(here, "./ui/primitives.css"), "utf8");

function tsxFiles(root: string): string[] {
  if (!existsSync(root)) return [];
  return readdirSync(root, { withFileTypes: true })
    .sort((left, right) => left.name.localeCompare(right.name))
    .flatMap((entry) => {
      const path = resolve(root, entry.name);
      if (entry.isDirectory()) return tsxFiles(path);
      return entry.isFile() && entry.name.endsWith(".tsx") ? [path] : [];
    });
}

function literalClasses(source: string): string[] {
  return Array.from(source.matchAll(/className="([^"]+)"/g))
    .flatMap((match) => match[1].split(/\s+/))
    .filter(Boolean);
}

function hasSelector(name: string): boolean {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`\\.${escaped}(?=[\\s.{:#,>+~\\[])`).test(primitiveCss);
}

function rule(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return primitiveCss.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
}

describe("Investor Profile workspace CSS", () => {
  it("defines every Slice 5 Investor class", () => {
    const controller = resolve(here, "./InvestorProfilePanel.tsx");
    const context = resolve(here, "./ResearchPersonalizationContext.tsx");
    const sources = [controller, ...tsxFiles(resolve(here, "./settings/investor")), context]
      .filter(existsSync)
      .map((path) => readFileSync(path, "utf8"));
    const classes = [...new Set(sources.flatMap(literalClasses))]
      .filter((name) => (
        name === "investor-profile-panel"
        || name.startsWith("ip-")
        || name.startsWith("research-personalization-context")
      ));

    expect(classes).toEqual(expect.arrayContaining([
      "investor-profile-panel",
      "ip-actions",
      "ip-calibration-log",
      "ip-chip",
      "ip-grid",
      "ip-guardrail",
      "research-personalization-context",
      "research-personalization-context-source",
    ]));
    expect(classes.filter((name) => !hasSelector(name)).sort()).toEqual([]);
  });

  it("uses responsive intrinsic grids and wrap-safe command rows", () => {
    expect(rule(".ip-grid")).toMatch(/display:\s*grid/);
    expect(rule(".ip-grid")).toMatch(/repeat\(auto-fit,\s*minmax\(/);

    const proposalGrid = rule('.investor-profile-panel [data-testid="proposal-changes"] > div');
    expect(proposalGrid).toMatch(/display:\s*grid/);
    expect(proposalGrid).toMatch(/repeat\(auto-fit,\s*minmax\(/);

    const proposalRow = rule('.investor-profile-panel [data-testid="proposal-changes"] .ip-guardrail');
    expect(proposalRow).toMatch(/display:\s*grid/);
    expect(proposalRow).toMatch(/grid-template-columns:[^;]*minmax\(/);

    const modeHeading = rule(".investor-profile-panel [data-investor-mode-heading]");
    expect(modeHeading).toMatch(/min-height:\s*var\(--control-height-default\)/);
    expect(modeHeading).toMatch(/overflow-wrap:\s*anywhere/);

    expect(rule(".ip-actions")).toMatch(/flex-wrap:\s*wrap/);
    expect(rule(".ip-actions .ui-button")).toMatch(/white-space:\s*normal/);
    expect(rule(".ip-actions .ui-button")).toMatch(/overflow-wrap:\s*anywhere/);
    expect(rule(".ip-chip")).toMatch(/max-width:\s*100%/);
    expect(rule(".ip-chip")).toMatch(/white-space:\s*normal/);
    expect(rule(".ip-chip")).toMatch(/overflow-wrap:\s*anywhere/);

    expect(rule(".ip-calibration-log")).toMatch(/max-height:/);
    expect(rule(".ip-calibration-log")).toMatch(/overflow:\s*auto/);
    expect(rule(".research-personalization-context-source")).toMatch(/white-space:\s*pre-wrap/);
    expect(rule(".research-personalization-context-source")).toMatch(/overflow-wrap:\s*anywhere/);
  });

  it("keeps the Summary current-context source intrinsically wrap-safe", () => {
    const contextSource = rule(
      '.investor-profile-panel [data-testid="current-context-disclosure"] pre',
    );

    expect(contextSource).toMatch(/min-width:\s*0/);
    expect(contextSource).toMatch(/max-width:\s*100%/);
    expect(contextSource).toMatch(/white-space:\s*pre-wrap/);
    expect(contextSource).toMatch(/overflow-wrap:\s*anywhere/);
  });

  it("keeps the Calibration current question intrinsically wrap-safe", () => {
    const currentQuestion = rule(
      ".investor-profile-panel > .ip-calibration > section blockquote",
    );

    expect(currentQuestion).toMatch(/min-width:\s*0/);
    expect(currentQuestion).toMatch(/max-width:\s*100%/);
    expect(currentQuestion).toMatch(/white-space:\s*pre-wrap/);
    expect(currentQuestion).toMatch(/overflow-wrap:\s*anywhere/);
  });

  it("targets Edit labels and toggle through the split-renderer root only", () => {
    const editLabel = rule(
      '.investor-profile-panel > [data-testid="investor-profile-edit"] > label',
    );
    const editToggle = rule(
      '.investor-profile-panel > [data-testid="investor-profile-edit"] > .ip-toggle',
    );

    expect(editLabel).toMatch(/display:\s*grid/);
    expect(editLabel).toMatch(/color:\s*var\(--muted\)/);
    expect(editToggle).toMatch(/display:\s*flex/);
    expect(editToggle).toMatch(/align-items:\s*center/);
    expect(primitiveCss).not.toMatch(
      /\.investor-profile-panel\s*>\s*label(?=\s*[,{}])/,
    );
    expect(primitiveCss).not.toMatch(/\.investor-profile-panel\s*>\s*\.ip-toggle\b/);
  });

  it("adds no media query breakpoint or nested-card selector", () => {
    const additionStart = primitiveCss.indexOf(".investor-profile-panel > section");
    expect(additionStart).toBeGreaterThanOrEqual(0);
    const addition = primitiveCss.slice(additionStart);

    expect(addition).not.toMatch(/@media/i);
    expect(addition).not.toMatch(/\b(?:959|960|961)(?:px)?\b/);
    expect(addition).not.toMatch(/font-size:\s*[^;{}]*vw/i);
    expect(addition).not.toMatch(/letter-spacing:\s*-/i);
    expect(addition).not.toMatch(
      /\.ip-guardrail\s+\.ip-guardrail|\.research-personalization-context\s+\.ip-guardrail|\.ip-guardrail\s+\.research-personalization-context/,
    );
    expect(addition).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
  });
});
