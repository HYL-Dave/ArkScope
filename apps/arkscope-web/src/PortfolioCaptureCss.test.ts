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

  it("keeps_account_detail_financial_columns_inside_one_scroll_owner", () => {
    expect(rule(".portfolio-account-details .ui-data-table")).toMatch(
      /min-width:\s*1800px/,
    );
    expect(rule('.portfolio-account-details .ui-data-table [data-align="right"]'))
      .toMatch(/white-space:\s*nowrap/);
  });

  it("lets_the_completed_portfolio_tabs_wrap_without_a_new_breakpoint", () => {
    expect(rule(".portfolio-view-tabs")).toMatch(/flex-wrap:\s*wrap/);
    expect(rule(".portfolio-view-tab")).toMatch(
      /min-height:\s*var\(--control-height-default\)/,
    );
  });
});
