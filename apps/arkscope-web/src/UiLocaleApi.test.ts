/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from "vitest";

import { getUiLocale, setUiLocale } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("UI locale API", () => {
  it("GETs the key-specific ui-locale route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ locale: "zh-Hant", source: "default" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(getUiLocale()).resolves.toEqual({
      locale: "zh-Hant",
      source: "default",
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("http://127.0.0.1:8420/profile/settings/ui-locale");
    expect((init as RequestInit).method).toBeUndefined();
  });

  it("PUTs only the validated locale field to the key-specific route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ locale: "en", source: "stored" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(setUiLocale("en")).resolves.toEqual({
      locale: "en",
      source: "stored",
    });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(String(url)).toBe("http://127.0.0.1:8420/profile/settings/ui-locale");
    expect(init.method).toBe("PUT");
    expect(new Headers(init.headers).get("content-type")).toBe("application/json");
    expect(JSON.parse(String(init.body))).toEqual({ locale: "en" });
    expect(Object.keys(JSON.parse(String(init.body)))).toEqual(["locale"]);
  });
});
