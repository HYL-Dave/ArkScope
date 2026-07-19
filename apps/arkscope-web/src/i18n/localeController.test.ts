import { describe, expect, it, vi } from "vitest";

import {
  createUiLocaleController,
  type UiLocaleAuthority,
  type UiLocaleResponse,
} from "./localeController";
import type { UiLocale } from "./locale";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function response(locale: UiLocale, source: "default" | "stored" = "stored") {
  return { locale, source } satisfies UiLocaleResponse;
}

function harness(
  authority: UiLocaleAuthority,
  initialLocale: UiLocale = "zh-Hant",
) {
  const applyLocale = vi.fn();
  const writeCache = vi.fn((_locale: UiLocale) => true);
  const controller = createUiLocaleController({
    initialLocale,
    authority,
    applyLocale,
    writeCache,
  });
  return { controller, applyLocale, writeCache };
}

describe("locale controller", () => {
  it("authoritative GET corrects runtime document and cache", async () => {
    const { controller, applyLocale, writeCache } = harness({
      get: vi.fn().mockResolvedValue(response("en")),
      put: vi.fn(),
    });

    await controller.reconcile();

    expect(controller.getSnapshot()).toEqual({
      locale: "en",
      busy: false,
      errorCode: null,
    });
    expect(applyLocale).toHaveBeenCalledOnce();
    expect(applyLocale).toHaveBeenCalledWith("en");
    expect(writeCache).toHaveBeenCalledOnce();
    expect(writeCache).toHaveBeenCalledWith("en");
  });

  it("same-locale GET still refreshes the write-through cache once", async () => {
    const { controller, writeCache } = harness({
      get: vi.fn().mockResolvedValue(response("zh-Hant", "default")),
      put: vi.fn(),
    });

    await controller.reconcile();

    expect(controller.getSnapshot().locale).toBe("zh-Hant");
    expect(writeCache).toHaveBeenCalledOnce();
    expect(writeCache).toHaveBeenCalledWith("zh-Hant");
  });

  it("GET failure preserves bootstrap truth and performs no cache write", async () => {
    const authorities: UiLocaleAuthority[] = [
      {
        get: vi.fn().mockRejectedValue(new Error("private authority detail")),
        put: vi.fn(),
      },
      {
        get: vi.fn().mockResolvedValue({ locale: "fr", source: "stored" }),
        put: vi.fn(),
      } as UiLocaleAuthority,
    ];

    for (const authority of authorities) {
      const { controller, applyLocale, writeCache } = harness(authority);
      await controller.reconcile();
      expect(controller.getSnapshot()).toEqual({
        locale: "zh-Hant",
        busy: false,
        errorCode: null,
      });
      expect(applyLocale).not.toHaveBeenCalled();
      expect(writeCache).not.toHaveBeenCalled();
      expect(JSON.stringify(controller.getSnapshot())).not.toContain("private");
    }
  });

  it("PUT is optimistic but writes cache only after success", async () => {
    const pendingPut = deferred<UiLocaleResponse>();
    const { controller, applyLocale, writeCache } = harness({
      get: vi.fn(),
      put: vi.fn(() => pendingPut.promise),
    });

    const result = controller.setLocale("en");
    expect(controller.getSnapshot()).toEqual({
      locale: "en",
      busy: true,
      errorCode: null,
    });
    expect(applyLocale).toHaveBeenCalledWith("en");
    expect(writeCache).not.toHaveBeenCalled();

    pendingPut.resolve(response("en"));
    await expect(result).resolves.toBe(true);
    expect(controller.getSnapshot()).toEqual({
      locale: "en",
      busy: false,
      errorCode: null,
    });
    expect(writeCache).toHaveBeenCalledOnce();
    expect(writeCache).toHaveBeenCalledWith("en");
  });

  it("PUT failure rolls back and exposes only the stable error code", async () => {
    const authorities: UiLocaleAuthority[] = [
      {
        get: vi.fn(),
        put: vi.fn().mockRejectedValue(new Error("secret provider failure")),
      },
      {
        get: vi.fn(),
        put: vi.fn().mockResolvedValue({ locale: "fr", source: "stored" }),
      } as UiLocaleAuthority,
    ];

    for (const authority of authorities) {
      const { controller, applyLocale, writeCache } = harness(authority);
      await expect(controller.setLocale("en")).resolves.toBe(false);
      expect(controller.getSnapshot()).toEqual({
        locale: "zh-Hant",
        busy: false,
        errorCode: "write_failed",
      });
      expect(applyLocale.mock.calls.map(([locale]) => locale)).toEqual([
        "en",
        "zh-Hant",
      ]);
      expect(writeCache).not.toHaveBeenCalled();
      expect(JSON.stringify(controller.getSnapshot())).not.toContain("secret");
    }
  });

  it("prevents overlapping locale writes", async () => {
    const pendingPut = deferred<UiLocaleResponse>();
    const put = vi.fn(() => pendingPut.promise);
    const { controller } = harness({ get: vi.fn(), put });

    const first = controller.setLocale("en");
    await expect(controller.setLocale("zh-Hant")).resolves.toBe(false);
    expect(put).toHaveBeenCalledOnce();

    pendingPut.resolve(response("en"));
    await expect(first).resolves.toBe(true);
  });

  it("late startup GET cannot override a newer successful PUT", async () => {
    const pendingGet = deferred<UiLocaleResponse>();
    const pendingPut = deferred<UiLocaleResponse>();
    const { controller, applyLocale, writeCache } = harness({
      get: vi.fn(() => pendingGet.promise),
      put: vi.fn(() => pendingPut.promise),
    });

    const reconcile = controller.reconcile();
    const write = controller.setLocale("en");
    pendingPut.resolve(response("en"));
    await write;
    pendingGet.resolve(response("zh-Hant"));
    await reconcile;

    expect(controller.getSnapshot().locale).toBe("en");
    expect(applyLocale.mock.calls.map(([locale]) => locale)).toEqual(["en"]);
    expect(writeCache.mock.calls.map(([locale]) => locale)).toEqual(["en"]);
  });

  it("late startup GET cannot override rollback after a newer failed PUT", async () => {
    const pendingGet = deferred<UiLocaleResponse>();
    const pendingPut = deferred<UiLocaleResponse>();
    const { controller, applyLocale, writeCache } = harness({
      get: vi.fn(() => pendingGet.promise),
      put: vi.fn(() => pendingPut.promise),
    });

    const reconcile = controller.reconcile();
    const write = controller.setLocale("en");
    pendingPut.reject(new Error("private write failure"));
    await write;
    pendingGet.resolve(response("en"));
    await reconcile;

    expect(controller.getSnapshot()).toEqual({
      locale: "zh-Hant",
      busy: false,
      errorCode: "write_failed",
    });
    expect(applyLocale.mock.calls.map(([locale]) => locale)).toEqual([
      "en",
      "zh-Hant",
    ]);
    expect(writeCache).not.toHaveBeenCalled();
  });

  it("coalesces coincident and StrictMode-style startup reconciliation", async () => {
    const pendingGet = deferred<UiLocaleResponse>();
    const get = vi.fn(() => pendingGet.promise);
    const { controller } = harness({ get, put: vi.fn() });

    const first = controller.reconcile();
    const second = controller.reconcile();
    expect(second).toBe(first);
    expect(get).toHaveBeenCalledOnce();

    pendingGet.resolve(response("zh-Hant"));
    await Promise.all([first, second]);
    await controller.reconcile();
    expect(get).toHaveBeenCalledOnce();
  });
});
