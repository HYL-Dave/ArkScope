/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  getProvidersConfig,
  putProviderConfig,
  setUiLocale,
} from "./api";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

async function rejected(operation: Promise<unknown>): Promise<unknown> {
  try {
    await operation;
  } catch (error) {
    return error;
  }
  throw new Error("expected operation to reject");
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("typed API errors", () => {
  it("preserves the legacy GET message while capturing structured HTTP metadata", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(503, {
      detail: {
        code: "provider_config_setup_required",
        message: "planted setup detail",
      },
    })));

    await expect(getProvidersConfig()).rejects.toMatchObject({
      name: "ApiError",
      message: "/providers/config returned 503",
      path: "/providers/config",
      status: 503,
      code: "provider_config_setup_required",
      diagnostic: "planted setup detail",
    });
  });

  it("preserves the legacy mutation message while exposing a stable code", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(409, {
      detail: { code: "guarded_provider_setting" },
    })));

    const error = await rejected(putProviderConfig("ibkr", { client_id: "7" }));
    expect(error).toMatchObject({
      name: "ApiError",
      message: "/providers/config/ibkr returned 409: guarded_provider_setting",
      path: "/providers/config/ibkr",
      status: 409,
      code: "guarded_provider_setting",
      diagnostic: null,
    });
  });

  it("captures string detail as diagnostic without inventing a code", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(422, {
      detail: "planted string detail",
    })));

    const error = await rejected(setUiLocale("en"));
    expect(error).toMatchObject({
      name: "ApiError",
      message: "/profile/settings/ui-locale returned 422: planted string detail",
      path: "/profile/settings/ui-locale",
      status: 422,
      code: null,
      diagnostic: "planted string detail",
    });
  });

  it("handles malformed and empty error bodies without invented detail", async () => {
    const cases = [
      new Response("not json", { status: 500 }),
      new Response(null, { status: 500 }),
      jsonResponse(500, []),
      jsonResponse(500, { detail: 17 }),
    ];
    const fetchMock = vi.fn();
    for (const response of cases) fetchMock.mockResolvedValueOnce(response);
    vi.stubGlobal("fetch", fetchMock);

    for (const _case of cases) {
      const error = await rejected(getProvidersConfig());
      expect(error).toMatchObject({
        name: "ApiError",
        message: "/providers/config returned 500",
        code: null,
        diagnostic: null,
      });
    }
  });

  it("keeps timeout and network failures outside HTTP ApiError classification", async () => {
    const aborted = new Error("aborted");
    aborted.name = "AbortError";
    const network = new TypeError("network unavailable");
    vi.stubGlobal("fetch", vi.fn()
      .mockRejectedValueOnce(aborted)
      .mockRejectedValueOnce(network));

    const timeoutError = await rejected(getProvidersConfig());
    expect(timeoutError).toBeInstanceOf(Error);
    expect(timeoutError).not.toBeInstanceOf(ApiError);
    expect(timeoutError).toMatchObject({
      name: "Error",
      message: "/providers/config timed out after 8s",
    });

    const networkError = await rejected(getProvidersConfig());
    expect(networkError).toBe(network);
    expect(networkError).not.toBeInstanceOf(ApiError);
  });

  it("keeps every existing public API error instance compatible with Error", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(jsonResponse(503, { detail: { code: "setup_required" } }))
      .mockResolvedValueOnce(jsonResponse(409, { detail: "guarded" })));

    const errors = [
      await rejected(getProvidersConfig()),
      await rejected(putProviderConfig("ibkr", {})),
    ];
    for (const error of errors) {
      expect(error).toBeInstanceOf(Error);
      expect(error).toBeInstanceOf(ApiError);
      expect((error as Error).name).toBe("ApiError");
    }
  });
});
