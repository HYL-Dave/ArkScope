import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { createInstance } from "i18next";
import { describe, expect, it } from "vitest";

import { initializeI18n, resourceNamespaces, resources } from "./resources";
type ResourceTree = Record<string, unknown>;

interface PortfolioSourceClaim {
  signature: string;
  count: number;
  claimType: "exact" | "shared_exact" | "plural_exact" | "compound_plural"
    | "template_prefix" | "template_suffix" | "excluded";
  path?: string;
  paths?: string[];
  reason?: string;
  sharedContext?: string;
}

interface PortfolioOwnershipContract {
  version: 2;
  sourceClaims: PortfolioSourceClaim[];
  directUiClaims: Array<{
    claimType: "direct_ui";
    id: string;
    path: string;
    sourceFile: string;
    selector: string;
  }>;
  presenterClaims: Array<{
    claimType: "presenter";
    id: string;
    path: string;
  }>;
  referenceClaims: Array<{
    claimType: "presenter_reference";
    id: string;
    path: string;
    sourceSignature: string;
  }>;
}

function normalizePortfolioCopy(value: string): string {
  const input = value.replaceAll("&amp;", "&").replaceAll("&gt;", ">");
  let output = "";
  for (let index = 0; index < input.length;) {
    if (input.startsWith("{{", index)) {
      const end = input.indexOf("}}", index + 2);
      output += "{{value}}";
      index = end < 0 ? input.length : end + 2;
    } else if (input.startsWith("${", index)) {
      let depth = 1;
      let end = index + 2;
      while (end < input.length && depth > 0) {
        if (input[end] === "{") depth += 1;
        if (input[end] === "}") depth -= 1;
        end += 1;
      }
      output += "{{value}}";
      index = end;
    } else {
      output += input[index];
      index += 1;
    }
  }
  return output;
}

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
  it("contains the exact Explore subtree inventory in both locales", () => {
    const expectedSubtreeCounts = {
      errors: 48,
      home: 23,
      watchlist: 71,
      universe: 38,
      lifecycle: 410,
      news: 44,
      tickerDetail: 89,
      aiCard: 67,
      tags: 7,
    } as const;
    const expectedCountCopy = {
      "zh-Hant": {
        watchlist: {
          renderedTickerCount: { one: "{{count}} 檔", other: "{{count}} 檔" },
          customListCount: { one: "· {{count}} 個自訂清單", other: "· {{count}} 個自訂清單" },
          noteCount: { one: "{{count}} 筆筆記", other: "{{count}} 筆筆記" },
          consensusAnalystSummary: {
            one: "共 {{total}} 位分析師 · 更新 {{when}}",
            other: "共 {{total}} 位分析師 · 更新 {{when}}",
          },
        },
        universe: {
          noteCount: { one: "{{count}} 筆記", other: "{{count}} 筆記" },
          summaryCounts: {
            one: "{{total}} 檔 · {{summarized}} 有摘要 · {{withoutSummary}} 無摘要",
            other: "{{total}} 檔 · {{summarized}} 有摘要 · {{withoutSummary}} 無摘要",
          },
        },
      },
      en: {
        watchlist: {
          renderedTickerCount: { one: "{{count}} ticker", other: "{{count}} tickers" },
          customListCount: { one: "· {{count}} custom list", other: "· {{count}} custom lists" },
          noteCount: { one: "{{count}} note", other: "{{count}} notes" },
          consensusAnalystSummary: {
            one: "{{total}} analyst · Updated {{when}}",
            other: "{{total}} analysts · Updated {{when}}",
          },
        },
        universe: {
          noteCount: { one: "{{count}} note", other: "{{count}} notes" },
          summaryCounts: {
            one: "{{total}} ticker · {{summarized}} with summary · {{withoutSummary}} without summary",
            other: "{{total}} tickers · {{summarized}} with summary · {{withoutSummary}} without summary",
          },
        },
      },
    } as const;
    const expectedNewsCopy = {
      "zh-Hant": {
        marketSearchSummary: "· 搜尋「{{query}}」（按相關性排序，標題加權）",
        seekingAlphaSearchSummary: "· 搜尋「{{query}}」",
        loadMoreProgress: "載入更多（{{visible}}/{{total}}）",
        modeLabel: "新聞來源",
        marketProviderLabel: "市場新聞 Provider",
        dayWindowLabel: "時間範圍",
      },
      en: {
        marketSearchSummary: "· Search “{{query}}” (sorted by relevance with title weighting)",
        seekingAlphaSearchSummary: "· Search “{{query}}”",
        loadMoreProgress: "Load more ({{visible}}/{{total}})",
        modeLabel: "News source",
        marketProviderLabel: "Market News provider",
        dayWindowLabel: "Time window",
      },
    } as const;
    const expectedTask7Copy = {
      "zh-Hant": {
        tickerDetail: {
          statementSummary: {
            one: "{{title}}（{{count}} 期）",
            other: "{{title}}（{{count}} 期）",
          },
          retry: "重試",
          sourceStoredSec: "已儲存的 SEC 基本面",
          kvLabels: {
            latestClose: "最新收盤價",
            changePercent: "漲跌幅",
            periodHigh: "區間高點",
            periodLow: "區間低點",
            rangePercent: "區間振幅",
            volume: "成交量",
            bars: "K 線筆數",
            dates: "日期範圍",
            snapshotDate: "快照日期",
            marketCap: "市值",
            pe: "P/E",
            forwardPe: "Forward P/E",
            ps: "P/S",
            pb: "P/B",
            roe: "ROE",
            roa: "ROA",
            debtToEquity: "D/E",
            currentRatio: "流動比率",
            grossMargin: "毛利率",
            operatingMargin: "營業利益率",
            netMargin: "淨利率",
            revenueGrowth: "營收成長",
            earningsGrowth: "獲利成長",
            dividendYield: "股息殖利率",
            beta: "Beta",
            freeCashFlow: "自由現金流",
            cashAndEquivalents: "現金及約當現金",
            totalDebt: "總債務",
          },
        },
        aiCard: {
          evidenceSummary: "引用證據摘要（{{shown}} / {{total}}）",
          daysSuffix: { one: "天", other: "天" },
          recentArticlesSuffix: { one: "篇（最近期）", other: "篇（最近期）" },
          sourcesSeparator: { one: "源 ·", other: "源 ·" },
          citationsSuffix: { one: "引用）", other: "引用）" },
          itemCount: { one: "[{{count}} 項]", other: "[{{count}} 項]" },
        },
      },
      en: {
        tickerDetail: {
          statementSummary: {
            one: "{{title}} ({{count}} period)",
            other: "{{title}} ({{count}} periods)",
          },
          retry: "Retry",
          sourceStoredSec: "Stored SEC fundamentals",
          kvLabels: {
            latestClose: "Latest close",
            changePercent: "Change %",
            periodHigh: "Period high",
            periodLow: "Period low",
            rangePercent: "Range %",
            volume: "Volume",
            bars: "Bars",
            dates: "Dates",
            snapshotDate: "Snapshot date",
            marketCap: "Market cap",
            pe: "P/E",
            forwardPe: "Forward P/E",
            ps: "P/S",
            pb: "P/B",
            roe: "ROE",
            roa: "ROA",
            debtToEquity: "D/E",
            currentRatio: "Current ratio",
            grossMargin: "Gross margin",
            operatingMargin: "Operating margin",
            netMargin: "Net margin",
            revenueGrowth: "Revenue growth",
            earningsGrowth: "Earnings growth",
            dividendYield: "Dividend yield",
            beta: "Beta",
            freeCashFlow: "Free cash flow",
            cashAndEquivalents: "Cash & equiv.",
            totalDebt: "Total debt",
          },
        },
        aiCard: {
          evidenceSummary: "Evidence citation summary ({{shown}} / {{total}})",
          daysSuffix: { one: "day", other: "days" },
          recentArticlesSuffix: {
            one: "article (most recent)",
            other: "articles (most recent)",
          },
          sourcesSeparator: { one: "source ·", other: "sources ·" },
          citationsSuffix: { one: "citation)", other: "citations)" },
          itemCount: { one: "[{{count}} item]", other: "[{{count}} items]" },
        },
      },
    } as const;

    expect(resourceNamespaces).toContain("explore");
    for (const locale of ["zh-Hant", "en"] as const) {
      const explore = (resources[locale] as Record<string, unknown>).explore;
      expect.soft(explore, `${locale}.explore`).toBeDefined();
      if (!explore || typeof explore !== "object" || Array.isArray(explore)) continue;
      const flattened = flattenResource(explore as ResourceTree);
      expect(flattened.size, `${locale}.explore`).toBe(797);
      for (const path of [
        "errors.operations.watchlistDeleteList",
        "watchlist.emptyListWithArchivedHint",
        "watchlist.emptyListWithoutArchivedHint",
        "watchlist.emptyActiveListWithArchivedHint",
        "watchlist.emptyActiveListWithoutArchivedHint",
        "watchlist.consensusRatingsSummary",
        "watchlist.renderedTickerCount.one",
        "watchlist.renderedTickerCount.other",
        "watchlist.customListCount.one",
        "watchlist.customListCount.other",
        "watchlist.noteCount.one",
        "watchlist.noteCount.other",
        "watchlist.consensusAnalystSummary.one",
        "watchlist.consensusAnalystSummary.other",
        "universe.allListsCount",
        "universe.noteCount.one",
        "universe.noteCount.other",
        "universe.summaryCounts.one",
        "universe.summaryCounts.other",
        "universe.importSummarySeparator",
        "lifecycle.sections.auditDetails",
        "lifecycle.sections.manualSupplement",
        "lifecycle.states.llmDerived",
        "lifecycle.translation.viewMode",
        "news.marketSearchSummary",
        "news.seekingAlphaSearchSummary",
        "news.loadMoreProgress",
        "news.modeLabel",
        "news.marketProviderLabel",
        "news.dayWindowLabel",
        "tickerDetail.statementSummary.one",
        "tickerDetail.statementSummary.other",
        "tickerDetail.retry",
        "tickerDetail.sourceStoredSec",
        "aiCard.evidenceSummary",
        "aiCard.daysSuffix.one",
        "aiCard.daysSuffix.other",
        "aiCard.recentArticlesSuffix.one",
        "aiCard.recentArticlesSuffix.other",
        "aiCard.sourcesSeparator.one",
        "aiCard.sourcesSeparator.other",
        "aiCard.citationsSuffix.one",
        "aiCard.citationsSuffix.other",
        "aiCard.itemCount.one",
        "aiCard.itemCount.other",
      ]) {
        expect.soft(flattened.has(path), `${locale}.explore.${path}`).toBe(true);
      }
      for (const path of [
        "errors.operations.tickerLoadIv",
        "errors.operations.tickerLoadIvHistory",
        "tickerDetail.ivSignalSuffix",
        "tickerDetail.atmIv",
        "tickerDetail.hv30",
        "tickerDetail.ivHistorySummary.one",
        "tickerDetail.ivHistorySummary.other",
        "tickerDetail.quotes",
        "tickerDetail.spot",
        "tickerDetail.vrp",
        "tickerDetail.noIv",
        "tickerDetail.impliedVolatility",
        "tickerDetail.ivLocalCoverage",
        "tickerDetail.ivCurrentSource",
        "tickerDetail.ivHistory",
        "tickerDetail.kvLabels.currentAtmIv",
        "tickerDetail.kvLabels.hv30d",
        "tickerDetail.kvLabels.vrp",
        "tickerDetail.kvLabels.ivRank",
        "tickerDetail.kvLabels.ivPercentile",
        "tickerDetail.kvLabels.spot",
        "tickerDetail.kvLabels.historyDays",
        "watchlist.emptyList",
        "watchlist.maybeTryArchived",
        "watchlist.tryArchived",
        "watchlist.emptyActiveList",
        "watchlist.consensusBuySummary",
        "watchlist.consensusSellSummary",
        "watchlist.filesSuffix",
        "watchlist.customListCount",
        "watchlist.noteCount",
        "watchlist.consensusAnalystSummary",
        "universe.allListsPrefix",
        "universe.filesSeparator",
        "universe.noteCount",
        "universe.summaryCounts",
        "universe.withSummary",
        "news.searchPrefix",
        "news.searchSuffix",
        "news.loadMore",
        "news.openTickerChip",
        "news.analysisArticleRuntime",
        "news.marketNewsRuntime",
        "tickerDetail.ivHistoryPrefix",
        "tickerDetail.rowsSource",
        "tickerDetail.periodsSuffix",
        "aiCard.evidenceSummaryPrefix",
      ]) {
        expect.soft(flattened.has(path), `${locale}.explore.${path}`).toBe(false);
      }
      expect.soft(explore, `${locale}.explore count copy`).toMatchObject(expectedCountCopy[locale]);
      expect.soft((explore as ResourceTree).news, `${locale}.explore news copy`)
        .toMatchObject(expectedNewsCopy[locale]);
      expect.soft(explore, `${locale}.explore Task 7 copy`)
        .toMatchObject(expectedTask7Copy[locale]);
      for (const [subtree, count] of Object.entries(expectedSubtreeCounts)) {
        expect(
          flattenResource((explore as ResourceTree)[subtree] as ResourceTree).size,
          `${locale}.explore.${subtree}`,
        ).toBe(count);
      }
    }
  });

  it("keeps Explore resources statically bundled and free of source values", () => {
    const root = resolve(import.meta.dirname, "resources");
    const resourceSource = readFileSync(resolve(import.meta.dirname, "resources.ts"), "utf8");
    const paths = [
      resolve(root, "zh-Hant/explore.ts"),
      resolve(root, "en/explore.ts"),
    ];

    expect(resourceSource).not.toMatch(/import\s*\(|fetch\s*\(/);
    for (const path of paths) {
      expect.soft(existsSync(path), path).toBe(true);
      if (!existsSync(path)) continue;
      const source = readFileSync(path, "utf8");
      expect(source).not.toMatch(/NVDA|gpt-[\w.-]+|sk-(?:ant-)?[\w-]+|https?:\/\//i);
      expect(source).not.toMatch(/\[[^\]]+\]\s*:/);
      expect(source).not.toMatch(/import\s*\(|fetch\s*\(/);
    }
  });

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
        localeLabel: "介面語言",
        localeSelfName: "繁體中文",
        action: "儲存",
        workspace: "設定",
        section: "資料來源與排程",
        task: "AI 研究",
        provider: "IBKR Gateway",
        schedule: "IBKR 股價",
        coverage: "交易日 / 價格覆蓋",
        coverageDescription: "以正規交易時段的預期 15 分鐘格線比對本地觀測；沒有獨立證據時，未觀測到的格子只標為未知。",
        coverageReadOnly: "唯讀診斷；不會啟動修復，也不會產生 planner 工作。",
        coverageMarketScope: "美國上市股票代理範圍",
        coverageSession: "正規交易時段（RTH）",
        storedFundamentals: "已儲存的 SEC 基本面",
        financialCache: "財務快取",
        news: "新聞資料",
        macro: "總經資料",
        investor: "風險意願高於承受能力",
        investorRiskCapacity: "風險承受能力(1-10)",
        investorAvoidances: "想避開的(逗號分隔)",
        investorFlags: "行為傾向(供助手校準,非診斷)",
        investorNotes: "自由描述(目標、自我觀察、想被怎麼協助)",
        investorDraftSuccess: "草稿已產生(未儲存)",
        investorUpdating: "正在更新投資人設定",
        investorUnset: "未設定",
        investorRiskComparison: "風險意願與風險承受能力:",
        investorSkillMode: "技能模式:off(技能建議屬後續階段,尚未啟用)",
        calibrationStarted: "校準對話已開始",
        calibrationUpdated: "校準回覆已更新",
        proposalPending: "待核准校準提案",
        proposalApply: "套用校準提案",
        investorSaveAction: "儲存設定",
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
        localeLabel: "Interface language",
        localeSelfName: "English",
        action: "Save",
        workspace: "Settings",
        section: "Data Sources and Schedules",
        task: "AI Research",
        provider: "IBKR Gateway",
        schedule: "IBKR Prices",
        coverage: "Trading-day / Price Coverage",
        coverageDescription: "Compares local observations with the expected 15-minute RTH grid; absent observations remain unknown without independent evidence.",
        coverageReadOnly: "Read-only diagnostic; does not start a repair or supply planner work.",
        coverageMarketScope: "US-listed equity proxy",
        coverageSession: "Regular trading hours (RTH)",
        storedFundamentals: "Stored SEC Fundamentals",
        financialCache: "Financial Cache",
        news: "News Data",
        macro: "Macro Data",
        investor: "Risk appetite above capacity",
        investorRiskCapacity: "Risk capacity (1-10)",
        investorAvoidances: "Avoidances (comma-separated)",
        investorFlags: "Behavioral tendencies (for calibration, not diagnosis)",
        investorNotes: "Free-form notes (goals, observations, and preferred assistance)",
        investorDraftSuccess: "Draft generated (not saved)",
        investorUpdating: "Updating Investor Profile",
        investorUnset: "Not set",
        investorRiskComparison: "Risk appetite and risk capacity:",
        investorSkillMode: "Skill mode: off (skill recommendations are a later phase and are not yet enabled)",
        calibrationStarted: "Calibration conversation started",
        calibrationUpdated: "Calibration response updated",
        proposalPending: "Calibration proposal awaiting approval",
        proposalApply: "Apply calibration proposal",
        investorSaveAction: "Save settings",
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
      const commonT = instance.getFixedT(expected.locale, "common");
      expect(t(($) => $.locale.label)).toBe(expected.localeLabel);
      expect(t(($) => $.locale.selfName)).toBe(expected.localeSelfName);
      expect(t(($) => $.actions.save)).toBe(expected.action);
      expect(t(($) => $.workspace.title)).toBe(expected.workspace);
      expect(t(($) => $.registry.sections.dataSources.title)).toBe(expected.section);
      expect(t(($) => $.models.tasks.aiResearch.label)).toBe(expected.task);
      expect(t(($) => $.dataSources.providers.names.ibkr)).toBe(expected.provider);
      expect(t(($) => $.dataSources.schedule.sources.ibkrPrices.label)).toBe(expected.schedule);
      expect(t(($) => $.dataStorage.coverage.title)).toBe(expected.coverage);
      expect(t(($) => $.dataStorage.coverage.description)).toBe(expected.coverageDescription);
      expect(t(($) => $.dataStorage.coverage.readOnly)).toBe(expected.coverageReadOnly);
      expect(t(($) => $.dataStorage.coverage.facts.marketScopeValue))
        .toBe(expected.coverageMarketScope);
      expect(t(($) => $.dataStorage.coverage.facts.sessionValue)).toBe(expected.coverageSession);
      expect(t(($) => $.dataStorage.labels.fundamentals)).toBe(expected.storedFundamentals);
      expect(t(($) => $.dataStorage.labels.financialCache)).toBe(expected.financialCache);
      expect(t(($) => $.newsStorage.title)).toBe(expected.news);
      expect(t(($) => $.macroStorage.title)).toBe(expected.macro);
      expect.soft(commonT(($) => $.personalization.mismatch.appetiteAboveCapacity))
        .toBe(expected.investor);
      const investor = resources[expected.locale].settings.investor;
      expect.soft((investor as Record<string, unknown>).stances).toBeUndefined();
      expect.soft((investor as Record<string, unknown>).mismatch).toBeUndefined();
      expect.soft(investor.fields.riskCapacity).toBe(expected.investorRiskCapacity);
      expect.soft(investor.fields.avoidances).toBe(expected.investorAvoidances);
      expect.soft(investor.fields.flags).toBe(expected.investorFlags);
      expect.soft(investor.fields.notes).toBe(expected.investorNotes);
      expect.soft(investor.draft.success).toBe(expected.investorDraftSuccess);
      expect(t(($) => $.investor.panel.updating)).toBe(expected.investorUpdating);
      expect(t(($) => $.investor.fields.unset)).toBe(expected.investorUnset);
      expect(t(($) => $.investor.fields.riskComparison)).toBe(expected.investorRiskComparison);
      expect(t(($) => $.investor.fields.skillMode)).toBe(expected.investorSkillMode);
      expect(t(($) => $.investor.calibration.started)).toBe(expected.calibrationStarted);
      expect(t(($) => $.investor.calibration.updated)).toBe(expected.calibrationUpdated);
      expect(t(($) => $.investor.proposal.pending)).toBe(expected.proposalPending);
      expect(t(($) => $.investor.proposal.apply)).toBe(expected.proposalApply);
      expect(t(($) => $.investor.saveAction)).toBe(expected.investorSaveAction);
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

  it("resolves the Slice 5 Investor workspace copy in both locales", () => {
    const cases = [
      {
        locale: "zh-Hant" as const,
        summary: "投資人設定摘要",
        calibration: "引導式校準",
        topic: "遇到虧損時怎麼做",
        prompt: "假設一個重要持股在短期內下跌 18%，但長期 thesis 尚未明確失效，你通常會怎麼處理？",
        effect: "優先檢視下行風險、部位大小與風控紀律。",
        researchTitle: "本次執行的個人化情境",
        researchNotice: "這是本次研究實際使用的歷史快照，不是目前的投資人設定。",
      },
      {
        locale: "en" as const,
        summary: "Investor Profile summary",
        calibration: "Guided calibration",
        topic: "How you respond to losses",
        prompt: "Suppose an important holding falls 18% over a short period while its long-term thesis is not clearly broken. What would you usually do?",
        effect: "Prioritizes downside, position sizing, and risk limit discipline.",
        researchTitle: "Personalization context for this run",
        researchNotice: "This is the historical snapshot used by this Research run, not your current Investor Profile.",
      },
    ];

    for (const expected of cases) {
      const instance = createInstance();
      initializeI18n(instance, expected.locale);
      const settingsT = instance.getFixedT(expected.locale, "settings");
      const researchT = instance.getFixedT(expected.locale, "research");
      expect(settingsT(($) => $.investor.workspace.summary.title)).toBe(expected.summary);
      expect(settingsT(($) => $.investor.workspace.calibration.title)).toBe(expected.calibration);
      expect(settingsT(($) => $.investor.workspace.topics.lossResponse.label)).toBe(expected.topic);
      expect(settingsT(($) => $.investor.workspace.prompts.lossResponseOpeningV1)).toBe(expected.prompt);
      expect(settingsT(($) => $.investor.workspace.effects.strictRiskControl)).toBe(expected.effect);
      expect(researchT(($) => $.personalization.title)).toBe(expected.researchTitle);
      expect(researchT(($) => $.personalization.runNotice)).toBe(expected.researchNotice);
    }
  });

  it("contains the reviewed remaining-surface namespace inventory in both locales", () => {
    const portfolioResourceOwnership = JSON.parse(readFileSync(resolve(
      import.meta.dirname,
      "../../scripts/i18n/fixtures/portfolio-resource-ownership.json",
    ), "utf8")) as PortfolioOwnershipContract;
    const expectedCounts = {
      common: 61,
      shell: 37,
      settings: 800,
      research: 207,
      explore: 797,
      portfolio: 374,
      system: 24,
    } as const;

    const expectedCoveragePaths = [
      "title",
      "description",
      "readOnly",
      "generatedAt",
      "lookback",
      "lookbackLabel",
      "facts.universe",
      "facts.interval",
      "facts.marketScope",
      "facts.marketScopeValue",
      "facts.session",
      "facts.sessionValue",
      "facts.reviewedThrough",
      "facts.horizonMonths",
      "headings.date",
      "headings.status",
      "headings.expectedSlots",
      "headings.complete",
      "headings.partial",
      "headings.unknown",
      "status.weekend",
      "status.marketClosed",
      "status.inProgress",
      "status.complete",
      "status.partial",
      "status.indeterminateTickers",
      "status.unknown",
      "status.unavailable",
      "reasons.calendarUnavailable",
      "reasons.dateUnreviewed",
      "reasons.observationUnavailable",
      "reasons.noObservations",
      "health.fixtureHorizonLow",
      "health.dateUnreviewed",
      "health.calendarUnavailable",
      "health.marketDbMissing",
      "health.marketDbUnreadable",
      "health.pricesSchemaMissing",
      "drilldown.partialTitle",
      "drilldown.partialDetail",
      "drilldown.unknownTitle",
      "drilldown.unknownDetail",
      "drilldown.unmatched",
      "drilldown.providerIssues",
      "drilldown.securityDefinition",
      "drilldown.priceUnresolvedReview",
      "drilldown.sessionWindow",
    ].map((path) => `dataStorage.coverage.${path}`).sort();

    expect(resourceNamespaces).toEqual(Object.keys(expectedCounts));
    const flattenedPortfolioByLocale = new Map<string, Map<string, string>>();
    for (const locale of ["zh-Hant", "en"] as const) {
      const localeResources = resources[locale] as Record<string, unknown>;
      let total = 0;
      for (const [namespace, count] of Object.entries(expectedCounts)) {
        const resource = localeResources[namespace];
        expect.soft(resource, `${locale}.${namespace}`).toBeDefined();
        if (resource && typeof resource === "object" && !Array.isArray(resource)) {
          const actual = flattenResource(resource as ResourceTree).size;
          expect.soft(actual, `${locale}.${namespace}`).toBe(count);
          total += actual;
        }
      }
      expect(total, `${locale}.total`).toBe(2300);

      const settings = flattenResource(localeResources.settings as ResourceTree);
      expect(
        [...settings.keys()].filter((path) => /dataSources\.schedule\.(?:labels\.(?:readOnly|retired)|sources\.(?:ivHistory|localIncremental|priceBackfill))/u.test(path)),
        `${locale}.settings.retiredScheduleCopy`,
      ).toEqual([]);
      expect(settings.has("dataStorage.labels.iv"), `${locale}.settings.dataStorage.labels.iv`)
        .toBe(false);
      expect(settings.has("dataStorage.summary.iv"), `${locale}.settings.dataStorage.summary.iv`)
        .toBe(false);
      expect(
        [...settings.keys()]
          .filter((path) => path.startsWith("dataStorage.coverage."))
          .sort(),
        `${locale}.settings.dataStorage.coverage`,
      ).toEqual(expectedCoveragePaths);

      const portfolio = flattenResource(localeResources.portfolio as ResourceTree);
      flattenedPortfolioByLocale.set(locale, portfolio);
      const expectedPortfolioFamilies = {
        holdings: 69,
        activity: 142,
        capture: 68,
        accountOverview: 36,
        recentActivity: 37,
        tableLabels: 22,
      } as const;
      for (const [family, expected] of Object.entries(expectedPortfolioFamilies)) {
        expect(
          [...portfolio.keys()].filter((key) => key.startsWith(`${family}.`)),
          `${locale}.portfolio.${family}`,
        ).toHaveLength(expected);
      }
      expect([...portfolio.keys()].filter((key) => /(?:^|\.)(?:inventory|copy[0-9]+)(?:\.|$)/u.test(key)))
        .toEqual([]);
    }

    const portfolioSourceFiles = new Map([
      ["src/Holdings.tsx", "holdings"],
      ["src/PortfolioActivity.tsx", "activity"],
      ["src/PortfolioCapturePanel.tsx", "capture"],
      ["src/PortfolioAccountOverview.tsx", "accountOverview"],
      ["src/PortfolioRecentActivity.tsx", "recentActivity"],
    ]);
    const debt = JSON.parse(readFileSync(resolve(
      import.meta.dirname,
      "../../scripts/i18n/visible-literal-debt.json",
    ), "utf8")) as { signatures: Array<{ signature: string; count: number }> };
    expect(portfolioResourceOwnership.version).toBe(2);
    const ownershipSignatures = portfolioResourceOwnership.sourceClaims.map(({ signature }) => signature);
    expect(new Set(ownershipSignatures).size).toBe(portfolioResourceOwnership.sourceClaims.length);
    expect(debt.signatures).toEqual([]);
    expect(portfolioResourceOwnership.sourceClaims).toHaveLength(372);
    expect(portfolioResourceOwnership.sourceClaims.reduce((sum, entry) => sum + entry.count, 0))
      .toBe(391);
    expect(new Set(portfolioResourceOwnership.sourceClaims.map(({ signature }) => (
      (JSON.parse(signature) as [string, string, string])[0]
    )))).toEqual(new Set(portfolioSourceFiles.keys()));

    const reviewedExclusions = new Map([
      ['["src/Holdings.tsx","jsx_attribute","NVDA"]', "holdings-calibration-example"],
      ['["src/PortfolioActivity.tsx","presenter_return","broker_day_gap"]', "broker-day-gap-machine-operand"],
      ['["src/PortfolioRecentActivity.tsx","presenter_return","broker_day_gap"]', "broker-day-gap-machine-operand"],
    ]);
    expect(portfolioResourceOwnership.sourceClaims.filter((entry) => entry.claimType === "excluded")
      .map((entry) => [entry.signature, entry.reason]))
      .toEqual([...reviewedExclusions]);

    const expectedDirectUiClaims = [[
      "holdings.page_header.eyebrow",
      "holdings.surface.eyebrow",
      "src/Holdings.tsx",
      "$.holdings.surface.eyebrow",
    ]];
    const directUiClaims = portfolioResourceOwnership.directUiClaims ?? [];
    expect(directUiClaims.map(({ claimType, id, path, sourceFile, selector }) => [
      claimType,
      id,
      path,
      sourceFile,
      selector,
    ])).toEqual(expectedDirectUiClaims.map(([id, path, sourceFile, selector]) => [
      "direct_ui",
      id,
      path,
      sourceFile,
      selector,
    ]));
    for (const claim of directUiClaims) {
      expect(claim.path.startsWith("holdings.")).toBe(true);
      for (const [locale, portfolio] of flattenedPortfolioByLocale) {
        expect(portfolio.has(claim.path), `${locale}.portfolio.${claim.path}`).toBe(true);
      }
      const consumer = readFileSync(resolve(import.meta.dirname, "../..", claim.sourceFile), "utf8");
      expect(consumer, `${claim.sourceFile} -> ${claim.selector}`).toContain(claim.selector);
    }

    const expectedPresenterClaims = [
      ["operation.holding_create", "holdings.operations.holdingCreate"],
      ["operation.holding_update", "holdings.operations.holdingUpdate"],
      ["operation.holding_close", "holdings.operations.holdingClose"],
      ["operation.overview_load", "accountOverview.operations.overviewLoad"],
      ["operation.overview_toggle_aggregate", "accountOverview.operations.overviewToggleAggregate"],
      ["activity.field.quantity", "activity.fields.quantity"],
      ["activity.field.avg_cost", "activity.fields.avgCost"],
      ["activity.field.currency", "activity.fields.currency"],
      ["activity.field.notes", "activity.fields.notes"],
      ["activity.field.thesis", "activity.fields.thesis"],
      ["activity.field.tags", "activity.fields.tags"],
      ["activity.field.market_value", "activity.fields.marketValue"],
      ["activity.field.unrealized_pnl", "activity.fields.unrealizedPnl"],
      ["activity.unknown.stable_id", "activity.unknown.stableId"],
      ["activity.unknown.field", "activity.unknown.field"],
      ["activity.position_context.complete", "activity.surface.positionContextComplete"],
      ["activity.gross_notional_kind.deterministic_arithmetic", "activity.surface.grossNotionalKind"],
      ["developer.code", "capture.diagnostics.code"],
      ["developer.route", "capture.diagnostics.route"],
    ];
    expect(portfolioResourceOwnership.presenterClaims
      .map(({ claimType, id, path }) => [claimType, id, path]))
      .toEqual(expectedPresenterClaims.map(([id, path]) => ["presenter", id, path]));
    const expectedReferenceClaims = [[
      "developer.status",
      "capture.surface.runsStateHeader",
      '["src/PortfolioCapturePanel.tsx","runtime_cjk","狀態"]',
    ]];
    expect(portfolioResourceOwnership.referenceClaims
      .map(({ claimType, id, path, sourceSignature }) => [claimType, id, path, sourceSignature]))
      .toEqual(expectedReferenceClaims.map(([id, path, sourceSignature]) => [
        "presenter_reference",
        id,
        path,
        sourceSignature,
      ]));

    const sourcePathClaims = new Map<string, PortfolioSourceClaim[]>();
    for (const entry of portfolioResourceOwnership.sourceClaims) {
      const [sourceFile, kind, sourceCopy] = JSON.parse(entry.signature) as [string, string, string];
      const isTableLabel = (sourceFile === "src/Holdings.tsx" && kind === "object_property"
          && ["Account", "Symbol", "Asset", "Qty", "Currency", "Avg Cost", "Market Value", "Notes", "Status"].includes(sourceCopy))
        || (sourceFile === "src/PortfolioCapturePanel.tsx" && kind === "object_property"
          && ["Avg Cost", "Market Value", "Unrealized P&L"].includes(sourceCopy))
        || (sourceFile === "src/PortfolioAccountOverview.tsx"
          && ((kind === "object_property" && ["Capture Run", "Base Currency"].includes(sourceCopy))
            || kind === "tuple_column_label"));
      const expectedFamily = isTableLabel ? "tableLabels" : portfolioSourceFiles.get(sourceFile);
      if (entry.claimType === "excluded") {
        expect(reviewedExclusions.has(entry.signature), entry.signature).toBe(true);
        expect(entry.path).toBeUndefined();
        expect(entry.paths).toBeUndefined();
        continue;
      }
      const paths = entry.paths ?? (entry.path ? [entry.path] : []);
      expect(paths.length, entry.signature).toBeGreaterThan(0);
      if (entry.claimType === "plural_exact") expect(paths).toHaveLength(2);
      if (entry.claimType === "compound_plural") {
        expect(entry.signature).toBe('["src/PortfolioRecentActivity.tsx","runtime_cjk","${manualActionLabel(item.action)} · ${item.changes.length} 項欄位"]');
        expect(paths).toEqual([
          "recentActivity.surface.manualFact",
          "recentActivity.fieldCount.one",
          "recentActivity.fieldCount.other",
        ]);
      }
      if (!["plural_exact", "compound_plural"].includes(entry.claimType)) expect(paths).toHaveLength(1);
      const normalizedSource = normalizePortfolioCopy(sourceCopy);
      for (const path of paths) {
        expect(path.startsWith(`${expectedFamily}.`), `${entry.signature} -> ${path}`).toBe(true);
        for (const [locale, portfolio] of flattenedPortfolioByLocale) {
          expect(portfolio.has(path), `${locale}.portfolio.${path}`).toBe(true);
        }
        const normalizedResource = normalizePortfolioCopy(flattenedPortfolioByLocale.get("zh-Hant")!.get(path)!);
        if (["exact", "shared_exact", "plural_exact"].includes(entry.claimType)) {
          expect(normalizedResource, `${entry.signature} -> ${path}`).toBe(normalizedSource);
        } else if (entry.claimType === "template_prefix") {
          expect(normalizedResource.startsWith(normalizedSource), `${entry.signature} -> ${path}`).toBe(true);
        } else if (entry.claimType === "template_suffix") {
          expect(normalizedResource.endsWith(normalizedSource), `${entry.signature} -> ${path}`).toBe(true);
        } else {
          expect(path === paths[0] ? normalizedResource === normalizedSource : normalizedSource.endsWith(normalizedResource), `${entry.signature} -> ${path}`).toBe(true);
        }
        const claims = sourcePathClaims.get(path) ?? [];
        claims.push(entry);
        sourcePathClaims.set(path, claims);
      }
    }
    for (const [path, pathClaims] of sourcePathClaims) {
      const exactClaims = pathClaims.filter(({ claimType }) => claimType === "shared_exact");
      if (exactClaims.length === 0) continue;
      expect(exactClaims).toHaveLength(pathClaims.length);
      expect(new Set(exactClaims.map(({ sharedContext }) => sharedContext))).toEqual(new Set([path]));
    }

    for (const reference of portfolioResourceOwnership.referenceClaims) {
      expect(sourcePathClaims.get(reference.path)?.map(({ signature }) => signature))
        .toContain(reference.sourceSignature);
      for (const [locale, portfolio] of flattenedPortfolioByLocale) {
        expect(portfolio.has(reference.path), `${locale}.portfolio.${reference.path}`).toBe(true);
      }
    }

    const presenterPaths = new Set(portfolioResourceOwnership.presenterClaims.map(({ path }) => path));
    expect(new Set(presenterPaths).size).toBe(expectedPresenterClaims.length);
    expect([...presenterPaths].filter((path) => sourcePathClaims.has(path))).toEqual([]);
    const directUiPaths = new Set(directUiClaims.map(({ path }) => path));
    expect(new Set(directUiPaths).size).toBe(expectedDirectUiClaims.length);
    expect([...directUiPaths].filter((path) => sourcePathClaims.has(path) || presenterPaths.has(path))).toEqual([]);
    const allPortfolioPaths = [...flattenedPortfolioByLocale.get("zh-Hant")!.keys()].sort();
    const claimedPaths = new Set([...sourcePathClaims.keys(), ...presenterPaths, ...directUiPaths]);
    expect(allPortfolioPaths.filter((path) => !claimedPaths.has(path))).toEqual([]);
    expect([...claimedPaths].sort()).toEqual(allPortfolioPaths);
    expect(claimedPaths.size).toBe(374);

    const familyClaimCounts = Object.fromEntries(["holdings", "activity", "capture", "accountOverview", "recentActivity", "tableLabels"]
      .map((family) => [family, [...claimedPaths].filter((path) => path.startsWith(`${family}.`)).length]));
    expect(familyClaimCounts).toEqual({
      holdings: 69,
      activity: 142,
      capture: 68,
      accountOverview: 36,
      recentActivity: 37,
      tableLabels: 22,
    });
    expect(resources["zh-Hant"].portfolio.holdings.validation.tickerQuantityRequired)
      .toBe("Ticker and non-zero quantity are required");
  });

  it("moves shared model chrome to one Common owner without Settings duplicates", () => {
    const expectedModels = {
      "zh-Hant": {
        groups: {
          available: "可供此任務使用",
          visibleDisabled: "此登入可見",
          advanced: "進階／未驗證",
          current: "目前路由",
        },
        reasons: {
          missingActiveCredential: "尚未設定此 provider 的登入",
          taskAuthModeUnsupported: "此登入方式不支援這個任務",
          taskTestUnsupported: "此登入方式尚不支援實際測試",
          taskCapabilityMissing: "缺少任務能力",
          modelNotVisible: "此登入的探索清單未顯示此模型",
          modelNotInRegistry: "自訂／未知模型，尚未驗證能力",
          discoveryUnavailable: "暫時無法讀取模型探索狀態",
          providerCallFailed: "provider 實際呼叫失敗",
          reauthRequired: "登入已失效，請重新登入",
        },
        authModes: {
          apiKey: "API key",
          apiKeyPool: "API key pool",
          chatgptOauth: "ChatGPT 訂閱登入",
          claudeCodeOauth: "Claude 訂閱登入",
        },
        thinkingModes: {
          none: "無特殊 thinking 行為",
          manualBudget: "使用手動 thinking budget",
          adaptiveOptIn: "可選擇 adaptive thinking",
          adaptiveDefaultOn: "預設開啟 adaptive thinking",
          adaptiveAlwaysOn: "固定開啟 adaptive thinking",
        },
        compatibility: {
          decoratedSuffix: "未驗證（舊 sidecar 相容模式）",
          settingsNotice: "未驗證（舊 sidecar 相容模式）。",
        },
      },
      en: {
        groups: {
          available: "Available for this task",
          visibleDisabled: "Visible to this sign-in",
          advanced: "Advanced / unverified",
          current: "Current route",
        },
        reasons: {
          missingActiveCredential: "No sign-in is configured for this provider",
          taskAuthModeUnsupported: "This sign-in method does not support the task",
          taskTestUnsupported: "This sign-in method does not yet support live testing",
          taskCapabilityMissing: "Task capability is missing",
          modelNotVisible: "This model does not appear in the discovery list for this sign-in",
          modelNotInRegistry: "Custom or unknown model; capabilities are unverified",
          discoveryUnavailable: "Model discovery status is temporarily unavailable",
          providerCallFailed: "The live provider call failed",
          reauthRequired: "The sign-in has expired. Sign in again",
        },
        authModes: {
          apiKey: "API key",
          apiKeyPool: "API key pool",
          chatgptOauth: "ChatGPT subscription sign-in",
          claudeCodeOauth: "Claude subscription sign-in",
        },
        thinkingModes: {
          none: "No special thinking behavior",
          manualBudget: "Uses a manual thinking budget",
          adaptiveOptIn: "Adaptive thinking available",
          adaptiveDefaultOn: "Adaptive thinking on by default",
          adaptiveAlwaysOn: "Adaptive thinking always on",
        },
        compatibility: {
          decoratedSuffix: "Unverified (legacy sidecar compatibility mode)",
          settingsNotice: "Unverified (legacy sidecar compatibility mode).",
        },
      },
    } as const;
    const removedSettingsPaths = [
      "models.catalog.unavailable",
      "models.credentials.missing",
      "models.credentials.apiKey",
      "models.credentials.apiKeyPool",
      "models.credentials.chatgptOAuth",
      "models.credentials.claudeCodeOAuth",
      "models.compatibility.legacyMode",
      "models.compatibility.missingCapability",
      "models.compatibility.unsupported",
      "models.compatibility.modelNotVisible",
      "models.groups.available",
      "models.groups.visibleDisabled",
      "models.groups.advanced",
      "models.groups.current",
      "models.custom.unknown",
      "models.thinking.none",
      "models.thinking.manualBudget",
      "models.thinking.adaptiveOptIn",
      "models.thinking.adaptiveDefaultOn",
      "models.thinking.adaptiveAlwaysOn",
      "models.test.failed",
      "models.test.unsupported",
      "providers.openAI.tokenExpired",
    ] as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      const commonModels = (resources[locale].common as ResourceTree).models as ResourceTree;
      expect(commonModels, `${locale}.common.models`).toEqual(expectedModels[locale]);
      expect(flattenResource(commonModels).size, `${locale}.common.models`).toBe(24);
      const settings = flattenResource(resources[locale].settings as ResourceTree);
      for (const path of removedSettingsPaths) {
        expect.soft(settings.has(path), `${locale}.settings.${path}`).toBe(false);
      }
    }
  });

  it("preserves the reviewed pre-Slice-5 Settings-origin inventory across the Common move", () => {
    const postSliceSettingsPaths = [
      "workspace.routes.effortRequired",
      "workspace.routes.modelRetired",
      "models.route.effortRequired",
      "models.route.modelRetired",
      "models.catalog.selectEffort",
      "models.metrics.officialPricing",
      "actions.refreshStatus",
      "dataStorage.coverage.generatedAt",
      "dataStorage.coverage.drilldown.securityDefinition",
      "dataStorage.coverage.drilldown.priceUnresolvedReview",
      "dataSources.schedule.history.gatewayUnavailable",
      "dataSources.schedule.history.priceUnresolved_one",
      "dataSources.schedule.history.priceUnresolved_other",
      "dataSources.schedule.history.newsCoverageIncomplete_one",
      "dataSources.schedule.history.newsCoverageIncomplete_other",
      "providers.accountUsage.syncFailedNoSnapshot",
      "providers.accountUsage.syncTransportFailed",
      "providers.accountUsage.cachedReadFailedStale",
      "providers.accountUsage.cachedReadFailedNone",
      "providers.accountUsage.retryLocalRead",
      "providers.accountUsage.syncClaudeCost",
      "providers.accountUsage.fiveHourWindow",
      "providers.accountUsage.sevenDayWindow",
      "dataSources.extension.degraded",
      "dataSources.extension.workloads.alphaPicks",
      "dataSources.extension.workloads.marketNews",
      "dataSources.extension.status.captureDegraded",
      "dataSources.extension.status.legacyCauseAbsent",
      "dataSources.extension.status.diagnosticsRejected",
      "dataSources.extension.status.additionalDiagnostics",
      "dataSources.extension.status.captureCounts",
      "dataSources.extension.stages.tabNavigation",
      "dataSources.extension.stages.pageReadiness",
      "dataSources.extension.stages.scriptInjection",
      "dataSources.extension.stages.contentParse",
      "dataSources.extension.stages.nativeTransport",
      "dataSources.extension.stages.localPersistence",
      "dataSources.extension.stages.reconciliation",
      "dataSources.extension.stages.extensionRuntime",
      "dataSources.extension.reasons.accessRestricted",
      "dataSources.extension.reasons.loginRequired",
      "dataSources.extension.reasons.modalBlocked",
      "dataSources.extension.reasons.navigationTimeout",
      "dataSources.extension.reasons.detailTimeout",
      "dataSources.extension.reasons.domNotReady",
      "dataSources.extension.reasons.parserEmpty",
      "dataSources.extension.reasons.nativeHostUnavailable",
      "dataSources.extension.reasons.extensionDependencyMissing",
      "dataSources.extension.reasons.reconciliationFailed",
      "dataSources.extension.reasons.commentScanFailed",
      "dataSources.extension.reasons.unknownFailure",
      "dataSources.extension.reasons.tabClosed",
      "dataSources.extension.reasons.browserApiFailed",
      "dataSources.extension.reasons.scriptInjectionFailed",
      "dataSources.extension.reasons.nativeResponseInvalid",
      "dataSources.extension.reasons.databaseBusy",
      "dataSources.extension.reasons.databaseIntegrityFailed",
      "dataSources.extension.reasons.databaseWriteFailed",
      "dataSources.extension.developer.jobName",
      "dataSources.extension.developer.stage",
      "dataSources.extension.developer.reason",
      "dataSources.extension.developer.target",
      "dataSources.extension.developer.occurredAt",
      "dataSources.extension.developer.retryable",
      "dataSources.extension.developer.attemptCount",
      "dataSources.extension.developer.recurrence",
      "dataSources.extension.developer.omittedCount",
      "macroStorage.schedule.disabled",
      "macroStorage.schedule.enabledCount_one",
      "macroStorage.schedule.enabledCount_other",
      "macroStorage.schedule.unknown",
      "macroStorage.schedule.title",
      "dataSources.schedule.sources.secCorporateActions.label",
      "dataSources.schedule.sources.secCorporateActions.description",
      "dataStorage.lifecycle.title",
      "dataStorage.lifecycle.description",
      "dataStorage.lifecycle.handoff",
      "dataStorage.lifecycle.openWorkflow",
      "dataStorage.lifecycle.summary.activeCases",
      "dataStorage.lifecycle.summary.sourceMissing",
    ] as const;
    const currentOwnerSettingsPaths = new Set([
      "workspace.routes.effortRequired",
      "workspace.routes.modelRetired",
      "models.route.effortRequired",
      "models.route.modelRetired",
      "models.catalog.selectEffort",
    ]);
    const retiredSettingsPaths = [
      "dataStorage.update.title",
      "dataStorage.update.never",
      "dataStorage.update.succeeded",
      "dataStorage.update.failed",
      "dataStorage.update.generatedAt",
      "macroStorage.snapshot.autoEnabled",
      "macroStorage.snapshot.autoDisabled",
      "dataSources.extension.status.detailFailuresRecorded_one",
      "dataSources.extension.status.detailFailuresRecorded_other",
    ] as const;
    const expectedSubtreeCounts = {
      actions: 18,
      workspace: 31,
      registry: 30,
      errors: 13,
      models: 70,
      runtime: 21,
      providers: 130,
      dataSources: 155,
      dataStorage: 65,
      newsStorage: 27,
      macroStorage: 31,
      investor: 140,
    } as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      const settings = resources[locale].settings as ResourceTree;
      const workspaceCount = flattenResource(
        (settings.investor as ResourceTree).workspace as ResourceTree,
      ).size;
      const flattenedSettings = flattenResource(settings);
      for (const path of postSliceSettingsPaths) {
        expect(flattenedSettings.has(path), `${locale}.settings.${path}`).toBe(true);
      }
      for (const path of retiredSettingsPaths) {
        expect(flattenedSettings.has(path), `${locale}.settings.${path}`).toBe(false);
      }
      const physicalPreSliceCount = flattenedSettings.size
        - workspaceCount
        + 5
        - postSliceSettingsPaths.length
        + retiredSettingsPaths.length;
      const commonModels = (resources[locale].common as ResourceTree).models as ResourceTree;
      expect(commonModels, `${locale}.common.models`).toBeDefined();
      if (!commonModels) continue;
      const movedModelCount = flattenResource(commonModels).size - 1;
      expect(physicalPreSliceCount).toBe(639);
      expect(movedModelCount).toBe(23);
      expect(physicalPreSliceCount + movedModelCount).toBe(662);
      expect(flattenResource(settings.locale as ResourceTree).size).toBe(3);
      expect(workspaceCount).toBe(95);
      for (const [subtree, count] of Object.entries(expectedSubtreeCounts)) {
        const currentAddedCount = postSliceSettingsPaths
          .filter((path) => (
            !currentOwnerSettingsPaths.has(path) && path.startsWith(`${subtree}.`)
          )).length;
        const currentRetiredCount = retiredSettingsPaths
          .filter((path) => path.startsWith(`${subtree}.`)).length;
        expect(
          flattenResource(settings[subtree] as ResourceTree).size
            - currentAddedCount
            + currentRetiredCount,
          `${locale}.${subtree}`,
        )
          .toBe(count);
      }
    }
  });
});
