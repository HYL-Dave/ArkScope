import { createInstance } from "i18next";
import { describe, expect, it } from "vitest";

import { initializeI18n, resourceNamespaces, resources } from "./resources";

type ResourceTree = Record<string, unknown>;

function flattenResource(tree: ResourceTree, prefix = ""): Map<string, string> {
  const flattened = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") {
      flattened.set(path, value);
    } else if (value && typeof value === "object" && !Array.isArray(value)) {
      for (const [nestedPath, nestedValue] of flattenResource(
        value as ResourceTree,
        path,
      )) {
        flattened.set(nestedPath, nestedValue);
      }
    } else {
      throw new Error(`Non-string resource leaf at ${path}`);
    }
  }
  return flattened;
}

describe("bundled i18n resources", () => {
  it("keeps locale namespace and recursive key paths identical", () => {
    const zhNamespaces = Object.keys(resources["zh-Hant"]).sort();
    const enNamespaces = Object.keys(resources.en).sort();
    expect(enNamespaces).toEqual(zhNamespaces);

    for (const namespace of resourceNamespaces) {
      const zhKeys = [...flattenResource(resources["zh-Hant"][namespace]).keys()].sort();
      const enKeys = [...flattenResource(resources.en[namespace]).keys()].sort();
      expect(enKeys).toEqual(zhKeys);
    }
  });

  it("requires every resource leaf to be a non-empty string", () => {
    for (const locale of ["zh-Hant", "en"] as const) {
      for (const namespace of resourceNamespaces) {
        for (const value of flattenResource(resources[locale][namespace]).values()) {
          expect(value.trim()).not.toBe("");
        }
      }
    }
  });

  it("initializes bundled zh-Hant resources synchronously", () => {
    const instance = createInstance();

    initializeI18n(instance, "zh-Hant");

    expect(instance.isInitialized).toBe(true);
    expect(instance.language).toBe("zh-Hant");
    expect(instance.t(($) => $.i18n.missingTranslation)).toBe(
      "此文字暫時無法顯示。",
    );
  });

  it("switches to bundled English without loading resources", async () => {
    const instance = createInstance();
    initializeI18n(instance, "zh-Hant");

    await instance.changeLanguage("en");

    expect(instance.language).toBe("en");
    expect(instance.t(($) => $.i18n.missingTranslation)).toBe(
      "This text is temporarily unavailable.",
    );
    expect(instance.hasResourceBundle("zh-Hant", "settings")).toBe(true);
    expect(instance.hasResourceBundle("en", "settings")).toBe(true);
  });

  it("returns localized safe copy instead of a raw missing key", async () => {
    const instance = createInstance();
    initializeI18n(instance, "zh-Hant");

    // @ts-expect-error Unknown selectors must fail statically while runtime remains safe.
    expect(instance.t(($) => $.i18n.notARealKey)).toBe("此文字暫時無法顯示。");
    await instance.changeLanguage("en");
    // @ts-expect-error Unknown selectors must fail statically while runtime remains safe.
    expect(instance.t(($) => $.i18n.notARealKey)).toBe(
      "This text is temporarily unavailable.",
    );
  });

  it("supports exactly one reviewed typed translation-key style", () => {
    const instance = createInstance();
    initializeI18n(instance, "en");

    const translated: string = instance.t(
      ($) => $.locale.writeFailed,
      { ns: "settings" },
    );
    expect(translated).toBe(
      "Could not save the interface language. The previous setting was restored.",
    );
  });

  it("resolves the reviewed common and shell copy in both locales", () => {
    const cases = [
      {
        locale: "zh-Hant" as const,
        close: "關閉",
        result: "結果：AI 研究對話",
        universe: "全部標的",
        running: "執行中 2",
      },
      {
        locale: "en" as const,
        close: "Close",
        result: "Result: AI Research conversation",
        universe: "Universe",
        running: "Running 2",
      },
    ];

    for (const expected of cases) {
      const instance = createInstance();
      initializeI18n(instance, expected.locale);
      const commonT = instance.getFixedT(expected.locale, "common");
      const shellT = instance.getFixedT(expected.locale, "shell");
      expect(commonT(($) => $.actions.close)).toBe(expected.close);
      expect(commonT(($) => $.boundedProgress.result, {
        destination: expected.locale === "en"
          ? "AI Research conversation"
          : "AI 研究對話",
      })).toBe(expected.result);
      expect(shellT(($) => $.navigation.views.universe)).toBe(expected.universe);
      expect(shellT(($) => $.backgroundWork.activeCount, { count: 2 }))
        .toBe(expected.running);
    }
  });

  it("resolves the reviewed Settings copy inventory in both locales", () => {
    const cases = [
      {
        locale: "zh-Hant" as const,
        action: "儲存",
        workspace: "設定",
        section: "資料來源與排程",
        task: "AI 研究",
        provider: "IBKR Gateway",
        schedule: "價格缺口補抓",
        coverage: "交易日 / 價格覆蓋",
        news: "新聞資料",
        macro: "總經資料",
        investor: "風險意願高於承受能力",
      },
      {
        locale: "en" as const,
        action: "Save",
        workspace: "Settings",
        section: "Data Sources and Schedules",
        task: "AI Research",
        provider: "IBKR Gateway",
        schedule: "Price Gap Backfill",
        coverage: "Trading-day / Price Coverage",
        news: "News Data",
        macro: "Macro Data",
        investor: "Risk appetite above capacity",
      },
    ];

    for (const expected of cases) {
      const instance = createInstance();
      initializeI18n(instance, expected.locale);
      const t = instance.getFixedT(expected.locale, "settings");
      expect(t(($) => $.actions.save)).toBe(expected.action);
      expect(t(($) => $.workspace.title)).toBe(expected.workspace);
      expect(t(($) => $.registry.sections.dataSources.title)).toBe(expected.section);
      expect(t(($) => $.models.tasks.aiResearch.label)).toBe(expected.task);
      expect(t(($) => $.dataSources.providers.names.ibkr)).toBe(expected.provider);
      expect(t(($) => $.dataSources.schedule.sources.priceBackfill.label)).toBe(expected.schedule);
      expect(t(($) => $.dataStorage.coverage.title)).toBe(expected.coverage);
      expect(t(($) => $.newsStorage.title)).toBe(expected.news);
      expect(t(($) => $.macroStorage.title)).toBe(expected.macro);
      expect(t(($) => $.investor.mismatch.appetiteAboveCapacity)).toBe(expected.investor);
    }
  });

  it("contains exactly 486 Settings leaves per locale", () => {
    const expectedSubtreeCounts = {
      actions: 18,
      workspace: 27,
      registry: 30,
      errors: 13,
      models: 62,
      runtime: 20,
      providers: 104,
      dataSources: 83,
      dataStorage: 37,
      newsStorage: 11,
      macroStorage: 27,
      investor: 53,
    } as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      const settings = resources[locale].settings as ResourceTree;
      expect(flattenResource(settings).size).toBe(486);
      expect(flattenResource(settings.locale as ResourceTree).size).toBe(1);
      for (const [subtree, count] of Object.entries(expectedSubtreeCounts)) {
        expect(flattenResource(settings[subtree] as ResourceTree).size, `${locale}.${subtree}`)
          .toBe(count);
      }
    }
  });
});
