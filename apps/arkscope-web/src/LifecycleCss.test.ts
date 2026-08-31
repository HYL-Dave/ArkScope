import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(here, "./styles.css"), "utf8");

function rule(selector: string, source = css): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return source.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
}

function media(maxWidth: number): string {
  const marker = `@media (max-width: ${maxWidth}px)`;
  const start = css.indexOf(marker);
  if (start < 0) return "";
  const open = css.indexOf("{", start);
  let depth = 1;
  for (let index = open + 1; index < css.length; index += 1) {
    if (css[index] === "{") depth += 1;
    if (css[index] !== "}") continue;
    depth -= 1;
    if (depth === 0) return css.slice(open + 1, index);
  }
  return "";
}

describe("lifecycle queue CSS contract", () => {
  it("keeps four stable desktop segments and two bounded mobile columns", () => {
    expect(rule(".lifecycle-queue-switch")).toMatch(/display:\s*grid/);
    expect(rule(".lifecycle-queue-switch")).toMatch(
      /grid-template-columns:\s*repeat\(4,\s*minmax\(8rem,\s*1fr\)\)/,
    );
    expect(rule(".lifecycle-queue-switch .ui-button")).toMatch(/white-space:\s*normal/);
    expect(rule(".lifecycle-queue-switch .ui-button")).toMatch(/min-height:\s*[^;]+/);
    expect(rule(".lifecycle-queue-switch", media(720))).toMatch(
      /grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
  });

  it("keeps closed manual evidence commands out of layout", () => {
    expect(
      rule(".lifecycle-manual-supplement:not([open]) > .lifecycle-commands"),
    ).toMatch(/display:\s*none/);
  });

  it("keeps closed evidence bodies out of layout", () => {
    expect(
      rule(".lifecycle-evidence-item:not([open]) > .lifecycle-evidence-body"),
    ).toMatch(/display:\s*none/);
  });
});
