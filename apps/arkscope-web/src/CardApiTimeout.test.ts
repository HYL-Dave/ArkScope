/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RuntimeConfig } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("card API timeouts", () => {
  const runtimeWith = (synthesis: number, translation: number) => ({
    fixed_task_runtime: {
      card_synthesis: {
        task: "card_synthesis",
        model_timeout_s: synthesis,
        source: "db",
        db_saved: true,
        warning: null,
      },
      card_translation: {
        task: "card_translation",
        model_timeout_s: translation,
        source: "db",
        db_saved: true,
        warning: null,
      },
    },
  }) as RuntimeConfig;

  it("derives independent task budgets and uses 900 seconds for old sidecars", async () => {
    const { fixedTaskRequestTimeoutMs } = await import("./api");

    expect(fixedTaskRequestTimeoutMs(null, "card_synthesis")).toBe(960_000);
    expect(fixedTaskRequestTimeoutMs(runtimeWith(1200, 600), "card_synthesis")).toBe(1_260_000);
    expect(fixedTaskRequestTimeoutMs(runtimeWith(1200, 600), "card_translation")).toBe(660_000);
  });

  it("uses each effective task budget for generation and translation", async () => {
    const setTimeoutSpy = vi.spyOn(window, "setTimeout");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response("{}", {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    const { generateCard, translateCard } = await import("./api");
    const runtime = runtimeWith(1200, 600);
    await generateCard("MU", { provider: "anthropic" }, runtime);
    await translateCard(1, "zh-Hant", runtime);

    const budgets = setTimeoutSpy.mock.calls.map((call) => call[1]);
    expect(budgets).toEqual([1_260_000, 660_000]);
  });
});
