export type SettingsGroupId = "ai_models" | "personalization" | "data_sync";

export type SettingsAnchorId =
  | "providers"
  | "models"
  | "fixed_task_runtime"
  | "research_runtime"
  | "investor_profile"
  | "data_sources"
  | "data_storage"
  | "news_storage"
  | "macro_storage";

export interface SettingsSectionDefinition {
  id: SettingsAnchorId;
  group: SettingsGroupId;
  title: string;
  description: string;
  keywords: readonly string[];
}

export interface SettingsGroupDefinition {
  id: SettingsGroupId;
  title: string;
  sections: readonly SettingsSectionDefinition[];
}

export const SETTINGS_GROUPS: readonly SettingsGroupDefinition[] = [
  {
    id: "ai_models",
    title: "AI 與模型",
    sections: [
      {
        id: "providers",
        group: "ai_models",
        title: "Provider 登入與憑證",
        description: "管理 AI provider 登入、訂閱與 API 憑證。",
        keywords: ["provider", "oauth", "api key", "credential", "憑證", "登入", "anthropic", "openai", "chatgpt", "claude"],
      },
      {
        id: "models",
        group: "ai_models",
        title: "模型與任務路由",
        description: "依任務選擇模型、provider 與推理強度。",
        keywords: ["model", "models", "模型", "任務", "路由", "routing", "effort"],
      },
      {
        id: "fixed_task_runtime",
        group: "ai_models",
        title: "固定 AI 任務執行限制",
        description: "設定 AI 卡片生成與翻譯的模型執行上界。",
        keywords: ["timeout", "runtime", "卡片生成", "卡片翻譯", "fixed task"],
      },
      {
        id: "research_runtime",
        group: "ai_models",
        title: "AI 研究執行限制",
        description: "設定 AI 研究 session 與單次執行限制。",
        keywords: ["ai 研究", "research", "timeout", "runtime", "session"],
      },
    ],
  },
  {
    id: "personalization",
    title: "個人化",
    sections: [
      {
        id: "investor_profile",
        group: "personalization",
        title: "投資人設定",
        description: "管理投資人輪廓、風險意願與研究個人化。",
        keywords: ["投資人", "個人化", "investor profile", "risk appetite", "風險意願", "風險承受能力"],
      },
    ],
  },
  {
    id: "data_sync",
    title: "資料與同步",
    sections: [
      {
        id: "data_sources",
        group: "data_sync",
        title: "資料來源與排程",
        description: "查看資料來源健康度、排程與瀏覽器擴充同步狀態。",
        keywords: [
          "data sources",
          "schedule",
          "資料來源",
          "排程",
          "health",
          "provider health",
          "credential",
          "seeking alpha",
          "sa extension",
          "ibkr client id",
          "IBKR 用戶端 ID",
        ],
      },
      {
        id: "data_storage",
        group: "data_sync",
        title: "市場資料",
        description: "查看價格、IV、基本面與交易日資料覆蓋。",
        keywords: ["market data", "市場資料", "price", "價格", "iv", "基本面", "coverage", "sqlite"],
      },
      {
        id: "news_storage",
        group: "data_sync",
        title: "新聞資料",
        description: "查看新聞資料量、攝入狀態與最近更新。",
        keywords: ["news", "新聞", "ingestion", "文章", "polygon", "finnhub", "ibkr"],
      },
      {
        id: "macro_storage",
        group: "data_sync",
        title: "總經資料",
        description: "查看 FRED series、資料快照與總經資料覆蓋。",
        keywords: [
          "macro",
          "總經",
          "總體經濟",
          "fred",
          "fred snapshot",
          "snapshot",
          "series",
          "observation",
          "資料快照",
        ],
      },
    ],
  },
];

export const SETTINGS_ANCHOR_IDS = SETTINGS_GROUPS.flatMap(
  (group) => group.sections.map((section) => section.id),
) as readonly SettingsAnchorId[];

const SECTIONS_BY_ID = new Map<SettingsAnchorId, SettingsSectionDefinition>(
  SETTINGS_GROUPS.flatMap((group) => group.sections.map((section) => [section.id, section] as const)),
);

const GROUPS_BY_SECTION_ID = new Map<SettingsAnchorId, SettingsGroupDefinition>(
  SETTINGS_GROUPS.flatMap((group) => group.sections.map((section) => [section.id, group] as const)),
);

const GROUPS_BY_ID = new Map<SettingsGroupId, SettingsGroupDefinition>(
  SETTINGS_GROUPS.map((group) => [group.id, group] as const),
);

export function settingsSection(id: SettingsAnchorId): SettingsSectionDefinition {
  const section = SECTIONS_BY_ID.get(id);
  if (!section) throw new Error(`unknown settings section: ${String(id)}`);
  return section;
}

export function settingsGroupFor(id: SettingsAnchorId): SettingsGroupDefinition {
  const group = GROUPS_BY_SECTION_ID.get(id);
  if (!group) throw new Error(`unknown settings section: ${String(id)}`);
  return group;
}

export function settingsGroup(id: SettingsGroupId): SettingsGroupDefinition {
  const group = GROUPS_BY_ID.get(id);
  if (!group) throw new Error(`unknown settings group: ${String(id)}`);
  return group;
}

export function firstSettingsAnchor(id: SettingsGroupId): SettingsAnchorId {
  const section = settingsGroup(id).sections[0];
  if (!section) throw new Error(`settings group has no sections: ${String(id)}`);
  return section.id;
}

export function settingsAnchorDomId(id: SettingsAnchorId): string {
  return `settings-${id}`;
}

function normalizeSearchValue(value: string): string {
  return value.normalize("NFKC").trim().toLowerCase();
}

export function searchSettings(query: string): readonly SettingsSectionDefinition[] {
  const normalizedQuery = normalizeSearchValue(query);
  const sections = SETTINGS_GROUPS.flatMap((group) => group.sections);
  if (!normalizedQuery) return sections;

  return sections.filter((section) => {
    const values = [section.title, section.description, ...section.keywords];
    return values.some((value) => normalizeSearchValue(value).includes(normalizedQuery));
  });
}
