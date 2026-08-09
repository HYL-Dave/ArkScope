import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";


describe("legacy score retirement boundary", () => {
  it("removes score fields from current frontend DTOs and fixtures", () => {
    const root = fileURLToPath(new URL(".", import.meta.url));
    const owners = ["api.ts", "Home.test.tsx", "Watchlist.test.tsx", "Universe.test.tsx"];
    const retired = ["sentiment_mean", "bullish_ratio"];

    for (const owner of owners) {
      const source = readFileSync(`${root}/${owner}`, "utf8");
      for (const field of retired) {
        expect(source, `${owner} still carries ${field}`).not.toContain(field);
      }
    }
  });
});
