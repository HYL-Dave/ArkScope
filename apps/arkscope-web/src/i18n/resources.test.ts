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
        backlog: "內文佇列：待處理",
        earliest: "最早 2026-07-21T03:04:05Z",
        catalogFailure: "無法載入 AI 模型設定。請重新整理，或到 System / Health 檢查連線。",
        routeBlocked: "本次變更尚未儲存：請先到 Provider 登入與憑證完成 AI 研究所選 provider 的登入。",
        missingModel: "儲存前，請為 AI 研究選擇或輸入模型。",
        environmentRoute: "目前由環境變數控制；可以儲存到 DB，但 runtime 仍以 env 為準。",
        unavailable: "不可選：缺少任務能力",
        maximumEffort: "使用最大 reasoning effort；目前只有 GPT-5.6 系列 model 支援。",
        fixedDescription: "較高 effort 的模型可能需要更久；這裡只控制最長等待時間，不會變更模型或 effort。",
        fixedSaved: "固定 AI 任務執行限制已儲存到 profile DB。",
        fixedReset: "固定 AI 任務執行限制已重設為環境變數／內建預設。",
        researchDescription: "控制單次 AI 研究的工具輪數與 subscription driver timeout。API-key 路徑目前只套用 max turns；切頁不中斷與並行會由 server-owned run manager 解決。",
        maxToolCalls: "模型可連續呼叫工具的最大輪數；API-key 與 subscription Research 都會套用。",
        researchSaved: "AI 研究執行限制已儲存到 profile DB。",
        researchReset: "AI 研究執行限制已重設為設定檔／內建預設。",
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
        backlog: "Body queue: Pending",
        earliest: "Earliest retry: 2026-07-21T03:04:05Z",
        catalogFailure: "Could not load AI model settings. Refresh the page, or check the connection under System / Health.",
        routeBlocked: "These changes were not saved. Complete the selected provider sign-in for AI Research under Provider Sign-in and Credentials first.",
        missingModel: "Select or enter a model for AI Research before saving.",
        environmentRoute: "The environment currently controls this route. You can save a DB value, but runtime continues to follow the environment override.",
        unavailable: "Unavailable: Task capability is missing",
        maximumEffort: "Maximum reasoning effort; currently supported by GPT-5.6 models.",
        fixedDescription: "Higher-effort models may need more time. These limits only control the maximum wait; they do not change the model or effort.",
        fixedSaved: "Fixed AI task runtime limits were saved to the profile DB.",
        fixedReset: "Fixed AI task runtime limits were reset to the environment or built-in defaults.",
        researchDescription: "Controls tool turns and subscription-driver timeouts for one AI Research run. The API-key path currently applies only the maximum turn limit; page navigation continuity and concurrency remain owned by the server run manager.",
        maxToolCalls: "The maximum number of consecutive tool-call turns; applies to both API-key and subscription Research.",
        researchSaved: "AI Research runtime limits were saved to the profile DB.",
        researchReset: "AI Research runtime limits were reset to the profile file or built-in defaults.",
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
      expect(t(($) => $.dataSources.schedule.backlog.queue, { value: expected.locale === "en" ? "Pending" : "待處理" }))
        .toBe(expected.backlog);
      expect(t(($) => $.dataSources.schedule.backlog.earliest, { timestamp: "2026-07-21T03:04:05Z" }))
        .toBe(expected.earliest);
      expect(t(($) => $.workspace.catalog.failure)).toBe(expected.catalogFailure);
      expect(t(($) => $.workspace.routes.saveBlocked, { value: expected.task }))
        .toBe(expected.routeBlocked);
      expect(t(($) => $.workspace.routes.missingModel, { taskLabel: expected.task }))
        .toBe(expected.missingModel);
      expect(t(($) => $.models.route.envOverrideDetail)).toBe(expected.environmentRoute);
      expect(t(($) => $.models.compatibility.unavailableReasons, {
        value: expected.locale === "en" ? "Task capability is missing" : "缺少任務能力",
      })).toBe(expected.unavailable);
      expect(t(($) => $.models.effortDescriptions.openai.max, { sourceId: "GPT-5.6" }))
        .toBe(expected.maximumEffort);
      expect(t(($) => $.runtime.fixed.description)).toBe(expected.fixedDescription);
      expect(t(($) => $.runtime.fixed.saved)).toBe(expected.fixedSaved);
      expect(t(($) => $.runtime.fixed.reset)).toBe(expected.fixedReset);
      expect(t(($) => $.runtime.research.description)).toBe(expected.researchDescription);
      expect(t(($) => $.runtime.research.help.maxToolCalls)).toBe(expected.maxToolCalls);
      expect(t(($) => $.runtime.research.saved)).toBe(expected.researchSaved);
      expect(t(($) => $.runtime.research.reset)).toBe(expected.researchReset);
    }
  });

  it("contains exactly 520 Settings leaves per locale", () => {
    const expectedSubtreeCounts = {
      actions: 18,
      workspace: 29,
      registry: 30,
      errors: 13,
      models: 91,
      runtime: 21,
      providers: 104,
      dataSources: 85,
      dataStorage: 37,
      newsStorage: 11,
      macroStorage: 27,
      investor: 53,
    } as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      const settings = resources[locale].settings as ResourceTree;
      expect(flattenResource(settings).size).toBe(520);
      expect(flattenResource(settings.locale as ResourceTree).size).toBe(1);
      for (const [subtree, count] of Object.entries(expectedSubtreeCounts)) {
        expect(flattenResource(settings[subtree] as ResourceTree).size, `${locale}.${subtree}`)
          .toBe(count);
      }
    }
  });
});
