/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("card API timeouts", () => {
  it("keeps generation and translation UI budgets above the provider deadline", async () => {
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
    await generateCard("MU", { provider: "anthropic" });
    await translateCard(1);

    const budgets = setTimeoutSpy.mock.calls.map((call) => call[1]);
    expect(budgets).toEqual([300_000, 300_000]);
  });
});
