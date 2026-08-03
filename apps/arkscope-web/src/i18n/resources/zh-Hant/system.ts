// Translation authority: docs/design/ARKSCOPE_TERMINOLOGY.md
const system = {
  sidecar: {
    loading: "正在連線至本機 Sidecar…",
    failure: "無法連線至本機 Sidecar",
    retry: "重試",
    ready: "本機 Sidecar 已連線。",
  },
  dataSourceSettings: "資料來源設定",
  developer: {
    heading: "Developer Mode",
    showDiagnostics: "顯示本機診斷資訊",
  },
  runtime: {
    modelsInUse: "Models in use",
    cardSynthesis: "card synthesis",
    cardTranslation: "card translation",
    anthropicDefaultAdvanced: "anthropic (default / advanced)",
    openAIDefaultAdvanced: "openai (default / advanced)",
    apiKeysPresent: "API keys present",
    keySet: "✓ set",
    keyMissing: "✗ missing",
  },
  status: {
    registryTools: "Registry tools",
    serverTime: "Server time",
    status: "Status",
    toolCategories: "Tool categories",
    dataSourcesTickers: "Data sources (tickers)",
    dataSourceLabels: {
      newsTickers: "新聞標的",
      priceTickers: "價格標的",
      storedSecFundamentals: "已儲存的 SEC 基本面",
      unknown: "未知資料來源（{{value}}）",
    },
  },
} as const;

export default system;
