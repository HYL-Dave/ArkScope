import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(here, "./styles.css"), "utf8");

function rule(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
}

describe("portfolio capture responsive table contract", () => {
  it("keeps_financial_columns_stable_inside_the_horizontal_scroll_owner", () => {
    expect(rule(".portfolio-capture .ui-data-table")).toMatch(/min-width:\s*620px/);
    expect(rule(".portfolio-capture-review .ui-data-table")).toMatch(/min-width:\s*760px/);
    expect(rule('.portfolio-capture .ui-data-table [data-align="right"]')).toMatch(
      /white-space:\s*nowrap/,
    );
  });
});
