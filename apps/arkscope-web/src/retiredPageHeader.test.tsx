/** @vitest-environment jsdom */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { Button } from "./ui/Button";
import { PageHeader } from "./ui/PageHeader";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const styles = readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");
const primitives = readFileSync(resolve(process.cwd(), "src/ui/primitives.css"), "utf8");

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;
const sheets: HTMLStyleElement[] = [];

function readRules(css: string) {
  const sheet = document.createElement("style");
  sheet.textContent = css;
  document.head.appendChild(sheet);
  sheets.push(sheet);
  expect(sheet.sheet).not.toBeNull();
  const rules: { rule: CSSStyleRule; media: boolean }[] = [];
  function visit(children: CSSRuleList, media = false) {
    for (const child of Array.from(children)) {
      if (child.type === CSSRule.STYLE_RULE) {
        rules.push({ rule: child as CSSStyleRule, media });
      }
      if ("cssRules" in child) {
        visit((child as CSSGroupingRule).cssRules, media || child.type === CSSRule.MEDIA_RULE);
      }
    }
  }
  visit(sheet.sheet!.cssRules);
  expect(rules.length).toBeGreaterThan(0);
  return rules;
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  host?.remove();
  for (const sheet of sheets.splice(0)) sheet.remove();
  root = null;
  host = null;
});

describe("EIR-001 retired page-header selectors", () => {
  it.each(["desktop", "media"] as const)(
    "has no exact .page-head or .page-head-actions class selectors in %s rules",
    (scope) => {
      const rules = readRules(styles).filter(({ media }) => media === (scope === "media"));
      expect(rules.length).toBeGreaterThan(0);
      // Match complete class tokens, not detailpage-head or ui-page-header.
      const retired = /\.page-head(?:-actions)?(?![\w-])/;
      expect(rules.filter(({ rule }) => retired.test(rule.selectorText))
        .map(({ rule }) => rule.selectorText)).toEqual([]);
    },
  );

  it("retains styled real PageHeader and detailpage-head positive controls", async () => {
    const rules = [...readRules(styles), ...readRules(primitives)];
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    await act(async () => root!.render(
      <>
        <PageHeader
          eyebrow="Portfolio"
          title="Holdings"
          context={<span>9 positions</span>}
          actions={<Button>Refresh</Button>}
        />
        <div className="detailpage-head"><button type="button">Back</button></div>
      </>,
    ));

    expect(host.querySelectorAll("h1")).toHaveLength(1);
    expect(host.querySelector("h1")?.textContent).toBe("Holdings");
    expect(host.querySelector(".ui-page-header-context")?.textContent).toBe("9 positions");
    expect(host.querySelector(".ui-page-header-actions button")?.textContent).toBe("Refresh");
    expect(host.querySelector(".page-head, .page-head-actions")).toBeNull();
    for (const selector of [
      ".detailpage-head",
      ".ui-page-header",
      ".ui-page-header-copy",
      ".ui-page-header h1",
      ".ui-page-header-context",
      ".ui-page-header-actions",
    ]) {
      expect(host.querySelector(selector), selector).not.toBeNull();
      const controls = rules.filter(({ rule }) => rule.selectorText === selector);
      expect(controls.length, selector).toBeGreaterThan(0);
      for (const { rule } of controls) expect(rule.style.length, selector).toBeGreaterThan(0);
    }
  });
});
